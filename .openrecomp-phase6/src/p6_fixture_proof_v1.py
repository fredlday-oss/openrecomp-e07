#!/usr/bin/env python3
"""Deterministic builder for the Phase-6 public MMC1 proof fixture.

Assembles `.openrecomp-phase6/fixture/p6_public_mmc1_proof.asm` with the
original frozen Phase-5 assembler (read-only), cross-checks every assembled
instruction against the frozen OpenRecomp NES6502 decoder, and packs the
documented MMC1/mapper-1 proof image:

* 4 x 16 KiB PRG banks (64 KiB): bank 3 is the fixed last bank with the
  program and vectors; banks 0..2 carry original deterministic data used by
  the PRG-bank-switching exercise;
* 4 x 8 KiB CHR banks (32 KiB) with the original deterministic pattern;
* horizontal mirroring in the header; the program explicitly writes all four
  MMC1 register windows and switches PRG banks, CHR 4 KiB banks and mirroring
  modes.

The builder is pure: it returns bytes and a metadata document and never writes
files. The proof fixture is original Apache-2.0 work with no third-party or
console-derived program data. The P6-01 established fixture remains frozen and
is built by `p6_fixture_build_v1`.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402,F401
from p5_fixture_asm_v1 import AssemblyError  # noqa: E402
import p6_fixture_build_v1 as base_fixture  # noqa: E402

ASM_PATH = ROOT / ".openrecomp-phase6" / "fixture" / "p6_public_mmc1_proof.asm"
ASSEMBLER_PATH = ROOT / ".openrecomp-phase5" / "src" / "p5_fixture_asm_v1.py"

FIXED_ORIGIN = 0xC000
FIXED_BANK_INDEX = 3
PRG_BANKS = 4
CHR_BANKS = 4
PRG_SIZE = PRG_BANKS * 0x4000
CHR_SIZE = CHR_BANKS * 0x2000
MAGIC = b"NES\x1a"

FLAGS6 = 0x10
FLAGS7 = 0x00

_A16_READS = {"lda", "ldx", "ldy", "adc", "sbc", "and", "ora", "eor",
              "cmp", "cpx", "cpy", "bit"}
_A16_WRITES = {"sta", "stx", "sty"}
_A16_RMW = {"inc", "dec", "asl", "lsr", "rol", "ror"}
_MMC1_WINDOWS = {0x8000, 0xA000, 0xC000, 0xE000}


class ProofFixtureBuildError(ValueError):
    """Fail-closed proof fixture build error."""


def proof_data_bank(bank: int) -> bytes:
    """Original deterministic proof data bank (16 KiB)."""
    if not 0 <= bank < PRG_BANKS - 1:
        raise ProofFixtureBuildError(f"data bank index {bank} out of range")
    data = bytearray(0x4000)
    for index in range(len(data)):
        data[index] = (index * 0x2B + bank * 0x61 + 0x0F) & 0xFF
    data[0x0000] = 0x10 + bank
    data[0x0100] = 0x40 + bank
    return bytes(data)


def _behaviour_inventory(result) -> dict:
    reads: dict[int, int] = {}
    writes: dict[int, int] = {}
    rmw: dict[int, int] = {}
    indirect: dict[int, int] = {}
    histogram: dict[str, int] = {}
    for instruction in result.instructions:
        key = f"{instruction.mnemonic} {instruction.mode}"
        histogram[key] = histogram.get(key, 0) + 1
        if instruction.mode in ("abs", "absx", "absy"):
            address = int.from_bytes(instruction.bytes[1:3], "little")
            target = None
            if instruction.mnemonic in _A16_READS:
                target = reads
            elif instruction.mnemonic in _A16_WRITES:
                target = writes
            elif instruction.mnemonic in _A16_RMW:
                target = rmw
            if target is not None:
                target[address] = target.get(address, 0) + 1
        elif instruction.mode == "ind":
            address = int.from_bytes(instruction.bytes[1:3], "little")
            indirect[address] = indirect.get(address, 0) + 1

    def hex_map(document: dict[int, int]) -> dict[str, int]:
        return {f"0x{address:04x}": count
                for address, count in sorted(document.items())}

    return {
        "instruction_count": len(result.instructions),
        "opcode_form_count": len(histogram),
        "opcode_histogram": dict(sorted(histogram.items())),
        "reads": hex_map(reads),
        "writes": hex_map(writes),
        "read_modify_write": hex_map(rmw),
        "indirect_targets": hex_map(indirect),
        "mmc1_write_windows": sorted(
            f"0x{address:04x}" for address in writes if address in _MMC1_WINDOWS),
        "ppu_writes": sorted(
            f"0x{address:04x}" for address in writes
            if 0x2000 <= address <= 0x2007 or address == 0x4014),
        "ppu_reads": sorted(
            f"0x{address:04x}" for address in reads
            if address in (0x2002, 0x2007)),
        "controller_reads": sorted(
            f"0x{address:04x}" for address in reads if address == 0x4016),
        "switchable_window_reads": sorted(
            f"0x{address:04x}" for address in reads
            if 0x8000 <= address <= 0xBFFF),
        "exit_thunk": sorted(
            f"0x{address:04x}" for address in indirect if address == 0x02FF),
    }


def build_from_source(source: str) -> tuple[bytes, dict]:
    try:
        result = base_fixture.assemble(source, origin=FIXED_ORIGIN)
    except AssemblyError as exc:
        raise ProofFixtureBuildError(f"assembly failed: {exc}") from exc
    if result.origin != FIXED_ORIGIN or result.end != 0x10000:
        raise ProofFixtureBuildError(
            f"fixed bank layout 0x{result.origin:04x}-0x{result.end:04x} "
            "does not cover $C000-$FFFF")
    if len(result.image) != 0x4000:
        raise ProofFixtureBuildError("fixed bank is not 16 KiB")
    try:
        cross_check = base_fixture._cross_check(result.image, result)
    except base_fixture.FixtureBuildError as exc:
        raise ProofFixtureBuildError(f"decoder cross-check failed: {exc}") from exc

    vectors = {
        "nmi": int.from_bytes(result.image[-6:-4], "little"),
        "reset": int.from_bytes(result.image[-4:-2], "little"),
        "irq": int.from_bytes(result.image[-2:], "little"),
    }
    for name, label in (("nmi", "nmi_handler"), ("reset", "reset"),
                        ("irq", "irq_handler")):
        if result.labels.get(label) != vectors[name]:
            raise ProofFixtureBuildError(
                f"{name} vector 0x{vectors[name]:04x} does not match label {label}")

    data_banks = [proof_data_bank(index) for index in range(PRG_BANKS - 1)]
    prg_banks = data_banks + [result.image]
    prg = b"".join(prg_banks)
    chr_bytes = base_fixture.chr_pattern()
    header = bytes([0x4E, 0x45, 0x53, 0x1A, PRG_BANKS, CHR_BANKS, FLAGS6, FLAGS7,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    rom = header + prg + chr_bytes
    metadata = {
        "stage": "P6-06",
        "fixture": "openrecomp-phase6-public-mmc1-proof-fixture",
        "claim": "MMC1_SUBSET_V1",
        "license": "Apache-2.0",
        "origin": "original",
        "source": ".openrecomp-phase6/fixture/p6_public_mmc1_proof.asm",
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "assembler": ".openrecomp-phase5/src/p5_fixture_asm_v1.py",
        "assembler_sha256": hashlib.sha256(ASSEMBLER_PATH.read_bytes()).hexdigest(),
        "decoder_cross_check": "adapters/nes6502.py",
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "rom_size": len(rom),
        "header_hex": header.hex(),
        "mapper": 1,
        "submapper": 0,
        "mirroring": "horizontal",
        "power_on_control": 0x0C,
        "prg_sha256": hashlib.sha256(prg).hexdigest(),
        "prg_size": len(prg),
        "prg_banks": PRG_BANKS,
        "prg_bank_sha256": [hashlib.sha256(bank).hexdigest() for bank in prg_banks],
        "chr_sha256": hashlib.sha256(chr_bytes).hexdigest(),
        "chr_size": len(chr_bytes),
        "chr_banks": CHR_BANKS,
        "fixed_bank_index": FIXED_BANK_INDEX,
        "fixed_bank_origin": FIXED_ORIGIN,
        "vectors": vectors,
        "labels": result.labels,
        "instruction_count": len(result.instructions),
        "instructions_cross_checked": cross_check["instructions_checked"],
        "data_spans": result.data_spans,
        "behaviour": _behaviour_inventory(result),
    }
    return rom, metadata


def build_proof() -> tuple[bytes, dict]:
    source = ASM_PATH.read_text(encoding="utf-8")
    return build_from_source(source)


if __name__ == "__main__":
    try:
        document_rom, document_metadata = build_proof()
    except ProofFixtureBuildError as exc:
        print(f"P6_PROOF_FIXTURE_BUILD=FAIL {exc}", file=sys.stderr)
        raise SystemExit(2)
    import json
    print(json.dumps(document_metadata, indent=2, sort_keys=True))
    raise SystemExit(0)
