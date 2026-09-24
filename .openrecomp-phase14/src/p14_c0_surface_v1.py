#!/usr/bin/env python3
"""OpenRecomp Phase-14 synthetic C0 BIOS-object surface V1.

Phase 14 extends the versioned, project-owned synthetic guest data window that
Phase 12 established for the BIOS-resident B0 jump table with the minimum C0
surface the real Hercules early-card IRQ patch routine inspects.

The real routine (``fn_80026ea8``) performs exactly this guest-visible dataflow
after ``B0:0x56 GetC0Table()`` returns:

    C0[6]                      read at table + 0x18
    word0 = handler + 0x70     read
    word1 = handler + 0x74     read
    early = ((word0 & 0xffff) << 16) | (word1 & 0xffff)
    dest  = early + 0x28       five-word game-side patch copied here
    cont  = early + 0x3c       stored to 0x8002ed90

Phase 14 models this with project-owned synthetic objects inside the existing
bounded window. None of these addresses is a recovered/authentic PS1 BIOS
address; they are implementation-defined synthetic identities. Every access is
bounds-checked against the window and unknown offsets fail closed.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src"):
    sys.path.insert(0, str(ROOT / extra))

import p12_services_v1 as services12  # noqa: E402

SURFACE_VERSION = "1.0.0"

#: Reuse the exact Phase-12 synthetic window (project-owned, never BIOS).
WINDOW_BASE = services12.SYNTH_BASE
WINDOW_SIZE = services12.SYNTH_SIZE

#: C0 jump table base inside the window, and the documented exception-handler
#: index the guest reads (C(06h) = exception handler).
C0_TABLE_OFFSET = 0x0800
C0_EXCEPTION_INDEX = 6
C0_EXCEPTION_SLOT_OFFSET = C0_TABLE_OFFSET + (C0_EXCEPTION_INDEX * 4)  # 0x0818

#: Synthetic exception-handler object; +0x70/+0x74 carry the early-card handler
#: address halves.
EXCEPTION_HANDLER_OFFSET = 0x1800
EXCEPTION_HANDLER_HIGH_OFFSET = EXCEPTION_HANDLER_OFFSET + 0x70  # 0x1870
EXCEPTION_HANDLER_LOW_OFFSET = EXCEPTION_HANDLER_OFFSET + 0x74   # 0x1874

#: Synthetic early-card IRQ handler object.
EARLY_HANDLER_OFFSET = 0x1900
CARD_PATCH_OFFSET = EARLY_HANDLER_OFFSET + 0x28  # 0x1928
CARD_PATCH_WORDS = 5
CARD_PATCH_BYTES = CARD_PATCH_WORDS * 4          # 20
CARD_CONTINUATION_OFFSET = EARLY_HANDLER_OFFSET + 0x3C  # 0x193c

#: Guest globals the routine touches.
GUEST_CONTINUATION_SLOT = 0x8002ED90

#: The five-word game-side patch source range inside the fixture image. Only the
#: bounds are recorded here; the words themselves are read from the private
#: fixture at gate time and are never committed.
CARD_PATCH_SOURCE_START = 0x80026E50
CARD_PATCH_SOURCE_END = 0x80026E64  # exclusive


def _addr(offset: int) -> int:
    return WINDOW_BASE + offset


def addresses() -> dict[str, int]:
    return {
        "window_base": WINDOW_BASE,
        "window_size": WINDOW_SIZE,
        "c0_table": _addr(C0_TABLE_OFFSET),
        "c0_exception_slot": _addr(C0_EXCEPTION_SLOT_OFFSET),
        "exception_handler": _addr(EXCEPTION_HANDLER_OFFSET),
        "exception_handler_high": _addr(EXCEPTION_HANDLER_HIGH_OFFSET),
        "exception_handler_low": _addr(EXCEPTION_HANDLER_LOW_OFFSET),
        "early_handler": _addr(EARLY_HANDLER_OFFSET),
        "card_patch": _addr(CARD_PATCH_OFFSET),
        "card_continuation": _addr(CARD_CONTINUATION_OFFSET),
    }


def handler_halves(early_handler_address: int) -> tuple[int, int]:
    """The +0x70 / +0x74 halves encoding an early-card handler address."""
    return ((early_handler_address >> 16) & 0xFFFF, early_handler_address & 0xFFFF)


def reconstruct_handler(high: int, low: int) -> int:
    """The exact guest derivation ``((high & 0xffff) << 16) | (low & 0xffff)``."""
    return (((high & 0xFFFF) << 16) | (low & 0xFFFF)) & 0xFFFFFFFF


def synthetic_offsets() -> dict[str, int]:
    return {
        "c0_table_offset": C0_TABLE_OFFSET,
        "c0_exception_index": C0_EXCEPTION_INDEX,
        "c0_exception_slot_offset": C0_EXCEPTION_SLOT_OFFSET,
        "exception_handler_offset": EXCEPTION_HANDLER_OFFSET,
        "exception_handler_high_offset": EXCEPTION_HANDLER_HIGH_OFFSET,
        "exception_handler_low_offset": EXCEPTION_HANDLER_LOW_OFFSET,
        "early_handler_offset": EARLY_HANDLER_OFFSET,
        "card_patch_offset": CARD_PATCH_OFFSET,
        "card_patch_words": CARD_PATCH_WORDS,
        "card_patch_bytes": CARD_PATCH_BYTES,
        "card_continuation_offset": CARD_CONTINUATION_OFFSET,
    }


def bounds_ok(offset: int, width: int = 4) -> bool:
    return 0 <= offset and offset + width <= WINDOW_SIZE


def surface_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase14-c0-surface-v1",
        "surface_version": SURFACE_VERSION,
        "classification": "synthetic-project-owned-not-a-recovered-bios-address",
        "window": {
            "base": f"0x{WINDOW_BASE:08x}",
            "size": WINDOW_SIZE,
            "reused_from": "phase12-synthetic-b0-window",
        },
        "objects": {
            "c0_table_offset": f"0x{C0_TABLE_OFFSET:x}",
            "c0_exception_index": C0_EXCEPTION_INDEX,
            "c0_exception_slot_offset": f"0x{C0_EXCEPTION_SLOT_OFFSET:x}",
            "exception_handler_offset": f"0x{EXCEPTION_HANDLER_OFFSET:x}",
            "early_handler_offset": f"0x{EARLY_HANDLER_OFFSET:x}",
            "card_patch_offset": f"0x{CARD_PATCH_OFFSET:x}",
            "card_patch_bytes": CARD_PATCH_BYTES,
            "card_continuation_offset": f"0x{CARD_CONTINUATION_OFFSET:x}",
        },
        "derivations": {
            "early_handler": "((word[handler+0x70] & 0xffff) << 16) | (word[handler+0x74] & 0xffff)",
            "patch_destination": "early_handler + 0x28",
            "continuation": "early_handler + 0x3c",
            "guest_slot": f"0x{GUEST_CONTINUATION_SLOT:08x}",
        },
        "authentic_bios_address_claimed": False,
        "third_party_code_imported": "NO",
    }
