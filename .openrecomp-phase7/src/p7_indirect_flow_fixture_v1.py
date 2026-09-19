#!/usr/bin/env python3
"""Deterministic builder for the original Phase-7 indirect-flow fixture.

Builds a full MMC1/mapper-1 NES image:
4 x 16 KiB PRG (bank 1: dispatch sites and table, bank 3 fixed: reset and
run-exit), 1 x 8 KiB CHR, horizontal mirroring. Original Apache-2.0 work with
a deterministic, pure builder. No third-party or console-derived data.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402
import p6_frontier_v1 as frontier  # noqa: E402
import p6_ines_v1 as ingestion  # noqa: E402
from p5_fixture_asm_v1 import AssemblyError, assemble  # noqa: E402

FIXED_ASM = ROOT / ".openrecomp-phase7" / "fixture" / "p7_indirect_flow_fixture.asm"
BANK_ASM = ROOT / ".openrecomp-phase7" / "fixture" / "p7_indirect_flow_bank.asm"

FIXED_ORIGIN = 0xC000
LOW_ORIGIN = 0x8000
FIXED_BANK_INDEX = 3
PRG_BANKS = 4
CHR_BANKS = 1
PRG_BANK_SIZE = 0x4000
CHR_SIZE = 0x2000
HEADER_SIZE = 16
FLAGS6 = 0x10

EXPECTED_MARKERS = {
    0: {"kind": 0xE0, "target": 0x01, "fixed": 0xF0},
    1: {"kind": 0xF2, "target": 0x02, "fixed": 0xF0},
    2: {"kind": 0x00, "target": 0x00, "fixed": 0xF0},
}

def _indirect_sites(result) -> list[int]:
    sites = []
    for instruction in result.instructions:
        if instruction.mnemonic == "jmp" and instruction.mode == "ind":
            if instruction.bytes[1:] != bytes([0xE2, 0x00]):
                raise IndirectFixtureError(
                    f"indirect site 0x{instruction.address:04x} does not use "
                    "the $00E2 pointer")
            sites.append(instruction.address)
    return sites


class IndirectFixtureError(ValueError):
    """Fail-closed fixture build error."""


def _data_bank(bank: int) -> bytes:
    return bytes(((index * 0x21 + bank * 0x4B + 7) & 0xFF)
                 for index in range(PRG_BANK_SIZE))


def _assemble(source: str, origin: int, size: int) -> bytes:
    try:
        result = assemble(source, origin=origin)
    except AssemblyError as exc:
        raise IndirectFixtureError(f"assembly failed: {exc}") from exc
    if result.origin != origin:
        raise IndirectFixtureError("assembled origin mismatch")
    if len(result.image) > size:
        raise IndirectFixtureError("assembled image exceeds the bank size")
    return bytes(result.image) + b"\x00" * (size - len(result.image))


def _cross_check(image: bytes, result, origin: int) -> int:
    memory = bytearray(0x10000)
    memory[origin:origin + len(image)] = image
    for instruction in result.instructions:
        decoded = nes_adapter.decode_full(memory, instruction.address)
        if decoded["op"] != instruction.mnemonic \
                or decoded["length"] != len(instruction.bytes):
            raise IndirectFixtureError(
                f"cross-check mismatch at 0x{instruction.address:04x}")
    return len(result.instructions)


def build() -> tuple[bytes, dict]:
    fixed_source = FIXED_ASM.read_text(encoding="utf-8")
    bank_source = BANK_ASM.read_text(encoding="utf-8")
    try:
        fixed_result = assemble(fixed_source, origin=FIXED_ORIGIN)
        bank_result = assemble(bank_source, origin=LOW_ORIGIN)
    except AssemblyError as exc:
        raise IndirectFixtureError(f"assembly failed: {exc}") from exc
    if fixed_result.end != 0x10000:
        raise IndirectFixtureError("fixed bank must span $C000-$FFFF")
    fixed_checked = _cross_check(fixed_result.image, fixed_result, FIXED_ORIGIN)
    bank_checked = _cross_check(bank_result.image, bank_result, LOW_ORIGIN)

    selector_immediate = None
    instructions = fixed_result.instructions
    for index, instruction in enumerate(instructions[:-1]):
        if instruction.mnemonic == "lda" and instruction.mode == "imm":
            nxt = instructions[index + 1]
            if nxt.mnemonic == "sta" and nxt.mode == "zp" \
                    and nxt.bytes[1] == 0x10:
                selector_immediate = instruction.address + 1
    if selector_immediate is None:
        raise IndirectFixtureError("selector immediate was not found")
    sites = _indirect_sites(bank_result)
    if len(sites) != 3:
        raise IndirectFixtureError(
            f"expected exactly three indirect sites, found {len(sites)}")

    banks = [_data_bank(0),
             _assemble(bank_source, LOW_ORIGIN, PRG_BANK_SIZE),
             _data_bank(2),
             bytes(fixed_result.image)]
    prg = b"".join(banks)
    chr_bytes = bytes(((index * 0x17 + 0x33) & 0xFF)
                      for index in range(CHR_SIZE))
    header = bytes([0x4E, 0x45, 0x53, 0x1A, PRG_BANKS, CHR_BANKS, FLAGS6,
                    0, 0, 0, 0, 0, 0, 0, 0, 0])
    rom = header + prg + chr_bytes

    labels = dict(fixed_result.labels)
    labels.update(bank_result.labels)
    run_exit = labels.get("run_exit")
    if run_exit is None:
        raise IndirectFixtureError("run_exit label is missing")
    vectors = {
        "nmi": int.from_bytes(fixed_result.image[-6:-4], "little"),
        "reset": int.from_bytes(fixed_result.image[-4:-2], "little"),
        "irq": int.from_bytes(fixed_result.image[-2:], "little"),
    }
    metadata = {
        "stage": "P7-07",
        "fixture": "openrecomp-phase7-indirect-flow-fixture",
        "license": "Apache-2.0",
        "origin": "original",
        "sources": [".openrecomp-phase7/fixture/p7_indirect_flow_fixture.asm",
                    ".openrecomp-phase7/fixture/p7_indirect_flow_bank.asm"],
        "source_sha256": hashlib.sha256(
            (fixed_source + "\n" + bank_source).encode("utf-8")).hexdigest(),
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "rom_size": len(rom),
        "mapper": 1,
        "mirroring": "horizontal",
        "prg_sha256": hashlib.sha256(prg).hexdigest(),
        "prg_size": len(prg),
        "prg_banks": PRG_BANKS,
        "chr_sha256": hashlib.sha256(chr_bytes).hexdigest(),
        "chr_size": len(chr_bytes),
        "chr_banks": CHR_BANKS,
        "fixed_bank_index": FIXED_BANK_INDEX,
        "cpu_origin": FIXED_ORIGIN,
        "vectors": vectors,
        "labels": labels,
        "sites": sites,
        "selector_immediate_address": selector_immediate,
        "exit_site": run_exit,
        "instruction_count": fixed_checked + bank_checked,
        "instructions_cross_checked": fixed_checked + bank_checked,
        "expected_markers": {str(key): value
                             for key, value in EXPECTED_MARKERS.items()},
        "public_claim": "original Apache-2.0 public fixture for the bounded "
                        "indirect-control-flow resolution proof only",
    }
    return rom, metadata


def inventory(rom: bytes, *, source_label: str = "p7_public_fixture") -> dict:
    return ingestion.ingest(rom, source_label=source_label)


def cpu_image_for_bank(rom: bytes, inventory_document: dict,
                       bank: int) -> bytes:
    prg_size = int(inventory_document["prg_bytes"])
    prg_banks = prg_size // 0x4000
    if not 0 <= bank < prg_banks:
        raise IndirectFixtureError(f"bank {bank} out of range")
    prg = rom[16:16 + prg_size]
    image = bytearray(0x10000)
    image[0x8000:0xC000] = prg[bank * 0x4000:(bank + 1) * 0x4000]
    image[0xC000:0x10000] = prg[(prg_banks - 1) * 0x4000:prg_banks * 0x4000]
    return bytes(image)


def patched_rom(rom: bytes, metadata: dict, selector: int) -> bytes:
    if isinstance(selector, bool) or not isinstance(selector, int) \
            or not 0 <= selector <= 0xFF:
        raise IndirectFixtureError("selector must be an 8-bit integer")
    address = metadata["selector_immediate_address"]
    offset = (HEADER_SIZE + FIXED_BANK_INDEX * PRG_BANK_SIZE
              + (address - FIXED_ORIGIN))
    patched = bytearray(rom)
    patched[offset] = selector
    return bytes(patched)


__all__ = [
    "EXPECTED_MARKERS",
    "FIXED_ASM",
    "BANK_ASM",
    "IndirectFixtureError",
    "build",
    "cpu_image_for_bank",
    "inventory",
    "patched_rom",
]
