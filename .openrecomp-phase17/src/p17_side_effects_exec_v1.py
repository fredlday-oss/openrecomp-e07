#!/usr/bin/env python3
"""OpenRecomp Phase-17 P17-06R live BIOS/Exec and device side-effect frontier.

P17-05R executed 78 authentic instructions and stopped with
PC_NOT_IN_AUTHENTICATED_TABLE at 0x80026cc8.  This module:

* derives the P17-06R continuation entry from the recorded P17-05R frontier (it
  is never hard-coded),
* authenticates every newly reached region directly from the read-only private
  source bytes (SLUS_005.29 / TITLE payload) with the same frozen decoder and
  the same canonical checked-equality discipline as P17-04R/P17-05R
  (source SHA-256 -> PS-X EXE header -> file offset -> guest PC -> word ->
  fresh decode -> execution record),
* discovers the dynamic frontier with the emitted native runtime itself (the
  runtime is the single authority; no Python replica is used as evidence),
  extending the authenticated table one newly reached region at a time,
* captures a deterministic, provenance-complete transcript of the BIOS/device
  side effects that authentic execution actually produces,
* fails closed on any unauthenticated address, unverified word, unsupported
  semantic, unmapped address, non-reproduced P17-05R frontier or device event
  without provenance.

BIOS dispatch is modelled only as an envelope (record + return transfer to RA);
BIOS internals are explicitly NOT modelled and every event records that.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _extra in ("", ".openrecomp-phase17/src", ".openrecomp-phase3/src",
               ".openrecomp-phase9/src"):
    _path = str(ROOT / _extra) if _extra else str(ROOT)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import p17_device_transcript_v1 as transcript_model
import p17_mainexe_auth_v1 as mainexe_auth
import p17_title_decode_v1 as title_decode
import p17_title_exec_continuation_v1 as cont
import p17_title_exec_emit_v1 as emitter
import p3_code_frontier_v1 as frontier_engine

STAGE = "P17-06R"
NEXT_STAGE = "P17-07R"

#: Execution bound: additional authenticated guest instructions past the
#: recorded P17-05R frontier.
CONTINUATION_BUDGET = 8192
#: Discovery is bounded and deterministic; a run that keeps producing new
#: unauthenticated frontiers stops after this many emissions.
MAX_DISCOVERY_ROUNDS = 12
#: Transcript / trace capacities of the emitted runtime.
EVENT_CAP = 65536
BIOS_DISPATCH_LIMIT = 1048576
DEVICE_EVENT_LIMIT = 65536
POST_ENTRY_CAP = 64
TRACE_CAP = 262144

DEFAULT_PRIVATE_BUILD_ROOT = pathlib.Path("/home/fred/OpenRecomp/private-build/phase17/P17-06R")
PRIVATE_BUILD_ROOT_ENV = emitter.PRIVATE_BUILD_ROOT_ENV
OFFICIAL_RUN_DIRS = ("official-run-1", "official-run-2")

#: Recorded P17-05R evidence (authoritative for the continuation entry).
P17_05R_RESULT = ROOT / ".openrecomp-phase17/evidence/P17-05R/RESULT.json"

PERSISTED_ARTIFACTS = (
    ("generated_source", "or_side_effects_v1.c"),
    ("generated_header", "or_side_effects_v1.h"),
    ("generated_harness", "or_side_effects_harness_v1.c"),
    ("private_mapping", "private_mapping.json"),
    ("build_metadata", "build_metadata.json"),
    ("shared_object", "or_side_effects_v1.so"),
    ("executable", "or_side_effects_v1"),
)

ALLOWED_STOP_REASONS = frozenset({
    "PC_NOT_IN_AUTHENTICATED_TABLE",
    "STEP_LIMIT_REACHED",
    "CONTINUATION_BUDGET_REACHED",
    "UNSUPPORTED_OPERATION",
    "SIGNED_OVERFLOW",
    "UNALIGNED_OR_OUT_OF_BOUNDS_MEMORY_ACCESS",
    "OUT_OF_BOUNDS_MEMORY_ACCESS",
    "DIVIDE_BY_ZERO",
    "MISSING_DELAY_SLOT",
    "UNSUPPORTED_DELAY_SLOT_CONTROL_FLOW",
    "JUMP_WITHOUT_TARGET",
    "BRANCH_WITHOUT_TARGET",
    "BIOS_DISPATCH_LIMIT_REACHED",
    "DEVICE_EVENT_LIMIT_REACHED",
})

#: Operations reached by the authentic continuation that are not part of the
#: P17-05R implemented vocabulary.  They are implemented with exact R3000A
#: semantics (see the emitted runtime) and reported separately from the
#: P17-05R vocabulary so the implemented/exercised split stays honest.
ADDITIONAL_OPS = frozenset({
    "lwl", "lwr", "swl", "swr", "div", "divu", "mthi", "mtlo", "add", "sub",
})

SIDE_SUPPORTED_OPS = frozenset(set(emitter.SUPPORTED_OPS) | set(ADDITIONAL_OPS))

UNAUTHENTICATABLE_CODES = frozenset({
    "CONTINUATION_ENTRY_UNALIGNED",
    "CONTINUATION_ENTRY_OUTSIDE_AUTHENTICATED_TEXT",
    "CONTINUATION_ENTRY_UNDECODABLE",
})

MEMORY_OPS = ("lw", "lh", "lhu", "lb", "lbu", "sw", "sh", "sb",
              "lwl", "lwr", "swl", "swr")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: pathlib.Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def _parse_hex(value: Any) -> int:
    if isinstance(value, int):
        return value
    return int(str(value), 16)


class SideEffectsError(ValueError):
    """Fail-closed P17-06R rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def private_build_root() -> pathlib.Path:
    override = os.environ.get(PRIVATE_BUILD_ROOT_ENV)
    if override:
        return pathlib.Path(override)
    return DEFAULT_PRIVATE_BUILD_ROOT


def official_run_dir(label: str, root: pathlib.Path | None = None) -> pathlib.Path:
    base = root if root is not None else private_build_root()
    return base / label


def recorded_p17_05r_frontier(path: pathlib.Path | None = None) -> dict[str, Any]:
    """Load and validate the recorded P17-05R frontier from committed evidence."""
    source = path if path is not None else P17_05R_RESULT
    if not source.is_file():
        raise SideEffectsError("P17_05R_EVIDENCE_MISSING", source.name)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SideEffectsError("P17_05R_EVIDENCE_MALFORMED") from exc
    if document.get("stage") != "P17-05R" or document.get("status") != "PASS":
        raise SideEffectsError("P17_05R_EVIDENCE_NOT_ACCEPTED")
    frontier = document.get("authentic_frontier")
    if not isinstance(frontier, dict):
        raise SideEffectsError("P17_05R_FRONTIER_MISSING")
    for key in ("last_successfully_executed_pc", "attempted_frontier_pc", "frontier_pc",
                "stop_reason"):
        if key not in frontier:
            raise SideEffectsError("P17_05R_FRONTIER_FIELD_MISSING", key)
    if frontier["stop_reason"] != "PC_NOT_IN_AUTHENTICATED_TABLE":
        raise SideEffectsError("P17_05R_FRONTIER_NOT_TABLE_GAP", str(frontier["stop_reason"]))
    entry = _parse_hex(frontier["attempted_frontier_pc"])
    last = _parse_hex(frontier["last_successfully_executed_pc"])
    if entry == last:
        raise SideEffectsError("P17_05R_FRONTIER_NOT_ADVANCING",
                               f"entry={_hex32(entry)} last={_hex32(last)}")
    return frontier


# --------------------------------------------------------------------------
# Merged authenticated record set across TITLE + newly reached main-EXE regions
# --------------------------------------------------------------------------


@dataclass
class SideEffectsAnalysis:
    """Authenticated record set for the P17-06R continuation.

    The base is the P17-05R merged analysis: the TITLE reachable set plus the
    main-EXE records reachable from 0x80011af0.  The merged dictionaries include
    every newly reached region authenticated in this stage.
    """

    base: cont.ContinuationAnalysis
    recorded_frontier: dict[str, Any]
    records_by_address: dict[int, dict[str, Any]] = field(default_factory=dict)
    delay_by_owner: dict[int, int] = field(default_factory=dict)
    provenance: dict[int, Any] = field(default_factory=dict)
    reachable: set[int] = field(default_factory=set)
    region_log: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(cls, base: cont.ContinuationAnalysis,
               recorded_frontier: dict[str, Any]) -> "SideEffectsAnalysis":
        # The authenticated executable set is exactly the set of reachable PCs
        # for which a provenance record was established (TITLE projection plus
        # the main-EXE records reachable from the recorded P17-04R entry).
        return cls(
            base=base,
            recorded_frontier=recorded_frontier,
            records_by_address=dict(base.records_by_address),
            delay_by_owner=dict(base.delay_by_owner),
            provenance=dict(base.provenance),
            reachable=set(base.provenance),
        )

    # -- region geometry ---------------------------------------------------
    @property
    def title_text_addr(self) -> int:
        return self.base.title.identity.t_addr

    @property
    def title_text_end(self) -> int:
        return self.base.title.identity.text_end

    @property
    def mainexe_text_addr(self) -> int:
        return self.base.mainexe.identity.t_addr

    @property
    def mainexe_text_end(self) -> int:
        return self.base.mainexe.identity.t_addr + self.base.mainexe.identity.t_size

    @property
    def continuation_entry_pc(self) -> int:
        return self.base.continuation_entry_pc

    @property
    def identity(self) -> Any:
        return self.base.title.identity

    @property
    def projection(self) -> dict[str, Any]:
        return self.base.title.projection

    @property
    def frontier(self) -> dict[str, Any]:
        return {"reachable_addresses": sorted(self.reachable)}

    @property
    def record_count(self) -> int:
        return len(self.reachable)

    def region_of(self, pc: int) -> str:
        if self.title_text_addr <= pc < self.title_text_end:
            return "TITLE"
        if self.mainexe_text_addr <= pc < self.mainexe_text_end:
            return "MAIN_EXE"
        return "OUTSIDE"

    def read_authenticated_word(self, pc: int) -> int:
        return self.base.read_authenticated_word(pc)

    @property
    def title_record_count(self) -> int:
        return sum(1 for pc in self.reachable if self.region_of(pc) == "TITLE")

    @property
    def mainexe_record_count(self) -> int:
        return sum(1 for pc in self.reachable if self.region_of(pc) == "MAIN_EXE")

    # -- authentication ----------------------------------------------------
    def authenticate_and_extend(self, pc: int) -> dict[str, Any]:
        """Authenticate the region newly reached at pc and merge its records."""
        if pc & 3:
            raise SideEffectsError("CONTINUATION_ENTRY_UNALIGNED", _hex32(pc))
        region = self.region_of(pc)
        if region == "OUTSIDE":
            raise SideEffectsError("CONTINUATION_ENTRY_OUTSIDE_AUTHENTICATED_TEXT", _hex32(pc))
        before = len(self.reachable)
        if region == "MAIN_EXE":
            analysis = mainexe_auth.build_mainexe_analysis(
                pc,
                identity=self.base.mainexe.identity,
                file_bytes=self.base.mainexe.file_bytes or None,
            )
            records = analysis.records_by_address
            delay = analysis.delay_by_owner
            provenance = analysis.provenance
            file_offset = mainexe_auth.guest_to_file_offset(self.base.mainexe.identity, pc)
        else:
            records, delay, provenance = self._analyze_title_region(pc)
            file_offset = self._title_file_offset(pc)
        # Authenticated executable records: the region reachable set that
        # carries a provenance entry; every record is re-verified against a
        # fresh decode from the same source bytes before emission.
        added_pcs: list[int] = []
        for candidate in sorted(provenance):
            if candidate in self.reachable:
                continue
            if candidate not in records:
                raise SideEffectsError("NEW_REGION_RECORD_MISSING", _hex32(candidate))
            self.reachable.add(candidate)
            self.records_by_address.setdefault(candidate, records[candidate])
            added_pcs.append(candidate)
        for candidate, raw in records.items():
            self.records_by_address.setdefault(candidate, raw)
        for owner, delay_pc in delay.items():
            self.delay_by_owner.setdefault(owner, delay_pc)
        for candidate, prov in provenance.items():
            self.provenance.setdefault(candidate, prov)
        missing = [p for p in added_pcs if p not in self.provenance]
        if missing:
            raise SideEffectsError("NEW_REGION_PROVENANCE_MISSING", _hex32(missing[0]))
        for owner, delay_pc in self.delay_by_owner.items():
            if delay_pc not in self.reachable:
                raise SideEffectsError("DELAY_SLOT_RECORD_MISSING",
                                       f"owner={_hex32(owner)} delay={_hex32(delay_pc)}")
        entry = {
            "entry_pc": _hex32(pc),
            "region": region,
            "entry_file_offset": file_offset,
            "added_records": len(added_pcs),
            "records_before": before,
            "records_after": len(self.reachable),
            "region_reachable_count": len(provenance),
        }
        self.region_log.append(entry)
        return {"added": len(added_pcs), "added_pcs": added_pcs, "region": region,
                "entry_pc": pc, "entry_file_offset": file_offset}

    def _title_file_offset(self, pc: int) -> int:
        return self._title_file_offset_base() + (pc - self.title_text_addr)

    def _title_file_offset_base(self) -> int:
        for candidate in sorted(self.base.title.provenance):
            prov = self.base.title.provenance[candidate]
            return prov.file_offset - prov.payload_offset
        raise SideEffectsError("TITLE_PROVENANCE_EMPTY")

    def _analyze_title_region(self, entry: int) -> tuple[dict, dict, dict]:
        payload = self.base.title.identity.payload
        start = self.title_text_addr
        end = self.title_text_end

        def read_word(address: int) -> int:
            offset = address - start
            if offset < 0 or offset + 4 > len(payload):
                raise SideEffectsError("TITLE_WORD_OUT_OF_RANGE", _hex32(address))
            return struct.unpack_from("<I", payload, offset)[0]

        result = frontier_engine.analyze(read_word, start, end, entry)
        reachable = set(result["reachable_addresses"])
        records = {record["address"]: record for record in result["records"]
                   if record["address"] in reachable}
        delay = {item["owner"]: item["delay"] for item in result["delay_slots"]}
        file_base = self._title_file_offset_base()
        first = sorted(self.base.title.provenance)[0]
        sample = self.base.title.provenance[first]
        provenance: dict[int, Any] = {}
        for pc in sorted(records):
            provenance[pc] = title_decode.SourceProvenance(
                guest_pc=pc,
                payload_offset=pc - start,
                file_offset=file_base + (pc - start),
                title_file_sha256=sample.title_file_sha256,
                title_payload_sha256=sample.title_payload_sha256,
            )
        return records, delay, provenance


def build_side_effects_analysis(*, title_analysis: Any | None = None,
                                fixture_dir: pathlib.Path | None = None,
                                recorded_frontier: dict[str, Any] | None = None
                                ) -> SideEffectsAnalysis:
    """Build the P17-06R merged analysis (P17-05R set + derived entry)."""
    if recorded_frontier is None:
        recorded_frontier = recorded_p17_05r_frontier()
    if title_analysis is None:
        title_analysis = title_decode.analyze_title_decode(fixture_dir=fixture_dir)
    base = cont.build_continuation_analysis(
        title_analysis=title_analysis,
        fixture_dir=fixture_dir,
        recorded_frontier=cont.recorded_p17_04r_frontier(),
    )
    analysis = SideEffectsAnalysis.create(base, recorded_frontier)
    entry = _parse_hex(recorded_frontier["attempted_frontier_pc"])
    if analysis.region_of(entry) == "OUTSIDE":
        raise SideEffectsError("CONTINUATION_ENTRY_OUTSIDE_AUTHENTICATED_TEXT", _hex32(entry))
    if entry in analysis.reachable:
        raise SideEffectsError("CONTINUATION_ENTRY_ALREADY_AUTHENTICATED", _hex32(entry))
    return analysis


# --------------------------------------------------------------------------
# C generation: P17-06R emitted runtime
# --------------------------------------------------------------------------

_HEADER_TEMPLATE = r"""/* Generated by p17_side_effects_exec_v1.py from authenticated records. */
#ifndef OR_SIDE_EFFECTS_V1_H
#define OR_SIDE_EFFECTS_V1_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OR_SIDE_RAM_SIZE 2097152u
#define OR_SIDE_RAM_KSEG0_BASE 0x80000000u
#define OR_SIDE_CONTINUATION_BUDGET @@CONT_BUDGET@@u
#define OR_SIDE_TOTAL_BUDGET @@TOTAL_BUDGET@@u
#define OR_SIDE_CONTINUATION_ENTRY @@ENTRY_PC@@u
#define OR_SIDE_EVENT_CAP @@EVENT_CAP@@u
#define OR_SIDE_BIOS_DISPATCH_LIMIT @@BIOS_LIMIT@@u
#define OR_SIDE_DEVICE_EVENT_LIMIT @@DEVICE_LIMIT@@u

/* One recorded BIOS/device side-effect event.  kind 1 = BIOS dispatch
   (f[0] vector, f[1] function, f[2..5] a0..a3, f[6] ra, f[7] sp, f[8] gp,
   f[9] owning instruction pc, f[10] delay-slot pc, f[11] return pc);
   kind 2 = memory-mapped I/O (f[0] store flag, f[1] address, f[2] width,
   f[3] value, f[4] owning instruction pc, f[5] delay-slot pc). */
struct or_side_event_v1 {
    uint32_t kind;
    uint32_t seq;
    uint32_t f[12];
};

struct or_side_event_log_v1 {
    struct or_side_event_v1 *events;
    uint32_t cap;
    uint32_t count;
    int overflow;
};

struct or_side_guest_state_v1 {
    uint32_t regs[32];
    uint32_t pc;
    uint32_t next_pc;
    uint32_t hi;
    uint32_t lo;
    uint32_t delay_pc;
    int      delay_active;
    uint32_t step_count;
    uint32_t budget;
    int      stop;
    char     stop_reason[64];
    uint32_t last_executed_pc;
    uint32_t attempted_frontier_pc;
    uint32_t pending_transfer_target;
    int      pending_transfer_type;
    int      pending_transfer_applied;
    uint32_t delay_slot_owner_pc;
    uint32_t continuation_entry_steps;
    uint32_t bios_dispatch_count;
    uint32_t device_event_count;
};

struct or_side_runtime_services_v1 {
    void *user_data;
    void (*transcript)(void *user_data, uint32_t pc, const char *op, uint32_t step);
    struct or_side_event_log_v1 *events;
    uint8_t *ram_base;
    uint32_t ram_size;
};

int or_side_execute_v1(struct or_side_guest_state_v1 *state,
                       const struct or_side_runtime_services_v1 *services);

uint32_t or_side_record_count(void);
const uint32_t *or_side_pc_table(void);
const uint8_t *or_side_pc_seen(void);
const char *or_side_op_for_index(uint32_t index);
const uint32_t *or_side_post_entry_pcs(uint32_t *count);
const char *or_side_stop_reason(const struct or_side_guest_state_v1 *state);

#ifdef __cplusplus
}
#endif

#endif
"""


_RUNTIME_TEMPLATE = r"""/* Generated by p17_side_effects_exec_v1.py from authenticated records. */
/* Semantic vocabulary: @@VOCAB@@ */
/* Provenance digest: @@PROV@@ */
#include "or_side_effects_v1.h"
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#define RAM_SIZE OR_SIDE_RAM_SIZE
#define RAM_KSEG0_BASE OR_SIDE_RAM_KSEG0_BASE
#define RECORD_COUNT @@RECORD_COUNT@@u

static uint8_t g_default_ram[RAM_SIZE];
static uint8_t *g_ram = g_default_ram;

static const uint8_t g_title_payload[@@TITLE_LEN@@] = {
@@TITLE_LITERAL@@
};

static const uint8_t g_mainexe_payload[@@MAINEXE_LEN@@] = {
@@MAINEXE_LITERAL@@
};

static const uint32_t g_pc_table[RECORD_COUNT] = {
@@PC_TABLE@@
};

static const char *const g_op_table[RECORD_COUNT] = {
@@OP_TABLE@@
};

static uint8_t g_pc_seen[RECORD_COUNT];
static uint32_t g_post_entry_pcs[@@POST_ENTRY_CAP@@];
static uint32_t g_post_entry_count = 0;

uint32_t or_side_record_count(void) { return RECORD_COUNT; }
const uint32_t *or_side_pc_table(void) { return g_pc_table; }
const uint8_t *or_side_pc_seen(void) { return g_pc_seen; }
const char *or_side_op_for_index(uint32_t index) {
    return (index < RECORD_COUNT) ? g_op_table[index] : "?";
}
const uint32_t *or_side_post_entry_pcs(uint32_t *count) {
    *count = g_post_entry_count;
    return g_post_entry_pcs;
}
const char *or_side_stop_reason(const struct or_side_guest_state_v1 *state) {
    return state ? state->stop_reason : "";
}

static int ram_check(uint32_t addr) {
    return (RAM_KSEG0_BASE <= addr && addr < RAM_KSEG0_BASE + RAM_SIZE) ||
           (0xa0000000u <= addr && addr < 0xa0000000u + RAM_SIZE) ||
           (addr < RAM_SIZE);
}

static uint32_t ram_offset(uint32_t addr) {
    if (RAM_KSEG0_BASE <= addr && addr < RAM_KSEG0_BASE + RAM_SIZE) return addr - RAM_KSEG0_BASE;
    if (0xa0000000u <= addr && addr < 0xa0000000u + RAM_SIZE) return addr - 0xa0000000u;
    return addr;
}

static uint32_t ram_load_u32(uint32_t addr) {
    uint32_t off = ram_offset(addr);
    return (uint32_t)g_ram[off] | ((uint32_t)g_ram[off + 1] << 8) |
           ((uint32_t)g_ram[off + 2] << 16) | ((uint32_t)g_ram[off + 3] << 24);
}

static uint16_t ram_load_u16(uint32_t addr) {
    uint32_t off = ram_offset(addr);
    return (uint16_t)((uint16_t)g_ram[off] | ((uint16_t)g_ram[off + 1] << 8));
}

static uint8_t ram_load_u8(uint32_t addr) {
    return g_ram[ram_offset(addr)];
}

static void ram_store_u32(uint32_t addr, uint32_t value) {
    uint32_t off = ram_offset(addr);
    g_ram[off] = (uint8_t)value;
    g_ram[off + 1] = (uint8_t)(value >> 8);
    g_ram[off + 2] = (uint8_t)(value >> 16);
    g_ram[off + 3] = (uint8_t)(value >> 24);
}

static void ram_store_u16(uint32_t addr, uint16_t value) {
    uint32_t off = ram_offset(addr);
    g_ram[off] = (uint8_t)value;
    g_ram[off + 1] = (uint8_t)(value >> 8);
}

static void ram_store_u8(uint32_t addr, uint8_t value) {
    g_ram[ram_offset(addr)] = value;
}

/* --- exact R3000A unaligned load/store semantics (little endian) -------- */

static uint32_t ram_lwl(uint32_t addr, uint32_t rt) {
    uint32_t aligned = addr & ~3u;
    uint32_t byte = addr & 3u;
    uint32_t word = ram_load_u32(aligned);
    uint32_t shift = 8u * (3u - byte);
    uint32_t mask = (shift == 0u) ? 0u : (0xFFFFFFFFu >> (32u - shift));
    return (rt & mask) | (word << shift);
}

static uint32_t ram_lwr(uint32_t addr, uint32_t rt) {
    uint32_t aligned = addr & ~3u;
    uint32_t byte = addr & 3u;
    uint32_t word = ram_load_u32(aligned);
    uint32_t width = 8u * (4u - byte);
    uint32_t lowmask = (width >= 32u) ? 0xFFFFFFFFu : ((1u << width) - 1u);
    return (rt & ~lowmask) | ((word >> (8u * byte)) & lowmask);
}

static void ram_swl(uint32_t addr, uint32_t value) {
    uint32_t aligned = addr & ~3u;
    uint32_t byte = addr & 3u;
    uint32_t word = ram_load_u32(aligned);
    uint8_t d[4];
    d[0] = (uint8_t)word; d[1] = (uint8_t)(word >> 8);
    d[2] = (uint8_t)(word >> 16); d[3] = (uint8_t)(word >> 24);
    d[byte] = (uint8_t)(value >> 24);
    if (byte >= 1u) d[byte - 1] = (uint8_t)(value >> 16);
    if (byte >= 2u) d[byte - 2] = (uint8_t)(value >> 8);
    if (byte == 3u) d[byte - 3] = (uint8_t)value;
    ram_store_u32(aligned, (uint32_t)d[0] | ((uint32_t)d[1] << 8) |
                           ((uint32_t)d[2] << 16) | ((uint32_t)d[3] << 24));
}

static void ram_swr(uint32_t addr, uint32_t value) {
    uint32_t aligned = addr & ~3u;
    uint32_t byte = addr & 3u;
    uint32_t word = ram_load_u32(aligned);
    uint8_t d[4];
    d[0] = (uint8_t)word; d[1] = (uint8_t)(word >> 8);
    d[2] = (uint8_t)(word >> 16); d[3] = (uint8_t)(word >> 24);
    d[byte] = (uint8_t)value;
    if (byte <= 2u) d[byte + 1] = (uint8_t)(value >> 8);
    if (byte <= 1u) d[byte + 2] = (uint8_t)(value >> 16);
    if (byte == 0u) d[byte + 3] = (uint8_t)(value >> 24);
    ram_store_u32(aligned, (uint32_t)d[0] | ((uint32_t)d[1] << 8) |
                           ((uint32_t)d[2] << 16) | ((uint32_t)d[3] << 24));
}

/* --- BIOS / device layer ------------------------------------------------ */

static int dev_phys_addr(uint32_t addr, uint32_t *out) {
    if (addr >= 0x1f801000u && addr < 0x1f802000u) { *out = addr; return 1; }
    if (addr >= 0xa0000000u && addr < 0xa0200000u) {
        uint32_t candidate = addr - 0xa0000000u;
        if (candidate >= 0x1f801000u && candidate < 0x1f802000u) { *out = candidate; return 1; }
    }
    if (addr >= 0xbf800000u && addr < 0xbfa00000u) {
        uint32_t candidate = addr - 0xbf800000u;
        if (candidate >= 0x1f801000u && candidate < 0x1f802000u) { *out = candidate; return 1; }
    }
    return 0;
}

static int dev_is_mmio(uint32_t addr) {
    uint32_t phys = 0u;
    return dev_phys_addr(addr, &phys);
}

static int dev_bios_vector(uint32_t pc, uint32_t *vector) {
    if (pc == 0x000000a0u || pc == 0x800000a0u) { *vector = 0x000000a0u; return 1; }
    if (pc == 0x000000b0u || pc == 0x800000b0u) { *vector = 0x000000b0u; return 1; }
    if (pc == 0x000000c0u || pc == 0x800000c0u) { *vector = 0x000000c0u; return 1; }
    return 0;
}

static void dev_record(struct or_side_guest_state_v1 *state,
                       const struct or_side_runtime_services_v1 *services,
                       uint32_t kind, const uint32_t *fields, uint32_t count) {
    struct or_side_event_log_v1 *log = services ? services->events : 0;
    uint32_t i;
    if (!log || !log->events) return;
    if (log->count >= log->cap) { log->overflow = 1; return; }
    log->events[log->count].kind = kind;
    log->events[log->count].seq = log->count;
    for (i = 0u; i < 12u; i++) {
        log->events[log->count].f[i] = (i < count) ? fields[i] : 0u;
    }
    log->count++;
    (void)state;
}

static uint32_t dev_owner_pc(const struct or_side_guest_state_v1 *state, uint32_t *delay_out) {
    if (state->delay_pc != 0u && state->last_executed_pc == state->delay_pc) {
        *delay_out = state->delay_pc;
        return state->delay_slot_owner_pc;
    }
    *delay_out = 0u;
    return state->last_executed_pc;
}

static void or_side_mark_pc(uint32_t index) {
    if (index < RECORD_COUNT) g_pc_seen[index] = 1u;
}

static void or_side_note_post_entry(struct or_side_guest_state_v1 *state, uint32_t pc) {
    if (state->continuation_entry_steps == 0u) return;
    if (g_post_entry_count < @@POST_ENTRY_CAP@@u) {
        g_post_entry_pcs[g_post_entry_count] = pc;
        g_post_entry_count++;
    }
}

static void or_side_stop(struct or_side_guest_state_v1 *state, const char *reason) {
    state->stop = 1;
    strncpy(state->stop_reason, reason, sizeof(state->stop_reason) - 1);
    state->stop_reason[sizeof(state->stop_reason) - 1] = 0;
}

static const char *op_name_for_pc(uint32_t pc) {
    switch (pc) {
@@OPNAME_CASES@@
        default: return "?";
    }
}

int or_side_execute_v1(struct or_side_guest_state_v1 *state,
                       const struct or_side_runtime_services_v1 *services) {
    uint32_t vector = 0u;
    if (!state) return -1;
    if (services && services->ram_base) {
        if (services->ram_size != RAM_SIZE) {
            or_side_stop(state, "SERVICES_RAM_SIZE_MISMATCH");
            return 0;
        }
        g_ram = services->ram_base;
    } else {
        g_ram = g_default_ram;
    }
    memcpy(g_ram + @@TITLE_OFFSET@@u, g_title_payload, sizeof(g_title_payload));
    memcpy(g_ram + @@MAINEXE_OFFSET@@u, g_mainexe_payload, sizeof(g_mainexe_payload));
    state->stop = 0;
    state->delay_active = 0;
    state->delay_pc = 0;
    state->last_executed_pc = 0;
    state->attempted_frontier_pc = 0;
    state->delay_slot_owner_pc = 0;
    state->pending_transfer_type = 0;
    state->pending_transfer_target = 0;
    state->pending_transfer_applied = 0;
    state->continuation_entry_steps = 0;
    state->bios_dispatch_count = 0;
    state->device_event_count = 0;
    g_post_entry_count = 0;

    while (!state->stop) {
        state->regs[0] = 0;
        if (state->step_count >= state->budget) {
            state->attempted_frontier_pc = state->pc;
            or_side_stop(state, "STEP_LIMIT_REACHED");
            break;
        }
        if (state->pc == OR_SIDE_CONTINUATION_ENTRY && state->continuation_entry_steps == 0u) {
            state->continuation_entry_steps = state->step_count;
        }
        if (state->continuation_entry_steps != 0u &&
            (state->step_count - state->continuation_entry_steps) >= OR_SIDE_CONTINUATION_BUDGET) {
            state->attempted_frontier_pc = state->pc;
            or_side_stop(state, "CONTINUATION_BUDGET_REACHED");
            break;
        }
        if (dev_bios_vector(state->pc, &vector)) {
            uint32_t fields[12];
            uint32_t delay_pc = 0u;
            uint32_t owner = dev_owner_pc(state, &delay_pc);
            fields[0] = vector;
            fields[1] = state->regs[9];
            fields[2] = state->regs[4];
            fields[3] = state->regs[5];
            fields[4] = state->regs[6];
            fields[5] = state->regs[7];
            fields[6] = state->regs[31];
            fields[7] = state->regs[29];
            fields[8] = state->regs[28];
            fields[9] = owner;
            fields[10] = delay_pc;
            fields[11] = state->regs[31];
            dev_record(state, services, 1u, fields, 12u);
            state->bios_dispatch_count++;
            if (state->bios_dispatch_count > OR_SIDE_BIOS_DISPATCH_LIMIT) {
                state->attempted_frontier_pc = state->pc;
                or_side_stop(state, "BIOS_DISPATCH_LIMIT_REACHED");
                break;
            }
            if (state->pending_transfer_type != 0) state->pending_transfer_applied = 1;
            state->delay_active = 0;
            state->pc = state->regs[31];
            continue;
        }
        state->next_pc = state->pc;
        state->attempted_frontier_pc = state->pc;
        switch (state->pc) {
@@INSTRUCTION_CASES@@
            default:
                or_side_stop(state, "PC_NOT_IN_AUTHENTICATED_TABLE");
                break;
        }
    }
    return 0;
}
"""


RUNTIME_RESULT_SCHEMA = "openrecomp-phase17-side-effects-result-v1"
HARNESS_SCHEMA = "openrecomp-phase17-side-effects-runtime-output-v1"


@dataclass
class SideEmissionContext:
    analysis: SideEffectsAnalysis
    records: list[Any] = field(default_factory=list)
    record_by_pc: dict[int, Any] = field(default_factory=dict)
    index_by_pc: dict[int, int] = field(default_factory=dict)
    h_path: pathlib.Path | None = None
    c_path: pathlib.Path | None = None
    harness_path: pathlib.Path | None = None
    so_path: pathlib.Path | None = None
    exe_path: pathlib.Path | None = None


def _emit_completion_side(rec: Any, ctx: SideEmissionContext, indent: str) -> list[str]:
    index = ctx.index_by_pc[rec.pc]
    return [
        f"{indent}state->step_count++;",
        f"{indent}state->last_executed_pc = 0x{rec.pc:08x}u;",
        f"{indent}if (services && services->transcript) {{ services->transcript(services->user_data, 0x{rec.pc:08x}u, op_name_for_pc(0x{rec.pc:08x}u), state->step_count); }}",
        f"{indent}or_side_mark_pc({index}u);",
        f"{indent}or_side_note_post_entry(state, 0x{rec.pc:08x}u);",
    ]


def _emit_delay_slot_side(ctx: SideEmissionContext, owner_pc: int,
                          indent: str = "        ") -> list[str]:
    delay_pc = ctx.analysis.delay_by_owner.get(owner_pc)
    if delay_pc is None:
        return [
            f'{indent}or_side_stop(state, "MISSING_DELAY_SLOT");',
            f"{indent}break;",
        ]
    rec = ctx.record_by_pc[delay_pc]
    lines = [
        f"{indent}/* delay slot 0x{delay_pc:08x} */",
        f"{indent}if (state->continuation_entry_steps != 0u && (state->step_count - state->continuation_entry_steps) >= OR_SIDE_CONTINUATION_BUDGET) {{",
        f"{indent}    state->attempted_frontier_pc = 0x{delay_pc:08x}u;",
        f'{indent}    or_side_stop(state, "CONTINUATION_BUDGET_REACHED");',
        f"{indent}    break;",
        f"{indent}}}",
        f"{indent}state->delay_active = 1;",
        f"{indent}state->delay_pc = 0x{delay_pc:08x}u;",
        f"{indent}state->delay_slot_owner_pc = 0x{owner_pc:08x}u;",
        f"{indent}state->pc = 0x{delay_pc:08x}u;",
        f"{indent}state->attempted_frontier_pc = 0x{delay_pc:08x}u;",
    ]
    lines.extend(_emit_instruction_side(rec, ctx, indent, is_delay_slot=True))
    lines.append(f"{indent}state->delay_active = 0;")
    return lines


def _emit_mmio_hook(rec: Any, store: bool, width: int, value_expression: str,
                    indent: str) -> list[str]:
    return [
        f"{indent}    uint32_t _ef[12];",
        f"{indent}    _ef[0] = {1 if store else 0}u; _ef[1] = _addr; _ef[2] = {width}u;",
        f"{indent}    _ef[3] = {value_expression}; _ef[4] = 0x{rec.pc:08x}u; _ef[5] = 0u;",
        f"{indent}    dev_record(state, services, 2u, _ef, 6u);",
        f"{indent}    state->device_event_count++;",
        f'{indent}    if (state->device_event_count > OR_SIDE_DEVICE_EVENT_LIMIT) {{ or_side_stop(state, "DEVICE_EVENT_LIMIT_REACHED"); break; }}',
    ]


_ALIGNMENT_CHECK = {
    4: '( _addr & 3u) != 0u',
    2: '( _addr & 1u) != 0u',
    1: '0u',
}
_OOB_REASON = {
    4: "UNALIGNED_OR_OUT_OF_BOUNDS_MEMORY_ACCESS",
    2: "UNALIGNED_OR_OUT_OF_BOUNDS_MEMORY_ACCESS",
    1: "OUT_OF_BOUNDS_MEMORY_ACCESS",
}
_RAM_LOAD = {
    "lw": "ram_load_u32(_addr)",
    "lh": "(uint32_t)(int32_t)(int16_t)ram_load_u16(_addr)",
    "lhu": "ram_load_u16(_addr)",
    "lb": "(uint32_t)(int32_t)(int8_t)ram_load_u8(_addr)",
    "lbu": "ram_load_u8(_addr)",
}
_RAM_STORE = {
    "sw": "ram_store_u32(_addr, state->regs[{rt}]);",
    "sh": "ram_store_u16(_addr, (uint16_t)(state->regs[{rt}] & 0xffffu));",
    "sb": "ram_store_u8(_addr, (uint8_t)(state->regs[{rt}] & 0xffu));",
}


def _emit_instruction_side(rec: Any, ctx: SideEmissionContext, indent: str = "        ",
                           *, is_delay_slot: bool = False) -> list[str]:
    """Emit one authenticated instruction with the P17-06R device layer."""
    op = rec.op
    rs, rt, rd = rec.rs, rec.rt, rec.rd
    imm = rec.imm
    target = rec.target
    pc_hex = f"0x{rec.pc:08x}u"
    out: list[str] = []

    def line(code: str) -> None:
        out.append(f"{indent}{code}")

    if is_delay_slot and op in emitter.CONTROL_OPS:
        line('or_side_stop(state, "UNSUPPORTED_DELAY_SLOT_CONTROL_FLOW");')
        line("break;")
        return out

    line("state->regs[0] = 0;")

    if op == "nop":
        pass
    elif op == "addu":
        line(f"state->regs[{rd}] = state->regs[{rs}] + state->regs[{rt}];")
    elif op == "subu":
        line(f"state->regs[{rd}] = state->regs[{rs}] - state->regs[{rt}];")
    elif op == "add":
        line("{")
        line(f"  int32_t _a = (int32_t)state->regs[{rs}];")
        line(f"  int32_t _b = (int32_t)state->regs[{rt}];")
        line("  int32_t _r = (int32_t)((uint32_t)_a + (uint32_t)_b);")
        line('  if (((_a ^ _b) & 0x80000000) == 0 && ((_a ^ _r) & 0x80000000) != 0) { or_side_stop(state, "SIGNED_OVERFLOW"); break; }')
        line(f"  state->regs[{rd}] = (uint32_t)_r;")
        line("}")
    elif op == "sub":
        line("{")
        line(f"  int32_t _a = (int32_t)state->regs[{rs}];")
        line(f"  int32_t _b = (int32_t)state->regs[{rt}];")
        line("  int32_t _r = (int32_t)((uint32_t)_a - (uint32_t)_b);")
        line('  if (((_a ^ _b) & 0x80000000) != 0 && ((_a ^ _r) & 0x80000000) != 0) { or_side_stop(state, "SIGNED_OVERFLOW"); break; }')
        line(f"  state->regs[{rd}] = (uint32_t)_r;")
        line("}")
    elif op == "and":
        line(f"state->regs[{rd}] = state->regs[{rs}] & state->regs[{rt}];")
    elif op == "or":
        line(f"state->regs[{rd}] = state->regs[{rs}] | state->regs[{rt}];")
    elif op == "xor":
        line(f"state->regs[{rd}] = state->regs[{rs}] ^ state->regs[{rt}];")
    elif op == "nor":
        line(f"state->regs[{rd}] = ~(state->regs[{rs}] | state->regs[{rt}]);")
    elif op == "sll":
        line(f"state->regs[{rd}] = state->regs[{rt}] << {rec.shamt};")
    elif op == "srl":
        line(f"state->regs[{rd}] = state->regs[{rt}] >> {rec.shamt};")
    elif op == "sra":
        line(f"state->regs[{rd}] = (uint32_t)(((int32_t)state->regs[{rt}]) >> {rec.shamt});")
    elif op == "sllv":
        line(f"state->regs[{rd}] = state->regs[{rt}] << (state->regs[{rs}] & 0x1f);")
    elif op == "srlv":
        line(f"state->regs[{rd}] = state->regs[{rt}] >> (state->regs[{rs}] & 0x1f);")
    elif op == "srav":
        line(f"state->regs[{rd}] = (uint32_t)(((int32_t)state->regs[{rt}]) >> (state->regs[{rs}] & 0x1f));")
    elif op == "slt":
        line(f"state->regs[{rd}] = ((int32_t)state->regs[{rs}] < (int32_t)state->regs[{rt}]) ? 1u : 0u;")
    elif op == "sltu":
        line(f"state->regs[{rd}] = (state->regs[{rs}] < state->regs[{rt}]) ? 1u : 0u;")
    elif op == "addiu":
        line(f"state->regs[{rt}] = state->regs[{rs}] + (int32_t)(int16_t)({imm & 0xFFFF}u);")
    elif op == "addi":
        line("{")
        line(f"  int32_t _a = (int32_t)state->regs[{rs}];")
        line(f"  int32_t _b = (int32_t)(int16_t)({imm & 0xFFFF}u);")
        line("  int32_t _r = _a + _b;")
        line('  if (((_a ^ _b) & 0x80000000) == 0 && ((_a ^ _r) & 0x80000000) != 0) { or_side_stop(state, "SIGNED_OVERFLOW"); break; }')
        line(f"  state->regs[{rt}] = (uint32_t)_r;")
        line("}")
    elif op == "andi":
        line(f"state->regs[{rt}] = state->regs[{rs}] & {imm & 0xFFFF}u;")
    elif op == "ori":
        line(f"state->regs[{rt}] = state->regs[{rs}] | {imm & 0xFFFF}u;")
    elif op == "xori":
        line(f"state->regs[{rt}] = state->regs[{rs}] ^ {imm & 0xFFFF}u;")
    elif op == "slti":
        line(f"state->regs[{rt}] = ((int32_t)state->regs[{rs}] < (int32_t)(int16_t)({imm & 0xFFFF}u)) ? 1u : 0u;")
    elif op == "sltiu":
        line(f"state->regs[{rt}] = (state->regs[{rs}] < (uint32_t)({imm & 0xFFFF}u)) ? 1u : 0u;")
    elif op == "lui":
        line(f"state->regs[{rt}] = {imm & 0xFFFF}u << 16;")
    elif op in ("lw", "lh", "lhu", "lb", "lbu", "sw", "sh", "sb"):
        width = {"lw": 4, "lh": 2, "lhu": 2, "lb": 1, "lbu": 1,
                 "sw": 4, "sh": 2, "sb": 1}[op]
        store = op in ("sw", "sh", "sb")
        line(f"{{ uint32_t _addr = state->regs[{rs}] + (int32_t)(int16_t)({imm & 0xFFFF}u);")
        line("  if (dev_is_mmio(_addr)) {")
        out.extend(_emit_mmio_hook(rec, store, width,
                                   f"state->regs[{rt}]" if store else "0u", indent))
        if not store:
            line(f"    state->regs[{rt}] = 0u; /* MMIO read model */")
        line("  } else {")
        line(f'    if ({_ALIGNMENT_CHECK[width]} || !ram_check(_addr)) {{ or_side_stop(state, "{_OOB_REASON[width]}"); break; }}')
        if store:
            line("    " + _RAM_STORE[op].format(rt=rt))
        else:
            line(f"    state->regs[{rt}] = {_RAM_LOAD[op]};")
        line("  }")
        line("}")
    elif op in ("lwl", "lwr", "swl", "swr"):
        store = op in ("swl", "swr")
        helper = {"lwl": "ram_lwl", "lwr": "ram_lwr",
                  "swl": "ram_swl", "swr": "ram_swr"}[op]
        line(f"{{ uint32_t _addr = state->regs[{rs}] + (int32_t)(int16_t)({imm & 0xFFFF}u);")
        line("  if (dev_is_mmio(_addr)) {")
        out.extend(_emit_mmio_hook(rec, store, 4,
                                   f"state->regs[{rt}]" if store else "0u", indent))
        if not store:
            line(f"    state->regs[{rt}] = 0u; /* MMIO read model */")
        line("  } else {")
        line(f'    if (!ram_check(_addr) || !ram_check(_addr + 3u)) {{ or_side_stop(state, "OUT_OF_BOUNDS_MEMORY_ACCESS"); break; }}')
        if store:
            line(f"    {helper}(_addr, state->regs[{rt}]);")
        else:
            line(f"    state->regs[{rt}] = {helper}(_addr, state->regs[{rt}]);")
        line("  }")
        line("}")
    elif op == "mult":
        line("{")
        line(f"  int64_t _prod = (int64_t)(int32_t)state->regs[{rs}] * (int64_t)(int32_t)state->regs[{rt}];")
        line("  state->lo = (uint32_t)_prod;")
        line("  state->hi = (uint32_t)((uint64_t)_prod >> 32);")
        line("}")
    elif op == "multu":
        line("{")
        line(f"  uint64_t _prod = (uint64_t)state->regs[{rs}] * (uint64_t)state->regs[{rt}];")
        line("  state->lo = (uint32_t)_prod;")
        line("  state->hi = (uint32_t)(_prod >> 32);")
        line("}")
    elif op == "div":
        line("{")
        line(f"  int32_t _b = (int32_t)state->regs[{rt}];")
        line(f"  int32_t _a = (int32_t)state->regs[{rs}];")
        line('  if (_b == 0) { or_side_stop(state, "DIVIDE_BY_ZERO"); break; }')
        line("  if (_a == (int32_t)0x80000000 && _b == -1) { state->lo = 0x80000000u; state->hi = 0u; }")
        line("  else { state->lo = (uint32_t)(_a / _b); state->hi = (uint32_t)(_a % _b); }")
        line("}")
    elif op == "divu":
        line("{")
        line(f"  uint32_t _b = state->regs[{rt}];")
        line(f"  uint32_t _a = state->regs[{rs}];")
        line('  if (_b == 0u) { or_side_stop(state, "DIVIDE_BY_ZERO"); break; }')
        line("  state->lo = _a / _b;")
        line("  state->hi = _a % _b;")
        line("}")
    elif op == "mflo":
        line(f"state->regs[{rd}] = state->lo;")
    elif op == "mfhi":
        line(f"state->regs[{rd}] = state->hi;")
    elif op == "mthi":
        line(f"state->hi = state->regs[{rs}];")
    elif op == "mtlo":
        line(f"state->lo = state->regs[{rs}];")
    elif op in emitter.JUMP_OPS:
        if target is None:
            line('or_side_stop(state, "JUMP_WITHOUT_TARGET");')
            line("break;")
            return out
        if op == "jal":
            line(f"state->regs[31] = 0x{rec.pc + 8:08x}u;")
            line("state->pending_transfer_type = 1; /* DIRECT_CALL */")
            line(f"state->pending_transfer_target = 0x{target:08x}u;")
            out.extend(_emit_completion_side(rec, ctx, indent))
            out.extend(_emit_delay_slot_side(ctx, rec.pc, indent))
            line("state->pc = state->pending_transfer_target;")
            line("state->pending_transfer_applied = 1;")
            line("break;")
            return out
        out.extend(_emit_completion_side(rec, ctx, indent))
        out.extend(_emit_delay_slot_side(ctx, rec.pc, indent))
        line(f"state->pc = 0x{target:08x}u;")
        line("break;")
        return out
    elif op in emitter.BRANCH_CONDITION_OPS:
        cond = {
            "beq": f"state->regs[{rs}] == state->regs[{rt}]",
            "bne": f"state->regs[{rs}] != state->regs[{rt}]",
            "blez": f"(int32_t)state->regs[{rs}] <= 0",
            "bgtz": f"(int32_t)state->regs[{rs}] > 0",
            "bltz": f"(int32_t)state->regs[{rs}] < 0",
            "bgez": f"(int32_t)state->regs[{rs}] >= 0",
        }[op]
        if target is None:
            line('or_side_stop(state, "BRANCH_WITHOUT_TARGET");')
            line("break;")
            return out
        line(f"{{ int _cond = ({cond}) ? 1 : 0;")
        out.extend(_emit_completion_side(rec, ctx, indent + "  "))
        out.extend(_emit_delay_slot_side(ctx, rec.pc, indent + "  "))
        line(f"  state->pc = _cond ? 0x{target:08x}u : 0x{rec.pc + 8:08x}u;")
        line("}")
        line("break;")
        return out
    elif op == "jr":
        line(f"{{ uint32_t _target = state->regs[{rs}];")
        out.extend(_emit_completion_side(rec, ctx, indent + "  "))
        out.extend(_emit_delay_slot_side(ctx, rec.pc, indent + "  "))
        line("  state->pc = _target;")
        line("}")
        line("break;")
        return out
    elif op == "jalr":
        line(f"{{ uint32_t _target = state->regs[{rs}];")
        if rd != 0:
            line(f"  state->regs[{rd}] = 0x{rec.pc + 8:08x}u;")
        out.extend(_emit_completion_side(rec, ctx, indent + "  "))
        out.extend(_emit_delay_slot_side(ctx, rec.pc, indent + "  "))
        line("  state->pc = _target;")
        line("}")
        line("break;")
        return out
    else:
        line('or_side_stop(state, "UNSUPPORTED_OPERATION");')
        line("break;")
        return out

    out.extend(_emit_completion_side(rec, ctx, indent))
    if is_delay_slot:
        return out
    line(f"state->pc = 0x{rec.pc + 4:08x}u;")
    line("break;")
    return out


_HARNESS_TEMPLATE = r"""/* Generated deterministic harness for or_side_execute_v1. */
#include "or_side_effects_v1.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define RAM_SIZE OR_SIDE_RAM_SIZE
#define TRACE_CAP @@TRACE_CAP@@u

static uint8_t g_harness_ram[RAM_SIZE];
static const char *g_ops[TRACE_CAP];
static uint32_t g_step_pcs[TRACE_CAP];
static uint32_t g_ops_len = 0;
static struct or_side_event_v1 g_events[OR_SIDE_EVENT_CAP];
static struct or_side_event_log_v1 g_event_log;

static void trace_cb(void *user_data, uint32_t pc, const char *op, uint32_t step) {
    (void)user_data; (void)step;
    if (g_ops_len < TRACE_CAP) {
        g_ops[g_ops_len] = (op != NULL) ? op : "?";
        g_step_pcs[g_ops_len] = pc;
        g_ops_len++;
    }
}

static void print_hex(const uint8_t *data, int n) {
    for (int i = 0; i < n; i++) printf("%02x", (unsigned)data[i]);
}

static void ram_digest(uint8_t *out) {
    uint32_t h0 = 0x6a09e667u, h1 = 0xbb67ae85u, h2 = 0x3c6ef372u, h3 = 0xa54ff53au;
    for (uint32_t i = 0; i < RAM_SIZE; i += 4) {
        uint32_t w = (uint32_t)g_harness_ram[i] | ((uint32_t)g_harness_ram[i + 1] << 8) |
                     ((uint32_t)g_harness_ram[i + 2] << 16) | ((uint32_t)g_harness_ram[i + 3] << 24);
        h0 ^= w;
        h1 ^= (w << 7) | (w >> 25);
        h2 += w;
        h3 ^= (w >> 11) | (w << 21);
        uint32_t t = h0;
        h0 = h1;
        h1 = h2;
        h2 = h3;
        h3 = t;
    }
    out[0] = (uint8_t)h0; out[1] = (uint8_t)(h0 >> 8); out[2] = (uint8_t)(h0 >> 16); out[3] = (uint8_t)(h0 >> 24);
    out[4] = (uint8_t)h1; out[5] = (uint8_t)(h1 >> 8); out[6] = (uint8_t)(h1 >> 16); out[7] = (uint8_t)(h1 >> 24);
    out[8] = (uint8_t)h2; out[9] = (uint8_t)(h2 >> 8); out[10] = (uint8_t)(h2 >> 16); out[11] = (uint8_t)(h2 >> 24);
    out[12] = (uint8_t)h3; out[13] = (uint8_t)(h3 >> 8); out[14] = (uint8_t)(h3 >> 16); out[15] = (uint8_t)(h3 >> 24);
}

int main(void) {
    struct or_side_guest_state_v1 state;
    struct or_side_runtime_services_v1 services;
    uint32_t i, j, count;
    const uint32_t *pcs;
    const uint8_t *seen;
    const uint32_t *post;
    uint8_t rdigest[16];
    uint8_t regdigest[16];

    memset(&state, 0, sizeof(state));
    memset(&services, 0, sizeof(services));
    g_event_log.events = g_events;
    g_event_log.cap = OR_SIDE_EVENT_CAP;
    g_event_log.count = 0;
    g_event_log.overflow = 0;
    state.pc = @@ENTRY@@u;
    state.budget = OR_SIDE_TOTAL_BUDGET;
    services.ram_base = g_harness_ram;
    services.ram_size = RAM_SIZE;
    services.transcript = trace_cb;
    services.events = &g_event_log;

    or_side_execute_v1(&state, &services);

    ram_digest(rdigest);
    {
        uint32_t h0 = 0x6a09e667u, h1 = 0xbb67ae85u;
        for (i = 0; i < 32u; i++) { h0 ^= state.regs[i]; h1 += state.regs[i]; }
        h0 ^= state.pc ^ state.hi ^ state.lo;
        h1 += state.pc + state.hi + state.lo;
        regdigest[0] = (uint8_t)h0; regdigest[1] = (uint8_t)(h0 >> 8);
        regdigest[2] = (uint8_t)(h0 >> 16); regdigest[3] = (uint8_t)(h0 >> 24);
        regdigest[4] = (uint8_t)h1; regdigest[5] = (uint8_t)(h1 >> 8);
        regdigest[6] = (uint8_t)(h1 >> 16); regdigest[7] = (uint8_t)(h1 >> 24);
        regdigest[8] = (uint8_t)state.step_count; regdigest[9] = (uint8_t)(state.step_count >> 8);
        regdigest[10] = (uint8_t)state.stop; regdigest[11] = 0;
        memset(regdigest + 12, 0, 4);
    }

    printf("SCHEMA %s\n", "@@SCHEMA@@");
    printf("ENTRY_PC 0x%08x\n", @@ENTRY@@u);
    printf("EXECUTED %u\n", state.step_count);
    printf("CONTINUATION_ENTRY_STEPS %u\n", state.continuation_entry_steps);
    printf("CONTINUATION_EXECUTED %u\n", state.step_count - state.continuation_entry_steps);
    printf("STOP_REASON %s\n", state.stop_reason);
    printf("FINAL_PC 0x%08x\n", state.pc);
    printf("LAST_EXECUTED_PC 0x%08x\n", state.last_executed_pc);
    printf("ATTEMPTED_FRONTIER_PC 0x%08x\n", state.attempted_frontier_pc);
    printf("REGISTER_DIGEST ");
    print_hex(regdigest, 16);
    printf("\n");
    printf("RAM_DIGEST ");
    print_hex(rdigest, 16);
    printf("\n");
    printf("PROVENANCE_DIGEST %s\n", "@@PROV@@");
    printf("BIOS_DISPATCH_COUNT %u\n", state.bios_dispatch_count);
    printf("DEVICE_EVENT_COUNT %u\n", state.device_event_count);
    printf("EVENT_OVERFLOW %d\n", g_event_log.overflow);
    printf("TRACE_LEN %u\n", g_ops_len);
    for (i = 0; i < g_ops_len; i++) printf("STEP 0x%08x %s\n", g_step_pcs[i], g_ops[i]);

    pcs = or_side_pc_table();
    seen = or_side_pc_seen();
    count = 0;
    for (i = 0; i < or_side_record_count(); i++) if (seen[i]) count++;
    printf("DISTINCT_PC_COUNT %u\n", count);
    for (i = 0; i < or_side_record_count(); i++) {
        if (seen[i]) printf("PC 0x%08x\n", pcs[i]);
    }
    post = or_side_post_entry_pcs(&count);
    printf("POST_ENTRY_COUNT %u\n", count);
    for (i = 0; i < count; i++) printf("POST_ENTRY 0x%08x\n", post[i]);
    printf("EVENT_COUNT %u\n", g_event_log.count);
    for (i = 0; i < g_event_log.count; i++) {
        printf("EVENT %u %u", g_event_log.events[i].kind, g_event_log.events[i].seq);
        for (j = 0; j < 12u; j++) printf(" 0x%08x", g_event_log.events[i].f[j]);
        printf("\n");
    }
    printf("END\n");
    return 0;
}
"""


def _generate_header(continuation_entry_pc: int, frontier_steps: int) -> str:
    return (_HEADER_TEMPLATE
            .replace("@@CONT_BUDGET@@", str(CONTINUATION_BUDGET))
            .replace("@@TOTAL_BUDGET@@", str(frontier_steps + CONTINUATION_BUDGET + 64))
            .replace("@@ENTRY_PC@@", f"0x{continuation_entry_pc:08x}")
            .replace("@@EVENT_CAP@@", str(EVENT_CAP))
            .replace("@@BIOS_LIMIT@@", str(BIOS_DISPATCH_LIMIT))
            .replace("@@DEVICE_LIMIT@@", str(DEVICE_EVENT_LIMIT)))


def _generate_runtime(analysis: SideEffectsAnalysis, ctx: SideEmissionContext,
                      recorded_frontier: dict[str, Any]) -> str:
    entry_pc = _parse_hex(recorded_frontier["attempted_frontier_pc"])
    op_name_cases = [f"        case 0x{rec.pc:08x}u: return \"{rec.op}\";" for rec in ctx.records]
    instruction_cases = []
    for rec in ctx.records:
        body = _emit_instruction_side(rec, ctx)
        instruction_cases.append(f"        case 0x{rec.pc:08x}u:\n" + "\n".join(body))
    pc_table = []
    for index, rec in enumerate(ctx.records):
        pc_table.append(f"    0x{rec.pc:08x}u,")
    op_table = []
    for rec in ctx.records:
        op_table.append(f"    \"{rec.op}\",")
    title_payload = analysis.base.title.identity.payload
    mainexe_payload = analysis.base.mainexe.identity.payload
    vocabulary = sorted({rec.op for rec in ctx.records if rec.op in SIDE_SUPPORTED_OPS})
    provenance_digest = _sha256_bytes(
        json.dumps([rec.provenance_digest for rec in ctx.records], sort_keys=True).encode("utf-8")
    )
    return (_RUNTIME_TEMPLATE
            .replace("@@VOCAB@@", ", ".join(vocabulary))
            .replace("@@PROV@@", provenance_digest)
            .replace("@@RECORD_COUNT@@", str(len(ctx.records)))
            .replace("@@TITLE_LEN@@", str(len(title_payload)))
            .replace("@@TITLE_LITERAL@@", emitter._hex_bytes(title_payload))
            .replace("@@MAINEXE_LEN@@", str(len(mainexe_payload)))
            .replace("@@MAINEXE_LITERAL@@", emitter._hex_bytes(mainexe_payload))
            .replace("@@PC_TABLE@@", "\n".join(pc_table))
            .replace("@@OP_TABLE@@", "\n".join(op_table))
            .replace("@@POST_ENTRY_CAP@@", str(POST_ENTRY_CAP))
            .replace("@@OPNAME_CASES@@", "\n".join(op_name_cases))
            .replace("@@INSTRUCTION_CASES@@", "\n".join(instruction_cases))
            .replace("@@TITLE_OFFSET@@",
                     f"0x{analysis.base.title_text_addr - emitter.RAM_KSEG0_BASE:08x}")
            .replace("@@MAINEXE_OFFSET@@",
                     f"0x{analysis.mainexe_text_addr - emitter.RAM_KSEG0_BASE:08x}")
            .replace("@@ENTRY@@", f"0x{entry_pc:08x}"))


def _generate_harness(ctx: SideEmissionContext) -> str:
    provenance_digest = _sha256_bytes(
        json.dumps([rec.provenance_digest for rec in ctx.records], sort_keys=True).encode("utf-8")
    )
    return (_HARNESS_TEMPLATE
            .replace("@@TRACE_CAP@@", str(TRACE_CAP))
            .replace("@@SCHEMA@@", HARNESS_SCHEMA)
            .replace("@@PROV@@", provenance_digest)
            .replace("@@ENTRY@@", f"0x{cont.TITLE_ENTRY_PC:08x}"))


def _parse_runtime_stdout(text: str) -> dict[str, Any]:
    """Parse the deterministic line protocol emitted by the harness."""
    if "END\n" not in text and not text.rstrip().endswith("END"):
        raise SideEffectsError("RUNTIME_OUTPUT_TRUNCATED")
    result: dict[str, Any] = {
        "distinct_executed_pcs": [],
        "post_entry_pcs": [],
        "events": [],
        "step_trace": [],
        "trace_length": 0,
    }
    integer_fields = {
        "EXECUTED": "executed_instruction_count",
        "CONTINUATION_ENTRY_STEPS": "continuation_entry_steps",
        "CONTINUATION_EXECUTED": "continuation_executed_count",
        "BIOS_DISPATCH_COUNT": "bios_dispatch_count",
        "DEVICE_EVENT_COUNT": "device_event_count",
        "TRACE_LEN": "trace_length",
    }
    hex_fields = {
        "ENTRY_PC": "entry_pc",
        "FINAL_PC": "final_pc",
        "LAST_EXECUTED_PC": "last_successfully_executed_pc",
        "ATTEMPTED_FRONTIER_PC": "attempted_frontier_pc",
    }
    string_fields = {
        "SCHEMA": "schema",
        "STOP_REASON": "stop_reason",
        "REGISTER_DIGEST": "register_digest",
        "RAM_DIGEST": "ram_digest",
        "PROVENANCE_DIGEST": "provenance_digest",
    }
    for line in text.splitlines():
        if not line or line == "END":
            continue
        parts = line.split(" ")
        key = parts[0]
        if key in integer_fields:
            result[integer_fields[key]] = int(parts[1])
        elif key in hex_fields:
            result[hex_fields[key]] = parts[1]
        elif key in string_fields:
            result[string_fields[key]] = parts[1]
        elif key == "EVENT_OVERFLOW":
            result["event_overflow"] = bool(int(parts[1]))
        elif key == "PC":
            result["distinct_executed_pcs"].append(parts[1])
        elif key == "POST_ENTRY":
            result["post_entry_pcs"].append(parts[1])
        elif key == "EVENT":
            result["events"].append({
                "kind": int(parts[1]),
                "seq": int(parts[2]),
                "fields": [int(value, 16) for value in parts[3:15]],
            })
        elif key == "STEP":
            if len(parts) != 3:
                raise SideEffectsError("RUNTIME_OUTPUT_STEP_MALFORMED", line)
            result["step_trace"].append({"pc": parts[1], "op": parts[2]})
        elif key in ("DISTINCT_PC_COUNT", "POST_ENTRY_COUNT", "EVENT_COUNT"):
            result[key.lower()] = int(parts[1])
        else:
            raise SideEffectsError("RUNTIME_OUTPUT_UNKNOWN_FIELD", key)
    for required in ("schema", "stop_reason", "executed_instruction_count",
                     "continuation_entry_steps", "final_pc"):
        if required not in result:
            raise SideEffectsError("RUNTIME_OUTPUT_FIELD_MISSING", required)
    if result["schema"] != HARNESS_SCHEMA:
        raise SideEffectsError("RUNTIME_OUTPUT_SCHEMA_MISMATCH")
    if result.get("distinct_pc_count") != len(result["distinct_executed_pcs"]):
        raise SideEffectsError("RUNTIME_OUTPUT_PC_COUNT_MISMATCH")
    if result.get("post_entry_count") != len(result["post_entry_pcs"]):
        raise SideEffectsError("RUNTIME_OUTPUT_POST_ENTRY_COUNT_MISMATCH")
    if result.get("event_count") != len(result["events"]):
        raise SideEffectsError("RUNTIME_OUTPUT_EVENT_COUNT_MISMATCH")
    # The per-step trace must account for exactly the instructions the runtime
    # reports as executed, so per-step op accounting is bound to real execution
    # rather than to the set of distinct PCs visited.
    if int(result.get("trace_length", 0)) != len(result["step_trace"]):
        raise SideEffectsError(
            "RUNTIME_OUTPUT_STEP_COUNT_MISMATCH",
            f"reported={result.get('trace_length')} parsed={len(result['step_trace'])}",
        )
    if len(result["step_trace"]) != int(result.get("executed_instruction_count", 0)):
        raise SideEffectsError(
            "RUNTIME_OUTPUT_STEP_COUNT_VS_EXECUTED_MISMATCH",
            f"steps={len(result['step_trace'])} "
            f"executed={result.get('executed_instruction_count')}",
        )
    result["frontier_pc"] = result["final_pc"]
    # Derived schema fields. The harness-reported DISTINCT_PC_COUNT is already
    # checked against the PC list above, so these are bound to the same value the
    # runtime actually emitted rather than recomputed independently.
    result["distinct_executed_pc_count"] = len(result["distinct_executed_pcs"])
    result["post_entry_pc_count"] = len(result["post_entry_pcs"])
    return result


def provenance_digest_map(analysis: SideEffectsAnalysis) -> dict[int, str]:
    return {pc: emitter._provenance_digest_for_pc(analysis, pc)
            for pc in analysis.provenance}


def executed_vocabulary(analysis: SideEffectsAnalysis,
                        step_trace: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-executed-instruction op and region counts.

    Derived from the runtime's per-step trace (one entry per executed
    instruction), so the counts sum to the executed-instruction total. Counting
    distinct PCs instead would silently under-report repeated execution.
    """
    counts: dict[str, int] = {}
    region_counts: dict[str, int] = {}
    for step in step_trace:
        pc = int(str(step["pc"]), 16)
        if analysis.records_by_address.get(pc) is None:
            raise SideEffectsError("EXECUTED_PC_NOT_AUTHENTICATED", _hex32(pc))
        op = str(step["op"])
        counts[op] = counts.get(op, 0) + 1
        region = analysis.region_of(pc)
        region_counts[region] = region_counts.get(region, 0) + 1
    return {
        "op_counts": dict(sorted(counts.items())),
        "exercised": sorted(counts),
        "region_counts": dict(sorted(region_counts.items())),
    }


def frontier_block(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "stop_reason": result["stop_reason"],
        "last_successfully_executed_pc": result["last_successfully_executed_pc"],
        "attempted_frontier_pc": result["attempted_frontier_pc"],
        "frontier_pc": result["frontier_pc"],
        "final_pc": result["final_pc"],
        "continuation_entry_steps": result["continuation_entry_steps"],
        "continuation_executed_count": result["continuation_executed_count"],
        "executed_instruction_count": result["executed_instruction_count"],
        "distinct_executed_pc_count": len(result["distinct_executed_pcs"]),
    }


#: Recorded P17-05R continuation evidence (authoritative for the frontier step
#: count that the P17-06R replay must reproduce).
P17_05R_CONTINUATION = ROOT / ".openrecomp-phase17/evidence/P17-05R/continuation.json"


def recorded_p17_05r_frontier_steps(frontier: dict[str, Any] | None = None) -> int:
    """Authentic instruction count at the recorded P17-05R frontier.

    Read from the committed P17-05R continuation evidence so the P17-06R replay
    can be checked against it; nothing is hard-coded here.
    """
    if not P17_05R_CONTINUATION.is_file():
        raise SideEffectsError("P17_05R_CONTINUATION_EVIDENCE_MISSING")
    try:
        document = json.loads(P17_05R_CONTINUATION.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SideEffectsError("P17_05R_CONTINUATION_EVIDENCE_MALFORMED") from exc
    if (document.get("schema") != "openrecomp-phase17-continuation-v1"
            or document.get("stage") != "P17-05R"):
        raise SideEffectsError("P17_05R_CONTINUATION_EVIDENCE_MISMATCH")
    steps = int(document.get("executed_instruction_count") or 0)
    if steps <= 0:
        raise SideEffectsError("P17_05R_CONTINUATION_STEPS_INVALID")
    if frontier is not None:
        title_prefix = int(frontier.get("title_prefix_executed_count") or 0)
        mainexe = int(frontier.get("mainexe_executed_count") or 0)
        if steps < title_prefix + mainexe:
            raise SideEffectsError("P17_05R_CONTINUATION_STEPS_INCONSISTENT")
    return steps


def _build_private_mapping(analysis: SideEffectsAnalysis, ctx: SideEmissionContext
                           ) -> dict[str, Any]:
    entries = []
    for index, rec in enumerate(ctx.records):
        word = analysis.read_authenticated_word(rec.pc)
        entries.append({
            "index": index,
            "region": analysis.region_of(rec.pc),
            "guest_pc": _hex32(rec.pc),
            "authenticated_source_word": f"0x{word:08x}",
            "decoded_record": rec.asdict(),
            "provenance_digest": rec.provenance_digest,
        })
    return {
        "schema": "openrecomp-phase17-side-effects-private-mapping-v1",
        "stage": STAGE,
        "title_payload_sha256": analysis.base.title.projection["provenance"]["title_payload_sha256"],
        "mainexe_file_sha256": analysis.base.mainexe.file_sha256,
        "mainexe_payload_sha256": analysis.base.mainexe.payload_sha256,
        "continuation_entry_pc": _hex32(analysis.continuation_entry_pc),
        "record_count": len(entries),
        "records": entries,
    }


def emit_side_effects_executable(analysis: SideEffectsAnalysis, run_dir: pathlib.Path,
                                 *, recorded_frontier: dict[str, Any] | None = None,
                                 frontier_steps: int | None = None,
                                 allow_entry_stop: bool = False) -> dict[str, Any]:
    """Emit, compile, run and persist the authenticated P17-06R runtime."""
    if recorded_frontier is None:
        recorded_frontier = recorded_p17_05r_frontier()
    if frontier_steps is None:
        frontier_steps = recorded_p17_05r_frontier_steps(recorded_frontier)
    entry_pc = _parse_hex(recorded_frontier["attempted_frontier_pc"])
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    ctx = SideEmissionContext(analysis=analysis)
    ctx.records = emitter._make_semantic_records(analysis)
    ctx.record_by_pc = {rec.pc: rec for rec in ctx.records}
    ctx.index_by_pc = {rec.pc: index for index, rec in enumerate(ctx.records)}

    h_path = run_dir / "or_side_effects_v1.h"
    c_path = run_dir / "or_side_effects_v1.c"
    harness_path = run_dir / "or_side_effects_harness_v1.c"
    ctx.h_path, ctx.c_path, ctx.harness_path = h_path, c_path, harness_path
    h_path.write_text(_generate_header(entry_pc, frontier_steps),
                      encoding="utf-8", newline="\n")
    c_path.write_text(_generate_runtime(analysis, ctx, recorded_frontier),
                      encoding="utf-8", newline="\n")
    harness_path.write_text(_generate_harness(ctx), encoding="utf-8", newline="\n")

    so_path = run_dir / "or_side_effects_v1.so"
    exe_path = run_dir / "or_side_effects_v1"
    ctx.so_path, ctx.exe_path = so_path, exe_path
    include_flag = f"-I{run_dir}"
    so_cmd = emitter._compile_c(c_path, so_path, extra_flags=("-shared", "-fPIC", include_flag))
    exe_cmd = emitter._compile_c(harness_path, exe_path,
                                 extra_flags=(include_flag, str(c_path)))
    completed = subprocess.run([str(exe_path)], capture_output=True)
    if completed.returncode != 0:
        raise SideEffectsError("RUNTIME_EXIT_NONZERO",
                               completed.stderr.decode("utf-8", "replace")[:200])
    stdout_text = completed.stdout.decode("utf-8")
    rr = _parse_runtime_stdout(stdout_text)

    # --- Fail-closed frontier / provenance classification ------------------
    if rr["stop_reason"] not in ALLOWED_STOP_REASONS:
        raise SideEffectsError("UNTYPED_STOP_REASON", str(rr["stop_reason"]))
    if int(rr["continuation_entry_steps"]) != int(frontier_steps):
        raise SideEffectsError(
            "CONTINUATION_ENTRY_STEPS_MISMATCH",
            f"live={rr['continuation_entry_steps']} recorded={frontier_steps}",
        )
    if int(rr["continuation_executed_count"]) < 0:
        raise SideEffectsError("CONTINUATION_EXECUTED_NEGATIVE")
    if int(rr["continuation_executed_count"]) > CONTINUATION_BUDGET:
        raise SideEffectsError("CONTINUATION_BUDGET_EXCEEDED",
                               str(rr["continuation_executed_count"]))
    if rr["executed_instruction_count"] != (frontier_steps + rr["continuation_executed_count"]):
        raise SideEffectsError("EXECUTED_COUNT_INCONSISTENT")
    stopped_at_entry = (
        rr["stop_reason"] == "PC_NOT_IN_AUTHENTICATED_TABLE"
        and int(str(rr["attempted_frontier_pc"]), 16) == entry_pc
    )
    if stopped_at_entry:
        # Frontier-discovery probe: this table legitimately stops exactly at the
        # not-yet-authenticated continuation entry.
        if not allow_entry_stop:
            raise SideEffectsError("CONTINUATION_ENTRY_NOT_EXECUTED")
        if int(rr["continuation_executed_count"]) != 0:
            raise SideEffectsError("CONTINUATION_ENTRY_STOP_WITH_PROGRESS")
    else:
        if not rr["post_entry_pcs"] or int(rr["post_entry_pcs"][0], 16) != entry_pc:
            raise SideEffectsError("CONTINUATION_ENTRY_NOT_EXECUTED")
    if int(rr["trace_length"]) != int(rr["executed_instruction_count"]):
        raise SideEffectsError(
            "EXECUTED_TRACE_LENGTH_MISMATCH",
            f"trace={rr['trace_length']} executed={rr['executed_instruction_count']}",
        )
    if rr.get("event_overflow"):
        raise SideEffectsError("DEVICE_EVENT_LOG_OVERFLOW")

    vocabulary = executed_vocabulary(analysis, rr["step_trace"])
    if sum(vocabulary["op_counts"].values()) != int(rr["executed_instruction_count"]):
        raise SideEffectsError("EXECUTED_OP_COUNT_SUM_MISMATCH")
    missing = sorted(set(vocabulary["exercised"]) - SIDE_SUPPORTED_OPS)
    if missing:
        raise SideEffectsError("EXERCISED_OP_NOT_IMPLEMENTED", ",".join(missing))

    provenance_map = provenance_digest_map(analysis)
    for raw in rr["distinct_executed_pcs"]:
        pc = int(str(raw), 16)
        if pc not in provenance_map:
            raise SideEffectsError("EXECUTED_PC_WITHOUT_PROVENANCE", _hex32(pc))

    device_events = [raw for raw in rr["events"]
                     if raw["kind"] == transcript_model.KIND_BIOS_DISPATCH]
    mmio_events = [raw for raw in rr["events"]
                   if raw["kind"] == transcript_model.KIND_MMIO]
    if len(device_events) != int(rr["bios_dispatch_count"]):
        raise SideEffectsError("BIOS_DISPATCH_COUNT_MISMATCH")
    if len(mmio_events) != int(rr["device_event_count"]):
        raise SideEffectsError("DEVICE_EVENT_COUNT_MISMATCH")

    events: list[dict[str, Any]] = []
    for raw in rr["events"]:
        fields = raw["fields"]
        if raw["kind"] == transcript_model.KIND_BIOS_DISPATCH:
            events.append(transcript_model.bios_event(
                sequence=raw["seq"], vector_pc=fields[0], function=fields[1],
                args=fields[2:6], ra=fields[6], sp=fields[7], gp=fields[8],
                owning_instruction_pc=fields[9],
                delay_slot_pc=fields[10] if fields[10] else None))
        elif raw["kind"] == transcript_model.KIND_MMIO:
            events.append(transcript_model.mmio_event(
                sequence=raw["seq"], address=fields[1], store=bool(fields[0]),
                width=fields[2], value=fields[3], owning_instruction_pc=fields[4],
                delay_slot_pc=fields[5] if fields[5] else None))
        else:
            raise SideEffectsError("DEVICE_EVENT_KIND_UNKNOWN", str(raw["kind"]))
    events = transcript_model.attach_provenance(events, provenance_map)
    transcript_doc = transcript_model.transcript_document(
        stage=STAGE, next_stage=NEXT_STAGE, events=events,
        bios_dispatch_count=int(rr["bios_dispatch_count"]),
        device_event_count=int(rr["device_event_count"]),
        continuation_entry_pc=entry_pc, stop_reason=rr["stop_reason"])
    transcript_model.validate_transcript(transcript_doc, provenance_map)
    transcript_bytes = transcript_model.canonical_bytes(transcript_doc)
    transcript_sha256 = transcript_model.sha256_bytes(transcript_bytes)

    private_map = _build_private_mapping(analysis, ctx)
    private_map_path = run_dir / "private_mapping.json"
    map_bytes = (json.dumps(private_map, indent=2, sort_keys=True) + "\n").encode("utf-8")
    private_map_path.write_bytes(map_bytes)

    hashes = {
        "generated_source_sha256": _sha256_file(c_path),
        "generated_header_sha256": _sha256_file(h_path),
        "generated_harness_sha256": _sha256_file(harness_path),
        "shared_object_sha256": _sha256_file(so_path),
        "executable_sha256": _sha256_file(exe_path),
        "private_mapping_sha256": _sha256_bytes(map_bytes),
    }
    metadata = {
        "schema": "openrecomp-phase17-side-effects-build-metadata-v1",
        "stage": STAGE,
        "private_build_root_env_var": emitter.PRIVATE_BUILD_ROOT_ENV,
        "compiler_command_shared_object": emitter._public_command(so_cmd, run_dir),
        "compiler_command_executable": emitter._public_command(exe_cmd, run_dir),
        "path_normalization": "<private-run-dir> = run directory beneath the configured private build root",
        "toolchain": emitter._toolchain_identity(),
        "generated_source_sha256": hashes["generated_source_sha256"],
        "generated_header_sha256": hashes["generated_header_sha256"],
        "generated_harness_sha256": hashes["generated_harness_sha256"],
        "private_mapping_sha256": hashes["private_mapping_sha256"],
        "shared_object_sha256": hashes["shared_object_sha256"],
        "executable_sha256": hashes["executable_sha256"],
        "generated_source_bytes": c_path.stat().st_size,
        "shared_object_bytes": so_path.stat().st_size,
        "executable_bytes": exe_path.stat().st_size,
        "semantic_record_count": len(ctx.records),
        "continuation_entry_pc": _hex32(analysis.continuation_entry_pc),
        "continuation_budget": CONTINUATION_BUDGET,
        "p17_05r_frontier_steps": frontier_steps,
        "transcript_sha256": transcript_sha256,
    }
    metadata_path = run_dir / "build_metadata.json"
    meta_bytes = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8")
    metadata_path.write_bytes(meta_bytes)

    (run_dir / "transcript.json").write_bytes(transcript_bytes)
    (run_dir / "transcript.sha256").write_text(
        f"{transcript_sha256}  transcript.json\n", encoding="utf-8", newline="\n")

    # The per-step trace is large and redundant with the published op counts, so
    # it stays out of the public manifest; the counts derived from it are
    # published instead.
    rr_public = {key: value for key, value in rr.items()
                 if key not in ("events", "step_trace")}
    rr_public["event_count"] = len(events)
    provenance_digest = _sha256_bytes(
        json.dumps([rec.provenance_digest for rec in ctx.records], sort_keys=True).encode("utf-8"))

    persisted = {
        "root_env_var": emitter.PRIVATE_BUILD_ROOT_ENV,
        "artifacts": {
            name: {
                "name": filename,
                "sha256": _sha256_file(run_dir / filename),
                "bytes": (run_dir / filename).stat().st_size,
            }
            for name, filename in PERSISTED_ARTIFACTS
        },
        "private_mapping_record_count": len(ctx.records),
    }

    manifest: dict[str, Any] = {
        "schema": "openrecomp-phase17-side-effects-emission-v1",
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "emission_kind": "AUTHENTICATED_GENERATED_C_SIDE_EFFECT_RUNTIME",
        "interface": {
            "header": "or_side_effects_v1.h",
            "execute_symbol": "or_side_execute_v1",
            "guest_state_struct": "or_side_guest_state_v1",
            "services_struct": "or_side_runtime_services_v1",
            "event_struct": "or_side_event_v1",
        },
        "persistence": persisted,
        "source": {
            "title_projection_digest": analysis.base.title.projection["projection_digest"],
            "title_payload_sha256": analysis.base.title.projection["provenance"]["title_payload_sha256"],
            "mainexe_file_sha256": analysis.base.mainexe.file_sha256,
            "mainexe_payload_sha256": analysis.base.mainexe.payload_sha256,
            "continuation_entry_pc": _hex32(entry_pc),
            "p17_05r_frontier_steps": frontier_steps,
            "entry_pc": _hex32(cont.TITLE_ENTRY_PC),
            "record_count": len(ctx.records),
            "title_record_count": analysis.title_record_count,
            "mainexe_record_count": analysis.mainexe_record_count,
            "record_count_by_region": {
                "TITLE": analysis.title_record_count,
                "MAIN_EXE": analysis.mainexe_record_count,
            },
            "generated_source_sha256": hashes["generated_source_sha256"],
            "generated_harness_sha256": hashes["generated_harness_sha256"],
            "implemented_semantic_vocabulary": sorted(SIDE_SUPPORTED_OPS),
            "implemented_semantic_vocabulary_count": len(SIDE_SUPPORTED_OPS),
            "p17_05r_implemented_semantic_vocabulary": sorted(emitter.SUPPORTED_OPS),
            "additional_implemented_semantic_vocabulary": sorted(ADDITIONAL_OPS),
            "exercised_semantic_vocabulary": vocabulary["exercised"],
            "exercised_semantic_vocabulary_count": len(vocabulary["exercised"]),
            "executed_op_counts": vocabulary["op_counts"],
            "executed_region_counts": vocabulary["region_counts"],
            "provenance_digest": provenance_digest,
        },
        "device_layer": {
            "bios_dispatch_model": transcript_model.BIOS_MODEL,
            "bios_internals": transcript_model.BIOS_INTERNALS,
            "mmio_read_model": transcript_model.MMIO_READ_MODEL,
            "mmio_write_model": transcript_model.MMIO_WRITE_MODEL,
            "bios_vectors_modeled": ["A0", "B0", "C0"],
            "device_traffic_reached": bool(events),
        },
        "transcript": {
            "sha256": transcript_sha256,
            "event_count": len(events),
            "bios_dispatch_count": int(rr["bios_dispatch_count"]),
            "device_event_count": int(rr["device_event_count"]),
            "event_class_counts": transcript_doc["event_class_counts"],
        },
        "build": {
            "toolchain": metadata["toolchain"],
            "executable_sha256": hashes["executable_sha256"],
            "shared_object_sha256": hashes["shared_object_sha256"],
            "build_metadata_sha256": _sha256_bytes(meta_bytes),
            "runtime_result_schema": HARNESS_SCHEMA,
        },
        "active_build": {
            "phase17_emitter": "p17_side_effects_exec_v1.py",
            "frozen_decoder": "p3_decode_mips32_v1.classify (unchanged)",
            "frozen_frontier_engine": "p3_code_frontier_v1.analyze (unchanged)",
            "phase16_hand_authored_title_guest_flow": "EXCLUDED",
            "execution": "GENERATED_NATIVE_RUNTIME",
        },
        "frontier": frontier_block(rr),
        "region_log": list(analysis.region_log),
        "runtime_result": rr_public,
        "claims": {
            "initialization": "NOT_PROVEN",
            "frame": "NOT_PROVEN",
            "playability": "NOT_PROVEN",
            "general_compatibility": "NOT_PROVEN",
            "first_frame_ready": "NO",
        },
        "transcript_document": transcript_doc,
    }
    manifest["emission_digest"] = emitter._digest_dict(manifest, "emission_digest")
    return manifest


def discover_continuation(analysis: SideEffectsAnalysis, generations_dir: pathlib.Path,
                          *, recorded_frontier: dict[str, Any] | None = None,
                          frontier_steps: int | None = None
                          ) -> tuple[dict[str, Any], list[dict[str, Any]], SideEffectsAnalysis]:
    """Discover the dynamic frontier with the emitted runtime as the authority."""
    if recorded_frontier is None:
        recorded_frontier = recorded_p17_05r_frontier()
    if frontier_steps is None:
        frontier_steps = recorded_p17_05r_frontier_steps(recorded_frontier)
    generations_dir = generations_dir.resolve()
    observations: list[dict[str, Any]] = []
    manifest: dict[str, Any] | None = None
    for generation in range(MAX_DISCOVERY_ROUNDS):
        run_dir = generations_dir / f"generation-{generation}"
        # The emitted table always carries the complete authenticated set: a
        # reduced probe would stop at authenticated-but-unemitted PCs and could
        # not be distinguished from a genuine unauthenticated frontier.
        manifest = emit_side_effects_executable(
            analysis, run_dir, recorded_frontier=recorded_frontier,
            frontier_steps=frontier_steps, allow_entry_stop=True)
        rr = manifest["runtime_result"]
        observations.append({
            "generation": generation,
            "authenticated_record_count": analysis.record_count,
            "stop_reason": rr["stop_reason"],
            "attempted_frontier_pc": rr["attempted_frontier_pc"],
            "executed_instruction_count": rr["executed_instruction_count"],
            "continuation_executed_count": rr["continuation_executed_count"],
            "bios_dispatch_count": rr["bios_dispatch_count"],
            "device_event_count": rr["device_event_count"],
        })
        if rr["stop_reason"] != "PC_NOT_IN_AUTHENTICATED_TABLE":
            break
        new_pc = int(str(rr["attempted_frontier_pc"]), 16)
        if new_pc in analysis.reachable:
            raise SideEffectsError("AUTHENTICATED_PC_NOT_IN_EMITTED_TABLE",
                                   _hex32(new_pc))
        extension = analysis.authenticate_and_extend(new_pc)
        if extension["added"] == 0:
            break
    if manifest is None:
        raise SideEffectsError("DISCOVERY_NOT_EXECUTED")
    return manifest, observations, analysis
