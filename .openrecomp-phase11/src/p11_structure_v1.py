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
from openrecomp.indirect_control_flow import classify_indirect_control_flow

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
    terminal_index: dict[int, tuple[str, str]] = {}
    for unit in result.units.units:
        for block in unit.blocks:
            terminal = block.instructions[-1]
            terminal_index[terminal.address] = (unit.function_id, block.id)
    mapping: dict[int, tuple[str, str]] = {}
    for document in classification["services"]:
        site = document["site"]
        unit = terminal_index.get(site)
        if unit is None:
            raise Phase11StructureError("BIOS_SITE_NOT_FOUND", f"0x{site:08x}")
        mapping[site] = unit
    return mapping


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
