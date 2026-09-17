#!/usr/bin/env python3
"""OpenRecomp Phase-3 boundary gate (P3-00).

P3-00 is the Phase-3 entry verification stage.  It adds no emulation or
recompilation capability.  The deterministic gate proves, before any Phase-3
implementation work begins:

* the Phase-2 frozen tag ``openrecomp-phase2-pass`` resolves to the recorded
  commit/tree and the current Phase-3 branch descends from that boundary;
* the Phase-2 terminal evidence is unchanged (frozen byte identities on disk)
  and still declares ``OPENRECOMP_P2_99=PASS`` /
  ``OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS``;
* the frozen verification context is preserved: the 28 recorded
  verification-context files exist on disk with the recorded canonical
  manifest digest and remain untracked, because tracking them changes the
  tracked-file context in which the frozen Phase-1/Phase-2 gates were
  verified (27 are UTF-16LE captures; one carries the public-safety needle);
* ``python tools/test_phase2_final_verdict_v1.py`` (verify-only) still passes
  on this tree, byte-identically to the recorded terminal stdout;
* the Phase-3 control plane exists and is deterministic (no timestamps, host
  paths, or process identity);
* CoreMark has not been treated as proven or supported
  (``COREMARK_STATUS=NOT_PROVEN``);
* the working tree has no unexpected untracked paths beyond the documented
  Phase-2 residue and the Phase-3 control plane itself.

On success it emits::

    OPENRECOMP_P3_00=PASS
    OPENRECOMP_PHASE3_BOUNDARY_V1=PASS tests=<count>

Any failed invariant fails closed and emits ``OPENRECOMP_P3_00=FAIL``.

Usage:

    python tools/test_phase3_boundary_v1.py
    python tools/test_phase3_boundary_v1.py --evidence-dir .openrecomp-phase3/evidence/P3-00
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL_PLANE = ROOT / ".openrecomp-phase3"
EVIDENCE_ROOT = CONTROL_PLANE / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-00"

STAGE = "P3-00"
STAGE_MARKER = "OPENRECOMP_P3_00"
FEATURE_MARKER = "OPENRECOMP_PHASE3_BOUNDARY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF"

PHASE2_TAG = "openrecomp-phase2-pass"
PHASE2_COMMIT = "01b1d7cba8c931fca95d041389cfb1902b7c89fe"
PHASE2_TREE = "6513eefa5ef59b7d0e127f0179c6fc6c21fdac78"
PHASE1_TAG = "openrecomp-phase1-pass"
PHASE1_COMMIT = "46c2f971e1a42cf49bd936bad94697b81bf31002"

SOURCE_SUMS = "SOURCE_SHA256SUMS.txt"
SOURCE_SUMS_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
SOURCE_SUMS_ENTRIES = 134
P2_99_RESULT_JSON = ".openrecomp-phase2/evidence/P2-99/RESULT.json"
P2_99_RESULT_JSON_SHA256 = "880d25961949b0dc9aedaca78ca60d2dac54bbffeb6fd61e63045acd6394d8df"
P2_99_GATE = "tools/test_phase2_final_verdict_v1.py"
P2_99_GATE_SHA256 = "8d6a42d5e335fb7d7612bb222adca19be0e5290a26a8cc65e63b8be0b9e64e21"
P2_99_STDOUT_SHA256 = "66913e5752a9e2b7e399513710b4dce05efce9a714335c3b9908c0e30ea38c28"
P2_99_STDOUT_MARKERS = (
    "OPENRECOMP_P2_99=PASS",
    "OPENRECOMP_PHASE2_FINAL_VERDICT_V1=PASS tests=202",
    "OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS",
)
P2_99_DOC_MARKERS = (
    "OPENRECOMP_P2_99=PASS",
    "OPENRECOMP_PHASE2_FINAL_VERDICT_V1=PASS",
    "OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS",
)
P2_99_RUN1 = ".openrecomp-phase2/evidence/P2-99/run1.txt"
P2_99_RUN2 = ".openrecomp-phase2/evidence/P2-99/run2.txt"
P2_99_TERMINAL_CAPTURE = ".openrecomp-phase2/evidence/P2-99/p2_90_terminal_run.txt"
P2_99_TERMINAL_CAPTURE_SHA256_LF = (
    "ac9c0b8abcdd7c0d0c3d271f0276f2e4a923cf32e3103a8322757ec96824a7f2"
)
P2_90_FROZEN_CAPTURE = ".openrecomp-phase2/evidence/P2-90/p2_90_run1.txt"
P2_90_FROZEN_CAPTURE_SHA256 = (
    "74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7"
)
P2_90_CAPTURE_PRESERVATION = (
    ".openrecomp-phase2/evidence/P2-99/p2_90_capture_preservation.json"
)
P2_PLANE_STATE = ".openrecomp-phase2/STATE.md"
P2_PLANE_HANDOFF = ".openrecomp-phase2/HANDOFF.md"

CONTROL_FILES = (
    "CONTROL_POLICY.md",
    "SCOPE.md",
    "STAGE_QUEUE.md",
    "STATE.md",
    "HANDOFF.md",
)
REQUIRED_FIELDS = {
    "PHASE": "3",
    "BASELINE_TAG": PHASE2_TAG,
    "BASELINE_COMMIT": PHASE2_COMMIT,
    "BASELINE_TREE": PHASE2_TREE,
    "FINAL_VERDICT": "NOT_PROVEN",
    "COREMARK_STATUS": "NOT_PROVEN",
}
DOCUMENTED_RESIDUE = (
    ".openrecomp-phase2/backups/",
    ".openrecomp-phase2/scratch/",
    "artifacts/mips32_translation_v1/",
    "artifacts/mips32_translation_evidence_closure_v1/",
)
P3_ALLOWED_UNTRACKED = (".openrecomp-phase3/", "tools/test_phase3_")

# Frozen Phase-2 verification-context files.  They stay on disk (hash-pinned by
# SOURCE_SHA256SUMS.txt and the frozen stage evidence) but must remain
# untracked: 27 are UTF-16LE stdout/regression captures that the strict-UTF-8
# Phase-1 public-safety-scan gate rejects as tracked text, and
# tools/test_build_package_reproducibility_v1.py contains the literal
# private-key rejection needle exercised by its own package content policy
# test.  The official Phase-2 terminal verification was performed with these
# files untracked; tracking them changes that verification context.
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
FROZEN_UNTRACKED_MANIFEST_SHA256 = (
    "40e4f23a35f40c5d25da630467d46f5e8ad8409a40efff8412892217447a8349"
)

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
COREMARK_CLAIM_PATTERNS = (
    re.compile(rb"OPENRECOMP_P3_COREMARK\S*=PASS"),
    re.compile(rb"COREMARK_STATUS=(?:PASS|PROVEN|BOUNDED_PROVEN)"),
    re.compile(rb"COREMARK_(?:PROOF|VERDICT)=(?:PASS|PROVEN)"),
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


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
# Frozen boundary
# ---------------------------------------------------------------------------
def audit_frozen_boundary() -> None:
    tag_type = run_capture(["git", "cat-file", "-t", PHASE2_TAG], timeout=120)
    check("phase2:tag-annotated", tag_type.returncode == 0 and tag_type.stdout.strip() == "tag")
    tag_commit = run_capture(["git", "rev-parse", f"{PHASE2_TAG}^{{commit}}"], timeout=120)
    check("phase2:tag-commit",
          tag_commit.returncode == 0 and tag_commit.stdout.strip() == PHASE2_COMMIT)
    tag_tree = run_capture(["git", "rev-parse", f"{PHASE2_TAG}^{{tree}}"], timeout=120)
    check("phase2:tag-tree",
          tag_tree.returncode == 0 and tag_tree.stdout.strip() == PHASE2_TREE)
    commit_tree = run_capture(["git", "rev-parse", f"{PHASE2_COMMIT}^{{tree}}"], timeout=120)
    check("phase2:commit-tree",
          commit_tree.returncode == 0 and commit_tree.stdout.strip() == PHASE2_TREE)
    phase1 = run_capture(["git", "rev-parse", f"{PHASE1_TAG}^{{commit}}"], timeout=120)
    check("phase1:tag-commit",
          phase1.returncode == 0 and phase1.stdout.strip() == PHASE1_COMMIT)
    ancestor = run_capture(
        ["git", "merge-base", "--is-ancestor", PHASE2_COMMIT, "HEAD"], timeout=120)
    check("branch:descends-from-boundary",
          ancestor.returncode == 0)
    merge_base = run_capture(["git", "merge-base", PHASE2_COMMIT, "HEAD"], timeout=120)
    check("branch:merge-base-is-boundary",
          merge_base.returncode == 0 and merge_base.stdout.strip() == PHASE2_COMMIT)
    branch = run_capture(["git", "branch", "--show-current"], timeout=120)
    check("branch:phase3-branch", branch.returncode == 0 and branch.stdout.strip().startswith("phase3/"))
    ahead = run_capture(["git", "rev-list", "--count", f"{PHASE2_COMMIT}..HEAD"], timeout=120)
    check("branch:ahead-count-readable", ahead.returncode == 0 and ahead.stdout.strip().isdigit())
    FINDINGS["boundary"] = {
        "tag": PHASE2_TAG,
        "commit": PHASE2_COMMIT,
        "tree": PHASE2_TREE,
        "branch": branch.stdout.strip(),
        "commits_since_boundary": int(ahead.stdout.strip() or 0),
    }


# ---------------------------------------------------------------------------
# Frozen Phase-2 evidence (disk byte identities)
# ---------------------------------------------------------------------------
def audit_frozen_evidence() -> None:
    check("evidence:source-sums", sha256_file(ROOT / SOURCE_SUMS) == SOURCE_SUMS_SHA256)
    manifest_lines = [
        line for line in read_text(ROOT / SOURCE_SUMS).strip().splitlines() if line.strip()
    ]
    check("evidence:source-sums-entries", len(manifest_lines) == SOURCE_SUMS_ENTRIES)
    check("evidence:p2-99-result-json",
          sha256_file(ROOT / P2_99_RESULT_JSON) == P2_99_RESULT_JSON_SHA256)
    check("evidence:p2-99-gate", sha256_file(ROOT / P2_99_GATE) == P2_99_GATE_SHA256)
    check("evidence:p2-99-run1", sha256_file(ROOT / P2_99_RUN1) == P2_99_STDOUT_SHA256)
    check("evidence:p2-99-run2", sha256_file(ROOT / P2_99_RUN2) == P2_99_STDOUT_SHA256)
    check("evidence:p2-90-frozen-capture",
          sha256_file(ROOT / P2_90_FROZEN_CAPTURE) == P2_90_FROZEN_CAPTURE_SHA256)
    terminal = normalize_text(read_text(ROOT / P2_99_TERMINAL_CAPTURE))
    check("evidence:p2-99-terminal-capture",
          sha256_bytes(terminal.encode("utf-8")) == P2_99_TERMINAL_CAPTURE_SHA256_LF)
    state = read_text(ROOT / P2_PLANE_STATE)
    handoff = read_text(ROOT / P2_PLANE_HANDOFF)
    for marker in P2_99_DOC_MARKERS:
        check(f"evidence:phase2-state:{marker.split('=')[0]}", marker in state)
        check(f"evidence:phase2-handoff:{marker.split('=')[0]}", marker in handoff)
    preservation = json.loads(read_text(ROOT / P2_90_CAPTURE_PRESERVATION))
    frozen = preservation.get("frozen_files", {})
    check("evidence:p2-90-preservation-restored",
          bool(frozen) and all(
              item.get("restored_byte_identical_to_before") is True
              for item in frozen.values()))
    FINDINGS["frozen_evidence"] = {
        "source_sums_sha256": sha256_file(ROOT / SOURCE_SUMS),
        "source_sums_entries": len(manifest_lines),
        "p2_99_result_json_sha256": sha256_file(ROOT / P2_99_RESULT_JSON),
        "p2_99_terminal_capture_sha256_lf": sha256_bytes(terminal.encode("utf-8")),
    }


# ---------------------------------------------------------------------------
# Frozen verification context (untracked-but-pinned Phase-2 files)
# ---------------------------------------------------------------------------
def audit_verification_context() -> None:
    tracked = {
        item.replace("\\", "/")
        for item in run_capture(["git", "ls-files", "-z"], timeout=300).stdout.split("\x00")
        if item
    }
    check("verification-context:tracked-set-readable", isinstance(tracked, set))
    missing = [rel for rel in FROZEN_UNTRACKED_FILES if not (ROOT / rel).is_file()]
    check("verification-context:files-present", not missing)
    tracked_again = [rel for rel in FROZEN_UNTRACKED_FILES if rel in tracked]
    check("verification-context:files-untracked", not tracked_again)
    lines = [
        f"{sha256_file(ROOT / rel)}  {rel}"
        for rel in sorted(FROZEN_UNTRACKED_FILES)
    ]
    manifest = "\n".join(lines) + "\n"
    digest = sha256_bytes(manifest.encode("utf-8"))
    (EVIDENCE_DIR / "frozen_untracked_manifest.txt").write_bytes(manifest.encode("utf-8"))
    check("verification-context:manifest-digest", digest == FROZEN_UNTRACKED_MANIFEST_SHA256)
    FINDINGS["verification_context"] = {
        "files": len(FROZEN_UNTRACKED_FILES),
        "manifest_sha256": digest,
        "missing": missing,
        "tracked_again": tracked_again,
    }


# ---------------------------------------------------------------------------
# P2-99 re-verification on the Phase-3 tree
# ---------------------------------------------------------------------------
def audit_p2_99_reverify(python: str) -> None:
    completed = run_capture_bytes([python, P2_99_GATE], timeout=7200)
    stdout_bytes = completed.stdout or b""
    stderr_bytes = completed.stderr or b""
    stdout = normalize_text(stdout_bytes.decode("utf-8", errors="replace"))
    (EVIDENCE_DIR / "p2_99_reverify_stdout.txt").write_bytes(stdout_bytes)
    (EVIDENCE_DIR / "p2_99_reverify_stderr.txt").write_bytes(stderr_bytes)
    check("p2-99:returncode", completed.returncode == 0)
    check("p2-99:stderr-empty", not stderr_bytes.strip())
    check("p2-99:no-failures", "FAIL" not in stdout)
    for marker in P2_99_STDOUT_MARKERS:
        check(f"p2-99:marker:{marker.split('=')[0]}", marker in stdout)
    digest = sha256_bytes(stdout_bytes)
    check("p2-99:stdout-byte-identical", digest == P2_99_STDOUT_SHA256)
    FINDINGS["p2_99_reverify"] = {
        "returncode": completed.returncode,
        "stdout_sha256": digest,
        "stdout_sha256_lf": sha256_bytes(
            stdout_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")),
        "stdout_bytes": len(stdout_bytes),
        "stderr_empty": not stderr_bytes.strip(),
    }


# ---------------------------------------------------------------------------
# Phase-3 control plane
# ---------------------------------------------------------------------------
def parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def control_plane_files() -> list[pathlib.Path]:
    """The Phase-3 governance files whose determinism P3-00 verifies.

    Build inputs, toolchain caches, external sources and stage evidence are
    deliberately out of scope; they are recorded by their own stage gates.
    """
    return [
        CONTROL_PLANE / name
        for name in CONTROL_FILES
        if (CONTROL_PLANE / name).is_file()
    ]


def audit_control_plane() -> None:
    for name in CONTROL_FILES:
        check(f"control-plane:exists:{name}", (CONTROL_PLANE / name).is_file())
    check("control-plane:evidence-dir", EVIDENCE_ROOT.is_dir())
    state_path = CONTROL_PLANE / "STATE.md"
    queue = read_text(CONTROL_PLANE / "STAGE_QUEUE.md")
    state = read_text(state_path)
    fields = parse_fields(state)
    for key, value in REQUIRED_FIELDS.items():
        check(f"control-plane:state:{key}", fields.get(key) == value)
    check("control-plane:current-stage",
          re.search(r"^CURRENT_STAGE=P3-\d\d\s*$", state, re.MULTILINE) is not None)
    check("control-plane:last-passed-stage",
          re.search(r"^LAST_PASSED_STAGE=(?:NONE|P3-\d\d)\s*$", state, re.MULTILINE) is not None)
    check("control-plane:status",
          re.search(r"^STATUS=(?:ACTIVE|COMPLETE)\s*$", state, re.MULTILINE) is not None)
    check("control-plane:queue-p3-00",
          re.search(r"^\|\s*P3-00\s*\|[^|]*\|\s*(?:ACTIVE|COMPLETE)\s*\|", queue,
                    re.MULTILINE) is not None)
    check("control-plane:queue-p3-01",
          re.search(r"^\|\s*P3-01\s*\|[^|]*\|\s*(?:QUEUED|ACTIVE|COMPLETE)\s*\|", queue,
                    re.MULTILINE) is not None)
    check("control-plane:terminal-reserved",
          TERMINAL_MARKER in queue and "NOT_PROVEN" in queue)
    check("control-plane:scope-target", "CoreMark" in read_text(CONTROL_PLANE / "SCOPE.md"))
    check("control-plane:policy-boundary",
          PHASE2_TAG in read_text(CONTROL_PLANE / "CONTROL_POLICY.md"))

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
        if path.suffix.lower() == ".md":
            for pattern in COREMARK_CLAIM_PATTERNS:
                if pattern.search(data):
                    claim_findings.append(f"{relative}:coremark-claim")
    check("control-plane:deterministic", not offending)
    check("control-plane:coremark-not-proven", not claim_findings)

    digest_lines = [
        f"{sha256_file(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in control_plane_files()
    ]
    digest = sha256_bytes(("\n".join(digest_lines) + "\n").encode("utf-8"))
    (EVIDENCE_DIR / "control_plane_manifest.txt").write_bytes(
        ("\n".join(digest_lines) + "\n").encode("utf-8"))
    FINDINGS["control_plane"] = {
        "files": len(digest_lines),
        "digest_sha256": digest,
        "offending": offending,
        "coremark_claim_findings": claim_findings,
    }


# ---------------------------------------------------------------------------
# Worktree / residue / legal
# ---------------------------------------------------------------------------
def audit_worktree() -> None:
    status = run_capture(["git", "status", "--porcelain"], timeout=300)
    check("worktree:status-readable", status.returncode == 0)
    untracked = [
        line[3:].strip().replace("\\", "/")
        for line in status.stdout.splitlines()
        if line.startswith("?? ")
    ]
    unexpected = [
        item for item in untracked
        if not item.startswith(P3_ALLOWED_UNTRACKED)
        and item not in FROZEN_UNTRACKED_FILES
        and not any(item.startswith(prefix) for prefix in DOCUMENTED_RESIDUE)
    ]
    check("worktree:no-unexpected-untracked", not unexpected)
    residue_files = sorted(
        path for prefix in DOCUMENTED_RESIDUE
        for path in (ROOT / prefix.rstrip("/")).rglob("*")
        if path.is_file()
    )
    manifest_lines = [
        f"{sha256_file(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in residue_files
    ]
    (EVIDENCE_DIR / "residue_manifest.txt").write_bytes(
        ("\n".join(manifest_lines) + "\n").encode("utf-8"))
    check("worktree:residue-documented",
          all((ROOT / prefix.rstrip("/")).exists() for prefix in DOCUMENTED_RESIDUE))
    FINDINGS["worktree"] = {
        "untracked_top_level": untracked,
        "unexpected": unexpected,
        "residue_files": len(residue_files),
        "residue_manifest_sha256": sha256_bytes(
            ("\n".join(manifest_lines) + "\n").encode("utf-8")),
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
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P3-00 Phase-3 boundary gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-00")
    parser.add_argument("--python", type=str, default=sys.executable)
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}

    print("=== P3-00 Phase-3 Boundary Gate ===", flush=True)
    failure: str | None = None
    try:
        section("control_plane", audit_control_plane)
        section("frozen_boundary", audit_frozen_boundary)
        section("verification_context", audit_verification_context)
        section("p2_99_reverify", audit_p2_99_reverify, args.python)
        section("frozen_evidence", audit_frozen_evidence)
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
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    (EVIDENCE_DIR / "p3_00_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    print("\n=== RESULT ===")
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{TERMINAL_MARKER}=NOT_PROVEN")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FEATURE_MARKER}=FAIL")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
