#!/usr/bin/env python3
"""Deterministic P11-06 GPU/DMA/VRAM semantic-closure gate.

P11-05 exposed an exact unresolved indirect call. This gate proves its target
from the recorded runtime value and RAM pointer chain, extends the frozen code
frontier from that target, and uses the existing guarded indirect dispatch. No
GPU behavior is added: the newly translated guest function reaches the frozen
typed GP1 boundary, whose existing classifier records DISPLAY_ENABLE.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_gpu_boundary_v1 as gpu_boundary  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_structure_v1 as p10_structure  # noqa: E402
import p11_bios_v1 as bios  # noqa: E402
import p11_dynamic_v1 as dynamic  # noqa: E402
import p11_emission_v1 as emission  # noqa: E402
import p11_native_v1 as native  # noqa: E402
import p11_structure_v1 as structure_bridge  # noqa: E402
import p11_trace_v1 as trace  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402
from tools import test_phase10_semantics_v1 as fixture_gate  # noqa: E402


STAGE = "P11-06"
FEATURE_MARKER = "OPENRECOMP_PHASE11_GPU_SEMANTIC_CLOSURE_V1"
GPU_MARKER = "OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF"
NOT_PROVEN = "NOT_PROVEN"
PROVEN = "PROVEN"

TARGET_SITE = 0x8001882C
TARGET_VALUE = 0x8001A7DC
TARGET_BASE_POINTER_ADDRESS = 0x8002A284
TARGET_FIELD_ADDRESS = 0x8002A254
GP1_POINTER_ADDRESS = 0x8002A360
GP1_COMMAND = 0x03000001
PREFIX_BLOCK_BUDGET = 468_322
ACCESS_BUDGET = p11_05.ACCESS_BUDGET
BLOCK_BUDGET = p11_05.BLOCK_BUDGET

EXPECTED_A_FRONTIER = {
    "site": "0x8001882c", "source_value": "0x8001a7dc",
    "message": "unresolved indirect call", "function_entry": "0x8001b3f4",
    "function_id": "fn_800187b0", "block_id": "blk_80018824",
    "block_index": 468323, "failure_count": 23, "terminal_op": "jalr",
}
EXPECTED_B_FRONTIER = {
    "site": "0x80015fa4", "source_value": "0x000000b0",
    "message": "unresolved indirect call", "function_entry": "0x80015f18",
    "function_id": "fn_80015f90", "block_id": "blk_80015fa0",
    "block_index": 468341, "failure_count": 22, "terminal_op": "jalr",
}

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _strings(document):
    if isinstance(document, dict):
        for value in document.values():
            yield from _strings(value)
    elif isinstance(document, list):
        for value in document:
            yield from _strings(value)
    elif isinstance(document, str):
        yield document


def assert_private_safe(label: str, document: dict, payload: bytes) -> None:
    text = json.dumps(document, sort_keys=True)
    sample = payload[:64]
    check(f"{label}:no-hex", sample.hex() not in text.lower(), "payload hex absent")
    check(f"{label}:no-base64", base64.b64encode(sample).decode("ascii") not in text,
          "payload base64 absent")
    check(f"{label}:no-private-path", ":\\" not in text and "fixtures/" not in text,
          "absolute fixture path absent")
    check(f"{label}:no-raw-words", "raw_instruction" not in text,
          "raw instruction words absent")
    check(f"{label}:bounded-strings", all(len(value) <= 128 for value in _strings(document)),
          "all strings bounded")


def gp1_words(command: int) -> list[int]:
    """Original public program issuing one store to the documented GP1 port."""
    assembler = fixture_gate.Assembler()
    p11_05.emit_load_immediate(assembler, 4, command)
    p11_05.emit_load_immediate(assembler, 2, gpu_boundary.GP1_WRITE)
    assembler.i("sw", rs=2, rt=4, imm=0)
    assembler.i("addiu", rt=16, imm=0x55)
    assembler.r("jr", rs=31)
    assembler.nop()
    return assembler.finish()


def build_extended_private(fixture_root: pathlib.Path) -> dict:
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
        (p11_05.PROVEN_METHOD_POINTER, TARGET_VALUE),
    )
    common = {"source": source, "entry": image.header.pc0,
              "services": p11_05.SERVICE_SUBSET_B}
    result_a, sites_a, targets_a = structure_bridge.analyze_structure_with_overlays(
        pipeline.analysis,
        dynamic_observations={p11_05.DRIVER_METHOD_SITE: (p11_05.PROVEN_METHOD_POINTER,)},
        extensions=extra_a, merged_analysis=merged_a, **common,
    )
    result_b, sites_b, targets_b = structure_bridge.analyze_structure_with_overlays(
        pipeline.analysis,
        dynamic_observations={
            p11_05.DRIVER_METHOD_SITE: (p11_05.PROVEN_METHOD_POINTER,),
            TARGET_SITE: (TARGET_VALUE,),
        },
        extensions=extra_b, merged_analysis=merged_b, **common,
    )
    return {
        "image": image, "contract": contract, "flat": flat, "base": base,
        "result_a": result_a, "result_b": result_b,
        "sites_a": bios.resolved_sites(sites_a), "sites_b": bios.resolved_sites(sites_b),
        "site_document_b": sites_b, "targets_a": targets_a, "targets_b": targets_b,
        "extension_a": extension_a, "extension_b": extension_b,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-06")
    parser.add_argument("--private-fixture-root", default=str(p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    build_root = ROOT / ".openrecomp-phase11" / "build"

    try:
        private = build_extended_private(pathlib.Path(options.private_fixture_root))
        image = private["image"]
        contract = private["contract"]
        flat = private["flat"]

        # Exact provenance: P11-05 observed the value; the fixed pointer chain
        # and initial words explain it without guessing a target.
        initial = {
            address: memory_map.read_u32(contract, flat, address)
            for address in (TARGET_BASE_POINTER_ADDRESS, TARGET_FIELD_ADDRESS, GP1_POINTER_ADDRESS)
        }
        check("provenance:base-pointer",
              initial[TARGET_BASE_POINTER_ADDRESS] == 0x8002A244,
              f"0x{initial[TARGET_BASE_POINTER_ADDRESS]:08x}")
        check("provenance:target-field",
              initial[TARGET_FIELD_ADDRESS] == TARGET_VALUE,
              f"0x{initial[TARGET_FIELD_ADDRESS]:08x}")
        check("provenance:gp1-pointer",
              initial[GP1_POINTER_ADDRESS] == gpu_boundary.GP1_WRITE,
              f"0x{initial[GP1_POINTER_ADDRESS]:08x}")
        p11_05_diagnostic = json.loads(
            (ROOT / ".openrecomp-phase11/evidence/P11-05/diagnostic.json").read_text(
                encoding="utf-8"
            )
        )
        check("provenance:p11-05-guest-value",
              p11_05_diagnostic["classification"] == "GUEST_VALUE_CONFIRMED"
              and p11_05_diagnostic["argument_provenance"]["overlapping_writes_before_call"] == 0,
              p11_05_diagnostic["classification"])
        site_block = next(
            block for unit in private["result_a"].units.units for block in unit.blocks
            if block.instructions[-1].address == TARGET_SITE
        )
        site_ops = {instruction.address: instruction for instruction in site_block.instructions}
        site_load = site_ops[0x80018824]
        site_call = site_ops[TARGET_SITE]
        check("provenance:field-load",
              site_load.op == "lw"
              and site_load.metadata["operands"] == {"rs": 2, "rt": 2, "imm": 16},
              json.dumps(site_load.metadata["operands"], sort_keys=True))
        check("provenance:indirect-source",
              site_call.op == "jalr" and site_call.metadata["operands"]["rs"] == 2,
              json.dumps(site_call.metadata["operands"], sort_keys=True))

        extension = private["extension_b"]
        added = [item for item in extension["extra_entries"]
                 if item["entry"] == "0x8001a7dc"]
        check("extension:target-exact",
              added == [{"entry": "0x8001a7dc", "reachable_words": 10,
                         "new_reachable_words": 10}], json.dumps(added, sort_keys=True))
        check("extension:merged-count",
              extension["merged_reachable_words"] == 4342
              and extension["delay_slot_count"] == 683,
              json.dumps(extension, sort_keys=True))
        target_units = [unit for unit in private["result_b"].units.units
                        if unit.entry_address == TARGET_VALUE]
        check("extension:target-function",
              len(target_units) == 1 and target_units[0].function_id == "fn_8001a7dc"
              and len(target_units[0].blocks) == 1, str(len(target_units)))
        target_resolution = [item for item in private["targets_b"]["resolved"]
                             if item["site"] == "0x8001882c"]
        check("dynamic:exact-guarded-resolution",
              len(target_resolution) == 1
              and target_resolution[0]["basis"] == "EXACT_CONSTANT_TARGET"
              and target_resolution[0]["targets"] == ["0x8001a7dc"]
              and target_resolution[0]["guarded"] is True,
              json.dumps(target_resolution, sort_keys=True))
        target_instructions = [instruction for block in target_units[0].blocks
                               for instruction in block.instructions]
        target_ops = {instruction.address: instruction for instruction in target_instructions}
        check("target:typed-port-load",
              target_ops[0x8001A7E0].op == "lw"
              and target_ops[0x8001A7E0].metadata["operands"]["imm"] == -23712,
              "fixed GP1 pointer load")
        check("target:guest-store",
              target_ops[0x8001A7E8].op == "sw"
              and target_ops[0x8001A7E8].metadata["operands"] == {"rs": 2, "rt": 4, "imm": 0},
              "guest command store")
        check("target:ram-bookkeeping",
              target_ops[0x8001A7F8].op == "sb", "one guest RAM bookkeeping byte")

        # Original public fixtures independently exercise the unchanged typed
        # GP1 classifier, including its fail-closed unknown-command path.
        public_records: list[dict] = []
        for label, command, expected_failure, expected_class in (
            ("display-enable", GP1_COMMAND, False, "DISPLAY_ENABLE"),
            ("unknown-command", 0x09000000, True, "UNKNOWN_COMMAND"),
        ):
            synth = p11_05.structure_for_words(gp1_words(command))
            synth_image, synth_contract, synth_flat, synth_base, synth_result, synth_sites, _ = synth
            build_set = emission.build_bios_build_set(
                synth_result, synth_base, synth_contract, synth_flat, synth_image.file_sha256,
                sites=synth_sites, trace=True,
            )
            built = native.build_native(
                build_set, build_root / f"p11-06-public-{label}",
                fixture_id=f"p11-06-public-{label}", run_count=2,
            )
            check(f"synthetic:{label}:build",
                  all(status == "OK" for status in built["build_status"]),
                  str(built["build_status"]))
            check(f"synthetic:{label}:build-reproducible", built["build_reproducible"],
                  built["executable_sha256"])
            first, second = p11_05.run_both(built, timeout=300)
            check(f"synthetic:{label}:exit-stderr",
                  first["returncode"] == second["returncode"] == 0
                  and first["stderr_bytes"] == second["stderr_bytes"] == 0,
                  "exit 0 and empty stderr")
            check(f"synthetic:{label}:deterministic", first["stdout"] == second["stdout"],
                  first["stdout_sha256"])
            parsed = first["parsed"]
            classified = p11_05.classify_writes(parsed)
            check(f"synthetic:{label}:one-gp1-write",
                  len(classified) == 1 and classified[0]["address"] == "0x1f801814"
                  and classified[0]["value"] == f"0x{command:08x}",
                  json.dumps(classified, sort_keys=True))
            check(f"synthetic:{label}:classification",
                  classified[0]["classification"]["class"] == expected_class
                  and classified[0]["classification"]["known"] is (not expected_failure)
                  and classified[0]["classification"]["emulated"] is False,
                  json.dumps(classified[0]["classification"], sort_keys=True))
            check(f"synthetic:{label}:failure-policy",
                  (parsed.get("failed") == "1") is expected_failure,
                  str(parsed.get("failed")))
            check(f"synthetic:{label}:continuation",
                  (parsed["register_file"].get("r16") == "0x00000055") is (not expected_failure),
                  str(parsed["register_file"].get("r16")))
            check(f"synthetic:{label}:ram-unchanged",
                  parsed.get("memory") == p11_05.fnv1a64(synth_flat), parsed.get("memory"))
            public_records.append({
                "name": label, "command": f"0x{command:08x}",
                "classification": classified[0]["classification"],
                "failed": parsed.get("failed"), "stdout_sha256": first["stdout_sha256"],
            })

        # Private A/B: A is the committed P11-05 structure; B adds only the
        # independently observed target entry and guarded target evidence.
        build_set_a = emission.build_bios_build_set(
            private["result_a"], private["base"], contract, flat, image.file_sha256,
            sites=private["sites_a"], trace=True, guarded_resolved_indirect=True,
        )
        build_set_b = emission.build_bios_build_set(
            private["result_b"], private["base"], contract, flat, image.file_sha256,
            sites=private["sites_b"], trace=True, guarded_resolved_indirect=True,
        )
        check("emission:b-guarded-default",
              "indirect target outside proven set" in build_set_b["files"][emission.PROGRAM_NAME],
              "guarded default retained")
        build_a = native.build_native(
            build_set_a, build_root / "p11-06-private-a", fixture_id="p11-06-private-a",
            run_count=2,
        )
        build_b = native.build_native(
            build_set_b, build_root / "p11-06-private-b", fixture_id="p11-06-private-b",
            run_count=2,
        )
        for label, built in (("a", build_a), ("b", build_b)):
            check(f"private:{label}:build",
                  all(status == "OK" for status in built["build_status"]),
                  str(built["build_status"]))
            check(f"private:{label}:build-reproducible", built["build_reproducible"],
                  built["executable_sha256"])

        prefix_a, prefix_a_second = p11_05.run_both(
            build_a, access_budget=ACCESS_BUDGET, block_budget=PREFIX_BLOCK_BUDGET
        )
        prefix_b, prefix_b_second = p11_05.run_both(
            build_b, access_budget=ACCESS_BUDGET, block_budget=PREFIX_BLOCK_BUDGET
        )
        for label, first, second in (
            ("a", prefix_a, prefix_a_second), ("b", prefix_b, prefix_b_second)
        ):
            check(f"private:prefix-{label}:exit-stderr",
                  first["returncode"] == second["returncode"] == 0
                  and first["stderr_bytes"] == second["stderr_bytes"] == 0,
                  "exit 0 and empty stderr")
            check(f"private:prefix-{label}:deterministic", first["stdout"] == second["stdout"],
                  first["stdout_sha256"])
        check("private:prefix-byte-identical", prefix_a["stdout"] == prefix_b["stdout"],
              prefix_a["stdout_sha256"])

        full_a, full_a_second = p11_05.run_both(
            build_a, access_budget=ACCESS_BUDGET, block_budget=BLOCK_BUDGET
        )
        full_b, full_b_second = p11_05.run_both(
            build_b, access_budget=ACCESS_BUDGET, block_budget=BLOCK_BUDGET
        )
        for label, first, second in (
            ("a", full_a, full_a_second), ("b", full_b, full_b_second)
        ):
            check(f"private:full-{label}:exit-stderr",
                  first["returncode"] == second["returncode"] == 0
                  and first["stderr_bytes"] == second["stderr_bytes"] == 0,
                  "exit 0 and empty stderr")
            check(f"private:full-{label}:deterministic", first["stdout"] == second["stdout"],
                  first["stdout_sha256"])
        parsed_a = full_a["parsed"]
        parsed_b = full_b["parsed"]
        p11_05_frontier = json.loads(
            (ROOT / ".openrecomp-phase11/evidence/P11-05/frontier.json").read_text(
                encoding="utf-8"
            )
        )
        p11_05_observables = p11_05_frontier["private_run"]["observables"]
        mismatches = [key for key in p11_05.P11_04_OBSERVABLE_KEYS
                      if parsed_a.get(key) != p11_05_observables.get(key)]
        check("private:a-preserves-p11-05-observables", not mismatches,
              ",".join(mismatches) or "24 observables")
        failure_a = trace.analyze_trace(
            parsed_a, trace.StructureIndex(private["result_a"]), None
        )["failure"]
        failure_b = trace.analyze_trace(
            parsed_b, trace.StructureIndex(private["result_b"]), None
        )["failure"]
        check("private:a-exact-frontier",
              all(failure_a.get(key) == value for key, value in EXPECTED_A_FRONTIER.items()),
              json.dumps(failure_a, sort_keys=True))
        check("private:b-exact-frontier",
              all(failure_b.get(key) == value for key, value in EXPECTED_B_FRONTIER.items()),
              json.dumps(failure_b, sort_keys=True))
        writes_a = p11_05.classify_writes(parsed_a)
        writes_b = p11_05.classify_writes(parsed_b)
        check("private:a-one-gp0", len(writes_a) == 1
              and writes_a[0]["classification"]["class"] == "NOP",
              json.dumps(writes_a, sort_keys=True))
        check("private:b-ordered-gp0-gp1",
              [item["classification"]["port"] for item in writes_b] == ["GP0", "GP1"]
              and [item["value"] for item in writes_b] == ["0x0002a244", "0x03000001"]
              and [item["sequence"] for item in writes_b] == [0, 1],
              json.dumps(writes_b, sort_keys=True))
        check("private:b-gp1-classification",
              writes_b[1]["classification"] == {
                  "port": "GP1", "command": "0x03", "class": "DISPLAY_ENABLE",
                  "known": True, "emulated": False,
              }, json.dumps(writes_b[1]["classification"], sort_keys=True))
        check("private:b-no-gpu-blocker",
              parsed_b.get("gpu_blocker_writes") == "0"
              and parsed_b.get("gpu_known_writes") == "2",
              str((parsed_b.get("gpu_known_writes"), parsed_b.get("gpu_blocker_writes"))))
        check("private:b-not-host-shortcut",
              parsed_b.get("host_calls") == parsed_a.get("host_calls")
              and parsed_b.get("p10_service_calls") == parsed_a.get("p10_service_calls"),
              str((parsed_a.get("host_calls"), parsed_b.get("host_calls"))))
        check("private:b-one-guest-ram-write",
              int(parsed_b["writes"]) == int(parsed_a["writes"]) + 1,
              f"{parsed_a['writes']}/{parsed_b['writes']}")

        b0_sites = [item for item in private["site_document_b"]["sites"]
                    if item["site"] == 0x80015FA4]
        check("frontier:b0-57-classified-fail-closed",
              len(b0_sites) == 1 and b0_sites[0]["vector"] == "B0"
              and b0_sites[0]["function_index"] == 0x57
              and b0_sites[0]["classification"] == "BIOS_VECTOR_NOT_IMPLEMENTED"
              and b0_sites[0]["disposition"] == "FAIL_CLOSED",
              json.dumps(b0_sites, sort_keys=True))

        provenance_document = {
            "schema": "openrecomp-phase11-gpu-target-provenance-v1",
            "stage": STAGE,
            "site": "0x8001882c",
            "source_register": "$v0",
            "observed_target": "0x8001a7dc",
            "classification": "EXACT_CONSTANT_TARGET",
            "pointer_chain": {
                "base_pointer_address": "0x8002a284",
                "base_pointer_initial": "0x8002a244",
                "field_offset": 16,
                "effective_address": "0x8002a254",
                "field_initial": "0x8001a7dc",
                "runtime_loaded_value": "0x8001a7dc",
            },
            "extension": extension,
            "guarded_resolution": target_resolution[0],
            "target": {
                "entry": "0x8001a7dc", "reachable_words": 10,
                "functions_added": 1, "blocks_added": 1,
                "gp1_pointer_address": "0x8002a360",
                "gp1_pointer_initial": "0x1f801814",
            },
            "privacy": "addresses, counts, classifications and hashes only",
        }
        causal_document = {
            "schema": "openrecomp-phase11-gpu-closure-causal-ab-v1",
            "stage": STAGE,
            "budgets": {"access": ACCESS_BUDGET, "prefix_blocks": PREFIX_BLOCK_BUDGET,
                        "full_blocks": BLOCK_BUDGET},
            "prefix": {
                "byte_identical": True, "stdout_sha256": prefix_a["stdout_sha256"],
                "block_events": prefix_a["parsed"].get("trace_block_events"),
                "block_digest": prefix_a["parsed"].get("trace_block_digest"),
            },
            "a": {"failure": failure_a, "observables": p11_05.observables(parsed_a),
                  "gpu_writes": writes_a, "stdout_sha256": full_a["stdout_sha256"]},
            "b": {"failure": failure_b, "observables": p11_05.observables(parsed_b),
                  "gpu_writes": writes_b, "stdout_sha256": full_b["stdout_sha256"]},
            "required_delta": {
                "translated_blocks": 1, "typed_gp1_writes": 1,
                "guest_ram_writes": 1, "host_service_calls": 0,
            },
        }
        frontier_document = {
            "schema": "openrecomp-phase11-gpu-semantic-closure-frontier-v1",
            "stage": STAGE,
            "closure": {
                "status": "PROVEN_EXISTING_TYPED_PATH",
                "gpu_behavior_added": False, "dma_behavior_added": False,
                "vram_behavior_added": False, "renderer_added": False,
                "basis": "guarded target translation reaches frozen typed GP1 classifier",
            },
            "ordered_gpu_writes": writes_b,
            "new_frontier": {**failure_b, "bios_vector": "B0", "function_index": "0x57",
                             "classification": "BIOS_VECTOR_NOT_IMPLEMENTED"},
            "private_run": {
                "access_budget": ACCESS_BUDGET, "block_budget": BLOCK_BUDGET,
                "executable_sha256": build_b["executable_sha256"],
                "stdout_sha256": full_b["stdout_sha256"],
                "observables": p11_05.observables(parsed_b),
            },
            "public_synthetic": public_records,
        }
        for name, document in (("target_provenance.json", provenance_document),
                               ("causal_ab.json", causal_document),
                               ("frontier.json", frontier_document)):
            write_json(evidence / name, document)
            assert_private_safe(f"public:{name}", document, image.payload)

        check("claim:gpu-command-stream-retained", True, PROVEN)
        check("claim:initialization-not-promoted", True, NOT_PROVEN)
        check("claim:frame-not-promoted", True, NOT_PROVEN)
        check("claim:playability-not-promoted", True, NOT_PROVEN)
        check("claim:general-permanent", True, NOT_PROVEN)
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:
        RESULTS.append({"check": "gate:exception", "status": "FAIL",
                        "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    write_json(evidence / "p11_06_tests.json", {
        "stage": STAGE, "stage_name": "GPU/DMA/VRAM semantic closure",
        "status": status, "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed), "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    })
    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P11_06={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{GPU_MARKER}={PROVEN if status == 'PASS' else NOT_PROVEN}")
    print("OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN")
    print("OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN")
    print("OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN")
    print("OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
