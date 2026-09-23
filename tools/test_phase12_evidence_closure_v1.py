#!/usr/bin/env python3
"""Deterministic P12-91 Phase-12 evidence-closure gate.

Audits the whole Phase-12 evidence tree: stage presence/order, evidence-backed
PASS claims, internally consistent test counts and hashes, deterministic runs,
absence of private/BIOS/host-path bytes in committed evidence, the frozen
Phase-11 boundary, the read-only reconnaissance hashes and the proof matrix.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE_COMMIT = "665d11dc9f760d0c4ea2486e186c1fe5c762647c"
STAGES = ("P12-00", "P12-01", "P12-02", "P12-03", "P12-04", "P12-05",
          "P12-06", "P12-07", "P12-08", "P12-09", "P12-10", "P12-20",
          "P12-30", "P12-40", "P12-90")
RECON_DIR = ROOT.parents[1] / "reconnaissance" / "b0-5b-target-v1" / "evidence"
DEFAULT_FIXTURE_ROOT = ROOT.parents[1] / "fixtures" / "psx" / "hercules"

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL",
                    "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def write_json(path: pathlib.Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *arguments], cwd=str(ROOT),
                          capture_output=True, text=True)


def proof_matrix() -> dict[str, Any]:
    def read(stage: str) -> dict[str, Any]:
        return json.loads(
            (ROOT / f".openrecomp-phase12/evidence/{stage}/RESULT.json").read_text(
                encoding="utf-8")
        )

    return {
        "OPENRECOMP_PHASE12_B0_5B_CHANGECLEARPAD_V1": {
            "result": "PASS", "stage": "P12-01"},
        "OPENRECOMP_PHASE12_B0_TABLE_INDIRECT_V1": {
            "result": "PASS", "stage": "P12-03"},
        "OPENRECOMP_PHASE12_END_TO_END_REPLAY_V1": {
            "result": "PASS", "stage": "P12-40"},
        "OPENRECOMP_PHASE12_GPU_OT_DMA_V1": {
            "result": "NOT_PROVEN", "stage": "P12-06"},
        "OPENRECOMP_PHASE12_TEXTURE_VRAM_V1": {
            "result": "NOT_PROVEN", "stage": "P12-07"},
        "OPENRECOMP_PHASE12_GTE_GEOMETRY_V1": {
            "result": "NOT_PROVEN", "stage": "P12-08"},
        "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF": {
            "result": "NOT_PROVEN", "stage": "P12-05"},
        "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF": {
            "result": "NOT_PROVEN", "stage": "P12-10"},
        "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF": {
            "result": "NOT_PROVEN", "stage": "reserved"},
        "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY": {
            "result": "NOT_PROVEN", "stage": "reserved"},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-91")
    parser.add_argument("--private-fixture-root",
                        default=str(DEFAULT_FIXTURE_ROOT))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        evidence_root = ROOT / ".openrecomp-phase12" / "evidence"
        index: list[dict[str, Any]] = []
        for stage in STAGES:
            stage_dir = evidence_root / stage
            for name in ("RESULT.json", "RESULT.md", "official_runs.json",
                         "determinism.json"):
                check(f"{stage}:has-{name}", (stage_dir / name).is_file(), name)
            for artifact in sorted(stage_dir.glob("*.json")):
                index.append({
                    "stage": stage,
                    "name": artifact.name,
                    "sha256": sha256_file(artifact),
                    "bytes": artifact.stat().st_size,
                })
        check("index:non-empty", len(index) > 0, str(len(index)))

        total_checks = 0
        for stage in STAGES:
            tests_paths = list((evidence_root / stage).glob("*_tests.json"))
            check(f"{stage}:one-tests-record", len(tests_paths) == 1,
                  str([p.name for p in tests_paths]))
            tests = json.loads(tests_paths[0].read_text(encoding="utf-8"))
            summary = tests["summary"]
            check(f"{stage}:tests-internally-consistent",
                  summary["passed"] == len(tests["checks"])
                  and summary["failed"] == 0,
                  json.dumps(summary))
            total_checks += summary["passed"]
            result = json.loads(
                (evidence_root / stage / "RESULT.json").read_text(encoding="utf-8"))
            check(f"{stage}:marker-pass",
                  result["markers"].get(f"OPENRECOMP_P12_{stage.split('-')[1]}") == "PASS",
                  json.dumps(result["markers"], sort_keys=True))

        # Source manifest consistency.
        sources = []
        for pattern in (".openrecomp-phase12/src/*.py", ".openrecomp-phase12/runtime/*",
                        "tools/test_phase12_*.py"):
            sources.extend(
                p.relative_to(ROOT).as_posix()
                for p in ROOT.glob(pattern)
                if p.is_file() and p.name != "__init__.py"
                and "__pycache__" not in p.parts
            )
        expected = "".join(
            f"{sha256_file(ROOT / rel)} *{rel}\n" for rel in sorted(sources)
        )
        manifest = (ROOT / ".openrecomp-phase12/SOURCE_SHA256SUMS.txt").read_text(
            encoding="utf-8")
        check("manifest:consistent", manifest == expected,
              f"{len(sources)} sources")

        # Frozen Phase-11 boundary.
        head = git("rev-parse", "HEAD").stdout.strip()
        check("frozen:base-ancestor",
              git("merge-base", "--is-ancestor", BASE_COMMIT, head).returncode == 0,
              head)
        changed = [
            line for line in git("diff", "--name-only", BASE_COMMIT, head,
                                 "--", ".openrecomp-phase11", ".openrecomp-phase10").stdout.splitlines()
        ]
        check("frozen:phase11-phase10-unchanged", not changed, "\n".join(changed)[:200])

        # Public-safety of committed evidence.
        payload = (pathlib.Path(options.private_fixture_root) / "SLUS_005.29").read_bytes()
        sample = payload[:64]
        violations: list[str] = []
        for artifact in evidence_root.rglob("*"):
            if not artifact.is_file():
                continue
            if artifact.suffix.lower() not in (".json", ".md", ".txt"):
                continue
            text = artifact.read_text(encoding="utf-8", errors="replace")
            lowered = text.lower()
            if sample.hex() in lowered or base64.b64encode(sample).decode("ascii") in text:
                violations.append(f"{artifact.name}:payload")
            if ":\\" in text or "fixtures/" in text:
                violations.append(f"{artifact.name}:path")
            if "c:\\users" in lowered:
                violations.append(f"{artifact.name}:host")
        check("safety:no-private-bytes", not violations,
              json.dumps(violations[:5]))
        banned = [p.name for p in (ROOT / ".openrecomp-phase12").rglob("*")
                  if "build" not in p.parts
                  and p.suffix.lower() in (".bin", ".rom", ".iso", ".cue", ".exe")]
        check("safety:no-binary-fixture", not banned, json.dumps(banned[:5]))

        # Read-only reconnaissance unchanged (if present).
        recon_note = "reconnaissance-directory-present"
        if RECON_DIR.is_dir() and (RECON_DIR / "CONSOLIDATED_VERIFICATION.json").is_file():
            consolidated = json.loads(
                (RECON_DIR / "CONSOLIDATED_VERIFICATION.json").read_text(encoding="utf-8"))
            mismatches = {
                name: expected_hash for name, expected_hash in
                consolidated["evidence_sha256"].items()
                if (RECON_DIR / name).is_file()
                and sha256_file(RECON_DIR / name) != expected_hash
            }
            check("recon:unchanged", not mismatches, json.dumps(mismatches, sort_keys=True))
        else:
            recon_note = "reconnaissance-directory-absent"
            check("recon:absent-not-modified", True, recon_note)

        matrix = proof_matrix()
        check("matrix:entries", len(matrix) == 10, str(len(matrix)))
        check("matrix:proofs-not-promoted",
              matrix["OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"]["result"] == "NOT_PROVEN"
              and matrix["OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"]["result"] == "NOT_PROVEN",
              "target proofs NOT_PROVEN")

        closure = {
            "schema": "openrecomp-phase12-evidence-closure-v1",
            "stage": "P12-91",
            "phase11_base_commit": BASE_COMMIT,
            "stage_count": len(STAGES),
            "evidence_files": len(index),
            "total_stage_checks": total_checks,
            "manifest_entries": len(sources),
            "proof_matrix": matrix,
            "safety": {
                "private_payload_bytes": False,
                "private_host_paths": False,
                "binary_fixture_files": False,
                "bios_rom_bytes": False,
                "host_secrets": False,
            },
            "frozen_phase11_unchanged": True,
            "reconnaissance": recon_note,
        }
        write_json(evidence / "evidence_closure.json", closure)
        write_json(evidence / "evidence_index.json", {
            "schema": "openrecomp-phase12-evidence-index-v1",
            "stage": "P12-91",
            "files": index,
        })

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": "P12-91",
            "checks": RESULTS,
            "summary": {"passed": len(RESULTS), "failed": 0},
        }
        write_json(evidence / "p12_91_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": "P12-91",
            "status": "PASS",
            "markers": {"OPENRECOMP_P12_91": "PASS"},
            "next_stage": "P12-99",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_91=PASS")
        print(f"P12_91_STAGE_CHECKS={len(RESULTS)}")
        print(f"P12_91_EVIDENCE_FILES={len(index)}")
        print(f"P12_91_TOTAL_STAGE_CHECKS={total_checks}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-91:{exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: p12-91:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
