#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor
from openrecomp.runtime import CoreRuntimeError
from tools.aot_c_backend_v1 import generate
from tools.aot_native_module_v1 import NativeAOTError, NativeAOTModule

MASK32 = 0xFFFFFFFF
EXPECTED_POSITIVE = 0x80000018
EXPECTED_BINOPS = {"add", "sub", "mul", "and", "or", "xor", "shl", "lshr", "ashr"}
EXPECTED_PREDS = {"eq", "ne", "ult", "ule", "ugt", "uge", "slt", "sle", "sgt", "sge"}
EXPECTED_CASTS = {"zext", "sext", "trunc", "bitcast"}
EXPECTED_OPS = {"const", "read_state", "write_state", "binop", "compare", "cast", "select", "load", "store", "call"}
EXPECTED_TERMINATORS = {"branch", "jump", "indirect_jump", "return", "trap"}


def jbytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def source_hash(name: str) -> str:
    return hashlib.sha256(("OPENRECOMP_AOT_HARDENING_V1:" + name).encode("ascii")).hexdigest()


def function(fid: str, address: int, blocks: list[dict], *, params: list[dict] | None = None, return_type: str | None = "i32") -> dict:
    return {
        "id": fid,
        "guest_address": address,
        "params": [] if params is None else params,
        "return_type": return_type,
        "blocks": blocks,
    }


def block(bid: str, address: int, instructions: list[dict], terminator: dict) -> dict:
    return {
        "id": bid,
        "guest_address": address,
        "instructions": instructions,
        "terminator": terminator,
    }


def ir_document(name: str, functions: list[dict], *, features: list[str] | None = None, hosts: list[str] | None = None, endianness: str = "little") -> dict:
    return {
        "ir_version": "1.0.0",
        "module_id": f"synthetic.aot-hardening.{name}",
        "source": {
            "architecture": "synthetic-ir-v1",
            "adapter": "openrecomp.aot-hardening-v1",
            "address_bits": 32,
            "endianness": endianness,
            "input_sha256": source_hash(name + ":" + endianness),
        },
        "required_features": ["core-v1"] if features is None else features,
        "host_contract_version": "0.1.1",
        "required_host_symbols": [] if hosts is None else hosts,
        "state_slots": [{"id": "state:out", "type": "i32"}],
        "entry_function": "main",
        "functions": functions,
    }


def make_module(ir: dict, contract: dict, contract_bytes: bytes, *, max_operations: int = 1000, max_call_depth: int = 8) -> ModuleImage:
    ir_bytes = jbytes(ir)
    ir_sha = hashlib.sha256(ir_bytes).hexdigest()
    contract_sha = hashlib.sha256(contract_bytes).hexdigest()
    manifest = {
        "module_format_version": "1.0.0",
        "module_id": ir["module_id"],
        "ir": {
            "version": ir["ir_version"],
            "sha256": ir_sha,
            "source_input_sha256": ir["source"]["input_sha256"],
        },
        "host_contract": {
            "version": contract["contract_version"],
            "sha256": contract_sha,
        },
        "memory": {
            "size_bytes": contract["memory"]["size_bytes"],
            "segments": [],
        },
        "initial_state": [{"slot": "state:out", "value": 0}],
        "entry": {
            "function": "main",
            "observe_state_slot": "state:out",
        },
        "limits": {
            "max_operations": max_operations,
            "max_call_depth": max_call_depth,
        },
        "provenance": {
            "producer": ir["source"]["adapter"],
            "source_input_sha256": ir["source"]["input_sha256"],
        },
    }
    return ModuleImage.from_documents(
        manifest,
        ir,
        contract,
        ir_sha256=ir_sha,
        contract_sha256=contract_sha,
    )


def positive_ir(endianness: str) -> dict:
    helper = function(
        "helper",
        0x2000,
        [
            block(
                "helper_entry",
                0x2000,
                [
                    {"op": "const", "result": "%three", "result_type": "i32", "value": 3},
                    {
                        "op": "binop",
                        "result": "%helper_mul",
                        "result_type": "i32",
                        "kind": "mul",
                        "lhs": {"value": "%p"},
                        "rhs": {"value": "%three"},
                    },
                ],
                {"op": "return", "value": {"value": "%helper_mul"}},
            )
        ],
        params=[{"id": "%p", "type": "i32"}],
    )

    ins: list[dict] = [
        {"op": "const", "result": "%a", "result_type": "i32", "value": 0x80000004},
        {"op": "const", "result": "%b", "result_type": "i32", "value": 4},
        {"op": "binop", "result": "%add", "result_type": "i32", "kind": "add", "lhs": {"value": "%a"}, "rhs": {"value": "%b"}},
        {"op": "binop", "result": "%sub", "result_type": "i32", "kind": "sub", "lhs": {"value": "%a"}, "rhs": {"value": "%b"}},
        {"op": "binop", "result": "%mul", "result_type": "i32", "kind": "mul", "lhs": {"value": "%b"}, "rhs": {"const": 7, "type": "i32"}},
        {"op": "binop", "result": "%and", "result_type": "i32", "kind": "and", "lhs": {"value": "%a"}, "rhs": {"const": 0xFF, "type": "i32"}},
        {"op": "binop", "result": "%or", "result_type": "i32", "kind": "or", "lhs": {"value": "%b"}, "rhs": {"const": 0x10, "type": "i32"}},
        {"op": "binop", "result": "%xor", "result_type": "i32", "kind": "xor", "lhs": {"value": "%a"}, "rhs": {"value": "%b"}},
        {"op": "const", "result": "%shift", "result_type": "i32", "value": 2},
        {"op": "binop", "result": "%shl", "result_type": "i32", "kind": "shl", "lhs": {"value": "%b"}, "rhs": {"value": "%shift"}},
        {"op": "binop", "result": "%lshr", "result_type": "i32", "kind": "lshr", "lhs": {"value": "%a"}, "rhs": {"value": "%shift"}},
        {"op": "binop", "result": "%ashr", "result_type": "i32", "kind": "ashr", "lhs": {"value": "%a"}, "rhs": {"value": "%shift"}},
    ]
    for pred, lhs, rhs in [
        ("eq", {"value": "%b"}, {"const": 4, "type": "i32"}),
        ("ne", {"value": "%a"}, {"value": "%b"}),
        ("ult", {"value": "%b"}, {"value": "%a"}),
        ("ule", {"value": "%b"}, {"value": "%a"}),
        ("ugt", {"value": "%a"}, {"value": "%b"}),
        ("uge", {"value": "%a"}, {"value": "%b"}),
        ("slt", {"value": "%a"}, {"value": "%b"}),
        ("sle", {"value": "%a"}, {"value": "%b"}),
        ("sgt", {"value": "%b"}, {"value": "%a"}),
        ("sge", {"value": "%b"}, {"value": "%a"}),
    ]:
        ins.append({"op": "compare", "result": f"%cmp_{pred}", "result_type": "i1", "predicate": pred, "lhs": lhs, "rhs": rhs})
    ins.extend([
        {"op": "const", "result": "%small", "result_type": "i8", "value": 0xF0},
        {"op": "cast", "result": "%zext", "result_type": "i32", "kind": "zext", "value": {"value": "%small"}},
        {"op": "cast", "result": "%sext", "result_type": "i32", "kind": "sext", "value": {"value": "%small"}},
        {"op": "cast", "result": "%trunc", "result_type": "i16", "kind": "trunc", "value": {"value": "%a"}},
        {"op": "cast", "result": "%bitcast", "result_type": "i32", "kind": "bitcast", "value": {"value": "%b"}},
        {"op": "select", "result": "%selected", "result_type": "i32", "condition": {"value": "%cmp_eq"}, "if_true": {"value": "%add"}, "if_false": {"value": "%sub"}},
        {"op": "const", "result": "%addr", "result_type": "i32", "value": 16},
        {"op": "store", "width_bits": 32, "address": {"value": "%addr"}, "value": {"value": "%selected"}, "alignment": 4, "misaligned_policy": "fault"},
        {"op": "load", "result": "%loaded", "result_type": "i32", "width_bits": 32, "signed": False, "address": {"value": "%addr"}, "alignment": 4, "misaligned_policy": "fault"},
        {"op": "const", "result": "%addr8", "result_type": "i32", "value": 20},
        {"op": "store", "width_bits": 8, "address": {"value": "%addr8"}, "value": {"value": "%small"}, "alignment": 1, "misaligned_policy": "fault"},
        {"op": "load", "result": "%signed_load", "result_type": "i32", "width_bits": 8, "signed": True, "address": {"value": "%addr8"}, "alignment": 1, "misaligned_policy": "fault"},
        {"op": "call", "callee": "helper", "args": [{"value": "%loaded"}], "result": "%called", "result_type": "i32"},
        {"op": "write_state", "slot": "state:out", "value": {"value": "%called"}},
        {"op": "compare", "result": "%branch_cond", "result_type": "i1", "predicate": "eq", "lhs": {"value": "%loaded"}, "rhs": {"value": "%selected"}},
    ])

    main = function(
        "main",
        0x1000,
        [
            block("entry", 0x1000, ins, {"op": "branch", "condition": {"value": "%branch_cond"}, "target_true": "after", "target_false": "trap_bad"}),
            block("after", 0x1080, [], {"op": "jump", "target": "dispatch"}),
            block("dispatch", 0x10C0, [{"op": "const", "result": "%target", "result_type": "i32", "value": 0x1100}], {"op": "indirect_jump", "target": {"value": "%target"}, "candidate_blocks": ["end"]}),
            block("trap_bad", 0x10E0, [], {"op": "trap", "reason": "unexpected hardening branch"}),
            block("end", 0x1100, [{"op": "read_state", "result": "%ret", "result_type": "i32", "slot": "state:out"}], {"op": "return", "value": {"value": "%ret"}}),
        ],
    )
    return ir_document(
        "positive",
        [main, helper],
        features=["core-v1", "bounded-indirect-jump"],
        endianness=endianness,
    )


def simple_ir(name: str, instructions: list[dict], terminator: dict, *, extra_blocks: list[dict] | None = None, features: list[str] | None = None, hosts: list[str] | None = None, extra_functions: list[dict] | None = None) -> dict:
    blocks = [block("entry", 0x1000, instructions, terminator)]
    if extra_blocks:
        blocks.extend(extra_blocks)
    functions = [function("main", 0x1000, blocks)]
    if extra_functions:
        functions.extend(extra_functions)
    return ir_document(name, functions, features=features, hosts=hosts)


def fault_cases(memory_size: int) -> list[tuple[str, dict, int, int, str]]:
    oob = simple_ir(
        "fault-memory-oob",
        [
            {"op": "const", "result": "%addr", "result_type": "i32", "value": memory_size},
            {"op": "load", "result": "%x", "result_type": "i32", "width_bits": 32, "signed": False, "address": {"value": "%addr"}, "alignment": 4, "misaligned_policy": "fault"},
        ],
        {"op": "return", "value": {"value": "%x"}},
    )
    misaligned = simple_ir(
        "fault-misaligned",
        [
            {"op": "const", "result": "%addr", "result_type": "i32", "value": 1},
            {"op": "load", "result": "%x", "result_type": "i32", "width_bits": 32, "signed": False, "address": {"value": "%addr"}, "alignment": 4, "misaligned_policy": "fault"},
        ],
        {"op": "return", "value": {"value": "%x"}},
    )
    op_limit = simple_ir(
        "fault-operation-limit",
        [
            {"op": "const", "result": "%x", "result_type": "i32", "value": 1},
            {"op": "write_state", "slot": "state:out", "value": {"value": "%x"}},
        ],
        {"op": "return", "value": {"value": "%x"}},
    )
    shift = simple_ir(
        "fault-shift-count",
        [
            {"op": "const", "result": "%x", "result_type": "i32", "value": 1},
            {"op": "binop", "result": "%y", "result_type": "i32", "kind": "shl", "lhs": {"value": "%x"}, "rhs": {"const": 32, "type": "i32"}},
        ],
        {"op": "return", "value": {"value": "%y"}},
    )
    trap = simple_ir("fault-trap", [], {"op": "trap", "reason": "hardening trap"})
    indirect = simple_ir(
        "fault-indirect-target",
        [{"op": "const", "result": "%target", "result_type": "i32", "value": 0x9999}],
        {"op": "indirect_jump", "target": {"value": "%target"}, "candidate_blocks": ["end"]},
        extra_blocks=[block("end", 0x1100, [{"op": "const", "result": "%x", "result_type": "i32", "value": 0}], {"op": "return", "value": {"value": "%x"}})],
        features=["core-v1", "bounded-indirect-jump"],
    )
    leaf = function("leaf", 0x3000, [block("leaf_entry", 0x3000, [{"op": "const", "result": "%leaf_x", "result_type": "i32", "value": 7}], {"op": "return", "value": {"value": "%leaf_x"}})])
    mid = function("mid", 0x2000, [block("mid_entry", 0x2000, [{"op": "call", "callee": "leaf", "args": [], "result": "%mid_x", "result_type": "i32"}], {"op": "return", "value": {"value": "%mid_x"}})])
    depth = simple_ir(
        "fault-call-depth",
        [{"op": "call", "callee": "mid", "args": [], "result": "%x", "result_type": "i32"}],
        {"op": "return", "value": {"value": "%x"}},
        extra_functions=[mid, leaf],
    )
    host_failure = simple_ir(
        "fault-host-failure",
        [
            {"op": "host_call", "symbol": "host_system", "args": []},
            {"op": "const", "result": "%x", "result_type": "i32", "value": 0},
        ],
        {"op": "return", "value": {"value": "%x"}},
        features=["core-v1", "host-call"],
        hosts=["host_system"],
    )
    host_void = simple_ir(
        "fault-host-void",
        [
            {"op": "host_call", "symbol": "host_system", "args": [], "result": "%h", "result_type": "i32"},
        ],
        {"op": "return", "value": {"value": "%h"}},
        features=["core-v1", "host-call"],
        hosts=["host_system"],
    )
    return [
        ("memory-oob", oob, 1000, 8, "memory-fault"),
        ("misalignment", misaligned, 1000, 8, "misalignment"),
        ("operation-limit", op_limit, 1, 8, "operation-limit"),
        ("shift-count", shift, 1000, 8, "shift-count"),
        ("trap", trap, 1000, 8, "trap"),
        ("indirect-target", indirect, 1000, 8, "indirect-target"),
        ("call-depth", depth, 1000, 1, "call-depth"),
        ("host-failure", host_failure, 1000, 8, "host-failure"),
        ("host-void", host_void, 1000, 8, "host-void"),
    ]


def classify_fault(message: str) -> str:
    text = message.lower()
    if "deterministic memory fault" in text:
        return "memory-fault"
    if "misalignment" in text:
        return "misalignment"
    if "operation limit exceeded" in text:
        return "operation-limit"
    if "shift count" in text:
        return "shift-count"
    if "hardening trap" in text:
        return "trap"
    if "indirect target" in text:
        return "indirect-target"
    if "call-depth limit exceeded" in text:
        return "call-depth"
    if "host call failed" in text:
        return "host-failure"
    if "returned void" in text:
        return "host-void"
    return "unknown"


def host_callbacks(case_name: str) -> dict[str, Callable[[list[int]], int | None]]:
    if case_name == "host-failure":
        def fail(_: list[int]) -> int | None:
            raise CoreRuntimeError("host call failed")
        return {"host_system": fail}
    if case_name == "host-void":
        return {"host_system": lambda _: None}
    return {}


def compile_shared(compiler: str, c_path: Path, so_path: Path) -> None:
    subprocess.run(
        [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared", str(c_path), "-o", str(so_path)],
        check=True,
    )


def run_reference(module: ModuleImage, case_name: str):
    host = CallbackHostBinding(module.host_contract["contract_version"], host_callbacks(case_name))
    executor = ReferenceExecutor(module, host)
    result = executor.run()
    return result, executor


def configure_native_host(native: NativeAOTModule, case_name: str) -> None:
    if case_name == "host-failure":
        native.set_host_callback(lambda _symbol, _args: (False, None))
    elif case_name == "host-void":
        native.set_host_callback(lambda _symbol, _args: (True, None))


def coverage(ir: dict) -> None:
    ops: set[str] = set()
    binops: set[str] = set()
    preds: set[str] = set()
    casts: set[str] = set()
    terms: set[str] = set()
    for fn in ir["functions"]:
        for b in fn["blocks"]:
            terms.add(b["terminator"]["op"])
            for insn in b["instructions"]:
                ops.add(insn["op"])
                if insn["op"] == "binop":
                    binops.add(insn["kind"])
                elif insn["op"] == "compare":
                    preds.add(insn["predicate"])
                elif insn["op"] == "cast":
                    casts.add(insn["kind"])
    if not EXPECTED_OPS <= ops:
        raise AssertionError(f"positive fixture lost op coverage: {sorted(EXPECTED_OPS - ops)}")
    if binops != EXPECTED_BINOPS:
        raise AssertionError(f"positive fixture binop coverage mismatch: {sorted(binops)}")
    if not EXPECTED_PREDS <= preds:
        raise AssertionError(f"positive fixture compare coverage mismatch: {sorted(EXPECTED_PREDS - preds)}")
    if casts != EXPECTED_CASTS:
        raise AssertionError(f"positive fixture cast coverage mismatch: {sorted(casts)}")
    if terms != EXPECTED_TERMINATORS:
        raise AssertionError(f"positive fixture terminator coverage mismatch: {sorted(terms)}")


def positive_gate(contract: dict, contract_bytes: bytes, compilers: list[str], out_dir: Path) -> dict:
    summary: dict[str, dict] = {}
    for endianness in ("little", "big"):
        ir = positive_ir(endianness)
        coverage(ir)
        module = make_module(ir, contract, contract_bytes)
        c_text = generate(module)
        if c_text != generate(module):
            raise AssertionError("AOT hardening fixture generation is not deterministic")
        c_path = out_dir / f"positive-{endianness}.c"
        ir_path = out_dir / f"positive-{endianness}.ir.json"
        module_path = out_dir / f"positive-{endianness}.module.json"
        c_path.write_text(c_text, encoding="utf-8", newline="\n")
        ir_path.write_bytes(jbytes(ir))
        module_path.write_bytes(jbytes(module.manifest))

        ref, executor = run_reference(module, "positive")
        if ref.observed_state != EXPECTED_POSITIVE or ref.function_return != EXPECTED_POSITIVE:
            raise AssertionError(f"positive {endianness} reference result changed: {ref}")
        memory = bytes(executor.memory.data[16:21])
        expected_word = (0x80000008).to_bytes(4, endianness) + bytes([0xF0])
        if memory != expected_word:
            raise AssertionError(f"positive {endianness} memory mismatch: {memory.hex()} != {expected_word.hex()}")

        compiler_results: dict[str, dict] = {}
        for compiler in compilers:
            so_path = out_dir / f"positive-{endianness}-{Path(compiler).name}.so"
            compile_shared(compiler, c_path, so_path)
            native = NativeAOTModule(so_path)
            native.run()
            actual = {
                "observed_state": native.observed_state,
                "function_return": native.function_return,
                "operations": native.operations,
                "state": native.state_snapshot(),
                "memory_hex": native.memory(16, 5).hex(),
            }
            expected = {
                "observed_state": ref.observed_state,
                "function_return": ref.function_return,
                "operations": ref.operations,
                "state": ref.state,
                "memory_hex": memory.hex(),
            }
            if actual != expected:
                raise AssertionError(f"positive {endianness}/{compiler} differs from Core API: {actual} != {expected}")
            compiler_results[compiler] = actual
        summary[endianness] = {
            "reference": {
                "observed_state": ref.observed_state,
                "function_return": ref.function_return,
                "operations": ref.operations,
                "state": ref.state,
                "memory_hex": memory.hex(),
            },
            "compilers": compiler_results,
        }
    return summary


def fault_gate(contract: dict, contract_bytes: bytes, compilers: list[str], out_dir: Path) -> list[dict]:
    report: list[dict] = []
    for name, ir, max_ops, max_depth, expected_category in fault_cases(contract["memory"]["size_bytes"]):
        module = make_module(ir, contract, contract_bytes, max_operations=max_ops, max_call_depth=max_depth)
        try:
            run_reference(module, name)
        except CoreRuntimeError as exc:
            reference_message = str(exc)
        else:
            raise AssertionError(f"fault case {name} unexpectedly passed Core API")
        if classify_fault(reference_message) != expected_category:
            raise AssertionError(f"fault case {name} Core API category mismatch: {reference_message}")

        c_path = out_dir / f"fault-{name}.c"
        c_path.write_text(generate(module), encoding="utf-8", newline="\n")
        per_compiler: dict[str, str] = {}
        for compiler in compilers:
            so_path = out_dir / f"fault-{name}-{Path(compiler).name}.so"
            compile_shared(compiler, c_path, so_path)
            native = NativeAOTModule(so_path)
            configure_native_host(native, name)
            try:
                native.run()
            except NativeAOTError as exc:
                aot_message = str(exc)
            else:
                raise AssertionError(f"fault case {name}/{compiler} unexpectedly passed AOT")
            if classify_fault(aot_message) != expected_category:
                raise AssertionError(f"fault case {name}/{compiler} category mismatch: {aot_message}")
            per_compiler[compiler] = aot_message
        report.append({
            "case": name,
            "category": expected_category,
            "core_api": reference_message,
            "aot": per_compiler,
        })
        print(f"PASS fault-equivalence: {name} -> {expected_category}")
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", action="append", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    contract_path = ROOT / "contracts" / "host_contract.json"
    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes)

    try:
        positive = positive_gate(contract, contract_bytes, args.compiler, out_dir)
        faults = fault_gate(contract, contract_bytes, args.compiler, out_dir)
        report = {
            "frontier": "OPENRECOMP_AOT_HARDENING_V1",
            "expected_positive": EXPECTED_POSITIVE,
            "compilers": args.compiler,
            "positive": positive,
            "faults": faults,
        }
        (out_dir / "RESULT.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, AssertionError, subprocess.CalledProcessError) as exc:
        print(f"OPENRECOMP_AOT_HARDENING_V1=FAIL: {exc}", file=sys.stderr)
        return 2

    print(f"AOT_HARDENING_POSITIVE={EXPECTED_POSITIVE}")
    print(f"AOT_HARDENING_FAULT_CASES={len(faults)}")
    print("OPENRECOMP_AOT_HARDENING_WARNING_CLEAN=PASS")
    print("OPENRECOMP_AOT_HARDENING_FAULT_EQUIVALENCE=PASS")
    print("OPENRECOMP_AOT_HARDENING_V1=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
