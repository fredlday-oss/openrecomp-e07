#!/usr/bin/env python3
"""OpenRecomp Phase-12 BIOS service surface V1.

Extends the frozen Phase-11 typed BIOS vector boundary with the two documented
B0 services Phase 12 proves necessary:

* ``ps1.bios.B0.57`` GetB0Table: no arguments, returns a guest pointer to the
  mutable word-indexed B0 jump table in ``$v0`` (documented public contract).
* ``ps1.bios.B0.5b`` ChangeClearPAD(int): one argument, toggles the documented
  pad/card clear auto-acknowledge mode and returns nothing.

The B0 table is BIOS-resident and absent from the fixture. Phase 12 does not
invent a BIOS address: it models the required semantics through a clearly
synthetic, project-owned guest data window (``P12_SYNTH_BASE``) populated by the
runtime. The window is implementation-defined and is never presented as a
recovered BIOS pointer. Unknown B0 entries stay zero and fail closed when
dereferenced.

Installing the phase-12 surface mutates only the in-memory Phase-11 tables of
the current process; no frozen source file is modified.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase10/src", ".openrecomp-phase11/src"):
    sys.path.insert(0, str(ROOT / extra))

import p11_bios_v1 as p11_bios  # noqa: E402

SERVICES_VERSION = "1.0.0"

#: Synthetic, project-owned guest data window used to model the BIOS-resident
#: B0 table object. Deliberately outside every modelled RAM/IO/BIOS segment.
SYNTH_BASE = 0x1F000000
SYNTH_SIZE = 0x2000
#: B0 table entry byte offset for index 0x5B (0x5b * 4).
B0_ENTRY_5B_OFFSET = 0x16C
#: Synthetic target object offset inside the window (the modelled
#: ChangeClearPAD function object the caller patches relative to).
SYNTH_TARGET_OFFSET = 0x1000
#: Documented B0 table entry count.
B0_ENTRY_COUNT = 0x60
#: The caller's target-relative offsets that must be writable.
TARGET_RELATIVE_OFFSETS = (0x594, 0x5BC)
DERIVED_POINTER_OFFSETS = (0x884, 0x894)

DOCUMENTED_B0_SERVICES: dict[int, dict[str, Any]] = {
    0x57: {
        "name": "GetB0Table",
        "signature": [],
        "returns": "guest pointer to the mutable B0 jump table in $v0",
        "result_register": 2,
        "refusal": "never refused for the documented no-argument call",
        "semantics": "return the synthetic project-owned B0 table pointer; no GPU, renderer, DMA, VRAM, interrupt, timing or frame behaviour",
        "source": "public PS1 BIOS function table documentation (PSX-SPX BIOS function summary)",
    },
    0x5B: {
        "name": "ChangeClearPAD",
        "signature": ["mode"],
        "returns": "none",
        "result_register": None,
        "refusal": "unsupported mode value (only 0 and 1 are established) or wrong argument count",
        "semantics": "record the documented pad/card clear auto-acknowledge mode in typed BIOS state; no SIO, interrupt, DMA or device behaviour is modelled",
        "source": "public PS1 BIOS function table documentation (PSX-SPX BIOS function summary: B(5Bh) ChangeClearPAD(int))",
    },
}

#: Documented A0 services additionally modelled by the Phase-12 frontier loop.
#: Each is a documented no-argument, void service whose architectural effect is
#: absent in the bounded, non-cached, flat-memory runtime model. Unknown A0
#: services remain fail-closed.
DOCUMENTED_A0_SERVICES_ADDITIONS: dict[int, dict[str, Any]] = {
    0x44: {
        "name": "FlushCache",
        "signature": [],
        "returns": "none",
        "result_register": None,
        "refusal": "wrong argument count",
        "semantics": (
            "documented instruction/data cache flush; the bounded runtime models "
            "a flat, immediately-coherent memory with no caches, so the flush has "
            "no observable architectural effect and is recorded as a typed no-op"
        ),
        "source": "public PS1 BIOS function table documentation (PSX-SPX BIOS function summary: A(44h) FlushCache)",
    },
}

DOCUMENTED_INDEX_NAMES_ADDITIONS = {
    ("B0", 0x57): "GetB0Table",
    ("B0", 0x5B): "ChangeClearPAD",
    ("A0", 0x44): "FlushCache",
}

#: Snapshot of the frozen Phase-11 A0 surface, captured before any Phase-12
#: install so that a stage can pin its own service surface deterministically.
BASE_A0_SERVICES: dict[int, dict[str, Any]] = dict(p11_bios.DOCUMENTED_A0_SERVICES)



def install(extra_a0: tuple[int, ...] = ()) -> dict[str, dict[int, dict[str, Any]]]:
    """Install a pinned Phase-12 service surface into the in-memory tables.

    ``extra_a0`` selects which documented A0 additions are modelled by the
    calling stage, so each stage keeps a deterministic, reproducible surface.
    """
    a0 = dict(BASE_A0_SERVICES)
    for index in extra_a0:
        if index not in DOCUMENTED_A0_SERVICES_ADDITIONS:
            raise KeyError(f"no documented A0 addition for 0x{index:02x}")
        a0[index] = DOCUMENTED_A0_SERVICES_ADDITIONS[index]
    p11_bios.DOCUMENTED_A0_SERVICES.clear()
    p11_bios.DOCUMENTED_A0_SERVICES.update(a0)
    p11_bios.VECTOR_TABLES["A0"] = p11_bios.DOCUMENTED_A0_SERVICES
    p11_bios.DOCUMENTED_B0_SERVICES.clear()
    p11_bios.DOCUMENTED_B0_SERVICES.update(DOCUMENTED_B0_SERVICES)
    p11_bios.DOCUMENTED_INDEX_NAMES.update(DOCUMENTED_INDEX_NAMES_ADDITIONS)
    # VECTOR_TABLES["B0"] is the same object as DOCUMENTED_B0_SERVICES.
    p11_bios.VECTOR_TABLES["B0"] = p11_bios.DOCUMENTED_B0_SERVICES
    return service_tables()


def service_tables() -> dict[str, dict[int, dict[str, Any]]]:
    return {
        "A0": p11_bios.DOCUMENTED_A0_SERVICES,
        "B0": p11_bios.DOCUMENTED_B0_SERVICES,
        "C0": p11_bios.DOCUMENTED_C0_SERVICES,
    }


def service_surface_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase12-b0-service-surface-v1",
        "services_version": SERVICES_VERSION,
        "b0_services": {
            f"0x{index:02x}": {
                "op_name": f"call_bios_b0_{index:02x}",
                "service_id": f"ps1.bios.B0.{index:02x}",
                "name": document["name"],
                "signature": document["signature"],
                "result_register": document["result_register"],
                "semantics": document["semantics"],
                "source": document["source"],
            }
            for index, document in sorted(DOCUMENTED_B0_SERVICES.items())
        },
        "synthetic_window": {
            "base": f"0x{SYNTH_BASE:08x}",
            "size": SYNTH_SIZE,
            "table_entry_5b_offset": f"0x{B0_ENTRY_5B_OFFSET:x}",
            "target_offset": f"0x{SYNTH_TARGET_OFFSET:x}",
            "entry_count": B0_ENTRY_COUNT,
            "target_relative_offsets": [f"0x{value:x}" for value in TARGET_RELATIVE_OFFSETS],
            "derived_pointer_offsets": [f"0x{value:x}" for value in DERIVED_POINTER_OFFSETS],
            "classification": "synthetic-project-owned-not-a-recovered-bios-address",
        },
        "unknown_entry_policy": "zero and fail-closed when dereferenced",
        "a0_additions": {
            f"0x{index:02x}": {
                "service_id": f"ps1.bios.A0.{index:02x}",
                "name": document["name"],
                "signature": document["signature"],
                "result_register": document["result_register"],
                "semantics": document["semantics"],
            }
            for index, document in sorted(DOCUMENTED_A0_SERVICES_ADDITIONS.items())
        },
        "third_party_code_imported": "NO",
    }
