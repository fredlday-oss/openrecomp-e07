#!/usr/bin/env python3
"""Phase-7 translation-frontier integration (P7-08).

Integrates the proven P7-02..P7-07 results into the static recompilation
pipeline for the public Phase-7 fixtures:

* bank-aware reachability (P7-04) fixes the physical-bank identities;
* the inline-dispatch classification (P7-02/P7-03) excludes data regions the
  documented decoder rejects;
* the indirect evidence model (P7-06/P7-07) supplies explicit resolved target
  sets; the frontier walk follows the assignment's proven target for each
  `RESOLVED_EXACT` / `RESOLVED_FINITE_SET` site and *stops* at
  `UNRESOLVED`/`IMPOSSIBLE` sites (fail closed);
* host code is emitted only for the resulting proven paths through the frozen
  Phase-5 CPU emitter and the Phase-6 MMC1 runtime support; any unresolved
  site, undecodable node, unresolved bank provenance or CPU-address collision
  across banks fails closed with an explicit frontier entry and no artifact.
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

import adapters.nes6502 as nes  # noqa: E402
import p5_frontier_v1 as frozen_frontier  # noqa: E402
import p6_emit_v1 as emit_module  # noqa: E402
from openrecomp.frontends import nes6502 as bridge  # noqa: E402
from openrecomp.program_model import (  # noqa: E402
    DecodedInstruction,
    EvidenceClass,
    InstructionFlow,
)

PROVEN = "PROVEN"
UNRESOLVED = "UNRESOLVED"
RESOLVED_EXACT = "RESOLVED_EXACT"
RESOLVED_FINITE_SET = "RESOLVED_FINITE_SET"
IMPOSSIBLE = "IMPOSSIBLE"

FIXED_WINDOW_START = 0xC000
LOW_WINDOW = 0x8000


class P7IntegrationError(ValueError):
    """Fail-closed Phase-7 integration error."""


def _image_for_context(prg: bytes, prg_banks: int, bank: int) -> bytes:
    image = bytearray(0x10000)
    image[LOW_WINDOW:FIXED_WINDOW_START] = prg[
        bank * 0x4000:(bank + 1) * 0x4000]
    fixed = prg_banks - 1
    image[FIXED_WINDOW_START:0x10000] = prg[
        fixed * 0x4000:(fixed + 1) * 0x4000]
    return bytes(image)


def _target_bank(current_bank: int, target: int, prg_banks: int) -> int:
    return current_bank if target < FIXED_WINDOW_START else prg_banks - 1


def specialize(prg: bytes, prg_banks: int, roots: list[int],
               bank_report: dict[str, Any], evidence_report: dict[str, Any],
               assignment: dict[int, list[int]]) -> dict[str, Any]:
    if bank_report.get("status") != "OK":
        raise P7IntegrationError(
            f"bank-aware reachability is not OK: {bank_report.get('status')!r}")
    known = {(entry["bank"], entry["address"]): entry
             for entry in bank_report["instructions"]}
    successors: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for edge in bank_report["edges"]:
        if edge["dst_bank"] is None:
            continue
        successors.setdefault(
            (edge["src_bank"], edge["src_address"]), []).append(
                (edge["dst_bank"], edge["dst_address"]))
    sites = {record["site"]: record for record in evidence_report["sites"]}
    fixed_bank = prg_banks - 1
    pending = [(fixed_bank, root) for root in roots]
    visited: dict[tuple[int, int], dict[str, Any]] = {}
    frontier: list[dict[str, Any]] = []
    dynamic_returns: list[dict[str, Any]] = []
    images: dict[int, bytes] = {}

    def image(bank: int) -> bytes:
        if bank not in images:
            images[bank] = _image_for_context(prg, prg_banks, bank)
        return images[bank]

    dispatch: dict[tuple[int, int], list[int]] = {}
    while pending:
        node = pending.pop()
        if node in visited:
            continue
        bank, address = node
        entry = known.get(node)
        record = sites.get(address)
        if record is not None:
            state = record.get("classification")
            if state in (RESOLVED_EXACT, RESOLVED_FINITE_SET):
                chosen = assignment.get(address)
                if chosen is None:
                    if state == RESOLVED_EXACT:
                        chosen = list(record["feasible_targets"][0])
                    else:
                        frontier.append({
                            "bank": bank, "address": address,
                            "classification": state,
                            "reason": "resolved indirect site has no "
                                      "assignment; fail closed"})
                        continue
                if list(chosen) not in [list(item)
                                        for item in
                                        record["feasible_targets"]]:
                    frontier.append({
                        "bank": bank, "address": address,
                        "classification": state,
                        "reason": f"assigned target {chosen} is not in the "
                                  "proven feasible set; fail closed"})
                    continue
                dispatch[node] = list(chosen)
                if entry is None:
                    entry = {"bank": bank, "address": address,
                             "op": "jmp", "length": 3,
                             "provenance": PROVEN, "dynamic": True}
                visited[node] = entry
                pending.append((chosen[0], chosen[1]))
                continue
            frontier.append({
                "bank": bank, "address": address,
                "classification": state,
                "reason": record.get("reason", "indirect site is not "
                                                "resolved; fail closed")})
            continue
        if entry is None:
            try:
                insn = nes.decode_full(image(bank), address)
            except nes.NES6502Error as exc:
                frontier.append({
                    "bank": bank, "address": address,
                    "reason": f"undecodable node: {exc}"})
                continue
            entry = {"bank": bank, "address": address, "op": insn["op"],
                     "length": insn["length"], "provenance": PROVEN,
                     "dynamic": True}
            targets, _unresolved = frozen_frontier.successors(insn, address)
            for target in targets:
                pending.append((_target_bank(bank, target, prg_banks), target))
            if insn["op"] in ("rts", "rti"):
                dynamic_returns.append({"bank": bank, "address": address,
                                        "instruction": insn["op"]})
        else:
            if entry["provenance"] != PROVEN:
                frontier.append({
                    "bank": bank, "address": address,
                    "reason": "unresolved bank provenance; fail closed"})
                continue
            for target in successors.get(node, []):
                pending.append(target)
        visited[node] = entry

    addresses: dict[int, int] = {}
    for bank, address in visited:
        addresses.setdefault(address, bank)
        if addresses[address] != bank:
            raise P7IntegrationError(
                f"CPU address 0x{address:04x} is proven in two physical banks; "
                "the shared emitter cannot distinguish them; fail closed")
    identities = [
        {"bank": bank, "address": address, "op": entry["op"],
         "length": entry["length"], "dynamic": entry.get("dynamic", False)}
        for (bank, address), entry in sorted(visited.items())
    ]
    digest = hashlib.sha256(",".join(
        f"{bank}:{address:04x}" for bank, address in sorted(visited))
        .encode("ascii")).hexdigest()
    return {
        "stage": "P7-08",
        "identities": identities,
        "identity_count": len(identities),
        "identity_digest": digest,
        "banks": sorted({bank for bank, _address in visited}),
        "dynamic_nodes": sum(1 for entry in visited.values()
                             if entry.get("dynamic")),
        "frontier": sorted(frontier, key=lambda item: (item.get("address", 0),
                                                       item.get("bank", 0),
                                                       item["reason"])),
        "frontier_count": len(frontier),
        "dynamic_returns": dynamic_returns,
        "assignment": {f"0x{site:04x}": value
                       for site, value in sorted(assignment.items())},
        "dispatch": {f"{bank}:0x{address:04x}": target
                     for (bank, address), target in sorted(dispatch.items())},
        "fail_closed": bool(frontier),
    }


def bridge_instructions(prg: bytes, prg_banks: int,
                        specialized: dict[str, Any]) -> tuple:
    dispatch: dict[int, list[int]] = {}
    for key, target in specialized.get("dispatch", {}).items():
        _bank, address = key.split(":")
        dispatch[int(address, 16)] = list(target)
    instructions = []
    for identity in specialized["identities"]:
        address = identity["address"]
        if address in dispatch:
            target = dispatch[address]
            instructions.append(DecodedInstruction(
                address=address,
                op="jmp",
                size_bytes=3,
                flow=InstructionFlow.JUMP,
                direct_target=target[1],
                unresolved=False,
                evidence=EvidenceClass.PROVEN,
                metadata={"adapter_fields": {
                    "word": 0x4C, "abs": target[1], "target": target[1]}},
            ))
            continue
        image = _image_for_context(prg, prg_banks, identity["bank"])
        try:
            instructions.append(bridge.instruction_from_nes6502(
                image, address))
        except bridge.NES6502BridgeError as exc:
            raise P7IntegrationError(
                f"node {identity['bank']}:0x{address:04x} cannot "
                f"be bridged: {exc}") from exc
    return tuple(sorted(instructions, key=lambda item: item.address))


def emit_host(rom: bytes, inventory: dict[str, Any], prg: bytes,
              prg_banks: int, specialized: dict[str, Any],
              metadata_fields: dict[str, Any]) -> dict[str, Any]:
    instructions = bridge_instructions(prg, prg_banks, specialized)
    if not instructions:
        raise P7IntegrationError("no proven instructions to emit")
    metadata = dict(metadata_fields)
    metadata.setdefault("fixed_bank_origin", 0xC000)
    metadata.setdefault("cpu_origin", 0x8000)
    program_text = emit_module.emit_host_program(instructions, metadata)
    support_text = emit_module.emit_support(rom, metadata, (0, 0, 0))
    return {
        "instructions": len(instructions),
        "host_program_sha256": hashlib.sha256(
            program_text.encode("utf-8")).hexdigest(),
        "support_sha256": hashlib.sha256(
            support_text.encode("utf-8")).hexdigest(),
        "host_program": program_text,
        "support": support_text,
    }


def build_native(emission: dict[str, Any], *, fixture_id: str,
                 workspace: pathlib.Path) -> Any:
    return emit_module.build_native(
        emission["host_program"], emission["support"],
        fixture_id=fixture_id, workspace=workspace, run_count=2)


__all__ = [
    "FIXED_WINDOW_START",
    "P7IntegrationError",
    "build_native",
    "bridge_instructions",
    "emit_host",
    "specialize",
]
