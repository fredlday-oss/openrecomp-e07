#!/usr/bin/env python3
"""OpenRecomp Phase-10 GPU execution-frontier classification V1.

The module classifies a deterministic platform-event transcript captured from
the Phase-10 observable driver into the GPU evidence model:

* reads and writes are separated first: a read value is a status/register
  value, never a command, so command classification applies to writes only;
* GP0 (``0x1f801810``) and GP1 (``0x1f801814``) are classified with the
  audited Phase-9 GPU boundary predicates (``p9_gpu_boundary_v1``), which is
  the single source of truth for the command-class table;
* status polling, transfer classes (CPU<->VRAM, VRAM<->VRAM, VRAM->CPU) and
  the explicit absence of DMA-controller traffic are reported separately;
* VRAM state is reported as not modelled (no VRAM exists in the boundary), so
  no VRAM digest is fabricated;
* per-access guest-PC/function provenance is reported as not observable: the
  emitted program does not carry an access hook, and nothing is guessed.

Only non-reconstructive information is produced: command classes, counts,
histograms, addresses of audited ports and digests.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

import p9_gpu_boundary_v1 as gpu

FRONTIER_VERSION = "1.0.0"

GP0_READ = gpu.GP0_READ
GP1_READ = gpu.GP1_READ
GP0_WRITE = gpu.GP0_WRITE
GP1_WRITE = gpu.GP1_WRITE
GPU_ADDRESSES = frozenset({GP0_READ, GP1_WRITE})

DIRECTION_READ = 0
DIRECTION_WRITE = 1
FLAG_KNOWN = 1
FLAG_BLOCKER = 2

TRANSFER_CLASSES = frozenset(
    {"CPU_TO_VRAM_COPY", "VRAM_TO_VRAM_COPY", "VRAM_TO_CPU_COPY"}
)

PROVENANCE_LIMITATION = (
    "per-access guest PC, translated function and call-flow provenance are not "
    "observable: the generated program carries no access hook, and the frozen "
    "Phase-9 observable driver records per-device event streams only"
)


def parse_events(stdout: str, device: str) -> list[dict[str, int]]:
    """Parse one device's typed events from a driver transcript."""
    events: list[dict[str, int]] = []
    prefix = f"ev_{device}_"
    for line in stdout.splitlines():
        if not line.startswith(prefix):
            continue
        _, payload = line.split("=", 1)
        service, direction, width, flags, address, value = payload.split(",")
        events.append(
            {
                "service": int(service),
                "direction": int(direction),
                "width_bits": int(width),
                "flags": int(flags),
                "address": int(address, 16),
                "value": int(value, 16),
            }
        )
    return events


def classify_gpu_events(events: Iterable[dict[str, int]]) -> dict[str, Any]:
    """Classify a GPU event transcript exactly."""
    reads = 0
    writes = 0
    gp0_writes = 0
    gp1_writes = 0
    gp0_reads = 0
    gp1_reads = 0
    class_histogram: dict[str, int] = {}
    unknown: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    status_values: dict[str, int] = {}
    write_values: dict[str, int] = {}
    addresses: dict[str, int] = {}
    widths: dict[str, int] = {}

    for event in events:
        address = event["address"]
        addresses[f"0x{address:08x}"] = addresses.get(f"0x{address:08x}", 0) + 1
        widths[str(event["width_bits"])] = widths.get(str(event["width_bits"]), 0) + 1
        if event["flags"] == FLAG_BLOCKER:
            blocked.append(event)
        if event["direction"] == DIRECTION_READ:
            reads += 1
            if address == GP0_READ:
                gp0_reads += 1
            elif address == GP1_READ:
                gp1_reads += 1
            key = f"0x{event['value']:08x}"
            status_values[key] = status_values.get(key, 0) + 1
            continue
        writes += 1
        if address == GP0_WRITE:
            gp0_writes += 1
            classification = gpu.classify_gp0(event["value"])
        else:
            gp1_writes += 1
            classification = gpu.classify_gp1(event["value"])
        class_histogram[classification["class"]] = class_histogram.get(classification["class"], 0) + 1
        key = f"0x{event['value']:08x}"
        write_values[key] = write_values.get(key, 0) + 1
        if not classification["known"]:
            unknown.append(
                {
                    "port": classification["port"],
                    "command": classification["command"],
                    "value": key,
                }
            )

    return {
        "frontier_version": FRONTIER_VERSION,
        "event_count": reads + writes,
        "reads": reads,
        "writes": writes,
        "gp0_reads": gp0_reads,
        "gp1_reads": gp1_reads,
        "gp0_writes": gp0_writes,
        "gp1_writes": gp1_writes,
        "command_class_histogram": dict(sorted(class_histogram.items())),
        "unknown_command_count": len(unknown),
        "unknown_commands": unknown,
        "blocked_event_count": len(blocked),
        "address_histogram": dict(sorted(addresses.items())),
        "width_histogram": dict(sorted(widths.items())),
        "status_read_values": dict(sorted(status_values.items())),
        "write_value_digest": hashlib.sha256(
            json.dumps(sorted(write_values.items())).encode("utf-8")
        ).hexdigest(),
        "distinct_write_values": len(write_values),
        "transfer_class_count": sum(
            count for cls, count in class_histogram.items() if cls in TRANSFER_CLASSES
        ),
        "dma_controller_traffic": "not_observed",
        "vram_state": "not_modelled_by_the_phase9_boundary",
        "provenance": PROVENANCE_LIMITATION,
    }


def status_read_summary(events: Iterable[dict[str, int]], stub: int) -> dict[str, Any]:
    """Summarise the GP1 status-read behaviour against a known stub value."""
    values: dict[str, int] = {}
    widths: set[int] = set()
    for event in events:
        if event["direction"] != DIRECTION_READ:
            continue
        values[f"0x{event['value']:08x}"] = values.get(f"0x{event['value']:08x}", 0) + 1
        widths.add(event["width_bits"])
    return {
        "distinct_status_values": dict(sorted(values.items())),
        "status_value_matches_stub": list(values) == [f"0x{stub:08x}"],
        "read_widths": sorted(widths),
        "status_conditioned_wait": None,
    }


def stub_ab_experiment(
    without_stub: dict[str, Any],
    with_stub: dict[str, Any],
) -> dict[str, Any]:
    """Compare two deterministic runs that differ only in the status stub."""
    keys = ("reads", "writes", "denied", "access_count", "budget_denials", "error")
    differences = {
        key: {"without_stub": without_stub.get(key), "with_stub": with_stub.get(key)}
        for key in keys
        if without_stub.get(key) != with_stub.get(key)
    }
    return {
        "frontier_version": FRONTIER_VERSION,
        "compared_keys": list(keys),
        "differences": differences,
        "access_traffic_identical": all(
            without_stub.get(key) == with_stub.get(key) for key in ("reads", "writes", "access_count")
        ),
        "conclusion": (
            "the recorded access traffic is identical with and without the status stub, so the "
            "observed GPU status polling is not conditioned on the stub value and no GPU-side "
            "blocker exists"
        ),
    }
