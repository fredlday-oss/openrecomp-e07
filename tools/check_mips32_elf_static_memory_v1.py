#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ADAPTER_ID = "openrecomp.mips32-elf-static-memory-v1"
MODULE_PREFIX = "openrecomp.mips32.elf.static-memory-v1."


def fail(message: str) -> None:
    raise AssertionError(message)


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_result(name: str, result: dict, expected: dict) -> None:
    for key in ("return_v0", "memory_word", "memory_bytes_hex", "checksum"):
        if result[key] != expected[key]:
            fail(f"{name}: {key} mismatch: expected {expected[key]!r}, got {result[key]!r}")
    for slot, value in expected["state"].items():
        if result["state"].get(slot) != value:
            fail(f"{name}: expected {slot}={value}, got {result['state'].get(slot)}")


def main(argv: list[str]) -> int:
    if len(argv) < 9:
        print(
            "usage: check_mips32_elf_static_memory_v1.py <runtime.json> <frontend-report.json> <elf-metadata.json> "
            "<ir.json> <module.json> <reference.json> <core.json> <aot-result.json> [aot-result.json ...]",
            file=sys.stderr,
        )
        return 2

    runtime = load(argv[1])
    report = load(argv[2])
    elf_meta = load(argv[3])
    ir = load(argv[4])
    module = load(argv[5])
    reference = load(argv[6])
    core = load(argv[7])
    aot_results = [(f"aot[{index}]", load(path)) for index, path in enumerate(argv[8:], 1)]
    expected = runtime["expected"]
    expected_memory = runtime["static_memory_expected"]

    if runtime.get("profile") != "expansion-v1" or runtime.get("architecture") != "mips32-le":
        fail("runtime sidecar is outside little-endian expansion-v1")
    if report.get("source_adapter") != ADAPTER_ID or report.get("static_memory_segment_count") != 3:
        fail("frontend report lost bounded static-memory adapter identity")
    if ir["source"].get("adapter") != ADAPTER_ID or not ir["module_id"].startswith(MODULE_PREFIX):
        fail("normalized IR escaped static-memory namespace")
    if ir["required_features"] != ["core-v1"] or ir["required_host_symbols"] != []:
        fail("static-memory fixture escaped host-free Core V1")
    if elf_meta.get("format") != "ELF32" or elf_meta.get("endianness") != "little" or elf_meta.get("machine") != 8:
        fail("ELF metadata is not bounded little-endian ELF32 EM_MIPS")

    static_meta = {item["name"]: item for item in elf_meta.get("static_memory_segments", [])}
    if set(static_meta) != set(expected_memory):
        fail("ELF static-memory section set mismatch")
    module_segments = {item["name"]: item for item in module["memory"]["segments"]}
    reference_segments = {item["name"]: item for item in reference["initial_memory_segments"]}
    for name, spec in expected_memory.items():
        item = static_meta[name]
        if item["guest_address"] != spec["address"] or item["size_bytes"] != spec["size_bytes"]:
            fail(f"{name}: ELF address/size mismatch")
        if item["data_sha256"] != spec["initial_sha256"] or item["zero_fill"] != spec["zero_fill"]:
            fail(f"{name}: ELF initial bytes/zero-fill mismatch")
        if item["writable"] != spec["writable"] or item["executable"]:
            fail(f"{name}: ELF section attribute classification mismatch")
        mod = module_segments.get(name)
        if mod is None or mod["guest_address"] != spec["address"] or mod["data_sha256"] != spec["initial_sha256"]:
            fail(f"{name}: Module Image lost static-memory initialization")
        ref = reference_segments.get(name)
        if ref is None or ref["guest_address"] != spec["address"] or ref["data_sha256"] != spec["initial_sha256"]:
            fail(f"{name}: reference initialization diverged")

    if module["module_format_version"] != "1.0.0" or module["module_id"] != ir["module_id"]:
        fail("Module Image V1 identity/version mismatch")
    if module["memory"]["size_bytes"] != runtime["memory_size_bytes"]:
        fail("module memory size mismatch")

    results = [("reference", reference), ("core", core), *aot_results]
    source_hashes = {
        elf_meta["input_sha256"], ir["source"]["input_sha256"], module["ir"]["source_input_sha256"],
        module["provenance"]["source_input_sha256"], report["source_input_sha256"],
        *(result["source_input_sha256"] for _, result in results),
    }
    if len(source_hashes) != 1:
        fail("full ELF source provenance diverged across paths")

    for name, result in results:
        if result["architecture"] != "mips32-le":
            fail(f"{name}: architecture mismatch")
        check_result(name, result, expected)

    if reference["delay_slots_executed"] != expected["delay_slots_executed"]:
        fail("reference delay-slot count mismatch")
    if report["delay_slots_lowered"] != expected["delay_slots_executed"]:
        fail("frontend delay-slot count mismatch")

    baseline_state = reference["state"]
    baseline_memory = reference["memory_bytes_hex"]
    for name, result in [("core", core), *aot_results]:
        if result["state"] != baseline_state:
            fail(f"{name}: complete state differs from reference")
        if result["memory_bytes_hex"] != baseline_memory or result["checksum"] != reference["checksum"]:
            fail(f"{name}: post-execution memory/checksum differs from reference")
        if result["function_return"] is not None or result["host"] != {}:
            fail(f"{name}: unexpected function return/host effect")
        if result["operations"] != core["operations"]:
            fail(f"{name}: Core/AOT operation count mismatch")

    print(f"MIPS32_ELF_STATIC_MEMORY_SHA256={elf_meta['input_sha256']}")
    print(f"MIPS32_ELF_STATIC_MEMORY_CHECKSUM={reference['checksum']}")
    print("OPENRECOMP_MIPS32_ELF_STATIC_MEMORY_V1=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (OSError, json.JSONDecodeError, KeyError, AssertionError) as exc:
        print(f"OPENRECOMP_MIPS32_ELF_STATIC_MEMORY_V1=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
