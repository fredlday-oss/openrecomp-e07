#!/usr/bin/env python3
"""Deterministic P8-00 Phase-7-boundary and Phase-8 control-plane gate.

The gate verifies the frozen Phase-7 baseline identity, the clean Phase-8
branch boundary, the untouched Phase-7 terminal evidence, the inherited
Phase-6 `ABSENT_RECONCILED` reconciliation, the recorded toolchain set, and
the frozen Phase-8 control plane. It adds no MIPS32 capability.

On success it emits::

    OPENRECOMP_P8_00=PASS
    OPENRECOMP_PHASE8_BOUNDARY_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_boundary_v1.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
P8 = ROOT / ".openrecomp-phase8"

BASELINE_TAG = "openrecomp-phase7-pass"
BASELINE_TAG_OBJECT = "b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800"
BASELINE_COMMIT = "2917aa6549ab975cffdeb50120514c1723f7e493"
BASELINE_TREE = "59529c130d759ceb1ca9e6c65a510fa373656b01"
BRANCH = "phase8/mips32-end-to-end-native-v1"

TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN"

FROZEN_P7_HASHES = {
    ".openrecomp-phase7/evidence/P7-99/RESULT.md":
        "88648d7fdecf06e5dd9c089a1a2f032ddcbb4df4c1ff13df30144d87ea398a73",
    ".openrecomp-phase7/evidence/P7-99/terminal_verdict.json":
        "1f26733ed712299e3ad9d278432856e76facd473df92590c22f57e6dacf01955",
    ".openrecomp-phase7/evidence/P7-99/verdict_record.json":
        "51ff2374c067ddb7c1063880d33118b807104bae8861c8d87b1e66e1abbb1d00",
    ".openrecomp-phase7/evidence/P7-99/p7_99_tests.json":
        "b9d77b29fc35d3c32a87f6c4956c0ed7246595b549de271427b238d718aa36d9",
    ".openrecomp-phase7/STATE.md":
        "23c423e9163e3f7fc873b06e293ee96bd85a18b22ca655a24d62d35453f6eb33",
    ".openrecomp-phase7/STAGE_QUEUE.md":
        "6162bda0a5ec2c92b817d31bb2968a2f32f10df3ce80139cd8d68c1946ced377",
    ".openrecomp-phase7/HANDOFF.md":
        "65a56a974f0e651b74b7c0c3399b55c8a45ca1513ddebcb2cde0de3f0447c89a",
    ".openrecomp-phase7/SOURCE_SHA256SUMS.txt":
        "d5da028111b4e8d9cf24e961270393d34aba2a8f6e7d63279739a0afa69fef7a",
}

DOCUMENTED_PRIOR_TRACKED_DIFF = {
    ".openrecomp-phase3/evidence/P3-00/p3_00_tests.json",
    ".openrecomp-phase3/evidence/P3-00/residue_manifest.txt",
}

REQUIRED_CONTROL_FILES = (
    ".openrecomp-phase8/.gitignore",
    ".openrecomp-phase8/ACCELERATION_POLICY.md",
    ".openrecomp-phase8/CONTROL_POLICY.md",
    ".openrecomp-phase8/EVIDENCE_SCHEMA.md",
    ".openrecomp-phase8/FIXTURE_POLICY.md",
    ".openrecomp-phase8/HANDOFF.md",
    ".openrecomp-phase8/SCOPE.md",
    ".openrecomp-phase8/STAGE_QUEUE.md",
    ".openrecomp-phase8/STATE.md",
    ".openrecomp-phase8/evidence/README.md",
    ".openrecomp-phase8/src/p8_source_manifest_v1.py",
)

FROZEN_STAGES = (
    "P8-00", "P8-01", "P8-02", "P8-03", "P8-04", "P8-05", "P8-06", "P8-07",
    "P8-08", "P8-09", "P8-10", "P8-11", "P8-12", "P8-90", "P8-91", "P8-99",
)

TOOLCHAIN_COMMANDS = {
    "python": ("python", "--version"),
    "git": ("git", "--version"),
    "clang": ("clang", "--version"),
    "clang-cl": ("clang-cl", "--version"),
    "lld-link": ("lld-link", "--version"),
    "ninja": ("ninja", "--version"),
    "cmake": ("cmake", "--version"),
    "zig": (".openrecomp-phase3/tools/zig/zig.exe", "version"),
}


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def capture_toolchains() -> dict[str, dict[str, str]]:
    captured: dict[str, dict[str, str]] = {}
    for name, command in TOOLCHAIN_COMMANDS.items():
        executable = command[0]
        if not pathlib.Path(executable).is_absolute():
            candidate = ROOT / executable
            if candidate.is_file():
                executable = str(candidate)
        try:
            result = subprocess.run(
                [executable, *command[1:]],
                check=False,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            captured[name] = {"version": "UNAVAILABLE"}
            continue
        text = (result.stdout or result.stderr).strip()
        first = text.splitlines()[0].strip() if text else ""
        captured[name] = {"version": first or "UNAVAILABLE", "exit_code": str(result.returncode)}
    return captured


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="re-run the boundary checks without rewriting the committed P8-00 evidence sidecars",
    )
    options = parser.parse_args()

    checks: list[dict[str, object]] = []

    def check(label: str, condition: bool, detail: str) -> None:
        checks.append({"check": label, "passed": bool(condition), "detail": detail})

    toolchains: dict[str, dict[str, str]] = {}
    try:
        check("baseline:tag-object", git("rev-parse", BASELINE_TAG) == BASELINE_TAG_OBJECT, BASELINE_TAG_OBJECT)
        check("baseline:tag-type", git("cat-file", "-t", BASELINE_TAG) == "tag", "annotated tag")
        check("baseline:tag-commit", git("rev-parse", f"{BASELINE_TAG}^{{commit}}") == BASELINE_COMMIT, BASELINE_COMMIT)
        check("baseline:tag-tree", git("rev-parse", f"{BASELINE_TAG}^{{tree}}") == BASELINE_TREE, BASELINE_TREE)

        check("branch:name", git("branch", "--show-current") == BRANCH, BRANCH)
        head = git("rev-parse", "HEAD")
        head_tree = git("rev-parse", "HEAD^{tree}")
        ancestor = subprocess.run(
            ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).returncode == 0
        check("branch:descends-from-baseline", ancestor, BASELINE_COMMIT)
        at_boundary = head == BASELINE_COMMIT
        check("branch:head-at-boundary-or-descendant", at_boundary or ancestor, head)
        check(
            "branch:boundary-tree-identical",
            (not at_boundary) or head_tree == BASELINE_TREE,
            head_tree if at_boundary else "descendant",
        )

        phase6_tags = git("tag", "-l", "openrecomp-phase6*")
        check("phase6:tag-absent", phase6_tags == "", phase6_tags or "absent")
        phase7_state = (ROOT / ".openrecomp-phase7" / "STATE.md").read_text(encoding="utf-8")
        check(
            "phase6:absent-reconciled-record",
            "BASELINE_TAG_STATUS=ABSENT_RECONCILED" in phase7_state,
            "ABSENT_RECONCILED",
        )
        check(
            "phase6:no-fabricated-tag",
            not (ROOT / ".openrecomp-phase6").joinpath("TAG_CREATED").exists(),
            "no fabrication marker",
        )

        for rel, expected in sorted(FROZEN_P7_HASHES.items()):
            observed = sha256_file(ROOT / rel)
            check(f"frozen:p7-terminal:{rel}", observed == expected, observed)

        prior_paths = [f".openrecomp-phase{i}" for i in range(1, 8)]
        changed = git("diff", "--name-only", BASELINE_COMMIT, "--", *prior_paths)
        changed_set = set(filter(None, changed.splitlines()))
        check(
            "frozen:no-prior-tracked-change-outside-documented-residue",
            changed_set <= DOCUMENTED_PRIOR_TRACKED_DIFF,
            ",".join(sorted(changed_set)) or "none",
        )
        status_lines = git("status", "--porcelain", "--untracked-files=all").splitlines()
        undocumented: list[str] = []
        for line in status_lines:
            match = re.search(r"\.openrecomp-phase([1-7])/", line)
            if not match:
                continue
            numeric = int(match.group(1))
            path = line[3:].strip().strip('"')
            if numeric in (2, 3):
                continue
            undocumented.append(path)
        check("frozen:no-new-prior-residue", not undocumented, ",".join(undocumented) or "none")

        toolchains = capture_toolchains()
        for name, record in sorted(toolchains.items()):
            check(f"toolchain:{name}", record["version"] != "UNAVAILABLE", record["version"])

        for rel in REQUIRED_CONTROL_FILES:
            check(f"control:file:{rel}", (ROOT / rel).is_file(), rel)

        state = (P8 / "STATE.md").read_text(encoding="utf-8")
        for marker in (TERMINAL_MARKER, GENERAL_MARKER):
            check(f"state:marker:{marker.split('=')[0]}", marker in state, marker)
        check("state:baseline-tag-object", f"BASELINE_TAG_OBJECT={BASELINE_TAG_OBJECT}" in state, BASELINE_TAG_OBJECT)
        check("state:baseline-commit", f"BASELINE_COMMIT={BASELINE_COMMIT}" in state, BASELINE_COMMIT)
        check("state:baseline-tree", f"BASELINE_TREE={BASELINE_TREE}" in state, BASELINE_TREE)
        check("state:queue-frozen", "QUEUE_FREEZE=FROZEN" in state, "FROZEN")
        check(
            "state:last-passed",
            bool(re.search(r"^LAST_PASSED_STAGE=P8-[0-9]{2}$", state, re.MULTILINE)),
            "stage shape",
        )
        check(
            "state:current-stage",
            bool(re.search(r"^CURRENT_STAGE=P8-[0-9]{2}$", state, re.MULTILINE)),
            "stage shape",
        )
        check("state:v2-line-outside-baseline", "PHASE7_V2_LINE=OUTSIDE_BASELINE" in state, "OUTSIDE_BASELINE")

        queue = (P8 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        found = tuple(re.findall(r"^\| (P8-[0-9]{2}) \|", queue, flags=re.MULTILINE))
        check("queue:exact-stage-order", found == FROZEN_STAGES, ",".join(found))
        check("queue:p8-00-pass", bool(re.search(r"^\| P8-00 \| [^|]+ \| PASS \|", queue, re.MULTILINE)), "P8-00 PASS")
        check("queue:p8-99-queued", bool(re.search(r"^\| P8-99 \| [^|]+ \| QUEUED \|", queue, re.MULTILINE)), "P8-99 QUEUED")
        check("queue:no-extra-status", queue.count("| ACTIVE |") == 0, "no active row before P8-01 gate")

        policy = re.sub(r"\s+", " ", (P8 / "CONTROL_POLICY.md").read_text(encoding="utf-8"))
        check("policy:no-history-rewrite", "force-push" in policy and "rebase" in policy, "history rewrite forbidden")
        check("policy:two-official-runs", "runs twice" in policy, "two-run determinism")
        check("policy:additive", "additive under" in policy, "prior phases immutable")
        check("policy:serial-frontier", "one serial implementation frontier" in policy, "one frontier")
        check("policy:no-guessing", "never guess" in policy, "fail closed")
        check("policy:commit-only-pass", "Commit only completed `PASS` boundaries" in policy, "commit policy")

        acceleration = re.sub(r"\s+", " ", (P8 / "ACCELERATION_POLICY.md").read_text(encoding="utf-8"))
        check(
            "acceleration:cache-contract",
            "openrecomp-phase8-analysis-cache-v1" in acceleration,
            "cache key schema",
        )
        check("acceleration:fast-vs-terminal", "terminal gate" in acceleration, "fast/terminal gate policy")
        check("acceleration:incremental-build", "content-hash" in acceleration or "content hash" in acceleration, "incremental build")

        scope = (P8 / "SCOPE.md").read_text(encoding="utf-8")
        check("scope:terminal-marker", "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF" in scope, "terminal claim")
        check("scope:general-non-claim", GENERAL_MARKER in scope, GENERAL_MARKER)
        check("scope:no-linux-kernel", "Linux kernel" in scope, "kernel-emulation boundary")

        fixture_policy = re.sub(r"\s+", " ", (P8 / "FIXTURE_POLICY.md").read_text(encoding="utf-8"))
        check("fixture:licence", "redistribution licence" in fixture_policy, "licence requirement")
        check("fixture:no-proprietary", "proprietary" in fixture_policy, "no proprietary material")

        manifest = subprocess.run(
            [sys.executable, str(P8 / "src" / "p8_source_manifest_v1.py")],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        check(
            "source:manifest",
            manifest.returncode == 0 and manifest.stderr == "" and "=PASS entries=" in manifest.stdout,
            manifest.stdout.strip() or manifest.stderr.strip(),
        )
    except Exception as exc:  # stable fail-closed boundary
        check("gate:exception", False, f"{type(exc).__name__}")

    checks.sort(key=lambda item: str(item["check"]))
    failed = [item for item in checks if not item["passed"]]
    status = "PASS" if not failed else "FAIL"

    evidence = P8 / "evidence" / "P8-00"
    evidence.mkdir(parents=True, exist_ok=True)
    record = {
        "stage": "P8-00",
        "stage_name": "Phase-8 boundary and acceleration control plane",
        "status": status,
        "tests": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "baseline": {
            "tag": BASELINE_TAG,
            "tag_object": BASELINE_TAG_OBJECT,
            "commit": BASELINE_COMMIT,
            "tree": BASELINE_TREE,
            "branch": BRANCH,
        },
        "markers": {"terminal": TERMINAL_MARKER, "general": GENERAL_MARKER},
        "checks": checks,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    baseline_record = {
        "schema": "openrecomp-phase8-baseline-v1",
        "stage": "P8-00",
        "tag": BASELINE_TAG,
        "tag_object": BASELINE_TAG_OBJECT,
        "commit": BASELINE_COMMIT,
        "tree": BASELINE_TREE,
        "branch": BRANCH,
        "audited_head": head,
        "audited_head_tree": head_tree,
        "boundary_mode": "AT_BOUNDARY" if at_boundary else "DESCENDANT",
        "phase6_tag_status": "ABSENT_RECONCILED",
        "phase7_v2_line": "OUTSIDE_BASELINE",
        "frozen_phase7_terminal_evidence": FROZEN_P7_HASHES,
        "markers": {"terminal": TERMINAL_MARKER, "general": GENERAL_MARKER},
    }
    toolchain_record = {
        "schema": "openrecomp-phase8-toolchains-v1",
        "stage": "P8-00",
        "tools": toolchains,
    }
    if not options.verify_only:
        for name, payload in (
            ("p8_00_tests.json", record),
            ("baseline.json", baseline_record),
            ("toolchains.json", toolchain_record),
        ):
            (evidence / name).write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )

    for item in checks:
        prefix = "PASS" if item["passed"] else "FAIL"
        print(f"{prefix}: {item['check']}")
    print(f"OPENRECOMP_P8_00={status}")
    print(f"OPENRECOMP_PHASE8_BOUNDARY_V1={status} tests={len(checks)}")
    print(TERMINAL_MARKER)
    print(GENERAL_MARKER)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
