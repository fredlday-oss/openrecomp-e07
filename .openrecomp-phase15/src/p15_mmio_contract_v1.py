#!/usr/bin/env python3
"""OpenRecomp Phase-15 bounded interrupt/peripheral MMIO contract V1.

A pure-Python executable model of the Phase-15 register semantics used by the
focused unit tests. It mirrors ``runtime/p15_mmio_extension_v1.c`` exactly so the
contract can be tested without a compiler and cross-checked against the C
fragment by the P15-01 gate.

The model defines explicit allowed access widths; an unsupported width fails
closed, and an unmodelled address is reported as unhandled so control falls
through to the frozen fail-closed platform boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "1.0.0"

STATUS_OK = 0
STATUS_UNHANDLED = -1000
STATUS_WIDTH_UNSUPPORTED = 2

I_STAT = 0x1F801070
I_MASK = 0x1F801074
SYS_CONTROL = 0x1F801020
D2_MADR = 0x1F8010A0
D2_BCR = 0x1F8010A4
D2_CHCR = 0x1F8010A8
DPCR = 0x1F8010F0
DICR = 0x1F8010F4

D2_CHCR_BUSY = 0x01000000

#: Allowed widths per register (see ``p15_surface_v1.MMIO_REGISTERS``).
ALLOWED_WIDTHS: dict[int, tuple[int, ...]] = {
    I_STAT: (16, 32),
    I_MASK: (16, 32),
    SYS_CONTROL: (32,),
    D2_MADR: (32,),
    D2_BCR: (32,),
    D2_CHCR: (32,),
    DPCR: (32,),
    DICR: (32,),
}

#: Registers that are part of the contract but hold no read-observable data.
ADDRESSES = frozenset(ALLOWED_WIDTHS)


@dataclass
class MmioModel:
    """Deterministic bounded register model with a bounded access transcript."""

    i_stat: int = 0
    i_mask: int = 0
    sys_control: int = 0
    d2_madr: int = 0
    d2_bcr: int = 0
    d2_chcr: int = 0
    dpcr: int = 0
    dicr: int = 0
    reads: int = 0
    writes: int = 0
    unsupported: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    capacity: int = 4096

    def _record(self, address: int, width_bits: int, is_write: int, value: int) -> None:
        if len(self.events) < self.capacity:
            self.events.append({
                "address": address,
                "width_bits": width_bits,
                "is_write": is_write,
                "value": value,
            })

    def read(self, address: int, width_bits: int) -> tuple[int, int]:
        """Return ``(status, value)`` for one guest read."""
        if address not in ALLOWED_WIDTHS:
            return STATUS_UNHANDLED, 0
        if width_bits not in ALLOWED_WIDTHS[address]:
            self.unsupported += 1
            return STATUS_WIDTH_UNSUPPORTED, 0
        if address == I_STAT:
            value = self.i_stat
        elif address == I_MASK:
            value = self.i_mask
        elif address == SYS_CONTROL:
            value = self.sys_control
        elif address == D2_MADR:
            value = self.d2_madr
        elif address == D2_BCR:
            value = self.d2_bcr
        elif address == D2_CHCR:
            value = self.d2_chcr
        elif address == DICR:
            value = self.dicr
        else:
            value = self.dpcr
        if width_bits == 16:
            value &= 0xFFFF
        self._record(address, width_bits, 0, value)
        self.reads += 1
        return STATUS_OK, value

    def write(self, address: int, width_bits: int, value: int) -> int:
        """Return the status for one guest write."""
        if address not in ALLOWED_WIDTHS:
            return STATUS_UNHANDLED
        if width_bits not in ALLOWED_WIDTHS[address]:
            self.unsupported += 1
            return STATUS_WIDTH_UNSUPPORTED
        if address == I_STAT:
            self.i_stat &= (value & 0xFFFF)
        elif address == I_MASK:
            self.i_mask = value & 0xFFFF
        elif address == SYS_CONTROL:
            self.sys_control = value & 0xFFFFFFFF
        elif address == D2_MADR:
            self.d2_madr = value & 0xFFFFFFFF
        elif address == D2_BCR:
            self.d2_bcr = value & 0xFFFFFFFF
        elif address == D2_CHCR:
            self.d2_chcr = (value & 0xFFFFFFFF) & ~D2_CHCR_BUSY
        elif address == DICR:
            self.dicr = value & 0xFFFFFFFF
        else:
            self.dpcr = value & 0xFFFFFFFF
        self._record(address, width_bits, 1, value & 0xFFFFFFFF)
        self.writes += 1
        return STATUS_OK

    def digest(self) -> int:
        value = 0xCBF29CE484222325
        for event in self.events:
            encoded = (
                (event["width_bits"] & 0xFF)
                | ((event["is_write"] & 0xFF) << 8)
                | ((event["address"] & 0xFFFFFFFF) << 16)
                | ((event["value"] & 0xFFFFFFFF) << 48)
            )
            for byte in range(16):
                value ^= (encoded >> (8 * byte)) & 0xFF
                value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        return value


def contract_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase15-interrupt-mmio-contract-v1",
        "contract_version": CONTRACT_VERSION,
        "registers": {
            f"0x{address:08x}": list(widths)
            for address, widths in sorted(ALLOWED_WIDTHS.items())
        },
        "status": {
            "ok": STATUS_OK,
            "unhandled": STATUS_UNHANDLED,
            "width_unsupported": STATUS_WIDTH_UNSUPPORTED,
        },
        "d2_chcr_busy_bit": f"0x{D2_CHCR_BUSY:08x}",
        "cpu_interrupt_delivery": "NOT_MODELED",
        "third_party_code_imported": "NO",
    }
