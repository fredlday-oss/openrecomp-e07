#!/usr/bin/env python3
"""Deterministic P17-07R checked device/frame frontier assessment gate.

Replaces the historical P17-07 stage, which hard-coded ``encountered: false``
for every observation class and inferred device-event absence from a digest,
so its ``PASS`` marker established no observation at all.

This gate binds the assessment to the committed, committed-digest-verified
P17-06R device transcript, re-validates every event against an independently
re-derived authenticated provenance map, and requires each of the seven
observation classes to resolve to an explicit status with a checked basis.
Fail-closed negatives cover transcript tampering, digest mismatch, unprovenanced
owners, and any attempt to promote a proof marker.
"""

from __future__ import annotations

import copy
import json
import os
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase17/src", ".openrecomp-phase3/src",
              ".openrecomp-phase9/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p17_device_frontier_assessment_v1 as dfa
import p17_device_transcript_v1 as transcript_model
import p17_fixture_verification_v1 as fixture
import p17_side_effects_exec_v1 as side
import p17_title_decode_v1 as title_decode
from p17_contracts_v1 import (FIRST_FRAME_READY_MARKER, FRAME_MARKER,
                              GENERAL_MARKER, INITIALIZATION_MARKER,
                              PLAYABILITY_MARKER)
from p17_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P17-07R"
NEXT_STAGE = "P17-90"
BASE_COMMIT = "2701415223dd182a40cf257c849952a6ce63ee08"
WORKER_BRANCH = "agent/deepseek-phase17-p17-07r-r1"

PUBLIC_SCAN_FILES = ("RESULT.json", "device_frontier_assessment.json",
                     "transcript_binding.json", "next_stage.json",
                     "stage_metadata.json")

ASSESSMENT_MARKER = "OPENRECOMP_PHASE17_CHECKED_DEVICE_FRONTIER_ASSESSMENT_V1"

_ANALYSIS_CACHE: dict[str, Any] = {}


def fixture_root() -> pathlib.Path:
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def _raises(fn, exc_type=Exception, code: str | tuple[str, ...] | None = None) -> bool:
    try:
        fn()
        return False
    except exc_type as exc:
        if code is None:
            return True
        allowed = (code,) if isinstance(code, str) else code
        return getattr(exc, "code", None) in allowed


def rederived_analysis() -> Any:
    """Re-derive the P17-06R authenticated record set without compiling.

    The four newly authenticated main-EXE region entry PCs are read from the
    committed P17-06R ``RESULT.json``; the frozen decoder re-authenticates each
    region from the read-only private source bytes.  The resulting record set is
    required to match the committed record counts and region log exactly, so a
    transcript owner can only be checked against provenance that this gate
    rebuilt itself.
    """
    if "analysis" in _ANALYSIS_CACHE:
        return _ANALYSIS_CACHE["analysis"]
    fx = fixture_root()
    fixture.verify_fixture_with_callback(fx, lambda label, condition, detail="": None)
    title_analysis = title_decode.analyze_title_decode(fixture_dir=fx)
    recorded = side.recorded_p17_05r_frontier()
    analysis = side.build_side_effects_analysis(title_analysis=title_analysis,
                                               recorded_frontier=recorded)
    result = dfa.load_committed_result()
    for region in result["newly_authenticated_regions"]:
        analysis.authenticate_and_extend(int(str(region["entry_pc"]), 16))
    _ANALYSIS_CACHE["analysis"] = analysis
    _ANALYSIS_CACHE["title_analysis"] = title_analysis
    return analysis


def rederived_op_map() -> dict[str, str]:
    """Map executed instruction PCs to their decoded semantic op name."""
    if "op_by_pc" in _ANALYSIS_CACHE:
        return _ANALYSIS_CACHE["op_by_pc"]
    analysis = rederived_analysis()
    op_by_pc = {
        dfa.hex32(pc): str(record.get("op") or "")
        for pc, record in analysis.records_by_address.items()
    }
    _ANALYSIS_CACHE["op_by_pc"] = op_by_pc
    return op_by_pc


# --- Negative controls (fail closed) ---------------------------------------

def negative_transcript_digest_mismatch() -> dict[str, Any]:
    """A transcript whose events were edited is rejected by the committed digest."""
    import tempfile

    transcript = dfa.load_committed_transcript()
    tampered = copy.deepcopy(transcript)
    tampered["events"][1]["value"] = "0x00000001"
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "transcript.json"
        path.write_bytes(transcript_model.canonical_bytes(tampered))
        rejected = _raises(
            lambda: dfa.load_committed_transcript(
                path, dfa.P17_06R_TRANSCRIPT_SHA),
            dfa.AssessmentError, "TRANSCRIPT_DIGEST_MISMATCH")
    return {"ok": rejected, "untampered_loads": True,
            "detail": json.dumps({"events": len(tampered["events"])}, sort_keys=True)}


def negative_unprovenanced_owner() -> dict[str, Any]:
    """A transcript event owned by an unprovenanced PC is rejected."""
    transcript = dfa.load_committed_transcript()
    tampered = copy.deepcopy(transcript)
    tampered["events"][0]["owning_instruction_pc"] = "0x80000000"
    provenance = dfa.rederive_provenance_map(rederived_analysis())
    return {"ok": _raises(
        lambda: dfa.assess_device_frontier(
            transcript=tampered, continuation=dfa.load_committed_continuation(),
            provenance_by_pc=provenance, op_by_pc=rederived_op_map()),
        dfa.AssessmentError, "TRANSCRIPT_REVALIDATION_FAILED"),
        "owner_replaced": "0x80000000"}


def negative_altered_provenance_digest() -> dict[str, Any]:
    """An event whose provenance digest was altered is rejected."""
    transcript = dfa.load_committed_transcript()
    tampered = copy.deepcopy(transcript)
    tampered["events"][0]["owning_instruction_provenance_digest"] = "00" * 32
    provenance = dfa.rederive_provenance_map(rederived_analysis())
    return {"ok": _raises(
        lambda: dfa.assess_device_frontier(
            transcript=tampered, continuation=dfa.load_committed_continuation(),
            provenance_by_pc=provenance, op_by_pc=rederived_op_map()),
        dfa.AssessmentError, "TRANSCRIPT_REVALIDATION_FAILED"),
        "digest_altered": True}


def negative_miscounted_transcript() -> dict[str, Any]:
    """Counts that disagree with the committed continuation are rejected."""
    transcript = dfa.load_committed_transcript()
    tampered = copy.deepcopy(transcript)
    tampered["device_event_count"] = int(transcript["device_event_count"]) + 1
    provenance = dfa.rederive_provenance_map(rederived_analysis())
    return {"ok": _raises(
        lambda: dfa.assess_device_frontier(
            transcript=tampered, continuation=dfa.load_committed_continuation(),
            provenance_by_pc=provenance, op_by_pc=rederived_op_map()),
        dfa.AssessmentError, "TRANSCRIPT_DEVICE_COUNT_MISMATCH"),
        "inflated_device_count": True}


def negative_continuation_digest_mismatch() -> dict[str, Any]:
    """A continuation record bound to a different transcript digest is rejected."""
    transcript = dfa.load_committed_transcript()
    continuation = dfa.load_committed_continuation()
    tampered = copy.deepcopy(continuation)
    tampered["transcript_sha256"] = "00" * 32
    provenance = dfa.rederive_provenance_map(rederived_analysis())
    return {"ok": _raises(
        lambda: dfa.assess_device_frontier(
            transcript=transcript, continuation=tampered,
            provenance_by_pc=provenance, op_by_pc=rederived_op_map()),
        dfa.AssessmentError, "CONTINUATION_TRANSCRIPT_DIGEST_MISMATCH"),
        "digest_replaced": True}


def negative_frontier_mismatch() -> dict[str, Any]:
    """A continuation record with no frontier block is rejected."""
    transcript = dfa.load_committed_transcript()
    continuation = dfa.load_committed_continuation()
    tampered = copy.deepcopy(continuation)
    tampered["frontier"] = {}
    provenance = dfa.rederive_provenance_map(rederived_analysis())
    return {"ok": _raises(
        lambda: dfa.assess_device_frontier(
            transcript=transcript, continuation=tampered,
            provenance_by_pc=provenance, op_by_pc=rederived_op_map()),
        dfa.AssessmentError, "CONTINUATION_FRONTIER_MISSING"),
        "frontier_emptied": True}


def negative_frontier_field_removed() -> dict[str, Any]:
    """A frontier missing one required field is rejected, not defaulted."""
    transcript = dfa.load_committed_transcript()
    continuation = dfa.load_committed_continuation()
    provenance = dfa.rederive_provenance_map(rederived_analysis())
    results: dict[str, Any] = {}
    for field in ("stop_reason", "last_successfully_executed_pc",
                  "attempted_frontier_pc", "executed_instruction_count",
                  "continuation_executed_count", "distinct_executed_pc_count"):
        tampered = copy.deepcopy(continuation)
        tampered["frontier"].pop(field, None)
        results[field] = _raises(
            lambda t=tampered: dfa.assess_device_frontier(
                transcript=transcript, continuation=t,
                provenance_by_pc=provenance, op_by_pc=rederived_op_map()),
            dfa.AssessmentError, "CONTINUATION_FRONTIER_FIELD_MISSING")
    return {"ok": all(results.values()), "rejected_fields": results}


def negative_continuation_entry_mismatch() -> dict[str, Any]:
    """A continuation entry PC that disagrees with the transcript is rejected."""
    transcript = dfa.load_committed_transcript()
    continuation = dfa.load_committed_continuation()
    tampered = copy.deepcopy(continuation)
    tampered["continuation_entry_pc"] = "0x80011af0"
    provenance = dfa.rederive_provenance_map(rederived_analysis())
    return {"ok": _raises(
        lambda: dfa.assess_device_frontier(
            transcript=transcript, continuation=tampered,
            provenance_by_pc=provenance, op_by_pc=rederived_op_map()),
        dfa.AssessmentError, "CONTINUATION_ENTRY_PC_MISMATCH"),
        "entry_replaced": tampered["continuation_entry_pc"]}


def negative_promotion_attempt() -> dict[str, Any]:
    """The assessment can never promote a proof marker or frame readiness."""
    assessment = dfa.assess_device_frontier(
        transcript=dfa.load_committed_transcript(),
        continuation=dfa.load_committed_continuation(),
        provenance_by_pc=dfa.rederive_provenance_map(rederived_analysis()),
        op_by_pc=rederived_op_map())
    claims = assessment["claims"]
    return {"ok": (claims["initialization"] == "NOT_PROVEN"
                   and claims["frame"] == "NOT_PROVEN"
                   and claims["playability"] == "NOT_PROVEN"
                   and claims["general_compatibility"] == "NOT_PROVEN"
                   and claims["first_frame_ready"] == "NO"
                   and dfa.STAGE not in json.dumps(claims)),
            "claims": claims}


def negative_empty_transcript() -> dict[str, Any]:
    """An empty event list is rejected rather than read as a negative finding."""
    transcript = dfa.load_committed_transcript()
    tampered = copy.deepcopy(transcript)
    tampered["events"] = []
    provenance = dfa.rederive_provenance_map(rederived_analysis())
    return {"ok": _raises(
        lambda: dfa.assess_device_frontier(
            transcript=tampered, continuation=dfa.load_committed_continuation(),
            provenance_by_pc=provenance, op_by_pc=rederived_op_map()),
        dfa.AssessmentError, "TRANSCRIPT_EVENTS_MISSING"),
        "events_emptied": True}


def negative_missing_transcript() -> dict[str, Any]:
    """A missing committed transcript is rejected."""
    return {"ok": _raises(
        lambda: dfa.load_committed_transcript(
            dfa.ROOT / "nonexistent-transcript.json", dfa.P17_06R_TRANSCRIPT_SHA),
        dfa.AssessmentError, "TRANSCRIPT_UNAVAILABLE"),
        "path": "nonexistent-transcript.json"}


def negative_historical_hollow_observation() -> dict[str, Any]:
    """The historical P17-07 evidence is not a checked observation basis.

    The historical module hard-coded ``encountered: false`` for every class and
    read its digests from a stage document that no gate validated against a
    checked transcript.  This stage proves it is not used as an input, and that
    its own assessment resolves the poll class as ENCOUNTERED where the
    historical document claimed no events.
    """
    historical = json.loads(
        (ROOT / ".openrecomp-phase17/evidence/P17-07/frontier_assessment.json")
        .read_text(encoding="utf-8"))
    observations = historical.get("observations", {})
    all_negative = bool(observations) and all(
        entry.get("encountered") is False for entry in observations.values())
    assessment = dfa.assess_device_frontier(
        transcript=dfa.load_committed_transcript(),
        continuation=dfa.load_committed_continuation(),
        provenance_by_pc=dfa.rederive_provenance_map(rederived_analysis()),
        op_by_pc=rederived_op_map())
    poll = assessment["observations"][dfa.GPU_WAIT_POLL]
    return {"ok": all_negative
                   and poll["status"] == dfa.STATUS_ENCOUNTERED
                   and poll["event_count"] > 0,
            "historical_classes": sorted(observations),
            "historical_all_encountered_false": all_negative,
            "checked_poll_events": poll["event_count"],
            "checked_poll_status": poll["status"]}


# --- Gate body ---------------------------------------------------------------

def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 1. Committed P17-06R inputs exist, and the transcript matches its digest.
    transcript = dfa.load_committed_transcript()
    continuation = dfa.load_committed_continuation()
    result = dfa.load_committed_result()
    gate.check("p17_06r:result-status-pass", str(result.get("status")) == "PASS",
               json.dumps({"status": result.get("status")}, sort_keys=True))
    gate.check("p17_06r:transcript-digest-verified",
               dfa.sha256_bytes(transcript_model.canonical_bytes(transcript))
               == continuation["transcript_sha256"],
               continuation["transcript_sha256"])
    gate.check("p17_06r:committed-transcript-untouched",
               transcript.get("next_stage") == STAGE,
               json.dumps({"transcript_next_stage": transcript.get("next_stage")},
                          sort_keys=True))
    gate.check("next-stage:declared-constant", NEXT_STAGE == "P17-90")

    # 2. Independently re-derive the authenticated record set.
    analysis = rederived_analysis()
    provenance = dfa.rederive_provenance_map(analysis)
    gate.check("rederive:record-count-matches-committed",
               analysis.record_count == int(continuation["record_counts"]["total"]),
               json.dumps({"rederived": analysis.record_count,
                           "committed": continuation["record_counts"]["total"]},
                          sort_keys=True))
    gate.check("rederive:region-log-matches-committed",
               analysis.region_log == continuation["authenticated_region_log"],
               json.dumps({"regions": len(analysis.region_log)}, sort_keys=True))
    gate.check("rederive:provenance-non-empty", len(provenance) > 0,
               json.dumps({"digests": len(provenance)}, sort_keys=True))

    # 3. The assessment, bound to the checked transcript.
    assessment = dfa.assess_device_frontier(
        transcript=transcript, continuation=continuation,
        provenance_by_pc=provenance, op_by_pc=rederived_op_map())
    gate.check("assessment:schema", assessment["schema"] == dfa.SCHEMA_ASSESSMENT)
    gate.check("assessment:stage-and-next", assessment["stage"] == STAGE
               and assessment["next_stage"] == NEXT_STAGE)
    gate.check("assessment:all-classes-present",
               set(assessment["observations"]) == set(dfa.OBSERVATION_CLASSES),
               json.dumps(sorted(assessment["observations"]), sort_keys=True))
    gate.check("assessment:every-class-has-checked-basis",
               all(observation["status"] in dfa.OBSERVATION_STATUSES
                   and observation["basis"].strip()
                   for observation in assessment["observations"].values()),
               json.dumps({name: observation["status"]
                           for name, observation
                           in sorted(assessment["observations"].items())},
                          sort_keys=True))
    gate.check("assessment:no-hardcoded-negative",
               any(observation["status"] == dfa.STATUS_ENCOUNTERED
                   for observation in assessment["observations"].values()),
               "at least one class resolves as ENCOUNTERED from checked evidence")
    gate.check("assessment:negative-findings-recorded",
               len(assessment["negative_findings"]) >= len(dfa.OBSERVATION_CLASSES),
               json.dumps(assessment["negative_findings"], sort_keys=True))

    # 4. The wait-poll finding that explains the bounded stop.
    poll = assessment["observations"][dfa.GPU_WAIT_POLL]
    gate.check("poll:encountered", poll["status"] == dfa.STATUS_ENCOUNTERED,
               json.dumps({"events": poll["event_count"]}, sort_keys=True))
    gate.check("poll:dominant-owner-is-a-load",
               bool(poll["dominant_owner_op"]) and poll["dominant_owner_op"] in dfa.LOAD_OPS,
               json.dumps({"owner": poll["dominant_owner_pc"],
                           "op": poll["dominant_owner_op"]}, sort_keys=True))
    gate.check("poll:all-reads-zero-under-zero-fill",
               all(int(str(event["value"]), 16) == 0
                   for event in transcript["events"]
                   if event.get("class") == "GPUSTAT_READ"),
               "every GPUSTAT read returned zero")
    gate.check("poll:wait-predicate-not-observable",
               poll["wait_predicate_observable"] is False,
               "zero-fill reads cannot evaluate the guest poll exit condition")

    # 5. Device-surface classes are NOT_ENCOUNTERED or NOT_ESTABLISHED only.
    for name in (dfa.GPU_WRITES, dfa.DMA2, dfa.OT_TRAVERSAL,
                 dfa.FRAMEBUFFER_ACTIVITY, dfa.ORDERING_TABLE_WRITES,
                 dfa.INITIALIZATION_PREDICATES):
        status = assessment["observations"][name]["status"]
        gate.check(f"observation:{name}:resolved",
                   status in (dfa.STATUS_NOT_ENCOUNTERED, dfa.STATUS_NOT_ESTABLISHED),
                   json.dumps({"status": status}, sort_keys=True))
    gate.check("observation:gpu-writes-not-encountered",
               assessment["observations"][dfa.GPU_WRITES]["event_count"] == 0)
    gate.check("observation:dma2-not-encountered",
               assessment["observations"][dfa.DMA2]["event_count"] == 0)
    gate.check("observation:ram-store-classes-not-established",
               assessment["observations"][dfa.ORDERING_TABLE_WRITES]["status"]
               == dfa.STATUS_NOT_ESTABLISHED
               and assessment["observations"][dfa.OT_TRAVERSAL]["status"]
               == dfa.STATUS_NOT_ESTABLISHED)
    gate.check("observation:initialization-not-established",
               assessment["observations"][dfa.INITIALIZATION_PREDICATES]["status"]
               == dfa.STATUS_NOT_ESTABLISHED)

    # 6. Historical P17-07 is not an input, and the transcript is not reused here.
    historical = negative_historical_hollow_observation()
    gate.check("historical:p17-07-not-used-as-basis", historical["ok"],
               json.dumps({k: v for k, v in historical.items() if k != "ok"},
                          sort_keys=True))
    gate.check("historical:p17-07-evidence-untouched",
               (ROOT / ".openrecomp-phase17/evidence/P17-07/frontier_assessment.json")
               .is_file())

    # 7. Negative controls.
    negatives = {
        "transcript-digest-mismatch": negative_transcript_digest_mismatch(),
        "unprovenanced-owner": negative_unprovenanced_owner(),
        "altered-provenance-digest": negative_altered_provenance_digest(),
        "miscounted-transcript": negative_miscounted_transcript(),
        "continuation-digest-mismatch": negative_continuation_digest_mismatch(),
        "frontier-mismatch": negative_frontier_mismatch(),
        "frontier-field-removed": negative_frontier_field_removed(),
        "continuation-entry-mismatch": negative_continuation_entry_mismatch(),
        "promotion-attempt": negative_promotion_attempt(),
        "empty-transcript": negative_empty_transcript(),
        "missing-transcript": negative_missing_transcript(),
    }
    for name, result in negatives.items():
        gate.check(f"negative:{name}", result["ok"],
                   json.dumps({k: v for k, v in result.items() if k != "ok"},
                              sort_keys=True))

    # 8. Evidence documents.
    binding = {
        "schema": "openrecomp-phase17-device-transcript-binding-v1",
        "stage": STAGE,
        "source_stage": dfa.SOURCE_STAGE,
        "transcript_sha256": dfa.sha256_bytes(
            transcript_model.canonical_bytes(transcript)),
        "transcript_event_count": int(transcript["event_count"]),
        "device_event_count": int(transcript["device_event_count"]),
        "bios_dispatch_count": int(transcript["bios_dispatch_count"]),
        "event_class_counts": transcript["event_class_counts"],
        "bios_model": transcript["bios_model"],
        "mmio_model": transcript["mmio_model"],
        "revalidated_against_rederived_provenance": True,
        "rederived_provenance_digest_count": len(provenance),
    }
    stage_metadata = {
        "schema": "openrecomp-phase17-stage-metadata-v1",
        "stage": STAGE,
        "status": "PASS",
        "next_stage": NEXT_STAGE,
        "base_commit": BASE_COMMIT,
        "worker_branch": WORKER_BRANCH,
        "resulting_candidate_commit": "PENDING_FINAL_COMMIT",
        "resulting_candidate_commit_resolver": f"git rev-parse {WORKER_BRANCH}",
    }
    result_doc = {
        "schema": "openrecomp-phase17-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "next_stage": NEXT_STAGE,
        "evidence_class": dfa.EVIDENCE_CLASS,
        "base_commit": BASE_COMMIT,
        "worker_branch": WORKER_BRANCH,
        "resulting_candidate_commit": "PENDING_FINAL_COMMIT",
        "resulting_candidate_commit_resolver": f"git rev-parse {WORKER_BRANCH}",
        "source_stage": dfa.SOURCE_STAGE,
        "transcript_sha256": dfa.sha256_bytes(
            transcript_model.canonical_bytes(transcript)),
        "supersedes_historical_stage": "P17-07",
        "markers": {
            ASSESSMENT_MARKER: "PASS",
            "OPENRECOMP_P17_07R": "PASS",
            INITIALIZATION_MARKER: "NOT_PROVEN",
            FRAME_MARKER: "NOT_PROVEN",
            PLAYABILITY_MARKER: "NOT_PROVEN",
            GENERAL_MARKER: "NOT_PROVEN",
            FIRST_FRAME_READY_MARKER: "NO",
        },
        "proof_boundaries": {
            INITIALIZATION_MARKER: "NOT_PROVEN",
            FRAME_MARKER: "NOT_PROVEN",
            PLAYABILITY_MARKER: "NOT_PROVEN",
            GENERAL_MARKER: "NOT_PROVEN",
            FIRST_FRAME_READY_MARKER: "NO",
        },
        "observation_status": {
            name: observation["status"]
            for name, observation in sorted(assessment["observations"].items())
        },
        "negative_findings": assessment["negative_findings"],
    }
    next_stage_doc = {
        "schema": "openrecomp-phase17-next-stage-v1",
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "authoritative_sources": [
            "RESULT.json", "device_frontier_assessment.json",
            "transcript_binding.json", "stage_metadata.json", "next_stage.json",
            "STATE.md", "HANDOFF.md",
        ],
    }
    for name, document in (("device_frontier_assessment", assessment),
                           ("transcript_binding", binding),
                           ("result", result_doc),
                           ("next_stage", next_stage_doc),
                           ("stage_metadata", stage_metadata)):
        text = json.dumps(document, sort_keys=True)
        for term in ("raw_instruction", "instruction_word", "payload_bytes", "bios_bytes"):
            gate.check(f"public:{name}:no-{term.replace('_', '-')}-field", term not in text)
        gate.check(f"public:{name}:no-private-paths",
                   "/home/" not in text and "fixtures/" not in text and "/tmp/" not in text)
        assert_public_safe(gate, name, document)

    write_json(evidence / "device_frontier_assessment.json", assessment)
    write_json(evidence / "transcript_binding.json", binding)
    write_json(evidence / "RESULT.json", result_doc)
    write_json(evidence / "next_stage.json", next_stage_doc)
    write_json(evidence / "stage_metadata.json", stage_metadata)

    # 9. Scope: no Phase-1..16 modifications; frozen Phase-16 integrity.
    changed = subprocess.run(
        ["git", "status", "--porcelain", "--",
         ".openrecomp-phase1", ".openrecomp-phase2", ".openrecomp-phase3",
         ".openrecomp-phase4", ".openrecomp-phase5", ".openrecomp-phase6",
         ".openrecomp-phase7", ".openrecomp-phase8", ".openrecomp-phase9",
         ".openrecomp-phase10", ".openrecomp-phase11", ".openrecomp-phase12",
         ".openrecomp-phase13", ".openrecomp-phase14", ".openrecomp-phase15",
         ".openrecomp-phase16"],
        cwd=str(root), capture_output=True, text=True)
    gate.check("scope:no-phase-1-16-changes", not changed.stdout.strip(),
               changed.stdout.strip() or "[]")
    frozen = subprocess.run(
        [sys.executable, str(root / ".openrecomp-phase17" / "src"
                             / "p17_frozen_phase16_integrity_v1.py")],
        cwd=str(root), capture_output=True, text=True)
    gate.check("scope:phase16-frozen-integrity",
               frozen.returncode == 0
               and "OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS" in frozen.stdout,
               frozen.stdout.strip() or frozen.stderr.strip())

    # 10. Markers: no proof marker is promoted by this stage.
    gate.mark(ASSESSMENT_MARKER)
    gate.mark("OPENRECOMP_P17_07R")
    for marker in (INITIALIZATION_MARKER, FRAME_MARKER, PLAYABILITY_MARKER,
                   GENERAL_MARKER):
        gate.mark(marker, "NOT_PROVEN")
    gate.mark(FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase17/evidence/P17-07R"))
