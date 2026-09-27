#!/usr/bin/env python3
"""OpenRecomp Phase-18 frozen Phase-17 authority verification V1.

Independently re-verifies (from live Git, never from chat):
  * the Phase-17 terminal tag resolves to the certified commit;
  * the certified commit's tree matches;
  * HEAD descends from the certified commit (Phase-18 branch fork point);
  * the Phase-17 terminal marker is PASS in the committed verdict;
  * no Phase-1..17 namespace has been modified relative to the certified commit.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

AUTHORITY_COMMIT = "d7cc5d09eebde398ca6ff3f3dad8dd5841913b69"
AUTHORITY_TREE = "ad3aa822e5a02905ebc25477f7b6c69d0bffa055"
AUTHORITY_TAG = "openrecomp-phase17-pass"
PHASE17_TERMINAL_MARKER = "OPENRECOMP_PHASE17_TERMINAL_V1"
PHASE17_VERDICT_PATH = ".openrecomp-phase17/evidence/P17-99/verdict.json"

MARKER = "OPENRECOMP_PHASE18_P17_AUTHORITY_FROZEN"
CANONICAL_MARKER = "OPENRECOMP_PHASE18_CANONICAL_FROZEN_AUTHORITY_GATE"

FROZEN_NAMESPACES = tuple(f".openrecomp-phase{n}" for n in range(1, 18))


def git(*args: str, text: bool = True):
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=text)


def verify() -> tuple[bool, dict[str, object]]:
    report: dict[str, object] = {}

    # 1. Tag resolves to the certified commit.
    tag_commit = git("rev-parse", f"{AUTHORITY_TAG}^{{commit}}").stdout
    tag_commit = tag_commit.strip() if isinstance(tag_commit, str) else tag_commit.decode().strip()
    report["tag"] = AUTHORITY_TAG
    report["tag_commit"] = tag_commit
    if tag_commit != AUTHORITY_COMMIT:
        report["tag_ok"] = False
        return False, report
    report["tag_ok"] = True

    # 2. Certified tree.
    tree = git("rev-parse", f"{AUTHORITY_COMMIT}^{{tree}}").stdout.strip()
    report["authority_tree"] = tree
    report["tree_ok"] = tree == AUTHORITY_TREE
    if tree != AUTHORITY_TREE:
        return False, report

    # 3. HEAD descends from the authority commit (forks do not rewrite history).
    ancestor = git("merge-base", "--is-ancestor", AUTHORITY_COMMIT, "HEAD").returncode == 0
    report["head_descends_from_authority"] = ancestor
    if not ancestor:
        return False, report

    # 4. Committed Phase-17 terminal marker is PASS.
    verdict_path = ROOT / PHASE17_VERDICT_PATH
    marker_ok = False
    if verdict_path.is_file():
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        marker_ok = (verdict.get("terminal_marker") == PHASE17_TERMINAL_MARKER
                     and verdict.get("claim_markers", {}).get("FIRST_FRAME_READY") == "NO")
    report["phase17_terminal_marker_ok"] = marker_ok
    if not marker_ok:
        return False, report

    # 5. No Phase-1..17 namespace modified relative to the authority commit.
    diff = git("diff", "--name-only", f"{AUTHORITY_COMMIT}..HEAD", "--",
               *FROZEN_NAMESPACES).stdout.strip()
    report["prior_phase_modified"] = diff.splitlines() if diff else []
    if diff:
        return False, report

    # 6. No staged/unstaged/untracked changes in prior-phase namespaces.
    porcelain = git("status", "--porcelain", "--", *FROZEN_NAMESPACES).stdout.strip()
    report["prior_phase_dirty"] = porcelain.splitlines() if porcelain else []
    if porcelain:
        return False, report

    return True, report


def main() -> int:
    ok, report = verify()
    if not ok:
        print(f"{MARKER}=FAIL")
        print(f"{CANONICAL_MARKER}=FAIL {json.dumps(report, sort_keys=True)}")
        return 1
    print(f"{MARKER}=PASS authority={AUTHORITY_COMMIT} tag={AUTHORITY_TAG}")
    print(f"{CANONICAL_MARKER}=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
