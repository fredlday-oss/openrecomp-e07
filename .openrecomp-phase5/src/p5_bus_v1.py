#!/usr/bin/env python3
"""Phase-5 bounded NES CPU memory map and mapper model (P5-05).

An original implementation of the documented NES CPU bus for the audited
public NROM fixture, kept behind an explicit platform boundary:

* 2 KiB internal RAM at $0000-$07FF mirrored through $1FFF;
* PPU register window $2000-$3FFF routed as register = (address - $2000) & 7
  to an attached PPU port (PPU semantics are P5-06 scope);
* APU/IO $4000-$4017 register latches, $4015 status, $4014 OAM DMA
  (256 bytes copied through the CPU bus), controller strobe/serial ports;
* $4018-$401F disabled I/O and $4020-$5FFF expansion fail closed;
* cartridge window: optional PRG-RAM at $6000-$7FFF and NROM (mapper 0) PRG
  ROM at $8000-$FFFF with the documented 16 KiB mirroring for NROM-128.

No mapper behaviour is guessed: a non-NROM image fails closed at construction.
The module mirrors the frozen independent platform contract
(`tools/nes_platform_v1.py`) and is differentially verified against it.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Protocol

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

RAM_SIZE = 0x0800
APU_IO_BASE = 0x4000
APU_REGISTER_COUNT = 0x18
OAM_SIZE = 0x0100
PRG_ROM_BASE = 0x8000
PRG_RAM_BASE = 0x6000


class P5BusError(ValueError):
    """Fail-closed NES CPU bus error."""


class PpuPort(Protocol):
    oam: bytearray

    def cpu_read(self, register: int) -> int: ...

    def cpu_write(self, register: int, value: int) -> None: ...


def _check_address(address: int) -> int:
    if isinstance(address, bool) or not isinstance(address, int) or not (0 <= address <= 0xFFFF):
        raise P5BusError(f"CPU address 0x{address!r} is outside the 16-bit space")
    return address


class P5Cartridge:
    """Bounded NROM (mapper 0) cartridge window."""

    def __init__(self, rom: bytes, inventory: dict) -> None:
        if inventory.get("mapper") != 0:
            raise P5BusError(
                f"mapper {inventory.get('mapper')!r} is not implemented; "
                "fail closed instead of guessing banking behaviour")
        prg_offset = 16 + int(inventory.get("trainer_bytes") or 0)
        prg_bytes = int(inventory["prg_bytes"])
        prg = bytes(rom[prg_offset:prg_offset + prg_bytes])
        if len(prg) != prg_bytes or len(prg) not in (0x4000, 0x8000):
            raise P5BusError(
                f"NROM PRG must be 16 or 32 KiB, got {len(prg)}")
        self.prg = prg
        self.prg_ram_bytes = int(inventory.get("prg_ram_bytes") or 0)
        if self.prg_ram_bytes:
            if self.prg_ram_bytes > 0x2000:
                raise P5BusError(
                    f"PRG-RAM size {self.prg_ram_bytes} exceeds the 8 KiB window")
            self.prg_ram = bytearray(self.prg_ram_bytes)
        else:
            self.prg_ram = None

    def cpu_read(self, address: int) -> int:
        if PRG_RAM_BASE <= address < PRG_ROM_BASE:
            if self.prg_ram is None:
                raise P5BusError(
                    f"PRG-RAM read at 0x{address:04x} but no PRG-RAM is present")
            return self.prg_ram[address - PRG_RAM_BASE]
        if PRG_ROM_BASE <= address <= 0xFFFF:
            offset = address - PRG_ROM_BASE
            if len(self.prg) == 0x4000:
                offset &= 0x3FFF
            return self.prg[offset]
        raise P5BusError(f"cartridge read outside the cartridge window: 0x{address:04x}")

    def cpu_write(self, address: int, value: int) -> None:
        if PRG_RAM_BASE <= address < PRG_ROM_BASE:
            if self.prg_ram is None:
                raise P5BusError(
                    f"PRG-RAM write at 0x{address:04x} but no PRG-RAM is present")
            self.prg_ram[address - PRG_RAM_BASE] = value & 0xFF
            return
        if PRG_ROM_BASE <= address <= 0xFFFF:
            return  # NROM has no mapper registers; documented writes ignored
        raise P5BusError(f"cartridge write outside the cartridge window: 0x{address:04x}")


class P5ControllerPorts:
    """Documented standard-controller serial protocol."""

    def __init__(self) -> None:
        self.states = [0x00, 0x00]
        self.strobe = 0
        self.bits_read = [0, 0]

    def set_controller(self, port: int, state: int) -> None:
        if port not in (0, 1):
            raise P5BusError(f"controller port must be 0 or 1, got {port}")
        if isinstance(state, bool) or not isinstance(state, int) or not (0 <= state <= 0xFF):
            raise P5BusError(f"controller state 0x{state!r} is outside 8 bits")
        self.states[port] = state

    def write(self, value: int) -> None:
        self.strobe = value & 0x01
        self.bits_read = [0, 0]

    def read(self, port: int) -> int:
        if self.strobe:
            return 0x40 | (self.states[port] & 0x01)
        count = self.bits_read[port]
        bit = ((self.states[port] >> count) & 0x01) if count < 8 else 1
        self.bits_read[port] = count + 1
        return 0x40 | bit


class P5NesBus:
    """Bounded, fail-closed NES CPU bus for the audited NROM fixture."""

    def __init__(self, cartridge: P5Cartridge, ppu: PpuPort,
                 controllers: P5ControllerPorts | None = None) -> None:
        self.cartridge = cartridge
        self.ppu = ppu
        self.controllers = controllers or P5ControllerPorts()
        self.ram = bytearray(RAM_SIZE)
        self.apu_registers = bytearray(APU_REGISTER_COUNT)
        self.apu_status = 0

    def read(self, address: int) -> int:
        address = _check_address(address)
        if address < 0x2000:
            return self.ram[address & 0x07FF]
        if address < 0x4000:
            return self.ppu.cpu_read((address - 0x2000) & 0x07)
        if address == 0x4014:
            return 0
        if address == 0x4015:
            return self.apu_status
        if address == 0x4016:
            return self.controllers.read(0)
        if address == 0x4017:
            return self.controllers.read(1)
        if address < 0x4018:
            return 0
        if address < 0x4020:
            raise P5BusError(f"read from disabled I/O register 0x{address:04x}")
        if address < 0x6000:
            raise P5BusError(f"read from the expansion area 0x{address:04x}")
        return self.cartridge.cpu_read(address)

    def write(self, address: int, value: int) -> None:
        address = _check_address(address)
        if isinstance(value, bool) or not isinstance(value, int):
            raise P5BusError(f"CPU write value {value!r} is not an integer")
        value &= 0xFF
        if address < 0x2000:
            self.ram[address & 0x07FF] = value
            return
        if address < 0x4000:
            self.ppu.cpu_write((address - 0x2000) & 0x07, value)
            return
        if address <= 0x4013:
            self.apu_registers[address - APU_IO_BASE] = value
            return
        if address == 0x4014:
            self._oam_dma(value)
            return
        if address == 0x4015:
            self.apu_status = value & 0x1F
            return
        if address == 0x4016:
            self.controllers.write(value)
            return
        if address == 0x4017:
            self.apu_registers[0x17] = value
            return
        if address < 0x4020:
            raise P5BusError(f"write to disabled I/O register 0x{address:04x}")
        if address < 0x6000:
            raise P5BusError(f"write to the expansion area 0x{address:04x}")
        self.cartridge.cpu_write(address, value)

    def _oam_dma(self, page: int) -> None:
        base = (page & 0xFF) << 8
        for offset in range(OAM_SIZE):
            self.ppu.oam[offset] = self.read(base + offset)


__all__ = [
    "APU_IO_BASE",
    "APU_REGISTER_COUNT",
    "OAM_SIZE",
    "P5BusError",
    "P5Cartridge",
    "P5ControllerPorts",
    "P5NesBus",
    "PRG_RAM_BASE",
    "PRG_ROM_BASE",
    "RAM_SIZE",
]
