from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validate_ir_v1 import SUPPORTED_FEATURES as V1_SUPPORTED_FEATURES
from tools.validate_ir_v1 import validate_document as validate_document_v1

V1_SCHEMA_PATH = ROOT / "schema" / "openrecomp-ir-v1.schema.json"
IR_V1_1_VERSION = "1.1.0"
INTEGER_DIVREM_FEATURE = "integer-divrem-v1"
DIVREM_KINDS = {"udiv", "urem", "sdiv", "srem"}
SUPPORTED_FEATURES = set(V1_SUPPORTED_FEATURES) | {INTEGER_DIVREM_FEATURE}


class IRV11SemanticError(ValueError):
    pass


def schema_v1_1() -> dict:
    schema = copy.deepcopy(json.loads(V1_SCHEMA_PATH.read_text(encoding="utf-8")))
    schema["title"] = "OpenRecomp Normalized IR V1.1"
    schema["properties"]["ir_version"] = {"const": IR_V1_1_VERSION}
    kinds = schema["$defs"]["binop_inst"]["properties"]["kind"]["enum"]
    for kind in sorted(DIVREM_KINDS):
        if kind not in kinds:
            kinds.append(kind)
    return schema


def _divrem_instructions(ir: dict) -> list[dict]:
    found: list[dict] = []
    for function in ir.get("functions", []):
        for block in function.get("blocks", []):
            for insn in block.get("instructions", []):
                if insn.get("op") == "binop" and insn.get("kind") in DIVREM_KINDS:
                    found.append(insn)
    return found


def validate_document_v1_1(ir: dict) -> None:
    jsonschema.validate(ir, schema_v1_1())
    unknown = sorted(set(ir["required_features"]) - SUPPORTED_FEATURES)
    if unknown:
        raise IRV11SemanticError("unsupported required feature(s): " + ", ".join(unknown))
    divrem = _divrem_instructions(ir)
    if divrem and INTEGER_DIVREM_FEATURE not in ir["required_features"]:
        raise IRV11SemanticError(
            f"{INTEGER_DIVREM_FEATURE} is required when V1.1 div/rem operations are present"
        )

    # Reuse every frozen V1 semantic/type invariant through a surrogate in
    # which only the additive V1.1 delta has been erased.
    surrogate = copy.deepcopy(ir)
    surrogate["ir_version"] = "1.0.0"
    surrogate["required_features"] = [
        feature for feature in surrogate["required_features"]
        if feature != INTEGER_DIVREM_FEATURE
    ]
    for function in surrogate["functions"]:
        for block in function["blocks"]:
            for insn in block["instructions"]:
                if insn.get("op") == "binop" and insn.get("kind") in DIVREM_KINDS:
                    insn["kind"] = "mul"
    validate_document_v1(surrogate)


def load_and_validate_v1_1(path: str | Path) -> dict:
    ir = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_document_v1_1(ir)
    return ir
