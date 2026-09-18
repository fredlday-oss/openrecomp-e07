#!/usr/bin/env python3
"""OpenRecomp Phase-5 boundary gate (P5-00).

Verifies the exact frozen Phase-4 PASS boundary, independently re-runs the
Phase-4 final verdict gate in a reconstructed pre-verdict context, establishes
the Phase-5 control-plane/ROM-safety/public-private-fixture separation and
freezes the Phase-5 queue rows before any P5-01 implementation work.

On success it emits::

    OPENRECOMP_P5_00=PASS
    OPENRECOMP_PHASE5_BOUNDARY_V1=PASS tests=<count>
    OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase5_boundary_v1.py --evidence-dir .openrecomp-phase5/evidence/P5-00
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
CONTROL4 = ROOT / ".openrecomp-phase4"
CONTROL5 = ROOT / ".openrecomp-phase5"

STAGE = "P5-00"
STAGE_MARKER = "OPENRECOMP_P5_00"
FEATURE_MARKER = "OPENRECOMP_PHASE5_BOUNDARY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

PHASE4_TAG = "openrecomp-phase4-pass"
PHASE4_TAG_OBJECT = "e7eaab18fee267b3d7962db13835c9e14dd77fc2"
PHASE4_COMMIT = "b3c71fb690f00b4811e8ec30c28f7725141295d0"
PHASE4_TREE = "f2ca3080915aa68f403526b89dfc17454687aed6"
PHASE3_TAG_OBJECT = "ac31524504b1b5cc63aabcfd5132a3eb4275e8e9"
PHASE3_COMMIT = "e16e4b29b90f379615f1af97e47747cd1d531796"
PHASE3_TREE = "a940f0d84a32adaf191f7ff2bebfb24cc855cde0"
PHASE2_COMMIT = "01b1d7cba8c931fca95d041389cfb1902b7c89fe"
PHASE1_COMMIT = "46c2f971e1a42cf49bd936bad94697b81bf31002"

P4_99_GATE = "tools/test_phase4_final_verdict_v1.py"
P4_99_GATE_SHA256 = "6c357c18401ebff522810e8106fdd70032a7a2774ea63ad1377351aa3ca22abd"
P4_99_RECORD_SHA256 = "f13cf89155daaf07731097a7530a642c7cbd60cc5ae231e9f602139cdcc78154"
P4_99_STDOUT_BYTES = 2609
P4_99_STDOUT_RAW_SHA256 = "903308caf2167053de63f8d87a7376c09125c7ea0d0fd2d0fc08a90d90ec8c6e"
P4_99_STDOUT_LF_SHA256 = "79c6f395637bf195e478b03eeadd009dfbf83df4e2e51648245a08d93acbca7d"
P4_99_TESTS = 79
P4_TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
P4_COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

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
    ("P5-01", "NES/iNES ingestion and inventory"),
    ("P5-02", "2A03/6502 decode + reachable instruction frontier"),
    ("P5-03", "CPU semantics proof"),
    ("P5-04", "ProgramModel / CFG / functions / translation units"),
    ("P5-05", "NES CPU memory map + mapper model"),
    ("P5-06", "PPU boundary / deterministic graphics model"),
    ("P5-07", "APU/input/timing/interrupt boundary"),
    ("P5-08", "Host emission + NES platform adapter"),
    ("P5-09", "Native execution of legal NES fixture"),
    ("P5-10", "Independent NES reference equivalence"),
    ("P5-11", "Private TMNT compatibility run"),
    ("P5-12", "Reproducible NES package"),
    ("P5-90", "Phase-5 whole regression"),
    ("P5-91", "Evidence index + compatibility limitations"),
    ("P5-99", "Final Phase-5 verdict"),
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
    "artifacts/",
)
ALLOWED_UNTRACKED_RE = re.compile(r"^tools/test_phase5_[A-Za-z0-9_]+\.py$")
ALLOWED_MODIFIED_PREFIXES = (".openrecomp-phase5/",)
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
                          text=True, encoding="utf-8", errors="replace", timeout=300)


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
        match = re.match(r"^\|\s*(P5-\d\d)\s*\|\s*([^|]+?)\s*\|\s*([A-Z_]+)\s*\|", line)
        if match:
            rows.append((match.group(1), match.group(2), match.group(3)))
    return rows


def parse_ledger_rows(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^\|\s*(P5-\d\d)\s*\|[^|]*\|\s*([A-Z_]+)\s*\|", line)
        if match:
            rows.append((match.group(1), match.group(2)))
    return rows


def reconstruct_p4_99_context() -> dict[str, Any]:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="p5_p4_99_recon_"))
    created = False
    try:
        added = git(["worktree", "add", "--detach", str(tmp), PHASE4_TAG])
        if added.returncode != 0:
            raise AssertionError(f"recon:worktree-add: {added.stderr.strip()[:200]}")
        created = True
        state_path = tmp / ".openrecomp-phase4" / "STATE.md"
        state_text = state_path.read_text(encoding="utf-8")
        if "LAST_PASSED_STAGE=P4-99" not in state_text:
            raise AssertionError("recon:state-marker-missing")
        state_text = state_text.replace("LAST_PASSED_STAGE=P4-99",
                                        "LAST_PASSED_STAGE=P4-91")
        state_path.write_text(state_text, encoding="utf-8", newline="\n")
        queue_path = tmp / ".openrecomp-phase4" / "STAGE_QUEUE.md"
        queue_text = queue_path.read_text(encoding="utf-8")
        if f"{P4_TERMINAL_MARKER}=PASS" not in queue_text:
            raise AssertionError("recon:queue-marker-missing")
        queue_text = queue_text.replace(f"{P4_TERMINAL_MARKER}=PASS",
                                        f"{P4_TERMINAL_MARKER}=NOT_PROVEN")
        queue_path.write_text(queue_text, encoding="utf-8", newline="\n")

        runs = []
        tests_path = tmp / ".openrecomp-phase4" / "evidence" / "P4-99" / "p4_99_tests.json"
        for _index in (1, 2):
            completed = subprocess.run(
                [sys.executable, str(tmp / "tools" / "test_phase4_final_verdict_v1.py")],
                cwd=str(tmp), capture_output=True)
            runs.append({
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "tests_sha256": sha256_bytes(tests_path.read_bytes())
                if tests_path.is_file() else "",
            })
        return {
            "raw_bytes": len(runs[0]["stdout"]),
            "stdout_sha256_raw": sha256_bytes(runs[0]["stdout"]),
            "stdout_sha256_lf": sha256_bytes(lf_normalize(runs[0]["stdout"])),
            "tests_sha256": runs[0]["tests_sha256"],
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
        check(f"control-plane:exists:{name}", (CONTROL5 / name).is_file())
    check("control-plane:evidence-dir", (CONTROL5 / "evidence").is_dir())

    state = read_text(CONTROL5 / "STATE.md")
    queue = read_text(CONTROL5 / "STAGE_QUEUE.md")
    check("control-plane:phase", re.search(r"^PHASE=5\s*$", state, re.MULTILINE) is not None)
    check("control-plane:current-stage",
          re.search(r"^CURRENT_STAGE=P5-\d\d\s*$", state, re.MULTILINE) is not None)
    check("control-plane:last-passed-stage",
          re.search(r"^LAST_PASSED_STAGE=(?:NONE|P5-\d\d)\s*$", state, re.MULTILINE) is not None)
    check("control-plane:status",
          re.search(r"^STATUS=(?:ACTIVE|COMPLETE)\s*$", state, re.MULTILINE) is not None)
    check("control-plane:baseline-tag", "BASELINE_TAG=openrecomp-phase4-pass" in state)
    check("control-plane:baseline-object", PHASE4_TAG_OBJECT in state)
    check("control-plane:baseline-commit", PHASE4_COMMIT in state)
    check("control-plane:baseline-tree", PHASE4_TREE in state)

    rows = parse_queue_rows(queue)
    by_id = {row[0]: row for row in rows}
    check("control-plane:queue-ids-frozen",
          [row[0] for row in rows] == ["P5-00"] + [item[0] for item in FROZEN_QUEUE])
    check("control-plane:queue-names-frozen",
          all(by_id.get(stage, ("", "", ""))[1] == name for stage, name in FROZEN_QUEUE))
    check("control-plane:queue-statuses-valid",
          all(row[2] in QUEUE_STATUSES for row in rows))
    check("control-plane:queue-at-most-one-active",
          sum(1 for row in rows if row[2] == "ACTIVE") <= 1)
    check("control-plane:queue-freeze-section",
          "## Queue freeze" in queue and "P5-01" in queue and "P5-99" in queue)
    complete = {row[0] for row in rows if row[2] == "COMPLETE"}
    ledger = parse_ledger_rows(state)
    check("control-plane:ledger-ids-frozen",
          [row[0] for row in ledger] == ["P5-00"] + [item[0] for item in FROZEN_QUEUE])
    check("control-plane:ledger-statuses-valid",
          all(row[1] in LEDGER_STATUSES for row in ledger))
    ledger_pass = {row[0] for row in ledger if row[1] == "PASS"}
    check("control-plane:complete-set-matches-ledger", complete == ledger_pass)
    check("control-plane:terminal-marker-present", f"{TERMINAL_MARKER}=" in queue)
    check("control-plane:compat-marker-reserved",
          f"{COMPAT_MARKER}=NOT_PROVEN" in queue
          and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
    check("control-plane:freeze-record", "QUEUE_FREEZE=FROZEN" in state)

    scope = read_text(CONTROL5 / "SCOPE.md")
    check("control-plane:scope-terminal", TERMINAL_MARKER in scope)
    check("control-plane:scope-nonclaims",
          "all NES games" in scope and "cycle accuracy" in scope
          and "Famicom Disk System" in scope)
    policy = read_text(CONTROL5 / "CONTROL_POLICY.md")
    check("control-plane:rom-policy",
          "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE" in policy and "Never commit" in policy)
    fixture_policy = read_text(CONTROL5 / "FIXTURE_POLICY.md")
    check("control-plane:fixture-policy-private",
          "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE" in fixture_policy
          and "tmnt.nes" in fixture_policy and ROM_SHA256 in fixture_policy)
    check("control-plane:fixture-policy-public",
          "Apache-2.0" in fixture_policy and "Public / audited fixture" in fixture_policy)
    check("control-plane:separated-fixtures",
          "must not become the public Phase-5 proof fixture" in fixture_policy
          and "never appears in the package" in fixture_policy)


def audit_frozen_chain() -> None:
    check("chain:phase4-tag-annotated",
          git(["cat-file", "-t", PHASE4_TAG]).stdout.strip() == "tag")
    check("chain:phase4-tag-object",
          git(["rev-parse", PHASE4_TAG]).stdout.strip() == PHASE4_TAG_OBJECT)
    check("chain:phase4-commit",
          git(["rev-parse", f"{PHASE4_TAG}^{{commit}}"]).stdout.strip() == PHASE4_COMMIT)
    check("chain:phase4-tree",
          git(["rev-parse", f"{PHASE4_TAG}^{{tree}}"]).stdout.strip() == PHASE4_TREE)
    check("chain:phase3-tag-object",
          git(["rev-parse", "openrecomp-phase3-pass"]).stdout.strip() == PHASE3_TAG_OBJECT)
    check("chain:phase3-commit",
          git(["rev-parse", "openrecomp-phase3-pass^{commit}"]).stdout.strip()
          == PHASE3_COMMIT)
    check("chain:phase3-tree",
          git(["rev-parse", "openrecomp-phase3-pass^{tree}"]).stdout.strip() == PHASE3_TREE)
    check("chain:phase2-commit",
          git(["rev-parse", "openrecomp-phase2-pass^{commit}"]).stdout.strip()
          == PHASE2_COMMIT)
    check("chain:phase1-commit",
          git(["rev-parse", "openrecomp-phase1-pass^{commit}"]).stdout.strip()
          == PHASE1_COMMIT)
    check("chain:descends",
          git(["merge-base", "--is-ancestor", PHASE4_COMMIT, "HEAD"]).returncode == 0)


def audit_phase4_verdict() -> None:
    check("verdict:gate-hash", sha256_file(ROOT / P4_99_GATE) == P4_99_GATE_SHA256)
    record_path = CONTROL4 / "evidence" / "P4-99" / "p4_99_tests.json"
    check("verdict:record-present", record_path.is_file())
    check("verdict:record-hash", sha256_file(record_path) == P4_99_RECORD_SHA256)
    record = json.loads(read_text(record_path))
    check("verdict:record-status", record["status"] == "PASS"
          and record["failure"] is None and record["tests"] == P4_99_TESTS)
    check("verdict:record-terminal",
          record["markers"]["terminal"] == f"{P4_TERMINAL_MARKER}=PASS")
    check("verdict:terminal-marker-promoted",
          f"{P4_TERMINAL_MARKER}=PASS" in read_text(CONTROL4 / "STAGE_QUEUE.md"))
    check("verdict:general-marker-never-promoted",
          f"{P4_COMPAT_MARKER}=NOT_PROVEN" in read_text(CONTROL4 / "STAGE_QUEUE.md")
          and f"{P4_COMPAT_MARKER}=NOT_PROVEN" in read_text(CONTROL4 / "STATE.md"))
    official = json.loads(read_text(CONTROL4 / "evidence" / "P4-99"
                                    / "official_runs.json"))
    check("verdict:official-runs-recorded",
          official["identical_raw"] is True and official["identical_lf"] is True
          and all(run["stdout_sha256_raw"] == P4_99_STDOUT_RAW_SHA256
                  for run in official["official_runs"]))


def audit_reconstruction() -> None:
    recon = reconstruct_p4_99_context()
    FINDINGS["p4_99_reconstruction"] = {key: value for key, value in recon.items()
                                        if key != "stdout"}
    check("recon:returncode-zero", recon["returncode_zero_both"])
    check("recon:stderr-empty", recon["stderr_empty_both"])
    check("recon:stdout-bytes", recon["raw_bytes"] == P4_99_STDOUT_BYTES)
    check("recon:stdout-raw-hash", recon["stdout_sha256_raw"] == P4_99_STDOUT_RAW_SHA256)
    check("recon:stdout-lf-hash", recon["stdout_sha256_lf"] == P4_99_STDOUT_LF_SHA256)
    check("recon:record-hash", recon["tests_sha256"] == P4_99_RECORD_SHA256)
    check("recon:identical", recon["identical_raw"] is True
          and recon["identical_stderr"] is True)
    stdout_text = recon["stdout"].decode("utf-8", errors="replace")
    check("recon:markers",
          "OPENRECOMP_P4_99=PASS" in stdout_text
          and f"OPENRECOMP_PHASE4_FINAL_VERDICT_V1=PASS tests={P4_99_TESTS}" in stdout_text
          and f"{P4_TERMINAL_MARKER}=PASS" in stdout_text)


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
    manifest = CONTROL5 / "SOURCE_SHA256SUMS.txt"
    check("source:manifest-exists", manifest.is_file())
    entries = parse_manifest(manifest)
    bad = [rel for digest, rel in entries
           if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
    check("source:manifest-verified", bool(entries) and not bad)
    FINDINGS["phase5_manifest_entries"] = len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-00 Phase-5 boundary gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-00")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}

    print("=== P5-00 Phase-5 Boundary Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("control_plane")
        audit_control_plane()

        banner("source_integrity")
        audit_source_integrity()

        banner("frozen_chain")
        audit_frozen_chain()

        banner("phase4_verdict")
        audit_phase4_verdict()

        banner("p4_99_reconstruction")
        audit_reconstruction()

        banner("rom_safety")
        audit_rom_safety()

        banner("worktree_hygiene")
        problems = worktree_hygiene_problems()
        FINDINGS["worktree_problems"] = problems
        check("hygiene:no-unexpected-paths", problems == [])

        digest_lines = [
            f"{sha256_file(CONTROL5 / name)}  .openrecomp-phase5/{name}"
            for name in CONTROL_FILES
        ]
        digest_text = "\n".join(digest_lines) + "\n"
        (EVIDENCE_DIR / "control_plane_manifest.txt").write_text(
            digest_text, encoding="utf-8", newline="\n")
        FINDINGS["control_plane_digest"] = sha256_bytes(digest_text.encode("utf-8"))
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
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    (EVIDENCE_DIR / "p5_00_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
