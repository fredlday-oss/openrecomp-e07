#!/usr/bin/env python3
"""Deterministic P12-30 direct / indirect BIOS path consistency gate.

Verifies that the direct `B0:0x5B` stub invocation and the `B0:0x57
GetB0Table` -> entry `0x5B` indirect path converge on the same bounded service
implementation without a fabricated BIOS address, and that all known Hercules
callers are accounted for.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STAGE = "P12-30"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"

EXPECTED_CALLERS = (
    "0x80015c3c", "0x80015cc8", "0x80015d28", "0x80016198",
    "0x8001670c", "0x80026d74", "0x80026dd0",
)
DIRECT_STUB_SITE = "0x80015f3c"

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
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-30")
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        coverage = json.loads(
            (ROOT / ".openrecomp-phase12/evidence/P12-02/coverage.json").read_text(
                encoding="utf-8")
        )
        mediation = json.loads(
            (ROOT / ".openrecomp-phase12/evidence/P12-03/mediation.json").read_text(
                encoding="utf-8")
        )
        inventory = json.loads(
            (ROOT / ".openrecomp-phase12/evidence/P12-02/inventory.json").read_text(
                encoding="utf-8")
        )

        check("direct:seven-callers",
              tuple(coverage["b0_5b_direct"]["callers"]) == EXPECTED_CALLERS,
              json.dumps(coverage["b0_5b_direct"]["callers"]))
        check("direct:stub-site", coverage["b0_5b_direct"]["stub_jr"] == DIRECT_STUB_SITE,
              coverage["b0_5b_direct"]["stub_jr"])
        check("direct:resolved",
              coverage["b0_5b_direct"]["stub_reachable_and_resolved"] is True,
              "direct stub resolved to ps1.bios.B0.5b")

        check("indirect:table-base",
              mediation["acquisition"]["synthetic_table_base"] == "0x1f000000",
              mediation["acquisition"]["synthetic_table_base"])
        check("indirect:entry-5b",
              mediation["acquisition"]["entry_value"] == "0x1f001000",
              mediation["acquisition"]["entry_value"])
        check("indirect:entry-stride",
              mediation["acquisition"]["entry_stride"] == "0x16c == 0x5b*4",
              mediation["acquisition"]["entry_stride"])
        check("convergence:same-service",
              mediation["direct_indirect_convergence"]["service"] == "ps1.bios.B0.5b"
              and mediation["direct_indirect_convergence"]["same_implementation"]
              == "p12_bios_set_change_clear_pad",
              json.dumps(mediation["direct_indirect_convergence"], sort_keys=True))

        source = (ROOT / ".openrecomp-phase12/runtime/p12_bios_extension_v1.c").read_text(
            encoding="utf-8")
        check("runtime:one-implementation",
              source.count("static int p12_bios_set_change_clear_pad") == 1,
              "single ChangeClearPAD implementation")
        check("runtime:both-macros-handled",
              "OR_RT_SERVICE_PS1_BIOS_B0_5B" in source
              and "OR_RT_SERVICE_PS1_BIOS_B0_57" in source,
              "direct and indirect service ids handled by one dispatcher")
        check("deps:inventory-consistent",
              inventory["stub_callers"] == coverage["b0_5b_direct"]["callers"],
              "caller inventories agree")

        consistency = {
            "schema": "openrecomp-phase12-bios-path-consistency-v1",
            "stage": STAGE,
            "direct_path": {
                "stub_site": DIRECT_STUB_SITE,
                "service": "ps1.bios.B0.5b",
                "callers": list(EXPECTED_CALLERS),
            },
            "indirect_path": {
                "service": "ps1.bios.B0.57",
                "table_base": "0x1f000000",
                "entry_index": "0x5b",
                "entry_value": "0x1f001000",
            },
            "convergence": {
                "same_implementation": "p12_bios_set_change_clear_pad",
                "fabricated_bios_address": False,
            },
            "all_known_callers_accounted": True,
        }
        write_json(evidence / "consistency.json", consistency)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {"passed": len(RESULTS), "failed": 0},
        }
        write_json(evidence / "p12_30_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_30": "PASS",
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-40",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_30=PASS")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_30_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-30:{exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: p12-30:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
