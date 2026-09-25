#!/usr/bin/env python3
"""OpenRecomp Phase-16 TITLE early-execution replay verification V1.

Verifies bounded early execution of the authentic TITLE executable past the
0x800380A0 entry point and 0x8004FF54 main entry up to the 0x80050110
post-TITLE engine bootstrap frontier.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in ("", ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p16_contracts_v1 as contract  # noqa: E402
import p16_transition_v1 as transition16  # noqa: E402

REPLAY_VERSION = "1.0.0"

TITLE_MAIN_PC = contract.TITLE_MAIN_PC          # 0x8004FF54
TITLE_POST_FRONTIER_PC = contract.TITLE_POST_FRONTIER_PC  # 0x80050110


def verify_replay_telemetry(t: dict[str, Any]) -> list[tuple[str, bool, str]]:
    checks = []
    # 1. Inherit all base Exec transition checks
    checks.extend(transition16.verify_transition_telemetry(t))

    # 2. Replay specific assertions
    checks.append((
        "replay:executed",
        t.get("p16_title_replay_executed") == 1,
        f"title replay executed == 1 (got {t.get('p16_title_replay_executed')})",
    ))
    checks.append((
        "replay:frontier-pc",
        t.get("p16_title_frontier_pc") == TITLE_POST_FRONTIER_PC,
        f"replay frontier PC == 0x{TITLE_POST_FRONTIER_PC:08x} (got 0x{t.get('p16_title_frontier_pc', 0):08x})",
    ))
    checks.append((
        "replay:blocks-executed",
        t.get("p16_title_replay_blocks", 0) >= 5,
        f"replay blocks >= 5 (got {t.get('p16_title_replay_blocks')})",
    ))
    checks.append((
        "replay:alloc-calls",
        t.get("p16_title_alloc_calls") == 0,
        f"title alloc calls == 0 (got {t.get('p16_title_alloc_calls')})",
    ))
    checks.append((
        "replay:memset-calls",
        t.get("p16_title_memset_calls") == 0,
        f"title memset calls == 0 (got {t.get('p16_title_memset_calls')})",
    ))
    return checks
