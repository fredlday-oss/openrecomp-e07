#!/usr/bin/env python3
"""OpenRecomp Phase-8 neutral structure bridge for the real MIPS32 ELF.

This module bridges the frozen Phase-3 frontier records of the P8-01 fixture
to the existing shared, architecture-neutral layers:

    ProgramModel -> CFG -> function discovery -> call graph -> translation units

It is additive and P8-specific; no shared or frozen layer is modified.

Delay slots
-----------

The shared neutral model has no delay-slot concept.  Phase 8 models a MIPS32
control transfer exactly by *folding* its delay-slot instruction into the
control instruction:

* the delay-slot record is removed from the neutral instruction stream;
* the control instruction's ``size_bytes`` becomes 8 (control + delay slot),
  so the shared continuation logic lands on ``address + 8``;
* the delay-slot instruction's decode fields are attached to the control
  instruction's metadata under ``delay_slot`` so an explicit emitter contract
  can execute it before the transfer.

This preserves MIPS32 semantics because the delay slot always executes (taken
and not-taken paths) before the transfer, and the branch condition is
evaluated before the delay slot in both paths.  The bridge fails closed if a
delay slot is missing, is itself a control transfer, is the target of another
transfer, or if a direct target is not a neutral instruction.

Indirect control flow
---------------------

``jr $ra`` is a structural return only when the frozen record marks the
terminator as ``return``; every other indirect control transfer becomes an
explicit unresolved ``INDIRECT_JUMP``/``INDIRECT_CALL`` with no invented
target.  No target is ever fabricated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

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

CONTINUATION_TRAPS = frozenset({"syscall", "break"})
CONTROL_TERMINATORS = frozenset(
    {
        "conditional-branch",
        "jump",
        "direct-call",
        "return",
        "indirect-call",
        "indirect-jump",
        "unsupported-control",
        "external-trap",
    }
)


class P8StructureError(ValueError):
    """Fail-closed structure bridge error with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass
class P8StructureResult:
    """Neutral structure derived from the frozen frontier."""

    cfg: Any
    discovery: Any
    call_graph: Any
    units: Any
    classification: Any
    folded_delay_slots: dict[int, dict[str, Any]] = field(default_factory=dict)
    neutral_addresses: tuple[int, ...] = ()
    dropped_delay_addresses: tuple[int, ...] = ()

    def to_program_model(self) -> Any:
        return self.discovery.to_program_model()


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise P8StructureError(code, detail)


def _is_control(record: dict[str, Any]) -> bool:
    return bool(record.get("control_flow"))


def _flow_for_record(record: dict[str, Any]) -> tuple[InstructionFlow, int | None, bool]:
    """Map one reachable frontier record to neutral flow facts (fail closed)."""
    address = record.get("address")
    if not isinstance(address, int) or address < 0 or address & 3:
        raise P8StructureError("INVALID_RECORD_ADDRESS", f"{address!r}")

    control_flow = record.get("control_flow")
    terminator = record.get("terminator")
    operands = record.get("operands") or {}
    target = record.get("target")

    if not control_flow:
        if terminator is not None:
            raise P8StructureError("INCONSISTENT_TERMINATOR", f"0x{address:08x} {terminator!r}")
        if record.get("delay_slot"):
            raise P8StructureError("INCONSISTENT_DELAY_SLOT", f"0x{address:08x}")
        if record.get("exception_transfer") and record.get("op") not in CONTINUATION_TRAPS:
            raise P8StructureError("UNKNOWN_EXCEPTION_TRANSFER", f"0x{address:08x}")
        if target is not None:
            raise P8StructureError("INCONSISTENT_TARGET", f"0x{address:08x}")
        return InstructionFlow.NORMAL, None, False

    if terminator not in CONTROL_TERMINATORS:
        raise P8StructureError("UNKNOWN_TERMINATOR", f"0x{address:08x} {terminator!r}")
    if terminator in ("unsupported-control", "external-trap"):
        raise P8StructureError("UNSUPPORTED_CONTROL_TRANSFER", f"0x{address:08x} {record.get('op')!r}")

    if terminator == "conditional-branch":
        _require(isinstance(target, int) and not target & 3, "MISSING_BRANCH_TARGET", f"0x{address:08x}")
        return InstructionFlow.BRANCH, target, False
    if terminator == "jump":
        _require(isinstance(target, int) and not target & 3, "MISSING_JUMP_TARGET", f"0x{address:08x}")
        return InstructionFlow.JUMP, target, False
    if terminator == "direct-call":
        _require(isinstance(target, int) and not target & 3, "MISSING_CALL_TARGET", f"0x{address:08x}")
        return InstructionFlow.CALL, target, False
    if terminator == "return":
        _require(target is None, "RETURN_WITH_TARGET", f"0x{address:08x}")
        _require(
            record.get("op") == "jr" and operands.get("rs") == 31,
            "RETURN_NOT_RA",
            f"0x{address:08x} {record.get('op')!r} {operands}",
        )
        return InstructionFlow.RETURN, None, False
    if terminator == "indirect-call":
        _require(target is None, "INDIRECT_CALL_WITH_TARGET", f"0x{address:08x}")
        return InstructionFlow.INDIRECT_CALL, None, True
    if terminator == "indirect-jump":
        _require(target is None, "INDIRECT_JUMP_WITH_TARGET", f"0x{address:08x}")
        return InstructionFlow.INDIRECT_JUMP, None, True
    raise P8StructureError("UNREACHABLE_TERMINATOR", f"0x{address:08x} {terminator!r}")


def _adapter_fields(record: dict[str, Any]) -> dict[str, Any]:
    operands = record.get("operands")
    if not isinstance(operands, dict):
        raise P8StructureError("MISSING_OPERANDS", f"0x{record['address']:08x}")
    fields = dict(operands)
    fields["address"] = record["address"]
    fields["op"] = record["op"]
    return fields


def _neutral_instruction(record: dict[str, Any], delay_slot: dict[str, Any] | None) -> Any:
    flow, direct_target, unresolved = _flow_for_record(record)
    fields = _adapter_fields(record)
    metadata: dict[str, Any] = {
        "word": record["word"],
        "decode_class": record["decode_class"],
        "operands": dict(record.get("operands") or {}),
        "exception_transfer": bool(record.get("exception_transfer")),
        "adapter_fields": fields,
        "delay_slot": delay_slot,
    }
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


def analyze_structure(analysis: dict[str, Any], *, source: ProgramSource, entry: int) -> P8StructureResult:
    """Build the neutral structure for one frozen frontier analysis."""
    if not isinstance(analysis, dict):
        raise P8StructureError("INVALID_ANALYSIS", type(analysis).__name__)
    records = analysis.get("records")
    reachable = analysis.get("reachable_addresses")
    if not isinstance(records, list) or not records:
        raise P8StructureError("INVALID_ANALYSIS", "records")
    if not isinstance(reachable, (list, tuple)) or not reachable:
        raise P8StructureError("INVALID_ANALYSIS", "reachable_addresses")

    by_address: dict[int, dict[str, Any]] = {}
    for record in records:
        address = record.get("address")
        if not isinstance(address, int):
            raise P8StructureError("INVALID_RECORD", f"{address!r}")
        if address in by_address:
            raise P8StructureError("DUPLICATE_RECORD", f"0x{address:08x}")
        by_address[address] = record

    reachable_set = set()
    for address in reachable:
        if not isinstance(address, int) or address not in by_address:
            raise P8StructureError("INVALID_REACHABLE", f"{address!r}")
        reachable_set.add(address)

    # Delay-slot map, validated fail closed.
    delay_by_owner: dict[int, int] = {}
    for item in analysis.get("delay_slots", []):
        owner = item.get("owner")
        delay = item.get("delay")
        if not isinstance(owner, int) or not isinstance(delay, int):
            raise P8StructureError("INVALID_DELAY_SLOT", f"{item!r}")
        if owner in delay_by_owner:
            raise P8StructureError("DUPLICATE_DELAY_SLOT", f"0x{owner:08x}")
        delay_by_owner[owner] = delay
    for owner, delay in sorted(delay_by_owner.items()):
        _require(delay == owner + 4, "DELAY_SLOT_NOT_ADJACENT", f"0x{owner:08x}->0x{delay:08x}")
        _require(owner in reachable_set, "DELAY_OWNER_UNREACHABLE", f"0x{owner:08x}")
        _require(delay in reachable_set, "DELAY_SLOT_UNREACHABLE", f"0x{delay:08x}")
        owner_record = by_address[owner]
        delay_record = by_address[delay]
        _require(_is_control(owner_record), "DELAY_OWNER_NOT_CONTROL", f"0x{owner:08x}")
        _require(owner_record.get("delay_slot") is True, "MISSING_DELAY_SLOT_FLAG", f"0x{owner:08x}")
        _require(not _is_control(delay_record), "DELAY_SLOT_IS_CONTROL", f"0x{delay:08x}")
        _require(not delay_record.get("exception_transfer"), "DELAY_SLOT_IS_TRAP", f"0x{delay:08x}")
    for owner, delay in sorted(delay_by_owner.items()):
        for other in reachable_set:
            other_record = by_address[other]
            target = other_record.get("target")
            if target == delay:
                raise P8StructureError("TARGET_INTO_DELAY_SLOT", f"0x{other:08x}->0x{delay:08x}")

    folded: dict[int, dict[str, Any]] = {}
    instructions: list[Any] = []
    for address in sorted(reachable_set):
        record = by_address[address]
        if address in set(delay_by_owner.values()):
            continue
        if _is_control(record):
            if record.get("delay_slot") is not True:
                raise P8StructureError("CONTROL_WITHOUT_DELAY_SLOT", f"0x{address:08x}")
            delay = delay_by_owner.get(address)
            if delay is None:
                raise P8StructureError("CONTROL_DELAY_SLOT_UNKNOWN", f"0x{address:08x}")
            delay_record = by_address[delay]
            delay_fields = _adapter_fields(delay_record)
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
        raise P8StructureError("EMPTY_STREAM", "no neutral instructions")

    cfg = build_cfg(stream, source=source, entries=[EntryPoint(entry, PROVEN)], mode=CFGMode.CLOSED)
    discovery = discover_functions(cfg, program_entries=[entry], include_direct_call_targets=True)
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)
    classification = classify_indirect_control_flow(units, evidence=[])

    return P8StructureResult(
        cfg=cfg,
        discovery=discovery,
        call_graph=call_graph,
        units=units,
        classification=classification,
        folded_delay_slots=folded,
        neutral_addresses=tuple(instruction.address for instruction in stream),
        dropped_delay_addresses=tuple(sorted(set(delay_by_owner.values()))),
    )


def structure_summary(result: P8StructureResult) -> dict[str, Any]:
    """Deterministic summary of the derived neutral structure."""
    edge_histogram: dict[str, int] = {}
    for block in result.cfg.blocks:
        for successor in block.successors:
            edge_histogram[successor.kind.value] = edge_histogram.get(successor.kind.value, 0) + 1
    flow_histogram: dict[str, int] = {}
    for instruction in result.cfg.instructions:
        flow_histogram[instruction.flow.value] = flow_histogram.get(instruction.flow.value, 0) + 1
    unresolved = [
        {
            "function_id": item.function_id,
            "block_id": item.block_id,
            "address": item.address,
            "op": item.op,
            "kind": item.kind.value,
            "status": item.status.value,
            "target": None if not item.targets else list(item.targets),
        }
        for item in result.classification.classifications()
        if item.status.value.startswith("UNRESOLVED")
    ]
    return {
        "structure_version": STRUCTURE_VERSION,
        "neutral_instructions": len(result.cfg.instructions),
        "folded_delay_slots": len(result.folded_delay_slots),
        "non_nop_delay_slots": sum(1 for item in result.folded_delay_slots.values() if item["non_nop"]),
        "blocks": len(result.cfg.blocks),
        "edges": sum(edge_histogram.values()),
        "edge_histogram": dict(sorted(edge_histogram.items())),
        "flow_histogram": dict(sorted(flow_histogram.items())),
        "functions": len(result.discovery.functions),
        "shared_blocks": len(result.discovery.shared_blocks),
        "unowned_blocks": len(result.discovery.unowned_blocks),
        "call_edges_internal": len(result.call_graph.internal_edges()),
        "call_edges_external": len(result.call_graph.external_edges()),
        "call_edges_unresolved": len(result.call_graph.unresolved_edges()),
        "translation_units": len(result.units.units),
        "entry_unit": result.units.entry_unit,
        "entry_function": result.discovery.entry_function_id,
        "program_model_fingerprint": result.discovery.to_program_model().fingerprint(),
        "cfg_fingerprint": result.cfg.fingerprint(),
        "call_graph_fingerprint": result.call_graph.fingerprint(),
        "units_fingerprint": result.units.fingerprint(),
        "discovery_fingerprint": result.discovery.fingerprint(),
        "classification_units": len(result.classification.units),
        "unresolved_sites": unresolved,
    }


def structure_digest(summary: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(summary, sort_keys=True).encode("utf-8")).hexdigest()
