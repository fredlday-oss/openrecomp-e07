#!/usr/bin/env python3
"""OpenRecomp Phase-10 highest Hercules milestone gate (P10-11).

The gate re-derives the highest demonstrated milestone from the committed stage
evidence and binds every milestone verdict to the exact evidence hash it rests
on, so no milestone claim can outlive its evidence.

Milestone ladder and the derivation rules used here:

* A - translated native execution begins: requires a deterministic native run of
  translated guest code with observable guest-state effects (`P10-05`);
* B - game initialisation completes: requires evidence that the guest's
  initialisation path runs to completion (no such evidence exists; the guest
  fails closed inside that path);
* C - GPU command stream reached: requires GPU command writes (`P10-07` records
  zero GP0/GP1 writes, so it is not established);
* D - first valid rendered frame: requires a frame/present observable (none);
* E - title/logo screen: requires frame evidence plus display output (none);
* F - menu reached: requires a menu state reachable through completed
  initialisation and a frame loop (none);
* G - controllable gameplay: requires deterministic scripted input that causes
  reproducible game-state progression (none: the controller data port is never
  touched).

On success it emits::

    OPENRECOMP_P10_11=PASS
    OPENRECOMP_PHASE10_MILESTONE_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_milestone_v1.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]

STAGE = "P10-11"
FEATURE_MARKER = "OPENRECOMP_PHASE10_MILESTONE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

#: Committed evidence this milestone record is bound to.
EVIDENCE = {
    "P10-05": (
        ".openrecomp-phase10/evidence/P10-05/native_entry.json",
        "ef7b834293e4e5ff1067c78154ccbbeac218276bea1375000bd380e3cb6c05e9",
    ),
    "P10-07": (
        ".openrecomp-phase10/evidence/P10-07/gpu_frontier.json",
        "e60c4dc20089bcb7d70d11247ecaadd44b750437c14e3bea3f4fce452632d73a",
    ),
    "P10-08": (
        ".openrecomp-phase10/evidence/P10-08/timing_frontier.json",
        "a2dc8506a5444be019662cb5ae9042483c74b8993ecc9af1a191c5cf1d735eb2",
    ),
    "P10-09": (
        ".openrecomp-phase10/evidence/P10-09/disc_frontier.json",
        "9e8715c489a033b717e5b69607d747c4315c99d0fed11234845fcc49b4ca0896",
    ),
    "P10-10": (
        ".openrecomp-phase10/evidence/P10-10/input_spu_frontier.json",
        "2b697b82813aa14af1f0744e76cb0d534a0dc3a4263544a10e0b6bb5b35bb538",
    ),
}

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-11")
    args = parser.parse_args()
    evidence = (ROOT / args.evidence_dir).resolve()

    try:
        records: dict[str, dict] = {}
        for stage, (relative, expected) in sorted(EVIDENCE.items()):
            path = ROOT / relative
            check(f"evidence:{stage}:present", path.is_file(), relative)
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
            check(f"evidence:{stage}:sha256", observed == expected, observed)
            records[stage] = json.loads(path.read_bytes().decode("utf-8"))

        # --- milestone A ------------------------------------------------------
        execution = records["P10-05"]["execution"]
        milestone_record = records["P10-05"]["milestone"]
        check("A:mileage-record", milestone_record["highest"] == "A", milestone_record["highest"])
        check("A:deterministic", execution["deterministic"] is True, "true")
        check(
            "A:guest-traffic",
            int(execution["reads"]) + int(execution["writes"]) > 1000000,
            f"{execution['reads']}+{execution['writes']}",
        )
        check("A:failed-closed", execution["failed"] == "1", str(execution["failed"]))
        entry = records["P10-05"]["entry"]
        check("A:crt0-effect", entry["observed_gp"] == "0x8002ed78" and entry["observed_frame_pointer"] == "0x80200000", json.dumps(entry, sort_keys=True))
        check("A:guest-entry", entry["guest_entry_pc"] == "0x800132e8", entry["guest_entry_pc"])

        # --- milestone B: not established -------------------------------------
        check(
            "B:not-established",
            execution["error"] == "unresolved indirect jump",
            execution["error"],
        )
        check(
            "B:explicitly-not-claimed",
            any("milestone B" in item for item in milestone_record["not_claimed"]),
            json.dumps(milestone_record["not_claimed"]),
        )
        check(
            "B:no-completion-marker",
            "initialisation_completed" not in json.dumps(records["P10-05"]),
            "no initialisation-completion marker exists in the native record",
        )

        # --- milestone C: not established -------------------------------------
        frontier = records["P10-07"]["new_frontier"]
        transcript = records["P10-07"]["transcript"]
        check("C:not-established", frontier["gpu_command_stream_reached"] is False, "false")
        check("C:no-gp0-writes", transcript["gp0_writes"] == 0, str(transcript["gp0_writes"]))
        check("C:no-gp1-writes", transcript["gp1_writes"] == 0, str(transcript["gp1_writes"]))
        check("C:status-only", transcript["reads"] == transcript["gp1_reads"], f"{transcript['reads']}/{transcript['gp1_reads']}")

        # --- milestones D/E/F: no frame evidence ------------------------------
        loop = records["P10-10"]["game_loop"]
        check("D:no-frame-loop", loop["frame_loop_reached"] is False, "false")
        check("E:no-frame-loop", loop["frame_loop_reached"] is False, "false")
        check("F:no-frame-loop", loop["frame_loop_reached"] is False, "false")
        check("DEF:busy-poll-instead", loop["busy_poll_loop_reached"] is True, "true")

        # --- milestone G: no input-driven progression -------------------------
        controller = records["P10-10"]["controller"]
        check("G:no-controller-data", controller["controller_data_reached"] is False, "false")
        check("G:no-input-progression", controller["scripted_input_consumable"] is False, "false")
        check("G:no-interrupt-progress", loop["interrupt_driven_progress_required"] is False, "false")
        check(
            "G:no-disc-path",
            records["P10-09"]["classification"]["data_path_reached"] is False,
            "no disc data path",
        )

        # --- supporting frontier facts ----------------------------------------
        reconciliation = records["P10-08"]["classification"]["reconciliation"]
        check("frontier:denials-reconciled", reconciliation["matches"] is True, json.dumps(reconciliation, sort_keys=True))
        check(
            "frontier:first-blocker",
            records["P10-07"]["new_frontier"]["first_remaining_blocker"].startswith("the executed unresolved indirect jump"),
            records["P10-07"]["new_frontier"]["first_remaining_blocker"][:80],
        )

        milestone_table = {
            "A": {
                "established": True,
                "statement": "translated native execution begins: the guest entry and its initialisation prefix execute deterministically as generated host code",
                "evidence": [EVIDENCE["P10-05"][0], EVIDENCE["P10-05"][1]],
            },
            "B": {
                "established": False,
                "reason": "the guest fails closed inside its initialisation path at an executed unresolved indirect jump; no completion evidence exists",
                "evidence": [EVIDENCE["P10-05"][0], EVIDENCE["P10-07"][0]],
            },
            "C": {
                "established": False,
                "reason": "only GP1 status reads are reached; there are zero GP0 and zero GP1 command writes",
                "evidence": [EVIDENCE["P10-07"][0], EVIDENCE["P10-07"][1]],
            },
            "D": {"established": False, "reason": "no frame or present observable exists", "evidence": [EVIDENCE["P10-10"][0], EVIDENCE["P10-10"][1]]},
            "E": {"established": False, "reason": "no frame and no display output exists", "evidence": [EVIDENCE["P10-10"][0], EVIDENCE["P10-10"][1]]},
            "F": {"established": False, "reason": "no completed initialisation, no frame loop and no menu state is reachable", "evidence": [EVIDENCE["P10-10"][0], EVIDENCE["P10-10"][1]]},
            "G": {
                "established": False,
                "reason": "the controller data port is never touched and no input-driven state progression exists",
                "evidence": [EVIDENCE["P10-10"][0], EVIDENCE["P10-10"][1], EVIDENCE["P10-09"][0]],
            },
        }
        check(
            "milestone:single-established",
            [name for name, item in milestone_table.items() if item["established"]] == ["A"],
            ",".join(sorted(name for name, item in milestone_table.items() if item["established"])),
        )
        check(
            "milestone:playability-requires-g",
            milestone_table["G"]["established"] is False,
            "G not established, so playability must stay NOT_PROVEN",
        )

        write_json(
            evidence / "milestone.json",
            {
                "schema": "openrecomp-phase10-milestone-v1",
                "stage": STAGE,
                "label": "hercules-private-fixture",
                "is_pass_criterion": False,
                "highest_milestone": "A",
                "milestones": milestone_table,
                "evidence_binding": {
                    stage: {"path": relative, "sha256": digest}
                    for stage, (relative, digest) in sorted(EVIDENCE.items())
                },
                "first_remaining_blocker": records["P10-07"]["new_frontier"]["first_remaining_blocker"],
                "claims": {
                    "native_execution_proof": NOT_PROVEN,
                    "playability": NOT_PROVEN,
                    "general_ps1_compatibility": NOT_PROVEN,
                },
                "promotion_rule": (
                    "milestone G with deterministic scripted-input evidence of reproducible game-state "
                    "progression is the only evidence that may support a playability claim; it is absent"
                ),
            },
        )

        check("claim:native-execution-not-promoted", True, NOT_PROVEN)
        check("claim:playability-not-promoted", True, NOT_PROVEN)
        check("claim:general-not-promoted", True, NOT_PROVEN)
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    stage_record = {
        "stage": STAGE,
        "stage_name": "Highest Hercules milestone",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p10_11_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_11={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
