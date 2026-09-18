#!/usr/bin/env python3
"""Phase-6 MMC1 cartridge service (P6-07).

CPU- and PPU-side mapper service for the supported MMC1 profile, composing the
audited P6-02 .. P6-05 models: serial register file, PRG window mapping, CHR
window mapping, nametable mirroring and the disabled PRG-RAM window. It
implements the same `cpu_read`/`cpu_write` cartridge protocol used by the
frozen Phase-5 bus (`p5_bus_v1.P5NesBus`), so it can be attached without
modifying the frozen bus, and it exposes an explicit `advance(cost)` hook so
the runtime can supply CPU cycle numbers for the serial write protocol.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT / ".openrecomp-phase6" / "src"),):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_mapper1_chr_v1 as chr_model  # noqa: E402
import p6_mapper1_prg_v1 as prg_model  # noqa: E402
import p6_mapper1_variant_v1 as variant_model  # noqa: E402
import p6_mmc1_spec_v1 as mmc1_spec  # noqa: E402
import p6_mmc1_serial_v1 as serial_model  # noqa: E402

PRG_RAM_BASE = 0x6000
PRG_ROM_BASE = 0x8000
CHR_BASE = 0x0000
CHR_END = 0x1FFF
NAMETABLE_BASE = 0x2000
NAMETABLE_END = 0x3EFF


class P6CartridgeError(ValueError):
    """Fail-closed Phase-6 cartridge error."""


class P6Mmc1Cartridge:
    def __init__(self, rom: bytes, inventory: dict[str, Any]) -> None:
        classification = mmc1_spec.classify(inventory)
        if classification["status"] != "SUPPORTED_MMC1":
            raise P6CartridgeError(
                f"cartridge classification {classification['status']} is not "
                f"supported: {', '.join(classification['reasons']) or 'no reasons'}")
        self.classification = classification
        self.inventory = dict(inventory)
        prg_offset = 16 + int(inventory.get("trainer_bytes") or 0)
        prg_bytes = int(inventory["prg_bytes"])
        chr_bytes = int(inventory["chr_bytes"])
        if inventory.get("chr_is_ram"):
            raise P6CartridgeError("CHR-RAM cartridges are not supported")
        self.prg = bytes(rom[prg_offset:prg_offset + prg_bytes])
        self.chr = bytes(rom[prg_offset + prg_bytes:
                             prg_offset + prg_bytes + chr_bytes])
        if len(self.prg) != prg_bytes or len(self.chr) != chr_bytes:
            raise P6CartridgeError("cartridge segments are truncated")
        self.prg_banks = int(classification["prg_banks_16k"])
        self.chr_banks_8k = int(classification["chr_banks_8k"])
        self.serial = serial_model.MMC1Serial()
        self.cycles = 0
        self.prg_window = prg_model.MMC1PrgMapper(self.prg_banks, self.serial)
        self.chr_window = chr_model.MMC1Chr(self.chr_banks_8k, self.serial)
        self.nametables = chr_model.MMC1Nametables(self.serial)
        self.prg_ram = variant_model.MMC1PrgRamWindow(inventory)

    def advance(self, cost: int) -> None:
        if isinstance(cost, bool) or not isinstance(cost, int) or cost < 0:
            raise P6CartridgeError("advance cost must be a non-negative integer")
        self.cycles += cost

    def _check_address(self, address: int) -> int:
        if isinstance(address, bool) or not isinstance(address, int):
            raise P6CartridgeError("address must be an integer")
        if not 0 <= address <= 0xFFFF:
            raise P6CartridgeError(f"address 0x{address:x} outside 16 bits")
        return address

    def cpu_read(self, address: int) -> int:
        address = self._check_address(address)
        if PRG_RAM_BASE <= address < PRG_ROM_BASE:
            return self.prg_ram.read(address)
        if PRG_ROM_BASE <= address <= 0xFFFF:
            return self.prg[self.prg_window.map_offset(address)]
        raise P6CartridgeError(
            f"cartridge read outside the cartridge window: 0x{address:04x}")

    def cpu_write(self, address: int, value: int) -> dict[str, Any] | None:
        address = self._check_address(address)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFF:
            raise P6CartridgeError("write value must be an 8-bit integer")
        if PRG_RAM_BASE <= address < PRG_ROM_BASE:
            self.prg_ram.write(address, value)
            return None
        if PRG_ROM_BASE <= address <= 0xFFFF:
            return self.serial.write(address, value, self.cycles)
        raise P6CartridgeError(
            f"cartridge write outside the cartridge window: 0x{address:04x}")

    def ppu_chr_read(self, address: int) -> int:
        if isinstance(address, bool) or not isinstance(address, int):
            raise P6CartridgeError("PPU address must be an integer")
        if not CHR_BASE <= address <= CHR_END:
            raise P6CartridgeError(
                f"PPU address 0x{address:04x} outside the CHR window")
        return self.chr[self.chr_window.map_offset(address)]

    def ppu_nametable_target(self, address: int) -> tuple[int, int]:
        if not NAMETABLE_BASE <= address <= NAMETABLE_END:
            raise P6CartridgeError(
                f"PPU address 0x{address:04x} outside the nametable window")
        return (self.nametables.table_for_address(address),
                self.nametables.offset_in_table(address))

    def mapper_state(self) -> dict[str, Any]:
        low, high = self.prg_window.window_banks()
        chr_layout = self.chr_window.banks()
        return {
            "registers": dict(zip(serial_model.REGISTER_NAMES,
                                  self.serial.registers)),
            "shift": self.serial.shift,
            "count": self.serial.count,
            "last_write_cycle": self.serial.last_write_cycle,
            "cycles": self.cycles,
            "prg_window_8000_bank": low,
            "prg_window_c000_bank": high,
            "chr_mode": chr_layout["chr_mode"] if "chr_mode" in chr_layout
                        else self.chr_window.chr_mode,
            "chr_bank_0": chr_layout["bank_0"],
            "chr_bank_1": chr_layout["bank_1"],
            "mirroring": self.nametables.mirroring,
            "prg_ram_enabled": self.prg_ram.present(),
        }


__all__ = ["P6CartridgeError", "P6Mmc1Cartridge"]
