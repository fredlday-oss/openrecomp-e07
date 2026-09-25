#!/usr/bin/env python3
"""Deterministic P15-40 initialization replay gate.

Runs the bounded Hercules initialization replay twice through the complete
Phase-15 mediated MMIO, BIOS, and critical-section syscall runtime under
explicit deterministic block budgets.
Requires byte-identical stdout across dual runs, clean exit, zero stderr,
zero non-RAM memory denials, zero unhandled MMIO accesses, zero BIOS service
failures, and zero critical syscall failures.
Markers emitted:
  OPENRECOMP_P15_40=PASS
  OPENRECOMP_PHASE15_INITIALIZATION_REPLAY_V1=PASS
  OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
  OPENRECOMP_PHASE15_HERCULES_FRAME_PROOF=NOT_PROVEN
  OPENRECOMP_PHASE15_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
  OPENRECOMP_PHASE15_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

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
    INITIALIZATION_REPLAY_MARKER,
    PLAYABILITY_MARKER,
)
from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
import p15_probe_v1 as probe  # noqa: E402
import p15_surface_v1 as surface  # noqa: E402

STAGE = "P15-40"


def nonram_denials(parsed: dict) -> int:
    return sum(
        int(count)
        for signature, count in parsed.get("nonram", {}).items()
        if int(signature.rsplit(":", 1)[-1]) != 0
    )


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 1. Execute live initialization replay twice
    result = probe.build_and_run(
        root / ".openrecomp-phase15/build/P15-40", "p15-40",
        block_budget=surface.FRONTIER_BLOCK_BUDGET,
        p15_a0=(0x13, 0x72), p15_b0=surface.P15_B0,
    )
    first, second, simple = result["first"], result["second"], result["simple"]
    parsed = first["parsed"]
    denials = nonram_denials(parsed)
    critical_failures = int(simple.get("p15_critical_syscall_failures", 0))
    enter_count = int(simple.get("p15_enter_critical_calls", 0))
    exit_count = int(simple.get("p15_exit_critical_calls", 0))
    cpu_ie = int(simple.get("p15_cpu_interrupt_enabled", 0))

    # 2. Gate checks
    gate.check("replay:build", result["built"]["build_status"] == ["OK", "OK"],
               str(result["built"]["build_status"]))
    gate.check("replay:deterministic-match", probe.deterministic_match(result),
               first["stdout_sha256"])
    gate.check("replay:stdout-identical", first["stdout"] == second["stdout"],
               f"sha256={first['stdout_sha256']}")
    gate.check("replay:stderr-empty",
               first["stderr_bytes"] == 0 and second["stderr_bytes"] == 0,
               f"{first['stderr_bytes']}:{second['stderr_bytes']}")
    gate.check("replay:trace-indirect-clean",
               simple.get("trace_failure_count") == "0",
               simple.get("trace_failure_count"))
    gate.check("replay:nonram-denials-zero", denials == 0, str(denials))
    gate.check("replay:mmio-unsupported-zero",
               simple.get("p15_mmio_unsupported") == "0",
               simple.get("p15_mmio_unsupported"))
    gate.check("replay:bios-failures-zero",
               simple.get("p15_bios_service_failures") == "0",
               simple.get("p15_bios_service_failures"))
    gate.check("replay:critical-failures-zero", critical_failures == 0,
               str(critical_failures))
    gate.check("replay:critical-balanced", enter_count == exit_count and enter_count == 7,
               f"{enter_count}:{exit_count}")
    gate.check("replay:cpu-interrupt-enabled", cpu_ie == 1, str(cpu_ie))
    gate.check("replay:host-bound-reached",
               simple.get("bound_reached") == "1" and simple.get("bound_denials") == "1",
               f"{simple.get('bound_reached')}:{simple.get('bound_denials')}")

    observations = {
        key: simple.get(key)
        for key in probe.DETERMINISTIC_KEYS
        if key in simple
    }

    replay_doc = {
        "schema": "openrecomp-phase15-initialization-replay-v1",
        "stage": STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "fixture": {
            "sha256": result["image"].file_sha256,
            "size": result["image"].file_size,
        },
        "build_status": result["built"]["build_status"],
        "run1_sha256": first["stdout_sha256"],
        "run2_sha256": second["stdout_sha256"],
        "byte_identical": probe.deterministic_match(result),
        "block_budget": surface.FRONTIER_BLOCK_BUDGET,
        "observables": observations,
        "fail_closed_discipline": "STRICT_NO_SUPPRESSION",
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "replay.json", replay_doc)
    assert_public_safe(gate, "replay", replay_doc, result["image"].payload)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "markers": {
            "OPENRECOMP_P15_40": "PASS",
            INITIALIZATION_REPLAY_MARKER: "PASS",
            INITIALIZATION_MARKER: "NOT_PROVEN",
            FRAME_MARKER: "NOT_PROVEN",
            PLAYABILITY_MARKER: "NOT_PROVEN",
            GENERAL_MARKER: "NOT_PROVEN",
        },
        "next_stage": "P15-50",
        "next_action": "advance to Stage P15-50 first-frame readiness assessment",
    })
    gate.mark("OPENRECOMP_P15_40")
    gate.mark(INITIALIZATION_REPLAY_MARKER)
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-40"))
