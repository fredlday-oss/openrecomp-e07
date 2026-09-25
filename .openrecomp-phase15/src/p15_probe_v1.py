#!/usr/bin/env python3
"""OpenRecomp Phase-15 private initialization probe V1.

Builds and runs the frozen private Hercules initialization path with the
canonical Phase-15 MMIO surface, twice, under explicit deterministic budgets. No
private payload is returned; only non-reconstructive observables.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src", ".openrecomp-phase15/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p11_native_v1 as native  # noqa: E402
import p11_trace_v1 as p11_trace  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402

import p15_analysis_v1 as analysis_mod  # noqa: E402
import p15_emission_v1 as emission  # noqa: E402
import p15_surface_v1 as surface  # noqa: E402
import p15_trace_v1 as trace  # noqa: E402

PROBE_VERSION = "1.0.0"

DEFAULT_FIXTURE_ROOT = p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT
ACCESS_BUDGET = p11_05.ACCESS_BUDGET

DETERMINISTIC_KEYS = (
    "failed", "error", "exit_status", "registers", "memory",
    "gpu_events", "gpu", "input_events", "input", "spu_events", "spu",
    "cdrom_events", "cdrom", "reads", "writes", "denied", "host_calls",
    "p10_access_budget", "p10_access_count", "p10_budget_denials",
    "p10_service_calls", "p10_service_failures",
    "nonram_signatures", "nonram_overflow",
    "trace_block_events", "trace_function_events", "trace_block_digest",
    "trace_distinct_blocks", "trace_distinct_functions", "trace_failure_count",
    "bound_reached", "bound_denials",
    "p15_i_stat", "p15_i_mask", "p15_sys_control", "p15_d2_chcr",
    "p15_mmio_reads", "p15_mmio_writes", "p15_mmio_digest",
    "p15_timer1_count", "p15_timer1_mode", "p15_timer1_reads",
    "p15_timer1_mode_writes", "p15_frame_tick_reads", "p15_frame_tick_value",
    "p15_gpustat_reads",
    "p15_enter_critical_calls", "p15_exit_critical_calls",
    "p15_critical_syscall_failures", "p15_cpu_interrupt_enabled",
)


def build_and_run(
    build_root: pathlib.Path,
    tag: str,
    *,
    fixture_root: pathlib.Path | None = None,
    block_budget: int = surface.FRONTIER_BLOCK_BUDGET,
    access_budget: int = ACCESS_BUDGET,
    timeout: int = 2400,
    p15_a0: tuple[int, ...] = (),
    p15_b0: tuple[int, ...] = (),
) -> dict[str, Any]:
    """Build and run the Phase-15 initialization-path private program twice."""
    fixture_root = fixture_root or DEFAULT_FIXTURE_ROOT
    private = analysis_mod.build_phase15_private(
        fixture_root, extra_a0=surface.EXTRA_A0, extra_c0=surface.EXTRA_C0,
        extra_b0=surface.EXTRA_B0, p14_b0=surface.P14_B0, p14_a0=surface.P14_A0,
        p15_a0=p15_a0, p15_b0=p15_b0, internal_targets=surface.INTERNAL_TARGETS,
    )
    image = private["image"]
    build_set = emission.build_build_set(
        private["result_b"], private["base"], private["contract"], private["flat"],
        image.file_sha256, sites=private["sites_b"], trace=True,
        guarded_resolved_indirect=True, extra_a0=surface.EXTRA_A0,
        extra_c0=surface.EXTRA_C0, extra_b0=surface.EXTRA_B0,
        p14_b0=surface.P14_B0, p14_a0=surface.P14_A0, p15_a0=p15_a0, p15_b0=p15_b0,
    )
    built = native.build_native(
        build_set, build_root / tag, fixture_id=tag, run_count=2,
    )
    first = trace.run_program(built["executables"][0], budget=access_budget,
                              block_budget=block_budget, timeout=timeout)
    second = trace.run_program(built["executables"][1], budget=access_budget,
                               block_budget=block_budget, timeout=timeout)
    analysis = p11_trace.analyze_trace(
        first["parsed"], p11_trace.StructureIndex(private["result_b"]), None
    )
    return {
        "private": private,
        "build_set": build_set,
        "built": built,
        "first": first,
        "second": second,
        "simple": first["simple"],
        "analysis": analysis,
        "failure": analysis["failure"],
        "image": image,
    }


def deterministic_match(result: dict[str, Any]) -> bool:
    return result["first"]["stdout"] == result["second"]["stdout"]
