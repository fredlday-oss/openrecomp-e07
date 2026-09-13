#!/usr/bin/env python3
"""Fail-closed tests for OpenRecomp Shared Program Model V1 (P2-01).

Proves `openrecomp/program_model.py` with deterministic, architecture-neutral
coverage:

1.  straight-line basic block, with a 64-bit address (beyond 32 bits);
2.  conditional branch with two successors (real NES 6502 decode);
3.  direct call between functions (`jsr`) and the direct call graph;
4.  unresolved control flow: indirect call site and indirect jump;
5.  evidence classification (default CANDIDATE, PROVEN survives serialization);
6.  deterministic serialization / round-trip / fingerprint / ordering;
7.  JSON Schema conformance and the CLI validator;
8.  graph-consistency rejections (all fail closed);
9.  adapter fail-closed propagation for an undocumented encoding.

The model is structural only: no guest semantics are introduced and frozen IR V1
is untouched.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import jsonschema  # noqa: E402

from adapters import nes6502  # noqa: E402
from openrecomp.program_model import (  # noqa: E402
    BasicBlock,
    DecodedInstruction,
    EdgeKind,
    EvidenceClass,
    FunctionUnit,
    InstructionFlow,
    ProgramModel,
    ProgramModelError,
    ProgramSource,
    Successor,
    UnresolvedSite,
    instruction_from_adapter,
)
from validate_program_model_v1 import load_and_validate  # noqa: E402

SCHEMA = json.loads((ROOT / "schema" / "openrecomp-program-v1.schema.json").read_text(encoding="utf-8"))
CAND = EvidenceClass.CANDIDATE
PROV = EvidenceClass.PROVEN


def insn(address, op, *, size=None, flow=InstructionFlow.NORMAL, target=None, unresolved=False, evidence=CAND, metadata=None):
    return DecodedInstruction(address, op, size, flow, target, unresolved, evidence, metadata or {})


def flow_for(decoded):
    op = decoded["op"]
    if op in {"rts", "rti", "brk"}:
        return InstructionFlow.RETURN
    if nes6502.is_branch(decoded):
        return InstructionFlow.BRANCH
    if op == "jsr":
        return InstructionFlow.CALL
    if op == "jmp":
        return InstructionFlow.JUMP if isinstance(decoded.get("target"), int) else InstructionFlow.INDIRECT_JUMP
    return InstructionFlow.NORMAL


def nes_code(base, blob):
    code = bytearray(0x10000)
    code[base : base + len(blob)] = blob
    return code


def expect_fail(label, thunk, error_type=ProgramModelError):
    try:
        thunk()
    except error_type:
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"{label}: raised {type(exc).__name__} instead of {error_type.__name__}: {exc}") from exc
    raise AssertionError(f"{label}: accepted")


def check(label, condition):
    if not condition:
        raise AssertionError(f"{label}: condition failed")
    print(f"PASS: {label}")


# --------------------------------------------------------------------------
# 1. straight-line block with a 64-bit address
# --------------------------------------------------------------------------
def build_linear_64():
    block_a = BasicBlock(
        "blk_a",
        0x1_0000_0000,
        (insn(0x1_0000_0000, "mov", size=4), insn(0x1_0000_0004, "add", size=4)),
        (Successor(EdgeKind.FALLTHROUGH, target_block="blk_b", target_address=0x1_0000_0008, evidence=PROV),),
        evidence=PROV,
    )
    block_b = BasicBlock(
        "blk_b",
        0x1_0000_0008,
        (insn(0x1_0000_0008, "ret", size=4, flow=InstructionFlow.RETURN, evidence=PROV),),
        (),
        evidence=PROV,
    )
    function = FunctionUnit("fn_big", 0x1_0000_0000, (block_a, block_b), evidence=PROV)
    return ProgramModel(
        ProgramSource("synthetic-64", adapter="openrecomp.synthetic", address_width_bits=64, endianness="big"),
        [function],
        "fn_big",
    )


# --------------------------------------------------------------------------
# 2/3. NES 6502 decode: branch and direct call
# --------------------------------------------------------------------------
def build_nes_branch():
    code = nes_code(0x8000, bytes([0xA9, 0x05, 0xF0, 0x02, 0xEA, 0x60, 0x60]))
    lda = instruction_from_adapter(nes6502.decode_full(code, 0x8000), flow=flow_for(nes6502.decode_full(code, 0x8000)))
    beq = instruction_from_adapter(nes6502.decode_full(code, 0x8002), flow=InstructionFlow.BRANCH)
    nop = instruction_from_adapter(nes6502.decode_full(code, 0x8004), flow=flow_for(nes6502.decode_full(code, 0x8004)))
    rts_1 = instruction_from_adapter(nes6502.decode_full(code, 0x8005), flow=InstructionFlow.RETURN)
    rts_2 = instruction_from_adapter(nes6502.decode_full(code, 0x8006), flow=InstructionFlow.RETURN)

    block_a = BasicBlock(
        "blk_8000",
        0x8000,
        (lda, beq),
        (
            Successor(EdgeKind.BRANCH_TAKEN, target_block="blk_8006", target_address=0x8006),
            Successor(EdgeKind.BRANCH_NOT_TAKEN, target_block="blk_8004", target_address=0x8004),
        ),
    )
    block_b = BasicBlock("blk_8004", 0x8004, (nop, rts_1))
    block_c = BasicBlock("blk_8006", 0x8006, (rts_2,))
    function = FunctionUnit("fn_8000", 0x8000, (block_a, block_b, block_c))
    return ProgramModel(ProgramSource("nes6502", adapter="openrecomp.nes6502", address_width_bits=16), [function], "fn_8000")


def build_nes_call():
    code = nes_code(0x8000, bytes([0x20, 0x00, 0x90, 0x60]))
    code[0x9000] = 0x60
    jsr = instruction_from_adapter(nes6502.decode_full(code, 0x8000), flow=InstructionFlow.CALL)
    caller_rts = instruction_from_adapter(nes6502.decode_full(code, 0x8003), flow=InstructionFlow.RETURN)
    callee_rts = instruction_from_adapter(nes6502.decode_full(code, 0x9000), flow=InstructionFlow.RETURN)

    caller = BasicBlock("blk_main", 0x8000, (jsr,), (Successor(EdgeKind.CALL_RETURN, target_block="blk_ret", target_address=0x8003),))
    ret = BasicBlock("blk_ret", 0x8003, (caller_rts,))
    callee = BasicBlock("blk_callee", 0x9000, (callee_rts,))
    fn_main = FunctionUnit("fn_main", 0x8000, (caller, ret), direct_callees=("fn_9000",))
    fn_9000 = FunctionUnit("fn_9000", 0x9000, (callee,))
    return ProgramModel(
        ProgramSource("nes6502", adapter="openrecomp.nes6502", address_width_bits=16),
        [fn_main, fn_9000],
        "fn_main",
    )


# --------------------------------------------------------------------------
# 4. unresolved control flow
# --------------------------------------------------------------------------
def build_unresolved():
    u_call = insn(0x100, "call_ix", size=2, flow=InstructionFlow.INDIRECT_CALL, unresolved=True)
    cont = insn(0x102, "ret", size=1, flow=InstructionFlow.RETURN)
    blk_call = BasicBlock("blk_ucall", 0x100, (u_call,), (Successor(EdgeKind.CALL_RETURN, target_block="blk_cont", target_address=0x102),))
    blk_cont = BasicBlock("blk_cont", 0x102, (cont,))
    fn_call = FunctionUnit(
        "fn_ucall",
        0x100,
        (blk_call, blk_cont),
        unresolved_call_sites=(UnresolvedSite("blk_ucall", 0x100, "call_ix", "computed call target"),),
    )

    u_jump = insn(0x200, "jmp_ix", size=2, flow=InstructionFlow.INDIRECT_JUMP, unresolved=True)
    blk_jump = BasicBlock(
        "blk_ujump",
        0x200,
        (u_jump,),
        (Successor(EdgeKind.INDIRECT, resolved=False, detail="setjmp table not statically recoverable"),),
    )
    fn_jump = FunctionUnit("fn_ujump", 0x200, (blk_jump,))
    return ProgramModel(ProgramSource("synthetic-unresolved"), [fn_call, fn_jump], "fn_ucall")


def main() -> int:
    tests = 0

    # --- 1. linear 64-bit ----------------------------------------------------
    model64 = build_linear_64()
    check("64bit-address-preserved", model64.function("fn_big").entry_address == 0x1_0000_0000)
    check("64bit-lookup", model64.lookup(0x1_0000_0008) == {"address": 0x1_0000_0008, "function": "fn_big", "block": "blk_b"})
    check("64bit-predecessor", model64.predecessor_map()["blk_b"] == ({"from": "blk_a", "function": "fn_big", "kind": "FALLTHROUGH"},))
    tests += 3

    # --- 2. NES branch -------------------------------------------------------
    nes = build_nes_branch()
    branch_block = nes.block("blk_8000")
    check("branch-two-successors", len(branch_block.successors) == 2)
    check("branch-terminal-classification", branch_block.terminal_flow() == InstructionFlow.BRANCH)
    check("branch-variable-length-size", nes.block("blk_8000").instructions[0].size_bytes == 2 and nes.block("blk_8004").instructions[0].size_bytes == 1)
    check("branch-predecessors", {item["from"] for item in nes.predecessor_map()["blk_8006"]} == {"blk_8000"})
    check("branch-adapter-unresolved-false", nes.block("blk_8000").instructions[1].unresolved is False)
    tests += 5

    # --- 3. direct call ------------------------------------------------------
    call = build_nes_call()
    check("direct-call-graph", call.direct_call_graph() == ({"from": "fn_main", "to": "fn_9000"},))
    check("direct-call-callee-recorded", call.function("fn_main").direct_callees == ("fn_9000",))
    check("direct-call-no-unresolved", call.unresolved_inventory() == ())
    tests += 3

    # --- 4. unresolved -------------------------------------------------------
    unresolved = build_unresolved()
    inventory = unresolved.unresolved_inventory()
    check("unresolved-count", len(inventory) == 2)
    check("unresolved-call-kind", any(item["kind"] == "INDIRECT_CALL" for item in inventory))
    check("unresolved-jump-kind", any(item["kind"] == "INDIRECT_JUMP" for item in inventory))
    check("unresolved-excluded-from-direct-call-graph", unresolved.direct_call_graph() == ())
    tests += 4

    # --- 5. evidence classification -----------------------------------------
    default_block = BasicBlock("b", 0, (insn(0, "nop", size=1),))
    default_function = FunctionUnit("f", 0, (default_block,))
    default_model = ProgramModel(ProgramSource("synthetic"), [default_function], "f")
    check("default-evidence-candidate", default_model.block("b").evidence == CAND and default_model.function("f").evidence == CAND)
    check("default-instruction-candidate", default_model.block("b").instructions[0].evidence == CAND)
    check("adapter-default-candidate", instruction_from_adapter({"address": 0, "op": "nop", "length": 1}).evidence == CAND)
    restored = ProgramModel.deserialize(model64.serialize())
    check("proven-survives-serialization", restored.function("fn_big").evidence == PROV and restored.block("blk_b").instructions[0].evidence == PROV)
    tests += 4

    # --- 6. determinism ------------------------------------------------------
    again = build_linear_64()
    check("deterministic-serialize", model64.serialize() == again.serialize())
    check("roundtrip-bytes", ProgramModel.deserialize(model64.serialize()).serialize() == model64.serialize())
    check("fingerprint-stable", model64.fingerprint() == ProgramModel.deserialize(model64.serialize()).fingerprint())
    f_reversed = ProgramModel(ProgramSource("synthetic-order"), [FunctionUnit("f2", 0x20, (BasicBlock("b2", 0x20, (insn(0x20, "nop"),)),)), FunctionUnit("f1", 0x10, (BasicBlock("b1", 0x10, (insn(0x10, "nop"),)),))], "f1")
    f_ordered = ProgramModel(ProgramSource("synthetic-order"), [FunctionUnit("f1", 0x10, (BasicBlock("b1", 0x10, (insn(0x10, "nop"),)),)), FunctionUnit("f2", 0x20, (BasicBlock("b2", 0x20, (insn(0x20, "nop"),)),))], "f1")
    check("order-independent-serialize", f_reversed.serialize() == f_ordered.serialize())
    tests += 4

    # --- 7. schema + CLI validator ------------------------------------------
    for label, model in (("linear64", model64), ("nes-branch", nes), ("nes-call", call), ("unresolved", unresolved)):
        jsonschema.validate(model.to_document(), SCHEMA)
        print(f"PASS schema: {label}")
        tests += 1
    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "good.json"
        good.write_text(json.dumps(call.to_document(), indent=2), encoding="utf-8")
        check("cli-valid", load_and_validate(good) is not None)
        bad = Path(tmp) / "bad.json"
        document = call.to_document()
        document["functions"][0]["blocks"][0]["instructions"][0]["flow"] = "NOPE"
        bad.write_text(json.dumps(document), encoding="utf-8")
        expect_fail("cli-schema-reject", lambda: load_and_validate(bad), jsonschema.ValidationError)
        tests += 2

    # --- 8. graph-consistency rejections ------------------------------------
    def linear():
        return build_linear_64()

    def dup_block():
        m = linear()
        function = m.functions[0]
        duplicate = BasicBlock("blk_a", 0x1_0000_0010, (insn(0x1_0000_0010, "nop"),))
        ProgramModel(m.source, [FunctionUnit(function.id, function.entry_address, (function.blocks[0], duplicate))], function.id)

    def dup_function():
        m = linear()
        f = m.functions[0]
        ProgramModel(m.source, [f, FunctionUnit(f.id, 0x2_0000_0000, (BasicBlock("x", 0x2_0000_0000, (insn(0x2_0000_0000, "nop"),)),))], f.id)

    def dangling_successor():
        block = BasicBlock("a", 0, (insn(0, "jmp", size=1, flow=InstructionFlow.JUMP, target=4),), (Successor(EdgeKind.JUMP, target_block="nope"),))
        ProgramModel(ProgramSource("s"), [FunctionUnit("f", 0, (block,))], "f")

    def target_address_mismatch():
        block = BasicBlock("a", 0, (insn(0, "jmp", size=1, flow=InstructionFlow.JUMP, target=4),), (Successor(EdgeKind.JUMP, target_block="b", target_address=999),))
        b = BasicBlock("b", 4, (insn(4, "nop"),))
        ProgramModel(ProgramSource("s"), [FunctionUnit("f", 0, (block, b))], "f")

    def unknown_callee():
        block = BasicBlock("a", 0, (insn(0, "call", size=1, flow=InstructionFlow.CALL, target=8),), (Successor(EdgeKind.CALL_RETURN, target_block="a"),))
        ProgramModel(ProgramSource("s"), [FunctionUnit("f", 0, (block,), direct_callees=("ghost",))], "f")

    def bad_function_entry():
        a = BasicBlock("a", 0x10, (insn(0x10, "nop"),))
        ProgramModel(ProgramSource("s"), [FunctionUnit("f", 0, (a,))], "f")

    def return_with_successor():
        a = BasicBlock("a", 0, (insn(0, "ret", size=1, flow=InstructionFlow.RETURN),), (Successor(EdgeKind.JUMP, target_block="a"),))
        ProgramModel(ProgramSource("s"), [FunctionUnit("f", 0, (a,))], "f")

    def branch_one_successor():
        a = BasicBlock("a", 0, (insn(0, "beq", size=1, flow=InstructionFlow.BRANCH, target=4),), (Successor(EdgeKind.BRANCH_TAKEN, target_block="a"),))
        ProgramModel(ProgramSource("s"), [FunctionUnit("f", 0, (a,))], "f")

    def call_without_return_edge():
        a = BasicBlock("a", 0, (insn(0, "call", size=1, flow=InstructionFlow.CALL, target=4),), (Successor(EdgeKind.FALLTHROUGH, target_block="a"),))
        ProgramModel(ProgramSource("s"), [FunctionUnit("f", 0, (a,))], "f")

    def indirect_jump_resolved():
        a = BasicBlock("a", 0, (insn(0, "jmp_ix", size=1, flow=InstructionFlow.INDIRECT_JUMP, unresolved=True),), (Successor(EdgeKind.INDIRECT, target_block="a"),))
        ProgramModel(ProgramSource("s"), [FunctionUnit("f", 0, (a,))], "f")

    def width_overflow():
        a = BasicBlock("a", 0x10000, (insn(0x10000, "nop"),))
        ProgramModel(ProgramSource("s", address_width_bits=16), [FunctionUnit("f", 0x10000, (a,))], "f")

    def unknown_entry():
        a = BasicBlock("a", 0, (insn(0, "nop"),))
        ProgramModel(ProgramSource("s"), [FunctionUnit("f", 0, (a,))], "ghost")

    def unsorted_instructions():
        BasicBlock("a", 4, (insn(8, "nop"), insn(4, "nop")))

    def unsupported_version():
        document = linear().to_document()
        document["program_model_version"] = "9.9.9"
        ProgramModel.from_document(document)

    for label, thunk in (
        ("duplicate-block-id", dup_block),
        ("duplicate-function-id", dup_function),
        ("dangling-successor", dangling_successor),
        ("successor-target-address-mismatch", target_address_mismatch),
        ("unknown-direct-callee", unknown_callee),
        ("function-entry-mismatch", bad_function_entry),
        ("return-block-with-successor", return_with_successor),
        ("branch-one-successor", branch_one_successor),
        ("call-without-return-edge", call_without_return_edge),
        ("indirect-jump-resolved-successor", indirect_jump_resolved),
        ("address-exceeds-declared-width", width_overflow),
        ("unknown-entry-function", unknown_entry),
        ("unsorted-instructions", unsorted_instructions),
        ("unsupported-model-version", unsupported_version),
    ):
        expect_fail(label, thunk)
        tests += 1

    expect_fail("indirect-with-direct-target", lambda: insn(0, "jmp_ix", size=1, flow=InstructionFlow.INDIRECT_JUMP, target=4))
    expect_fail("resolved-successor-without-target", lambda: Successor(EdgeKind.JUMP))
    expect_fail("unresolved-successor-with-target", lambda: Successor(EdgeKind.INDIRECT, target_block="a", resolved=False))
    expect_fail("non-serializable-metadata", lambda: insn(0, "nop", size=1, metadata={"bad": {1, 2}}))
    expect_fail("invalid-evidence", lambda: insn(0, "nop", size=1, evidence="MAYBE"))
    tests += 5

    # --- 9. adapter fail-closed -------------------------------------------------
    try:
        nes6502.decode_full(nes_code(0x8000, bytes([0x02])), 0x8000)
    except nes6502.NES6502Error:
        print("PASS reject: undocumented-opcode-fails-closed")
        tests += 1
    else:
        raise AssertionError("undocumented-opcode-fails-closed: accepted")

    print(f"OPENRECOMP_PROGRAM_MODEL_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
