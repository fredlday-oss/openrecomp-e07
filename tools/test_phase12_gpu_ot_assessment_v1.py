#!/usr/bin/env python3
"""Deterministic P12-06 GPU DMA / DrawOTag / OT promotion assessment.

The Hercules frame path is unreachable (initialization is blocked at the C0
interrupt-routine dispatcher), so no DMA2/ordering-table/draw-OT semantics can
be promoted. The gate re-verifies the existing production typed GPU boundary
with the frozen P9 classifier and records honestly that the Phase-12 GPU/OT/DMA
marker remains `NOT_PROVEN`; DMA2 linked-list mode and OT traversal are not
modelled by the bounded runtime.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_gpu_boundary_v1 as gpu_boundary  # noqa: E402

STAGE = "P12-06"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"
GPU_OT_DMA_MARKER = "OPENRECOMP_PHASE12_GPU_OT_DMA_V1"

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


RUNTIME_SOURCES = (
    ".openrecomp-phase9/runtime/p9_runtime_support.c",
    ".openrecomp-phase10/runtime/p10_mips_extension_v1.c",
    ".openrecomp-phase11/runtime/p11_bios_extension_v1.c",
    ".openrecomp-phase12/runtime/p12_bios_extension_v1.c",
)


def runtime_token_counts() -> dict[str, int]:
    text = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in RUNTIME_SOURCES
    )
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = text.lower()
    return {term: text.count(term) for term in
            ("dma", "drawotag", "ordering", "linked list", "clearotag", "addprim")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-06")
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

        counts = runtime_token_counts()
        check("runtime:no-dma-modelled", counts["dma"] == 0, str(counts))
        check("runtime:no-ot-modelled",
              counts["drawotag"] == 0 and counts["ordering"] == 0
              and counts["linked list"] == 0 and counts["clearotag"] == 0
              and counts["addprim"] == 0, str(counts))

        check("gpu:gp0-known-nop",
              gpu_boundary.classify_gp0(0x00000000) == {
                  "port": "GP0", "command": "0x00", "class": "NOP",
                  "known": True, "emulated": False,
              }, json.dumps(gpu_boundary.classify_gp0(0x00000000), sort_keys=True))
        check("gpu:gp1-display-enable",
              gpu_boundary.classify_gp1(0x03000001)["class"] == "DISPLAY_ENABLE"
              and gpu_boundary.classify_gp1(0x03000001)["emulated"] is False,
              json.dumps(gpu_boundary.classify_gp1(0x03000001), sort_keys=True))
        check("gpu:boundary-classification-only",
              gpu_boundary.classify_gp0(0x02C0C0C0)["emulated"] is False,
              "GP0 boundary classifies, never renders")

        assessment = {
            "schema": "openrecomp-phase12-gpu-ot-dma-assessment-v1",
            "stage": STAGE,
            "marker": GPU_OT_DMA_MARKER,
            "result": "NOT_PROVEN",
            "reason": "the Hercules frame path is unreachable (initialization blocked at "
                      "C0 interrupt services); DMA2 linked-list mode, ordering-table "
                      "traversal and draw-OT submission are not modelled by the bounded "
                      "runtime",
            "verified_production_semantics": {
                "typed_gp0_gp1_classifier": "present (frozen Phase-9 boundary)",
                "emulated": False,
            },
            "runtime_token_counts": counts,
            "predecessor": {INITIALIZATION_MARKER: "NOT_PROVEN"},
        }
        write_json(evidence / "assessment.json", assessment)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {"passed": len(RESULTS), "failed": 0},
        }
        write_json(evidence / "p12_06_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_06": "PASS",
                GPU_OT_DMA_MARKER: "NOT_PROVEN",
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-07",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_06=PASS")
        print(f"{GPU_OT_DMA_MARKER}=NOT_PROVEN")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_06_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-06:{exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: p12-06:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
