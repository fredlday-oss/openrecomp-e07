#!/usr/bin/env python3
"""Deterministic P12-90 whole Phase-12 regression gate.

Re-verifies the frozen Phase-11 boundary, source integrity, every P12 stage's
committed deterministic evidence and marker, and the reserved proof markers.
The expensive private-fixture stages are verified against their committed
two-run deterministic evidence (their shared-runtime build identities are
historical), not re-executed.
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
FROZEN_PREFIXES = (
    ".openrecomp-phase1", ".openrecomp-phase2", ".openrecomp-phase3",
    ".openrecomp-phase4", ".openrecomp-phase5", ".openrecomp-phase6",
    ".openrecomp-phase7", ".openrecomp-phase8", ".openrecomp-phase9",
    ".openrecomp-phase10", ".openrecomp-phase11", "tools",
)
INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"

STAGES = ("P12-00", "P12-01", "P12-02", "P12-03", "P12-04", "P12-05",
          "P12-06", "P12-07", "P12-08", "P12-09", "P12-10", "P12-20",
          "P12-30", "P12-40")

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
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-90")
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        head = git("rev-parse", "HEAD").stdout.strip()
        ancestor = git("merge-base", "--is-ancestor", BASE_COMMIT, head).returncode
        check("boundary:base-ancestor", ancestor == 0, str(ancestor))
        diff = git("diff", "--name-only", BASE_COMMIT, head, "--", *FROZEN_PREFIXES)
        changed = [line for line in diff.stdout.splitlines()
                   if not line.startswith("tools/test_phase12_")]
        check("boundary:frozen-tree-unchanged", not changed,
              "\n".join(changed)[:200])
        touched = []
        for line in git("status", "--porcelain", "--", *FROZEN_PREFIXES).stdout.splitlines():
            if line.startswith("??"):
                continue
            path = line[3:].strip().strip('"')
            if path.startswith("tools/test_phase12_"):
                continue
            touched.append(line)
        check("boundary:frozen-worktree-clean", not touched, "\n".join(touched)[:200])

        integrity = subprocess.run(
            [sys.executable, ".openrecomp-phase12/src/p12_source_manifest_v1.py"],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        check("source:integrity",
              integrity.stdout.startswith("OPENRECOMP_PHASE12_SOURCE_INTEGRITY=PASS"),
              integrity.stdout.strip())

        total_checks = 0
        stage_summary: list[dict[str, Any]] = []
        for stage in STAGES:
            result_path = ROOT / f".openrecomp-phase12/evidence/{stage}/RESULT.json"
            if not result_path.is_file():
                check(f"{stage}:result-present", False, "missing RESULT.json")
                continue
            result = json.loads(result_path.read_text(encoding="utf-8"))
            marker = f"OPENRECOMP_P12_{stage.split('-')[1]}"
            check(f"{stage}:status", result.get("status") == "PASS",
                  str(result.get("status")))
            check(f"{stage}:marker", result.get("markers", {}).get(marker) == "PASS",
                  json.dumps(result.get("markers", {}), sort_keys=True))
            runs_path = ROOT / f".openrecomp-phase12/evidence/{stage}/official_runs.json"
            check(f"{stage}:official-runs-present", runs_path.is_file(), "present")
            runs = json.loads(runs_path.read_text(encoding="utf-8"))
            det_path = ROOT / f".openrecomp-phase12/evidence/{stage}/determinism.json"
            determinism = json.loads(det_path.read_text(encoding="utf-8"))
            check(f"{stage}:two-run-identical",
                  runs["identical_raw"] and runs["identical_lf"]
                  and runs["returncode_zero_both"] and runs["stderr_empty_both"]
                  and runs["markers_present_both"]
                  and determinism["artifacts_identical"],
                  json.dumps({k: runs[k] for k in
                              ("identical_raw", "identical_lf", "returncode_zero_both",
                               "stderr_empty_both", "markers_present_both")}
                             | {"artifacts_identical": determinism["artifacts_identical"]},
                             sort_keys=True))
            tests_path = ROOT / f".openrecomp-phase12/evidence/{stage}/p12_{stage.split('-')[1].lower()}_tests.json"
            passed = None
            if tests_path.is_file():
                tests = json.loads(tests_path.read_text(encoding="utf-8"))
                passed = tests.get("summary", {}).get("passed")
                total_checks += int(passed or 0)
            stage_summary.append({
                "stage": stage,
                "marker": marker,
                "result_marker": result.get("markers", {}).get(marker),
                "checks": passed,
                "two_run_identical": runs["identical_raw"] and runs["identical_lf"],
            })

        check("summary:stages", len(stage_summary) == len(STAGES),
              str(len(stage_summary)))
        check("summary:checks-positive", total_checks > 0, str(total_checks))

        for marker in (INITIALIZATION_MARKER, FRAME_MARKER, PLAYABILITY_MARKER,
                       GENERAL_MARKER):
            values = {
                json.loads((ROOT / f".openrecomp-phase12/evidence/{stage}/RESULT.json")
                           .read_text(encoding="utf-8")).get("markers", {}).get(marker)
                for stage in STAGES
                if (ROOT / f".openrecomp-phase12/evidence/{stage}/RESULT.json").is_file()
            }
            check(f"reserved:{marker.split('_')[-1]}",
                  "PROVEN" not in values, json.dumps(sorted(str(v) for v in values)))

        regression = {
            "schema": "openrecomp-phase12-whole-regression-v1",
            "stage": "P12-90",
            "phase11_base_commit": BASE_COMMIT,
            "frozen_tree_unchanged": True,
            "source_integrity": "PASS",
            "stage_count": len(stage_summary),
            "total_stage_checks": total_checks,
            "stage_summary": stage_summary,
            "reserved_markers": {
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
        }
        write_json(evidence / "regression.json", regression)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": "P12-90",
            "checks": RESULTS,
            "summary": {"passed": len(RESULTS), "failed": 0},
        }
        write_json(evidence / "p12_90_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": "P12-90",
            "status": "PASS",
            "markers": {"OPENRECOMP_P12_90": "PASS"},
            "next_stage": "P12-91",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_90=PASS")
        print(f"P12_90_STAGE_CHECKS={len(RESULTS)}")
        print(f"P12_90_TOTAL_STAGE_CHECKS={total_checks}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-90:{exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: p12-90:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
