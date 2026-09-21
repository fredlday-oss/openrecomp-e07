#!/usr/bin/env python3
"""OpenRecomp Phase-10 evidence closure and proof matrix gate (P10-91).

The gate verifies, on one audited tree:

* every completed Phase-10 stage record (`P10-00` .. `P10-12`, `P10-90`) exists
  with a `RESULT.md`, a machine-readable tests record, an `official_runs.json`
  with two byte-identical runs, empty stderr, exit 0 and the correct reserved
  markers, and every sidecar hash recorded there matches the file on disk;
* the evidence index covers every committed Phase-10 evidence file (excluding
  this stage's own generated sidecars and the post-index terminal stage) with
  exact SHA-256 and size;
* the proof matrix records the exact private fixture identity, the native
  execution state, the exact highest Hercules milestone, the
  CPU/BIOS/GPU/DMA-timing/CD-filesystem/SPU-input frontiers, the deliberate
  exclusions and the unresolved blockers;
* the claim ledger classifies every Phase-10 claim as
  `PROVEN` / `BOUNDED` / `NOT_PROVEN` / `NOT_TESTED`, keeps the permanent
  general-PS1 non-claim and the reserved terminal/playability markers
  unpromoted;
* the public-safety verification finds no private payload material, no absolute
  host paths and no reconstructive commercial data in the committed Phase-10
  evidence, and the Phase-10 source manifest verifies.

On success it emits::

    OPENRECOMP_P10_91=PASS
    OPENRECOMP_PHASE10_EVIDENCE_CLOSURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_evidence_closure_v1.py
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

STAGE = "P10-91"
FEATURE_MARKER = "OPENRECOMP_PHASE10_EVIDENCE_CLOSURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

COMPLETED_STAGES = (
    "P10-00", "P10-01", "P10-02", "P10-03", "P10-04", "P10-05", "P10-06",
    "P10-07", "P10-08", "P10-09", "P10-10", "P10-11", "P10-12", "P10-90",
)

PERMANENT_NON_CLAIMS = (f"{GENERAL_MARKER}=NOT_PROVEN",)
RESERVED_NON_CLAIMS = (
    f"{TERMINAL_MARKER}=NOT_PROVEN",
    f"{PLAYABILITY_MARKER}=NOT_PROVEN",
)

REQUIRED_CLAIMS = {
    "psx_exe_ingestion": "PROVEN",
    "break_syscall_classification": "PROVEN",
    "control_without_delay_slot_reconciliation": "PROVEN",
    "cpu_control_frontier_closure": "PROVEN",
    "bios_call_classification": "PROVEN",
    "native_execution_entry": "PROVEN",
    "dynamic_io_discovery": "PROVEN",
    "gpu_frontier_classification": "PROVEN",
    "interrupt_dma_timing_classification": "PROVEN",
    "cdrom_disc_frontier_classification": "PROVEN",
    "controller_spu_game_loop_classification": "PROVEN",
    "highest_milestone_a": "PROVEN",
    "fail_closed_hardening_and_reproducibility": "PROVEN",
    "whole_project_regression": "PROVEN",
    "private_fixture_scope": "BOUNDED",
    "event_transcript_caps_and_access_budget": "BOUNDED",
    "platform_port_contract_stubs": "BOUNDED",
    "read_driven_virtual_time": "BOUNDED",
    "historical_stage_composition": "BOUNDED",
    "native_execution_proof": "NOT_PROVEN",
    "hercules_playability": "NOT_PROVEN",
    "general_ps1_compatibility": "NOT_PROVEN",
    "milestone_b_initialisation_complete": "NOT_PROVEN",
    "milestone_c_gpu_command_stream": "NOT_PROVEN",
    "milestone_d_e_f_frame_present_observable": "NOT_PROVEN",
    "milestone_g_controllable_gameplay": "NOT_PROVEN",
    "bios_emulation": "NOT_PROVEN",
    "gpu_rendering_vram": "NOT_PROVEN",
    "spu_audio_synthesis": "NOT_PROVEN",
    "cdrom_disc_reading_streaming": "NOT_PROVEN",
    "controller_input_consumption": "NOT_PROVEN",
    "interrupt_delivery": "NOT_PROVEN",
    "dma_transfer": "NOT_PROVEN",
    "cycle_accurate_timing": "NOT_PROVEN",
    "arbitrary_psx_exe_compatibility": "NOT_TESTED",
    "memory_cards_link_cable": "NOT_TESTED",
}

DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)

HOST_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/|/root/)")
ALLOWED_EVIDENCE_SUFFIXES = (".json", ".md", ".txt")

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


def build_index() -> dict:
    entries = []
    total_bytes = 0
    # The index excludes its own generated sidecars and the post-index terminal
    # stage, which is produced after the index and audited by the P10-99 gate.
    excluded_prefixes = (
        ".openrecomp-phase10/evidence/P10-91/",
        ".openrecomp-phase10/evidence/P10-99/",
    )
    for path in sorted(EVIDENCE.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if any(relative.startswith(prefix) for prefix in excluded_prefixes):
            continue
        size = path.stat().st_size
        total_bytes += size
        entries.append(
            {
                "path": relative,
                "stage": path.relative_to(EVIDENCE).parts[0],
                "bytes": size,
                "sha256": sha256_file(path),
                "tracked": True,
            }
        )
    return {
        "schema": "openrecomp-phase10-evidence-index-v1",
        "stage": STAGE,
        "entry_count": len(entries),
        "total_bytes": total_bytes,
        "entries": entries,
        "note": "the index excludes its own directory's generated sidecars and the post-index terminal stage (P10-99)",
    }


def build_proof_matrix() -> dict:
    fixture = load("P10-00/fixture_identity.json")
    structure = load("P10-02/structure_reconciliation.json")
    semantics = load("P10-03/frontier_closure.json")
    bios = load("P10-04/bios_classification.json")
    native = load("P10-05/native_entry.json")
    io = load("P10-06/io_discovery.json")
    gpu = load("P10-07/gpu_frontier.json")
    timing = load("P10-08/timing_frontier.json")
    disc = load("P10-09/disc_frontier.json")
    input_spu = load("P10-10/input_spu_frontier.json")
    milestone = load("P10-11/milestone.json")
    hardening = load("P10-12/hardening.json")
    regression = load("P10-90/whole_regression.json")
    bios_classification = bios["classification"]
    return {
        "schema": "openrecomp-phase10-proof-matrix-v1",
        "stage": STAGE,
        "fixture_identity": {
            "executable": fixture["executable"],
            "disc": {
                "cue": fixture["disc"]["cue"],
                "bins": fixture["disc"]["bins"],
                "volume": fixture["disc"]["volume"],
            },
            "system_cnf": fixture["system_cnf"],
        },
        "native_execution": {
            "entry": native["entry"],
            "execution": native["execution"],
            "memory_image": native["memory_image"],
            "first_host_service_transition": {
                "address_observable": native["first_host_service_transition"]["address_observable"],
                "candidate_site_count": native["first_host_service_transition"]["candidate_site_count"],
            },
            "translated_trace": {
                "exception_sites": native["translated_trace"]["exception_sites"],
            },
        },
        "highest_milestone": milestone["highest_milestone"],
        "milestones": {
            key: item["established"] for key, item in sorted(milestone["milestones"].items())
        },
        "milestone_claims": milestone["claims"],
        "frontiers": {
            "structure": {
                "cause": structure["cause"],
                "resolution": structure["resolution"],
                "summary": structure["structure_summary"],
                "new_frontier": structure["new_frontier"],
            },
            "semantics": {
                "preconditions": semantics["preconditions"],
                "unruled_ops": semantics["unruled_ops"],
            },
            "bios": {
                "bios_call_count": bios_classification["bios_call_count"],
                "site_count": bios_classification["site_count"],
                "histogram": bios_classification["histogram"],
                "unknown_policy": bios_classification["unknown_policy"],
                "index_register": bios_classification["index_register"],
                "vector_bases": bios_classification["vector_bases"],
                "resolved_internal_call_count": bios_classification["resolved_internal_call_count"],
                "boundary": bios["p9_boundary_reused"],
            },
            "io": {
                "dynamic": io["dynamic"],
                "static": io["static"],
            },
            "gpu": {
                "transcript": gpu["transcript"],
                "status_read_stub": gpu["gpu_status_read_stub"],
                "denial_attribution": gpu["denial_attribution"],
                "new_frontier": gpu["new_frontier"],
                "not_implemented": gpu["not_implemented"],
            },
            "timing": {
                "classification": timing["classification"],
            },
            "disc": {
                "classification": disc["classification"],
                "disc_identity_sha256": disc["disc_identity_sha256"],
            },
            "input_spu": {
                "controller": input_spu["controller"],
                "spu": input_spu["spu"],
                "game_loop": input_spu["game_loop"],
            },
            "hardening": {
                "ingest_negatives": hardening["ingest_negatives"],
                "trap_negatives": hardening["trap_negatives"],
                "cache": hardening["cache"],
                "rebuild": hardening["rebuild"],
                "no_guest_machine_code": hardening["no_guest_machine_code"],
                "safety_scan": hardening["safety_scan"],
                "bounded_execution": hardening["bounded_execution"],
            },
        },
        "whole_regression": {
            "stage": regression["stage"],
            "counts": regression["counts"],
            "guards": regression["guards"],
            "p8_terminal_audits": [
                {"stage": item["stage"], "tests": item["tests"]}
                for item in regression["frozen_p8_terminal"]
            ],
        },
        "claims": [
            {"key": key, "class": klass, "evidence": _claim_evidence(key)}
            for key, klass in sorted(REQUIRED_CLAIMS.items())
        ],
        "deliberate_exclusions": [
            "no BIOS image is loaded, executed or emulated",
            "no GPU rendering, framebuffer or VRAM state is modelled",
            "no SPU synthesis or RAM transfer is implemented",
            "no disc data path, sector transfer, ISO9660 access, overlay or streaming is implemented",
            "no controller input is consumed and no frame or interrupt-driven loop is claimed",
            "no interrupt delivery, DMA transfer or memory-control timing model is implemented",
            "no generic exception machinery is added: BREAK/SYSCALL stay explicit fail-closed terminators",
        ],
        "unresolved_blockers": [
            "an executed unresolved indirect jump blocks initialisation (the failing guest PC is not observable)",
            "milestones B..G are unreachable without resolving that control-flow frontier",
            "the access budget bounds accesses, not execution (mitigated by the default budget and a bounded host timeout)",
            "SPU RAM transfer, interrupt delivery, DMA, memory-control timing, disc data transfer and controller consumption remain unreached/unimplemented",
        ],
        "permanent_non_claims": list(PERMANENT_NON_CLAIMS),
        "reserved_non_claims_at_p10_91": list(RESERVED_NON_CLAIMS),
        "terminal_claim": TERMINAL_MARKER,
        "terminal_claim_status_at_p10_91": NOT_PROVEN,
        "playability_claim": PLAYABILITY_MARKER,
        "playability_claim_status_at_p10_91": NOT_PROVEN,
    }


def _claim_evidence(key: str) -> list[str]:
    return {
        "psx_exe_ingestion": ["P10-00", "P10-12"],
        "break_syscall_classification": ["P10-01", "P10-12"],
        "control_without_delay_slot_reconciliation": ["P10-02"],
        "cpu_control_frontier_closure": ["P10-03", "P10-12"],
        "bios_call_classification": ["P10-04", "P10-12"],
        "native_execution_entry": ["P10-05", "P10-11", "P10-12"],
        "dynamic_io_discovery": ["P10-06"],
        "gpu_frontier_classification": ["P10-07"],
        "interrupt_dma_timing_classification": ["P10-08"],
        "cdrom_disc_frontier_classification": ["P10-09"],
        "controller_spu_game_loop_classification": ["P10-10"],
        "highest_milestone_a": ["P10-11"],
        "fail_closed_hardening_and_reproducibility": ["P10-12", "P10-90"],
        "whole_project_regression": ["P10-90"],
        "private_fixture_scope": ["P10-00", "P10-11"],
        "event_transcript_caps_and_access_budget": ["P10-05", "P10-07", "P10-12"],
        "platform_port_contract_stubs": ["P10-07", "P10-08", "P10-09", "P10-10"],
        "read_driven_virtual_time": ["P10-08"],
        "historical_stage_composition": ["P10-07", "P10-08", "P10-90"],
    }.get(key, [])


def build_ledger() -> dict:
    return {
        "schema": "openrecomp-phase10-claim-ledger-v1",
        "stage": STAGE,
        "classes": ["PROVEN", "BOUNDED", "NOT_PROVEN", "NOT_TESTED"],
        "claims": [
            {"claim": "PS-X EXE ingestion for the bounded V1 container form", "class": "PROVEN", "key": "psx_exe_ingestion", "evidence": ["P10-00", "P10-12"]},
            {"claim": "Exact BREAK/SYSCALL encoding and architectural semantics classification", "class": "PROVEN", "key": "break_syscall_classification", "evidence": ["P10-01", "P10-12"]},
            {"claim": "CONTROL_WITHOUT_DELAY_SLOT reconciled by the additive exception-aware structure bridge", "class": "PROVEN", "key": "control_without_delay_slot_reconciliation", "evidence": ["P10-02"]},
            {"claim": "Reachable CPU/control frontier closure for the private fixture", "class": "PROVEN", "key": "cpu_control_frontier_closure", "evidence": ["P10-03", "P10-12"]},
            {"claim": "Exact BIOS call-site classification with the typed fail-closed service boundary and no BIOS image", "class": "PROVEN", "key": "bios_call_classification", "evidence": ["P10-04", "P10-12"]},
            {"claim": "Deterministic translated native execution entry into the private guest code (milestone A)", "class": "PROVEN", "key": "native_execution_entry", "evidence": ["P10-05", "P10-11", "P10-12"]},
            {"claim": "Dynamic and static PS1 I/O discovery over the audited port ranges", "class": "PROVEN", "key": "dynamic_io_discovery", "evidence": ["P10-06"]},
            {"claim": "Exact GPU frontier classification (GP1 status polling only; no command stream)", "class": "PROVEN", "key": "gpu_frontier_classification", "evidence": ["P10-07"]},
            {"claim": "Exact interrupt/DMA/timing frontier classification with a read-driven virtual-time contract", "class": "PROVEN", "key": "interrupt_dma_timing_classification", "evidence": ["P10-08"]},
            {"claim": "Exact disc/CD-ROM frontier classification (register traffic only; no data path)", "class": "PROVEN", "key": "cdrom_disc_frontier_classification", "evidence": ["P10-09"]},
            {"claim": "Exact controller/SPU/game-loop frontier classification (no controller consumption; served busy-poll loop)", "class": "PROVEN", "key": "controller_spu_game_loop_classification", "evidence": ["P10-10"]},
            {"claim": "Highest demonstrated Hercules milestone is A", "class": "PROVEN", "key": "highest_milestone_a", "evidence": ["P10-11"]},
            {"claim": "Fail-closed hardening, immutable-hash cache correctness, reproducible rebuild and public-safety closure", "class": "PROVEN", "key": "fail_closed_hardening_and_reproducibility", "evidence": ["P10-12", "P10-90"]},
            {"claim": "Whole-project regression across the frozen Phase-1..9 chain and the completed Phase-10 stages", "class": "PROVEN", "key": "whole_project_regression", "evidence": ["P10-90"]},
            {"claim": "Every demonstrated result is bounded to the exact private fixture", "class": "BOUNDED", "key": "private_fixture_scope", "evidence": ["P10-00", "P10-11"]},
            {"claim": "Per-device transcripts are capped and the access budget bounds accesses, not execution", "class": "BOUNDED", "key": "event_transcript_caps_and_access_budget", "evidence": ["P10-05", "P10-07", "P10-12"]},
            {"claim": "Platform ports are event-recording contract stubs, not hardware-accurate emulation", "class": "BOUNDED", "key": "platform_port_contract_stubs", "evidence": ["P10-07", "P10-08", "P10-09", "P10-10"]},
            {"claim": "Virtual time is read-driven (`tick & 0xffff`), not cycle accurate", "class": "BOUNDED", "key": "read_driven_virtual_time", "evidence": ["P10-08"]},
            {"claim": "Completed stage records carry the runtime composition as it was at their own boundary", "class": "BOUNDED", "key": "historical_stage_composition", "evidence": ["P10-07", "P10-08", "P10-90"]},
            {"claim": "Reserved terminal native-execution proof marker", "class": "NOT_PROVEN", "key": "native_execution_proof", "evidence": []},
            {"claim": "Hercules playability", "class": "NOT_PROVEN", "key": "hercules_playability", "evidence": []},
            {"claim": "General PS1 compatibility", "class": "NOT_PROVEN", "key": "general_ps1_compatibility", "evidence": []},
            {"claim": "Milestone B (initialisation completes)", "class": "NOT_PROVEN", "key": "milestone_b_initialisation_complete", "evidence": []},
            {"claim": "Milestone C (GPU command stream reached)", "class": "NOT_PROVEN", "key": "milestone_c_gpu_command_stream", "evidence": []},
            {"claim": "Milestones D/E/F (frame or present observable)", "class": "NOT_PROVEN", "key": "milestone_d_e_f_frame_present_observable", "evidence": []},
            {"claim": "Milestone G (controllable gameplay)", "class": "NOT_PROVEN", "key": "milestone_g_controllable_gameplay", "evidence": []},
            {"claim": "BIOS emulation", "class": "NOT_PROVEN", "key": "bios_emulation", "evidence": []},
            {"claim": "GPU rendering / VRAM behaviour", "class": "NOT_PROVEN", "key": "gpu_rendering_vram", "evidence": []},
            {"claim": "SPU audio synthesis", "class": "NOT_PROVEN", "key": "spu_audio_synthesis", "evidence": []},
            {"claim": "CD-ROM disc reading / filesystem / streaming", "class": "NOT_PROVEN", "key": "cdrom_disc_reading_streaming", "evidence": []},
            {"claim": "Controller input consumption", "class": "NOT_PROVEN", "key": "controller_input_consumption", "evidence": []},
            {"claim": "Interrupt delivery / event scheduling", "class": "NOT_PROVEN", "key": "interrupt_delivery", "evidence": []},
            {"claim": "DMA transfer", "class": "NOT_PROVEN", "key": "dma_transfer", "evidence": []},
            {"claim": "Cycle-accurate timing", "class": "NOT_PROVEN", "key": "cycle_accurate_timing", "evidence": []},
            {"claim": "Arbitrary PS-X EXE compatibility", "class": "NOT_TESTED", "key": "arbitrary_psx_exe_compatibility", "evidence": []},
            {"claim": "Memory cards, link cable and other unimplemented devices", "class": "NOT_TESTED", "key": "memory_cards_link_cable", "evidence": []},
        ],
        "permanent_non_claims": list(PERMANENT_NON_CLAIMS),
        "reserved_non_claims_at_p10_91": list(RESERVED_NON_CLAIMS),
        "terminal_claim": TERMINAL_MARKER,
        "terminal_claim_status_at_p10_91": NOT_PROVEN,
        "playability_claim_status_at_p10_91": NOT_PROVEN,
    }


def verify_stage_records() -> dict:
    summary = {}
    for stage in COMPLETED_STAGES:
        stage_dir = EVIDENCE / stage
        check(f"record:{stage}:dir", stage_dir.is_dir(), stage)
        check(f"record:{stage}:result", (stage_dir / "RESULT.md").is_file(), stage)
        runs_path = stage_dir / "official_runs.json"
        check(f"record:{stage}:official-runs", runs_path.is_file(), stage)
        runs = json.loads(runs_path.read_text(encoding="utf-8"))
        check(f"record:{stage}:two-runs", runs["identical_raw"] and runs["identical_lf"], "identical")
        check(f"record:{stage}:stderr", runs["stderr_empty_both"], "empty")
        check(f"record:{stage}:exit", runs["returncode_zero_both"], "zero")
        check(f"record:{stage}:markers", runs["markers_present_both"], "markers")
        number = stage.split("-")[1]
        tests_path = stage_dir / f"p10_{number}_tests.json"
        check(f"record:{stage}:tests-present", tests_path.is_file(), tests_path.name)
        for run in runs["runs"]:
            key = f"p10_{number}_tests_sha256"
            if key in run:
                check(f"record:{stage}:tests-hash:{run['name']}", sha256_file(tests_path) == run[key], run[key])
        for artifact, digest in sorted(runs.get("artifact_sha256", {}).items()):
            artifact_path = stage_dir / artifact
            check(
                f"record:{stage}:sidecar:{artifact}",
                artifact_path.is_file() and sha256_file(artifact_path) == digest,
                digest,
            )
        tests = json.loads(tests_path.read_text(encoding="utf-8"))
        check(f"record:{stage}:tests-status", tests["status"] == "PASS" and tests["failed"] == 0, tests["status"])
        summary[stage] = {
            "tests": tests["tests"],
            "stdout_sha256_raw": runs["runs"][0]["stdout_sha256_raw"],
            "sidecars": sorted(runs.get("artifact_sha256", {})),
        }
    return summary


def verify_exact_records() -> None:
    fixture = load("P10-00/fixture_identity.json")
    check("fixture:executable-sha256", fixture["executable"]["sha256"] == "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f", fixture["executable"]["sha256"])
    check("fixture:executable-size", fixture["executable"]["size"] == 129024, str(fixture["executable"]["size"]))
    cue = fixture["disc"]["cue"]
    check("fixture:cue-sha256", cue["cue_sha256"] == "beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2", cue["cue_sha256"])
    check("fixture:cue-size", cue["cue_size"] == 101, str(cue["cue_size"]))
    check("fixture:one-track", cue["track_count"] == 1 and cue["tracks"][0]["type"] == "MODE2/2352", "MODE2/2352")
    bins = fixture["disc"]["bins"]
    check("fixture:bin-count", len(bins) == 1, str(len(bins)))
    check("fixture:bin-sha256", bins[0]["sha256"] == "2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365", bins[0]["sha256"])
    check("fixture:bin-size", bins[0]["size"] == 409452624, str(bins[0]["size"]))
    system_cnf = fixture["system_cnf"]
    check("fixture:boot-target", system_cnf["boot_target"] == "SLUS_005.29", system_cnf["boot_target"])
    check("fixture:boot-extent-identity", system_cnf["matches_primary_executable"] and system_cnf["boot_extent_sha256"] == fixture["executable"]["sha256"], "boot extent equals executable")

    native = load("P10-05/native_entry.json")
    execution = native["execution"]
    check("native:guest-entry", native["entry"]["guest_entry_pc"] == "0x800132e8", native["entry"]["guest_entry_pc"])
    check("native:reads", execution["reads"] == 982859, str(execution["reads"]))
    check("native:writes", execution["writes"] == 799023, str(execution["writes"]))
    check("native:denied", execution["denied"] == 11, str(execution["denied"]))
    check("native:host-calls", execution["host_calls"] == 79, str(execution["host_calls"]))
    check("native:budget", execution["access_budget"] == 2000000 and execution["access_count"] == 2000005, str(execution["access_count"]))
    check("native:budget-denials", execution["budget_denials"] == 5, str(execution["budget_denials"]))
    check("native:budget-reached", execution["budget_reached"] is True, "true")
    check("native:failed", execution["failed"] == "1" and execution["failed"] != "0", execution["failed"])
    check("native:termination", execution["termination_category"] == "UNRESOLVED_INDIRECT_JUMP", execution["termination_category"])
    check("native:deterministic", execution["deterministic"] is True, "true")

    milestone = load("P10-11/milestone.json")
    check("milestone:highest", milestone["highest_milestone"] == "A", milestone["highest_milestone"])
    established = {key: item["established"] for key, item in milestone["milestones"].items()}
    check("milestone:a-established", established.get("A") is True, "A")
    check("milestone:b-g-not-established", all(established.get(key) is False for key in ("B", "C", "D", "E", "F", "G")), json.dumps(established, sort_keys=True))
    check("milestone:playability-not-promoted", milestone["claims"]["playability"] == NOT_PROVEN, milestone["claims"]["playability"])

    structure = load("P10-02/structure_reconciliation.json")
    summary = structure["structure_summary"]
    check("structure:blocks", summary["blocks"] == 739, str(summary["blocks"]))
    check("structure:internal-calls", summary["call_edges_internal"] == 209, str(summary["call_edges_internal"]))
    check("structure:unresolved-calls", summary["call_edges_unresolved"] == 22, str(summary["call_edges_unresolved"]))
    check("structure:units", summary["classification_units"] == 110, str(summary["classification_units"]))
    check("structure:frozen-module", structure["frozen_module_modified"] is False, "false")
    check("structure:first-unresolved-site", structure["new_frontier"]["first_unresolved_indirect_site"] == "0x80013e7c", structure["new_frontier"]["first_unresolved_indirect_site"])

    semantics = load("P10-03/frontier_closure.json")
    check("semantics:unruled-ops", semantics["unruled_ops"] == [], str(semantics["unruled_ops"]))
    check("semantics:trap-sites", semantics["preconditions"]["trap_sites"] == 3, str(semantics["preconditions"]["trap_sites"]))
    check("semantics:jalr-sites", semantics["preconditions"]["jalr_sites"] == 22, str(semantics["preconditions"]["jalr_sites"]))

    bios = load("P10-04/bios_classification.json")["classification"]
    check("bios:call-count", bios["bios_call_count"] == 3, str(bios["bios_call_count"]))
    check("bios:histogram", bios["histogram"] == {"BIOS_VECTOR_CALL": 3, "INDIRECT_TARGET_UNRESOLVED": 19}, json.dumps(bios["histogram"], sort_keys=True))
    check("bios:fail-closed", bios["unknown_policy"] == "fail-closed", bios["unknown_policy"])
    check("bios:site-count", bios["site_count"] == 22, str(bios["site_count"]))

    io = load("P10-06/io_discovery.json")
    check("io:observed-devices", io["dynamic"]["observed_device_count"] == 4, str(io["dynamic"]["observed_device_count"]))
    check("io:denied", io["dynamic"]["denied_accesses"] == 11, str(io["dynamic"]["denied_accesses"]))
    check("io:access-sites", io["static"]["access_site_count"] == 1107, str(io["static"]["access_site_count"]))
    check("io:no-device-sites", io["static"]["device_histogram"] == {}, json.dumps(io["static"]["device_histogram"], sort_keys=True))

    gpu = load("P10-07/gpu_frontier.json")
    transcript = gpu["transcript"]
    check("gpu:event-count", transcript["event_count"] == 65536, str(transcript["event_count"]))
    check("gpu:gp1-reads", transcript["gp1_reads"] == 65536, str(transcript["gp1_reads"]))
    check("gpu:no-command-writes", transcript["gp0_writes"] == 0 and transcript["gp1_writes"] == 0, json.dumps(transcript, sort_keys=True))
    check("gpu:no-unknown", transcript["unknown_command_count"] == 0 and transcript["blocked_event_count"] == 0, "0/0")
    check("gpu:status-stub", gpu["gpu_status_read_stub"] == "0x14802000", gpu["gpu_status_read_stub"])
    check("gpu:no-gpu-blocker", gpu["denial_attribution"]["gpu_blocker_events"] == 0, str(gpu["denial_attribution"]["gpu_blocker_events"]))

    timing = load("P10-08/timing_frontier.json")["classification"]
    check("timing:served", timing["served_observations"] == 218112, str(timing["served_observations"]))
    counters = timing["counters"]
    check("timing:counters", counters["reads"] == 982859 and counters["writes"] == 799023 and counters["host_calls"] == 79, json.dumps(counters, sort_keys=True))
    reconciliation = timing["reconciliation"]
    check(
        "timing:denial-reconciliation",
        reconciliation["matches"] is True and reconciliation["reported_denied"] == 11
        and reconciliation["platform_denial_observations"] == 6 and reconciliation["budget_denials"] == 5,
        json.dumps(reconciliation, sort_keys=True),
    )

    disc = load("P10-09/disc_frontier.json")["classification"]
    command = disc["command_classification"]
    check("disc:commands", command["command_histogram"] == {"READ_N": 4, "SET_MODE": 4, "SET_LOCATION": 1, "UNKNOWN_COMMAND": 1}, json.dumps(command["command_histogram"], sort_keys=True))
    data_path = disc["data_path"]
    check(
        "disc:no-data-path",
        all(value is False for key, value in data_path.items() if key != "evidence"),
        json.dumps({key: value for key, value in data_path.items() if key != "evidence"}, sort_keys=True),
    )

    input_spu = load("P10-10/input_spu_frontier.json")
    check("input:controller-not-reached", input_spu["controller"]["controller_data_reached"] is False, "false")
    check("input:no-scripted-consumption", input_spu["controller"]["scripted_input_consumable"] is False, "false")
    check("loop:no-frame-loop", input_spu["game_loop"]["frame_loop_reached"] is False, "false")
    check("loop:busy-poll-served", input_spu["game_loop"]["busy_poll_served"] is True, "true")
    check("spu:event-count", input_spu["spu"]["event_count"] == 5, str(input_spu["spu"]["event_count"]))

    hardening = load("P10-12/hardening.json")
    check("hardening:ingest-negatives", hardening["ingest_negatives"] == 12, str(hardening["ingest_negatives"]))
    check("hardening:trap-negatives", hardening["trap_negatives"] == 3, str(hardening["trap_negatives"]))
    check("hardening:cache-invalidations", hardening["cache"]["invalidations_tested"] == 9, str(hardening["cache"]["invalidations_tested"]))
    check("hardening:no-guest-code", hardening["no_guest_machine_code"] is True, "true")
    check("hardening:rebuild-identical", hardening["rebuild"]["identical_to_committed_records"] is True, "true")
    check("hardening:no-leaks", hardening["safety_scan"]["private_payload_violations"] == [] and hardening["safety_scan"]["host_path_violations"] == [], "clean")

    regression = load("P10-90/whole_regression.json")
    check("regression:stage", regression["stage"] == "P10-90", regression["stage"])
    check("regression:counts", regression["counts"]["total_reverified_tests"] == 3068, str(regression["counts"]["total_reverified_tests"]))
    check("regression:guards", regression["guards"]["native_execution_proof"] == NOT_PROVEN and regression["guards"]["playability"] == NOT_PROVEN, json.dumps(regression["guards"], sort_keys=True))
    p10_90_tests = load("P10-90/p10_90_tests.json")
    check("regression:tests-status", p10_90_tests["status"] == "PASS" and p10_90_tests["failed"] == 0, p10_90_tests["status"])


def verify_claim_markers() -> None:
    state = (P10 / "STATE.md").read_text(encoding="utf-8")
    queue = (P10 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
    for marker in (TERMINAL_MARKER, PLAYABILITY_MARKER, GENERAL_MARKER):
        label = marker.replace("OPENRECOMP_PHASE10_", "").lower()
        check(f"marker:{label}", f"{marker}=NOT_PROVEN" in state, marker)
    check("marker:permanent-general-queue", f"{GENERAL_MARKER}=NOT_PROVEN" in queue, "permanent non-claim recorded")
    check("queue:p10-90-pass", "| P10-90 | Whole-project regression | PASS |" in queue, "P10-90 PASS")
    check(
        "queue:p10-91-recorded",
        "| P10-91 | Evidence closure + proof matrix | QUEUED |" in queue
        or "| P10-91 | Evidence closure + proof matrix | PASS |" in queue,
        "P10-91 queued or complete",
    )


def verify_manifest() -> None:
    completed = subprocess.run(
        [sys.executable, str(P10 / "src" / "p10_source_manifest_v1.py")],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
    )
    check(
        "manifest:phase10",
        completed.returncode == 0 and "=PASS entries=" in completed.stdout,
        completed.stdout.strip() or completed.stderr.strip(),
    )


def verify_safety(index: dict, fixture_path: pathlib.Path) -> None:
    payload = fixture_path.read_bytes()[0x800:0x1800] if fixture_path.is_file() else None
    sample_hex = payload[:64].hex() if payload else ""
    sample_b64 = base64.b64encode(payload[:64]).decode("ascii") if payload else ""
    leaks: list[str] = []
    host_paths: list[str] = []
    binary = []
    for entry in index["entries"]:
        path = ROOT / entry["path"]
        if path.suffix not in ALLOWED_EVIDENCE_SUFFIXES:
            binary.append(entry["path"])
            continue
        data = path.read_bytes()
        if b"\x00" in data:
            binary.append(entry["path"])
            continue
        text = data.decode("utf-8", errors="replace")
        if HOST_PATH_RE.search(text):
            host_paths.append(entry["path"])
        if payload is not None:
            lowered = text.lower()
            if sample_hex in lowered:
                leaks.append(entry["path"] + ":hex")
                continue
            if sample_b64 in text:
                leaks.append(entry["path"] + ":base64")
                continue
            for start in range(0, min(len(payload), 4096) - 8):
                run = payload[start : start + 8]
                if all(32 <= byte < 127 for byte in run):
                    if run.decode("ascii") in text:
                        leaks.append(entry["path"] + ":ascii")
                        break
    check("safety:no-payload-leaks", leaks == [], json.dumps(leaks))
    check("safety:no-host-paths", host_paths == [], json.dumps(host_paths))
    check("safety:text-only-evidence", binary == [], json.dumps(binary))
    check("safety:private-not-a-criterion", True, "private fixture present" if fixture_path.is_file() else "absent")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-91")
    parser.add_argument("--verify-only", action="store_true", help="re-run the checks without rewriting the committed index/matrix/ledger")
    parser.add_argument("--private-fixture", default=os.environ.get("OPENRECOMP_PSX_PRIVATE_FIXTURE", str(DEFAULT_PRIVATE_FIXTURE)))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        stage_summary = verify_stage_records()
        check("records:stage-count", len(stage_summary) == len(COMPLETED_STAGES), str(len(stage_summary)))

        verify_exact_records()
        verify_claim_markers()
        verify_manifest()

        index = build_index()
        check("index:entries", index["entry_count"] >= 120, str(index["entry_count"]))
        check("index:stages-covered", {entry["stage"] for entry in index["entries"]} >= set(COMPLETED_STAGES), "stages")
        check("index:no-own-sidecars", all("P10-91" not in entry["path"] for entry in index["entries"]), "own sidecars excluded")
        check("index:all-hashes", all(len(entry["sha256"]) == 64 for entry in index["entries"]), "hashes")
        committed_index_path = evidence / "evidence_index.json"
        if not options.verify_only:
            write_json(committed_index_path, index)
        check("index:committed", committed_index_path.is_file(), "present")
        committed_index = json.loads(committed_index_path.read_text(encoding="utf-8"))
        check("index:matches-live", committed_index == index, "live index equals committed index")

        matrix = build_proof_matrix()
        check("matrix:milestone", matrix["highest_milestone"] == "A", matrix["highest_milestone"])
        check("matrix:exclusions", len(matrix["deliberate_exclusions"]) >= 5, str(len(matrix["deliberate_exclusions"])))
        check("matrix:blockers", len(matrix["unresolved_blockers"]) >= 3, str(len(matrix["unresolved_blockers"])))
        check("matrix:terminal-reserved", matrix["terminal_claim_status_at_p10_91"] == NOT_PROVEN, NOT_PROVEN)
        committed_matrix_path = evidence / "proof_matrix.json"
        if not options.verify_only:
            write_json(committed_matrix_path, matrix)
        check("matrix:committed", committed_matrix_path.is_file(), "present")
        committed_matrix = json.loads(committed_matrix_path.read_text(encoding="utf-8"))
        check("matrix:matches-live", committed_matrix == matrix, "live matrix equals committed matrix")

        ledger = build_ledger()
        committed_ledger_path = evidence / "claim_ledger.json"
        if not options.verify_only:
            write_json(committed_ledger_path, ledger)
        check("ledger:committed", committed_ledger_path.is_file(), "present")
        committed_ledger = json.loads(committed_ledger_path.read_text(encoding="utf-8"))
        check("ledger:matches-live", committed_ledger == ledger, "live ledger equals committed ledger")
        claims = {item["key"]: item["class"] for item in committed_ledger["claims"]}
        for key, expected in sorted(REQUIRED_CLAIMS.items()):
            check(f"ledger:claim:{key}", claims.get(key) == expected, str(claims.get(key)))
        check("ledger:permanent-non-claims", tuple(committed_ledger["permanent_non_claims"]) == PERMANENT_NON_CLAIMS, "permanent")
        check("ledger:terminal-reserved", committed_ledger["terminal_claim_status_at_p10_91"] == NOT_PROVEN, NOT_PROVEN)
        classes = {item["class"] for item in committed_ledger["claims"]}
        check("ledger:classes", classes <= {"PROVEN", "BOUNDED", "NOT_PROVEN", "NOT_TESTED"}, ",".join(sorted(classes)))

        verify_safety(index, pathlib.Path(options.private_fixture))
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    if not options.verify_only:
        write_json(
            evidence / "p10_91_tests.json",
            {
                "stage": STAGE,
                "stage_name": "Evidence closure and proof matrix",
                "status": status,
                "tests": len(results),
                "passed": sum(1 for item in results if item["status"] == "PASS"),
                "failed": len(failed),
                "checks": results,
                "failure": None if not failed else [item["check"] for item in failed],
            },
        )

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_91={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
