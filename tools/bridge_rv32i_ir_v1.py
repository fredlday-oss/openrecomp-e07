#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HOSTS = {"host_graphics", "host_audio", "host_input", "host_system"}
HOST_ARGS = {
    "host_graphics": (10, 11, 12),
    "host_audio": (10,),
    "host_input": (10,),
    "host_system": (10, 11),
}
HOST_RETURNS = {"host_input", "host_system"}
LEGACY_VERSION = "0.1.1"
BRIDGE_VERSION = "1.0.0"
V1_VERSION = "1.0.0"


class BridgeError(ValueError):
    pass


def _id(name: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_%.:-]", "_", name)
    if not out or not re.match(r"^[A-Za-z_%.]", out):
        out = "fn_" + out
    return out


def _slot(reg: int) -> str:
    return f"gpr:x{reg}"


def _tmp(address: int, tag: str) -> str:
    return f"%v{address:08x}_{tag}"


def _u32(value: int) -> int:
    return value & 0xFFFFFFFF


def _function_instructions(function: dict, insn_by_addr: dict[int, dict]) -> list[dict]:
    out: list[dict] = []
    for block in function["basic_blocks"]:
        for address in block["instruction_addresses"]:
            if address not in insn_by_addr:
                raise BridgeError(f"{function['name']}: missing legacy instruction 0x{address:x}")
            out.append(insn_by_addr[address])
    return out


def _reachable_functions(legacy: dict) -> tuple[list[dict], dict[int, dict]]:
    by_addr = {f["address"]: f for f in legacy["functions"]}
    by_name = {f["name"]: f for f in legacy["functions"]}
    if "fixture_main" not in by_name:
        raise BridgeError("legacy IR has no fixture_main")

    insn_by_addr = {i["address"]: i for i in legacy["instructions"]}
    seen: set[int] = set()
    todo = [by_name["fixture_main"]]
    ordered: list[dict] = []

    while todo:
        function = todo.pop()
        if function["address"] in seen:
            continue
        seen.add(function["address"])
        ordered.append(function)
        for insn in _function_instructions(function, insn_by_addr):
            if insn["op"] != "jal" or insn["rd"] == 0:
                continue
            target = insn["target"]
            callee = by_addr.get(target)
            if callee and callee["name"] not in HOSTS and callee["address"] not in seen:
                todo.append(callee)

    ordered.sort(key=lambda f: f["address"])
    return ordered, by_addr


def _read_reg(out: list[dict], address: int, reg: int, tag: str) -> dict:
    if reg == 0:
        return {"const": 0, "type": "i32"}
    result = _tmp(address, tag)
    out.append({
        "op": "read_state",
        "result": result,
        "result_type": "i32",
        "slot": _slot(reg),
        "source_address": address,
    })
    return {"value": result}


def _write_reg(out: list[dict], address: int, reg: int, value: dict) -> None:
    if reg == 0:
        return
    out.append({
        "op": "write_state",
        "slot": _slot(reg),
        "value": value,
        "source_address": address,
    })


def _binop_write(out: list[dict], insn: dict, kind: str, lhs: dict, rhs: dict, tag: str = "result") -> None:
    address = insn["address"]
    result = _tmp(address, tag)
    out.append({
        "op": "binop",
        "result": result,
        "result_type": "i32",
        "kind": kind,
        "lhs": lhs,
        "rhs": rhs,
        "source_address": address,
    })
    _write_reg(out, address, insn["rd"], {"value": result})


def _host_call(out: list[dict], insn: dict, host_name: str) -> None:
    address = insn["address"]
    if insn["rd"] != 0:
        _write_reg(out, address, insn["rd"], {"const": _u32(address + 4), "type": "i32"})

    args = [_read_reg(out, address, reg, f"host_arg{idx}") for idx, reg in enumerate(HOST_ARGS[host_name])]
    call = {
        "op": "host_call",
        "symbol": host_name,
        "args": args,
        "source_address": address,
    }
    if host_name in HOST_RETURNS:
        result = _tmp(address, "hostret")
        call["result"] = result
        call["result_type"] = "i32"
        out.append(call)
        _write_reg(out, address, 10, {"value": result})
    else:
        out.append(call)


def _lower_nonterminator(out: list[dict], insn: dict, function_by_addr: dict[int, dict]) -> None:
    address = insn["address"]
    op = insn["op"]

    if op == "addi":
        lhs = _read_reg(out, address, insn["rs1"], "rs1")
        _binop_write(out, insn, "add", lhs, {"const": _u32(insn["imm"]), "type": "i32"})
    elif op == "andi":
        lhs = _read_reg(out, address, insn["rs1"], "rs1")
        _binop_write(out, insn, "and", lhs, {"const": _u32(insn["imm"]), "type": "i32"})
    elif op == "slli":
        lhs = _read_reg(out, address, insn["rs1"], "rs1")
        _binop_write(out, insn, "shl", lhs, {"const": insn["imm"], "type": "i32"})
    elif op == "srli":
        lhs = _read_reg(out, address, insn["rs1"], "rs1")
        _binop_write(out, insn, "lshr", lhs, {"const": insn["imm"], "type": "i32"})
    elif op == "add":
        lhs = _read_reg(out, address, insn["rs1"], "rs1")
        rhs = _read_reg(out, address, insn["rs2"], "rs2")
        _binop_write(out, insn, "add", lhs, rhs)
    elif op == "xor":
        lhs = _read_reg(out, address, insn["rs1"], "rs1")
        rhs = _read_reg(out, address, insn["rs2"], "rs2")
        _binop_write(out, insn, "xor", lhs, rhs)
    elif op == "lui":
        result = _tmp(address, "lui")
        out.append({
            "op": "const",
            "result": result,
            "result_type": "i32",
            "value": _u32(insn["imm"]),
            "source_address": address,
        })
        _write_reg(out, address, insn["rd"], {"value": result})
    elif op in {"lw", "lhu"}:
        base = _read_reg(out, address, insn["rs1"], "base")
        effective = _tmp(address, "addr")
        out.append({
            "op": "binop",
            "result": effective,
            "result_type": "i32",
            "kind": "add",
            "lhs": base,
            "rhs": {"const": _u32(insn["imm"]), "type": "i32"},
            "source_address": address,
        })
        loaded = _tmp(address, "load")
        width = 32 if op == "lw" else 16
        out.append({
            "op": "load",
            "result": loaded,
            "result_type": "i32",
            "width_bits": width,
            "signed": op == "lw",
            "address": {"value": effective},
            "alignment": width // 8,
            "misaligned_policy": "fault",
            "source_address": address,
        })
        _write_reg(out, address, insn["rd"], {"value": loaded})
    elif op == "sw":
        base = _read_reg(out, address, insn["rs1"], "base")
        value = _read_reg(out, address, insn["rs2"], "store_value")
        effective = _tmp(address, "addr")
        out.append({
            "op": "binop",
            "result": effective,
            "result_type": "i32",
            "kind": "add",
            "lhs": base,
            "rhs": {"const": _u32(insn["imm"]), "type": "i32"},
            "source_address": address,
        })
        out.append({
            "op": "store",
            "width_bits": 32,
            "address": {"value": effective},
            "value": value,
            "alignment": 4,
            "misaligned_policy": "fault",
            "source_address": address,
        })
    elif op == "jal" and insn["rd"] != 0:
        target = insn["target"]
        callee = function_by_addr.get(target)
        if not callee:
            raise BridgeError(f"0x{address:x}: direct call target 0x{target:x} is not a known function")
        if callee["name"] in HOSTS:
            _host_call(out, insn, callee["name"])
        else:
            _write_reg(out, address, insn["rd"], {"const": _u32(address + 4), "type": "i32"})
            out.append({
                "op": "call",
                "callee": _id(callee["name"]),
                "args": [],
                "source_address": address,
            })
    else:
        raise BridgeError(f"0x{address:x}: unsupported non-terminator op {op}")


def _block_id(address: int) -> str:
    return f"b_{address:08x}"


def _convert_function(function: dict, legacy: dict, function_by_addr: dict[int, dict], reachable_addrs: set[int]) -> tuple[dict, set[str]]:
    insn_by_addr = {i["address"]: i for i in legacy["instructions"]}
    address_to_block: dict[int, str] = {}
    for block in function["basic_blocks"]:
        bid = _block_id(block["start"])
        for address in block["instruction_addresses"]:
            address_to_block[address] = bid

    used_hosts: set[str] = set()
    blocks: list[dict] = []

    for legacy_block in function["basic_blocks"]:
        addresses = legacy_block["instruction_addresses"]
        if not addresses:
            continue
        lowered: list[dict] = []
        terminator: dict | None = None

        for index, address in enumerate(addresses):
            insn = insn_by_addr[address]
            op = insn["op"]
            last = index == len(addresses) - 1

            if op in {"bltu", "bgeu", "beq", "bne"}:
                if not last:
                    raise BridgeError(f"0x{address:x}: branch is not last in legacy basic block")
                lhs = _read_reg(lowered, address, insn["rs1"], "branch_lhs")
                rhs = _read_reg(lowered, address, insn["rs2"], "branch_rhs")
                cond = _tmp(address, "cond")
                predicate = {"bltu": "ult", "bgeu": "uge", "beq": "eq", "bne": "ne"}[op]
                lowered.append({
                    "op": "compare",
                    "result": cond,
                    "result_type": "i1",
                    "predicate": predicate,
                    "lhs": lhs,
                    "rhs": rhs,
                    "source_address": address,
                })
                target = address_to_block.get(insn["target"])
                fallthrough = address_to_block.get(address + 4)
                if not target or not fallthrough:
                    raise BridgeError(f"0x{address:x}: branch target/fallthrough is outside function CFG")
                terminator = {
                    "op": "branch",
                    "condition": {"value": cond},
                    "target_true": target,
                    "target_false": fallthrough,
                    "source_address": address,
                }
                continue

            if op == "jal" and insn["rd"] == 0:
                if not last:
                    raise BridgeError(f"0x{address:x}: tail/unconditional jal is not last in block")
                target = insn["target"]
                local_target = address_to_block.get(target)
                callee = function_by_addr.get(target)
                if local_target:
                    terminator = {"op": "jump", "target": local_target, "source_address": address}
                elif callee and callee["name"] in HOSTS:
                    _host_call(lowered, insn, callee["name"])
                    used_hosts.add(callee["name"])
                    terminator = {"op": "return", "source_address": address}
                elif callee and callee["address"] in reachable_addrs:
                    lowered.append({"op": "call", "callee": _id(callee["name"]), "args": [], "source_address": address})
                    terminator = {"op": "return", "source_address": address}
                else:
                    raise BridgeError(f"0x{address:x}: unbounded tail target 0x{target:x}")
                continue

            if op == "jalr":
                if not last:
                    raise BridgeError(f"0x{address:x}: jalr is not last in block")
                if insn["rd"] == 0 and insn["rs1"] == 1 and insn["imm"] == 0:
                    terminator = {"op": "return", "source_address": address}
                else:
                    raise BridgeError(
                        f"0x{address:x}: unsupported/unbounded jalr rd={insn['rd']} rs1={insn['rs1']} imm={insn['imm']}"
                    )
                continue

            _lower_nonterminator(lowered, insn, function_by_addr)
            if op == "jal":
                callee = function_by_addr.get(insn["target"])
                if callee and callee["name"] in HOSTS:
                    used_hosts.add(callee["name"])

        if terminator is None:
            next_address = addresses[-1] + 4
            next_block = address_to_block.get(next_address)
            if not next_block:
                raise BridgeError(f"{function['name']}: block 0x{legacy_block['start']:x} has no explicit terminator/fallthrough")
            terminator = {"op": "jump", "target": next_block, "source_address": addresses[-1]}

        blocks.append({
            "id": _block_id(legacy_block["start"]),
            "guest_address": legacy_block["start"],
            "instructions": lowered,
            "terminator": terminator,
        })

    return {
        "id": _id(function["name"]),
        "guest_address": function["address"],
        "params": [],
        "return_type": None,
        "blocks": blocks,
    }, used_hosts


def convert(legacy: dict, host_contract: dict) -> tuple[dict, dict]:
    if legacy.get("ir_version") != LEGACY_VERSION:
        raise BridgeError(f"expected legacy IR {LEGACY_VERSION}")
    if legacy.get("architecture") != "riscv32-rv32i":
        raise BridgeError("bridge only accepts riscv32-rv32i")
    if legacy.get("architecture_adapter", {}).get("bits") != 32:
        raise BridgeError("bridge requires a 32-bit source adapter")
    if legacy.get("architecture_adapter", {}).get("endianness") != "little":
        raise BridgeError("bridge requires little-endian RV32I")
    if host_contract.get("memory", {}).get("oob_policy") != "deterministic fault":
        raise BridgeError("host memory contract must fail closed")
    if host_contract.get("system", {}).get("wall_clock") or host_contract.get("system", {}).get("randomness"):
        raise BridgeError("host contract must be deterministic")

    reachable, function_by_addr = _reachable_functions(legacy)
    reachable_addrs = {f["address"] for f in reachable}
    converted_functions: list[dict] = []
    used_hosts: set[str] = set()
    for function in reachable:
        converted, hosts = _convert_function(function, legacy, function_by_addr, reachable_addrs)
        converted_functions.append(converted)
        used_hosts.update(hosts)

    v1 = {
        "ir_version": V1_VERSION,
        "module_id": "e07.rv32i.fixture-full.ir-v1",
        "source": {
            "architecture": legacy["architecture"],
            "adapter": "openrecomp.riscv32-legacy-bridge-v1",
            "address_bits": 32,
            "endianness": "little",
            "input_sha256": legacy["input_sha256"],
        },
        "required_features": ["core-v1"] + (["host-call"] if used_hosts else []),
        "host_contract_version": host_contract["contract_version"],
        "required_host_symbols": sorted(used_hosts),
        "state_slots": [{"id": _slot(i), "type": "i32"} for i in range(1, 32)],
        "entry_function": "fixture_main",
        "functions": converted_functions,
    }

    sidecar = {
        "bridge_version": BRIDGE_VERSION,
        "source_ir_version": LEGACY_VERSION,
        "source_input_sha256": legacy["input_sha256"],
        "memory_size_bytes": host_contract["memory"]["size_bytes"],
        "initial_state": {_slot(2): 0x30000},
        "memory_segments": [
            {
                "name": section["name"],
                "guest_address": section["addr"],
                "data_hex": section["data_hex"],
            }
            for section in legacy["alloc_sections"]
            if section["name"] != ".text"
        ],
        "entry_state_slot": _slot(10),
        "max_operations": 2_000_000,
    }
    return v1, sidecar


def _write_json(path: str | Path, value: dict) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: bridge_rv32i_ir_v1.py <legacy-ir.json> <host-contract.json> <out-v1.json> <out-sidecar.json>", file=sys.stderr)
        return 2
    try:
        legacy_bytes = Path(argv[1]).read_bytes()
        legacy = json.loads(legacy_bytes)
        contract = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        v1, sidecar = convert(legacy, contract)
        sidecar["source_legacy_ir_sha256"] = hashlib.sha256(legacy_bytes).hexdigest()
        _write_json(argv[3], v1)
        _write_json(argv[4], sidecar)
    except (OSError, json.JSONDecodeError, KeyError, BridgeError) as exc:
        print(f"OPENRECOMP_RV32I_IR_V1_BRIDGE_REJECT: {exc}", file=sys.stderr)
        return 2
    print("OPENRECOMP_RV32I_IR_V1_BRIDGE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
