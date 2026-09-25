#!/usr/bin/env python3
"""OpenRecomp Phase-16 TITLE load causality support V1.

Implements controlled ablation testing to establish causal proofs:
1. CD-ROM sector delivery causality: removing CD delivery causes fail-closed
   halt at fn_80012414, proving CD delivery is necessary to reach A0:0x43 Exec.
2. Mode 2 Form 1 sync pattern causality: corrupting sector sync causes fail-closed
   halt, proving sync validation actively guards sector integrity.
3. Authentic payload causality: substituting zero/unauthentic payload delivers
   data, reaches Exec, but fails SHA-256 payload verification and entry instruction check,
   proving authentic disc bytes are causally necessary for valid TITLE execution.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in ("", ".openrecomp-phase15/src", ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p16_contracts_v1 as contract  # noqa: E402

CAUSALITY_VERSION = "1.0.0"

ABLATION_NONE = "NONE"
ABLATION_NULL_DISC = "NULL_DISC"
ABLATION_CORRUPT_SYNC = "CORRUPT_SYNC"
ABLATION_ZERO_PAYLOAD = "ZERO_PAYLOAD"

ALL_ABLATIONS = (
    ABLATION_NONE,
    ABLATION_NULL_DISC,
    ABLATION_CORRUPT_SYNC,
    ABLATION_ZERO_PAYLOAD,
)


def parse_telemetry(stdout_bytes: bytes) -> dict[str, Any]:
    telemetry: dict[str, Any] = {}
    for line in stdout_bytes.decode("utf-8", errors="replace").splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if val.isdigit():
                telemetry[key] = int(val)
            elif val.startswith("0x"):
                try:
                    telemetry[key] = int(val, 16)
                except ValueError:
                    telemetry[key] = val
            else:
                telemetry[key] = val
    return telemetry


def run_ablation(
    executable: pathlib.Path,
    *,
    budget: int,
    block_budget: int,
    ablation: str | None = None,
    timeout: int = 1800,
) -> dict[str, Any]:
    env = os.environ.copy()
    if ablation and ablation != ABLATION_NONE:
        env["OPENRECOMP_CDROM_ABLATION"] = ablation
    else:
        env.pop("OPENRECOMP_CDROM_ABLATION", None)

    command = [str(executable), str(budget), str(block_budget)]
    completed = subprocess.run(
        command,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    stdout = completed.stdout
    stderr = completed.stderr
    telemetry = parse_telemetry(stdout)
    return {
        "ablation": ablation or ABLATION_NONE,
        "returncode": completed.returncode,
        "stderr_bytes": len(stderr),
        "stdout": stdout,
        "telemetry": telemetry,
    }


def verify_baseline(t: dict[str, Any]) -> list[tuple[str, bool, str]]:
    checks = []
    checks.append(("baseline:failed-zero", t.get("failed") == 0, f"failed == 0 (got {t.get('failed')})"))
    checks.append(("baseline:error-empty", t.get("error") == "", f"error empty (got {t.get('error')})"))
    checks.append(("baseline:cd-reads", t.get("p16_cdrom_read_calls") == 2, f"CD reads == 2 (got {t.get('p16_cdrom_read_calls')})"))
    checks.append(("baseline:cd-sectors", t.get("p16_cdrom_sectors_delivered") == 146, f"CD sectors == 146 (got {t.get('p16_cdrom_sectors_delivered')})"))
    checks.append(("baseline:cd-bytes", t.get("p16_cdrom_bytes_delivered") == 299008, f"CD bytes == 299008 (got {t.get('p16_cdrom_bytes_delivered')})"))
    checks.append(("baseline:cd-failures-zero", t.get("p16_cdrom_read_failures") == 0, f"CD failures == 0 (got {t.get('p16_cdrom_read_failures')})"))
    checks.append(("baseline:exec-calls", t.get("p16_exec_calls") == 1, f"Exec calls == 1 (got {t.get('p16_exec_calls')})"))
    checks.append(("baseline:exec-pc0", t.get("p16_exec_pc0") == contract.TITLE_ENTRY_PC, f"Exec pc0 == 0x{contract.TITLE_ENTRY_PC:08x}"))
    checks.append(("baseline:exec-struct", t.get("p16_exec_struct_addr") == contract.EXEC_STRUCT_ADDR, f"Exec struct == 0x{contract.EXEC_STRUCT_ADDR:08x}"))
    checks.append(("baseline:exec-payload-verified", t.get("p16_exec_payload_verified") == 1, f"payload verified == 1 (got {t.get('p16_exec_payload_verified')})"))
    checks.append(("baseline:exec-first-word", t.get("p16_exec_first_word") == contract.TITLE_FIRST_INSTR_WORD, f"first word == 0x{contract.TITLE_FIRST_INSTR_WORD:08x}"))
    return checks


def verify_null_disc_ablation(t: dict[str, Any]) -> list[tuple[str, bool, str]]:
    checks = []
    checks.append(("null-disc:failed-closed", t.get("failed") == 1, f"failed == 1 (got {t.get('failed')})"))
    checks.append(("null-disc:read-failed-msg", t.get("error") == "p16 cdrom read failed", f"error message match (got {t.get('error')})"))
    checks.append(("null-disc:cd-reads", t.get("p16_cdrom_read_calls") == 2, f"CD reads attempted == 2 (got {t.get('p16_cdrom_read_calls')})"))
    checks.append(("null-disc:cd-sectors-zero", t.get("p16_cdrom_sectors_delivered") == 0, f"CD sectors == 0 (got {t.get('p16_cdrom_sectors_delivered')})"))
    checks.append(("null-disc:cd-failures-positive", t.get("p16_cdrom_read_failures", 0) >= 1, f"CD failures >= 1 (got {t.get('p16_cdrom_read_failures')})"))
    checks.append(("null-disc:exec-unreached", t.get("p16_exec_calls") == 0, f"Exec calls == 0 (got {t.get('p16_exec_calls')})"))
    checks.append(("null-disc:payload-unverified", t.get("p16_exec_payload_verified") == 0, f"payload verified == 0 (got {t.get('p16_exec_payload_verified')})"))
    return checks


def verify_corrupt_sync_ablation(t: dict[str, Any]) -> list[tuple[str, bool, str]]:
    checks = []
    checks.append(("corrupt-sync:failed-closed", t.get("failed") == 1, f"failed == 1 (got {t.get('failed')})"))
    checks.append(("corrupt-sync:read-failed-msg", t.get("error") == "p16 cdrom read failed", f"error message match (got {t.get('error')})"))
    checks.append(("corrupt-sync:cd-reads", t.get("p16_cdrom_read_calls") == 2, f"CD reads attempted == 2 (got {t.get('p16_cdrom_read_calls')})"))
    checks.append(("corrupt-sync:cd-sectors-zero", t.get("p16_cdrom_sectors_delivered") == 0, f"CD sectors == 0 (got {t.get('p16_cdrom_sectors_delivered')})"))
    checks.append(("corrupt-sync:cd-failures-positive", t.get("p16_cdrom_read_failures", 0) >= 1, f"CD failures >= 1 (got {t.get('p16_cdrom_read_failures')})"))
    checks.append(("corrupt-sync:exec-unreached", t.get("p16_exec_calls") == 0, f"Exec calls == 0 (got {t.get('p16_exec_calls')})"))
    checks.append(("corrupt-sync:payload-unverified", t.get("p16_exec_payload_verified") == 0, f"payload verified == 0 (got {t.get('p16_exec_payload_verified')})"))
    return checks


def verify_zero_payload_ablation(t: dict[str, Any]) -> list[tuple[str, bool, str]]:
    checks = []
    checks.append(("zero-payload:failed-closed", t.get("failed") == 1, f"failed == 1 (got {t.get('failed')})"))
    checks.append(("zero-payload:error-msg", t.get("error") == "runtime host service ps1.bios.A0.43 failed", f"error message match (got {t.get('error')})"))
    checks.append(("zero-payload:cd-reads", t.get("p16_cdrom_read_calls") == 2, f"CD reads == 2 (got {t.get('p16_cdrom_read_calls')})"))
    checks.append(("zero-payload:cd-sectors", t.get("p16_cdrom_sectors_delivered") == 146, f"CD sectors == 146 (got {t.get('p16_cdrom_sectors_delivered')})"))
    checks.append(("zero-payload:exec-reached", t.get("p16_exec_calls") == 1, f"Exec calls == 1 (got {t.get('p16_exec_calls')})"))
    checks.append(("zero-payload:exec-pc0", t.get("p16_exec_pc0") == contract.TITLE_ENTRY_PC, f"Exec pc0 == 0x{contract.TITLE_ENTRY_PC:08x}"))
    checks.append(("zero-payload:payload-rejected", t.get("p16_exec_payload_verified") == 0, f"payload verified == 0 (got {t.get('p16_exec_payload_verified')})"))
    checks.append(("zero-payload:first-word-zero", t.get("p16_exec_first_word") == 0, f"first word == 0 (got 0x{t.get('p16_exec_first_word', 0):08x})"))
    return checks
