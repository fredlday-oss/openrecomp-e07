#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1 SPU/audio boundary V1.

The boundary classifies reachable SPU register interactions and provides an
explicit audio service/runtime contract with bounded, deterministic event
recording. No audio synthesis, reverb, sample playback or hardware accuracy is
implemented or claimed; unsupported registers fail closed with an explicit
blocker.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

SPU_BOUNDARY_VERSION = "1.0.0"

SPU_BASE = 0x1F801C00
SPU_SIZE = 0x400
VOICE_BASE = 0x1F801C00
VOICE_SIZE = 0x180
CONTROL_BASE = 0x1F801D80
CONTROL_SIZE = 0x40
TRANSFER_BASE = 0x1F801DA0
TRANSFER_SIZE = 0x10
CD_AUDIO_BASE = 0x1F801DB0
CD_AUDIO_SIZE = 0x10

NAMED_REGISTERS = {
    0x1F801D80: "MAIN_VOLUME_LEFT",
    0x1F801D82: "MAIN_VOLUME_RIGHT",
    0x1F801D88: "VOICE_ON_LOW",
    0x1F801D8A: "VOICE_ON_HIGH",
    0x1F801D8C: "VOICE_OFF_LOW",
    0x1F801D8E: "VOICE_OFF_HIGH",
    0x1F801D90: "PITCH_MOD_LOW",
    0x1F801D92: "PITCH_MOD_HIGH",
    0x1F801D94: "NOISE_ON_LOW",
    0x1F801D96: "NOISE_ON_HIGH",
    0x1F801D98: "REVERB_ON_LOW",
    0x1F801D9A: "REVERB_ON_HIGH",
    0x1F801D9C: "ENDX_LOW",
    0x1F801D9E: "ENDX_HIGH",
    0x1F801DA2: "REVERB_WORK_ADDR",
    0x1F801DA4: "IRQ_ADDR",
    0x1F801DA6: "TRANSFER_ADDR",
    0x1F801DA8: "TRANSFER_DATA",
    0x1F801DAA: "SPU_CONTROL",
    0x1F801DAC: "TRANSFER_CONTROL",
    0x1F801DAE: "SPU_STATUS",
}

TRANSFER_REGISTER_ADDRESSES = frozenset({0x1F801DA6, 0x1F801DA8, 0x1F801DAC})

STUB_POLICY = "contract-stub-not-hardware-accurate"


class SpuBoundaryError(ValueError):
    """Fail-closed SPU boundary rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def classify(address: int) -> str:
    if VOICE_BASE <= address < VOICE_BASE + VOICE_SIZE:
        return "VOICE_REGISTER"
    if address in TRANSFER_REGISTER_ADDRESSES:
        return "TRANSFER_REGISTER"
    if address in NAMED_REGISTERS:
        return "CONTROL_REGISTER"
    if CONTROL_BASE <= address < CONTROL_BASE + CONTROL_SIZE:
        return "CONTROL_REGISTER"
    if TRANSFER_BASE <= address < TRANSFER_BASE + TRANSFER_SIZE:
        return "TRANSFER_REGISTER"
    if CD_AUDIO_BASE <= address < CD_AUDIO_BASE + CD_AUDIO_SIZE:
        return "CD_AUDIO_REGISTER"
    return "UNKNOWN_SPU_REGISTER"


@dataclass
class SpuAdapter:
    """Bounded SPU platform adapter: classify and record, never synthesize."""

    events: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[dict[str, Any]] = field(default_factory=list)

    def _event(self, address: int, width_bits: int, direction: str, value: int | None) -> dict[str, Any]:
        category = classify(address)
        event = {
            "sequence": len(self.events),
            "direction": direction,
            "address": f"0x{address:08x}",
            "width_bits": width_bits,
            "register": NAMED_REGISTERS.get(address, category),
            "category": category,
            "value": None if value is None else f"0x{value:08x}",
            "emulated": False,
            "blocker": category == "UNKNOWN_SPU_REGISTER",
        }
        if category == "UNKNOWN_SPU_REGISTER":
            event["reason"] = "register outside the bounded SPU contract"
        if direction == "read":
            event["stub_policy"] = STUB_POLICY
        self.events.append(event)
        if event["blocker"]:
            self.blockers.append(dict(event))
        return event

    def write(self, address: int, width_bits: int, value: int) -> dict[str, Any]:
        if not (SPU_BASE <= address < SPU_BASE + SPU_SIZE):
            raise SpuBoundaryError("NOT_AN_SPU_PORT", f"0x{address:08x}")
        return self._event(address, width_bits, "write", value)

    def read(self, address: int, width_bits: int) -> dict[str, Any]:
        if not (SPU_BASE <= address < SPU_BASE + SPU_SIZE):
            raise SpuBoundaryError("NOT_AN_SPU_PORT", f"0x{address:08x}")
        return self._event(address, width_bits, "read", 0)

    def document(self) -> dict[str, Any]:
        return {
            "boundary_version": SPU_BOUNDARY_VERSION,
            "emulation": "none-event-recording",
            "audio_synthesis": "none",
            "ranges": {
                "voices": f"0x{VOICE_BASE:08x}+{VOICE_SIZE}",
                "control": f"0x{CONTROL_BASE:08x}+{CONTROL_SIZE}",
                "transfer": f"0x{TRANSFER_BASE:08x}+{TRANSFER_SIZE}",
                "cd_audio": f"0x{CD_AUDIO_BASE:08x}+{CD_AUDIO_SIZE}",
            },
            "named_registers": {f"0x{address:08x}": name for address, name in sorted(NAMED_REGISTERS.items())},
            "read_stubs": {"policy": STUB_POLICY},
            "events": list(self.events),
            "event_count": len(self.events),
            "blocker_count": len(self.blockers),
            "transcript_digest": self.transcript_digest(),
        }

    def transcript_digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.events, sort_keys=True).encode("utf-8")
        ).hexdigest()
