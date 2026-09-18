#!/usr/bin/env python3
"""Independent reference model for the Phase-6 MMC1 serial protocol.

Independently structured from `p6_mmc1_serial_v1`: the shift register is kept
as an explicit list of received bits, commits are assembled bit-by-bit, and the
write window is checked with a different predicate. It implements the same
audited `MMC1_SUBSET_V1` contract and exists only for differential testing; it
is never used by the runtime.
"""
from __future__ import annotations

from typing import Any

WINDOW_START = 0x8000
WINDOW_END = 0xFFFF
NAMES = ["control", "chr_bank_0", "chr_bank_1", "prg_bank"]
INITIAL = [0x0C, 0, 0, 0]


class MMC1ReferenceError(ValueError):
    """Reference-model fail-closed error (malformed input)."""


class MMC1SerialReference:
    def __init__(self) -> None:
        self.reg = list(INITIAL)
        self.bits: list[int] = []
        self.previous_cycle: int | None = None

    def _validate(self, address: int, value: int, cpu_cycle: int) -> None:
        if type(address) is not int or type(value) is not int or type(cpu_cycle) is not int:
            raise MMC1ReferenceError("write fields must be plain integers")
        if not (WINDOW_START <= address <= WINDOW_END):
            raise MMC1ReferenceError("address outside write window")
        if value < 0 or value > 255:
            raise MMC1ReferenceError("value outside byte range")
        if cpu_cycle < 0:
            raise MMC1ReferenceError("negative cycle")

    def write(self, address: int, value: int, cpu_cycle: int) -> dict[str, Any]:
        self._validate(address, value, cpu_cycle)
        result: dict[str, Any] = {
            "address": address,
            "value": value,
            "cpu_cycle": cpu_cycle,
            "register": None,
        }
        if self.previous_cycle is not None and cpu_cycle - self.previous_cycle == 1:
            result["action"] = "suppressed"
            return result
        self.previous_cycle = cpu_cycle
        bits = bin(value)[2:].zfill(8)
        if bits[0] == "1":
            self.bits = []
            result["action"] = "reset_shift"
            return result
        self.bits.append(int(bits[-1]))
        if len(self.bits) < 5:
            result["action"] = "shift"
            result["register"] = NAMES[address // 0x2000 - 4]
            return result
        number = 0
        for position, bit in enumerate(self.bits):
            number += bit * (2 ** position)
        slot = address // 0x2000 - 4
        self.reg[slot] = number
        self.bits = []
        result["action"] = "commit"
        result["register"] = NAMES[slot]
        result["register_value"] = number
        return result

    def snapshot(self) -> dict[str, Any]:
        registers = dict(zip(NAMES, self.reg))
        shift = 0
        for position, bit in enumerate(self.bits):
            shift += bit * (2 ** position)
        return {
            "registers": registers,
            "shift": shift,
            "count": len(self.bits),
            "last_write_cycle": self.previous_cycle,
        }


__all__ = ["MMC1ReferenceError", "MMC1SerialReference"]
