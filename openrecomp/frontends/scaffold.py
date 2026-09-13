"""Architecture-neutral scaffolding for guest-architecture frontends.

Implements the executable frontend contract
(`contracts/frontend_contract_v1.json`, `docs/FRONTEND_CONTRACT_V1.md`) as
reusable fail-closed helpers for new guest frontends (SM83, Z80,
6502-family). The established RV32I and MIPS32 paths do not depend on this
module; it is strictly additive.

Rules enforced here mirror the authoritative gates (`tools/validate_ir_v1.py`,
`openrecomp/executor.py`, `openrecomp/module.py`) and are documented in the
contract:

- decode dictionaries are validated fail-closed (address/op/word shape);
- every emitted document is re-validated with `validate_document` before it is
  returned, so a scaffolding-built document can never bypass frozen IR V1;
- constant shift counts must be normalized (< result width) because the Core
  API executor faults on any unnormalized runtime shift; variable shift
  amounts are allowed but remain the caller's obligation to normalize;
- state slots, function ids, block ids and result ids are unique and well
  formed; operands only reference already-defined results;
- every block ends in exactly one terminator;
- memory segments are in-range and non-overlapping;
- the entry function, observe slot and initial state reference declared
  objects.

Nothing here knows a guest ISA; per-ISA knowledge (prefixes, flags, cycle
costs, mnemonic encodings) belongs in `adapters/<architecture>.py` and
`tools/<architecture>_frontend_v1.py`.
"""
from __future__ import annotations

import re
from typing import Any

from openrecomp.runtime import TYPE_BITS

from tools.validate_ir_v1 import validate_document

ALLOWED_TYPES = frozenset(TYPE_BITS)
BINOP_KINDS = frozenset({"add", "sub", "mul", "and", "or", "xor", "shl", "lshr", "ashr"})
SHIFT_KINDS = frozenset({"shl", "lshr", "ashr"})
CAST_KINDS = frozenset({"zext", "sext", "trunc", "bitcast"})
PREDICATES = frozenset({"eq", "ne", "ult", "ule", "ugt", "uge", "slt", "sle", "sgt", "sge"})
ID_PATTERN = re.compile(r"^[A-Za-z_%.][A-Za-z0-9_%.:-]*$")
ALLOWED_ADDRESS_BITS = frozenset({32, 64})
ALLOWED_ENDIANNESS = frozenset({"little", "big"})
IR_VERSION = "1.0.0"


class ScaffoldError(ValueError):
    """Fail-closed violation of the frontend contract in a scaffolding call."""


def _check_id(value: Any, where: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.match(value):
        raise ScaffoldError(f"{where}: {value!r} is not a valid IR identifier")
    return value


def _check_type(type_name: Any, where: str) -> str:
    if type_name not in ALLOWED_TYPES:
        raise ScaffoldError(f"{where}: unsupported integer type {type_name!r}")
    return type_name


def validate_decode(insn: dict, *, address_bits: int = 32, where: str = "decode") -> dict:
    """Validate a decoder result against the contract's decode shape.

    Fails closed on a non-dict result, an address outside the guest address
    space, a missing/empty op name, or a non-integer negative instruction
    word. Returns the instruction unchanged.
    """
    if not isinstance(insn, dict):
        raise ScaffoldError(f"{where}: decoder returned {type(insn).__name__}, expected dict")
    address = insn.get("address")
    if isinstance(address, bool) or not isinstance(address, int) or address < 0 or address >= (1 << address_bits):
        raise ScaffoldError(f"{where}: instruction address {address!r} is outside the {address_bits}-bit address space")
    op = insn.get("op")
    if not isinstance(op, str) or not op:
        raise ScaffoldError(f"{where}: decoded instruction has no non-empty op name")
    word = insn.get("word")
    if word is not None and (isinstance(word, bool) or not isinstance(word, int) or word < 0):
        raise ScaffoldError(f"{where}: instruction word {word!r} must be a non-negative integer")
    return insn


class IRBuilder:
    """Assembles a normalized IR V1 document and its execution sidecar."""

    def __init__(
        self,
        *,
        module_id: str,
        architecture: str,
        adapter: str,
        address_bits: int,
        endianness: str,
        input_sha256: str,
        host_contract_version: str,
        required_features: tuple[str, ...] = ("core-v1",),
        required_host_symbols: tuple[str, ...] = (),
    ) -> None:
        _check_id(module_id, "module_id")
        if not isinstance(architecture, str) or not architecture:
            raise ScaffoldError("architecture must be a non-empty string")
        if not isinstance(adapter, str) or not adapter:
            raise ScaffoldError("adapter must be a non-empty string")
        if address_bits not in ALLOWED_ADDRESS_BITS:
            raise ScaffoldError(f"address_bits must be one of {sorted(ALLOWED_ADDRESS_BITS)}")
        if endianness not in ALLOWED_ENDIANNESS:
            raise ScaffoldError(f"endianness must be one of {sorted(ALLOWED_ENDIANNESS)}")
        if not isinstance(input_sha256, str) or len(input_sha256) != 64:
            raise ScaffoldError("input_sha256 must be a 64-character hex digest")
        if not isinstance(host_contract_version, str) or not host_contract_version:
            raise ScaffoldError("host_contract_version must be a non-empty string")
        for feature in required_features:
            _check_id(feature, "required_features")
        for symbol in required_host_symbols:
            _check_id(symbol, "required_host_symbols")

        self.module_id = module_id
        self.architecture = architecture
        self.adapter = adapter
        self.address_bits = address_bits
        self.address_type = f"i{address_bits}"
        self.endianness = endianness
        self.input_sha256 = input_sha256
        self.host_contract_version = host_contract_version
        self.required_features = list(required_features)
        self.required_host_symbols = list(required_host_symbols)
        self._state_types: dict[str, str] = {}
        self._functions: dict[str, _FunctionBuilder] = {}
        self._function_order: list[str] = []
        self._segments: list[dict[str, Any]] = []

    # -- state -----------------------------------------------------------
    def declare_state_slot(self, slot_id: str, type_name: str) -> None:
        _check_id(slot_id, "state slot id")
        _check_type(type_name, f"state slot {slot_id}")
        if slot_id in self._state_types:
            raise ScaffoldError(f"duplicate state slot {slot_id}")
        self._state_types[slot_id] = type_name

    # -- functions -------------------------------------------------------
    def add_function(
        self,
        function_id: str,
        guest_address: int,
        *,
        params: tuple[tuple[str, str], ...] = (),
        return_type: str | None = None,
    ) -> "_FunctionBuilder":
        _check_id(function_id, "function id")
        if isinstance(guest_address, bool) or not isinstance(guest_address, int) or guest_address < 0:
            raise ScaffoldError(f"{function_id}: guest address must be a non-negative integer")
        if function_id in self._functions:
            raise ScaffoldError(f"duplicate function id {function_id}")
        if return_type is not None:
            _check_type(return_type, f"{function_id} return type")
        builder = _FunctionBuilder(self, function_id, guest_address, params, return_type)
        self._functions[function_id] = builder
        self._function_order.append(function_id)
        return builder

    # -- memory ----------------------------------------------------------
    def add_memory_segment(self, name: str, guest_address: int, data: bytes, *, memory_size_bytes: int) -> None:
        _check_id(name, "memory segment name")
        if isinstance(guest_address, bool) or not isinstance(guest_address, int) or guest_address < 0:
            raise ScaffoldError(f"segment {name}: guest address must be a non-negative integer")
        if not isinstance(data, (bytes, bytearray)):
            raise ScaffoldError(f"segment {name}: data must be bytes")
        if guest_address + len(data) > memory_size_bytes:
            raise ScaffoldError(f"segment {name} exceeds the declared memory size")
        self._segments.append({"name": name, "guest_address": guest_address, "data": bytes(data)})

    # -- assembly --------------------------------------------------------
    def build(
        self,
        *,
        entry_function: str,
        memory_size_bytes: int,
        initial_state: dict[str, int],
        observe_state_slot: str,
        max_operations: int,
    ) -> tuple[dict, dict]:
        """Assemble and validate the IR document plus its execution sidecar."""
        _check_id(entry_function, "entry function")
        _check_id(observe_state_slot, "observe state slot")
        if entry_function not in self._functions:
            raise ScaffoldError(f"entry function {entry_function} is not declared")
        if observe_state_slot not in self._state_types:
            raise ScaffoldError(f"observe state slot {observe_state_slot} is not declared")
        if isinstance(memory_size_bytes, bool) or not isinstance(memory_size_bytes, int) or memory_size_bytes <= 0:
            raise ScaffoldError("memory_size_bytes must be a positive integer")
        if isinstance(max_operations, bool) or not isinstance(max_operations, int) or max_operations <= 0:
            raise ScaffoldError("max_operations must be a positive integer")

        for slot, value in initial_state.items():
            if slot not in self._state_types:
                raise ScaffoldError(f"initial state references undeclared slot {slot}")
            bits = TYPE_BITS[self._state_types[slot]]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value >= (1 << bits):
                raise ScaffoldError(f"initial value {value} does not fit slot {slot}")

        start = 0
        for segment in sorted(self._segments, key=lambda item: (item["guest_address"], item["name"])):
            if segment["guest_address"] < start:
                raise ScaffoldError(f"memory segments overlap or are out of order at {segment['name']}")
            start = segment["guest_address"] + len(segment["data"])

        functions = []
        for function_id in self._function_order:
            functions.append(self._functions[function_id].finish())

        ir = {
            "ir_version": IR_VERSION,
            "module_id": self.module_id,
            "source": {
                "architecture": self.architecture,
                "adapter": self.adapter,
                "address_bits": self.address_bits,
                "endianness": self.endianness,
                "input_sha256": self.input_sha256,
            },
            "required_features": list(self.required_features),
            "host_contract_version": self.host_contract_version,
            "required_host_symbols": list(self.required_host_symbols),
            "state_slots": [
                {"id": slot_id, "type": type_name}
                for slot_id, type_name in self._state_types.items()
            ],
            "entry_function": entry_function,
            "functions": functions,
        }
        try:
            validate_document(ir)
        except ValueError as exc:
            raise ScaffoldError(f"assembled IR failed validation: {exc}") from exc

        sidecar = {
            "frontend_version": IR_VERSION,
            "source_input_sha256": self.input_sha256,
            "memory_size_bytes": memory_size_bytes,
            "initial_state": dict(sorted(initial_state.items())),
            "memory_segments": [
                {"name": item["name"], "guest_address": item["guest_address"], "data_hex": item["data"].hex()}
                for item in sorted(self._segments, key=lambda entry: (entry["guest_address"], entry["name"]))
            ],
            "entry_state_slot": observe_state_slot,
            "max_operations": max_operations,
        }
        return ir, sidecar


class _FunctionBuilder:
    def __init__(
        self,
        owner: IRBuilder,
        function_id: str,
        guest_address: int,
        params: tuple[tuple[str, str], ...],
        return_type: str | None,
    ) -> None:
        self.owner = owner
        self.function_id = function_id
        self.guest_address = guest_address
        self.return_type = return_type
        self.params: list[dict[str, str]] = []
        self.defined_types: dict[str, str] = {}
        for param_id, type_name in params:
            _check_id(param_id, f"{function_id} param id")
            _check_type(type_name, f"{function_id} param {param_id}")
            if param_id in self.defined_types:
                raise ScaffoldError(f"{function_id}: duplicate param id {param_id}")
            self.params.append({"id": param_id, "type": type_name})
            self.defined_types[param_id] = type_name
        self._blocks: dict[str, _BlockBuilder] = {}
        self._block_order: list[str] = []

    def add_block(self, block_id: str, guest_address: int) -> "_BlockBuilder":
        _check_id(block_id, f"{self.function_id} block id")
        if isinstance(guest_address, bool) or not isinstance(guest_address, int) or guest_address < 0:
            raise ScaffoldError(f"{self.function_id}: block guest address must be a non-negative integer")
        if block_id in self._blocks:
            raise ScaffoldError(f"{self.function_id}: duplicate block id {block_id}")
        block = _BlockBuilder(self, block_id, guest_address)
        self._blocks[block_id] = block
        self._block_order.append(block_id)
        return block

    def define_result(self, result_id: str, type_name: str) -> None:
        _check_id(result_id, f"{self.function_id} result id")
        _check_type(type_name, f"{self.function_id} result {result_id}")
        if result_id in self.defined_types:
            raise ScaffoldError(f"{self.function_id}: duplicate result id {result_id}")
        self.defined_types[result_id] = type_name

    def finish(self) -> dict:
        blocks = []
        for block_id in self._block_order:
            blocks.append(self._blocks[block_id].finish())
        return {
            "id": self.function_id,
            "guest_address": self.guest_address,
            "params": self.params,
            "return_type": self.return_type,
            "blocks": blocks,
        }


class _BlockBuilder:
    def __init__(self, owner: _FunctionBuilder, block_id: str, guest_address: int) -> None:
        self.owner = owner
        self.builder = owner.owner
        self.block_id = block_id
        self.guest_address = guest_address
        self.instructions: list[dict] = []
        self.terminator: dict | None = None

    # -- operand helpers -------------------------------------------------
    def value(self, result_id: str) -> dict:
        _check_id(result_id, f"{self.block_id} operand")
        if result_id not in self.owner.defined_types:
            raise ScaffoldError(f"{self.function_id}: operand references undefined value {result_id}")
        return {"value": result_id}

    def const(self, value: int, type_name: str) -> dict:
        _check_type(type_name, f"{self.function_id} constant")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ScaffoldError(f"{self.function_id}: constant must be a non-negative integer")
        if value >= (1 << TYPE_BITS[type_name]):
            raise ScaffoldError(f"{self.function_id}: constant {value} does not fit {type_name}")
        return {"const": value, "type": type_name}

    @property
    def function_id(self) -> str:
        return self.owner.function_id

    def _operand(self, operand: dict, where: str) -> tuple[str, str]:
        if not isinstance(operand, dict):
            raise ScaffoldError(f"{where}: operand must be a dict")
        if "value" in operand:
            _check_id(operand["value"], f"{where} operand")
            type_name = self.owner.defined_types.get(operand["value"])
            if type_name is None:
                raise ScaffoldError(f"{where}: operand references undefined value {operand['value']}")
            return type_name, operand["value"]
        if "const" in operand:
            if "type" not in operand:
                raise ScaffoldError(f"{where}: constant operand lacks a type")
            _check_type(operand["type"], f"{where} constant operand")
            value = operand["const"]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ScaffoldError(f"{where}: constant must be a non-negative integer")
            if value >= (1 << TYPE_BITS[operand["type"]]):
                raise ScaffoldError(f"{where}: constant {value} does not fit {operand['type']}")
            return operand["type"], None
        raise ScaffoldError(f"{where}: operand must be a value or a typed constant")

    def _emit(self, instruction: dict) -> None:
        if self.terminator is not None:
            raise ScaffoldError(f"{self.function_id}/{self.block_id}: instruction emitted after terminator")
        self.instructions.append(instruction)

    def _set_terminator(self, terminator: dict) -> None:
        if self.terminator is not None:
            raise ScaffoldError(f"{self.function_id}/{self.block_id}: duplicate terminator")
        self.terminator = terminator

    # -- instructions ----------------------------------------------------
    def const_result(self, result: str, result_type: str, value: int) -> None:
        self.owner.define_result(result, result_type)
        self._emit(
            {
                "op": "const",
                "result": result,
                "result_type": result_type,
                "value": value,
                "source_address": self.guest_address,
            }
        )

    def read_state(self, result: str, slot: str) -> None:
        type_name = self.builder._state_types.get(slot)
        if type_name is None:
            raise ScaffoldError(f"{self.function_id}: read from undeclared state slot {slot}")
        self.owner.define_result(result, type_name)
        self._emit(
            {
                "op": "read_state",
                "result": result,
                "result_type": type_name,
                "slot": slot,
                "source_address": self.guest_address,
            }
        )

    def write_state(self, slot: str, value: dict) -> None:
        slot_type = self.builder._state_types.get(slot)
        if slot_type is None:
            raise ScaffoldError(f"{self.function_id}: write to undeclared state slot {slot}")
        value_type, _ = self._operand(value, "write_state")
        if value_type != slot_type:
            raise ScaffoldError(
                f"{self.function_id}: write_state value type {value_type} does not match slot {slot} ({slot_type})"
            )
        self._emit({"op": "write_state", "slot": slot, "value": value, "source_address": self.guest_address})

    def binop(self, result: str, result_type: str, kind: str, lhs: dict, rhs: dict) -> None:
        _check_type(result_type, "binop result type")
        if kind not in BINOP_KINDS:
            raise ScaffoldError(f"{self.function_id}: unsupported binop kind {kind}")
        lhs_type, _ = self._operand(lhs, "binop lhs")
        rhs_type, _ = self._operand(rhs, "binop rhs")
        if lhs_type != result_type or rhs_type != result_type:
            raise ScaffoldError(f"{self.function_id}: binop operands must match result type {result_type}")
        if kind in SHIFT_KINDS and "const" in rhs and rhs["const"] >= TYPE_BITS[result_type]:
            raise ScaffoldError(
                f"{self.function_id}: unnormalized {kind} count {rhs['const']} for {result_type} "
                "(frontend contract: shift counts must be normalized)"
            )
        self.owner.define_result(result, result_type)
        self._emit(
            {
                "op": "binop",
                "result": result,
                "result_type": result_type,
                "kind": kind,
                "lhs": lhs,
                "rhs": rhs,
                "source_address": self.guest_address,
            }
        )

    def compare(self, result: str, predicate: str, lhs: dict, rhs: dict) -> None:
        if predicate not in PREDICATES:
            raise ScaffoldError(f"{self.function_id}: unsupported predicate {predicate}")
        lhs_type, _ = self._operand(lhs, "compare lhs")
        rhs_type, _ = self._operand(rhs, "compare rhs")
        if lhs_type != rhs_type:
            raise ScaffoldError(f"{self.function_id}: compare operands must have the same type")
        self.owner.define_result(result, "i1")
        self._emit(
            {
                "op": "compare",
                "result": result,
                "result_type": "i1",
                "predicate": predicate,
                "lhs": lhs,
                "rhs": rhs,
                "source_address": self.guest_address,
            }
        )

    def cast(self, result: str, result_type: str, kind: str, value: dict) -> None:
        _check_type(result_type, "cast result type")
        if kind not in CAST_KINDS:
            raise ScaffoldError(f"{self.function_id}: unsupported cast kind {kind}")
        source_type, _ = self._operand(value, "cast value")
        source_bits = TYPE_BITS[source_type]
        result_bits = TYPE_BITS[result_type]
        if kind in {"zext", "sext"} and result_bits <= source_bits:
            raise ScaffoldError(f"{self.function_id}: {kind} must increase width")
        if kind == "trunc" and result_bits >= source_bits:
            raise ScaffoldError(f"{self.function_id}: trunc must decrease width")
        if kind == "bitcast" and result_bits != source_bits:
            raise ScaffoldError(f"{self.function_id}: bitcast must preserve width")
        self.owner.define_result(result, result_type)
        self._emit(
            {
                "op": "cast",
                "result": result,
                "result_type": result_type,
                "kind": kind,
                "value": value,
                "source_address": self.guest_address,
            }
        )

    def zext_to_address(self, result: str, value: dict) -> None:
        """Zero-extend a narrow guest value to the exact IR address type.

        Narrow-address guests (SM83/Z80/6502-family) carry addresses in the
        width of `source.address_bits` (32). This is the contract's
        `narrow_address_rule` helper.
        """
        source_type, _ = self._operand(value, "zext_to_address value")
        if TYPE_BITS[source_type] >= self.builder.address_bits:
            raise ScaffoldError(f"{self.function_id}: value is already as wide as the address type")
        self.cast(result, self.builder.address_type, "zext", value)

    def select(self, result: str, result_type: str, condition: dict, if_true: dict, if_false: dict) -> None:
        _check_type(result_type, "select result type")
        cond_type, _ = self._operand(condition, "select condition")
        if cond_type != "i1":
            raise ScaffoldError(f"{self.function_id}: select condition must be i1")
        yes_type, _ = self._operand(if_true, "select if_true")
        no_type, _ = self._operand(if_false, "select if_false")
        if yes_type != result_type or no_type != result_type:
            raise ScaffoldError(f"{self.function_id}: select arms must match result type {result_type}")
        self.owner.define_result(result, result_type)
        self._emit(
            {
                "op": "select",
                "result": result,
                "result_type": result_type,
                "condition": condition,
                "if_true": if_true,
                "if_false": if_false,
                "source_address": self.guest_address,
            }
        )

    def load(self, result: str, result_type: str, *, width_bits: int, signed: bool, address: dict, alignment: int) -> None:
        _check_type(result_type, "load result type")
        if width_bits not in {8, 16, 32, 64}:
            raise ScaffoldError(f"{self.function_id}: unsupported load width {width_bits}")
        if TYPE_BITS[result_type] < width_bits:
            raise ScaffoldError(f"{self.function_id}: load result is narrower than the access")
        if alignment not in {1, 2, 4, 8} or alignment > width_bits // 8:
            raise ScaffoldError(f"{self.function_id}: alignment exceeds the access width")
        address_type, _ = self._operand(address, "load address")
        if address_type != self.builder.address_type:
            raise ScaffoldError(
                f"{self.function_id}: load address must be {self.builder.address_type}, got {address_type}"
            )
        self.owner.define_result(result, result_type)
        self._emit(
            {
                "op": "load",
                "result": result,
                "result_type": result_type,
                "width_bits": width_bits,
                "signed": bool(signed),
                "address": address,
                "alignment": alignment,
                "misaligned_policy": "fault",
                "source_address": self.guest_address,
            }
        )

    def store(self, *, width_bits: int, address: dict, value: dict, alignment: int) -> None:
        if width_bits not in {8, 16, 32, 64}:
            raise ScaffoldError(f"{self.function_id}: unsupported store width {width_bits}")
        if alignment not in {1, 2, 4, 8} or alignment > width_bits // 8:
            raise ScaffoldError(f"{self.function_id}: alignment exceeds the access width")
        address_type, _ = self._operand(address, "store address")
        if address_type != self.builder.address_type:
            raise ScaffoldError(
                f"{self.function_id}: store address must be {self.builder.address_type}, got {address_type}"
            )
        value_type, _ = self._operand(value, "store value")
        if TYPE_BITS[value_type] != width_bits:
            raise ScaffoldError(f"{self.function_id}: store value width must equal the access width")
        self._emit(
            {
                "op": "store",
                "width_bits": width_bits,
                "address": address,
                "value": value,
                "alignment": alignment,
                "misaligned_policy": "fault",
                "source_address": self.guest_address,
            }
        )

    def call(self, callee: str, args: list[dict], *, result: str | None = None, result_type: str | None = None) -> None:
        _check_id(callee, "call callee")
        if (result is None) != (result_type is None):
            raise ScaffoldError(f"{self.function_id}: call result and result_type must appear together")
        for arg in args:
            self._operand(arg, "call argument")
        if result is not None:
            self.owner.define_result(result, result_type)
        instruction: dict = {"op": "call", "callee": callee, "args": args, "source_address": self.guest_address}
        if result is not None:
            instruction["result"] = result
            instruction["result_type"] = result_type
        self._emit(instruction)

    def host_call(self, symbol: str, args: list[dict], *, result: str | None = None, result_type: str | None = None) -> None:
        _check_id(symbol, "host_call symbol")
        if symbol not in self.builder.required_host_symbols:
            raise ScaffoldError(f"{self.function_id}: host symbol {symbol} is not declared")
        if (result is None) != (result_type is None):
            raise ScaffoldError(f"{self.function_id}: host_call result and result_type must appear together")
        for arg in args:
            self._operand(arg, "host_call argument")
        if result is not None:
            self.owner.define_result(result, result_type)
        instruction: dict = {"op": "host_call", "symbol": symbol, "args": args, "source_address": self.guest_address}
        if result is not None:
            instruction["result"] = result
            instruction["result_type"] = result_type
        self._emit(instruction)

    # -- terminators -----------------------------------------------------
    def jump(self, target: str) -> None:
        _check_id(target, "jump target")
        self._set_terminator({"op": "jump", "target": target, "source_address": self.guest_address})

    def branch(self, condition: dict, target_true: str, target_false: str) -> None:
        condition_type, _ = self._operand(condition, "branch condition")
        if condition_type != "i1":
            raise ScaffoldError(f"{self.function_id}: branch condition must be i1")
        _check_id(target_true, "branch target_true")
        _check_id(target_false, "branch target_false")
        self._set_terminator(
            {
                "op": "branch",
                "condition": condition,
                "target_true": target_true,
                "target_false": target_false,
                "source_address": self.guest_address,
            }
        )

    def ret(self, value: dict | None = None) -> None:
        if self.owner.return_type is None:
            if value is not None:
                raise ScaffoldError(f"{self.function_id}: void function cannot return a value")
        else:
            if value is None:
                raise ScaffoldError(f"{self.function_id}: non-void function must return a value")
            value_type, _ = self._operand(value, "return value")
            if value_type != self.owner.return_type:
                raise ScaffoldError(
                    f"{self.function_id}: return type {value_type} does not match {self.owner.return_type}"
                )
        terminator: dict = {"op": "return", "source_address": self.guest_address}
        if value is not None:
            terminator["value"] = value
        self._set_terminator(terminator)

    def indirect_jump(self, target: dict, candidate_blocks: list[str]) -> None:
        target_type, _ = self._operand(target, "indirect_jump target")
        if target_type != self.builder.address_type:
            raise ScaffoldError(
                f"{self.function_id}: indirect jump target must be {self.builder.address_type}, got {target_type}"
            )
        if not candidate_blocks or len(set(candidate_blocks)) != len(candidate_blocks):
            raise ScaffoldError(f"{self.function_id}: candidate_blocks must be non-empty and unique")
        for block_id in candidate_blocks:
            _check_id(block_id, "indirect_jump candidate")
        self._set_terminator(
            {
                "op": "indirect_jump",
                "target": target,
                "candidate_blocks": list(candidate_blocks),
                "source_address": self.guest_address,
            }
        )

    def trap(self, reason: str) -> None:
        if not isinstance(reason, str) or not reason:
            raise ScaffoldError(f"{self.function_id}: trap requires a non-empty reason")
        self._set_terminator({"op": "trap", "reason": reason, "source_address": self.guest_address})

    def finish(self) -> dict:
        if self.terminator is None:
            raise ScaffoldError(f"{self.function_id}/{self.block_id}: block has no terminator")
        return {
            "id": self.block_id,
            "guest_address": self.guest_address,
            "instructions": self.instructions,
            "terminator": self.terminator,
        }
