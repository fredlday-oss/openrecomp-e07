#!/usr/bin/env python3
"""OpenRecomp Phase-10 Hercules BIOS/service frontier V1.

The Phase-9 typed BIOS/service boundary is reused unchanged
(``p9_bios_boundary_v1``): no BIOS image, no BIOS-derived code and no emulated
BIOS behaviour.

This module adds exact, evidence-bounded classification of the reachable
indirect-call sites using only the frozen frontier records:

* a bounded backwards slice resolves an indirect-call target register to a
  constant when the immediately preceding reachable writes are a single
  ``lui``/``addiu``/``ori`` (or the ``lui`` + ``addiu``/``ori`` pair) with no
  intervening write, load, or control-flow boundary;
* a resolved constant that equals a BIOS vector base (``0xA0``/``0xB0``/
  ``0xC0`` or their KSEG0 forms) is classified as a BIOS vector call, with the
  function index taken from a constant write to ``$t1`` in the call's delay
  slot when present;
* a resolved constant that is a known internal function entry is classified as
  an exactly resolved internal call (usable as explicit indirect-control-flow
  evidence);
* any other resolved constant and every unresolved register is kept explicit
  and fail-closed; no target is ever guessed.

BIOS function indices are recorded as *identifiers only*. Their semantics are
NOT determined here: every BIOS service stays ``implemented: false`` and
``fail-closed`` until direct evidence exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import p9_bios_boundary_v1 as p9_bios

BIOS_VERSION = "1.0.0"

#: BIOS vector bases in the low KUSEG window and their KSEG0 forms.
VECTOR_BASES = {
    "A0": (0x000000A0, 0x800000A0),
    "B0": (0x000000B0, 0x800000B0),
    "C0": (0x000000C0, 0x800000C0),
}

#: The register carrying the BIOS function index in the observed convention.
INDEX_REGISTER = 9  # $t1

#: The register carrying the BIOS vector base in the observed convention.
VECTOR_REGISTER = 10  # $t2

MAX_SLICE_DEPTH = 8

CLASS_BIOS_VECTOR_CALL = "BIOS_VECTOR_CALL"
CLASS_RESOLVED_INTERNAL_CALL = "RESOLVED_INTERNAL_CALL"
CLASS_UNRESOLVED_CONSTANT_TARGET = "UNRESOLVED_CONSTANT_TARGET"
CLASS_INDIRECT_TARGET_UNRESOLVED = "INDIRECT_TARGET_UNRESOLVED"

DISPOSITION_FAIL_CLOSED = "FAIL_CLOSED"
DISPOSITION_EXACT_TARGET = "EXACT_TARGET"


@dataclass(frozen=True)
class CallSite:
    site: int
    op: str
    source_register: int
    classification: str
    target: int | None = None
    vector: str | None = None
    function_index: int | None = None
    service_id: str | None = None
    disposition: str = DISPOSITION_FAIL_CLOSED
    evidence: tuple[str, ...] = ()

    def to_document(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "site_hex": f"0x{self.site:08x}",
            "op": self.op,
            "source_register": self.source_register,
            "classification": self.classification,
            "target": None if self.target is None else f"0x{self.target:08x}",
            "vector": self.vector,
            "function_index": self.function_index,
            "service_id": self.service_id,
            "disposition": self.disposition,
            "evidence": list(self.evidence),
        }


def _reachable_by_address(analysis: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], set[int]]:
    records = analysis.get("records") or []
    return {record["address"]: record for record in records}, set(analysis.get("reachable_addresses") or [])


def _delay_owner(analysis: dict[str, Any], address: int) -> int | None:
    for slot in analysis.get("delay_slots", []):
        if slot.get("delay") == address:
            return slot.get("owner")
    return None


def _signed16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


#: Explicit destination-field classification for the reachable op set. An op
#: outside this table stops the slice (its write set is unknown here).
_WRITE_RT = frozenset(
    {"addi", "addiu", "andi", "ori", "xori", "slti", "sltiu", "lui", "lb",
     "lbu", "lh", "lhu", "lw", "lwl", "lwr"}
)
_WRITE_RD = frozenset(
    {"addu", "subu", "and", "or", "xor", "nor", "slt", "sltu", "sll", "srl",
     "sra", "sllv", "srlv", "srav", "mfhi", "mflo", "movz", "movn"}
)
_NO_GPR_WRITE = frozenset(
    {"nop", "sw", "sb", "sh", "swl", "swr", "mult", "multu", "div", "divu",
     "break", "syscall", "j", "cache", "sync", "mthi", "mtlo", "teq"}
)


def _writes_register(record: dict[str, Any], register: int) -> bool | None:
    """True/False when the write set is known, None when it is not."""
    op = record.get("op")
    operands = record.get("operands") or {}
    if op in _WRITE_RT:
        return operands.get("rt") == register
    if op in _WRITE_RD:
        return operands.get("rd") == register
    if op == "jal":
        return register == 31
    if op == "jalr":
        return operands.get("rd") == register
    if op in _NO_GPR_WRITE:
        return False
    return None


def resolve_constant(
    analysis: dict[str, Any],
    site: int,
    register: int,
    depth: int = MAX_SLICE_DEPTH,
) -> tuple[int | None, tuple[str, ...]]:
    """Resolve a register to a constant through a bounded backwards slice."""
    by_address, reachable = _reachable_by_address(analysis)
    evidence: list[str] = []
    current = site
    remaining = depth
    while remaining > 0:
        remaining -= 1
        owner = _delay_owner(analysis, current)
        previous = owner if owner is not None else current - 4
        if previous not in reachable:
            return None, tuple(evidence) + ("slice-left-reachable-region",)
        record = by_address.get(previous)
        if record is None:
            return None, tuple(evidence) + ("slice-missing-record",)
        if record.get("control_flow") and record.get("terminator") not in ("direct-call",):
            return None, tuple(evidence) + ("slice-crossed-control-flow",)
        operands = record.get("operands") or {}
        op = record.get("op")
        writes = _writes_register(record, register)
        if writes is None:
            return None, tuple(evidence) + (f"slice-unknown-writer:{op}",)
        if not writes:
            evidence.append(f"skip@{previous:08x}")
            current = previous
            continue
        if op == "lui" and operands.get("rt") == register:
            return ((operands.get("imm") or 0) << 16) & 0xFFFFFFFF, tuple(evidence) + (f"lui@0x{previous:08x}",)
        if op in ("addiu", "ori") and operands.get("rt") == register and operands.get("rs") == 0:
            low = operands.get("imm") or 0
            if op == "addiu":
                low = _signed16(low)
            return low & 0xFFFFFFFF, tuple(evidence) + (f"{op}@0x{previous:08x}",)
        if op in ("addiu", "ori") and operands.get("rt") == register and operands.get("rs") == register:
            # Low-half update of a previously materialised constant (lui pair).
            base, base_evidence = resolve_constant(analysis, previous, register, remaining)
            if base is None:
                return None, tuple(evidence) + base_evidence + (f"low-half-base-unresolved@0x{previous:08x}",)
            low = operands.get("imm") or 0
            if op == "addiu":
                low = _signed16(low)
            return (base + low) & 0xFFFFFFFF, tuple(evidence) + base_evidence + (f"{op}@0x{previous:08x}",)
        return None, tuple(evidence) + (f"slice-writer:{op}@0x{previous:08x}",)
    return None, tuple(evidence) + ("slice-depth-exceeded",)


def delay_slot_index(analysis: dict[str, Any], site: int) -> tuple[int | None, tuple[str, ...]]:
    """The constant written to ``$t1`` in the call's delay slot, if any."""
    by_address, reachable = _reachable_by_address(analysis)
    delay = site + 4
    if delay not in reachable:
        return None, ("no-delay-slot",)
    record = by_address.get(delay) or {}
    if _delay_owner(analysis, delay) != site:
        return None, ("delay-slot-owner-mismatch",)
    operands = record.get("operands") or {}
    if record.get("op") in ("addiu", "ori") and operands.get("rt") == INDEX_REGISTER and operands.get("rs") == 0:
        value = operands.get("imm") or 0
        if record.get("op") == "addiu":
            value = _signed16(value)
        return value & 0xFFFFFFFF, (f"index-{record.get('op')}@0x{delay:08x}",)
    return None, (f"delay-slot-op:{record.get('op')}",)


def _vector_for_target(target: int) -> str | None:
    for name, (low, high) in VECTOR_BASES.items():
        if target in (low, high):
            return name
    return None


def classify_calls(
    analysis: dict[str, Any],
    *,
    function_entries: frozenset[int] = frozenset(),
) -> dict[str, Any]:
    """Classify every reachable indirect-call site deterministically."""
    by_address, reachable = _reachable_by_address(analysis)
    sites: list[CallSite] = []
    for record in sorted(by_address.values(), key=lambda item: item["address"]):
        if record.get("terminator") != "indirect-call" or record["address"] not in reachable:
            continue
        operands = record.get("operands") or {}
        source = operands.get("rs")
        target, slice_evidence = (None, ()) if not isinstance(source, int) else resolve_constant(
            analysis, record["address"], source
        )
        if target is None:
            sites.append(
                CallSite(
                    site=record["address"],
                    op=record["op"],
                    source_register=source if isinstance(source, int) else -1,
                    classification=CLASS_INDIRECT_TARGET_UNRESOLVED,
                    evidence=slice_evidence,
                )
            )
            continue
        vector = _vector_for_target(target)
        if vector is not None:
            index, index_evidence = delay_slot_index(analysis, record["address"])
            service = None if index is None else f"ps1.bios.{vector}.{index:02x}"
            sites.append(
                CallSite(
                    site=record["address"],
                    op=record["op"],
                    source_register=source,
                    classification=CLASS_BIOS_VECTOR_CALL,
                    target=target,
                    vector=vector,
                    function_index=index,
                    service_id=service,
                    disposition=DISPOSITION_FAIL_CLOSED,
                    evidence=slice_evidence + index_evidence,
                )
            )
            continue
        if target in function_entries:
            sites.append(
                CallSite(
                    site=record["address"],
                    op=record["op"],
                    source_register=source,
                    classification=CLASS_RESOLVED_INTERNAL_CALL,
                    target=target,
                    disposition=DISPOSITION_EXACT_TARGET,
                    evidence=slice_evidence,
                )
            )
            continue
        sites.append(
            CallSite(
                site=record["address"],
                op=record["op"],
                source_register=source,
                classification=CLASS_UNRESOLVED_CONSTANT_TARGET,
                target=target,
                disposition=DISPOSITION_FAIL_CLOSED,
                evidence=slice_evidence,
            )
        )

    histogram: dict[str, int] = {}
    for site in sites:
        histogram[site.classification] = histogram.get(site.classification, 0) + 1
    bios = [site for site in sites if site.classification == CLASS_BIOS_VECTOR_CALL]
    resolved = [site for site in sites if site.classification == CLASS_RESOLVED_INTERNAL_CALL]
    return {
        "bios_version": BIOS_VERSION,
        "site_count": len(sites),
        "histogram": dict(sorted(histogram.items())),
        "sites": [site.to_document() for site in sites],
        "bios_calls": [site.to_document() for site in bios],
        "bios_call_count": len(bios),
        "bios_functions": sorted(
            {site.service_id for site in bios if site.service_id is not None}
        ),
        "resolved_internal_calls": [site.to_document() for site in resolved],
        "resolved_internal_call_count": len(resolved),
        "resolved_evidence_targets": sorted({site.target for site in resolved if site.target is not None}),
        "index_register": INDEX_REGISTER,
        "vector_bases": {name: f"0x{low:08x}" for name, (low, _high) in sorted(VECTOR_BASES.items())},
        "unknown_policy": "fail-closed",
    }


def typed_boundary(call_classification: dict[str, Any]) -> dict[str, Any]:
    """The Phase-10 typed service boundary: Phase-9 vectors plus observed calls."""
    boundary = p9_bios.default_boundary().as_dict()
    services = []
    for service_id in call_classification["bios_functions"]:
        services.append(
            {
                "service_id": service_id,
                "category": "bios",
                "implemented": False,
                "disposition": DISPOSITION_FAIL_CLOSED,
                "site_count": sum(
                    1 for site in call_classification["bios_calls"]
                    if site["service_id"] == service_id
                ),
            }
        )
    boundary["bios_version"] = BIOS_VERSION
    boundary["observed_services"] = services
    boundary["observed_service_count"] = len(services)
    boundary["bios_image"] = "none"
    boundary["unknown_service_policy"] = "fail-closed"
    boundary["semantics_determined"] = False
    return boundary
