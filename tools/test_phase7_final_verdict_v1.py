#!/usr/bin/env python3
"""OpenRecomp Phase-7 final verdict gate (P7-99).

Issues `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=PASS` only if the exact
bounded audited public translation/control-flow claim is proven by the
audited tree and evidence: source integrity, the frozen Phase-1..Phase-6
chain, the complete Phase-7 stage ledger, every pinned public identity and
the separated claim ledger. The general NES compatibility marker and the
private TMNT playability marker remain `NOT_PROVEN` permanently.

On success it emits::

    OPENRECOMP_P7_99=PASS
    OPENRECOMP_PHASE7_FINAL_VERDICT_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=PASS
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_final_verdict_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-99
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL7 = ROOT / ".openrecomp-phase7"

STAGE = "P7-99"
STAGE_MARKER = "OPENRECOMP_P7_99"
FEATURE_MARKER = "OPENRECOMP_PHASE7_FINAL_VERDICT_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

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
PHASE6_COMMIT = "1643817d43196c43155805249137e4b4e4a21eb1"
PHASE6_TREE = "cda3f535be43dc6f3d4b457d11d356ae39ea34af"

ROOT_MANIFEST_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
PHASE3_MANIFEST_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P6_99_RECORD_SHA256 = "e7e462f15ca64a2d8db130ec664ac309d5ebfef1c128fd392111d19e4be30ea4"
P6_91_CLAIM_SHA256 = ""

PUBLIC_FIXTURES = {
    "P7-03": ("66c4d8c759e622e214f25eb1cb1a6f67b928d3031e1d21a4db0367f06ccd6d8c",
              ".openrecomp-phase7/evidence/P7-03/classification_fixture.json",
              "rom_sha256"),
    "P7-05": ("902a9c4281a7616a67f12df08b2b3526867f1bff831c982530c53cc769cbd53a",
              ".openrecomp-phase7/evidence/P7-05/bank_structure.json",
              "rom_sha256"),
    "P7-07": ("1c9ad6582576a5c7c12a27b8a0077257c7c414142cd81ffdc92cb4a8ff1c9248",
              ".openrecomp-phase7/evidence/P7-07/indirect_fixture.json",
              "rom_sha256"),
}
HOST_PROGRAM_SHA256 = "231a3a09924e94c7977ffaae71712ad9d48e443495c633ae2b6b96a8539b0b38"
SUPPORT_SHA256 = "5ea325b2dea6eb348638e129c51e242aaaa047be83860ba38302e3963ef8b6a7"
EXECUTABLE_SHA256 = "23679fb850d427951dc4f685b5322ccc9de3c4f50df5cd18fa97f2a2b83426ab"
P7_09_EXECUTABLES = {
    "exact": "23679fb850d427951dc4f685b5322ccc9de3c4f50df5cd18fa97f2a2b83426ab",
    "finite": "7da08a48b96394acb0c569c5c71142225c5fb6e0fa6c74b802978dae49405e77",
    "unresolved": "ea6bef2371f7246219298788167c763cb82effbe868510191deb66d3266f31d8",
}
PRIVATE_SHA256 = "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
PRIVATE_SIZE = 262160

STAGE_NAMES = {f"P7-{i:02d}": None for i in range(0, 15)}
STAGE_NAMES.update({"P7-90": None, "P7-91": None})
LEDGER_STAGES = tuple(sorted(STAGE_NAMES))

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
EVIDENCE_WRITES: dict[str, bytes] = {}


class P7VerdictError(ValueError):
    """Fail-closed Phase-7 verdict scope error."""


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
        raise P7VerdictError("claim ledger is missing")
    if ledger.get("phase7_public_translation", {}).get("status") != "PROVEN":
        raise P7VerdictError("the bounded public Phase-7 claim is not PROVEN")
    if ledger.get("private_tmnt_compatibility", {}).get("status") != "UNPROVEN":
        raise P7VerdictError("private compatibility must remain UNPROVEN")
    if ledger.get("general_nes", {}).get("status") != "UNPROVEN":
        raise P7VerdictError("general NES compatibility must remain UNPROVEN")
    if record.get("terminal_marker") != f"{TERMINAL_MARKER}=NOT_PROVEN":
        raise P7VerdictError("the terminal marker was not in its reserved state")
    if record.get("compatibility_marker") != f"{COMPAT_MARKER}=NOT_PROVEN":
        raise P7VerdictError("the general marker was promoted")
    if record.get("playability_marker") != f"{PLAYABILITY_MARKER}=NOT_PROVEN":
        raise P7VerdictError("the playability marker was promoted")


def expect_scope_fail(label: str, record: dict[str, Any]) -> None:
    try:
        verify_claim_scope(record)
    except P7VerdictError:
        check(f"reject:{label}", True)
        return
    raise AssertionError(f"reject:{label}: accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description="P7-99 final verdict gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-99")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    for item in EVIDENCE_DIR.iterdir():
        if item.is_file():
            item.unlink()
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-99 Final Phase-7 Verdict Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        check("source:root-manifest",
              sha256_file(ROOT / "SOURCE_SHA256SUMS.txt")
              == ROOT_MANIFEST_SHA256)
        check("source:phase3-manifest",
              sha256_file(ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt")
              == PHASE3_MANIFEST_SHA256)
        for phase in ("phase4", "phase5", "phase6", "phase7"):
            path = (ROOT / f".openrecomp-{phase}" / "SOURCE_SHA256SUMS.txt")
            entries = parse_manifest(path)
            check(f"source:{phase}-manifest-verified",
                  bool(entries) and all(
                      sha256_file(ROOT / rel) == digest
                      for digest, rel in entries))
        check("source:p6-99-record",
              sha256_file(ROOT / ".openrecomp-phase6" / "evidence" / "P6-99"
                          / "p6_99_tests.json") == P6_99_RECORD_SHA256)
        check("source:private-image",
              pathlib.Path(r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes")
              .is_file())

        banner("frozen_chain")
        check("chain:phase5",
              git(["rev-parse", "openrecomp-phase5-pass"]).stdout.strip()
              == PHASE5_TAG_OBJECT
              and git(["rev-parse", "openrecomp-phase5-pass^{commit}"]).stdout.strip()
              == PHASE5_COMMIT
              and git(["rev-parse", "openrecomp-phase5-pass^{tree}"]).stdout.strip()
              == PHASE5_TREE)
        check("chain:phase4",
              git(["rev-parse", "openrecomp-phase4-pass"]).stdout.strip()
              == PHASE4_TAG_OBJECT
              and git(["rev-parse", "openrecomp-phase4-pass^{commit}"]).stdout.strip()
              == PHASE4_COMMIT
              and git(["rev-parse", "openrecomp-phase4-pass^{tree}"]).stdout.strip()
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
        check("chain:phase6",
              git(["rev-parse", "refs/heads/phase6/nes-compat-v1"]).stdout.strip()
              == PHASE6_COMMIT
              and git(["rev-parse", f"{PHASE6_COMMIT}^{{tree}}"]).stdout.strip()
              == PHASE6_TREE)
        check("chain:descends",
              git(["merge-base", "--is-ancestor", PHASE6_COMMIT,
                   "HEAD"]).returncode == 0)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:current-stage", "CURRENT_STAGE=P7-99" in state)
        check("control-plane:last-passed", "LAST_PASSED_STAGE=P7-91" in state)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in state
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:general-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in state
              and f"{COMPAT_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue)
        rows = re.findall(r"^\|\s*(P7-\d\d)\s*\|[^|]*\|\s*([A-Z_]+)\s*\|",
                          queue, re.MULTILINE)
        by_id = {row[0]: row[1] for row in rows}
        for stage in LEDGER_STAGES:
            check(f"control-plane:queue:{stage}",
                  by_id.get(stage) == "COMPLETE")
        for stage in LEDGER_STAGES:
            row = re.search(rf"^\|\s*{stage}\s*\|[^|]*\|\s*PASS\s*\|", state,
                            re.MULTILINE)
            check(f"control-plane:ledger:{stage}", row is not None)

        banner("stage_records")
        for stage in LEDGER_STAGES:
            path = (CONTROL7 / "evidence" / stage /
                    f"{stage.lower().replace('-', '_')}_tests.json")
            check(f"record:{stage}:present", path.is_file())
            document = read_json(path)
            check(f"record:{stage}:pass",
                  document["status"] == "PASS"
                  and document["failure"] is None)

        banner("public_identities")
        for stage, (expected, relative, key) in PUBLIC_FIXTURES.items():
            record = read_json(ROOT / relative)
            if stage in ("P7-05", "P7-07"):
                actual = record["fixture"][key]
            else:
                actual = record[key]
            check(f"identity:{stage}-fixture", actual == expected)
        p7_08 = read_json(ROOT / ".openrecomp-phase7" / "evidence" / "P7-08"
                          / "translation_frontier.json")
        emission = p7_08["indirect_fixture"]["emission"]
        check("identity:host-program",
              emission["host_program_sha256"] == HOST_PROGRAM_SHA256
              and emission["support_sha256"] == SUPPORT_SHA256)
        check("identity:native-executable",
              p7_08["indirect_fixture"]["native_build"]["executable_sha256"]
              == EXECUTABLE_SHA256)
        p7_09 = read_json(ROOT / ".openrecomp-phase7" / "evidence" / "P7-09"
                          / "native_execution.json")
        for name, expected in P7_09_EXECUTABLES.items():
            check(f"identity:p7-09-{name}",
                  p7_09["variants"][name]["executable_sha256"] == expected)
        check("identity:p7-09-fail-closed",
              p7_09["variants"]["unresolved"]["fields"]["failed"] == "1"
              and p7_09["variants"]["unresolved"]["fields"]["error"]
              == "pc outside the emitted image")
        p7_10 = read_json(ROOT / ".openrecomp-phase7" / "evidence" / "P7-10"
                          / "reference_equivalence.json")
        check("identity:reference-equivalence",
              all(p7_10["variants"][name].get("clock_delta") == -2
                  for name in ("exact", "finite"))
              and p7_10["variants"]["exact"]["native_fields"]
              ["ram_fnv1a64"]
              == p7_10["variants"]["exact"]["reference_fields"]
              ["ram_fnv1a64"]
              and p7_10["variants"]["unresolved"].get("policy") is not None)
        p7_11 = read_json(ROOT / ".openrecomp-phase7" / "evidence" / "P7-11"
                          / "private_frontier.json")
        check("identity:private-frontier",
              p7_11["image_sha256"] == PRIVATE_SHA256
              and p7_11["p7_bank_frontier"]["proven_instructions"] == 530
              and p7_11["p7_bank_frontier"]["unresolved_instructions"]
              == 14027
              and p7_11["classification_0xc570"]["classification"]
              == "DATA_NOT_CODE"
              and p7_11["indirect_evidence"]["counts"]
              == {"RESOLVED_FINITE_SET": 3})
        p7_12 = read_json(ROOT / ".openrecomp-phase7" / "evidence" / "P7-12"
                          / "inline_closure.json")
        check("identity:closure",
              p7_12["private_image"]["baseline_instructions"] == 1250
              and p7_12["private_image"]["closure_instructions"] == 1255
              and p7_12["private_image"]["stop"]["address"] == 0xBB6B)
        p7_13 = read_json(ROOT / ".openrecomp-phase7" / "evidence" / "P7-13"
                          / "private_frontier_run2.json")
        check("identity:private-run2",
              p7_13["native_execution_reached"] is False
              and p7_13["interactive_behaviour_reached"] is False
              and [item["classification"] for item in p7_13["stop_reasons"]]
              == ["undocumented_opcode_unclassified", "bank_state_unresolved",
                  "platform_runtime_not_tested"])
        p7_14 = read_json(ROOT / ".openrecomp-phase7" / "evidence" / "P7-14"
                          / "workflow.json")
        check("identity:workflow",
              p7_14["bank_switching"]["status"] == "COMPLETED"
              and p7_14["indirect_flow"]["status"]
              == "COMPLETED_WITH_FRONTIER"
              and p7_14["private_image"]["status"] == "FAIL_CLOSED"
              and p7_14["hygiene"]["no_byte_identical_copy"] is True)

        banner("claim_scope_guard")
        claims = read_json(ROOT / ".openrecomp-phase7" / "evidence" / "P7-91"
                           / "claim_record.json")
        verify_claim_scope(claims)
        check("scope:bounded-claim-only", True)
        promoted = copy.deepcopy(claims)
        promoted["ledger"]["general_nes"]["status"] = "PROVEN"
        expect_scope_fail("general-promotion", promoted)
        promoted = copy.deepcopy(claims)
        promoted["ledger"]["private_tmnt_compatibility"]["status"] = "PROVEN"
        expect_scope_fail("private-promotion", promoted)
        promoted = copy.deepcopy(claims)
        promoted["playability_marker"] = f"{PLAYABILITY_MARKER}=PASS"
        expect_scope_fail("playability-promotion", promoted)
        promoted = copy.deepcopy(claims)
        promoted["compatibility_marker"] = f"{COMPAT_MARKER}=PASS"
        expect_scope_fail("compat-marker-promotion", promoted)
        promoted = copy.deepcopy(claims)
        promoted["ledger"]["phase7_public_translation"]["status"] = "UNPROVEN"
        expect_scope_fail("phase7-demotion", promoted)

        banner("evidence")
        index = read_json(ROOT / ".openrecomp-phase7" / "evidence" / "P7-91"
                          / "evidence_index.json")
        verdict = {
            "stage": STAGE,
            "verdict": "PASS",
            "scope": {
                "asserted": "the exact bounded audited public Phase-7 "
                            "translation/control-flow claim (classification "
                            "of 0x7C as data, bank-aware reachability and "
                            "structure, indirect evidence with explicit "
                            "states, public fixtures, integration, native "
                            "execution and bounded reference equivalence, "
                            "inline-dispatch closure and reusable workflow)",
                "not_asserted": [
                    "general NES compatibility",
                    "commercial-game compatibility",
                    "TMNT playability",
                    "all undocumented 6502 opcodes",
                    "all indirect-control-flow recovery",
                    "arbitrary bank-switched binaries",
                    "cycle accuracy",
                    "full PPU/APU accuracy",
                    "arbitrary 6502 compatibility",
                ],
            },
            "identities": {
                "public_fixtures": {stage: expected for stage, (expected, _r,
                                                                  _k) in
                                    PUBLIC_FIXTURES.items()},
                "host_program_sha256": HOST_PROGRAM_SHA256,
                "support_sha256": SUPPORT_SHA256,
                "executable_sha256": EXECUTABLE_SHA256,
                "p7_09_executables": P7_09_EXECUTABLES,
                "private_image_sha256": PRIVATE_SHA256,
                "evidence_files": index["evidence_files"],
                "proven_claims": len(claims["proven_claims"]),
                "bounded_claims": len(claims["bounded_claims"]),
            },
            "markers": {
                "stage": f"{STAGE_MARKER}=PASS",
                "gate": f"{FEATURE_MARKER}=PASS",
                "terminal": f"{TERMINAL_MARKER}=PASS",
                "compatibility": f"{COMPAT_MARKER}=NOT_PROVEN",
                "playability": f"{PLAYABILITY_MARKER}=NOT_PROVEN",
            },
            "terminal_tag": {
                "created": False,
                "reason": "the frozen Phase-7 control policy does not require "
                          "a terminal tag; the terminal boundary is the "
                          "verdict commit",
            },
        }
        write_json("terminal_verdict.json", verdict)
        write_json("verdict_record.json", {
            "stage": STAGE,
            "markers": verdict["markers"],
            "scope": verdict["scope"]["asserted"],
        })
        private_path = pathlib.Path(
            r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes")
        private_bytes = private_path.read_bytes() if private_path.is_file() else b""
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}",
                  private_bytes not in data)
        FINDINGS["verdict"] = verdict["identities"]
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
            "playability": f"{PLAYABILITY_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for name, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / name).write_bytes(data)
    (EVIDENCE_DIR / "p7_99_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}={terminal}")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
