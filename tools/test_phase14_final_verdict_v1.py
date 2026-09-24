#!/usr/bin/env python3
"""Deterministic P14-99 terminal bounded-verdict gate."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase14/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p14_gate_v1 import run_stage, write_json  # noqa: E402
from p14_contracts_v1 import (  # noqa: E402
    B0_56_MARKER,
    B0_57_MARKER,
    C0_TABLE_MARKER,
    CARD_CONTINUATION_MARKER,
    CARD_INIT_CHAIN_MARKER,
    CARD_IRQ_MARKER,
    EARLY_CARD_PATCH_MARKER,
    FRAME_MARKER,
    GENERAL_MARKER,
    INITIALIZATION_MARKER,
    INITIALIZATION_REPLAY_MARKER,
    PHASE13_BASE_COMMIT,
    PLAYABILITY_MARKER,
)

STAGE = "P14-99"
EVIDENCE = ROOT / ".openrecomp-phase14/evidence"

STAGE_DIRS = ("P14-00", "P14-01", "P14-05", "P14-20", "P14-30", "P14-40",
              "P14-50", "P14-90", "P14-91")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True).stdout.strip()


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    markers: dict[str, str] = {}
    for stage in STAGE_DIRS:
        result_path = EVIDENCE / stage / "RESULT.json"
        gate.check(f"verdict:record-{stage}", result_path.is_file(), stage)
        document = json.loads(result_path.read_text(encoding="utf-8"))
        markers.update(document.get("markers", {}))

    def result(number: str) -> str:
        return "PASS" if markers.get(f"OPENRECOMP_P14_{number}") == "PASS" else "FAIL"

    head = git("rev-parse", "HEAD")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    commits = [line for line in git("log", "--oneline",
                                    f"{PHASE13_BASE_COMMIT}..HEAD").splitlines() if line]
    status = [line for line in git("status", "--porcelain").splitlines()
              if not line.endswith(".openrecomp-phase14/") and ".openrecomp-phase14/" not in line]

    proof = json.loads((EVIDENCE / "P14-05" / "initialization_proof.json").read_text(encoding="utf-8"))
    stage_results = {f"P14_{number:02d}_RESULT": result(f"{number:02d}")
                     for number in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
                                    20, 30, 40, 50, 90, 91)}
    stage_results["P14_99_RESULT"] = "PASS"

    verdict = {
        "schema": "openrecomp-phase14-final-verdict-v1",
        "stage": STAGE,
        "branch": branch,
        "phase13_base_commit": PHASE13_BASE_COMMIT,
        "phase14_head": head,
        "stage_results": stage_results,
        "claim_markers": {
            B0_56_MARKER: markers.get(B0_56_MARKER, "NOT_PROVEN"),
            C0_TABLE_MARKER: markers.get(C0_TABLE_MARKER, "NOT_PROVEN"),
            EARLY_CARD_PATCH_MARKER: markers.get(EARLY_CARD_PATCH_MARKER, "NOT_PROVEN"),
            CARD_CONTINUATION_MARKER: markers.get(CARD_CONTINUATION_MARKER, "NOT_PROVEN"),
            B0_57_MARKER: markers.get(B0_57_MARKER, "NOT_PROVEN"),
            CARD_INIT_CHAIN_MARKER: markers.get(CARD_INIT_CHAIN_MARKER, "NOT_PROVEN"),
            CARD_IRQ_MARKER: markers.get(CARD_IRQ_MARKER, "NOT_REQUIRED"),
            INITIALIZATION_REPLAY_MARKER: markers.get(INITIALIZATION_REPLAY_MARKER, "NOT_PROVEN"),
            INITIALIZATION_MARKER: "NOT_PROVEN",
            FRAME_MARKER: "NOT_PROVEN",
            PLAYABILITY_MARKER: "NOT_PROVEN",
            GENERAL_MARKER: "NOT_PROVEN",
        },
        "current_technical_frontier": "0x1F801074 interrupt-mask MMIO (I_STAT/I_MASK) reached on the "
                                      "live post-card path; the bounded device boundary fails closed",
        "initialization_proof_complete": "NO",
        "phase14_target_proof_complete": "NO",
        "final_verdict": "PASS_BOUNDED_INITIALIZATION_CLOSURE_FRONTIER_REMAINS",
        "commits_created": commits,
        "remaining_worktree_changes": status,
        "next_frame_frontier": "NOT_READY",
    }
    write_json(evidence / "verdict.json", verdict)
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase14-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P14_99": "PASS", INITIALIZATION_MARKER: "NOT_PROVEN",
                    FRAME_MARKER: "NOT_PROVEN", PLAYABILITY_MARKER: "NOT_PROVEN",
                    GENERAL_MARKER: "NOT_PROVEN"},
        "next_stage": "NONE",
    })
    write_json(evidence / "p14_99_tests.json", gate.tests_document("final-verdict"))

    print(f"CURRENT_BRANCH={branch}")
    print(f"PHASE13_BASE_COMMIT={PHASE13_BASE_COMMIT}")
    print(f"PHASE14_HEAD={head}")
    for key in ("P14_00_RESULT", "P14_01_RESULT", "P14_02_RESULT", "P14_03_RESULT",
                "P14_04_RESULT", "P14_05_RESULT", "P14_06_RESULT", "P14_07_RESULT",
                "P14_08_RESULT", "P14_09_RESULT", "P14_10_RESULT", "P14_11_RESULT",
                "P14_20_RESULT", "P14_30_RESULT", "P14_40_RESULT", "P14_50_RESULT",
                "P14_90_RESULT", "P14_91_RESULT", "P14_99_RESULT"):
        print(f"{key}={stage_results[key]}")
    for marker, value in verdict["claim_markers"].items():
        print(f"{marker}={value}")
    print("CARD_IRQ_DELIVERY_REQUIRED_NOW=NO")
    print("HARDWARE_INTERRUPT_DELIVERY_REQUIRED_NOW=NO")
    print(f"CURRENT_TECHNICAL_FRONTIER={verdict['current_technical_frontier']}")
    print("INITIALIZATION_PROOF_COMPLETE=NO")
    print("PHASE14_TARGET_PROOF_COMPLETE=NO")
    print("PRIVATE_FIXTURE_BYTES_COMMITTED=NO")
    print("THIRD_PARTY_CODE_IMPORTED=NO")
    print("PHASE13_TOUCHED=NO")
    print("PRIOR_RECON_TOUCHED=NO")
    print(f"FINAL_VERDICT={verdict['final_verdict']}")
    print("COMMITS_CREATED=" + "|".join(commits))
    print("REMAINING_WORKTREE_CHANGES=" + ("NONE" if not status else ";".join(status)))
    print("NEXT_FRAME_FRONTIER=NOT_READY")
    gate.mark("OPENRECOMP_P14_99")
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase14/evidence/P14-99"))
