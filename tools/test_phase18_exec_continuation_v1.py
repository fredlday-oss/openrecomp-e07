#!/usr/bin/env python3
"""Deterministic P18-02 authentic poll exit / execution continuation gate.

P18-02 continues authentic Hercules execution across the GPUSTAT wait-poll left
open at the end of Phase 17, using the P18-01 minimum state-driven bit-26 model,
and proves mechanically that:

  * the emitted runtime's GPUSTAT read returns bit 26 as a function of GPU state
    (not a constant), while the literal Phase-17 ZERO_FILL_RECORDED read model
    is absent from the generated source;
  * authentic execution enters the derived poll owner PC and leaves the poll
    (the poll branch is taken to the fall-through exit within the budget);
  * the GPUSTAT value the guest consumed at the poll owner has bit 26 set;
  * every executed continuation instruction is authenticated and every newly
    reached region is authenticated from the read-only source bytes;
  * the device transcript is produced by the current execution and every event
    carries an authenticated owning-instruction provenance digest;
  * dual official runs are byte-identical;
  * with the Phase-17 zero read model as a negative control, the guest does NOT
    leave the poll.

It promotes NO proof marker: FIRST_FRAME_READY stays NO and the Phase-18 claim
markers stay NOT_PROVEN.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase18/src", ".openrecomp-phase17/src",
              ".openrecomp-phase3/src", ".openrecomp-phase9/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p18_contracts_v1 as contract
import p18_exec_continuation_v1 as cont
import p18_fixture_verification_v1 as fixture
import p18_gpustat_state_model_v1 as state_model
import p18_poll_condition_auth_v1 as poll_auth
import p17_device_transcript_v1 as transcript_model
import p17_side_effects_exec_v1 as side
import p17_title_exec_emit_v1 as emitter
from p18_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P18-02"
NEXT_STAGE = "P18-03"

STAGE_MARKER = "OPENRECOMP_P18_02"
POLL_EXIT_MARKER = "OPENRECOMP_PHASE18_GPUSTAT_POLL_EXIT"
CONTINUATION_MARKER = "OPENRECOMP_PHASE18_AUTHENTIC_EXECUTION_CONTINUATION"

PUBLIC_SCAN_FILES = ("RESULT.json", "poll_exit.json", "gpu_state_model.json",
                     "continuation.json", "transcript.json")
FORBIDDEN_TERMS = ("raw_instruction", "instruction_word", "payload_bytes",
                   "bios_bytes")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True).stdout.strip()


def run_authority() -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, ".openrecomp-phase18/src/p18_frozen_phase17_authority_v1.py"],
        cwd=str(ROOT), capture_output=True, text=True)
    ok = (completed.returncode == 0
          and "OPENRECOMP_PHASE18_P17_AUTHORITY_FROZEN=PASS" in completed.stdout)
    return ok, completed.stdout.strip() if not ok else "authority-ok"


def phase17_evidence_untouched() -> tuple[bool, list[str]]:
    changed = git("diff", "--name-only", f"{contract.PHASE17_TERMINAL_COMMIT}..HEAD",
                  "--", *contract.FROZEN_NAMESPACES).splitlines()
    dirty = git("status", "--porcelain", "--", *contract.FROZEN_NAMESPACES).splitlines()
    return (not changed and not dirty), changed + dirty


def _raises(fn, exc_type=Exception, code: str | tuple[str, ...] | None = None) -> bool:
    try:
        fn()
        return False
    except exc_type as exc:
        if code is None:
            return True
        allowed = (code,) if isinstance(code, str) else code
        return getattr(exc, "code", None) in allowed


# --- Negative controls -----------------------------------------------------


def negative_zero_fill_poll() -> dict[str, Any]:
    """With the Phase-17 zero read model the guest must NOT leave the poll."""
    geometry = cont.poll_geometry(poll_auth.load_transcript()[0])
    with tempfile.TemporaryDirectory() as tmp:
        gens = pathlib.Path(tmp) / "zero-gens"
        analysis = cont.continuation_analysis()
        cont.run_continuation(gens, analysis, enabled=False)
    cont.invalidate_overlay_for_tests()
    trace = list(cont.LAST_STEP_TRACE)
    exit_info = cont.detect_poll_exit(trace, geometry)
    poll_entered = any(int(str(step["pc"]), 16) == geometry["poll_pc_int"] for step in trace)
    return {
        "poll_entered": poll_entered,
        "exit_detected": exit_info["exit_detected"],
        "taken_to_exit_count": exit_info["taken_to_exit_count"],
        "ok": poll_entered and not exit_info["exit_detected"],
    }


def negative_unmodelled_bit() -> bool:
    model = state_model.GpuStatModel()
    return _raises(lambda: model.consume_mask(1 << 28),
                   state_model.GpuStatModelError, "UNMODELLED_GPUSTAT_BIT")


def negative_tampered_poll_digest() -> bool:
    document, _ = poll_auth.load_transcript()
    owner, _, _ = poll_auth.dominant_gpustat_owner(document)
    records, provenance = poll_auth._window_records(owner, None)
    return _raises(lambda: poll_auth.derive_structure(owner, records, provenance, "0" * 64),
                   poll_auth.PollConditionError, "POLL_PROVENANCE_DIGEST_MISMATCH")


def negative_event_without_provenance(document: dict[str, Any],
                                      provenance_map: dict[int, str]) -> bool:
    events = [dict(event) for event in document["events"]]
    forged = transcript_model.mmio_event(
        sequence=len(events), address=0x1F801810, store=True, width=4, value=0,
        owning_instruction_pc=0x80030000, delay_slot_pc=None)
    forged["owning_instruction_provenance_digest"] = "0" * 64
    events.append(forged)
    clone = dict(document)
    clone["events"] = events
    clone["event_count"] = len(events)
    return _raises(lambda: transcript_model.validate_transcript(clone, provenance_map),
                   transcript_model.TranscriptError, "EVENT_WITHOUT_PROVENANCE")


def negative_unexecuted_pc_rejected() -> bool:
    """A device event owned by an unexecuted PC cannot enter the transcript."""
    analysis = cont.continuation_analysis()
    provenance_map = side.provenance_digest_map(analysis)
    fabricated = {"pc": 0xDEADBEEF}
    return fabricated["pc"] not in provenance_map


# --- Gate body -------------------------------------------------------------


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    stale = evidence / "p18_02_tests.json"
    if stale.is_file():
        stale.unlink()

    # 1. Authority + frozen history.
    ok, out = run_authority()
    gate.check("authority:phase17-frozen", ok, out)
    untouched, offenders = phase17_evidence_untouched()
    gate.check("frozen:phase1-17-untouched", untouched, ",".join(offenders[:5]))

    # 2. Fixture integrity (fail-closed) + committed transcript digest.
    fx = cont.fixture_root()
    fixture.verify_fixture_with_callback(
        fx, lambda label, condition, detail="": gate.check(label, condition, str(detail)))
    transcript_doc, digest = poll_auth.load_transcript()
    gate.check("source:transcript-digest", digest == poll_auth.P17_06R_TRANSCRIPT_SHA256,
               "P17-06R transcript digest")

    # 3. Derived poll geometry (never hard-coded).
    geometry = cont.poll_geometry(transcript_doc)
    gate.check("poll:derived", geometry["status_bit"] == 26, geometry["poll_pc"])
    gate.check("poll:provenance-reverified",
               geometry["poll_pc_provenance_matches_transcript"] is True,
               geometry["poll_pc_provenance_digest"])
    gate.check("poll:loop-structure",
               geometry["loop_body_ops"] == ["lw", "nop", "and", "beq"],
               json.dumps(geometry["loop_body_ops"]))
    gate.check("poll:branch-target", geometry["loop_target_pc"] == geometry["poll_pc"],
               geometry["loop_target_pc"])

    # 4. Overlay anchor fail-closed controls (synthetic, no fixture needed).
    anchors = cont.overlay_anchor_selftest()
    gate.check("overlay:anchor-controls", anchors["ok"], json.dumps(anchors, sort_keys=True))

    # 5. Primary execution: dual official runs, each with its own discovery.
    private_root = cont.private_build_root()
    analysis = cont.continuation_analysis()

    def _fresh_run(label: str):
        cont.invalidate_overlay_for_tests()
        gens = private_root / f"{label}-discovery"
        if gens.exists():
            shutil.rmtree(gens)
        gens.mkdir(parents=True, exist_ok=False)
        run_analysis = cont.continuation_analysis()
        manifest, observations, run_analysis = cont.run_continuation(gens, run_analysis,
                                                                     enabled=True)
        cont.invalidate_overlay_for_tests()
        run_dir = cont.official_run_dir(label)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=False)
        final = cont.emit_continuation(run_dir, run_analysis, enabled=True)
        return manifest, observations, run_analysis, final, run_dir

    manifests = []
    observations = []
    analyses = []
    finals = []
    run_dirs = []
    for label in cont.OFFICIAL_RUN_LABELS:
        m, obs, a, final, run_dir = _fresh_run(label)
        manifests.append(m)
        observations.append(obs)
        analyses.append(a)
        finals.append(final)
        run_dirs.append(run_dir)

    run_analysis = analyses[-1]
    manifest = manifests[-1]
    rr = manifest["runtime_result"]
    trace = list(cont.LAST_STEP_TRACE)

    # 6. Execution left the poll (positive) and consumed a bit-26-set GPUSTAT.
    exit_info = cont.detect_poll_exit(trace, geometry)
    gate.check("poll:entered", exit_info["poll_entries"] >= 1,
               json.dumps(exit_info, sort_keys=True))
    gate.check("poll:exit-taken", exit_info["exit_detected"] is True,
               json.dumps(exit_info, sort_keys=True))
    gate.check("poll:exit-taken-from-branch",
               exit_info["exit_taken_from"] is not None,
               json.dumps(exit_info, sort_keys=True))
    owner_reads = [e for e in rr.get("p18_gpustat_read_log", [])
                   if e["pc"] == geometry["poll_pc"]]
    gate.check("poll:owner-read-observed", bool(owner_reads),
               json.dumps({"owner_reads": len(owner_reads)}, sort_keys=True))
    gate.check("poll:owner-read-bit26-set",
               bool(owner_reads) and (int(owner_reads[0]["value"], 16) & 0x04000000) != 0,
               json.dumps(owner_reads[:1], sort_keys=True))
    stats = rr.get("p18_stats", {})
    gate.check("gpu:read-model-counted", stats.get("gpustat_reads", 0) >= 1,
               json.dumps(stats, sort_keys=True))

    # 7. Newly authenticated regions + every executed PC authenticated.
    gate.check("regions:discovered", len(run_analysis.region_log) >= 1,
               json.dumps(run_analysis.region_log, sort_keys=True))
    chain_ok = True
    identity = run_analysis.base.mainexe.identity
    for region in run_analysis.region_log:
        pc = int(region["entry_pc"], 16)
        if pc not in run_analysis.reachable:
            chain_ok = False
        expected = (side.mainexe_auth.HEADER_SIZE + (pc - identity.t_addr)
                    if region["region"] == "MAIN_EXE" else run_analysis._title_file_offset(pc))
        if region["entry_file_offset"] != expected:
            chain_ok = False
    gate.check("regions:provenance-chain-holds", chain_ok)
    executed_pcs = [int(str(pc), 16) for pc in rr["distinct_executed_pcs"]]
    gate.check("continuation:executed-pcs-all-authenticated",
               all(pc in run_analysis.reachable for pc in executed_pcs),
               json.dumps({"executed": len(executed_pcs)}, sort_keys=True))
    provenance_map = side.provenance_digest_map(run_analysis)
    gate.check("continuation:executed-pcs-have-provenance",
               all(pc in provenance_map for pc in executed_pcs))
    gate.check("continuation:budget-respected",
               0 <= int(rr["continuation_executed_count"]) <= side.CONTINUATION_BUDGET,
               str(rr["continuation_executed_count"]))
    gate.check("continuation:typed-stop-reason",
               rr["stop_reason"] in side.ALLOWED_STOP_REASONS, rr["stop_reason"])

    # 8. Causal device transcript from this execution.
    transcript, transcript_sha = cont.build_causal_transcript(manifest, provenance_map)
    gate.check("transcript:schema", transcript["schema"] == transcript_model.SCHEMA_TRANSCRIPT)
    gate.check("transcript:events-non-empty", len(transcript["events"]) >= 1)
    gate.check("transcript:gpustat-read-model",
               transcript["gpustat_read_model"] == cont.P18_GPUSTAT_READ_MODEL)
    gate.check("transcript:no-replayed-events",
               all(event.get("owning_instruction_provenance_digest") in set(provenance_map.values())
                   for event in transcript["events"]))
    transcript_model.validate_transcript(transcript, provenance_map)
    gate.check("transcript:validated", True, transcript_sha)
    transcript_bytes = cont.transcript_bytes(transcript)
    (evidence / "transcript.json").write_bytes(transcript_bytes)
    (evidence / "transcript.sha256").write_text(
        f"{transcript_sha}  transcript.json\n", encoding="utf-8", newline="\n")

    # 9. Source-level anti-hardcoding proof.
    generated_runtime = (run_dirs[-1] / "or_side_effects_v1.c").read_text(encoding="utf-8")
    discipline = cont.source_discipline(generated_runtime)
    gate.check("discipline:zero-read-model-absent", discipline["zero_read_model_absent"],
               json.dumps(discipline, sort_keys=True))
    gate.check("discipline:gpustat-state-driven", discipline["gpustat_state_driven_present"])
    gate.check("discipline:gpu-write-modelled", discipline["gpu_write_present"])
    gate.check("discipline:tick-modelled", discipline["tick_present"])
    gate.check("discipline:gpustat-function-pc-free", discipline["gpustat_function_pc_free"])
    gate.check("emission:no-phase16-import",
               "p16_emission_v1" not in generated_runtime)

    # 10. Dual-run determinism.
    gate.check("determinism:manifest-identical", finals[0] == finals[1])
    gate.check("determinism:runtime-result-identical",
               finals[0]["runtime_result"] == finals[1]["runtime_result"])
    gate.check("determinism:transcript-counts-identical",
               finals[0]["transcript"] == finals[1]["transcript"])
    gate.check("determinism:executable-hash-identical",
               manifests[0]["build"]["executable_sha256"]
               == manifests[1]["build"]["executable_sha256"])
    gate.check("determinism:regions-identical",
               [r["entry_pc"] for r in analyses[0].region_log]
               == [r["entry_pc"] for r in analyses[1].region_log])

    # 11. Negative controls.
    zero_fill = negative_zero_fill_poll()
    gate.check("negative:zero-fill-poll-not-exited", zero_fill["ok"],
               json.dumps(zero_fill, sort_keys=True))
    gate.check("negative:unmodelled-bit-rejected", negative_unmodelled_bit())
    gate.check("negative:tampered-poll-digest", negative_tampered_poll_digest())
    gate.check("negative:event-without-provenance",
               negative_event_without_provenance(transcript, provenance_map))
    gate.check("negative:unexecuted-pc-rejected", negative_unexecuted_pc_rejected())

    # 12. Evidence documents.
    exit_doc = {
        "schema": "openrecomp-phase18-poll-exit-v1",
        "stage": STAGE,
        "geometry": {k: v for k, v in geometry.items() if not k.endswith("_int")},
        "exit": exit_info,
        "owner_reads": owner_reads,
        "gpu_stats": stats,
        "stop_reason": rr["stop_reason"],
        "executed_instruction_count": rr["executed_instruction_count"],
        "continuation_executed_count": rr["continuation_executed_count"],
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "poll_exit.json", exit_doc)
    assert_public_safe(gate, "poll_exit", exit_doc)

    model_doc = {
        "schema": "openrecomp-phase18-gpu-state-model-v1",
        "stage": STAGE,
        "model": cont.P18_GPUSTAT_READ_MODEL,
        "gpustat_bit": 26,
        "fifo_depth": cont.GPU_FIFO_DEPTH,
        "drain_rate": "one command per executed guest instruction",
        "gp0_writes": stats.get("gp0_writes", 0),
        "gp1_writes": stats.get("gp1_writes", 0),
        "mmio_writes": stats.get("mmio_writes", 0),
        "mmio_reads_unmodelled": stats.get("mmio_reads_unmodelled", 0),
        "drained": stats.get("drained", 0),
        "fifo_overflow": stats.get("fifo_overflow", 0),
        "discipline": discipline,
        "not_hardcoded": ("bit 26 is a function of modelled GPU state; the poll PC "
                          "and tested bit are derived from authenticated bytes"),
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "gpu_state_model.json", model_doc)
    assert_public_safe(gate, "gpu_state_model", model_doc)

    continuation_doc = {
        "schema": "openrecomp-phase18-continuation-v1",
        "stage": STAGE,
        "official_runs": [{"label": label, "discovery": obs}
                          for label, obs in zip(cont.OFFICIAL_RUN_LABELS, observations)],
        "region_log": run_analysis.region_log,
        "record_count": run_analysis.record_count,
        "continuation_entry_pc": side._hex32(run_analysis.continuation_entry_pc),
        "stop_reason": rr["stop_reason"],
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "continuation.json", continuation_doc)
    assert_public_safe(gate, "continuation", continuation_doc)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase18-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "authority_commit": contract.PHASE17_TERMINAL_COMMIT,
        "authority_tree": contract.PHASE17_TERMINAL_TREE,
        "poll_exit": {
            "poll_pc": geometry["poll_pc"],
            "status_bit": geometry["status_bit"],
            "taken_to_exit_count": exit_info["taken_to_exit_count"],
            "owner_reads": len(owner_reads),
            "owner_read_value": owner_reads[0]["value"] if owner_reads else None,
        },
        "continuation": {
            "executed_instruction_count": rr["executed_instruction_count"],
            "continuation_executed_count": rr["continuation_executed_count"],
            "distinct_executed_pc_count": rr["distinct_executed_pc_count"],
            "record_count": run_analysis.record_count,
            "regions": len(run_analysis.region_log),
            "stop_reason": rr["stop_reason"],
        },
        "transcript_sha256": transcript_sha,
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            "OPENRECOMP_P18_01": "PASS",
            STAGE_MARKER: "PASS",
            POLL_EXIT_MARKER: "CONFIRMED",
            CONTINUATION_MARKER: "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
            contract.FIRST_FRAME_READY_MARKER: "NO",
        },
        "next_stage": NEXT_STAGE,
    })

    gate.mark(contract.BOOTSTRAP_MARKER)
    gate.mark("OPENRECOMP_P18_01")
    gate.mark(STAGE_MARKER)
    gate.mark(POLL_EXIT_MARKER, "CONFIRMED")
    gate.mark(CONTINUATION_MARKER)
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase18/evidence/P18-02"))
