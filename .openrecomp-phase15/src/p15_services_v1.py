#!/usr/bin/env python3
"""OpenRecomp Phase-15 BIOS service surface V1.

Extends the frozen Phase-14 typed BIOS vector boundary with the documented BIOS
services Phase 15 proves necessary to advance the Hercules initialization
frontier to the semantic initialization boundary:

* ``ps1.bios.A0.43`` Exec(entry): the documented program execution handoff. The
  bounded project model records the entry argument and the semantic
  initialization boundary; it never recompiles, executes or fabricates the
  target executable. The site at ``0x80015b84`` is the real live callsite.

Installing the Phase-15 surface first installs the pinned Phase-14 surface, then
adds only the selected documented Phase-15 additions, so each stage keeps a
deterministic, reproducible surface. Unknown indices remain fail-closed.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src"):
    sys.path.insert(0, str(ROOT / extra))

import p11_bios_v1 as p11_bios  # noqa: E402
import p14_services_v1 as services14  # noqa: E402

SERVICES_VERSION = "1.0.0"

#: The documented TITLE-overlay entry point of this fixture (non-reconstructive
#: metadata; it is the guest argument, not a recovered BIOS address).
TITLE_ENTRY = 0x800380A0

DOCUMENTED_A0_SERVICES_ADDITIONS: dict[int, dict[str, Any]] = {
    0x13: {
        "name": "setjmp",
        "signature": ["buf"],
        "returns": "0 in $v0 on a direct call",
        "result_register": 2,
        "refusal": "wrong argument count or a missing result slot",
        "semantics": (
            "documented incomplete POSIX setjmp. The bounded project model "
            "returns the documented direct-call value 0. The A(14h) longjmp "
            "companion is unreachable in this fixture (no A0:0x14 stub or "
            "callsite exists), so the 0x30-byte jump buffer is never read and "
            "the model does not fabricate saved register state"
        ),
        "source": (
            "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): A(13h) "
            "setjmp(buf))"
        ),
    },
    0x43: {
        "name": "Exec",
        "signature": ["entry"],
        "returns": "does not return (transfers control to the loaded executable)",
        "result_register": None,
        "refusal": (
            "wrong argument count or a non-canonical entry argument; the bounded "
            "model records the entry argument and never fabricates a target"
        ),
        "semantics": (
            "documented program-execution handoff. The bounded project model "
            "records the entry argument and marks the semantic initialization "
            "boundary; the target executable is loaded by the real guest from the "
            "disc and is neither recompiled nor executed by the host. This is a "
            "semantic handoff record, not a fabricated control-flow target"
        ),
        "source": (
            "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): A(43h) "
            "Exec(ptr) / DoExecute)"
        ),
    },
    0x72: {
        "name": "_96_remove",
        "signature": [],
        "returns": "none",
        "result_register": None,
        "refusal": "wrong argument count",
        "semantics": (
            "documented CD-ROM subsystem deinitialization. The bounded project "
            "model records the call; the documented effect (removing the CD-ROM "
            "interrupt handlers) has no guest-observable effect because "
            "interrupt delivery is not modelled. No CD-ROM device, DMA or SIO "
            "behaviour is modelled"
        ),
        "source": (
            "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): A(56h)/A(72h) "
            "_96_remove())"
        ),
    },
}

DOCUMENTED_B0_SERVICES_ADDITIONS: dict[int, dict[str, Any]] = {
    0x17: {
        "name": "ReturnFromException",
        "signature": [],
        "returns": "does not return (restores the saved exception context)",
        "result_register": None,
        "refusal": "wrong argument count",
        "semantics": (
            "documented exception-return entry. The bounded project model records "
            "the call; no exception is ever delivered or pending in the bounded "
            "path, so no context is restored and control continues normally. No "
            "COP0 exception vectoring, interrupt arbitration or scheduling is "
            "modelled"
        ),
        "source": (
            "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): B(17h) "
            "ReturnFromException())"
        ),
    },
    0x18: {
        "name": "ResetEntryInt",
        "signature": [],
        "returns": "none",
        "result_register": None,
        "refusal": "wrong argument count",
        "semantics": (
            "documented reset of the BIOS entry-interrupt handler. The bounded "
            "project model clears the recorded entry-interrupt hook; no "
            "interrupt delivery is modelled"
        ),
        "source": (
            "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): B(18h) "
            "ResetEntryInt())"
        ),
    },
    0x19: {
        "name": "HookEntryInt",
        "signature": ["addr"],
        "returns": "none",
        "result_register": None,
        "refusal": "null or out-of-range handler pointer, or wrong argument count",
        "semantics": (
            "documented installation of a user entry-interrupt handler. The "
            "bounded project model validates and records the handler pointer; "
            "the handler is never executed because no interrupt or exception is "
            "delivered in the bounded path"
        ),
        "source": (
            "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): B(19h) "
            "HookEntryInt(addr))"
        ),
    },
}

DOCUMENTED_INDEX_NAMES_ADDITIONS = {
    ("A0", 0x13): "setjmp",
    ("A0", 0x43): "Exec",
    ("A0", 0x72): "_96_remove",
    ("B0", 0x17): "ReturnFromException",
    ("B0", 0x18): "ResetEntryInt",
    ("B0", 0x19): "HookEntryInt",
}

SUPPORTED_A0_ADDITIONS = tuple(sorted(DOCUMENTED_A0_SERVICES_ADDITIONS))
SUPPORTED_B0_ADDITIONS = tuple(sorted(DOCUMENTED_B0_SERVICES_ADDITIONS))


def install(
    extra_a0: tuple[int, ...] = (),
    extra_c0: tuple[int, ...] = (0x02, 0x03),
    extra_b0: tuple[int, ...] = (0x12, 0x13, 0x14, 0x4A, 0x4B, 0x4C),
    p14_b0: tuple[int, ...] = (),
    p14_a0: tuple[int, ...] = (),
    p15_a0: tuple[int, ...] = (),
    p15_b0: tuple[int, ...] = (),
) -> dict[str, dict[int, dict[str, Any]]]:
    """Install the pinned Phase-15 surface (Phase-14 plus selected additions)."""
    tables = services14.install(
        extra_a0, extra_c0, extra_b0, p14_b0=p14_b0, p14_a0=p14_a0
    )
    for index in p15_a0:
        if index not in DOCUMENTED_A0_SERVICES_ADDITIONS:
            raise KeyError(f"no documented Phase-15 A0 addition for 0x{index:02x}")
    for index in p15_b0:
        if index not in DOCUMENTED_B0_SERVICES_ADDITIONS:
            raise KeyError(f"no documented Phase-15 B0 addition for 0x{index:02x}")
    for index in p15_a0:
        p11_bios.DOCUMENTED_A0_SERVICES[index] = DOCUMENTED_A0_SERVICES_ADDITIONS[index]
    for index in p15_b0:
        p11_bios.DOCUMENTED_B0_SERVICES[index] = DOCUMENTED_B0_SERVICES_ADDITIONS[index]
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
    base = services14.service_surface_document()
    base["schema"] = "openrecomp-phase15-bios-service-surface-v1"
    base["services_version"] = SERVICES_VERSION
    base["a0_additions_p15"] = {
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
    base["b0_additions_p15"] = {
        f"0x{index:02x}": {
            "service_id": f"ps1.bios.B0.{index:02x}",
            "name": document["name"],
            "signature": document["signature"],
            "result_register": document["result_register"],
            "semantics": document["semantics"],
            "source": document["source"],
        }
        for index, document in sorted(DOCUMENTED_B0_SERVICES_ADDITIONS.items())
    }
    base["title_entry"] = f"0x{TITLE_ENTRY:08x}"
    base["third_party_code_imported"] = "NO"
    return base
