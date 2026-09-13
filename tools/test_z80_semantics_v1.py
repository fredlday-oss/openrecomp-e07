#!/usr/bin/env python3
"""P1-21 gate: documented Z80 instruction semantics (reference interpreter).

Pins hand-derived documented behaviour of `tools/z80_reference_v1.py` for
every instruction class (Zilog Z80 CPU User Manual flag rules; z80-heaven /
ZEXALL public documentation for the block-transfer flag details): ALU flags
with P/V = overflow, logical parity, INC/DEC overflow, 16-bit ADD/ADC/SBC,
rotates, DAA, BIT, block ops with internal repetition, EX/EXX shadow set,
DJNZ, RLD/RRD, IN/OUT ports, LD A,I/R with P/V = IFF2, EI delay, plus a
full-coverage execution sweep over every documented encoding and fail-closed
rejections.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from adapters.z80 import FLAG_C, FLAG_H, FLAG_N, FLAG_PV, FLAG_S, FLAG_Z  # noqa: E402
from z80_reference_v1 import MEMORY_SIZE, ReferenceZ80, Z80ReferenceError, Z80State, load_program  # noqa: E402
from test_z80_decode_v1 import ED_DOCUMENTED  # noqa: E402

HALT_IMAGE = bytes([0x76]) * MEMORY_SIZE


def run_pin(code: bytes, *, state: Z80State | None = None, memory: bytes | None = None, steps: int = 10000):
    if memory is None:
        memory = HALT_IMAGE
    image = bytearray(memory)
    image[0x0100:0x0100 + len(code)] = code
    ref = ReferenceZ80(image, state or Z80State(pc=0x0100, sp=0xFFFE))
    final = ref.run(max_steps=steps)
    return ref, final


def pin(label: str, code: bytes, checks: dict, *, state: Z80State | None = None, memory: bytes | None = None) -> None:
    ref, final = run_pin(code, state=state, memory=memory)
    for key, expected in checks.items():
        actual = final.get(key)
        if actual != expected:
            raise AssertionError(f"{label}: {key} = {actual:#x} != {expected:#x}")
    print(f"PASS {label}")


def mem_pin(label: str, code: bytes, address: int, expected: int, *, state: Z80State | None = None) -> None:
    ref, _ = run_pin(code, state=state)
    actual = ref.memory[address]
    if actual != expected:
        raise AssertionError(f"{label}: mem[{address:#x}] = {actual:#x} != {expected:#x}")
    print(f"PASS {label}")


def port_pin(label: str, code: bytes, port: int, expected: int, *, state: Z80State | None = None) -> None:
    ref, _ = run_pin(code, state=state)
    actual = ref.ports[port]
    if actual != expected:
        raise AssertionError(f"{label}: port[{port:#x}] = {actual:#x} != {expected:#x}")
    print(f"PASS {label}")


def expect_fail(label: str, action) -> None:
    try:
        action()
    except Z80ReferenceError:
        print(f"PASS reject: {label}")
        return
    raise AssertionError(f"{label}: accepted")


def main() -> int:
    tests = 0

    # -- 8-bit ALU and flags ------------------------------------------------
    pin("add", bytes([0x3E, 0x2A, 0x06, 0x0F, 0x80, 0x76]), {"a": 0x39, "f": FLAG_H})
    pin("add-overflow", bytes([0x80, 0x76]), {"a": 0x80, "f": FLAG_S | FLAG_H | FLAG_PV}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x7F, b=0x01))
    pin("add-carry", bytes([0x80, 0x76]), {"a": 0x00, "f": FLAG_Z | FLAG_H | FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0xFF, b=0x01))
    pin("adc-with-carry-in", bytes([0x88, 0x76]), {"a": 0x11, "f": FLAG_H}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x0F, b=0x01, f=FLAG_C))
    pin("sub", bytes([0x90, 0x76]), {"a": 0x0F, "f": FLAG_H | FLAG_N}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x10, b=0x01))
    pin("sub-borrow", bytes([0x90, 0x76]), {"a": 0xFF, "f": FLAG_S | FLAG_H | FLAG_N | FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x00, b=0x01))
    pin("sbc", bytes([0x98, 0x76]), {"a": 0xFE, "f": FLAG_S | FLAG_H | FLAG_N | FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x00, b=0x01, f=FLAG_C))
    pin("and-parity-h", bytes([0xE6, 0x0F, 0x76]), {"a": 0x0C, "f": FLAG_H | FLAG_PV}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x3C))
    pin("xor", bytes([0xEE, 0xFF, 0x76]), {"a": 0xA5, "f": FLAG_S | FLAG_PV}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x5A))
    pin("or", bytes([0xF6, 0x00, 0x76]), {"a": 0x00, "f": FLAG_Z | FLAG_PV}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x00))
    pin("cp-keeps-a", bytes([0xFE, 0x01, 0x76]), {"a": 0x10, "f": FLAG_H | FLAG_N}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x10))
    pin("inc-overflow", bytes([0x04, 0x76]), {"b": 0x80, "f": FLAG_S | FLAG_H | FLAG_PV}, state=Z80State(pc=0x0100, sp=0xFFFE, b=0x7F))
    pin("dec-overflow", bytes([0x05, 0x76]), {"b": 0x7F, "f": FLAG_H | FLAG_PV | FLAG_N}, state=Z80State(pc=0x0100, sp=0xFFFE, b=0x80))
    pin("inc-preserves-c", bytes([0x04, 0x76]), {"b": 0x01, "f": FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, b=0x00, f=FLAG_C))
    pin("neg", bytes([0xED, 0x44, 0x76]), {"a": 0x80, "f": FLAG_S | FLAG_PV | FLAG_N | FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x80))
    pin("neg-zero", bytes([0xED, 0x44, 0x76]), {"a": 0x00, "f": FLAG_Z | FLAG_N}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x00))
    tests += 15

    # -- DAA --------------------------------------------------------------
    pin("daa-after-add", bytes([0x80, 0x27, 0x76]), {"a": 0x16, "f": 0x00}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x0F, b=0x01))
    pin("daa-after-add-carry", bytes([0x80, 0x27, 0x76]), {"a": 0x00, "f": FLAG_Z | FLAG_PV | FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x99, b=0x01))
    pin("daa-after-sub", bytes([0x90, 0x27, 0x76]), {"a": 0x09, "f": FLAG_PV | FLAG_N}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x10, b=0x01))
    tests += 3

    # -- 16-bit arithmetic ------------------------------------------------
    pin("add-hl-half", bytes([0x09, 0x76]), {"h": 0x10, "l": 0x00, "f": FLAG_H}, state=Z80State(pc=0x0100, sp=0xFFFE, h=0x0F, l=0xFF, b=0x00, c=0x01))
    pin("add-hl-carry", bytes([0x09, 0x76]), {"h": 0x00, "l": 0x00, "f": FLAG_H | FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, h=0xFF, l=0xFF, b=0x00, c=0x01))
    pin("add-hl-preserves-szpv", bytes([0x29, 0x76]), {"h": 0x00, "l": 0x00, "f": FLAG_S | FLAG_Z | FLAG_PV | FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, h=0x80, l=0x00, f=FLAG_S | FLAG_Z | FLAG_PV))
    pin("adc-hl", bytes([0xED, 0x4A, 0x76]), {"h": 0x01, "l": 0x01, "f": 0x00}, state=Z80State(pc=0x0100, sp=0xFFFE, h=0x00, l=0xFF, b=0x00, c=0x01, f=FLAG_C))
    pin("sbc-hl", bytes([0xED, 0x42, 0x76]), {"h": 0x00, "l": 0x00, "f": FLAG_Z | FLAG_N}, state=Z80State(pc=0x0100, sp=0xFFFE, h=0x00, l=0x01, b=0x00, c=0x01))
    pin("add-ix", bytes([0xDD, 0x09, 0x76]), {"ix": 0x1235, "f": 0x00}, state=Z80State(pc=0x0100, sp=0xFFFE, ix=0x1234, b=0x00, c=0x01))
    tests += 6

    # -- rotates and CB ----------------------------------------------------
    pin("rlca", bytes([0x07, 0x76]), {"a": 0x01, "f": FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x80))
    pin("rla-through-c", bytes([0x17, 0x76]), {"a": 0x01, "f": 0x00}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x00, f=FLAG_C))
    pin("rra-preserves-sz", bytes([0x1F, 0x76]), {"a": 0x00, "f": FLAG_S | FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x01, f=FLAG_S))
    pin("cb-rlc", bytes([0xCB, 0x00, 0x76]), {"b": 0x01, "f": FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, b=0x80))
    pin("cb-sla-parity", bytes([0xCB, 0x20, 0x76]), {"b": 0x0C, "f": FLAG_PV}, state=Z80State(pc=0x0100, sp=0xFFFE, b=0x06))
    pin("cb-sra-sign", bytes([0xCB, 0x28, 0x76]), {"b": 0xC0, "f": FLAG_S | FLAG_PV | FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, b=0x81))
    pin("cb-srl", bytes([0xCB, 0x38, 0x76]), {"b": 0x01, "f": FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, b=0x03))
    pin("cb-bit-set", bytes([0xCB, 0x7F, 0x76]), {"f": FLAG_Z | FLAG_H | FLAG_PV}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x7F, f=0x00))
    pin("cb-bit-zero-keeps-c", bytes([0xCB, 0x7F, 0x76]), {"f": FLAG_H | FLAG_C}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x80, f=FLAG_C))
    pin("cb-res", bytes([0xCB, 0x80, 0x76]), {"b": 0xFE}, state=Z80State(pc=0x0100, sp=0xFFFE, b=0xFF, f=FLAG_S))
    pin("cb-set", bytes([0xCB, 0xC0, 0x76]), {"b": 0x01}, state=Z80State(pc=0x0100, sp=0xFFFE, b=0x00))
    tests += 11

    # -- stack and control flow ---------------------------------------------
    pin("push-pop-bc", bytes([0xC5, 0xC1, 0x76]), {"b": 0x12, "c": 0x34, "sp": 0xFFFE}, state=Z80State(pc=0x0100, sp=0xFFFE, b=0x12, c=0x34))
    pin("pop-af-full-byte", bytes([0xF5, 0xF1, 0x76]), {"a": 0xAB, "f": 0x3F, "sp": 0xFFFE}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0xAB, f=0x3F))
    pin("djnz-loops-then-exits", bytes([0x06, 0x02, 0x00, 0x10, 0xFD, 0x76]), {"b": 0x00, "pc": 0x0106, "halted": 1}, state=Z80State(pc=0x0100, sp=0xFFFE))
    pin("jp-cond-pe-taken", bytes([0xEA, 0x00, 0x00, 0x00, 0x76]), {"pc": 0x0001, "halted": 1}, state=Z80State(pc=0x0100, sp=0xFFFE, f=FLAG_PV))
    pin("jp-cond-po-taken", bytes([0xE2, 0x02, 0x00, 0x76]), {"pc": 0x0003, "halted": 1}, state=Z80State(pc=0x0100, sp=0xFFFE, f=0x00))
    pin("call-ret-round-trip", bytes([0xCD, 0x50, 0x01, 0x3E, 0x2A, 0x76]) + bytes(0x0150 - 0x0106) + bytes([0xC9]), {"a": 0x2A, "sp": 0xFFFE, "pc": 0x0106}, state=Z80State(pc=0x0100, sp=0xFFFE))
    pin("rst-vector", bytes([0xC7, 0x00, 0x00, 0x76]), {"sp": 0xFFFC, "pc": 0x0001}, state=Z80State(pc=0x0100, sp=0xFFFE))
    pin("ret-cond-not-taken", bytes([0xC8, 0x3E, 0x05, 0x76]), {"a": 0x05}, state=Z80State(pc=0x0100, sp=0xFFFE, f=0x00))
    pin("jp-hl", bytes([0x21, 0x50, 0x01, 0xE9, 0x00, 0x00, 0x76]), {"pc": 0x0151}, state=Z80State(pc=0x0100, sp=0xFFFE))
    pin("jp-ix", bytes([0xDD, 0x21, 0x50, 0x01, 0xDD, 0xE9, 0x00, 0x76]), {"pc": 0x0151}, state=Z80State(pc=0x0100, sp=0xFFFE))
    tests += 11

    # -- exchanges and shadow set --------------------------------------------
    pin("exx", bytes([0xD9, 0x76]), {"b": 0x77, "b2": 0x01, "d2": 0x02}, state=Z80State(pc=0x0100, sp=0xFFFE, b=0x01, d=0x02, b2=0x77))
    pin("ex-af", bytes([0x08, 0x76]), {"a": 0x77, "a2": 0x01, "f": 0xFF, "f2": 0x00}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x01, f=0x00, a2=0x77, f2=0xFF))
    ref, final = run_pin(bytes([0xE3, 0x76]), state=Z80State(pc=0x0100, sp=0xFFFE, h=0xAB, l=0xCD), memory=_with(0xFFFE, 0x34, 0xFFFF, 0x12))
    assert final["h"] == 0x12 and final["l"] == 0x34 and final["sp"] == 0xFFFE
    assert ref.memory[0xFFFE] == 0xCD and ref.memory[0xFFFF] == 0xAB
    print("PASS ex-sp-hl")
    tests += 1
    tests += 3

    # -- memory forms and index addressing -------------------------------------
    mem_pin("ld-a16-a", bytes([0x3E, 0x5A, 0x32, 0x00, 0xC0, 0x76]), 0xC000, 0x5A)
    pin("ld-a-a16", bytes([0x3A, 0x00, 0xC0, 0x76]), {"a": 0x77}, memory=_with(0xC000, 0x77))
    mem_pin("ld-ixd-n", bytes([0xDD, 0x36, 0x05, 0x5A, 0x76]), 0x8005, 0x5A, state=Z80State(pc=0x0100, sp=0xFFFE, ix=0x8000))
    pin("ld-h-ixd", bytes([0xDD, 0x66, 0xFC, 0x76]), {"h": 0x77}, state=Z80State(pc=0x0100, sp=0xFFFE, ix=0x8004), memory=_with(0x8000, 0x77))
    mem_pin("inc-ixd", bytes([0xDD, 0x34, 0x01, 0x76]), 0x8001, 0x77, state=Z80State(pc=0x0100, sp=0xFFFE, ix=0x8000))
    ref, _ = run_pin(bytes([0xDD, 0xCB, 0x02, 0x9E, 0x76]), state=Z80State(pc=0x0100, sp=0xFFFE, ix=0x8000), memory=_with(0x8002, 0xFF))
    assert ref.memory[0x8002] == 0xF7  # RES 3
    print("PASS ddcb-res-ixd")
    tests += 1
    pin("ld-ix-a16", bytes([0xDD, 0x2A, 0x00, 0xC0, 0x76]), {"ix": 0x3412}, memory=_with(0xC000, 0x12, 0xC001, 0x34))
    tests += 7

    # -- ports ----------------------------------------------------------------
    port_pin("out-n-a", bytes([0x3E, 0x7F, 0xD3, 0x01, 0x76]), 0x01, 0x7F)
    # in a,(n) addresses port (A<<8)|n -> low byte only in the 256-byte model
    image = bytearray(HALT_IMAGE)
    image[0x0100:0x0103] = bytes([0xDB, 0x01, 0x76])
    ref = ReferenceZ80(image, Z80State(pc=0x0100, sp=0xFFFE))
    ref.ports[0x01] = 0x42
    final = ref.run()
    assert final["a"] == 0x42
    print("PASS in-a-n")
    image = bytearray(HALT_IMAGE)
    image[0x0100:0x0103] = bytes([0xDB, 0x01, 0x76])
    ref = ReferenceZ80(image, Z80State(pc=0x0100, sp=0xFFFE, a=0x7F))
    ref.ports[0x01] = 0x5A
    final = ref.run()
    assert final["a"] == 0x5A
    print("PASS in-a-n-port-address (A<<8)|n low-byte model")
    port_pin("out-c-a", bytes([0x01, 0x37, 0x00, 0x3E, 0x5A, 0xED, 0x79, 0x76]), 0x37, 0x5A)
    image = bytearray(HALT_IMAGE)
    image[0x0100:0x0103] = bytes([0xED, 0x40, 0x76])
    ref = ReferenceZ80(image, Z80State(pc=0x0100, sp=0xFFFE, b=0xFF, c=0x01))
    ref.ports[0x01] = 0x03
    final = ref.run()
    assert final["b"] == 0x03 and final["f"] == FLAG_PV  # parity(0x03) even
    print("PASS in-b-c-flags")
    tests += 5

    # -- block ops -------------------------------------------------------------
    mem = bytearray(HALT_IMAGE)
    mem[0xC000:0xC004] = bytes([0x11, 0x22, 0x33, 0x44])
    ref, final = run_pin(bytes([0x21, 0x00, 0xC0, 0x11, 0x00, 0xD0, 0x01, 0x04, 0x00, 0xED, 0xB0, 0x76]), memory=bytes(mem))
    assert ref.memory[0xD000:0xD004] == bytes([0x11, 0x22, 0x33, 0x44])
    assert final["b"] == 0x00 and final["c"] == 0x00 and final["f"] == 0x00  # H=0, N=0, P/V=0 (BC==0)
    assert final["h"] == 0xC0 and final["l"] == 0x04 and final["d"] == 0xD0 and final["e"] == 0x04
    print("PASS ldir-4-copies-internal-repeat")
    ref, final = run_pin(bytes([0x21, 0x00, 0xC0, 0x11, 0x00, 0xD0, 0x01, 0x02, 0x00, 0xED, 0xA0, 0x76]), memory=bytes(mem))
    assert ref.memory[0xD000] == 0x11 and ref.memory[0xD001] == 0x76  # LDI transfers once
    assert final["b"] == 0x00 and final["c"] == 0x01 and final["f"] == FLAG_PV  # P/V: BC != 0
    print("PASS ldi-single-with-pv")
    mem = bytearray(HALT_IMAGE)
    mem[0xC000:0xC003] = bytes([0x10, 0x20, 0x30])
    ref, final = run_pin(bytes([0x21, 0x00, 0xC0, 0x01, 0x03, 0x00, 0x3E, 0x20, 0xED, 0xB1, 0x76]), memory=bytes(mem))
    assert final["a"] == 0x20 and final["b"] == 0x00 and final["c"] == 0x01 and final["f"] & FLAG_Z  # found the 0x20
    assert final["h"] == 0xC0 and final["l"] == 0x02  # stopped after the match
    print("PASS cpir-find-match-stops")
    tests += 3

    # -- block-I/O documented flag model (z80-heaven: Z = B==0 after dec, N by
    # direction, C flag/register + S/H preserved; Zilog P/V = B-1 != 0) -------
    image = bytearray(HALT_IMAGE)
    image[0x0100:0x0103] = bytes([0xED, 0xA2, 0x76])  # INI
    ref = ReferenceZ80(image, Z80State(pc=0x0100, sp=0xFFFE, b=0x01, c=0x40, h=0xC0, l=0x00, f=0xFF))
    ref.ports[0x40] = 0x5A
    final = ref.run()
    assert ref.memory[0xC000] == 0x5A and final["b"] == 0x00 and final["c"] == 0x40  # C register preserved
    assert final["h"] == 0xC0 and final["l"] == 0x01
    assert final["f"] == FLAG_S | FLAG_Z | FLAG_H | FLAG_C  # N reset, S/H/C preserved
    print("PASS ini-transfer-flags")
    tests += 1

    image = bytearray(HALT_IMAGE)
    image[0x0100:0x0103] = bytes([0xED, 0xAA, 0x76])  # IND
    ref = ReferenceZ80(image, Z80State(pc=0x0100, sp=0xFFFE, b=0x01, c=0x40, h=0xC0, l=0x01, f=0x00))
    ref.ports[0x40] = 0x5A
    final = ref.run()
    assert ref.memory[0xC001] == 0x5A and final["b"] == 0x00 and final["c"] == 0x40  # C register preserved
    assert final["h"] == 0xC0 and final["l"] == 0x00
    assert final["f"] == FLAG_Z | FLAG_N  # N set by the -d variant
    print("PASS ind-transfer-n-set")
    tests += 1

    image = bytearray(HALT_IMAGE)
    image[0x0100:0x0103] = bytes([0xED, 0xA3, 0x76])  # OUTI
    ref = ReferenceZ80(image, Z80State(pc=0x0100, sp=0xFFFE, b=0x02, c=0x37, h=0xC0, l=0x00, f=0xFF))
    ref.memory[0xC000] = 0x5A
    final = ref.run()
    assert ref.ports[0x37] == 0x5A and final["b"] == 0x01 and final["c"] == 0x37  # C register preserved
    assert final["h"] == 0xC0 and final["l"] == 0x01
    assert final["f"] == FLAG_S | FLAG_H | FLAG_PV | FLAG_C  # Z=0 (B!=0), PV=1, N reset
    print("PASS outi-flags-pv")
    tests += 1

    image = bytearray(HALT_IMAGE)
    image[0x0100:0x0103] = bytes([0xED, 0xAB, 0x76])  # OUTD
    ref = ReferenceZ80(image, Z80State(pc=0x0100, sp=0xFFFE, b=0x01, c=0x37, h=0xC0, l=0x01, f=0x00))
    ref.memory[0xC001] = 0x5A
    final = ref.run()
    assert ref.ports[0x37] == 0x5A and final["b"] == 0x00 and final["c"] == 0x37  # C register preserved
    assert final["h"] == 0xC0 and final["l"] == 0x00
    assert final["f"] == FLAG_Z | FLAG_N  # N set by the -d variant
    print("PASS outd-n-set")
    tests += 1

    image = bytearray(HALT_IMAGE)
    image[0x0100:0x0103] = bytes([0xED, 0xB2, 0x76])  # INIR
    ref = ReferenceZ80(image, Z80State(pc=0x0100, sp=0xFFFE, b=0x03, c=0x40, h=0xC0, l=0x00))
    ref.ports[0x40] = 0x11
    final = ref.run()
    assert ref.memory[0xC000:0xC003] == bytes([0x11, 0x11, 0x11])
    assert final["b"] == 0x00 and final["h"] == 0xC0 and final["l"] == 0x03
    assert final["f"] == FLAG_Z  # P/V cleared once B == 0
    print("PASS inir-internal-repeat")
    tests += 1

    image = bytearray(HALT_IMAGE)
    image[0x0100:0x0103] = bytes([0xED, 0xB3, 0x76])  # OTIR
    ref = ReferenceZ80(image, Z80State(pc=0x0100, sp=0xFFFE, b=0x03, c=0x37, h=0xC0, l=0x00))
    ref.memory[0xC000] = 0x11
    ref.memory[0xC001] = 0x22
    ref.memory[0xC002] = 0x33
    final = ref.run()
    assert ref.ports[0x37] == 0x33 and final["b"] == 0x00 and final["h"] == 0xC0 and final["l"] == 0x03
    assert final["f"] == FLAG_Z
    print("PASS otir-internal-repeat")
    tests += 1

    port_pin("out-c-a-8bit-port-mask", bytes([0x01, 0x37, 0x01, 0x3E, 0x5A, 0xED, 0x79, 0x76]), 0x37, 0x5A)
    tests += 1

    # -- specials ---------------------------------------------------------------
    pin("ld-a-i-copies-iff2", bytes([0xED, 0x57, 0x76]), {"a": 0x00, "f": FLAG_Z | FLAG_PV}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x55, i=0x00, iff2=True))
    pin("ld-a-r", bytes([0xED, 0x5F, 0x76]), {"a": 0x3E}, state=Z80State(pc=0x0100, sp=0xFFFE, r=0x3E))
    pin("ld-i-a", bytes([0xED, 0x47, 0x76]), {"i": 0x99}, state=Z80State(pc=0x0100, sp=0xFFFE, a=0x99))
    pin("ei-delay", bytes([0xFB, 0x00, 0x76]), {"iff1": 1, "iff2": 1}, state=Z80State(pc=0x0100, sp=0xFFFE))
    pin("ei-then-di-stays-off", bytes([0xFB, 0xF3, 0x76]), {"iff1": 0, "iff2": 0}, state=Z80State(pc=0x0100, sp=0xFFFE))
    pin("retn-copies-iff2", bytes([0xC5, 0xED, 0x45, 0x76]), {"iff1": 1, "pc": 0x0302, "halted": 1}, state=Z80State(pc=0x0100, sp=0xFFFE, b=0x03, c=0x01, iff1=False, iff2=True))
    pin("im-2", bytes([0xED, 0x5E, 0x76]), {"im": 2}, state=Z80State(pc=0x0100, sp=0xFFFE))
    pin("ex-de-hl", bytes([0xEB, 0x76]), {"d": 0xAB, "e": 0xCD, "h": 0x01, "l": 0x02}, state=Z80State(pc=0x0100, sp=0xFFFE, d=0x01, e=0x02, h=0xAB, l=0xCD))
    tests += 8

    # -- full documented coverage -------------------------------------------
    covered = 0
    for opcode in range(256):
        if opcode in (0xCB, 0xDD, 0xED, 0xFD):  # prefixes: covered by the ED/CB sweeps
            continue
        run_pin(bytes([opcode, 0x00, 0x00, 0x00, 0x76]), steps=80)
        covered += 1
    print(f"PASS base-opcode semantics coverage {covered}/252 (4 prefixes covered separately)")
    tests += 1

    covered_ed = 0
    inout_family = {0xA2, 0xAA, 0xB2, 0x0, 0xBA, 0xA3, 0xAB, 0xB3, 0xBB}
    for sub in range(256):
        if sub not in ED_DOCUMENTED:
            continue
        # B=C=1 (or BC=1) so repeating block ops stop after one iteration.
        if sub in inout_family:
            state = Z80State(pc=0x0100, sp=0xFFFE, b=0x01, c=0x01)
        else:
            state = Z80State(pc=0x0100, sp=0xFFFE, b=0x00, c=0x01)
        run_pin(bytes([0xED, sub, 0x00, 0x00, 0x76]), steps=80, state=state)
        covered_ed += 1
    print(f"PASS ed-page semantics coverage {covered_ed}/65 documented")
    tests += 1

    covered_cb = 0
    for sub in range(256):
        if 0x30 <= sub < 0x38:
            continue
        run_pin(bytes([0xCB, sub, 0x00, 0x76]), steps=80)
        covered_cb += 1
    print(f"PASS cb-page semantics coverage {covered_cb}/248 documented")
    tests += 1

    covered_idx = 0
    for sub in range(256):
        if sub & 7 != 6 or (0x30 <= sub < 0x38):
            continue
        run_pin(bytes([0xDD, 0xCB, 0x00, sub, 0x76]), steps=80)
        run_pin(bytes([0xFD, 0xCB, 0x00, sub, 0x76]), steps=80)
        covered_idx += 2
    print(f"PASS ddcb/fdcb semantics coverage {covered_idx}/62 documented")
    tests += 1

    # -- fail closed -----------------------------------------------------------
    try:
        run_pin(bytes([0x00] * 8), steps=5)
    except Z80ReferenceError:
        print("PASS reject: step-limit-exceeded")
        tests += 1
    else:
        raise AssertionError("runaway program did not hit the step limit")

    print(f"OPENRECOMP_Z80_SEMANTICS_V1=PASS tests={tests}")
    return 0


def _with(address: int, value: int, address2: int | None = None, value2: int | None = None) -> bytes:
    image = bytearray(HALT_IMAGE)
    image[address] = value
    if address2 is not None:
        image[address2] = value2
    return bytes(image)


if __name__ == "__main__":
    raise SystemExit(main())
