#!/usr/bin/env python3
"""OpenRecomp Phase-15 canonical initialization-MMIO surface V1.

One authoritative description of the production surface, the bounded internal
indirect-target admissions, the deterministic execution budgets and the bounded
interrupt/peripheral MMIO register contract used by the official Phase-15 gates.
All values are derived from mechanically observed fixture behaviour or from the
project-owned bounded register model; none is guessed.
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

import p14_closure_surface_v1 as surface14  # noqa: E402

SURFACE_VERSION = "1.0.0"

#: BIOS service surface (Phase-14 pinned services plus the Phase-15 additions).
EXTRA_A0 = surface14.EXTRA_A0
EXTRA_C0 = surface14.EXTRA_C0
EXTRA_B0 = surface14.EXTRA_B0
P14_B0 = surface14.P14_B0
P14_A0 = surface14.P14_A0
P15_A0 = (0x13, 0x43, 0x72)
P15_B0 = (0x17, 0x18, 0x19)

#: Bounded, site-specific internal indirect-target admissions (unchanged).
INTERNAL_TARGETS = surface14.INTERNAL_TARGETS
HISTORICAL_INDIRECT_SITES = surface14.HISTORICAL_INDIRECT_SITES

#: Deterministic budgets.
SERVICE_BLOCK_BUDGET = surface14.SERVICE_BLOCK_BUDGET
FRONTIER_BLOCK_BUDGET = surface14.FRONTIER_BLOCK_BUDGET
#: The boundary-closure budget must run far enough for the real initialization
#: path to reach (or provably fail before) the semantic boundary.
BOUNDARY_BLOCK_BUDGET = 4_000_000

CARD_PATCH_SOURCE_START = surface14.CARD_PATCH_SOURCE_START
CARD_PATCH_SOURCE_END = surface14.CARD_PATCH_SOURCE_END

#: The bounded project-owned interrupt/peripheral MMIO register contract. Each
#: entry records the address, the allowed access widths, the operations the live
#: path performs and the bounded semantics. No CPU interrupt delivery, no COP0
#: exception vectoring, no GPU execution and no asynchronous DMA timing.
MMIO_REGISTERS: dict[str, dict[str, Any]] = {
    "I_STAT": {
        "address": 0x1F801070,
        "allowed_widths": (16, 32),
        "operations": ("READ", "WRITE"),
        "read_semantics": "return the pending interrupt bits (bounded initial 0x0000)",
        "write_semantics": "acknowledge: i_stat = i_stat & (value & 0xffff)",
        "class": "bounded-project-owned-register-model",
    },
    "I_MASK": {
        "address": 0x1F801074,
        "allowed_widths": (16, 32),
        "operations": ("READ", "WRITE"),
        "read_semantics": "return the current 16-bit interrupt mask",
        "write_semantics": "store: i_mask = value & 0xffff",
        "class": "bounded-project-owned-register-model",
    },
    "SYS_CONTROL": {
        "address": 0x1F801020,
        "allowed_widths": (32,),
        "operations": ("READ", "WRITE"),
        "read_semantics": "return the stored 32-bit register",
        "write_semantics": "store the 32-bit register",
        "class": "bounded-project-owned-register-model",
    },
    "DPCR": {
        "address": 0x1F8010F0,
        "allowed_widths": (32,),
        "operations": ("READ", "WRITE"),
        "read_semantics": "return the stored 32-bit register",
        "write_semantics": "store the 32-bit register",
        "class": "bounded-project-owned-register-model",
    },
    "D2_MADR": {
        "address": 0x1F8010A0,
        "allowed_widths": (32,),
        "operations": ("READ", "WRITE"),
        "read_semantics": "return the stored 32-bit register",
        "write_semantics": "store the 32-bit register",
        "class": "bounded-project-owned-register-model",
    },
    "D2_BCR": {
        "address": 0x1F8010A4,
        "allowed_widths": (32,),
        "operations": ("READ", "WRITE"),
        "read_semantics": "return the stored 32-bit register",
        "write_semantics": "store the 32-bit register",
        "class": "bounded-project-owned-register-model",
    },
    "D2_CHCR": {
        "address": 0x1F8010A8,
        "allowed_widths": (32,),
        "operations": ("READ", "WRITE"),
        "read_semantics": "return the stored register with the busy/start bit (bit 24) clear",
        "write_semantics": "store with deterministic synchronous completion: chcr = value & ~0x01000000",
        "class": "bounded-project-owned-register-model",
    },
    "DICR": {
        "address": 0x1F8010F4,
        "allowed_widths": (32,),
        "operations": ("READ", "WRITE"),
        "read_semantics": "return the stored 32-bit register",
        "write_semantics": "store the 32-bit register; no DMA interrupt is generated",
        "class": "bounded-project-owned-register-model",
    },
    "TIMER1_COUNT": {
        "address": 0x1F801110,
        "allowed_widths": (32,),
        "operations": ("READ",),
        "read_semantics": "return virtual scanline count then advance by 263",
        "write_semantics": "unsupported and fail closed",
        "class": "bounded-project-owned-register-model",
    },
    "TIMER1_MODE": {
        "address": 0x1F801114,
        "allowed_widths": (32,),
        "operations": ("WRITE",),
        "read_semantics": "unsupported and fail closed",
        "write_semantics": "accept only live IRQ-disabled mode 0x00000107",
        "class": "bounded-project-owned-register-model",
    },
    "GPUSTAT": {
        "address": 0x1F801814,
        "allowed_widths": (32,),
        "operations": ("READ",),
        "read_semantics": "return audited boundary contract value 0x14802000",
        "write_semantics": "not intercepted; GP1 writes retain the frozen GPU command boundary",
        "class": "bounded-project-owned-status-contract",
    },
}

#: Device MMIO observed on the live post-card path.
OBSERVED_DEVICE_REGISTERS = {
    "timer1_counter": 0x1F801110,
    "gpu_status": 0x1F801814,
    "interrupt_mask": 0x1F801074,
    "interrupt_stat": 0x1F801070,
}

#: The documented bounded GPUSTAT contract stub.
GPUSTAT_STUB = 0x14802000
FRAME_TICK_ADDRESS = 0x80029678


def mmio_addresses() -> set[int]:
    return {entry["address"] for entry in MMIO_REGISTERS.values()}


def surface_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase15-init-mmio-surface-v1",
        "surface_version": SURFACE_VERSION,
        "extra_a0": list(EXTRA_A0),
        "extra_c0": list(EXTRA_C0),
        "extra_b0": list(EXTRA_B0),
        "p14_b0": list(P14_B0),
        "p14_a0": list(P14_A0),
        "p15_a0": list(P15_A0),
        "p15_b0": list(P15_B0),
        "internal_targets": {
            f"0x{site:08x}": [f"0x{target:08x}" for target in targets]
            for site, targets in sorted(INTERNAL_TARGETS.items())
        },
        "service_block_budget": SERVICE_BLOCK_BUDGET,
        "frontier_block_budget": FRONTIER_BLOCK_BUDGET,
        "boundary_block_budget": BOUNDARY_BLOCK_BUDGET,
        "mmio_registers": {
            name: {
                "address": f"0x{entry['address']:08x}",
                "allowed_widths": list(entry["allowed_widths"]),
                "operations": list(entry["operations"]),
                "read_semantics": entry["read_semantics"],
                "write_semantics": entry["write_semantics"],
                "class": entry["class"],
            }
            for name, entry in sorted(MMIO_REGISTERS.items())
        },
        "gpustat_stub": f"0x{GPUSTAT_STUB:08x}",
        "frame_tick": {
            "address": f"0x{FRAME_TICK_ADDRESS:08x}",
            "semantics": "increment by one on each bounds-checked discrete-time poll",
        },
        "cpu_interrupt_delivery": "NOT_MODELED",
        "timer1_irq_delivery": "NOT_MODELED",
        "gpu_command_execution": "NOT_MODELED",
        "gpu_rasterization": "NOT_MODELED",
        "asynchronous_dma_timing": "NOT_MODELED",
        "arbitrary_indirect_execution": False,
        "third_party_code_imported": "NO",
    }
