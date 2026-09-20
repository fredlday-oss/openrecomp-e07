#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1 translation-frontier closure V1.

The module reuses the frozen Phase-8 closed MIPS32 semantic rule table
(``p8_mips32_semantics_v1``) unchanged and adds only:

* an explicit coverage check that classifies every reachable neutral
  instruction of a PS1 pipeline result exactly once against the table;
* an explicit, evidence-based classification of the reachable
  recognized-unsupported MIPS32 forms (so nothing is silently ignored or
  guessed);
* an explicit COP0/GTE reachability scan.

No new instruction semantics are added here. If the bounded fixture required a
form outside the frozen table, the coverage check fails closed instead of
inventing behaviour.
"""

from __future__ import annotations

from typing import Any, Iterable

import p8_mips32_semantics_v1 as p8_semantics
from openrecomp.host_emitter import HostEmitterConfig

CLOSURE_VERSION = "1.0.0"

ARCHITECTURE = p8_semantics.ARCHITECTURE

#: Evidence-based categories for reachable recognized-unsupported MIPS32
#: forms outside the frozen Phase-8 table. No behaviour is implied.
UNSUPPORTED_CATEGORIES = {
    "lwl": "UNALIGNED_PARTIAL_WORD_LOAD",
    "lwr": "UNALIGNED_PARTIAL_WORD_LOAD",
    "swl": "UNALIGNED_PARTIAL_WORD_STORE",
    "swr": "UNALIGNED_PARTIAL_WORD_STORE",
    "jalr": "INDIRECT_CONTROL_FLOW",
    "break": "TRAP_OR_SYSTEM",
    "syscall": "TRAP_OR_SYSTEM",
    "addi": "OVERFLOW_TRAPPING_ARITHMETIC",
    "add": "OVERFLOW_TRAPPING_ARITHMETIC",
    "sub": "OVERFLOW_TRAPPING_ARITHMETIC",
}

#: COP0/GTE instruction prefixes; any reachable match is an explicit blocker.
COPROCESSOR_PREFIXES = ("mfc0", "mtc0", "cfc0", "ctc0", "cfc2", "ctc2", "cop", "lwc2", "swc2", "gte")


def build_semantics():
    """The frozen Phase-8 rule table (unchanged)."""
    return p8_semantics.build_semantics()


def build_emitter_config(entry_function: str, **kwargs: Any) -> HostEmitterConfig:
    """The frozen Phase-8 emitter configuration (unchanged)."""
    return p8_semantics.build_emitter_config(entry_function, **kwargs)


def runtime_services() -> Any:
    """The bounded PS1 host-service surface.

    The bounded fixture reaches only memory-mapped platform ports, which are
    served by the P9 runtime support's address translation; no explicit
    generic-runtime host service is required. The empty table is explicit.
    """
    from openrecomp import runtime_abi as rt_abi

    return rt_abi.RuntimeServiceTable([])


def coverage(structure: Any) -> dict[str, Any]:
    """Classify every reachable neutral instruction exactly once.

    Returns a deterministic record with the covered op histogram, the exact
    uncovered sites (fail-closed) and the flow mismatches.
    """
    table = build_semantics()
    covered: dict[str, int] = {}
    uncovered: list[dict[str, Any]] = []
    flow_mismatch: list[dict[str, Any]] = []
    for instruction in structure.cfg.instructions:
        op = instruction.op
        if not table.has(ARCHITECTURE, op):
            uncovered.append({"address": f"0x{instruction.address:08x}", "op": op})
            continue
        rule = table.rule(ARCHITECTURE, op)
        if rule.flow is not instruction.flow:
            flow_mismatch.append(
                {
                    "address": f"0x{instruction.address:08x}",
                    "op": op,
                    "expected": rule.flow.value,
                    "observed": instruction.flow.value,
                }
            )
            continue
        covered[op] = covered.get(op, 0) + 1
    return {
        "closure_version": CLOSURE_VERSION,
        "architecture": ARCHITECTURE,
        "instructions": len(structure.cfg.instructions),
        "covered": sum(covered.values()),
        "covered_histogram": dict(sorted(covered.items())),
        "uncovered": sorted(uncovered, key=lambda item: item["address"]),
        "flow_mismatch": sorted(flow_mismatch, key=lambda item: item["address"]),
        "closed": not uncovered and not flow_mismatch,
    }


def classify_reachable_unsupported(histogram: dict[str, int]) -> dict[str, Any]:
    """Classify reachable recognized-unsupported forms by explicit category."""
    categories: dict[str, dict[str, int]] = {}
    unknown: dict[str, int] = {}
    for op, count in sorted(histogram.items()):
        category = UNSUPPORTED_CATEGORIES.get(op)
        if category is None:
            unknown[op] = count
            continue
        bucket = categories.setdefault(category, {})
        bucket[op] = count
    return {
        "categories": {name: dict(sorted(ops.items())) for name, ops in sorted(categories.items())},
        "category_totals": {name: sum(ops.values()) for name, ops in sorted(categories.items())},
        "unknown_ops": dict(sorted(unknown.items())),
        "total": sum(histogram.values()),
    }


def coprocessor_reachable(histogram: dict[str, int]) -> dict[str, int]:
    """Reachable COP0/GTE-prefixed ops (explicit blocker when non-empty)."""
    found: dict[str, int] = {}
    for op, count in sorted(histogram.items()):
        lowered = op.lower()
        if any(lowered.startswith(prefix) for prefix in COPROCESSOR_PREFIXES):
            found[op] = count
    return found
