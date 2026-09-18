#!/usr/bin/env python3
"""Phase-6 MMC1/mapper-1 supported-subset definition and requirements inventory.

This module is the machine-readable, auditable boundary for the Phase-6 MMC1
platform path. It records what Phase 6 commits to implement, what it explicitly
does not support and which facts are documented MMC1 architectural behaviour
rather than guesses. It contains no execution model: P6-02 .. P6-05 implement
the serial protocol, PRG/CHR banking, mirroring and PRG-RAM contract behind
this boundary.
"""
from __future__ import annotations

from typing import Any

MAPPER = 1
SERIAL_BITS = 5

REGISTERS = (
    {"name": "control", "index": 0, "cpu_min": 0x8000, "cpu_max": 0x9FFF},
    {"name": "chr_bank_0", "index": 1, "cpu_min": 0xA000, "cpu_max": 0xBFFF},
    {"name": "chr_bank_1", "index": 2, "cpu_min": 0xC000, "cpu_max": 0xDFFF},
    {"name": "prg_bank", "index": 3, "cpu_min": 0xE000, "cpu_max": 0xFFFF},
)

MIRRORING = {
    0: "one_screen_lower",
    1: "one_screen_upper",
    2: "vertical",
    3: "horizontal",
}

PRG_MODES = {
    0: "32k_switch_at_8000_bank_low_bit_ignored",
    1: "32k_switch_at_8000_bank_low_bit_ignored",
    2: "fix_first_bank_at_8000_switch_16k_at_c000",
    3: "fix_last_bank_at_c000_switch_16k_at_8000",
}

CHR_MODES = {
    0: "8k_bank_from_register_1_shifted_right",
    1: "two_4k_banks_from_registers_1_and_2",
}

CONTROL_BITS = {
    "mirroring": {"shift": 0, "mask": 0x03},
    "prg_mode": {"shift": 2, "mask": 0x03},
    "chr_mode": {"shift": 4, "mask": 0x01},
}

# Documented MMC1 power-on state assumed by the audited contract: the shift
# register is cleared and the control register presents mode 3 (fix last bank
# at $C000), CHR mode 0 (8 KiB) and one-screen lower mirroring.
POWER_ON_CONTROL = 0x0C
POWER_ON_MIRRORING = "one_screen_lower"
POWER_ON_PRG_MODE = 3
POWER_ON_CHR_MODE = 0

MIN_PRG_BYTES = 0x4000
MAX_PRG_BYTES = 0x40000
MIN_CHR_ROM_BYTES = 0x2000
MAX_CHR_ROM_BYTES = 0x20000
PRG_BANK_BYTES = 0x4000
CHR_BANK_BYTES = 0x2000

REQUIREMENT_STATUSES = ("SUPPORTED", "UNSUPPORTED", "NOT_TESTED")

_REQUIREMENTS: tuple[dict[str, Any], ...] = (
    {"id": "MAP-001", "area": "mapper", "status": "SUPPORTED",
     "requirement": "iNES/NES 2.0 mapper number 1 only",
     "basis": "declared header field; unsupported mappers fail closed"},
    {"id": "MAP-002", "area": "mapper", "status": "SUPPORTED",
     "requirement": "submapper 0 only; non-zero submapper is classified unsupported",
     "basis": "declared NES 2.0 sub-field; variant wiring is never inferred"},
    {"id": "MAP-003", "area": "mapper", "status": "SUPPORTED",
     "requirement": "documented exact-size iNES/NES 2.0 containers without "
                    "extended-size forms",
     "basis": "Phase-5 ingestion contract, reused read-only"},
    {"id": "REG-001", "area": "serial", "status": "SUPPORTED",
     "requirement": "four 5-bit internal registers selected by CPU address "
                    "bits 14:13 across the $8000-$FFFF write window",
     "basis": "documented MMC1 register map"},
    {"id": "REG-002", "area": "serial", "status": "SUPPORTED",
     "requirement": "write bit 0 is the data bit; five writes commit the "
                    "register least-significant bit first",
     "basis": "documented MMC1 serial protocol"},
    {"id": "REG-003", "area": "serial", "status": "SUPPORTED",
     "requirement": "a write with bit 7 set resets the shift register",
     "basis": "documented MMC1 serial protocol"},
    {"id": "REG-004", "area": "serial", "status": "SUPPORTED",
     "requirement": "writes on consecutive CPU cycles are suppressed as "
                    "documented; the exact implementation is proven by P6-02 "
                    "differential vectors",
     "basis": "documented MMC1 write timing behaviour"},
    {"id": "REG-005", "area": "serial", "status": "SUPPORTED",
     "requirement": "power-on state: shift register cleared, control register "
                    "0x0C (PRG mode 3, CHR mode 0, one-screen lower), all "
                    "other registers 0",
     "basis": "documented MMC1 power-on state; audited bounded assumption"},
    {"id": "CTRL-001", "area": "control", "status": "SUPPORTED",
     "requirement": "mirroring bits 1:0 select one-screen lower/upper, "
                    "vertical and horizontal",
     "basis": "documented MMC1 control register"},
    {"id": "CTRL-002", "area": "control", "status": "SUPPORTED",
     "requirement": "PRG mode bits 3:2 select 32 KiB switch, fixed-first or "
                    "fixed-last 16 KiB mapping",
     "basis": "documented MMC1 control register"},
    {"id": "CTRL-003", "area": "control", "status": "SUPPORTED",
     "requirement": "CHR mode bit 4 selects one 8 KiB bank or two independent "
                    "4 KiB banks",
     "basis": "documented MMC1 control register"},
    {"id": "PRG-001", "area": "prg_banking", "status": "SUPPORTED",
     "requirement": "16 KiB bank selection from the low bits of the PRG "
                    "register to the switchable window",
     "basis": "documented MMC1 PRG banking"},
    {"id": "PRG-002", "area": "prg_banking", "status": "SUPPORTED",
     "requirement": "32 KiB mode ignores the low bank bit of the PRG register",
     "basis": "documented MMC1 PRG banking"},
    {"id": "PRG-003", "area": "prg_banking", "status": "SUPPORTED",
     "requirement": "PRG mode 2 fixes the first bank at $8000; PRG mode 3 "
                    "fixes the last bank at $C000",
     "basis": "documented MMC1 PRG banking"},
    {"id": "PRG-004", "area": "prg_banking", "status": "SUPPORTED",
     "requirement": "bank numbers mask to the declared PRG ROM bank count; "
                    "masking is proven by P6-03 bounded reference vectors",
     "basis": "declared ROM size and documented MMC1 wiring"},
    {"id": "PRG-005", "area": "prg_banking", "status": "SUPPORTED",
     "requirement": "PRG ROM sizes 16 KiB .. 256 KiB in exact 16 KiB banks "
                    "with a power-of-two bank count (1, 2, 4, 8, 16)",
     "basis": "supported-subset bound; larger or non-power-of-two ROMs fail closed"},
    {"id": "CHR-001", "area": "chr_banking", "status": "SUPPORTED",
     "requirement": "8 KiB CHR mode uses PRG-register-style bits of the CHR "
                    "bank 0 register shifted right by one",
     "basis": "documented MMC1 CHR banking"},
    {"id": "CHR-002", "area": "chr_banking", "status": "SUPPORTED",
     "requirement": "4 KiB CHR mode maps CHR bank 0 and CHR bank 1 registers "
                    "to the two 4 KiB PPU windows",
     "basis": "documented MMC1 CHR banking"},
    {"id": "CHR-003", "area": "chr_banking", "status": "SUPPORTED",
     "requirement": "CHR ROM sizes 8 KiB .. 128 KiB in exact 8 KiB banks",
     "basis": "supported-subset bound and declared header fields"},
    {"id": "RAM-001", "area": "prg_ram", "status": "SUPPORTED",
     "requirement": "supported fixture declares no PRG-RAM/NVRAM and no "
                    "battery; declared PRG-RAM fails closed until P6-05 "
                    "classifies the variant explicitly",
     "basis": "declared header fields; board wiring is never inferred"},
    {"id": "IRQ-001", "area": "interrupts", "status": "SUPPORTED",
     "requirement": "MMC1 contributes no interrupt source",
     "basis": "documented MMC1 behaviour"},
    {"id": "VAR-001", "area": "variants", "status": "UNSUPPORTED",
     "requirement": "MMC1A/MMC1B/MMC1C discrete implementation differences",
     "basis": "out of scope; no differential board evidence"},
    {"id": "VAR-002", "area": "variants", "status": "UNSUPPORTED",
     "requirement": "SUROM/SXROM/SOROM and 512 KiB PRG wiring variants",
     "basis": "out of scope; would require extra address-line wiring evidence"},
    {"id": "VAR-003", "area": "variants", "status": "UNSUPPORTED",
     "requirement": "CHR-RAM MMC1 boards",
     "basis": "out of scope for the audited fixtures"},
    {"id": "VAR-004", "area": "variants", "status": "UNSUPPORTED",
     "requirement": "four-screen, VS UniSystem and PlayChoice layouts",
     "basis": "out of scope; classified fail-closed"},
    {"id": "VAR-005", "area": "variants", "status": "UNSUPPORTED",
     "requirement": "write-protection, board-specific bus conflicts and "
                    "wiring not proven by cartridge evidence",
     "basis": "never inferred"},
)


class MMC1SpecError(ValueError):
    """Fail-closed MMC1 specification error."""


def requirements_inventory() -> list[dict[str, Any]]:
    return [dict(entry) for entry in _REQUIREMENTS]


def subset_document() -> dict[str, Any]:
    return {
        "claim": "MMC1_SUBSET_V1",
        "mapper": MAPPER,
        "serial_bits": SERIAL_BITS,
        "registers": [dict(entry) for entry in REGISTERS],
        "mirroring": dict(MIRRORING),
        "prg_modes": dict(PRG_MODES),
        "chr_modes": dict(CHR_MODES),
        "control_bits": {key: dict(value) for key, value in CONTROL_BITS.items()},
        "power_on": {
            "control": POWER_ON_CONTROL,
            "mirroring": POWER_ON_MIRRORING,
            "prg_mode": POWER_ON_PRG_MODE,
            "chr_mode": POWER_ON_CHR_MODE,
        },
        "limits": {
            "min_prg_bytes": MIN_PRG_BYTES,
            "max_prg_bytes": MAX_PRG_BYTES,
            "min_chr_rom_bytes": MIN_CHR_ROM_BYTES,
            "max_chr_rom_bytes": MAX_CHR_ROM_BYTES,
            "prg_bank_bytes": PRG_BANK_BYTES,
            "chr_bank_bytes": CHR_BANK_BYTES,
        },
        "requirements": requirements_inventory(),
    }


def classify(inventory: dict[str, Any]) -> dict[str, Any]:
    """Classify one inventory document against the supported MMC1 subset.

    Returns a deterministic classification. Unsupported or uncertain inputs are
    classified with explicit reason codes; no hardware behaviour is inferred.
    """
    mapper = int(inventory.get("mapper", -1))
    base = {
        "claim": "MMC1_SUBSET_V1",
        "mapper": mapper,
        "power_on_control": POWER_ON_CONTROL,
        "power_on_mirroring": POWER_ON_MIRRORING,
        "power_on_prg_mode": POWER_ON_PRG_MODE,
        "power_on_chr_mode": POWER_ON_CHR_MODE,
        "prg_banks_16k": 0,
        "chr_banks_8k": 0,
        "mirroring": str(inventory.get("mirroring", "unknown")),
        "reasons": [],
    }
    if mapper != MAPPER:
        base["status"] = "BLOCKED_UNSUPPORTED_MAPPER"
        base["target"] = "unsupported_mapper"
        return base

    reasons: list[str] = []
    if int(inventory.get("submapper", 0)) != 0:
        reasons.append("submapper_nonzero")
    if inventory.get("unsupported_metadata"):
        reasons.extend(str(item) for item in inventory["unsupported_metadata"])
    if inventory.get("battery"):
        reasons.append("battery_or_prg_ram")
    if inventory.get("chr_is_ram"):
        reasons.append("chr_ram")
    if int(inventory.get("prg_ram_bytes", 0) or 0) != 0:
        reasons.append("prg_ram_declared")

    prg_bytes = int(inventory.get("prg_bytes", 0))
    chr_bytes = int(inventory.get("chr_bytes", 0))
    if prg_bytes < MIN_PRG_BYTES or prg_bytes > MAX_PRG_BYTES:
        reasons.append("prg_size_out_of_supported_range")
    elif prg_bytes % PRG_BANK_BYTES != 0:
        reasons.append("prg_size_not_16k_multiple")
    else:
        prg_banks = prg_bytes // PRG_BANK_BYTES
        if prg_banks & (prg_banks - 1) != 0:
            reasons.append("prg_bank_count_not_power_of_two")
    if chr_bytes == 0:
        reasons.append("chr_rom_absent")
    elif chr_bytes < MIN_CHR_ROM_BYTES or chr_bytes > MAX_CHR_ROM_BYTES:
        reasons.append("chr_size_out_of_supported_range")
    elif chr_bytes % CHR_BANK_BYTES != 0:
        reasons.append("chr_size_not_8k_multiple")

    base["prg_banks_16k"] = prg_bytes // PRG_BANK_BYTES
    base["chr_banks_8k"] = chr_bytes // CHR_BANK_BYTES
    if reasons:
        base["status"] = "BLOCKED_UNSUPPORTED_MMC1_VARIANT"
        base["target"] = "unsupported_mmc1_variant"
        base["reasons"] = sorted(set(reasons))
        return base
    base["status"] = "SUPPORTED_MMC1"
    base["target"] = "mmc1"
    return base


__all__ = [
    "CHR_MODES",
    "CHR_BANK_BYTES",
    "CONTROL_BITS",
    "MAPPER",
    "MAX_CHR_ROM_BYTES",
    "MAX_PRG_BYTES",
    "MIN_CHR_ROM_BYTES",
    "MIN_PRG_BYTES",
    "MIRRORING",
    "MMC1SpecError",
    "POWER_ON_CHR_MODE",
    "POWER_ON_CONTROL",
    "POWER_ON_MIRRORING",
    "POWER_ON_PRG_MODE",
    "PRG_BANK_BYTES",
    "PRG_MODES",
    "REGISTERS",
    "REQUIREMENT_STATUSES",
    "SERIAL_BITS",
    "classify",
    "requirements_inventory",
    "subset_document",
]
