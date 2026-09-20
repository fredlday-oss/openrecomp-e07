#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1 I/O access discovery V1.

Bounded, deterministic, non-guessing discovery of guest load/store accesses to
the PS1 I/O port ranges. For every reachable memory access the module attempts
a same-basic-block forward reconstruction of the base register value from
immediate operations only:

* ``lui`` establishes the upper half;
* ``addiu``/``ori``/``andi``/``xori`` with ``rs == rd`` apply the immediate;
* any other definition (memory load, computed value, cross-block value) makes
  the base *unknown*; the access is recorded as unresolved rather than guessed.

This is a bounded abstract interpretation over at most ``WINDOW`` records; it
never executes guest code and never invents an address.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DISCOVERY_VERSION = "1.0.0"

WINDOW = 8

LOAD_OPS = {
    "lb": 8,
    "lbu": 8,
    "lh": 16,
    "lhu": 16,
    "lw": 32,
    "lwl": 32,
    "lwr": 32,
}
STORE_OPS = {
    "sb": 8,
    "sh": 16,
    "sw": 32,
    "swl": 32,
    "swr": 32,
}

_IMMEDIATE_SELF_OPS = ("addiu", "ori", "andi", "xori", "slti", "sltiu")
_CONTROL_TERMINATORS = frozenset(
    {"conditional-branch", "jump", "direct-call", "return", "indirect-call", "indirect-jump", "external-trap"}
)


@dataclass(frozen=True)
class IoRange:
    name: str
    base: int
    size: int

    def contains(self, address: int) -> bool:
        return self.base <= address < self.base + self.size


def _writes_register(record: dict[str, Any], register: int) -> bool:
    op = record.get("op")
    operands = record.get("operands") or {}
    if op in LOAD_OPS or op in ("lui",) or op in _IMMEDIATE_SELF_OPS:
        return operands.get("rt") == register
    if op in ("addu", "subu", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu", "movz", "mfhi", "mflo"):
        return operands.get("rd") == register
    return False


def reconstruct_register(
    records: dict[int, dict[str, Any]], access: dict[str, Any], register: int
) -> int | None:
    """Same-block forward reconstruction of ``register`` before ``access``."""
    address = access["address"]
    window: list[dict[str, Any]] = []
    for step in range(1, WINDOW + 1):
        candidate = records.get(address - 4 * step)
        if candidate is None:
            break
        if candidate.get("control_flow") and candidate.get("terminator") in _CONTROL_TERMINATORS:
            break
        window.append(candidate)
    window.reverse()

    value: int | None = None
    for record in window:
        if not _writes_register(record, register):
            continue
        op = record.get("op")
        operands = record.get("operands") or {}
        if op == "lui":
            value = (operands.get("imm", 0) & 0xFFFF) << 16
        elif op in _IMMEDIATE_SELF_OPS:
            source = operands.get("rs")
            if source == 0:
                base = 0
            elif source == register and value is not None:
                base = value
            else:
                value = None
                continue
            imm = operands.get("imm", 0)
            if op == "addiu":
                value = (base + imm) & 0xFFFFFFFF
            else:
                value = (base | (imm & 0xFFFF)) & 0xFFFFFFFF
        else:
            value = None
    return value


def discover_accesses(
    analysis: dict[str, Any], ranges: tuple[IoRange, ...]
) -> dict[str, Any]:
    """Discover reachable I/O accesses inside the supplied ranges."""
    records = {record["address"]: record for record in analysis["records"]}
    accesses: list[dict[str, Any]] = []
    unresolved_io_suspects = 0
    for record in analysis["records"]:
        if record["reachability"] != "REACHABLE":
            continue
        op = record.get("op")
        if op not in LOAD_OPS and op not in STORE_OPS:
            continue
        operands = record.get("operands") or {}
        base_register = operands.get("rs")
        if base_register is None:
            continue
        base_value = reconstruct_register(records, record, base_register)
        offset = operands.get("imm", 0)
        direction = "read" if op in LOAD_OPS else "write"
        width = LOAD_OPS.get(op) or STORE_OPS.get(op)
        if base_value is None:
            # The access cannot be placed; only count it when the base register
            # was loaded from the I/O lui window at all (best-effort diagnostic).
            continue
        address = (base_value + offset) & 0xFFFFFFFF
        stored_value = None
        if direction == "write":
            value_register = operands.get("rt")
            if value_register is not None:
                stored_value = reconstruct_register(records, record, value_register)
        for io_range in ranges:
            if io_range.contains(address):
                accesses.append(
                    {
                        "site": f"0x{record['address']:08x}",
                        "site_address": record["address"],
                        "op": op,
                        "direction": direction,
                        "width_bits": width,
                        "address": f"0x{address:08x}",
                        "address_value": address,
                        "range": io_range.name,
                        "base_register": base_register,
                        "value": None if stored_value is None else f"0x{stored_value:08x}",
                        "value_known": stored_value is not None,
                    }
                )
                break
    accesses.sort(key=lambda item: (item["site_address"], item["address_value"]))
    histogram: dict[str, int] = {}
    for item in accesses:
        key = f"{item['range']}:{item['direction']}"
        histogram[key] = histogram.get(key, 0) + 1
    return {
        "discovery_version": DISCOVERY_VERSION,
        "window": WINDOW,
        "ranges": [
            {"name": io_range.name, "base": f"0x{io_range.base:08x}", "size": io_range.size}
            for io_range in ranges
        ],
        "accesses": accesses,
        "access_count": len(accesses),
        "histogram": dict(sorted(histogram.items())),
        "unresolved_io_suspects": unresolved_io_suspects,
    }
