#!/usr/bin/env python3
"""OpenRecomp Phase-14 frozen Phase-13 boundary verification V1.

The Phase-13 terminal boundary gate is branch-pinned (it asserts the Phase-13
branch name) and therefore cannot be run unchanged from the Phase-14 branch.
This module verifies the same frozen-boundary invariant in a branch-agnostic,
non-mutating way at the Git level:

* the frozen Phase-13 terminal commit is an ancestor of the current ``HEAD``;
* the frozen Phase-13 terminal tree hash is the recorded
  ``a74a602c19c18e11a918848e3d1a63d911c243f3``;
* no path under ``.openrecomp-phase13`` or any ``tools/test_phase13_*`` gate was
  changed between the frozen commit and ``HEAD``.

Any failure exits non-zero.
"""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

FROZEN_COMMIT = "7bb4502450d47a0d3f3b207a072c5729277af278"
FROZEN_TREE = "a74a602c19c18e11a918848e3d1a63d911c243f3"
MARKER = "OPENRECOMP_PHASE14_P13_BOUNDARY_FROZEN"


def git(*args: str, text: bool = True):
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=text)


def main() -> int:
    ancestor = git("merge-base", "--is-ancestor", FROZEN_COMMIT, "HEAD").returncode == 0
    if not ancestor:
        print(f"{MARKER}=FAIL ancestry")
        return 1

    tree = git("rev-parse", f"{FROZEN_COMMIT}^{{tree}}").stdout.strip()
    if tree != FROZEN_TREE:
        print(f"{MARKER}=FAIL frozen-tree")
        return 1

    diff = git("diff", "--name-only", f"{FROZEN_COMMIT}..HEAD", "--",
               ".openrecomp-phase13", "tools/test_phase13_boundary_v1.py",
               "tools/test_phase13_queue_v1.py", "tools/test_phase13_frontier_v1.py",
               "tools/test_phase13_whole_regression_v1.py",
               "tools/test_phase13_final_verdict_v1.py").stdout.strip()
    if diff:
        print(f"{MARKER}=FAIL frozen-modified {diff}")
        return 1

    print(f"{MARKER}=PASS frozen_commit={FROZEN_COMMIT} frozen_tree={FROZEN_TREE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
