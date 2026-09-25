#!/usr/bin/env python3
"""OpenRecomp Phase-16 canonical CD-ROM execution & surface V1.

Authoritative description of the Phase-16 production surface:
- C0:0x0A (ChangeClearRCnt) admission
- 0x8001AA14 indirect jump resolution: (0x8001A31C, 0x8001A0C0)
- CD-ROM sector delivery contract for authentic Hercules disc image
- GP0 (0x1F801810) LoadImage (0xA0) multi-word parameter/data accounting
- Deterministic execution budgets and A0:0x43 Exec terminal telemetry
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src", ".openrecomp-phase15/src"):
    sys.path.insert(0, str(ROOT / extra))

import p15_surface_v1 as surface15  # noqa: E402
from p16_contracts_v1 import (
    TITLE_ENTRY_PC,
    TITLE_PAYLOAD_SECTORS,
    TITLE_PAYLOAD_SHA256,
    TITLE_PAYLOAD_SIZE,
    TITLE_SP_ADDR,
    TITLE_START_LBA,
    TITLE_TEXT_ADDR,
    TITLE_TOTAL_SECTORS,
)

SURFACE_VERSION = "1.0.0"

#: BIOS service surface (Phase 15 surface plus C0:0x0A).
EXTRA_A0 = surface15.EXTRA_A0
EXTRA_C0 = (0x02, 0x03, 0x0A)
EXTRA_B0 = surface15.EXTRA_B0
P14_B0 = surface15.P14_B0
P14_A0 = surface15.P14_A0
P15_A0 = surface15.P15_A0
P15_B0 = surface15.P15_B0

#: Bounded internal indirect-target admissions (includes 0x8001aa14 branch targets).
INTERNAL_TARGETS = dict(surface15.INTERNAL_TARGETS)
INTERNAL_TARGETS[0x8001AA14] = (0x8001A31C, 0x8001A0C0)
HISTORICAL_INDIRECT_SITES = surface15.HISTORICAL_INDIRECT_SITES

#: Deterministic execution budgets.
SERVICE_BLOCK_BUDGET = surface15.SERVICE_BLOCK_BUDGET
FRONTIER_BLOCK_BUDGET = 2_000_000
BOUNDARY_BLOCK_BUDGET = surface15.BOUNDARY_BLOCK_BUDGET

#: Peripheral / MMIO registers from Phase 15.
MMIO_REGISTERS = dict(surface15.MMIO_REGISTERS)
OBSERVED_DEVICE_REGISTERS = surface15.OBSERVED_DEVICE_REGISTERS
GPUSTAT_STUB = surface15.GPUSTAT_STUB
FRAME_TICK_ADDRESS = surface15.FRAME_TICK_ADDRESS

#: CD-ROM sector format constants.
CD_RAW_SECTOR_SIZE = 2352
CD_USER_DATA_OFFSET = 24
CD_USER_DATA_SIZE = 2048
CD_MAX_LBA = 174087


def mmio_addresses() -> set[int]:
    return surface15.mmio_addresses()


def surface_document() -> dict[str, Any]:
    doc = surface15.surface_document()
    doc["schema"] = "openrecomp-phase16-surface-v1"
    doc["surface_version"] = SURFACE_VERSION
    doc["extra_c0"] = list(EXTRA_C0)
    doc["internal_targets"] = {
        f"0x{site:08x}": [f"0x{target:08x}" for target in targets]
        for site, targets in sorted(INTERNAL_TARGETS.items())
    }
    doc["frontier_block_budget"] = FRONTIER_BLOCK_BUDGET
    doc["cdrom"] = {
        "title_start_lba": TITLE_START_LBA,
        "title_total_sectors": TITLE_TOTAL_SECTORS,
        "title_payload_sectors": TITLE_PAYLOAD_SECTORS,
        "title_payload_size": TITLE_PAYLOAD_SIZE,
        "title_payload_sha256": TITLE_PAYLOAD_SHA256,
        "title_text_addr": f"0x{TITLE_TEXT_ADDR:08x}",
        "title_entry_pc": f"0x{TITLE_ENTRY_PC:08x}",
        "title_sp_addr": f"0x{TITLE_SP_ADDR:08x}",
        "raw_sector_size": CD_RAW_SECTOR_SIZE,
        "user_data_offset": CD_USER_DATA_OFFSET,
        "user_data_size": CD_USER_DATA_SIZE,
    }
    return doc
