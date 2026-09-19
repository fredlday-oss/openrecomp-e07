#!/usr/bin/env python3
"""OpenRecomp Phase-6 whole regression audit gate (P6-90).

Re-verifies the frozen Phase-1/2/3/4/5 chain and re-runs every Phase-6 stage
gate P6-00 .. P6-13 from the audited tree, requiring each gate's stdout to be
byte-identical to its recorded official capture:

* frozen boundary identities for the Phase-1/2/3/4/5 tags (object, commit,
  tree), descent from the Phase-5 boundary, and the root/Phase-3/Phase-4/
  Phase-5/Phase-6 source manifests;
* frozen terminal verdict records: P3-99 (record + gate hashes), P4-99 (record
  + gate hashes + terminal marker), P5-99 (record + gate hashes + official
  stdout capture + terminal marker + permanent general marker);
* the Phase-1 host gate set re-run directly;
* the frozen Phase-5 whole-regression gate (P5-90) re-run in its deterministic
  reconstructed pre-P5-90 context (detached worktree at the parent of the
  P5-90 completion commit, with the frozen gate and untracked-toolchain
  junction restored), requiring byte-identical stdout to its official capture;
  that gate re-runs P5-00 .. P5-12 and, through P5-00, the P4-99 final verdict
  reconstruction, so the Phase-4 terminal audit is re-executed as well;
* every Phase-6 stage gate P6-00 .. P6-13 re-run into scratch evidence and
  required to reproduce its recorded official stdout byte-for-byte with empty
  stderr and exit 0.

Frozen historical evidence is never modified; a transient Phase-4 sidecar that
a nested Phase-4 regression may refresh is restored immediately and recorded.

On success it emits::

    OPENRECOMP_P6_90=PASS
    OPENRECOMP_PHASE6_WHOLE_REGRESSION_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_whole_regression_v1.py \
        --evidence-dir .openrecomp-phase6/evidence/P6-90
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
PHASE6 = ROOT / ".openrecomp-phase6"
for entry in (str(PHASE6 / "src"), str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

STAGE = "P6-90"
STAGE_MARKER = "OPENRECOMP_P6_90"
FEATURE_MARKER = "OPENRECOMP_PHASE6_WHOLE_REGRESSION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

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

ROOT_MANIFEST_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
ROOT_MANIFEST_ENTRIES = 134
PHASE3_MANIFEST_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
PHASE3_MANIFEST_ENTRIES = 24
P3_99_RECORD_SHA256 = "c893250b539cf1e82f368c09fe848f8f695ebece17f7735713c5367a3d93c1cf"
P3_99_GATE_SHA256 = "ba5814902797d9848614e08b6bd655c00061dfb0d2dc90fec30da60382d558fa"
P4_99_RECORD_SHA256 = "f13cf89155daaf07731097a7530a642c7cbd60cc5ae231e9f602139cdcc78154"
P4_99_GATE = "tools/test_phase4_final_verdict_v1.py"
P4_99_GATE_SHA256 = "6c357c18401ebff522810e8106fdd70032a7a2774ea63ad1377351aa3ca22abd"
P5_99_GATE = "tools/test_phase5_final_verdict_v1.py"
P5_99_GATE_SHA256 = "bc772128a91344e17d1ed00fb5e2b503aae8a0ef5e4ad9de35b7fbdfcba52143"
P5_99_RECORD_SHA256 = "b0e8267c70ab2e990ca74665d8020ba463280447dd9f5fb370f4411cfb6e72c9"
P5_99_STDOUT_BYTES = 2971
P5_99_STDOUT_RAW_SHA256 = "bc1f1e97f9f34cb06eba388a96e3879e4304e9a38a7224051d1c05aceced1591"
P5_99_TESTS = 87

P1_HOST_GATE = "tools/phase1_host_gates_v1.py"
P1_HOST_MARKER = "OPENRECOMP_PHASE1_HOST_GATES_V1=PASS"
P1_HOST_COUNTS = "OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2"

P5_90_GATE_REL = "tools/test_phase5_whole_regression_v1.py"
P5_90_CONTEXT = "ee6a98af45552b50e0e7826006ccb3e4c95c525c"
P5_90_GATE_SHA256 = "ccecffe187e077566f4bbf2047ee79d60e3e98c1d29e215e9adc7dd8b76da392"
P5_90_STDOUT_BYTES = 2039
P5_90_STDOUT_RAW_SHA256 = "e487dbc0221d813d1d1138065be422bf8440d96f64d0dee5cd94d80f123ff5c5"
P5_90_TESTS_SHA256 = "431d4e5a9766b2c3aff214146541f1346ef3d65ae8721b1cead93db298172262"

PHASE1_PUBLIC_HELPER = "tools/test_build_package_reproducibility_v1.py"
PHASE3_TOOLS_REL = ".openrecomp-phase3/tools"

STAGE_GATES = (
    ("P6-00", "tools/test_phase6_boundary_v1.py"),
    ("P6-01", "tools/test_phase6_mmc1_inventory_v1.py"),
    ("P6-02", "tools/test_phase6_mmc1_serial_v1.py"),
    ("P6-03", "tools/test_phase6_mmc1_prg_v1.py"),
    ("P6-04", "tools/test_phase6_mmc1_chr_v1.py"),
    ("P6-05", "tools/test_phase6_mmc1_variant_v1.py"),
    ("P6-06", "tools/test_phase6_mmc1_fixture_v1.py"),
    ("P6-07", "tools/test_phase6_mmc1_recompile_v1.py"),
    ("P6-08", "tools/test_phase6_mmc1_native_v1.py"),
    ("P6-09", "tools/test_phase6_mmc1_reference_equiv_v1.py"),
    ("P6-10", "tools/test_phase6_private_tmnt_v1.py"),
    ("P6-11", "tools/test_phase6_evidence_expansion_v1.py"),
    ("P6-12", "tools/test_phase6_workflow_v1.py"),
    ("P6-13", "tools/test_phase6_private_workflow_v1.py"),
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
    return (json.dumps(document, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def git(arguments: list[str], cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *arguments], cwd=str(cwd or ROOT),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=600)


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


def run_stage_gate(stage: str, script: str) -> dict[str, Any]:
    evidence = PHASE6 / "scratch" / "P6-90" / stage
    completed = subprocess.run(
        [sys.executable, str(ROOT / script),
         "--evidence-dir", evidence.relative_to(ROOT).as_posix()],
        cwd=str(ROOT), capture_output=True)
    determinism = json.loads(
        (PHASE6 / "evidence" / stage / "determinism.json").read_text(
            encoding="utf-8"))
    expected_raw = determinism["runs"]["run1"]["stdout_sha256_raw"]
    actual_raw = sha256_bytes(completed.stdout)
    markers = [line for line in
               completed.stdout.decode("utf-8", errors="replace").splitlines()
               if line.startswith("OPENRECOMP_")]
    return {
        "stage": stage,
        "script": script,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": actual_raw,
        "official_stdout_sha256_raw": expected_raw,
        "stdout_matches_official": actual_raw == expected_raw,
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
        "fail_lines": [line for line in
                       completed.stdout.decode("utf-8", errors="replace").splitlines()
                       if line.startswith("FAIL:")],
        "markers": markers,
    }


def run_p5_90_reconstruction() -> dict[str, Any]:
    if sha256_file(ROOT / P5_90_GATE_REL) != P5_90_GATE_SHA256:
        raise AssertionError("p5-90 gate identity changed")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="p6_p5_90_recon_"))
    created = False
    junction = tmp / PHASE3_TOOLS_REL
    try:
        added = git(["worktree", "add", "--detach", str(tmp), P5_90_CONTEXT])
        if added.returncode != 0:
            raise AssertionError(
                f"recon:worktree-add: {added.stderr.strip()[:200]}")
        created = True
        (tmp / P5_90_GATE_REL).write_bytes(
            (ROOT / P5_90_GATE_REL).read_bytes())
        (tmp / PHASE1_PUBLIC_HELPER).write_bytes(
            (ROOT / PHASE1_PUBLIC_HELPER).read_bytes())
        linked = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction),
             str(ROOT / PHASE3_TOOLS_REL)], capture_output=True, text=True)
        if linked.returncode != 0:
            raise AssertionError(
                f"recon:junction: {linked.stdout.strip()[:200]}")
        completed = subprocess.run(
            [sys.executable, P5_90_GATE_REL,
             "--evidence-dir", ".openrecomp-phase5/scratch/p6_90_recon"],
            cwd=str(tmp), capture_output=True)
        tests_path = (tmp / ".openrecomp-phase5" / "scratch" / "p6_90_recon"
                      / "p5_90_tests.json")
        return {
            "context_commit": P5_90_CONTEXT,
            "returncode": completed.returncode,
            "stdout_bytes": len(completed.stdout),
            "stdout_sha256_raw": sha256_bytes(completed.stdout),
            "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
            "stderr_bytes": len(completed.stderr),
            "stderr_empty": len(completed.stderr) == 0,
            "tests_sha256": (sha256_bytes(tests_path.read_bytes())
                             if tests_path.is_file() else ""),
            "markers": [line for line in completed.stdout.decode(
                "utf-8", errors="replace").splitlines()
                if line.startswith("OPENRECOMP_P5_")],
        }
    finally:
        if junction.exists():
            subprocess.run(["cmd", "/c", "rmdir", str(junction)],
                           capture_output=True)
        if created:
            removed = git(["worktree", "remove", "--force", str(tmp)])
            if removed.returncode != 0:
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
        git(["worktree", "prune"])


def run_phase1_host_gates() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / P1_HOST_GATE), "--only", "source-integrity"],
        cwd=str(ROOT), capture_output=True)
    full = subprocess.run(
        [sys.executable, str(ROOT / P1_HOST_GATE)], cwd=str(ROOT),
        capture_output=True)
    text = full.stdout.decode("utf-8", errors="replace")
    return {
        "returncode": full.returncode,
        "stdout_bytes": len(full.stdout),
        "stdout_sha256_raw": sha256_bytes(full.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(full.stdout)),
        "stderr_bytes": len(full.stderr),
        "stderr_empty": len(full.stderr) == 0,
        "marker_present": P1_HOST_MARKER in text,
        "counts_present": P1_HOST_COUNTS in text,
        "source_integrity_returncode": completed.returncode,
        "source_integrity_marker": "OPENRECOMP_PHASE1_HOST_GATES_V1=PASS"
        in completed.stdout.decode("utf-8", errors="replace"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P6-90 whole regression gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-90")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-90 Phase-6 Whole Regression Audit Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        manifest = PHASE6 / "SOURCE_SHA256SUMS.txt"
        check("source:manifest-exists", manifest.is_file())
        entries = parse_manifest(manifest)
        bad = [rel for digest, rel in entries
               if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
        check("source:manifest-verified", bool(entries) and not bad)

        banner("frozen_chain")
        check("chain:phase5-tag-annotated",
              git(["cat-file", "-t", PHASE5_TAG]).stdout.strip() == "tag")
        check("chain:phase5-tag-object",
              git(["rev-parse", PHASE5_TAG]).stdout.strip() == PHASE5_TAG_OBJECT)
        check("chain:phase5-commit",
              git(["rev-parse", f"{PHASE5_TAG}^{{commit}}"]).stdout.strip()
              == PHASE5_COMMIT)
        check("chain:phase5-tree",
              git(["rev-parse", f"{PHASE5_TAG}^{{tree}}"]).stdout.strip()
              == PHASE5_TREE)
        check("chain:phase4-tag-object",
              git(["rev-parse", "openrecomp-phase4-pass"]).stdout.strip()
              == PHASE4_TAG_OBJECT)
        check("chain:phase4-commit",
              git(["rev-parse", "openrecomp-phase4-pass^{commit}"]).stdout.strip()
              == PHASE4_COMMIT)
        check("chain:phase4-tree",
              git(["rev-parse", "openrecomp-phase4-pass^{tree}"]).stdout.strip()
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
              git(["merge-base", "--is-ancestor", PHASE5_COMMIT, "HEAD"]
                  ).returncode == 0)

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
        check("manifest:phase4-verified",
              bool(phase4_entries) and all(
                  sha256_file(ROOT / rel) == digest
                  for digest, rel in phase4_entries))
        phase5_entries = parse_manifest(
            ROOT / ".openrecomp-phase5" / "SOURCE_SHA256SUMS.txt")
        check("manifest:phase5-verified",
              bool(phase5_entries) and all(
                  sha256_file(ROOT / rel) == digest
                  for digest, rel in phase5_entries))
        FINDINGS["manifest_counts"] = {
            "root": len(parse_manifest(ROOT / "SOURCE_SHA256SUMS.txt")),
            "phase3": len(parse_manifest(
                ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt")),
            "phase4": len(phase4_entries),
            "phase5": len(phase5_entries),
            "phase6": len(entries),
        }

        banner("frozen_terminal_records")
        check("record:p3-99",
              sha256_file(ROOT / ".openrecomp-phase3" / "evidence" / "P3-99"
                          / "RESULT.json") == P3_99_RECORD_SHA256
              and sha256_file(ROOT / "tools" / "test_phase3_final_verdict_v1.py")
              == P3_99_GATE_SHA256)
        p3_record = json.loads(
            (ROOT / ".openrecomp-phase3" / "evidence" / "P3-99"
             / "RESULT.json").read_text(encoding="utf-8"))
        check("record:p3-terminal",
              p3_record["status"] == "PASS"
              and p3_record["markers"]["terminal"]
              == "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=PASS")
        check("record:p2-terminal-marker",
              "OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS"
              in (ROOT / ".openrecomp-phase2" / "STAGE_QUEUE.md").read_text(
                  encoding="utf-8"))
        check("record:p4-99",
              sha256_file(ROOT / ".openrecomp-phase4" / "evidence" / "P4-99"
                          / "p4_99_tests.json") == P4_99_RECORD_SHA256
              and sha256_file(ROOT / P4_99_GATE) == P4_99_GATE_SHA256)
        p4_record = json.loads(
            (ROOT / ".openrecomp-phase4" / "evidence" / "P4-99"
             / "p4_99_tests.json").read_text(encoding="utf-8"))
        check("record:p4-terminal",
              p4_record["status"] == "PASS"
              and p4_record["markers"]["terminal"]
              == "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=PASS")
        check("record:p5-99",
              sha256_file(ROOT / P5_99_GATE) == P5_99_GATE_SHA256
              and sha256_file(ROOT / ".openrecomp-phase5" / "evidence" / "P5-99"
                              / "p5_99_tests.json") == P5_99_RECORD_SHA256)
        p5_record = json.loads(
            (ROOT / ".openrecomp-phase5" / "evidence" / "P5-99"
             / "p5_99_tests.json").read_text(encoding="utf-8"))
        check("record:p5-terminal",
              p5_record["status"] == "PASS"
              and p5_record["tests"] == P5_99_TESTS
              and p5_record["markers"]["terminal"]
              == "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=PASS"
              and p5_record["markers"]["compatibility"]
              == "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN")
        p5_official = json.loads(
            (ROOT / ".openrecomp-phase5" / "evidence" / "P5-99"
             / "official_runs.json").read_text(encoding="utf-8"))
        check("record:p5-official-capture",
              p5_official["identical_raw"] is True
              and p5_official["identical_lf"] is True
              and all(run["stdout_sha256_raw"] == P5_99_STDOUT_RAW_SHA256
                      and run["stdout_bytes"] == P5_99_STDOUT_BYTES
                      for run in p5_official["runs"]))
        check("record:phase5-terminal-marker",
              "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=PASS"
              in (ROOT / ".openrecomp-phase5" / "STAGE_QUEUE.md").read_text(
                  encoding="utf-8"))

        banner("phase1_host_gates")
        phase1 = run_phase1_host_gates()
        check("phase1:exit", phase1["returncode"] == 0)
        check("phase1:marker", phase1["marker_present"])
        check("phase1:counts", phase1["counts_present"])
        check("phase1:source-integrity",
              phase1["source_integrity_returncode"] == 0
              and phase1["source_integrity_marker"])
        FINDINGS["phase1_host_gates"] = {
            key: value for key, value in phase1.items()}

        banner("phase5_whole_regression_reconstruction")
        p5_90 = run_p5_90_reconstruction()
        check("p5-90:returncode", p5_90["returncode"] == 0)
        check("p5-90:stderr-empty", p5_90["stderr_empty"])
        check("p5-90:stdout-bytes", p5_90["stdout_bytes"] == P5_90_STDOUT_BYTES)
        check("p5-90:stdout-official",
              p5_90["stdout_sha256_raw"] == P5_90_STDOUT_RAW_SHA256)
        check("p5-90:tests-record", p5_90["tests_sha256"] == P5_90_TESTS_SHA256)
        check("p5-90:markers",
              any("OPENRECOMP_P5_90=PASS" in marker
                  for marker in p5_90["markers"]))
        FINDINGS["p5_90_reconstruction"] = p5_90

        banner("phase6_stage_gates")
        records = []
        for stage, script in STAGE_GATES:
            record = run_stage_gate(stage, script)
            records.append(record)
            check(f"gate:{stage}:exit", record["returncode"] == 0)
            check(f"gate:{stage}:stderr", record["stderr_empty"])
            check(f"gate:{stage}:stdout-official",
                  record["stdout_matches_official"])
        FINDINGS["stage_gates"] = records

        banner("frozen_restore")
        restored = restore_frozen()
        check("restore:frozen-clean",
              git(["status", "--porcelain=v1", "--", *FROZEN_RESTORE]
                  ).stdout.strip() == "")
        FINDINGS["restored_frozen_sidecars"] = restored

        banner("evidence_immutability")
        status = git(["status", "--porcelain=v1", "--",
                      ".openrecomp-phase5/evidence",
                      ".openrecomp-phase6/evidence"]).stdout
        modified = [line for line in status.splitlines()
                    if line.strip() and not line.endswith("/")]
        check("immutability:no-tracked-evidence-modified",
              all(not line.startswith(" M") for line in modified))

        banner("evidence")
        write_json("whole_regression.json", {
            "stage": STAGE,
            "frozen": {
                "phase5_tag_object": PHASE5_TAG_OBJECT,
                "phase5_commit": PHASE5_COMMIT,
                "phase5_tree": PHASE5_TREE,
                "phase4_tag_object": PHASE4_TAG_OBJECT,
                "phase4_commit": PHASE4_COMMIT,
                "phase4_tree": PHASE4_TREE,
                "phase3_tag_object": PHASE3_TAG_OBJECT,
                "phase3_commit": PHASE3_COMMIT,
                "phase3_tree": PHASE3_TREE,
                "phase2_commit": PHASE2_COMMIT,
                "phase1_commit": PHASE1_COMMIT,
                "root_manifest_sha256": ROOT_MANIFEST_SHA256,
                "phase3_manifest_sha256": PHASE3_MANIFEST_SHA256,
                "p3_99_record_sha256": P3_99_RECORD_SHA256,
                "p4_99_record_sha256": P4_99_RECORD_SHA256,
                "p5_99_record_sha256": P5_99_RECORD_SHA256,
                "p5_99_stdout_raw_sha256": P5_99_STDOUT_RAW_SHA256,
            },
            "manifest_counts": FINDINGS["manifest_counts"],
            "phase1_host_gates": FINDINGS["phase1_host_gates"],
            "phase5_whole_regression": p5_90,
            "phase6_stage_gates": records,
            "restored_frozen_sidecars": restored,
            "coverage": {
                "phase1": "tools/phase1_host_gates_v1.py re-run directly",
                "phase2": "frozen boundary tag/commit, root manifest and the "
                          "PASS terminal verdict marker verified; Phase-2 "
                          "sources are pinned by the frozen root manifest",
                "phase3": "frozen boundary tag/commit/tree, manifest and P3-99 "
                          "terminal record verified",
                "phase4": "frozen boundary, manifest and P4-99 record verified; "
                          "the P4-99 final verdict gate is re-executed inside "
                          "the Phase-5 whole-regression reconstruction",
                "phase5": "P5-90 whole regression re-run in the reconstructed "
                          "pre-P5-90 context (P5-00 .. P5-12 re-executed)",
                "phase6": "all Phase-6 stage gates P6-00 .. P6-13 re-run with "
                          "byte-identical official stdout",
            },
        })
        check("hygiene:no-private-rom-in-evidence",
              all(b"2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
                  not in data for data in EVIDENCE_WRITES.values()))
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        restore_frozen()

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
    (EVIDENCE_DIR / "p6_90_tests.json").write_text(
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
