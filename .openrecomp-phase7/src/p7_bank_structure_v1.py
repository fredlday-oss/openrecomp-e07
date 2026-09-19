#!/usr/bin/env python3
"""Phase-7 bank-aware neutral ProgramModel / CFG integration (P7-05).

Builds one architecture-neutral structure per proven physical PRG bank
identity from the P7-04 bank-aware reachability result, using only the shared
architecture-neutral layers (`openrecomp.program_model`, `openrecomp.cfg`,
`openrecomp.functions`, `openrecomp.call_graph`,
`openrecomp.translation_units`, `openrecomp.indirect_control_flow`) through
the frozen `openrecomp.frontends.nes6502` bridge:

* instructions are decoded per bank identity; two physical banks sharing a CPU
  address never share an instruction object or CFG;
* direct targets that leave the bank identity are cross-checked against the
  bank-aware reachability edges and are never fabricated: a target without a
  proven model edge fails closed;
* cross-bank call entries are supplied as explicit PROVEN entry points to the
  destination bank's structure, so function discovery sees the real cross-bank
  call without inventing an address edge inside a bank;
* unresolved indirect sites carry no fabricated targets.

The neutral layers are not modified; the bank wrapper is additive.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p7_bank_reachability_v1 as bank_model  # noqa: E402
from openrecomp.call_graph import build_call_graph  # noqa: E402
from openrecomp.cfg import CFGMode, EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.indirect_control_flow import classify_indirect_control_flow  # noqa: E402
from openrecomp.program_model import EvidenceClass, ProgramSource  # noqa: E402
from openrecomp.translation_units import build_translation_units  # noqa: E402
from openrecomp.frontends import nes6502 as bridge  # noqa: E402

PROVEN = bank_model.PROVEN
UNRESOLVED = bank_model.UNRESOLVED


class P7BankStructureError(ValueError):
    """Fail-closed bank-aware structure error."""


def _bank_bytes(prg: bytes, prg_banks: int, bank: int) -> bytes:
    if not 0 <= bank < prg_banks:
        raise P7BankStructureError(f"bank {bank} out of range")
    return bytes(prg[bank * bank_model.PRG_BANK_BYTES:
                     (bank + 1) * bank_model.PRG_BANK_BYTES])


def build(prg: bytes, prg_banks: int, reachability: dict[str, Any], *,
          roots: list[int]) -> dict[str, Any]:
    if reachability.get("status") != "OK":
        raise P7BankStructureError(
            f"reachability is not OK: {reachability.get('status')!r}")
    instructions = reachability["instructions"]
    edges = reachability["edges"]
    proven = [entry for entry in instructions
              if entry["provenance"] == PROVEN]
    if not proven:
        raise P7BankStructureError("no proven code identities")
    cross_edges = [edge for edge in edges
                   if edge["provenance"] == PROVEN
                   and edge["dst_bank"] is not None
                   and edge["src_bank"] != edge["dst_bank"]]
    by_bank: dict[int, list[dict[str, Any]]] = {}
    for entry in proven:
        by_bank.setdefault(entry["bank"], []).append(entry)

    bank_documents: list[dict[str, Any]] = []
    for bank in sorted(by_bank):
        entries_for_bank = sorted(by_bank[bank],
                                  key=lambda item: item["address"])
        image = bank_model.image_for_bank(prg, prg_banks, bank)
        decoded = []
        for entry in entries_for_bank:
            try:
                decoded.append(bridge.instruction_from_nes6502(
                    image, entry["address"], evidence=EvidenceClass.PROVEN))
            except bridge.NES6502BridgeError as exc:
                raise P7BankStructureError(
                    f"bank {bank} instruction 0x{entry['address']:04x} cannot "
                    f"be bridged: {exc}") from exc
        internal = {instruction.address for instruction in decoded}
        cross_in = sorted({edge["dst_address"] for edge in cross_edges
                           if edge["dst_bank"] == bank
                           and edge["dst_address"] in internal})
        entry_addresses = sorted(
            ({address for address in roots if address in internal}
             | set(cross_in)))
        if not entry_addresses:
            raise P7BankStructureError(
                f"bank {bank} has no entry point in its proven code")
        source = ProgramSource(
            "nes6502",
            adapter="adapters.nes6502",
            address_width_bits=16,
            endianness="little",
            input_sha256=hashlib.sha256(
                _bank_bytes(prg, prg_banks, bank)).hexdigest(),
        )
        try:
            cfg = build_cfg(
                decoded,
                source=source,
                entries=[EntryPoint(address, EvidenceClass.PROVEN)
                         for address in entry_addresses],
                mode=CFGMode.OPEN,
            )
            discovery = discover_functions(cfg,
                                           program_entries=entry_addresses)
            call_graph = build_call_graph(discovery)
            units = build_translation_units(discovery, call_graph=call_graph)
            classification = classify_indirect_control_flow(units)
        except (ValueError, KeyError) as exc:
            raise P7BankStructureError(
                f"bank {bank} neutral structure failed: {exc}") from exc

        external_targets: list[dict[str, Any]] = []
        for instruction in decoded:
            target = instruction.direct_target
            if target is None or target in internal:
                continue
            matches = [edge for edge in cross_edges
                       if edge["src_bank"] == bank
                       and edge["src_address"] == instruction.address
                       and edge["dst_address"] == target]
            if not matches:
                raise P7BankStructureError(
                    f"bank {bank} 0x{instruction.address:04x}: direct target "
                    f"0x{target:04x} has no proven bank-qualified edge "
                    "(fabricated cross-bank edge rejected)")
            external_targets.append({
                "address": instruction.address,
                "op": instruction.op,
                "target": target,
                "dst_bank": matches[0]["dst_bank"],
                "kind": matches[0]["kind"],
            })

        indirect_document = classification.to_document()
        indirect_sites = []
        for unit in indirect_document["units"]:
            for site in unit["classifications"]:
                indirect_sites.append({
                    "unit_id": site["unit_id"],
                    "address": site["address"],
                    "op": site["op"],
                    "kind": site["kind"],
                    "status": site["status"],
                    "targets": site["targets"],
                })
                if site["status"] != "RESOLVED" and site["targets"]:
                    raise P7BankStructureError(
                        f"bank {bank} 0x{site['address']:04x}: unresolved "
                        "indirect site carries fabricated targets")

        call_sites = [
            {"address": site.address, "target": site.target_address,
             "op": site.op}
            for site in cfg.direct_call_sites
        ]
        function_entries = sorted(
            function.entry_address for function in discovery.functions)
        for target in cross_in:
            if target not in function_entries:
                raise P7BankStructureError(
                    f"bank {bank}: cross-bank entry 0x{target:04x} was not "
                    "discovered as a function")
        bank_documents.append({
            "bank": bank,
            "bank_sha256": hashlib.sha256(
                _bank_bytes(prg, prg_banks, bank)).hexdigest(),
            "proven_instructions": len(decoded),
            "entry_addresses": entry_addresses,
            "cross_bank_entries": cross_in,
            "external_targets": external_targets,
            "blocks": len(cfg.blocks),
            "cfg_fingerprint": cfg.fingerprint(),
            "discovery_fingerprint": discovery.fingerprint(),
            "call_graph_fingerprint": call_graph.fingerprint(),
            "units_fingerprint": units.fingerprint(),
            "classification_fingerprint": classification.fingerprint(),
            "functions": len(discovery.functions),
            "function_entries": function_entries,
            "translation_units": len(units.units),
            "call_sites": call_sites,
            "call_edges": [{"kind": edge.kind.value, "caller": edge.caller,
                            "callee": edge.callee}
                           for edge in call_graph.edges],
            "indirect_sites": indirect_sites,
            "unowned_control_flow": list(
                indirect_document["unowned_control_flow"]),
        })
    return {
        "stage": "P7-05",
        "architecture": "nes6502",
        "banks": bank_documents,
        "bank_count": len(bank_documents),
        "cross_bank_edges": cross_edges,
        "cross_bank_edge_count": len(cross_edges),
        "rejected_unresolved_identities": [
            entry for entry in instructions
            if entry["provenance"] != PROVEN],
        "claim": "bank-qualified neutral structure; only PROVEN physical-bank "
                 "code identities are represented and no cross-bank edge is "
                 "fabricated",
    }


__all__ = ["P7BankStructureError", "build"]
