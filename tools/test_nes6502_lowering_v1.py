#!/usr/bin/env python3
"""P1-31 gate: NES 6502 control flow + normalized IR V1 lowering, differential proof.

Runs synthetic NMOS 6502 programs twice:
- through the independent machine-code reference (`tools/nes6502_reference_v1.py`);
- through the frontend (`tools/nes6502_frontend_v1.py`) -> frozen normalized IR
  V1 -> Module Image V1 -> the architecture-neutral Core API
  `ReferenceExecutor`.

The final CPU state (A/X/Y/SP/P and the halted PC), the full 64 KiB guest
memory must match exactly. Also proves: conversion determinism, full lowering
coverage of every non-control official opcode, terminator coverage for every
documented control-flow form (including the NMOS JMP-indirect page bug),
and fail-closed rejection of undocumented encodings, out-of-region targets,
truncated instructions and malformed data ranges.
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

from adapters.nes6502 import FLAG_I, FLAG_UNUSED, OFFICIAL, decode_full, is_control_flow  # noqa: E402
from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor  # noqa: E402
from nes6502_frontend_v1 import NES6502FrontendError, convert  # noqa: E402
from nes6502_reference_v1 import (  # noqa: E402
    MEMORY_SIZE,
    NES6502ReferenceError,
    NES6502State,
    ReferenceNES6502,
)

CONTRACT_PATH = ROOT / "contracts" / "host_contract.json"
ENTRY = 0x0100
HALT = 0x02
BASE = FLAG_UNUSED | FLAG_I


def serialize(document: object) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_image(program: bytes, data: dict[int, int] | None = None) -> bytearray:
    image = bytearray([HALT] * MEMORY_SIZE)
    image[ENTRY:ENTRY + len(program)] = program
    for address, value in (data or {}).items():
        image[address] = value & 0xFF
    return image


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
            "producer": "openrecomp.nes6502-frontend-v1",
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


def base_meta(
    region_end: int,
    *,
    region_start: int = ENTRY,
    extra_leaders=None,
    data_ranges=None,
    initial_state=None,
) -> dict:
    meta = {
        "architecture": "nes6502",
        "entry_address": ENTRY,
        "region_start": region_start,
        "region_end": region_end,
        "initial_state": initial_state
        or {
            "cpu:a": 0x00, "cpu:x": 0x00, "cpu:y": 0x00, "cpu:sp": 0xFD,
            "cpu:pc": ENTRY, "cpu:p": BASE, "platform:halted": 0,
        },
        "observe_state_slot": "cpu:a",
        "max_operations": 1000000,
    }
    if extra_leaders is not None:
        meta["extra_leaders"] = list(extra_leaders)
    if data_ranges is not None:
        meta["data_ranges"] = [list(item) for item in data_ranges]
    return meta


def differential(
    image: bytes,
    region_end: int,
    *,
    region_start: int = ENTRY,
    extra_leaders=None,
    data_ranges=None,
    initial: NES6502State | None = None,
) -> tuple[dict, bytes, dict]:
    ref = ReferenceNES6502(image, initial or NES6502State(pc=ENTRY, sp=0xFD, p=BASE))
    ref_state = ref.run(max_steps=100000)
    meta = base_meta(region_end, region_start=region_start, extra_leaders=extra_leaders, data_ranges=data_ranges)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_bytes = CONTRACT_PATH.read_bytes()
    execution, core_memory, _ir, _sidecar, report = core_result(image, meta, contract, contract_bytes)
    for key, expected in ref_state.items():
        if key == "steps":
            continue
        slot = "platform:halted" if key == "halted" else f"cpu:{key}"
        actual = execution.state[slot]
        if key == "halted":
            actual = int(actual)
        if int(actual) != int(expected):
            raise AssertionError(f"{slot} = {actual:#x} != reference {expected:#x}")
    if bytes(ref.memory) != core_memory[:MEMORY_SIZE]:
        for index, (left, right) in enumerate(zip(ref.memory, core_memory[:MEMORY_SIZE])):
            if left != right:
                raise AssertionError(f"guest memory differs at 0x{index:04x}: {left:#x} != {right:#x}")
        raise AssertionError("guest memory length differs")
    return ref_state, core_memory, report


def assemble_main() -> tuple[bytes, int]:
    image = build_image(b"")
    def put(address: int, *values: int) -> None:
        image[address:address + len(values)] = bytes(values)
    put(0x0100, 0xA9, 0x2A)
    put(0x0102, 0xAA)
    put(0x0103, 0xA8)
    put(0x0104, 0xE8)
    put(0x0105, 0x88)
    put(0x0106, 0x8A)
    put(0x0107, 0x48)
    put(0x0108, 0xA9, 0x00)
    put(0x010A, 0x68)
    put(0x010B, 0x29, 0x0F)
    put(0x010D, 0x09, 0xF0)
    put(0x010F, 0x49, 0x0F)
    put(0x0111, 0x69, 0x11)
    put(0x0113, 0xE9, 0x02)
    put(0x0115, 0xC9, 0xFF)
    put(0x0117, 0x85, 0x10)
    put(0x0119, 0xA6, 0x10)
    put(0x011B, 0xE6, 0x10)
    put(0x011D, 0xC6, 0x10)
    put(0x011F, 0x0A)
    put(0x0120, 0x4A)
    put(0x0121, 0x2A)
    put(0x0122, 0x6A)
    put(0x0123, 0x20, 0x30, 0x01)
    put(0x0126, 0x4C, 0x40, 0x01)
    put(0x0130, 0xA9, 0x55)
    put(0x0132, 0x60)
    put(0x0140, 0xA2, 0x42)
    put(0x0142, HALT)
    return bytes(image), 0x0143


def assemble_indirect() -> tuple[bytes, int, list[int]]:
    image = build_image(b"")
    def put(address: int, *values: int) -> None:
        image[address:address + len(values)] = bytes(values)
    put(0x0100, 0xA0, 0x05)
    put(0x0102, 0xB1, 0x10)
    put(0x0104, 0x85, 0x20)
    put(0x0106, 0xA2, 0x04)
    put(0x0108, 0xA1, 0x10)
    put(0x010A, 0x85, 0x21)
    put(0x010C, 0x6C, 0xFF, 0x02)
    put(0x0500, 0xA9, 0x77)
    put(0x0502, HALT)
    image[0x0010] = 0x00
    image[0x0011] = 0x03
    image[0x0014] = 0x00
    image[0x0015] = 0x04
    image[0x0305] = 0x11
    image[0x0400] = 0x22
    image[0x02FF] = 0x00
    image[0x0200] = 0x05
    return bytes(image), 0x0503, [0x0500]


def assemble_brk() -> tuple[bytes, int, list[int]]:
    image = build_image(b"")
    def put(address: int, *values: int) -> None:
        image[address:address + len(values)] = bytes(values)
    put(0x0100, 0x00, 0xEA)
    put(0x0102, 0xA9, 0x33)
    put(0x0104, HALT)
    put(0x0200, 0xA9, 0x44)
    put(0x0202, 0x40)
    put(0x0203, HALT)
    image[0xFFFE] = 0x00
    image[0xFFFF] = 0x02
    return bytes(image), 0x0204, [0x0200]


def main() -> int:
    tests = 0
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_bytes = CONTRACT_PATH.read_bytes()

    # 1. Differential: full ALU/memory/stack/branch/jsr-rts program ----------
    image, region_end = assemble_main()
    ref_state, core_memory, report = differential(image, region_end)
    assert ref_state["x"] == 0x42 and ref_state["a"] == 0x55, ref_state
    assert ref_state["pc"] == 0x0142 and ref_state["halted"] == 1, ref_state
    assert core_memory[0x10] == 0x03
    print(
        "PASS differential-proof reference == Core API "
        f"(a={ref_state['a']:#x} x={ref_state['x']:#x} sp={ref_state['sp']:#x} "
        f"p={ref_state['p']:#x} pc={ref_state['pc']:#x} blocks={report['blocks']})"
    )
    tests += 1

    # 2. Differential: indirect addressing + JMP-indirect page bug -----------
    image, region_end, extra = assemble_indirect()
    ref_state, core_memory, _report = differential(
        image, region_end, extra_leaders=extra, data_ranges=[[0x0300, 0x0310], [0x03F8, 0x0408]]
    )
    assert ref_state["a"] == 0x77 and ref_state["x"] == 0x04, ref_state
    assert core_memory[0x20] == 0x11 and core_memory[0x21] == 0x22
    print("PASS differential-proof indirect modes + JMP-indirect page bug")
    tests += 1

    # 3. Differential: BRK / RTI --------------------------------------------
    image, region_end, extra = assemble_brk()
    ref_state, _core_memory, _report = differential(image, region_end, extra_leaders=extra)
    assert ref_state["a"] == 0x33, hex(ref_state["a"])
    assert ref_state["sp"] == 0xFD, hex(ref_state["sp"])
    print("PASS differential-proof BRK/RTI stack + vector")
    tests += 1

    # 4. Frontend determinism -------------------------------------------------
    image, region_end = assemble_main()
    meta = base_meta(region_end)
    ir_a, sidecar_a, report_a = convert(image, meta, contract)
    ir_b, sidecar_b, report_b = convert(image, meta, contract)
    if serialize(ir_a) != serialize(ir_b) or serialize(sidecar_a) != serialize(sidecar_b) or serialize(report_a) != serialize(report_b):
        raise AssertionError("frontend output is not deterministic")
    print("PASS frontend-determinism")
    tests += 1

    # 5. Full lowering coverage of every non-control official opcode ---------
    covered = 0
    for opcode in sorted(OFFICIAL):
        insn = decode_full(bytes([opcode, HALT, HALT, HALT]), 0)
        if is_control_flow(insn):
            continue
        program = bytes([opcode, HALT, HALT, HALT, HALT])
        sub_meta = base_meta(ENTRY + len(program))
        convert(build_image(program), sub_meta, contract)
        covered += 1
    print(f"PASS lowering coverage non-control official {covered}/137")
    assert covered == 137, covered
    tests += 1

    # 6. Terminator coverage --------------------------------------------------
    terminator_programs = {
        "jmp-abs": (bytes([0x4C, 0x05, 0x01, HALT, HALT, 0xA9, 0x42, HALT]), {}),
        "jmp-indirect": (bytes([0x6C, 0xFF, 0x02]), {0x02FF: 0x00, 0x0200: 0x05, 0x0500: 0xA9, 0x0501: 0x77, 0x0502: HALT}),
        "beq-taken": (bytes([0xF0, 0x02, HALT, HALT, 0xA9, 0x42, HALT]), {}),
        "bne-not-taken": (bytes([0xD0, 0x02, HALT, HALT, 0xA9, 0x42, HALT]), {}),
        "bpl": (bytes([0x10, 0x02, HALT, HALT, 0xA9, 0x42, HALT]), {}),
        "bmi": (bytes([0x30, 0x02, HALT, HALT, 0xA9, 0x42, HALT]), {}),
        "bcc": (bytes([0x90, 0x02, HALT, HALT, 0xA9, 0x42, HALT]), {}),
        "bcs": (bytes([0xB0, 0x02, HALT, HALT, 0xA9, 0x42, HALT]), {}),
        "bvc": (bytes([0x50, 0x02, HALT, HALT, 0xA9, 0x42, HALT]), {}),
        "bvs": (bytes([0x70, 0x02, HALT, HALT, 0xA9, 0x42, HALT]), {}),
        "jsr-rts": (bytes([0x20, 0x07, 0x01, HALT, HALT, HALT, HALT, 0xA9, 0x42, 0x60, HALT]), {}),
        "rts": (bytes([0x60, HALT]), {}),
        "rti": (bytes([0x40, HALT]), {}),
        "brk": (bytes([0x00, 0xEA, HALT]), {}),
        "halt": (bytes([HALT]), {}),
    }
    for name, (program, data) in terminator_programs.items():
        sub_meta = base_meta(ENTRY + len(program))
        convert(build_image(program, data), sub_meta, contract)
    print(f"PASS terminator coverage {len(terminator_programs)} control-flow forms")
    tests += 1

    # 7. Fail-closed cases ----------------------------------------------------
    short_meta = base_meta(ENTRY + 1)
    image, _end = assemble_main()
    try:
        convert(image, short_meta, contract)
    except NES6502FrontendError:
        print("PASS reject: instruction-overlaps-region-boundary")
        tests += 1
    else:
        raise AssertionError("instruction overlapping the region boundary was accepted")

    image = build_image(bytes([0x03, HALT]))
    try:
        convert(image, base_meta(ENTRY + 2), contract)
    except NES6502FrontendError:
        print("PASS reject: undocumented-opcode")
        tests += 1
    else:
        raise AssertionError("undocumented opcode was lowered")

    image = build_image(bytes([0x4C, 0x00, 0x80, HALT]))
    try:
        convert(image, base_meta(ENTRY + 4), contract)
    except NES6502FrontendError:
        print("PASS reject: control-flow-target-outside-region")
        tests += 1
    else:
        raise AssertionError("out-of-region jump target was accepted")

    image = build_image(bytes([0x4C, 0x00]))
    try:
        convert(image, base_meta(ENTRY + 4), contract)
    except NES6502FrontendError:
        print("PASS reject: truncated-instruction")
        tests += 1
    else:
        raise AssertionError("truncated instruction was accepted")

    image = build_image(b"")
    bad_meta = base_meta(ENTRY + 2, region_start=0)
    bad_meta["data_ranges"] = [[ENTRY, ENTRY + 2]]
    try:
        convert(image, bad_meta, contract)
    except NES6502FrontendError:
        print("PASS reject: region-start-inside-data-range")
        tests += 1
    else:
        raise AssertionError("region start inside a data range was accepted")

    try:
        convert(bytes(16), base_meta(ENTRY + 2), contract)
    except NES6502FrontendError:
        print("PASS reject: short-memory-image")
        tests += 1
    else:
        raise AssertionError("short memory image was accepted")

    print(f"OPENRECOMP_NES6502_LOWERING_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
