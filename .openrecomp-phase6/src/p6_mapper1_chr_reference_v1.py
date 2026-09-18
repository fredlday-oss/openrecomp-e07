#!/usr/bin/env python3
"""Independent reference model for Phase-6 MMC1 CHR banking and mirroring.

Independently structured from `p6_mapper1_chr_v1`: CHR banks are computed with
integer division and modulo, mapping is selected through explicit branch
tables, and nametable selection uses direct address-bit extraction instead of
the implementation's tuple lookup. Used only for differential testing.
"""
from __future__ import annotations

from typing import Any


class MMC1PpuReferenceError(ValueError):
    """Reference-model fail-closed error."""


VALID_CHR_BANK_COUNTS_8K = {1, 2, 4, 8, 16}


def reference_chr_banks(control: int, register_0: int, register_1: int,
                        chr_bank_count_8k: int) -> dict[str, Any]:
    if chr_bank_count_8k not in VALID_CHR_BANK_COUNTS_8K:
        raise MMC1PpuReferenceError("unsupported CHR bank count")
    if control < 0 or control > 0x1F or register_0 < 0 or register_0 > 0x1F \
            or register_1 < 0 or register_1 > 0x1F:
        raise MMC1PpuReferenceError("register value out of range")
    chr_mode = control // 16
    if chr_mode == 0:
        bank8k = (register_0 // 2) % chr_bank_count_8k
        return {"granule": 8192, "count": chr_bank_count_8k,
                "bank_0": bank8k, "bank_1": bank8k}
    count_4k = chr_bank_count_8k * 2
    return {"granule": 4096, "count": count_4k,
            "bank_0": register_0 % count_4k, "bank_1": register_1 % count_4k}


def reference_chr_offset(control: int, register_0: int, register_1: int,
                         chr_bank_count_8k: int, address: int) -> int:
    if address < 0 or address > 0x1FFF:
        raise MMC1PpuReferenceError("address outside CHR window")
    layout = reference_chr_banks(control, register_0, register_1,
                                 chr_bank_count_8k)
    if layout["granule"] == 8192:
        return layout["bank_0"] * 8192 + address
    if address < 0x1000:
        return layout["bank_0"] * 4096 + address
    return layout["bank_1"] * 4096 + (address - 0x1000)


def reference_mirroring_table(control: int, address: int) -> int:
    if address < 0x2000 or address > 0x3EFF:
        raise MMC1PpuReferenceError("address outside nametable window")
    mode = control % 4
    bit10 = (address // 0x400) % 2
    bit11 = (address // 0x800) % 2
    if mode == 0:
        return 0
    if mode == 1:
        return 1
    if mode == 2:
        return bit10
    return bit11


def reference_nametable_offset(control: int, address: int) -> int:
    table = reference_mirroring_table(control, address)
    return table * 1024 + (address % 1024)


__all__ = [
    "MMC1PpuReferenceError",
    "reference_chr_banks",
    "reference_chr_offset",
    "reference_mirroring_table",
    "reference_nametable_offset",
]
