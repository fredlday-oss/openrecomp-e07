#!/usr/bin/env python3
"""OpenRecomp Phase-11 BIOS vector frontier V1.

The Phase-9/Phase-10 typed BIOS boundary is reused unchanged (no BIOS image, no
BIOS-derived code and no BIOS material). This module adds exact,
evidence-bounded classification of the *causal* indirect-control sites that the
Phase-10 frontier did not cover:

* the audited BIOS jump-table convention is applied to reachable indirect
  *jumps* (``jr``) as well as indirect calls: the vector base is a resolved
  constant in the source register and the function index is a constant written
  to ``$t1`` in the transfer's delay slot (``INDEX_REGISTER``/``VECTOR_REGISTER``
  from ``p10_bios_boundary_v1``);
* a site whose vector base resolves to a documented A0/B0/C0 vector and whose
  function index resolves to a *documented* service is classified as a
  ``BIOS_VECTOR_SERVICE`` with a stable neutral op name and service id;
* a site whose index does not resolve, or whose (vector, index) pair is not in
  the documented service table, stays fail-closed and is never renamed;
* every classification is emitted as explicit ``IndirectControlFlowEvidence``
  with the external-runtime basis, so the shared classifier carries the proof.

Documented service semantics come from public PlayStation documentation
(the PSX-SPX BIOS function tables). They are recorded as identifiers plus the
documented signature and refusal rule; nothing console-derived is used and no
BIOS image is loaded, executed or emulated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import p10_bios_boundary_v1 as p10_bios
from openrecomp.indirect_control_flow import (
    IndirectControlFlowBasis,
    IndirectControlFlowEvidence,
    IndirectControlFlowKind,
    IndirectControlFlowStatus,
)
from openrecomp.program_model import EvidenceClass

BIOS_VERSION = "1.1.0"

#: The MIPS argument registers of the documented A0/B0/C0 calling convention.
BIOS_ARGUMENT_REGISTERS = (4, 5, 6)
#: The MIPS return-value register of the documented convention.
BIOS_RETURN_REGISTER = 2

#: Documented A0 services used by the frontier. The semantics are public
#: documentation facts, not console-derived material:
#:   A(2Bh) memset(dst, fillbyte, len)
#:   fills len bytes at dst with (fillbyte & 0xff); refuses (returns 0) when
#:   dst == 0, len == 0 or len > 0x7fffffff; otherwise returns dst.
DOCUMENTED_A0_SERVICES = {
    0x2B: {
        "name": "memset",
        "signature": ["dst", "fillbyte", "len"],
        "returns": "dst, or 0 when refused",
        "refusal": "dst == 0, len == 0 or len > 0x7fffffff",
        "semantics": "fill len bytes at dst with (fillbyte & 0xff) through the checked guest memory boundary",
        "source": "public PS1 BIOS function table documentation (PSX-SPX BIOS function summary / memory fill-copy-compare)",
    },
}

#: Documented B0/C0 services are not implemented and stay fail-closed.
DOCUMENTED_B0_SERVICES: dict[int, dict[str, Any]] = {}
DOCUMENTED_C0_SERVICES: dict[int, dict[str, Any]] = {}

#: Public documented *names* for the vector indices observed in this fixture.
#: These are identifiers only: no semantics is determined here, and no service
#: outside DOCUMENTED_A0_SERVICES is implemented. Source: public PS1 BIOS
#: function table documentation (PSX-SPX BIOS function summary).
DOCUMENTED_INDEX_NAMES = {
    ("A0", 0x2B): "memset",
    ("A0", 0x30): "srand",
    ("A0", 0x3F): "printf",
    ("A0", 0x43): "DoExecute",
    ("A0", 0x44): "FlushCache",
    ("A0", 0x49): "GPU_cw",
    ("A0", 0x70): "_bu_init",
    ("B0", 0x3F): "puts",
    ("C0", 0x02): "SysEnqIntRP",
    ("C0", 0x03): "SysDeqIntRP",
}

VECTOR_TABLES = {
    "A0": DOCUMENTED_A0_SERVICES,
    "B0": DOCUMENTED_B0_SERVICES,
    "C0": DOCUMENTED_C0_SERVICES,
}

CLASS_BIOS_VECTOR_SERVICE = "BIOS_VECTOR_SERVICE"
CLASS_BIOS_VECTOR_UNKNOWN_INDEX = "BIOS_VECTOR_UNKNOWN_INDEX"
CLASS_BIOS_VECTOR_NOT_IMPLEMENTED = "BIOS_VECTOR_NOT_IMPLEMENTED"
CLASS_NOT_BIOS = "NOT_BIOS"

DISPOSITION_EXACT_EXTERNAL = "EXACT_EXTERNAL_SERVICE"
DISPOSITION_FAIL_CLOSED = "FAIL_CLOSED"

ERROR_CODES = (
    "INVALID_ANALYSIS",
    "UNKNOWN_VECTOR",
)


class BiosFrontierError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown BIOS frontier error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class BiosVectorSite:
    site: int
    op: str
    kind: str
    source_register: int
    vector: str
    vector_value: int
    function_index: int | None
    service_id: str | None
    op_name: str | None
    classification: str
    disposition: str
    slice_evidence: tuple[str, ...] = ()
    index_evidence: tuple[str, ...] = ()
    function_id: str | None = None
    block_id: str | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "site_hex": f"0x{self.site:08x}",
            "op": self.op,
            "kind": self.kind,
            "source_register": self.source_register,
            "vector": self.vector,
            "vector_value": f"0x{self.vector_value:08x}",
            "function_index": self.function_index,
            "service_id": self.service_id,
            "op_name": self.op_name,
            "classification": self.classification,
            "disposition": self.disposition,
            "slice_evidence": list(self.slice_evidence),
            "index_evidence": list(self.index_evidence),
            "function_id": self.function_id,
            "block_id": self.block_id,
            "documented_name": (
                DOCUMENTED_INDEX_NAMES.get((self.vector, self.function_index))
                if self.function_index is not None else None
            ),
        }


def _vector_for_value(value: int) -> str | None:
    for name, (low, high) in sorted(p10_bios.VECTOR_BASES.items()):
        if value in (low, high):
            return name
    return None


def classify_vector_sites(analysis: dict[str, Any]) -> dict[str, Any]:
    """Classify every reachable indirect-control site against the BIOS vectors."""
    if not isinstance(analysis, dict) or not isinstance(analysis.get("records"), list):
        raise BiosFrontierError("INVALID_ANALYSIS", type(analysis).__name__)
    reachable = set(analysis.get("reachable_addresses") or [])
    sites: list[BiosVectorSite] = []
    for record in sorted(analysis["records"], key=lambda item: item["address"]):
        address = record["address"]
        if address not in reachable:
            continue
        terminator = record.get("terminator")
        if terminator == "indirect-call":
            kind = IndirectControlFlowKind.INDIRECT_CALL
        elif terminator == "indirect-jump":
            kind = IndirectControlFlowKind.INDIRECT_JUMP
        else:
            continue
        operands = record.get("operands") or {}
        source = operands.get("rs")
        if not isinstance(source, int):
            continue
        target, slice_evidence = p10_bios.resolve_constant(analysis, address, source)
        if target is None:
            continue
        vector = _vector_for_value(target)
        if vector is None:
            sites.append(
                BiosVectorSite(
                    site=address,
                    op=record.get("op", ""),
                    kind=kind.value,
                    source_register=source,
                    vector="",
                    vector_value=target,
                    function_index=None,
                    service_id=None,
                    op_name=None,
                    classification=CLASS_NOT_BIOS,
                    disposition=DISPOSITION_FAIL_CLOSED,
                    slice_evidence=slice_evidence,
                )
            )
            continue
        index, index_evidence = p10_bios.delay_slot_index(analysis, address)
        documented = VECTOR_TABLES[vector]
        if index is None:
            sites.append(
                BiosVectorSite(
                    site=address,
                    op=record.get("op", ""),
                    kind=kind.value,
                    source_register=source,
                    vector=vector,
                    vector_value=target,
                    function_index=None,
                    service_id=None,
                    op_name=None,
                    classification=CLASS_BIOS_VECTOR_UNKNOWN_INDEX,
                    disposition=DISPOSITION_FAIL_CLOSED,
                    slice_evidence=slice_evidence,
                    index_evidence=index_evidence,
                )
            )
            continue
        if index not in documented:
            sites.append(
                BiosVectorSite(
                    site=address,
                    op=record.get("op", ""),
                    kind=kind.value,
                    source_register=source,
                    vector=vector,
                    vector_value=target,
                    function_index=index,
                    service_id=None,
                    op_name=None,
                    classification=CLASS_BIOS_VECTOR_NOT_IMPLEMENTED,
                    disposition=DISPOSITION_FAIL_CLOSED,
                    slice_evidence=slice_evidence,
                    index_evidence=index_evidence,
                )
            )
            continue
        suffix = "jump" if kind is IndirectControlFlowKind.INDIRECT_JUMP else "call"
        op_name = f"{suffix}_bios_{vector.lower()}_{index:02x}"
        sites.append(
            BiosVectorSite(
                site=address,
                op=record.get("op", ""),
                kind=kind.value,
                source_register=source,
                vector=vector,
                vector_value=target,
                function_index=index,
                service_id=f"ps1.bios.{vector}.{index:02x}",
                op_name=op_name,
                classification=CLASS_BIOS_VECTOR_SERVICE,
                disposition=DISPOSITION_EXACT_EXTERNAL,
                slice_evidence=slice_evidence,
                index_evidence=index_evidence,
            )
        )

    histogram: dict[str, int] = {}
    for site in sites:
        histogram[site.classification] = histogram.get(site.classification, 0) + 1
    services = [site for site in sites if site.classification == CLASS_BIOS_VECTOR_SERVICE]
    return {
        "bios_version": BIOS_VERSION,
        "site_count": len(sites),
        "histogram": dict(sorted(histogram.items())),
        "sites": [site.to_document() for site in sites],
        "services": [site.to_document() for site in services],
        "service_count": len(services),
        "service_ids": sorted({site.service_id for site in services if site.service_id}),
        "index_register": p10_bios.INDEX_REGISTER,
        "vector_register": p10_bios.VECTOR_REGISTER,
        "documented_a0_services": {
            f"0x{index:02x}": dict(document)
            for index, document in sorted(DOCUMENTED_A0_SERVICES.items())
        },
        "documented_b0_service_count": len(DOCUMENTED_B0_SERVICES),
        "documented_c0_service_count": len(DOCUMENTED_C0_SERVICES),
        "unknown_policy": "fail-closed",
        "bios_image": "none",
    }


def resolved_sites(classification: dict[str, Any]) -> list[BiosVectorSite]:
    """Rebuild the resolved site records from a classification document."""
    sites: list[BiosVectorSite] = []
    for document in classification["services"]:
        sites.append(
            BiosVectorSite(
                site=document["site"],
                op=document["op"],
                kind=document["kind"],
                source_register=document["source_register"],
                vector=document["vector"],
                vector_value=int(document["vector_value"], 16),
                function_index=document["function_index"],
                service_id=document["service_id"],
                op_name=document["op_name"],
                classification=document["classification"],
                disposition=document["disposition"],
                slice_evidence=tuple(document["slice_evidence"]),
                index_evidence=tuple(document["index_evidence"]),
            )
        )
    return sites


def service_arities(sites: list[BiosVectorSite]) -> dict[str, int]:
    """The declared arity of every resolved BIOS service."""
    arities: dict[str, int] = {}
    for site in sites:
        document = VECTOR_TABLES[site.vector][site.function_index]
        arities[site.service_id] = len(document["signature"])
    return arities


def site_plan(classification: dict[str, Any]) -> dict[str, Any]:
    """A deterministic site -> (op name, service id, argument fields) plan."""
    plan: dict[str, Any] = {}
    for document in classification["services"]:
        plan[document["site_hex"]] = {
            "op_name": document["op_name"],
            "service_id": document["service_id"],
            "kind": document["kind"],
            "function_index": document["function_index"],
            "vector": document["vector"],
            "argument_fields": {
                "bios_arg0": BIOS_ARGUMENT_REGISTERS[0],
                "bios_arg1": BIOS_ARGUMENT_REGISTERS[1],
                "bios_arg2": BIOS_ARGUMENT_REGISTERS[2],
                "bios_ret": BIOS_RETURN_REGISTER,
                "bios_index": document["function_index"],
            },
        }
    return plan


def apply_site_plan(analysis: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any]:
    """A copy of the analysis with the resolved BIOS sites renamed and annotated."""
    import copy

    plan = site_plan(classification)
    modified = copy.deepcopy(analysis)
    for record in modified["records"]:
        entry = plan.get(f"0x{record['address']:08x}")
        if entry is None:
            continue
        if record.get("terminator") not in ("indirect-jump", "indirect-call"):
            continue
        record["op"] = entry["op_name"]
        operands = record.setdefault("operands", {})
        operands.update(entry["argument_fields"])
    return modified


def evidence_records(
    classification: dict[str, Any],
    site_units: dict[int, tuple[str, str]],
) -> tuple[IndirectControlFlowEvidence, ...]:
    """Explicit external-runtime evidence for every resolved BIOS site."""
    records: list[IndirectControlFlowEvidence] = []
    for document in classification["services"]:
        site = document["site"]
        unit = site_units.get(site)
        if unit is None:
            continue
        function_id, block_id = unit
        kind = IndirectControlFlowKind(document["kind"])
        detail = "; ".join(
            [
                f"vector={document['vector']}",
                f"vector_value={document['vector_value']}",
                f"function_index={document['function_index']}",
                f"service={document['service_id']}",
                "convention=$t2 vector base, $t1 index in the delay slot",
                *document["slice_evidence"],
                *document["index_evidence"],
            ]
        )
        records.append(
            IndirectControlFlowEvidence(
                function_id=function_id,
                block_id=block_id,
                address=site,
                kind=kind,
                status=IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED,
                basis=IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE,
                external_mechanism=f"ps1.bios.{document['vector']}",
                detail=detail,
                source="phase11-bios-vector-evidence",
                evidence=EvidenceClass.PROVEN,
            )
        )
    return tuple(records)
