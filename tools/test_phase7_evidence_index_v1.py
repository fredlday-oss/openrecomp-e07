#!/usr/bin/env python3
"""OpenRecomp Phase-7 evidence index and compatibility matrix gate (P7-91).

Builds and verifies the complete Phase-7 evidence index, the frozen
boundaries, every stage record and the claim ledger with the frozen
vocabulary, keeping the Phase-5 NROM proof, the Phase-6 MMC1 proof, the
Phase-7 public translation/control-flow proof, the private TMNT observations
and general NES compatibility separate.

On success it emits::

    OPENRECOMP_P7_91=PASS
    OPENRECOMP_PHASE7_EVIDENCE_INDEX_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_evidence_index_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-91
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL7 = ROOT / ".openrecomp-phase7"
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src"),
              str(CONTROL7 / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p7_evidence_index_v1 as index_module  # noqa: E402

STAGE = "P7-91"
STAGE_MARKER = "OPENRECOMP_P7_91"
FEATURE_MARKER = "OPENRECOMP_PHASE7_EVIDENCE_INDEX_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_90_RECORD_REL = ".openrecomp-phase7/evidence/P7-90/p7_90_tests.json"
P7_14_GATE = "tools/test_phase7_workflow_v1.py"
MIN_EVIDENCE_FILES = 140


class ClaimScopeError(ValueError):
    """Fail-closed claim-scope error."""


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


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def canonical_text(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def verify_claim_scope(record: dict[str, Any]) -> None:
    ledger = record.get("ledger")
    if not isinstance(ledger, dict):
        raise ClaimScopeError("claim ledger is missing")
    statuses = {name: ledger.get(name, {}).get("status")
                for name in ("phase5_public_nrom", "phase6_public_mmc1",
                             "phase7_public_translation",
                             "private_tmnt_compatibility", "general_nes")}
    if statuses["phase7_public_translation"] != "PROVEN":
        raise ClaimScopeError("the bounded public Phase-7 claim is not PROVEN")
    if statuses["phase5_public_nrom"] != "PROVEN" \
            or statuses["phase6_public_mmc1"] != "PROVEN":
        raise ClaimScopeError("the frozen earlier public proofs are not PROVEN")
    if statuses["private_tmnt_compatibility"] != "UNPROVEN":
        raise ClaimScopeError("private compatibility must remain UNPROVEN")
    if statuses["general_nes"] != "UNPROVEN":
        raise ClaimScopeError("general NES compatibility must remain UNPROVEN")
    for key in ("terminal_marker", "compatibility_marker",
                "playability_marker"):
        expected = {
            "terminal_marker": f"{TERMINAL_MARKER}=NOT_PROVEN",
            "compatibility_marker": f"{COMPAT_MARKER}=NOT_PROVEN",
            "playability_marker": f"{PLAYABILITY_MARKER}=NOT_PROVEN",
        }[key]
        if record.get(key) != expected:
            raise ClaimScopeError(f"{key} was promoted")


def expect_scope_fail(label: str, record: dict[str, Any]) -> None:
    try:
        verify_claim_scope(record)
    except ClaimScopeError:
        check(f"reject:{label}", True)
        return
    raise AssertionError(f"reject:{label}: accepted")


def run_regression(script: str, extra: list[str] | None = None) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, script, *(extra or [])],
                               cwd=str(ROOT), capture_output=True)
    stdout = completed.stdout
    stderr = completed.stderr
    markers = [line for line in stdout.decode("utf-8", errors="replace").splitlines()
               if line.startswith("OPENRECOMP_")]
    return {
        "script": script,
        "returncode": completed.returncode,
        "stdout_bytes": len(stdout),
        "stdout_sha256_raw": sha256_bytes(stdout),
        "stderr_empty": not stderr,
        "markers": markers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-91 evidence index and compatibility matrix gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-91")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-91"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-91 Evidence Index and Compatibility Matrix Gate ===",
          flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        manifest = CONTROL7 / "SOURCE_SHA256SUMS.txt"
        entries = []
        for line in manifest.read_text(encoding="utf-8").strip().splitlines():
            digest, rel = line.split(" *", 1)
            entries.append((digest, rel))
        bad = [rel for digest, rel in entries
               if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
        check("source:manifest-verified", bool(entries) and not bad)

        banner("anchors")
        check("anchor:p7-90-record-pass",
              json.loads((ROOT / P7_90_RECORD_REL).read_text(
                  encoding="utf-8"))["status"] == "PASS")
        check("anchor:p6-91-claim-record",
              (ROOT / ".openrecomp-phase6" / "evidence" / "P6-91"
               / "claim_record.json").is_file())

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-91 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)

        banner("evidence_index")
        index = index_module.build_index()
        index_repeat = index_module.build_index()
        check("index:deterministic",
              canonical_text(index) == canonical_text(index_repeat))
        check("index:size",
              index["evidence_files"] >= MIN_EVIDENCE_FILES)
        independent = []
        for path in sorted((CONTROL7 / "evidence").rglob("*")):
            if path.is_file() and "P7-91" not in path.parts:
                independent.append(path.relative_to(ROOT).as_posix())
        indexed = [entry["path"] for entry in index["files"]
                   if "P7-91" not in entry["path"]]
        check("index:independent-walk", sorted(indexed) == sorted(independent))
        check("index:hashes",
              all(sha256_file(ROOT / entry["path"]) == entry["sha256"]
                  for entry in index["files"]))
        FINDINGS["evidence_files"] = index["evidence_files"]
        FINDINGS["index_digest"] = index["index_digest"]

        banner("claim_ledger")
        claim = index_module.build_claim_record(index)
        check("claim:vocabulary",
              claim["vocabulary"] == ["PROVEN", "BOUNDED", "UNPROVEN",
                                      "UNSUPPORTED", "NOT TESTED"])
        check("claim:five-sections",
              set(claim["ledger"]) == {
                  "phase5_public_nrom", "phase6_public_mmc1",
                  "phase7_public_translation",
                  "private_tmnt_compatibility", "general_nes"})
        check("claim:phase7-proven",
              claim["ledger"]["phase7_public_translation"]["status"]
              == "PROVEN"
              and claim["ledger"]["phase7_public_translation"]["proven_count"]
              == len(index_module.PHASE7_PROVEN) >= 11
              and claim["ledger"]["phase7_public_translation"]["bounded_count"]
              == len(index_module.PHASE7_BOUNDED) >= 5)
        check("claim:private-unproven",
              claim["ledger"]["private_tmnt_compatibility"]["status"]
              == "UNPROVEN"
              and claim["ledger"]["private_tmnt_compatibility"]["playability"]
              == "NOT_PROVEN"
              and len(claim["ledger"]["private_tmnt_compatibility"]
                      ["blockers"]) == 3)
        check("claim:general-unproven",
              claim["ledger"]["general_nes"]["status"] == "UNPROVEN")
        check("claim:markers",
              claim["terminal_marker"]
              == f"{TERMINAL_MARKER}=NOT_PROVEN"
              and claim["compatibility_marker"]
              == f"{COMPAT_MARKER}=NOT_PROVEN"
              and claim["playability_marker"]
              == f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        check("claim:stage-records",
              len(claim["stage_records"]) == len(index_module.STAGES)
              and all(record["status"] == "PASS"
                      for record in claim["stage_records"].values()))
        check("claim:limitations",
              len(claim["limitations"]) >= 8)
        FINDINGS["proven_count"] = len(index_module.PHASE7_PROVEN)
        FINDINGS["bounded_count"] = len(index_module.PHASE7_BOUNDED)

        banner("scope_guard")
        verify_claim_scope(claim)
        check("scope:bounded-claim-only", True)
        import copy
        promoted = copy.deepcopy(claim)
        promoted["ledger"]["general_nes"]["status"] = "PROVEN"
        expect_scope_fail("general-promotion", promoted)
        promoted = copy.deepcopy(claim)
        promoted["ledger"]["private_tmnt_compatibility"]["status"] = "PROVEN"
        expect_scope_fail("private-promotion", promoted)
        promoted = copy.deepcopy(claim)
        promoted["compatibility_marker"] = f"{COMPAT_MARKER}=PASS"
        expect_scope_fail("compat-marker-promotion", promoted)
        promoted = copy.deepcopy(claim)
        promoted["playability_marker"] = f"{PLAYABILITY_MARKER}=PASS"
        expect_scope_fail("playability-promotion", promoted)
        promoted = copy.deepcopy(claim)
        promoted["ledger"]["phase7_public_translation"]["status"] = "UNPROVEN"
        expect_scope_fail("phase7-demotion", promoted)

        banner("regressions")
        regression = run_regression(
            P7_14_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-91/regression_p7_14"])
        check("regression:p7-14:exit", regression["returncode"] == 0)
        check("regression:p7-14:stderr", regression["stderr_empty"])
        check("regression:p7-14:marker",
              any(marker == "OPENRECOMP_P7_14=PASS"
                  for marker in regression["markers"]))
        FINDINGS["regression_p7_14"] = {
            key: value for key, value in regression.items() if key != "markers"}

        banner("evidence")
        write_json("evidence_index.json", {
            key: value for key, value in index.items() if key != "files"})
        write_json("claim_record.json", claim)
        private = pathlib.Path(
            r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes")
        private_bytes = private.read_bytes() if private.is_file() else b""
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}",
                  private_bytes not in data)
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
            "playability": f"{PLAYABILITY_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for name, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / name).write_bytes(data)
    (EVIDENCE_DIR / "p7_91_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
