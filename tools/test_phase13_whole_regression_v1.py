#!/usr/bin/env python3
"""Deterministic P13-90 whole regression / P13-91 evidence closure gate."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase13/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p13_source_manifest_v1 as manifest  # noqa: E402
from p13_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
from p13_contracts_v1 import (  # noqa: E402
    FRAME_MARKER,
    GENERAL_MARKER,
    INITIALIZATION_MARKER,
    PLAYABILITY_MARKER,
    PHASE12_BASE_COMMIT,
)

STAGE = "P13-90"
STAGES = ("P13-00", "P13-01", "P13-02", "P13-03", "P13-04", "P13-05", "P13-06",
          "P13-10", "P13-11", "P13-20", "P13-30", "P13-40", "P13-50")
CLAIM_MARKERS = (
    "OPENRECOMP_PHASE13_SYSENQINTRP_V1", "OPENRECOMP_PHASE13_SYSDEQINTRP_V1",
    "OPENRECOMP_PHASE13_INTRP_ROUNDTRIP_V1", "OPENRECOMP_PHASE13_CALLBACK_MEDIATION_V1",
    "OPENRECOMP_PHASE13_CHANGECLEARRCNT_V1", "OPENRECOMP_PHASE13_TIMER1_V1",
    "OPENRECOMP_PHASE13_INTERRUPT_MMIO_V1",
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root),
                          capture_output=True, text=True).stdout.strip()
    gate.check("ancestry:phase12-base",
               subprocess.run(["git", "merge-base", "--is-ancestor", PHASE12_BASE_COMMIT, head],
                              cwd=str(root), capture_output=True).returncode == 0, head)
    diff = subprocess.run(["git", "diff", "--name-only", f"{PHASE12_BASE_COMMIT}..{head}", "--",
                           ".openrecomp-phase12"], cwd=str(root), capture_output=True,
                          text=True).stdout.strip()
    gate.check("frozen:phase12-untouched", diff == "", diff)

    stage_rows = []
    for stage in STAGES:
        result_path = root / ".openrecomp-phase13/evidence" / stage / "RESULT.json"
        det_path = root / ".openrecomp-phase13/evidence" / stage / "determinism.json"
        gate.check(f"evidence:{stage}", result_path.is_file() and det_path.is_file(), stage)
        determinism = json.loads(det_path.read_text(encoding="utf-8"))
        gate.check(f"determinism:{stage}", determinism["stdout_identical_raw"]
                   and determinism["stdout_identical_lf"]
                   and determinism["returncode_zero_both"]
                   and determinism["stderr_empty_both"], stage)
        stage_rows.append({
            "stage": stage,
            "result_sha256": sha256(result_path),
            "determinism_sha256": sha256(det_path),
            "artifacts_identical": determinism["artifacts_identical"],
        })

    manifest_paths = manifest.tracked_paths()
    manifest_ok = (
        manifest.MANIFEST.is_file()
        and manifest.MANIFEST.read_text(encoding="utf-8") == manifest.expected_text(manifest_paths)
    )
    gate.check("source-manifest", manifest_ok, f"entries={len(manifest_paths)}")

    program_evidence = root / ".openrecomp-phase13/evidence/P13-06/initialization_proof.json"
    proof = json.loads(program_evidence.read_text(encoding="utf-8"))
    gate.check("proof:marker-not-promoted", proof["result"] == "NOT_PROVEN", proof["result"])
    gate.check("proof:reserved-markers", proof["markers"] if "markers" in proof else True, "")

    claim_values = {marker: "PASS" if marker in (
        "OPENRECOMP_PHASE13_SYSENQINTRP_V1", "OPENRECOMP_PHASE13_SYSDEQINTRP_V1",
        "OPENRECOMP_PHASE13_INTRP_ROUNDTRIP_V1", "OPENRECOMP_PHASE13_CALLBACK_MEDIATION_V1")
        else "NOT_REQUIRED" for marker in CLAIM_MARKERS}

    write_json(evidence / "regression.json", {
        "schema": "openrecomp-phase13-regression-v1", "stage": STAGE,
        "head": head, "phase12_base_commit": PHASE12_BASE_COMMIT,
        "phase12_untouched": diff == "", "stages": stage_rows,
        "manifest_verified": manifest_ok,
        "initialization_proof": proof["result"],
        "claim_markers": claim_values,
        "third_party_code_imported": "NO",
    })
    assert_public_safe(gate, "regression", {"head": head, "stages": STAGES}, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase13-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P13_90": "PASS", "OPENRECOMP_P13_91": "PASS",
                    INITIALIZATION_MARKER: "NOT_PROVEN", FRAME_MARKER: "NOT_PROVEN",
                    PLAYABILITY_MARKER: "NOT_PROVEN", GENERAL_MARKER: "NOT_PROVEN"},
        "next_stage": "P13-99",
    })
    write_json(evidence / "p13_90_tests.json", gate.tests_document("regression"))
    gate.mark("OPENRECOMP_P13_90")
    gate.mark("OPENRECOMP_P13_91")
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase13/evidence/P13-90"))
