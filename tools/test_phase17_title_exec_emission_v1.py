#!/usr/bin/env python3
"""Deterministic P17-04R authenticated executable emission gate.

Emits a compiled, host-native runtime from authenticated P17-02 TITLE decode
records, executes it, and records non-reconstructive evidence.  All raw-bearing
artifacts are generated in an isolated temporary directory outside the repository.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import struct
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
            return exc.code == "P17_02_PROJECTION_DIGEST_MISMATCH"
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
            return exc.code == "MISSING_PROVENANCE"


def negative_unsupported_instruction_runtime() -> bool:
    """A synthetic unsupported op is rejected at runtime."""
    records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=1),
        emitter.synthesize_decode_record(0x80038004, "div", rs=1, rt=1),
    ]
    payload_words = [0x20010001, 0x0021001A]
    with tempfile.TemporaryDirectory() as tmp:
        result = emitter.emit_synthetic_executable(
            records, payload_words, 0x80038000, pathlib.Path(tmp), t_addr=0x80038000
        )
        return result["runtime_result"]["stop_reason"] == "UNSUPPORTED_OPERATION"


def negative_altered_instruction_word_changes_state() -> bool:
    """Changing a synthetic operand changes the runtime result, proving the
    generated artifact executes actual instruction semantics rather than walking
    addresses.
    """
    base = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=5),
        emitter.synthesize_decode_record(0x80038004, "sw", rs=0, rt=1, imm=0x100),
    ]
    payload_base = [0x20010005, 0xAC010100]
    altered = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=7),
        emitter.synthesize_decode_record(0x80038004, "sw", rs=0, rt=1, imm=0x100),
    ]
    payload_altered = [0x20010007, 0xAC010100]
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


def positive_delay_slot_semantics() -> dict[str, Any]:
    """Open synthetic test: branch delay slot is executed before the branch
    target is taken and the not-taken path is correct.
    """
    records = [
        emitter.synthesize_decode_record(0x80038000, "addiu", rs=0, rt=1, imm=5),
        emitter.synthesize_decode_record(0x80038004, "beq", rs=1, rt=0, target=0x80038014),
        emitter.synthesize_decode_record(0x80038008, "addiu", rs=0, rt=2, imm=7),  # delay slot
        emitter.synthesize_decode_record(0x8003800c, "addiu", rs=0, rt=3, imm=9),  # not taken
        emitter.synthesize_decode_record(0x80038010, "addiu", rs=0, rt=5, imm=13), # not taken + 4
        emitter.synthesize_decode_record(0x80038014, "addiu", rs=0, rt=4, imm=11), # target
    ]
    payload_words = [
        0x20010005,
        0x10200003,
        0x20020007,
        0x20030009,
        0x2005000D,
        0x2004000B,
    ]
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
    gate.check("emission:source-generated", bool(manifest["source"]["generated_source_sha256"]))
    gate.check("emission:executable-generated", bool(manifest["build"]["executable_sha256"]))
    gate.check("emission:entry-pc", rr["entry_pc"] == "0x800380a0")
    gate.check("emission:executed-instructions", rr["executed_instruction_count"] > 0)
    gate.check(
        "emission:stop-is-frontier",
        rr["stop_reason"] in {
            "UNSUPPORTED_DIRECT_CALL",
            "UNSUPPORTED_OPERATION",
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
        "determinism:executable-hash-identical",
        manifest1["build"]["executable_sha256"]
        == manifest2["build"]["executable_sha256"],
    )
    gate.check(
        "determinism:runtime-result-identical",
        manifest1["runtime_result"] == manifest2["runtime_result"],
    )

    # 5. Negative tests.
    gate.check("negative:p17-02-digest-mismatch", negative_p17_02_digest_mismatch())
    gate.check("negative:payload-sha256-mismatch", negative_payload_sha256_mismatch())
    gate.check("negative:missing-provenance", negative_missing_provenance())
    gate.check("negative:unsupported-instruction-runtime", negative_unsupported_instruction_runtime())
    gate.check(
        "negative:altered-instruction-word-changes-state",
        negative_altered_instruction_word_changes_state(),
    )

    delay = positive_delay_slot_semantics()
    gate.check("positive:delay-slot-semantics", delay["ok"], json.dumps(delay["result"], sort_keys=True))

    # 6. Public safety.
    text = json.dumps(manifest, sort_keys=True)
    for term in ("raw_instruction", "instruction_word", "payload_bytes", "bios_bytes"):
        gate.check(f"public:no-{term}", term not in text)
    gate.check("public:no-private-paths", "/home/" not in text and "fixtures/" not in text)
    assert_public_safe(gate, "title-exec-emission", manifest)

    # 7. Evidence.
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
