#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openrecomp.divrem_v1 import divrem_result
from tools.ir_v1_1_contract import validate_document_v1_1
from tools.validate_ir_v1 import validate_document as validate_v1


def minimal(kind: str = "udiv") -> dict:
    return {
        "ir_version": "1.1.0", "module_id": "divrem.unit",
        "source": {"architecture": "unit", "adapter": "unit", "address_bits": 32, "endianness": "little", "input_sha256": "0" * 64},
        "required_features": ["core-v1", "integer-divrem-v1"], "host_contract_version": "0.1.1", "required_host_symbols": [],
        "state_slots": [{"id": "result", "type": "i32"}], "entry_function": "main",
        "functions": [{"id": "main", "guest_address": 0, "params": [], "return_type": None, "blocks": [{"id": "entry", "guest_address": 0, "instructions": [{"op": "binop", "result": "%q", "result_type": "i32", "kind": kind, "lhs": {"const": 37, "type": "i32"}, "rhs": {"const": 5, "type": "i32"}}, {"op": "write_state", "slot": "result", "value": {"value": "%q"}}], "terminator": {"op": "return"}}]}],
    }


def expect_reject(fn) -> None:
    try: fn()
    except Exception: return
    raise AssertionError("invalid input was accepted")


def main() -> None:
    assert divrem_result("udiv", 37, 5, 32) == 7
    assert divrem_result("urem", 37, 5, 32) == 2
    assert divrem_result("sdiv", (-37) & 0xFFFFFFFF, 5, 32) == ((-7) & 0xFFFFFFFF)
    assert divrem_result("srem", (-37) & 0xFFFFFFFF, 5, 32) == ((-2) & 0xFFFFFFFF)
    assert divrem_result("udiv", 123, 0, 32) == 0xFFFFFFFF
    assert divrem_result("urem", 123, 0, 32) == 123
    assert divrem_result("sdiv", 0xFFFFFF85, 0, 32) == 0xFFFFFFFF
    assert divrem_result("srem", 0xFFFFFF85, 0, 32) == 0xFFFFFF85
    assert divrem_result("sdiv", 0x80000000, 0xFFFFFFFF, 32) == 0x80000000
    assert divrem_result("srem", 0x80000000, 0xFFFFFFFF, 32) == 0
    print("OPENRECOMP_IR_V1_1_DIVREM_EDGE_SEMANTICS=PASS tests=10")
    for kind in ("udiv", "urem", "sdiv", "srem"): validate_document_v1_1(minimal(kind))
    print("OPENRECOMP_IR_V1_1_DIVREM_SCHEMA=PASS kinds=4")
    missing_feature = minimal(); missing_feature["required_features"] = ["core-v1"]
    expect_reject(lambda: validate_document_v1_1(missing_feature))
    old_version = minimal(); old_version["ir_version"] = "1.0.0"
    expect_reject(lambda: validate_document_v1_1(old_version))
    expect_reject(lambda: validate_v1(minimal()))
    print("OPENRECOMP_IR_V1_1_DIVREM_FAIL_CLOSED=PASS tests=3")


if __name__ == "__main__":
    main()
