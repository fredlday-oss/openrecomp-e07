#!/usr/bin/env python3
"""OpenRecomp Phase-6 evidence index + compatibility matrix gate (P6-91).

Verifies the complete Phase-6 evidence index (every stage evidence file with
size and sha256, control-plane hashes, frozen boundary identities, manifest
entries) against an independent filesystem walk, and the claim ledger using
the frozen vocabulary PROVEN / BOUNDED / UNPROVEN / UNSUPPORTED / NOT TESTED
with the four required areas kept separate:

1. the Phase-5 public NROM result (anchored to the frozen P5-91 record);
2. the Phase-6 public MMC1 result;
3. the private local TMNT compatibility observation (non-redistributed, exact
   remaining blockers recorded);
4. general NES compatibility (`OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=
   NOT_PROVEN`, never promoted).

On success it emits::

    OPENRECOMP_P6_91=PASS
    OPENRECOMP_PHASE6_EVIDENCE_INDEX_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_evidence_index_v1.py \
        --evidence-dir .openrecomp-phase6/evidence/P6-91
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
PHASE6 = ROOT / ".openrecomp-phase6"
for entry in (str(PHASE6 / "src"), str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_evidence_index_v1 as index_module  # noqa: E402

STAGE = "P6-91"
STAGE_MARKER = "OPENRECOMP_P6_91"
FEATURE_MARKER = "OPENRECOMP_PHASE6_EVIDENCE_INDEX_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

PRIVATE_PATH = r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes"
PRIVATE_SHA256 = "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
PRIVATE_SIZE = 262160

MIN_EVIDENCE_FILES = 120
MIN_PHASE6_PROVEN = 10
MIN_PHASE6_BOUNDED = 4
MIN_PRIVATE_OBSERVATIONS = 4
MIN_PRIVATE_BLOCKERS = 4
MIN_UNPROVEN = 8
MIN_UNSUPPORTED = 9
MIN_NOT_TESTED = 8

ANCHORS = {
    ".openrecomp-phase5/evidence/P5-91/claim_record.json":
        "ef926dacb99315400a2631abbbaca909ccc794cec766deedd246bca9c4db2149",
    ".openrecomp-phase5/evidence/P5-99/p5_99_tests.json":
        "b0e8267c70ab2e990ca74665d8020ba463280447dd9f5fb370f4411cfb6e72c9",
    ".openrecomp-phase6/evidence/P6-10/tmnt_pipeline.json":
        "0b8c9014fa11f9e363f1cfb1c569048f786b8baec2117769adb862b375a3ebdc",
    ".openrecomp-phase6/evidence/P6-12/workflow.json":
        "4ae486db95cc80418e8ac146396139f67367d22edaae2cd5b2495ef87ca5aeae",
    ".openrecomp-phase6/evidence/P6-13/private_workflow.json":
        "07ce9a558582ed1178b08ff158e2bff41ce9939e0416aaf07fb0dc64f180dd0e",
    ".openrecomp-phase6/evidence/P6-13/frontier_record.json":
        "e49a0b3422d6a65b5b50ce820db5c9f9d02ef3662aa114f5287db3a8232bf484",
    ".openrecomp-phase6/evidence/P6-90/whole_regression.json":
        "ed4d03cc3fe6e748e24521d465422b81f2d0ef13cc65388e2c86e90f4c5700b7",
}

EXPECTED_PRIVATE_BLOCKERS = (
    ("unsupported_opcode", "0xC570"),
    ("unresolved_indirect_control_flow", "0x86E8"),
    ("bank_state_unresolved", "1048"),
    ("platform_runtime_not_tested", "until translation completes"),
)

REGRESSIONS = (
    ("tools/test_phase6_private_workflow_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-91/regression_p6_13"]),
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


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def canonical(document: Any) -> bytes:
    return index_module.canonical(document)


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def run_regression(script: str, extra: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / script), *extra], cwd=str(ROOT),
        capture_output=True)
    markers = [line for line in
               completed.stdout.decode("utf-8", errors="replace").splitlines()
               if line.startswith("OPENRECOMP_")]
    return {
        "script": script,
        "extra": extra,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": sha256_bytes(completed.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
        "markers": markers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P6-91 evidence index and compatibility matrix gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-91")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-91 Evidence Index + Compatibility Matrix Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        manifest = PHASE6 / "SOURCE_SHA256SUMS.txt"
        check("source:manifest-exists", manifest.is_file())
        entries = []
        for line in manifest.read_text(encoding="utf-8").strip().splitlines():
            digest, rel = line.split(" *", 1)
            entries.append((digest, rel))
        bad = [rel for digest, rel in entries
               if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
        check("source:manifest-verified", bool(entries) and not bad)

        banner("frozen_chain")
        check("chain:phase5-tag-object",
              subprocess.run(["git", "rev-parse", "openrecomp-phase5-pass"],
                             cwd=str(ROOT), capture_output=True, text=True
                             ).stdout.strip() == PHASE5_TAG_OBJECT)
        check("chain:phase5-commit",
              subprocess.run(["git", "rev-parse", "openrecomp-phase5-pass^{commit}"],
                             cwd=str(ROOT), capture_output=True, text=True
                             ).stdout.strip() == PHASE5_COMMIT)
        check("chain:phase5-tree",
              subprocess.run(["git", "rev-parse", "openrecomp-phase5-pass^{tree}"],
                             cwd=str(ROOT), capture_output=True, text=True
                             ).stdout.strip() == PHASE5_TREE)
        check("chain:descends",
              subprocess.run(["git", "merge-base", "--is-ancestor", PHASE5_COMMIT,
                              "HEAD"], cwd=str(ROOT), capture_output=True
              ).returncode == 0)

        banner("control_plane")
        state = (PHASE6 / "STATE.md").read_text(encoding="utf-8")
        queue = (PHASE6 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P6-91 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("anchors")
        observed_anchors = {}
        for rel, digest in sorted(ANCHORS.items()):
            path = ROOT / rel
            check(f"anchor:present:{rel}", path.is_file())
            actual = sha256_file(path)
            observed_anchors[rel] = actual
            check(f"anchor:hash:{rel}", actual == digest)
        check("anchor:phase5-claim-record",
              observed_anchors[".openrecomp-phase5/evidence/P5-91/"
                               "claim_record.json"]
              == index_module.P5_91_CLAIM_RECORD_SHA256)
        p6_10 = json.loads(
            (PHASE6 / "evidence" / "P6-10" / "tmnt_pipeline.json").read_text(
                encoding="utf-8"))
        p6_13 = json.loads(
            (PHASE6 / "evidence" / "P6-13" / "frontier_record.json").read_text(
                encoding="utf-8"))
        check("anchor:private-blockers-stable",
              p6_10["frontier"]["candidate"]["stop"]["address"] == 0xC570
              and [item["classification"]
                   for item in p6_13["stop_reasons"]]
              == ["unsupported_opcode", "unresolved_indirect_control_flow",
                  "bank_state_unresolved", "platform_runtime_not_tested"])

        banner("evidence_index")
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
        mismatched = [item["path"] for item in index_a["files"]
                      if item["size"] != (ROOT / item["path"]).stat().st_size
                      or item["sha256"] != sha256_file(ROOT / item["path"])]
        check("index:hashes", mismatched == [])
        control_ok = all(
            item["sha256"] == sha256_file(ROOT / item["path"])
            for item in index_a["control_plane"])
        check("index:control-plane", control_ok)
        manifest_ok = all(
            item["sha256"] == sha256_file(ROOT / item["path"])
            for item in index_a["phase6_manifest"])
        check("index:phase6-manifest", manifest_ok)
        check("index:boundaries",
              index_a["boundaries"] == index_module.BOUNDARIES)
        check("index:phase5-result",
              index_a["phase5_public_result"]["state"] == "PASS"
              and index_a["phase5_public_result"]["claim_record_sha256"]
              == index_module.P5_91_CLAIM_RECORD_SHA256)
        check("index:no-rom-bytes",
              all(item["size"] != PRIVATE_SIZE
                  or item["sha256"] != PRIVATE_SHA256
                  for item in index_a["files"]))
        FINDINGS["indexed_files"] = index_a["evidence_files"]

        banner("claim_ledger")
        record_a = index_module.build_claim_record()
        record_b = index_module.build_claim_record()
        check("ledger:deterministic", canonical(record_a) == canonical(record_b))
        ledger = record_a["ledger"]
        check("ledger:sections-distinct",
              set(ledger) == {"phase5_public_nrom", "phase6_public_mmc1",
                              "private_tmnt_compatibility", "general_nes"}
              and ledger["phase5_public_nrom"]["section"].startswith(
                  "Phase-5 public NROM result")
              and ledger["phase6_public_mmc1"]["section"].startswith(
                  "Phase-6 public MMC1 result")
              and ledger["private_tmnt_compatibility"]["section"].startswith(
                  "private local compatibility")
              and ledger["general_nes"]["section"]
              == "general NES compatibility")
        check("ledger:phase5-phase6-separate",
              "P5" in ledger["phase5_public_nrom"]["evidence"]
              and "P6" in ledger["phase6_public_mmc1"]["evidence"])
        check("ledger:phase6-proven",
              record_a["proven_count"] >= MIN_PHASE6_PROVEN
              and ledger["phase6_public_mmc1"]["status"] == "PROVEN")
        check("ledger:phase6-bounded",
              record_a["bounded_count"] >= MIN_PHASE6_BOUNDED
              and any("MMC1_SUBSET_V1" in item["claim"]
                      for item in ledger["phase6_public_mmc1"]["bounded"]))
        check("ledger:private-observations",
              record_a["private_observation_count"]
              >= MIN_PRIVATE_OBSERVATIONS
              and ledger["private_tmnt_compatibility"]["status"] == "UNPROVEN"
              and ledger["private_tmnt_compatibility"]["fixture"]
              == "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE")
        check("ledger:private-identity",
              ledger["private_tmnt_compatibility"]["image_sha256"]
              == PRIVATE_SHA256
              and ledger["private_tmnt_compatibility"]["image_size"]
              == PRIVATE_SIZE)
        blockers = ledger["private_tmnt_compatibility"][
            "exact_remaining_blockers"]
        check("ledger:private-blockers-count",
              len(blockers) >= MIN_PRIVATE_BLOCKERS)
        check("ledger:private-blockers-exact",
              all(any(classification == entry["classification"]
                      and token in entry["detail"]
                      for entry in blockers)
                  for classification, token in EXPECTED_PRIVATE_BLOCKERS))
        check("ledger:private-no-public-claim",
              ledger["private_tmnt_compatibility"]["public_claim"]
              .startswith("none"))
        check("ledger:general-unproven",
              record_a["unproven_count"] >= MIN_UNPROVEN
              and ledger["general_nes"]["status"] == "UNPROVEN"
              and record_a["generic_runtime_status"] == "NOT_PROVEN")
        check("ledger:general-unsupported",
              record_a["unsupported_count"] >= MIN_UNSUPPORTED
              and any("MMC1A" in item["area"]
                      for item in ledger["general_nes"]["unsupported"]))
        check("ledger:general-not-tested",
              record_a["not_tested_count"] >= MIN_NOT_TESTED
              and any("PAL" in item["area"]
                      for item in ledger["general_nes"]["not_tested"]))
        check("ledger:markers-reserved",
              record_a["terminal_marker"]
              == f"{TERMINAL_MARKER}=NOT_PROVEN"
              and record_a["compatibility_marker"]
              == f"{COMPAT_MARKER}=NOT_PROVEN")
        text = canonical(record_a).decode("utf-8")
        check("ledger:vocabulary",
              all(word in text for word in
                  ("PROVEN", "BOUNDED", "UNPROVEN", "UNSUPPORTED",
                   "NOT TESTED")))
        check("ledger:limitations",
              len(record_a["limitations"]) >= 6
              and any("TMNT" in item for item in record_a["limitations"]))

        banner("stage_records")
        for stage in index_module.STAGES:
            record_path = (PHASE6 / "evidence" / stage
                           / f"{stage.lower().replace('-', '_')}_tests.json")
            check(f"record:{stage}:present", record_path.is_file())
            document = json.loads(record_path.read_text(encoding="utf-8"))
            check(f"record:{stage}:pass",
                  document["status"] == "PASS" and document["failure"] is None)
        FINDINGS["stage_records"] = list(index_module.STAGES)

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        check("regression:p6-13-marker",
              any("OPENRECOMP_P6_13=PASS" in marker
                  for marker in regressions[0]["markers"]))
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("evidence_index.json", index_a)
        write_json("claim_record.json", record_a)
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        if pathlib.Path(PRIVATE_PATH).is_file():
            rom = pathlib.Path(PRIVATE_PATH).read_bytes()
            last_bank = rom[-0x4000:]
            for name, data in EVIDENCE_WRITES.items():
                check(f"hygiene:no-private-rom-bytes:{name}", rom not in data)
                check(f"hygiene:no-private-bank-bytes:{name}",
                      last_bank not in data)
        check("hygiene:private-observation-recorded",
              PRIVATE_SHA256 in EVIDENCE_WRITES["claim_record.json"].decode(
                  "utf-8"))
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
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
    (EVIDENCE_DIR / "p6_91_tests.json").write_text(
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
