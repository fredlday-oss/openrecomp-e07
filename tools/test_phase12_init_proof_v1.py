#!/usr/bin/env python3
"""Deterministic P12-05 Hercules initialization-proof gate.

Executes the P12-00 initialization contract on the final stage tree with two
fresh deterministic runs and reports the result honestly. Because the
initialization completion boundary is not reached (C0 interrupt services stay
fail-closed), `OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF` remains
`NOT_PROVEN`; the stage itself passes as a bounded result.
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

import p12_proof_v1 as proof  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402
from tools import test_phase12_caller_coverage_v1 as cov  # noqa: E402

STAGE = "P12-05"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"

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
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-05")
    parser.add_argument("--private-fixture-root",
                        default=str(p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    build_root = ROOT / ".openrecomp-phase12" / "build"

    try:
        result = proof.build_and_run(build_root, "p12-05-initialization",
                                     fixture_root=pathlib.Path(options.private_fixture_root))
        built = result["built"]
        first = result["first"]
        second = result["second"]
        check("run:build", all(status == "OK" for status in built["build_status"]),
              str(built["build_status"]))
        check("run:build-reproducible", built["build_reproducible"], "reproducible")
        check("run:exit-stderr",
              first["returncode"] == second["returncode"] == 0
              and first["stderr_bytes"] == second["stderr_bytes"] == 0,
              "exit 0 and empty stderr")
        check("run:two-fresh-deterministic", proof.deterministic_match(first, second),
              first["stdout_sha256"])

        contract = proof.evaluate_initialization_contract(result)
        predicates = contract["predicates"]
        check("contract:predecessor", predicates["INIT-PREDECESSOR"], "P12-00..04 present")
        check("contract:b0-patch", predicates["INIT-B0-PATCH"],
              "GetB0Table entry 0x5B, derived pointers, eleven-word clear")
        check("contract:deterministic", predicates["INIT-DETERMINISTIC"],
              "two-run determinism")
        check("contract:no-fabrication", predicates["INIT-NO-FABRICATION"], "true")
        check("contract:boundary-not-reached", contract["boundary_reached"] is False,
              json.dumps(contract["current_frontier"], sort_keys=True))
        check("contract:no-fail-closed-false", predicates["INIT-NO-FAIL-CLOSED"] is False,
              "fail-closed events remain on the prefix")
        check("contract:not-satisfied", contract["satisfied"] is False,
              "initialization contract not satisfied")
        check("contract:milestone-b-not-proven", contract["milestone_b"] == "NOT_PROVEN",
              contract["milestone_b"])

        proof_document = {
            "schema": "openrecomp-phase12-initialization-proof-v1",
            "stage": STAGE,
            "result": "NOT_PROVEN",
            "marker": INITIALIZATION_MARKER,
            "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
            "predicates": predicates,
            "satisfied": False,
            "boundary_reached": False,
            "current_frontier": contract["current_frontier"],
            "blocker": contract["blocker"],
            "deterministic_fields": proof.deterministic_fields(first, second),
            "runs": {
                "first_stdout_sha256": first["stdout_sha256"],
                "second_stdout_sha256": second["stdout_sha256"],
                "byte_identical": proof.deterministic_match(first, second),
                "block_events": first["simple"].get("trace_block_events"),
                "block_digest": first["simple"].get("trace_block_digest"),
            },
        }
        write_json(evidence / "initialization_proof.json", proof_document)
        cov.assert_public_safe("initialization_proof", proof_document, result["image"].payload)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {
                "passed": sum(item["status"] == "PASS" for item in RESULTS),
                "failed": sum(item["status"] == "FAIL" for item in RESULTS),
            },
        }
        write_json(evidence / "p12_05_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_05": "PASS",
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-06",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_05=PASS")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_05_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-05:{exc}")
        return 1
    except Exception as exc:  # fail closed without a traceback
        print(f"FAIL: p12-05:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
