#!/usr/bin/env python3
"""Deterministic P14-20 fail-closed hardening gate."""

from __future__ import annotations

import json
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
import p11_bios_v1 as p11_bios  # noqa: E402
import p11_native_v1 as native  # noqa: E402
from p14_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
from p14_contracts_v1 import FRAME_MARKER, GENERAL_MARKER, INITIALIZATION_MARKER, PLAYABILITY_MARKER  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402

import p14_analysis_v1 as analysis_mod  # noqa: E402
import p14_c0_surface_v1 as c0_surface  # noqa: E402
import p14_closure_surface_v1 as surface  # noqa: E402
import p14_emission_v1 as emission  # noqa: E402
import p14_services_v1 as services  # noqa: E402
import p14_trace_v1 as trace  # noqa: E402

STAGE = "P14-20"


def negative_driver(ids: dict[str, int]) -> str:
    b0_56 = ids["ps1.bios.B0.56"]
    b0_57 = ids["ps1.bios.B0.57"]
    cont = ids["ps1.bios.internal.card_continuation"]
    return f'''#include <stdint.h>
#include <stdio.h>
void p9_runtime_init(void);
int or_rt_host_call(uint64_t, uint32_t, const uint64_t *, uint64_t *);
int main(void)
{{
    uint64_t args[2];
    uint64_t out = UINT64_C(0);
    int s;
    p9_runtime_init();
    s = or_rt_host_call(UINT64_C({b0_56}), 1u, args, &out);
    printf("b0_56_arity=%d\\n", s);
    s = or_rt_host_call(UINT64_C({b0_57}), 1u, args, &out);
    printf("b0_57_arity=%d\\n", s);
    args[0] = UINT64_C(0x1f001928);
    s = or_rt_host_call(UINT64_C({cont}), 1u, args, &out);
    printf("cont_patch_dest_rejected=%d\\n", s);
    args[0] = UINT64_C(0x80026e98);
    s = or_rt_host_call(UINT64_C({cont}), 1u, args, &out);
    printf("cont_guest_target_rejected=%d\\n", s);
    s = or_rt_host_call(UINT64_C(0x000000ff), 0u, NULL, &out);
    printf("unknown_identity=%d\\n", s);
    s = or_rt_host_call(UINT64_C({b0_56}), 0u, NULL, &out);
    printf("b0_56_ok=%d\\n", s);
    return 0;
}}
'''


def _numeric_ids(record):
    if isinstance(record, dict):
        if "service_numeric_ids" in record:
            return record["service_numeric_ids"]
        for value in record.values():
            found = _numeric_ids(value)
            if found:
                return found
    return None


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # --- analysis-level fail-closed policy -----------------------------------
    services.install(surface.EXTRA_A0, surface.EXTRA_C0, surface.EXTRA_B0,
                     p14_b0=surface.P14_B0, p14_a0=surface.P14_A0)
    gate.check("surface:c0-0a-unimplemented", 0x0A not in p11_bios.DOCUMENTED_C0_SERVICES,
               "C0:0x0A stays fail closed")
    gate.check("surface:a0-72-unimplemented", 0x72 not in services.DOCUMENTED_A0_SERVICES_ADDITIONS,
               "A0:0x72 stays fail closed")
    gate.check("surface:b0-17-19-unimplemented",
               0x17 not in services.DOCUMENTED_B0_SERVICES_ADDITIONS
               and 0x19 not in services.DOCUMENTED_B0_SERVICES_ADDITIONS,
               "B0:0x17/0x19 stay fail closed")

    private = analysis_mod.build_phase14_private(
        p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT, extra_a0=surface.EXTRA_A0,
        extra_c0=surface.EXTRA_C0, extra_b0=surface.EXTRA_B0,
        p14_b0=surface.P14_B0, p14_a0=surface.P14_A0,
        internal_targets=surface.INTERNAL_TARGETS,
    )
    not_implemented = [d for d in private["site_document_b"]["sites"]
                       if d["classification"] == "BIOS_VECTOR_NOT_IMPLEMENTED"]
    gate.check("analysis:unresolved-sites-fail-closed",
               all(d["service_id"] is None and d["disposition"] == "FAIL_CLOSED"
                   for d in not_implemented),
               json.dumps([d["site_hex"] for d in not_implemented]))
    classification = private["result_b"].classification.to_document()
    resolved_internal = 0
    for unit in classification.get("units", []):
        for item in unit.get("classifications", []):
            if item.get("address") in surface.INTERNAL_TARGETS:
                resolved_internal += 1
                gate.check(f"guarded:{item['address']:08x}",
                           item["status"] == "RESOLVED"
                           and item["basis"] in ("EXACT_CONSTANT_TARGET", "EXACT_TARGET_SET")
                           and tuple(item["targets"]) == surface.INTERNAL_TARGETS[item["address"]],
                           json.dumps(item, sort_keys=True))
    gate.check("guarded:all-sites", resolved_internal == len(surface.INTERNAL_TARGETS),
               f"{resolved_internal}/{len(surface.INTERNAL_TARGETS)}")

    # --- synthetic surface bounds --------------------------------------------
    gate.check("synthetic:window-bounds",
               c0_surface.bounds_ok(0x193c) and not c0_surface.bounds_ok(0x1f002000)
               and not c0_surface.bounds_ok(-4),
               json.dumps(c0_surface.synthetic_offsets(), sort_keys=True))
    gate.check("synthetic:handler-reconstruction-exact",
               c0_surface.reconstruct_handler(*c0_surface.handler_halves(0x1F001900)) == 0x1F001900
               and c0_surface.reconstruct_handler(0, 0) == 0,
               "guest derivation reproduced exactly")
    gate.check("synthetic:not-authentic-bios",
               c0_surface.surface_document()["authentic_bios_address_claimed"] is False)

    # --- runtime fail-closed negatives ---------------------------------------
    build_set = emission.build_build_set(
        private["result_b"], private["base"], private["contract"], private["flat"],
        private["image"].file_sha256, sites=private["sites_b"], trace=True,
        guarded_resolved_indirect=True, extra_a0=surface.EXTRA_A0,
        extra_c0=surface.EXTRA_C0, extra_b0=surface.EXTRA_B0,
        p14_b0=surface.P14_B0, p14_a0=surface.P14_A0,
    )
    ids = _numeric_ids(build_set["runtime_composition"])
    direct_set = dict(build_set)
    direct_set["files"] = dict(build_set["files"])
    direct_set["files"][emission.DRIVER_NAME] = (
        p9_emission.render_image_header(private["contract"]) + "\n" + negative_driver(ids)
    )
    built = native.build_native(direct_set, root / ".openrecomp-phase14/build/p14-hardening",
                                fixture_id="p14-hardening", run_count=2)
    gate.check("negative:build", all(s == "OK" for s in built["build_status"]),
               str(built["build_status"]))
    first = trace.run_program(built["executables"][0], timeout=600)
    second = trace.run_program(built["executables"][1], timeout=600)
    gate.check("negative:deterministic", first["stdout"] == second["stdout"],
               first["stdout_sha256"])
    d = first["simple"]
    gate.check("negative:b0-56-arity", d.get("b0_56_arity") == "13", d.get("b0_56_arity"))
    gate.check("negative:b0-57-arity", d.get("b0_57_arity") == "13", d.get("b0_57_arity"))
    gate.check("negative:continuation-patch-dest", d.get("cont_patch_dest_rejected") == "13",
               d.get("cont_patch_dest_rejected"))
    gate.check("negative:continuation-guest-target", d.get("cont_guest_target_rejected") == "13",
               d.get("cont_guest_target_rejected"))
    gate.check("negative:unknown-identity", d.get("unknown_identity") == "6",
               d.get("unknown_identity"))

    document = {
        "schema": "openrecomp-phase14-hardening-v1", "stage": STAGE,
        "evidence_class": "PUBLIC_SYNTHETIC",
        "unresolved_sites": sorted(d["site_hex"] for d in not_implemented),
        "guarded_indirect_sites": sorted(f"0x{s:08x}" for s in surface.INTERNAL_TARGETS),
        "synthetic_surface": c0_surface.surface_document(),
        "runtime_negatives": d,
        "generic_allow_all_indirect": False,
        "generic_allow_all_bios": False,
        "broad_synthetic_memory": False,
    }
    write_json(evidence / "hardening.json", document)
    assert_public_safe(gate, "hardening", document, private["image"].payload)
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase14-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P14_20": "PASS", INITIALIZATION_MARKER: "NOT_PROVEN",
                    FRAME_MARKER: "NOT_PROVEN", PLAYABILITY_MARKER: "NOT_PROVEN",
                    GENERAL_MARKER: "NOT_PROVEN"},
        "next_stage": "P14-30",
    })
    write_json(evidence / "p14_20_tests.json", gate.tests_document("hardening"))
    gate.mark("OPENRECOMP_P14_20")
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase14/evidence/P14-20"))
