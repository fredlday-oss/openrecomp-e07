#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from openrecomp import (
    CallbackHostBinding,
    CoreRuntimeError,
    GuestMemory,
    GuestState,
    ModuleError,
    ModuleImage,
    ReferenceExecutor,
)

ROOT = Path(__file__).resolve().parents[1]
IR_PATH = ROOT / "examples" / "ir-v1" / "minimal.json"
CONTRACT_PATH = ROOT / "contracts" / "host_contract.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_manifest(ir_bytes: bytes, contract_bytes: bytes, ir: dict, contract: dict) -> dict:
    return {
        "module_format_version": "1.0.0",
        "module_id": ir["module_id"],
        "ir": {
            "version": ir["ir_version"],
            "sha256": digest(ir_bytes),
            "source_input_sha256": ir["source"]["input_sha256"],
        },
        "host_contract": {
            "version": contract["contract_version"],
            "sha256": digest(contract_bytes),
        },
        "memory": {"size_bytes": contract["memory"]["size_bytes"], "segments": []},
        "initial_state": [],
        "entry": {"function": ir["entry_function"], "observe_state_slot": "gpr:a0"},
        "limits": {"max_operations": 100, "max_call_depth": 8},
        "provenance": {
            "producer": "openrecomp.core-api-v1-test",
            "source_input_sha256": ir["source"]["input_sha256"],
        },
    }


def main() -> None:
    ir_bytes = IR_PATH.read_bytes()
    contract_bytes = CONTRACT_PATH.read_bytes()
    ir = json.loads(ir_bytes)
    contract = json.loads(contract_bytes)
    manifest = build_manifest(ir_bytes, contract_bytes, ir, contract)

    with tempfile.TemporaryDirectory() as temp:
        manifest_path = Path(temp) / "module.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        module = ModuleImage.from_files(manifest_path, IR_PATH, CONTRACT_PATH)

        host = CallbackHostBinding(
            contract["contract_version"],
            {"host_system": lambda args: sum(args)},
        )
        result = ReferenceExecutor(module, host).run()
        assert result.observed_state == 22, result
        assert result.function_return == 22, result
        print("PASS core-execution")

        try:
            ReferenceExecutor(module, CallbackHostBinding(contract["contract_version"], {}))
        except CoreRuntimeError:
            print("PASS missing-host-binding-rejected")
        else:
            raise AssertionError("missing host binding was accepted")

        try:
            GuestMemory(8, tuple(), "little").load(
                8,
                width_bits=8,
                result_type="i8",
                signed=False,
                alignment=1,
                misaligned_policy="fault",
            )
        except CoreRuntimeError:
            print("PASS memory-oob-rejected")
        else:
            raise AssertionError("out-of-bounds read was accepted")

        try:
            GuestState(ir["state_slots"], {}).write("missing-slot", 1)
        except CoreRuntimeError:
            print("PASS undeclared-state-rejected")
        else:
            raise AssertionError("undeclared state slot was accepted")

        bad = json.loads(json.dumps(manifest))
        bad["ir"]["sha256"] = "0" * 64
        bad_path = Path(temp) / "bad-module.json"
        bad_path.write_text(json.dumps(bad, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            ModuleImage.from_files(bad_path, IR_PATH, CONTRACT_PATH)
        except ModuleError:
            print("PASS integrity-mismatch-rejected")
        else:
            raise AssertionError("IR integrity mismatch was accepted")

    print("OPENRECOMP_CORE_API_V1_TESTS=PASS tests=5")


if __name__ == "__main__":
    main()
