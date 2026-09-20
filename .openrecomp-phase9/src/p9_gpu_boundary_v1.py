#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1 GPU/runtime boundary V1.

This module defines a clean platform adapter boundary for the reachable
GPU-facing behaviour of the bounded fixtures. It does **not** emulate the
PS1 GPU: writes to GP0/GP1 are classified against a documented command table
and recorded as a deterministic typed event transcript; reads return explicit
contract stubs labelled as such. Unknown commands become explicit unresolved
blockers and never guess behaviour.

The adapter is host-side only; it contains no GPU hardware emulation, no
rendering and no console-derived material.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

GPU_BOUNDARY_VERSION = "1.0.0"

GP0_WRITE = 0x1F801810
GP0_READ = 0x1F801810
GP1_WRITE = 0x1F801814
GP1_READ = 0x1F801814

GPU_PORTS = {
    GP0_WRITE: {"name": "GP0", "direction": "write", "width_bits": 32},
    GP1_WRITE: {"name": "GP1", "direction": "write", "width_bits": 32},
}

#: Documented GP0 command-class table (coarse classification only).
GP0_CLASSES = (
    (0x00, 0x00, "NOP"),
    (0x01, 0x01, "CLEAR_CACHE"),
    (0x02, 0x02, "FILL_RECTANGLE"),
    (0x20, 0x3F, "POLYGON"),
    (0x40, 0x5F, "LINE"),
    (0x60, 0x7F, "RECTANGLE"),
    (0x80, 0x9F, "VRAM_TO_VRAM_COPY"),
    (0xA0, 0xBF, "CPU_TO_VRAM_COPY"),
    (0xC0, 0xDF, "VRAM_TO_CPU_COPY"),
    (0xE0, 0xE7, "DRAW_ENVIRONMENT"),
)

#: Documented GP1 command table (coarse classification only).
GP1_CLASSES = (
    (0x00, 0x00, "RESET_GPU"),
    (0x01, 0x01, "RESET_COMMAND_BUFFER"),
    (0x02, 0x02, "ACKNOWLEDGE_IRQ"),
    (0x03, 0x03, "DISPLAY_ENABLE"),
    (0x04, 0x04, "DMA_DIRECTION"),
    (0x05, 0x05, "DISPLAY_VRAM_START"),
    (0x06, 0x06, "HORIZONTAL_DISPLAY_RANGE"),
    (0x07, 0x07, "VERTICAL_DISPLAY_RANGE"),
    (0x08, 0x08, "DISPLAY_MODE"),
    (0x10, 0x10, "GET_GPU_INFO"),
)

#: Explicit contract stubs for GPU reads (not hardware-accurate).
GPUSTAT_STUB = 0x14802000
GPUREAD_STUB = 0x00000000
STUB_POLICY = "contract-stub-not-hardware-accurate"


def _classify(table: tuple[tuple[int, int, str], ...], command: int) -> str:
    for low, high, name in table:
        if low <= command <= high:
            return name
    return "UNKNOWN_COMMAND"


def classify_gp0(value: int) -> dict[str, Any]:
    command = (value >> 24) & 0xFF
    name = _classify(GP0_CLASSES, command)
    return {
        "port": "GP0",
        "command": f"0x{command:02x}",
        "class": name,
        "known": name != "UNKNOWN_COMMAND",
        "emulated": False,
    }


def classify_gp1(value: int) -> dict[str, Any]:
    command = (value >> 24) & 0xFF
    name = _classify(GP1_CLASSES, command)
    return {
        "port": "GP1",
        "command": f"0x{command:02x}",
        "class": name,
        "known": name != "UNKNOWN_COMMAND",
        "emulated": False,
    }


@dataclass
class GpuAdapter:
    """Bounded GPU platform adapter: classify and record, never emulate."""

    events: list[dict[str, Any]] = field(default_factory=list)
    unknown_commands: list[dict[str, Any]] = field(default_factory=list)
    write_count: int = 0
    read_count: int = 0

    def write(self, address: int, width_bits: int, value: int) -> dict[str, Any]:
        port = GPU_PORTS.get(address)
        if port is None or port["direction"] != "write":
            raise ValueError(f"not a GPU write port: 0x{address:08x}")
        if width_bits != port["width_bits"]:
            raise ValueError(f"GPU write width {width_bits} unsupported on {port['name']}")
        classification = classify_gp0(value) if port["name"] == "GP0" else classify_gp1(value)
        event = {
            "sequence": len(self.events),
            "direction": "write",
            "port": port["name"],
            "address": f"0x{address:08x}",
            "width_bits": width_bits,
            "value": f"0x{value & 0xFFFFFFFF:08x}",
            **classification,
        }
        self.events.append(event)
        self.write_count += 1
        if not classification["known"]:
            self.unknown_commands.append(dict(event))
        return event

    def read(self, address: int, width_bits: int) -> dict[str, Any]:
        if address == GP0_READ:
            port, value = "GP0", GPUREAD_STUB
        elif address == GP1_READ:
            port, value = "GP1", GPUSTAT_STUB
        else:
            raise ValueError(f"not a GPU read port: 0x{address:08x}")
        if width_bits != 32:
            raise ValueError(f"GPU read width {width_bits} unsupported on {port}")
        event = {
            "sequence": len(self.events),
            "direction": "read",
            "port": port,
            "address": f"0x{address:08x}",
            "width_bits": width_bits,
            "value": f"0x{value:08x}",
            "class": "CONTRACT_STUB",
            "known": True,
            "emulated": False,
            "stub_policy": STUB_POLICY,
        }
        self.events.append(event)
        self.read_count += 1
        return event

    def document(self) -> dict[str, Any]:
        return {
            "boundary_version": GPU_BOUNDARY_VERSION,
            "emulation": "none-event-recording",
            "ports": {
                f"0x{address:08x}": dict(port) for address, port in sorted(GPU_PORTS.items())
            },
            "gp0_command_classes": [
                {"low": f"0x{low:02x}", "high": f"0x{high:02x}", "class": name}
                for low, high, name in GP0_CLASSES
            ],
            "gp1_command_classes": [
                {"low": f"0x{low:02x}", "high": f"0x{high:02x}", "class": name}
                for low, high, name in GP1_CLASSES
            ],
            "read_stubs": {
                "GP0": f"0x{GPUREAD_STUB:08x}",
                "GP1": f"0x{GPUSTAT_STUB:08x}",
                "policy": STUB_POLICY,
            },
            "events": list(self.events),
            "event_count": len(self.events),
            "write_count": self.write_count,
            "read_count": self.read_count,
            "unknown_commands": list(self.unknown_commands),
            "unknown_command_count": len(self.unknown_commands),
            "transcript_digest": self.transcript_digest(),
        }

    def transcript_digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.events, sort_keys=True).encode("utf-8")
        ).hexdigest()
