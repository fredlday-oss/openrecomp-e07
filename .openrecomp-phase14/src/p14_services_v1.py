#!/usr/bin/env python3
"""OpenRecomp Phase-14 BIOS service surface V1.

Extends the frozen Phase-13 typed BIOS vector boundary with the documented BIOS
services Phase 14 proves necessary to advance the Hercules initialization
frontier past the Phase-13 terminal blocker at ``0x80026ebc``:

* ``ps1.bios.B0.56`` GetC0Table(): no arguments; returns a pointer to the
  project-owned synthetic C0 jump table.
* ``ps1.bios.B0.3f`` puts(text): documented string output (bounded host sink).
* ``ps1.bios.A0.70`` _bu_init(): documented memory-card subsystem init; returns
  0 in $v0.
* ``ps1.bios.A0.30`` abs(value): documented integer absolute value.

Installing the Phase-14 surface first installs the pinned Phase-13 surface, then
adds only the selected documented Phase-14 additions, so each stage keeps a
deterministic, reproducible surface. Unknown indices remain fail-closed.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src"):
    sys.path.insert(0, str(ROOT / extra))

import p11_bios_v1 as p11_bios  # noqa: E402
import p13_services_v1 as services13  # noqa: E402

SERVICES_VERSION = "1.0.0"

DOCUMENTED_B0_SERVICES_ADDITIONS: dict[int, dict[str, Any]] = {
    0x56: {
        "name": "GetC0Table",
        "signature": [],
        "returns": "guest pointer to the synthetic C0 jump table in $v0",
        "result_register": 2,
        "refusal": "never refused for the documented no-argument call",
        "semantics": (
            "return the project-owned synthetic C0 table pointer; populate the "
            "bounded synthetic C0 object (C0[6] -> synthetic exception-handler "
            "object, whose +0x70/+0x74 words encode the synthetic early-card IRQ "
            "handler address). No interrupt delivery, handler execution, "
            "I_STAT/I_MASK, JOY, SIO, DMA or timer behaviour is modelled"
        ),
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): B(56h) GetC0Table())",
    },
    0x3F: {
        "name": "puts",
        "signature": ["text"],
        "returns": "none",
        "result_register": None,
        "refusal": "null/out-of-range string pointer or an unterminated string within the bounded read",
        "semantics": (
            "read the NUL-terminated string through the checked guest-memory "
            "boundary within a fixed bound and discard it (the host has no "
            "console); no device, DMA or interrupt behaviour is modelled"
        ),
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): B(3Fh) puts(src))",
    },
}

DOCUMENTED_A0_SERVICES_ADDITIONS: dict[int, dict[str, Any]] = {
    0x70: {
        "name": "_bu_init",
        "signature": [],
        "returns": "0 in $v0",
        "result_register": 2,
        "refusal": "wrong argument count",
        "semantics": (
            "documented memory-card subsystem initialisation; the bounded model "
            "records the call and returns 0. No card I/O, SIO, DMA, interrupt or "
            "device behaviour is modelled"
        ),
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): A(70h) _bu_init())",
    },
    0x30: {
        "name": "abs",
        "signature": ["value"],
        "returns": "absolute value of the (signed) argument in $v0",
        "result_register": 2,
        "refusal": "wrong argument count or missing result slot",
        "semantics": (
            "return the documented integer absolute value; pure arithmetic, no "
            "memory, device, DMA or interrupt behaviour is modelled"
        ),
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): A(30h) abs(value))",
    },
}

DOCUMENTED_INDEX_NAMES_ADDITIONS = {
    ("B0", 0x56): "GetC0Table",
    ("B0", 0x3F): "puts",
    ("A0", 0x70): "_bu_init",
    ("A0", 0x30): "abs",
}

#: The full Phase-14 B0/A0 addition surface (activation is per-stage).
SUPPORTED_B0_ADDITIONS = tuple(sorted(DOCUMENTED_B0_SERVICES_ADDITIONS))
SUPPORTED_A0_ADDITIONS = tuple(sorted(DOCUMENTED_A0_SERVICES_ADDITIONS))


def install(
    extra_a0: tuple[int, ...] = (),
    extra_c0: tuple[int, ...] = (0x02, 0x03),
    extra_b0: tuple[int, ...] = (0x12, 0x13, 0x14, 0x4A, 0x4B, 0x4C),
    p14_b0: tuple[int, ...] = (),
    p14_a0: tuple[int, ...] = (),
) -> dict[str, dict[int, dict[str, Any]]]:
    """Install the pinned Phase-14 surface (Phase-13 plus selected additions)."""
    tables = services13.install(extra_a0, extra_c0, extra_b0)
    for index in p14_b0:
        if index not in DOCUMENTED_B0_SERVICES_ADDITIONS:
            raise KeyError(f"no documented Phase-14 B0 addition for 0x{index:02x}")
    for index in p14_a0:
        if index not in DOCUMENTED_A0_SERVICES_ADDITIONS:
            raise KeyError(f"no documented Phase-14 A0 addition for 0x{index:02x}")
    for index in p14_b0:
        p11_bios.DOCUMENTED_B0_SERVICES[index] = DOCUMENTED_B0_SERVICES_ADDITIONS[index]
    for index in p14_a0:
        p11_bios.DOCUMENTED_A0_SERVICES[index] = DOCUMENTED_A0_SERVICES_ADDITIONS[index]
    p11_bios.DOCUMENTED_INDEX_NAMES.update(DOCUMENTED_INDEX_NAMES_ADDITIONS)
    p11_bios.VECTOR_TABLES["A0"] = p11_bios.DOCUMENTED_A0_SERVICES
    p11_bios.VECTOR_TABLES["B0"] = p11_bios.DOCUMENTED_B0_SERVICES
    tables["A0"] = p11_bios.DOCUMENTED_A0_SERVICES
    tables["B0"] = p11_bios.DOCUMENTED_B0_SERVICES
    return tables


def service_tables() -> dict[str, dict[int, dict[str, Any]]]:
    return {
        "A0": p11_bios.DOCUMENTED_A0_SERVICES,
        "B0": p11_bios.DOCUMENTED_B0_SERVICES,
        "C0": p11_bios.DOCUMENTED_C0_SERVICES,
    }


def service_surface_document() -> dict[str, Any]:
    base = services13.service_surface_document()
    base["schema"] = "openrecomp-phase14-bios-service-surface-v1"
    base["services_version"] = SERVICES_VERSION
    base["b0_additions"] = {
        f"0x{index:02x}": {
            "op_name": f"call_bios_b0_{index:02x}" if index != 0x56 else "jump_bios_b0_56",
            "service_id": f"ps1.bios.B0.{index:02x}",
            "name": document["name"],
            "signature": document["signature"],
            "result_register": document["result_register"],
            "semantics": document["semantics"],
            "source": document["source"],
        }
        for index, document in sorted(DOCUMENTED_B0_SERVICES_ADDITIONS.items())
    }
    base["a0_additions"] = {
        f"0x{index:02x}": {
            "service_id": f"ps1.bios.A0.{index:02x}",
            "name": document["name"],
            "signature": document["signature"],
            "result_register": document["result_register"],
            "semantics": document["semantics"],
            "source": document["source"],
        }
        for index, document in sorted(DOCUMENTED_A0_SERVICES_ADDITIONS.items())
    }
    base["third_party_code_imported"] = "NO"
    return base
