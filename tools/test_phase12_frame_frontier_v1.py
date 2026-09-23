#!/usr/bin/env python3
"""Deterministic P12-09 Hercules first-frame execution frontier-loop gate.

Resumes the final-tree initialization execution and records that no
frame-submission boundary is reachable while initialization is blocked at the C0
interrupt-routine dispatcher. The observed GPU traffic is classified and shown
to be initialization-only (no ordering-table traversal, DMA or frame
submission). The frame marker remains `NOT_PROVEN`.
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

import p9_gpu_boundary_v1 as gpu_boundary  # noqa: E402
import p11_trace_v1 as p11_trace  # noqa: E402
import p12_proof_v1 as proof  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402
from tools import test_phase12_caller_coverage_v1 as cov  # noqa: E402

STAGE = "P12-09"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"

#: GP0 opcodes that would indicate primitive/frame submission.
FRAME_GP0_OPCODES = tuple(range(0x20, 0x40)) + tuple(range(0x40, 0x60)) \
    + tuple(range(0x60, 0x80)) + tuple(range(0x80, 0xA0)) \
    + tuple(range(0xA0, 0xC0)) + tuple(range(0xC0, 0xE0))

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
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-09")
    parser.add_argument("--private-fixture-root",
                        default=str(p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    build_root = ROOT / ".openrecomp-phase12" / "build"

    try:
        initial = json.loads(
            (ROOT / ".openrecomp-phase12/evidence/P12-05/RESULT.json").read_text(
                encoding="utf-8")
        )
        check("predecessor:initialization-not-proven",
              initial["markers"][INITIALIZATION_MARKER] == "NOT_PROVEN",
              initial["markers"][INITIALIZATION_MARKER])

        result = proof.build_and_run(build_root, "p12-09-frame-frontier",
                                     fixture_root=pathlib.Path(options.private_fixture_root))
        first = result["first"]
        second = result["second"]
        check("run:deterministic", proof.deterministic_match(first, second),
              first["stdout_sha256"])
        failure = result["failure"]
        check("frontier:no-frame-boundary", failure.get("site") is not None,
              json.dumps(failure, sort_keys=True))
        check("frontier:same-c0-blocker",
              failure.get("site") == "0x80015f5c"
              and failure.get("source_value") == "0x000000c0",
              json.dumps(failure, sort_keys=True))

        writes = p11_05.classify_writes(first["parsed"])
        frame_writes = [
            item for item in writes
            if item["classification"]["port"] == "GP0"
            and int(item["classification"]["command"], 16) in FRAME_GP0_OPCODES
        ]
        check("gpu:no-frame-primitive", not frame_writes,
              json.dumps(frame_writes, sort_keys=True))
        check("gpu:initialization-only",
              all(item["classification"]["class"] in ("NOP", "DISPLAY_ENABLE")
                  for item in writes),
              json.dumps([item["classification"] for item in writes], sort_keys=True))
        check("no-ot-no-dma",
              first["simple"].get("trace_distinct_blocks") is not None
              and "drawotag" not in first["stdout"].decode("utf-8", "replace").lower(),
              "no ordering-table/DMA activity observed")

        frontier_document = {
            "schema": "openrecomp-phase12-frame-frontier-v1",
            "stage": STAGE,
            "result": "NOT_PROVEN",
            "reason": "no frame-submission boundary is reachable; initialization is "
                      "blocked at the C0 interrupt-routine dispatcher",
            "current_frontier": failure,
            "gpu_writes": [
                {"port": item["classification"]["port"],
                 "class": item["classification"]["class"],
                 "known": item["classification"]["known"]}
                for item in writes
            ],
            "frame_gp0_primitive_count": len(frame_writes),
            "repeating_loop": {
                "detected": result["analysis"]["repeating_loop"]["detected"],
                "cycle_length": result["analysis"]["repeating_loop"]["cycle_length"],
                "phase": "post-failure polling, not a frame cycle",
            },
            "runs": {
                "first_stdout_sha256": first["stdout_sha256"],
                "second_stdout_sha256": second["stdout_sha256"],
                "byte_identical": proof.deterministic_match(first, second),
            },
        }
        write_json(evidence / "frame_frontier.json", frontier_document)
        cov.assert_public_safe("frame_frontier", frontier_document, result["image"].payload)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {"passed": len(RESULTS), "failed": 0},
        }
        write_json(evidence / "p12_09_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_09": "PASS",
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-10",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_09=PASS")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_09_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-09:{exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: p12-09:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
