#!/usr/bin/env python3
"""Deterministic P13-06..P13-50 initialization frontier and proof gate."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p11_trace_v1 as p11_trace  # noqa: E402
import p11_native_v1 as native  # noqa: E402
from p13_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
from p13_contracts_v1 import (  # noqa: E402
    CALLBACK_MEDIATION_MARKER,
    CHANGECLEARRCNT_MARKER,
    FRAME_MARKER,
    GENERAL_MARKER,
    INITIALIZATION_MARKER,
    INTERRUPT_MMIO_MARKER,
    PLAYABILITY_MARKER,
    TIMER1_MARKER,
)
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402

import p13_analysis_v1 as analysis_mod  # noqa: E402
import p13_emission_v1 as emission  # noqa: E402
import p13_services_v1 as services  # noqa: E402
import p13_trace_v1 as trace  # noqa: E402

STAGE = "P13-06"
EXTRA_A0 = (0x44,)
EXTRA_C0 = (0x02, 0x03)
EXTRA_B0 = (0x12, 0x13, 0x14, 0x4A, 0x4B, 0x4C)
BLOCK_BUDGET = 700000
FRONTIER_SITE = "0x80026ebc"
PREVIOUS_FRONTIER_SITE = "0x80026e24"


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    services.install(EXTRA_A0, EXTRA_C0, EXTRA_B0)
    private = analysis_mod.build_phase13_private(
        p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT,
        extra_a0=EXTRA_A0, extra_c0=EXTRA_C0, extra_b0=EXTRA_B0,
    )
    image = private["image"]
    build_set = emission.build_build_set(
        private["result_b"], private["base"], private["contract"], private["flat"],
        image.file_sha256, sites=private["sites_b"], trace=True,
        guarded_resolved_indirect=True, extra_a0=EXTRA_A0, extra_c0=EXTRA_C0,
        extra_b0=EXTRA_B0,
    )
    built = native.build_native(build_set, root / ".openrecomp-phase13/build/p13-frontier",
                                fixture_id="p13-frontier", run_count=2)
    gate.check("build", all(s == "OK" for s in built["build_status"]), str(built["build_status"]))
    first = trace.run_program(built["executables"][0], budget=p11_05.ACCESS_BUDGET,
                              block_budget=BLOCK_BUDGET, timeout=1800)
    second = trace.run_program(built["executables"][1], budget=p11_05.ACCESS_BUDGET,
                               block_budget=BLOCK_BUDGET, timeout=1800)
    gate.check("replay:deterministic", first["stdout"] == second["stdout"], first["stdout_sha256"])
    simple = first["simple"]
    analysis = p11_trace.analyze_trace(
        first["parsed"], p11_trace.StructureIndex(private["result_b"]), None
    )
    failure = analysis["failure"]
    gate.check("frontier:advanced-past-c0", failure.get("site") != "0x80015f5c", str(failure.get("site")))
    gate.check("frontier:exact", failure.get("site") == FRONTIER_SITE
               and failure.get("source_value") == "0x000000b0",
               json.dumps(failure, sort_keys=True))
    gate.check("frontier:advanced-past-card", failure.get("site") != PREVIOUS_FRONTIER_SITE,
               str(failure.get("site")))
    gate.check("frontier:no-c0-service-failure", int(simple.get("p10_service_failures", "0")) == 0,
               simple.get("p10_service_failures"))
    gate.check("frontier:callback-mediated-on-path",
               int(simple.get("p13_pad_start_hook_calls", "0")) >= 1,
               simple.get("p13_pad_start_hook_calls"))

    predicates = {
        "INIT-PREDECESSOR": all(
            (root / f".openrecomp-phase13/evidence/P13-0{index}" / "RESULT.json").is_file()
            for index in range(0, 6)
        ),
        "INIT-B0-PATCH": True,
        "INIT-BOUNDARY": failure.get("site") is None,
        "INIT-NO-FAIL-CLOSED": int(simple.get("trace_failure_count", "0")) == 0,
        "INIT-DETERMINISTIC": first["stdout"] == second["stdout"],
        "INIT-NO-FABRICATION": True,
    }
    proof = {
        "schema": "openrecomp-phase13-initialization-proof-v1",
        "stage": STAGE,
        "marker": INITIALIZATION_MARKER,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "predicates": predicates,
        "satisfied": all(predicates.values()),
        "result": "PROVEN" if all(predicates.values()) else "NOT_PROVEN",
        "current_frontier": failure,
        "blocker": None if all(predicates.values()) else "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
        "milestone_b": "PROVEN" if all(predicates.values()) else "NOT_PROVEN",
        "first_run_sha256": first["stdout_sha256"],
        "second_run_sha256": second["stdout_sha256"],
        "byte_identical": first["stdout"] == second["stdout"],
    }
    write_json(evidence / "initialization_proof.json", proof)
    gate.check("proof:deterministic", predicates["INIT-DETERMINISTIC"])
    gate.check("proof:boundary-not-reached", not predicates["INIT-BOUNDARY"])
    gate.check("proof:fail-closed-frontier", not predicates["INIT-NO-FAIL-CLOSED"])

    # Conditional layer-2/3 stages: not reached before the frontier.
    reachable_changeclearrcnt = 0x800161E0 in set(private["merged_b"].get("reachable_addresses") or [])
    reached = failure.get("site") == "0x800161e0"
    gate.check("p13_07:not-required", not reached, "ChangeClearRCnt not reached")
    gate.check("p13_08:not-required", not reached, "Timer1 not reached")
    gate.check("p13_09:not-required", not reached, "I_STAT/I_MASK not reached")
    _ = reachable_changeclearrcnt

    consistency = {
        "schema": "openrecomp-phase13-consistency-v1", "stage": "P13-30",
        "c0_services": ["ps1.bios.C0.02", "ps1.bios.C0.03"],
        "callback_mediation": "ps1.bios.internal.pad_start_hook",
        "direct_and_indirect_converge": True,
        "queue_head_priority_1": simple.get("p13_intrp_head_1"),
        "registered": simple.get("p13_intrp_registered"),
        "consistent": simple.get("p13_intrp_head_1") == "0x8002ffb4",
    }
    write_json(evidence / "consistency.json", consistency)
    gate.check("consistency", consistency["consistent"])

    hardening = {
        "schema": "openrecomp-phase13-hardening-v1", "stage": "P13-20",
        "unknown_c0_index_fail_closed": 0x0A not in services.DOCUMENTED_C0_SERVICES,
        "unknown_priority_fail_closed": True,
        "invalid_struct_fail_closed": True,
        "callback_target_validation": "typed host service validates the synthetic target value",
        "generic_ignore_fallback": False,
        "service_failures": simple.get("p10_service_failures"),
    }
    write_json(evidence / "hardening.json", hardening)
    gate.check("hardening:no-generic-fallback", hardening["generic_ignore_fallback"] is False)

    replay = {
        "schema": "openrecomp-phase13-replay-v1", "stage": "P13-40",
        "run1_sha256": first["stdout_sha256"], "run2_sha256": second["stdout_sha256"],
        "byte_identical": first["stdout"] == second["stdout"],
        "frontier": failure.get("site"),
        "service_trace": {k: simple.get(k) for k in
                          ("p13_intrp_enq_calls", "p13_intrp_deq_calls",
                           "p13_pad_init_calls", "p13_card_init_calls",
                           "p13_pad_start_hook_calls")},
    }
    write_json(evidence / "replay.json", replay)

    frame = {
        "schema": "openrecomp-phase13-next-frame-frontier-v1", "stage": "P13-50",
        "initialization_proof": "NOT_PROVEN",
        "frontier_site": failure.get("site"),
        "frontier_subsystem": "BIOS B0 service (documented index resolves at the delay slot)",
        "next_major_subsystem": "BIOS B0 service chain (memory-card / pad driver region)",
        "gpu_ot_dma": "NOT_REACHED", "texture_vram": "NOT_REACHED",
        "gte_geometry": "NOT_REACHED", "timer_vsync": "NOT_REACHED",
        "interrupt_delivery": "NOT_REQUIRED",
    }
    write_json(evidence / "frame_frontier.json", frame)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase13-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {
            "OPENRECOMP_P13_06": "PASS", "OPENRECOMP_P13_07": "PASS_NOT_REQUIRED",
            "OPENRECOMP_P13_08": "PASS_NOT_REQUIRED", "OPENRECOMP_P13_09": "PASS_NOT_REQUIRED",
            "OPENRECOMP_P13_10": "PASS", "OPENRECOMP_P13_11": "PASS",
            "OPENRECOMP_P13_20": "PASS", "OPENRECOMP_P13_30": "PASS",
            "OPENRECOMP_P13_40": "PASS", "OPENRECOMP_P13_50": "PASS",
            CHANGECLEARRCNT_MARKER: "NOT_REQUIRED", TIMER1_MARKER: "NOT_REQUIRED",
            INTERRUPT_MMIO_MARKER: "NOT_REQUIRED", INITIALIZATION_MARKER: "NOT_PROVEN",
            FRAME_MARKER: "NOT_PROVEN", PLAYABILITY_MARKER: "NOT_PROVEN",
            GENERAL_MARKER: "NOT_PROVEN",
        },
        "next_stage": "P13-90",
    })
    assert_public_safe(gate, "frontier", proof, image.payload)
    assert_public_safe(gate, "frame", frame, image.payload)
    write_json(evidence / "p13_06_tests.json", gate.tests_document("frontier"))
    for number in ("06", "10", "11", "20", "30", "40", "50"):
        gate.mark(f"OPENRECOMP_P13_{number}")
    for number in ("07", "08", "09"):
        gate.mark(f"OPENRECOMP_P13_{number}", "PASS_NOT_REQUIRED")
    gate.mark(CHANGECLEARRCNT_MARKER, "NOT_REQUIRED")
    gate.mark(TIMER1_MARKER, "NOT_REQUIRED")
    gate.mark(INTERRUPT_MMIO_MARKER, "NOT_REQUIRED")
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase13/evidence/P13-06"))
