#!/usr/bin/env python3
"""OpenRecomp Phase-5 final verdict gate (P5-99).

Issues the Phase-5 terminal verdict only if the exact bounded public NES
static-recompilation claim is supported by the audited tree and evidence:
source integrity, the frozen Phase-1/2/3/4 chain, the complete Phase-5 stage
ledger, every stage record PASS, the fixture/translation/execution/
equivalence/package identities and the whole-regression record.

On success it promotes the terminal marker for the bounded claim only::

    OPENRECOMP_P5_99=PASS
    OPENRECOMP_PHASE5_FINAL_VERDICT_V1=PASS tests=<count>
    OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=PASS
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
CONTROL = ROOT / ".openrecomp-phase5"

STAGE = "P5-99"
STAGE_MARKER = "OPENRECOMP_P5_99"
FEATURE_MARKER = "OPENRECOMP_PHASE5_FINAL_VERDICT_V1"
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
PHASE3_MANIFEST_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_99_RECORD_SHA256 = "c893250b539cf1e82f368c09fe848f8f695ebece17f7735713c5367a3d93c1cf"
P3_99_GATE_SHA256 = "ba5814902797d9848614e08b6bd655c00061dfb0d2dc90fec30da60382d558fa"
P4_99_RECORD_SHA256 = "f13cf89155daaf07731097a7530a642c7cbd60cc5ae231e9f602139cdcc78154"
P4_99_GATE = "tools/test_phase4_final_verdict_v1.py"
P4_99_GATE_SHA256 = "6c357c18401ebff522810e8106fdd70032a7a2774ea63ad1377351aa3ca22abd"

PUBLIC_ROM_SHA256 = "272c94cdc79463cd1020ff14db1892ba56af07e4cfda97f5f1df89dd807772b9"
PROGRAM_SHA256 = "6e4dcb44aedd4fb010f00c8cbdf17ae3b92f5ce98a963bcffdbbbb8939c79078"
SUPPORT_SHA256 = "2b411eea226bb6a59eb97314102dc7794d5551002f5b8bf6dffe4a75f6fd8b48"
OBSERVABLE_STATE = "0x440A095E452B3BA9"
OBSERVABLE_STEPS = "90904"
PACKAGE_SHA256 = "447f72cc616d80fa72e3681c5acd34b00833d7e3fe3fb5bf8bf3230347cc4c13"

LEDGER_STAGES = tuple(f"P5-{index:02d}"
                      for index in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 90, 91))

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}


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


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-99 final verdict gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-99")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}

    print("=== P5-99 Phase-5 Final Verdict Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        check("source:root-manifest",
              sha256_file(ROOT / "SOURCE_SHA256SUMS.txt") == ROOT_MANIFEST_SHA256)
        check("source:phase3-manifest",
              sha256_file(ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt")
              == PHASE3_MANIFEST_SHA256)
        phase4_entries = parse_manifest(
            ROOT / ".openrecomp-phase4" / "SOURCE_SHA256SUMS.txt")
        check("source:phase4-manifest-verified",
              bool(phase4_entries) and all(
                  sha256_file(ROOT / rel) == digest
                  for digest, rel in phase4_entries))
        phase5_entries = parse_manifest(CONTROL / "SOURCE_SHA256SUMS.txt")
        check("source:phase5-manifest-verified",
              bool(phase5_entries) and all(
                  sha256_file(ROOT / rel) == digest
                  for digest, rel in phase5_entries))
        check("source:p3-99",
              sha256_file(ROOT / ".openrecomp-phase3" / "evidence" / "P3-99"
                          / "RESULT.json") == P3_99_RECORD_SHA256
              and sha256_file(ROOT / "tools" / "test_phase3_final_verdict_v1.py")
              == P3_99_GATE_SHA256)
        check("source:p4-99",
              sha256_file(ROOT / ".openrecomp-phase4" / "evidence" / "P4-99"
                          / "p4_99_tests.json") == P4_99_RECORD_SHA256
              and sha256_file(ROOT / P4_99_GATE) == P4_99_GATE_SHA256)

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
        check("chain:phase3",
              git(["rev-parse", "openrecomp-phase3-pass"]).stdout.strip()
              == PHASE3_TAG_OBJECT
              and git(["rev-parse", "openrecomp-phase3-pass^{commit}"]).stdout.strip()
              == PHASE3_COMMIT
              and git(["rev-parse", "openrecomp-phase3-pass^{tree}"]).stdout.strip()
              == PHASE3_TREE)
        check("chain:phase2-phase1",
              git(["rev-parse", "openrecomp-phase2-pass^{commit}"]).stdout.strip()
              == PHASE2_COMMIT
              and git(["rev-parse", "openrecomp-phase1-pass^{commit}"]).stdout.strip()
              == PHASE1_COMMIT)
        check("chain:descends",
              git(["merge-base", "--is-ancestor", PHASE4_COMMIT, "HEAD"]).returncode == 0)

        banner("control_plane")
        state = (CONTROL / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:current-stage", "CURRENT_STAGE=P5-99" in state)
        check("control-plane:last-passed", "LAST_PASSED_STAGE=P5-91" in state)
        rows = re.findall(r"^\|\s*(P5-\d\d)\s*\|[^|]*\|\s*([A-Z_]+)\s*\|",
                          queue, re.MULTILINE)
        by_id = {row[0]: row[1] for row in rows}
        for stage in LEDGER_STAGES:
            check(f"control-plane:queue:{stage}", by_id.get(stage) == "COMPLETE")
        for stage in LEDGER_STAGES:
            row = re.search(rf"^\|\s*{stage}\s*\|[^|]*\|\s*PASS\s*\|", state,
                            re.MULTILINE)
            check(f"control-plane:ledger:{stage}", row is not None)
        check("control-plane:terminal-reserved-before-verdict",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:general-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("stage_records")
        for stage in LEDGER_STAGES:
            record_path = CONTROL / "evidence" / stage / f"{stage.lower().replace('-', '_')}_tests.json"
            check(f"record:{stage}:present", record_path.is_file())
            document = read_json(record_path)
            check(f"record:{stage}:pass",
                  document["status"] == "PASS" and document["failure"] is None)

        banner("identities")
        fixture = read_json(CONTROL / "evidence" / "P5-01" / "ingestion.json")
        check("identity:public-fixture",
              fixture["public_fixture"]["image_sha256"] == PUBLIC_ROM_SHA256
              and fixture["public_fixture"]["execution_status"] == "SUPPORTED_NROM")
        emission = read_json(CONTROL / "evidence" / "P5-08" / "emission.json")
        check("identity:translation",
              emission["program_sha256"] == PROGRAM_SHA256
              and emission["support_sha256"] == SUPPORT_SHA256)
        observable = read_json(CONTROL / "evidence" / "P5-08" / "observable.json")
        check("identity:native-observable",
              observable["fields"]["state_fnv1a64"] == OBSERVABLE_STATE
              and observable["fields"]["steps"] == OBSERVABLE_STEPS)
        equivalence = read_json(CONTROL / "evidence" / "P5-10" / "equivalence.json")
        check("identity:equivalence",
              all(record["comparison"]["equivalent"]
                  for record in equivalence["records"].values()))
        executions = read_json(CONTROL / "evidence" / "P5-09" / "executions.json")
        check("identity:interactivity",
              len(executions["executions"]) == 4
              and all(record["fields"]["failed"] == "0"
                      for record in executions["executions"].values()))
        package = read_json(CONTROL / "evidence" / "P5-12" / "verification.json")
        check("identity:package", package["package_sha256"] == PACKAGE_SHA256)
        index = read_json(CONTROL / "evidence" / "P5-91" / "evidence_index.json")
        check("identity:package-index",
              index["package"]["sha256"] == PACKAGE_SHA256)
        claims = read_json(CONTROL / "evidence" / "P5-91" / "claim_record.json")
        check("identity:claims",
              claims["proven_count"] == 12 and claims["bounded_count"] == 4
              and claims["private_observation_count"] == 4
              and claims["unproven_count"] == 7
              and claims["unsupported_count"] == 4
              and claims["not_tested_count"] == 6
              and claims["ledger"]["general_nes"]["status"] == "NOT_PROVEN")
        regression = read_json(CONTROL / "evidence" / "P5-90" / "determinism.json")
        check("identity:whole-regression",
              regression["stdout_identical_raw"] is True
              and regression["stdout_identical_lf"] is True)
        private = read_json(CONTROL / "evidence" / "P5-11" / "blockers.json")
        check("identity:private-blocked",
              private["execution_status"] == "BLOCKED_UNSUPPORTED_MAPPER")
        FINDINGS["identities"] = {
            "public_fixture_sha256": PUBLIC_ROM_SHA256,
            "program_sha256": PROGRAM_SHA256,
            "support_sha256": SUPPORT_SHA256,
            "state_fnv1a64": OBSERVABLE_STATE,
            "steps": OBSERVABLE_STEPS,
            "package_sha256": PACKAGE_SHA256,
            "proven": claims["proven_count"],
            "bounded": claims["bounded_count"],
        }
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    status = "FAIL" if failure else "PASS"
    terminal = "PASS" if status == "PASS" else "NOT_PROVEN"

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
            "compatibility": f"{COMPAT_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    (EVIDENCE_DIR / "p5_99_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}={terminal}")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
