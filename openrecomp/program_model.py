"""OpenRecomp Shared Program Model V1 (architecture-neutral structural layer).

`OpenRecomp Phase 2` stage P2-01 deliverable. This module defines the neutral
structure that sits between the architecture adapter / decoder seam and the
normalized execution IR:

    DecodedInstruction -> BasicBlock -> FunctionUnit -> ProgramModel

Design constraints (see `.openrecomp-phase2/SCOPE.md` and `STAGE_QUEUE.md`):

* architecture-neutral: addresses are arbitrary-precision integers, instruction
  width is optional and per-instruction, control flow is described by neutral
  kinds rather than any ISA's mnemonics or encodings;
* provenance-explicit: every instruction, block and function carries an
  `EvidenceClass` (`PROVEN` or `CANDIDATE`). Heuristic discovery defaults to
  `CANDIDATE`; nothing here silently promotes a discovery to `PROVEN`;
* serialization-stable: `serialize()` produces canonical JSON and
  `deserialize()` reconstructs an equal model, including evidence classes;
* fail-closed: `validate()` rejects structurally inconsistent graphs instead of
  guessing.

The module has no guest-ISA knowledge. ISA-specific decoding belongs to
`adapters/<architecture>.py`; `instruction_from_adapter()` only reads the
already-documented adapter decode shape. Normalized IR V1 and Module Image V1
(`1.0.0`) are frozen and are not referenced or modified here.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator, Mapping

PROGRAM_MODEL_VERSION = "1.0.0"
SCHEMA_PATH_NAME = "schema/openrecomp-program-v1.schema.json"
_ID_PATTERN = re.compile(r"^[A-Za-z_%.][A-Za-z0-9_%.:-]*$")
_ADDRESS_SENTINEL = object()


class ProgramModelError(ValueError):
    """Raised when a program model is structurally invalid or inconsistent."""


class EvidenceClass(str, Enum):
    """Provenance classification for a discovered structural unit.

    `PROVEN` means the unit's structure was established by evidence (e.g. an
    exact decoded direct target in range). `CANDIDATE` means it was discovered
    heuristically and has not been independently established. The shared model
    must never promote a candidate implicitly.
    """

    PROVEN = "PROVEN"
    CANDIDATE = "CANDIDATE"


class InstructionFlow(str, Enum):
    """Architecture-neutral classification of one instruction's control effect."""

    NORMAL = "NORMAL"
    BRANCH = "BRANCH"
    JUMP = "JUMP"
    CALL = "CALL"
    RETURN = "RETURN"
    INDIRECT_JUMP = "INDIRECT_JUMP"
    INDIRECT_CALL = "INDIRECT_CALL"
    TRAP = "TRAP"


class EdgeKind(str, Enum):
    """Architecture-neutral classification of one structural CFG edge."""

    FALLTHROUGH = "FALLTHROUGH"
    BRANCH_TAKEN = "BRANCH_TAKEN"
    BRANCH_NOT_TAKEN = "BRANCH_NOT_TAKEN"
    JUMP = "JUMP"
    CALL_RETURN = "CALL_RETURN"
    RETURN = "RETURN"
    INDIRECT = "INDIRECT"
    TRAP = "TRAP"


def _require_id(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _ID_PATTERN.match(value):
        raise ProgramModelError(f"{where}: {value!r} is not a valid program-model identifier")
    return value


def _require_address(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProgramModelError(f"{where}: address {value!r} must be a non-negative integer")
    return value


def _require_optional_size(value: Any, where: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProgramModelError(f"{where}: size_bytes {value!r} must be a positive integer or null")
    return value


def _require_optional_address(value: Any, where: str) -> int | None:
    if value is None:
        return None
    return _require_address(value, where)


def _canonicalize_metadata(value: Any, where: str) -> Any:
    """Return a deterministic, JSON-safe copy of a metadata value.

    Rejects values that cannot be serialized deterministically (sets, bytes,
    non-string keys, custom objects) so serialization is always reproducible.
    """
    if value is None or isinstance(value, bool) or isinstance(value, int) or isinstance(value, float) or isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return [_canonicalize_metadata(item, f"{where}[]") for item in value]
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProgramModelError(f"{where}: metadata keys must be strings, got {key!r}")
            out[key] = _canonicalize_metadata(item, f"{where}.{key}")
        return out
    raise ProgramModelError(f"{where}: metadata value of type {type(value).__name__} is not serializable")


@dataclass(frozen=True)
class DecodedInstruction:
    """One decoded guest instruction in neutral form.

    `address` is an arbitrary-precision guest address; `size_bytes` is the
    instruction extent where the ISA defines one (nullable); `flow` is the
    neutral control classification; `direct_target` is the proven static target
    where one exists; `unresolved` marks a control transfer whose target cannot
    be established statically.
    """

    address: int
    op: str
    size_bytes: int | None = None
    flow: InstructionFlow = InstructionFlow.NORMAL
    direct_target: int | None = None
    unresolved: bool = False
    evidence: EvidenceClass = EvidenceClass.CANDIDATE
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_address(self.address, "instruction.address")
        if not isinstance(self.op, str) or not self.op:
            raise ProgramModelError("instruction.op must be a non-empty string")
        _require_optional_size(self.size_bytes, "instruction.size_bytes")
        if not isinstance(self.flow, InstructionFlow):
            raise ProgramModelError(f"instruction.flow must be an InstructionFlow, got {self.flow!r}")
        _require_optional_address(self.direct_target, "instruction.direct_target")
        if not isinstance(self.unresolved, bool):
            raise ProgramModelError("instruction.unresolved must be a boolean")
        if not isinstance(self.evidence, EvidenceClass):
            raise ProgramModelError(f"instruction.evidence must be an EvidenceClass, got {self.evidence!r}")
        _canonicalize_metadata(dict(self.metadata), f"instruction@0x{self.address:x}.metadata")
        if self.flow in (InstructionFlow.INDIRECT_JUMP, InstructionFlow.INDIRECT_CALL):
            if self.direct_target is not None:
                raise ProgramModelError("an indirect instruction must not carry a static direct_target")
            if not self.unresolved:
                raise ProgramModelError("an indirect instruction must be marked unresolved")
        if self.flow in (InstructionFlow.BRANCH, InstructionFlow.JUMP, InstructionFlow.CALL) and self.direct_target is None and not self.unresolved:
            raise ProgramModelError(f"a direct {self.flow.value} instruction must carry a direct_target or be unresolved")

    def stable_key(self) -> tuple:
        """Deterministic identity tuple independent of object identity."""
        return (
            self.address,
            self.op,
            self.size_bytes,
            self.flow.value,
            self.direct_target,
            self.unresolved,
            self.evidence.value,
            canonical_json(_canonicalize_metadata(dict(self.metadata), "metadata")),
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.to_document()).encode("utf-8")).hexdigest()

    def to_document(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "op": self.op,
            "size_bytes": self.size_bytes,
            "flow": self.flow.value,
            "direct_target": self.direct_target,
            "unresolved": self.unresolved,
            "evidence": self.evidence.value,
            "metadata": _canonicalize_metadata(dict(self.metadata), "metadata"),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "DecodedInstruction":
        _require_object(document, "instruction")
        _require_keys(document, {"address", "op"}, "instruction")
        return cls(
            address=document["address"],
            op=document["op"],
            size_bytes=document.get("size_bytes"),
            flow=InstructionFlow(document.get("flow", InstructionFlow.NORMAL.value)),
            direct_target=document.get("direct_target"),
            unresolved=document.get("unresolved", False),
            evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
            metadata=document.get("metadata", {}),
        )


def instruction_from_adapter(
    decoded: Mapping[str, Any],
    *,
    flow: InstructionFlow = InstructionFlow.NORMAL,
    unresolved: bool = False,
    direct_target: Any = _ADDRESS_SENTINEL,
    evidence: EvidenceClass = EvidenceClass.CANDIDATE,
    size_bytes: Any = _ADDRESS_SENTINEL,
    metadata: Mapping[str, Any] | None = None,
) -> DecodedInstruction:
    """Build a neutral instruction from the documented adapter `decode` result.

    This is the narrowly scoped integration with the existing adapter seam. It
    reads the adapter's public shape (`address`, `op`, optional `length`,
    optional `target`) and never re-decodes guest bytes. Missing required fields
    fail closed. ISA-specific flow classification stays in the caller.
    """
    if not isinstance(decoded, Mapping):
        raise ProgramModelError("adapter decode result must be a mapping")
    if "address" not in decoded or "op" not in decoded:
        raise ProgramModelError("adapter decode result must provide 'address' and 'op'")

    if direct_target is _ADDRESS_SENTINEL:
        candidate = decoded.get("target")
        direct_target = candidate if isinstance(candidate, int) and not isinstance(candidate, bool) else None
    if size_bytes is _ADDRESS_SENTINEL:
        candidate = decoded.get("length", decoded.get("size_bytes"))
        size_bytes = candidate if isinstance(candidate, int) and not isinstance(candidate, bool) else None

    extra = dict(metadata or {})
    if "adapter_fields" not in extra:
        reserved = {"address", "op", "length", "size_bytes", "target"}
        extra["adapter_fields"] = {
            key: value for key, value in sorted(decoded.items()) if key not in reserved
        }
    return DecodedInstruction(
        address=decoded["address"],
        op=decoded["op"],
        size_bytes=size_bytes,
        flow=flow,
        direct_target=direct_target,
        unresolved=unresolved,
        evidence=evidence,
        metadata=extra,
    )


@dataclass(frozen=True)
class Successor:
    """One outgoing structural edge from a basic block.

    `resolved` distinguishes an edge to a known block from an unresolved
    control transfer. A resolved edge names `target_block` and may record the
    matching `target_address`; an unresolved edge names neither.
    """

    kind: EdgeKind
    target_block: str | None = None
    target_address: int | None = None
    resolved: bool = True
    evidence: EvidenceClass = EvidenceClass.CANDIDATE
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EdgeKind):
            raise ProgramModelError(f"successor.kind must be an EdgeKind, got {self.kind!r}")
        if self.target_block is not None:
            _require_id(self.target_block, "successor.target_block")
        _require_optional_address(self.target_address, "successor.target_address")
        if not isinstance(self.resolved, bool):
            raise ProgramModelError("successor.resolved must be a boolean")
        if not isinstance(self.evidence, EvidenceClass):
            raise ProgramModelError(f"successor.evidence must be an EvidenceClass, got {self.evidence!r}")
        if self.detail is not None and (not isinstance(self.detail, str) or not self.detail):
            raise ProgramModelError("successor.detail must be a non-empty string or null")
        if self.resolved:
            if self.target_block is None:
                raise ProgramModelError("a resolved successor must name a target_block")
        elif self.target_block is not None:
            raise ProgramModelError("an unresolved successor must not name a target_block")

    def to_document(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "target_block": self.target_block,
            "target_address": self.target_address,
            "resolved": self.resolved,
            "evidence": self.evidence.value,
            "detail": self.detail,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "Successor":
        _require_object(document, "successor")
        _require_keys(document, {"kind"}, "successor")
        return cls(
            kind=EdgeKind(document["kind"]),
            target_block=document.get("target_block"),
            target_address=document.get("target_address"),
            resolved=document.get("resolved", True),
            evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
            detail=document.get("detail"),
        )


@dataclass(frozen=True)
class BasicBlock:
    """A maximal, ordered sequence of instructions with explicit successors."""

    id: str
    entry_address: int
    instructions: tuple[DecodedInstruction, ...]
    successors: tuple[Successor, ...] = ()
    evidence: EvidenceClass = EvidenceClass.CANDIDATE

    def __post_init__(self) -> None:
        _require_id(self.id, "block.id")
        _require_address(self.entry_address, "block.entry_address")
        if not isinstance(self.instructions, tuple) or not self.instructions:
            raise ProgramModelError(f"block {self.id}: instructions must be a non-empty tuple")
        for instruction in self.instructions:
            if not isinstance(instruction, DecodedInstruction):
                raise ProgramModelError(f"block {self.id}: instruction membership must be DecodedInstruction")
        if instruction_addresses(self.instructions) != tuple(sorted(instruction_addresses(self.instructions))):
            raise ProgramModelError(f"block {self.id}: instruction addresses must be non-decreasing")
        if self.instructions[0].address != self.entry_address:
            raise ProgramModelError(f"block {self.id}: entry_address must equal the first instruction address")
        if not isinstance(self.successors, tuple):
            raise ProgramModelError(f"block {self.id}: successors must be a tuple")
        for successor in self.successors:
            if not isinstance(successor, Successor):
                raise ProgramModelError(f"block {self.id}: successor membership must be Successor")
        if not isinstance(self.evidence, EvidenceClass):
            raise ProgramModelError(f"block {self.id}: evidence must be an EvidenceClass")
        seen: set[tuple] = set()
        for successor in self.successors:
            key = (successor.kind.value, successor.target_block, successor.target_address, successor.resolved)
            if key in seen:
                raise ProgramModelError(f"block {self.id}: duplicate successor edge {key}")
            seen.add(key)

    @property
    def terminal(self) -> DecodedInstruction:
        return self.instructions[-1]

    def terminal_flow(self) -> InstructionFlow:
        return self.terminal.flow

    def successor_blocks(self) -> tuple[str, ...]:
        return tuple(
            successor.target_block
            for successor in self.successors
            if successor.resolved and successor.target_block is not None
        )

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entry_address": self.entry_address,
            "evidence": self.evidence.value,
            "instructions": [instruction.to_document() for instruction in self.instructions],
            "successors": [successor.to_document() for successor in self._ordered_successors()],
        }

    def _ordered_successors(self) -> tuple[Successor, ...]:
        return tuple(
            sorted(
                self.successors,
                key=lambda item: (item.kind.value, item.target_address if item.target_address is not None else -1, item.target_block or ""),
            )
        )

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "BasicBlock":
        _require_object(document, "block")
        _require_keys(document, {"id", "entry_address", "instructions"}, "block")
        if not isinstance(document["instructions"], list) or not document["instructions"]:
            raise ProgramModelError("block.instructions must be a non-empty list")
        return cls(
            id=document["id"],
            entry_address=document["entry_address"],
            instructions=tuple(DecodedInstruction.from_document(item) for item in document["instructions"]),
            successors=tuple(Successor.from_document(item) for item in document.get("successors", [])),
            evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
        )


@dataclass(frozen=True)
class UnresolvedSite:
    """An unresolved control-flow site recorded at function level."""

    block_id: str
    address: int
    op: str
    reason: str
    evidence: EvidenceClass = EvidenceClass.CANDIDATE

    def __post_init__(self) -> None:
        _require_id(self.block_id, "unresolved_site.block_id")
        _require_address(self.address, "unresolved_site.address")
        if not isinstance(self.op, str) or not self.op:
            raise ProgramModelError("unresolved_site.op must be a non-empty string")
        if not isinstance(self.reason, str) or not self.reason:
            raise ProgramModelError("unresolved_site.reason must be a non-empty string")
        if not isinstance(self.evidence, EvidenceClass):
            raise ProgramModelError("unresolved_site.evidence must be an EvidenceClass")

    def to_document(self) -> dict[str, Any]:
        return {
            "block": self.block_id,
            "address": self.address,
            "op": self.op,
            "reason": self.reason,
            "evidence": self.evidence.value,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "UnresolvedSite":
        _require_object(document, "unresolved_site")
        _require_keys(document, {"block", "address", "op", "reason"}, "unresolved_site")
        return cls(
            block_id=document["block"],
            address=document["address"],
            op=document["op"],
            reason=document["reason"],
            evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
        )


@dataclass(frozen=True)
class FunctionUnit:
    """A recovered or candidate function: an entry, its blocks and call facts.

    `direct_callees` contains only proven direct callee function ids;
    computed/indirect call sites are recorded separately in
    `unresolved_call_sites`. Presence in the model does not imply the function
    is proven; `evidence` carries `CANDIDATE` unless independently established.
    """

    id: str
    entry_address: int
    blocks: tuple[BasicBlock, ...]
    direct_callees: tuple[str, ...] = ()
    unresolved_call_sites: tuple[UnresolvedSite, ...] = ()
    evidence: EvidenceClass = EvidenceClass.CANDIDATE

    def __post_init__(self) -> None:
        _require_id(self.id, "function.id")
        _require_address(self.entry_address, "function.entry_address")
        if not isinstance(self.blocks, tuple) or not self.blocks:
            raise ProgramModelError(f"function {self.id}: blocks must be a non-empty tuple")
        for block in self.blocks:
            if not isinstance(block, BasicBlock):
                raise ProgramModelError(f"function {self.id}: block membership must be BasicBlock")
        if self.blocks[0].entry_address != self.entry_address:
            raise ProgramModelError(f"function {self.id}: first block entry must equal function entry_address")
        if not isinstance(self.direct_callees, tuple) or len(set(self.direct_callees)) != len(self.direct_callees):
            raise ProgramModelError(f"function {self.id}: direct_callees must be a tuple of unique ids")
        for callee in self.direct_callees:
            _require_id(callee, f"function {self.id} direct callee")
        if not isinstance(self.unresolved_call_sites, tuple):
            raise ProgramModelError(f"function {self.id}: unresolved_call_sites must be a tuple")
        for site in self.unresolved_call_sites:
            if not isinstance(site, UnresolvedSite):
                raise ProgramModelError(f"function {self.id}: unresolved site membership must be UnresolvedSite")
        if not isinstance(self.evidence, EvidenceClass):
            raise ProgramModelError(f"function {self.id}: evidence must be an EvidenceClass")

    def ordered_blocks(self) -> tuple[BasicBlock, ...]:
        return tuple(sorted(self.blocks, key=lambda block: (block.entry_address, block.id)))

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entry_address": self.entry_address,
            "evidence": self.evidence.value,
            "direct_callees": list(sorted(self.direct_callees)),
            "unresolved_call_sites": [
                site.to_document() for site in sorted(self.unresolved_call_sites, key=lambda item: (item.address, item.block_id))
            ],
            "blocks": [block.to_document() for block in self.ordered_blocks()],
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "FunctionUnit":
        _require_object(document, "function")
        _require_keys(document, {"id", "entry_address", "blocks"}, "function")
        if not isinstance(document["blocks"], list) or not document["blocks"]:
            raise ProgramModelError("function.blocks must be a non-empty list")
        return cls(
            id=document["id"],
            entry_address=document["entry_address"],
            blocks=tuple(BasicBlock.from_document(item) for item in document["blocks"]),
            direct_callees=tuple(document.get("direct_callees", [])),
            unresolved_call_sites=tuple(UnresolvedSite.from_document(item) for item in document.get("unresolved_call_sites", [])),
            evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
        )


@dataclass(frozen=True)
class ProgramSource:
    """Guest identity and descriptive (not prescriptive) address metadata."""

    architecture: str
    adapter: str | None = None
    address_width_bits: int | None = None
    endianness: str | None = None
    input_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.architecture, str) or not self.architecture:
            raise ProgramModelError("source.architecture must be a non-empty string")
        if self.adapter is not None and (not isinstance(self.adapter, str) or not self.adapter):
            raise ProgramModelError("source.adapter must be a non-empty string or null")
        if self.address_width_bits is not None:
            if isinstance(self.address_width_bits, bool) or not isinstance(self.address_width_bits, int) or self.address_width_bits <= 0:
                raise ProgramModelError("source.address_width_bits must be a positive integer or null")
        if self.endianness is not None and self.endianness not in {"little", "big"}:
            raise ProgramModelError("source.endianness must be 'little', 'big' or null")
        if self.input_sha256 is not None:
            if not isinstance(self.input_sha256, str) or not re.match(r"^[0-9a-f]{64}$", self.input_sha256):
                raise ProgramModelError("source.input_sha256 must be a lowercase 64-character digest or null")

    def to_document(self) -> dict[str, Any]:
        return {
            "architecture": self.architecture,
            "adapter": self.adapter,
            "address_width_bits": self.address_width_bits,
            "endianness": self.endianness,
            "input_sha256": self.input_sha256,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "ProgramSource":
        _require_object(document, "source")
        _require_keys(document, {"architecture"}, "source")
        return cls(
            architecture=document["architecture"],
            adapter=document.get("adapter"),
            address_width_bits=document.get("address_width_bits"),
            endianness=document.get("endianness"),
            input_sha256=document.get("input_sha256"),
        )


class ProgramModel:
    """The shared architecture-neutral program structure.

    Construction validates immediately: an invalid graph raises
    `ProgramModelError` rather than yielding a partially trusted model.
    """

    def __init__(
        self,
        source: ProgramSource,
        functions: tuple[FunctionUnit, ...] | list[FunctionUnit],
        entry_function: str,
    ) -> None:
        self.source = source
        self.functions = tuple(functions)
        self.entry_function = entry_function
        self._functions_by_id: dict[str, FunctionUnit] = {}
        self._blocks_by_id: dict[str, BasicBlock] = {}
        self._function_of_block: dict[str, str] = {}
        self._block_entry_index: dict[int, str] = {}
        self._function_entry_index: dict[int, str] = {}
        self.validate()

    def validate(self) -> None:
        self._functions_by_id = {}
        self._blocks_by_id = {}
        self._function_of_block = {}
        self._block_entry_index = {}
        self._function_entry_index = {}

        if not isinstance(self.source, ProgramSource):
            raise ProgramModelError("source must be a ProgramSource")
        if not self.functions:
            raise ProgramModelError("program model must contain at least one function")
        _require_id(self.entry_function, "entry_function")

        for function in self.functions:
            if function.id in self._functions_by_id:
                raise ProgramModelError(f"duplicate function id {function.id}")
            if function.entry_address in self._function_entry_index:
                raise ProgramModelError(f"duplicate function entry address 0x{function.entry_address:x}")
            self._functions_by_id[function.id] = function
            self._function_entry_index[function.entry_address] = function.id
            for block in function.blocks:
                if block.id in self._blocks_by_id:
                    raise ProgramModelError(f"duplicate block id {block.id}")
                if block.entry_address in self._block_entry_index:
                    raise ProgramModelError(f"duplicate block entry address 0x{block.entry_address:x}")
                self._blocks_by_id[block.id] = block
                self._function_of_block[block.id] = function.id
                self._block_entry_index[block.entry_address] = block.id

        if self.entry_function not in self._functions_by_id:
            raise ProgramModelError(f"entry_function {self.entry_function} is not declared")

        width = self.source.address_width_bits
        for function in self.functions:
            if width is not None and function.entry_address >= (1 << width):
                raise ProgramModelError(f"function {function.id}: entry address exceeds the declared {width}-bit width")
            for block in function.blocks:
                if width is not None and block.entry_address >= (1 << width):
                    raise ProgramModelError(f"block {block.id}: entry address exceeds the declared {width}-bit width")
                self._validate_block(function, block, width)
            for callee in function.direct_callees:
                if callee not in self._functions_by_id:
                    raise ProgramModelError(f"function {function.id}: direct callee {callee} is not declared")
            for site in function.unresolved_call_sites:
                if site.block_id not in self._blocks_by_id:
                    raise ProgramModelError(f"function {function.id}: unresolved call site references unknown block {site.block_id}")
                if self._function_of_block[site.block_id] != function.id:
                    raise ProgramModelError(f"function {function.id}: unresolved call site block {site.block_id} belongs to another function")

        self.predecessor_map()

    def _validate_block(self, function: FunctionUnit, block: BasicBlock, width: int | None) -> None:
        addresses = instruction_addresses(block.instructions)
        if len(set(addresses)) != len(addresses):
            raise ProgramModelError(f"block {block.id}: duplicate instruction address")
        if width is not None:
            for instruction in block.instructions:
                if instruction.address >= (1 << width):
                    raise ProgramModelError(f"block {block.id}: instruction address exceeds the declared {width}-bit width")
                if instruction.direct_target is not None and instruction.direct_target >= (1 << width):
                    raise ProgramModelError(f"block {block.id}: direct target exceeds the declared {width}-bit width")

        for successor in block.successors:
            if successor.resolved:
                if successor.target_block not in self._blocks_by_id:
                    raise ProgramModelError(f"block {block.id}: successor target {successor.target_block} is not declared")
                target = self._blocks_by_id[successor.target_block]
                if successor.target_address is not None and successor.target_address != target.entry_address:
                    raise ProgramModelError(
                        f"block {block.id}: successor target_address 0x{successor.target_address:x} does not match block {target.id}"
                    )
            elif successor.kind in (EdgeKind.RETURN, EdgeKind.TRAP):
                raise ProgramModelError(f"block {block.id}: {successor.kind.value} successor cannot be unresolved")
            elif successor.detail is None:
                raise ProgramModelError(f"block {block.id}: unresolved successor must carry a detail")

        flow = block.terminal_flow()
        kinds = [successor.kind for successor in block.successors]
        if flow in (InstructionFlow.RETURN, InstructionFlow.TRAP):
            if block.successors:
                raise ProgramModelError(f"block {block.id}: {flow.value} block must not have successors")
        elif flow == InstructionFlow.INDIRECT_JUMP:
            if len(block.successors) != 1 or block.successors[0].resolved or block.successors[0].kind != EdgeKind.INDIRECT:
                raise ProgramModelError(f"block {block.id}: INDIRECT_JUMP block needs exactly one unresolved INDIRECT successor")
        elif flow == InstructionFlow.INDIRECT_CALL:
            if kinds != [EdgeKind.CALL_RETURN]:
                raise ProgramModelError(f"block {block.id}: INDIRECT_CALL block needs exactly one CALL_RETURN successor")
        elif flow == InstructionFlow.CALL:
            if kinds != [EdgeKind.CALL_RETURN]:
                raise ProgramModelError(f"block {block.id}: CALL block needs exactly one CALL_RETURN successor")
        elif flow == InstructionFlow.JUMP:
            if len(block.successors) != 1 or block.successors[0].kind != EdgeKind.JUMP:
                raise ProgramModelError(f"block {block.id}: JUMP block needs exactly one JUMP successor")
        elif flow == InstructionFlow.BRANCH:
            if len(block.successors) != 2:
                raise ProgramModelError(f"block {block.id}: BRANCH block needs exactly two successors")
            if sorted(kinds) != sorted([EdgeKind.BRANCH_TAKEN, EdgeKind.BRANCH_NOT_TAKEN]):
                raise ProgramModelError(f"block {block.id}: BRANCH successors must be BRANCH_TAKEN and BRANCH_NOT_TAKEN")
        elif flow == InstructionFlow.NORMAL:
            if len(block.successors) > 1 or (block.successors and block.successors[0].kind != EdgeKind.FALLTHROUGH):
                raise ProgramModelError(f"block {block.id}: NORMAL block may only have a single FALLTHROUGH successor")

    def function(self, function_id: str) -> FunctionUnit:
        try:
            return self._functions_by_id[function_id]
        except KeyError as exc:
            raise ProgramModelError(f"unknown function {function_id}") from exc

    def block(self, block_id: str) -> BasicBlock:
        try:
            return self._blocks_by_id[block_id]
        except KeyError as exc:
            raise ProgramModelError(f"unknown block {block_id}") from exc

    def blocks(self) -> tuple[BasicBlock, ...]:
        return tuple(block for function in self.ordered_functions() for block in function.ordered_blocks())

    def ordered_functions(self) -> tuple[FunctionUnit, ...]:
        return tuple(sorted(self.functions, key=lambda function: (function.entry_address, function.id)))

    def lookup(self, address: int) -> dict[str, Any] | None:
        """Resolve an exact block/function entry address, or return None."""
        _require_address(address, "lookup")
        block_id = self._block_entry_index.get(address)
        if block_id is None:
            return None
        return {"address": address, "function": self._function_of_block[block_id], "block": block_id}

    def predecessor_map(self) -> dict[str, tuple[dict[str, Any], ...]]:
        """Derive predecessors from resolved successors; always consistent."""
        predecessors: dict[str, list[dict[str, Any]]] = {block_id: [] for block_id in self._blocks_by_id}
        for function in self.ordered_functions():
            for block in function.ordered_blocks():
                for successor in block.successors:
                    if successor.resolved and successor.target_block in predecessors:
                        predecessors[successor.target_block].append(
                            {"from": block.id, "function": function.id, "kind": successor.kind.value}
                        )
        ordered: dict[str, tuple[dict[str, Any], ...]] = {}
        for block_id in sorted(predecessors):
            ordered[block_id] = tuple(sorted(predecessors[block_id], key=lambda item: (item["function"], item["from"], item["kind"])))
        return ordered

    def direct_call_graph(self) -> tuple[dict[str, Any], ...]:
        """Direct calls only; unresolved indirect call sites are separate."""
        edges = [
            {"from": function.id, "to": callee}
            for function in self.ordered_functions()
            for callee in sorted(function.direct_callees)
        ]
        return tuple(sorted(edges, key=lambda edge: (edge["from"], edge["to"])))

    def unresolved_inventory(self) -> tuple[dict[str, Any], ...]:
        """All unresolved control-flow sites, both calls and jumps."""
        inventory: list[dict[str, Any]] = []
        for function in self.ordered_functions():
            for site in sorted(function.unresolved_call_sites, key=lambda item: (item.address, item.block_id)):
                inventory.append(
                    {
                        "function": function.id,
                        "block": site.block_id,
                        "address": site.address,
                        "op": site.op,
                        "kind": InstructionFlow.INDIRECT_CALL.value,
                        "reason": site.reason,
                        "evidence": site.evidence.value,
                    }
                )
            for block in function.ordered_blocks():
                for successor in block.successors:
                    if not successor.resolved:
                        instruction = block.terminal
                        inventory.append(
                            {
                                "function": function.id,
                                "block": block.id,
                                "address": instruction.address,
                                "op": instruction.op,
                                "kind": instruction.flow.value,
                                "reason": successor.detail or "unresolved target",
                                "evidence": successor.evidence.value,
                            }
                        )
        return tuple(sorted(inventory, key=lambda item: (item["address"], item["function"], item["block"], item["kind"])))

    def walk(self) -> Iterator[dict[str, Any]]:
        """Deterministic traversal in (entry address, id) order."""
        for function in self.ordered_functions():
            yield {"kind": "function", "id": function.id, "address": function.entry_address, "evidence": function.evidence.value}
            for block in function.ordered_blocks():
                yield {"kind": "block", "id": block.id, "address": block.entry_address, "evidence": block.evidence.value}
                for instruction in block.instructions:
                    yield {
                        "kind": "instruction",
                        "id": f"{block.id}@0x{instruction.address:x}",
                        "address": instruction.address,
                        "evidence": instruction.evidence.value,
                    }

    def to_document(self) -> dict[str, Any]:
        return {
            "program_model_version": PROGRAM_MODEL_VERSION,
            "source": self.source.to_document(),
            "entry": {"function": self.entry_function, "address": self.function(self.entry_function).entry_address},
            "functions": [function.to_document() for function in self.ordered_functions()],
        }

    def serialize(self) -> bytes:
        return (canonical_json(self.to_document()) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return hashlib.sha256(self.serialize()).hexdigest()

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "ProgramModel":
        _require_object(document, "program")
        _require_keys(document, {"program_model_version", "source", "entry", "functions"}, "program")
        version = document["program_model_version"]
        if version != PROGRAM_MODEL_VERSION:
            raise ProgramModelError(f"unsupported program_model_version {version!r}")
        if not isinstance(document["functions"], list) or not document["functions"]:
            raise ProgramModelError("program.functions must be a non-empty list")
        entry = document["entry"]
        _require_object(entry, "program.entry")
        _require_keys(entry, {"function", "address"}, "program.entry")
        model = cls(
            source=ProgramSource.from_document(document["source"]),
            functions=tuple(FunctionUnit.from_document(item) for item in document["functions"]),
            entry_function=entry["function"],
        )
        if entry["address"] != model.function(entry["function"]).entry_address:
            raise ProgramModelError("program.entry.address does not match the entry function's entry_address")
        return model

    @classmethod
    def deserialize(cls, data: bytes | str) -> "ProgramModel":
        try:
            document = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProgramModelError(f"invalid program model JSON: {exc}") from exc
        return cls.from_document(document)


def instruction_addresses(instructions: tuple[DecodedInstruction, ...]) -> tuple[int, ...]:
    return tuple(instruction.address for instruction in instructions)


def canonical_json(document: Any) -> str:
    """Canonical, sorted, separator-stable JSON used for hashing and storage."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _require_object(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProgramModelError(f"{where}: expected a JSON object")
    return value


def _require_keys(document: Mapping[str, Any], required: set[str], where: str) -> None:
    missing = sorted(required - set(document))
    if missing:
        raise ProgramModelError(f"{where}: missing required key(s): {', '.join(missing)}")
