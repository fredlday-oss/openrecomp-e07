#!/usr/bin/env python3
"""OpenRecomp Phase-3 neutral program structure V1 (P3-05).

Bridges the audited MIPS32 decode/reachability frontier (P3-03) and its
reference-checked semantic overlay (P3-04) into the frozen Phase-2
architecture-neutral structure layers:

    DecodedInstruction -> BasicBlock -> FunctionUnit -> ProgramModel
    ControlFlowGraph -> FunctionDiscoveryResult -> CallGraph
    -> TranslationUnitSet

The module adds no instruction semantics and no new control flow. It only
re-packages the frozen frontier records into the shared neutral types so the
Phase-2 layers can be exercised on the real CoreMark ELF.

Classification rules (fail closed):

* only ``REACHABLE`` words of the audited frontier become neutral
  instructions; unreachable words stay an explicit structural frontier and are
  never attributed to a block or function;
* the neutral flow of an instruction is a pure function of its frozen frontier
  record -- never a re-decode and never an assumption. A control-flow record
  whose terminator/target/delay-slot shape is inconsistent with the frozen
  decode contract raises :class:`StructureError` instead of being guessed;
* indirect targets are never resolved: a reachable ``jr $at`` record maps to
  ``INDIRECT_JUMP`` with no ``direct_target``, an ``INDIRECT_CALL`` record
  (the dead ``jalr``) is never reachable in the audited frontier;
* ``div``/``divu``/``teq`` are non-control records whose fall-through
  continuation is the only audited successor; they are neutral ``NORMAL``
  instructions and stay listed in the semantic exception frontier;
* every instruction carries ``EvidenceClass.PROVEN`` only because its structure
  was established exactly: an exact decoded word reached from the proven ELF
  entry through resolved direct edges. ``PROVEN`` here is the shared model's
  structural classification; it is not a runtime-execution claim and not an
  instruction-semantics claim (P3-04 owns the semantics frontier);
* the shared layers have no MIPS32 delay-slot concept, so the frontier's delay
  slots are represented as ordinary ``NORMAL`` instructions and their
  delay-slot relationship is preserved separately as explicit frontier
  evidence (``delay_slot_frontier``); the structural approximation is recorded
  rather than hidden.

This module is OpenRecomp-original, standard-library only, and contains no
console assets, proprietary data or copied tables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import p3_code_frontier_v1 as frontier_v1
import p3_decode_mips32_v1 as decode_v1
from openrecomp.call_graph import CallEdgeKind, CallGraph, build_call_graph
from openrecomp.cfg import CFGMode, ControlFlowGraph, EntryPoint, build_cfg
from openrecomp.functions import FunctionDiscoveryResult, discover_functions
from openrecomp.program_model import (
    DecodedInstruction,
    EvidenceClass,
    InstructionFlow,
    ProgramSource,
    instruction_from_adapter,
)
from openrecomp.translation_units import TranslationUnitSet, build_translation_units

STRUCTURE_VERSION = "1.0.0"

CONTINUATION_TRAPS = frozenset({"div", "divu", "teq", "tge", "tgeu", "tlt", "tltu", "tne"})
CONTROL_TERMINATORS = frozenset({
    decode_v1.TERM_CONDITIONAL_BRANCH,
    decode_v1.TERM_JUMP,
    decode_v1.TERM_DIRECT_CALL,
    decode_v1.TERM_RETURN,
    decode_v1.TERM_INDIRECT_CALL,
    decode_v1.TERM_INDIRECT_JUMP,
    decode_v1.TERM_UNSUPPORTED_CONTROL,
    decode_v1.TERM_EXTERNAL_TRAP,
})


class StructureError(ValueError):
    """Fail-closed structure-bridge rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class StructureResult:
    """The neutral Phase-2 structure derived from one frozen frontier analysis."""

    source: ProgramSource
    entry: int
    instructions: tuple[DecodedInstruction, ...]
    cfg: ControlFlowGraph
    discovery: FunctionDiscoveryResult
    call_graph: CallGraph
    units: TranslationUnitSet
    unreachable_frontier: tuple[dict[str, Any], ...]
    delay_slot_frontier: tuple[dict[str, Any], ...]
    reachable_records: tuple[dict[str, Any], ...] = field(default=())


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise StructureError(code, detail)


def flow_for_record(record: dict[str, Any]) -> tuple[InstructionFlow, int | None, bool]:
    """Map one frozen frontier record to neutral flow facts (fail closed)."""
    address = record.get("address")
    if not isinstance(address, int) or address < 0 or address & 3:
        raise StructureError("INVALID_RECORD_ADDRESS", f"address={address!r}")
    if decode_v1.is_invalid(record):
        raise StructureError(
            "REACHABLE_INVALID_ENCODING",
            f"0x{address:08x} {record.get('reason')}")

    control_flow = record.get("control_flow")
    terminator = record.get("terminator")
    delay_slot = record.get("delay_slot")
    target = record.get("target")

    if not control_flow:
        if terminator is not None:
            raise StructureError(
                "INCONSISTENT_TERMINATOR",
                f"0x{address:08x} non-control record carries terminator {terminator!r}")
        if delay_slot:
            raise StructureError(
                "INCONSISTENT_DELAY_SLOT",
                f"0x{address:08x} non-control record claims a delay slot")
        if record.get("exception_transfer") and record.get("op") not in CONTINUATION_TRAPS:
            raise StructureError(
                "UNKNOWN_EXCEPTION_TRANSFER",
                f"0x{address:08x} non-control exception transfer op={record.get('op')!r}")
        if target is not None:
            raise StructureError(
                "INCONSISTENT_TARGET",
                f"0x{address:08x} non-control record carries target 0x{target:x}")
        return InstructionFlow.NORMAL, None, False

    if terminator not in CONTROL_TERMINATORS:
        raise StructureError(
            "UNKNOWN_TERMINATOR", f"0x{address:08x} terminator={terminator!r}")

    if terminator in (decode_v1.TERM_UNSUPPORTED_CONTROL, decode_v1.TERM_EXTERNAL_TRAP):
        if terminator == decode_v1.TERM_UNSUPPORTED_CONTROL:
            raise StructureError(
                "UNSUPPORTED_CONTROL_TRANSFER",
                f"0x{address:08x} op={record.get('op')!r}; never guessed")
        if target is not None or delay_slot:
            raise StructureError(
                "INCONSISTENT_TRAP",
                f"0x{address:08x} external trap with target/delay-slot")
        return InstructionFlow.TRAP, None, False

    _require(delay_slot is True, "MISSING_DELAY_SLOT",
             f"0x{address:08x} {terminator} without a delay slot")
    if target is not None and (not isinstance(target, int) or target & 3):
        raise StructureError(
            "INVALID_DIRECT_TARGET", f"0x{address:08x} target={target!r}")

    if terminator == decode_v1.TERM_CONDITIONAL_BRANCH:
        if target is None:
            raise StructureError(
                "MISSING_BRANCH_TARGET",
                f"0x{address:08x} {record.get('op')!r} branch without an encoded target")
        return InstructionFlow.BRANCH, target, False
    if terminator == decode_v1.TERM_JUMP:
        if target is None:
            raise StructureError(
                "MISSING_JUMP_TARGET",
                f"0x{address:08x} {record.get('op')!r} jump without an encoded target")
        return InstructionFlow.JUMP, target, False
    if terminator == decode_v1.TERM_DIRECT_CALL:
        if target is None:
            raise StructureError(
                "MISSING_CALL_TARGET",
                f"0x{address:08x} {record.get('op')!r} call without an encoded target")
        return InstructionFlow.CALL, target, False
    if terminator == decode_v1.TERM_RETURN:
        if target is not None:
            raise StructureError(
                "RETURN_WITH_TARGET", f"0x{address:08x} return carries a target")
        return InstructionFlow.RETURN, None, False
    if terminator == decode_v1.TERM_INDIRECT_CALL:
        if target is not None:
            raise StructureError(
                "INDIRECT_CALL_WITH_TARGET",
                f"0x{address:08x} indirect call carries a static target")
        return InstructionFlow.INDIRECT_CALL, None, True
    if terminator == decode_v1.TERM_INDIRECT_JUMP:
        if target is not None:
            raise StructureError(
                "INDIRECT_JUMP_WITH_TARGET",
                f"0x{address:08x} indirect jump carries a static target")
        return InstructionFlow.INDIRECT_JUMP, None, True
    raise StructureError("UNREACHABLE_TERMINATOR", f"0x{address:08x} {terminator!r}")


def neutral_instruction(record: dict[str, Any]) -> DecodedInstruction:
    """Build one neutral instruction from a reachable frozen frontier record."""
    flow, direct_target, unresolved = flow_for_record(record)
    operands = record.get("operands")
    if not isinstance(operands, dict):
        raise StructureError("MISSING_OPERANDS", f"0x{record['address']:08x}")
    metadata = {
        "word": record["word"],
        "decode_class": record["decode_class"],
        "semantics": record["semantics"],
        "operands": dict(operands),
        "delay_slot": bool(record["delay_slot"]),
        "exception_transfer": bool(record["exception_transfer"]),
    }
    return instruction_from_adapter(
        {"address": record["address"], "op": record["op"]},
        flow=flow,
        unresolved=unresolved,
        direct_target=direct_target,
        size_bytes=4,
        evidence=EvidenceClass.PROVEN,
        metadata=metadata,
    )


def _index_reachable(analysis: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], list[int]]:
    if not isinstance(analysis, dict):
        raise StructureError("INVALID_ANALYSIS", f"type={type(analysis).__name__}")
    records = analysis.get("records")
    if not isinstance(records, list) or not records:
        raise StructureError("INVALID_ANALYSIS", "records must be a non-empty list")
    by_address: dict[int, dict[str, Any]] = {}
    for record in records:
        address = record.get("address") if isinstance(record, dict) else None
        if not isinstance(address, int):
            raise StructureError("INVALID_RECORD", f"address={address!r}")
        if address in by_address:
            raise StructureError("DUPLICATE_RECORD", f"0x{address:08x}")
        by_address[address] = record
    region = analysis.get("region")
    if not isinstance(region, dict):
        raise StructureError("INVALID_ANALYSIS", "region must be an object")
    start, end = region.get("start"), region.get("end")
    if not isinstance(start, int) or not isinstance(end, int) or start & 3 or end & 3 or end <= start:
        raise StructureError("INVALID_REGION", f"start={start!r} end={end!r}")
    if region.get("words") != len(records):
        raise StructureError(
            "INCONSISTENT_REGION",
            f"declared_words={region.get('words')!r} records={len(records)}")
    if sorted(by_address) != list(range(start, end, 4)):
        raise StructureError("INCONSISTENT_REGION", "record addresses do not tile the region")
    reachable = analysis.get("reachable_addresses")
    if not isinstance(reachable, list):
        raise StructureError("INVALID_ANALYSIS", "reachable_addresses must be a list")
    for address in reachable:
        if not isinstance(address, int) or address not in by_address:
            raise StructureError("INVALID_REACHABLE_ADDRESS", f"{address!r}")
    return by_address, list(reachable)


def analyze_structure(
    analysis: dict[str, Any],
    *,
    source: ProgramSource,
    entry: int,
) -> StructureResult:
    """Derive the neutral Phase-2 structure from a frozen frontier analysis."""
    if not isinstance(source, ProgramSource):
        raise StructureError("INVALID_SOURCE", f"type={type(source).__name__}")
    if not isinstance(entry, int) or entry < 0 or entry & 3:
        raise StructureError("INVALID_ENTRY", f"entry={entry!r}")

    by_address, reachable_addresses = _index_reachable(analysis)
    region = analysis["region"]
    start, end = region["start"], region["end"]
    if not (isinstance(start, int) and isinstance(end, int) and start < end):
        raise StructureError("INVALID_REGION", f"start={start!r} end={end!r}")
    if not start <= entry < end:
        raise StructureError("ENTRY_OUTSIDE_REGION", f"entry=0x{entry:x}")
    if start not in by_address:
        raise StructureError("ENTRY_NOT_DECODED", f"entry=0x{entry:x}")

    reachable_set = set(reachable_addresses)
    reachable_records = [
        by_address[address] for address in sorted(reachable_set)
    ]
    unreachable_records = [
        by_address[address] for address in sorted(set(by_address) - reachable_set)
    ]

    instructions = tuple(neutral_instruction(record) for record in reachable_records)

    entry_point = EntryPoint(
        entry,
        EvidenceClass.PROVEN,
        "ELF program entry (P3-01/P3-02 verified) reached through the P3-03 direct frontier",
    )
    cfg = build_cfg(
        instructions,
        source=source,
        entries=[entry_point],
        mode=CFGMode.CLOSED,
    )
    discovery = discover_functions(
        cfg,
        program_entries=[entry_point],
        include_direct_call_targets=True,
    )
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)

    delay_slot_frontier = tuple(
        {
            "owner": item["owner"],
            "owner_op": by_address[item["owner"]]["op"],
            "owner_terminator": by_address[item["owner"]]["terminator"],
            "delay": item["delay"],
            "delay_op": by_address[item["delay"]]["op"],
        }
        for item in sorted(analysis["delay_slots"], key=lambda item: (item["delay"], item["owner"]))
    )
    unreachable_frontier = tuple(
        {
            "address": record["address"],
            "word": record["word"],
            "decode_class": record["decode_class"],
            "op": record["op"],
            "control_flow": record["control_flow"],
        }
        for record in unreachable_records
    )
    return StructureResult(
        source=source,
        entry=entry,
        instructions=instructions,
        cfg=cfg,
        discovery=discovery,
        call_graph=call_graph,
        units=units,
        unreachable_frontier=unreachable_frontier,
        delay_slot_frontier=delay_slot_frontier,
        reachable_records=tuple(reachable_records),
    )


def flow_histogram(result: StructureResult) -> dict[str, int]:
    histogram: dict[str, int] = {}
    for instruction in result.instructions:
        histogram[instruction.flow.value] = histogram.get(instruction.flow.value, 0) + 1
    return dict(sorted(histogram.items()))


def edge_histogram(result: StructureResult) -> dict[str, int]:
    histogram: dict[str, int] = {}
    for block in result.cfg.ordered_blocks():
        for successor in block.successors:
            histogram[successor.kind.value] = histogram.get(successor.kind.value, 0) + 1
    return dict(sorted(histogram.items()))


def structure_summary(result: StructureResult) -> dict[str, Any]:
    """Deterministic aggregate facts used by the gate and the evidence files."""
    cfg = result.cfg
    discovery = result.discovery
    call_graph = result.call_graph
    units = result.units
    return {
        "structure_version": STRUCTURE_VERSION,
        "entry": result.entry,
        "instruction_count": len(result.instructions),
        "flow_histogram": flow_histogram(result),
        "block_count": len(cfg.blocks),
        "edge_histogram": edge_histogram(result),
        "resolved_edges": sum(
            1 for block in cfg.ordered_blocks() for successor in block.successors if successor.resolved),
        "unresolved_edges": sum(
            1 for block in cfg.ordered_blocks() for successor in block.successors if not successor.resolved),
        "direct_call_sites": len(cfg.direct_call_sites),
        "unresolved_call_sites": len(cfg.unresolved_call_sites),
        "unresolved_jump_sites": len(cfg.unresolved_jump_sites),
        "function_count": len(discovery.functions),
        "unowned_blocks": list(discovery.unowned_blocks),
        "shared_blocks": [item.to_document() for item in discovery.shared_blocks],
        "suppressed_entries": [item.to_document() for item in discovery.suppressed_entries],
        "external_direct_call_targets": [
            item.to_document() for item in discovery.external_direct_call_targets
        ],
        "call_graph_nodes": len(call_graph.nodes),
        "call_graph_edges": len(call_graph.edges),
        "call_graph_internal_edges": len(call_graph.internal_edges()),
        "call_graph_external_edges": len(call_graph.external_edges()),
        "call_graph_unresolved_edges": len(call_graph.unresolved_edges()),
        "call_graph_recursive": list(call_graph.recursive_functions()),
        "translation_unit_count": len(units.units),
        "entry_unit": units.entry_unit,
        "unowned_control_flow": [site.to_document() for site in units.unowned_control_flow],
        "program_model_fingerprint": discovery.to_program_model().fingerprint(),
        "cfg_fingerprint": cfg.fingerprint(),
        "call_graph_fingerprint": call_graph.fingerprint(),
        "translation_unit_set_fingerprint": units.fingerprint(),
        "discovery_fingerprint": discovery.fingerprint(),
        "unreachable_word_count": len(result.unreachable_frontier),
        "delay_slot_count": len(result.delay_slot_frontier),
        "indirect_sites": [
            {
                "address": instruction.address,
                "op": instruction.op,
                "flow": instruction.flow.value,
                "direct_target": instruction.direct_target,
                "unresolved": instruction.unresolved,
                "target_resolution": "not statically resolved; no target invented",
            }
            for instruction in result.instructions
            if instruction.flow in (InstructionFlow.INDIRECT_JUMP, InstructionFlow.INDIRECT_CALL)
        ],
    }


__all__ = [
    "CONTINUATION_TRAPS",
    "CONTROL_TERMINATORS",
    "STRUCTURE_VERSION",
    "StructureError",
    "StructureResult",
    "analyze_structure",
    "edge_histogram",
    "flow_for_record",
    "flow_histogram",
    "neutral_instruction",
    "structure_summary",
]
