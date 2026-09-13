#!/usr/bin/env python3
"""P1-17 gate: SM83/GB/GBC regression + differential audit.

Executable audit of the whole SM83 / Game Boy / Game Boy Color chain:

1. runs every P1-10..P1-16 gate script twice;
2. requires each run to succeed AND produce byte-identical output
   (determinism audit — the differential proofs inside those gates compare
   the P1-12 reference against the P1-13 frontend -> IR V1 -> Core API chain
   on identical final CPU state and 64 KiB memory);
3. requires the published regression markers in every run;
4. re-checks the frontend contract gate and the shared architecture harness
   (sm83 fixture) as part of the architecture-boundary audit.

No new semantics: this gate only re-pins the frozen evidence.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

AUDITED = (
    ("test_sm83_state_v1.py", "OPENRECOMP_SM83_STATE_V1=PASS"),
    ("test_sm83_decode_v1.py", "OPENRECOMP_SM83_DECODE_V1=PASS"),
    ("test_sm83_semantics_v1.py", "OPENRECOMP_SM83_SEMANTICS_V1=PASS"),
    ("test_sm83_lowering_v1.py", "OPENRECOMP_SM83_LOWERING_V1=PASS"),
    ("test_gb_rom_v1.py", "OPENRECOMP_GB_ROM_V1=PASS"),
    ("test_gb_headless_v1.py", "OPENRECOMP_GB_HEADLESS_V1=PASS"),
    ("test_gb_mode_v1.py", "OPENRECOMP_GB_MODE_V1=PASS"),
    ("check_frontend_contract_v1.py", "OPENRECOMP_FRONTEND_CONTRACT_V1=PASS"),
)
HARNESS_CASES = (
    ("arch_harness_v1.py", "examples/sm83-v1/arch-harness-v1.json", "OPENRECOMP_ARCH_HARNESS_V1=PASS"),
)

FROZEN_MARKERS = (
    # P1-13 differential (frozen since P1-13)
    ("test_sm83_lowering_v1.py", "a=0x7 f=0xc0 hl=0x1334 sp=0xff0a operations=681"),
    # P1-15 differential (frozen since P1-15)
    ("test_gb_headless_v1.py", "a=0x7 f=0xc0 hl=0x1334 sp=0xff0c halted=1 operations=594 blocks=7"),
    # P1-12 test count (was 62, repaired to 65 in P1-15)
    ("test_sm83_semantics_v1.py", "tests=65"),
    ("test_sm83_lowering_v1.py", "tests=8"),
    ("test_gb_rom_v1.py", "tests=8"),
    ("test_gb_headless_v1.py", "tests=14"),
    ("test_gb_mode_v1.py", "tests=11"),
)


def run(script: str, *args: str) -> str:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        raise AssertionError(f"{script} exited {completed.returncode}: {combined[-400:]}")
    return combined


def main() -> int:
    tests = 0
    captured: dict[str, str] = {}
    for script, marker in AUDITED:
        first = run(script)
        if marker not in first:
            raise AssertionError(f"{script}: marker {marker!r} missing")
        second = run(script)
        if marker not in second:
            raise AssertionError(f"{script} (2nd run): marker {marker!r} missing")
        if hashlib.sha256(first.encode("utf-8")).hexdigest() != hashlib.sha256(second.encode("utf-8")).hexdigest():
            raise AssertionError(f"{script}: output is not deterministic across two runs")
        captured[script] = first
        print(f"PASS audit deterministic x2: {script}")
        tests += 1

    for script, fixture, marker in HARNESS_CASES:
        first = run(script, fixture)
        if marker not in first:
            raise AssertionError(f"{script} {fixture}: marker {marker!r} missing")
        second = run(script, fixture)
        if hashlib.sha256(first.encode("utf-8")).hexdigest() != hashlib.sha256(second.encode("utf-8")).hexdigest():
            raise AssertionError(f"{script} {fixture}: output is not deterministic across two runs")
        print(f"PASS audit deterministic x2: {script} {fixture}")
        tests += 1

    for script, frozen in FROZEN_MARKERS:
        if frozen not in captured.get(script, ""):
            raise AssertionError(f"{script}: frozen regression marker {frozen!r} missing")
        print(f"PASS frozen marker: {frozen}")
        tests += 1

    print(f"OPENRECOMP_SM83_GB_GBC_REGRESSION_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
