#!/usr/bin/env python3
"""OpenRecomp Phase-10 final bounded verdict gate (P10-99).

The gate audits every Phase-10 stage record and issues the terminal markers
only for the exact evidence-supported bounded claim:

* the frozen Phase-9 terminal boundary and the frozen Phase-8 terminal records
  re-verify;
* every required Phase-10 stage (`P10-00` .. `P10-12`, `P10-90`, `P10-91`) is
  `PASS` with two byte-identical official runs, empty stderr, exit 0 and its
  gate marker present;
* the `P10-90` whole-regression record and the `P10-91` proof matrix and claim
  ledger verify, with the terminal marker still reserved at `P10-91`;
* the exact private fixture identity, the native execution evidence and the
  exact highest milestone (`A`) match the committed records;
* the scope guards keep the permanent general-PS1 non-claim and the playability
  non-claim, and the public-safety verification is clean.

On success it emits::

    OPENRECOMP_P10_99=PASS
    OPENRECOMP_PHASE10_FINAL_VERDICT_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=PASS
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Otherwise it emits `OPENRECOMP_P10_99=FAIL`, the terminal proof `NOT_PROVEN`
and both non-claims.

Usage:

    python tools/test_phase10_final_verdict_v1.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
P10 = ROOT / ".openrecomp-phase10"
EVIDENCE = P10 / "evidence"

STAGE = "P10-99"
FEATURE_MARKER = "OPENRECOMP_PHASE10_FINAL_VERDICT_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

BASELINE_COMMIT = "08c639d9032a364163f2985432744be420d402eb"
BASELINE_TREE = "900dccf06ce3d5df7b499a9f05a6ceea060114d7"
FROZEN_BRANCH = "phase8/mips32-end-to-end-native-v1"

REQUIRED_STAGES = {
    "P10-00": "OPENRECOMP_PHASE10_BOUNDARY_V1=PASS",
    "P10-01": "OPENRECOMP_PHASE10_BREAK_V1=PASS",
    "P10-02": "OPENRECOMP_PHASE10_STRUCTURE_V1=PASS",
    "P10-03": "OPENRECOMP_PHASE10_SEMANTICS_V1=PASS",
    "P10-04": "OPENRECOMP_PHASE10_BIOS_V1=PASS",
    "P10-05": "OPENRECOMP_PHASE10_NATIVE_ENTRY_V1=PASS",
    "P10-06": "OPENRECOMP_PHASE10_IO_DISCOVERY_V1=PASS",
    "P10-07": "OPENRECOMP_PHASE10_GPU_FRONTIER_V1=PASS",
    "P10-08": "OPENRECOMP_PHASE10_TIMING_FRONTIER_V1=PASS",
    "P10-09": "OPENRECOMP_PHASE10_DISC_FRONTIER_V1=PASS",
    "P10-10": "OPENRECOMP_PHASE10_INPUT_SPU_FRONTIER_V1=PASS",
    "P10-11": "OPENRECOMP_PHASE10_MILESTONE_V1=PASS",
    "P10-12": "OPENRECOMP_PHASE10_HARDENING_V1=PASS",
    "P10-90": "OPENRECOMP_PHASE10_WHOLE_REGRESSION_V1=PASS",
    "P10-91": "OPENRECOMP_PHASE10_EVIDENCE_CLOSURE_V1=PASS",
}

FROZEN_P9_HASHES = {
    ".openrecomp-phase9/evidence/P9-99/terminal_verdict.json":
        "5d4c70008436925c3c986a4166376bc322400c119ea3ea24df234ba2eca4d783",
    ".openrecomp-phase9/evidence/P9-99/verdict_record.json":
        "96337230b155694ba9f150bb5b6201388ad74279956c11ced296bfc736b7dcae",
    ".openrecomp-phase9/evidence/P9-99/RESULT.md":
        "2ef6752fd1187883ebe9dd9814d286448a8f061056d3456d273dfdcf83261383",
    ".openrecomp-phase9/STATE.md":
        "11267465040b7f36ff96b422c6f7b711dee50e1c7acdc745f486b53adda1157e",
    ".openrecomp-phase9/STAGE_QUEUE.md":
        "93eec1dc331b877c81572a25997be1364c0b62e742032a1de3e18caf77d8f7a8",
    ".openrecomp-phase9/SOURCE_SHA256SUMS.txt":
        "ef72fbb1dbf75ad45fbf71940e9eca4725b246442c3e4be231ba77cacdfedb46",
    ".openrecomp-phase9/CONTROL_POLICY.md":
        "1bdbb7c5075d8542999a0d5336120ca705e076d38e2ab838aef1d5206323815b",
    ".openrecomp-phase9/FIXTURE_POLICY.md":
        "efc13de51cba3eb6e8c3f21898c63f503a6ce4808d72a489d94399334ccd2675",
    ".openrecomp-phase9/EVIDENCE_SCHEMA.md":
        "ceb1e39dc7dee28d541c3e42fdd85129547b606748e02825467e6e97b4a2796e",
    ".openrecomp-phase9/SCOPE.md":
        "d45f4d748dfc053623f6cf57114ca1f65957302db80b8c53649aead4caf99b71",
}

FROZEN_P8_HASHES = {
    ".openrecomp-phase8/evidence/P8-99/terminal_verdict.json":
        "ffe1b89d1284435cbb9dd53318025ee052ad0fa58b1f8a304736a381712dc693",
    ".openrecomp-phase8/evidence/P8-99/RESULT.md":
        "b07c3ec76c591df7999599e0fa5f1f43f0a1854462b45da96bc8523b2cb04204",
    ".openrecomp-phase8/evidence/P8-91/evidence_index.json":
        "9133c838980091d5b72775fed0678e5895cf90c858eb18549de5ced10c7772f7",
    ".openrecomp-phase8/evidence/P8-90/p8_90_tests.json":
        "782597be2f9bd4b4a834d55094a3304616675857b88e4b84abc509bbdd658912",
    ".openrecomp-phase8/STATE.md":
        "ef56426db4f17deef78635a35ea8074ef6c7a5f17926cd18f4687f6bea63bcd4",
    ".openrecomp-phase8/SOURCE_SHA256SUMS.txt":
        "5ac27eb1f23ae412a14e94c62a80f811b7a1670e53b404356b49595d1f9f4221",
}

LEDGER_COUNTS = {"PROVEN": 14, "BOUNDED": 5, "NOT_PROVEN": 15, "NOT_TESTED": 2}

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


def load(relative: str) -> dict:
    return json.loads((EVIDENCE / relative).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-99")
    parser.add_argument("--private-fixture", default=os.environ.get("OPENRECOMP_PSX_PRIVATE_FIXTURE", str(DEFAULT_PRIVATE_FIXTURE)))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        # --- frozen boundary and terminal records ----------------------------
        commit_tree = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", f"{BASELINE_COMMIT}^{{tree}}"],
            capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip()
        check("baseline:commit-tree", commit_tree == BASELINE_TREE, commit_tree)
        frozen_tip = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", FROZEN_BRANCH],
            capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip()
        check("baseline:frozen-branch-tip", frozen_tip == BASELINE_COMMIT, frozen_tip)
        for rel, digest in sorted(FROZEN_P9_HASHES.items()):
            check(f"frozen:p9-terminal:{rel}", sha256_file(ROOT / rel) == digest, digest)
        for rel, digest in sorted(FROZEN_P8_HASHES.items()):
            check(f"frozen:p8-terminal:{rel}", sha256_file(ROOT / rel) == digest, digest)
        verdict9 = json.loads((ROOT / ".openrecomp-phase9" / "evidence" / "P9-99" / "terminal_verdict.json").read_text(encoding="utf-8"))
        check("frozen:p9-99-decision", verdict9.get("decision") == "PASS", str(verdict9.get("decision")))
        check(
            "frozen:p9-99-terminal-marker",
            "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=PASS" in verdict9.get("markers_issued", []),
            "terminal PASS",
        )

        # --- required Phase-10 stage records ---------------------------------
        for stage, marker in sorted(REQUIRED_STAGES.items()):
            stage_dir = EVIDENCE / stage
            check(f"stage:{stage}:result", (stage_dir / "RESULT.md").is_file(), stage)
            runs = json.loads((stage_dir / "official_runs.json").read_text(encoding="utf-8"))
            check(f"stage:{stage}:two-runs", runs["identical_raw"] and runs["identical_lf"], "identical")
            check(f"stage:{stage}:stderr", runs["stderr_empty_both"], "empty")
            check(f"stage:{stage}:exit", runs["returncode_zero_both"], "zero")
            check(f"stage:{stage}:markers", runs["markers_present_both"], "markers")
            check(f"stage:{stage}:gate-marker", any(marker in recorded for recorded in runs["runs"][0]["markers"]), marker)
            tests = json.loads((stage_dir / f"p10_{stage.split('-')[1]}_tests.json").read_text(encoding="utf-8"))
            check(f"stage:{stage}:tests", tests["status"] == "PASS" and tests["failed"] == 0, tests["status"])

        # --- whole regression and evidence closure ---------------------------
        regression = load("P10-90/whole_regression.json")
        counts = regression["counts"]
        check("p10-90:total", counts["total_reverified_tests"] == 3068, str(counts["total_reverified_tests"]))
        check("p10-90:historical", counts["historical_reverified_tests"] == 1435, str(counts["historical_reverified_tests"]))
        check("p10-90:phase10", counts["phase10_tests"] == 1633, str(counts["phase10_tests"]))
        check("p10-90:guards", regression["guards"]["native_execution_proof"] == NOT_PROVEN and regression["guards"]["playability"] == NOT_PROVEN, json.dumps(regression["guards"], sort_keys=True))
        check("p10-90:p8-audits", [item["stage"] for item in regression["frozen_p8_terminal"]] == ["P8-90", "P8-91", "P8-99"], "3 audits")

        matrix = load("P10-91/proof_matrix.json")
        check("p10-91:milestone", matrix["highest_milestone"] == "A", matrix["highest_milestone"])
        check("p10-91:terminal-reserved", matrix["terminal_claim_status_at_p10_91"] == NOT_PROVEN, NOT_PROVEN)
        check("p10-91:milestones-b-g", all(matrix["milestones"][key] is False for key in ("B", "C", "D", "E", "F", "G")), "B..G not established")
        ledger = load("P10-91/claim_ledger.json")
        ledger_counts: dict[str, int] = {}
        for item in ledger["claims"]:
            ledger_counts[item["class"]] = ledger_counts.get(item["class"], 0) + 1
        check("p10-91:ledger-counts", ledger_counts == LEDGER_COUNTS, json.dumps(ledger_counts, sort_keys=True))
        check("p10-91:permanent-non-claims", tuple(ledger["permanent_non_claims"]) == (f"{GENERAL_MARKER}=NOT_PROVEN",), "permanent")
        check(
            "p10-91:reserved-non-claims",
            tuple(ledger["reserved_non_claims_at_p10_91"]) == (f"{TERMINAL_MARKER}=NOT_PROVEN", f"{PLAYABILITY_MARKER}=NOT_PROVEN"),
            "reserved",
        )
        index = load("P10-91/evidence_index.json")
        check("p10-91:index-entries", index["entry_count"] >= 130, str(index["entry_count"]))
        check("p10-91:index-no-terminal", all("P10-99" not in entry["path"] for entry in index["entries"]), "terminal stage excluded")

        # --- exact fixture identity and native execution evidence ------------
        fixture = load("P10-00/fixture_identity.json")
        check("fixture:executable", fixture["executable"]["sha256"] == "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f" and fixture["executable"]["size"] == 129024, "executable")
        cue = fixture["disc"]["cue"]
        check("fixture:cue", cue["cue_sha256"] == "beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2" and cue["cue_size"] == 101 and cue["track_count"] == 1, "cue")
        bins = fixture["disc"]["bins"]
        check("fixture:bin", len(bins) == 1 and bins[0]["sha256"] == "2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365" and bins[0]["size"] == 409452624, "bin")
        check("fixture:boot", fixture["system_cnf"]["matches_primary_executable"] is True and fixture["system_cnf"]["boot_target"] == "SLUS_005.29", "boot extent")

        native = load("P10-05/native_entry.json")
        execution = native["execution"]
        check("native:guest-entry", native["entry"]["guest_entry_pc"] == "0x800132e8", native["entry"]["guest_entry_pc"])
        check("native:counters", execution["reads"] == 982859 and execution["writes"] == 799023 and execution["denied"] == 11 and execution["host_calls"] == 79, json.dumps(execution, sort_keys=True))
        check("native:budget", execution["access_budget"] == 2000000 and execution["access_count"] == 2000005 and execution["budget_denials"] == 5 and execution["budget_reached"] is True, "budget")
        check("native:termination", execution["termination_category"] == "UNRESOLVED_INDIRECT_JUMP" and execution["failed"] == "1", execution["termination_category"])
        check("native:deterministic", execution["deterministic"] is True, "true")

        milestone = load("P10-11/milestone.json")
        check("milestone:highest", milestone["highest_milestone"] == "A", milestone["highest_milestone"])
        check("milestone:a", milestone["milestones"]["A"]["established"] is True, "A")
        check("milestone:playability", milestone["claims"]["playability"] == NOT_PROVEN, milestone["claims"]["playability"])

        hardening = load("P10-12/hardening.json")
        check("hardening:rebuild", hardening["rebuild"]["identical_to_committed_records"] is True, "identical")
        check("hardening:no-guest-code", hardening["no_guest_machine_code"] is True, "true")
        check("hardening:negatives", hardening["ingest_negatives"] == 12 and hardening["trap_negatives"] == 3, "12/3")

        # --- scope guards -----------------------------------------------------
        scope = (P10 / "SCOPE.md").read_text(encoding="utf-8")
        state = (P10 / "STATE.md").read_text(encoding="utf-8")
        queue = (P10 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        policy = (P10 / "CONTROL_POLICY.md").read_text(encoding="utf-8")
        for name, text in (("scope", scope), ("state", state)):
            check(f"guards:{name}:general", f"{GENERAL_MARKER}=NOT_PROVEN" in text, name)
            check(f"guards:{name}:playability", f"{PLAYABILITY_MARKER}=NOT_PROVEN" in text, name)
        check("guards:scope:terminal-name", TERMINAL_MARKER in scope, "terminal claim")
        check(
            "guards:state:terminal",
            f"{TERMINAL_MARKER}=NOT_PROVEN" in state or f"{TERMINAL_MARKER}=PASS" in state,
            "reserved or consistently promoted",
        )
        check("guards:queue:permanent-general", f"{GENERAL_MARKER}=NOT_PROVEN" in queue, "permanent non-claim recorded")
        check("guards:policy:serial-frontier", "one serial implementation frontier" in policy, "one frontier")
        check("guards:policy:no-guessing", "never guess" in policy, "fail closed")
        rows = re.findall(r"^\| (P10-[0-9]{2}) \| [^|]+ \| ([A-Z_]+) \|", queue, flags=re.MULTILINE)
        row_status = {stage: status for stage, status in rows}
        check("guards:queue-complete", all(row_status.get(stage) == "PASS" for stage in REQUIRED_STAGES), json.dumps(row_status, sort_keys=True))
        check("guards:queue-terminal", row_status.get("P10-99") in ("QUEUED", "PASS"), str(row_status.get("P10-99")))

        # --- public safety ----------------------------------------------------
        fixture_path = pathlib.Path(options.private_fixture)
        payload = fixture_path.read_bytes()[0x800:0x1800] if fixture_path.is_file() else None
        leaks: list[str] = []
        host_paths: list[str] = []
        own = (EVIDENCE / "P10-99").resolve()
        for path in sorted(EVIDENCE.rglob("*")):
            if not path.is_file() or own in path.resolve().parents:
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            text = data.decode("utf-8", errors="replace")
            relative = path.relative_to(ROOT).as_posix()
            if HOST_PATH_RE.search(text):
                host_paths.append(relative)
            if payload is not None:
                lowered = text.lower()
                if payload[:64].hex() in lowered:
                    leaks.append(relative + ":hex")
                elif base64.b64encode(payload[:48]).decode("ascii") in text:
                    leaks.append(relative + ":base64")
                else:
                    for start in range(0, min(len(payload), 4096) - 8):
                        run = payload[start : start + 8]
                        if all(32 <= byte < 127 for byte in run):
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
    terminal = f"{TERMINAL_MARKER}={'PASS' if status == 'PASS' else NOT_PROVEN}"
    playability = f"{PLAYABILITY_MARKER}=NOT_PROVEN"
    general = f"{GENERAL_MARKER}=NOT_PROVEN"
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
            "stage": f"OPENRECOMP_P10_99={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={len(results)}",
            "terminal": terminal,
            "general": general,
            "playability": playability,
        },
    }
    write_json(evidence / "p10_99_tests.json", record)
    terminal_verdict = {
        "stage": STAGE,
        "decision": status,
        "fixture": {
            "label": "hercules-private-fixture",
            "executable_sha256": "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f",
            "executable_size": 129024,
            "cue_sha256": "beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2",
            "bin_sha256": "2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365",
            "bin_size": 409452624,
        },
        "markers_issued": [terminal, general, playability],
        "required_stages": [
            {"stage": stage, "gate_marker": marker, "outcome": "PASS"}
            for stage, marker in sorted(REQUIRED_STAGES.items())
        ],
        "native_execution": {
            "guest_entry_pc": "0x800132e8",
            "reads": 982859,
            "writes": 799023,
            "denied": 11,
            "host_calls": 79,
            "access_budget": 2000000,
            "access_count": 2000005,
            "budget_denials": 5,
            "termination_category": "UNRESOLVED_INDIRECT_JUMP",
            "deterministic": True,
            "highest_milestone": "A",
        },
        "whole_regression": {
            "phase10_gates": 13,
            "phase8_terminal_audits": 3,
            "total_reverified_tests": 3068,
        },
        "scope_guards": {
            "general_ps1_compatibility": "NOT_PROVEN",
            "hercules_playability": "NOT_PROVEN",
            "milestones_b_g": "NOT_PROVEN",
            "arbitrary_psx_exe": "NOT_TESTED",
            "bios_emulation": "NOT_PROVEN",
            "gpu_rendering_vram": "NOT_PROVEN",
            "spu_audio_synthesis": "NOT_PROVEN",
            "cdrom_disc_reading_streaming": "NOT_PROVEN",
            "controller_input_consumption": "NOT_PROVEN",
            "interrupt_delivery_dma_timing": "NOT_PROVEN",
            "memory_cards_link_cable": "NOT_TESTED",
        },
    }
    write_json(evidence / "terminal_verdict.json", terminal_verdict)
    write_json(
        evidence / "verdict_record.json",
        {
            "stage": STAGE,
            "decision": status,
            "tests": len(results),
            "fixture_sha256": "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f",
            "terminal_marker": terminal,
            "general_marker": general,
            "playability_marker": playability,
        },
    )

    for item in results:
        if item["status"] != "PASS":
            print(f"FAIL: {item['check']} :: {item.get('detail', '')}")
    print(f"OPENRECOMP_P10_99={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(terminal)
    print(general)
    print(playability)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
