#!/usr/bin/env python3
"""Phase-6 MMC1 serial shift-register protocol (P6-02).

Implements the audited `MMC1_SUBSET_V1` write protocol as a deterministic
state machine over CPU cycle numbers:

* four 5-bit internal registers selected by CPU address bits 14:13;
* five writes commit a register, least-significant bit first;
* a write with bit 7 set resets the shift register;
* a write on the CPU cycle immediately after another MMC1 write is suppressed
  and leaves all state (including the last-write cycle) unchanged;
* power-on state: control register 0x0C, all other registers 0, shift register
  cleared;
* malformed writes (outside $8000-$FFFF, non-8-bit values, negative cycles)
  fail closed with `MMC1SerialError`.

This module deliberately implements only the register file and the serial
protocol. PRG/CHR mapping (P6-03/P6-04) and PRG-RAM (P6-05) are separate
stages and consume this state.
"""
from __future__ import annotations

from typing import Any

WRITE_WINDOW_MIN = 0x8000
WRITE_WINDOW_MAX = 0xFFFF

REGISTER_NAMES = ("control", "chr_bank_0", "chr_bank_1", "prg_bank")
POWER_ON_REGISTERS = (0x0C, 0x00, 0x00, 0x00)
SERIAL_BITS = 5


class MMC1SerialError(ValueError):
    """Fail-closed MMC1 serial-protocol error."""


def _require_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MMC1SerialError(f"{name} must be an integer")
    return value


def register_index(address: int) -> int:
    """Return the internal register index selected by address bits 14:13."""
    return (address >> 13) & 0x03


class MMC1Serial:
    """Deterministic MMC1 serial register file."""

    def __init__(self) -> None:
        self.registers: list[int] = list(POWER_ON_REGISTERS)
        self.shift: int = 0
        self.count: int = 0
        self.last_write_cycle: int | None = None

    def reset(self) -> None:
        self.registers = list(POWER_ON_REGISTERS)
        self.shift = 0
        self.count = 0
        self.last_write_cycle = None

    def state(self) -> dict[str, Any]:
        return {
            "registers": {name: self.registers[index]
                          for index, name in enumerate(REGISTER_NAMES)},
            "shift": self.shift,
            "count": self.count,
            "last_write_cycle": self.last_write_cycle,
        }

    def write(self, address: int, value: int, cpu_cycle: int) -> dict[str, Any]:
        address = _require_int("address", address)
        value = _require_int("value", value)
        cpu_cycle = _require_int("cpu_cycle", cpu_cycle)
        if not WRITE_WINDOW_MIN <= address <= WRITE_WINDOW_MAX:
            raise MMC1SerialError(
                f"address 0x{address:x} outside the $8000-$FFFF write window")
        if not 0 <= value <= 0xFF:
            raise MMC1SerialError(f"value {value} is not an 8-bit write")
        if cpu_cycle < 0:
            raise MMC1SerialError("cpu_cycle must not be negative")

        if self.last_write_cycle is not None and cpu_cycle == self.last_write_cycle + 1:
            return {
                "action": "suppressed",
                "address": address,
                "value": value,
                "cpu_cycle": cpu_cycle,
                "register": None,
            }
        self.last_write_cycle = cpu_cycle

        if value & 0x80:
            self.shift = 0
            self.count = 0
            return {
                "action": "reset_shift",
                "address": address,
                "value": value,
                "cpu_cycle": cpu_cycle,
                "register": None,
            }

        target = register_index(address)
        self.shift |= (value & 0x01) << self.count
        self.count += 1
        if self.count == SERIAL_BITS:
            committed = self.shift
            self.registers[target] = committed
            self.shift = 0
            self.count = 0
            return {
                "action": "commit",
                "address": address,
                "value": value,
                "cpu_cycle": cpu_cycle,
                "register": REGISTER_NAMES[target],
                "register_value": committed,
            }
        return {
            "action": "shift",
            "address": address,
            "value": value,
            "cpu_cycle": cpu_cycle,
            "register": REGISTER_NAMES[target],
        }


def register_value(serial: MMC1Serial, name: str) -> int:
    if name not in REGISTER_NAMES:
        raise MMC1SerialError(f"unknown MMC1 register {name!r}")
    return serial.registers[REGISTER_NAMES.index(name)]


__all__ = [
    "MMC1Serial",
    "MMC1SerialError",
    "POWER_ON_REGISTERS",
    "REGISTER_NAMES",
    "SERIAL_BITS",
    "WRITE_WINDOW_MAX",
    "WRITE_WINDOW_MIN",
    "register_index",
    "register_value",
]
