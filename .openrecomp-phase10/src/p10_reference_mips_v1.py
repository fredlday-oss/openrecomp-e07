#!/usr/bin/env python3
"""OpenRecomp Phase-10 independent MIPS32 reference interpreter V1.

An independently structured bounded interpreter for exactly the op set that the
Phase-10 synthetic semantics fixture exercises. It exists to cross-check the
generated host translation, so it is written without importing the emitter,
the semantic rule table, the Phase-8 rule table, the runtime ABI or the
Phase-9 reference interpreter:

* its own bit-field decoder;
* its own little-endian guest memory model with the same KSEG0/KSEG1 window
  and width-bounded, range-checked accesses;
* its own register file, HI/LO state and delay-slot execution order;
* explicit fail-closed errors with stable codes.

It never executes original console machine code: it interprets
OpenRecomp-authored fixture words only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REFERENCE_VERSION = "1.0.0"

MASK32 = 0xFFFFFFFF
RAM_BASE = 0x80000000
RAM_MIRROR = 0xA0000000
RAM_SIZE = 0x00200000

STEP_LIMIT = 200000

FUNCTS = {
    0x00: "sll", 0x02: "srl", 0x03: "sra", 0x04: "sllv", 0x06: "srlv",
    0x07: "srav", 0x08: "jr", 0x09: "jalr", 0x0C: "syscall", 0x0D: "break",
    0x10: "mfhi", 0x12: "mflo", 0x18: "mult", 0x19: "multu", 0x1A: "div",
    0x1B: "divu", 0x20: "add", 0x21: "addu", 0x22: "sub", 0x23: "subu",
    0x24: "and", 0x25: "or", 0x26: "xor", 0x27: "nor", 0x2A: "slt", 0x2B: "sltu",
}

OPCODES = {
    0x02: "j", 0x03: "jal", 0x04: "beq", 0x05: "bne", 0x06: "blez",
    0x07: "bgtz", 0x08: "addi", 0x09: "addiu", 0x0A: "slti", 0x0B: "sltiu",
    0x0C: "andi", 0x0D: "ori", 0x0E: "xori", 0x0F: "lui", 0x20: "lb",
    0x21: "lh", 0x22: "lwl", 0x23: "lw", 0x24: "lbu", 0x25: "lhu",
    0x26: "lwr", 0x28: "sb", 0x29: "sh", 0x2A: "swl", 0x2B: "sw",
    0x2E: "swr",
}

REGIMM = {0x00: "bltz", 0x01: "bgez", 0x10: "bltzal", 0x11: "bgezal"}


class ReferenceError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def sign16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def sign32(value: int) -> int:
    value &= MASK32
    return value - 0x100000000 if value & 0x80000000 else value


@dataclass
class ReferenceMachine:
    """Independent bounded MIPS32 interpreter over OpenRecomp fixture words."""

    code: dict[int, int]
    entry: int
    ram: bytearray
    registers: list[int] = field(default_factory=lambda: [0] * 32)
    hi: int = 0
    lo: int = 0
    steps: int = 0
    hi_defined: bool = False
    failed: int = 0
    error: str = ""
    denied: int = 0

    # --- memory ---------------------------------------------------------
    def _offset(self, address: int, width: int) -> int:
        for base in (RAM_BASE, RAM_MIRROR):
            if base <= address and address + width <= base + len(self.ram):
                return address - base
        raise ReferenceError("MEMORY_OUT_OF_RANGE", f"0x{address:08x}/{width}")

    def read(self, address: int, width: int) -> int:
        address &= MASK32
        offset = self._offset(address, width)
        value = 0
        for index in range(width):
            value |= self.ram[offset + index] << (8 * index)
        return value

    def write(self, address: int, width: int, value: int) -> None:
        address &= MASK32
        offset = self._offset(address, width)
        for index in range(width):
            self.ram[offset + index] = (value >> (8 * index)) & 0xFF

    # --- registers ------------------------------------------------------
    def r(self, index: int) -> int:
        return self.registers[index] & MASK32

    def w(self, index: int, value: int) -> None:
        if index != 0:
            self.registers[index] = value & MASK32

    # --- decode ---------------------------------------------------------
    def decode(self, word: int) -> dict[str, int | str]:
        opcode = (word >> 26) & 0x3F
        rs = (word >> 21) & 0x1F
        rt = (word >> 16) & 0x1F
        rd = (word >> 11) & 0x1F
        shamt = (word >> 6) & 0x1F
        funct = word & 0x3F
        imm = word & 0xFFFF
        if opcode == 0:
            return {"op": FUNCTS.get(funct, f"special-0x{funct:02x}"), "rs": rs, "rt": rt,
                    "rd": rd, "shamt": shamt, "imm": imm, "funct": funct, "opcode": 0}
        if opcode == 1:
            return {"op": REGIMM.get(rt, f"regimm-0x{rt:02x}"), "rs": rs, "rt": rt,
                    "rd": rd, "shamt": shamt, "imm": imm, "opcode": 1}
        return {"op": OPCODES.get(opcode, f"opcode-0x{opcode:02x}"), "rs": rs, "rt": rt,
                "rd": rd, "shamt": shamt, "imm": imm, "opcode": opcode}

    # --- execution ------------------------------------------------------
    def _step(self, pc: int) -> dict[str, int | str] | None:
        """Fetch, decode and execute one instruction; fail closed on error."""
        if self.steps >= STEP_LIMIT:
            self.fail("STEP_LIMIT", str(self.steps))
            return None
        self.steps += 1
        if pc not in self.code:
            self.fail("PC_OUTSIDE_IMAGE", f"0x{pc:08x}")
            return None
        decoded = self.decode(self.code[pc])
        if decoded["op"] in ("syscall", "break"):
            self.fail("GUEST_TRAP", f"{decoded['op']} at 0x{pc:08x}")
            return None
        try:
            self.execute(pc, decoded)
        except ReferenceError as exc:
            self.fail(exc.code, exc.detail)
            return None
        return decoded

    def run(self) -> "ReferenceMachine":
        pc = self.entry
        while True:
            decoded = self._step(pc)
            if decoded is None:
                return self
            word = self.code.get(pc)
            op = decoded["op"]
            if op in ("j", "jal", "jr", "jalr", "beq", "bne", "bltz", "bgez", "blez", "bgtz"):
                # The delay slot always executes, before the transfer applies.
                delay = self._step(pc + 4)
                if delay is None:
                    return self
            if op == "j":
                pc = ((pc + 4) & 0xF0000000) | (((word or 0) & 0x03FFFFFF) << 2)
            elif op == "jal":
                self.w(31, pc + 8)
                pc = ((pc + 4) & 0xF0000000) | (((word or 0) & 0x03FFFFFF) << 2)
            elif op == "beq":
                pc = ((pc + 4) + (sign16(decoded["imm"]) << 2)
                      if self.r(decoded["rs"]) == self.r(decoded["rt"]) else pc + 8)
            elif op == "bne":
                pc = ((pc + 4) + (sign16(decoded["imm"]) << 2)
                      if self.r(decoded["rs"]) != self.r(decoded["rt"]) else pc + 8)
            elif op == "bltz":
                pc = ((pc + 4) + (sign16(decoded["imm"]) << 2)
                      if sign32(self.r(decoded["rs"])) < 0 else pc + 8)
            elif op == "bgez":
                pc = ((pc + 4) + (sign16(decoded["imm"]) << 2)
                      if sign32(self.r(decoded["rs"])) >= 0 else pc + 8)
            elif op == "blez":
                pc = ((pc + 4) + (sign16(decoded["imm"]) << 2)
                      if sign32(self.r(decoded["rs"])) <= 0 else pc + 8)
            elif op == "bgtz":
                pc = ((pc + 4) + (sign16(decoded["imm"]) << 2)
                      if sign32(self.r(decoded["rs"])) > 0 else pc + 8)
            elif op == "jr":
                target = self.r(decoded["rs"])
                if target == 0:
                    return self
                if target & 3 or target not in self.code:
                    self.fail("PC_OUTSIDE_IMAGE", f"0x{target:08x}")
                    return self
                pc = target
            elif op == "jalr":
                target = self.r(decoded["rs"])
                self.w(decoded["rd"], pc + 8)
                if target & 3 or target not in self.code:
                    self.fail("PC_OUTSIDE_IMAGE", f"0x{target:08x}")
                    return self
                pc = target
            else:
                pc = pc + 4

    def fail(self, code: str, detail: str) -> None:
        self.failed = 1
        self.error = f"{code}: {detail}"

    def execute(self, pc: int, d: dict) -> None:
        op = d["op"]
        rs, rt, rd, shamt, imm = d["rs"], d["rt"], d["rd"], d["shamt"], d["imm"]
        if op == "nop":
            return
        if op == "sll":
            self.w(rd, self.r(rt) << shamt)
        elif op == "srl":
            self.w(rd, self.r(rt) >> shamt)
        elif op == "sra":
            self.w(rd, sign32(self.r(rt)) >> shamt)
        elif op == "addu":
            self.w(rd, self.r(rs) + self.r(rt))
        elif op == "subu":
            self.w(rd, self.r(rs) - self.r(rt))
        elif op == "and":
            self.w(rd, self.r(rs) & self.r(rt))
        elif op == "or":
            self.w(rd, self.r(rs) | self.r(rt))
        elif op == "xor":
            self.w(rd, self.r(rs) ^ self.r(rt))
        elif op == "nor":
            self.w(rd, ~(self.r(rs) | self.r(rt)))
        elif op == "slt":
            self.w(rd, 1 if sign32(self.r(rs)) < sign32(self.r(rt)) else 0)
        elif op == "sltu":
            self.w(rd, 1 if self.r(rs) < self.r(rt) else 0)
        elif op == "mult":
            self.lo = (self.r(rs) * self.r(rt)) & MASK32
            self.hi = (sign32(self.r(rs)) * sign32(self.r(rt))) >> 32 & MASK32
            self.hi_defined = True
        elif op == "mfhi":
            if not self.hi_defined:
                raise ReferenceError("HI_UNDEFINED", f"0x{pc:08x}")
            self.w(rd, self.hi)
        elif op == "addiu":
            self.w(rt, self.r(rs) + sign16(imm))
        elif op == "addi":
            total = sign32(self.r(rs)) + sign16(imm)
            if total != sign32(total):
                raise ReferenceError("OVERFLOW", f"0x{pc:08x}")
            self.w(rt, total)
        elif op == "andi":
            self.w(rt, self.r(rs) & imm)
        elif op == "ori":
            self.w(rt, self.r(rs) | imm)
        elif op == "xori":
            self.w(rt, self.r(rs) ^ imm)
        elif op == "lui":
            self.w(rt, imm << 16)
        elif op == "slti":
            self.w(rt, 1 if sign32(self.r(rs)) < sign16(imm) else 0)
        elif op == "sltiu":
            self.w(rt, 1 if self.r(rs) < (sign16(imm) & MASK32) else 0)
        elif op == "lb":
            self.w(rt, sign_extend(self.read(self.r(rs) + sign16(imm), 1), 8))
        elif op == "lbu":
            self.w(rt, self.read(self.r(rs) + sign16(imm), 1))
        elif op == "lh":
            self.w(rt, sign_extend(self.read(self.r(rs) + sign16(imm), 2), 16))
        elif op == "lhu":
            self.w(rt, self.read(self.r(rs) + sign16(imm), 2))
        elif op == "lw":
            self.w(rt, self.read(self.r(rs) + sign16(imm), 4))
        elif op == "sb":
            self.write(self.r(rs) + sign16(imm), 1, self.r(rt))
        elif op == "sh":
            self.write(self.r(rs) + sign16(imm), 2, self.r(rt))
        elif op == "sw":
            self.write(self.r(rs) + sign16(imm), 4, self.r(rt))
        elif op in ("lwl", "lwr", "swl", "swr"):
            self._partial(pc, op, self.r(rs) + sign16(imm), rt)
        elif op in ("j", "jal", "beq", "bne", "bltz", "bgez", "blez", "bgtz"):
            return
        elif op in ("jr", "jalr"):
            return
        else:
            raise ReferenceError("UNSUPPORTED_OP", f"{op} at 0x{pc:08x}")

    def _partial(self, pc: int, op: str, address: int, rt: int) -> None:
        address &= MASK32
        aligned = address & ~3
        offset = address & 3
        word = self.read(aligned, 4)
        data = [(word >> (8 * index)) & 0xFF for index in range(4)]
        value = self.r(rt)
        if op == "lwl":
            # rt's high bytes take memory bytes 0..offset (rt keeps its low bytes).
            result = value
            for index in range(offset + 1):
                byte = (word >> (8 * (offset - index))) & 0xFF
                shift = 8 * (3 - index)
                result = (result & ~(0xFF << shift)) | (byte << shift)
            self.w(rt, result)
        elif op == "lwr":
            # rt's low bytes take memory bytes offset..3 (rt keeps its high bytes).
            result = value
            for index in range(offset, 4):
                byte = (word >> (8 * index)) & 0xFF
                shift = 8 * (index - offset)
                result = (result & ~(0xFF << shift)) | (byte << shift)
            self.w(rt, result)
        elif op == "swl":
            merged = list(data)
            for index in range(offset + 1):
                merged[offset - index] = (value >> (8 * (3 - index))) & 0xFF
            self.write(aligned, 4, sum(byte << (8 * index) for index, byte in enumerate(merged)))
        else:
            merged = list(data)
            for index in range(4 - offset):
                merged[offset + index] = (value >> (8 * index)) & 0xFF
            self.write(aligned, 4, sum(byte << (8 * index) for index, byte in enumerate(merged)))


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def build_code(words: list[int], load_address: int) -> dict[int, int]:
    return {load_address + 4 * index: word for index, word in enumerate(words)}


def load_and_run(words: list[int], load_address: int, entry: int, flat: bytes) -> ReferenceMachine:
    machine = ReferenceMachine(
        code=build_code(words, load_address),
        entry=entry,
        ram=bytearray(flat),
    )
    return machine.run()


def observables(machine: ReferenceMachine) -> dict[str, Any]:
    registers = 0xCBF29CE484222325
    for index in range(32):
        value = machine.registers[index] & MASK32
        for byte in range(4):
            registers ^= (value >> (8 * byte)) & 0xFF
            registers = (registers * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    memory = 0xCBF29CE484222325
    for byte in machine.ram:
        memory ^= byte
        memory = (memory * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return {
        "failed": machine.failed,
        "error": machine.error,
        "exit_status": f"0x{machine.r(2):08x}",
        "registers_digest": f"0x{registers:016x}",
        "memory_digest": f"0x{memory:016x}",
        "steps": machine.steps,
        "denied": machine.denied,
    }
