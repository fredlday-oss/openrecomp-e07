#!/usr/bin/env python3
"""Phase-6 MMC1 PRG-RAM contract and variant boundary (P6-05).

The supported `MMC1_SUBSET_V1` cartridge profile declares no PRG-RAM/NVRAM and
no battery. This module implements exactly that contract and nothing more:

* the `$6000-$7FFF` window is disabled; reads and writes fail closed;
* construction fails closed when an image declares PRG-RAM/NVRAM or a battery,
  because that board wiring is not proven by the audited cartridges;
* the variant ledger classifies unsupported MMC1 board variants/features
  explicitly and never infers wiring from private-image behaviour.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT / ".openrecomp-phase6" / "src"),):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_mmc1_spec_v1 as mmc1_spec  # noqa: E402

PRG_RAM_BASE = 0x6000
PRG_RAM_END = 0x7FFF
PRG_RAM_WINDOW_BYTES = 0x2000
SUPPORTED_PROFILE = "discrete_mmc1_chr_rom_no_wram"

VARIANT_STATUSES = ("SUPPORTED", "UNSUPPORTED", "NOT_TESTED")

_VARIANT_LEDGER: tuple[dict[str, Any], ...] = (
    {"id": "V-001", "status": "SUPPORTED",
     "name": "base discrete MMC1 with CHR ROM, no PRG-RAM/NVRAM/battery",
     "requirement": "mapper 1, submapper 0, power-of-two PRG/CHR bank counts, "
                    "declared PRG-RAM/NVRAM 0, no battery",
     "basis": "the supported `MMC1_SUBSET_V1` profile and the audited fixtures"},
    {"id": "V-002", "status": "UNSUPPORTED",
     "name": "MMC1A/MMC1B/MMC1C discrete implementation differences",
     "requirement": "revision-specific serial/reset behaviour",
     "basis": "no revision differential board evidence; never inferred"},
    {"id": "V-003", "status": "UNSUPPORTED",
     "name": "CHR-RAM boards (SNROM/SXROM-like)",
     "requirement": "CHR-RAM banking and enable wiring",
     "basis": "the audited fixtures use CHR ROM; wiring never inferred"},
    {"id": "V-004", "status": "UNSUPPORTED",
     "name": "PRG-RAM/battery boards (SOROM/SXROM-like)",
     "requirement": "PRG-RAM enable and battery-backed NVRAM",
     "basis": "the supported profile declares no PRG-RAM/NVRAM"},
    {"id": "V-005", "status": "UNSUPPORTED",
     "name": "SUROM 512 KiB PRG wiring",
     "requirement": "512 KiB PRG bank selection beyond the supported range",
     "basis": "explicit range bound; wiring never inferred"},
    {"id": "V-006", "status": "UNSUPPORTED",
     "name": "SOROM/SXROM 512 KiB hybrids",
     "requirement": "512 KiB PRG plus PRG-RAM",
     "basis": "outside the supported range and profile"},
    {"id": "V-007", "status": "UNSUPPORTED",
     "name": "four-screen nametable boards",
     "requirement": "four-screen layout",
     "basis": "classified fail-closed by the ingestion contract"},
    {"id": "V-008", "status": "UNSUPPORTED",
     "name": "VS UniSystem and PlayChoice boards",
     "requirement": "arcade hardware registers",
     "basis": "out of scope; classified fail-closed"},
    {"id": "V-009", "status": "UNSUPPORTED",
     "name": "non-power-of-two PRG/CHR bank counts",
     "requirement": "masking of unwired address lines",
     "basis": "deliberate power-of-two bound; no audited fixture requires it"},
    {"id": "V-010", "status": "UNSUPPORTED",
     "name": "non-zero NES 2.0 submapper",
     "requirement": "variant-specific submapper wiring",
     "basis": "submapper is a declaration, not proven board wiring"},
    {"id": "V-011", "status": "NOT_TESTED",
     "name": "MMC1 clone/FPGA implementations",
     "requirement": "clone-specific timing and reset behaviour",
     "basis": "no clone hardware or differential evidence available"},
    {"id": "V-012", "status": "UNSUPPORTED",
     "name": "write-protection and board-specific bus conflicts",
     "requirement": "board wiring beyond the declared header",
     "basis": "never inferred from cartridge metadata"},
)

_REASON_LABELS = {
    "chr_ram": "CHR-RAM board",
    "chr_rom_absent": "CHR-RAM board",
    "battery_or_prg_ram": "PRG-RAM/battery board",
    "prg_ram_declared": "PRG-RAM/battery board",
    "submapper_nonzero": "non-zero submapper variant",
    "prg_size_out_of_supported_range": "PRG size outside the supported range",
    "chr_size_out_of_supported_range": "CHR size outside the supported range",
    "prg_bank_count_not_power_of_two": "non-power-of-two PRG wiring",
    "chr_bank_count_not_power_of_two": "non-power-of-two CHR wiring",
    "four_screen_nametable_layout": "four-screen board",
    "vs_unisystem": "VS UniSystem board",
    "playchoice": "PlayChoice board",
}


class MMC1PrgRamError(ValueError):
    """Fail-closed MMC1 PRG-RAM contract error."""


class MMC1PrgRamWindow:
    """The supported profile's disabled `$6000-$7FFF` PRG-RAM window."""

    def __init__(self, inventory: dict[str, Any]) -> None:
        if not isinstance(inventory, dict):
            raise MMC1PrgRamError("inventory must be a document")
        declared = int(inventory.get("prg_ram_bytes") or 0)
        battery = bool(inventory.get("battery"))
        self.declared_bytes = declared
        self.battery = battery
        self.enabled = False
        if declared > 0 or battery:
            raise MMC1PrgRamError(
                f"declared PRG-RAM ({declared} bytes) / battery ({battery}) is "
                "an unsupported MMC1 variant feature; the supported profile "
                "declares none and its wiring is never inferred")

    def present(self) -> bool:
        return False

    def _check(self, address: int) -> int:
        if isinstance(address, bool) or not isinstance(address, int):
            raise MMC1PrgRamError("address must be an integer")
        if not PRG_RAM_BASE <= address <= PRG_RAM_END:
            raise MMC1PrgRamError(
                f"address 0x{address:04x} outside the PRG-RAM window "
                f"${PRG_RAM_BASE:04x}-${PRG_RAM_END:04x}")
        return address

    def read(self, address: int) -> int:
        self._check(address)
        raise MMC1PrgRamError(
            f"PRG-RAM read at 0x{address:04x} but the supported profile has no "
            "PRG-RAM")

    def write(self, address: int, value: int) -> None:
        self._check(address)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFF:
            raise MMC1PrgRamError("value must be an 8-bit integer")
        raise MMC1PrgRamError(
            f"PRG-RAM write at 0x{address:04x} but the supported profile has no "
            "PRG-RAM")

    def status(self) -> dict[str, Any]:
        return {
            "profile": SUPPORTED_PROFILE,
            "prg_ram_enabled": self.enabled,
            "declared_bytes": self.declared_bytes,
            "battery": self.battery,
            "window": [PRG_RAM_BASE, PRG_RAM_END],
        }


def variant_ledger() -> list[dict[str, Any]]:
    return [dict(entry) for entry in _VARIANT_LEDGER]


def classify_variant(inventory: dict[str, Any]) -> dict[str, Any]:
    """Classify one inventory document at the board-variant boundary."""
    base = mmc1_spec.classify(inventory)
    report: dict[str, Any] = {
        "profile": SUPPORTED_PROFILE,
        "mapper": base["mapper"],
        "reasons": list(base["reasons"]),
        "variant_labels": sorted({_REASON_LABELS.get(reason, reason)
                                  for reason in base["reasons"]}),
        "claim": "MMC1_SUBSET_V1",
    }
    if base["status"] == "SUPPORTED_MMC1":
        report["status"] = "SUPPORTED_PROFILE"
    elif base["status"] == "BLOCKED_UNSUPPORTED_MAPPER":
        report["status"] = "BLOCKED_UNSUPPORTED_MAPPER"
    else:
        report["status"] = "BLOCKED_UNSUPPORTED_MMC1_VARIANT"
    return report


__all__ = [
    "MMC1PrgRamError",
    "MMC1PrgRamWindow",
    "PRG_RAM_BASE",
    "PRG_RAM_END",
    "PRG_RAM_WINDOW_BYTES",
    "SUPPORTED_PROFILE",
    "VARIANT_STATUSES",
    "classify_variant",
    "variant_ledger",
]
