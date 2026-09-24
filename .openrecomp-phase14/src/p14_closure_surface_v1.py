#!/usr/bin/env python3
"""OpenRecomp Phase-14 canonical initialization-closure surface V1.

One authoritative description of the production surface, the bounded internal
indirect-target admissions and the deterministic execution budgets used by the
official Phase-14 gates. All values are derived from mechanically observed
fixture behaviour or from the project-owned synthetic model; none is guessed.
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

import p14_c0_surface_v1 as c0_surface  # noqa: E402

SURFACE_VERSION = "1.0.0"

#: BIOS service surface (Phase-13 pinned services plus the Phase-14 additions).
EXTRA_A0 = (0x44,)
EXTRA_C0 = (0x02, 0x03)
EXTRA_B0 = (0x12, 0x13, 0x14, 0x4A, 0x4B, 0x4C)
P14_B0 = (0x56, 0x3F)
P14_A0 = (0x70, 0x30)

#: Bounded, site-specific internal indirect-target admissions. Each site is a
#: real instruction whose source register is derived from immutable static
#: dispatch provenance; the emitter emits a guarded switch and any other value
#: still fails closed. No arbitrary indirect execution is admitted.
INTERNAL_TARGETS: dict[int, tuple[int, ...]] = {
    0x80018B54: (0x8001A908,),
    0x80018A4C: (0x8001A908,),
    0x80016234: (0x80016648,),
    0x8001889C: (0x8001B030,),
    0x8001AA14: (0x8001A31C,),
}

#: The five Phase-13 trace-failure sites that the internal admissions close.
HISTORICAL_INDIRECT_SITES = (0x80018B54, 0x80018A4C, 0x80016234, 0x8001889C)

#: Deterministic budgets. The service/patch chain completes before the first
#: device-MMIO fail-closed event; the frontier budget runs past it.
SERVICE_BLOCK_BUDGET = 475000
FRONTIER_BLOCK_BUDGET = 520000

#: Device MMIO observed on the live post-card path (non-reconstructive
#: classification only; no register semantics are claimed).
OBSERVED_DEVICE_REGISTERS = {
    "timer1_counter": 0x1F801110,
    "gpu_status": 0x1F801814,
    "interrupt_mask": 0x1F801074,
    "cdrom_index_command": 0x1F801800,
}

#: The synthesized card patch source range (the guest's own five-word
#: trampoline). Only bounds are recorded; bytes are read from the private
#: fixture at gate time and never committed.
CARD_PATCH_SOURCE_START = c0_surface.CARD_PATCH_SOURCE_START
CARD_PATCH_SOURCE_END = c0_surface.CARD_PATCH_SOURCE_END


def surface_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase14-closure-surface-v1",
        "surface_version": SURFACE_VERSION,
        "extra_a0": list(EXTRA_A0),
        "extra_c0": list(EXTRA_C0),
        "extra_b0": list(EXTRA_B0),
        "p14_b0": list(P14_B0),
        "p14_a0": list(P14_A0),
        "internal_targets": {
            f"0x{site:08x}": [f"0x{target:08x}" for target in targets]
            for site, targets in sorted(INTERNAL_TARGETS.items())
        },
        "service_block_budget": SERVICE_BLOCK_BUDGET,
        "frontier_block_budget": FRONTIER_BLOCK_BUDGET,
        "c0_surface": c0_surface.surface_document(),
        "arbitrary_indirect_execution": False,
        "card_irq_delivery": "NOT_MODELED",
        "interrupt_mmio": "NOT_MODELED",
        "third_party_code_imported": "NO",
    }
