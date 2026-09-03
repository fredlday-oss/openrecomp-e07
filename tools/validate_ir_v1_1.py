#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

import jsonschema

from ir_v1_1_contract import IRV11SemanticError, load_and_validate_v1_1


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_ir_v1_1.py <ir.json>", file=sys.stderr)
        return 2
    try:
        load_and_validate_v1_1(argv[1])
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError, IRV11SemanticError, ValueError) as exc:
        print(f"OPENRECOMP_IR_V1_1_REJECT: {exc}", file=sys.stderr)
        return 2
    print("OPENRECOMP_IR_V1_1_VALID=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
