#!/usr/bin/env python3
"""Fail-closed tests for OpenRecomp deterministic CFG construction (P2-02).

Proves `openrecomp/cfg.py` over the P2-01 shared model with architecture-neutral,
deterministic coverage: block boundaries, every required edge kind, closed/open
policy, evidence propagation, arbitrary-width addresses, real NES 6502
variable-width decoding, and the required fail-closed rejections.

No guest semantics are introduced; frozen IR V1 is untouched.
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
from openrecomp.cfg import (  # noqa: E402
    CFGError,
    CFGMode,
    CallSite,
    ControlFlowGraph,
    EntryPoint,
    build_cfg,
    combine_evidence,
)
from openrecomp.program_model import (  # noqa: E402
    BasicBlock,
    DecodedInstruction,
    EdgeKind,
    EvidenceClass,
    InstructionFlow,
    ProgramSource,
    Successor,
    instruction_from_adapter,
)
from validate_program_model_v1 import load_and_validate  # noqa: E402

SCHEMA = json.loads((ROOT / "schema" / "openrecomp-program-v1.schema.json").read_text(encoding="utf-8"))
PROV = EvidenceClass.PROVEN
CAND = EvidenceClass.CANDIDATE


def I(address, op, size=1, flow=InstructionFlow.NORMAL, evidence=PROV, target=None, unresolved=False):
    return DecodedInstruction(
        address=address,
        op=op,
        size_bytes=size,
        flow=flow,
        direct_target=target,
        unresolved=unresolved,
        evidence=evidence,
    )


def build(insns, entries, *, mode=CFGMode.CLOSED, width=None, boundaries=(), presorted=False):
    source = ProgramSource("synthetic", adapter="openrecomp.synthetic", address_width_bits=width)
    return build_cfg(insns, source=source, entries=entries, mode=mode, region_boundaries=boundaries, presorted=presorted)


RESULTS: list[dict[str, str]] = []


def check(label, condition):
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}")


def expect_fail(label, thunk, error_type=CFGError):
    try:
        thunk()
    except error_type:
        RESULTS.append({"check": f"reject:{label}", "status": "PASS"})
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        RESULTS.append({"check": f"reject:{label}", "status": "FAIL"})
        raise AssertionError(f"{label}: raised {type(exc).__name__} instead of {error_type.__name__}: {exc}") from exc
    RESULTS.append({"check": f"reject:{label}", "status": "FAIL"})
    raise AssertionError(f"{label}: accepted")


# --- scenarios ------------------------------------------------------------
def g_linear():
    return build([I(0x1000, "mov", 2), I(0x1002, "add", 2), I(0x1004, "ret", 1, InstructionFlow.RETURN)], [EntryPoint(0x1000, PROV)])


def g_forward_branch():
    return build(
        [
            I(0x2000, "cmp", 2),
            I(0x2002, "beq", 2, InstructionFlow.BRANCH, target=0x2008),
            I(0x2004, "nop", 2),
            I(0x2006, "ret", 1, InstructionFlow.RETURN),
            I(0x2008, "ret", 1, InstructionFlow.RETURN),
        ],
        [EntryPoint(0x2000, PROV)],
    )


def g_backward_branch():
    return build(
        [I(0x3000, "add", 2), I(0x3002, "bne", 2, InstructionFlow.BRANCH, target=0x3000), I(0x3004, "ret", 1, InstructionFlow.RETURN)],
        [EntryPoint(0x3000, PROV)],
    )


def g_forward_jump():
    return build(
        [
            I(0x4000, "jmp", 2, InstructionFlow.JUMP, target=0x4006),
            I(0x4002, "nop", 2),
            I(0x4004, "nop", 2),
            I(0x4006, "ret", 1, InstructionFlow.RETURN),
        ],
        [EntryPoint(0x4000, PROV)],
    )


def g_backward_jump():
    return build(
        [I(0x5000, "nop", 2), I(0x5002, "jmp", 2, InstructionFlow.JUMP, target=0x5000), I(0x5004, "ret", 1, InstructionFlow.RETURN)],
        [EntryPoint(0x5000, PROV)],
    )


def g_return():
    return build([I(0x6000, "ret", 1, InstructionFlow.RETURN)], [EntryPoint(0x6000, PROV)])


def g_call_external():
    return build([I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x8000), I(0x7003, "ret", 1, InstructionFlow.RETURN)], [EntryPoint(0x7000, PROV)])


def g_call_local():
    ins = [
        I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x8000),
        I(0x7003, "ret", 1, InstructionFlow.RETURN),
        I(0x8000, "ret", 1, InstructionFlow.RETURN),
    ]
    return build(ins, [EntryPoint(0x7000, PROV), EntryPoint(0x8000, PROV)])


def g_indirect_call():
    return build(
        [I(0x9000, "call_ix", 2, InstructionFlow.INDIRECT_CALL, unresolved=True), I(0x9002, "ret", 1, InstructionFlow.RETURN)],
        [EntryPoint(0x9000, PROV)],
    )


def g_indirect_jump():
    return build([I(0xA000, "jmp_ix", 2, InstructionFlow.INDIRECT_JUMP, unresolved=True)], [EntryPoint(0xA000, PROV)])


def g_trap():
    return build([I(0xB000, "trap", 1, InstructionFlow.TRAP)], [EntryPoint(0xB000, PROV)])


def g_multi_targets():
    return build(
        [
            I(0xC000, "beq", 2, InstructionFlow.BRANCH, target=0xC00A),
            I(0xC002, "bne", 2, InstructionFlow.BRANCH, target=0xC010),
            I(0xC004, "ret", 1, InstructionFlow.RETURN),
            I(0xC005, "ret", 1, InstructionFlow.RETURN),
            I(0xC00A, "ret", 1, InstructionFlow.RETURN),
            I(0xC010, "ret", 1, InstructionFlow.RETURN),
        ],
        [EntryPoint(0xC000, PROV)],
    )


def g_variable_width():
    return build(
        [
            I(0x100, "a", 1),
            I(0x101, "b", 2),
            I(0x103, "c", 4),
            I(0x107, "d", 1),
            I(0x108, "e", 2, InstructionFlow.BRANCH, target=0x100),
            I(0x10A, "f", 3),
            I(0x10D, "ret", 1, InstructionFlow.RETURN),
        ],
        [EntryPoint(0x100, PROV)],
    )


def g_wide():
    base = 0x1_0000_0000
    return build(
        [
            I(base, "mov", 4),
            I(base + 4, "beq", 4, InstructionFlow.BRANCH, target=base + 0xC),
            I(base + 8, "ret", 4, InstructionFlow.RETURN),
            I(base + 0xC, "ret", 4, InstructionFlow.RETURN),
        ],
        [EntryPoint(base, PROV)],
    )


def nes_flow(decoded):
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


def g_nes6502():
    code = bytearray(0x10000)
    code[0x8000:0x8007] = bytes([0xA9, 0x05, 0xF0, 0x02, 0xEA, 0x60, 0x60])
    instructions = []
    for address in (0x8000, 0x8002, 0x8004, 0x8005, 0x8006):
        decoded = nes6502.decode_full(code, address)
        instructions.append(instruction_from_adapter(decoded, flow=nes_flow(decoded), evidence=PROV))
    return build_cfg(instructions, source=ProgramSource("nes6502", adapter="openrecomp.nes6502", address_width_bits=16), entries=[EntryPoint(0x8000, PROV)])


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    tests = 0

    # 1. straight-line -> one block --------------------------------------
    g = g_linear()
    blocks = g.ordered_blocks()
    check("linear-one-block", len(blocks) == 1 and blocks[0].id == "blk_1000")
    check("linear-instruction-membership", [i.address for i in blocks[0].instructions] == [0x1000, 0x1002, 0x1004])
    check("linear-terminal-no-successor", blocks[0].successors == ())
    tests += 3

    # 2/3. forward conditional branch -> target + fallthrough ------------
    g = g_forward_branch()
    branch = g.block("blk_2000")
    kinds = {s.kind: s for s in branch.successors}
    check("branch-two-successors", len(branch.successors) == 2)
    check("branch-taken-target", kinds[EdgeKind.BRANCH_TAKEN].target_address == 0x2008 and kinds[EdgeKind.BRANCH_TAKEN].target_block == "blk_2008")
    check("branch-fallthrough", kinds[EdgeKind.BRANCH_NOT_TAKEN].target_address == 0x2004 and kinds[EdgeKind.BRANCH_NOT_TAKEN].target_block == "blk_2004")
    check("branch-block-count", len(g.ordered_blocks()) == 3)
    check("branch-predecessors", {p["from"] for p in g.predecessors()["blk_2008"]} == {"blk_2000"})
    tests += 5

    # 4. backward conditional branch / loop ------------------------------
    g = g_backward_branch()
    loop = g.block("blk_3000")
    taken = [s for s in loop.successors if s.kind == EdgeKind.BRANCH_TAKEN][0]
    check("loop-back-edge", taken.target_block == "blk_3000" and taken.resolved)
    check("loop-self-predecessor", any(p["from"] == "blk_3000" for p in g.predecessors()["blk_3000"]))
    tests += 2

    # 5. forward unconditional jump --------------------------------------
    g = g_forward_jump()
    jump = g.block("blk_4000")
    check("forward-jump-only-edge", len(jump.successors) == 1 and jump.successors[0].kind == EdgeKind.JUMP)
    check("forward-jump-target", jump.successors[0].target_block == "blk_4006" and jump.successors[0].target_address == 0x4006)
    tests += 2

    # 6. backward unconditional jump -------------------------------------
    g = g_backward_jump()
    jump = g.block("blk_5000")
    check("backward-jump-self", jump.successors[0].target_block == "blk_5000")
    tests += 1

    # 7. return terminator ------------------------------------------------
    g = g_return()
    check("return-no-successor", g.block("blk_6000").successors == ())
    tests += 1

    # 8/9. direct call with continuation, callee kept separate -----------
    g = g_call_external()
    caller = g.block("blk_7000")
    check("call-continuation", len(caller.successors) == 1 and caller.successors[0].kind == EdgeKind.CALL_RETURN and caller.successors[0].target_block == "blk_7003")
    check("call-site-recorded", [(s.block_id, s.address, s.op, s.target_address) for s in g.direct_call_sites] == [("blk_7000", 0x7000, "jsr", 0x8000)])
    check("call-callee-not-absorbed", "blk_8000" not in {b.id for b in g.blocks})

    g = g_call_local()
    check("call-local-callee-block", "blk_8000" in {b.id for b in g.blocks})
    check("call-local-no-edge-to-callee", g.predecessors()["blk_8000"] == ())
    check("call-local-site-preserved", g.direct_call_sites[0].target_address == 0x8000)
    tests += 6

    # 10. unresolved indirect call ---------------------------------------
    g = g_indirect_call()
    block = g.block("blk_9000")
    check("indirect-call-continuation", len(block.successors) == 1 and block.successors[0].kind == EdgeKind.CALL_RETURN)
    check("indirect-call-site", [(s.block_id, s.address, s.op) for s in g.unresolved_call_sites] == [("blk_9000", 0x9000, "call_ix")])
    check("indirect-call-no-direct-site", g.direct_call_sites == ())
    tests += 3

    # 11. unresolved indirect jump ---------------------------------------
    g = g_indirect_jump()
    block = g.block("blk_a000")
    check("indirect-jump-one-unsolved", len(block.successors) == 1 and not block.successors[0].resolved and block.successors[0].kind == EdgeKind.INDIRECT)
    check("indirect-jump-site", [(s.block_id, s.address, s.op) for s in g.unresolved_jump_sites] == [("blk_a000", 0xA000, "jmp_ix")])
    tests += 2

    # 12. terminal / stop -------------------------------------------------
    check("trap-no-successor", g_trap().block("blk_b000").successors == ())
    tests += 1

    # 13. multiple branch targets ----------------------------------------
    g = g_multi_targets()
    taken_targets = {
        s.target_address
        for block in g.blocks
        for s in block.successors
        if s.kind == EdgeKind.BRANCH_TAKEN and s.resolved
    }
    check("multi-target-taken", taken_targets == {0xC00A, 0xC010})
    check("multi-target-block-count", len(g.ordered_blocks()) == 6)
    tests += 2

    # 14/15. multiple entries and disconnected regions -------------------
    g = build(
        [I(0x100, "nop", 1), I(0x101, "ret", 1, InstructionFlow.RETURN), I(0x200, "nop", 1), I(0x201, "ret", 1, InstructionFlow.RETURN)],
        [EntryPoint(0x100, PROV), EntryPoint(0x200, PROV)],
    )
    check("multiple-entries", [e.address for e in g.ordered_entries()] == [0x100, 0x200])
    check("multiple-entry-blocks", {b.id for b in g.blocks} == {"blk_100", "blk_200"})
    g = build([I(0x100, "nop", 1), I(0x101, "ret", 1, InstructionFlow.RETURN), I(0x200, "nop", 1), I(0x201, "ret", 1, InstructionFlow.RETURN)], [EntryPoint(0x100, PROV)])
    check("disconnected-region-block", "blk_200" in {b.id for b in g.blocks})
    tests += 3

    # 16. variable-width sequence ----------------------------------------
    g = g_variable_width()
    check("variable-width-block-count", len(g.ordered_blocks()) == 2)
    loop_block = g.block("blk_100")
    check("variable-width-back-edge", any(s.target_block == "blk_100" for s in loop_block.successors))
    check("variable-width-fallthrough-address", [i.address for i in g.block("blk_10a").instructions] == [0x10A, 0x10D])
    tests += 3

    # 17. real NES6502 variable-width decode -----------------------------
    g = g_nes6502()
    check("nes-block-count", len(g.ordered_blocks()) == 3)
    branch = g.block("blk_8000")
    check("nes-branch-taken", any(s.kind == EdgeKind.BRANCH_TAKEN and s.target_address == 0x8006 for s in branch.successors))
    check("nes-branch-fallthrough", any(s.kind == EdgeKind.BRANCH_NOT_TAKEN and s.target_address == 0x8004 for s in branch.successors))
    check("nes-variable-sizes", [i.size_bytes for i in branch.instructions] == [2, 2])
    check("nes-evidence-preserved", branch.evidence == PROV)
    tests += 5

    # 18. address > 0xFFFFFFFF -------------------------------------------
    g = g_wide()
    base = 0x1_0000_0000
    check("wide-entry-preserved", g.ordered_blocks()[0].entry_address == base)
    wide_branch = g.block(f"blk_{base:x}")
    check("wide-target-preserved", any(s.target_address == base + 0xC for s in wide_branch.successors))
    tests += 2

    # 19/20/21. determinism, ordering, serialization ---------------------
    a = g_multi_targets()
    shuffled = list(reversed(list(a.instructions)))
    b = build(shuffled, [EntryPoint(0xC000, PROV)])
    check("deterministic-serialization", a.serialize() == b.serialize())
    check("deterministic-fingerprint", a.fingerprint() == b.fingerprint())
    check("deterministic-block-order", [blk.id for blk in a.ordered_blocks()] == [blk.id for blk in b.ordered_blocks()])
    check("deterministic-edge-order", [tuple(s.kind.value for s in blk.successors) for blk in a.ordered_blocks()] == [tuple(s.kind.value for s in blk.successors) for blk in b.ordered_blocks()])
    check("roundtrip-bytes", ControlFlowGraph.deserialize(a.serialize()).serialize() == a.serialize())
    tests += 5

    # 22/23. evidence preservation ---------------------------------------
    g = g_forward_branch()
    check("proven-block", g.block("blk_2000").evidence == PROV)
    check("proven-edge", all(s.evidence == PROV for s in g.block("blk_2000").successors))
    g = build(
        [
            I(0x2000, "cmp", 2, evidence=CAND),
            I(0x2002, "beq", 2, InstructionFlow.BRANCH, evidence=CAND, target=0x2008),
            I(0x2004, "nop", 2, evidence=PROV),
            I(0x2006, "ret", 1, InstructionFlow.RETURN, evidence=PROV),
            I(0x2008, "ret", 1, InstructionFlow.RETURN, evidence=PROV),
        ],
        [EntryPoint(0x2000, PROV)],
    )
    check("candidate-block-not-promoted", g.block("blk_2000").evidence == CAND)
    check("candidate-edge-not-promoted", all(s.evidence == CAND for s in g.block("blk_2000").successors))
    check("combine-evidence-never-promotes", combine_evidence(PROV, CAND) == CAND and combine_evidence(PROV, PROV) == PROV)
    tests += 5

    # open vs closed policy ----------------------------------------------
    external = [I(0x100, "beq", 2, InstructionFlow.BRANCH, target=0x5000), I(0x102, "ret", 1, InstructionFlow.RETURN)]
    expect_fail("closed-missing-direct-target", lambda: build(external, [EntryPoint(0x100, PROV)], mode=CFGMode.CLOSED))
    g = build(external, [EntryPoint(0x100, PROV)], mode=CFGMode.OPEN)
    taken = [s for s in g.block("blk_100").successors if s.kind == EdgeKind.BRANCH_TAKEN][0]
    check("open-external-edge", (not taken.resolved) and taken.target_address == 0x5000 and taken.detail is not None)
    check("open-cfg-wrap-valid", g.to_program_model().function(f"region_100").entry_address == 0x100)
    external_fallthrough = [I(0x200, "beq", 2, InstructionFlow.BRANCH, target=0x200)]
    g = build(external_fallthrough, [EntryPoint(0x200, PROV)], mode=CFGMode.OPEN)
    not_taken = [s for s in g.block("blk_200").successors if s.kind == EdgeKind.BRANCH_NOT_TAKEN][0]
    check("open-external-fallthrough", (not not_taken.resolved) and not_taken.target_address == 0x202)
    tests += 5

    # region boundaries ---------------------------------------------------
    g = build([I(0x1000, "nop", 1), I(0x1001, "nop", 1), I(0x1002, "ret", 1, InstructionFlow.RETURN)], [EntryPoint(0x1000, PROV)], boundaries=[0x1001])
    check("region-boundary-splits", {b.id for b in g.blocks} == {"blk_1000", "blk_1001"})
    tests += 1

    # 24-29, 32. builder fail-closed rejections --------------------------
    expect_fail("duplicate-instruction", lambda: build([I(0x1000, "nop"), I(0x1000, "nop")], [EntryPoint(0x1000, PROV)]))
    expect_fail("overlapping-extent", lambda: build([I(0x1000, "nop", 4), I(0x1002, "nop", 1)], [EntryPoint(0x1000, PROV)]))
    expect_fail(
        "direct-target-interior",
        lambda: build(
            [I(0x1000, "mov", 2), I(0x1002, "beq", 2, InstructionFlow.BRANCH, target=0x1001), I(0x1004, "ret", 1, InstructionFlow.RETURN)],
            [EntryPoint(0x1000, PROV)],
        ),
    )
    expect_fail(
        "fallthrough-interior",
        lambda: build([I(0x1000, "beq", 2, InstructionFlow.BRANCH, target=0x1010), I(0x1001, "mov", 2)], [EntryPoint(0x1000, PROV)]),
    )
    expect_fail("missing-closed-target", lambda: build([I(0x100, "beq", 2, InstructionFlow.BRANCH, target=0x9999), I(0x102, "ret", 1, InstructionFlow.RETURN)], [EntryPoint(0x100, PROV)]))
    expect_fail("malformed-entry", lambda: build([I(0x100, "nop"), I(0x101, "ret", 1, InstructionFlow.RETURN)], [EntryPoint(0x9999, PROV)]))
    expect_fail(
        "entry-interior",
        lambda: build([I(0x100, "mov", 2), I(0x102, "ret", 1, InstructionFlow.RETURN)], [EntryPoint(0x101, PROV)]),
    )
    expect_fail("presorted-inconsistent", lambda: build([I(0x100, "nop"), I(0x101, "nop")][::-1], [EntryPoint(0x100, PROV)], presorted=True))
    expect_fail("ambiguous-normal-unresolved", lambda: build([I(0x100, "nop", 1, InstructionFlow.NORMAL, unresolved=True)], [EntryPoint(0x100, PROV)]))
    expect_fail("return-with-target", lambda: build([I(0x100, "ret", 1, InstructionFlow.RETURN, target=0x200)], [EntryPoint(0x100, PROV)]))
    expect_fail("impossible-fallthrough-call", lambda: build([I(0x100, "jsr", None, InstructionFlow.CALL, target=0x200)], [EntryPoint(0x100, PROV)]))
    expect_fail("malformed-boundary", lambda: build([I(0x100, "nop")], [EntryPoint(0x100, PROV)], boundaries=[0x999]))
    tests += 12

    # 30/31. hand-constructed CFG graph-consistency rejections -----------
    src = ProgramSource("synthetic")
    ghost_edge = Successor(EdgeKind.JUMP, target_block="ghost")
    bad_block = BasicBlock("blk_bad", 0x10, (I(0x10, "jmp", 1, InstructionFlow.JUMP, target=0x20),), (ghost_edge,))
    expect_fail(
        "edge-to-nonexistent-block",
        lambda: ControlFlowGraph(src, CFGMode.CLOSED, [EntryPoint(0, PROV)], [bad_block.instructions[0]], [bad_block]),
    )
    mid_flow = BasicBlock("blk_flow", 0, (I(0, "jmp", 1, InstructionFlow.JUMP, target=1), I(1, "ret", 1, InstructionFlow.RETURN)))
    expect_fail(
        "instruction-after-terminal",
        lambda: ControlFlowGraph(src, CFGMode.CLOSED, [EntryPoint(0, PROV)], list(mid_flow.instructions), [mid_flow]),
    )
    dup_id_a = BasicBlock("blk_dup", 0, (I(0, "nop", 1),))
    dup_id_b = BasicBlock("blk_dup", 8, (I(8, "nop", 1),))
    expect_fail(
        "duplicate-block-identity",
        lambda: ControlFlowGraph(src, CFGMode.CLOSED, [EntryPoint(0, PROV)], [I(0, "nop", 1), I(8, "nop", 1)], [dup_id_a, dup_id_b]),
    )
    overlap_a = BasicBlock("blk_o1", 0, (I(0, "nop", 1),))
    overlap_b = BasicBlock("blk_o2", 0, (I(0, "other", 1),))
    expect_fail(
        "overlapping-block-entry",
        lambda: ControlFlowGraph(src, CFGMode.CLOSED, [EntryPoint(0, PROV)], [I(0, "nop", 1)], [overlap_a, overlap_b]),
    )
    shared_a = BasicBlock("blk_s1", 0, (I(0, "nop", 1), I(4, "nop", 1)))
    shared_b = BasicBlock("blk_s2", 4, (I(4, "nop", 1), I(8, "nop", 1)))
    expect_fail(
        "instruction-in-two-blocks",
        lambda: ControlFlowGraph(src, CFGMode.CLOSED, [EntryPoint(0, PROV)], [I(0, "nop", 1), I(4, "nop", 1), I(8, "nop", 1)], [shared_a, shared_b]),
    )
    unassigned = BasicBlock("blk_u", 0, (I(0, "nop", 1),))
    expect_fail(
        "instruction-unassigned",
        lambda: ControlFlowGraph(src, CFGMode.CLOSED, [EntryPoint(0, PROV)], [I(0, "nop", 1), I(8, "nop", 1)], [unassigned]),
    )
    tests += 6

    # schema + CLI validation of the CFG's ProgramModel view -------------
    for label, graph in (("forward-branch", g_forward_branch()), ("open-external", build(external, [EntryPoint(0x100, PROV)], mode=CFGMode.OPEN)), ("nes6502", g_nes6502()), ("wide", g_wide())):
        jsonschema.validate(graph.to_program_model().to_document(), SCHEMA)
        print(f"PASS schema: {label}")
        tests += 1
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cfg.program.json"
        path.write_bytes(g_nes6502().to_program_model().serialize())
        check("cfg-program-valid", load_and_validate(path) is not None)
        tests += 1

    # CFG document round-trip preserves evidence and unresolved sites ----
    g = g_indirect_call()
    restored = ControlFlowGraph.deserialize(g.serialize())
    check("cfg-roundtrip-fingerprint", restored.fingerprint() == g.fingerprint())
    check("cfg-roundtrip-unresolved", [(s.block_id, s.address, s.op) for s in restored.unresolved_call_sites] == [("blk_9000", 0x9000, "call_ix")])
    tests += 2

    if args.json:
        record = {
            "stage": "P2-02",
            "marker": f"OPENRECOMP_CFG_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "results": sorted(RESULTS, key=lambda item: item["check"]),
            "sample_fingerprints": {
                "forward_branch": g_forward_branch().fingerprint(),
                "nes6502": g_nes6502().fingerprint(),
                "wide": g_wide().fingerprint(),
                "open_external": build(external, [EntryPoint(0x100, PROV)], mode=CFGMode.OPEN).fingerprint(),
            },
        }
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_CFG_V1_JSON={out.name}")

    print(f"OPENRECOMP_CFG_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
