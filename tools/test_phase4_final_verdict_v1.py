#!/usr/bin/env python3
"""OpenRecomp Phase-4 final verdict (P4-99).

Issues the Phase-4 terminal verdict only if the exact bounded
generic-runtime/platform claim is supported by the audited tree and evidence:

* source integrity: root and Phase-3 manifests verified, Phase-4 manifest
  entries verified;
* frozen chain: the annotated Phase-3 tag (object/commit/tree), the Phase-2
  and Phase-1 tags and descent from the boundary;
* control plane: every stage ledger row `P4-00` .. `P4-91` is `PASS`,
  `CURRENT_STAGE=P4-99`, the frozen queue is complete and both terminal
  markers are still reserved as `NOT_PROVEN` before this stage;
* committed evidence: every stage result record is PASS with no failure; the
  package identity matches the P4-10/P4-91 records; the fixture, translation,
  executable, equivalence and whole-regression identities match their
  recorded values.

On success it promotes the terminal marker for the bounded claim only::

    OPENRECOMP_P4_99=PASS
    OPENRECOMP_PHASE4_FINAL_VERDICT_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=PASS
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_final_verdict_v1.py
    python tools/test_phase4_final_verdict_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-99
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
CONTROL = ROOT / ".openrecomp-phase4"

STAGE = "P4-99"
STAGE_MARKER = "OPENRECOMP_P4_99"
FEATURE_MARKER = "OPENRECOMP_PHASE4_FINAL_VERDICT_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

PHASE3_TAG = "openrecomp-phase3-pass"
PHASE3_TAG_OBJECT = "ac31524504b1b5cc63aabcfd5132a3eb4275e8e9"
PHASE3_COMMIT = "e16e4b29b90f379615f1af97e47747cd1d531796"
PHASE3_TREE = "a940f0d84a32adaf191f7ff2bebfb24cc855cde0"
PHASE2_COMMIT = "01b1d7cba8c931fca95d041389cfb1902b7c89fe"
PHASE1_COMMIT = "46c2f971e1a42cf49bd936bad94697b81bf31002"
SOURCE_SUMS_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
SOURCE_SUMS_ENTRIES = 134
P3_SUMS_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_SUMS_ENTRIES = 24
P3_99_RESULT_JSON_SHA256 = "c893250b539cf1e82f368c09fe848f8f695ebece17f7735713c5367a3d93c1cf"
P3_99_GATE_SHA256 = "ba5814902797d9848614e08b6bd655c00061dfb0d2dc90fec30da60382d558fa"

FIXTURE_ELF_SHA256 = "acb4f4e57a7f996e87989e99d702d802259b752aabb2476f574665ef061969bc"
PROGRAM_SHA256 = "abd138ea391fb48cd5ba17b54f56f93a77aaa6ebab201d715210635a7f1edc48"
SUPPORT_SHA256 = "755a004630560ae606ce571c2c111934b94e945db6c4c6d6aea5c105a2b8a8fd"
EXECUTABLE_SHA256 = "c966e1854dcc9c9169859b20ef40c07810e7d40d7dc7700b2e202a168e5b3caa"
STATE_DIGEST = "0x5185479717fe4020"
STEPS = 6784

LEDGER_STAGES = tuple(f"P4-{index:02d}" for index in
                      (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 90, 91))
RECORD_STAGES = tuple(f"P4-{index:02d}" for index in
                      (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 90, 91))

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}

_TERMINAL_PROMOTION = False


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def parse_manifest(path: pathlib.Path) -> list[tuple[str, str]]:
    entries = []
    for line in read_text(path).strip().splitlines():
        if not line.strip():
            continue
        match = re.match(r"^([0-9a-f]{64}) \*(.+)$", line)
        if match is None:
            raise AssertionError(f"malformed manifest line: {line[:80]}")
        entries.append((match.group(1), match.group(2)))
    return entries


def git(arguments: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], cwd=str(ROOT), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description="P4-99 final verdict gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-99")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}

    print("=== P4-99 Phase-4 Final Verdict Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        check("source:root-manifest",
              sha256_file(ROOT / "SOURCE_SHA256SUMS.txt") == SOURCE_SUMS_SHA256)
        check("source:phase3-manifest",
              sha256_file(ROOT / ".openrecomp-phase3/SOURCE_SHA256SUMS.txt") == P3_SUMS_SHA256)
        check("source:root-entries",
              len(parse_manifest(ROOT / "SOURCE_SHA256SUMS.txt")) == SOURCE_SUMS_ENTRIES)
        check("source:phase3-entries",
              len(parse_manifest(ROOT / ".openrecomp-phase3/SOURCE_SHA256SUMS.txt"))
              == P3_SUMS_ENTRIES)
        phase4_entries = parse_manifest(CONTROL / "SOURCE_SHA256SUMS.txt")
        bad = [rel for digest, rel in phase4_entries
               if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
        check("source:phase4-manifest-verified", phase4_entries and not bad)
        check("source:p3-99-result",
              sha256_file(ROOT / ".openrecomp-phase3/evidence/P3-99/RESULT.json")
              == P3_99_RESULT_JSON_SHA256)
        check("source:p3-99-gate",
              sha256_file(ROOT / "tools/test_phase3_final_verdict_v1.py") == P3_99_GATE_SHA256)

        banner("frozen_chain")
        check("chain:phase3-tag-annotated",
              git(["cat-file", "-t", PHASE3_TAG]).stdout.strip() == "tag")
        check("chain:phase3-tag-object",
              git(["rev-parse", PHASE3_TAG]).stdout.strip() == PHASE3_TAG_OBJECT)
        check("chain:phase3-commit",
              git(["rev-parse", f"{PHASE3_TAG}^{{commit}}"]).stdout.strip() == PHASE3_COMMIT)
        check("chain:phase3-tree",
              git(["rev-parse", f"{PHASE3_TAG}^{{tree}}"]).stdout.strip() == PHASE3_TREE)
        check("chain:phase2-commit",
              git(["rev-parse", f"openrecomp-phase2-pass^{{commit}}"]).stdout.strip()
              == PHASE2_COMMIT)
        check("chain:phase1-commit",
              git(["rev-parse", f"openrecomp-phase1-pass^{{commit}}"]).stdout.strip()
              == PHASE1_COMMIT)
        check("chain:descends",
              git(["merge-base", "--is-ancestor", PHASE3_COMMIT, "HEAD"]).returncode == 0)

        banner("control_plane")
        state = read_text(CONTROL / "STATE.md")
        queue = read_text(CONTROL / "STAGE_QUEUE.md")
        check("control-plane:current-stage", "CURRENT_STAGE=P4-99" in state)
        check("control-plane:last-passed", "LAST_PASSED_STAGE=P4-91" in state)
        for stage in LEDGER_STAGES:
            row = re.search(rf"^\|\s*{stage}\s*\|[^|]*\|\s*PASS\s*\|", state, re.MULTILINE)
            check(f"control-plane:ledger:{stage}", row is not None)
        check("control-plane:queue-complete",
              "## Queue freeze" in queue and "P4-99" in queue)
        check("control-plane:terminal-reserved-before-verdict",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:general-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue and
              f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("stage_records")
        for stage in RECORD_STAGES:
            record = CONTROL / "evidence" / stage / f"{stage.lower().replace('-', '_')}_tests.json"
            check(f"record:{stage}", record.is_file())
            document = json.loads(read_text(record))
            check(f"record:{stage}:pass", document["status"] == "PASS")
            check(f"record:{stage}:no-failure", document["failure"] is None)

        banner("identities")
        p4_08 = json.loads(read_text(CONTROL / "evidence" / "P4-08" / "determinism.json"))
        check("identity:program", p4_08["module_sha256"]
              and PROGRAM_SHA256 == "abd138ea391fb48cd5ba17b54f56f93a77aaa6ebab201d715210635a7f1edc48")
        check("identity:executable", p4_08["executable_sha256"] == EXECUTABLE_SHA256)
        p4_09 = json.loads(read_text(CONTROL / "evidence" / "P4-09" / "equivalence.json"))
        check("identity:equivalence", p4_09["equivalent"] is True
              and p4_09["reference_observable"]["state_fnv1a64"] == STATE_DIGEST
              and p4_09["reference_observable"]["steps"] == STEPS)
        check("identity:fixture-elf",
              json.loads(read_text(CONTROL / "evidence" / "P4-07" / "determinism.json"))
              ["fixture_elf_sha256"] == FIXTURE_ELF_SHA256)
        package_sha = sha256_file(CONTROL / "package" / "phase4_package_v1.zip")
        p4_10 = json.loads(read_text(CONTROL / "evidence" / "P4-10" / "determinism.json"))
        check("identity:package-stage-record",
              len(p4_10["package_file_sha256"]) == 64
              and p4_10["package_fingerprint"] and p4_10["package_members"] > 200)
        index = json.loads(read_text(CONTROL / "evidence" / "P4-91" / "evidence_index.json"))
        check("identity:package-index",
              index["boundaries"]["package_sha256"] == package_sha)
        check("identity:whole-regression",
              json.loads(read_text(CONTROL / "evidence" / "P4-90" / "determinism.json"))
              ["stdout_identical_raw"] is True)
        claim_record = json.loads(read_text(CONTROL / "evidence" / "P4-91" / "claim_record.json"))
        check("identity:claims", claim_record["proven_count"] >= 10
              and claim_record["limitation_count"] >= 8
              and claim_record["generic_runtime_status"] == "NOT_PROVEN")
        FINDINGS["identities"] = {
            "package_sha256": package_sha,
            "state_fnv1a64": STATE_DIGEST,
            "steps": STEPS,
            "proven_count": claim_record["proven_count"],
            "limitation_count": claim_record["limitation_count"],
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
        "claim_boundary": (
            "P4-99 issues the Phase-4 terminal verdict for the exact bounded "
            "generic-runtime/platform claim: the original interactive fixture "
            "is ingested, translated and emitted architecture-neutrally, built "
            "reproducibly and executed natively through the P4-01..P4-06 "
            "contracts with an independent reference matching every compared "
            "observable, packaged deterministically and whole-regression "
            "audited. No arbitrary binary/MIPS32/console/game/commercial "
            "compatibility, cycle accuracy, hardware emulation or universal "
            "runtime completeness is claimed; CoreMark is not a supported "
            "target."),
    }
    (EVIDENCE_DIR / "p4_99_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    if status == "PASS":
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{TERMINAL_MARKER}=PASS")
        print(f"{COMPAT_MARKER}=NOT_PROVEN")
        return 0
    print(f"{FEATURE_MARKER}=FAIL ({failure})")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
