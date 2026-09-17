#!/usr/bin/env python3
"""OpenRecomp Phase-3 deterministic MIPS32 host emission V1 (P3-07).

Emits one deterministic, portable C translation of the entire audited CoreMark
MIPS32 executable image (every decodable word), with exact instruction
semantics and true MIPS32 delay-slot behaviour, plus the host-side generic
runtime support that executes it through the frozen P2-08 runtime ABI boundary.

Guest translation (``program_text``):

* consumes the frozen P3-03 decode/classification records, the P3-05 neutral
  structure and the P3-06 static-data model; it never re-decodes bytes and
  never invents an address, register or target;
* every emitted instruction has an explicit semantic rule keyed by its decoded
  ``op``; an unrecognised op fails closed at emission time;
* every emitted direct transfer (branch/jump/call) must target an emitted word,
  and a control transfer whose delay slot is not an emitted non-control word
  fails closed at emission time;
* indirect transfers (``jr``/``jalr``) are emitted as *runtime-mediated*
  validated dispatch: the target is read from the guest register at run time,
  alignment is checked, and an address with no emitted case fails closed in the
  dispatcher. No static indirect target is guessed and none is needed;
* guest memory accesses go through the frozen P2-08 ABI
  (``or_rt_memory_read``/``or_rt_memory_write``); the two port MMIO windows are
  runtime-mediated host calls (``p3_uart_write``, ``p3_exit``); every other
  out-of-image access fails closed;
* every instruction is emitted exactly once and the dispatcher advances by one
  instruction per step with the MIPS32 delay-slot protocol
  (``g_pending``/``g_has_pending``).

Host support (``support_text``): deterministic region-checked memory, the UART
byte sink and exit-status window, the FNV-1a 64 observable digest and the
report. The observable contract (exit status, UART stream, step count, PC,
HI/LO and the digest order) is documented in the emitted text and re-implemented
independently by the P3-09 reference.

The emitted C is byte-identical for identical inputs and uses only portable C.

This module is OpenRecomp-original, standard-library only, and contains no
console assets, proprietary data or copied tables.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import p3_decode_mips32_v1 as decode_v1
from openrecomp import runtime_abi as rt_abi

HOST_EMIT_VERSION = "1.0.0"
MASK32 = 0xFFFFFFFF

IMAGE_WINDOW = 0x10000
MAX_STEPS = 400000000
UART_CAPACITY = 1 << 20
UART_ADDR = 0x10000000
EXIT_ADDR = 0x10000008
UART_SERVICE = "p3_uart_write"
EXIT_SERVICE = "p3_exit"

OP_SET = frozenset({
    "nop", "lui", "addiu", "ori", "andi", "xori", "slti", "sltiu",
    "addu", "subu", "and", "or", "xor", "nor", "slt", "sltu",
    "sll", "srl", "sra",
    "lb", "lbu", "lh", "lhu", "lw", "sb", "sh", "sw", "swl", "swr",
    "beq", "bne", "blez", "bgtz", "bltz", "bgez", "j", "jal", "jr",
    "mult", "multu", "div", "divu", "mfhi", "mflo", "mul",
    "movz", "movn", "teq", "jalr",
})


class HostEmitError(ValueError):
    """Fail-closed host-emission rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def runtime_services() -> rt_abi.RuntimeServiceTable:
    """The two runtime-mediated external services declared to the P2-08 ABI."""
    return rt_abi.RuntimeServiceTable(
        services=(
            rt_abi.RuntimeService(UART_SERVICE, 1),
            rt_abi.RuntimeService(EXIT_SERVICE, 1),
        ),
        handlers={
            UART_SERVICE: lambda args: None,
            EXIT_SERVICE: lambda args: None,
        },
    )


@dataclass(frozen=True)
class EmittedProgram:
    stage: str
    program_text: str
    support_text: str
    fingerprint: str
    support_fingerprint: str
    emitted_addresses: tuple[int, ...]
    case_count: int
    op_histogram: dict[str, int]
    link_histogram: dict[str, int]
    direct_targets: int
    indirect_sites: tuple[dict[str, Any], ...]
    delay_slots: int
    image_sha256: str
    region_table: tuple[tuple[int, int, str], ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "host_emit_version": HOST_EMIT_VERSION,
            "program_fingerprint": self.fingerprint,
            "support_fingerprint": self.support_fingerprint,
            "case_count": self.case_count,
            "op_histogram": dict(sorted(self.op_histogram.items())),
            "link_histogram": dict(sorted(self.link_histogram.items())),
            "direct_targets": self.direct_targets,
            "indirect_sites": list(self.indirect_sites),
            "delay_slots": self.delay_slots,
            "image_sha256": self.image_sha256,
            "region_table": [
                {"start": f"0x{start:08x}", "end": f"0x{end:08x}", "permissions": permissions}
                for start, end, permissions in self.region_table
            ],
            "emitted_addresses_sha256": hashlib.sha256(
                "\n".join(f"0x{address:08x}" for address in self.emitted_addresses)
                .encode("ascii")).hexdigest(),
        }


def _u32(value: int) -> str:
    return f"0x{value & MASK32:08x}u"


def _c_string(value: str) -> str:
    if any(ord(ch) > 0x7F for ch in value):
        raise HostEmitError("NON_ASCII_MESSAGE", value)
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _op(record: dict[str, Any], name: str) -> int:
    operands = record["operands"]
    if name not in operands:
        raise HostEmitError(
            "MISSING_OPERAND", f"0x{record['address']:08x} {record['op']} needs {name!r}")
    value = operands[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise HostEmitError(
            "INVALID_OPERAND", f"0x{record['address']:08x} {record['op']}.{name}={value!r}")
    return value


def _advance() -> str:
    return ("        if (g_has_pending) { g_pc = g_pending; g_has_pending = 0u; } "
            "else { g_pc += 4u; }")


def _transfer(target: int | None, taken: bool | None = None) -> list[str]:
    lines = []
    if taken is None:
        lines.append(f"        g_pending = {_u32(target)};")
    else:
        lines.append(f"        g_pending = ({taken}) ? {_u32(target)} : (g_pc + 8u);")
    lines.append("        g_has_pending = 1u;")
    lines.append("        g_pc += 4u;")
    return lines


def _setr(reg: int, expr: str) -> str:
    if reg == 0:
        return "        /* $zero write discarded */"
    return f"        g_r[{reg}] = ({expr}) & 0xffffffffu;"


def emit_instruction(record: dict[str, Any]) -> list[str]:
    """Emit one decoded instruction's C statements (fail closed on unknown ops)."""
    op = record["op"]
    address = record["address"]
    if op not in OP_SET:
        raise HostEmitError("UNSUPPORTED_OP", f"0x{address:08x} {op!r}")

    if op == "nop":
        return []
    if op == "lui":
        return [_setr(_op(record, "rt"), _u32(_op(record, "imm") << 16))]
    if op == "addiu":
        return [_setr(_op(record, "rt"),
                      f"g_r[{_op(record, 'rs')}] + (uint32_t)(int32_t){_op(record, 'imm')}")]
    if op == "ori":
        return [_setr(_op(record, "rt"),
                      f"g_r[{_op(record, 'rs')}] | {_u32(_op(record, 'imm'))}")]
    if op == "andi":
        return [_setr(_op(record, "rt"),
                      f"g_r[{_op(record, 'rs')}] & {_u32(_op(record, 'imm'))}")]
    if op == "xori":
        return [_setr(_op(record, "rt"),
                      f"g_r[{_op(record, 'rs')}] ^ {_u32(_op(record, 'imm'))}")]
    if op in ("slti", "sltiu"):
        if op == "slti":
            predicate = f"(int32_t)g_r[{_op(record, 'rs')}] < (int32_t){_op(record, 'imm')}"
        else:
            predicate = f"g_r[{_op(record, 'rs')}] < {_u32(_op(record, 'imm'))}"
        return [_setr(_op(record, "rt"), f"({predicate}) ? 1u : 0u")]
    if op == "addu":
        return [_setr(_op(record, "rd"),
                      f"g_r[{_op(record, 'rs')}] + g_r[{_op(record, 'rt')}]")]
    if op == "subu":
        return [_setr(_op(record, "rd"),
                      f"g_r[{_op(record, 'rs')}] - g_r[{_op(record, 'rt')}]")]
    if op == "and":
        return [_setr(_op(record, "rd"),
                      f"g_r[{_op(record, 'rs')}] & g_r[{_op(record, 'rt')}]")]
    if op == "or":
        return [_setr(_op(record, "rd"),
                      f"g_r[{_op(record, 'rs')}] | g_r[{_op(record, 'rt')}]")]
    if op == "xor":
        return [_setr(_op(record, "rd"),
                      f"g_r[{_op(record, 'rs')}] ^ g_r[{_op(record, 'rt')}]")]
    if op == "nor":
        return [_setr(_op(record, "rd"),
                      f"~(g_r[{_op(record, 'rs')}] | g_r[{_op(record, 'rt')}])")]
    if op == "slt":
        return [_setr(_op(record, "rd"),
                      f"((int32_t)g_r[{_op(record, 'rs')}] < (int32_t)g_r[{_op(record, 'rt')}]) ? 1u : 0u")]
    if op == "sltu":
        return [_setr(_op(record, "rd"),
                      f"(g_r[{_op(record, 'rs')}] < g_r[{_op(record, 'rt')}]) ? 1u : 0u")]
    if op in ("sll", "srl", "sra"):
        shamt = _op(record, "shamt")
        if not 0 <= shamt < 32:
            raise HostEmitError("INVALID_SHAMT", f"0x{address:08x} {shamt}")
        source = f"g_r[{_op(record, 'rt')}]"
        if op == "sll":
            expr = f"{source} << {shamt}"
        elif op == "srl":
            expr = f"{source} >> {shamt}"
        else:
            expr = f"(uint32_t)((int32_t){source} >> {shamt})"
        return [_setr(_op(record, "rd"), expr)]
    if op in ("lb", "lbu", "lh", "lhu", "lw"):
        width = {"lb": 1, "lbu": 1, "lh": 2, "lhu": 2, "lw": 4}[op]
        sign = 1 if op in ("lb", "lh") else 0
        return [_setr(_op(record, "rt"),
                      f"or_load(g_r[{_op(record, 'rs')}] + "
                      f"(uint32_t)(int32_t){_op(record, 'imm')}, {width}u, {sign}u)")]
    if op in ("sb", "sh", "sw"):
        width = {"sb": 1, "sh": 2, "sw": 4}[op]
        return [f"        or_store(g_r[{_op(record, 'rs')}] + "
                f"(uint32_t)(int32_t){_op(record, 'imm')}, {width}u, g_r[{_op(record, 'rt')}]);"]
    if op in ("swl", "swr"):
        rs = _op(record, "rs")
        rt = _op(record, "rt")
        imm = _op(record, "imm")
        return [f"        or_partial_store(g_r[{rs}] + (uint32_t)(int32_t){imm}, "
                f"g_r[{rt}], {1 if op == 'swl' else 0}u);"]
    if op == "beq":
        return _transfer(_op(record, "target"),
                         f"g_r[{_op(record, 'rs')}] == g_r[{_op(record, 'rt')}]")
    if op == "bne":
        return _transfer(_op(record, "target"),
                         f"g_r[{_op(record, 'rs')}] != g_r[{_op(record, 'rt')}]")
    if op == "blez":
        return _transfer(_op(record, "target"),
                         f"(int32_t)g_r[{_op(record, 'rs')}] <= 0")
    if op == "bgtz":
        return _transfer(_op(record, "target"),
                         f"(int32_t)g_r[{_op(record, 'rs')}] > 0")
    if op == "bltz":
        return _transfer(_op(record, "target"),
                         f"(int32_t)g_r[{_op(record, 'rs')}] < 0")
    if op == "bgez":
        return _transfer(_op(record, "target"),
                         f"(int32_t)g_r[{_op(record, 'rs')}] >= 0")
    if op == "j":
        return _transfer(_op(record, "target"))
    if op == "jal":
        lines = [_setr(31, "g_pc + 8u")]
        lines += _transfer(_op(record, "target"))
        return lines
    if op == "jr":
        rs = _op(record, "rs")
        return [
            f"        if ((g_r[{rs}] & 3u) != 0u) {{ or_fail(\"unaligned indirect jump target\"); }}",
            f"        else {{ g_pending = g_r[{rs}]; g_has_pending = 1u; g_pc += 4u; }}",
        ]
    if op == "jalr":
        rs = _op(record, "rs")
        rd = _op(record, "rd")
        lines = []
        if rd != 0:
            lines.append(f"        g_r[{rd}] = (g_pc + 8u) & 0xffffffffu;")
        lines += [
            f"        if ((g_r[{rs}] & 3u) != 0u) {{ or_fail(\"unaligned indirect call target\"); }}",
            f"        else {{ g_pending = g_r[{rs}]; g_has_pending = 1u; g_pc += 4u; }}",
        ]
        return lines
    if op in ("mult", "multu"):
        rs = _op(record, "rs")
        rt = _op(record, "rt")
        if op == "mult":
            expr = f"(uint64_t)(int64_t)(int32_t)g_r[{rs}] * (uint64_t)(int64_t)(int32_t)g_r[{rt}]"
        else:
            expr = f"(uint64_t)g_r[{rs}] * (uint64_t)g_r[{rt}]"
        return [f"        {{ const uint64_t or_product = {expr};",
                "          g_lo = (uint32_t)(or_product & 0xffffffffu);",
                "          g_hi = (uint32_t)(or_product >> 32u); }"]
    if op == "div":
        return [f"        or_div(g_r[{_op(record, 'rs')}], g_r[{_op(record, 'rt')}]);"]
    if op == "divu":
        return [f"        or_div(g_r[{_op(record, 'rs')}], g_r[{_op(record, 'rt')}]);"]
    if op == "mfhi":
        return [_setr(_op(record, "rd"), "g_hi")]
    if op == "mflo":
        return [_setr(_op(record, "rd"), "g_lo")]
    if op == "mul":
        rs = _op(record, "rs")
        rt = _op(record, "rt")
        rd = _op(record, "rd")
        return [_setr(rd, f"(uint32_t)((int32_t)g_r[{rs}] * (int32_t)g_r[{rt}])")]
    if op == "movz":
        return [f"        if (g_r[{_op(record, 'rt')}] == 0u) {{",
                _setr(_op(record, "rd"), f"g_r[{_op(record, 'rs')}]"),
                "        }"]
    if op == "movn":
        return [f"        if (g_r[{_op(record, 'rt')}] != 0u) {{",
                _setr(_op(record, "rd"), f"g_r[{_op(record, 'rs')}]"),
                "        }"]
    if op == "teq":
        return [f"        if (g_r[{_op(record, 'rs')}] == g_r[{_op(record, 'rt')}]) {{",
                f"          or_fail({_c_string('teq trap code=0x%x' % _op(record, 'code'))});",
                "        }"]
    raise HostEmitError("UNHANDLED_OP", f"0x{address:08x} {op!r}")


def _format_rows(data: bytes, per_row: int = 16) -> list[str]:
    rows = []
    for offset in range(0, len(data), per_row):
        chunk = data[offset:offset + per_row]
        rows.append("    " + " ".join(f"0x{byte:02x}," for byte in chunk))
    return rows


PROGRAM_HELPERS = """\
static void or_step(void);

static uint64_t g_r[32];
static uint32_t g_hi;
static uint32_t g_lo;
static uint32_t g_pc;
static uint32_t g_pending;
static uint32_t g_has_pending;
static uint64_t g_steps;
static uint32_t g_exited;
static uint32_t g_failed;
static const char *g_error = "";

static void or_fail(const char *message) {
    if (!g_failed) { g_error = message; }
    g_failed = 1u;
}

static void or_abi_failure(int code) {
    or_fail(or_rt_failure_reason(code));
}

static uint32_t or_load(uint32_t address, uint32_t size, uint32_t sign) {
    uint64_t value = 0u;
    int code = or_rt_memory_read((uint64_t)address, size * 8u, &value);
    if (code != OR_RT_OK) {
        or_abi_failure(code);
        return 0u;
    }
    uint32_t result = (uint32_t)(value & 0xffffffffu);
    if (sign && size < 4u) {
        uint32_t bits = size * 8u;
        if (result & (1u << (bits - 1u))) {
            result |= (0xffffffffu << bits);
        }
    }
    return result;
}

static void or_host_service(uint64_t service, uint32_t argc, const uint64_t *args) {
    uint64_t result = 0u;
    int code = or_rt_host_call(service, argc, args, &result);
    if (code != OR_RT_OK) {
        or_abi_failure(code);
    }
}

static void or_store(uint32_t address, uint32_t size, uint32_t value) {
    if (address == OR_UART_ADDR) {
        if (size != 1u) { or_fail("UART window requires a byte store"); return; }
        { const uint64_t or_args[1] = { (uint64_t)(value & 0xffu) };
          or_host_service(OR_RT_SERVICE_P3_UART_WRITE, 1u, or_args); }
        return;
    }
    if (address == OR_EXIT_ADDR) {
        if (size != 4u) { or_fail("exit window requires a word store"); return; }
        if (g_exited) { or_fail("exit window written twice"); return; }
        { const uint64_t or_args[1] = { (uint64_t)value };
          or_host_service(OR_RT_SERVICE_P3_EXIT, 1u, or_args); }
        g_exited = 1u;
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
    int code = or_rt_memory_read((uint64_t)aligned, 32u, &word_value);
    if (code != OR_RT_OK) {
        or_abi_failure(code);
        return;
    }
    uint8_t bytes[4];
    for (uint32_t index = 0; index < 4u; ++index) {
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
    uint32_t merged = 0u;
    for (uint32_t index = 0; index < 4u; ++index) {
        merged |= (uint32_t)bytes[index] << (8u * index);
    }
    code = or_rt_memory_write((uint64_t)aligned, 32u, (uint64_t)merged);
    if (code != OR_RT_OK) {
        or_abi_failure(code);
    }
}

static void or_div(uint32_t dividend, uint32_t divisor) {
    if (divisor == 0u) {
        or_fail("divide by zero");
        return;
    }
    g_lo = dividend / divisor;
    g_hi = dividend % divisor;
}

void openrecomp_run(void) {
    for (uint32_t index = 0; index < 32u; ++index) { g_r[index] = 0u; }
    g_hi = 0u;
    g_lo = 0u;
    g_pending = 0u;
    g_has_pending = 0u;
    g_steps = 0u;
    g_exited = 0u;
    g_failed = 0u;
    g_error = "";
    g_pc = OR_ENTRY;
    while (!g_exited && !g_failed && g_steps < OR_MAX_STEPS) {
        ++g_steps;
        or_step();
    }
    if (!g_exited && !g_failed) {
        or_fail("step limit exceeded");
    }
}

int openrecomp_failed(void) { return (int)g_failed; }
const char *openrecomp_error(void) { return g_error; }
uint64_t openrecomp_steps(void) { return g_steps; }
uint32_t openrecomp_pc(void) { return g_pc; }
uint32_t openrecomp_hi(void) { return g_hi; }
uint32_t openrecomp_lo(void) { return g_lo; }
size_t openrecomp_register_count(void) { return 32u; }
uint32_t openrecomp_register_value(size_t index) {
    return index < 32u ? (uint32_t)g_r[index] : 0u;
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


SUPPORT_HELPERS = """\
static uint8_t g_mem[OR_IMAGE_WINDOW];
static uint8_t g_uart[OR_UART_CAPACITY];
static uint32_t g_uart_len;
static uint32_t g_exit_status;
static uint32_t g_exit_written;

static uint32_t or_region_flags(uint32_t address, uint32_t size, uint32_t *out_flags) {
    uint32_t end = address + size;
    if (end < address) { return 0u; }
    for (uint32_t index = 0; index < openrecomp_region_count(); ++index) {
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
    if (out_value == 0) { return OR_RT_MEMORY_WIDTH_UNSUPPORTED; }
    if (width_bits != 8u && width_bits != 16u && width_bits != 32u) {
        return OR_RT_MEMORY_WIDTH_UNSUPPORTED;
    }
    if (address > 0xffffffffu) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    uint32_t start = (uint32_t)address;
    uint32_t size = width_bits / 8u;
    uint32_t flags = 0u;
    if (!or_region_flags(start, size, &flags)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    if (!(flags & OR_REGION_READABLE)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    uint32_t value = 0u;
    for (uint32_t index = 0; index < size; ++index) {
        value |= (uint32_t)g_mem[start + index] << (8u * index);
    }
    *out_value = (uint64_t)value;
    return OR_RT_OK;
}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value) {
    if (width_bits != 8u && width_bits != 16u && width_bits != 32u) {
        return OR_RT_MEMORY_WIDTH_UNSUPPORTED;
    }
    if (address > 0xffffffffu) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    uint32_t start = (uint32_t)address;
    uint32_t size = width_bits / 8u;
    uint32_t flags = 0u;
    if (!or_region_flags(start, size, &flags)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    if (!(flags & OR_REGION_WRITABLE)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    for (uint32_t index = 0; index < size; ++index) {
        g_mem[start + index] = (uint8_t)((value >> (8u * index)) & 0xffu);
    }
    return OR_RT_OK;
}

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value) {
    (void)out_value;
    if (service_id == OR_RT_SERVICE_P3_UART_WRITE) {
        if (argc != 1u || args == 0) { return OR_RT_HOST_CALL_ARITY; }
        if (g_uart_len >= OR_UART_CAPACITY) { return OR_RT_HOST_SERVICE_FAILED; }
        g_uart[g_uart_len++] = (uint8_t)(args[0] & 0xffu);
        return OR_RT_OK;
    }
    if (service_id == OR_RT_SERVICE_P3_EXIT) {
        if (argc != 1u || args == 0) { return OR_RT_HOST_CALL_ARITY; }
        if (g_exit_written) { return OR_RT_HOST_SERVICE_FAILED; }
        g_exit_status = (uint32_t)(args[0] & 0xffffffffu);
        g_exit_written = 1u;
        return OR_RT_OK;
    }
    return OR_RT_UNKNOWN_HOST_SERVICE;
}

static const char *or_failure_reasons[] = {
    "",
__REASONS__
};

const char *or_rt_failure_reason(int code) {
    if (code < 0 || (size_t)code >= sizeof(or_failure_reasons) / sizeof(or_failure_reasons[0])) {
        return "runtime failure";
    }
    return or_failure_reasons[code];
}

static uint64_t or_fnv1a64(uint64_t hash, const uint8_t *data, size_t size) {
    for (size_t index = 0; index < size; ++index) {
        hash ^= (uint64_t)data[index];
        hash *= UINT64_C(0x100000001b3);
    }
    return hash;
}

static uint64_t or_hash_u32(uint64_t hash, uint32_t value) {
    uint8_t bytes[4];
    for (uint32_t index = 0; index < 4u; ++index) {
        bytes[index] = (uint8_t)((value >> (8u * index)) & 0xffu);
    }
    return or_fnv1a64(hash, bytes, sizeof(bytes));
}

static uint64_t or_state_hash(void) {
    uint64_t hash = UINT64_C(0xcbf29ce484222325);
    hash = or_fnv1a64(hash, g_mem, sizeof(g_mem));
    for (uint32_t index = 0; index < openrecomp_register_count(); ++index) {
        hash = or_hash_u32(hash, openrecomp_register_value(index));
    }
    hash = or_hash_u32(hash, openrecomp_hi());
    hash = or_hash_u32(hash, openrecomp_lo());
    hash = or_hash_u32(hash, openrecomp_pc());
    hash = or_hash_u32(hash, (uint32_t)openrecomp_steps());
    hash = or_hash_u32(hash, g_exit_status);
    hash = or_hash_u32(hash, g_uart_len);
    hash = or_fnv1a64(hash, g_uart, (size_t)g_uart_len);
    return hash;
}

int main(void) {
    const uint8_t *image = openrecomp_image();
    for (uint32_t index = 0; index < openrecomp_image_size(); ++index) {
        g_mem[index] = image[index];
    }
    openrecomp_run();
    printf("exit_status=%u\\n", (unsigned)g_exit_status);
    printf("steps=%llu\\n", (unsigned long long)openrecomp_steps());
    printf("pc=0x%08x\\n", (unsigned)openrecomp_pc());
    printf("hi=0x%08x\\n", (unsigned)openrecomp_hi());
    printf("lo=0x%08x\\n", (unsigned)openrecomp_lo());
    printf("uart_bytes=%u\\n", (unsigned)g_uart_len);
    printf("uart_hex=");
    for (uint32_t index = 0; index < g_uart_len; ++index) {
        printf("%02x", (unsigned)g_uart[index]);
    }
    printf("\\n");
    printf("state_fnv1a64=0x%016llx\\n", (unsigned long long)or_state_hash());
    printf("failed=%d\\n", openrecomp_failed());
    printf("failure=%s\\n", openrecomp_error());
    return 0;
}
"""


def emit_program(
    analysis: dict[str, Any],
    model,
    *,
    source_sha256: str,
) -> EmittedProgram:
    """Emit the deterministic host C translation of the audited image."""
    emitted: dict[int, dict[str, Any]] = {}
    for record in analysis["records"]:
        if decode_v1.is_invalid(record):
            continue
        if record["terminator"] == decode_v1.TERM_UNSUPPORTED_CONTROL:
            raise HostEmitError("UNSUPPORTED_CONTROL", f"0x{record['address']:08x} {record['op']}")
        if record["terminator"] == decode_v1.TERM_EXTERNAL_TRAP:
            raise HostEmitError("EXTERNAL_TRAP_OP", f"0x{record['address']:08x} {record['op']}")
        if record["op"] not in OP_SET:
            raise HostEmitError("UNSUPPORTED_OP", f"0x{record['address']:08x} {record['op']!r}")
        emitted[record["address"]] = record
    if not emitted:
        raise HostEmitError("EMPTY_IMAGE", "no decodable words")

    delay_slots = 0
    for address in sorted(emitted):
        record = emitted[address]
        if record["control_flow"] and record["delay_slot"]:
            delay = address + 4
            if delay not in emitted:
                raise HostEmitError(
                    "DELAY_SLOT_NOT_EMITTED", f"0x{address:08x} delay=0x{delay:08x}")
            if emitted[delay]["control_flow"]:
                raise HostEmitError(
                    "CONTROL_IN_DELAY_SLOT", f"0x{address:08x} delay=0x{delay:08x}")
            delay_slots += 1
        if record["terminator"] == decode_v1.TERM_UNSUPPORTED_CONTROL:
            raise HostEmitError("UNSUPPORTED_CONTROL", f"0x{address:08x} {record['op']}")
        if record["terminator"] == decode_v1.TERM_EXTERNAL_TRAP:
            raise HostEmitError("EXTERNAL_TRAP_OP", f"0x{address:08x} {record['op']}")

    direct_targets = 0
    for address in sorted(emitted):
        record = emitted[address]
        if record["target"] is not None and record["control_flow"]:
            target = record["target"]
            if target not in emitted:
                raise HostEmitError(
                    "DIRECT_TARGET_NOT_EMITTED", f"0x{address:08x} -> 0x{target:08x}")
            direct_targets += 1

    op_histogram: dict[str, int] = {}
    link_histogram: dict[str, int] = {}
    for record in emitted.values():
        op_histogram[record["op"]] = op_histogram.get(record["op"], 0) + 1
        if record["terminator"] is not None:
            link_histogram[record["terminator"]] = link_histogram.get(record["terminator"], 0) + 1

    indirect_sites = []
    for address in sorted(emitted):
        record = emitted[address]
        if record["terminator"] in (decode_v1.TERM_INDIRECT_JUMP, decode_v1.TERM_INDIRECT_CALL):
            if record["target"] is not None:
                raise HostEmitError("INDIRECT_WITH_TARGET", f"0x{address:08x}")
            indirect_sites.append({
                "address": f"0x{address:08x}",
                "op": record["op"],
                "resolution": "runtime-mediated validated dispatch; no static target",
            })

    region_table = []
    for region in sorted(model.regions, key=lambda item: item.vaddr):
        if region.vaddr + region.size > IMAGE_WINDOW:
            raise HostEmitError("REGION_OUTSIDE_WINDOW", f"0x{region.vaddr:08x}+{region.size}")
        flags = []
        if "r" in region.permissions:
            flags.append("OR_REGION_READABLE")
        if "w" in region.permissions:
            flags.append("OR_REGION_WRITABLE")
        if not flags:
            raise HostEmitError("REGION_WITHOUT_ACCESS", f"0x{region.vaddr:08x}")
        region_table.append(
            (region.vaddr, region.vaddr + region.size, " | ".join(flags)))

    image_bytes = bytearray(IMAGE_WINDOW)
    for region in sorted(model.regions, key=lambda item: item.vaddr):
        if not region.content:
            continue
        if len(region.content) != region.size:
            raise HostEmitError(
                "REGION_CONTENT_SIZE",
                f"0x{region.vaddr:08x} declared={region.size} content={len(region.content)}")
        image_bytes[region.vaddr:region.vaddr + region.size] = region.content
    image_sha256 = hashlib.sha256(bytes(image_bytes)).hexdigest()

    services = runtime_services()
    abi_text = rt_abi.abi_c_declarations(services).rstrip("\n")

    lines: list[str] = []
    lines.append("/* OpenRecomp Phase-3 deterministic MIPS32 host translation (P3-07). */")
    lines.append(f"/* host_emit_version: {HOST_EMIT_VERSION} */")
    lines.append(f"/* guest_elf_sha256: {source_sha256} */")
    lines.append(f"/* guest_image_sha256: {image_sha256} */")
    lines.append(f"/* emitted_case_count: {len(emitted)} */")
    lines.append(f"/* direct_targets: {direct_targets}; delay_slots: {delay_slots} */")
    lines.append("/* Generated from the frozen P3-03 decode records, the P3-05 neutral")
    lines.append("   structure and the P3-06 static-data model. Indirect transfers are")
    lines.append("   runtime-mediated: the target is validated at run time and an address")
    lines.append("   with no emitted case fails closed in the dispatcher. */")
    lines.append("#include <stdint.h>")
    lines.append("#include <stddef.h>")
    lines.append("")
    lines.append(abi_text)
    lines.append("")
    lines.append(f"#define OR_IMAGE_WINDOW {IMAGE_WINDOW}u")
    lines.append(f"#define OR_MAX_STEPS {MAX_STEPS}u")
    lines.append(f"#define OR_UART_CAPACITY {UART_CAPACITY}u")
    lines.append(f"#define OR_UART_ADDR {_u32(UART_ADDR)}")
    lines.append(f"#define OR_EXIT_ADDR {_u32(EXIT_ADDR)}")
    lines.append(f"#define OR_ENTRY {_u32(analysis['entry'])}")
    lines.append("#define OR_REGION_READABLE 1u")
    lines.append("#define OR_REGION_WRITABLE 2u")
    lines.append(f"#define OR_REGION_COUNT {len(region_table)}u")
    lines.append("")
    lines.append("static const uint8_t g_image[OR_IMAGE_WINDOW] = {")
    lines.extend(_format_rows(bytes(image_bytes)))
    lines.append("};")
    lines.append("")
    lines.append("static const uint32_t g_or_regions[OR_REGION_COUNT][3] = {")
    for start, end, flags in region_table:
        lines.append(f"    {{ {_u32(start)}, {_u32(end)}, {flags} }},")
    lines.append("};")
    lines.append("")
    lines.append(PROGRAM_HELPERS.rstrip("\n"))
    lines.append("")
    lines.append("static void or_step(void) {")
    lines.append("    switch (g_pc) {")
    for address in sorted(emitted):
        record = emitted[address]
        lines.append(f"    case {_u32(address)}: /* {record['op']} */")
        body = list(emit_instruction(record))
        if not record["control_flow"]:
            body.append(_advance())
        lines.extend(body)
        lines.append("        break;")
    lines.append("    default:")
    lines.append('        or_fail("pc outside the emitted image");')
    lines.append("        g_pc = 0xfffffffcu;")
    lines.append("        break;")
    lines.append("    }")
    lines.append("}")
    lines.append("")
    program_text = "\n".join(lines) + "\n"

    support_lines: list[str] = []
    support_lines.append("/* OpenRecomp Phase-3 CoreMark host runtime support (P3-07/P3-08). */")
    support_lines.append(f"/* host_emit_version: {HOST_EMIT_VERSION} */")
    support_lines.append(f"/* guest_image_sha256: {image_sha256} */")
    support_lines.append("/* Observable contract (re-implemented independently by the P3-09")
    support_lines.append("   reference): after openrecomp_run(), report exit_status, steps, pc, hi,")
    support_lines.append("   lo, uart_bytes, uart_hex and state_fnv1a64 (FNV-1a 64 over the flat")
    support_lines.append("   image bytes, the 32 registers little-endian, hi, lo, pc, steps,")
    support_lines.append("   exit_status, uart_len and the uart bytes, in that order). */")
    support_lines.append("#include <stdint.h>")
    support_lines.append("#include <stddef.h>")
    support_lines.append("#include <stdio.h>")
    support_lines.append("")
    support_lines.append(abi_text)
    support_lines.append("")
    support_lines.append(f"#define OR_IMAGE_WINDOW {IMAGE_WINDOW}u")
    support_lines.append(f"#define OR_UART_CAPACITY {UART_CAPACITY}u")
    support_lines.append("#define OR_REGION_READABLE 1u")
    support_lines.append("#define OR_REGION_WRITABLE 2u")
    support_lines.append("")
    support_lines.append("void openrecomp_run(void);")
    support_lines.append("int openrecomp_failed(void);")
    support_lines.append("const char *openrecomp_error(void);")
    support_lines.append("uint64_t openrecomp_steps(void);")
    support_lines.append("uint32_t openrecomp_pc(void);")
    support_lines.append("uint32_t openrecomp_hi(void);")
    support_lines.append("uint32_t openrecomp_lo(void);")
    support_lines.append("size_t openrecomp_register_count(void);")
    support_lines.append("uint32_t openrecomp_register_value(size_t index);")
    support_lines.append("const uint8_t *openrecomp_image(void);")
    support_lines.append("uint32_t openrecomp_image_size(void);")
    support_lines.append("uint32_t openrecomp_region_count(void);")
    support_lines.append("void openrecomp_region(uint32_t index, uint32_t *start, uint32_t *end, uint32_t *flags);")
    support_lines.append("")
    support_lines.append(SUPPORT_HELPERS.replace(
        "__REASONS__",
        "\n".join(f'    {_c_string(code)},' for code in rt_abi.RUNTIME_FAILURE_CODES)))
    support_lines.append("")
    support_text = "\n".join(support_lines) + "\n"

    return EmittedProgram(
        stage="P3-07",
        program_text=program_text,
        support_text=support_text,
        fingerprint=hashlib.sha256(program_text.encode("utf-8")).hexdigest(),
        support_fingerprint=hashlib.sha256(support_text.encode("utf-8")).hexdigest(),
        emitted_addresses=tuple(sorted(emitted)),
        case_count=len(emitted),
        op_histogram=op_histogram,
        link_histogram=link_histogram,
        direct_targets=direct_targets,
        indirect_sites=tuple(indirect_sites),
        delay_slots=delay_slots,
        image_sha256=image_sha256,
        region_table=tuple(region_table),
    )


__all__ = [
    "EXIT_ADDR",
    "EXIT_SERVICE",
    "EmittedProgram",
    "HOST_EMIT_VERSION",
    "HostEmitError",
    "IMAGE_WINDOW",
    "MAX_STEPS",
    "OP_SET",
    "UART_ADDR",
    "UART_CAPACITY",
    "UART_SERVICE",
    "emit_instruction",
    "emit_program",
    "runtime_services",
]
