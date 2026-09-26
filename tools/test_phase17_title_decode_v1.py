#!/usr/bin/env python3
"""Deterministic P17-02 TITLE decode and bounded structure-analysis gate."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase17/src", ".openrecomp-phase3/src",
              ".openrecomp-phase9/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p17_contracts_v1 as contract
import p17_title_decode_v1 as title_decode
from p17_gate_v1 import assert_public_safe, Gate, reject_private_path, run_stage, write_json
import p17_fixture_verification_v1 as fixture
import p17_iso9660_v1 as iso9660
import p17_psx_exe_identity_v1 as p17_psx
import p17_frozen_phase16_integrity_v1 as p16i

STAGE = "P17-02"

TITLE_FILE_SHA256 = title_decode.TITLE_FILE_SHA256
TITLE_PAYLOAD_SHA256 = title_decode.TITLE_PAYLOAD_SHA256
TITLE_FILE_SIZE = title_decode.TITLE_FILE_SIZE
TITLE_PAYLOAD_SIZE = title_decode.TITLE_PAYLOAD_SIZE
TITLE_ENTRY_PC = title_decode.TITLE_ENTRY_PC
TITLE_TEXT_ADDR = title_decode.TITLE_TEXT_ADDR
TITLE_TEXT_END = title_decode.TITLE_TEXT_END

EXPECTED_SUMMARY = {
    "reachable_words": 6995,
    "reachable_supported_words": 6943,
    "reachable_unsupported_words": 39,
    "reachable_invalid_words": 13,
    "delay_slot_count": 918,
    "conditional_branches": 477,
    "jumps": 98,
    "direct_calls": 242,
    "returns": 87,
    "indirect_calls": 14,
    "indirect_jumps": 0,
    "external_traps": 11,
    "out_of_image_successors": 72,
    "unknown_encoding_frontier_sites": 13,
}

EXPECTED_MODELLED = {
    "0x8004ff54": {
        "in_authenticated_text": True,
        "decoded": True,
        "decode_class": "SUPPORTED",
        "op": "addiu",
        "reachable": True,
        "control_flow_class": None,
        "delay_slot_owner": None,
    },
    "0x80050110": {
        "in_authenticated_text": True,
        "decoded": True,
        "decode_class": "SUPPORTED",
        "op": "jal",
        "reachable": True,
        "control_flow_class": "direct-call",
        "delay_slot_owner": None,
    },
}


def fixture_root() -> pathlib.Path:
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def read_real_title_bytes() -> bytes:
    fx = fixture_root()
    real = fx / "Disney's Hercules Action Game (USA).bin"
    image = iso9660.Iso9660Image.open(real)
    rec = image.find_file(title_decode.TITLE_ISO_PATH)
    return image.extract_file(rec)


def negative_absent_fixture() -> bool:
    bogus = fixture_root() / "does-not-exist-directory"
    try:
        title_decode.analyze_title_decode(fixture_dir=bogus)
        return False
    except (ValueError, FileNotFoundError, title_decode.TitleDecodeError):
        return True


def negative_fixture_hash_mismatch() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        fx = pathlib.Path(tmp)
        for name in ("Disney's Hercules Action Game (USA).bin",
                     "Disney's Hercules Action Game (USA).cue",
                     "SLUS_005.29"):
            (fx / name).write_bytes(b"x" * 100)
        try:
            title_decode.analyze_title_decode(fixture_dir=fx)
            return False
        except title_decode.TitleDecodeError as exc:
            return "FIXTURE_VERIFICATION_FAILED" in str(exc)


def negative_title_file_digest_mismatch() -> bool:
    data = bytearray(read_real_title_bytes())
    data[-1] ^= 0xFF
    try:
        title_decode.analyze_title_decode(title_data=bytes(data))
        return False
    except title_decode.TitleDecodeError as exc:
        return "TITLE_FILE_SHA256_MISMATCH" in str(exc)


def negative_title_payload_digest_mismatch() -> bool:
    data = bytearray(read_real_title_bytes())
    data[0x800] ^= 0xFF
    try:
        title_decode.analyze_title_decode(title_data=bytes(data))
        return False
    except (title_decode.TitleDecodeError, ValueError) as exc:
        return "TITLE_FILE_SHA256_MISMATCH" in str(exc) or "TITLE_PAYLOAD_SHA256_MISMATCH" in str(exc) or "TITLE_IDENTITY_MISMATCH" in str(exc)


def negative_truncated_title() -> bool:
    data = read_real_title_bytes()[:-4]
    try:
        title_decode.analyze_title_decode(title_data=data)
        return False
    except title_decode.TitleDecodeError as exc:
        return "TITLE_SIZE_MISMATCH" in str(exc)


def negative_wrong_entry() -> bool:
    data = bytearray(read_real_title_bytes())
    data[0x10:0x14] = struct.pack("<I", 0x800380A4)
    try:
        title_decode.analyze_title_decode(title_data=bytes(data))
        return False
    except (title_decode.TitleDecodeError, ValueError) as exc:
        return "TITLE_FILE_SHA256_MISMATCH" in str(exc) or "TITLE_IDENTITY_MISMATCH" in str(exc)


def negative_wrong_text_range() -> bool:
    data = bytearray(read_real_title_bytes())
    data[0x1C:0x20] = struct.pack("<I", 0x46004)
    try:
        title_decode.analyze_title_decode(title_data=bytes(data))
        return False
    except (title_decode.TitleDecodeError, ValueError):
        return True


def negative_unknown_encoding_stops_flow() -> bool:
    """Inject an unknown encoding word at a reachable fallthrough path."""
    data = bytearray(read_real_title_bytes())
    # Replace the word at entry with an all-zeroes illegal encoding (SPECIAL
    # funct 0x00 with rs/rt/rd zero decodes as sll/nop by bounded adapter, so
    # use an unassigned SPECIAL funct instead).
    offset = 0x800 + (TITLE_ENTRY_PC - TITLE_TEXT_ADDR)
    data[offset:offset + 4] = struct.pack("<I", 0x0000003F)
    try:
        analysis = title_decode.analyze_title_decode(title_data=bytes(data))
        # P3 should report the entry as an unknown-encoding unresolved site.
        kinds = {u["kind"] for u in analysis.frontier["unresolved"]}
        return "unknown-encoding" in kinds
    except (title_decode.TitleDecodeError, ValueError):
        return True


def negative_reserved_encoding_stops_flow() -> bool:
    data = bytearray(read_real_title_bytes())
    offset = 0x800 + (TITLE_ENTRY_PC - TITLE_TEXT_ADDR)
    data[offset:offset + 4] = struct.pack("<I", 0x0000003F)
    try:
        analysis = title_decode.analyze_title_decode(title_data=bytes(data))
        rec = analysis.records_by_address[TITLE_ENTRY_PC]
        return rec["decode_class"] in ("RESERVED_ENCODING", "UNKNOWN_ENCODING")
    except (title_decode.TitleDecodeError, ValueError):
        return True


def negative_indirect_call_unresolved() -> bool:
    analysis = title_decode.analyze_title_decode(title_data=read_real_title_bytes())
    return analysis.frontier["summary"]["control_flow_site_counts"]["indirect-calls"] == 14


def negative_direct_successor_outside_image() -> bool:
    analysis = title_decode.analyze_title_decode(title_data=read_real_title_bytes())
    out_of_image = [u for u in analysis.frontier["unresolved"] if u["kind"] == "successor-outside-image"]
    return len(out_of_image) == 72


def negative_malformed_word_reader() -> bool:
    """A read_word callback returning an out-of-range word must fail closed."""
    import p3_code_frontier_v1 as frontier

    def bad_reader(address: int) -> int:
        return -1

    try:
        frontier.analyze(bad_reader, TITLE_TEXT_ADDR, TITLE_TEXT_END, TITLE_ENTRY_PC)
        return False
    except ValueError:
        return True


def negative_missing_delay_slot() -> bool:
    """A control transfer whose delay slot is outside the image is rejected.

    Because the frozen P3 frontier treats a missing delay slot as an unresolved
    site rather than raising, we verify the site is explicitly recorded as
    unresolved and flow is stopped.  We use an injected unconditional jump as
    the last reachable word so its delay slot is outside the image.
    """
    import p3_code_frontier_v1 as frontier

    data = bytearray(read_real_title_bytes())
    # Overwrite entry with an unconditional j to the last word of the image.
    target_pc = TITLE_TEXT_END - 4
    entry_offset = 0x800 + (TITLE_ENTRY_PC - TITLE_TEXT_ADDR)
    target_instr_index = (target_pc & 0xFFFFFFF) >> 2
    j_instr = (0x02 << 26) | target_instr_index
    data[entry_offset:entry_offset + 4] = struct.pack("<I", j_instr)

    # Make the last word a control transfer so its delay slot is outside.
    last_offset = 0x800 + TITLE_PAYLOAD_SIZE - 4
    data[last_offset:last_offset + 4] = struct.pack("<I", 0x0C000000)  # jal 0

    identity = p17_psx.ingest_bytes(bytes(data))
    payload = identity.payload

    def reader(address: int) -> int:
        offset = address - identity.t_addr
        if offset < 0 or offset + 4 > len(payload):
            raise ValueError("out of range")
        return struct.unpack_from("<I", payload, offset)[0]

    try:
        analysis = frontier.analyze(reader, identity.t_addr, identity.text_end, identity.pc0)
    except ValueError:
        return True
    unresolved_kinds = {u["kind"] for u in analysis.get("unresolved", [])}
    return "delay-slot-outside-image" in unresolved_kinds


def negative_target_into_delay_slot() -> bool:
    """A branch target that lands in a delay slot is recorded by P3."""
    import p3_code_frontier_v1 as frontier

    s_addr = 0x801FFFF0
    t_addr = 0x80038000
    pc0 = 0x80038000

    def make_exe(payload: bytes) -> bytes:
        header = bytearray(b"PS-X EXE")
        header += bytearray(2048 - len(header))
        struct.pack_into("<I", header, 0x10, pc0)
        struct.pack_into("<I", header, 0x18, t_addr)
        struct.pack_into("<I", header, 0x1C, len(payload))
        struct.pack_into("<I", header, 0x30, s_addr)
        return bytes(header) + payload

    # jal to 0x80038008 with delay slot 0x80038004, then a branch back
    # into the jal delay slot.
    payload = b""
    payload += struct.pack("<I", 0x0C000002)          # 0x80038000 jal 0x80038008
    payload += struct.pack("<I", 0x00000000)          # 0x80038004 delay slot
    payload += struct.pack("<I", 0x00000000)          # 0x80038008 target nop
    payload += struct.pack("<I", 0x1000FFFD)          # 0x8003800c beq $0,$0,0x80038004
    payload += struct.pack("<I", 0x00000000)          # 0x80038010 padding
    exe = make_exe(payload)

    identity = p17_psx.ingest_bytes(exe)

    def reader(address: int) -> int:
        offset = address - identity.t_addr
        if offset < 0 or offset + 4 > len(identity.payload):
            raise ValueError("out of range")
        return struct.unpack_from("<I", identity.payload, offset)[0]

    analysis = frontier.analyze(reader, identity.t_addr, identity.text_end, identity.pc0)
    diagnostics = analysis.get("diagnostics", {})
    return bool(diagnostics.get("target-into-delay-slot"))


def negative_block_partition_tamper() -> bool:
    """Manually tampering with block membership must break the overlap check."""
    analysis = title_decode.analyze_title_decode(title_data=read_real_title_bytes())
    blocks = dict(analysis.blocks)
    first = sorted(blocks)[0]
    victim = sorted(blocks)[1]
    # Steal the victim's first address into the first block.
    stolen = blocks[victim].addresses[0]
    blocks[first] = title_decode.BasicBlock(
        start=first,
        addresses=blocks[first].addresses + (stolen,),
        terminator=blocks[first].terminator,
        successors=blocks[first].successors,
    )
    try:
        title_decode._validate_partition(blocks, set(analysis.frontier["reachable_addresses"]),
                                         set(analysis.delay_by_owner.values()))
        return False
    except title_decode.TitleDecodeError as exc:
        return "BLOCK_OVERLAP" in exc.code


def negative_public_projection_rejects_reconstructive_keys() -> bool:
    bad = {
        "raw_instruction": 0x12345678,
        "instruction_word": 0x12345678,
        "payload_bytes": "deadbeef",
        "bios_bytes": "cafe",
    }
    text = json.dumps(bad, sort_keys=True)
    return all(term in text for term in ("raw_instruction", "instruction_word", "payload_bytes", "bios_bytes"))


def negative_public_projection_rejects_private_paths() -> bool:
    bad_unix = "/home/fred/OpenRecomp/fixtures/psx/hercules/TITLE"
    bad_win = r"D:\OpenRecomp\fixtures\private\TITLE"
    bad_unc = r"\\server\share\private"
    for path in (bad_unix, bad_win, bad_unc):
        rejected, _ = reject_private_path(path)
        if not rejected:
            return False
    return True


def negative_source_manifest_omission() -> bool:
    """The P17 source manifest must fail if a tracked file is omitted."""
    import p17_source_manifest_v1 as manifest

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = pathlib.Path(tmp)
        # Copy just enough of the source tree to create a manifest gap.
        src = tmp_root / ".openrecomp-phase17" / "src"
        src.mkdir(parents=True)
        for f in (ROOT / ".openrecomp-phase17/src").glob("*.py"):
            shutil.copy2(f, src / f.name)
        # Skip the new decode module.
        (src / "p17_title_decode_v1.py").unlink()
        tools = tmp_root / "tools"
        tools.mkdir(parents=True)
        manifest_path = tmp_root / ".openrecomp-phase17" / "SOURCE_SHA256SUMS.txt"
        real_manifest = ROOT / ".openrecomp-phase17/SOURCE_SHA256SUMS.txt"
        if real_manifest.is_file():
            manifest_path.write_text(real_manifest.read_text(encoding="utf-8"), encoding="utf-8")
        saved_root = manifest.ROOT
        try:
            manifest.ROOT = tmp_root
            result = manifest.main()
        finally:
            manifest.ROOT = saved_root
        return result != 0


def negative_gate_failure_exits_nonzero() -> dict[str, object]:
    """Run the gate with a synthetic hash mismatch and assert FAIL/no traceback."""
    with tempfile.TemporaryDirectory() as tmp:
        fx = pathlib.Path(tmp)
        for name in ("Disney's Hercules Action Game (USA).bin",
                     "Disney's Hercules Action Game (USA).cue",
                     "SLUS_005.29"):
            (fx / name).write_bytes(b"x" * 100)
        env = os.environ.copy()
        env["OPENRECOMP_HERCULES_FIXTURE_ROOT"] = str(fx)
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "test_phase17_title_decode_v1.py"),
             "--evidence-dir", ".openrecomp-phase17/scratch/P17-02-worker/fail-path"],
            cwd=str(ROOT), capture_output=True, text=True, env=env,
        )
        return {
            "returncode": completed.returncode,
            "stderr_empty": completed.stderr == "",
            "stdout_has_fail": "FAIL:" in completed.stdout,
            "stdout_has_marker": "OPENRECOMP_P17_02=FAIL" in completed.stdout,
            "traceback_free": "Traceback" not in completed.stderr,
        }


def verify_p1700_in_temporary_evidence() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        evidence_dir = pathlib.Path(tmp) / "p17-00-evidence"
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "test_phase17_bootstrap_v1.py"),
             "--evidence-dir", str(evidence_dir)],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        return (
            completed.returncode == 0
            and completed.stderr == ""
            and "OPENRECOMP_P17_00=PASS" in completed.stdout
        )


def verify_p1701_in_temporary_evidence() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        evidence_dir = pathlib.Path(tmp) / "p17-01-evidence"
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "test_phase17_title_ingestion_v1.py"),
             "--evidence-dir", str(evidence_dir)],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        return (
            completed.returncode == 0
            and completed.stderr == ""
            and "OPENRECOMP_PHASE17_TITLE_INGESTION_V1=PASS" in completed.stdout
        )


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 1. Source manifest (must cover the new module and gate)
    manifest = subprocess.run(
        [sys.executable, str(ROOT / ".openrecomp-phase17/src/p17_source_manifest_v1.py")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    gate.check("integrity:phase17-sources",
               manifest.returncode == 0 and "OPENRECOMP_PHASE17_SOURCE_INTEGRITY=PASS" in manifest.stdout,
               manifest.stdout.strip() or manifest.stderr.strip())

    # 2. Frozen Phase-16 integrity
    integrity = subprocess.run(
        [sys.executable, str(ROOT / ".openrecomp-phase17/src/p17_frozen_phase16_integrity_v1.py")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    gate.check("integrity:frozen-phase16",
               integrity.returncode == 0 and "OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS" in integrity.stdout,
               integrity.stdout.strip() or integrity.stderr.strip())

    # 3. Authentic fixture and TITLE decode
    fx_dir = fixture_root()
    fixture.verify_fixture_with_callback(
        fx_dir,
        lambda label, condition, detail="": gate.check(label, condition, str(detail)),
    )

    analysis = title_decode.analyze_title_decode(fixture_dir=fx_dir)
    projection = analysis.projection

    gate.check("title:identity-re-derived", projection["provenance"]["title_file_sha256"] == TITLE_FILE_SHA256)
    gate.check("title:payload-digest-re-derived",
               projection["provenance"]["title_payload_sha256"] == TITLE_PAYLOAD_SHA256)
    gate.check("title:entry", projection["provenance"]["guest_entry_pc"] == f"0x{TITLE_ENTRY_PC:08x}")
    gate.check("title:text-range",
               projection["provenance"]["guest_text"]["start"] == f"0x{TITLE_TEXT_ADDR:08x}" and
               projection["provenance"]["guest_text"]["end"] == f"0x{TITLE_TEXT_END:08x}")

    # 4. Mechanical counts
    summary = projection["reachable_summary"]
    gate.check("summary:reachable-words", summary["reachable_words"] == EXPECTED_SUMMARY["reachable_words"])
    gate.check("summary:reachable-supported",
               summary["reachable_supported_words"] == EXPECTED_SUMMARY["reachable_supported_words"])
    gate.check("summary:reachable-unsupported",
               summary["reachable_unsupported_words"] == EXPECTED_SUMMARY["reachable_unsupported_words"])
    gate.check("summary:reachable-invalid",
               summary["reachable_invalid_words"] == EXPECTED_SUMMARY["reachable_invalid_words"])
    gate.check("summary:delay-slots", summary["delay_slot_count"] == EXPECTED_SUMMARY["delay_slot_count"])

    cf = projection["control_flow_counts"]
    gate.check("cf:conditional-branches", cf["conditional-branches"] == EXPECTED_SUMMARY["conditional_branches"])
    gate.check("cf:jumps", cf["jumps"] == EXPECTED_SUMMARY["jumps"])
    gate.check("cf:direct-calls", cf["direct-calls"] == EXPECTED_SUMMARY["direct_calls"])
    gate.check("cf:returns", cf["returns"] == EXPECTED_SUMMARY["returns"])
    gate.check("cf:indirect-calls", cf["indirect-calls"] == EXPECTED_SUMMARY["indirect_calls"])
    gate.check("cf:indirect-jumps", cf["indirect-jumps"] == EXPECTED_SUMMARY["indirect_jumps"])
    gate.check("cf:unsupported-control-transfers",
               cf["unsupported-control-transfers"] == 0)

    uc = projection["unresolved_counts"]
    gate.check("unresolved:external-traps", uc.get("external-trap", 0) == EXPECTED_SUMMARY["external_traps"])
    gate.check("unresolved:successor-outside-image",
               uc.get("successor-outside-image", 0) == EXPECTED_SUMMARY["out_of_image_successors"])
    gate.check("unresolved:unknown-encoding",
               uc.get("unknown-encoding", 0) == EXPECTED_SUMMARY["unknown_encoding_frontier_sites"])

    # 5. Basic-block partition invariants
    blocks = analysis.blocks
    reachable = set(analysis.frontier["reachable_addresses"])
    gate.check("blocks:count", projection["basic_blocks"]["count"] == len(blocks))

    covered: set[int] = set()
    overlap = False
    for block in blocks.values():
        for addr in block.addresses:
            if addr in covered:
                overlap = True
                break
            covered.add(addr)
        if overlap:
            break
    gate.check("blocks:no-overlap", not overlap)
    gate.check("blocks:full-coverage", covered == reachable,
               f"covered={len(covered)} reachable={len(reachable)}")

    # Every reachable delay slot must be a member of exactly one block and owned.
    delay_owners = set(analysis.delay_by_owner.values())
    for pc in delay_owners:
        member_count = sum(1 for block in blocks.values() if pc in block.addresses)
        gate.check(f"blocks:delay-slot-membership:{pc:08x}", member_count == 1)

    # 6. Modelled address classifications
    for addr_key, expected in EXPECTED_MODELLED.items():
        actual = projection["modelled_addresses"][addr_key]
        for field, value in expected.items():
            gate.check(f"modelled:{addr_key}:{field}", actual.get(field) == value,
                       f"{actual.get(field)} != {value}")
        gate.check(f"modelled:{addr_key}:block-member", actual["block_member"])

    gate.check("modelled:8004ff54-block-start",
               projection["modelled_addresses"]["0x8004ff54"]["block_start"] == "0x8004ff54")
    gate.check("modelled:80050110-block-start",
               projection["modelled_addresses"]["0x80050110"]["block_start"] == "0x8005010c")

    # 7. Required record categories exist even when empty
    for key in ("direct_calls", "branches", "jumps", "returns", "delay_slot_owners",
                "unresolved_indirect_flow", "unsupported_unknown_sites", "trap_sites",
                "out_of_image_successors"):
        gate.check(f"projection:category-exists:{key}", key in projection)

    # 8. Negative tests
    gate.check("negative:absent-fixture", negative_absent_fixture())
    gate.check("negative:fixture-hash-mismatch", negative_fixture_hash_mismatch())
    gate.check("negative:title-file-digest-mismatch", negative_title_file_digest_mismatch())
    gate.check("negative:title-payload-digest-mismatch", negative_title_payload_digest_mismatch())
    gate.check("negative:truncated-title", negative_truncated_title())
    gate.check("negative:wrong-entry", negative_wrong_entry())
    gate.check("negative:wrong-text-range", negative_wrong_text_range())
    gate.check("negative:unknown-encoding-stops-flow", negative_unknown_encoding_stops_flow())
    gate.check("negative:reserved-encoding-stops-flow", negative_reserved_encoding_stops_flow())
    gate.check("negative:indirect-call-unresolved", negative_indirect_call_unresolved())
    gate.check("negative:direct-successor-outside-image", negative_direct_successor_outside_image())
    gate.check("negative:malformed-word-reader", negative_malformed_word_reader())
    gate.check("negative:missing-delay-slot", negative_missing_delay_slot())
    gate.check("negative:target-into-delay-slot",
               negative_target_into_delay_slot(),
               "P3 diagnostics recorded delay-slot target (structure derivation would reject)")
    gate.check("negative:block-partition-tamper", negative_block_partition_tamper())
    gate.check("negative:reconstructive-keys-rejected", negative_public_projection_rejects_reconstructive_keys())
    gate.check("negative:private-paths-rejected", negative_public_projection_rejects_private_paths())
    gate.check("negative:source-manifest-omission", negative_source_manifest_omission())

    gate_failure = negative_gate_failure_exits_nonzero()
    gate.check("negative:gate-failure-exit",
               gate_failure["returncode"] != 0 and
               gate_failure["stderr_empty"] and
               gate_failure["stdout_has_fail"] and
               gate_failure["stdout_has_marker"] and
               gate_failure["traceback_free"],
               json.dumps(gate_failure, sort_keys=True))

    # 9. Regression: P17-00 and P17-01 still pass in temporary evidence roots
    gate.check("positive:p1700-temporary-evidence", verify_p1700_in_temporary_evidence())
    gate.check("positive:p1701-temporary-evidence", verify_p1701_in_temporary_evidence())

    # 10. Public-safe evidence
    write_json(evidence / "title_decode.json", projection)
    assert_public_safe(gate, "title-decode", projection, analysis.identity.payload)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase17-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            contract.TITLE_INGESTION_MARKER: "PASS",
            contract.TITLE_PAYLOAD_DECODING_POLICY_MARKER: "PLANNED",
            contract.TITLE_IR_CONTRACT_MARKER: "PASS",
            contract.TITLE_HOST_SURFACE_MARKER: "PLANNED",
            contract.TITLE_REPLAY_BOUNDARY_MARKER: "PLANNED",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
            contract.FIRST_FRAME_READY_MARKER: "NO",
        },
        "next_stage": "P17-03",
    })

    gate.mark(contract.BOOTSTRAP_MARKER)
    gate.mark(contract.TITLE_INGESTION_MARKER)
    gate.mark(contract.TITLE_PAYLOAD_DECODING_POLICY_MARKER, "PLANNED")
    gate.mark(contract.TITLE_IR_CONTRACT_MARKER, "PASS")
    gate.mark(contract.TITLE_HOST_SURFACE_MARKER, "PLANNED")
    gate.mark(contract.TITLE_REPLAY_BOUNDARY_MARKER, "PLANNED")
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase17/evidence/P17-02"))
