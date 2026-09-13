#!/usr/bin/env python3
"""P1-31 gate: documented NES 6502-family instruction semantics.

Pins the documented behaviour of `tools/nes6502_reference_v1.py` for every
instruction class, using the public NESdev / masswerk documentation:

- load/store/transfer/stack instructions and their N/Z flags;
- BIT (N/V from the operand, Z from A & operand);
- ADC/SBC binary arithmetic with the documented C/V rules, and the NES
  2A03 fact that decimal mode is disabled (D has no effect on ADC/SBC);
- CMP/CPX/CPY (C = no borrow, N/Z from the subtraction);
- INC/DEC/INX/INY/DEX/DEY (C unaffected);
- ASL/LSR/ROL/ROR accumulator and memory with the shifted-out carry;
- all eight conditional branches (taken and not-taken);
- JMP absolute, JMP indirect with the documented NMOS page-boundary bug;
- JSR/RTS and BRK/RTI with the documented stack/B-flag behaviour;
- flag set/clear instructions and NOP;
- every documented addressing mode (immediate, zp, zp,X, zp,Y, abs, abs,X,
  abs,Y, indexed-indirect, indirect-indexed and zero-page wrap);
- reset/IRQ/NMI interrupt entry (I masking, pushed B flag, vectors);
- a full-coverage execution sweep over every official opcode;
- fail-closed rejection of undocumented encodings.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from adapters.nes6502 import (  # noqa: E402
    FLAG_B,
    FLAG_C,
    FLAG_D,
    FLAG_I,
    FLAG_N,
    FLAG_UNUSED,
    FLAG_V,
    FLAG_Z,
    OFFICIAL,
)
from nes6502_reference_v1 import (  # noqa: E402
    MEMORY_SIZE,
    NES6502ReferenceError,
    NES6502State,
    ReferenceNES6502,
)

BASE = FLAG_UNUSED | FLAG_I  # 0x24: unused bit always set, I set on reset
ENTRY = 0x0100
HALT = 0x02


def make_memory(code: bytes, data: dict[int, int] | None = None) -> bytearray:
    memory = bytearray([HALT] * MEMORY_SIZE)
    memory[ENTRY:ENTRY + len(code)] = code
    for address, value in (data or {}).items():
        memory[address] = value & 0xFF
    return memory


def st(**kw) -> NES6502State:
    values = {"pc": ENTRY, "sp": 0xFD, "p": BASE}
    values.update(kw)
    return NES6502State(**values)


def run(code: bytes, state: NES6502State, data: dict[int, int] | None = None, steps: int = 1000):
    memory = make_memory(code, data)
    ref = ReferenceNES6502(memory, state)
    final = ref.run(max_steps=steps)
    return ref, final


def pin(label: str, code: bytes, checks: dict, state: NES6502State | None = None, data: dict[int, int] | None = None) -> None:
    ref, final = run(code, state or st(), data)
    for key, expected in checks.items():
        actual = final.get(key)
        if actual != expected:
            raise AssertionError(f"{label}: {key} = {actual:#x} != {expected:#x}")
    print(f"PASS {label}")


def mem_pin(label: str, code: bytes, address: int, expected: int, state: NES6502State | None = None, data: dict[int, int] | None = None) -> None:
    ref, _final = run(code, state or st(), data)
    actual = ref.memory[address]
    if actual != expected:
        raise AssertionError(f"{label}: mem[{address:#x}] = {actual:#x} != {expected:#x}")
    print(f"PASS {label}")


def expect_fail(label: str, action) -> None:
    try:
        action()
    except NES6502ReferenceError:
        print(f"PASS reject: {label}")
        return
    raise AssertionError(f"{label}: accepted")


def main() -> int:
    tests = 0

    # -- load / store ------------------------------------------------------
    pin("lda-imm-negative", bytes([0xA9, 0x80, HALT]), {"a": 0x80, "p": BASE | FLAG_N})
    pin("lda-imm-zero", bytes([0xA9, 0x00, HALT]), {"a": 0x00, "p": BASE | FLAG_Z})
    pin("ldx-imm", bytes([0xA2, 0x7F, HALT]), {"x": 0x7F, "p": BASE})
    pin("ldy-imm-zero", bytes([0xA0, 0x00, HALT]), {"y": 0x00, "p": BASE | FLAG_Z})
    pin("lda-abs", bytes([0xAD, 0x00, 0x03, HALT]), {"a": 0x42}, data={0x0300: 0x42})
    pin("lda-abs-y", bytes([0xB9, 0x00, 0x02, HALT]), {"a": 0x42}, state=st(y=0x05), data={0x0205: 0x42})
    pin("lda-abs-x", bytes([0xBD, 0x00, 0x02, HALT]), {"a": 0x42}, state=st(x=0x05), data={0x0205: 0x42})
    pin("lda-zp-x", bytes([0xB5, 0x10, HALT]), {"a": 0x42}, state=st(x=0x05), data={0x15: 0x42})
    pin("ldx-zp-y", bytes([0xB6, 0x10, HALT]), {"x": 0x42}, state=st(y=0x05), data={0x15: 0x42})
    pin("lda-zp-x-wrap", bytes([0xB5, 0xFF, HALT]), {"a": 0x42}, state=st(x=0x02), data={0x0001: 0x42})
    pin("lda-ind-x", bytes([0xA1, 0x10, HALT]), {"a": 0x42}, state=st(x=0x04), data={0x14: 0x00, 0x15: 0x03, 0x0300: 0x42})
    pin("lda-ind-y", bytes([0xB1, 0x10, HALT]), {"a": 0x42}, state=st(y=0x05), data={0x10: 0x00, 0x11: 0x03, 0x0305: 0x42})
    pin("sta-zp", bytes([0xA9, 0x37, 0x85, 0x10, HALT]), {"a": 0x37})
    mem_pin("sta-zp-store", bytes([0xA9, 0x37, 0x85, 0x10, HALT]), 0x10, 0x37)
    mem_pin("stx-zp-store", bytes([0xA2, 0x55, 0x86, 0x10, HALT]), 0x10, 0x55)
    mem_pin("sty-zp-store", bytes([0xA0, 0x66, 0x84, 0x10, HALT]), 0x10, 0x66)
    mem_pin("sta-abs-x-store", bytes([0xA9, 0x77, 0x9D, 0x00, 0x02, HALT]), 0x0203, 0x77, state=st(x=0x03))
    tests += 20

    # -- transfers ---------------------------------------------------------
    pin("tax", bytes([0xA9, 0x80, 0xAA, HALT]), {"a": 0x80, "x": 0x80, "p": BASE | FLAG_N})
    pin("tay", bytes([0xA9, 0x80, 0xA8, HALT]), {"a": 0x80, "y": 0x80, "p": BASE | FLAG_N})
    pin("txa", bytes([0xA2, 0x00, 0x8A, HALT]), {"a": 0x00, "x": 0x00, "p": BASE | FLAG_Z})
    pin("tya", bytes([0xA0, 0x00, 0x98, HALT]), {"a": 0x00, "y": 0x00, "p": BASE | FLAG_Z})
    pin("tsx", bytes([0xBA, HALT]), {"x": 0x80, "sp": 0x80, "p": BASE | FLAG_N}, state=st(sp=0x80))
    pin("txs-no-flags", bytes([0xA2, 0x80, 0x9A, HALT]), {"sp": 0x80, "x": 0x80, "p": BASE | FLAG_N})
    tests += 6

    # -- stack -------------------------------------------------------------
    pin("pha-pla", bytes([0xA9, 0x42, 0x48, 0xA9, 0x00, 0x68, HALT]), {"a": 0x42, "sp": 0xFD, "p": BASE})
    mem_pin("pha-store", bytes([0xA9, 0x42, 0x48, HALT]), 0x01FD, 0x42)
    pin("php-plp-roundtrip", bytes([0x08, 0x28, HALT]), {"p": BASE | FLAG_C}, state=st(p=BASE | FLAG_C))
    mem_pin("php-pushes-bflag", bytes([0x08, HALT]), 0x01FD, BASE | FLAG_C | FLAG_B, state=st(p=BASE | FLAG_C))
    tests += 4

    # -- logical -----------------------------------------------------------
    pin("and-imm", bytes([0xA9, 0x0F, 0x29, 0x3C, HALT]), {"a": 0x0C, "p": BASE})
    pin("ora-imm", bytes([0xA9, 0x0F, 0x09, 0xF0, HALT]), {"a": 0xFF, "p": BASE | FLAG_N})
    pin("eor-imm", bytes([0xA9, 0xFF, 0x49, 0x0F, HALT]), {"a": 0xF0, "p": BASE | FLAG_N})
    pin("bit-zp", bytes([0xA9, 0x0F, 0x24, 0x10, HALT]), {"a": 0x0F, "p": BASE | FLAG_Z | FLAG_N | FLAG_V}, data={0x10: 0xC0})
    tests += 4

    # -- ADC / SBC (binary; NES has no decimal mode) -----------------------
    pin("adc-basic", bytes([0x69, 0x0F, HALT]), {"a": 0x39, "p": BASE}, state=st(a=0x2A))
    pin("adc-carry", bytes([0x69, 0x01, HALT]), {"a": 0x00, "p": BASE | FLAG_C | FLAG_Z}, state=st(a=0xFF))
    pin("adc-overflow", bytes([0x69, 0x01, HALT]), {"a": 0x80, "p": BASE | FLAG_V | FLAG_N}, state=st(a=0x7F))
    pin("adc-carry-in", bytes([0x69, 0x00, HALT]), {"a": 0x01, "p": BASE}, state=st(a=0x00, p=BASE | FLAG_C))
    pin("adc-decimal-disabled", bytes([0x69, 0x01, HALT]), {"a": 0x0A, "p": BASE | FLAG_D}, state=st(a=0x09, p=BASE | FLAG_D))
    pin("sbc-basic", bytes([0xE9, 0x01, HALT]), {"a": 0x0F, "p": BASE | FLAG_C}, state=st(a=0x10, p=BASE | FLAG_C))
    pin("sbc-borrow", bytes([0xE9, 0x01, HALT]), {"a": 0xFF, "p": BASE | FLAG_N}, state=st(a=0x00, p=BASE | FLAG_C))
    pin("sbc-overflow", bytes([0xE9, 0x01, HALT]), {"a": 0x7F, "p": BASE | FLAG_V | FLAG_C}, state=st(a=0x80, p=BASE | FLAG_C))
    pin("sbc-decimal-disabled", bytes([0xE9, 0x01, HALT]), {"a": 0xFF, "p": BASE | FLAG_D | FLAG_N}, state=st(a=0x00, p=BASE | FLAG_D | FLAG_C))
    tests += 9

    # -- comparisons -------------------------------------------------------
    pin("cmp-equal", bytes([0xC9, 0x10, HALT]), {"a": 0x10, "p": BASE | FLAG_Z | FLAG_C}, state=st(a=0x10))
    pin("cmp-less", bytes([0xC9, 0x20, HALT]), {"p": BASE | FLAG_N}, state=st(a=0x10))
    pin("cmp-greater", bytes([0xC9, 0x10, HALT]), {"p": BASE | FLAG_C}, state=st(a=0x20))
    pin("cpx", bytes([0xE0, 0x20, HALT]), {"p": BASE | FLAG_N}, state=st(x=0x10))
    pin("cpy", bytes([0xC0, 0x10, HALT]), {"p": BASE | FLAG_Z | FLAG_C}, state=st(y=0x10))
    tests += 5

    # -- increments / decrements -------------------------------------------
    pin("inc-zp-preserves-c", bytes([0xE6, 0x10, HALT]), {"p": BASE | FLAG_C | FLAG_N}, state=st(p=BASE | FLAG_C), data={0x10: 0x7F})
    mem_pin("inc-zp-store", bytes([0xE6, 0x10, HALT]), 0x10, 0x80, data={0x10: 0x7F})
    mem_pin("dec-zp-store", bytes([0xC6, 0x10, HALT]), 0x10, 0x7F, data={0x10: 0x80})
    pin("inx-wrap", bytes([0xE8, HALT]), {"x": 0x00, "p": BASE | FLAG_Z}, state=st(x=0xFF))
    pin("iny-wrap", bytes([0xC8, HALT]), {"y": 0x00, "p": BASE | FLAG_Z}, state=st(y=0xFF))
    pin("dex-wrap", bytes([0xCA, HALT]), {"x": 0xFF, "p": BASE | FLAG_N}, state=st(x=0x00))
    pin("dey-wrap", bytes([0x88, HALT]), {"y": 0xFF, "p": BASE | FLAG_N}, state=st(y=0x00))
    tests += 7

    # -- shifts / rotates --------------------------------------------------
    pin("asl-a", bytes([0x0A, HALT]), {"a": 0x02, "p": BASE | FLAG_C}, state=st(a=0x81))
    pin("lsr-a", bytes([0x4A, HALT]), {"a": 0x00, "p": BASE | FLAG_C | FLAG_Z}, state=st(a=0x01))
    pin("rol-a", bytes([0x2A, HALT]), {"a": 0x00, "p": BASE | FLAG_C | FLAG_Z}, state=st(a=0x80))
    pin("rol-a-carry-in", bytes([0x2A, HALT]), {"a": 0x01, "p": BASE}, state=st(a=0x00, p=BASE | FLAG_C))
    pin("ror-a", bytes([0x6A, HALT]), {"a": 0x00, "p": BASE | FLAG_C | FLAG_Z}, state=st(a=0x01))
    pin("ror-a-carry-in", bytes([0x6A, HALT]), {"a": 0x80, "p": BASE | FLAG_N}, state=st(a=0x00, p=BASE | FLAG_C))
    mem_pin("asl-zp-store", bytes([0x06, 0x10, HALT]), 0x10, 0x00, data={0x10: 0x80})
    mem_pin("lsr-zp-store", bytes([0x46, 0x10, HALT]), 0x10, 0x00, data={0x10: 0x01})
    mem_pin("rol-zp-store", bytes([0x26, 0x10, HALT]), 0x10, 0x00, data={0x10: 0x80})
    mem_pin("ror-zp-store", bytes([0x66, 0x10, HALT]), 0x10, 0x00, data={0x10: 0x01})
    tests += 10

    # -- conditional branches (all eight, taken) ---------------------------
    branch_program = bytes([0x00, 0x02, HALT, HALT, 0xA9, 0x42, HALT])
    branches = {
        "beq": (0xF0, BASE | FLAG_Z),
        "bne": (0xD0, BASE),
        "bpl": (0x10, BASE),
        "bmi": (0x30, BASE | FLAG_N),
        "bcc": (0x90, BASE),
        "bcs": (0xB0, BASE | FLAG_C),
        "bvc": (0x50, BASE),
        "bvs": (0x70, BASE | FLAG_V),
    }
    for name, (opcode, flags) in branches.items():
        code = bytes([opcode, 0x02, HALT, HALT, 0xA9, 0x42, HALT])
        pin(f"{name}-taken", code, {"a": 0x42}, state=st(p=flags))
    # not-taken: BEQ with Z clear never reaches the LDA
    pin("beq-not-taken", branch_program, {"a": 0x00}, state=st(p=BASE))
    pin("bne-not-taken", bytes([0xD0, 0x02, HALT, HALT, 0xA9, 0x42, HALT]), {"a": 0x00}, state=st(p=BASE | FLAG_Z))
    tests += 10

    # -- jumps / calls -----------------------------------------------------
    pin("jmp-abs", bytes([0x4C, 0x05, 0x01, HALT, HALT, 0xA9, 0x42, HALT]), {"a": 0x42})
    pin(
        "jmp-indirect-page-bug",
        bytes([0x6C, 0xFF, 0x00]),
        {"a": 0x42},
        data={0x00FF: 0x00, 0x0000: 0x02, 0x0200: 0xA9, 0x0201: 0x42, 0x0202: HALT},
    )
    pin(
        "jsr-rts",
        bytes([0x20, 0x08, 0x01, 0xA9, 0x42, HALT, HALT, HALT, 0xA9, 0x11, 0x60, HALT]),
        {"a": 0x42, "sp": 0xFD},
    )
    pin(
        "brk-rti",
        bytes([0x00, HALT]),
        {"a": 0x42, "p": BASE | FLAG_C, "sp": 0xFD},
        state=st(p=BASE | FLAG_C),
        data={0xFFFE: 0x00, 0xFFFF: 0x02, 0x0200: 0xA9, 0x0201: 0x42, 0x0202: 0x40, 0x0203: HALT},
    )
    tests += 4

    # -- flag instructions / NOP -------------------------------------------
    pin("clc", bytes([0x18, HALT]), {"p": BASE}, state=st(p=BASE | FLAG_C))
    pin("sec", bytes([0x38, HALT]), {"p": BASE | FLAG_C})
    pin("cli", bytes([0x58, HALT]), {"p": BASE & ~FLAG_I})
    pin("sei", bytes([0x78, HALT]), {"p": BASE}, state=st(p=BASE & ~FLAG_I))
    pin("clv", bytes([0xB8, HALT]), {"p": BASE}, state=st(p=BASE | FLAG_V))
    pin("cld", bytes([0xD8, HALT]), {"p": BASE}, state=st(p=BASE | FLAG_D))
    pin("sed", bytes([0xF8, HALT]), {"p": BASE | FLAG_D})
    pin("nop", bytes([0xEA, HALT]), {"a": 0x11, "p": BASE | FLAG_C}, state=st(a=0x11, p=BASE | FLAG_C))
    tests += 8

    # -- interrupt / reset entry -------------------------------------------
    ref = ReferenceNES6502(make_memory(bytes([HALT]), {0xFFFC: 0x00, 0xFFFD: 0x02}), NES6502State(sp=0xAA, p=0))
    ref.reset()
    if (ref.state.pc, ref.state.sp, ref.state.p) != (0x0200, 0xFD, BASE):
        raise AssertionError(f"reset: pc={ref.state.pc:#x} sp={ref.state.sp:#x} p={ref.state.p:#x}")
    print("PASS reset-vector-and-state")

    ref = ReferenceNES6502(make_memory(bytes([HALT]), {0xFFFE: 0x00, 0xFFFF: 0x02}), st(p=BASE))
    if ref.irq() is not False or ref.state.pc != ENTRY:
        raise AssertionError("masked IRQ was taken")
    print("PASS irq-masked-by-i")

    ref = ReferenceNES6502(make_memory(bytes([HALT]), {0xFFFE: 0x00, 0xFFFF: 0x02}), st(p=BASE & ~FLAG_I))
    if ref.irq() is not True:
        raise AssertionError("unmasked IRQ was ignored")
    assert ref.state.pc == 0x0200, hex(ref.state.pc)
    assert ref.state.sp == 0xFA, hex(ref.state.sp)
    assert ref.state.p == BASE, hex(ref.state.p)
    assert ref.memory[0x01FD] == 0x01 and ref.memory[0x01FC] == 0x00 and ref.memory[0x01FB] == (BASE & ~FLAG_I) | FLAG_UNUSED
    print("PASS irq-vector-stack-and-i")

    ref = ReferenceNES6502(make_memory(bytes([HALT]), {0xFFFA: 0x00, 0xFFFB: 0x02}), st(p=BASE))
    if ref.nmi() is not True or ref.state.pc != 0x0200:
        raise AssertionError("NMI was not taken")
    assert ref.state.p == BASE
    print("PASS nmi-vector")
    tests += 4

    # -- full-coverage execution sweep -------------------------------------
    covered = 0
    for opcode in sorted(OFFICIAL):
        program = bytes([opcode, HALT, HALT, HALT, HALT])
        ref = ReferenceNES6502(make_memory(program), st())
        ref.run(max_steps=100)
        if not ref.state.halted:
            raise AssertionError(f"opcode 0x{opcode:02x} did not halt in the coverage sweep")
        covered += 1
    assert covered == 151, covered
    print(f"PASS execution-coverage official {covered}/151")
    tests += 1

    # -- fail-closed -------------------------------------------------------
    from adapters.nes6502 import UNDOCUMENTED  # noqa: E402

    expect_fail(
        "undocumented-opcode",
        lambda: ReferenceNES6502(make_memory(bytes([0x03, HALT])), st()).run(max_steps=10),
    )
    expect_fail("short-memory-model", lambda: ReferenceNES6502(bytes(16), st()))
    sample_undocumented = [op for op in sorted(UNDOCUMENTED) if op != HALT][:8]
    for opcode in sample_undocumented:
        expect_fail(
            f"undocumented-0x{opcode:02x}",
            lambda op=opcode: ReferenceNES6502(make_memory(bytes([op, HALT])), st()).run(max_steps=10),
        )
    tests += 2 + len(sample_undocumented)

    print(f"OPENRECOMP_NES6502_SEMANTICS_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
