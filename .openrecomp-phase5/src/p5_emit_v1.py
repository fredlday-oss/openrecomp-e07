#!/usr/bin/env python3
"""Phase-5 deterministic NES host emission (P5-08).

Emits a deterministic C translation of the audited public fixture's neutral
instructions plus the bounded NES platform runtime support, using the shared
Phase-2 host build pipeline (`openrecomp.build_pipeline`). The generated
program:

* is a switch-over-PC machine on the proven 6502 subset with documented
  semantics (flags, stack, page wrap, RMW, JMP-indirect page wrap, BRK/RTI);
* calls only the typed runtime ABI externs (`or_rt_memory_read/write`,
  `or_rt_host_call`, `or_rt_failure_reason`) - never arbitrary host code;
* performs NMI entry as generated host logic at instruction boundaries when
  the platform support reports a due delivery;
* maps the single declared indirect run-exit site to the declared `p5.exit`
  host service; any other indirect site fails closed at emission;
* never executes original guest code on the host.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402
import p5_platform_v1 as platform  # noqa: E402

EXIT_SERVICE_NAME = "p5.exit"
EXIT_SERVICE_ID = 1
DEFAULT_MAX_STEPS = 4000000


class HostEmitError(ValueError):
    """Fail-closed host emission error."""


PROGRAM_TEMPLATE = """\
/* OpenRecomp Phase-5 NES host translation (P5-08). Generated deterministically. */
/* source_rom_sha256: @@ROM_SHA256@@ */
/* region: 0x@@REGION_START@@-0x@@REGION_END@@ instructions=@@INSTRUCTION_COUNT@@ */
#include <stdint.h>
#include <stddef.h>

enum {
    OR_RT_OK = 0,
    OR_RT_MEMORY_OUT_OF_RANGE = 1,
    OR_RT_MEMORY_WIDTH_UNSUPPORTED = 2,
    OR_RT_MEMORY_ADDRESS_OVERFLOW = 3,
    OR_RT_MEMORY_ENDIANNESS_UNSUPPORTED = 4,
    OR_RT_MEMORY_SEGMENT_OVERLAP = 5,
    OR_RT_UNKNOWN_HOST_SERVICE = 6,
    OR_RT_HOST_SERVICE_FAILED = 7,
    OR_RT_HOST_CALL_ARITY = 8,
    OR_RT_INPUT_INVALID = 9,
    OR_RT_FRAME_INVALID = 10,
    OR_RT_AUDIO_INVALID = 11,
    OR_RT_ABI_VERSION_MISMATCH = 12,
    OR_RT_UNSUPPORTED_OPERATION = 13,
    OR_RT_TRAP = 14,
};

#define OR_RT_SERVICE_P5_EXIT UINT64_C(@@EXIT_SERVICE_ID@@)

extern int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value);
extern int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value);
extern int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);
extern const char *or_rt_failure_reason(int code);
extern int or_rt_take_nmi(void);
extern void or_rt_advance(uint32_t cost);

#define OR_MAX_STEPS @@MAX_STEPS@@u
#define OR_ENTRY 0x@@ENTRY@@u

static uint8_t g_a, g_x, g_y, g_sp;
static uint16_t g_pc;
static uint8_t g_c, g_z, g_n, g_v, g_d, g_i;
static uint64_t g_steps;
static int g_failed;
static const char *g_error = "";
static int g_exit_requested;

static void or_fail(const char *message) {
    if (!g_failed) { g_failed = 1; g_error = message; }
}

static uint8_t or_read(uint16_t address) {
    uint64_t value = 0u;
    if (or_rt_memory_read((uint64_t)address, 8u, &value) != OR_RT_OK) {
        or_fail(or_rt_failure_reason(OR_RT_MEMORY_OUT_OF_RANGE));
        return 0u;
    }
    return (uint8_t)value;
}

static void or_write(uint16_t address, uint8_t value) {
    if (or_rt_memory_write((uint64_t)address, 8u, (uint64_t)value) != OR_RT_OK) {
        or_fail(or_rt_failure_reason(OR_RT_MEMORY_OUT_OF_RANGE));
    }
}

static uint16_t or_read16(uint16_t address) {
    return (uint16_t)((uint16_t)or_read(address)
        | ((uint16_t)or_read((uint16_t)(address + 1u)) << 8));
}

static uint16_t or_indirect(uint16_t pointer) {
    uint8_t lo = or_read(pointer);
    uint16_t high_address = (uint16_t)((pointer & 0xFF00u)
        | ((uint16_t)(pointer + 1u) & 0x00FFu));
    return (uint16_t)((uint16_t)lo | ((uint16_t)or_read(high_address) << 8));
}

static void or_push(uint8_t value) {
    or_write((uint16_t)(0x0100u | (uint16_t)g_sp), value);
    g_sp = (uint8_t)(g_sp - 1u);
}

static uint8_t or_pop(void) {
    g_sp = (uint8_t)(g_sp + 1u);
    return or_read((uint16_t)(0x0100u | (uint16_t)g_sp));
}

static void or_set_nz(uint8_t value) {
    g_n = (uint8_t)((value >> 7u) & 1u);
    g_z = (uint8_t)(value == 0u);
}

static uint8_t or_status(uint8_t break_flag) {
    return (uint8_t)(0x20u | (uint8_t)((g_n << 7u) | (g_v << 6u)
        | (break_flag << 4u) | (g_d << 3u) | (g_i << 2u) | (g_z << 1u) | g_c));
}

static void or_set_status(uint8_t value) {
    g_n = (uint8_t)((value >> 7u) & 1u);
    g_v = (uint8_t)((value >> 6u) & 1u);
    g_d = (uint8_t)((value >> 3u) & 1u);
    g_i = (uint8_t)((value >> 2u) & 1u);
    g_z = (uint8_t)((value >> 1u) & 1u);
    g_c = (uint8_t)(value & 1u);
}

static uint16_t or_addr_zp(uint8_t zp) { return zp; }
static uint16_t or_addr_zpx(uint8_t zp) { return (uint16_t)((uint8_t)(zp + g_x)); }
static uint16_t or_addr_zpy(uint8_t zp) { return (uint16_t)((uint8_t)(zp + g_y)); }
static uint16_t or_addr_absx(uint16_t abs) { return (uint16_t)(abs + g_x); }
static uint16_t or_addr_absy(uint16_t abs) { return (uint16_t)(abs + g_y); }
static uint16_t or_addr_indx(uint8_t zp) {
    uint8_t base = (uint8_t)(zp + g_x);
    return (uint16_t)((uint16_t)or_read(base)
        | ((uint16_t)or_read((uint8_t)(base + 1u)) << 8));
}
static uint16_t or_addr_indy(uint8_t zp) {
    uint16_t base = (uint16_t)((uint16_t)or_read(zp)
        | ((uint16_t)or_read((uint8_t)(zp + 1u)) << 8));
    return (uint16_t)(base + g_y);
}

static void or_nmi_entry(void) {
    or_push((uint8_t)(g_pc >> 8u));
    or_push((uint8_t)(g_pc & 0x00FFu));
    or_push(or_status(0u));
    g_i = 1u;
    g_pc = or_read16(0xFFFAu);
}

@@CASES@@

void openrecomp_run(void) {
    g_a = 0u; g_x = 0u; g_y = 0u; g_sp = 0xFDu;
    g_c = 0u; g_z = 0u; g_n = 0u; g_v = 0u; g_d = 0u; g_i = 0u;
    g_pc = (uint16_t)OR_ENTRY; g_steps = 0u; g_failed = 0; g_error = "";
    g_exit_requested = 0;
    while (!g_failed && !g_exit_requested && g_steps < (uint64_t)OR_MAX_STEPS) {
        if (or_rt_take_nmi()) { or_nmi_entry(); }
        or_step();
        g_steps++;
    }
    if (!g_failed && !g_exit_requested && g_steps >= (uint64_t)OR_MAX_STEPS) {
        or_fail("step limit exceeded");
    }
}

int openrecomp_failed(void) { return g_failed; }
const char *openrecomp_error(void) { return g_error; }
int openrecomp_exit_requested(void) { return g_exit_requested; }
uint64_t openrecomp_steps(void) { return g_steps; }
uint16_t openrecomp_pc(void) { return g_pc; }
uint8_t openrecomp_a(void) { return g_a; }
uint8_t openrecomp_x(void) { return g_x; }
uint8_t openrecomp_y(void) { return g_y; }
uint8_t openrecomp_sp(void) { return g_sp; }
uint8_t openrecomp_status(void) { return or_status(0u); }
"""


def _u8(value: int) -> str:
    return f"0x{value & 0xFF:02X}u"


def _address_of(mode: str, fields: dict[str, Any]) -> str | None:
    if mode == "zp":
        return f"or_addr_zp({_u8(fields['zp'])})"
    if mode == "zpx":
        return f"or_addr_zpx({_u8(fields['zp,x'])})"
    if mode == "zpy":
        return f"or_addr_zpy({_u8(fields['zp,y'])})"
    if mode == "abs":
        return f"(uint16_t)0x{fields['abs']:04X}u"
    if mode == "absx":
        return f"or_addr_absx((uint16_t)0x{fields['abs,x']:04X}u)"
    if mode == "absy":
        return f"or_addr_absy((uint16_t)0x{fields['abs,y']:04X}u)"
    if mode == "indx":
        return f"or_addr_indx({_u8(fields['indirect,x'])})"
    if mode == "indy":
        return f"or_addr_indy({_u8(fields['indirect,y'])})"
    return None


def _read_operand(mode: str, fields: dict[str, Any]) -> list[str]:
    if mode == "imm":
        return [f"uint8_t m = {_u8(fields['imm8'])};"]
    address = _address_of(mode, fields)
    if address is None:
        raise HostEmitError(f"unsupported read mode {mode!r}")
    return [f"uint16_t ea = {address};", "uint8_t m = or_read(ea);"]


def _store_operand(mode: str, fields: dict[str, Any], register: str) -> list[str]:
    address = _address_of(mode, fields)
    if address is None:
        raise HostEmitError(f"unsupported write mode {mode!r}")
    return [f"uint16_t ea = {address};", f"or_write(ea, {register});"]


def _rmw_operand(mode: str, fields: dict[str, Any]) -> list[str]:
    if mode == "acc":
        return ["uint8_t m = g_a;"]
    address = _address_of(mode, fields)
    if address is None:
        raise HostEmitError(f"unsupported RMW mode {mode!r}")
    return [f"uint16_t ea = {address};", "uint8_t m = or_read(ea);"]


def _rmw_store(mode: str) -> list[str]:
    if mode == "acc":
        return ["g_a = m;"]
    return ["or_write(ea, m);"]


_BRANCH_CONDITIONS = {
    "bpl": "g_n == 0u", "bmi": "g_n == 1u",
    "bvc": "g_v == 0u", "bvs": "g_v == 1u",
    "bcc": "g_c == 0u", "bcs": "g_c == 1u",
    "bne": "g_z == 0u", "beq": "g_z == 1u",
}

_FLAG_WRITES = {
    "clc": ("c", "0"), "sec": ("c", "1"),
    "cld": ("d", "0"), "sed": ("d", "1"),
    "cli": ("i", "0"), "sei": ("i", "1"),
    "clv": ("v", "0"),
}

_REGISTER_OPS = {
    "inx": ("g_x", "g_x", "+"), "iny": ("g_y", "g_y", "+"),
    "dex": ("g_x", "g_x", "-"), "dey": ("g_y", "g_y", "-"),
    "tax": ("g_x", "g_a", None), "tay": ("g_y", "g_a", None),
    "txa": ("g_a", "g_x", None), "tya": ("g_a", "g_y", None),
}


def body_for(instruction, mode: str, next_address: int, cost: int,
             exit_sites: dict[int, str]) -> list[str]:
    fields = dict((instruction.metadata or {}).get("adapter_fields", {}))
    op = instruction.op
    lines: list[str] = []
    if op in ("adc", "sbc", "and", "ora", "eor", "cmp", "cpx", "cpy"):
        lines += _read_operand(mode, fields)
        if op in ("cmp", "cpx", "cpy"):
            register = {"cmp": "g_a", "cpx": "g_x", "cpy": "g_y"}[op]
            lines.append(
                f"uint16_t diff = (uint16_t)((uint16_t){register} - (uint16_t)m);")
            lines.append(f"g_c = (uint8_t)({register} >= m);")
            lines.append("or_set_nz((uint8_t)diff);")
        elif op == "adc":
            lines.append("uint16_t sum = (uint16_t)((uint16_t)g_a + (uint16_t)m + (uint16_t)g_c);")
            lines.append("uint8_t result = (uint8_t)sum;")
            lines.append("g_v = (uint8_t)((((g_a ^ result) & (m ^ result)) >> 7u) & 1u);")
            lines.append("g_c = (uint8_t)((sum >> 8u) & 1u);")
            lines.append("g_a = result; or_set_nz(result);")
        elif op == "sbc":
            lines.append("uint16_t diff = (uint16_t)((uint16_t)g_a - (uint16_t)m - (uint16_t)(g_c ^ 1u));")
            lines.append("uint8_t result = (uint8_t)diff;")
            lines.append("g_v = (uint8_t)((((g_a ^ m) & (g_a ^ result)) >> 7u) & 1u);")
            lines.append("g_c = (uint8_t)((diff >> 8u) ? 0u : 1u);")
            lines.append("g_a = result; or_set_nz(result);")
        else:
            operation = {"and": "&", "ora": "|", "eor": "^"}[op]
            lines.append(f"g_a = (uint8_t)(g_a {operation} m); or_set_nz(g_a);")
    elif op in ("lda", "ldx", "ldy"):
        lines += _read_operand(mode, fields)
        register = {"lda": "g_a", "ldx": "g_x", "ldy": "g_y"}[op]
        lines.append(f"{register} = m; or_set_nz(m);")
    elif op == "bit":
        lines += _read_operand(mode, fields)
        lines.append("g_z = (uint8_t)((g_a & m) == 0u);")
        lines.append("g_n = (uint8_t)((m >> 7u) & 1u);")
        lines.append("g_v = (uint8_t)((m >> 6u) & 1u);")
    elif op in ("sta", "stx", "sty"):
        register = {"sta": "g_a", "stx": "g_x", "sty": "g_y"}[op]
        lines += _store_operand(mode, fields, register)
    elif op in ("asl", "lsr", "rol", "ror"):
        lines += _rmw_operand(mode, fields)
        if op == "asl":
            lines.append("g_c = (uint8_t)((m >> 7u) & 1u);")
            lines.append("m = (uint8_t)(m << 1u);")
            lines.append("or_set_nz(m);")
        elif op == "lsr":
            lines.append("g_c = (uint8_t)(m & 1u);")
            lines.append("m = (uint8_t)(m >> 1u);")
            lines.append("g_n = 0u; g_z = (uint8_t)(m == 0u);")
        elif op == "rol":
            lines.append("uint8_t carry_out = (uint8_t)((m >> 7u) & 1u);")
            lines.append("m = (uint8_t)((uint8_t)(m << 1u) | g_c);")
            lines.append("g_c = carry_out; or_set_nz(m);")
        else:
            lines.append("uint8_t carry_out = (uint8_t)(m & 1u);")
            lines.append("m = (uint8_t)((uint8_t)(m >> 1u) | (uint8_t)(g_c << 7u));")
            lines.append("g_c = carry_out; or_set_nz(m);")
        lines += _rmw_store(mode)
    elif op in ("inc", "dec"):
        lines += _rmw_operand(mode, fields)
        lines.append("m = (uint8_t)(m %s 1u);" % ("+" if op == "inc" else "-"))
        lines.append("or_set_nz(m);")
        lines += _rmw_store(mode)
    elif op in _REGISTER_OPS:
        target, source, adjustment = _REGISTER_OPS[op]
        if adjustment is None:
            lines.append(f"{target} = {source}; or_set_nz({target});")
        else:
            lines.append(f"{target} = (uint8_t)({source} {adjustment} 1u); or_set_nz({target});")
    elif op == "tsx":
        lines.append("g_x = g_sp; or_set_nz(g_x);")
    elif op == "txs":
        lines.append("g_sp = g_x;")
    elif op == "nop":
        pass
    elif op in _FLAG_WRITES:
        flag, value = _FLAG_WRITES[op]
        lines.append(f"g_{flag} = {value}u;")
    elif op == "pha":
        lines.append("or_push(g_a);")
    elif op == "php":
        lines.append("or_push(or_status(1u));")
    elif op == "pla":
        lines.append("g_a = or_pop(); or_set_nz(g_a);")
    elif op == "plp":
        lines.append("or_set_status(or_pop());")
    elif op == "jmp":
        if instruction.unresolved:
            if instruction.address not in exit_sites:
                raise HostEmitError(
                    f"unresolved indirect jump at 0x{instruction.address:04x} has no "
                    "declared service binding; fail closed")
            lines.append("const uint64_t exit_args[1] = { (uint64_t)g_pc };")
            lines.append("uint64_t exit_result = 0u;")
            lines.append(
                "if (or_rt_host_call((uint64_t)OR_RT_SERVICE_P5_EXIT, 1u, "
                "exit_args, &exit_result) != OR_RT_OK) {")
            lines.append("    or_fail(or_rt_failure_reason(OR_RT_HOST_SERVICE_FAILED));")
            lines.append("    return;")
            lines.append("}")
            lines.append("g_exit_requested = 1;")
            lines.append(f"or_rt_advance({cost}u);")
            lines.append("return;")
            return lines
        if mode == "ind":
            lines.append(f"g_pc = or_indirect((uint16_t)0x{fields['indirect']:04X}u);")
        else:
            lines.append(f"g_pc = (uint16_t)0x{fields['abs']:04X}u;")
        lines.append(f"or_rt_advance({cost}u);")
        return lines
    elif op == "jsr":
        target = fields["a16"]
        return_address = (instruction.address + 2) & 0xFFFF
        lines.append(f"or_push((uint8_t)((uint16_t)0x{return_address:04X}u >> 8u));")
        lines.append(f"or_push((uint8_t)((uint16_t)0x{return_address:04X}u & 0x00FFu));")
        lines.append(f"g_pc = (uint16_t)0x{target:04X}u;")
        lines.append(f"or_rt_advance({cost}u);")
        return lines
    elif op == "rts":
        lines.append("uint8_t rts_lo = or_pop();")
        lines.append("uint8_t rts_hi = or_pop();")
        lines.append("g_pc = (uint16_t)((uint16_t)(((uint16_t)rts_hi << 8) | rts_lo) + 1u);")
        lines.append(f"or_rt_advance({cost}u);")
        return lines
    elif op == "rti":
        lines.append("or_set_status(or_pop());")
        lines.append("uint8_t rti_lo = or_pop();")
        lines.append("uint8_t rti_hi = or_pop();")
        lines.append("g_pc = (uint16_t)(((uint16_t)rti_hi << 8) | rti_lo);")
        lines.append(f"or_rt_advance({cost}u);")
        return lines
    elif op == "brk":
        break_address = (instruction.address + 2) & 0xFFFF
        lines.append(f"or_push((uint8_t)((uint16_t)0x{break_address:04X}u >> 8u));")
        lines.append(f"or_push((uint8_t)((uint16_t)0x{break_address:04X}u & 0x00FFu));")
        lines.append("or_push(or_status(1u));")
        lines.append("g_i = 1u;")
        lines.append("g_pc = or_read16(0xFFFEu);")
        lines.append(f"or_rt_advance({cost}u);")
        return lines
    elif op in _BRANCH_CONDITIONS:
        condition = _BRANCH_CONDITIONS[op]
        lines.append(f"if ({condition}) {{ g_pc = (uint16_t)0x{fields['target']:04X}u; }}")
        lines.append(f"else {{ g_pc = (uint16_t)0x{next_address:04X}u; }}")
        lines.append(f"or_rt_advance({cost}u);")
        return lines
    else:
        raise HostEmitError(f"no semantics for {op!r} at 0x{instruction.address:04x}")
    lines.append(f"g_pc = (uint16_t)0x{next_address:04X}u;")
    lines.append(f"or_rt_advance({cost}u);")
    return lines


def emit_cases(instructions, exit_sites: dict[int, str]) -> str:
    lines: list[str] = ["static void or_step(void) {", "    switch (g_pc) {"]
    for instruction in instructions:
        fields = dict((instruction.metadata or {}).get("adapter_fields", {}))
        word = fields.get("word")
        entry = nes_adapter.OPCODES.get(word) if word is not None else None
        if entry is None:
            raise HostEmitError(f"undocumented opcode at 0x{instruction.address:04x}")
        _mnemonic, mode, _kind = entry
        cost = platform.INSTRUCTION_COST[word]
        next_address = (instruction.address + instruction.size_bytes) & 0xFFFF
        try:
            body = body_for(instruction, mode, next_address, cost, exit_sites)
        except HostEmitError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HostEmitError(
                f"emission failed closed at 0x{instruction.address:04x} "
                f"({instruction.op} {mode}): {exc}") from exc
        lines.append(f"    case 0x{instruction.address:04X}u: {{")
        for item in body:
            lines.append(f"        {item}")
        lines.append("        break;")
        lines.append("    }")
    lines.append("    default:")
    lines.append("        or_fail(\"pc outside the emitted image\");")
    lines.append("        break;")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines)


def emit_program(instructions, metadata: dict, exit_sites: dict[int, str],
                 max_steps: int = DEFAULT_MAX_STEPS) -> str:
    cases = emit_cases(instructions, exit_sites)
    region_start = metadata["cpu_origin"]
    region_end = max(
        instruction.address + instruction.size_bytes for instruction in instructions)
    return (PROGRAM_TEMPLATE
            .replace("@@ROM_SHA256@@", metadata["rom_sha256"])
            .replace("@@REGION_START@@", f"{region_start:04X}")
            .replace("@@REGION_END@@", f"{region_end:04X}")
            .replace("@@INSTRUCTION_COUNT@@", str(len(instructions)))
            .replace("@@EXIT_SERVICE_ID@@", str(EXIT_SERVICE_ID))
            .replace("@@MAX_STEPS@@", str(max_steps))
            .replace("@@ENTRY@@", f"{metadata['vectors']['reset']:04X}")
            .replace("@@CASES@@", cases))


__all__ = [
    "DEFAULT_MAX_STEPS",
    "EXIT_SERVICE_ID",
    "EXIT_SERVICE_NAME",
    "HostEmitError",
    "PROGRAM_TEMPLATE",
    "body_for",
    "emit_cases",
    "emit_program",
]
