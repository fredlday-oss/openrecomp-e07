#!/usr/bin/env python3
"""Fail-closed tests and deterministic synthetic proof for frontend scaffolding.

Proves `openrecomp/frontends/scaffold.py`:

- decode-contract validation fails closed;
- IRBuilder rejects each contract violation tested here at emit/build time;
- a synthetic 8-bit-style workload built purely through the scaffolding
  validates as frozen normalized IR V1, packages as Module Image V1 and
  executes through the architecture-neutral Core API reference executor with
  the pinned deterministic result below.

Expected trace of the synthetic proof (hand-derived, then pinned):

    entry:  (200 + 60) & 0xFF = 4  -> cpu:a = 4;  4 < 10  -> taken
    taken:  cpu:a = 4 + 1 = 5
    join:   mem[0] = 0x7A (122); 122 & 15 = 10; store 10 @ mem[1]
            mem[cpu:a=5] = 0x2B (43); eq(5,5) -> chosen = 43 -> cpu:a = 43
            call halve: 43 lshr 2 = 10 -> cpu:a = 10
    return 10; observed cpu:a = 10; memory[1] = 10
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor  # noqa: E402
from openrecomp.frontends.scaffold import IRBuilder, ScaffoldError, validate_decode  # noqa: E402

CONTRACT_PATH = ROOT / "contracts" / "host_contract.json"
SOURCE_BLOB = b"synthetic scaffold proof v1"
INPUT_SHA = hashlib.sha256(SOURCE_BLOB).hexdigest()
MEMORY_SIZE = 262144
SEGMENT = bytes([0x7A, 0x00, 0x33, 0x44, 0x55, 0x2B]) + bytes(10)

EXPECTED_OBSERVED = 10
EXPECTED_RETURN = 10
EXPECTED_MEMORY_AT_1 = 10
EXPECTED_MEMORY_AT_0 = 0x7A
EXPECTED_OPERATIONS = 27  # pinned after the first verified Core API run


def serialize(document: object) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_builder() -> IRBuilder:
    builder = IRBuilder(
        module_id="openrecomp.scaffold.synthetic.8bit-proof",
        architecture="synthetic-8bit",
        adapter="openrecomp.frontends.scaffold-v1",
        address_bits=32,
        endianness="little",
        input_sha256=INPUT_SHA,
        host_contract_version="0.1.1",
    )
    builder.declare_state_slot("cpu:a", "i8")
    builder.declare_state_slot("cpu:f", "i1")
    return builder


def build_proof() -> tuple[dict, dict]:
    builder = new_builder()
    builder.add_memory_segment("data", 0, SEGMENT, memory_size_bytes=MEMORY_SIZE)

    main = builder.add_function("main", 0x100, return_type="i8")

    entry = main.add_block("entry", 0x100)
    entry.const_result("%x", "i8", 200)
    entry.const_result("%y", "i8", 60)
    entry.binop("%sum", "i8", "add", entry.value("%x"), entry.value("%y"))
    entry.write_state("cpu:a", entry.value("%sum"))
    entry.compare("%lt", "ult", entry.value("%sum"), entry.const(10, "i8"))
    entry.branch(entry.value("%lt"), "taken", "fall")

    taken = main.add_block("taken", 0x104)
    taken.read_state("%a", "cpu:a")
    taken.const_result("%one", "i8", 1)
    taken.binop("%inc", "i8", "add", taken.value("%a"), taken.value("%one"))
    taken.write_state("cpu:a", taken.value("%inc"))
    taken.jump("join")

    fall = main.add_block("fall", 0x108)
    fall.const_result("%ff", "i8", 200)
    fall.write_state("cpu:a", fall.value("%ff"))
    fall.jump("join")

    join = main.add_block("join", 0x10C)
    join.read_state("%acc", "cpu:a")
    join.zext_to_address("%accaddr", join.value("%acc"))
    join.load("%mem", "i8", width_bits=8, signed=False, address=join.const(0, "i32"), alignment=1)
    join.binop("%masked", "i8", "and", join.value("%mem"), join.const(15, "i8"))
    join.store(width_bits=8, address=join.const(1, "i32"), value=join.value("%masked"), alignment=1)
    join.load("%b2", "i8", width_bits=8, signed=False, address=join.value("%accaddr"), alignment=1)
    join.compare("%eq", "eq", join.value("%acc"), join.const(5, "i8"))
    join.select("%chosen", "i8", join.value("%eq"), join.value("%b2"), join.value("%masked"))
    join.write_state("cpu:a", join.value("%chosen"))
    join.call("halve", [], result="%halved", result_type="i8")
    join.write_state("cpu:a", join.value("%halved"))
    join.ret(join.value("%halved"))

    dispatch = main.add_block("dispatch", 0x110)
    dispatch.read_state("%d", "cpu:a")
    dispatch.zext_to_address("%daddr", dispatch.value("%d"))
    dispatch.indirect_jump(dispatch.value("%daddr"), ["taken", "fall", "join"])

    unreachable = main.add_block("unreachable", 0x114)
    unreachable.trap("synthetic-proof-unreachable")

    halve = builder.add_function("halve", 0x200, return_type="i8")
    half_block = halve.add_block("half", 0x200)
    half_block.read_state("%v", "cpu:a")
    half_block.const_result("%c2", "i8", 2)
    half_block.binop("%h", "i8", "lshr", half_block.value("%v"), half_block.value("%c2"))
    half_block.ret(half_block.value("%h"))

    return builder.build(
        entry_function="main",
        memory_size_bytes=MEMORY_SIZE,
        initial_state={"cpu:a": 0, "cpu:f": 1},
        observe_state_slot="cpu:a",
        max_operations=10000,
    )


def build_manifest(ir: dict, ir_bytes: bytes, contract: dict, contract_bytes: bytes, sidecar: dict) -> dict:
    segments = []
    for segment in sorted(sidecar["memory_segments"], key=lambda item: (item["guest_address"], item["name"])):
        data = bytes.fromhex(segment["data_hex"])
        segments.append(
            {
                "name": segment["name"],
                "guest_address": segment["guest_address"],
                "data_hex": data.hex(),
                "data_sha256": digest(data),
            }
        )
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
        "memory": {"size_bytes": sidecar["memory_size_bytes"], "segments": segments},
        "initial_state": [
            {"slot": slot, "value": value} for slot, value in sorted(sidecar["initial_state"].items())
        ],
        "entry": {
            "function": ir["entry_function"],
            "observe_state_slot": sidecar["entry_state_slot"],
        },
        "limits": {"max_operations": sidecar["max_operations"], "max_call_depth": 1024},
        "provenance": {
            "producer": "openrecomp.frontends.scaffold-v1",
            "source_input_sha256": ir["source"]["input_sha256"],
        },
    }


def expect_fail(label: str, action, error_type=ScaffoldError) -> None:
    try:
        action()
    except error_type:
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"{label}: raised {type(exc).__name__} instead of {error_type.__name__}: {exc}") from exc
    raise AssertionError(f"{label}: accepted")


def main() -> int:
    tests = 0
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_bytes = CONTRACT_PATH.read_bytes()

    # --- negative: decode contract ------------------------------------
    expect_fail("decode-missing-op", lambda: validate_decode({"address": 0}))
    expect_fail("decode-negative-address", lambda: validate_decode({"address": -1, "op": "nop"}))
    expect_fail("decode-bool-address", lambda: validate_decode({"address": True, "op": "nop"}))
    expect_fail("decode-nonint-word", lambda: validate_decode({"address": 0, "op": "nop", "word": "x"}))
    expect_fail("decode-non-dict", lambda: validate_decode(7))  # type: ignore[arg-type]
    tests += 5

    # --- negative: builder emit-time ----------------------------------
    def fresh_block():
        builder = new_builder()
        function = builder.add_function("f", 0, return_type=None)
        return builder, function, function.add_block("b", 0)

    builder, function, block = fresh_block()
    expect_fail("write-undeclared-slot", lambda: block.write_state("cpu:z", block.const(1, "i8")))
    tests += 1

    builder, function, block = fresh_block()
    expect_fail(
        "unnormalized-shift-count",
        lambda: block.binop("r", "i8", "shl", block.const(1, "i8"), block.const(8, "i8")),
    )
    tests += 1

    builder, function, block = fresh_block()
    block.const_result("r", "i8", 1)
    expect_fail("duplicate-result-id", lambda: block.const_result("r", "i8", 2))
    tests += 1

    builder, function, block = fresh_block()
    expect_fail("undefined-value-operand", lambda: block.write_state("cpu:a", {"value": "%nope"}))
    tests += 1

    builder, function, block = fresh_block()
    expect_fail(
        "store-width-mismatch",
        lambda: block.store(width_bits=8, address=block.const(0, "i32"), value=block.const(1, "i16"), alignment=1),
    )
    tests += 1

    builder, function, block = fresh_block()
    expect_fail(
        "load-address-type",
        lambda: block.load("r", "i8", width_bits=8, signed=False, address=block.const(0, "i8"), alignment=1),
    )
    tests += 1

    builder, function, block = fresh_block()
    expect_fail("write-state-type-mismatch", lambda: block.write_state("cpu:a", block.const(1, "i16")))
    tests += 1

    builder, function, block = fresh_block()
    expect_fail("cast-zext-not-increasing", lambda: block.cast("r", "i8", "zext", block.const(1, "i8")))
    tests += 1

    builder, function, block = fresh_block()
    expect_fail(
        "compare-type-mismatch",
        lambda: block.compare("c", "eq", block.const(1, "i8"), block.const(1, "i16")),
    )
    tests += 1

    builder, function, block = fresh_block()
    expect_fail("host-call-undeclared-symbol", lambda: block.host_call("host_x", []))
    tests += 1

    builder, function, block = fresh_block()
    expect_fail("call-result-without-type", lambda: block.call("f", [], result="%r"))
    tests += 1

    builder, function, block = fresh_block()
    expect_fail("trap-without-reason", lambda: block.trap(""))
    tests += 1

    builder, function, block = fresh_block()
    expect_fail("instruction-after-terminator", lambda: (block.ret(None), block.const_result("r", "i8", 1)))
    tests += 1

    builder, function, block = fresh_block()
    expect_fail("duplicate-terminator", lambda: (block.ret(None), block.ret(None)))
    tests += 1

    # --- negative: builder build-time ---------------------------------
    def build_with(**overrides):
        options = {
            "entry_function": "main2",
            "memory_size_bytes": MEMORY_SIZE,
            "initial_state": {"cpu:a": 0},
            "observe_state_slot": "cpu:a",
            "max_operations": 100,
        }
        options.update(overrides)
        builder = new_builder()
        function = builder.add_function("main2", 0, return_type="i8")
        block = function.add_block("b", 0)
        block.const_result("r", "i8", 1)
        block.ret(block.value("r"))
        builder.build(**options)

    expect_fail("block-without-terminator", lambda: _build_missing_terminator(), ScaffoldError)
    tests += 1

    expect_fail("jump-to-unknown-block", lambda: _build_unknown_jump(), ScaffoldError)
    tests += 1

    expect_fail("segment-out-of-bounds", lambda: _build_oob_segment(), ScaffoldError)
    tests += 1

    expect_fail("initial-state-undeclared-slot", lambda: build_with(initial_state={"cpu:z": 1}), ScaffoldError)
    tests += 1

    expect_fail("entry-function-unknown", lambda: build_with(entry_function="ghost"), ScaffoldError)
    tests += 1

    expect_fail("observe-slot-undeclared", lambda: build_with(observe_state_slot="cpu:z"), ScaffoldError)
    tests += 1

    # --- positive: deterministic synthetic proof ----------------------
    ir_a, sidecar_a = build_proof()
    ir_b, sidecar_b = build_proof()
    if serialize(ir_a) != serialize(ir_b) or serialize(sidecar_a) != serialize(sidecar_b):
        raise AssertionError("scaffolding output is not byte-identical across two builds")
    print("PASS scaffolding-build-deterministic")
    tests += 1

    required_sidecar_keys = {
        "source_input_sha256",
        "memory_size_bytes",
        "initial_state",
        "memory_segments",
        "entry_state_slot",
        "max_operations",
    }
    missing = required_sidecar_keys - set(sidecar_a)
    if missing:
        raise AssertionError(f"sidecar missing keys: {sorted(missing)}")
    if sidecar_a["source_input_sha256"] != INPUT_SHA:
        raise AssertionError("sidecar source hash does not match the synthetic input")
    print("PASS sidecar-contract-shape")
    tests += 1

    ir_bytes = serialize(ir_a).encode("utf-8")
    manifest = build_manifest(ir_a, ir_bytes, contract, contract_bytes, sidecar_a)
    results = []
    executor_memory = None
    for _ in range(2):
        module = ModuleImage.from_documents(
            manifest,
            ir_a,
            contract,
            ir_sha256=digest(ir_bytes),
            contract_sha256=digest(contract_bytes),
        )
        host = CallbackHostBinding(contract["contract_version"], {})
        executor = ReferenceExecutor(module, host)
        execution = executor.run()
        results.append(execution)
        if executor_memory is None:
            executor_memory = executor.memory.data

    for run_number, execution in enumerate(results, 1):
        if execution.observed_state != EXPECTED_OBSERVED:
            raise AssertionError(f"run {run_number}: observed {execution.observed_state} != {EXPECTED_OBSERVED}")
        if execution.function_return != EXPECTED_RETURN:
            raise AssertionError(f"run {run_number}: return {execution.function_return} != {EXPECTED_RETURN}")
        if execution.operations != EXPECTED_OPERATIONS:
            raise AssertionError(
                f"run {run_number}: operations {execution.operations} != pinned {EXPECTED_OPERATIONS}"
            )
    assert executor_memory is not None
    if executor_memory[0] != EXPECTED_MEMORY_AT_0 or executor_memory[1] != EXPECTED_MEMORY_AT_1:
        raise AssertionError(f"memory after execution is {list(executor_memory[:2])}")
    if results[0].state != results[1].state:
        raise AssertionError("execution state differs across two runs")
    print(
        "PASS synthetic-proof observed=10 return=10 memory=[122,10] "
        f"operations={results[0].operations} deterministic"
    )
    tests += 1

    print(f"OPENRECOMP_FRONTEND_SCAFFOLD_V1=PASS tests={tests}")
    return 0


def _build_missing_terminator() -> None:
    builder = new_builder()
    function = builder.add_function("main2", 0, return_type="i8")
    function.add_block("b", 0).const_result("r", "i8", 1)
    builder.build(
        entry_function="main2",
        memory_size_bytes=MEMORY_SIZE,
        initial_state={},
        observe_state_slot="cpu:a",
        max_operations=100,
    )


def _build_unknown_jump() -> None:
    builder = new_builder()
    function = builder.add_function("main2", 0, return_type="i8")
    block = function.add_block("b", 0)
    block.const_result("r", "i8", 1)
    block.jump("ghost")
    builder.build(
        entry_function="main2",
        memory_size_bytes=MEMORY_SIZE,
        initial_state={},
        observe_state_slot="cpu:a",
        max_operations=100,
    )


def _build_oob_segment() -> None:
    builder = new_builder()
    builder.add_memory_segment("big", MEMORY_SIZE - 2, bytes(4), memory_size_bytes=MEMORY_SIZE)
    function = builder.add_function("main2", 0, return_type="i8")
    block = function.add_block("b", 0)
    block.const_result("r", "i8", 1)
    block.ret(block.value("r"))
    builder.build(
        entry_function="main2",
        memory_size_bytes=MEMORY_SIZE,
        initial_state={},
        observe_state_slot="cpu:a",
        max_operations=100,
    )


if __name__ == "__main__":
    raise SystemExit(main())
