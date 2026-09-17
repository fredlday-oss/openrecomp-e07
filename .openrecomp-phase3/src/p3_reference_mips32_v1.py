#!/usr/bin/env python3
"""OpenRecomp Phase-3 independent MIPS32 reference execution V1 (P3-09).

A deliberately independent implementation of the audited CoreMark MIPS32
program, written separately from the P3-07 host emitter and from the P3-04
semantics overlay:

* its own minimal little-endian ELF32 loader (program headers, `PT_LOAD`
  segments, flat 64 KiB window, region permissions);
* its own instruction decoder working directly on raw 32-bit words (no reuse
  of `adapters.mips32`, `p3_decode_mips32_v1` or `p3_semantics_mips32_v1`);
* exact MIPS32 integer semantics for the audited op set with true delay-slot
  behaviour, HI/LO state, region-checked little-endian byte/half/word memory
  access and the two documented MMIO windows (deterministic UART byte sink and
  exit status word);
* the same documented observable contract as the P3-08 native runtime: exit
  status, executed steps, final PC/HI/LO, the UART byte stream and an FNV-1a 64
  digest over the flat image bytes, the 32 registers little-endian, HI, LO, PC,
  steps, exit status, UART length and the UART bytes, in that order;
* the same deterministic fail-closed messages for the audited exceptional
  states (divide by zero, taken trap with the encoded code preserved, unaligned
  indirect target, out-of-image or non-writable memory access, PC outside the
  emitted image, step limit exceeded).

It is OpenRecomp-original, standard-library only, and contains no console
assets, proprietary data or copied tables.
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from typing import Any, Callable

REFERENCE_VERSION = "1.0.0"
MASK32 = 0xFFFFFFFF
IMAGE_WINDOW = 0x10000
UART_ADDR = 0x10000000
EXIT_ADDR = 0x10000008
UART_CAPACITY = 1 << 20
DEFAULT_MAX_STEPS = 400000000
ENTRY = 0x4650
TEXT_START = 0x1000
TEXT_END = 0x467C

FAIL_PC_OUTSIDE = "pc outside the emitted image"
FAIL_MEMORY_OUT_OF_RANGE = "MEMORY_OUT_OF_RANGE"
FAIL_DIVIDE_BY_ZERO = "divide by zero"
FAIL_UNALIGNED_JUMP = "unaligned indirect jump target"
FAIL_UNALIGNED_CALL = "unaligned indirect call target"
FAIL_STEP_LIMIT = "step limit exceeded"


class ReferenceError(ValueError):
    """Fail-closed reference rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class LoadedImage:
    data: bytes
    regions: tuple[tuple[int, int, str], ...]
    entry: int

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def _fnv1a64(hash_value: int, data: bytes) -> int:
    for byte in data:
        hash_value ^= byte
        hash_value = (hash_value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return hash_value


def _fnv1a64_u32(hash_value: int, value: int) -> int:
    return _fnv1a64(hash_value, struct.pack("<I", value & MASK32))


def hash_state(image: bytes, registers: list[int], hi: int, lo: int, pc: int,
               steps: int, exit_status: int, uart: bytes) -> int:
    """The documented FNV-1a 64 observable digest (P3-07/P3-08 contract)."""
    hash_value = 0xCBF29CE484222325
    hash_value = _fnv1a64(hash_value, image)
    for value in registers:
        hash_value = _fnv1a64_u32(hash_value, value)
    hash_value = _fnv1a64_u32(hash_value, hi)
    hash_value = _fnv1a64_u32(hash_value, lo)
    hash_value = _fnv1a64_u32(hash_value, pc)
    hash_value = _fnv1a64_u32(hash_value, steps & MASK32)
    hash_value = _fnv1a64_u32(hash_value, exit_status)
    hash_value = _fnv1a64_u32(hash_value, len(uart))
    hash_value = _fnv1a64(hash_value, uart)
    return hash_value


def load_elf_flat(data: bytes) -> LoadedImage:
    """Minimal independent little-endian ELF32 loader into a flat image."""
    if len(data) < 52 or data[:4] != b"\x7fELF":
        raise ReferenceError("INVALID_ELF_MAGIC")
    if data[4] != 1:
        raise ReferenceError("UNSUPPORTED_CLASS", str(data[4]))
    if data[5] != 1:
        raise ReferenceError("UNSUPPORTED_ENDIANNESS", str(data[5]))
    (e_type, e_machine, e_version, e_entry, e_phoff, _e_shoff, _e_flags,
     e_ehsize, e_phentsize, e_phnum, _e_shentsize, _e_shnum,
     _e_shstrndx) = struct.unpack_from("<HHIIIIIHHHHHH", data, 0x10)
    if e_version != 1 or e_ehsize != 52:
        raise ReferenceError("UNSUPPORTED_HEADER")
    if e_type != 2 or e_machine != 8:
        raise ReferenceError("UNSUPPORTED_MACHINE", f"type={e_type} machine={e_machine}")
    if e_phentsize != 32 or e_phnum == 0:
        raise ReferenceError("MALFORMED_PROGRAM_TABLE")
    if e_phoff + e_phnum * e_phentsize > len(data):
        raise ReferenceError("PROGRAM_TABLE_OUT_OF_BOUNDS")
    segments = []
    for index in range(e_phnum):
        (p_type, p_offset, p_vaddr, _p_paddr, p_filesz, p_memsz, p_flags,
         _p_align) = struct.unpack_from("<IIIIIIII", data, e_phoff + index * e_phentsize)
        if p_type != 1 or p_memsz == 0:
            continue
        if p_filesz > p_memsz:
            raise ReferenceError("INVALID_SEGMENT")
        if p_offset + p_filesz > len(data):
            raise ReferenceError("SEGMENT_OUT_OF_BOUNDS")
        if p_vaddr + p_memsz > IMAGE_WINDOW:
            raise ReferenceError("SEGMENT_OUTSIDE_WINDOW", hex(p_vaddr))
        segments.append((p_vaddr, p_offset, p_filesz, p_memsz, p_flags))
    if not segments:
        raise ReferenceError("NO_LOAD_SEGMENTS")
    segments.sort(key=lambda item: item[0])
    for first, second in zip(segments, segments[1:]):
        if first[0] + first[3] > second[0]:
            raise ReferenceError("OVERLAPPING_SEGMENTS")
    image = bytearray(IMAGE_WINDOW)
    regions = []
    for vaddr, offset, filesz, memsz, flags in segments:
        image[vaddr:vaddr + filesz] = data[offset:offset + filesz]
        permissions = ("r" if flags & 4 else "-") + ("w" if flags & 2 else "-") \
            + ("x" if flags & 1 else "-")
        regions.append((vaddr, vaddr + memsz, permissions))
    return LoadedImage(bytes(image), tuple(regions), e_entry)


# --- decoder ---------------------------------------------------------------
K_INVALID = 0
K_NOP = 1
K_LUI = 2
K_ADDIU = 3
K_ORI = 4
K_ANDI = 5
K_XORI = 6
K_SLTI = 7
K_SLTIU = 8
K_ADDU = 9
K_SUBU = 10
K_AND = 11
K_OR = 12
K_XOR = 13
K_NOR = 14
K_SLT = 15
K_SLTU = 16
K_SLL = 17
K_SRL = 18
K_SRA = 19
K_LB = 20
K_LBU = 21
K_LH = 22
K_LHU = 23
K_LW = 24
K_SB = 25
K_SH = 26
K_SW = 27
K_SWL = 28
K_SWR = 29
K_BEQ = 30
K_BNE = 31
K_BLEZ = 32
K_BGTZ = 33
K_BLTZ = 34
K_BGEZ = 35
K_J = 36
K_JAL = 37
K_JR = 38
K_MULTU = 39
K_MFHI = 40
K_MFLO = 41
K_MUL = 42
K_MOVZ = 43
K_MOVN = 44
K_DIVU = 45
K_TEQ = 46
K_JALR = 47

CONTROL_KINDS = frozenset({
    K_BEQ, K_BNE, K_BLEZ, K_BGTZ, K_BLTZ, K_BGEZ, K_J, K_JAL, K_JR, K_JALR,
    K_TEQ,
})

OP_NAMES = {
    K_NOP: "nop", K_LUI: "lui", K_ADDIU: "addiu", K_ORI: "ori",
    K_ANDI: "andi", K_XORI: "xori", K_SLTI: "slti", K_SLTIU: "sltiu",
    K_ADDU: "addu", K_SUBU: "subu", K_AND: "and", K_OR: "or", K_XOR: "xor",
    K_NOR: "nor", K_SLT: "slt", K_SLTU: "sltu", K_SLL: "sll", K_SRL: "srl",
    K_SRA: "sra", K_LB: "lb", K_LBU: "lbu", K_LH: "lh", K_LHU: "lhu",
    K_LW: "lw", K_SB: "sb", K_SH: "sh", K_SW: "sw", K_SWL: "swl",
    K_SWR: "swr", K_BEQ: "beq", K_BNE: "bne", K_BLEZ: "blez", K_BGTZ: "bgtz",
    K_BLTZ: "bltz", K_BGEZ: "bgez", K_J: "j", K_JAL: "jal", K_JR: "jr",
    K_MULTU: "multu", K_MFHI: "mfhi", K_MFLO: "mflo", K_MUL: "mul",
    K_MOVZ: "movz", K_MOVN: "movn", K_DIVU: "divu", K_TEQ: "teq",
    K_JALR: "jalr",
}


def _sign16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def _sign32(value: int) -> int:
    value &= MASK32
    return value - 0x100000000 if value & 0x80000000 else value


def decode_word(word: int, address: int) -> tuple:
    """Decode one raw little-endian word into a reference instruction record."""
    opcode = (word >> 26) & 0x3F
    rs = (word >> 21) & 0x1F
    rt = (word >> 16) & 0x1F
    rd = (word >> 11) & 0x1F
    shamt = (word >> 6) & 0x1F
    funct = word & 0x3F
    imm = word & 0xFFFF
    simm = _sign16(imm)
    if word == 0:
        return (K_NOP,)
    if opcode == 0:
        if funct == 0x00 and rs == 0:
            return (K_SLL, rt, rd, shamt)
        if funct == 0x02 and rs == 0:
            return (K_SRL, rt, rd, shamt)
        if funct == 0x03 and rs == 0:
            return (K_SRA, rt, rd, shamt)
        if funct == 0x08 and rt == 0 and rd == 0 and shamt == 0:
            return (K_JR, rs)
        if funct == 0x09 and rt == 0 and shamt == 0:
            return (K_JALR, rs, rd)
        if funct == 0x0A and shamt == 0:
            return (K_MOVZ, rs, rt, rd)
        if funct == 0x0B and shamt == 0:
            return (K_MOVN, rs, rt, rd)
        if funct == 0x10 and rs == 0 and rt == 0 and shamt == 0:
            return (K_MFHI, rd)
        if funct == 0x12 and rs == 0 and rt == 0 and shamt == 0:
            return (K_MFLO, rd)
        if funct == 0x19 and rd == 0 and shamt == 0:
            return (K_MULTU, rs, rt)
        if funct == 0x1B and rd == 0 and shamt == 0:
            return (K_DIVU, rs, rt)
        if funct == 0x21 and shamt == 0:
            return (K_ADDU, rs, rt, rd)
        if funct == 0x23 and shamt == 0:
            return (K_SUBU, rs, rt, rd)
        if funct == 0x24 and shamt == 0:
            return (K_AND, rs, rt, rd)
        if funct == 0x25 and shamt == 0:
            return (K_OR, rs, rt, rd)
        if funct == 0x26 and shamt == 0:
            return (K_XOR, rs, rt, rd)
        if funct == 0x27 and shamt == 0:
            return (K_NOR, rs, rt, rd)
        if funct == 0x2A and shamt == 0:
            return (K_SLT, rs, rt, rd)
        if funct == 0x2B and shamt == 0:
            return (K_SLTU, rs, rt, rd)
        if funct == 0x34:
            return (K_TEQ, rs, rt, (word >> 6) & 0x3FF)
        return (K_INVALID,)
    if opcode == 0x01:
        target = (address + 4 + (simm << 2)) & MASK32
        if rt == 0x00:
            return (K_BLTZ, rs, target)
        if rt == 0x01:
            return (K_BGEZ, rs, target)
        return (K_INVALID,)
    if opcode == 0x02:
        return (K_J, ((address + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2))
    if opcode == 0x03:
        return (K_JAL, ((address + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2))
    if opcode == 0x04:
        return (K_BEQ, rs, rt, (address + 4 + (simm << 2)) & MASK32)
    if opcode == 0x05:
        return (K_BNE, rs, rt, (address + 4 + (simm << 2)) & MASK32)
    if opcode == 0x06 and rt == 0:
        return (K_BLEZ, rs, (address + 4 + (simm << 2)) & MASK32)
    if opcode == 0x07 and rt == 0:
        return (K_BGTZ, rs, (address + 4 + (simm << 2)) & MASK32)
    if opcode in (0x08, 0x09):
        return (K_ADDIU, rs, rt, simm)
    if opcode == 0x0A:
        return (K_SLTI, rs, rt, simm)
    if opcode == 0x0B:
        return (K_SLTIU, rs, rt, simm)
    if opcode == 0x0C:
        return (K_ANDI, rs, rt, imm)
    if opcode == 0x0D:
        return (K_ORI, rs, rt, imm)
    if opcode == 0x0E:
        return (K_XORI, rs, rt, imm)
    if opcode == 0x0F and rs == 0:
        return (K_LUI, rt, imm)
    if opcode == 0x1C and funct == 0x02 and shamt == 0:
        return (K_MUL, rs, rt, rd)
    if opcode == 0x20:
        return (K_LB, rs, rt, simm)
    if opcode == 0x21:
        return (K_LH, rs, rt, simm)
    if opcode == 0x23:
        return (K_LW, rs, rt, simm)
    if opcode == 0x24:
        return (K_LBU, rs, rt, simm)
    if opcode == 0x25:
        return (K_LHU, rs, rt, simm)
    if opcode == 0x28:
        return (K_SB, rs, rt, simm)
    if opcode == 0x29:
        return (K_SH, rs, rt, simm)
    if opcode == 0x2A:
        return (K_SWL, rs, rt, simm)
    if opcode == 0x2B:
        return (K_SW, rs, rt, simm)
    if opcode == 0x2E:
        return (K_SWR, rs, rt, simm)
    return (K_INVALID,)


def decode_text(image: bytes, start: int = TEXT_START, end: int = TEXT_END) -> dict[int, tuple]:
    """Decode every word of the executable region; invalid words stay absent."""
    code: dict[int, tuple] = {}
    for address in range(start, end, 4):
        word = int.from_bytes(image[address:address + 4], "little")
        record = decode_word(word, address)
        if record[0] != K_INVALID:
            code[address] = record
    return code


# --- execution -------------------------------------------------------------
@dataclass(frozen=True)
class ReferenceRun:
    observable: dict[str, str]
    image: bytes
    registers: tuple[int, ...]
    dump: bytes


def run(
    data: bytes,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
    uart_capacity: int = UART_CAPACITY,
    progress: Callable[[int], None] | None = None,
) -> ReferenceRun:
    """Execute the audited program and return the recorded result."""
    loaded = load_elf_flat(data)
    mem = bytearray(loaded.data)
    regions = loaded.regions

    def readable(address: int, size: int) -> bool:
        end = address + size
        if end > IMAGE_WINDOW or end < address:
            return False
        for start, limit, permissions in regions:
            if start <= address and end <= limit:
                return "r" in permissions
        return False

    def writable(address: int, size: int) -> bool:
        end = address + size
        if end > IMAGE_WINDOW or end < address:
            return False
        for start, limit, permissions in regions:
            if start <= address and end <= limit:
                return "w" in permissions
        return False

    code = decode_text(bytes(mem))
    R = [0] * 32
    hi = 0
    lo = 0
    pc = loaded.entry
    pending = 0
    has_pending = 0
    steps = 0
    uart = bytearray()
    exit_status = 0
    exited = 0
    failed = 0
    failure = ""

    while not exited and not failed and steps < max_steps:
        steps += 1
        if pc & 3 or not (TEXT_START <= pc < TEXT_END):
            failure = FAIL_PC_OUTSIDE
            failed = 1
            break
        record = code.get(pc)
        if record is None:
            failure = FAIL_PC_OUTSIDE
            failed = 1
            break
        kind = record[0]
        if kind == K_NOP:
            pass
        elif kind == K_LUI:
            R[record[1]] = (record[2] << 16) & MASK32
        elif kind == K_ADDIU:
            R[record[2]] = (R[record[1]] + record[3]) & MASK32
        elif kind == K_ORI:
            R[record[2]] = R[record[1]] | record[3]
        elif kind == K_ANDI:
            R[record[2]] = R[record[1]] & record[3]
        elif kind == K_XORI:
            R[record[2]] = R[record[1]] ^ record[3]
        elif kind == K_SLTI:
            R[record[2]] = 1 if _sign32(R[record[1]]) < record[3] else 0
        elif kind == K_SLTIU:
            R[record[2]] = 1 if R[record[1]] < (record[3] & MASK32) else 0
        elif kind == K_ADDU:
            R[record[3]] = (R[record[1]] + R[record[2]]) & MASK32
        elif kind == K_SUBU:
            R[record[3]] = (R[record[1]] - R[record[2]]) & MASK32
        elif kind == K_AND:
            R[record[3]] = R[record[1]] & R[record[2]]
        elif kind == K_OR:
            R[record[3]] = R[record[1]] | R[record[2]]
        elif kind == K_XOR:
            R[record[3]] = R[record[1]] ^ R[record[2]]
        elif kind == K_NOR:
            R[record[3]] = (~(R[record[1]] | R[record[2]])) & MASK32
        elif kind == K_SLT:
            R[record[3]] = 1 if _sign32(R[record[1]]) < _sign32(R[record[2]]) else 0
        elif kind == K_SLTU:
            R[record[3]] = 1 if R[record[1]] < R[record[2]] else 0
        elif kind == K_SLL:
            R[record[2]] = (R[record[1]] << record[3]) & MASK32
        elif kind == K_SRL:
            R[record[2]] = R[record[1]] >> record[3]
        elif kind == K_SRA:
            R[record[2]] = (_sign32(R[record[1]]) >> record[3]) & MASK32
        elif kind in (K_LB, K_LBU, K_LH, K_LHU, K_LW):
            address = (R[record[1]] + record[3]) & MASK32
            size = 1 if kind in (K_LB, K_LBU) else (2 if kind in (K_LH, K_LHU) else 4)
            if not readable(address, size):
                failure = FAIL_MEMORY_OUT_OF_RANGE
                failed = 1
                break
            value = int.from_bytes(mem[address:address + size], "little")
            if kind in (K_LB, K_LH) and value & (1 << (size * 8 - 1)):
                value -= 1 << (size * 8)
            R[record[2]] = value & MASK32
        elif kind in (K_SB, K_SH, K_SW):
            address = (R[record[1]] + record[3]) & MASK32
            size = 1 if kind == K_SB else (2 if kind == K_SH else 4)
            value = R[record[2]]
            if address == UART_ADDR:
                if size != 1:
                    failure = "UART window requires a byte store"
                    failed = 1
                    break
                if len(uart) >= uart_capacity:
                    failure = "UART byte sink overflow"
                    failed = 1
                    break
                uart.append(value & 0xFF)
            elif address == EXIT_ADDR:
                if size != 4:
                    failure = "exit window requires a word store"
                    failed = 1
                    break
                if exited:
                    failure = "exit window written twice"
                    failed = 1
                    break
                exit_status = value & MASK32
                exited = 1
            elif not writable(address, size):
                failure = FAIL_MEMORY_OUT_OF_RANGE
                failed = 1
                break
            else:
                mem[address:address + size] = (value & MASK32).to_bytes(4, "little")[:size]
        elif kind in (K_SWL, K_SWR):
            address = (R[record[1]] + record[3]) & MASK32
            aligned = address & ~3
            offset = address & 3
            if not writable(aligned, 4):
                failure = FAIL_MEMORY_OUT_OF_RANGE
                failed = 1
                break
            value = R[record[2]]
            merged = bytearray(mem[aligned:aligned + 4])
            if kind == K_SWL:
                merged[offset] = (value >> 24) & 0xFF
                if offset >= 1:
                    merged[offset - 1] = (value >> 16) & 0xFF
                if offset >= 2:
                    merged[offset - 2] = (value >> 8) & 0xFF
                if offset == 3:
                    merged[offset - 3] = value & 0xFF
            else:
                merged[offset] = value & 0xFF
                if offset <= 2:
                    merged[offset + 1] = (value >> 8) & 0xFF
                if offset <= 1:
                    merged[offset + 2] = (value >> 16) & 0xFF
                if offset == 0:
                    merged[offset + 3] = (value >> 24) & 0xFF
            mem[aligned:aligned + 4] = merged
        elif kind == K_BEQ:
            pending = record[3] if R[record[1]] == R[record[2]] else (pc + 8)
            has_pending = 1
        elif kind == K_BNE:
            pending = record[3] if R[record[1]] != R[record[2]] else (pc + 8)
            has_pending = 1
        elif kind == K_BLEZ:
            pending = record[2] if _sign32(R[record[1]]) <= 0 else (pc + 8)
            has_pending = 1
        elif kind == K_BGTZ:
            pending = record[2] if _sign32(R[record[1]]) > 0 else (pc + 8)
            has_pending = 1
        elif kind == K_BLTZ:
            pending = record[2] if _sign32(R[record[1]]) < 0 else (pc + 8)
            has_pending = 1
        elif kind == K_BGEZ:
            pending = record[2] if _sign32(R[record[1]]) >= 0 else (pc + 8)
            has_pending = 1
        elif kind == K_J:
            pending = record[1]
            has_pending = 1
        elif kind == K_JAL:
            R[31] = (pc + 8) & MASK32
            pending = record[1]
            has_pending = 1
        elif kind == K_JR:
            target = R[record[1]]
            if target & 3:
                failure = FAIL_UNALIGNED_JUMP
                failed = 1
                break
            pending = target
            has_pending = 1
        elif kind == K_JALR:
            target = R[record[1]]
            if target & 3:
                failure = FAIL_UNALIGNED_CALL
                failed = 1
                break
            R[record[2]] = (pc + 8) & MASK32
            pending = target
            has_pending = 1
        elif kind == K_MULTU:
            product = R[record[1]] * R[record[2]]
            lo = product & MASK32
            hi = (product >> 32) & MASK32
        elif kind == K_MFHI:
            R[record[1]] = hi
        elif kind == K_MFLO:
            R[record[1]] = lo
        elif kind == K_MUL:
            R[record[3]] = (_sign32(R[record[1]]) * _sign32(R[record[2]])) & MASK32
        elif kind == K_MOVZ:
            if R[record[2]] == 0:
                R[record[3]] = R[record[1]]
        elif kind == K_MOVN:
            if R[record[2]] != 0:
                R[record[3]] = R[record[1]]
        elif kind == K_DIVU:
            divisor = R[record[2]]
            if divisor == 0:
                failure = FAIL_DIVIDE_BY_ZERO
                failed = 1
                break
            lo = R[record[1]] // divisor
            hi = R[record[1]] % divisor
        elif kind == K_TEQ:
            if R[record[1]] == R[record[2]]:
                failure = f"teq trap code=0x{record[3]:x}"
                failed = 1
                break
        else:
            failure = "unknown reference instruction"
            failed = 1
            break

        R[0] = 0
        if kind in CONTROL_KINDS:
            pc = (pc + 4) & MASK32
        elif has_pending:
            pc = pending
            has_pending = 0
        else:
            pc = (pc + 4) & MASK32
        if progress is not None and (steps & 0xFFFFFF) == 0:
            progress(steps)

    if not exited and not failed:
        failure = FAIL_STEP_LIMIT
        failed = 1

    image = bytes(mem)
    uart_bytes = bytes(uart)
    observable = {
        "exit_status": str(exit_status),
        "steps": str(steps),
        "pc": f"0x{pc:08x}",
        "hi": f"0x{hi:08x}",
        "lo": f"0x{lo:08x}",
        "uart_bytes": str(len(uart_bytes)),
        "uart_hex": uart_bytes.hex(),
        "state_fnv1a64": "0x%016x" % hash_state(
            image, R, hi, lo, pc, steps, exit_status, uart_bytes),
        "failed": "1" if failed else "0",
        "failure": failure,
    }
    dump = b"".join(struct.pack("<I", value) for value in R)
    return ReferenceRun(observable=observable, image=image,
                        registers=tuple(R), dump=dump)


__all__ = [
    "ENTRY",
    "FAIL_DIVIDE_BY_ZERO",
    "FAIL_MEMORY_OUT_OF_RANGE",
    "FAIL_PC_OUTSIDE",
    "FAIL_STEP_LIMIT",
    "FAIL_UNALIGNED_CALL",
    "FAIL_UNALIGNED_JUMP",
    "IMAGE_WINDOW",
    "LoadedImage",
    "OP_NAMES",
    "REFERENCE_VERSION",
    "ReferenceError",
    "ReferenceRun",
    "decode_text",
    "decode_word",
    "hash_state",
    "load_elf_flat",
    "run",
]
