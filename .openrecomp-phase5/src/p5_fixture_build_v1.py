#!/usr/bin/env python3
"""Deterministic builder for the original Phase-5 public NES fixture.

Assembles `.openrecomp-phase5/fixture/p5_public_fixture.asm` with the original
Phase-5 assembler (`p5_fixture_asm_v1`), cross-checks every assembled
instruction against the frozen OpenRecomp NES6502 decoder
(`adapters.nes6502`), and packs a documented NROM-128 (mapper 0) iNES image
with an original deterministic CHR-ROM pattern.

The builder is pure: it returns bytes and a metadata document and never writes
files. The public fixture is original Apache-2.0 work with no third-party or
console-derived program data.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402
from p5_fixture_asm_v1 import AssemblyError, assemble  # noqa: E402

ASM_PATH = ROOT / ".openrecomp-phase5" / "fixture" / "p5_public_fixture.asm"

CPU_ORIGIN = 0xC000
PRG_SIZE = 0x4000
CHR_SIZE = 0x2000
HEADER_SIZE = 16
MAGIC = b"NES\x1a"

# Public fixture header fields (documented iNES, mapper 0 NROM-128).
FLAGS6 = 0x00  # vertical arrangement (conventional horizontal mirroring)
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


def chr_pattern() -> bytes:
    """Original deterministic CHR-ROM pattern (256 tiles of 16 bytes)."""
    data = bytearray(CHR_SIZE)
    for index in range(CHR_SIZE):
        tile = index >> 4
        row = index & 0x0F
        if row < 8:
            data[index] = ((tile + row) * 0x11) & 0xFF
        else:
            data[index] = ((tile ^ row) * 0x05) & 0xFF
    return bytes(data)


def _memory_with(image: bytes) -> bytearray:
    memory = bytearray(0x10000)
    memory[CPU_ORIGIN:CPU_ORIGIN + len(image)] = image
    memory[0x8000:0x8000 + len(image)] = image
    return memory


def _cross_check(image: bytes, result) -> dict:
    memory = _memory_with(image)
    checked = 0
    for instruction in result.instructions:
        if not CPU_ORIGIN <= instruction.address < CPU_ORIGIN + PRG_SIZE:
            raise FixtureBuildError(
                f"instruction outside PRG window at 0x{instruction.address:04x}")
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
        result = assemble(source)
    except AssemblyError as exc:
        raise FixtureBuildError(f"assembly failed: {exc}") from exc
    if result.origin != CPU_ORIGIN:
        raise FixtureBuildError(
            f"fixture origin 0x{result.origin:04x} is not 0x{CPU_ORIGIN:04x}")
    if result.end != 0x10000:
        raise FixtureBuildError(
            f"fixture ends at 0x{result.end:04x}, expected 0x10000")
    if len(result.image) != PRG_SIZE:
        raise FixtureBuildError(
            f"fixture PRG is {len(result.image)} bytes, expected {PRG_SIZE}")
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

    chr_bytes = chr_pattern()
    header = bytes([0x4E, 0x45, 0x53, 0x1A, 1, 1, FLAGS6, FLAGS7, FLAGS8,
                    FLAGS9, FLAGS10, FLAGS11, FLAGS12, FLAGS13, FLAGS14, FLAGS15])
    rom = header + result.image + chr_bytes
    metadata = {
        "fixture": "openrecomp-phase5-public-fixture",
        "license": "Apache-2.0",
        "origin": "original",
        "source": ".openrecomp-phase5/fixture/p5_public_fixture.asm",
        "assembler": ".openrecomp-phase5/src/p5_fixture_asm_v1.py",
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "rom_size": len(rom),
        "header_hex": header.hex(),
        "prg_sha256": hashlib.sha256(result.image).hexdigest(),
        "prg_size": len(result.image),
        "chr_sha256": hashlib.sha256(chr_bytes).hexdigest(),
        "chr_size": len(chr_bytes),
        "mapper": 0,
        "mirroring": "horizontal",
        "cpu_origin": CPU_ORIGIN,
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
        print(f"P5_PUBLIC_FIXTURE_BUILD=FAIL {exc}", file=sys.stderr)
        raise SystemExit(2)
    import json
    print(json.dumps(document_metadata, indent=2, sort_keys=True))
    raise SystemExit(0)
