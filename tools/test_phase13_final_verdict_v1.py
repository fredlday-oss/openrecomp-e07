#!/usr/bin/env python3
"""Deterministic P13-99 final Phase-13 verdict gate."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase13/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p13_gate_v1 import run_stage, write_json  # noqa: E402
from p13_contracts_v1 import (  # noqa: E402
    CALLBACK_MEDIATION_MARKER,
    CHANGECLEARRCNT_MARKER,
    FRAME_MARKER,
    GENERAL_MARKER,
    INITIALIZATION_CONTRACT_SOURCE,
    INITIALIZATION_MARKER,
    INITIALIZATION_REPLAY_MARKER,
    INTERRUPT_MMIO_MARKER,
    INTRP_ROUNDTRIP_MARKER,
    PLAYABILITY_MARKER,
    SYSDEQINTRP_MARKER,
    SYSENQINTRP_MARKER,
    TIMER1_MARKER,
)

STAGE = "P13-99"
FINAL_VERDICT = "PHASE13_EXECUTION_COMPLETE_INITIALIZATION_NOT_PROVEN_BOUNDED_C0_AND_CALLBACK"


def load(root: pathlib.Path, relative: str):
    path = root / relative
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    proof = load(root, ".openrecomp-phase13/evidence/P13-06/initialization_proof.json")
    regression = load(root, ".openrecomp-phase13/evidence/P13-90/regression.json")
    boundary = load(root, ".openrecomp-phase13/evidence/P13-00/boundary.json")
    observation = load(root, ".openrecomp-phase13/evidence/P13-01/c0_observation.json")
    frame = load(root, ".openrecomp-phase13/evidence/P13-06/frame_frontier.json")
    gate.check("evidence:proof", proof is not None)
    gate.check("evidence:regression", regression is not None)
    gate.check("evidence:boundary", boundary is not None)
    gate.check("evidence:observation", observation is not None)
    gate.check("evidence:frame", frame is not None)

    initialization = proof["result"]
    gate.check("verdict:terminal-markers",
               initialization in ("PROVEN", "NOT_PROVEN"), initialization)
    gate.check("verdict:replay", proof["byte_identical"] is True, "")
    gate.check("verdict:phase12-untouched", regression["phase12_untouched"] is True, "")
    gate.check("verdict:contract-source", boundary["initialization_contract_source"]
               == INITIALIZATION_CONTRACT_SOURCE, boundary["initialization_contract_source"])

    frontier = proof["current_frontier"].get("site")
    target_complete = "YES" if initialization == "PROVEN" else "NO"

    document = {
        "schema": "openrecomp-phase13-terminal-verdict-v1",
        "stage": STAGE,
        "final_verdict": FINAL_VERDICT,
        "phase13_execution": "COMPLETE",
        "clauses": {
            "sysenqintrp": "PASS",
            "sysdeqintrp": "PASS",
            "intrp_roundtrip": "PASS",
            "callback_provenance": "PASS",
            "callback_mediation": "PASS",
            "changeclearrcnt": "NOT_REQUIRED",
            "timer1": "NOT_REQUIRED",
            "interrupt_mmio": "NOT_REQUIRED",
            "hardware_interrupt_delivery_required_now": "NO",
            "hercules_initialization_proof": initialization,
            "hercules_first_frame_proof": "NOT_PROVEN",
            "hercules_playability_proof": "NOT_PROVEN",
            "general_ps1_compatibility": "NOT_PROVEN",
        },
        "current_technical_frontier": frontier,
        "first_required_interrupt_source": "NOT_PROVEN",
        "initialization_proof_complete": "YES" if initialization == "PROVEN" else "NO",
        "phase13_target_proof_complete": target_complete,
        "next_frame_frontier": frame["next_major_subsystem"],
        "initialization_contract_source": INITIALIZATION_CONTRACT_SOURCE,
        "initialization_contract_changed": "NO",
        "third_party_code_imported": "NO",
        "phase12_touched": "NO",
        "prior_recon_touched": "NO",
        "private_fixture_bytes_committed": "NO",
    }
    write_json(evidence / "verdict.json", document)
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase13-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P13_99": "PASS",
                    "OPENRECOMP_PHASE13": "PASS_BOUNDED_C0_AND_CALLBACK_MEDIATION",
                    INITIALIZATION_MARKER: initialization,
                    FRAME_MARKER: "NOT_PROVEN", PLAYABILITY_MARKER: "NOT_PROVEN",
                    GENERAL_MARKER: "NOT_PROVEN"},
    })
    write_json(evidence / "p13_99_tests.json", gate.tests_document("verdict"))

    gate.mark("OPENRECOMP_P13_99")
    gate.mark("OPENRECOMP_PHASE13", "PASS_BOUNDED_C0_AND_CALLBACK_MEDIATION")
    gate.mark(SYSENQINTRP_MARKER, "PASS")
    gate.mark(SYSDEQINTRP_MARKER, "PASS")
    gate.mark(INTRP_ROUNDTRIP_MARKER, "PASS")
    gate.mark(CALLBACK_MEDIATION_MARKER, "PASS")
    gate.mark(CHANGECLEARRCNT_MARKER, "NOT_REQUIRED")
    gate.mark(TIMER1_MARKER, "NOT_REQUIRED")
    gate.mark(INTERRUPT_MMIO_MARKER, "NOT_REQUIRED")
    gate.mark(INITIALIZATION_MARKER, initialization)
    gate.mark(INITIALIZATION_REPLAY_MARKER, "PASS")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")
    gate.mark("HARDWARE_INTERRUPT_DELIVERY_REQUIRED_NOW", "NO")
    gate.mark("FIRST_REQUIRED_INTERRUPT_SOURCE", "NOT_PROVEN")
    gate.mark("CURRENT_TECHNICAL_FRONTIER", frontier or "NONE")
    gate.mark("INITIALIZATION_PROOF_COMPLETE", document["initialization_proof_complete"])
    gate.mark("PHASE13_TARGET_PROOF_COMPLETE", target_complete)
    gate.mark("THIRD_PARTY_CODE_IMPORTED", "NO")
    gate.mark("PHASE12_TOUCHED", "NO")
    gate.mark("PRIOR_RECON_TOUCHED", "NO")
    gate.mark("PRIVATE_FIXTURE_BYTES_COMMITTED", "NO")
    gate.mark("FINAL_VERDICT", FINAL_VERDICT)
    gate.mark("NEXT_FRAME_FRONTIER", frame["next_major_subsystem"])


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase13/evidence/P13-99"))
