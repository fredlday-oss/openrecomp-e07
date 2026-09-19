#!/usr/bin/env python3
"""OpenRecomp Phase-6 final verdict gate (P6-99).

Issues the Phase-6 terminal verdict only if the exact bounded audited public
MMC1 static-recompilation claim is supported by the audited tree and evidence:
source integrity, the frozen Phase-1..5 chain, the complete Phase-6 stage
ledger, every stage record PASS, the fixture/translation/execution/
equivalence/workflow/whole-regression/claim-ledger identities and the
reserved-marker control-plane state.

On success it promotes the terminal marker for the bounded claim only::

    OPENRECOMP_P6_99=PASS
    OPENRECOMP_PHASE6_FINAL_VERDICT_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

The PASS never implies general NES compatibility, all MMC1 boards/revisions,
all NES games, commercial-game compatibility, cycle accuracy, full PPU/APU
accuracy, FDS compatibility or arbitrary 6502 compatibility.

Usage:

    python tools/test_phase6_final_verdict_v1.py \
        --evidence-dir .openrecomp-phase6/evidence/P6-99
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
PHASE6 = ROOT / ".openrecomp-phase6"

STAGE = "P6-99"
STAGE_MARKER = "OPENRECOMP_P6_99"
FEATURE_MARKER = "OPENRECOMP_PHASE6_FINAL_VERDICT_V1"
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
PHASE3_MANIFEST_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_99_RECORD_SHA256 = "c893250b539cf1e82f368c09fe848f8f695ebece17f7735713c5367a3d93c1cf"
P3_99_GATE_SHA256 = "ba5814902797d9848614e08b6bd655c00061dfb0d2dc90fec30da60382d558fa"
P4_99_RECORD_SHA256 = "f13cf89155daaf07731097a7530a642c7cbd60cc5ae231e9f602139cdcc78154"
P4_99_GATE_SHA256 = "6c357c18401ebff522810e8106fdd70032a7a2774ea63ad1377351aa3ca22abd"
P5_99_RECORD_SHA256 = "b0e8267c70ab2e990ca74665d8020ba463280447dd9f5fb370f4411cfb6e72c9"
P5_99_GATE_SHA256 = "bc772128a91344e17d1ed00fb5e2b503aae8a0ef5e4ad9de35b7fbdfcba52143"

PHASE6_ROM_SHA256 = "9e10dce532266592f9ccda781bc6d3a7354ab4951bd3db87e4f43d1c45056b70"
PHASE6_HOST_PROGRAM_SHA256 = (
    "6c1ccac5b49b6af231cef81115990c49d784edad5509615624078646866bf9f1")
PHASE6_SUPPORT_SHA256 = (
    "c15980d43ba9854c7e8dd5917a32a6e13ac3235d8fb7de06c50b91a2fb02ffb6")
PHASE6_EXECUTABLE_SHA256 = (
    "0ba034bd1e7c081bb0ee07a8d8606ba425f1f0139db65eab9fb57c4ff30f6255")
PHASE6_OBSERVABLES = {
    "failed": "0",
    "exit": "1",
    "steps": "82731",
    "pc": "0xC089",
    "frames": "9",
    "nmi": "6",
    "clock": "241746",
    "mmc1_regs": "1F070703",
    "exit_word": "0101010101010000",
}
PRIVATE_SHA256 = "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
PRIVATE_SIZE = 262160
PRIVATE_BLOCKER_CLASSES = ("unsupported_opcode",
                           "unresolved_indirect_control_flow",
                           "bank_state_unresolved",
                           "platform_runtime_not_tested")

EXPECTED_CLAIM_COUNTS = {
    "phase5_proven_count": 7,
    "phase5_bounded_count": 4,
    "proven_count": 11,
    "bounded_count": 5,
    "private_observation_count": 4,
    "private_blocker_count": 4,
    "unproven_count": 8,
    "unsupported_count": 9,
    "not_tested_count": 8,
}
MIN_EVIDENCE_FILES = 180

LEDGER_STAGES = (tuple(f"P6-{index:02d}" for index in range(0, 14))
                 + ("P6-90", "P6-91"))

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
EVIDENCE_WRITES: dict[str, bytes] = {}


class P6VerdictError(ValueError):
    """Fail-closed Phase-6 verdict scope error."""


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


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *arguments], cwd=str(ROOT),
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


def verify_claim_scope(record: dict[str, Any]) -> None:
    ledger = record.get("ledger")
    if not isinstance(ledger, dict):
        raise P6VerdictError("claim ledger is missing")
    statuses = {name: ledger.get(name, {}).get("status")
                for name in ("phase5_public_nrom", "phase6_public_mmc1",
                             "private_tmnt_compatibility", "general_nes")}
    if statuses["phase6_public_mmc1"] != "PROVEN":
        raise P6VerdictError("the bounded public MMC1 claim is not PROVEN")
    if statuses["phase5_public_nrom"] != "PROVEN":
        raise P6VerdictError("the frozen public NROM claim is not PROVEN")
    if statuses["general_nes"] != "UNPROVEN":
        raise P6VerdictError("general NES compatibility must remain UNPROVEN")
    if statuses["private_tmnt_compatibility"] != "UNPROVEN":
        raise P6VerdictError("private compatibility must remain UNPROVEN")
    if record.get("compatibility_marker") != f"{COMPAT_MARKER}=NOT_PROVEN":
        raise P6VerdictError("the general NES compatibility marker was promoted")
    if record.get("terminal_marker") != f"{TERMINAL_MARKER}=NOT_PROVEN":
        raise P6VerdictError("the terminal marker was not in its reserved state")


def expect_scope_fail(label: str, record: dict[str, Any]) -> None:
    try:
        verify_claim_scope(record)
    except P6VerdictError:
        check(f"reject:{label}", True)
        return
    raise AssertionError(f"reject:{label}: accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description="P6-99 final verdict gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-99")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-99 Phase-6 Final Verdict Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        check("source:root-manifest",
              sha256_file(ROOT / "SOURCE_SHA256SUMS.txt")
              == ROOT_MANIFEST_SHA256)
        check("source:phase3-manifest",
              sha256_file(ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt")
              == PHASE3_MANIFEST_SHA256)
        phase4_entries = parse_manifest(
            ROOT / ".openrecomp-phase4" / "SOURCE_SHA256SUMS.txt")
        check("source:phase4-manifest-verified",
              bool(phase4_entries) and all(
                  sha256_file(ROOT / rel) == digest
                  for digest, rel in phase4_entries))
        phase5_entries = parse_manifest(
            ROOT / ".openrecomp-phase5" / "SOURCE_SHA256SUMS.txt")
        check("source:phase5-manifest-verified",
              bool(phase5_entries) and all(
                  sha256_file(ROOT / rel) == digest
                  for digest, rel in phase5_entries))
        phase6_entries = parse_manifest(PHASE6 / "SOURCE_SHA256SUMS.txt")
        check("source:phase6-manifest-verified",
              bool(phase6_entries) and all(
                  sha256_file(ROOT / rel) == digest
                  for digest, rel in phase6_entries))
        check("source:p3-99",
              sha256_file(ROOT / ".openrecomp-phase3" / "evidence" / "P3-99"
                          / "RESULT.json") == P3_99_RECORD_SHA256
              and sha256_file(ROOT / "tools" / "test_phase3_final_verdict_v1.py")
              == P3_99_GATE_SHA256)
        check("source:p4-99",
              sha256_file(ROOT / ".openrecomp-phase4" / "evidence" / "P4-99"
                          / "p4_99_tests.json") == P4_99_RECORD_SHA256
              and sha256_file(ROOT / "tools" / "test_phase4_final_verdict_v1.py")
              == P4_99_GATE_SHA256)
        check("source:p5-99",
              sha256_file(ROOT / ".openrecomp-phase5" / "evidence" / "P5-99"
                          / "p5_99_tests.json") == P5_99_RECORD_SHA256
              and sha256_file(ROOT / "tools" / "test_phase5_final_verdict_v1.py")
              == P5_99_GATE_SHA256)
        private_path = pathlib.Path(
            r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes")
        check("source:private-image",
              private_path.is_file()
              and private_path.stat().st_size == PRIVATE_SIZE
              and sha256_file(private_path) == PRIVATE_SHA256)

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
        check("chain:phase4",
              git(["rev-parse", "openrecomp-phase4-pass"]).stdout.strip()
              == PHASE4_TAG_OBJECT
              and git(["rev-parse", "openrecomp-phase4-pass^{commit}"],
                      ).stdout.strip() == PHASE4_COMMIT
              and git(["rev-parse", "openrecomp-phase4-pass^{tree}"],
                      ).stdout.strip() == PHASE4_TREE)
        check("chain:phase3",
              git(["rev-parse", "openrecomp-phase3-pass"]).stdout.strip()
              == PHASE3_TAG_OBJECT
              and git(["rev-parse", "openrecomp-phase3-pass^{commit}"],
                      ).stdout.strip() == PHASE3_COMMIT
              and git(["rev-parse", "openrecomp-phase3-pass^{tree}"],
                      ).stdout.strip() == PHASE3_TREE)
        check("chain:phase2-phase1",
              git(["rev-parse", "openrecomp-phase2-pass^{commit}"]
                  ).stdout.strip() == PHASE2_COMMIT
              and git(["rev-parse", "openrecomp-phase1-pass^{commit}"]
                      ).stdout.strip() == PHASE1_COMMIT)
        check("chain:descends",
              git(["merge-base", "--is-ancestor", PHASE5_COMMIT, "HEAD"]
                  ).returncode == 0)

        banner("control_plane")
        state = (PHASE6 / "STATE.md").read_text(encoding="utf-8")
        queue = (PHASE6 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:current-stage", "CURRENT_STAGE=P6-99" in state)
        check("control-plane:last-passed", "LAST_PASSED_STAGE=P6-91" in state)
        check("control-plane:mmc1-reserved",
              "MMC1_PLATFORM_STATUS=NOT_PROVEN" in state
              and "FINAL_VERDICT=NOT_PROVEN" in state)
        rows = re.findall(r"^\|\s*(P6-\d\d)\s*\|[^|]*\|\s*([A-Z_]+)\s*\|",
                          queue, re.MULTILINE)
        by_id = {row[0]: row[1] for row in rows}
        for stage in LEDGER_STAGES:
            check(f"control-plane:queue:{stage}",
                  by_id.get(stage) == "COMPLETE")
        for stage in LEDGER_STAGES:
            row = re.search(rf"^\|\s*{stage}\s*\|[^|]*\|\s*PASS\s*\|", state,
                            re.MULTILINE)
            check(f"control-plane:ledger:{stage}", row is not None)
        check("control-plane:terminal-reserved-before-verdict",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:general-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("stage_records")
        for stage in LEDGER_STAGES:
            record_path = (PHASE6 / "evidence" / stage
                           / f"{stage.lower().replace('-', '_')}_tests.json")
            check(f"record:{stage}:present", record_path.is_file())
            document = read_json(record_path)
            check(f"record:{stage}:pass",
                  document["status"] == "PASS" and document["failure"] is None)
        FINDINGS["ledger_stages"] = list(LEDGER_STAGES)

        banner("identities")
        p6_06 = read_json(PHASE6 / "evidence" / "P6-06"
                          / "proof_fixture.json")["metadata"]
        check("identity:public-mmc1-fixture",
              p6_06["rom_sha256"] == PHASE6_ROM_SHA256
              and p6_06["mapper"] == 1 and p6_06["submapper"] == 0
              and p6_06["prg_banks"] == 4 and p6_06["chr_banks"] == 4)
        p6_07 = read_json(PHASE6 / "evidence" / "P6-07" / "emission.json")
        check("identity:translation",
              p6_07["host_program_sha256"] == PHASE6_HOST_PROGRAM_SHA256
              and p6_07["support_sha256"] == PHASE6_SUPPORT_SHA256)
        p6_08 = read_json(PHASE6 / "evidence" / "P6-08" / "build.json")
        check("identity:native-executable",
              p6_08["executable_sha256"] == PHASE6_EXECUTABLE_SHA256
              and p6_08["classification"] == "EXECUTABLE_REPRODUCIBLE")
        p6_08_exec = read_json(PHASE6 / "evidence" / "P6-08"
                               / "executions.json")
        check("identity:native-observables",
              all(p6_08_exec["fields"].get(key) == value
                  for key, value in PHASE6_OBSERVABLES.items())
              and len(p6_08_exec["frames"]) == 9
              and p6_08_exec["runs"] == 3)
        p6_09 = read_json(PHASE6 / "evidence" / "P6-09" / "equivalence.json")
        check("identity:reference-equivalence",
              p6_09["fixture"]["rom_sha256"] == PHASE6_ROM_SHA256
              and set(p6_09["plans"]) == {"p6_08", "all_buttons", "mixed_bits"}
              and all(record["comparison"]["equivalent"] is True
                      and record["comparison"]["mismatches"] == []
                      for record in p6_09["records"].values()))
        p6_10 = read_json(PHASE6 / "evidence" / "P6-10" / "blockers.json")
        check("identity:private-frontier",
              p6_10["execution_status"]
              == "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE"
              and "0xc570" in p6_10["blockers"][0]["detail"])
        p6_11 = read_json(PHASE6 / "evidence" / "P6-11"
                          / "platform_expansion.json")
        check("identity:platform-decision",
              p6_11["decision"]["decision"] == "NO_ADDITION_JUSTIFIED"
              and p6_11["decision"]["additions"] == [])
        p6_12 = read_json(PHASE6 / "evidence" / "P6-12" / "workflow.json")
        check("identity:workflow",
              p6_12["workflow"] == "p6_rom_to_native_v1"
              and p6_12["public_report"]["status"] == "COMPLETED"
              and p6_12["public_report"]["blockers"] == []
              and p6_12["public_report"]["generated_sources"]
              ["host_program_sha256"] == PHASE6_HOST_PROGRAM_SHA256
              and p6_12["public_report"]["generated_sources"]["support_sha256"]
              == PHASE6_SUPPORT_SHA256
              and p6_12["public_report"]["native_build"]["executable_sha256"]
              == PHASE6_EXECUTABLE_SHA256)
        p6_13 = read_json(PHASE6 / "evidence" / "P6-13"
                          / "frontier_record.json")
        check("identity:private-second-run",
              p6_13["native_execution_reached"] is False
              and p6_13["interactive_behaviour_reached"] is False
              and tuple(entry["classification"]
                        for entry in p6_13["stop_reasons"])
              == PRIVATE_BLOCKER_CLASSES)
        p6_90 = read_json(PHASE6 / "evidence" / "P6-90"
                          / "whole_regression.json")
        check("identity:whole-regression",
              p6_90["phase5_whole_regression"]["stdout_sha256_raw"]
              == "e487dbc0221d813d1d1138065be422bf8440d96f64d0dee5cd94d80f123ff5c5"
              and all(record["stdout_matches_official"] is True
                      for record in p6_90["phase6_stage_gates"])
              and len(p6_90["phase6_stage_gates"]) == 14)
        p6_91_index = read_json(PHASE6 / "evidence" / "P6-91"
                                / "evidence_index.json")
        p6_91_claims = read_json(PHASE6 / "evidence" / "P6-91"
                                 / "claim_record.json")
        check("identity:evidence-index",
              p6_91_index["evidence_files"] >= MIN_EVIDENCE_FILES
              and p6_91_index["boundaries"]["phase6_public_mmc1_rom_sha256"]
              == PHASE6_ROM_SHA256)
        check("identity:claim-counts",
              all(p6_91_claims[key] == value
                  for key, value in EXPECTED_CLAIM_COUNTS.items()))
        check("identity:claim-sections",
              set(p6_91_claims["ledger"]) == {
                  "phase5_public_nrom", "phase6_public_mmc1",
                  "private_tmnt_compatibility", "general_nes"}
              and p6_91_claims["ledger"]["general_nes"]["status"]
              == "UNPROVEN")
        check("identity:limitations",
              len(p6_91_claims["limitations"]) >= 6)

        banner("scope_guard")
        verify_claim_scope(p6_91_claims)
        check("scope:bounded-claim-only", True)
        import copy
        promoted = copy.deepcopy(p6_91_claims)
        promoted["ledger"]["general_nes"]["status"] = "PROVEN"
        expect_scope_fail("general-promotion", promoted)
        promoted = copy.deepcopy(p6_91_claims)
        promoted["ledger"]["private_tmnt_compatibility"]["status"] = "PROVEN"
        expect_scope_fail("private-promotion", promoted)
        promoted = copy.deepcopy(p6_91_claims)
        promoted["compatibility_marker"] = f"{COMPAT_MARKER}=PASS"
        expect_scope_fail("compat-marker-promotion", promoted)
        promoted = copy.deepcopy(p6_91_claims)
        promoted["ledger"]["phase6_public_mmc1"]["status"] = "UNPROVEN"
        expect_scope_fail("phase6-demotion", promoted)

        banner("evidence")
        verdict = {
            "stage": STAGE,
            "verdict": "PASS",
            "scope": {
                "asserted": "the exact bounded audited public MMC1 "
                            "static-recompilation claim",
                "not_asserted": [
                    "general NES compatibility",
                    "all MMC1 boards, revisions or wiring variants",
                    "all NES games",
                    "commercial-game compatibility",
                    "cycle accuracy",
                    "full PPU accuracy",
                    "full APU accuracy",
                    "Famicom Disk System compatibility",
                    "arbitrary 6502 compatibility",
                ],
            },
            "identities": {
                "public_mmc1_fixture_sha256": PHASE6_ROM_SHA256,
                "host_program_sha256": PHASE6_HOST_PROGRAM_SHA256,
                "support_sha256": PHASE6_SUPPORT_SHA256,
                "executable_sha256": PHASE6_EXECUTABLE_SHA256,
                "observables": PHASE6_OBSERVABLES,
                "private_image_sha256": PRIVATE_SHA256,
                "private_blockers": list(PRIVATE_BLOCKER_CLASSES),
                "evidence_files": p6_91_index["evidence_files"],
            },
            "markers": {
                "stage": f"{STAGE_MARKER}=PASS",
                "gate": f"{FEATURE_MARKER}=PASS",
                "terminal": f"{TERMINAL_MARKER}=PASS",
                "compatibility": f"{COMPAT_MARKER}=NOT_PROVEN",
            },
            "terminal_tag": {
                "created": False,
                "reason": "the frozen Phase-6 control policy does not require "
                          "a terminal tag; the terminal boundary is the "
                          "verdict commit",
            },
        }
        write_json("terminal_verdict.json", verdict)
        private_bytes = private_path.read_bytes()
        write_json("verdict_record.json", {
            "stage": STAGE,
            "markers": verdict["markers"],
            "claim_counts": EXPECTED_CLAIM_COUNTS,
        })
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
        check("hygiene:private-hash-recorded",
              PRIVATE_SHA256 in EVIDENCE_WRITES[
                  "terminal_verdict.json"].decode("utf-8"))
        FINDINGS["verdict"] = verdict["identities"]
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
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
    for name, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / name).write_bytes(data)
    (EVIDENCE_DIR / "p6_99_tests.json").write_text(
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
