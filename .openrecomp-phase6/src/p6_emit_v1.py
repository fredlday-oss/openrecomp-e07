#!/usr/bin/env python3
"""Phase-6 host emission and MMC1 runtime support (P6-07/P6-08).

* `emit_host_program` reuses the frozen Phase-5 CPU emitter (`p5_emit_v1`,
  read-only) for the proven 6502 subset and maps the single declared page-wrap
  run-exit thunk to the `p6.exit` runtime service; any other unresolved
  indirect site fails closed.
* `emit_support` generates the MMC1 runtime support C source: a bank-aware
  cartridge (serial protocol, PRG/CHR windows, mirroring, disabled PRG-RAM)
  behind the same typed runtime ABI (`or_rt_memory_read/write`,
  `or_rt_host_call`, `or_rt_failure_reason`, `or_rt_take_nmi`,
  `or_rt_advance`) used by Phase 5.
* `build_native` builds both through the shared Phase-2 build pipeline.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any, Sequence

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p5_emit_v1 as cpu_emit  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402

FRAME_UNITS = 29780
VBLANK_UNITS = 2273
NMI_ENTRY_COST = 7
EXIT_SERVICE_NAME = "p6.exit"
EXIT_SERVICE_ID = cpu_emit.EXIT_SERVICE_ID


class P6EmitError(ValueError):
    """Fail-closed Phase-6 emission error."""


def exit_sites_for(instructions) -> dict[int, str]:
    sites: dict[int, str] = {}
    for instruction in instructions:
        if instruction.flow.value == "INDIRECT_JUMP":
            fields = dict((instruction.metadata or {}).get("adapter_fields", {}))
            pointer = fields.get("indirect")
            if pointer != 0x02FF:
                raise P6EmitError(
                    f"unresolved indirect site at 0x{instruction.address:04x} "
                    f"points at 0x{pointer:04x}, not the declared page-wrap "
                    "run-exit thunk; fail closed")
            sites[instruction.address] = EXIT_SERVICE_NAME
    if len(sites) != 1:
        raise P6EmitError(
            f"expected exactly one declared run-exit thunk, found {len(sites)}")
    return sites


def emit_host_program(instructions, metadata: dict,
                      max_steps: int = cpu_emit.DEFAULT_MAX_STEPS) -> str:
    merged = dict(metadata)
    if "cpu_origin" not in merged:
        merged["cpu_origin"] = merged["fixed_bank_origin"]
    return cpu_emit.emit_program(instructions, merged, exit_sites_for(instructions),
                                 max_steps=max_steps)


SUPPORT_TEMPLATE = """\
/* OpenRecomp Phase-6 NES MMC1 runtime support (P6-08). Generated deterministically. */
/* source_rom_sha256: @@ROM_SHA256@@ */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

int openrecomp_failed(void);
const char *openrecomp_error(void);
int openrecomp_exit_requested(void);
uint64_t openrecomp_steps(void);
uint16_t openrecomp_pc(void);
uint8_t openrecomp_a(void);
uint8_t openrecomp_x(void);
uint8_t openrecomp_y(void);
uint8_t openrecomp_sp(void);
uint8_t openrecomp_status(void);
void openrecomp_run(void);

#define FRAME_UNITS @@FRAME_UNITS@@u
#define VBLANK_UNITS @@VBLANK_UNITS@@u
#define NMI_ENTRY_COST @@NMI_ENTRY_COST@@u
#define INPUT_PLAN_LEN @@INPUT_PLAN_LEN@@u
#define MAX_FRAMES 64u
#define PRG_BANK_BYTES 0x4000u
#define PRG_BANKS @@PRG_BANKS@@u
#define CHR_BANKS_8K @@CHR_BANKS@@u

static const uint8_t g_prg[@@PRG_SIZE@@] = {
@@PRG@@
};
static const uint8_t g_chr[@@CHR_SIZE@@] = {
@@CHR@@
};
static const uint8_t g_input_plan[INPUT_PLAN_LEN] = { @@INPUT_PLAN@@ };

static uint8_t g_ram[2048];
static uint8_t g_vram[2048];
static uint8_t g_palette[32];
static uint8_t g_oam[256];
static uint8_t g_apu[0x18];
static uint8_t g_apu_status;
static uint8_t g_controller_state;
static uint8_t g_strobe;
static uint8_t g_shift;
static uint8_t g_ctrl;
static uint8_t g_mask;
static uint8_t g_ppu_status;
static uint8_t g_oam_addr;
static uint16_t g_ppu_addr;
static uint16_t g_ppu_t;
static uint8_t g_ppu_w;
static uint8_t g_scroll_x;
static uint8_t g_scroll_y;
static uint8_t g_buffer;
static uint8_t g_open_bus;
static uint32_t g_clock;
static uint32_t g_frame_index;
static uint32_t g_next_frame_start;
static uint32_t g_next_vblank_end;
static uint32_t g_pending_nmi;
static uint32_t g_nmi_delivered;
static uint32_t g_frame_input[MAX_FRAMES];
static uint64_t g_frame_tile[MAX_FRAMES];
static uint64_t g_frame_ppu[MAX_FRAMES];
static uint32_t g_exit_argument;
static int g_host_failed;
static const char *g_host_error = "";

/* MMC1 audited state (P6-02 .. P6-05). */
static uint8_t g_mmc1_regs[4] = { 0x0Cu, 0x00u, 0x00u, 0x00u };
static uint8_t g_mmc1_shift;
static uint8_t g_mmc1_count;
static uint32_t g_mmc1_last_cycle = 0xFFFFFFFFu;
static int g_mmc1_has_last;
static uint32_t g_mmc1_writes;

static uint64_t fnv1a64_byte(uint64_t state, uint8_t value) {
    state ^= (uint64_t)value;
    state *= UINT64_C(1099511628211);
    return state;
}

static uint64_t fnv1a64_bytes(uint64_t state, const uint8_t *data, size_t length) {
    size_t index;
    for (index = 0; index < length; ++index) {
        state = fnv1a64_byte(state, data[index]);
    }
    return state;
}

static void host_fail(const char *message) {
    if (!g_host_failed) { g_host_failed = 1; g_host_error = message; }
}

static void mmc1_write(uint16_t address, uint8_t value) {
    uint32_t cycle = g_clock;
    uint8_t target;
    if (g_mmc1_has_last && cycle == g_mmc1_last_cycle + 1u) { return; }
    g_mmc1_last_cycle = cycle;
    g_mmc1_has_last = 1;
    g_mmc1_writes += 1u;
    if (value & 0x80u) { g_mmc1_shift = 0u; g_mmc1_count = 0u; return; }
    g_mmc1_shift = (uint8_t)(g_mmc1_shift | ((uint8_t)(value & 0x01u) << g_mmc1_count));
    g_mmc1_count = (uint8_t)(g_mmc1_count + 1u);
    if (g_mmc1_count == 5u) {
        target = (uint8_t)((address >> 13u) & 0x03u);
        g_mmc1_regs[target] = g_mmc1_shift;
        g_mmc1_shift = 0u;
        g_mmc1_count = 0u;
    }
}

static uint16_t prg_bank_for_window(uint8_t high_window) {
    uint8_t mode = (uint8_t)((g_mmc1_regs[0] >> 2u) & 0x03u);
    uint8_t reg = (uint8_t)(g_mmc1_regs[3] & (uint8_t)(PRG_BANKS - 1u));
    if (mode == 0u || mode == 1u) {
        uint8_t base = (uint8_t)((g_mmc1_regs[3] & 0x1Eu) & (uint8_t)(PRG_BANKS - 1u));
        if (high_window) { return (uint16_t)((base + 1u) & (PRG_BANKS - 1u)); }
        return (uint16_t)base;
    }
    if (mode == 2u) { return high_window ? (uint16_t)reg : 0u; }
    return high_window ? (uint16_t)(PRG_BANKS - 1u) : (uint16_t)reg;
}

static uint16_t chr_offset(uint16_t address) {
    if ((g_mmc1_regs[0] & 0x10u) == 0u) {
        uint8_t bank = (uint8_t)((g_mmc1_regs[1] >> 1u)
            & (uint8_t)(CHR_BANKS_8K - 1u));
        return (uint16_t)(((uint16_t)bank << 13u) | (address & 0x1FFFu));
    }
    {
        uint8_t count4 = (uint8_t)(CHR_BANKS_8K * 2u);
        uint8_t bank = (address < 0x1000u)
            ? (uint8_t)(g_mmc1_regs[1] & (uint8_t)(count4 - 1u))
            : (uint8_t)(g_mmc1_regs[2] & (uint8_t)(count4 - 1u));
        return (uint16_t)(((uint16_t)bank << 12u) | (address & 0x0FFFu));
    }
}

static uint16_t nametable_index(uint16_t address) {
    uint16_t offset = (uint16_t)(address - 0x2000u);
    uint8_t mode = (uint8_t)(g_mmc1_regs[0] & 0x03u);
    uint8_t bit10;
    uint8_t bit11;
    uint8_t table;
    if (offset >= 0x1000u) { offset = (uint16_t)(offset - 0x1000u); }
    bit10 = (uint8_t)((offset >> 10u) & 0x01u);
    bit11 = (uint8_t)((offset >> 11u) & 0x01u);
    if (mode == 0u) { table = 0u; }
    else if (mode == 1u) { table = 1u; }
    else if (mode == 2u) { table = bit10; }
    else { table = bit11; }
    return (uint16_t)(((uint16_t)table * 0x400u) + (offset & 0x3FFu));
}

static uint8_t palette_index(uint16_t address) {
    uint8_t index = (uint8_t)((address - 0x3F00u) & 0x1Fu);
    if (index == 0x10u || index == 0x14u || index == 0x18u || index == 0x1Cu) {
        index = (uint8_t)(index - 0x10u);
    }
    return index;
}

static uint8_t ppu_memory_read(uint16_t address) {
    address = (uint16_t)(address & 0x3FFFu);
    if (address < 0x2000u) { return g_chr[chr_offset(address)]; }
    if (address < 0x3F00u) { return g_vram[nametable_index(address)]; }
    {
        uint8_t value = g_palette[palette_index(address)];
        if (g_mask & 0x01u) { value = (uint8_t)(value & 0x30u); }
        return value;
    }
}

static void ppu_memory_write(uint16_t address, uint8_t value) {
    address = (uint16_t)(address & 0x3FFFu);
    if (address < 0x2000u) {
        host_fail("CHR ROM write fails closed");
        return;
    }
    if (address < 0x3F00u) { g_vram[nametable_index(address)] = value; return; }
    g_palette[palette_index(address)] = (uint8_t)(value & 0x3Fu);
}

static uint8_t ppu_register_read(uint8_t reg) {
    if (reg == 2u) {
        uint8_t value = (uint8_t)((g_ppu_status & 0xE0u) | (g_open_bus & 0x1Fu));
        g_ppu_status = (uint8_t)(g_ppu_status & ~0x80u);
        g_ppu_w = 0u;
        return value;
    }
    if (reg == 4u) { return g_oam[g_oam_addr]; }
    if (reg == 7u) {
        uint16_t address = g_ppu_addr;
        uint8_t value;
        if (address >= 0x3F00u) {
            value = ppu_memory_read(address);
            g_buffer = ppu_memory_read((uint16_t)((address - 0x1000u) & 0x3FFFu));
        } else {
            value = g_buffer;
            g_buffer = ppu_memory_read(address);
        }
        g_ppu_addr = (uint16_t)((address
            + ((g_ctrl & 0x04u) ? 32u : 1u)) & 0x3FFFu);
        return value;
    }
    return g_open_bus;
}

static void ppu_register_write(uint8_t reg, uint8_t value) {
    g_open_bus = value;
    if (reg == 0u) { g_ctrl = value; return; }
    if (reg == 1u) { g_mask = value; return; }
    if (reg == 2u) { return; }
    if (reg == 3u) { g_oam_addr = value; return; }
    if (reg == 4u) {
        g_oam[g_oam_addr] = value;
        g_oam_addr = (uint8_t)(g_oam_addr + 1u);
        return;
    }
    if (reg == 5u) {
        if (g_ppu_w == 0u) { g_scroll_x = value; g_ppu_w = 1u; }
        else { g_scroll_y = value; g_ppu_w = 0u; }
        return;
    }
    if (reg == 6u) {
        if (g_ppu_w == 0u) {
            g_ppu_t = (uint16_t)(((uint16_t)(value & 0x3Fu) << 8)
                | (g_ppu_t & 0x00FFu));
            g_ppu_w = 1u;
        } else {
            g_ppu_t = (uint16_t)(((uint16_t)g_ppu_t & 0xFF00u) | value);
            g_ppu_addr = (uint16_t)(g_ppu_t & 0x3FFFu);
            g_ppu_w = 0u;
        }
        return;
    }
    ppu_memory_write(g_ppu_addr, value);
    g_ppu_addr = (uint16_t)((g_ppu_addr
        + ((g_ctrl & 0x04u) ? 32u : 1u)) & 0x3FFFu);
}

static uint8_t controller_read(uint8_t port) {
    (void)port;
    if (g_strobe) { return (uint8_t)(0x40u | (g_controller_state & 0x01u)); }
    {
        uint8_t bit = 1u;
        if (g_shift < 8u) { bit = (uint8_t)((g_controller_state >> g_shift) & 0x01u); }
        g_shift = (uint8_t)(g_shift + 1u);
        return (uint8_t)(0x40u | bit);
    }
}

static void oam_dma(uint8_t page) {
    uint16_t base = (uint16_t)((uint16_t)page << 8);
    uint32_t offset;
    for (offset = 0u; offset < 256u; ++offset) {
        uint64_t value = 0u;
        extern int or_rt_memory_read(uint64_t, uint32_t, uint64_t *);
        if (or_rt_memory_read((uint64_t)(uint16_t)(base + (uint16_t)offset), 8u,
                              &value) != 0) {
            host_fail("OAM DMA read failed");
            return;
        }
        g_oam[offset] = (uint8_t)value;
    }
}

static int bus_read(uint16_t address, uint8_t *out) {
    if (address < 0x2000u) { *out = g_ram[address & 0x07FFu]; return 0; }
    if (address < 0x4000u) {
        *out = ppu_register_read((uint8_t)((address - 0x2000u) & 0x07u));
        return 0;
    }
    if (address == 0x4014u) { *out = 0u; return 0; }
    if (address == 0x4015u) { *out = g_apu_status; return 0; }
    if (address == 0x4016u) { *out = controller_read(0u); return 0; }
    if (address == 0x4017u) { *out = controller_read(1u); return 0; }
    if (address < 0x4018u) { *out = 0u; return 0; }
    if (address < 0x4020u) { return 1; }
    if (address < 0x6000u) { return 1; }
    if (address < 0x8000u) { return 1; }
    {
        uint16_t bank = prg_bank_for_window((uint8_t)(address >= 0xC000u));
        *out = g_prg[(uint16_t)((uint16_t)bank * PRG_BANK_BYTES
            + (uint16_t)(address & 0x3FFFu))];
        return 0;
    }
}

static int bus_write(uint16_t address, uint8_t value) {
    if (address < 0x2000u) { g_ram[address & 0x07FFu] = value; return 0; }
    if (address < 0x4000u) {
        ppu_register_write((uint8_t)((address - 0x2000u) & 0x07u), value);
        return 0;
    }
    if (address <= 0x4013u) { g_apu[address - 0x4000u] = value; return 0; }
    if (address == 0x4014u) { oam_dma(value); return 0; }
    if (address == 0x4015u) { g_apu_status = (uint8_t)(value & 0x1Fu); return 0; }
    if (address == 0x4016u) {
        g_strobe = (uint8_t)(value & 0x01u);
        g_shift = 0u;
        return 0;
    }
    if (address == 0x4017u) { g_apu[0x17] = value; return 0; }
    if (address < 0x4018u) { return 1; }
    if (address < 0x4020u) { return 1; }
    if (address < 0x6000u) { return 1; }
    if (address < 0x8000u) { return 1; }
    mmc1_write(address, value);
    return 0;
}

/* ---- typed runtime ABI ---- */
int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value) {
    uint8_t value;
    if (width_bits != 8u || out_value == 0) { return 2; }
    if (address > 0xFFFFu) { return 1; }
    if (bus_read((uint16_t)address, &value) != 0) { return 1; }
    *out_value = (uint64_t)value;
    return 0;
}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value) {
    if (width_bits != 8u) { return 2; }
    if (address > 0xFFFFu) { return 1; }
    if (bus_write((uint16_t)address, (uint8_t)(value & 0xFFu)) != 0) { return 1; }
    return 0;
}

const char *or_rt_failure_reason(int code) {
    switch (code) {
    case 0: return "";
    case 1: return "memory out of range";
    case 2: return "memory width unsupported";
    case 6: return "unknown host service";
    case 7: return "host service failed";
    case 8: return "host call arity";
    default: return "runtime failure";
    }
}

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args,
                    uint64_t *out_value) {
    (void)out_value;
    if (service_id == UINT64_C(@@EXIT_SERVICE_ID@@)) {
        if (argc != 1u || args == 0) { return 8; }
        g_exit_argument = (uint32_t)args[0];
        return 0;
    }
    return 6;
}

static void record_frame(void) {
    uint64_t tile = UINT64_C(14695981039346656037);
    uint64_t ppu = UINT64_C(14695981039346656037);
    uint8_t input;
    if (g_frame_index < MAX_FRAMES) {
        input = g_input_plan[
            (g_frame_index < INPUT_PLAN_LEN) ? g_frame_index : (INPUT_PLAN_LEN - 1u)];
        g_frame_input[g_frame_index] = input;
        g_frame_tile[g_frame_index] = fnv1a64_bytes(tile, g_vram, 960u);
        ppu = fnv1a64_bytes(ppu, g_vram, 2048u);
        ppu = fnv1a64_bytes(ppu, g_palette, 32u);
        ppu = fnv1a64_bytes(ppu, g_oam, 256u);
        g_frame_ppu[g_frame_index] = ppu;
    }
}

static void frame_start(uint32_t at) {
    uint8_t input = g_input_plan[
        (g_frame_index < INPUT_PLAN_LEN) ? g_frame_index : (INPUT_PLAN_LEN - 1u)];
    g_controller_state = input;
    g_ppu_status = (uint8_t)(g_ppu_status | 0x80u);
    if (g_ctrl & 0x80u) { g_pending_nmi += 1u; }
    record_frame();
    g_frame_index += 1u;
    g_next_frame_start += FRAME_UNITS;
    g_next_vblank_end = at + VBLANK_UNITS;
}

void or_rt_advance(uint32_t cost) {
    uint32_t target = g_clock + cost;
    while (g_next_frame_start <= target) { frame_start(g_next_frame_start); }
    while (g_next_vblank_end <= target) {
        g_ppu_status = (uint8_t)(g_ppu_status & ~0x80u);
        g_next_vblank_end += FRAME_UNITS;
    }
    g_clock = target;
}

int or_rt_take_nmi(void) {
    if (g_pending_nmi == 0u) { return 0; }
    g_pending_nmi -= 1u;
    g_nmi_delivered += 1u;
    g_clock += NMI_ENTRY_COST;
    return 1;
}

static void print_hex_bytes(const uint8_t *data, size_t length) {
    size_t index;
    for (index = 0; index < length; ++index) { printf("%02X", (unsigned)data[index]); }
}

int main(void) {
    uint64_t state = UINT64_C(14695981039346656037);
    uint32_t index;
    memset(g_ram, 0, sizeof(g_ram));
    memset(g_vram, 0, sizeof(g_vram));
    memset(g_palette, 0, sizeof(g_palette));
    memset(g_oam, 0, sizeof(g_oam));
    memset(g_apu, 0, sizeof(g_apu));
    g_clock = 0u; g_frame_index = 0u; g_next_frame_start = 0u;
    g_next_vblank_end = VBLANK_UNITS; g_pending_nmi = 0u; g_nmi_delivered = 0u;

    openrecomp_run();

    state = fnv1a64_bytes(state, g_ram, 2048u);
    state = fnv1a64_bytes(state, g_vram, 2048u);
    state = fnv1a64_bytes(state, g_palette, 32u);
    state = fnv1a64_bytes(state, g_oam, 256u);
    state = fnv1a64_bytes(state, g_apu, 0x18u);
    state = fnv1a64_byte(state, g_apu_status);
    state = fnv1a64_byte(state, g_controller_state);
    state = fnv1a64_byte(state, g_ctrl);
    state = fnv1a64_byte(state, g_mask);
    state = fnv1a64_byte(state, g_ppu_status);
    state = fnv1a64_byte(state, g_oam_addr);
    state = fnv1a64_byte(state, (uint8_t)(g_ppu_addr & 0xFFu));
    state = fnv1a64_byte(state, (uint8_t)(g_ppu_addr >> 8u));
    state = fnv1a64_byte(state, g_scroll_x);
    state = fnv1a64_byte(state, g_scroll_y);
    state = fnv1a64_byte(state, g_buffer);
    state = fnv1a64_bytes(state, g_mmc1_regs, 4u);
    state = fnv1a64_byte(state, g_mmc1_shift);
    state = fnv1a64_byte(state, g_mmc1_count);
    state = fnv1a64_byte(state, openrecomp_a());
    state = fnv1a64_byte(state, openrecomp_x());
    state = fnv1a64_byte(state, openrecomp_y());
    state = fnv1a64_byte(state, openrecomp_sp());
    state = fnv1a64_byte(state, (uint8_t)(openrecomp_pc() & 0xFFu));
    state = fnv1a64_byte(state, (uint8_t)(openrecomp_pc() >> 8u));
    state = fnv1a64_byte(state, openrecomp_status());
    state = fnv1a64_byte(state, (uint8_t)(openrecomp_steps() & 0xFFu));
    state = fnv1a64_byte(state, (uint8_t)((openrecomp_steps() >> 8u) & 0xFFu));
    state = fnv1a64_byte(state, (uint8_t)((openrecomp_steps() >> 16u) & 0xFFu));
    state = fnv1a64_byte(state, (uint8_t)((openrecomp_steps() >> 24u) & 0xFFu));

    printf("failed=%d\\n", openrecomp_failed() || g_host_failed);
    printf("error=%s\\n", openrecomp_failed() ? openrecomp_error() : g_host_error);
    printf("exit=%d\\n", openrecomp_exit_requested());
    printf("steps=%llu\\n", (unsigned long long)openrecomp_steps());
    printf("pc=0x%04X\\n", (unsigned)openrecomp_pc());
    printf("a=0x%02X\\n", (unsigned)openrecomp_a());
    printf("x=0x%02X\\n", (unsigned)openrecomp_x());
    printf("y=0x%02X\\n", (unsigned)openrecomp_y());
    printf("sp=0x%02X\\n", (unsigned)openrecomp_sp());
    printf("p=0x%02X\\n", (unsigned)openrecomp_status());
    printf("frames=%u\\n", (unsigned)g_frame_index);
    printf("nmi=%u\\n", (unsigned)g_nmi_delivered);
    printf("clock=%u\\n", (unsigned)g_clock);
    printf("exit_arg=0x%08X\\n", (unsigned)g_exit_argument);
    printf("ram_fnv1a64=0x%016llX\\n",
           (unsigned long long)fnv1a64_bytes(UINT64_C(14695981039346656037), g_ram, 2048u));
    printf("ppu_fnv1a64=0x%016llX\\n",
           (unsigned long long)fnv1a64_bytes(
               fnv1a64_bytes(
                   fnv1a64_bytes(UINT64_C(14695981039346656037), g_vram, 2048u),
                   g_palette, 32u), g_oam, 256u));
    printf("state_fnv1a64=0x%016llX\\n", (unsigned long long)state);
    printf("mmc1_regs=%02X%02X%02X%02X\\n", (unsigned)g_mmc1_regs[0],
           (unsigned)g_mmc1_regs[1], (unsigned)g_mmc1_regs[2],
           (unsigned)g_mmc1_regs[3]);
    printf("mmc1_shift=%u\\n", (unsigned)g_mmc1_shift);
    printf("mmc1_count=%u\\n", (unsigned)g_mmc1_count);
    printf("mmc1_writes=%u\\n", (unsigned)g_mmc1_writes);
    printf("prg_window_8000=%u\\n", (unsigned)prg_bank_for_window(0u));
    printf("prg_window_c000=%u\\n", (unsigned)prg_bank_for_window(1u));
    printf("chr_mode=%u\\n", (unsigned)((g_mmc1_regs[0] >> 4u) & 0x01u));
    printf("mirroring=%u\\n", (unsigned)(g_mmc1_regs[0] & 0x03u));
    printf("prg_ram_enabled=0\\n");
    for (index = 0u; index < g_frame_index && index < MAX_FRAMES; ++index) {
        printf("frame[%u]=%02X,%016llX,%016llX\\n", (unsigned)index,
               (unsigned)g_frame_input[index],
               (unsigned long long)g_frame_tile[index],
               (unsigned long long)g_frame_ppu[index]);
    }
    printf("exit_word=");
    print_hex_bytes(g_ram + 0x0400, 8u);
    printf("\\n");
    return 0;
}
"""


def _array_bytes(data: bytes, indent: str = "    ") -> str:
    lines = []
    for start in range(0, len(data), 12):
        chunk = data[start:start + 12]
        lines.append(indent + ", ".join(f"0x{value:02X}" for value in chunk) + ",")
    return "\n".join(lines)


def emit_support(rom: bytes, metadata: dict, plan: Sequence[int]) -> str:
    prg_size = int(metadata["prg_size"])
    chr_size = int(metadata["chr_size"])
    prg = rom[16:16 + prg_size]
    chr_data = rom[16 + prg_size:16 + prg_size + chr_size]
    if len(prg) != prg_size or len(chr_data) != chr_size:
        raise P6EmitError("fixture segments are truncated")
    return (SUPPORT_TEMPLATE
            .replace("@@ROM_SHA256@@", metadata["rom_sha256"])
            .replace("@@FRAME_UNITS@@", str(FRAME_UNITS))
            .replace("@@VBLANK_UNITS@@", str(VBLANK_UNITS))
            .replace("@@NMI_ENTRY_COST@@", str(NMI_ENTRY_COST))
            .replace("@@INPUT_PLAN_LEN@@", str(len(plan)))
            .replace("@@INPUT_PLAN@@", ", ".join(f"0x{value:02X}" for value in plan))
            .replace("@@PRG_SIZE@@", str(prg_size))
            .replace("@@PRG_BANKS@@", str(metadata["prg_banks"]))
            .replace("@@CHR_SIZE@@", str(chr_size))
            .replace("@@CHR_BANKS@@", str(metadata["chr_banks"]))
            .replace("@@PRG@@", _array_bytes(prg))
            .replace("@@CHR@@", _array_bytes(chr_data))
            .replace("@@EXIT_SERVICE_ID@@", str(EXIT_SERVICE_ID)))


def build_native(program_text: str, support_text: str, *,
                 fixture_id: str, workspace: pathlib.Path,
                 run_count: int = 2) -> Any:
    return bp.build_generated_host(
        lambda: program_text,
        support_sources=(
            bp.BuildSource("p6_nes_support.c",
                           bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           support_text.encode("utf-8")),
        ),
        config=bp.BuildConfig(fixture_id=fixture_id, smoke_test=False,
                              run_count=run_count),
        workspace=workspace,
        keep_workspace=True,
    )


__all__ = [
    "EXIT_SERVICE_ID",
    "EXIT_SERVICE_NAME",
    "FRAME_UNITS",
    "NMI_ENTRY_COST",
    "P6EmitError",
    "SUPPORT_TEMPLATE",
    "VBLANK_UNITS",
    "build_native",
    "emit_host_program",
    "emit_support",
    "exit_sites_for",
]
