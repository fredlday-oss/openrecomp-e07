#!/usr/bin/env python3
"""OpenRecomp Phase-4 independent fixture reference (P4-09).

An independently written ELF32 loader, raw-word decoder and interpreter for
the P4-07 fixture instruction set.  It shares no decoding, control-flow or
emission code with the Phase-3 emitter or the Phase-4 generated program: the
loader parses program headers directly, the decoder is written from the
MIPS32 encoding, and the executor implements the fixture's delay-slot
protocol and MMIO windows (output 0x20000000, input 0x20000004, exit
0x20000008, ticks 0x2000000c) with the declared deterministic input plan and
the one-tick-per-retired-instruction policy.

It produces the P4-01 canonical observable (transcript bytes, exit status,
steps, PC, FNV-1a 64 state digest over the contract layout) so the P4-09 gate
can compare the native generated program against this reference over the full
run.
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from typing import Any

REFERENCE_VERSION = "1.0.0"
IMAGE_WINDOW = 0x10000
ENTRY = 0x1C00
TEXT_START = 0x1000
TEXT_SIZE = 3104
OUTPUT_CAPACITY = 1 << 16
DEFAULT_MAX_STEPS = 20000000
MMIO_OUT = 0x20000000
MMIO_IN = 0x20000004
MMIO_EXIT = 0x20000008
MMIO_TICKS = 0x2000000C
REGISTER_COUNT = 32
AUX_COUNT = 2
FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
MASK32 = 0xFFFFFFFF


class ReferenceFixtureError(ValueError):
    pass


def _u32(value: int) -> int:
    return value & MASK32


def _s32(value: int) -> int:
    value &= MASK32
    return value - 0x100000000 if value & 0x80000000 else value


@dataclass(frozen=True)
class Segment:
    vaddr: int
    filesz: int
    memsz: int
    flags: int
    data: bytes

    def to_document(self) -> dict[str, Any]:
        return {"vaddr": hex(self.vaddr), "filesz": self.filesz,
                "memsz": self.memsz, "flags": self.flags}


def load_segments(data: bytes) -> tuple[tuple[Segment, ...], int]:
    """Independent ELF32 little-endian loader (program headers only)."""
    if len(data) < 52 or data[:4] != b"\x7fELF":
        raise ReferenceFixtureError("not an ELF file")
    if data[4] != 1 or data[5] != 1:
        raise ReferenceFixtureError("only ELF32 little-endian is supported")
    e_entry, e_phoff = struct.unpack_from("<II", data, 24)
    e_phentsize, e_phnum = struct.unpack_from("<HH", data, 42)
    if e_phentsize != 32 or e_phnum == 0 or e_phoff + e_phnum * 32 > len(data):
        raise ReferenceFixtureError("malformed program header table")
    segments = []
    for index in range(e_phnum):
        offset = e_phoff + index * 32
        p_type, p_offset, p_vaddr, _p_paddr, p_filesz, p_memsz, p_flags = \
            struct.unpack_from("<IIIIIII", data, offset)
        if p_type != 1:
            continue
        if p_offset + p_filesz > len(data) or p_filesz > p_memsz:
            raise ReferenceFixtureError("load segment out of bounds")
        segments.append(Segment(vaddr=p_vaddr, filesz=p_filesz, memsz=p_memsz,
                                flags=p_flags, data=data[p_offset:p_offset + p_filesz]))
    if not segments:
        raise ReferenceFixtureError("no load segments")
    return tuple(segments), e_entry


# --- independent decoder ----------------------------------------------------
K_INVALID = 0
K_NOP = 1
K_LUI = 2
K_ADDIU = 3
K_ORI = 4
K_ANDI = 5
K_SLTIU = 6
K_ADDU = 7
K_SUBU = 8
K_AND = 9
K_OR = 10
K_XOR = 11
K_SLL = 12
K_SRL = 13
K_LBU = 14
K_LW = 15
K_SB = 16
K_SW = 17
K_BEQ = 18
K_BNE = 19
K_J = 20
K_JAL = 21
K_JR = 22
K_MFHI = 23
K_MULTU = 24
K_MOVN = 25
K_MUL = 26
K_SPECIAL = 27
K_REGIMM = 28


def decode(word: int) -> tuple[int, dict[str, int]]:
    opcode = (word >> 26) & 0x3F
    rs = (word >> 21) & 31
    rt = (word >> 16) & 31
    rd = (word >> 11) & 31
    shamt = (word >> 6) & 31
    funct = word & 0x3F
    imm = word & 0xFFFF
    fields = {"rs": rs, "rt": rt, "rd": rd, "shamt": shamt, "imm": imm,
              "target": word & 0x3FFFFFF, "word": word}
    if opcode == 0 and funct == 0x00 and rs == 0 and rt == 0 and rd == 0 and shamt == 0:
        return K_NOP, fields
    if opcode == 0x0F:
        return K_LUI, fields
    if opcode == 0x09:
        return K_ADDIU, fields
    if opcode == 0x0D:
        return K_ORI, fields
    if opcode == 0x0C:
        return K_ANDI, fields
    if opcode == 0x0B:
        return K_SLTIU, fields
    if opcode == 0x24:
        return K_LBU, fields
    if opcode == 0x23:
        return K_LW, fields
    if opcode == 0x28:
        return K_SB, fields
    if opcode == 0x2B:
        return K_SW, fields
    if opcode == 0x04:
        return K_BEQ, fields
    if opcode == 0x05:
        return K_BNE, fields
    if opcode == 0x02:
        return K_J, fields
    if opcode == 0x03:
        return K_JAL, fields
    if opcode == 0x01:
        return K_REGIMM, fields
    if opcode == 0x00:
        if funct == 0x21:
            return K_ADDU, fields
        if funct == 0x23:
            return K_SUBU, fields
        if funct == 0x24:
            return K_AND, fields
        if funct == 0x25:
            return K_OR, fields
        if funct == 0x26:
            return K_XOR, fields
        if funct == 0x00:
            return K_SLL, fields
        if funct == 0x02:
            return K_SRL, fields
        if funct == 0x08:
            return K_JR, fields
        if funct == 0x10:
            return K_MFHI, fields
        if funct == 0x19:
            return K_MULTU, fields
        if funct == 0x0B:
            return K_MOVN, fields
        return K_SPECIAL, fields
    if opcode == 0x1C and funct == 0x02:
        return K_MUL, fields
    return K_INVALID, fields


class ReferenceMachine:
    """An independently implemented executor for the fixture program."""

    def __init__(
        self,
        segments: tuple[Segment, ...],
        entry: int,
        *,
        input_plan: bytes,
        max_steps: int = DEFAULT_MAX_STEPS,
        output_capacity: int = OUTPUT_CAPACITY,
    ) -> None:
        self._segments = segments
        self._entry = entry
        self._input = bytes(input_plan)
        self._input_pos = 0
        self._max_steps = max_steps
        self._output_capacity = output_capacity
        self.memory = bytearray(IMAGE_WINDOW)
        for segment in segments:
            if segment.vaddr + segment.filesz > IMAGE_WINDOW:
                raise ReferenceFixtureError("segment exceeds the image window")
            self.memory[segment.vaddr:segment.vaddr + segment.filesz] = segment.data
        self.registers = [0] * REGISTER_COUNT
        self.hi = 0
        self.lo = 0
        self.pc = entry
        self.steps = 0
        self.pending = 0
        self.has_pending = False
        self.output = bytearray()
        self.exit_status: int | None = None
        self.terminated = False
        self.failed = False
        self.failure = ""
        self.exception_sites: list[str] = []

    # -- memory --------------------------------------------------------------
    def region_for(self, address: int, size: int) -> Segment | None:
        end = address + size
        for segment in self._segments:
            if segment.vaddr <= address and end <= segment.vaddr + segment.memsz:
                return segment
        return None

    def _fail(self, reason: str) -> None:
        if not self.failed:
            self.failed = True
            self.failure = reason

    def read(self, address: int, size: int) -> int:
        segment = self.region_for(address, size)
        if segment is None or not (segment.flags & 4):
            self._fail("MEMORY_OUT_OF_RANGE")
            return 0
        value = 0
        for index in range(size):
            value |= self.memory[address + index] << (8 * index)
        return value

    def write(self, address: int, size: int, value: int) -> None:
        segment = self.region_for(address, size)
        if segment is None or not (segment.flags & 2):
            self._fail("MEMORY_OUT_OF_RANGE")
            return
        for index in range(size):
            self.memory[address + index] = (value >> (8 * index)) & 0xFF

    def set_register(self, index: int, value: int) -> None:
        if index != 0:
            self.registers[index] = _u32(value)

    # -- execution -----------------------------------------------------------
    def step(self) -> None:
        word = int.from_bytes(self.memory[self.pc:self.pc + 4], "little")
        kind, fields = decode(word)
        rs, rt, rd, imm = fields["rs"], fields["rt"], fields["rd"], fields["imm"]
        r = self.registers

        def advance() -> None:
            if self.has_pending:
                self.pc = self.pending
                self.has_pending = False
            else:
                self.pc = _u32(self.pc + 4)

        def transfer(target: int | None, taken: bool | None = None) -> None:
            if taken is None:
                self.pending = _u32(target)
            else:
                self.pending = _u32(target) if taken else _u32(self.pc + 8)
            self.has_pending = True
            self.pc = _u32(self.pc + 4)

        if kind == K_NOP:
            advance()
        elif kind == K_LUI:
            self.set_register(rt, imm << 16)
            advance()
        elif kind == K_ADDIU:
            self.set_register(rt, r[rs] + (imm - 0x10000 if imm & 0x8000 else imm))
            advance()
        elif kind == K_ORI:
            self.set_register(rt, r[rs] | imm)
            advance()
        elif kind == K_ANDI:
            self.set_register(rt, r[rs] & imm)
            advance()
        elif kind == K_SLTIU:
            self.set_register(rt, 1 if r[rs] < imm else 0)
            advance()
        elif kind == K_LBU:
            address = _u32(r[rs] + (imm - 0x10000 if imm & 0x8000 else imm))
            if address == MMIO_IN:
                if self._input_pos < len(self._input):
                    value = self._input[self._input_pos]
                    self._input_pos += 1
                else:
                    value = 0xFF
            elif address == MMIO_TICKS:
                value = self.steps & MASK32
            else:
                value = self.read(address, 1)
            self.set_register(rt, value)
            advance()
        elif kind == K_LW:
            address = _u32(r[rs] + (imm - 0x10000 if imm & 0x8000 else imm))
            if address == MMIO_TICKS:
                value = self.steps & MASK32
            else:
                value = self.read(address, 4)
            self.set_register(rt, value)
            advance()
        elif kind == K_SB:
            address = _u32(r[rs] + (imm - 0x10000 if imm & 0x8000 else imm))
            if address == MMIO_OUT:
                if len(self.output) >= self._output_capacity:
                    self._fail("output capacity exceeded")
                else:
                    self.output.append(r[rt] & 0xFF)
            else:
                self.write(address, 1, r[rt])
            advance()
        elif kind == K_SW:
            address = _u32(r[rs] + (imm - 0x10000 if imm & 0x8000 else imm))
            if address == MMIO_EXIT:
                if self.exit_status is not None:
                    self._fail("duplicate exit")
                else:
                    self.exit_status = r[rt] & MASK32
                    self.terminated = True
            else:
                self.write(address, 4, r[rt])
            advance()
        elif kind == K_BEQ:
            offset = imm - 0x10000 if imm & 0x8000 else imm
            transfer(self.pc + 4 + (offset << 2), r[rs] == r[rt])
        elif kind == K_BNE:
            offset = imm - 0x10000 if imm & 0x8000 else imm
            transfer(self.pc + 4 + (offset << 2), r[rs] != r[rt])
        elif kind == K_J:
            transfer((self.pc & 0xF0000000) | (fields["target"] << 2))
        elif kind == K_JAL:
            self.set_register(31, self.pc + 8)
            transfer((self.pc & 0xF0000000) | (fields["target"] << 2))
        elif kind == K_JR:
            target = r[rs]
            if target & 3:
                self._fail("unaligned indirect jump target")
                advance()
            else:
                transfer(target)
        elif kind == K_REGIMM:
            offset = imm - 0x10000 if imm & 0x8000 else imm
            if rt == 0x00:
                transfer(self.pc + 4 + (offset << 2), _s32(r[rs]) < 0)
            elif rt == 0x01:
                transfer(self.pc + 4 + (offset << 2), _s32(r[rs]) >= 0)
            else:
                self._fail(f"unsupported REGIMM rt=0x{rt:x}")
                advance()
        elif kind == K_ADDU:
            self.set_register(rd, r[rs] + r[rt])
            advance()
        elif kind == K_SUBU:
            self.set_register(rd, r[rs] - r[rt])
            advance()
        elif kind == K_AND:
            self.set_register(rd, r[rs] & r[rt])
            advance()
        elif kind == K_OR:
            self.set_register(rd, r[rs] | r[rt])
            advance()
        elif kind == K_XOR:
            self.set_register(rd, r[rs] ^ r[rt])
            advance()
        elif kind == K_SLL:
            self.set_register(rd, r[rt] << fields["shamt"])
            advance()
        elif kind == K_SRL:
            self.set_register(rd, r[rt] >> fields["shamt"])
            advance()
        elif kind == K_MFHI:
            self.set_register(rd, self.hi)
            advance()
        elif kind == K_MULTU:
            product = r[rs] * r[rt]
            self.lo = product & MASK32
            self.hi = (product >> 32) & MASK32
            advance()
        elif kind == K_MOVN:
            if r[rt] != 0:
                self.set_register(rd, r[rs])
            advance()
        elif kind == K_MUL:
            self.set_register(rd, _u32(_s32(r[rs]) * _s32(r[rt])))
            advance()
        elif kind == K_INVALID:
            self._fail(f"unsupported instruction 0x{word:08x} at 0x{self.pc:08x}")
            advance()
        else:
            self._fail(f"unsupported instruction 0x{word:08x} at 0x{self.pc:08x}")
            advance()

    def run(self) -> None:
        while not self.failed and not self.terminated and self.steps < self._max_steps:
            self.step()
            self.steps += 1
        if not self.failed and not self.terminated and self.steps >= self._max_steps:
            self._fail("step limit exceeded")

    # -- observable ----------------------------------------------------------
    def image_window(self) -> bytes:
        return bytes(self.memory)

    def observable_document(self) -> dict[str, Any]:
        return {
            "exit_status": None if self.exit_status is None else self.exit_status,
            "steps": self.steps,
            "pc": self.pc,
            "hi": self.hi,
            "lo": self.lo,
            "failed": self.failed,
            "failure": self.failure,
            "output_bytes": len(self.output),
            "output_sha256": hashlib.sha256(bytes(self.output)).hexdigest(),
            "state_fnv1a64": self.observable_digest(),
        }

    def observable_digest(self) -> str:
        state = FNV_OFFSET

        def mix(data: bytes) -> None:
            nonlocal state
            for byte in data:
                state ^= byte
                state = (state * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF

        def mix_u32(value: int) -> None:
            mix((value & MASK32).to_bytes(4, "little"))

        image = self.image_window()
        mix(b"OROBS1")
        mix_u32(IMAGE_WINDOW)
        mix(image)
        mix_u32(REGISTER_COUNT)
        for register in self.registers:
            mix_u32(register)
        mix_u32(AUX_COUNT)
        mix_u32(self.hi)
        mix_u32(self.lo)
        mix_u32(self.pc)
        mix((self.steps & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "little"))
        mix_u32(0xFFFFFFFF if self.exit_status is None else self.exit_status)
        mix_u32(len(self.output))
        mix(bytes(self.output))
        return f"0x{state:016x}"


def reference_document(segments: tuple[Segment, ...], entry: int) -> dict[str, Any]:
    return {
        "reference_version": REFERENCE_VERSION,
        "entry": hex(entry),
        "segments": [segment.to_document() for segment in segments],
        "text": {"start": hex(TEXT_START), "size": TEXT_SIZE},
    }
