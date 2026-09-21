#!/usr/bin/env python3
"""OpenRecomp Phase-10 exception/trap classification V1.

The module provides the architectural classification of the MIPS
exception-raising instructions that the frozen Phase-3 decoder records as
``external-trap`` records, and the bounded handling strategy for them.

Architectural basis (public MIPS/PS1 facts, stated explicitly and never
extended by guessing):

* ``SPECIAL`` funct ``0x0C`` is ``SYSCALL`` and funct ``0x0D`` is ``BREAK``;
* both raise a synchronous exception, not a control transfer: there is no
  branch delay slot and the instruction does not execute a jump;
* the exception code is reported in ``Cause.ExcCode``: ``8`` = ``Sys``
  (SYSCALL) and ``9`` = ``Bp`` (BREAK);
* for a synchronous exception raised by the instruction itself, ``EPC`` holds
  the address of the faulting instruction and ``Cause.BD`` is 0 unless the
  faulting instruction occupies a branch delay slot;
* the general exception vector is ``0x80000080`` with ``BEV`` = 0 and
  ``0xBFC00180`` with ``BEV`` = 1;
* whether a handler ever returns to (or past) the faulting instruction is
  handler-specific and is NOT modelled here.

The bounded handling strategy is therefore:

* statically, the instruction becomes an explicit terminal exception site with
  ``InstructionFlow.TRAP`` and no successor (no delay slot is manufactured and
  no fall-through is fabricated);
* dynamically, executing such a site fails closed with an explicit
  ``GUEST_BREAK`` / ``GUEST_SYSCALL`` category; no exception delivery, no BIOS
  handler and no continuation is invented;
* a trap that occupies a branch delay slot sets ``Cause.BD`` = 1 and is a
  different case: it is rejected as unsupported rather than folded.

Nothing in this module executes code or writes payload bytes.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

EXCEPTION_VERSION = "1.0.0"

#: Public MIPS exception codes relevant to the bounded Phase-10 frontier.
EXCEPTION_CODES = {
    8: "Sys",
    9: "Bp",
    12: "Ov",
    13: "Tr",
}

#: PS1 general-exception vector addresses for the two BEV states.
EXCEPTION_VECTORS = {
    "BEV0": 0x80000080,
    "BEV1": 0xBFC00180,
}

#: Architecturally defined trap-raising SPECIAL functs for this bounded form.
TRAP_FUNCTS = {
    0x0C: "syscall",
    0x0D: "break",
}

TRAP_EXCEPTION_CODES = {
    "syscall": 8,
    "break": 9,
}

TERMINATOR_EXTERNAL_TRAP = "external-trap"

#: Bounded handling categories surfaced to the runtime.
HANDLING_CATEGORIES = {
    "break": "GUEST_BREAK",
    "syscall": "GUEST_SYSCALL",
}

CONTINUATION_POLICY = "NOT_MODELLED_FAIL_CLOSED"

ERROR_CODES = (
    "NOT_A_TRAP_RECORD",
    "UNSUPPORTED_TRAP_OP",
    "TRAP_FLAG_MISMATCH",
    "TRAP_HAS_DELAY_SLOT",
    "TRAP_HAS_TARGET",
    "TRAP_CODE_OUT_OF_RANGE",
)


class TrapClassificationError(ValueError):
    """Fail-closed trap classification error with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown trap classification error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise TrapClassificationError(code, detail)


def architectural_facts() -> dict[str, Any]:
    """Deterministic record of the public architectural facts used here."""
    return {
        "exception_version": EXCEPTION_VERSION,
        "special_functs": {f"0x{funct:02x}": name for funct, name in sorted(TRAP_FUNCTS.items())},
        "exception_codes": {str(code): name for code, name in sorted(EXCEPTION_CODES.items())},
        "trap_exception_codes": dict(sorted(TRAP_EXCEPTION_CODES.items())),
        "vectors": {name: f"0x{value:08x}" for name, value in sorted(EXCEPTION_VECTORS.items())},
        "epc_rule": "synchronous fault: EPC = faulting instruction address, Cause.BD = 0 unless in a delay slot",
        "continuation_policy": CONTINUATION_POLICY,
        "handling_categories": dict(sorted(HANDLING_CATEGORIES.items())),
    }


def decode_trap_word(word: int) -> dict[str, int]:
    """Independent bit extraction of a SPECIAL trap encoding.

    The extraction uses only the encoded word and does not call the frozen
    decoder, so it is an independent reference for the frozen classification.
    """
    _require(isinstance(word, int) and 0 <= word <= 0xFFFFFFFF, "TRAP_CODE_OUT_OF_RANGE", repr(word))
    opcode = (word >> 26) & 0x3F
    funct = word & 0x3F
    code20 = (word >> 6) & 0xFFFFF
    code10 = (word >> 6) & 0x3FF
    return {
        "opcode": opcode,
        "funct": funct,
        "code20": code20,
        "code10": code10,
    }


def classify_trap_site(record: dict[str, Any]) -> dict[str, Any]:
    """Classify one frozen frontier ``external-trap`` record exactly."""
    op = record.get("op")
    if record.get("terminator") != TERMINATOR_EXTERNAL_TRAP or op not in TRAP_FUNCTS.values():
        raise TrapClassificationError("NOT_A_TRAP_RECORD", f"{op!r} {record.get('terminator')!r}")
    _require(record.get("control_flow") is True, "TRAP_FLAG_MISMATCH", "control_flow")
    _require(record.get("exception_transfer") is True, "TRAP_FLAG_MISMATCH", "exception_transfer")
    _require(record.get("delay_slot") is False, "TRAP_HAS_DELAY_SLOT", f"0x{record.get('address', 0):08x}")
    _require(record.get("target") is None, "TRAP_HAS_TARGET", f"0x{record.get('address', 0):08x}")

    address = record.get("address")
    word = record.get("word")
    _require(isinstance(address, int) and address % 4 == 0, "TRAP_CODE_OUT_OF_RANGE", repr(address))
    _require(isinstance(word, int), "TRAP_CODE_OUT_OF_RANGE", repr(word))

    decoded = decode_trap_word(word)
    _require(decoded["opcode"] == 0, "NOT_A_TRAP_RECORD", "opcode")
    _require(TRAP_FUNCTS[decoded["funct"]] == op, "NOT_A_TRAP_RECORD", "funct mismatch")

    operands = record.get("operands") or {}
    recorded_code = operands.get("code")
    _require(recorded_code == decoded["code20"], "TRAP_CODE_OUT_OF_RANGE", f"{recorded_code!r} != {decoded['code20']}")

    exc_code = TRAP_EXCEPTION_CODES[op]
    return {
        "site": address,
        "site_hex": f"0x{address:08x}",
        "op": op,
        "code": decoded["code20"],
        "code_hex": f"0x{decoded['code20']:05x}",
        "funct": decoded["funct"],
        "exception_code": exc_code,
        "exception_name": EXCEPTION_CODES[exc_code],
        "epc": address,
        "bd": 0,
        "delay_slot": False,
        "successors": [],
        "vector_bev0": f"0x{EXCEPTION_VECTORS['BEV0']:08x}",
        "vector_bev1": f"0x{EXCEPTION_VECTORS['BEV1']:08x}",
        "continuation": CONTINUATION_POLICY,
        "handling": "explicit-trap-terminator",
        "runtime_category": HANDLING_CATEGORIES[op],
        "evidence": "PROVEN",
    }


def classify_trap_sites(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify every reachable trap record deterministically."""
    sites = [
        classify_trap_site(record)
        for record in records
        if record.get("terminator") == TERMINATOR_EXTERNAL_TRAP
    ]
    sites.sort(key=lambda item: item["site"])
    histogram: dict[str, int] = {}
    for site in sites:
        histogram[site["op"]] = histogram.get(site["op"], 0) + 1
    return {
        "exception_version": EXCEPTION_VERSION,
        "site_count": len(sites),
        "histogram": dict(sorted(histogram.items())),
        "sites": sites,
        "continuation_policy": CONTINUATION_POLICY,
    }


def word_from_le_bytes(data: bytes) -> int:
    _require(len(data) == 4, "TRAP_CODE_OUT_OF_RANGE", f"{len(data)} bytes")
    return struct.unpack("<I", data)[0]


def _delay_owner(analysis: dict[str, Any], address: int) -> int | None:
    for slot in analysis.get("delay_slots", []):
        if slot.get("delay") == address:
            return slot.get("owner")
    return None


def trap_site_context(analysis: dict[str, Any], site: int) -> dict[str, Any]:
    """Exact predecessor and region context for one trap site.

    The walk uses only the frozen frontier records: reachability, decoded
    control classification, delay-slot ownership and direct-call targets.
    Nothing is inferred beyond those records.
    """
    records = analysis.get("records") or []
    by_address = {record["address"]: record for record in records}
    reachable = set(analysis.get("reachable_addresses") or [])
    _require(site in by_address and site in reachable, "NOT_A_TRAP_RECORD", f"0x{site:08x}")

    entry = analysis.get("entry")
    call_targets = {
        record["target"]
        for record in records
        if record.get("control_flow")
        and record.get("terminator") == "direct-call"
        and isinstance(record.get("target"), int)
        and record["address"] in reachable
    }
    boundaries = set(call_targets)
    if isinstance(entry, int):
        boundaries.add(entry)
    region_start = max(value for value in boundaries if value <= site)

    predecessor_chain: list[dict[str, Any]] = []
    current = site
    predecessor_kind = "unresolved"
    predecessor_site: int | None = None
    while True:
        previous = current - 4
        record = by_address.get(previous)
        if record is None or previous not in reachable:
            predecessor_kind = "region-boundary"
            break
        owner = _delay_owner(analysis, current)
        if owner is not None and owner == previous:
            terminator = record.get("terminator")
            predecessor_kind = {
                "direct-call": "direct-call-continuation",
                "conditional-branch": "conditional-branch-continuation",
                "indirect-call": "indirect-call-continuation",
            }.get(terminator, f"{terminator}-continuation")
            predecessor_site = previous
            predecessor_chain.append({"address": previous, "role": predecessor_kind})
            break
        if record.get("control_flow"):
            predecessor_kind = "control-without-fallthrough"
            predecessor_site = previous
            predecessor_chain.append({"address": previous, "role": predecessor_kind})
            break
        predecessor_chain.append({"address": previous, "role": "straight-line-predecessor"})
        current = previous
        if previous <= region_start:
            predecessor_kind = "region-entry"
            break

    inbound_targets = sorted(
        record["address"]
        for record in records
        if isinstance(record.get("target"), int)
        and record["target"] == site
        and record["address"] in reachable
    )
    returns_before = sorted(
        record["address"]
        for record in records
        if record.get("terminator") == "return"
        and record["address"] in reachable
        and region_start <= record["address"] < site
    )
    return {
        "site": site,
        "site_hex": f"0x{site:08x}",
        "region_start": region_start,
        "region_start_hex": f"0x{region_start:08x}",
        "region_start_is_entry": region_start == entry,
        "region_start_is_direct_call_target": region_start in call_targets,
        "predecessor_kind": predecessor_kind,
        "predecessor_site": predecessor_site,
        "predecessor_site_hex": None if predecessor_site is None else f"0x{predecessor_site:08x}",
        "predecessor_chain": list(reversed(predecessor_chain)),
        "inbound_targets": inbound_targets,
        "inbound_target_count": len(inbound_targets),
        "reachable_returns_before_site": returns_before,
        "reachable_return_count_before_site": len(returns_before),
        "reached_by_fallthrough_only": not inbound_targets,
    }
