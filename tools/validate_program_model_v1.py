#!/usr/bin/env python3
"""Validate an OpenRecomp Shared Program Model V1 document.

Two layers are enforced:

1. JSON Schema (`schema/openrecomp-program-v1.schema.json`) for the wire shape;
2. `openrecomp.program_model.ProgramModel.from_document` for graph consistency
   (unique ids, declared successor/callee references, reciprocal predecessor
   derivation, entry agreement, address-width agreement).

Rejection is fail-closed with exit code 2. Acceptance prints
`OPENRECOMP_PROGRAM_MODEL_V1_VALID=PASS`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jsonschema  # noqa: E402

from openrecomp.program_model import ProgramModel, ProgramModelError  # noqa: E402

SCHEMA_PATH = ROOT / "schema" / "openrecomp-program-v1.schema.json"


def load_and_validate(path: str | Path) -> ProgramModel:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    jsonschema.validate(document, schema)
    return ProgramModel.from_document(document)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_program_model_v1.py <program.json>", file=sys.stderr)
        return 2
    try:
        load_and_validate(argv[1])
    except (json.JSONDecodeError, jsonschema.ValidationError, ProgramModelError) as exc:
        print(f"OPENRECOMP_PROGRAM_MODEL_V1_REJECT: {exc}", file=sys.stderr)
        return 2
    print("OPENRECOMP_PROGRAM_MODEL_V1_VALID=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
