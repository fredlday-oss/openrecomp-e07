#!/usr/bin/env python3
"""OpenRecomp Phase-14 execution-trace support V1.

Thin additive layer over the frozen Phase-13 trace support: it runs a generated
program with explicit deterministic budgets and exposes every ``key=value`` line
(including the additive ``p14_*`` observables) as a simple mapping.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase12/src", ".openrecomp-phase13/src"):
    sys.path.insert(0, str(ROOT / extra))

import p13_trace_v1 as p13_trace  # noqa: E402

TRACE_VERSION = "4.0.0"


def simple_map(stdout: bytes) -> dict[str, str]:
    return p13_trace.simple_map(stdout)


def run_program(executable: pathlib.Path, *, budget: int | None = None,
                block_budget: int | None = None, timeout: int = 1800) -> dict:
    return p13_trace.run_program(
        executable, budget=budget, block_budget=block_budget, timeout=timeout
    )
