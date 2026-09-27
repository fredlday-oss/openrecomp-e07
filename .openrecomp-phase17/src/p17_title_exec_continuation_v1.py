#!/usr/bin/env python3
"""OpenRecomp Phase-17 P17-05R authenticated execution continuation V1.

P17-04R executed 37 authentic TITLE instructions and stopped with
PC_NOT_IN_AUTHENTICATED_TABLE after the authentic JAL at 0x8003812c (delay slot
0x80038130) transferred to 0x80011af0.  That destination lies inside the main game
executable, which the bounded TITLE-only P17-02 projection legitimately does not
cover.

This module extends the authenticated record set with the main-EXE records
reachable from that continuation entry, using the SAME frozen decoder and the
SAME canonical checked-equality discipline as P17-04R, and emits compiled
runtimes that resume from the recorded P17-04R frontier state and continue real
authenticated guest execution for a bounded number of newly authenticated
main-EXE instructions.

Fail-closed: any unauthenticated address, unverified word, unsupported semantic,
unmapped address, non-reproducible TITLE prefix, or non-advancing frontier
rejects the build before/at emission.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import struct
import sys
from dataclasses import dataclass, field
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _extra in ("", ".openrecomp-phase17/src", ".openrecomp-phase3/src",
               ".openrecomp-phase9/src"):
    _path = str(ROOT / _extra) if _extra else str(ROOT)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import p17_mainexe_auth_v1 as mainexe_auth
import p17_title_decode_v1 as title_decode
import p17_title_exec_emit_v1 as emitter

#: The recorded P17-04R frontier state (the committed evidence is authoritative
#: for the continuation entry; the live TITLE prefix must reproduce it).
P17_04R_RESULT = ROOT / ".openrecomp-phase17/evidence/P17-04R/RESULT.json"

#: Hard execution bound for newly authenticated main-EXE instructions.
CONTINUATION_BUDGET = 4096
#: Total step budget (TITLE prefix + continuation) kept as a safety net.
TOTAL_STEP_BUDGET = 100000
#: Wall-clock trace capacity; must exceed TOTAL_STEP_BUDGET.
TRACE_CAP = 131072
MAINEXE_PC_CAP = 8192

NEXT_STAGE = "P17-06R"

# Deterministic private build root for this stage.  OPENRECOMP_P17_PRIVATE_BUILD_ROOT
# overrides the default; nothing path-bearing is ever committed to public evidence.
DEFAULT_PRIVATE_BUILD_ROOT = pathlib.Path("/home/fred/OpenRecomp/private-build/phase17/P17-05R")
PRIVATE_BUILD_ROOT_ENV = emitter.PRIVATE_BUILD_ROOT_ENV
OFFICIAL_RUN_DIRS = ("official-run-1", "official-run-2")


def private_build_root() -> pathlib.Path:
    """Resolve the deterministic private build root (env override honoured)."""
    override = os.environ.get(PRIVATE_BUILD_ROOT_ENV)
    if override:
        return pathlib.Path(override)
    return DEFAULT_PRIVATE_BUILD_ROOT


def official_run_dir(label: str, root: pathlib.Path | None = None) -> pathlib.Path:
    """Return a fresh official run directory beneath the private build root."""
    base = root if root is not None else private_build_root()
    return base / label

PERSISTED_ARTIFACTS = (
    ("generated_source", "or_title_continuation_v1.c"),
    ("generated_header", "or_title_continuation_v1.h"),
    ("generated_harness", "or_title_continuation_harness_v1.c"),
    ("private_mapping", "private_mapping.json"),
    ("build_metadata", "build_metadata.json"),
    ("shared_object", "or_title_continuation_v1.so"),
    ("executable", "or_title_continuation_v1"),
)

RAM_SIZE = 2 * 1024 * 1024
TITLE_ENTRY_PC = 0x800380A0


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest_dict(doc: dict[str, Any], exclude_key: str | None = None) -> str:
    body = {k: v for k, v in doc.items() if k != exclude_key}
    return _sha256_bytes(json.dumps(body, sort_keys=True).encode("utf-8"))


def _sha256_file(path: pathlib.Path) -> str:
    return _sha256_bytes(path.read_bytes())


class ContinuationError(ValueError):
    """Fail-closed continuation rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _parse_hex(value: Any) -> int:
    if isinstance(value, int):
        return value
    return int(str(value), 16)


def recorded_p17_04r_frontier(path: pathlib.Path | None = None) -> dict[str, Any]:
    """Load the recorded P17-04R frontier state from committed evidence."""
    source = path if path is not None else P17_04R_RESULT
    if not source.is_file():
        raise ContinuationError("P17_04R_EVIDENCE_MISSING", str(source.name))
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContinuationError("P17_04R_EVIDENCE_MALFORMED") from exc
    frontier = document.get("authentic_frontier")
    if not isinstance(frontier, dict):
        raise ContinuationError("P17_04R_FRONTIER_MISSING")
    for key in ("last_successfully_executed_pc", "attempted_frontier_pc", "frontier_pc",
                "executed_instruction_count", "stop_reason"):
        if key not in frontier:
            raise ContinuationError("P17_04R_FRONTIER_FIELD_MISSING", key)
    return frontier


@dataclass
class ContinuationAnalysis:
    """Merged authenticated record set across the TITLE -> main-EXE transition."""

    title: Any
    mainexe: mainexe_auth.MainExeAnalysis
    continuation_entry_pc: int
    records_by_address: dict[int, dict[str, Any]] = field(default_factory=dict)
    delay_by_owner: dict[int, int] = field(default_factory=dict)
    provenance: dict[int, Any] = field(default_factory=dict)
    frontier: dict[str, Any] = field(default_factory=dict)

    @property
    def title_text_addr(self) -> int:
        return self.title.identity.t_addr

    @property
    def title_text_end(self) -> int:
        return self.title.identity.text_end

    @property
    def mainexe_text_addr(self) -> int:
        return self.mainexe.identity.t_addr

    @property
    def mainexe_text_end(self) -> int:
        return self.mainexe.identity.t_addr + self.mainexe.identity.t_size

    @property
    def title_record_count(self) -> int:
        """Authenticated TITLE records actually emitted (reachable set only)."""
        return sum(1 for pc in self.frontier["reachable_addresses"] if self._is_title(pc))

    @property
    def mainexe_record_count(self) -> int:
        """Authenticated main-EXE records actually emitted (reachable set only)."""
        return sum(1 for pc in self.frontier["reachable_addresses"]
                   if not self._is_title(pc))

    def _is_title(self, pc: int) -> bool:
        return self.title_text_addr <= pc < self.title_text_end

    def _is_mainexe(self, pc: int) -> bool:
        return self.mainexe_text_addr <= pc < self.mainexe_text_end

    def read_authenticated_word(self, pc: int) -> int:
        """Resolve the authenticated source word for either region (fail closed)."""
        if self._is_title(pc):
            return emitter._read_authenticated_word(self.title, pc)
        if self._is_mainexe(pc):
            return mainexe_auth.read_authenticated_word(
                self.mainexe.identity, pc, file_bytes=self.mainexe.file_bytes or None
            )
        raise ContinuationError("PC_OUTSIDE_AUTHENTICATED_SOURCES", f"0x{pc:08x}")

    def region_of(self, pc: int) -> str:
        if self._is_title(pc):
            return "TITLE"
        if self._is_mainexe(pc):
            return "MAIN_EXE"
        return "OUTSIDE"


def build_continuation_analysis(
    *,
    title_analysis: Any | None = None,
    fixture_dir: pathlib.Path | None = None,
    continuation_entry_pc: int | None = None,
    recorded_frontier: dict[str, Any] | None = None,
) -> ContinuationAnalysis:
    """Build the merged authenticated record set for the continuation entry."""
    if title_analysis is None:
        title_analysis = title_decode.analyze_title_decode(fixture_dir=fixture_dir)
    emitter.verify_authenticated_analysis(title_analysis)

    if recorded_frontier is None:
        recorded_frontier = recorded_p17_04r_frontier()
    if continuation_entry_pc is None:
        continuation_entry_pc = _parse_hex(recorded_frontier["attempted_frontier_pc"])

    mainexe = mainexe_auth.build_mainexe_analysis(
        continuation_entry_pc, fixture_dir=fixture_dir
    )
    if mainexe.reachable_count < 1:
        raise ContinuationError("MAINEXE_REACHABLE_SET_EMPTY",
                                f"0x{continuation_entry_pc:08x}")

    records_by_address: dict[int, dict[str, Any]] = dict(title_analysis.records_by_address)
    overlap = sorted(set(records_by_address) & set(mainexe.records_by_address))
    if overlap:
        raise ContinuationError("AUTHENTICATED_REGION_OVERLAP",
                                ",".join(f"0x{pc:08x}" for pc in overlap))
    records_by_address.update(mainexe.records_by_address)

    delay_by_owner = dict(title_analysis.delay_by_owner)
    delay_by_owner.update(mainexe.delay_by_owner)

    provenance: dict[int, Any] = dict(title_analysis.provenance)
    provenance.update(mainexe.provenance)

    reachable = sorted(set(title_analysis.frontier["reachable_addresses"])
                       | set(mainexe.frontier["reachable_addresses"]))

    return ContinuationAnalysis(
        title=title_analysis,
        mainexe=mainexe,
        continuation_entry_pc=continuation_entry_pc,
        records_by_address=records_by_address,
        delay_by_owner=delay_by_owner,
        provenance=provenance,
        frontier={
            "reachable_addresses": reachable,
            "title_reachable_count": len(title_analysis.frontier["reachable_addresses"]),
            "mainexe_reachable_count": mainexe.reachable_count,
        },
    )


# --------------------------------------------------------------------------
# Generated runtime (header / source / harness)
# --------------------------------------------------------------------------

_HEADER_TEMPLATE = r"""/* Generated by p17_title_exec_continuation_v1.py from authenticated records. */
#ifndef OR_TITLE_CONTINUATION_V1_H
#define OR_TITLE_CONTINUATION_V1_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OR_CONT_RAM_SIZE 2097152u
#define OR_CONT_RAM_KSEG0_BASE 0x80000000u
#define OR_CONT_MAINEXE_TEXT_ADDR @@MAINEXE_ADDR@@u
#define OR_CONT_MAINEXE_TEXT_END @@MAINEXE_END@@u
#define OR_CONT_CONTINUATION_BUDGET @@CONT_BUDGET@@u
#define OR_CONT_TOTAL_BUDGET @@TOTAL_BUDGET@@u

/* Persistent guest-state container across the TITLE -> main-EXE transition. */
struct or_cont_guest_state_v1 {
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
};

/* Bounded runtime services.  All pointers may be NULL to select defaults. */
struct or_cont_runtime_services_v1 {
    void *user_data;
    void (*transcript)(void *user_data, uint32_t pc, const char *op, uint32_t step);
    int (*host_call)(void *user_data, const char *symbol,
                     const uint64_t *args, uint64_t argc,
                     uint64_t *out_value, uint32_t *out_has_value);
    uint8_t *ram_base;
    uint32_t ram_size;
    /* Returns non-zero to stop once the authenticated main-EXE continuation
       budget has been reached.  May be NULL. */
    int (*continuation_limit_reached)(void *user_data);
};

int or_cont_execute_v1(struct or_cont_guest_state_v1 *state,
                       const struct or_cont_runtime_services_v1 *services);

#ifdef __cplusplus
}
#endif

#endif
"""

_RUNTIME_C_TEMPLATE = r"""/* Generated by p17_title_exec_continuation_v1.py from authenticated records. */
/* Semantic vocabulary: @@VOCAB@@ */
/* Provenance digest: @@PROV@@ */
#include "or_title_continuation_v1.h"
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#define RAM_SIZE OR_CONT_RAM_SIZE
#define RAM_KSEG0_BASE OR_CONT_RAM_KSEG0_BASE

static uint8_t g_default_ram[RAM_SIZE];
static uint8_t *g_ram = g_default_ram;

static const uint8_t g_title_payload[@@TITLE_LEN@@] = {
@@TITLE_LITERAL@@
};

static const uint8_t g_mainexe_payload[@@MAINEXE_LEN@@] = {
@@MAINEXE_LITERAL@@
};

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
    return (uint16_t)g_ram[off] | ((uint16_t)g_ram[off + 1] << 8);
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

static void ram_digest(uint8_t *out) {
    uint32_t h0 = 0x6a09e667u, h1 = 0xbb67ae85u, h2 = 0x3c6ef372u, h3 = 0xa54ff53au;
    for (uint32_t i = 0; i < RAM_SIZE; i += 4) {
        uint32_t w = (uint32_t)g_ram[i] | ((uint32_t)g_ram[i + 1] << 8) |
                     ((uint32_t)g_ram[i + 2] << 16) | ((uint32_t)g_ram[i + 3] << 24);
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

static const char *op_name_for_pc(uint32_t pc) {
    switch (pc) {
@@OPNAME_CASES@@
        default: return "?";
    }
}

int or_cont_execute_v1(struct or_cont_guest_state_v1 *state,
                       const struct or_cont_runtime_services_v1 *services) {
    if (!state) return -1;
    if (services && services->ram_base) {
        if (services->ram_size != RAM_SIZE) {
            state->stop = 1;
            strncpy(state->stop_reason, "SERVICES_RAM_SIZE_MISMATCH", sizeof(state->stop_reason) - 1);
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

    while (!state->stop) {
        state->regs[0] = 0;
        if (state->step_count >= state->budget) {
            state->attempted_frontier_pc = state->pc;
            state->stop = 1;
            strncpy(state->stop_reason, "STEP_LIMIT_REACHED", sizeof(state->stop_reason) - 1);
            break;
        }
        if (services && services->continuation_limit_reached &&
            services->continuation_limit_reached(services->user_data)) {
            state->attempted_frontier_pc = state->pc;
            state->stop = 1;
            strncpy(state->stop_reason, "CONTINUATION_BUDGET_REACHED", sizeof(state->stop_reason) - 1);
            break;
        }
        state->next_pc = state->pc;
        state->attempted_frontier_pc = state->pc;
        switch (state->pc) {
@@INSTRUCTION_CASES@@
            default:
                state->stop = 1;
                strncpy(state->stop_reason, "PC_NOT_IN_AUTHENTICATED_TABLE", sizeof(state->stop_reason) - 1);
                break;
        }
    }
    return 0;
}
"""

_HARNESS_TEMPLATE = r"""/* Generated deterministic continuation harness for or_cont_execute_v1. */
#include "or_title_continuation_v1.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define RAM_SIZE OR_CONT_RAM_SIZE
#define TRACE_CAP @@TRACE_CAP@@u
#define MAINEXE_PC_CAP @@MAINEXE_PC_CAP@@u
#define MAINEXE_TEXT_ADDR OR_CONT_MAINEXE_TEXT_ADDR
#define MAINEXE_TEXT_END OR_CONT_MAINEXE_TEXT_END
#define CONTINUATION_BUDGET OR_CONT_CONTINUATION_BUDGET

static uint8_t g_harness_ram[RAM_SIZE];
static const char *g_ops[TRACE_CAP];
static uint32_t g_pcs[TRACE_CAP];
static uint32_t g_trace_len = 0;
static uint32_t g_mainexe_pcs[MAINEXE_PC_CAP];
static uint32_t g_mainexe_pc_len = 0;
static uint32_t g_mainexe_steps = 0;
static uint32_t g_title_steps = 0;
static uint32_t g_title_prefix_count = 0;
static uint32_t g_title_prefix_last_pc = 0;
static uint32_t g_first_mainexe_pc = 0;
static uint32_t g_prev_pc = 0;
static int g_crossed = 0;

static void trace_cb(void *user_data, uint32_t pc, const char *op, uint32_t step) {
    (void)user_data; (void)step;
    if (g_trace_len < TRACE_CAP) {
        g_pcs[g_trace_len] = pc;
        g_ops[g_trace_len] = (op != NULL) ? op : "?";
        g_trace_len++;
    }
    if (pc >= MAINEXE_TEXT_ADDR && pc < MAINEXE_TEXT_END) {
        if (!g_crossed) {
            g_crossed = 1;
            g_first_mainexe_pc = pc;
            g_title_prefix_count = g_title_steps;
            g_title_prefix_last_pc = g_prev_pc;
        }
        g_mainexe_steps++;
        if (g_mainexe_pc_len < MAINEXE_PC_CAP &&
            (g_mainexe_pc_len == 0 || g_mainexe_pcs[g_mainexe_pc_len - 1] != pc)) {
            g_mainexe_pcs[g_mainexe_pc_len++] = pc;
        }
    } else if (!g_crossed) {
        g_title_steps++;
    }
    g_prev_pc = pc;
}

static int continuation_limit_reached(void *user_data) {
    (void)user_data;
    return (g_mainexe_steps >= CONTINUATION_BUDGET) ? 1 : 0;
}

static void hex32(char *out, uint32_t value) {
    const char *hex = "0123456789abcdef";
    for (int i = 7; i >= 0; i--) {
        out[7 - i] = hex[(value >> (i * 4)) & 0xf];
    }
    out[8] = '\0';
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

static const char *transfer_name(int kind) {
    if (kind == 1) return "DIRECT_CALL";
    if (kind == 2) return "INDIRECT_CALL";
    return "NONE";
}

int main(void) {
    struct or_cont_guest_state_v1 state;
    struct or_cont_runtime_services_v1 services;
    memset(&state, 0, sizeof(state));
    memset(&services, 0, sizeof(services));
    state.pc = @@ENTRY@@u;
    state.budget = OR_CONT_TOTAL_BUDGET;
    services.ram_base = g_harness_ram;
    services.ram_size = RAM_SIZE;
    services.transcript = trace_cb;
    services.continuation_limit_reached = continuation_limit_reached;

    or_cont_execute_v1(&state, &services);

    uint8_t rdigest[16];
    ram_digest(rdigest);
    uint8_t regdigest[16];
    {
        uint32_t h0 = 0x6a09e667u, h1 = 0xbb67ae85u;
        for (int i = 0; i < 32; i++) {
            h0 ^= state.regs[i];
            h1 += state.regs[i];
        }
        h0 ^= state.pc ^ state.hi ^ state.lo;
        h1 += state.pc + state.hi + state.lo;
        regdigest[0] = (uint8_t)h0; regdigest[1] = (uint8_t)(h0 >> 8); regdigest[2] = (uint8_t)(h0 >> 16); regdigest[3] = (uint8_t)(h0 >> 24);
        regdigest[4] = (uint8_t)h1; regdigest[5] = (uint8_t)(h1 >> 8); regdigest[6] = (uint8_t)(h1 >> 16); regdigest[7] = (uint8_t)(h1 >> 24);
        regdigest[8] = (uint8_t)state.step_count; regdigest[9] = (uint8_t)(state.step_count >> 8);
        regdigest[10] = (uint8_t)state.stop; regdigest[11] = 0;
        memset(regdigest + 12, 0, 4);
    }

    char entry_str[9], stop_str[9], last_str[9], attempt_str[9];
    hex32(entry_str, @@ENTRY@@u);
    hex32(stop_str, state.pc);
    hex32(last_str, state.last_executed_pc);
    hex32(attempt_str, state.attempted_frontier_pc);

    printf("{\n");
    printf("  \"schema\": \"openrecomp-phase17-title-exec-continuation-result-v1\",\n");
    printf("  \"entry_pc\": \"0x%s\",\n", entry_str);
    printf("  \"executed_instruction_count\": %u,\n", state.step_count);
    printf("  \"trace_event_count\": %u,\n", g_trace_len);
    printf("  \"title_prefix_executed_count\": %u,\n", g_title_prefix_count);
    printf("  \"mainexe_executed_count\": %u,\n", g_mainexe_steps);
    printf("  \"mainexe_executed_pc_count\": %u,\n", g_mainexe_pc_len);
    printf("  \"final_pc\": \"0x%s\",\n", stop_str);
    printf("  \"stop_pc\": \"0x%s\",\n", stop_str);
    printf("  \"frontier_pc\": \"0x%s\",\n", stop_str);
    printf("  \"last_successfully_executed_pc\": \"0x%s\",\n", last_str);
    printf("  \"attempted_frontier_pc\": \"0x%s\",\n", attempt_str);
    printf("  \"stop_reason\": \"%s\",\n", state.stop_reason);
    printf("  \"pending_transfer_type\": \"%s\",\n", transfer_name(state.pending_transfer_type));
    printf("  \"pending_transfer_target\": \"0x%08x\",\n", state.pending_transfer_target);
    printf("  \"pending_transfer_applied\": %d,\n", state.pending_transfer_applied);
    printf("  \"delay_slot_owner_pc\": \"0x%08x\",\n", state.delay_slot_owner_pc);
    printf("  \"delay_slot_pc\": \"0x%08x\",\n", state.delay_pc);
    printf("  \"delay_active_at_stop\": %d,\n", state.delay_active);
    printf("  \"mainexe_first_pc\": \"0x%08x\",\n", g_first_mainexe_pc);
    printf("  \"title_prefix_last_executed_pc\": \"0x%08x\",\n", g_title_prefix_last_pc);
    printf("  \"mainexe_executed_pcs\": [");
    for (uint32_t i = 0; i < g_mainexe_pc_len; i++) {
        if (i) printf(", ");
        printf("\"0x%08x\"", g_mainexe_pcs[i]);
    }
    printf("],\n");
    printf("  \"register_digest\": \"");
    print_hex(regdigest, 16);
    printf("\",\n");
    printf("  \"ram_digest\": \"");
    print_hex(rdigest, 16);
    printf("\",\n");
    printf("  \"provenance_digest\": \"@@PROV@@\",\n");
    printf("  \"implemented_semantic_vocabulary\": [");
    const char *impl_vocabulary[] = {@@IMPL_VOCAB@@};
    for (size_t i = 0; i < @@IMPL_COUNT@@u; i++) {
        if (i) printf(", ");
        printf("\"%s\"", impl_vocabulary[i]);
    }
    printf("],\n");
    printf("  \"implemented_semantic_vocabulary_count\": @@IMPL_COUNT@@,\n");
    printf("  \"emitted_semantic_vocabulary\": [");
    const char *emitted_vocabulary[] = {@@EMITTED_VOCAB@@};
    for (size_t i = 0; i < @@EMITTED_COUNT@@u; i++) {
        if (i) printf(", ");
        printf("\"%s\"", emitted_vocabulary[i]);
    }
    printf("],\n");
    printf("  \"emitted_semantic_vocabulary_count\": @@EMITTED_COUNT@@,\n");
    printf("  \"executed_semantic_trace\": [");
    for (uint32_t i = 0; i < g_trace_len; i++) {
        if (i) printf(", ");
        printf("\"%s\"", g_ops[i]);
    }
    printf("],\n");
    printf("  \"executed_semantic_trace_length\": %u\n", g_trace_len);
    printf("}\n");
    return 0;
}
"""


def _generate_header(analysis: ContinuationAnalysis) -> str:
    return (_HEADER_TEMPLATE
            .replace("@@MAINEXE_ADDR@@", f"0x{analysis.mainexe_text_addr:08x}")
            .replace("@@MAINEXE_END@@", f"0x{analysis.mainexe_text_end:08x}")
            .replace("@@CONT_BUDGET@@", str(CONTINUATION_BUDGET))
            .replace("@@TOTAL_BUDGET@@", str(TOTAL_STEP_BUDGET)))


def _generate_runtime_c(analysis: ContinuationAnalysis,
                        ctx: emitter.EmissionContext) -> str:
    records = ctx.records
    ctx.record_by_pc = {rec.pc: rec for rec in records}

    op_name_cases: list[str] = []
    instruction_cases: list[str] = []
    for rec in records:
        op_name_cases.append(f"        case 0x{rec.pc:08x}u: return \"{rec.op}\";")
        label = f"        case 0x{rec.pc:08x}u:"
        body = emitter._emit_instruction(rec, ctx)
        instruction_cases.append(label + "\n" + "\n".join(body))

    title_payload = analysis.title.identity.payload
    mainexe_payload = analysis.mainexe.identity.payload
    vocabulary = sorted({rec.op for rec in records if rec.op in emitter.SUPPORTED_OPS})
    provenance_digest = _sha256_bytes(
        json.dumps([rec.provenance_digest for rec in records], sort_keys=True).encode("utf-8")
    )
    return (_RUNTIME_C_TEMPLATE
            .replace("@@VOCAB@@", ", ".join(vocabulary))
            .replace("@@PROV@@", provenance_digest)
            .replace("@@TITLE_LEN@@", str(len(title_payload)))
            .replace("@@TITLE_LITERAL@@", emitter._hex_bytes(title_payload))
            .replace("@@MAINEXE_LEN@@", str(len(mainexe_payload)))
            .replace("@@MAINEXE_LITERAL@@", emitter._hex_bytes(mainexe_payload))
            .replace("@@TITLE_OFFSET@@", f"0x{analysis.title_text_addr - emitter.RAM_KSEG0_BASE:08x}")
            .replace("@@MAINEXE_OFFSET@@", f"0x{analysis.mainexe_text_addr - emitter.RAM_KSEG0_BASE:08x}")
            .replace("@@OPNAME_CASES@@", "\n".join(op_name_cases))
            .replace("@@INSTRUCTION_CASES@@", "\n".join(instruction_cases)))


def _generate_harness_c(analysis: ContinuationAnalysis,
                        ctx: emitter.EmissionContext) -> str:
    provenance_digest = _sha256_bytes(
        json.dumps([rec.provenance_digest for rec in ctx.records], sort_keys=True).encode("utf-8")
    )
    implemented_vocabulary = sorted(emitter.SUPPORTED_OPS)
    impl_vocab_literal = ", ".join(f'"{op}"' for op in implemented_vocabulary)
    vocabulary = sorted({rec.op for rec in ctx.records if rec.op in emitter.SUPPORTED_OPS})
    vocab_literal = ", ".join(f'"{op}"' for op in vocabulary)
    return (_HARNESS_TEMPLATE
            .replace("@@ENTRY@@", f"0x{TITLE_ENTRY_PC:08x}")
            .replace("@@TRACE_CAP@@", str(TRACE_CAP))
            .replace("@@MAINEXE_PC_CAP@@", str(MAINEXE_PC_CAP))
            .replace("@@PROV@@", provenance_digest)
            .replace("@@IMPL_VOCAB@@", impl_vocab_literal)
            .replace("@@IMPL_COUNT@@", str(len(implemented_vocabulary)))
            .replace("@@EMITTED_VOCAB@@", vocab_literal)
            .replace("@@EMITTED_COUNT@@", str(len(vocabulary))))


def _build_private_mapping(analysis: ContinuationAnalysis,
                           ctx: emitter.EmissionContext) -> dict[str, Any]:
    """Full private authenticated mapping for both regions (never public)."""
    title_records: list[dict[str, Any]] = []
    mainexe_records: list[dict[str, Any]] = []
    for index, rec in enumerate(ctx.records):
        word = analysis.read_authenticated_word(rec.pc)
        region = analysis.region_of(rec.pc)
        entry = {
            "index": index,
            "region": region,
            "guest_pc": f"0x{rec.pc:08x}",
            "authenticated_source_word": f"0x{word:08x}",
            "decoded_record": rec.asdict(),
            "provenance_digest": rec.provenance_digest,
        }
        if region == "TITLE":
            title_records.append(entry)
        else:
            mainexe_records.append(entry)
    return {
        "schema": "openrecomp-phase17-title-exec-continuation-private-mapping-v1",
        "stage": "P17-05R",
        "title_payload_sha256": analysis.title.projection["provenance"]["title_payload_sha256"],
        "mainexe_file_sha256": analysis.mainexe.file_sha256,
        "mainexe_payload_sha256": analysis.mainexe.payload_sha256,
        "continuation_entry_pc": f"0x{analysis.continuation_entry_pc:08x}",
        "title_records": title_records,
        "mainexe_records": mainexe_records,
    }


def _build_metadata_document(run_dir: pathlib.Path, so_cmd: list[str], exe_cmd: list[str],
                             hashes: dict[str, str], record_count: int,
                             analysis: ContinuationAnalysis) -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase17-title-exec-continuation-build-metadata-v1",
        "stage": "P17-05R",
        "private_build_root_env_var": emitter.PRIVATE_BUILD_ROOT_ENV,
        "compiler_command_shared_object": emitter._public_command(so_cmd, run_dir),
        "compiler_command_executable": emitter._public_command(exe_cmd, run_dir),
        "path_normalization": "<private-run-dir> = the run directory beneath the configured private build root",
        "toolchain": emitter._toolchain_identity(),
        "generated_source_sha256": hashes["generated_source_sha256"],
        "generated_header_sha256": hashes["generated_header_sha256"],
        "generated_harness_sha256": hashes["generated_harness_sha256"],
        "private_mapping_sha256": hashes["private_mapping_sha256"],
        "shared_object_sha256": hashes["shared_object_sha256"],
        "executable_sha256": hashes["executable_sha256"],
        "generated_source_bytes": (run_dir / "or_title_continuation_v1.c").stat().st_size,
        "shared_object_bytes": (run_dir / "or_title_continuation_v1.so").stat().st_size,
        "executable_bytes": (run_dir / "or_title_continuation_v1").stat().st_size,
        "semantic_record_count": record_count,
        "title_payload_sha256": analysis.title.projection["provenance"]["title_payload_sha256"],
        "mainexe_file_sha256": analysis.mainexe.file_sha256,
        "mainexe_payload_sha256": analysis.mainexe.payload_sha256,
        "continuation_entry_pc": f"0x{analysis.continuation_entry_pc:08x}",
        "continuation_budget": CONTINUATION_BUDGET,
    }


def emit_continuation_executable(
    analysis: ContinuationAnalysis,
    run_dir: pathlib.Path,
    *,
    recorded_frontier: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit, compile, run and persist the authenticated continuation runtime."""
    if recorded_frontier is None:
        recorded_frontier = recorded_p17_04r_frontier()
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    ctx = emitter.EmissionContext(analysis=analysis, run_dir=run_dir)
    ctx.records = emitter._make_semantic_records(analysis)
    ctx.record_by_pc = {rec.pc: rec for rec in ctx.records}

    h_path = run_dir / "or_title_continuation_v1.h"
    c_path = run_dir / "or_title_continuation_v1.c"
    harness_path = run_dir / "or_title_continuation_harness_v1.c"
    ctx.h_path, ctx.c_path, ctx.harness_path = h_path, c_path, harness_path

    h_path.write_text(_generate_header(analysis), encoding="utf-8", newline="\n")
    c_path.write_text(_generate_runtime_c(analysis, ctx), encoding="utf-8", newline="\n")
    harness_path.write_text(_generate_harness_c(analysis, ctx), encoding="utf-8", newline="\n")

    so_path = run_dir / "or_title_continuation_v1.so"
    exe_path = run_dir / "or_title_continuation_v1"
    ctx.so_path, ctx.exe_path = so_path, exe_path
    include_flag = f"-I{run_dir}"
    so_cmd = emitter._compile_c(c_path, so_path, extra_flags=("-shared", "-fPIC", include_flag))
    exe_cmd = emitter._compile_c(harness_path, exe_path,
                                 extra_flags=(include_flag, str(c_path)))
    result = emitter._run(exe_path)

    private_map = _build_private_mapping(analysis, ctx)
    private_map_path = run_dir / "private_mapping.json"
    map_bytes = (json.dumps(private_map, indent=2, sort_keys=True) + "\n").encode("utf-8")
    private_map_path.write_bytes(map_bytes)
    private_map_sha256 = _sha256_bytes(map_bytes)

    hashes = {
        "generated_source_sha256": _sha256_file(c_path),
        "generated_header_sha256": _sha256_file(h_path),
        "generated_harness_sha256": _sha256_file(harness_path),
        "shared_object_sha256": _sha256_file(so_path),
        "executable_sha256": _sha256_file(exe_path),
        "private_mapping_sha256": private_map_sha256,
    }

    metadata_path = run_dir / "build_metadata.json"
    metadata = _build_metadata_document(run_dir, so_cmd, exe_cmd, hashes,
                                        len(ctx.records), analysis)
    meta_bytes = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8")
    metadata_path.write_bytes(meta_bytes)

    # --- Fail-closed frontier classification -------------------------------
    trace = [str(op) for op in (result.get("executed_semantic_trace") or [])]
    executed_count = int(result["executed_instruction_count"])
    if len(trace) != executed_count:
        raise ContinuationError(
            "EXECUTED_TRACE_LENGTH_MISMATCH",
            f"trace={len(trace)} executed={executed_count}",
        )
    implemented = sorted(emitter.SUPPORTED_OPS)
    exercised = sorted(set(trace))
    missing = sorted(set(exercised) - set(implemented))
    if missing:
        raise ContinuationError("EXERCISED_OP_NOT_IMPLEMENTED", ",".join(missing))

    mainexe_executed = int(result["mainexe_executed_count"])
    if mainexe_executed < 1:
        raise ContinuationError(
            "CONTINUATION_NOT_ENTERED",
            f"stop_reason={result.get('stop_reason')}",
        )

    expected_title_count = int(recorded_frontier["executed_instruction_count"])
    expected_title_last = _parse_hex(recorded_frontier["last_successfully_executed_pc"])
    expected_entry = _parse_hex(recorded_frontier["attempted_frontier_pc"])
    if int(result["title_prefix_executed_count"]) != expected_title_count:
        raise ContinuationError(
            "TITLE_FRONTIER_REPRODUCTION_MISMATCH",
            f"title_prefix={result['title_prefix_executed_count']} recorded={expected_title_count}",
        )
    if _parse_hex(result["title_prefix_last_executed_pc"]) != expected_title_last:
        raise ContinuationError(
            "TITLE_FRONTIER_REPRODUCTION_MISMATCH",
            f"last={result['title_prefix_last_executed_pc']} recorded=0x{expected_title_last:08x}",
        )
    if _parse_hex(result["mainexe_first_pc"]) != expected_entry:
        raise ContinuationError(
            "CONTINUATION_ENTRY_MISMATCH",
            f"first={result['mainexe_first_pc']} recorded=0x{expected_entry:08x}",
        )

    provenance_digest = _sha256_bytes(
        json.dumps([rec.provenance_digest for rec in ctx.records], sort_keys=True).encode("utf-8")
    )
    result["exercised_semantic_vocabulary"] = exercised
    result["exercised_semantic_vocabulary_count"] = len(exercised)
    result["executed_semantic_trace_length"] = len(trace)
    result["record_count"] = len(ctx.records)
    result["title_record_count"] = analysis.title_record_count
    result["mainexe_record_count"] = analysis.mainexe_record_count

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
    if persisted["artifacts"]["private_mapping"]["sha256"] != private_map_sha256:
        raise ContinuationError("PRIVATE_MAPPING_DIGEST_MISMATCH")

    manifest = {
        "schema": "openrecomp-phase17-title-exec-continuation-emission-v1",
        "stage": "P17-05R",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "emission_kind": "AUTHENTICATED_GENERATED_C_CONTINUATION_RUNTIME",
        "next_stage": NEXT_STAGE,
        "interface": {
            "header": "or_title_continuation_v1.h",
            "execute_symbol": "or_cont_execute_v1",
            "guest_state_struct": "or_cont_guest_state_v1",
            "services_struct": "or_cont_runtime_services_v1",
        },
        "persistence": persisted,
        "source": {
            "title_projection_digest": analysis.title.projection["projection_digest"],
            "title_payload_sha256": analysis.title.projection["provenance"]["title_payload_sha256"],
            "mainexe_file_sha256": analysis.mainexe.file_sha256,
            "mainexe_payload_sha256": analysis.mainexe.payload_sha256,
            "continuation_entry_pc": f"0x{analysis.continuation_entry_pc:08x}",
            "entry_pc": f"0x{TITLE_ENTRY_PC:08x}",
            "record_count": len(ctx.records),
            "title_record_count": analysis.title_record_count,
            "mainexe_record_count": analysis.mainexe_record_count,
            "header_sha256": hashes["generated_header_sha256"],
            "generated_source_sha256": hashes["generated_source_sha256"],
            "generated_harness_sha256": hashes["generated_harness_sha256"],
            "implemented_semantic_vocabulary": implemented,
            "implemented_semantic_vocabulary_count": len(implemented),
            "emitted_semantic_vocabulary": sorted({rec.op for rec in ctx.records
                                                   if rec.op in emitter.SUPPORTED_OPS}),
            "exercised_semantic_vocabulary": exercised,
            "exercised_semantic_vocabulary_count": len(exercised),
            "executed_semantic_trace": trace,
            "provenance_digest": provenance_digest,
        },
        "build": {
            "toolchain": metadata["toolchain"],
            "executable_sha256": hashes["executable_sha256"],
            "shared_object_sha256": hashes["shared_object_sha256"],
            "build_metadata_sha256": _sha256_bytes(meta_bytes),
            "runtime_result_schema": "openrecomp-phase17-title-exec-continuation-result-v1",
        },
        "active_build": {
            "phase17_emitter": "p17_title_exec_continuation_v1.py",
            "frozen_decoder": "p3_decode_mips32_v1.classify (unchanged)",
            "phase16_hand_authored_title_guest_flow": "EXCLUDED",
            "execution": "GENERATED_NATIVE_RUNTIME",
        },
        "frontier": {
            "stop_reason": result["stop_reason"],
            "last_successfully_executed_pc": result["last_successfully_executed_pc"],
            "attempted_frontier_pc": result["attempted_frontier_pc"],
            "frontier_pc": result["frontier_pc"],
            "title_prefix_executed_count": result["title_prefix_executed_count"],
            "title_prefix_last_executed_pc": result["title_prefix_last_executed_pc"],
            "mainexe_first_pc": result["mainexe_first_pc"],
            "mainexe_executed_count": result["mainexe_executed_count"],
        },
        "runtime_result": result,
        "claims": {
            "initialization": "NOT_PROVEN",
            "frame": "NOT_PROVEN",
            "playability": "NOT_PROVEN",
            "general_compatibility": "NOT_PROVEN",
            "first_frame_ready": "NO",
        },
    }
    manifest["emission_digest"] = _digest_dict(manifest, "emission_digest")
    return manifest
