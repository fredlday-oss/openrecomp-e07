#!/usr/bin/env python3
"""P11-99 Phase-11 final bounded verdict gate.

Audits every required Phase-11 stage record (`P11-00` through `P11-07`,
`P11-RC`, `P11-90`, `P11-91`), re-verifies the frozen Phase-10 terminal
boundary is byte-for-byte untouched, re-verifies the P11-91 proof matrix and
claim ledger, re-checks the exact private fixture identity and the exact
proven milestone-C GPU command evidence, and issues the terminal stage
marker for the exact evidence-supported bounded claim only.

The four Phase-11 claim markers reserved for milestones B, D and G plus
general PS1 compatibility are never promoted by this gate; they remain
`NOT_PROVEN` regardless of the stage outcome. The already-promoted
milestone-C GPU command-proof marker is verified unchanged, not re-decided.

On success it emits::

    OPENRECOMP_P11_99=PASS
    OPENRECOMP_PHASE11_FINAL_VERDICT_V1=PASS tests=<count>
    OPENRECOMP_PHASE11_HIGHEST_MILESTONE=C_PRIVATE_FIXTURE_BOUNDED
    OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF=PROVEN
    OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase11_final_verdict_v1.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re
import subprocess
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
P11 = ROOT / ".openrecomp-phase11"
EVIDENCE = P11 / "evidence"

STAGE = "P11-99"
FEATURE_MARKER = "OPENRECOMP_PHASE11_FINAL_VERDICT_V1"

GPU_MARKER = "OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN"
FRAME_MARKER = "OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN"
GENERAL_MARKER = "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN"
NOT_PROVEN = "NOT_PROVEN"
RESERVED_MARKERS = (
    INITIALIZATION_MARKER, FRAME_MARKER, PLAYABILITY_MARKER, GENERAL_MARKER,
)

BRANCH = "phase11/ps1-playability-v1"
PHASE10_COMMIT = "8961682aa36e14db979e8e8dbe88e04fa2b4c87a"
PHASE10_TREE = "4a58d9238d76a490560c588bb470fd9e6a58cafe"
PHASE10_BRANCH = "phase10/ps1-commercial-game-native-v1"
P11_91_COMMIT = "1aef50f636ade68ecbb9d713b406d0eafc1c02ac"

REQUIRED_STAGES = {
    "P11-00": ("tools/test_phase11_boundary_v1.py", "p11_00_tests.json",
               "OPENRECOMP_P11_00=PASS"),
    "P11-01": ("tools/test_phase11_causality_v1.py", "p11_01_tests.json",
               "OPENRECOMP_P11_01=PASS"),
    "P11-02": ("tools/test_phase11_indirect_v1.py", "p11_02_tests.json",
               "OPENRECOMP_P11_02=PASS"),
    "P11-03": ("tools/test_phase11_event_contract_v1.py", "p11_03_tests.json",
               "OPENRECOMP_P11_03=PASS"),
    "P11-04": ("tools/test_phase11_initialization_v1.py", "p11_04_tests.json",
               "OPENRECOMP_P11_04=PASS"),
    "P11-05": ("tools/test_phase11_gpu_v1.py", "p11_05_tests.json",
               "OPENRECOMP_P11_05=PASS"),
    "P11-06": ("tools/test_phase11_gpu_closure_v1.py", "p11_06_tests.json",
               "OPENRECOMP_P11_06=PASS"),
    "P11-07": ("tools/test_phase11_b0_table_v1.py", "p11_07_tests.json",
               "OPENRECOMP_P11_07=PASS"),
    "P11-RC": ("tools/test_phase11_queue_reconciliation_v1.py", "p11_rc_tests.json",
               "OPENRECOMP_P11_RC=PASS"),
    "P11-90": ("tools/test_phase11_whole_regression_v1.py", "p11_90_tests.json",
               "OPENRECOMP_P11_90=PASS"),
    "P11-91": ("tools/test_phase11_evidence_closure_v1.py", "p11_91_tests.json",
               "OPENRECOMP_P11_91=PASS"),
}
STAGES_WITHOUT_RESULT = ("P11-90",)
UNEXECUTED_STAGES = ("P11-08", "P11-09", "P11-10", "P11-11", "P11-12")

DEFAULT_PRIVATE_FIXTURE = ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
HOST_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\](?![\\])|/home/[a-z]|/Users/|/root/)")

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL",
                     "detail": str(detail)})
    if not condition:
        raise AssertionError(f"{label}: {detail}")


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: pathlib.Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                     encoding="utf-8", newline="\n")


def load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(ROOT), check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    if completed.returncode != 0 or completed.stderr:
        raise RuntimeError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def tests_status(doc: dict[str, Any]) -> tuple[str, int, int]:
    if "summary" in doc:
        failed = int(doc["summary"]["failed"])
        passed = int(doc["summary"]["passed"])
        return ("PASS" if failed == 0 else "FAIL"), passed, failed
    return doc["status"], int(doc["passed"]), int(doc["failed"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-99")
    parser.add_argument("--private-fixture", default=str(DEFAULT_PRIVATE_FIXTURE))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        # --- frozen Phase-10 boundary, untouched since P11-00 ----------------
        check("boundary:commit-tree",
              git("rev-parse", f"{PHASE10_COMMIT}^{{tree}}") == PHASE10_TREE,
              PHASE10_TREE)
        check("boundary:frozen-branch-tip",
              git("rev-parse", PHASE10_BRANCH) == PHASE10_COMMIT, PHASE10_COMMIT)
        historical_p10_subtree = git("rev-parse", f"{PHASE10_COMMIT}:.openrecomp-phase10")
        current_p10_subtree = git("rev-parse", "HEAD:.openrecomp-phase10")
        check("boundary:phase10-subtree-unchanged",
              current_p10_subtree == historical_p10_subtree, current_p10_subtree)
        check("boundary:current-branch", git("branch", "--show-current") == BRANCH, BRANCH)
        check("boundary:p11-91-ancestor",
              git("merge-base", "--is-ancestor", P11_91_COMMIT, "HEAD") or "true", "true")

        # --- required Phase-11 stage records ----------------------------------
        stage_records: list[dict[str, Any]] = []
        for stage, (script, tests_name, gate_marker) in sorted(REQUIRED_STAGES.items()):
            stage_dir = EVIDENCE / stage
            check(f"stage:{stage}:dir", stage_dir.is_dir(), stage_dir)
            if stage not in STAGES_WITHOUT_RESULT:
                check(f"stage:{stage}:result-md", (stage_dir / "RESULT.md").is_file(),
                      "RESULT.md")
            official = load(stage_dir / "official_runs.json")
            check(f"stage:{stage}:two-runs",
                  official["identical_raw"] and official["identical_lf"], "identical")
            check(f"stage:{stage}:stderr", official["stderr_empty_both"], "empty")
            check(f"stage:{stage}:exit", official["returncode_zero_both"], "zero")
            check(f"stage:{stage}:markers", official["markers_present_both"], "markers")
            check(f"stage:{stage}:gate-marker",
                  any(gate_marker in recorded for recorded in official["runs"][0]["markers"]),
                  gate_marker)
            check(f"stage:{stage}:no-fail-lines",
                  all(not run["fail_lines"] for run in official["runs"]), "no FAIL")
            tests_doc = load(stage_dir / tests_name)
            status, passed, failed = tests_status(tests_doc)
            check(f"stage:{stage}:tests", status == "PASS" and failed == 0, status)
            stage_records.append({"stage": stage, "gate_marker": gate_marker,
                                   "checks_passed": passed, "outcome": "PASS"})

        # --- P11-91 proof matrix and claim ledger -----------------------------
        matrix = load(EVIDENCE / "P11-91" / "proof_matrix.json")
        check("p11-91:highest-milestone", matrix["highest_proven_milestone"] == "C",
              matrix["highest_proven_milestone"])
        check("p11-91:milestones-not-proven",
              all(matrix["milestones"][key] == "NOT_PROVEN"
                  for key in ("B", "D", "E", "F", "G")),
              matrix["milestones"])
        check("p11-91:reserved-count",
              len(matrix["terminal_claims_reserved_at_p11_91"]) == 4,
              matrix["terminal_claims_reserved_at_p11_91"])
        check("p11-91:frontier",
              matrix["frontier"]["site"] == "0x80015fa4"
              and matrix["frontier"]["block_index"] == 468341
              and matrix["frontier"]["status"] == "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
              matrix["frontier"])
        ledger = load(EVIDENCE / "P11-91" / "claim_ledger.json")
        check("p11-91:ledger-reserved",
              set(ledger["reserved_non_claims_at_p11_91"]) == set(RESERVED_MARKERS),
              ledger["reserved_non_claims_at_p11_91"])
        check("p11-91:ledger-permanent",
              ledger["permanent_non_claim"] == GENERAL_MARKER, ledger["permanent_non_claim"])
        check("p11-91:ledger-gpu-marker",
              ledger["gpu_command_proof_marker"] == f"{GPU_MARKER}=PROVEN",
              ledger["gpu_command_proof_marker"])

        # --- exact fixture identity and milestone-C GPU evidence --------------
        fixture = load(EVIDENCE / "P11-00" / "fixture_identity.json")["identity"]
        check("fixture:executable",
              fixture["executable"]["sha256"]
              == "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f"
              and fixture["executable"]["size"] == 129024, "executable")
        check("fixture:cue",
              fixture["disc"]["cue"]["cue_sha256"]
              == "beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2",
              "cue")
        check("fixture:bin",
              fixture["disc"]["bins"][0]["sha256"]
              == "2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365",
              "bin")

        causal_ab = load(EVIDENCE / "P11-05" / "causal_ab.json")
        required_write = causal_ab["prefix"]["required_gpu_write"][0]
        check("gpu:required-write",
              required_write["value"] == "0x0002a244"
              and required_write["classification"]["known"] is True
              and required_write["classification"]["class"] == "NOP",
              required_write)
        check("gpu:conclusion",
              causal_ab["conclusion"]
              == "frontier moved; only the documented void service and typed NOP differ pre-frontier",
              causal_ab["conclusion"])

        blocker = load(EVIDENCE / "P11-07" / "blocker.json")
        check("blocker:classification",
              blocker["classification"] == "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
              blocker["classification"])
        check("blocker:milestone-c",
              blocker["milestones"]["C"] == "PROVEN_IN_P11_05", blocker["milestones"]["C"])
        check("blocker:no-delta", not any(blocker["implementation_delta"].values()),
              blocker["implementation_delta"])

        # --- scope guards: reserved markers, permanent non-claim, queue -------
        state = (P11 / "STATE.md").read_text(encoding="utf-8")
        queue = (P11 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        scope = (P11 / "SCOPE.md").read_text(encoding="utf-8")
        for marker in RESERVED_MARKERS:
            check(f"guards:state:{marker}", marker in state, marker)
        check("guards:state:gpu-marker", f"{GPU_MARKER}=PROVEN" in state, "gpu marker")
        check("guards:queue:general", f"{GENERAL_MARKER}` (permanent)" in queue,
              "permanent non-claim")
        scope_concepts = {
            INITIALIZATION_MARKER: "initialization completes",
            FRAME_MARKER: "first valid frame",
            PLAYABILITY_MARKER: "controllable gameplay",
            GENERAL_MARKER.split("=")[0]: "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN",
        }
        check("guards:scope:markers-present",
              all(concept in scope for concept in scope_concepts.values()),
              "reserved milestone concepts present in scope")
        for stage in REQUIRED_STAGES:
            check(f"guards:queue-row:{stage}:pass",
                  re.search(rf"\|\s*{re.escape(stage)}\s*\|\s*PASS", state) is not None,
                  stage)
        for stage in UNEXECUTED_STAGES:
            check(f"guards:state-row:{stage}:not-executed",
                  f"| {stage} | NOT EXECUTED — no stage verdict assigned |" in state,
                  stage)

        # --- public safety ------------------------------------------------------
        fixture_path = pathlib.Path(options.private_fixture)
        payload = fixture_path.read_bytes()[0x800:0x1800] if fixture_path.is_file() else None
        leaks: list[str] = []
        host_paths: list[str] = []
        own = (EVIDENCE / "P11-99").resolve()
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
                        run = payload[start:start + 8]
                        if all(32 <= byte < 127 for byte in run) and run.decode("ascii") in text:
                            leaks.append(relative + ":ascii")
                            break
        check("safety:no-payload-leaks", leaks == [], leaks)
        check("safety:no-host-paths", host_paths == [], host_paths)

        decision = "PASS"
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
        decision = "FAIL"
        stage_records = []
    except Exception as exc:
        RESULTS.append({"check": "gate:exception", "status": "FAIL",
                         "detail": f"{type(exc).__name__}: {exc}"})
        decision = "FAIL"
        stage_records = []

    status = "PASS" if decision == "PASS" and all(
        item["status"] == "PASS" for item in RESULTS) else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    gpu_marker_line = f"{GPU_MARKER}=PROVEN"
    reserved_lines = [f"{marker}" for marker in RESERVED_MARKERS]
    record = {
        "schema": "openrecomp-phase11-tests-v1",
        "stage": STAGE,
        "status": status,
        "checks": results,
        "summary": {
            "passed": sum(1 for item in results if item["status"] == "PASS"),
            "failed": sum(1 for item in results if item["status"] != "PASS"),
        },
        "markers": {
            "stage": f"OPENRECOMP_P11_99={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={len(results)}",
            "highest_milestone": "C_PRIVATE_FIXTURE_BOUNDED",
            "gpu_command_proof": gpu_marker_line,
            "reserved": reserved_lines,
        },
    }
    write_json(evidence / "p11_99_tests.json", record)

    terminal_verdict = {
        "schema": "openrecomp-phase11-terminal-verdict-v1",
        "stage": STAGE,
        "decision": status,
        "fixture": {
            "label": "hercules-private-fixture",
            "executable_sha256":
                "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f",
            "executable_size": 129024,
            "cue_sha256":
                "beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2",
            "bin_sha256":
                "2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365",
        },
        "highest_proven_milestone": "C",
        "milestone_c_evidence": {
            "gp0_write": "0x0002a244",
            "classification": "known NOP",
            "stage": "P11-05",
        },
        "frontier": {
            "site": "0x80015fa4",
            "vector": "B0",
            "function_index": "0x57",
            "public_name": "GetB0Table",
            "block_index": 468341,
            "required_entry": "B0:0x5b ChangeClearPAD",
            "status": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
            "cause": "architectural/evidentiary, not implementation defect",
        },
        "markers_issued": [
            f"OPENRECOMP_P11_99={status}",
            gpu_marker_line,
            *reserved_lines,
        ],
        "required_stages": stage_records,
        "unexecuted_stages": list(UNEXECUTED_STAGES),
        "scope_guards": {
            "milestone_b": "NOT_PROVEN",
            "milestone_d": "NOT_PROVEN",
            "milestone_e": "NOT_PROVEN",
            "milestone_f": "NOT_PROVEN",
            "milestone_g": "NOT_PROVEN",
            "general_ps1_compatibility": "NOT_PROVEN_PERMANENT",
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
    write_json(evidence / "verdict_record.json", {
        "schema": "openrecomp-phase11-verdict-record-v1",
        "stage": STAGE,
        "decision": status,
        "tests": len(results),
        "fixture_sha256": "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f",
        "highest_proven_milestone": "C",
        "gpu_command_proof_marker": gpu_marker_line,
        "reserved_markers": list(RESERVED_MARKERS),
    })

    for item in results:
        if item["status"] != "PASS":
            print(f"FAIL: {item['check']} :: {item.get('detail', '')}")
    print(f"OPENRECOMP_P11_99={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print("OPENRECOMP_PHASE11_HIGHEST_MILESTONE=C_PRIVATE_FIXTURE_BOUNDED")
    print(gpu_marker_line)
    for marker in reserved_lines:
        print(marker)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
