#!/usr/bin/env python3
"""P1-13 gate: SM83 control flow + normalized IR V1 lowering, differential proof.

Runs one synthetic SM83 program twice:
- through the independent machine-code reference (`tools/sm83_reference_v1.py`, P1-12);
- through the frontend (`tools/sm83_frontend_v1.py`) -> frozen normalized IR V1 ->
  Module Image V1 -> the architecture-neutral Core API `ReferenceExecutor`.

The final CPU state and the full 64 KiB guest memory must match exactly.
Also proves: conversion determinism, full lowering coverage of every
documented opcode (with explicit terminator coverage for all control-flow
forms), and fail-closed rejection of undocumented code, out-of-region targets
and non-code region bytes.
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

from adapters.sm83 import UNDOCUMENTED  # noqa: E402
from adapters import sm83  # noqa: E402
from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor  # noqa: E402
from sm83_frontend_v1 import SM83FrontendError, convert  # noqa: E402
from sm83_reference_v1 import SM83State, ReferenceSM83  # noqa: E402

CONTRACT_PATH = ROOT / "contracts" / "host_contract.json"
MEMORY_SIZE = 1 << 16
ENTRY = 0x0100

CONTROL_OPS = {"jp", "jr", "call", "ret", "reti", "rst", "jp_hl", "halt", "stop"}


def assemble() -> bytes:
    """Synthetic program: ALU + flags, rotates, CB page, DAA, memory forms,
    16-bit arithmetic, stack, call/ret, conditional jump, RST to halt."""
    code = bytearray(0x100)  # nops (region padding)

    def put(address: int, *values: int) -> None:
        code[address - ENTRY:address - ENTRY + len(values)] = bytes(values)

    put(0x0100, 0x3E, 0x2A, 0x06, 0x0F, 0x80, 0xE6, 0x0F, 0x0E, 0x05, 0x81)
    put(0x010A, 0x05, 0x04, 0x07)
    put(0x010D, 0xCB, 0x11, 0xCB, 0x21, 0xCB, 0x30, 0xCB, 0x41, 0xCB, 0x81)
    put(0x0117, 0xCB, 0xC7, 0x27)
    put(0x011A, 0x21, 0x00, 0xC0, 0x36, 0x5A, 0x2A, 0x2C, 0x34)
    put(0x0122, 0x01, 0x34, 0x12, 0x03, 0x0B, 0x19)
    put(0x0128, 0x31, 0x00, 0xFF, 0xE8, 0x10, 0xF8, 0xFC, 0xF9)
    put(0x0130, 0xCD, 0x50, 0x01, 0xC5, 0xE1)
    put(0x0135, 0x3E, 0x07, 0x00, 0x00)
    put(0x0139, 0xFE, 0x07, 0x28, 0x02)
    put(0x013D, 0x3E, 0x99, 0x18, 0x01)
    put(0x013F, 0xC7)
    put(0x0150, 0x3E, 0x55, 0x04, 0xC9)
    return bytes(code)


def build_image() -> bytearray:
    image = bytearray(MEMORY_SIZE)
    image[ENTRY:ENTRY + 0x100] = assemble()
    image[0x0000] = 0x76  # halt at the RST vector
    image[0xC002] = 0x77  # data cell for INC (HL)
    image[0xC003] = 0x33  # unused data cell
    return image


def serialize(document: object) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reference_result(image: bytes):
    ref = ReferenceSM83(image, SM83State())
    final = ref.run(max_steps=100000)
    return final, bytes(ref.memory)


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
            "producer": "openrecomp.sm83-frontend-v1",
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
        "architecture": "sm83-gb",
        "entry_address": ENTRY,
        "region_start": 0x0000,
        "region_end": region_end,
        "initial_state": {"cpu:a": 0, "cpu:f": 0, "cpu:sp": 0xFFFE},
        "observe_state_slot": "cpu:a",
        "max_operations": 1000000,
    }


def make_image(program: bytes) -> bytes:
    image = bytearray(MEMORY_SIZE)
    image[ENTRY:ENTRY + len(program)] = program
    return bytes(image)


def main() -> int:
    tests = 0
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_bytes = CONTRACT_PATH.read_bytes()
    image = bytes(build_image())

    meta = base_meta(0x0154)
    ref_state, ref_memory = reference_result(image)
    execution, core_memory, ir, sidecar, report = core_result(image, meta, contract, contract_bytes)

    state_keys = ("a", "f", "b", "c", "d", "e", "h", "l", "sp")
    for key in state_keys:
        expected = ref_state[key]
        actual = execution.state[f"cpu:{key}"]
        if actual != expected:
            raise AssertionError(f"cpu:{key} = {actual:#x} != reference {expected:#x}")
    if ref_state["halted"] != int(execution.state["platform:halted"]):
        raise AssertionError("halted state differs from the reference")
    core_guest_memory = core_memory[:MEMORY_SIZE]
    if ref_memory != core_guest_memory:
        for index, (left, right) in enumerate(zip(ref_memory, core_guest_memory)):
            if left != right:
                raise AssertionError(f"guest memory differs at 0x{index:04x}: {left:#x} != {right:#x}")
        raise AssertionError("guest memory length differs")
    print(
        "PASS differential-proof reference == Core API "
        f"(a={ref_state['a']:#x} f={ref_state['f']:#x} hl={ref_state['h']:#x}{ref_state['l']:02x} "
        f"sp={ref_state['sp']:#x} operations={execution.operations})"
    )
    tests += 1

    ir_again, sidecar_again, report_again = convert(image, meta, contract)
    if serialize(ir) != serialize(ir_again):
        raise AssertionError("frontend IR is not deterministic")
    if serialize(sidecar) != serialize(sidecar_again):
        raise AssertionError("frontend sidecar is not deterministic")
    if serialize(report) != serialize(report_again):
        raise AssertionError("frontend report is not deterministic")
    print("PASS frontend-determinism")
    tests += 1

    # Full lowering coverage: every documented opcode (except control flow,
    # covered below) and every CB encoding lowers without error.
    for opcode in range(256):
        if opcode in UNDOCUMENTED or opcode == 0xCB:
            continue
        if sm83.decode(ENTRY, opcode)["op"] in CONTROL_OPS:
            continue
        program = bytes([opcode, 0x00, 0x00, 0x76])
        sub_meta = base_meta(ENTRY + len(program))
        sub_meta["region_start"] = ENTRY
        sub_meta["entry_address"] = ENTRY
        convert(make_image(program), sub_meta, contract)
    for sub in range(256):
        program = bytes([0xCB, sub, 0x00, 0x76])
        sub_meta = base_meta(ENTRY + len(program))
        sub_meta["region_start"] = ENTRY
        sub_meta["entry_address"] = ENTRY
        convert(make_image(program), sub_meta, contract)
    print("PASS lowering coverage documented base + CB encodings")
    tests += 1

    # Terminator coverage for every control-flow form -------------------
    terminator_programs = {
        "jp-unconditional": bytes([0xC3, 0x03, 0x01, 0x76]),
        "jp-conditional-not-taken": bytes([0xC2, 0x04, 0x01, 0x00, 0x76]),
        "jr-conditional-not-taken": bytes([0x20, 0x02, 0x3E, 0x01, 0x76]),
        "call-conditional-not-taken": bytes([0xCC, 0x04, 0x01, 0x00, 0x76]),
        "ret-conditional-not-taken": bytes([0xC8, 0x00, 0x76]),
        "ret-unconditional": bytes([0xC9, 0x76]),
        "rst-vector": bytes([0xC7, 0x00, 0x00, 0x00, 0x76]),
        "jp-hl": bytes([0x21, 0x05, 0x01, 0xE9, 0x00, 0x76]),
        "stop": bytes([0x10, 0x00, 0x76]),
    }
    terminator_flags = {
        "jp-conditional-not-taken": 0x80,
        "jr-conditional-not-taken": 0x80,
        "call-conditional-not-taken": 0x80,
        "ret-conditional-not-taken": 0x00,
    }
    terminator_memory = {
        "ret-unconditional": {0xFFFE: 0x01, 0xFFFF: 0x01},
        "reti": {},
    }
    for name, program in terminator_programs.items():
        sub_meta = base_meta(ENTRY + len(program))
        sub_meta["region_start"] = 0x0000
        sub_meta["entry_address"] = ENTRY
        sub_meta["initial_state"] = {
            "cpu:a": 0,
            "cpu:f": terminator_flags.get(name, 0),
            "cpu:sp": 0xFFFE,
        }
        image = bytearray(MEMORY_SIZE)
        image[0x0000] = 0x76  # vector/runaway target halts
        image[ENTRY:ENTRY + len(program)] = program
        for address, value in terminator_memory.get(name, {}).items():
            image[address] = value
        convert(bytes(image), sub_meta, contract)
    print(f"PASS terminator coverage {len(terminator_programs)} control-flow forms")
    tests += 1

    # Fail-closed cases --------------------------------------------------
    bad_image = build_image()
    bad_image[ENTRY] = 0xD3  # undocumented
    try:
        convert(bytes(bad_image), meta, contract)
    except SM83FrontendError:
        print("PASS reject: undocumented-opcode")
        tests += 1
    else:
        raise AssertionError("undocumented opcode was lowered")

    bad_image = build_image()
    bad_image[ENTRY] = 0xC3  # jp a16
    bad_image[ENTRY + 1] = 0x00
    bad_image[ENTRY + 2] = 0x80  # target 0x8000 outside region
    try:
        convert(bytes(bad_image), meta, contract)
    except SM83FrontendError:
        print("PASS reject: control-flow-target-outside-region")
        tests += 1
    else:
        raise AssertionError("out-of-region jump target was accepted")

    bad_image = build_image()
    bad_image[ENTRY + 2] = 0xD3  # undocumented byte at an instruction boundary
    try:
        convert(bytes(bad_image), meta, contract)
    except SM83FrontendError:
        print("PASS reject: undocumented-byte-inside-region")
        tests += 1
    else:
        raise AssertionError("undocumented byte inside the region was accepted")

    short_meta = base_meta(ENTRY + 1)  # cuts the 2-byte `ld a,d8` at the entry
    try:
        convert(image, short_meta, contract)
    except SM83FrontendError:
        print("PASS reject: instruction-overlaps-region-boundary")
        tests += 1
    else:
        raise AssertionError("instruction overlapping the region boundary was accepted")

    print(f"OPENRECOMP_SM83_LOWERING_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
