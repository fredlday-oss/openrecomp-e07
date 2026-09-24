#!/usr/bin/env python3
"""Deterministic P14-40 initialization replay gate."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p14_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
from p14_contracts_v1 import (  # noqa: E402
    FRAME_MARKER,
    GENERAL_MARKER,
    INITIALIZATION_MARKER,
    INITIALIZATION_REPLAY_MARKER,
    PLAYABILITY_MARKER,
)

import p14_closure_surface_v1 as surface  # noqa: E402
import p14_probe_v1 as probe  # noqa: E402

STAGE = "P14-40"

OBSERVABLE_KEYS = (
    "p14_getc0_calls", "p14_c0_ready", "p14_card_patch_fnv", "p14_card_patch_writes",
    "p14_ram_2ed90", "p14_bu_init_calls", "p14_abs_calls", "p14_puts_calls",
    "p14_mflo_calls", "p14_continuation_calls", "trace_failure_count",
    "trace_block_digest", "p10_service_failures", "denied",
)


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    result = probe.build_and_run(root / ".openrecomp-phase14/build/p14-replay",
                                 "p14-replay",
                                 block_budget=surface.SERVICE_BLOCK_BUDGET)
    first, second, simple = result["first"], result["second"], result["simple"]
    identical = first["stdout"] == second["stdout"]
    gate.check("replay:stdout-identical", identical, first["stdout_sha256"])
    gate.check("replay:stderr-empty",
               first["stderr_bytes"] == 0 and second["stderr_bytes"] == 0,
               f"{first['stderr_bytes']}:{second['stderr_bytes']}")
    observations = {key: simple.get(key) for key in OBSERVABLE_KEYS}
    write_json(evidence / "replay.json", {
        "schema": "openrecomp-phase14-initialization-replay-v1",
        "stage": STAGE,
        "run1_sha256": first["stdout_sha256"],
        "run2_sha256": second["stdout_sha256"],
        "byte_identical": identical,
        "observables": observations,
        "service_sequence": [
            "ChangeClearPAD", "EnterCriticalSection", "InitCARD2",
            "GetC0Table/early-card-patch", "GetB0Table/card-delay-patch",
            "StopCARD2", "ExitCriticalSection", "_bu_init", "abs", "puts",
        ],
        "synthetic_state": {
            "c0_table": "0x1f000800",
            "early_handler": "0x1f001900",
            "card_continuation": observations.get("p14_card_continuation_address"),
        },
    })
    assert_public_safe(gate, "replay", {"observables": observations}, result["image"].payload)
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase14-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P14_40": "PASS", INITIALIZATION_REPLAY_MARKER: "PASS",
                    INITIALIZATION_MARKER: "NOT_PROVEN", FRAME_MARKER: "NOT_PROVEN",
                    PLAYABILITY_MARKER: "NOT_PROVEN", GENERAL_MARKER: "NOT_PROVEN"},
        "next_stage": "P14-50",
    })
    write_json(evidence / "p14_40_tests.json", gate.tests_document("replay"))
    gate.mark("OPENRECOMP_P14_40")
    gate.mark(INITIALIZATION_REPLAY_MARKER)
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase14/evidence/P14-40"))
