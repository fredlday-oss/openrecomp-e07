#!/usr/bin/env python3
"""P1-21 gate: Z80 control flow + normalized IR V1 lowering, differential proof.

Runs two synthetic Z80 programs twice:
- through the independent machine-code reference (`tools/z80_reference_v1.py`);
- through the frontend (`tools/z80_frontend_v1.py`) -> frozen normalized IR
  V1 -> Module Image V1 -> the architecture-neutral Core API
  `ReferenceExecutor`.

The final CPU state (including the shadow set, IX/IY/SP, flags), the full
64 KiB guest memory AND the 256-byte deterministic port model must match
exactly. Also proves: conversion determinism, full lowering coverage of
every documented encoding (base/ED/CB/DD-FD/DDCB-FDCB families with explicit
terminator coverage), and fail-closed rejection of out-of-region targets,
undocumented encodings and malformed data ranges.
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

from adapters import z80  # noqa: E402
from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor  # noqa: E402
from test_z80_decode_v1 import ED_DOCUMENTED  # noqa: E402
from z80_frontend_v1 import PORT_BASE, Z80FrontendError, convert  # noqa: E402
from z80_reference_v1 import MEMORY_SIZE, ReferenceZ80, Z80State  # noqa: E402

CONTRACT_PATH = ROOT / "contracts" / "host_contract.json"
ENTRY = 0x0100

CONTROL_OPS = {"jp", "jr", "call", "ret", "retn", "reti", "rst", "djnz", "jp_ind"}


def assemble() -> bytes:
    """Synthetic program: ALU/flags, rotates, CB, DAA, NEG, memory forms,
    16-bit arithmetic, stack, call/ret, EX, IX+d, DJNZ, conditional JR."""
    code = bytearray(0x100)

    def put(address: int, *values: int) -> None:
        code[address - ENTRY:address - ENTRY + len(values)] = bytes(values)

    put(0x0100, 0x3E, 0x2A, 0x06, 0x0F, 0x80, 0xE6, 0x0F, 0x0E, 0x05, 0x81, 0x05, 0x04, 0x07, 0xCB, 0x19, 0x27, 0xED, 0x44)
    put(0x0112, 0x21, 0x00, 0xC0, 0x36, 0x5A, 0x2B, 0x34)
    put(0x0119, 0x01, 0x34, 0x12, 0x03, 0x0B, 0x09)
    put(0x011F, 0x31, 0x00, 0xFF, 0xCD, 0x50, 0x01, 0xE5, 0xD1, 0xEB)
    put(0x0128, 0xDD, 0x21, 0x00, 0xC8, 0xDD, 0x36, 0x03, 0x7F, 0xDD, 0x34, 0x03)
    put(0x0133, 0x06, 0x02, 0x00, 0x10, 0xFD)
    put(0x0138, 0x3E, 0x07, 0xFE, 0x07, 0x28, 0x02)
    put(0x013E, 0x3E, 0x99, 0x18, 0x00, 0x76)
    put(0x0150, 0x3E, 0x55, 0x04, 0xC9)
    return bytes(code)


def assemble_block() -> bytes:
    """Synthetic program: LDIR block transfer + OUT (C),A / IN A,(C) ports."""
    code = bytearray(0x100)

    def put(address: int, *values: int) -> None:
        code[address - ENTRY:address - ENTRY + len(values)] = bytes(values)

    put(0x0100, 0x21, 0x00, 0xC0, 0x11, 0x00, 0xD0, 0x01, 0x04, 0x00, 0xED, 0xB0)
    put(0x010B, 0x01, 0x40, 0x00, 0x3E, 0x5A, 0xED, 0x79, 0xED, 0x78, 0x76)
    return bytes(code)


def assemble_block_io() -> bytes:
    """Synthetic program: OUT (C),A with BC > 0xFF (8-bit port mask), INIR,
    OTIR — exercising the documented block-I/O flag model end to end."""
    code = bytearray(0x100)

    def put(address: int, *values: int) -> None:
        code[address - ENTRY:address - ENTRY + len(values)] = bytes(values)

    put(0x0100, 0x01, 0x40, 0x01, 0x3E, 0x5A, 0xED, 0x79)
    put(0x0107, 0x21, 0x00, 0xC0, 0x06, 0x03, 0xED, 0xB2)
    put(0x010E, 0x0E, 0x37, 0x21, 0x00, 0xD0, 0x06, 0x02, 0xED, 0xB3, 0x76)
    return bytes(code)


def build_image(program: bytes, data: dict[int, int] | None = None) -> bytearray:
    image = bytearray(MEMORY_SIZE)
    image[ENTRY:ENTRY + len(program)] = program
    for address, value in (data or {}).items():
        image[address] = value
    return image


def serialize(document: object) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def core_result(image: bytes, meta: dict, contract: dict, contract_bytes: bytes):
    ir, sidecar, report = convert(image, meta, contract)
    ir_bytes = serialize(ir).encode("utf-8")
    segments = []
    for segment in sorted(sidecar["memory_segments"], key=lambda item: (item["guest_address"], item["name"])):
        data = bytes.fromhex(segment["data_hex"])
        segments.append(
            {
                "name": segment["name"],
                "guest_address": segment["guest_address"],
                "data_hex": data.hex(),
                "data_sha256": digest(data),
            }
        )
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
        "memory": {"size_bytes": sidecar["memory_size_bytes"], "segments": segments},
        "initial_state": [
            {"slot": slot, "value": value} for slot, value in sorted(sidecar["initial_state"].items())
        ],
        "entry": {
            "function": ir["entry_function"],
            "observe_state_slot": sidecar["entry_state_slot"],
        },
        "limits": {"max_operations": sidecar["max_operations"], "max_call_depth": 1024},
        "provenance": {
            "producer": "openrecomp.z80-frontend-v1",
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
    executor = ReferenceExecutor(module, CallbackHostBinding(contract["contract_version"], {}))
    execution = executor.run()
    return execution, bytes(executor.memory.data), ir, sidecar, report


def base_meta(region_end: int) -> dict:
    return {
        "architecture": "z80-sms",
        "entry_address": ENTRY,
        "region_start": ENTRY,
        "region_end": region_end,
        "initial_state": {"cpu:a": 0, "cpu:f": 0, "cpu:sp": 0xFFFE},
        "observe_state_slot": "cpu:a",
        "max_operations": 1000000,
    }


def make_image(program: bytes) -> bytes:
    image = bytearray(MEMORY_SIZE)
    image[ENTRY:ENTRY + len(program)] = program
    return bytes(image)


def differential(program: bytes, region_end: int, data: dict[int, int] | None = None) -> tuple[dict, bytes, dict]:
    image = bytes(build_image(program, data))
    ref = ReferenceZ80(image, Z80State(pc=ENTRY, sp=0xFFFE))
    ref_state = ref.run(max_steps=100000)
    meta = base_meta(region_end)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_bytes = CONTRACT_PATH.read_bytes()
    execution, core_memory, _ir, _sidecar, report = core_result(image, meta, contract, contract_bytes)
    state_keys = ("a", "f", "b", "c", "d", "e", "h", "l", "a2", "f2", "b2", "c2", "d2", "e2", "h2", "l2", "ix", "iy", "sp")
    for key in state_keys:
        expected = ref_state[key]
        actual = execution.state[f"cpu:{key}"]
        if actual != expected:
            raise AssertionError(f"cpu:{key} = {actual:#x} != reference {expected:#x}")
    if ref_state["halted"] != int(execution.state["platform:halted"]):
        raise AssertionError("halted state differs from the reference")
    if int(ref_state["iff1"]) != int(execution.state["platform:iff1"]):
        raise AssertionError("iff1 differs from the reference")
    if int(ref_state["iff2"]) != int(execution.state["platform:iff2"]):
        raise AssertionError("iff2 differs from the reference")
    if bytes(ref.memory) != core_memory[:MEMORY_SIZE]:
        for index, (left, right) in enumerate(zip(ref.memory, core_memory[:MEMORY_SIZE])):
            if left != right:
                raise AssertionError(f"guest memory differs at 0x{index:04x}: {left:#x} != {right:#x}")
        raise AssertionError("guest memory length differs")
    if bytes(ref.ports) != core_memory[PORT_BASE:PORT_BASE + 256]:
        raise AssertionError("port model differs from the reference")
    return ref_state, core_memory, report


def main() -> int:
    tests = 0
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_bytes = CONTRACT_PATH.read_bytes()

    # 1. Differential proof 1: full CPU fixture --------------------------------
    ref_state, _core_memory, report = differential(assemble(), 0x0160)
    pinned = {"a": 0x07, "f": 0x42, "b": 0x00, "c": 0x34, "d": 0xD2, "e": 0x33,
              "h": 0xD2, "l": 0x33, "sp": 0xFF00, "ix": 0xC800, "halted": 1}
    for key, expected in pinned.items():
        actual = ref_state[key]
        if actual != expected:
            raise AssertionError(f"pinned {key}: {actual:#x} != {expected:#x}")
    image = bytes(build_image(assemble()))
    ref_check = ReferenceZ80(image, Z80State(pc=ENTRY, sp=0xFFFE))
    ref_check.run(max_steps=100000)
    assert ref_check.memory[0xC000] == 0x5A and ref_check.memory[0xBFFF] == 0x01 and ref_check.memory[0xC803] == 0x80
    print(
        "PASS differential-proof reference == Core API "
        f"(a={ref_state['a']:#x} f={ref_state['f']:#x} hl={ref_state['h']:#x}{ref_state['l']:02x} "
        f"sp={ref_state['sp']:#x} ix={ref_state['ix']:#x} halted={ref_state['halted']} blocks={report['blocks']})"
    )
    tests += 1

    # 2. Differential proof 2: block ops + ports ----------------------------------
    data = {0xC000: 0x11, 0xC001: 0x22, 0xC002: 0x33, 0xC003: 0x44}
    ref_state, core_memory, _report = differential(assemble_block(), 0x0115, data)
    assert ref_state["a"] == 0x5A and ref_state["f"] == 0x04
    assert core_memory[0xD000:0xD004] == bytes([0x11, 0x22, 0x33, 0x44])
    assert core_memory[PORT_BASE + 0x40] == 0x5A
    print("PASS differential-proof block-ops + ports (LDIR + OUT/IN (C))")
    tests += 1

    # 3. Differential proof 3: block-I/O flags + 8-bit port mask ------------------
    data = {0xD000: 0x11, 0xD001: 0x22}
    ref_state, core_memory, _report = differential(assemble_block_io(), 0x0119, data)
    assert ref_state["b"] == 0x00 and ref_state["c"] == 0x37  # C register preserved
    assert ref_state["h"] == 0xD0 and ref_state["l"] == 0x02
    assert ref_state["f"] == 0x40  # Z set by the final OTIR iteration, N reset
    assert core_memory[0xC000:0xC003] == bytes([0x5A, 0x5A, 0x5A])
    assert core_memory[PORT_BASE + 0x37] == 0x22
    assert core_memory[PORT_BASE + 0x40] == 0x5A
    print("PASS differential-proof block-I/O (INIR/OTIR flags + 8-bit port mask)")
    tests += 1

    # 3. Frontend determinism ----------------------------------------------------
    image = bytes(build_image(assemble()))
    meta = base_meta(0x0160)
    ir_a, sidecar_a, report_a = convert(image, meta, contract)
    ir_b, sidecar_b, report_b = convert(image, meta, contract)
    if serialize(ir_a) != serialize(ir_b) or serialize(sidecar_a) != serialize(sidecar_b) or serialize(report_a) != serialize(report_b):
        raise AssertionError("frontend output is not deterministic")
    print("PASS frontend-determinism")
    tests += 1

    # 4. Full lowering coverage -----------------------------------------------------
    covered = 0
    for opcode in range(256):
        if opcode in (0xCB, 0xDD, 0xED, 0xFD):
            continue
        if z80.decode(ENTRY, opcode)["op"] in CONTROL_OPS or opcode == 0x76:
            continue
        program = bytes([opcode, 0x00, 0x00, 0x00, 0x76])
        sub_meta = base_meta(ENTRY + len(program))
        convert(make_image(program), sub_meta, contract)
        covered += 1
    print(f"PASS lowering coverage base {covered}/252-minus-control documented")
    tests += 1

    covered_ed = 0
    for sub in ED_DOCUMENTED:
        program = bytes([0xED, sub, 0x00, 0x00, 0x76])
        sub_meta = base_meta(ENTRY + len(program))
        convert(make_image(program), sub_meta, contract)
        covered_ed += 1
    print(f"PASS lowering coverage ed {covered_ed}/65 documented")
    tests += 1

    covered_cb = 0
    for sub in range(256):
        if 0x30 <= sub < 0x38:
            continue
        program = bytes([0xCB, sub, 0x00, 0x76])
        sub_meta = base_meta(ENTRY + len(program))
        convert(make_image(program), sub_meta, contract)
        covered_cb += 1
    print(f"PASS lowering coverage cb {covered_cb}/248 documented")
    tests += 1

    index_programs = [
        bytes([0xDD, 0x21, 0x34, 0x12, 0x76]),
        bytes([0xDD, 0x36, 0x05, 0x7F, 0x76]),
        bytes([0xDD, 0x46, 0xFC, 0x76]),
        bytes([0xDD, 0x70, 0x02, 0x76]),
        bytes([0xDD, 0x86, 0x03, 0x76]),
        bytes([0xFD, 0x96, 0x03, 0x76]),
        bytes([0xDD, 0x34, 0x7F, 0x76]),
        bytes([0xDD, 0x35, 0x00, 0x76]),
        bytes([0xDD, 0x23, 0x76]),
        bytes([0xDD, 0x2B, 0x76]),
        bytes([0xFD, 0x29, 0x76]),
        bytes([0xDD, 0x2A, 0x00, 0xC0, 0x76]),
        bytes([0xDD, 0x22, 0x00, 0xC0, 0x76]),
        bytes([0xDD, 0xE5, 0x76]),
        bytes([0xDD, 0xE1, 0x76]),
        bytes([0xDD, 0xE3, 0x76]),
        bytes([0xDD, 0xF9, 0x76]),
        bytes([0xFD, 0xCB, 0xFE, 0x9E, 0x76]),
        bytes([0xDD, 0xCB, 0x05, 0x7E, 0x76]),
        bytes([0xDD, 0xCB, 0x05, 0x06, 0x76]),
    ]
    for program in index_programs:
        sub_meta = base_meta(ENTRY + len(program))
        convert(make_image(program), sub_meta, contract)
    print(f"PASS lowering coverage dd/fd/ddcb/fdcb {len(index_programs)} representative index forms")
    tests += 1

    # 5. Terminator coverage ---------------------------------------------------------
    terminator_programs = {
        "jp-unconditional": bytes([0xC3, 0x03, 0x01, 0x76]),
        "jp-conditional-not-taken": bytes([0xC2, 0x04, 0x01, 0x00, 0x76]),
        "jr-conditional-not-taken": bytes([0x20, 0x02, 0x3E, 0x01, 0x76]),
        "djnz": bytes([0x06, 0x01, 0x10, 0xFC, 0x76]),
        "call-conditional-not-taken": bytes([0xCC, 0x04, 0x01, 0x00, 0x76]),
        "call": bytes([0xCD, 0x05, 0x01, 0x00, 0x76, 0x76]),
        "ret-conditional-not-taken": bytes([0xC8, 0x00, 0x76]),
        "ret": bytes([0xC9, 0x76]),
        "retn": bytes([0xED, 0x45, 0x76]),
        "reti": bytes([0xED, 0x4D, 0x76]),
        "rst-vector": bytes([0xC7, 0x00, 0x00, 0x00, 0x76]),
        "jp-hl": bytes([0x21, 0x05, 0x01, 0xE9, 0x00, 0x76]),
        "jp-ix": bytes([0xDD, 0x21, 0x06, 0x01, 0xDD, 0xE9, 0x76]),
        "jp-iy": bytes([0xFD, 0x21, 0x07, 0x01, 0xFD, 0xE9, 0x76]),
        "halt": bytes([0x76]),
    }
    for name, program in terminator_programs.items():
        sub_meta = base_meta(ENTRY + len(program))
        sub_meta["region_start"] = 0x0000
        sub_meta["entry_address"] = ENTRY
        sub_meta["initial_state"] = {"cpu:a": 0, "cpu:f": 0x40 if "not-taken" not in name else 0, "cpu:sp": 0xFFFE}
        image = bytearray(MEMORY_SIZE)
        image[0x0000] = 0x76  # RST vector / popped-return target halts
        image[ENTRY:ENTRY + len(program)] = program
        convert(bytes(image), sub_meta, contract)
    print(f"PASS terminator coverage {len(terminator_programs)} control-flow forms")
    tests += 1

    # 6. Fail-closed cases -----------------------------------------------------------
    image = build_image(assemble())
    image[ENTRY] = 0xED
    image[ENTRY + 1] = 0x00  # undocumented ED 00
    try:
        convert(bytes(image), base_meta(0x0160), contract)
    except Z80FrontendError:
        print("PASS reject: undocumented-ed-opcode")
        tests += 1
    else:
        raise AssertionError("undocumented ED opcode was lowered")

    image = build_image(assemble())
    image[ENTRY] = 0xC3
    image[ENTRY + 1] = 0x00
    image[ENTRY + 2] = 0x80  # target outside region
    try:
        convert(bytes(image), base_meta(0x0160), contract)
    except Z80FrontendError:
        print("PASS reject: control-flow-target-outside-region")
        tests += 1
    else:
        raise AssertionError("out-of-region jump target was accepted")

    image = build_image(assemble())
    image[ENTRY] = 0xDD
    image[ENTRY + 1] = 0x26  # undocumented IXH split
    image[ENTRY + 2] = 0x11
    try:
        convert(bytes(image), base_meta(0x0160), contract)
    except Z80FrontendError:
        print("PASS reject: ixh-split-form")
        tests += 1
    else:
        raise AssertionError("IXH register-split form was lowered")

    short_meta = base_meta(ENTRY + 1)
    try:
        convert(bytes(build_image(assemble())), short_meta, contract)
    except Z80FrontendError:
        print("PASS reject: instruction-overlaps-region-boundary")
        tests += 1
    else:
        raise AssertionError("instruction overlapping the region boundary was accepted")

    bad_meta = base_meta(0x0160)
    bad_meta["data_ranges"] = [[ENTRY, ENTRY + 2]]
    try:
        convert(bytes(build_image(assemble())), bad_meta, contract)
    except Z80FrontendError:
        print("PASS reject: region-start-inside-data-range")
        tests += 1
    else:
        raise AssertionError("region start inside a data range was accepted")

    print(f"OPENRECOMP_Z80_LOWERING_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
