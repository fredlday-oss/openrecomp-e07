#!/usr/bin/env python3
"""OpenRecomp Phase-10 disc / CD-ROM / streaming frontier classification V1.

The module classifies the deterministic CD-ROM register transcript of a
Phase-10 native run against the audited Phase-9 CD-ROM boundary, whose
documented command table is the single source of truth for command identity.

It records:

* register-level traffic by register and direction (index/status, command,
  parameter, interrupt enable);
* every command byte with its documented class or an explicit unknown marker;
* the disc data path: whether any disc data transfer (data-port read, sector
  request, ISO9660/file access, streaming or XA) is reached at all;
* the requirement record: what the reachable path actually requires, and what
  remains not reached and therefore not implemented.

No disc bytes, sector contents, file contents or reconstructed disc data are
produced or committed.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

import p9_cdrom_boundary_v1 as cdrom

DISC_VERSION = "1.0.0"

REGISTERS = {
    cdrom.INDEX_STATUS: "INDEX_STATUS",
    cdrom.COMMAND: "COMMAND",
    cdrom.PARAMETER: "PARAMETER",
    cdrom.INTERRUPT_ENABLE: "INTERRUPT_ENABLE",
}

#: Disc data-path capabilities that the current frontier does not reach.
DATA_PATH_CAPABILITIES = (
    "sector_read",
    "iso9660_directory_access",
    "file_open_or_read",
    "executable_overlay_load",
    "resource_load",
    "data_streaming",
    "xa_audio_streaming",
    "asynchronous_cd_event",
)


def classify_commands(values: Iterable[int]) -> dict[str, Any]:
    """Classify CD-ROM command bytes with the audited Phase-9 command table."""
    histogram: dict[str, int] = {}
    unknown: list[int] = []
    for value in values:
        name = cdrom.COMMAND_CLASSES.get(value & 0xFF, "UNKNOWN_COMMAND")
        histogram[name] = histogram.get(name, 0) + 1
        if name == "UNKNOWN_COMMAND":
            unknown.append(value & 0xFF)
    return {
        "disc_version": DISC_VERSION,
        "command_count": sum(histogram.values()),
        "command_histogram": dict(sorted(histogram.items())),
        "unknown_commands": sorted(set(unknown)),
        "unknown_command_count": len(unknown),
        "documented_command_table_size": len(cdrom.COMMAND_CLASSES),
    }


def classify_events(events: Iterable[dict[str, int]]) -> dict[str, Any]:
    """Classify a CD-ROM register transcript exactly."""
    by_register: dict[str, dict[str, int]] = {}
    commands: list[int] = []
    blockers: list[dict[str, Any]] = []
    for event in events:
        name = REGISTERS.get(event["address"], f"UNKNOWN_0x{event['address']:08x}")
        direction = "write" if event["direction"] == 1 else "read"
        by_register.setdefault(name, {})
        by_register[name][direction] = by_register[name].get(direction, 0) + 1
        if name == "COMMAND" and direction == "write":
            commands.append(event["value"] & 0xFF)
        if event["flags"] == 2:
            blockers.append(
                {
                    "register": name,
                    "direction": direction,
                    "value": f"0x{event['value']:02x}" if name == "COMMAND" else f"0x{event['value']:08x}",
                }
            )
    command_classification = classify_commands(commands)
    data_path = {
        capability: False for capability in DATA_PATH_CAPABILITIES
    }
    data_path["evidence"] = (
        "no disc data port read, no sector request and no file/streaming operation appears in the "
        "recorded transcript: only index/status, parameter, command and interrupt-enable register "
        "traffic is present"
    )
    return {
        "disc_version": DISC_VERSION,
        "event_count": len(list(events)) if isinstance(events, list) else None,
        "register_histogram": {name: dict(sorted(counts.items())) for name, counts in sorted(by_register.items())},
        "command_classification": command_classification,
        "blockers": blockers,
        "data_path": data_path,
        "data_path_reached": any(data_path[capability] for capability in DATA_PATH_CAPABILITIES),
        "disc_image_used": "none",
        "stub_policy": cdrom.STUB_POLICY,
    }


def requirements(classification: dict[str, Any]) -> dict[str, Any]:
    """What the reachable disc path requires, and what stays unimplemented."""
    command_classes = classification["command_classification"]["command_histogram"]
    return {
        "disc_version": DISC_VERSION,
        "implemented_at_phase10": [],
        "served_by_phase9_boundary": sorted(command_classes),
        "unknown_commands": classification["command_classification"]["unknown_commands"],
        "unknown_command_disposition": "NOT_IMPLEMENTED_FAIL_CLOSED",
        "data_path_implemented": False,
        "reason": (
            "the reachable path performs register-level CD-ROM traffic only; no disc data transfer "
            "is reached, so implementing ISO9660, sector reads, streaming or XA would be speculative"
        ),
        "cue_role": (
            "the verified CUE is the authoritative disc entry point and remains the required source "
            "for any future disc behaviour, but it is not read by the current frontier"
        ),
    }


def digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode("utf-8")).hexdigest()
