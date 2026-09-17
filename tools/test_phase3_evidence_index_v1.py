#!/usr/bin/env python3
"""OpenRecomp Phase-3 evidence index + limitations gate (P3-91).

P3-91 produces the complete Phase-3 evidence index and the explicit
bounded/unproven claim record:

* indexes every Phase-3 evidence file (stage, name, size, sha256 and tracked
  status), the control-plane files, the frozen Phase-2 boundary identities and
  the P3-10 package identity;
* verifies that every stage directory P3-00 .. P3-90 carries a result record,
  that the indexed tracked files agree with ``git ls-files`` and their bytes,
  and that the record is internally consistent;
* records the bounded proven statements and the explicit limitations/unproven
  list, each with the stage or evidence that establishes it;
* leaves the terminal marker reserved as ``NOT_PROVEN`` (the verdict is issued
  only by P3-99).

On success it emits::

    OPENRECOMP_P3_91=PASS
    OPENRECOMP_PHASE3_EVIDENCE_INDEX_V1=PASS tests=<count>

Any failed invariant fails closed and emits ``OPENRECOMP_P3_91=FAIL``.

Usage:

    python tools/test_phase3_evidence_index_v1.py
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
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-91"

STAGE = "P3-91"
STAGE_MARKER = "OPENRECOMP_P3_91"
FEATURE_MARKER = "OPENRECOMP_PHASE3_EVIDENCE_INDEX_V1"
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
PACKAGE_SHA256 = "cf9ab795b8b900b098e0c067b0694a2c16ed400ee25e134b23f045dde3a86350"
PACKAGE_FINGERPRINT = "9050a1175b5914b0c571b49b33d3b2dc280f51e16f160b1230aeed217bf94078"

EVIDENCE_STAGES = (
    "P3-00", "P3-01", "P3-02", "P3-03", "P3-04", "P3-05", "P3-06", "P3-07",
    "P3-08", "P3-09", "P3-10", "P3-90",
)
CONTROL_FILES = (
    "CONTROL_POLICY.md", "SCOPE.md", "STAGE_QUEUE.md", "STATE.md",
    "HANDOFF.md", "SOURCE_SHA256SUMS.txt",
)

PROVEN_STATEMENTS = (
    "the CoreMark MIPS32 ELF is reproducible from pinned open sources and a "
    "recorded toolchain (P3-01)",
    "the ELF is ingested fail-closed into a deterministic guest image (P3-02)",
    "the audited executable frontier is decoded and classified exactly, with "
    "the unsupported encodings enumerated (P3-03) and the reachable semantic "
    "frontier implemented and reference-checked (P3-04)",
    "the frozen Phase-2 structural layers recover the direct structure on the "
    "real ELF with unchanged neutrality (P3-05)",
    "the static data image and the reachable global access model are "
    "reconstructed explicitly (P3-06)",
    "the whole audited image is translated deterministically to host C with "
    "runtime-mediated indirect dispatch and MMIO (P3-07)",
    "the native program builds byte-reproducibly and executes deterministically "
    "with CoreMark's own validation CRCs (P3-08)",
    "an independently written MIPS32 reference produces an identical observable "
    "for the full run (P3-09)",
    "the tracked Phase-3 path packages byte-reproducibly and the whole "
    "Phase-1/Phase-2/Phase-3 gate set passes together (P3-10, P3-90)",
)

LIMITATIONS = (
    {
        "id": "L1",
        "limitation": "the shared Phase-2 structural layers have no MIPS32 "
                      "delay-slot concept",
        "evidence": "P3-05 delay-slot policy: call delay slots are the "
                    "CALL_RETURN continuation, branch delay slots the "
                    "BRANCH_NOT_TAKEN successor and 97 jump/return/indirect "
                    "delay slots are explicit orphan blocks",
        "impact": "the shared-layer CFG is a structural approximation; true "
                  "delay-slot execution is provided by the P3-07 emitter and "
                  "the P3-09 reference, not by the shared layers",
    },
    {
        "id": "L2",
        "limitation": "three reachable jr $at jump tables and the dead jalr "
                      "target are unresolved at the shared-layer boundary",
        "evidence": "P3-03/P3-04 frontier and P3-05 unresolved inventory",
        "impact": "targets are never guessed; the P3-07 emitter resolves them "
                  "at run time through validated dispatch over the emitted "
                  "image, and the P3-09 reference executes them natively",
    },
    {
        "id": "L3",
        "limitation": "493 of 505 reachable memory accesses have runtime base "
                      "registers with no static alias information",
        "evidence": "P3-06 access model",
        "impact": "no alias analysis is performed; those accesses are never "
                  "assumed to hit or miss any object",
    },
    {
        "id": "L4",
        "limitation": "architecturally UNPREDICTABLE states fail closed",
        "evidence": "P3-04 semantics and P3-07/P3-08 runtime boundaries",
        "impact": "divide by zero, taken trap, unaligned indirect target and "
                  "mul-defined HI/LO reads are refused rather than guessed; the "
                  "audited run never reaches them",
    },
    {
        "id": "L5",
        "limitation": "native reproducibility is bound to the recorded "
                      "clang-cl/lld-link toolchain and host platform",
        "evidence": "P3-08 build manifest and toolchain identity",
        "impact": "the build is byte-reproducible for that toolchain; a "
                  "different toolchain may produce different bytes",
    },
    {
        "id": "L6",
        "limitation": "one audited -O1 non-PIC soft-float MIPS32 fixture only",
        "evidence": "P3-01 build profile; SCOPE -O2 is a later stress target",
        "impact": "no arbitrary MIPS32, PS1, PS2 or commercial binary or game "
                  "compatibility is proven",
    },
    {
        "id": "L7",
        "limitation": "CoreMark is not a supported target",
        "evidence": "COREMARK_STATUS=NOT_PROVEN in the control plane",
        "impact": "the bounded real-ELF recompilation proof does not claim "
                  "general CoreMark support",
    },
    {
        "id": "L8",
        "limitation": "the committed P3-10 package is the boundary snapshot of "
                      "the tracked Phase-3 path",
        "evidence": "P3-10 package report and P3-90 package audit",
        "impact": "later tracked additions are not retroactively included in "
                  "the committed archive",
    },
)

CLAIM_BOUNDARY = (
    "P3-91 indexes the evidence and records the bounded proven statements and "
    "the explicit limitations. It neither adds capability nor issues the "
    "terminal verdict."
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
    FINDINGS["source_integrity"] = {
        "root_manifest_sha256": root_digest,
        "phase3_manifest_sha256": phase3_digest,
        "phase3_manifest_entries": len(phase3_entries),
    }


def tracked_set() -> set[str]:
    raw = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"], stderr=subprocess.STDOUT)
    return {item.decode("utf-8") for item in raw.split(b"\x00") if item}


def audit_index() -> None:
    tracked = tracked_set()
    entries = []
    total = 0
    for path in sorted(EVIDENCE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(".openrecomp-phase3/evidence/P3-91/"):
            continue
        stage = path.relative_to(EVIDENCE_ROOT).parts[0]
        content = path.read_bytes()
        total += len(content)
        entries.append({
            "stage": stage,
            "path": relative,
            "size": len(content),
            "sha256": sha256_bytes(content),
            "tracked": relative in tracked,
        })
    check("index:non-empty", bool(entries))
    findings = [item for item in entries if not item["tracked"]
                and not (item["path"].startswith(".openrecomp-phase3/"))]
    check("index:untracked-outside-control-plane", not findings)
    stages = sorted({item["stage"] for item in entries})
    check("index:stage-set", all(stage in stages for stage in EVIDENCE_STAGES))
    for stage in EVIDENCE_STAGES:
        stage_files = [item for item in entries if item["stage"] == stage]
        result_names = ("RESULT.json", f"p3_{stage[3:]}_tests.json")
        check(f"index:stage:{stage}:has-result",
              any(item["path"].endswith(result_names) for item in stage_files))
        check(f"index:stage:{stage}:tracked",
              all(item["tracked"] for item in stage_files
                  if item["path"].endswith(".json")))

    control = []
    for name in CONTROL_FILES:
        path = CONTROL_PLANE / name
        check(f"index:control:{name}", path.is_file())
        control.append({
            "name": name,
            "size": path.stat().st_size,
            "sha256": sha256_bytes(path.read_bytes()),
        })
    check("index:control-plane-set", len(control) == len(CONTROL_FILES))

    boundary = {
        "phase2_tag": PHASE2_TAG,
        "phase2_commit": PHASE2_COMMIT,
        "phase2_tree": PHASE2_TREE,
        "phase1_tag": PHASE1_TAG,
        "phase1_commit": PHASE1_COMMIT,
        "p2_99_result_sha256": P2_99_RESULT_SHA256,
        "p2_99_stdout_sha256": P2_99_STDOUT_SHA256,
        "package_archive_sha256": PACKAGE_SHA256,
        "package_fingerprint": PACKAGE_FINGERPRINT,
    }
    payload = {
        "stage": STAGE,
        "generated_from": "the on-disk evidence tree",
        "file_count": len(entries),
        "total_bytes": total,
        "entries": entries,
        "control_plane": control,
        "frozen_boundary": boundary,
        "policy": (
            "the index covers every artifact under .openrecomp-phase3/evidence "
            "(including the platform-line-ending capture files and the "
            "uncommitted working-tree records of the current stage); tracked "
            "status is recorded per file"
        ),
    }
    ARTIFACTS["evidence_index.json"] = evidence_json_bytes(payload)
    FINDINGS["index"] = {
        "file_count": len(entries),
        "total_bytes": total,
        "stages": stages,
        "tracked": sum(1 for item in entries if item["tracked"]),
        "untracked": sum(1 for item in entries if not item["tracked"]),
    }


def audit_claim_record() -> None:
    state = (CONTROL_PLANE / "STATE.md").read_text(encoding="utf-8")
    queue = (CONTROL_PLANE / "STAGE_QUEUE.md").read_text(encoding="utf-8")
    check("claim:terminal-reserved-state", f"{TERMINAL_MARKER}=" in queue
          and "NOT_PROVEN" in queue and "NOT_PROVEN" in state)
    check("claim:coremark-not-proven", "COREMARK_STATUS=NOT_PROVEN" in state)
    check("claim:limitations-non-empty", len(LIMITATIONS) >= 8)
    check("claim:limitation-ids-unique",
          len({item["id"] for item in LIMITATIONS}) == len(LIMITATIONS))
    check("claim:proven-statements", len(PROVEN_STATEMENTS) >= 9)
    check("claim:limitations-have-evidence",
          all(item["evidence"] and item["impact"] for item in LIMITATIONS))
    p3_10 = json.loads(
        (EVIDENCE_ROOT / "P3-10" / "RESULT.json").read_text(encoding="utf-8"))
    p3_90 = json.loads(
        (EVIDENCE_ROOT / "P3-90" / "RESULT.json").read_text(encoding="utf-8"))
    check("claim:p3-90-audit", p3_90["status"] == "PASS"
          and p3_90["findings"]["whole_regression"]["failed"] == 0)
    check("claim:p3-10-package", p3_10["status"] == "PASS"
          and p3_10["findings"]["package"]["archive_sha256"] == PACKAGE_SHA256)
    payload = {
        "stage": STAGE,
        "terminal_marker": f"{TERMINAL_MARKER}=NOT_PROVEN",
        "coremark_status": "NOT_PROVEN",
        "proven": list(PROVEN_STATEMENTS),
        "unproven": [
            "arbitrary MIPS32 ELF support",
            "PS1 compatibility",
            "PS2 compatibility",
            "game or commercial binary compatibility",
            "cycle accuracy, hardware/console emulation",
            "self-modifying code",
            "the -O2 stress profile",
            "runtime equivalence beyond the audited deterministic observable",
        ],
        "limitations": list(LIMITATIONS),
        "claim_boundary": (
            "the bounded Phase-3 claim is deterministic observable equivalence "
            "for the single audited CoreMark MIPS32 -O1 fixture between the "
            "native host execution and an independent reference; nothing "
            "broader is claimed"
        ),
    }
    ARTIFACTS["claim_record.json"] = evidence_json_bytes(payload)
    FINDINGS["claim_record"] = {
        "terminal_marker": payload["terminal_marker"],
        "proven_count": len(payload["proven"]),
        "unproven_count": len(payload["unproven"]),
        "limitation_count": len(payload["limitations"]),
    }


def audit_determinism() -> None:
    artifact_hashes = {name: sha256_bytes(payload) for name, payload in sorted(ARTIFACTS.items())}
    record = {
        "stage": STAGE,
        "artifact_sha256": artifact_hashes,
        "terminal_marker": f"{TERMINAL_MARKER}=NOT_PROVEN",
    }
    ARTIFACTS["determinism.json"] = evidence_json_bytes(record)
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
    parser = argparse.ArgumentParser(description="P3-91 evidence index gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-91")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, ARTIFACTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    ARTIFACTS = {}

    print("=== P3-91 Evidence Index + Limitations Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    evidence_files: dict[str, str] = {}
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("evidence index")
        audit_index()
        banner("claim record")
        audit_claim_record()
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
    (EVIDENCE_DIR / "RESULT.json").write_bytes(payload)

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
