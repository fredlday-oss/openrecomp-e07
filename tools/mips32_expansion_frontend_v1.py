#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mips32 import DecodeError, decode, is_control_flow

MASK32 = 0xFFFFFFFF
FRONTEND_VERSION = "1.0.0"
PROFILE = "expansion-v1"
BRANCH_OPS = {"beq", "bne", "blez", "bgtz", "bltz", "bgez"}


class FrontendError(ValueError):
    pass


def _u32(value: int) -> int:
    return value & MASK32


def _slot(reg: int) -> str:
    return f"gpr:r{reg}"


def _tmp(address: int, tag: str) -> str:
    return f"%mx{address:08x}_{tag}"


def _block_id(address: int) -> str:
    return f"b_{address:08x}"


def load_hex(path: str | Path) -> tuple[dict[int, int], str]:
    source = Path(path).read_bytes()
    words: dict[int, int] = {}
    for line_number, raw in enumerate(source.decode("utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise FrontendError(f"line {line_number}: expected '<address> <word>'")
        try:
            address = int(parts[0], 16)
            word = int(parts[1], 16)
        except ValueError as exc:
            raise FrontendError(f"line {line_number}: invalid hexadecimal value") from exc
        if address & 3:
            raise FrontendError(f"line {line_number}: instruction address is not 4-byte aligned")
        if word < 0 or word > MASK32:
            raise FrontendError(f"line {line_number}: instruction word exceeds 32 bits")
        if address in words:
            raise FrontendError(f"line {line_number}: duplicate address 0x{address:x}")
        words[address] = word
    if not words:
        raise FrontendError("fixture contains no instruction words")
    return words, hashlib.sha256(source).hexdigest()


def _read_state(out: list[dict], address: int, slot: str, tag: str, type_name: str = "i32") -> dict:
    result = _tmp(address, tag)
    out.append({
        "op": "read_state",
        "result": result,
        "result_type": type_name,
        "slot": slot,
        "source_address": address,
    })
    return {"value": result}


def _read_reg(out: list[dict], address: int, reg: int, tag: str) -> dict:
    if reg == 0:
        return {"const": 0, "type": "i32"}
    return _read_state(out, address, _slot(reg), tag)


def _write_state(out: list[dict], address: int, slot: str, value: dict) -> None:
    out.append({"op": "write_state", "slot": slot, "value": value, "source_address": address})


def _write_reg(out: list[dict], address: int, reg: int, value: dict) -> None:
    if reg != 0:
        _write_state(out, address, _slot(reg), value)


def _binop(out: list[dict], address: int, tag: str, kind: str, lhs: dict, rhs: dict, type_name: str = "i32") -> dict:
    result = _tmp(address, tag)
    out.append({
        "op": "binop", "result": result, "result_type": type_name, "kind": kind,
        "lhs": lhs, "rhs": rhs, "source_address": address,
    })
    return {"value": result}


def _cast(out: list[dict], address: int, tag: str, kind: str, value: dict, type_name: str) -> dict:
    result = _tmp(address, tag)
    out.append({
        "op": "cast", "result": result, "result_type": type_name,
        "kind": kind, "value": value, "source_address": address,
    })
    return {"value": result}


def _compare_i32(out: list[dict], address: int, tag: str, predicate: str, lhs: dict, rhs: dict) -> dict:
    result = _tmp(address, tag)
    out.append({
        "op": "compare", "result": result, "result_type": "i1", "predicate": predicate,
        "lhs": lhs, "rhs": rhs, "source_address": address,
    })
    return {"value": result}


def _lower_simple(out: list[dict], insn: dict) -> None:
    address = insn["address"]
    op = insn["op"]
    if op == "nop":
        return

    if op in {"addiu", "andi", "ori", "xori"}:
        lhs = _read_reg(out, address, insn["rs"], "rs")
        kind = {"addiu": "add", "andi": "and", "ori": "or", "xori": "xor"}[op]
        imm = _u32(insn["imm"]) if op == "addiu" else insn["imm"]
        value = _binop(out, address, op, kind, lhs, {"const": imm, "type": "i32"})
        _write_reg(out, address, insn["rt"], value)
        return

    if op == "lui":
        result = _tmp(address, "lui")
        out.append({
            "op": "const", "result": result, "result_type": "i32",
            "value": _u32(insn["imm"] << 16), "source_address": address,
        })
        _write_reg(out, address, insn["rt"], {"value": result})
        return

    if op in {"addu", "subu", "and", "or", "xor", "nor"}:
        lhs = _read_reg(out, address, insn["rs"], "rs")
        rhs = _read_reg(out, address, insn["rt"], "rt")
        if op == "nor":
            ored = _binop(out, address, "nor_or", "or", lhs, rhs)
            value = _binop(out, address, "nor", "xor", ored, {"const": MASK32, "type": "i32"})
        else:
            kind = {"addu": "add", "subu": "sub", "and": "and", "or": "or", "xor": "xor"}[op]
            value = _binop(out, address, op, kind, lhs, rhs)
        _write_reg(out, address, insn["rd"], value)
        return

    if op in {"sll", "srl", "sra", "sllv", "srlv", "srav"}:
        value = _read_reg(out, address, insn["rt"], "shift_value")
        if op in {"sll", "srl", "sra"}:
            amount = {"const": insn["shamt"], "type": "i32"}
        else:
            raw = _read_reg(out, address, insn["rs"], "shift_raw")
            amount = _binop(out, address, "shift_mask", "and", raw, {"const": 31, "type": "i32"})
        kind = {"sll": "shl", "sllv": "shl", "srl": "lshr", "srlv": "lshr", "sra": "ashr", "srav": "ashr"}[op]
        shifted = _binop(out, address, op, kind, value, amount)
        _write_reg(out, address, insn["rd"], shifted)
        return

    if op in {"slt", "sltu", "slti", "sltiu"}:
        lhs = _read_reg(out, address, insn["rs"], "cmp_lhs")
        if op in {"slt", "sltu"}:
            rhs = _read_reg(out, address, insn["rt"], "cmp_rhs")
            target = insn["rd"]
        else:
            rhs = {"const": _u32(insn["imm"]), "type": "i32"}
            target = insn["rt"]
        flag = _compare_i32(out, address, "cmp", "slt" if op in {"slt", "slti"} else "ult", lhs, rhs)
        widened = _cast(out, address, "cmp_i32", "zext", flag, "i32")
        _write_reg(out, address, target, widened)
        return

    if op in {"mult", "multu"}:
        lhs32 = _read_reg(out, address, insn["rs"], "mul_lhs32")
        rhs32 = _read_reg(out, address, insn["rt"], "mul_rhs32")
        ext_kind = "sext" if op == "mult" else "zext"
        lhs64 = _cast(out, address, "mul_lhs64", ext_kind, lhs32, "i64")
        rhs64 = _cast(out, address, "mul_rhs64", ext_kind, rhs32, "i64")
        product = _binop(out, address, "mul64", "mul", lhs64, rhs64, "i64")
        lo = _cast(out, address, "mul_lo", "trunc", product, "i32")
        high64 = _binop(out, address, "mul_high64", "lshr", product, {"const": 32, "type": "i64"}, "i64")
        hi = _cast(out, address, "mul_hi", "trunc", high64, "i32")
        _write_state(out, address, "special:lo", lo)
        _write_state(out, address, "special:hi", hi)
        return

    if op in {"mfhi", "mflo"}:
        value = _read_state(out, address, "special:hi" if op == "mfhi" else "special:lo", op)
        _write_reg(out, address, insn["rd"], value)
        return

    load_info = {
        "lb": (8, True, 1), "lbu": (8, False, 1),
        "lh": (16, True, 2), "lhu": (16, False, 2),
        "lw": (32, True, 4),
    }
    store_info = {"sb": (8, 1), "sh": (16, 2), "sw": (32, 4)}
    if op in load_info or op in store_info:
        base = _read_reg(out, address, insn["rs"], "base")
        effective = _binop(
            out, address, "addr", "add", base,
            {"const": _u32(insn["imm"]), "type": "i32"},
        )
        if op in load_info:
            width, signed, alignment = load_info[op]
            loaded = _tmp(address, "load")
            out.append({
                "op": "load", "result": loaded, "result_type": "i32",
                "width_bits": width, "signed": signed, "address": effective,
                "alignment": alignment, "misaligned_policy": "fault", "source_address": address,
            })
            _write_reg(out, address, insn["rt"], {"value": loaded})
        else:
            width, alignment = store_info[op]
            value = _read_reg(out, address, insn["rt"], "store_value")
            if width < 32:
                value = _cast(out, address, "store_narrow", "trunc", value, f"i{width}")
            out.append({
                "op": "store", "width_bits": width, "address": effective, "value": value,
                "alignment": alignment, "misaligned_policy": "fault", "source_address": address,
            })
        return

    raise FrontendError(f"0x{address:x}: {op} cannot be lowered as a simple instruction")


def _function_ranges(meta: dict, words: dict[int, int]) -> list[tuple[dict, int]]:
    functions = sorted(meta["functions"], key=lambda item: item["address"])
    if not functions:
        raise FrontendError("fixture declares no functions")
    max_end = max(words) + 4
    out: list[tuple[dict, int]] = []
    seen_ids: set[str] = set()
    seen_addresses: set[int] = set()
    for index, function in enumerate(functions):
        fid = function["id"]
        start = function["address"]
        if fid in seen_ids or start in seen_addresses:
            raise FrontendError("duplicate function id/address")
        if start not in words:
            raise FrontendError(f"function {fid} starts outside fixture")
        seen_ids.add(fid)
        seen_addresses.add(start)
        end = functions[index + 1]["address"] if index + 1 < len(functions) else max_end
        if end <= start:
            raise FrontendError(f"invalid function range for {fid}")
        for address in range(start, end, 4):
            if address not in words:
                raise FrontendError(f"function {fid} has a hole at 0x{address:x}")
        out.append((function, end))
    return out


def _collect_leaders(function: dict, end: int, words: dict[int, int], function_by_address: dict[int, dict]) -> tuple[set[int], set[int]]:
    start = function["address"]
    leaders = {start}
    delay_slots: set[int] = set()
    for address in range(start, end, 4):
        if address in delay_slots:
            continue
        insn = decode(address, words[address])
        if not is_control_flow(insn):
            continue
        delay = address + 4
        if delay >= end or delay not in words:
            raise FrontendError(f"0x{address:x}: control transfer lacks an in-function delay slot")
        delay_insn = decode(delay, words[delay])
        if is_control_flow(delay_insn):
            raise FrontendError(f"0x{address:x}: control transfer in delay slot is outside expansion V1")
        delay_slots.add(delay)
        if insn["op"] in BRANCH_OPS:
            target = insn["target"]
            continuation = address + 8
            if not (start <= target < end) or target not in words:
                raise FrontendError(f"0x{address:x}: branch target leaves function")
            if not (start <= continuation < end) or continuation not in words:
                raise FrontendError(f"0x{address:x}: branch continuation leaves function")
            leaders.update({target, continuation})
        elif insn["op"] == "j":
            target = insn["target"]
            if not (start <= target < end) or target not in words:
                raise FrontendError(f"0x{address:x}: jump target leaves function")
            leaders.add(target)
        elif insn["op"] == "jal":
            if insn["target"] not in function_by_address:
                raise FrontendError(f"0x{address:x}: jal target is not a declared function")
            continuation = address + 8
            if not (start <= continuation < end) or continuation not in words:
                raise FrontendError(f"0x{address:x}: call continuation leaves function")
            leaders.add(continuation)
        elif insn["op"] == "jr" and insn["rs"] != 31:
            raise FrontendError(f"0x{address:x}: only jr $ra is supported in expansion V1")
    bad = sorted(leaders & delay_slots)
    if bad:
        raise FrontendError("control-flow target enters delay slot: " + ", ".join(f"0x{x:x}" for x in bad))
    return leaders, delay_slots


def _branch_condition(instructions: list[dict], insn: dict) -> dict:
    address = insn["address"]
    op = insn["op"]
    lhs = _read_reg(instructions, address, insn["rs"], "branch_lhs")
    if op in {"beq", "bne"}:
        rhs = _read_reg(instructions, address, insn["rt"], "branch_rhs")
        predicate = "eq" if op == "beq" else "ne"
    else:
        rhs = {"const": 0, "type": "i32"}
        predicate = {"blez": "sle", "bgtz": "sgt", "bltz": "slt", "bgez": "sge"}[op]
    return _compare_i32(instructions, address, "branch_cond", predicate, lhs, rhs)


def _convert_function(function: dict, end: int, words: dict[int, int], function_by_address: dict[int, dict]) -> tuple[dict, int]:
    start = function["address"]
    leaders, delay_slots = _collect_leaders(function, end, words, function_by_address)
    blocks: list[dict] = []
    delay_count = 0
    for leader in sorted(leaders):
        instructions: list[dict] = []
        address = leader
        terminator: dict | None = None
        while address < end:
            if address != leader and address in leaders:
                terminator = {"op": "jump", "target": _block_id(address), "source_address": address - 4}
                break
            if address in delay_slots:
                raise FrontendError(f"0x{address:x}: orphan delay slot reached as a normal instruction")
            insn = decode(address, words[address])
            if not is_control_flow(insn):
                _lower_simple(instructions, insn)
                address += 4
                continue
            delay_address = address + 4
            delay_insn = decode(delay_address, words[delay_address])
            if is_control_flow(delay_insn):
                raise FrontendError(f"0x{address:x}: nested control transfer in delay slot")
            delay_count += 1
            if insn["op"] in BRANCH_OPS:
                condition = _branch_condition(instructions, insn)
                _lower_simple(instructions, delay_insn)
                terminator = {
                    "op": "branch", "condition": condition,
                    "target_true": _block_id(insn["target"]),
                    "target_false": _block_id(address + 8), "source_address": address,
                }
            elif insn["op"] == "jal":
                callee = function_by_address[insn["target"]]
                _write_reg(instructions, address, 31, {"const": _u32(address + 8), "type": "i32"})
                _lower_simple(instructions, delay_insn)
                instructions.append({"op": "call", "callee": callee["id"], "args": [], "source_address": address})
                terminator = {"op": "jump", "target": _block_id(address + 8), "source_address": address}
            elif insn["op"] == "j":
                _lower_simple(instructions, delay_insn)
                terminator = {"op": "jump", "target": _block_id(insn["target"]), "source_address": address}
            elif insn["op"] == "jr":
                if insn["rs"] != 31:
                    raise FrontendError(f"0x{address:x}: only jr $ra is supported")
                _lower_simple(instructions, delay_insn)
                terminator = {"op": "return", "source_address": address}
            else:
                raise FrontendError(f"0x{address:x}: unsupported control transfer {insn['op']}")
            break
        if terminator is None:
            raise FrontendError(f"block 0x{leader:x} reaches function end without terminator")
        blocks.append({"id": _block_id(leader), "guest_address": leader, "instructions": instructions, "terminator": terminator})
    return ({"id": function["id"], "guest_address": start, "params": [], "return_type": None, "blocks": blocks}, delay_count)


def convert(meta: dict, words: dict[int, int], source_sha256: str, contract: dict) -> tuple[dict, dict, dict]:
    if meta.get("fixture_version") != FRONTEND_VERSION or meta.get("profile") != PROFILE:
        raise FrontendError("unsupported MIPS32 expansion fixture/profile version")
    architecture = meta.get("architecture")
    if architecture not in {"mips32-le", "mips32-be"}:
        raise FrontendError("expansion V1 requires mips32-le or mips32-be")
    if contract.get("memory", {}).get("oob_policy") != "deterministic fault":
        raise FrontendError("host memory contract must fail closed")
    if contract.get("system", {}).get("wall_clock") or contract.get("system", {}).get("randomness"):
        raise FrontendError("host contract must remain deterministic")
    if meta["memory_size_bytes"] != contract["memory"]["size_bytes"]:
        raise FrontendError("fixture/host memory-size mismatch")

    ranges = _function_ranges(meta, words)
    function_by_address = {item["address"]: item for item, _ in ranges}
    entry = function_by_address.get(meta["entry_address"])
    if entry is None:
        raise FrontendError("entry address is not a declared function")
    converted_functions: list[dict] = []
    total_delay_slots = 0
    for function, end in ranges:
        converted, count = _convert_function(function, end, words, function_by_address)
        converted_functions.append(converted)
        total_delay_slots += count

    state_slots = [{"id": _slot(reg), "type": "i32"} for reg in range(1, 32)]
    state_slots += [{"id": "special:hi", "type": "i32"}, {"id": "special:lo", "type": "i32"}]
    slot_ids = {item["id"] for item in state_slots}
    fixture_id = meta["fixture_id"]
    ir = {
        "ir_version": "1.0.0",
        "module_id": f"openrecomp.mips32.synthetic.expansion-v1.{fixture_id}",
        "source": {
            "architecture": architecture,
            "adapter": "openrecomp.mips32-expansion-v1",
            "address_bits": 32,
            "endianness": "big" if architecture == "mips32-be" else "little",
            "input_sha256": source_sha256,
        },
        "required_features": ["core-v1"],
        "host_contract_version": contract["contract_version"],
        "required_host_symbols": [],
        "state_slots": state_slots,
        "entry_function": entry["id"],
        "functions": converted_functions,
    }
    for slot in meta["initial_state"]:
        if slot not in slot_ids:
            raise FrontendError(f"initial state references undeclared slot {slot}")
    if meta["observe_state_slot"] not in slot_ids:
        raise FrontendError("observed state slot is undeclared")
    sidecar = {
        "frontend_version": FRONTEND_VERSION,
        "source_input_sha256": source_sha256,
        "memory_size_bytes": meta["memory_size_bytes"],
        "initial_state": dict(sorted(meta["initial_state"].items())),
        "memory_segments": [],
        "entry_state_slot": meta["observe_state_slot"],
        "max_operations": meta["max_operations"],
    }
    report = {
        "frontend_version": FRONTEND_VERSION,
        "profile": PROFILE,
        "fixture_id": fixture_id,
        "architecture": architecture,
        "functions": len(converted_functions),
        "source_words": len(words),
        "delay_slots_lowered": total_delay_slots,
        "source_input_sha256": source_sha256,
    }
    return ir, sidecar, report


def _write_json(path: str | Path, value: dict) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 7:
        print("usage: mips32_expansion_frontend_v1.py <fixture.hex> <fixture.json> <host-contract.json> <out-ir.json> <out-sidecar.json> <out-report.json>", file=sys.stderr)
        return 2
    try:
        words, source_hash = load_hex(argv[1])
        meta = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        contract = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        ir, sidecar, report = convert(meta, words, source_hash, contract)
        _write_json(argv[4], ir)
        _write_json(argv[5], sidecar)
        _write_json(argv[6], report)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, DecodeError, FrontendError) as exc:
        print(f"OPENRECOMP_MIPS32_EXPANSION_FRONTEND=FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"MIPS32_EXPANSION_FIXTURE={report['fixture_id']}")
    print(f"MIPS32_EXPANSION_ARCH={report['architecture']}")
    print(f"MIPS32_EXPANSION_FUNCTIONS={report['functions']}")
    print(f"MIPS32_EXPANSION_DELAY_SLOTS_LOWERED={report['delay_slots_lowered']}")
    print("OPENRECOMP_MIPS32_EXPANSION_FRONTEND=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
