#!/usr/bin/env python3
"""Deterministic P15-91 evidence-closure gate.

Validates complete Phase-15 evidence artifacts across all required stages,
verifies frozen Phase-14 baseline preservation, checks that no private fixture
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
              ".openrecomp-phase14/src", ".openrecomp-phase15/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p15_contracts_v1 import (  # noqa: E402
    FRAME_MARKER,
    GENERAL_MARKER,
    INITIALIZATION_MARKER,
    PHASE14_BASE_COMMIT,
    PLAYABILITY_MARKER,
)
from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402

STAGE = "P15-91"
EVIDENCE = ROOT / ".openrecomp-phase15/evidence"

REQUIRED_STAGES = (
    "P15-00", "P15-01", "P15-02", "P15-03", "P15-04",
    "P15-05", "P15-06", "P15-07", "P15-08", "P15-09",
    "P15-10", "P15-11", "P15-20", "P15-30", "P15-40",
    "P15-50", "P15-90",
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
        [sys.executable, ".openrecomp-phase15/src/p15_source_manifest_v1.py"],
        cwd=str(root), capture_output=True, text=True,
    )
    gate.check("source-integrity", manifest.returncode == 0
               and "OPENRECOMP_PHASE15_SOURCE_INTEGRITY=PASS" in manifest.stdout,
               manifest.stdout.strip())

    # Frozen Phase 14 boundary verification
    frozen_p14 = subprocess.run(
        [sys.executable, ".openrecomp-phase15/src/p15_frozen_phase14_boundary_v1.py"],
        cwd=str(root), capture_output=True, text=True,
    )
    gate.check("frozen:phase14-boundary", frozen_p14.returncode == 0
               and "OPENRECOMP_PHASE15_P14_BOUNDARY_FROZEN=PASS" in frozen_p14.stdout,
               frozen_p14.stdout.strip())

    # Forbidden files not tracked in git
    tracked = subprocess.run(["git", "ls-files"], cwd=str(root),
                             capture_output=True, text=True).stdout.splitlines()
    leaked = [name for name in tracked if any(token in name for token in FORBIDDEN_TRACKED)]
    gate.check("private:no-fixture-bytes-tracked", not leaked, ",".join(leaked))

    # Proof evaluation check
    proof_doc = json.loads((EVIDENCE / "P15-11" / "init_proof_evaluation.json").read_text(encoding="utf-8"))
    gate.check("proof:marker-matches-evidence",
               proof_doc["verdict"] == "NOT_PROVEN"
               and index["P15-11"]["markers"].get(INITIALIZATION_MARKER) == "NOT_PROVEN")

    # Readiness evaluation check
    readiness_doc = json.loads((EVIDENCE / "P15-50" / "readiness.json").read_text(encoding="utf-8"))
    gate.check("readiness:marker-matches-evidence",
               readiness_doc["first_frame_ready"] == "NO"
               and index["P15-50"]["markers"].get("FIRST_FRAME_READY") == "NO")

    # Reserved proof markers honesty
    gate.check("reserved:frame-playability-general",
               index["P15-00"]["markers"].get(FRAME_MARKER) == "NOT_PROVEN"
               and index["P15-00"]["markers"].get(PLAYABILITY_MARKER) == "NOT_PROVEN"
               and index["P15-00"]["markers"].get(GENERAL_MARKER) == "NOT_PROVEN")

    closure_doc = {
        "schema": "openrecomp-phase15-evidence-index-v1",
        "stage": STAGE,
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "stages": index,
        "source_integrity": "PASS",
        "phase14_frozen_preserved": "YES",
        "phase14_base_commit": PHASE14_BASE_COMMIT,
        "private_fixture_bytes_tracked": "NO",
        "third_party_code_imported": "NO",
        "fail_closed_discipline": "STRICT_NO_SUPPRESSION",
    }
    write_json(evidence / "evidence_index.json", closure_doc)
    assert_public_safe(gate, "evidence_index", closure_doc, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            "OPENRECOMP_P15_91": "PASS",
            INITIALIZATION_MARKER: "NOT_PROVEN",
            FRAME_MARKER: "NOT_PROVEN",
            PLAYABILITY_MARKER: "NOT_PROVEN",
            GENERAL_MARKER: "NOT_PROVEN",
        },
        "next_stage": "P15-99",
        "next_action": "advance to Stage P15-99 final Phase-15 verdict",
    })
    gate.mark("OPENRECOMP_P15_91")
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-91"))
