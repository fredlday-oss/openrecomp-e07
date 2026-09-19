#!/usr/bin/env python3
"""Phase-7 indirect-jump evidence model (P7-06).

Deterministic evidence model for indirect `jmp (pointer)` sites, built for the
three private `$E2` sites (`0x86E8`, `0x8956`, `0x8F3C`) and reusable on
public fixtures:

* the pointer's reaching definitions are found on the unique straight-line
  predecessor chain of the site; a definition only counts when every
  instruction from the definition to the site has exactly one static
  predecessor (no middle entry), otherwise the site is `UNRESOLVED`;
* value sources are classified as constants (`lda #imm`), fixed ROM reads
  (`lda abs`), paired table reads (`lda abs,x` / `lda abs,y`) or unknown;
* the index register domain is computed by bounded abstract simulation of the
  chain (8-bit registers, `and` masks, `asl`/`lsr`, `tax`/`tay`/`t` transfers,
  increments) so table candidate pointers are enumerated exactly over the
  proven domain;
* candidate pointers are enumerated per physical PRG bank (table bytes come
  from the bank mapped at the window), and each candidate target is checked
  for validity (window, target bank, documented decode) - targets are never
  guessed;
* explicit states: `RESOLVED_EXACT`, `RESOLVED_FINITE_SET`, `UNRESOLVED`,
  `IMPOSSIBLE`, with pointer writes/reads, memory provenance and bank
  provenance recorded.

No ROM bytes are returned, stored, echoed or written to evidence.
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
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p7_bank_reachability_v1 as bank_model  # noqa: E402
import p7_opcode_7c_v1 as opcode_module  # noqa: E402

PRIVATE_SITES = (0x86E8, 0x8956, 0x8F3C)
POINTER = 0xE2
POINTER_HIGH = 0xE3
LOW_WINDOW = 0x8000
HIGH_WINDOW_MAX = 0xFFFF
FIXED_WINDOW_START = 0xC000
CHAIN_LIMIT = 64
MAX_INDEX_DOMAIN = 256

RESOLVED_EXACT = "RESOLVED_EXACT"
RESOLVED_FINITE_SET = "RESOLVED_FINITE_SET"
UNRESOLVED = "UNRESOLVED"
IMPOSSIBLE = "IMPOSSIBLE"

BRANCH_OPS = frozenset({"bpl", "bmi", "bvc", "bvs", "bcc", "bcs", "bne", "beq"})
FULL = frozenset(range(256))
TRACKED_OPS = frozenset({
    "lda", "ldx", "ldy", "and", "ora", "eor", "adc", "sbc", "lsr", "asl",
    "rol", "ror", "tax", "tay", "txa", "tya", "tsx", "txs", "inx", "iny",
    "dex", "dey", "pla", "pla", "txs",
})


class P7IndirectError(ValueError):
    """Fail-closed indirect-evidence error."""


def build_predecessors(instructions: dict[int, dict]) -> dict[int, list[int]]:
    predecessors: dict[int, list[int]] = {}
    for address, insn in sorted(instructions.items()):
        for target in _successors(insn, address):
            predecessors.setdefault(target, []).append(address)
    return predecessors


def _successors(insn: dict, address: int) -> list[int]:
    fallthrough = (address + insn["length"]) & 0xFFFF
    op = insn["op"]
    if op == "jsr":
        return [insn["a16"], fallthrough]
    if op == "jmp" and "indirect" not in insn:
        return [insn["target"]]
    if op == "jmp":
        return []
    if op in BRANCH_OPS:
        return [insn["target"], fallthrough]
    if op in ("rts", "rti"):
        return []
    if op == "brk":
        return [(address + 2) & 0xFFFF]
    return [fallthrough]


def unique_chain(instructions: dict[int, dict], predecessors: dict[int, list[int]],
                 site: int, limit: int = CHAIN_LIMIT) -> list[dict]:
    """Unique straight-line fallthrough predecessor chain ending before site."""
    chain: list[dict] = []
    current = site
    for _ in range(limit):
        candidates = predecessors.get(current, [])
        if len(candidates) != 1:
            break
        previous_address = candidates[0]
        previous = instructions.get(previous_address)
        if previous is None:
            break
        if previous_address + previous["length"] != current:
            break
        chain.append(previous)
        current = previous_address
    return list(reversed(chain))


def simulate_domains(chain: list[dict]) -> list[tuple[frozenset, frozenset, frozenset]]:
    """Register value domains after each chain instruction (full-range start)."""
    dom_a: frozenset = FULL
    dom_x: frozenset = FULL
    dom_y: frozenset = FULL
    snapshots: list[tuple[frozenset, frozenset, frozenset]] = []
    for insn in chain:
        op = insn["op"]
        if op == "lda":
            if "imm8" in insn:
                dom_a = frozenset({insn["imm8"]})
            else:
                dom_a = FULL
        elif op == "ldx":
            if "imm8" in insn:
                dom_x = frozenset({insn["imm8"]})
            else:
                dom_x = FULL
        elif op == "ldy":
            if "imm8" in insn:
                dom_y = frozenset({insn["imm8"]})
            else:
                dom_y = FULL
        elif op == "and" and "imm8" in insn:
            dom_a = frozenset(value & insn["imm8"] for value in dom_a)
        elif op == "ora" and "imm8" in insn:
            dom_a = frozenset(value | insn["imm8"] for value in dom_a)
        elif op == "eor" and "imm8" in insn:
            dom_a = frozenset(value ^ insn["imm8"] for value in dom_a)
        elif op in ("adc", "sbc") and "imm8" in insn:
            dom_a = FULL
        elif op == "lsr" and insn.get("dst") == "a":
            dom_a = frozenset(value >> 1 for value in dom_a)
        elif op == "asl" and insn.get("dst") == "a":
            dom_a = frozenset((value << 1) & 0xFF for value in dom_a)
        elif op == "rol" and insn.get("dst") == "a":
            dom_a = FULL
        elif op == "ror" and insn.get("dst") == "a":
            dom_a = FULL
        elif op == "tax":
            dom_x = dom_a
        elif op == "tay":
            dom_y = dom_a
        elif op == "txa":
            dom_a = dom_x
        elif op == "tya":
            dom_a = dom_y
        elif op == "tsx":
            dom_x = FULL
        elif op == "txs":
            pass
        elif op == "inx":
            dom_x = frozenset((value + 1) & 0xFF for value in dom_x)
        elif op == "iny":
            dom_y = frozenset((value + 1) & 0xFF for value in dom_y)
        elif op == "dex":
            dom_x = frozenset((value - 1) & 0xFF for value in dom_x)
        elif op == "dey":
            dom_y = frozenset((value - 1) & 0xFF for value in dom_y)
        snapshots.append((dom_a, dom_x, dom_y))
    return snapshots


def _writes_pointer(insn: dict, byte: int) -> bool:
    if insn["op"] not in ("sta", "stx", "sty"):
        return False
    return insn.get("zp") == byte


def _value_source(chain: list[dict], write_index: int) -> dict[str, Any]:
    if write_index == 0:
        return {"kind": "unknown", "reason": "no preceding instruction"}
    source = chain[write_index - 1]
    op = source["op"]
    if op == "lda" and "imm8" in source:
        return {"kind": "constant", "value": source["imm8"],
                "address": source["address"]}
    if op == "lda" and "abs" in source and "x" not in source and "y" not in source:
        return {"kind": "rom_read", "address": source["abs"],
                "source_address": source["address"]}
    if op == "lda" and "abs,x" in source:
        return {"kind": "table", "base": source["abs,x"], "index": "x",
                "source_address": source["address"]}
    if op == "lda" and "abs,y" in source:
        return {"kind": "table", "base": source["abs,y"], "index": "y",
                "source_address": source["address"]}
    if op == "txa":
        return {"kind": "unknown", "reason": "value comes from X"}
    if op == "tya":
        return {"kind": "unknown", "reason": "value comes from Y"}
    return {"kind": "unknown",
            "reason": f"value source op {op!r} is not statically resolved"}


def _read_bank_byte(prg: bytes, prg_banks: int, bank: int,
                    address: int) -> int:
    if LOW_WINDOW <= address < FIXED_WINDOW_START:
        offset = bank * bank_model.PRG_BANK_BYTES + (address - LOW_WINDOW)
    else:
        offset = ((prg_banks - 1) * bank_model.PRG_BANK_BYTES
                  + (address - FIXED_WINDOW_START))
    if not 0 <= offset < len(prg):
        raise P7IndirectError(f"address 0x{address:04x} bank {bank} is "
                              "outside the PRG image")
    return prg[offset]


def _target_bank(target: int, current_bank: int, prg_banks: int) -> int:
    if target < FIXED_WINDOW_START:
        return current_bank
    return prg_banks - 1


MAX_CANDIDATES = 4096


def _byte_values(prg: bytes, prg_banks: int, bank: int, source: dict,
                 domain: list[int] | None) -> list[int] | None:
    kind = source["kind"]
    if kind == "constant":
        return [source["value"]]
    if kind == "rom_read":
        return [_read_bank_byte(prg, prg_banks, bank, source["address"])]
    if kind == "table" and domain:
        return [_read_bank_byte(prg, prg_banks, bank,
                                source["base"] + index)
                for index in domain]
    return None


def _candidate_targets(prg: bytes, prg_banks: int,
                       definitions: dict[int, dict],
                       domains: list[frozenset],
                       evaluated_banks: list[int]) -> dict[str, Any]:
    low_def = definitions[POINTER]
    high_def = definitions[POINTER_HIGH]
    low_source = low_def["source"]
    high_source = high_def["source"]
    if low_source["kind"] == "unknown" or high_source["kind"] == "unknown":
        return {"state": UNRESOLVED,
                "reason": "pointer byte value source is not statistically "
                          "known"}
    table_pair = (low_source["kind"] == "table"
                  and high_source["kind"] == "table"
                  and low_source["base"] + 1 == high_source["base"]
                  and low_source["index"] == high_source["index"])
    domain = None
    if table_pair:
        domain = sorted(domains[low_def["chain_index"]][
            1 if low_source["index"] == "x" else 2])
        if not domain or len(domain) > MAX_INDEX_DOMAIN:
            return {"state": UNRESOLVED,
                    "reason": "index domain is empty or unbounded"}
    per_bank: dict[str, Any] = {}
    feasible: set[tuple[int, int, int]] = set()
    infeasible: set[tuple[int, int]] = set()
    for bank in evaluated_banks:
        lows = _byte_values(prg, prg_banks, bank, low_source, domain)
        highs = _byte_values(prg, prg_banks, bank, high_source, domain)
        if lows is None or highs is None:
            return {"state": UNRESOLVED,
                    "reason": "a pointer byte value source is not "
                              "statically enumerable"}
        if table_pair:
            rows = [(domain[index], lows[index], highs[index])
                    for index in range(len(domain))]
        else:
            if len(lows) * len(highs) > MAX_CANDIDATES:
                return {"state": UNRESOLVED,
                        "reason": "candidate pointer space exceeds the "
                                  f"bounded limit ({len(lows)}x{len(highs)})"}
            rows = [(None, low, high) for low in lows for high in highs]
        bank_rows = []
        for index, low, high in rows:
            target = low | (high << 8)
            target_bank = _target_bank(target, bank, prg_banks)
            row = {"index": index, "target": target,
                   "target_bank": target_bank}
            if not LOW_WINDOW <= target <= HIGH_WINDOW_MAX:
                row["feasible"] = False
                row["reason"] = "target outside the PRG windows"
                infeasible.add((bank, target))
            else:
                image = bank_model.image_for_bank(prg, prg_banks,
                                                  target_bank)
                try:
                    decoded = nes.decode_full(image, target)
                    row["feasible"] = True
                    row["op"] = decoded["op"]
                    feasible.add((target_bank, target, bank))
                except nes.NES6502Error as exc:
                    row["feasible"] = False
                    row["reason"] = f"undecodable target: {exc}"
                    infeasible.add((bank, target))
            bank_rows.append(row)
        per_bank[str(bank)] = {
            "candidates": len(bank_rows),
            "feasible": sum(1 for row in bank_rows if row["feasible"]),
            "targets": sorted({(row["target_bank"], row["target"])
                               for row in bank_rows if row["feasible"]}),
            "sample_rows": bank_rows[:8],
            "row_digest": hashlib.sha256(
                ",".join(f"{row['index']}:{row['target']:04x}:"
                         f"{int(row['feasible'])}" for row in bank_rows)
                .encode("ascii")).hexdigest(),
        }
    if not feasible and infeasible:
        state = IMPOSSIBLE
        reason = "all enumerated pointer values are outside the windows or " \
                 "undecodable"
    elif feasible:
        targets = sorted({(target_bank, target)
                          for target_bank, target, _bank in feasible})
        state = (RESOLVED_EXACT if len(targets) == 1
                 else RESOLVED_FINITE_SET)
        reason = (f"pointer values from proven sources yield {len(targets)} "
                  f"feasible (target_bank, target) pairs across "
                  f"{len(evaluated_banks)} evaluated physical bank(s)")
    else:
        state = UNRESOLVED
        reason = "no candidate pointers were enumerated"
    return {
        "state": state,
        "reason": reason,
        "source_kinds": {f"0x{POINTER:02x}": low_source["kind"],
                         f"0x{POINTER_HIGH:02x}": high_source["kind"]},
        "table_pair": table_pair,
        "index_register": low_source.get("index") if table_pair else None,
        "index_domain_size": len(domain) if domain else None,
        "index_domain": domain,
        "table_base": low_source.get("base"),
        "table_high": high_source.get("base"),
        "evaluated_banks": list(evaluated_banks),
        "per_bank": per_bank,
        "feasible_targets": [[target_bank, target] for target_bank, target
                             in sorted({(item[0], item[1])
                                        for item in feasible})],
        "infeasible_count": len(infeasible),
    }


def _site_bank_provenance(bank_identities: dict[int, list[dict]] | None,
                          site: int, prg_banks: int) -> dict[str, Any]:
    identities = [entry for entry in (bank_identities or {}).get(site, [])
                  if entry["op"] == "jmp"]
    proves = sorted({entry["bank"] for entry in identities
                     if entry["provenance"] == "PROVEN"})
    candidates = sorted({entry["bank"] for entry in identities})
    if proves:
        state = "PROVEN"
        evaluated = proves
    elif candidates:
        state = "UNRESOLVED"
        evaluated = candidates
    else:
        state = "MODEL_UNREACHED"
        evaluated = list(range(prg_banks))
    return {
        "state": state,
        "proven_banks": proves,
        "candidate_banks": candidates,
        "identities": identities,
        "evaluated_banks": evaluated,
    }


def analyze_image(image: bytes, prg: bytes, prg_banks: int, sites: list[int],
                  *, bank_identities: dict[int, list[dict]] | None = None,
                  roots: list[int] | None = None) -> dict[str, Any]:
    if len(image) != 0x10000:
        raise P7IndirectError("the decode image must be exactly 64 KiB")
    if roots is None:
        raise P7IndirectError("roots are required")
    instructions = opcode_module.candidate_walk(image, roots)
    predecessors = build_predecessors(instructions)
    site_records = []
    for site in sites:
        insn = instructions.get(site)
        if insn is None or insn["op"] != "jmp" or "indirect" not in insn:
            site_records.append({
                "site": site,
                "classification": UNRESOLVED,
                "reason": "site is not a reachable indirect jmp",
                "pointer": None,
            })
            continue
        if insn["indirect"] != POINTER:
            site_records.append({
                "site": site,
                "classification": UNRESOLVED,
                "reason": f"site pointer is 0x{insn['indirect']:04x}, not "
                          f"0x{POINTER:04x}",
                "pointer": insn["indirect"],
            })
            continue
        chain = unique_chain(instructions, predecessors, site)
        domains = simulate_domains(chain)
        definitions: dict[int, dict] = {}
        for byte in (POINTER, POINTER_HIGH):
            for index in range(len(chain) - 1, -1, -1):
                if _writes_pointer(chain[index], byte):
                    definitions[byte] = {
                        "chain_index": index,
                        "instruction": {
                            "address": chain[index]["address"],
                            "op": chain[index]["op"],
                        },
                        "source": _value_source(chain, index),
                    }
                    break
        writes = [{"address": insn_["address"], "op": insn_["op"],
                   "byte": f"0x{insn_['zp']:02x}"}
                  for insn_ in chain
                  if insn_["op"] in ("sta", "stx", "sty")
                  and insn_.get("zp") in (POINTER, POINTER_HIGH)]
        pointer_reads = [
            {"address": address, "op": entry["op"]}
            for address, entry in sorted(instructions.items())
            if entry.get("zp") in (POINTER, POINTER_HIGH)
            and entry["op"] in ("lda", "ldx", "ldy", "adc", "sbc", "and",
                                "ora", "eor", "cmp", "inc", "dec", "bit")]
        relevant_start = len(chain)
        for index, entry in enumerate(chain):
            if entry["op"] in TRACKED_OPS \
                    or _writes_pointer(entry, POINTER) \
                    or _writes_pointer(entry, POINTER_HIGH):
                relevant_start = index
                break
        relevant_chain = chain[relevant_start:]
        record = {
            "site": site,
            "instruction": {"op": insn["op"], "length": insn["length"]},
            "pointer": insn["indirect"],
            "window": "low" if site < FIXED_WINDOW_START else "high",
            "chain_length": len(chain),
            "chain_relevant_length": len(relevant_chain),
            "chain_unique": bool(relevant_chain)
            and all(len(predecessors.get(entry["address"], [])) == 1
                    for entry in relevant_chain[1:])
            and all(entry["address"] + entry["length"]
                    == (relevant_chain[index + 1]["address"]
                        if index + 1 < len(relevant_chain) else site)
                    for index, entry in enumerate(relevant_chain)),
            "chain": [{"address": entry["address"], "op": entry["op"]}
                      for entry in chain[-16:]],
            "definitions": {
                f"0x{byte:02x}": definitions.get(byte)
                for byte in (POINTER, POINTER_HIGH)
            },
            "writes": writes,
            "pointer_reads": pointer_reads,
            "bank_provenance": _site_bank_provenance(bank_identities, site,
                                                     prg_banks),
        }
        if POINTER not in definitions or POINTER_HIGH not in definitions:
            record["classification"] = UNRESOLVED
            record["reason"] = "no reaching definition for a pointer byte on " \
                               "the unique chain"
            site_records.append(record)
            continue
        if not record["chain_unique"]:
            record["classification"] = UNRESOLVED
            record["reason"] = "the chain has a middle entry or is not a " \
                               "unique fallthrough path"
            site_records.append(record)
            continue
        sources = [definitions[POINTER]["source"],
                   definitions[POINTER_HIGH]["source"]]
        if any(source["kind"] == "unknown" for source in sources):
            record["classification"] = UNRESOLVED
            record["reason"] = "pointer byte value source is not statically " \
                               "known: " + "; ".join(
                                   source.get("reason", "unknown")
                                   for source in sources)
            site_records.append(record)
            continue
        resolution = _candidate_targets(
            prg, prg_banks, definitions, domains,
            record["bank_provenance"]["evaluated_banks"])
        record.update(resolution)
        record["classification"] = resolution["state"]
        site_records.append(record)
    counts: dict[str, int] = {}
    for record in site_records:
        state = record["classification"]
        counts[state] = counts.get(state, 0) + 1
    return {
        "stage": "P7-06",
        "sites": site_records,
        "counts": counts,
        "claim": "indirect-jump evidence with explicit RESOLVED_EXACT / "
                 "RESOLVED_FINITE_SET / UNRESOLVED / IMPOSSIBLE states; "
                 "targets are enumerated from proven value sources only and "
                 "never guessed",
    }


def analyze_private(path: pathlib.Path | str = private_fixture.PRIVATE_ROM) -> dict[str, Any]:
    location = pathlib.Path(path)
    if not location.is_file():
        raise P7IndirectError("private compatibility fixture is not present")
    data = location.read_bytes()
    image, inventory = opcode_module.build_image(data)
    prg_bytes = int(inventory["prg_bytes"])
    prg_banks = prg_bytes // bank_model.PRG_BANK_BYTES
    prg = data[16:16 + prg_bytes]
    roots = [inventory["vectors"][name] for name in ("reset", "nmi", "irq")]
    bank_report = bank_model.analyze(prg, prg_banks, roots,
                                     budget=300000, unresolved_limit=20000)
    identifiers: dict[int, list[dict]] = {}
    for entry in bank_report["instructions"]:
        identifiers.setdefault(entry["address"], []).append(entry)
    record = analyze_image(image, prg, prg_banks, list(PRIVATE_SITES),
                           bank_identities=identifiers, roots=roots)
    record.update({
        "fixture": "private_tmnt",
        "image_sha256": inventory["image_sha256"],
        "image_size": inventory["actual_size"],
        "prg_banks": prg_banks,
        "bank_model": {
            "status": bank_report["status"],
            "nodes_visited": bank_report["nodes_visited"],
            "proven_instructions": bank_report["proven_instructions"],
            "unresolved_instructions": bank_report["unresolved_instructions"],
            "unresolved_limited": bank_report["unresolved_limited"],
        },
        "public_claim": "none; private local analysis must not enter the "
                        "public package",
    })
    return record


__all__ = [
    "IMPOSSIBLE",
    "POINTER",
    "PRIVATE_SITES",
    "P7IndirectError",
    "RESOLVED_EXACT",
    "RESOLVED_FINITE_SET",
    "UNRESOLVED",
    "analyze_image",
    "analyze_private",
    "build_predecessors",
    "simulate_domains",
    "unique_chain",
]
