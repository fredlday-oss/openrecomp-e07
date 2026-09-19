#!/usr/bin/env python3
"""Phase-7 bank-aware MMC1 cartridge reachability model (P7-04).

Models executable reachability across MMC1 PRG bank states with explicit
fixed and switchable windows:

* code identity is `(physical_prg_bank, cpu_address)`, never a bare CPU
  address: two different physical banks sharing `$8000-$BFFF` remain distinct;
* the current window layout is derived from the audited MMC1 control/PRG
  register state through the frozen independent reference model
  (`p6_mapper1_prg_reference_v1.reference_window_banks`), covering PRG modes 0
  through 3;
* statically unrolled five-write constant sequences (the audited MMC1 serial
  protocol: LSB first, bit-7 shift reset, register selected by address bits
  14:13) commit concrete register values; a committed PRG register becomes a
  proven bank state;
* control-register and PRG-register provenance are tracked separately, so an
  unresolved PRG value does not taint a window that mode 3 keeps fixed, and an
  unresolved control value taints both windows;
* any writer that cannot be resolved statically (non-constant value, CHR or
  control address with unknown value, indexed/indirect store, or two
  consecutive mapper writes whose cycle-adjacent suppression cannot be
  excluded) marks the affected register unresolved for that path; banks that
  remain unknown are expanded individually with provenance `UNRESOLVED`
  instead of being guessed or merged;
* every reachable instruction carries `PROVEN` or `UNRESOLVED` bank
  provenance, and the same CPU address reached under different physical banks
  is recorded as separate identities and reported in
  `multi_bank_cpu_addresses`;
* malformed bank counts/roots, window-spanning instructions, undecodable
  reachable opcodes and budgets fail closed with a deterministic status.

The model is static only: it never executes guest code and never reads or
writes private data. Cycle-adjacent MMC1 write suppression is not modelled
because static instruction addresses carry no cycle schedule; two adjacent
mapper writes are therefore treated as ambiguous and fail closed.
"""
from __future__ import annotations

import hashlib
import json
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
import p6_mapper1_prg_reference_v1 as prg_reference  # noqa: E402

CPU_SIZE = 0x10000
PRG_BANK_BYTES = 0x4000
PRG_BANKS_VALID = frozenset({1, 2, 4, 8, 16})
LOW_WINDOW = (0x8000, 0xBFFF)
HIGH_WINDOW = (0xC000, 0xFFFF)
MAPPER_WRITE_MIN = 0x8000
MAPPER_WRITE_MAX = 0xFFFF
SERIAL_BITS = 5
DEFAULT_BUDGET = 200000
DEFAULT_UNRESOLVED_LIMIT = 4096

PROVEN = "PROVEN"
UNRESOLVED = "UNRESOLVED"

BRANCH_OPS = frozenset({"bpl", "bmi", "bvc", "bvs", "bcc", "bcs", "bne", "beq"})


class BankReachabilityError(ValueError):
    """Fail-closed bank-aware reachability error."""


def _validate(prg: bytes, prg_banks: int, roots: list[int],
              budget: int) -> None:
    if not isinstance(prg, (bytes, bytearray)):
        raise BankReachabilityError("PRG must be bytes")
    if prg_banks not in PRG_BANKS_VALID:
        raise BankReachabilityError(f"unsupported PRG bank count {prg_banks}")
    if len(prg) != prg_banks * PRG_BANK_BYTES:
        raise BankReachabilityError("PRG size does not match the bank count")
    if not roots:
        raise BankReachabilityError("at least one root is required")
    for root in roots:
        if isinstance(root, bool) or not isinstance(root, int):
            raise BankReachabilityError("roots must be integers")
        if not LOW_WINDOW[0] <= root <= HIGH_WINDOW[1]:
            raise BankReachabilityError(
                f"root 0x{root:x} is outside the PRG window")
    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        raise BankReachabilityError("budget must be a positive integer")


def image_for_bank(prg: bytes, prg_banks: int, bank: int) -> bytes:
    """64 KiB decode image with `bank` mapped at both PRG windows."""
    if not 0 <= bank < prg_banks:
        raise BankReachabilityError(f"bank {bank} out of range")
    image = bytearray(CPU_SIZE)
    chunk = prg[bank * PRG_BANK_BYTES:(bank + 1) * PRG_BANK_BYTES]
    image[LOW_WINDOW[0]:LOW_WINDOW[0] + PRG_BANK_BYTES] = chunk
    image[HIGH_WINDOW[0]:HIGH_WINDOW[0] + PRG_BANK_BYTES] = chunk
    return bytes(image)


def _window_of(address: int) -> str:
    if LOW_WINDOW[0] <= address <= LOW_WINDOW[1]:
        return "low"
    if HIGH_WINDOW[0] <= address <= HIGH_WINDOW[1]:
        return "high"
    raise BankReachabilityError(f"address 0x{address:x} outside the PRG windows")


def window_banks_partial(control: int | None, prg_reg: int | None,
                         prg_banks: int) -> tuple[int | None, int | None]:
    """Per-window physical banks with partial knowledge (None = unknown)."""
    if control is None:
        return None, None
    mode = (control // 4) % 4
    if mode in (0, 1):
        if prg_reg is None:
            return None, None
        first = (prg_reg - (prg_reg % 2)) % prg_banks
        second = (first + 1) % prg_banks
        return first, second
    if mode == 2:
        return 0, (None if prg_reg is None else prg_reg % prg_banks)
    return (None if prg_reg is None else prg_reg % prg_banks), prg_banks - 1


def _reference_layout(control: int, prg_reg: int,
                      prg_banks: int) -> dict[str, Any]:
    try:
        first, second = prg_reference.reference_window_banks(
            control, prg_reg, prg_banks)
        layout = prg_reference.reference_layout(control, prg_reg, prg_banks)
    except prg_reference.MMC1PrgReferenceError as exc:
        raise BankReachabilityError(f"window layout failed: {exc}") from exc
    return {
        "window_8000_bank": first,
        "window_c000_bank": second,
        "prg_mode": layout["prg_mode"],
        "control": control,
        "prg_register": prg_reg,
    }


def _writes_accumulator(insn: dict) -> bool:
    op = insn["op"]
    if op in ("sta", "stx", "sty", "cmp", "cpx", "cpy", "bit", "nop", "inc",
              "dec"):
        return False
    if op in ("pha", "php", "jsr", "jmp", "rts", "rti", "brk"):
        return False
    if op in BRANCH_OPS:
        return False
    return True


def _is_store(insn: dict) -> tuple[bool, bool, int]:
    """Return (is_store, address_known, address)."""
    op = insn["op"]
    if op not in ("sta", "stx", "sty"):
        return False, False, 0
    if "abs" in insn:
        return True, True, insn["abs"]
    if "abs,x" in insn or "abs,y" in insn or "indirect,x" in insn \
            or "indirect,y" in insn:
        return True, False, 0
    return False, False, 0


def analyze(prg: bytes, prg_banks: int, roots: list[int], *,
            budget: int = DEFAULT_BUDGET,
            unresolved_limit: int = DEFAULT_UNRESOLVED_LIMIT) -> dict[str, Any]:
    """Bank-aware static reachability analysis over the PRG windows.

    `unresolved_limit` bounds how many `UNRESOLVED`-provenance candidate
    instructions are expanded across possible physical banks; when the limit
    is reached the unresolved frontier is marked truncated (`unresolved_limited`)
    and no further unresolved candidates are decoded. `PROVEN` reachability is
    never truncated.
    """
    _validate(prg, prg_banks, list(roots), budget)
    if isinstance(unresolved_limit, bool) or not isinstance(unresolved_limit, int) \
            or unresolved_limit <= 0:
        raise BankReachabilityError("unresolved_limit must be a positive integer")
    unresolved_limited = False
    unresolved_nodes = 0
    images = {bank: image_for_bank(prg, prg_banks, bank)
              for bank in range(prg_banks)}

    # State: (control or None, prg_reg or None, shift, count, const_a,
    #         prev_write)
    start_state = (0x0C, 0x00, 0, 0, None, False)

    pending: list[tuple[int, tuple]] = [(root, start_state) for root in roots]
    visited: set[tuple] = set()
    code: dict[tuple[int, int], dict[str, Any]] = {}
    covered: dict[int, set[int]] = {bank: set() for bank in range(prg_banks)}
    bank_switches: list[dict[str, Any]] = []
    unresolved_writes: list[dict[str, Any]] = []
    unresolved_decode_sites: list[dict[str, Any]] = []
    mode_histogram: dict[str, int] = {}
    dynamic_returns: list[dict[str, Any]] = []
    indirect_sites: list[dict[str, Any]] = []
    stop: dict[str, Any] | None = None
    status = "OK"

    while pending:
        pc, state = pending.pop()
        (control, prg_reg, shift, count, const_a, prev_write) = state
        if not LOW_WINDOW[0] <= pc <= HIGH_WINDOW[1]:
            if control is not None and prg_reg is not None:
                status = "BLOCKED_TARGET_OUTSIDE"
                stop = {"address": pc, "reason": "direct control-flow target "
                                                  "outside the PRG windows"}
                break
            unresolved_decode_sites.append({
                "address": pc, "bank": None,
                "reason": "direct control-flow target outside the PRG windows "
                          "under unresolved provenance"})
            continue
        low_bank, high_bank = window_banks_partial(control, prg_reg, prg_banks)
        slot = _window_of(pc)
        bank = low_bank if slot == "low" else high_bank
        if bank is None:
            banks = list(range(prg_banks))
            provenance = UNRESOLVED
        else:
            banks = [bank]
            provenance = PROVEN

        for bank in banks:
            node_key = (pc, bank, state)
            if node_key in visited:
                continue
            if provenance == UNRESOLVED:
                if unresolved_nodes >= unresolved_limit:
                    unresolved_limited = True
                    continue
                unresolved_nodes += 1
            if len(visited) >= budget:
                status = "BLOCKED_BUDGET"
                stop = {"address": pc, "bank": bank, "reason": "budget"}
                break
            visited.add(node_key)
            image = images[bank]
            try:
                insn = nes.decode_full(image, pc)
            except nes.NES6502Error as exc:
                if provenance == PROVEN:
                    status = "BLOCKED_UNDECODABLE"
                    stop = {"address": pc, "bank": bank,
                            "reason": f"{type(exc).__name__}: {exc}"}
                    break
                unresolved_decode_sites.append({
                    "address": pc, "bank": bank,
                    "reason": f"{type(exc).__name__}: {exc}"})
                continue
            window = _window_of(pc)
            last = pc + insn["length"] - 1
            if _window_of(last) != window:
                if provenance == PROVEN:
                    status = "BLOCKED_WINDOW_SPAN"
                    stop = {"address": pc, "bank": bank,
                            "reason": "instruction spans the "
                                      "fixed/switchable window boundary"}
                    break
                unresolved_decode_sites.append({
                    "address": pc, "bank": bank,
                    "reason": "instruction spans the fixed/switchable "
                              "window boundary"})
                continue
            key = (bank, pc)
            if key in code:
                code[key]["visits"] += 1
            else:
                code[key] = {"address": pc, "op": insn["op"],
                             "length": insn["length"],
                             "window": window, "provenance": provenance,
                             "visits": 1}
            covered[bank].update(range(pc, pc + insn["length"]))
            if control is not None:
                mode = str((control // 4) % 4)
                mode_histogram[mode] = mode_histogram.get(mode, 0) + 1

            new_control, new_prg = control, prg_reg
            new_shift, new_count = shift, count
            new_const = const_a
            new_prev_write = False

            is_store, address_known, address = _is_store(insn)
            if is_store and not address_known:
                if control is not None or prg_reg is not None:
                    unresolved_writes.append({
                        "address": pc, "bank": bank,
                        "reason": "indexed/indirect store could target the "
                                  "MMC1 register windows; fail closed"})
                new_control, new_prg = None, None
                new_shift, new_count = 0, 0
            elif is_store and address_known \
                    and MAPPER_WRITE_MIN <= address <= MAPPER_WRITE_MAX:
                register = (address >> 13) & 3
                new_prev_write = True
                if prev_write:
                    unresolved_writes.append({
                        "address": pc, "bank": bank, "register": register,
                        "reason": "two consecutive MMC1 writes: "
                                  "cycle-adjacent suppression cannot be "
                                  "excluded statically; fail closed"})
                    new_control, new_prg = None, None
                    new_shift, new_count = 0, 0
                elif insn["op"] != "sta" or const_a is None:
                    unresolved_writes.append({
                        "address": pc, "bank": bank, "register": register,
                        "reason": "MMC1 write value is not a statically "
                                  "known constant; fail closed"})
                    if register == 0:
                        new_control = None
                    elif register == 3:
                        new_prg = None
                    new_shift, new_count = 0, 0
                else:
                    value = const_a
                    if value & 0x80:
                        new_shift, new_count = 0, 0
                    else:
                        new_shift = new_shift | ((value & 0x01) << new_count)
                        new_count += 1
                        if new_count == SERIAL_BITS:
                            if register == 0:
                                new_control = new_shift & 0x1F
                            elif register == 3:
                                new_prg = new_shift & 0x1F
                            switch = {"address": pc, "bank": bank,
                                      "register": register,
                                      "value": new_shift & 0x1F}
                            if new_control is not None \
                                    and new_prg is not None:
                                switch["result_layout"] = _reference_layout(
                                    new_control, new_prg, prg_banks)
                                switch["window_8000_bank"] = \
                                    switch["result_layout"]["window_8000_bank"]
                                switch["window_c000_bank"] = \
                                    switch["result_layout"]["window_c000_bank"]
                            bank_switches.append(switch)
                            new_shift, new_count = 0, 0

            if insn["op"] == "lda" and "imm8" in insn:
                new_const = insn["imm8"]
            elif _writes_accumulator(insn):
                new_const = None
            if insn["op"] in ("jmp", "jsr", "rts", "rti", "brk") \
                    or insn["op"] in BRANCH_OPS:
                new_const = None
            next_state = (new_control, new_prg, new_shift, new_count,
                          new_const, new_prev_write)

            if insn["op"] in ("rts", "rti"):
                dynamic_returns.append({"address": pc, "bank": bank,
                                        "instruction": insn["op"]})
            targets, unresolved = frozen_frontier.successors(insn, pc)
            if unresolved:
                indirect_sites.append({"address": pc, "bank": bank,
                                       "instruction": insn["op"],
                                       "pointer": insn.get("indirect")})
            for target in targets:
                pending.append((target, next_state))
        if status != "OK":
            break

    multi_bank: dict[int, set[int]] = {}
    identities = []
    for (bank, address), entry in sorted(code.items()):
        identities.append([bank, address, entry["provenance"]])
        multi_bank.setdefault(address, set()).add(bank)
    code_by_bank: list[dict[str, Any]] = []
    for bank in range(prg_banks):
        entries = [entry for (entry_bank, _address), entry in code.items()
                   if entry_bank == bank]
        if not entries:
            continue
        proven = sum(1 for entry in entries
                     if entry["provenance"] == PROVEN)
        resolved = len(entries) - proven
        code_by_bank.append({
            "bank": bank,
            "provenance": (PROVEN if resolved == 0 else UNRESOLVED),
            "instructions": len(entries),
            "proven_instructions": proven,
            "unresolved_instructions": resolved,
            "bytes": len(covered[bank]),
            "cpu_range": [min(entry["address"] for entry in entries),
                          max(entry["address"] for entry in entries)],
            "address_samples": sorted(entry["address"] for entry in entries)[:16],
            "address_digest": hashlib.sha256(
                ",".join(f"{entry['address']:04x}" for entry in entries)
                .encode("ascii")).hexdigest(),
        })
    collisions = {str(address): sorted(banks)
                  for address, banks in sorted(multi_bank.items())
                  if len(banks) > 1}
    proven_instructions = sum(
        1 for entry in code.values() if entry["provenance"] == PROVEN)
    unresolved_instructions = sum(
        1 for entry in code.values() if entry["provenance"] == UNRESOLVED)
    digest = hashlib.sha256(json.dumps(
        {"identities": identities, "switches": bank_switches},
        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "status": status,
        "stop": stop,
        "prg_banks": prg_banks,
        "nodes_visited": len(visited),
        "instructions": len(code),
        "proven_instructions": proven_instructions,
        "unresolved_instructions": unresolved_instructions,
        "unresolved_limited": unresolved_limited,
        "unresolved_limit": unresolved_limit,
        "code_by_bank": code_by_bank,
        "identity_digest": digest,
        "bank_switches": bank_switches,
        "unresolved_mapper_writes": unresolved_writes,
        "unresolved_decode_sites": sorted(
            unresolved_decode_sites,
            key=lambda item: (item["address"], item["bank"])),
        "mode_histogram": dict(sorted(mode_histogram.items())),
        "multi_bank_cpu_addresses": collisions,
        "dynamic_returns": sorted(dynamic_returns,
                                  key=lambda item: (item["address"],
                                                    item["bank"])),
        "indirect_sites": sorted(indirect_sites,
                                 key=lambda item: (item["address"],
                                                   item["bank"])),
        "claim": "bank-aware static reachability; PROVEN code is safe to "
                 "translate, UNRESOLVED code is candidate only; different "
                 "physical banks sharing a CPU address are never merged",
    }


__all__ = [
    "BankReachabilityError",
    "DEFAULT_BUDGET",
    "HIGH_WINDOW",
    "LOW_WINDOW",
    "PRG_BANK_BYTES",
    "PROVEN",
    "UNRESOLVED",
    "analyze",
    "image_for_bank",
    "window_banks_partial",
]
