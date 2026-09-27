#!/usr/bin/env python3
"""Phase-17 P17-07R checked device/frame frontier assessment.

The historical P17-07 stage inferred the absence of device events from a
digest and hard-coded ``encountered: false`` for every observation class, so
its ``PASS`` marker did not establish any observation.  This module replaces it
with a fail-closed assessment that is bound to the committed, checked P17-06R
device transcript and to an independently re-derived provenance map.

Every observation is resolved to exactly one of three statuses:

``ENCOUNTERED``
    The checked transcript contains one or more events of the class, with
    owning instruction PCs and provenance digests.
``NOT_ENCOUNTERED``
    The checked transcript is complete for the instrumented device surface and
    contains zero events of the class.  This is a *negative* finding with a
    checked basis, not an absence of evidence.
``NOT_ESTABLISHED``
    The transcript does not instrument the mechanism at all, so no conclusion
    is drawn in either direction.  This is used for phenomena that depend on
    guest RAM stores, which the device/BIOS transcript does not record.

The module never promotes a proof marker.  Initialization, frame, playability
and general PS1 compatibility stay ``NOT_PROVEN`` and ``FIRST_FRAME_READY``
stays ``NO`` regardless of the assessment outcome.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

import p17_device_transcript_v1 as transcript_model

SCHEMA_ASSESSMENT = "openrecomp-phase17-checked-device-frontier-assessment-v1"

STAGE = "P17-07R"
NEXT_STAGE = "P17-90"
SOURCE_STAGE = "P17-06R"

ROOT = pathlib.Path(__file__).resolve().parents[2]
P17_06R_EVIDENCE = ROOT / ".openrecomp-phase17/evidence/P17-06R"
P17_06R_TRANSCRIPT = P17_06R_EVIDENCE / "transcript.json"
P17_06R_TRANSCRIPT_SHA = P17_06R_EVIDENCE / "transcript.sha256"
P17_06R_CONTINUATION = P17_06R_EVIDENCE / "continuation.json"
P17_06R_RESULT = P17_06R_EVIDENCE / "RESULT.json"

EVIDENCE_CLASS = "PRIVATE_FIXTURE_BOUNDED"

#: Statuses an observation may resolve to.  Anything else is a fail-closed bug.
STATUS_ENCOUNTERED = "ENCOUNTERED"
STATUS_NOT_ENCOUNTERED = "NOT_ENCOUNTERED"
STATUS_NOT_ESTABLISHED = "NOT_ESTABLISHED"
OBSERVATION_STATUSES = frozenset({
    STATUS_ENCOUNTERED, STATUS_NOT_ENCOUNTERED, STATUS_NOT_ESTABLISHED,
})

#: The six observation classes carried over from the historical P17-07
#: contract, plus the GPU wait-loop poll that the checked transcript actually
#: does establish.
GPU_WRITES = "gpu_writes"
DMA2 = "dma2"
ORDERING_TABLE_WRITES = "ordering_table_writes"
OT_TRAVERSAL = "ot_traversal"
FRAMEBUFFER_ACTIVITY = "framebuffer_activity"
INITIALIZATION_PREDICATES = "initialization_predicates"
GPU_WAIT_POLL = "gpu_wait_poll"

OBSERVATION_CLASSES = (
    GPU_WRITES,
    DMA2,
    ORDERING_TABLE_WRITES,
    OT_TRAVERSAL,
    FRAMEBUFFER_ACTIVITY,
    INITIALIZATION_PREDICATES,
    GPU_WAIT_POLL,
)

#: Physical register windows that carry the framebuffer (GP0 command) path.
GP0_PHYS = 0x1F801810
GP1_PHYS = 0x1F801814

#: DMA channel 2 control register.  PS1 DMA channel N starts at
#: 0x1F801080 + N * 0x10 and its CHCR is the low word at offset 0x8.
DMA2_CHCR_PHYS = 0x1F8010A8

#: Guest load ops that can produce a device read event.
LOAD_OPS = frozenset({"lw", "lhu", "lbu", "lwl", "lwr"})
STORE_OPS = frozenset({"sw", "sh", "sb", "swl", "swr"})

#: Event kinds exactly as they appear in the committed transcript document.
#: ``p17_device_transcript_v1`` serializes ``kind`` as a string; its ``KIND_*``
#: integer constants are runtime-internal and never reach the wire format, so an
#: assessment must compare against these wire values.
WIRE_KIND_BIOS_DISPATCH = "BIOS_DISPATCH"
WIRE_KIND_MMIO = "MMIO"


#: Every event kind the checked transcript is able to record.  Used to justify
#: the ``NOT_ESTABLISHED`` verdicts: anything that can only be observed through
#: a guest RAM store is outside this instrumented surface.
RECORDABLE_KINDS = frozenset({WIRE_KIND_BIOS_DISPATCH, WIRE_KIND_MMIO})
class AssessmentError(ValueError):
    """Fail-closed assessment error."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def canonical_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: pathlib.Path, code: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise AssessmentError(code, f"{path.name}: {type(err).__name__}") from err
    if not isinstance(document, dict):
        raise AssessmentError(code, f"{path.name}: not an object")
    return document


def load_committed_transcript(
    transcript_path: pathlib.Path = P17_06R_TRANSCRIPT,
    sha_path: pathlib.Path = P17_06R_TRANSCRIPT_SHA,
) -> dict[str, Any]:
    """Load the committed P17-06R transcript and verify its committed digest.

    The transcript is re-hashed here rather than trusted, so an assessment can
    never be built from an edited event list that still carries the old digest.
    """
    if not transcript_path.is_file():
        raise AssessmentError("TRANSCRIPT_UNAVAILABLE", transcript_path.name)
    if not sha_path.is_file():
        raise AssessmentError("TRANSCRIPT_DIGEST_UNAVAILABLE", sha_path.name)
    document = _load_json(transcript_path, "TRANSCRIPT_UNREADABLE")
    recorded = sha_path.read_text(encoding="utf-8").split()
    if not recorded or recorded[0] != transcript_model.sha256_bytes(
            transcript_model.canonical_bytes(document)):
        raise AssessmentError("TRANSCRIPT_DIGEST_MISMATCH", transcript_path.name)
    return document


def load_committed_continuation(
    continuation_path: pathlib.Path = P17_06R_CONTINUATION,
) -> dict[str, Any]:
    return _load_json(continuation_path, "CONTINUATION_EVIDENCE_UNAVAILABLE")


def load_committed_result(
    result_path: pathlib.Path = P17_06R_RESULT,
) -> dict[str, Any]:
    return _load_json(result_path, "RESULT_EVIDENCE_UNAVAILABLE")


def rederive_provenance_map(analysis: Any) -> dict[int, str]:
    """Independently re-derive the authenticated provenance digests.

    ``analysis`` is a freshly built P17-06R side-effects analysis, built from
    the read-only private source bytes by the frozen decoder.  The digests are
    recomputed here so a transcript event owner is checked against a
    provenance map that did not come from the transcript's own producer.
    """
    import p17_side_effects_exec_v1 as side

    if analysis is None:
        raise AssessmentError("PROVENANCE_SOURCE_MISSING")
    mapping = side.provenance_digest_map(analysis)
    if not mapping:
        raise AssessmentError("PROVENANCE_MAP_EMPTY")
    return mapping


def _owning_pcs(events: list[dict[str, Any]]) -> list[str]:
    return sorted({str(event["owning_instruction_pc"]) for event in events})


def _mmio_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events
            if event.get("kind") == WIRE_KIND_MMIO]


def _bios_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events
            if event.get("kind") == WIRE_KIND_BIOS_DISPATCH]


def _events_by_class(events: list[dict[str, Any]], class_name: str
                     ) -> list[dict[str, Any]]:
    return [event for event in events if event.get("class") == class_name]


def _observation(status: str, *, basis: str, event_count: int = 0,
                 owning_instruction_pcs: list[str] | None = None,
                 addresses: list[str] | None = None,
                 extra: dict[str, Any] | None = None) -> dict[str, Any]:
    if status not in OBSERVATION_STATUSES:
        raise AssessmentError("OBSERVATION_STATUS_UNKNOWN", status)
    document: dict[str, Any] = {
        "status": status,
        "basis": basis,
        "event_count": int(event_count),
        "owning_instruction_pcs": owning_instruction_pcs or [],
    }
    if addresses is not None:
        document["addresses"] = addresses
    if extra:
        document.update(extra)
    return document


def _address(events: list[dict[str, Any]]) -> str:
    return hex32(int(str(events[0]["address"]), 16))


def _all_kinds_recordable(events: list[dict[str, Any]]) -> bool:
    return all(str(event.get("kind")) in RECORDABLE_KINDS for event in events)


def assess_device_frontier(*, transcript: dict[str, Any],
                           continuation: dict[str, Any],
                           provenance_by_pc: dict[int, str],
                           op_by_pc: dict[str, str] | None = None) -> dict[str, Any]:
    """Assess the device/frame frontier from the checked transcript.

    The transcript is re-validated against ``provenance_by_pc`` before any
    observation is made, so an assessment cannot be built on an unprovenanced
    or misclassified event.
    """
    if op_by_pc is None:
        op_by_pc = {}

    events = transcript.get("events")
    if not isinstance(events, list) or not events:
        raise AssessmentError("TRANSCRIPT_EVENTS_MISSING")

    # Fail closed on the transcript itself before interpreting it.
    try:
        transcript_model.validate_transcript(transcript, provenance_by_pc)
    except transcript_model.TranscriptError as err:
        raise AssessmentError("TRANSCRIPT_REVALIDATION_FAILED",
                              f"{err.code}: {err.detail}") from err

    if str(transcript.get("stage")) != SOURCE_STAGE:
        raise AssessmentError("TRANSCRIPT_STAGE_MISMATCH", str(transcript.get("stage")))

    device_events = _mmio_events(events)
    bios_events = _bios_events(events)
    if not device_events and not bios_events:
        raise AssessmentError("TRANSCRIPT_NO_DEVICE_EVENTS")

    # The committed continuation evidence is the authority for the frontier and
    # for the counts; a transcript that disagrees is rejected.
    if int(transcript["device_event_count"]) != len(device_events):
        raise AssessmentError("TRANSCRIPT_DEVICE_COUNT_MISMATCH")
    if int(transcript["bios_dispatch_count"]) != len(bios_events):
        raise AssessmentError("TRANSCRIPT_BIOS_COUNT_MISMATCH")
    if int(transcript["event_count"]) != len(events):
        raise AssessmentError("TRANSCRIPT_EVENT_COUNT_MISMATCH")
    for key in ("device_event_count", "bios_dispatch_count"):
        if key in continuation and int(continuation[key]) != int(transcript[key]):
            raise AssessmentError("CONTINUATION_TRANSCRIPT_COUNT_MISMATCH", key)
    if continuation.get("transcript_sha256") != transcript_model.sha256_bytes(
            transcript_model.canonical_bytes(transcript)):
        raise AssessmentError("CONTINUATION_TRANSCRIPT_DIGEST_MISMATCH")

    kinds_recordable = _all_kinds_recordable(events)

    # --- GPU wait poll: the one device phenomenon the transcript does establish.
    gpu_reads = _events_by_class(device_events, "GPUSTAT_READ")
    poll_owner: str | None = None
    poll_count = 0
    poll_op: str | None = None
    if gpu_reads:
        by_owner: dict[str, int] = {}
        for event in gpu_reads:
            owner = str(event["owning_instruction_pc"])
            by_owner[owner] = by_owner.get(owner, 0) + 1
        poll_owner, poll_count = max(by_owner.items(), key=lambda item: (item[1], item[0]))
        poll_op = op_by_pc.get(poll_owner)
        if poll_op is not None and poll_op not in LOAD_OPS:
            raise AssessmentError("POLL_OWNER_NOT_A_LOAD", f"{poll_owner}:{poll_op}")
        for event in gpu_reads:
            if int(str(event["value"]), 16) != 0:
                raise AssessmentError("POLL_READ_NONZERO_UNDER_ZERO_FILL",
                                      str(event["owning_instruction_pc"]))
        share = len(gpu_reads) / len(device_events)
        if share < 0.5:
            raise AssessmentError("POLL_NOT_DOMINANT", f"{share:.4f}")
    poll_extra: dict[str, Any] = {
        "read_address": _address(gpu_reads) if gpu_reads else None,
        "read_model": transcript_model.MMIO_READ_MODEL,
        "all_reads_returned_zero": bool(gpu_reads),
    }
    wait_poll = _observation(
        STATUS_ENCOUNTERED if gpu_reads else STATUS_NOT_ENCOUNTERED,
        basis=("checked transcript: GPUSTAT_READ events, each zero-filled under "
               f"{transcript_model.MMIO_READ_MODEL}"),
        event_count=len(gpu_reads),
        owning_instruction_pcs=_owning_pcs(gpu_reads),
        addresses=sorted({_address([event]) for event in gpu_reads}),
        extra={
            "dominant_owner_pc": poll_owner,
            "dominant_owner_event_count": poll_count,
            "dominant_owner_op": poll_op,
            "wait_predicate_observable": False,
            "wait_predicate_basis": (
                "every GPUSTAT read returned zero under the zero-fill model, so "
                "the guest's poll exit condition cannot be evaluated from this "
                "transcript"),
            **poll_extra,
        },
    )

    observations: dict[str, Any] = {}

    # --- GP0 / framebuffer command path.
    gp0_writes = [event for event in device_events
                  if event.get("class") == "GP0_WRITE"]
    observations[GPU_WRITES] = _observation(
        STATUS_ENCOUNTERED if gp0_writes else STATUS_NOT_ENCOUNTERED,
        basis=("checked transcript: the instrumented device surface records every "
               f"MMIO access; zero GP0 writes to {hex32(GP0_PHYS)} were recorded"),
        event_count=len(gp0_writes),
        owning_instruction_pcs=_owning_pcs(gp0_writes),
        addresses=sorted({_address([event]) for event in gp0_writes}) if gp0_writes else [],
    )

    framebuffer_events = [event for event in device_events
                          if event.get("class") in ("GP0_WRITE", "GP1_WRITE")]
    observations[FRAMEBUFFER_ACTIVITY] = _observation(
        STATUS_ENCOUNTERED if framebuffer_events else STATUS_NOT_ENCOUNTERED,
        basis=("checked transcript: no GP0/GP1 command traffic was recorded, so no "
               "framebuffer activity is established"),
        event_count=len(framebuffer_events),
        owning_instruction_pcs=_owning_pcs(framebuffer_events),
        addresses=(sorted({_address([event]) for event in framebuffer_events})
                   if framebuffer_events else []),
    )

    # --- DMA channel 2 (the ordering-table channel).
    dma_events = _events_by_class(device_events, "DMA_ACCESS")
    dma2_events = [event for event in dma_events
                   if int(str(event["address"]), 16) == DMA2_CHCR_PHYS]
    dma2_status = STATUS_NOT_ENCOUNTERED
    dma2_basis = ("checked transcript: no DMA channel 2 control write was recorded; "
                  f"the instrumented surface covers 0x1F801080-0x1F8010FF "
                  f"including {hex32(DMA2_CHCR_PHYS)}")
    if dma2_events:
        dma2_status = STATUS_ENCOUNTERED
        dma2_basis = "checked transcript: DMA channel 2 control access recorded"
    elif dma_events:
        dma2_events = []
        dma2_basis = ("checked transcript: DMA accesses were recorded on other "
                      f"channels; none on channel 2 ({hex32(DMA2_CHCR_PHYS)})")
    observations[DMA2] = _observation(
        dma2_status,
        basis=dma2_basis,
        event_count=len(dma2_events),
        owning_instruction_pcs=_owning_pcs(dma2_events),
        addresses=(sorted({_address([event]) for event in dma2_events})
                   if dma2_events else []),
        extra={"total_dma_events": len(dma_events)},
    )

    # --- Ordering-table writes and traversal depend on guest RAM stores, which
    # the device/BIOS transcript does not record.  No conclusion either way.
    ram_store_basis = (
        "the checked transcript records only BIOS dispatches and device MMIO "
        f"accesses (kinds {sorted(RECORDABLE_KINDS)}); it does not record guest RAM "
        "stores, so ordering-table writes cannot be observed either way")
    if not kinds_recordable:
        ram_store_basis += " (and an unrecordable event kind was present)"
    observations[ORDERING_TABLE_WRITES] = _observation(
        STATUS_NOT_ESTABLISHED,
        basis=ram_store_basis,
        event_count=0,
        extra={"recorded_event_kinds": sorted({str(e["kind"]) for e in events})},
    )
    observations[OT_TRAVERSAL] = _observation(
        STATUS_NOT_ESTABLISHED,
        basis=(ram_store_basis + "; traversal would additionally require the BIOS "
               f"internals, which are {transcript_model.BIOS_INTERNALS}"),
        event_count=0,
    )

    # --- Initialization predicates need both a modelled BIOS and a live device.
    init_extra = {
        "bios_dispatch_count": len(bios_events),
        "bios_internals": transcript_model.BIOS_INTERNALS,
        "bios_vectors_observed": sorted({str(e["vector"]) for e in bios_events}),
    }
    if bios_events and gpu_reads:
        init_status = STATUS_NOT_ESTABLISHED
        init_basis = (
            "checked transcript: a BIOS envelope dispatch was recorded, but BIOS "
            f"internals are {transcript_model.BIOS_INTERNALS} and every GPUSTAT read "
            "returned zero, so no initialization predicate is established")
    elif bios_events:
        init_status = STATUS_NOT_ESTABLISHED
        init_basis = (
            "checked transcript: a BIOS envelope dispatch was recorded, but BIOS "
            f"internals are {transcript_model.BIOS_INTERNALS}, so no initialization "
            "predicate is established")
    else:
        init_status = STATUS_NOT_ESTABLISHED
        init_basis = ("checked transcript: no BIOS dispatch and no device read was "
                      "recorded, so no initialization predicate is established")
    observations[INITIALIZATION_PREDICATES] = _observation(
        init_status, basis=init_basis, event_count=len(bios_events),
        owning_instruction_pcs=_owning_pcs(bios_events), extra=init_extra,
    )

    observations[GPU_WAIT_POLL] = wait_poll

    if set(observations) != set(OBSERVATION_CLASSES):
        raise AssessmentError("OBSERVATION_SET_INCOMPLETE")

    frontier = continuation.get("frontier")
    if not isinstance(frontier, dict) or not frontier:
        raise AssessmentError("CONTINUATION_FRONTIER_MISSING")
    required_frontier = (
        "stop_reason", "last_successfully_executed_pc", "attempted_frontier_pc",
        "executed_instruction_count", "continuation_executed_count",
        "distinct_executed_pc_count",
    )
    missing_frontier = [key for key in required_frontier
                        if frontier.get(key) in (None, "")]
    if missing_frontier:
        raise AssessmentError("CONTINUATION_FRONTIER_FIELD_MISSING",
                              ",".join(missing_frontier))
    if str(continuation.get("continuation_entry_pc")) != str(
            transcript.get("continuation_entry_pc")):
        raise AssessmentError("CONTINUATION_ENTRY_PC_MISMATCH")
    return {
        "schema": SCHEMA_ASSESSMENT,
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "evidence_class": EVIDENCE_CLASS,
        "source": {
            "source_stage": SOURCE_STAGE,
            "transcript_sha256": transcript_model.sha256_bytes(
                transcript_model.canonical_bytes(transcript)),
            "transcript_event_count": len(events),
            "continuation_entry_pc": continuation.get("continuation_entry_pc"),
            "record_counts": continuation.get("record_counts"),
            "provenance_source": "independently re-derived from the frozen decoder",
            "provenance_digest_count": len(provenance_by_pc),
        },
        "frontier": {
            "stop_reason": frontier.get("stop_reason"),
            "last_successfully_executed_pc": frontier.get(
                "last_successfully_executed_pc"),
            "attempted_frontier_pc": frontier.get("attempted_frontier_pc"),
            "executed_instruction_count": frontier.get("executed_instruction_count"),
            "continuation_executed_count": frontier.get("continuation_executed_count"),
            "distinct_executed_pc_count": frontier.get("distinct_executed_pc_count"),
        },
        "transcript_binding": {
            "device_event_count": len(device_events),
            "bios_dispatch_count": len(bios_events),
            "event_class_counts": transcript.get("event_class_counts"),
            "revalidated_against_rederived_provenance": True,
            "bios_model": transcript.get("bios_model"),
            "mmio_model": transcript.get("mmio_model"),
        },
        "observations": observations,
        "negative_findings": _negative_findings(observations),
        "claims": {
            "initialization": "NOT_PROVEN",
            "frame": "NOT_PROVEN",
            "playability": "NOT_PROVEN",
            "general_compatibility": "NOT_PROVEN",
            "first_frame_ready": "NO",
        },
    }


def _negative_findings(observations: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    for name in sorted(observations):
        observation = observations[name]
        if observation["status"] == STATUS_NOT_ENCOUNTERED:
            findings.append(f"{name}: no event of this class in the checked transcript")
        elif observation["status"] == STATUS_NOT_ESTABLISHED:
            findings.append(f"{name}: mechanism not instrumented; no conclusion drawn")
    poll = observations.get(GPU_WAIT_POLL, {})
    if poll.get("status") == STATUS_ENCOUNTERED:
        findings.append(
            "the dominant device traffic is a GPUSTAT wait poll returning zero; the "
            "guest cannot make progress under the declared device model")
    return findings


def assessment_digest(assessment: dict[str, Any]) -> str:
    document = dict(assessment)
    document.pop("assessment_digest", None)
    return sha256_bytes(canonical_bytes(document))
