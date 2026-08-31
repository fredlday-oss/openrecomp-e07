#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "openrecomp-ir-v1.schema.json"
SUPPORTED_FEATURES = {
    "core-v1",
    "host-call",
    "bounded-indirect-jump",
}
TYPE_BITS = {"i1": 1, "i8": 8, "i16": 16, "i32": 32, "i64": 64}


class IRSemanticError(ValueError):
    pass


def _operand_refs(operand: dict) -> list[str]:
    return [operand["value"]] if "value" in operand else []


def _check_const(value: int, type_name: str, where: str) -> None:
    bits = TYPE_BITS[type_name]
    if value >= (1 << bits):
        raise IRSemanticError(f"{where}: constant {value} does not fit {type_name}")


def _instruction_operands(insn: dict) -> list[dict]:
    op = insn["op"]
    if op == "write_state":
        return [insn["value"]]
    if op == "binop" or op == "compare":
        return [insn["lhs"], insn["rhs"]]
    if op == "cast":
        return [insn["value"]]
    if op == "select":
        return [insn["condition"], insn["if_true"], insn["if_false"]]
    if op == "load":
        return [insn["address"]]
    if op == "store":
        return [insn["address"], insn["value"]]
    if op in {"call", "host_call"}:
        return list(insn["args"])
    return []


def _terminator_operands(term: dict) -> list[dict]:
    if term["op"] == "branch":
        return [term["condition"]]
    if term["op"] == "return" and "value" in term:
        return [term["value"]]
    if term["op"] == "indirect_jump":
        return [term["target"]]
    return []


def _check_operand(operand: dict, defined: set[str], where: str) -> None:
    if "value" in operand:
        if operand["value"] not in defined:
            raise IRSemanticError(f"{where}: undefined value {operand['value']}")
    else:
        _check_const(operand["const"], operand["type"], where)


def validate_document(ir: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(ir, schema)

    unknown_features = sorted(set(ir["required_features"]) - SUPPORTED_FEATURES)
    if unknown_features:
        raise IRSemanticError("unsupported required feature(s): " + ", ".join(unknown_features))

    function_ids = [f["id"] for f in ir["functions"]]
    if len(function_ids) != len(set(function_ids)):
        raise IRSemanticError("duplicate function id")
    if ir["entry_function"] not in set(function_ids):
        raise IRSemanticError("entry_function does not name a function")

    address_limit = 1 << ir["source"]["address_bits"]
    declared_hosts = set(ir["required_host_symbols"])
    function_set = set(function_ids)

    for function in ir["functions"]:
        if function["guest_address"] >= address_limit:
            raise IRSemanticError(f"{function['id']}: function guest address exceeds address width")

        block_ids = [b["id"] for b in function["blocks"]]
        if len(block_ids) != len(set(block_ids)):
            raise IRSemanticError(f"{function['id']}: duplicate block id")
        block_set = set(block_ids)
        function_results: set[str] = set()

        for block in function["blocks"]:
            if block["guest_address"] >= address_limit:
                raise IRSemanticError(f"{function['id']}/{block['id']}: block guest address exceeds address width")

            # V1 temporaries are deliberately block-local. State that must cross a
            # control-flow edge is represented via explicit state/memory operations.
            defined: set[str] = set()

            for index, insn in enumerate(block["instructions"]):
                where = f"{function['id']}/{block['id']}/instruction[{index}]"

                for operand in _instruction_operands(insn):
                    _check_operand(operand, defined, where)

                if insn["op"] == "const":
                    _check_const(insn["value"], insn["result_type"], where)

                if insn["op"] in {"call", "host_call"}:
                    has_result = "result" in insn
                    has_type = "result_type" in insn
                    if has_result != has_type:
                        raise IRSemanticError(f"{where}: result and result_type must appear together")

                if insn["op"] == "call" and insn["callee"] not in function_set:
                    raise IRSemanticError(f"{where}: unknown callee {insn['callee']}")

                if insn["op"] == "host_call" and insn["symbol"] not in declared_hosts:
                    raise IRSemanticError(f"{where}: host symbol {insn['symbol']} is not declared")

                if insn["op"] in {"load", "store"}:
                    if insn["alignment"] > insn["width_bits"] // 8:
                        raise IRSemanticError(f"{where}: alignment exceeds access width")

                if "result" in insn:
                    result = insn["result"]
                    if result in function_results:
                        raise IRSemanticError(f"{where}: duplicate result id {result}")
                    function_results.add(result)
                    defined.add(result)

            term = block["terminator"]
            term_where = f"{function['id']}/{block['id']}/terminator"
            for operand in _terminator_operands(term):
                _check_operand(operand, defined, term_where)

            if term["op"] == "jump" and term["target"] not in block_set:
                raise IRSemanticError(f"{term_where}: unknown target {term['target']}")
            if term["op"] == "branch":
                for target in (term["target_true"], term["target_false"]):
                    if target not in block_set:
                        raise IRSemanticError(f"{term_where}: unknown target {target}")
            if term["op"] == "indirect_jump":
                for target in term["candidate_blocks"]:
                    if target not in block_set:
                        raise IRSemanticError(f"{term_where}: unknown candidate target {target}")


def load_and_validate(path: str | Path) -> dict:
    ir = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_document(ir)
    return ir


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_ir_v1.py <ir.json>", file=sys.stderr)
        return 2
    try:
        load_and_validate(argv[1])
    except (json.JSONDecodeError, jsonschema.ValidationError, IRSemanticError) as exc:
        print(f"OPENRECOMP_IR_V1_REJECT: {exc}", file=sys.stderr)
        return 2
    print("OPENRECOMP_IR_V1_VALID=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
