#!/usr/bin/env python3
"""OpenRecomp Phase-3 reproducible package + whole regression gate (P3-10).

P3-10 produces the byte-reproducible package of the audited Phase-3 path and
runs the whole Phase-1/Phase-2/Phase-3 gate set together.

The deterministic gate:

* verifies source integrity: the frozen root ``SOURCE_SHA256SUMS.txt`` is
  unchanged and every entry still hashes, and the Phase-3
  ``.openrecomp-phase3/SOURCE_SHA256SUMS.txt`` manifest registers and verifies
  the Phase-3 source/gate files (grown additively to this stage's set);
* collects the tracked Phase-3 path (control plane, sources, gates, port
  files, generated host code and tracked evidence) and builds the deterministic
  package twice from the same state, requiring byte-identical archives;
* verifies the embedded manifest (membership, sizes, hashes, fingerprint) and
  the content policy (no compiled artifacts, host paths, timestamps, UUIDs or
  sensitive markers);
* runs the whole gate set (P2-99, P3-00 .. P3-09, Phase-1 host gates, public
  safety scan) and requires exit 0, empty stderr and byte-identical stdout
  against the pinned per-gate LF hashes;
* records the package, the package report, the whole-regression audit and the
  reserved terminal marker state as evidence.

On success it emits::

    OPENRECOMP_P3_10=PASS
    OPENRECOMP_PHASE3_PACKAGE_REGRESSION_V1=PASS tests=<count>

Any failed invariant fails closed and emits ``OPENRECOMP_P3_10=FAIL``.

Usage:

    python tools/test_phase3_package_regression_v1.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / ".openrecomp-phase3" / "src"
for candidate in (str(ROOT), str(SRC_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from p3_elf_image_v1 import evidence_json_bytes, sha256_bytes  # noqa: E402
from p3_package_v1 import (  # noqa: E402
    MANIFEST_NAME,
    PackageEntry,
    PackageError,
    build_package,
    content_policy_findings,
    verify_package,
)

EVIDENCE_ROOT = ROOT / ".openrecomp-phase3" / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-10"

STAGE = "P3-10"
STAGE_MARKER = "OPENRECOMP_P3_10"
FEATURE_MARKER = "OPENRECOMP_PHASE3_PACKAGE_REGRESSION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF"

P3_SOURCE_MANIFEST = ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt"
P3_SOURCE_FILES = (
    ".openrecomp-phase3/src/p3_code_frontier_v1.py",
    ".openrecomp-phase3/src/p3_decode_mips32_v1.py",
    ".openrecomp-phase3/src/p3_elf_image_v1.py",
    ".openrecomp-phase3/src/p3_host_emit_v1.py",
    ".openrecomp-phase3/src/p3_package_v1.py",
    ".openrecomp-phase3/src/p3_reference_mips32_v1.py",
    ".openrecomp-phase3/src/p3_semantics_mips32_v1.py",
    ".openrecomp-phase3/src/p3_static_data_v1.py",
    ".openrecomp-phase3/src/p3_structure_v1.py",
    ".openrecomp-phase3/src/p3_target_mips32_v1.py",
    "tools/test_phase3_boundary_v1.py",
    "tools/test_phase3_coremark_fixture_v1.py",
    "tools/test_phase3_decode_frontier_v1.py",
    "tools/test_phase3_elf_ingestion_v1.py",
    "tools/test_phase3_host_emit_v1.py",
    "tools/test_phase3_native_runtime_v1.py",
    "tools/test_phase3_package_regression_v1.py",
    "tools/test_phase3_reachable_semantics_v1.py",
    "tools/test_phase3_reference_equivalence_v1.py",
    "tools/test_phase3_static_data_v1.py",
    "tools/test_phase3_structure_v1.py",
)
ROOT_MANIFEST = ROOT / "SOURCE_SHA256SUMS.txt"
ROOT_MANIFEST_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
ROOT_MANIFEST_ENTRIES = 134

REGRESSION_GATES = (
    ("P2-99", "tools/test_phase2_final_verdict_v1.py",
     "563d33bf2cf0dc00d1f00ebb4921277064f4119640d781cfd41f8ae397a60ecf"),
    ("P3-00", "tools/test_phase3_boundary_v1.py",
     "02664e80d78ae03d66767c472fcc8a2cc65b0fb90cf2efdb3cbbf3c6b5efff7c"),
    ("P3-01", "tools/test_phase3_coremark_fixture_v1.py",
     "6560923f68cd5d3ac71a2b368557745024b10ca41646a2df290527e0f2e8395e"),
    ("P3-02", "tools/test_phase3_elf_ingestion_v1.py",
     "4fdb2e9fce920bca592e9ab2491da754c349e22d90e0ec5f9036eb59617a3f96"),
    ("P3-03", "tools/test_phase3_decode_frontier_v1.py",
     "ee1495a9aac09613f3ec155e6c41cfb60cb733a9e436020dd8df77771b82d8bf"),
    ("P3-04", "tools/test_phase3_reachable_semantics_v1.py",
     "9219922d34beeccc085fdc46eff3f81043c8ffe4aca79de9b31983792d0c4648"),
    ("P3-05", "tools/test_phase3_structure_v1.py",
     "f8948ea8ab651267d22c624bbb950fa0973c7fe82dd4f5f93606754ac60f7e39"),
    ("P3-06", "tools/test_phase3_static_data_v1.py",
     "c4a1d4ff9a0b4fc96266188c0e0422837274b2d5218d8239278c4d0c9e5521ad"),
    ("P3-07", "tools/test_phase3_host_emit_v1.py",
     "bbda74356513f41ba6baed2eb003337f4cc33bb07c623edf07ba3bd9da184061"),
    ("P3-08", "tools/test_phase3_native_runtime_v1.py",
     "50c645ac890b4e29ef0377b65cd97c7a25d633024a280e6dda22182bb6e5148b"),
    ("P3-09", "tools/test_phase3_reference_equivalence_v1.py",
     "e628f5653191d31f41d6cb67d56569d2d158abef7ed1d870ba146304b7e6f2e3"),
    ("PHASE1", "tools/phase1_host_gates_v1.py",
     "0371f7ef9bd63a81d2fced42238d0a1e6fbb1731d719f4b277e4a4dc5a11de38"),
    ("SAFETY", "tools/public_safety_scan.py",
     "0793ee2cf2ad7a19dbe2fe7f98d2e08a272db9653837c73bc9558fc33de5e5a2"),
)
PACKAGE_ROOTS = (".openrecomp-phase3/", "tools/test_phase3_")
PACKAGE_EXCLUDED_PARTS = (
    ".openrecomp-phase3/tools/",
    ".openrecomp-phase3/external/",
    ".openrecomp-phase3/build/",
    ".openrecomp-phase3/evidence/P3-10/",
)
# Records whose content is host-specific command lines (absolute interpreter or
# toolchain paths) are excluded from the package by design; their deterministic
# content is represented by the stage result records and the P3-10 regression
# audit. They remain tracked evidence in the repository.
PACKAGE_EXCLUDED_NAMES = (
    ".openrecomp-phase3/evidence/P3-01/build_reproducibility.json",
    ".openrecomp-phase3/evidence/P3-01/p3_01_tests.json",
)
PACKAGE_EXCLUDED_SUFFIX_NAMES = ("/official_runs.json", "/regression_summary.json")

SOURCE_INTEGRITY = "source_integrity.txt"
PACKAGE_REPORT = "package_report.json"
PACKAGE_ARCHIVE = "phase3_package_v1.zip"
REGRESSION_JSON = "whole_regression.json"
DETERMINISM = "determinism.json"
RESULT_JSON = "RESULT.json"

CLAIM_BOUNDARY = (
    "P3-10 proves that the tracked Phase-3 path packages into a byte-identical "
    "archive across independent builds and that the whole Phase-1/Phase-2/"
    "Phase-3 gate set passes together with byte-identical stdout. It does not "
    "by itself promote the terminal claim: the Phase-3 verdict remains "
    "NOT_PROVEN until P3-90/P3-91/P3-99 audit and issue it."
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
ARTIFACTS: dict[str, bytes] = {}
EVIDENCE_DIR = DEFAULT_EVIDENCE_DIR


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def parse_manifest(path: pathlib.Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if " *" not in line:
            raise ValueError(f"unparsable manifest line: {line[:80]}")
        digest, relative = line.split(" *", 1)
        if relative in entries:
            raise ValueError(f"duplicate manifest entry: {relative}")
        entries[relative] = digest
    return entries


def audit_source_integrity() -> None:
    check("source:root-manifest-exists", ROOT_MANIFEST.is_file())
    root_digest = sha256_bytes(ROOT_MANIFEST.read_bytes())
    check("source:root-manifest-frozen-sha256", root_digest == ROOT_MANIFEST_SHA256)
    root_entries = parse_manifest(ROOT_MANIFEST)
    check("source:root-manifest-entry-count", len(root_entries) == ROOT_MANIFEST_ENTRIES)
    check("source:root-manifest-entries-verified", not [
        relative for relative, digest in sorted(root_entries.items())
        if not (ROOT / relative).is_file()
        or sha256_bytes((ROOT / relative).read_bytes()) != digest])
    check("source:phase3-manifest-exists", P3_SOURCE_MANIFEST.is_file())
    phase3_digest = sha256_bytes(P3_SOURCE_MANIFEST.read_bytes())
    phase3_entries = parse_manifest(P3_SOURCE_MANIFEST)
    check("source:phase3-manifest-entry-set",
          tuple(sorted(phase3_entries)) == tuple(sorted(P3_SOURCE_FILES)))
    check("source:phase3-manifest-entries-verified", not [
        relative for relative, digest in sorted(phase3_entries.items())
        if not (ROOT / relative).is_file()
        or sha256_bytes((ROOT / relative).read_bytes()) != digest])
    lines = [
        f"PHASE3_SOURCE_MANIFEST={P3_SOURCE_MANIFEST.relative_to(ROOT).as_posix()}",
        f"PHASE3_SOURCE_MANIFEST_SHA256={phase3_digest}",
        f"PHASE3_SOURCE_ENTRIES={len(phase3_entries)}",
    ]
    lines += [f"{digest} *{relative}" for relative, digest in sorted(phase3_entries.items())]
    lines += [
        "PHASE3_SOURCE_INTEGRITY=PASS",
        f"ROOT_SOURCE_MANIFEST={ROOT_MANIFEST.name}",
        f"ROOT_SOURCE_MANIFEST_SHA256={root_digest}",
        f"ROOT_SOURCE_MANIFEST_ENTRIES={len(root_entries)}",
        "ROOT_SOURCE_INTEGRITY=PASS",
    ]
    ARTIFACTS[SOURCE_INTEGRITY] = ("\n".join(lines) + "\n").encode("utf-8")
    FINDINGS["source_integrity"] = {
        "root_manifest_sha256": root_digest,
        "phase3_manifest_sha256": phase3_digest,
        "phase3_manifest_entries": len(phase3_entries),
    }


def tracked_phase3_files() -> list[str]:
    raw = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"], stderr=subprocess.STDOUT)
    names = [item.decode("utf-8") for item in raw.split(b"\x00") if item]
    selected = []
    for name in names:
        if not any(name.startswith(prefix) for prefix in PACKAGE_ROOTS):
            continue
        if any(part in name for part in PACKAGE_EXCLUDED_PARTS):
            continue
        if name in PACKAGE_EXCLUDED_NAMES:
            continue
        if any(name.endswith(suffix) for suffix in PACKAGE_EXCLUDED_SUFFIX_NAMES):
            continue
        selected.append(name)
    return sorted(selected)


def collect_entries() -> tuple[PackageEntry, ...]:
    files = tracked_phase3_files()
    entries = []
    for name in files:
        path = ROOT / name
        if not path.is_file():
            raise PackageError("PACKAGE_FILE_MISSING", name)
        entries.append(PackageEntry(name, path.read_bytes()))
    return tuple(entries)


def audit_package() -> None:
    entries = collect_entries()
    check("package:has-control-plane", any(
        entry.name == ".openrecomp-phase3/CONTROL_POLICY.md" for entry in entries))
    check("package:has-generated-host-code", any(
        entry.name == ".openrecomp-phase3/evidence/P3-07/coremark_program.c"
        for entry in entries) and any(
        entry.name == ".openrecomp-phase3/evidence/P3-07/coremark_support.c"
        for entry in entries))
    check("package:has-equivalence-record", any(
        entry.name == ".openrecomp-phase3/evidence/P3-09/equivalence.json"
        for entry in entries))
    check("package:has-native-record", any(
        entry.name == ".openrecomp-phase3/evidence/P3-08/native_execution.json"
        for entry in entries))
    findings = content_policy_findings(entries)
    check("package:content-policy", not findings)

    first = build_package(entries, extra={
        "stage": STAGE,
        "phase": 3,
        "audited_fixture_sha256": (
            "16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669"),
        "terminal_marker": f"{TERMINAL_MARKER}=NOT_PROVEN",
    })
    second = build_package(entries, extra={
        "stage": STAGE,
        "phase": 3,
        "audited_fixture_sha256": (
            "16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669"),
        "terminal_marker": f"{TERMINAL_MARKER}=NOT_PROVEN",
    })
    check("package:reproducible", first.archive == second.archive)
    check("package:fingerprint-stable", first.fingerprint == second.fingerprint)
    manifest = verify_package(first.archive)
    check("package:manifest-verified", manifest["package_fingerprint"] == first.fingerprint)
    check("package:entry-count", manifest["entry_count"] == first.entry_count)
    check("package:manifest-name", MANIFEST_NAME not in {
        item["name"] for item in manifest["entries"]})

    payload = {
        "stage": STAGE,
        "archive": PACKAGE_ARCHIVE,
        "archive_sha256": sha256_bytes(first.archive),
        "archive_bytes": len(first.archive),
        "package_fingerprint": first.fingerprint,
        "entry_count": first.entry_count,
        "total_bytes": first.total_bytes,
        "reproducible": True,
        "manifest": manifest,
        "policy": (
            "the package contains the tracked Phase-3 path at gate run time: "
            "control plane, sources, gates, port files, generated host code and "
            "tracked evidence; the toolchain, external CoreMark sources, build "
            "roots and the host-specific run/build command records "
            "(official_runs.json, regression_summary.json, "
            "P3-01 build_reproducibility.json and p3_01_tests.json) are excluded "
            "by design"
        ),
    }
    ARTIFACTS[PACKAGE_REPORT] = evidence_json_bytes(payload)
    ARTIFACTS[PACKAGE_ARCHIVE] = first.archive
    FINDINGS["package"] = {
        "archive_sha256": payload["archive_sha256"],
        "archive_bytes": payload["archive_bytes"],
        "package_fingerprint": first.fingerprint,
        "entry_count": first.entry_count,
        "total_bytes": first.total_bytes,
    }


def audit_whole_regression() -> None:
    rows = []
    for label, gate, expected_lf in REGRESSION_GATES:
        print(f"running {label}: {gate}", flush=True)
        completed = subprocess.run(
            [sys.executable, gate], cwd=str(ROOT), capture_output=True, timeout=7200)
        stdout = completed.stdout or b""
        stderr = completed.stderr or b""
        lf = stdout.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        actual_lf = hashlib.sha256(lf).hexdigest()
        rows.append({
            "stage": label,
            "gate": gate,
            "returncode": completed.returncode,
            "stderr_empty": not stderr.strip(),
            "stdout_sha256_lf": actual_lf,
            "expected_stdout_sha256_lf": expected_lf,
            "stdout_bytes": len(stdout),
            "match": actual_lf == expected_lf and completed.returncode == 0
            and not stderr.strip(),
        })
    failures = [row for row in rows if not row["match"]]
    for row in failures:
        print(f"REGRESSION-FAILURE: {row['stage']} {row['gate']}", flush=True)
    check("regression:all-gates-pass", not failures)
    check("regression:gate-count", len(rows) == len(REGRESSION_GATES))
    payload = {
        "stage": STAGE,
        "gates": rows,
        "summary": {
            "total": len(rows),
            "passed": len(rows) - len(failures),
            "failed": len(failures),
        },
        "policy": (
            "every gate must exit 0 with empty stderr and stdout byte-identical "
            "(LF-normalized) to its recorded capture; P3-09 re-executes the full "
            "independent reference run as part of the audit"
        ),
    }
    ARTIFACTS[REGRESSION_JSON] = evidence_json_bytes(payload)
    FINDINGS["whole_regression"] = payload["summary"]


def audit_determinism() -> None:
    artifact_hashes = {name: sha256_bytes(payload) for name, payload in sorted(ARTIFACTS.items())}
    record = {
        "stage": STAGE,
        "artifact_sha256": artifact_hashes,
        "terminal_marker": f"{TERMINAL_MARKER}=NOT_PROVEN",
    }
    ARTIFACTS[DETERMINISM] = evidence_json_bytes(record)
    FINDINGS["determinism"] = {"artifact_count": len(artifact_hashes)}
    check("determinism:artifact-hashes-recorded", bool(artifact_hashes))


def write_evidence() -> dict[str, str]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for name, payload in sorted(ARTIFACTS.items()):
        (EVIDENCE_DIR / name).write_bytes(payload)
        hashes[name] = sha256_bytes(payload)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser(description="P3-10 package + whole regression gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-10")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, ARTIFACTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    ARTIFACTS = {}

    print("=== P3-10 Reproducible Package + Whole Regression Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    evidence_files: dict[str, str] = {}
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("package")
        audit_package()
        banner("whole regression")
        audit_whole_regression()
        banner("determinism")
        audit_determinism()
        evidence_files = write_evidence()
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"
        status = "FAIL"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
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
        "claim_boundary": CLAIM_BOUNDARY,
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "evidence_files": evidence_files,
        "failure": failure,
    }
    payload = evidence_json_bytes(result)
    (EVIDENCE_DIR / RESULT_JSON).write_bytes(payload)

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
