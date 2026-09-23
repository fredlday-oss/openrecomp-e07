#!/usr/bin/env python3
"""OpenRecomp Phase-12 execution-trace support V1.

Thin additive layer over the frozen Phase-11 trace support: it runs a generated
program with explicit deterministic budgets, parses the frozen observables
exactly as Phase 11 does, and additionally exposes every `key=value` line
(including the additive `p12_*` observables) as a simple mapping.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase11/src",):
    sys.path.insert(0, str(ROOT / extra))

import p11_trace_v1 as p11_trace  # noqa: E402

TRACE_VERSION = "2.0.0"


def simple_map(stdout: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in stdout.decode("utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def run_program(executable: pathlib.Path, *, budget: int | None = None,
                block_budget: int | None = None, timeout: int = 1800) -> dict:
    result = p11_trace.run_trace_program(
        executable, budget=budget, block_budget=block_budget, timeout=timeout
    )
    result["simple"] = simple_map(result["stdout"])
    return result
