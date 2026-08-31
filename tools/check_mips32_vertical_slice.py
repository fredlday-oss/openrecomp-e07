#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

LEGACY_MIPS_OPS = {
    "nop", "addiu", "ori", "lui", "addu", "slt", "sltu",
    "lw", "sw", "beq", "bne", "j", "jal", "jr",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def main(argv: list[str]) -> int:
    if len(argv) != 7:
        print(
            "usage: check_mips32_vertical_slice.py <fixture.json> <frontend-report.json> <ir.json> <module.json> <reference.json> <core.json>",
            file=sys.stderr,
        )
        return 2

    meta = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    report = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    ir = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
    module = json.loads(Path(argv[4]).read_text(encoding="utf-8"))
    reference = json.loads(Path(argv[5]).read_text(encoding="utf-8"))
    core = json.loads(Path(argv[6]).read_text(encoding="utf-8"))
    expected = meta["expected"]

    if ir["ir_version"] != "1.0.0":
        fail("MIPS32 frontend did not emit IR V1")
    if ir["source"]["architecture"] != "mips32-le":
        fail("wrong normalized source architecture")
    if ir["source"]["adapter"] != "openrecomp.mips32-v1-slice":
        fail("unexpected MIPS32 adapter identity")
    if ir["required_features"] != ["core-v1"]:
        fail(f"unexpected IR features: {ir['required_features']}")
    if ir["required_host_symbols"] != []:
        fail("bounded MIPS32 slice should not require host symbols")
    if len(ir["functions"]) != 2:
        fail("expected exactly two synthetic MIPS32 functions")

    slots = {item["id"] for item in ir["state_slots"]}
    if slots != {f"gpr:r{i}" for i in range(1, 32)}:
        fail("MIPS32 normalized state slots are incomplete")

    normalized_ops: set[str] = set()
    for function in ir["functions"]:
        for block in function["blocks"]:
            normalized_ops.update(item["op"] for item in block["instructions"])
            normalized_ops.add(block["terminator"]["op"])
    leaked = sorted(normalized_ops & LEGACY_MIPS_OPS)
    if leaked:
        fail("MIPS opcodes leaked into normalized IR op field: " + ", ".join(leaked))

    if module["module_format_version"] != "1.0.0":
        fail("MIPS32 path did not use Module Image V1")
    if module["module_id"] != ir["module_id"]:
        fail("module/IR identity mismatch")

    source_hashes = {
        ir["source"]["input_sha256"],
        module["ir"]["source_input_sha256"],
        module["provenance"]["source_input_sha256"],
        reference["source_input_sha256"],
        core["source_input_sha256"],
        report["source_input_sha256"],
    }
    if len(source_hashes) != 1:
        fail("source provenance diverged across frontend/module/reference/Core paths")

    for name, result in (("reference", reference), ("core", core)):
        if result["return_v0"] != expected["return_v0"]:
            fail(f"{name}: v0 mismatch")
        if result["memory_word"] != expected["memory_word"]:
            fail(f"{name}: observable memory word mismatch")
        if result["memory_bytes_hex"] != expected["memory_bytes_hex"]:
            fail(f"{name}: observable memory bytes mismatch")
        if result["checksum"] != expected["checksum"]:
            fail(f"{name}: checksum mismatch")
        for slot, value in expected["registers"].items():
            if result["state"].get(slot) != value:
                fail(f"{name}: expected {slot}={value}, got {result['state'].get(slot)}")

    if reference["state"] != core["state"]:
        fail("reference/Core complete MIPS32 register state differs")
    if reference["memory_bytes_hex"] != core["memory_bytes_hex"]:
        fail("reference/Core observable memory differs")
    if reference["checksum"] != core["checksum"]:
        fail("reference/Core checksum differs")
    if core["function_return"] is not None:
        fail("void MIPS32 entry unexpectedly returned an IR value")
    if core["host"] != {}:
        fail("host side effects appeared in host-free MIPS32 slice")

    expected_delays = expected["delay_slots_executed"]
    if reference["delay_slots_executed"] != expected_delays:
        fail("reference delay-slot count mismatch")
    if report["delay_slots_lowered"] != expected_delays:
        fail("frontend did not lower every executed synthetic delay slot")

    required_portable = {
        "binop", "branch", "call", "cast", "compare", "const", "jump",
        "load", "read_state", "return", "store", "write_state",
    }
    missing = sorted(required_portable - normalized_ops)
    if missing:
        fail("MIPS32 slice did not exercise expected portable ops: " + ", ".join(missing))

    print("MIPS32_IR_V1_PORTABLE_OPS=" + ",".join(sorted(normalized_ops)))
    print(f"MIPS32_IR_V1_FUNCTIONS={len(ir['functions'])}")
    print(f"MIPS32_DELAY_SLOTS={expected_delays}")
    print(f"MIPS32_REFERENCE_CHECKSUM={reference['checksum']}")
    print(f"MIPS32_CORE_API_CHECKSUM={core['checksum']}")
    print(f"MIPS32_CORE_API_OPERATIONS={core['operations']}")
    print(f"OPENRECOMP_MIPS32_VERTICAL_SLICE_V1=PASS checksum={core['checksum']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (OSError, json.JSONDecodeError, KeyError, AssertionError) as exc:
        print(f"OPENRECOMP_MIPS32_VERTICAL_SLICE_V1=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
