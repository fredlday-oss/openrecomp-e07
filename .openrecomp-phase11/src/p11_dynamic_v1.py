#!/usr/bin/env python3
"""OpenRecomp Phase-11 dynamic target resolution V1.

Two additive capabilities, both evidence-bounded:

* **frontier extension**: the frozen Phase-3 code frontier is re-run from an
  additional proven entry point and merged with the inherited frontier. The
  records must agree exactly (same region, same decoder) and the reachable set
  and delay-slot set are unioned; a disagreement fails closed.
* **dynamic target resolution**: an unresolved indirect site is resolved only
  when its source value was observed deterministically at runtime *and* the
  observed value is a valid instruction boundary inside the extended reachable
  set. The resolution is emitted as an explicit ``RESOLVED`` classification
  with a guarded dispatch (the emitter's ``guarded_resolved_indirect`` option),
  so any other runtime value still fails closed. No target is guessed.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

import p3_code_frontier_v1 as frontier
from openrecomp.indirect_control_flow import (
    IndirectControlFlowBasis,
    IndirectControlFlowEvidence,
    IndirectControlFlowKind,
    IndirectControlFlowStatus,
)
from openrecomp.program_model import EvidenceClass

DYNAMIC_VERSION = "1.0.0"

ERROR_CODES = (
    "RECORD_MISMATCH",
    "DELAY_SLOT_MISMATCH",
    "INVALID_ENTRY",
    "OBSERVED_TARGET_NOT_REACHABLE",
    "OBSERVED_TARGET_NOT_ALIGNED",
)


class DynamicResolutionError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown dynamic resolution error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _decode_fields(record: dict[str, Any]) -> dict[str, Any]:
    """The decoder-derived fields of a frontier record (reachability excluded)."""
    return {key: value for key, value in record.items() if key != "reachability"}


def extend_analysis(
    base_analysis: dict[str, Any],
    read_word: Callable[[int], int],
    start: int,
    end: int,
    extra_entries: tuple[int, ...],
) -> tuple[dict[str, Any], dict[str, Any], tuple[tuple[int, dict[str, Any]], ...]]:
    """Merge the inherited frontier with frontiers discovered from extra entries.

    Returns the merged analysis, the extension provenance document and the
    per-entry analyses (used to build the neutral instruction streams).
    """
    if not extra_entries:
        raise DynamicResolutionError("INVALID_ENTRY", "no extra entries")
    base_records = {record["address"]: record for record in base_analysis["records"]}
    reachable = set(base_analysis["reachable_addresses"])
    delay_slots: dict[int, dict[str, Any]] = {
        item["owner"]: item for item in base_analysis["delay_slots"]
    }
    entry_records: list[dict[str, Any]] = []
    extra_analyses: list[tuple[int, dict[str, Any]]] = []
    for entry in sorted(extra_entries):
        if entry & 3 or not (start <= entry < end):
            raise DynamicResolutionError("INVALID_ENTRY", f"0x{entry:08x}")
        extra = frontier.analyze(read_word, start, end, entry)
        for record in extra["records"]:
            address = record["address"]
            known = base_records.get(address)
            if known is not None and _decode_fields(known) != _decode_fields(record):
                raise DynamicResolutionError("RECORD_MISMATCH", f"0x{address:08x}")
        for slot in extra["delay_slots"]:
            known = delay_slots.get(slot["owner"])
            if known is not None and known != slot:
                raise DynamicResolutionError("DELAY_SLOT_MISMATCH", f"0x{slot['owner']:08x}")
            delay_slots[slot["owner"]] = slot
        new_reachable = set(extra["reachable_addresses"]) - reachable
        reachable |= set(extra["reachable_addresses"])
        entry_records.append(
            {
                "entry": f"0x{entry:08x}",
                "reachable_words": len(extra["reachable_addresses"]),
                "new_reachable_words": len(new_reachable),
            }
        )
        extra_analyses.append((entry, extra))

    all_addresses = sorted(base_records)
    merged = dict(base_analysis)
    merged["reachable_addresses"] = sorted(reachable)
    merged["unreachable_addresses"] = sorted(set(all_addresses) - reachable)
    merged["delay_slots"] = [delay_slots[owner] for owner in sorted(delay_slots)]
    merged["records"] = [base_records[address] for address in all_addresses]
    for record in merged["records"]:
        record["reachability"] = (
            frontier.REACHABLE if record["address"] in reachable else frontier.UNREACHABLE
        )
    document = {
        "dynamic_version": DYNAMIC_VERSION,
        "base_entry": f"0x{base_analysis['entry']:08x}",
        "base_reachable_words": len(base_analysis["reachable_addresses"]),
        "extra_entries": entry_records,
        "merged_reachable_words": len(merged["reachable_addresses"]),
        "record_count": len(merged["records"]),
        "delay_slot_count": len(merged["delay_slots"]),
        "merged_reachable_sha256": hashlib.sha256(
            json.dumps(merged["reachable_addresses"]).encode("utf-8")
        ).hexdigest(),
    }
    return merged, document, tuple(extra_analyses)


def resolve_sites(
    analysis: dict[str, Any],
    *,
    observations: dict[int, tuple[int, ...]],
    site_units: dict[int, tuple[str, str]],
) -> tuple[tuple[IndirectControlFlowEvidence, ...], dict[str, Any]]:
    """Explicit RESOLVED evidence for dynamically proven indirect targets."""
    reachable = set(analysis["reachable_addresses"])
    records = {record["address"]: record for record in analysis["records"]}
    evidence: list[IndirectControlFlowEvidence] = []
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for site in sorted(observations):
        values = tuple(sorted(set(observations[site])))
        record = records.get(site)
        unit = site_units.get(site)
        if record is None or unit is None:
            unresolved.append({"site": f"0x{site:08x}", "reason": "site-not-in-structure"})
            continue
        kind = (
            IndirectControlFlowKind.INDIRECT_CALL
            if record.get("terminator") == "indirect-call"
            else IndirectControlFlowKind.INDIRECT_JUMP
        )
        for value in values:
            if value & 3:
                raise DynamicResolutionError("OBSERVED_TARGET_NOT_ALIGNED", f"0x{value:08x}")
            if value not in reachable:
                raise DynamicResolutionError("OBSERVED_TARGET_NOT_REACHABLE", f"0x{value:08x}")
        basis = (
            IndirectControlFlowBasis.EXACT_CONSTANT_TARGET
            if len(values) == 1
            else IndirectControlFlowBasis.EXACT_TARGET_SET
        )
        function_id, block_id = unit
        detail = "; ".join(
            [
                f"observed_targets={','.join(f'0x{value:08x}' for value in values)}",
                "observed deterministically at runtime",
                "every observed target is a reachable instruction boundary",
                "guarded dispatch: any other runtime value fails closed",
            ]
        )
        evidence.append(
            IndirectControlFlowEvidence(
                function_id=function_id,
                block_id=block_id,
                address=site,
                kind=kind,
                status=IndirectControlFlowStatus.RESOLVED,
                basis=basis,
                targets=values,
                detail=detail,
                source="phase11-dynamic-execution-evidence",
                evidence=EvidenceClass.PROVEN,
            )
        )
        resolved.append(
            {
                "site": f"0x{site:08x}",
                "kind": kind.value,
                "targets": [f"0x{value:08x}" for value in values],
                "basis": basis.value,
                "guarded": True,
            }
        )
    document = {
        "dynamic_version": DYNAMIC_VERSION,
        "resolved": resolved,
        "resolved_count": len(resolved),
        "unresolved": unresolved,
        "unresolved_count": len(unresolved),
        "policy": "a target is resolved only when observed deterministically and reachable",
    }
    return tuple(evidence), document
