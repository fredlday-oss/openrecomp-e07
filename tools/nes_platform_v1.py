#!/usr/bin/env python3
"""NES CPU-facing PPU/APU/controller platform contract (P1-33).

Implements the documented NES CPU bus and the CPU-facing PPU, APU and standard
controller register surfaces needed for deterministic headless tests. Facts
follow the public NESdev references ("CPU memory map", "PPU registers",
"Standard controller"):

- CPU memory map: 2 KiB internal RAM at $0000-$07FF mirrored through
  $1FFF (address & $07FF); PPU registers at $2000-$2007 mirrored through
  $3FFF (address & 7); APU/IO at $4000-$4017; $4018-$401F disabled;
  $4020-$5FFF expansion; $6000-$FFFF routed to the cartridge mapper;
- PPU registers ($2000-$2007): PPUCTRL (write, NMI-enable bit 7 and
  VRAM-increment bit 2), PPUMASK (write), PPUSTATUS (read: vblank bit 7,
  sprite-0 bit 6, overflow bit 5; the read clears the vblank flag and the
  shared write latch), OAMADDR (write), OAMDATA (read/write, writes increment
  OAMADDR, reads do not), PPUSCROLL (two writes X then Y), PPUADDR (two writes
  high then low), PPUDATA (read/write with the documented one-byte read buffer,
  palette reads returned immediately, address auto-increment 1 or 32);
- PPU memory: 8 KiB CHR via the mapper; 2 KiB nametable VRAM with the
  documented horizontal/vertical arrangement mapping; 32-byte palette with the
  documented $3F10/$3F14/$3F18/$3F1C mirrors; 0x3000-0x3EFF mirrors
  0x2000-0x2EFF; palette resides at $3F00-$3FFF (14-bit PPU address space);
- OAMDMA ($4014): copies 256 bytes from CPU page (value << 8) to OAM;
- APU: $4000-$4013 register latches, $4015 status read/write and $4017 frame
  counter (deterministic surface; audio synthesis deferred);
- standard controller ($4016 write strobe; $4016/$4017 read): button report
  order A, B, Select, Start, Up, Down, Left, Right; reads return the open-bus
  value $40 in the undriven bits; after 8 bits an official controller reports 1.

Deferred (documented, out of Phase 1): cycle-perfect PPU/APU, sprite-0 hit and
overflow timing, OAM decay, DMC/DPCM read conflicts, four-screen VRAM,
non-NROM mappers. Commercial ROM bytes never enter this repository; the local
primary NES image is an external verification input (metadata only, per
`.openrecomp-phase1/ROM_PATHS.md`).
"""
from __future__ import annotations

from nes_rom_v1 import NESROMError, classify, make_mapper

RAM_SIZE = 0x800
VRAM_SIZE = 0x800
PALETTE_SIZE = 0x20
OAM_SIZE = 0x100
PPU_ADDRESS_MASK = 0x3FFF

BUTTON_ORDER = ("a", "b", "select", "start", "up", "down", "left", "right")


class NESPlatformError(ValueError):
    """Fail-closed NES platform error."""


def _controller_byte(buttons) -> int:
    if isinstance(buttons, int):
        if isinstance(buttons, bool) or not (0 <= buttons <= 0xFF):
            raise NESPlatformError(f"controller state 0x{buttons:x} is outside 8 bits")
        return buttons
    value = 0
    for index, name in enumerate(BUTTON_ORDER):
        if name in buttons:
            value |= 1 << index
    unknown = set(buttons) - set(BUTTON_ORDER)
    if unknown:
        raise NESPlatformError(f"unknown controller button(s): {sorted(unknown)}")
    return value


class NesPpu:
    """Deterministic CPU-facing PPU register + memory surface."""

    def __init__(self, mapper, mirroring: str) -> None:
        if mirroring not in ("horizontal", "vertical", "four-screen"):
            raise NESPlatformError(f"unknown nametable mirroring {mirroring!r}")
        self.mapper = mapper
        self.mirroring = mirroring
        self.vram = bytearray(VRAM_SIZE)
        self.palette = bytearray(PALETTE_SIZE)
        self.oam = bytearray(OAM_SIZE)
        self.oam_addr = 0
        self.ctrl = 0
        self.mask = 0
        self.status = 0
        self.addr = 0
        self.t = 0
        self.w = 0
        self.scroll_x = 0
        self.scroll_y = 0
        self.buffer = 0
        self.open_bus = 0

    def _increment(self) -> int:
        return 32 if (self.ctrl & 0x04) else 1

    def set_vblank(self, value: bool) -> None:
        if value:
            self.status |= 0x80
        else:
            self.status &= ~0x80

    def nmi_enabled(self) -> bool:
        return bool(self.ctrl & 0x80)

    def cpu_write(self, register: int, value: int) -> None:
        value &= 0xFF
        self.open_bus = value
        if register == 0:
            self.ctrl = value
        elif register == 1:
            self.mask = value
        elif register == 2:
            pass  # PPUSTATUS is read-only
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
                self.addr = self.t & PPU_ADDRESS_MASK
                self.w = 0
        elif register == 7:
            self.memory_write(self.addr, value)
            self.addr = (self.addr + self._increment()) & PPU_ADDRESS_MASK
        else:
            raise NESPlatformError(f"unknown PPU register ${register:x}")

    def cpu_read(self, register: int) -> int:
        if register == 2:
            value = (self.status & 0xE0) | (self.open_bus & 0x1F)
            self.status &= ~0x80  # documented: reading clears vblank
            self.w = 0  # documented: reading clears the write latch
            return value
        if register == 4:
            return self.oam[self.oam_addr]  # reads do not increment
        if register == 7:
            return self._ppudata_read()
        # Write-only registers return the open-bus latch.
        return self.open_bus

    def _ppudata_read(self) -> int:
        address = self.addr
        if 0x3F00 <= address <= 0x3FFF:
            value = self.memory_read(address)
            self.buffer = self.memory_read((address - 0x1000) & PPU_ADDRESS_MASK)
        else:
            value = self.buffer
            self.buffer = self.memory_read(address)
        self.addr = (address + self._increment()) & PPU_ADDRESS_MASK
        return value

    def _nametable_index(self, address: int) -> int:
        offset = address - 0x2000
        if offset >= 0x1000:
            offset -= 0x1000
        nametable = (offset >> 10) & 0x03
        if self.mirroring == "horizontal":
            physical = ((nametable >> 1) * 0x400) + (offset & 0x3FF)
        elif self.mirroring == "vertical":
            physical = ((nametable & 1) * 0x400) + (offset & 0x3FF)
        else:
            raise NESPlatformError("four-screen nametables are not modelled (only 2 KiB VRAM)")
        return physical

    def _palette_index(self, address: int) -> int:
        index = (address - 0x3F00) & 0x1F
        if index in (0x10, 0x14, 0x18, 0x1C):
            index -= 0x10  # documented universal-background mirrors
        return index

    def memory_read(self, address: int) -> int:
        address &= PPU_ADDRESS_MASK
        if address < 0x2000:
            return self.mapper.ppu_read(address)
        if address < 0x3F00:
            return self.vram[self._nametable_index(address)]
        value = self.palette[self._palette_index(address)]
        if self.mask & 0x01:
            value &= 0x30  # documented greyscale AND behaviour on reads
        return value

    def memory_write(self, address: int, value: int) -> None:
        address &= PPU_ADDRESS_MASK
        value &= 0xFF
        if address < 0x2000:
            self.mapper.ppu_write(address, value)
        elif address < 0x3F00:
            self.vram[self._nametable_index(address)] = value
        else:
            self.palette[self._palette_index(address)] = value & 0x3F


class NesMachine:
    """The documented NES CPU bus routed through a cartridge mapper."""

    def __init__(self, rom: bytes) -> None:
        try:
            info = classify(rom)
            self.mapper = make_mapper(rom)
        except NESROMError as exc:
            raise NESPlatformError(str(exc)) from exc
        self.mirroring = info.mirroring
        self.ram = bytearray(RAM_SIZE)
        self.ppu = NesPpu(self.mapper, info.mirroring)
        self.apu_registers = bytearray(0x18)  # $4000-$4017
        self.apu_status = 0
        self.strobe = 0
        self.controllers = [0x00, 0x00]
        self.controller_bits_read = [0, 0]

    # -- controllers -------------------------------------------------------
    def set_controller(self, port: int, buttons) -> None:
        if port not in (0, 1):
            raise NESPlatformError(f"controller port must be 0 or 1, got {port}")
        self.controllers[port] = _controller_byte(buttons)

    def _read_controller(self, port: int) -> int:
        if self.strobe:
            return 0x40 | (self.controllers[port] & 0x01)
        count = self.controller_bits_read[port]
        bit = ((self.controllers[port] >> count) & 0x01) if count < 8 else 1
        self.controller_bits_read[port] = count + 1
        return 0x40 | bit

    def _write_strobe(self, value: int) -> None:
        self.strobe = value & 0x01
        self.controller_bits_read = [0, 0]

    # -- OAM DMA -----------------------------------------------------------
    def _oam_dma(self, page: int) -> None:
        base = (page & 0xFF) << 8
        for offset in range(OAM_SIZE):
            self.ppu.oam[offset] = self.read_memory(base + offset)

    # -- CPU bus -----------------------------------------------------------
    def read_memory(self, address: int) -> int:
        if isinstance(address, bool) or not isinstance(address, int) or not (0 <= address <= 0xFFFF):
            raise NESPlatformError(f"CPU address 0x{address:x} is outside the 16-bit space")
        if address < 0x2000:
            return self.ram[address & 0x07FF]
        if address < 0x4000:
            return self.ppu.cpu_read(address & 0x07)
        if address == 0x4014:
            return 0  # OAMDMA is write-only
        if address == 0x4015:
            return self.apu_status
        if address == 0x4016:
            return self._read_controller(0)
        if address == 0x4017:
            return self._read_controller(1)
        if address < 0x4018:
            return 0  # APU channel registers are write-only; deterministic 0
        if address < 0x4020:
            raise NESPlatformError(f"access to disabled I/O register 0x{address:04x}")
        if address < 0x6000:
            raise NESPlatformError(f"access to the expansion area 0x{address:04x}")
        return self.mapper.cpu_read(address)

    def write_memory(self, address: int, value: int) -> None:
        if isinstance(address, bool) or not isinstance(address, int) or not (0 <= address <= 0xFFFF):
            raise NESPlatformError(f"CPU address 0x{address:x} is outside the 16-bit space")
        value &= 0xFF
        if address < 0x2000:
            self.ram[address & 0x07FF] = value
        elif address < 0x4000:
            self.ppu.cpu_write(address & 0x07, value)
        elif address <= 0x4013:
            self.apu_registers[address - 0x4000] = value
        elif address == 0x4014:
            self._oam_dma(value)
        elif address == 0x4015:
            self.apu_status = value & 0x1F
        elif address == 0x4016:
            self._write_strobe(value)
        elif address == 0x4017:
            self.apu_registers[0x17] = value
        elif address < 0x4018:
            raise NESPlatformError(f"write to disabled I/O register 0x{address:04x}")
        elif address < 0x4020:
            raise NESPlatformError(f"write to the expansion area 0x{address:04x}")
        else:
            self.mapper.cpu_write(address, value)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: nes_platform_v1.py <rom.nes>", file=sys.stderr)
        return 2
    try:
        data = __import__("pathlib").Path(argv[1]).read_bytes()
        info = classify(data)
    except (OSError, NESROMError) as exc:
        print(f"OPENRECOMP_NES_PLATFORM_V1=FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"NES_PLATFORM_MAPPER={info.mapper}")
    print(f"NES_PLATFORM_MIRRORING={info.mirroring}")
    print(f"NES_PLATFORM_PRG_BYTES={info.prg_bytes}")
    print("OPENRECOMP_NES_PLATFORM_V1=PASS")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))
