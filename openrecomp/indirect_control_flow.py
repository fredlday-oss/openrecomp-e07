"""OpenRecomp deterministic architecture-neutral indirect-control-flow classification (P2-06).

`OpenRecomp Phase 2` stage P2-06 deliverable. This module turns the unresolved
indirect call/jump sites carried forward by the completed structural pipeline
(P2-01 `UnresolvedSite`, P2-02 `InstructionFlow`, P2-03 function ownership,
P2-04 `UNRESOLVED_INDIRECT` call edges, P2-05 `TranslationUnit`) into an explicit,
deterministic classification suitable for a later host-emitter stage.

Core safety rule: **unknown remains unknown**. The classifier never invents a
target:

* a site with no positive proof is left `UNRESOLVED_INDIRECT_CALL` /
  `UNRESOLVED_INDIRECT_JUMP`;
* a target is only recorded when an explicit, machine-readable
  `IndirectControlFlowEvidence` proof claim matches the exact structural site;
* a bounded candidate set stays `BOUNDED_CANDIDATES` and is never treated as
  resolved;
* a `RESOLVED` classification requires PROVEN evidence and an exact proof basis;
* address-shaped integers, nearby code, opcode appearance and adapter metadata
  are never used to synthesise a target.

The module is architecture-neutral: it consumes only neutral P2 structures and
introduces no opcode table, calling convention, delay slot, stack frame, address
width, endianness or console assumption. It performs no IR lowering and emits no
host code.

Proof bases (see `IndirectControlFlowBasis`) are supplied by an explicit evidence
record; the classifier validates the claim against the structural site and fails
closed on any contradiction, duplicate, unknown site or malformed document.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from openrecomp.call_graph import CallEdgeKind
from openrecomp.program_model import (
    EvidenceClass,
    InstructionFlow,
    ProgramModelError,
    ProgramSource,
    UnresolvedSite,
    _require_address,
    _require_id,
    _require_keys,
    _require_object,
    canonical_json,
)
from openrecomp.translation_units import TranslationUnit, TranslationUnitSet

INDIRECT_CONTROL_FLOW_VERSION = "1.0.0"


class IndirectControlFlowError(ValueError):
    """Raised when indirect-control-flow input is invalid, contradictory or unsupported."""


def _icf_id(value: Any, where: str) -> str:
    try:
        return _require_id(value, where)
    except ProgramModelError as exc:
        raise IndirectControlFlowError(str(exc)) from exc


def _icf_address(value: Any, where: str) -> int:
    try:
        return _require_address(value, where)
    except ProgramModelError as exc:
        raise IndirectControlFlowError(str(exc)) from exc


def _icf_object(value: Any, where: str) -> Mapping[str, Any]:
    try:
        return _require_object(value, where)
    except ProgramModelError as exc:
        raise IndirectControlFlowError(str(exc)) from exc


def _icf_keys(document: Mapping[str, Any], required: set[str], where: str) -> None:
    try:
        _require_keys(document, required, where)
    except ProgramModelError as exc:
        raise IndirectControlFlowError(str(exc)) from exc


class IndirectControlFlowKind(str, Enum):
    """Architecture-neutral kind of an indirect control transfer."""

    INDIRECT_CALL = "INDIRECT_CALL"
    INDIRECT_JUMP = "INDIRECT_JUMP"


class IndirectControlFlowStatus(str, Enum):
    """Deterministic classification of one indirect-control-flow site.

    Only `RESOLVED` carries proven exact targets. `BOUNDED_CANDIDATES` is a
    bounded unproven candidate set and must never be treated as resolved.
    `UNSUPPORTED_OR_MALFORMED` is the fail-closed bucket for structurally
    inconsistent or unsupported evidence.
    """

    RESOLVED = "RESOLVED"
    BOUNDED_CANDIDATES = "BOUNDED_CANDIDATES"
    EXTERNAL_OR_RUNTIME_MEDIATED = "EXTERNAL_OR_RUNTIME_MEDIATED"
    RETURN_LIKE = "RETURN_LIKE"
    UNRESOLVED_INDIRECT_CALL = "UNRESOLVED_INDIRECT_CALL"
    UNRESOLVED_INDIRECT_JUMP = "UNRESOLVED_INDIRECT_JUMP"
    UNSUPPORTED_OR_MALFORMED = "UNSUPPORTED_OR_MALFORMED"


class IndirectControlFlowBasis(str, Enum):
    """Explicit machine-readable proof basis for one classification."""

    EXACT_CONSTANT_TARGET = "EXACT_CONSTANT_TARGET"
    EXACT_TARGET_SET = "EXACT_TARGET_SET"
    ADAPTER_EVIDENCE = "ADAPTER_EVIDENCE"
    BOUNDED_CANDIDATE_EVIDENCE = "BOUNDED_CANDIDATE_EVIDENCE"
    EXTERNAL_RUNTIME_EVIDENCE = "EXTERNAL_RUNTIME_EVIDENCE"
    STRUCTURAL_RETURN_EVIDENCE = "STRUCTURAL_RETURN_EVIDENCE"
    NONE = "NONE"


_RESOLVED_BASES = frozenset(
    {
        IndirectControlFlowBasis.EXACT_CONSTANT_TARGET,
        IndirectControlFlowBasis.EXACT_TARGET_SET,
        IndirectControlFlowBasis.ADAPTER_EVIDENCE,
    }
)
_BOUNDED_BASES = frozenset(
    {
        IndirectControlFlowBasis.BOUNDED_CANDIDATE_EVIDENCE,
        IndirectControlFlowBasis.ADAPTER_EVIDENCE,
    }
)
_POSITIVE_STATUSES = frozenset(
    {
        IndirectControlFlowStatus.RESOLVED,
        IndirectControlFlowStatus.BOUNDED_CANDIDATES,
        IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED,
        IndirectControlFlowStatus.RETURN_LIKE,
    }
)


def _canonical_targets(targets: Any, where: str) -> tuple[int, ...]:
    if not isinstance(targets, tuple):
        raise IndirectControlFlowError(f"{where}: targets must be a tuple of addresses")
    collected: list[int] = []
    for target in targets:
        collected.append(_icf_address(target, f"{where} target"))
    if len(set(collected)) != len(collected):
        raise IndirectControlFlowError(f"{where}: targets must be unique")
    return tuple(sorted(collected))


def _canonical_ids(values: Any, where: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise IndirectControlFlowError(f"{where}: must be a tuple of identifiers")
    collected: list[str] = []
    for value in values:
        collected.append(_icf_id(value, where))
    if len(set(collected)) != len(collected):
        raise IndirectControlFlowError(f"{where}: identifiers must be unique")
    return tuple(sorted(collected))


def _canonical_provenance(provenance: Any, where: str) -> tuple[str, ...]:
    if not isinstance(provenance, tuple) or not provenance:
        raise IndirectControlFlowError(f"{where}: provenance must be a non-empty tuple of labels")
    for label in provenance:
        if not isinstance(label, str) or not label:
            raise IndirectControlFlowError(f"{where}: provenance labels must be non-empty strings")
    return tuple(sorted(set(provenance)))


def _validate_claim(
    status: IndirectControlFlowStatus,
    basis: IndirectControlFlowBasis,
    targets: tuple[int, ...],
    external_mechanism: str | None,
    kind: IndirectControlFlowKind,
    where: str,
) -> None:
    if status is IndirectControlFlowStatus.RESOLVED:
        if basis not in _RESOLVED_BASES:
            raise IndirectControlFlowError(f"{where}: RESOLVED requires an exact-target proof basis, got {basis.value}")
        if not targets:
            raise IndirectControlFlowError(f"{where}: RESOLVED requires at least one proven target")
        if basis is IndirectControlFlowBasis.EXACT_CONSTANT_TARGET and len(targets) != 1:
            raise IndirectControlFlowError(f"{where}: EXACT_CONSTANT_TARGET requires exactly one target")
        if basis is IndirectControlFlowBasis.EXACT_TARGET_SET and len(targets) < 2:
            raise IndirectControlFlowError(f"{where}: EXACT_TARGET_SET requires at least two targets")
        if external_mechanism is not None:
            raise IndirectControlFlowError(f"{where}: RESOLVED must not carry an external mechanism")
    elif status is IndirectControlFlowStatus.BOUNDED_CANDIDATES:
        if basis not in _BOUNDED_BASES:
            raise IndirectControlFlowError(
                f"{where}: BOUNDED_CANDIDATES requires bounded-candidate or adapter evidence, got {basis.value}"
            )
        if not targets:
            raise IndirectControlFlowError(f"{where}: BOUNDED_CANDIDATES requires at least one candidate target")
        if external_mechanism is not None:
            raise IndirectControlFlowError(f"{where}: BOUNDED_CANDIDATES must not carry an external mechanism")
    elif status is IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED:
        if basis is not IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE:
            raise IndirectControlFlowError(
                f"{where}: EXTERNAL_OR_RUNTIME_MEDIATED requires EXTERNAL_RUNTIME_EVIDENCE, got {basis.value}"
            )
        if targets:
            raise IndirectControlFlowError(f"{where}: EXTERNAL_OR_RUNTIME_MEDIATED must not carry internal targets")
        if not external_mechanism:
            raise IndirectControlFlowError(f"{where}: EXTERNAL_OR_RUNTIME_MEDIATED requires an external mechanism label")
    elif status is IndirectControlFlowStatus.RETURN_LIKE:
        if basis is not IndirectControlFlowBasis.STRUCTURAL_RETURN_EVIDENCE:
            raise IndirectControlFlowError(
                f"{where}: RETURN_LIKE requires STRUCTURAL_RETURN_EVIDENCE, got {basis.value}"
            )
        if targets:
            raise IndirectControlFlowError(f"{where}: RETURN_LIKE must not carry targets")
        if kind is not IndirectControlFlowKind.INDIRECT_JUMP:
            raise IndirectControlFlowError(f"{where}: RETURN_LIKE only applies to an indirect jump")
        if external_mechanism is not None:
            raise IndirectControlFlowError(f"{where}: RETURN_LIKE must not carry an external mechanism")
    elif status is IndirectControlFlowStatus.UNRESOLVED_INDIRECT_CALL:
        if basis is not IndirectControlFlowBasis.NONE or targets or external_mechanism is not None:
            raise IndirectControlFlowError(f"{where}: UNRESOLVED_INDIRECT_CALL must be evidence-free")
        if kind is not IndirectControlFlowKind.INDIRECT_CALL:
            raise IndirectControlFlowError(f"{where}: UNRESOLVED_INDIRECT_CALL requires an indirect call site")
    elif status is IndirectControlFlowStatus.UNRESOLVED_INDIRECT_JUMP:
        if basis is not IndirectControlFlowBasis.NONE or targets or external_mechanism is not None:
            raise IndirectControlFlowError(f"{where}: UNRESOLVED_INDIRECT_JUMP must be evidence-free")
        if kind is not IndirectControlFlowKind.INDIRECT_JUMP:
            raise IndirectControlFlowError(f"{where}: UNRESOLVED_INDIRECT_JUMP requires an indirect jump site")
    elif status is IndirectControlFlowStatus.UNSUPPORTED_OR_MALFORMED:
        if basis is not IndirectControlFlowBasis.NONE or targets or external_mechanism is not None:
            raise IndirectControlFlowError(f"{where}: UNSUPPORTED_OR_MALFORMED must not carry targets or mechanisms")
    else:
        raise IndirectControlFlowError(f"{where}: unsupported classification status {status!r}")


def _require_optional_string(value: Any, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise IndirectControlFlowError(f"{where}: must be a non-empty string or null")
    return value


@dataclass(frozen=True)
class IndirectControlFlowEvidence:
    """An explicit, machine-readable proof claim about one structural site.

    Evidence records are supplied by a trusted adapter or fixture; the classifier
    never generates them. A record must identify the exact structural site
    (`function_id`, `block_id`, `address`, `kind`) and declare a positive status
    with a proof basis and, where applicable, exact or candidate targets.
    """

    function_id: str
    block_id: str
    address: int
    kind: IndirectControlFlowKind
    status: IndirectControlFlowStatus
    basis: IndirectControlFlowBasis
    targets: tuple[int, ...] = ()
    external_mechanism: str | None = None
    detail: str | None = None
    source: str = "explicit"
    evidence: EvidenceClass = EvidenceClass.PROVEN

    def __post_init__(self) -> None:
        _icf_id(self.function_id, "evidence.function_id")
        _icf_id(self.block_id, "evidence.block_id")
        _icf_address(self.address, "evidence.address")
        if not isinstance(self.kind, IndirectControlFlowKind):
            raise IndirectControlFlowError(f"evidence.kind must be an IndirectControlFlowKind, got {self.kind!r}")
        if not isinstance(self.status, IndirectControlFlowStatus):
            raise IndirectControlFlowError(f"evidence.status must be an IndirectControlFlowStatus, got {self.status!r}")
        if not isinstance(self.basis, IndirectControlFlowBasis):
            raise IndirectControlFlowError(f"evidence.basis must be an IndirectControlFlowBasis, got {self.basis!r}")
        if self.status not in _POSITIVE_STATUSES:
            raise IndirectControlFlowError(
                f"evidence {self.key()}: status {self.status.value} is not a positive proof claim"
            )
        if self.basis is IndirectControlFlowBasis.NONE:
            raise IndirectControlFlowError(f"evidence {self.key()}: a proof claim may not use the NONE basis")
        targets = _canonical_targets(self.targets, f"evidence {self.key()}")
        external_mechanism = _require_optional_string(self.external_mechanism, f"evidence {self.key()}.external_mechanism")
        detail = _require_optional_string(self.detail, f"evidence {self.key()}.detail")
        if not isinstance(self.source, str) or not self.source:
            raise IndirectControlFlowError(f"evidence {self.key()}: source must be a non-empty string")
        if not isinstance(self.evidence, EvidenceClass):
            raise IndirectControlFlowError(f"evidence {self.key()}: evidence must be an EvidenceClass")
        if self.status is IndirectControlFlowStatus.RESOLVED and self.evidence is not EvidenceClass.PROVEN:
            raise IndirectControlFlowError(
                f"evidence {self.key()}: RESOLVED requires PROVEN evidence (a candidate target must not be promoted)"
            )
        _validate_claim(self.status, self.basis, targets, external_mechanism, self.kind, f"evidence {self.key()}")
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "external_mechanism", external_mechanism)
        object.__setattr__(self, "detail", detail)

    def key(self) -> tuple[str, str, int, str]:
        return (self.function_id, self.block_id, self.address, self.kind.value)

    def to_document(self) -> dict[str, Any]:
        return {
            "function_id": self.function_id,
            "block_id": self.block_id,
            "address": self.address,
            "kind": self.kind.value,
            "status": self.status.value,
            "basis": self.basis.value,
            "targets": list(self.targets),
            "external_mechanism": self.external_mechanism,
            "detail": self.detail,
            "source": self.source,
            "evidence": self.evidence.value,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "IndirectControlFlowEvidence":
        try:
            _icf_object(document, "evidence")
            _icf_keys(
                document,
                {"function_id", "block_id", "address", "kind", "status", "basis"},
                "evidence",
            )
            return cls(
                function_id=document["function_id"],
                block_id=document["block_id"],
                address=document["address"],
                kind=IndirectControlFlowKind(document["kind"]),
                status=IndirectControlFlowStatus(document["status"]),
                basis=IndirectControlFlowBasis(document["basis"]),
                targets=tuple(document.get("targets", ())),
                external_mechanism=document.get("external_mechanism"),
                detail=document.get("detail"),
                source=document.get("source", "explicit"),
                evidence=EvidenceClass(document.get("evidence", EvidenceClass.PROVEN.value)),
            )
        except IndirectControlFlowError:
            raise
        except (ProgramModelError, ValueError) as exc:
            raise IndirectControlFlowError(str(exc)) from exc


@dataclass(frozen=True)
class IndirectControlFlowClassification:
    """Deterministic classification of one structural indirect site.

    The original `UnresolvedSite` is embedded unchanged so the unresolved
    evidence and reason survive even when the site is later classified.
    """

    unit_id: str
    function_id: str
    entry_address: int
    block_id: str
    address: int
    op: str
    kind: IndirectControlFlowKind
    status: IndirectControlFlowStatus
    basis: IndirectControlFlowBasis
    targets: tuple[int, ...] = ()
    target_functions: tuple[str, ...] = ()
    external_mechanism: str | None = None
    detail: str | None = None
    evidence: EvidenceClass = EvidenceClass.CANDIDATE
    provenance: tuple[str, ...] = ()
    unresolved_site: UnresolvedSite | None = None

    def __post_init__(self) -> None:
        _icf_id(self.unit_id, "classification.unit_id")
        _icf_id(self.function_id, "classification.function_id")
        _icf_address(self.entry_address, "classification.entry_address")
        _icf_id(self.block_id, "classification.block_id")
        _icf_address(self.address, "classification.address")
        if not isinstance(self.op, str) or not self.op:
            raise IndirectControlFlowError(f"classification {self.block_id}@0x{self.address:x}: op must be a non-empty string")
        if not isinstance(self.kind, IndirectControlFlowKind):
            raise IndirectControlFlowError(f"classification.kind must be an IndirectControlFlowKind, got {self.kind!r}")
        if not isinstance(self.status, IndirectControlFlowStatus):
            raise IndirectControlFlowError(
                f"classification.status must be an IndirectControlFlowStatus, got {self.status!r}"
            )
        if not isinstance(self.basis, IndirectControlFlowBasis):
            raise IndirectControlFlowError(
                f"classification.basis must be an IndirectControlFlowBasis, got {self.basis!r}"
            )
        if not isinstance(self.evidence, EvidenceClass):
            raise IndirectControlFlowError("classification.evidence must be an EvidenceClass")
        targets = _canonical_targets(self.targets, f"classification {self.block_id}@0x{self.address:x}")
        target_functions = _canonical_ids(
            self.target_functions, f"classification {self.block_id}@0x{self.address:x}.target_functions"
        )
        external_mechanism = _require_optional_string(
            self.external_mechanism, f"classification {self.block_id}@0x{self.address:x}.external_mechanism"
        )
        detail = _require_optional_string(self.detail, f"classification {self.block_id}@0x{self.address:x}.detail")
        provenance = _canonical_provenance(
            self.provenance, f"classification {self.block_id}@0x{self.address:x}.provenance"
        )
        if self.status is IndirectControlFlowStatus.RESOLVED and self.evidence is not EvidenceClass.PROVEN:
            raise IndirectControlFlowError(
                f"classification {self.block_id}@0x{self.address:x}: RESOLVED requires PROVEN evidence"
            )
        if self.unresolved_site is None:
            raise IndirectControlFlowError(
                f"classification {self.block_id}@0x{self.address:x}: unresolved_site provenance is required"
            )
        if not isinstance(self.unresolved_site, UnresolvedSite):
            raise IndirectControlFlowError(
                f"classification {self.block_id}@0x{self.address:x}: unresolved_site must be an UnresolvedSite"
            )
        if (
            self.unresolved_site.block_id != self.block_id
            or self.unresolved_site.address != self.address
            or self.unresolved_site.op != self.op
        ):
            raise IndirectControlFlowError(
                f"classification {self.block_id}@0x{self.address:x}: unresolved_site provenance disagrees with the site"
            )
        _validate_claim(
            self.status,
            self.basis,
            targets,
            external_mechanism,
            self.kind,
            f"classification {self.block_id}@0x{self.address:x}",
        )
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "target_functions", target_functions)
        object.__setattr__(self, "external_mechanism", external_mechanism)
        object.__setattr__(self, "detail", detail)
        object.__setattr__(self, "provenance", provenance)

    def key(self) -> tuple[str, str, int, str]:
        return (self.function_id, self.block_id, self.address, self.kind.value)

    @property
    def resolved(self) -> bool:
        return self.status is IndirectControlFlowStatus.RESOLVED

    def to_document(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "function_id": self.function_id,
            "entry_address": self.entry_address,
            "block_id": self.block_id,
            "address": self.address,
            "op": self.op,
            "kind": self.kind.value,
            "status": self.status.value,
            "basis": self.basis.value,
            "targets": list(self.targets),
            "target_functions": list(self.target_functions),
            "external_mechanism": self.external_mechanism,
            "detail": self.detail,
            "evidence": self.evidence.value,
            "provenance": list(self.provenance),
            "unresolved_site": (self.unresolved_site.to_document() if self.unresolved_site is not None else None),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "IndirectControlFlowClassification":
        try:
            _icf_object(document, "classification")
            _icf_keys(
                document,
                {
                    "unit_id",
                    "function_id",
                    "entry_address",
                    "block_id",
                    "address",
                    "op",
                    "kind",
                    "status",
                    "basis",
                    "unresolved_site",
                },
                "classification",
            )
            unresolved = document["unresolved_site"]
            if unresolved is None:
                raise IndirectControlFlowError("classification.unresolved_site is required")
            return cls(
                unit_id=document["unit_id"],
                function_id=document["function_id"],
                entry_address=document["entry_address"],
                block_id=document["block_id"],
                address=document["address"],
                op=document["op"],
                kind=IndirectControlFlowKind(document["kind"]),
                status=IndirectControlFlowStatus(document["status"]),
                basis=IndirectControlFlowBasis(document["basis"]),
                targets=tuple(document.get("targets", ())),
                target_functions=tuple(document.get("target_functions", ())),
                external_mechanism=document.get("external_mechanism"),
                detail=document.get("detail"),
                evidence=EvidenceClass(document.get("evidence", EvidenceClass.CANDIDATE.value)),
                provenance=tuple(document.get("provenance", ())),
                unresolved_site=UnresolvedSite.from_document(unresolved),
            )
        except IndirectControlFlowError:
            raise
        except (ProgramModelError, ValueError) as exc:
            raise IndirectControlFlowError(str(exc)) from exc


@dataclass(frozen=True)
class IndirectControlFlowUnit:
    """All indirect-control-flow classifications for one translation unit."""

    unit_id: str
    function_id: str
    entry_address: int
    classifications: tuple[IndirectControlFlowClassification, ...] = ()

    def __post_init__(self) -> None:
        _icf_id(self.unit_id, "unit.unit_id")
        _icf_id(self.function_id, "unit.function_id")
        _icf_address(self.entry_address, "unit.entry_address")
        if not isinstance(self.classifications, tuple):
            raise IndirectControlFlowError(f"unit {self.unit_id}: classifications must be a tuple")
        for classification in self.classifications:
            if not isinstance(classification, IndirectControlFlowClassification):
                raise IndirectControlFlowError(f"unit {self.unit_id}: classification membership must be a classification")
            if (
                classification.unit_id != self.unit_id
                or classification.function_id != self.function_id
                or classification.entry_address != self.entry_address
            ):
                raise IndirectControlFlowError(
                    f"unit {self.unit_id}: classification {classification.key()} does not belong to this unit"
                )
        ordered = tuple(sorted(self.classifications, key=lambda item: (item.address, item.kind.value, item.block_id)))
        keys = [item.key() for item in ordered]
        if len(set(keys)) != len(keys):
            raise IndirectControlFlowError(f"unit {self.unit_id}: duplicate classification site")
        object.__setattr__(self, "classifications", ordered)

    def site_count(self) -> int:
        return len(self.classifications)

    def to_document(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "function_id": self.function_id,
            "entry_address": self.entry_address,
            "classifications": [item.to_document() for item in self.classifications],
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "IndirectControlFlowUnit":
        try:
            _icf_object(document, "unit")
            _icf_keys(document, {"unit_id", "function_id", "entry_address"}, "unit")
            return cls(
                unit_id=document["unit_id"],
                function_id=document["function_id"],
                entry_address=document["entry_address"],
                classifications=tuple(
                    IndirectControlFlowClassification.from_document(item)
                    for item in document.get("classifications", [])
                ),
            )
        except IndirectControlFlowError:
            raise
        except (ProgramModelError, ValueError) as exc:
            raise IndirectControlFlowError(str(exc)) from exc


def _site_order_key(site: UnresolvedSite) -> tuple:
    return (site.address, site.block_id, site.op)


class IndirectControlFlowSet:
    """A validated, deterministic classification of a whole `TranslationUnitSet`."""

    def __init__(
        self,
        source: ProgramSource,
        units: Iterable[IndirectControlFlowUnit],
        *,
        unowned_control_flow: Iterable[UnresolvedSite] = (),
    ) -> None:
        if not isinstance(source, ProgramSource):
            raise IndirectControlFlowError("source must be a ProgramSource")
        self.source = source
        unit_items = tuple(units)
        for unit in unit_items:
            if not isinstance(unit, IndirectControlFlowUnit):
                raise IndirectControlFlowError("units must be IndirectControlFlowUnit instances")
        self.units = tuple(sorted(unit_items, key=lambda unit: (unit.entry_address, unit.function_id)))
        residual = tuple(unowned_control_flow)
        for site in residual:
            if not isinstance(site, UnresolvedSite):
                raise IndirectControlFlowError("unowned_control_flow must contain UnresolvedSite instances")
        self.unowned_control_flow = tuple(sorted(residual, key=_site_order_key))
        self._unit_by_function: dict[str, IndirectControlFlowUnit] = {}
        self._unit_by_id: dict[str, IndirectControlFlowUnit] = {}
        self._classification_by_key: dict[tuple[str, str, int, str], IndirectControlFlowClassification] = {}
        self.validate()

    def validate(self) -> None:
        if not self.units:
            raise IndirectControlFlowError("indirect-control-flow set must contain at least one unit")
        width = self.source.address_width_bits
        self._unit_by_function = {}
        self._unit_by_id = {}
        self._classification_by_key = {}
        entry_addresses: set[int] = set()
        owned_blocks: dict[str, str] = {}
        for unit in self.units:
            if not isinstance(unit, IndirectControlFlowUnit):
                raise IndirectControlFlowError("units must be IndirectControlFlowUnit instances")
            if unit.unit_id in self._unit_by_id:
                raise IndirectControlFlowError(f"duplicate indirect-control-flow unit id {unit.unit_id}")
            if unit.function_id in self._unit_by_function:
                raise IndirectControlFlowError(f"duplicate indirect-control-flow function id {unit.function_id}")
            if unit.entry_address in entry_addresses:
                raise IndirectControlFlowError(f"duplicate unit entry address 0x{unit.entry_address:x}")
            if width is not None and unit.entry_address >= (1 << width):
                raise IndirectControlFlowError(f"unit {unit.unit_id}: entry address exceeds the declared {width}-bit width")
            self._unit_by_id[unit.unit_id] = unit
            self._unit_by_function[unit.function_id] = unit
            entry_addresses.add(unit.entry_address)
            for classification in unit.classifications:
                key = classification.key()
                if key in self._classification_by_key:
                    raise IndirectControlFlowError(f"duplicate classification site {key}")
                self._classification_by_key[key] = classification
            for block_id in {item.block_id for item in unit.classifications}:
                if block_id in owned_blocks:
                    raise IndirectControlFlowError(
                        f"classification block {block_id} is classified in more than one unit"
                    )
                owned_blocks[block_id] = unit.unit_id

        for site in self.unowned_control_flow:
            if site.block_id in owned_blocks:
                raise IndirectControlFlowError(
                    f"unowned control-flow site block {site.block_id} is owned by unit {owned_blocks[site.block_id]}"
                )

    def classifications(self) -> tuple[IndirectControlFlowClassification, ...]:
        return tuple(item for unit in self.units for item in unit.classifications)

    def unit_for(self, function_id: str) -> IndirectControlFlowUnit:
        try:
            return self._unit_by_function[function_id]
        except KeyError as exc:
            raise IndirectControlFlowError(f"unknown indirect-control-flow function {function_id}") from exc

    def unit_by_id(self, unit_id: str) -> IndirectControlFlowUnit:
        try:
            return self._unit_by_id[unit_id]
        except KeyError as exc:
            raise IndirectControlFlowError(f"unknown indirect-control-flow unit {unit_id}") from exc

    def classification_for(
        self,
        function_id: str,
        block_id: str,
        address: int,
        kind: IndirectControlFlowKind,
    ) -> IndirectControlFlowClassification:
        try:
            return self._classification_by_key[(function_id, block_id, address, kind.value)]
        except KeyError as exc:
            raise IndirectControlFlowError(
                f"unknown indirect-control-flow site {function_id}/{block_id}@0x{address:x} ({kind.value})"
            ) from exc

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {status.value: 0 for status in IndirectControlFlowStatus}
        for classification in self.classifications():
            counts[classification.status.value] += 1
        return {key: counts[key] for key in sorted(counts)}

    def to_document(self) -> dict[str, Any]:
        return {
            "indirect_control_flow_version": INDIRECT_CONTROL_FLOW_VERSION,
            "source": self.source.to_document(),
            "units": [unit.to_document() for unit in self.units],
            "unowned_control_flow": [site.to_document() for site in self.unowned_control_flow],
        }

    def serialize(self) -> bytes:
        return (canonical_json(self.to_document()) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return hashlib.sha256(self.serialize()).hexdigest()

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "IndirectControlFlowSet":
        try:
            _icf_object(document, "indirect-control-flow set")
            _icf_keys(
                document,
                {"indirect_control_flow_version", "source", "units"},
                "indirect-control-flow set",
            )
            version = document["indirect_control_flow_version"]
            if version != INDIRECT_CONTROL_FLOW_VERSION:
                raise IndirectControlFlowError(f"unsupported indirect_control_flow_version {version!r}")
            if not isinstance(document["units"], list) or not document["units"]:
                raise IndirectControlFlowError("indirect-control-flow set.units must be a non-empty list")
            return cls(
                source=ProgramSource.from_document(document["source"]),
                units=tuple(IndirectControlFlowUnit.from_document(item) for item in document["units"]),
                unowned_control_flow=tuple(
                    UnresolvedSite.from_document(item) for item in document.get("unowned_control_flow", [])
                ),
            )
        except IndirectControlFlowError:
            raise
        except (ProgramModelError, ValueError) as exc:
            raise IndirectControlFlowError(str(exc)) from exc

    @classmethod
    def deserialize(cls, data: bytes | str) -> "IndirectControlFlowSet":
        import json

        try:
            document = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise IndirectControlFlowError(f"invalid indirect-control-flow JSON: {exc}") from exc
        return cls.from_document(document)


def _kind_for_flow(flow: InstructionFlow) -> IndirectControlFlowKind | None:
    if flow is InstructionFlow.INDIRECT_CALL:
        return IndirectControlFlowKind.INDIRECT_CALL
    if flow is InstructionFlow.INDIRECT_JUMP:
        return IndirectControlFlowKind.INDIRECT_JUMP
    return None


def _structural_provenance(kind: IndirectControlFlowKind) -> tuple[str, ...]:
    if kind is IndirectControlFlowKind.INDIRECT_CALL:
        return (
            "P2-02:InstructionFlow.INDIRECT_CALL",
            "P2-04:CallGraphEdge.UNRESOLVED_INDIRECT",
            "P2-05:TranslationUnit.unresolved_call_sites",
        )
    return (
        "P2-02:InstructionFlow.INDIRECT_JUMP",
        "P2-05:TranslationUnit.unresolved_jump_sites",
    )


def _unit_sites(
    unit: TranslationUnit,
) -> list[tuple[str, int, str, IndirectControlFlowKind, UnresolvedSite]]:
    """Enumerate and cross-check the indirect sites owned by one translation unit."""
    observed: list[tuple[str, int, str, IndirectControlFlowKind]] = []
    for block in unit.blocks:
        for index, instruction in enumerate(block.instructions):
            kind = _kind_for_flow(instruction.flow)
            if kind is None:
                continue
            if index != len(block.instructions) - 1:
                raise IndirectControlFlowError(
                    f"unit {unit.unit_id}: indirect control instruction 0x{instruction.address:x} is not the block terminator"
                )
            observed.append((block.id, instruction.address, instruction.op, kind))

    call_sites = {(site.block_id, site.address, site.op): site for site in unit.unresolved_call_sites}
    jump_sites = {(site.block_id, site.address, site.op): site for site in unit.unresolved_jump_sites}
    if len(call_sites) != len(unit.unresolved_call_sites):
        raise IndirectControlFlowError(f"unit {unit.unit_id}: duplicate unresolved call site")
    if len(jump_sites) != len(unit.unresolved_jump_sites):
        raise IndirectControlFlowError(f"unit {unit.unit_id}: duplicate unresolved jump site")

    observed_calls = {(block, address, op) for block, address, op, kind in observed if kind is IndirectControlFlowKind.INDIRECT_CALL}
    observed_jumps = {(block, address, op) for block, address, op, kind in observed if kind is IndirectControlFlowKind.INDIRECT_JUMP}
    if observed_calls != set(call_sites):
        raise IndirectControlFlowError(
            f"unit {unit.unit_id}: indirect-call instructions disagree with unresolved_call_sites"
        )
    if observed_jumps != set(jump_sites):
        raise IndirectControlFlowError(
            f"unit {unit.unit_id}: indirect-jump instructions disagree with unresolved_jump_sites"
        )

    edge_sites = {
        (edge.call_site_block, edge.call_site_address, edge.call_site_op)
        for edge in unit.call_edges
        if edge.kind is CallEdgeKind.UNRESOLVED_INDIRECT
    }
    if edge_sites != observed_calls:
        raise IndirectControlFlowError(
            f"unit {unit.unit_id}: UNRESOLVED_INDIRECT call edges disagree with indirect-call instructions"
        )

    return [
        (block, address, op, kind, (call_sites if kind is IndirectControlFlowKind.INDIRECT_CALL else jump_sites)[(block, address, op)])
        for block, address, op, kind in observed
    ]


def _classify_site(
    unit: TranslationUnit,
    block_id: str,
    address: int,
    op: str,
    kind: IndirectControlFlowKind,
    unresolved_site: UnresolvedSite,
    evidence: IndirectControlFlowEvidence | None,
    entry_index: Mapping[int, str],
) -> IndirectControlFlowClassification:
    if evidence is None:
        status = (
            IndirectControlFlowStatus.UNRESOLVED_INDIRECT_CALL
            if kind is IndirectControlFlowKind.INDIRECT_CALL
            else IndirectControlFlowStatus.UNRESOLVED_INDIRECT_JUMP
        )
        basis = IndirectControlFlowBasis.NONE
        targets: tuple[int, ...] = ()
        target_functions: tuple[str, ...] = ()
        external_mechanism = None
        detail = None
        evidence_class = unresolved_site.evidence
        provenance = _structural_provenance(kind)
    else:
        status = evidence.status
        basis = evidence.basis
        targets = evidence.targets
        target_functions = tuple(sorted({entry_index[target] for target in targets if target in entry_index}))
        external_mechanism = evidence.external_mechanism
        detail = evidence.detail
        evidence_class = evidence.evidence
        provenance = _structural_provenance(kind) + (f"evidence:{evidence.source}",)
    return IndirectControlFlowClassification(
        unit_id=unit.unit_id,
        function_id=unit.function_id,
        entry_address=unit.entry_address,
        block_id=block_id,
        address=address,
        op=op,
        kind=kind,
        status=status,
        basis=basis,
        targets=targets,
        target_functions=target_functions,
        external_mechanism=external_mechanism,
        detail=detail,
        evidence=evidence_class,
        provenance=provenance,
        unresolved_site=unresolved_site,
    )


def classify_indirect_control_flow_from(
    units: Iterable[TranslationUnit],
    *,
    source: ProgramSource,
    unowned_control_flow: Iterable[UnresolvedSite] = (),
    evidence: Iterable[IndirectControlFlowEvidence] = (),
) -> IndirectControlFlowSet:
    """Classify the indirect sites of the supplied translation units."""
    if not isinstance(source, ProgramSource):
        raise IndirectControlFlowError("source must be a ProgramSource")
    unit_items = tuple(units)
    if not unit_items:
        raise IndirectControlFlowError("at least one translation unit is required")
    for unit in unit_items:
        if not isinstance(unit, TranslationUnit):
            raise IndirectControlFlowError("units must be TranslationUnit instances")
    units = tuple(sorted(unit_items, key=lambda unit: (unit.entry_address, unit.function_id)))

    entry_index: dict[int, str] = {}
    for unit in units:
        if unit.entry_address in entry_index:
            raise IndirectControlFlowError(f"duplicate translation-unit entry address 0x{unit.entry_address:x}")
        entry_index[unit.entry_address] = unit.function_id

    evidence_index: dict[tuple[str, str, int, str], IndirectControlFlowEvidence] = {}
    for record in evidence:
        if not isinstance(record, IndirectControlFlowEvidence):
            raise IndirectControlFlowError("evidence must contain IndirectControlFlowEvidence instances")
        if record.key() in evidence_index:
            raise IndirectControlFlowError(f"duplicate or conflicting evidence for site {record.key()}")
        evidence_index[record.key()] = record

    all_sites: set[tuple[str, str, int, str]] = set()
    unit_sites = {}
    for unit in units:
        sites = _unit_sites(unit)
        unit_sites[unit.unit_id] = sites
        for block_id, address, op, kind, _ in sites:
            all_sites.add((unit.function_id, block_id, address, kind.value))

    for key in evidence_index:
        if key not in all_sites:
            raise IndirectControlFlowError(f"evidence references an unknown indirect site {key}")

    result_units: list[IndirectControlFlowUnit] = []
    for unit in units:
        classifications = tuple(
            _classify_site(
                unit,
                block_id,
                address,
                op,
                kind,
                unresolved_site,
                evidence_index.get((unit.function_id, block_id, address, kind.value)),
                entry_index,
            )
            for block_id, address, op, kind, unresolved_site in unit_sites[unit.unit_id]
        )
        result_units.append(
            IndirectControlFlowUnit(unit.unit_id, unit.function_id, unit.entry_address, classifications)
        )

    return IndirectControlFlowSet(source, result_units, unowned_control_flow=unowned_control_flow)


def classify_indirect_control_flow(
    translation_units: TranslationUnitSet,
    *,
    evidence: Iterable[IndirectControlFlowEvidence] = (),
) -> IndirectControlFlowSet:
    """Classify the indirect sites of a completed P2-05 translation-unit set.

    The translation units are never mutated; their structural evidence is only
    read. Unowned control flow carried by the P2-05 set is preserved as residual
    evidence and is not classified (its control-flow kind cannot be established
    without inventing information).
    """
    if not isinstance(translation_units, TranslationUnitSet):
        raise IndirectControlFlowError("classify_indirect_control_flow requires a TranslationUnitSet")
    return classify_indirect_control_flow_from(
        translation_units.units,
        source=translation_units.source,
        unowned_control_flow=translation_units.unowned_control_flow,
        evidence=evidence,
    )
