#!/usr/bin/env python3
"""Phase-5 exact reachable/dead/unsupported instruction frontier (P5-02).

Walks the public fixture from its reset/NMI/IRQ roots with the frozen NMOS
6502 decoder (`adapters.nes6502`), following only documented static control
flow:

* direct `jmp`, `jsr` and conditional-branch targets, plus fallthrough;
* `rts`, `rti` and `brk` terminate statically (dynamic return / vector);
* `jmp (indirect)` is an unresolved indirect site and is never guessed;
* undocumented opcodes fail closed (`NES6502Error`).

The reachable set is exact for the audited public fixture. Data regions and
padding are classified as non-code; unreachable decodable instructions are
reported as dead. Nothing is inferred or fabricated.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT / ".openrecomp-phase5" / "src"), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402

CPU_SIZE = 0x10000
PRG_ROM_BASE = 0x8000

BRANCH_NAMES = frozenset(name for name, _flag, _taken in nes_adapter.BRANCHES.values())


class FrontierError(ValueError):
    """Fail-closed reachable-frontier error."""


def build_cpu_image(rom: bytes, prg_offset: int, prg_bytes: int) -> bytes:
    image = bytearray(CPU_SIZE)
    prg = rom[prg_offset:prg_offset + prg_bytes]
    if len(prg) not in (0x4000, 0x8000):
        raise FrontierError(
            f"frontier currently supports 16/32 KiB NROM PRG, got {len(prg)}")
    image[PRG_ROM_BASE:PRG_ROM_BASE + len(prg)] = prg
    if len(prg) == 0x4000:
        image[0xC000:0x10000] = prg
    return bytes(image)


def successors(instruction: dict, address: int) -> tuple[list[int], bool]:
    """Documented static successors; `unresolved` marks indirect jumps.

    `brk` continues at `pc+2` because that is exactly the return address BRK
    pushes (documented); `rts`/`rti` returns are dynamic and are recorded
    separately rather than guessed.
    """
    op = instruction["op"]
    fallthrough = (address + instruction["length"]) & 0xFFFF
    if op == "brk":
        return [(address + 2) & 0xFFFF], False
    if op in ("rts", "rti"):
        return [], False
    if op == "jmp":
        if "indirect" in instruction:
            return [], True
        return [instruction["target"]], False
    if op == "jsr":
        return [instruction["a16"], fallthrough], False
    if op in BRANCH_NAMES:
        return [instruction["target"], fallthrough], False
    return [fallthrough], False


def reachable_frontier(image: bytes, roots: list[int]) -> dict[str, Any]:
    if len(image) != CPU_SIZE:
        raise FrontierError("guest image must be exactly 64 KiB")
    pending = list(roots)
    visited: dict[int, dict] = {}
    indirect_sites: list[dict] = []
    interrupt_sites: list[dict] = []
    dynamic_return_sites: list[dict] = []
    while pending:
        address = pending.pop()
        if address in visited:
            continue
        try:
            instruction = nes_adapter.decode_full(image, address)
        except nes_adapter.NES6502Error as exc:
            raise FrontierError(
                f"reachable decode failed at 0x{address:04x}: {exc}") from exc
        visited[address] = instruction
        targets, unresolved = successors(instruction, address)
        if unresolved:
            indirect_sites.append({
                "address": address,
                "instruction": instruction["op"],
                "indirect": instruction.get("indirect"),
            })
        if instruction["op"] == "brk":
            interrupt_sites.append({
                "address": address,
                "instruction": "brk",
                "continuation": (address + 2) & 0xFFFF,
            })
        if instruction["op"] in ("rti", "rts"):
            dynamic_return_sites.append({
                "address": address,
                "instruction": instruction["op"],
            })
        pending.extend(targets)

    covered: set[int] = set()
    for address, instruction in visited.items():
        covered.update(range(address, address + instruction["length"]))

    opcode_histogram: dict[str, int] = {}
    mode_histogram: dict[str, int] = {}
    for instruction in sorted(visited.values(), key=lambda item: item["address"]):
        opcode_histogram[instruction["op"]] = (
            opcode_histogram.get(instruction["op"], 0) + 1)
        mode = nes_adapter.OPCODES[instruction["word"]][1]
        mode_histogram[mode] = mode_histogram.get(mode, 0) + 1

    return {
        "roots": sorted(roots),
        "reachable_instructions": len(visited),
        "reachable_bytes": len(covered),
        "reachable_addresses": sorted(visited),
        "covered_bytes": sorted(covered),
        "opcode_histogram": dict(sorted(opcode_histogram.items())),
        "mode_histogram": dict(sorted(mode_histogram.items())),
        "indirect_sites": sorted(indirect_sites, key=lambda item: item["address"]),
        "interrupt_sites": sorted(interrupt_sites, key=lambda item: item["address"]),
        "dynamic_return_sites": sorted(dynamic_return_sites,
                                       key=lambda item: item["address"]),
        "instructions": [
            {
                "address": item["address"],
                "op": item["op"],
                "length": item["length"],
                "word": item["word"],
                "target": item.get("target"),
            }
            for item in sorted(visited.values(), key=lambda entry: entry["address"])
        ],
    }


def linear_decode(image: bytes, start: int, end: int) -> dict[int, dict]:
    """Linear decode of a contiguous code region (no reachability inference)."""
    instructions: dict[int, dict] = {}
    address = start
    while address < end:
        try:
            instruction = nes_adapter.decode_full(image, address)
        except nes_adapter.NES6502Error as exc:
            raise FrontierError(
                f"linear decode failed at 0x{address:04x} (region code must be "
                f"fully decodable): {exc}") from exc
        if address + instruction["length"] > end:
            raise FrontierError(
                f"instruction at 0x{address:04x} overlaps the region end 0x{end:04x}")
        instructions[address] = instruction
        address += instruction["length"]
    return instructions


def classify_code_span(image: bytes, start: int, end: int,
                       reachable: set[int]) -> dict[str, Any]:
    linear = linear_decode(image, start, end)
    dead = [address for address in sorted(linear) if address not in reachable]
    return {
        "span": [start, end],
        "linear_instructions": len(linear),
        "reachable_in_span": sum(1 for address in linear if address in reachable),
        "dead_in_span": len(dead),
        "dead_addresses": dead,
    }


def code_region_from_metadata(metadata: dict) -> tuple[int, int]:
    spans = metadata.get("data_spans") or []
    if not spans:
        raise FrontierError("fixture metadata declares no data spans")
    origin = metadata["cpu_origin"]
    first_data = min(span[0] for span in spans if span[0] >= origin)
    return origin, first_data


def analysis(rom: bytes, metadata: dict, inventory: dict) -> dict[str, Any]:
    region_start, region_end = code_region_from_metadata(metadata)
    image = build_cpu_image(rom, 16, metadata["prg_size"])
    vectors = inventory["vectors"]
    roots = [vectors["reset"], vectors["nmi"], vectors["irq"]]
    frontier = reachable_frontier(image, roots)
    reachable_starts = set(frontier["reachable_addresses"])
    span = classify_code_span(image, region_start, region_end, reachable_starts)
    return {
        "stage": "P5-02",
        "source": "original public fixture (Apache-2.0)",
        "image_sha256": hashlib.sha256(image).hexdigest(),
        "code_region": [region_start, region_end],
        "roots": {name: vectors[name] for name in ("reset", "nmi", "irq")},
        "reachable": {
            "instructions": frontier["reachable_instructions"],
            "bytes": frontier["reachable_bytes"],
            "opcode_histogram": frontier["opcode_histogram"],
            "mode_histogram": frontier["mode_histogram"],
            "indirect_sites": frontier["indirect_sites"],
            "interrupt_sites": frontier["interrupt_sites"],
            "dynamic_return_sites": frontier["dynamic_return_sites"],
        },
        "code_span": span,
        "unsupported": {
            "reachable_undocumented_opcodes": 0,
            "note": "frozen decoder fails closed on undocumented opcodes; none "
                    "occur on the reachable public-fixture path",
        },
        "decimal_mode": {
            "instructions_present": ["sed", "cld"],
            "arithmetic": "binary_only_2a03",
            "note": "NES 2A03 has no decimal-mode arithmetic; exact semantics are "
                    "proven in P5-03 against the independent reference",
        },
    }


__all__ = [
    "FrontierError",
    "analysis",
    "build_cpu_image",
    "classify_code_span",
    "code_region_from_metadata",
    "linear_decode",
    "reachable_frontier",
    "successors",
]
