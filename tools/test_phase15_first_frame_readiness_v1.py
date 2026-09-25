#!/usr/bin/env python3
"""Deterministic P15-50 first-frame readiness assessment gate.

Assesses whether the execution frontier is ready to advance to first-frame
rendering proof.
Under the fail-closed discipline:
- OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF remains NOT_PROVEN
- Boundary handoff to TITLE overlay at 0x800380a0 requires CD-ROM sector delivery
- GPU command execution and rasterization remain strictly NOT_MODELED
Therefore, FIRST_FRAME_READY evaluates to NO.
Stage P15-50 passes cleanly with marker OPENRECOMP_P15_50=PASS and FIRST_FRAME_READY=NO.
"""

from __future__ import annotations

import json
import pathlib
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
    PLAYABILITY_MARKER,
)
from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402

STAGE = "P15-50"
EVIDENCE_ROOT = ROOT / ".openrecomp-phase15" / "evidence"


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 1. Read predecessor evidence
    init_eval_path = EVIDENCE_ROOT / "P15-11" / "init_proof_evaluation.json"
    gate.check("pred:p15-11-eval-exists", init_eval_path.is_file(), str(init_eval_path))
    init_eval = json.loads(init_eval_path.read_text(encoding="utf-8"))

    init_boundary_path = EVIDENCE_ROOT / "P15-09" / "init_boundary.json"
    gate.check("pred:p15-09-boundary-exists", init_boundary_path.is_file(), str(init_boundary_path))
    init_boundary = json.loads(init_boundary_path.read_text(encoding="utf-8"))

    hardening_path = EVIDENCE_ROOT / "P15-20" / "hardening.json"
    gate.check("pred:p15-20-hardening-exists", hardening_path.is_file(), str(hardening_path))
    hardening = json.loads(hardening_path.read_text(encoding="utf-8"))

    replay_path = EVIDENCE_ROOT / "P15-40" / "replay.json"
    gate.check("pred:p15-40-replay-exists", replay_path.is_file(), str(replay_path))
    replay = json.loads(replay_path.read_text(encoding="utf-8"))

    # 2. Evaluate readiness criteria
    init_proof_verdict = init_eval.get("verdict")
    gate.check("readiness:init-not-proven", init_proof_verdict == "NOT_PROVEN", str(init_proof_verdict))

    boundary_reached = init_boundary.get("boundary_exec_handoff", {}).get("reached", True)
    gate.check("readiness:boundary-not-reached", not boundary_reached, f"reached={boundary_reached}")

    gpu_cmd = hardening.get("surface_invariants", {}).get("gpu_command_execution")
    gate.check("readiness:gpu-cmd-not-modeled", gpu_cmd == "NOT_MODELED", str(gpu_cmd))

    gpu_raster = hardening.get("surface_invariants", {}).get("gpu_rasterization")
    gate.check("readiness:gpu-raster-not-modeled", gpu_raster == "NOT_MODELED", str(gpu_raster))

    replay_identical = replay.get("byte_identical", False)
    gate.check("readiness:replay-deterministic", replay_identical is True, str(replay_identical))

    first_frame_ready = (
        init_proof_verdict == "PROVEN"
        and boundary_reached is True
        and gpu_cmd == "MODELED"
        and gpu_raster == "MODELED"
    )
    gate.check("readiness:first-frame-ready-is-false", not first_frame_ready, "fails closed honestly")

    readiness_doc = {
        "schema": "openrecomp-phase15-first-frame-readiness-v1",
        "stage": STAGE,
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "initialization_proof_status": init_proof_verdict,
        "initialization_boundary_reached": boundary_reached,
        "gpu_command_execution": gpu_cmd,
        "gpu_rasterization": gpu_raster,
        "replay_byte_identical": replay_identical,
        "first_frame_ready": "NO",
        "unsatisfied_prerequisites": [
            "OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF is NOT_PROVEN",
            "A0:0x43 Exec handoff to TITLE entry (0x800380a0) requires CD-ROM sector delivery",
            "GPU command execution and rasterization are NOT_MODELED",
        ],
        "candidate_next_phase": "OPENRECOMP PHASE 16: PS1 CD-ROM SECTOR DELIVERY & GPU PIPELINE",
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "readiness.json", readiness_doc)
    assert_public_safe(gate, "readiness", readiness_doc, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            "OPENRECOMP_P15_50": "PASS",
            "FIRST_FRAME_READY": "NO",
            INITIALIZATION_MARKER: "NOT_PROVEN",
            FRAME_MARKER: "NOT_PROVEN",
            PLAYABILITY_MARKER: "NOT_PROVEN",
            GENERAL_MARKER: "NOT_PROVEN",
        },
        "next_stage": "P15-90",
        "next_action": "advance to Stage P15-90 whole Phase-15 regression suite",
    })
    gate.mark("OPENRECOMP_P15_50")
    gate.mark("FIRST_FRAME_READY", "NO")
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-50"))
