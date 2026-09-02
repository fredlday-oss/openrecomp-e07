#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ADAPTER_ID = "openrecomp.mips32-elf-expansion-v1"
MODULE_PREFIX = "openrecomp.mips32.elf.expansion-v1."


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
            "usage: check_mips32_elf_ingestion_v1.py <runtime.json> <frontend-report.json> <elf-metadata.json> "
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

    if runtime.get("profile") != "expansion-v1" or runtime.get("architecture") != "mips32-le":
        fail("runtime sidecar is outside little-endian expansion-v1")
    if elf_meta["format"] != "ELF32" or elf_meta["endianness"] != "little" or elf_meta["machine"] != 8:
        fail("ELF metadata is not bounded ELF32 little-endian EM_MIPS")
    if elf_meta["entry_point"] != runtime["entry_address"]:
        fail("ELF entry point disagrees with bounded runtime fixture")
    if report["input_format"] != "ELF32" or report["elf_machine"] != 8:
        fail("frontend report lost ELF32/EM_MIPS identity")
    if report["source_adapter"] != ADAPTER_ID:
        fail("frontend report has unexpected ELF adapter identity")
    if ir["ir_version"] != "1.0.0" or ir["source"]["architecture"] != "mips32-le":
        fail("ELF frontend did not emit bounded MIPS32 IR V1")
    if ir["source"]["adapter"] != ADAPTER_ID:
        fail("unexpected normalized MIPS32 ELF adapter identity")
    if not ir["module_id"].startswith(MODULE_PREFIX):
        fail("MIPS32 ELF module identity is outside the ELF namespace")
    if ir["required_features"] != ["core-v1"] or ir["required_host_symbols"] != []:
        fail("MIPS32 ELF fixture escaped the host-free Core V1 contract")

    expected_slots = {f"gpr:r{i}" for i in range(1, 32)} | {"special:hi", "special:lo"}
    if {item["id"] for item in ir["state_slots"]} != expected_slots:
        fail("normalized MIPS32 ELF state slots are incomplete")
    if module["module_format_version"] != "1.0.0" or module["module_id"] != ir["module_id"]:
        fail("Module Image V1 identity/version mismatch")

    results = [("reference", reference), ("core", core), *aot_results]
    source_hashes = {
        elf_meta["input_sha256"],
        ir["source"]["input_sha256"],
        module["ir"]["source_input_sha256"],
        module["provenance"]["source_input_sha256"],
        report["source_input_sha256"],
        *(result["source_input_sha256"] for _, result in results),
    }
    if len(source_hashes) != 1:
        fail("ELF source provenance diverged across MIPS32 paths")

    if reference.get("input_format") != "ELF32" or reference.get("elf_machine") != 8:
        fail("independent reference result lost ELF identity")
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
            fail(f"{name}: complete state differs from independent reference")
        if result["memory_bytes_hex"] != baseline_memory or result["checksum"] != reference["checksum"]:
            fail(f"{name}: memory/checksum differs from independent reference")
        if result["function_return"] is not None or result["host"] != {}:
            fail(f"{name}: unexpected function return/host side effect")
        if result["operations"] != core["operations"]:
            fail(f"{name}: Core/AOT operation count mismatch")

    print(f"MIPS32_ELF_SHA256={elf_meta['input_sha256']}")
    print(f"MIPS32_ELF_TEXT_SHA256={elf_meta['text']['sha256']}")
    print(f"MIPS32_ELF_CHECKSUM={reference['checksum']}")
    print("OPENRECOMP_MIPS32_ELF_INGESTION_V1=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (OSError, json.JSONDecodeError, KeyError, AssertionError) as exc:
        print(f"OPENRECOMP_MIPS32_ELF_INGESTION_V1=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
