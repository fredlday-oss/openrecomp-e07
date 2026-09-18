#!/usr/bin/env python3
"""OpenRecomp Phase-5 evidence index + compatibility limitations gate (P5-91).

Verifies the complete Phase-5 evidence index (every stage file with size and
sha256, control-plane hashes, frozen identities, package identity) against an
independent filesystem walk, and the claim ledger separating PROVEN /
BOUNDED / UNPROVEN / UNSUPPORTED / NOT TESTED with the public fixture,
private TMNT and general-compatibility sections kept separate.

On success it emits::

    OPENRECOMP_P5_91=PASS
    OPENRECOMP_PHASE5_EVIDENCE_INDEX_V1=PASS tests=<count>
    OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
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
for entry in (str(ROOT), str(ROOT / ".openrecomp-phase5" / "src"), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p5_evidence_index_v1 as index_module  # noqa: E402

STAGE = "P5-91"
STAGE_MARKER = "OPENRECOMP_P5_91"
FEATURE_MARKER = "OPENRECOMP_PHASE5_EVIDENCE_INDEX_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"
PRIVATE_ROM = pathlib.Path(r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes")

MIN_EVIDENCE_FILES = 150
MIN_PROVEN = 12
MIN_BOUNDED = 4
MIN_PRIVATE = 4
MIN_UNPROVEN = 7
MIN_UNSUPPORTED = 4
MIN_NOT_TESTED = 6

REGRESSIONS = (
    ("tools/test_phase5_tmnt_private_v1.py",
     ["--evidence-dir", ".openrecomp-phase5/scratch/regression_p5_91_p5_11"]),
    ("tools/test_nes_rom_v1.py", []),
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


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def canonical(document: Any) -> bytes:
    return index_module.canonical(document)


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def run_regression(script: str, extra: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / script), *extra],
        cwd=str(ROOT), capture_output=True)
    return {
        "script": script,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": sha256_bytes(completed.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-91 evidence index gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-91")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-91 Evidence Index + Compatibility Limitations Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("index")
        index_a = index_module.build_index()
        index_b = index_module.build_index()
        check("index:deterministic", canonical(index_a) == canonical(index_b))
        check("index:evidence-count",
              index_a["evidence_files"] >= MIN_EVIDENCE_FILES)
        check("index:stages", tuple(index_a["stages"]) == index_module.STAGES)

        disk_files = set()
        for stage in index_module.STAGES:
            directory = index_module.EVIDENCE_ROOT / stage
            if directory.is_dir():
                for path in directory.rglob("*"):
                    if path.is_file():
                        disk_files.add(path.relative_to(ROOT).as_posix())
        indexed = {item["path"] for item in index_a["files"]}
        check("index:complete", indexed == disk_files)
        for item in index_a["files"]:
            path = ROOT / item["path"]
            if item["size"] != path.stat().st_size or item["sha256"] != sha256_bytes(
                    path.read_bytes()):
                raise AssertionError(f"index mismatch: {item['path']}")
        check("index:hashes", True)
        control_ok = all(
            item["sha256"] == sha256_bytes((ROOT / item["path"]).read_bytes())
            for item in index_a["control_plane"])
        check("index:control-plane", control_ok)
        check("index:package",
              index_a["package"]["sha256"]
              == "447f72cc616d80fa72e3681c5acd34b00833d7e3fe3fb5bf8bf3230347cc4c13")
        manifest_ok = all(
            item["sha256"] == sha256_bytes((ROOT / item["path"]).read_bytes())
            for item in index_a["phase5_manifest"])
        check("index:phase5-manifest", manifest_ok)
        check("index:boundaries",
              index_a["boundaries"] == index_module.BOUNDARIES)

        banner("claim_ledger")
        record_a = index_module.build_claim_record()
        record_b = index_module.build_claim_record()
        check("ledger:deterministic", canonical(record_a) == canonical(record_b))
        check("ledger:proven", record_a["proven_count"] >= MIN_PROVEN)
        check("ledger:bounded", record_a["bounded_count"] >= MIN_BOUNDED)
        check("ledger:private",
              record_a["private_observation_count"] >= MIN_PRIVATE)
        check("ledger:unproven", record_a["unproven_count"] >= MIN_UNPROVEN)
        check("ledger:unsupported",
              record_a["unsupported_count"] >= MIN_UNSUPPORTED)
        check("ledger:not-tested",
              record_a["not_tested_count"] >= MIN_NOT_TESTED)
        check("ledger:general-not-proven",
              record_a["ledger"]["general_nes"]["status"] == "NOT_PROVEN"
              and record_a["generic_runtime_status"] == "NOT_PROVEN")
        check("ledger:sections-distinct",
              record_a["sections"]["public"] == "legal public fixture result"
              and record_a["sections"]["private"].startswith("private TMNT")
              and record_a["sections"]["general"] == "general NES compatibility")
        for word in ("PROVEN", "BOUNDED", "UNPROVEN", "UNSUPPORTED", "NOT TESTED"):
            if word not in canonical(record_a).decode("utf-8"):
                raise AssertionError(f"ledger vocabulary missing: {word}")
        check("ledger:vocabulary", True)
        check("ledger:private-separate",
              "public_claim" not in record_a["ledger"]["private_tmnt_observations"]
              and record_a["ledger"]["private_tmnt_observations"]["section"].startswith(
                  "private local compatibility"))

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("evidence_index.json", index_a)
        write_json("claim_record.json", record_a)
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        if PRIVATE_ROM.is_file():
            rom = PRIVATE_ROM.read_bytes()
            check("hygiene:no-private-rom-bytes",
                  all(rom not in data for data in EVIDENCE_WRITES.values()))
        check("hygiene:private-observation-recorded",
              "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
              in EVIDENCE_WRITES["claim_record.json"].decode("utf-8"))
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
        FINDINGS["indexed_files"] = index_a["evidence_files"]
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
    (EVIDENCE_DIR / "p5_91_tests.json").write_text(
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
