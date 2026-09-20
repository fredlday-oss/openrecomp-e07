#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1 BIOS/service boundary V1.

The PS1 BIOS is never loaded, executed or emulated. The boundary this module
defines is an explicit, typed, versioned host-side service contract:

* a closed service table with stable ids, names, arities, categories and an
  explicit implemented/unimplemented flag;
* explicit BIOS jump-table vectors (A0/B0/C0) and a bounded, evidence-based
  discovery of reachable indirect call sites that *candidate* for BIOS table
  calls (immediate vector loaded into the call register immediately before the
  call), versus sites whose target comes from memory or a computation
  (explicitly unresolved, never guessed);
* unknown service ids and unimplemented BIOS services fail closed.

No BIOS image, BIOS code, firmware, key or console-derived material is used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BOUNDARY_VERSION = "1.0.0"

BIOS_TABLE_VECTORS = {"A0": 0xA0, "B0": 0xB0, "C0": 0xC0}

SCAN_WINDOW = 8

SITE_CLASSES = (
    "BIOS_TABLE_CALL_CANDIDATE",
    "INDIRECT_TARGET_IMMEDIATE_NOT_BIOS",
    "INDIRECT_TARGET_FROM_MEMORY_UNRESOLVED",
    "INDIRECT_TARGET_COMPUTED_UNRESOLVED",
    "INDIRECT_TARGET_UNKNOWN",
)

#: Immediate-loading ops that can define a call register.
_IMMEDIATE_OPS = ("addiu", "ori", "andi", "xori", "slti", "sltiu")
_MEMORY_OPS = ("lw", "lb", "lbu", "lh", "lhu", "lwl", "lwr")
_CONTROL_TERMINATORS = frozenset(
    {"conditional-branch", "jump", "direct-call", "return", "indirect-call", "indirect-jump", "external-trap"}
)


class ServiceBoundaryError(ValueError):
    """Fail-closed service boundary rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class HostService:
    service_id: str
    name: str
    arity: int
    category: str
    implemented: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "name": self.name,
            "arity": self.arity,
            "category": self.category,
            "implemented": self.implemented,
        }


@dataclass
class ServiceBoundary:
    """Typed, versioned host-service boundary (no BIOS image)."""

    services: tuple[HostService, ...] = ()
    bios_image: str = "none"
    unknown_service_policy: str = "fail-closed"

    def resolve(self, service_id: str) -> HostService:
        for service in self.services:
            if service.service_id == service_id:
                return service
        raise ServiceBoundaryError("UNKNOWN_SERVICE", service_id)

    def invoke(self, service_id: str, args: tuple[int, ...]) -> int:
        service = self.resolve(service_id)
        if not service.implemented:
            raise ServiceBoundaryError("UNIMPLEMENTED_SERVICE", service_id)
        raise ServiceBoundaryError("UNIMPLEMENTED_SERVICE", service_id)

    def as_dict(self) -> dict[str, Any]:
        return {
            "boundary_version": BOUNDARY_VERSION,
            "bios_image": self.bios_image,
            "unknown_service_policy": self.unknown_service_policy,
            "services": [service.as_dict() for service in self.services],
            "vectors": {name: f"0x{value:02x}" for name, value in sorted(BIOS_TABLE_VECTORS.items())},
        }


#: Recognized BIOS jump-table vectors, declared explicitly unimplemented.
BIOS_SERVICES = (
    HostService("bios-A0", "BIOS A0 jump-table vector", 0, "bios", False),
    HostService("bios-B0", "BIOS B0 jump-table vector", 0, "bios", False),
    HostService("bios-C0", "BIOS C0 jump-table vector", 0, "bios", False),
)


def default_boundary() -> ServiceBoundary:
    """The bounded Phase-9 boundary: BIOS vectors recognized, none implemented."""
    return ServiceBoundary(services=BIOS_SERVICES)


def _write_target(record: dict[str, Any]) -> int | None:
    """The destination register a record writes, if any (bounded set)."""
    op = record.get("op")
    operands = record.get("operands") or {}
    if op in _IMMEDIATE_OPS or op in _MEMORY_OPS or op == "lui":
        return operands.get("rt")
    if op in ("addu", "subu", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu", "movz"):
        return operands.get("rd")
    return None


def _immediate_value(record: dict[str, Any]) -> int | None:
    op = record.get("op")
    operands = record.get("operands") or {}
    if op == "lui":
        value = operands.get("imm")
        return None if value is None else (value & 0xFFFF) << 16
    if op in _IMMEDIATE_OPS:
        value = operands.get("imm")
        return None if value is None else value & 0xFFFF
    return None


def classify_call_site(records: dict[int, dict[str, Any]], site: dict[str, Any]) -> dict[str, Any]:
    """Bounded backward classification of one indirect call site."""
    address = site["address"]
    operands = site.get("operands") or {}
    source = operands.get("rs")
    if source is None:
        return {"site": address, "class": "INDIRECT_TARGET_UNKNOWN", "source_register": None}

    window: list[dict[str, Any]] = []
    for step in range(1, SCAN_WINDOW + 1):
        candidate = records.get(address - 4 * step)
        if candidate is None:
            break
        if candidate.get("control_flow") and candidate.get("terminator") in _CONTROL_TERMINATORS:
            break
        window.append(candidate)
        if _write_target(candidate) == source:
            break

    if not window:
        return {"site": address, "class": "INDIRECT_TARGET_UNKNOWN", "source_register": source}

    defining = window[0]
    if _write_target(defining) != source:
        return {"site": address, "class": "INDIRECT_TARGET_UNKNOWN", "source_register": source}

    op = defining.get("op")
    if op == "lui":
        # A lui may pair with a following ori/addiu to the same register.
        value = _immediate_value(defining) or 0
        for record in window[1:]:
            if _write_target(record) == source and record.get("op") in _IMMEDIATE_OPS:
                value |= _immediate_value(record) or 0
                break
            if _write_target(record) == source:
                break
        return _classify_value(address, source, value, defining)
    if op in _IMMEDIATE_OPS:
        value = _immediate_value(defining)
        if value is None:
            return {"site": address, "class": "INDIRECT_TARGET_COMPUTED_UNRESOLVED", "source_register": source}
        return _classify_value(address, source, value, defining)
    if op in _MEMORY_OPS:
        return {
            "site": address,
            "class": "INDIRECT_TARGET_FROM_MEMORY_UNRESOLVED",
            "source_register": source,
            "defining_op": op,
        }
    return {
        "site": address,
        "class": "INDIRECT_TARGET_COMPUTED_UNRESOLVED",
        "source_register": source,
        "defining_op": op,
    }


def _classify_value(address: int, source: int, value: int, defining: dict[str, Any]) -> dict[str, Any]:
    for name, vector in sorted(BIOS_TABLE_VECTORS.items()):
        if value == vector:
            return {
                "site": address,
                "class": "BIOS_TABLE_CALL_CANDIDATE",
                "source_register": source,
                "vector": name,
                "immediate": f"0x{value:02x}",
                "defining_op": defining.get("op"),
                "defining_address": f"0x{defining['address']:08x}",
            }
    return {
        "site": address,
        "class": "INDIRECT_TARGET_IMMEDIATE_NOT_BIOS",
        "source_register": source,
        "immediate": f"0x{value:08x}",
        "defining_op": defining.get("op"),
    }


def discover(analysis: dict[str, Any]) -> dict[str, Any]:
    """Discover and classify reachable indirect call sites for the BIOS boundary."""
    records = {record["address"]: record for record in analysis["records"]}
    sites = [
        record
        for record in analysis["records"]
        if record["reachability"] == "REACHABLE"
        and record.get("op") == "jalr"
        and record.get("terminator") == "indirect-call"
    ]
    classified = [classify_call_site(records, site) for site in sites]
    histogram: dict[str, int] = {}
    for item in classified:
        histogram[item["class"]] = histogram.get(item["class"], 0) + 1
    candidates = [item for item in classified if item["class"] == "BIOS_TABLE_CALL_CANDIDATE"]
    return {
        "boundary_version": BOUNDARY_VERSION,
        "sites": sorted(classified, key=lambda item: item["site"]),
        "site_count": len(classified),
        "histogram": dict(sorted(histogram.items())),
        "bios_candidates": sorted(candidates, key=lambda item: item["site"]),
        "bios_candidate_count": len(candidates),
    }
