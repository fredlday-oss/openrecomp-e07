from __future__ import annotations

from pathlib import Path

import openrecomp.module as module_v1
from tools.ir_v1_1_contract import validate_document_v1_1


def load_module_v1_1(
    manifest_path: str | Path,
    ir_path: str | Path,
    host_contract_path: str | Path,
):
    old_validator = module_v1.validate_document
    module_v1.validate_document = validate_document_v1_1
    try:
        return module_v1.ModuleImage.from_files(manifest_path, ir_path, host_contract_path)
    finally:
        module_v1.validate_document = old_validator
