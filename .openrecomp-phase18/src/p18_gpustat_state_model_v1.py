#!/usr/bin/env python3
"""OpenRecomp Phase-18 P18-01 minimal faithful GPUSTAT state model V1.

Phase 17 observed a wait-poll on GPUSTAT (0x1f801814) that never terminated
because the declared MMIO read model (ZERO_FILL_RECORDED) returned a constant
zero for every read.  This module defines the MINIMUM GPUSTAT semantics required
to evaluate the authentic guest poll condition, and nothing more.

Derivation discipline (all three legs are required):

1. the authentic guest poll condition is re-derived from authenticated fixture
   bytes (see p18_poll_condition_auth_v1); it tests a single mask bit, so the
   minimum model only has to be correct for that bit;
2. the bit assignment is documented PS1 GPU behaviour corroborated by two
   independent emulator references (DuckStation GPUSTATReg and PCSX-Redux
   GPUSTATUS_IDLE), both of which place GPU command-ready (idle) at bit 26
   (0x04000000);
3. the value is a function of GPU state, not a title- or PC-specific constant:
   a GPU that is idle and can accept a GP0 command reports the bit set; a GPU
   with a command pending/in flight reports it clear.

Fail-closed design
------------------
Only bit 26 is modelled.  Any request to interpret a GPUSTAT mask outside the
modelled coverage raises GpuStatModelError with code UNMODELLED_GPUSTAT_BIT.
This is deliberate: the Phase-17 failure mode was precisely an unmodelled
status register silently reading back as zero.  A future stage that reaches
guest code consuming a bit this model does not cover must fail closed rather
than inherit a zero that is not caused by device state.

This module promotes no proof marker and asserts no frame/initialization
property.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Physical PS1 GPUSTAT register.
GPUSTAT_PHYS = 0x1F801814

#: GPUSTAT bit reporting the GPU is ready to receive a command
#: (a.k.a. "GPU idle", "CMD ready").
BIT_READY_TO_RECEIVE_CMD = 26
MASK_READY_TO_RECEIVE_CMD = 1 << BIT_READY_TO_RECEIVE_CMD  # 0x04000000

#: The complete set of GPUSTAT bits this model is allowed to synthesise.
MODELLED_BITS: dict[int, str] = {
    BIT_READY_TO_RECEIVE_CMD: "ready_to_receive_cmd",
}

#: Bits observed in the P18-00 frontier analysis that P18-01 deliberately does
#: NOT model (recorded so the coverage boundary is explicit, not implicit).
UNMODELLED_OBSERVED_BITS: dict[int, str] = {
    13: "interlace_field",
    19: "dma_request_ready",
    22: "interlace_mode",
    23: "display_enable",
    28: "ready_to_receive_dma_block",
    31: "ready_to_send_vram_to_cpu",
}


class GpuStatModelError(ValueError):
    """Fail-closed GPUSTAT model rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class GpuState:
    """Minimum GPU state needed to evaluate the observed poll condition.

    command_pending is True while a GP0/GP1 command is queued or in flight and
    the GPU therefore cannot accept a new command immediately.
    """

    command_pending: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.command_pending, bool):
            raise GpuStatModelError(
                "GPUSTAT_STATE_TYPE_INVALID",
                f"command_pending={self.command_pending!r}",
            )

    def ready_to_receive_cmd(self) -> int:
        # 1 when idle and able to accept a command, 0 when busy.
        return 0 if self.command_pending else 1


def modelled_mask() -> int:
    mask = 0
    for bit in MODELLED_BITS:
        mask |= 1 << bit
    return mask


class GpuStatModel:
    """Minimum faithful GPUSTAT model (bit 26 only)."""

    def __init__(self) -> None:
        self._mask = modelled_mask()

    @property
    def coverage(self) -> dict[int, str]:
        return dict(MODELLED_BITS)

    def consume_mask(self, mask: int) -> int:
        """Validate every bit in mask is modelled; return the mask.

        Fails closed (UNMODELLED_GPUSTAT_BIT) when guest code consumes a status
        bit this model does not synthesise.
        """
        if mask < 0:
            raise GpuStatModelError("GPUSTAT_MASK_INVALID", hex(mask & 0xFFFFFFFF))
        unknown = mask & ~self._mask
        if unknown:
            raise GpuStatModelError("UNMODELLED_GPUSTAT_BIT", hex(unknown))
        return mask

    def value(self, state: GpuState) -> int:
        """Synthesise the GPUSTAT word from device state (modelled bits only)."""
        if not isinstance(state, GpuState):
            raise GpuStatModelError("GPUSTAT_STATE_INVALID", repr(type(state)))
        word = 0
        if state.ready_to_receive_cmd():
            word |= MASK_READY_TO_RECEIVE_CMD
        return word & self._mask


def reference_bit26(state: GpuState) -> int:
    """Independent secondary implementation used only for cross-checking.

    Written as a distinct expression so a copy/paste error in GpuStatModel
    cannot silently agree with itself.
    """
    busy = bool(state.command_pending)
    return (1 << BIT_READY_TO_RECEIVE_CMD) if not busy else 0


def reference_value(state: GpuState) -> int:
    return reference_bit26(state)
