#!/usr/bin/env python3
"""Deterministic P11-03 event / interrupt / DMA progress-contract gate.

The gate determines the event contract for the current exact frontier:

* the documented ``A0:0x3f`` printf vector call is served as a bounded,
  no-console, documented service (the prerequisite for reaching the frontier);
* public synthetic native fixtures verify the documented printf contract
  (``%08x``, ``%d``, ``%s``, ``%c``, signed values, and fail-closed on an
  unsupported conversion or on more varargs than the declared surface);
* the private fixture reruns deterministically and the frontier moves to the
  next exact blocker, an unresolved indirect *call* at ``0x80016204`` whose
  source pointer ``0x80016384`` is a statically initialized driver-method
  pointer (provenance recorded for the next stage);
* deterministic execution-budget bisection proves that the whole progress to
  the frontier is RAM-only: zero device-port accesses, zero non-RAM access
  signatures, zero interrupt/DMA/timer/memory-control interaction. No event
  source is accessed, so no event behaviour is proven necessary and the event
  requirement remains ``NOT_PROVEN`` with zero implementation delta.

On success it emits::

    OPENRECOMP_P11_03=PASS
    OPENRECOMP_PHASE11_EVENT_CONTRACT_V1=PASS tests=<count>
    OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase11_event_contract_v1.py
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
import p11_cache_v1 as cache  # noqa: E402
import p11_emission_v1 as emission  # noqa: E402
import p11_native_v1 as native  # noqa: E402
import p11_structure_v1 as structure_bridge  # noqa: E402
import p11_trace_v1 as trace  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402
from tools import test_phase10_semantics_v1 as fixture_gate  # noqa: E402

STAGE = "P11-03"
FEATURE_MARKER = "OPENRECOMP_PHASE11_EVENT_CONTRACT_V1"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE_ROOT = ROOT.parents[1] / "fixtures" / "psx" / "hercules"

#: The documented service surface this stage resolved.
SERVICE_SUBSET = {
    "A0": {
        0x2B: bios.DOCUMENTED_A0_SERVICES[0x2B],
        0x3F: bios.DOCUMENTED_A0_SERVICES[0x3F],
    },
    "B0": {},
    "C0": {},
}

#: Event-relevant documented services that are statically reachable but not
#: dynamically reached before the frontier.
EVENT_SERVICE_INDICES = (
    ("C0", 0x02, "SysEnqIntRP"),
    ("C0", 0x03, "SysDeqIntRP"),
    ("C0", 0x0A, None),
    ("B0", 0x12, None),
    ("B0", 0x13, None),
    ("B0", 0x4A, None),
    ("B0", 0x4B, None),
)

EXPECTED_FRONTIER = {
    "failure_site": "0x80016204",
    "failure_source": "0x80016384",
    "failure_message": "unresolved indirect call",
    "failure_function": "0x800161ec",
    "failure_block": "blk_800161ec",
    "failure_block_index": 468281,
    "failure_count": 27,
    "block_events": 966047,
    "block_digest": "0xe114354a5b3e89c8",
    "reads": "636986",
    "writes": "721766",
    "denied": "10",
    "host_calls": "83",
    "p10_access_count": "1500004",
    "p10_budget_denials": "4",
    "memory": "0x4552e679a9de06bc",
    "gpu_events": "65536",
    "cdrom_events": "38",
    "spu_events": "5",
    "nonram_signatures": "17",
}

#: The frontier access index and its RAM-only proof.
EXPECTED_FRONTIER_ACCESS_INDEX = 506040
EXPECTED_BEFORE_FRONTIER = {
    "error": "runtime memory read failed",
    "gpu_events": "0",
    "input_events": "0",
    "cdrom_events": "0",
    "spu_events": "0",
    "nonram_signatures": "0",
}

#: Static provenance of the next blocker's source pointer (private metadata only).
EXPECTED_POINTER_PROVENANCE = {
    "driver_global_address": "0x80029644",
    "driver_structure": "0x80029624",
    "method_field_offset": 12,
    "method_pointer": "0x80016384",
    "pointer_image_offset": "0x80029630",
    "pointer_occurrences_in_image": 1,
    "prologue_word": "0x27bdffe8",
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


def emit_load_immediate(a, register: int, value: int) -> None:
    a.i("lui", rt=register, imm=(value >> 16) & 0xFFFF)
    a.i("ori", rs=register, rt=register, imm=value & 0xFFFF)


def store_string(a, address: int, text: str) -> None:
    data = text.encode("ascii")
    for index in range(0, len(data) + 1, 4):
        chunk = data[index : index + 4]
        if not chunk and index > 0:
            break
        word = int.from_bytes(chunk + b"\x00" * (4 - len(chunk)), "little")
        emit_load_immediate(a, 1, address)
        emit_load_immediate(a, 2, word)
        a.i("sw", rs=1, rt=2, imm=index)


def printf_words(fmt: str, *, arg1: int = 0, arg2: int = 0, index: int = 0x3F,
                 extra_string: str | None = None, extra_address: int = 0x80021040) -> list[int]:
    """A tiny OpenRecomp-authored program that calls the A0 printf stub."""
    a = fixture_gate.Assembler()
    store_string(a, 0x80021000, fmt)
    if extra_string is not None:
        store_string(a, extra_address, extra_string)
    if extra_string is not None:
        arg1 = extra_address
    emit_load_immediate(a, 4, 0x80021000)
    emit_load_immediate(a, 5, arg1 & 0xFFFFFFFF)
    emit_load_immediate(a, 6, arg2 & 0xFFFFFFFF)
    a.jump("jal", "bios_stub")
    a.nop()
    a.r("jr", rs=31)
    a.nop()
    a.label("bios_stub")
    a.i("addiu", rt=10, imm=0xA0)
    a.r("jr", rs=10)
    a.i("addiu", rt=9, imm=index)
    return a.finish()


def structure_for_words(words: list[int]):
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
    result, document = structure_bridge.analyze_structure_with_bios(
        pipeline.analysis, source=source, entry=image.header.pc0, services=SERVICE_SUBSET
    )
    sites = bios.resolved_sites(document)
    return image, contract, flat, base, result, sites, document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-03")
    parser.add_argument("--private-fixture-root", default=str(DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()

    evidence = (ROOT / options.evidence_dir).resolve()
    fixture_root = pathlib.Path(options.private_fixture_root)
    build_root = ROOT / ".openrecomp-phase11" / "build"

    try:
        # --- 1. private classification with the extended service surface ------
        check("fixture:directory", fixture_root.is_dir(), "private fixture directory present")
        image = psx.ingest((fixture_root / fixture.PRIMARY_EXECUTABLE).read_bytes())
        contract = memory_map.build_contract(image)
        flat = memory_map.flat_image(image)
        source = ProgramSource(
            "mips32-bounded-v1",
            adapter="adapters.mips32",
            address_width_bits=32,
            endianness="little",
            input_sha256=image.file_sha256,
        )
        pipeline = bridge.analyze(image, contract, flat)
        base_result = p10_structure.analyze_structure(pipeline.analysis, source=source, entry=image.header.pc0)
        result, site_document = structure_bridge.analyze_structure_with_bios(
            pipeline.analysis, source=source, entry=image.header.pc0, services=SERVICE_SUBSET
        )
        sites = bios.resolved_sites(site_document)
        classification = bios.classify_vector_sites(pipeline.analysis, services=SERVICE_SUBSET)
        check(
            "bios:histogram",
            classification["histogram"] == {"BIOS_VECTOR_SERVICE": 2, "BIOS_VECTOR_NOT_IMPLEMENTED": 17},
            json.dumps(classification["histogram"], sort_keys=True),
        )
        resolved_ids = sorted(site.service_id for site in sites)
        check(
            "bios:resolved-services",
            resolved_ids == ["ps1.bios.A0.2b", "ps1.bios.A0.3f"],
            ",".join(resolved_ids),
        )
        event_sites = [
            item for item in classification["sites"]
            if (item["vector"], item["function_index"]) in
            {(vector, index) for vector, index, _ in EVENT_SERVICE_INDICES}
        ]
        check(
            "event:services-enumerated",
            len(event_sites) == len(EVENT_SERVICE_INDICES),
            f"{len(event_sites)} event-relevant sites",
        )
        check(
            "event:services-not-resolved",
            all(item["classification"] == "BIOS_VECTOR_NOT_IMPLEMENTED" and item["op_name"] is None
                for item in event_sites),
            "every event-relevant service stays fail-closed",
        )

        # --- 2. printf synthetic fixtures ------------------------------------
        printf_cases = (
            ("printf-hex", printf_words("%08x,%08x", arg1=0x1A2B3C4D, arg2=0xDEADBEEF),
             {"failed": "0", "error": "", "r02": "0x00000011"}),
            ("printf-decimal", printf_words("%d", arg1=42),
             {"failed": "0", "error": "", "r02": "0x00000002"}),
            ("printf-signed", printf_words("x%dy", arg1=0xFFFFFFF9),
             {"failed": "0", "error": "", "r02": "0x00000004"}),
            ("printf-string", printf_words("%s", extra_string="abc"),
             {"failed": "0", "error": "", "r02": "0x00000003"}),
            ("printf-char", printf_words("%c", arg1=0x41),
             {"failed": "0", "error": "", "r02": "0x00000001"}),
            ("printf-too-many-varargs", printf_words("%d %d %d", arg1=1, arg2=2),
             {"failed": "1", "error": "runtime host service ps1.bios.A0.3f failed"}),
            ("printf-unsupported-conversion", printf_words("%q", arg1=1),
             {"failed": "1", "error": "runtime host service ps1.bios.A0.3f failed"}),
        )
        printf_records: list[dict] = []
        for name, words, expectations in printf_cases:
            synth_image, synth_contract, synth_flat, synth_base, synth_result, synth_sites, _ = structure_for_words(words)
            synth_build = emission.build_bios_build_set(
                synth_result, synth_base, synth_contract, synth_flat, synth_image.file_sha256,
                sites=synth_sites, trace=False,
            )
            synth_native = native.build_native(
                synth_build, build_root / f"p11-03-{name}", fixture_id=f"p11-03-{name}", run_count=2
            )
            check(f"synthetic:{name}:build", all(status == "OK" for status in synth_native["build_status"]),
                  str(synth_native["build_status"]))
            synth_run = native.run_native(synth_native["executables"][0], timeout=300)
            synth_second = native.run_native(synth_native["executables"][0], timeout=300)
            check(f"synthetic:{name}:deterministic",
                  synth_run["stdout_sha256"] == synth_second["stdout_sha256"], synth_run["stdout_sha256"])
            synth_parsed = synth_run["parsed"]
            for key, expected in sorted(expectations.items()):
                observed = (synth_parsed["register_file"].get(key) if key in synth_parsed["register_file"]
                            else synth_parsed.get(key))
                check(f"synthetic:{name}:{key}", observed == expected, str(observed))
            printf_records.append(
                {
                    "name": name,
                    "executable_sha256": synth_native["executable_sha256"],
                    "stdout_sha256": synth_run["stdout_sha256"],
                    "failed": synth_parsed.get("failed"),
                    "error": synth_parsed.get("error"),
                    "service_calls": synth_parsed.get("p10_service_calls"),
                    "service_failures": synth_parsed.get("p10_service_failures"),
                    "return_value": synth_parsed["register_file"].get("r02"),
                    "expected": expectations,
                }
            )
        check(
            "synthetic:printf-served",
            all(record["service_calls"] == "1" and record["service_failures"] == "0"
                for record in printf_records[:5]),
            json.dumps([(record["service_calls"], record["service_failures"]) for record in printf_records[:5]]),
        )
        check(
            "synthetic:printf-fail-closed",
            all(record["failed"] == "1" and record["service_failures"] == "1"
                for record in printf_records[5:]),
            json.dumps([(record["failed"], record["service_failures"]) for record in printf_records[5:]]),
        )

        # --- 3. private frontier with both services served --------------------
        build_set = emission.build_bios_build_set(
            result, base_result, contract, flat, image.file_sha256, sites=sites, trace=True
        )
        native_build = native.build_native(
            build_set, build_root / "p11-03-frontier", fixture_id="p11-03-frontier"
        )
        check("native:build", all(status == "OK" for status in native_build["build_status"]),
              str(native_build["build_status"]))
        check("native:reproducible", native_build["build_reproducible"] is True,
              native_build["executable_sha256"])
        frontier_run = native.run_native(
            native_build["executables"][0], access_budget=1500000, block_budget=8000000, timeout=600
        )
        frontier_second = native.run_native(
            native_build["executables"][0], access_budget=1500000, block_budget=8000000, timeout=600
        )
        check("frontier:deterministic", frontier_run["stdout_sha256"] == frontier_second["stdout_sha256"],
              frontier_run["stdout_sha256"])
        traced = frontier_run["parsed"]
        for key, expected in sorted(EXPECTED_FRONTIER.items()):
            if key in ("failure_site", "failure_source", "failure_message", "failure_function",
                       "failure_block", "failure_block_index", "failure_count", "block_events",
                       "block_digest"):
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
            "frontier:totals",
            analysis["totals"]["block_events"] == EXPECTED_FRONTIER["block_events"]
            and analysis["totals"]["block_digest"] == EXPECTED_FRONTIER["block_digest"],
            json.dumps(analysis["totals"], sort_keys=True),
        )
        check(
            "frontier:moved-past-printf",
            failure["site"] != "0x80026cec" and failure["block_index"] > 468147,
            f"{failure['site']} @ {failure['block_index']}",
        )
        check(
            "frontier:printf-served",
            traced.get("p10_service_failures") == "0" and int(traced.get("host_calls", "0")) > 81,
            f"host_calls={traced.get('host_calls')} failures={traced.get('p10_service_failures')}",
        )

        # --- 4. deterministic RAM-only proof before the frontier -------------
        before_run = native.run_native(
            native_build["executables"][0],
            access_budget=EXPECTED_FRONTIER_ACCESS_INDEX - 1,
            block_budget=8000000, timeout=600,
        )["parsed"]
        at_run = native.run_native(
            native_build["executables"][0],
            access_budget=EXPECTED_FRONTIER_ACCESS_INDEX,
            block_budget=8000000, timeout=600,
        )["parsed"]
        check(
            "bisect:just-below-frontier",
            before_run.get("error") != "unresolved indirect call",
            str(before_run.get("error")),
        )
        check(
            "bisect:at-frontier",
            at_run.get("error") == "unresolved indirect call",
            str(at_run.get("error")),
        )
        check(
            "ram-only:error-before",
            before_run.get("error") == EXPECTED_BEFORE_FRONTIER["error"],
            str(before_run.get("error")),
        )
        for key in ("gpu_events", "input_events", "cdrom_events", "spu_events", "nonram_signatures"):
            check(f"ram-only:{key}", at_run.get(key) == EXPECTED_BEFORE_FRONTIER[key], str(at_run.get(key)))
            check(f"ram-only-before:{key}", before_run.get(key) == EXPECTED_BEFORE_FRONTIER[key],
                  str(before_run.get(key)))
        check(
            "ram-only:frontier-index",
            int(at_run.get("p10_access_count", "0")) >= EXPECTED_FRONTIER_ACCESS_INDEX,
            str(at_run.get("p10_access_count")),
        )
        check(
            "event:no-device-access-before-frontier",
            all(at_run.get(key) == "0" for key in
                ("gpu_events", "input_events", "cdrom_events", "spu_events", "nonram_signatures")),
            json.dumps({key: at_run.get(key) for key in
                        ("gpu_events", "input_events", "cdrom_events", "spu_events",
                         "nonram_signatures")}, sort_keys=True),
        )

        # --- 5. next-blocker pointer provenance (private metadata only) ------
        def word(address: int) -> int:
            offset = address - 0x80000000
            return int.from_bytes(flat[offset : offset + 4], "little")

        driver_global = word(0x80029644)
        driver_structure = driver_global & 0xFFFFFFFF
        method_pointer = word(driver_structure + 12)
        packed = method_pointer.to_bytes(4, "little")
        occurrences = 0
        cursor = flat.find(packed)
        first_offset = None
        while cursor >= 0:
            occurrences += 1
            if first_offset is None:
                first_offset = 0x80000000 + cursor
            cursor = flat.find(packed, cursor + 1)
        prologue = word(method_pointer)
        check(
            "provenance:driver-global",
            f"0x{driver_structure:08x}" == EXPECTED_POINTER_PROVENANCE["driver_structure"],
            f"0x{driver_structure:08x}",
        )
        check(
            "provenance:method-pointer",
            f"0x{method_pointer:08x}" == EXPECTED_POINTER_PROVENANCE["method_pointer"],
            f"0x{method_pointer:08x}",
        )
        check(
            "provenance:occurrence",
            occurrences == EXPECTED_POINTER_PROVENANCE["pointer_occurrences_in_image"]
            and first_offset is not None
            and f"0x{first_offset:08x}" == EXPECTED_POINTER_PROVENANCE["pointer_image_offset"],
            f"{occurrences}@{first_offset and hex(first_offset)}",
        )
        check(
            "provenance:prologue",
            f"0x{prologue:08x}" == EXPECTED_POINTER_PROVENANCE["prologue_word"],
            f"0x{prologue:08x}",
        )
        entries = {unit.entry_address for unit in result.units.units}
        blocks = {block.entry_address for unit in result.units.units for block in unit.blocks}
        check(
            "provenance:not-yet-translated",
            method_pointer not in entries and method_pointer not in blocks,
            "the proven target is not yet a translated entry (next stage)",
        )

        # --- 6. evidence ------------------------------------------------------
        event_document = {
            "schema": "openrecomp-phase11-event-contract-v1",
            "stage": STAGE,
            "label": "hercules-private-fixture",
            "question": [
                "does initialization require interrupt delivery, interrupt",
                "acknowledgement, DMA completion, timer transitions,",
                "memory-control state or another event source?",
            ],
            "determination": {
                "requires_interrupt_delivery": "NOT_PROVEN",
                "requires_interrupt_acknowledgement": "NOT_PROVEN",
                "requires_dma_completion": "NOT_PROVEN",
                "requires_timer_transition": "NOT_PROVEN",
                "requires_memory_control_state": "NOT_PROVEN",
                "requires_another_event_source": "NOT_PROVEN",
                "implementation_delta": "zero",
                "reason": [
                    "the entire 506040-access progress to the first fail-closed",
                    "event is RAM-only: zero device-port accesses, zero non-RAM",
                    "access signatures, zero interrupt/DMA/timer/memory-control",
                    "interaction; an event source that is never accessed cannot be",
                    "the causal blocker, so no event behaviour is proven necessary",
                ],
            },
            "event_relevant_services": [
                {
                    "vector": vector,
                    "index": f"0x{index:02x}",
                    "documented_name": name,
                    "resolved": False,
                    "reached_before_frontier": False,
                }
                for vector, index, name in EVENT_SERVICE_INDICES
            ],
            "frontier_access_index": EXPECTED_FRONTIER_ACCESS_INDEX,
            "before_frontier_observables": {
                key: at_run.get(key) for key in
                ("error", "reads", "writes", "denied", "host_calls", "p10_access_count",
                 "gpu_events", "input_events", "cdrom_events", "spu_events", "nonram_signatures")
            },
            "at_frontier_observables": {
                key: at_run.get(key) for key in
                ("error", "reads", "writes", "denied", "host_calls", "p10_access_count",
                 "gpu_events", "input_events", "cdrom_events", "spu_events", "nonram_signatures")
            },
            "causal_ab": {
                "event_ab_possible": False,
                "reason": "no event source is accessed before the frontier; changing an unaccessed condition cannot change progress",
                "service_ab": [
                    "serving A0:0x2b moved the frontier from block 9424 to 468147",
                    "and serving A0:0x3f moved it to 468281; both are causal",
                    "service dependencies, not event dependencies",
                ],
            },
            "next_blocker": {
                "site": EXPECTED_FRONTIER["failure_site"],
                "kind": "INDIRECT_CALL",
                "function": EXPECTED_FRONTIER["failure_function"],
                "block": EXPECTED_FRONTIER["failure_block"],
                "source_pointer": EXPECTED_FRONTIER["failure_source"],
                "message": EXPECTED_FRONTIER["failure_message"],
                "pointer_provenance": {
                    "driver_global_address": EXPECTED_POINTER_PROVENANCE["driver_global_address"],
                    "driver_structure": EXPECTED_POINTER_PROVENANCE["driver_structure"],
                    "method_field_offset": EXPECTED_POINTER_PROVENANCE["method_field_offset"],
                    "method_pointer": EXPECTED_POINTER_PROVENANCE["method_pointer"],
                    "pointer_image_offset": EXPECTED_POINTER_PROVENANCE["pointer_image_offset"],
                    "occurrences_in_image": EXPECTED_POINTER_PROVENANCE["pointer_occurrences_in_image"],
                    "prologue_word": EXPECTED_POINTER_PROVENANCE["prologue_word"],
                    "classification": [
                        "a statically initialized driver method pointer: the global at",
                        "0x80029644 holds the structure address, the field at offset 12",
                        "holds a function entry that the static CFG did not discover",
                        "because it is only reachable through this indirect call",
                    ],
                },
            },
        }
        frontier_document = {
            "schema": "openrecomp-phase11-event-frontier-v1",
            "stage": STAGE,
            "bios_vector_classification": classification,
            "runtime_composition": build_set["runtime_composition"],
            "emission": {
                "program_fingerprint": build_set["program_fingerprint"],
                "files": [
                    {"name": name, "sha256": build_set["hashes"][name],
                     "bytes": len(build_set["files"][name].encode("utf-8"))}
                    for name in emission.EMISSION_NAMES
                ],
                "bios_sites": build_set["bios_sites"],
                "semantics": build_set["semantics"],
            },
            "frontier_run": {
                "access_budget": 1500000,
                "block_budget": 8000000,
                "executable_sha256": native_build["executable_sha256"],
                "stdout_sha256": frontier_run["stdout_sha256"],
                "observables": {key: traced.get(key) for key in OBSERVABLE_KEYS},
                "trace": {
                    key: traced.get(key) for key in (
                        "trace_block_events", "trace_function_events", "trace_block_digest",
                        "trace_distinct_blocks", "trace_distinct_functions",
                        "trace_failure_count", "trace_failure_site", "trace_failure_source",
                        "trace_failure_message", "trace_failure_block_index",
                        "trace_failure_function", "trace_ring_count",
                        "bound_budget", "bound_reached", "bound_denials",
                    )
                },
                "analysis": analysis,
            },
            "printf_service_fixtures": printf_records,
            "frontier_movement": {
                "p11_01_first_failure": "0x80026ccc @ 9424",
                "p11_02_first_failure": "0x80026cec @ 468147",
                "p11_03_first_failure": "0x80016204 @ 468281",
                "statement": [
                    "each documented service resolution moves the first fail-closed",
                    "event forward; the remaining 17 BIOS vector sites and the dynamic",
                    "driver-method call stay fail-closed",
                ],
            },
        }
        for name, document in (("event_contract", event_document), ("frontier", frontier_document)):
            write_json(evidence / f"{name}.json", document)
            assert_no_payload_leak(f"public:{name}", document, image.payload)

        # cache provenance includes the extended service surface
        identity = fixture.build_identity(fixture_root)
        provenance = cache.build_provenance(identity, traced=True)
        provenance["bios_site_plan_digest"] = hashlib.sha256(
            json.dumps(bios.site_plan(classification), sort_keys=True).encode("utf-8")
        ).hexdigest()
        phase_cache = cache.Phase11Cache(ROOT / ".openrecomp-phase11" / "cache")
        document = {"stage": STAGE, "services": resolved_ids}
        key = phase_cache.store(provenance, document)
        check("cache:hit", phase_cache.lookup(provenance) == document, "stored document returned")
        stale = dict(provenance)
        stale["bios_site_plan_digest"] = "0" * 64
        check("cache:site-plan-miss", phase_cache.key(stale) != key and phase_cache.lookup(stale) is None,
              "service surface is part of the key")

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
        "stage_name": "Event / interrupt / DMA progress contract",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p11_03_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P11_03={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{INITIALIZATION_MARKER}={NOT_PROVEN}")
    print(f"{FRAME_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
