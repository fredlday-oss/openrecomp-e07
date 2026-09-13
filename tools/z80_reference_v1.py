#!/usr/bin/env python3
"""Independent Z80 machine-code reference interpreter (P1-21).

An original, synthetic-input-only reference model of the documented Zilog
Z80 instruction semantics, written as the oracle for the deterministic
headless proof (P1-23) exactly like `tools/sm83_reference_v1.py` serves the
Game Boy path.

Only documented behaviour is implemented (Zilog Z80 CPU User Manual flag
rules; z80-heaven flag documentation for the block-transfer flag details):

- 8-bit ALU: S/Z/H/P/V/N/C with the documented rules — H between bits 3/4,
  C out of bit 7, P/V = overflow for add/sub-family and INC/DEC, P/V =
  even parity for logical/rotate/IN/RLD/RRD operations; N set by the
  sub-family/CP/NEG/DEC/CPI/CPD; BIT sets H and clears N with P/V = Z
  (hardware copy, secondary-documented) and S/C unchanged;
- 16-bit ADD HL,rp sets only H (bit 11) and C (bit 15); ADC/SBC HL,rp set
  the full flag set with P/V = overflow;
- rotates RLCA/RRCA/RLA/RRA affect only H/N/C (S/Z/P/V unchanged);
- CB rotates/shifts set S/Z/H=0/P/V=parity/N=0/C;
- DAA post-add/post-subtract adjustment with the documented carry rule;
- EX/EXX/EX AF,AF' shadow exchanges; POP AF loads the full F byte;
- block ops: LDI/LDD/LDIR/LDDR (H=0, N=0, P/V = BC!=0), CPI/CPD/CPIR/CPDR
  (S/Z/H/N from CP, P/V = BC!=0), INI/IND/INIR/INDR and OUTI/OUTD/OTIR/OTDR
  with Z = (B == 0 after decrement), P/V = (B != 0), N set by the -d
  variants and reset by the -i variants, the C flag AND the C register
  preserved, S/H undefined and therefore preserved (Zilog Z80 CPU User
  Manual primary; z80-heaven secondary documentation for the block-I/O
  family);
- IN r,(C) sets S/Z/H=0/P/V=parity/N=0 and keeps C; IN A,(n)/OUT leave all
  flags alone; the port space is a deterministic 256-byte model
  (`port_in`/`port_out`; the SMS port map arrives in P1-22);
- LD A,I / LD A,R set S/Z/H=0/N=0 and P/V = IFF2;
- interrupts: DI clears IFF1/IFF2, EI sets both, RETN copies IFF2 into
  IFF1 (documented); interrupt *dispatch* is platform work (P1-22);
- R is only changed by LD R,A (M1-fetch refresh increments are cycle
  behaviour, out of scope);
- all memory access is bounds checked against the 64 KiB model; reaching an
  undocumented opcode raises `Z80ReferenceError` (fail closed);
- cycle counts are intentionally not modelled.

The reference is deliberately independent of the IR lowering in this stage
so the P1-21/P1-23 differential proofs have two separately written semantic
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

from adapters.z80 import (  # noqa: E402
    FLAG_C,
    FLAG_H,
    FLAG_N,
    FLAG_PV,
    FLAG_S,
    FLAG_Z,
    Z80Error,
    Z80State,
    decode_full,
    exchange_af,
    exchange_all,
    get_pair,
    is_control_flow,
    set_pair,
)

MEMORY_SIZE = 1 << 16
PORT_SPACE_SIZE = 1 << 8


class Z80ReferenceError(RuntimeError):
    """Deterministic fail-closed reference failure."""


class ReferenceZ80:
    def __init__(self, memory: bytes | bytearray, state: Z80State | None = None) -> None:
        if len(memory) != MEMORY_SIZE:
            raise Z80ReferenceError(f"reference requires a {MEMORY_SIZE}-byte memory model")
        self.memory = bytearray(memory)
        self.ports = bytearray(PORT_SPACE_SIZE)
        self.state = state if state is not None else Z80State()
        self.steps = 0
        self.ei_pending = False
        self._current_insn: dict = {}
        self._current_op = ""

    # -- documented memory helpers --------------------------------------
    def _check(self, address: int) -> int:
        if not (0 <= address < MEMORY_SIZE):
            raise Z80ReferenceError(f"deterministic memory fault at 0x{address & 0xFFFF:x}")
        return address

    def read_byte(self, address: int) -> int:
        return self.memory[self._check(address & 0xFFFF)]

    def write_byte(self, address: int, value: int) -> None:
        self.memory[self._check(address & 0xFFFF)] = value & 0xFF

    def read_word(self, address: int) -> int:
        return self.read_byte(address) | (self.read_byte((address + 1) & 0xFFFF) << 8)

    def write_word(self, address: int, value: int) -> None:
        value &= 0xFFFF
        self.write_byte(address, value & 0xFF)
        self.write_byte((address + 1) & 0xFFFF, value >> 8)

    # -- ports -----------------------------------------------------------
    def port_in(self, address: int) -> int:
        """Deterministic 256-byte port model (the SMS map arrives in P1-22)."""
        return self.ports[address & 0xFF]

    def port_out(self, address: int, value: int) -> None:
        self.ports[address & 0xFF] = value & 0xFF

    # -- register access -------------------------------------------------
    def _r8(self, name: str) -> int:
        if name == "(hl)":
            return self.read_byte(self._hl())
        if name == "(ix+d)":
            return self.read_byte(self._index_address("ix"))
        if name == "(iy+d)":
            return self.read_byte(self._index_address("iy"))
        return getattr(self.state, name)

    def _set_r8(self, name: str, value: int) -> None:
        value &= 0xFF
        if name == "(hl)":
            self.write_byte(self._hl(), value)
        elif name == "(ix+d)":
            self.write_byte(self._index_address("ix"), value)
        elif name == "(iy+d)":
            self.write_byte(self._index_address("iy"), value)
        else:
            setattr(self.state, name, value)

    def _hl(self) -> int:
        return (self.state.h << 8) | self.state.l

    def _set_hl(self, value: int) -> None:
        value &= 0xFFFF
        self.state.h = value >> 8
        self.state.l = value & 0xFF

    def _index_address(self, base: str) -> int:
        d = self._current_insn.get("d", 0)
        return (getattr(self.state, base) + d) & 0xFFFF

    def _r16(self, name: str) -> int:
        if name == "sp":
            return self.state.sp
        if name == "ix":
            return self.state.ix
        if name == "iy":
            return self.state.iy
        return get_pair(self.state, name)

    def _set_r16(self, name: str, value: int) -> None:
        value &= 0xFFFF
        if name == "sp":
            self.state.sp = value
        elif name == "ix":
            self.state.ix = value
        elif name == "iy":
            self.state.iy = value
        else:
            set_pair(self.state, name, value)

    # -- flag helpers ----------------------------------------------------
    def _set_flags(self, s: bool, z: bool, h: bool, pv: bool, n: bool, c: bool) -> None:
        value = 0
        if s:
            value |= FLAG_S
        if z:
            value |= FLAG_Z
        if h:
            value |= FLAG_H
        if pv:
            value |= FLAG_PV
        if n:
            value |= FLAG_N
        if c:
            value |= FLAG_C
        self.state.f = value

    @staticmethod
    def _parity(value: int) -> bool:
        return bin(value & 0xFF).count("1") % 2 == 0

    def _szp(self, value: int) -> tuple[bool, bool, bool]:
        value &= 0xFF
        return bool(value & 0x80), value == 0, self._parity(value)

    def _szp_flags(self, value: int) -> None:
        s, z, pv = self._szp(value)
        self._set_flags(s, z, False, pv, False, bool(self.state.f & FLAG_C))

    def _condition(self, cond: str) -> bool:
        f = self.state.f
        return {
            "nz": not (f & FLAG_Z),
            "z": bool(f & FLAG_Z),
            "nc": not (f & FLAG_C),
            "c": bool(f & FLAG_C),
            "po": not (f & FLAG_PV),
            "pe": bool(f & FLAG_PV),
            "p": not (f & FLAG_S),
            "m": bool(f & FLAG_S),
        }[cond]

    def _overflow_add(self, a: int, b: int, result: int) -> bool:
        return bool(((a ^ result) & (b ^ result) & 0x80))

    def _overflow_sub(self, a: int, b: int, result: int) -> bool:
        return bool(((a ^ b) & (a ^ result) & 0x80))

    # -- 8-bit ALU -------------------------------------------------------
    def _alu8(self, kind: str, operand: int) -> None:
        a = self.state.a
        carry = bool(self.state.f & FLAG_C)
        if kind == "add":
            result = a + operand
            s, z, pv = self._szp(result)
            self._set_flags(s, z, ((a & 0xF) + (operand & 0xF)) > 0xF, self._overflow_add(a, operand, result), False, result > 0xFF)
            self.state.a = result & 0xFF
        elif kind == "adc":
            result = a + operand + carry
            self._set_flags(
                bool(result & 0x80),
                (result & 0xFF) == 0,
                ((a & 0xF) + (operand & 0xF) + carry) > 0xF,
                self._overflow_add(a, operand, result),
                False,
                result > 0xFF,
            )
            self.state.a = result & 0xFF
        elif kind in ("sub", "cp"):
            result = a - operand
            self._set_flags(
                bool(result & 0x80),
                (result & 0xFF) == 0,
                ((a & 0xF) - (operand & 0xF)) < 0,
                self._overflow_sub(a, operand, result),
                True,
                result < 0,
            )
            if kind == "sub":
                self.state.a = result & 0xFF
        elif kind == "sbc":
            result = a - operand - carry
            self._set_flags(
                bool(result & 0x80),
                (result & 0xFF) == 0,
                ((a & 0xF) - (operand & 0xF) - carry) < 0,
                self._overflow_sub(a, operand, result),
                True,
                result < 0,
            )
            self.state.a = result & 0xFF
        elif kind == "and":
            result = a & operand
            self._set_flags(bool(result & 0x80), result == 0, True, self._parity(result), False, False)
            self.state.a = result
        elif kind == "xor":
            result = a ^ operand
            self._set_flags(bool(result & 0x80), result == 0, False, self._parity(result), False, False)
            self.state.a = result
        elif kind == "or":
            result = a | operand
            self._set_flags(bool(result & 0x80), result == 0, False, self._parity(result), False, False)
            self.state.a = result
        else:
            raise Z80ReferenceError(f"unsupported ALU kind {kind}")

    def _neg(self) -> None:
        a = self.state.a
        result = 0 - a
        self._set_flags(
            bool(result & 0x80),
            (result & 0xFF) == 0,
            ((0 & 0xF) - (a & 0xF)) < 0,
            self._overflow_sub(0, a, result),
            True,
            result < 0,
        )
        self.state.a = result & 0xFF

    def _inc8(self, name: str) -> None:
        before = self._r8(name)
        result = before + 1
        self._set_r8(name, result)
        self._set_flags(
            bool(result & 0x80),
            (result & 0xFF) == 0,
            (before & 0xF) == 0xF,
            before == 0x7F,  # documented overflow
            False,
            bool(self.state.f & FLAG_C),
        )

    def _dec8(self, name: str) -> None:
        before = self._r8(name)
        result = before - 1
        self._set_r8(name, result)
        self._set_flags(
            bool(result & 0x80),
            (result & 0xFF) == 0,
            (before & 0xF) == 0,
            before == 0x80,  # documented overflow
            True,
            bool(self.state.f & FLAG_C),
        )

    def _daa(self) -> None:
        f = self.state.f
        a = self.state.a
        correction = 0
        carry = bool(f & FLAG_C)
        if (f & FLAG_H) or (not (f & FLAG_N) and (a & 0x0F) > 9):
            correction |= 0x06
        if carry or (not (f & FLAG_N) and a > 0x99):
            correction |= 0x60
            carry = True
        result = (a + correction) if not (f & FLAG_N) else (a - correction)
        result &= 0xFF
        self.state.a = result
        self._set_flags(
            bool(result & 0x80),
            result == 0,
            False,
            self._parity(result),
            bool(f & FLAG_N),
            carry,
        )

    # -- 16-bit arithmetic ------------------------------------------------
    def _add16(self, dst: str, operand: int, *, carry_kind: str | None = None) -> None:
        value = self._r16(dst)
        if carry_kind is None:
            result = value + operand
            f = self.state.f
            self._set_r16(dst, result)
            # Documented ADD HL,ss: N reset; S/Z/P/V unaffected; H/C computed.
            self.state.f = (f & (FLAG_S | FLAG_Z | FLAG_PV)) | (
                FLAG_H if ((value & 0xFFF) + (operand & 0xFFF)) > 0xFFF else 0
            ) | (FLAG_C if result > 0xFFFF else 0)
            return
        carry = bool(self.state.f & FLAG_C)
        if carry_kind == "adc":
            result = value + operand + carry
            h = ((value & 0xFFF) + (operand & 0xFFF) + carry) > 0xFFF
            c = result > 0xFFFF
            pv = self._overflow_add(value, operand, result)
            n = False
        else:
            result = value - operand - carry
            h = ((value & 0xFFF) - (operand & 0xFFF) - carry) < 0
            c = result < 0
            pv = self._overflow_sub(value, operand, result)
            n = True
        self._set_r16(dst, result)
        self._set_flags(bool(result & 0x8000), (result & 0xFFFF) == 0, h, pv, n, c)

    # -- stack -------------------------------------------------------------
    def _push(self, value: int) -> None:
        value &= 0xFFFF
        self.state.sp = (self.state.sp - 1) & 0xFFFF
        self.write_byte(self.state.sp, value >> 8)
        self.state.sp = (self.state.sp - 1) & 0xFFFF
        self.write_byte(self.state.sp, value & 0xFF)

    def _pop(self) -> int:
        low = self.read_byte(self.state.sp)
        self.state.sp = (self.state.sp + 1) & 0xFFFF
        high = self.read_byte(self.state.sp)
        self.state.sp = (self.state.sp + 1) & 0xFFFF
        return (high << 8) | low

    # -- rotates/shifts -----------------------------------------------------
    def _rotate_a(self, op: str) -> None:
        a = self.state.a
        carry = bool(self.state.f & FLAG_C)
        if op == "rlca":
            out = (a >> 7) & 1
            self.state.a = ((a << 1) | out) & 0xFF
        elif op == "rrca":
            out = a & 1
            self.state.a = ((a >> 1) | (out << 7)) & 0xFF
        elif op == "rla":
            out = (a >> 7) & 1
            self.state.a = ((a << 1) | int(carry)) & 0xFF
        else:
            out = a & 1
            self.state.a = ((a >> 1) | (int(carry) << 7)) & 0xFF
        f = self.state.f
        self.state.f = (f & (FLAG_S | FLAG_Z | FLAG_PV)) | (FLAG_C if out else 0)

    def _cb_op(self, op: str, name: str, n: int | None = None) -> None:
        value = self._r8(name)
        carry = bool(self.state.f & FLAG_C)
        if op == "bit":
            bit = (value >> n) & 1
            f = self.state.f
            self.state.f = (f & (FLAG_S | FLAG_C)) | (FLAG_H | (FLAG_Z if bit == 0 else 0) | (FLAG_PV if bit == 0 else 0))
            return
        if op == "res":
            self._set_r8(name, value & ~(1 << n))
            return
        if op == "set":
            self._set_r8(name, value | (1 << n))
            return
        if op == "rlc":
            out = (value >> 7) & 1
            result = ((value << 1) | out) & 0xFF
        elif op == "rrc":
            out = value & 1
            result = ((value >> 1) | (out << 7)) & 0xFF
        elif op == "rl":
            out = (value >> 7) & 1
            result = ((value << 1) | int(carry)) & 0xFF
        elif op == "rr":
            out = value & 1
            result = ((value >> 1) | (int(carry) << 7)) & 0xFF
        elif op == "sla":
            out = (value >> 7) & 1
            result = (value << 1) & 0xFF
        elif op == "sra":
            out = value & 1
            result = ((value >> 1) | (value & 0x80)) & 0xFF
        elif op == "srl":
            out = value & 1
            result = value >> 1
        else:
            raise Z80ReferenceError(f"unsupported CB op {op}")
        self._set_r8(name, result)
        self._set_flags(bool(result & 0x80), result == 0, False, self._parity(result), False, bool(out))

    # -- execution -----------------------------------------------------------
    def step(self) -> dict:
        """Execute one instruction; returns a deterministic trace entry."""
        state = self.state
        if self.ei_pending:
            # Documented: EI enables interrupts after the following instruction.
            self.ei_pending = False
            state.iff1 = state.iff2 = True
        address = state.pc
        try:
            insn = decode_full(self.memory, address)
        except Z80Error as exc:
            raise Z80ReferenceError(f"decode rejected: {exc}") from exc
        self._current_insn = insn
        self._current_op = insn["op"]
        op = insn["op"]
        self.steps += 1
        next_pc = (address + insn["length"]) & 0xFFFF

        def r8(name: str) -> int:
            return self._r8(name)

        if op == "nop":
            pass
        elif op == "halt":
            state.halted = True
            state.pc = next_pc
            return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "di":
            state.iff1 = state.iff2 = False
            self.ei_pending = False
        elif op == "ei":
            self.ei_pending = True
        elif op == "im":
            state.im = insn["mode"]
        elif op == "ld":
            self._ld(insn, r8)
        elif op == "ex":
            if insn.get("dst") == "(sp)":
                value = self.read_word(state.sp)
                self.write_word(state.sp, self._r16(insn["src"]))
                self._set_r16(insn["src"], value)
            else:
                de = get_pair(state, "de")
                set_pair(state, "de", self._hl())
                self._set_hl(de)
        elif op == "exx":
            exchange_all(state)
        elif op == "ex_af":
            exchange_af(state)
        elif op in ("add", "adc", "sub", "sbc", "and", "xor", "or", "cp"):
            operand = insn["imm8"] if "imm8" in insn else r8(insn["r"])
            self._alu8(op, operand)
        elif op == "neg":
            self._neg()
        elif op == "daa":
            self._daa()
        elif op == "cpl":
            state.a ^= 0xFF
            self.state.f = (state.f & (FLAG_S | FLAG_Z | FLAG_PV | FLAG_C)) | FLAG_H | FLAG_N
        elif op == "scf":
            self.state.f = (state.f & (FLAG_S | FLAG_Z | FLAG_PV)) | FLAG_C
        elif op == "ccf":
            carry = bool(state.f & FLAG_C)
            self.state.f = (state.f & (FLAG_S | FLAG_Z | FLAG_PV)) | (FLAG_H if carry else 0) | (0 if carry else FLAG_C)
        elif op in ("rlca", "rrca", "rla", "rra"):
            self._rotate_a(op)
        elif op in ("rlc", "rrc", "rl", "rr", "sla", "sra", "srl", "bit", "res", "set"):
            self._cb_op(op, insn["r"], insn.get("n"))
        elif op == "rrd":
            # Documented: A[3:0] -> (HL)[7:4] -> (HL)[3:0] -> A[3:0].
            value = self.read_byte(self._hl())
            new_a = (state.a & 0xF0) | (value & 0x0F)
            self.write_byte(self._hl(), ((state.a & 0x0F) << 4) | (value >> 4))
            state.a = new_a
            self._szp_flags(new_a)
        elif op == "rld":
            # Documented: (HL)[3:0] -> (HL)[7:4] -> A[3:0]... A[3:0] = old (HL)[7:4].
            value = self.read_byte(self._hl())
            new_a = (state.a & 0xF0) | (value >> 4)
            self.write_byte(self._hl(), ((value << 4) & 0xFF) | (state.a & 0x0F))
            state.a = new_a
            self._szp_flags(new_a)
        elif op == "ld_sp_r16":
            state.sp = self._r16(insn["reg"])
        elif op == "inc":
            name = insn["r"]
            if name in ("bc", "de", "hl", "sp", "ix", "iy"):
                self._set_r16(name, self._r16(name) + 1)
            else:
                self._inc8(name)
        elif op == "dec":
            name = insn["r"]
            if name in ("bc", "de", "hl", "sp", "ix", "iy"):
                self._set_r16(name, self._r16(name) - 1)
            else:
                self._dec8(name)
        elif op == "add_hl":
            self._add16("hl", self._r16(insn["pair"]))
        elif op == "add_r16":
            self._add16(insn["dst"], self._r16(insn["pair"]))
        elif op == "adc_hl":
            self._add16("hl", self._r16(insn["pair"]), carry_kind="adc")
        elif op == "sbc_hl":
            self._add16("hl", self._r16(insn["pair"]), carry_kind="sbc")
        elif op == "push":
            self._push(self._r16(insn["pair"]))
        elif op == "pop":
            value = self._pop()
            if insn["pair"] == "af":
                state.a = value >> 8
                state.f = value & 0xFF  # documented: POP AF loads the full F byte
            else:
                self._set_r16(insn["pair"], value)
        elif op == "in":
            if insn.get("src") == "(c)":
                value = self.port_in(self._r16("bc"))
                self._set_r8(insn["dst"], value)
                self._szp_flags(value)
            else:
                self._set_r8(insn["dst"], self.port_in((state.a << 8) | insn["port_n"]))
        elif op == "out":
            if insn.get("dst") == "(c)":
                self.port_out(self._r16("bc"), r8(insn["src"]))
            else:
                self.port_out((state.a << 8) | insn["port_n"], state.a)
        elif op in ("ldi", "ldd", "ldir", "lddr", "cpi", "cpd", "cpir", "cpdr",
                    "ini", "ind", "inir", "indr", "outi", "outd", "otir", "otdr"):
            if self._block_op(op):
                # Documented: repeating block ops hold PC and iterate internally.
                state.pc = address
                return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "jp_ind":
            state.pc = self._r16(insn["reg"])
            return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "jp":
            if "cond" not in insn or self._condition(insn["cond"]):
                state.pc = insn["target"]
                return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "jr":
            if "cond" not in insn or self._condition(insn["cond"]):
                state.pc = insn["target"]
                return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "djnz":
            state.b = (state.b - 1) & 0xFF
            if state.b:
                state.pc = insn["target"]
                return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "call":
            if "cond" not in insn or self._condition(insn["cond"]):
                self._push(next_pc)
                state.pc = insn["target"]
                return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "ret":
            if "cond" not in insn or self._condition(insn["cond"]):
                state.pc = self._pop()
                return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "retn":
            state.pc = self._pop()
            state.iff1 = state.iff2  # documented
            return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "reti":
            state.pc = self._pop()
            return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "rst":
            self._push(next_pc)
            state.pc = insn["vector"]
            return {"address": address, "op": op, "state": state.snapshot()}
        else:
            raise Z80ReferenceError(f"0x{address:x}: unsupported op {op}")

        state.pc = next_pc
        return {"address": address, "op": op, "state": state.snapshot()}

    def _ld(self, insn: dict, r8) -> None:
        state = self.state
        dst = insn.get("dst")
        src = insn.get("src")
        if dst == "sp" and src is None and "imm16" in insn:
            state.sp = insn["imm16"]
        elif dst in ("bc", "de", "hl", "sp", "ix", "iy") and "imm16" in insn:
            self._set_r16(dst, insn["imm16"])
        elif dst in ("bc", "de", "hl", "sp") and src == "(a16)":
            self._set_r16(dst, self.read_word(insn["a16"]))
        elif dst == "(a16)" and src in ("bc", "de", "hl", "sp", "a", "ix", "iy"):
            if src == "a":
                self.write_byte(insn["a16"], state.a)
            else:
                self.write_word(insn["a16"], self._r16(src))
        elif dst in ("i", "r"):
            setattr(state, dst, state.a)
        elif src in ("i", "r"):
            value = getattr(state, src)
            state.a = value
            self._set_flags(bool(value & 0x80), value == 0, False, state.iff2, False, bool(state.f & FLAG_C))
        elif dst == "(bc)":
            self.write_byte(self._r16("bc"), state.a)
        elif dst == "(de)":
            self.write_byte(self._r16("de"), state.a)
        elif src == "(bc)":
            self._set_r8(dst, self.read_byte(self._r16("bc")))
        elif src == "(de)":
            self._set_r8(dst, self.read_byte(self._r16("de")))
        elif dst in ("ix", "iy") and src == "(a16)":
            setattr(state, dst, self.read_word(insn["a16"]))
        elif src == "(a16)":
            self._set_r8(dst, self.read_byte(insn["a16"]))
        elif dst in ("b", "c", "d", "e", "h", "l", "a", "(hl)", "(ix+d)", "(iy+d)"):
            value = insn["imm8"] if "imm8" in insn else r8(src)
            self._set_r8(dst, value)
        else:
            raise Z80ReferenceError(f"0x{insn['address']:x}: unsupported ld form {insn}")

    def _block_op(self, op: str) -> bool:
        """One block-op iteration. Returns True when the CPU repeats
        internally (documented: PC does not advance while the op repeats)."""
        state = self.state
        # ldd/cpd/ind/outd (and their -r forms) decrement HL/DE.
        direction = -1 if op.endswith(("d", "dr")) else 1
        base = op[0]
        if base == "l":
            value = self.read_byte(self._hl())
            self.write_byte(self._r16("de"), value)
            self._set_hl(self._hl() + direction)
            self._set_r16("de", self._r16("de") + direction)
            self._set_r16("bc", self._r16("bc") - 1)
            f = state.f
            state.f = (f & (FLAG_S | FLAG_Z | FLAG_C)) | (FLAG_PV if self._r16("bc") else 0)
            return op.endswith(("ir", "dr")) and self._r16("bc") != 0
        if base == "c":
            value = self.read_byte(self._hl())
            a = state.a
            result = a - value
            self._set_hl(self._hl() + direction)
            self._set_r16("bc", self._r16("bc") - 1)
            self._set_flags(
                bool(result & 0x80),
                (result & 0xFF) == 0,
                ((a & 0xF) - (value & 0xF)) < 0,
                bool(self._r16("bc")),
                True,
                bool(state.f & FLAG_C),
            )
            return op.endswith(("ir", "dr")) and self._r16("bc") != 0 and not (state.f & FLAG_Z)
        if base == "i":
            value = self.port_in(self._r16("bc"))
            self.write_byte(self._hl(), value)
            state.b = (state.b - 1) & 0xFF
            self._set_hl(self._hl() + direction)
            f = state.f
            state.f = (
                (f & (FLAG_S | FLAG_H | FLAG_C))
                | (FLAG_N if direction == -1 else 0)
                | (FLAG_Z if state.b == 0 else 0)
                | (FLAG_PV if state.b else 0)
            )
            return op.endswith(("ir", "dr")) and state.b != 0
        if base == "o":
            value = self.read_byte(self._hl())
            state.b = (state.b - 1) & 0xFF
            self.port_out(self._r16("bc"), value)
            self._set_hl(self._hl() + direction)
            f = state.f
            state.f = (
                (f & (FLAG_S | FLAG_H | FLAG_C))
                | (FLAG_N if direction == -1 else 0)
                | (FLAG_Z if state.b == 0 else 0)
                | (FLAG_PV if state.b else 0)
            )
            return op.endswith(("ir", "dr")) and state.b != 0
        raise Z80ReferenceError(f"unsupported block op {op}")

    def run(self, *, max_steps: int = 1_000_000) -> dict:
        """Run until HALT or the step limit; returns final state."""
        while self.steps < max_steps and not self.state.halted:
            self.step()
        if self.steps >= max_steps and not self.state.halted:
            raise Z80ReferenceError("reference step limit exceeded")
        return self.state.snapshot()


def load_program(code: bytes, *, entry: int = 0x0100, memory: bytes | None = None) -> ReferenceZ80:
    """Place a synthetic program into a fresh 64 KiB memory model."""
    if memory is None:
        memory = bytes(MEMORY_SIZE)
    if len(memory) != MEMORY_SIZE:
        raise Z80ReferenceError("memory model must be 64 KiB")
    if entry + len(code) > MEMORY_SIZE:
        raise Z80ReferenceError("program does not fit the memory model")
    image = bytearray(memory)
    image[entry:entry + len(code)] = code
    state = Z80State(pc=entry, sp=0xFFFE)
    return ReferenceZ80(image, state)
