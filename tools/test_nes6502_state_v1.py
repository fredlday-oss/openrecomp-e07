#!/usr/bin/env python3
"""P1-30 gate: documented NES 6502 architectural state model.

Pins the NMOS 6502 register/flag facts in `adapters/nes6502.py` against the
publicly documented 6502 architecture (register file, flag bit positions,
no architectural register pairs, 8-bit standalone SP, implicit PC, 16-bit address space),
verifies fail-closed behaviour, and proves the state-slot model flows through
the architecture-neutral scaffolding into Core API V1 execution.
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

from adapters import nes6502  # noqa: E402
from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor  # noqa: E402
from openrecomp.frontends.scaffold import IRBuilder  # noqa: E402

CONTRACT_PATH = ROOT / "contracts" / "host_contract.json"
INPUT_SHA = hashlib.sha256(b"synthetic nes6502 state proof v1").hexdigest()
MEMORY_SIZE = 262144

EXPECTED_A = 0x3E
EXPECTED_X = 0x12
EXPECTED_Y = 0x42
EXPECTED_SP = 0xFE
EXPECTED_PC = 0x0100
EXPECTED_P = 0xD0  # N=1, V=1, unused=1, B=1, D=0, I=0, Z=0, C=0
EXPECTED_OPERATIONS = 8  # pinned after the first verified Core API run


def serialize(document: object) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expect_fail(label: str, action, error_type=nes6502.NES6502Error) -> None:
    try:
        action()
    except error_type:
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"{label}: accepted")


def build_register_composition() -> tuple[dict, dict]:
    builder = IRBuilder(
        module_id="openrecomp.nes6502.state.synthetic.register-compose",
        architecture="nes6502",
        adapter="openrecomp.nes6502-state-v1",
        address_bits=32,
        endianness="little",
        input_sha256=INPUT_SHA,
        host_contract_version="0.1.1",
    )
    for slot_id, type_name in nes6502.STATE_SLOTS.items():
        builder.declare_state_slot(slot_id, type_name)
    # Synthetic Core API probe only; AX is not an architectural 6502 register pair.
    builder.declare_state_slot("probe:ax", "i16")

    function = builder.add_function("compose_ax", 0x0100, return_type="i16")
    block = function.add_block("entry", 0x0100)
    block.read_state("%a", "cpu:a")
    block.cast("%a16", "i16", "zext", block.value("%a"))
    block.binop("%ashl", "i16", "shl", block.value("%a16"), block.const(8, "i16"))
    block.read_state("%x", "cpu:x")
    block.cast("%x16", "i16", "zext", block.value("%x"))
    block.binop("%ax", "i16", "or", block.value("%ashl"), block.value("%x16"))
    block.write_state("probe:ax", block.value("%ax"))
    block.ret(block.value("%ax"))

    return builder.build(
        entry_function="compose_ax",
        memory_size_bytes=MEMORY_SIZE,
        initial_state={"cpu:a": EXPECTED_A, "cpu:x": EXPECTED_X, "cpu:sp": EXPECTED_SP, "cpu:pc": EXPECTED_PC},
        observe_state_slot="probe:ax",
        max_operations=100,
    )


def main() -> int:
    tests = 0
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_bytes = CONTRACT_PATH.read_bytes()

    info = nes6502.info
    assert info.architecture_id == "nes6502", info.architecture_id
    assert info.bits == 8, info.bits
    assert info.endianness == "little", info.endianness
    assert info.registers == ("a", "x", "y", "sp", "pc"), info.registers
    assert info.calling_convention, "calling convention must be documented"
    print("PASS architecture-info")
    tests += 1

    assert nes6502.FLAG_N == 0x80, nes6502.FLAG_N
    assert nes6502.FLAG_V == 0x40, nes6502.FLAG_V
    assert nes6502.FLAG_B == 0x10, nes6502.FLAG_B
    assert nes6502.FLAG_D == 0x08, nes6502.FLAG_D
    assert nes6502.FLAG_I == 0x04, nes6502.FLAG_I
    assert nes6502.FLAG_Z == 0x02, nes6502.FLAG_Z
    assert nes6502.FLAG_C == 0x01, nes6502.FLAG_C
    assert nes6502.FLAG_UNUSED == 0x20, nes6502.FLAG_UNUSED
    flags = {nes6502.FLAG_N, nes6502.FLAG_V, nes6502.FLAG_B, nes6502.FLAG_D,
             nes6502.FLAG_I, nes6502.FLAG_Z, nes6502.FLAG_C, nes6502.FLAG_UNUSED}
    assert len(flags) == 8, "flag bits must be distinct"
    print("PASS flag-positions N=0x80 V=0x40 B=0x10 D=0x08 I=0x04 Z=0x02 C=0x01 unused=0x20")
    tests += 1

    assert nes6502.STATE_SLOTS == {
        "cpu:a": "i8",
        "cpu:x": "i8",
        "cpu:y": "i8",
        "cpu:sp": "i8",
        "cpu:pc": "i16",
    }, nes6502.STATE_SLOTS
    print("PASS state-slots A/X/Y/SP=i8 PC=i16")
    tests += 1

    assert nes6502.REGISTER_PAIRS == (), nes6502.REGISTER_PAIRS
    print("PASS no architectural register pairs")
    tests += 1

    # Test register value validation
    try:
        nes6502._check_byte(0x100, "test")
        raise AssertionError("Should have failed on out-of-range byte")
    except nes6502.NES6502Error:
        print("PASS register validation rejects out-of-range values")
        tests += 1

    try:
        nes6502._check_byte(-1, "test")
        raise AssertionError("Should have failed on negative value")
    except nes6502.NES6502Error:
        print("PASS register validation rejects negative values")
        tests += 1

    # Test address validation
    try:
        nes6502._check_address(0x10000, "test")
        raise AssertionError("Should have failed on out-of-range address")
    except nes6502.NES6502Error:
        print("PASS address validation rejects out-of-range addresses")
        tests += 1

    # Test undocumented opcode rejection
    try:
        nes6502.decode(0x100, 0x03)
        raise AssertionError("Should have failed on undocumented opcode")
    except nes6502.NES6502Error:
        print("PASS decode rejects undocumented opcodes")
        tests += 1

    # Test basic instruction decoding
    insn = nes6502.decode(0x100, 0x09)  # ORA #imm
    assert insn["op"] == "ora"
    assert insn["src"] == "imm"
    print("PASS basic instruction decoding")
    tests += 1

    ir, sidecar = build_register_composition()
    ir_again, sidecar_again = build_register_composition()
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
            "producer": "openrecomp.nes6502-state-v1",
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

    assert execution.observed_state == (EXPECTED_A << 8) | EXPECTED_X, hex(execution.observed_state)
    assert execution.state["cpu:a"] == EXPECTED_A, hex(execution.state["cpu:a"])
    assert execution.state["cpu:x"] == EXPECTED_X, hex(execution.state["cpu:x"])
    assert execution.state["cpu:y"] == 0x00, hex(execution.state["cpu:y"])
    assert execution.state["cpu:sp"] == EXPECTED_SP, hex(execution.state["cpu:sp"])
    assert execution.state["cpu:pc"] == EXPECTED_PC, hex(execution.state["cpu:pc"])
    print(
        "PASS neutral-chain proof A=0x3E X=0x12 sp=0xFE pc=0x0100 "
        f"operations={execution.operations} deterministic"
    )
    tests += 1

    print(f"OPENRECOMP_NES6502_STATE_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
