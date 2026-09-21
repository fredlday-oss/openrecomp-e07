#!/usr/bin/env python3
"""OpenRecomp Phase-10 exception-aware structure bridge V1.

The frozen Phase-8 neutral-structure bridge fails closed with
``CONTROL_WITHOUT_DELAY_SLOT`` for every record that the frozen Phase-3
frontier marks with ``control_flow`` true but no delay slot. The Phase-3
decoder marks ``break`` and ``syscall`` that way because they are
exception-raising instructions, not delay-slot control transfers.

This bridge keeps the frozen Phase-8 module untouched and reuses it for
everything it already models:

* the same frozen delay-slot validation and folding helpers;
* the same shared, architecture-neutral ``ProgramModel`` -> ``CFG`` ->
  ``discover_functions`` -> ``build_call_graph`` -> ``build_translation_units``
  -> ``classify_indirect_control_flow`` layers, in the same closed mode.

It adds exactly one thing: an ``external-trap`` record is mapped to the shared
neutral ``InstructionFlow.TRAP`` with no successor, no delay slot and no
fabricated fall-through, and is validated against the Phase-10 exception
classification first (so a malformed or in-delay-slot trap still fails closed).

No delay slot is ever manufactured. A non-trap control record without a delay
slot still fails closed with ``CONTROL_WITHOUT_DELAY_SLOT``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import p8_structure_v1 as p8
import p10_exception_v1 as exception
from openrecomp.call_graph import build_call_graph
from openrecomp.cfg import CFGMode, EntryPoint, build_cfg
from openrecomp.functions import discover_functions
from openrecomp.indirect_control_flow import classify_indirect_control_flow
from openrecomp.program_model import (
    EvidenceClass,
    InstructionFlow,
    ProgramSource,
    instruction_from_adapter,
)
from openrecomp.translation_units import build_translation_units

STRUCTURE_VERSION = "1.0.0"

PROVEN = EvidenceClass.PROVEN

#: Neutral op name for the frozen frontier's ``indirect-jump`` classification
#: of a ``jr`` whose source register is not ``$ra``. The frozen Phase-3
#: decoder already distinguishes a structural return (``jr $ra``) from an
#: indirect jump; the neutral host-emitter contract allows exactly one flow per
#: ``(architecture, op)`` pair, so the two distinct classifications carry
#: distinct neutral op names with distinct explicit rules. No target is
#: invented and nothing is reclassified as code.
JR_INDIRECT_OP = "jr_indirect"


@dataclass
class P10StructureResult:
    """Neutral structure derived from one frozen frontier analysis."""

    cfg: Any
    discovery: Any
    call_graph: Any
    units: Any
    classification: Any
    folded_delay_slots: dict[int, dict[str, Any]] = field(default_factory=dict)
    neutral_addresses: tuple[int, ...] = ()
    dropped_delay_addresses: tuple[int, ...] = ()
    trap_sites: tuple[dict[str, Any], ...] = ()

    def to_program_model(self) -> Any:
        return self.discovery.to_program_model()

    def trap_addresses(self) -> tuple[int, ...]:
        return tuple(site["site"] for site in self.trap_sites)


def _classify_trap(record: dict[str, Any]) -> dict[str, Any]:
    """Classify one trap record, surfacing failures as structure errors."""
    try:
        return exception.classify_trap_site(record)
    except exception.TrapClassificationError as exc:
        raise p8.P8StructureError(exc.code, exc.detail) from exc


def _exception_flow(record: dict[str, Any]) -> tuple[InstructionFlow, int | None, bool]:
    """Trap-aware flow mapping: fall back to the frozen Phase-8 mapping."""
    if record.get("terminator") == exception.TERMINATOR_EXTERNAL_TRAP:
        classification = _classify_trap(record)
        if classification["delay_slot"] or classification["successors"]:
            raise p8.P8StructureError("TRAP_MUST_BE_TERMINAL", f"0x{record['address']:08x}")
        return InstructionFlow.TRAP, None, False
    return p8._flow_for_record(record)


def _adapter_fields(record: dict[str, Any]) -> dict[str, Any]:
    """The Phase-8 adapter fields with the explicit indirect-jump rename."""
    fields = p8._adapter_fields(record)
    if record.get("op") == "jr" and record.get("terminator") == "indirect-jump":
        fields["op"] = JR_INDIRECT_OP
    return fields


def _neutral_instruction(record: dict[str, Any], delay_slot: dict[str, Any] | None) -> Any:
    flow, direct_target, unresolved = _exception_flow(record)
    fields = _adapter_fields(record)
    metadata: dict[str, Any] = {
        "word": record["word"],
        "decode_class": record["decode_class"],
        "operands": dict(record.get("operands") or {}),
        "exception_transfer": bool(record.get("exception_transfer")),
        "adapter_fields": fields,
        "delay_slot": delay_slot,
    }
    if flow is InstructionFlow.TRAP:
        metadata["exception"] = _classify_trap(record)
    size_bytes = 8 if delay_slot is not None else 4
    return instruction_from_adapter(
        fields,
        flow=flow,
        unresolved=unresolved,
        direct_target=direct_target,
        size_bytes=size_bytes,
        evidence=PROVEN,
        metadata=metadata,
    )


def analyze_structure(
    analysis: dict[str, Any], *, source: ProgramSource, entry: int
) -> P10StructureResult:
    """Build the neutral structure for one frozen frontier analysis."""
    if not isinstance(analysis, dict):
        raise p8.P8StructureError("INVALID_ANALYSIS", type(analysis).__name__)
    records = analysis.get("records")
    reachable = analysis.get("reachable_addresses")
    if not isinstance(records, list) or not records:
        raise p8.P8StructureError("INVALID_ANALYSIS", "records")
    if not isinstance(reachable, (list, tuple)) or not reachable:
        raise p8.P8StructureError("INVALID_ANALYSIS", "reachable_addresses")

    by_address: dict[int, dict[str, Any]] = {}
    for record in records:
        address = record.get("address")
        if not isinstance(address, int):
            raise p8.P8StructureError("INVALID_RECORD", f"{address!r}")
        if address in by_address:
            raise p8.P8StructureError("DUPLICATE_RECORD", f"0x{address:08x}")
        by_address[address] = record

    reachable_set: set[int] = set()
    for address in reachable:
        if not isinstance(address, int) or address not in by_address:
            raise p8.P8StructureError("INVALID_REACHABLE", f"{address!r}")
        reachable_set.add(address)

    delay_by_owner: dict[int, int] = {}
    for item in analysis.get("delay_slots", []):
        owner = item.get("owner")
        delay = item.get("delay")
        if not isinstance(owner, int) or not isinstance(delay, int):
            raise p8.P8StructureError("INVALID_DELAY_SLOT", f"{item!r}")
        if owner in delay_by_owner:
            raise p8.P8StructureError("DUPLICATE_DELAY_SLOT", f"0x{owner:08x}")
        delay_by_owner[owner] = delay
    for owner, delay in sorted(delay_by_owner.items()):
        p8._require(delay == owner + 4, "DELAY_SLOT_NOT_ADJACENT", f"0x{owner:08x}->0x{delay:08x}")
        p8._require(owner in reachable_set, "DELAY_OWNER_UNREACHABLE", f"0x{owner:08x}")
        p8._require(delay in reachable_set, "DELAY_SLOT_UNREACHABLE", f"0x{delay:08x}")
        owner_record = by_address[owner]
        delay_record = by_address[delay]
        p8._require(p8._is_control(owner_record), "DELAY_OWNER_NOT_CONTROL", f"0x{owner:08x}")
        p8._require(owner_record.get("delay_slot") is True, "MISSING_DELAY_SLOT_FLAG", f"0x{owner:08x}")
        p8._require(not p8._is_control(delay_record), "DELAY_SLOT_IS_CONTROL", f"0x{delay:08x}")
        p8._require(not delay_record.get("exception_transfer"), "DELAY_SLOT_IS_TRAP", f"0x{delay:08x}")
    for owner, delay in sorted(delay_by_owner.items()):
        for other in reachable_set:
            other_record = by_address[other]
            target = other_record.get("target")
            if target == delay:
                raise p8.P8StructureError("TARGET_INTO_DELAY_SLOT", f"0x{other:08x}->0x{delay:08x}")

    folded: dict[int, dict[str, Any]] = {}
    instructions: list[Any] = []
    trapped: list[dict[str, Any]] = []
    delay_slot_values = set(delay_by_owner.values())
    for address in sorted(reachable_set):
        record = by_address[address]
        if address in delay_slot_values:
            continue
        if p8._is_control(record):
            delay = delay_by_owner.get(address)
            if record.get("terminator") == exception.TERMINATOR_EXTERNAL_TRAP:
                if delay is not None:
                    raise p8.P8StructureError("TRAP_WITH_DELAY_SLOT", f"0x{address:08x}")
                classification = _classify_trap(record)
                trapped.append(classification)
                instructions.append(_neutral_instruction(record, None))
                continue
            if record.get("delay_slot") is not True:
                raise p8.P8StructureError("CONTROL_WITHOUT_DELAY_SLOT", f"0x{address:08x}")
            if delay is None:
                raise p8.P8StructureError("CONTROL_DELAY_SLOT_UNKNOWN", f"0x{address:08x}")
            delay_record = by_address[delay]
            delay_fields = p8._adapter_fields(delay_record)
            folded[address] = {
                "address": delay,
                "op": delay_record["op"],
                "word": delay_record["word"],
                "adapter_fields": delay_fields,
                "operands": dict(delay_record.get("operands") or {}),
                "non_nop": delay_record["word"] != 0,
            }
            instructions.append(_neutral_instruction(record, folded[address]))
        else:
            instructions.append(_neutral_instruction(record, None))

    stream = tuple(instructions)
    if not stream:
        raise p8.P8StructureError("EMPTY_STREAM", "no neutral instructions")

    cfg = build_cfg(stream, source=source, entries=[EntryPoint(entry, PROVEN)], mode=CFGMode.CLOSED)
    discovery = discover_functions(cfg, program_entries=[entry], include_direct_call_targets=True)
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)
    classification = classify_indirect_control_flow(units, evidence=[])

    trapped.sort(key=lambda item: item["site"])
    return P10StructureResult(
        cfg=cfg,
        discovery=discovery,
        call_graph=call_graph,
        units=units,
        classification=classification,
        folded_delay_slots=folded,
        neutral_addresses=tuple(instruction.address for instruction in stream),
        dropped_delay_addresses=tuple(sorted(delay_slot_values)),
        trap_sites=tuple(trapped),
    )


def structure_summary(result: P10StructureResult) -> dict[str, Any]:
    """The frozen Phase-8 summary extended with the trap record."""
    summary = p8.structure_summary(result)
    summary["structure_version"] = STRUCTURE_VERSION
    summary["exception_sites"] = [
        {
            "site": site["site"],
            "site_hex": site["site_hex"],
            "op": site["op"],
            "code": site["code"],
            "exception_code": site["exception_code"],
            "exception_name": site["exception_name"],
            "epc": site["epc"],
            "bd": site["bd"],
            "successors": list(site["successors"]),
            "continuation": site["continuation"],
            "handling": site["handling"],
            "runtime_category": site["runtime_category"],
        }
        for site in result.trap_sites
    ]
    summary["exception_site_count"] = len(result.trap_sites)
    return summary


def structure_digest(summary: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(summary, sort_keys=True).encode("utf-8")).hexdigest()
