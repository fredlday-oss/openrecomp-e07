#!/usr/bin/env python3
"""OpenRecomp Phase-9 final bounded verdict gate (P9-99).

The gate audits every Phase-9 stage record and issues the terminal markers
only for the exact evidence-supported bounded PS1 platform/runtime
integration claim:

* the frozen Phase-8 terminal boundary, terminal evidence and terminal audit
  records re-verify;
* every required Phase-9 stage (`P9-00` .. `P9-12`, `P9-90`, `P9-91`) is
  `PASS` with two byte-identical official runs, empty stderr and exit 0;
* the public fixture identity, deterministic emission set, reproducible native
  executable and native/reference agreement (no excluded observables) match
  the committed records;
* the claim ledger classifies every claim and keeps both permanent non-claims;
* the public-safety verification is clean.

On success it emits::

    OPENRECOMP_P9_99=PASS
    OPENRECOMP_PHASE9_FINAL_VERDICT_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=PASS
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Otherwise it emits `OPENRECOMP_P9_99=FAIL`, the terminal proof `NOT_PROVEN`
and both permanent non-claims.

Usage:

    python tools/test_phase9_final_verdict_v1.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
P8 = ROOT / ".openrecomp-phase8"
P9 = ROOT / ".openrecomp-phase9"
EVIDENCE = P9 / "evidence"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "fixture"))

import p9_emission_v1 as emission  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p9_public_fixture_v1 as fixture  # noqa: E402

STAGE = "P9-99"
FEATURE_MARKER = "OPENRECOMP_PHASE9_FINAL_VERDICT_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"

BASELINE_COMMIT = "61136fc37cf0810e64241addd8f57a91872bc0af"
BASELINE_TREE = "f9262497b82fe0027c3b23432ba7bd8cbccdf433"
BRANCH = "phase8/mips32-end-to-end-native-v1"

REQUIRED_STAGES = {
    "P9-00": "OPENRECOMP_PHASE9_BOUNDARY_V1=PASS",
    "P9-01": "OPENRECOMP_PHASE9_INGESTION_V1=PASS",
    "P9-02": "OPENRECOMP_PHASE9_MEMORY_MAP_V1=PASS",
    "P9-03": "OPENRECOMP_PHASE9_PIPELINE_V1=PASS",
    "P9-04": "OPENRECOMP_PHASE9_TRANSLATION_CLOSURE_V1=PASS",
    "P9-05": "OPENRECOMP_PHASE9_BIOS_BOUNDARY_V1=PASS",
    "P9-06": "OPENRECOMP_PHASE9_GPU_BOUNDARY_V1=PASS",
    "P9-07": "OPENRECOMP_PHASE9_INPUT_TIMER_V1=PASS",
    "P9-08": "OPENRECOMP_PHASE9_SPU_BOUNDARY_V1=PASS",
    "P9-09": "OPENRECOMP_PHASE9_CDROM_BOUNDARY_V1=PASS",
    "P9-10": "OPENRECOMP_PHASE9_NATIVE_EXECUTION_V1=PASS",
    "P9-11": "OPENRECOMP_PHASE9_PRIVATE_VALIDATION_V1=PASS",
    "P9-12": "OPENRECOMP_PHASE9_HARDENING_V1=PASS",
    "P9-90": "OPENRECOMP_PHASE9_WHOLE_REGRESSION_V1=PASS",
    "P9-91": "OPENRECOMP_PHASE9_EVIDENCE_INDEX_V1=PASS",
}

FROZEN_P8_HASHES = {
    ".openrecomp-phase8/evidence/P8-99/RESULT.md": "b07c3ec76c591df7999599e0fa5f1f43f0a1854462b45da96bc8523b2cb04204",
    ".openrecomp-phase8/evidence/P8-99/terminal_verdict.json": "ffe1b89d1284435cbb9dd53318025ee052ad0fa58b1f8a304736a381712dc693",
    ".openrecomp-phase8/evidence/P8-99/verdict_record.json": "fa9d62c79ab6399981e1acedbedbd07a149daec2c6ea4bde1dc7aee3a7d52738",
    ".openrecomp-phase8/evidence/P8-99/p8_99_tests.json": "ff8ed0a79569b95810527b1a395ece4aec3b6eedba9054f704cd0dfd1bbd7f77",
    ".openrecomp-phase8/evidence/P8-99/official_runs.json": "459c5f397681e49cfb6830d8f1687e5923120bb061864f8319a0c8eb15dc333d",
    ".openrecomp-phase8/STATE.md": "ef56426db4f17deef78635a35ea8074ef6c7a5f17926cd18f4687f6bea63bcd4",
    ".openrecomp-phase8/STAGE_QUEUE.md": "5f1dc76669db00f766afcb55fa5d943b5b3498333cfc9cc8b6e63971ceeb1fbf",
    ".openrecomp-phase8/HANDOFF.md": "01abbc46c810b9da697932d34e3be7b18acab88b54a630ed777ab96f4da60c70",
    ".openrecomp-phase8/SOURCE_SHA256SUMS.txt": "5ac27eb1f23ae412a14e94c62a80f811b7a1670e53b404356b49595d1f9f4221",
    ".openrecomp-phase8/CONTROL_POLICY.md": "50bd69203c78f8ff45439f133a0b4dd01f54e1dcf4175a1886a49d0effff20b7",
    ".openrecomp-phase8/SCOPE.md": "82bc03b864b85509c7eb23a5e1aea124edc431f94d412064fa4d076c6b349ca1",
    ".openrecomp-phase8/ACCELERATION_POLICY.md": "02a10bc6aaa9c2d4accd8d9e5eab30c6e608c09d7090148e180dc4babc36bf95",
    ".openrecomp-phase8/EVIDENCE_SCHEMA.md": "4c7b4473972bed35bbdc0e6df54d642886b6697112361f2a8f04a6a659b86acf",
    ".openrecomp-phase8/FIXTURE_POLICY.md": "723e5794c836371ece147af53039a4134b788c1ea9ee9fc5d52a91edc330f879",
    ".openrecomp-phase8/evidence/README.md": "7167bc52738c562ff84e48c58f4381dc858a972cb7044f1cb850d4c5302ccd27",
}

PUBLIC_FIXTURE_SHA256 = "17466bc17edde54f4d371ae22281b9fb31cd9114c3c293aa7da103751c32c3da"
PUBLIC_FIXTURE_SIZE = 2240
EXECUTABLE_SHA256 = "5c016be2f043760ef6ac1a7c37c60bbe335c271f307b8e05275f75e0ee2ceb9d"
NATIVE_OBSERVABLE = {
    "failed": 0,
    "error": "",
    "exit_status": "0x00000002",
    "registers_digest": "0x17f2292e1363f17f",
    "memory_digest": "0x28d892afac2d8496",
    "gpu_events": 2,
    "gpu_digest": "0x6a326cbc723c24b1",
    "input_events": 2,
    "input_digest": "0xe35ba7548adde99a",
    "spu_events": 1,
    "spu_digest": "0x55788edbf95cf3ea",
    "cdrom_events": 1,
    "cdrom_digest": "0x0dc54fdf2d1b3c3c",
    "reads": 1,
    "writes": 4,
    "denied": 0,
    "host_calls": 0,
}

LEDGER_EXPECTED = {"PROVEN": 13, "BOUNDED": 3, "NOT_PROVEN": 10, "NOT_TESTED": 1}

DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)

HOST_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/|/root/)")

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase9/evidence/P9-99")
    parser.add_argument("--private-fixture", default=os.environ.get("OPENRECOMP_PSX_PRIVATE_FIXTURE", str(DEFAULT_PRIVATE_FIXTURE)))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        # --- frozen Phase-8 boundary and terminal records -------------------
        import subprocess

        commit_tree = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", f"{BASELINE_COMMIT}^{{tree}}"],
            capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip()
        check("baseline:commit-tree", commit_tree == BASELINE_TREE, commit_tree)
        branch = subprocess.run(
            ["git", "-C", str(ROOT), "branch", "--show-current"],
            capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip()
        check("baseline:branch", branch == BRANCH, branch)
        for rel, digest in sorted(FROZEN_P8_HASHES.items()):
            check(f"frozen:p8-terminal:{rel}", sha256_file(ROOT / rel) == digest, digest)
        verdict8 = json.loads((P8 / "evidence" / "P8-99" / "terminal_verdict.json").read_text(encoding="utf-8"))
        check("frozen:p8-terminal-decision", verdict8.get("decision") == "PASS", str(verdict8.get("decision")))

        # --- required Phase-9 stage records ---------------------------------
        for stage, marker in sorted(REQUIRED_STAGES.items()):
            stage_dir = EVIDENCE / stage
            check(f"stage:{stage}:result", (stage_dir / "RESULT.md").is_file(), stage)
            runs = json.loads((stage_dir / "official_runs.json").read_text(encoding="utf-8"))
            check(f"stage:{stage}:two-runs", runs["identical_raw"] and runs["identical_lf"], "identical")
            check(f"stage:{stage}:stderr", runs["stderr_empty_both"], "empty")
            check(f"stage:{stage}:exit", runs["returncode_zero_both"], "zero")
            check(f"stage:{stage}:markers", runs["markers_present_both"], "markers")
            check(f"stage:{stage}:gate-marker", any(marker in recorded for recorded in runs["runs"][0]["markers"]), marker)
            tests = json.loads((stage_dir / f"p9_{stage.split('-')[1]}_tests.json").read_text(encoding="utf-8"))
            check(f"stage:{stage}:tests", tests["status"] == "PASS" and tests["failed"] == 0, tests["status"])

        # --- P9-90 regression record ----------------------------------------
        whole = json.loads((EVIDENCE / "P9-90" / "whole_regression.json").read_text(encoding="utf-8"))
        check("p9-90:decision", whole["decision"] == "PASS", str(whole["decision"]))
        check("p9-90:phase9-gates", len(whole["phase9_stage_gates"]) == 13, str(len(whole["phase9_stage_gates"])))
        check("p9-90:p8-90-tests", whole["phase8_90"]["tests"] == 215, str(whole["phase8_90"]["tests"]))
        check("p9-90:reverified", whole["phase8_90"]["total_reverified_tests"] == 1463, str(whole["phase8_90"]["total_reverified_tests"]))
        check("p9-90:total", whole["total_reverified_tests"] == 3113, str(whole["total_reverified_tests"]))

        # --- P9-91 ledger ----------------------------------------------------
        ledger = json.loads((EVIDENCE / "P9-91" / "claim_ledger.json").read_text(encoding="utf-8"))
        counts: dict[str, int] = {}
        for item in ledger["claims"]:
            counts[item["class"]] = counts.get(item["class"], 0) + 1
        check("ledger:counts", counts == LEDGER_EXPECTED, json.dumps(counts, sort_keys=True))
        check(
            "ledger:permanent-non-claims",
            tuple(ledger["permanent_non_claims"]) == (f"{GENERAL_MARKER}=NOT_PROVEN", f"{PLAYABILITY_MARKER}=NOT_PROVEN"),
            "permanent",
        )
        check("ledger:terminal-reserved-at-p9-91", ledger["terminal_claim_status_at_p9_91"] == "NOT_PROVEN", "reserved")

        # --- public fixture and native/reference agreement -------------------
        public_bytes = fixture.build_fixture()
        check("fixture:sha256", hashlib.sha256(public_bytes).hexdigest() == PUBLIC_FIXTURE_SHA256, hashlib.sha256(public_bytes).hexdigest())
        check("fixture:size", len(public_bytes) == PUBLIC_FIXTURE_SIZE, str(len(public_bytes)))
        emission_record = json.loads((EVIDENCE / "P9-10" / "emission.json").read_text(encoding="utf-8"))
        check("emission:file-set", tuple(item["name"] for item in emission_record["files"]) == emission.EMISSION_NAMES, "names")
        native_record = json.loads((EVIDENCE / "P9-10" / "native_execution.json").read_text(encoding="utf-8"))
        check("native:executable", native_record["executable_sha256"] == EXECUTABLE_SHA256, native_record["executable_sha256"])
        check("native:observable", native_record["observable"] == NATIVE_OBSERVABLE, "observable")
        equivalence = json.loads((EVIDENCE / "P9-10" / "equivalence.json").read_text(encoding="utf-8"))
        check("equivalence:no-exclusions", equivalence["excluded_observables"] == [], "none")
        check("equivalence:no-mismatches", equivalence["mismatches"] == {}, "none")
        rebuild = json.loads((EVIDENCE / "P9-12" / "rebuild.json").read_text(encoding="utf-8"))
        check("rebuild:executable", rebuild["executable_sha256"] == EXECUTABLE_SHA256, rebuild["executable_sha256"])
        check("rebuild:agreement", rebuild["reference_agreement"] is True, "agreement")

        # --- private validation boundary -------------------------------------
        private_record = json.loads((EVIDENCE / "P9-11" / "private_validation.json").read_text(encoding="utf-8"))
        check("private:not-a-criterion", private_record["is_pass_criterion"] is False, "false")
        check("private:execution-status", private_record["bounded_execution"]["status"] == "NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED", private_record["bounded_execution"]["status"])
        check("private:first-blocker", private_record["frontier"]["first_blocker"]["site_hex"] == "0x80013390", "0x80013390")

        # --- scope guards ----------------------------------------------------
        scope = (P9 / "SCOPE.md").read_text(encoding="utf-8")
        state = (P9 / "STATE.md").read_text(encoding="utf-8")
        queue = (P9 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        policy = (P9 / "CONTROL_POLICY.md").read_text(encoding="utf-8")
        for name, text in (("scope", scope), ("state", state), ("queue", queue), ("policy", policy)):
            check(f"guards:{name}:general", f"{GENERAL_MARKER}=NOT_PROVEN" in text, name)
            check(f"guards:{name}:playability", f"{PLAYABILITY_MARKER}=NOT_PROVEN" in text, name)
        check("guards:terminal-name", TERMINAL_MARKER in scope, "terminal claim")
        rows = re.findall(r"^\| (P9-[0-9]{2}) \| [^|]+ \| ([A-Z_]+) \|", queue, flags=re.MULTILINE)
        row_status = {stage: status for stage, status in rows}
        check("guards:queue-complete", all(row_status.get(stage) == "PASS" for stage in REQUIRED_STAGES), json.dumps(row_status, sort_keys=True))
        check("guards:queue-terminal", row_status.get("P9-99") in ("QUEUED", "PASS"), str(row_status.get("P9-99")))

        # --- public safety ---------------------------------------------------
        fixture_path = pathlib.Path(options.private_fixture)
        payload = psx.ingest(fixture_path.read_bytes()).payload if fixture_path.is_file() else None
        leaks: list[str] = []
        host_paths: list[str] = []
        own = (EVIDENCE / "P9-99").resolve()
        for path in sorted(EVIDENCE.rglob("*")):
            if not path.is_file() or own in path.resolve().parents:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            relative = path.relative_to(ROOT).as_posix()
            if HOST_PATH_RE.search(text):
                host_paths.append(relative)
            if payload is not None:
                lowered = text.lower()
                if payload[:64].hex() in lowered:
                    leaks.append(relative + ":hex")
                if base64.b64encode(payload[:48]).decode("ascii") in text:
                    leaks.append(relative + ":base64")
                for start in range(0, min(len(payload), 512)):
                    run = payload[start : start + 8]
                    if len(run) == 8 and all(32 <= byte < 127 for byte in run):
                        if run.decode("ascii") in text:
                            leaks.append(relative + ":ascii")
                            break
        check("safety:no-payload-leaks", leaks == [], json.dumps(leaks))
        check("safety:no-host-paths", host_paths == [], json.dumps(host_paths))

        decision = "PASS"
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
        decision = "FAIL"
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})
        decision = "FAIL"

    status = "PASS" if decision == "PASS" and all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    terminal = f"{TERMINAL_MARKER}={'PASS' if status == 'PASS' else 'NOT_PROVEN'}"
    results = sorted(RESULTS, key=lambda item: item["check"])
    record = {
        "stage": STAGE,
        "stage_name": "Final bounded verdict",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": sum(1 for item in results if item["status"] != "PASS"),
        "checks": results,
        "failure": None if status == "PASS" else [item for item in results if item["status"] != "PASS"],
        "markers": {
            "stage": f"OPENRECOMP_P9_99={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={len(results)}",
            "terminal": terminal,
            "general": f"{GENERAL_MARKER}=NOT_PROVEN",
            "playability": f"{PLAYABILITY_MARKER}=NOT_PROVEN",
        },
    }
    write_json(evidence / "p9_99_tests.json", record)
    terminal_verdict = {
        "stage": STAGE,
        "decision": status,
        "fixture": {
            "label": fixture.PUBLIC_FIXTURE.label,
            "sha256": PUBLIC_FIXTURE_SHA256,
            "size": PUBLIC_FIXTURE_SIZE,
        },
        "markers_issued": [
            terminal,
            f"{GENERAL_MARKER}=NOT_PROVEN",
            f"{PLAYABILITY_MARKER}=NOT_PROVEN",
        ],
        "required_stages": [
            {"stage": stage, "gate_marker": marker, "outcome": "PASS"}
            for stage, marker in sorted(REQUIRED_STAGES.items())
        ],
        "native_reference_agreement": {
            "excluded_observables": [],
            "executable_sha256": EXECUTABLE_SHA256,
            "observable": NATIVE_OBSERVABLE,
        },
        "whole_regression": {
            "phase9_gates": 13,
            "phase8_terminal_audits": 3,
            "total_reverified_tests": 3113,
        },
        "scope_guards": {
            "general_ps1_compatibility": "NOT_PROVEN",
            "hercules_playability": "NOT_PROVEN",
            "arbitrary_psx_exe": "NOT_PROVEN",
            "bios_emulation": "NOT_PROVEN",
            "gpu_spu_cdrom_hardware": "NOT_PROVEN",
            "cop0_gte": "NOT_PROVEN",
            "interrupts": "NOT_PROVEN",
            "ps2": "NOT_PROVEN",
        },
    }
    write_json(evidence / "terminal_verdict.json", terminal_verdict)
    write_json(
        evidence / "verdict_record.json",
        {
            "stage": STAGE,
            "decision": status,
            "tests": len(results),
            "fixture_sha256": PUBLIC_FIXTURE_SHA256,
            "terminal_marker": terminal,
            "general_marker": f"{GENERAL_MARKER}=NOT_PROVEN",
            "playability_marker": f"{PLAYABILITY_MARKER}=NOT_PROVEN",
        },
    )

    for item in results:
        if item["status"] != "PASS":
            print(f"FAIL: {item['check']} :: {item.get('detail', '')}")
    print(f"OPENRECOMP_P9_99={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(terminal)
    print(f"{GENERAL_MARKER}=NOT_PROVEN")
    print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
