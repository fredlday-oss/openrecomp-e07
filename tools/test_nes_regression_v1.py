#!/usr/bin/env python3
"""P1-35 gate: 6502/NES regression + differential audit.

Executable audit of the whole 6502 / NES chain:

1. runs every P1-30..P1-34 gate script twice;
2. requires each run to succeed AND produce byte-identical output
   (determinism audit — the differential proofs inside those gates compare
   the P1-31 reference against the frontend -> IR V1 -> Core API chain on
   identical final CPU state and the full 64 KiB address space);
3. requires the published regression markers in every run;
4. re-checks the frontend-contract gate as part of the architecture-boundary
   audit.

No new semantics: this gate only re-pins the frozen evidence.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

AUDITED = (
    ("test_nes6502_state_v1.py", "OPENRECOMP_NES6502_STATE_V1=PASS"),
    ("test_nes6502_decode_v1.py", "OPENRECOMP_NES6502_DECODE_V1=PASS"),
    ("test_nes6502_semantics_v1.py", "OPENRECOMP_NES6502_SEMANTICS_V1=PASS"),
    ("test_nes6502_lowering_v1.py", "OPENRECOMP_NES6502_LOWERING_V1=PASS"),
    ("test_nes_rom_v1.py", "OPENRECOMP_NES_ROM_V1=PASS"),
    ("test_nes_platform_v1.py", "OPENRECOMP_NES_PLATFORM_V1=PASS"),
    ("test_nes_headless_v1.py", "OPENRECOMP_NES_HEADLESS_V1=PASS"),
    ("check_frontend_contract_v1.py", "OPENRECOMP_FRONTEND_CONTRACT_V1=PASS"),
)

FROZEN_MARKERS = (
    # P1-30 test counts
    ("test_nes6502_state_v1.py", "tests=10"),
    # P1-31 test counts
    ("test_nes6502_semantics_v1.py", "tests=102"),
    ("test_nes6502_lowering_v1.py", "tests=12"),
    # P1-32/P1-33 test counts
    ("test_nes_rom_v1.py", "tests=12"),
    ("test_nes_platform_v1.py", "tests=10"),
    # P1-34 headless differential + count (frozen since P1-34)
    ("test_nes_headless_v1.py", "a=0xc6 x=0x0 sp=0xfd p=0xa4 pc=0x8032"),
    ("test_nes_headless_v1.py", "ppuctrl=0x7e ppumask=0x1e vram=1122 oam_dma=1 controller=0x41 apu=0x1f"),
    ("test_nes_headless_v1.py", "tests=7"),
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

    for script, frozen in FROZEN_MARKERS:
        if frozen not in captured.get(script, ""):
            raise AssertionError(f"{script}: frozen regression marker {frozen!r} missing")
        print(f"PASS frozen marker: {frozen}")
        tests += 1

    print(f"OPENRECOMP_NES_REGRESSION_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
