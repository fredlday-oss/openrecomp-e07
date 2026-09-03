from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import openrecomp.module as module_v1
from tools.ir_v1_1_contract import validate_document_v1_1


def load_module_v1_1(
    manifest_path: str | Path,
    ir_path: str | Path,
    host_contract_path: str | Path,
):
    """Load unchanged Module Image V1 carrying an IR V1.1 payload.

    Module Image format remains 1.0.0. Its frozen schema pins the embedded IR
    version to 1.0.0, so the V1.1 adapter derives only that additive manifest
    constraint in a temporary schema while reusing every other frozen check.
    """
    schema = copy.deepcopy(json.loads(Path(module_v1.MODULE_SCHEMA_PATH).read_text(encoding="utf-8")))
    schema["properties"]["ir"]["properties"]["version"] = {"const": "1.1.0"}
    old_validator = module_v1.validate_document
    old_schema_path = module_v1.MODULE_SCHEMA_PATH
    with tempfile.TemporaryDirectory(prefix="openrecomp-v1-1-") as tmp:
        derived_schema = Path(tmp) / "openrecomp-module-v1-ir-v1.1.schema.json"
        derived_schema.write_text(json.dumps(schema, sort_keys=True), encoding="utf-8")
        module_v1.validate_document = validate_document_v1_1
        module_v1.MODULE_SCHEMA_PATH = derived_schema
        try:
            return module_v1.ModuleImage.from_files(manifest_path, ir_path, host_contract_path)
        finally:
            module_v1.validate_document = old_validator
            module_v1.MODULE_SCHEMA_PATH = old_schema_path
