#!/usr/bin/env python3
"""OpenRecomp Phase-4 whole regression audit (P4-90).

Runs the complete required regression set from the audited Phase-4 tree and
checks that every frozen earlier proof boundary remains valid:

* frozen boundary identities: the annotated Phase-3 tag (object, commit,
  tree), the Phase-2 and Phase-1 tags, descent from the boundary, the root and
  Phase-3 source manifests, the P3-99 result/gate/stdout identities and the
  committed P4-00/P4-08/P4-09/P4-10 boundary records;
* the Phase-4 boundary gate (P4-00) is re-run with the documented dynamic
  frozen-boundary hygiene (all modified tracked Phase-4 paths held out and
  re-applied; committed boundary sidecars restored) and must emit its
  byte-identical official stdout;
* every Phase-4 stage gate (P4-01 .. P4-10) is re-run from the audited tree
  and must reproduce its recorded official stdout byte-for-byte with empty
  stderr;
* the Phase-1 host gates and the public-safety scan are re-run with their
  recorded stdout identities; the full Phase-1/Phase-2/Phase-3 chains are
  exercised by the P4-00 gate (which re-runs the frozen P3-99 final verdict
  including P2-99 and every Phase-3 stage gate).

It emits::

    OPENRECOMP_P4_90=PASS
    OPENRECOMP_PHASE4_WHOLE_REGRESSION_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_whole_regression_v1.py
    python tools/test_phase4_whole_regression_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-90
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

STAGE = "P4-90"
STAGE_MARKER = "OPENRECOMP_P4_90"
FEATURE_MARKER = "OPENRECOMP_PHASE4_WHOLE_REGRESSION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

PHASE3_TAG = "openrecomp-phase3-pass"
PHASE3_TAG_OBJECT = "ac31524504b1b5cc63aabcfd5132a3eb4275e8e9"
PHASE3_COMMIT = "e16e4b29b90f379615f1af97e47747cd1d531796"
PHASE3_TREE = "a940f0d84a32adaf191f7ff2bebfb24cc855cde0"
PHASE2_COMMIT = "01b1d7cba8c931fca95d041389cfb1902b7c89fe"
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

BOUNDARY_GATE = "tools/test_phase4_boundary_v1.py"
BOUNDARY_STDOUT_RAW = "953312d08eab65d72d7f80f7bc2f0d50adb6c9cb770324b5398b52803a92c5f8"
REGRESSIONS = (
    ("regression_p4_01", "tools/test_phase4_runtime_abi_v1.py",
     "OPENRECOMP_PHASE4_RUNTIME_ABI_V1=PASS tests=156",
     "81c96314335da8420b5fe72f9659ce0efcf603f82179566c4c3a218c2e4c0b6d"),
    ("regression_p4_02", "tools/test_phase4_guest_memory_v1.py",
     "OPENRECOMP_PHASE4_GUEST_MEMORY_V1=PASS tests=113",
     "5cfc58f1bea7a89b835b17086e6d9f90ec9137e2a4527e6aa30c0b11139cff6e"),
    ("regression_p4_03", "tools/test_phase4_runtime_services_v1.py",
     "OPENRECOMP_PHASE4_RUNTIME_SERVICES_V1=PASS tests=86",
     "cc2f73daa0d9a2b4cff977db5c20ec083208c9ea35f903e7a0e63af134cb013b"),
    ("regression_p4_04", "tools/test_phase4_deterministic_io_v1.py",
     "OPENRECOMP_PHASE4_DETERMINISTIC_IO_V1=PASS tests=101",
     "e55ad6cb52592d5fbaa4fdea525ba05c437b9c942ebeeaf28c13ef9e1ca49ac3"),
    ("regression_p4_05", "tools/test_phase4_platform_adapter_v1.py",
     "OPENRECOMP_PHASE4_PLATFORM_ADAPTER_V1=PASS tests=76",
     "849af7fd1f63930bdf3c8459906ce11578ea7f7224ed00423a52079df45bdde0"),
    ("regression_p4_06", "tools/test_phase4_graphics_audio_v1.py",
     "OPENRECOMP_PHASE4_GRAPHICS_AUDIO_V1=PASS tests=72",
     "d2a59e4a45513f55b58dbae2a1f7fd880a607013614b7842861f62580a4b2da1"),
    ("regression_p4_07", "tools/test_phase4_fixture_v1.py",
     "OPENRECOMP_PHASE4_FIXTURE_V1=PASS tests=49",
     "76dd4cf2a07da5ddc153822b212d4b9b21f467c03bca05811cd8d507bbb0ec14"),
    ("regression_p4_08", "tools/test_phase4_adapter_execution_v1.py",
     "OPENRECOMP_PHASE4_ADAPTER_EXECUTION_V1=PASS tests=73",
     "4449d842df0a6087d44b693aa39776b86583a0c909321f3ad1b619d8664ccded"),
    ("regression_p4_09", "tools/test_phase4_generic_runtime_proof_v1.py",
     "OPENRECOMP_PHASE4_END_TO_END_NATIVE_PROOF_V1=PASS tests=55",
     "8ab7d3fa8a7788f5a916d78c57726ed702c12851c3ed01c026bc4175ba2b291e"),
    ("regression_p4_10", "tools/test_phase4_package_regression_v1.py",
     "OPENRECOMP_PHASE4_PACKAGE_REGRESSION_V1=PASS tests=71",
     "8a9769d7019a4e15f3733c2ea697d17dfc316311d0c7b260092dbeb7f3b47ba9"),
    ("regression_phase1_host_gates", "tools/phase1_host_gates_v1.py",
     "OPENRECOMP_PHASE1_HOST_GATES_V1=PASS",
     "2a9d1bba538b91605d61c3c47d8208cc7012cdfe49042f088c409dc54729cc35"),
    ("regression_public_safety", "tools/public_safety_scan.py",
     "OPENRECOMP_PUBLIC_SAFETY=PASS",
     "ad022ff195be230e31115124d48b7f6d8ccaae58d97eab2779b8b1ad694dbb2e"),
)
BOUNDARY_SIDECARS = (
    ".openrecomp-phase4/evidence/P4-00/control_plane_manifest.txt",
    ".openrecomp-phase4/evidence/P4-00/p4_00_tests.json",
    ".openrecomp-phase4/evidence/P4-01/p4_01_tests.json",
    ".openrecomp-phase4/evidence/P4-02/p4_02_tests.json",
    ".openrecomp-phase4/evidence/P4-03/p4_03_tests.json",
    ".openrecomp-phase4/evidence/P4-04/p4_04_tests.json",
    ".openrecomp-phase4/evidence/P4-05/p4_05_tests.json",
    ".openrecomp-phase4/evidence/P4-06/p4_06_tests.json",
    ".openrecomp-phase4/evidence/P4-07/p4_07_tests.json",
    ".openrecomp-phase4/evidence/P4-08/p4_08_tests.json",
    ".openrecomp-phase4/evidence/P4-09/p4_09_tests.json",
)
BOUNDARY_RECORDS = (
    ".openrecomp-phase4/evidence/P4-00/p4_00_tests.json",
    ".openrecomp-phase4/evidence/P4-08/p4_08_tests.json",
    ".openrecomp-phase4/evidence/P4-09/p4_09_tests.json",
    ".openrecomp-phase4/evidence/P4-10/p4_10_tests.json",
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
ARTIFACTS: dict[str, bytes] = {}


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


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


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


def git(arguments: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], cwd=str(ROOT), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def head_bytes(rel: str) -> bytes:
    """Committed bytes of a path (no text decoding; binary-safe)."""
    return subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=str(ROOT),
                          capture_output=True).stdout


def audit_boundaries() -> None:
    tag_type = git(["cat-file", "-t", PHASE3_TAG])
    check("boundary:phase3-tag-annotated", tag_type.stdout.strip() == "tag")
    tag_object = git(["rev-parse", PHASE3_TAG])
    check("boundary:phase3-tag-object", tag_object.stdout.strip() == PHASE3_TAG_OBJECT)
    tag_commit = git(["rev-parse", f"{PHASE3_TAG}^{{commit}}"])
    check("boundary:phase3-commit", tag_commit.stdout.strip() == PHASE3_COMMIT)
    tag_tree = git(["rev-parse", f"{PHASE3_TAG}^{{tree}}"])
    check("boundary:phase3-tree", tag_tree.stdout.strip() == PHASE3_TREE)
    check("boundary:phase2-commit",
          git(["rev-parse", f"openrecomp-phase2-pass^{{commit}}"]).stdout.strip()
          == PHASE2_COMMIT)
    check("boundary:phase1-commit",
          git(["rev-parse", f"openrecomp-phase1-pass^{{commit}}"]).stdout.strip()
          == PHASE1_COMMIT)
    check("boundary:descends",
          git(["merge-base", "--is-ancestor", PHASE3_COMMIT, "HEAD"]).returncode == 0)
    check("boundary:root-manifest", sha256_file(ROOT / SOURCE_SUMS) == SOURCE_SUMS_SHA256)
    check("boundary:root-manifest-entries",
          len(parse_manifest(ROOT / SOURCE_SUMS)) == SOURCE_SUMS_ENTRIES)
    check("boundary:phase3-manifest", sha256_file(ROOT / P3_SUMS) == P3_SUMS_SHA256)
    check("boundary:phase3-manifest-entries",
          len(parse_manifest(ROOT / P3_SUMS)) == P3_SUMS_ENTRIES)
    check("boundary:p3-99-result", sha256_file(ROOT / P3_99_RESULT_JSON) == P3_99_RESULT_JSON_SHA256)
    check("boundary:p3-99-gate", sha256_file(ROOT / P3_99_GATE) == P3_99_GATE_SHA256)
    phase4_entries = parse_manifest(ROOT / P4_SUMS)
    bad = [rel for digest, rel in phase4_entries
           if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
    check("boundary:phase4-manifest-verified", phase4_entries and not bad)
    for relative in BOUNDARY_RECORDS:
        path = ROOT / relative
        check(f"boundary:record:{path.name}", path.is_file())
        document = json.loads(read_text(path))
        check(f"boundary:record:{path.name}:pass", document["status"] == "PASS")
        check(f"boundary:record:{path.name}:no-failure", document["failure"] is None)
    FINDINGS["boundaries"] = {
        "phase3_tag_object": PHASE3_TAG_OBJECT,
        "phase3_commit": PHASE3_COMMIT,
        "phase3_tree": PHASE3_TREE,
        "phase4_manifest_entries": len(phase4_entries),
    }


def run_gate(name: str, script: str) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, script], cwd=str(ROOT),
                               capture_output=True, timeout=7200)
    out = completed.stdout or b""
    err = completed.stderr or b""
    return {"name": name, "script": script, "returncode": completed.returncode,
            "stdout_bytes": len(out), "stdout_sha256_raw": sha256_bytes(out),
            "stderr_bytes": len(err), "stderr_empty": not err.strip(),
            "stdout_lf": out.replace(b"\r\n", b"\n").replace(b"\r", b"\n"),
            "stderr_lf": err.replace(b"\r\n", b"\n").replace(b"\r", b"\n")}


def audit_boundary_gate() -> dict[str, Any]:
    status = git(["status", "--porcelain"], timeout=300).stdout
    modified = sorted(
        line[3:].strip().replace("\\", "/") for line in status.splitlines()
        if line[:2] in (" M", "M ", "MM")
        and (line[3:].strip().startswith(".openrecomp-phase4/")
             or line[3:].strip().startswith("tools/test_phase4_")))
    staged = sorted(
        line[3:].strip().replace("\\", "/") for line in status.splitlines()
        if line[:2].startswith("A")
        and line[3:].strip().startswith(".openrecomp-phase4/"))
    check("boundary-gate:no-staged-phase4-paths", not staged)
    saved = {rel: (ROOT / rel).read_bytes() for rel in modified}
    for rel in modified + list(BOUNDARY_SIDECARS):
        (ROOT / rel).write_bytes(head_bytes(rel))
    row = run_gate("regression_p4_00", BOUNDARY_GATE)
    ARTIFACTS["regression_p4_00.txt"] = row["stdout_lf"]
    ARTIFACTS["regression_p4_00.err.txt"] = row["stderr_lf"]
    for rel in modified:
        (ROOT / rel).write_bytes(saved[rel])
    for rel in BOUNDARY_SIDECARS:
        (ROOT / rel).write_bytes(head_bytes(rel))
    check("boundary-gate:returncode", row["returncode"] == 0)
    check("boundary-gate:stderr-empty", row["stderr_empty"])
    check("boundary-gate:stdout-byte-identical",
          row["stdout_sha256_raw"] == BOUNDARY_STDOUT_RAW)
    row["held_out_modified_tracked"] = modified
    row["sidecars_restored_to_committed"] = all(
        sha256_file(ROOT / rel) == sha256_bytes(head_bytes(rel))
        for rel in BOUNDARY_SIDECARS)
    del row["stdout_lf"], row["stderr_lf"]
    return row


def audit_regressions() -> list[dict[str, Any]]:
    rows = []
    for name, script, marker, expected_stdout in REGRESSIONS:
        row = run_gate(name, script)
        check(f"{name}:returncode", row["returncode"] == 0)
        check(f"{name}:stderr-empty", row["stderr_empty"])
        stdout = row["stdout_lf"].decode("utf-8", "replace")
        check(f"{name}:marker", marker in stdout)
        check(f"{name}:stdout-byte-identical", row["stdout_sha256_raw"] == expected_stdout)
        ARTIFACTS[f"{name}.txt"] = row["stdout_lf"]
        ARTIFACTS[f"{name}.err.txt"] = row["stderr_lf"]
        del row["stdout_lf"], row["stderr_lf"]
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P4-90 whole regression gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-90")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, ARTIFACTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    ARTIFACTS = {}

    print("=== P4-90 Phase-4 Whole Regression Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("boundaries")
        audit_boundaries()
        banner("boundary_gate")
        boundary_row = audit_boundary_gate()
        banner("regressions")
        rows = audit_regressions()
        rows.append(boundary_row)
        ARTIFACTS["whole_regression.json"] = (
            json.dumps({"stage": STAGE, "regressions": rows,
                        "all_returncode_zero": all(row["returncode"] == 0 for row in rows),
                        "all_stderr_empty": all(row["stderr_empty"] for row in rows),
                        "findings": FINDINGS},
                       indent=2, sort_keys=True) + "\n").encode("utf-8")
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
    for name, payload in ARTIFACTS.items():
        (EVIDENCE_DIR / name).write_bytes(payload)
    (EVIDENCE_DIR / "p4_90_tests.json").write_bytes(
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
