#!/usr/bin/env python3
"""OpenRecomp Phase-16 Post-TITLE frontier measurement & closure V1.

Defines the contract and observables for measuring and closing the post-TITLE
frontier reached at 0x80050110 in Disney's Hercules Action Game (USA).
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in ("", ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p16_contracts_v1 as contract  # noqa: E402
import p16_replay_v1 as replay16  # noqa: E402

FRONTIER_VERSION = "1.0.0"

TITLE_POST_FRONTIER_PC = contract.TITLE_POST_FRONTIER_PC  # 0x80050110


def verify_frontier_telemetry(t: dict[str, Any]) -> list[tuple[str, bool, str]]:
    checks = []
    # 1. Inherit all replay telemetry checks
    checks.extend(replay16.verify_replay_telemetry(t))

    # 2. Frontier closure assertions
    checks.append((
        "frontier:exact-pc",
        t.get("p16_title_frontier_pc") == TITLE_POST_FRONTIER_PC,
        f"frontier PC == 0x{TITLE_POST_FRONTIER_PC:08x} (got 0x{t.get('p16_title_frontier_pc', 0):08x})",
    ))
    checks.append((
        "frontier:block-count",
        t.get("p16_title_replay_blocks", 0) >= 5,
        f"frontier blocks >= 5 (got {t.get('p16_title_replay_blocks')})",
    ))
    checks.append((
        "frontier:replay-success",
        t.get("p16_title_replay_executed") == 1,
        "title replay successfully executed to frontier",
    ))
    checks.append((
        "frontier:no-overflow",
        t.get("nonram_overflow") == 0,
        f"nonram overflow == 0 (got {t.get('nonram_overflow')})",
    ))
    return checks
