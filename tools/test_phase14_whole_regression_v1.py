#!/usr/bin/env python3
"""Deterministic P14-90 whole Phase-14 regression gate.

Runs the complete official Phase-14 suite plus the frozen-boundary integrity and
regression checks, aggregates the results and records a machine-readable
regression document. Every sub-run must exit 0, produce empty stderr and contain
no ``FAIL:`` line.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase14/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p14_gate_v1 import run_stage, write_json  # noqa: E402
from p14_contracts_v1 import FRAME_MARKER, GENERAL_MARKER, INITIALIZATION_MARKER, PLAYABILITY_MARKER  # noqa: E402

STAGE = "P14-90"
SCRATCH = ".openrecomp-phase14/build/regression"

SUITES = (
    ("p14-source-integrity", ".openrecomp-phase14/src/p14_source_manifest_v1.py", None),
    ("p13-source-integrity", ".openrecomp-phase14/src/p14_frozen_phase13_integrity_v1.py", None),
    ("p12-source-integrity", ".openrecomp-phase12/src/p12_source_manifest_v1.py", None),
    ("p13-boundary", ".openrecomp-phase14/src/p14_frozen_phase13_boundary_v1.py", None),
    ("p14-boundary", "tools/test_phase14_boundary_v1.py", "p14-boundary"),
    ("p14-service", "tools/test_phase14_service_v1.py", "p14-service"),
    ("p14-consistency", "tools/test_phase14_consistency_v1.py", "p14-consistency"),
    ("p14-hardening", "tools/test_phase14_hardening_v1.py", "p14-hardening"),
    ("p14-replay", "tools/test_phase14_replay_v1.py", "p14-replay"),
    ("p14-frontier-initialization-probe", "tools/test_phase14_frontier_v1.py", "p14-frontier"),
    ("p14-readiness", "tools/test_phase14_readiness_v1.py", "p14-readiness"),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    results = []
    for name, script, evidence_name in SUITES:
        command = [sys.executable, script]
        if evidence_name is not None:
            command += ["--evidence-dir", f"{SCRATCH}/{evidence_name}"]
        completed = subprocess.run(command, cwd=str(root), capture_output=True)
        stdout = completed.stdout
        stderr = completed.stderr
        text = stdout.decode("utf-8", errors="replace")
        fail_lines = [line for line in text.splitlines() if line.startswith("FAIL:")]
        passed = completed.returncode == 0 and len(stderr) == 0 and not fail_lines
        results.append({
            "name": name,
            "returncode": completed.returncode,
            "stderr_empty": len(stderr) == 0,
            "stdout_sha256": sha256_bytes(stdout),
            "fail_lines": fail_lines,
            "status": "PASS" if passed else "FAIL",
        })
        gate.check(f"regression:{name}", passed,
                   json.dumps(results[-1], sort_keys=True))

    tests = len(results)
    failed = sum(item["status"] == "FAIL" for item in results)
    regression = {
        "schema": "openrecomp-phase14-regression-v1",
        "stage": STAGE,
        "suites": results,
        "tests": tests,
        "failed": failed,
    }
    write_json(evidence / "regression.json", regression)
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase14-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P14_90": "PASS", "P14_90_TESTS": str(tests),
                    "P14_90_FAILED": str(failed),
                    INITIALIZATION_MARKER: "NOT_PROVEN", FRAME_MARKER: "NOT_PROVEN",
                    PLAYABILITY_MARKER: "NOT_PROVEN", GENERAL_MARKER: "NOT_PROVEN"},
        "next_stage": "P14-91",
    })
    write_json(evidence / "p14_90_tests.json", gate.tests_document("whole-regression"))
    gate.mark("OPENRECOMP_P14_90")
    gate.mark("P14_90_TESTS", str(tests))
    gate.mark("P14_90_FAILED", str(failed))
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase14/evidence/P14-90"))
