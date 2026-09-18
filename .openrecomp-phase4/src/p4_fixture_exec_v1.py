#!/usr/bin/env python3
"""OpenRecomp Phase-4 fixture translation + adapter execution core (P4-08).

Translates the P4-07 interactive fixture into architecture-neutral generated C
and runs it through a real implementation of the platform-adapter/runtime
contracts:

* the fixture ELF is rebuilt from source with the recorded P4-07 toolchain and
  analysed with the frozen Phase-3 decode/reachability layers (read-only use);
* every reachable word is emitted as one switch case by the frozen
  architecture-neutral instruction emitter; unsupported or unhandled records
  fail closed at emission time;
* the generated program speaks only the P4-01 generated-code <-> runtime ABI
  (``or_rt_*`` externs and ``openrecomp_*`` accessors) and maps the fixture's
  four MMIO windows onto the declared fixture instance services
  (``fixture.out``/``fixture.in``/``fixture.exit``/``fixture.ticks``), which
  the P4-03/P4-04/P4-05 layers alias onto the generic runtime interfaces;
* the emitted support implements the runtime side of the ABI (checked memory
  with the fixture's region table, typed service dispatch, deterministic
  input plan, bounded output, virtual ticks = retired guest steps) and prints
  the P4-01 canonical observable (transcript, exit status, steps, PC and the
  FNV-1a 64 state digest over the contract layout).

Nothing here modifies the frozen Phase-1/Phase-2/Phase-3 modules; they are
imported read-only.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from dataclasses import dataclass
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for candidate in (str(ROOT), str(ROOT / ".openrecomp-phase4" / "src"),
                  str(ROOT / ".openrecomp-phase3" / "src")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import p4_guest_memory_v1 as gm  # noqa: E402
import p4_runtime_abi_v1 as abi  # noqa: E402
from p3_code_frontier_v1 import analyze  # noqa: E402
from p3_elf_image_v1 import ingest  # noqa: E402
from p3_host_emit_v1 import HostEmitError, emit_instruction  # noqa: E402
from p3_target_mips32_v1 import MIPS32_O32  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402

FIXTURE_ELF_SHA256 = "acb4f4e57a7f996e87989e99d702d802259b752aabb2476f574665ef061969bc"
FIXTURE_ELF_SIZE = 9884
FIXTURE_ELF_PATH = ".openrecomp-phase4/build/P4-07/candidate-a/p4_fixture_mips32_O1.elf"
FIXTURE_ENTRY = 0x1C00
IMAGE_WINDOW = 0x10000
MAX_STEPS = 20000000
OUTPUT_CAPACITY = 1 << 16
INPUT_CAPACITY = 64
INPUT_PLAN = bytes.fromhex("0512ab34ff")
INPUT_PLAN_PATH = ".openrecomp-phase4/fixture/input_plan.json"
PROFILE_NAME = "p4-fixture-mips32-o32"

SERVICE_IDS = ("fixture.exit", "fixture.in", "fixture.out", "fixture.ticks")
SERVICE_DESCRIPTIONS = {
    "fixture.exit": "Terminate the fixture run with a 32-bit status.",
    "fixture.in": "Read one byte of the deterministic input plan (0xffffffff at end).",
    "fixture.out": "Append one byte to the bounded fixture transcript.",
    "fixture.ticks": "Read the virtual tick count (retired guest steps).",
}
ARG_TYPES = {
    "fixture.exit": ("u32",),
    "fixture.in": (),
    "fixture.out": ("u32",),
    "fixture.ticks": (),
}
RESULT_TYPES = {
    "fixture.exit": None,
    "fixture.in": "u32",
    "fixture.out": None,
    "fixture.ticks": "u32",
}
TERMINATES = {"fixture.exit": True}

CONTROL_OPS = frozenset({"beq", "bne", "blez", "bgtz", "bltz", "bgez", "j", "jal",
                         "jr", "jalr"})
MMIO_OUT = 0x20000000
MMIO_IN = 0x20000004
MMIO_EXIT = 0x20000008
MMIO_TICKS = 0x2000000C

FAILURE_ENUM = "\n".join(
    [f"    OR_RT_{code} = {index + 1}," for index, code in enumerate(rt.RUNTIME_FAILURE_CODES)])
SERVICE_MACROS = "\n".join(
    f"#define OR_RT_SERVICE_{service_id.replace('fixture.', 'FIXTURE_').replace('.', '_').upper()} "
    f"UINT64_C({numeric_id})"
    for numeric_id, service_id in enumerate(SERVICE_IDS, start=1))
SERVICE_MACRO_BY_ID = {
    service_id: f"OR_RT_SERVICE_{service_id.replace('fixture.', 'FIXTURE_').replace('.', '_').upper()}"
    for service_id in SERVICE_IDS
}
SERVICE_NUMERIC = {service_id: index for index, service_id in enumerate(SERVICE_IDS, start=1)}


class FixtureExecError(ValueError):
    """Raised when fixture translation or execution setup fails closed."""


def fixture_services() -> tuple[abi.ServiceDescriptor, ...]:
    descriptors = []
    for numeric_id, service_id in enumerate(SERVICE_IDS, start=1):
        descriptors.append(abi.ServiceDescriptor(
            service_id=service_id,
            numeric_id=numeric_id,
            version=rt.RUNTIME_ABI_VERSION,
            arg_types=ARG_TYPES[service_id],
            result_type=RESULT_TYPES[service_id],
            terminates_run=TERMINATES.get(service_id, False),
            description=SERVICE_DESCRIPTIONS[service_id],
        ))
    return tuple(descriptors)


def fixture_profile() -> abi.InstanceProfile:
    return abi.InstanceProfile(
        name=PROFILE_NAME,
        abi_version=rt.RUNTIME_ABI_VERSION,
        endianness="little",
        widths=(8, 16, 32),
        register_count=32,
        aux_registers=(("hi", "openrecomp_hi", "uint32_t"),
                       ("lo", "openrecomp_lo", "uint32_t")),
        services=fixture_services(),
        entry_return_policy="fault",
        artifacts=((FIXTURE_ELF_PATH, FIXTURE_ELF_SHA256),),
    )


def rebuild_fixture(root_name: str = "p4-08") -> bytes:
    """Rebuild the fixture with the recorded P4-07 build recipe."""
    tools_dir = str(ROOT / "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import test_phase4_fixture_v1 as p407

    build = p407.build_fixture(root_name)
    if build["elf_sha256"] != FIXTURE_ELF_SHA256 or build["elf_size"] != FIXTURE_ELF_SIZE:
        raise FixtureExecError("rebuilt fixture ELF does not match the pinned identity")
    return build["data"]


def load_fixture_elf() -> bytes:
    path = ROOT / FIXTURE_ELF_PATH
    if path.is_file():
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() == FIXTURE_ELF_SHA256 and len(data) == FIXTURE_ELF_SIZE:
            return data
    return rebuild_fixture()


def analyze_fixture(data: bytes) -> dict[str, Any]:
    ingested = ingest(data, MIPS32_O32)
    text = next(section for section in ingested.parsed.sections if section.name == ".text")
    frontier = analyze(ingested.image.read_u32, text.sh_addr,
                       text.sh_addr + text.sh_size, ingested.parsed.header.e_entry)
    return {"ingested": ingested, "text": text, "frontier": frontier,
            "entry": ingested.parsed.header.e_entry}


def fixture_regions(data: bytes) -> tuple[gm.GuestRegion, ...]:
    ingested = ingest(data, MIPS32_O32)
    regions: list[gm.GuestRegion] = []
    file_bytes_by_offset: dict[int, bytes] = {}
    for segment in ingested.parsed.load_segments:
        payload = ingested.image.read(segment.p_vaddr, segment.p_filesz)
        file_bytes_by_offset[segment.p_vaddr] = payload
    definitions = (
        ("elf_image_headers", 0x0, 308, gm.RegionKind.RODATA),
        ("text", 0x1000, 3104, gm.RegionKind.CODE),
        ("rodata", 0x1C20, 129, gm.RegionKind.RODATA),
        ("data", 0x1CB0, 40, gm.RegionKind.DATA),
        ("bss_zero_fill", 0x1CD8, 9496, gm.RegionKind.BSS),
    )
    for name, start, size, kind in definitions:
        payload = file_bytes_by_offset.get(start, b"")[:size]
        regions.append(gm.region(name, start, size, kind, file_data=payload))
    return tuple(regions)


def fixture_memory_model(data: bytes) -> gm.GuestMemoryModel:
    return gm.GuestMemoryModel(fixture_regions(data), endianness="little", alignment="allow")


def fixture_image(data: bytes) -> bytes:
    ingested = ingest(data, MIPS32_O32)
    window = bytearray(IMAGE_WINDOW)
    for segment in ingested.parsed.load_segments:
        if segment.p_vaddr + segment.p_filesz > IMAGE_WINDOW:
            raise FixtureExecError("fixture load segment exceeds the image window")
        payload = ingested.image.read(segment.p_vaddr, segment.p_filesz)
        window[segment.p_vaddr:segment.p_vaddr + len(payload)] = payload
    return bytes(window)


def _format_image_rows(image: bytes, per_row: int = 16) -> str:
    rows = []
    for offset in range(0, len(image), per_row):
        chunk = image[offset:offset + per_row]
        rows.append("    " + ", ".join(f"0x{byte:02x}" for byte in chunk) + ",")
    return "\n".join(rows)


def _format_region_rows(regions: tuple[gm.GuestRegion, ...]) -> str:
    rows = []
    for item in regions:
        flags = gm.FROZEN_REGION_READABLE if item.readable else 0
        if item.writable:
            flags |= gm.FROZEN_REGION_WRITABLE
        rows.append(f"    {{ 0x{item.start:08x}u, 0x{item.end:08x}u, {flags}u }},")
    return "\n".join(rows)


PROGRAM_TEMPLATE = """\
/* OpenRecomp Phase-4 fixture host translation (P4-08). Architecture-neutral. */
/* source_elf_sha256: @@ELF_SHA256@@ */
/* generated-code <-> runtime ABI: @@ABI_NAME@@ @@ABI_VERSION@@ */
#include <stdint.h>
#include <stddef.h>

enum {
    OR_RT_OK = 0,
@@FAILURE_ENUM@@
};

@@SERVICE_MACROS@@

extern int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value);
extern int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value);
extern int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);
extern const char *or_rt_failure_reason(int code);

#define OR_IMAGE_WINDOW @@IMAGE_WINDOW@@u
#define OR_MAX_STEPS @@MAX_STEPS@@u
#define OR_ENTRY 0x@@ENTRY@@u
#define OR_REGION_READABLE 1u
#define OR_REGION_WRITABLE 2u
#define OR_REGION_COUNT @@REGION_COUNT@@u
#define OR_OUT_ADDR 0x20000000u
#define OR_IN_ADDR 0x20000004u
#define OR_EXIT_ADDR 0x20000008u
#define OR_TICKS_ADDR 0x2000000cu

static const uint8_t g_image[OR_IMAGE_WINDOW] = {
@@IMAGE_ROWS@@
};

static const uint32_t g_or_regions[OR_REGION_COUNT][3] = {
@@REGION_ROWS@@
};

static uint32_t g_r[32];
static uint32_t g_pc;
static uint32_t g_hi;
static uint32_t g_lo;
static uint64_t g_steps;
static uint32_t g_pending;
static uint32_t g_has_pending;
static int g_failed;
static const char *g_error = "";
static int g_exit_requested;

static void or_fail(const char *reason) {
    if (!g_failed) {
        g_failed = 1;
        g_error = reason;
    }
}

static void or_abi_failure(int code) {
    or_fail(or_rt_failure_reason(code));
}

static uint32_t or_region_flags(uint32_t address, uint32_t size) {
    uint32_t index;
    uint32_t end = address + size;
    if (end < address) {
        return 0u;
    }
    for (index = 0u; index < OR_REGION_COUNT; ++index) {
        uint32_t start = g_or_regions[index][0];
        uint32_t limit = g_or_regions[index][1];
        if (address >= start && end <= limit) {
            return g_or_regions[index][2];
        }
    }
    return 0u;
}

static uint32_t or_host_service(uint64_t service, uint32_t argc,
                                const uint64_t *args, uint64_t *result) {
    int code = or_rt_host_call(service, argc, args, result);
    if (code != OR_RT_OK) {
        or_abi_failure(code);
        return 0u;
    }
    return 1u;
}

static uint32_t or_load(uint32_t address, uint32_t size, uint32_t sign) {
    if (address == OR_IN_ADDR) {
        uint64_t result = 0u;
        if (size != 1u) { or_fail("input window requires a byte load"); return 0u; }
        if (!or_host_service(OR_RT_SERVICE_FIXTURE_IN, 0u, 0, &result)) { return 0u; }
        return (uint32_t)(result & 0xffu);
    }
    if (address == OR_TICKS_ADDR) {
        uint64_t result = 0u;
        if (size != 4u) { or_fail("ticks window requires a word load"); return 0u; }
        if (!or_host_service(OR_RT_SERVICE_FIXTURE_TICKS, 0u, 0, &result)) { return 0u; }
        return (uint32_t)result;
    }
    {
        uint64_t value = 0u;
        int code = or_rt_memory_read((uint64_t)address, size * 8u, &value);
        if (code != OR_RT_OK) {
            or_abi_failure(code);
            return 0u;
        }
        if (sign && size == 1u) { return (uint32_t)(int32_t)(int8_t)(value & 0xffu); }
        if (sign && size == 2u) { return (uint32_t)(int32_t)(int16_t)(value & 0xffffu); }
        return (uint32_t)value;
    }
}

static void or_store(uint32_t address, uint32_t size, uint32_t value) {
    if (address == OR_OUT_ADDR) {
        const uint64_t args[1] = { (uint64_t)(value & 0xffu) };
        if (size != 1u) { or_fail("output window requires a byte store"); return; }
        or_host_service(OR_RT_SERVICE_FIXTURE_OUT, 1u, args, 0);
        return;
    }
    if (address == OR_EXIT_ADDR) {
        const uint64_t args[1] = { (uint64_t)value };
        if (size != 4u) { or_fail("exit window requires a word store"); return; }
        if (or_host_service(OR_RT_SERVICE_FIXTURE_EXIT, 1u, args, 0)) {
            g_exit_requested = 1;
        }
        return;
    }
    {
        int code = or_rt_memory_write((uint64_t)address, size * 8u, (uint64_t)value);
        if (code != OR_RT_OK) {
            or_abi_failure(code);
        }
    }
}

static void or_partial_store(uint32_t address, uint32_t value, uint32_t left) {
    uint32_t aligned = address & ~3u;
    uint32_t offset = address & 3u;
    uint64_t word_value = 0u;
    uint8_t bytes[4];
    uint32_t index;
    uint32_t merged = 0u;
    int code = or_rt_memory_read((uint64_t)aligned, 32u, &word_value);
    if (code != OR_RT_OK) {
        or_abi_failure(code);
        return;
    }
    for (index = 0u; index < 4u; ++index) {
        bytes[index] = (uint8_t)(((uint32_t)word_value >> (8u * index)) & 0xffu);
    }
    if (left) {
        bytes[offset] = (uint8_t)((value >> 24u) & 0xffu);
        if (offset >= 1u) { bytes[offset - 1u] = (uint8_t)((value >> 16u) & 0xffu); }
        if (offset >= 2u) { bytes[offset - 2u] = (uint8_t)((value >> 8u) & 0xffu); }
        if (offset == 3u) { bytes[offset - 3u] = (uint8_t)(value & 0xffu); }
    } else {
        bytes[offset] = (uint8_t)(value & 0xffu);
        if (offset <= 2u) { bytes[offset + 1u] = (uint8_t)((value >> 8u) & 0xffu); }
        if (offset <= 1u) { bytes[offset + 2u] = (uint8_t)((value >> 16u) & 0xffu); }
        if (offset == 0u) { bytes[offset + 3u] = (uint8_t)((value >> 24u) & 0xffu); }
    }
    for (index = 0u; index < 4u; ++index) {
        merged |= (uint32_t)bytes[index] << (8u * index);
    }
    code = or_rt_memory_write((uint64_t)aligned, 32u, (uint64_t)merged);
    if (code != OR_RT_OK) {
        or_abi_failure(code);
    }
}

static void or_div(uint32_t numerator, uint32_t denominator) {
    if (denominator == 0u) {
        or_fail("division by zero");
        return;
    }
    g_lo = numerator / denominator;
    g_hi = numerator % denominator;
}

static void or_step(void) {
    switch (g_pc) {
@@CASES@@
    default:
        or_fail("pc outside the emitted image");
        break;
    }
}

void openrecomp_run(void) {
    g_pc = OR_ENTRY;
    while (!g_failed && !g_exit_requested && g_steps < OR_MAX_STEPS) {
        or_step();
        g_steps++;
    }
    if (!g_failed && !g_exit_requested && g_steps >= OR_MAX_STEPS) {
        or_fail("step limit exceeded");
    }
}

int openrecomp_failed(void) { return g_failed; }
const char *openrecomp_error(void) { return g_error; }
uint64_t openrecomp_steps(void) { return g_steps; }
uint32_t openrecomp_pc(void) { return g_pc; }
uint32_t openrecomp_hi(void) { return g_hi; }
uint32_t openrecomp_lo(void) { return g_lo; }
size_t openrecomp_register_count(void) { return 32u; }
uint32_t openrecomp_register_value(size_t index) {
    if (index >= 32u) { return 0u; }
    return g_r[index];
}
const uint8_t *openrecomp_image(void) { return g_image; }
uint32_t openrecomp_image_size(void) { return OR_IMAGE_WINDOW; }
uint32_t openrecomp_region_count(void) { return OR_REGION_COUNT; }
void openrecomp_region(uint32_t index, uint32_t *start, uint32_t *end, uint32_t *flags) {
    if (index >= OR_REGION_COUNT) { return; }
    *start = g_or_regions[index][0];
    *end = g_or_regions[index][1];
    *flags = g_or_regions[index][2];
}
"""


def emit_fixture_program(data: bytes) -> str:
    analysis = analyze_fixture(data)
    ingested = analysis["ingested"]
    records = {record["address"]: record
               for record in analysis["frontier"]["records"]}
    reachable = analysis["frontier"]["reachable_addresses"]
    regions = fixture_regions(data)
    image = fixture_image(data)
    cases: list[str] = []
    for address in sorted(reachable):
        record = records[address]
        try:
            body = emit_instruction(record)
        except HostEmitError as exc:
            raise FixtureExecError(f"emission failed closed at 0x{address:08x}: {exc}") from exc
        cases.append(f"    case 0x{address:08x}u:")
        cases.extend(body)
        if record["op"] not in CONTROL_OPS:
            cases.append("        if (g_has_pending) { g_pc = g_pending; g_has_pending = 0u; } "
                         "else { g_pc += 4u; }")
        cases.append("        break;")
    text = PROGRAM_TEMPLATE
    text = text.replace("@@ELF_SHA256@@", FIXTURE_ELF_SHA256)
    text = text.replace("@@ABI_NAME@@", rt.RUNTIME_ABI_NAME)
    text = text.replace("@@ABI_VERSION@@", rt.RUNTIME_ABI_VERSION)
    text = text.replace("@@FAILURE_ENUM@@", FAILURE_ENUM)
    text = text.replace("@@SERVICE_MACROS@@", SERVICE_MACROS)
    text = text.replace("@@IMAGE_WINDOW@@", str(IMAGE_WINDOW))
    text = text.replace("@@MAX_STEPS@@", str(MAX_STEPS))
    text = text.replace("@@ENTRY@@", f"{FIXTURE_ENTRY:08x}")
    text = text.replace("@@REGION_COUNT@@", str(len(regions)))
    text = text.replace("@@IMAGE_ROWS@@", _format_image_rows(image))
    text = text.replace("@@REGION_ROWS@@", _format_region_rows(regions))
    text = text.replace("@@CASES@@", "\n".join(cases))
    return text


SUPPORT_TEMPLATE = """\
/* OpenRecomp Phase-4 fixture runtime support (P4-08). */
/* Implements the runtime side of the generated-code <-> runtime ABI and the
   declared fixture instance services over the generic runtime contracts. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

enum {
    OR_RT_OK = 0,
@@FAILURE_ENUM@@
};

@@SERVICE_MACROS@@

extern int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value);
extern int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value);
extern int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);
extern const char *or_rt_failure_reason(int code);

void openrecomp_run(void);
int openrecomp_failed(void);
const char *openrecomp_error(void);
uint64_t openrecomp_steps(void);
uint32_t openrecomp_pc(void);
uint32_t openrecomp_hi(void);
uint32_t openrecomp_lo(void);
size_t openrecomp_register_count(void);
uint32_t openrecomp_register_value(size_t index);
const uint8_t *openrecomp_image(void);
uint32_t openrecomp_image_size(void);
uint32_t openrecomp_region_count(void);
void openrecomp_region(uint32_t index, uint32_t *start, uint32_t *end, uint32_t *flags);

#define OR_IMAGE_WINDOW @@IMAGE_WINDOW@@u
#define OR_OUTPUT_CAPACITY @@OUTPUT_CAPACITY@@u
#define OR_INPUT_CAPACITY @@INPUT_CAPACITY@@u
#define OR_INPUT_PLAN_LENGTH @@INPUT_LENGTH@@u
#define OR_REGION_READABLE 1u
#define OR_REGION_WRITABLE 2u

static uint8_t g_mem[OR_IMAGE_WINDOW];
static uint8_t g_output[OR_OUTPUT_CAPACITY];
static uint32_t g_output_len;
static uint8_t g_input[OR_INPUT_CAPACITY];
static uint32_t g_input_len;
static uint32_t g_input_pos;
static uint32_t g_exit_status;
static uint32_t g_exit_written;

static const uint8_t g_input_plan[OR_INPUT_CAPACITY] = {
@@INPUT_ROWS@@
};

static uint32_t or_region_flags(uint32_t address, uint32_t size, uint32_t *out_flags) {
    uint32_t index;
    uint32_t end = address + size;
    if (end < address) { return 0u; }
    for (index = 0u; index < openrecomp_region_count(); ++index) {
        uint32_t start = 0u, limit = 0u, flags = 0u;
        openrecomp_region(index, &start, &limit, &flags);
        if (address >= start && end <= limit) {
            if (out_flags) { *out_flags = flags; }
            return 1u;
        }
    }
    return 0u;
}

int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value) {
    uint32_t start;
    uint32_t size;
    uint32_t flags = 0u;
    uint32_t value = 0u;
    uint32_t index;
    if (out_value == 0) { return OR_RT_MEMORY_WIDTH_UNSUPPORTED; }
    if (width_bits != 8u && width_bits != 16u && width_bits != 32u) {
        return OR_RT_MEMORY_WIDTH_UNSUPPORTED;
    }
    if (address > 0xffffffffu) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    start = (uint32_t)address;
    size = width_bits / 8u;
    if (!or_region_flags(start, size, &flags)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    if (!(flags & OR_REGION_READABLE)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    for (index = 0u; index < size; ++index) {
        value |= (uint32_t)g_mem[start + index] << (8u * index);
    }
    *out_value = (uint64_t)value;
    return OR_RT_OK;
}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value) {
    uint32_t start;
    uint32_t size;
    uint32_t flags = 0u;
    uint32_t index;
    if (width_bits != 8u && width_bits != 16u && width_bits != 32u) {
        return OR_RT_MEMORY_WIDTH_UNSUPPORTED;
    }
    if (address > 0xffffffffu) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    start = (uint32_t)address;
    size = width_bits / 8u;
    if (!or_region_flags(start, size, &flags)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    if (!(flags & OR_REGION_WRITABLE)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    for (index = 0u; index < size; ++index) {
        g_mem[start + index] = (uint8_t)((value >> (8u * index)) & 0xffu);
    }
    return OR_RT_OK;
}

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args,
                    uint64_t *out_value) {
    if (service_id == (uint64_t)OR_RT_SERVICE_FIXTURE_EXIT) {
        if (argc != 1u || args == 0) { return OR_RT_HOST_CALL_ARITY; }
        if (g_exit_written) { return OR_RT_HOST_SERVICE_FAILED; }
        g_exit_status = (uint32_t)(args[0] & 0xffffffffu);
        g_exit_written = 1u;
        return OR_RT_OK;
    }
    if (service_id == (uint64_t)OR_RT_SERVICE_FIXTURE_IN) {
        if (argc != 0u) { return OR_RT_HOST_CALL_ARITY; }
        if (out_value == 0) { return OR_RT_HOST_SERVICE_FAILED; }
        if (g_input_pos >= g_input_len) { *out_value = UINT64_C(0xffffffff); return OR_RT_OK; }
        *out_value = (uint64_t)g_input[g_input_pos];
        g_input_pos += 1u;
        return OR_RT_OK;
    }
    if (service_id == (uint64_t)OR_RT_SERVICE_FIXTURE_OUT) {
        if (argc != 1u || args == 0) { return OR_RT_HOST_CALL_ARITY; }
        if (g_output_len >= OR_OUTPUT_CAPACITY) { return OR_RT_UNSUPPORTED_OPERATION; }
        g_output[g_output_len] = (uint8_t)(args[0] & 0xffu);
        g_output_len += 1u;
        return OR_RT_OK;
    }
    if (service_id == (uint64_t)OR_RT_SERVICE_FIXTURE_TICKS) {
        if (argc != 0u) { return OR_RT_HOST_CALL_ARITY; }
        if (out_value == 0) { return OR_RT_HOST_SERVICE_FAILED; }
        *out_value = openrecomp_steps();
        return OR_RT_OK;
    }
    return OR_RT_UNKNOWN_HOST_SERVICE;
}

static const char *or_failure_reasons[] = {
    "",
@@FAILURE_REASONS@@
};

const char *or_rt_failure_reason(int code) {
    if (code < 0 || (size_t)code >= sizeof(or_failure_reasons) / sizeof(or_failure_reasons[0])) {
        return "runtime failure";
    }
    return or_failure_reasons[code];
}

static uint64_t or_fnv1a64(uint64_t state, const uint8_t *data, size_t size) {
    size_t index;
    for (index = 0; index < size; ++index) {
        state ^= (uint64_t)data[index];
        state *= UINT64_C(0x100000001b3);
    }
    return state;
}

static uint64_t or_hash_u32(uint64_t state, uint32_t value) {
    uint8_t bytes[4];
    uint32_t index;
    for (index = 0u; index < 4u; ++index) {
        bytes[index] = (uint8_t)((value >> (8u * index)) & 0xffu);
    }
    return or_fnv1a64(state, bytes, sizeof(bytes));
}

static uint64_t or_state_hash(void) {
    uint64_t state = UINT64_C(0xcbf29ce484222325);
    uint32_t status = g_exit_written ? g_exit_status : 0xffffffffu;
    state = or_fnv1a64(state, (const uint8_t *)"OROBS1", 6u);
    state = or_hash_u32(state, OR_IMAGE_WINDOW);
    state = or_fnv1a64(state, g_mem, OR_IMAGE_WINDOW);
    state = or_hash_u32(state, 32u);
    for (uint32_t index = 0u; index < 32u; ++index) {
        state = or_hash_u32(state, openrecomp_register_value((size_t)index));
    }
    state = or_hash_u32(state, 2u);
    state = or_hash_u32(state, openrecomp_hi());
    state = or_hash_u32(state, openrecomp_lo());
    state = or_hash_u32(state, openrecomp_pc());
    {
        uint64_t steps = openrecomp_steps();
        uint8_t bytes[8];
        for (uint32_t index = 0u; index < 8u; ++index) {
            bytes[index] = (uint8_t)((steps >> (8u * index)) & 0xffu);
        }
        state = or_fnv1a64(state, bytes, sizeof(bytes));
    }
    state = or_hash_u32(state, status);
    state = or_hash_u32(state, g_output_len);
    state = or_fnv1a64(state, g_output, (size_t)g_output_len);
    return state;
}

int main(void) {
    const uint8_t *image = openrecomp_image();
    uint32_t index;
    uint32_t count = openrecomp_image_size();
    if (count > OR_IMAGE_WINDOW) { count = OR_IMAGE_WINDOW; }
    for (index = 0u; index < count; ++index) {
        g_mem[index] = image[index];
    }
    g_input_len = OR_INPUT_PLAN_LENGTH;
    for (index = 0u; index < OR_INPUT_PLAN_LENGTH; ++index) {
        g_input[index] = g_input_plan[index];
    }
    openrecomp_run();
    printf("exit_status=%u\\n", (unsigned)(g_exit_written ? g_exit_status : 0xffffffffu));
    printf("steps=%llu\\n", (unsigned long long)openrecomp_steps());
    printf("pc=0x%08x\\n", (unsigned)openrecomp_pc());
    printf("failed=%d\\n", openrecomp_failed());
    printf("failure=%s\\n", openrecomp_error());
    printf("output_bytes=%u\\n", (unsigned)g_output_len);
    printf("output_hex=");
    for (index = 0u; index < g_output_len; ++index) {
        printf("%02x", (unsigned)g_output[index]);
    }
    printf("\\n");
    printf("state_fnv1a64=0x%016llx\\n", (unsigned long long)or_state_hash());
    return 0;
}
"""


def emit_fixture_support() -> str:
    input_rows = "    " + ", ".join(f"0x{byte:02x}" for byte in INPUT_PLAN) + ","
    failure_reasons = "\n".join(
        f'    "{code}",' for code in rt.RUNTIME_FAILURE_CODES)
    text = SUPPORT_TEMPLATE
    text = text.replace("@@FAILURE_ENUM@@", FAILURE_ENUM)
    text = text.replace("@@SERVICE_MACROS@@", SERVICE_MACROS)
    text = text.replace("@@IMAGE_WINDOW@@", str(IMAGE_WINDOW))
    text = text.replace("@@OUTPUT_CAPACITY@@", str(OUTPUT_CAPACITY))
    text = text.replace("@@INPUT_CAPACITY@@", str(INPUT_CAPACITY))
    text = text.replace("@@INPUT_LENGTH@@", str(len(INPUT_PLAN)))
    text = text.replace("@@INPUT_ROWS@@", input_rows)
    text = text.replace("@@FAILURE_REASONS@@", failure_reasons)
    return text


@dataclass(frozen=True)
class FixtureTranslation:
    program_text: str
    support_text: str
    program_sha256: str
    support_sha256: str
    source_elf_sha256: str
    reachable_words: int
    entry: int

    def to_document(self) -> dict[str, Any]:
        return {
            "stage": "P4-08",
            "source_elf_sha256": self.source_elf_sha256,
            "program_sha256": self.program_sha256,
            "support_sha256": self.support_sha256,
            "reachable_words": self.reachable_words,
            "entry": hex(self.entry),
            "profile": fixture_profile().name,
            "services": [service.to_document() for service in fixture_services()],
        }


def translate_fixture(data: bytes) -> FixtureTranslation:
    program = emit_fixture_program(data)
    support = emit_fixture_support()
    analysis = analyze_fixture(data)
    return FixtureTranslation(
        program_text=program,
        support_text=support,
        program_sha256=hashlib.sha256(program.encode("utf-8")).hexdigest(),
        support_sha256=hashlib.sha256(support.encode("utf-8")).hexdigest(),
        source_elf_sha256=hashlib.sha256(data).hexdigest(),
        reachable_words=len(analysis["frontier"]["reachable_addresses"]),
        entry=analysis["entry"],
    )


def input_plan_document() -> dict[str, Any]:
    return json.loads((ROOT / INPUT_PLAN_PATH).read_text(encoding="utf-8"))
