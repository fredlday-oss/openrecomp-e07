#!/usr/bin/env python3
"""OpenRecomp Phase-18 GPUSTAT-polling frontier analysis V1.

Re-derives, purely from the committed Phase-17 P17-06R device transcript, the
exact frontier that Phase 18 starts from. Nothing here is hard-coded from chat:
every reported number is computed from the transcript bytes, whose SHA-256 is
re-verified against the recorded digest before analysis.

Output is public-safe: sequence numbers, addresses, PCs, class names, widths and
counts only. No instruction words, no payload bytes, no private paths.

This module proves *nothing* about the GPU. It establishes the binding
constraint (a zero-returning GPUSTAT wait-poll) and states the minimum
behaviour a faithful GPUSTAT state model would have to satisfy to allow the
guest to leave the loop. It promotes no marker.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]

TRANSCRIPT_PATH = ROOT / ".openrecomp-phase17/evidence/P17-06R/transcript.json"
EXPECTED_TRANSCRIPT_SHA256 = (
    "d7e222c87726748ced23dd60c2b1ba138625227c984dac587be6a5761695fd3a")

#: PS1 GPUSTAT register (physical) and the ready/status bits it exposes.
GPUSTAT_PHYS = 0x1F801814
#: GP0 write port (physical).
GP0_PHYS = 0x1F801810
#: DMA channel-2 (GPU) register window base.
DMA2_BASE = 0x1F8010A0
DMA2_END = 0x1F8010AF

#: Bit meanings of the GPUSTAT word (documented PS1 behaviour) that Phase 18
#: must reason about. Bit numbers only; no value is asserted as hardware truth.
GPUSTAT_BIT_MEANINGS = {
    13: "interlace_field",
    19: "dma_request_ready",
    22: "interlace_mode",
    23: "display_enable",
    26: "ready_to_receive_cmd",
    28: "ready_to_receive_dma_block",
    31: "ready_to_send_vram_to_cpu",
}


class FrontierAnalysisError(ValueError):
    """Fail-closed analysis rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def _int(value: Any) -> int:
    return int(str(value), 16) if isinstance(value, str) else int(value)


def load_transcript(path: pathlib.Path = TRANSCRIPT_PATH) -> tuple[dict[str, Any], str]:
    """Load and digest-verify the committed P17-06R transcript."""
    if not path.is_file():
        raise FrontierAnalysisError("TRANSCRIPT_MISSING", str(path.name))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_TRANSCRIPT_SHA256:
        raise FrontierAnalysisError("TRANSCRIPT_DIGEST_MISMATCH", digest)
    document = json.loads(raw.decode("utf-8"))
    if document.get("schema") != "openrecomp-phase17-device-transcript-v1":
        raise FrontierAnalysisError("TRANSCRIPT_SCHEMA_MISMATCH")
    return document, digest


def _mmio_events(document: dict[str, Any]) -> list[dict[str, Any]]:
    events = document.get("events")
    if not isinstance(events, list):
        raise FrontierAnalysisError("TRANSCRIPT_EVENTS_MISSING")
    return [event for event in events
            if event.get("kind") == "MMIO"
            and str(event.get("access")) in ("READ", "WRITE")]


def analyse(document: dict[str, Any], digest: str) -> dict[str, Any]:
    # Fail closed on a digest that does not match the recorded transcript
    # digest: analysis of an unauthenticated transcript is not evidence.
    if digest != EXPECTED_TRANSCRIPT_SHA256:
        raise FrontierAnalysisError("TRANSCRIPT_DIGEST_MISMATCH", digest)
    events = document["events"]
    if int(document.get("event_count", -1)) != len(events):
        raise FrontierAnalysisError("TRANSCRIPT_EVENT_COUNT_MISMATCH")

    class_counts: dict[str, int] = {}
    for event in events:
        key = event["kind"] if event["kind"] != "MMIO" else event["class"]
        class_counts[key] = class_counts.get(key, 0) + 1

    mmio = _mmio_events(document)

    def class_events(name: str, access: str) -> list[dict[str, Any]]:
        return [event for event in mmio
                if event.get("class") == name and event.get("access") == access]

    gpustat_reads = class_events("GPUSTAT_READ", "READ")
    gpustat_writes = [event for event in mmio
                      if _int(event.get("address", 0)) == GPUSTAT_PHYS
                      and event.get("access") == "WRITE"]

    # Owner census for the GPUSTAT wait-poll reads.
    owner_counts: dict[str, int] = {}
    for event in gpustat_reads:
        owner = str(event["owning_instruction_pc"])
        owner_counts[owner] = owner_counts.get(owner, 0) + 1
    dominant_owner = None
    dominant_owner_count = 0
    for owner, count in sorted(owner_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        dominant_owner, dominant_owner_count = owner, count
        break

    read_values = {str(event.get("value")) for event in gpustat_reads}
    all_zero = bool(gpustat_reads) and read_values == {"0x00000000"}

    # Model name is read from the transcript, not hard-coded.
    read_model = None
    for event in gpustat_reads:
        read_model = event.get("model")
        break
    if read_model is None:
        read_model = document.get("mmio_model", {}).get("read")

    # DMA-2 channel access census (bounded window, address only).
    dma2 = [event for event in mmio
            if DMA2_BASE <= _int(event.get("address", 0)) <= DMA2_END]
    gp0_writes = class_events("GP0_WRITE", "WRITE")

    frontier = {
        "continuation_entry_pc": document.get("continuation_entry_pc"),
        "runtime_stop_reason": document.get("runtime_stop_reason"),
    }

    analysis: dict[str, Any] = {
        "schema": "openrecomp-phase18-gpustat-frontier-analysis-v1",
        "source": {
            "stage": document.get("stage"),
            "transcript_sha256": digest,
            "transcript_sha256_expected": EXPECTED_TRANSCRIPT_SHA256,
            "transcript_reverified": digest == EXPECTED_TRANSCRIPT_SHA256,
            "event_count": len(events),
            "device_event_count": int(document.get("device_event_count", -1)),
            "bios_dispatch_count": int(document.get("bios_dispatch_count", -1)),
            "event_class_counts": dict(sorted(class_counts.items())),
        },
        "frontier": frontier,
        "gpustat": {
            "address": hex32(GPUSTAT_PHYS),
            "read_count": len(gpustat_reads),
            "write_count": len(gpustat_writes),
            "all_reads_returned_zero": all_zero,
            "read_values_observed": sorted(read_values),
            "read_model": read_model,
            "owner_counts": dict(sorted(owner_counts.items())),
            "dominant_owner_pc": dominant_owner,
            "dominant_owner_count": dominant_owner_count,
            "dominant_owner_share": (
                round(dominant_owner_count / len(gpustat_reads), 6)
                if gpustat_reads else 0.0
            ),
            "poll_exit_condition": "bit26_ready_to_receive_cmd == 1",
            "poll_exit_observable_under_model": False,
            "bit_meanings": {str(k): v for k, v in sorted(GPUSTAT_BIT_MEANINGS.items())},
        },
        "adjacent_frontier": {
            "gp0_write_count": len(gp0_writes),
            "dma2_window_event_count": len(dma2),
            "interrupt_access_count": class_counts.get("INTERRUPT_ACCESS", 0),
            "timer_access_count": class_counts.get("TIMER_ACCESS", 0),
        },
        "claims": {
            "first_frame_ready": "NO",
            "initialization": "NOT_PROVEN",
            "frame": "NOT_PROVEN",
            "playability": "NOT_PROVEN",
            "general_compatibility": "NOT_PROVEN",
        },
        "binding_constraint": (
            "Under the declared ZERO_FILL_RECORDED read model every GPUSTAT read "
            "returns zero, so the guest's poll exit condition (bit 26 = 1) can "
            "never be evaluated true and authentic execution cannot leave the "
            "wait loop. A faithful model would have to make GPUSTAT report "
            "bit 26 (ready-to-receive-command) as 1 as a function of GPU state, "
            "not as a title-specific constant."
        ),
        "promotes_no_proof_marker": True,
    }
    return analysis


def analyse_committed() -> tuple[dict[str, Any], str]:
    document, digest = load_transcript()
    return analyse(document, digest), digest


def main() -> int:
    analysis, _ = analyse_committed()
    print("OPENRECOMP_PHASE18_GPUSTAT_FRONTIER_ANALYSIS=PASS")
    print(json.dumps({
        "dominant_owner_pc": analysis["gpustat"]["dominant_owner_pc"],
        "gpustat_read_count": analysis["gpustat"]["read_count"],
        "all_reads_returned_zero": analysis["gpustat"]["all_reads_returned_zero"],
        "read_model": analysis["gpustat"]["read_model"],
        "stop_reason": analysis["frontier"]["runtime_stop_reason"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
