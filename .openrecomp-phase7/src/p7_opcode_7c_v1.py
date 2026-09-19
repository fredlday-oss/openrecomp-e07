#!/usr/bin/env python3
"""Phase-7 undocumented-opcode `0x7C` classification (P7-02).

Determines what the `0x7C` byte at the private-image address `0xC570`
represents from structural evidence in this binary/context, without guessing
semantics from the opcode value alone and without adding any undocumented
opcode support:

1. a bounded documented-control-flow walk reproduces the Phase-6 frontier and
   stops at `0xC570` (undocumented opcode);
2. the static predecessor set of `0xC570` is computed from the walk: the only
   predecessor is the fallthrough edge of `jsr $C71F` at `0xC56D`;
3. the callee entry at `0xC71F` is analysed: it pulls the two bytes of the
   pushed return address (`pla`/`sta $00`, `pla`/`sta $01`) before any
   transfer, reads memory through `lda ($00),y`, and dispatches through
   `jmp ($0002)` - the documented "inline dispatch table after the call"
   idiom;
4. the inline table at `0xC570` is decoded as little-endian 16-bit code
   pointers until an entry leaves the fixed code window: six entries
   (`$C57C`, `$C644`, `$C679`, `$C686`, `$CB24`, `$C6B6`), each decoding to a
   documented instruction, with documented code resuming at `0xC57C`;
5. a nested table at `0xC581` after the resumed `lda $1C; jsr $C71F` is
   recorded as corroborating structure.

The bounded classification for `0xC570` is `DATA_NOT_CODE`: the byte is the
low byte of the first inline dispatch pointer, not an executable instruction.
No undocumented-opcode semantics are implemented and no universal
undocumented-opcode claim is made. No ROM bytes are returned, stored, echoed
or written to evidence.
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
import p6_frontier_v1 as frontier  # noqa: E402
import p6_ines_v1 as ingestion  # noqa: E402
import p6_private_fixture_v1 as pf  # noqa: E402

PRIVATE_ROM = pf.PRIVATE_ROM
TARGET_ADDRESS = 0xC570
TARGET_OPCODE = 0x7C
CALLEE_ADDRESS = 0xC71F
CALL_SITE = 0xC56D

FIXED_WINDOW_BASE = 0xC000
FIXED_WINDOW_END = 0xFFFF

WALK_BUDGET = 20000
CALLEE_WINDOW = 16
TABLE_ENTRY_LIMIT = 32
CORROBORATION_WINDOW = 16

TRANSFERS = frozenset({"rts", "rti", "brk", "jsr"})
BRANCH_OPS = frozenset({"bpl", "bmi", "bvc", "bvs", "bcc", "bcs", "bne", "beq"})


class P7OpcodeError(ValueError):
    """Fail-closed P7-02 classification error."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ingest_inventory(data: bytes) -> dict[str, Any]:
    inventory = ingestion.ingest(data, source_label="private_tmnt")
    if inventory["phase6"]["status"] != "SUPPORTED_MMC1":
        raise P7OpcodeError("private image is not classified SUPPORTED_MMC1")
    return inventory


def _metadata(inventory: dict[str, Any]) -> dict[str, Any]:
    return {
        "rom_sha256": inventory["image_sha256"],
        "prg_size": inventory["prg_bytes"],
        "chr_size": inventory["chr_bytes"],
        "prg_banks": inventory["prg_bytes"] // 0x4000,
        "chr_banks": inventory["chr_bytes"] // 0x2000,
    }


def build_image(data: bytes) -> tuple[bytes, dict[str, Any]]:
    inventory = _ingest_inventory(data)
    image = frontier.build_mmc1_cpu_image(data, _metadata(inventory))
    return image, inventory


def candidate_walk(image: bytes, roots: list[int],
                   budget: int = WALK_BUDGET) -> dict[int, dict]:
    """Frozen documented-control-flow candidate walk (same model as Phase 6)."""
    pending = list(roots)
    visited: dict[int, dict] = {}
    while pending:
        address = pending.pop()
        if address in visited:
            continue
        if not 0x8000 <= address <= 0xFFFF:
            continue
        if len(visited) >= budget:
            break
        try:
            instruction = nes.decode_full(image, address)
        except nes.NES6502Error:
            break
        visited[address] = instruction
        targets, _unresolved = frontier.frozen_frontier.successors(instruction,
                                                                   address)
        pending.extend(targets)
    return visited


def predecessors(instructions: dict[int, dict], address: int) -> list[dict]:
    """All static predecessor edges of `address` inside the decoded set."""
    found: list[dict] = []
    for source, instruction in sorted(instructions.items()):
        fallthrough = (source + instruction["length"]) & 0xFFFF
        op = instruction["op"]
        if op == "jsr":
            if instruction["a16"] == address:
                found.append({"address": source, "op": op, "edge": "target"})
            if fallthrough == address:
                found.append({"address": source, "op": op,
                              "edge": "fallthrough"})
        elif op == "jmp" and "indirect" not in instruction:
            if instruction["target"] == address:
                found.append({"address": source, "op": op, "edge": "target"})
        elif op in BRANCH_OPS:
            if instruction["target"] == address:
                found.append({"address": source, "op": op, "edge": "target"})
            if fallthrough == address:
                found.append({"address": source, "op": op,
                              "edge": "fallthrough"})
        elif op not in ("rts", "rti", "jmp", "brk"):
            if fallthrough == address:
                found.append({"address": source, "op": op,
                              "edge": "fallthrough"})
    return found


def _callee_window(image: bytes, target: int,
                   window: int = CALLEE_WINDOW) -> dict[str, Any]:
    """Linear decode of the callee entry plus the return-consumption evidence."""
    instructions = []
    pulls = 0
    indirect_reads = 0
    indirect_jump = False
    pc = target
    terminated = False
    for _ in range(window):
        try:
            instruction = nes.decode_full(image, pc)
        except nes.NES6502Error as exc:
            instructions.append({"address": pc, "op": "UNDECODABLE",
                                 "reason": str(exc)})
            break
        op = instruction["op"]
        entry = {"address": pc, "op": op, "length": instruction["length"]}
        if "indirect,y" in instruction:
            entry["mode"] = "indirect,y"
            indirect_reads += 1
        elif "indirect" in instruction and op == "jmp":
            entry["mode"] = "indirect"
            indirect_jump = True
        elif "zp" in instruction:
            entry["zp"] = instruction["zp"]
        instructions.append(entry)
        if op == "pla":
            pulls += 1
        if op in ("rts", "rti", "brk") or (op == "jmp" and indirect_jump):
            terminated = True
            break
        if op == "jsr":
            terminated = True
            break
        pc += instruction["length"]
    consumes = pulls >= 2 and indirect_reads >= 1 and indirect_jump
    return {
        "address": target,
        "instructions": instructions,
        "pulls": pulls,
        "indirect_reads": indirect_reads,
        "indirect_jump": indirect_jump,
        "terminated": terminated,
        "consumes_return_address": consumes,
    }


def _inline_table(image: bytes, base: int,
                  limit: int = TABLE_ENTRY_LIMIT) -> dict[str, Any]:
    """Decode little-endian pointers until an entry leaves the code window."""
    entries = []
    index = 0
    while index < limit:
        offset = base + 2 * index
        if offset + 1 >= len(image):
            break
        lo = image[offset]
        hi = image[offset + 1]
        target = lo | (hi << 8)
        if not FIXED_WINDOW_BASE <= target <= FIXED_WINDOW_END:
            break
        try:
            first = nes.decode_full(image, target)
        except nes.NES6502Error:
            break
        entries.append({"index": index, "table_offset": offset,
                        "target": target, "first_op": first["op"]})
        index += 1
    return {
        "base": base,
        "entries": len(entries),
        "byte_length": 2 * len(entries),
        "targets": [entry["target"] for entry in entries],
        "all_targets_in_code_window": all(
            FIXED_WINDOW_BASE <= entry["target"] <= FIXED_WINDOW_END
            for entry in entries),
        "all_targets_decode": len(entries) > 0,
        "entry_detail": entries,
        "resume_address": base + 2 * len(entries),
    }


def _linear_corroboration(image: bytes, start: int,
                          window: int = CORROBORATION_WINDOW) -> dict[str, Any]:
    """Show the byte stream is not a coherent documented instruction stream."""
    pc = start + 1
    steps = 0
    undocumented_at: int | None = None
    while steps < window:
        if pc >= len(image):
            break
        try:
            instruction = nes.decode_full(image, pc)
        except nes.NES6502Error:
            undocumented_at = pc
            break
        pc += instruction["length"]
        steps += 1
    forced_three = None
    pc = start + 3
    for _ in range(window):
        if pc >= len(image):
            break
        try:
            instruction = nes.decode_full(image, pc)
        except nes.NES6502Error:
            forced_three = pc
            break
        pc += instruction["length"]
    return {
        "linear_undocumented_offset": (undocumented_at - start)
        if undocumented_at is not None else None,
        "linear_undocumented_address": undocumented_at,
        "forced_three_byte_undocumented_offset": (forced_three - start)
        if forced_three is not None else None,
        "forced_three_byte_undocumented_address": forced_three,
        "coherent_documented_stream": undocumented_at is None,
    }


def classify(image: bytes, stop_address: int = TARGET_ADDRESS,
             roots: list[int] | None = None) -> dict[str, Any]:
    """Classify the byte at `stop_address` from structural evidence only."""
    if roots is None:
        raise P7OpcodeError("roots are required for the classification walk")
    instructions = candidate_walk(image, roots)
    if stop_address in instructions:
        return {
            "address": stop_address,
            "classification": "REACHABLE_CODE",
            "reason": "the address is a decode of the documented control-flow "
                      "walk with documented opcode semantics",
            "opcode_semantics_required": False,
            "universal_claim": False,
        }
    preds = predecessors(instructions, stop_address)
    if not preds:
        return {
            "address": stop_address,
            "classification": "UNREACHABLE",
            "reason": "no static predecessor in the bounded documented walk",
            "opcode_semantics_required": False,
            "universal_claim": False,
        }
    if len(preds) != 1:
        return {
            "address": stop_address,
            "classification": "AMBIGUOUS",
            "reason": f"{len(preds)} static predecessor edges",
            "predecessors": preds,
            "opcode_semantics_required": False,
            "universal_claim": False,
        }
    predecessor = preds[0]
    if predecessor["op"] != "jsr" or predecessor["edge"] != "fallthrough":
        return {
            "address": stop_address,
            "classification": "AMBIGUOUS",
            "reason": "the only predecessor is not a jsr fallthrough",
            "predecessors": preds,
            "opcode_semantics_required": False,
            "universal_claim": False,
        }
    call_site = predecessor["address"]
    callee = nes.decode_full(image, call_site)["a16"]
    callee_record = _callee_window(image, callee)
    if not callee_record["consumes_return_address"]:
        return {
            "address": stop_address,
            "classification": "AMBIGUOUS",
            "reason": "the callee does not consume the pushed return address",
            "predecessors": preds,
            "callee": callee_record,
            "opcode_semantics_required": False,
            "universal_claim": False,
        }
    table = _inline_table(image, stop_address)
    if table["entries"] < 1:
        return {
            "address": stop_address,
            "classification": "AMBIGUOUS",
            "reason": "no in-window inline dispatch table follows the call",
            "predecessors": preds,
            "callee": callee_record,
            "opcode_semantics_required": False,
            "universal_claim": False,
        }
    resume = table["resume_address"]
    resume_record: dict[str, Any] = {"address": resume}
    try:
        first = nes.decode_full(image, resume)
        resume_record["first_op"] = first["op"]
        second_pc = resume + first["length"]
        if second_pc < len(image):
            second = nes.decode_full(image, second_pc)
            resume_record["second_op"] = second["op"]
            resume_record["second_address"] = second_pc
            if second["op"] == "jsr":
                resume_record["second_target"] = second["a16"]
                nested_base = (second_pc + second["length"]) & 0xFFFF
                nested = _inline_table(image, nested_base)
                resume_record["nested_table"] = nested
    except nes.NES6502Error:
        resume_record["first_op"] = "UNDECODABLE"
    corroboration = _linear_corroboration(image, stop_address)
    return {
        "address": stop_address,
        "opcode": f"0x{image[stop_address]:02x}",
        "classification": "DATA_NOT_CODE",
        "method": "inline_dispatch_table_v1",
        "reason": "the byte is the low byte of the first 16-bit code pointer "
                  "in the inline dispatch table consumed by the callee's "
                  "pulled-return-address pointer; documented code resumes "
                  "after the table",
        "predecessors": preds,
        "call_site": call_site,
        "callee": callee_record,
        "inline_table": table,
        "code_resume": resume_record,
        "corroboration": corroboration,
        "opcode_semantics_required": False,
        "universal_claim": False,
        "public_claim": "none; private local analysis must not enter the "
                        "public package",
    }


def run(path: pathlib.Path | str = PRIVATE_ROM,
        stop_address: int = TARGET_ADDRESS) -> dict[str, Any]:
    location = pathlib.Path(path)
    if not location.is_file():
        raise P7OpcodeError("private compatibility fixture is not present")
    try:
        data = location.read_bytes()
    except OSError as exc:
        raise P7OpcodeError(f"cannot read private fixture: {exc}") from exc
    try:
        image, inventory = build_image(data)
    except (ingestion.P6IngestionError, frontier.P6FrontierError) as exc:
        raise P7OpcodeError(f"ingestion failed closed: {exc}") from exc
    vectors = inventory["vectors"]
    roots = [vectors["reset"], vectors["nmi"], vectors["irq"]]
    record = classify(image, stop_address, roots)
    record.update({
        "stage": "P7-02",
        "fixture": "private_tmnt",
        "image_sha256": inventory["image_sha256"],
        "image_size": inventory["actual_size"],
        "documented_opcode_count": len(nes.OPCODES),
        "target_opcode_supported_by_decoder": TARGET_OPCODE in nes.OPCODES,
        "reference_basis": {
            "cpu_variant":
                "NES Ricoh 2A03 NMOS 6502 core (no decimal-mode arithmetic)",
            "documented_semantics_used":
                "PLA, STA zp, LDA (zp),Y, JMP (indirect) and 16-bit "
                "little-endian pointer arithmetic - all documented 6502 "
                "behaviour performed by the analysed callee",
            "opcode_table_basis":
                "the classification is structural (control-flow predecessor, "
                "callee return-address consumption and pointer-table layout) "
                "and does not depend on any undocumented-opcode table entry",
            "independent_mechanism_tests":
                "the stage gate proves the same classifier on original "
                "synthetic public images: full inline-dispatch idiom -> "
                "DATA_NOT_CODE, non-consuming callee -> AMBIGUOUS, no table "
                "-> AMBIGUOUS, branch/literal predecessor -> AMBIGUOUS",
            "public_documentation":
                "the documented 6502 instruction set is public; no "
                "copyrighted or console-derived material is used",
        },
        "semantics_added": False,
        "universal_claim": False,
    })
    return record


__all__ = [
    "CALLEE_ADDRESS",
    "CALL_SITE",
    "P7OpcodeError",
    "PRIVATE_ROM",
    "TARGET_ADDRESS",
    "TARGET_OPCODE",
    "build_image",
    "candidate_walk",
    "classify",
    "predecessors",
    "run",
]
