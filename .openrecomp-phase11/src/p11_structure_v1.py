#!/usr/bin/env python3
"""OpenRecomp Phase-11 structure bridge with the BIOS vector overlay V1.

The frozen Phase-10 exception-aware structure bridge is reused unchanged for
everything it already models. This bridge adds exactly one deterministic
pre-processing step:

* an analysis copy is annotated with the Phase-11 BIOS site plan (the neutral
  op of a site proven to be a documented BIOS vector service is renamed to the
  site-specific neutral op, and the audited argument/return register fields are
  attached to the record's operands);
* the modified analysis is fed through the frozen Phase-10 bridge, so the whole
  shared ProgramModel -> CFG -> functions -> call graph -> translation units
  pipeline is the same code;
* the shared indirect-control classifier is then re-run with the explicit
  external-runtime evidence records, so the resolved BIOS sites carry
  ``EXTERNAL_OR_RUNTIME_MEDIATED`` with a documented mechanism.

No target is guessed: only sites whose vector base and function index both
resolve to constants and whose (vector, index) pair is documented are renamed.
Everything else keeps the frozen fail-closed classification.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import p10_structure_v1 as p10_structure
import p11_bios_v1 as bios
from openrecomp.call_graph import build_call_graph
from openrecomp.cfg import CFGMode, EntryPoint, build_cfg
from openrecomp.functions import discover_functions
from openrecomp.indirect_control_flow import classify_indirect_control_flow
from openrecomp.program_model import EvidenceClass
from openrecomp.translation_units import build_translation_units

PROVEN = EvidenceClass.PROVEN

STRUCTURE_VERSION = "1.1.0"

ERROR_CODES = (
    "BIOS_SITE_NOT_FOUND",
    "BIOS_SITE_KIND_MISMATCH",
    "BIOS_EVIDENCE_REJECTED",
)


class Phase11StructureError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown Phase-11 structure error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _site_units(result: Any, classification: dict[str, Any]) -> dict[int, tuple[str, str]]:
    """Map every resolved BIOS site address to its (function_id, block_id)."""
    mapping: dict[int, tuple[str, str]] = {}
    terminals = terminal_units(result)
    for document in classification["services"]:
        site = document["site"]
        unit = terminals.get(site)
        if unit is None:
            raise Phase11StructureError("BIOS_SITE_NOT_FOUND", f"0x{site:08x}")
        mapping[site] = unit
    return mapping


def terminal_units(result: Any) -> dict[int, tuple[str, str]]:
    """Map every block terminal address to its (function_id, block_id)."""
    index: dict[int, tuple[str, str]] = {}
    for unit in result.units.units:
        for block in unit.blocks:
            index[block.instructions[-1].address] = (unit.function_id, block.id)
    return index


def analyze_structure_with_overlays(
    base_analysis: dict[str, Any],
    *,
    source: Any,
    entry: int,
    services: dict[str, dict[int, dict[str, Any]]] | None = None,
    dynamic_observations: dict[int, tuple[int, ...]] | None = None,
    extensions: tuple[tuple[int, dict[str, Any]], ...] = (),
    merged_analysis: dict[str, Any] | None = None,
) -> tuple[Any, dict[str, Any], dict[str, Any] | None]:
    """The frozen Phase-10 structure plus the BIOS and dynamic-target overlays.

    ``extensions`` are additional proven code entry points with their own
    frontier analyses (for example a statically initialized driver-method
    pointer). The validated neutral instruction streams from the frozen
    Phase-10 bridge are reused verbatim per region; the graph layers are
    rebuilt with the extended entry set. ``merged_analysis`` supplies the
    merged reachable set for classification and evidence.
    """
    import p11_dynamic_v1 as dynamic

    classification_analysis = merged_analysis if merged_analysis is not None else base_analysis
    site_classification = bios.classify_vector_sites(classification_analysis, services=services)
    base = p10_structure.analyze_structure(
        bios.apply_site_plan(base_analysis, bios.classify_vector_sites(base_analysis, services=services)),
        source=source,
        entry=entry,
    )
    if extensions:
        stream_by_address = {instruction.address: instruction for instruction in base.cfg.instructions}
        entries = [entry]
        for extra_entry, extra_analysis in extensions:
            extra_sites = bios.classify_vector_sites(extra_analysis, services=services)
            extra_result = p10_structure.analyze_structure(
                bios.apply_site_plan(extra_analysis, extra_sites), source=source, entry=extra_entry
            )
            for instruction in extra_result.cfg.instructions:
                existing = stream_by_address.get(instruction.address)
                if existing is not None and existing != instruction:
                    raise Phase11StructureError(
                        "BIOS_SITE_KIND_MISMATCH", f"0x{instruction.address:08x}"
                    )
                stream_by_address[instruction.address] = instruction
            entries.append(extra_entry)
        stream = tuple(stream_by_address[address] for address in sorted(stream_by_address))
        cfg = build_cfg(
            stream,
            source=source,
            entries=[EntryPoint(item, PROVEN) for item in entries],
            mode=CFGMode.CLOSED,
        )
        discovery = discover_functions(cfg, program_entries=entries, include_direct_call_targets=True)
        call_graph = build_call_graph(discovery)
        units = build_translation_units(discovery, call_graph=call_graph)
        base = dataclasses.replace(
            base, cfg=cfg, discovery=discovery, call_graph=call_graph, units=units
        )
    evidence = list(bios.evidence_records(site_classification, _site_units(base, site_classification)))
    dynamic_document = None
    if dynamic_observations:
        bios_sites = {document["site"] for document in site_classification["services"]}
        overlap = sorted(set(dynamic_observations) & bios_sites)
        if overlap:
            raise Phase11StructureError("BIOS_SITE_KIND_MISMATCH", f"overlap at 0x{overlap[0]:08x}")
        dynamic_evidence, dynamic_document = dynamic.resolve_sites(
            classification_analysis, observations=dynamic_observations, site_units=terminal_units(base)
        )
        evidence.extend(dynamic_evidence)
    try:
        classification = classify_indirect_control_flow(base.units, evidence=tuple(evidence))
    except Exception as exc:  # fail closed with a stable code
        raise Phase11StructureError("BIOS_EVIDENCE_REJECTED", f"{type(exc).__name__}: {exc}") from exc
    result = dataclasses.replace(base, classification=classification)
    document = dict(site_classification)
    document["structure_version"] = STRUCTURE_VERSION
    document["resolved_op_names"] = sorted(
        {item["op_name"] for item in site_classification["services"] if item["op_name"]}
    )
    return result, document, dynamic_document


def analyze_structure_with_bios(analysis: dict[str, Any], *, source: Any, entry: int,
                                services: dict[str, dict[int, dict[str, Any]]] | None = None
                                ) -> tuple[Any, dict[str, Any]]:
    """The frozen Phase-10 structure plus the Phase-11 BIOS vector overlay."""
    site_classification = bios.classify_vector_sites(analysis, services=services)
    modified = bios.apply_site_plan(analysis, site_classification)
    base = p10_structure.analyze_structure(modified, source=source, entry=entry)
    site_units = _site_units(base, site_classification)
    evidence = bios.evidence_records(site_classification, site_units)
    try:
        classification = classify_indirect_control_flow(base.units, evidence=evidence)
    except Exception as exc:  # fail closed with a stable code
        raise Phase11StructureError("BIOS_EVIDENCE_REJECTED", f"{type(exc).__name__}: {exc}") from exc
    result = dataclasses.replace(base, classification=classification)
    document = dict(site_classification)
    document["structure_version"] = STRUCTURE_VERSION
    document["resolved_op_names"] = sorted(
        {item["op_name"] for item in site_classification["services"] if item["op_name"]}
    )
    return result, document


def site_units_document(site_units: dict[int, tuple[str, str]]) -> dict[str, Any]:
    return {
        f"0x{site:08x}": {"function_id": unit[0], "block_id": unit[1]}
        for site, unit in sorted(site_units.items())
    }
