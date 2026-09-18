#!/usr/bin/env python3
"""Phase-6 MMC1 PRG banking (P6-03).

Maps the `MMC1_SUBSET_V1` control/PRG register state to the CPU `$8000-$FFFF`
cartridge window:

* 32 KiB modes (control PRG mode 0/1): the register low bit is ignored and the
  selected 32 KiB bank covers both windows;
* mode 2: bank 0 fixed at `$8000-$BFFF`, the register-selected bank at
  `$C000-$FFFF`;
* mode 3: the register-selected bank at `$8000-$BFFF`, the last bank fixed at
  `$C000-$FFFF`;
* bank masking is `register & (bank_count - 1)` with a power-of-two bank count;
* unsupported bank counts or addresses fail closed with `MMC1PrgError`.

The serial register file from P6-02 is consumed read-only; this module never
mutates registers.
"""
from __future__ import annotations

import sys
from typing import Any

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT / ".openrecomp-phase6" / "src"),):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from p6_mmc1_serial_v1 import MMC1Serial  # noqa: E402

PRG_WINDOW_MIN = 0x8000
PRG_WINDOW_MAX = 0xFFFF
PRG_BANK_BYTES = 0x4000
SUPPORTED_PRG_BANK_COUNTS = (1, 2, 4, 8, 16)

MIRRORING_BY_BITS = {
    0: "one_screen_lower",
    1: "one_screen_upper",
    2: "vertical",
    3: "horizontal",
}


class MMC1PrgError(ValueError):
    """Fail-closed MMC1 PRG banking error."""


class MMC1PrgMapper:
    def __init__(self, prg_bank_count: int, serial: MMC1Serial | None = None) -> None:
        if isinstance(prg_bank_count, bool) or not isinstance(prg_bank_count, int):
            raise MMC1PrgError("prg_bank_count must be an integer")
        if prg_bank_count not in SUPPORTED_PRG_BANK_COUNTS:
            raise MMC1PrgError(
                f"unsupported PRG bank count {prg_bank_count}; supported: "
                f"{', '.join(str(item) for item in SUPPORTED_PRG_BANK_COUNTS)}")
        self.prg_bank_count = prg_bank_count
        self.serial = serial if serial is not None else MMC1Serial()

    @property
    def mask(self) -> int:
        return self.prg_bank_count - 1

    @property
    def control(self) -> int:
        return self.serial.registers[0]

    @property
    def mirroring_bits(self) -> int:
        return self.control & 0x03

    @property
    def mirroring(self) -> str:
        return MIRRORING_BY_BITS[self.mirroring_bits]

    @property
    def prg_mode(self) -> int:
        return (self.control >> 2) & 0x03

    @property
    def chr_mode(self) -> int:
        return (self.control >> 4) & 0x01

    @property
    def prg_register(self) -> int:
        return self.serial.registers[3]

    def window_banks(self) -> tuple[int, int]:
        mode = self.prg_mode
        register = self.prg_register
        mask = self.mask
        if mode in (0, 1):
            base = (register & 0x1E) & mask
            return base, (base + 1) & mask
        if mode == 2:
            return 0, register & mask
        return register & mask, self.prg_bank_count - 1

    def window_for_address(self, address: int) -> int:
        address = _require_address(address)
        return (address >> 14) & 0x01

    def bank_for_address(self, address: int) -> int:
        return self.window_banks()[self.window_for_address(address)]

    def map_offset(self, address: int) -> int:
        """Return the PRG ROM image offset for a CPU $8000-$FFFF address."""
        address = _require_address(address)
        window = (address >> 14) & 0x01
        bank = self.window_banks()[window]
        return bank * PRG_BANK_BYTES + (address & 0x3FFF)

    def layout(self) -> dict[str, Any]:
        low, high = self.window_banks()
        return {
            "prg_mode": self.prg_mode,
            "chr_mode": self.chr_mode,
            "mirroring": self.mirroring,
            "prg_register": self.prg_register,
            "prg_bank_count": self.prg_bank_count,
            "window_8000_bank": low,
            "window_c000_bank": high,
        }


def _require_address(address: int) -> int:
    if isinstance(address, bool) or not isinstance(address, int):
        raise MMC1PrgError("address must be an integer")
    if not PRG_WINDOW_MIN <= address <= PRG_WINDOW_MAX:
        raise MMC1PrgError(
            f"address 0x{address:04x} outside the PRG window "
            f"${PRG_WINDOW_MIN:04x}-${PRG_WINDOW_MAX:04x}")
    return address


__all__ = [
    "MMC1PrgError",
    "MMC1PrgMapper",
    "MIRRORING_BY_BITS",
    "PRG_BANK_BYTES",
    "PRG_WINDOW_MAX",
    "PRG_WINDOW_MIN",
    "SUPPORTED_PRG_BANK_COUNTS",
]
