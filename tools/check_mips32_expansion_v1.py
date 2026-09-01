#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

LEGACY_MIPS_OPS = {
    "nop", "sll", "srl", "sra", "sllv", "srlv", "srav", "jr",
    "mfhi", "mflo", "mult", "multu", "div", "divu", "addu", "subu",
    "and", "or", "xor", "nor", "slt", "sltu", "addiu", "slti", "sltiu",
    "andi", "ori", "xori", "lui", "beq", "bne", "blez", "bgtz", "bltz",
    "bgez", "lb", "lbu", "lh", "lhu", "lw", "sb", "sh", "sw", "j", "jal",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _check_result(name: str, result: dict, expected: dict) -> None:
    for key in ("return_v0", "memory_word", "memory_bytes_hex", "checksum"):
        if result[key] != expected[key]:
            fail(f"{name}: {key} mismatch: expected {expected[key]!r}, got {result[key]!r}")
    for slot, value in expected["state"].items():
        if result["state"].get(slot) != value:
            fail(f"{name}: expected {slot}={value}, got {result['state'].get(slot)}")


def main(argv: list[str]) -> int:
    if len(argv) < 8:
        print(
            "usage: check_mips32_expansion_v1.py <fixture.json> <frontend-report.json> <ir.json> <module.json> <reference.json> <core.json> <aot-result.json> [aot-result.json ...]",
            file=sys.stderr,
        )
        return 2
    meta = _load(argv[1])
    report = _load(argv[2])
    ir = _load(argv[3])
    module = _load(argv[4])
    reference = _load(argv[5])
    core = _load(argv[6])
    aot_results = [(f"aot[{index}]", _load(path)) for index, path in enumerate(argv[7:], 1)]
    expected = meta["expected"]

    if meta.get("profile") != "expansion-v1":
        fail("fixture is not expansion-v1")
    if ir["ir_version"] != "1.0.0":
        fail("expanded frontend did not emit IR V1")
    if ir["source"]["architecture"] != meta["architecture"]:
        fail("wrong normalized source architecture")
    if ir["source"]["adapter"] != "openrecomp.mips32-expansion-v1":
        fail("unexpected expanded MIPS32 adapter identity")
    if ir["required_features"] != ["core-v1"] or ir["required_host_symbols"] != []:
        fail("expanded MIPS32 fixture escaped the host-free Core V1 contract")

    expected_slots = {f"gpr:r{i}" for i in range(1, 32)} | {"special:hi", "special:lo"}
    if {item["id"] for item in ir["state_slots"]} != expected_slots:
        fail("expanded MIPS32 normalized state slots are incomplete")

    normalized_ops: set[str] = set()
    for function in ir["functions"]:
        for block in function["blocks"]:
            normalized_ops.update(item["op"] for item in block["instructions"])
            normalized_ops.add(block["terminator"]["op"])
    leaked = sorted(normalized_ops & LEGACY_MIPS_OPS)
    if leaked:
        fail("MIPS opcode(s) leaked into normalized IR op field: " + ", ".join(leaked))

    if module["module_format_version"] != "1.0.0" or module["module_id"] != ir["module_id"]:
        fail("Module Image V1 identity/version mismatch")

    results = [("reference", reference), ("core", core), *aot_results]
    source_hashes = {
        ir["source"]["input_sha256"],
        module["ir"]["source_input_sha256"],
        module["provenance"]["source_input_sha256"],
        report["source_input_sha256"],
        *(result["source_input_sha256"] for _, result in results),
    }
    if len(source_hashes) != 1:
        fail("source provenance diverged across expanded MIPS32 paths")

    for name, result in results:
        if result["architecture"] != meta["architecture"]:
            fail(f"{name}: architecture mismatch")
        _check_result(name, result, expected)

    if reference["delay_slots_executed"] != expected["delay_slots_executed"]:
        fail("reference delay-slot count mismatch")
    if report["delay_slots_lowered"] != expected["delay_slots_executed"]:
        fail("frontend delay-slot count mismatch")
    if core["function_return"] is not None or core["host"] != {}:
        fail("Core path gained unexpected function return/host side effect")

    baseline_state = reference["state"]
    baseline_memory = reference["memory_bytes_hex"]
    for name, result in [("core", core), *aot_results]:
        if result["state"] != baseline_state:
            fail(f"{name}: complete state differs from independent reference")
        if result["memory_bytes_hex"] != baseline_memory:
            fail(f"{name}: observable memory differs from independent reference")
        if result["checksum"] != reference["checksum"]:
            fail(f"{name}: checksum differs from independent reference")
        if result["function_return"] is not None or result["host"] != {}:
            fail(f"{name}: unexpected function return/host side effect")
        if result["operations"] != core["operations"]:
            fail(f"{name}: Core/AOT operation count mismatch")

    print(f"MIPS32_EXPANSION_FIXTURE={meta['fixture_id']}")
    print(f"MIPS32_EXPANSION_ARCH={meta['architecture']}")
    print(f"MIPS32_EXPANSION_CHECKSUM={reference['checksum']}")
    print(f"MIPS32_EXPANSION_CORE_OPERATIONS={core['operations']}")
    print(f"MIPS32_EXPANSION_DELAY_SLOTS={reference['delay_slots_executed']}")
    print(f"OPENRECOMP_MIPS32_EXPANSION_FIXTURE=PASS fixture={meta['fixture_id']} checksum={reference['checksum']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (OSError, json.JSONDecodeError, KeyError, AssertionError) as exc:
        print(f"OPENRECOMP_MIPS32_EXPANSION_FIXTURE=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
