#!/usr/bin/env python3
"""Original synthetic MMC1 fixtures for the Phase-7 bank-reachability model.

These are original Apache-2.0 test programs authored for Phase 7 (assembled
with the frozen Phase-5 assembler) used to exercise the P7-04 bank-aware
reachability model:

* `proven_fixture`: fixed-bank code commits a PRG bank through an unrolled
  five-write constant sequence and calls code in the switchable window;
* `unknown_fixture`: the same call with unresolved write values (fail-closed
  expansion over physical banks);
* `reset_bit_fixture`: a bit-7 shift reset precedes the sequence;
* `suppression_fixture`: two consecutive MMC1 writes (ambiguous suppression);
* `span_fixture`: a reachable instruction spans the fixed/switchable window
  boundary (fail closed);
* `p6_public_proof`: the frozen public Phase-6 MMC1 proof fixture.

No third-party or console-derived program data is used.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_fixture_proof_v1 as p6_proof  # noqa: E402
from p5_fixture_asm_v1 import AssemblyError, assemble  # noqa: E402

PRG_BANK_BYTES = 0x4000
FIXED_ORIGIN = 0xC000
LOW_ORIGIN = 0x8000

HEADER = (
    ".equ EXIT_VEC, $02FF\n"
    ".equ MARKER, $0300\n"
    ".equ MMC1_PRG, $E000\n"
)

TAIL = (
    "        jsr $8000\n"
    "        jmp (EXIT_VEC)\n"
    "nmi_handler:\n"
    "        rti\n"
    "irq_handler:\n"
    "        rti\n"
    "        .org $FFFA\n"
    "        .word nmi_handler\n"
    "        .word reset\n"
    "        .word irq_handler\n"
)


class BankFixtureError(ValueError):
    """Fail-closed synthetic fixture error."""


def _write_sequence(values: list[int]) -> str:
    if len(values) != 5:
        raise BankFixtureError("an MMC1 commit sequence needs five writes")
    lines = []
    for value in values:
        lines.append(f"        lda #${value:02X}")
        lines.append("        sta MMC1_PRG")
    return "\n".join(lines) + "\n"


def _bits(value: int) -> list[int]:
    return [(value >> index) & 0x01 for index in range(5)]


def _assemble(source: str, origin: int, size: int) -> bytes:
    try:
        result = assemble(source, origin=origin)
    except AssemblyError as exc:
        raise BankFixtureError(f"assembly failed: {exc}") from exc
    if result.origin != origin:
        raise BankFixtureError("assembled origin mismatch")
    if len(result.image) > size:
        raise BankFixtureError("assembled image exceeds the requested size")
    return bytes(result.image) + b"\x00" * (size - len(result.image))


def _fixed_source(body: str) -> str:
    return (HEADER
            + ".org $C000\n"
            + "reset:\n"
            + "        sei\n"
            + "        cld\n"
            + "        ldx #$FF\n"
            + "        txs\n"
            + body
            + TAIL)


def _bank_routine(bank: int) -> bytes:
    marker = (0x5A + bank) & 0xFF
    source = (f".equ MARKER, $0300\n"
              f".org $8000\n"
              f"entry:\n"
              f"        lda #${marker:02X}\n"
              f"        sta MARKER\n"
              f"        rts\n")
    return _assemble(source, LOW_ORIGIN, PRG_BANK_BYTES)


def _data_bank(bank: int) -> bytes:
    return bytes(((index * 0x1F + bank * 0x11 + 1) & 0xFF)
                 for index in range(PRG_BANK_BYTES))


def _pack(banks: list[bytes]) -> bytes:
    return b"".join(banks)


def proven_fixture(prg_banks: int = 4, target_bank: int = 2) -> dict:
    if not 0 <= target_bank < prg_banks:
        raise BankFixtureError("target bank out of range")
    source = _fixed_source(_write_sequence(_bits(target_bank)))
    fixed = _assemble(source, FIXED_ORIGIN, PRG_BANK_BYTES)
    banks = [_data_bank(index) for index in range(prg_banks)]
    for index in range(prg_banks):
        banks[index] = _bank_routine(index)
    banks[prg_banks - 1] = fixed
    return {
        "name": "proven",
        "prg": _pack(banks),
        "prg_banks": prg_banks,
        "roots": [0xC000],
        "expected_bank": target_bank,
        "expected_addresses": [0x8000],
    }


def unknown_fixture(prg_banks: int = 4) -> dict:
    body = ""
    for _ in range(5):
        body += "        lda $10\n        sta MMC1_PRG\n"
    source = _fixed_source(body)
    fixed = _assemble(source, FIXED_ORIGIN, PRG_BANK_BYTES)
    banks = [_bank_routine(index) for index in range(prg_banks)]
    banks[prg_banks - 1] = fixed
    return {
        "name": "unknown_values",
        "prg": _pack(banks),
        "prg_banks": prg_banks,
        "roots": [0xC000],
    }


def reset_bit_fixture(prg_banks: int = 4, target_bank: int = 1) -> dict:
    body = "        lda #$80\n        sta MMC1_PRG\n"
    body += _write_sequence(_bits(target_bank))
    source = _fixed_source(body)
    fixed = _assemble(source, FIXED_ORIGIN, PRG_BANK_BYTES)
    banks = [_bank_routine(index) for index in range(prg_banks)]
    banks[prg_banks - 1] = fixed
    return {
        "name": "reset_bit",
        "prg": _pack(banks),
        "prg_banks": prg_banks,
        "roots": [0xC000],
        "expected_bank": target_bank,
        "expected_addresses": [0x8000],
    }


def suppression_fixture(prg_banks: int = 4) -> dict:
    body = ("        lda #$00\n"
            "        sta MMC1_PRG\n"
            "        sta MMC1_PRG\n")
    source = _fixed_source(body)
    fixed = _assemble(source, FIXED_ORIGIN, PRG_BANK_BYTES)
    banks = [_bank_routine(index) for index in range(prg_banks)]
    banks[prg_banks - 1] = fixed
    return {
        "name": "consecutive_writes",
        "prg": _pack(banks),
        "prg_banks": prg_banks,
        "roots": [0xC000],
    }


def span_fixture(prg_banks: int = 4) -> dict:
    body = _write_sequence(_bits(1))
    body += "        jsr $BFFF\n"
    source = _fixed_source(body)
    fixed = _assemble(source, FIXED_ORIGIN, PRG_BANK_BYTES)
    banks = [_bank_routine(index) for index in range(prg_banks)]
    banks[prg_banks - 1] = fixed
    bank = bytearray(banks[1])
    bank[PRG_BANK_BYTES - 1] = 0xA9  # two-byte instruction at $BFFF
    banks[1] = bytes(bank)
    return {
        "name": "window_span",
        "prg": _pack(banks),
        "prg_banks": prg_banks,
        "roots": [0xC000],
    }


def p6_public_proof() -> dict:
    rom, metadata = p6_proof.build_proof()
    prg_size = metadata["prg_size"]
    trainer = metadata.get("trainer_bytes", 0)
    base = 16 + trainer
    prg = rom[base:base + prg_size]
    vectors = metadata["vectors"]
    return {
        "name": "p6_public_proof",
        "prg": bytes(prg),
        "prg_banks": metadata["prg_banks"],
        "roots": [vectors["reset"], vectors["nmi"], vectors["irq"]],
    }


FIXTURES = (
    proven_fixture,
    unknown_fixture,
    reset_bit_fixture,
    suppression_fixture,
    span_fixture,
    p6_public_proof,
)

__all__ = [
    "FIXTURES",
    "BankFixtureError",
    "p6_public_proof",
    "proven_fixture",
    "reset_bit_fixture",
    "span_fixture",
    "suppression_fixture",
    "unknown_fixture",
]
