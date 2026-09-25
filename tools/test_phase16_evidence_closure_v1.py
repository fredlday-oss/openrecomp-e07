#!/usr/bin/env python3
"""Deterministic P16-91 evidence-closure gate.

Validates complete Phase-16 evidence artifacts across all required stages,
verifies frozen Phase-15 baseline preservation, checks that no private fixture
bytes are tracked in git, confirms honest non-promotion of reserved markers,
and produces the canonical evidence index.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src", ".openrecomp-phase15/src",
              ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p16_contracts_v1 as contract  # noqa: E402
from p16_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402

STAGE = "P16-91"
EVIDENCE = ROOT / ".openrecomp-phase16/evidence"

REQUIRED_STAGES = (
    "P16-00", "P16-01", "P16-02", "P16-03", "P16-04",
    "P16-05", "P16-06", "P16-07", "P16-08", "P16-90",
)

FORBIDDEN_TRACKED = (".bin", ".cue", "SLUS", "fixtures/psx/hercules")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    index = {}
    for stage_id in REQUIRED_STAGES:
        result_path = EVIDENCE / stage_id / "RESULT.json"
        gate.check(f"record:{stage_id}", result_path.is_file(), str(result_path.name))
        document = json.loads(result_path.read_text(encoding="utf-8"))
        gate.check(f"status:{stage_id}", document.get("status") == "PASS", document.get("status"))
        index[stage_id] = {
            "sha256": sha256(result_path),
            "status": document.get("status"),
            "markers": document.get("markers", {}),
        }
        for artifact in sorted((EVIDENCE / stage_id).glob("*.json")):
            json.loads(artifact.read_text(encoding="utf-8"))

    # Source manifest integrity
    manifest = subprocess.run(
        [sys.executable, ".openrecomp-phase16/src/p16_source_manifest_v1.py"],
        cwd=str(root), capture_output=True, text=True,
    )
    gate.check("source-integrity", manifest.returncode == 0
               and "OPENRECOMP_PHASE16_SOURCE_INTEGRITY=PASS" in manifest.stdout,
               manifest.stdout.strip())

    # Frozen Phase 15 integrity verification
    frozen_p15_int = subprocess.run(
        [sys.executable, ".openrecomp-phase16/src/p16_frozen_phase15_integrity_v1.py"],
        cwd=str(root), capture_output=True, text=True,
    )
    gate.check("frozen:phase15-integrity", frozen_p15_int.returncode == 0
               and "OPENRECOMP_PHASE16_P15_SOURCE_INTEGRITY=PASS" in frozen_p15_int.stdout,
               frozen_p15_int.stdout.strip())

    # Frozen Phase 15 boundary verification
    frozen_p15_bnd = subprocess.run(
        [sys.executable, ".openrecomp-phase16/src/p16_frozen_phase15_boundary_v1.py"],
        cwd=str(root), capture_output=True, text=True,
    )
    gate.check("frozen:phase15-boundary", frozen_p15_bnd.returncode == 0
               and "OPENRECOMP_PHASE16_P15_BOUNDARY_FROZEN=PASS" in frozen_p15_bnd.stdout,
               frozen_p15_bnd.stdout.strip())

    # Forbidden files not tracked in git
    tracked = subprocess.run(["git", "ls-files"], cwd=str(root),
                             capture_output=True, text=True).stdout.splitlines()
    leaked = [name for name in tracked if any(token in name for token in FORBIDDEN_TRACKED)]
    gate.check("private:no-fixture-bytes-tracked", not leaked, ",".join(leaked))

    # Reserved claim markers check across stages
    for stage_id in REQUIRED_STAGES:
        st_markers = index[stage_id].get("markers", {})
        if contract.INITIALIZATION_MARKER in st_markers:
            gate.check(f"{stage_id}:init-not-proven",
                       st_markers[contract.INITIALIZATION_MARKER] == "NOT_PROVEN")
        if contract.FRAME_MARKER in st_markers:
            gate.check(f"{stage_id}:frame-not-proven",
                       st_markers[contract.FRAME_MARKER] == "NOT_PROVEN")
        if contract.FIRST_FRAME_READY_MARKER in st_markers:
            gate.check(f"{stage_id}:first-frame-no",
                       st_markers[contract.FIRST_FRAME_READY_MARKER] == "NO")

    evidence_index_doc = {
        "schema": "openrecomp-phase16-evidence-index-v1",
        "stage": STAGE,
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "required_stages": list(REQUIRED_STAGES),
        "stages": index,
        "phase15_base_commit": contract.PHASE15_BASE_COMMIT,
        "phase14_base_commit": contract.PHASE14_BASE_COMMIT,
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
        "fail_closed_discipline": "STRICT_NO_SUPPRESSION",
    }
    write_json(evidence / "evidence_index.json", evidence_index_doc)
    assert_public_safe(gate, "evidence-index", evidence_index_doc, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase16-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            contract.EVIDENCE_CLOSURE_MARKER: "PASS",
            "P16_91_STAGES_VERIFIED": str(len(REQUIRED_STAGES)),
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
            contract.FIRST_FRAME_READY_MARKER: "NO",
        },
        "next_stage": "P16-99",
        "next_action": "advance to Stage P16-99 final verdict",
    })
    gate.mark(contract.EVIDENCE_CLOSURE_MARKER)
    gate.mark("P16_91_STAGES_VERIFIED", str(len(REQUIRED_STAGES)))
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase16/evidence/P16-91"))
