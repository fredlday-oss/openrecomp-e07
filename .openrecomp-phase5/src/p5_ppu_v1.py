#!/usr/bin/env python3
"""Phase-5 bounded PPU interface and deterministic graphics model (P5-06).

An original implementation of the documented CPU-facing PPU register and
memory surface required by the audited public fixture:

* registers $2000-$2007: PPUCTRL, PPUMASK, PPUSTATUS (vblank bit 7, read
  clears vblank and the shared write latch), OAMADDR, OAMDATA (writes
  increment the address, reads do not), PPUSCROLL (X then Y), PPUADDR (high
  then low), PPUDATA (documented one-byte read buffer; palette reads are
  immediate and refresh the buffer from the mirrored background entry);
* PPU memory: 8 KiB CHR space through the cartridge (ROM read-only, optional
  RAM writable), 2 KiB nametable VRAM with documented horizontal/vertical
  arrangement mapping, 32-byte palette with the $3F10/$3F14/$3F18/$3F1C
  mirrors, $3000-$3EFF nametable mirroring, greyscale read masking;
* vblank is an explicit deterministic platform event (`set_vblank`); NMI
  enable is `nmi_enabled()` for the P5-07 delivery boundary;
* deterministic graphics observation: a bounded tile-space view (one byte per
  nametable tile) plus canonical PPU state digests, submitted through the
  Phase-4 graphics boundary. This is a bounded state model - NOT emulated
  video output, no cycle accuracy and no sprite rendering.

Unsupported and fail-closed: four-screen nametables, CHR-ROM writes, unknown
PPU registers, out-of-range PPU addresses.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase4" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from openrecomp import runtime_abi as rt  # noqa: E402

CHR_SIZE = 0x2000
VRAM_SIZE = 0x0800
PALETTE_SIZE = 0x20
OAM_SIZE = 0x0100
PPU_ADDRESS_MASK = 0x3FFF
NAMETABLE_TILE_COUNT = 960


class P5PpuError(ValueError):
    """Fail-closed PPU error."""


def _check_byte(value: int, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not (0 <= value <= 0xFF):
        raise P5PpuError(f"{what} 0x{value!r} is outside 8 bits")
    return value


class P5Ppu:
    """Deterministic CPU-facing PPU register/memory surface (bounded)."""

    def __init__(self, mirroring: str, chr_rom: bytes | None = None) -> None:
        if mirroring not in ("horizontal", "vertical"):
            raise P5PpuError(
                f"mirroring {mirroring!r} is not supported (four-screen and "
                "unknown arrangements fail closed)")
        self.mirroring = mirroring
        if chr_rom is None:
            self.chr = bytearray(CHR_SIZE)
            self.chr_is_ram = True
        else:
            self.chr = bytes(chr_rom)
            if len(self.chr) != CHR_SIZE:
                raise P5PpuError(f"CHR ROM must be 8 KiB, got {len(self.chr)}")
            self.chr_is_ram = False
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

    # -- deterministic vblank / NMI-enable surface -------------------------
    def set_vblank(self, value: bool) -> None:
        if value:
            self.status |= 0x80
        else:
            self.status &= ~0x80

    def vblank(self) -> bool:
        return bool(self.status & 0x80)

    def nmi_enabled(self) -> bool:
        return bool(self.ctrl & 0x80)

    def increment(self) -> int:
        return 32 if (self.ctrl & 0x04) else 1

    # -- CPU-facing registers ----------------------------------------------
    def cpu_write(self, register: int, value: int) -> None:
        if isinstance(register, bool) or not isinstance(register, int) or not (0 <= register <= 7):
            raise P5PpuError(f"unknown PPU register ${register!r}")
        value = _check_byte(value, "PPU write value")
        self.open_bus = value
        if register == 0:
            self.ctrl = value
        elif register == 1:
            self.mask = value
        elif register == 2:
            return
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
        else:
            self.memory_write(self.addr, value)
            self.addr = (self.addr + self.increment()) & PPU_ADDRESS_MASK

    def cpu_read(self, register: int) -> int:
        if isinstance(register, bool) or not isinstance(register, int) or not (0 <= register <= 7):
            raise P5PpuError(f"unknown PPU register ${register!r}")
        if register == 2:
            value = (self.status & 0xE0) | (self.open_bus & 0x1F)
            self.status &= ~0x80
            self.w = 0
            return value
        if register == 4:
            return self.oam[self.oam_addr]
        if register == 7:
            return self._ppudata_read()
        return self.open_bus

    def _ppudata_read(self) -> int:
        address = self.addr
        if 0x3F00 <= address <= 0x3FFF:
            value = self.memory_read(address)
            self.buffer = self.memory_read((address - 0x1000) & PPU_ADDRESS_MASK)
        else:
            value = self.buffer
            self.buffer = self.memory_read(address)
        self.addr = (address + self.increment()) & PPU_ADDRESS_MASK
        return value

    # -- PPU memory ---------------------------------------------------------
    def _nametable_index(self, address: int) -> int:
        offset = address - 0x2000
        if offset >= 0x1000:
            offset -= 0x1000
        nametable = (offset >> 10) & 0x03
        if self.mirroring == "horizontal":
            physical = ((nametable >> 1) * 0x400) + (offset & 0x3FF)
        else:
            physical = ((nametable & 1) * 0x400) + (offset & 0x3FF)
        return physical

    def _palette_index(self, address: int) -> int:
        index = (address - 0x3F00) & 0x1F
        if index in (0x10, 0x14, 0x18, 0x1C):
            index -= 0x10
        return index

    def memory_read(self, address: int) -> int:
        if isinstance(address, bool) or not isinstance(address, int) or not (0 <= address <= 0xFFFF):
            raise P5PpuError(f"PPU address 0x{address!r} is outside the 16-bit space")
        address &= PPU_ADDRESS_MASK
        if address < 0x2000:
            return self.chr[address]
        if address < 0x3F00:
            return self.vram[self._nametable_index(address)]
        value = self.palette[self._palette_index(address)]
        if self.mask & 0x01:
            value &= 0x30
        return value

    def memory_write(self, address: int, value: int) -> None:
        if isinstance(address, bool) or not isinstance(address, int) or not (0 <= address <= 0xFFFF):
            raise P5PpuError(f"PPU address 0x{address!r} is outside the 16-bit space")
        address &= PPU_ADDRESS_MASK
        value = _check_byte(value, "PPU write value")
        if address < 0x2000:
            if not self.chr_is_ram:
                raise P5PpuError("CHR ROM is not writable")
            self.chr[address] = value
        elif address < 0x3F00:
            self.vram[self._nametable_index(address)] = value
        else:
            self.palette[self._palette_index(address)] = value & 0x3F

    # -- deterministic bounded graphics observation -------------------------
    def tile_space(self) -> bytes:
        return bytes(self.vram[0:NAMETABLE_TILE_COUNT])

    def state_document(self) -> dict[str, Any]:
        return {
            "ctrl": self.ctrl,
            "mask": self.mask,
            "status": self.status,
            "oam_addr": self.oam_addr,
            "addr": self.addr,
            "t": self.t,
            "w": self.w,
            "scroll_x": self.scroll_x,
            "scroll_y": self.scroll_y,
            "buffer": self.buffer,
            "open_bus": self.open_bus,
            "vram_sha256": hashlib.sha256(bytes(self.vram)).hexdigest(),
            "palette_sha256": hashlib.sha256(bytes(self.palette)).hexdigest(),
            "oam_sha256": hashlib.sha256(bytes(self.oam)).hexdigest(),
            "chr_sha256": hashlib.sha256(bytes(self.chr)).hexdigest(),
            "chr_is_ram": self.chr_is_ram,
            "mirroring": self.mirroring,
            "vblank": self.vblank(),
            "nmi_enabled": self.nmi_enabled(),
        }

    def digest(self) -> str:
        text = json.dumps(self.state_document(), indent=2, sort_keys=True) + "\n"
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def frame_observable(self, sequence: int) -> rt.RuntimeFrame:
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise P5PpuError("frame sequence must be a non-negative integer")
        payload = self.tile_space()
        return rt.RuntimeFrame(32, 30, rt.RuntimePixelFormat.GRAY8, payload,
                               sequence=sequence)


def timing_assumptions() -> dict[str, Any]:
    """The documented bounded timing model (no cycle accuracy claim)."""
    return {
        "vblank_source": "explicit deterministic platform event (P5-07)",
        "nmi_delivery": "platform queues NMI at vblank when PPUCTRL bit 7 is set; "
                        "delivered at an instruction boundary (P5-07)",
        "frame_length_model": "virtual frame: 29780 retired CPU clock units with a "
                              "2273-unit vblank window (documented NTSC nominal), "
                              "instruction clock costs from a documented P5 table",
        "ppu_rendering": "not modelled; the observable is a bounded tile-space "
                         "state view submitted through the Phase-4 graphics boundary",
        "cycle_accuracy": False,
        "sprite_rendering": False,
        "sprite_zero_hit": False,
        "sprite_overflow_timing": False,
        "fine_scroll_rendering": False,
        "four_screen": "unsupported, fails closed",
    }


__all__ = [
    "CHR_SIZE",
    "NAMETABLE_TILE_COUNT",
    "OAM_SIZE",
    "P5Ppu",
    "P5PpuError",
    "PALETTE_SIZE",
    "PPU_ADDRESS_MASK",
    "VRAM_SIZE",
    "timing_assumptions",
]
