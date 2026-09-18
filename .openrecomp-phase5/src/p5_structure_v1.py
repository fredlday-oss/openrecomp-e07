#!/usr/bin/env python3
"""Phase-5 neutral program structure (P5-04).

Bridges the real public fixture into the shared architecture-neutral Phase-2
layers through the frozen `openrecomp.frontends.nes6502` bridge seam:

    adapters.nes6502 decode
      -> P2-01 ProgramModel
      -> P2-02 CFG
      -> P2-03 function discovery
      -> P2-04 call graph
      -> P2-05 translation units
      -> P2-06 indirect-control-flow classification

Reset/NMI/IRQ roots are represented explicitly. The only additional program
entry is the documented BRK continuation (`$C0A8`): the single BRK site pushes
PC+2 (documented 6502 semantics) and the IRQ handler's RTI returns there; it is
recorded as a root, never as a fabricated call target. Indirect targets are
never invented: the one `jmp (indirect)` site stays `UNRESOLVED_INDIRECT_JUMP`
with an empty target set.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p5_frontier_v1 as frontier  # noqa: E402
from openrecomp.call_graph import build_call_graph  # noqa: E402
from openrecomp.cfg import EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.indirect_control_flow import classify_indirect_control_flow  # noqa: E402
from openrecomp.program_model import EvidenceClass, ProgramSource  # noqa: E402
from openrecomp.translation_units import build_translation_units  # noqa: E402
from openrecomp.frontends import nes6502 as bridge  # noqa: E402

BRK_SITE = 0xC0A6
BRK_CONTINUATION = 0xC0A8


def _call_site_addresses(instructions) -> dict[int, int]:
    sites: dict[int, int] = {}
    for instruction in instructions:
        if instruction.flow.value == "CALL" and instruction.direct_target is not None:
            sites[instruction.address] = instruction.direct_target
    return sites


def build_structure(rom: bytes, metadata: dict, inventory: dict) -> dict[str, Any]:
    image = frontier.build_cpu_image(rom, 16, metadata["prg_size"])
    region_start, region_end = frontier.code_region_from_metadata(metadata)
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
        "reset": {
            "address": vectors["reset"],
            "basis": "reset vector 0xFFFC/0xFFFD",
        },
        "nmi": {
            "address": vectors["nmi"],
            "basis": "NMI vector 0xFFFA/0xFFFB",
        },
        "irq": {
            "address": vectors["irq"],
            "basis": "IRQ/BRK vector 0xFFFE/0xFFFF",
        },
        "brk_continuation": {
            "address": BRK_CONTINUATION,
            "basis": "BRK at 0xC0A6 pushes PC+2 (documented); the IRQ handler "
                     "RTI returns to 0xC0A8",
        },
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

    reachable = frontier.reachable_frontier(
        image, [vectors["reset"], vectors["nmi"], vectors["irq"]])
    reachable_addresses = set(reachable["reachable_addresses"])
    neutral_addresses = {instruction.address for instruction in instructions}
    extra_instructions = sorted(neutral_addresses - reachable_addresses)
    missing_instructions = sorted(reachable_addresses - neutral_addresses)

    call_edges = []
    for edge in call_graph.edges:
        call_edges.append({
            "kind": edge.kind.value,
            "caller": edge.caller,
            "callee": edge.callee,
        })
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
    trap_sites = [instruction.address for instruction in instructions
                  if instruction.flow.value == "TRAP"]

    return {
        "stage": "P5-04",
        "source": "original public fixture (Apache-2.0)",
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
        "call_edges": call_edges,
        "translation_units": len(units.units),
        "indirect_classifications": indirect,
        "trap_sites": sorted(trap_sites),
        "unowned_control_flow": list(classification.to_document()["unowned_control_flow"]),
        "neutral_addresses": sorted(neutral_addresses),
        "reachable_addresses": sorted(reachable_addresses),
        "extra_instructions": extra_instructions,
        "missing_instructions": missing_instructions,
        "boundary_violations": boundary_violations,
    }


__all__ = [
    "BRK_CONTINUATION",
    "BRK_SITE",
    "build_structure",
]
