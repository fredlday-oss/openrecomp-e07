#!/usr/bin/env python3
"""OpenRecomp Phase-7 private TMNT frontier gate (P7-11).

Re-runs the private image through the Phase-7 machinery and records the exact
frontier delta against the frozen Phase-6 record: the classified data table at
`0xC570`, the three resolved `$E2` sites, the expanded bank-aware candidate
frontier, and the still-incomplete translation/native status. Metadata and
derived evidence only - never ROM bytes.

On success it emits::

    OPENRECOMP_P7_11=PASS
    OPENRECOMP_PHASE7_PRIVATE_FRONTIER_RUN_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_private_frontier_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-11
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

import adapters.nes6502 as nes  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p7_private_frontier_v1 as private_frontier  # noqa: E402

STAGE = "P7-11"
STAGE_MARKER = "OPENRECOMP_P7_11"
FEATURE_MARKER = "OPENRECOMP_PHASE7_PRIVATE_FRONTIER_RUN_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_10_RECORD_REL = ".openrecomp-phase7/evidence/P7-10/p7_10_tests.json"
P7_06_GATE = "tools/test_phase7_indirect_evidence_v1.py"
PRIVATE_SHA256 = (
    "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1")

REGRESSIONS = ("tools/test_nes_rom_v1.py",)

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


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def canonical_text(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_regression(script: str, extra: list[str] | None = None) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, script, *(extra or [])],
                               cwd=str(ROOT), capture_output=True)
    stdout = completed.stdout
    stderr = completed.stderr
    markers = [line for line in stdout.decode("utf-8", errors="replace").splitlines()
               if line.startswith("OPENRECOMP_")]
    return {
        "script": script,
        "command": ["python", script, *(extra or [])],
        "returncode": completed.returncode,
        "stdout_bytes": len(stdout),
        "stdout_sha256_raw": sha256_bytes(stdout),
        "stdout_sha256_lf": sha256_bytes(stdout.replace(b"\r\n", b"\n")),
        "stderr_bytes": len(stderr),
        "stderr_empty": not stderr,
        "markers": markers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-11 private TMNT frontier gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-11")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-11"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-11 Private TMNT Frontier Gate ===", flush=True)
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
        check("anchor:p7-10-record-pass",
              read_json(ROOT / P7_10_RECORD_REL)["status"] == "PASS")
        check("anchor:decoder-unchanged", len(nes.OPCODES) == 151)
        check("anchor:private-image",
              private_fixture.PRIVATE_ROM.is_file()
              and private_fixture.PRIVATE_ROM.stat().st_size == 262160
              and sha256_file(private_fixture.PRIVATE_ROM) == PRIVATE_SHA256)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-11 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)

        banner("private_frontier")
        record = private_frontier.run()
        record_repeat = private_frontier.run()
        check("private:deterministic",
              canonical_text(record) == canonical_text(record_repeat))
        check("private:identity",
              record["image_sha256"] == PRIVATE_SHA256
              and record["image_size"] == 262160
              and record["classification"]
              == "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE")
        check("private:p6-anchor",
              record["p6_frontier"]["stop_address"] == 0xC570
              and record["p6_frontier"]["candidate_instructions"] == 1250
              and record["p6_frontier"]["low_window_instructions"] == 1048
              and record["p6_frontier"]["indirect_sites"]
              == [0x86E8, 0x8956, 0x8F3C])
        check("private:bank-frontier",
              record["p7_bank_frontier"]["status"] == "BLOCKED_UNDECODABLE"
              and record["p7_bank_frontier"]["stop"]["address"] == 0xC570
              and record["p7_bank_frontier"]["stop"]["bank"] == 7
              and record["p7_bank_frontier"]["proven_instructions"] == 530
              and record["p7_bank_frontier"]["unresolved_instructions"]
              == 14027
              and record["p7_bank_frontier"]["unresolved_limited"] is True
              and len(record["p7_bank_frontier"]["code_by_bank"]) == 8)
        check("private:data-classification",
              record["classification_0xc570"]["classification"]
              == "DATA_NOT_CODE"
              and record["classification_0xc570"]["inline_table"]["entries"]
              == 6
              and record["classification_0xc570"]["inline_table"]
              ["resume_address"] == 0xC57C
              and record["classification_0xc570"]["semantics_added"] is False)
        sites = {entry["site"]: entry
                 for entry in record["indirect_evidence"]["sites"]}
        check("private:e2-resolved",
              record["indirect_evidence"]["counts"]
              == {"RESOLVED_FINITE_SET": 3}
              and sites[0x86E8]["bank_provenance"] == "PROVEN"
              and sites[0x86E8]["proven_banks"] == [0]
              and sites[0x86E8]["feasible_target_count"] == 4
              and sites[0x8956]["bank_provenance"] == "UNRESOLVED"
              and sites[0x8956]["feasible_target_count"] == 4
              and sites[0x8F3C]["bank_provenance"] == "MODEL_UNREACHED"
              and sites[0x8F3C]["feasible_target_count"] == 300)
        check("private:delta-record",
              record["deltas"]["c570_blocker"]["closure_applied"] is False
              and record["deltas"]["e2_sites"]["p7_status"]
              == "ALL_RESOLVED_FINITE_SET"
              and record["deltas"]["bank_window_frontier"]["delta"]
              == "EXPANDED"
              and record["deltas"]["translation"]["status"]
              == "NOT_ATTEMPTED"
              and record["deltas"]["native_build"]["status"]
              == "NOT_ATTEMPTED")
        check("private:no-rom-bytes",
              private_fixture.PRIVATE_ROM.read_bytes()
              not in canonical_text(record).encode("utf-8"))
        FINDINGS["deltas"] = record["deltas"]
        FINDINGS["frontier"] = {
            "proven": record["p7_bank_frontier"]["proven_instructions"],
            "unresolved": record["p7_bank_frontier"]
            ["unresolved_instructions"],
            "sites": record["indirect_evidence"]["counts"],
        }
        check("private:blockers",
              len(record["blockers"]) == 3
              and record["blockers"][0]["stage"] == "frontier"
              and record["blockers"][1]["stage"] == "bank_state"
              and record["blockers"][2]["code"] == "NOT_TESTED")

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            regression_record = run_regression(script)
            check(f"regression:{script}:exit",
                  regression_record["returncode"] == 0)
            check(f"regression:{script}:stderr",
                  regression_record["stderr_empty"])
            regressions.append(regression_record)
        p7_06_regression = run_regression(
            P7_06_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-11/regression_p7_06"])
        check("regression:p7-06:exit", p7_06_regression["returncode"] == 0)
        check("regression:p7-06:stderr", p7_06_regression["stderr_empty"])
        check("regression:p7-06:marker",
              any(marker == "OPENRECOMP_P7_06=PASS"
                  for marker in p7_06_regression["markers"]))
        regressions.append(p7_06_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("private_frontier.json", record)
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
        check("hygiene:no-rom-extension-in-scratch",
              not any(path.suffix.lower() in (".nes", ".fds", ".unf", ".unif")
                      for path in SCRATCH.rglob("*") if path.is_file()))
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
    (EVIDENCE_DIR / "p7_11_tests.json").write_text(
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
