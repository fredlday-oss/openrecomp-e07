#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema

from validate_ir_v1 import IRSemanticError, validate_document

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ir-v1" / "minimal.json"


def expect_reject(name: str, document: dict) -> None:
    try:
        validate_document(document)
    except (IRSemanticError, jsonschema.ValidationError):
        print(f"PASS reject: {name}")
        return
    raise AssertionError(f"expected rejection: {name}")


def main() -> None:
    base = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    validate_document(base)
    print("PASS accept: minimal-v1")

    bad = copy.deepcopy(base)
    bad["ir_version"] = "2.0.0"
    expect_reject("wrong-major-version", bad)

    bad = copy.deepcopy(base)
    bad["required_features"].append("unknown-future-feature")
    expect_reject("unknown-required-feature", bad)

    bad = copy.deepcopy(base)
    bad["functions"][0]["id"] = "other"
    expect_reject("missing-entry-function", bad)

    bad = copy.deepcopy(base)
    bad["functions"].append(copy.deepcopy(base["functions"][0]))
    expect_reject("duplicate-function-id", bad)

    bad = copy.deepcopy(base)
    bad["functions"][0]["blocks"][0]["instructions"][2]["lhs"] = {"value": "%missing"}
    expect_reject("undefined-block-local-value", bad)

    bad = copy.deepcopy(base)
    bad["functions"][0]["blocks"][0]["instructions"][3]["symbol"] = "host_graphics"
    expect_reject("undeclared-host-symbol", bad)

    bad = copy.deepcopy(base)
    bad["functions"][0]["blocks"][0]["terminator"] = {
        "op": "jump",
        "target": "does-not-exist"
    }
    expect_reject("unknown-direct-target", bad)

    bad = copy.deepcopy(base)
    bad["functions"][0]["blocks"][0]["terminator"] = {
        "op": "indirect_jump",
        "target": {"value": "%hostret"},
        "candidate_blocks": []
    }
    expect_reject("unbounded-indirect-jump", bad)

    bad = copy.deepcopy(base)
    bad["functions"][0]["blocks"][0]["instructions"][0]["value"] = 1 << 32
    expect_reject("constant-overflow", bad)

    bad = copy.deepcopy(base)
    bad["functions"][0]["blocks"][0]["instructions"][2]["kind"] = "riscv_addi"
    expect_reject("guest-isa-opcode-leak", bad)

    bad = copy.deepcopy(base)
    bad["state_slots"] = []
    expect_reject("undeclared-state-slot", bad)

    bad = copy.deepcopy(base)
    bad["state_slots"][0]["type"] = "i16"
    expect_reject("state-slot-type-mismatch", bad)

    bad = copy.deepcopy(base)
    bad["functions"][0]["blocks"][0]["instructions"][1]["result_type"] = "i16"
    expect_reject("binop-type-mismatch", bad)

    bad = copy.deepcopy(base)
    bad["functions"][0]["return_type"] = "i16"
    expect_reject("return-type-mismatch", bad)

    print("OPENRECOMP_IR_V1_SPEC=PASS tests=15")


if __name__ == "__main__":
    main()
