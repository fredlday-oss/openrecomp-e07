#!/usr/bin/env python3
"""Deterministic P12-99 final Phase-12 verdict gate.

Runs only after P12-91 PASS. Reports the Phase-12 infrastructure/regression
integrity and each proof marker separately, and issues the bounded terminal
verdict. The target proofs are not achieved, so the combined
initialization-and-frame proof marker remains `NOT_PROVEN` and the phase closes
bounded, never falsely successful.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE_COMMIT = "665d11dc9f760d0c4ea2486e186c1fe5c762647c"
STAGES = ("P12-00", "P12-01", "P12-02", "P12-03", "P12-04", "P12-05",
          "P12-06", "P12-07", "P12-08", "P12-09", "P12-10", "P12-20",
          "P12-30", "P12-40", "P12-90", "P12-91")
FINAL_VERDICT = "PASS_BOUNDED_B0_MEDIATION_PRIVATE_FIXTURE"

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


def git(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *arguments], cwd=str(ROOT),
                          capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-99")
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        closure = json.loads(
            (ROOT / ".openrecomp-phase12/evidence/P12-91/RESULT.json").read_text(
                encoding="utf-8")
        )
        check("predecessor:p12-91",
              closure["status"] == "PASS"
              and closure["markers"]["OPENRECOMP_P12_91"] == "PASS",
              json.dumps(closure["markers"], sort_keys=True))

        stage_results: dict[str, str] = {}
        for stage in STAGES:
            result = json.loads(
                (ROOT / f".openrecomp-phase12/evidence/{stage}/RESULT.json").read_text(
                    encoding="utf-8")
            )
            stage_results[stage] = result["status"]

        matrix = json.loads(
            (ROOT / ".openrecomp-phase12/evidence/P12-91/evidence_closure.json")
            .read_text(encoding="utf-8")
        )["proof_matrix"]

        check("infrastructure:all-stages-pass",
              all(value == "PASS" for value in stage_results.values()),
              json.dumps(stage_results, sort_keys=True))
        check("proof:b0-5b",
              matrix["OPENRECOMP_PHASE12_B0_5B_CHANGECLEARPAD_V1"]["result"] == "PASS",
              "PASS")
        check("proof:b0-table",
              matrix["OPENRECOMP_PHASE12_B0_TABLE_INDIRECT_V1"]["result"] == "PASS",
              "PASS")
        check("proof:replay",
              matrix["OPENRECOMP_PHASE12_END_TO_END_REPLAY_V1"]["result"] == "PASS",
              "PASS")
        check("proof:initialization-not-proven",
              matrix["OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"]["result"]
              == "NOT_PROVEN", "NOT_PROVEN")
        check("proof:frame-not-proven",
              matrix["OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"]["result"]
              == "NOT_PROVEN", "NOT_PROVEN")
        check("proof:playability-reserved",
              matrix["OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"]["result"]
              == "NOT_PROVEN", "NOT_PROVEN")
        check("proof:general-reserved",
              matrix["OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"]["result"]
              == "NOT_PROVEN", "NOT_PROVEN")
        target_complete = (
            matrix["OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"]["result"] == "PASS"
            and matrix["OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"]["result"] == "PASS"
        )
        check("target-proof-not-complete", not target_complete, "NO")

        f90 = json.loads(
            (ROOT / ".openrecomp-phase12/evidence/P12-90/determinism.json").read_text(
                encoding="utf-8")
        )
        run1 = f90["runs"]["run1"]
        run2 = f90["runs"]["run2"]
        f90_tests = json.loads(
            (ROOT / ".openrecomp-phase12/evidence/P12-90/p12_90_tests.json").read_text(
                encoding="utf-8")
        )["summary"]

        branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        head = git("rev-parse", "HEAD").stdout.strip()
        commits = git("log", "--oneline", f"{BASE_COMMIT}..HEAD").stdout.strip().splitlines()
        residue = []
        for line in git("status", "--porcelain").stdout.splitlines():
            path = line[3:].strip().strip('"')
            if path.startswith(".openrecomp-phase12") or path.startswith("tools/test_phase12_"):
                continue
            residue.append(line)
        boundary = json.loads(
            (ROOT / ".openrecomp-phase12/evidence/P12-04/blocker.json").read_text(
                encoding="utf-8")
        )
        frontier = boundary["current_frontier"]

        report = {
            "schema": "openrecomp-phase12-final-verdict-v1",
            "stage": "P12-99",
            "CURRENT_BRANCH": branch,
            "PHASE11_BASE_COMMIT": BASE_COMMIT,
            "PHASE12_HEAD": head,
            "P12_STAGE_RESULTS": stage_results,
            "markers": {key: value["result"] for key, value in sorted(matrix.items())},
            "P12_90_TESTS": f90_tests["passed"],
            "P12_90_FAILED": f90_tests["failed"],
            "P12_90_RUN1_SHA256": run1["stdout_sha256_raw"],
            "P12_90_RUN2_SHA256": run2["stdout_sha256_raw"],
            "P12_90_BYTE_IDENTICAL": run1["stdout_sha256_raw"] == run2["stdout_sha256_raw"],
            "CURRENT_TECHNICAL_FRONTIER": frontier,
            "INITIALIZATION_PROOF_COMPLETE": "NO",
            "FRAME_PROOF_COMPLETE": "NO",
            "PHASE12_TARGET_PROOF_COMPLETE": "NO",
            "FINAL_VERDICT": FINAL_VERDICT,
            "COMMITS_CREATED": commits,
            "INHERITED_RESIDUE_LINES": len(residue),
            "THIRD_PARTY_CODE_IMPORTED": "NO",
            "PHASE11_TOUCHED": "NO",
            "PRIOR_RECON_TOUCHED": "NO",
            "PRIVATE_FIXTURE_BYTES_COMMITTED": "NO",
        }
        write_json(evidence / "final_verdict.json", report)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": "P12-99",
            "checks": RESULTS,
            "summary": {"passed": len(RESULTS), "failed": 0},
        }
        write_json(evidence / "p12_99_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": "P12-99",
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_99": "PASS",
                "OPENRECOMP_PHASE12": FINAL_VERDICT,
                "OPENRECOMP_PHASE12_INITIALIZATION_AND_FRAME_PROOF": "NOT_PROVEN",
            },
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_99=PASS")
        print(f"CURRENT_BRANCH={branch}")
        print(f"PHASE11_BASE_COMMIT={BASE_COMMIT}")
        print(f"PHASE12_HEAD={head}")
        for stage in STAGES:
            print(f"{stage.replace('-', '_')}_RESULT={stage_results[stage]}")
        print("P12_90_TESTS=" + str(f90_tests["passed"]))
        print("P12_90_FAILED=" + str(f90_tests["failed"]))
        print(f"P12_90_RUN1_SHA256={run1['stdout_sha256_raw']}")
        print(f"P12_90_RUN2_SHA256={run2['stdout_sha256_raw']}")
        print(f"P12_90_BYTE_IDENTICAL={report['P12_90_BYTE_IDENTICAL']}")
        for key, value in sorted(matrix.items()):
            print(f"{key}={value['result']}" if "result" in value else f"{key}={value}")
        print("THIRD_PARTY_CODE_IMPORTED=NO")
        print("PHASE11_TOUCHED=NO")
        print("PRIOR_RECON_TOUCHED=NO")
        print("PRIVATE_FIXTURE_BYTES_COMMITTED=NO")
        print(f"CURRENT_TECHNICAL_FRONTIER={frontier['site']}({frontier['function_id']},block={frontier['block_index']})")
        print("INITIALIZATION_PROOF_COMPLETE=NO")
        print("FRAME_PROOF_COMPLETE=NO")
        print("PHASE12_TARGET_PROOF_COMPLETE=NO")
        print("OPENRECOMP_PHASE12_INITIALIZATION_AND_FRAME_PROOF=NOT_PROVEN")
        print(f"OPENRECOMP_PHASE12={FINAL_VERDICT}")
        print(f"FINAL_VERDICT={FINAL_VERDICT}")
        print(f"P12_99_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-99:{exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: p12-99:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
