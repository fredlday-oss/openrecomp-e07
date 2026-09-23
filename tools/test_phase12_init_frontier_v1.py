#!/usr/bin/env python3
"""Deterministic P12-04 Hercules initialization frontier-loop gate.

Implements the minimum documented A0:0x44 `FlushCache` semantics (no argument,
void; no observable effect in the non-cached flat-memory bounded model), reruns
the private initialization path, and records the next exact frontier. The next
frontier is BIOS interrupt-routine management (C0:0x02/0x03, C0:0x0a), whose
faithful semantics require interrupt delivery that the bounded architecture does
not model; those services therefore stay fail-closed and the initialization
completion boundary is recorded as `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`.
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
import p11_bios_v1 as p11_bios  # noqa: E402
import p11_native_v1 as native  # noqa: E402
import p11_trace_v1 as p11_trace  # noqa: E402
import p12_emission_v1 as emission  # noqa: E402
import p12_services_v1 as services  # noqa: E402
import p12_trace_v1 as trace  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402
from tools import test_phase12_changeclear_pad_v1 as ccp  # noqa: E402
from tools import test_phase12_caller_coverage_v1 as cov  # noqa: E402

STAGE = "P12-04"
BLOCKER = "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"

ACCESS_BUDGET = p11_05.ACCESS_BUDGET
BLOCK_BUDGET = p11_05.BLOCK_BUDGET

EXPECTED_NEW_FRONTIER = {
    "site": "0x80015f5c",
    "message": "unresolved indirect jump",
    "source_value": "0x000000c0",
    "function_id": "fn_80015f58",
    "block_id": "blk_80015f58",
    "terminal_op": "jr_indirect",
}
EXPECTED_C0_SITES = (
    (0x80015F4C, 0x02),
    (0x80015F5C, 0x03),
    (0x800161E0, 0x0A),
)

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


def a0_flush_words() -> list[int]:
    assembler = ccp.fixture_gate.Assembler()
    assembler.i("addiu", rt=2, imm=0x1234)
    assembler.jump("jal", "bios_stub")
    assembler.nop()
    assembler.i("addiu", rt=16, imm=0x55)
    assembler.r("jr", rs=31)
    assembler.nop()
    assembler.label("bios_stub")
    assembler.i("addiu", rt=10, imm=0xA0)
    assembler.r("jr", rs=10)
    assembler.i("addiu", rt=9, imm=0x44)
    return assembler.finish()


def flush_direct_driver(service_id: int) -> str:
    return f'''#include <stdint.h>
#include <stdio.h>
void p9_runtime_init(void);
int or_rt_host_call(uint64_t, uint32_t, const uint64_t *, uint64_t *);
uint64_t p9_runtime_memory_reads(void);
uint64_t p9_runtime_memory_writes(void);
uint64_t p10_runtime_mips_service_calls(void);
uint64_t p10_runtime_mips_service_failures(void);
int main(void)
{{
    uint64_t args[1];
    uint64_t out = UINT64_C(0);
    int s0, s1;
    p9_runtime_init();
    s0 = or_rt_host_call(UINT64_C({service_id}), 0u, NULL, &out);
    printf("flush_status=%d\\n", s0);
    args[0] = UINT64_C(1);
    s1 = or_rt_host_call(UINT64_C({service_id}), 1u, args, &out);
    printf("flush_arity_status=%d\\n", s1);
    printf("reads=%llu\\n", (unsigned long long)p9_runtime_memory_reads());
    printf("writes=%llu\\n", (unsigned long long)p9_runtime_memory_writes());
    printf("service_calls=%llu\\n", (unsigned long long)p10_runtime_mips_service_calls());
    printf("service_failures=%llu\\n", (unsigned long long)p10_runtime_mips_service_failures());
    return 0;
}}
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-04")
    parser.add_argument("--private-fixture-root",
                        default=str(p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    fixture_root = pathlib.Path(options.private_fixture_root)
    build_root = ROOT / ".openrecomp-phase12" / "build"

    try:
        tables = services.install(extra_a0=(0x44,))
        check("surface:flushcache-installed",
              0x44 in tables["A0"]
              and tables["A0"][0x44]["name"] == "FlushCache"
              and tables["A0"][0x44]["signature"] == []
              and tables["A0"][0x44]["result_register"] is None,
              json.dumps(tables["A0"][0x44], sort_keys=True))

        # Public synthetic: A0:0x44 registration through the emitter.
        words = a0_flush_words()
        image, contract, flat, result, sites, document = ccp.structure_for_words(words, tables)
        check("synthetic:one-site", len(sites) == 1, str(len(sites)))
        site = sites[0]
        check("synthetic:service",
              site.service_id == "ps1.bios.A0.44" and site.vector == "A0"
              and site.function_index == 0x44 and site.kind == "INDIRECT_JUMP",
              json.dumps(site.to_document(), sort_keys=True))
        build_set = emission.build_build_set(
            result, result, contract, flat, image.file_sha256,
            sites=sites, trace=True, extra_a0=(0x44,),
        )
        built = native.build_native(
            build_set, build_root / "p12-04-public",
            fixture_id="p12-04-public", run_count=2,
        )
        check("synthetic:build", all(status == "OK" for status in built["build_status"]),
              str(built["build_status"]))
        first = trace.run_program(built["executables"][0], timeout=300)
        second = trace.run_program(built["executables"][1], timeout=300)
        check("synthetic:deterministic", first["stdout"] == second["stdout"],
              first["stdout_sha256"])
        simple = first["simple"]
        check("synthetic:success", simple.get("failed") == "0", str(simple.get("failed")))
        check("synthetic:ram-unchanged",
              first["parsed"].get("memory") == p11_05.fnv1a64(flat),
              str(first["parsed"].get("memory")))
        check("synthetic:void-return",
              first["parsed"]["register_file"].get("r02") == "0x00001234",
              str(first["parsed"]["register_file"].get("r02")))
        check("synthetic:continuation",
              first["parsed"]["register_file"].get("r16") == "0x00000055",
              str(first["parsed"]["register_file"].get("r16")))

        # Direct dispatcher: identity, void success, arity refusal.
        ids = build_set["runtime_composition"]["base"]["bios_fragment"]["service_numeric_ids"]
        check("dispatch:id-present", "ps1.bios.A0.44" in ids, json.dumps(sorted(ids)))
        direct_set = dict(build_set)
        direct_set["files"] = dict(build_set["files"])
        direct_set["files"][emission.DRIVER_NAME] = (
            p9_emission.render_image_header(contract) + "\n"
            + flush_direct_driver(ids["ps1.bios.A0.44"])
        )
        direct_build = native.build_native(
            direct_set, build_root / "p12-04-direct",
            fixture_id="p12-04-direct", run_count=2,
        )
        check("dispatch:build", all(status == "OK" for status in direct_build["build_status"]),
              str(direct_build["build_status"]))
        direct_first = trace.run_program(direct_build["executables"][0], timeout=300)
        direct_second = trace.run_program(direct_build["executables"][1], timeout=300)
        check("dispatch:deterministic", direct_first["stdout"] == direct_second["stdout"],
              direct_first["stdout_sha256"])
        direct = direct_first["simple"]
        check("dispatch:exact",
              direct == {
                  "flush_status": "0", "flush_arity_status": "13",
                  "reads": "0", "writes": "0", "service_calls": "2",
                  "service_failures": "1",
              }, json.dumps(direct, sort_keys=True))

        # Private fixture: the initialization frontier moves and stops at C0.
        private = cov.build_phase12_private(fixture_root, extra_a0=(0x44,))
        image = private["image"]
        contract = private["contract"]
        flat = private["flat"]
        private_set = emission.build_build_set(
            private["result_b"], private["base"], contract, flat, image.file_sha256,
            sites=private["sites_b"], trace=True, guarded_resolved_indirect=True,
            extra_a0=(0x44,),
        )
        private_build = native.build_native(
            private_set, build_root / "p12-04-private",
            fixture_id="p12-04-private", run_count=2,
        )
        check("private:build", all(status == "OK" for status in private_build["build_status"]),
              str(private_build["build_status"]))
        private_first = trace.run_program(private_build["executables"][0],
                                          budget=ACCESS_BUDGET, block_budget=BLOCK_BUDGET,
                                          timeout=1800)
        private_second = trace.run_program(private_build["executables"][1],
                                           budget=ACCESS_BUDGET, block_budget=BLOCK_BUDGET,
                                           timeout=1800)
        check("private:deterministic", private_first["stdout"] == private_second["stdout"],
              private_first["stdout_sha256"])
        ps = private_first["simple"]
        check("private:flushcache-exercised",
              int(ps.get("p10_service_calls", "0")) >= 94,
              ps.get("p10_service_calls"))
        analysis = p11_trace.analyze_trace(
            private_first["parsed"], p11_trace.StructureIndex(private["result_b"]), None
        )
        failure = analysis["failure"]
        check("private:frontier-past-flushcache",
              failure.get("site") != "0x80015b94", str(failure.get("site")))
        check("private:exact-frontier",
              all(failure.get(key) == value for key, value in EXPECTED_NEW_FRONTIER.items()),
              json.dumps(failure, sort_keys=True))

        # The C0 interrupt-routine services stay fail-closed.
        c0_sites = [item for item in private["site_document_b"]["sites"]
                    if item["vector"] == "C0"]
        observed = {(item["site"], item["function_index"]) for item in c0_sites}
        check("c0:reachable-sites",
              all(pair in observed for pair in EXPECTED_C0_SITES),
              json.dumps(sorted(observed)))
        check("c0:all-fail-closed",
              all(item["classification"] == "BIOS_VECTOR_NOT_IMPLEMENTED"
                  and item["disposition"] == "FAIL_CLOSED"
                  and item["service_id"] is None for item in c0_sites),
              json.dumps(c0_sites, sort_keys=True))

        blocker_document = {
            "schema": "openrecomp-phase12-initialization-frontier-v1",
            "stage": STAGE,
            "classification": BLOCKER,
            "implemented_this_stage": {
                "service": "ps1.bios.A0.44",
                "name": "FlushCache",
                "semantics": "documented cache flush; no observable effect in the "
                             "non-cached flat-memory bounded model",
            },
            "previous_frontier": {"site": "0x80015b94", "service": "ps1.bios.A0.44"},
            "current_frontier": failure,
            "blocking_c0_sites": [
                {"site": f"0x{site:08x}", "function_index": f"0x{index:02x}",
                 "name": p11_bios.DOCUMENTED_INDEX_NAMES.get(("C0", index))}
                for site, index in EXPECTED_C0_SITES
            ],
            "missing_evidence": [
                "faithful BIOS interrupt-routine registration semantics (C0:0x02/0x03)",
                "root-counter interrupt-clear semantics (C0:0x0a)",
                "interrupt delivery and callback invocation ordering, which the bounded "
                "architecture does not model and must not guess",
            ],
            "decision": "the C0 interrupt services remain fail-closed; implementing only "
                        "registration would be a permissive partial model without "
                        "evidence for delivery semantics",
            "milestone_b": "NOT_PROVEN",
        }
        write_json(evidence / "blocker.json", blocker_document)
        cov.assert_public_safe("blocker", blocker_document, image.payload)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {
                "passed": sum(item["status"] == "PASS" for item in RESULTS),
                "failed": sum(item["status"] == "FAIL" for item in RESULTS),
            },
        }
        write_json(evidence / "p12_04_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_04": "PASS",
                "OPENRECOMP_PHASE12_INITIALIZATION_FRONTIER": BLOCKER,
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-05",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_04=PASS")
        print(f"OPENRECOMP_PHASE12_INITIALIZATION_FRONTIER={BLOCKER}")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_04_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-04:{exc}")
        return 1
    except Exception as exc:  # fail closed without a traceback
        print(f"FAIL: p12-04:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
