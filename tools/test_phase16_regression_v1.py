#!/usr/bin/env python3
"""Deterministic P16-90 whole Phase-16 regression gate.

Runs the complete official Phase-16 suite plus the frozen Phase-15 boundary and
integrity checks, aggregates the results, and records a machine-readable
regression document. Every sub-run must exit 0, produce empty stderr, and contain
no FAIL lines.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src", ".openrecomp-phase15/src",
              ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p16_contracts_v1 as contract  # noqa: E402
from p16_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402

STAGE = "P16-90"
SCRATCH = ".openrecomp-phase16/build/regression"

SUITES = (
    ("p16-source-integrity", ".openrecomp-phase16/src/p16_source_manifest_v1.py", None),
    ("p15-source-integrity", ".openrecomp-phase16/src/p16_frozen_phase15_integrity_v1.py", None),
    ("p15-frozen-boundary", ".openrecomp-phase16/src/p16_frozen_phase15_boundary_v1.py", None),
    ("p16-bootstrap", "tools/test_phase16_bootstrap_v1.py", "p16-bootstrap"),
    ("p16-exec-contract", "tools/test_phase16_exec_contract_v1.py", "p16-exec-contract"),
    ("p16-title-mapping", "tools/test_phase16_title_mapping_v1.py", "p16-title-mapping"),
    ("p16-cdrom-source", "tools/test_phase16_cdrom_source_v1.py", "p16-cdrom-source"),
    ("p16-cdrom-production", "tools/test_phase16_cdrom_production_v1.py", "p16-cdrom-production"),
    ("p16-title-load-causality", "tools/test_phase16_title_load_causality_v1.py", "p16-title-load-causality"),
    ("p16-title-exec-transition", "tools/test_phase16_title_exec_transition_v1.py", "p16-title-exec-transition"),
    ("p16-title-replay", "tools/test_phase16_title_replay_v1.py", "p16-title-replay"),
    ("p16-frontier-closure", "tools/test_phase16_frontier_closure_v1.py", "p16-frontier-closure"),
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
    regression_doc = {
        "schema": "openrecomp-phase16-regression-v1",
        "stage": STAGE,
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "suites": results,
        "tests": tests,
        "failed": failed,
        "fail_closed_discipline": "STRICT_NO_SUPPRESSION",
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "regression.json", regression_doc)
    assert_public_safe(gate, "regression", regression_doc, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase16-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            contract.REGRESSION_MARKER: "PASS",
            "P16_90_TESTS": str(tests),
            "P16_90_FAILED": str(failed),
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
            contract.FIRST_FRAME_READY_MARKER: "NO",
        },
        "next_stage": "P16-91",
        "next_action": "advance to Stage P16-91 evidence closure",
    })
    gate.mark(contract.REGRESSION_MARKER)
    gate.mark("P16_90_TESTS", str(tests))
    gate.mark("P16_90_FAILED", str(failed))
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase16/evidence/P16-90"))
