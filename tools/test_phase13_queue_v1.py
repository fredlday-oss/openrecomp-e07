#!/usr/bin/env python3
"""Deterministic P13-01..P13-05 C0 queue / round-trip / callback gate."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_emission_v1 as p9_emission  # noqa: E402
import p11_native_v1 as native  # noqa: E402
import p11_trace_v1 as p11_trace  # noqa: E402
from p13_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
from p13_contracts_v1 import (  # noqa: E402
    CALLBACK_MEDIATION_MARKER,
    FRAME_MARKER,
    GENERAL_MARKER,
    INITIALIZATION_MARKER,
    INTRP_ROUNDTRIP_MARKER,
    PLAYABILITY_MARKER,
    SYSDEQINTRP_MARKER,
    SYSENQINTRP_MARKER,
)
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402

import p13_analysis_v1 as analysis_mod  # noqa: E402
import p13_emission_v1 as emission  # noqa: E402
import p13_pad_hook_v1 as pad_hook  # noqa: E402
import p13_services_v1 as services  # noqa: E402
import p13_trace_v1 as trace  # noqa: E402

STAGE = "P13-01"
EXTRA_A0 = (0x44,)
EXTRA_C0 = (0x02, 0x03)
EXTRA_B0 = (0x12, 0x13, 0x14, 0x4A, 0x4B, 0x4C)
BLOCK_BUDGET = 700000


def _numeric_ids(record):
    if isinstance(record, dict):
        if "service_numeric_ids" in record:
            return record["service_numeric_ids"]
        for value in record.values():
            found = _numeric_ids(value)
            if found:
                return found
    return None


def direct_driver(c0_02: int, c0_03: int) -> str:
    return f'''#include <stdint.h>
#include <stdio.h>
void p9_runtime_init(void);
int or_rt_host_call(uint64_t, uint32_t, const uint64_t *, uint64_t *);
uint64_t p10_runtime_mips_service_calls(void);
uint64_t p10_runtime_mips_service_failures(void);
int main(void)
{{
    uint64_t args[2];
    uint64_t out = UINT64_C(0);
    int s;
    p9_runtime_init();
    args[0] = UINT64_C(1); args[1] = UINT64_C(0x8002ffb4);
    s = or_rt_host_call(UINT64_C({c0_02}), 2u, args, &out);
    printf("enq_status=%d\\n", s);
    s = or_rt_host_call(UINT64_C({c0_02}), 2u, args, &out);
    printf("enq_duplicate_status=%d\\n", s);
    s = or_rt_host_call(UINT64_C({c0_03}), 2u, args, &out);
    printf("deq_status=%d\\n", s);
    printf("deq_out=0x%08x\\n", (unsigned)out);
    s = or_rt_host_call(UINT64_C({c0_03}), 2u, args, &out);
    printf("deq_empty_status=%d\\n", s);
    printf("deq_empty_out=0x%08x\\n", (unsigned)out);
    args[0] = UINT64_C(9); args[1] = UINT64_C(0x8002ffb4);
    s = or_rt_host_call(UINT64_C({c0_02}), 2u, args, &out);
    printf("enq_bad_priority_status=%d\\n", s);
    args[0] = UINT64_C(1); args[1] = UINT64_C(0);
    s = or_rt_host_call(UINT64_C({c0_02}), 2u, args, &out);
    printf("enq_null_struct_status=%d\\n", s);
    s = or_rt_host_call(UINT64_C({c0_02}), 1u, args, &out);
    printf("enq_arity_status=%d\\n", s);
    printf("service_calls=%llu\\n", (unsigned long long)p10_runtime_mips_service_calls());
    printf("service_failures=%llu\\n", (unsigned long long)p10_runtime_mips_service_failures());
    return 0;
}}
'''


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    tables = services.install(EXTRA_A0, EXTRA_C0, EXTRA_B0)
    gate.check("surface:enq", tables["C0"][0x02]["name"] == "SysEnqIntRP"
               and tables["C0"][0x02]["signature"] == ["priority", "struc"], "")
    gate.check("surface:deq", tables["C0"][0x03]["name"] == "SysDeqIntRP"
               and tables["C0"][0x03]["signature"] == ["priority", "struc"], "")
    gate.check("surface:c0-index-0a-fail-closed", 0x0A not in tables["C0"], "")

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
    service_ids = build_set["semantics"]["service_ids"]
    for marker, service in ((SYSENQINTRP_MARKER, "ps1.bios.C0.02"),
                            (SYSDEQINTRP_MARKER, "ps1.bios.C0.03"),
                            (CALLBACK_MEDIATION_MARKER, "ps1.bios.internal.pad_start_hook")):
        gate.check(f"semantics:{service}", service in service_ids, ",".join(service_ids))
    rules = build_set["semantics"]["pad_hook_rules"]
    gate.check("semantics:pad-hook-rule", any(
        item["service"] == "ps1.bios.internal.pad_start_hook"
        and item["flow"] == "INDIRECT_JUMP" and item["args"] == [pad_hook.PAD_HOOK_FIELD]
        and item["result"] is None for item in rules), str(rules))

    c0_sites = [item for item in private["site_document_b"]["sites"] if item["vector"] == "C0"]
    resolved = {item["site"]: item["service_id"] for item in c0_sites
                if item["service_id"] is not None}
    gate.check("classify:c0-02-03-resolved",
               resolved.get(0x80015F4C) == "ps1.bios.C0.02"
               and resolved.get(0x80015F5C) == "ps1.bios.C0.03", str(sorted(resolved.items())))
    gate.check("classify:c0-0a-fail-closed",
               all(item["service_id"] is None and item["disposition"] == "FAIL_CLOSED"
                   for item in c0_sites if item["function_index"] == 0x0A), "")

    built = native.build_native(build_set, root / ".openrecomp-phase13/build/p13-queue",
                                fixture_id="p13-queue", run_count=2)
    gate.check("private:build", all(s == "OK" for s in built["build_status"]), str(built["build_status"]))
    first = trace.run_program(built["executables"][0], budget=p11_05.ACCESS_BUDGET,
                              block_budget=BLOCK_BUDGET, timeout=1800)
    second = trace.run_program(built["executables"][1], budget=p11_05.ACCESS_BUDGET,
                               block_budget=BLOCK_BUDGET, timeout=1800)
    gate.check("private:deterministic", first["stdout"] == second["stdout"], first["stdout_sha256"])
    simple = first["simple"]
    gate.check("intrp:enq", int(simple.get("p13_intrp_enq_calls", "0")) >= 1, simple.get("p13_intrp_enq_calls"))
    gate.check("intrp:deq", int(simple.get("p13_intrp_deq_calls", "0")) >= 1, simple.get("p13_intrp_deq_calls"))
    gate.check("intrp:empty-deq-returns-zero", simple.get("p13_intrp_deq_result") == "0x00000000",
               simple.get("p13_intrp_deq_result"))
    gate.check("intrp:registered", int(simple.get("p13_intrp_registered", "0")) >= 1,
               simple.get("p13_intrp_registered"))
    gate.check("intrp:head-priority-1", simple.get("p13_intrp_head_1") == "0x8002ffb4",
               simple.get("p13_intrp_head_1"))
    gate.check("callback:func1-provenance", simple.get("p13_intrp_func1") == "0x80015e98",
               simple.get("p13_intrp_func1"))
    gate.check("callback:func2-provenance", simple.get("p13_intrp_func2") == "0x80015e30",
               simple.get("p13_intrp_func2"))
    gate.check("callback:pad-start-hook-mediated",
               int(simple.get("p13_pad_start_hook_calls", "0")) >= 1
               and simple.get("p13_pad_start_hook_last_target") == "0x1f001884",
               f"{simple.get('p13_pad_start_hook_calls')}:{simple.get('p13_pad_start_hook_last_target')}")
    gate.check("callback:stop-hook-not-required", simple.get("p13_pad_stop_hook_calls") == "0",
               simple.get("p13_pad_stop_hook_calls"))
    gate.check("fail-closed:no-service-failures", int(simple.get("p10_service_failures", "0")) == 0,
               simple.get("p10_service_failures"))

    observation = {
        "schema": "openrecomp-phase13-c0-observation-v1", "stage": STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "intrp": {key: simple.get(f"p13_intrp_{key}") for key in
                  ("enq_calls", "deq_calls", "registered", "last_priority", "last_struct",
                   "deq_result", "head_0", "head_1", "head_2", "head_3", "func1", "func2")},
        "callback": {key: simple.get(f"p13_pad_{key}") for key in
                     ("start_hook_calls", "start_hook_last_target", "stop_hook_calls")},
        "pad": {key: simple.get(f"p13_pad_{key}") for key in
                ("buf1", "siz1", "buf2", "siz2", "enable", "started")},
        "card": {key: simple.get(f"p13_card_{key}") for key in
                 ("pad_enable", "started", "init_calls", "start_calls", "stop_calls")},
        "frontier": first["parsed"].get("trace_failure_site"),
        "callback_mediation": pad_hook.document(),
    }
    write_json(evidence / "c0_observation.json", observation)
    assert_public_safe(gate, "observation", observation, image.payload)

    numeric = _numeric_ids(build_set["runtime_composition"])
    gate.check("dispatch:ids", numeric and "ps1.bios.C0.02" in numeric
               and "ps1.bios.C0.03" in numeric, str(sorted((numeric or {}).keys())))
    direct_set = dict(build_set)
    direct_set["files"] = dict(build_set["files"])
    direct_set["files"][emission.DRIVER_NAME] = (
        p9_emission.render_image_header(private["contract"]) + "\n"
        + direct_driver(numeric["ps1.bios.C0.02"], numeric["ps1.bios.C0.03"])
    )
    direct_build = native.build_native(direct_set, root / ".openrecomp-phase13/build/p13-queue-direct",
                                       fixture_id="p13-queue-direct", run_count=2)
    gate.check("dispatch:build", all(s == "OK" for s in direct_build["build_status"]),
               str(direct_build["build_status"]))
    direct = trace.run_program(direct_build["executables"][0], timeout=300)["simple"]
    gate.check("dispatch:enqueue", direct.get("enq_status") == "0", direct.get("enq_status"))
    gate.check("dispatch:duplicate-rejected", direct.get("enq_duplicate_status") == "13",
               direct.get("enq_duplicate_status"))
    gate.check("dispatch:dequeue", direct.get("deq_status") == "0"
               and direct.get("deq_out") == "0x8002ffb4",
               f"{direct.get('deq_status')}:{direct.get('deq_out')}")
    gate.check("dispatch:empty-dequeue", direct.get("deq_empty_status") == "0"
               and direct.get("deq_empty_out") == "0x00000000",
               f"{direct.get('deq_empty_status')}:{direct.get('deq_empty_out')}")
    gate.check("dispatch:bad-priority-rejected", direct.get("enq_bad_priority_status") == "13",
               direct.get("enq_bad_priority_status"))
    gate.check("dispatch:null-struct-rejected", direct.get("enq_null_struct_status") == "13",
               direct.get("enq_null_struct_status"))
    gate.check("dispatch:arity-rejected", direct.get("enq_arity_status") == "13",
               direct.get("enq_arity_status"))
    gate.check("dispatch:failures", direct.get("service_failures") == "4",
               direct.get("service_failures"))
    write_json(evidence / "dispatch.json", {
        "schema": "openrecomp-phase13-c0-dispatch-v1", "stage": STAGE,
        "result": direct, "evidence_class": "PUBLIC_SYNTHETIC",
    })
    assert_public_safe(gate, "dispatch", direct, image.payload)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase13-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P13_01": "PASS", "OPENRECOMP_P13_02": "PASS",
                    "OPENRECOMP_P13_03": "PASS", "OPENRECOMP_P13_04": "PASS",
                    "OPENRECOMP_P13_05": "PASS", SYSENQINTRP_MARKER: "PASS",
                    SYSDEQINTRP_MARKER: "PASS", INTRP_ROUNDTRIP_MARKER: "PASS",
                    CALLBACK_MEDIATION_MARKER: "PASS", INITIALIZATION_MARKER: "NOT_PROVEN",
                    FRAME_MARKER: "NOT_PROVEN", PLAYABILITY_MARKER: "NOT_PROVEN",
                    GENERAL_MARKER: "NOT_PROVEN"},
        "next_stage": "P13-06",
    })
    write_json(evidence / "p13_01_tests.json", gate.tests_document("queue"))
    for number in ("01", "02", "03", "04", "05"):
        gate.mark(f"OPENRECOMP_P13_{number}")
    gate.mark(SYSENQINTRP_MARKER)
    gate.mark(SYSDEQINTRP_MARKER)
    gate.mark(INTRP_ROUNDTRIP_MARKER)
    gate.mark(CALLBACK_MEDIATION_MARKER)
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase13/evidence/P13-01"))
