#!/usr/bin/env python3
"""Independent SM83 machine-code reference interpreter (P1-12).

An original, synthetic-input-only reference model of the documented Sharp
SM83 instruction semantics, written as the oracle for the deterministic
headless proof (P1-15) exactly like `tools/mips32_oracle_v1.py` and
`tools/run_mips32_reference.py` serve the MIPS32 paths.

Only documented behavior is implemented:

- 8-bit ALU with the documented Z/N/H/C flag rules (half-carry between bits
  3 and 4, carry out of bit 7; SUB/SBC/CP set N; AND sets H, clears N/C;
  XOR/OR clear N/H/C; INC/DEC preserve C);
- 16-bit ADD HL,rr (H from bit 11, C from bit 15, Z preserved) and ADD SP,r8
  / LD HL,SP+r8 (Z=0, N=0, H/C from the 8-bit addition);
- rotates/shifts through and without carry, with the documented Z/N/H/C
  effects per CB opcode; SWAP clears C;
- DAA with the documented post-add/post-subtract adjustment;
- stack (PUSH/POP/CALL/RET/RST) with the documented high-byte-first order and
  16-bit SP wrap; POP AF masks the low nibble of F;
- EI takes effect after the next instruction (documented); DI is immediate;
- HALT and STOP terminate execution (`halted`), no guessing beyond that;
- all memory access is bounds checked against the 64 KiB model; reaching an
  undocumented opcode raises `SM83ReferenceError` (fail closed);
- cycle counts are intentionally not modelled (out of scope, like the MIPS32
  reference).

The reference is deliberately independent of the IR lowering that arrives in
P1-13 so the P1-15 differential proof has two separately written semantic
implementations.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.sm83 import (  # noqa: E402
    FLAG_C,
    FLAG_H,
    FLAG_N,
    FLAG_WRITE_MASK,
    FLAG_Z,
    SM83Error,
    decode_full,
    is_control_flow,
)

MEMORY_SIZE = 1 << 16


class SM83ReferenceError(RuntimeError):
    """Deterministic fail-closed reference failure."""


@dataclass
class SM83State:
    a: int = 0
    f: int = 0
    b: int = 0
    c: int = 0
    d: int = 0
    e: int = 0
    h: int = 0
    l: int = 0
    sp: int = 0xFFFE
    pc: int = 0x0100
    ime: bool = False
    ei_pending: bool = False
    halted: bool = False

    def snapshot(self) -> dict:
        return {
            "a": self.a,
            "f": self.f,
            "b": self.b,
            "c": self.c,
            "d": self.d,
            "e": self.e,
            "h": self.h,
            "l": self.l,
            "sp": self.sp,
            "pc": self.pc,
            "ime": int(self.ime),
            "halted": int(self.halted),
        }


def _z(result: int) -> int:
    return 0x80 if result == 0 else 0


def _f_from(z: bool, n: bool, h: bool, c: bool) -> int:
    value = 0
    if z:
        value |= FLAG_Z
    if n:
        value |= FLAG_N
    if h:
        value |= FLAG_H
    if c:
        value |= FLAG_C
    return value


class ReferenceSM83:
    def __init__(self, memory: bytes | bytearray, state: SM83State | None = None) -> None:
        if len(memory) != MEMORY_SIZE:
            raise SM83ReferenceError(f"reference requires a {MEMORY_SIZE}-byte memory model")
        self.memory = bytearray(memory)
        self.state = state if state is not None else SM83State()
        self.steps = 0

    # -- documented memory helpers --------------------------------------
    def _check(self, address: int) -> int:
        if not (0 <= address < MEMORY_SIZE):
            raise SM83ReferenceError(f"deterministic memory fault at 0x{address & 0xFFFF:x}")
        return address

    def read_byte(self, address: int) -> int:
        return self.memory[self._check(address & 0xFFFF)]

    def write_byte(self, address: int, value: int) -> None:
        self.memory[self._check(address & 0xFFFF)] = value & 0xFF

    def read_word(self, address: int) -> int:
        return self.read_byte(address) | (self.read_byte(address + 1) << 8)

    def write_word(self, address: int, value: int) -> None:
        value &= 0xFFFF
        self.write_byte(address, value & 0xFF)
        self.write_byte(address + 1, value >> 8)

    # -- register access -------------------------------------------------
    def _r8(self, name: str) -> int:
        if name == "(hl)":
            return self.read_byte((self.state.h << 8) | self.state.l)
        if name == "a":
            return self.state.a
        return getattr(self.state, name)

    def _set_r8(self, name: str, value: int) -> None:
        value &= 0xFF
        if name == "(hl)":
            self.write_byte((self.state.h << 8) | self.state.l, value)
        elif name == "a":
            self.state.a = value
        else:
            setattr(self.state, name, value)

    def _pair(self, name: str) -> int:
        if name == "sp":
            return self.state.sp
        high, low = {"bc": ("b", "c"), "de": ("d", "e"), "hl": ("h", "l"), "af": ("a", "f")}[name]
        return (getattr(self.state, high) << 8) | getattr(self.state, low)

    def _set_pair(self, name: str, value: int) -> None:
        value &= 0xFFFF
        if name == "sp":
            self.state.sp = value
            return
        high, low = {"bc": ("b", "c"), "de": ("d", "e"), "hl": ("h", "l"), "af": ("a", "f")}[name]
        setattr(self.state, high, value >> 8)
        setattr(self.state, low, value & 0xFF)

    # -- flag helpers ----------------------------------------------------
    def _set_flags(self, z: int, n: int, h: int, c: int) -> None:
        self.state.f = _f_from(bool(z), bool(n), bool(h), bool(c))

    def _add8(self, a: int, b: int, carry_in: int = 0) -> int:
        result = a + b + carry_in
        self._set_flags(
            (result & 0xFF) == 0,
            0,
            ((a & 0xF) + (b & 0xF) + carry_in) > 0xF,
            result > 0xFF,
        )
        return result & 0xFF

    def _sub8(self, a: int, b: int, carry_in: int = 0) -> int:
        result = a - b - carry_in
        self._set_flags(
            (result & 0xFF) == 0,
            1,
            ((a & 0xF) - (b & 0xF) - carry_in) < 0,
            result < 0,
        )
        return result & 0xFF

    def _logical(self, value: int, *, h: bool) -> None:
        self._set_flags(value == 0, 0, int(h), 0)

    def _inc8(self, name: str) -> None:
        before = self._r8(name)
        value = (before + 1) & 0xFF
        self._set_r8(name, value)
        self.state.f = (self.state.f & FLAG_C) | _f_from(value == 0, 0, (before & 0xF) == 0xF, False)

    def _dec8(self, name: str) -> None:
        before = self._r8(name)
        value = (before - 1) & 0xFF
        self._set_r8(name, value)
        self.state.f = (self.state.f & FLAG_C) | _f_from(value == 0, 1, (before & 0xF) == 0, False)

    def _add_hl(self, pair: str) -> None:
        hl = self._pair("hl")
        value = self._pair(pair)
        result = hl + value
        f = self.state.f
        self.state.f = (f & FLAG_Z) | _f_from(False, 0, ((hl & 0xFFF) + (value & 0xFFF)) > 0xFFF, result > 0xFFFF)
        self._set_pair("hl", result & 0xFFFF)

    def _add_sp(self, rel: int) -> None:
        sp = self.state.sp
        result = (sp + rel) & 0xFFFF
        self._set_flags(
            0,
            0,
            ((sp & 0xF) + (rel & 0xF)) > 0xF,
            ((sp & 0xFF) + (rel & 0xFF)) > 0xFF,
        )
        self.state.sp = result

    def _condition(self, cond: str) -> bool:
        f = self.state.f
        return {
            "nz": not (f & FLAG_Z),
            "z": bool(f & FLAG_Z),
            "nc": not (f & FLAG_C),
            "c": bool(f & FLAG_C),
        }[cond]

    def _push(self, value: int) -> None:
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

    def _daa(self) -> None:
        # Documented DAA: Z set if A == 0; H reset; N preserved; C per rule.
        f = self.state.f
        a = self.state.a
        if not (f & FLAG_N):
            if (f & FLAG_C) or a > 0x99:
                a = (a + 0x60) & 0xFF
                f |= FLAG_C
            if (f & FLAG_H) or (a & 0x0F) > 0x09:
                a = (a + 0x06) & 0xFF
        else:
            if f & FLAG_C:
                a = (a - 0x60) & 0xFF
            if f & FLAG_H:
                a = (a - 0x06) & 0xFF
        f = (f & (FLAG_N | FLAG_C)) | (FLAG_Z if a == 0 else 0)
        self.state.a = a
        self.state.f = f

    # -- execution -------------------------------------------------------
    def step(self) -> dict:
        """Execute one instruction; returns a deterministic trace entry."""
        state = self.state
        if state.ei_pending:
            # Documented: EI takes effect after the next instruction starts.
            state.ei_pending = False
            state.ime = True
        address = state.pc
        try:
            insn = decode_full(self.memory, address)
        except SM83Error as exc:
            raise SM83ReferenceError(f"decode rejected: {exc}") from exc
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
        elif op == "stop":
            state.halted = True
            state.pc = next_pc
            return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "di":
            state.ime = False
            state.ei_pending = False
        elif op == "ei":
            state.ei_pending = True
        elif op == "ld":
            if insn.get("dst") == "sp":
                state.sp = insn["imm16"]
            elif insn["dst"] in ("(bc)", "(de)", "(hl)", "(hl+)", "(hl-)"):
                value = insn["imm8"] if "imm8" in insn else r8(insn["src"])
                target = self._hl() if insn["dst"] in ("(hl)", "(hl+)", "(hl-)") else self._pair(insn["dst"][1:3])
                self.write_byte(target, value)
                if insn["dst"] in ("(hl+)", "(hl-)"):
                    self._set_pair("hl", (target + (1 if insn["dst"] == "(hl+)" else -1)) & 0xFFFF)
            elif insn["dst"] == "(a16)":
                if insn.get("src") == "sp":
                    self.write_word(insn["a16"], state.sp)
                else:
                    self.write_byte(insn["a16"], state.a)  # documented 8-bit store `ld (a16), a`
            elif insn.get("src") in ("(bc)", "(de)", "(hl)", "(hl+)", "(hl-)", "(a16)"):
                if insn["src"] == "(a16)":
                    value = self.read_word(insn["a16"])
                else:
                    source = self._hl() if insn["src"] in ("(hl)", "(hl+)", "(hl-)") else self._pair(insn["src"][1:3])
                    value = self.read_byte(source)
                    if insn["src"] in ("(hl+)", "(hl-)"):
                        self._set_pair("hl", (source + (1 if insn["src"] == "(hl+)" else -1)) & 0xFFFF)
                self._set_r8(insn["dst"], value)
            elif insn.get("dst") in ("bc", "de", "hl"):
                self._set_pair(insn["dst"], insn["imm16"])
            elif "imm8" in insn:
                self._set_r8(insn["dst"], insn["imm8"])
            elif insn.get("dst") in ("b", "c", "d", "e", "h", "l", "a", "(hl)"):
                self._set_r8(insn["dst"], r8(insn["src"]))
            else:
                raise SM83ReferenceError(f"0x{address:x}: unsupported ld form {insn}")
        elif op == "ldh":
            if insn["dir"] == "store":
                self.write_byte(0xFF00 + (insn["a8"] if "a8" in insn else state.c), state.a)
            else:
                state.a = self.read_byte(0xFF00 + (insn["a8"] if "a8" in insn else state.c))
        elif op == "inc":
            name = insn["r"]
            if name in ("bc", "de", "hl", "sp"):
                self._set_pair(name, (self._pair(name) + 1) & 0xFFFF)
            else:
                self._inc8(name)
        elif op == "dec":
            name = insn["r"]
            if name in ("bc", "de", "hl", "sp"):
                self._set_pair(name, (self._pair(name) - 1) & 0xFFFF)
            else:
                self._dec8(name)
        elif op in ("add", "adc", "sub", "sbc", "and", "xor", "or", "cp"):
            a = state.a
            if "r" in insn:
                value = r8(insn["r"])
            else:
                value = insn["imm8"]
            if op == "add":
                state.a = self._add8(a, value)
            elif op == "adc":
                state.a = self._add8(a, value, 1 if state.f & FLAG_C else 0)
            elif op == "sub":
                state.a = self._sub8(a, value)
            elif op == "sbc":
                state.a = self._sub8(a, value, 1 if state.f & FLAG_C else 0)
            elif op == "and":
                state.a = a & value
                self._logical(state.a, h=True)
            elif op == "xor":
                state.a = a ^ value
                self._logical(state.a, h=False)
            elif op == "or":
                state.a = a | value
                self._logical(state.a, h=False)
            else:
                self._sub8(a, value)
        elif op == "add_hl":
            self._add_hl(insn["pair"])
        elif op == "add_sp":
            self._add_sp(insn["rel"])
        elif op == "ld_hl_sp":
            result = (state.sp + insn["rel"]) & 0xFFFF
            self._set_flags(
                0,
                0,
                ((state.sp & 0xF) + (insn["rel"] & 0xF)) > 0xF,
                ((state.sp & 0xFF) + (insn["rel"] & 0xFF)) > 0xFF,
            )
            self._set_pair("hl", result)
        elif op == "ld_sp_hl":
            state.sp = self._pair("hl")
        elif op == "jp_hl":
            state.pc = self._pair("hl")
            return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "jp":
            if "cond" not in insn or self._condition(insn["cond"]):
                state.pc = insn["target"]
                return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "jr":
            if "cond" not in insn or self._condition(insn["cond"]):
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
        elif op == "reti":
            state.pc = self._pop()
            state.ime = True
            return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "rst":
            self._push(next_pc)
            state.pc = insn["vector"]
            return {"address": address, "op": op, "state": state.snapshot()}
        elif op == "push":
            self._push(self._pair(insn["pair"]))
        elif op == "pop":
            value = self._pop()
            if insn["pair"] == "af":
                state.a = value >> 8
                state.f = value & FLAG_WRITE_MASK
            else:
                self._set_pair(insn["pair"], value)
        elif op in ("rlca", "rrca", "rla", "rra"):
            a = state.a
            carry = bool(state.f & FLAG_C)
            if op == "rlca":
                out = (a >> 7) & 1
                state.a = ((a << 1) | out) & 0xFF
                carry = bool(out)
            elif op == "rrca":
                out = a & 1
                state.a = ((a >> 1) | (out << 7)) & 0xFF
                carry = bool(out)
            elif op == "rla":
                out = (a >> 7) & 1
                state.a = ((a << 1) | int(carry)) & 0xFF
                carry = bool(out)
            else:
                out = a & 1
                state.a = ((a >> 1) | (int(carry) << 7)) & 0xFF
                carry = bool(out)
            self._set_flags(0, 0, 0, int(carry))
        elif op in ("rlc", "rrc", "rl", "rr", "sla", "sra", "srl", "swap", "bit", "res", "set"):
            self._cb(op, insn)
        elif op == "daa":
            self._daa()
        elif op == "cpl":
            state.a ^= 0xFF
            state.f = (state.f & (FLAG_Z | FLAG_C)) | FLAG_N | FLAG_H
        elif op == "scf":
            state.f = (state.f & FLAG_Z) | FLAG_C
        elif op == "ccf":
            state.f = (state.f & (FLAG_Z | FLAG_C)) ^ FLAG_C
        else:
            raise SM83ReferenceError(f"0x{address:x}: unsupported op {op}")

        state.pc = next_pc
        return {"address": address, "op": op, "state": state.snapshot()}

    def _hl(self) -> int:
        return (self.state.h << 8) | self.state.l

    def _cb(self, op: str, insn: dict) -> None:
        state = self.state
        name = insn["r"]
        value = self._r8(name)
        carry = bool(state.f & FLAG_C)
        if op == "bit":
            bit = (value >> insn["n"]) & 1
            state.f = (state.f & FLAG_C) | _f_from(bit == 0, 0, 1, False)
            return
        if op == "res":
            self._set_r8(name, value & ~(1 << insn["n"]))
            return
        if op == "set":
            self._set_r8(name, value | (1 << insn["n"]))
            return
        if op == "rlc":
            out = (value >> 7) & 1
            result = ((value << 1) | out) & 0xFF
            carry = bool(out)
        elif op == "rrc":
            out = value & 1
            result = ((value >> 1) | (out << 7)) & 0xFF
            carry = bool(out)
        elif op == "rl":
            out = (value >> 7) & 1
            result = ((value << 1) | int(carry)) & 0xFF
            carry = bool(out)
        elif op == "rr":
            out = value & 1
            result = ((value >> 1) | (int(carry) << 7)) & 0xFF
            carry = bool(out)
        elif op == "sla":
            out = (value >> 7) & 1
            result = (value << 1) & 0xFF
            carry = bool(out)
        elif op == "sra":
            out = value & 1
            result = ((value >> 1) | (value & 0x80)) & 0xFF
            carry = bool(out)
        elif op == "srl":
            out = value & 1
            result = value >> 1
            carry = bool(out)
        elif op == "swap":
            result = ((value & 0x0F) << 4) | (value >> 4)
            carry = False
        else:
            raise SM83ReferenceError(f"unsupported CB op {op}")
        self._set_r8(name, result)
        self._set_flags(result == 0, 0, 0, int(carry))

    def run(self, *, max_steps: int = 1_000_000) -> dict:
        """Run until HALT/STOP or the step limit; returns final state."""
        while self.steps < max_steps and not self.state.halted:
            self.step()
        if self.steps >= max_steps and not self.state.halted:
            raise SM83ReferenceError("reference step limit exceeded")
        return self.state.snapshot()


def load_program(code: bytes, *, entry: int = 0x0100, memory: bytes | None = None) -> ReferenceSM83:
    """Place a synthetic program into a fresh 64 KiB memory model."""
    if memory is None:
        memory = bytes(MEMORY_SIZE)
    if len(memory) != MEMORY_SIZE:
        raise SM83ReferenceError("memory model must be 64 KiB")
    if entry + len(code) > MEMORY_SIZE:
        raise SM83ReferenceError("program does not fit the memory model")
    image = bytearray(memory)
    image[entry:entry + len(code)] = code
    return ReferenceSM83(image, SM83State(pc=entry))
