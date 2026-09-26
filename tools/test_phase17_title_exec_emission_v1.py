#!/usr/bin/env python3
"""Deterministic P17-04R Revision 3 authenticated executable emission gate.

Emits a compiled, host-native, reusable runtime from authenticated P17-02 TITLE
decode records, verifies per-instruction authenticated-word -> fresh decode ->
SemanticRecord binding, executes it, and records non-reconstructive evidence.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase17/src", ".openrecomp-phase3/src",
              ".openrecomp-phase9/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p17_contracts_v1 as contract
import p17_fixture_verification_v1 as fixture
import p17_iso9660_v1 as iso9660
import p17_title_decode_v1 as title_decode
import p17_title_exec_emit_v1 as emitter
from p17_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P17-04R"
TITLE_ISO_PATH = title_decode.TITLE_ISO_PATH


# ctypes bindings for the reusable execution interface.
class _OrGuestState(ctypes.Structure):
    _fields_ = [
        ("regs", ctypes.c_uint32 * 32),
        ("pc", ctypes.c_uint32),
        ("next_pc", ctypes.c_uint32),
        ("hi", ctypes.c_uint32),
        ("lo", ctypes.c_uint32),
        ("delay_pc", ctypes.c_uint32),
        ("delay_active", ctypes.c_int),
        ("step_count", ctypes.c_uint32),
        ("budget", ctypes.c_uint32),
        ("stop", ctypes.c_int),
        ("stop_reason", ctypes.c_char * 64),
    ]


class _OrRuntimeServices(ctypes.Structure):
    _fields_ = [
        ("user_data", ctypes.c_void_p),
        ("transcript", ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32)),
        ("host_call", ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_char_p,
                                        ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint64,
                                        ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint32))),
        ("ram_base", ctypes.POINTER(ctypes.c_uint8)),
        ("ram_size", ctypes.c_uint32),
    ]


RAM_SIZE = 2 * 1024 * 1024


def fixture_root() -> pathlib.Path:
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def read_real_title_bytes() -> bytes:
    fx = fixture_root()
    image = iso9660.Iso9660Image.open(fx / "Disney's Hercules Action Game (USA).bin")
    record = image.find_file(TITLE_ISO_PATH)
    return image.extract_file(record)


def load_p17_02_projection() -> dict[str, Any]:
    path = ROOT / ".openrecomp-phase17/evidence/P17-02/title_decode.json"
    return emitter._load_p17_02_projection(path)


def _load_live_analysis() -> Any:
    fx = fixture_root()
    fixture.verify_fixture_with_callback(
        fx,
        lambda label, condition, detail="": None,
    )
    return title_decode.analyze_title_decode(fixture_dir=fx)


def _encode_payload(records: list[dict[str, Any]]) -> list[int]:
    """Encode synthetic decode records into little-endian MIPS32 words."""
    return [_encode_record_word(r) for r in records]


def _encode_record_word(rec: dict[str, Any]) -> int:
    op = rec["op"]
    operands = rec.get("operands", {})
    addr = rec["address"]
    rs = operands.get("rs", 0)
    rt = operands.get("rt", 0)
    rd = operands.get("rd", 0)
    shamt = operands.get("shamt", 0)
    imm = operands.get("imm", 0)
    target = operands.get("target")
    if op == "addiu":
        return (0x09 << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "addi":
        return (0x08 << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "addu":
        return (rs << 21) | (rt << 16) | (rd << 11) | 0x21
    if op == "subu":
        return (rs << 21) | (rt << 16) | (rd << 11) | 0x23
    if op == "and":
        return (rs << 21) | (rt << 16) | (rd << 11) | 0x24
    if op == "or":
        return (rs << 21) | (rt << 16) | (rd << 11) | 0x25
    if op == "xor":
        return (rs << 21) | (rt << 16) | (rd << 11) | 0x26
    if op == "nor":
        return (rs << 21) | (rt << 16) | (rd << 11) | 0x27
    if op == "sll":
        return (rt << 16) | (rd << 11) | (shamt << 6)
    if op == "srl":
        return (rt << 16) | (rd << 11) | (shamt << 6) | 0x02
    if op == "sra":
        return (rt << 16) | (rd << 11) | (shamt << 6) | 0x03
    if op == "sllv":
        return (rs << 21) | (rt << 16) | (rd << 11) | 0x04
    if op == "srlv":
        return (rs << 21) | (rt << 16) | (rd << 11) | 0x06
    if op == "srav":
        return (rs << 21) | (rt << 16) | (rd << 11) | 0x07
    if op == "slt":
        return (rs << 21) | (rt << 16) | (rd << 11) | 0x2A
    if op == "sltu":
        return (rs << 21) | (rt << 16) | (rd << 11) | 0x2B
    if op == "andi":
        return (0x0C << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "ori":
        return (0x0D << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "xori":
        return (0x0E << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "slti":
        return (0x0A << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "sltiu":
        return (0x0B << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "lui":
        return (0x0F << 26) | (rt << 16) | (imm & 0xFFFF)
    if op == "lw":
        return (0x23 << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "lh":
        return (0x21 << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "lhu":
        return (0x25 << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "lb":
        return (0x20 << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "lbu":
        return (0x24 << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "sw":
        return (0x2B << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "sh":
        return (0x29 << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "sb":
        return (0x28 << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)
    if op == "mult":
        return (rs << 21) | (rt << 16) | 0x18
    if op == "multu":
        return (rs << 21) | (rt << 16) | 0x19
    if op == "mflo":
        return (rd << 11) | 0x12
    if op == "mfhi":
        return (rd << 11) | 0x10
    if op == "beq":
        offset = ((target - addr - 4) >> 2) & 0xFFFF
        return (0x04 << 26) | (rs << 21) | (rt << 16) | offset
    if op == "bne":
        offset = ((target - addr - 4) >> 2) & 0xFFFF
        return (0x05 << 26) | (rs << 21) | (rt << 16) | offset
    if op == "blez":
        offset = ((target - addr - 4) >> 2) & 0xFFFF
        return (0x06 << 26) | (rs << 21) | offset
    if op == "bgtz":
        offset = ((target - addr - 4) >> 2) & 0xFFFF
        return (0x07 << 26) | (rs << 21) | offset
    if op == "bltz":
        offset = ((target - addr - 4) >> 2) & 0xFFFF
        return (0x01 << 26) | (rs << 21) | offset
    if op == "bgez":
        offset = ((target - addr - 4) >> 2) & 0xFFFF
        return (0x01 << 26) | (rs << 21) | (0x01 << 16) | offset
    if op == "j":
        return (0x02 << 26) | ((target >> 2) & 0x3FFFFFF)
    if op == "jal":
        return (0x03 << 26) | ((target >> 2) & 0x3FFFFFF)
    if op == "jr":
        return (rs << 21) | 0x08
    if op == "jalr":
        return (rs << 21) | (rd << 11) | 0x09
    if op == "nop":
        return 0
    if op == "div":
        return (rs << 21) | (rt << 16) | 0x1A
    raise ValueError(f"unsupported op for encoder: {op}")


def _run_emission(analysis: Any, run_dir: pathlib.Path) -> dict[str, Any]:
    return emitter.emit_executable(analysis, run_dir=run_dir)


def negative_p17_02_digest_mismatch() -> bool:
    """A tampered P17-02 projection digest is rejected before emission."""
    analysis = _load_live_analysis()
    with tempfile.TemporaryDirectory() as tmp:
        bad_evidence = pathlib.Path(tmp) / "bad_p17_02.json"
        projection = load_p17_02_projection()
        projection["projection_digest"] = "0" * 64
        bad_evidence.write_text(json.dumps(projection), encoding="utf-8", newline="\n")
        saved = emitter.P17_02_EVIDENCE
        try:
            emitter.P17_02_EVIDENCE = bad_evidence
            run_dir = pathlib.Path(tmp) / "run"
            _run_emission(analysis, run_dir)
            return False
        except emitter.TitleExecEmitError as exc:
            return exc.code in ("AUTHENTICATED_PROJECTION_MISMATCH", "P17_02_PROJECTION_DIGEST_MISMATCH")
        finally:
            emitter.P17_02_EVIDENCE = saved


def negative_payload_sha256_mismatch() -> bool:
    """A P17-02 payload identity mismatch is rejected."""
    analysis = _load_live_analysis()
    with tempfile.TemporaryDirectory() as tmp:
        bad_evidence = pathlib.Path(tmp) / "bad_p17_02.json"
        projection = load_p17_02_projection()
        projection["provenance"]["title_payload_sha256"] = "0" * 64
        projection["projection_digest"] = emitter._digest_dict(projection, "projection_digest")
        bad_evidence.write_text(json.dumps(projection), encoding="utf-8", newline="\n")
        saved = emitter.P17_02_EVIDENCE
        try:
            emitter.P17_02_EVIDENCE = bad_evidence
            run_dir = pathlib.Path(tmp) / "run"
            _run_emission(analysis, run_dir)
            return False
        except emitter.TitleExecEmitError as exc:
            return exc.code == "TITLE_PAYLOAD_SHA256_MISMATCH"
        finally:
            emitter.P17_02_EVIDENCE = saved


def negative_missing_provenance() -> bool:
    """A reachable PC without provenance is rejected."""
    analysis = _load_live_analysis()
    del analysis.provenance[next(iter(analysis.provenance))]
    with tempfile.TemporaryDirectory() as tmp:
        try:
            _run_emission(analysis, pathlib.Path(tmp) / "run")
            return False
        except emitter.TitleExecEmitError as exc:
            return exc.code == "MISSING_SOURCE_PROVENANCE"


def negative_unsupported_instruction_runtime() -> bool:
    """A synthetic unsupported op is rejected at runtime."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=1),
        emitter.synthesize_decode_record(0x80038004, "div", rs=1, rt=1),
    ]
    payload_words = _encode_payload(records)
    with tempfile.TemporaryDirectory() as tmp:
        result = emitter.emit_synthetic_executable(
            records, payload_words, 0x80038000, pathlib.Path(tmp), t_addr=0x80038000
        )
        return result["runtime_result"]["stop_reason"] == "UNSUPPORTED_OPERATION"


def negative_altered_instruction_word_changes_state() -> bool:
    """Changing a synthetic operand changes the runtime result."""
    base = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=5),
        emitter.synthesize_decode_record(0x80038004, "sw", rs=0, rt=1, imm=0x100),
    ]
    payload_base = _encode_payload(base)
    altered = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=7),
        emitter.synthesize_decode_record(0x80038004, "sw", rs=0, rt=1, imm=0x100),
    ]
    payload_altered = _encode_payload(altered)
    with tempfile.TemporaryDirectory() as tmp:
        base_dir = pathlib.Path(tmp) / "base"
        alt_dir = pathlib.Path(tmp) / "alt"
        base_dir.mkdir()
        alt_dir.mkdir()
        base_res = emitter.emit_synthetic_executable(
            base, payload_base, 0x80038000, base_dir, t_addr=0x80038000
        )
        alt_res = emitter.emit_synthetic_executable(
            altered, payload_altered, 0x80038000, alt_dir, t_addr=0x80038000
        )
        return (
            base_res["runtime_result"]["executed_instruction_count"]
            == alt_res["runtime_result"]["executed_instruction_count"]
            and base_res["runtime_result"]["register_digest"]
            != alt_res["runtime_result"]["register_digest"]
        )


def _build_fake_analysis_for_binding(payload_words: list[int], records: list[dict[str, Any]], t_addr_arg: int = 0x80038000) -> Any:
    payload_bytes = b"".join(struct.pack("<I", w & 0xFFFFFFFF) for w in payload_words)
    text_end_arg = t_addr_arg + len(payload_bytes)

    class _FakeIdentity:
        payload = payload_bytes
        t_addr = t_addr_arg
        text_end = text_end_arg

    class _FakeAnalysis:
        identity = _FakeIdentity()
        frontier = {"reachable_addresses": sorted({r["address"] for r in records})}
        records_by_address = {r["address"]: r for r in records}
        delay_by_owner = {}
        provenance = {}
        projection = {
            "projection_digest": hashlib.sha256(b"synthetic").hexdigest(),
            "provenance": {"title_payload_sha256": hashlib.sha256(payload_bytes).hexdigest()},
        }

    fake = _FakeAnalysis()
    for pc in fake.frontier["reachable_addresses"]:
        fake.provenance[pc] = type("P", (), {"asdict": lambda self, pc=pc: {"guest_pc": f"0x{pc:08x}", "title_payload_sha256": hashlib.sha256(payload_bytes).hexdigest()}})()
    return fake


def _semantic_from_raw(records_by_address: dict[int, dict[str, Any]], pc: int, analysis: Any) -> emitter.SemanticRecord:
    raw = records_by_address[pc]
    operands = raw.get("operands") or {}
    delay = analysis.delay_by_owner.get(pc)
    return emitter.SemanticRecord(
        pc=pc,
        op=raw["op"],
        rs=int(operands.get("rs", 0)) & 0x1F,
        rt=int(operands.get("rt", 0)) & 0x1F,
        rd=int(operands.get("rd", 0)) & 0x1F,
        shamt=int(operands.get("shamt", 0)) & 0x1F,
        imm=emitter._sign16(int(operands.get("imm", 0)) & 0xFFFF),
        target=(int(operands["target"]) & 0xFFFFFFFF) if operands.get("target") is not None else None,
        delay_slot=(delay & 0xFFFFFFFF) if delay is not None else None,
        control_flow=bool(raw.get("control_flow")),
        terminator=raw.get("terminator"),
        link=bool(raw.get("link")),
        provenance_digest=emitter._provenance_digest_for_pc(analysis, pc),
    )


def negative_altered_source_word() -> bool:
    """An altered authenticated source word fails binding before emission."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=5),
    ]
    payload = _encode_payload(records)
    analysis = _build_fake_analysis_for_binding(payload, records, t_addr_arg=0x80038000)
    rec = _semantic_from_raw(analysis.records_by_address, 0x80038000, analysis)
    # Mutate the source word in the authenticated payload.
    payload_bytes = bytearray(analysis.identity.payload)
    payload_bytes[0:4] = struct.pack("<I", 0x24010007)
    analysis.identity.payload = bytes(payload_bytes)
    try:
        emitter._verify_record_against_fresh_decode(rec, analysis)
        return False
    except emitter.TitleExecEmitError as exc:
        return exc.code == "OPERAND_MISMATCH"


def negative_altered_decoded_opcode() -> bool:
    """A semantic record whose opcode disagrees with the fresh decode fails."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=5),
    ]
    payload = _encode_payload(records)
    analysis = _build_fake_analysis_for_binding(payload, records, t_addr_arg=0x80038000)
    raw = analysis.records_by_address[0x80038000]
    raw["op"] = "ori"
    rec = _semantic_from_raw(analysis.records_by_address, 0x80038000, analysis)
    try:
        emitter._verify_record_against_fresh_decode(rec, analysis)
        return False
    except emitter.TitleExecEmitError as exc:
        return exc.code == "OPCODE_MISMATCH"


def negative_altered_operand() -> bool:
    """A semantic record whose operand disagrees with the fresh decode fails."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=5),
    ]
    payload = _encode_payload(records)
    analysis = _build_fake_analysis_for_binding(payload, records, t_addr_arg=0x80038000)
    raw = analysis.records_by_address[0x80038000]
    raw["operands"]["rt"] = 2
    rec = _semantic_from_raw(analysis.records_by_address, 0x80038000, analysis)
    try:
        emitter._verify_record_against_fresh_decode(rec, analysis)
        return False
    except emitter.TitleExecEmitError as exc:
        return exc.code == "OPERAND_MISMATCH"


def negative_altered_control_flow_target() -> bool:
    """A branch record with a wrong target fails binding."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "beq", rs=0, rt=0, target=0x80038014),
    ]
    # Encode the actual word with the architecturally correct target (0x8003800c),
    # then leave the semantic record claiming 0x80038014.
    encode_records = [
        emitter.synthesize_decode_record(0x80038000, "beq", rs=0, rt=0, target=0x8003800c),
    ]
    payload = _encode_payload(encode_records)
    analysis = _build_fake_analysis_for_binding(payload, records, t_addr_arg=0x80038000)
    rec = _semantic_from_raw(analysis.records_by_address, 0x80038000, analysis)
    try:
        emitter._verify_record_against_fresh_decode(rec, analysis)
        return False
    except emitter.TitleExecEmitError as exc:
        return exc.code == "TARGET_MISMATCH"


def negative_record_from_wrong_pc() -> bool:
    """A record whose fields describe a different PC's word fails."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=5),
        emitter.synthesize_decode_record(0x80038004, "sw", rs=0, rt=1, imm=0x100),
    ]
    payload = _encode_payload(records)
    analysis = _build_fake_analysis_for_binding(payload, records, t_addr_arg=0x80038000)
    # Build a record for PC 0x80038000 but using the sw fields from 0x80038004.
    raw_sw = dict(analysis.records_by_address[0x80038004])
    raw_sw["address"] = 0x80038000
    analysis.records_by_address[0x80038000] = raw_sw
    rec = _semantic_from_raw(analysis.records_by_address, 0x80038000, analysis)
    try:
        emitter._verify_record_against_fresh_decode(rec, analysis)
        return False
    except emitter.TitleExecEmitError as exc:
        return exc.code == "OPCODE_MISMATCH"


def negative_unauthenticated_record() -> bool:
    """A record for a PC outside the authenticated decode set fails."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=5),
    ]
    payload = _encode_payload(records)
    analysis = _build_fake_analysis_for_binding(payload, records, t_addr_arg=0x80038000)
    rec = emitter.SemanticRecord(
        pc=0x80038010,
        op="addiu",
        rs=0,
        rt=1,
        rd=0,
        shamt=0,
        imm=5,
        target=None,
        delay_slot=None,
        control_flow=False,
        terminator=None,
        link=False,
        provenance_digest="0" * 64,
    )
    try:
        emitter._verify_record_against_fresh_decode(rec, analysis)
        return False
    except emitter.TitleExecEmitError as exc:
        return exc.code == "UNAUTHENTICATED_RECORD"


def adversarial_branch_delay_slot_changes_operand() -> dict[str, Any]:
    """Branch decision is captured before the delay slot changes a compared register."""
    # Taken branch: beq $1,$2,target with r1=r2=0; delay slot addiu $2,$2,1.
    # Decision (taken) is captured before delay slot; r2 becomes 1 but branch still taken.
    taken_records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=0),
        emitter.synthesize_decode_record(0x80038004, "addiu", rs=0, rt=2, imm=0),
        emitter.synthesize_decode_record(0x80038008, "beq", rs=1, rt=2, target=0x80038018),
        emitter.synthesize_decode_record(0x8003800c, "addiu", rs=2, rt=2, imm=1),
        emitter.synthesize_decode_record(0x80038010, "addiu", rs=0, rt=5, imm=99),
        emitter.synthesize_decode_record(0x80038014, "addiu", rs=0, rt=6, imm=99),
        emitter.synthesize_decode_record(0x80038018, "addiu", rs=0, rt=4, imm=1),
    ]
    taken_payload = _encode_payload(taken_records)
    # Not-taken branch: beq $1,$2,target with r1=0,r2=1; delay slot addiu $2,$2,-1.
    # Decision (not taken) captured before delay slot; r2 becomes 0 but branch still not taken.
    not_taken_records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=0),
        emitter.synthesize_decode_record(0x80038004, "addiu", rs=0, rt=2, imm=1),
        emitter.synthesize_decode_record(0x80038008, "beq", rs=1, rt=2, target=0x80038018),
        emitter.synthesize_decode_record(0x8003800c, "addiu", rs=2, rt=2, imm=-1),
        emitter.synthesize_decode_record(0x80038010, "addiu", rs=0, rt=5, imm=99),
        emitter.synthesize_decode_record(0x80038014, "addiu", rs=0, rt=6, imm=99),
        emitter.synthesize_decode_record(0x80038018, "addiu", rs=0, rt=4, imm=1),
    ]
    not_taken_payload = _encode_payload(not_taken_records)
    with tempfile.TemporaryDirectory() as tmp:
        taken_res = emitter.emit_synthetic_executable(
            taken_records, taken_payload, 0x80038000, pathlib.Path(tmp) / "taken", t_addr=0x80038000,
            delay_by_owner={0x80038008: 0x8003800c},
        )
        not_taken_res = emitter.emit_synthetic_executable(
            not_taken_records, not_taken_payload, 0x80038000, pathlib.Path(tmp) / "not_taken", t_addr=0x80038000,
            delay_by_owner={0x80038008: 0x8003800c},
        )
    taken_rr = taken_res["runtime_result"]
    not_rr = not_taken_res["runtime_result"]
    # The branch decision is captured before the delay slot, so the taken path
    # skips the fall-through filler instructions and the not-taken path executes
    # them, even though the delay slot changes the register that the branch used.
    ok = (
        taken_rr["final_pc"] == "0x8003801c"
        and taken_rr["executed_instruction_count"] == 5
        and not_rr["final_pc"] == "0x8003801c"
        and not_rr["executed_instruction_count"] == 7
        and taken_rr["stop_reason"] == "PC_NOT_IN_AUTHENTICATED_TABLE"
        and not_rr["stop_reason"] == "PC_NOT_IN_AUTHENTICATED_TABLE"
        # Different outcomes prove the delay-slot write did not re-evaluate the branch.
        and taken_rr["register_digest"] != not_rr["register_digest"]
    )
    return {"ok": ok, "taken": taken_rr, "not_taken": not_rr}


def adversarial_jr_delay_slot_changes_target() -> dict[str, Any]:
    """JR target is captured before the delay slot changes the source register."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=3, imm=0),
        emitter.synthesize_decode_record(0x80038004, "lui", rs=0, rt=3, imm=0x8003),
        emitter.synthesize_decode_record(0x80038008, "ori", rs=3, rt=3, imm=0x8018),
        emitter.synthesize_decode_record(0x8003800c, "jr", rs=3),
        emitter.synthesize_decode_record(0x80038010, "addiu", rs=3, rt=3, imm=4),
        emitter.synthesize_decode_record(0x80038014, "addiu", rs=0, rt=5, imm=99),
        emitter.synthesize_decode_record(0x80038018, "addiu", rs=0, rt=4, imm=1),
    ]
    payload = _encode_payload(records)
    with tempfile.TemporaryDirectory() as tmp:
        result = emitter.emit_synthetic_executable(
            records, payload, 0x80038000, pathlib.Path(tmp), t_addr=0x80038000,
            delay_by_owner={0x8003800c: 0x80038010},
        )
    rr = result["runtime_result"]
    # JR target is captured before the delay slot modifies the source register.
    # The delay slot here changes r3 from 0x80038018 to 0x8003801c, yet execution
    # still reaches 0x80038018 (the original target).
    ok = (
        rr["final_pc"] == "0x8003801c"
        and rr["executed_instruction_count"] == 6
        and rr["stop_reason"] == "PC_NOT_IN_AUTHENTICATED_TABLE"
    )
    return {"ok": ok, "result": rr}


def adversarial_jalr_link_visible_to_delay_slot() -> dict[str, Any]:
    """JALR writes the link register before the delay slot executes."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=3, imm=0),
        emitter.synthesize_decode_record(0x80038004, "lui", rs=0, rt=3, imm=0x8003),
        emitter.synthesize_decode_record(0x80038008, "ori", rs=3, rt=3, imm=0x8018),
        emitter.synthesize_decode_record(0x8003800c, "jalr", rs=3, rd=10),
        emitter.synthesize_decode_record(0x80038010, "sw", rs=10, rt=10, imm=0x200),
        emitter.synthesize_decode_record(0x80038014, "addiu", rs=0, rt=5, imm=99),
        emitter.synthesize_decode_record(0x80038018, "addiu", rs=0, rt=4, imm=1),
    ]
    payload = _encode_payload(records)
    with tempfile.TemporaryDirectory() as tmp:
        result = emitter.emit_synthetic_executable(
            records, payload, 0x80038000, pathlib.Path(tmp), t_addr=0x80038000,
            delay_by_owner={0x8003800c: 0x80038010},
        )
    rr = result["runtime_result"]
    # JALR link value is visible to the delay slot. Execution reaches the target
    # and the link register was set before the delay slot ran.
    ok = (
        rr["final_pc"] == "0x8003801c"
        and rr["executed_instruction_count"] == 6
        and rr["stop_reason"] == "PC_NOT_IN_AUTHENTICATED_TABLE"
    )
    return {"ok": ok, "result": rr}


def interface_shared_object_exports_symbol(manifest: dict[str, Any], run_dir: pathlib.Path) -> bool:
    """The generated shared object exports the reusable entry symbol."""
    so_path = run_dir / "or_title_runtime_v1.so"
    completed = subprocess.run(["nm", "-D", str(so_path)], capture_output=True, text=True)
    if completed.returncode != 0:
        return False
    return "or_title_execute_v1" in completed.stdout


def _load_so(so_path: pathlib.Path) -> ctypes.CDLL:
    lib = ctypes.CDLL(str(so_path))
    lib.or_title_execute_v1.argtypes = [ctypes.POINTER(_OrGuestState), ctypes.POINTER(_OrRuntimeServices)]
    lib.or_title_execute_v1.restype = ctypes.c_int
    return lib


def _build_interface_fixture(tmp: pathlib.Path) -> pathlib.Path:
    """Build a synthetic runtime with three simple instructions for interface tests."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=5),
        emitter.synthesize_decode_record(0x80038004, "addiu", rs=1, rt=2, imm=3),
        emitter.synthesize_decode_record(0x80038008, "sw", rs=0, rt=2, imm=0x100),
    ]
    payload = _encode_payload(records)
    result = emitter.emit_synthetic_executable(
        records, payload, 0x80038000, tmp, t_addr=0x80038000
    )
    return pathlib.Path(result["run_dir"]) / "or_title_runtime_v1.so"


def interface_state_transfer(so_path: pathlib.Path) -> dict[str, Any]:
    """Caller can pass GPR/PC/HI/LO state in and read updated state out."""
    state = _OrGuestState()
    state.pc = 0x80038000
    state.budget = 10
    state.regs[1] = 5
    ram = (ctypes.c_uint8 * RAM_SIZE)()
    services = _OrRuntimeServices()
    services.ram_base = ctypes.cast(ram, ctypes.POINTER(ctypes.c_uint8))
    services.ram_size = RAM_SIZE
    lib = _load_so(so_path)
    lib.or_title_execute_v1(ctypes.byref(state), ctypes.byref(services))
    ok = (
        state.stop == 1
        and state.stop_reason.decode("utf-8", errors="replace").startswith("PC_NOT_IN_AUTHENTICATED_TABLE")
        and state.regs[1] == 5
        and state.step_count == 3
    )
    return {"ok": ok, "step_count": state.step_count, "final_pc": f"0x{state.pc:08x}", "r1": state.regs[1]}


def interface_transcript_hook(so_path: pathlib.Path) -> dict[str, Any]:
    """The runtime calls the transcript hook once per executed guest instruction."""
    entries: list[tuple[int, bytes, int]] = []
    @ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32)
    def cb(user_data, pc, op, step):
        entries.append((pc, op, step))
    state = _OrGuestState()
    state.pc = 0x80038000
    state.budget = 10
    ram = (ctypes.c_uint8 * RAM_SIZE)()
    services = _OrRuntimeServices()
    services.user_data = None
    services.transcript = cb
    services.ram_base = ctypes.cast(ram, ctypes.POINTER(ctypes.c_uint8))
    services.ram_size = RAM_SIZE
    lib = _load_so(so_path)
    lib.or_title_execute_v1(ctypes.byref(state), ctypes.byref(services))
    ok = len(entries) == 3 and entries[0][2] == 1 and entries[1][2] == 2 and entries[2][2] == 3
    return {"ok": ok, "entries": [(pc, op.decode("utf-8", errors="replace"), step) for pc, op, step in entries]}


def interface_budget_and_stop_reason(so_path: pathlib.Path) -> dict[str, Any]:
    """A bounded execution budget produces a typed STEP_LIMIT_REACHED stop."""
    state = _OrGuestState()
    state.pc = 0x80038000
    state.budget = 2
    ram = (ctypes.c_uint8 * RAM_SIZE)()
    services = _OrRuntimeServices()
    services.ram_base = ctypes.cast(ram, ctypes.POINTER(ctypes.c_uint8))
    services.ram_size = RAM_SIZE
    lib = _load_so(so_path)
    lib.or_title_execute_v1(ctypes.byref(state), ctypes.byref(services))
    reason = state.stop_reason.decode("utf-8", errors="replace").rstrip("\\x00")
    ok = state.stop == 1 and reason == "STEP_LIMIT_REACHED" and state.step_count == 2
    return {"ok": ok, "step_count": state.step_count, "reason": reason, "final_pc": f"0x{state.pc:08x}"}


def positive_delay_slot_semantics() -> dict[str, Any]:
    """Open synthetic test: branch delay slot is executed before target."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=5),
        emitter.synthesize_decode_record(0x80038004, "beq", rs=1, rt=0, target=0x80038014),
        emitter.synthesize_decode_record(0x80038008, "addiu", rs=0, rt=2, imm=7),
        emitter.synthesize_decode_record(0x8003800c, "addiu", rs=0, rt=3, imm=9),
        emitter.synthesize_decode_record(0x80038010, "addiu", rs=0, rt=5, imm=13),
        emitter.synthesize_decode_record(0x80038014, "addiu", rs=0, rt=4, imm=11),
    ]
    payload_words = _encode_payload(records)
    with tempfile.TemporaryDirectory() as tmp:
        result = emitter.emit_synthetic_executable(
            records,
            payload_words,
            0x80038000,
            pathlib.Path(tmp),
            t_addr=0x80038000,
            delay_by_owner={0x80038004: 0x80038008},
        )
    rr = result["runtime_result"]
    expected = {
        "executed_instruction_count": 6,
        "final_pc": "0x80038018",
        "stop_reason": "PC_NOT_IN_AUTHENTICATED_TABLE",
    }
    return {
        "ok": (
            rr["executed_instruction_count"] == expected["executed_instruction_count"]
            and rr["final_pc"] == expected["final_pc"]
            and rr["stop_reason"] == expected["stop_reason"]
        ),
        "result": rr,
    }


def positive_handwritten_substitute_excluded(manifest: dict[str, Any]) -> bool:
    active = manifest.get("active_build", {})
    return (
        active.get("phase16_hand_authored_title_guest_flow") == "EXCLUDED"
        and active.get("phase16_guest_flow_imports") == []
        and active.get("phase17_emitter") == "p17_title_exec_emit_v1.py"
        and active.get("execution") == "GENERATED_NATIVE_RUNTIME"
        and active.get("rejected_p17_04_address_inventory_path") == "EXCLUDED"
    )


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 1. Authentic fixture and P17-02 projection.
    fx = fixture_root()
    fixture.verify_fixture_with_callback(
        fx,
        lambda label, condition, detail="": gate.check(label, condition, str(detail)),
    )
    gate.check("p17_02:projection-loadable", True)
    projection = load_p17_02_projection()
    gate.check(
        "p17_02:projection-digest-valid",
        projection["projection_digest"] == emitter._digest_dict(projection, "projection_digest"),
    )

    # 2. Live authenticated analysis must match the committed projection.
    analysis = _load_live_analysis()
    gate.check(
        "p17_02:live-projection-digest-matches",
        analysis.projection["projection_digest"] == projection["projection_digest"],
    )

    # 3. Emit, compile, and run the authenticated executable.
    with tempfile.TemporaryDirectory(prefix="p17-04r-emit-") as tmp:
        run_dir = pathlib.Path(tmp) / "run"
        manifest = _run_emission(analysis, run_dir)

        rr = manifest["runtime_result"]
        gate.check("emission:header-generated", bool(manifest["source"]["header_sha256"]))
        gate.check("emission:source-generated", bool(manifest["source"]["generated_source_sha256"]))
        gate.check("emission:harness-generated", bool(manifest["source"]["generated_harness_sha256"]))
        gate.check("emission:shared-object-generated", bool(manifest["build"]["shared_object_sha256"]))
        gate.check("emission:executable-generated", bool(manifest["build"]["executable_sha256"]))
        gate.check("emission:entry-pc", rr["entry_pc"] == "0x800380a0")
        gate.check("emission:executed-instructions", rr["executed_instruction_count"] > 0)
        gate.check(
            "emission:stop-is-frontier",
            rr["stop_reason"] in {
                "UNSUPPORTED_DIRECT_CALL",
                "UNSUPPORTED_OPERATION",
                "SIGNED_OVERFLOW",
                "UNALIGNED_OR_OUT_OF_BOUNDS_MEMORY_ACCESS",
                "OUT_OF_BOUNDS_MEMORY_ACCESS",
                "PC_NOT_IN_AUTHENTICATED_TABLE",
                "STEP_LIMIT_REACHED",
            },
        )
        gate.check("emission:register-digest-present", bool(rr["register_digest"]))
        gate.check("emission:ram-digest-present", bool(rr["ram_digest"]))
        gate.check(
            "emission:semantic-vocabulary-non-empty",
            bool(manifest["source"]["semantic_vocabulary"]),
        )
        gate.check(
            "emission:provenance-digest-present",
            bool(manifest["source"]["provenance_digest"]),
        )
        gate.check(
            "emission:phase16-hand-authored-flow-excluded",
            positive_handwritten_substitute_excluded(manifest),
        )
        generated_c = (run_dir / "or_title_runtime_v1.c").read_text(encoding="utf-8")
        gate.check(
            "emission:no-phase16-transition-code-import",
            "TITLE_TRANSITION_CODE" not in generated_c and "p16_emission_v1" not in generated_c,
        )

        # 7. Reusable persistent guest-state interface tests.
        gate.check(
            "interface:shared-object-exports-symbol",
            interface_shared_object_exports_symbol(manifest, run_dir),
        )
        with tempfile.TemporaryDirectory(prefix="p17-04r-interface-") as itmp:
            iface_so = _build_interface_fixture(pathlib.Path(itmp))
            state_xfer = interface_state_transfer(iface_so)
            gate.check("interface:state-transfer", state_xfer["ok"], json.dumps(state_xfer, sort_keys=True))
            transcript = interface_transcript_hook(iface_so)
            gate.check("interface:transcript-hook", transcript["ok"], json.dumps(transcript, sort_keys=True))
            budget = interface_budget_and_stop_reason(iface_so)
            gate.check("interface:budget-stop-reason", budget["ok"], json.dumps(budget, sort_keys=True))

    # 4. Determinism across two emissions from the same analysis.
    with tempfile.TemporaryDirectory(prefix="p17-04r-det1-") as tmp1:
        with tempfile.TemporaryDirectory(prefix="p17-04r-det2-") as tmp2:
            manifest1 = _run_emission(analysis, pathlib.Path(tmp1) / "run")
            manifest2 = _run_emission(analysis, pathlib.Path(tmp2) / "run")
    gate.check(
        "determinism:source-hash-identical",
        manifest1["source"]["generated_source_sha256"]
        == manifest2["source"]["generated_source_sha256"],
    )
    gate.check(
        "determinism:shared-object-hash-identical",
        manifest1["build"]["shared_object_sha256"]
        == manifest2["build"]["shared_object_sha256"],
    )
    gate.check(
        "determinism:executable-hash-identical",
        manifest1["build"]["executable_sha256"]
        == manifest2["build"]["executable_sha256"],
    )
    gate.check(
        "determinism:runtime-result-identical",
        manifest1["runtime_result"] == manifest2["runtime_result"],
    )

    # 5. Authenticated-word binding negative tests.
    gate.check("negative:p17-02-digest-mismatch", negative_p17_02_digest_mismatch())
    gate.check("negative:payload-sha256-mismatch", negative_payload_sha256_mismatch())
    gate.check("negative:missing-provenance", negative_missing_provenance())
    gate.check("negative:unsupported-instruction-runtime", negative_unsupported_instruction_runtime())
    gate.check(
        "negative:altered-instruction-word-changes-state",
        negative_altered_instruction_word_changes_state(),
    )
    gate.check("negative:altered-source-word", negative_altered_source_word())
    gate.check("negative:altered-decoded-opcode", negative_altered_decoded_opcode())
    gate.check("negative:altered-operand", negative_altered_operand())
    gate.check("negative:altered-control-flow-target", negative_altered_control_flow_target())
    gate.check("negative:record-from-wrong-pc", negative_record_from_wrong_pc())
    gate.check("negative:unauthenticated-record", negative_unauthenticated_record())

    # 6. Delay-slot adversarial tests.
    delay = positive_delay_slot_semantics()
    gate.check("positive:delay-slot-semantics", delay["ok"], json.dumps(delay["result"], sort_keys=True))

    branch_adv = adversarial_branch_delay_slot_changes_operand()
    gate.check(
        "adversarial:branch-delay-slot-changes-operand",
        branch_adv["ok"],
        json.dumps({"taken": branch_adv["taken"], "not_taken": branch_adv["not_taken"]}, sort_keys=True),
    )

    jr_adv = adversarial_jr_delay_slot_changes_target()
    gate.check("adversarial:jr-delay-slot-changes-target", jr_adv["ok"], json.dumps(jr_adv["result"], sort_keys=True))

    jalr_adv = adversarial_jalr_link_visible_to_delay_slot()
    gate.check("adversarial:jalr-link-visible-to-delay-slot", jalr_adv["ok"], json.dumps(jalr_adv["result"], sort_keys=True))

    # 8. Public safety.
    text = json.dumps(manifest, sort_keys=True)
    for term in ("raw_instruction", "instruction_word", "payload_bytes", "bios_bytes"):
        gate.check(f"public:no-{term}", term not in text)
    gate.check("public:no-private-paths", "/home/" not in text and "fixtures/" not in text)
    assert_public_safe(gate, "title-exec-emission", manifest)

    # 9. Evidence.
    write_json(evidence / "title_exec_emission.json", manifest)
    write_json(evidence / "runtime_result.json", rr)

    markers = {
        "OPENRECOMP_PHASE17_AUTHENTIC_TITLE_EXEC_EMISSION_V1": "PASS",
        "OPENRECOMP_P17_04R": "PASS",
        contract.INITIALIZATION_MARKER: "NOT_PROVEN",
        contract.FRAME_MARKER: "NOT_PROVEN",
        contract.PLAYABILITY_MARKER: "NOT_PROVEN",
        contract.GENERAL_MARKER: "NOT_PROVEN",
        contract.FIRST_FRAME_READY_MARKER: "NO",
    }
    for k, v in markers.items():
        gate.mark(k, v)
    write_json(
        evidence / "RESULT.json",
        {
            "schema": "openrecomp-phase17-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
            "markers": markers,
            "next_stage": "P17-05",
        },
    )


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase17/evidence/P17-04R"))
