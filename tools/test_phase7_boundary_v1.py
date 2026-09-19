#!/usr/bin/env python3
"""OpenRecomp Phase-7 boundary gate (P7-00).

Verifies the exact frozen Phase-6 terminal boundary (commit/tree and the
recorded absence of a Phase-6 terminal tag), independently re-runs the
Phase-6 final verdict gate in a reconstructed pre-verdict context, establishes
the Phase-7 control-plane/ROM-safety/public-private-fixture separation and
freezes the Phase-7 queue rows before any P7-01 implementation work.

On success it emits::

    OPENRECOMP_P7_00=PASS
    OPENRECOMP_PHASE7_BOUNDARY_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_boundary_v1.py --evidence-dir .openrecomp-phase7/evidence/P7-00
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL6 = ROOT / ".openrecomp-phase6"
CONTROL7 = ROOT / ".openrecomp-phase7"

STAGE = "P7-00"
STAGE_MARKER = "OPENRECOMP_P7_00"
FEATURE_MARKER = "OPENRECOMP_PHASE7_BOUNDARY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

PHASE6_BRANCH = "phase6/nes-compat-v1"
PHASE6_COMMIT = "1643817d43196c43155805249137e4b4e4a21eb1"
PHASE6_TREE = "cda3f535be43dc6f3d4b457d11d356ae39ea34af"
PHASE6_TAG = "openrecomp-phase6-pass"
PHASE6_TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
PHASE6_COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"
PHASE7_BRANCH = "phase7/nes-translation-frontier-v1"

PHASE5_TAG = "openrecomp-phase5-pass"
PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"
PHASE4_TAG_OBJECT = "e7eaab18fee267b3d7962db13835c9e14dd77fc2"
PHASE4_COMMIT = "b3c71fb690f00b4811e8ec30c28f7725141295d0"
PHASE4_TREE = "f2ca3080915aa68f403526b89dfc17454687aed6"
PHASE3_TAG_OBJECT = "ac31524504b1b5cc63aabcfd5132a3eb4275e8e9"
PHASE3_COMMIT = "e16e4b29b90f379615f1af97e47747cd1d531796"
PHASE3_TREE = "a940f0d84a32adaf191f7ff2bebfb24cc855cde0"
PHASE2_COMMIT = "01b1d7cba8c931fca95d041389cfb1902b7c89fe"
PHASE1_COMMIT = "46c2f971e1a42cf49bd936bad94697b81bf31002"

P6_99_GATE = "tools/test_phase6_final_verdict_v1.py"
P6_99_GATE_SHA256 = "55d96214883a334807c9e9cb17ed0a53e92c3d6f2c09cf45725e490f0f5b67f4"
P6_99_RECORD_SHA256 = "e7e462f15ca64a2d8db130ec664ac309d5ebfef1c128fd392111d19e4be30ea4"
P6_99_STDOUT_BYTES = 3750
P6_99_STDOUT_RAW_SHA256 = "d7e96e11d94202fff91380dc4020e5523aa7d87dacfb3f05ee35cbf469d3a365"
P6_99_STDOUT_LF_SHA256 = "4fafd3842eb1df3d7f44f166cec6bd064d28e71121fffdb882e7ca1969c2978a"
P6_99_TESTS = 108
P6_90_STDOUT_RAW_SHA256 = "e487dbc0221d813d1d1138065be422bf8440d96f64d0dee5cd94d80f123ff5c5"

ROM_PATH = pathlib.Path(r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes")
ROM_SIZE = 262160
ROM_SHA256 = "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
ROM_MD5 = "d60c64b46f9a6b5ee6a78bfe2fee7d48"

CONTROL_FILES = (
    "STATE.md",
    "HANDOFF.md",
    "STAGE_QUEUE.md",
    "CONTROL_POLICY.md",
    "EVIDENCE_SCHEMA.md",
    "SCOPE.md",
    "FIXTURE_POLICY.md",
)

FROZEN_QUEUE = (
    ("P7-01", "TMNT frontier re-derivation"),
    ("P7-02", "Undocumented opcode 0x7C classification"),
    ("P7-03", "Public undocumented-opcode proof fixture"),
    ("P7-04", "Bank-aware cartridge reachability model"),
    ("P7-05", "Bank-aware ProgramModel / CFG integration"),
    ("P7-06", "Indirect jump evidence model"),
    ("P7-07", "Public indirect-control-flow proof fixture"),
    ("P7-08", "Translation frontier integration"),
    ("P7-09", "Native execution of public Phase-7 fixture"),
    ("P7-10", "Independent reference equivalence"),
    ("P7-11", "Private TMNT frontier run"),
    ("P7-12", "Evidence-driven translation closure"),
    ("P7-13", "Second private TMNT run"),
    ("P7-14", "Reusable bank-aware ROM-to-native workflow"),
    ("P7-90", "Whole regression"),
    ("P7-91", "Evidence index and compatibility matrix"),
    ("P7-99", "Final Phase-7 verdict"),
)
QUEUE_STATUSES = ("QUEUED", "ACTIVE", "COMPLETE")
LEDGER_STATUSES = ("QUEUED", "ACTIVE", "PASS", "FAIL", "BLOCKED")

ROM_EXTENSIONS = (".nes", ".fds", ".unf", ".unif", ".prg", ".chr")

ALLOWED_UNTRACKED_EXACT = (
    "tools/test_build_package_reproducibility_v1.py",
)
ALLOWED_UNTRACKED_PREFIXES = (
    ".openrecomp-phase2/",
    ".openrecomp-phase3/",
    ".openrecomp-phase5/",
    ".openrecomp-phase6/",
    ".openrecomp-phase7/",
    "artifacts/",
)
ALLOWED_UNTRACKED_RE = re.compile(r"^tools/test_phase(?:5|6|7)_[A-Za-z0-9_]+\.py$")
ALLOWED_MODIFIED_PREFIXES = (".openrecomp-phase5/", ".openrecomp-phase6/",
                             ".openrecomp-phase7/")
ALLOWED_MODIFIED_EXACT = (
    ".openrecomp-phase3/evidence/P3-00/p3_00_tests.json",
    ".openrecomp-phase3/evidence/P3-00/residue_manifest.txt",
    ".gitignore",
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def md5_file(path: pathlib.Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def git(arguments: list[str], cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *arguments], cwd=str(cwd or ROOT), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600)


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def parse_manifest(path: pathlib.Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in read_text(path).strip().splitlines():
        if not line.strip():
            continue
        match = re.match(r"^([0-9a-f]{64}) \*(.+)$", line)
        if match is None:
            raise AssertionError(f"malformed manifest line: {line[:80]}")
        entries.append((match.group(1), match.group(2)))
    return entries


def parse_queue_rows(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^\|\s*(P7-\d\d)\s*\|\s*([^|]+?)\s*\|\s*([A-Z_]+)\s*\|", line)
        if match:
            rows.append((match.group(1), match.group(2), match.group(3)))
    return rows


def parse_ledger_rows(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^\|\s*(P7-\d\d)\s*\|[^|]*\|\s*([A-Z_]+)\s*\|", line)
        if match:
            rows.append((match.group(1), match.group(2)))
    return rows


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise AssertionError(f"recon:{label}: anchor count {text.count(old)} != 1")
    return text.replace(old, new)


def reconstruct_p6_99_context() -> dict[str, Any]:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="p7_p6_99_recon_"))
    created = False
    try:
        added = git(["worktree", "add", "--detach", str(tmp), PHASE6_COMMIT])
        if added.returncode != 0:
            raise AssertionError(f"recon:worktree-add: {added.stderr.strip()[:200]}")
        created = True
        state_path = tmp / ".openrecomp-phase6" / "STATE.md"
        state_text = state_path.read_text(encoding="utf-8")
        state_text = replace_once(state_text, "LAST_PASSED_STAGE=P6-99",
                                  "LAST_PASSED_STAGE=P6-91", "state-last-passed")
        state_text = replace_once(state_text, "MMC1_PLATFORM_STATUS=PROVEN",
                                  "MMC1_PLATFORM_STATUS=NOT_PROVEN", "state-mmc1")
        state_text = replace_once(state_text, "FINAL_VERDICT=PASS",
                                  "FINAL_VERDICT=NOT_PROVEN", "state-verdict")
        state_text = replace_once(
            state_text, "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS",
            "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN", "state-terminal")
        state_path.write_text(state_text, encoding="utf-8", newline="\n")

        queue_path = tmp / ".openrecomp-phase6" / "STAGE_QUEUE.md"
        queue_text = queue_path.read_text(encoding="utf-8")
        queue_text = replace_once(
            queue_text, "| P6-99 | Final Phase-6 verdict | COMPLETE |",
            "| P6-99 | Final Phase-6 verdict | QUEUED |", "queue-p6-99")
        if queue_text.count("OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS") < 1:
            raise AssertionError("recon:queue-terminal: promoted marker missing")
        queue_text = queue_text.replace(
            "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS",
            "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN")
        queue_path.write_text(queue_text, encoding="utf-8", newline="\n")

        evidence_dir = tmp / ".openrecomp-phase6" / "evidence" / "P6-99-recon"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        tests_path = evidence_dir / "p6_99_tests.json"
        runs = []
        for _index in (1, 2):
            completed = subprocess.run(
                [sys.executable, str(tmp / "tools" / "test_phase6_final_verdict_v1.py"),
                 "--evidence-dir", str(evidence_dir)],
                cwd=str(tmp), capture_output=True)
            runs.append({
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            })
        return {
            "raw_bytes": len(runs[0]["stdout"]),
            "stdout_sha256_raw": sha256_bytes(runs[0]["stdout"]),
            "stdout_sha256_lf": sha256_bytes(lf_normalize(runs[0]["stdout"])),
            "tests_sha256": sha256_bytes(tests_path.read_bytes())
            if tests_path.is_file() else "",
            "identical_raw": runs[0]["stdout"] == runs[1]["stdout"],
            "identical_stderr": runs[0]["stderr"] == runs[1]["stderr"],
            "returncode_zero_both": runs[0]["returncode"] == 0 and runs[1]["returncode"] == 0,
            "stderr_empty_both": not runs[0]["stderr"] and not runs[1]["stderr"],
            "stdout": runs[0]["stdout"],
        }
    finally:
        if created:
            removed = git(["worktree", "remove", "--force", str(tmp)])
            if removed.returncode != 0:
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
        git(["worktree", "prune"])


def scan_worktree_for_copies(size: int, digest: str) -> list[str]:
    matches: list[str] = []
    skip_dirs = {".git", "__pycache__", ".venv", "venv"}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        try:
            if path.stat().st_size != size:
                continue
            if sha256_file(path) == digest:
                matches.append(path.relative_to(ROOT).as_posix())
        except OSError:
            continue
    return matches


def list_rom_extension_files() -> list[str]:
    found: list[str] = []
    skip_dirs = {".git", "__pycache__"}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix.lower() in ROM_EXTENSIONS:
            found.append(path.relative_to(ROOT).as_posix())
    return found


def worktree_hygiene_problems() -> list[str]:
    status = git(["status", "--porcelain=v1"])
    problems: list[str] = []
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        code = line[:2]
        entry = line[3:].strip()
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        allowed = (entry in ALLOWED_UNTRACKED_EXACT
                   or entry in ALLOWED_MODIFIED_EXACT
                   or entry.startswith(ALLOWED_UNTRACKED_PREFIXES)
                   or entry.startswith(ALLOWED_MODIFIED_PREFIXES)
                   or ALLOWED_UNTRACKED_RE.match(entry) is not None)
        if not allowed:
            kind = "untracked" if code == "??" else "modified"
            problems.append(f"{kind}:{entry}")
    return problems


def audit_control_plane() -> None:
    for name in CONTROL_FILES:
        check(f"control-plane:exists:{name}", (CONTROL7 / name).is_file())
    check("control-plane:evidence-dir", (CONTROL7 / "evidence").is_dir())
    check("control-plane:src-dir", (CONTROL7 / "src").is_dir())

    state = read_text(CONTROL7 / "STATE.md")
    queue = read_text(CONTROL7 / "STAGE_QUEUE.md")
    check("control-plane:phase", re.search(r"^PHASE=7\s*$", state, re.MULTILINE) is not None)
    check("control-plane:current-stage",
          re.search(r"^CURRENT_STAGE=P7-\d\d\s*$", state, re.MULTILINE) is not None)
    check("control-plane:last-passed-stage",
          re.search(r"^LAST_PASSED_STAGE=(?:NONE|P7-\d\d)\s*$", state, re.MULTILINE) is not None)
    check("control-plane:status",
          re.search(r"^STATUS=(?:ACTIVE|COMPLETE)\s*$", state, re.MULTILINE) is not None)
    check("control-plane:baseline", "BASELINE=openrecomp-phase6-pass" in state)
    check("control-plane:baseline-tag-status",
          "BASELINE_TAG_STATUS=ABSENT_RECONCILED" in state)
    check("control-plane:baseline-commit", PHASE6_COMMIT in state)
    check("control-plane:baseline-tree", PHASE6_TREE in state)
    check("control-plane:baseline-terminal",
          f"BASELINE_TERMINAL={PHASE6_TERMINAL_MARKER}=PASS" in state)
    check("control-plane:baseline-general",
          f"BASELINE_GENERAL={PHASE6_COMPAT_MARKER}=NOT_PROVEN" in state)
    check("control-plane:frontier-status-reserved",
          "TRANSLATION_FRONTIER_STATUS=NOT_PROVEN" in state)

    rows = parse_queue_rows(queue)
    by_id = {row[0]: row for row in rows}
    check("control-plane:queue-ids-frozen",
          [row[0] for row in rows] == ["P7-00"] + [item[0] for item in FROZEN_QUEUE])
    check("control-plane:queue-names-frozen",
          all(by_id.get(stage, ("", "", ""))[1] == name for stage, name in FROZEN_QUEUE))
    check("control-plane:queue-statuses-valid",
          all(row[2] in QUEUE_STATUSES for row in rows))
    check("control-plane:queue-at-most-one-active",
          sum(1 for row in rows if row[2] == "ACTIVE") <= 1)
    check("control-plane:queue-freeze-section",
          "## Queue freeze" in queue and "P7-01" in queue and "P7-99" in queue)
    check("control-plane:queue-freeze-record",
          "renumbered" in queue and "redefined by the freeze" in queue)
    complete = {row[0] for row in rows if row[2] == "COMPLETE"}
    ledger = parse_ledger_rows(state)
    check("control-plane:ledger-ids-frozen",
          [row[0] for row in ledger] == ["P7-00"] + [item[0] for item in FROZEN_QUEUE])
    check("control-plane:ledger-statuses-valid",
          all(row[1] in LEDGER_STATUSES for row in ledger))
    ledger_pass = {row[0] for row in ledger if row[1] == "PASS"}
    check("control-plane:complete-set-matches-ledger", complete == ledger_pass)
    check("control-plane:terminal-marker-reserved",
          f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
          and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
    check("control-plane:compat-marker-reserved",
          f"{COMPAT_MARKER}=NOT_PROVEN" in queue
          and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
    check("control-plane:playability-marker-reserved",
          f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
          and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)
    check("control-plane:freeze-record", "QUEUE_FREEZE=FROZEN" in state)
    check("control-plane:queue-freeze-stages",
          "QUEUE_FREEZE_STAGES=P7-01..P7-99" in state)

    scope = read_text(CONTROL7 / "SCOPE.md")
    check("control-plane:scope-terminal", TERMINAL_MARKER in scope)
    check("control-plane:scope-nonclaims",
          "all undocumented 6502 opcodes" in scope
          and "all indirect-control-flow recovery" in scope
          and "arbitrary bank-switched binaries" in scope
          and "cycle accuracy" in scope
          and "TMNT playability is NOT required for Phase-7 PASS" in scope)
    policy = read_text(CONTROL7 / "CONTROL_POLICY.md")
    check("control-plane:rom-policy",
          "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE" in policy and "Never commit" in policy)
    check("control-plane:tag-reconciliation",
          "ABSENT_RECONCILED" in policy and "No tag" in policy
          and "fabricating" in policy)
    fixture_policy = read_text(CONTROL7 / "FIXTURE_POLICY.md")
    check("control-plane:fixture-policy-private",
          "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE" in fixture_policy
          and "tmnt.nes" in fixture_policy and ROM_SHA256 in fixture_policy)
    check("control-plane:fixture-policy-public",
          "Apache-2.0" in fixture_policy and "Public / audited fixtures" in fixture_policy)
    check("control-plane:separated-fixtures",
          "must not become the public Phase-7 proof fixture" in fixture_policy
          and "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE` never appears in the package"
          in fixture_policy)


def audit_frozen_chain() -> None:
    check("chain:phase5-tag-annotated",
          git(["cat-file", "-t", PHASE5_TAG]).stdout.strip() == "tag")
    check("chain:phase5-tag-object",
          git(["rev-parse", PHASE5_TAG]).stdout.strip() == PHASE5_TAG_OBJECT)
    check("chain:phase5-commit",
          git(["rev-parse", f"{PHASE5_TAG}^{{commit}}"]).stdout.strip() == PHASE5_COMMIT)
    check("chain:phase5-tree",
          git(["rev-parse", f"{PHASE5_TAG}^{{tree}}"]).stdout.strip() == PHASE5_TREE)
    check("chain:phase4",
          git(["rev-parse", "openrecomp-phase4-pass"]).stdout.strip() == PHASE4_TAG_OBJECT
          and git(["rev-parse", "openrecomp-phase4-pass^{commit}"]).stdout.strip()
          == PHASE4_COMMIT
          and git(["rev-parse", "openrecomp-phase4-pass^{tree}"]).stdout.strip()
          == PHASE4_TREE)
    check("chain:phase3",
          git(["rev-parse", "openrecomp-phase3-pass"]).stdout.strip() == PHASE3_TAG_OBJECT
          and git(["rev-parse", "openrecomp-phase3-pass^{commit}"]).stdout.strip()
          == PHASE3_COMMIT
          and git(["rev-parse", "openrecomp-phase3-pass^{tree}"]).stdout.strip()
          == PHASE3_TREE)
    check("chain:phase2-phase1",
          git(["rev-parse", "openrecomp-phase2-pass^{commit}"]).stdout.strip()
          == PHASE2_COMMIT
          and git(["rev-parse", "openrecomp-phase1-pass^{commit}"]).stdout.strip()
          == PHASE1_COMMIT)
    check("chain:phase6-branch-commit",
          git(["rev-parse", f"refs/heads/{PHASE6_BRANCH}"]).stdout.strip()
          == PHASE6_COMMIT)
    check("chain:phase6-commit",
          git(["rev-parse", f"{PHASE6_COMMIT}^{{commit}}"]).stdout.strip()
          == PHASE6_COMMIT)
    check("chain:phase6-tree",
          git(["rev-parse", f"{PHASE6_COMMIT}^{{tree}}"]).stdout.strip() == PHASE6_TREE)
    check("chain:phase6-descends-phase5",
          git(["merge-base", "--is-ancestor", PHASE5_COMMIT, PHASE6_COMMIT]).returncode == 0)
    check("chain:head-descends-phase6",
          git(["merge-base", "--is-ancestor", PHASE6_COMMIT, "HEAD"]).returncode == 0)
    tag_probe = git(["rev-parse", "--verify", "--quiet", f"refs/tags/{PHASE6_TAG}"])
    check("chain:phase6-tag-absent-reconciled", tag_probe.returncode != 0)
    check("chain:phase6-tag-absence-recorded",
          "Terminal tag: not created" in read_text(CONTROL6 / "HANDOFF.md"))
    branch = git(["symbolic-ref", "--quiet", "--short", "HEAD"]).stdout.strip()
    check("chain:on-phase7-branch", branch in ("", PHASE7_BRANCH)
          or branch.startswith("phase7/"))


def audit_phase6_verdict() -> None:
    check("verdict6:gate-hash", sha256_file(ROOT / P6_99_GATE) == P6_99_GATE_SHA256)
    record_path = CONTROL6 / "evidence" / "P6-99" / "p6_99_tests.json"
    check("verdict6:record-present", record_path.is_file())
    check("verdict6:record-hash", sha256_file(record_path) == P6_99_RECORD_SHA256)
    record = json.loads(read_text(record_path))
    check("verdict6:record-status", record["status"] == "PASS"
          and record["failure"] is None and record["tests"] == P6_99_TESTS)
    check("verdict6:record-terminal",
          record["markers"]["terminal"] == f"{PHASE6_TERMINAL_MARKER}=PASS")
    check("verdict6:record-general",
          record["markers"]["compatibility"] == f"{PHASE6_COMPAT_MARKER}=NOT_PROVEN")
    state6 = read_text(CONTROL6 / "STATE.md")
    queue6 = read_text(CONTROL6 / "STAGE_QUEUE.md")
    check("verdict6:terminal-marker-promoted",
          f"{PHASE6_TERMINAL_MARKER}=PASS" in state6
          and f"{PHASE6_TERMINAL_MARKER}=PASS" in queue6)
    check("verdict6:general-marker-never-promoted",
          f"{PHASE6_COMPAT_MARKER}=NOT_PROVEN" in state6
          and f"{PHASE6_COMPAT_MARKER}=NOT_PROVEN" in queue6)
    check("verdict6:private-not-promoted",
          "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS" in state6
          and "TMNT remains not playable" in read_text(CONTROL6 / "HANDOFF.md"))

    p6_90 = json.loads(read_text(CONTROL6 / "evidence" / "P6-90"
                                 / "whole_regression.json"))
    check("verdict6:whole-regression",
          len(p6_90["phase6_stage_gates"]) == 14
          and all(gate["stdout_matches_official"] is True
                  for gate in p6_90["phase6_stage_gates"])
          and p6_90["phase5_whole_regression"]["stdout_sha256_raw"]
          == P6_90_STDOUT_RAW_SHA256)
    p6_91_claims = json.loads(read_text(CONTROL6 / "evidence" / "P6-91"
                                        / "claim_record.json"))
    check("verdict6:claim-ledger-separated",
          p6_91_claims["terminal_marker"] == f"{PHASE6_TERMINAL_MARKER}=NOT_PROVEN"
          and p6_91_claims["ledger"]["phase6_public_mmc1"]["status"] == "PROVEN"
          and p6_91_claims["ledger"]["general_nes"]["status"] == "UNPROVEN"
          and p6_91_claims["ledger"]["private_tmnt_compatibility"]["status"]
          == "UNPROVEN")


def audit_reconstruction() -> None:
    recon = reconstruct_p6_99_context()
    FINDINGS["p6_99_reconstruction"] = {key: value for key, value in recon.items()
                                        if key != "stdout"}
    check("recon:returncode-zero", recon["returncode_zero_both"])
    check("recon:stderr-empty", recon["stderr_empty_both"])
    check("recon:stdout-bytes", recon["raw_bytes"] == P6_99_STDOUT_BYTES)
    check("recon:stdout-raw-hash", recon["stdout_sha256_raw"] == P6_99_STDOUT_RAW_SHA256)
    check("recon:stdout-lf-hash", recon["stdout_sha256_lf"] == P6_99_STDOUT_LF_SHA256)
    check("recon:record-hash", recon["tests_sha256"] == P6_99_RECORD_SHA256)
    check("recon:identical", recon["identical_raw"] is True
          and recon["identical_stderr"] is True)
    stdout_text = recon["stdout"].decode("utf-8", errors="replace")
    check("recon:markers",
          "OPENRECOMP_P6_99=PASS" in stdout_text
          and f"OPENRECOMP_PHASE6_FINAL_VERDICT_V1=PASS tests={P6_99_TESTS}"
          in stdout_text
          and f"{PHASE6_TERMINAL_MARKER}=PASS" in stdout_text)


def audit_rom_safety() -> None:
    check("rom:exists", ROM_PATH.is_file())
    check("rom:outside-worktree", not str(ROM_PATH).lower().startswith(str(ROOT).lower()))
    check("rom:size", ROM_PATH.stat().st_size == ROM_SIZE)
    check("rom:sha256", sha256_file(ROM_PATH) == ROM_SHA256)
    check("rom:md5", md5_file(ROM_PATH) == ROM_MD5)
    tracked_roms = git(["ls-files", "--",
                        *[f"*{extension}" for extension in ROM_EXTENSIONS]])
    check("rom:no-tracked-images", tracked_roms.stdout.strip() == "")
    present = list_rom_extension_files()
    FINDINGS["rom_extension_files"] = present
    check("rom:no-worktree-images", present == [])
    copies = scan_worktree_for_copies(ROM_SIZE, ROM_SHA256)
    FINDINGS["private_rom_copies"] = copies
    check("rom:no-private-copy", copies == [])
    ignore_text = read_text(ROOT / ".gitignore")
    for extension in (".nes", ".fds", ".unf", ".unif"):
        check(f"rom:gitignore:{extension}", f"*{extension}" in ignore_text)
    for probe in ("probe.nes", "probe.fds", "probe.unf", "probe.unif", "Roms/probe.rom",
                  "roms/probe.rom"):
        ignored = subprocess.run(["git", "check-ignore", "-q", "--no-index", "--", probe],
                                 cwd=str(ROOT), capture_output=True)
        check(f"rom:ignored:{probe}", ignored.returncode == 0)


def audit_source_integrity() -> None:
    manifest = CONTROL7 / "SOURCE_SHA256SUMS.txt"
    check("source:manifest-exists", manifest.is_file())
    entries = parse_manifest(manifest)
    bad = [rel for digest, rel in entries
           if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
    check("source:manifest-verified", bool(entries) and not bad)
    FINDINGS["phase7_manifest_entries"] = len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description="P7-00 Phase-7 boundary gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-00")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}

    print("=== P7-00 Phase-7 Boundary Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("control_plane")
        audit_control_plane()

        banner("source_integrity")
        audit_source_integrity()

        banner("frozen_chain")
        audit_frozen_chain()

        banner("phase6_verdict")
        audit_phase6_verdict()

        banner("p6_99_reconstruction")
        audit_reconstruction()

        banner("rom_safety")
        audit_rom_safety()

        banner("worktree_hygiene")
        problems = worktree_hygiene_problems()
        FINDINGS["worktree_problems"] = problems
        check("hygiene:no-unexpected-paths", problems == [])

        digest_lines = [
            f"{sha256_file(CONTROL7 / name)}  .openrecomp-phase7/{name}"
            for name in CONTROL_FILES
        ]
        digest_text = "\n".join(digest_lines) + "\n"
        (EVIDENCE_DIR / "control_plane_manifest.txt").write_text(
            digest_text, encoding="utf-8", newline="\n")
        FINDINGS["control_plane_digest"] = sha256_bytes(digest_text.encode("utf-8"))
        FINDINGS["phase6_baseline_commit"] = PHASE6_COMMIT
        FINDINGS["phase6_baseline_tree"] = PHASE6_TREE
        FINDINGS["phase6_tag_present"] = False
        FINDINGS["private_rom_sha256"] = ROM_SHA256
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    status = "FAIL" if failure else "PASS"

    result = {
        "stage": STAGE,
        "stage_name": FEATURE_MARKER,
        "status": status,
        "tests": passed,
        "passed": passed,
        "failed": failed,
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={passed}",
            "terminal": f"{TERMINAL_MARKER}=NOT_PROVEN",
            "compatibility": f"{COMPAT_MARKER}=NOT_PROVEN",
            "playability": f"{PLAYABILITY_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    (EVIDENCE_DIR / "p7_00_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
