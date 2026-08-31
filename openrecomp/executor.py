from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .module import ModuleImage
from .runtime import (
    CoreRuntimeError,
    GuestMemory,
    GuestState,
    HostBinding,
    TYPE_BITS,
    mask_for,
    signed_value,
)


@dataclass(frozen=True)
class ExecutionResult:
    function_return: int | None
    observed_state: int
    operations: int
    state: dict[str, int]
    host: dict[str, Any]


class ReferenceExecutor:
    """Architecture-neutral executable semantics for normalized OpenRecomp IR V1."""

    def __init__(self, module: ModuleImage, host: HostBinding):
        self.module = module
        self.ir = module.ir
        self.host = host

        if host.contract_version != self.ir["host_contract_version"]:
            raise CoreRuntimeError("host binding contract version mismatch")
        missing = sorted(set(self.ir["required_host_symbols"]) - set(host.symbols))
        if missing:
            raise CoreRuntimeError("missing host binding(s): " + ", ".join(missing))

        self.state = GuestState(self.ir["state_slots"], module.initial_state)
        self.memory = GuestMemory(
            module.memory_size_bytes,
            module.memory_segments,
            self.ir["source"]["endianness"],
        )
        self.functions = {function["id"]: function for function in self.ir["functions"]}
        self.operations = 0

    def _step(self) -> None:
        self.operations += 1
        if self.operations > self.module.limits.max_operations:
            raise CoreRuntimeError("operation limit exceeded")

    @staticmethod
    def _value(operand: dict[str, Any], values: dict[str, tuple[int, str]]) -> tuple[int, str]:
        if "value" in operand:
            try:
                return values[operand["value"]]
            except KeyError as exc:
                raise CoreRuntimeError(f"undefined runtime value {operand['value']}") from exc
        return operand["const"] & mask_for(operand["type"]), operand["type"]

    def _address(self, operand: dict[str, Any], values: dict[str, tuple[int, str]]) -> int:
        value, type_name = self._value(operand, values)
        expected = f"i{self.ir['source']['address_bits']}"
        if type_name != expected:
            raise CoreRuntimeError(f"memory address has type {type_name}, expected {expected}")
        return value

    def _execute_instruction(
        self,
        insn: dict[str, Any],
        values: dict[str, tuple[int, str]],
        depth: int,
    ) -> None:
        self._step()
        op = insn["op"]
        result: int | None = None

        if op == "const":
            result = insn["value"]

        elif op == "read_state":
            result = self.state.read(insn["slot"])

        elif op == "write_state":
            value, _ = self._value(insn["value"], values)
            self.state.write(insn["slot"], value)
            return

        elif op == "binop":
            lhs, _ = self._value(insn["lhs"], values)
            rhs, _ = self._value(insn["rhs"], values)
            bits = TYPE_BITS[insn["result_type"]]
            mask = (1 << bits) - 1
            kind = insn["kind"]
            if kind == "add":
                result = lhs + rhs
            elif kind == "sub":
                result = lhs - rhs
            elif kind == "mul":
                result = lhs * rhs
            elif kind == "and":
                result = lhs & rhs
            elif kind == "or":
                result = lhs | rhs
            elif kind == "xor":
                result = lhs ^ rhs
            elif kind in {"shl", "lshr", "ashr"}:
                if rhs >= bits:
                    raise CoreRuntimeError(f"shift count {rhs} is not normalized for {insn['result_type']}")
                if kind == "shl":
                    result = lhs << rhs
                elif kind == "lshr":
                    result = lhs >> rhs
                else:
                    result = signed_value(lhs, bits) >> rhs
            else:
                raise CoreRuntimeError(f"unsupported binop {kind}")
            result &= mask

        elif op == "compare":
            lhs, lhs_type = self._value(insn["lhs"], values)
            rhs, _ = self._value(insn["rhs"], values)
            bits = TYPE_BITS[lhs_type]
            predicate = insn["predicate"]
            if predicate == "eq":
                flag = lhs == rhs
            elif predicate == "ne":
                flag = lhs != rhs
            elif predicate == "ult":
                flag = lhs < rhs
            elif predicate == "ule":
                flag = lhs <= rhs
            elif predicate == "ugt":
                flag = lhs > rhs
            elif predicate == "uge":
                flag = lhs >= rhs
            elif predicate == "slt":
                flag = signed_value(lhs, bits) < signed_value(rhs, bits)
            elif predicate == "sle":
                flag = signed_value(lhs, bits) <= signed_value(rhs, bits)
            elif predicate == "sgt":
                flag = signed_value(lhs, bits) > signed_value(rhs, bits)
            elif predicate == "sge":
                flag = signed_value(lhs, bits) >= signed_value(rhs, bits)
            else:
                raise CoreRuntimeError(f"unsupported predicate {predicate}")
            result = 1 if flag else 0

        elif op == "cast":
            value, source_type = self._value(insn["value"], values)
            source_bits = TYPE_BITS[source_type]
            result_bits = TYPE_BITS[insn["result_type"]]
            kind = insn["kind"]
            if kind == "zext":
                result = value
            elif kind == "sext":
                result = signed_value(value, source_bits)
            elif kind in {"trunc", "bitcast"}:
                result = value
            else:
                raise CoreRuntimeError(f"unsupported cast {kind}")
            result &= (1 << result_bits) - 1

        elif op == "select":
            condition, _ = self._value(insn["condition"], values)
            selected = insn["if_true"] if condition else insn["if_false"]
            result, _ = self._value(selected, values)

        elif op == "load":
            result = self.memory.load(
                self._address(insn["address"], values),
                width_bits=insn["width_bits"],
                result_type=insn["result_type"],
                signed=insn["signed"],
                alignment=insn["alignment"],
                misaligned_policy=insn["misaligned_policy"],
            )

        elif op == "store":
            value, _ = self._value(insn["value"], values)
            self.memory.store(
                self._address(insn["address"], values),
                value,
                width_bits=insn["width_bits"],
                alignment=insn["alignment"],
                misaligned_policy=insn["misaligned_policy"],
            )
            return

        elif op == "call":
            args = [self._value(arg, values)[0] for arg in insn["args"]]
            returned = self.execute_function(insn["callee"], args, depth + 1)
            if "result" not in insn:
                return
            if returned is None:
                raise CoreRuntimeError(f"callee {insn['callee']} returned void")
            result = returned

        elif op == "host_call":
            args = [self._value(arg, values)[0] for arg in insn["args"]]
            returned = self.host.call(insn["symbol"], args)
            if "result" not in insn:
                return
            if returned is None:
                raise CoreRuntimeError(f"host {insn['symbol']} returned void")
            result = returned

        else:
            raise CoreRuntimeError(f"unsupported IR operation {op}")

        if "result" in insn:
            assert result is not None
            values[insn["result"]] = (
                result & mask_for(insn["result_type"]),
                insn["result_type"],
            )

    def execute_function(self, function_id: str, args: list[int], depth: int = 0) -> int | None:
        if depth > self.module.limits.max_call_depth:
            raise CoreRuntimeError("call-depth limit exceeded")
        try:
            function = self.functions[function_id]
        except KeyError as exc:
            raise CoreRuntimeError(f"unknown function {function_id}") from exc
        if len(args) != len(function["params"]):
            raise CoreRuntimeError(f"{function_id}: argument count mismatch")

        blocks = {block["id"]: block for block in function["blocks"]}
        address_to_block = {block["guest_address"]: block["id"] for block in function["blocks"]}
        block_id = function["blocks"][0]["id"]
        first_block = True

        while True:
            block = blocks[block_id]
            values: dict[str, tuple[int, str]] = {}
            if first_block:
                for param, value in zip(function["params"], args):
                    values[param["id"]] = (value & mask_for(param["type"]), param["type"])
                first_block = False

            for insn in block["instructions"]:
                self._execute_instruction(insn, values, depth)

            self._step()
            term = block["terminator"]
            op = term["op"]
            if op == "jump":
                block_id = term["target"]
            elif op == "branch":
                condition, _ = self._value(term["condition"], values)
                block_id = term["target_true"] if condition else term["target_false"]
            elif op == "return":
                if "value" not in term:
                    return None
                return self._value(term["value"], values)[0]
            elif op == "indirect_jump":
                target, _ = self._value(term["target"], values)
                if target not in address_to_block:
                    raise CoreRuntimeError(f"indirect target 0x{target:x} has no block")
                candidate = address_to_block[target]
                if candidate not in term["candidate_blocks"]:
                    raise CoreRuntimeError(f"indirect target {candidate} is outside candidate set")
                block_id = candidate
            elif op == "trap":
                raise CoreRuntimeError(f"IR trap: {term['reason']}")
            else:
                raise CoreRuntimeError(f"unsupported terminator {op}")

    def run(self, args: list[int] | None = None) -> ExecutionResult:
        returned = self.execute_function(self.module.entry_function, [] if args is None else args)
        return ExecutionResult(
            function_return=returned,
            observed_state=self.state.read(self.module.observe_state_slot),
            operations=self.operations,
            state=self.state.snapshot(),
            host=self.host.snapshot(),
        )
