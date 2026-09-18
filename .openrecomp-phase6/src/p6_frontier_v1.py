#!/usr/bin/env python3
"""Phase-6 bank-aware reachable frontier for the public MMC1 proof fixture.

Builds the 64 KiB CPU image for the MMC1 layout: the fixed last 16 KiB PRG
bank at `$C000-$FFFF` and the mapper-selected low bank at `$8000-$BFFF`
(documented post-reset state: PRG mode 3, PRG register 0). Only documented
static control flow is followed; indirect jumps stay unresolved and are never
guessed. The frozen Phase-5 frontier walk (`p5_frontier_v1`, read-only) does
the traversal.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT / ".openrecomp-phase5" / "src"), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p5_frontier_v1 as frozen_frontier  # noqa: E402

CPU_SIZE = 0x10000
LOW_WINDOW_BASE = 0x8000
FIXED_WINDOW_BASE = 0xC000
BANK_BYTES = 0x4000


class P6FrontierError(ValueError):
    """Fail-closed Phase-6 frontier error."""


def build_mmc1_cpu_image(rom: bytes, metadata: dict, *, low_bank: int = 0) -> bytes:
    prg_size = int(metadata["prg_size"])
    prg_banks = int(metadata["prg_banks"])
    if prg_size != prg_banks * BANK_BYTES:
        raise P6FrontierError("PRG size does not match the declared bank count")
    if not 0 <= low_bank < prg_banks:
        raise P6FrontierError(f"low bank {low_bank} outside the PRG bank count")
    prg = bytes(rom[16:16 + prg_size])
    if len(prg) != prg_size:
        raise P6FrontierError("PRG segment is truncated")
    image = bytearray(CPU_SIZE)
    image[FIXED_WINDOW_BASE:CPU_SIZE] = prg[(prg_banks - 1) * BANK_BYTES:]
    image[LOW_WINDOW_BASE:FIXED_WINDOW_BASE] = prg[low_bank * BANK_BYTES:
                                                   (low_bank + 1) * BANK_BYTES]
    return bytes(image)


def code_region(metadata: dict) -> tuple[int, int]:
    origin = int(metadata["fixed_bank_origin"])
    spans = metadata.get("data_spans") or []
    if not spans:
        raise P6FrontierError("proof fixture metadata declares no data spans")
    first_data = min(span[0] for span in spans if span[0] >= origin)
    return origin, first_data


def analysis(rom: bytes, metadata: dict, inventory: dict) -> dict[str, Any]:
    image = build_mmc1_cpu_image(rom, metadata)
    region_start, region_end = code_region(metadata)
    vectors = inventory["vectors"]
    roots = [vectors["reset"], vectors["nmi"], vectors["irq"]]
    reached = frozen_frontier.reachable_frontier(image, roots)
    reachable = set(reached["reachable_addresses"])
    span = frozen_frontier.classify_code_span(image, region_start, region_end,
                                              reachable)
    outside = [address for address in sorted(reachable)
               if not region_start <= address < region_end]
    if outside:
        raise P6FrontierError(
            f"reachable code outside the fixed bank: {outside[:4]}")
    low_bank_reads = sorted({address for address in reachable
                             if LOW_WINDOW_BASE <= address < FIXED_WINDOW_BASE})
    return {
        "stage": "P6-07",
        "source": "original public MMC1 proof fixture (Apache-2.0)",
        "image_sha256": hashlib.sha256(image).hexdigest(),
        "code_region": [region_start, region_end],
        "roots": {name: vectors[name] for name in ("reset", "nmi", "irq")},
        "reachable": {
            "instructions": reached["reachable_instructions"],
            "bytes": reached["reachable_bytes"],
            "opcode_histogram": reached["opcode_histogram"],
            "mode_histogram": reached["mode_histogram"],
            "indirect_sites": reached["indirect_sites"],
            "interrupt_sites": reached["interrupt_sites"],
            "dynamic_return_sites": reached["dynamic_return_sites"],
        },
        "code_span": span,
        "window_note": "fixed last bank at $C000-$FFFF with PRG mode 3; "
                       "the low bank is mapper-selected and never executed "
                       "directly by the audited program",
        "low_window_reachable_addresses": low_bank_reads,
    }


__all__ = [
    "BANK_BYTES",
    "CPU_SIZE",
    "FIXED_WINDOW_BASE",
    "LOW_WINDOW_BASE",
    "P6FrontierError",
    "analysis",
    "build_mmc1_cpu_image",
    "code_region",
]
