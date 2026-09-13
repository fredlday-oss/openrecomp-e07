#!/usr/bin/env python3
"""Executable gate for the architecture-neutral OpenRecomp frontend contract.

The contract itself lives in `contracts/frontend_contract_v1.json` and is
documented in `docs/FRONTEND_CONTRACT_V1.md`. This tool is the enforcement
point: every rule in the contract that names a probe must have a probe
implemented here, and every registered architecture must satisfy the adapter
surface, the fail-closed rules and (where one is declared) an end-to-end chain
proof through frozen normalized IR V1, Module Image V1 and Core API V1.

The gate never treats a missing toolchain as a pass: a declared chain proof
that cannot be executed is a failure, and toolchain-dependent proofs stay in
`tools/phase1_host_gates_v1.py` as explicit skips.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import jsonschema  # noqa: E402

from openrecomp import (  # noqa: E402
    CallbackHostBinding,
    ModuleError,
    ModuleImage,
    ReferenceExecutor,
)
from openrecomp.runtime import CoreRuntimeError  # noqa: E402
from tools.validate_ir_v1 import IRSemanticError, validate_document  # noqa: E402

CONTRACT_PATH = ROOT / "contracts" / "frontend_contract_v1.json"
IR_SCHEMA_PATH = ROOT / "schema" / "openrecomp-ir-v1.schema.json"
HOST_CONTRACT_PATH = ROOT / "contracts" / "host_contract.json"


class ContractViolation(AssertionError):
    """Raised when an implementation does not honour the frontend contract."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _serialize(document: object) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _resolve(document: dict, dotted: str) -> object:
    node: object = document
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise ContractViolation(f"contract path {dotted} is not present in the document")
        node = node[part]
    return node


def _run_tool(argv: list[str]) -> str:
    """Run a repository tool exactly as CI does: from the repository root."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        [sys.executable, *argv],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        raise ContractViolation(f"{' '.join(argv)} exited {completed.returncode}: {combined.strip()[-400:]}")
    return combined


class ContractContext:
    """Shared inputs derived once so every probe inspects the same artefacts."""

    def __init__(self, contract: dict) -> None:
        self.contract = contract
        self.ir_schema = json.loads(IR_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.host_contract = json.loads(HOST_CONTRACT_PATH.read_text(encoding="utf-8"))
        self.host_contract_bytes = HOST_CONTRACT_PATH.read_bytes()
        self.architectures = {item["architecture"]: item for item in contract["registered_architectures"]}

        frontend_entry = self.architectures["mips32-le"]
        self.frontend = importlib.import_module(frontend_entry["frontend_module"])
        self.adapter = importlib.import_module(frontend_entry["adapter_module"])
        self.fixture_hex = ROOT / "examples" / "mips32-v1" / "fixture.hex"
        self.fixture_meta_path = ROOT / "examples" / "mips32-v1" / "fixture.json"
        self.fixture_meta = json.loads(self.fixture_meta_path.read_text(encoding="utf-8"))
        self.words, self.source_sha256 = self.frontend.load_hex(self.fixture_hex)
        self.ir, self.sidecar, self.report = self.frontend.convert(
            self.fixture_meta, self.words, self.source_sha256, self.host_contract
        )

    # -- helpers ---------------------------------------------------------
    def decoded_mnemonics(self) -> set[str]:
        return {self.adapter.decode(address, word)["op"] for address, word in sorted(self.words.items())}

    def ir_vocabulary(self) -> tuple[set[str], set[str], set[str]]:
        ops: set[str] = set()
        kinds: set[str] = set()
        predicates: set[str] = set()
        for function in self.ir["functions"]:
            for block in function["blocks"]:
                for insn in block["instructions"]:
                    ops.add(insn["op"])
                    if "kind" in insn:
                        kinds.add(insn["kind"])
                    if "predicate" in insn:
                        predicates.add(insn["predicate"])
                ops.add(block["terminator"]["op"])
        return ops, kinds, predicates

    def schema_enum(self, definition: str, field: str) -> set[str]:
        node = self.ir_schema["$defs"][definition]
        if field in node["properties"]:
            return set(node["properties"][field]["enum"])
        return set(node["properties"][field]["items"]["enum"])

    def mutate_ir(self) -> dict:
        return copy.deepcopy(self.ir)

    def build_manifest(self, ir: dict, ir_bytes: bytes, *, observe_state_slot: str, max_operations: int = 1000) -> dict:
        return {
            "module_format_version": self.contract["module_format_version"],
            "module_id": ir["module_id"],
            "ir": {
                "version": ir["ir_version"],
                "sha256": _digest(ir_bytes),
                "source_input_sha256": ir["source"]["input_sha256"],
            },
            "host_contract": {
                "version": self.host_contract["contract_version"],
                "sha256": _digest(self.host_contract_bytes),
            },
            "memory": {"size_bytes": self.host_contract["memory"]["size_bytes"], "segments": []},
            "initial_state": [],
            "entry": {"function": ir["entry_function"], "observe_state_slot": observe_state_slot},
            "limits": {"max_operations": max_operations, "max_call_depth": 8},
            "provenance": {
                "producer": "openrecomp.frontend-contract-v1-probe",
                "source_input_sha256": ir["source"]["input_sha256"],
            },
        }

    def execute_documents(self, ir: dict, *, observe_state_slot: str, hosts: dict | None = None) -> object:
        ir_bytes = _serialize(ir).encode("utf-8")
        manifest = self.build_manifest(ir, ir_bytes, observe_state_slot=observe_state_slot)
        module = ModuleImage.from_documents(
            manifest,
            ir,
            self.host_contract,
            ir_sha256=_digest(ir_bytes),
            contract_sha256=_digest(self.host_contract_bytes),
        )
        binding = CallbackHostBinding(self.host_contract["contract_version"], hosts or {})
        return ReferenceExecutor(module, binding).run()


# ---------------------------------------------------------------------------
# probes: one function per lowering_rules[].probe id in the contract
# ---------------------------------------------------------------------------


def probe_ir_vocabulary_is_closed(ctx: ContractContext) -> str:
    allowed_instruction_ops = {
        branch["$ref"].split("/")[-1].replace("_inst", "")
        for branch in ctx.ir_schema["$defs"]["instruction"]["oneOf"]
    }
    allowed_terminators = set()
    for branch in ctx.ir_schema["$defs"]["terminator"]["oneOf"]:
        allowed_terminators.add(branch["properties"]["op"]["const"])
    allowed_kinds = set()
    for definition in ("binop_inst", "cast_inst"):
        allowed_kinds |= set(ctx.ir_schema["$defs"][definition]["properties"]["kind"]["enum"])
    allowed_predicates = set(ctx.ir_schema["$defs"]["compare_inst"]["properties"]["predicate"]["enum"])

    ops, kinds, predicates = ctx.ir_vocabulary()
    unknown_ops = sorted(ops - allowed_instruction_ops - allowed_terminators)
    if unknown_ops:
        raise ContractViolation(f"IR uses operations outside frozen IR V1: {unknown_ops}")
    unknown_kinds = sorted(kinds - allowed_kinds)
    if unknown_kinds:
        raise ContractViolation(f"IR uses binop/cast kinds outside frozen IR V1: {unknown_kinds}")
    unknown_predicates = sorted(predicates - allowed_predicates)
    if unknown_predicates:
        raise ContractViolation(f"IR uses predicates outside frozen IR V1: {unknown_predicates}")

    leaked = sorted(ops & ctx.decoded_mnemonics())
    if leaked:
        raise ContractViolation(f"guest mnemonics leaked into normalized IR: {leaked}")
    return f"ops={len(ops)} kinds={len(kinds)} predicates={len(predicates)} guest_mnemonics_leaked=0"


def probe_conversion_is_deterministic(ctx: ContractContext) -> str:
    again_ir, again_sidecar, again_report = ctx.frontend.convert(
        ctx.fixture_meta, ctx.words, ctx.source_sha256, ctx.host_contract
    )
    for name, first, second in (
        ("ir", ctx.ir, again_ir),
        ("sidecar", ctx.sidecar, again_sidecar),
        ("report", ctx.report, again_report),
    ):
        if _serialize(first) != _serialize(second):
            raise ContractViolation(f"{name} output is not byte-identical across two conversions")
    return "ir/sidecar/report byte-identical across two conversions"


def probe_host_contract_oob_policy_must_fault(ctx: ContractContext) -> str:
    tampered = copy.deepcopy(ctx.host_contract)
    tampered["memory"]["oob_policy"] = "allow"
    try:
        ctx.frontend.convert(ctx.fixture_meta, ctx.words, ctx.source_sha256, tampered)
    except ctx.frontend.FrontendError:
        return "oob_policy='allow' rejected by frontend"
    raise ContractViolation("frontend accepted a host contract that does not fault closed on out-of-bounds memory")


def probe_host_contract_must_be_deterministic(ctx: ContractContext) -> str:
    rejected = []
    for field in ("wall_clock", "randomness"):
        tampered = copy.deepcopy(ctx.host_contract)
        tampered["system"][field] = True
        try:
            ctx.frontend.convert(ctx.fixture_meta, ctx.words, ctx.source_sha256, tampered)
        except ctx.frontend.FrontendError:
            rejected.append(field)
    if len(rejected) != 2:
        raise ContractViolation(f"frontend accepted a non-deterministic host contract (rejected only {rejected})")
    return "wall_clock=true and randomness=true both rejected"


def probe_unknown_encoding_rejected(ctx: ContractContext) -> str:
    checked = []
    for architecture, entry in sorted(ctx.architectures.items()):
        module = importlib.import_module(entry["adapter_module"])
        probe = entry["decode_reject_probe"]
        expected = probe["expect_error"]
        error_type = _expected_error(module, entry, expected)
        try:
            module.decode(probe["address"], probe["word"])
        except error_type:
            checked.append(f"{architecture}:{expected}")
        else:
            raise ContractViolation(f"{architecture}: decode accepted probe word 0x{probe['word']:x}")
    return "rejected " + ", ".join(checked)


def _expected_error(module, entry: dict, expected: str):
    if expected == "DecodeError":
        attribute = entry.get("adapter_error_attribute") or "DecodeError"
        error_type = getattr(module, attribute, None)
        if not isinstance(error_type, type) or not issubclass(error_type, ValueError):
            raise ContractViolation(f"{entry['adapter_module']} does not expose a ValueError-derived {attribute}")
        return error_type
    if expected == "NotImplementedError":
        return NotImplementedError
    if expected == "ValueError":
        return ValueError
    raise ContractViolation(f"contract declares an unsupported expect_error value: {expected}")


def probe_undeclared_state_slot_rejected(ctx: ContractContext) -> str:
    ir = ctx.mutate_ir()
    for function in ir["functions"]:
        for block in function["blocks"]:
            for insn in block["instructions"]:
                if insn["op"] == "write_state":
                    insn["slot"] = "probe:undeclared-slot"
                    try:
                        validate_document(ir)
                    except IRSemanticError:
                        return "write_state to an undeclared slot rejected"
                    raise ContractViolation("IR validation accepted an undeclared state slot")
    raise ContractViolation("fixture produced no write_state instruction to probe")


def probe_memory_address_type_must_match_address_bits(ctx: ContractContext) -> str:
    ir = ctx.mutate_ir()
    for function in ir["functions"]:
        for block in function["blocks"]:
            for index, insn in enumerate(block["instructions"]):
                if insn["op"] != "load":
                    continue
                block["instructions"].insert(
                    index,
                    {
                        "op": "cast",
                        "result": "%probe_narrow_address",
                        "result_type": "i16",
                        "kind": "trunc",
                        "value": insn["address"],
                        "source_address": insn["source_address"],
                    },
                )
                insn["address"] = {"value": "%probe_narrow_address"}
                try:
                    validate_document(ir)
                except IRSemanticError:
                    return "i16 memory address rejected while source.address_bits=32"
                raise ContractViolation("IR validation accepted a memory address narrower than source.address_bits")
    raise ContractViolation("fixture produced no load instruction to probe")


def probe_shift_count_must_be_normalized(ctx: ContractContext) -> str:
    ir = {
        "ir_version": ctx.contract["normalized_ir_version"],
        "module_id": "openrecomp.frontend-contract-v1.shift-normalization-probe",
        "source": {
            "architecture": "probe-synthetic",
            "adapter": "openrecomp.frontend-contract-v1-probe",
            "address_bits": 32,
            "endianness": "little",
            "input_sha256": "0" * 64,
        },
        "required_features": ["core-v1"],
        "host_contract_version": ctx.host_contract["contract_version"],
        "required_host_symbols": [],
        "state_slots": [{"id": "probe:r", "type": "i8"}],
        "entry_function": "probe_main",
        "functions": [
            {
                "id": "probe_main",
                "guest_address": 0,
                "params": [],
                "return_type": None,
                "blocks": [
                    {
                        "id": "entry",
                        "guest_address": 0,
                        "instructions": [
                            {"op": "const", "result": "%v", "result_type": "i8", "value": 1, "source_address": 0},
                            {
                                "op": "binop",
                                "result": "%shifted",
                                "result_type": "i8",
                                "kind": "shl",
                                "lhs": {"value": "%v"},
                                "rhs": {"const": 8, "type": "i8"},
                                "source_address": 0,
                            },
                            {
                                "op": "write_state",
                                "slot": "probe:r",
                                "value": {"value": "%shifted"},
                                "source_address": 0,
                            },
                        ],
                        "terminator": {"op": "return", "source_address": 0},
                    }
                ],
            }
        ],
    }
    validate_document(ir)
    try:
        ctx.execute_documents(ir, observe_state_slot="probe:r")
    except CoreRuntimeError as exc:
        if "shift count" not in str(exc):
            raise ContractViolation(f"unexpected Core API failure for the shift probe: {exc}") from exc
        return "i8 shl by 8 faults deterministically instead of being masked"
    raise ContractViolation("Core API accepted an unnormalized shift count")


def probe_no_division_in_ir_v1(ctx: ContractContext) -> str:
    ir = ctx.mutate_ir()
    for function in ir["functions"]:
        for block in function["blocks"]:
            for insn in block["instructions"]:
                if insn["op"] == "binop":
                    insn["kind"] = "div"
                    try:
                        validate_document(ir)
                    except jsonschema.ValidationError:
                        return "binop kind 'div' rejected by frozen IR V1 schema"
                    raise ContractViolation("frozen IR V1 accepted a division operation")
    raise ContractViolation("fixture produced no binop instruction to probe")


def probe_unsupported_feature_rejected(ctx: ContractContext) -> str:
    ir = ctx.mutate_ir()
    ir["required_features"] = sorted(set(ir["required_features"]) | {"probe-unsupported-feature"})
    try:
        validate_document(ir)
    except IRSemanticError:
        return "unsupported required_features entry rejected"
    raise ContractViolation("IR validation accepted an unsupported required feature")


def probe_trap_terminator_is_the_fail_closed_exit(ctx: ContractContext) -> str:
    ir = {
        "ir_version": ctx.contract["normalized_ir_version"],
        "module_id": "openrecomp.frontend-contract-v1.trap-probe",
        "source": {
            "architecture": "probe-synthetic",
            "adapter": "openrecomp.frontend-contract-v1-probe",
            "address_bits": 32,
            "endianness": "little",
            "input_sha256": "0" * 64,
        },
        "required_features": ["core-v1"],
        "host_contract_version": ctx.host_contract["contract_version"],
        "required_host_symbols": [],
        "state_slots": [{"id": "probe:r", "type": "i8"}],
        "entry_function": "probe_main",
        "functions": [
            {
                "id": "probe_main",
                "guest_address": 0,
                "params": [],
                "return_type": None,
                "blocks": [
                    {
                        "id": "entry",
                        "guest_address": 0,
                        "instructions": [],
                        "terminator": {"op": "trap", "reason": "probe-unsupported-edge", "source_address": 0},
                    }
                ],
            }
        ],
    }
    validate_document(ir)
    try:
        ctx.execute_documents(ir, observe_state_slot="probe:r")
    except CoreRuntimeError as exc:
        if "probe-unsupported-edge" not in str(exc):
            raise ContractViolation(f"trap terminator lost its reason: {exc}") from exc
        return "trap terminator faults deterministically and preserves the reason"
    raise ContractViolation("Core API executed a trap terminator")


def probe_module_integrity_is_enforced(ctx: ContractContext) -> str:
    with tempfile.TemporaryDirectory(prefix="openrecomp-contract-") as temp:
        work = Path(temp)
        _run_frontend_chain(ctx, work, expect_marker="OPENRECOMP_MODULE_V1_PACKAGE=PASS", stop_after="package")
        module_path = work / "fixture.a.module.json"
        manifest = json.loads(module_path.read_text(encoding="utf-8"))
        manifest["ir"]["sha256"] = "0" * 64
        tampered = work / "tampered.module.json"
        tampered.write_text(_serialize(manifest), encoding="utf-8")
        try:
            ModuleImage.from_files(tampered, work / "fixture.a.ir.json", HOST_CONTRACT_PATH)
        except ModuleError:
            return "module with a tampered IR hash rejected"
    raise ContractViolation("Module Image V1 accepted a tampered IR hash")


def probe_ir_source_identity_must_match_registration(ctx: ContractContext) -> str:
    spec = ctx.contract["ir_source_identity"]
    entry = ctx.architectures["mips32-le"]
    source = ctx.ir["source"]
    if spec["architecture_must_equal_registration"] and source["architecture"] != entry["architecture"]:
        raise ContractViolation(
            f"ir.source.architecture '{source['architecture']}' does not match registration '{entry['architecture']}'"
        )
    if not isinstance(source["adapter"], str) or not source["adapter"].startswith(spec["adapter_prefix"]):
        raise ContractViolation(
            f"ir.source.adapter {source.get('adapter')!r} lacks the '{spec['adapter_prefix']}' identity prefix"
        )
    if source["address_bits"] not in ctx.contract["allowed_address_bits"]:
        raise ContractViolation(f"ir.source.address_bits {source['address_bits']} is outside frozen IR V1")
    if source["endianness"] not in spec["endianness_values"]:
        raise ContractViolation(f"ir.source.endianness '{source['endianness']}' is not an allowed value")
    if spec["input_sha256_must_equal_fixture_bytes"]:
        fixture_hash = _digest(ctx.fixture_hex.read_bytes())
        if source["input_sha256"] != fixture_hash:
            raise ContractViolation("ir.source.input_sha256 does not match the fixture bytes")
    adapter_id = ctx.adapter.info.architecture_id
    if adapter_id != entry.get("adapter_architecture_id", entry["architecture"]):
        raise ContractViolation(
            f"adapter legacy id '{adapter_id}' does not match registration adapter_architecture_id "
            f"'{entry.get('adapter_architecture_id')}'"
        )
    return (
        f"architecture={source['architecture']} adapter={source['adapter']} "
        f"address_bits={source['address_bits']} endianness={source['endianness']} "
        "input_sha256=fixture-bytes legacy_id=" + adapter_id
    )


PROBES = {
    "conversion_is_deterministic": probe_conversion_is_deterministic,
    "host_contract_must_be_deterministic": probe_host_contract_must_be_deterministic,
    "host_contract_oob_policy_must_fault": probe_host_contract_oob_policy_must_fault,
    "ir_source_identity_must_match_registration": probe_ir_source_identity_must_match_registration,
    "ir_vocabulary_is_closed": probe_ir_vocabulary_is_closed,
    "memory_address_type_must_match_address_bits": probe_memory_address_type_must_match_address_bits,
    "module_integrity_is_enforced": probe_module_integrity_is_enforced,
    "no_division_in_ir_v1": probe_no_division_in_ir_v1,
    "shift_count_must_be_normalized": probe_shift_count_must_be_normalized,
    "trap_terminator_is_the_fail_closed_exit": probe_trap_terminator_is_the_fail_closed_exit,
    "undeclared_state_slot_rejected": probe_undeclared_state_slot_rejected,
    "unknown_encoding_rejected": probe_unknown_encoding_rejected,
    "unsupported_feature_rejected": probe_unsupported_feature_rejected,
}


# ---------------------------------------------------------------------------
# structural checks
# ---------------------------------------------------------------------------


def check_adapter_surface(ctx: ContractContext) -> list[str]:
    surface = ctx.contract["adapter_surface"]
    field_types = {
        "str": str,
        "int": int,
        "tuple": tuple,
    }
    results = []
    for architecture, entry in sorted(ctx.architectures.items()):
        module = importlib.import_module(entry["adapter_module"])
        info = getattr(module, surface["info_attribute"], None)
        if info is None:
            raise ContractViolation(f"{architecture}: adapter has no '{surface['info_attribute']}'")
        if type(info).__name__ != "ArchitectureInfo":
            raise ContractViolation(f"{architecture}: info is not an ArchitectureInfo instance")
        for field, type_name in surface["info_fields"].items():
            value = getattr(info, field, None)
            if value is None:
                raise ContractViolation(f"{architecture}: ArchitectureInfo is missing '{field}'")
            expected = field_types[type_name]
            if expected is int and isinstance(value, bool):
                raise ContractViolation(f"{architecture}: '{field}' must not be a bool")
            if not isinstance(value, expected):
                raise ContractViolation(f"{architecture}: '{field}' must be {type_name}")
        declared_id = entry.get("adapter_architecture_id", architecture)
        if info.architecture_id != declared_id:
            raise ContractViolation(
                f"{architecture}: adapter advertises architecture_id '{info.architecture_id}', "
                f"registration declares '{declared_id}'"
            )
        if info.endianness not in surface["endianness_values"]:
            raise ContractViolation(f"{architecture}: unsupported endianness '{info.endianness}'")
        if not info.registers or not all(isinstance(name, str) and name for name in info.registers):
            raise ContractViolation(f"{architecture}: registers must be a non-empty tuple of names")
        for name in surface["required_callables"]:
            if not callable(getattr(module, name, None)):
                raise ContractViolation(f"{architecture}: adapter is missing callable '{name}'")
        if list(getattr(module, "branch_targets")({})) != []:
            raise ContractViolation(f"{architecture}: branch_targets must be empty for an instruction without a target")
        attribute = entry.get("adapter_error_attribute")
        if attribute is not None:
            error_type = getattr(module, attribute, None)
            if not isinstance(error_type, type) or not issubclass(error_type, ValueError):
                raise ContractViolation(f"{architecture}: {attribute} must derive from ValueError")
        results.append(
            f"{architecture} bits={info.bits} endianness={info.endianness} "
            f"registers={len(info.registers)} error={attribute or 'ValueError'} "
            f"classification={entry['classification']}"
        )
    return results


def check_host_contract_preconditions(ctx: ContractContext) -> list[str]:
    results = []
    for rule in ctx.contract["host_contract_preconditions"]:
        actual = _resolve(ctx.host_contract, rule["path"])
        if actual != rule["equals"]:
            raise ContractViolation(
                f"contracts/host_contract.json violates precondition {rule['path']} == {rule['equals']!r} (got {actual!r})"
            )
        results.append(f"{rule['path']}=={rule['equals']!r}")
    documents = {
        "host_contract": ctx.host_contract,
        "ir": ctx.ir,
        "sidecar": ctx.sidecar,
    }
    for rule in ctx.contract["cross_document_preconditions"]:
        left = _resolve(documents, rule["left"])
        right = _resolve(documents, rule["right"])
        if left != right:
            raise ContractViolation(f"cross-document precondition failed: {rule['left']}={left!r} != {rule['right']}={right!r}")
        results.append(f"{rule['left']}=={rule['right']}")
    return results


def check_sidecar_conformance(ctx: ContractContext) -> list[str]:
    spec = ctx.contract["execution_sidecar"]
    type_names = {"sha256": str, "int": int, "object": dict, "array": list, "str": str}
    results = []
    for key, type_name in sorted(spec["required_keys"].items()):
        if key not in ctx.sidecar:
            raise ContractViolation(f"execution sidecar is missing required key '{key}'")
        value = ctx.sidecar[key]
        expected = type_names[type_name]
        if expected is int and isinstance(value, bool):
            raise ContractViolation(f"sidecar '{key}' must not be a bool")
        if not isinstance(value, expected):
            raise ContractViolation(f"sidecar '{key}' must be {type_name}")
        if type_name == "sha256" and (len(value) != 64 or any(c not in "0123456789abcdef" for c in value)):
            raise ContractViolation(f"sidecar '{key}' is not a lowercase sha256 hex digest")
        results.append(f"{key}:{type_name}")
    allowed = set(spec["required_keys"]) | set(spec["optional_keys"])
    unknown = sorted(set(ctx.sidecar) - allowed)
    if unknown:
        raise ContractViolation(f"execution sidecar carries keys outside the contract: {unknown}")
    for segment in ctx.sidecar["memory_segments"]:
        missing = [key for key in spec["memory_segment_keys"] if key not in segment]
        if missing:
            raise ContractViolation(f"memory segment is missing keys: {missing}")
    for slot in ctx.sidecar["initial_state"]:
        declared = {item["id"] for item in ctx.ir["state_slots"]}
        if slot not in declared:
            raise ContractViolation(f"sidecar initial_state references undeclared slot '{slot}'")
    if ctx.sidecar["entry_state_slot"] not in {item["id"] for item in ctx.ir["state_slots"]}:
        raise ContractViolation("sidecar entry_state_slot is not declared by the IR")
    return results


def check_narrow_address_rule(ctx: ContractContext) -> list[str]:
    rule = ctx.contract["narrow_address_rule"]
    allowed = ctx.contract["allowed_address_bits"]
    required = rule["required_source_address_bits"]
    if required not in allowed:
        raise ContractViolation("narrow-address rule requires an address width outside frozen IR V1")
    if required < rule["applies_below_address_bits"]:
        raise ContractViolation("narrow-address rule is self-contradictory")
    narrow = []
    for architecture, entry in sorted(ctx.architectures.items()):
        module = importlib.import_module(entry["adapter_module"])
        if module.info.bits < rule["applies_below_address_bits"]:
            narrow.append(f"{architecture}:{module.info.bits}->i{required}")
    return [
        f"address_bits_allowed={allowed}",
        f"narrow_guests_modelled_at={required}",
        f"representation={rule['required_address_representation']}",
        "narrow_registered_architectures=" + (",".join(narrow) if narrow else "none"),
    ]


# ---------------------------------------------------------------------------
# chain proofs
# ---------------------------------------------------------------------------


def _run_frontend_chain(ctx: ContractContext, work: Path, *, expect_marker: str, stop_after: str | None = None) -> dict[str, Path]:
    entry = ctx.architectures["mips32-le"]
    proof = entry["chain_proof"]
    paths = {
        "ir": work / "fixture.a.ir.json",
        "sidecar": work / "fixture.a.sidecar.json",
        "frontend": work / "fixture.a.frontend.json",
        "reference": work / "reference.json",
        "module": work / "fixture.a.module.json",
        "core": work / "core.json",
    }
    hex_path = str(Path(proof["fixture_hex"]).as_posix())
    meta_path = str(Path(proof["fixture_meta"]).as_posix())
    contract_path = str(Path(proof["host_contract"]).as_posix())

    output = _run_tool(
        [
            proof["frontend"], hex_path, meta_path, contract_path,
            str(paths["ir"]), str(paths["sidecar"]), str(paths["frontend"]),
        ]
    )
    if "OPENRECOMP_MIPS32_FRONTEND_V1=PASS" not in output:
        raise ContractViolation("frontend did not report its pass marker")
    if stop_after == "frontend":
        return paths

    output = _run_tool(["tools/validate_ir_v1.py", str(paths["ir"])])
    if "OPENRECOMP_IR_V1_VALID=PASS" not in output:
        raise ContractViolation("normalized IR V1 did not validate")

    output = _run_tool([proof["reference"], hex_path, meta_path, str(paths["reference"])])
    if "OPENRECOMP_MIPS32_REFERENCE=PASS" not in output:
        raise ContractViolation("independent MIPS32 reference did not report its pass marker")

    output = _run_tool(
        [proof["packager"], str(paths["ir"]), str(paths["sidecar"]), contract_path, str(paths["module"])]
    )
    if expect_marker not in output:
        raise ContractViolation(f"packager did not report {expect_marker}")
    if stop_after == "package":
        return paths

    output = _run_tool([proof["module_validator"], str(paths["module"]), str(paths["ir"]), contract_path])
    if "OPENRECOMP_MODULE_V1_VALID=PASS" not in output:
        raise ContractViolation("Module Image V1 did not validate")

    output = _run_tool(
        [proof["core_runner"], str(paths["module"]), str(paths["ir"]), contract_path, meta_path, str(paths["core"])]
    )
    if "OPENRECOMP_MIPS32_CORE_API_V1=PASS" not in output:
        raise ContractViolation("Core API V1 execution did not report its pass marker")

    output = _run_tool(
        [
            proof["equivalence_checker"], meta_path, str(paths["frontend"]), str(paths["ir"]),
            str(paths["module"]), str(paths["reference"]), str(paths["core"]),
        ]
    )
    if "OPENRECOMP_MIPS32_VERTICAL_SLICE_V1=PASS" not in output:
        raise ContractViolation("reference/Core equivalence check did not pass")
    return paths


def chain_proof_frontend_fixture(ctx: ContractContext, entry: dict) -> dict:
    proof = entry["chain_proof"]
    published = proof["published_result"]
    with tempfile.TemporaryDirectory(prefix="openrecomp-contract-") as temp:
        paths = _run_frontend_chain(ctx, Path(temp), expect_marker="OPENRECOMP_MODULE_V1_PACKAGE=PASS")
        core = json.loads(paths["core"].read_text(encoding="utf-8"))
        reference = json.loads(paths["reference"].read_text(encoding="utf-8"))
        frontend_report = json.loads(paths["frontend"].read_text(encoding="utf-8"))
        module = json.loads(paths["module"].read_text(encoding="utf-8"))

    observed = {
        "checksum": core["checksum"],
        "memory_word": core["memory_word"],
        "operations": core["operations"],
        "return_v0": core["return_v0"],
    }
    expected = {key: published[key] for key in observed}
    if observed != expected:
        raise ContractViolation(f"Core API result {observed} does not match published {expected}")
    if reference["checksum"] != published["checksum"]:
        raise ContractViolation("independent reference checksum does not match the published value")
    if frontend_report["delay_slots_lowered"] != published["delay_slots"]:
        raise ContractViolation("frontend delay-slot count does not match the published value")
    if module["module_format_version"] != ctx.contract["module_format_version"]:
        raise ContractViolation("packaged module is not Module Image V1")
    return {
        "architecture": entry["architecture"],
        "chain": "fixture -> frontend -> IR V1 -> Module Image V1 -> Core API V1",
        "kind": proof["kind"],
        "result": observed,
    }


def chain_proof_prebuilt_module(ctx: ContractContext, entry: dict) -> dict:
    proof = entry["chain_proof"]
    ir_path = ROOT / proof["ir"]
    contract_path = ROOT / proof["host_contract"]
    ir_bytes = ir_path.read_bytes()
    contract_bytes = contract_path.read_bytes()
    ir = json.loads(ir_bytes)
    contract = json.loads(contract_bytes)
    if ir["ir_version"] != ctx.contract["normalized_ir_version"]:
        raise ContractViolation("prebuilt IR is not normalized IR V1")
    validate_document(ir)

    manifest = {
        "module_format_version": ctx.contract["module_format_version"],
        "module_id": ir["module_id"],
        "ir": {
            "version": ir["ir_version"],
            "sha256": _digest(ir_bytes),
            "source_input_sha256": ir["source"]["input_sha256"],
        },
        "host_contract": {
            "version": contract["contract_version"],
            "sha256": _digest(contract_bytes),
        },
        "memory": {"size_bytes": contract["memory"]["size_bytes"], "segments": []},
        "initial_state": [],
        "entry": {"function": ir["entry_function"], "observe_state_slot": proof["observe_state_slot"]},
        "limits": {"max_operations": 100, "max_call_depth": 8},
        "provenance": {
            "producer": "openrecomp.frontend-contract-v1-chain-proof",
            "source_input_sha256": ir["source"]["input_sha256"],
        },
    }
    module = ModuleImage.from_documents(
        manifest, ir, contract, ir_sha256=_digest(ir_bytes), contract_sha256=_digest(contract_bytes)
    )
    callbacks = {}
    for symbol, spec in proof["host_bindings"].items():
        if spec["kind"] != "sum_args":
            raise ContractViolation(f"unsupported host binding kind '{spec['kind']}' in contract")
        callbacks[symbol] = lambda args: sum(args)
    result = ReferenceExecutor(module, CallbackHostBinding(contract["contract_version"], callbacks)).run()
    observed = {"function_return": result.function_return, "observed_state": result.observed_state}
    if observed != proof["published_result"]:
        raise ContractViolation(f"prebuilt module result {observed} does not match {proof['published_result']}")
    return {
        "architecture": entry["architecture"],
        "chain": "prebuilt IR V1 -> Module Image V1 -> Core API V1",
        "kind": proof["kind"],
        "result": observed,
    }


CHAIN_PROOFS = {
    "frontend-fixture-chain": chain_proof_frontend_fixture,
    "prebuilt-ir-module": chain_proof_prebuilt_module,
}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic contract report here")
    args = parser.parse_args(argv[1:])

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    record: dict = {
        "checks": [],
        "contract_id": contract["contract_id"],
        "contract_version": contract["contract_version"],
        "normalized_ir_version": contract["normalized_ir_version"],
        "schema_version": "1.0.0",
    }

    def add(kind: str, check_id: str, action) -> bool:
        try:
            detail = action()
        except (
            ContractViolation,
            CoreRuntimeError,
            ModuleError,
            OSError,
            KeyError,
            ImportError,
            AttributeError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            record["checks"].append({"detail": f"{type(exc).__name__}: {exc}", "id": check_id, "kind": kind, "status": "FAIL"})
            return False
        if isinstance(detail, list):
            detail = "; ".join(str(item) for item in detail)
        record["checks"].append({"detail": str(detail), "id": check_id, "kind": kind, "status": "PASS"})
        return True

    try:
        ctx = ContractContext(contract)
    except Exception as exc:  # noqa: BLE001 - contract setup failure is itself the finding
        record["checks"].append(
            {"detail": f"{type(exc).__name__}: {exc}", "id": "contract-context", "kind": "setup", "status": "FAIL"}
        )
        ctx = None

    if ctx is not None:
        declared = [rule["probe"] for rule in contract["lowering_rules"]]
        add("anti-drift", "probes-declared-and-implemented", lambda: _check_probe_registry(contract))
        add("structural", "adapter-surface", lambda: check_adapter_surface(ctx))
        add("structural", "host-contract-preconditions", lambda: check_host_contract_preconditions(ctx))
        add("structural", "execution-sidecar-conformance", lambda: check_sidecar_conformance(ctx))
        add("structural", "narrow-address-rule", lambda: check_narrow_address_rule(ctx))
        for rule in contract["lowering_rules"]:
            add("probe", rule["id"], lambda rule=rule: PROBES[rule["probe"]](ctx))
        for architecture, entry in sorted(ctx.architectures.items()):
            proof = entry.get("chain_proof")
            if proof is None:
                continue
            handler = CHAIN_PROOFS.get(proof["kind"])
            if handler is None:
                add("chain-proof", architecture, _unsupported_kind(proof["kind"]))
                continue
            add("chain-proof", architecture, lambda handler=handler, entry=entry: _describe_chain(handler(ctx, entry)))

    failures = [item for item in record["checks"] if item["status"] != "PASS"]
    for item in record["checks"]:
        print(f"{item['status']:<5} {item['kind']:<12} {item['id']:<44} {item['detail']}")

    record["status"] = "FAIL" if failures else "PASS"
    record["totals"] = {
        "chain_proofs": sum(1 for item in record["checks"] if item["kind"] == "chain-proof" and item["status"] == "PASS"),
        "fail": len(failures),
        "pass": len(record["checks"]) - len(failures),
        "probes": sum(1 for item in record["checks"] if item["kind"] == "probe"),
    }
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_serialize(record), encoding="utf-8")
        print(f"OPENRECOMP_FRONTEND_CONTRACT_JSON={out.name}")

    totals = record["totals"]
    print(
        "OPENRECOMP_FRONTEND_CONTRACT_CHECKS=%d PROBES=%d CHAIN_PROOFS=%d FAIL=%d"
        % (totals["pass"] + totals["fail"], totals["probes"], totals["chain_proofs"], totals["fail"])
    )
    if failures:
        print("OPENRECOMP_FRONTEND_CONTRACT_V1=FAIL")
        return 1
    print("OPENRECOMP_FRONTEND_CONTRACT_V1=PASS")
    return 0


def _check_probe_registry(contract: dict) -> str:
    declared = {rule["probe"] for rule in contract["lowering_rules"]}
    unimplemented = sorted(declared - set(PROBES))
    if unimplemented:
        raise ContractViolation(f"contract declares probes with no implementation: {unimplemented}")
    unused = sorted(set(PROBES) - declared)
    if unused:
        raise ContractViolation(f"implemented probes are not declared by the contract: {unused}")
    return f"{len(declared)} declared probes all implemented, no undeclared probe"


def _unsupported_kind(kind: str):
    def action():
        raise ContractViolation(f"unsupported chain proof kind '{kind}'")

    return action


def _describe_chain(proof: dict) -> str:
    return f"[{proof['kind']}] {proof['chain']} result={json.dumps(proof['result'], sort_keys=True)}"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
