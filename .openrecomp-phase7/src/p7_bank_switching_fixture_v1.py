#!/usr/bin/env python3
"""Deterministic builder for the original Phase-7 bank-switching fixture.

Builds a full MMC1/mapper-1 NES image whose fixed last bank (bank 3) commits
PRG bank 1 and calls into the switchable window, with the switchable routine
calling back into a fixed-bank helper. 4 x 16 KiB PRG, 1 x 8 KiB CHR,
horizontal mirroring, original Apache-2.0 work. The builder is pure and never
writes files.
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

ASM_PATH = ROOT / ".openrecomp-phase7" / "fixture" / "p7_bank_switching_fixture.asm"
ASSEMBLER_PATH = ".openrecomp-phase5/src/p5_fixture_asm_v1.py"
DECODER_PATH = "adapters/nes6502.py"

FIXED_ORIGIN = 0xC000
LOW_ORIGIN = 0x8000
FIXED_BANK_INDEX = 3
PRG_BANKS = 4
CHR_BANKS = 1
PRG_BANK_SIZE = 0x4000
CHR_BANK_SIZE = 0x2000
PRG_SIZE = PRG_BANKS * PRG_BANK_SIZE
CHR_SIZE = CHR_BANKS * CHR_BANK_SIZE
HEADER_SIZE = 16

FLAGS6 = 0x10  # mapper 1, horizontal mirroring, no trainer/battery

_BANK_ONE_SOURCE = (
    ".equ MARK_A, $0300\n"
    ".org $8000\n"
    "bank_entry:\n"
    "        jsr $C100\n"
    "        lda #$77\n"
    "        sta MARK_A\n"
    "        rts\n"
)


class BankFixtureBuildError(ValueError):
    """Fail-closed bank-switching fixture build error."""


def _data_bank(bank: int) -> bytes:
    return bytes(((index * 0x2D + bank * 0x57 + 3) & 0xFF)
                 for index in range(PRG_BANK_SIZE))


def _assemble(source: str, origin: int, size: int) -> bytes:
    try:
        result = assemble(source, origin=origin)
    except AssemblyError as exc:
        raise BankFixtureBuildError(f"assembly failed: {exc}") from exc
    if result.origin != origin:
        raise BankFixtureBuildError("assembled origin mismatch")
    if len(result.image) > size:
        raise BankFixtureBuildError("assembled image exceeds the bank size")
    return bytes(result.image) + b"\x00" * (size - len(result.image))


def _simple_routine(marker: int) -> bytes:
    source = (f".org $8000\n"
              f"entry:\n"
              f"        lda #${marker:02X}\n"
              f"        sta $0303\n"
              f"        rts\n")
    return _assemble(source, LOW_ORIGIN, PRG_BANK_SIZE)


def _cross_check(image: bytes, result, origin: int) -> int:
    memory = bytearray(0x10000)
    memory[origin:origin + len(image)] = image
    memory[0x8000:0x8000 + len(image)] = image
    for instruction in result.instructions:
        decoded = nes_adapter.decode_full(memory, instruction.address)
        if decoded["op"] != instruction.mnemonic \
                or decoded["length"] != len(instruction.bytes):
            raise BankFixtureBuildError(
                f"cross-check mismatch at 0x{instruction.address:04x}")
    return len(result.instructions)


def build() -> tuple[bytes, dict]:
    fixed_source = ASM_PATH.read_text(encoding="utf-8")
    try:
        fixed_result = assemble(fixed_source, origin=FIXED_ORIGIN)
    except AssemblyError as exc:
        raise BankFixtureBuildError(f"assembly failed: {exc}") from exc
    if fixed_result.end != 0x10000 or len(fixed_result.image) != PRG_BANK_SIZE:
        raise BankFixtureBuildError("fixed bank must span $C000-$FFFF")
    fixed_checked = _cross_check(fixed_result.image, fixed_result, FIXED_ORIGIN)

    try:
        bank1_result = assemble(_BANK_ONE_SOURCE, origin=LOW_ORIGIN)
    except AssemblyError as exc:
        raise BankFixtureBuildError(f"bank 1 assembly failed: {exc}") from exc
    bank1 = bytes(bank1_result.image) + b"\x00" * (
        PRG_BANK_SIZE - len(bank1_result.image))
    bank1_checked = _cross_check(bank1_result.image, bank1_result, LOW_ORIGIN)

    banks = [_data_bank(0), bank1, _simple_routine(0x82), _data_bank(3)]
    banks[FIXED_BANK_INDEX] = fixed_result.image
    prg = b"".join(banks)

    chr_bytes = bytes(((index * 0x13 + 0x2F) & 0xFF)
                      for index in range(CHR_SIZE))
    header = bytes([0x4E, 0x45, 0x53, 0x1A, PRG_BANKS, CHR_BANKS, FLAGS6,
                    0, 0, 0, 0, 0, 0, 0, 0, 0])
    rom = header + prg + chr_bytes

    labels = dict(fixed_result.labels)
    labels.update(bank1_result.labels)
    exit_sites = [instruction.address for instruction in fixed_result.instructions
                  if instruction.mnemonic == "jmp" and instruction.mode == "ind"]
    if len(exit_sites) != 1:
        raise BankFixtureBuildError(
            f"expected exactly one indirect jmp run-exit thunk, found "
            f"{len(exit_sites)}")
    vectors = {
        "nmi": int.from_bytes(fixed_result.image[-6:-4], "little"),
        "reset": int.from_bytes(fixed_result.image[-4:-2], "little"),
        "irq": int.from_bytes(fixed_result.image[-2:], "little"),
    }
    source_bytes = fixed_source.encode("utf-8")
    metadata = {
        "stage": "P7-05",
        "fixture": "openrecomp-phase7-bank-switching-structure-fixture",
        "license": "Apache-2.0",
        "origin": "original",
        "source": ".openrecomp-phase7/fixture/p7_bank_switching_fixture.asm",
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "assembler": ASSEMBLER_PATH,
        "assembler_sha256": hashlib.sha256(
            (ROOT / ASSEMBLER_PATH).read_bytes()).hexdigest(),
        "decoder_cross_check": DECODER_PATH,
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "rom_size": len(rom),
        "mapper": 1,
        "mirroring": "horizontal",
        "prg_sha256": hashlib.sha256(prg).hexdigest(),
        "prg_size": len(prg),
        "prg_banks": PRG_BANKS,
        "prg_bank_sha256": [hashlib.sha256(bank).hexdigest() for bank in banks],
        "chr_sha256": hashlib.sha256(chr_bytes).hexdigest(),
        "chr_size": len(chr_bytes),
        "chr_banks": CHR_BANKS,
        "fixed_bank_index": FIXED_BANK_INDEX,
        "fixed_bank_origin": FIXED_ORIGIN,
        "cpu_origin": FIXED_ORIGIN,
        "vectors": vectors,
        "labels": labels,
        "instruction_count": fixed_checked + bank1_checked,
        "instructions_cross_checked": fixed_checked + bank1_checked,
        "selected_bank": 1,
        "cross_bank_calls": [
            {"src_bank": 3, "src_label": "reset", "dst_bank": 1,
             "dst_address": 0x8000, "kind": "call"},
            {"src_bank": 1, "src_address": 0x8000, "dst_bank": 3,
             "dst_address": 0xC100, "kind": "call"},
        ],
        "exit_site": exit_sites[0],
        "expected_runtime": {
            "markers": {"mark_a": 0x77, "mark_b": 0x77, "mark_c": 0x42},
            "exit_site": exit_sites[0],
            "note": "reset returns from the bank-1 routine with A=$77 and "
                    "stores it to MARK_B before the run-exit thunk",
        },
        "public_claim": "original Apache-2.0 public fixture for the bounded "
                        "bank-aware structure proof only",
    }
    return rom, metadata


def inventory(rom: bytes, *, source_label: str = "p7_public_fixture") -> dict:
    return ingestion.ingest(rom, source_label=source_label)


def cpu_image(rom: bytes, inventory_document: dict) -> bytes:
    metadata = {
        "rom_sha256": inventory_document["image_sha256"],
        "prg_size": inventory_document["prg_bytes"],
        "chr_size": inventory_document["chr_bytes"],
        "prg_banks": inventory_document["prg_bytes"] // 0x4000,
        "chr_banks": inventory_document["chr_bytes"] // 0x2000,
    }
    return frontier.build_mmc1_cpu_image(rom, metadata)


__all__ = [
    "ASM_PATH",
    "BankFixtureBuildError",
    "build",
    "cpu_image",
    "inventory",
]
