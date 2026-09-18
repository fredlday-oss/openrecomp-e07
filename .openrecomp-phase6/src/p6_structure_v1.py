#!/usr/bin/env python3
"""Phase-6 neutral program structure for the public MMC1 proof fixture.

Bridges the fixed-bank code of the proof fixture into the shared
architecture-neutral ProgramModel / CFG / function-discovery / call-graph /
translation-unit / indirect-control-flow layers through the frozen
`openrecomp.frontends.nes6502` seam, exactly as Phase 5 did for the NROM
fixture. Reset/NMI/IRQ roots are explicit; the single declared page-wrap
run-exit thunk stays an unresolved indirect site with no fabricated targets.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_frontier_v1 as p6_frontier  # noqa: E402
from openrecomp.call_graph import build_call_graph  # noqa: E402
from openrecomp.cfg import EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.indirect_control_flow import classify_indirect_control_flow  # noqa: E402
from openrecomp.program_model import EvidenceClass, ProgramSource  # noqa: E402
from openrecomp.translation_units import build_translation_units  # noqa: E402
from openrecomp.frontends import nes6502 as bridge  # noqa: E402


class P6StructureError(ValueError):
    """Fail-closed Phase-6 structure error."""


def _call_site_addresses(instructions) -> dict[int, int]:
    sites: dict[int, int] = {}
    for instruction in instructions:
        if instruction.flow.value == "CALL" and instruction.direct_target is not None:
            sites[instruction.address] = instruction.direct_target
    return sites


def build_structure(rom: bytes, metadata: dict, inventory: dict) -> dict[str, Any]:
    image = p6_frontier.build_mmc1_cpu_image(rom, metadata)
    region_start, region_end = p6_frontier.code_region(metadata)
    instructions = bridge.bridge_region(image, entry=region_start, end=region_end)
    region_bytes = bytes(image[region_start:region_end])
    source = ProgramSource(
        "nes6502",
        adapter="adapters.nes6502",
        address_width_bits=16,
        endianness="little",
        input_sha256=hashlib.sha256(region_bytes).hexdigest(),
    )
    vectors = inventory["vectors"]
    roots = {
        "reset": {"address": vectors["reset"],
                  "basis": "reset vector 0xFFFC/0xFFFD"},
        "nmi": {"address": vectors["nmi"],
                "basis": "NMI vector 0xFFFA/0xFFFB"},
        "irq": {"address": vectors["irq"],
                "basis": "IRQ/BRK vector 0xFFFE/0xFFFF"},
    }
    entry_addresses = [item["address"] for item in roots.values()]
    cfg = build_cfg(
        instructions,
        source=source,
        entries=[EntryPoint(address, EvidenceClass.PROVEN)
                 for address in entry_addresses],
    )
    discovery = discover_functions(cfg, program_entries=entry_addresses)
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)
    classification = classify_indirect_control_flow(units)

    call_sites = _call_site_addresses(instructions)
    allowed_function_entries = set(entry_addresses) | set(call_sites.values())
    function_entries = [function.entry_address for function in discovery.functions]
    boundary_violations = [address for address in function_entries
                           if address not in allowed_function_entries]

    reachable = p6_frontier.analysis(rom, metadata, inventory)
    reachable_addresses = set(reachable["code_span"]["dead_addresses"])
    linear = set()
    for instruction in instructions:
        linear.add(instruction.address)
    neutral_addresses = {instruction.address for instruction in instructions}
    dead_set = set(reachable["code_span"]["dead_addresses"])
    called = set(call_sites)

    indirect = []
    for item in classification.to_document()["units"]:
        for entry in item["classifications"]:
            indirect.append({
                "unit_id": entry["unit_id"],
                "entry_address": entry["entry_address"],
                "address": entry["address"],
                "op": entry["op"],
                "kind": entry["kind"],
                "status": entry["status"],
                "targets": entry["targets"],
                "target_functions": entry["target_functions"],
                "basis": entry["basis"],
            })
    unresolved_sites = [entry for entry in indirect
                        if entry["status"] != "RESOLVED"]
    for entry in unresolved_sites:
        if entry["targets"]:
            raise P6StructureError(
                f"unresolved indirect site at 0x{entry['address']:04x} carries "
                "fabricated targets")

    return {
        "stage": "P6-07",
        "source": "original public MMC1 proof fixture (Apache-2.0)",
        "region": [region_start, region_end],
        "region_sha256": hashlib.sha256(region_bytes).hexdigest(),
        "roots": roots,
        "entry_addresses": entry_addresses,
        "instructions": len(instructions),
        "blocks": len(cfg.blocks),
        "cfg_fingerprint": cfg.fingerprint(),
        "discovery_fingerprint": discovery.fingerprint(),
        "call_graph_fingerprint": call_graph.fingerprint(),
        "units_fingerprint": units.fingerprint(),
        "classification_fingerprint": classification.fingerprint(),
        "function_entries": sorted(function_entries),
        "function_ids": [function.id for function in discovery.functions],
        "call_sites": [{"address": address, "target": target}
                       for address, target in sorted(call_sites.items())],
        "call_edges": [{"kind": edge.kind.value, "caller": edge.caller,
                        "callee": edge.callee} for edge in call_graph.edges],
        "translation_units": len(units.units),
        "indirect_classifications": indirect,
        "trap_sites": [],
        "unowned_control_flow": list(
            classification.to_document()["unowned_control_flow"]),
        "neutral_addresses": sorted(neutral_addresses),
        "dead_in_span": sorted(dead_set),
        "boundary_violations": boundary_violations,
        "indirect_site_count": len(indirect),
    }


__all__ = ["P6StructureError", "build_structure"]
