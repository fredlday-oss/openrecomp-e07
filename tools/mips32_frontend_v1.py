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


class FrontendError(ValueError):
    pass


def _u32(value: int) -> int:
    return value & MASK32


def _slot(reg: int) -> str:
    return f"gpr:r{reg}"


def _tmp(address: int, tag: str) -> str:
    return f"%m{address:08x}_{tag}"


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


def _read_reg(out: list[dict], address: int, reg: int, tag: str) -> dict:
    if reg == 0:
        return {"const": 0, "type": "i32"}
    result = _tmp(address, tag)
    out.append(
        {
            "op": "read_state",
            "result": result,
            "result_type": "i32",
            "slot": _slot(reg),
            "source_address": address,
        }
    )
    return {"value": result}


def _write_reg(out: list[dict], address: int, reg: int, value: dict) -> None:
    if reg == 0:
        return
    out.append(
        {
            "op": "write_state",
            "slot": _slot(reg),
            "value": value,
            "source_address": address,
        }
    )


def _lower_simple(out: list[dict], insn: dict) -> None:
    address = insn["address"]
    op = insn["op"]

    if op == "nop":
        return

    if op == "addiu":
        lhs = _read_reg(out, address, insn["rs"], "rs")
        result = _tmp(address, "addiu")
        out.append(
            {
                "op": "binop",
                "result": result,
                "result_type": "i32",
                "kind": "add",
                "lhs": lhs,
                "rhs": {"const": _u32(insn["imm"]), "type": "i32"},
                "source_address": address,
            }
        )
        _write_reg(out, address, insn["rt"], {"value": result})
        return

    if op == "ori":
        lhs = _read_reg(out, address, insn["rs"], "rs")
        result = _tmp(address, "ori")
        out.append(
            {
                "op": "binop",
                "result": result,
                "result_type": "i32",
                "kind": "or",
                "lhs": lhs,
                "rhs": {"const": insn["imm"], "type": "i32"},
                "source_address": address,
            }
        )
        _write_reg(out, address, insn["rt"], {"value": result})
        return

    if op == "lui":
        result = _tmp(address, "lui")
        out.append(
            {
                "op": "const",
                "result": result,
                "result_type": "i32",
                "value": _u32(insn["imm"] << 16),
                "source_address": address,
            }
        )
        _write_reg(out, address, insn["rt"], {"value": result})
        return

    if op == "addu":
        lhs = _read_reg(out, address, insn["rs"], "rs")
        rhs = _read_reg(out, address, insn["rt"], "rt")
        result = _tmp(address, "addu")
        out.append(
            {
                "op": "binop",
                "result": result,
                "result_type": "i32",
                "kind": "add",
                "lhs": lhs,
                "rhs": rhs,
                "source_address": address,
            }
        )
        _write_reg(out, address, insn["rd"], {"value": result})
        return

    if op in {"slt", "sltu"}:
        lhs = _read_reg(out, address, insn["rs"], "rs")
        rhs = _read_reg(out, address, insn["rt"], "rt")
        flag = _tmp(address, "cmp")
        out.append(
            {
                "op": "compare",
                "result": flag,
                "result_type": "i1",
                "predicate": "slt" if op == "slt" else "ult",
                "lhs": lhs,
                "rhs": rhs,
                "source_address": address,
            }
        )
        widened = _tmp(address, "cmp_i32")
        out.append(
            {
                "op": "cast",
                "result": widened,
                "result_type": "i32",
                "kind": "zext",
                "value": {"value": flag},
                "source_address": address,
            }
        )
        _write_reg(out, address, insn["rd"], {"value": widened})
        return

    if op in {"lw", "sw"}:
        base = _read_reg(out, address, insn["rs"], "base")
        effective = _tmp(address, "addr")
        out.append(
            {
                "op": "binop",
                "result": effective,
                "result_type": "i32",
                "kind": "add",
                "lhs": base,
                "rhs": {"const": _u32(insn["imm"]), "type": "i32"},
                "source_address": address,
            }
        )
        if op == "lw":
            loaded = _tmp(address, "load")
            out.append(
                {
                    "op": "load",
                    "result": loaded,
                    "result_type": "i32",
                    "width_bits": 32,
                    "signed": True,
                    "address": {"value": effective},
                    "alignment": 4,
                    "misaligned_policy": "fault",
                    "source_address": address,
                }
            )
            _write_reg(out, address, insn["rt"], {"value": loaded})
        else:
            value = _read_reg(out, address, insn["rt"], "store_value")
            out.append(
                {
                    "op": "store",
                    "width_bits": 32,
                    "address": {"value": effective},
                    "value": value,
                    "alignment": 4,
                    "misaligned_policy": "fault",
                    "source_address": address,
                }
            )
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


def _collect_leaders(
    function: dict,
    end: int,
    words: dict[int, int],
    function_by_address: dict[int, dict],
) -> tuple[set[int], set[int]]:
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
            raise FrontendError(f"0x{address:x}: control transfer in delay slot is outside V1 slice")
        delay_slots.add(delay)

        if insn["op"] in {"beq", "bne"}:
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
        elif insn["op"] == "jr":
            if insn["rs"] != 31:
                raise FrontendError(f"0x{address:x}: only jr $ra is supported in the V1 slice")

    bad = sorted(leaders & delay_slots)
    if bad:
        raise FrontendError("control-flow target enters delay slot: " + ", ".join(f"0x{x:x}" for x in bad))
    return leaders, delay_slots


def _convert_function(
    function: dict,
    end: int,
    words: dict[int, int],
    function_by_address: dict[int, dict],
) -> tuple[dict, int]:
    start = function["address"]
    leaders, delay_slots = _collect_leaders(function, end, words, function_by_address)
    ordered_leaders = sorted(leaders)
    blocks: list[dict] = []
    delay_count = 0

    for leader in ordered_leaders:
        instructions: list[dict] = []
        address = leader
        terminator: dict | None = None

        while address < end:
            if address != leader and address in leaders:
                terminator = {
                    "op": "jump",
                    "target": _block_id(address),
                    "source_address": address - 4,
                }
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

            if insn["op"] in {"beq", "bne"}:
                lhs = _read_reg(instructions, address, insn["rs"], "branch_lhs")
                rhs = _read_reg(instructions, address, insn["rt"], "branch_rhs")
                condition = _tmp(address, "branch_cond")
                instructions.append(
                    {
                        "op": "compare",
                        "result": condition,
                        "result_type": "i1",
                        "predicate": "eq" if insn["op"] == "beq" else "ne",
                        "lhs": lhs,
                        "rhs": rhs,
                        "source_address": address,
                    }
                )
                _lower_simple(instructions, delay_insn)
                terminator = {
                    "op": "branch",
                    "condition": {"value": condition},
                    "target_true": _block_id(insn["target"]),
                    "target_false": _block_id(address + 8),
                    "source_address": address,
                }

            elif insn["op"] == "jal":
                callee = function_by_address[insn["target"]]
                _write_reg(
                    instructions,
                    address,
                    31,
                    {"const": _u32(address + 8), "type": "i32"},
                )
                _lower_simple(instructions, delay_insn)
                instructions.append(
                    {
                        "op": "call",
                        "callee": callee["id"],
                        "args": [],
                        "source_address": address,
                    }
                )
                terminator = {
                    "op": "jump",
                    "target": _block_id(address + 8),
                    "source_address": address,
                }

            elif insn["op"] == "j":
                _lower_simple(instructions, delay_insn)
                terminator = {
                    "op": "jump",
                    "target": _block_id(insn["target"]),
                    "source_address": address,
                }

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

        blocks.append(
            {
                "id": _block_id(leader),
                "guest_address": leader,
                "instructions": instructions,
                "terminator": terminator,
            }
        )

    return (
        {
            "id": function["id"],
            "guest_address": start,
            "params": [],
            "return_type": None,
            "blocks": blocks,
        },
        delay_count,
    )


def convert(meta: dict, words: dict[int, int], source_sha256: str, contract: dict) -> tuple[dict, dict, dict]:
    if meta.get("fixture_version") != FRONTEND_VERSION:
        raise FrontendError("unsupported MIPS32 fixture version")
    if meta.get("architecture") != "mips32-le":
        raise FrontendError("vertical slice requires mips32-le")
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

    ir = {
        "ir_version": "1.0.0",
        "module_id": "openrecomp.mips32.synthetic.vertical-slice-v1",
        "source": {
            "architecture": "mips32-le",
            "adapter": "openrecomp.mips32-v1-slice",
            "address_bits": 32,
            "endianness": "little",
            "input_sha256": source_sha256,
        },
        "required_features": ["core-v1"],
        "host_contract_version": contract["contract_version"],
        "required_host_symbols": [],
        "state_slots": [{"id": _slot(reg), "type": "i32"} for reg in range(1, 32)],
        "entry_function": entry["id"],
        "functions": converted_functions,
    }

    for slot in meta["initial_state"]:
        if slot not in {item["id"] for item in ir["state_slots"]}:
            raise FrontendError(f"initial state references undeclared slot {slot}")
    if meta["observe_state_slot"] not in {item["id"] for item in ir["state_slots"]}:
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
        "architecture": "mips32-le",
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
        print(
            "usage: mips32_frontend_v1.py <fixture.hex> <fixture.json> <host-contract.json> <out-ir.json> <out-sidecar.json> <out-report.json>",
            file=sys.stderr,
        )
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
        print(f"OPENRECOMP_MIPS32_FRONTEND_V1=FAIL: {exc}", file=sys.stderr)
        return 2

    print(f"MIPS32_FRONTEND_FUNCTIONS={report['functions']}")
    print(f"MIPS32_DELAY_SLOTS_LOWERED={report['delay_slots_lowered']}")
    print("OPENRECOMP_MIPS32_FRONTEND_V1=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
