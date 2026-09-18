#!/usr/bin/env python3
"""Phase-6 independent MMC1 reference driver (P6-09).

Independently structured execution path for the public MMC1 proof fixture:

* the CPU core is the frozen, independently written `ReferenceNES6502` oracle
  (`tools/nes6502_reference_v1.py`, read-only) bridged to the platform bus
  through the frozen `NesReference6502` seam;
* the MMC1 cartridge composes the independently structured P6-02 .. P6-05
  reference models (explicit received-bit shift list, modulo banking, direct
  address-bit nametable mapping), not the implementation-side models that the
  native support mirrors;
* the CPU bus, PPU register/memory surface, APU latches, OAM DMA, controller
  protocol and frame/vblank/NMI scheduling are implemented here from the same
  audited documented contract as the generated C runtime support, with an
  independent structure and its own base-cost schedule;
* the declared page-wrap run-exit site is intercepted with the same
  service-binding semantics as the emitted native program: the original jump
  is never taken and the recorded argument is the site address.

The driver emits the exact canonical observable layout of the native support
(field order and frame transcript), so the gate can require byte-for-byte
equivalence for the bounded public MMC1 proof.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any, Iterable

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase6" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from nes6502_reference_v1 import NES6502State  # noqa: E402
from nes_headless_v1 import NesReference6502  # noqa: E402
import p6_mapper1_chr_reference_v1 as chr_reference  # noqa: E402
import p6_mapper1_prg_reference_v1 as prg_reference  # noqa: E402
import p6_mmc1_serial_reference_v1 as serial_reference  # noqa: E402

FRAME_UNITS = 29780
VBLANK_UNITS = 2273
NMI_ENTRY_COST = 7
FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211

CPU_IMAGE_SIZE = 0x10000
PRG_BANK_BYTES = 0x4000
PRG_WINDOW_BASE = 0x8000
FIXED_WINDOW_BASE = 0xC000
PRG_RAM_BASE = 0x6000
CHR_WINDOW_END = 0x1FFF

MAX_STEPS = 4000000
EXIT_SITE = 0xC089
EXIT_SERVICE = "p6.exit"
GUEST_CODE_FLOOR = 0xC000

# Independent base-cost schedule covering exactly the documented opcode set of
# the public MMC1 proof fixture. The P6-09 gate cross-checks every entry
# against the frozen audited cost table before any equivalence run.
REFERENCE_COSTS: dict[int, int] = {
    0x09: 2,   # ora #
    0x10: 2,   # bpl
    0x18: 2,   # clc
    0x20: 6,   # jsr
    0x29: 2,   # and #
    0x2C: 4,   # bit abs
    0x2E: 6,   # rol abs
    0x40: 6,   # rti
    0x48: 3,   # pha
    0x49: 2,   # eor #
    0x4A: 2,   # lsr a
    0x4C: 3,   # jmp abs
    0x60: 6,   # rts
    0x68: 3,   # pla
    0x6C: 5,   # jmp (ind)
    0x6D: 4,   # adc abs
    0x78: 2,   # sei
    0x8A: 2,   # txa
    0x8D: 4,   # sta abs
    0x98: 2,   # tya
    0x9A: 2,   # txs
    0x9D: 5,   # sta abs,x
    0xA0: 2,   # ldy #
    0xA2: 2,   # ldx #
    0xA8: 2,   # tay
    0xA9: 2,   # lda #
    0xAA: 2,   # tax
    0xAD: 4,   # lda abs
    0xAE: 4,   # ldx abs
    0xB0: 2,   # bcs
    0xBD: 4,   # lda abs,x
    0xC0: 2,   # cpy #
    0xC8: 2,   # iny
    0xC9: 2,   # cmp #
    0xCA: 2,   # dex
    0xD0: 2,   # bne
    0xD8: 2,   # cld
    0xE0: 2,   # cpx #
    0xE8: 2,   # inx
    0xEE: 6,   # inc abs
}


class P6ReferenceError(ValueError):
    """Fail-closed Phase-6 reference error."""


def fnv1a64(state: int, data: bytes) -> int:
    for value in data:
        state ^= value
        state = (state * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return state


def fnv1a64_byte(state: int, value: int) -> int:
    state ^= value & 0xFF
    return (state * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF


class P6Mmc1ReferencePlatform:
    """Independent MMC1 CPU bus plus CPU-facing PPU/APU/controller surface."""

    def __init__(self, rom: bytes, inventory: dict[str, Any]) -> None:
        if not isinstance(inventory, dict):
            raise P6ReferenceError("inventory must be a document")
        phase6 = inventory.get("phase6") or {}
        if phase6.get("status") != "SUPPORTED_MMC1":
            raise P6ReferenceError(
                f"cartridge status {phase6.get('status')!r} is not supported")
        if inventory.get("chr_is_ram"):
            raise P6ReferenceError("CHR-RAM cartridges are not supported")
        if inventory.get("battery") or int(inventory.get("prg_ram_bytes") or 0) > 0:
            raise P6ReferenceError(
                "declared PRG-RAM/battery is an unsupported MMC1 variant")
        trainer = int(inventory.get("trainer_bytes") or 0)
        prg_bytes = int(inventory["prg_bytes"])
        chr_bytes = int(inventory["chr_bytes"])
        base = 16 + trainer
        self.prg = bytes(rom[base:base + prg_bytes])
        self.chr = bytes(rom[base + prg_bytes:base + prg_bytes + chr_bytes])
        if len(self.prg) != prg_bytes or len(self.chr) != chr_bytes:
            raise P6ReferenceError("cartridge segments are truncated")
        self.prg_banks_16k = int(phase6["prg_banks_16k"])
        self.chr_banks_8k = int(phase6["chr_banks_8k"])

        self.serial = serial_reference.MMC1SerialReference()
        self.clock = 0
        self.serial_writes = 0
        self.suppressed_writes = 0

        self.ram = bytearray(0x800)
        self.vram = bytearray(0x800)
        self.palette = bytearray(0x20)
        self.oam = bytearray(0x100)
        self.apu = bytearray(0x18)
        self.apu_status = 0
        self.controllers = [0, 0]
        self.strobe = 0
        self.shift = 0

        self.ctrl = 0
        self.mask = 0
        self.status = 0
        self.oam_addr = 0
        self.addr = 0
        self.t = 0
        self.w = 0
        self.scroll_x = 0
        self.scroll_y = 0
        self.buffer = 0
        self.open_bus = 0

    # -- controller --------------------------------------------------------
    def set_controller(self, port: int, state: int) -> None:
        if port != 0:
            raise P6ReferenceError("only controller port 0 is supported")
        if isinstance(state, bool) or not isinstance(state, int) or not 0 <= state <= 0xFF:
            raise P6ReferenceError("controller state must be an 8-bit integer")
        self.controllers[0] = state

    def controller_read(self) -> int:
        if self.strobe:
            return 0x40 | (self.controllers[0] & 0x01)
        bit = 1
        if self.shift < 8:
            bit = (self.controllers[0] >> self.shift) & 0x01
        self.shift = (self.shift + 1) & 0xFF
        return 0x40 | bit

    # -- PPU ---------------------------------------------------------------
    def _increment(self) -> int:
        return 32 if (self.ctrl & 0x04) else 1

    def _palette_index(self, address: int) -> int:
        index = (address - 0x3F00) & 0x1F
        if index in (0x10, 0x14, 0x18, 0x1C):
            index -= 0x10
        return index

    def ppu_memory_read(self, address: int) -> int:
        address &= 0x3FFF
        if address < 0x2000:
            return self.chr[self._chr_offset(address)]
        if address < 0x3F00:
            return self.vram[self._nametable_offset(address)]
        value = self.palette[self._palette_index(address)]
        if self.mask & 0x01:
            value &= 0x30
        return value

    def ppu_memory_write(self, address: int, value: int) -> None:
        address &= 0x3FFF
        value &= 0xFF
        if address < 0x2000:
            raise P6ReferenceError("CHR ROM write fails closed")
        if address < 0x3F00:
            self.vram[self._nametable_offset(address)] = value
        else:
            self.palette[self._palette_index(address)] = value & 0x3F

    def _chr_offset(self, address: int) -> int:
        return chr_reference.reference_chr_offset(
            self.serial.reg[0], self.serial.reg[1], self.serial.reg[2],
            self.chr_banks_8k, address)

    def _nametable_offset(self, address: int) -> int:
        return chr_reference.reference_nametable_offset(self.serial.reg[0],
                                                        address)

    def ppu_register_read(self, register: int) -> int:
        if register == 2:
            value = (self.status & 0xE0) | (self.open_bus & 0x1F)
            self.status &= ~0x80
            self.w = 0
            return value
        if register == 4:
            return self.oam[self.oam_addr]
        if register == 7:
            address = self.addr
            if address >= 0x3F00:
                value = self.ppu_memory_read(address)
                self.buffer = self.ppu_memory_read((address - 0x1000) & 0x3FFF)
            else:
                value = self.buffer
                self.buffer = self.ppu_memory_read(address)
            self.addr = (address + self._increment()) & 0x3FFF
            return value
        return self.open_bus

    def ppu_register_write(self, register: int, value: int) -> None:
        value &= 0xFF
        self.open_bus = value
        if register == 0:
            self.ctrl = value
        elif register == 1:
            self.mask = value
        elif register == 2:
            pass
        elif register == 3:
            self.oam_addr = value
        elif register == 4:
            self.oam[self.oam_addr] = value
            self.oam_addr = (self.oam_addr + 1) & 0xFF
        elif register == 5:
            if self.w == 0:
                self.scroll_x = value
                self.w = 1
            else:
                self.scroll_y = value
                self.w = 0
        elif register == 6:
            if self.w == 0:
                self.t = (self.t & 0x00FF) | ((value & 0x3F) << 8)
                self.w = 1
            else:
                self.t = (self.t & 0xFF00) | value
                self.addr = self.t & 0x3FFF
                self.w = 0
        elif register == 7:
            self.ppu_memory_write(self.addr, value)
            self.addr = (self.addr + self._increment()) & 0x3FFF
        else:
            raise P6ReferenceError(f"unknown PPU register {register}")

    # -- MMC1 --------------------------------------------------------------
    def _mmc1_cpu_read(self, address: int) -> int:
        offset = prg_reference.reference_map_offset(
            self.serial.reg[0], self.serial.reg[3], self.prg_banks_16k, address)
        if offset < 0 or offset >= len(self.prg):
            raise P6ReferenceError(
                f"PRG offset 0x{offset:x} outside the supported image")
        return self.prg[offset]

    def _mmc1_cpu_write(self, address: int, value: int) -> None:
        result = self.serial.write(address, value, self.clock)
        if result["action"] == "suppressed":
            self.suppressed_writes += 1
        else:
            self.serial_writes += 1

    def prg_window_banks(self) -> tuple[int, int]:
        return prg_reference.reference_window_banks(
            self.serial.reg[0], self.serial.reg[3], self.prg_banks_16k)

    def chr_banks(self) -> dict[str, Any]:
        return chr_reference.reference_chr_banks(
            self.serial.reg[0], self.serial.reg[1], self.serial.reg[2],
            self.chr_banks_8k)

    # -- CPU bus -----------------------------------------------------------
    def _check_address(self, address: int) -> int:
        if isinstance(address, bool) or not isinstance(address, int):
            raise P6ReferenceError("CPU address must be an integer")
        if not 0 <= address <= 0xFFFF:
            raise P6ReferenceError(f"CPU address 0x{address:x} outside 16 bits")
        return address

    def read_memory(self, address: int) -> int:
        address = self._check_address(address)
        if address < 0x2000:
            return self.ram[address & 0x07FF]
        if address < 0x4000:
            return self.ppu_register_read((address - 0x2000) & 0x07)
        if address == 0x4014:
            return 0
        if address == 0x4015:
            return self.apu_status
        if address == 0x4016:
            return self.controller_read()
        if address == 0x4017:
            return self.controller_read()
        if address < 0x4018:
            return 0
        if address < 0x4020:
            raise P6ReferenceError(
                f"read of disabled I/O register 0x{address:04x}")
        if address < 0x6000:
            raise P6ReferenceError(f"read of expansion area 0x{address:04x}")
        if address < 0x8000:
            raise P6ReferenceError(
                f"read of disabled PRG-RAM window 0x{address:04x}")
        return self._mmc1_cpu_read(address)

    def _oam_dma(self, page: int) -> None:
        base = (page & 0xFF) << 8
        for offset in range(0x100):
            self.oam[offset] = self.read_memory(base + offset)

    def write_memory(self, address: int, value: int) -> None:
        address = self._check_address(address)
        if isinstance(value, bool) or not isinstance(value, int):
            raise P6ReferenceError("CPU write value must be an integer")
        value &= 0xFF
        if address < 0x2000:
            self.ram[address & 0x07FF] = value
        elif address < 0x4000:
            self.ppu_register_write((address - 0x2000) & 0x07, value)
        elif address <= 0x4013:
            self.apu[address - 0x4000] = value
        elif address == 0x4014:
            self._oam_dma(value)
        elif address == 0x4015:
            self.apu_status = value & 0x1F
        elif address == 0x4016:
            self.strobe = value & 0x01
            self.shift = 0
        elif address == 0x4017:
            self.apu[0x17] = value
        elif address < 0x4018:
            raise P6ReferenceError(
                f"write to disabled I/O register 0x{address:04x}")
        elif address < 0x4020:
            raise P6ReferenceError(f"write to expansion area 0x{address:04x}")
        elif address < 0x8000:
            raise P6ReferenceError(
                f"write to disabled PRG-RAM window 0x{address:04x}")
        else:
            self._mmc1_cpu_write(address, value)

    # -- observable state --------------------------------------------------
    def mapper_state(self) -> dict[str, Any]:
        snapshot = self.serial.snapshot()
        low, high = self.prg_window_banks()
        chr_layout = self.chr_banks()
        return {
            "registers": dict(snapshot["registers"]),
            "shift": snapshot["shift"],
            "count": snapshot["count"],
            "last_write_cycle": snapshot["last_write_cycle"],
            "serial_writes": self.serial_writes,
            "suppressed_writes": self.suppressed_writes,
            "cycles": self.clock,
            "prg_window_8000_bank": low,
            "prg_window_c000_bank": high,
            "chr_mode": self.serial.reg[0] // 16,
            "chr_bank_0": chr_layout["bank_0"],
            "chr_bank_1": chr_layout["bank_1"],
            "mirroring": self.serial.reg[0] % 4,
            "prg_ram_enabled": 0,
        }


def build_cpu_image(platform: P6Mmc1ReferencePlatform) -> bytes:
    """Power-on MMC1 CPU image: fixed last bank at $C000, bank 0 at $8000."""
    banks = platform.prg_banks_16k
    if len(platform.prg) != banks * PRG_BANK_BYTES:
        raise P6ReferenceError("PRG size does not match the bank count")
    image = bytearray(CPU_IMAGE_SIZE)
    image[FIXED_WINDOW_BASE:CPU_IMAGE_SIZE] = platform.prg[
        (banks - 1) * PRG_BANK_BYTES:]
    image[PRG_WINDOW_BASE:FIXED_WINDOW_BASE] = platform.prg[:PRG_BANK_BYTES]
    return bytes(image)


def run_reference(rom: bytes, inventory: dict[str, Any],
                  plan: Iterable[int], *, exit_site: int = EXIT_SITE,
                  max_steps: int = MAX_STEPS, frame_units: int = FRAME_UNITS,
                  vblank_units: int = VBLANK_UNITS,
                  nmi_entry_cost: int = NMI_ENTRY_COST) -> dict[str, Any]:
    plan = tuple(plan)
    if not plan:
        raise P6ReferenceError("input plan is empty")
    values = []
    for item in plan:
        if isinstance(item, bool) or not isinstance(item, int) or not 0 <= item <= 0xFF:
            raise P6ReferenceError("input plan values must be 8-bit integers")
        values.append(item)
    plan = tuple(values)
    if max_steps <= 0:
        raise P6ReferenceError("max_steps must be positive")

    platform = P6Mmc1ReferencePlatform(rom, inventory)
    image = build_cpu_image(platform)
    reset = int(inventory["vectors"]["reset"])
    if not FIXED_WINDOW_BASE <= reset <= 0xFFFF:
        raise P6ReferenceError(
            f"reset vector 0x{reset:04x} outside the fixed bank")
    cpu = NesReference6502(platform, image, NES6502State(pc=reset, sp=0xFD, p=0))
    state = cpu.state

    clock = 0
    next_frame_start = 0
    next_vblank_end = vblank_units
    pending_nmi = 0
    nmi_delivered = 0
    frame_index = 0
    frames: list[dict[str, Any]] = []
    steps = 0
    exit_requested = False
    exit_argument = 0
    services: list[dict[str, Any]] = []
    executed: set[int] = set()

    def frame_start(at: int) -> None:
        nonlocal pending_nmi, frame_index, next_frame_start, next_vblank_end
        input_value = plan[min(frame_index, len(plan) - 1)]
        platform.set_controller(0, input_value)
        platform.status |= 0x80
        if platform.ctrl & 0x80:
            pending_nmi += 1
        vram = bytes(platform.vram)
        tile = fnv1a64(FNV_OFFSET, vram[0:960])
        ppu_digest = fnv1a64(FNV_OFFSET, vram)
        ppu_digest = fnv1a64(ppu_digest, bytes(platform.palette))
        ppu_digest = fnv1a64(ppu_digest, bytes(platform.oam))
        frames.append({
            "index": frame_index,
            "input": input_value,
            "tile": tile,
            "ppu": ppu_digest,
            "clock": at,
        })
        frame_index += 1
        next_frame_start += frame_units
        next_vblank_end = at + vblank_units

    def advance(cost: int) -> None:
        nonlocal clock, next_vblank_end
        target = clock + cost
        while next_frame_start <= target:
            frame_start(next_frame_start)
        while next_vblank_end <= target:
            platform.status &= ~0x80
            next_vblank_end += frame_units
        clock = target

    while steps < max_steps:
        if pending_nmi > 0:
            pending_nmi -= 1
            nmi_delivered += 1
            platform.clock = clock
            cpu.nmi()
            clock += nmi_entry_cost
        pc = state.pc & 0xFFFF
        executed.add(pc)
        opcode = image[pc]
        cost = REFERENCE_COSTS.get(opcode)
        if cost is None:
            raise P6ReferenceError(
                f"opcode 0x{opcode:02x} at 0x{pc:04x} has no reference cost")
        if pc == exit_site:
            services.append({"service": EXIT_SERVICE, "argc": 1, "args": [pc]})
            exit_requested = True
            exit_argument = pc
            platform.clock = clock
            advance(cost)
            steps += 1
            break
        platform.clock = clock
        cpu.step()
        advance(cost)
        steps += 1
        if state.halted:
            raise P6ReferenceError("reference CPU halted unexpectedly")
    else:
        raise P6ReferenceError("reference step limit reached")

    if not exit_requested:
        raise P6ReferenceError("reference did not reach the declared exit site")
    outside = sorted(address for address in executed
                     if not GUEST_CODE_FLOOR <= address <= 0xFFFF)
    if outside:
        raise P6ReferenceError(
            f"executed code outside the fixed bank: {outside[:4]}")

    ram = bytes(platform.ram)
    vram = bytes(platform.vram)
    palette = bytes(platform.palette)
    oam = bytes(platform.oam)
    apu = bytes(platform.apu)
    controller_state = platform.controllers[0]
    p = (state.p | 0x20) & 0xFF

    digest = FNV_OFFSET
    digest = fnv1a64(digest, ram)
    digest = fnv1a64(digest, vram)
    digest = fnv1a64(digest, palette)
    digest = fnv1a64(digest, oam)
    digest = fnv1a64(digest, apu)
    digest = fnv1a64_byte(digest, platform.apu_status)
    digest = fnv1a64_byte(digest, controller_state)
    digest = fnv1a64_byte(digest, platform.ctrl)
    digest = fnv1a64_byte(digest, platform.mask)
    digest = fnv1a64_byte(digest, platform.status)
    digest = fnv1a64_byte(digest, platform.oam_addr)
    digest = fnv1a64_byte(digest, platform.addr & 0xFF)
    digest = fnv1a64_byte(digest, (platform.addr >> 8) & 0xFF)
    digest = fnv1a64_byte(digest, platform.scroll_x)
    digest = fnv1a64_byte(digest, platform.scroll_y)
    digest = fnv1a64_byte(digest, platform.buffer)
    digest = fnv1a64(digest, bytes(platform.serial.reg))
    digest = fnv1a64_byte(digest, platform.serial.snapshot()["shift"])
    digest = fnv1a64_byte(digest, platform.serial.snapshot()["count"])
    digest = fnv1a64_byte(digest, state.a)
    digest = fnv1a64_byte(digest, state.x)
    digest = fnv1a64_byte(digest, state.y)
    digest = fnv1a64_byte(digest, state.sp)
    digest = fnv1a64_byte(digest, state.pc & 0xFF)
    digest = fnv1a64_byte(digest, (state.pc >> 8) & 0xFF)
    digest = fnv1a64_byte(digest, p)
    digest = fnv1a64_byte(digest, steps & 0xFF)
    digest = fnv1a64_byte(digest, (steps >> 8) & 0xFF)
    digest = fnv1a64_byte(digest, (steps >> 16) & 0xFF)
    digest = fnv1a64_byte(digest, (steps >> 24) & 0xFF)

    mapper = platform.mapper_state()
    registers = platform.serial.reg
    fields = {
        "failed": "0",
        "error": "",
        "exit": "1" if exit_requested else "0",
        "steps": str(steps),
        "pc": f"0x{state.pc & 0xFFFF:04X}",
        "a": f"0x{state.a & 0xFF:02X}",
        "x": f"0x{state.x & 0xFF:02X}",
        "y": f"0x{state.y & 0xFF:02X}",
        "sp": f"0x{state.sp & 0xFF:02X}",
        "p": f"0x{p:02X}",
        "frames": str(frame_index),
        "nmi": str(nmi_delivered),
        "clock": str(clock),
        "exit_arg": f"0x{exit_argument:08X}",
        "ram_fnv1a64": f"0x{fnv1a64(FNV_OFFSET, ram):016X}",
        "ppu_fnv1a64": f"0x{fnv1a64(fnv1a64(fnv1a64(FNV_OFFSET, vram), palette), oam):016X}",
        "state_fnv1a64": f"0x{digest:016X}",
        "mmc1_regs": "".join(f"{value:02X}" for value in registers),
        "mmc1_shift": str(mapper["shift"]),
        "mmc1_count": str(mapper["count"]),
        "mmc1_writes": str(mapper["serial_writes"]),
        "prg_window_8000": str(mapper["prg_window_8000_bank"]),
        "prg_window_c000": str(mapper["prg_window_c000_bank"]),
        "chr_mode": str(mapper["chr_mode"]),
        "mirroring": str(mapper["mirroring"]),
        "prg_ram_enabled": "0",
    }
    frame_lines = [
        f"frame[{item['index']}]={item['input']:02X},{item['tile']:016X},"
        f"{item['ppu']:016X}"
        for item in frames
    ]
    exit_word = ram[0x0400:0x0408].hex().upper()
    return {
        "fields": fields,
        "frames": frame_lines,
        "exit_word": exit_word,
        "frame_records": frames,
        "services": services,
        "mapper": mapper,
        "cpu": {
            "a": state.a, "x": state.x, "y": state.y, "sp": state.sp,
            "pc": state.pc & 0xFFFF, "p": p, "steps": steps,
            "clock": clock, "nmi": nmi_delivered,
        },
        "raw": {
            "ram": ram,
            "vram": vram,
            "palette": palette,
            "oam": oam,
            "apu": apu,
            "apu_status": platform.apu_status,
            "controller_state": controller_state,
            "executed_addresses": sorted(executed),
        },
    }


__all__ = [
    "EXIT_SERVICE",
    "EXIT_SITE",
    "FNV_OFFSET",
    "FRAME_UNITS",
    "MAX_STEPS",
    "NMI_ENTRY_COST",
    "P6Mmc1ReferencePlatform",
    "P6ReferenceError",
    "REFERENCE_COSTS",
    "VBLANK_UNITS",
    "build_cpu_image",
    "fnv1a64",
    "fnv1a64_byte",
    "run_reference",
]
