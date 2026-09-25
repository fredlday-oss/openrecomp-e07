#!/usr/bin/env python3
"""Deterministic P15-08 live frontier replay after bounded MMIO closure."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src", ".openrecomp-phase15/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
import p15_probe_v1 as probe  # noqa: E402
import p15_surface_v1 as surface  # noqa: E402

STAGE = "P15-08"
ENTER_BLOCK = "0x80015f18"
EXIT_BLOCK = "0x80015f28"
ENTRY_BREAK_BLOCK = "0x80013390"


def nonram_denials(parsed: dict) -> int:
    return sum(
        int(count)
        for signature, count in parsed.get("nonram", {}).items()
        if int(signature.rsplit(":", 1)[-1]) != 0
    )


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    result = probe.build_and_run(
        root / ".openrecomp-phase15/build/P15-08", "p15-08",
        block_budget=surface.FRONTIER_BLOCK_BUDGET,
        p15_a0=(0x13, 0x72), p15_b0=surface.P15_B0,
    )
    first, second, simple = result["first"], result["second"], result["simple"]
    parsed = first["parsed"]
    counts = parsed.get("trace_block_counts", {})
    enter_count = int(counts.get(ENTER_BLOCK, 0))
    exit_count = int(counts.get(EXIT_BLOCK, 0))
    break_count = int(counts.get(ENTRY_BREAK_BLOCK, 0))
    denials = nonram_denials(parsed)

    gate.check("replay:build", result["built"]["build_status"] == ["OK", "OK"],
               str(result["built"]["build_status"]))
    gate.check("replay:deterministic", probe.deterministic_match(result),
               first["stdout_sha256"])
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
    gate.check("replay:host-bound-reached",
               simple.get("bound_reached") == "1"
               and simple.get("bound_denials") == "1",
               f"{simple.get('bound_reached')}:{simple.get('bound_denials')}")
    gate.check("frontier:enter-critical-reached", enter_count > 0,
               str(enter_count))
    gate.check("frontier:exit-critical-reached", exit_count > 0,
               str(exit_count))
    gate.check("frontier:balanced", enter_count == exit_count,
               f"{enter_count}:{exit_count}")
    gate.check("frontier:entry-break-not-reached", break_count == 0,
               str(break_count))
    gate.check("frontier:failure-category",
               simple.get("failed") == "1"
               and simple.get("error") == "guest trap is unsupported",
               f"{simple.get('failed')}:{simple.get('error')}")
    gate.check("frontier:live-devices",
               all(int(simple.get(key, "0")) > 0 for key in (
                   "p15_timer1_reads", "p15_frame_tick_reads", "p15_gpustat_reads")),
               ":".join(simple.get(key, "0") for key in (
                   "p15_timer1_reads", "p15_frame_tick_reads", "p15_gpustat_reads")))

    frontier = {
        "schema": "openrecomp-phase15-frontier-ii-v1",
        "stage": STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "fixture": {"sha256": result["image"].file_sha256,
                    "size": result["image"].file_size},
        "build_status": result["built"]["build_status"],
        "run1_sha256": first["stdout_sha256"],
        "run2_sha256": second["stdout_sha256"],
        "byte_identical": probe.deterministic_match(result),
        "block_budget": surface.FRONTIER_BLOCK_BUDGET,
        "block_events": int(simple.get("trace_block_events", "0")),
        "bound_reached": simple.get("bound_reached"),
        "bound_denials": simple.get("bound_denials"),
        "trace_failure_count": int(simple.get("trace_failure_count", "0")),
        "memory_denial_count": denials,
        "unexpected_mmio_count": int(simple.get("p15_mmio_unsupported", "0")),
        "unknown_service_count": int(simple.get("p15_bios_service_failures", "0")),
        "first_remaining_blocker": {
            "kind": "REACHED_BOUNDED_CRITICAL_SECTION_SYSCALLS",
            "enter": {"block": ENTER_BLOCK, "site": "0x80015f1c",
                      "syscall_selector": 1, "count": enter_count},
            "exit": {"block": EXIT_BLOCK, "site": "0x80015f2c",
                     "syscall_selector": 2, "count": exit_count},
            "classification": "PROVEN_BY_FROZEN_TRAP_CLASSIFICATION_AND_LIVE_COUNTS",
            "generic_exception_delivery_required": "NO",
        },
        "boundary": {"kind": "A0:0x43 Exec", "site": "0x80015b84",
                     "title_entry": "0x800380a0", "reached": False,
                     "basis": "critical-section syscall frontier precedes boundary"},
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "frontier_ii.json", frontier)
    assert_public_safe(gate, "frontier-ii", frontier, result["image"].payload)
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1", "stage": STAGE,
        "status": "PASS", "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "markers": {"OPENRECOMP_P15_08": "PASS"},
        "next_stage": "P15-09",
        "next_action": "mediate only syscall selectors 1/2 at their exact proven sites and rerun to the Exec boundary",
    })
    gate.mark("OPENRECOMP_P15_08")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-08"))
