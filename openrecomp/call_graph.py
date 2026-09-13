"""OpenRecomp deterministic architecture-neutral call-graph recovery (P2-04).

`OpenRecomp Phase 2` stage P2-04 deliverable. This module converts the P2-03
discovered `FunctionUnit` set plus the P2-02 `ControlFlowGraph` direct-call-site
evidence into an explicit, validated whole-program **direct** call graph.

It reuses the shared types unchanged (`FunctionUnit`, `ProgramModel`, `CallSite`,
`UnresolvedSite`, `EvidenceClass`, `FunctionDiscoveryResult`) and does not
reconstruct CFGs, re-discover functions or decode instructions.

It distinguishes:

* `INTERNAL_DIRECT` — caller and callee are both discovered functions;
* `EXTERNAL_DIRECT` — a direct target with no discovered function in the region;
* `UNRESOLVED_INDIRECT` — an indirect call whose target is not resolved.

Indirect jumps are deliberately **excluded**: the call graph records calls only.
Indirect targets are never guessed. Recursion and mutual recursion are reported
deterministically. Evidence is conservative and survives serialization.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from openrecomp.cfg import ControlFlowGraph, combine_evidence
from openrecomp.functions import (
    ExternalDirectCallTarget,
    FunctionDiscoveryResult,
    FunctionDiscoveryError,
)
from openrecomp.program_model import (
    EvidenceClass,
    FunctionUnit,
    ProgramSource,
    _require_id,
    _require_address,
    _require_keys,
    _require_object,
    canonical_json,
)

CALL_GRAPH_VERSION = "1.0.0"


class CallGraphError(ValueError):
    """Raised when call-graph input is invalid or inconsistent."""


class CallEdgeKind(str, Enum):
    """Architecture-neutral classification of one call-graph edge."""

    INTERNAL_DIRECT = "INTERNAL_DIRECT"
    EXTERNAL_DIRECT = "EXTERNAL_DIRECT"
    UNRESOLVED_INDIRECT = "UNRESOLVED_INDIRECT"


@dataclass(frozen=True)
class CallGraphNode:
    """One discovered function as a call-graph node (stable P2-03 identity)."""

    function_id: str
    entry_address: int
    evidence: EvidenceClass = EvidenceClass.CANDIDATE

    def __post_init__(self) -> None:
        _require_id(self.function_id, "call-graph node.function_id")
        _require_address(self.entry_address, "call-graph node.entry_address")
        if not isinstance(self.evidence, EvidenceClass):
            raise CallGraphError(f"node {self.function_id}: evidence must be an EvidenceClass")

    def to_document(self) -> dict[str, Any]:
        return {"function": self.function_id, "entry_address": self.entry_address, "evidence": self.evidence.value}

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "CallGraphNode":
        _require_object(document, "call-graph node")
        _require_keys(document, {"function", "entry_address"}, "call-graph node")
        return cls(
            function_id=document["function"],
            entry_address=document["entry_address"],
            evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
        )


@dataclass(frozen=True)
class CallGraphEdge:
    """One call edge, identified by the exact calling site that produced it."""

    kind: CallEdgeKind
    caller: str
    call_site_block: str
    call_site_address: int
    call_site_op: str
    evidence: EvidenceClass = EvidenceClass.CANDIDATE
    callee: str | None = None
    target_address: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CallEdgeKind):
            raise CallGraphError(f"edge.kind must be a CallEdgeKind, got {self.kind!r}")
        _require_id(self.caller, "edge.caller")
        _require_id(self.call_site_block, "edge.call_site_block")
        _require_address(self.call_site_address, "edge.call_site_address")
        if not isinstance(self.call_site_op, str) or not self.call_site_op:
            raise CallGraphError("edge.call_site_op must be a non-empty string")
        if not isinstance(self.evidence, EvidenceClass):
            raise CallGraphError("edge.evidence must be an EvidenceClass")
        if self.callee is not None:
            _require_id(self.callee, "edge.callee")
        if self.target_address is not None:
            _require_address(self.target_address, "edge.target_address")
        if self.kind is CallEdgeKind.INTERNAL_DIRECT:
            if self.callee is None or self.target_address is not None:
                raise CallGraphError("INTERNAL_DIRECT edge needs a callee and no target_address")
        elif self.kind is CallEdgeKind.EXTERNAL_DIRECT:
            if self.callee is not None or self.target_address is None:
                raise CallGraphError("EXTERNAL_DIRECT edge needs a target_address and no callee")
        elif self.kind is CallEdgeKind.UNRESOLVED_INDIRECT:
            if self.callee is not None or self.target_address is not None:
                raise CallGraphError("UNRESOLVED_INDIRECT edge must not carry a callee or target_address")

    def identity(self) -> tuple:
        return (
            self.kind.value,
            self.caller,
            self.call_site_block,
            self.call_site_address,
            self.callee,
            self.target_address,
        )

    def to_document(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "caller": self.caller,
            "call_site": {"block": self.call_site_block, "address": self.call_site_address, "op": self.call_site_op},
            "callee": self.callee,
            "target_address": self.target_address,
            "evidence": self.evidence.value,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "CallGraphEdge":
        _require_object(document, "call-graph edge")
        _require_keys(document, {"kind", "caller", "call_site"}, "call-graph edge")
        call_site = document["call_site"]
        _require_object(call_site, "call-graph edge.call_site")
        _require_keys(call_site, {"block", "address", "op"}, "call-graph edge.call_site")
        return cls(
            kind=CallEdgeKind(document["kind"]),
            caller=document["caller"],
            call_site_block=call_site["block"],
            call_site_address=call_site["address"],
            call_site_op=call_site["op"],
            evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
            callee=document.get("callee"),
            target_address=document.get("target_address"),
        )


class CallGraph:
    """A validated, deterministic whole-program direct call graph."""

    def __init__(
        self,
        nodes: Iterable[CallGraphNode],
        edges: Iterable[CallGraphEdge],
        *,
        entry_function: str | None = None,
        function_units: Mapping[str, FunctionUnit] | None = None,
        source: ProgramSource | None = None,
    ) -> None:
        self.nodes = tuple(nodes)
        self.edges = tuple(edges)
        self.entry_function = entry_function
        self.function_units = dict(function_units) if function_units is not None else None
        self.source = source
        self._node_by_id: dict[str, CallGraphNode] = {}
        self._edges_by_caller: dict[str, list[CallGraphEdge]] = {}
        self._edges_by_callee: dict[str, list[CallGraphEdge]] = {}
        self.validate()

    def validate(self) -> None:
        self._node_by_id = {}
        entry_addresses: set[int] = set()
        for node in self.nodes:
            if not isinstance(node, CallGraphNode):
                raise CallGraphError("nodes must be CallGraphNode instances")
            if node.function_id in self._node_by_id:
                raise CallGraphError(f"duplicate call-graph node identity {node.function_id}")
            if node.entry_address in entry_addresses:
                raise CallGraphError(f"duplicate call-graph node entry address 0x{node.entry_address:x}")
            self._node_by_id[node.function_id] = node
            entry_addresses.add(node.entry_address)
        if not self.nodes:
            raise CallGraphError("call graph must contain at least one node")

        self.nodes = tuple(sorted(self.nodes, key=lambda node: (node.entry_address, node.function_id)))

        if self.entry_function is not None:
            _require_id(self.entry_function, "entry_function")
            if self.entry_function not in self._node_by_id:
                raise CallGraphError(f"entry_function {self.entry_function} is not a call-graph node")

        if self.function_units is not None:
            if set(self.function_units) != set(self._node_by_id):
                raise CallGraphError("function_units keys must match call-graph node ids")
            for node in self.nodes:
                function = self.function_units[node.function_id]
                if not isinstance(function, FunctionUnit):
                    raise CallGraphError(f"function_units[{node.function_id}] must be a FunctionUnit")
                if function.entry_address != node.entry_address:
                    raise CallGraphError(f"node {node.function_id}: entry address disagrees with the function unit")
                if function.evidence is not node.evidence:
                    raise CallGraphError(f"node {node.function_id}: evidence disagrees with the function unit")

        seen: set[tuple] = set()
        internal_callees: dict[str, set[str]] = {node.function_id: set() for node in self.nodes}
        for edge in self.edges:
            if not isinstance(edge, CallGraphEdge):
                raise CallGraphError("edges must be CallGraphEdge instances")
            if edge.caller not in self._node_by_id:
                raise CallGraphError(f"edge caller {edge.caller} is not a call-graph node")
            if edge.kind is CallEdgeKind.INTERNAL_DIRECT:
                if edge.callee not in self._node_by_id:
                    raise CallGraphError(f"internal edge callee {edge.callee} is not a call-graph node")
                internal_callees[edge.caller].add(edge.callee)
            elif edge.kind is CallEdgeKind.EXTERNAL_DIRECT:
                if edge.target_address in entry_addresses:
                    raise CallGraphError(f"external edge target 0x{edge.target_address:x} matches a call-graph node entry")
            key = edge.identity()
            if key in seen:
                raise CallGraphError(f"duplicate call-graph edge {key}")
            seen.add(key)

        self.edges = tuple(
            sorted(
                self.edges,
                key=lambda edge: (
                    edge.caller,
                    edge.call_site_address,
                    edge.kind.value,
                    edge.callee or "",
                    edge.target_address if edge.target_address is not None else -1,
                ),
            )
        )

        self._edges_by_caller = {node.function_id: [] for node in self.nodes}
        self._edges_by_callee = {node.function_id: [] for node in self.nodes}
        for edge in self.edges:
            self._edges_by_caller[edge.caller].append(edge)
            if edge.kind is CallEdgeKind.INTERNAL_DIRECT and edge.callee is not None:
                self._edges_by_callee[edge.callee].append(edge)

        if self.function_units is not None:
            for node in self.nodes:
                function = self.function_units[node.function_id]
                if set(function.direct_callees) != internal_callees[node.function_id]:
                    raise CallGraphError(
                        f"function {node.function_id} direct_callees {sorted(function.direct_callees)} "
                        f"disagree with recovered direct-call evidence {sorted(internal_callees[node.function_id])}"
                    )

    def node(self, function_id: str) -> CallGraphNode:
        try:
            return self._node_by_id[function_id]
        except KeyError as exc:
            raise CallGraphError(f"unknown call-graph node {function_id}") from exc

    def edges_from(self, function_id: str) -> tuple[CallGraphEdge, ...]:
        if function_id not in self._edges_by_caller:
            raise CallGraphError(f"unknown call-graph node {function_id}")
        return tuple(self._edges_by_caller[function_id])

    def edges_to(self, function_id: str) -> tuple[CallGraphEdge, ...]:
        if function_id not in self._edges_by_callee:
            raise CallGraphError(f"unknown call-graph node {function_id}")
        return tuple(self._edges_by_callee[function_id])

    def internal_edges(self) -> tuple[CallGraphEdge, ...]:
        return tuple(edge for edge in self.edges if edge.kind is CallEdgeKind.INTERNAL_DIRECT)

    def external_edges(self) -> tuple[CallGraphEdge, ...]:
        return tuple(edge for edge in self.edges if edge.kind is CallEdgeKind.EXTERNAL_DIRECT)

    def unresolved_edges(self) -> tuple[CallGraphEdge, ...]:
        return tuple(edge for edge in self.edges if edge.kind is CallEdgeKind.UNRESOLVED_INDIRECT)

    def callees(self, function_id: str) -> tuple[str, ...]:
        return tuple(sorted({edge.callee for edge in self.edges_from(function_id) if edge.kind is CallEdgeKind.INTERNAL_DIRECT}))

    def recursive_functions(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                edge.caller
                for edge in self.internal_edges()
                if edge.callee == edge.caller
            )
        )

    def strongly_connected_components(self) -> tuple[tuple[str, ...], ...]:
        adjacency: dict[str, list[str]] = {node.function_id: [] for node in self.nodes}
        for edge in self.internal_edges():
            adjacency[edge.caller].append(edge.callee)
        for key in adjacency:
            adjacency[key] = sorted(set(adjacency[key]))

        visited: set[str] = set()
        finish: list[str] = []
        for root in [node.function_id for node in self.nodes]:
            if root in visited:
                continue
            visited.add(root)
            stack: list[tuple[str, int]] = [(root, 0)]
            while stack:
                current, index = stack[-1]
                if index < len(adjacency[current]):
                    target = adjacency[current][index]
                    stack[-1] = (current, index + 1)
                    if target not in visited:
                        visited.add(target)
                        stack.append((target, 0))
                else:
                    finish.append(current)
                    stack.pop()

        reverse: dict[str, list[str]] = {node.function_id: [] for node in self.nodes}
        for source, targets in adjacency.items():
            for target in targets:
                reverse[target].append(source)
        for key in reverse:
            reverse[key] = sorted(set(reverse[key]))

        components: list[tuple[str, ...]] = []
        assigned: set[str] = set()
        for root in reversed(finish):
            if root in assigned:
                continue
            assigned.add(root)
            component: list[str] = []
            stack = [root]
            while stack:
                current = stack.pop()
                component.append(current)
                for previous in reverse[current]:
                    if previous not in assigned:
                        assigned.add(previous)
                        stack.append(previous)
            components.append(tuple(sorted(component)))
        return tuple(sorted(components))

    def mutual_recursion_components(self) -> tuple[tuple[str, ...], ...]:
        return tuple(sorted(component for component in self.strongly_connected_components() if len(component) > 1))

    def to_document(self) -> dict[str, Any]:
        return {
            "call_graph_version": CALL_GRAPH_VERSION,
            "entry_function": self.entry_function,
            "nodes": [node.to_document() for node in self.nodes],
            "edges": [edge.to_document() for edge in self.edges],
            "recursive_functions": list(self.recursive_functions()),
            "mutual_recursion_components": [list(component) for component in self.mutual_recursion_components()],
        }

    def serialize(self) -> bytes:
        return (canonical_json(self.to_document()) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return hashlib.sha256(self.serialize()).hexdigest()

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "CallGraph":
        _require_object(document, "call graph")
        _require_keys(document, {"call_graph_version", "nodes", "edges"}, "call graph")
        if document["call_graph_version"] != CALL_GRAPH_VERSION:
            raise CallGraphError(f"unsupported call_graph_version {document['call_graph_version']!r}")
        if not isinstance(document["nodes"], list) or not document["nodes"]:
            raise CallGraphError("call graph nodes must be a non-empty list")
        return cls(
            nodes=tuple(CallGraphNode.from_document(item) for item in document["nodes"]),
            edges=tuple(CallGraphEdge.from_document(item) for item in document["edges"]),
            entry_function=document.get("entry_function"),
        )

    @classmethod
    def deserialize(cls, data: bytes | str) -> "CallGraph":
        import json

        try:
            document = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CallGraphError(f"invalid call-graph JSON: {exc}") from exc
        return cls.from_document(document)


def _entry_address_index(functions: Iterable[FunctionUnit]) -> dict[int, str]:
    index: dict[int, str] = {}
    for function in functions:
        if function.entry_address in index:
            raise CallGraphError(f"duplicate function entry address 0x{function.entry_address:x}")
        index[function.entry_address] = function.id
    return index


def build_call_graph_from(
    cfg: ControlFlowGraph,
    functions: Iterable[FunctionUnit],
    *,
    entry_function_id: str,
    external_direct_call_targets: Iterable[ExternalDirectCallTarget] = (),
) -> CallGraph:
    """Build a validated call graph from CFG call sites and discovered functions."""
    if not isinstance(cfg, ControlFlowGraph):
        raise CallGraphError("cfg must be a ControlFlowGraph")
    functions = tuple(functions)
    if not functions:
        raise CallGraphError("at least one discovered function is required")

    entry_index = _entry_address_index(functions)
    node_evidence = {function.id: function.evidence for function in functions}
    block_entries = {block.entry_address for block in cfg.blocks}
    block_owner: dict[str, str] = {}
    for function in functions:
        for block in function.blocks:
            if block.id in block_owner:
                raise CallGraphError(f"block {block.id} is owned by more than one function")
            block_owner[block.id] = function.id

    nodes = tuple(CallGraphNode(function.id, function.entry_address, function.evidence) for function in functions)
    edges: list[CallGraphEdge] = []
    derived_callees: dict[str, set[str]] = {function.id: set() for function in functions}

    for site in cfg.direct_call_sites:
        owner = block_owner.get(site.block_id)
        if owner is None:
            raise CallGraphError(
                f"direct call site 0x{site.address:x} in block {site.block_id} is not owned by any discovered function"
            )
        if site.target_address in entry_index:
            callee = entry_index[site.target_address]
            edges.append(
                CallGraphEdge(
                    CallEdgeKind.INTERNAL_DIRECT,
                    owner,
                    site.block_id,
                    site.address,
                    site.op,
                    combine_evidence(site.evidence, node_evidence[callee]),
                    callee=callee,
                )
            )
            derived_callees[owner].add(callee)
        elif site.target_address in block_entries:
            raise CallGraphError(
                f"direct call target 0x{site.target_address:x} is a CFG block boundary but not a discovered function entry"
            )
        else:
            edges.append(
                CallGraphEdge(
                    CallEdgeKind.EXTERNAL_DIRECT,
                    owner,
                    site.block_id,
                    site.address,
                    site.op,
                    site.evidence,
                    target_address=site.target_address,
                )
            )

    for site in cfg.unresolved_call_sites:
        owner = block_owner.get(site.block_id)
        if owner is None:
            raise CallGraphError(
                f"unresolved call site 0x{site.address:x} in block {site.block_id} is not owned by any discovered function"
            )
        edges.append(
            CallGraphEdge(
                CallEdgeKind.UNRESOLVED_INDIRECT,
                owner,
                site.block_id,
                site.address,
                site.op,
                site.evidence,
            )
        )

    external_edges = {edge.target_address for edge in edges if edge.kind is CallEdgeKind.EXTERNAL_DIRECT}
    external_inventory = {target.address for target in external_direct_call_targets}
    if external_edges != external_inventory:
        raise CallGraphError(
            f"external direct-call inventory {sorted(external_inventory)} disagrees with recovered "
            f"external call edges {sorted(external_edges)}"
        )

    return CallGraph(
        nodes,
        edges,
        entry_function=entry_function_id,
        function_units={function.id: function for function in functions},
        source=cfg.source,
    )


def build_call_graph(discovery: FunctionDiscoveryResult) -> CallGraph:
    """Build the whole-program direct call graph for a P2-03 discovery result."""
    if not isinstance(discovery, FunctionDiscoveryResult):
        raise CallGraphError("build_call_graph requires a FunctionDiscoveryResult")
    try:
        return build_call_graph_from(
            discovery.cfg,
            discovery.functions,
            entry_function_id=discovery.entry_function_id,
            external_direct_call_targets=discovery.external_direct_call_targets,
        )
    except FunctionDiscoveryError as exc:
        raise CallGraphError(str(exc)) from exc
