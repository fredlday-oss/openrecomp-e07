#!/usr/bin/env python3
"""OpenRecomp Phase-13 BIOS service surface V1.

Extends the frozen Phase-12 typed BIOS vector boundary with the documented BIOS
services Phase 13 proves necessary to advance the Hercules initialization
frontier:

* ``ps1.bios.C0.02`` SysEnqIntRP(priority, struc) and
  ``ps1.bios.C0.03`` SysDeqIntRP(priority, struc): documented four-chain
  interrupt-routine queue bookkeeping (see ``p13_bios_extension_v1.c``).
* ``ps1.bios.B0.12`` InitPAD2(buf1, siz1, buf2, siz2), ``ps1.bios.B0.13``
  StartPAD2() and ``ps1.bios.B0.14`` StopPAD2(): documented joypad buffer
  bookkeeping.

Documented semantics source: public PlayStation documentation (PSX-SPX Kernel
(BIOS) function summary). No interrupt delivery, callback execution, SIO/DMA
device behaviour, I_STAT/I_MASK access or timer access is modelled.

Installing the Phase-13 surface first installs the pinned Phase-12 surface, then
populates the in-memory C0/B0 tables. Only in-memory tables of the current
process are mutated; no frozen source file is modified.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src"):
    sys.path.insert(0, str(ROOT / extra))

import p11_bios_v1 as p11_bios  # noqa: E402
import p12_services_v1 as services12  # noqa: E402

SERVICES_VERSION = "1.0.0"

#: The documented Kernel priority chains 0..3 (PSX-SPX "Priority Chains").
PRIORITY_CHAIN_COUNT = 4
#: The documented 16-byte ``IntRP`` element layout (PSX-SPX).
INTRP_ELEMENT_SIZE = 0x10
INTRP_NEXT_OFFSET = 0x00
INTRP_SECOND_FUNCTION_OFFSET = 0x04
INTRP_FIRST_FUNCTION_OFFSET = 0x08

#: Documented joypad buffer size (PSX-SPX: "should be 22h bytes each").
PAD_BUFFER_SIZE = 0x22
#: Project safety bound for a modelled pad buffer (fail closed above it).
PAD_BUFFER_SIZE_MAX = 0x100

DOCUMENTED_C0_SERVICES: dict[int, dict[str, Any]] = {
    0x02: {
        "name": "SysEnqIntRP",
        "signature": ["priority", "struc"],
        "returns": "0 on success",
        "result_register": 2,
        "refusal": "priority outside the documented chains (0..3), a null/invalid handler "
                   "element pointer, or an element already registered in the chain",
        "semantics": (
            "insert the guest handler element at the head of the documented priority "
            "chain and write the previous head pointer into the element's next field "
            "(offset 0); BIOS queue bookkeeping only, no interrupt delivery and no "
            "callback execution"
        ),
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): C(02h) SysEnqIntRP(priority,struc))",
    },
    0x03: {
        "name": "SysDeqIntRP",
        "signature": ["priority", "struc"],
        "returns": "removed element pointer, or 0 when the chain is empty",
        "result_register": 2,
        "refusal": "priority outside the documented chains (0..3) or an invalid handler "
                   "element pointer",
        "semantics": (
            "remove the element from the head of the documented priority chain, "
            "returning the removed element pointer in $v0 (0 when the chain is empty or "
            "the supplied element is not the chain head, matching the documented "
            "first-element-only removal behaviour); no callback execution and no hardware "
            "interrupt side effects"
        ),
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): C(03h) SysDeqIntRP(priority,struc))",
    },
}

DOCUMENTED_B0_SERVICES_ADDITIONS: dict[int, dict[str, Any]] = {
    0x12: {
        "name": "InitPAD2",
        "signature": ["buf1", "siz1", "buf2", "siz2"],
        "returns": "none",
        "result_register": None,
        "refusal": "null buffer, unsupported buffer size, or a buffer outside mapped guest RAM",
        "semantics": (
            "memorize the buf1/buf2 addresses, zerofill siz1/siz2 bytes of the guest "
            "buffers through the checked guest-memory boundary and set the documented "
            "pad-enable flag; no SIO, interrupt, DMA or device behaviour is modelled"
        ),
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): B(12h) InitPAD2(buf1,siz1,buf2,siz2))",
    },
    0x13: {
        "name": "StartPAD2",
        "signature": [],
        "returns": "none",
        "result_register": None,
        "refusal": "wrong argument count",
        "semantics": (
            "record the documented pad-start bookkeeping flag; the BIOS-resident "
            "PadCardIrq handler enqueue has no guest-observable effect in the bounded "
            "model because interrupt delivery and handler execution are not modelled"
        ),
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): B(13h) StartPAD2())",
    },
    0x14: {
        "name": "StopPAD2",
        "signature": [],
        "returns": "none",
        "result_register": None,
        "refusal": "wrong argument count",
        "semantics": (
            "clear the documented pad-start bookkeeping flag; no SIO, interrupt, DMA or "
            "device behaviour is modelled"
        ),
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): B(14h) StopPAD2())",
    },
    0x4A: {
        "name": "InitCARD2",
        "signature": ["pad_enable"],
        "returns": "none",
        "result_register": None,
        "refusal": "unsupported pad-enable flag value or wrong argument count",
        "semantics": (
            "record the documented memory-card pad-enable flag (which selects whether pads "
            "are handled together with memory cards) and the card-initialised bookkeeping "
            "state; the BIOS-resident card IRQ handler enqueue and the k0/k1 register use "
            "have no guest-observable effect in the bounded model because interrupt "
            "delivery and handler execution are not modelled"
        ),
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): B(4Ah) InitCARD2(pad_enable))",
    },
    0x4B: {
        "name": "StartCARD2",
        "signature": [],
        "returns": "none",
        "result_register": None,
        "refusal": "wrong argument count",
        "semantics": (
            "record the documented memory-card start bookkeeping flag; no SIO, interrupt, "
            "DMA or device behaviour is modelled"
        ),
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): B(4Bh) StartCARD2())",
    },
    0x4C: {
        "name": "StopCARD2",
        "signature": [],
        "returns": "none",
        "result_register": None,
        "refusal": "wrong argument count",
        "semantics": (
            "clear the documented memory-card start bookkeeping flag; no SIO, interrupt, "
            "DMA or device behaviour is modelled"
        ),
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): B(4Ch) StopCARD2())",
    },
}

DOCUMENTED_INDEX_NAMES_ADDITIONS = {
    ("C0", 0x02): "SysEnqIntRP",
    ("C0", 0x03): "SysDeqIntRP",
    ("B0", 0x12): "InitPAD2",
    ("B0", 0x13): "StartPAD2",
    ("B0", 0x14): "StopPAD2",
    ("B0", 0x4A): "InitCARD2",
    ("B0", 0x4B): "StartCARD2",
    ("B0", 0x4C): "StopCARD2",
}

#: The documented BIOS A/B/C calling convention passes arguments in $a0..$a3
#: (registers 4..7). The frozen Phase-11 surface declared only $a0..$a2; Phase 13
#: extends the in-memory tuple to include $a3 so the documented four-argument
#: joypad service can be modelled exactly. No frozen source is modified.
BIOS_ARGUMENT_REGISTERS = (4, 5, 6, 7)

SUPPORTED_C0_INDICES = tuple(sorted(DOCUMENTED_C0_SERVICES))
SUPPORTED_B0_INDICES = tuple(sorted(DOCUMENTED_B0_SERVICES_ADDITIONS))


def install(
    extra_a0: tuple[int, ...] = (),
    extra_c0: tuple[int, ...] = (),
    extra_b0: tuple[int, ...] = (),
) -> dict[str, dict[int, dict[str, Any]]]:
    """Install a pinned Phase-13 surface: Phase-12 surface plus the C0/B0 additions."""
    tables = services12.install(extra_a0)
    p11_bios.BIOS_ARGUMENT_REGISTERS = BIOS_ARGUMENT_REGISTERS
    for index in extra_c0:
        if index not in DOCUMENTED_C0_SERVICES:
            raise KeyError(f"no documented C0 service for 0x{index:02x}")
    for index in extra_b0:
        if index not in DOCUMENTED_B0_SERVICES_ADDITIONS:
            raise KeyError(f"no documented B0 addition for 0x{index:02x}")
    selected_c0 = {index: DOCUMENTED_C0_SERVICES[index] for index in extra_c0}
    p11_bios.DOCUMENTED_C0_SERVICES.clear()
    p11_bios.DOCUMENTED_C0_SERVICES.update(selected_c0)
    p11_bios.VECTOR_TABLES["C0"] = p11_bios.DOCUMENTED_C0_SERVICES
    for index in extra_b0:
        p11_bios.DOCUMENTED_B0_SERVICES[index] = DOCUMENTED_B0_SERVICES_ADDITIONS[index]
    p11_bios.VECTOR_TABLES["B0"] = p11_bios.DOCUMENTED_B0_SERVICES
    p11_bios.DOCUMENTED_INDEX_NAMES.update(DOCUMENTED_INDEX_NAMES_ADDITIONS)
    tables["C0"] = p11_bios.DOCUMENTED_C0_SERVICES
    tables["B0"] = p11_bios.DOCUMENTED_B0_SERVICES
    return tables


def service_tables() -> dict[str, dict[int, dict[str, Any]]]:
    return {
        "A0": p11_bios.DOCUMENTED_A0_SERVICES,
        "B0": p11_bios.DOCUMENTED_B0_SERVICES,
        "C0": p11_bios.DOCUMENTED_C0_SERVICES,
    }


def service_surface_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase13-bios-service-surface-v1",
        "services_version": SERVICES_VERSION,
        "c0_services": {
            f"0x{index:02x}": {
                "op_name": f"jump_bios_c0_{index:02x}",
                "service_id": f"ps1.bios.C0.{index:02x}",
                "name": document["name"],
                "signature": document["signature"],
                "result_register": document["result_register"],
                "semantics": document["semantics"],
                "source": document["source"],
            }
            for index, document in sorted(DOCUMENTED_C0_SERVICES.items())
        },
        "b0_additions": {
            f"0x{index:02x}": {
                "op_name": f"jump_bios_b0_{index:02x}",
                "service_id": f"ps1.bios.B0.{index:02x}",
                "name": document["name"],
                "signature": document["signature"],
                "result_register": document["result_register"],
                "semantics": document["semantics"],
                "source": document["source"],
            }
            for index, document in sorted(DOCUMENTED_B0_SERVICES_ADDITIONS.items())
        },
        "priority_chain_count": PRIORITY_CHAIN_COUNT,
        "element_layout": {
            "size": INTRP_ELEMENT_SIZE,
            "next_offset": INTRP_NEXT_OFFSET,
            "second_function_offset": INTRP_SECOND_FUNCTION_OFFSET,
            "first_function_offset": INTRP_FIRST_FUNCTION_OFFSET,
            "source": "public PS1 BIOS documentation (PSX-SPX Kernel (BIOS): priority chains)",
        },
        "pad_buffer_size": PAD_BUFFER_SIZE,
        "pad_buffer_size_max": PAD_BUFFER_SIZE_MAX,
        "modelled": [
            "typed per-priority IntRP chain bookkeeping",
            "documented handler-element next-pointer write/removal",
            "documented joypad buffer memorisation and zerofill",
        ],
        "not_modelled": [
            "interrupt delivery",
            "callback execution",
            "I_STAT / I_MASK access",
            "root counters / timers",
            "SIO / DMA / device behaviour",
        ],
        "third_party_code_imported": "NO",
    }
