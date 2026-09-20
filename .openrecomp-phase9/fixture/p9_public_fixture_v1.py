#!/usr/bin/env python3
"""OpenRecomp-authored public PS1 validation fixture V1.

This module is original OpenRecomp material: a small, deterministic PS-X EXE
program written for the bounded Phase-9 PS1 platform/runtime integration
proof. It contains no third-party code, no proprietary material and no
console-derived data.

The program is deliberately restricted to the frozen Phase-8 supported
MIPS32 op set and to direct control flow:

* direct calls and ``jr $ra`` returns only (no indirect jumps or calls);
* a delay-slot ``nop`` after every control transfer;
* loads/stores only to the bounded RAM regions and to the typed platform
  service ports (GPU GP0/GP1, controller, timer 0, SPU, CD-ROM command);
* termination by returning from the entry function to the host boundary.

The program exercises the platform service boundary as a deterministic,
observable event sequence without emulating any console hardware beyond the
bounded service contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import psx_fixture_builder_v1 as builder

PROGRAM_LOAD_ADDRESS = 0x80010000
STACK_POINTER = 0x801FFFF0
RAM_SCRATCH = 0x80030000

#: Platform service ports exercised by the fixture.
GP0 = 0x1F801810
GP1 = 0x1F801814
JOY_DATA = 0x1F801040
TIMER0_COUNTER = 0x1F801100
SPU_CNT_LOW = 0x1F801DAA
CDROM_COMMAND = 0x1F801801

ZERO, V0 = 0, 2
T0, T1, T2, T3 = 8, 9, 10, 11
SP, RA = 29, 31


class ProgramBuilder:
    """Minimal deterministic label-aware MIPS32 word builder."""

    def __init__(self, base: int = PROGRAM_LOAD_ADDRESS) -> None:
        self.base = base
        self.words: list[int] = []
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str, str, str]] = []

    def address(self, index: int | None = None) -> int:
        return self.base + 4 * (len(self.words) if index is None else index)

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"duplicate label {name}")
        self.labels[name] = len(self.words)

    def emit(self, word: int) -> None:
        self.words.append(word & 0xFFFFFFFF)

    def nop(self) -> None:
        self.emit(builder.nop())

    def branch(self, op: str, rs: int, rt: int, label: str) -> None:
        index = len(self.words)
        self.emit(builder.i_type(op, rs, rt, 0))
        self.fixups.append((index, label, "branch", op))

    def jump(self, op: str, label: str) -> None:
        index = len(self.words)
        self.emit(builder.j_type(op, 0))
        self.fixups.append((index, label, "jump", op))

    def resolve(self) -> tuple[int, ...]:
        for index, label, kind, op in self.fixups:
            if label not in self.labels:
                raise ValueError(f"unknown label {label}")
            target_index = self.labels[label]
            target = self.base + 4 * target_index
            if kind == "branch":
                offset = (target - (self.address(index) + 4)) // 4
                if not -0x8000 <= offset < 0x8000:
                    raise ValueError(f"branch out of range to {label}")
                self.words[index] = self.words[index] | (offset & 0xFFFF)
            else:
                self.words[index] = builder.j_type(op, target)
        return tuple(self.words)


def build_words() -> tuple[int, ...]:
    """Build the public fixture program words."""
    p = ProgramBuilder()
    i_type = builder.i_type
    r_type = builder.r_type

    p.label("entry")
    p.emit(i_type("lui", rt=SP, imm=0x801F))
    p.emit(i_type("ori", rt=SP, rs=SP, imm=0xFFF0))
    p.emit(i_type("addiu", rt=SP, rs=SP, imm=-32))
    p.emit(i_type("sw", rs=SP, rt=RA, imm=28))
    p.jump("jal", "work")
    p.nop()
    p.emit(i_type("lw", rs=SP, rt=RA, imm=28))
    p.emit(i_type("addiu", rt=SP, rs=SP, imm=32))
    p.emit(r_type("jr", rs=RA))
    p.nop()

    p.label("work")
    p.emit(i_type("lui", rt=T0, imm=0x1F80))
    p.emit(i_type("addiu", rt=T0, rs=T0, imm=JOY_DATA & 0xFFFF))
    p.emit(i_type("lw", rs=T0, rt=T1, imm=0))
    p.emit(i_type("andi", rt=T1, rs=T1, imm=0xFFFF))
    p.emit(i_type("lui", rt=T2, imm=RAM_SCRATCH >> 16))
    p.emit(i_type("sw", rs=T2, rt=T1, imm=0))

    p.emit(i_type("lui", rt=T0, imm=0x1F80))
    p.emit(i_type("addiu", rt=T0, rs=T0, imm=TIMER0_COUNTER & 0xFFFF))
    p.emit(i_type("lw", rs=T0, rt=T3, imm=0))
    p.emit(i_type("sw", rs=T2, rt=T3, imm=4))

    p.emit(i_type("lui", rt=T0, imm=0x1F80))
    p.emit(i_type("addiu", rt=T0, rs=T0, imm=GP0 & 0xFFFF))
    p.emit(i_type("addiu", rt=T1, rs=ZERO, imm=0x00A0))
    p.emit(i_type("sw", rs=T0, rt=T1, imm=0))
    p.emit(i_type("addiu", rt=T1, rs=ZERO, imm=0x0000))
    p.emit(i_type("sw", rs=T0, rt=T1, imm=4))

    p.emit(i_type("lui", rt=T0, imm=0x1F80))
    p.emit(i_type("addiu", rt=T0, rs=T0, imm=SPU_CNT_LOW & 0xFFFF))
    p.emit(i_type("addiu", rt=T1, rs=ZERO, imm=0x00C0))
    p.emit(i_type("sb", rs=T0, rt=T1, imm=0))

    p.emit(i_type("lui", rt=T0, imm=0x1F80))
    p.emit(i_type("addiu", rt=T0, rs=T0, imm=CDROM_COMMAND & 0xFFFF))
    p.emit(i_type("addiu", rt=T1, rs=ZERO, imm=0x0019))
    p.emit(i_type("sb", rs=T0, rt=T1, imm=0))

    p.branch("beq", ZERO, ZERO, "skip_dead")
    p.nop()
    p.emit(i_type("addiu", rt=V0, rs=ZERO, imm=0x0DE0))
    p.label("skip_dead")
    p.branch("bne", ZERO, ZERO, "skip_two")
    p.nop()
    p.emit(i_type("addiu", rt=V0, rs=ZERO, imm=1))
    p.label("skip_two")

    p.jump("jal", "helper")
    p.nop()
    p.emit(i_type("sb", rs=T2, rt=V0, imm=8))
    p.emit(r_type("jr", rs=RA))
    p.nop()

    p.label("helper")
    p.emit(i_type("addiu", rt=V0, rs=V0, imm=1))
    p.emit(r_type("jr", rs=RA))
    p.nop()

    return p.resolve()


def helper_call_index() -> int:
    """Index of the ``jal helper`` instruction in the built program."""
    words = build_words()
    helper_address = PROGRAM_LOAD_ADDRESS + 4 * (len(words) - 3)
    for index, word in enumerate(words):
        if (word >> 26) == 0x03:
            target = (word & 0x03FFFFFF) << 2
            if (target | 0x80000000) == helper_address:
                return index
    raise ValueError("helper call site not found")


def build_fixture() -> bytes:
    """Build the deterministic public PS-X EXE fixture bytes."""
    return builder.build_from_words(
        build_words(),
        load_address=PROGRAM_LOAD_ADDRESS,
        stack_pointer=STACK_POINTER,
    )


@dataclass(frozen=True)
class PublicFixture:
    label: str = "openrecomp-authored-ps1-v1"
    words: tuple[int, ...] = field(default_factory=build_words)
    load_address: int = PROGRAM_LOAD_ADDRESS
    stack_pointer: int = STACK_POINTER

    def build(self) -> bytes:
        return builder.build_from_words(
            self.words,
            load_address=self.load_address,
            stack_pointer=self.stack_pointer,
        )


PUBLIC_FIXTURE = PublicFixture()
