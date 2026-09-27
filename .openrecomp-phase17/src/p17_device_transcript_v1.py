#!/usr/bin/env python3
"""OpenRecomp Phase-17 P17-06R device/BIOS side-effect transcript model.

This module owns the public-safe representation of the BIOS/device side effects
observed by authentic P17-06R guest execution:

* BIOS dispatch events (A0 / B0 / C0 vectors and their function selectors),
* memory-mapped I/O events (GP0 / GP1 / GPUSTAT / DMA / OT / timers /
  interrupts / CD-ROM / SPU / PAD and any other PS1 hardware register),
* deterministic canonical serialization, and hashing.

Design constraints honoured here:

* every event is a fact of execution (a dispatch that happened, an access that
  happened); no event is ever inferred from an address that was merely decoded;
* the transcript document carries only sequence numbers, addresses, register
  values, widths, class names and provenance digests - never raw payload bytes,
  never BIOS bytes, never private paths;
* classification is a pure function of the accessed physical address and the
  access direction, so it can be reproduced by an independent reviewer.

The BIOS dispatch envelope (vector, function selector, arguments, return
transfer) is modelled by the emitted runtime.  BIOS internals are explicitly
NOT modelled and the transcript records that boundary per event.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_TRANSCRIPT = "openrecomp-phase17-device-transcript-v1"

#: Event kinds produced by the emitted runtime.
KIND_BIOS_DISPATCH = 1
KIND_MMIO = 2

BIOS_VECTOR_NAMES: dict[int, str] = {
    0x000000A0: "A0",
    0x000000B0: "B0",
    0x000000C0: "C0",
    0x800000A0: "A0",
    0x800000B0: "B0",
    0x800000C0: "C0",
}

#: PS1 hardware register window (physical).
MMIO_PHYS_START = 0x1F801000
MMIO_PHYS_END = 0x1F802000

#: Canonical KSEG1 aliases of the hardware window.
_KSEG1_ALIASES = (0xA0000000, 0xBF800000)

BIOS_MODEL = "ENVELOPE_DISPATCH_RETURN_TO_RA"
BIOS_INTERNALS = "NOT_MODELED"
MMIO_READ_MODEL = "ZERO_FILL_RECORDED"
MMIO_WRITE_MODEL = "RECORDED_NOT_APPLIED"


class TranscriptError(ValueError):
    """Fail-closed transcript rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def physical_address(address: int) -> int | None:
    """Map a guest address into the PS1 hardware window, or return None."""
    address &= 0xFFFFFFFF
    if MMIO_PHYS_START <= address < MMIO_PHYS_END:
        return address
    for base in _KSEG1_ALIASES:
        candidate = address - base
        if MMIO_PHYS_START <= candidate < MMIO_PHYS_END:
            return candidate
    return None


def bios_vector_name(pc: int) -> str | None:
    return BIOS_VECTOR_NAMES.get(pc & 0xFFFFFFFF)


def classify_device_access(address: int, *, store: bool, width: int,
                           value: int = 0) -> str | None:
    """Classify a hardware access purely from its physical address.

    Returns None when the address is not a PS1 hardware register.
    """
    phys = physical_address(address)
    if phys is None:
        return None
    if phys == 0x1F801810:
        return "GP0_WRITE" if store else "GP0_READ"
    if phys == 0x1F801814:
        return "GP1_WRITE" if store else "GPUSTAT_READ"
    if 0x1F801040 <= phys <= 0x1F80104F:
        return "PAD_ACCESS"
    if 0x1F801050 <= phys <= 0x1F80105F:
        return "SIO_ACCESS"
    if 0x1F801070 <= phys <= 0x1F801077:
        return "INTERRUPT_ACCESS"
    if 0x1F801080 <= phys <= 0x1F8010FF:
        # DMA channel registers: CHCR low word is at offset 0x8 of each channel.
        channel_offset = (phys - 0x1F801080) & 0x7F
        if channel_offset == 0x8 and store and (value & 0x04000000):
            return "OT_DMA_CHAIN_START"
        return "DMA_ACCESS"
    if 0x1F801100 <= phys <= 0x1F80112F:
        return "TIMER_ACCESS"
    if 0x1F801800 <= phys <= 0x1F801803:
        return "CDROM_ACCESS"
    if 0x1F801C00 <= phys <= 0x1F801FFF:
        return "SPU_ACCESS"
    return "MMIO_ACCESS"


def bios_event(*, sequence: int, vector_pc: int, function: int, args: list[int],
               ra: int, sp: int, gp: int, owning_instruction_pc: int,
               delay_slot_pc: int | None) -> dict[str, Any]:
    """Build one public-safe BIOS dispatch event."""
    name = bios_vector_name(vector_pc)
    if name is None:
        raise TranscriptError("NOT_A_BIOS_VECTOR", hex32(vector_pc))
    return {
        "sequence": sequence,
        "kind": "BIOS_DISPATCH",
        "vector": name,
        "vector_pc": hex32(vector_pc),
        "table_index": hex32(function),
        "table_index_decimal": function & 0xFFFFFFFF,
        "function_number": hex32(function),
        "arguments": {
            "a0": hex32(args[0]), "a1": hex32(args[1]),
            "a2": hex32(args[2]), "a3": hex32(args[3]),
        },
        "ra": hex32(ra),
        "sp": hex32(sp),
        "gp": hex32(gp),
        "owning_instruction_pc": hex32(owning_instruction_pc),
        "delay_slot_pc": hex32(delay_slot_pc) if delay_slot_pc is not None else None,
        "transfer_semantics": BIOS_MODEL,
        "return_pc": hex32(ra),
        "bios_internals": BIOS_INTERNALS,
    }


def mmio_event(*, sequence: int, address: int, store: bool, width: int,
               value: int, owning_instruction_pc: int,
               delay_slot_pc: int | None) -> dict[str, Any]:
    """Build one public-safe memory-mapped I/O event."""
    class_name = classify_device_access(address, store=store, width=width, value=value)
    if class_name is None:
        raise TranscriptError("NOT_A_DEVICE_ADDRESS", hex32(address))
    return {
        "sequence": sequence,
        "kind": "MMIO",
        "class": class_name,
        "access": "WRITE" if store else "READ",
        "address": hex32(address),
        "width": width,
        "value": hex32(value),
        "owning_instruction_pc": hex32(owning_instruction_pc),
        "delay_slot_pc": hex32(delay_slot_pc) if delay_slot_pc is not None else None,
        "model": MMIO_WRITE_MODEL if store else MMIO_READ_MODEL,
    }


def attach_provenance(events: list[dict[str, Any]],
                      provenance_digest_by_pc: dict[int, str]) -> list[dict[str, Any]]:
    """Attach the owning-instruction provenance digest to every event.

    Fail closed when an event claims an owning instruction that is not in the
    authenticated table: an event without a provenance chain is not evidence.
    """
    enriched: list[dict[str, Any]] = []
    for event in events:
        owner = int(str(event["owning_instruction_pc"]), 16)
        digest = provenance_digest_by_pc.get(owner)
        if digest is None:
            raise TranscriptError("EVENT_WITHOUT_PROVENANCE", hex32(owner))
        item = dict(event)
        item["owning_instruction_provenance_digest"] = digest
        enriched.append(item)
    return enriched


def canonical_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transcript_document(*, stage: str, next_stage: str,
                        events: list[dict[str, Any]],
                        bios_dispatch_count: int, device_event_count: int,
                        continuation_entry_pc: int,
                        stop_reason: str) -> dict[str, Any]:
    """Assemble the deterministic transcript document (hash-free)."""
    counts: dict[str, int] = {}
    for event in events:
        key = event["kind"] if event["kind"] != "MMIO" else event["class"]
        counts[key] = counts.get(key, 0) + 1
    return {
        "schema": SCHEMA_TRANSCRIPT,
        "stage": stage,
        "next_stage": next_stage,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "event_count": len(events),
        "bios_dispatch_count": bios_dispatch_count,
        "device_event_count": device_event_count,
        "event_class_counts": dict(sorted(counts.items())),
        "continuation_entry_pc": hex32(continuation_entry_pc),
        "runtime_stop_reason": stop_reason,
        "bios_model": {"dispatch": BIOS_MODEL, "internals": BIOS_INTERNALS},
        "mmio_model": {"read": MMIO_READ_MODEL, "write": MMIO_WRITE_MODEL},
        "events": events,
    }


def validate_transcript(document: dict[str, Any],
                        provenance_digest_by_pc: dict[int, str]) -> None:
    """Fail-closed re-validation of a transcript document."""
    if document.get("schema") != SCHEMA_TRANSCRIPT:
        raise TranscriptError("TRANSCRIPT_SCHEMA_MISMATCH")
    events = document.get("events")
    if not isinstance(events, list):
        raise TranscriptError("TRANSCRIPT_EVENTS_MISSING")
    if int(document.get("event_count", -1)) != len(events):
        raise TranscriptError("TRANSCRIPT_EVENT_COUNT_MISMATCH")
    for index, event in enumerate(events):
        if int(event.get("sequence", -1)) != index:
            raise TranscriptError("TRANSCRIPT_SEQUENCE_GAP", str(index))
        owner = int(str(event["owning_instruction_pc"]), 16)
        digest = provenance_digest_by_pc.get(owner)
        if digest is None:
            raise TranscriptError("EVENT_WITHOUT_PROVENANCE", hex32(owner))
        if event.get("owning_instruction_provenance_digest") != digest:
            raise TranscriptError("EVENT_PROVENANCE_DIGEST_MISMATCH", hex32(owner))
        if event["kind"] == "BIOS_DISPATCH":
            if bios_vector_name(int(str(event["vector_pc"]), 16)) != event["vector"]:
                raise TranscriptError("EVENT_VECTOR_MISMATCH", str(index))
            if event.get("bios_internals") != BIOS_INTERNALS:
                raise TranscriptError("EVENT_BIOS_MODEL_MISMATCH", str(index))
        elif event["kind"] == "MMIO":
            address = int(str(event["address"]), 16)
            store = event["access"] == "WRITE"
            expected = classify_device_access(address, store=store,
                                              width=int(event["width"]),
                                              value=int(str(event["value"]), 16))
            if expected != event.get("class"):
                raise TranscriptError("EVENT_MMIO_CLASS_MISMATCH", str(index))
        else:
            raise TranscriptError("EVENT_KIND_UNKNOWN", str(index))
