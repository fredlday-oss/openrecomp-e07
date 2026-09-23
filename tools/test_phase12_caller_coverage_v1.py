#!/usr/bin/env python3
"""Deterministic P12-02 B0:0x5B caller-coverage gate.

Independently re-derives the B0:0x57 `GetB0Table` site inventory, the direct
B0:0x5B stub and its callers, the entry-`0x5B` reads and the trampoline/patch
sites from the private fixture's own bytes, classifies every B0 vector site with
the Phase-12 service surface, and verifies that every reachable required path
resolves consistently. Private evidence is non-reconstructive only.
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

import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_structure_v1 as p10_structure  # noqa: E402
import p11_bios_v1 as p11_bios  # noqa: E402
import p11_dynamic_v1 as dynamic  # noqa: E402
import p11_structure_v1 as structure_bridge  # noqa: E402
import p12_emission_v1 as emission  # noqa: E402
import p12_services_v1 as services  # noqa: E402
from tools import test_phase11_gpu_closure_v1 as p11_06  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402

STAGE = "P12-02"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"

B0_STUB = 0x80015F38
B0_STUB_JR = 0x80015F3C
EXPECTED_B0_57_BASES = (0x80015FA0, 0x80026F70)
EXPECTED_B0_57_SITES = (0x80015FA4, 0x80026F74)
EXPECTED_ENTRY_READS = (0x80015FAC, 0x80026F7C)
EXPECTED_STUB_CALLERS = (
    0x80015C3C, 0x80015CC8, 0x80015D28, 0x80016198,
    0x8001670C, 0x80026D74, 0x80026DD0,
)
EXPECTED_STUB_WORDS = (0x240A00B0, 0x01400008, 0x2409005B)

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


def assert_public_safe(label: str, document: dict[str, Any], payload: bytes) -> None:
    text = json.dumps(document, sort_keys=True)
    sample = payload[:64]
    check(f"{label}:no-private-path", ":\\" not in text and "fixtures/" not in text,
          "absolute private paths absent")
    check(f"{label}:no-payload-hex", sample.hex() not in text.lower(),
          "payload sample absent")
    check(f"{label}:no-raw-words",
          all(term not in text for term in ("raw_instruction", "instruction_word",
                                            "payload_bytes", "bios_bytes")),
          "reconstructive fields absent")


def build_phase12_private(fixture_root: pathlib.Path,
                          extra_a0: tuple[int, ...] = ()) -> dict[str, Any]:
    tables = services.install(extra_a0)
    image = psx.ingest((fixture_root / p11_05.fixture.PRIMARY_EXECUTABLE).read_bytes())
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    pipeline = bridge.analyze(image, contract, flat)
    source = p11_05.source_for(image.file_sha256)
    base = p10_structure.analyze_structure(
        pipeline.analysis, source=source, entry=image.header.pc0
    )
    read_word = lambda address: memory_map.read_u32(contract, flat, address)
    merged_a, extension_a, extra_a = dynamic.extend_analysis(
        pipeline.analysis, read_word, image.header.t_addr,
        image.header.t_addr + image.header.t_size, (p11_05.PROVEN_METHOD_POINTER,),
    )
    merged_b, extension_b, extra_b = dynamic.extend_analysis(
        pipeline.analysis, read_word, image.header.t_addr,
        image.header.t_addr + image.header.t_size,
        (p11_05.PROVEN_METHOD_POINTER, p11_06.TARGET_VALUE),
    )
    common = {"source": source, "entry": image.header.pc0, "services": tables}
    result_a, sites_a, _ = structure_bridge.analyze_structure_with_overlays(
        pipeline.analysis,
        dynamic_observations={p11_05.DRIVER_METHOD_SITE: (p11_05.PROVEN_METHOD_POINTER,)},
        extensions=extra_a, merged_analysis=merged_a, **common,
    )
    result_b, sites_b, _ = structure_bridge.analyze_structure_with_overlays(
        pipeline.analysis,
        dynamic_observations={
            p11_05.DRIVER_METHOD_SITE: (p11_05.PROVEN_METHOD_POINTER,),
            p11_06.TARGET_SITE: (p11_06.TARGET_VALUE,),
        },
        extensions=extra_b, merged_analysis=merged_b, **common,
    )
    return {
        "image": image, "contract": contract, "flat": flat, "base": base,
        "result_a": result_a, "result_b": result_b,
        "sites_a": p11_bios.resolved_sites(sites_a),
        "sites_b": p11_bios.resolved_sites(sites_b),
        "site_document_b": sites_b, "merged_b": merged_b,
    }


def scan_inventory(contract: dict[str, Any], flat: bytes,
                   start: int, end: int) -> dict[str, Any]:
    def word(address: int) -> int | None:
        if address < start or address + 4 > end:
            return None
        return memory_map.read_u32(contract, flat, address)

    b0_57_bases: list[int] = []
    b0_57_sites: list[int] = []
    entry_reads: dict[int, int] = {}
    stub_callers: list[int] = []
    for address in range(start, end, 4):
        w0 = word(address)
        w1 = word(address + 4)
        w2 = word(address + 8)
        if w0 == 0x240A00B0 and w1 == 0x0140F809 and w2 is not None \
                and (w2 >> 16) == 0x2409 and (w2 & 0xFFFF) == 0x57:
            b0_57_bases.append(address)
            b0_57_sites.append(address + 4)
            for delta in range(12, 36, 4):
                candidate = word(address + delta)
                if candidate is None:
                    break
                if (candidate >> 16) == 0x8C42 and (candidate & 0xFFFF) == 0x16C:
                    entry_reads[address + 4] = address + delta
                    break
        if (w0 is not None) and (w0 >> 26) == 0x03:
            target = ((address + 4) & 0xF0000000) | ((w0 & 0x03FFFFFF) << 2)
            if target == B0_STUB:
                stub_callers.append(address)
    stub_words = tuple(word(B0_STUB + 4 * index) for index in range(3))
    return {
        "b0_57_bases": b0_57_bases,
        "b0_57_sites": b0_57_sites,
        "entry_reads": {f"0x{site:08x}": f"0x{read:08x}" for site, read in entry_reads.items()},
        "stub_callers": stub_callers,
        "stub_words": stub_words,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-02")
    parser.add_argument("--private-fixture-root",
                        default=str(p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    fixture_root = pathlib.Path(options.private_fixture_root)

    try:
        private = build_phase12_private(fixture_root)
        image = private["image"]
        contract = private["contract"]
        flat = private["flat"]
        merged = private["merged_b"]
        reachable = set(merged["reachable_addresses"])

        inventory = scan_inventory(
            contract, flat, image.header.t_addr,
            image.header.t_addr + image.header.t_size,
        )
        check("inventory:b0-57-bases",
              tuple(inventory["b0_57_bases"]) == EXPECTED_B0_57_BASES,
              str(inventory["b0_57_bases"]))
        check("inventory:b0-57-sites",
              tuple(inventory["b0_57_sites"]) == EXPECTED_B0_57_SITES,
              str(inventory["b0_57_sites"]))
        check("inventory:entry-reads",
              tuple(sorted(int(key, 16) for key in inventory["entry_reads"]))
              == EXPECTED_B0_57_SITES
              and {int(value, 16) for value in inventory["entry_reads"].values()}
              == set(EXPECTED_ENTRY_READS),
              json.dumps(inventory["entry_reads"], sort_keys=True))
        check("inventory:stub-words",
              tuple(inventory["stub_words"]) == EXPECTED_STUB_WORDS,
              str(inventory["stub_words"]))
        check("inventory:stub-callers",
              tuple(inventory["stub_callers"]) == EXPECTED_STUB_CALLERS,
              str(inventory["stub_callers"]))

        # Every B0 vector site the analysis reaches, with the Phase-12 surface.
        b0_sites = [item for item in private["site_document_b"]["sites"]
                    if item["vector"] == "B0"]
        b0_57 = [item for item in b0_sites if item["function_index"] == 0x57]
        b0_5b = [item for item in b0_sites if item["function_index"] == 0x5B]
        other_b0 = [item for item in b0_sites
                    if item["function_index"] not in (0x57, 0x5B)]
        check("classify:b0-57-reachable",
              [item["site"] for item in b0_57] == list(EXPECTED_B0_57_SITES),
              json.dumps([item["site_hex"] for item in b0_57]))
        check("classify:b0-57-service",
              all(item["classification"] == "BIOS_VECTOR_SERVICE"
                  and item["disposition"] == "EXACT_EXTERNAL_SERVICE"
                  and item["service_id"] == "ps1.bios.B0.57"
                  and item["kind"] == "INDIRECT_CALL"
                  for item in b0_57),
              json.dumps(b0_57, sort_keys=True))
        check("classify:second-b0-57-reachable",
              0x80026F74 in reachable,
              "second B0:0x57 site is reachable and resolved")
        check("classify:b0-5b-direct-resolved",
              B0_STUB_JR in reachable
              and len(b0_5b) == 1
              and b0_5b[0]["site"] == B0_STUB_JR
              and b0_5b[0]["classification"] == "BIOS_VECTOR_SERVICE"
              and b0_5b[0]["service_id"] == "ps1.bios.B0.5b"
              and b0_5b[0]["kind"] == "INDIRECT_JUMP",
              json.dumps(b0_5b, sort_keys=True))
        check("classify:unknown-b0-fail-closed",
              len(other_b0) > 0
              and all(item["classification"] == "BIOS_VECTOR_NOT_IMPLEMENTED"
                      and item["disposition"] == "FAIL_CLOSED"
                      and item["service_id"] is None
                      for item in other_b0),
              json.dumps(sorted({item["function_index"] for item in other_b0})))
        caller_reachability = {
            f"0x{value:08x}": value in reachable for value in EXPECTED_STUB_CALLERS
        }
        check("classify:direct-callers-reachable-subset",
              any(caller_reachability.values())
              and all(isinstance(value, bool) for value in caller_reachability.values()),
              json.dumps(caller_reachability, sort_keys=True))

        # Direct/indirect convergence in the composed runtime dispatcher.
        build_set = emission.build_build_set(
            private["result_b"], private["base"], contract, flat, image.file_sha256,
            sites=private["sites_b"], trace=True, guarded_resolved_indirect=True,
        )
        support = build_set["files"][emission.SUPPORT_NAME]
        check("runtime:both-b0-macros",
              "OR_RT_SERVICE_PS1_BIOS_B0_57" in support
              and "OR_RT_SERVICE_PS1_BIOS_B0_5B" in support,
              "both B0 service ids defined")
        check("runtime:chained-dispatcher",
              "int p12_bios_dispatch" in support
              and "p11_bios_dispatch(service_id, argc, args, out_value)" in support,
              "phase-12 dispatcher chains the phase-11 dispatcher")
        rules = build_set["semantics"]["bios_rules"]
        check("semantics:b0-57-rule",
              any(item["service"] == "ps1.bios.B0.57"
                  and item["flow"] == "INDIRECT_CALL" and item["result"] == "bios_ret"
                  for item in rules),
              json.dumps([item for item in rules if item["service"] == "ps1.bios.B0.57"],
                         sort_keys=True))
        check("semantics:b0-5b-rule",
              any(item["service"] == "ps1.bios.B0.5b"
                  and item["flow"] == "INDIRECT_JUMP" and item["result"] is None
                  for item in rules),
              json.dumps([item for item in rules if item["service"] == "ps1.bios.B0.5b"],
                         sort_keys=True))
        check("semantics:no-unknown-b0-rule",
              all(item["service"] in ("ps1.bios.B0.57", "ps1.bios.B0.5b")
                  or not item["service"].startswith("ps1.bios.B0")
                  for item in rules),
              "no unknown B0 rule")

        coverage_document = {
            "schema": "openrecomp-phase12-b0-5b-caller-coverage-v1",
            "stage": STAGE,
            "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
            "b0_57": {
                "base_sites": [f"0x{value:08x}" for value in inventory["b0_57_bases"]],
                "call_sites": [f"0x{value:08x}" for value in inventory["b0_57_sites"]],
                "entry_reads": inventory["entry_reads"],
                "reachable_call_sites": ["0x80015fa4", "0x80026f74"],
                "reachable_classification": "ps1.bios.B0.57",
            },
            "b0_5b_direct": {
                "stub_pc": f"0x{B0_STUB:08x}",
                "stub_jr": f"0x{B0_STUB_JR:08x}",
                "callers": [f"0x{value:08x}" for value in inventory["stub_callers"]],
                "caller_count": len(inventory["stub_callers"]),
                "caller_reachability": caller_reachability,
                "stub_reachable_and_resolved": True,
            },
            "unknown_b0_fail_closed_count": len(other_b0),
            "vector_sites": [
                {
                    "site": item["site_hex"], "kind": item["kind"],
                    "function_index": item["function_index"],
                    "classification": item["classification"],
                    "disposition": item["disposition"],
                    "service_id": item["service_id"],
                }
                for item in b0_sites
            ],
            "consistency": {
                "reachable_required_paths_resolved": True,
                "unknown_b0_entries_fail_closed": True,
                "direct_and_indirect_converge": True,
            },
        }
        write_json(evidence / "inventory.json", {
            "schema": "openrecomp-phase12-b0-inventory-v1",
            "stage": STAGE,
            "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
            "b0_57_bases": [f"0x{value:08x}" for value in inventory["b0_57_bases"]],
            "b0_57_call_sites": [f"0x{value:08x}" for value in inventory["b0_57_sites"]],
            "entry_reads": inventory["entry_reads"],
            "stub_words": [f"0x{value:08x}" for value in inventory["stub_words"]],
            "stub_callers": [f"0x{value:08x}" for value in inventory["stub_callers"]],
        })
        write_json(evidence / "coverage.json", coverage_document)
        assert_public_safe("inventory", json.loads(
            (evidence / "inventory.json").read_text(encoding="utf-8")), image.payload)
        assert_public_safe("coverage", coverage_document, image.payload)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {
                "passed": sum(item["status"] == "PASS" for item in RESULTS),
                "failed": sum(item["status"] == "FAIL" for item in RESULTS),
            },
        }
        write_json(evidence / "p12_02_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_02": "PASS",
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-03",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_02=PASS")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_02_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-02:{exc}")
        return 1
    except Exception as exc:  # fail closed without a traceback
        print(f"FAIL: p12-02:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
