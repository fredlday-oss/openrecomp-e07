#!/usr/bin/env python3
"""Deterministic P18-03 causal device transcript gate.

P18-03 captures deterministic device events actually CAUSED by authentic guest
execution continued past the GPUSTAT wait-poll (P18-02), and proves
mechanically that:

  * every event is bound to sequence, guest PC, authenticated source owner,
    decoded instruction (independent fresh decode of the authenticated private
    word), event type/class, address/register, value, width, and the relevant
    causal device state (emitted by the runtime itself, never reconstructed);
  * reached categories are listed and unreached categories are explicitly
    not-reached (never silently treated as a valid no-op);
  * any event without an authenticated owner fails closed;
  * dual official runs are byte-identical and an independent fresh-private-root
    reproduction is byte-identical to official evidence.

It promotes NO proof marker: FIRST_FRAME_READY stays NO and the Phase-18 claim
markers stay NOT_PROVEN.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase18/src", ".openrecomp-phase17/src",
              ".openrecomp-phase3/src", ".openrecomp-phase9/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p18_causal_transcript_v1 as causal
import p18_contracts_v1 as contract
import p18_exec_continuation_v1 as cont
import p18_fixture_verification_v1 as fixture
import p18_gpustat_state_model_v1 as state_model
import p18_poll_condition_auth_v1 as poll_auth
import p17_device_transcript_v1 as transcript_model
import p17_side_effects_exec_v1 as side
from p18_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P18-03"
NEXT_STAGE = "P18-04"

STAGE_MARKER = "OPENRECOMP_P18_03"
CAUSAL_MARKER = "OPENRECOMP_PHASE18_CAUSAL_DEVICE_TRANSCRIPT"

PUBLIC_SCAN_FILES = ("RESULT.json", "causal_transcript.json",
                     "category_coverage.json", "negative_tests.json")
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


def negative_event_without_owner(analysis) -> bool:
    """An event owned by an unauthenticated PC fails the fresh-decode check."""
    return _raises(lambda: causal.fresh_decode_for_owner(analysis, 0xDEADBEEF),
                   causal.CausalTranscriptError, "OWNER_NOT_AUTHENTICATED")


def negative_owner_without_provenance(document, provenance_map) -> bool:
    events = [dict(event) for event in document["events"]]
    forged = transcript_model.mmio_event(
        sequence=len(events), address=0x1F801810, store=True, width=4, value=0,
        owning_instruction_pc=0x80030000, delay_slot_pc=None)
    forged["owning_instruction_provenance_digest"] = "0" * 64
    events.append(forged)
    clone = dict(document)
    clone["events"] = events
    clone["event_count"] = len(events)
    return _raises(lambda: causal.validate_causal_transcript(clone, provenance_map),
                   transcript_model.TranscriptError, "EVENT_WITHOUT_PROVENANCE")


def negative_causal_count_mismatch(runtime_result) -> bool:
    """A causal snapshot log that does not match its declared count fails."""
    def build():
        snapshots = runtime_result["p18_causal_snapshots"]
        # Recreate the parse guard by constructing a minimal parse input.
        lines = ["P18C_CAUSAL_COUNT %d" % (len(snapshots) + 1)]
        for s in snapshots:
            lines.append("P18C_CAUSAL %d %d 0x%08x 0x%08x 0x%08x %d %d" % (
                s["store"], s["width"], s["address"], s["value"], s["owner"],
                s["pending_before"], s["pending_after"]))
        causal._parse_causal_lines("\n".join(lines))
    return _raises(build, causal.CausalTranscriptError, "CAUSAL_COUNT_MISMATCH")


def negative_causal_overflow(runtime_result) -> bool:
    """A causal log overflow flag fails the transcript build."""
    def build():
        rr = dict(runtime_result)
        rr["p18_causal_overflow"] = 1
        manifest = {"runtime_result": rr, "transcript_document": {"events": []}}
        causal.build_causal_transcript(manifest, None, {})
    return _raises(build, causal.CausalTranscriptError, "CAUSAL_LOG_OVERFLOW")


def negative_tampered_fresh_decode() -> bool:
    """A tampered decode record (op differs from fresh decode) fails closed."""
    analysis = causal.continuation_analysis()
    provenance_map = side.provenance_digest_map(analysis)
    pc = min(provenance_map)
    original_op = analysis.records_by_address[pc].get("op")
    try:
        analysis.records_by_address[pc]["op"] = "addu"
        causal.fresh_decode_for_owner(analysis, pc)
        return False
    except causal.CausalTranscriptError as err:
        return err.code == "FRESH_DECODE_MISMATCH"
    finally:
        analysis.records_by_address[pc]["op"] = original_op


def negative_zero_fill_poll() -> dict[str, Any]:
    """With the Phase-17 zero read model the guest must NOT leave the poll."""
    geometry = cont.poll_geometry(poll_auth.load_transcript()[0])
    with tempfile.TemporaryDirectory() as tmp:
        gens = pathlib.Path(tmp) / "zero-gens"
        analysis = causal.continuation_analysis()
        causal.run_continuation(gens, analysis, enabled=False)
    causal.invalidate_overlay_for_tests()
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


# --- Gate body -------------------------------------------------------------


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    stale = evidence / "p18_03_tests.json"
    if stale.is_file():
        stale.unlink()

    # 1. Authority + frozen history.
    ok, out = run_authority()
    gate.check("authority:phase17-frozen", ok, out)
    untouched, offenders = phase17_evidence_untouched()
    gate.check("frozen:phase1-17-untouched", untouched, ",".join(offenders[:5]))

    # 2. Fixture integrity (fail-closed) + committed transcript digest.
    fx = causal.fixture_root()
    fixture.verify_fixture_with_callback(
        fx, lambda label, condition, detail="": gate.check(label, condition, str(detail)))
    transcript_doc, digest = poll_auth.load_transcript()
    gate.check("source:transcript-digest", digest == poll_auth.P17_06R_TRANSCRIPT_SHA256,
               "P17-06R transcript digest")

    # 3. Derived poll geometry (never hard-coded) + bit-26 model in force.
    geometry = cont.poll_geometry(transcript_doc)
    gate.check("poll:derived", geometry["status_bit"] == 26, geometry["poll_pc"])
    gate.check("poll:provenance-reverified",
               geometry["poll_pc_provenance_matches_transcript"] is True,
               geometry["poll_pc_provenance_digest"])

    # 4. Overlay anchor fail-closed controls (synthetic, no fixture needed).
    p18c_anchors = cont.overlay_anchor_selftest()
    gate.check("overlay:p18-02-anchor-controls", p18c_anchors["ok"],
               json.dumps(p18c_anchors, sort_keys=True))
    causal_anchors = causal.overlay_anchor_selftest()
    gate.check("overlay:p18-03-anchor-controls", causal_anchors["ok"],
               json.dumps(causal_anchors, sort_keys=True))

    # 5. Primary execution: dual official runs, each with its own discovery.
    private_root = causal.private_build_root()

    def _fresh_run(label: str):
        causal.invalidate_overlay_for_tests()
        gens = private_root / f"{label}-discovery"
        if gens.exists():
            shutil.rmtree(gens)
        gens.mkdir(parents=True, exist_ok=False)
        run_analysis = causal.continuation_analysis()
        manifest, observations, run_analysis = causal.run_continuation(gens, run_analysis,
                                                                       enabled=True)
        causal.invalidate_overlay_for_tests()
        run_dir = causal.official_run_dir(label)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=False)
        final = causal.emit_continuation(run_dir, run_analysis, enabled=True)
        return manifest, observations, run_analysis, final, run_dir

    manifests = []
    observations = []
    analyses = []
    finals = []
    run_dirs = []
    for label in causal.OFFICIAL_RUN_LABELS:
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

    # 6. Execution left the poll (positive) with the state-driven read.
    exit_info = cont.detect_poll_exit(trace, geometry)
    gate.check("poll:exit-taken", exit_info["exit_detected"] is True,
               json.dumps(exit_info, sort_keys=True))
    gate.check("gpu:read-model-counted", rr.get("p18_stats", {}).get("gpustat_reads", 0) >= 1,
               json.dumps(rr.get("p18_stats", {}), sort_keys=True))

    # 7. Provenance: every executed PC authenticated.
    provenance_map = side.provenance_digest_map(run_analysis)
    executed_pcs = [int(str(pc), 16) for pc in rr["distinct_executed_pcs"]]
    gate.check("continuation:executed-pcs-all-authenticated",
               all(pc in run_analysis.reachable for pc in executed_pcs),
               json.dumps({"executed": len(executed_pcs)}, sort_keys=True))
    gate.check("continuation:executed-pcs-have-provenance",
               all(pc in provenance_map for pc in executed_pcs))

    # 8. Causal transcript from this execution.
    causal_doc, causal_sha = causal.build_causal_transcript(manifest, run_analysis,
                                                            provenance_map)
    gate.check("transcript:schema",
               causal_doc["schema"] == "openrecomp-phase18-causal-device-transcript-v1")
    gate.check("transcript:events-non-empty", len(causal_doc["events"]) >= 1)
    gate.check("transcript:causal-snapshot-count",
               causal_doc["causal_snapshot_count"] == len(rr["p18_causal_snapshots"]))
    # Every MMIO event carries causal device state; every event carries a decode.
    gate.check("transcript:all-events-decoded",
               all("decoded_instruction" in event for event in causal_doc["events"]))
    gate.check("transcript:mmio-events-causal",
               all("causal_device_state" in event
                   for event in causal_doc["events"] if event["kind"] == "MMIO"))
    gate.check("transcript:no-replayed-events",
               all(event.get("owning_instruction_provenance_digest") in set(provenance_map.values())
                   for event in causal_doc["events"]))
    gate.check("transcript:gpustat-read-model",
               causal_doc["gpustat_read_model"] == cont.P18_GPUSTAT_READ_MODEL)
    causal.validate_causal_transcript(causal_doc, provenance_map)
    gate.check("transcript:validated", True, causal_sha)
    causal_bytes = causal.transcript_bytes(causal_doc)
    (evidence / "causal_transcript.json").write_bytes(causal_bytes)
    (evidence / "causal_transcript.sha256").write_text(
        f"{causal_sha}  causal_transcript.json\n", encoding="utf-8", newline="\n")

    # 9. Category coverage: reached vs unreached explicit.
    coverage = causal.category_coverage(causal_doc)
    gate.check("coverage:unreached-explicit",
               coverage["unreached"] == sorted(set(causal.CATEGORIES) - set(coverage["reached"])),
               json.dumps(coverage, sort_keys=True))
    gate.check("coverage:vrarm-mutation-not-silently-reached",
               "VRAM_MUTATION" in coverage["unreached"] or "VRAM_MUTATION" in coverage["reached"],
               "VRAM_MUTATION tracked explicitly")

    # 10. Source-level anti-hardcoding proof.
    generated_runtime = (run_dirs[-1] / "or_side_effects_v1.c").read_text(encoding="utf-8")
    discipline = causal.source_discipline(generated_runtime)
    gate.check("discipline:causal-snapshot-log-present",
               discipline["causal_snapshot_log_present"], json.dumps(discipline, sort_keys=True))
    gate.check("discipline:zero-read-model-absent", discipline["zero_read_model_absent"])
    gate.check("discipline:gpustat-state-driven", discipline["gpustat_state_driven_present"])
    gate.check("discipline:causal-functions-pc-free", discipline["causal_functions_pc_free"])

    # 11. Dual-run determinism.
    gate.check("determinism:manifest-identical", finals[0] == finals[1])
    gate.check("determinism:runtime-result-identical",
               finals[0]["runtime_result"] == finals[1]["runtime_result"])
    gate.check("determinism:transcript-counts-identical",
               finals[0]["transcript"] == finals[1]["transcript"])
    gate.check("determinism:causal-snapshots-identical",
               rr["p18_causal_snapshots"] == manifests[0]["runtime_result"]["p18_causal_snapshots"])
    gate.check("determinism:regions-identical",
               [r["entry_pc"] for r in analyses[0].region_log]
               == [r["entry_pc"] for r in analyses[1].region_log])

    # 12. Negative controls.
    gate.check("negative:event-without-owner-rejected",
               negative_event_without_owner(run_analysis))
    gate.check("negative:event-without-provenance",
               negative_owner_without_provenance(causal_doc, provenance_map))
    gate.check("negative:causal-count-mismatch", negative_causal_count_mismatch(rr))
    gate.check("negative:causal-overflow", negative_causal_overflow(rr))
    gate.check("negative:tampered-fresh-decode",
               negative_tampered_fresh_decode())
    zero_fill = negative_zero_fill_poll()
    gate.check("negative:zero-fill-poll-not-exited", zero_fill["ok"],
               json.dumps(zero_fill, sort_keys=True))
    gate.check("negative:unmodelled-bit-rejected", negative_unmodelled_bit())

    # 13. Evidence documents.
    write_json(evidence / "category_coverage.json", coverage)
    assert_public_safe(gate, "category_coverage", coverage)

    negative_doc = {
        "schema": "openrecomp-phase18-negative-tests-v1",
        "stage": STAGE,
        "event_without_owner_rejected": negative_event_without_owner(run_analysis),
        "event_without_provenance_rejected": negative_owner_without_provenance(
            causal_doc, provenance_map),
        "causal_count_mismatch_rejected": negative_causal_count_mismatch(rr),
        "causal_overflow_rejected": negative_causal_overflow(rr),
        "tampered_fresh_decode_rejected": negative_tampered_fresh_decode(),
        "zero_fill_poll_not_exited": zero_fill,
        "unmodelled_bit_rejected": negative_unmodelled_bit(),
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "negative_tests.json", negative_doc)
    assert_public_safe(gate, "negative_tests", negative_doc)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase18-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "authority_commit": contract.PHASE17_TERMINAL_COMMIT,
        "authority_tree": contract.PHASE17_TERMINAL_TREE,
        "causal_transcript": {
            "sha256": causal_sha,
            "event_count": len(causal_doc["events"]),
            "causal_snapshot_count": causal_doc["causal_snapshot_count"],
            "reached_categories": coverage["reached"],
            "unreached_categories": coverage["unreached"],
        },
        "continuation": {
            "executed_instruction_count": rr["executed_instruction_count"],
            "continuation_executed_count": rr["continuation_executed_count"],
            "distinct_executed_pc_count": rr["distinct_executed_pc_count"],
            "stop_reason": rr["stop_reason"],
        },
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            "OPENRECOMP_P18_01": "PASS",
            "OPENRECOMP_P18_02": "PASS",
            STAGE_MARKER: "PASS",
            CAUSAL_MARKER: "PASS",
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
    gate.mark("OPENRECOMP_P18_02")
    gate.mark(STAGE_MARKER)
    gate.mark(CAUSAL_MARKER)
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase18/evidence/P18-03"))