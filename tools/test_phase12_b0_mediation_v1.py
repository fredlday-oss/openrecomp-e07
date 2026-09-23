#!/usr/bin/env python3
"""Deterministic P12-03 GetB0Table indirect service-mediation gate.

Closes the `B0:0x57` -> table entry `0x5B` indirect-control problem without
inventing a BIOS-resident guest address: the synthetic project-owned window is
populated at runtime and the entry resolves to the synthetic ChangeClearPAD
target. The gate runs the real Hercules initialization path past the frozen
Phase-11 frontier, verifies the documented pad-patch observables and the exact
new frontier, and records the bounded evidence.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_emission_v1 as p9_emission  # noqa: E402
import p10_fixture_identity_v1 as fixture_identity  # noqa: E402
import p11_bios_v1 as p11_bios  # noqa: E402
import p11_native_v1 as native  # noqa: E402
import p11_trace_v1 as p11_trace  # noqa: E402
import p12_emission_v1 as emission  # noqa: E402
import p12_services_v1 as services  # noqa: E402
import p12_trace_v1 as trace  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402
from tools import test_phase12_caller_coverage_v1 as cov  # noqa: E402

STAGE = "P12-03"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"

ACCESS_BUDGET = p11_05.ACCESS_BUDGET
BLOCK_BUDGET = p11_05.BLOCK_BUDGET

P11_07_FRONTIER_SITE = 0x80015FA4
B0_ENTRY_5B = 0x5B
SYNTH_TARGET = services.SYNTH_BASE + services.SYNTH_TARGET_OFFSET
DERIVED_884 = SYNTH_TARGET + 0x884
DERIVED_894 = SYNTH_TARGET + 0x894
EXPECTED_NEW_FRONTIER = {
    "site": "0x80015b94",
    "message": "unresolved indirect jump",
    "source_value": "0x000000a0",
    "function_id": "fn_80015b90",
    "block_id": "blk_80015b90",
    "terminal_op": "jr_indirect",
}

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


def unknown_entry_driver(b0_57: int) -> str:
    return f'''#include <stdint.h>
#include <stdio.h>
void p9_runtime_init(void);
int or_rt_host_call(uint64_t, uint32_t, const uint64_t *, uint64_t *);
uint32_t p12_bios_b0_entry(uint32_t);
uint32_t p12_synth_read32(uint32_t);
int main(void)
{{
    uint64_t out = UINT64_C(0);
    int status;
    p9_runtime_init();
    status = or_rt_host_call(UINT64_C({b0_57}), 0u, NULL, &out);
    printf("get_status=%d\\n", status);
    printf("entry_10=0x%08x\\n", (unsigned)p12_bios_b0_entry(0x10u));
    printf("entry_19=0x%08x\\n", (unsigned)p12_bios_b0_entry(0x19u));
    printf("entry_44=0x%08x\\n", (unsigned)p12_bios_b0_entry(0x44u));
    printf("entry_57=0x%08x\\n", (unsigned)p12_bios_b0_entry(0x57u));
    printf("entry_5b=0x%08x\\n", (unsigned)p12_bios_b0_entry(0x5bu));
    printf("table_0000=0x%08x\\n", (unsigned)p12_synth_read32(0x0000u));
    printf("table_05b0=0x%08x\\n", (unsigned)p12_synth_read32(0x05b0u));
    return 0;
}}
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-03")
    parser.add_argument("--private-fixture-root",
                        default=str(p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    fixture_root = pathlib.Path(options.private_fixture_root)
    build_root = ROOT / ".openrecomp-phase12" / "build"

    try:
        check("entry:stride", services.B0_ENTRY_5B_OFFSET == B0_ENTRY_5B * 4,
              f"0x{services.B0_ENTRY_5B_OFFSET:x} == 0x5b*4")

        private = cov.build_phase12_private(fixture_root)
        image = private["image"]
        contract = private["contract"]
        flat = private["flat"]

        build_set = emission.build_build_set(
            private["result_b"], private["base"], contract, flat, image.file_sha256,
            sites=private["sites_b"], trace=True, guarded_resolved_indirect=True,
        )
        built = native.build_native(
            build_set, build_root / "p12-03-private",
            fixture_id="p12-03-private", run_count=2,
        )
        check("private:build", all(status == "OK" for status in built["build_status"]),
              str(built["build_status"]))
        check("private:reproducible", built["build_reproducible"],
              built["executable_sha256"])

        first = trace.run_program(built["executables"][0], budget=ACCESS_BUDGET,
                                  block_budget=BLOCK_BUDGET, timeout=1800)
        second = trace.run_program(built["executables"][1], budget=ACCESS_BUDGET,
                                   block_budget=BLOCK_BUDGET, timeout=1800)
        check("private:exit-stderr",
              first["returncode"] == second["returncode"] == 0
              and first["stderr_bytes"] == second["stderr_bytes"] == 0,
              "exit 0 and empty stderr")
        check("private:deterministic", first["stdout"] == second["stdout"],
              first["stdout_sha256"])
        simple = first["simple"]

        # Mediation observables: GetB0Table -> synthetic table -> entry 0x5B.
        check("mediate:table-base",
              simple.get("p12_b0_table_base") == f"0x{services.SYNTH_BASE:08x}",
              str(simple.get("p12_b0_table_base")))
        check("mediate:entry-5b",
              simple.get("p12_b0_entry_5b") == f"0x{SYNTH_TARGET:08x}",
              str(simple.get("p12_b0_entry_5b")))
        check("mediate:derived-884",
              simple.get("p12_ram_2ed84") == f"0x{DERIVED_884:08x}",
              str(simple.get("p12_ram_2ed84")))
        check("mediate:derived-894",
              simple.get("p12_ram_2ed88") == f"0x{DERIVED_894:08x}",
              str(simple.get("p12_ram_2ed88")))
        clear = [simple.get(f"p12_synth_5b_clear_{index}") for index in range(11)]
        check("mediate:eleven-word-clear", clear == ["0x00000000"] * 11,
              json.dumps(clear))
        check("mediate:entry-read-observed",
              any(key.startswith("nonram_")
                  and key not in ("nonram_signatures", "nonram_overflow")
                  and value.split(",")[0] == "0x1f00016c"
                  for key, value in simple.items()),
              "synthetic table entry read observed")
        clear_addrs = {f"0x1f0015{offset:02x}" for offset in range(0x94, 0xC0, 4)}
        observed_writes = {
            value.split(",")[0] for key, value in simple.items()
            if key.startswith("nonram_")
            and key not in ("nonram_signatures", "nonram_overflow")
            and value.split(",")[2] == "1"
        }
        check("mediate:clear-write-signatures",
              clear_addrs <= observed_writes,
              json.dumps(sorted(clear_addrs - observed_writes)))
        check("mediate:change-pad-called",
              int(simple.get("p12_change_clear_calls", "0")) >= 1,
              str(simple.get("p12_change_clear_calls")))
        check("mediate:no-service-failure",
              simple.get("p10_service_failures") == "0",
              str(simple.get("p10_service_failures")))

        # New frontier: past the P11-07 B0 site, at the A0 jump dispatcher.
        analysis = p11_trace.analyze_trace(
            first["parsed"], p11_trace.StructureIndex(private["result_b"]), None
        )
        failure = analysis["failure"]
        check("frontier:past-p11-07", failure.get("site") != f"0x{P11_07_FRONTIER_SITE:08x}",
              str(failure.get("site")))
        check("frontier:exact",
              all(failure.get(key) == value for key, value in EXPECTED_NEW_FRONTIER.items()),
              json.dumps(failure, sort_keys=True))

        # B0:0x57 remains a typed service; unknown B0 entries unavailable.
        b0_57 = [item for item in private["site_document_b"]["sites"]
                 if item["vector"] == "B0" and item["function_index"] == 0x57]
        check("bios:b0-57-service",
              len(b0_57) == 2 and all(item["service_id"] == "ps1.bios.B0.57"
                                      for item in b0_57),
              json.dumps(b0_57, sort_keys=True))

        # Unknown table-entry rejection and non-execution, public dispatcher path.
        direct_set = dict(build_set)
        direct_set["files"] = dict(build_set["files"])
        ids = build_set["runtime_composition"]["base"]["bios_fragment"]["service_numeric_ids"]
        direct_set["files"][emission.DRIVER_NAME] = (
            p9_emission.render_image_header(contract) + "\n"
            + unknown_entry_driver(ids["ps1.bios.B0.57"])
        )
        direct_build = native.build_native(
            direct_set, build_root / "p12-03-unknown",
            fixture_id="p12-03-unknown", run_count=2,
        )
        check("unknown:build",
              all(status == "OK" for status in direct_build["build_status"]),
              str(direct_build["build_status"]))
        direct_first = trace.run_program(direct_build["executables"][0], timeout=300)
        direct_second = trace.run_program(direct_build["executables"][1], timeout=300)
        check("unknown:deterministic", direct_first["stdout"] == direct_second["stdout"],
              direct_first["stdout_sha256"])
        unknown = direct_first["simple"]
        check("unknown:entries-zero",
              unknown.get("get_status") == "0"
              and unknown.get("entry_10") == "0x00000000"
              and unknown.get("entry_19") == "0x00000000"
              and unknown.get("entry_44") == "0x00000000"
              and unknown.get("entry_57") == "0x00000000"
              and unknown.get("entry_5b") == f"0x{SYNTH_TARGET:08x}"
              and unknown.get("table_0000") == "0x00000000"
              and unknown.get("table_05b0") == "0x00000000",
              json.dumps(unknown, sort_keys=True))

        # No arbitrary guest execution: the guest image is inert and unknown
        # entries carry no pointer into BIOS or code.
        support = build_set["files"][emission.SUPPORT_NAME]
        check("no:guest-interpreter",
              all(term not in support for term in ("guest_pc", "decode_and_execute",
                                                    "execute_guest")),
              "no guest-code interpreter")
        check("no:unknown-pointer",
              services.SYNTH_BASE + services.SYNTH_SIZE <= services.SYNTH_BASE + 0x2000
              and SYNTH_TARGET + 0x8A0 <= services.SYNTH_BASE + services.SYNTH_SIZE,
              "synthetic object stays inside the project-owned window")

        mediation_document = {
            "schema": "openrecomp-phase12-b0-table-mediation-v1",
            "stage": STAGE,
            "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
            "acquisition": {
                "service": "ps1.bios.B0.57",
                "synthetic_table_base": f"0x{services.SYNTH_BASE:08x}",
                "entry_index": "0x5b",
                "entry_byte_offset": f"0x{services.B0_ENTRY_5B_OFFSET:x}",
                "entry_stride": "0x16c == 0x5b*4",
                "entry_value": f"0x{SYNTH_TARGET:08x}",
            },
            "caller_use": {
                "entry_read": "0x1f00016c",
                "derived_pointer_884": f"0x{DERIVED_884:08x}",
                "derived_pointer_894": f"0x{DERIVED_894:08x}",
                "eleven_word_clear": "all zero",
                "clear_write_signatures": sorted(clear_addrs),
            },
            "direct_indirect_convergence": {
                "service": "ps1.bios.B0.5b",
                "direct_site": "0x80015f3c",
                "indirect_entry": "0x5b",
                "same_implementation": "p12_bios_set_change_clear_pad",
            },
            "direct_call_count": simple.get("p12_change_clear_calls"),
            "synthetic_writes": simple.get("p12_synth_writes"),
            "synthetic_reads": simple.get("p12_synth_reads"),
            "new_frontier": failure,
            "unknown_entry_policy": "zero and fail-closed; no pointer into BIOS or code",
            "no_arbitrary_guest_execution": True,
        }
        frontier_document = {
            "schema": "openrecomp-phase12-b0-table-frontier-v1",
            "stage": STAGE,
            "previous_frontier": {"site": "0x80015fa4", "block_index": 468341},
            "new_frontier": failure,
            "private_run": {
                "access_budget": ACCESS_BUDGET,
                "block_budget": BLOCK_BUDGET,
                "executable_sha256": built["executable_sha256"],
                "stdout_sha256": first["stdout_sha256"],
                "block_events": simple.get("trace_block_events"),
                "block_digest": simple.get("trace_block_digest"),
            },
        }
        write_json(evidence / "mediation.json", mediation_document)
        write_json(evidence / "frontier.json", frontier_document)
        cov.assert_public_safe("mediation", mediation_document, image.payload)
        cov.assert_public_safe("frontier", frontier_document, image.payload)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {
                "passed": sum(item["status"] == "PASS" for item in RESULTS),
                "failed": sum(item["status"] == "FAIL" for item in RESULTS),
            },
        }
        write_json(evidence / "p12_03_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_03": "PASS",
                "OPENRECOMP_PHASE12_B0_TABLE_INDIRECT_V1": "PASS",
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-04",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_03=PASS")
        print("OPENRECOMP_PHASE12_B0_TABLE_INDIRECT_V1=PASS")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_03_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-03:{exc}")
        return 1
    except Exception as exc:  # fail closed without a traceback
        print(f"FAIL: p12-03:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
