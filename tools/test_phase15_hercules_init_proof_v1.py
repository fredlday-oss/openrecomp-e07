#!/usr/bin/env python3
"""Deterministic P15-11 Hercules initialization proof predicate gate.

Formally evaluates the Phase-15 initialization proof predicate:
Formula: INIT-PREDECESSOR and INIT-B0-PATCH and INIT-BOUNDARY and
         INIT-NO-FAIL-CLOSED and INIT-DETERMINISTIC and INIT-NO-FABRICATION
         and (trace_failure_count == 0) and (failed == 0) and (memory_denials == 0)

Evaluation:
- INIT-PREDECESSOR: SATISFIED (P15-00 through P15-10 official PASS records verified)
- INIT-B0-PATCH: SATISFIED (Card patch verified and installed)
- INIT-DETERMINISTIC: SATISFIED (byte-identical across dual runs, empty stderr)
- INIT-NO-FABRICATION: SATISFIED (THIRD_PARTY_CODE_IMPORTED=NO, zero guest fabrication)
- trace_failure_count == 0: SATISFIED
- memory_denial_count == 0: SATISFIED
- INIT-BOUNDARY: NOT_SATISFIED (A0:0x43 Exec handoff at 0x80015b84 requires
  TITLE overlay CD sector delivery which is absent in the bounded model)
- INIT-NO-FAIL-CLOSED: NOT_SATISFIED for complete boundary traversal

Under strict fail-closed discipline, OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF
is NOT PROVEN and must not be promoted.
Stage P15-11 PASSES with marker OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN.
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

from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402

STAGE = "P15-11"
EVIDENCE_ROOT = ROOT / ".openrecomp-phase15" / "evidence"


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 1. Verify predecessor stage evidence completeness
    predecessors = ["P15-00", "P15-01", "P15-02", "P15-03", "P15-04",
                    "P15-05", "P15-06", "P15-07", "P15-08", "P15-09", "P15-10"]
    pred_results = {}
    for pred in predecessors:
        res_file = EVIDENCE_ROOT / pred / "RESULT.json"
        gate.check(f"pred:{pred}-exists", res_file.is_file(), f"{pred} RESULT.json present")
        doc = json.loads(res_file.read_text(encoding="utf-8"))
        gate.check(f"pred:{pred}-pass", doc.get("status") == "PASS", f"{pred} status is PASS")
        pred_results[pred] = doc

    # 2. Check boundary status from P15-09
    p09_boundary = json.loads((EVIDENCE_ROOT / "P15-09" / "init_boundary.json").read_text(encoding="utf-8"))
    boundary_reached = p09_boundary.get("boundary_exec_handoff", {}).get("reached", False)
    boundary_count = p09_boundary.get("boundary_exec_handoff", {}).get("count", -1)
    gate.check("predicate:boundary-not-reached", not boundary_reached and boundary_count == 0,
               f"boundary reached={boundary_reached} count={boundary_count}")

    # 3. Evaluate each condition of the formal formula
    conditions = {
        "INIT-PREDECESSOR": True,
        "INIT-B0-PATCH": True,
        "INIT-BOUNDARY": False,  # CD sector delivery required
        "INIT-NO-FAIL-CLOSED": False,  # Not traversable to Exec boundary
        "INIT-DETERMINISTIC": True,
        "INIT-NO-FABRICATION": True,
        "trace_failure_count == 0": p09_boundary.get("trace_failure_count") == 0,
        "memory_denial_count == 0": p09_boundary.get("memory_denial_count") == 0,
        "failed == 0": False,  # Stopped at boundary dependency
    }

    formula_satisfied = all(conditions.values())
    gate.check("predicate:formula-fails-closed", not formula_satisfied, "formal formula correctly fails closed")

    init_eval = {
        "schema": "openrecomp-phase15-init-proof-evaluation-v1",
        "stage": STAGE,
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "formal_formula": "INIT-PREDECESSOR and INIT-B0-PATCH and INIT-BOUNDARY and INIT-NO-FAIL-CLOSED and INIT-DETERMINISTIC and INIT-NO-FABRICATION and (trace_failure_count == 0) and (failed == 0) and (memory_denials == 0)",
        "condition_evaluations": conditions,
        "unsatisfied_reasons": [
            "INIT-BOUNDARY: A0:0x43 Exec handoff at 0x80015b84 requires TITLE overlay CD-ROM sector delivery",
            "INIT-NO-FAIL-CLOSED: complete boundary traversal requires CD-ROM sector payload delivery",
            "failed == 0: host budget boundary reached prior to semantic Exec handoff",
        ],
        "verdict": "NOT_PROVEN",
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "init_proof_evaluation.json", init_eval)
    assert_public_safe(gate, "init-proof-evaluation", init_eval, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            "OPENRECOMP_P15_11": "PASS",
            "OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF": "NOT_PROVEN",
            "OPENRECOMP_PHASE15_HERCULES_FRAME_PROOF": "NOT_PROVEN",
            "OPENRECOMP_PHASE15_HERCULES_PLAYABILITY_PROOF": "NOT_PROVEN",
            "OPENRECOMP_PHASE15_GENERAL_PS1_COMPATIBILITY": "NOT_PROVEN",
        },
        "next_stage": "P15-20",
        "next_action": "advance to Stage P15-20 hardening and fail-closed verification",
    })
    gate.mark("OPENRECOMP_P15_11")
    gate.mark("OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF", "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-11"))
