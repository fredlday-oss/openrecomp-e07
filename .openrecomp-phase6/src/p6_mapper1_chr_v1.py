#!/usr/bin/env python3
"""Phase-6 MMC1 CHR banking and nametable mirroring (P6-04).

Maps the `MMC1_SUBSET_V1` control/CHR register state to PPU space:

* CHR mode 0: one 8 KiB bank from the CHR bank 0 register shifted right by one;
* CHR mode 1: two independent 4 KiB banks from the CHR bank 0/1 registers;
* bank masking is modulo the supported power-of-two bank count
  (8 KiB units 1, 2, 4, 8, 16 = 8 KiB .. 128 KiB);
* mirroring bits 1:0 select one-screen lower/upper, vertical and horizontal;
* nametable mapping covers `$2000-$3EFF`; palette passthrough is reported
  explicitly and outside ranges fail closed.

The serial register file from P6-02 is consumed read-only; this module never
mutates registers.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT / ".openrecomp-phase6" / "src"),):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from p6_mmc1_serial_v1 import MMC1Serial  # noqa: E402

CHR_WINDOW_MIN = 0x0000
CHR_WINDOW_MAX = 0x1FFF
NAMETABLE_WINDOW_MIN = 0x2000
NAMETABLE_WINDOW_MAX = 0x3EFF
PALETTE_WINDOW_MIN = 0x3F00
PALETTE_WINDOW_MAX = 0x3FFF
CHR_BANK_BYTES_8K = 0x2000
CHR_BANK_BYTES_4K = 0x1000
SUPPORTED_CHR_BANK_COUNTS_8K = (1, 2, 4, 8, 16)

MIRRORING_NAMES = {
    0: "one_screen_lower",
    1: "one_screen_upper",
    2: "vertical",
    3: "horizontal",
}

# Physical nametable selected for (address bit 10, address bit 11) per mode.
_MIRROR_TABLE = {
    0: (0, 0, 0, 0),
    1: (1, 1, 1, 1),
    2: (0, 1, 0, 1),
    3: (0, 0, 1, 1),
}


class MMC1ChrError(ValueError):
    """Fail-closed MMC1 CHR/mirroring error."""


def _require_address(address: int, minimum: int, maximum: int, label: str) -> int:
    if isinstance(address, bool) or not isinstance(address, int):
        raise MMC1ChrError("address must be an integer")
    if not minimum <= address <= maximum:
        raise MMC1ChrError(
            f"address 0x{address:04x} outside the {label} window "
            f"${minimum:04x}-${maximum:04x}")
    return address


class MMC1Chr:
    def __init__(self, chr_bank_count_8k: int, serial: MMC1Serial | None = None) -> None:
        if isinstance(chr_bank_count_8k, bool) or not isinstance(chr_bank_count_8k, int):
            raise MMC1ChrError("chr_bank_count_8k must be an integer")
        if chr_bank_count_8k not in SUPPORTED_CHR_BANK_COUNTS_8K:
            raise MMC1ChrError(
                f"unsupported CHR 8 KiB bank count {chr_bank_count_8k}; "
                f"supported: {', '.join(str(item) for item in SUPPORTED_CHR_BANK_COUNTS_8K)}")
        self.chr_bank_count_8k = chr_bank_count_8k
        self.serial = serial if serial is not None else MMC1Serial()

    @property
    def control(self) -> int:
        return self.serial.registers[0]

    @property
    def chr_mode(self) -> int:
        return (self.control >> 4) & 0x01

    @property
    def register_0(self) -> int:
        return self.serial.registers[1]

    @property
    def register_1(self) -> int:
        return self.serial.registers[2]

    def banks(self) -> dict[str, Any]:
        if self.chr_mode == 0:
            bank = (self.register_0 >> 1) & (self.chr_bank_count_8k - 1)
            return {"granule": CHR_BANK_BYTES_8K, "count": self.chr_bank_count_8k,
                    "bank_0": bank, "bank_1": bank}
        count_4k = self.chr_bank_count_8k * 2
        return {"granule": CHR_BANK_BYTES_4K, "count": count_4k,
                "bank_0": self.register_0 & (count_4k - 1),
                "bank_1": self.register_1 & (count_4k - 1)}

    def map_offset(self, address: int) -> int:
        address = _require_address(address, CHR_WINDOW_MIN, CHR_WINDOW_MAX, "CHR")
        layout = self.banks()
        if layout["granule"] == CHR_BANK_BYTES_8K:
            return layout["bank_0"] * CHR_BANK_BYTES_8K + (address & 0x1FFF)
        half = (address >> 12) & 0x01
        bank = layout["bank_0"] if half == 0 else layout["bank_1"]
        return bank * CHR_BANK_BYTES_4K + (address & 0x0FFF)

    def layout(self) -> dict[str, Any]:
        return {"chr_mode": self.chr_mode, **self.banks()}


class MMC1Nametables:
    def __init__(self, serial: MMC1Serial | None = None) -> None:
        self.serial = serial if serial is not None else MMC1Serial()

    @property
    def control(self) -> int:
        return self.serial.registers[0]

    @property
    def mirroring_bits(self) -> int:
        return self.control & 0x03

    @property
    def mirroring(self) -> str:
        return MIRRORING_NAMES[self.mirroring_bits]

    def table_for_address(self, address: int) -> int:
        address = _require_address(address, NAMETABLE_WINDOW_MIN,
                                   NAMETABLE_WINDOW_MAX, "nametable")
        bit10 = (address >> 10) & 1
        bit11 = (address >> 11) & 1
        return _MIRROR_TABLE[self.mirroring_bits][bit10 + 2 * bit11]

    def offset_in_table(self, address: int) -> int:
        address = _require_address(address, NAMETABLE_WINDOW_MIN,
                                   NAMETABLE_WINDOW_MAX, "nametable")
        return address & 0x03FF

    def physical_offset(self, address: int) -> int:
        table = self.table_for_address(address)
        return table * 0x0400 + (address & 0x03FF)

    def layout(self) -> dict[str, Any]:
        return {"mirroring_bits": self.mirroring_bits,
                "mirroring": self.mirroring}


__all__ = [
    "CHR_BANK_BYTES_4K",
    "CHR_BANK_BYTES_8K",
    "CHR_WINDOW_MAX",
    "CHR_WINDOW_MIN",
    "MMC1Chr",
    "MMC1ChrError",
    "MMC1Nametables",
    "MIRRORING_NAMES",
    "NAMETABLE_WINDOW_MAX",
    "NAMETABLE_WINDOW_MIN",
    "PALETTE_WINDOW_MAX",
    "PALETTE_WINDOW_MIN",
    "SUPPORTED_CHR_BANK_COUNTS_8K",
]
