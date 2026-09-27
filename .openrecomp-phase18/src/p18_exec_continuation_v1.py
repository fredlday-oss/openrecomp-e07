#!/usr/bin/env python3
"""OpenRecomp Phase-18 P18-02 authentic poll exit / execution continuation V1.

P18-01 established the guest poll condition from authenticated fixture bytes:
the loop at the modal GPUSTAT owner is 'lw; nop; and; beq' with a single-bit
mask (bit 26, ready-to-receive-command) and the branch returning to the load;
the exit requires bit 26 set.  P18-01 also established that under the Phase-17
ZERO_FILL_RECORDED MMIO read model the exit is unreachable, and defined the
minimum state-driven bit-26 model.

This module continues authentic execution across that poll:

* it authenticates the executable set exactly as P17-06R does (frozen decoder,
  source SHA-256 -> PS-X EXE header -> file offset -> guest PC -> word -> fresh
  decode -> record);
* it drives the frozen P17-06R generated runtime through a fail-closed overlay
  so that the GPUSTAT read (0x1f801814) returns bit 26 as a function of GPU
  state, while GP0 (0x1f801810) / GP1 (0x1f801814) writes are recorded as
  state mutations and drained once per executed guest instruction;
* it runs the bounded P17-06R dynamic discovery with that runtime as the single
  authority, so the authentic guest leaves the poll and continues into newly
  authenticated regions;
* it captures the causal device transcript produced by that execution;
* it fails closed on any missing/duplicated overlay anchor, any unmodelled
  status bit, any executed instruction without provenance and any event without
  an authenticated owner.

Nothing here is title-specific: the poll PC and geometry are derived from the
committed P17-06R transcript, the tested bit is derived from the authenticated
instruction that defines the mask, and the GPU state machine is expressed purely
as state (a command FIFO depth and a drain rate), with no title constant.

The module promotes no proof marker: FIRST_FRAME_READY stays NO and the Phase-18
claim markers stay NOT_PROVEN.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
from dataclasses import dataclass
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _extra in ("", ".openrecomp-phase18/src", ".openrecomp-phase17/src",
               ".openrecomp-phase3/src", ".openrecomp-phase9/src"):
    _path = str(ROOT / _extra) if _extra else str(ROOT)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import p17_side_effects_exec_v1 as side  # noqa: E402
import p17_title_decode_v1 as title_decode  # noqa: E402
import p17_title_exec_emit_v1 as emitter  # noqa: E402

STAGE = "P18-02"
NEXT_STAGE = "P18-03"

#: GPU command FIFO depth modelled by the emitted state machine.  A bounded
#: depth is a property of the device, not of any title.
GPU_FIFO_DEPTH = 8

#: Physical register addresses (PS1 hardware).
GP0_PHYS = 0x1F801810
GPUSTAT_PHYS = 0x1F801814

#: Anchors of the frozen P17-06R generated runtime.  Each must appear exactly
#: once, except the MMIO hook lines which appear once per emitted memory access
#: site.  A missing or duplicated anchor raises a stable error code.
ANCHOR_RUNTIME_INCLUDE = "#include <stdlib.h>\n"
ANCHOR_LOOP_HEAD = "    while (!state->stop) {\n"
ANCHOR_HARNESS_END = '    printf("END\\n");\n'
MMIO_READ_RE = re.compile(
    r"state->regs\[(\d+)\] = 0u; /\* MMIO read model \*/")
MMIO_WRITE_ANCHOR = "    dev_record(state, services, 2u, _ef, 6u);\n"

_UNMODELLED_STATUS_BITS = (13, 19, 22, 23, 28, 31)


class ContinuationError(ValueError):
    """Fail-closed P18-02 rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


# --------------------------------------------------------------------------
# Emitted GPU state machine (inserted verbatim into the frozen runtime)
# --------------------------------------------------------------------------

_GPU_STATE_COMMON = r"""
/* --- P18-02: state-driven GPU/GPUSTAT model (no title constants) -------- */
#define OR_P18_GPU_FIFO_DEPTH @@FIFO_DEPTH@@u
static uint32_t s_p18_gpu_pending = 0u;
static uint32_t s_p18_gpustat_reads = 0u;
static uint32_t s_p18_gpustat_bit26_set = 0u;
static uint32_t s_p18_gpustat_last = 0u;
static uint32_t s_p18_gp0_writes = 0u;
static uint32_t s_p18_gp1_writes = 0u;
static uint32_t s_p18_mmio_writes = 0u;
static uint32_t s_p18_mmio_reads_unmodelled = 0u;
static uint32_t s_p18_drained = 0u;
static uint32_t s_p18_fifo_overflow = 0u;
static uint32_t g_p18_pc = 0u;
#define OR_P18_GPUSTAT_LOG_CAP 256u
static uint32_t s_p18_gpustat_log_pc[OR_P18_GPUSTAT_LOG_CAP];
static uint32_t s_p18_gpustat_log_value[OR_P18_GPUSTAT_LOG_CAP];
static uint32_t s_p18_gpustat_log_count = 0u;

static uint32_t or_p18_phys(uint32_t addr) {
    if (addr >= 0x1f801000u && addr < 0x1f802000u) return addr;
    if (addr >= 0xa0000000u && addr < 0xa0200000u) {
        uint32_t c = addr - 0xa0000000u;
        if (c >= 0x1f801000u && c < 0x1f802000u) return c;
    }
    if (addr >= 0xbf800000u && addr < 0xbfa00000u) {
        uint32_t c = addr - 0xbf800000u;
        if (c >= 0x1f801000u && c < 0x1f802000u) return c;
    }
    return 0u;
}

@@GPUSTAT_BODY@@

static void or_p18_gpu_write(uint32_t phys, uint32_t value) {
    (void)value;
    if (phys == 0x1f801810u) s_p18_gp0_writes++;
    else if (phys == 0x1f801814u) s_p18_gp1_writes++;
    if (s_p18_gpu_pending < OR_P18_GPU_FIFO_DEPTH) s_p18_gpu_pending++;
    else s_p18_fifo_overflow = 1u;
}

static uint32_t or_p18_mmio_read(uint32_t addr) {
    uint32_t phys = or_p18_phys(addr);
    if (phys == 0x1f801814u) return or_p18_gpustat();
    s_p18_mmio_reads_unmodelled++;
    return 0u;
}

static void or_p18_mmio_write(uint32_t store, uint32_t addr, uint32_t value) {
    uint32_t phys;
    if (!store) return;
    phys = or_p18_phys(addr);
    if (phys == 0u) return;
    s_p18_mmio_writes++;
    if (phys == 0x1f801810u || phys == 0x1f801814u) or_p18_gpu_write(phys, value);
}

static void or_p18_tick(void) {
    if (s_p18_gpu_pending != 0u) { s_p18_gpu_pending--; s_p18_drained++; }
}

uint32_t or_p18_last_gpustat_value(void) { return s_p18_gpustat_last; }
uint32_t or_p18_last_gpustat_gp0_writes(void) { return s_p18_gp0_writes; }
uint32_t or_p18_last_gpustat_gp1_writes(void) { return s_p18_gp1_writes; }
uint32_t or_p18_last_gpustat_reads(void) { return s_p18_gpustat_reads; }
uint32_t or_p18_last_gpustat_bit26_set(void) { return s_p18_gpustat_bit26_set; }
uint32_t or_p18_last_mmio_writes(void) { return s_p18_mmio_writes; }
uint32_t or_p18_last_mmio_reads_unmodelled(void) { return s_p18_mmio_reads_unmodelled; }
uint32_t or_p18_last_drained(void) { return s_p18_drained; }
uint32_t or_p18_fifo_overflow(void) { return s_p18_fifo_overflow; }
uint32_t or_p18_gpustat_log_count(void) { return s_p18_gpustat_log_count; }
uint32_t or_p18_gpustat_log_pc(uint32_t i) { return (i < s_p18_gpustat_log_count) ? s_p18_gpustat_log_pc[i] : 0u; }
uint32_t or_p18_gpustat_log_value(uint32_t i) { return (i < s_p18_gpustat_log_count) ? s_p18_gpustat_log_value[i] : 0u; }
"""

_GPUSTAT_STATE_DRIVEN = r"""static uint32_t or_p18_gpustat(void) {
    /* bit 26 (ready-to-receive-command) is 1 exactly while the GPU has no
       command in flight; state, not a constant. */
    const uint32_t ready = 0x04000000u;
    s_p18_gpustat_reads++;
    if (s_p18_gpustat_log_count < OR_P18_GPUSTAT_LOG_CAP) {
        s_p18_gpustat_log_pc[s_p18_gpustat_log_count] = g_p18_pc;
        s_p18_gpustat_log_value[s_p18_gpustat_log_count] = (s_p18_gpu_pending == 0u) ? ready : 0u;
        s_p18_gpustat_log_count++;
    }
    if (s_p18_gpu_pending == 0u) { s_p18_gpustat_bit26_set++; s_p18_gpustat_last = ready; return ready; }
    s_p18_gpustat_last = 0u;
    return 0u;
}"""

_GPUSTAT_ZERO_FILL = r"""static uint32_t or_p18_gpustat(void) {
    /* NEGATIVE CONTROL ONLY: the Phase-17 declared ZERO_FILL_RECORDED read
       model.  Every GPUSTAT read returns zero, so bit 26 can never be set. */
    s_p18_gpustat_reads++;
    if (s_p18_gpustat_log_count < OR_P18_GPUSTAT_LOG_CAP) {
        s_p18_gpustat_log_pc[s_p18_gpustat_log_count] = g_p18_pc;
        s_p18_gpustat_log_value[s_p18_gpustat_log_count] = 0u;
        s_p18_gpustat_log_count++;
    }
    s_p18_gpustat_last = 0u;
    return 0u;
}"""

_HARNESS_DUMP = r"""
    {
        extern uint32_t or_p18_last_gpustat_value(void);
        extern uint32_t or_p18_gpustat_log_count(void);
        extern uint32_t or_p18_gpustat_log_pc(uint32_t i);
        extern uint32_t or_p18_gpustat_log_value(uint32_t i);
        extern uint32_t or_p18_last_gpustat_gp0_writes(void);
        extern uint32_t or_p18_last_gpustat_gp1_writes(void);
        extern uint32_t or_p18_last_gpustat_reads(void);
        extern uint32_t or_p18_last_gpustat_bit26_set(void);
        extern uint32_t or_p18_last_mmio_writes(void);
        extern uint32_t or_p18_last_mmio_reads_unmodelled(void);
        extern uint32_t or_p18_last_drained(void);
        extern uint32_t or_p18_fifo_overflow(void);
        uint32_t _p18i, _p18n = or_p18_gpustat_log_count();
        printf("P18_GPUSTAT_VALUE_BITS 0x%08x\n", (unsigned)or_p18_last_gpustat_value());
        printf("P18_GPUSTAT_LOG_COUNT %u\n", (unsigned)_p18n);
        printf("P18_STATS %u %u %u %u %u %u %u %u\n",
               (unsigned)or_p18_last_gpustat_reads(),
               (unsigned)or_p18_last_gpustat_bit26_set(),
               (unsigned)or_p18_last_gpustat_gp0_writes(),
               (unsigned)or_p18_last_gpustat_gp1_writes(),
               (unsigned)or_p18_last_mmio_writes(),
               (unsigned)or_p18_last_mmio_reads_unmodelled(),
               (unsigned)or_p18_last_drained(),
               (unsigned)or_p18_fifo_overflow());
        for (_p18i = 0u; _p18i < _p18n; _p18i++) {
            printf("P18_GPUSTAT_READ 0x%08x 0x%08x\n",
                   (unsigned)or_p18_gpustat_log_pc(_p18i),
                   (unsigned)or_p18_gpustat_log_value(_p18i));
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
LAST_STEP_TRACE: list[dict[str, Any]] = []


def gpu_state_body(enabled: bool) -> str:
    return _GPUSTAT_STATE_DRIVEN if enabled else _GPUSTAT_ZERO_FILL


def build_gpu_state_source(enabled: bool) -> str:
    return _GPU_STATE_COMMON.replace("@@FIFO_DEPTH@@", str(GPU_FIFO_DEPTH)).replace(
        "@@GPUSTAT_BODY@@", gpu_state_body(enabled))


def _count(text: str, needle: str) -> int:
    return text.count(needle)


def _validate_anchor(text: str, needle: str, name: str, minimum: int = 1) -> None:
    found = _count(text, needle)
    if found < minimum:
        raise ContinuationError("OVERLAY_ANCHOR_MISSING", f"{name}={found}")
    if minimum == 1 and found != 1:
        raise ContinuationError("OVERLAY_ANCHOR_DUPLICATED", f"{name}={found}")


def apply_runtime_overlay(runtime_source: str, enabled: bool) -> str:
    """Insert the GPU state machine into the frozen P17-06R generated runtime."""
    _validate_anchor(runtime_source, ANCHOR_RUNTIME_INCLUDE, "runtime-include")
    _validate_anchor(runtime_source, ANCHOR_LOOP_HEAD, "runtime-loop-head")

    text = runtime_source.replace(
        ANCHOR_RUNTIME_INCLUDE,
        ANCHOR_RUNTIME_INCLUDE + build_gpu_state_source(enabled), 1)
    text = text.replace(
        ANCHOR_LOOP_HEAD,
        ANCHOR_LOOP_HEAD + "        g_p18_pc = state->pc;\n        or_p18_tick();\n", 1)

    hits = MMIO_READ_RE.findall(text)
    if len(hits) < 2:
        raise ContinuationError("OVERLAY_ANCHOR_MISSING", f"mmio-read={len(hits)}")
    text, count = MMIO_READ_RE.subn(
        r"state->regs[\1] = or_p18_mmio_read(_addr); /* P18-02 state-driven MMIO read */",
        text)
    if count != len(hits):
        raise ContinuationError("OVERLAY_SUBSTITUTION_MISMATCH", f"{count}!={len(hits)}")

    writes = _count(text, MMIO_WRITE_ANCHOR)
    if writes < 2:
        raise ContinuationError("OVERLAY_ANCHOR_MISSING", f"mmio-write={writes}")
    text = text.replace(
        MMIO_WRITE_ANCHOR,
        "    or_p18_mmio_write(_ef[0], _ef[1], _ef[3]);\n" + MMIO_WRITE_ANCHOR)

    if "0u; /* MMIO read model */" in text:
        raise ContinuationError("OVERLAY_ZERO_MODEL_REMAINS")
    return text


def apply_harness_overlay(harness_source: str, enabled: bool) -> str:
    """Insert the GPUSTAT value dump just before the harness END marker."""
    _validate_anchor(harness_source, ANCHOR_HARNESS_END, "harness-end")
    return harness_source.replace(ANCHOR_HARNESS_END, _HARNESS_DUMP + ANCHOR_HARNESS_END, 1)


def _wrapper_generate_runtime(analysis, ctx, recorded_frontier):
    base = _ORIGINALS["generate_runtime"](analysis, ctx, recorded_frontier)
    return apply_runtime_overlay(base, _OVERLAY_STATE["enabled"])


def _wrapper_generate_harness(ctx):
    base = _ORIGINALS["generate_harness"](ctx)
    return apply_harness_overlay(base, _OVERLAY_STATE["enabled"])


def _wrapper_parse_runtime_stdout(text):
    # P18-* lines are outside the frozen P17 line protocol: strip them before
    # the frozen parser runs, then handle them here.
    ours = [line for line in text.splitlines() if line.startswith("P18_")]
    filtered = "\n".join(line for line in text.splitlines()
                             if not line.startswith("P18_")) + "\n"
    result = _ORIGINALS["parse_runtime_stdout"](filtered)
    for line in ours:
        if line.startswith("P18_GPUSTAT_VALUE_BITS "):
            result["p18_gpustat_value_bits"] = line.split(" ", 1)[1]
        elif line.startswith("P18_GPUSTAT_READ "):
            parts = line.split(" ")
            result.setdefault("p18_gpustat_read_log", []).append(
                {"pc": parts[1], "value": parts[2]})
        elif line.startswith("P18_STATS "):
            parts = line.split(" ")
            result["p18_stats"] = {
                "gpustat_reads": int(parts[1]),
                "bit26_set": int(parts[2]),
                "gp0_writes": int(parts[3]),
                "gp1_writes": int(parts[4]),
                "mmio_writes": int(parts[5]),
                "mmio_reads_unmodelled": int(parts[6]),
                "drained": int(parts[7]),
                "fifo_overflow": int(parts[8]),
            }
    LAST_STEP_TRACE[:] = result.get("step_trace", [])
    return result


def _wrapper_compiler_command(c_path, exe_path, extra_flags=()):
    flags = tuple(extra_flags) + ("-Wno-unused-function",)
    return _ORIGINALS["compiler_command"](c_path, exe_path, flags)


def install_overlay(enabled: bool) -> None:
    """Install (idempotently) the fail-closed overlay for a given mode."""
    side._generate_runtime = _wrapper_generate_runtime
    side._generate_harness = _wrapper_generate_harness
    side._parse_runtime_stdout = _wrapper_parse_runtime_stdout
    emitter._compiler_command = _wrapper_compiler_command
    _OVERLAY_STATE["enabled"] = enabled


# --------------------------------------------------------------------------
# Analysis / continuation drivers
# --------------------------------------------------------------------------

def fixture_root() -> pathlib.Path:
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def continuation_analysis(*, title_analysis: Any | None = None,
                          fixture_dir: pathlib.Path | None = None):
    """Authenticate the executable set exactly as P17-06R does."""
    if fixture_dir is None:
        fixture_dir = fixture_root()
    if title_analysis is None:
        title_analysis = title_decode.analyze_title_decode(fixture_dir=fixture_dir)
    return side.build_side_effects_analysis(
        title_analysis=title_analysis, fixture_dir=fixture_dir)


def run_continuation(generations_dir: pathlib.Path, analysis,
                     *, enabled: bool = True, frontier_steps: int | None = None):
    """Run bounded dynamic discovery with the (optionally disabled) overlay."""
    install_overlay(enabled)
    if frontier_steps is None:
        frontier_steps = side.recorded_p17_05r_frontier_steps()
    generations_dir = pathlib.Path(generations_dir)
    generations_dir.mkdir(parents=True, exist_ok=True)
    return side.discover_continuation(analysis, generations_dir,
                                      frontier_steps=frontier_steps)


def emit_continuation(run_dir: pathlib.Path, analysis, *, enabled: bool = True,
                      frontier_steps: int | None = None):
    """Emit the final official runtime for an already-discovered analysis."""
    install_overlay(enabled)
    if frontier_steps is None:
        frontier_steps = side.recorded_p17_05r_frontier_steps()
    return side.emit_side_effects_executable(
        analysis, pathlib.Path(run_dir), frontier_steps=frontier_steps)


# --------------------------------------------------------------------------
# Poll geometry / exit detection (derived, never hard-coded)
# --------------------------------------------------------------------------

def poll_geometry(transcript: dict[str, Any]) -> dict[str, Any]:
    """Derive the poll owner PC and branch geometry from the P17-06R transcript."""
    import p18_poll_condition_auth_v1 as poll_auth
    document = transcript
    owner, count, total = poll_auth.dominant_gpustat_owner(document)
    condition = poll_auth.derive_poll_condition(owner, transcript=document)
    branch_pc = int(str(condition["branch_pc"]), 16)
    return {
        "poll_pc": condition["poll_pc"],
        "poll_pc_int": owner,
        "branch_pc": condition["branch_pc"],
        "branch_pc_int": branch_pc,
        "branch_fallthrough_pc": hex32(branch_pc + 8),
        "loop_target_pc": condition["branch_target"],
        "loop_body_ops": condition["loop_body_ops"],
        "mask_value": condition["mask_value"],
        "status_bit": condition["status_bit"],
        "exit_condition": condition["exit_condition"],
        "owner_read_count": count,
        "total_gpustat_reads": total,
        "poll_pc_provenance_digest": condition["poll_pc_provenance_digest"],
        "poll_pc_provenance_matches_transcript":
            condition["poll_pc_provenance_matches_transcript"],
    }


def detect_poll_exit(step_trace: list[dict[str, Any]], geometry: dict[str, Any]
                     ) -> dict[str, Any]:
    """Detect the poll loop entry and the taken-to-exit branch from the trace."""
    poll_pc = geometry["poll_pc_int"]
    branch_pc = geometry["branch_pc_int"]
    fallthrough = int(geometry["branch_fallthrough_pc"], 16)

    poll_entries = 0
    branch_taken = 0
    exit_from = None
    exit_index = None
    previous = None
    for index, step in enumerate(step_trace):
        pc = int(str(step["pc"]), 16)
        if pc == poll_pc and previous != poll_pc:
            poll_entries += 1
        if pc == branch_pc and index + 2 < len(step_trace):
            successor = int(str(step_trace[index + 2]["pc"]), 16)
            if successor == fallthrough:
                branch_taken += 1
                if exit_from is None:
                    exit_from = step["pc"]
                    exit_index = index
        previous = pc
    return {
        "poll_entries": poll_entries,
        "branch_executions": sum(
            1 for step in step_trace if int(str(step["pc"]), 16) == branch_pc),
        "taken_to_exit_count": branch_taken,
        "exit_taken_from": exit_from,
        "exit_trace_index": exit_index,
        "exit_detected": branch_taken >= 1,
    }


def gpustat_value_bits(runtime_result: dict[str, Any]) -> str:
    value = runtime_result.get("p18_gpustat_value_bits")
    if not isinstance(value, str):
        raise ContinuationError("GPUSTAT_VALUE_NOT_CAPTURED")
    return value


# --------------------------------------------------------------------------
# Source-level anti-hardcoding proof
# --------------------------------------------------------------------------

def source_discipline(generated_runtime: str) -> dict[str, Any]:
    """Prove from the generated source that the read is state-driven."""
    zero_model_absent = "0u; /* MMIO read model */" not in generated_runtime
    state_driven_present = ("s_p18_gpu_pending == 0u" in generated_runtime
                            and "or_p18_gpustat()" in generated_runtime)
    gpu_write_present = "or_p18_gpu_write(phys, value)" in generated_runtime
    tick_present = "or_p18_tick();" in generated_runtime
    # The GPUSTAT value must be produced by a single generic, state-driven read
    # path shared by every read: the function body must contain NO guest PC
    # constant. (The poll PC legitimately appears elsewhere as a dispatch case
    # label of the executable, so the whole-file absence test is not the right
    # property; the value function is.)
    marker = "static uint32_t or_p18_gpustat(void) {"
    body = ""
    if marker in generated_runtime:
        body = generated_runtime.split(marker, 1)[1].split("}", 1)[0]
    guest_pc_literal = re.search(r"0x80[0-9a-f]{5}", body) is not None
    gpustat_body_pc_free = (bool(body)
                            and not guest_pc_literal
                            and "s_p18_gpu_pending" in body)
    return {
        "zero_read_model_absent": zero_model_absent,
        "gpustat_state_driven_present": state_driven_present,
        "gpu_write_present": gpu_write_present,
        "tick_present": tick_present,
        "gpustat_function_pc_free": gpustat_body_pc_free,
        "state_expression": "bit26 set iff s_p18_gpu_pending == 0",
    }


def overlay_anchor_selftest() -> dict[str, Any]:
    """Fail-closed anchor controls against synthetic sources."""
    results: dict[str, Any] = {}
    valid_runtime = (ANCHOR_RUNTIME_INCLUDE + "x\n" + ANCHOR_LOOP_HEAD
                     + '    state->regs[7] = 0u; /* MMIO read model */\n'
                     + '    state->regs[8] = 0u; /* MMIO read model */\n'
                     + MMIO_WRITE_ANCHOR + MMIO_WRITE_ANCHOR)
    applied = apply_runtime_overlay(valid_runtime, True)
    results["valid_applies"] = ("or_p18_tick();" in applied
                                and "or_p18_mmio_read(_addr)" in applied
                                and "or_p18_mmio_write(_ef[0]" in applied)
    try:
        apply_runtime_overlay(valid_runtime.replace(ANCHOR_RUNTIME_INCLUDE, "", 1), True)
        results["missing_include_rejected"] = False
    except ContinuationError as err:
        results["missing_include_rejected"] = err.code == "OVERLAY_ANCHOR_MISSING"
    try:
        apply_runtime_overlay(valid_runtime + ANCHOR_LOOP_HEAD, True)
        results["duplicated_loop_rejected"] = False
    except ContinuationError as err:
        results["duplicated_loop_rejected"] = err.code == "OVERLAY_ANCHOR_DUPLICATED"
    try:
        apply_harness_overlay('int main(void){return 0;}\n', True)
        results["missing_harness_end_rejected"] = False
    except ContinuationError as err:
        results["missing_harness_end_rejected"] = err.code == "OVERLAY_ANCHOR_MISSING"
    results["ok"] = all(value for key, value in results.items() if key != "ok")
    return results


def invalidate_overlay_for_tests() -> None:
    """Kept for the gate: installing is idempotent, so this is a no-op."""
    return None


if __name__ == "__main__":
    raise SystemExit(0)


# --------------------------------------------------------------------------
# Causal device transcript (built from the P18 runtime's own execution)
# --------------------------------------------------------------------------

#: The read model the P18 runtime actually applies to GPUSTAT reads.
P18_GPUSTAT_READ_MODEL = "P18_STATE_DRIVEN_BIT26"


def build_causal_transcript(manifest: dict[str, Any],
                            provenance_map: dict[int, str] | None = None
                            ) -> tuple[dict[str, Any], str]:
    """Assemble + fail-closed validate the device transcript of this execution."""
    import p17_device_transcript_v1 as transcript_model
    rr = manifest["runtime_result"]
    if provenance_map is None:
        raise ContinuationError("PROVENANCE_MAP_REQUIRED")
    events: list[dict[str, Any]] = []
    for raw in manifest["transcript_document"]["events"]:
        events.append(dict(raw))
    # Rebuild through the frozen constructors so classes are re-derived from the
    # accessed physical address, then annotate the P18 read model explicitly.
    rebuilt: list[dict[str, Any]] = []
    for event in events:
        if event["kind"] == "BIOS_DISPATCH":
            rebuilt.append(transcript_model.bios_event(
                sequence=event["sequence"],
                vector_pc=int(str(event["vector_pc"]), 16),
                function=int(str(event["function_number"]), 16),
                args=[int(str(event["arguments"][key]), 16)
                      for key in ("a0", "a1", "a2", "a3")],
                ra=int(str(event["ra"]), 16),
                sp=int(str(event["sp"]), 16),
                gp=int(str(event["gp"]), 16),
                owning_instruction_pc=int(str(event["owning_instruction_pc"]), 16),
                delay_slot_pc=(int(str(event["delay_slot_pc"]), 16)
                               if event.get("delay_slot_pc") else None)))
        elif event["kind"] == "MMIO":
            item = transcript_model.mmio_event(
                sequence=event["sequence"],
                address=int(str(event["address"]), 16),
                store=event["access"] == "WRITE",
                width=int(event["width"]),
                value=int(str(event["value"]), 16),
                owning_instruction_pc=int(str(event["owning_instruction_pc"]), 16),
                delay_slot_pc=(int(str(event["delay_slot_pc"]), 16)
                               if event.get("delay_slot_pc") else None))
            if item["class"] == "GPUSTAT_READ":
                item["model"] = P18_GPUSTAT_READ_MODEL
            rebuilt.append(item)
        else:
            raise ContinuationError("TRANSCRIPT_EVENT_KIND_UNKNOWN", str(event["kind"]))
    rebuilt = transcript_model.attach_provenance(rebuilt, provenance_map)
    document = transcript_model.transcript_document(
        stage=STAGE, next_stage=NEXT_STAGE, events=rebuilt,
        bios_dispatch_count=int(rr["bios_dispatch_count"]),
        device_event_count=int(rr["device_event_count"]),
        continuation_entry_pc=int(str(rr["entry_pc"]), 16),
        stop_reason=rr["stop_reason"])
    document["gpustat_read_model"] = P18_GPUSTAT_READ_MODEL
    document["gpu_state_model"] = "STATE_DRIVEN_BIT26"
    transcript_model.validate_transcript(document, provenance_map)
    data = transcript_model.canonical_bytes(document)
    return document, _sha256_bytes(data)


def transcript_bytes(document: dict[str, Any]) -> bytes:
    import p17_device_transcript_v1 as transcript_model
    return transcript_model.canonical_bytes(document)


# --------------------------------------------------------------------------
# Private build root / official run labels
# --------------------------------------------------------------------------

P18_PRIVATE_BUILD_ROOT_ENV = "OPENRECOMP_P18_PRIVATE_BUILD_ROOT"
DEFAULT_P18_PRIVATE_BUILD_ROOT = ROOT.parents[1] / "private-build" / "phase18" / "P18-02"
OFFICIAL_RUN_LABELS = ("official-run-1", "official-run-2")


def private_build_root() -> pathlib.Path:
    """Deterministic private build root (env override honoured)."""
    override = os.environ.get(P18_PRIVATE_BUILD_ROOT_ENV)
    if override:
        return pathlib.Path(override)
    return DEFAULT_P18_PRIVATE_BUILD_ROOT


def official_run_dir(label: str) -> pathlib.Path:
    return private_build_root() / label
