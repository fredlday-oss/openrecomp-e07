#!/usr/bin/env python3
"""OpenRecomp Phase-5 whole regression audit gate (P5-90).

Re-verifies the frozen Phase-1/2/3/4 chain and re-runs every Phase-5 stage
gate P5-00 .. P5-12 from the audited tree, requiring each gate's stdout to be
byte-identical to its recorded official capture. Scratch evidence is used so
committed stage evidence is never modified; the one frozen Phase-4 sidecar
that a Phase-4 regression refreshes is restored immediately and recorded.

On success it emits::

    OPENRECOMP_P5_90=PASS
    OPENRECOMP_PHASE5_WHOLE_REGRESSION_V1=PASS tests=<count>
    OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
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
for entry in (str(ROOT), str(ROOT / ".openrecomp-phase5" / "src"), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

STAGE = "P5-90"
STAGE_MARKER = "OPENRECOMP_P5_90"
FEATURE_MARKER = "OPENRECOMP_PHASE5_WHOLE_REGRESSION_V1"
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
ROOT_MANIFEST_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
ROOT_MANIFEST_ENTRIES = 134
PHASE3_MANIFEST_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
PHASE3_MANIFEST_ENTRIES = 24
P3_99_RECORD_SHA256 = "c893250b539cf1e82f368c09fe848f8f695ebece17f7735713c5367a3d93c1cf"
P3_99_GATE_SHA256 = "ba5814902797d9848614e08b6bd655c00061dfb0d2dc90fec30da60382d558fa"
P4_99_RECORD_SHA256 = "f13cf89155daaf07731097a7530a642c7cbd60cc5ae231e9f602139cdcc78154"
P4_99_GATE = "tools/test_phase4_final_verdict_v1.py"
P4_99_GATE_SHA256 = "6c357c18401ebff522810e8106fdd70032a7a2774ea63ad1377351aa3ca22abd"

STAGE_GATES = (
    ("P5-00", "tools/test_phase5_boundary_v1.py"),
    ("P5-01", "tools/test_phase5_ingestion_v1.py"),
    ("P5-02", "tools/test_phase5_frontier_v1.py"),
    ("P5-03", "tools/test_phase5_semantics_v1.py"),
    ("P5-04", "tools/test_phase5_structure_v1.py"),
    ("P5-05", "tools/test_phase5_bus_v1.py"),
    ("P5-06", "tools/test_phase5_ppu_v1.py"),
    ("P5-07", "tools/test_phase5_platform_v1.py"),
    ("P5-08", "tools/test_phase5_host_emit_v1.py"),
    ("P5-09", "tools/test_phase5_native_exec_v1.py"),
    ("P5-10", "tools/test_phase5_reference_equiv_v1.py"),
    ("P5-11", "tools/test_phase5_tmnt_private_v1.py"),
    ("P5-12", "tools/test_phase5_package_v1.py"),
)
FROZEN_RESTORE = (
    ".openrecomp-phase4/evidence/P4-06/p4_06_tests.json",
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


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def git(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *arguments], cwd=str(ROOT), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def parse_manifest(path: pathlib.Path) -> list[tuple[str, str]]:
    entries = []
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        match = re.match(r"^([0-9a-f]{64}) \*(.+)$", line)
        if match is None:
            raise AssertionError(f"malformed manifest line: {line[:80]}")
        entries.append((match.group(1), match.group(2)))
    return entries


def restore_frozen() -> list[str]:
    restored = []
    for relative in FROZEN_RESTORE:
        status = git(["status", "--porcelain=v1", "--", relative]).stdout.strip()
        if status:
            git(["checkout", "HEAD", "--", relative])
            restored.append(relative)
    return restored


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-90 whole regression gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-90")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}
    scratch = ROOT / ".openrecomp-phase5" / "scratch" / "P5-90"

    print("=== P5-90 Phase-5 Whole Regression Audit Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("frozen_chain")
        check("chain:phase4-tag-annotated",
              git(["cat-file", "-t", PHASE4_TAG]).stdout.strip() == "tag")
        check("chain:phase4-tag-object",
              git(["rev-parse", PHASE4_TAG]).stdout.strip() == PHASE4_TAG_OBJECT)
        check("chain:phase4-commit",
              git(["rev-parse", f"{PHASE4_TAG}^{{commit}}"]).stdout.strip()
              == PHASE4_COMMIT)
        check("chain:phase4-tree",
              git(["rev-parse", f"{PHASE4_TAG}^{{tree}}"]).stdout.strip()
              == PHASE4_TREE)
        check("chain:phase3-tag-object",
              git(["rev-parse", "openrecomp-phase3-pass"]).stdout.strip()
              == PHASE3_TAG_OBJECT)
        check("chain:phase3-commit",
              git(["rev-parse", "openrecomp-phase3-pass^{commit}"]).stdout.strip()
              == PHASE3_COMMIT)
        check("chain:phase3-tree",
              git(["rev-parse", "openrecomp-phase3-pass^{tree}"]).stdout.strip()
              == PHASE3_TREE)
        check("chain:phase2-commit",
              git(["rev-parse", "openrecomp-phase2-pass^{commit}"]).stdout.strip()
              == PHASE2_COMMIT)
        check("chain:phase1-commit",
              git(["rev-parse", "openrecomp-phase1-pass^{commit}"]).stdout.strip()
              == PHASE1_COMMIT)
        check("chain:descends",
              git(["merge-base", "--is-ancestor", PHASE4_COMMIT, "HEAD"]).returncode == 0)

        banner("frozen_manifests")
        check("manifest:root",
              sha256_file(ROOT / "SOURCE_SHA256SUMS.txt") == ROOT_MANIFEST_SHA256
              and len(parse_manifest(ROOT / "SOURCE_SHA256SUMS.txt"))
              == ROOT_MANIFEST_ENTRIES)
        check("manifest:phase3",
              sha256_file(ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt")
              == PHASE3_MANIFEST_SHA256
              and len(parse_manifest(
                  ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt"))
              == PHASE3_MANIFEST_ENTRIES)
        phase4_entries = parse_manifest(
            ROOT / ".openrecomp-phase4" / "SOURCE_SHA256SUMS.txt")
        bad_phase4 = [rel for digest, rel in phase4_entries
                      if sha256_file(ROOT / rel) != digest]
        check("manifest:phase4-verified",
              bool(phase4_entries) and not bad_phase4)
        phase5_entries = parse_manifest(
            ROOT / ".openrecomp-phase5" / "SOURCE_SHA256SUMS.txt")
        bad_phase5 = [rel for digest, rel in phase5_entries
                      if sha256_file(ROOT / rel) != digest]
        check("manifest:phase5-verified",
              bool(phase5_entries) and not bad_phase5)
        check("record:p3-99",
              sha256_file(ROOT / ".openrecomp-phase3" / "evidence" / "P3-99"
                          / "RESULT.json") == P3_99_RECORD_SHA256
              and sha256_file(ROOT / "tools" / "test_phase3_final_verdict_v1.py")
              == P3_99_GATE_SHA256)
        check("record:p4-99",
              sha256_file(ROOT / ".openrecomp-phase4" / "evidence" / "P4-99"
                          / "p4_99_tests.json") == P4_99_RECORD_SHA256
              and sha256_file(ROOT / P4_99_GATE) == P4_99_GATE_SHA256)
        check("record:p4-terminal",
              "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=PASS"
              in (ROOT / ".openrecomp-phase4" / "STAGE_QUEUE.md").read_text(
                  encoding="utf-8"))

        banner("stage_gates")
        records = []
        for stage, script in STAGE_GATES:
            official = json.loads(
                (ROOT / ".openrecomp-phase5" / "evidence" / stage
                 / "determinism.json").read_text(encoding="utf-8"))
            expected_raw = official["runs"]["run1"]["stdout_sha256_raw"]
            evidence_dir = scratch / stage
            completed = subprocess.run(
                [sys.executable, str(ROOT / script),
                 "--evidence-dir", str(evidence_dir.relative_to(ROOT))],
                cwd=str(ROOT), capture_output=True)
            actual_raw = sha256_bytes(completed.stdout)
            markers = [line for line in completed.stdout.decode(
                "utf-8", errors="replace").splitlines()
                if line.startswith("OPENRECOMP_P5_")]
            record = {
                "stage": stage,
                "script": script,
                "returncode": completed.returncode,
                "stdout_sha256_raw": actual_raw,
                "official_stdout_sha256_raw": expected_raw,
                "stdout_matches_official": actual_raw == expected_raw,
                "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
                "stderr_empty": len(completed.stderr) == 0,
                "markers": markers,
            }
            records.append(record)
            check(f"gate:{stage}:exit", completed.returncode == 0)
            check(f"gate:{stage}:stderr", record["stderr_empty"])
            check(f"gate:{stage}:stdout-official",
                  record["stdout_matches_official"])
            if stage == "P5-06":
                restored = restore_frozen()
                record["restored_frozen_sidecars"] = restored
        FINDINGS["stage_gates"] = records

        banner("evidence_immutability")
        status = git(["status", "--porcelain=v1", "--",
                      ".openrecomp-phase5/evidence"]).stdout
        modified = [line for line in status.splitlines()
                    if line.strip() and not line.endswith("/")]
        check("immutability:no-tracked-evidence-modified",
              all(not line.startswith(" M") for line in modified))

        banner("frozen_restore")
        restored = restore_frozen()
        check("restore:frozen-clean",
              git(["status", "--porcelain=v1", "--",
                   *FROZEN_RESTORE]).stdout.strip() == "")
        FINDINGS["restored_frozen_sidecars"] = restored

        banner("evidence")
        write_json("whole_regression.json", {
            "stage": STAGE,
            "frozen": {
                "phase4_tag_object": PHASE4_TAG_OBJECT,
                "phase4_commit": PHASE4_COMMIT,
                "phase4_tree": PHASE4_TREE,
                "root_manifest_sha256": ROOT_MANIFEST_SHA256,
                "phase3_manifest_sha256": PHASE3_MANIFEST_SHA256,
                "p3_99_record_sha256": P3_99_RECORD_SHA256,
                "p4_99_record_sha256": P4_99_RECORD_SHA256,
            },
            "stage_gates": records,
            "restored_frozen_sidecars": restored,
        })
        check("hygiene:no-private-rom-in-evidence",
              all(b"2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
                  not in data for data in EVIDENCE_WRITES.values()))
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
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
    for name, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / name).write_bytes(data)
    (EVIDENCE_DIR / "p5_90_tests.json").write_text(
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
