#!/usr/bin/env python3
"""OpenRecomp Phase-16 frozen Phase-15 and Phase-14 boundary verification V1."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

FROZEN_PHASE15_COMMIT = "5cec005d45e8361e5ea132731661b13a72a5ed13"
FROZEN_PHASE15_TREE = "f7d5aebe1d0db96a0850dc03123d9ad04040460d"
FROZEN_PHASE14_COMMIT = "830be0f7be998061e8d442134cfae511d5dd8c62"
FROZEN_PHASE14_TREE = "3b5b998dacc60eff88258509bdb5cc548b8b1401"

MARKER = "OPENRECOMP_PHASE16_P15_BOUNDARY_FROZEN"


def git(*args: str, text: bool = True):
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=text)


def verify_frozen_boundary() -> bool:
    # 1. Phase 15 ancestry check
    ancestor = git("merge-base", "--is-ancestor", FROZEN_PHASE15_COMMIT, "HEAD").returncode == 0
    if not ancestor:
        return False

    # 2. Phase 15 tree check
    tree15 = git("rev-parse", f"{FROZEN_PHASE15_COMMIT}^{{tree}}").stdout.strip()
    if tree15 != FROZEN_PHASE15_TREE:
        return False

    # 3. Phase 15 path modification check
    diff15 = git("diff", "--name-only", f"{FROZEN_PHASE15_COMMIT}..HEAD", "--", ".openrecomp-phase15").stdout.strip()
    if diff15:
        return False

    # 4. Phase 14 tree check
    tree14 = git("rev-parse", f"{FROZEN_PHASE14_COMMIT}^{{tree}}").stdout.strip()
    if tree14 != FROZEN_PHASE14_TREE:
        return False

    return True


def main() -> int:
    if not verify_frozen_boundary():
        print(f"{MARKER}=FAIL")
        return 1
    print(f"{MARKER}=PASS frozen_phase15={FROZEN_PHASE15_COMMIT} frozen_phase14={FROZEN_PHASE14_COMMIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
