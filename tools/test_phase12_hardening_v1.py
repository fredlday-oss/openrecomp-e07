#!/usr/bin/env python3
"""Deterministic P12-20 Phase-12 runtime / fail-closed hardening gate.

Exercises the composed Phase-12 dispatcher with malformed and unsupported
inputs, verifies unknown services and unknown indirect IDs reject, checks that
unknown B0 entries stay zero and that a null guest target fails closed, and
proves the production runtime contains no private-fixture path and no permissive
fallback.
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
import p11_native_v1 as native  # noqa: E402
import p12_emission_v1 as emission  # noqa: E402
import p12_services_v1 as services  # noqa: E402
import p12_trace_v1 as trace  # noqa: E402
from tools import test_phase12_changeclear_pad_v1 as ccp  # noqa: E402
from tools import test_phase12_caller_coverage_v1 as cov  # noqa: E402

STAGE = "P12-20"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"

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


def hardening_words() -> list[int]:
    assembler = ccp.fixture_gate.Assembler()
    variants = ((0x44, 0xA0), (0x57, 0xB0), (0x5B, 0xB0))
    for index, _vector in variants:
        assembler.jump("jal", f"stub_{index}")
        assembler.nop()
    assembler.i("addiu", rt=16, imm=0x55)
    assembler.r("jr", rs=31)
    assembler.nop()
    for index, vector in variants:
        assembler.label(f"stub_{index}")
        assembler.i("addiu", rt=10, imm=vector)
        assembler.r("jr", rs=10)
        assembler.i("addiu", rt=9, imm=index)
    return assembler.finish()


def hardening_driver(ids: dict[str, int], unknown_id: int) -> str:
    return f'''#include <stdint.h>
#include <stdio.h>
void p9_runtime_init(void);
int or_rt_host_call(uint64_t, uint32_t, const uint64_t *, uint64_t *);
int or_rt_memory_read(uint64_t, uint32_t, uint64_t *);
uint64_t p10_runtime_mips_service_calls(void);
uint64_t p10_runtime_mips_service_failures(void);
uint32_t p12_bios_b0_entry(uint32_t);
int main(void)
{{
    uint64_t args[1];
    uint64_t out = UINT64_C(0);
    uint64_t mem = UINT64_C(0);
    int s_unknown, s_b0_57_argc, s_b0_5b_bad, s_b0_5b_arity, s_a0_44_arity, mem_status;
    p9_runtime_init();
    s_unknown = or_rt_host_call(UINT64_C({unknown_id}), 0u, NULL, &out);
    args[0] = UINT64_C(0);
    s_b0_57_argc = or_rt_host_call(UINT64_C({ids["ps1.bios.B0.57"]}), 1u, args, &out);
    args[0] = UINT64_C(2);
    s_b0_5b_bad = or_rt_host_call(UINT64_C({ids["ps1.bios.B0.5b"]}), 1u, args, &out);
    s_b0_5b_arity = or_rt_host_call(UINT64_C({ids["ps1.bios.B0.5b"]}), 0u, args, &out);
    s_a0_44_arity = or_rt_host_call(UINT64_C({ids["ps1.bios.A0.44"]}), 1u, args, &out);
    mem_status = or_rt_memory_read(UINT64_C(0), 32u, &mem);
    printf("unknown_status=%d\\n", s_unknown);
    printf("b0_57_argc_status=%d\\n", s_b0_57_argc);
    printf("b0_5b_bad_status=%d\\n", s_b0_5b_bad);
    printf("b0_5b_arity_status=%d\\n", s_b0_5b_arity);
    printf("a0_44_arity_status=%d\\n", s_a0_44_arity);
    printf("null_target_read_status=%d\\n", mem_status);
    printf("unknown_b0_entry=0x%08x\\n", (unsigned)p12_bios_b0_entry(0x10u));
    printf("service_calls=%llu\\n", (unsigned long long)p10_runtime_mips_service_calls());
    printf("service_failures=%llu\\n", (unsigned long long)p10_runtime_mips_service_failures());
    return 0;
}}
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-20")
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    build_root = ROOT / ".openrecomp-phase12" / "build"

    try:
        tables = services.install(extra_a0=(0x44,))
        words = hardening_words()
        image, contract, flat, result, sites, document = ccp.structure_for_words(words, tables)
        check("sites:three", len(sites) == 3, str(len(sites)))
        build_set = emission.build_build_set(
            result, result, contract, flat, image.file_sha256,
            sites=sites, trace=True, extra_a0=(0x44,),
        )
        ids = build_set["runtime_composition"]["base"]["bios_fragment"]["service_numeric_ids"]
        check("ids:expected",
              set(ids) == {"ps1.bios.A0.44", "ps1.bios.B0.57", "ps1.bios.B0.5b"},
              json.dumps(sorted(ids)))
        unknown_id = max(ids.values()) + 1000

        direct_set = dict(build_set)
        direct_set["files"] = dict(build_set["files"])
        direct_set["files"][emission.DRIVER_NAME] = (
            p9_emission.render_image_header(contract) + "\n"
            + hardening_driver(ids, unknown_id)
        )
        built = native.build_native(
            direct_set, build_root / "p12-20-hardening",
            fixture_id="p12-20-hardening", run_count=2,
        )
        check("build", all(status == "OK" for status in built["build_status"]),
              str(built["build_status"]))
        first = trace.run_program(built["executables"][0], timeout=300)
        second = trace.run_program(built["executables"][1], timeout=300)
        check("deterministic", first["stdout"] == second["stdout"],
              first["stdout_sha256"])
        simple = first["simple"]
        expected = {
            "unknown_status": "6",
            "b0_57_argc_status": "13",
            "b0_5b_bad_status": "13",
            "b0_5b_arity_status": "13",
            "a0_44_arity_status": "13",
            "null_target_read_status": "1",
            "unknown_b0_entry": "0x00000000",
            "service_calls": "5",
            "service_failures": "4",
        }
        mismatches = {key: (simple.get(key), value)
                      for key, value in expected.items() if simple.get(key) != value}
        check("dispatcher:exact-fail-closed", not mismatches,
              json.dumps(mismatches, sort_keys=True))

        # Production runtime must not hardcode the private fixture.
        production = list((ROOT / ".openrecomp-phase12" / "src").glob("*.py")) + \
            list((ROOT / ".openrecomp-phase12" / "runtime").glob("*"))
        offenders: list[str] = []
        for path in production:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            if any(term in text for term in ("slus_005", "fixtures/", "fixtures\\",
                                              "d:\\openrecomp", "hercules action game",
                                              ".bin\"", ".cue\"")):
                offenders.append(path.name)
        check("production:no-private-path", not offenders, json.dumps(offenders))
        check("production:no-fail-open",
              "return P9_RT_UNKNOWN_HOST_SERVICE;" in
              (ROOT / ".openrecomp-phase12/runtime/p12_bios_extension_v1.c").read_text(
                  encoding="utf-8"),
              "unknown services still fail closed")

        hardening = {
            "schema": "openrecomp-phase12-hardening-v1",
            "stage": STAGE,
            "observables": simple,
            "expected": expected,
            "stdout_sha256": first["stdout_sha256"],
            "checks": [
                "unknown host service id rejects (status 6)",
                "B0:0x57 wrong arity rejects (13)",
                "B0:0x5b unsupported mode rejects (13)",
                "B0:0x5b wrong arity rejects (13)",
                "A0:0x44 wrong arity rejects (13)",
                "null guest target read fails closed (status 1)",
                "unknown B0 entry is zero",
                "no private fixture path in production sources",
                "no permissive fallback",
            ],
        }
        write_json(evidence / "hardening.json", hardening)
        cov.assert_public_safe("hardening", hardening, image.payload)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {"passed": len(RESULTS), "failed": 0},
        }
        write_json(evidence / "p12_20_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_20": "PASS",
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-30",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_20=PASS")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_20_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-20:{exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: p12-20:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
