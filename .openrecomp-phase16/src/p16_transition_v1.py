#!/usr/bin/env python3
"""OpenRecomp Phase-16 TITLE Exec transition contract and verification V1.

Defines the contract and observables for transferring guest execution from
the initial loader's A0:0x43 Exec dispatch into the authentic TITLE overlay
entry point at 0x800380A0.

Transition sequence:
1. Dispatch A0:0x43 Exec with authentic TITLE payload verified in RAM.
2. Initialize guest context: $sp = 0x801FFFF0, $fp = 0x801FFFF0, $gp = 0x00000000.
3. Transfer control to fn_fn_800380a0.
4. Execute BSS clear loop for 0x8007D8CC.
5. Compute and configure TITLE global pointer: $gp = 0x8007A3E0.
6. Call fn_fn_80011af0 in main executable to register heap configuration:
   - heap_start = 0x8007D8D0 (stored at 0x80035D00)
   - heap_size  = 0x7FF7A738 (stored at 0x80035D04)
7. Restore return address and reach TITLE main function frontier at 0x8004FF54.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in ("", ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p16_contracts_v1 as contract  # noqa: E402

TRANSITION_VERSION = "1.0.0"

TITLE_ENTRY_PC = contract.TITLE_ENTRY_PC  # 0x800380A0
TITLE_SP_ADDR = contract.TITLE_SP_ADDR    # 0x801FFFF0
TITLE_INITIAL_GP = 0x8007A3E0
TITLE_HEAP_START = 0x8007D8D0
TITLE_HEAP_SIZE = 0x7FF7A738
TITLE_HEAP_CONFIG_ADDR1 = 0x80035D00
TITLE_HEAP_CONFIG_ADDR2 = 0x80035D04
TITLE_MAIN_TARGET = 0x8004FF54


def verify_transition_telemetry(t: dict[str, Any]) -> list[tuple[str, bool, str]]:
    checks = []
    # 1. Base Exec dispatch assertions
    checks.append(("exec:calls", t.get("p16_exec_calls") == 1, f"Exec calls == 1 (got {t.get('p16_exec_calls')})"))
    checks.append(("exec:struct-addr", t.get("p16_exec_struct_addr") == contract.EXEC_STRUCT_ADDR, f"Exec struct addr == 0x{contract.EXEC_STRUCT_ADDR:08x}"))
    checks.append(("exec:pc0", t.get("p16_exec_pc0") == TITLE_ENTRY_PC, f"Exec pc0 == 0x{TITLE_ENTRY_PC:08x}"))
    checks.append(("exec:sp-addr", t.get("p16_exec_sp_addr") == TITLE_SP_ADDR, f"Exec sp == 0x{TITLE_SP_ADDR:08x}"))
    checks.append(("exec:payload-verified", t.get("p16_exec_payload_verified") == 1, "authentic TITLE overlay payload SHA-256 verified"))
    checks.append(("exec:first-word", t.get("p16_exec_first_word") == contract.TITLE_FIRST_INSTR_WORD, f"first word == 0x{contract.TITLE_FIRST_INSTR_WORD:08x}"))

    # 2. Execution Transition Assertions
    checks.append(("transition:dispatched", t.get("p16_transition_dispatched") == 1, f"transition dispatched == 1 (got {t.get('p16_transition_dispatched')})"))
    checks.append(("transition:target", t.get("p16_transition_target") == TITLE_ENTRY_PC, f"transition target == 0x{TITLE_ENTRY_PC:08x} (got 0x{t.get('p16_transition_target', 0):08x})"))
    checks.append(("transition:sp", t.get("p16_transition_sp") == TITLE_SP_ADDR, f"transition sp == 0x{TITLE_SP_ADDR:08x} (got 0x{t.get('p16_transition_sp', 0):08x})"))
    checks.append(("transition:entry-called", t.get("p16_title_entry_called") == 1, f"title entry called == 1 (got {t.get('p16_title_entry_called')})"))
    checks.append(("transition:initial-gp", t.get("p16_title_initial_gp") == TITLE_INITIAL_GP, f"title gp == 0x{TITLE_INITIAL_GP:08x} (got 0x{t.get('p16_title_initial_gp', 0):08x})"))
    checks.append(("transition:heap-start", t.get("p16_title_heap_start") == TITLE_HEAP_START, f"heap start == 0x{TITLE_HEAP_START:08x} (got 0x{t.get('p16_title_heap_start', 0):08x})"))
    checks.append(("transition:heap-size", t.get("p16_title_heap_size") == TITLE_HEAP_SIZE, f"heap size == 0x{TITLE_HEAP_SIZE:08x} (got 0x{t.get('p16_title_heap_size', 0):08x})"))
    checks.append(("transition:cfg-param1", t.get("p16_title_cfg_param1") == TITLE_HEAP_START, f"cfg param1 (heap start in RAM) == 0x{TITLE_HEAP_START:08x} (got 0x{t.get('p16_title_cfg_param1', 0):08x})"))
    checks.append(("transition:cfg-param2", t.get("p16_title_cfg_param2") == TITLE_HEAP_SIZE, f"cfg param2 (heap size in RAM) == 0x{TITLE_HEAP_SIZE:08x} (got 0x{t.get('p16_title_cfg_param2', 0):08x})"))
    checks.append(("transition:main-reached", t.get("p16_title_main_reached") == 1, f"title main reached == 1 (got {t.get('p16_title_main_reached')})"))
    checks.append(("transition:main-target", t.get("p16_title_main_target") == TITLE_MAIN_TARGET, f"title main target == 0x{TITLE_MAIN_TARGET:08x} (got 0x{t.get('p16_title_main_target', 0):08x})"))

    # 3. Execution status assertions
    checks.append(("transition:failed-zero", t.get("failed") == 0, f"failed == 0 (got {t.get('failed')})"))
    checks.append(("transition:error-empty", t.get("error") == "", f"error empty (got {t.get('error')})"))
    return checks
