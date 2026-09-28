#!/usr/bin/env python3
"""OpenRecomp Phase-18 P18-03 causal device transcript V1.

P18-02 continued authentic guest execution past the GPUSTAT wait-poll using the
P18-01 minimum state-driven bit-26 model, and produced a device transcript whose
events carry an authenticated owning-instruction provenance digest.  P18-03
goes one step further and proves, mechanically, that every device event is
CAUSED by the current execution rather than replayed:

* it layers a second fail-closed overlay on top of the P18-02 overlay so the
  frozen P17-06R generated runtime emits, alongside every MMIO event, a causal
  device-state snapshot (store, address, width, value-as-produced, owning PC,
  and the GPU command-FIFO depth before/after the event);
* it binds every event to its decoded instruction by performing an independent
  fresh decode of the authenticated private source word at the event owner PC
  (frozen decoder + canonical checked-equality) and recording a fresh-decode
  digest that ties source SHA-256 -> file offset -> guest PC -> fresh decode
  without ever emitting the raw word or operand bytes;
* it classifies reached vs unreached device categories explicitly, so an
  unreached category is never silently treated as a valid no-op;
* it fails closed on any event without an authenticated owner, any causal
  snapshot count mismatch, any causal-log overflow, or any unverified decode.

The module reuses the frozen P17-06R emitter/runtime through the fail-closed
P18 overlay pattern already established by p18_exec_continuation_v1.py, and the
BIT-26 state model stays in force.  No title-specific constants are introduced
and no Phase-17 tree is modified.

The module promotes no proof marker: FIRST_FRAME_READY stays NO and the Phase-18
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

import p17_side_effects_exec_v1 as side  # noqa: E402
import p17_title_exec_emit_v1 as emitter  # noqa: E402
import p18_exec_continuation_v1 as p18c  # noqa: E402

STAGE = "P18-03"
NEXT_STAGE = "P18-04"

#: Causal device-state snapshot log capacity of the emitted runtime.
CAUSAL_LOG_CAP = 4096

#: The causal transcript document schema (distinct from the frozen P17 schema).
CAUSAL_SCHEMA = "openrecomp-phase18-causal-device-transcript-v1"

#: Anchors of the P18-02-overlaid runtime that the P18-03 overlay consumes.
ANCHOR_CAUSAL_INSERT = ("uint32_t or_p18_gpustat_log_value(uint32_t i) { return "
                        "(i < s_p18_gpustat_log_count) ? "
                        "s_p18_gpustat_log_value[i] : 0u; }\n")
WRITE_HOOK = "or_p18_mmio_write(_ef[0], _ef[1], _ef[3]);"
WRITE_HOOK_REPLACEMENT = "or_p18_causal_write(_ef[0], _ef[1], _ef[2], _ef[3], _ef[4]);"
READ_HOOK = " = or_p18_mmio_read(_addr);"
READ_HOOK_REPLACEMENT = " = or_p18_causal_read(_addr, _ef);"

#: Event categories recognised by P18-03.  VRAM mutation is not an MMIO class
#: (it is a consequence of GPU command execution, P18-04/P18-06 territory) and is
#: tracked here only so its not-reached status is explicit, never implicit.
CATEGORIES = (
    "BIOS_DISPATCH",
    "GPUSTAT_READ",
    "GP0_READ",
    "GP0_WRITE",
    "GP1_WRITE",
    "DMA_ACCESS",
    "OT_DMA_CHAIN_START",
    "INTERRUPT_ACCESS",
    "TIMER_ACCESS",
    "CDROM_ACCESS",
    "SPU_ACCESS",
    "PAD_ACCESS",
    "SIO_ACCESS",
    "MMIO_ACCESS",
    "VRAM_MUTATION",
)

#: Causal rules explaining how the device state produces each event's value.
CAUSAL_RULE_GPUSTAT_READ = "bit26 = (gpu_pending == 0); value = 0x04000000 iff idle"
CAUSAL_RULE_GPU_WRITE = "write enqueues one GPU command; gpu_pending increments (bounded)"
CAUSAL_RULE_UNMODELLED = "unmodelled device: zero-fill read / recorded-not-applied write"


class CausalTranscriptError(ValueError):
    """Fail-closed P18-03 rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def _sign16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


# --------------------------------------------------------------------------
# Emitted causal device-state snapshot block (inserted into the frozen runtime)
# --------------------------------------------------------------------------

_CAUSAL_C_BLOCK = r"""
/* --- P18-03: causal device-state snapshot log (no title constants) ------ */
#define OR_P18_CAUSAL_LOG_CAP @@CAUSAL_CAP@@u
static uint32_t s_p18_causal_count = 0u;
static uint32_t s_p18_causal_store[OR_P18_CAUSAL_LOG_CAP];
static uint32_t s_p18_causal_addr[OR_P18_CAUSAL_LOG_CAP];
static uint32_t s_p18_causal_width[OR_P18_CAUSAL_LOG_CAP];
static uint32_t s_p18_causal_value[OR_P18_CAUSAL_LOG_CAP];
static uint32_t s_p18_causal_owner[OR_P18_CAUSAL_LOG_CAP];
static uint32_t s_p18_causal_pending_before[OR_P18_CAUSAL_LOG_CAP];
static uint32_t s_p18_causal_pending_after[OR_P18_CAUSAL_LOG_CAP];
static uint32_t s_p18_causal_overflow = 0u;

static void or_p18_causal_record(uint32_t store, uint32_t addr, uint32_t width,
                                 uint32_t value, uint32_t owner,
                                 uint32_t pending_before, uint32_t pending_after) {
    if (s_p18_causal_count >= OR_P18_CAUSAL_LOG_CAP) { s_p18_causal_overflow = 1u; return; }
    s_p18_causal_store[s_p18_causal_count] = store;
    s_p18_causal_addr[s_p18_causal_count] = addr;
    s_p18_causal_width[s_p18_causal_count] = width;
    s_p18_causal_value[s_p18_causal_count] = value;
    s_p18_causal_owner[s_p18_causal_count] = owner;
    s_p18_causal_pending_before[s_p18_causal_count] = pending_before;
    s_p18_causal_pending_after[s_p18_causal_count] = pending_after;
    s_p18_causal_count++;
}

static uint32_t or_p18_causal_read(uint32_t addr, const uint32_t *ef) {
    uint32_t before = s_p18_gpu_pending;
    uint32_t value = or_p18_mmio_read(addr);
    uint32_t after = s_p18_gpu_pending;
    or_p18_causal_record(0u, addr, ef[2], value, ef[4], before, after);
    return value;
}

static void or_p18_causal_write(uint32_t store, uint32_t addr, uint32_t width,
                                uint32_t value, uint32_t owner) {
    uint32_t before = s_p18_gpu_pending;
    or_p18_mmio_write(store, addr, value);
    if (!store) return; /* read events are recorded by or_p18_causal_read */
    uint32_t after = s_p18_gpu_pending;
    or_p18_causal_record(store, addr, width, value, owner, before, after);
}

uint32_t or_p18_causal_log_count(void) { return s_p18_causal_count; }
uint32_t or_p18_causal_log_store(uint32_t i) { return (i < s_p18_causal_count) ? s_p18_causal_store[i] : 0u; }
uint32_t or_p18_causal_log_addr(uint32_t i) { return (i < s_p18_causal_count) ? s_p18_causal_addr[i] : 0u; }
uint32_t or_p18_causal_log_width(uint32_t i) { return (i < s_p18_causal_count) ? s_p18_causal_width[i] : 0u; }
uint32_t or_p18_causal_log_value(uint32_t i) { return (i < s_p18_causal_count) ? s_p18_causal_value[i] : 0u; }
uint32_t or_p18_causal_log_owner(uint32_t i) { return (i < s_p18_causal_count) ? s_p18_causal_owner[i] : 0u; }
uint32_t or_p18_causal_pending_before(uint32_t i) { return (i < s_p18_causal_count) ? s_p18_causal_pending_before[i] : 0u; }
uint32_t or_p18_causal_pending_after(uint32_t i) { return (i < s_p18_causal_count) ? s_p18_causal_pending_after[i] : 0u; }
uint32_t or_p18_causal_overflow(void) { return s_p18_causal_overflow; }
"""

_CAUSAL_DUMP = r"""
    {
        extern uint32_t or_p18_causal_log_count(void);
        extern uint32_t or_p18_causal_log_store(uint32_t i);
        extern uint32_t or_p18_causal_log_addr(uint32_t i);
        extern uint32_t or_p18_causal_log_width(uint32_t i);
        extern uint32_t or_p18_causal_log_value(uint32_t i);
        extern uint32_t or_p18_causal_log_owner(uint32_t i);
        extern uint32_t or_p18_causal_pending_before(uint32_t i);
        extern uint32_t or_p18_causal_pending_after(uint32_t i);
        extern uint32_t or_p18_causal_overflow(void);
        uint32_t _c18, _c18n = or_p18_causal_log_count();
        printf("P18C_CAUSAL_COUNT %u\n", (unsigned)_c18n);
        printf("P18C_CAUSAL_OVERFLOW %u\n", (unsigned)or_p18_causal_overflow());
        for (_c18 = 0u; _c18 < _c18n; _c18++) {
            printf("P18C_CAUSAL %u %u 0x%08x 0x%08x 0x%08x %u %u\n",
                   (unsigned)or_p18_causal_log_store(_c18),
                   (unsigned)or_p18_causal_log_width(_c18),
                   (unsigned)or_p18_causal_log_addr(_c18),
                   (unsigned)or_p18_causal_log_value(_c18),
                   (unsigned)or_p18_causal_log_owner(_c18),
                   (unsigned)or_p18_causal_pending_before(_c18),
                   (unsigned)or_p18_causal_pending_after(_c18));
        }
    }
"""


# --------------------------------------------------------------------------
# Fail-closed overlay installation
# --------------------------------------------------------------------------

_OVERLAY_STATE: dict[str, Any] = {"enabled": None}
_ORIGINALS: dict[str, Any] = {
    "generate_runtime": side._generate_runtime,
    "generate_harness": side._generate_harness,
    "parse_runtime_stdout": side._parse_runtime_stdout,
    "compiler_command": emitter._compiler_command,
}


def _count(text: str, needle: str) -> int:
    return text.count(needle)


def _validate_anchor(text: str, needle: str, name: str, minimum: int = 1) -> None:
    found = _count(text, needle)
    if found < minimum:
        raise CausalTranscriptError("OVERLAY_ANCHOR_MISSING", f"{name}={found}")
    if minimum == 1 and found != 1:
        raise CausalTranscriptError("OVERLAY_ANCHOR_DUPLICATED", f"{name}={found}")


def build_causal_source() -> str:
    return _CAUSAL_C_BLOCK.replace("@@CAUSAL_CAP@@", str(CAUSAL_LOG_CAP))


def apply_causal_runtime_overlay(runtime_source: str, enabled: bool) -> str:
    """Insert the causal snapshot log + hooks into the P18-02-overlaid runtime."""
    _validate_anchor(runtime_source, ANCHOR_CAUSAL_INSERT, "causal-insert")

    write_count = _count(runtime_source, WRITE_HOOK)
    if write_count < 2:
        raise CausalTranscriptError("OVERLAY_ANCHOR_MISSING", f"causal-write={write_count}")
    read_count = _count(runtime_source, READ_HOOK)
    if read_count < 2:
        raise CausalTranscriptError("OVERLAY_ANCHOR_MISSING", f"causal-read={read_count}")

    text = runtime_source.replace(
        ANCHOR_CAUSAL_INSERT, ANCHOR_CAUSAL_INSERT + build_causal_source(), 1)

    text = text.replace(WRITE_HOOK, WRITE_HOOK_REPLACEMENT)
    text = text.replace(READ_HOOK, READ_HOOK_REPLACEMENT)

    if WRITE_HOOK in text:
        raise CausalTranscriptError("OVERLAY_WRITE_HOOK_REMAINS")
    if READ_HOOK in text:
        raise CausalTranscriptError("OVERLAY_READ_HOOK_REMAINS")
    if "or_p18_causal_read(_addr, _ef)" not in text:
        raise CausalTranscriptError("OVERLAY_READ_HOOK_MISSING")
    if "or_p18_causal_write(_ef[0]" not in text:
        raise CausalTranscriptError("OVERLAY_WRITE_HOOK_MISSING")
    return text


def apply_causal_harness_overlay(harness_source: str, enabled: bool) -> str:
    """Insert the causal dump just before the harness END marker."""
    _validate_anchor(harness_source, p18c.ANCHOR_HARNESS_END, "harness-end")
    return harness_source.replace(p18c.ANCHOR_HARNESS_END,
                                  _CAUSAL_DUMP + p18c.ANCHOR_HARNESS_END, 1)


def _wrapper_generate_runtime(analysis, ctx, recorded_frontier):
    base = _ORIGINALS["generate_runtime"](analysis, ctx, recorded_frontier)
    gpu_source = p18c.apply_runtime_overlay(base, _OVERLAY_STATE["enabled"])
    return apply_causal_runtime_overlay(gpu_source, _OVERLAY_STATE["enabled"])


def _wrapper_generate_harness(ctx):
    base = _ORIGINALS["generate_harness"](ctx)
    gpu_harness = p18c.apply_harness_overlay(base, _OVERLAY_STATE["enabled"])
    return apply_causal_harness_overlay(gpu_harness, _OVERLAY_STATE["enabled"])


def _parse_causal_lines(text: str) -> dict[str, Any]:
    count = None
    overflow = 0
    snapshots: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.startswith("P18C_"):
            continue
        if line.startswith("P18C_CAUSAL_COUNT "):
            count = int(line.split(" ", 1)[1])
        elif line.startswith("P18C_CAUSAL_OVERFLOW "):
            overflow = int(line.split(" ", 1)[1])
        elif line.startswith("P18C_CAUSAL "):
            parts = line.split(" ")
            snapshots.append({
                "store": int(parts[1]),
                "width": int(parts[2]),
                "address": int(parts[3], 16),
                "value": int(parts[4], 16),
                "owner": int(parts[5], 16),
                "pending_before": int(parts[6]),
                "pending_after": int(parts[7]),
            })
    if count is None:
        raise CausalTranscriptError("CAUSAL_COUNT_MISSING")
    if count != len(snapshots):
        raise CausalTranscriptError("CAUSAL_COUNT_MISMATCH",
                                    f"reported={count} parsed={len(snapshots)}")
    return {"p18_causal_count": count, "p18_causal_overflow": overflow,
            "p18_causal_snapshots": snapshots}


def _wrapper_parse_runtime_stdout(text: str):
    causal = _parse_causal_lines(text)
    stripped = "\n".join(line for line in text.splitlines()
                         if not line.startswith("P18C_")) + "\n"
    result = p18c._wrapper_parse_runtime_stdout(stripped)
    result.update(causal)
    return result


def _wrapper_compiler_command(c_path, exe_path, extra_flags=()):
    flags = tuple(extra_flags) + ("-Wno-unused-function",)
    return _ORIGINALS["compiler_command"](c_path, exe_path, flags)


def install_overlay(enabled: bool) -> None:
    """Install (idempotently) the P18-03 causal overlay for a given mode."""
    side._generate_runtime = _wrapper_generate_runtime
    side._generate_harness = _wrapper_generate_harness
    side._parse_runtime_stdout = _wrapper_parse_runtime_stdout
    emitter._compiler_command = _wrapper_compiler_command
    _OVERLAY_STATE["enabled"] = enabled


def invalidate_overlay_for_tests() -> None:
    """Kept for the gate; installing is idempotent, so this is a no-op."""
    return None


# --------------------------------------------------------------------------
# Analysis / continuation drivers
# --------------------------------------------------------------------------

def fixture_root() -> pathlib.Path:
    return p18c.fixture_root()


def continuation_analysis(*, title_analysis=None, fixture_dir=None):
    return p18c.continuation_analysis(title_analysis=title_analysis,
                                      fixture_dir=fixture_dir)


def run_continuation(generations_dir: pathlib.Path, analysis,
                     *, enabled: bool = True, frontier_steps: int | None = None):
    install_overlay(enabled)
    if frontier_steps is None:
        frontier_steps = side.recorded_p17_05r_frontier_steps()
    generations_dir = pathlib.Path(generations_dir)
    generations_dir.mkdir(parents=True, exist_ok=True)
    return side.discover_continuation(analysis, generations_dir,
                                      frontier_steps=frontier_steps)


def emit_continuation(run_dir: pathlib.Path, analysis, *, enabled: bool = True,
                      frontier_steps: int | None = None):
    install_overlay(enabled)
    if frontier_steps is None:
        frontier_steps = side.recorded_p17_05r_frontier_steps()
    return side.emit_side_effects_executable(
        analysis, pathlib.Path(run_dir), frontier_steps=frontier_steps)


# --------------------------------------------------------------------------
# Fresh decode per event owner (word bound by digest, never emitted)
# --------------------------------------------------------------------------

def _provenance_source_sha(prov: Any) -> str:
    data = prov.asdict()
    source_sha = data.get("mainexe_file_sha256") or data.get("title_file_sha256")
    if not source_sha:
        raise CausalTranscriptError("PROVENANCE_SOURCE_SHA_MISSING",
                                    data.get("guest_pc", "?"))
    return source_sha


def fresh_decode_for_owner(analysis, pc: int) -> dict[str, Any]:
    """Independently fresh-decode the authenticated private word at pc.

    Returns public-safe decoded metadata plus a digest that binds the source
    chain (source SHA-256 -> file offset -> guest PC) to the fresh decode
    result, without emitting the raw word or operand bytes.
    """
    raw = analysis.records_by_address.get(pc)
    if raw is None:
        raise CausalTranscriptError("OWNER_NOT_AUTHENTICATED", hex32(pc))
    prov = analysis.provenance.get(pc)
    if prov is None:
        raise CausalTranscriptError("OWNER_WITHOUT_PROVENANCE", hex32(pc))
    word = analysis.read_authenticated_word(pc)
    fresh = emitter._fresh_decode_word(pc, word)

    ops = raw.get("operands") or {}
    raw_target = ops.get("target")
    expected_target = (int(raw_target) & emitter.MASK32) if raw_target is not None else None
    mismatches: list[str] = []
    if raw.get("op") != fresh["op"]:
        mismatches.append("op")
    if (int(ops.get("rs", 0)) & 0x1F) != fresh["rs"]:
        mismatches.append("rs")
    if (int(ops.get("rt", 0)) & 0x1F) != fresh["rt"]:
        mismatches.append("rt")
    if (int(ops.get("rd", 0)) & 0x1F) != fresh["rd"]:
        mismatches.append("rd")
    if (int(ops.get("shamt", 0)) & 0x1F) != fresh["shamt"]:
        mismatches.append("shamt")
    if _sign16(int(ops.get("imm", 0)) & 0xFFFF) != fresh["imm"]:
        mismatches.append("imm")
    if expected_target != fresh["target"]:
        mismatches.append("target")
    if bool(raw.get("control_flow")) != fresh["control_flow"]:
        mismatches.append("control_flow")
    if raw.get("terminator") != fresh["terminator"]:
        mismatches.append("terminator")
    if bool(raw.get("link")) != fresh["link"]:
        mismatches.append("link")
    if mismatches:
        raise CausalTranscriptError("FRESH_DECODE_MISMATCH",
                                    f"{hex32(pc)}:{','.join(mismatches)}")

    identity = prov.asdict()
    digest = _sha256_bytes(json.dumps({
        "guest_pc": identity.get("guest_pc"),
        "file_offset": identity.get("file_offset"),
        "payload_offset": identity.get("payload_offset"),
        "source_file_sha256": _provenance_source_sha(prov),
        "op": fresh["op"],
        "rs": fresh["rs"], "rt": fresh["rt"], "rd": fresh["rd"],
        "shamt": fresh["shamt"], "imm": fresh["imm"],
        "target": hex32(fresh["target"]) if fresh["target"] is not None else None,
        "control_flow": fresh["control_flow"],
        "terminator": fresh["terminator"],
        "link": fresh["link"],
    }, sort_keys=True).encode("utf-8"))

    return {
        "owner_pc": hex32(pc),
        "decoded_op": fresh["op"],
        "fresh_decode_verified": True,
        "fresh_decode_digest": digest,
    }


# --------------------------------------------------------------------------
# Causal transcript assembly
# --------------------------------------------------------------------------

def causal_state_for_event(event: dict[str, Any], snapshot: dict[str, Any]
                           ) -> dict[str, Any]:
    """Derive the relevant causal device state for one MMIO event."""
    class_name = event.get("class")
    if class_name == "GPUSTAT_READ":
        rule = CAUSAL_RULE_GPUSTAT_READ
    elif class_name in ("GP0_WRITE", "GP1_WRITE", "GP0_READ"):
        rule = CAUSAL_RULE_GPU_WRITE
    else:
        rule = CAUSAL_RULE_UNMODELLED
    if class_name in ("GPUSTAT_READ", "GP0_READ", "GP0_WRITE", "GP1_WRITE"):
        model = "P18_STATE_DRIVEN_BIT26"
    elif event.get("access") == "READ":
        model = "ZERO_FILL_RECORDED"
    else:
        model = "RECORDED_NOT_APPLIED"
    return {
        "model": model,
        "gpu_pending_before": snapshot["pending_before"],
        "gpu_pending_after": snapshot["pending_after"],
        "produced_value": hex32(snapshot["value"]),
        "causal_rule": rule,
    }


def build_causal_transcript(manifest: dict[str, Any], analysis,
                            provenance_map: dict[int, str]
                            ) -> tuple[dict[str, Any], str]:
    """Assemble + fail-closed validate the causal device transcript."""
    import p17_device_transcript_v1 as transcript_model
    rr = manifest["runtime_result"]
    snapshots = rr.get("p18_causal_snapshots")
    if not isinstance(snapshots, list):
        raise CausalTranscriptError("CAUSAL_SNAPSHOTS_MISSING")
    if rr.get("p18_causal_overflow"):
        raise CausalTranscriptError("CAUSAL_LOG_OVERFLOW")
    if provenance_map is None or analysis is None:
        raise CausalTranscriptError("PROVENANCE_MAP_REQUIRED")

    # Reuse the proven P18-02 rebuild (correct read model + provenance attach).
    base_doc, _base_sha = p18c.build_causal_transcript(manifest, provenance_map)

    events: list[dict[str, Any]] = []
    mmio_index = 0
    for raw in base_doc["events"]:
        event = dict(raw)
        owner = int(str(event["owning_instruction_pc"]), 16)
        if owner not in provenance_map:
            raise CausalTranscriptError("EVENT_WITHOUT_PROVENANCE", hex32(owner))
        fresh = fresh_decode_for_owner(analysis, owner)
        event["decoded_instruction"] = {
            "op": fresh["decoded_op"],
            "verified": fresh["fresh_decode_verified"],
            "fresh_decode_digest": fresh["fresh_decode_digest"],
        }
        if event["kind"] == "MMIO":
            if mmio_index >= len(snapshots):
                raise CausalTranscriptError("CAUSAL_SNAPSHOT_UNDERRUN", str(mmio_index))
            snapshot = snapshots[mmio_index]
            mmio_index += 1
            address = int(str(event["address"]), 16)
            store = 1 if event["access"] == "WRITE" else 0
            if snapshot["store"] != store:
                raise CausalTranscriptError("CAUSAL_STORE_MISMATCH", str(mmio_index))
            if snapshot["address"] != address:
                raise CausalTranscriptError("CAUSAL_ADDR_MISMATCH", str(mmio_index))
            if snapshot["width"] != int(event["width"]):
                raise CausalTranscriptError("CAUSAL_WIDTH_MISMATCH", str(mmio_index))
            if snapshot["owner"] != owner:
                raise CausalTranscriptError("CAUSAL_OWNER_MISMATCH", str(mmio_index))
            if store and snapshot["value"] != int(str(event["value"]), 16):
                raise CausalTranscriptError("CAUSAL_WRITE_VALUE_MISMATCH", str(mmio_index))
            # For reads the frozen dev_record records a stale 0u; the causal
            # snapshot is the value the guest actually consumed.
            if not store:
                event["value"] = hex32(snapshot["value"])
            event["causal_device_state"] = causal_state_for_event(event, snapshot)
        events.append(event)

    if mmio_index != len(snapshots):
        raise CausalTranscriptError("CAUSAL_SNAPSHOT_COUNT_MISMATCH",
                                    f"events={mmio_index} snapshots={len(snapshots)}")

    document = transcript_model.transcript_document(
        stage=STAGE, next_stage=NEXT_STAGE, events=events,
        bios_dispatch_count=int(rr["bios_dispatch_count"]),
        device_event_count=int(rr["device_event_count"]),
        continuation_entry_pc=int(str(rr["entry_pc"]), 16),
        stop_reason=rr["stop_reason"])
    document["gpustat_read_model"] = p18c.P18_GPUSTAT_READ_MODEL
    document["gpu_state_model"] = "STATE_DRIVEN_BIT26"
    document["causal_log_capacity"] = CAUSAL_LOG_CAP
    document["causal_snapshot_count"] = len(snapshots)
    document["schema"] = CAUSAL_SCHEMA
    validate_causal_transcript(document, provenance_map)
    data = transcript_model.canonical_bytes(document)
    return document, _sha256_bytes(data)


def validate_causal_transcript(document: dict[str, Any],
                                 provenance_map: dict[int, str]) -> None:
    """Fail-closed re-validation of a causal transcript document.

    The frozen P17-06R validator is the authority for provenance, sequence and
    class checks; the causal schema is a superset, so it is presented back to
    the frozen validator under its own schema name, then the causal-specific
    fields are checked here.
    """
    import p17_device_transcript_v1 as transcript_model
    if document.get("schema") != CAUSAL_SCHEMA:
        raise CausalTranscriptError("CAUSAL_SCHEMA_MISMATCH")
    clone = dict(document)
    clone["schema"] = transcript_model.SCHEMA_TRANSCRIPT
    transcript_model.validate_transcript(clone, provenance_map)
    for event in document["events"]:
        if "decoded_instruction" not in event:
            raise CausalTranscriptError("EVENT_DECODE_MISSING", str(event.get("sequence")))
        if event["kind"] == "MMIO" and "causal_device_state" not in event:
            raise CausalTranscriptError("EVENT_CAUSAL_STATE_MISSING", str(event.get("sequence")))
    if not isinstance(document.get("causal_snapshot_count"), int):
        raise CausalTranscriptError("CAUSAL_SNAPSHOT_COUNT_MISSING")


def transcript_bytes(document: dict[str, Any]) -> bytes:
    import p17_device_transcript_v1 as transcript_model
    return transcript_model.canonical_bytes(document)


def category_coverage(document: dict[str, Any]) -> dict[str, Any]:
    """Classify reached vs unreached device categories explicitly."""
    counts: dict[str, int] = {}
    for event in document["events"]:
        key = event["kind"] if event["kind"] == "BIOS_DISPATCH" else event["class"]
        counts[key] = counts.get(key, 0) + 1
    categories = []
    for name in CATEGORIES:
        reached = counts.get(name, 0) > 0
        categories.append({
            "category": name,
            "reached": reached,
            "event_count": counts.get(name, 0),
            "status": "REACHED" if reached else "NOT_REACHED",
        })
    return {
        "schema": "openrecomp-phase18-category-coverage-v1",
        "stage": STAGE,
        "total_events": len(document["events"]),
        "categories": categories,
        "reached": sorted(k for k, v in counts.items() if v > 0),
        "unreached": sorted(set(CATEGORIES) - set(counts)),
        "promotes_no_proof_marker": True,
    }


# --------------------------------------------------------------------------
# Source-level anti-hardcoding proof
# --------------------------------------------------------------------------

def source_discipline(generated_runtime: str) -> dict[str, Any]:
    """Prove from the generated source that the causal log is state-driven and
    title-free, and that the P18-02 bit-26 model remains in force."""
    causal_present = ("or_p18_causal_record" in generated_runtime
                      and "or_p18_causal_read(_addr, _ef)" in generated_runtime
                      and "or_p18_causal_write(_ef[0]" in generated_runtime)
    zero_model_absent = "0u; /* MMIO read model */" not in generated_runtime
    state_driven_present = ("s_p18_gpu_pending == 0u" in generated_runtime
                            and "or_p18_gpustat()" in generated_runtime)
    causal_function_pc_free = True
    for fn in ("or_p18_causal_read(uint32_t addr, const uint32_t *ef)",
               "or_p18_causal_write(uint32_t store, uint32_t addr",
               "or_p18_causal_record(uint32_t store, uint32_t addr"):
        marker = "static " + fn
        if marker in generated_runtime:
            body = generated_runtime.split(marker, 1)[1].split("}", 1)[0]
            if re.search(r"0x80[0-9a-f]{5}", body):
                causal_function_pc_free = False
    return {
        "causal_snapshot_log_present": causal_present,
        "zero_read_model_absent": zero_model_absent,
        "gpustat_state_driven_present": state_driven_present,
        "causal_functions_pc_free": causal_function_pc_free,
        "state_expression": "bit26 set iff s_p18_gpu_pending == 0",
    }


def overlay_anchor_selftest() -> dict[str, Any]:
    """Fail-closed anchor controls against synthetic P18-02-overlaid sources."""
    results: dict[str, Any] = {}
    synthetic_gpu = (p18c.ANCHOR_RUNTIME_INCLUDE + p18c.build_gpu_state_source(True)
                     + p18c.ANCHOR_LOOP_HEAD)
    synthetic = (synthetic_gpu
                 + "    or_p18_mmio_write(_ef[0], _ef[1], _ef[3]);\n"
                 + "    state->regs[7] = or_p18_mmio_read(_addr);\n"
                 + "    or_p18_mmio_write(_ef[0], _ef[1], _ef[3]);\n"
                 + "    state->regs[8] = or_p18_mmio_read(_addr);\n")
    applied = apply_causal_runtime_overlay(synthetic, True)
    results["valid_applies"] = ("or_p18_causal_record" in applied
                                and "or_p18_causal_read(_addr, _ef)" in applied
                                and "or_p18_causal_write(_ef[0]" in applied)
    try:
        apply_causal_runtime_overlay(
            synthetic.replace(ANCHOR_CAUSAL_INSERT, "", 1), True)
        results["missing_insert_rejected"] = False
    except CausalTranscriptError as err:
        results["missing_insert_rejected"] = err.code == "OVERLAY_ANCHOR_MISSING"
    try:
        apply_causal_runtime_overlay(
            synthetic_gpu + "    state->regs[7] = or_p18_mmio_read(_addr);\n"
            + "    state->regs[8] = or_p18_mmio_read(_addr);\n", True)
        results["missing_write_hook_rejected"] = False
    except CausalTranscriptError as err:
        results["missing_write_hook_rejected"] = err.code == "OVERLAY_ANCHOR_MISSING"
    try:
        apply_causal_harness_overlay("int main(void){return 0;}\n", True)
        results["missing_harness_end_rejected"] = False
    except CausalTranscriptError as err:
        results["missing_harness_end_rejected"] = err.code == "OVERLAY_ANCHOR_MISSING"
    results["ok"] = all(value for key, value in results.items() if key != "ok")
    return results


# --------------------------------------------------------------------------
# Private build root / official run labels
# --------------------------------------------------------------------------

P18_PRIVATE_BUILD_ROOT_ENV = "OPENRECOMP_P18_PRIVATE_BUILD_ROOT"
DEFAULT_P18_PRIVATE_BUILD_ROOT = ROOT.parents[1] / "private-build" / "phase18" / "P18-03"
OFFICIAL_RUN_LABELS = ("official-run-1", "official-run-2")


def private_build_root() -> pathlib.Path:
    override = os.environ.get(P18_PRIVATE_BUILD_ROOT_ENV)
    if override:
        return pathlib.Path(override)
    return DEFAULT_P18_PRIVATE_BUILD_ROOT


def official_run_dir(label: str) -> pathlib.Path:
    return private_build_root() / label


if __name__ == "__main__":
    raise SystemExit(0)
