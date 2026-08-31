#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openrecomp import ModuleImage
from openrecomp.runtime import TYPE_BITS


class AOTError(ValueError):
    pass


def c_string(value: str) -> str:
    if any(ord(ch) > 0x7F for ch in value):
        raise AOTError("AOT V1 C backend requires ASCII identifiers/symbols")
    return json.dumps(value)


def u64(value: int) -> str:
    if value < 0 or value > 0xFFFFFFFFFFFFFFFF:
        raise AOTError(f"integer is outside uint64 range: {value}")
    return f"UINT64_C({value})"


def operand_expr(operand: dict[str, Any], values: dict[str, int]) -> str:
    if "const" in operand:
        return u64(operand["const"])
    try:
        return f"v[{values[operand['value']]}]"
    except KeyError as exc:
        raise AOTError(f"undefined normalized value {operand.get('value')}") from exc


def result_slots(function: dict[str, Any]) -> dict[str, int]:
    names: list[str] = [param["id"] for param in function["params"]]
    for block in function["blocks"]:
        for insn in block["instructions"]:
            if "result" in insn:
                names.append(insn["result"])
    if len(names) != len(set(names)):
        raise AOTError(f"{function['id']}: duplicate value id reached AOT backend")
    return {name: index for index, name in enumerate(names)}


def emit_instruction(
    insn: dict[str, Any],
    values: dict[str, int],
    state_index: dict[str, int],
    function_index: dict[str, int],
    serial: int,
) -> list[str]:
    op = insn["op"]
    out = ["    if (!or_step()) return 0;"]
    result = insn.get("result")
    target = f"v[{values[result]}]" if result is not None else None
    bits = TYPE_BITS.get(insn.get("result_type", ""))

    if op == "const":
        out.append(f"    {target} = {u64(insn['value'])} & or_mask({bits});")

    elif op == "read_state":
        out.append(f"    {target} = g_state[{state_index[insn['slot']]}] & or_mask({bits});")

    elif op == "write_state":
        slot = state_index[insn["slot"]]
        slot_bits = TYPE_BITS[insn["value"].get("type", "i64")] if "const" in insn["value"] else None
        if slot_bits is None:
            # The semantic validator already proves the operand matches the slot type.
            slot_bits = 64
        expr = operand_expr(insn["value"], values)
        out.append(f"    g_state[{slot}] = ({expr}) & g_state_masks[{slot}];")

    elif op == "binop":
        lhs = operand_expr(insn["lhs"], values)
        rhs = operand_expr(insn["rhs"], values)
        kind = insn["kind"]
        if kind == "add":
            expr = f"(({lhs}) + ({rhs}))"
        elif kind == "sub":
            expr = f"(({lhs}) - ({rhs}))"
        elif kind == "mul":
            expr = f"(({lhs}) * ({rhs}))"
        elif kind == "and":
            expr = f"(({lhs}) & ({rhs}))"
        elif kind == "or":
            expr = f"(({lhs}) | ({rhs}))"
        elif kind == "xor":
            expr = f"(({lhs}) ^ ({rhs}))"
        elif kind in {"shl", "lshr", "ashr"}:
            out.append(f"    if (({rhs}) >= {bits}) {{ or_fail(\"shift count is not normalized\"); return 0; }}")
            if kind == "shl":
                expr = f"(({lhs}) << ({rhs}))"
            elif kind == "lshr":
                expr = f"(({lhs}) >> ({rhs}))"
            else:
                expr = f"((uint64_t)(or_signed(({lhs}), {bits}) >> ({rhs})))"
        else:
            raise AOTError(f"unsupported normalized binop {kind}")
        out.append(f"    {target} = ({expr}) & or_mask({bits});")

    elif op == "compare":
        lhs = operand_expr(insn["lhs"], values)
        rhs = operand_expr(insn["rhs"], values)
        predicate = insn["predicate"]
        if predicate == "eq":
            expr = f"(({lhs}) == ({rhs}))"
        elif predicate == "ne":
            expr = f"(({lhs}) != ({rhs}))"
        elif predicate == "ult":
            expr = f"(({lhs}) < ({rhs}))"
        elif predicate == "ule":
            expr = f"(({lhs}) <= ({rhs}))"
        elif predicate == "ugt":
            expr = f"(({lhs}) > ({rhs}))"
        elif predicate == "uge":
            expr = f"(({lhs}) >= ({rhs}))"
        elif predicate in {"slt", "sle", "sgt", "sge"}:
            # The validator proves both operands have the same type. Determine width
            # from an explicit constant type when available, otherwise use the result
            # producer map emitted below through or_value_bits().
            lhs_bits = TYPE_BITS.get(insn["lhs"].get("type", ""), 0)
            if lhs_bits == 0:
                lhs_bits = 32 if insn.get("source_address") is not None else 64
            cmpop = {"slt": "<", "sle": "<=", "sgt": ">", "sge": ">="}[predicate]
            expr = f"(or_signed(({lhs}), {lhs_bits}) {cmpop} or_signed(({rhs}), {lhs_bits}))"
        else:
            raise AOTError(f"unsupported normalized predicate {predicate}")
        out.append(f"    {target} = ({expr}) ? UINT64_C(1) : UINT64_C(0);")

    elif op == "cast":
        value = operand_expr(insn["value"], values)
        source_bits = TYPE_BITS.get(insn["value"].get("type", ""), 0)
        kind = insn["kind"]
        if kind == "sext":
            if source_bits == 0:
                raise AOTError("sext source must expose a constant type to the portable C backend")
            expr = f"((uint64_t)or_signed(({value}), {source_bits}))"
        else:
            expr = value
        out.append(f"    {target} = ({expr}) & or_mask({bits});")

    elif op == "select":
        cond = operand_expr(insn["condition"], values)
        yes = operand_expr(insn["if_true"], values)
        no = operand_expr(insn["if_false"], values)
        out.append(f"    {target} = (({cond}) ? ({yes}) : ({no})) & or_mask({bits});")

    elif op == "load":
        addr = operand_expr(insn["address"], values)
        out.append(
            f"    {target} = or_load(({addr}), {insn['width_bits']}, {bits}, "
            f"{1 if insn['signed'] else 0}, {insn['alignment']}, "
            f"{1 if insn['misaligned_policy'] == 'fault' else 0});"
        )
        out.append("    if (g_failed) return 0;")

    elif op == "store":
        addr = operand_expr(insn["address"], values)
        value = operand_expr(insn["value"], values)
        out.append(
            f"    or_store(({addr}), ({value}), {insn['width_bits']}, {insn['alignment']}, "
            f"{1 if insn['misaligned_policy'] == 'fault' else 0});"
        )
        out.append("    if (g_failed) return 0;")

    elif op == "call":
        args = [operand_expr(arg, values) for arg in insn["args"]]
        arr = f"call_args_{serial}"
        if args:
            out.append(f"    uint64_t {arr}[{len(args)}] = {{{', '.join(args)}}};")
            ptr = arr
        else:
            ptr = "NULL"
        out.append(f"    int call_has_{serial} = 0;")
        out.append(
            f"    uint64_t call_ret_{serial} = or_fn_{function_index[insn['callee']]}"
            f"({ptr}, {len(args)}, &call_has_{serial}, depth + 1);"
        )
        out.append("    if (g_failed) return 0;")
        if result is not None:
            out.append(f"    if (!call_has_{serial}) {{ or_fail(\"non-void call produced no value\"); return 0; }}")
            out.append(f"    {target} = call_ret_{serial} & or_mask({bits});")

    elif op == "host_call":
        args = [operand_expr(arg, values) for arg in insn["args"]]
        arr = f"host_args_{serial}"
        if args:
            out.append(f"    uint64_t {arr}[{len(args)}] = {{{', '.join(args)}}};")
            ptr = arr
        else:
            ptr = "NULL"
        out.append(f"    uint64_t host_ret_{serial} = 0;")
        out.append(f"    int host_has_{serial} = 0;")
        out.append(
            f"    if (!g_host_callback || !g_host_callback({c_string(insn['symbol'])}, {ptr}, {len(args)}, "
            f"&host_ret_{serial}, &host_has_{serial})) {{ or_fail(\"host call failed\"); return 0; }}"
        )
        if result is not None:
            out.append(f"    if (!host_has_{serial}) {{ or_fail(\"host call produced no value\"); return 0; }}")
            out.append(f"    {target} = host_ret_{serial} & or_mask({bits});")

    else:
        raise AOTError(f"unsupported normalized IR operation {op}")

    return out


def emit_function(
    function: dict[str, Any],
    function_number: int,
    function_index: dict[str, int],
    state_index: dict[str, int],
    ir: dict[str, Any],
    max_depth: int,
) -> list[str]:
    values = result_slots(function)
    storage = max(1, len(values))
    blocks = function["blocks"]
    block_index = {block["id"]: i for i, block in enumerate(blocks)}
    guest_to_block: dict[int, str] = {}
    for block in blocks:
        addr = block["guest_address"]
        if addr in guest_to_block:
            raise AOTError(f"{function['id']}: duplicate block guest address 0x{addr:x}")
        guest_to_block[addr] = block["id"]

    lines = [
        f"static uint64_t or_fn_{function_number}(const uint64_t *args, size_t argc, int *has_return, uint32_t depth) {{",
        f"    uint64_t v[{storage}] = {{0}};",
        f"    if (depth > {max_depth}u) {{ or_fail(\"call-depth limit exceeded\"); return 0; }}",
        f"    if (argc != {len(function['params'])}u) {{ or_fail(\"argument count mismatch\"); return 0; }}",
        "    *has_return = 0;",
    ]
    for i, param in enumerate(function["params"]):
        lines.append(f"    v[{values[param['id']]}] = args[{i}] & or_mask({TYPE_BITS[param['type']]});")
    lines.append(f"    goto or_f{function_number}_b0;")

    serial = 0
    for bnum, block in enumerate(blocks):
        lines.append(f"or_f{function_number}_b{bnum}:")
        for insn in block["instructions"]:
            lines.extend(emit_instruction(insn, values, state_index, function_index, serial))
            serial += 1
        lines.append("    if (!or_step()) return 0;")
        term = block["terminator"]
        op = term["op"]
        if op == "jump":
            lines.append(f"    goto or_f{function_number}_b{block_index[term['target']]};")
        elif op == "branch":
            cond = operand_expr(term["condition"], values)
            lines.append(
                f"    if ({cond}) goto or_f{function_number}_b{block_index[term['target_true']]}; "
                f"else goto or_f{function_number}_b{block_index[term['target_false']]};"
            )
        elif op == "return":
            if "value" in term:
                value = operand_expr(term["value"], values)
                rbits = TYPE_BITS[function["return_type"]]
                lines.append("    *has_return = 1;")
                lines.append(f"    return ({value}) & or_mask({rbits});")
            else:
                lines.append("    *has_return = 0;")
                lines.append("    return 0;")
        elif op == "indirect_jump":
            target = operand_expr(term["target"], values)
            lines.append(f"    switch ((uint64_t)({target})) {{")
            for candidate in term["candidate_blocks"]:
                block = blocks[block_index[candidate]]
                lines.append(f"      case {u64(block['guest_address'])}: goto or_f{function_number}_b{block_index[candidate]};")
            lines.append("      default: or_fail(\"indirect target is outside candidate set\"); return 0;")
            lines.append("    }")
        elif op == "trap":
            lines.append(f"    or_fail({c_string(term['reason'])});")
            lines.append("    return 0;")
        else:
            raise AOTError(f"unsupported normalized terminator {op}")

    lines.append("}")
    return lines


def generate(module: ModuleImage) -> str:
    ir = module.ir
    state_slots = ir["state_slots"]
    state_index = {slot["id"]: i for i, slot in enumerate(state_slots)}
    if len(state_index) != len(state_slots):
        raise AOTError("duplicate state slot reached AOT backend")

    functions = ir["functions"]
    function_index = {function["id"]: i for i, function in enumerate(functions)}
    if len(function_index) != len(functions):
        raise AOTError("duplicate function reached AOT backend")

    entry_index = function_index[module.entry_function]
    observe_index = state_index[module.observe_state_slot]
    state_storage = max(1, len(state_slots))
    memory_storage = max(1, module.memory_size_bytes)
    big_endian = 1 if ir["source"]["endianness"] == "big" else 0

    lines: list[str] = [
        "/* Generated deterministically by OpenRecomp IR V1 portable C AOT backend. */",
        "#include <stdint.h>",
        "#include <stddef.h>",
        "#include <string.h>",
        "#include <limits.h>",
        "",
        "typedef int (*openrecomp_host_callback)(const char *, const uint64_t *, size_t, uint64_t *, int *);",
        "static openrecomp_host_callback g_host_callback = NULL;",
        f"static uint64_t g_state[{state_storage}];",
        f"static uint8_t g_memory[{memory_storage}];",
        "static uint64_t g_operations = 0;",
        "static int g_failed = 0;",
        "static const char *g_error = \"\";",
        "static uint64_t g_entry_return = 0;",
        "static int g_entry_has_return = 0;",
        f"static const uint64_t g_max_operations = {u64(module.limits.max_operations)};",
        f"static const int g_big_endian = {big_endian};",
        "",
        "static uint64_t or_mask(unsigned bits) {",
        "    return bits >= 64 ? UINT64_MAX : ((UINT64_C(1) << bits) - UINT64_C(1));",
        "}",
        "static int64_t or_signed(uint64_t value, unsigned bits) {",
        "    uint64_t mask = or_mask(bits);",
        "    value &= mask;",
        "    if (bits >= 64) return (int64_t)value;",
        "    uint64_t sign = UINT64_C(1) << (bits - 1);",
        "    if (value & sign) value |= ~mask;",
        "    return (int64_t)value;",
        "}",
        "static void or_fail(const char *message) {",
        "    if (!g_failed) g_error = message;",
        "    g_failed = 1;",
        "}",
        "static int or_step(void) {",
        "    g_operations += UINT64_C(1);",
        "    if (g_operations > g_max_operations) { or_fail(\"operation limit exceeded\"); return 0; }",
        "    return 1;",
        "}",
        "static int or_bounds(uint64_t address, size_t size) {",
        f"    const uint64_t total = {u64(module.memory_size_bytes)};",
        "    if (address > total || (uint64_t)size > total - address) { or_fail(\"deterministic memory fault\"); return 0; }",
        "    return 1;",
        "}",
        "static uint64_t or_load(uint64_t address, unsigned width_bits, unsigned result_bits, int is_signed, unsigned alignment, int fault_misaligned) {",
        "    size_t size = width_bits / 8u;",
        "    if (fault_misaligned && alignment > 1u && (address % alignment) != 0u) { or_fail(\"deterministic misalignment fault\"); return 0; }",
        "    if (!or_bounds(address, size)) return 0;",
        "    uint64_t value = 0;",
        "    for (size_t i = 0; i < size; ++i) {",
        "        size_t index = g_big_endian ? i : (size - 1u - i);",
        "        value = (value << 8u) | g_memory[address + index];",
        "    }",
        "    if (is_signed && width_bits < result_bits) value = (uint64_t)or_signed(value, width_bits);",
        "    return value & or_mask(result_bits);",
        "}",
        "static void or_store(uint64_t address, uint64_t value, unsigned width_bits, unsigned alignment, int fault_misaligned) {",
        "    size_t size = width_bits / 8u;",
        "    if (fault_misaligned && alignment > 1u && (address % alignment) != 0u) { or_fail(\"deterministic misalignment fault\"); return; }",
        "    if (!or_bounds(address, size)) return;",
        "    for (size_t i = 0; i < size; ++i) {",
        "        size_t shift_index = g_big_endian ? (size - 1u - i) : i;",
        "        g_memory[address + i] = (uint8_t)((value >> (shift_index * 8u)) & UINT64_C(0xff));",
        "    }",
        "}",
        "",
    ]

    masks = [f"or_mask({TYPE_BITS[slot['type']]})" for slot in state_slots]
    if masks:
        lines.append(f"static const uint64_t g_state_masks[{len(masks)}] = {{{', '.join(masks)}}};")
    else:
        lines.append("static const uint64_t g_state_masks[1] = {UINT64_MAX};")
    names = [c_string(slot["id"]) for slot in state_slots]
    if names:
        lines.append(f"static const char *g_state_names[{len(names)}] = {{{', '.join(names)}}};")
    else:
        lines.append("static const char *g_state_names[1] = {\"\"};")

    for seg_index, segment in enumerate(module.memory_segments):
        data = ", ".join(f"0x{byte:02x}" for byte in segment.data)
        storage = max(1, len(segment.data))
        if data:
            lines.append(f"static const uint8_t g_segment_{seg_index}[{storage}] = {{{data}}};")
        else:
            lines.append(f"static const uint8_t g_segment_{seg_index}[1] = {{0}};")

    lines.append("")
    for i in range(len(functions)):
        lines.append(f"static uint64_t or_fn_{i}(const uint64_t *, size_t, int *, uint32_t);")
    lines.append("")

    for i, function in enumerate(functions):
        lines.extend(emit_function(function, i, function_index, state_index, ir, module.limits.max_call_depth))
        lines.append("")

    lines.extend([
        "void openrecomp_set_host_callback(openrecomp_host_callback callback) { g_host_callback = callback; }",
        "",
        "static void or_reset(void) {",
        "    memset(g_state, 0, sizeof(g_state));",
        "    memset(g_memory, 0, sizeof(g_memory));",
        "    g_operations = 0; g_failed = 0; g_error = \"\"; g_entry_return = 0; g_entry_has_return = 0;",
    ])
    for slot, value in sorted(module.initial_state.items()):
        lines.append(f"    g_state[{state_index[slot]}] = {u64(value)} & g_state_masks[{state_index[slot]}];")
    for seg_index, segment in enumerate(module.memory_segments):
        if segment.data:
            lines.append(
                f"    memcpy(g_memory + {u64(segment.guest_address)}, g_segment_{seg_index}, {len(segment.data)}u);"
            )
    lines.extend([
        "}",
        "",
        "int openrecomp_run(void) {",
        "    or_reset();",
        f"    g_entry_return = or_fn_{entry_index}(NULL, 0u, &g_entry_has_return, 0u);",
        "    return g_failed ? 0 : 1;",
        "}",
        f"uint64_t openrecomp_observed_state(void) {{ return g_state[{observe_index}]; }}",
        "uint64_t openrecomp_function_return(void) { return g_entry_return; }",
        "int openrecomp_function_has_return(void) { return g_entry_has_return; }",
        "uint64_t openrecomp_operations(void) { return g_operations; }",
        "const char *openrecomp_error(void) { return g_error; }",
        f"size_t openrecomp_state_count(void) {{ return {len(state_slots)}u; }}",
        "const char *openrecomp_state_name(size_t index) {",
        f"    return index < {len(state_slots)}u ? g_state_names[index] : NULL;",
        "}",
        "uint64_t openrecomp_state_value(size_t index) {",
        f"    return index < {len(state_slots)}u ? g_state[index] : UINT64_C(0);",
        "}",
        f"size_t openrecomp_memory_size(void) {{ return {module.memory_size_bytes}u; }}",
        "int openrecomp_memory_read(uint64_t address, size_t size, uint8_t *out) {",
        f"    const uint64_t total = {u64(module.memory_size_bytes)};",
        "    if (!out || address > total || (uint64_t)size > total - address) return 0;",
        "    memcpy(out, g_memory + address, size);",
        "    return 1;",
        "}",
        "",
    ])
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "usage: aot_translate_ir_v1_c.py <module-v1.json> <ir-v1.json> <host-contract.json> <out.c>",
            file=sys.stderr,
        )
        return 2
    try:
        module = ModuleImage.from_files(argv[1], argv[2], argv[3])
        source = generate(module)
        Path(argv[4]).write_text(source, encoding="utf-8", newline="\n")
    except (OSError, KeyError, ValueError, AOTError) as exc:
        print(f"OPENRECOMP_IR_V1_AOT_TRANSLATE=FAIL: {exc}", file=sys.stderr)
        return 2
    print("OPENRECOMP_IR_V1_AOT_TRANSLATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
