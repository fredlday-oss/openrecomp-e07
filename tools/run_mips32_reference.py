#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

MASK32 = 0xFFFFFFFF


class ReferenceError(RuntimeError):
    pass


def _sign16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _signed32(value: int) -> int:
    value &= MASK32
    return value - 0x100000000 if value & 0x80000000 else value


def load_hex(path: str | Path) -> tuple[dict[int, int], str]:
    source = Path(path).read_bytes()
    words: dict[int, int] = {}
    for line_number, raw in enumerate(source.decode("utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ReferenceError(f"line {line_number}: malformed fixture record")
        address = int(parts[0], 16)
        word = int(parts[1], 16)
        if address & 3 or word > MASK32 or address in words:
            raise ReferenceError(f"line {line_number}: invalid instruction record")
        words[address] = word
    if not words:
        raise ReferenceError("empty MIPS32 fixture")
    return words, hashlib.sha256(source).hexdigest()


def _checksum(registers: list[int], memory_bytes: bytes) -> int:
    value = 2166136261
    for reg in range(1, 32):
        for byte in (registers[reg] & MASK32).to_bytes(4, "little"):
            value = ((value ^ byte) * 16777619) & MASK32
    for byte in memory_bytes:
        value = ((value ^ byte) * 16777619) & MASK32
    return value


class ReferenceMachine:
    def __init__(self, words: dict[int, int], meta: dict):
        self.words = words
        self.meta = meta
        self.regs = [0] * 32
        for slot, value in meta["initial_state"].items():
            if not slot.startswith("gpr:r"):
                raise ReferenceError(f"invalid initial state slot {slot}")
            reg = int(slot[5:])
            if not 1 <= reg <= 31:
                raise ReferenceError(f"invalid initial register {slot}")
            self.regs[reg] = value & MASK32
        self.memory = bytearray(meta["memory_size_bytes"])
        self.pc = meta["entry_address"]
        self.instructions_executed = 0
        self.delay_slots_executed = 0
        self.max_steps = meta["max_reference_steps"]

    def read(self, reg: int) -> int:
        return 0 if reg == 0 else self.regs[reg] & MASK32

    def write(self, reg: int, value: int) -> None:
        if reg != 0:
            self.regs[reg] = value & MASK32

    def _step(self) -> None:
        self.instructions_executed += 1
        if self.instructions_executed > self.max_steps:
            raise ReferenceError("reference instruction limit exceeded")

    def _bounds(self, address: int, size: int) -> None:
        if address < 0 or address > len(self.memory) or size > len(self.memory) - address:
            raise ReferenceError(f"memory fault at 0x{address:x} size={size}")

    def _execute_simple(self, address: int, word: int) -> None:
        self._step()
        if word == 0:
            return

        opcode = (word >> 26) & 0x3F
        rs = (word >> 21) & 0x1F
        rt = (word >> 16) & 0x1F
        rd = (word >> 11) & 0x1F
        shamt = (word >> 6) & 0x1F
        funct = word & 0x3F
        imm = word & 0xFFFF

        if opcode == 0:
            if shamt != 0:
                raise ReferenceError(f"0x{address:x}: unsupported shift/SPECIAL encoding")
            if funct == 0x21:
                self.write(rd, self.read(rs) + self.read(rt))
                return
            if funct == 0x2A:
                self.write(rd, 1 if _signed32(self.read(rs)) < _signed32(self.read(rt)) else 0)
                return
            if funct == 0x2B:
                self.write(rd, 1 if self.read(rs) < self.read(rt) else 0)
                return
            raise ReferenceError(f"0x{address:x}: control/unsupported SPECIAL in simple path")

        if opcode == 0x09:
            self.write(rt, self.read(rs) + _sign16(imm))
            return
        if opcode == 0x0D:
            self.write(rt, self.read(rs) | imm)
            return
        if opcode == 0x0F:
            if rs != 0:
                raise ReferenceError(f"0x{address:x}: malformed lui")
            self.write(rt, imm << 16)
            return
        if opcode in {0x23, 0x2B}:
            effective = (self.read(rs) + _sign16(imm)) & MASK32
            if effective & 3:
                raise ReferenceError(f"misaligned 32-bit memory access at 0x{effective:x}")
            self._bounds(effective, 4)
            if opcode == 0x23:
                self.write(rt, int.from_bytes(self.memory[effective:effective + 4], "little"))
            else:
                self.memory[effective:effective + 4] = self.read(rt).to_bytes(4, "little")
            return

        raise ReferenceError(f"0x{address:x}: unsupported simple opcode 0x{opcode:02x}")

    def _delay(self, address: int) -> None:
        if address not in self.words:
            raise ReferenceError(f"0x{address - 4:x}: missing delay slot")
        word = self.words[address]
        opcode = (word >> 26) & 0x3F
        funct = word & 0x3F
        if opcode in {0x02, 0x03, 0x04, 0x05} or (opcode == 0 and funct == 0x08 and word != 0):
            raise ReferenceError(f"0x{address:x}: control transfer in delay slot is outside slice")
        self._execute_simple(address, word)
        self.delay_slots_executed += 1

    def run(self) -> None:
        while self.pc != 0:
            if self.pc not in self.words:
                raise ReferenceError(f"PC left synthetic image at 0x{self.pc:x}")
            address = self.pc
            word = self.words[address]
            opcode = (word >> 26) & 0x3F
            rs = (word >> 21) & 0x1F
            rt = (word >> 16) & 0x1F
            funct = word & 0x3F
            imm = word & 0xFFFF

            is_control = opcode in {0x02, 0x03, 0x04, 0x05} or (opcode == 0 and funct == 0x08 and word != 0)
            if not is_control:
                self._execute_simple(address, word)
                self.pc = (address + 4) & MASK32
                continue

            self._step()
            delay_address = address + 4

            if opcode in {0x04, 0x05}:
                lhs = self.read(rs)
                rhs = self.read(rt)
                taken = lhs == rhs if opcode == 0x04 else lhs != rhs
                target = (address + 4 + (_sign16(imm) << 2)) & MASK32
                self._delay(delay_address)
                self.pc = target if taken else (address + 8) & MASK32
                continue

            if opcode in {0x02, 0x03}:
                target = ((address + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
                if opcode == 0x03:
                    self.write(31, address + 8)
                self._delay(delay_address)
                self.pc = target
                continue

            if opcode == 0 and funct == 0x08:
                if rt != 0 or ((word >> 11) & 0x1F) != 0 or ((word >> 6) & 0x1F) != 0:
                    raise ReferenceError(f"0x{address:x}: malformed jr")
                target = self.read(rs)
                self._delay(delay_address)
                self.pc = target
                continue

            raise ReferenceError(f"0x{address:x}: unsupported control transfer")

    def result(self, source_sha256: str) -> dict:
        obs = self.meta["observable_memory"]
        memory_bytes = bytes(self.memory[obs["address"]:obs["address"] + obs["size_bytes"]])
        state = {f"gpr:r{reg}": self.read(reg) for reg in range(1, 32)}
        return {
            "architecture": "mips32-le",
            "source_input_sha256": source_sha256,
            "return_v0": self.read(2),
            "state": state,
            "memory_address": obs["address"],
            "memory_bytes_hex": memory_bytes.hex(),
            "memory_word": int.from_bytes(memory_bytes, "little"),
            "checksum": _checksum(self.regs, memory_bytes),
            "instructions_executed": self.instructions_executed,
            "delay_slots_executed": self.delay_slots_executed,
        }


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: run_mips32_reference.py <fixture.hex> <fixture.json> <out-result.json>", file=sys.stderr)
        return 2
    try:
        words, source_hash = load_hex(argv[1])
        meta = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        machine = ReferenceMachine(words, meta)
        machine.run()
        result = machine.result(source_hash)
        Path(argv[3]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError, KeyError, json.JSONDecodeError, ReferenceError) as exc:
        print(f"OPENRECOMP_MIPS32_REFERENCE=FAIL: {exc}", file=sys.stderr)
        return 2

    print(f"MIPS32_REFERENCE_V0={result['return_v0']}")
    print(f"MIPS32_REFERENCE_CHECKSUM={result['checksum']}")
    print(f"MIPS32_REFERENCE_DELAY_SLOTS={result['delay_slots_executed']}")
    print("OPENRECOMP_MIPS32_REFERENCE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
