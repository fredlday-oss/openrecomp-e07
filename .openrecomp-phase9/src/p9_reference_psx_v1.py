#!/usr/bin/env python3
"""OpenRecomp Phase-9 independent PS-X EXE reference interpreter V1.

This module is an independently structured reference path for the bounded
Phase-9 public fixture. It does not import the OpenRecomp emitter, semantics,
memory-map, boundary or emission modules: it has its own PS-X EXE loader, its
own MIPS32 decoder/interpreter (restricted to the bounded op set), its own
RAM/address-translation model and its own platform port model implementing the
same bounded contract.

It exists to differentially verify the native path: identical observables
(exit status, register file and digest, RAM digest, typed platform event
counts and digests, access counters) with no excluded observables.

It executes only the original OpenRecomp-authored public fixture and contains
no console-derived material.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from typing import Any

REFERENCE_VERSION = "1.0.0"

MAGIC = b"PS-X EXE"
HEADER_SIZE = 0x800
RAM_BASE = 0x80000000
RAM_KSEG1_BASE = 0xA0000000
RAM_SIZE = 0x200000
IO_BASE = 0x1F801000
IO_SIZE = 0x2000

FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3

SERVICE_GPU = 1
SERVICE_INPUT = 2
SERVICE_SPU = 3
SERVICE_CDROM = 4

READ = 0
WRITE = 1

FLAG_KNOWN = 1
FLAG_BLOCKER = 2

STEP_LIMIT = 1_000_000

# Platform ports (mirrors of the bounded contract; independent constants).
GP0 = 0x1F801810
GP1 = 0x1F801814
JOY_DATA = 0x1F801040
JOY_STAT = 0x1F801044
JOY_MODE = 0x1F801048
JOY_CTRL = 0x1F80104A
JOY_BAUD = 0x1F80104E
TIMER_COUNTERS = (0x1F801100, 0x1F801110, 0x1F801120)
TIMER_MODES = (0x1F801104, 0x1F801114, 0x1F801124)
TIMER_TARGETS = (0x1F801108, 0x1F801118, 0x1F801128)
I_STAT = 0x1F801070
I_MASK = 0x1F801074
SPU_BASE = 0x1F801C00
SPU_CONTROL_BASE = 0x1F801D80
SPU_TRANSFER_BASE = 0x1F801DA0
SPU_CD_AUDIO_BASE = 0x1F801DB0
CDROM_BASE = 0x1F801800
CDROM_INDEX_STATUS = 0x1F801800
CDROM_COMMAND = 0x1F801801


class ReferenceError(RuntimeError):
    """Fail-closed reference rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass
class ReferenceRun:
    registers: list[int]
    memory: bytes
    events: dict[int, list[tuple[int, int, int, int, int, int]]]
    reads: int
    writes: int
    denied: int
    host_calls: int
    steps: int
    exit_status: int
    failed: bool
    error: str
    trace: list[int] = field(default_factory=list)

    def to_observables(self) -> dict[str, Any]:
        return {
            "exit_status": f"0x{self.exit_status & 0xFFFFFFFF:08x}",
            "registers": {f"r{index:02d}": f"0x{value & 0xFFFFFFFF:08x}" for index, value in enumerate(self.registers)},
            "registers_digest": f"0x{registers_digest(self.registers):016x}",
            "memory_digest": f"0x{fnv1a64(self.memory):016x}",
            "gpu_events": len(self.events[SERVICE_GPU]),
            "gpu_digest": f"0x{events_digest(self.events[SERVICE_GPU]):016x}",
            "input_events": len(self.events[SERVICE_INPUT]),
            "input_digest": f"0x{events_digest(self.events[SERVICE_INPUT]):016x}",
            "spu_events": len(self.events[SERVICE_SPU]),
            "spu_digest": f"0x{events_digest(self.events[SERVICE_SPU]):016x}",
            "cdrom_events": len(self.events[SERVICE_CDROM]),
            "cdrom_digest": f"0x{events_digest(self.events[SERVICE_CDROM]):016x}",
            "reads": self.reads,
            "writes": self.writes,
            "denied": self.denied,
            "host_calls": self.host_calls,
            "steps": self.steps,
            "failed": 1 if self.failed else 0,
            "error": self.error,
        }


def fnv1a64(data: bytes) -> int:
    value = FNV_OFFSET
    for byte in data:
        value ^= byte
        value = (value * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return value


def registers_digest(registers: list[int]) -> int:
    value = FNV_OFFSET
    for register in registers:
        masked = register & 0xFFFFFFFF
        for byte in range(4):
            value ^= (masked >> (8 * byte)) & 0xFF
            value = (value * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return value


def events_digest(events: list[tuple[int, int, int, int, int, int]]) -> int:
    value = FNV_OFFSET
    for service, direction, width_bits, flags, address, data in events:
        encoded = struct.pack("<BBBBII", service, direction, width_bits, flags, address & 0xFFFFFFFF, data & 0xFFFFFFFF) + b"\x00" * 4
        for byte in encoded:
            value ^= byte
            value = (value * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return value


class PsxMachine:
    """Independent bounded PS-X EXE interpreter and platform model."""

    def __init__(self, data: bytes) -> None:
        if len(data) < HEADER_SIZE or data[:8] != MAGIC:
            raise ReferenceError("BAD_CONTAINER")
        self.pc0, self.gp0, self.t_addr, self.t_size = struct.unpack_from("<IIII", data, 0x10)
        self.s_addr = struct.unpack_from("<I", data, 0x30)[0]
        self.payload = data[HEADER_SIZE : HEADER_SIZE + self.t_size]
        if len(self.payload) != self.t_size:
            raise ReferenceError("TRUNCATED_PAYLOAD")
        self.memory = bytearray(RAM_SIZE)
        self.memory[self.t_addr - RAM_BASE : self.t_addr - RAM_BASE + self.t_size] = self.payload
        self.registers = [0] * 32
        self.events: dict[int, list[tuple[int, int, int, int, int, int]]] = {
            SERVICE_GPU: [], SERVICE_INPUT: [], SERVICE_SPU: [], SERVICE_CDROM: []
        }
        self.reads = 0
        self.writes = 0
        self.denied = 0
        self.host_calls = 0
        self.ticks = 0
        self.buttons = 0
        self.failed = False
        self.error = ""
        self.steps = 0

    # -- memory -----------------------------------------------------------
    def _ram_offset(self, address: int, width: int) -> int | None:
        if RAM_BASE <= address and address + width <= RAM_BASE + RAM_SIZE:
            return address - RAM_BASE
        if RAM_KSEG1_BASE <= address and address + width <= RAM_KSEG1_BASE + RAM_SIZE:
            return address - RAM_KSEG1_BASE
        return None

    def _record(self, service: int, direction: int, width_bits: int, flags: int, address: int, value: int) -> None:
        self.events[service].append((service, direction, width_bits, flags, address, value))

    def read(self, address: int, width_bits: int) -> int:
        width = width_bits // 8
        offset = self._ram_offset(address, width)
        if offset is not None:
            self.reads += 1
            return int.from_bytes(self.memory[offset : offset + width], "little")
        if IO_BASE <= address and address + width <= IO_BASE + IO_SIZE:
            return self._platform_read(address, width_bits)
        self.denied += 1
        raise ReferenceError("MEMORY_OUT_OF_RANGE", f"0x{address:08x}")

    def write(self, address: int, width_bits: int, value: int) -> None:
        width = width_bits // 8
        offset = self._ram_offset(address, width)
        if offset is not None:
            self.writes += 1
            self.memory[offset : offset + width] = (value & ((1 << width_bits) - 1)).to_bytes(width, "little")
            return
        if IO_BASE <= address and address + width <= IO_BASE + IO_SIZE:
            self._platform_write(address, width_bits, value)
            return
        self.denied += 1
        raise ReferenceError("MEMORY_OUT_OF_RANGE", f"0x{address:08x}")

    # -- platform ---------------------------------------------------------
    @staticmethod
    def _gp0_known(command: int) -> bool:
        return (
            command in (0x00, 0x01, 0x02)
            or 0x20 <= command <= 0x3F
            or 0x40 <= command <= 0x5F
            or 0x60 <= command <= 0x7F
            or 0x80 <= command <= 0x9F
            or 0xA0 <= command <= 0xBF
            or 0xC0 <= command <= 0xDF
            or 0xE0 <= command <= 0xE7
        )

    @staticmethod
    def _gp1_known(command: int) -> bool:
        return command <= 0x08 or command == 0x10

    @staticmethod
    def _spu_known(address: int) -> bool:
        return (
            SPU_BASE <= address < SPU_BASE + 0x180
            or SPU_CONTROL_BASE <= address < SPU_CONTROL_BASE + 0x40
            or SPU_TRANSFER_BASE <= address < SPU_TRANSFER_BASE + 0x10
            or SPU_CD_AUDIO_BASE <= address < SPU_CD_AUDIO_BASE + 0x10
        )

    def _platform_read(self, address: int, width_bits: int) -> int:
        if address == JOY_DATA:
            self._record(SERVICE_INPUT, READ, width_bits, FLAG_KNOWN, address, self.buttons & 0xFFFF)
            return self.buttons & 0xFFFF
        if address == JOY_STAT:
            self._record(SERVICE_INPUT, READ, width_bits, FLAG_KNOWN, address, 1)
            return 1
        if address in TIMER_COUNTERS:
            value = self.ticks & 0xFFFF
            self.ticks += 1
            self._record(SERVICE_INPUT, READ, width_bits, FLAG_KNOWN, address, value)
            return value
        if address in (JOY_MODE, JOY_CTRL, JOY_BAUD) or address in TIMER_MODES or address in TIMER_TARGETS:
            self._record(SERVICE_INPUT, READ, width_bits, FLAG_KNOWN, address, 0)
            return 0
        if address in (I_STAT, I_MASK):
            self._record(SERVICE_INPUT, READ, width_bits, FLAG_BLOCKER, address, 0)
            self.denied += 1
            raise ReferenceError("UNSUPPORTED_OPERATION", f"0x{address:08x}")
        if address in (GP0, GP1):
            self._record(SERVICE_GPU, READ, width_bits, FLAG_KNOWN, address, 0)
            return 0
        if self._spu_known(address):
            self._record(SERVICE_SPU, READ, width_bits, FLAG_KNOWN, address, 0)
            return 0
        if CDROM_BASE <= address < CDROM_BASE + 4:
            self._record(SERVICE_CDROM, READ, width_bits, FLAG_KNOWN, address, 0)
            return 0
        self.denied += 1
        raise ReferenceError("UNSUPPORTED_OPERATION", f"0x{address:08x}")

    def _platform_write(self, address: int, width_bits: int, value: int) -> None:
        value &= 0xFFFFFFFF
        if address == JOY_DATA:
            self.buttons = value & 0xFFFF
            self._record(SERVICE_INPUT, WRITE, width_bits, FLAG_KNOWN, address, value)
            return
        if address in (JOY_MODE, JOY_CTRL, JOY_BAUD) or address in TIMER_MODES or address in TIMER_TARGETS:
            self._record(SERVICE_INPUT, WRITE, width_bits, FLAG_KNOWN, address, value)
            return
        if address in (I_STAT, I_MASK):
            self._record(SERVICE_INPUT, WRITE, width_bits, FLAG_BLOCKER, address, value)
            self.denied += 1
            raise ReferenceError("UNSUPPORTED_OPERATION", f"0x{address:08x}")
        if address in (GP0, GP1):
            command = (value >> 24) & 0xFF
            known = self._gp0_known(command) if address == GP0 else self._gp1_known(command)
            self._record(SERVICE_GPU, WRITE, width_bits, FLAG_KNOWN if known else FLAG_BLOCKER, address, value)
            if not known:
                self.denied += 1
                raise ReferenceError("UNSUPPORTED_OPERATION", f"0x{address:08x}")
            return
        if self._spu_known(address):
            self._record(SERVICE_SPU, WRITE, width_bits, FLAG_KNOWN, address, value)
            return
        if CDROM_BASE <= address < CDROM_BASE + 4:
            if address == CDROM_COMMAND and (value & 0xFF) > 0x1F:
                self._record(SERVICE_CDROM, WRITE, width_bits, FLAG_BLOCKER, address, value)
                self.denied += 1
                raise ReferenceError("UNSUPPORTED_OPERATION", f"0x{address:08x}")
            self._record(SERVICE_CDROM, WRITE, width_bits, FLAG_KNOWN, address, value)
            return
        self.denied += 1
        raise ReferenceError("UNSUPPORTED_OPERATION", f"0x{address:08x}")

    # -- execution --------------------------------------------------------
    def _fetch(self, pc: int) -> int:
        offset = self._ram_offset(pc, 4)
        if offset is None:
            raise ReferenceError("PC_OUTSIDE_RAM", f"0x{pc:08x}")
        return int.from_bytes(self.memory[offset : offset + 4], "little")

    def _execute(self, pc: int) -> int:
        word = self._fetch(pc)
        opcode = word >> 26
        rs = (word >> 21) & 0x1F
        rt = (word >> 16) & 0x1F
        rd = (word >> 11) & 0x1F
        shamt = (word >> 6) & 0x1F
        funct = word & 0x3F
        imm = word & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        regs = self.registers

        if word == 0:
            return pc + 4
        if opcode == 0x00:
            if funct == 0x08:  # jr
                target = regs[rs]
                return target if rs != 31 else target
            if funct == 0x21:  # addu
                regs[rd] = (regs[rs] + regs[rt]) & 0xFFFFFFFF
                return pc + 4
            raise ReferenceError("UNSUPPORTED_OP", f"0x{pc:08x} r-type {funct:#x}")
        if opcode == 0x02 or opcode == 0x03:  # j / jal
            target = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
            if opcode == 0x03:
                regs[31] = (pc + 8) & 0xFFFFFFFF
            return target
        if opcode == 0x04 or opcode == 0x05:  # beq / bne
            return pc + 4
        if opcode == 0x08:  # addi
            regs[rt] = (regs[rs] + simm) & 0xFFFFFFFF
            return pc + 4
        if opcode == 0x09:  # addiu
            regs[rt] = (regs[rs] + simm) & 0xFFFFFFFF
            return pc + 4
        if opcode == 0x0C:  # andi
            regs[rt] = regs[rs] & imm
            return pc + 4
        if opcode == 0x0D:  # ori
            regs[rt] = regs[rs] | imm
            return pc + 4
        if opcode == 0x0F:  # lui
            regs[rt] = (imm << 16) & 0xFFFFFFFF
            return pc + 4
        if opcode == 0x23:  # lw
            regs[rt] = self.read((regs[rs] + simm) & 0xFFFFFFFF, 32)
            return pc + 4
        if opcode == 0x20:  # lb
            value = self.read((regs[rs] + simm) & 0xFFFFFFFF, 8)
            regs[rt] = value - 0x100 if value & 0x80 else value
            return pc + 4
        if opcode == 0x24:  # lbu
            regs[rt] = self.read((regs[rs] + simm) & 0xFFFFFFFF, 8)
            return pc + 4
        if opcode == 0x2B:  # sw
            self.write((regs[rs] + simm) & 0xFFFFFFFF, 32, regs[rt])
            return pc + 4
        if opcode == 0x28:  # sb
            self.write((regs[rs] + simm) & 0xFFFFFFFF, 8, regs[rt] & 0xFF)
            return pc + 4
        raise ReferenceError("UNSUPPORTED_OP", f"0x{pc:08x} opcode {opcode:#x}")

    def _is_branch(self, pc: int) -> bool:
        word = self._fetch(pc)
        opcode = word >> 26
        return opcode in (0x02, 0x03, 0x04, 0x05) or (opcode == 0x00 and (word & 0x3F) == 0x08)

    def run(self) -> ReferenceRun:
        pc = self.pc0
        call_stack: list[int] = []
        while True:
            if self.steps >= STEP_LIMIT:
                raise ReferenceError("STEP_LIMIT", str(self.steps))
            self.steps += 1
            if self._is_branch(pc):
                # Execute the delay slot first, then apply the transfer.
                word = self._fetch(pc)
                opcode = word >> 26
                rs = (word >> 21) & 0x1F
                rt = (word >> 16) & 0x1F
                imm = word & 0xFFFF
                simm = imm - 0x10000 if imm & 0x8000 else imm
                self._execute(pc + 4)
                if opcode == 0x02:
                    pc = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
                elif opcode == 0x03:
                    self.registers[31] = (pc + 8) & 0xFFFFFFFF
                    call_stack.append((pc + 8) & 0xFFFFFFFF)
                    pc = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
                elif opcode == 0x04:
                    pc = ((pc + 4) + (simm << 2)) & 0xFFFFFFFF if self.registers[rs] == self.registers[rt] else (pc + 8) & 0xFFFFFFFF
                elif opcode == 0x05:
                    pc = ((pc + 4) + (simm << 2)) & 0xFFFFFFFF if self.registers[rs] != self.registers[rt] else (pc + 8) & 0xFFFFFFFF
                else:  # jr $ra models the emitter's function return
                    if rs != 31:
                        raise ReferenceError("UNSUPPORTED_INDIRECT", f"0x{pc:08x}")
                    if not call_stack:
                        break
                    pc = call_stack.pop()
                continue
            pc = self._execute(pc)
        return ReferenceRun(
            registers=list(self.registers),
            memory=bytes(self.memory),
            events=self.events,
            reads=self.reads,
            writes=self.writes,
            denied=self.denied,
            host_calls=self.host_calls,
            steps=self.steps,
            exit_status=self.registers[2] & 0xFFFFFFFF,
            failed=self.failed,
            error=self.error,
        )


def load_and_run(data: bytes) -> ReferenceRun:
    return PsxMachine(data).run()


def fixture_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
