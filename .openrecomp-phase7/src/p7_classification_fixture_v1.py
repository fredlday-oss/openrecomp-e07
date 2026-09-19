#!/usr/bin/env python3
"""Deterministic builder for the original Phase-7 classification fixture.

Assembles `.openrecomp-phase7/fixture/p7_inline_dispatch_fixture.asm` with the
frozen original Phase-5 assembler (imported read-only), cross-checks every
assembled instruction against the frozen OpenRecomp NES6502 decoder, and packs
a documented MMC1/mapper-1 iNES image:

* 2 x 16 KiB PRG banks (32 KiB), bank 1 fixed containing the code and vectors,
  bank 0 an original deterministic data pattern;
* 1 x 8 KiB CHR bank with an original deterministic pattern;
* horizontal mirroring; power-on MMC1 registers from the frozen model.

The fixture is original Apache-2.0 work authored for Phase 7; it contains no
third-party or console-derived program data. The builder is pure: it returns
bytes and a metadata document and never writes files.
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

ASM_PATH = ROOT / ".openrecomp-phase7" / "fixture" / "p7_inline_dispatch_fixture.asm"
ASSEMBLER_PATH = ".openrecomp-phase5/src/p5_fixture_asm_v1.py"
DECODER_PATH = "adapters/nes6502.py"

FIXED_ORIGIN = 0xC000
FIXED_BANK_INDEX = 1
PRG_BANKS = 2
CHR_BANKS = 1
PRG_BANK_SIZE = 0x4000
CHR_BANK_SIZE = 0x2000
PRG_SIZE = PRG_BANKS * PRG_BANK_SIZE
CHR_SIZE = CHR_BANKS * CHR_BANK_SIZE
HEADER_SIZE = 16
MAGIC = b"NES\x1a"

FLAGS6 = 0x10  # mapper low nibble 1, horizontal mirroring, no trainer/battery
FLAGS7 = 0x00

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


def prg_data_bank() -> bytes:
    """Original deterministic PRG data bank (16 KiB)."""
    data = bytearray(PRG_BANK_SIZE)
    for index in range(PRG_BANK_SIZE):
        data[index] = (index * 0x1F + 0x3D) & 0xFF
    data[0] = 0x50
    data[1] = 0x37
    return bytes(data)


def chr_pattern() -> bytes:
    """Original deterministic CHR-ROM pattern (8 KiB)."""
    data = bytearray(CHR_SIZE)
    for index in range(CHR_SIZE):
        tile = index >> 4
        row = index & 0x0F
        if row < 8:
            data[index] = ((tile * 0x07 + row) ^ 0x5A) & 0xFF
        else:
            data[index] = ((tile + row * 0x03) * 0x0B) & 0xFF
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


def _instruction_facts(result) -> dict:
    labels = result.labels
    call_site = None
    dispatcher_entry = labels["dispatch"]
    for instruction in result.instructions:
        if instruction.mnemonic == "jsr":
            target = int.from_bytes(instruction.bytes[1:], "little")
            if target == dispatcher_entry:
                call_site = instruction.address
    if call_site is None:
        raise FixtureBuildError("no jsr to the dispatch callee was assembled")
    selector_immediate = call_site - 2
    if result.image[selector_immediate - FIXED_ORIGIN] != 0xA9:
        raise FixtureBuildError(
            "the instruction before the dispatch call is not lda immediate")
    pla_addresses = [
        instruction.address for instruction in result.instructions
        if instruction.mnemonic == "pla"
        and dispatcher_entry <= instruction.address < labels["exit_thunk"]
    ]
    if len(pla_addresses) < 2:
        raise FixtureBuildError("the dispatcher does not pull the return address")
    return {
        "call_site": call_site,
        "table_base": labels["inline_table"],
        "resume_code": labels["resume_code"],
        "dispatch_entry": dispatcher_entry,
        "exit_site": labels["exit_thunk"],
        "selector_immediate_address": selector_immediate,
        "dispatcher_pla_addresses": pla_addresses,
        "targets": [labels["target0"], labels["target1"], labels["target2"]],
        "plain_sub": labels["plain_sub"],
    }


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
            f"fixed bank is {len(result.image)} bytes, expected 0x{PRG_BANK_SIZE:x}")
    cross_check = _cross_check(result.image, result)
    facts = _instruction_facts(result)

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

    data_bank = prg_data_bank()
    prg = data_bank + result.image
    chr_bytes = chr_pattern()
    header = bytes([0x4E, 0x45, 0x53, 0x1A, PRG_BANKS, CHR_BANKS, FLAGS6, FLAGS7,
                    0, 0, 0, 0, 0, 0, 0, 0])
    rom = header + prg + chr_bytes
    if not rom.startswith(MAGIC):
        raise FixtureBuildError("packed image lost the iNES magic")

    source_bytes = source.encode("utf-8")
    metadata = {
        "stage": "P7-03",
        "fixture": "openrecomp-phase7-inline-dispatch-classification-fixture",
        "license": "Apache-2.0",
        "origin": "original",
        "source": ".openrecomp-phase7/fixture/p7_inline_dispatch_fixture.asm",
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "assembler": ASSEMBLER_PATH,
        "assembler_sha256": hashlib.sha256(
            (ROOT / ASSEMBLER_PATH).read_bytes()).hexdigest(),
        "decoder_cross_check": DECODER_PATH,
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "rom_size": len(rom),
        "header_hex": header.hex(),
        "mapper": 1,
        "mirroring": "horizontal",
        "prg_sha256": hashlib.sha256(prg).hexdigest(),
        "prg_size": len(prg),
        "prg_banks": PRG_BANKS,
        "prg_bank_sha256": [hashlib.sha256(bank).hexdigest()
                            for bank in (data_bank, result.image)],
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
        "mechanism": facts,
        "expected_runtime": {
            "selector": 0x01,
            "selected_index": 1,
            "markers": {"marker": 0x11, "selector": 0x01, "plain_out": 0x22},
            "target_markers": {str(target): marker for target, marker in zip(
                facts["targets"], (0x10, 0x11, 0x12))},
            "exit_service": "p7.exit",
        },
        "public_claim": "original Apache-2.0 public fixture for the bounded "
                        "inline-dispatch classification mechanism only",
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


def patched_rom(rom: bytes, metadata: dict, selector: int) -> bytes:
    """Return a copy of the original fixture with a different selector byte."""
    if isinstance(selector, bool) or not isinstance(selector, int) \
            or not 0 <= selector <= 0xFF:
        raise FixtureBuildError("selector must be an 8-bit integer")
    address = metadata["mechanism"]["selector_immediate_address"]
    offset = (HEADER_SIZE + (PRG_BANKS - 1) * PRG_BANK_SIZE
              + (address - FIXED_ORIGIN) + 1)
    patched = bytearray(rom)
    patched[offset] = selector
    return bytes(patched)


__all__ = [
    "ASM_PATH",
    "FixtureBuildError",
    "PRG_BANK_SIZE",
    "build",
    "cpu_image",
    "inventory",
    "patched_rom",
]
