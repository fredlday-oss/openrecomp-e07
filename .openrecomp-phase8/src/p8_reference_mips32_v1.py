#!/usr/bin/env python3
"""OpenRecomp Phase-8 independent MIPS32 reference for the frozen real ELF.

This module is deliberately independent from the recompilation path:

* it has its own minimal ELF32 loader (it does not use `p3_elf_image_v1`);
* it has its own decoder and interpreter for the architectural semantics of
  the reachable op set (it does not use `openrecomp.host_emitter`,
  `p8_mips32_semantics_v1` or any generated host source);
* it implements the P8-05 bounded memory/runtime contract directly: the flat
  guest image with `PT_LOAD` region permissions, the write-only byte output
  window, and identical event counters (reads, writes, host calls, denied
  accesses).

The reference reports the same bounded observable record as the native
driver so the two paths can be compared field by field.
"""

from __future__ import annotations

from dataclasses import dataclass, field

REFERENCE_VERSION = "1.0.0"

OUTPUT_ADDRESS = 0x10000000
SUPPORTED_WIDTHS = (8, 16, 32)
IMAGE_LIMIT = 1 << 20
DEFAULT_MAX_STEPS = 10_000_000


class ReferenceError(RuntimeError):
    """Fail-closed reference error with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _sx(value: int, bits: int) -> int:
    mask = (1 << bits) - 1
    value &= mask
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


@dataclass(frozen=True)
class Region:
    base: int
    size: int
    permissions: str
    name: str

    def contains(self, address: int, width_bytes: int) -> bool:
        return self.base <= address and address + width_bytes <= self.base + self.size


@dataclass
class LoadedImage:
    entry: int
    image: bytearray
    regions: tuple[Region, ...]
    executable: tuple[Region, ...]

    def region_at(self, address: int, width_bytes: int) -> Region | None:
        for region in self.regions:
            if region.contains(address, width_bytes):
                return region
        return None

    def read_word(self, address: int) -> int:
        return int.from_bytes(self.image[address : address + 4], "little")

    def executable_at(self, address: int) -> bool:
        return any(region.contains(address, 4) for region in self.executable)


def load_elf32(data: bytes) -> LoadedImage:
    """Minimal independent ELF32 little-endian loader (PT_LOAD only)."""
    if len(data) < 52 or data[:4] != b"\x7fELF":
        raise ReferenceError("NOT_ELF", f"{len(data)} bytes")
    if data[4] != 1 or data[5] != 1:
        raise ReferenceError("UNSUPPORTED_CLASS_OR_ENDIANNESS", f"class={data[4]} data={data[5]}")
    e_type = _u16(data, 16)
    e_machine = _u16(data, 18)
    if e_type != 2 or e_machine != 8:
        raise ReferenceError("UNSUPPORTED_TYPE_OR_MACHINE", f"type={e_type} machine={e_machine}")
    e_entry = _u32(data, 24)
    e_phoff = _u32(data, 28)
    e_phentsize = _u16(data, 42)
    e_phnum = _u16(data, 44)
    if e_phentsize != 32:
        raise ReferenceError("BAD_PROGRAM_HEADER_SIZE", str(e_phentsize))
    if not e_phnum:
        raise ReferenceError("NO_PROGRAM_HEADERS", "")

    regions: list[Region] = []
    flat = bytearray()
    for index in range(e_phnum):
        offset = e_phoff + index * e_phentsize
        p_type = _u32(data, offset)
        if p_type != 1:
            continue
        p_offset = _u32(data, offset + 4)
        p_vaddr = _u32(data, offset + 8)
        p_filesz = _u32(data, offset + 16)
        p_memsz = _u32(data, offset + 20)
        p_flags = _u32(data, offset + 24)
        if p_filesz > p_memsz:
            raise ReferenceError("FILESZ_GT_MEMSZ", f"segment {index}")
        if p_offset + p_filesz > len(data):
            raise ReferenceError("SEGMENT_BEYOND_EOF", f"segment {index}")
        if p_vaddr + p_memsz > IMAGE_LIMIT:
            raise ReferenceError("SEGMENT_OUTSIDE_LIMIT", f"0x{p_vaddr:x}+{p_memsz}")
        if len(flat) < p_vaddr + p_memsz:
            flat.extend(b"\x00" * (p_vaddr + p_memsz - len(flat)))
        flat[p_vaddr : p_vaddr + p_filesz] = data[p_offset : p_offset + p_filesz]
        permissions = ""
        if p_flags & 4:
            permissions += "r"
        if p_flags & 2:
            permissions += "w"
        if p_flags & 1:
            permissions += "x"
        region = Region(p_vaddr, p_memsz, permissions, f"load_{len(regions)}")
        for other in regions:
            if region.base < other.base + other.size and other.base < region.base + region.size:
                raise ReferenceError("OVERLAPPING_REGIONS", f"0x{region.base:x} / 0x{other.base:x}")
        regions.append(region)

    if not regions:
        raise ReferenceError("NO_LOAD_REGIONS", "")
    executable = tuple(region for region in regions if "x" in region.permissions)
    if not executable:
        raise ReferenceError("NO_EXECUTABLE_REGION", "")
    if not any(region.contains(e_entry, 4) for region in executable):
        raise ReferenceError("ENTRY_NOT_EXECUTABLE", f"0x{e_entry:x}")
    return LoadedImage(entry=e_entry, image=flat, regions=tuple(regions), executable=executable)


@dataclass
class ReferenceRun:
    registers: tuple[int, ...]
    exit_status: int
    transcript: bytes
    memory: bytes
    reads: int
    writes: int
    host_calls: int
    denied: int
    steps: int
    halted: bool

    def to_observables(self) -> dict:
        registers_digest = 0xCBF29CE484222325
        for value in self.registers:
            value &= 0xFFFFFFFF
            for byte in range(4):
                registers_digest ^= (value >> (8 * byte)) & 0xFF
                registers_digest = (registers_digest * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        memory_digest = 0xCBF29CE484222325
        for byte in self.memory:
            memory_digest ^= byte
            memory_digest = (memory_digest * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        transcript_digest = 0xCBF29CE484222325
        for byte in self.transcript:
            transcript_digest ^= byte
            transcript_digest = (transcript_digest * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        return {
            "exit_status": f"0x{self.exit_status & 0xFFFFFFFF:08x}",
            "registers": {f"r{index:02d}": f"0x{value & 0xFFFFFFFF:08x}" for index, value in enumerate(self.registers)},
            "registers_digest": f"0x{registers_digest:016x}",
            "memory_digest": f"0x{memory_digest:016x}",
            "transcript_len": len(self.transcript),
            "transcript_digest": f"0x{transcript_digest:016x}",
            "transcript_text": self.transcript.decode("ascii", "replace"),
            "reads": self.reads,
            "writes": self.writes,
            "host_calls": self.host_calls,
            "denied": self.denied,
        }


def execute(image: LoadedImage, *, max_steps: int = DEFAULT_MAX_STEPS) -> ReferenceRun:
    """Execute the loaded image and return the bounded observable record."""
    registers = [0] * 32
    memory = bytearray(image.image)
    transcript = bytearray()
    reads = writes = host_calls = denied = 0
    pc = image.entry
    steps = 0

    def read(address: int, width_bits: int) -> int:
        nonlocal reads, denied
        if width_bits not in SUPPORTED_WIDTHS:
            denied += 1
            raise ReferenceError("MEMORY_WIDTH_UNSUPPORTED", str(width_bits))
        width_bytes = width_bits // 8
        if address == OUTPUT_ADDRESS:
            denied += 1
            raise ReferenceError("MEMORY_OUT_OF_RANGE", "output window read")
        if address + width_bytes > len(memory):
            denied += 1
            raise ReferenceError("MEMORY_OUT_OF_RANGE", f"0x{address:x}")
        reads += 1
        return int.from_bytes(memory[address : address + width_bytes], "little")

    def write(address: int, width_bits: int, value: int) -> None:
        nonlocal writes, host_calls, denied
        if width_bits not in SUPPORTED_WIDTHS:
            denied += 1
            raise ReferenceError("MEMORY_WIDTH_UNSUPPORTED", str(width_bits))
        width_bytes = width_bits // 8
        if address == OUTPUT_ADDRESS:
            if width_bits != 8:
                denied += 1
                raise ReferenceError("MEMORY_WIDTH_UNSUPPORTED", "output window store width")
            host_calls += 1
            transcript.append(value & 0xFF)
            return
        if address + width_bytes > len(memory):
            denied += 1
            raise ReferenceError("MEMORY_OUT_OF_RANGE", f"0x{address:x}")
        region = image.region_at(address, width_bytes)
        if region is None or "w" not in region.permissions:
            denied += 1
            raise ReferenceError("UNSUPPORTED_OPERATION", f"write 0x{address:x}")
        memory[address : address + width_bytes] = (value & ((1 << width_bits) - 1)).to_bytes(width_bytes, "little")
        writes += 1

    while True:
        if pc == 0:
            break
        steps += 1
        if steps > max_steps:
            raise ReferenceError("STEP_LIMIT", str(steps))
        if pc & 3 or not image.executable_at(pc):
            raise ReferenceError("PC_OUTSIDE_EXECUTABLE", f"0x{pc:x}")
        word = image.read_word(pc)
        opcode = (word >> 26) & 0x3F
        rs = (word >> 21) & 0x1F
        rt = (word >> 16) & 0x1F
        rd = (word >> 11) & 0x1F
        shamt = (word >> 6) & 0x1F
        funct = word & 0x3F
        imm = word & 0xFFFF
        simm = _sx(imm, 16)
        transfer: int | None = None
        is_transfer = False

        if word == 0:
            pass
        elif opcode == 0x09:  # addiu
            registers[rt] = (registers[rs] + simm) & 0xFFFFFFFF
        elif opcode == 0x0F:  # lui
            registers[rt] = (imm << 16) & 0xFFFFFFFF
        elif opcode == 0x0D:  # ori
            registers[rt] = (registers[rs] | imm) & 0xFFFFFFFF
        elif opcode == 0x0C:  # andi
            registers[rt] = (registers[rs] & imm) & 0xFFFFFFFF
        elif opcode == 0x04:  # beq
            is_transfer = True
            transfer = (pc + 4 + (simm << 2)) & 0xFFFFFFFF if registers[rs] == registers[rt] else None
        elif opcode == 0x05:  # bne
            is_transfer = True
            transfer = (pc + 4 + (simm << 2)) & 0xFFFFFFFF if registers[rs] != registers[rt] else None
        elif opcode == 0x02:  # j
            is_transfer = True
            transfer = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
        elif opcode == 0x03:  # jal
            registers[31] = (pc + 8) & 0xFFFFFFFF
            is_transfer = True
            transfer = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
        elif opcode == 0x20:  # lb
            registers[rt] = _sx(read((registers[rs] + simm) & 0xFFFFFFFF, 8), 8) & 0xFFFFFFFF
        elif opcode == 0x24:  # lbu
            registers[rt] = read((registers[rs] + simm) & 0xFFFFFFFF, 8)
        elif opcode == 0x23:  # lw
            registers[rt] = read((registers[rs] + simm) & 0xFFFFFFFF, 32)
        elif opcode == 0x28:  # sb
            write((registers[rs] + simm) & 0xFFFFFFFF, 8, registers[rt])
        elif opcode == 0x2B:  # sw
            write((registers[rs] + simm) & 0xFFFFFFFF, 32, registers[rt])
        elif opcode == 0 and funct == 0x21:  # addu
            registers[rd] = (registers[rs] + registers[rt]) & 0xFFFFFFFF
        elif opcode == 0 and funct == 0x25:  # or
            registers[rd] = (registers[rs] | registers[rt]) & 0xFFFFFFFF
        elif opcode == 0 and funct == 0x26:  # xor
            registers[rd] = (registers[rs] ^ registers[rt]) & 0xFFFFFFFF
        elif opcode == 0 and funct == 0x00:  # sll
            registers[rd] = (registers[rt] << shamt) & 0xFFFFFFFF
        elif opcode == 0 and funct == 0x02:  # srl
            registers[rd] = (registers[rt] & 0xFFFFFFFF) >> shamt
        elif opcode == 0 and funct == 0x03:  # sra
            registers[rd] = (_sx(registers[rt], 32) >> shamt) & 0xFFFFFFFF
        elif opcode == 0 and funct == 0x0A:  # movz
            if registers[rt] == 0:
                registers[rd] = registers[rs]
        elif opcode == 0 and funct == 0x08:  # jr
            is_transfer = True
            transfer = registers[rs] & 0xFFFFFFFF
        else:
            raise ReferenceError("UNSUPPORTED_INSTRUCTION", f"0x{pc:x} word=0x{word:08x}")

        registers[0] = 0

        if is_transfer:
            # Delay slot: execute the instruction at pc + 4, then transfer.
            delay_pc = pc + 4
            if delay_pc & 3 or not image.executable_at(delay_pc):
                raise ReferenceError("DELAY_SLOT_OUTSIDE_EXECUTABLE", f"0x{delay_pc:x}")
            delay_word = image.read_word(delay_pc)
            d_opcode = (delay_word >> 26) & 0x3F
            d_rs = (delay_word >> 21) & 0x1F
            d_rt = (delay_word >> 16) & 0x1F
            d_rd = (delay_word >> 11) & 0x1F
            d_shamt = (delay_word >> 6) & 0x1F
            d_funct = delay_word & 0x3F
            d_imm = delay_word & 0xFFFF
            d_simm = _sx(d_imm, 16)
            if delay_word == 0:
                pass
            elif d_opcode == 0x09:
                registers[d_rt] = (registers[d_rs] + d_simm) & 0xFFFFFFFF
            elif d_opcode == 0x0F:
                registers[d_rt] = (d_imm << 16) & 0xFFFFFFFF
            elif d_opcode == 0x0D:
                registers[d_rt] = (registers[d_rs] | d_imm) & 0xFFFFFFFF
            elif d_opcode == 0x0C:
                registers[d_rt] = (registers[d_rs] & d_imm) & 0xFFFFFFFF
            elif d_opcode == 0x20:
                registers[d_rt] = _sx(read((registers[d_rs] + d_simm) & 0xFFFFFFFF, 8), 8) & 0xFFFFFFFF
            elif d_opcode == 0x24:
                registers[d_rt] = read((registers[d_rs] + d_simm) & 0xFFFFFFFF, 8)
            elif d_opcode == 0x23:
                registers[d_rt] = read((registers[d_rs] + d_simm) & 0xFFFFFFFF, 32)
            elif d_opcode == 0x28:
                write((registers[d_rs] + d_simm) & 0xFFFFFFFF, 8, registers[d_rt])
            elif d_opcode == 0x2B:
                write((registers[d_rs] + d_simm) & 0xFFFFFFFF, 32, registers[d_rt])
            elif d_opcode == 0 and d_funct == 0x21:
                registers[d_rd] = (registers[d_rs] + registers[d_rt]) & 0xFFFFFFFF
            elif d_opcode == 0 and d_funct == 0x25:
                registers[d_rd] = (registers[d_rs] | registers[d_rt]) & 0xFFFFFFFF
            elif d_opcode == 0 and d_funct == 0x26:
                registers[d_rd] = (registers[d_rs] ^ registers[d_rt]) & 0xFFFFFFFF
            elif d_opcode == 0 and d_funct == 0x00:
                registers[d_rd] = (registers[d_rt] << d_shamt) & 0xFFFFFFFF
            elif d_opcode == 0 and d_funct == 0x0A:
                if registers[d_rt] == 0:
                    registers[d_rd] = registers[d_rs]
            else:
                raise ReferenceError("UNSUPPORTED_DELAY_SLOT", f"0x{delay_pc:x} word=0x{delay_word:08x}")
            registers[0] = 0
            pc = transfer if transfer is not None else delay_pc + 4
        else:
            pc = pc + 4

    halt_pc = pc
    return ReferenceRun(
        registers=tuple(registers),
        exit_status=registers[2],
        transcript=bytes(transcript),
        memory=bytes(memory),
        reads=reads,
        writes=writes,
        host_calls=host_calls,
        denied=denied,
        steps=steps,
        halted=halt_pc == 0,
    )
