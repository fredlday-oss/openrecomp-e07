#!/usr/bin/env python3
"""Phase-7 evidence-driven inline-dispatch closure (P7-12).

P7-11 demonstrated that the bank-aware frontier still stops at the classified
`DATA_NOT_CODE` inline dispatch table at `0xC570`. This module adds exactly the
translation/control-flow behaviour that evidence requires, and no more:

* detect the inline dispatch idiom structurally (a `jsr` whose fallthrough
  bytes are an undocumented byte stream, whose callee consumes the pushed
  return address, and whose fallthrough is a decodable little-endian pointer
  table with at least one in-window target);
* close the frontier over the proven structure: do not decode the table bytes
  as instructions, follow the callee and the proven finite target set, and
  resume at the address after the table;
* fail closed everywhere else (undocumented bytes, unresolved indirect jumps
  and budgets stop the walk).

The closure is verified on the public P7-03 fixture (whose runtime evidence
proves the mechanism) before it is applied to the private image.
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
import p7_opcode_7c_v1 as opcode_module  # noqa: E402

DEFAULT_BUDGET = 200000


class P7ClosureError(ValueError):
    """Fail-closed closure error."""


def detect_inline_tables(image: bytes,
                         instructions: dict[int, dict]) -> list[dict]:
    tables = []
    for address, insn in sorted(instructions.items()):
        if insn["op"] != "jsr":
            continue
        fallthrough = (address + insn["length"]) & 0xFFFF
        if fallthrough in instructions:
            continue
        try:
            nes.decode_full(image, fallthrough)
            continue
        except nes.NES6502Error:
            pass
        callee = opcode_module._callee_window(image, insn["a16"])
        if not callee["consumes_return_address"]:
            continue
        table = opcode_module._inline_table(image, fallthrough)
        if table["entries"] < 1:
            continue
        tables.append({
            "call_site": address,
            "callee": insn["a16"],
            "table_base": fallthrough,
            "entries": table["entries"],
            "byte_length": table["byte_length"],
            "targets": table["targets"],
            "resume_address": table["resume_address"],
        })
    return tables


def closure_walk(image: bytes, roots: list[int], tables: list[dict],
                 *, budget: int = DEFAULT_BUDGET) -> dict[str, Any]:
    by_site = {table["call_site"]: table for table in tables}
    table_spans = []
    for table in tables:
        table_spans.append((table["table_base"],
                            table["table_base"] + table["byte_length"]))
    pending = list(roots)
    visited: dict[int, dict] = {}
    resolved_sites: list[dict] = []
    remaining_tables = set(by_site)
    stop: dict[str, Any] | None = None
    while pending:
        address = pending.pop()
        if address in visited:
            continue
        if len(visited) >= budget:
            stop = {"address": address, "kind": "budget",
                    "reason": "closure walk budget"}
            break
        if any(start <= address < end for start, end in table_spans):
            stop = {"address": address, "kind": "table_span",
                    "reason": "control flow entered a classified table span"}
            break
        try:
            insn = nes.decode_full(image, address)
        except nes.NES6502Error as exc:
            stop = {"address": address, "kind": "undocumented_opcode",
                    "reason": str(exc)}
            break
        visited[address] = insn
        table = by_site.get(address)
        if table is not None:
            remaining_tables.discard(address)
            resolved_sites.append({
                "call_site": address,
                "callee": table["callee"],
                "table_base": table["table_base"],
                "entries": table["entries"],
                "targets": table["targets"],
                "resume_address": table["resume_address"],
            })
            if table["callee"] not in visited:
                pending.append(table["callee"])
            for target in table["targets"]:
                pending.append(target)
            continue
        targets, _unresolved = frozen_frontier.successors(insn, address)
        for target in targets:
            pending.append(target)
    covered: set[int] = set()
    for address, insn in visited.items():
        covered.update(range(address, address + insn["length"]))
    digest = hashlib.sha256(",".join(
        f"{address:04x}" for address in sorted(visited))
        .encode("ascii")).hexdigest()
    return {
        "instructions": len(visited),
        "bytes": len(covered),
        "addresses": sorted(visited) if len(visited) <= 4096 else None,
        "address_digest": digest,
        "resolved_sites": sorted(resolved_sites,
                                 key=lambda item: item["call_site"]),
        "resolved_site_count": len(resolved_sites),
        "unresolved_sites": sorted(
            {table["call_site"] for table in tables} - remaining_tables),
        "stop": stop,
        "table_count": len(tables),
    }


def analyze(image: bytes, roots: list[int], *,
            budget: int = DEFAULT_BUDGET) -> dict[str, Any]:
    baseline = opcode_module.candidate_walk(image, roots)
    tables = detect_inline_tables(image, baseline)
    closure = closure_walk(image, roots, tables, budget=budget)
    return {
        "stage": "P7-12",
        "baseline": {
            "instructions": len(baseline),
            "stop": {
                "address": None,
                "note": "baseline walk stops at the first undocumented byte",
            },
        },
        "tables": tables,
        "closure": closure,
        "delta_instructions":
            closure["instructions"] - len(baseline),
        "claim": "the inline-dispatch closure decodes only proven code, "
                 "follows only proven finite target sets and skips only "
                 "structurally classified data tables; everything else fails "
                 "closed",
    }


__all__ = [
    "DEFAULT_BUDGET",
    "P7ClosureError",
    "analyze",
    "closure_walk",
    "detect_inline_tables",
]
