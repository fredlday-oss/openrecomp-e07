#!/usr/bin/env python3
"""Independent reference model for Phase-6 MMC1 PRG banking.

Independently structured from `p6_mapper1_prg_v1`: window selection is
computed with modulo arithmetic over explicit derived counts instead of
bit-mask expressions, and the control mode is decoded through a dispatch
table. It implements the same audited `MMC1_SUBSET_V1` contract and is used
only for differential testing.
"""
from __future__ import annotations

from typing import Any


class MMC1PrgReferenceError(ValueError):
    """Reference-model fail-closed error."""


VALID_BANK_COUNTS = {1, 2, 4, 8, 16}


def reference_window_banks(control: int, prg_register: int,
                           prg_bank_count: int) -> tuple[int, int]:
    if prg_bank_count not in VALID_BANK_COUNTS:
        raise MMC1PrgReferenceError("unsupported bank count")
    if control < 0 or control > 0x1F or prg_register < 0 or prg_register > 0x1F:
        raise MMC1PrgReferenceError("register value out of range")
    mode = (control // 4) % 4
    if mode in (0, 1):
        even = prg_register - (prg_register % 2)
        first = even % prg_bank_count
        second = (first + 1) % prg_bank_count
        return first, second
    if mode == 2:
        return 0, prg_register % prg_bank_count
    if mode == 3:
        return prg_register % prg_bank_count, prg_bank_count - 1
    raise MMC1PrgReferenceError("unreachable mode")


def reference_map_offset(control: int, prg_register: int, prg_bank_count: int,
                         address: int) -> int:
    if address < 0x8000 or address > 0xFFFF:
        raise MMC1PrgReferenceError("address outside PRG window")
    first, second = reference_window_banks(control, prg_register, prg_bank_count)
    slot = 0 if address < 0xC000 else 1
    bank = first if slot == 0 else second
    return bank * 16384 + (address % 16384)


def reference_layout(control: int, prg_register: int,
                     prg_bank_count: int) -> dict[str, Any]:
    first, second = reference_window_banks(control, prg_register, prg_bank_count)
    return {
        "prg_mode": (control // 4) % 4,
        "chr_mode": control // 16,
        "mirroring_bits": control % 4,
        "window_8000_bank": first,
        "window_c000_bank": second,
    }


__all__ = [
    "MMC1PrgReferenceError",
    "reference_layout",
    "reference_map_offset",
    "reference_window_banks",
]
