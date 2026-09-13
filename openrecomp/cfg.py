"""OpenRecomp deterministic architecture-neutral CFG construction (P2-02).

`OpenRecomp Phase 2` stage P2-02 deliverable. This module derives basic-block
boundaries and control-flow edges from an ordered collection of
`openrecomp.program_model.DecodedInstruction` objects plus explicit neutral
metadata (entry points, direct targets and per-instruction flow classification).

It builds on the P2-01 shared program model and reuses its types unchanged:
`BasicBlock`, `Successor`, `EdgeKind`, `InstructionFlow`, `EvidenceClass`,
`ProgramSource`, `UnresolvedSite` and canonical JSON. It does **not** implement
function discovery (P2-03), whole-program call-graph recovery, translation units
or IR lowering.

Design rules:

* block boundaries come only from supplied entries, proven direct targets, and
  structural continuation after explicitly classified control flow; no ISA
  assumption (no ``address + 4``, no delay slots, no fixed width);
* instruction extent is read from `DecodedInstruction.size_bytes`; if a required
  fallthrough extent is unavailable the builder fails closed;
* indirect/unresolved control flow is preserved explicitly, never guessed;
* derived structure never increases evidence strength: an edge or block is
  `PROVEN` only if every input is `PROVEN`;
* two explicit modes: `CLOSED` (every direct local edge must resolve to a
  supplied instruction) and `OPEN` (an edge may leave the supplied region as an
  explicit unresolved edge carrying its destination address);
* construction is deterministic: sorting and canonical serialization do not
  depend on input order or object identity.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from openrecomp.program_model import (
    BasicBlock,
    DecodedInstruction,
    EdgeKind,
    EvidenceClass,
    FunctionUnit,
    InstructionFlow,
    ProgramModel,
    ProgramSource,
    Successor,
    UnresolvedSite,
    _require_address,
    _require_id,
    _require_keys,
    _require_object,
    canonical_json,
)

CFG_VERSION = "1.0.0"
_BLOCK_PREFIX = "blk"
_REGION_PREFIX = "region"
_TARGET_BEARING_KINDS = frozenset(
    {
        EdgeKind.FALLTHROUGH,
        EdgeKind.BRANCH_TAKEN,
        EdgeKind.BRANCH_NOT_TAKEN,
        EdgeKind.JUMP,
        EdgeKind.CALL_RETURN,
        EdgeKind.INDIRECT,
    }
)


class CFGError(ValueError):
    """Raised when CFG input or a constructed graph is invalid or ambiguous."""


class CFGMode(str, Enum):
    """Resolution policy for direct edges that leave the supplied region."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"


def combine_evidence(*classes: EvidenceClass) -> EvidenceClass:
    """Conservative evidence join: PROVEN only if every input is PROVEN."""
    if not classes:
        return EvidenceClass.CANDIDATE
    for item in classes:
        if not isinstance(item, EvidenceClass):
            raise CFGError(f"evidence must be EvidenceClass, got {item!r}")
    return EvidenceClass.PROVEN if all(item is EvidenceClass.PROVEN for item in classes) else EvidenceClass.CANDIDATE


@dataclass(frozen=True)
class EntryPoint:
    """An explicit region entry point supplied to the CFG builder."""

    address: int
    evidence: EvidenceClass = EvidenceClass.CANDIDATE
    detail: str | None = None

    def __post_init__(self) -> None:
        _require_address(self.address, "entry.address")
        if not isinstance(self.evidence, EvidenceClass):
            raise CFGError("entry.evidence must be an EvidenceClass")
        if self.detail is not None and (not isinstance(self.detail, str) or not self.detail):
            raise CFGError("entry.detail must be a non-empty string or null")

    def to_document(self) -> dict[str, Any]:
        return {"address": self.address, "evidence": self.evidence.value, "detail": self.detail}

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "EntryPoint":
        _require_object(document, "entry")
        _require_keys(document, {"address"}, "entry")
        return cls(
            address=document["address"],
            evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
            detail=document.get("detail"),
        )


@dataclass(frozen=True)
class CallSite:
    """A proven direct call site (callee identity is a later-stage concern)."""

    block_id: str
    address: int
    op: str
    target_address: int
    evidence: EvidenceClass = EvidenceClass.CANDIDATE

    def __post_init__(self) -> None:
        _require_id(self.block_id, "call_site.block_id")
        _require_address(self.address, "call_site.address")
        if not isinstance(self.op, str) or not self.op:
            raise CFGError("call_site.op must be a non-empty string")
        _require_address(self.target_address, "call_site.target_address")
        if not isinstance(self.evidence, EvidenceClass):
            raise CFGError("call_site.evidence must be an EvidenceClass")

    def to_document(self) -> dict[str, Any]:
        return {
            "block": self.block_id,
            "address": self.address,
            "op": self.op,
            "target": self.target_address,
            "evidence": self.evidence.value,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "CallSite":
        _require_object(document, "call_site")
        _require_keys(document, {"block", "address", "op", "target"}, "call_site")
        return cls(
            block_id=document["block"],
            address=document["address"],
            op=document["op"],
            target_address=document["target"],
            evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
        )


class ControlFlowGraph:
    """A validated, deterministic basic-block / CFG structure."""

    def __init__(
        self,
        source: ProgramSource,
        mode: CFGMode,
        entries: Iterable[EntryPoint],
        instructions: Iterable[DecodedInstruction],
        blocks: Iterable[BasicBlock],
        *,
        direct_call_sites: Iterable[CallSite] = (),
        unresolved_call_sites: Iterable[UnresolvedSite] = (),
        unresolved_jump_sites: Iterable[UnresolvedSite] = (),
        validate: bool = True,
    ) -> None:
        if not isinstance(source, ProgramSource):
            raise CFGError("source must be a ProgramSource")
        if not isinstance(mode, CFGMode):
            raise CFGError(f"mode must be a CFGMode, got {mode!r}")
        self.source = source
        self.mode = mode
        self.entries = tuple(entries)
        self.instructions = tuple(instructions)
        self.blocks = tuple(blocks)
        self.direct_call_sites = tuple(direct_call_sites)
        self.unresolved_call_sites = tuple(unresolved_call_sites)
        self.unresolved_jump_sites = tuple(unresolved_jump_sites)
        self._by_address: dict[int, DecodedInstruction] = {}
        self._block_by_id: dict[str, BasicBlock] = {}
        self._block_by_entry: dict[int, BasicBlock] = {}
        if validate:
            self.validate()

    def validate(self) -> None:
        width = self.source.address_width_bits
        self._by_address = {}
        for instruction in self.instructions:
            if not isinstance(instruction, DecodedInstruction):
                raise CFGError("instructions must be DecodedInstruction instances")
            if instruction.address in self._by_address:
                raise CFGError(f"duplicate instruction address 0x{instruction.address:x}")
            if width is not None and instruction.address >= (1 << width):
                raise CFGError(f"instruction 0x{instruction.address:x} exceeds the declared {width}-bit width")
            self._by_address[instruction.address] = instruction

        self._block_by_id = {}
        self._block_by_entry = {}
        assigned: dict[int, str] = {}
        for block in self.blocks:
            if not isinstance(block, BasicBlock):
                raise CFGError("blocks must be BasicBlock instances")
            if block.id in self._block_by_id:
                raise CFGError(f"duplicate block identity {block.id}")
            if block.entry_address in self._block_by_entry:
                raise CFGError(f"duplicate block entry address 0x{block.entry_address:x}")
            self._block_by_id[block.id] = block
            self._block_by_entry[block.entry_address] = block
            for index, instruction in enumerate(block.instructions):
                supplied = self._by_address.get(instruction.address)
                if supplied is None:
                    raise CFGError(f"block {block.id}: instruction 0x{instruction.address:x} is not supplied")
                if supplied != instruction:
                    raise CFGError(f"block {block.id}: instruction 0x{instruction.address:x} disagrees with the supplied instruction")
                if instruction.address in assigned:
                    raise CFGError(f"instruction 0x{instruction.address:x} is assigned to blocks {assigned[instruction.address]} and {block.id}")
                assigned[instruction.address] = block.id
                if index != len(block.instructions) - 1 and instruction.flow != InstructionFlow.NORMAL:
                    raise CFGError(f"block {block.id}: control-flow instruction 0x{instruction.address:x} appears before the block terminator")

        for instruction in self.instructions:
            if instruction.address not in assigned:
                raise CFGError(f"instruction 0x{instruction.address:x} is not assigned to any block")

        for block in self.blocks:
            for successor in block.successors:
                if successor.resolved:
                    if successor.target_block not in self._block_by_id:
                        raise CFGError(f"block {block.id}: edge targets nonexistent local block {successor.target_block}")
                    target = self._block_by_id[successor.target_block]
                    if successor.target_address is not None and successor.target_address != target.entry_address:
                        raise CFGError(f"block {block.id}: edge target_address does not match block {target.id}")
                elif successor.kind not in _TARGET_BEARING_KINDS:
                    raise CFGError(f"block {block.id}: {successor.kind.value} edge cannot be unresolved")
                elif successor.detail is None:
                    raise CFGError(f"block {block.id}: unresolved edge must carry a detail")

        entry_addresses = [entry.address for entry in self.entries]
        if len(set(entry_addresses)) != len(entry_addresses):
            raise CFGError("duplicate entry point")
        for entry in self.entries:
            if entry.address not in self._block_by_entry:
                raise CFGError(f"entry point 0x{entry.address:x} does not start a block")

        for site in self.direct_call_sites:
            self._validate_site(site.block_id, site.address, InstructionFlow.CALL, "direct call site")
        for site in self.unresolved_call_sites:
            self._validate_site(site.block_id, site.address, InstructionFlow.INDIRECT_CALL, "unresolved call site")
        for site in self.unresolved_jump_sites:
            self._validate_site(site.block_id, site.address, InstructionFlow.INDIRECT_JUMP, "unresolved jump site")

    def _validate_site(self, block_id: str, address: int, flow: InstructionFlow, label: str) -> None:
        block = self._block_by_id.get(block_id)
        if block is None:
            raise CFGError(f"{label} references unknown block {block_id}")
        matches = [instruction for instruction in block.instructions if instruction.address == address]
        if not matches:
            raise CFGError(f"{label} address 0x{address:x} is not in block {block_id}")
        if matches[0].flow != flow:
            raise CFGError(f"{label} at 0x{address:x} is not a {flow.value} instruction")

    def ordered_blocks(self) -> tuple[BasicBlock, ...]:
        return tuple(sorted(self.blocks, key=lambda block: (block.entry_address, block.id)))

    def ordered_entries(self) -> tuple[EntryPoint, ...]:
        return tuple(sorted(self.entries, key=lambda entry: (entry.address, entry.evidence.value)))

    def block(self, block_id: str) -> BasicBlock:
        try:
            return self._block_by_id[block_id]
        except KeyError as exc:
            raise CFGError(f"unknown block {block_id}") from exc

    def predecessors(self) -> dict[str, tuple[dict[str, Any], ...]]:
        """Derive predecessors from resolved edges; always internally consistent."""
        collected: dict[str, list[dict[str, Any]]] = {block.id: [] for block in self.blocks}
        for block in self.ordered_blocks():
            for successor in block.successors:
                if successor.resolved and successor.target_block in collected:
                    collected[successor.target_block].append(
                        {"from": block.id, "kind": successor.kind.value, "evidence": successor.evidence.value}
                    )
        return {
            block_id: tuple(sorted(items, key=lambda item: (item["from"], item["kind"])))
            for block_id, items in sorted(collected.items())
        }

    def to_program_model(self, region_id: str | None = None) -> ProgramModel:
        """Wrap the whole region in one neutral container and validate via P2-01.

        This is a serialization/validation bridge only. It does not perform
        function discovery or claim that the region is a single function.
        """
        if not self.blocks:
            raise CFGError("cannot wrap an empty CFG")
        ordered = self.ordered_blocks()
        entry = ordered[0].entry_address
        region_id = region_id or f"{_REGION_PREFIX}_{entry:x}"
        function = FunctionUnit(
            region_id,
            entry,
            ordered,
            unresolved_call_sites=tuple(self.unresolved_call_sites),
            evidence=combine_evidence(*(block.evidence for block in ordered)),
        )
        return ProgramModel(self.source, [function], region_id)

    def to_document(self) -> dict[str, Any]:
        return {
            "cfg_version": CFG_VERSION,
            "mode": self.mode.value,
            "source": self.source.to_document(),
            "entries": [entry.to_document() for entry in self.ordered_entries()],
            "blocks": [block.to_document() for block in self.ordered_blocks()],
            "direct_call_sites": [site.to_document() for site in self._ordered_call_sites()],
            "unresolved_call_sites": [site.to_document() for site in self._ordered_sites(self.unresolved_call_sites)],
            "unresolved_jump_sites": [site.to_document() for site in self._ordered_sites(self.unresolved_jump_sites)],
        }

    def _ordered_call_sites(self) -> tuple[CallSite, ...]:
        return tuple(sorted(self.direct_call_sites, key=lambda site: (site.address, site.block_id, site.target_address)))

    @staticmethod
    def _ordered_sites(sites: Iterable[UnresolvedSite]) -> tuple[UnresolvedSite, ...]:
        return tuple(sorted(sites, key=lambda site: (site.address, site.block_id, site.op)))

    def serialize(self) -> bytes:
        return (canonical_json(self.to_document()) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return hashlib.sha256(self.serialize()).hexdigest()

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "ControlFlowGraph":
        _require_object(document, "cfg")
        _require_keys(document, {"cfg_version", "mode", "source", "entries", "blocks"}, "cfg")
        if document["cfg_version"] != CFG_VERSION:
            raise CFGError(f"unsupported cfg_version {document['cfg_version']!r}")
        if not isinstance(document["blocks"], list) or not document["blocks"]:
            raise CFGError("cfg.blocks must be a non-empty list")
        blocks = tuple(BasicBlock.from_document(item) for item in document["blocks"])
        instructions = tuple(
            sorted((instruction for block in blocks for instruction in block.instructions), key=lambda item: item.address)
        )
        return cls(
            source=ProgramSource.from_document(document["source"]),
            mode=CFGMode(document["mode"]),
            entries=tuple(EntryPoint.from_document(item) for item in document["entries"]),
            instructions=instructions,
            blocks=blocks,
            direct_call_sites=tuple(CallSite.from_document(item) for item in document.get("direct_call_sites", [])),
            unresolved_call_sites=tuple(UnresolvedSite.from_document(item) for item in document.get("unresolved_call_sites", [])),
            unresolved_jump_sites=tuple(UnresolvedSite.from_document(item) for item in document.get("unresolved_jump_sites", [])),
        )

    @classmethod
    def deserialize(cls, data: bytes | str) -> "ControlFlowGraph":
        import json

        try:
            document = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CFGError(f"invalid cfg JSON: {exc}") from exc
        return cls.from_document(document)


def _next_address(instruction: DecodedInstruction) -> int | None:
    if instruction.size_bytes is None:
        return None
    return instruction.address + instruction.size_bytes


def _normalize_entries(entries: Iterable[int | EntryPoint]) -> tuple[EntryPoint, ...]:
    normalized: list[EntryPoint] = []
    for item in entries:
        if isinstance(item, EntryPoint):
            normalized.append(item)
        elif isinstance(item, bool) or not isinstance(item, int):
            raise CFGError(f"entry point must be an int or EntryPoint, got {item!r}")
        else:
            normalized.append(EntryPoint(item))
    if not normalized:
        raise CFGError("at least one entry point is required")
    return tuple(normalized)


def build_cfg(
    instructions: Iterable[DecodedInstruction],
    *,
    source: ProgramSource,
    entries: Iterable[int | EntryPoint],
    mode: CFGMode = CFGMode.CLOSED,
    region_boundaries: Iterable[int] = (),
    presorted: bool = False,
) -> ControlFlowGraph:
    """Derive basic blocks and CFG edges from neutral decoded instructions.

    `instructions` may be supplied in any order unless `presorted` is true, in
    which case the supplied order must already be strictly ascending by address.
    `entries` and `region_boundaries` are explicit block-start addresses.
    """
    if not isinstance(source, ProgramSource):
        raise CFGError("source must be a ProgramSource")
    if not isinstance(mode, CFGMode):
        raise CFGError(f"mode must be a CFGMode, got {mode!r}")

    items = list(instructions)
    for instruction in items:
        if not isinstance(instruction, DecodedInstruction):
            raise CFGError("instructions must be DecodedInstruction instances")
    addresses = [instruction.address for instruction in items]
    if not items:
        raise CFGError("at least one instruction is required")
    if len(set(addresses)) != len(addresses):
        raise CFGError("duplicate instruction address in supplied decoded region")
    if presorted and addresses != sorted(addresses):
        raise CFGError("supplied instruction ordering is not ascending by address")

    width = source.address_width_bits
    ordered = tuple(sorted(items, key=lambda instruction: instruction.address))
    for instruction in ordered:
        if width is not None and instruction.address >= (1 << width):
            raise CFGError(f"instruction 0x{instruction.address:x} exceeds the declared {width}-bit width")
        if instruction.flow in (InstructionFlow.RETURN, InstructionFlow.TRAP) and instruction.direct_target is not None:
            raise CFGError(f"0x{instruction.address:x}: {instruction.flow.value} must not carry a direct target")
        if instruction.flow == InstructionFlow.NORMAL and instruction.unresolved:
            raise CFGError(f"0x{instruction.address:x}: unresolved NORMAL flow is ambiguous")
    by_address = {instruction.address: instruction for instruction in ordered}

    def classify(address: int) -> str:
        if address in by_address:
            return "exact"
        for instruction in ordered:
            if instruction.size_bytes is not None and instruction.address < address < instruction.address + instruction.size_bytes:
                return "interior"
        return "outside"

    for instruction in ordered:
        if instruction.flow in (InstructionFlow.BRANCH, InstructionFlow.CALL, InstructionFlow.INDIRECT_CALL):
            next_address = _next_address(instruction)
            if next_address is not None and classify(next_address) == "interior":
                raise CFGError(f"0x{instruction.address:x}: fallthrough 0x{next_address:x} enters the middle of an instruction")
    for first, second in zip(ordered, ordered[1:]):
        if first.size_bytes is not None and first.address + first.size_bytes > second.address:
            raise CFGError(f"overlapping instruction extent at 0x{first.address:x} and 0x{second.address:x}")

    boundaries = list(region_boundaries)
    for boundary in boundaries:
        if isinstance(boundary, bool) or not isinstance(boundary, int) or boundary < 0:
            raise CFGError(f"malformed region boundary {boundary!r}")
        if width is not None and boundary >= (1 << width):
            raise CFGError(f"region boundary 0x{boundary:x} exceeds the declared {width}-bit width")
    entries_normalized = _normalize_entries(entries)

    leaders: set[int] = set()
    for entry in entries_normalized:
        status = classify(entry.address)
        if status == "interior":
            raise CFGError(f"entry point 0x{entry.address:x} enters the middle of an instruction")
        if status != "exact":
            raise CFGError(f"malformed entry point 0x{entry.address:x}: not a supplied instruction")
        leaders.add(entry.address)
    for boundary in boundaries:
        status = classify(boundary)
        if status == "interior":
            raise CFGError(f"region boundary 0x{boundary:x} enters the middle of an instruction")
        if status != "exact":
            raise CFGError(f"malformed region boundary 0x{boundary:x}: not a supplied instruction")
        leaders.add(boundary)

    for instruction in ordered:
        next_address = _next_address(instruction)
        if instruction.direct_target is not None:
            target = instruction.direct_target
            if width is not None and target >= (1 << width):
                raise CFGError(f"0x{instruction.address:x}: direct target 0x{target:x} exceeds the declared {width}-bit width")
            status = classify(target)
            if status == "interior":
                raise CFGError(f"0x{instruction.address:x}: direct target 0x{target:x} enters the middle of an instruction")
            if status == "outside" and mode == CFGMode.CLOSED and instruction.flow in (InstructionFlow.BRANCH, InstructionFlow.JUMP):
                raise CFGError(f"0x{instruction.address:x}: direct target 0x{target:x} is missing from the closed region")
            if status == "exact":
                leaders.add(target)
        if instruction.flow in (InstructionFlow.BRANCH, InstructionFlow.CALL, InstructionFlow.INDIRECT_CALL):
            if next_address is not None and next_address in by_address:
                leaders.add(next_address)
        if instruction.flow in (InstructionFlow.RETURN, InstructionFlow.TRAP, InstructionFlow.INDIRECT_JUMP):
            if next_address is not None and next_address in by_address:
                leaders.add(next_address)

    specs: list[tuple[int, int]] = []
    start: int | None = None
    for index, instruction in enumerate(ordered):
        if start is None:
            start = index
        end = False
        if instruction.flow != InstructionFlow.NORMAL:
            end = True
        else:
            next_address = _next_address(instruction)
            if next_address is None:
                if index == len(ordered) - 1:
                    end = True
                else:
                    raise CFGError(f"0x{instruction.address:x}: impossible fallthrough (instruction extent unavailable)")
            else:
                following = ordered[index + 1] if index + 1 < len(ordered) else None
                if following is None or next_address != following.address or next_address in leaders:
                    end = True
        if end:
            specs.append((start, index))
            start = None

    entry_evidence = {entry.address: entry.evidence for entry in entries_normalized}
    blocks: list[BasicBlock] = []
    block_evidence: dict[str, EvidenceClass] = {}
    for first, last in specs:
        members = tuple(ordered[first : last + 1])
        entry = members[0].address
        block_id = f"{_BLOCK_PREFIX}_{entry:x}"
        evidence_inputs = [instruction.evidence for instruction in members]
        if entry in entry_evidence:
            evidence_inputs.append(entry_evidence[entry])
        blocks.append(BasicBlock(block_id, entry, members))
        block_evidence[block_id] = combine_evidence(*evidence_inputs)

    block_by_entry = {block.entry_address: block for block in blocks}

    def resolve(block_id: str, target: int | None, kind: EdgeKind, base: EvidenceClass, label: str) -> Successor:
        if target is None:
            return Successor(kind, resolved=False, evidence=base, detail=f"{label}: target unavailable")
        if width is not None and target >= (1 << width):
            raise CFGError(f"0x{target:x}: {label} exceeds the declared {width}-bit width")
        status = classify(target)
        if status == "interior":
            raise CFGError(f"block {block_id}: {label} 0x{target:x} enters the middle of an instruction")
        if status == "exact":
            target_block = block_by_entry.get(target)
            if target_block is None:
                raise CFGError(f"block {block_id}: {label} 0x{target:x} has no local block")
            return Successor(
                kind,
                target_block=target_block.id,
                target_address=target,
                resolved=True,
                evidence=combine_evidence(base, block_evidence[target_block.id]),
            )
        if mode == CFGMode.CLOSED:
            raise CFGError(f"block {block_id}: closed-CFG {label} 0x{target:x} is not in the supplied region")
        return Successor(kind, resolved=False, target_address=target, evidence=base, detail=f"{label}: target leaves the decoded region")

    direct_call_sites: list[CallSite] = []
    unresolved_call_sites: list[UnresolvedSite] = []
    unresolved_jump_sites: list[UnresolvedSite] = []
    finalized: list[BasicBlock] = []
    for block in blocks:
        terminator = block.instructions[-1]
        base = block_evidence[block.id]
        successors: list[Successor] = []
        flow = terminator.flow
        if flow == InstructionFlow.NORMAL:
            next_address = _next_address(terminator)
            if next_address is not None and next_address in by_address:
                target_block = block_by_entry.get(next_address)
                if target_block is not None:
                    successors.append(
                        Successor(
                            EdgeKind.FALLTHROUGH,
                            target_block=target_block.id,
                            target_address=next_address,
                            evidence=combine_evidence(base, block_evidence[target_block.id]),
                        )
                    )
        elif flow == InstructionFlow.BRANCH:
            if terminator.direct_target is None:
                successors.append(resolve(block.id, None, EdgeKind.BRANCH_TAKEN, base, "branch target"))
            else:
                successors.append(resolve(block.id, terminator.direct_target, EdgeKind.BRANCH_TAKEN, base, "branch target"))
            next_address = _next_address(terminator)
            if next_address is None:
                raise CFGError(f"block {block.id}: impossible fallthrough (branch extent unavailable)")
            successors.append(resolve(block.id, next_address, EdgeKind.BRANCH_NOT_TAKEN, base, "branch fallthrough"))
        elif flow == InstructionFlow.JUMP:
            successors.append(resolve(block.id, terminator.direct_target, EdgeKind.JUMP, base, "jump target"))
        elif flow == InstructionFlow.CALL:
            if terminator.direct_target is not None:
                direct_call_sites.append(CallSite(block.id, terminator.address, terminator.op, terminator.direct_target, base))
            next_address = _next_address(terminator)
            if next_address is None:
                raise CFGError(f"block {block.id}: impossible fallthrough (call extent unavailable)")
            successors.append(resolve(block.id, next_address, EdgeKind.CALL_RETURN, base, "call continuation"))
        elif flow == InstructionFlow.INDIRECT_CALL:
            unresolved_call_sites.append(
                UnresolvedSite(block.id, terminator.address, terminator.op, "unresolved indirect call target", base)
            )
            next_address = _next_address(terminator)
            if next_address is None:
                raise CFGError(f"block {block.id}: impossible fallthrough (indirect call extent unavailable)")
            successors.append(resolve(block.id, next_address, EdgeKind.CALL_RETURN, base, "call continuation"))
        elif flow == InstructionFlow.INDIRECT_JUMP:
            unresolved_jump_sites.append(
                UnresolvedSite(block.id, terminator.address, terminator.op, "unresolved indirect jump target", base)
            )
            successors.append(
                Successor(EdgeKind.INDIRECT, resolved=False, evidence=base, detail="unresolved indirect jump target")
            )
        elif flow in (InstructionFlow.RETURN, InstructionFlow.TRAP):
            pass
        else:
            raise CFGError(f"block {block.id}: unsupported flow {flow!r}")
        finalized.append(
            BasicBlock(
                block.id,
                block.entry_address,
                block.instructions,
                tuple(sorted(successors, key=lambda item: (item.kind.value, item.target_address if item.target_address is not None else -1))),
                evidence=block_evidence[block.id],
            )
        )

    return ControlFlowGraph(
        source,
        mode,
        entries_normalized,
        ordered,
        tuple(sorted(finalized, key=lambda block: (block.entry_address, block.id))),
        direct_call_sites=tuple(sorted(direct_call_sites, key=lambda site: (site.address, site.block_id))),
        unresolved_call_sites=tuple(sorted(unresolved_call_sites, key=lambda site: (site.address, site.block_id))),
        unresolved_jump_sites=tuple(sorted(unresolved_jump_sites, key=lambda site: (site.address, site.block_id))),
    )
