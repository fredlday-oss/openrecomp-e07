#!/usr/bin/env python3
"""OpenRecomp Phase-17 frozen Phase-16 and prior boundary verification V1."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

FROZEN_PHASE16_COMMIT = "a0c26e882ca65cfc84cbec78f7e787509a4992a3"
FROZEN_PHASE16_TREE = "7f70357c14636d56c4c8bd000f5092f7052a1425"
FROZEN_PHASE15_COMMIT = "5cec005d45e8361e5ea132731661b13a72a5ed13"
FROZEN_PHASE15_TREE = "f7d5aebe1d0db96a0850dc03123d9ad04040460d"
FROZEN_PHASE14_COMMIT = "830be0f7be998061e8d442134cfae511d5dd8c62"
FROZEN_PHASE14_TREE = "3b5b998dacc60eff88258509bdb5cc548b8b1401"

MARKER = "OPENRECOMP_PHASE17_P16_BOUNDARY_FROZEN"


def git(*args: str, text: bool = True):
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=text)


def verify_frozen_boundary() -> bool:
    # 1. Phase 16 ancestry check
    ancestor = git("merge-base", "--is-ancestor", FROZEN_PHASE16_COMMIT, "HEAD").returncode == 0
    if not ancestor:
        return False

    # 2. Phase 16 tree check
    tree16 = git("rev-parse", f"{FROZEN_PHASE16_COMMIT}^{{tree}}").stdout.strip()
    if tree16 != FROZEN_PHASE16_TREE:
        return False

    # 3. Phase 16 path modification check
    diff16 = git("diff", "--name-only", f"{FROZEN_PHASE16_COMMIT}..HEAD", "--", ".openrecomp-phase16").stdout.strip()
    if diff16:
        return False

    # 4. Phase 15 tree and path checks
    tree15 = git("rev-parse", f"{FROZEN_PHASE15_COMMIT}^{{tree}}").stdout.strip()
    if tree15 != FROZEN_PHASE15_TREE:
        return False
    diff15 = git("diff", "--name-only", f"{FROZEN_PHASE15_COMMIT}..HEAD", "--", ".openrecomp-phase15").stdout.strip()
    if diff15:
        return False

    # 5. Phase 14 tree check
    tree14 = git("rev-parse", f"{FROZEN_PHASE14_COMMIT}^{{tree}}").stdout.strip()
    if tree14 != FROZEN_PHASE14_TREE:
        return False

    return True


def main() -> int:
    if not verify_frozen_boundary():
        print(f"{MARKER}=FAIL")
        return 1
    print(f"{MARKER}=PASS frozen_phase16={FROZEN_PHASE16_COMMIT} frozen_phase15={FROZEN_PHASE15_COMMIT} frozen_phase14={FROZEN_PHASE14_COMMIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
