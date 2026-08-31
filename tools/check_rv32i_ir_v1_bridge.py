#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EXPECTED_HOSTS = {"host_graphics", "host_audio", "host_input", "host_system"}
LEGACY_GUEST_OPS = {"addi", "andi", "slli", "srli", "add", "xor", "lw", "lhu", "sw", "lui", "bltu", "bgeu", "beq", "bne", "jal", "jalr"}
STATE_KEYS = ["return_a0", "tick_count", "graphics_calls", "audio_calls", "input_calls", "system_calls", "checksum"]


def fail(message: str) -> None:
    raise AssertionError(message)


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print("usage: check_rv32i_ir_v1_bridge.py <legacy-ir.json> <v1.json> <bridge-result.json> <golden-state.json> <native-run.txt>", file=sys.stderr)
        return 2

    legacy = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    v1 = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    result = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
    golden = json.loads(Path(argv[4]).read_text(encoding="utf-8"))
    native_text = Path(argv[5]).read_text(encoding="utf-8")

    if legacy["ir_version"] != "0.1.1":
        fail("unexpected legacy IR version")
    if v1["ir_version"] != "1.0.0":
        fail("unexpected normalized IR version")
    if v1["source"]["input_sha256"] != legacy["input_sha256"]:
        fail("normalized IR lost source-input provenance")
    if v1["entry_function"] != "fixture_main":
        fail("normalized entry function changed")
    if set(v1["required_host_symbols"]) != EXPECTED_HOSTS:
        fail(f"unexpected host symbol set: {v1['required_host_symbols']}")

    state_slots = {s["id"] for s in v1["state_slots"]}
    expected_slots = {f"gpr:x{i}" for i in range(1, 32)}
    if state_slots != expected_slots:
        fail("RV32I bridge state-slot declaration is incomplete")

    normalized_ops: set[str] = set()
    for function in v1["functions"]:
        for block in function["blocks"]:
            normalized_ops.update(insn["op"] for insn in block["instructions"])
            normalized_ops.add(block["terminator"]["op"])
    leaked = sorted(normalized_ops & LEGACY_GUEST_OPS)
    if leaked:
        fail("guest opcodes leaked into normalized operation field: " + ", ".join(leaked))

    for key in STATE_KEYS:
        if result.get(key) != golden.get(key):
            fail(f"{key} mismatch bridge={result.get(key)} golden={golden.get(key)}")

    match = re.search(r"^CHECKSUM=(\d+)\s*$", native_text, re.MULTILINE)
    if not match:
        fail("native E07 checksum marker missing")
    native_checksum = int(match.group(1))
    if native_checksum != result["checksum"]:
        fail(f"native/IR-V1 checksum mismatch native={native_checksum} v1={result['checksum']}")

    e07_ops = sorted({insn["op"] for insn in legacy["instructions"]})
    print("E07_LEGACY_OPS=" + ",".join(e07_ops))
    print("IR_V1_PORTABLE_OPS=" + ",".join(sorted(normalized_ops)))
    print(f"IR_V1_BRIDGE_FUNCTIONS={len(v1['functions'])}")
    print(f"IR_V1_BRIDGE_OPERATIONS={result['operations']}")
    print(f"OPENRECOMP_RV32I_IR_V1_EQUIVALENCE=PASS checksum={result['checksum']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (OSError, json.JSONDecodeError, KeyError, AssertionError) as exc:
        print(f"OPENRECOMP_RV32I_IR_V1_EQUIVALENCE=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
