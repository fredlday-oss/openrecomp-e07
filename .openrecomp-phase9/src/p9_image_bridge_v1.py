#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1-to-MIPS32 pipeline bridge V1.

The bridge feeds a validated PS-X EXE image, through its explicit PS1
address-space contract, into the existing frozen Phase-8 MIPS32 pipeline:

    p3_code_frontier_v1.analyze
        -> p8_structure_v1.analyze_structure
        -> shared ProgramModel / CFG / functions / call graph / units

No MIPS pipeline is forked or duplicated: the frozen Phase-3 decode/frontier
and the frozen Phase-8 neutral-structure bridge are used unchanged. The bridge
records exact reachable-frontier and structure counts, and classifies
unresolved indirect control flow and unsupported control transfers explicitly
instead of guessing.

This module performs static analysis only; it executes nothing.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import p3_code_frontier_v1 as frontier
import p8_structure_v1 as structure_bridge
import p9_memory_map_v1 as memory_map
import p9_psx_exe_v1 as psx
from openrecomp.program_model import ProgramSource

BRIDGE_VERSION = "1.0.0"

ARCHITECTURE = "mips32-bounded-v1"


@dataclass
class PipelineResult:
    """Deterministic result of the PS1-to-MIPS32 static pipeline."""

    frontier: dict[str, Any]
    summary: dict[str, Any]
    structure: Any = None
    structure_summary: dict[str, Any] | None = None
    structure_error: dict[str, str] | None = None
    first_blocker: dict[str, Any] | None = None
    source: ProgramSource | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "bridge_version": BRIDGE_VERSION,
            "frontier": self.frontier,
            "summary": self.summary,
            "structure_summary": self.structure_summary,
            "structure_error": self.structure_error,
            "first_blocker": self.first_blocker,
        }

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.to_document(), sort_keys=True).encode("utf-8")
        ).hexdigest()


def _first_blocker(analysis: dict[str, Any]) -> dict[str, Any] | None:
    unresolved = analysis.get("unresolved") or []
    if unresolved:
        item = sorted(unresolved, key=lambda entry: (entry.get("site", 0), entry.get("kind", "")))[0]
        return {
            "site": item.get("site"),
            "site_hex": f"0x{item.get('site', 0):08x}",
            "kind": item.get("kind"),
            "op": item.get("op"),
            "detail": item.get("detail") or item.get("note"),
        }
    return None


def analyze(image: psx.PsxExeImage, contract: dict[str, Any], flat: bytes) -> PipelineResult:
    """Run the frozen MIPS32 pipeline over the reachable executable frontier."""
    header = image.header
    analysis = frontier.analyze(
        lambda address: memory_map.read_u32(contract, flat, address),
        header.t_addr,
        header.t_addr + header.t_size,
        header.pc0,
    )
    summary = dict(analysis["summary"])
    summary["delay_slot_count"] = len(analysis["delay_slots"])
    summary["non_nop_delay_slot_count"] = sum(
        1
        for slot in analysis["delay_slots"]
        if _record_at(analysis, slot["delay"])["word"] != 0
    )
    summary["reachable_op_histogram"] = {
        op: count
        for op, count in sorted(
            _histogram(
                record["op"]
                for record in analysis["records"]
                if record["reachability"] == frontier.REACHABLE
            ).items()
        )
    }
    summary["reachable_decode_classes"] = dict(
        sorted(
            _histogram(
                record["decode_class"]
                for record in analysis["records"]
                if record["reachability"] == frontier.REACHABLE
            ).items()
        )
    )

    source = ProgramSource(
        ARCHITECTURE,
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=image.file_sha256,
    )
    result = PipelineResult(
        frontier={
            "entry": f"0x{header.pc0:08x}",
            "text": f"0x{header.t_addr:08x}+{header.t_size}",
            "region_words": (header.t_size // 4),
        },
        summary=summary,
        first_blocker=_first_blocker(analysis),
        source=source,
    )

    try:
        structure = structure_bridge.analyze_structure(analysis, source=source, entry=header.pc0)
    except structure_bridge.P8StructureError as exc:
        result.structure_error = {"code": exc.code, "detail": exc.detail}
        return result

    result.structure = structure
    result.structure_summary = structure_bridge.structure_summary(structure)
    return result


def _histogram(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _record_at(analysis: dict[str, Any], address: int) -> dict[str, Any]:
    for record in analysis["records"]:
        if record["address"] == address:
            return record
    raise KeyError(f"no record at 0x{address:08x}")
