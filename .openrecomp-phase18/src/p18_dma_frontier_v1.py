#!/usr/bin/env python3
"""OpenRecomp Phase-18 P18-05 DMA / ordering-table frontier V1.

P18-04 established that the authentic continuation reaches GPUSTAT reads and
BIOS dispatch - and zero GP0/GP1 writes.  P18-05 asks the DMA question
mechanically: *is* any DMA-channel or ordering-table activity reachable, and if
so, what does it decode to?

The module does three things, none of them title-specific and none of them
fabricating traffic:

1. It proves from the generated runtime source that a genuine DMA-window tap
   exists, gated on exactly 0x1f801080..0x1f8010ff and reduced through the same
   shared physical-address reducer the GPU path uses, so an "unreached" result
   is a genuine frontier state, not a missing implementation.
2. It installs a fourth additive overlay that records every access the device
   model actually receives in the DMA window (physical register, store flag,
   width, opaque value digest, owner PC) and reports every DMA channel as
   explicitly NOT_REACHED when none occurred - never as a silent no-op.
3. It decodes reached DMA register values (channel, MADR/BCR/CHCR, direction,
   sync mode) and exposes a bounded ordering-table traversal model with
   alignment, cycle and depth checks.

Nothing here weakens the P18-02/P18-03/P18-04 overlays; P18-05 only adds taps
and decoding.  The module promotes no proof marker: FIRST_FRAME_READY stays NO
and the Phase-18 claim markers stay NOT_PROVEN.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import sys
from typing import Any, Callable

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _extra in ("", ".openrecomp-phase18/src", ".openrecomp-phase17/src",
               ".openrecomp-phase3/src", ".openrecomp-phase9/src"):
    _path = str(ROOT / _extra) if _extra else str(ROOT)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import p18_exec_continuation_v1 as p18b  # noqa: E402
import p18_causal_transcript_v1 as p18c  # noqa: E402
import p18_gpu_command_frontier_v1 as p18g  # noqa: E402

STAGE = "P18-05"
NEXT_STAGE = "P18-06"

#: PS1 DMA register window (eight 0x10-byte channels).
DMA_WINDOW_START = 0x1F801080
DMA_WINDOW_END = 0x1F8010FF
DMA_CHANNEL_STRIDE = 0x10
DMA_CHANNEL_COUNT = 8

CHANNEL_NAMES = {
    0: "MDEC_IN", 1: "MDEC_OUT", 2: "GPU", 3: "CDROM",
    4: "SPU", 5: "PIO", 6: "OTC", 7: "UNUSED",
}

REGISTER_NAMES = {0x0: "MADR", 0x4: "BCR", 0x8: "CHCR", 0xC: "UNUSED"}

CHCR_DIRECTION_FROM_RAM = 0x1
CHCR_STEP_DECREMENT = 0x2
CHCR_CHOPPING = 0x100
CHCR_SYNC_SHIFT = 16
CHCR_SYNC_MASK = 0x7
CHCR_START = 0x01000000
CHCR_TRIGGER = 0x10000000

SYNC_NAMES = {0: "manual", 1: "request", 2: "linked_list", 3: "reserved"}

#: Ordering-table linked-list encoding: the node header word carries the next
#: node address in bits 2..20 and the command count in bits 24..31; bit 23 set
#: terminates the list.  The words following the header are the GPU commands.
END_OF_LIST_BIT = 0x800000
NEXT_ADDR_MASK = 0x1FFFFC
HEADER_COUNT_SHIFT = 24
HEADER_COUNT_MASK = 0xFF
OT_MAX_NODES = 512
OT_MAX_COMMANDS = 4096

#: Line prefix of the P18-05 generated-runtime DMA tap.
DMA_PREFIX = "P18D_"


class DmaFrontierError(ValueError):
    """Fail-closed P18-05 rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def _dma_phys(addr: int) -> int:
    """Reduce a KUSEG/KSEG0/KSEG1 address to its DMA physical register."""
    candidate = addr & 0x1FFFFFFF
    if DMA_WINDOW_START <= candidate <= DMA_WINDOW_END:
        return candidate
    raise DmaFrontierError("DMA_ADDRESS_NOT_IN_WINDOW", hex32(addr))


def channel_of(phys: int) -> int:
    return (phys - DMA_WINDOW_START) // DMA_CHANNEL_STRIDE


def channel_name(index: int) -> str:
    return CHANNEL_NAMES.get(index, "UNKNOWN")


def register_of(phys: int) -> str:
    offset = (phys - DMA_WINDOW_START) % DMA_CHANNEL_STRIDE
    if offset not in REGISTER_NAMES:
        raise DmaFrontierError("DMA_REGISTER_UNKNOWN", hex32(phys))
    return REGISTER_NAMES[offset]


def decode_chcr(value: int) -> dict[str, Any]:
    """Decode a CHCR word (fail-closed on the reserved sync mode)."""
    word = value & 0xFFFFFFFF
    sync = (word >> CHCR_SYNC_SHIFT) & CHCR_SYNC_MASK
    if sync == 3:
        raise DmaFrontierError("DMA_SYNC_MODE_UNSUPPORTED", hex32(word))
    return {
        "direction": "from_ram" if word & CHCR_DIRECTION_FROM_RAM else "to_ram",
        "step": "decrement" if word & CHCR_STEP_DECREMENT else "increment",
        "chopping": bool(word & CHCR_CHOPPING),
        "chop_size": (word >> 9) & 0x3,
        "sync_mode": sync,
        "sync_name": SYNC_NAMES[sync],
        "start": bool(word & CHCR_START),
        "trigger": bool(word & CHCR_TRIGGER),
    }


def decode_register(channel: int, register: str, value: int, *, store: bool
                    ) -> dict[str, Any]:
    """Decode one DMA register access into public-safe fields."""
    word = value & 0xFFFFFFFF
    entry: dict[str, Any] = {"channel": channel,
                             "channel_name": channel_name(channel),
                             "register": register}
    if register == "MADR":
        if store and (word & 0x3):
            raise DmaFrontierError("DMA_MADR_UNALIGNED", hex32(word))
        entry["madr"] = hex32(word)
    elif register == "BCR":
        entry["block_size"] = word & 0xFFFF
        entry["block_count"] = (word >> 16) & 0xFFFF
    elif register == "CHCR":
        entry.update(decode_chcr(word))
    elif register == "UNUSED":
        entry["reserved"] = True
    return entry


def traverse_ordering_table(reader: Callable[[int], int], start: int, *,
                            max_nodes: int = OT_MAX_NODES) -> dict[str, Any]:
    """Bounded, alignment-checked, cycle-checked ordering-table traversal.

    The node word encodes the next pointer (bits 2..20) and the end-of-list bit
    (23).  Each node's first word is classified with the P18-04 GP0 classifier
    so an unknown command surfaces as UNKNOWN rather than being swallowed.
    """
    if start & 0x3:
        raise DmaFrontierError("OT_NODE_UNALIGNED", hex32(start))
    if start == 0:
        raise DmaFrontierError("OT_START_INVALID", hex32(start))
    visited: set[int] = set()
    nodes: list[dict[str, Any]] = []
    address = start
    command_total = 0
    unsupported_total = 0
    while True:
        if address in visited:
            raise DmaFrontierError("OT_CYCLE_DETECTED", hex32(address))
        if address & 0x3:
            raise DmaFrontierError("OT_NODE_UNALIGNED", hex32(address))
        if len(nodes) >= max_nodes:
            raise DmaFrontierError("OT_TRAVERSAL_BOUND_EXCEEDED", str(max_nodes))
        visited.add(address)
        header = reader(address) & 0xFFFFFFFF
        count = (header >> HEADER_COUNT_SHIFT) & HEADER_COUNT_MASK
        terminated = bool(header & END_OF_LIST_BIT)
        if command_total + count > OT_MAX_COMMANDS:
            raise DmaFrontierError("OT_COMMAND_BOUND_EXCEEDED", str(OT_MAX_COMMANDS))
        commands: list[dict[str, Any]] = []
        for index in range(count):
            command_address = address + 4 * (index + 1)
            if command_address & 0x3:
                raise DmaFrontierError("OT_NODE_UNALIGNED", hex32(command_address))
            word = reader(command_address) & 0xFFFFFFFF
            classification = p18g.classify_gp0_command(word)
            commands.append({
                "index": index,
                "command_byte": classification["command_byte"],
                "class": classification["class"],
                "unsupported": classification["unsupported"],
                "word_digest": _sha256_bytes(word.to_bytes(4, "little")),
            })
        unsupported_total += sum(1 for c in commands if c["unsupported"])
        nodes.append({
            "index": len(nodes),
            "address": hex32(address),
            "command_count": count,
            "commands": commands,
            "terminated": terminated,
            "header_digest": _sha256_bytes(header.to_bytes(4, "little")),
        })
        command_total += count
        if terminated:
            break
        address = header & NEXT_ADDR_MASK
    return {
        "start": hex32(start),
        "node_count": len(nodes),
        "nodes": nodes,
        "command_count": command_total,
        "termination": "END_OF_LIST_BIT",
        "bounded_by": max_nodes,
        "unsupported_command_count": unsupported_total,
    }


class DmaFrontierTap:
    """Pure-Python model of the per-access DMA tap.

    The real tap lives in the generated C runtime; this model exists so the
    decoder, the channel/register reduction and the unreached rule can be
    positive- and negative-tested without emitting a runtime.  Both share the
    same register map.
    """

    def __init__(self) -> None:
        self.accesses: list[dict[str, Any]] = []

    def record_access(self, addr: int, *, store: bool, width: int, value: int,
                      owner_pc: int) -> dict[str, Any]:
        phys = _dma_phys(addr)
        channel = channel_of(phys)
        register = register_of(phys)
        word = value & 0xFFFFFFFF
        entry: dict[str, Any] = {
            "sequence": len(self.accesses),
            "channel": channel,
            "channel_name": channel_name(channel),
            "register": register,
            "physical_address": hex32(phys),
            "access": "WRITE" if store else "READ",
            "width": width,
            "value_digest": _sha256_bytes(word.to_bytes(4, "little")),
            "owner_pc": hex32(owner_pc),
        }
        entry.update(decode_register(channel, register, word, store=store))
        self.accesses.append(entry)
        return entry


def dma_window_unreached(opened: bool, address: int) -> bool:
    """True only when the DMA window is genuinely unopened."""
    if opened:
        return False
    _dma_phys(address)
    return True


# --------------------------------------------------------------------------
# Generated-runtime tap (fourth additive overlay on P18-02/03/04)
# --------------------------------------------------------------------------

_G_DMA_BLOCK = r"""
/* --- P18-05: DMA-window access tap (no title constants) ---------------- */
#define OR_P18D_CAP 65536u
static uint32_t s_p18d_count = 0u;
static uint32_t s_p18d_store[OR_P18D_CAP];
static uint32_t s_p18d_addr[OR_P18D_CAP];
static uint32_t s_p18d_width[OR_P18D_CAP];
static uint32_t s_p18d_value[OR_P18D_CAP];
static uint32_t s_p18d_owner[OR_P18D_CAP];
static uint32_t s_p18d_overflow = 0u;
static uint32_t s_p18d_dma_total = 0u;

static void or_p18d_dma_record(uint32_t store, uint32_t addr, uint32_t width, uint32_t value, uint32_t owner) {
    uint32_t phys = or_p18_phys(addr);
    if (phys < 0x1f801080u || phys > 0x1f8010ffu) return;
    if (s_p18d_count >= OR_P18D_CAP) { s_p18d_overflow = 1u; return; }
    s_p18d_store[s_p18d_count] = store;
    s_p18d_addr[s_p18d_count] = addr;
    s_p18d_width[s_p18d_count] = width;
    s_p18d_value[s_p18d_count] = value;
    s_p18d_owner[s_p18d_count] = owner;
    s_p18d_count++;
    s_p18d_dma_total++;
}

static uint32_t or_p18_dma_read(uint32_t addr, const uint32_t *ef) {
    uint32_t value = or_p18_causal_read(addr, ef);
    or_p18d_dma_record(0u, addr, ef[2], value, ef[4]);
    return value;
}

static void or_p18_dma_write(uint32_t store, uint32_t addr, uint32_t width, uint32_t value, uint32_t owner) {
    or_p18_causal_write(store, addr, width, value, owner);
    or_p18d_dma_record(store, addr, width, value, owner);
}

uint32_t or_p18d_count(void) { return s_p18d_count; }
uint32_t or_p18d_store(uint32_t i) { return (i < s_p18d_count) ? s_p18d_store[i] : 0u; }
uint32_t or_p18d_addr(uint32_t i) { return (i < s_p18d_count) ? s_p18d_addr[i] : 0u; }
uint32_t or_p18d_width(uint32_t i) { return (i < s_p18d_count) ? s_p18d_width[i] : 0u; }
uint32_t or_p18d_value(uint32_t i) { return (i < s_p18d_count) ? s_p18d_value[i] : 0u; }
uint32_t or_p18d_owner(uint32_t i) { return (i < s_p18d_count) ? s_p18d_owner[i] : 0u; }
uint32_t or_p18d_overflow(void) { return s_p18d_overflow; }
uint32_t or_p18d_dma_total(void) { return s_p18d_dma_total; }
"""

_G_DMA_DUMP = r"""
    {
        extern uint32_t or_p18d_count(void);
        extern uint32_t or_p18d_store(uint32_t i);
        extern uint32_t or_p18d_addr(uint32_t i);
        extern uint32_t or_p18d_width(uint32_t i);
        extern uint32_t or_p18d_value(uint32_t i);
        extern uint32_t or_p18d_owner(uint32_t i);
        extern uint32_t or_p18d_overflow(void);
        extern uint32_t or_p18d_dma_total(void);
        uint32_t _d18, _d18n = or_p18d_count();
        printf("P18D_COUNT %u\n", (unsigned)_d18n);
        printf("P18D_OVERFLOW %u\n", (unsigned)or_p18d_overflow());
        printf("P18D_DMA_TOTAL %u\n", (unsigned)or_p18d_dma_total());
        for (_d18 = 0u; _d18 < _d18n; _d18++) {
            printf("P18D_DMA %u %u 0x%08x 0x%08x 0x%08x\n",
                   (unsigned)or_p18d_store(_d18),
                   (unsigned)or_p18d_width(_d18),
                   (unsigned)or_p18d_addr(_d18),
                   (unsigned)or_p18d_value(_d18),
                   (unsigned)or_p18d_owner(_d18));
        }
    }
"""

#: End of the P18-03 causal block: the P18-05 tap is inserted after it so the
#: DMA wrappers may reference the causal wrappers defined above them.
G_INSERT_ANCHOR = ("uint32_t or_p18_causal_overflow(void) { return "
                   "s_p18_causal_overflow; }\n")

G_READ_HOOK = "or_p18_causal_read(_addr, _ef)"
G_READ_HOOK_REPLACEMENT = "or_p18_dma_read(_addr, _ef)"
G_WRITE_HOOK = "or_p18_causal_write(_ef[0], _ef[1], _ef[2], _ef[3], _ef[4])"
G_WRITE_HOOK_REPLACEMENT = "or_p18_dma_write(_ef[0], _ef[1], _ef[2], _ef[3], _ef[4])"

#: The exact physical-address gate the DMA tap applies.
DMA_WINDOW_GATE = "if (phys < 0x1f801080u || phys > 0x1f8010ffu) return;"

_OVERLAY_STATE: dict[str, Any] = {"installed": False, "enabled": True}
_ORIGINALS: dict[str, Any] = {
    "generate_runtime": p18g._wrapper_generate_runtime,
    "generate_harness": p18g._wrapper_generate_harness,
    "parse_runtime_stdout": p18g._wrapper_parse_runtime_stdout,
}


def _count(text: str, needle: str) -> int:
    return text.count(needle)


def build_dma_source() -> str:
    return _G_DMA_BLOCK


def apply_dma_runtime_overlay(runtime_source: str, enabled: bool) -> str:
    """Insert the DMA-window tap into a P18-04-overlaid runtime.

    Additive only: the P18-02/03/04 paths are preserved; the DMA wrappers call
    through to the causal wrappers and add a window-gated record.  A missing or
    duplicated anchor fails closed.
    """
    if _count(runtime_source, G_INSERT_ANCHOR) != 1:
        raise DmaFrontierError("OVERLAY_ANCHOR_MISSING",
                               f"dma-insert={_count(runtime_source, G_INSERT_ANCHOR)}")
    read_hooks = _count(runtime_source, G_READ_HOOK)
    write_hooks = _count(runtime_source, G_WRITE_HOOK)
    if read_hooks < 1:
        raise DmaFrontierError("OVERLAY_ANCHOR_MISSING", f"dma-read-hook={read_hooks}")
    if write_hooks < 1:
        raise DmaFrontierError("OVERLAY_ANCHOR_MISSING", f"dma-write-hook={write_hooks}")
    if "or_p18d_dma_record(uint32_t store" in runtime_source:
        raise DmaFrontierError("OVERLAY_TAP_ALREADY_PRESENT")

    text = runtime_source.replace(G_READ_HOOK, G_READ_HOOK_REPLACEMENT)
    text = text.replace(G_WRITE_HOOK, G_WRITE_HOOK_REPLACEMENT)
    text = text.replace(G_INSERT_ANCHOR, G_INSERT_ANCHOR + build_dma_source(), 1)

    if G_READ_HOOK in text:
        raise DmaFrontierError("OVERLAY_READ_HOOK_REMAINS")
    if G_WRITE_HOOK in text:
        raise DmaFrontierError("OVERLAY_WRITE_HOOK_REMAINS")
    if "or_p18_dma_read(_addr, _ef)" not in text:
        raise DmaFrontierError("OVERLAY_READ_HOOK_MISSING")
    if "or_p18_dma_write(_ef[0]" not in text:
        raise DmaFrontierError("OVERLAY_WRITE_HOOK_MISSING")
    if DMA_WINDOW_GATE not in text:
        raise DmaFrontierError("OVERLAY_DMA_GATE_MISSING")
    if "or_p18_causal_read(addr, ef)" not in text:
        raise DmaFrontierError("OVERLAY_CAUSAL_READ_DELEGATION_MISSING")
    return text


def apply_dma_harness_overlay(harness_source: str, enabled: bool) -> str:
    """Insert the DMA dump just before the P17-06R harness END marker."""
    anchor = p18b.ANCHOR_HARNESS_END
    if _count(harness_source, anchor) != 1:
        raise DmaFrontierError("OVERLAY_ANCHOR_MISSING", "harness-end")
    return harness_source.replace(anchor, _G_DMA_DUMP + anchor, 1)


def overlay_anchor_selftest() -> dict[str, Any]:
    """Fail-closed anchor controls against a synthetic P18-04-overlaid source."""
    results: dict[str, Any] = {}
    synthetic = (p18b.ANCHOR_RUNTIME_INCLUDE + p18b.build_gpu_state_source(True)
                 + p18c.build_causal_source()
                 + p18b.ANCHOR_LOOP_HEAD
                 + "    state->regs[7] = or_p18_causal_read(_addr, _ef);\n"
                 + "    or_p18_causal_write(_ef[0], _ef[1], _ef[2], _ef[3], _ef[4]);\n")
    applied = apply_dma_runtime_overlay(synthetic, True)
    results["valid_applies"] = ("or_p18_dma_read(_addr, _ef)" in applied
                                and "or_p18_dma_write(_ef[0]" in applied
                                and DMA_WINDOW_GATE in applied)
    try:
        apply_dma_runtime_overlay(
            synthetic.replace(G_INSERT_ANCHOR, "", 1), True)
        results["missing_insert_rejected"] = False
    except DmaFrontierError as err:
        results["missing_insert_rejected"] = err.code == "OVERLAY_ANCHOR_MISSING"
    try:
        apply_dma_runtime_overlay(
            synthetic.replace(G_READ_HOOK, "or_p18_mmio_read(_addr)"), True)
        results["missing_read_hook_rejected"] = False
    except DmaFrontierError as err:
        results["missing_read_hook_rejected"] = err.code == "OVERLAY_ANCHOR_MISSING"
    try:
        apply_dma_harness_overlay("int main(void){return 0;}\n", True)
        results["missing_harness_end_rejected"] = False
    except DmaFrontierError as err:
        results["missing_harness_end_rejected"] = err.code == "OVERLAY_ANCHOR_MISSING"
    results["ok"] = all(value for key, value in results.items() if key != "ok")
    return results


# --------------------------------------------------------------------------
# Parse the generated runtime DMA tap back into a public-safe frontier
# --------------------------------------------------------------------------

def _parse_dma_lines(text: str) -> dict[str, Any]:
    count = None
    overflow = 0
    dma_total = 0
    entries: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.startswith(DMA_PREFIX):
            continue
        if line.startswith("P18D_COUNT "):
            count = int(line.split(" ", 1)[1])
        elif line.startswith("P18D_OVERFLOW "):
            overflow = int(line.split(" ", 1)[1])
        elif line.startswith("P18D_DMA_TOTAL "):
            dma_total = int(line.split(" ", 1)[1])
        elif line.startswith("P18D_DMA "):
            parts = line.split(" ")
            entries.append({
                "sequence": len(entries),
                "store": int(parts[1]),
                "width": int(parts[2]),
                "address": int(parts[3], 16),
                "value": int(parts[4], 16),
                "owner_pc": int(parts[5], 16),
            })
    if count is None:
        raise DmaFrontierError("DMA_COUNT_MISSING")
    if overflow:
        raise DmaFrontierError("DMA_LOG_OVERFLOW")
    if count != len(entries):
        raise DmaFrontierError("DMA_COUNT_MISMATCH",
                               f"reported={count} parsed={len(entries)}")
    if count != dma_total:
        raise DmaFrontierError("DMA_TOTAL_MISMATCH",
                               f"count={count} total={dma_total}")
    return {"dma_count": count, "dma_total": dma_total, "entries": entries}


def dma_path_discipline(generated_source: str) -> dict[str, Any]:
    """Prove from the generated source that the DMA window tap is real.

    This is the load-bearing evidence for a DMA FRONTIER NOT YET REACHED
    verdict: the device model genuinely contains a DMA-window tap, gated on
    exactly 0x1f801080..0x1f8010ff and reduced through the shared
    physical-address reducer, with the access-site hooks rewired, and the record
    function free of any guest-PC constant.
    """
    gate = _count(generated_source, DMA_WINDOW_GATE)
    start_literal = _count(generated_source, "0x1f801080u")
    end_literal = _count(generated_source, "0x1f8010ffu")
    record_def = ("static void or_p18d_dma_record(uint32_t store, uint32_t addr, "
                  "uint32_t width, uint32_t value, uint32_t owner) {")
    record_present = record_def in generated_source
    body = ""
    if record_present:
        body = generated_source.split(record_def, 1)[1].split("}", 1)[0]
    pc_free = re.search(r"0x80[0-9a-f]{5}", body) is None
    reducer = _count(generated_source, "static uint32_t or_p18_phys(uint32_t addr) {") == 1
    read_hook = "or_p18_dma_read(_addr, _ef)" in generated_source
    write_hook = "or_p18_dma_write(_ef[0]" in generated_source
    return {
        "dma_window_tap_present": bool(gate == 1 and record_present and pc_free
                                       and reducer and read_hook and write_hook),
        "window_gate_count": gate,
        "window_start_literal_count": start_literal,
        "window_end_literal_count": end_literal,
        "dma_record_function_pc_free": pc_free,
        "shared_phys_reducer_present": reducer,
        "read_hook_present": read_hook,
        "write_hook_present": write_hook,
        "gate_expression": "phys in [0x1f801080,0x1f8010ff] -> or_p18d_dma_record",
    }


def dma_window_materialisation(analysis, reached_pcs: list[int]) -> dict[str, Any]:
    """Conservative, title-free check: is the DMA window materialised?

    Over the authenticated records of the reached set we look for any
    instruction that materialises the hardware-register high half (0x1f80) as an
    immediate, or any branch/call target inside the DMA window.  Finding none is
    necessary but not sufficient for "unreached"; it is combined with the
    runtime evidence (zero recorded DMA accesses).
    """
    reachable = set(reached_pcs)
    sites: list[str] = []
    for pc, record in sorted(analysis.records_by_address.items()):
        if pc not in reachable:
            continue
        operands = record.get("operands") or {}
        immediate = operands.get("imm")
        if immediate is not None and (int(immediate) & 0xFFFF) == 0x1F80:
            sites.append(hex32(pc))
        target = operands.get("target")
        if target is not None:
            value = int(target) & 0xFFFFFFFF
            if DMA_WINDOW_START <= value <= DMA_WINDOW_END:
                sites.append(hex32(pc))
    return {
        "reached_pc_count": len(reachable),
        "records_examined": len(analysis.records_by_address),
        "window_high_half_sites": sites,
        "window_high_half_site_count": len(sites),
        "method": ("immediate == 0x1f80 or branch/call target inside "
                   "0x1f801080..0x1f8010ff"),
    }


def _register_from_phys(phys: int) -> str:
    return register_of(phys)


def build_dma_frontier(runtime_result: dict[str, Any], generated_source: str,
                       provenance_map: dict[int, str]
                       ) -> tuple[dict[str, Any], str]:
    """Assemble + fail-closed validate the DMA frontier document."""
    dma = runtime_result.get("p18d_dma")
    if not isinstance(dma, dict):
        raise DmaFrontierError("DMA_RESULT_MISSING")
    path = dma_path_discipline(generated_source)
    if not path["dma_window_tap_present"]:
        raise DmaFrontierError("DMA_TAP_ABSENT")

    events: list[dict[str, Any]] = []
    reached_channels: set[int] = set()
    for entry in dma["entries"]:
        phys = _dma_phys(entry["address"])
        channel = channel_of(phys)
        register = _register_from_phys(phys)
        owner = entry["owner_pc"]
        if owner not in provenance_map:
            raise DmaFrontierError("EVENT_WITHOUT_PROVENANCE", hex32(owner))
        word = entry["value"] & 0xFFFFFFFF
        event: dict[str, Any] = {
            "sequence": entry["sequence"],
            "channel": channel,
            "channel_name": channel_name(channel),
            "register": register,
            "physical_address": hex32(phys),
            "access": "WRITE" if entry["store"] else "READ",
            "width": entry["width"],
            "owner_pc": hex32(owner),
            "owner_provenance_digest": provenance_map[owner],
            "value_digest": _sha256_bytes(word.to_bytes(4, "little")),
        }
        event.update(decode_register(channel, register, word,
                                     store=bool(entry["store"])))
        events.append(event)
        reached_channels.add(channel)

    reached = bool(events)
    channels = [
        {"index": index, "name": channel_name(index),
         "status": "REACHED" if index in reached_channels else "NOT_REACHED"}
        for index in range(DMA_CHANNEL_COUNT)
    ]
    document: dict[str, Any] = {
        "schema": "openrecomp-phase18-dma-frontier-v1",
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "dma_access_count": dma["dma_total"],
        "dma_reached": reached,
        "reached_channels": sorted(reached_channels),
        "channels": channels,
        "write_path": path,
        "events": events,
        "promotes_no_proof_marker": True,
    }
    if not reached:
        document["dma_status"] = "NOT_REACHED"
        document["explicit_not_reached"] = True
    validate_dma_frontier(document, provenance_map)
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return document, _sha256_bytes(data)


def validate_dma_frontier(document: dict[str, Any],
                          provenance_map: dict[int, str]) -> None:
    """Fail-closed re-validation of the DMA frontier document."""
    if document.get("schema") != "openrecomp-phase18-dma-frontier-v1":
        raise DmaFrontierError("DMA_FRONTIER_SCHEMA_MISMATCH")
    events = document.get("events")
    if not isinstance(events, list):
        raise DmaFrontierError("DMA_FRONTIER_EVENTS_MISSING")
    digests = set(provenance_map.values())
    for event in events:
        phys = int(str(event["physical_address"]), 16)
        if not DMA_WINDOW_START <= phys <= DMA_WINDOW_END:
            raise DmaFrontierError("DMA_FRONTIER_ADDRESS_INVALID",
                                   event["physical_address"])
        if event.get("owner_provenance_digest") not in digests:
            raise DmaFrontierError("EVENT_WITHOUT_PROVENANCE",
                                   event.get("owner_pc", "?"))
        if "value_digest" not in event:
            raise DmaFrontierError("EVENT_VALUE_DIGEST_MISSING")
        if "register" not in event or "channel" not in event:
            raise DmaFrontierError("EVENT_REGISTER_MISSING")
    channels = document.get("channels")
    if not isinstance(channels, list) or len(channels) != DMA_CHANNEL_COUNT:
        raise DmaFrontierError("DMA_CHANNELS_MISSING")
    if not events and document.get("dma_status") != "NOT_REACHED":
        raise DmaFrontierError("UNREACHED_STATUS_MISSING")
    if events and document.get("dma_status") == "NOT_REACHED":
        raise DmaFrontierError("REACHED_MARKED_UNREACHED")


def frontier_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


# --------------------------------------------------------------------------
# Overlay installation / drivers (mirrors the P18-04 pattern)
# --------------------------------------------------------------------------

def _install_composed_stack() -> None:
    """Re-assert the composed P18-02+03+04+05 overlay stack on the runtime.

    Each inner overlay wrapper reads its own module-level enabled flag, so every
    layer's flag must be set here (a missing flag fails closed with KeyError,
    which the gate reports as an unhandled exception and never as PASS).
    """
    enabled = _OVERLAY_STATE["enabled"]
    p18b._OVERLAY_STATE["enabled"] = enabled
    p18c._OVERLAY_STATE["enabled"] = enabled
    p18g._OVERLAY_STATE["enabled"] = enabled
    p18g._OVERLAY_STATE["installed"] = True
    p18b.side._generate_runtime = _wrapper_generate_runtime
    p18b.side._generate_harness = _wrapper_generate_harness
    p18b.side._parse_runtime_stdout = _wrapper_parse_runtime_stdout
    p18c.install_overlay = lambda enabled=True: _install_composed_stack()
    p18g.install_overlay = lambda *, enabled=True: _install_composed_stack()


def install_overlay(*, enabled: bool = True) -> None:
    """Compose and install the four-overlay stack once."""
    _OVERLAY_STATE["enabled"] = enabled
    _OVERLAY_STATE["installed"] = True
    _install_composed_stack()


def _wrapper_generate_runtime(analysis, ctx, recorded_frontier):
    base = _ORIGINALS["generate_runtime"](analysis, ctx, recorded_frontier)
    return apply_dma_runtime_overlay(base, _OVERLAY_STATE["enabled"])


def _wrapper_generate_harness(ctx):
    base = _ORIGINALS["generate_harness"](ctx)
    return apply_dma_harness_overlay(base, _OVERLAY_STATE["enabled"])


def _wrapper_parse_runtime_stdout(text: str):
    dma = _parse_dma_lines(text)
    stripped = "\n".join(line for line in text.splitlines()
                         if not line.startswith(DMA_PREFIX)) + "\n"
    result = _ORIGINALS["parse_runtime_stdout"](stripped)
    result["p18d_dma"] = dma
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


P18_PRIVATE_BUILD_ROOT_ENV = "OPENRECOMP_P18_PRIVATE_BUILD_ROOT_05"
DEFAULT_P18_PRIVATE_BUILD_ROOT = (ROOT.parents[1] / "private-build" / "phase18"
                                  / "P18-05")


def private_build_root() -> pathlib.Path:
    override = os.environ.get(P18_PRIVATE_BUILD_ROOT_ENV)
    if override:
        return pathlib.Path(override)
    return DEFAULT_P18_PRIVATE_BUILD_ROOT


def official_run_dir(label: str) -> pathlib.Path:
    return private_build_root() / label


if __name__ == "__main__":
    raise SystemExit(0)
