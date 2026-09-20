#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1 CD-ROM/file-service boundary V1.

The boundary classifies reachable CD-ROM register interactions and provides an
explicit, bounded disc/file service contract with deterministic event
recording. No disc image, disc bytes, file system or streaming behaviour is
used or emulated; unknown commands fail closed with an explicit blocker.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

CDROM_BOUNDARY_VERSION = "1.0.0"

CDROM_BASE = 0x1F801800
CDROM_SIZE = 0x4

INDEX_STATUS = 0x1F801800
COMMAND = 0x1F801801
PARAMETER = 0x1F801802
INTERRUPT_ENABLE = 0x1F801803

REGISTER_NAMES = {
    INDEX_STATUS: "INDEX_STATUS",
    COMMAND: "COMMAND",
    PARAMETER: "PARAMETER",
    INTERRUPT_ENABLE: "INTERRUPT_ENABLE",
}

#: Documented CD-ROM command bytes (coarse classification only).
COMMAND_CLASSES = {
    0x00: "SYNC",
    0x01: "GET_STAT",
    0x02: "SET_LOCATION",
    0x03: "PLAY",
    0x04: "FORWARD",
    0x05: "BACKWARD",
    0x06: "READ_N",
    0x07: "MOTOR_ON",
    0x08: "STOP",
    0x09: "PAUSE",
    0x0A: "INIT",
    0x0B: "MUTE",
    0x0C: "DEMUTE",
    0x0D: "SET_FILTER",
    0x0E: "SET_MODE",
    0x0F: "GET_PARAM",
    0x10: "GET_LOCATION",
    0x11: "GET_LOCATION_L",
    0x12: "SET_SESSION",
    0x13: "GET_TN",
    0x14: "GET_TD",
    0x15: "SEEK_L",
    0x16: "SEEK_P",
    0x17: "SET_CLOCK",
    0x18: "GET_CLOCK",
    0x19: "TEST",
    0x1A: "GET_ID",
    0x1B: "READ_S",
    0x1C: "RESET",
    0x1D: "GET_Q",
    0x1E: "READ_TOC",
    0x1F: "VIDEO_CD",
}

STUB_POLICY = "contract-stub-not-hardware-accurate"


class CdromBoundaryError(ValueError):
    """Fail-closed CD-ROM boundary rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass
class CdromAdapter:
    """Bounded CD-ROM platform adapter: classify and record, never read discs."""

    events: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[dict[str, Any]] = field(default_factory=list)
    index: int = 0

    def _event(
        self, address: int, width_bits: int, direction: str, value: int | None, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        event = {
            "sequence": len(self.events),
            "direction": direction,
            "address": f"0x{address:08x}",
            "width_bits": width_bits,
            "register": REGISTER_NAMES.get(address, "UNKNOWN"),
            "value": None if value is None else f"0x{value:08x}",
            "disc_image": "none",
            "emulated": False,
            "blocker": False,
        }
        if extra:
            event.update(extra)
        if direction == "read":
            event["stub_policy"] = STUB_POLICY
        self.events.append(event)
        if event["blocker"]:
            self.blockers.append(dict(event))
        return event

    def write(self, address: int, width_bits: int, value: int) -> dict[str, Any]:
        if not (CDROM_BASE <= address < CDROM_BASE + CDROM_SIZE):
            raise CdromBoundaryError("NOT_A_CDROM_PORT", f"0x{address:08x}")
        if address == COMMAND:
            command = value & 0xFF
            name = COMMAND_CLASSES.get(command)
            return self._event(
                address,
                width_bits,
                "write",
                value,
                {
                    "class": name or "UNKNOWN_COMMAND",
                    "command": f"0x{command:02x}",
                    "blocker": name is None,
                    "reason": None if name else "command outside the bounded contract",
                },
            )
        if address == INDEX_STATUS:
            self.index = value & 0x03
            return self._event(address, width_bits, "write", value, {"class": "INDEX_SET", "index": self.index})
        if address == PARAMETER:
            return self._event(address, width_bits, "write", value, {"class": "PARAMETER_FIFO"})
        return self._event(address, width_bits, "write", value, {"class": "INTERRUPT_ENABLE_WRITE"})

    def read(self, address: int, width_bits: int) -> dict[str, Any]:
        if not (CDROM_BASE <= address < CDROM_BASE + CDROM_SIZE):
            raise CdromBoundaryError("NOT_A_CDROM_PORT", f"0x{address:08x}")
        if address == INDEX_STATUS:
            return self._event(address, width_bits, "read", self.index, {"class": "INDEX_STATUS_STUB"})
        if address == INTERRUPT_ENABLE:
            return self._event(address, width_bits, "read", 0, {"class": "INTERRUPT_STUB"})
        return self._event(address, width_bits, "read", 0, {"class": "READ_STUB"})

    def document(self) -> dict[str, Any]:
        return {
            "boundary_version": CDROM_BOUNDARY_VERSION,
            "emulation": "none-event-recording",
            "disc_image": "none",
            "file_service": "none",
            "ports": {f"0x{address:08x}": name for address, name in sorted(REGISTER_NAMES.items())},
            "command_classes": {f"0x{command:02x}": name for command, name in sorted(COMMAND_CLASSES.items())},
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
