#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "openrecomp-ir-v1.schema.json"
SUPPORTED_FEATURES = {"core-v1", "host-call", "bounded-indirect-jump"}
TYPE_BITS = {"i1": 1, "i8": 8, "i16": 16, "i32": 32, "i64": 64}


class IRSemanticError(ValueError):
    pass


def _check_const(value: int, type_name: str, where: str) -> None:
    if value >= (1 << TYPE_BITS[type_name]):
        raise IRSemanticError(f"{where}: constant {value} does not fit {type_name}")


def _operand_type(operand: dict, defined_types: dict[str, str], where: str) -> str:
    if "value" in operand:
        name = operand["value"]
        if name not in defined_types:
            raise IRSemanticError(f"{where}: undefined value {name}")
        return defined_types[name]
    _check_const(operand["const"], operand["type"], where)
    return operand["type"]


def _source_address_ok(item: dict, limit: int, where: str) -> None:
    if "source_address" in item and item["source_address"] >= limit:
        raise IRSemanticError(f"{where}: source_address exceeds address width")


def validate_document(ir: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(ir, schema)

    unknown_features = sorted(set(ir["required_features"]) - SUPPORTED_FEATURES)
    if unknown_features:
        raise IRSemanticError("unsupported required feature(s): " + ", ".join(unknown_features))

    state_ids = [s["id"] for s in ir["state_slots"]]
    if len(state_ids) != len(set(state_ids)):
        raise IRSemanticError("duplicate state slot id")
    state_types = {s["id"]: s["type"] for s in ir["state_slots"]}

    function_ids = [f["id"] for f in ir["functions"]]
    if len(function_ids) != len(set(function_ids)):
        raise IRSemanticError("duplicate function id")
    if ir["entry_function"] not in set(function_ids):
        raise IRSemanticError("entry_function does not name a function")

    signatures: dict[str, tuple[list[str], str | None]] = {}
    for function in ir["functions"]:
        param_ids = [p["id"] for p in function["params"]]
        if len(param_ids) != len(set(param_ids)):
            raise IRSemanticError(f"{function['id']}: duplicate parameter id")
        signatures[function["id"]] = ([p["type"] for p in function["params"]], function["return_type"])

    address_bits = ir["source"]["address_bits"]
    address_type = f"i{address_bits}"
    address_limit = 1 << address_bits
    declared_hosts = set(ir["required_host_symbols"])

    for function in ir["functions"]:
        if function["guest_address"] >= address_limit:
            raise IRSemanticError(f"{function['id']}: function guest address exceeds address width")

        block_ids = [b["id"] for b in function["blocks"]]
        if len(block_ids) != len(set(block_ids)):
            raise IRSemanticError(f"{function['id']}: duplicate block id")
        block_set = set(block_ids)
        function_results = {p["id"] for p in function["params"]}

        for block_index, block in enumerate(function["blocks"]):
            if block["guest_address"] >= address_limit:
                raise IRSemanticError(f"{function['id']}/{block['id']}: block guest address exceeds address width")

            # Function parameters are available in the entry block only. Other
            # cross-edge state must use explicit state slots or memory in V1.
            defined_types: dict[str, str] = {}
            if block_index == 0:
                defined_types.update({p["id"]: p["type"] for p in function["params"]})

            for index, insn in enumerate(block["instructions"]):
                where = f"{function['id']}/{block['id']}/instruction[{index}]"
                _source_address_ok(insn, address_limit, where)
                op = insn["op"]

                if op == "const":
                    _check_const(insn["value"], insn["result_type"], where)

                elif op == "read_state":
                    slot = insn["slot"]
                    if slot not in state_types:
                        raise IRSemanticError(f"{where}: undeclared state slot {slot}")
                    if insn["result_type"] != state_types[slot]:
                        raise IRSemanticError(f"{where}: read_state type does not match slot {slot}")

                elif op == "write_state":
                    slot = insn["slot"]
                    if slot not in state_types:
                        raise IRSemanticError(f"{where}: undeclared state slot {slot}")
                    value_type = _operand_type(insn["value"], defined_types, where)
                    if value_type != state_types[slot]:
                        raise IRSemanticError(f"{where}: write_state type does not match slot {slot}")

                elif op == "binop":
                    lhs = _operand_type(insn["lhs"], defined_types, where)
                    rhs = _operand_type(insn["rhs"], defined_types, where)
                    if lhs != insn["result_type"] or rhs != insn["result_type"]:
                        raise IRSemanticError(f"{where}: binop operands must match result_type")

                elif op == "compare":
                    lhs = _operand_type(insn["lhs"], defined_types, where)
                    rhs = _operand_type(insn["rhs"], defined_types, where)
                    if lhs != rhs:
                        raise IRSemanticError(f"{where}: compare operands must have the same type")

                elif op == "cast":
                    source_type = _operand_type(insn["value"], defined_types, where)
                    source_bits = TYPE_BITS[source_type]
                    result_bits = TYPE_BITS[insn["result_type"]]
                    kind = insn["kind"]
                    if kind in {"zext", "sext"} and result_bits <= source_bits:
                        raise IRSemanticError(f"{where}: extension must increase width")
                    if kind == "trunc" and result_bits >= source_bits:
                        raise IRSemanticError(f"{where}: truncation must decrease width")
                    if kind == "bitcast" and result_bits != source_bits:
                        raise IRSemanticError(f"{where}: bitcast must preserve width")

                elif op == "select":
                    cond = _operand_type(insn["condition"], defined_types, where)
                    yes = _operand_type(insn["if_true"], defined_types, where)
                    no = _operand_type(insn["if_false"], defined_types, where)
                    if cond != "i1":
                        raise IRSemanticError(f"{where}: select condition must be i1")
                    if yes != insn["result_type"] or no != insn["result_type"]:
                        raise IRSemanticError(f"{where}: select values must match result_type")

                elif op == "load":
                    addr = _operand_type(insn["address"], defined_types, where)
                    if addr != address_type:
                        raise IRSemanticError(f"{where}: memory address must be {address_type}")
                    if insn["alignment"] > insn["width_bits"] // 8:
                        raise IRSemanticError(f"{where}: alignment exceeds access width")
                    if TYPE_BITS[insn["result_type"]] < insn["width_bits"]:
                        raise IRSemanticError(f"{where}: load result is narrower than access width")

                elif op == "store":
                    addr = _operand_type(insn["address"], defined_types, where)
                    value_type = _operand_type(insn["value"], defined_types, where)
                    if addr != address_type:
                        raise IRSemanticError(f"{where}: memory address must be {address_type}")
                    if insn["alignment"] > insn["width_bits"] // 8:
                        raise IRSemanticError(f"{where}: alignment exceeds access width")
                    if TYPE_BITS[value_type] != insn["width_bits"]:
                        raise IRSemanticError(f"{where}: store value width must equal access width")

                elif op == "call":
                    callee = insn["callee"]
                    if callee not in signatures:
                        raise IRSemanticError(f"{where}: unknown callee {callee}")
                    expected_params, return_type = signatures[callee]
                    actual = [_operand_type(a, defined_types, where) for a in insn["args"]]
                    if actual != expected_params:
                        raise IRSemanticError(f"{where}: call arguments do not match callee signature")
                    has_result = "result" in insn
                    has_type = "result_type" in insn
                    if has_result != has_type:
                        raise IRSemanticError(f"{where}: result and result_type must appear together")
                    if has_result and insn["result_type"] != return_type:
                        raise IRSemanticError(f"{where}: call result type does not match callee")
                    if return_type is None and has_result:
                        raise IRSemanticError(f"{where}: void callee cannot produce a result")

                elif op == "host_call":
                    for operand in insn["args"]:
                        _operand_type(operand, defined_types, where)
                    if insn["symbol"] not in declared_hosts:
                        raise IRSemanticError(f"{where}: host symbol {insn['symbol']} is not declared")
                    if ("result" in insn) != ("result_type" in insn):
                        raise IRSemanticError(f"{where}: result and result_type must appear together")

                if "result" in insn:
                    result = insn["result"]
                    if result in function_results:
                        raise IRSemanticError(f"{where}: duplicate result id {result}")
                    function_results.add(result)
                    defined_types[result] = insn["result_type"]

            term = block["terminator"]
            term_where = f"{function['id']}/{block['id']}/terminator"
            _source_address_ok(term, address_limit, term_where)

            if term["op"] == "jump":
                if term["target"] not in block_set:
                    raise IRSemanticError(f"{term_where}: unknown target {term['target']}")

            elif term["op"] == "branch":
                if _operand_type(term["condition"], defined_types, term_where) != "i1":
                    raise IRSemanticError(f"{term_where}: branch condition must be i1")
                for target in (term["target_true"], term["target_false"]):
                    if target not in block_set:
                        raise IRSemanticError(f"{term_where}: unknown target {target}")

            elif term["op"] == "return":
                expected = function["return_type"]
                has_value = "value" in term
                if expected is None and has_value:
                    raise IRSemanticError(f"{term_where}: void function cannot return a value")
                if expected is not None and not has_value:
                    raise IRSemanticError(f"{term_where}: non-void function must return a value")
                if has_value and _operand_type(term["value"], defined_types, term_where) != expected:
                    raise IRSemanticError(f"{term_where}: return value type mismatch")

            elif term["op"] == "indirect_jump":
                if _operand_type(term["target"], defined_types, term_where) != address_type:
                    raise IRSemanticError(f"{term_where}: indirect target must be {address_type}")
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
