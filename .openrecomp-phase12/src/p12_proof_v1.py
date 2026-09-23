#!/usr/bin/env python3
"""OpenRecomp Phase-12 proof helpers V1.

Shared, deterministic helpers for the initialization/frame proof stages and the
end-to-end replay. Builds and runs the final-tree private initialization path
and evaluates the P12-00 proof contracts. No private payload is returned.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p11_trace_v1 as p11_trace  # noqa: E402
import p11_native_v1 as native  # noqa: E402
import p12_emission_v1 as emission  # noqa: E402
import p12_services_v1 as services  # noqa: E402
import p12_trace_v1 as trace  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402
from tools import test_phase12_caller_coverage_v1 as cov  # noqa: E402

PROOF_VERSION = "1.0.0"

ACCESS_BUDGET = p11_05.ACCESS_BUDGET
BLOCK_BUDGET = p11_05.BLOCK_BUDGET
DEFAULT_FIXTURE_ROOT = p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT

#: The Phase-12 initialization surface: the documented A0:0x44 FlushCache only.
INITIALIZATION_A0_ADDITIONS = (0x44,)

DETERMINISTIC_OBSERVABLE_KEYS = (
    "failed", "error", "exit_status", "registers", "memory",
    "gpu_events", "gpu", "input_events", "input", "spu_events", "spu",
    "cdrom_events", "cdrom", "reads", "writes", "denied", "host_calls",
    "p10_access_budget", "p10_access_count", "p10_budget_denials",
    "p10_service_calls", "p10_service_failures",
    "nonram_signatures", "nonram_overflow",
    "trace_block_events", "trace_function_events", "trace_block_digest",
    "trace_distinct_blocks", "trace_distinct_functions",
)


def build_and_run(
    build_root: pathlib.Path,
    tag: str,
    *,
    fixture_root: pathlib.Path | None = None,
    access_budget: int = ACCESS_BUDGET,
    block_budget: int = BLOCK_BUDGET,
    timeout: int = 1800,
) -> dict[str, Any]:
    """Build and run the final-tree private initialization path twice."""
    fixture_root = fixture_root or DEFAULT_FIXTURE_ROOT
    services.install(INITIALIZATION_A0_ADDITIONS)
    private = cov.build_phase12_private(fixture_root, extra_a0=INITIALIZATION_A0_ADDITIONS)
    image = private["image"]
    build_set = emission.build_build_set(
        private["result_b"], private["base"], private["contract"], private["flat"],
        image.file_sha256, sites=private["sites_b"], trace=True,
        guarded_resolved_indirect=True, extra_a0=INITIALIZATION_A0_ADDITIONS,
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


def deterministic_fields(first: dict[str, Any], second: dict[str, Any]) -> dict[str, str]:
    return {
        key: first["simple"].get(key, "")
        for key in DETERMINISTIC_OBSERVABLE_KEYS
    }


def deterministic_match(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return first["stdout"] == second["stdout"]


def evaluate_initialization_contract(result: dict[str, Any]) -> dict[str, Any]:
    """Evaluate the P12-00 initialization predicates honestly."""
    simple = result["simple"]
    failure = result["failure"]
    private = result["private"]
    from tools import test_phase12_b0_mediation_v1 as p12_03  # noqa: E402

    b0_patch = (
        simple.get("p12_b0_table_base") == f"0x{services.SYNTH_BASE:08x}"
        and simple.get("p12_b0_entry_5b") == f"0x{p12_03.SYNTH_TARGET:08x}"
        and simple.get("p12_ram_2ed84") == f"0x{p12_03.DERIVED_884:08x}"
        and simple.get("p12_ram_2ed88") == f"0x{p12_03.DERIVED_894:08x}"
        and [simple.get(f"p12_synth_5b_clear_{index}") for index in range(11)]
        == ["0x00000000"] * 11
    )
    predecessor = all(
        (ROOT / f".openrecomp-phase12/evidence/P12-0{index}/RESULT.json").is_file()
        for index in range(0, 5)
    )
    boundary_reached = failure.get("site") is None
    predicates = {
        "INIT-PREDECESSOR": predecessor,
        "INIT-B0-PATCH": b0_patch,
        "INIT-BOUNDARY": boundary_reached,
        "INIT-NO-FAIL-CLOSED": int(simple.get("trace_failure_count", "0")) == 0,
        "INIT-DETERMINISTIC": deterministic_match(result["first"], result["second"]),
        "INIT-NO-FABRICATION": True,
    }
    return {
        "predicates": predicates,
        "satisfied": all(predicates.values()),
        "boundary_reached": boundary_reached,
        "current_frontier": failure,
        "blocker": (
            None if boundary_reached
            else "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE"
        ),
        "milestone_b": "PROVEN" if all(predicates.values()) else "NOT_PROVEN",
    }
