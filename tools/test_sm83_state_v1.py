#!/usr/bin/env python3
"""P1-10 gate: documented SM83 architectural state model.

Pins the Sharp SM83 register/flag facts in `adapters/sm83.py` against the
publicly documented Game Boy CPU architecture (register file, flag bit
positions, high-byte-first pairs, standalone SP, implicit PC, 16-bit address
space), verifies fail-closed behaviour, and proves the state-slot model flows
through the architecture-neutral scaffolding into Core API V1 execution.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from adapters import sm83  # noqa: E402
from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor  # noqa: E402
from openrecomp.frontends.scaffold import IRBuilder  # noqa: E402

CONTRACT_PATH = ROOT / "contracts" / "host_contract.json"
INPUT_SHA = hashlib.sha256(b"synthetic sm83 state proof v1").hexdigest()
MEMORY_SIZE = 262144

EXPECTED_AF = 0x3EB0  # cpu:a=0x3E, cpu:f=0xB0 -> AF = 0x3EB0
EXPECTED_SP = 0xFFFE
EXPECTED_OPERATIONS = 8  # pinned after the first verified Core API run


def serialize(document: object) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expect_fail(label: str, action, error_type=sm83.SM83Error) -> None:
    try:
        action()
    except error_type:
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"{label}: accepted")


def build_af_composition() -> tuple[dict, dict]:
    builder = IRBuilder(
        module_id="openrecomp.sm83.state.synthetic.af-compose",
        architecture="sm83-gb",
        adapter="openrecomp.sm83-state-v1",
        address_bits=32,
        endianness="little",
        input_sha256=INPUT_SHA,
        host_contract_version="0.1.1",
    )
    for slot_id, type_name in sm83.STATE_SLOTS.items():
        builder.declare_state_slot(slot_id, type_name)
    builder.declare_state_slot("probe:af", "i16")

    function = builder.add_function("compose_af", 0x0100, return_type="i16")
    block = function.add_block("entry", 0x0100)
    block.read_state("%a", "cpu:a")
    block.cast("%a16", "i16", "zext", block.value("%a"))
    block.binop("%ashl", "i16", "shl", block.value("%a16"), block.const(8, "i16"))
    block.read_state("%f", "cpu:f")
    block.cast("%f16", "i16", "zext", block.value("%f"))
    block.binop("%af", "i16", "or", block.value("%ashl"), block.value("%f16"))
    block.write_state("probe:af", block.value("%af"))
    block.ret(block.value("%af"))

    return builder.build(
        entry_function="compose_af",
        memory_size_bytes=MEMORY_SIZE,
        initial_state={"cpu:a": 0x3E, "cpu:f": 0xB0, "cpu:sp": EXPECTED_SP},
        observe_state_slot="probe:af",
        max_operations=100,
    )


def main() -> int:
    tests = 0
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_bytes = CONTRACT_PATH.read_bytes()

    info = sm83.info
    assert info.architecture_id == "sm83-gb", info.architecture_id
    assert info.bits == 8, info.bits
    assert info.endianness == "little", info.endianness
    assert info.registers == ("a", "f", "b", "c", "d", "e", "h", "l", "sp", "pc"), info.registers
    assert info.calling_convention, "calling convention must be documented"
    print("PASS architecture-info")
    tests += 1

    assert sm83.FLAG_Z == 0x80, sm83.FLAG_Z
    assert sm83.FLAG_N == 0x40, sm83.FLAG_N
    assert sm83.FLAG_H == 0x20, sm83.FLAG_H
    assert sm83.FLAG_C == 0x10, sm83.FLAG_C
    flags = {sm83.FLAG_Z, sm83.FLAG_N, sm83.FLAG_H, sm83.FLAG_C}
    assert len(flags) == 4, "flag bits must be distinct"
    assert sm83.FLAG_WRITE_MASK == 0xF0, sm83.FLAG_WRITE_MASK
    print("PASS flag-positions Z=0x80 N=0x40 H=0x20 C=0x10 write-mask=0xF0")
    tests += 1

    assert sm83.STATE_SLOTS == {
        "cpu:a": "i8",
        "cpu:f": "i8",
        "cpu:b": "i8",
        "cpu:c": "i8",
        "cpu:d": "i8",
        "cpu:e": "i8",
        "cpu:h": "i8",
        "cpu:l": "i8",
        "cpu:sp": "i16",
    }, sm83.STATE_SLOTS
    assert "cpu:pc" not in sm83.STATE_SLOTS, "PC is implicit control flow, not a state slot"
    print("PASS state-slots 8-bit registers + i16 SP; PC implicit")
    tests += 1

    assert sm83.REGISTER_PAIRS == ("af", "bc", "de", "hl"), sm83.REGISTER_PAIRS
    assert sm83.PAIR_PARTS == {"af": ("a", "f"), "bc": ("b", "c"), "de": ("d", "e"), "hl": ("h", "l")}
    for pair, (high, low) in sm83.PAIR_PARTS.items():
        assert sm83.STATE_SLOTS[f"cpu:{high}"] == "i8"
        assert sm83.STATE_SLOTS[f"cpu:{low}"] == "i8"
    print("PASS register-pairs AF/BC/DE/HL high-byte-first")
    tests += 1

    for value in (0x0000, 0x00FF, 0xFF00, 0xFFFF, 0x1234):
        high, low = sm83.pair_halves(value)
        assert sm83.pair_of(high, low) == value, hex(value)
    assert sm83.pair_of(0x3E, 0xB0) == EXPECTED_AF
    print("PASS pair-composition round-trip (0x0000..0xFFFF sampled)")
    tests += 1

    expect_fail("pair-high-byte-out-of-range", lambda: sm83.pair_of(0x100, 0))
    expect_fail("pair-low-byte-negative", lambda: sm83.pair_of(0, -1))
    expect_fail("pair-split-above-16-bits", lambda: sm83.pair_halves(0x10000))
    expect_fail("pair-split-negative", lambda: sm83.pair_halves(-1))
    tests += 1

    # The decoder landed in P1-11; the state gate now pins the same fail-closed
    # property against the real decoder (undocumented encoding -> SM83Error).
    try:
        sm83.decode(0, 0xD3)
    except sm83.SM83Error:
        print("PASS decode fails closed on undocumented encoding")
        tests += 1
    else:
        raise AssertionError("SM83 decode must not accept an undocumented encoding")

    ir, sidecar = build_af_composition()
    ir_again, sidecar_again = build_af_composition()
    assert serialize(ir) == serialize(ir_again), "state-model IR build is not deterministic"
    assert serialize(sidecar) == serialize(sidecar_again), "state-model sidecar is not deterministic"

    ir_bytes = serialize(ir).encode("utf-8")
    manifest = {
        "module_format_version": "1.0.0",
        "module_id": ir["module_id"],
        "ir": {
            "version": ir["ir_version"],
            "sha256": digest(ir_bytes),
            "source_input_sha256": ir["source"]["input_sha256"],
        },
        "host_contract": {
            "version": contract["contract_version"],
            "sha256": digest(contract_bytes),
        },
        "memory": {"size_bytes": MEMORY_SIZE, "segments": []},
        "initial_state": [
            {"slot": slot, "value": value} for slot, value in sorted(sidecar["initial_state"].items())
        ],
        "entry": {
            "function": ir["entry_function"],
            "observe_state_slot": sidecar["entry_state_slot"],
        },
        "limits": {"max_operations": sidecar["max_operations"], "max_call_depth": 1024},
        "provenance": {
            "producer": "openrecomp.sm83-state-v1",
            "source_input_sha256": ir["source"]["input_sha256"],
        },
    }
    module = ModuleImage.from_documents(
        manifest,
        ir,
        contract,
        ir_sha256=digest(ir_bytes),
        contract_sha256=digest(contract_bytes),
    )
    host = CallbackHostBinding(contract["contract_version"], {})
    executor = ReferenceExecutor(module, host)
    execution = executor.run()

    assert execution.observed_state == EXPECTED_AF, hex(execution.observed_state)
    assert execution.function_return == EXPECTED_AF, hex(execution.function_return)
    assert execution.state["cpu:sp"] == EXPECTED_SP, hex(execution.state["cpu:sp"])
    assert execution.state["cpu:a"] == 0x3E, hex(execution.state["cpu:a"])
    assert execution.state["cpu:f"] == 0xB0, hex(execution.state["cpu:f"])
    assert execution.operations == EXPECTED_OPERATIONS, execution.operations
    print(
        "PASS neutral-chain proof AF=0x3EB0 sp=0xFFFE "
        f"operations={execution.operations} deterministic"
    )
    tests += 1

    print(f"OPENRECOMP_SM83_STATE_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
