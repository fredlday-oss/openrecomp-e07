#!/usr/bin/env python3
"""Deterministic P15-90 whole Phase-15 regression gate.

Runs the complete official Phase-15 suite plus the frozen Phase-14 boundary and
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
              ".openrecomp-phase14/src", ".openrecomp-phase15/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p15_contracts_v1 import (  # noqa: E402
    FRAME_MARKER,
    GENERAL_MARKER,
    INITIALIZATION_MARKER,
    PLAYABILITY_MARKER,
)
from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402

STAGE = "P15-90"
SCRATCH = ".openrecomp-phase15/build/regression"

SUITES = (
    ("p15-source-integrity", ".openrecomp-phase15/src/p15_source_manifest_v1.py", None),
    ("p14-source-integrity", ".openrecomp-phase15/src/p15_frozen_phase14_integrity_v1.py", None),
    ("p14-boundary", ".openrecomp-phase15/src/p15_frozen_phase14_boundary_v1.py", None),
    ("p15-interrupt-mmio", "tools/test_phase15_interrupt_mmio_v1.py", "p15-interrupt-mmio"),
    ("p15-i-stat-i-mask", "tools/test_phase15_i_stat_i_mask_v1.py", "p15-i-stat-i-mask"),
    ("p15-sys-control-dma2", "tools/test_phase15_sys_control_dma2_v1.py", "p15-sys-control-dma2"),
    ("p15-null-store", "tools/test_phase15_null_store_v1.py", "p15-null-store"),
    ("p15-timer1-virtual-time", "tools/test_phase15_timer1_virtual_time_v1.py", "p15-timer1-virtual-time"),
    ("p15-gpustat", "tools/test_phase15_gpustat_v1.py", "p15-gpustat"),
    ("p15-init-no-fail-closed", "tools/test_phase15_init_no_fail_closed_v1.py", "p15-init-no-fail-closed"),
    ("p15-hercules-init-proof", "tools/test_phase15_hercules_init_proof_v1.py", "p15-hercules-init-proof"),
    ("p15-hardening", "tools/test_phase15_hardening_v1.py", "p15-hardening"),
    ("p15-consistency", "tools/test_phase15_consistency_v1.py", "p15-consistency"),
    ("p15-init-replay", "tools/test_phase15_init_replay_v1.py", "p15-init-replay"),
    ("p15-first-frame-readiness", "tools/test_phase15_first_frame_readiness_v1.py", "p15-first-frame-readiness"),
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
        "schema": "openrecomp-phase15-regression-v1",
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
        "schema": "openrecomp-phase15-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            "OPENRECOMP_P15_90": "PASS",
            "P15_90_TESTS": str(tests),
            "P15_90_FAILED": str(failed),
            INITIALIZATION_MARKER: "NOT_PROVEN",
            FRAME_MARKER: "NOT_PROVEN",
            PLAYABILITY_MARKER: "NOT_PROVEN",
            GENERAL_MARKER: "NOT_PROVEN",
        },
        "next_stage": "P15-91",
        "next_action": "advance to Stage P15-91 evidence closure",
    })
    gate.mark("OPENRECOMP_P15_90")
    gate.mark("P15_90_TESTS", str(tests))
    gate.mark("P15_90_FAILED", str(failed))
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-90"))
