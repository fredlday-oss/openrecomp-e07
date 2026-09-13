"""OpenRecomp deterministic architecture-neutral translation units (P2-05).

`OpenRecomp Phase 2` stage P2-05 deliverable. This module packages each P2-03
discovered `FunctionUnit` (with its P2-02 CFG structure and P2-04 direct-call
evidence) into exactly one deterministic `TranslationUnit`, and groups the units
into a validated `TranslationUnitSet`.

A `TranslationUnit` is a **structural packaging boundary**, not a semantic
lowering boundary. This stage does not lower instructions to the normalized
OpenRecomp IR and introduces no architecture-specific semantics: it reuses the
shared P2-01/P2-02/P2-03/P2-04 types unchanged and only re-packages their
evidence.

Guarantees:

* `FunctionUnit -> exactly one TranslationUnit` (one-to-one, stable ids);
* function identity, evidence and arbitrary-precision entry addresses survive
  without truncation;
* block order is canonical (`entry block first`, then `(entry_address, id)`),
  instructions and CFG successors are preserved verbatim;
* resolved direct-call relationships and unresolved indirect call/jump evidence
  are preserved, never invented;
* function-discovery provenance (`entry_sources`, `EntryBasis`) is retained so a
  unit can always be explained;
* set-level residual evidence (`shared_blocks`, `suppressed_entries`,
  `unowned_blocks`, external direct-call inventory and control flow in unowned
  blocks) is retained rather than discarded;
* serialization is canonical and byte-identical for identical inputs;
* structurally invalid or unsupported input fails closed with
  `TranslationUnitError`.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from openrecomp.call_graph import (
    CallEdgeKind,
    CallGraph,
    CallGraphEdge,
    CallGraphError,
    build_call_graph,
    build_call_graph_from,
)
from openrecomp.functions import (
    EntryBasis,
    ExternalDirectCallTarget,
    FunctionDiscoveryResult,
    FunctionEntrySource,
    SharedBlock,
    SuppressedEntry,
)
from openrecomp.program_model import (
    BasicBlock,
    EvidenceClass,
    FunctionUnit,
    ProgramModelError,
    ProgramSource,
    UnresolvedSite,
    _require_address,
    _require_id,
    _require_keys,
    _require_object,
    canonical_json,
)

TRANSLATION_UNIT_VERSION = "1.0.0"


class TranslationUnitError(ValueError):
    """Raised when translation-unit input is invalid or inconsistent."""


def _tu_id(value: Any, where: str) -> str:
    try:
        return _require_id(value, where)
    except ProgramModelError as exc:
        raise TranslationUnitError(str(exc)) from exc


def _tu_address(value: Any, where: str) -> int:
    try:
        return _require_address(value, where)
    except ProgramModelError as exc:
        raise TranslationUnitError(str(exc)) from exc


def _tu_object(value: Any, where: str) -> Mapping[str, Any]:
    try:
        return _require_object(value, where)
    except ProgramModelError as exc:
        raise TranslationUnitError(str(exc)) from exc


def _tu_keys(document: Mapping[str, Any], required: set[str], where: str) -> None:
    try:
        _require_keys(document, required, where)
    except ProgramModelError as exc:
        raise TranslationUnitError(str(exc)) from exc


def _canonical_blocks(blocks: tuple[BasicBlock, ...], entry_address: int) -> tuple[BasicBlock, ...]:
    """Deterministic block order: entry block first, then `(entry_address, id)`."""
    entry_blocks = [block for block in blocks if block.entry_address == entry_address]
    if len(entry_blocks) != 1:
        raise TranslationUnitError(
            f"unit entry 0x{entry_address:x}: exactly one block must start at the entry address, found {len(entry_blocks)}"
        )
    entry = entry_blocks[0]
    others = [block for block in blocks if block is not entry]
    return (entry,) + tuple(sorted(others, key=lambda block: (block.entry_address, block.id)))


def _edge_order_key(edge: CallGraphEdge) -> tuple:
    return (
        edge.call_site_address,
        edge.kind.value,
        edge.callee or "",
        edge.target_address if edge.target_address is not None else -1,
        edge.call_site_block,
    )


def _site_order_key(site: UnresolvedSite) -> tuple:
    return (site.address, site.block_id, site.op)


def _basis_order_key(basis: EntryBasis) -> tuple:
    return (basis.source.value, basis.address, basis.evidence.value)


def _parse_basis(document: Mapping[str, Any]) -> EntryBasis:
    _tu_object(document, "unit provenance entry")
    _tu_keys(document, {"address", "source", "evidence"}, "unit provenance entry")
    return EntryBasis(
        address=document["address"],
        source=FunctionEntrySource(document["source"]),
        evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
        detail=document.get("detail"),
    )


def _parse_suppressed(document: Mapping[str, Any]) -> SuppressedEntry:
    _tu_object(document, "suppressed entry")
    _tu_keys(document, {"address", "evidence", "reason"}, "suppressed entry")
    return SuppressedEntry(
        address=document["address"],
        evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
        reason=document["reason"],
        owner=document.get("owner"),
    )


def _parse_shared(document: Mapping[str, Any]) -> SharedBlock:
    _tu_object(document, "shared block")
    _tu_keys(document, {"block", "owner", "also_reachable_from"}, "shared block")
    return SharedBlock(
        block_id=document["block"],
        owner=document["owner"],
        also_reachable_from=tuple(document.get("also_reachable_from", ())),
    )


def _parse_external(document: Mapping[str, Any]) -> ExternalDirectCallTarget:
    _tu_object(document, "external direct-call target")
    _tu_keys(document, {"address", "evidence"}, "external direct-call target")
    return ExternalDirectCallTarget(
        address=document["address"],
        evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
        call_site_block=document.get("call_site_block"),
    )


@dataclass(frozen=True)
class TranslationUnit:
    """One discovered function packaged for later translation/lowering stages.

    The unit carries the function's identity, canonical block order, the P2-04
    call edges whose caller is this function, the function's unresolved call
    sites, the unresolved jump sites owned by its blocks, and the discovery
    provenance explaining how the function was established. No instruction is
    transformed.
    """

    unit_id: str
    function_id: str
    entry_address: int
    blocks: tuple[BasicBlock, ...]
    call_edges: tuple[CallGraphEdge, ...] = ()
    direct_callees: tuple[str, ...] = ()
    unresolved_call_sites: tuple[UnresolvedSite, ...] = ()
    unresolved_jump_sites: tuple[UnresolvedSite, ...] = ()
    evidence: EvidenceClass = EvidenceClass.CANDIDATE
    entry_sources: tuple[str, ...] = ()
    provenance: tuple[EntryBasis, ...] = ()

    def __post_init__(self) -> None:
        _tu_id(self.unit_id, "translation unit.unit_id")
        _tu_id(self.function_id, "translation unit.function_id")
        _tu_address(self.entry_address, "translation unit.entry_address")
        if not isinstance(self.evidence, EvidenceClass):
            raise TranslationUnitError(f"unit {self.unit_id}: evidence must be an EvidenceClass")

        if not isinstance(self.blocks, tuple) or not self.blocks:
            raise TranslationUnitError(f"unit {self.unit_id}: blocks must be a non-empty tuple")
        for block in self.blocks:
            if not isinstance(block, BasicBlock):
                raise TranslationUnitError(f"unit {self.unit_id}: block membership must be BasicBlock")
        ordered_blocks = _canonical_blocks(self.blocks, self.entry_address)
        object.__setattr__(self, "blocks", ordered_blocks)

        block_ids = [block.id for block in self.blocks]
        if len(set(block_ids)) != len(block_ids):
            raise TranslationUnitError(f"unit {self.unit_id}: duplicate block id in translation unit")
        block_entries = [block.entry_address for block in self.blocks]
        if len(set(block_entries)) != len(block_entries):
            raise TranslationUnitError(f"unit {self.unit_id}: duplicate block entry address in translation unit")
        owned_blocks = set(block_ids)

        if not isinstance(self.call_edges, tuple):
            raise TranslationUnitError(f"unit {self.unit_id}: call_edges must be a tuple")
        for edge in self.call_edges:
            if not isinstance(edge, CallGraphEdge):
                raise TranslationUnitError(f"unit {self.unit_id}: call edge membership must be CallGraphEdge")
            if edge.caller != self.function_id:
                raise TranslationUnitError(f"unit {self.unit_id}: call edge caller {edge.caller} is not this function")
            if edge.call_site_block not in owned_blocks:
                raise TranslationUnitError(
                    f"unit {self.unit_id}: call edge site block {edge.call_site_block} is not owned by this unit"
                )
        object.__setattr__(self, "call_edges", tuple(sorted(self.call_edges, key=_edge_order_key)))

        if not isinstance(self.direct_callees, tuple) or len(set(self.direct_callees)) != len(self.direct_callees):
            raise TranslationUnitError(f"unit {self.unit_id}: direct_callees must be a tuple of unique ids")
        for callee in self.direct_callees:
            _tu_id(callee, f"unit {self.unit_id} direct callee")
        resolved_callees = {edge.callee for edge in self.call_edges if edge.kind is CallEdgeKind.INTERNAL_DIRECT}
        if resolved_callees != set(self.direct_callees):
            raise TranslationUnitError(
                f"unit {self.unit_id}: direct_callees {sorted(self.direct_callees)} disagree with resolved "
                f"call edges {sorted(resolved_callees)}"
            )

        if not isinstance(self.unresolved_call_sites, tuple):
            raise TranslationUnitError(f"unit {self.unit_id}: unresolved_call_sites must be a tuple")
        for site in self.unresolved_call_sites:
            if not isinstance(site, UnresolvedSite):
                raise TranslationUnitError(f"unit {self.unit_id}: unresolved call site membership must be UnresolvedSite")
            if site.block_id not in owned_blocks:
                raise TranslationUnitError(
                    f"unit {self.unit_id}: unresolved call site block {site.block_id} is not owned by this unit"
                )
        object.__setattr__(
            self, "unresolved_call_sites", tuple(sorted(self.unresolved_call_sites, key=_site_order_key))
        )

        if not isinstance(self.unresolved_jump_sites, tuple):
            raise TranslationUnitError(f"unit {self.unit_id}: unresolved_jump_sites must be a tuple")
        for site in self.unresolved_jump_sites:
            if not isinstance(site, UnresolvedSite):
                raise TranslationUnitError(f"unit {self.unit_id}: unresolved jump site membership must be UnresolvedSite")
            if site.block_id not in owned_blocks:
                raise TranslationUnitError(
                    f"unit {self.unit_id}: unresolved jump site block {site.block_id} is not owned by this unit"
                )
        object.__setattr__(
            self, "unresolved_jump_sites", tuple(sorted(self.unresolved_jump_sites, key=_site_order_key))
        )

        if not isinstance(self.entry_sources, tuple) or len(set(self.entry_sources)) != len(self.entry_sources):
            raise TranslationUnitError(f"unit {self.unit_id}: entry_sources must be a tuple of unique strings")
        for source in self.entry_sources:
            if not isinstance(source, str) or not source:
                raise TranslationUnitError(f"unit {self.unit_id}: entry_sources must contain non-empty strings")

        if not isinstance(self.provenance, tuple):
            raise TranslationUnitError(f"unit {self.unit_id}: provenance must be a tuple")
        for basis in self.provenance:
            if not isinstance(basis, EntryBasis):
                raise TranslationUnitError(f"unit {self.unit_id}: provenance membership must be EntryBasis")
        object.__setattr__(self, "provenance", tuple(sorted(self.provenance, key=_basis_order_key)))

    def instructions(self) -> tuple:
        return tuple(instruction for block in self.blocks for instruction in block.instructions)

    def block(self, block_id: str) -> BasicBlock:
        for block in self.blocks:
            if block.id == block_id:
                return block
        raise TranslationUnitError(f"unit {self.unit_id}: unknown block {block_id}")

    def to_document(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "function_id": self.function_id,
            "entry_address": self.entry_address,
            "evidence": self.evidence.value,
            "entry_sources": list(self.entry_sources),
            "provenance": [basis.to_document() for basis in self.provenance],
            "direct_callees": list(sorted(self.direct_callees)),
            "blocks": [block.to_document() for block in self.blocks],
            "call_edges": [edge.to_document() for edge in self.call_edges],
            "unresolved_call_sites": [site.to_document() for site in self.unresolved_call_sites],
            "unresolved_jump_sites": [site.to_document() for site in self.unresolved_jump_sites],
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "TranslationUnit":
        try:
            _tu_object(document, "translation unit")
            _tu_keys(document, {"unit_id", "function_id", "entry_address", "blocks"}, "translation unit")
            if not isinstance(document["blocks"], list) or not document["blocks"]:
                raise TranslationUnitError("translation unit.blocks must be a non-empty list")
            return cls(
                unit_id=document["unit_id"],
                function_id=document["function_id"],
                entry_address=document["entry_address"],
                blocks=tuple(BasicBlock.from_document(item) for item in document["blocks"]),
                call_edges=tuple(CallGraphEdge.from_document(item) for item in document.get("call_edges", [])),
                direct_callees=tuple(document.get("direct_callees", [])),
                unresolved_call_sites=tuple(
                    UnresolvedSite.from_document(item) for item in document.get("unresolved_call_sites", [])
                ),
                unresolved_jump_sites=tuple(
                    UnresolvedSite.from_document(item) for item in document.get("unresolved_jump_sites", [])
                ),
                evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
                entry_sources=tuple(document.get("entry_sources", [])),
                provenance=tuple(_parse_basis(item) for item in document.get("provenance", [])),
            )
        except (ProgramModelError, CallGraphError) as exc:
            raise TranslationUnitError(str(exc)) from exc


class TranslationUnitSet:
    """A validated, deterministic set of translation units over one program.

    Construction validates immediately. Units are ordered by
    `(entry_address, function_id)`; residual evidence that belongs to no unit is
    retained explicitly.
    """

    def __init__(
        self,
        source: ProgramSource,
        units: Iterable[TranslationUnit],
        *,
        entry_unit: str | None = None,
        shared_blocks: Iterable[SharedBlock] = (),
        suppressed_entries: Iterable[SuppressedEntry] = (),
        unowned_blocks: Iterable[str] = (),
        external_direct_call_targets: Iterable[ExternalDirectCallTarget] = (),
        unowned_control_flow: Iterable[UnresolvedSite] = (),
    ) -> None:
        if not isinstance(source, ProgramSource):
            raise TranslationUnitError("source must be a ProgramSource")
        self.source = source
        self.units = tuple(sorted(units, key=lambda unit: (unit.entry_address, unit.function_id)))
        self.entry_unit = entry_unit
        self.shared_blocks = tuple(sorted(shared_blocks, key=lambda item: item.block_id))
        self.suppressed_entries = tuple(sorted(suppressed_entries, key=lambda item: item.address))
        self.unowned_blocks = tuple(sorted(unowned_blocks))
        self.external_direct_call_targets = tuple(sorted(external_direct_call_targets, key=lambda item: item.address))
        self.unowned_control_flow = tuple(sorted(unowned_control_flow, key=_site_order_key))
        self._unit_by_function: dict[str, TranslationUnit] = {}
        self._unit_by_id: dict[str, TranslationUnit] = {}
        self.validate()

    def validate(self) -> None:
        if not self.units:
            raise TranslationUnitError("translation unit set must contain at least one unit")

        width = self.source.address_width_bits
        self._unit_by_function = {}
        self._unit_by_id = {}
        entry_addresses: set[int] = set()
        owned_blocks: dict[str, str] = {}
        for unit in self.units:
            if not isinstance(unit, TranslationUnit):
                raise TranslationUnitError("units must be TranslationUnit instances")
            if unit.unit_id in self._unit_by_id:
                raise TranslationUnitError(f"duplicate translation unit id {unit.unit_id}")
            if unit.function_id in self._unit_by_function:
                raise TranslationUnitError(f"duplicate function id {unit.function_id}")
            if unit.entry_address in entry_addresses:
                raise TranslationUnitError(f"duplicate translation unit entry address 0x{unit.entry_address:x}")
            if width is not None and unit.entry_address >= (1 << width):
                raise TranslationUnitError(
                    f"unit {unit.unit_id}: entry address exceeds the declared {width}-bit width"
                )
            self._unit_by_id[unit.unit_id] = unit
            self._unit_by_function[unit.function_id] = unit
            entry_addresses.add(unit.entry_address)
            for block in unit.blocks:
                if block.id in owned_blocks:
                    raise TranslationUnitError(
                        f"block {block.id} is owned by units {owned_blocks[block.id]} and {unit.unit_id}"
                    )
                owned_blocks[block.id] = unit.unit_id

        if self.entry_unit is not None:
            _tu_id(self.entry_unit, "entry_unit")
            if self.entry_unit not in self._unit_by_id:
                raise TranslationUnitError(f"entry_unit {self.entry_unit} is not a translation unit")

        if len(set(self.unowned_blocks)) != len(self.unowned_blocks):
            raise TranslationUnitError("unowned_blocks must not contain duplicates")
        for block_id in self.unowned_blocks:
            _tu_id(block_id, "unowned block")
            if block_id in owned_blocks:
                raise TranslationUnitError(f"unowned block {block_id} is owned by unit {owned_blocks[block_id]}")

        for shared in self.shared_blocks:
            if not isinstance(shared, SharedBlock):
                raise TranslationUnitError("shared_blocks must contain SharedBlock instances")
            if shared.block_id not in owned_blocks:
                raise TranslationUnitError(f"shared block {shared.block_id} is not owned by any unit")
            if shared.owner not in self._unit_by_function:
                raise TranslationUnitError(f"shared block {shared.block_id} owner {shared.owner} is not a unit")
            for also in shared.also_reachable_from:
                if also not in self._unit_by_function:
                    raise TranslationUnitError(f"shared block {shared.block_id} references unknown unit {also}")

        for entry in self.suppressed_entries:
            if not isinstance(entry, SuppressedEntry):
                raise TranslationUnitError("suppressed_entries must contain SuppressedEntry instances")
            if entry.owner is not None and entry.owner not in self._unit_by_function:
                raise TranslationUnitError(f"suppressed entry owner {entry.owner} is not a unit")

        for target in self.external_direct_call_targets:
            if not isinstance(target, ExternalDirectCallTarget):
                raise TranslationUnitError("external_direct_call_targets must contain ExternalDirectCallTarget instances")
            if target.address in entry_addresses:
                raise TranslationUnitError(
                    f"external direct-call target 0x{target.address:x} matches a translation unit entry"
                )

        for site in self.unowned_control_flow:
            if not isinstance(site, UnresolvedSite):
                raise TranslationUnitError("unowned_control_flow must contain UnresolvedSite instances")
            if site.block_id in owned_blocks:
                raise TranslationUnitError(
                    f"unowned control-flow site block {site.block_id} is owned by unit {owned_blocks[site.block_id]}"
                )

    def ordered_units(self) -> tuple[TranslationUnit, ...]:
        return self.units

    def unit_for(self, function_id: str) -> TranslationUnit:
        try:
            return self._unit_by_function[function_id]
        except KeyError as exc:
            raise TranslationUnitError(f"unknown function {function_id}") from exc

    def unit_by_id(self, unit_id: str) -> TranslationUnit:
        try:
            return self._unit_by_id[unit_id]
        except KeyError as exc:
            raise TranslationUnitError(f"unknown translation unit {unit_id}") from exc

    def function_ids(self) -> tuple[str, ...]:
        return tuple(unit.function_id for unit in self.units)

    def to_document(self) -> dict[str, Any]:
        return {
            "translation_unit_set_version": TRANSLATION_UNIT_VERSION,
            "source": self.source.to_document(),
            "entry_unit": self.entry_unit,
            "units": [unit.to_document() for unit in self.units],
            "shared_blocks": [item.to_document() for item in self.shared_blocks],
            "suppressed_entries": [item.to_document() for item in self.suppressed_entries],
            "unowned_blocks": list(self.unowned_blocks),
            "external_direct_call_targets": [item.to_document() for item in self.external_direct_call_targets],
            "unowned_control_flow": [item.to_document() for item in self.unowned_control_flow],
        }

    def serialize(self) -> bytes:
        return (canonical_json(self.to_document()) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return hashlib.sha256(self.serialize()).hexdigest()

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "TranslationUnitSet":
        try:
            _tu_object(document, "translation unit set")
            _tu_keys(
                document,
                {"translation_unit_set_version", "source", "units"},
                "translation unit set",
            )
            version = document["translation_unit_set_version"]
            if version != TRANSLATION_UNIT_VERSION:
                raise TranslationUnitError(f"unsupported translation_unit_set_version {version!r}")
            if not isinstance(document["units"], list) or not document["units"]:
                raise TranslationUnitError("translation unit set.units must be a non-empty list")
            return cls(
                source=ProgramSource.from_document(document["source"]),
                units=tuple(TranslationUnit.from_document(item) for item in document["units"]),
                entry_unit=document.get("entry_unit"),
                shared_blocks=tuple(_parse_shared(item) for item in document.get("shared_blocks", [])),
                suppressed_entries=tuple(_parse_suppressed(item) for item in document.get("suppressed_entries", [])),
                unowned_blocks=tuple(document.get("unowned_blocks", [])),
                external_direct_call_targets=tuple(_parse_external(item) for item in document.get("external_direct_call_targets", [])),
                unowned_control_flow=tuple(
                    UnresolvedSite.from_document(item) for item in document.get("unowned_control_flow", [])
                ),
            )
        except (ProgramModelError, CallGraphError) as exc:
            raise TranslationUnitError(str(exc)) from exc

    @classmethod
    def deserialize(cls, data: bytes | str) -> "TranslationUnitSet":
        import json

        try:
            document = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise TranslationUnitError(f"invalid translation unit JSON: {exc}") from exc
        return cls.from_document(document)


def _validate_call_graph(cfg, functions: tuple[FunctionUnit, ...], call_graph: CallGraph) -> None:
    if not isinstance(call_graph, CallGraph):
        raise TranslationUnitError("call_graph must be a CallGraph")
    if call_graph.source is not None and call_graph.source != cfg.source:
        raise TranslationUnitError("call_graph source disagrees with the CFG source")
    function_ids = {function.id for function in functions}
    node_ids = {node.function_id for node in call_graph.nodes}
    if node_ids != function_ids:
        raise TranslationUnitError(
            f"call_graph nodes {sorted(node_ids)} disagree with discovered functions {sorted(function_ids)}"
        )
    nodes = {node.function_id: node for node in call_graph.nodes}
    for function in functions:
        node = nodes[function.id]
        if node.entry_address != function.entry_address:
            raise TranslationUnitError(f"function {function.id}: call_graph entry address disagrees")
        if node.evidence is not function.evidence:
            raise TranslationUnitError(f"function {function.id}: call_graph evidence disagrees")


def _block_owner(functions: tuple[FunctionUnit, ...]) -> dict[str, str]:
    owner: dict[str, str] = {}
    for function in functions:
        for block in function.blocks:
            if block.id in owner:
                raise TranslationUnitError(f"block {block.id} is owned by more than one discovered function")
            owner[block.id] = function.id
    return owner


def build_translation_units_from(
    cfg,
    functions: Iterable[FunctionUnit],
    *,
    provenance: Mapping[str, tuple[EntryBasis, ...]] | None = None,
    suppressed_entries: Iterable[SuppressedEntry] = (),
    shared_blocks: Iterable[SharedBlock] = (),
    unowned_blocks: Iterable[str] = (),
    external_direct_call_targets: Iterable[ExternalDirectCallTarget] = (),
    entry_function_id: str,
    call_graph: CallGraph | None = None,
) -> TranslationUnitSet:
    """Package discovered functions plus CFG/call-graph evidence into units."""
    from openrecomp.cfg import ControlFlowGraph

    if not isinstance(cfg, ControlFlowGraph):
        raise TranslationUnitError("cfg must be a ControlFlowGraph")
    functions = tuple(sorted(functions, key=lambda function: (function.entry_address, function.id)))
    if not functions:
        raise TranslationUnitError("at least one discovered function is required")

    if call_graph is None:
        try:
            call_graph = build_call_graph_from(
                cfg,
                functions,
                entry_function_id=entry_function_id,
                external_direct_call_targets=external_direct_call_targets,
            )
        except CallGraphError as exc:
            raise TranslationUnitError(str(exc)) from exc
    _validate_call_graph(cfg, functions, call_graph)

    owner = _block_owner(functions)
    provenance = {key: tuple(value) for key, value in (provenance or {}).items()}

    jump_by_function: dict[str, list[UnresolvedSite]] = {function.id: [] for function in functions}
    unowned_control_flow: list[UnresolvedSite] = []
    for site in cfg.unresolved_jump_sites:
        block_owner = owner.get(site.block_id)
        if block_owner is None:
            unowned_control_flow.append(site)
        else:
            jump_by_function[block_owner].append(site)
    for site in cfg.unresolved_call_sites:
        if owner.get(site.block_id) is None:
            unowned_control_flow.append(site)

    units: list[TranslationUnit] = []
    for function in functions:
        call_edges = tuple(call_graph.edges_from(function.id))
        unit = TranslationUnit(
            unit_id=f"tu_{function.id}",
            function_id=function.id,
            entry_address=function.entry_address,
            blocks=function.blocks,
            call_edges=call_edges,
            direct_callees=function.direct_callees,
            unresolved_call_sites=function.unresolved_call_sites,
            unresolved_jump_sites=tuple(jump_by_function[function.id]),
            evidence=function.evidence,
            entry_sources=function.entry_sources,
            provenance=provenance.get(function.id, ()),
        )
        units.append(unit)

    entry_unit = f"tu_{entry_function_id}"
    return TranslationUnitSet(
        cfg.source,
        units,
        entry_unit=entry_unit,
        shared_blocks=shared_blocks,
        suppressed_entries=suppressed_entries,
        unowned_blocks=unowned_blocks,
        external_direct_call_targets=external_direct_call_targets,
        unowned_control_flow=unowned_control_flow,
    )


def build_translation_units(
    discovery: FunctionDiscoveryResult,
    *,
    call_graph: CallGraph | None = None,
) -> TranslationUnitSet:
    """Build the deterministic translation-unit set for a P2-03 discovery result.

    The P2-04 call graph is reused when supplied, otherwise it is recovered from
    the same discovery result. No instruction is lowered.
    """
    if not isinstance(discovery, FunctionDiscoveryResult):
        raise TranslationUnitError("build_translation_units requires a FunctionDiscoveryResult")
    if call_graph is None:
        try:
            call_graph = build_call_graph(discovery)
        except CallGraphError as exc:
            raise TranslationUnitError(str(exc)) from exc
    return build_translation_units_from(
        discovery.cfg,
        discovery.functions,
        provenance=discovery.provenance,
        suppressed_entries=discovery.suppressed_entries,
        shared_blocks=discovery.shared_blocks,
        unowned_blocks=discovery.unowned_blocks,
        external_direct_call_targets=discovery.external_direct_call_targets,
        entry_function_id=discovery.entry_function_id,
        call_graph=call_graph,
    )
