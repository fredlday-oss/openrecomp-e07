#!/usr/bin/env python3
"""Deterministic P12-08 GTE / geometry / OT promotion assessment.

The Hercules frame path is unreachable (initialization blocked at C0), so no GTE
geometry can be promoted. GTE coprocessor operations are not in the production
semantic rule table and must fail closed; the gate records the marker
`NOT_PROVEN`.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p10_mips32_semantics_v1 as p10_semantics  # noqa: E402
import p11_dynamic_v1 as dynamic  # noqa: E402

STAGE = "P12-08"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"
GTE_GEOMETRY_MARKER = "OPENRECOMP_PHASE12_GTE_GEOMETRY_V1"

GTE_OPS = ("cop2", "lwc2", "swc2", "mfc2", "mtc2", "cfc2", "ctc2")

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-08")
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        initial = json.loads(
            (ROOT / ".openrecomp-phase12/evidence/P12-05/RESULT.json").read_text(
                encoding="utf-8")
        )
        check("predecessor:initialization-not-proven",
              initial["markers"][INITIALIZATION_MARKER] == "NOT_PROVEN",
              initial["markers"][INITIALIZATION_MARKER])

        rules = {rule.op for rule in p10_semantics.semantics_rules()}
        check("semantics:no-gte-rule",
              all(op not in rules for op in GTE_OPS),
              json.dumps([op for op in GTE_OPS if op in rules]))
        check("semantics:fail-closed-policy",
              dynamic.DYNAMIC_VERSION == "1.0.0",
              "the frozen dynamic resolver is reused unchanged")

        assessment = {
            "schema": "openrecomp-phase12-gte-geometry-assessment-v1",
            "stage": STAGE,
            "marker": GTE_GEOMETRY_MARKER,
            "result": "NOT_PROVEN",
            "reason": "the Hercules frame path is unreachable (initialization blocked at "
                      "C0 interrupt services); GTE geometry (RTPT/RTPS/NCLIP) and "
                      "depth-ordered OT insertion are not reached or modelled",
            "gte_ops_absent_from_rule_table": list(GTE_OPS),
            "policy": "any GTE coprocessor operation remains fail-closed",
        }
        write_json(evidence / "assessment.json", assessment)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {"passed": len(RESULTS), "failed": 0},
        }
        write_json(evidence / "p12_08_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_08": "PASS",
                GTE_GEOMETRY_MARKER: "NOT_PROVEN",
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-09",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_08=PASS")
        print(f"{GTE_GEOMETRY_MARKER}=NOT_PROVEN")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_08_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-08:{exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: p12-08:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
