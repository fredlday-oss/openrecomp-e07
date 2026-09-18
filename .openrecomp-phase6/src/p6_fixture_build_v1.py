#!/usr/bin/env python3
"""Deterministic builder for the original Phase-6 public MMC1 fixture.

Assembles `.openrecomp-phase6/fixture/p6_public_fixture.asm` with the original
frozen Phase-5 assembler (`p5_fixture_asm_v1`, imported read-only),
cross-checks every assembled instruction against the frozen OpenRecomp NES6502
decoder (`adapters.nes6502`), and packs a documented MMC1/mapper-1 iNES image:

* 4 x 16 KiB PRG banks (64 KiB), where bank 3 is the fixed last bank containing
  the code and vectors, and banks 0..2 are deterministic original data banks;
* 4 x 8 KiB CHR banks (32 KiB) with an original deterministic pattern;
* horizontal mirroring in the header; the reset program explicitly writes the
  MMC1 control/CHR/PRG registers.

The builder is pure: it returns bytes and a metadata document and never writes
files. The public fixture is original Apache-2.0 work with no third-party or
console-derived program data. P6-06 extends the fixture source for full
behavioural coverage; this module records the established P6-01 revision.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402
from p5_fixture_asm_v1 import AssemblyError, assemble  # noqa: E402

ASM_PATH = ROOT / ".openrecomp-phase6" / "fixture" / "p6_public_fixture.asm"

FIXED_ORIGIN = 0xC000
FIXED_BANK_INDEX = 3
PRG_BANKS = 4
CHR_BANKS = 4
PRG_BANK_SIZE = 0x4000
CHR_BANK_SIZE = 0x2000
PRG_SIZE = PRG_BANKS * PRG_BANK_SIZE
CHR_SIZE = CHR_BANKS * CHR_BANK_SIZE
HEADER_SIZE = 16
MAGIC = b"NES\x1a"

FLAGS6 = 0x10  # mapper low nibble 1, horizontal mirroring, no trainer/battery
FLAGS7 = 0x00
FLAGS8 = 0x00
FLAGS9 = 0x00
FLAGS10 = 0x00
FLAGS11 = 0x00
FLAGS12 = 0x00
FLAGS13 = 0x00
FLAGS14 = 0x00
FLAGS15 = 0x00

_MODE_OPERAND_FIELD = {
    "imm": "imm8",
    "zp": "zp",
    "zpx": "zp,x",
    "zpy": "zp,y",
    "abs": "abs",
    "absx": "abs,x",
    "absy": "abs,y",
    "ind": "indirect",
    "indx": "indirect,x",
    "indy": "indirect,y",
    "rel": "rel",
}


class FixtureBuildError(ValueError):
    """Fail-closed public fixture build error."""


def data_bank_pattern(bank: int) -> bytes:
    """Original deterministic data-bank pattern (16 KiB)."""
    if not 0 <= bank < PRG_BANKS - 1:
        raise FixtureBuildError(f"data bank index {bank} out of range")
    data = bytearray(PRG_BANK_SIZE)
    for index in range(PRG_BANK_SIZE):
        data[index] = (index * 0x1D + bank * 0x5B + 1) & 0xFF
    data[0] = bank
    data[1] = 0x4D
    return bytes(data)


def chr_pattern() -> bytes:
    """Original deterministic CHR-ROM pattern (4 x 8 KiB banks)."""
    data = bytearray(CHR_SIZE)
    for index in range(CHR_SIZE):
        bank = index >> 13
        local = index & 0x1FFF
        tile = local >> 4
        row = local & 0x0F
        if row < 8:
            data[index] = ((tile + row + bank) * 0x11) & 0xFF
        else:
            data[index] = ((tile ^ row) * 0x05 + bank) & 0xFF
    return bytes(data)


def _memory_with(image: bytes) -> bytearray:
    memory = bytearray(0x10000)
    memory[FIXED_ORIGIN:FIXED_ORIGIN + len(image)] = image
    memory[0x8000:0x8000 + len(image)] = image
    return memory


def _cross_check(image: bytes, result) -> dict:
    memory = _memory_with(image)
    checked = 0
    for instruction in result.instructions:
        if not FIXED_ORIGIN <= instruction.address < FIXED_ORIGIN + PRG_BANK_SIZE:
            raise FixtureBuildError(
                f"instruction outside fixed bank at 0x{instruction.address:04x}")
        decoded = nes_adapter.decode_full(memory, instruction.address)
        if decoded["op"] != instruction.mnemonic:
            raise FixtureBuildError(
                f"decode mismatch at 0x{instruction.address:04x}: "
                f"{instruction.mnemonic} vs {decoded['op']}")
        if decoded["length"] != len(instruction.bytes):
            raise FixtureBuildError(
                f"length mismatch at 0x{instruction.address:04x}")
        if decoded["word"] != instruction.bytes[0]:
            raise FixtureBuildError(
                f"opcode mismatch at 0x{instruction.address:04x}")
        mode = instruction.mode
        if mode == "acc":
            if decoded.get("dst") != "a":
                raise FixtureBuildError(
                    f"accumulator decode mismatch at 0x{instruction.address:04x}")
        elif mode == "rel":
            rel = instruction.bytes[1]
            rel = rel - 0x100 if rel & 0x80 else rel
            expected = (instruction.address + 2 + rel) & 0xFFFF
            if decoded.get("target") != expected or decoded.get("rel") != rel:
                raise FixtureBuildError(
                    f"branch target mismatch at 0x{instruction.address:04x}")
        elif mode not in ("imp",):
            field = _MODE_OPERAND_FIELD.get(mode)
            if instruction.mnemonic == "jsr":
                field = "a16"
            elif instruction.mnemonic == "jmp" and mode == "abs":
                field = "abs"
            if field is None or field not in decoded:
                raise FixtureBuildError(
                    f"operand field {field!r} missing at 0x{instruction.address:04x}")
            expected = int.from_bytes(instruction.bytes[1:], "little")
            if mode == "imm":
                expected &= 0xFF
            if decoded[field] != expected:
                raise FixtureBuildError(
                    f"operand mismatch at 0x{instruction.address:04x}")
        checked += 1
    return {"instructions_checked": checked}


def build() -> tuple[bytes, dict]:
    source = ASM_PATH.read_text(encoding="utf-8")
    try:
        result = assemble(source, origin=FIXED_ORIGIN)
    except AssemblyError as exc:
        raise FixtureBuildError(f"assembly failed: {exc}") from exc
    if result.origin != FIXED_ORIGIN:
        raise FixtureBuildError(
            f"fixture origin 0x{result.origin:04x} is not 0x{FIXED_ORIGIN:04x}")
    if result.end != 0x10000:
        raise FixtureBuildError(
            f"fixed bank ends at 0x{result.end:04x}, expected 0x10000")
    if len(result.image) != PRG_BANK_SIZE:
        raise FixtureBuildError(
            f"fixed bank is {len(result.image)} bytes, expected {PRG_BANK_SIZE}")
    cross_check = _cross_check(result.image, result)

    vectors = {
        "nmi": int.from_bytes(result.image[-6:-4], "little"),
        "reset": int.from_bytes(result.image[-4:-2], "little"),
        "irq": int.from_bytes(result.image[-2:], "little"),
    }
    for name, label in (("nmi", "nmi_handler"), ("reset", "reset"),
                        ("irq", "irq_handler")):
        if result.labels.get(label) != vectors[name]:
            raise FixtureBuildError(
                f"{name} vector 0x{vectors[name]:04x} does not match label {label}")

    data_banks = [data_bank_pattern(index) for index in range(PRG_BANKS - 1)]
    prg_banks = data_banks + [result.image]
    prg = b"".join(prg_banks)
    chr_bytes = chr_pattern()
    header = bytes([0x4E, 0x45, 0x53, 0x1A, PRG_BANKS, CHR_BANKS, FLAGS6, FLAGS7,
                    FLAGS8, FLAGS9, FLAGS10, FLAGS11, FLAGS12, FLAGS13, FLAGS14,
                    FLAGS15])
    rom = header + prg + chr_bytes
    metadata = {
        "stage": "P6-01",
        "fixture": "openrecomp-phase6-public-mmc1-fixture",
        "license": "Apache-2.0",
        "origin": "original",
        "source": ".openrecomp-phase6/fixture/p6_public_fixture.asm",
        "assembler": ".openrecomp-phase5/src/p5_fixture_asm_v1.py",
        "decoder_cross_check": "adapters/nes6502.py",
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "rom_size": len(rom),
        "header_hex": header.hex(),
        "mapper": 1,
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
        "cpu_origin": FIXED_ORIGIN,
        "vectors": vectors,
        "labels": result.labels,
        "instruction_count": len(result.instructions),
        "instructions_cross_checked": cross_check["instructions_checked"],
        "data_spans": result.data_spans,
    }
    return rom, metadata


if __name__ == "__main__":
    try:
        document_rom, document_metadata = build()
    except FixtureBuildError as exc:
        print(f"P6_PUBLIC_FIXTURE_BUILD=FAIL {exc}", file=sys.stderr)
        raise SystemExit(2)
    import json
    print(json.dumps(document_metadata, indent=2, sort_keys=True))
    raise SystemExit(0)
