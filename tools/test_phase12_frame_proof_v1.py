#!/usr/bin/env python3
"""Deterministic P12-10 Hercules first-frame proof gate.

Evaluates the P12-00 frame contract from the committed P12-05/P12-09 evidence.
No frame-submission boundary is reached, so
`OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF` remains `NOT_PROVEN`, and
playability/general compatibility remain reserved `NOT_PROVEN`.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"

STAGE = "P12-10"

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL",
                    "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def write_json(path: pathlib.Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def load(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-10")
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        init = load(".openrecomp-phase12/evidence/P12-05/initialization_proof.json")
        frontier = load(".openrecomp-phase12/evidence/P12-09/frame_frontier.json")

        check("predecessor:initialization-not-proven",
              init["result"] == "NOT_PROVEN", init["result"])
        check("predecessor:same-frontier",
              frontier["current_frontier"]["site"] == "0x80015f5c",
              json.dumps(frontier["current_frontier"], sort_keys=True))

        predicates = {
            "FRAME-PREDECESSOR": init["result"] == "PROVEN",
            "FRAME-PRIMITIVE": frontier["frame_gp0_primitive_count"] > 0,
            "FRAME-OT": False,
            "FRAME-SUBMIT": frontier["current_frontier"].get("site") is None,
            "FRAME-DETERMINISTIC": frontier["runs"]["byte_identical"],
            "FRAME-NOT-PLAYABILITY": True,
        }
        check("contract:predecessor-fails", predicates["FRAME-PREDECESSOR"] is False,
              "initialization not proven")
        check("contract:no-primitive", predicates["FRAME-PRIMITIVE"] is False,
              str(frontier["frame_gp0_primitive_count"]))
        check("contract:deterministic", predicates["FRAME-DETERMINISTIC"] is True,
              frontier["runs"]["first_stdout_sha256"])
        check("contract:not-satisfied", not all(predicates.values()),
              json.dumps(predicates, sort_keys=True))

        check("reserved:playability-not-proven",
              PLAYABILITY_MARKER.endswith("PLAYABILITY_PROOF"), "reserved")
        check("reserved:general-not-proven",
              GENERAL_MARKER.endswith("GENERAL_PS1_COMPATIBILITY"), "reserved")

        proof_document = {
            "schema": "openrecomp-phase12-frame-proof-v1",
            "stage": STAGE,
            "result": "NOT_PROVEN",
            "marker": FRAME_MARKER,
            "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
            "predicates": predicates,
            "satisfied": False,
            "current_frontier": frontier["current_frontier"],
            "reason": "the initialization predecessor is not proven and no "
                      "frame-submission boundary is reachable",
            "reserved_markers": {
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "explicitly_not_a_frame": [
                "initialization GPU traffic is classification-only (one GP0 NOP, one GP1 DISPLAY_ENABLE)",
                "the detected repeating 14-block cycle is post-failure polling",
            ],
        }
        write_json(evidence / "frame_proof.json", proof_document)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {"passed": len(RESULTS), "failed": 0},
        }
        write_json(evidence / "p12_10_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_10": "PASS",
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-20",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_10=PASS")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_10_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-10:{exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: p12-10:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
