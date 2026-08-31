#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from validate_ir_v1 import TYPE_BITS, load_and_validate

MASK32 = 0xFFFFFFFF


class BridgeRuntimeError(RuntimeError):
    pass


def _mask(type_name: str) -> int:
    return (1 << TYPE_BITS[type_name]) - 1


def _signed(value: int, bits: int) -> int:
    value &= (1 << bits) - 1
    sign = 1 << (bits - 1)
    return value - (1 << bits) if value & sign else value


class Runtime:
    def __init__(self, ir: dict, sidecar: dict, contract: dict):
        self.ir = ir
        self.sidecar = sidecar
        self.contract = contract
        if sidecar["source_input_sha256"] != ir["source"]["input_sha256"]:
            raise BridgeRuntimeError("sidecar/source input hash mismatch")
        if ir["host_contract_version"] != contract["contract_version"]:
            raise BridgeRuntimeError("host contract version mismatch")
        if sidecar["memory_size_bytes"] != contract["memory"]["size_bytes"]:
            raise BridgeRuntimeError("sidecar/host memory-size mismatch")
        if contract["memory"]["oob_policy"] != "deterministic fault":
            raise BridgeRuntimeError("runtime requires deterministic-fault memory policy")
        if contract["system"]["wall_clock"] or contract["system"]["randomness"]:
            raise BridgeRuntimeError("runtime requires deterministic host system contract")

        self.state_types = {s["id"]: s["type"] for s in ir["state_slots"]}
        self.state = {name: 0 for name in self.state_types}
        for name, value in sidecar["initial_state"].items():
            if name not in self.state_types:
                raise BridgeRuntimeError(f"initial state references undeclared slot {name}")
            self.state[name] = value & _mask(self.state_types[name])

        self.memory = bytearray(sidecar["memory_size_bytes"])
        occupied: list[tuple[int, int, str]] = []
        for segment in sorted(sidecar["memory_segments"], key=lambda s: s["guest_address"]):
            data = bytes.fromhex(segment["data_hex"])
            start = segment["guest_address"]
            end = start + len(data)
            if start < 0 or end > len(self.memory):
                raise BridgeRuntimeError(f"memory segment {segment['name']} is out of bounds")
            for old_start, old_end, old_name in occupied:
                if max(start, old_start) < min(end, old_end):
                    raise BridgeRuntimeError(f"memory segments overlap: {old_name} and {segment['name']}")
            occupied.append((start, end, segment["name"]))
            self.memory[start:end] = data

        self.functions = {f["id"]: f for f in ir["functions"]}
        self.operations = 0
        self.max_operations = sidecar["max_operations"]
        self.tick_count = contract["system"].get("tick_start", 0) & MASK32
        self.gfx_calls = 0
        self.audio_calls = 0
        self.input_calls = 0
        self.system_calls = 0
        self.framebuffer = bytearray(contract["graphics"]["width"] * contract["graphics"]["height"] * contract["graphics"]["channels"])
        self.audio_buf = [0] * contract["audio"]["sample_count"]

    def _step(self) -> None:
        self.operations += 1
        if self.operations > self.max_operations:
            raise BridgeRuntimeError("operation limit exceeded")

    def _value(self, operand: dict, values: dict[str, tuple[int, str]]) -> tuple[int, str]:
        if "value" in operand:
            try:
                return values[operand["value"]]
            except KeyError as exc:
                raise BridgeRuntimeError(f"undefined runtime value {operand['value']}") from exc
        return operand["const"] & _mask(operand["type"]), operand["type"]

    def _memory_address(self, operand: dict, values: dict[str, tuple[int, str]]) -> int:
        value, type_name = self._value(operand, values)
        expected = f"i{self.ir['source']['address_bits']}"
        if type_name != expected:
            raise BridgeRuntimeError(f"memory address has type {type_name}, expected {expected}")
        return value

    def _bounds(self, address: int, size: int) -> None:
        if address > len(self.memory) or size > len(self.memory) - address:
            raise BridgeRuntimeError(f"deterministic memory fault at 0x{address:x} size={size}")

    def _load(self, insn: dict, values: dict[str, tuple[int, str]]) -> int:
        address = self._memory_address(insn["address"], values)
        size = insn["width_bits"] // 8
        if insn["misaligned_policy"] == "fault" and address % insn["alignment"]:
            raise BridgeRuntimeError(f"deterministic misalignment fault at 0x{address:x}")
        self._bounds(address, size)
        byteorder = self.ir["source"]["endianness"]
        raw = int.from_bytes(self.memory[address:address + size], byteorder)
        result_bits = TYPE_BITS[insn["result_type"]]
        if insn["signed"] and insn["width_bits"] < result_bits:
            raw = _signed(raw, insn["width_bits"]) & ((1 << result_bits) - 1)
        return raw & ((1 << result_bits) - 1)

    def _store(self, insn: dict, values: dict[str, tuple[int, str]]) -> None:
        address = self._memory_address(insn["address"], values)
        value, _ = self._value(insn["value"], values)
        size = insn["width_bits"] // 8
        if insn["misaligned_policy"] == "fault" and address % insn["alignment"]:
            raise BridgeRuntimeError(f"deterministic misalignment fault at 0x{address:x}")
        self._bounds(address, size)
        mask = (1 << insn["width_bits"]) - 1
        self.memory[address:address + size] = (value & mask).to_bytes(size, self.ir["source"]["endianness"])

    def _host_call(self, symbol: str, args: list[int]) -> int | None:
        if symbol == "host_graphics":
            if len(args) != 3:
                raise BridgeRuntimeError("host_graphics arity mismatch")
            self.gfx_calls = (self.gfx_calls + 1) & MASK32
            x, y, value = args
            width = self.contract["graphics"]["width"]
            height = self.contract["graphics"]["height"]
            channels = self.contract["graphics"]["channels"]
            if channels != 3:
                raise BridgeRuntimeError("bridge proof currently requires RGB graphics contract")
            if x < width and y < height:
                p = (y * width + x) * channels
                v = value & 0xFF
                self.framebuffer[p] = v
                self.framebuffer[p + 1] = (v ^ self.contract["graphics"]["xor_g"]) & 0xFF
                self.framebuffer[p + 2] = (v ^ self.contract["graphics"]["xor_b"]) & 0xFF
            return None

        if symbol == "host_audio":
            if len(args) != 1:
                raise BridgeRuntimeError("host_audio arity mismatch")
            self.audio_calls = (self.audio_calls + 1) & MASK32
            sample = args[0]
            step = self.contract["audio"]["sample_step"]
            for i in range(len(self.audio_buf)):
                self.audio_buf[i] = (sample + i * step) & 0xFFFF
            return None

        if symbol == "host_input":
            if len(args) != 1:
                raise BridgeRuntimeError("host_input arity mismatch")
            self.input_calls = (self.input_calls + 1) & MASK32
            scripted = self.contract["input"]["values"]
            if not scripted:
                raise BridgeRuntimeError("host input script is empty")
            return scripted[args[0] % len(scripted)] & MASK32

        if symbol == "host_system":
            if len(args) != 2:
                raise BridgeRuntimeError("host_system arity mismatch")
            self.system_calls = (self.system_calls + 1) & MASK32
            out = (args[0] + args[1] + self.contract["system"]["deterministic_bias"] + self.tick_count) & MASK32
            self.tick_count = (self.tick_count + 1) & MASK32
            return out

        raise BridgeRuntimeError(f"unknown host symbol {symbol}")

    def _execute_instruction(self, insn: dict, values: dict[str, tuple[int, str]], depth: int) -> None:
        self._step()
        op = insn["op"]
        result: int | None = None

        if op == "const":
            result = insn["value"]

        elif op == "read_state":
            result = self.state[insn["slot"]]

        elif op == "write_state":
            value, _ = self._value(insn["value"], values)
            slot = insn["slot"]
            self.state[slot] = value & _mask(self.state_types[slot])
            return

        elif op == "binop":
            lhs, _ = self._value(insn["lhs"], values)
            rhs, _ = self._value(insn["rhs"], values)
            bits = TYPE_BITS[insn["result_type"]]
            mask = (1 << bits) - 1
            kind = insn["kind"]
            if kind == "add": result = lhs + rhs
            elif kind == "sub": result = lhs - rhs
            elif kind == "mul": result = lhs * rhs
            elif kind == "and": result = lhs & rhs
            elif kind == "or": result = lhs | rhs
            elif kind == "xor": result = lhs ^ rhs
            elif kind in {"shl", "lshr", "ashr"}:
                if rhs >= bits:
                    raise BridgeRuntimeError(f"shift count {rhs} is not normalized for {insn['result_type']}")
                if kind == "shl": result = lhs << rhs
                elif kind == "lshr": result = lhs >> rhs
                else: result = _signed(lhs, bits) >> rhs
            else:
                raise BridgeRuntimeError(f"unsupported binop {kind}")
            result &= mask

        elif op == "compare":
            lhs, lhs_type = self._value(insn["lhs"], values)
            rhs, _ = self._value(insn["rhs"], values)
            bits = TYPE_BITS[lhs_type]
            pred = insn["predicate"]
            if pred == "eq": flag = lhs == rhs
            elif pred == "ne": flag = lhs != rhs
            elif pred == "ult": flag = lhs < rhs
            elif pred == "ule": flag = lhs <= rhs
            elif pred == "ugt": flag = lhs > rhs
            elif pred == "uge": flag = lhs >= rhs
            elif pred == "slt": flag = _signed(lhs, bits) < _signed(rhs, bits)
            elif pred == "sle": flag = _signed(lhs, bits) <= _signed(rhs, bits)
            elif pred == "sgt": flag = _signed(lhs, bits) > _signed(rhs, bits)
            elif pred == "sge": flag = _signed(lhs, bits) >= _signed(rhs, bits)
            else: raise BridgeRuntimeError(f"unsupported predicate {pred}")
            result = 1 if flag else 0

        elif op == "cast":
            value, source_type = self._value(insn["value"], values)
            source_bits = TYPE_BITS[source_type]
            result_bits = TYPE_BITS[insn["result_type"]]
            kind = insn["kind"]
            if kind == "zext": result = value
            elif kind == "sext": result = _signed(value, source_bits)
            elif kind == "trunc": result = value
            elif kind == "bitcast": result = value
            else: raise BridgeRuntimeError(f"unsupported cast {kind}")
            result &= (1 << result_bits) - 1

        elif op == "select":
            cond, _ = self._value(insn["condition"], values)
            chosen = insn["if_true"] if cond else insn["if_false"]
            result, _ = self._value(chosen, values)

        elif op == "load":
            result = self._load(insn, values)

        elif op == "store":
            self._store(insn, values)
            return

        elif op == "call":
            args = [self._value(a, values)[0] for a in insn["args"]]
            returned = self.execute_function(insn["callee"], args, depth + 1)
            if "result" in insn:
                if returned is None:
                    raise BridgeRuntimeError(f"callee {insn['callee']} returned void")
                result = returned
            else:
                return

        elif op == "host_call":
            args = [self._value(a, values)[0] for a in insn["args"]]
            returned = self._host_call(insn["symbol"], args)
            if "result" in insn:
                if returned is None:
                    raise BridgeRuntimeError(f"host {insn['symbol']} returned void")
                result = returned
            else:
                return

        else:
            raise BridgeRuntimeError(f"unsupported IR operation {op}")

        if "result" in insn:
            values[insn["result"]] = (result & _mask(insn["result_type"]), insn["result_type"])

    def execute_function(self, function_id: str, args: list[int], depth: int = 0) -> int | None:
        if depth > 1024:
            raise BridgeRuntimeError("call-depth limit exceeded")
        function = self.functions[function_id]
        if len(args) != len(function["params"]):
            raise BridgeRuntimeError(f"{function_id}: argument count mismatch")
        blocks = {b["id"]: b for b in function["blocks"]}
        address_to_block = {b["guest_address"]: b["id"] for b in function["blocks"]}
        block_id = function["blocks"][0]["id"]
        first = True

        while True:
            block = blocks[block_id]
            values: dict[str, tuple[int, str]] = {}
            if first:
                for param, value in zip(function["params"], args):
                    values[param["id"]] = (value & _mask(param["type"]), param["type"])
                first = False

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
                    raise BridgeRuntimeError(f"indirect target 0x{target:x} has no block")
                candidate = address_to_block[target]
                if candidate not in term["candidate_blocks"]:
                    raise BridgeRuntimeError(f"indirect target {candidate} is outside candidate set")
                block_id = candidate
            elif op == "trap":
                raise BridgeRuntimeError(f"IR trap: {term['reason']}")
            else:
                raise BridgeRuntimeError(f"unsupported terminator {op}")

    def result(self) -> dict:
        entry_value = self.state[self.sidecar["entry_state_slot"]] & MASK32
        h = (entry_value ^ self.tick_count ^ (self.gfx_calls << 4) ^ (self.audio_calls << 8) ^ (self.input_calls << 12) ^ (self.system_calls << 16)) & MASK32
        for byte in self.framebuffer:
            h = ((h * 16777619) ^ byte) & MASK32
        for sample in self.audio_buf:
            h = ((h * 16777619) ^ (sample & 0xFFFF)) & MASK32
        audio_bytes = b"".join((x & 0xFFFF).to_bytes(2, "little") for x in self.audio_buf)
        return {
            "return_a0": entry_value,
            "tick_count": self.tick_count,
            "graphics_calls": self.gfx_calls,
            "audio_calls": self.audio_calls,
            "input_calls": self.input_calls,
            "system_calls": self.system_calls,
            "checksum": h,
            "operations": self.operations,
            "framebuffer_sha256": hashlib.sha256(bytes(self.framebuffer)).hexdigest(),
            "audio_payload_sha256": hashlib.sha256(audio_bytes).hexdigest(),
        }


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: run_ir_v1_bridge.py <ir-v1.json> <sidecar.json> <host-contract.json> <out-result.json>", file=sys.stderr)
        return 2
    try:
        ir = load_and_validate(argv[1])
        sidecar = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        contract = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        runtime = Runtime(ir, sidecar, contract)
        runtime.execute_function(ir["entry_function"], [])
        result = runtime.result()
        Path(argv[4]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, KeyError, ValueError, BridgeRuntimeError) as exc:
        print(f"OPENRECOMP_IR_V1_BRIDGE_RUNTIME_REJECT: {exc}", file=sys.stderr)
        return 2

    print(f"IR_V1_BRIDGE_CHECKSUM={result['checksum']}")
    print(f"IR_V1_BRIDGE_RETURN_A0={result['return_a0']}")
    print("OPENRECOMP_IR_V1_BRIDGE_RUNTIME=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
