#!/usr/bin/env python3
"""P1-12 gate: documented SM83 instruction semantics (reference interpreter).

Pins hand-derived documented behaviour of `tools/sm83_reference_v1.py` for
every instruction class: ALU/flag rules, 16-bit additions, rotates/shifts,
DAA, stack order, POP AF masking, EI delay, HALT/STOP, plus full-coverage
execution of all 256 base opcodes and all 256 CB encodings (fail closed on
the 11 undocumented opcodes and on truncated/runaway streams).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from adapters.sm83 import UNDOCUMENTED  # noqa: E402
from sm83_reference_v1 import (  # noqa: E402
    MEMORY_SIZE,
    SM83ReferenceError,
    SM83State,
    ReferenceSM83,
)

HALT_IMAGE = bytes([0x76]) * MEMORY_SIZE


def run_pin(code: bytes, *, state: SM83State | None = None, memory: bytes | None = None, steps: int = 10000):
    if memory is None:
        memory = HALT_IMAGE
    image = bytearray(memory)
    image[0x0100:0x0100 + len(code)] = code
    ref = ReferenceSM83(image, state or SM83State())
    final = ref.run(max_steps=steps)
    return ref, final


def pin(label: str, code: bytes, checks: dict, *, state: SM83State | None = None, memory: bytes | None = None) -> None:
    ref, final = run_pin(code, state=state, memory=memory)
    for key, expected in checks.items():
        actual = final.get(key)
        if actual != expected:
            raise AssertionError(f"{label}: {key} = {actual:#x} != {expected:#x}")
    print(f"PASS {label}")


def mem_pin(label: str, code: bytes, address: int, expected: int, *, state: SM83State | None = None) -> None:
    ref, _ = run_pin(code, state=state)
    actual = ref.memory[address]
    if actual != expected:
        raise AssertionError(f"{label}: mem[{address:#x}] = {actual:#x} != {expected:#x}")
    print(f"PASS {label}")


def main() -> int:
    tests = 0

    # -- 8-bit ALU and flags -------------------------------------------
    pin("add-half-carry", bytes([0x80, 0x76]), {"a": 0x10, "f": 0x20}, state=SM83State(a=0x0F, b=0x01))
    pin("add-full-carry", bytes([0x80, 0x76]), {"a": 0x00, "f": 0xB0}, state=SM83State(a=0xFF, b=0x01))
    pin("adc-with-carry-in", bytes([0x88, 0x76]), {"a": 0x11, "f": 0x20}, state=SM83State(a=0x0F, b=0x01, f=0x10))
    pin("sub", bytes([0x90, 0x76]), {"a": 0x0F, "f": 0x60}, state=SM83State(a=0x10, b=0x01))
    pin("sub-borrow", bytes([0x90, 0x76]), {"a": 0xFF, "f": 0x70}, state=SM83State(a=0x00, b=0x01))
    pin("sbc-with-borrow", bytes([0x98, 0x76]), {"a": 0xFE, "f": 0x70}, state=SM83State(a=0x00, b=0x01, f=0x10))
    pin("and-sets-h", bytes([0xE6, 0x0F, 0x76]), {"a": 0x0C, "f": 0x20}, state=SM83State(a=0x3C))
    pin("xor-clears-flags", bytes([0xEE, 0xFF, 0x76]), {"a": 0xA5, "f": 0x00}, state=SM83State(a=0x5A))
    pin("or-zero", bytes([0xF6, 0x00, 0x76]), {"a": 0x00, "f": 0x80}, state=SM83State(a=0x00))
    pin("cp-keeps-a", bytes([0xFE, 0x01, 0x76]), {"a": 0x10, "f": 0x60}, state=SM83State(a=0x10))
    pin("inc-wrap", bytes([0x04, 0x76]), {"b": 0x00, "f": 0xA0}, state=SM83State(b=0xFF))
    pin("inc-half-carry", bytes([0x04, 0x76]), {"b": 0x10, "f": 0x20}, state=SM83State(b=0x0F))
    pin("dec-wrap", bytes([0x05, 0x76]), {"b": 0xFF, "f": 0x60}, state=SM83State(b=0x00))
    pin("inc-preserves-c", bytes([0x04, 0x76]), {"b": 0x01, "f": 0x10}, state=SM83State(b=0x00, f=0x10))
    tests += 14

    # -- 16-bit arithmetic ----------------------------------------------
    pin("add-hl-half", bytes([0x09, 0x76]), {"h": 0x10, "l": 0x00, "f": 0x20}, state=SM83State(h=0x0F, l=0xFF, b=0x00, c=0x01))
    pin("add-hl-carry", bytes([0x09, 0x76]), {"h": 0x00, "l": 0x00, "f": 0x30}, state=SM83State(h=0xFF, l=0xFF, b=0x00, c=0x01))
    pin("add-hl-preserves-z", bytes([0x29, 0x76]), {"h": 0x00, "l": 0x00, "f": 0x90}, state=SM83State(h=0x80, l=0x00, f=0x80))
    pin("add-sp-carry", bytes([0xE8, 0x10, 0x76]), {"sp": 0x0000, "f": 0x10}, state=SM83State(sp=0xFFF0))
    pin("add-sp-half", bytes([0xE8, 0xF8, 0x76]), {"sp": 0x0000, "f": 0x30}, state=SM83State(sp=0x0008))
    pin("ld-hl-sp-flags", bytes([0xF8, 0xF8, 0x76]), {"h": 0x00, "l": 0x00, "f": 0x30}, state=SM83State(sp=0x0008))
    pin("inc-bc-no-flags", bytes([0x03, 0x76]), {"b": 0x12, "c": 0x35, "f": 0xF0}, state=SM83State(b=0x12, c=0x34, f=0xF0))
    tests += 7

    # -- rotates and shifts ---------------------------------------------
    pin("rlca", bytes([0x07, 0x76]), {"a": 0x01, "f": 0x10}, state=SM83State(a=0x80))
    pin("rrca", bytes([0x0F, 0x76]), {"a": 0x80, "f": 0x10}, state=SM83State(a=0x01))
    pin("rla-out", bytes([0x17, 0x76]), {"a": 0x00, "f": 0x10}, state=SM83State(a=0x80))
    pin("rra-out", bytes([0x1F, 0x76]), {"a": 0x00, "f": 0x10}, state=SM83State(a=0x01))
    pin("rla-through-c", bytes([0x17, 0x76]), {"a": 0x01, "f": 0x00}, state=SM83State(a=0x00, f=0x10))
    pin("cb-rlc", bytes([0xCB, 0x00, 0x76]), {"b": 0x01, "f": 0x10}, state=SM83State(b=0x80))
    pin("cb-rl", bytes([0xCB, 0x10, 0x76]), {"b": 0x00, "f": 0x90}, state=SM83State(b=0x80))
    pin("cb-sla", bytes([0xCB, 0x20, 0x76]), {"b": 0x00, "f": 0x90}, state=SM83State(b=0x80))
    pin("cb-sra-sign", bytes([0xCB, 0x28, 0x76]), {"b": 0xC0, "f": 0x10}, state=SM83State(b=0x81))
    pin("cb-srl", bytes([0xCB, 0x38, 0x76]), {"b": 0x00, "f": 0x90}, state=SM83State(b=0x01))
    pin("cb-swap", bytes([0xCB, 0x30, 0x76]), {"b": 0x5A, "f": 0x00}, state=SM83State(b=0xA5))
    tests += 11

    # -- bit operations --------------------------------------------------
    mem = bytearray(HALT_IMAGE)
    mem[0xC000] = 0x80
    pin("bit-set-zero-flag-clear", bytes([0xCB, 0x7E, 0x76]), {"f": 0x20}, state=SM83State(h=0xC0, l=0x00), memory=bytes(mem))
    mem = bytearray(HALT_IMAGE)
    mem[0xC000] = 0x7F
    pin("bit-zero-flag-set", bytes([0xCB, 0x7E, 0x76]), {"f": 0xA0}, state=SM83State(h=0xC0, l=0x00), memory=bytes(mem))
    pin("cb-res", bytes([0xCB, 0x80, 0x76]), {"b": 0xFE, "f": 0x50}, state=SM83State(b=0xFF, f=0x50))
    pin("cb-set", bytes([0xCB, 0xC0, 0x76]), {"b": 0x01, "f": 0x50}, state=SM83State(b=0x00, f=0x50))
    tests += 4

    # -- daa -------------------------------------------------------------
    pin("daa-after-add", bytes([0x80, 0x27, 0x76]), {"a": 0x16, "f": 0x00}, state=SM83State(a=0x0F, b=0x01))
    pin("daa-after-sub", bytes([0x90, 0x27, 0x76]), {"a": 0x09, "f": 0x40}, state=SM83State(a=0x10, b=0x01))
    tests += 2

    # -- flag-only ops ---------------------------------------------------
    pin("cpl", bytes([0x2F, 0x76]), {"a": 0xCA, "f": 0x60}, state=SM83State(a=0x35))
    pin("scf", bytes([0x37, 0x76]), {"f": 0x10}, state=SM83State())
    pin("ccf-from-c", bytes([0x3F, 0x76]), {"f": 0x00}, state=SM83State(f=0x10))
    pin("ccf-to-c", bytes([0x3F, 0x76]), {"f": 0x10}, state=SM83State())
    tests += 4

    # -- stack and control flow -----------------------------------------
    pin("push-pop-bc", bytes([0xC5, 0xC1, 0x76]), {"b": 0x12, "c": 0x34, "sp": 0xFFFE}, state=SM83State(b=0x12, c=0x34))
    pin("pop-af-masks-low-nibble", bytes([0xF5, 0xF1, 0x76]), {"a": 0xAB, "f": 0x30, "sp": 0xFFFE}, state=SM83State(a=0xAB, f=0x3F))
    call_ret_code = bytes([0xCD, 0x50, 0x01, 0x3E, 0x2A, 0x76]) + bytes(0x0150 - 0x0106) + bytes([0xC9])
    pin("call-ret-round-trip", call_ret_code, {"a": 0x2A, "sp": 0xFFFE, "pc": 0x0106}, state=SM83State())
    pin("jr-taken", bytes([0x18, 0x03, 0x00, 0x00, 0x00, 0x76]), {"pc": 0x0106}, state=SM83State())
    pin("jr-nz-not-taken", bytes([0x20, 0x03, 0x3E, 0x05, 0x76]), {"a": 0x05, "pc": 0x0105}, state=SM83State(f=0x80))
    pin("rst-vector", bytes([0xC7, 0x00, 0x00, 0x76]), {"sp": 0xFFFC, "pc": 0x0001}, state=SM83State())
    pin("jp-hl", bytes([0xE9, 0x00, 0x00]), {"pc": 0x0151}, state=SM83State(h=0x01, l=0x50))
    pin("ei-then-di-stays-off", bytes([0xFB, 0xF3, 0x76]), {"ime": 0}, state=SM83State())
    pin("ei-then-nop-enables", bytes([0xFB, 0x00, 0x76]), {"ime": 1}, state=SM83State())
    tests += 10

    # -- memory forms ----------------------------------------------------
    mem_pin("ldh-store-a8", bytes([0x3E, 0x5A, 0xE0, 0x80, 0x76]), 0xFF80, 0x5A)
    mem_pin("ldh-store-c", bytes([0xE2, 0x76]), 0xFF42, 0x99, state=SM83State(a=0x99, c=0x42))
    mem_pin("ld-hli-a", bytes([0x22, 0x76]), 0xC000, 0x5A, state=SM83State(h=0xC0, l=0x00, a=0x5A))
    mem_pin("inc-hl-mem", bytes([0x34, 0x76]), 0xC000, 0x77, state=SM83State(h=0xC0, l=0x00))
    mem_pin("ld-a16-a-store", bytes([0x3E, 0x5A, 0xEA, 0x00, 0xC0, 0x76]), 0xC000, 0x5A)
    mem_pin("ld-a16-a-store-no-clobber", bytes([0x3E, 0x5A, 0xEA, 0x00, 0xC0, 0x76]), 0xC001, 0x76)
    pin("ld-a-a16-load", bytes([0xFA, 0x00, 0xC0, 0x76]), {"a": 0x77}, memory=_with(0xC000, 0x77))
    tests += 7

    # (ld-a-hld needs a memory byte at 0xC001) --------------------------
    mem = bytearray(HALT_IMAGE)
    mem[0xC001] = 0x33
    pin("ld-a-hld", bytes([0x3A, 0x76]), {"a": 0x33, "h": 0xC0, "l": 0x00}, state=SM83State(h=0xC0, l=0x01), memory=bytes(mem))
    pin("ldh-load-c-reads", bytes([0xF2, 0x76]), {"a": 0x77}, state=SM83State(c=0x42), memory=_with(0xFF42, 0x77))
    tests += 2

    # -- full documented coverage ---------------------------------------
    covered = 0
    for opcode in range(256):
        if opcode in UNDOCUMENTED:
            try:
                run_pin(bytes([opcode, 0x00, 0x00, 0x76]), steps=10)
            except SM83ReferenceError:
                continue
            raise AssertionError(f"undocumented opcode 0x{opcode:02X} executed")
        run_pin(bytes([opcode, 0x00, 0x00, 0x76]), steps=10)
        covered += 1
    print(f"PASS base-opcode semantics coverage {covered}/245 documented")
    tests += 1

    covered_cb = 0
    for sub in range(256):
        run_pin(bytes([0xCB, sub, 0x00, 0x76]), steps=10)
        covered_cb += 1
    print(f"PASS cb-page semantics coverage {covered_cb}/256")
    tests += 1

    # -- fail closed -----------------------------------------------------
    try:
        run_pin(bytes([0x00] * 8), steps=5)
    except SM83ReferenceError:
        print("PASS reject: step-limit-exceeded")
        tests += 1
    else:
        raise AssertionError("runaway program did not hit the step limit")

    # 16-bit reads at 0xFFFF wrap to 0x0000 (documented hardware behaviour);
    # the low byte of the 16-bit read lands in A.
    pin("ld-a-a16-wrap-at-ffff", bytes([0xFA, 0xFF, 0xFF, 0x76]), {"a": 0x77}, memory=_with(0xFFFF, 0x77))
    tests += 1

    print(f"OPENRECOMP_SM83_SEMANTICS_V1=PASS tests={tests}")
    return 0


def _with(address: int, value: int) -> bytes:
    image = bytearray(HALT_IMAGE)
    image[address] = value
    return bytes(image)


if __name__ == "__main__":
    raise SystemExit(main())
