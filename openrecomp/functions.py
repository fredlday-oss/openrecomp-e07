"""OpenRecomp deterministic architecture-neutral function discovery (P2-03).

`OpenRecomp Phase 2` stage P2-03 deliverable. This module derives P2-01
`FunctionUnit` structures from evidence-backed function entries plus P2-02
`ControlFlowGraph` reachability.

It builds on the shared model and CFG and reuses their types unchanged. It does
**not** implement the final whole-program call graph (P2-04), translation units,
IR lowering or AOT integration, and it contains no ISA-specific function
heuristics (no prologue/epilogue, alignment, symbol-name or stack-frame rules).

Discovery model:

* entries come only from explicit evidence: a program/executable entry, a
  proven direct-call target, or an explicitly supplied proven/candidate function
  entry;
* a function body is the CFG-reachable set of blocks from its entry, following
  resolved intra-function edges only (no unresolved targets, no callee
  absorption);
* ownership is partitioned deterministically: PROVEN entries before CANDIDATE,
  then lower entry address first; weaker candidates nested in a proven function
  are suppressed with an explicit reason;
* direct calls record call-site information and may populate provisional
  `direct_callees`, but never absorb the callee;
* evidence is conservative: a function is `PROVEN` only when the entry and all
  required owned structure justify it.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from openrecomp.cfg import CFGMode, CallSite, ControlFlowGraph, EntryPoint, combine_evidence
from openrecomp.program_model import (
    BasicBlock,
    EvidenceClass,
    FunctionUnit,
    ProgramModel,
    ProgramSource,
    UnresolvedSite,
    _require_address,
    _require_keys,
    _require_object,
    canonical_json,
)

DISCOVERY_VERSION = "1.0.0"


class FunctionDiscoveryError(ValueError):
    """Raised when function discovery input is invalid or cannot be represented."""


class FunctionEntrySource(str, Enum):
    """The independent basis on which a function entry was established."""

    PROGRAM_ENTRY = "PROGRAM_ENTRY"
    DIRECT_CALL = "DIRECT_CALL"
    EXPLICIT_PROVEN = "EXPLICIT_PROVEN"
    EXPLICIT_CANDIDATE = "EXPLICIT_CANDIDATE"


_SOURCE_RANK = {
    FunctionEntrySource.PROGRAM_ENTRY: 0,
    FunctionEntrySource.DIRECT_CALL: 1,
    FunctionEntrySource.EXPLICIT_PROVEN: 2,
    FunctionEntrySource.EXPLICIT_CANDIDATE: 3,
}


def _evidence_rank(evidence: EvidenceClass) -> int:
    return 0 if evidence is EvidenceClass.PROVEN else 1


@dataclass(frozen=True)
class FunctionEntry:
    """A caller-supplied function entry with its evidence source."""

    address: int
    source: FunctionEntrySource
    evidence: EvidenceClass
    detail: str | None = None

    def __post_init__(self) -> None:
        _require_address(self.address, "function entry.address")
        if not isinstance(self.source, FunctionEntrySource):
            raise FunctionDiscoveryError(f"function entry.source must be a FunctionEntrySource, got {self.source!r}")
        if not isinstance(self.evidence, EvidenceClass):
            raise FunctionDiscoveryError(f"function entry.evidence must be an EvidenceClass, got {self.evidence!r}")
        if self.source is FunctionEntrySource.EXPLICIT_PROVEN and self.evidence is not EvidenceClass.PROVEN:
            raise FunctionDiscoveryError("EXPLICIT_PROVEN entries require PROVEN evidence")
        if self.source is FunctionEntrySource.EXPLICIT_CANDIDATE and self.evidence is not EvidenceClass.CANDIDATE:
            raise FunctionDiscoveryError("EXPLICIT_CANDIDATE entries require CANDIDATE evidence")
        if self.detail is not None and (not isinstance(self.detail, str) or not self.detail):
            raise FunctionDiscoveryError("function entry.detail must be a non-empty string or null")

    def to_document(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "source": self.source.value,
            "evidence": self.evidence.value,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class EntryBasis:
    """One independent reason a function entry exists (internal provenance)."""

    address: int
    source: FunctionEntrySource
    evidence: EvidenceClass
    detail: str | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "source": self.source.value,
            "evidence": self.evidence.value,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class SuppressedEntry:
    """An entry that was not given its own function, with the reason."""

    address: int
    evidence: EvidenceClass
    reason: str
    owner: str | None = None

    def to_document(self) -> dict[str, Any]:
        return {"address": self.address, "evidence": self.evidence.value, "reason": self.reason, "owner": self.owner}


@dataclass(frozen=True)
class SharedBlock:
    """A non-entry block reachable from multiple function entries."""

    block_id: str
    owner: str
    also_reachable_from: tuple[str, ...]

    def to_document(self) -> dict[str, Any]:
        return {"block": self.block_id, "owner": self.owner, "also_reachable_from": list(self.also_reachable_from)}


@dataclass(frozen=True)
class ExternalDirectCallTarget:
    """A direct-call target outside the supplied CFG (no function invented)."""

    address: int
    evidence: EvidenceClass
    call_site_block: str | None = None

    def to_document(self) -> dict[str, Any]:
        return {"address": self.address, "evidence": self.evidence.value, "call_site_block": self.call_site_block}


class FunctionDiscoveryResult:
    """Deterministic outcome of function discovery over one `ControlFlowGraph`."""

    def __init__(
        self,
        cfg: ControlFlowGraph,
        functions: Iterable[FunctionUnit],
        provenance: Mapping[str, tuple[EntryBasis, ...]],
        suppressed: Iterable[SuppressedEntry],
        external_direct_call_targets: Iterable[ExternalDirectCallTarget],
        shared_blocks: Iterable[SharedBlock],
        unowned_blocks: Iterable[str],
        entry_function_id: str,
    ) -> None:
        self.cfg = cfg
        self.functions = tuple(sorted(functions, key=lambda function: (function.entry_address, function.id)))
        self.provenance = {key: tuple(value) for key, value in sorted(provenance.items())}
        self.suppressed_entries = tuple(sorted(suppressed, key=lambda item: item.address))
        self.external_direct_call_targets = tuple(sorted(external_direct_call_targets, key=lambda item: item.address))
        self.shared_blocks = tuple(sorted(shared_blocks, key=lambda item: item.block_id))
        self.unowned_blocks = tuple(sorted(unowned_blocks))
        self.entry_function_id = entry_function_id
        self._functions_by_id = {function.id: function for function in self.functions}
        self.program_model = ProgramModel(cfg.source, list(self.functions), entry_function_id)

    def function(self, function_id: str) -> FunctionUnit:
        try:
            return self._functions_by_id[function_id]
        except KeyError as exc:
            raise FunctionDiscoveryError(f"unknown function {function_id}") from exc

    def basis(self, function_id: str) -> tuple[EntryBasis, ...]:
        return self.provenance.get(function_id, ())

    def to_program_model(self) -> ProgramModel:
        return self.program_model

    def to_document(self) -> dict[str, Any]:
        return {
            "discovery_version": DISCOVERY_VERSION,
            "source": self.cfg.source.to_document(),
            "entry_function": self.entry_function_id,
            "functions": [function.to_document() for function in self.functions],
            "provenance": {
                function_id: [basis.to_document() for basis in basis_list]
                for function_id, basis_list in sorted(self.provenance.items())
            },
            "suppressed_entries": [item.to_document() for item in self.suppressed_entries],
            "external_direct_call_targets": [item.to_document() for item in self.external_direct_call_targets],
            "shared_blocks": [item.to_document() for item in self.shared_blocks],
            "unowned_blocks": list(self.unowned_blocks),
        }

    def serialize(self) -> bytes:
        return (canonical_json(self.to_document()) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return hashlib.sha256(self.serialize()).hexdigest()


def _entry_basis_from_program(entry: int | EntryPoint) -> EntryBasis:
    if isinstance(entry, EntryPoint):
        return EntryBasis(entry.address, FunctionEntrySource.PROGRAM_ENTRY, entry.evidence, entry.detail)
    if isinstance(entry, bool) or not isinstance(entry, int):
        raise FunctionDiscoveryError(f"program entry must be an int or EntryPoint, got {entry!r}")
    return EntryBasis(entry, FunctionEntrySource.PROGRAM_ENTRY, EvidenceClass.PROVEN, None)


def _entry_basis_from_function(entry: int | FunctionEntry) -> EntryBasis:
    if isinstance(entry, FunctionEntry):
        return EntryBasis(entry.address, entry.source, entry.evidence, entry.detail)
    if isinstance(entry, bool) or not isinstance(entry, int):
        raise FunctionDiscoveryError(f"function entry must be an int or FunctionEntry, got {entry!r}")
    return EntryBasis(entry, FunctionEntrySource.EXPLICIT_CANDIDATE, EvidenceClass.CANDIDATE, None)


def discover_functions(
    cfg: ControlFlowGraph,
    *,
    program_entries: Iterable[int | EntryPoint] = (),
    function_entries: Iterable[int | FunctionEntry] = (),
    include_direct_call_targets: bool = True,
) -> FunctionDiscoveryResult:
    """Derive functions from evidence-backed entries and CFG reachability.

    `program_entries` are program/executable entry points (an `EntryPoint` may
    override the default `PROVEN` evidence). `function_entries` are explicitly
    supplied function entries (an int defaults to `CANDIDATE`). Direct-call
    targets are added when `include_direct_call_targets` is set.
    """
    if not isinstance(cfg, ControlFlowGraph):
        raise FunctionDiscoveryError("cfg must be a ControlFlowGraph")

    block_by_entry: dict[int, BasicBlock] = {block.entry_address: block for block in cfg.blocks}
    block_by_id: dict[str, BasicBlock] = {block.id: block for block in cfg.blocks}

    bases: list[EntryBasis] = []
    for entry in program_entries:
        bases.append(_entry_basis_from_program(entry))
    for entry in function_entries:
        bases.append(_entry_basis_from_function(entry))

    external_targets: list[ExternalDirectCallTarget] = []
    if include_direct_call_targets:
        for site in cfg.direct_call_sites:
            target = site.target_address
            if target in block_by_entry:
                bases.append(EntryBasis(target, FunctionEntrySource.DIRECT_CALL, site.evidence, f"direct call from {site.block_id}"))
            elif target in {instruction.address for instruction in cfg.instructions}:
                raise FunctionDiscoveryError(
                    f"direct-call target 0x{target:x} is inside the region but is not a block boundary"
                )
            else:
                external_targets.append(ExternalDirectCallTarget(target, site.evidence, site.block_id))

    if not bases:
        raise FunctionDiscoveryError("no function entries were supplied and no direct-call targets were found")

    for basis in bases:
        status = block_by_entry.get(basis.address)
        if status is None:
            interior = any(
                instruction.size_bytes is not None
                and instruction.address < basis.address < instruction.address + instruction.size_bytes
                for instruction in cfg.instructions
            )
            if interior:
                raise FunctionDiscoveryError(f"entry 0x{basis.address:x} enters the middle of an instruction")
            starts = {instruction.address for instruction in cfg.instructions}
            if basis.address in starts:
                raise FunctionDiscoveryError(f"entry 0x{basis.address:x} does not start a CFG basic block")
            if basis.source in (FunctionEntrySource.PROGRAM_ENTRY, FunctionEntrySource.EXPLICIT_PROVEN, FunctionEntrySource.EXPLICIT_CANDIDATE):
                raise FunctionDiscoveryError(f"entry 0x{basis.address:x} is absent from the supplied CFG")
            raise FunctionDiscoveryError(f"direct-call target 0x{basis.address:x} is not a CFG block boundary")

    basis_by_address: dict[int, list[EntryBasis]] = {}
    for basis in bases:
        basis_by_address.setdefault(basis.address, []).append(basis)

    entry_evidence: dict[int, EvidenceClass] = {}
    for address, address_bases in basis_by_address.items():
        evidence = (
            EvidenceClass.PROVEN
            if any(item.evidence is EvidenceClass.PROVEN for item in address_bases)
            else EvidenceClass.CANDIDATE
        )
        entry_evidence[address] = evidence

    entry_rank: dict[int, int] = {address: _evidence_rank(evidence) for address, evidence in entry_evidence.items()}
    entry_block_to_address = {block_by_entry[address].id: address for address in entry_evidence}

    def reachable(address: int) -> set[str]:
        start = block_by_entry[address].id
        seen = {start}
        stack = [start]
        while stack:
            current = stack.pop()
            for successor in block_by_id[current].successors:
                if not successor.resolved:
                    continue
                target = successor.target_block
                other = entry_block_to_address.get(target)
                if other is not None and other != address and entry_rank[other] <= entry_rank[address]:
                    continue
                if target not in seen:
                    seen.add(target)
                    stack.append(target)
        return seen

    reachability = {address: reachable(address) for address in entry_evidence}

    priority = sorted(entry_evidence, key=lambda address: (entry_rank[address], address))

    claimed: dict[str, str] = {}
    function_of_entry: dict[int, str] = {}
    entry_of_function: dict[str, int] = {}
    bodies: dict[str, list[str]] = {}
    suppressed: list[SuppressedEntry] = []
    for address in priority:
        start_block = block_by_entry[address]
        if start_block.id in claimed:
            owner = claimed[start_block.id]
            owner_evidence = entry_evidence[entry_of_function[owner]]
            if entry_evidence[address] is EvidenceClass.PROVEN and owner_evidence is EvidenceClass.PROVEN:
                raise FunctionDiscoveryError(
                    f"contradictory PROVEN ownership of block {start_block.id} (entry 0x{address:x})"
                )
            suppressed.append(
                SuppressedEntry(address, entry_evidence[address], "entry block owned by a stronger function", owner)
            )
            continue
        function_id = f"fn_{address:x}"
        body = [block_id for block_id in reachability[address] if block_id not in claimed]
        for block_id in body:
            claimed[block_id] = function_id
        function_of_entry[address] = function_id
        entry_of_function[function_id] = address
        bodies[function_id] = body

    functions: list[FunctionUnit] = []
    provenance: dict[str, tuple[EntryBasis, ...]] = {}
    for address, function_id in sorted(function_of_entry.items(), key=lambda item: item[1]):
        body_set = bodies[function_id]
        entry_block = block_by_entry[address]
        other_blocks = [block_by_id[block_id] for block_id in body_set if block_id != entry_block.id]
        other_blocks.sort(key=lambda block: (block.entry_address, block.id))
        ordered_blocks = (entry_block,) + tuple(other_blocks)

        callees: set[str] = set()
        for site in cfg.direct_call_sites:
            if site.block_id in body_set and site.target_address in function_of_entry:
                callees.add(function_of_entry[site.target_address])
        unresolved_sites = tuple(
            sorted(
                (site for site in cfg.unresolved_call_sites if site.block_id in body_set),
                key=lambda item: (item.address, item.block_id, item.op),
            )
        )
        internal_edge_evidence: list[EvidenceClass] = []
        for block in ordered_blocks:
            for successor in block.successors:
                if successor.resolved and successor.target_block in body_set:
                    internal_edge_evidence.append(successor.evidence)
        evidence = combine_evidence(
            entry_evidence[address],
            *[block.evidence for block in ordered_blocks],
            *internal_edge_evidence,
        )
        sources = tuple(sorted({basis.source.value for basis in basis_by_address[address]}))
        functions.append(
            FunctionUnit(
                function_id,
                address,
                ordered_blocks,
                direct_callees=tuple(sorted(callees)),
                unresolved_call_sites=unresolved_sites,
                evidence=evidence,
                entry_sources=sources,
            )
        )
        provenance[function_id] = tuple(sorted(basis_by_address[address], key=lambda item: (_SOURCE_RANK[item.source], item.evidence.value)))

    if not functions:
        raise FunctionDiscoveryError("no functions could be discovered from the supplied entries")

    program_entry_addresses = sorted(
        address for address, address_bases in basis_by_address.items() if any(b.source is FunctionEntrySource.PROGRAM_ENTRY for b in address_bases)
    )
    if program_entry_addresses and program_entry_addresses[0] in function_of_entry:
        entry_function_id = function_of_entry[program_entry_addresses[0]]
    else:
        entry_function_id = min(functions, key=lambda function: (function.entry_address, function.id)).id

    shared_blocks: list[SharedBlock] = []
    for block_id, owner in sorted(claimed.items()):
        reachable_from = sorted(
            {function_id for address, function_id in function_of_entry.items() if block_id in reachability[address]}
        )
        if len(reachable_from) > 1:
            shared_blocks.append(SharedBlock(block_id, owner, tuple(item for item in reachable_from if item != owner)))

    unowned_blocks = sorted(block.id for block in cfg.blocks if block.id not in claimed)

    return FunctionDiscoveryResult(
        cfg,
        functions,
        provenance,
        suppressed,
        external_targets,
        shared_blocks,
        unowned_blocks,
        entry_function_id,
    )
