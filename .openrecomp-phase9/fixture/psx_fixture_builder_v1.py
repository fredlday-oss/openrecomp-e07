#!/usr/bin/env python3
"""OpenRecomp-authored deterministic PS-X EXE fixture builder V1.

This module is original OpenRecomp material. It constructs bounded PS-X EXE
containers from OpenRecomp-authored MIPS32 words for testing and for the
public Phase-9 validation fixture. It contains no third-party code, no
proprietary material and no console-derived data.

The builder is deterministic: identical inputs always produce byte-identical
outputs. It never reads any external file.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Iterable, Sequence

MAGIC = b"PS-X EXE"
HEADER_SIZE = 0x800
RESERVED_SIZE = HEADER_SIZE - 0x38

DEFAULT_LOAD_ADDRESS = 0x80010000
DEFAULT_STACK_POINTER = 0x801FFFF0

# --- MIPS32 encoders (OpenRecomp-authored, restricted to the bounded ops) ----

R_TYPE_FUNCTS = {
    "sll": 0x00,
    "srl": 0x02,
    "sra": 0x03,
    "sllv": 0x04,
    "srlv": 0x06,
    "srav": 0x07,
    "jr": 0x08,
    "jalr": 0x09,
    "movz": 0x0A,
    "movn": 0x0B,
    "syscall": 0x0C,
    "break": 0x0D,
    "sync": 0x0F,
    "mfhi": 0x10,
    "mthi": 0x11,
    "mflo": 0x12,
    "mtlo": 0x13,
    "mult": 0x18,
    "multu": 0x19,
    "div": 0x1A,
    "divu": 0x1B,
    "add": 0x20,
    "addu": 0x21,
    "sub": 0x22,
    "subu": 0x23,
    "and": 0x24,
    "or": 0x25,
    "xor": 0x26,
    "nor": 0x27,
    "slt": 0x2A,
    "sltu": 0x2B,
}

I_TYPE_OPS = {
    "beq": 0x04,
    "bne": 0x05,
    "blez": 0x06,
    "bgtz": 0x07,
    "addi": 0x08,
    "addiu": 0x09,
    "slti": 0x0A,
    "sltiu": 0x0B,
    "andi": 0x0C,
    "ori": 0x0D,
    "xori": 0x0E,
    "lui": 0x0F,
    "lb": 0x20,
    "lh": 0x21,
    "lwl": 0x22,
    "lw": 0x23,
    "lbu": 0x24,
    "lhu": 0x25,
    "lwr": 0x26,
    "sb": 0x28,
    "sh": 0x29,
    "swl": 0x2A,
    "sw": 0x2B,
    "swr": 0x2E,
    "cache": 0x2F,
}

J_TYPE_OPS = {"j": 0x02, "jal": 0x03}


def _mask(value: int, bits: int) -> int:
    return value & ((1 << bits) - 1)


def r_type(funct: str, rs: int = 0, rt: int = 0, rd: int = 0, shamt: int = 0) -> int:
    return (
        (_mask(rs, 5) << 21)
        | (_mask(rt, 5) << 16)
        | (_mask(rd, 5) << 11)
        | (_mask(shamt, 5) << 6)
        | R_TYPE_FUNCTS[funct]
    )


def i_type(op: str, rs: int = 0, rt: int = 0, imm: int = 0) -> int:
    return (
        (I_TYPE_OPS[op] << 26)
        | (_mask(rs, 5) << 21)
        | (_mask(rt, 5) << 16)
        | _mask(imm, 16)
    )


def j_type(op: str, target: int) -> int:
    return (J_TYPE_OPS[op] << 26) | (_mask(target >> 2, 26))


def nop() -> int:
    return 0


def syscall(code: int = 0) -> int:
    return r_type("syscall", shamt=0) | (_mask(code, 20) << 6)


def break_(code: int = 0) -> int:
    return r_type("break", shamt=0) | (_mask(code, 20) << 6)


@dataclass(frozen=True)
class PsxExeSpec:
    """Deterministic PS-X EXE container specification."""

    words: tuple[int, ...]
    load_address: int = DEFAULT_LOAD_ADDRESS
    entry_index: int = 0
    gp: int = 0
    stack_pointer: int = DEFAULT_STACK_POINTER
    stack_size: int = 0
    bss_address: int = 0
    bss_size: int = 0
    reserved: bytes = field(default=b"", repr=False)

    def payload(self) -> bytes:
        return b"".join(struct.pack("<I", word & 0xFFFFFFFF) for word in self.words)

    def entry_address(self) -> int:
        return self.load_address + 4 * self.entry_index


def build(spec: PsxExeSpec) -> bytes:
    """Build one PS-X EXE byte string from an OpenRecomp-authored spec."""
    if not spec.words:
        raise ValueError("fixture spec requires at least one word")
    if not 0 <= spec.entry_index < len(spec.words):
        raise ValueError("entry_index outside the word list")
    if len(spec.reserved) > RESERVED_SIZE:
        raise ValueError("reserved bytes exceed the header reserved area")
    header = bytearray(HEADER_SIZE)
    header[0:8] = MAGIC
    struct.pack_into("<I", header, 0x08, 0)
    struct.pack_into("<I", header, 0x0C, 0)
    struct.pack_into("<I", header, 0x10, spec.entry_address())
    struct.pack_into("<I", header, 0x14, spec.gp)
    struct.pack_into("<I", header, 0x18, spec.load_address)
    struct.pack_into("<I", header, 0x1C, len(spec.words) * 4)
    struct.pack_into("<I", header, 0x20, 0)
    struct.pack_into("<I", header, 0x24, 0)
    struct.pack_into("<I", header, 0x28, spec.bss_address)
    struct.pack_into("<I", header, 0x2C, spec.bss_size)
    struct.pack_into("<I", header, 0x30, spec.stack_pointer)
    struct.pack_into("<I", header, 0x34, spec.stack_size)
    header[0x38 : 0x38 + len(spec.reserved)] = spec.reserved
    return bytes(header) + spec.payload()


def assemble_spec(
    words: Sequence[int],
    *,
    load_address: int = DEFAULT_LOAD_ADDRESS,
    entry_index: int = 0,
    gp: int = 0,
    stack_pointer: int = DEFAULT_STACK_POINTER,
    stack_size: int = 0,
    bss_address: int = 0,
    bss_size: int = 0,
    reserved: bytes = b"",
) -> PsxExeSpec:
    return PsxExeSpec(
        words=tuple(words),
        load_address=load_address,
        entry_index=entry_index,
        gp=gp,
        stack_pointer=stack_pointer,
        stack_size=stack_size,
        bss_address=bss_address,
        bss_size=bss_size,
        reserved=reserved,
    )


def build_from_words(words: Iterable[int], **kwargs) -> bytes:
    return build(assemble_spec(list(words), **kwargs))
