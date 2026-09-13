#!/usr/bin/env python3
"""Independent NES 6502 machine-code reference interpreter (P1-31).

An original, synthetic-input-only reference model of the documented NMOS 6502
instruction semantics used in the NES (2A03/2A07), written as the oracle for
the deterministic headless proof (P1-34) exactly like `tools/sm83_reference_v1.py`
serves the Game Boy path and `tools/z80_reference_v1.py` serves the Master System.

Only documented NMOS 6502 behaviour is implemented:

- 8-bit registers: A (accumulator), X, Y (index registers), SP (stack pointer)
- 16-bit PC (program counter)
- Processor status register P with flags: N (negative, bit 7), V (overflow, bit 6),
  unused (bit 5, always 1), B (break, bit 4, no storage), D (decimal, bit 3),
  I (interrupt disable, bit 2), Z (zero, bit 1), C (carry, bit 0)
- The B flag has no storage; it is set in the pushed P value by BRK (and by PHP)
  and cleared by hardware interrupts (IRQ/NMI) — this is documented NMOS behaviour
- ALU operations set flags according to documented 6502 rules:
  - N = result bit 7
  - Z = result == 0
  - C = carry out (addition/shifts) or no borrow (subtraction/compares)
  - V = signed overflow for ADC/SBC ((M^result) & (N^result) & 0x80)
- Addressing modes: immediate, zero page, zero page indexed, absolute,
  absolute indexed, indirect, indexed indirect, indirect indexed
- Stack: descending from 0x01FF, SP wraps within page 0x0100-0x01FF
- All memory access is bounds checked against the 64 KiB model
- Undocumented opcodes raise `NES6502ReferenceError` (fail closed)
- The NES 2A03/2A07 lacks decimal mode: D exists and can be set/cleared but
  has no effect on ADC/SBC, which are always binary (NESdev "Status flags")
- A decoded 0x02 byte is the synthetic test-harness halt convention only
  (`adapters/nes6502.HALT_OPCODE`); it is not a real instruction
- Cycle counts are intentionally not modelled

The reference is deliberately independent of the IR lowering in this stage
so the P1-31/P1-34 differential proofs have two separately written semantic
implementations.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from adapters.nes6502 import (  # noqa: E402
    FLAG_C,
    FLAG_D,
    FLAG_I,
    FLAG_N,
    FLAG_V,
    FLAG_Z,
    FLAG_B,
    FLAG_UNUSED,
    HALT_OPCODE,
    NES6502Error,
    decode_full,
    is_control_flow,
)

MEMORY_SIZE = 1 << 16


@dataclass
class NES6502State:
    """Documented NMOS 6502 architectural state."""
    a: int = 0
    x: int = 0
    y: int = 0
    sp: int = 0xFD  # Stack pointer starts at 0xFD on NES
    pc: int = 0
    p: int = FLAG_UNUSED | FLAG_I  # Unused bit always set, I set on reset
    halted: bool = False

    def copy(self) -> NES6502State:
        return NES6502State(
            a=self.a, x=self.x, y=self.y, sp=self.sp, pc=self.pc, p=self.p, halted=self.halted
        )


class NES6502ReferenceError(RuntimeError):
    """Deterministic fail-closed reference failure."""


class ReferenceNES6502:
    def __init__(self, memory: bytes | bytearray, state: NES6502State | None = None) -> None:
        if len(memory) != MEMORY_SIZE:
            raise NES6502ReferenceError(f"reference requires a {MEMORY_SIZE}-byte memory model")
        self.memory = bytearray(memory)
        self.state = state if state is not None else NES6502State()
        self.steps = 0

    # -- documented memory helpers --------------------------------------
    def _check(self, address: int) -> int:
        if not (0 <= address < MEMORY_SIZE):
            raise NES6502ReferenceError(f"deterministic memory fault at 0x{address & 0xFFFF:x}")
        return address

    def read_byte(self, address: int) -> int:
        return self.memory[self._check(address & 0xFFFF)]

    def write_byte(self, address: int, value: int) -> None:
        self.memory[self._check(address & 0xFFFF)] = value & 0xFF

    def read_word(self, address: int) -> int:
        """Read 16-bit word (little-endian)."""
        return self.read_byte(address) | (self.read_byte((address + 1) & 0xFFFF) << 8)

    def write_word(self, address: int, value: int) -> None:
        value &= 0xFFFF
        self.write_byte(address, value & 0xFF)
        self.write_byte((address + 1) & 0xFFFF, value >> 8)

    # -- stack operations -----------------------------------------------
    def _push(self, value: int) -> None:
        """Push byte to stack (SP descends from 0x01FF)."""
        self.write_byte(0x0100 | self.state.sp, value & 0xFF)
        self.state.sp = (self.state.sp - 1) & 0xFF

    def _pop(self) -> int:
        """Pop byte from stack."""
        self.state.sp = (self.state.sp + 1) & 0xFF
        return self.read_byte(0x0100 | self.state.sp)

    def _push_word(self, value: int) -> None:
        """Push 16-bit word to stack (high byte first)."""
        self._push((value >> 8) & 0xFF)
        self._push(value & 0xFF)

    def _pop_word(self) -> int:
        """Pop 16-bit word from stack (low byte first)."""
        lo = self._pop()
        hi = self._pop()
        return (hi << 8) | lo

    # -- flag operations ------------------------------------------------
    def _set_nz(self, value: int) -> None:
        """Set N and Z flags based on value."""
        value &= 0xFF
        self.state.p = (self.state.p & ~(FLAG_N | FLAG_Z)) | (
            (FLAG_N if value & 0x80 else 0) | (FLAG_Z if value == 0 else 0)
        )

    def _set_flag(self, flag: int, condition: bool) -> None:
        """Set or clear a flag."""
        if condition:
            self.state.p |= flag
        else:
            self.state.p &= ~flag

    # -- addressing mode resolution -------------------------------------
    def _resolve_address(self, insn: dict) -> int | None:
        """Resolve effective address for memory operands."""
        src = insn.get("src") or insn.get("dst")

        if src == "zp":
            return insn.get("zp", 0)
        elif src == "zp,x":
            return (insn.get("zp,x", 0) + self.state.x) & 0xFF
        elif src == "zp,y":
            return (insn.get("zp,y", 0) + self.state.y) & 0xFF
        elif src == "abs":
            return insn.get("abs", 0)
        elif src == "abs,x":
            return (insn.get("abs,x", 0) + self.state.x) & 0xFFFF
        elif src == "abs,y":
            return (insn.get("abs,y", 0) + self.state.y) & 0xFFFF
        elif src == "(indirect,x)":
            zp_addr = (insn.get("indirect,x", 0) + self.state.x) & 0xFF
            return self.read_byte(zp_addr) | (self.read_byte((zp_addr + 1) & 0xFF) << 8)
        elif src == "(indirect,y)":
            zp_addr = insn.get("indirect,y", 0)
            base = self.read_byte(zp_addr) | (self.read_byte((zp_addr + 1) & 0xFF) << 8)
            return (base + self.state.y) & 0xFFFF
        elif src == "(indirect)":
            # JMP indirect with page boundary bug
            addr = insn.get("indirect", 0)
            lo = self.read_byte(addr)
            # Page boundary bug: if addr is 0xXXFF, high byte comes from 0xXX00
            hi_addr = (addr & 0xFF00) | ((addr + 1) & 0xFF)
            hi = self.read_byte(hi_addr)
            return (hi << 8) | lo

        return None

    def _read_operand(self, insn: dict) -> int:
        """Read operand value based on addressing mode."""
        if "imm8" in insn:
            return insn["imm8"]

        addr = self._resolve_address(insn)
        if addr is not None:
            return self.read_byte(addr)

        return 0

    def _write_operand(self, insn: dict, value: int) -> None:
        """Write value to operand location."""
        addr = self._resolve_address(insn)
        if addr is not None:
            self.write_byte(addr, value & 0xFF)

    # -- ALU operations -------------------------------------------------
    def _adc(self, value: int) -> None:
        """Add with carry (binary only).

        The NES RP2A03/RP2A07 lacks the MOS 6502 decimal mode. The D flag
        exists and can be set/cleared/observed but has no effect on ADC/SBC
        (NESdev "Status flags": "On the NES, decimal mode is disabled and so
        this flag has no effect").
        """
        a = self.state.a
        c = 1 if (self.state.p & FLAG_C) else 0
        result = a + value + c
        self.state.a = result & 0xFF
        self._set_nz(self.state.a)
        self._set_flag(FLAG_C, result > 0xFF)
        self._set_flag(FLAG_V, ((a ^ result) & (value ^ result) & 0x80) != 0)

    def _sbc(self, value: int) -> None:
        """Subtract with carry (binary only; NES 2A03 has no decimal mode)."""
        a = self.state.a
        c = 1 if (self.state.p & FLAG_C) else 0
        result = a - value - (1 - c)
        self.state.a = result & 0xFF
        self._set_nz(self.state.a)
        self._set_flag(FLAG_C, result >= 0)
        self._set_flag(FLAG_V, ((a ^ result) & ((a ^ value) & 0x80)) != 0)

    def _cmp(self, reg_value: int, operand: int) -> None:
        """Compare register with operand."""
        result = reg_value - operand
        self._set_nz(result & 0xFF)
        self._set_flag(FLAG_C, result >= 0)

    # -- documented interrupt / reset entry ------------------------------
    def reset(self) -> None:
        """Documented power/reset entry: SP=0xFD, I set, PC from 0xFFFC.

        (NESdev "CPU power-up state": the stack pointer is initialised to
        0xFD and the interrupt-disable flag is set on reset.)
        """
        self.state.pc = self.read_word(0xFFFC)
        self.state.sp = 0xFD
        self.state.p = (self.state.p | FLAG_UNUSED | FLAG_I) & ~FLAG_B
        self.state.halted = False

    def _enter_interrupt(self, vector: int) -> None:
        """Push PC and P (B cleared, unused set), set I, load the vector.

        Documented hardware behaviour (NESdev "Status flags"): NMI and IRQ
        push the B flag as 0; the interrupt-disable flag is set.
        """
        self._push_word(self.state.pc)
        self._push((self.state.p | FLAG_UNUSED) & ~FLAG_B)
        self.state.p |= FLAG_I
        self.state.pc = self.read_word(vector)

    def irq(self) -> bool:
        """Maskable IRQ (vector 0xFFFE). Ignored while I is set."""
        if self.state.p & FLAG_I:
            return False
        self._enter_interrupt(0xFFFE)
        return True

    def nmi(self) -> bool:
        """Non-maskable NMI (vector 0xFFFA); always taken."""
        self._enter_interrupt(0xFFFA)
        return True

    # -- instruction execution ------------------------------------------
    def _execute(self, insn: dict) -> None:
        """Execute one decoded instruction."""
        op = insn["op"]

        # Load/Store operations
        if op == "lda":
            self.state.a = self._read_operand(insn)
            self._set_nz(self.state.a)
        elif op == "ldx":
            self.state.x = self._read_operand(insn)
            self._set_nz(self.state.x)
        elif op == "ldy":
            self.state.y = self._read_operand(insn)
            self._set_nz(self.state.y)
        elif op == "sta":
            self._write_operand(insn, self.state.a)
        elif op == "stx":
            self._write_operand(insn, self.state.x)
        elif op == "sty":
            self._write_operand(insn, self.state.y)

        # Transfer operations
        elif op == "tax":
            self.state.x = self.state.a
            self._set_nz(self.state.x)
        elif op == "tay":
            self.state.y = self.state.a
            self._set_nz(self.state.y)
        elif op == "txa":
            self.state.a = self.state.x
            self._set_nz(self.state.a)
        elif op == "tya":
            self.state.a = self.state.y
            self._set_nz(self.state.a)
        elif op == "tsx":
            self.state.x = self.state.sp
            self._set_nz(self.state.x)
        elif op == "txs":
            self.state.sp = self.state.x

        # Stack operations
        elif op == "pha":
            self._push(self.state.a)
        elif op == "php":
            # PHP sets B flag in pushed value
            self._push(self.state.p | FLAG_B | FLAG_UNUSED)
        elif op == "pla":
            self.state.a = self._pop()
            self._set_nz(self.state.a)
        elif op == "plp":
            # PLP: unused bit always set, ignore B flag from stack
            self.state.p = (self._pop() | FLAG_UNUSED) & ~FLAG_B

        # Logical operations
        elif op == "and":
            self.state.a &= self._read_operand(insn)
            self._set_nz(self.state.a)
        elif op == "ora":
            self.state.a |= self._read_operand(insn)
            self._set_nz(self.state.a)
        elif op == "eor":
            self.state.a ^= self._read_operand(insn)
            self._set_nz(self.state.a)
        elif op == "bit":
            value = self._read_operand(insn)
            result = self.state.a & value
            self._set_flag(FLAG_Z, result == 0)
            self._set_flag(FLAG_N, (value & 0x80) != 0)
            self._set_flag(FLAG_V, (value & 0x40) != 0)

        # Arithmetic operations
        elif op == "adc":
            self._adc(self._read_operand(insn))
        elif op == "sbc":
            self._sbc(self._read_operand(insn))
        elif op == "cmp":
            self._cmp(self.state.a, self._read_operand(insn))
        elif op == "cpx":
            self._cmp(self.state.x, self._read_operand(insn))
        elif op == "cpy":
            self._cmp(self.state.y, self._read_operand(insn))

        # Increment/Decrement
        elif op == "inc":
            addr = self._resolve_address(insn)
            value = (self.read_byte(addr) + 1) & 0xFF
            self.write_byte(addr, value)
            self._set_nz(value)
        elif op == "dec":
            addr = self._resolve_address(insn)
            value = (self.read_byte(addr) - 1) & 0xFF
            self.write_byte(addr, value)
            self._set_nz(value)
        elif op == "inx":
            self.state.x = (self.state.x + 1) & 0xFF
            self._set_nz(self.state.x)
        elif op == "iny":
            self.state.y = (self.state.y + 1) & 0xFF
            self._set_nz(self.state.y)
        elif op == "dex":
            self.state.x = (self.state.x - 1) & 0xFF
            self._set_nz(self.state.x)
        elif op == "dey":
            self.state.y = (self.state.y - 1) & 0xFF
            self._set_nz(self.state.y)

        # Shift/Rotate operations
        elif op == "asl":
            if insn.get("dst") == "a":
                self._set_flag(FLAG_C, (self.state.a & 0x80) != 0)
                self.state.a = (self.state.a << 1) & 0xFF
                self._set_nz(self.state.a)
            else:
                addr = self._resolve_address(insn)
                value = self.read_byte(addr)
                self._set_flag(FLAG_C, (value & 0x80) != 0)
                value = (value << 1) & 0xFF
                self.write_byte(addr, value)
                self._set_nz(value)
        elif op == "lsr":
            if insn.get("dst") == "a":
                self._set_flag(FLAG_C, (self.state.a & 0x01) != 0)
                self.state.a = (self.state.a >> 1) & 0xFF
                self._set_nz(self.state.a)
            else:
                addr = self._resolve_address(insn)
                value = self.read_byte(addr)
                self._set_flag(FLAG_C, (value & 0x01) != 0)
                value = (value >> 1) & 0xFF
                self.write_byte(addr, value)
                self._set_nz(value)
        elif op == "rol":
            c_in = 1 if (self.state.p & FLAG_C) else 0
            if insn.get("dst") == "a":
                self._set_flag(FLAG_C, (self.state.a & 0x80) != 0)
                self.state.a = ((self.state.a << 1) | c_in) & 0xFF
                self._set_nz(self.state.a)
            else:
                addr = self._resolve_address(insn)
                value = self.read_byte(addr)
                self._set_flag(FLAG_C, (value & 0x80) != 0)
                value = ((value << 1) | c_in) & 0xFF
                self.write_byte(addr, value)
                self._set_nz(value)
        elif op == "ror":
            c_in = 0x80 if (self.state.p & FLAG_C) else 0
            if insn.get("dst") == "a":
                self._set_flag(FLAG_C, (self.state.a & 0x01) != 0)
                self.state.a = ((self.state.a >> 1) | c_in) & 0xFF
                self._set_nz(self.state.a)
            else:
                addr = self._resolve_address(insn)
                value = self.read_byte(addr)
                self._set_flag(FLAG_C, (value & 0x01) != 0)
                value = ((value >> 1) | c_in) & 0xFF
                self.write_byte(addr, value)
                self._set_nz(value)

        # Branch operations
        elif op == "bcc":
            if not (self.state.p & FLAG_C):
                self.state.pc = insn["target"]
                return
        elif op == "bcs":
            if self.state.p & FLAG_C:
                self.state.pc = insn["target"]
                return
        elif op == "beq":
            if self.state.p & FLAG_Z:
                self.state.pc = insn["target"]
                return
        elif op == "bne":
            if not (self.state.p & FLAG_Z):
                self.state.pc = insn["target"]
                return
        elif op == "bmi":
            if self.state.p & FLAG_N:
                self.state.pc = insn["target"]
                return
        elif op == "bpl":
            if not (self.state.p & FLAG_N):
                self.state.pc = insn["target"]
                return
        elif op == "bvs":
            if self.state.p & FLAG_V:
                self.state.pc = insn["target"]
                return
        elif op == "bvc":
            if not (self.state.p & FLAG_V):
                self.state.pc = insn["target"]
                return

        # Jump/Call operations
        elif op == "jmp":
            if "indirect" in insn:
                pointer = insn["indirect"]
                lo = self.read_byte(pointer)
                hi = self.read_byte((pointer & 0xFF00) | ((pointer + 1) & 0x00FF))
                self.state.pc = (hi << 8) | lo
            else:
                self.state.pc = insn["target"]
            return
        elif op == "jsr":
            # Push return address (PC + 2, but PC already advanced by length)
            self._push_word((self.state.pc + insn["length"] - 1) & 0xFFFF)
            self.state.pc = insn["target"]
            return
        elif op == "rts":
            self.state.pc = (self._pop_word() + 1) & 0xFFFF
            return
        elif op == "rti":
            # Return from interrupt
            self.state.p = (self._pop() | FLAG_UNUSED) & ~FLAG_B
            self.state.pc = self._pop_word()
            return
        elif op == "brk":
            # BRK: push PC+2, push P with B set, load IRQ vector
            self._push_word((self.state.pc + 2) & 0xFFFF)
            self._push(self.state.p | FLAG_B | FLAG_UNUSED)
            self.state.p |= FLAG_I
            self.state.pc = self.read_word(0xFFFE)
            return

        # Flag operations
        elif op == "clc":
            self.state.p &= ~FLAG_C
        elif op == "sec":
            self.state.p |= FLAG_C
        elif op == "cli":
            self.state.p &= ~FLAG_I
        elif op == "sei":
            self.state.p |= FLAG_I
        elif op == "clv":
            self.state.p &= ~FLAG_V
        elif op == "cld":
            self.state.p &= ~FLAG_D
        elif op == "sed":
            self.state.p |= FLAG_D

        # NOP
        elif op == "nop":
            pass

        else:
            raise NES6502ReferenceError(f"unimplemented instruction: {op}")

        # Advance PC by instruction length
        self.state.pc = (self.state.pc + insn["length"]) & 0xFFFF

    def step(self) -> bool:
        """Execute one instruction. Returns False if halted."""
        if self.state.halted:
            return False

        # Synthetic test-harness halt convention (undocumented KIL/JAM 0x02);
        # see `adapters/nes6502.HALT_OPCODE`. Intercepted before decode.
        if self.memory[self.state.pc & 0xFFFF] == HALT_OPCODE:
            self.state.halted = True
            return False

        try:
            insn = decode_full(self.memory, self.state.pc)
        except NES6502Error as e:
            raise NES6502ReferenceError(f"decode error at PC=0x{self.state.pc:04x}: {e}") from e

        self._execute(insn)
        self.steps += 1
        return not self.state.halted

    def run(self, max_steps: int = 10000) -> dict:
        """Run until halted or max_steps reached."""
        while self.steps < max_steps and self.step():
            pass

        return {
            "a": self.state.a,
            "x": self.state.x,
            "y": self.state.y,
            "sp": self.state.sp,
            "pc": self.state.pc,
            "p": self.state.p,
            "halted": self.state.halted,
            "steps": self.steps,
        }


def load_program(code: bytes, start: int = 0x0100) -> bytearray:
    """Load program into memory at specified address with HALT padding."""
    memory = bytearray([0x02] * MEMORY_SIZE)  # Fill with KIL (synthetic halt)
    memory[start:start + len(code)] = code
    return memory


if __name__ == "__main__":
    # Simple smoke test
    code = bytes([
        0xA9, 0x42,  # LDA #$42
        0xAA,        # TAX
        0x8A,        # TXA
        0x02,        # KIL (halt)
    ])
    memory = load_program(code)
    ref = ReferenceNES6502(memory, NES6502State(pc=0x0100))
    result = ref.run()
    assert result["a"] == 0x42
    assert result["x"] == 0x42
    assert result["halted"]
    print("NES6502 reference smoke test: PASS")
