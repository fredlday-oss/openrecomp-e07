#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.aot_c_backend_v1 as base
from openrecomp.divrem_v1 import DIVREM_KINDS
from openrecomp.module_v1_1 import load_module_v1_1

_BASE_EMIT = base.emit_insn
_BASE_SCAN = base.scan_usage


def scan_usage_v1_1(ir: dict[str, Any]) -> dict[str, bool]:
    usage = _BASE_SCAN(ir)
    for function in ir["functions"]:
        for block in function["blocks"]:
            for insn in block["instructions"]:
                if insn.get("op") == "binop" and insn.get("kind") in DIVREM_KINDS:
                    usage["signed"] = True
    return usage


def emit_insn_v1_1(insn, slots, types, state_index, fn_index, serial):
    if insn.get("op") != "binop" or insn.get("kind") not in DIVREM_KINDS:
        return _BASE_EMIT(insn, slots, types, state_index, fn_index, serial)
    result = f"v[{slots[insn['result']]}]"
    bits = base.TYPE_BITS[insn["result_type"]]
    lhs = base.op_expr(insn["lhs"], slots); rhs = base.op_expr(insn["rhs"], slots)
    mode = {"udiv": 0, "urem": 1, "sdiv": 2, "srem": 3}[insn["kind"]]
    return ["    if (!or_step()) return 0;", f"    {result} = or_divrem(({lhs}), ({rhs}), {bits}u, {mode}u) & or_mask({bits});"]


DIVREM_C_HELPER = r'''static uint64_t or_divrem(uint64_t lhs, uint64_t rhs, unsigned bits, unsigned mode) {
    uint64_t mask = or_mask(bits);
    uint64_t sign;
    int64_t a;
    int64_t b;
    lhs &= mask;
    rhs &= mask;
    if (rhs == UINT64_C(0)) return (mode == 0u || mode == 2u) ? mask : lhs;
    if (mode == 0u) return (lhs / rhs) & mask;
    if (mode == 1u) return (lhs % rhs) & mask;
    sign = UINT64_C(1) << (bits - 1u);
    if (lhs == sign && rhs == mask) return mode == 2u ? sign : UINT64_C(0);
    a = or_signed(lhs, bits);
    b = or_signed(rhs, bits);
    if (mode == 2u) return ((uint64_t)(a / b)) & mask;
    return ((uint64_t)(a % b)) & mask;
}'''


def generate_v1_1(module) -> str:
    old_emit = base.emit_insn; old_scan = base.scan_usage
    base.emit_insn = emit_insn_v1_1; base.scan_usage = scan_usage_v1_1
    try:
        text = base.generate(module)
    finally:
        base.emit_insn = old_emit; base.scan_usage = old_scan
    anchor = "static void or_fail(const char *message)"
    if anchor not in text:
        raise base.AOTError("portable C helper insertion anchor missing")
    return text.replace(anchor, DIVREM_C_HELPER + "\n" + anchor, 1)


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: aot_c_backend_v1_1.py <module.json> <ir.json> <host-contract.json> <out.c>", file=sys.stderr); return 2
    try:
        module = load_module_v1_1(argv[1], argv[2], argv[3])
        Path(argv[4]).write_text(generate_v1_1(module), encoding="utf-8", newline="\n")
    except (OSError, KeyError, ValueError, base.AOTError) as exc:
        print(f"OPENRECOMP_IR_V1_1_AOT_TRANSLATE=FAIL: {exc}", file=sys.stderr); return 2
    print("OPENRECOMP_IR_V1_1_AOT_TRANSLATE=PASS"); return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
