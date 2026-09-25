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
CANONICAL_MARKER = "OPENRECOMP_PHASE17_CANONICAL_FROZEN_BOUNDARY_GATE"

FROZEN_NAMESPACES = (
    ".openrecomp-phase1",
    ".openrecomp-phase2",
    ".openrecomp-phase3",
    ".openrecomp-phase4",
    ".openrecomp-phase5",
    ".openrecomp-phase6",
    ".openrecomp-phase7",
    ".openrecomp-phase8",
    ".openrecomp-phase9",
    ".openrecomp-phase10",
    ".openrecomp-phase11",
    ".openrecomp-phase12",
    ".openrecomp-phase13",
    ".openrecomp-phase14",
    ".openrecomp-phase15",
    ".openrecomp-phase16",
)


def git(*args: str, text: bool = True):
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=text)


def verify_frozen_boundary() -> tuple[bool, dict[str, object]]:
    report: dict[str, object] = {}

    # 1. Phase 16 ancestry check
    ancestor = git("merge-base", "--is-ancestor", FROZEN_PHASE16_COMMIT, "HEAD").returncode == 0
    report["phase16_ancestor"] = ancestor
    if not ancestor:
        return False, report

    # 2. Phase 16 tree check
    tree16 = git("rev-parse", f"{FROZEN_PHASE16_COMMIT}^{{tree}}").stdout.strip()
    report["phase16_tree_ok"] = tree16 == FROZEN_PHASE16_TREE
    if tree16 != FROZEN_PHASE16_TREE:
        return False, report

    # 3. Phase 16 path modification check
    diff16 = git("diff", "--name-only", f"{FROZEN_PHASE16_COMMIT}..HEAD", "--", ".openrecomp-phase16").stdout.strip()
    report["phase16_modified"] = diff16.splitlines() if diff16 else []
    if diff16:
        return False, report

    # 4. Phase 15 tree and path checks
    tree15 = git("rev-parse", f"{FROZEN_PHASE15_COMMIT}^{{tree}}").stdout.strip()
    report["phase15_tree_ok"] = tree15 == FROZEN_PHASE15_TREE
    if tree15 != FROZEN_PHASE15_TREE:
        return False, report
    diff15 = git("diff", "--name-only", f"{FROZEN_PHASE15_COMMIT}..HEAD", "--", ".openrecomp-phase15").stdout.strip()
    report["phase15_modified"] = diff15.splitlines() if diff15 else []
    if diff15:
        return False, report

    # 5. Phase 14 tree check
    tree14 = git("rev-parse", f"{FROZEN_PHASE14_COMMIT}^{{tree}}").stdout.strip()
    report["phase14_tree_ok"] = tree14 == FROZEN_PHASE14_TREE
    if tree14 != FROZEN_PHASE14_TREE:
        return False, report

    # 6. Staged and unstaged changes in frozen namespaces
    staged = git("diff", "--cached", "--name-only", "--", *FROZEN_NAMESPACES).stdout.strip().splitlines()
    unstaged = git("diff", "--name-only", "--", *FROZEN_NAMESPACES).stdout.strip().splitlines()
    report["staged_prior_phase"] = staged
    report["unstaged_prior_phase"] = unstaged
    if staged or unstaged:
        return False, report

    # 7. Untracked additions in frozen namespaces
    porcelain = git("status", "--porcelain", "--", *FROZEN_NAMESPACES).stdout.strip().splitlines()
    untracked = [line[3:] for line in porcelain if line.startswith("?? ")]
    report["untracked_prior_phase"] = untracked
    if untracked:
        return False, report

    return True, report


def main() -> int:
    ok, report = verify_frozen_boundary()
    if not ok:
        print(f"{MARKER}=FAIL")
        print(f"{CANONICAL_MARKER}=FAIL {json.dumps(report, sort_keys=True)}")
        return 1
    print(f"{MARKER}=PASS frozen_phase16={FROZEN_PHASE16_COMMIT} frozen_phase15={FROZEN_PHASE15_COMMIT} frozen_phase14={FROZEN_PHASE14_COMMIT}")
    print(f"{CANONICAL_MARKER}=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
