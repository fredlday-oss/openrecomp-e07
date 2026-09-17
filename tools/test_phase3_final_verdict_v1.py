#!/usr/bin/env python3
"""OpenRecomp Phase-3 final verdict gate (P3-99).

P3-99 re-verifies the complete audited tree and issues the terminal Phase-3
verdict for the bounded real-ELF recompilation claim:

* source integrity: the frozen root manifest and the Phase-3 manifest;
* the frozen Phase-1/Phase-2 boundary identities (tags, commits, trees and the
  terminal P2-99 evidence hashes);
* the control-plane ledger and the completed stage records P3-00 .. P3-91;
* the P3-10 package identity and the P3-90 whole-regression record;
* the P3-91 evidence index and the explicit claim/limitation record;
* the deterministic observable equivalence record (P3-08 native observable vs
  P3-09 independent reference observable, all ten fields);
* a fresh whole-regression run of the deterministic gate set (P2-99,
  P3-00 .. P3-09, Phase-1 host gates, public safety) with byte-identical
  (LF-normalized) stdout against the recorded captures.

If and only if every check passes, the gate issues
``OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=PASS`` for that bounded claim. On any
failure it emits ``=NOT_PROVEN`` and fails closed.

``COREMARK_STATUS=NOT_PROVEN`` is preserved: the bounded proof is not general
CoreMark support and no arbitrary MIPS32, PS1, PS2 or commercial binary
compatibility is claimed.

Usage:

    python tools/test_phase3_final_verdict_v1.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
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

EVIDENCE_ROOT = ROOT / ".openrecomp-phase3" / "evidence"
CONTROL_PLANE = ROOT / ".openrecomp-phase3"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-99"

STAGE = "P3-99"
STAGE_MARKER = "OPENRECOMP_P3_99"
FEATURE_MARKER = "OPENRECOMP_PHASE3_FINAL_VERDICT_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF"

P3_SOURCE_MANIFEST = CONTROL_PLANE / "SOURCE_SHA256SUMS.txt"
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
    "tools/test_phase3_evidence_index_v1.py",
    "tools/test_phase3_final_verdict_v1.py",
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
P2_99_RESULT_SHA256 = "880d25961949b0dc9aedaca78ca60d2dac54bbffeb6fd61e63045acd6394d8df"
P2_99_STDOUT_SHA256 = "66913e5752a9e2b7e399513710b4dce05efce9a714335c3b9908c0e30ea38c28"
P2_90_CAPTURE_SHA256 = (
    "74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7"
)
FIXTURE_SHA256 = "16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669"
ELF_SIZE = 31184

PACKAGE_SHA256 = "cf9ab795b8b900b098e0c067b0694a2c16ed400ee25e134b23f045dde3a86350"
PACKAGE_FINGERPRINT = "9050a1175b5914b0c571b49b33d3b2dc280f51e16f160b1230aeed217bf94078"
PACKAGE_ENTRIES = 287
P3_90_REGRESSION_TOTAL = 13
P3_91_INDEX_FILES = 346
P3_91_LIMITATIONS = 8

EQUIVALENCE_STATE_HASH = "0x78651c29dd149ab1"
STEPS = "394997250"

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
EQUIVALENCE_JSON = "equivalence_verification.json"
REGRESSION_JSON = "whole_regression.json"
DETERMINISM = "determinism.json"
RESULT_JSON = "RESULT.json"

CLAIM_BOUNDARY = (
    "P3-99 issues the terminal Phase-3 verdict for the bounded audited claim: "
    "a legally clean, compiler-produced CoreMark MIPS32 -O1 ELF is statically "
    "recompiled to a native host executable whose deterministic observable is "
    "identical to an independently written MIPS32 reference execution, with a "
    "byte-reproducible package and whole-regression coherence. No arbitrary "
    "MIPS32, PS1, PS2, game or commercial binary compatibility is claimed and "
    "CoreMark is not a supported target."
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


def audit_chain() -> None:
    tag_type = run_capture(["git", "cat-file", "-t", PHASE2_TAG])
    check("chain:phase2-tag-annotated",
          tag_type.returncode == 0 and tag_type.stdout.strip() == b"tag")
    tag_commit = run_capture(["git", "rev-parse", f"{PHASE2_TAG}^{{commit}}"])
    check("chain:phase2-commit",
          tag_commit.returncode == 0 and tag_commit.stdout.strip().decode() == PHASE2_COMMIT)
    tag_tree = run_capture(["git", "rev-parse", f"{PHASE2_TAG}^{{tree}}"])
    check("chain:phase2-tree",
          tag_tree.returncode == 0 and tag_tree.stdout.strip().decode() == PHASE2_TREE)
    phase1 = run_capture(["git", "rev-parse", f"{PHASE1_TAG}^{{commit}}"])
    check("chain:phase1-commit",
          phase1.returncode == 0 and phase1.stdout.strip().decode() == PHASE1_COMMIT)
    ancestor = run_capture(["git", "merge-base", "--is-ancestor", PHASE2_COMMIT, "HEAD"])
    check("chain:descends", ancestor.returncode == 0)
    check("chain:p2-99-result",
          sha256_bytes((ROOT / ".openrecomp-phase2/evidence/P2-99/RESULT.json")
                       .read_bytes()) == P2_99_RESULT_SHA256)
    check("chain:p2-90-capture",
          sha256_bytes((ROOT / ".openrecomp-phase2/evidence/P2-90/p2_90_run1.txt")
                       .read_bytes()) == P2_90_CAPTURE_SHA256)

    data = (CONTROL_PLANE / "build" / "P3-01" / "candidate-a"
            / "coremark_mips32_O1.elf").read_bytes()
    check("chain:fixture-sha256", sha256_bytes(data) == FIXTURE_SHA256)
    check("chain:fixture-size", len(data) == ELF_SIZE)

    state = (CONTROL_PLANE / "STATE.md").read_text(encoding="utf-8")
    queue = (CONTROL_PLANE / "STAGE_QUEUE.md").read_text(encoding="utf-8")
    check("chain:state-current-stage", "CURRENT_STAGE=P3-99" in state)
    check("chain:state-last-passed",
          "LAST_PASSED_STAGE=P3-91" in state or "LAST_PASSED_STAGE=P3-99" in state)
    check("chain:state-coremark-not-proven", "COREMARK_STATUS=NOT_PROVEN" in state)
    check("chain:queue-terminal-reserved", TERMINAL_MARKER in queue)
    ledger = [line for line in state.splitlines()
              if line.startswith("| P3-") and "`PASS`" in line]
    check("chain:ledger-passed-stages", len(ledger) >= 12)
    check("chain:ledger-p3-99-active", any(
        line.startswith("| P3-99 ") and ("`ACTIVE`" in line or "`PASS`" in line)
        for line in state.splitlines()))


def audit_package_and_audits() -> None:
    archive = (EVIDENCE_ROOT / "P3-10" / "phase3_package_v1.zip").read_bytes()
    check("package:sha256", sha256_bytes(archive) == PACKAGE_SHA256)
    p3_10 = json.loads((EVIDENCE_ROOT / "P3-10" / "RESULT.json").read_text(encoding="utf-8"))
    check("package:fingerprint",
          p3_10["findings"]["package"]["package_fingerprint"] == PACKAGE_FINGERPRINT)
    check("package:entries", p3_10["findings"]["package"]["entry_count"] == PACKAGE_ENTRIES)
    p3_90 = json.loads((EVIDENCE_ROOT / "P3-90" / "RESULT.json").read_text(encoding="utf-8"))
    check("package:p3-90-pass", p3_90["status"] == "PASS")
    check("package:p3-90-regression",
          p3_90["findings"]["whole_regression"]["failed"] == 0
          and p3_90["findings"]["whole_regression"]["total"] == P3_90_REGRESSION_TOTAL)
    p3_91 = json.loads((EVIDENCE_ROOT / "P3-91" / "RESULT.json").read_text(encoding="utf-8"))
    check("package:p3-91-pass", p3_91["status"] == "PASS")
    check("package:p3-91-index", p3_91["findings"]["index"]["file_count"] == P3_91_INDEX_FILES)
    check("package:p3-91-limitations",
          p3_91["findings"]["claim_record"]["limitation_count"] == P3_91_LIMITATIONS)
    claim = json.loads((EVIDENCE_ROOT / "P3-91" / "claim_record.json").read_text(encoding="utf-8"))
    check("package:claim-terminal-reserved",
          claim["terminal_marker"] == f"{TERMINAL_MARKER}=NOT_PROVEN")
    check("package:claim-coremark", claim["coremark_status"] == "NOT_PROVEN")
    check("package:claim-limitations", len(claim["limitations"]) == P3_91_LIMITATIONS)
    check("package:claim-unproven", len(claim["unproven"]) >= 8)
    FINDINGS["chain_audits"] = {
        "package_sha256": PACKAGE_SHA256,
        "p3_90_regression": p3_90["findings"]["whole_regression"],
        "p3_91_index_files": p3_91["findings"]["index"]["file_count"],
        "p3_91_limitations": P3_91_LIMITATIONS,
    }


def audit_equivalence() -> None:
    native = json.loads((EVIDENCE_ROOT / "P3-08" / "native_execution.json")
                        .read_text(encoding="utf-8"))
    reference = json.loads((EVIDENCE_ROOT / "P3-09" / "reference_observable.json")
                           .read_text(encoding="utf-8"))
    equivalence = json.loads((EVIDENCE_ROOT / "P3-09" / "equivalence.json")
                             .read_text(encoding="utf-8"))
    p3_08 = json.loads((EVIDENCE_ROOT / "P3-08" / "RESULT.json").read_text(encoding="utf-8"))
    p3_09 = json.loads((EVIDENCE_ROOT / "P3-09" / "RESULT.json").read_text(encoding="utf-8"))
    check("equivalence:native-record",
          native["observable"] == p3_08["findings"]["native"]["observable"])
    check("equivalence:reference-record",
          reference["observable"] == p3_09["findings"]["reference"]["observable"])
    check("equivalence:native-fields",
          equivalence["native"] == native["observable"])
    check("equivalence:reference-fields",
          equivalence["reference"] == reference["observable"])
    check("equivalence:record", equivalence["result"] == "DETERMINISTIC_OBSERVABLE_EQUIVALENCE")
    check("equivalence:state-hash",
          equivalence["native"]["state_fnv1a64"] == EQUIVALENCE_STATE_HASH
          and equivalence["reference"]["state_fnv1a64"] == EQUIVALENCE_STATE_HASH)
    check("equivalence:steps", equivalence["native"]["steps"] == STEPS
          and equivalence["reference"]["steps"] == STEPS)
    check("equivalence:no-failure", equivalence["native"]["failed"] == "0"
          and equivalence["reference"]["failed"] == "0")
    check("equivalence:uart",
          equivalence["native"]["uart_hex"] == equivalence["reference"]["uart_hex"]
          and "Correct operation validated." in reference["uart_text"])
    payload = {
        "stage": STAGE,
        "terminal_marker": f"{TERMINAL_MARKER}=PASS",
        "equivalence": equivalence,
        "policy": (
            "the terminal verdict is issued only because the P3-08 native "
            "observable and the P3-09 independent reference observable are "
            "identical in every compared field on the audited tree"
        ),
    }
    ARTIFACTS[EQUIVALENCE_JSON] = evidence_json_bytes(payload)
    FINDINGS["equivalence"] = {
        "state_fnv1a64": EQUIVALENCE_STATE_HASH,
        "steps": STEPS,
        "fields": equivalence["fields"],
    }


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
    }
    ARTIFACTS[REGRESSION_JSON] = evidence_json_bytes(payload)
    FINDINGS["whole_regression"] = payload["summary"]


def audit_determinism() -> None:
    artifact_hashes = {name: sha256_bytes(payload) for name, payload in sorted(ARTIFACTS.items())}
    record = {
        "stage": STAGE,
        "artifact_sha256": artifact_hashes,
        "terminal_marker": f"{TERMINAL_MARKER}=PASS",
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
    parser = argparse.ArgumentParser(description="P3-99 final verdict gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-99")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, ARTIFACTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    ARTIFACTS = {}
    terminal = "NOT_PROVEN"

    print("=== P3-99 Phase-3 Final Verdict Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    evidence_files: dict[str, str] = {}
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("frozen chain")
        audit_chain()
        banner("package and completed audits")
        audit_package_and_audits()
        banner("equivalence")
        audit_equivalence()
        banner("whole regression")
        audit_whole_regression()
        banner("determinism")
        audit_determinism()
        terminal = "PASS"
        evidence_files = write_evidence()
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"
        status = "FAIL"
        terminal = "NOT_PROVEN"

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
            "terminal": f"{TERMINAL_MARKER}={terminal}",
        },
        "terminal_verdict": terminal,
        "claim_boundary": CLAIM_BOUNDARY,
        "coremark_status": "NOT_PROVEN",
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
        print(f"{TERMINAL_MARKER}=PASS")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FEATURE_MARKER}=FAIL")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
