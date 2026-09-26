#!/usr/bin/env python3
"""OpenRecomp Phase-17 P17-04R Revision 3 authenticated executable emission V1.

Build a deterministic, compiled, host-native runtime directly from the
authenticated P17-02 TITLE decode records.  Before any instruction is emitted,
the requested semantic record is checked against a fresh decode of the actual
authenticated private TITLE word at that PC.  Only verified decodes are emitted.

The generated artifact is a reusable C library exposing a persistent guest-state
execution interface (`or_title_execute_v1`) plus a separate deterministic test
harness.  The translated TITLE representation does not depend on a standalone
`main()` or a hard-coded synthetic initial state.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase9/src"):
    sys_path_extra = str(ROOT / extra) if extra else str(ROOT)
    if sys_path_extra not in sys.path:
        sys.path.insert(0, sys_path_extra)

import p3_decode_mips32_v1 as fresh_decode

P17_02_EVIDENCE = ROOT / ".openrecomp-phase17/evidence/P17-02/title_decode.json"

TITLE_ENTRY_PC = 0x800380A0
TITLE_TEXT_ADDR = 0x80038098
TITLE_TEXT_END = 0x8007E098
RAM_KSEG0_BASE = 0x80000000
RAM_SIZE = 2 * 1024 * 1024

# Operations implemented with exact semantics in the generated runtime.
SUPPORTED_OPS = frozenset(
    {
        "addu",
        "subu",
        "and",
        "or",
        "xor",
        "nor",
        "sll",
        "srl",
        "sra",
        "sllv",
        "srlv",
        "srav",
        "slt",
        "sltu",
        "addiu",
        "addi",
        "andi",
        "ori",
        "xori",
        "slti",
        "sltiu",
        "lui",
        "lw",
        "lh",
        "lhu",
        "lb",
        "lbu",
        "sw",
        "sh",
        "sb",
        "mult",
        "multu",
        "mflo",
        "mfhi",
        "nop",
        # Control flow implemented with explicit delay-slot handling.
        "beq",
        "bne",
        "blez",
        "bgtz",
        "bltz",
        "bgez",
        "j",
        "jal",
        "jr",
        "jalr",
    }
)

CONTROL_OPS = frozenset(
    {"beq", "bne", "blez", "bgtz", "bltz", "bgez", "j", "jal", "jr", "jalr"}
)

BRANCH_CONDITION_OPS = frozenset({"beq", "bne", "blez", "bgtz", "bltz", "bgez"})
JUMP_OPS = frozenset({"j", "jal"})
LINK_OPS = frozenset({"jal", "jalr"})

MASK32 = 0xFFFFFFFF


class TitleExecEmitError(ValueError):
    """Fail-closed rejection during authenticated executable emission."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class SemanticRecord:
    """One authenticated semantic record derived from a P17-02 decode record."""

    pc: int
    op: str
    rs: int
    rt: int
    rd: int
    shamt: int
    imm: int
    target: int | None
    delay_slot: int | None
    control_flow: bool
    terminator: str | None
    link: bool
    provenance_digest: str

    def asdict(self) -> dict[str, Any]:
        return {
            "pc": f"0x{self.pc:08x}",
            "op": self.op,
            "rs": self.rs,
            "rt": self.rt,
            "rd": self.rd,
            "shamt": self.shamt,
            "imm": self.imm,
            "target": (f"0x{self.target:08x}" if self.target is not None else None),
            "delay_slot": (f"0x{self.delay_slot:08x}" if self.delay_slot is not None else None),
            "control_flow": self.control_flow,
            "terminator": self.terminator,
            "link": self.link,
            "provenance_digest": self.provenance_digest,
        }


@dataclass
class EmissionContext:
    analysis: Any
    run_dir: pathlib.Path
    records: list[SemanticRecord] = field(default_factory=list)
    record_by_pc: dict[int, SemanticRecord] = field(default_factory=dict)
    h_path: pathlib.Path | None = None
    c_path: pathlib.Path | None = None
    harness_path: pathlib.Path | None = None
    so_path: pathlib.Path | None = None
    exe_path: pathlib.Path | None = None
    exe_result: dict[str, Any] | None = None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest_dict(doc: dict[str, Any], exclude_key: str | None = None) -> str:
    body = {k: v for k, v in doc.items() if k != exclude_key}
    return _sha256_bytes(json.dumps(body, sort_keys=True).encode("utf-8"))


def _load_p17_02_projection(path: pathlib.Path | None = None) -> dict[str, Any]:
    if path is None:
        path = P17_02_EVIDENCE
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        raise TitleExecEmitError("P17_02_EVIDENCE_UNAVAILABLE", str(path)) from exc
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TitleExecEmitError("P17_02_EVIDENCE_MALFORMED") from exc
    if not isinstance(doc, dict):
        raise TitleExecEmitError("P17_02_EVIDENCE_NOT_OBJECT")
    if doc.get("schema") != "openrecomp-phase17-title-decode-v1":
        raise TitleExecEmitError("P17_02_SCHEMA_MISMATCH")
    if doc.get("projection_digest") != _digest_dict(doc, "projection_digest"):
        raise TitleExecEmitError("P17_02_PROJECTION_DIGEST_MISMATCH")
    return doc


def verify_authenticated_analysis(analysis: Any) -> None:
    """Verify that *analysis* matches the committed P17-02 projection."""
    expected = _load_p17_02_projection()
    if analysis.projection.get("provenance", {}).get("title_payload_sha256") != expected.get("provenance", {}).get("title_payload_sha256"):
        raise TitleExecEmitError("TITLE_PAYLOAD_SHA256_MISMATCH")
    if analysis.projection.get("projection_digest") != expected.get("projection_digest"):
        raise TitleExecEmitError(
            "AUTHENTICATED_PROJECTION_MISMATCH",
            f"live={analysis.projection.get('projection_digest')} expected={expected.get('projection_digest')}",
        )


def _read_authenticated_word(analysis: Any, pc: int) -> int:
    """Read the actual 32-bit guest word from the authenticated private TITLE source."""
    t_addr = getattr(analysis.identity, "t_addr", TITLE_TEXT_ADDR)
    text_end = getattr(analysis.identity, "text_end", TITLE_TEXT_END)
    if not (t_addr <= pc < text_end) or pc & 3:
        raise TitleExecEmitError("AUTHENTICATED_SOURCE_PC_OUT_OF_RANGE", f"0x{pc:08x}")
    payload = analysis.identity.payload
    offset = pc - t_addr
    if offset < 0 or offset + 4 > len(payload):
        raise TitleExecEmitError("AUTHENTICATED_SOURCE_OFFSET_OUT_OF_RANGE", f"0x{pc:08x}")
    return struct.unpack_from("<I", payload, offset)[0]


def _sign16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _fresh_decode_word(pc: int, word: int) -> dict[str, Any]:
    """Decode *word* at *pc* and return normalized fields for comparison."""
    rec = fresh_decode.classify(pc, word)
    operands = rec.get("operands") or {}
    imm_raw = operands.get("imm")
    imm = _sign16(imm_raw) if imm_raw is not None else 0
    target = rec.get("target")
    return {
        "op": rec.get("op") or "unknown",
        "rs": int(operands.get("rs", 0)) & 0x1F,
        "rt": int(operands.get("rt", 0)) & 0x1F,
        "rd": int(operands.get("rd", 0)) & 0x1F,
        "shamt": int(operands.get("shamt", 0)) & 0x1F,
        "imm": imm,
        "target": (int(target) & MASK32) if target is not None else None,
        "control_flow": bool(rec.get("control_flow")),
        "terminator": rec.get("terminator"),
        "delay_slot": bool(rec.get("delay_slot")),
        "link": bool(rec.get("link")),
        "decode_class": rec.get("decode_class"),
    }


def _verify_record_against_fresh_decode(record: SemanticRecord, analysis: Any) -> None:
    """Authenticate one semantic record against the private TITLE word and fresh decode."""
    if record.pc not in analysis.records_by_address:
        raise TitleExecEmitError("UNAUTHENTICATED_RECORD", f"0x{record.pc:08x}")
    try:
        word = _read_authenticated_word(analysis, record.pc)
    except TitleExecEmitError:
        raise
    fresh = _fresh_decode_word(record.pc, word)

    if record.op != fresh["op"]:
        raise TitleExecEmitError(
            "OPCODE_MISMATCH",
            f"0x{record.pc:08x} record={record.op} fresh={fresh['op']}",
        )

    for field in ("rs", "rt", "rd", "shamt"):
        rec_val = getattr(record, field)
        fresh_val = fresh[field]
        if rec_val != fresh_val:
            raise TitleExecEmitError(
                "OPERAND_MISMATCH",
                f"0x{record.pc:08x} {field} record={rec_val} fresh={fresh_val}",
            )
    if record.imm != fresh["imm"]:
        raise TitleExecEmitError(
            "OPERAND_MISMATCH",
            f"0x{record.pc:08x} imm record={record.imm} fresh={fresh['imm']}",
        )

    if (record.target is None) != (fresh["target"] is None):
        raise TitleExecEmitError(
            "TARGET_MISMATCH",
            f"0x{record.pc:08x} target presence differs",
        )
    if record.target is not None and (record.target & MASK32) != (fresh["target"] & MASK32):
        raise TitleExecEmitError(
            "TARGET_MISMATCH",
            f"0x{record.pc:08x} target record=0x{record.target:08x} fresh=0x{fresh['target']:08x}",
        )

    if record.control_flow != fresh["control_flow"]:
        raise TitleExecEmitError(
            "CONTROL_FLOW_MISMATCH",
            f"0x{record.pc:08x} control_flow record={record.control_flow} fresh={fresh['control_flow']}",
        )
    if record.terminator != fresh["terminator"]:
        raise TitleExecEmitError(
            "CONTROL_FLOW_MISMATCH",
            f"0x{record.pc:08x} terminator record={record.terminator!r} fresh={fresh['terminator']!r}",
        )
    if bool(record.delay_slot) != fresh["delay_slot"]:
        raise TitleExecEmitError(
            "DELAY_SLOT_MISMATCH",
            f"0x{record.pc:08x} delay_slot record={record.delay_slot is not None} fresh={fresh['delay_slot']}",
        )
    if record.link != fresh["link"]:
        raise TitleExecEmitError(
            "CONTROL_FLOW_MISMATCH",
            f"0x{record.pc:08x} link record={record.link} fresh={fresh['link']}",
        )


def _provenance_digest_for_pc(analysis: Any, pc: int) -> str:
    prov = analysis.provenance.get(pc)
    if prov is None:
        raise TitleExecEmitError("MISSING_SOURCE_PROVENANCE", f"0x{pc:08x}")
    return _sha256_bytes(json.dumps(prov.asdict(), sort_keys=True).encode("utf-8"))


def _make_semantic_records(analysis: Any) -> list[SemanticRecord]:
    """Derive semantic records from authenticated decode records and verify each word."""
    records: list[SemanticRecord] = []
    delay_by_owner: dict[int, int] = analysis.delay_by_owner
    raw_by_pc: dict[int, dict[str, Any]] = analysis.records_by_address

    for pc in sorted(analysis.frontier["reachable_addresses"]):
        raw = raw_by_pc[pc]
        op = raw.get("op") or "unknown"
        operands = raw.get("operands") or {}
        provenance_digest = _provenance_digest_for_pc(analysis, pc)
        delay_slot = delay_by_owner.get(pc)

        record = SemanticRecord(
            pc=pc,
            op=op,
            rs=int(operands.get("rs", 0)) & 0x1F,
            rt=int(operands.get("rt", 0)) & 0x1F,
            rd=int(operands.get("rd", 0)) & 0x1F,
            shamt=int(operands.get("shamt", 0)) & 0x1F,
            imm=_sign16(int(operands.get("imm", 0)) & 0xFFFF),
            target=(int(operands["target"]) & MASK32) if operands.get("target") is not None else None,
            delay_slot=(delay_slot & MASK32) if delay_slot is not None else None,
            control_flow=bool(raw.get("control_flow")),
            terminator=raw.get("terminator"),
            link=bool(raw.get("link")),
            provenance_digest=provenance_digest,
        )
        _verify_record_against_fresh_decode(record, analysis)
        records.append(record)

    for owner, delay in delay_by_owner.items():
        if delay not in raw_by_pc:
            raise TitleExecEmitError("DELAY_SLOT_RECORD_MISSING", f"owner=0x{owner:08x} delay=0x{delay:08x}")

    return records


def _ram_offset(address: int) -> int:
    """Translate a KSEG0/KSEG1/KUSEG RAM address to a flat offset (fail closed)."""
    if RAM_KSEG0_BASE <= address < RAM_KSEG0_BASE + RAM_SIZE:
        return address - RAM_KSEG0_BASE
    if 0xA0000000 <= address < 0xA0000000 + RAM_SIZE:
        return address - 0xA0000000
    if 0x00000000 <= address < RAM_SIZE:
        return address
    raise TitleExecEmitError("UNSUPPORTED_ADDRESS_SEGMENT", f"0x{address:08x}")


def _hex_bytes(data: bytes) -> str:
    """Deterministic C byte array literal."""
    items = [f"0x{b:02x}" for b in data]
    lines = []
    for i in range(0, len(items), 16):
        lines.append(", ".join(items[i : i + 16]))
    return "\n".join("    " + line + "," for line in lines)


def _emit_delay_slot(ctx: EmissionContext, owner_pc: int, indent: str = "        ") -> list[str]:
    """Emit the verified delay-slot instruction for a control transfer."""
    delay_pc = ctx.analysis.delay_by_owner.get(owner_pc)
    if delay_pc is None:
        return [f'{indent}state->stop = 1; strncpy(state->stop_reason, "MISSING_DELAY_SLOT", sizeof(state->stop_reason) - 1); break;']
    rec = ctx.record_by_pc[delay_pc]
    lines = [f"{indent}/* delay slot 0x{delay_pc:08x} */"]
    lines.append(f"{indent}state->delay_active = 1;")
    lines.append(f"{indent}state->delay_pc = 0x{delay_pc:08x}u;")
    lines.append(f"{indent}state->step_count++;")
    lines.append(f"{indent}if (services && services->transcript) {{ services->transcript(services->user_data, 0x{delay_pc:08x}u, op_name_for_pc(0x{delay_pc:08x}u), state->step_count); }}")
    lines.extend(_emit_instruction(rec, ctx, indent, is_delay_slot=True))
    lines.append(f"{indent}state->delay_active = 0;")
    return lines


def _emit_instruction(rec: SemanticRecord, ctx: EmissionContext, indent: str = "        ", *, is_delay_slot: bool = False) -> list[str]:
    """Emit C statements implementing one verified semantic record."""
    op = rec.op
    rs, rt, rd = rec.rs, rec.rt, rec.rd
    imm = rec.imm
    target = rec.target
    out: list[str] = []

    def line(code: str) -> None:
        out.append(f"{indent}{code}")

    if is_delay_slot:
        line("state->regs[0] = 0;")
    else:
        line("state->step_count++;")
        line("if (services && services->transcript) { services->transcript(services->user_data, state->pc, op_name_for_pc(state->pc), state->step_count); }")
        line("state->regs[0] = 0;")

    if op == "nop":
        pass
    elif op == "addu":
        line(f"state->regs[{rd}] = state->regs[{rs}] + state->regs[{rt}];")
    elif op == "subu":
        line(f"state->regs[{rd}] = state->regs[{rs}] - state->regs[{rt}];")
    elif op == "and":
        line(f"state->regs[{rd}] = state->regs[{rs}] & state->regs[{rt}];")
    elif op == "or":
        line(f"state->regs[{rd}] = state->regs[{rs}] | state->regs[{rt}];")
    elif op == "xor":
        line(f"state->regs[{rd}] = state->regs[{rs}] ^ state->regs[{rt}];")
    elif op == "nor":
        line(f"state->regs[{rd}] = ~(state->regs[{rs}] | state->regs[{rt}]);")
    elif op == "sll":
        line(f"state->regs[{rd}] = state->regs[{rt}] << {rec.shamt};")
    elif op == "srl":
        line(f"state->regs[{rd}] = state->regs[{rt}] >> {rec.shamt};")
    elif op == "sra":
        line(f"state->regs[{rd}] = (uint32_t)(((int32_t)state->regs[{rt}]) >> {rec.shamt});")
    elif op == "sllv":
        line(f"state->regs[{rd}] = state->regs[{rt}] << (state->regs[{rs}] & 0x1f);")
    elif op == "srlv":
        line(f"state->regs[{rd}] = state->regs[{rt}] >> (state->regs[{rs}] & 0x1f);")
    elif op == "srav":
        line(f"state->regs[{rd}] = (uint32_t)(((int32_t)state->regs[{rt}]) >> (state->regs[{rs}] & 0x1f));")
    elif op == "slt":
        line(f"state->regs[{rd}] = ((int32_t)state->regs[{rs}] < (int32_t)state->regs[{rt}]) ? 1 : 0;")
    elif op == "sltu":
        line(f"state->regs[{rd}] = (state->regs[{rs}] < state->regs[{rt}]) ? 1 : 0;")
    elif op == "addiu":
        line(f"state->regs[{rt}] = state->regs[{rs}] + (int32_t)(int16_t)({imm & 0xFFFF}u);")
    elif op == "addi":
        line("{")
        line(f"  int32_t _a = (int32_t)state->regs[{rs}];")
        line(f"  int32_t _b = (int32_t)(int16_t)({imm & 0xFFFF}u);")
        line(f"  int32_t _r = _a + _b;")
        line(f"  if (((_a ^ _b) & 0x80000000) == 0 && ((_a ^ _r) & 0x80000000) != 0) {{ state->stop = 1; strncpy(state->stop_reason, \"SIGNED_OVERFLOW\", sizeof(state->stop_reason) - 1); break; }}")
        line(f"  state->regs[{rt}] = (uint32_t)_r;")
        line("}")
    elif op == "andi":
        line(f"state->regs[{rt}] = state->regs[{rs}] & {imm & 0xFFFF}u;")
    elif op == "ori":
        line(f"state->regs[{rt}] = state->regs[{rs}] | {imm & 0xFFFF}u;")
    elif op == "xori":
        line(f"state->regs[{rt}] = state->regs[{rs}] ^ {imm & 0xFFFF}u;")
    elif op == "slti":
        line(f"state->regs[{rt}] = ((int32_t)state->regs[{rs}] < (int32_t)(int16_t)({imm & 0xFFFF}u)) ? 1 : 0;")
    elif op == "sltiu":
        line(f"state->regs[{rt}] = (state->regs[{rs}] < (uint32_t)({imm & 0xFFFF}u)) ? 1 : 0;")
    elif op == "lui":
        line(f"state->regs[{rt}] = {imm & 0xFFFF}u << 16;")
    elif op in ("lw", "lh", "lhu", "lb", "lbu", "sw", "sh", "sb"):
        width = {"lw": 4, "lh": 2, "lhu": 2, "lb": 1, "lbu": 1, "sw": 4, "sh": 2, "sb": 1}[op]
        line(f"{{ uint32_t _addr = state->regs[{rs}] + (int32_t)(int16_t)({imm & 0xFFFF}u);")
        if width == 4:
            line(f"  if ((_addr & 3u) != 0 || !ram_check(_addr)) {{ state->stop = 1; strncpy(state->stop_reason, \"UNALIGNED_OR_OUT_OF_BOUNDS_MEMORY_ACCESS\", sizeof(state->stop_reason) - 1); break; }}")
        elif width == 2:
            line(f"  if ((_addr & 1u) != 0 || !ram_check(_addr)) {{ state->stop = 1; strncpy(state->stop_reason, \"UNALIGNED_OR_OUT_OF_BOUNDS_MEMORY_ACCESS\", sizeof(state->stop_reason) - 1); break; }}")
        else:
            line(f"  if (!ram_check(_addr)) {{ state->stop = 1; strncpy(state->stop_reason, \"OUT_OF_BOUNDS_MEMORY_ACCESS\", sizeof(state->stop_reason) - 1); break; }}")
        if op == "lw":
            line(f"  state->regs[{rt}] = ram_load_u32(_addr);")
        elif op == "lh":
            line(f"  state->regs[{rt}] = (uint32_t)(int32_t)(int16_t)ram_load_u16(_addr);")
        elif op == "lhu":
            line(f"  state->regs[{rt}] = ram_load_u16(_addr);")
        elif op == "lb":
            line(f"  state->regs[{rt}] = (uint32_t)(int32_t)(int8_t)ram_load_u8(_addr);")
        elif op == "lbu":
            line(f"  state->regs[{rt}] = ram_load_u8(_addr);")
        elif op == "sw":
            line(f"  ram_store_u32(_addr, state->regs[{rt}]);")
        elif op == "sh":
            line(f"  ram_store_u16(_addr, state->regs[{rt}] & 0xffff);")
        elif op == "sb":
            line(f"  ram_store_u8(_addr, state->regs[{rt}] & 0xff);")
        line("}")
    elif op == "mult":
        line("{")
        line("  int64_t _prod = (int64_t)(int32_t)state->regs[{rs}] * (int64_t)(int32_t)state->regs[{rt}];".format(rs=rs, rt=rt))
        line("  state->lo = (uint32_t)_prod;")
        line("  state->hi = (uint32_t)(_prod >> 32);")
        line("}")
    elif op == "multu":
        line("{")
        line("  uint64_t _prod = (uint64_t)state->regs[{rs}] * (uint64_t)state->regs[{rt}];".format(rs=rs, rt=rt))
        line("  state->lo = (uint32_t)_prod;")
        line("  state->hi = (uint32_t)(_prod >> 32);")
        line("}")
    elif op == "mflo":
        line(f"state->regs[{rd}] = state->lo;")
    elif op == "mfhi":
        line(f"state->regs[{rd}] = state->hi;")
    elif op in JUMP_OPS:
        if target is None:
            line("state->stop = 1; strncpy(state->stop_reason, \"JUMP_WITHOUT_TARGET\", sizeof(state->stop_reason) - 1); break;")
            return out
        if op == "jal":
            # Direct calls are unsupported in this bounded runtime.
            line("state->stop = 1; strncpy(state->stop_reason, \"UNSUPPORTED_DIRECT_CALL\", sizeof(state->stop_reason) - 1); break;")
            return out
        out.extend(_emit_delay_slot(ctx, rec.pc))
        line(f"state->pc = 0x{target:08x}u;")
        line("break;")
        return out
    elif op in BRANCH_CONDITION_OPS:
        cond = {
            "beq": f"state->regs[{rs}] == state->regs[{rt}]",
            "bne": f"state->regs[{rs}] != state->regs[{rt}]",
            "blez": f"(int32_t)state->regs[{rs}] <= 0",
            "bgtz": f"(int32_t)state->regs[{rs}] > 0",
            "bltz": f"(int32_t)state->regs[{rs}] < 0",
            "bgez": f"(int32_t)state->regs[{rs}] >= 0",
        }[op]
        if target is None:
            line("state->stop = 1; strncpy(state->stop_reason, \"BRANCH_WITHOUT_TARGET\", sizeof(state->stop_reason) - 1); break;")
            return out
        line(f"{{ int _cond = ({cond}) ? 1 : 0;")
        out.extend(_emit_delay_slot(ctx, rec.pc))
        line(f"  state->pc = _cond ? 0x{target:08x}u : 0x{rec.pc + 8:08x}u;")
        line("}")
        line("break;")
        return out
    elif op == "jr":
        line(f"{{ uint32_t _target = state->regs[{rs}];")
        out.extend(_emit_delay_slot(ctx, rec.pc))
        line(f"  state->pc = _target;")
        line("}")
        line("break;")
        return out
    elif op == "jalr":
        line(f"{{ uint32_t _target = state->regs[{rs}];")
        if rd != 0:
            line(f"  state->regs[{rd}] = 0x{rec.pc + 8:08x}u;")
        out.extend(_emit_delay_slot(ctx, rec.pc))
        line(f"  state->pc = _target;")
        line("}")
        line("break;")
        return out
    else:
        line(f"state->stop = 1; strncpy(state->stop_reason, \"UNSUPPORTED_OPERATION\", sizeof(state->stop_reason) - 1); break;")
        return out

    if is_delay_slot:
        return out

    line(f"state->pc = 0x{rec.pc + 4:08x}u;")
    line("break;")
    return out


def _generate_runtime_h(ctx: EmissionContext) -> str:
    """Generate the public interface header for the reusable runtime."""
    return """/* Generated by p17_title_exec_emit_v1.py from authenticated P17-02 records. */
#ifndef OR_TITLE_RUNTIME_V1_H
#define OR_TITLE_RUNTIME_V1_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OR_TITLE_RAM_SIZE 2097152u
#define OR_TITLE_RAM_KSEG0_BASE 0x80000000u

/* Persistent guest-state container.  The caller owns the object and may
   re-execute with modified state.  All fields are in/out unless documented. */
struct or_guest_state_v1 {
    uint32_t regs[32];   /* in/out; r0 is hardwired to zero by the runtime */
    uint32_t pc;         /* in/out */
    uint32_t next_pc;    /* out; pc after the current step (for debugging) */
    uint32_t hi;         /* in/out */
    uint32_t lo;         /* in/out */
    uint32_t delay_pc;   /* out; PC of the currently executing delay slot */
    int      delay_active; /* out; non-zero while a delay slot executes */
    uint32_t step_count; /* in/out; incremented for every guest instruction */
    uint32_t budget;     /* in; execution stops when step_count reaches budget */
    int      stop;       /* out */
    char     stop_reason[64]; /* out */
};

/* Bounded runtime services.  All pointers may be NULL to select defaults. */
struct or_runtime_services_v1 {
    void *user_data;
    void (*transcript)(void *user_data, uint32_t pc, const char *op, uint32_t step);
    int (*host_call)(void *user_data, const char *symbol,
                     const uint64_t *args, uint64_t argc,
                     uint64_t *out_value, uint32_t *out_has_value);
    uint8_t *ram_base;   /* if NULL, a static RAM array is used */
    uint32_t ram_size;   /* must be OR_TITLE_RAM_SIZE if ram_base is non-NULL */
};

/* Execute from *state* until stop, budget exhaustion, or an unsupported
   condition.  Returns 0 on a controlled stop (see state->stop_reason). */
int or_title_execute_v1(struct or_guest_state_v1 *state,
                        const struct or_runtime_services_v1 *services);

#ifdef __cplusplus
}
#endif

#endif
"""


def _generate_runtime_c(ctx: EmissionContext) -> str:
    """Generate the deterministic C library for the authenticated runtime."""
    analysis = ctx.analysis
    payload = analysis.identity.payload
    records = ctx.records
    ctx.record_by_pc = {rec.pc: rec for rec in records}

    op_name_cases: list[str] = []
    for rec in records:
        op_name_cases.append(f"        case 0x{rec.pc:08x}u: return \"{rec.op}\";")

    instruction_cases: list[str] = []
    for rec in records:
        label = f"        case 0x{rec.pc:08x}u:"
        body = _emit_instruction(rec, ctx)
        instruction_cases.append(label + "\n" + "\n".join(body))

    payload_literal = _hex_bytes(payload)
    payload_offset = TITLE_TEXT_ADDR - RAM_KSEG0_BASE

    vocabulary = sorted({rec.op for rec in records if rec.op in SUPPORTED_OPS})
    provenance_digest = _sha256_bytes(
        json.dumps([rec.provenance_digest for rec in records], sort_keys=True).encode("utf-8")
    )

    source = f"""/* Generated by p17_title_exec_emit_v1.py from authenticated P17-02 records. */
/* Semantic vocabulary: {", ".join(vocabulary)} */
/* Provenance digest: {provenance_digest} */
#include "or_title_runtime_v1.h"
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#define RAM_SIZE OR_TITLE_RAM_SIZE
#define RAM_KSEG0_BASE OR_TITLE_RAM_KSEG0_BASE

static uint8_t g_default_ram[RAM_SIZE];
static uint8_t *g_ram = g_default_ram;

static const uint8_t g_payload[{len(payload)}] = {{
{payload_literal}
}};

static int ram_check(uint32_t addr) {{
    return (RAM_KSEG0_BASE <= addr && addr < RAM_KSEG0_BASE + RAM_SIZE) ||
           (0xa0000000u <= addr && addr < 0xa0000000u + RAM_SIZE) ||
           (addr < RAM_SIZE);
}}

static uint32_t ram_offset(uint32_t addr) {{
    if (RAM_KSEG0_BASE <= addr && addr < RAM_KSEG0_BASE + RAM_SIZE) return addr - RAM_KSEG0_BASE;
    if (0xa0000000u <= addr && addr < 0xa0000000u + RAM_SIZE) return addr - 0xa0000000u;
    return addr;
}}

static uint32_t ram_load_u32(uint32_t addr) {{
    uint32_t off = ram_offset(addr);
    return (uint32_t)g_ram[off] | ((uint32_t)g_ram[off + 1] << 8) |
           ((uint32_t)g_ram[off + 2] << 16) | ((uint32_t)g_ram[off + 3] << 24);
}}

static uint16_t ram_load_u16(uint32_t addr) {{
    uint32_t off = ram_offset(addr);
    return (uint16_t)g_ram[off] | ((uint16_t)g_ram[off + 1] << 8);
}}

static uint8_t ram_load_u8(uint32_t addr) {{
    return g_ram[ram_offset(addr)];
}}

static void ram_store_u32(uint32_t addr, uint32_t value) {{
    uint32_t off = ram_offset(addr);
    g_ram[off] = (uint8_t)value;
    g_ram[off + 1] = (uint8_t)(value >> 8);
    g_ram[off + 2] = (uint8_t)(value >> 16);
    g_ram[off + 3] = (uint8_t)(value >> 24);
}}

static void ram_store_u16(uint32_t addr, uint16_t value) {{
    uint32_t off = ram_offset(addr);
    g_ram[off] = (uint8_t)value;
    g_ram[off + 1] = (uint8_t)(value >> 8);
}}

static void ram_store_u8(uint32_t addr, uint8_t value) {{
    g_ram[ram_offset(addr)] = value;
}}

static void ram_digest(uint8_t *out) {{
    uint32_t h0 = 0x6a09e667u, h1 = 0xbb67ae85u, h2 = 0x3c6ef372u, h3 = 0xa54ff53au;
    for (uint32_t i = 0; i < RAM_SIZE; i += 4) {{
        uint32_t w = (uint32_t)g_ram[i] | ((uint32_t)g_ram[i + 1] << 8) |
                     ((uint32_t)g_ram[i + 2] << 16) | ((uint32_t)g_ram[i + 3] << 24);
        h0 ^= w;
        h1 ^= (w << 7) | (w >> 25);
        h2 += w;
        h3 ^= (w >> 11) | (w << 21);
        uint32_t t = h0;
        h0 = h1;
        h1 = h2;
        h2 = h3;
        h3 = t;
    }}
    out[0] = (uint8_t)h0; out[1] = (uint8_t)(h0 >> 8); out[2] = (uint8_t)(h0 >> 16); out[3] = (uint8_t)(h0 >> 24);
    out[4] = (uint8_t)h1; out[5] = (uint8_t)(h1 >> 8); out[6] = (uint8_t)(h1 >> 16); out[7] = (uint8_t)(h1 >> 24);
    out[8] = (uint8_t)h2; out[9] = (uint8_t)(h2 >> 8); out[10] = (uint8_t)(h2 >> 16); out[11] = (uint8_t)(h2 >> 24);
    out[12] = (uint8_t)h3; out[13] = (uint8_t)(h3 >> 8); out[14] = (uint8_t)(h3 >> 16); out[15] = (uint8_t)(h3 >> 24);
}}

static const char *op_name_for_pc(uint32_t pc) {{
    switch (pc) {{
{chr(10).join(op_name_cases)}
        default: return "?";
    }}
}}

int or_title_execute_v1(struct or_guest_state_v1 *state,
                        const struct or_runtime_services_v1 *services) {{
    if (!state) return -1;
    if (services && services->ram_base) {{
        if (services->ram_size != RAM_SIZE) {{
            state->stop = 1;
            strncpy(state->stop_reason, "SERVICES_RAM_SIZE_MISMATCH", sizeof(state->stop_reason) - 1);
            return 0;
        }}
        g_ram = services->ram_base;
    }} else {{
        g_ram = g_default_ram;
    }}
    memcpy(g_ram + {payload_offset}u, g_payload, sizeof(g_payload));
    state->stop = 0;
    state->delay_active = 0;
    state->delay_pc = 0;

    while (!state->stop) {{
        state->regs[0] = 0;
        if (state->step_count >= state->budget) {{
            state->stop = 1;
            strncpy(state->stop_reason, "STEP_LIMIT_REACHED", sizeof(state->stop_reason) - 1);
            break;
        }}
        state->next_pc = state->pc;
        switch (state->pc) {{
{chr(10).join(instruction_cases)}
            default:
                state->stop = 1;
                strncpy(state->stop_reason, "PC_NOT_IN_AUTHENTICATED_TABLE", sizeof(state->stop_reason) - 1);
                break;
        }}
    }}
    return 0;
}}
"""
    return source


def _generate_harness_c(ctx: EmissionContext, entry_pc: int) -> str:
    """Generate a deterministic test harness that calls or_title_execute_v1."""
    provenance_digest = _sha256_bytes(
        json.dumps([rec.provenance_digest for rec in ctx.records], sort_keys=True).encode("utf-8")
    )
    vocabulary = sorted({rec.op for rec in ctx.records if rec.op in SUPPORTED_OPS})
    vocab_literal = ", ".join(f'"{op}"' for op in vocabulary)
    return f"""/* Generated deterministic harness for or_title_execute_v1. */
#include "or_title_runtime_v1.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define RAM_SIZE OR_TITLE_RAM_SIZE

static uint8_t g_harness_ram[RAM_SIZE];

static void hex32(char *out, uint32_t value) {{
    const char *hex = "0123456789abcdef";
    for (int i = 7; i >= 0; i--) {{
        out[7 - i] = hex[(value >> (i * 4)) & 0xf];
    }}
    out[8] = '\\0';
}}

static void ram_digest(uint8_t *out) {{
    uint32_t h0 = 0x6a09e667u, h1 = 0xbb67ae85u, h2 = 0x3c6ef372u, h3 = 0xa54ff53au;
    for (uint32_t i = 0; i < RAM_SIZE; i += 4) {{
        uint32_t w = (uint32_t)g_harness_ram[i] | ((uint32_t)g_harness_ram[i + 1] << 8) |
                     ((uint32_t)g_harness_ram[i + 2] << 16) | ((uint32_t)g_harness_ram[i + 3] << 24);
        h0 ^= w;
        h1 ^= (w << 7) | (w >> 25);
        h2 += w;
        h3 ^= (w >> 11) | (w << 21);
        uint32_t t = h0;
        h0 = h1;
        h1 = h2;
        h2 = h3;
        h3 = t;
    }}
    out[0] = (uint8_t)h0; out[1] = (uint8_t)(h0 >> 8); out[2] = (uint8_t)(h0 >> 16); out[3] = (uint8_t)(h0 >> 24);
    out[4] = (uint8_t)h1; out[5] = (uint8_t)(h1 >> 8); out[6] = (uint8_t)(h1 >> 16); out[7] = (uint8_t)(h1 >> 24);
    out[8] = (uint8_t)h2; out[9] = (uint8_t)(h2 >> 8); out[10] = (uint8_t)(h2 >> 16); out[11] = (uint8_t)(h2 >> 24);
    out[12] = (uint8_t)h3; out[13] = (uint8_t)(h3 >> 8); out[14] = (uint8_t)(h3 >> 16); out[15] = (uint8_t)(h3 >> 24);
}}

int main(void) {{
    struct or_guest_state_v1 state;
    struct or_runtime_services_v1 services;
    memset(&state, 0, sizeof(state));
    memset(&services, 0, sizeof(services));
    state.pc = 0x{entry_pc:08x}u;
    state.budget = 100000u;
    services.ram_base = g_harness_ram;
    services.ram_size = RAM_SIZE;

    or_title_execute_v1(&state, &services);

    uint8_t rdigest[16];
    ram_digest(rdigest);
    uint8_t regdigest[16];
    {{
        uint32_t h0 = 0x6a09e667u, h1 = 0xbb67ae85u;
        for (int i = 0; i < 32; i++) {{
            h0 ^= state.regs[i];
            h1 += state.regs[i];
        }}
        h0 ^= state.pc ^ state.hi ^ state.lo;
        h1 += state.pc + state.hi + state.lo;
        regdigest[0] = (uint8_t)h0; regdigest[1] = (uint8_t)(h0 >> 8); regdigest[2] = (uint8_t)(h0 >> 16); regdigest[3] = (uint8_t)(h0 >> 24);
        regdigest[4] = (uint8_t)h1; regdigest[5] = (uint8_t)(h1 >> 8); regdigest[6] = (uint8_t)(h1 >> 16); regdigest[7] = (uint8_t)(h1 >> 24);
        regdigest[8] = (uint8_t)state.step_count; regdigest[9] = (uint8_t)(state.step_count >> 8);
        regdigest[10] = (uint8_t)state.stop; regdigest[11] = 0;
        memset(regdigest + 12, 0, 4);
    }}

    char pc_str[9], final_pc_str[9];
    hex32(pc_str, 0x{entry_pc:08x}u);
    hex32(final_pc_str, state.pc);

    printf("{{\\n");
    printf("  \\"schema\\": \\"openrecomp-phase17-title-runtime-result-v1\\",\\n");
    printf("  \\"entry_pc\\": \\"0x%s\\",\\n", pc_str);
    printf("  \\"executed_instruction_count\\": %u,\\n", state.step_count);
    printf("  \\"final_pc\\": \\"0x%s\\",\\n", final_pc_str);
    printf("  \\"stop_reason\\": \\"%s\\",\\n", state.stop_reason);
    printf("  \\"register_digest\\": \\"");
    for (int i = 0; i < 16; i++) printf("%02x", regdigest[i]);
    printf("\\",\\n");
    printf("  \\"ram_digest\\": \\"");
    for (int i = 0; i < 16; i++) printf("%02x", rdigest[i]);
    printf("\\",\\n");
    printf("  \\"provenance_digest\\": \\"{provenance_digest}\\",\\n");
    printf("  \\"semantic_vocabulary\\": [");
    const char *vocabulary[] = {{{vocab_literal}}};
    for (size_t i = 0; i < {len(vocabulary)}; i++) {{
        if (i) printf(", ");
        printf("\\"%s\\"", vocabulary[i]);
    }}
    printf("]\\n");
    printf("}}\\n");
    return 0;
}}
"""


def _compile_c(c_path: pathlib.Path, exe_path: pathlib.Path, extra_flags: tuple[str, ...] = ()) -> None:
    cmd = [
        "cc",
        "-O0",
        "-std=c11",
        "-fno-stack-protector",
        "-fno-asynchronous-unwind-tables",
        "-frandom-seed=or_title_runtime_v1",
        "-Wl,--build-id=none",
        *extra_flags,
        "-o",
        str(exe_path),
        str(c_path),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise TitleExecEmitError(
            "NATIVE_COMPILE_FAILED",
            completed.stderr or completed.stdout,
        )


def _run(exe_path: pathlib.Path) -> dict[str, Any]:
    completed = subprocess.run([str(exe_path)], capture_output=True, text=True)
    if completed.returncode != 0:
        raise TitleExecEmitError("RUNTIME_EXIT_NONZERO", completed.stderr)
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise TitleExecEmitError("RUNTIME_OUTPUT_NOT_JSON", completed.stdout[:200]) from exc
    return result


def _write_files(ctx: EmissionContext, entry_pc: int) -> None:
    ctx.h_path = ctx.run_dir / "or_title_runtime_v1.h"
    ctx.c_path = ctx.run_dir / "or_title_runtime_v1.c"
    ctx.harness_path = ctx.run_dir / "or_title_runtime_harness_v1.c"

    ctx.h_path.write_text(_generate_runtime_h(ctx), encoding="utf-8", newline="\n")
    ctx.c_path.write_text(_generate_runtime_c(ctx), encoding="utf-8", newline="\n")
    ctx.harness_path.write_text(_generate_harness_c(ctx, entry_pc), encoding="utf-8", newline="\n")


def _compile_files(ctx: EmissionContext) -> None:
    ctx.so_path = ctx.run_dir / "or_title_runtime_v1.so"
    ctx.exe_path = ctx.run_dir / "or_title_runtime_v1"
    include_flag = f"-I{ctx.run_dir}"
    # Shared library exposing the reusable interface.
    _compile_c(
        ctx.c_path,
        ctx.so_path,
        extra_flags=("-shared", "-fPIC", include_flag),
    )
    # Deterministic harness executable.
    _compile_c(
        ctx.harness_path,
        ctx.exe_path,
        extra_flags=(include_flag, str(ctx.c_path)),
    )


def emit_executable(
    analysis: Any,
    run_dir: pathlib.Path | None = None,
) -> dict[str, Any]:
    """Emit, compile, and run the authenticated TITLE executable runtime.

    Returns a public-safe emission manifest with source/executable hashes and
    the runtime result.  All raw-bearing artifacts live only in *run_dir*.
    """
    verify_authenticated_analysis(analysis)

    if run_dir is None:
        run_dir = pathlib.Path(tempfile.mkdtemp(prefix="p17-04r-"))
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    ctx = EmissionContext(analysis=analysis, run_dir=run_dir)
    ctx.records = _make_semantic_records(analysis)

    _write_files(ctx, TITLE_ENTRY_PC)
    _compile_files(ctx)
    ctx.exe_result = _run(ctx.exe_path)

    source_hash = _sha256_bytes(ctx.c_path.read_bytes())
    exe_hash = _sha256_bytes(ctx.exe_path.read_bytes())
    h_hash = _sha256_bytes(ctx.h_path.read_bytes())
    harness_hash = _sha256_bytes(ctx.harness_path.read_bytes())
    so_hash = _sha256_bytes(ctx.so_path.read_bytes())

    provenance_digest = _sha256_bytes(
        json.dumps([rec.provenance_digest for rec in ctx.records], sort_keys=True).encode("utf-8")
    )

    manifest = {
        "schema": "openrecomp-phase17-title-exec-emission-v1",
        "stage": "P17-04R",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "emission_kind": "AUTHENTICATED_GENERATED_C_RUNTIME",
        "interface": {
            "header": "or_title_runtime_v1.h",
            "execute_symbol": "or_title_execute_v1",
            "guest_state_struct": "or_guest_state_v1",
            "services_struct": "or_runtime_services_v1",
        },
        "source": {
            "p17_02_projection_digest": analysis.projection["projection_digest"],
            "title_payload_sha256": analysis.projection["provenance"]["title_payload_sha256"],
            "entry_pc": f"0x{TITLE_ENTRY_PC:08x}",
            "header_sha256": h_hash,
            "generated_source_sha256": source_hash,
            "generated_harness_sha256": harness_hash,
            "semantic_vocabulary": sorted({rec.op for rec in ctx.records if rec.op in SUPPORTED_OPS}),
            "reachable_record_count": len(ctx.records),
            "provenance_digest": provenance_digest,
        },
        "build": {
            "compiler_command": "cc -O0 -std=c11 -fno-stack-protector -fno-asynchronous-unwind-tables -frandom-seed=or_title_runtime_v1 -Wl,--build-id=none",
            "executable_sha256": exe_hash,
            "shared_object_sha256": so_hash,
            "runtime_result_schema": "openrecomp-phase17-title-runtime-result-v1",
        },
        "active_build": {
            "phase17_emitter": "p17_title_exec_emit_v1.py",
            "phase16_hand_authored_title_guest_flow": "EXCLUDED",
            "phase16_guest_flow_imports": [],
            "execution": "GENERATED_NATIVE_RUNTIME",
            "rejected_p17_04_address_inventory_path": "EXCLUDED",
        },
        "runtime_result": ctx.exe_result,
        "claims": {
            "initialization": "NOT_PROVEN",
            "frame": "NOT_PROVEN",
            "playability": "NOT_PROVEN",
            "general_compatibility": "NOT_PROVEN",
            "first_frame_ready": "NO",
        },
    }
    manifest["emission_digest"] = _digest_dict(manifest, "emission_digest")
    return manifest


def emit_synthetic_executable(
    records: list[dict[str, Any]],
    payload_words: list[int],
    entry: int,
    run_dir: pathlib.Path,
    t_addr: int = 0x80038000,
    delay_by_owner: dict[int, int] | None = None,
) -> dict[str, Any]:
    """Emit and run a synthetic open test program using the same runtime generator.

    *records* are dictionaries with the same keys as a P17-02 decode record.
    The payload is built from *payload_words* and loaded at *t_addr*.
    *delay_by_owner* maps owner PC -> delay-slot PC for explicit delay handling.
    """
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    payload = b"".join(struct.pack("<I", w & MASK32) for w in payload_words)
    text_end = t_addr + len(payload)

    _payload = payload
    _t_addr = t_addr
    _text_end = text_end
    _delay_by_owner = dict(delay_by_owner) if delay_by_owner else {}

    class _FakeIdentity:
        payload = _payload
        t_addr = _t_addr
        text_end = _text_end

    class _FakeAnalysis:
        identity = _FakeIdentity()
        frontier = {"reachable_addresses": sorted({r["address"] for r in records})}
        records_by_address = {r["address"]: r for r in records}
        delay_by_owner = _delay_by_owner
        provenance = {}
        projection = {
            "projection_digest": _sha256_bytes(b"synthetic"),
            "provenance": {"title_payload_sha256": _sha256_bytes(_payload)},
        }

    fake = _FakeAnalysis()
    for pc in fake.frontier["reachable_addresses"]:
        fake.provenance[pc] = type("P", (), {"asdict": lambda self, pc=pc: {"guest_pc": f"0x{pc:08x}", "title_payload_sha256": _sha256_bytes(payload)}})()

    ctx = EmissionContext(analysis=fake, run_dir=run_dir)
    ctx.records = _make_semantic_records(fake)

    _write_files(ctx, entry)
    _compile_files(ctx)
    result = _run(ctx.exe_path)

    return {
        "run_dir": str(ctx.run_dir),
        "header_sha256": _sha256_bytes(ctx.h_path.read_bytes()),
        "source_sha256": _sha256_bytes(ctx.c_path.read_bytes()),
        "harness_sha256": _sha256_bytes(ctx.harness_path.read_bytes()),
        "exe_sha256": _sha256_bytes(ctx.exe_path.read_bytes()),
        "so_sha256": _sha256_bytes(ctx.so_path.read_bytes()),
        "runtime_result": result,
    }


def synthesize_decode_record(
    address: int,
    op: str,
    **operands: Any,
) -> dict[str, Any]:
    """Build a P17-02-style decode record for synthetic tests."""
    control_flow = op in CONTROL_OPS
    delay_slot = op in ("beq", "bne", "blez", "bgtz", "bltz", "bgez", "j", "jal", "jr", "jalr")
    link = op in ("jal",) or (op == "jalr" and operands.get("rd", 0) == 31)
    terminator: str | None = None
    if op in ("beq", "bne", "blez", "bgtz", "bltz", "bgez"):
        terminator = "conditional-branch"
    elif op == "j":
        terminator = "jump"
    elif op == "jal":
        terminator = "direct-call"
    elif op == "jr":
        terminator = "return" if operands.get("rs", 0) == 31 else "indirect-jump"
    elif op == "jalr":
        terminator = "indirect-call" if operands.get("rd", 0) == 31 else "indirect-jump"
    return {
        "address": address,
        "word": 0,
        "decode_class": "SUPPORTED",
        "op": op,
        "semantics": "SUPPORTED",
        "operands": dict(operands),
        "reason": None,
        "control_flow": control_flow,
        "terminator": terminator,
        "delay_slot": delay_slot,
        "target": operands.get("target"),
        "link": link,
        "trap": False,
        "exception_transfer": False,
        "reachability": "REACHABLE",
    }
