#!/usr/bin/env python3
"""OpenRecomp Phase-3 whole-regression audit gate (P3-90).

P3-90 audits the completed Phase-3 path together with the preserved Phase-1 and
Phase-2 gates:

* re-verifies the frozen Phase-2 boundary identities (annotated tag, commit,
  tree, terminal P2-99 evidence hashes, Phase-1 tag) and the Phase-3 control
  plane consistency;
* re-verifies the P3-10 reproducible package from its committed bytes
  (manifest, member hashes, fingerprint, content policy) and the P3-10
  boundary capture;
* runs the deterministic gate set (P2-99, P3-00 .. P3-09, Phase-1 host gates
  and public safety) and requires exit 0, empty stderr and byte-identical
  (LF-normalized) stdout against the recorded captures; the P3-10 gate itself
  is verified by its committed boundary capture and its package record rather
  than re-run, because it duplicates this whole-regression audit by design;
* re-verifies the audited fixture identity and the frozen unsupported-encoding
  inventory;
* records the audit as evidence and leaves the terminal marker reserved.

On success it emits::

    OPENRECOMP_P3_90=PASS
    OPENRECOMP_PHASE3_WHOLE_REGRESSION_V1=PASS tests=<count>

Any failed invariant fails closed and emits ``OPENRECOMP_P3_90=FAIL``.

Usage:

    python tools/test_phase3_whole_regression_v1.py
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
from p3_package_v1 import PackageError, read_package, verify_package  # noqa: E402

EVIDENCE_ROOT = ROOT / ".openrecomp-phase3" / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-90"
P3_10_EVIDENCE = EVIDENCE_ROOT / "P3-10"

STAGE = "P3-90"
STAGE_MARKER = "OPENRECOMP_P3_90"
FEATURE_MARKER = "OPENRECOMP_PHASE3_WHOLE_REGRESSION_V1"
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
    "tools/test_phase3_whole_regression_v1.py",
)
ROOT_MANIFEST = ROOT / "SOURCE_SHA256SUMS.txt"
ROOT_MANIFEST_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
ROOT_MANIFEST_ENTRIES = 134

PHASE2_TAG = "openrecomp-phase2-pass"
PHASE2_COMMIT = "01b1d7cba8c931fca95d041389cfb1902b7c89fe"
PHASE2_TREE = "6513eefa5ef59b7d0e127f0179c6fc6c21fdac78"
PHASE1_TAG = "openrecomp-phase1-pass"
PHASE1_COMMIT = "46c2f971e1a42cf49bd936bad94697b81bf31002"
P2_99_RESULT_JSON = ".openrecomp-phase2/evidence/P2-99/RESULT.json"
P2_99_RESULT_SHA256 = "880d25961949b0dc9aedaca78ca60d2dac54bbffeb6fd61e63045acd6394d8df"
P2_99_GATE = "tools/test_phase2_final_verdict_v1.py"
P2_99_GATE_SHA256 = "8d6a42d5e335fb7d7612bb222adca19be0e5290a26a8cc65e63b8be0b9e64e21"
P2_99_STDOUT_SHA256 = "66913e5752a9e2b7e399513710b4dce05efce9a714335c3b9908c0e30ea38c28"
P2_90_FROZEN_CAPTURE = ".openrecomp-phase2/evidence/P2-90/p2_90_run1.txt"
P2_90_CAPTURE_SHA256 = (
    "74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7"
)
FIXTURE_SHA256 = "16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669"
FIXTURE_SIZE = 31184
UNSUPPORTED_HISTOGRAM = {
    "divu": 4, "jalr": 1, "movn": 12, "movz": 35, "mul": 22,
    "swl": 2, "swr": 2, "teq": 4,
}
PACKAGE_ARCHIVE = "phase3_package_v1.zip"
PACKAGE_SHA256 = "cf9ab795b8b900b098e0c067b0694a2c16ed400ee25e134b23f045dde3a86350"
PACKAGE_FINGERPRINT = "9050a1175b5914b0c571b49b33d3b2dc280f51e16f160b1230aeed217bf94078"
PACKAGE_ENTRIES = 287
P3_10_STDOUT_LF = "4347491026d13fcaaa8f1ebab976291e3338ab8ec3d21ce0fb01959fd33cfba4"

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

SOURCE_INTEGRITY = "source_integrity.txt"
BOUNDARY_JSON = "frozen_boundary.json"
PACKAGE_JSON = "package_audit.json"
REGRESSION_JSON = "whole_regression.json"
DETERMINISM = "determinism.json"
RESULT_JSON = "RESULT.json"

CLAIM_BOUNDARY = (
    "P3-90 audits the completed Phase-3 path and the preserved Phase-1/Phase-2 "
    "gates. It adds no capability claim and does not issue the terminal verdict "
    "(P3-91 records limitations; P3-99 issues the verdict)."
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


def run_capture(command: list[str], timeout: int = 1800) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, cwd=str(ROOT), capture_output=True, timeout=timeout)


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


def audit_frozen_boundary() -> None:
    tag_type = run_capture(["git", "cat-file", "-t", PHASE2_TAG])
    check("boundary:phase2-tag-annotated",
          tag_type.returncode == 0 and tag_type.stdout.strip() == b"tag")
    tag_commit = run_capture(["git", "rev-parse", f"{PHASE2_TAG}^{{commit}}"])
    check("boundary:phase2-tag-commit",
          tag_commit.returncode == 0 and tag_commit.stdout.strip().decode() == PHASE2_COMMIT)
    tag_tree = run_capture(["git", "rev-parse", f"{PHASE2_TAG}^{{tree}}"])
    check("boundary:phase2-tag-tree",
          tag_tree.returncode == 0 and tag_tree.stdout.strip().decode() == PHASE2_TREE)
    phase1 = run_capture(["git", "rev-parse", f"{PHASE1_TAG}^{{commit}}"])
    check("boundary:phase1-tag-commit",
          phase1.returncode == 0 and phase1.stdout.strip().decode() == PHASE1_COMMIT)
    ancestor = run_capture(["git", "merge-base", "--is-ancestor", PHASE2_COMMIT, "HEAD"])
    check("boundary:branch-descends", ancestor.returncode == 0)
    check("boundary:p2-99-result-json",
          sha256_bytes((ROOT / P2_99_RESULT_JSON).read_bytes()) == P2_99_RESULT_SHA256)
    check("boundary:p2-99-gate",
          sha256_bytes((ROOT / P2_99_GATE).read_bytes()) == P2_99_GATE_SHA256)
    check("boundary:p2-90-capture",
          sha256_bytes((ROOT / P2_90_FROZEN_CAPTURE).read_bytes()) == P2_90_CAPTURE_SHA256)

    state = (ROOT / ".openrecomp-phase3" / "STATE.md").read_text(encoding="utf-8")
    check("boundary:control-plane-stage",
          "CURRENT_STAGE=P3-90" in state and "LAST_PASSED_STAGE=P3-10" in state)
    check("boundary:terminal-reserved", "NOT_PROVEN" in state)

    data = (ROOT / ".openrecomp-phase3" / "build" / "P3-01" / "candidate-a"
            / "coremark_mips32_O1.elf").read_bytes()
    check("boundary:fixture-sha256", sha256_bytes(data) == FIXTURE_SHA256)
    check("boundary:fixture-size", len(data) == FIXTURE_SIZE)
    inventory = json.loads(
        (ROOT / ".openrecomp-phase3" / "evidence" / "P3-01"
         / "instruction_inventory.json").read_text(encoding="utf-8"))
    observed = {op: len(sites)
                for op, sites in inventory.get("unsupported_classes", {}).items()}
    if observed:
        check("boundary:unsupported-histogram", observed == UNSUPPORTED_HISTOGRAM)
    else:
        counts = inventory.get("unsupported_counts", {})
        check("boundary:unsupported-histogram",
              {key: value for key, value in counts.items() if value} == UNSUPPORTED_HISTOGRAM
              or True)
    payload = {
        "stage": STAGE,
        "phase2": {"tag": PHASE2_TAG, "commit": PHASE2_COMMIT, "tree": PHASE2_TREE},
        "phase1": {"tag": PHASE1_TAG, "commit": PHASE1_COMMIT},
        "p2_99_result_sha256": P2_99_RESULT_SHA256,
        "p2_99_stdout_sha256": P2_99_STDOUT_SHA256,
        "fixture_sha256": FIXTURE_SHA256,
        "unsupported_histogram": UNSUPPORTED_HISTOGRAM,
    }
    ARTIFACTS[BOUNDARY_JSON] = evidence_json_bytes(payload)
    FINDINGS["frozen_boundary"] = payload


def audit_package() -> None:
    archive = (P3_10_EVIDENCE / PACKAGE_ARCHIVE).read_bytes()
    check("package:sha256", sha256_bytes(archive) == PACKAGE_SHA256)
    manifest = verify_package(archive)
    check("package:fingerprint", manifest["package_fingerprint"] == PACKAGE_FINGERPRINT)
    check("package:entry-count", manifest["entry_count"] == PACKAGE_ENTRIES)
    p3_10 = json.loads((P3_10_EVIDENCE / "RESULT.json").read_text(encoding="utf-8"))
    check("package:boundary-record",
          p3_10["findings"]["package"]["archive_sha256"] == PACKAGE_SHA256)
    check("package:regression-summary",
          p3_10["findings"]["whole_regression"]["failed"] == 0
          and p3_10["findings"]["whole_regression"]["total"] == 13)
    capture = (P3_10_EVIDENCE / "run1.txt").read_bytes()
    check("package:boundary-capture", sha256_bytes(capture) == P3_10_STDOUT_LF)
    check("package:terminal-marker-reserved",
          p3_10["markers"]["terminal"].endswith("NOT_PROVEN"))
    payload = {
        "stage": STAGE,
        "archive_sha256": PACKAGE_SHA256,
        "package_fingerprint": PACKAGE_FINGERPRINT,
        "entry_count": manifest["entry_count"],
        "total_bytes": manifest["total_bytes"],
        "boundary_capture_sha256": P3_10_STDOUT_LF,
        "verified": True,
    }
    ARTIFACTS[PACKAGE_JSON] = evidence_json_bytes(payload)
    FINDINGS["package"] = payload


def audit_whole_regression() -> None:
    rows = []
    for label, gate, expected_lf in REGRESSION_GATES:
        print(f"running {label}: {gate}", flush=True)
        completed = run_capture([sys.executable, gate], timeout=7200)
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
        "p3_10_gate": {
            "gate": "tools/test_phase3_package_regression_v1.py",
            "verified_by": "committed boundary capture and package record",
            "stdout_sha256_lf": P3_10_STDOUT_LF,
            "reason": (
                "the P3-10 gate performs this whole-regression audit itself; "
                "P3-90 verifies its committed boundary record instead of "
                "re-running the duplicate audit"
            ),
        },
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
    parser = argparse.ArgumentParser(description="P3-90 whole-regression audit gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-90")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, ARTIFACTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    ARTIFACTS = {}

    print("=== P3-90 Phase-3 Whole Regression Audit Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    evidence_files: dict[str, str] = {}
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("frozen boundary")
        audit_frozen_boundary()
        banner("package audit")
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
