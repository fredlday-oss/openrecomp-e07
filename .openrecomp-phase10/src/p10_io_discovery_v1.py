#!/usr/bin/env python3
"""OpenRecomp Phase-10 dynamic PS1 I/O discovery V1.

Two independent, evidence-bounded sources are combined:

* **dynamic**: the deterministic observable record of the `P10-05` native
  Hercules run (typed platform event counts per device, denied accesses, the
  host-service call count and the access budget state). The event categories
  come from the Phase-9 typed port boundary that the runtime implements;
* **static**: a constant-base scan over the reachable neutral program. Each
  reachable memory access whose base register resolves to a constant through
  the bounded slice is classified against the audited Phase-9 port ranges;
  accesses with an unresolved base stay in an explicit residual class.

Only the audited Phase-9 ranges are used, so the classification never invents a
device map. Addresses outside the audited window (the denied accesses) are
recorded as an explicit unresolved class because the frozen Phase-9 driver does
not expose the denied address.
"""

from __future__ import annotations

from typing import Any

import p9_cdrom_boundary_v1 as cdrom
import p9_gpu_boundary_v1 as gpu
import p9_input_timer_v1 as input_timer
import p9_io_discovery_v1 as io
import p9_spu_boundary_v1 as spu
import p10_bios_boundary_v1 as slice_resolver

IO_VERSION = "1.0.0"

#: The audited Phase-9 platform port ranges, reused unchanged.
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

#: Memory-access op types that can touch a device register.
ACCESS_OPS = (
    "lw", "lb", "lbu", "lh", "lhu", "lwl", "lwr",
    "sw", "sb", "sh", "swl", "swr",
)

CLASS_AUDITED_DEVICE = "AUDITED_DEVICE_RANGE"
CLASS_UNRESOLVED_BASE = "UNRESOLVED_BASE"
CLASS_OUTSIDE_AUDITED = "OUTSIDE_AUDITED_RANGES"

DYNAMIC_CLASSES = ("gpu", "input", "spu", "cdrom")


def classify_address(address: int) -> str | None:
    for entry in AUDITED_RANGES:
        if entry.base <= address < entry.base + entry.size:
            return entry.name
    return None


def _signed16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def discover_constant_accesses(analysis: dict[str, Any]) -> dict[str, Any]:
    """Classify reachable memory accesses whose base register is a constant."""
    records = analysis.get("records") or []
    reachable = set(analysis.get("reachable_addresses") or [])
    by_address = {record["address"]: record for record in records}
    sites: list[dict[str, Any]] = []
    for address in sorted(reachable):
        record = by_address[address]
        if record.get("op") not in ACCESS_OPS:
            continue
        operands = record.get("operands") or {}
        base = operands.get("rs")
        imm = operands.get("imm")
        if not isinstance(base, int) or not isinstance(imm, int):
            sites.append({"site": address, "op": record["op"], "classification": CLASS_UNRESOLVED_BASE})
            continue
        value, evidence = slice_resolver.resolve_constant(analysis, address, base)
        if value is None:
            sites.append(
                {
                    "site": address,
                    "op": record["op"],
                    "classification": CLASS_UNRESOLVED_BASE,
                    "evidence": list(evidence),
                }
            )
            continue
        target = (value + _signed16(imm)) & 0xFFFFFFFF
        name = classify_address(target)
        sites.append(
            {
                "site": address,
                "op": record["op"],
                "classification": CLASS_AUDITED_DEVICE if name else CLASS_OUTSIDE_AUDITED,
                "device": name,
                "address": f"0x{target:08x}",
                "evidence": list(evidence),
            }
        )
    histogram: dict[str, int] = {}
    devices: dict[str, int] = {}
    for site in sites:
        histogram[site["classification"]] = histogram.get(site["classification"], 0) + 1
        if site.get("device"):
            devices[site["device"]] = devices.get(site["device"], 0) + 1
    first_device_site = next(
        (site for site in sites if site["classification"] == CLASS_AUDITED_DEVICE), None
    )
    return {
        "io_version": IO_VERSION,
        "access_site_count": len(sites),
        "histogram": dict(sorted(histogram.items())),
        "device_histogram": dict(sorted(devices.items())),
        "first_device_site": first_device_site,
        "sites": sites,
        "audited_ranges": [
            {"name": entry.name, "base": f"0x{entry.base:08x}", "size": entry.size}
            for entry in AUDITED_RANGES
        ],
        "residual_policy": "unresolved bases and addresses outside the audited ranges stay explicit and fail closed",
    }


def classify_dynamic(native_record: dict[str, Any]) -> dict[str, Any]:
    """Classify the dynamically observed transitions of one native record."""
    execution = native_record.get("execution") or {}
    events = execution.get("events") or {}
    capped = execution.get("events_capped") or {}
    observed = []
    for name in DYNAMIC_CLASSES:
        count = int(events.get(name, 0))
        if count <= 0:
            continue
        observed.append(
            {
                "device": name,
                "event_count": count,
                "capped": bool(capped.get(name, False)),
                "required": True,
                "implemented_by": "phase9-typed-port-boundary",
            }
        )
    return {
        "io_version": IO_VERSION,
        "source": "P10-05 native observable record",
        "observed_devices": observed,
        "observed_device_count": len(observed),
        "denied_accesses": int(execution.get("denied", 0)),
        "denied_classification": CLASS_OUTSIDE_AUDITED,
        "denied_address_observable": False,
        "host_service_calls": int(execution.get("host_calls", 0)),
        "reads": int(execution.get("reads", 0)),
        "writes": int(execution.get("writes", 0)),
        "budget_reached": bool(execution.get("budget_reached", False)),
        "termination_category": execution.get("termination_category"),
        "unmodelled_device_policy": "fail-closed",
    }


def requirements(static: dict[str, Any], dynamic: dict[str, Any]) -> dict[str, Any]:
    """What the observed behaviour actually requires, and what stays unmodelled."""
    required = sorted({item["device"] for item in dynamic["observed_devices"]})
    statically_reachable = sorted(static["device_histogram"])
    return {
        "io_version": IO_VERSION,
        "dynamically_required_devices": required,
        "statically_reachable_devices": statically_reachable,
        "implemented_at_phase10": [],
        "already_implemented_by_phase9": required,
        "not_required_and_not_implemented": [
            device for device in ("dma", "memory_control", "expansion", "sio")
            if device not in required
        ],
        "policy": (
            "no device is extended at P10-06: the Phase-9 typed port boundary already "
            "serves every dynamically observed device class, and unmodelled ports or "
            "unknown commands remain fail-closed"
        ),
    }
