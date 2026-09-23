#!/usr/bin/env python3
"""Deterministic P12-07 texture / VRAM provenance promotion assessment.

The Hercules frame path is unreachable (initialization blocked at C0), so no
texture/VRAM provenance can be promoted. VRAM, LoadImage and texture upload are
not modelled by the bounded runtime; the gate records the marker `NOT_PROVEN`.
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

STAGE = "P12-07"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"
TEXTURE_VRAM_MARKER = "OPENRECOMP_PHASE12_TEXTURE_VRAM_V1"

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
            ("vram", "loadimage", "texture", "palette", "texpage", "tpage",
             "texel")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-07")
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
        check("runtime:no-vram-modelled", counts["vram"] == 0, str(counts))
        check("runtime:no-texture-modelled",
              counts["loadimage"] == 0 and counts["texture"] == 0
              and counts["palette"] == 0 and counts["texpage"] == 0
              and counts["tpage"] == 0 and counts["texel"] == 0, str(counts))

        cpu_to_vram = gpu_boundary.classify_gp0(0xA0000000)
        check("gpu:cpu-to-vram-classified-not-emulated",
              cpu_to_vram["known"] is True and cpu_to_vram["emulated"] is False,
              json.dumps(cpu_to_vram, sort_keys=True))

        assessment = {
            "schema": "openrecomp-phase12-texture-vram-assessment-v1",
            "stage": STAGE,
            "marker": TEXTURE_VRAM_MARKER,
            "result": "NOT_PROVEN",
            "reason": "the Hercules frame path is unreachable (initialization blocked at "
                      "C0 interrupt services); VRAM, LoadImage and texture/palette "
                      "provenance are not modelled by the bounded runtime",
            "verified_production_semantics": {
                "gp0_cpu_to_vram": "classified only; not emulated",
                "vram_state": "absent",
            },
            "runtime_token_counts": counts,
        }
        write_json(evidence / "assessment.json", assessment)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {"passed": len(RESULTS), "failed": 0},
        }
        write_json(evidence / "p12_07_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_07": "PASS",
                TEXTURE_VRAM_MARKER: "NOT_PROVEN",
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-08",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_07=PASS")
        print(f"{TEXTURE_VRAM_MARKER}=NOT_PROVEN")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_07_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-07:{exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: p12-07:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
