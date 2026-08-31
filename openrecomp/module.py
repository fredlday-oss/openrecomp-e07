from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

from tools.validate_ir_v1 import validate_document

ROOT = Path(__file__).resolve().parents[1]
MODULE_SCHEMA_PATH = ROOT / "schema" / "openrecomp-module-v1.schema.json"


class ModuleError(ValueError):
    """Raised when an OpenRecomp module image is invalid or inconsistent."""


@dataclass(frozen=True)
class MemorySegment:
    name: str
    guest_address: int
    data: bytes
    sha256: str


@dataclass(frozen=True)
class ExecutionLimits:
    max_operations: int
    max_call_depth: int


@dataclass(frozen=True)
class ModuleImage:
    manifest: dict[str, Any]
    ir: dict[str, Any]
    host_contract: dict[str, Any]
    memory_size_bytes: int
    memory_segments: tuple[MemorySegment, ...]
    initial_state: dict[str, int]
    entry_function: str
    observe_state_slot: str
    limits: ExecutionLimits

    @classmethod
    def from_files(
        cls,
        manifest_path: str | Path,
        ir_path: str | Path,
        host_contract_path: str | Path,
    ) -> "ModuleImage":
        manifest_bytes = Path(manifest_path).read_bytes()
        ir_bytes = Path(ir_path).read_bytes()
        contract_bytes = Path(host_contract_path).read_bytes()
        try:
            manifest = json.loads(manifest_bytes)
            ir = json.loads(ir_bytes)
            contract = json.loads(contract_bytes)
        except json.JSONDecodeError as exc:
            raise ModuleError(f"invalid JSON: {exc}") from exc
        return cls.from_documents(
            manifest,
            ir,
            contract,
            ir_sha256=hashlib.sha256(ir_bytes).hexdigest(),
            contract_sha256=hashlib.sha256(contract_bytes).hexdigest(),
        )

    @classmethod
    def from_documents(
        cls,
        manifest: dict[str, Any],
        ir: dict[str, Any],
        host_contract: dict[str, Any],
        *,
        ir_sha256: str,
        contract_sha256: str,
    ) -> "ModuleImage":
        schema = json.loads(MODULE_SCHEMA_PATH.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(manifest, schema)
            validate_document(ir)
        except jsonschema.ValidationError as exc:
            raise ModuleError(f"schema validation failed: {exc.message}") from exc
        except ValueError as exc:
            raise ModuleError(f"IR validation failed: {exc}") from exc

        if manifest["module_id"] != ir["module_id"]:
            raise ModuleError("module_id does not match normalized IR")
        if manifest["ir"]["version"] != ir["ir_version"]:
            raise ModuleError("module/IR version mismatch")
        if manifest["ir"]["sha256"] != ir_sha256:
            raise ModuleError("normalized IR SHA-256 mismatch")
        if manifest["ir"]["source_input_sha256"] != ir["source"]["input_sha256"]:
            raise ModuleError("module lost normalized IR source provenance")
        if manifest["provenance"]["source_input_sha256"] != ir["source"]["input_sha256"]:
            raise ModuleError("module provenance/source hash mismatch")

        contract_version = host_contract.get("contract_version")
        if manifest["host_contract"]["version"] != contract_version:
            raise ModuleError("module/host-contract version mismatch")
        if ir["host_contract_version"] != contract_version:
            raise ModuleError("IR/host-contract version mismatch")
        if manifest["host_contract"]["sha256"] != contract_sha256:
            raise ModuleError("host-contract SHA-256 mismatch")

        if manifest["entry"]["function"] != ir["entry_function"]:
            raise ModuleError("module entry function does not match normalized IR")
        function_ids = {f["id"] for f in ir["functions"]}
        if manifest["entry"]["function"] not in function_ids:
            raise ModuleError("module entry function is not declared")

        state_types = {slot["id"]: slot["type"] for slot in ir["state_slots"]}
        observe_slot = manifest["entry"]["observe_state_slot"]
        if observe_slot not in state_types:
            raise ModuleError("observe_state_slot is not declared by the normalized IR")

        initial_state: dict[str, int] = {}
        type_bits = {"i1": 1, "i8": 8, "i16": 16, "i32": 32, "i64": 64}
        for item in manifest["initial_state"]:
            slot = item["slot"]
            if slot in initial_state:
                raise ModuleError(f"duplicate initial-state slot {slot}")
            if slot not in state_types:
                raise ModuleError(f"initial state references undeclared slot {slot}")
            bits = type_bits[state_types[slot]]
            if item["value"] >= (1 << bits):
                raise ModuleError(f"initial value does not fit slot {slot}")
            initial_state[slot] = item["value"]

        memory_size = manifest["memory"]["size_bytes"]
        contract_memory = host_contract.get("memory", {})
        if contract_memory.get("size_bytes") != memory_size:
            raise ModuleError("module/host memory-size mismatch")
        if contract_memory.get("oob_policy") != "deterministic fault":
            raise ModuleError("Core API V1 reference executor requires deterministic-fault memory")

        memory_segments: list[MemorySegment] = []
        occupied: list[tuple[int, int, str]] = []
        for segment in sorted(manifest["memory"]["segments"], key=lambda s: (s["guest_address"], s["name"])):
            data = bytes.fromhex(segment["data_hex"])
            digest = hashlib.sha256(data).hexdigest()
            if digest != segment["data_sha256"]:
                raise ModuleError(f"memory segment hash mismatch: {segment['name']}")
            start = segment["guest_address"]
            end = start + len(data)
            if end > memory_size:
                raise ModuleError(f"memory segment is out of bounds: {segment['name']}")
            for old_start, old_end, old_name in occupied:
                if max(start, old_start) < min(end, old_end):
                    raise ModuleError(f"memory segments overlap: {old_name} and {segment['name']}")
            occupied.append((start, end, segment["name"]))
            memory_segments.append(MemorySegment(segment["name"], start, data, digest))

        limits = ExecutionLimits(
            max_operations=manifest["limits"]["max_operations"],
            max_call_depth=manifest["limits"]["max_call_depth"],
        )

        return cls(
            manifest=manifest,
            ir=ir,
            host_contract=host_contract,
            memory_size_bytes=memory_size,
            memory_segments=tuple(memory_segments),
            initial_state=initial_state,
            entry_function=manifest["entry"]["function"],
            observe_state_slot=observe_slot,
            limits=limits,
        )
