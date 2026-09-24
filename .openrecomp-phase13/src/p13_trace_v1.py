#!/usr/bin/env python3
"""OpenRecomp Phase-13 execution-trace support V1.

Thin additive layer over the frozen Phase-12 trace support: it runs a generated
program with explicit deterministic budgets and exposes every ``key=value`` line
(including the additive ``p13_*`` observables) as a simple mapping.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase12/src",):
    sys.path.insert(0, str(ROOT / extra))

import p12_trace_v1 as p12_trace  # noqa: E402

TRACE_VERSION = "3.0.0"


def simple_map(stdout: bytes) -> dict[str, str]:
    return p12_trace.simple_map(stdout)


def run_program(executable: pathlib.Path, *, budget: int | None = None,
                block_budget: int | None = None, timeout: int = 1800) -> dict:
    return p12_trace.run_program(
        executable, budget=budget, block_budget=block_budget, timeout=timeout
    )
