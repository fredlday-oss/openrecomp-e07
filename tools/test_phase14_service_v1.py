#!/usr/bin/env python3
"""Deterministic P14-01..P14-04 B0:0x56 / C0 surface / continuation gate.

The runtime services are exercised through a public direct-dispatch driver that
links the real composed support translation unit, so the emitted service macros
and the native dispatcher are validated exactly. The actual guest patch
dataflow is validated by the frontier gate (P14-03).
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_emission_v1 as p9_emission  # noqa: E402
import p11_native_v1 as native  # noqa: E402
from p14_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
from p14_contracts_v1 import (  # noqa: E402
    B0_56_MARKER,
    C0_TABLE_MARKER,
    CARD_CONTINUATION_MARKER,
    FRAME_MARKER,
    GENERAL_MARKER,
    INITIALIZATION_MARKER,
    PLAYABILITY_MARKER,
)
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402

import p14_analysis_v1 as analysis_mod  # noqa: E402
import p14_c0_surface_v1 as c0_surface  # noqa: E402
import p14_closure_surface_v1 as surface  # noqa: E402
import p14_emission_v1 as emission  # noqa: E402
import p14_trace_v1 as trace  # noqa: E402

STAGE = "P14-01"


def _numeric_ids(record):
    if isinstance(record, dict):
        if "service_numeric_ids" in record:
            return record["service_numeric_ids"]
        for value in record.values():
            found = _numeric_ids(value)
            if found:
                return found
    return None


def direct_driver(ids: dict[str, int]) -> str:
    b0_56 = ids["ps1.bios.B0.56"]
    cont = ids["ps1.bios.internal.card_continuation"]
    a0_70 = ids["ps1.bios.A0.70"]
    a0_30 = ids["ps1.bios.A0.30"]
    b0_3f = ids["ps1.bios.B0.3f"]
    return f'''#include <stdint.h>
#include <stdio.h>
void p9_runtime_init(void);
int or_rt_host_call(uint64_t, uint32_t, const uint64_t *, uint64_t *);
int or_rt_memory_write(uint64_t, uint32_t, uint64_t);
uint64_t p10_runtime_mips_service_calls(void);
uint64_t p10_runtime_mips_service_failures(void);
extern uint32_t p12_synth_read32(uint32_t offset);
int main(void)
{{
    uint64_t args[2];
    uint64_t out = UINT64_C(0);
    int s;
    uint32_t hi, lo, handler, c06;
    p9_runtime_init();
    s = or_rt_host_call(UINT64_C({b0_56}), 0u, NULL, &out);
    printf("getc0_status=%d\\n", s);
    printf("getc0_out=0x%08x\\n", (unsigned)out);
    c06 = p12_synth_read32(0x818u);
    hi = p12_synth_read32(0x1870u);
    lo = p12_synth_read32(0x1874u);
    handler = ((hi & 0xffffu) << 16) | (lo & 0xffffu);
    printf("c0_slot6=0x%08x\\n", (unsigned)c06);
    printf("c0_handler=0x%08x\\n", (unsigned)handler);
    args[0] = UINT64_C(1);
    s = or_rt_host_call(UINT64_C({b0_56}), 1u, args, &out);
    printf("getc0_arity_status=%d\\n", s);

    args[0] = UINT64_C(0x1f00193c);
    s = or_rt_host_call(UINT64_C({cont}), 1u, args, &out);
    printf("cont_status=%d\\n", s);
    args[0] = UINT64_C(0x1f001928);
    s = or_rt_host_call(UINT64_C({cont}), 1u, args, &out);
    printf("cont_bad_status=%d\\n", s);
    s = or_rt_host_call(UINT64_C({cont}), 0u, NULL, &out);
    printf("cont_arity_status=%d\\n", s);

    s = or_rt_host_call(UINT64_C({a0_70}), 0u, NULL, &out);
    printf("bu_status=%d\\n", s);
    printf("bu_out=0x%08x\\n", (unsigned)out);
    s = or_rt_host_call(UINT64_C({a0_70}), 1u, args, &out);
    printf("bu_arity_status=%d\\n", s);

    args[0] = UINT64_C(0xfffffffb);
    s = or_rt_host_call(UINT64_C({a0_30}), 1u, args, &out);
    printf("abs_neg_status=%d\\n", s);
    printf("abs_neg_out=0x%08x\\n", (unsigned)out);
    args[0] = UINT64_C(7);
    s = or_rt_host_call(UINT64_C({a0_30}), 1u, args, &out);
    printf("abs_pos_status=%d\\n", s);
    printf("abs_pos_out=0x%08x\\n", (unsigned)out);
    s = or_rt_host_call(UINT64_C({a0_30}), 0u, NULL, &out);
    printf("abs_arity_status=%d\\n", s);

    or_rt_memory_write(UINT64_C(0x80030000), 8u, UINT64_C(104));
    or_rt_memory_write(UINT64_C(0x80030001), 8u, UINT64_C(105));
    or_rt_memory_write(UINT64_C(0x80030002), 8u, UINT64_C(0));
    args[0] = UINT64_C(0x80030000);
    s = or_rt_host_call(UINT64_C({b0_3f}), 1u, args, &out);
    printf("puts_status=%d\\n", s);
    args[0] = UINT64_C(0);
    s = or_rt_host_call(UINT64_C({b0_3f}), 1u, args, &out);
    printf("puts_null_status=%d\\n", s);
    args[0] = UINT64_C(0xbfc00000);
    s = or_rt_host_call(UINT64_C({b0_3f}), 1u, args, &out);
    printf("puts_oob_status=%d\\n", s);
    s = or_rt_host_call(UINT64_C({b0_3f}), 0u, NULL, &out);
    printf("puts_arity_status=%d\\n", s);

    s = or_rt_host_call(UINT64_C(0xffffffff), 0u, NULL, &out);
    printf("unknown_status=%d\\n", s);
    printf("service_calls=%llu\\n", (unsigned long long)p10_runtime_mips_service_calls());
    printf("service_failures=%llu\\n", (unsigned long long)p10_runtime_mips_service_failures());
    return 0;
}}
'''


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    private = analysis_mod.build_phase14_private(
        p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT, extra_a0=surface.EXTRA_A0,
        extra_c0=surface.EXTRA_C0, extra_b0=surface.EXTRA_B0,
        p14_b0=surface.P14_B0, p14_a0=surface.P14_A0,
        internal_targets=surface.INTERNAL_TARGETS,
    )
    image = private["image"]
    build_set = emission.build_build_set(
        private["result_b"], private["base"], private["contract"], private["flat"],
        image.file_sha256, sites=private["sites_b"], trace=True,
        guarded_resolved_indirect=True, extra_a0=surface.EXTRA_A0,
        extra_c0=surface.EXTRA_C0, extra_b0=surface.EXTRA_B0,
        p14_b0=surface.P14_B0, p14_a0=surface.P14_A0,
    )
    ids = _numeric_ids(build_set["runtime_composition"])
    for service in ("ps1.bios.B0.56", "ps1.bios.internal.card_continuation",
                    "ps1.bios.A0.70", "ps1.bios.A0.30", "ps1.bios.B0.3f",
                    "ps1.mips.mflo"):
        gate.check(f"dispatch:id:{service}", service in ids, str(sorted(ids.keys())))

    direct_set = dict(build_set)
    direct_set["files"] = dict(build_set["files"])
    direct_set["files"][emission.DRIVER_NAME] = (
        p9_emission.render_image_header(private["contract"]) + "\n" + direct_driver(ids)
    )
    built = native.build_native(direct_set, root / ".openrecomp-phase14/build/p14-service",
                                fixture_id="p14-service", run_count=2)
    gate.check("dispatch:build", all(s == "OK" for s in built["build_status"]),
               str(built["build_status"]))
    first = trace.run_program(built["executables"][0], timeout=600)
    second = trace.run_program(built["executables"][1], timeout=600)
    gate.check("dispatch:deterministic", first["stdout"] == second["stdout"],
               first["stdout_sha256"])
    d = first["simple"]

    gate.check("getc0:status", d.get("getc0_status") == "0", d.get("getc0_status"))
    gate.check("getc0:pointer", d.get("getc0_out") == f"0x{surface.c0_surface.addresses()['c0_table']:08x}",
               d.get("getc0_out"))
    gate.check("c0:slot6", d.get("c0_slot6") == f"0x{surface.c0_surface.addresses()['exception_handler']:08x}",
               d.get("c0_slot6"))
    gate.check("c0:reconstruct-handler",
               d.get("c0_handler") == f"0x{surface.c0_surface.addresses()['early_handler']:08x}",
               d.get("c0_handler"))
    gate.check("getc0:arity-refused", d.get("getc0_arity_status") == "13", d.get("getc0_arity_status"))

    gate.check("continuation:accepted", d.get("cont_status") == "0", d.get("cont_status"))
    gate.check("continuation:arbitrary-refused", d.get("cont_bad_status") == "13",
               d.get("cont_bad_status"))
    gate.check("continuation:arity-refused", d.get("cont_arity_status") == "13",
               d.get("cont_arity_status"))

    gate.check("bu_init:status", d.get("bu_status") == "0" and d.get("bu_out") == "0x00000000",
               f"{d.get('bu_status')}:{d.get('bu_out')}")
    gate.check("bu_init:arity-refused", d.get("bu_arity_status") == "13", d.get("bu_arity_status"))
    gate.check("abs:negative", d.get("abs_neg_status") == "0" and d.get("abs_neg_out") == "0x00000005",
               f"{d.get('abs_neg_status')}:{d.get('abs_neg_out')}")
    gate.check("abs:positive", d.get("abs_pos_out") == "0x00000007", d.get("abs_pos_out"))
    gate.check("abs:arity-refused", d.get("abs_arity_status") == "13", d.get("abs_arity_status"))
    gate.check("puts:accepted", d.get("puts_status") == "0", d.get("puts_status"))
    gate.check("puts:null-refused", d.get("puts_null_status") == "13", d.get("puts_null_status"))
    gate.check("puts:oob-refused", d.get("puts_oob_status") == "13", d.get("puts_oob_status"))
    gate.check("puts:arity-refused", d.get("puts_arity_status") == "13", d.get("puts_arity_status"))
    gate.check("unknown:refused", d.get("unknown_status") == "6", d.get("unknown_status"))
    gate.check("surface:no-generic-fallback", d.get("service_failures") == "8",
               d.get("service_failures"))

    observation = {
        "schema": "openrecomp-phase14-service-observation-v1", "stage": STAGE,
        "evidence_class": "PUBLIC_SYNTHETIC",
        "direct": d,
        "c0_surface": surface.c0_surface.surface_document(),
        "closure_surface": surface.surface_document(),
        "b0_56": {"service": "ps1.bios.B0.56", "name": "GetC0Table",
                  "synthetic_table": f"0x{surface.c0_surface.addresses()['c0_table']:08x}"},
        "continuation": {
            "service": "ps1.bios.internal.card_continuation",
            "typed_identity": f"0x{surface.c0_surface.addresses()['card_continuation']:08x}",
        },
    }
    write_json(evidence / "dispatch.json", observation)
    assert_public_safe(gate, "dispatch", observation, image.payload)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase14-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P14_01": "PASS", "OPENRECOMP_P14_02": "PASS",
                    B0_56_MARKER: "PASS", C0_TABLE_MARKER: "PASS",
                    CARD_CONTINUATION_MARKER: "PASS", INITIALIZATION_MARKER: "NOT_PROVEN",
                    FRAME_MARKER: "NOT_PROVEN", PLAYABILITY_MARKER: "NOT_PROVEN",
                    GENERAL_MARKER: "NOT_PROVEN"},
        "next_stage": "P14-03",
    })
    write_json(evidence / "p14_01_tests.json", gate.tests_document("service"))
    gate.mark("OPENRECOMP_P14_01")
    gate.mark("OPENRECOMP_P14_02")
    gate.mark(B0_56_MARKER)
    gate.mark(C0_TABLE_MARKER)
    gate.mark(CARD_CONTINUATION_MARKER)
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase14/evidence/P14-01"))
