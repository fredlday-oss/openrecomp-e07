#!/usr/bin/env python3
"""OpenRecomp Phase-18 P18-04 GPU command frontier V1.

P18-03 established that the authentic continuation reaches BIOS dispatch,
GPUSTAT reads, INTERRUPT and TIMER traffic - and no GP0/GP1 write.  P18-04 asks
the GPU-command question mechanically: *is* any GP0/GP1 command reachable, and
if so, what does it decode to?

The module does three things, none of them title-specific and none of them
fabricating traffic:

1. It proves from the generated runtime source that the GP0/GP1 write path
   exists and is gated on exactly 0x1f801810 / 0x1f801814, so an "unreached"
   result is a genuine frontier state, not a missing implementation.
2. It installs a third additive overlay that records every GP0/GP1 write the
   device model actually receives (physical register, opaque word digest, owner
   PC) and reports GP0/GP1 as explicitly NOT_REACHED when none occurred - never
   as a silent no-op.
3. It classifies reached GP0 command words into an explicit class set; a word
   matching no class is reported UNKNOWN and never treated as a valid no-op.

Nothing here weakens the P18-02/P18-03 overlays; P18-04 only adds taps.  The
module promotes no proof marker: FIRST_FRAME_READY stays NO and the Phase-18
claim markers stay NOT_PROVEN.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _extra in ("", ".openrecomp-phase18/src", ".openrecomp-phase17/src",
               ".openrecomp-phase3/src", ".openrecomp-phase9/src"):
    _path = str(ROOT / _extra) if _extra else str(ROOT)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import p18_exec_continuation_v1 as p18b  # noqa: E402

import p18_causal_transcript_v1 as p18c  # noqa: E402

STAGE = "P18-04"
NEXT_STAGE = "P18-05"

#: PS1 GPU register physical window.
GP0_PHYS = 0x1F801810
GP1_PHYS = 0x1F801814
GP0GP1_PHYS = (GP0_PHYS, GP1_PHYS)

#: The high half of the PS1 hardware-register physical window (0x1f80xxxx).
HW_WINDOW_HIGH = 0x1F80

#: Line prefixes of the P18-04 generated-runtime tap.
FIFO_PREFIX = "P18G_FIFO"


class GpuCommandFrontierError(ValueError):
    """Fail-closed P18-04 rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def _public_phys(addr: int) -> int:
    """Reduce a KUSEG/KSEG0/KSEG1 address to its physical MMIO register."""
    candidate = addr & 0x1FFFFFFF
    if 0x1F801000 <= candidate < 0x1F802000:
        return candidate
    raise GpuCommandFrontierError("ADDRESS_NOT_HARDWARE_WINDOW", hex32(addr))


def classify_gp0_command(word: int) -> dict[str, Any]:
    """Classify one GP0 command word against the declared class set.

    Only classes required by authentic execution are named; anything unmatched
    is reported UNKNOWN and is never silently swallowed as a no-op.
    """
    value = word & 0xFFFFFFFF
    command = (value >> 24) & 0xFF
    if command == 0x00:
        name = "NOP"
    elif command == 0x01:
        name = "CLEAR_CACHE"
    elif command == 0x02:
        name = "FILL_RECTANGLE"
    elif (command & 0xE0) == 0x20:
        name = "POLYGON"
    elif (command & 0xE0) == 0x40:
        name = "LINE"
    elif (command & 0xE0) == 0x60:
        name = "RECTANGLE"
    elif (command & 0xF8) == 0x80:
        name = "VRAM_TO_VRAM_COPY"
    elif (command & 0xF8) == 0xA0:
        name = "CPU_TO_VRAM_COPY"
    elif (command & 0xF8) == 0xC0:
        name = "VRAM_TO_CPU_COPY"
    elif (command & 0xF8) == 0xE0:
        name = "ENVIRONMENT"
    elif (command & 0xF8) == 0xE1:
        name = "DRAW_MODE"
    elif (command & 0xF8) == 0xE2:
        name = "TEXTURE_WINDOW"
    elif (command & 0xF8) == 0xE3:
        name = "DRAWING_AREA_TOP_LEFT"
    elif (command & 0xF8) == 0xE4:
        name = "DRAWING_AREA_BOTTOM_RIGHT"
    elif (command & 0xF8) == 0xE5:
        name = "DRAWING_OFFSET"
    elif (command & 0xF8) == 0xE6:
        name = "MASK_BIT"
    else:
        name = "UNKNOWN"
    return {
        "command_byte": f"0x{command:02x}",
        "class": name,
        "unsupported": name == "UNKNOWN",
    }


class Gp0Gp1FrontierTap:
    """Pure-Python model of the per-write GP0/GP1 tap.

    The real tap lives in the generated C runtime; this model exists so the
    classifier, the physical-address reduction and the window-unreached rule can
    be positive- and negative-tested without emitting a runtime.  Both share the
    class set above.
    """

    def __init__(self) -> None:
        self.writes: list[dict[str, Any]] = []

    def record_write(self, addr: int, word: int, owner_pc: int) -> dict[str, Any]:
        phys = _public_phys(addr)
        if phys not in GP0GP1_PHYS:
            raise GpuCommandFrontierError("WRITE_NOT_GP0_GP1", hex32(phys))
        entry: dict[str, Any] = {
            "register": "GP0" if phys == GP0_PHYS else "GP1",
            "physical_address": hex32(phys),
            "owner_pc": hex32(owner_pc),
            "word_digest": _sha256_bytes((word & 0xFFFFFFFF).to_bytes(4, "little")),
        }
        entry.update(classify_gp0_command(word) if phys == GP0_PHYS
                     else {"command_byte": "n/a", "class": "GP1_CONTROL",
                           "unsupported": False})
        self.writes.append(entry)
        return entry


def window_unreached(opened: bool, address: int) -> bool:
    """True only when the GP0/GP1 window is genuinely unopened.

    A non-window address may never be claimed unreached through this helper: the
    physical reduction is required to land in the GP0/GP1 window.
    """
    if opened:
        return False
    phys = address & 0x1FFFFFFF
    if phys not in GP0GP1_PHYS:
        raise GpuCommandFrontierError("NOT_A_GP0_GP1_ADDRESS", hex32(address))
    return True


# --------------------------------------------------------------------------
# Generated-runtime tap (third additive overlay on P18-02/P18-03)
# --------------------------------------------------------------------------

_G_TAP_BLOCK = r"""
/* --- P18-04: GP0/GP1 command-frontier tap (no title constants) ---------- */
#define OR_P18G_FIFO_CAP 65536u
static uint32_t s_p18g_fifo_count = 0u;
static uint32_t s_p18g_fifo_phys[OR_P18G_FIFO_CAP];
static uint32_t s_p18g_fifo_word[OR_P18G_FIFO_CAP];
static uint32_t s_p18g_fifo_owner[OR_P18G_FIFO_CAP];
static uint32_t s_p18g_fifo_log_overflow = 0u;
static uint32_t s_p18g_gp0_total = 0u;
static uint32_t s_p18g_gp1_total = 0u;

static void or_p18g_fifo_record(uint32_t phys, uint32_t word, uint32_t owner) {
    if (phys != 0x1f801810u && phys != 0x1f801814u) return;
    if (s_p18g_fifo_count >= OR_P18G_FIFO_CAP) { s_p18g_fifo_log_overflow = 1u; return; }
    s_p18g_fifo_phys[s_p18g_fifo_count] = phys;
    s_p18g_fifo_word[s_p18g_fifo_count] = word;
    s_p18g_fifo_owner[s_p18g_fifo_count] = owner;
    s_p18g_fifo_count++;
    if (phys == 0x1f801810u) s_p18g_gp0_total++;
    else s_p18g_gp1_total++;
}

uint32_t or_p18g_fifo_count(void) { return s_p18g_fifo_count; }
uint32_t or_p18g_fifo_phys(uint32_t i) { return (i < s_p18g_fifo_count) ? s_p18g_fifo_phys[i] : 0u; }
uint32_t or_p18g_fifo_word(uint32_t i) { return (i < s_p18g_fifo_count) ? s_p18g_fifo_word[i] : 0u; }
uint32_t or_p18g_fifo_owner(uint32_t i) { return (i < s_p18g_fifo_count) ? s_p18g_fifo_owner[i] : 0u; }
uint32_t or_p18g_fifo_overflow(void) { return s_p18g_fifo_log_overflow; }
uint32_t or_p18g_gp0_total(void) { return s_p18g_gp0_total; }
uint32_t or_p18g_gp1_total(void) { return s_p18g_gp1_total; }
"""

_G_TAP_DUMP = r"""
    {
        extern uint32_t or_p18g_fifo_count(void);
        extern uint32_t or_p18g_fifo_phys(uint32_t i);
        extern uint32_t or_p18g_fifo_word(uint32_t i);
        extern uint32_t or_p18g_fifo_owner(uint32_t i);
        extern uint32_t or_p18g_fifo_overflow(void);
        extern uint32_t or_p18g_gp0_total(void);
        extern uint32_t or_p18g_gp1_total(void);
        uint32_t _g18, _g18n = or_p18g_fifo_count();
        printf("P18G_FIFO_COUNT %u\n", (unsigned)_g18n);
        printf("P18G_FIFO_OVERFLOW %u\n", (unsigned)or_p18g_fifo_overflow());
        printf("P18G_GP0_TOTAL %u\n", (unsigned)or_p18g_gp0_total());
        printf("P18G_GP1_TOTAL %u\n", (unsigned)or_p18g_gp1_total());
        for (_g18 = 0u; _g18 < _g18n; _g18++) {
            printf("P18G_FIFO %u 0x%08x 0x%08x 0x%08x\n",
                   (unsigned)_g18,
                   (unsigned)or_p18g_fifo_phys(_g18),
                   (unsigned)or_p18g_fifo_word(_g18),
                   (unsigned)or_p18g_fifo_owner(_g18));
        }
    }
"""

#: Anchor of the P18-02-overlaid runtime that the P18-04 tap extends: the
#: GPU write function definition, so the tap definitions precede their first use.
G_INSERT_ANCHOR = "static void or_p18_gpu_write(uint32_t phys, uint32_t value) {"
G_WRITE_FN = "static void or_p18_gpu_write(uint32_t phys, uint32_t value) {"
G_WRITE_CLOSE = "    else s_p18_fifo_overflow = 1u;\n}"

_OVERLAY_STATE: dict[str, Any] = {"installed": False}
_ORIGINALS: dict[str, Any] = {
    "generate_runtime": p18b.side._generate_runtime,
    "generate_harness": p18b.side._generate_harness,
}


def _count(text: str, needle: str) -> int:
    return text.count(needle)


def build_tap_source() -> str:
    return _G_TAP_BLOCK


def apply_gpu_frontier_runtime_overlay(runtime_source: str, enabled: bool) -> str:
    """Insert the GP0/GP1 FIFO tap into a P18-02-overlaid runtime.

    Additive only: the P18-02 write path is preserved verbatim; the tap records
    the already-classified physical address and the word the device model
    received.  A missing or duplicated anchor fails closed.
    """
    if _count(runtime_source, G_INSERT_ANCHOR) != 1:
        raise GpuCommandFrontierError(
            "OVERLAY_ANCHOR_MISSING", f"tap-insert={_count(runtime_source, G_INSERT_ANCHOR)}")
    if _count(runtime_source, G_WRITE_FN) != 1:
        raise GpuCommandFrontierError(
            "OVERLAY_ANCHOR_MISSING", f"gpu-write={_count(runtime_source, G_WRITE_FN)}")
    if _count(runtime_source, G_WRITE_CLOSE) != 1:
        raise GpuCommandFrontierError(
            "OVERLAY_ANCHOR_MISSING", f"gpu-write-close={_count(runtime_source, G_WRITE_CLOSE)}")

    if "or_p18g_fifo_record(uint32_t phys" in runtime_source:
        raise GpuCommandFrontierError("OVERLAY_TAP_ALREADY_PRESENT")
    text = runtime_source.replace(G_INSERT_ANCHOR, build_tap_source() + G_INSERT_ANCHOR, 1)
    replacement = G_WRITE_CLOSE.replace(
        "    else s_p18_fifo_overflow = 1u;\n}",
        "    else s_p18_fifo_overflow = 1u;\n"
        "    or_p18g_fifo_record(phys, value, g_p18_pc);\n}")
    text = text.replace(G_WRITE_CLOSE, replacement, 1)

    if "or_p18g_fifo_record(phys, value, g_p18_pc);" not in text:
        raise GpuCommandFrontierError("OVERLAY_TAP_HOOK_MISSING")
    if "or_p18_gpu_write(phys, value);" not in text:
        raise GpuCommandFrontierError("OVERLAY_GPU_WRITE_REMAINS")
    if "if (phys == 0x1f801810u || phys == 0x1f801814u) or_p18_gpu_write(phys, value);" not in text:
        raise GpuCommandFrontierError("OVERLAY_WRITE_GATE_MISSING")
    return text


def apply_gpu_frontier_harness_overlay(harness_source: str, enabled: bool) -> str:
    """Insert the FIFO dump just before the P17-06R harness END marker."""
    anchor = p18b.ANCHOR_HARNESS_END
    if _count(harness_source, anchor) != 1:
        raise GpuCommandFrontierError("OVERLAY_ANCHOR_MISSING", "harness-end")
    return harness_source.replace(anchor, _G_TAP_DUMP + anchor, 1)


def overlay_anchor_selftest() -> dict[str, Any]:
    """Fail-closed anchor controls against a synthetic P18-02-overlaid source."""
    results: dict[str, Any] = {}
    synthetic = (p18b.ANCHOR_RUNTIME_INCLUDE + p18b.build_gpu_state_source(True)
                 + p18b.ANCHOR_LOOP_HEAD)
    applied = apply_gpu_frontier_runtime_overlay(synthetic, True)
    results["valid_applies"] = (
        "or_p18g_fifo_record(phys, value, g_p18_pc);" in applied
        and "or_p18_gpu_write(phys, value);" in applied)
    try:
        apply_gpu_frontier_runtime_overlay(
            synthetic.replace(G_INSERT_ANCHOR, "", 1), True)
        results["missing_insert_rejected"] = False
    except GpuCommandFrontierError as err:
        results["missing_insert_rejected"] = err.code == "OVERLAY_ANCHOR_MISSING"
    try:
        apply_gpu_frontier_runtime_overlay(
            synthetic.replace(G_WRITE_CLOSE, "", 1), True)
        results["missing_write_rejected"] = False
    except GpuCommandFrontierError as err:
        results["missing_write_rejected"] = err.code == "OVERLAY_ANCHOR_MISSING"
    try:
        apply_gpu_frontier_harness_overlay("int main(void){return 0;}\\n", True)
        results["missing_harness_end_rejected"] = False
    except GpuCommandFrontierError as err:
        results["missing_harness_end_rejected"] = err.code == "OVERLAY_ANCHOR_MISSING"
    results["ok"] = all(value for key, value in results.items() if key != "ok")
    return results


# --------------------------------------------------------------------------
# Parse the generated runtime FIFO tap back into a public-safe frontier
# --------------------------------------------------------------------------

def _parse_fifo_lines(text: str) -> dict[str, Any]:
    count = None
    overflow = 0
    gp0_total = 0
    gp1_total = 0
    entries: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.startswith("P18G_"):
            continue
        if line.startswith("P18G_FIFO_COUNT "):
            count = int(line.split(" ", 1)[1])
        elif line.startswith("P18G_FIFO_OVERFLOW "):
            overflow = int(line.split(" ", 1)[1])
        elif line.startswith("P18G_GP0_TOTAL "):
            gp0_total = int(line.split(" ", 1)[1])
        elif line.startswith("P18G_GP1_TOTAL "):
            gp1_total = int(line.split(" ", 1)[1])
        elif line.startswith("P18G_FIFO "):
            parts = line.split(" ")
            entries.append({
                "sequence": int(parts[1]),
                "physical_address": int(parts[2], 16),
                "word": int(parts[3], 16),
                "owner_pc": int(parts[4], 16),
            })
    if count is None:
        raise GpuCommandFrontierError("FIFO_COUNT_MISSING")
    if overflow:
        raise GpuCommandFrontierError("FIFO_LOG_OVERFLOW")
    if count != len(entries):
        raise GpuCommandFrontierError(
            "FIFO_COUNT_MISMATCH", f"reported={count} parsed={len(entries)}")
    observed_gp0 = sum(1 for e in entries if e["physical_address"] == GP0_PHYS)
    observed_gp1 = sum(1 for e in entries if e["physical_address"] == GP1_PHYS)
    if observed_gp0 != gp0_total or observed_gp1 != gp1_total:
        raise GpuCommandFrontierError(
            "FIFO_TOTAL_MISMATCH",
            f"gp0={observed_gp0}/{gp0_total} gp1={observed_gp1}/{gp1_total}")
    return {
        "fifo_count": count,
        "gp0_total": gp0_total,
        "gp1_total": gp1_total,
        "entries": entries,
    }


def build_gpu_command_frontier(runtime_result: dict[str, Any], generated_source: str,
                               provenance_map: dict[int, str]
                               ) -> tuple[dict[str, Any], str]:
    """Assemble + fail-closed validate the GPU command frontier document."""
    fifo = runtime_result.get("p18g_fifo")
    if not isinstance(fifo, dict):
        raise GpuCommandFrontierError("FIFO_RESULT_MISSING")
    write_path = write_path_discipline(generated_source)
    if not write_path["gp0gp1_write_path_present"]:
        raise GpuCommandFrontierError("GPU_WRITE_PATH_ABSENT")

    events: list[dict[str, Any]] = []
    reached_registers: set[str] = set()
    for entry in fifo["entries"]:
        phys = entry["physical_address"]
        if phys not in GP0GP1_PHYS:
            raise GpuCommandFrontierError("FIFO_ADDRESS_NOT_GP0_GP1", hex32(phys))
        owner = entry["owner_pc"]
        if owner not in provenance_map:
            raise GpuCommandFrontierError("EVENT_WITHOUT_PROVENANCE", hex32(owner))
        register = "GP0" if phys == GP0_PHYS else "GP1"
        reached_registers.add(register)
        word = entry["word"] & 0xFFFFFFFF
        event: dict[str, Any] = {
            "sequence": entry["sequence"],
            "register": register,
            "physical_address": hex32(phys),
            "owner_pc": hex32(owner),
            "owner_provenance_digest": provenance_map[owner],
            "word_digest": _sha256_bytes(word.to_bytes(4, "little")),
            "width": 4,
        }
        event.update(classify_gp0_command(word) if register == "GP0"
                     else {"command_byte": "n/a", "class": "GP1_CONTROL",
                           "unsupported": False})
        events.append(event)

    frontier_reached = bool(events)
    document: dict[str, Any] = {
        "schema": "openrecomp-phase18-gpu-command-frontier-v1",
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "gp0_write_count": fifo["gp0_total"],
        "gp1_write_count": fifo["gp1_total"],
        "fifo_count": fifo["fifo_count"],
        "frontier_reached": frontier_reached,
        "reached_registers": sorted(reached_registers),
        "command_classes": sorted({event["class"] for event in events}),
        "unsupported_command_count": sum(1 for event in events if event["unsupported"]),
        "write_path": write_path,
        "events": events,
        "promotes_no_proof_marker": True,
    }
    if not frontier_reached:
        document["gp0gp1_status"] = "NOT_REACHED"
        document["explicit_not_reached"] = True
    validate_gpu_command_frontier(document, provenance_map)
    data = (json.dumps(document, indent=2, sort_keys=True) + "\\n").encode("utf-8")
    return document, _sha256_bytes(data)


def validate_gpu_command_frontier(document: dict[str, Any],
                                  provenance_map: dict[int, str]) -> None:
    """Fail-closed re-validation of the GPU command frontier document."""
    if document.get("schema") != "openrecomp-phase18-gpu-command-frontier-v1":
        raise GpuCommandFrontierError("FRONTIER_SCHEMA_MISMATCH")
    events = document.get("events")
    if not isinstance(events, list):
        raise GpuCommandFrontierError("FRONTIER_EVENTS_MISSING")
    digests = set(provenance_map.values())
    for event in events:
        if event["physical_address"] not in (hex32(GP0_PHYS), hex32(GP1_PHYS)):
            raise GpuCommandFrontierError("FRONTIER_ADDRESS_INVALID",
                                          event["physical_address"])
        if event.get("owner_provenance_digest") not in digests:
            raise GpuCommandFrontierError("EVENT_WITHOUT_PROVENANCE",
                                          event.get("owner_pc", "?"))
        if "word_digest" not in event:
            raise GpuCommandFrontierError("EVENT_WORD_DIGEST_MISSING")
        if event["register"] == "GP0" and "class" not in event:
            raise GpuCommandFrontierError("EVENT_CLASS_MISSING")
    if not events and document.get("gp0gp1_status") != "NOT_REACHED":
        raise GpuCommandFrontierError("UNREACHED_STATUS_MISSING")
    if events and document.get("gp0gp1_status") == "NOT_REACHED":
        raise GpuCommandFrontierError("REACHED_MARKED_UNREACHED")


def frontier_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\\n").encode("utf-8")




# --------------------------------------------------------------------------
# Overlay installation / drivers (mirrors the P18-03 pattern)
# --------------------------------------------------------------------------



# --------------------------------------------------------------------------
# Generated-source write-path discipline (the frontier-unreached proof)
# --------------------------------------------------------------------------

#: The exact physical-address gate the generated runtime applies before handing
#: a write to the GPU command path.
G_WRITE_GATE = ("if (phys == 0x1f801810u || phys == 0x1f801814u)"
                " or_p18_gpu_write(phys, value);")


def write_path_discipline(generated_source: str) -> dict[str, Any]:
    """Prove from the generated source that the GP0/GP1 write path is real.

    This is the load-bearing evidence for a COMMAND FRONTIER NOT YET REACHED
    verdict: the device model genuinely contains a GP0/GP1 command path, gated
    on exactly the two physical registers, driven by state (it bumps the bounded
    command FIFO) rather than by a title-specific constant.
    """
    gate_count = _count(generated_source, G_WRITE_GATE)
    gp0_literal = _count(generated_source, "0x1f801810u")
    gp1_literal = _count(generated_source, "0x1f801814u")
    gpu_write_def = "static void or_p18_gpu_write(uint32_t phys, uint32_t value) {"
    gpu_write_present = gpu_write_def in generated_source
    body = ""
    if gpu_write_present:
        body = generated_source.split(gpu_write_def, 1)[1].split("}", 1)[0]
    pc_free = re.search(r"0x80[0-9a-f]{5}", body) is None
    state_driven = "s_p18_gpu_pending" in body
    return {
        "gp0gp1_write_path_present": bool(gate_count == 1 and gpu_write_present
                                         and pc_free and state_driven),
        "write_gate_count": gate_count,
        "gp0_literal_count": gp0_literal,
        "gp1_literal_count": gp1_literal,
        "gpu_write_function_pc_free": pc_free,
        "gpu_write_state_driven": state_driven,
        "gate_expression": "phys == GP0_PHYS || phys == GP1_PHYS -> or_p18_gpu_write",
        "unmodelled_write_model": "RECORDED_NOT_APPLIED (writes outside the GPU window return early)",
    }


def window_materialisation(analysis, reached_pcs: list[int]) -> dict[str, Any]:
    """Conservative, title-free check: is the GP0/GP1 window materialised?

    Over the authenticated records of the reached set we look for any instruction
    that materialises the hardware-register high half (0x1f80) as an immediate,
    or any branch/call target inside 0x1f80xxxx.  Finding none is necessary but
    not sufficient for "unreached"; it is combined with the runtime evidence
    (zero recorded GP0/GP1 writes) to produce the verdict.
    """
    reachable = set(reached_pcs)
    high_half_sites: list[str] = []
    for pc, record in sorted(analysis.records_by_address.items()):
        if pc not in reachable:
            continue
        operands = record.get("operands") or {}
        immediate = operands.get("imm")
        if immediate is not None and (int(immediate) & 0xFFFF) == HW_WINDOW_HIGH:
            high_half_sites.append(hex32(pc))
        target = operands.get("target")
        if target is not None:
            value = int(target) & 0xFFFFFFFF
            if value not in (GP0_PHYS, GP1_PHYS) and 0x1F800000 <= value < 0x1F802000:
                high_half_sites.append(hex32(pc))
    return {
        "reached_pc_count": len(reachable),
        "records_examined": len(analysis.records_by_address),
        "window_high_half_sites": high_half_sites,
        "window_high_half_site_count": len(high_half_sites),
        "method": "immediate == 0x1f80 or branch/call target inside 0x1f80xxxx",
    }


# --------------------------------------------------------------------------
# Overlay installation / drivers (mirrors the P18-03 pattern)
# --------------------------------------------------------------------------

def _install_composed_stack() -> None:
    """Re-assert the composed overlay stack on the frozen runtime module.

    P18-03's own drivers call p18c.install_overlay, which rewires the frozen
    module to the P18-03-only wrapper.  Re-asserting here keeps the P18-04 FIFO
    tap wired across those calls, and p18c.install_overlay is redirected to this
    function so a later P18-03 install cannot silently drop the tap.
    """
    p18b.side._generate_runtime = _wrapper_generate_runtime
    p18b.side._generate_harness = _wrapper_generate_harness
    p18b.side._parse_runtime_stdout = _wrapper_parse_runtime_stdout
    p18c.install_overlay = lambda enabled=True: _install_composed_stack()


def install_overlay(*, enabled: bool = True) -> None:
    """Compose and install the P18-02 + P18-03 + P18-04 overlay stack once.

    The three overlays must be applied in order to the *raw* frozen P17-06R
    source (each validates its own anchors and injects its own hooks); composing
    them in a single wrapper keeps every stage's fail-closed anchor checks live.
    """
    _OVERLAY_STATE["enabled"] = enabled
    _OVERLAY_STATE["installed"] = True
    _install_composed_stack()


def _wrapper_generate_runtime(analysis, ctx, recorded_frontier):
    """Apply the P18-02 GPU overlay, then the P18-03 causal overlay, then the
    P18-04 FIFO tap, in that order (each validates its own anchors)."""
    enabled = _OVERLAY_STATE["enabled"]
    base = _ORIGINALS["generate_runtime"](analysis, ctx, recorded_frontier)
    gpu_source = p18b.apply_runtime_overlay(base, enabled)
    causal_source = p18c.apply_causal_runtime_overlay(gpu_source, enabled)
    return apply_gpu_frontier_runtime_overlay(causal_source, enabled)


def _wrapper_generate_harness(ctx):
    enabled = _OVERLAY_STATE["enabled"]
    base = _ORIGINALS["generate_harness"](ctx)
    gpu_harness = p18b.apply_harness_overlay(base, enabled)
    causal_harness = p18c.apply_causal_harness_overlay(gpu_harness, enabled)
    return apply_gpu_frontier_harness_overlay(causal_harness, enabled)


def _wrapper_parse_runtime_stdout(text: str):
    fifo = _parse_fifo_lines(text)
    stripped = "\n".join(line for line in text.splitlines()
                          if not line.startswith("P18G_")) + "\n"
    result = p18c._wrapper_parse_runtime_stdout(stripped)
    result["p18g_fifo"] = fifo
    return result


def fixture_root() -> pathlib.Path:
    return p18c.fixture_root()


def continuation_analysis(*, title_analysis=None, fixture_dir=None):
    return p18c.continuation_analysis(title_analysis=title_analysis,
                                      fixture_dir=fixture_dir)


def run_continuation(generations_dir: pathlib.Path, analysis,
                     *, frontier_steps: int | None = None):
    install_overlay()
    result = p18c.run_continuation(generations_dir, analysis,
                                   frontier_steps=frontier_steps)
    # The P18-03 driver re-installs its own overlay; re-assert the composed
    # P18-02+P18-03+P18-04 stack so the FIFO tap stays wired for emit.
    _install_composed_stack()
    return result


def emit_continuation(run_dir: pathlib.Path, analysis,
                      *, frontier_steps: int | None = None):
    install_overlay()
    _install_composed_stack()
    result = p18c.emit_continuation(run_dir, analysis,
                                    frontier_steps=frontier_steps)
    _install_composed_stack()
    return result


P18_PRIVATE_BUILD_ROOT_ENV = "OPENRECOMP_P18_PRIVATE_BUILD_ROOT_04"
DEFAULT_P18_PRIVATE_BUILD_ROOT = ROOT.parents[1] / "private-build" / "phase18" / "P18-04"


def private_build_root() -> pathlib.Path:
    """P18-04's own private build root (env override honoured)."""
    override = os.environ.get(P18_PRIVATE_BUILD_ROOT_ENV)
    if override:
        return pathlib.Path(override)
    return DEFAULT_P18_PRIVATE_BUILD_ROOT


def official_run_dir(label: str) -> pathlib.Path:
    return p18c.official_run_dir(label)


if __name__ == "__main__":
    raise SystemExit(0)
