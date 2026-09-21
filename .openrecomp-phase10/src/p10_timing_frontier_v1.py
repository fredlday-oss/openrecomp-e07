#!/usr/bin/env python3
"""OpenRecomp Phase-10 interrupt / DMA / timing frontier classification V1.

The module classifies the deterministic non-RAM access log of a Phase-10 native
run into:

* **served device accesses**: every access landing inside an audited Phase-9
  port range (GPU, controller/timer, SPU, CD-ROM, interrupt) together with its
  event category;
* **platform denials**: accesses that are recorded as blockers or that land
  outside every audited range, so the platform boundary refuses them;
* **budget denials**: accesses refused by the deterministic bounded-execution
  budget;
* **the denial reconciliation**: platform denials plus budget denials equal the
  runtime's denied counter exactly, so no denial stays unattributed.

Addresses outside the audited ranges are reported by *address* with a clearly
labelled public architectural address identification (never an implemented
behaviour and never a semantic assumption). Dispositions are fail-closed unless
direct evidence proves an interaction is required to progress.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

import p9_cdrom_boundary_v1 as cdrom
import p9_gpu_boundary_v1 as gpu
import p9_input_timer_v1 as input_timer
import p9_io_discovery_v1 as io
import p9_spu_boundary_v1 as spu

TIMING_VERSION = "1.0.0"

#: The audited Phase-9 port ranges, reused unchanged.
AUDITED_RANGES = (
    io.IoRange("gpu", gpu.GP0_WRITE, 8),
    io.IoRange("joy", input_timer.JOY_DATA, 0x10),
    io.IoRange("timer0", input_timer.TIMER_PORTS["timer0"][0], 0x10),
    io.IoRange("timer1", input_timer.TIMER_PORTS["timer1"][0], 0x10),
    io.IoRange("timer2", input_timer.TIMER_PORTS["timer2"][0], 0x10),
    io.IoRange("spu", spu.SPU_BASE, 0x400),
    io.IoRange("cdrom", cdrom.CDROM_BASE, 0x4),
    io.IoRange("interrupt", input_timer.I_STAT, 0x8),
)

#: Public architectural identifications for the denied addresses observed in the
#: private run. These are address identifications only: no behaviour is
#: implemented, assumed or emulated for them.
ARCHITECTURAL_ADDRESS_NOTES = {
    0x1F801020: "memory-control common delay register (public architecture address identification)",
    0x1F8010A8: "DMA channel-2 (GPU) channel-control register (public architecture address identification)",
    0x00000000: "low exception-vector / null-pointer window (public architecture address identification)",
    0x14802000: "the GPU status contract stub value used as an address, i.e. a corrupted pointer read",
}

#: The deterministic virtual-time abstraction implemented by the Phase-9
#: runtime. It is a bounded, reproducible counter, not a cycle-accurate model.
TIMING_ABSTRACTION = {
    "counter_read": "timer counter reads return (tick & 0xffff) and advance the tick by one",
    "tick_origin": "zero at runtime initialisation",
    "resolution": "one tick per counter read (read-driven, not clock-driven)",
    "cycle_accuracy": "not claimed",
    "wall_clock_dependency": "none",
    "max_counter_reads_before_wrap": 65536,
}

DISPOSITION_FAIL_CLOSED = "NOT_IMPLEMENTED_FAIL_CLOSED"

ERROR_CODES = (
    "NO_NONRAM_LOG",
    "DENIAL_MISMATCH",
    "UNKNOWN_CLASSIFICATION",
)


class TimingFrontierError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown timing frontier error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def classify_address(address: int) -> str | None:
    for entry in AUDITED_RANGES:
        if entry.base <= address < entry.base + entry.size:
            return entry.name
    return None


def parse_nonram_log(stdout: str) -> list[dict[str, int]]:
    entries: list[dict[str, int]] = []
    for line in stdout.splitlines():
        if not line.startswith("nonram_") or "=" not in line:
            continue
        key, payload = line.split("=", 1)
        if key in ("nonram_signatures", "nonram_overflow"):
            continue
        address, width, is_write, reason, count = payload.split(",")
        entries.append(
            {
                "address": int(address, 16),
                "width_bits": int(width),
                "is_write": int(is_write),
                "reason": int(reason),
                "count": int(count),
            }
        )
    if not entries:
        raise TimingFrontierError("NO_NONRAM_LOG", "no nonram_* entries in the transcript")
    return entries


def parse_scalar_fields(stdout: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in stdout.splitlines():
        if line.startswith("ev_"):
            continue
        if line.startswith("nonram_") and not (
            line.startswith("nonram_signatures") or line.startswith("nonram_overflow")
        ):
            continue
        if line.startswith("r") and len(line) > 1 and line[1].isdigit():
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return fields


def blocker_addresses(stdout: str) -> dict[int, int]:
    """Addresses of blocker-flagged platform events, mapped to their counts."""
    counts: dict[int, int] = {}
    for line in stdout.splitlines():
        if not line.startswith("ev_"):
            continue
        _, payload = line.split("=", 1)
        _service, _direction, _width, flags, address, _value = payload.split(",")
        if int(flags) == 2:
            key = int(address, 16)
            counts[key] = counts.get(key, 0) + 1
    return counts


def classify(nonram: Iterable[dict[str, int]], stdout: str) -> dict[str, Any]:
    fields = parse_scalar_fields(stdout)
    blocked = blocker_addresses(stdout)

    served: list[dict[str, Any]] = []
    denied: list[dict[str, Any]] = []
    for entry in nonram:
        device = classify_address(entry["address"])
        address = f"0x{entry['address']:08x}"
        budget_denied = entry["reason"] == 1
        blocked_count = blocked.get(entry["address"], 0)
        if budget_denied:
            denied_count = entry["count"]
            served_count = 0
            classification = "BUDGET_DENIED"
        elif device is None:
            denied_count = entry["count"]
            served_count = 0
            classification = "OUTSIDE_AUDITED_RANGES"
        else:
            denied_count = blocked_count
            served_count = entry["count"] - blocked_count
            classification = f"AUDITED_{device.upper()}"
            if blocked_count:
                classification += "_BLOCKED"
        record = {
            "address": address,
            "width_bits": entry["width_bits"],
            "direction": "write" if entry["is_write"] else "read",
            "classification": classification,
            "observations": entry["count"],
            "denied_observations": denied_count,
            "served_observations": served_count,
        }
        if denied_count and (device is None):
            record["note"] = ARCHITECTURAL_ADDRESS_NOTES.get(
                entry["address"], "no architectural identification recorded"
            )
        if budget_denied:
            record["disposition"] = "BOUNDED_EXECUTION_BUDGET"
            denied.append(record)
        elif denied_count:
            record["disposition"] = DISPOSITION_FAIL_CLOSED
            denied.append(record)
        else:
            record["disposition"] = "SERVED_BY_PHASE9_BOUNDARY"
            served.append(record)

    platform_denials = sum(
        entry["denied_observations"] for entry in denied if entry["classification"] != "BUDGET_DENIED"
    )
    logged_budget_denials = sum(
        entry["denied_observations"] for entry in denied if entry["classification"] == "BUDGET_DENIED"
    )
    budget_denials = int(fields.get("p10_budget_denials", "0"))
    denied_total = int(fields.get("denied", "0"))

    served_observations = sum(entry["served_observations"] for entry in served) + sum(
        entry["served_observations"] for entry in denied
    )
    denied_observations = sum(entry["denied_observations"] for entry in denied)
    reconciliation = {
        "platform_denial_observations": platform_denials,
        "logged_budget_denial_observations": logged_budget_denials,
        "budget_denials": budget_denials,
        "expected_total": platform_denials + budget_denials,
        "reported_denied": denied_total,
        "matches": platform_denials + budget_denials == denied_total,
        "logged_budget_subset_of_counter": logged_budget_denials <= budget_denials,
    }
    if not reconciliation["matches"]:
        raise TimingFrontierError(
            "DENIAL_MISMATCH",
            json.dumps(reconciliation, sort_keys=True),
        )

    histogram: dict[str, int] = {}
    for entry in served + denied:
        histogram[entry["classification"]] = (
            histogram.get(entry["classification"], 0) + entry["observations"]
        )

    return {
        "timing_version": TIMING_VERSION,
        "signature_count": len(served) + len(denied),
        "served": served,
        "denied": denied,
        "served_observations": served_observations,
        "denied_observations": denied_observations,
        "classification_histogram": dict(sorted(histogram.items())),
        "reconciliation": reconciliation,
        "blocked_addresses": {f"0x{address:08x}": count for address, count in sorted(blocked.items())},
        "read_budget": int(fields.get("p10_access_budget", "0")),
        "access_count": int(fields.get("p10_access_count", "0")),
        "first_failure": fields.get("error"),
        "timing_abstraction": dict(TIMING_ABSTRACTION),
        "counters": {
            key: int(fields.get(key, "0"))
            for key in ("reads", "writes", "host_calls", "gpu_events", "input_events", "spu_events", "cdrom_events")
        },
    }


def requirements(classification: dict[str, Any]) -> dict[str, Any]:
    """Dispositions for every interrupt/DMA/timing interaction observed."""
    served_devices = sorted(
        {
            entry["classification"].split("_")[1].lower()
            for entry in classification["served"]
        }
    )
    denied_devices = sorted(
        {entry["classification"] for entry in classification["denied"]}
    )
    return {
        "timing_version": TIMING_VERSION,
        "served_devices": served_devices,
        "denied_classes": denied_devices,
        "implemented_at_phase10": [],
        "dispositions": [
            {
                "interaction": "timer counter reads",
                "evidence": "paired one-to-one with the GPU status reads; served by the deterministic virtual-time counter",
                "required": True,
                "implemented": "already served by the Phase-9 runtime",
            },
            {
                "interaction": "interrupt mask read",
                "evidence": "one blocked read at 0x1f801074; no interrupt-status read and no interrupt-dependent wait is proven",
                "required": False,
                "implemented": False,
                "disposition": DISPOSITION_FAIL_CLOSED,
            },
            {
                "interaction": "DMA channel-2 (GPU) configuration",
                "evidence": "one denied 32-bit write at 0x1f8010a8; no transfer request or completion wait is proven",
                "required": False,
                "implemented": False,
                "disposition": DISPOSITION_FAIL_CLOSED,
                "reason": "a DMA channel cannot be modelled without VRAM/GPU transfer state, which the boundary does not model; accepting the write would invent transfer behaviour",
            },
            {
                "interaction": "memory-control delay configuration",
                "evidence": "two denied 32-bit writes at 0x1f801020",
                "required": False,
                "implemented": False,
                "disposition": DISPOSITION_FAIL_CLOSED,
                "reason": "delay registers affect timing only; there is no timing model in which accepting them would mean anything",
            },
            {
                "interaction": "low-address write",
                "evidence": "one denied byte write at 0x00000000",
                "required": False,
                "implemented": False,
                "disposition": DISPOSITION_FAIL_CLOSED,
            },
            {
                "interaction": "corrupted pointer read",
                "evidence": "one denied read of 0x14802000, which is the GPU status stub value used as an address",
                "required": False,
                "implemented": False,
                "disposition": "SYMPTOM_OF_THE_CONTROL_FLOW_FAILURE",
            },
        ],
        "policy": (
            "nothing is implemented at P10-08: the observed interrupt/DMA/memory-control "
            "interactions are not proven required for progress, and implementing them without "
            "VRAM/transfer/timing state would invent device behaviour"
        ),
    }
