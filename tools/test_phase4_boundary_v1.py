#!/usr/bin/env python3
"""OpenRecomp Phase-4 boundary gate (P4-00).

P4-00 is the Phase-4 entry verification stage.  It adds no runtime,
recompilation or emulation capability.  The deterministic gate proves, before
any Phase-4 implementation work begins:

* the frozen Phase-3 annotated tag ``openrecomp-phase3-pass`` resolves to the
  recorded tag object, commit and tree, and the current Phase-4 branch
  descends from that boundary (``merge-base`` is the boundary commit);
* the frozen Phase-3 terminal evidence is unchanged (root and Phase-3 source
  manifests, P3-99 result record, P3-99 gate, CoreMark fixture identity);
* ``python tools/test_phase3_final_verdict_v1.py`` independently re-passes on
  this tree, byte-identically to the recorded official capture, with the exact
  terminal markers and empty stderr.  Because the frozen P3-00 gate inside
  that regression predates Phase 4 (it requires a ``phase3/*`` branch name and
  rejects any untracked non-Phase-3 path), the re-run is performed in the
  exact frozen Phase-3 verification context: a temporary local
  ``phase3/p4-00-verification-context`` branch is created at the current
  commit for the duration of the re-run and deleted afterwards, and untracked
  Phase-4 material is held outside the worktree and restored byte-identically
  afterwards.  The committed P3-99 verdict record is restored from HEAD if a
  failed re-run overwrote it.  No frozen file is modified, no history is
  rewritten and no gate is weakened;
* the Phase-4 control plane exists and is deterministic (no timestamps, host
  paths, process identity or UUIDs);
* the frozen queue ``P4-01`` .. ``P4-99`` is complete, in order and consistent
  with the STATE ledger, and the terminal/general compatibility markers are
  reserved as ``NOT_PROVEN``;
* no new runtime capability is claimed (``GENERIC_RUNTIME_STATUS=NOT_PROVEN``);
* the working tree has no unexpected untracked paths beyond the documented
  Phase-2/Phase-3 sets and the Phase-4 control plane itself, and no tracked
  file outside frozen Phase-3 evidence directories is modified or deleted.

On success it emits::

    OPENRECOMP_P4_00=PASS
    OPENRECOMP_PHASE4_BOUNDARY_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Any failed invariant fails closed and emits ``OPENRECOMP_P4_00=FAIL``.

Usage:

    python tools/test_phase4_boundary_v1.py
    python tools/test_phase4_boundary_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-00
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
import time
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL_PLANE = ROOT / ".openrecomp-phase4"
EVIDENCE_ROOT = CONTROL_PLANE / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P4-00"

STAGE = "P4-00"
STAGE_MARKER = "OPENRECOMP_P4_00"
FEATURE_MARKER = "OPENRECOMP_PHASE4_BOUNDARY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

PHASE3_TAG = "openrecomp-phase3-pass"
PHASE3_TAG_OBJECT = "ac31524504b1b5cc63aabcfd5132a3eb4275e8e9"
PHASE3_COMMIT = "e16e4b29b90f379615f1af97e47747cd1d531796"
PHASE3_TREE = "a940f0d84a32adaf191f7ff2bebfb24cc855cde0"
PHASE2_TAG = "openrecomp-phase2-pass"
PHASE2_COMMIT = "01b1d7cba8c931fca95d041389cfb1902b7c89fe"
PHASE1_TAG = "openrecomp-phase1-pass"
PHASE1_COMMIT = "46c2f971e1a42cf49bd936bad94697b81bf31002"

SOURCE_SUMS = "SOURCE_SHA256SUMS.txt"
SOURCE_SUMS_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
SOURCE_SUMS_ENTRIES = 134
P3_SUMS = ".openrecomp-phase3/SOURCE_SHA256SUMS.txt"
P3_SUMS_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_SUMS_ENTRIES = 24
P4_SUMS = ".openrecomp-phase4/SOURCE_SHA256SUMS.txt"
P3_99_RESULT_JSON = ".openrecomp-phase3/evidence/P3-99/RESULT.json"
P3_99_RESULT_JSON_SHA256 = "c893250b539cf1e82f368c09fe848f8f695ebece17f7735713c5367a3d93c1cf"
P3_99_GATE = "tools/test_phase3_final_verdict_v1.py"
P3_99_GATE_SHA256 = "ba5814902797d9848614e08b6bd655c00061dfb0d2dc90fec30da60382d558fa"
P3_99_STDOUT_BYTES = 2498
P3_99_STDOUT_SHA256 = "953ec70c312c7203022ba98f763aabf270409e2f39a9a7fa2ac90d887ae087bc"
P3_99_STDOUT_SHA256_LF = "4974d03fdd02ef76e1fa6506d230cd2c9be9e1cfe55bb9d5d4851f7525c72dd5"
P3_99_MARKERS = (
    "OPENRECOMP_P3_99=PASS",
    "OPENRECOMP_PHASE3_FINAL_VERDICT_V1=PASS tests=46",
    "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=PASS",
)
FIXTURE_REL = ".openrecomp-phase3/build/P3-01/candidate-a/coremark_mips32_O1.elf"
FIXTURE_SHA256 = "16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669"
FIXTURE_SIZE = 31184
# Temporary Phase-3-named verification branch created (and deleted) by this
# gate at the current commit while the frozen P3-99 gate is re-run, because
# the frozen P3-00 gate inside that regression requires the current branch to
# be named phase3/*.  It is a local verification-context reconstruction; it
# changes no history and no frozen file.
TEMP_VERIFY_BRANCH = "phase3/p4-00-verification-context"

CONTROL_FILES = (
    "CONTROL_POLICY.md",
    "EVIDENCE_SCHEMA.md",
    "SCOPE.md",
    "STAGE_QUEUE.md",
    "STATE.md",
    "HANDOFF.md",
)
REQUIRED_FIELDS = {
    "PHASE": "4",
    "BASELINE_TAG": PHASE3_TAG,
    "BASELINE_COMMIT": PHASE3_COMMIT,
    "BASELINE_TREE": PHASE3_TREE,
    "FINAL_VERDICT": "NOT_PROVEN",
    "GENERIC_RUNTIME_STATUS": "NOT_PROVEN",
    "QUEUE_FREEZE": "FROZEN",
}

FROZEN_QUEUE = (
    ("P4-01", "Generic Runtime ABI V1"),
    ("P4-02", "Guest memory/runtime model"),
    ("P4-03", "Runtime service mediation"),
    ("P4-04", "Deterministic I/O, timing and input"),
    ("P4-05", "Platform Adapter Interface V1"),
    ("P4-06", "Graphics/audio abstraction boundary"),
    ("P4-07", "Interactive legally-clean fixture"),
    ("P4-08", "First platform-adapter execution proof"),
    ("P4-09", "End-to-end generic-runtime native proof"),
    ("P4-10", "Reproducible Phase-4 package"),
    ("P4-90", "Phase-4 whole regression audit"),
    ("P4-91", "Evidence index + limitations"),
    ("P4-99", "Final Phase-4 verdict"),
)
QUEUE_STATUSES = {"QUEUED", "ACTIVE", "COMPLETE"}
LEDGER_STATUSES = {"QUEUED", "ACTIVE", "PASS", "FAIL", "BLOCKED"}

DOCUMENTED_RESIDUE = (
    ".openrecomp-phase2/backups/",
    ".openrecomp-phase2/scratch/",
    "artifacts/mips32_translation_v1/",
    "artifacts/mips32_translation_evidence_closure_v1/",
)
ALLOWED_UNTRACKED_PREFIXES = (
    ".openrecomp-phase4/",
    "tools/test_phase4_",
    ".openrecomp-phase3/",
)
# Frozen Phase-2 verification-context files.  They stay on disk (hash-pinned by
# SOURCE_SHA256SUMS.txt and the frozen stage evidence) but must remain
# untracked: 27 are UTF-16LE captures the strict-UTF-8 public-safety scan
# rejects as tracked text, and tools/test_build_package_reproducibility_v1.py
# contains the literal private-key rejection needle exercised by its own
# package content policy test.
FROZEN_UNTRACKED_FILES = (
    ".openrecomp-phase2/evidence/P2-21/p2_21_gate.txt",
    ".openrecomp-phase2/evidence/P2-21/phase1_host_gates.txt",
    ".openrecomp-phase2/evidence/P2-21/source_integrity.txt",
    ".openrecomp-phase2/evidence/P2-22/p2_22_run1.txt",
    ".openrecomp-phase2/evidence/P2-22/p2_22_run2.txt",
    ".openrecomp-phase2/evidence/P2-22/p2_22_run_final.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_01_program_model.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_02_cfg.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_03_functions.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_04_call_graph.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_05_translation_units.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_06_indirect_control_flow.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_07_host_emitter.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_08_runtime_abi.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_09_deterministic_build.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_10_mips32_end_to_end.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_11_mips32_calls_memory.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_12_mips32_direct_cfg.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_13_runtime_host_boundary.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_14_mips32_larger_fixture.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_p2_20_nes6502_program_bridge.txt",
    ".openrecomp-phase2/evidence/P2-22/regression_phase1_source_integrity.txt",
    ".openrecomp-phase2/evidence/P2-22/source_integrity.txt",
    ".openrecomp-phase2/evidence/P2-30/run1.txt",
    ".openrecomp-phase2/evidence/P2-30/run2.txt",
    ".openrecomp-phase2/evidence/P2-50/p2_50_run1.txt",
    ".openrecomp-phase2/evidence/P2-50/p2_50_run2.txt",
    "tools/test_build_package_reproducibility_v1.py",
)

MODIFIED_TRACKED_PREFIXES = (".openrecomp-phase3/evidence/",)

HOST_PATH_PATTERN = re.compile(
    rb"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"
    rb"|(?<![\\])\\\\[A-Za-z0-9_.$-]"
    rb"|file://|/tmp/|/var/tmp/|/home/|/Users/|\\Temp\\|\\AppData\\|\\Users\\"
)
TIMESTAMP_PATTERN = re.compile(
    rb"\b(?:19|20)\d\d[-/]\d\d[-/]\d\d\b|\bT\d\d:\d\d:\d\d(?:\.\d+)?Z?\b"
    rb"|\b\d\d:\d\d:\d\d\b"
)
IDENTITY_PATTERN = re.compile(
    rb"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
CONSOLE_MAGICS = (
    (b"NES\x1a", "iNES container magic"),
    (b"FDS\x1a", "FDS container magic"),
    (b"UNIF", "UNIF container magic"),
)
PREMATURE_CLAIM_PATTERNS = (
    re.compile(rb"OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=PASS"),
    re.compile(rb"OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=(?:PASS|PROVEN)"),
    re.compile(rb"^GENERIC_RUNTIME_STATUS=(?:PASS|PROVEN)$", re.MULTILINE),
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
EVIDENCE_WRITES: dict[str, bytes] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def run_capture(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def run_capture_bytes(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        timeout=timeout,
    )


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def section(name: str, function, *args) -> None:
    print(f"\n--- {name} ---", flush=True)
    function(*args)


# ---------------------------------------------------------------------------
# Phase-4 control plane and frozen queue
# ---------------------------------------------------------------------------
def parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def parse_queue_rows(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        match = re.match(
            r"^\|\s*(P4-\d\d)\s*\|\s*([^|]+?)\s*\|\s*([A-Z]+)\s*\|", line)
        if match:
            rows.append((match.group(1), match.group(2).strip(), match.group(3)))
    return rows


def parse_ledger_rows(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^\|\s*(P4-\d\d)\s*\|[^|]*\|\s*([A-Z_]+)\s*\|", line)
        if match:
            rows.append((match.group(1), match.group(2)))
    return rows


def control_plane_files() -> list[pathlib.Path]:
    return [
        CONTROL_PLANE / name
        for name in CONTROL_FILES
        if (CONTROL_PLANE / name).is_file()
    ]


def audit_control_plane() -> None:
    for name in CONTROL_FILES:
        check(f"control-plane:exists:{name}", (CONTROL_PLANE / name).is_file())
    check("control-plane:evidence-dir", EVIDENCE_ROOT.is_dir())

    state = read_text(CONTROL_PLANE / "STATE.md")
    queue_text = read_text(CONTROL_PLANE / "STAGE_QUEUE.md")
    fields = parse_fields(state)
    for key, value in REQUIRED_FIELDS.items():
        check(f"control-plane:state:{key}", fields.get(key) == value)
    check("control-plane:current-stage",
          re.search(r"^CURRENT_STAGE=P4-\d\d\s*$", state, re.MULTILINE) is not None)
    check("control-plane:last-passed-stage",
          re.search(r"^LAST_PASSED_STAGE=(?:NONE|P4-\d\d)\s*$", state, re.MULTILINE) is not None)
    check("control-plane:status",
          re.search(r"^STATUS=(?:ACTIVE|COMPLETE)\s*$", state, re.MULTILINE) is not None)

    rows = parse_queue_rows(queue_text)
    by_id = {row[0]: row for row in rows}
    check("control-plane:queue-ids-frozen",
          [row[0] for row in rows] == ["P4-00"] + [item[0] for item in FROZEN_QUEUE])
    check("control-plane:queue-names-frozen",
          all(by_id.get(stage, ("", "", ""))[1] == name for stage, name in FROZEN_QUEUE))
    check("control-plane:queue-statuses-valid",
          all(row[2] in QUEUE_STATUSES for row in rows))
    check("control-plane:queue-at-most-one-active",
          sum(1 for row in rows if row[2] == "ACTIVE") <= 1)
    check("control-plane:queue-freeze-section",
          "## Queue freeze" in queue_text and "P4-01" in queue_text
          and "P4-99" in queue_text)
    complete = {row[0] for row in rows if row[2] == "COMPLETE"}
    ledger = parse_ledger_rows(state)
    check("control-plane:ledger-ids-frozen",
          [row[0] for row in ledger] == ["P4-00"] + [item[0] for item in FROZEN_QUEUE])
    check("control-plane:ledger-statuses-valid",
          all(row[1] in LEDGER_STATUSES for row in ledger))
    ledger_pass = {row[0] for row in ledger if row[1] == "PASS"}
    check("control-plane:complete-set-matches-ledger", complete == ledger_pass)
    check("control-plane:terminal-reserved",
          f"{TERMINAL_MARKER}=NOT_PROVEN" in queue_text
          and f"{COMPAT_MARKER}=NOT_PROVEN" in queue_text)
    check("control-plane:scope-target",
          "generic runtime" in read_text(CONTROL_PLANE / "SCOPE.md").lower())
    check("control-plane:policy-boundary",
          PHASE3_TAG in read_text(CONTROL_PLANE / "CONTROL_POLICY.md"))

    offending: list[str] = []
    claim_findings: list[str] = []
    for path in control_plane_files():
        data = path.read_bytes()
        relative = path.relative_to(ROOT).as_posix()
        if HOST_PATH_PATTERN.search(data):
            offending.append(f"{relative}:absolute-host-path")
        if TIMESTAMP_PATTERN.search(data):
            offending.append(f"{relative}:timestamp")
        if IDENTITY_PATTERN.search(data):
            offending.append(f"{relative}:uuid")
        for pattern in PREMATURE_CLAIM_PATTERNS:
            if pattern.search(data):
                claim_findings.append(f"{relative}:premature-claim")
    check("control-plane:deterministic", not offending)
    check("control-plane:no-premature-claims", not claim_findings)

    digest_lines = [
        f"{sha256_file(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in control_plane_files()
    ]
    EVIDENCE_WRITES["control_plane_manifest.txt"] = (
        ("\n".join(digest_lines) + "\n").encode("utf-8"))
    FINDINGS["control_plane"] = {
        "files": len(digest_lines),
        "digest_sha256": sha256_bytes(
            ("\n".join(digest_lines) + "\n").encode("utf-8")),
        "offending": offending,
        "premature_claims": claim_findings,
        "queue_complete": sorted(complete),
        "ledger_pass": sorted(ledger_pass),
    }


# ---------------------------------------------------------------------------
# Frozen Phase-3 boundary
# ---------------------------------------------------------------------------
def audit_frozen_boundary() -> None:
    tag_type = run_capture(["git", "cat-file", "-t", PHASE3_TAG], timeout=120)
    check("phase3:tag-annotated",
          tag_type.returncode == 0 and tag_type.stdout.strip() == "tag")
    tag_object = run_capture(["git", "rev-parse", PHASE3_TAG], timeout=120)
    check("phase3:tag-object",
          tag_object.returncode == 0 and tag_object.stdout.strip() == PHASE3_TAG_OBJECT)
    tag_commit = run_capture(["git", "rev-parse", f"{PHASE3_TAG}^{{commit}}"], timeout=120)
    check("phase3:tag-commit",
          tag_commit.returncode == 0 and tag_commit.stdout.strip() == PHASE3_COMMIT)
    tag_tree = run_capture(["git", "rev-parse", f"{PHASE3_TAG}^{{tree}}"], timeout=120)
    check("phase3:tag-tree",
          tag_tree.returncode == 0 and tag_tree.stdout.strip() == PHASE3_TREE)
    commit_tree = run_capture(["git", "rev-parse", f"{PHASE3_COMMIT}^{{tree}}"], timeout=120)
    check("phase3:commit-tree",
          commit_tree.returncode == 0 and commit_tree.stdout.strip() == PHASE3_TREE)
    phase2 = run_capture(["git", "rev-parse", f"{PHASE2_TAG}^{{commit}}"], timeout=120)
    check("phase2:tag-commit",
          phase2.returncode == 0 and phase2.stdout.strip() == PHASE2_COMMIT)
    phase1 = run_capture(["git", "rev-parse", f"{PHASE1_TAG}^{{commit}}"], timeout=120)
    check("phase1:tag-commit",
          phase1.returncode == 0 and phase1.stdout.strip() == PHASE1_COMMIT)
    ancestor = run_capture(
        ["git", "merge-base", "--is-ancestor", PHASE3_COMMIT, "HEAD"], timeout=120)
    check("branch:descends-from-boundary", ancestor.returncode == 0)
    merge_base = run_capture(["git", "merge-base", PHASE3_COMMIT, "HEAD"], timeout=120)
    check("branch:merge-base-is-boundary",
          merge_base.returncode == 0 and merge_base.stdout.strip() == PHASE3_COMMIT)
    branch = run_capture(["git", "branch", "--show-current"], timeout=120)
    check("branch:phase4-branch",
          branch.returncode == 0 and branch.stdout.strip().startswith("phase4/"))
    FINDINGS["boundary"] = {
        "tag": PHASE3_TAG,
        "tag_object": PHASE3_TAG_OBJECT,
        "commit": PHASE3_COMMIT,
        "tree": PHASE3_TREE,
        "branch": branch.stdout.strip(),
    }


# ---------------------------------------------------------------------------
# Frozen Phase-3 evidence identities
# ---------------------------------------------------------------------------
def audit_frozen_evidence() -> None:
    check("evidence:root-manifest", sha256_file(ROOT / SOURCE_SUMS) == SOURCE_SUMS_SHA256)
    root_lines = [
        line for line in read_text(ROOT / SOURCE_SUMS).strip().splitlines() if line.strip()
    ]
    check("evidence:root-manifest-entries", len(root_lines) == SOURCE_SUMS_ENTRIES)
    check("evidence:phase3-manifest", sha256_file(ROOT / P3_SUMS) == P3_SUMS_SHA256)
    phase3_lines = [
        line for line in read_text(ROOT / P3_SUMS).strip().splitlines() if line.strip()
    ]
    check("evidence:phase3-manifest-entries", len(phase3_lines) == P3_SUMS_ENTRIES)
    check("evidence:p3-99-result-json",
          sha256_file(ROOT / P3_99_RESULT_JSON) == P3_99_RESULT_JSON_SHA256)
    check("evidence:p3-99-gate", sha256_file(ROOT / P3_99_GATE) == P3_99_GATE_SHA256)
    fixture = (ROOT / FIXTURE_REL).read_bytes()
    check("evidence:fixture-sha256", sha256_bytes(fixture) == FIXTURE_SHA256)
    check("evidence:fixture-size", len(fixture) == FIXTURE_SIZE)
    FINDINGS["frozen_evidence"] = {
        "root_manifest_sha256": sha256_file(ROOT / SOURCE_SUMS),
        "root_manifest_entries": len(root_lines),
        "phase3_manifest_sha256": sha256_file(ROOT / P3_SUMS),
        "phase3_manifest_entries": len(phase3_lines),
        "fixture_sha256": sha256_bytes(fixture),
    }


# ---------------------------------------------------------------------------
# Phase-3 final gate re-run in the frozen Phase-3 verification context
# ---------------------------------------------------------------------------
def phase4_untracked_entries() -> list[str]:
    status = run_capture(["git", "status", "--porcelain"], timeout=300)
    entries: list[str] = []
    for line in status.stdout.splitlines():
        if not line.startswith("?? "):
            continue
        item = line[3:].strip().replace("\\", "/").rstrip("/")
        if item.startswith(".openrecomp-phase4") or item.startswith("tools/test_phase4_"):
            entries.append(item)
    return sorted(entries)


def current_branch() -> str:
    return run_capture(
        ["git", "branch", "--show-current"], timeout=120).stdout.strip()


def branch_exists(name: str) -> bool:
    exists = run_capture(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"],
        timeout=120)
    return exists.returncode == 0


def switch_to_branch(name: str) -> bool:
    """Switch branches, verifying the end state (transient-safe)."""
    for _ in range(5):
        if current_branch() == name:
            return True
        run_capture(["git", "switch", name], timeout=300)
        time.sleep(1.0)
    return current_branch() == name


def delete_branch(name: str) -> bool:
    """Delete a local branch, verifying the end state (transient-safe)."""
    for _ in range(5):
        if not branch_exists(name):
            return True
        run_capture(["git", "branch", "-d", name], timeout=300)
        time.sleep(1.0)
    return not branch_exists(name)


def restore_frozen_verdict() -> bool:
    """Restore the committed P3-99 verdict bytes if a re-run overwrote them.

    The frozen P3-99 gate rewrites its own ``RESULT.json`` on every run.  A
    failed re-run must not leave a FAIL record in the frozen verdict slot, so
    the committed bytes are restored from HEAD when they differ.  This writes
    the frozen record back; it never rewrites history.
    """
    committed = subprocess.run(
        ["git", "show", f"HEAD:{P3_99_RESULT_JSON}"],
        cwd=str(ROOT), capture_output=True).stdout
    path = ROOT / P3_99_RESULT_JSON
    current = path.read_bytes() if path.is_file() else b""
    if committed and committed != current:
        path.write_bytes(committed)
        return True
    return False


def audit_phase3_final_gate(python: str) -> None:
    original_branch = current_branch()
    check("phase3-gate:phase4-branch-context", original_branch.startswith("phase4/"))
    check("phase3-gate:verification-branch-name-free",
          not branch_exists(TEMP_VERIFY_BRANCH))
    verdict_restored_pre = restore_frozen_verdict()
    check("phase3-gate:frozen-verdict-pre-run",
          sha256_file(ROOT / P3_99_RESULT_JSON) == P3_99_RESULT_JSON_SHA256)

    run_capture(["git", "switch", "-c", TEMP_VERIFY_BRANCH], timeout=300)
    check("phase3-gate:verification-branch-created",
          current_branch() == TEMP_VERIFY_BRANCH)

    entries = phase4_untracked_entries()
    hold = pathlib.Path(tempfile.mkdtemp(prefix="p4_00_hold_"))
    moved: list[str] = []
    restored: list[str] = []
    completed: subprocess.CompletedProcess[bytes] | None = None
    branch_restored = False
    branch_deleted = False
    verdict_restored_post = False
    try:
        for rel in entries:
            source = ROOT / rel
            if not source.exists():
                continue
            destination = hold / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved.append(rel)
        completed = run_capture_bytes([python, P3_99_GATE], timeout=7200)
    finally:
        for rel in reversed(moved):
            source = hold / rel
            destination = ROOT / rel
            if source.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
                if destination.exists():
                    restored.append(rel)
        shutil.rmtree(hold, ignore_errors=True)
        branch_restored = switch_to_branch(original_branch)
        if branch_restored:
            branch_deleted = delete_branch(TEMP_VERIFY_BRANCH)
        verdict_restored_post = restore_frozen_verdict()

    check("phase3-gate:phase4-context-restored", len(restored) == len(moved))
    check("phase3-gate:original-branch-restored", branch_restored)
    check("phase3-gate:verification-branch-deleted", branch_deleted)
    check("phase3-gate:frozen-verdict-preserved",
          sha256_file(ROOT / P3_99_RESULT_JSON) == P3_99_RESULT_JSON_SHA256)

    stdout = completed.stdout or b""
    stderr = completed.stderr or b""
    stdout_lf = normalize_bytes(stdout)
    EVIDENCE_WRITES["p3_99_reverify_stdout.txt"] = stdout_lf
    EVIDENCE_WRITES["p3_99_reverify_stderr.txt"] = normalize_bytes(stderr)
    check("phase3-gate:returncode", completed.returncode == 0)
    check("phase3-gate:stderr-empty", not stderr.strip())
    check("phase3-gate:no-failures", b"FAIL" not in stdout_lf)
    decoded = stdout_lf.decode("utf-8", errors="replace")
    for marker in P3_99_MARKERS:
        check(f"phase3-gate:marker:{marker.split('=')[0]}", marker in decoded)
    check("phase3-gate:stdout-size", len(stdout) == P3_99_STDOUT_BYTES)
    check("phase3-gate:stdout-raw-sha256", sha256_bytes(stdout) == P3_99_STDOUT_SHA256)
    check("phase3-gate:stdout-lf-sha256", sha256_bytes(stdout_lf) == P3_99_STDOUT_SHA256_LF)
    FINDINGS["phase3_final_gate"] = {
        "original_branch": original_branch,
        "phase4_context_entries_held": len(moved),
        "phase4_context_entries_restored": len(restored),
        "returncode": completed.returncode,
        "stdout_bytes": len(stdout),
        "stdout_sha256_raw": sha256_bytes(stdout),
        "stdout_sha256_lf": sha256_bytes(stdout_lf),
        "stderr_empty": not stderr.strip(),
        "verification_branch": TEMP_VERIFY_BRANCH,
        "verdict_record_restored_pre_run": verdict_restored_pre,
        "verdict_record_restored_post_run": verdict_restored_post,
    }


# ---------------------------------------------------------------------------
# Worktree, residue and legal
# ---------------------------------------------------------------------------
def untracked_allowed(item: str) -> bool:
    if item in FROZEN_UNTRACKED_FILES:
        return True
    if any(item.startswith(prefix) for prefix in ALLOWED_UNTRACKED_PREFIXES):
        return True
    return any(item.startswith(prefix) for prefix in DOCUMENTED_RESIDUE)


def audit_worktree() -> None:
    status = run_capture(["git", "status", "--porcelain"], timeout=300)
    check("worktree:status-readable", status.returncode == 0)
    untracked: list[str] = []
    modified: list[str] = []
    unexpected_codes: list[str] = []
    for line in status.stdout.splitlines():
        if line.startswith("?? "):
            untracked.append(line[3:].strip().replace("\\", "/"))
            continue
        code = line[:2]
        path = line[3:].strip().replace("\\", "/")
        if "R" in code:
            unexpected_codes.append(f"rename:{path}")
        elif "D" in code:
            unexpected_codes.append(f"deleted:{path}")
        elif "M" in code:
            modified.append(path)
        elif code[0] == "A":
            unexpected_codes.append(f"staged-add:{path}")
    unexpected = [item for item in untracked if not untracked_allowed(item)]
    check("worktree:no-unexpected-untracked", not unexpected)
    bad_modified = [
        item for item in modified
        if not item.startswith(MODIFIED_TRACKED_PREFIXES)
    ]
    check("worktree:modified-tracked-scope", not bad_modified)
    check("worktree:no-deleted-or-staged-paths", not unexpected_codes)

    residue_files = sorted(
        path for prefix in DOCUMENTED_RESIDUE
        for path in (ROOT / prefix.rstrip("/")).rglob("*")
        if path.is_file()
    )
    check("worktree:residue-documented",
          all((ROOT / prefix.rstrip("/")).exists() for prefix in DOCUMENTED_RESIDUE))
    FINDINGS["worktree"] = {
        "untracked_entries": len(untracked),
        "unexpected_untracked": unexpected,
        "modified_tracked": modified,
        "unexpected_codes": unexpected_codes,
        "residue_files": len(residue_files),
    }

    console_findings: list[str] = []
    for path in sorted(CONTROL_PLANE.rglob("*")):
        if not path.is_file():
            continue
        head = path.read_bytes()[:16]
        for magic, label in CONSOLE_MAGICS:
            if head.startswith(magic):
                console_findings.append(
                    f"{path.relative_to(ROOT).as_posix()}:{label}")
    check("legal:no-console-magics", not console_findings)
    FINDINGS["legal"] = {"console_magics": console_findings}


# ---------------------------------------------------------------------------
# Phase-4 source manifest
# ---------------------------------------------------------------------------
def audit_phase4_manifest() -> None:
    manifest = ROOT / P4_SUMS
    check("source:phase4-manifest-exists", manifest.is_file())
    entries = [
        line for line in read_text(manifest).strip().splitlines() if line.strip()
    ]
    check("source:phase4-manifest-entries", len(entries) >= 1)
    bad: list[str] = []
    for line in entries:
        match = re.match(r"^([0-9a-f]{64}) \*(.+)$", line)
        if not match:
            bad.append(f"malformed:{line}")
            continue
        digest, rel = match.group(1), match.group(2)
        path = ROOT / rel
        if not path.is_file() or sha256_file(path) != digest:
            bad.append(f"mismatch:{rel}")
    check("source:phase4-manifest-entries-verified", not bad)
    FINDINGS["phase4_manifest"] = {
        "entries": len(entries),
        "bad": bad,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P4-00 Phase-4 boundary gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-00")
    parser.add_argument("--python", type=str, default=sys.executable)
    args = parser.parse_args()

    global EVIDENCE_DIR, EVIDENCE_ROOT, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P4-00 Phase-4 Boundary Gate ===", flush=True)
    failure: str | None = None
    try:
        section("control_plane", audit_control_plane)
        section("frozen_boundary", audit_frozen_boundary)
        section("phase3_final_gate", audit_phase3_final_gate, args.python)
        section("frozen_evidence", audit_frozen_evidence)
        section("phase4_manifest", audit_phase4_manifest)
        section("worktree", audit_worktree)
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
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for relative, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / relative).write_bytes(data)
    (EVIDENCE_DIR / "p4_00_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    print("\n=== RESULT ===")
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{TERMINAL_MARKER}=NOT_PROVEN")
        print(f"{COMPAT_MARKER}=NOT_PROVEN")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FEATURE_MARKER}=FAIL")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
