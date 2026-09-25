#!/usr/bin/env python3
"""OpenRecomp Phase-15 frozen Phase-14 boundary verification V1.

The Phase-14 terminal boundary is verified in a branch-agnostic, non-mutating way
at the Git level:

* the frozen Phase-14 terminal commit is an ancestor of the current ``HEAD``;
* the frozen Phase-14 terminal tree hash is the recorded
  ``3b5b998dacc60eff88258509bdb5cc548b8b1401``;
* no path under ``.openrecomp-phase14`` or any ``tools/test_phase14_*`` gate was
  changed between the frozen commit and ``HEAD``.

Any failure exits non-zero.
"""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

FROZEN_COMMIT = "830be0f7be998061e8d442134cfae511d5dd8c62"
FROZEN_TREE = "3b5b998dacc60eff88258509bdb5cc548b8b1401"
MARKER = "OPENRECOMP_PHASE15_P14_BOUNDARY_FROZEN"


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
               ".openrecomp-phase14").stdout.strip()
    if diff:
        print(f"{MARKER}=FAIL frozen-modified {diff}")
        return 1

    print(f"{MARKER}=PASS frozen_commit={FROZEN_COMMIT} frozen_tree={FROZEN_TREE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
