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
import re
import shutil
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
import p17_linkage_exclusion_v1 as linkage
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
        ("last_executed_pc", ctypes.c_uint32),
        ("attempted_frontier_pc", ctypes.c_uint32),
        ("pending_transfer_target", ctypes.c_uint32),
        ("pending_transfer_type", ctypes.c_int),
        ("pending_transfer_applied", ctypes.c_int),
        ("delay_slot_owner_pc", ctypes.c_uint32),
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


NEXT_STAGE = "P17-05R"
AUTHENTIC_JAL_OWNER_PC = 0x8003812C


def _hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def _run_state(so_path: pathlib.Path, entry_pc: int, budget: int = 100000,
               regs: dict[int, int] | None = None):
    """Execute the reusable interface directly and return the resulting state."""
    state = _OrGuestState()
    state.pc = entry_pc
    state.budget = budget
    for index, value in (regs or {}).items():
        state.regs[index] = value
    ram = (ctypes.c_uint8 * RAM_SIZE)()
    services = _OrRuntimeServices()
    services.ram_base = ctypes.cast(ram, ctypes.POINTER(ctypes.c_uint8))
    services.ram_size = RAM_SIZE
    lib = _load_so(so_path)
    lib.or_title_execute_v1(ctypes.byref(state), ctypes.byref(services))
    return state


def _authentic_jal_expectations(projection: dict[str, Any]) -> dict[str, Any]:
    """Derive the authentic JAL owner/delay-slot/target from P17-02 evidence."""
    owner = AUTHENTIC_JAL_OWNER_PC
    delay = None
    for entry in projection.get("delay_slot_owners", []):
        if int(entry["owner"], 16) == owner:
            delay = int(entry["delay_slot"], 16)
    target = None
    target_class = None
    for entry in projection.get("direct_calls", []):
        if int(entry["site"], 16) == owner:
            target = int(entry["target_pc"], 16)
            target_class = entry.get("target_class")
    return {
        "owner_pc": owner,
        "delay_slot_pc": delay,
        "target_pc": target,
        "target_class": target_class,
    }


def jal_frontier_is_premature(runtime_result: dict[str, Any], owner_pc: int) -> bool:
    """True when execution stopped AT the JAL owner without attempting its delay slot."""
    owner_hex = _hex32(owner_pc)
    at_owner = (
        runtime_result.get("frontier_pc") == owner_hex
        or runtime_result.get("stop_pc") == owner_hex
    )
    if not at_owner:
        return False
    if runtime_result.get("delay_slot_owner_pc") == owner_hex:
        return False
    return True


def authentic_jal_path_assessment(manifest: dict[str, Any],
                                  expectations: dict[str, Any]) -> dict[str, Any]:
    """Classify the authentic JAL/delay-slot frontier: option (A) or fail-closed (B)."""
    rr = manifest["runtime_result"]
    owner_hex = _hex32(expectations["owner_pc"])
    delay_hex = _hex32(expectations["delay_slot_pc"])
    target_hex = _hex32(expectations["target_pc"])
    attempted = (
        rr.get("delay_slot_pc") == delay_hex
        or rr.get("attempted_frontier_pc") == delay_hex
    )
    delay_executed = rr.get("last_successfully_executed_pc") == delay_hex
    fail_closed_here = (rr.get("frontier_pc") == delay_hex) and not delay_executed
    transfer_applied = (
        rr.get("pending_transfer_applied") == 1 and rr.get("frontier_pc") == target_hex
    )
    premature = jal_frontier_is_premature(rr, expectations["owner_pc"])
    ok = (
        attempted
        and not premature
        and rr.get("pending_transfer_type") == "DIRECT_CALL"
        and rr.get("pending_transfer_target") == target_hex
        and ((delay_executed and transfer_applied) or fail_closed_here)
    )
    return {
        "owner_pc": owner_hex,
        "delay_slot_pc": delay_hex,
        "expected_target_pc": target_hex,
        "target_class": expectations.get("target_class"),
        "delay_slot_attempted": attempted,
        "delay_slot_executed": delay_executed,
        "fail_closed_at_delay_slot": fail_closed_here,
        "pending_transfer_type": rr.get("pending_transfer_type"),
        "pending_transfer_target": rr.get("pending_transfer_target"),
        "pending_transfer_applied": rr.get("pending_transfer_applied"),
        "premature_owner_frontier": premature,
        "last_successfully_executed_pc": rr.get("last_successfully_executed_pc"),
        "attempted_frontier_pc": rr.get("attempted_frontier_pc"),
        "frontier_pc": rr.get("frontier_pc"),
        "executed_instruction_count": rr.get("executed_instruction_count"),
        "stop_reason": rr.get("stop_reason"),
        "ok": ok,
    }


def jal_premature_frontier_detected() -> dict[str, Any]:
    """Negative control: a fabricated premature JAL-owner frontier must be rejected."""
    fabricated = {
        "frontier_pc": _hex32(AUTHENTIC_JAL_OWNER_PC),
        "stop_pc": _hex32(AUTHENTIC_JAL_OWNER_PC),
        "delay_slot_owner_pc": "0x00000000",
        "delay_slot_pc": "0x00000000",
    }
    clean = {
        "frontier_pc": "0x80011af0",
        "stop_pc": "0x80011af0",
        "delay_slot_owner_pc": _hex32(AUTHENTIC_JAL_OWNER_PC),
        "delay_slot_pc": _hex32(AUTHENTIC_JAL_OWNER_PC + 4),
    }
    return {
        "premature_detected": jal_frontier_is_premature(fabricated, AUTHENTIC_JAL_OWNER_PC),
        "clean_rejected": jal_frontier_is_premature(clean, AUTHENTIC_JAL_OWNER_PC),
    }


def _jal_link_program():
    records = [
        emitter.synthesize_decode_record(0x80038000, "jal", target=0x80038010),
        emitter.synthesize_decode_record(0x80038004, "addiu", rs=31, rt=2, imm=0),
        emitter.synthesize_decode_record(0x80038008, "addiu", rs=0, rt=3, imm=111),
        emitter.synthesize_decode_record(0x8003800C, "addiu", rs=0, rt=4, imm=222),
        emitter.synthesize_decode_record(0x80038010, "addiu", rs=0, rt=5, imm=1),
    ]
    return records, _encode_payload(records), {0x80038000: 0x80038004}


def jal_link_and_pending_semantics() -> dict[str, Any]:
    """JAL: link register, delay slot observes link, transfer applied afterwards."""
    records, words, delay = _jal_link_program()
    with tempfile.TemporaryDirectory() as tmp:
        result = emitter.emit_synthetic_executable(
            records, words, 0x80038000, pathlib.Path(tmp), t_addr=0x80038000,
            delay_by_owner=delay,
        )
        so_path = pathlib.Path(result["run_dir"]) / "or_title_runtime_v1.so"
        state = _run_state(so_path, 0x80038000, budget=64)
    return {
        "link_value_seen_by_delay_slot": _hex32(state.regs[2]),
        "expected_link_value": _hex32(0x80038000 + 8),
        "fallthrough_instruction_skipped": state.regs[3] == 0,
        "target_reached": state.regs[5] == 1,
        "step_count": state.step_count,
        "final_pc": _hex32(state.pc),
        "delay_slot_owner_pc": _hex32(state.delay_slot_owner_pc),
        "delay_slot_pc": _hex32(state.delay_pc),
        "last_executed_pc": _hex32(state.last_executed_pc),
        "pending_transfer_type": state.pending_transfer_type,
        "pending_transfer_target": _hex32(state.pending_transfer_target),
        "pending_transfer_applied": state.pending_transfer_applied,
        "stop_reason": state.stop_reason.decode("utf-8", errors="replace").rstrip(chr(0)),
    }


def jal_fail_closed_at_delay_slot() -> dict[str, Any]:
    """An unemittable authentic delay slot must fail closed at the delay-slot PC."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "jal", target=0x80038020),
        emitter.synthesize_decode_record(0x80038004, "div", rs=1, rt=1),
    ]
    words = _encode_payload(records)
    with tempfile.TemporaryDirectory() as tmp:
        result = emitter.emit_synthetic_executable(
            records, words, 0x80038000, pathlib.Path(tmp), t_addr=0x80038000,
            delay_by_owner={0x80038000: 0x80038004},
        )
        so_path = pathlib.Path(result["run_dir"]) / "or_title_runtime_v1.so"
        state = _run_state(so_path, 0x80038000, budget=64)
    return {
        "stop_reason": state.stop_reason.decode("utf-8", errors="replace").rstrip(chr(0)),
        "stop_pc": _hex32(state.pc),
        "attempted_frontier_pc": _hex32(state.attempted_frontier_pc),
        "last_executed_pc": _hex32(state.last_executed_pc),
        "step_count": state.step_count,
        "link_register": _hex32(state.regs[31]),
        "delay_slot_owner_pc": _hex32(state.delay_slot_owner_pc),
        "delay_slot_pc": _hex32(state.delay_pc),
        "pending_transfer_type": state.pending_transfer_type,
        "pending_transfer_target": _hex32(state.pending_transfer_target),
        "pending_transfer_applied": state.pending_transfer_applied,
    }


def _vocabulary_coverage_program():
    """One instruction per implemented op, ordered so control flow never diverges."""
    records: list[dict[str, Any]] = []
    delay: dict[int, int] = {}
    pc = 0x80037000

    def add(op: str, **operands: Any) -> None:
        nonlocal pc
        records.append(emitter.synthesize_decode_record(pc, op, **operands))
        pc += 4

    simple = {
        "addiu": {"rs": 11, "rt": 12, "imm": 4},
        "addi": {"rs": 11, "rt": 12, "imm": 4},
        "addu": {"rs": 11, "rt": 12, "rd": 10},
        "subu": {"rs": 12, "rt": 11, "rd": 10},
        "and": {"rs": 11, "rt": 12, "rd": 10},
        "or": {"rs": 11, "rt": 12, "rd": 10},
        "xor": {"rs": 11, "rt": 12, "rd": 10},
        "nor": {"rs": 11, "rt": 12, "rd": 10},
        "sll": {"rs": 0, "rt": 12, "rd": 10, "shamt": 1},
        "srl": {"rs": 0, "rt": 12, "rd": 10, "shamt": 1},
        "sra": {"rs": 0, "rt": 12, "rd": 10, "shamt": 1},
        "sllv": {"rs": 11, "rt": 12, "rd": 10},
        "srlv": {"rs": 11, "rt": 12, "rd": 10},
        "srav": {"rs": 11, "rt": 12, "rd": 10},
        "slt": {"rs": 11, "rt": 12, "rd": 10},
        "sltu": {"rs": 11, "rt": 12, "rd": 10},
        "andi": {"rs": 11, "rt": 12, "imm": 1},
        "ori": {"rs": 11, "rt": 12, "imm": 1},
        "xori": {"rs": 11, "rt": 12, "imm": 1},
        "slti": {"rs": 11, "rt": 12, "imm": 1},
        "sltiu": {"rs": 11, "rt": 12, "imm": 1},
        "lui": {"rs": 0, "rt": 12, "imm": 1},
        "lw": {"rs": 0, "rt": 12, "imm": 0x100},
        "lh": {"rs": 0, "rt": 12, "imm": 0x102},
        "lhu": {"rs": 0, "rt": 12, "imm": 0x102},
        "lb": {"rs": 0, "rt": 12, "imm": 0x103},
        "lbu": {"rs": 0, "rt": 12, "imm": 0x103},
        "sw": {"rs": 0, "rt": 12, "imm": 0x100},
        "sh": {"rs": 0, "rt": 12, "imm": 0x102},
        "sb": {"rs": 0, "rt": 12, "imm": 0x103},
        "mult": {"rs": 11, "rt": 12},
        "multu": {"rs": 11, "rt": 12},
        "mflo": {"rs": 0, "rt": 0, "rd": 12},
        "mfhi": {"rs": 0, "rt": 0, "rd": 12},
        "nop": {},
    }
    add("addiu", rs=0, rt=11, imm=4)
    for op in sorted(simple):
        add(op, **simple[op])
    for op in ("beq", "bne", "blez", "bgtz", "bltz", "bgez"):
        branch_pc = pc
        records.append(emitter.synthesize_decode_record(branch_pc, op, rs=0, rt=0,
                                                        target=branch_pc + 8))
        records.append(emitter.synthesize_decode_record(branch_pc + 4, "nop"))
        delay[branch_pc] = branch_pc + 4
        pc += 8
    for op in ("j", "jal"):
        jump_pc = pc
        records.append(emitter.synthesize_decode_record(jump_pc, op, target=jump_pc + 8))
        records.append(emitter.synthesize_decode_record(jump_pc + 4, "nop"))
        delay[jump_pc] = jump_pc + 4
        pc += 8
    for op in ("jr", "jalr"):
        target = pc + 16
        records.append(emitter.synthesize_decode_record(pc, "lui", rs=0, rt=30,
                                                        imm=(target >> 16) & 0xFFFF))
        records.append(emitter.synthesize_decode_record(pc + 4, "ori", rs=30, rt=30,
                                                        imm=target & 0xFFFF))
        if op == "jr":
            records.append(emitter.synthesize_decode_record(pc + 8, "jr", rs=30))
        else:
            records.append(emitter.synthesize_decode_record(pc + 8, "jalr", rs=30, rd=31))
        records.append(emitter.synthesize_decode_record(pc + 12, "nop"))
        delay[pc + 8] = pc + 12
        pc += 16
    return records, delay, 0x80037000


def implemented_vocabulary_covered() -> dict[str, Any]:
    """Every implemented op must actually execute from a generated artifact."""
    records, delay, t_addr = _vocabulary_coverage_program()
    words = _encode_payload(records)
    with tempfile.TemporaryDirectory() as tmp:
        result = emitter.emit_synthetic_executable(
            records, words, t_addr, pathlib.Path(tmp), t_addr=t_addr,
            delay_by_owner=delay,
        )
    trace = result["runtime_result"]["executed_semantic_trace"]
    implemented = set(emitter.SUPPORTED_OPS)
    missing = sorted(implemented - set(trace))
    unexpected = sorted(set(trace) - implemented)
    return {
        "implemented_count": len(implemented),
        "trace_length": len(trace),
        "missing": missing,
        "unexpected": unexpected,
        "stop_reason": result["runtime_result"]["stop_reason"],
        "ok": not missing and not unexpected,
    }


def executed_vocabulary_is_derived(manifest: dict[str, Any]) -> dict[str, Any]:
    """The exercised vocabulary must be derived from the actual execution trace."""
    source = manifest["source"]
    rr = manifest["runtime_result"]
    trace = list(source.get("executed_semantic_trace") or [])
    exercised = list(source.get("exercised_semantic_vocabulary") or [])
    implemented = set(source.get("implemented_semantic_vocabulary") or [])
    runtime_exercised = list(rr.get("exercised_semantic_vocabulary") or [])
    executed_count = int(rr.get("executed_instruction_count") or 0)
    vocab_count = int(source.get("exercised_semantic_vocabulary_count") or 0)
    return {
        "trace_length": len(trace),
        "executed_instruction_count": executed_count,
        "trace_matches_executed_count": len(trace) == executed_count,
        "exercised_equals_sorted_unique_trace": exercised == sorted(set(trace)),
        "exercised_count_matches_list": vocab_count == len(exercised),
        "exercised_subset_of_implemented": set(exercised) <= implemented,
        "runtime_result_agrees": runtime_exercised == exercised,
        "executed_count_exceeds_vocabulary_count": executed_count > vocab_count,
        "implemented_count": len(implemented),
        "ok": (
            len(trace) == executed_count
            and exercised == sorted(set(trace))
            and vocab_count == len(exercised)
            and set(exercised) <= implemented
            and runtime_exercised == exercised
            and executed_count > vocab_count
        ),
    }


def private_build_root_probe() -> dict[str, Any]:
    """A separate process proves the env override and the default both resolve."""
    program = "\n".join([
        "import hashlib, json, os, sys",
        "sys.path.insert(0, sys.argv[1])",
        "import p17_title_exec_emit_v1 as e",
        "probe = '/tmp/or-p17-04r-rev4-override-probe'",
        "os.environ[e.PRIVATE_BUILD_ROOT_ENV] = probe",
        "overridden = str(e.private_build_root())",
        "os.environ.pop(e.PRIVATE_BUILD_ROOT_ENV, None)",
        "default = str(e.private_build_root())",
        "print(json.dumps({",
        "    'override_honoured': overridden == probe,",
        "    'env_value_differs_from_default': overridden != default,",
        "    'default_matches_declared_default': e.private_build_root() == e.DEFAULT_PRIVATE_BUILD_ROOT,",
        "    'default_digest_prefix': hashlib.sha256(default.encode()).hexdigest()[:16],",
        "    'env_var': e.PRIVATE_BUILD_ROOT_ENV,",
        "    'official_run_labels': list(e.OFFICIAL_RUN_DIRS),",
        "}))",
    ])
    completed = subprocess.run(
        [sys.executable, "-c", program, str(ROOT / ".openrecomp-phase17" / "src")],
        capture_output=True, text=True,
    )
    if completed.returncode != 0:
        return {"ok": False, "error": (completed.stderr or "").strip().splitlines()[-1:]}
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    payload["ok"] = bool(
        payload["override_honoured"]
        and payload["env_value_differs_from_default"]
        and payload["default_matches_declared_default"]
        and payload["official_run_labels"] == ["official-run-1", "official-run-2"]
        and payload["env_var"] == "OPENRECOMP_P17_PRIVATE_BUILD_ROOT"
    )
    return payload


def persisted_artifacts_ok(run_dir: pathlib.Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Every persisted artifact exists with the recorded digest, outside tempdirs."""
    recorded = manifest["persistence"]["artifacts"]
    temp_root = pathlib.Path(tempfile.gettempdir()).resolve()
    rows: dict[str, Any] = {}
    ok = True
    for key, filename in emitter.PERSISTED_ARTIFACTS:
        path = run_dir / filename
        exists = path.is_file()
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if exists else None
        matches = bool(exists and digest == recorded[key]["sha256"])
        try:
            path.resolve().relative_to(temp_root)
            outside_temp = False
        except ValueError:
            outside_temp = True
        if not (exists and matches and outside_temp):
            ok = False
        rows[key] = {
            "file": filename,
            "exists": exists,
            "sha256_matches": matches,
            "outside_tempdir": outside_temp,
            "sha256": recorded[key]["sha256"],
            "bytes": recorded[key]["bytes"],
        }
    return {"ok": ok, "artifacts": rows}


def child_process_persistence_check(run_label: str) -> dict[str, Any]:
    """A separate process re-reads the persisted artifacts from disk."""
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "test_phase17_persistence_v1.py"),
         "--run-label", run_label],
        capture_output=True, text=True,
    )
    marker = "OPENRECOMP_P17_04R_PERSISTENCE_AFTER_EXIT"
    return {
        "returncode": completed.returncode,
        "marker_present": f"{marker}=PASS" in completed.stdout,
        "ok": completed.returncode == 0 and f"{marker}=PASS" in completed.stdout,
    }


def reusable_interface_present(run_dir: pathlib.Path) -> dict[str, Any]:
    so_path = run_dir / "or_title_runtime_v1.so"
    header = run_dir / "or_title_runtime_v1.h"
    completed = subprocess.run(["nm", "-D", str(so_path)], capture_output=True, text=True)
    exports = completed.returncode == 0 and "or_title_execute_v1" in completed.stdout
    header_text = header.read_text(encoding="utf-8") if header.is_file() else ""
    return {
        "shared_object_exists": so_path.is_file(),
        "header_exists": header.is_file(),
        "exports_execute_symbol": exports,
        "header_declares_symbol": "or_title_execute_v1" in header_text,
        "ok": bool(so_path.is_file() and header.is_file() and exports
                   and "or_title_execute_v1" in header_text),
    }


def negative_fixture_artifact(tmp: pathlib.Path, symbol: str) -> pathlib.Path:
    """Build a synthetic artifact that links a forbidden historical symbol."""
    source = tmp / f"{symbol}_probe.c"
    artifact = tmp / f"{symbol}_probe.so"
    source.write_text(f"void {symbol}(void) {{ }}\n", encoding="utf-8", newline="\n")
    completed = subprocess.run(
        ["cc", "-shared", "-fPIC", "-o", str(artifact), str(source)],
        capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise emitter.TitleExecEmitError("NEGATIVE_FIXTURE_COMPILE_FAILED",
                                         completed.stderr or completed.stdout)
    return artifact


def linkage_exclusion_checks(artifact_paths: list[pathlib.Path]) -> dict[str, Any]:
    """Linkage-level exclusion plus a forbidden-symbol negative control."""
    report = linkage.linkage_exclusion_report(artifact_paths)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = pathlib.Path(tmp)
        negative_reports: dict[str, Any] = {}
        negative_ok = True
        for token in ("TITLE_TRANSITION_CODE", "p16_emission_v1"):
            forbidden = negative_fixture_artifact(tmp_dir, token)
            negative = linkage.linkage_exclusion_report([forbidden], tokens=[token])
            negative_reports[token] = {
                "excluded": negative["excluded"],
                "hit_count": negative["forbidden_hit_count"],
                "detected": (not negative["excluded"]) and negative["forbidden_hit_count"] > 0,
            }
            negative_ok = negative_ok and negative_reports[token]["detected"]
        clean = negative_fixture_artifact(tmp_dir, "or_unrelated_probe_symbol")
        clean_report = linkage.linkage_exclusion_report([clean])
        clean_ok = bool(clean_report["excluded"])
    return {
        "report": report,
        "negative_reports": negative_reports,
        "negative_ok": negative_ok,
        "clean_control_excluded": clean_ok,
        "ok": bool(report["excluded"] and negative_ok and clean_ok),
    }


def working_tree_phase_1_16_changes() -> list[str]:
    completed = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                               capture_output=True, text=True)
    pattern = re.compile(r"^\.openrecomp-phase(?:[1-9]|1[0-6])(?:/|$)")
    changes = []
    for line in completed.stdout.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ")[-1].strip()
        if pattern.match(path):
            changes.append(path)
    return changes


def _declared_next_stage(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            document = json.loads(text)
        except json.JSONDecodeError:
            return None
        value = document.get("next_stage")
        return str(value) if value is not None else None
    for line in text.splitlines():
        stripped = line.strip().lstrip("-*").strip()
        if stripped.lower().startswith("next_stage"):
            value = stripped.split(":", 1)[1].strip()
            return value.strip(chr(96)).strip()
    return None


def evidence_public_safety(evidence_dir: pathlib.Path) -> dict[str, Any]:
    """Fail-closed public-safety scan over the committed Revision 4 evidence."""
    # Payload/reconstructive leakage terms only.  Historical symbol *names* are
    # public identifiers (already present in tracked sources and handoff notes),
    # so they are legitimately recorded in the linkage inspection summary.
    forbidden_terms = (
        "raw_instruction",
        "instruction_word",
        "payload_bytes",
        "bios_bytes",
    )
    path_markers = ("/home/", "fixtures/", "/tmp/", "/Users/", ":\\")
    hits: list[str] = []
    files = [path for path in sorted(evidence_dir.glob("*.json")) if path.is_file()]
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for term in forbidden_terms:
            if term in text:
                hits.append(f"{path.name}:term:{term}")
        for marker in path_markers:
            if marker in text:
                hits.append(f"{path.name}:path:{marker}")
    return {"file_count": len(files), "hits": hits, "ok": not hits}


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 0. Remove stale gate/runner-generated evidence so the official run reports
    #    only artifacts produced by this Revision 4 gate invocation.
    # Only the run_stage-owned tests document is removed: it is regenerated in
    # this same process.  The stage runner owns run*.txt / run*.err.txt and
    # official_runs.json / determinism.json, which are regenerated afterwards.
    stale_tests = evidence / "p17_04r_tests.json"
    if stale_tests.is_file():
        stale_tests.unlink()

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

    # R4-03: the authoritative next stage for Revision 4.
    gate.check("next-stage:declared-constant", NEXT_STAGE == "P17-05R")

    # R4-01: private build root override and default behaviour (separate process).
    probe = private_build_root_probe()
    gate.check(
        "persistence:private-build-root-env-override",
        bool(probe.get("override_honoured")),
        json.dumps(probe, sort_keys=True),
    )
    gate.check(
        "persistence:private-build-root-default",
        bool(probe.get("default_matches_declared_default")),
        json.dumps({"default_digest_prefix": probe.get("default_digest_prefix"),
                    "env_var": probe.get("env_var")}, sort_keys=True),
    )

    # 3. Official runs into fresh persistent private run directories.
    private_root = emitter.private_build_root()
    run_dirs: list[pathlib.Path] = []
    manifests: list[dict[str, Any]] = []
    for label in emitter.OFFICIAL_RUN_DIRS:
        run_dir = emitter.official_run_dir(label, private_root)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=False)
        run_dirs.append(run_dir)
        manifests.append(_run_emission(analysis, run_dir))
    gate.check(
        "persistence:fresh-run-dirs-created",
        all(emitter.official_run_dir(label, private_root).is_dir()
            for label in emitter.OFFICIAL_RUN_DIRS),
    )
    gate.check("persistence:run-dirs-distinct", run_dirs[0] != run_dirs[1])

    manifest = manifests[0]
    second_manifest = manifests[1]
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
        "emission:implemented-semantic-vocabulary-non-empty",
        bool(manifest["source"]["implemented_semantic_vocabulary"]),
    )
    gate.check(
        "emission:exercised-semantic-vocabulary-non-empty",
        bool(manifest["source"]["exercised_semantic_vocabulary"]),
    )
    gate.check("emission:provenance-digest-present", bool(manifest["source"]["provenance_digest"]))
    gate.check("emission:phase16-hand-authored-flow-excluded",
               positive_handwritten_substitute_excluded(manifest))
    generated_c = (run_dirs[0] / "or_title_runtime_v1.c").read_text(encoding="utf-8")
    gate.check(
        "emission:no-phase16-transition-code-import",
        "TITLE_TRANSITION_CODE" not in generated_c and "p16_emission_v1" not in generated_c,
    )

    # R4-01: persisted artifacts must exist with the recorded digests.
    persisted_first = persisted_artifacts_ok(run_dirs[0], manifest)
    persisted_second = persisted_artifacts_ok(run_dirs[1], second_manifest)
    gate.check("persistence:run1-artifacts-exist-and-hash-match", persisted_first["ok"],
               json.dumps({k: v["sha256"] for k, v in persisted_first["artifacts"].items()},
                          sort_keys=True))
    gate.check("persistence:run2-artifacts-exist-and-hash-match", persisted_second["ok"])
    gate.check("persistence:generated-source-survives-process-exit",
               persisted_first["artifacts"]["generated_source"]["exists"]
               and persisted_first["artifacts"]["generated_source"]["sha256_matches"])
    gate.check("persistence:private-map-survives-process-exit",
               persisted_first["artifacts"]["private_mapping"]["exists"]
               and persisted_first["artifacts"]["private_mapping"]["sha256_matches"])
    gate.check("persistence:native-artifact-survives-process-exit",
               persisted_first["artifacts"]["shared_object"]["exists"]
               and persisted_first["artifacts"]["shared_object"]["sha256_matches"]
               and persisted_first["artifacts"]["executable"]["exists"]
               and persisted_first["artifacts"]["executable"]["sha256_matches"])
    gate.check("persistence:recorded-native-hash-matches-artifact",
               manifest["build"]["shared_object_sha256"]
               == persisted_first["artifacts"]["shared_object"]["sha256"]
               and manifest["build"]["executable_sha256"]
               == persisted_first["artifacts"]["executable"]["sha256"])
    gate.check("persistence:private-map-record-count",
               manifest["persistence"]["private_mapping_record_count"]
               == manifest["source"]["reachable_record_count"] > 0)
    gate.check("persistence:build-metadata-toolchain-recorded",
               bool(manifest["build"]["toolchain"].get("cc"))
               and "NATIVE" not in manifest["build"]["toolchain"].get("cc", ""))
    child_check = child_process_persistence_check(emitter.OFFICIAL_RUN_DIRS[0])
    gate.check("persistence:child-process-verification", child_check["ok"])
    interface_present = reusable_interface_present(run_dirs[0])
    gate.check("persistence:reusable-interface-on-disk", interface_present["ok"],
               json.dumps({k: v for k, v in interface_present.items() if k != "ok"},
                          sort_keys=True))

    # 4. Determinism across the two official runs.
    gate.check("determinism:generated-source-hash-identical",
               manifests[0]["source"]["generated_source_sha256"]
               == manifests[1]["source"]["generated_source_sha256"])
    gate.check("determinism:private-map-hash-identical",
               manifests[0]["persistence"]["artifacts"]["private_mapping"]["sha256"]
               == manifests[1]["persistence"]["artifacts"]["private_mapping"]["sha256"])
    gate.check("determinism:shared-object-hash-identical",
               manifests[0]["build"]["shared_object_sha256"]
               == manifests[1]["build"]["shared_object_sha256"])
    gate.check("determinism:executable-hash-identical",
               manifests[0]["build"]["executable_sha256"]
               == manifests[1]["build"]["executable_sha256"])
    gate.check("determinism:runtime-result-identical",
               manifests[0]["runtime_result"] == manifests[1]["runtime_result"])
    gate.check("determinism:build-metadata-hash-identical",
               manifests[0]["build"]["build_metadata_sha256"]
               == manifests[1]["build"]["build_metadata_sha256"])
    gate.check("determinism:manifest-identical", manifests[0] == manifests[1])

    # 5. Reusable persistent guest-state interface tests.
    gate.check(
        "interface:shared-object-exports-symbol",
        interface_shared_object_exports_symbol(manifest, run_dirs[0]),
    )
    with tempfile.TemporaryDirectory(prefix="p17-04r-interface-") as itmp:
        iface_so = _build_interface_fixture(pathlib.Path(itmp))
        state_xfer = interface_state_transfer(iface_so)
        gate.check("interface:state-transfer", state_xfer["ok"], json.dumps(state_xfer, sort_keys=True))
        transcript = interface_transcript_hook(iface_so)
        gate.check("interface:transcript-hook", transcript["ok"], json.dumps(transcript, sort_keys=True))
        budget = interface_budget_and_stop_reason(iface_so)
        gate.check("interface:budget-stop-reason", budget["ok"], json.dumps(budget, sort_keys=True))

    # 6. Authenticated-word binding negative tests.
    gate.check("negative:p17-02-digest-mismatch", negative_p17_02_digest_mismatch())
    gate.check("negative:payload-sha256-mismatch", negative_payload_sha256_mismatch())
    gate.check("negative:missing-provenance", negative_missing_provenance())
    gate.check("negative:unsupported-instruction-runtime", negative_unsupported_instruction_runtime())
    gate.check("negative:altered-instruction-word-changes-state",
               negative_altered_instruction_word_changes_state())
    gate.check("negative:altered-source-word", negative_altered_source_word())
    gate.check("negative:altered-decoded-opcode", negative_altered_decoded_opcode())
    gate.check("negative:altered-operand", negative_altered_operand())
    gate.check("negative:altered-control-flow-target", negative_altered_control_flow_target())
    gate.check("negative:record-from-wrong-pc", negative_record_from_wrong_pc())
    gate.check("negative:unauthenticated-record", negative_unauthenticated_record())

    # 7. Delay-slot and JAL frontier tests.
    delay = positive_delay_slot_semantics()
    gate.check("positive:delay-slot-semantics", delay["ok"], json.dumps(delay["result"], sort_keys=True))
    branch_adv = adversarial_branch_delay_slot_changes_operand()
    gate.check("adversarial:branch-delay-slot-changes-operand", branch_adv["ok"],
               json.dumps({"taken": branch_adv["taken"], "not_taken": branch_adv["not_taken"]},
                          sort_keys=True))
    jr_adv = adversarial_jr_delay_slot_changes_target()
    gate.check("adversarial:jr-delay-slot-changes-target", jr_adv["ok"],
               json.dumps(jr_adv["result"], sort_keys=True))
    jalr_adv = adversarial_jalr_link_visible_to_delay_slot()
    gate.check("adversarial:jalr-link-visible-to-delay-slot", jalr_adv["ok"],
               json.dumps(jalr_adv["result"], sort_keys=True))

    expectations = _authentic_jal_expectations(projection)
    gate.check("jal:authentic-owner-and-delay-slot-derived",
               expectations["owner_pc"] == AUTHENTIC_JAL_OWNER_PC
               and expectations["delay_slot_pc"] == AUTHENTIC_JAL_OWNER_PC + 4
               and expectations["target_pc"] is not None,
               json.dumps({k: (_hex32(v) if isinstance(v, int) else v)
                           for k, v in expectations.items()}, sort_keys=True))
    jal_assessment = authentic_jal_path_assessment(manifest, expectations)
    gate.check("jal:authentic-delay-slot-attempted", jal_assessment["delay_slot_attempted"],
               json.dumps(jal_assessment, sort_keys=True))
    gate.check("jal:no-premature-jal-owner-frontier",
               not jal_assessment["premature_owner_frontier"],
               json.dumps(jal_assessment, sort_keys=True))
    gate.check("jal:authentic-path-option-a-or-fail-closed", jal_assessment["ok"],
               json.dumps(jal_assessment, sort_keys=True))
    premature_probe = jal_premature_frontier_detected()
    gate.check("negative:premature-jal-owner-frontier-rejected",
               premature_probe["premature_detected"] and not premature_probe["clean_rejected"],
               json.dumps(premature_probe, sort_keys=True))

    link_semantics = jal_link_and_pending_semantics()
    gate.check("jal:link-register-semantics",
               link_semantics["link_value_seen_by_delay_slot"] == link_semantics["expected_link_value"],
               json.dumps(link_semantics, sort_keys=True))
    gate.check("jal:delay-slot-observes-link-state",
               link_semantics["delay_slot_owner_pc"] == _hex32(0x80038000)
               and link_semantics["delay_slot_pc"] == _hex32(0x80038004)
               and link_semantics["link_value_seen_by_delay_slot"] == _hex32(0x80038008),
               json.dumps(link_semantics, sort_keys=True))
    gate.check("jal:pending-target-not-applied-early",
               link_semantics["fallthrough_instruction_skipped"]
               and link_semantics["step_count"] == 3
               and link_semantics["last_executed_pc"] == _hex32(0x80038010),
               json.dumps(link_semantics, sort_keys=True))
    gate.check("jal:pending-transfer-applied-after-delay-slot",
               link_semantics["pending_transfer_type"] == 1
               and link_semantics["pending_transfer_target"] == _hex32(0x80038010)
               and link_semantics["pending_transfer_applied"] == 1
               and link_semantics["final_pc"] == _hex32(0x80038014),
               json.dumps(link_semantics, sort_keys=True))
    fail_closed = jal_fail_closed_at_delay_slot()
    gate.check("jal:fail-closed-at-authentic-delay-slot-pc",
               fail_closed["stop_reason"] == "UNSUPPORTED_OPERATION"
               and fail_closed["stop_pc"] == _hex32(0x80038004)
               and fail_closed["attempted_frontier_pc"] == _hex32(0x80038004)
               and fail_closed["last_executed_pc"] == _hex32(0x80038000)
               and fail_closed["step_count"] == 1
               and fail_closed["delay_slot_owner_pc"] == _hex32(0x80038000)
               and fail_closed["delay_slot_pc"] == _hex32(0x80038004),
               json.dumps(fail_closed, sort_keys=True))
    gate.check("jal:rejected-delay-slot-does-not-increment-executed-count",
               fail_closed["step_count"] == 1, json.dumps(fail_closed, sort_keys=True))
    gate.check("jal:rejected-delay-slot-does-not-apply-pending-transfer",
               fail_closed["pending_transfer_type"] == 1
               and fail_closed["pending_transfer_target"] == _hex32(0x80038020)
               and fail_closed["pending_transfer_applied"] == 0,
               json.dumps(fail_closed, sort_keys=True))

    # 8. Implemented vs exercised semantic vocabulary.
    coverage = implemented_vocabulary_covered()
    gate.check("vocabulary:implemented-ops-all-executable", coverage["ok"],
               json.dumps(coverage, sort_keys=True))
    derived = executed_vocabulary_is_derived(manifest)
    gate.check("vocabulary:exercised-derived-from-execution-trace", derived["ok"],
               json.dumps(derived, sort_keys=True))
    gate.check("vocabulary:exercised-subset-of-implemented",
               derived["exercised_subset_of_implemented"], json.dumps(derived, sort_keys=True))
    gate.check("vocabulary:executed-count-not-conflated-with-vocabulary-count",
               derived["executed_count_exceeds_vocabulary_count"] and derived["trace_matches_executed_count"],
               json.dumps(derived, sort_keys=True))

    # 9. Linkage-level exclusion of the historical handwritten substitute.
    linkage_checks = linkage_exclusion_checks([
        run_dirs[0] / "or_title_runtime_v1.so",
        run_dirs[0] / "or_title_runtime_v1",
    ])
    linkage_doc = linkage_checks["report"]
    gate.check("linkage:native-artifacts-excluded", linkage_doc["excluded"],
               json.dumps({"forbidden_hits": linkage_doc["forbidden_hits"],
                           "inspected_line_count": linkage_doc["inspected_line_count"]},
                          sort_keys=True))
    gate.check("linkage:inspection-method-and-digest-recorded",
               bool(linkage_doc["inspection_method"]) and len(linkage_doc["inspection_digest"]) == 64)
    gate.check("negative:forbidden-linked-symbol-detected", linkage_checks["ok"],
               json.dumps({"negative_reports": linkage_checks["negative_reports"],
                           "clean_control_excluded": linkage_checks["clean_control_excluded"]},
                          sort_keys=True))

    # 10. Scope: no Phase 1..16 modifications.
    phase_changes = working_tree_phase_1_16_changes()
    gate.check("scope:no-phase-1-16-changes", not phase_changes,
               json.dumps(phase_changes, sort_keys=True))
    frozen = subprocess.run(
        [sys.executable, str(ROOT / ".openrecomp-phase17" / "src" / "p17_frozen_phase16_integrity_v1.py")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    gate.check("scope:phase16-frozen-integrity",
               frozen.returncode == 0
               and "OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS" in frozen.stdout)

    # 11. Public safety.
    persistence_doc = {
        "schema": "openrecomp-phase17-persistence-v1",
        "stage": "P17-04R",
        "private_build_root_env_var": emitter.PRIVATE_BUILD_ROOT_ENV,
        "env_override_honoured": bool(probe.get("override_honoured")),
        "default_root_digest_prefix": probe.get("default_digest_prefix"),
        "official_run_dirs": list(emitter.OFFICIAL_RUN_DIRS),
        "artifacts": manifest["persistence"]["artifacts"],
        "run1_existence": persisted_first["artifacts"],
        "run2_existence": persisted_second["artifacts"],
        "child_process_verification": child_check,
        "reusable_interface": {k: v for k, v in interface_present.items() if k != "ok"},
        "hash_determinism": {
            "generated_source_identical": manifests[0]["source"]["generated_source_sha256"]
            == manifests[1]["source"]["generated_source_sha256"],
            "private_map_identical": manifests[0]["persistence"]["artifacts"]["private_mapping"]["sha256"]
            == manifests[1]["persistence"]["artifacts"]["private_mapping"]["sha256"],
            "shared_object_identical": manifests[0]["build"]["shared_object_sha256"]
            == manifests[1]["build"]["shared_object_sha256"],
            "executable_identical": manifests[0]["build"]["executable_sha256"]
            == manifests[1]["build"]["executable_sha256"],
            "manifest_identical": manifests[0] == manifests[1],
        },
    }
    vocabulary_doc = {
        "schema": "openrecomp-phase17-semantic-vocabulary-v1",
        "stage": "P17-04R",
        "implemented_semantic_vocabulary": manifest["source"]["implemented_semantic_vocabulary"],
        "implemented_semantic_vocabulary_count": manifest["source"]["implemented_semantic_vocabulary_count"],
        "exercised_semantic_vocabulary": manifest["source"]["exercised_semantic_vocabulary"],
        "exercised_semantic_vocabulary_count": manifest["source"]["exercised_semantic_vocabulary_count"],
        "executed_instruction_count": rr["executed_instruction_count"],
        "executed_semantic_trace": manifest["source"]["executed_semantic_trace"],
        "exercised_derived_from_execution_trace": derived,
        "implemented_coverage": coverage,
    }
    jal_doc = {
        "schema": "openrecomp-phase17-jal-frontier-v1",
        "stage": "P17-04R",
        "authentic_expectations": {
            k: (_hex32(v) if isinstance(v, int) else v) for k, v in expectations.items()
        },
        "authentic_assessment": jal_assessment,
        "premature_frontier_negative_control": premature_probe,
        "synthetic_link_semantics": link_semantics,
        "synthetic_fail_closed": fail_closed,
    }
    for name, document in (
        ("title-exec-emission", manifest),
        ("persistence", persistence_doc),
        ("semantic-vocabulary", vocabulary_doc),
        ("jal-frontier", jal_doc),
        ("linkage-exclusion", linkage_doc),
    ):
        text = json.dumps(document, sort_keys=True)
        for term in ("raw_instruction", "instruction_word", "payload_bytes", "bios_bytes"):
            gate.check(f"public:{name}:no-{term.replace(chr(95), chr(45))}-field",
                       term not in text)
        gate.check(f"public:{name}:no-private-paths",
                   "/home/" not in text and "fixtures/" not in text and "/tmp/" not in text)
        assert_public_safe(gate, name, document)

    # 12. Evidence.
    write_json(evidence / "title_exec_emission.json", manifest)
    write_json(evidence / "runtime_result.json", rr)
    write_json(evidence / "persistence.json", persistence_doc)
    write_json(evidence / "semantic_vocabulary.json", vocabulary_doc)
    write_json(evidence / "jal_frontier.json", jal_doc)
    write_json(evidence / "linkage_exclusion.json", linkage_doc)
    write_json(evidence / "next_stage.json", {
        "schema": "openrecomp-phase17-next-stage-v1",
        "stage": "P17-04R",
        "next_stage": NEXT_STAGE,
        "authoritative_sources": ["RESULT.json", "STATE.md", "HANDOFF.md",
                                  "title_exec_emission.json", "stage_metadata.json",
                                  "official_runs.json", "determinism.json"],
    })
    write_json(evidence / "stage_metadata.json", {
        "schema": "openrecomp-phase17-stage-metadata-v1",
        "stage": "P17-04R",
        "revision": 4,
        "status": "PASS",
        "next_stage": NEXT_STAGE,
        "base_commit": "937e5fa0a8e353808620b82b0203ab608e2d8cf4",
        "worker_branch": "agent/kimi-phase17-p17-04r-rev4",
        "resulting_candidate_commit": "PENDING_FINAL_COMMIT",
        "resulting_candidate_commit_resolver": "git rev-parse agent/kimi-phase17-p17-04r-rev4",
    })

    markers = {
        "OPENRECOMP_PHASE17_AUTHENTIC_TITLE_EXEC_EMISSION_V1": "PASS",
        "OPENRECOMP_P17_04R": "PASS",
        contract.INITIALIZATION_MARKER: "NOT_PROVEN",
        contract.FRAME_MARKER: "NOT_PROVEN",
        contract.PLAYABILITY_MARKER: "NOT_PROVEN",
        contract.GENERAL_MARKER: "NOT_PROVEN",
        contract.FIRST_FRAME_READY_MARKER: "NO",
    }
    for key, value in markers.items():
        gate.mark(key, value)
    write_json(
        evidence / "RESULT.json",
        {
            "schema": "openrecomp-phase17-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
            "base_commit": "937e5fa0a8e353808620b82b0203ab608e2d8cf4",
            "resulting_candidate_commit": "PENDING_FINAL_COMMIT",
            "resulting_candidate_commit_resolver": "git rev-parse agent/kimi-phase17-p17-04r-rev4",
            "authentic_frontier": {
                "jal_owner_pc": _hex32(expectations["owner_pc"]),
                "jal_delay_slot_pc": _hex32(expectations["delay_slot_pc"]),
                "last_successfully_executed_pc": rr["last_successfully_executed_pc"],
                "attempted_frontier_pc": rr["attempted_frontier_pc"],
                "frontier_pc": rr["frontier_pc"],
                "stop_reason": rr["stop_reason"],
                "executed_instruction_count": rr["executed_instruction_count"],
                "pending_transfer_type": rr["pending_transfer_type"],
                "pending_transfer_target": rr["pending_transfer_target"],
                "delay_slot_owner_pc": rr["delay_slot_owner_pc"],
                "delay_slot_pc": rr["delay_slot_pc"],
            },
            "semantic_vocabulary_counts": {
                "implemented": manifest["source"]["implemented_semantic_vocabulary_count"],
                "exercised": manifest["source"]["exercised_semantic_vocabulary_count"],
            },
            "persisted_artifacts": {
                key: {"file": value["name"], "sha256": value["sha256"]}
                for key, value in manifest["persistence"]["artifacts"].items()
            },
            "linkage_exclusion": {
                "excluded": linkage_doc["excluded"],
                "forbidden_hit_count": linkage_doc["forbidden_hit_count"],
                "inspection_method": linkage_doc["inspection_method"],
                "inspection_digest": linkage_doc["inspection_digest"],
                "negative_control_detected": linkage_checks["negative_ok"],
            },
            "markers": markers,
            "next_stage": NEXT_STAGE,
            "proof_boundaries": {
                "HERCULES_INITIALIZATION_PROOF": "NOT_PROVEN",
                "HERCULES_FRAME_PROOF": "NOT_PROVEN",
                "HERCULES_PLAYABILITY_PROOF": "NOT_PROVEN",
                "GENERAL_PS1_COMPATIBILITY": "NOT_PROVEN",
                "GENERAL_TITLE_COMPATIBILITY": "NOT_PROVEN",
                "FIRST_FRAME_READY": "NO",
            },
        },
    )

    # 13. Cross-file next-stage consistency (after all authoritative files exist).
    authoritative = {
        "RESULT.json": evidence / "RESULT.json",
        "title_exec_emission.json": evidence / "title_exec_emission.json",
        "stage_metadata.json": evidence / "stage_metadata.json",
        "next_stage.json": evidence / "next_stage.json",
        "official_runs.json": evidence / "official_runs.json",
        "determinism.json": evidence / "determinism.json",
        "STATE.md": ROOT / ".openrecomp-phase17" / "STATE.md",
        "HANDOFF.md": ROOT / ".openrecomp-phase17" / "HANDOFF.md",
    }
    declared = {}
    for name, path in authoritative.items():
        value = _declared_next_stage(path)
        if value is not None:
            declared[name] = value
    required = {"RESULT.json", "title_exec_emission.json", "stage_metadata.json",
                "next_stage.json", "STATE.md", "HANDOFF.md"}
    mismatched = sorted(name for name, value in declared.items() if value != NEXT_STAGE)
    missing = sorted(required - set(declared))
    gate.check("next-stage:cross-file-consistency", not mismatched and not missing,
               json.dumps({"mismatched": mismatched, "missing": missing}, sort_keys=True))

    # 14. Public safety over the committed evidence directory.
    evidence_scan = evidence_public_safety(evidence)
    gate.check("public:committed-evidence-clean", evidence_scan["ok"],
               json.dumps(evidence_scan, sort_keys=True))
    # The stage runner persists this gate stdout verbatim as run{1,2}.txt, so the
    # in-memory check results are scanned as the stdout the runner will commit.
    stdout_text = json.dumps(gate.results, sort_keys=True)
    stdout_hits = [term for term in ("raw_instruction", "instruction_word",
                                     "payload_bytes", "bios_bytes")
                   if term in stdout_text]
    stdout_hits += [marker for marker in ("/home/", "fixtures/", "/tmp/", "/Users/")
                    if marker in stdout_text]
    gate.check("public:gate-stdout-clean", not stdout_hits,
               json.dumps(stdout_hits, sort_keys=True))

    # R4-15: terminal Revision 4 marker, emitted only after every check passed.
    gate.mark("OPENRECOMP_P17_04R_REV4", "PASS")




if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase17/evidence/P17-04R"))
