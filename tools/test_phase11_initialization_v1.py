#!/usr/bin/env python3
"""Deterministic P11-04 initialization-completion gate.

The gate advances the exact audited fixture past the P11-03 frontier and
records the strongest proven initialization state:

* the frozen Phase-3 code frontier is re-run from the statically proven
  driver-method entry point and merged with the inherited frontier (records
  must agree exactly; reachable and delay-slot sets are unioned);
* the driver-method indirect call is resolved with explicit
  ``EXACT_CONSTANT_TARGET`` evidence and emitted with the additive guarded
  dispatch (any other runtime pointer fails closed);
* two newly reachable op types (``nor``, ``sllv``) receive architecture-exact
  additive rules verified by independent computation and a boundary case;
* public synthetic native fixtures verify the guarded dispatch both ways and
  the new rules;
* the private fixture reruns deterministically, the frontier moves again to
  the documented ``A0:0x49`` GPU_cw vector call, and initialization completion
  (milestone B) is **not** promoted: the exact remaining blocker is recorded.

On success it emits::

    OPENRECOMP_P11_04=PASS
    OPENRECOMP_PHASE11_INITIALIZATION_V1=PASS tests=<count>
    OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase11_initialization_v1.py
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

import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_fixture_identity_v1 as fixture  # noqa: E402
import p10_structure_v1 as p10_structure  # noqa: E402
import p11_bios_v1 as bios  # noqa: E402
import p11_dynamic_v1 as dynamic  # noqa: E402
import p11_emission_v1 as emission  # noqa: E402
import p11_native_v1 as native  # noqa: E402
import p11_semantics_v1 as semantics  # noqa: E402
import p11_structure_v1 as structure_bridge  # noqa: E402
import p11_trace_v1 as trace  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402
from tools import test_phase10_semantics_v1 as fixture_gate  # noqa: E402

STAGE = "P11-04"
FEATURE_MARKER = "OPENRECOMP_PHASE11_INITIALIZATION_V1"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE_ROOT = ROOT.parents[1] / "fixtures" / "psx" / "hercules"

FROZEN_PROGRAM_FINGERPRINT = "a047a52fb460d3786e5bff03b5c26ac2978ae768b581f5e6c4a9cbc284db4a9a"

SERVICE_SUBSET = {
    "A0": {
        0x2B: bios.DOCUMENTED_A0_SERVICES[0x2B],
        0x3F: bios.DOCUMENTED_A0_SERVICES[0x3F],
    },
    "B0": {},
    "C0": {},
}

PROVEN_METHOD_POINTER = 0x80016384
DRIVER_METHOD_SITE = 0x80016204

EXPECTED_FRONTIER = {
    "failure_site": "0x8001b424",
    "failure_source": "0x000000a0",
    "failure_message": "unresolved indirect jump",
    "failure_function": "0x8001b420",
    "failure_block": "blk_8001b420",
    "failure_block_index": 468286,
    "failure_count": 24,
    "block_events": 8000001,
    "bound_reached": "1",
    "bound_denials": "1",
    "host_calls": "83",
    "p10_service_failures": "0",
    "cdrom_events": "33",
    "spu_events": "0",
}

EXPECTED_EXTENSION = {
    "base_reachable_words": 4068,
    "merged_reachable_words": 4332,
    "extra_entry": "0x80016384",
    "extra_reachable_words": 281,
    "new_reachable_words": 264,
    "delay_slot_count": 682,
}

EXPECTED_STRUCTURE = {
    "functions": 121,
    "blocks": 793,
}

OBSERVABLE_KEYS = (
    "failed", "error", "exit_status", "registers", "memory",
    "gpu_events", "gpu", "input_events", "input", "spu_events", "spu",
    "cdrom_events", "cdrom", "reads", "writes", "denied", "host_calls",
    "p10_access_budget", "p10_access_count", "p10_budget_denials",
    "p10_service_calls", "p10_service_failures",
    "nonram_signatures", "nonram_overflow",
)

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _string_values(document):
    if isinstance(document, dict):
        for value in document.values():
            yield from _string_values(value)
    elif isinstance(document, list):
        for value in document:
            yield from _string_values(value)
    elif isinstance(document, str):
        yield document


def assert_no_payload_leak(label: str, document: dict, payload: bytes) -> None:
    text = json.dumps(document, sort_keys=True)
    lowered = text.lower()
    sample = payload[:64]
    check(f"{label}:no-hex", sample.hex() not in lowered, "payload hex present")
    check(
        f"{label}:no-base64",
        base64.b64encode(sample).decode("ascii") not in text,
        "payload base64 present",
    )
    for start in range(0, min(len(payload), 512)):
        run = payload[start : start + 8]
        if len(run) == 8 and all(32 <= byte < 127 for byte in run):
            check(
                f"{label}:no-ascii-run",
                run.decode("ascii") not in text,
                f"ascii payload run at {start}",
            )
    for value in _string_values(document):
        check(f"{label}:string-length", len(value) <= 128, f"{len(value)} chars")


def build_overlaid_structure(pipeline_analysis, contract, flat, header, fixture_sha256, *,
                             observations, extensions=(), merged=None):
    source = ProgramSource(
        "mips32-bounded-v1",
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=fixture_sha256,
    )
    base = p10_structure.analyze_structure(pipeline_analysis, source=source, entry=header.pc0)
    result, site_document, dynamic_document = structure_bridge.analyze_structure_with_overlays(
        pipeline_analysis,
        source=source,
        entry=header.pc0,
        services=SERVICE_SUBSET,
        dynamic_observations=observations,
        extensions=extensions,
        merged_analysis=merged,
    )
    return base, result, site_document, dynamic_document


def synthetic_overlay_words(words: list[int], *, observations: dict[int, tuple[int, ...]]):
    data = fixture_gate.builder.build_from_words(words, load_address=fixture_gate.LOAD)
    image = psx.ingest(data)
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    pipeline = bridge.analyze(image, contract, flat)
    source = ProgramSource(
        "mips32-bounded-v1",
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=image.file_sha256,
    )
    base = p10_structure.analyze_structure(pipeline.analysis, source=source, entry=image.header.pc0)
    result, _, dynamic_document = structure_bridge.analyze_structure_with_overlays(
        pipeline.analysis,
        source=source,
        entry=image.header.pc0,
        services={"A0": {}, "B0": {}, "C0": {}},
        dynamic_observations=observations,
    )
    return image, contract, flat, base, result, dynamic_document


def guarded_dispatch_words() -> list[int]:
    """A tiny program whose indirect call target must be guarded.

    The target (``0x80010028``) is a discovered function via the direct ``jal``,
    and the "wrong" observation target (``0x80010000``) is the reachable entry.
    """
    a = fixture_gate.Assembler()
    a.i("addiu", rt=8, imm=0)               # $t0 = 0
    a.jump("jal", "actual")                 # makes 0x80010028 a discovered function
    a.nop()
    a.i("lui", rt=2, imm=0x8001)
    a.i("ori", rs=2, rt=2, imm=0x0028)      # $v0 = 0x80010028
    a.r("jalr", rs=2, rd=31)                # site 0x80010014
    a.nop()
    a.i("addiu", rs=0, rt=31, imm=0)        # $ra = 0
    a.r("jr", rs=31)
    a.nop()
    a.label("actual")
    a.i("addiu", rs=0, rt=2, imm=2)         # actual target: $v0 = 2
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def nor_words() -> list[int]:
    a = fixture_gate.Assembler()
    a.i("lui", rt=8, imm=0x0F0F)
    a.i("ori", rs=8, rt=8, imm=0x0F0F)      # $t0 = 0x0F0F0F0F
    a.i("lui", rt=9, imm=0x00FF)
    a.i("ori", rs=9, rt=9, imm=0x00FF)      # $t1 = 0x00FF00FF
    a.r("nor", rs=8, rt=9, rd=10)           # $t2 = ~(0x0FFF0FFF) = 0xF000F000
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def sllv_words(shift: int) -> list[int]:
    a = fixture_gate.Assembler()
    a.i("addiu", rt=8, imm=shift)           # $t0 = shift amount
    a.i("addiu", rt=9, imm=1)               # $t1 = 1
    a.r("sllv", rs=8, rt=9, rd=10)          # $t2 = $t1 << ($t0 & 31)
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-04")
    parser.add_argument("--private-fixture-root", default=str(DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()

    evidence = (ROOT / options.evidence_dir).resolve()
    fixture_root = pathlib.Path(options.private_fixture_root)
    build_root = ROOT / ".openrecomp-phase11" / "build"

    try:
        # --- 1. frozen emitter output unchanged when new options are disabled --
        image = psx.ingest((fixture_root / fixture.PRIMARY_EXECUTABLE).read_bytes())
        contract = memory_map.build_contract(image)
        flat = memory_map.flat_image(image)
        header = image.header
        pipeline = bridge.analyze(image, contract, flat)
        source = ProgramSource(
            "mips32-bounded-v1",
            adapter="adapters.mips32",
            address_width_bits=32,
            endianness="little",
            input_sha256=image.file_sha256,
        )
        frozen_build = emission.uninstrumented_build_set(
            p10_structure.analyze_structure(pipeline.analysis, source=source, entry=header.pc0),
            contract, flat, image.file_sha256,
        )
        check(
            "emitter:disabled-byte-identical",
            frozen_build["program_fingerprint"] == FROZEN_PROGRAM_FINGERPRINT,
            frozen_build["program_fingerprint"],
        )

        # --- 2. frontier extension -------------------------------------------
        read_word = lambda address: memory_map.read_u32(contract, flat, address)
        merged, extension_document, extra_analyses = dynamic.extend_analysis(
            pipeline.analysis, read_word, header.t_addr, header.t_addr + header.t_size,
            (PROVEN_METHOD_POINTER,),
        )
        check(
            "extension:base-reachable",
            extension_document["base_reachable_words"] == EXPECTED_EXTENSION["base_reachable_words"],
            str(extension_document["base_reachable_words"]),
        )
        check(
            "extension:merged-reachable",
            extension_document["merged_reachable_words"] == EXPECTED_EXTENSION["merged_reachable_words"],
            str(extension_document["merged_reachable_words"]),
        )
        check(
            "extension:entry",
            extension_document["extra_entries"][0]["entry"] == EXPECTED_EXTENSION["extra_entry"]
            and extension_document["extra_entries"][0]["reachable_words"] == EXPECTED_EXTENSION["extra_reachable_words"]
            and extension_document["extra_entries"][0]["new_reachable_words"] == EXPECTED_EXTENSION["new_reachable_words"],
            json.dumps(extension_document["extra_entries"], sort_keys=True),
        )
        check(
            "extension:delay-slots",
            extension_document["delay_slot_count"] == EXPECTED_EXTENSION["delay_slot_count"],
            str(extension_document["delay_slot_count"]),
        )
        # Fail-closed negatives.
        try:
            dynamic.extend_analysis(pipeline.analysis, read_word, header.t_addr,
                                    header.t_addr + header.t_size, (0x80016385,))
            unaligned_rejected = False
        except dynamic.DynamicResolutionError:
            unaligned_rejected = True
        check("extension:unaligned-entry-rejected", unaligned_rejected, "unaligned entry fails closed")
        try:
            dynamic.extend_analysis(pipeline.analysis, read_word, header.t_addr,
                                    header.t_addr + header.t_size, (header.t_addr - 4,))
            outside_rejected = False
        except dynamic.DynamicResolutionError:
            outside_rejected = True
        check("extension:outside-region-rejected", outside_rejected, "outside entry fails closed")
        try:
            dynamic.resolve_sites(pipeline.analysis, observations={DRIVER_METHOD_SITE: (0x80000000,)},
                                  site_units={DRIVER_METHOD_SITE: ("fn_800161ec", "blk_800161ec")})
            unreachable_rejected = False
        except dynamic.DynamicResolutionError:
            unreachable_rejected = True
        check("dynamic:unreachable-target-rejected", unreachable_rejected, "unreachable target fails closed")

        # --- 3. overlaid structure and dynamic resolution ---------------------
        base_result, result, site_document, dynamic_document = build_overlaid_structure(
            pipeline.analysis, contract, flat, header, image.file_sha256,
            observations={DRIVER_METHOD_SITE: (PROVEN_METHOD_POINTER,)},
            extensions=extra_analyses, merged=merged,
        )
        check(
            "structure:functions",
            len(result.units.units) == EXPECTED_STRUCTURE["functions"],
            str(len(result.units.units)),
        )
        check(
            "structure:blocks",
            sum(len(unit.blocks) for unit in result.units.units) == EXPECTED_STRUCTURE["blocks"],
            str(sum(len(unit.blocks) for unit in result.units.units)),
        )
        check(
            "structure:proven-entry-translated",
            any(unit.entry_address == PROVEN_METHOD_POINTER for unit in result.units.units),
            "the driver method is translated",
        )
        check(
            "dynamic:resolved",
            dynamic_document["resolved_count"] == 1
            and dynamic_document["resolved"][0]["site"] == "0x80016204"
            and dynamic_document["resolved"][0]["basis"] == "EXACT_CONSTANT_TARGET"
            and dynamic_document["resolved"][0]["targets"] == ["0x80016384"]
            and dynamic_document["resolved"][0]["guarded"] is True,
            json.dumps(dynamic_document, sort_keys=True),
        )
        classified = None
        for unit in result.classification.units:
            for item in unit.classifications:
                if item.address == DRIVER_METHOD_SITE:
                    classified = item
        check("dynamic:classifier-resolved", classified is not None and classified.status.value == "RESOLVED",
              classified.status.value if classified else "missing")
        check(
            "dynamic:classifier-target",
            classified.targets == (PROVEN_METHOD_POINTER,),
            str(classified.targets),
        )
        check(
            "semantics:added-ops",
            list(semantics.ADDED_OPS) == ["nor", "sllv"],
            ",".join(semantics.ADDED_OPS),
        )
        table = semantics.build_semantics(bios.resolved_sites(site_document))
        check("semantics:nor-rule", table.has(semantics.ARCHITECTURE, "nor"), "nor rule present")
        check("semantics:sllv-rule", table.has(semantics.ARCHITECTURE, "sllv"), "sllv rule present")

        # --- 4. synthetic guarded dispatch and new rules ----------------------
        synthetic_records: list[dict] = []
        site = 0x80010014
        guarded_cases = (
            ("guarded-dispatch-taken", {site: (0x80010028,)}, {"failed": "0", "error": "", "r02": "0x00000002"}),
            ("guarded-dispatch-default", {site: (0x80010000,)},
             {"failed": "1", "error": "indirect target outside proven set"}),
        )
        for name, observations, expectations in guarded_cases:
            synth_image, synth_contract, synth_flat, synth_base, synth_result, synth_dynamic = synthetic_overlay_words(
                guarded_dispatch_words(), observations=observations
            )
            synth_build = emission.build_bios_build_set(
                synth_result, synth_base, synth_contract, synth_flat, synth_image.file_sha256,
                sites=(), trace=False, guarded_resolved_indirect=True,
            )
            check(f"synthetic:{name}:guarded-emitted",
                  "indirect target outside proven set" in synth_build["files"][emission.PROGRAM_NAME],
                  "guarded default present")
            synth_native = native.build_native(
                synth_build, build_root / f"p11-04-{name}", fixture_id=f"p11-04-{name}", run_count=2
            )
            synth_run = native.run_native(synth_native["executables"][0], timeout=300)
            synth_second = native.run_native(synth_native["executables"][0], timeout=300)
            check(f"synthetic:{name}:deterministic",
                  synth_run["stdout_sha256"] == synth_second["stdout_sha256"], synth_run["stdout_sha256"])
            synth_parsed = synth_run["parsed"]
            for key, expected in sorted(expectations.items()):
                observed = (synth_parsed["register_file"].get(key) if key in synth_parsed["register_file"]
                            else synth_parsed.get(key))
                check(f"synthetic:{name}:{key}", observed == expected, str(observed))
            synthetic_records.append(
                {
                    "name": name,
                    "executable_sha256": synth_native["executable_sha256"],
                    "stdout_sha256": synth_run["stdout_sha256"],
                    "failed": synth_parsed.get("failed"),
                    "error": synth_parsed.get("error"),
                    "return_value": synth_parsed["register_file"].get("r02"),
                    "expected": expectations,
                }
            )
        for name, words, expectations in (
            ("nor-rule", nor_words(), {"failed": "0", "error": "", "r10": "0xf000f000"}),
            ("sllv-rule", sllv_words(3), {"failed": "0", "error": "", "r10": "0x00000008"}),
            ("sllv-mask-boundary", sllv_words(33), {"failed": "0", "error": "", "r10": "0x00000002"}),
        ):
            synth_image, synth_contract, synth_flat, synth_base, synth_result, _ = synthetic_overlay_words(
                words, observations={}
            )
            synth_build = emission.build_bios_build_set(
                synth_result, synth_base, synth_contract, synth_flat, synth_image.file_sha256,
                sites=(), trace=False,
            )
            synth_native = native.build_native(
                synth_build, build_root / f"p11-04-{name}", fixture_id=f"p11-04-{name}", run_count=2
            )
            synth_run = native.run_native(synth_native["executables"][0], timeout=300)
            synth_second = native.run_native(synth_native["executables"][0], timeout=300)
            check(f"synthetic:{name}:deterministic",
                  synth_run["stdout_sha256"] == synth_second["stdout_sha256"], synth_run["stdout_sha256"])
            synth_parsed = synth_run["parsed"]
            for key, expected in sorted(expectations.items()):
                observed = (synth_parsed["register_file"].get(key) if key in synth_parsed["register_file"]
                            else synth_parsed.get(key))
                check(f"synthetic:{name}:{key}", observed == expected, str(observed))
            synthetic_records.append(
                {
                    "name": name,
                    "executable_sha256": synth_native["executable_sha256"],
                    "stdout_sha256": synth_run["stdout_sha256"],
                    "failed": synth_parsed.get("failed"),
                    "error": synth_parsed.get("error"),
                    "return_value": synth_parsed["register_file"].get("r10"),
                    "expected": expectations,
                }
            )
        # independent computation of the two new rules
        check(
            "synthetic:nor-independent",
            (~(0x0F0F0F0F | 0x00FF00FF) & 0xFFFFFFFF) == 0xF000F000,
            "python reference agrees with the nor rule",
        )
        check(
            "synthetic:sllv-independent",
            ((1 << (3 & 31)) & 0xFFFFFFFF) == 8 and ((1 << (33 & 31)) & 0xFFFFFFFF) == 2,
            "python reference agrees with the sllv masking semantics",
        )

        # --- 5. private frontier ----------------------------------------------
        sites = bios.resolved_sites(site_document)
        build_set = emission.build_bios_build_set(
            result, base_result, contract, flat, image.file_sha256, sites=sites, trace=True,
            guarded_resolved_indirect=True,
        )
        check(
            "emission:base-identity",
            build_set["base_program_fingerprint"] == FROZEN_PROGRAM_FINGERPRINT,
            build_set["base_program_fingerprint"],
        )
        check(
            "emission:guarded-default",
            "indirect target outside proven set" in build_set["files"][emission.PROGRAM_NAME],
            "guarded default present",
        )
        native_build = native.build_native(
            build_set, build_root / "p11-04-frontier", fixture_id="p11-04-frontier"
        )
        check("native:build", all(status == "OK" for status in native_build["build_status"]),
              str(native_build["build_status"]))
        check("native:reproducible", native_build["build_reproducible"] is True,
              native_build["executable_sha256"])
        frontier_run = native.run_native(
            native_build["executables"][0], access_budget=1500000, block_budget=8000000, timeout=900
        )
        frontier_second = native.run_native(
            native_build["executables"][0], access_budget=1500000, block_budget=8000000, timeout=900
        )
        check("frontier:deterministic", frontier_run["stdout_sha256"] == frontier_second["stdout_sha256"],
              frontier_run["stdout_sha256"])
        traced = frontier_run["parsed"]
        for key, expected in sorted(EXPECTED_FRONTIER.items()):
            if key in ("failure_site", "failure_source", "failure_message", "failure_function",
                       "failure_block", "failure_block_index", "failure_count", "block_events"):
                continue
            check(f"frontier:{key}", traced.get(key) == expected, str(traced.get(key)))
        index = trace.StructureIndex(result)
        analysis = trace.analyze_trace(traced, index, None)
        failure = analysis["failure"]
        check("frontier:site", failure["site"] == EXPECTED_FRONTIER["failure_site"], failure["site"])
        check("frontier:source", failure["source_value"] == EXPECTED_FRONTIER["failure_source"],
              str(failure["source_value"]))
        check("frontier:message", failure["message"] == EXPECTED_FRONTIER["failure_message"],
              str(failure["message"]))
        check(
            "frontier:function-and-block",
            failure["function_entry"] == EXPECTED_FRONTIER["failure_function"]
            and failure["block_id"] == EXPECTED_FRONTIER["failure_block"],
            f"{failure['function_entry']}/{failure['block_id']}",
        )
        check("frontier:block-index", failure["block_index"] == EXPECTED_FRONTIER["failure_block_index"],
              str(failure["block_index"]))
        check("frontier:failure-count", failure["failure_count"] == EXPECTED_FRONTIER["failure_count"],
              str(failure["failure_count"]))
        check(
            "frontier:moved-past-driver-method",
            failure["site"] not in ("0x80016204", "0x80026cec", "0x80026ccc")
            and failure["block_index"] > 468281,
            f"{failure['site']} @ {failure['block_index']}",
        )
        check(
            "frontier:next-blocker-is-gpu-cw",
            any(item["site_hex"] == "0x8001b424" and item["function_index"] == 0x49
                for item in site_document["sites"]),
            "A0:0x49 is the next documented blocker",
        )

        # --- 6. evidence -------------------------------------------------------
        frontier_document = {
            "schema": "openrecomp-phase11-initialization-frontier-v1",
            "stage": STAGE,
            "label": "hercules-private-fixture",
            "milestone_b": {
                "established": False,
                "reason": [
                    "initialization does not complete: the next fail-closed event is the",
                    "documented A0:0x49 GPU_cw vector call at 0x8001b424; milestone B is",
                    "NOT promoted",
                ],
            },
            "frontier_extension": extension_document,
            "dynamic_resolution": dynamic_document,
            "structure": {
                "functions": len(result.units.units),
                "blocks": sum(len(unit.blocks) for unit in result.units.units),
                "proven_entry": f"0x{PROVEN_METHOD_POINTER:08x}",
            },
            "added_semantics": {
                "added_ops": list(semantics.ADDED_OPS),
                "verified_by": "independent python computation plus boundary case",
            },
            "emission": {
                "program_fingerprint": build_set["program_fingerprint"],
                "base_program_fingerprint": build_set["base_program_fingerprint"],
                "guarded_resolved_indirect": True,
                "files": [
                    {"name": name, "sha256": build_set["hashes"][name],
                     "bytes": len(build_set["files"][name].encode("utf-8"))}
                    for name in emission.EMISSION_NAMES
                ],
            },
            "frontier_run": {
                "access_budget": 1500000,
                "block_budget": 8000000,
                "executable_sha256": native_build["executable_sha256"],
                "stdout_sha256": frontier_run["stdout_sha256"],
                "observables": {key: traced.get(key) for key in OBSERVABLE_KEYS},
                "trace": {
                    key: traced.get(key) for key in (
                        "trace_block_events", "trace_block_digest", "trace_distinct_blocks",
                        "trace_distinct_functions", "trace_failure_count", "trace_failure_site",
                        "trace_failure_source", "trace_failure_message",
                        "trace_failure_block_index", "trace_failure_function",
                        "bound_budget", "bound_reached", "bound_denials",
                    )
                },
                "analysis": analysis,
            },
            "synthetic_fixtures": synthetic_records,
            "frontier_movement": {
                "p11_01": "0x80026ccc @ 9424",
                "p11_02": "0x80026cec @ 468147",
                "p11_03": "0x80016204 @ 468281",
                "p11_04": "0x8001b424 @ 468286",
            },
        }
        write_json(evidence / "frontier.json", frontier_document)
        assert_no_payload_leak("public:frontier", frontier_document, image.payload)

        identity = fixture.build_identity(fixture_root)
        provenance = cache_provenance = None
        import p11_cache_v1 as cache

        provenance = cache.build_provenance(identity, traced=True)
        provenance["bios_site_plan_digest"] = hashlib.sha256(
            json.dumps(bios.site_plan(site_document), sort_keys=True).encode("utf-8")
        ).hexdigest()
        provenance["dynamic_target_digest"] = hashlib.sha256(
            json.dumps(dynamic_document["resolved"], sort_keys=True).encode("utf-8")
        ).hexdigest()
        phase_cache = cache.Phase11Cache(ROOT / ".openrecomp-phase11" / "cache")
        document = {"stage": STAGE, "services": [site.service_id for site in sites]}
        key = phase_cache.store(provenance, document)
        check("cache:hit", phase_cache.lookup(provenance) == document, "stored document returned")
        stale = dict(provenance)
        stale["dynamic_target_digest"] = "0" * 64
        check("cache:dynamic-target-miss", phase_cache.key(stale) != key and phase_cache.lookup(stale) is None,
              "dynamic target set is part of the key")

        check("claim:initialization-not-promoted", True, NOT_PROVEN)
        check("claim:frame-not-promoted", True, NOT_PROVEN)
        check("claim:playability-not-promoted", True, NOT_PROVEN)
        check("claim:general-permanent", True, NOT_PROVEN)
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    stage_record = {
        "stage": STAGE,
        "stage_name": "Milestone B: initialization completion",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p11_04_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P11_04={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{INITIALIZATION_MARKER}={NOT_PROVEN}")
    print(f"{FRAME_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
