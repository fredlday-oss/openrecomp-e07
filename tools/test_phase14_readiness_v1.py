#!/usr/bin/env python3
"""Deterministic P14-50 post-initialization / next-phase readiness assessment."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase14/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p14_gate_v1 import run_stage, write_json  # noqa: E402
from p14_contracts_v1 import FRAME_MARKER, GENERAL_MARKER, INITIALIZATION_MARKER, PLAYABILITY_MARKER  # noqa: E402

STAGE = "P14-50"

EVIDENCE_DIR = ROOT / ".openrecomp-phase14/evidence"


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    proof_path = EVIDENCE_DIR / "P14-05" / "initialization_proof.json"
    gate.check("evidence:initialization-proof", proof_path.is_file(), str(proof_path.name))
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    gate.check("proof:not-proven", proof["result"] == "NOT_PROVEN", proof["result"])

    frontier = proof["current_frontier"]
    next_ready = proof["result"] == "PROVEN"
    document = {
        "schema": "openrecomp-phase14-readiness-v1", "stage": STAGE,
        "initialization_proof": proof["result"],
        "initialization_boundary": "REACHED" if proof["predicates"]["INIT-BOUNDARY"] else "NOT_REACHED",
        "initialization_no_fail_closed": "TRUE" if proof["predicates"]["INIT-NO-FAIL-CLOSED"] else "FALSE",
        "next_subsystem": "interrupt MMIO (I_STAT/I_MASK) and root-counter / GPU-status wait",
        "next_frontier": {
            "device_registers": frontier.get("device_register_hits"),
            "memory_denials": frontier.get("memory_denials"),
            "claimed_exec_boundary_reached": False,
        },
        "next_phase_ready": "YES" if next_ready else "NO",
        "candidate_next_phase": "PS1 HERCULES FIRST-FRAME PROOF" if next_ready
                                else "NOT_READY_WAIT_INTERRUPT_MMIO_AND_ROOT_COUNTER",
        "banked_reconnaissance": [
            "clearimage-gpustat-packet-v1",
            "title-cd-sector-delivery-v1",
            "post-timer-first-frame-bridge-v1",
            "dma2-madr-origin-v1",
            "drawotag-linked-list-v1",
            "ot-population-v1",
            "texture-provenance-v1",
            "gte-geometry-v1",
        ],
        "banked_recon_used_as_proof": False,
        "note": "first-frame graphics/CD scope is NOT authorized by Phase 14; the banked "
                "reconnaissance is recorded, not promoted.",
    }
    write_json(evidence / "readiness.json", document)
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase14-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P14_50": "PASS", "OPENRECOMP_PHASE14_NEXT_PHASE_READY": "NO",
                    INITIALIZATION_MARKER: "NOT_PROVEN", FRAME_MARKER: "NOT_PROVEN",
                    PLAYABILITY_MARKER: "NOT_PROVEN", GENERAL_MARKER: "NOT_PROVEN"},
        "next_stage": "P14-90",
    })
    write_json(evidence / "p14_50_tests.json", gate.tests_document("readiness"))
    gate.mark("OPENRECOMP_P14_50")
    gate.mark("OPENRECOMP_PHASE14_NEXT_PHASE_READY", "NO")
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase14/evidence/P14-50"))
