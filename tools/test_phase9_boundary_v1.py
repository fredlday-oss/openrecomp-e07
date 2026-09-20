#!/usr/bin/env python3
"""Deterministic P9-00 Phase-8-boundary and Phase-9 control-plane gate.

The gate verifies the frozen Phase-8 terminal boundary identity, the untouched
Phase-1 through Phase-8 files and Phase-8 terminal evidence, the inherited
Phase-6/Phase-7 reconciliation records, the recorded toolchain set, and the
frozen Phase-9 control plane. It adds no PS1 capability.

On success it emits::

    OPENRECOMP_P9_00=PASS
    OPENRECOMP_PHASE9_BOUNDARY_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_boundary_v1.py
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
P9 = ROOT / ".openrecomp-phase9"

BASELINE_PHASE = 8
BASELINE_COMMIT = "61136fc37cf0810e64241addd8f57a91872bc0af"
BASELINE_TREE = "f9262497b82fe0027c3b23432ba7bd8cbccdf433"
BRANCH = "phase8/mips32-end-to-end-native-v1"

TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN"

FROZEN_P8_HASHES = {
    ".openrecomp-phase8/evidence/P8-99/RESULT.md":
        "b07c3ec76c591df7999599e0fa5f1f43f0a1854462b45da96bc8523b2cb04204",
    ".openrecomp-phase8/evidence/P8-99/terminal_verdict.json":
        "ffe1b89d1284435cbb9dd53318025ee052ad0fa58b1f8a304736a381712dc693",
    ".openrecomp-phase8/evidence/P8-99/verdict_record.json":
        "fa9d62c79ab6399981e1acedbedbd07a149daec2c6ea4bde1dc7aee3a7d52738",
    ".openrecomp-phase8/evidence/P8-99/p8_99_tests.json":
        "ff8ed0a79569b95810527b1a395ece4aec3b6eedba9054f704cd0dfd1bbd7f77",
    ".openrecomp-phase8/evidence/P8-99/official_runs.json":
        "459c5f397681e49cfb6830d8f1687e5923120bb061864f8319a0c8eb15dc333d",
    ".openrecomp-phase8/STATE.md":
        "ef56426db4f17deef78635a35ea8074ef6c7a5f17926cd18f4687f6bea63bcd4",
    ".openrecomp-phase8/STAGE_QUEUE.md":
        "5f1dc76669db00f766afcb55fa5d943b5b3498333cfc9cc8b6e63971ceeb1fbf",
    ".openrecomp-phase8/HANDOFF.md":
        "01abbc46c810b9da697932d34e3be7b18acab88b54a630ed777ab96f4da60c70",
    ".openrecomp-phase8/SOURCE_SHA256SUMS.txt":
        "5ac27eb1f23ae412a14e94c62a80f811b7a1670e53b404356b49595d1f9f4221",
    ".openrecomp-phase8/CONTROL_POLICY.md":
        "50bd69203c78f8ff45439f133a0b4dd01f54e1dcf4175a1886a49d0effff20b7",
    ".openrecomp-phase8/SCOPE.md":
        "82bc03b864b85509c7eb23a5e1aea124edc431f94d412064fa4d076c6b349ca1",
    ".openrecomp-phase8/ACCELERATION_POLICY.md":
        "02a10bc6aaa9c2d4accd8d9e5eab30c6e608c09d7090148e180dc4babc36bf95",
    ".openrecomp-phase8/EVIDENCE_SCHEMA.md":
        "4c7b4473972bed35bbdc0e6df54d642886b6697112361f2a8f04a6a659b86acf",
    ".openrecomp-phase8/FIXTURE_POLICY.md":
        "723e5794c836371ece147af53039a4134b788c1ea9ee9fc5d52a91edc330f879",
    ".openrecomp-phase8/evidence/README.md":
        "7167bc52738c562ff84e48c58f4381dc858a972cb7044f1cb850d4c5302ccd27",
}

DOCUMENTED_PRIOR_TRACKED_DIFF = {
    ".openrecomp-phase3/evidence/P3-00/p3_00_tests.json",
    ".openrecomp-phase3/evidence/P3-00/residue_manifest.txt",
}

REQUIRED_CONTROL_FILES = (
    ".openrecomp-phase9/.gitignore",
    ".openrecomp-phase9/ACCELERATION_POLICY.md",
    ".openrecomp-phase9/CONTROL_POLICY.md",
    ".openrecomp-phase9/EVIDENCE_SCHEMA.md",
    ".openrecomp-phase9/FIXTURE_POLICY.md",
    ".openrecomp-phase9/HANDOFF.md",
    ".openrecomp-phase9/SCOPE.md",
    ".openrecomp-phase9/STAGE_QUEUE.md",
    ".openrecomp-phase9/STATE.md",
    ".openrecomp-phase9/evidence/README.md",
    ".openrecomp-phase9/src/p9_source_manifest_v1.py",
    ".openrecomp-phase9/src/p9_stage_runner_v1.py",
)

FROZEN_STAGES = (
    "P9-00", "P9-01", "P9-02", "P9-03", "P9-04", "P9-05", "P9-06", "P9-07",
    "P9-08", "P9-09", "P9-10", "P9-11", "P9-12", "P9-90", "P9-91", "P9-99",
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
        help="re-run the boundary checks without rewriting the committed P9-00 evidence sidecars",
    )
    parser.add_argument(
        "--evidence-dir",
        default=".openrecomp-phase9/evidence/P9-00",
        help="evidence directory relative to the repository root",
    )
    options = parser.parse_args()

    checks: list[dict[str, object]] = []

    def check(label: str, condition: bool, detail: str) -> None:
        checks.append({"check": label, "passed": bool(condition), "detail": detail})

    toolchains: dict[str, dict[str, str]] = {}
    try:
        head = git("rev-parse", "HEAD")
        head_tree = git("rev-parse", "HEAD^{tree}")

        # Phase-8 terminal boundary identity.
        check("baseline:commit-type", git("cat-file", "-t", BASELINE_COMMIT) == "commit", BASELINE_COMMIT)
        check("baseline:commit-tree", git("rev-parse", f"{BASELINE_COMMIT}^{{tree}}") == BASELINE_TREE, BASELINE_TREE)
        check("branch:name", git("branch", "--show-current") == BRANCH, BRANCH)
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

        phase8_tags = git("tag", "-l", "openrecomp-phase8*")
        check("baseline:phase8-tag-absent-reconciled", phase8_tags == "", phase8_tags or "absent")

        verdict = json.loads((P8 / "evidence" / "P8-99" / "terminal_verdict.json").read_text(encoding="utf-8"))
        check("baseline:p8-99-decision", verdict.get("decision") == "PASS", str(verdict.get("decision")))
        check(
            "baseline:p8-99-terminal-marker",
            "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=PASS" in verdict.get("markers_issued", []),
            "terminal PASS",
        )
        required = verdict.get("required_stages", [])
        check(
            "baseline:p8-99-all-stages-pass",
            len(required) == 15 and all(item.get("outcome") == "PASS" for item in required),
            f"{sum(1 for item in required if item.get('outcome') == 'PASS')}/15",
        )

        # Frozen Phase-8 terminal evidence and control-plane hashes.
        for rel, expected in sorted(FROZEN_P8_HASHES.items()):
            observed = sha256_file(ROOT / rel)
            check(f"frozen:p8-terminal:{rel}", observed == expected, observed)

        # Frozen Phase-1..8 tracked/untracked state.
        prior_paths = [f".openrecomp-phase{i}" for i in range(1, 9)]
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
            match = re.search(r"\.openrecomp-phase([1-8])/", line)
            if not match:
                continue
            numeric = int(match.group(1))
            path = line[3:].strip().strip('"')
            if numeric in (2, 3):
                continue
            undocumented.append(path)
        check("frozen:no-new-prior-residue", not undocumented, ",".join(sorted(undocumented)) or "none")

        # Phase-8 source manifest still verifies unchanged.
        manifest = subprocess.run(
            [sys.executable, str(P8 / "src" / "p8_source_manifest_v1.py")],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        check(
            "frozen:p8-source-manifest",
            manifest.returncode == 0 and manifest.stderr == "" and "=PASS entries=" in manifest.stdout,
            manifest.stdout.strip() or manifest.stderr.strip(),
        )

        # Inherited reconciliations.
        phase6_tags = git("tag", "-l", "openrecomp-phase6*")
        check("reconcile:phase6-tag-absent", phase6_tags == "", phase6_tags or "absent")
        check(
            "reconcile:phase7-tag-object",
            git("rev-parse", "openrecomp-phase7-pass") == "b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800",
            "phase7 tag object",
        )
        check(
            "reconcile:phase7-tag-commit",
            git("rev-parse", "openrecomp-phase7-pass^{commit}") == "2917aa6549ab975cffdeb50120514c1723f7e493",
            "phase7 commit",
        )
        check(
            "reconcile:phase7-tag-tree",
            git("rev-parse", "openrecomp-phase7-pass^{tree}") == "59529c130d759ceb1ca9e6c65a510fa373656b01",
            "phase7 tree",
        )
        p8_state = (P8 / "STATE.md").read_text(encoding="utf-8")
        check("reconcile:phase7-v2-outside-baseline", "PHASE7_V2_LINE=OUTSIDE_BASELINE" in p8_state, "OUTSIDE_BASELINE")

        # Toolchains.
        toolchains = capture_toolchains()
        for name, record in sorted(toolchains.items()):
            check(f"toolchain:{name}", record["version"] != "UNAVAILABLE", record["version"])

        # Phase-9 control plane files.
        for rel in REQUIRED_CONTROL_FILES:
            check(f"control:file:{rel}", (ROOT / rel).is_file(), rel)

        # Phase-9 state.
        state = (P9 / "STATE.md").read_text(encoding="utf-8")
        terminal_name = TERMINAL_MARKER.split("=")[0]
        terminal_reserved = f"{terminal_name}=NOT_PROVEN" in state
        terminal_promoted = (
            f"{terminal_name}=PASS" in state
            and "FINAL_VERDICT=PASS" in state
            and "STATUS=COMPLETE" in state
        )
        check(
            f"state:marker:{terminal_name}",
            terminal_reserved or terminal_promoted,
            "reserved or consistently promoted",
        )
        check(f"state:marker:{GENERAL_MARKER.split('=')[0]}", GENERAL_MARKER in state, GENERAL_MARKER)
        check(
            f"state:marker:{PLAYABILITY_MARKER.split('=')[0]}",
            PLAYABILITY_MARKER in state,
            PLAYABILITY_MARKER,
        )
        check("state:baseline-commit", f"BASELINE_COMMIT={BASELINE_COMMIT}" in state, BASELINE_COMMIT)
        check("state:baseline-tree", f"BASELINE_TREE={BASELINE_TREE}" in state, BASELINE_TREE)
        check("state:baseline-tag-absent", "BASELINE_TAG_STATUS=ABSENT_RECONCILED" in state, "ABSENT_RECONCILED")
        check("state:phase8-terminal", "BASELINE_TERMINAL=OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=PASS" in state, "P8 terminal PASS")
        check("state:queue-frozen", "QUEUE_FREEZE=FROZEN" in state, "FROZEN")
        check(
            "state:last-passed",
            bool(re.search(r"^LAST_PASSED_STAGE=P9-[0-9]{2}$", state, re.MULTILINE)),
            "stage shape",
        )
        check(
            "state:current-stage",
            bool(re.search(r"^CURRENT_STAGE=P9-[0-9]{2}$", state, re.MULTILINE)),
            "stage shape",
        )
        check("state:phase7-v2-outside-baseline", "PHASE7_V2_LINE=OUTSIDE_BASELINE" in state, "OUTSIDE_BASELINE")

        # Phase-9 queue.
        queue = (P9 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        found = tuple(re.findall(r"^\| (P9-[0-9]{2}) \|", queue, flags=re.MULTILINE))
        check("queue:exact-stage-order", found == FROZEN_STAGES, ",".join(found))
        check("queue:p9-00-pass", bool(re.search(r"^\| P9-00 \| [^|]+ \| PASS \|", queue, re.MULTILINE)), "P9-00 PASS")
        check("queue:p9-99-queued", bool(re.search(r"^\| P9-99 \| [^|]+ \| (QUEUED|PASS) \|", queue, re.MULTILINE)), "P9-99 queued or complete")
        check("queue:no-extra-status", queue.count("| ACTIVE |") == 0, "no active row before P9-01 gate")

        # Policies.
        policy = re.sub(r"\s+", " ", (P9 / "CONTROL_POLICY.md").read_text(encoding="utf-8"))
        check("policy:no-history-rewrite", "force-push" in policy and "rebase" in policy, "history rewrite forbidden")
        check("policy:two-official-runs", "runs twice" in policy, "two-run determinism")
        check("policy:additive", "additive under" in policy, "prior phases immutable")
        check("policy:serial-frontier", "one serial implementation frontier" in policy, "one frontier")
        check("policy:no-guessing", "never guess" in policy, "fail closed")
        check("policy:commit-only-pass", "Commit only completed `PASS` boundaries" in policy, "commit policy")
        check(
            "policy:private-fixture-non-commit",
            "never committed" in policy and "byte-referenced" in policy,
            "private fixture policy",
        )
        check(
            "policy:no-original-machine-code",
            "Never execute original MIPS32 machine code" in policy,
            "generated host code only",
        )
        check("policy:general-non-claim", "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN" in policy, GENERAL_MARKER)
        check("policy:hercules-non-claim", "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN" in policy, PLAYABILITY_MARKER)

        acceleration = re.sub(r"\s+", " ", (P9 / "ACCELERATION_POLICY.md").read_text(encoding="utf-8"))
        check(
            "acceleration:cache-contract",
            "openrecomp-phase9-analysis-cache-v1" in acceleration,
            "cache key schema",
        )
        check("acceleration:fast-vs-terminal", "terminal gate" in acceleration, "fast/terminal gate policy")
        check(
            "acceleration:incremental-build",
            "content-hash" in acceleration or "content hash" in acceleration,
            "incremental build",
        )

        scope = (P9 / "SCOPE.md").read_text(encoding="utf-8")
        check("scope:terminal-marker", "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF" in scope, "terminal claim")
        check("scope:general-non-claim", GENERAL_MARKER in scope, GENERAL_MARKER)
        check("scope:hercules-non-claim", PLAYABILITY_MARKER in scope, PLAYABILITY_MARKER)
        check("scope:reuse-phase8", "reuses the" in scope or "reusing the" in scope, "Phase-8 pipeline reuse")
        check("scope:no-bios-image", "No BIOS image" in scope, "BIOS boundary")

        fixture_policy = re.sub(r"\s+", " ", (P9 / "FIXTURE_POLICY.md").read_text(encoding="utf-8"))
        check("fixture:public-open-required", "legally redistributable" in fixture_policy, "public fixture licence")
        check("fixture:private-metadata-only", "non-reconstructive" in fixture_policy, "private metadata rule")
        check("fixture:no-proprietary", "proprietary" in fixture_policy, "no proprietary material")
        check("fixture:bios-boundary", "No BIOS image" in fixture_policy, "BIOS boundary")

        evidence_schema = re.sub(r"\s+", " ", (P9 / "EVIDENCE_SCHEMA.md").read_text(encoding="utf-8"))
        check("evidence:two-runs", "two byte-identical stdout" in evidence_schema, "two-run determinism")
        check("evidence:private-non-reconstructive", "non-reconstructive" in evidence_schema, "private metadata rule")

        gitignore = (P9 / ".gitignore").read_text(encoding="utf-8")
        check(
            "evidence:transient-ignored",
            all(entry in gitignore for entry in ("build/", "cache/", "external/")),
            "transient dirs ignored",
        )
        evidence_dirs = sorted(
            item.name for item in (P9 / "evidence").iterdir() if item.is_dir()
        )
        check("evidence:boundary-stage-only", set(evidence_dirs) <= {"P9-00"}, ",".join(evidence_dirs) or "none")

        # Phase-9 source manifest.
        manifest9 = subprocess.run(
            [sys.executable, str(P9 / "src" / "p9_source_manifest_v1.py")],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        check(
            "source:manifest",
            manifest9.returncode == 0 and manifest9.stderr == "" and "=PASS entries=" in manifest9.stdout,
            manifest9.stdout.strip() or manifest9.stderr.strip(),
        )
    except Exception as exc:  # stable fail-closed boundary
        check("gate:exception", False, f"{type(exc).__name__}")

    checks.sort(key=lambda item: str(item["check"]))
    failed = [item for item in checks if not item["passed"]]
    status = "PASS" if not failed else "FAIL"

    evidence = (ROOT / options.evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    record = {
        "stage": "P9-00",
        "stage_name": "Phase-9 boundary and acceleration control plane",
        "status": status,
        "tests": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "baseline": {
            "phase": BASELINE_PHASE,
            "commit": BASELINE_COMMIT,
            "tree": BASELINE_TREE,
            "branch": BRANCH,
            "tag_status": "ABSENT_RECONCILED",
        },
        "markers": {
            "terminal": TERMINAL_MARKER,
            "general": GENERAL_MARKER,
            "playability": PLAYABILITY_MARKER,
        },
        "checks": checks,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    baseline_record = {
        "schema": "openrecomp-phase9-baseline-v1",
        "stage": "P9-00",
        "phase": BASELINE_PHASE,
        "commit": BASELINE_COMMIT,
        "tree": BASELINE_TREE,
        "branch": BRANCH,
        "tag_status": "ABSENT_RECONCILED",
        "audited_head": head,
        "audited_head_tree": head_tree,
        "boundary_mode": "AT_BOUNDARY" if at_boundary else "DESCENDANT",
        "phase6_tag_status": "ABSENT_RECONCILED",
        "phase7_tag_object": "b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800",
        "phase7_commit": "2917aa6549ab975cffdeb50120514c1723f7e493",
        "phase7_tree": "59529c130d759ceb1ca9e6c65a510fa373656b01",
        "phase7_v2_line": "OUTSIDE_BASELINE",
        "frozen_phase8_terminal_evidence": FROZEN_P8_HASHES,
        "markers": {
            "terminal": TERMINAL_MARKER,
            "general": GENERAL_MARKER,
            "playability": PLAYABILITY_MARKER,
        },
    }
    toolchain_record = {
        "schema": "openrecomp-phase9-toolchains-v1",
        "stage": "P9-00",
        "tools": toolchains,
    }
    if not options.verify_only:
        for name, payload in (
            ("p9_00_tests.json", record),
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
    print(f"OPENRECOMP_P9_00={status}")
    print(f"OPENRECOMP_PHASE9_BOUNDARY_V1={status} tests={len(checks)}")
    print(TERMINAL_MARKER)
    print(GENERAL_MARKER)
    print(PLAYABILITY_MARKER)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
