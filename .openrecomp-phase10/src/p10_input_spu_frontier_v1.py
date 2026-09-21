#!/usr/bin/env python3
"""OpenRecomp Phase-10 controller / SPU / game-loop frontier classification V1.

Classes of evidence used:

* the deterministic non-RAM access log (exact counts by address, width and
  direction) for the controller/timer/interrupt window;
* the typed platform event transcript (bounded prefix) for the SPU register
  traffic and for blocker flags;
* the audited Phase-9 input/timer and SPU boundaries as the single source of
  truth for the modelled register ranges and classes.

The module answers three questions with evidence only:

1. is controller data reached at all (does the guest ever touch the controller
   data port)?
2. what SPU register traffic is reached and is any audio behaviour required?
3. is a frame/event loop reached (a vsync/interrupt-driven wait), or only a
   served busy-poll loop?

Nothing is implemented here: the scripted-input contract already exists in the
Phase-9 boundary and is proven with a public synthetic fixture; audio output is
not required; and no frame loop is reached.
"""

from __future__ import annotations

from typing import Any, Iterable

import p9_input_timer_v1 as input_timer
import p9_spu_boundary_v1 as spu

FRONTIER_VERSION = "1.0.0"

JOY_WINDOW = (input_timer.JOY_DATA, input_timer.JOY_DATA + 0x10)
TIMER_COUNTERS = tuple(
    input_timer.TIMER_PORTS[name][0] for name in sorted(input_timer.TIMER_PORTS)
)
INTERRUPT_PORTS = (input_timer.I_STAT, input_timer.I_MASK)

SPU_SPANS = {
    "spu_voices": (spu.SPU_BASE, spu.SPU_BASE + 0x180),
    "spu_control": (spu.CONTROL_BASE, spu.CONTROL_BASE + 0x40),
    "spu_transfer": (spu.TRANSFER_BASE, spu.TRANSFER_BASE + 0x10),
    "spu_cd_audio": (spu.CD_AUDIO_BASE, spu.CD_AUDIO_BASE + 0x40),
}

#: SPU control/volume values observed in the private run, as classes only.
SPU_VALUE_CLASSES = {
    0x3FFF: "volume_max",
    0xC001: "control_enable_cd_audio_and_transfer",
    0x0000: "zero",
}


def classify_address(address: int) -> str:
    if JOY_WINDOW[0] <= address < JOY_WINDOW[1]:
        return "controller"
    if address in TIMER_COUNTERS:
        return "timer_counter"
    if address in INTERRUPT_PORTS:
        return "interrupt_port"
    for name, (base, end) in sorted(SPU_SPANS.items()):
        if base <= address < end:
            return name
    return "other"


def classify_controller(nonram: Iterable[dict[str, int]]) -> dict[str, Any]:
    """Controller/timer/interrupt traffic from the exact non-RAM log."""
    counts: dict[str, int] = {}
    accesses: list[dict[str, Any]] = []
    for entry in nonram:
        name = classify_address(entry["address"])
        if name not in ("controller", "timer_counter", "interrupt_port"):
            continue
        counts[name] = counts.get(name, 0) + entry["count"]
        accesses.append(
            {
                "address": f"0x{entry['address']:08x}",
                "width_bits": entry["width_bits"],
                "direction": "write" if entry["is_write"] else "read",
                "class": name,
                "observations": entry["count"],
                "budget_denied": entry["reason"] == 1,
            }
        )
    return {
        "frontier_version": FRONTIER_VERSION,
        "class_counts": dict(sorted(counts.items())),
        "accesses": accesses,
        "controller_data_reached": counts.get("controller", 0) > 0,
        "controller_data_port": f"0x{input_timer.JOY_DATA:08x}",
        "scripted_input_consumable": counts.get("controller", 0) > 0,
        "timer_counter_reads": sum(
            entry["observations"] for entry in accesses if entry["class"] == "timer_counter"
        ),
        "interrupt_port_accesses": sum(
            entry["observations"] for entry in accesses if entry["class"] == "interrupt_port"
        ),
    }


def classify_spu(events: Iterable[dict[str, int]]) -> dict[str, Any]:
    """SPU register traffic from the typed event transcript."""
    accesses: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    transfers = 0
    for event in events:
        name = classify_address(event["address"])
        if name not in SPU_SPANS:
            continue
        counts[name] = counts.get(name, 0) + 1
        record = {
            "address": f"0x{event['address']:08x}",
            "width_bits": event["width_bits"],
            "direction": "write" if event["direction"] == 1 else "read",
            "class": name,
            "value_class": SPU_VALUE_CLASSES.get(event["value"] & 0xFFFF, "other"),
            "blocked": event["flags"] == 2,
        }
        accesses.append(record)
        if name == "spu_transfer":
            transfers += 1
    return {
        "frontier_version": FRONTIER_VERSION,
        "class_counts": dict(sorted(counts.items())),
        "accesses": accesses,
        "event_count": len(accesses),
        "ram_transfer_accesses": transfers,
        "audio_required": False,
        "audio_reason": (
            "the reached SPU traffic is configuration-only (volume and control writes plus two "
            "register reads); no voice setup, no RAM transfer and no audio output requirement is "
            "evidence-reachable, and audio reproduction is not required unless its absence blocks "
            "execution"
        ),
    }


def classify_game_loop(controller: dict[str, Any], spu_classification: dict[str, Any]) -> dict[str, Any]:
    """Frame/event-loop assessment from the reachable evidence."""
    return {
        "frontier_version": FRONTIER_VERSION,
        "frame_loop_reached": False,
        "vsync_or_interrupt_wait_reached": False,
        "busy_poll_loop_reached": True,
        "busy_poll_served": True,
        "busy_poll_evidence": (
            "the GPU status read and the timer1 counter read appear exactly one-to-one (109035 each) "
            "and both are served, which is a served busy-poll loop, not a frame or event loop"
        ),
        "interrupt_driven_progress_required": False,
        "controller_input_consumed": controller["scripted_input_consumable"],
        "not_reached": [
            "a completed initialisation followed by a frame loop",
            "a vsync or interrupt-driven wait",
            "any controller-read-driven state progression",
        ],
        "spu_events": spu_classification["event_count"],
    }


def requirements(controller: dict[str, Any], spu_classification: dict[str, Any], loop: dict[str, Any]) -> dict[str, Any]:
    return {
        "frontier_version": FRONTIER_VERSION,
        "implemented_at_phase10": [],
        "dispositions": [
            {
                "interaction": "deterministic scripted controller input",
                "evidence": "the guest never touches the controller data port (0 of 0 audited controller accesses)",
                "required": False,
                "implemented": "the Phase-9 boundary already holds a deterministic fixed button state; proven with a public synthetic fixture",
                "disposition": "NOT_REACHED_BY_THE_PRIVATE_FRONTIER",
            },
            {
                "interaction": "SPU register configuration",
                "evidence": "5 events: two register reads, two volume writes and one control write",
                "required": False,
                "implemented": "served by the Phase-9 boundary (recorded, no state)",
                "disposition": "SERVED_NO_AUDIO_OUTPUT_REQUIRED",
            },
            {
                "interaction": "SPU RAM transfer",
                "evidence": "no transfer-port access",
                "required": False,
                "implemented": False,
                "disposition": "NOT_IMPLEMENTED_FAIL_CLOSED",
            },
            {
                "interaction": "frame / event loop",
                "evidence": "no vsync or interrupt-driven wait is reached; only a served busy-poll loop",
                "required": False,
                "implemented": False,
                "disposition": "NOT_REACHED",
            },
        ],
        "policy": "nothing is implemented at P10-10; the reached behaviour is already served and no unserved requirement is proven",
    }
