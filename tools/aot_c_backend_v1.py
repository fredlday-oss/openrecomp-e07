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


def cstr(value: str) -> str:
    if any(ord(ch) > 0x7F for ch in value):
        raise AOTError("portable C backend requires ASCII IR identifiers")
    return json.dumps(value)


def u64(value: int) -> str:
    if not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise AOTError(f"value outside uint64 range: {value}")
    return f"UINT64_C({value})"


def mask_literal(bits: int) -> str:
    if bits == 64:
        return "UINT64_MAX"
    return u64((1 << bits) - 1)


def value_layout(function: dict[str, Any]) -> tuple[dict[str, int], dict[str, str]]:
    ordered: list[tuple[str, str]] = [(p["id"], p["type"]) for p in function["params"]]
    for block in function["blocks"]:
        for insn in block["instructions"]:
            if "result" in insn:
                ordered.append((insn["result"], insn["result_type"]))
    names = [name for name, _ in ordered]
    if len(names) != len(set(names)):
        raise AOTError(f"{function['id']}: duplicate SSA value")
    return ({name: i for i, (name, _) in enumerate(ordered)}, dict(ordered))


def op_expr(operand: dict[str, Any], slots: dict[str, int]) -> str:
    if "const" in operand:
        return u64(operand["const"])
    try:
        return f"v[{slots[operand['value']]}]"
    except KeyError as exc:
        raise AOTError(f"undefined value {operand.get('value')}") from exc


def op_type(operand: dict[str, Any], types: dict[str, str]) -> str:
    if "const" in operand:
        return operand["type"]
    try:
        return types[operand["value"]]
    except KeyError as exc:
        raise AOTError(f"undefined value type {operand.get('value')}") from exc


def scan_usage(ir: dict[str, Any]) -> dict[str, bool]:
    usage = {
        "load": False,
        "store": False,
        "signed": False,
        "unsigned_compare": False,
    }
    for function in ir["functions"]:
        for block in function["blocks"]:
            for insn in block["instructions"]:
                op = insn["op"]
                if op == "load":
                    usage["load"] = True
                    # or_load contains the sign-extension path even when a
                    # particular call is unsigned, so the helper must exist.
                    usage["signed"] = True
                elif op == "store":
                    usage["store"] = True
                elif op == "binop" and insn["kind"] == "ashr":
                    usage["signed"] = True
                elif op == "compare":
                    if insn["predicate"] in {"slt", "sle", "sgt", "sge"}:
                        usage["signed"] = True
                    else:
                        usage["unsigned_compare"] = True
                elif op == "cast" and insn["kind"] == "sext":
                    usage["signed"] = True
    return usage


def emit_insn(
    insn: dict[str, Any],
    slots: dict[str, int],
    types: dict[str, str],
    state_index: dict[str, int],
    fn_index: dict[str, int],
    serial: int,
) -> list[str]:
    op = insn["op"]
    lines = ["    if (!or_step()) return 0;"]
    result = insn.get("result")
    dst = None if result is None else f"v[{slots[result]}]"
    rbits = None if result is None else TYPE_BITS[insn["result_type"]]

    if op == "const":
        lines.append(f"    {dst} = {u64(insn['value'])} & or_mask({rbits});")
    elif op == "read_state":
        lines.append(f"    {dst} = g_state[{state_index[insn['slot']]}];")
    elif op == "write_state":
        idx = state_index[insn["slot"]]
        lines.append(f"    g_state[{idx}] = ({op_expr(insn['value'], slots)}) & g_state_masks[{idx}];")
    elif op == "binop":
        a = op_expr(insn["lhs"], slots)
        b = op_expr(insn["rhs"], slots)
        kind = insn["kind"]
        simple = {"add": "+", "sub": "-", "mul": "*", "and": "&", "or": "|", "xor": "^"}
        if kind in simple:
            expr = f"(({a}) {simple[kind]} ({b}))"
        elif kind in {"shl", "lshr", "ashr"}:
            lines.append(f"    if (({b}) >= {rbits}u) {{ or_fail(\"shift count is not normalized\"); return 0; }}")
            if kind == "shl":
                expr = f"(({a}) << ({b}))"
            elif kind == "lshr":
                expr = f"(({a}) >> ({b}))"
            else:
                expr = f"((uint64_t)(or_signed(({a}), {rbits}u) >> ({b})))"
        else:
            raise AOTError(f"unsupported binop {kind}")
        lines.append(f"    {dst} = ({expr}) & or_mask({rbits});")
    elif op == "compare":
        a = op_expr(insn["lhs"], slots)
        b = op_expr(insn["rhs"], slots)
        pred = insn["predicate"]
        unsigned_codes = {"eq": 0, "ne": 1, "ult": 2, "ule": 3, "ugt": 4, "uge": 5}
        if pred in unsigned_codes:
            expr = f"or_compare_unsigned(({a}), ({b}), {unsigned_codes[pred]}u)"
        elif pred in {"slt", "sle", "sgt", "sge"}:
            bits = TYPE_BITS[op_type(insn["lhs"], types)]
            cmpop = {"slt": "<", "sle": "<=", "sgt": ">", "sge": ">="}[pred]
            expr = f"(or_signed(({a}), {bits}u) {cmpop} or_signed(({b}), {bits}u))"
        else:
            raise AOTError(f"unsupported compare predicate {pred}")
        lines.append(f"    {dst} = ({expr}) ? UINT64_C(1) : UINT64_C(0);")
    elif op == "cast":
        value = op_expr(insn["value"], slots)
        kind = insn["kind"]
        if kind == "sext":
            sbits = TYPE_BITS[op_type(insn["value"], types)]
            expr = f"((uint64_t)or_signed(({value}), {sbits}u))"
        elif kind in {"zext", "trunc", "bitcast"}:
            expr = value
        else:
            raise AOTError(f"unsupported cast {kind}")
        lines.append(f"    {dst} = ({expr}) & or_mask({rbits});")
    elif op == "select":
        c = op_expr(insn["condition"], slots)
        y = op_expr(insn["if_true"], slots)
        n = op_expr(insn["if_false"], slots)
        lines.append(f"    {dst} = (({c}) ? ({y}) : ({n})) & or_mask({rbits});")
    elif op == "load":
        address = op_expr(insn["address"], slots)
        lines.append(
            f"    {dst} = or_load(({address}), {insn['width_bits']}u, {rbits}u, "
            f"{1 if insn['signed'] else 0}, {insn['alignment']}u, "
            f"{1 if insn['misaligned_policy'] == 'fault' else 0});"
        )
        lines.append("    if (g_failed) return 0;")
    elif op == "store":
        address = op_expr(insn["address"], slots)
        value = op_expr(insn["value"], slots)
        lines.append(
            f"    or_store(({address}), ({value}), {insn['width_bits']}u, {insn['alignment']}u, "
            f"{1 if insn['misaligned_policy'] == 'fault' else 0});"
        )
        lines.append("    if (g_failed) return 0;")
    elif op == "call":
        args = [op_expr(a, slots) for a in insn["args"]]
        name = f"call_args_{serial}"
        ptr = "NULL"
        if args:
            lines.append(f"    uint64_t {name}[{len(args)}] = {{{', '.join(args)}}};")
            ptr = name
        lines.append(f"    int call_has_{serial} = 0;")
        call = (
            f"or_fn_{fn_index[insn['callee']]}({ptr}, {len(args)}u, "
            f"&call_has_{serial}, depth + 1u)"
        )
        if dst is None:
            lines.append(f"    (void){call};")
        else:
            lines.append(f"    uint64_t call_ret_{serial} = {call};")
        lines.append("    if (g_failed) return 0;")
        if dst is not None:
            lines.append(f"    if (!call_has_{serial}) {{ or_fail(\"call returned void\"); return 0; }}")
            lines.append(f"    {dst} = call_ret_{serial} & or_mask({rbits});")
    elif op == "host_call":
        args = [op_expr(a, slots) for a in insn["args"]]
        name = f"host_args_{serial}"
        ptr = "NULL"
        if args:
            lines.append(f"    uint64_t {name}[{len(args)}] = {{{', '.join(args)}}};")
            ptr = name
        lines.append(f"    uint64_t host_ret_{serial} = 0;")
        lines.append(f"    int host_has_{serial} = 0;")
        lines.append(
            f"    if (!g_host_callback || !g_host_callback({cstr(insn['symbol'])}, {ptr}, {len(args)}u, "
            f"&host_ret_{serial}, &host_has_{serial})) {{ or_fail(\"host call failed\"); return 0; }}"
        )
        if dst is not None:
            lines.append(f"    if (!host_has_{serial}) {{ or_fail(\"host call returned void\"); return 0; }}")
            lines.append(f"    {dst} = host_ret_{serial} & or_mask({rbits});")
    else:
        raise AOTError(f"unsupported normalized operation {op}")
    return lines


def emit_function(
    function: dict[str, Any],
    number: int,
    state_index: dict[str, int],
    fn_index: dict[str, int],
    max_depth: int,
) -> list[str]:
    slots, types = value_layout(function)
    blocks = function["blocks"]
    block_index = {b["id"]: i for i, b in enumerate(blocks)}
    if len(block_index) != len(blocks):
        raise AOTError(f"{function['id']}: duplicate block id")
    guest_addresses = [b["guest_address"] for b in blocks]
    if len(guest_addresses) != len(set(guest_addresses)):
        raise AOTError(f"{function['id']}: duplicate block guest address")

    lines = [
        f"static uint64_t or_fn_{number}(const uint64_t *args, size_t argc, int *has_return, uint32_t depth) {{",
        f"    uint64_t v[{max(1, len(slots))}] = {{0}};",
        "    (void)v;",
        f"    if (depth > {max_depth}u) {{ or_fail(\"call-depth limit exceeded\"); return 0; }}",
        f"    if (argc != {len(function['params'])}u) {{ or_fail(\"argument count mismatch\"); return 0; }}",
        "    *has_return = 0;",
    ]
    if not function["params"]:
        lines.append("    (void)args;")
    for i, param in enumerate(function["params"]):
        lines.append(f"    v[{slots[param['id']]}] = args[{i}] & or_mask({TYPE_BITS[param['type']]}u);")
    lines.append(f"    goto or_f{number}_b0;")

    serial = 0
    for bnum, block in enumerate(blocks):
        lines.append(f"or_f{number}_b{bnum}:")
        for insn in block["instructions"]:
            lines.extend(emit_insn(insn, slots, types, state_index, fn_index, serial))
            serial += 1
        lines.append("    if (!or_step()) return 0;")
        term = block["terminator"]
        op = term["op"]
        if op == "jump":
            lines.append(f"    goto or_f{number}_b{block_index[term['target']]};")
        elif op == "branch":
            cond = op_expr(term["condition"], slots)
            lines.append(
                f"    if ({cond}) goto or_f{number}_b{block_index[term['target_true']]}; "
                f"else goto or_f{number}_b{block_index[term['target_false']]};"
            )
        elif op == "return":
            if "value" in term:
                value = op_expr(term["value"], slots)
                bits = TYPE_BITS[function["return_type"]]
                lines.append("    *has_return = 1;")
                lines.append(f"    return ({value}) & or_mask({bits}u);")
            else:
                lines.append("    return 0;")
        elif op == "indirect_jump":
            target = op_expr(term["target"], slots)
            lines.append(f"    switch ((uint64_t)({target})) {{")
            for candidate in term["candidate_blocks"]:
                target_block = blocks[block_index[candidate]]
                lines.append(
                    f"      case {u64(target_block['guest_address'])}: goto or_f{number}_b{block_index[candidate]};"
                )
            lines.append("      default: or_fail(\"indirect target outside candidate set\"); return 0;")
            lines.append("    }")
        elif op == "trap":
            lines.append(f"    or_fail({cstr(term['reason'])});")
            lines.append("    return 0;")
        else:
            raise AOTError(f"unsupported terminator {op}")
    lines.append("}")
    return lines


def generate(module: ModuleImage) -> str:
    ir = module.ir
    usage = scan_usage(ir)
    states = ir["state_slots"]
    state_index = {slot["id"]: i for i, slot in enumerate(states)}
    functions = ir["functions"]
    fn_index = {fn["id"]: i for i, fn in enumerate(functions)}
    if len(state_index) != len(states) or len(fn_index) != len(functions):
        raise AOTError("duplicate state/function identifier")

    entry = fn_index[module.entry_function]
    observed = state_index[module.observe_state_slot]
    big = 1 if ir["source"]["endianness"] == "big" else 0
    lines = [
        "/* Deterministic OpenRecomp normalized IR V1 -> portable C output. */",
        "#include <stdint.h>",
        "#include <stddef.h>",
        "#include <string.h>",
        "#include <limits.h>",
        "",
        "typedef int (*openrecomp_host_callback)(const char *, const uint64_t *, size_t, uint64_t *, int *);",
        "static openrecomp_host_callback g_host_callback = NULL;",
        f"static uint64_t g_state[{max(1, len(states))}];",
        f"static uint8_t g_memory[{max(1, module.memory_size_bytes)}];",
        "static uint64_t g_operations;",
        "static int g_failed;",
        "static const char *g_error;",
        "static uint64_t g_entry_return;",
        "static int g_entry_has_return;",
        f"static const uint64_t g_max_operations = {u64(module.limits.max_operations)};",
    ]
    if usage["load"] or usage["store"]:
        lines.append(f"static const int g_big_endian = {big};")
    lines.extend([
        "",
        "static uint64_t or_mask(unsigned bits) { return bits >= 64u ? UINT64_MAX : ((UINT64_C(1) << bits) - UINT64_C(1)); }",
    ])
    if usage["signed"]:
        lines.extend([
            "static int64_t or_signed(uint64_t value, unsigned bits) {",
            "    uint64_t mask = or_mask(bits); value &= mask;",
            "    if (bits >= 64u) return (int64_t)value;",
            "    uint64_t sign = UINT64_C(1) << (bits - 1u);",
            "    if (value & sign) value |= ~mask;",
            "    return (int64_t)value;",
            "}",
        ])
    if usage["unsigned_compare"]:
        lines.extend([
            "static int or_compare_unsigned(uint64_t a, uint64_t b, unsigned predicate) {",
            "    switch (predicate) {",
            "      case 0u: return a == b;",
            "      case 1u: return a != b;",
            "      case 2u: return a < b;",
            "      case 3u: return a <= b;",
            "      case 4u: return a > b;",
            "      case 5u: return a >= b;",
            "      default: return 0;",
            "    }",
            "}",
        ])
    lines.extend([
        "static void or_fail(const char *message) { if (!g_failed) g_error = message; g_failed = 1; }",
        "static int or_step(void) {",
        "    g_operations += UINT64_C(1);",
        "    if (g_operations > g_max_operations) { or_fail(\"operation limit exceeded\"); return 0; }",
        "    return 1;",
        "}",
    ])
    if usage["load"] or usage["store"]:
        lines.append(
            f"static int or_bounds(uint64_t a, size_t n) {{ const uint64_t total = {u64(module.memory_size_bytes)}; if (a > total || (uint64_t)n > total - a) {{ or_fail(\"deterministic memory fault\"); return 0; }} return 1; }}"
        )
    if usage["load"]:
        lines.extend([
            "static uint64_t or_load(uint64_t a, unsigned width, unsigned result_bits, int is_signed, unsigned alignment, int fault_misaligned) {",
            "    size_t n = width / 8u;",
            "    if (fault_misaligned && alignment > 1u && (a % alignment)) { or_fail(\"deterministic misalignment fault\"); return 0; }",
            "    if (!or_bounds(a, n)) return 0;",
            "    uint64_t value = 0;",
            "    for (size_t i = 0; i < n; ++i) { size_t p = g_big_endian ? i : (n - 1u - i); value = (value << 8u) | g_memory[a + p]; }",
            "    if (is_signed && width < result_bits) value = (uint64_t)or_signed(value, width);",
            "    return value & or_mask(result_bits);",
            "}",
        ])
    if usage["store"]:
        lines.extend([
            "static void or_store(uint64_t a, uint64_t value, unsigned width, unsigned alignment, int fault_misaligned) {",
            "    size_t n = width / 8u;",
            "    if (fault_misaligned && alignment > 1u && (a % alignment)) { or_fail(\"deterministic misalignment fault\"); return; }",
            "    if (!or_bounds(a, n)) return;",
            "    for (size_t i = 0; i < n; ++i) { size_t s = g_big_endian ? (n - 1u - i) : i; g_memory[a + i] = (uint8_t)((value >> (s * 8u)) & UINT64_C(0xff)); }",
            "}",
        ])

    masks = [mask_literal(TYPE_BITS[s["type"]]) for s in states] or ["UINT64_MAX"]
    names = [cstr(s["id"]) for s in states] or [cstr("")]
    lines.append(f"static const uint64_t g_state_masks[{max(1, len(states))}] = {{{', '.join(masks)}}};")
    lines.append(f"static const char *g_state_names[{max(1, len(states))}] = {{{', '.join(names)}}};")

    for i, segment in enumerate(module.memory_segments):
        if segment.data:
            data = ", ".join(f"0x{b:02x}" for b in segment.data)
            lines.append(f"static const uint8_t g_segment_{i}[{len(segment.data)}] = {{{data}}};")

    for i in range(len(functions)):
        lines.append(f"static uint64_t or_fn_{i}(const uint64_t *, size_t, int *, uint32_t);")
    for i, function in enumerate(functions):
        lines.extend(emit_function(function, i, state_index, fn_index, module.limits.max_call_depth))

    lines.extend([
        "void openrecomp_set_host_callback(openrecomp_host_callback callback) { g_host_callback = callback; }",
        "static void or_reset(void) {",
        "    memset(g_state, 0, sizeof(g_state)); memset(g_memory, 0, sizeof(g_memory));",
        "    g_operations = 0; g_failed = 0; g_error = \"\"; g_entry_return = 0; g_entry_has_return = 0;",
    ])
    for slot, value in sorted(module.initial_state.items()):
        idx = state_index[slot]
        lines.append(f"    g_state[{idx}] = {u64(value)} & g_state_masks[{idx}];")
    for i, segment in enumerate(module.memory_segments):
        if segment.data:
            lines.append(f"    memcpy(g_memory + {segment.guest_address}u, g_segment_{i}, {len(segment.data)}u);")
    lines.extend([
        "}",
        "int openrecomp_run(void) {",
        "    or_reset();",
        f"    g_entry_return = or_fn_{entry}(NULL, 0u, &g_entry_has_return, 0u);",
        "    return g_failed ? 0 : 1;",
        "}",
        f"uint64_t openrecomp_observed_state(void) {{ return g_state[{observed}]; }}",
        "uint64_t openrecomp_function_return(void) { return g_entry_return; }",
        "int openrecomp_function_has_return(void) { return g_entry_has_return; }",
        "uint64_t openrecomp_operations(void) { return g_operations; }",
        "const char *openrecomp_error(void) { return g_error; }",
        f"size_t openrecomp_state_count(void) {{ return {len(states)}u; }}",
        f"const char *openrecomp_state_name(size_t i) {{ return i < {len(states)}u ? g_state_names[i] : NULL; }}",
        f"uint64_t openrecomp_state_value(size_t i) {{ return i < {len(states)}u ? g_state[i] : UINT64_C(0); }}",
        f"size_t openrecomp_memory_size(void) {{ return {module.memory_size_bytes}u; }}",
        "int openrecomp_memory_read(uint64_t a, size_t n, uint8_t *out) {",
        f"    const uint64_t total = {u64(module.memory_size_bytes)};",
        "    if (!out || a > total || (uint64_t)n > total - a) return 0;",
        "    memcpy(out, g_memory + a, n); return 1;",
        "}",
        "",
    ])
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: aot_c_backend_v1.py <module.json> <ir.json> <host-contract.json> <out.c>", file=sys.stderr)
        return 2
    try:
        module = ModuleImage.from_files(argv[1], argv[2], argv[3])
        Path(argv[4]).write_text(generate(module), encoding="utf-8", newline="\n")
    except (OSError, KeyError, ValueError, AOTError) as exc:
        print(f"OPENRECOMP_IR_V1_AOT_TRANSLATE=FAIL: {exc}", file=sys.stderr)
        return 2
    print("OPENRECOMP_IR_V1_AOT_TRANSLATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
