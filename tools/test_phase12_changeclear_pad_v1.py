#!/usr/bin/env python3
"""Deterministic P12-01 B0:0x5B ChangeClearPAD service gate.

Implements and verifies the minimum documented `ps1.bios.B0.5b`
`ChangeClearPAD(int)` service through the existing typed runtime/service
mediation architecture. The public synthetic fixtures exercise the emitter rule
and the composed production dispatcher; the private fixture is not needed here.
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
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_structure_v1 as p10_structure  # noqa: E402
import p11_bios_v1 as p11_bios  # noqa: E402
import p11_native_v1 as native  # noqa: E402
import p11_structure_v1 as structure_bridge  # noqa: E402
import p12_emission_v1 as emission  # noqa: E402
import p12_services_v1 as services  # noqa: E402
import p12_trace_v1 as trace  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402
from tools import test_phase10_semantics_v1 as fixture_gate  # noqa: E402

STAGE = "P12-01"
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


def source_for(sha256: str) -> ProgramSource:
    return ProgramSource("mips32-bounded-v1", adapter="adapters.mips32",
                         address_width_bits=32, endianness="little",
                         input_sha256=sha256)


def structure_for_words(words: list[int], service_tables: dict[str, Any]):
    data = fixture_gate.builder.build_from_words(words, load_address=fixture_gate.LOAD)
    image = psx.ingest(data)
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    pipeline = bridge.analyze(image, contract, flat)
    source = source_for(image.file_sha256)
    result, document = structure_bridge.analyze_structure_with_bios(
        pipeline.analysis, source=source, entry=image.header.pc0,
        services=service_tables,
    )
    return image, contract, flat, result, p11_bios.resolved_sites(document), document


def bios_stub_words(index: int, *, args: tuple[tuple[int, int], ...] = (),
                    sentinel: int | None = None) -> list[int]:
    """Original public program calling the documented B0 vector convention."""
    assembler = fixture_gate.Assembler()
    if sentinel is not None:
        assembler.i("addiu", rt=2, imm=sentinel)
    for register, value in args:
        assembler.i("addiu", rs=0, rt=register, imm=value)
    assembler.jump("jal", "bios_stub")
    assembler.nop()
    assembler.i("addiu", rt=16, imm=0x55)
    assembler.r("jr", rs=31)
    assembler.nop()
    assembler.label("bios_stub")
    assembler.i("addiu", rt=10, imm=0xB0)
    assembler.r("jr", rs=10)
    assembler.i("addiu", rt=9, imm=index)
    return assembler.finish()


def combined_words() -> list[int]:
    """Original public program with both B0 vector call shapes."""
    assembler = fixture_gate.Assembler()
    assembler.i("addiu", rs=0, rt=10, imm=0xB0)
    assembler.r("jalr", rs=10, rd=31)
    assembler.i("addiu", rs=0, rt=9, imm=0x57)
    assembler.i("addiu", rs=0, rt=4, imm=0)
    assembler.jump("jal", "bios_stub")
    assembler.nop()
    assembler.i("addiu", rt=16, imm=0x55)
    assembler.r("jr", rs=31)
    assembler.nop()
    assembler.label("bios_stub")
    assembler.i("addiu", rt=10, imm=0xB0)
    assembler.r("jr", rs=10)
    assembler.i("addiu", rt=9, imm=0x5B)
    return assembler.finish()


def direct_driver(b0_57: int, b0_5b: int) -> str:
    return f'''#include <stdint.h>
#include <stdio.h>
void p9_runtime_init(void);
int or_rt_host_call(uint64_t, uint32_t, const uint64_t *, uint64_t *);
uint64_t p9_runtime_host_calls(void);
uint64_t p10_runtime_mips_service_calls(void);
uint64_t p10_runtime_mips_service_failures(void);
uint32_t p12_bios_table_base(void);
uint32_t p12_bios_b0_entry(uint32_t);
uint32_t p12_bios_change_clear_pad(void);
uint64_t p12_bios_change_clear_calls(void);
int main(void)
{{
    uint64_t args[1];
    uint64_t out = UINT64_C(0);
    int s_get, s0, s1, s2, s3;
    p9_runtime_init();
    s_get = or_rt_host_call(UINT64_C({b0_57}), 0u, NULL, &out);
    printf("get_status=%d\\n", s_get);
    printf("table_base=0x%08x\\n", (unsigned)(out & UINT64_C(0xFFFFFFFF)));
    printf("entry_5b=0x%08x\\n", (unsigned)p12_bios_b0_entry(0x5bu));
    args[0] = UINT64_C(0);
    s0 = or_rt_host_call(UINT64_C({b0_5b}), 1u, args, &out);
    printf("pad0_status=%d\\n", s0);
    printf("pad0_state=%u\\n", (unsigned)p12_bios_change_clear_pad());
    args[0] = UINT64_C(1);
    s1 = or_rt_host_call(UINT64_C({b0_5b}), 1u, args, &out);
    printf("pad1_status=%d\\n", s1);
    printf("pad1_state=%u\\n", (unsigned)p12_bios_change_clear_pad());
    args[0] = UINT64_C(2);
    s2 = or_rt_host_call(UINT64_C({b0_5b}), 1u, args, &out);
    printf("pad_bad_status=%d\\n", s2);
    printf("pad_state_after_bad=%u\\n", (unsigned)p12_bios_change_clear_pad());
    s3 = or_rt_host_call(UINT64_C({b0_5b}), 0u, args, &out);
    printf("pad_arity_status=%d\\n", s3);
    printf("pad_calls=%llu\\n", (unsigned long long)p12_bios_change_clear_calls());
    printf("service_calls=%llu\\n", (unsigned long long)p10_runtime_mips_service_calls());
    printf("service_failures=%llu\\n", (unsigned long long)p10_runtime_mips_service_failures());
    printf("host_calls=%llu\\n", (unsigned long long)p9_runtime_host_calls());
    return 0;
}}
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-01")
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    build_root = ROOT / ".openrecomp-phase12" / "build"

    try:
        tables = services.install()
        check("service:b0-surface",
              sorted(p11_bios.DOCUMENTED_B0_SERVICES) == [0x57, 0x5B],
              str(sorted(p11_bios.DOCUMENTED_B0_SERVICES)))
        check("service:changeclearpad-name",
              tables["B0"][0x5B]["name"] == "ChangeClearPAD"
              and tables["B0"][0x5B]["signature"] == ["mode"]
              and tables["B0"][0x5B]["result_register"] is None,
              json.dumps(tables["B0"][0x5B], sort_keys=True))
        check("service:no-unrelated-b0",
              all(index in (0x57, 0x5B) for index in tables["B0"]),
              str(sorted(tables["B0"])))
        check("service:index-names",
              p11_bios.DOCUMENTED_INDEX_NAMES[("B0", 0x5B)] == "ChangeClearPAD"
              and p11_bios.DOCUMENTED_INDEX_NAMES[("B0", 0x57)] == "GetB0Table",
              "B0 names present")
        check("service:synthetic-not-bios-address",
              not (
                  memory_map.RAM_KSEG0_BASE <= services.SYNTH_BASE < memory_map.RAM_KSEG0_END
                  or memory_map.RAM_KSEG1_BASE <= services.SYNTH_BASE < memory_map.RAM_KSEG1_END
                  or memory_map.IO_BASE <= services.SYNTH_BASE < memory_map.IO_BASE + memory_map.IO_SIZE
                  or memory_map.BIOS_BASE <= services.SYNTH_BASE < memory_map.BIOS_BASE + memory_map.BIOS_SIZE
              ),
              f"0x{services.SYNTH_BASE:08x}")

        # Public synthetic: B0:0x5B through the emitter and production dispatcher.
        emitter_records: list[dict[str, Any]] = []
        for mode, expected_state in ((0, 0), (1, 1)):
            words = bios_stub_words(0x5B, args=((4, mode),), sentinel=0x1234)
            image, contract, flat, result, sites, document = structure_for_words(
                words, tables
            )
            check(f"emitter:mode{mode}:one-site", len(sites) == 1, str(len(sites)))
            site = sites[0]
            check(f"emitter:mode{mode}:service",
                  site.service_id == "ps1.bios.B0.5b"
                  and site.vector == "B0" and site.function_index == 0x5B
                  and site.op_name == "jump_bios_b0_5b"
                  and site.kind == "INDIRECT_JUMP",
                  json.dumps(site.to_document(), sort_keys=True))
            build_set = emission.build_build_set(
                result, result, contract, flat, image.file_sha256,
                sites=sites, trace=True,
            )
            rule = [item for item in build_set["semantics"]["bios_rules"]
                    if item["service"] == "ps1.bios.B0.5b"]
            check(f"emitter:mode{mode}:one-rule",
                  len(rule) == 1 and rule[0]["args"] == ["bios_arg0"]
                  and rule[0]["result"] is None
                  and rule[0]["flow"] == "INDIRECT_JUMP",
                  json.dumps(rule, sort_keys=True))
            built = native.build_native(
                build_set, build_root / f"p12-01-public-mode{mode}",
                fixture_id=f"p12-01-public-mode{mode}", run_count=2,
            )
            check(f"emitter:mode{mode}:build",
                  all(status == "OK" for status in built["build_status"]),
                  str(built["build_status"]))
            check(f"emitter:mode{mode}:reproducible", built["build_reproducible"],
                  built["executable_sha256"])
            first = trace.run_program(built["executables"][0], timeout=300)
            second = trace.run_program(built["executables"][1], timeout=300)
            check(f"emitter:mode{mode}:exit-stderr",
                  first["returncode"] == second["returncode"] == 0
                  and first["stderr_bytes"] == second["stderr_bytes"] == 0,
                  "exit 0 and empty stderr")
            check(f"emitter:mode{mode}:deterministic", first["stdout"] == second["stdout"],
                  first["stdout_sha256"])
            simple = first["simple"]
            check(f"emitter:mode{mode}:success",
                  simple.get("failed") == "0" and simple.get("error") == "",
                  str((simple.get("failed"), simple.get("error"))))
            check(f"emitter:mode{mode}:state",
                  simple.get("p12_change_clear_pad") == str(expected_state)
                  and simple.get("p12_change_clear_calls") == "1",
                  f"{simple.get('p12_change_clear_pad')}/{simple.get('p12_change_clear_calls')}")
            check(f"emitter:mode{mode}:void-return-preserved",
                  first["parsed"]["register_file"].get("r02") == "0x00001234",
                  str(first["parsed"]["register_file"].get("r02")))
            check(f"emitter:mode{mode}:continuation",
                  first["parsed"]["register_file"].get("r16") == "0x00000055",
                  str(first["parsed"]["register_file"].get("r16")))
            emitter_records.append({
                "mode": mode,
                "state": simple.get("p12_change_clear_pad"),
                "calls": simple.get("p12_change_clear_calls"),
                "stdout_sha256": first["stdout_sha256"],
            })

        # Public synthetic: unrelated B0 entry 0x58 stays fail-closed.
        words = bios_stub_words(0x58)
        image, contract, flat, result, sites, document = structure_for_words(words, tables)
        check("unrelated:no-service", sites == [], str(len(sites)))
        record = [item for item in document["sites"] if item["vector"] == "B0"
                  and item["function_index"] == 0x58]
        check("unrelated:not-implemented",
              len(record) == 1
              and record[0]["classification"] == "BIOS_VECTOR_NOT_IMPLEMENTED"
              and record[0]["disposition"] == "FAIL_CLOSED"
              and record[0]["service_id"] is None,
              json.dumps(record, sort_keys=True))

        # Direct production-dispatch unit test (service identity, arity, refusal).
        words = combined_words()
        image, contract, flat, result, sites, document = structure_for_words(words, tables)
        check("dispatch:two-sites", len(sites) == 2, str(len(sites)))
        build_set = emission.build_build_set(
            result, result, contract, flat, image.file_sha256, sites=sites, trace=True,
        )
        ids = build_set["runtime_composition"]["base"]["bios_fragment"]["service_numeric_ids"]
        check("dispatch:ids",
              set(ids) == {"ps1.bios.B0.57", "ps1.bios.B0.5b"},
              json.dumps(sorted(ids)))
        direct_set = dict(build_set)
        direct_set["files"] = dict(build_set["files"])
        direct_set["files"][emission.DRIVER_NAME] = (
            p9_emission.render_image_header(contract) + "\n"
            + direct_driver(ids["ps1.bios.B0.57"], ids["ps1.bios.B0.5b"])
        )
        direct_build = native.build_native(
            direct_set, build_root / "p12-01-direct",
            fixture_id="p12-01-direct", run_count=2,
        )
        check("dispatch:build",
              all(status == "OK" for status in direct_build["build_status"]),
              str(direct_build["build_status"]))
        direct_first = trace.run_program(direct_build["executables"][0], timeout=300)
        direct_second = trace.run_program(direct_build["executables"][1], timeout=300)
        check("dispatch:exit-stderr",
              direct_first["returncode"] == direct_second["returncode"] == 0
              and direct_first["stderr_bytes"] == direct_second["stderr_bytes"] == 0,
              "exit 0 and empty stderr")
        check("dispatch:deterministic",
              direct_first["stdout"] == direct_second["stdout"],
              direct_first["stdout_sha256"])
        direct = direct_first["simple"]
        expected = {
            "get_status": "0",
            "table_base": f"0x{services.SYNTH_BASE:08x}",
            "entry_5b": f"0x{services.SYNTH_BASE + services.SYNTH_TARGET_OFFSET:08x}",
            "pad0_status": "0",
            "pad0_state": "0",
            "pad1_status": "0",
            "pad1_state": "1",
            "pad_bad_status": "13",
            "pad_state_after_bad": "1",
            "pad_arity_status": "13",
            "pad_calls": "2",
            "service_calls": "5",
            "service_failures": "2",
            "host_calls": "5",
        }
        mismatches = {key: (direct.get(key), value)
                      for key, value in expected.items() if direct.get(key) != value}
        check("dispatch:exact-observables", not mismatches,
              json.dumps(mismatches, sort_keys=True))

        surface = services.service_surface_document()
        write_json(evidence / "service_surface.json", surface)
        write_json(evidence / "public_emitter.json", {
            "schema": "openrecomp-phase12-b0-5b-public-emitter-v1",
            "stage": STAGE,
            "records": emitter_records,
        })
        write_json(evidence / "direct_dispatch.json", {
            "schema": "openrecomp-phase12-b0-5b-direct-dispatch-v1",
            "stage": STAGE,
            "observables": direct,
            "expected": expected,
            "stdout_sha256": direct_first["stdout_sha256"],
        })

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {
                "passed": sum(item["status"] == "PASS" for item in RESULTS),
                "failed": sum(item["status"] == "FAIL" for item in RESULTS),
            },
        }
        write_json(evidence / "p12_01_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_01": "PASS",
                "OPENRECOMP_PHASE12_B0_5B_CHANGECLEARPAD_V1": "PASS",
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-02",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_01=PASS")
        print("OPENRECOMP_PHASE12_B0_5B_CHANGECLEARPAD_V1=PASS")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_01_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-01:{exc}")
        return 1
    except Exception as exc:  # fail closed without a traceback
        print(f"FAIL: p12-01:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
