#!/usr/bin/env python3
"""OpenRecomp Phase-18 P18-01 GPUSTAT reference constants V1.

This module is an INDEPENDENT data source for the bit-26 assignment.  It encodes
the GPUSTAT "GPU command ready / idle" bit as declared by two independent
open-source PlayStation GPU implementations, so the P18-01 gate can check that
the mask the *guest actually tests* (derived from authenticated fixture bytes)
agrees with documented hardware behaviour, instead of merely restating the
model.

Sources (public, non-Sony, independent emulator source code):

* DuckStation, src/core/gpu_types.h, union GPUSTATReg:
      BitField<u32, bool, 26, 1> gpu_idle;
      BitField<u32, bool, 27, 1> ready_to_send_vram;
      BitField<u32, bool, 28, 1> ready_to_receive_dma;
* PCSX-Redux, src/core/gpu.cc:
      #define GPUSTATUS_READYFORVRAM 0x08000000   (bit 27)
      #define GPUSTATUS_IDLE         0x04000000   // CMD ready (bit 26)

Both place the GPU command-ready ("idle") flag at bit 26, value 0x04000000.

This module carries no fixture bytes and promotes no proof marker.
"""

from __future__ import annotations

#: Bit index for GPU command-ready / idle, per the two references above.
REFERENCE_READY_BIT = 26
#: Mask value for that bit.
REFERENCE_READY_MASK = 1 << REFERENCE_READY_BIT  # 0x04000000

#: Additional documented GPUSTAT bits, recorded for boundary clarity only.
REFERENCE_OTHER_BITS: dict[str, int] = {
    "ready_to_send_vram": 0x08000000,
    "ready_to_receive_dma": 0x10000000,
    "dma_data_request": 0x02000000,
    "interrupt_request": 0x01000000,
}

#: Provenance of the constants (public identifiers only; no private paths).
REFERENCE_SOURCES: tuple[dict[str, str], ...] = (
    {
        "project": "DuckStation",
        "file": "src/core/gpu_types.h",
        "symbol": "GPUSTATReg::gpu_idle (bit 26)",
    },
    {
        "project": "PCSX-Redux",
        "file": "src/core/gpu.cc",
        "symbol": "GPUSTATUS_IDLE 0x04000000 // CMD ready",
    },
)


def reference_mask() -> int:
    return REFERENCE_READY_MASK


def agrees_with_mask(mask: int) -> bool:
    """True when mask is exactly the documented command-ready bit."""
    return mask == REFERENCE_READY_MASK
