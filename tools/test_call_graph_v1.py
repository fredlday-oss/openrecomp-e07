#!/usr/bin/env python3
"""Fail-closed tests for OpenRecomp deterministic call-graph recovery (P2-04).

Proves `openrecomp/call_graph.py` over the P2-03 discovered functions and P2-02
call-site evidence: node identity, internal/external/unresolved edge classes,
indirect-jump exclusion, recursion/mutual recursion, ownership validation,
evidence preservation, determinism and the required fail-closed rejections.

No guest semantics, decoding or CFG reconstruction are introduced.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from adapters import nes6502  # noqa: E402
from openrecomp.call_graph import (  # noqa: E402
    CallEdgeKind,
    CallGraph,
    CallGraphEdge,
    CallGraphError,
    CallGraphNode,
    build_call_graph,
    build_call_graph_from,
)
from openrecomp.cfg import EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.program_model import (  # noqa: E402
    BasicBlock,
    DecodedInstruction,
    EvidenceClass,
    FunctionUnit,
    InstructionFlow,
    ProgramSource,
    instruction_from_adapter,
)

PROV = EvidenceClass.PROVEN
CAND = EvidenceClass.CANDIDATE

RESULTS: list[dict[str, str]] = []


def I(address, op, size=1, flow=InstructionFlow.NORMAL, evidence=PROV, target=None, unresolved=False):
    return DecodedInstruction(
        address=address, op=op, size_bytes=size, flow=flow, direct_target=target, unresolved=unresolved, evidence=evidence
    )


def discover(insns, program_entries, *, width=None):
    cfg = build_cfg(
        insns,
        source=ProgramSource("synthetic", adapter="openrecomp.synthetic", address_width_bits=width),
        entries=[EntryPoint(address, PROV) for address in program_entries],
    )
    return discover_functions(cfg, program_entries=program_entries)


def check(label, condition):
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}")


def expect_fail(label, thunk, error_type=CallGraphError):
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


# --- fixtures --------------------------------------------------------------
def d_single():
    return discover([I(0x1000, "nop"), I(0x1001, "ret", 1, InstructionFlow.RETURN)], [0x1000])


def d_internal():
    return discover(
        [I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x8000), I(0x7003, "ret", 1, InstructionFlow.RETURN), I(0x8000, "ret", 1, InstructionFlow.RETURN)],
        [0x7000],
    )


def d_external():
    return discover(
        [I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x9000), I(0x7003, "ret", 1, InstructionFlow.RETURN)],
        [0x7000],
    )


def d_indirect():
    return discover(
        [I(0x1000, "call_ix", 2, InstructionFlow.INDIRECT_CALL, unresolved=True), I(0x1002, "ret", 1, InstructionFlow.RETURN)],
        [0x1000],
    )


def d_indirect_jump():
    return discover([I(0x2000, "jmp_ix", 2, InstructionFlow.INDIRECT_JUMP, unresolved=True)], [0x2000])


def d_recursive():
    return discover(
        [I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x7000), I(0x7003, "ret", 1, InstructionFlow.RETURN)],
        [0x7000],
    )


def d_mutual():
    return discover(
        [
            I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x8000),
            I(0x7003, "ret", 1, InstructionFlow.RETURN),
            I(0x8000, "jsr", 3, InstructionFlow.CALL, target=0x7000),
            I(0x8003, "ret", 1, InstructionFlow.RETURN),
        ],
        [0x7000],
    )


def d_multi_sites():
    return discover(
        [
            I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x8000),
            I(0x7003, "jsr", 3, InstructionFlow.CALL, target=0x8000),
            I(0x7006, "ret", 1, InstructionFlow.RETURN),
            I(0x8000, "ret", 1, InstructionFlow.RETURN),
        ],
        [0x7000],
    )


def d_candidate():
    return discover(
        [I(0x7000, "jsr", 3, InstructionFlow.CALL, evidence=CAND, target=0x8000), I(0x7003, "ret", 1, InstructionFlow.RETURN), I(0x8000, "ret", 1, InstructionFlow.RETURN, evidence=CAND)],
        [0x7000],
    )


def d_wide():
    base = 0x1_0000_0000
    return discover(
        [
            I(base, "jsr", 4, InstructionFlow.CALL, target=base + 0x10),
            I(base + 4, "ret", 4, InstructionFlow.RETURN),
            I(base + 0x10, "ret", 4, InstructionFlow.RETURN),
        ],
        [base],
        width=64,
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


def d_nes6502():
    code = bytearray(0x10000)
    code[0x8000:0x8006] = bytes([0x20, 0x00, 0x90, 0x60, 0x60, 0x00])
    code[0x9000] = 0x60
    instructions = []
    for address in (0x8000, 0x8003, 0x9000):
        decoded = nes6502.decode_full(code, address)
        instructions.append(instruction_from_adapter(decoded, flow=nes_flow(decoded), evidence=PROV))
    cfg = build_cfg(
        instructions,
        source=ProgramSource("nes6502", adapter="openrecomp.nes6502", address_width_bits=16),
        entries=[EntryPoint(0x8000, PROV)],
    )
    return discover_functions(cfg, program_entries=[0x8000])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    tests = 0

    # A. single function, no calls ---------------------------------------
    g = build_call_graph(d_single())
    check("single-node", len(g.nodes) == 1 and g.nodes[0].function_id == "fn_1000")
    check("single-no-edges", g.edges == ())
    check("single-node-evidence", g.nodes[0].evidence == PROV)
    tests += 3

    # B. internal direct call --------------------------------------------
    g = build_call_graph(d_internal())
    internal = g.internal_edges()
    check("internal-one-edge", len(internal) == 1 and internal[0].kind is CallEdgeKind.INTERNAL_DIRECT)
    check("internal-callee", internal[0].callee == "fn_8000" and internal[0].target_address is None)
    check("internal-evidence", internal[0].evidence == PROV)
    check("internal-callees-helper", g.callees("fn_7000") == ("fn_8000",))
    check("internal-edges-to", [e.caller for e in g.edges_to("fn_8000")] == ["fn_7000"])
    check("internal-no-node-for-callee-duplicate", len(g.nodes) == 2)
    tests += 6

    # C. external direct call --------------------------------------------
    g = build_call_graph(d_external())
    external = g.external_edges()
    check("external-one-edge", len(external) == 1 and external[0].kind is CallEdgeKind.EXTERNAL_DIRECT)
    check("external-target", external[0].target_address == 0x9000 and external[0].callee is None)
    check("external-no-node", {n.function_id for n in g.nodes} == {"fn_7000"})
    tests += 3

    # D. unresolved indirect call ----------------------------------------
    g = build_call_graph(d_indirect())
    unresolved = g.unresolved_edges()
    check("indirect-one-edge", len(unresolved) == 1 and unresolved[0].kind is CallEdgeKind.UNRESOLVED_INDIRECT)
    check("indirect-no-target", unresolved[0].callee is None and unresolved[0].target_address is None)
    check("indirect-no-callee-node", len(g.nodes) == 1)
    tests += 3

    # E. indirect jump excluded ------------------------------------------
    g = build_call_graph(d_indirect_jump())
    check("indirect-jump-excluded", g.edges == () and len(g.nodes) == 1)
    tests += 1

    # F. recursion --------------------------------------------------------
    g = build_call_graph(d_recursive())
    check("recursive-self-edge", g.internal_edges()[0].callee == "fn_7000")
    check("recursive-functions", g.recursive_functions() == ("fn_7000",))
    check("recursive-not-mutual", g.mutual_recursion_components() == ())
    tests += 3

    # G. mutual recursion -------------------------------------------------
    g = build_call_graph(d_mutual())
    check("mutual-two-nodes", len(g.nodes) == 2)
    check("mutual-component", g.mutual_recursion_components() == (("fn_7000", "fn_8000"),))
    check("mutual-no-self", g.recursive_functions() == ())
    tests += 3

    # H. multiple call sites ---------------------------------------------
    g = build_call_graph(d_multi_sites())
    internal = g.internal_edges()
    check("multi-site-two-edges", len(internal) == 2)
    check("multi-site-distinct-sites", sorted(e.call_site_address for e in internal) == [0x7000, 0x7003])
    check("multi-site-same-callee", {e.callee for e in internal} == {"fn_8000"})
    tests += 3

    # I. evidence preservation -------------------------------------------
    g = build_call_graph(d_candidate())
    check("candidate-internal-edge", g.internal_edges()[0].evidence == CAND)
    check("candidate-node", all(n.evidence == CAND for n in g.nodes))
    tests += 2

    # J. determinism ------------------------------------------------------
    a = build_call_graph(d_mutual())
    b = build_call_graph(d_mutual())
    check("deterministic-serialization", a.serialize() == b.serialize())
    check("deterministic-fingerprint", a.fingerprint() == b.fingerprint())
    check("deterministic-node-order", [n.function_id for n in a.nodes] == [n.function_id for n in b.nodes])
    check("deterministic-edge-order", [e.identity() for e in a.edges] == [e.identity() for e in b.edges])
    check("roundtrip-bytes", CallGraph.deserialize(a.serialize()).serialize() == a.serialize())
    check("document-derived", CallGraph.deserialize(a.serialize()).mutual_recursion_components() == (("fn_7000", "fn_8000"),))
    tests += 6

    # K. addresses above 0xFFFFFFFF --------------------------------------
    g = build_call_graph(d_wide())
    base = 0x1_0000_0000
    check("wide-node-entry", g.nodes[0].entry_address == base)
    check("wide-internal-target", g.internal_edges()[0].callee == f"fn_{base + 0x10:x}")
    tests += 2

    # L. NES6502-derived call graph --------------------------------------
    g = build_call_graph(d_nes6502())
    check("nes-two-nodes", {n.function_id for n in g.nodes} == {"fn_8000", "fn_9000"})
    check("nes-internal-edge", g.internal_edges()[0].caller == "fn_8000" and g.internal_edges()[0].callee == "fn_9000")
    tests += 2

    # S. cross-check with the P2-01 ProgramModel direct call graph -------
    d = d_internal()
    g = build_call_graph(d)
    pm_edges = {(edge["from"], edge["to"]) for edge in d.program_model.direct_call_graph()}
    cg_edges = {(edge.caller, edge.callee) for edge in g.internal_edges()}
    check("program-model-cross-check", pm_edges == cg_edges)
    tests += 1

    # M/O. ownership fail-closed -----------------------------------------
    d = d_internal()
    caller = next(f for f in d.functions if f.entry_address == 0x7000)
    callee = next(f for f in d.functions if f.entry_address == 0x8000)
    expect_fail(
        "call-site-block-unowned",
        lambda: build_call_graph_from(d.cfg, [callee], entry_function_id="fn_8000", external_direct_call_targets=d.external_direct_call_targets),
    )
    expect_fail(
        "duplicate-block-ownership",
        lambda: build_call_graph_from(d.cfg, [caller, caller], entry_function_id="fn_7000"),
    )
    tests += 2

    # P. external inventory mismatch -------------------------------------
    d = d_external()
    caller = d.functions[0]
    expect_fail(
        "external-inventory-mismatch",
        lambda: build_call_graph_from(d.cfg, [caller], entry_function_id="fn_7000", external_direct_call_targets=()),
    )
    tests += 1

    # Q. call target is a CFG block boundary but not a function entry ----
    d = d_internal()
    caller = next(f for f in d.functions if f.entry_address == 0x7000)
    detached_caller = FunctionUnit("fn_7000", 0x7000, caller.blocks, direct_callees=(), evidence=PROV)
    expect_fail(
        "call-target-not-function-entry",
        lambda: build_call_graph_from(d.cfg, [detached_caller], entry_function_id="fn_7000"),
    )
    tests += 1

    # R. unresolved call block unowned -----------------------------------
    d = d_indirect()
    callee_only = FunctionUnit("fn_1002", 0x1002, (d.functions[0].blocks[1],), evidence=PROV)
    expect_fail(
        "unresolved-call-block-unowned",
        lambda: build_call_graph_from(d.cfg, [callee_only], entry_function_id="fn_1002"),
    )
    tests += 1

    # N. structural fail-closed via direct construction ------------------
    function = FunctionUnit("fn_a", 0, (BasicBlock("blk_a", 0, (I(0, "nop"),)),), evidence=PROV)
    units = {"fn_a": function}
    node_a = CallGraphNode("fn_a", 0, PROV)
    node_b = CallGraphNode("fn_b", 8, PROV)
    function_b = FunctionUnit("fn_b", 8, (BasicBlock("blk_b", 8, (I(8, "nop"),)),), evidence=PROV)
    internal_ab = CallGraphEdge(CallEdgeKind.INTERNAL_DIRECT, "fn_a", "blk_a", 0, "jsr", PROV, callee="fn_b")
    external_a = CallGraphEdge(CallEdgeKind.EXTERNAL_DIRECT, "fn_a", "blk_a", 0, "jsr", PROV, target_address=0x9999)

    expect_fail("duplicate-node-id", lambda: CallGraph([node_a, CallGraphNode("fn_a", 0x20, PROV)], []))
    expect_fail("duplicate-node-entry", lambda: CallGraph([node_a, CallGraphNode("fn_c", 0, PROV)], []))
    expect_fail("empty-nodes", lambda: CallGraph([], []))
    expect_fail("edge-caller-not-node", lambda: CallGraph([node_a], [internal_ab]))
    expect_fail("internal-callee-not-node", lambda: CallGraph([node_a, node_b], [CallGraphEdge(CallEdgeKind.INTERNAL_DIRECT, "fn_a", "blk_a", 0, "jsr", PROV, callee="ghost")]))
    expect_fail("external-target-matches-node", lambda: CallGraph([node_a, node_b], [CallGraphEdge(CallEdgeKind.EXTERNAL_DIRECT, "fn_a", "blk_a", 0, "jsr", PROV, target_address=8)]))
    expect_fail("unresolved-with-callee", lambda: CallGraphEdge(CallEdgeKind.UNRESOLVED_INDIRECT, "fn_a", "blk_a", 0, "call_ix", PROV, callee="fn_b"))
    expect_fail("internal-without-callee", lambda: CallGraphEdge(CallEdgeKind.INTERNAL_DIRECT, "fn_a", "blk_a", 0, "jsr", PROV))
    expect_fail("duplicate-edge", lambda: CallGraph([node_a, node_b], [internal_ab, internal_ab]))
    expect_fail("entry-function-not-node", lambda: CallGraph([node_a], [], entry_function="ghost"))
    expect_fail("function-units-key-mismatch", lambda: CallGraph([node_a], [], function_units={"fn_b": function_b}))
    expect_fail("function-units-evidence-mismatch", lambda: CallGraph([CallGraphNode("fn_a", 0, CAND)], [], function_units=units))
    expect_fail(
        "function-units-callee-mismatch",
        lambda: CallGraph([node_a, node_b], [internal_ab], function_units=units),
    )
    expect_fail(
        "evidence-mismatch-candidate-node",
        lambda: CallGraph([CallGraphNode("fn_a", 0, CAND), node_b], [internal_ab], function_units={**units, "fn_b": function_b}),
    )
    expect_fail("unknown-edges-from", lambda: CallGraph([node_a], []).edges_from("ghost"))
    expect_fail("unknown-edges-to", lambda: CallGraph([node_a], []).edges_to("ghost"))
    tests += 16

    # Valid construction with matching units -----------------------------
    valid = CallGraph(
        [node_a, node_b],
        [internal_ab],
        entry_function="fn_a",
        function_units={"fn_a": FunctionUnit("fn_a", 0, function.blocks, direct_callees=("fn_b",), evidence=PROV), "fn_b": function_b},
    )
    check("valid-direct-construction", valid.internal_edges()[0].callee == "fn_b")
    tests += 1

    # external-only construction still validates -------------------------
    valid_external = CallGraph([node_a], [external_a], entry_function="fn_a")
    check("valid-external-construction", valid_external.external_edges()[0].target_address == 0x9999)
    tests += 1

    if args.json:
        record = {
            "stage": "P2-04",
            "marker": f"OPENRECOMP_CALL_GRAPH_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "results": sorted(RESULTS, key=lambda item: item["check"]),
            "sample_fingerprints": {
                "internal": build_call_graph(d_internal()).fingerprint(),
                "mixed": build_call_graph(discover(
                    [
                        I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x8000),
                        I(0x7003, "jsr", 3, InstructionFlow.CALL, target=0x9000),
                        I(0x7006, "call_ix", 2, InstructionFlow.INDIRECT_CALL, unresolved=True),
                        I(0x7008, "ret", 1, InstructionFlow.RETURN),
                        I(0x8000, "ret", 1, InstructionFlow.RETURN),
                    ],
                    [0x7000],
                )).fingerprint(),
                "mutual": build_call_graph(d_mutual()).fingerprint(),
                "nes6502": build_call_graph(d_nes6502()).fingerprint(),
            },
        }
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_CALL_GRAPH_V1_JSON={out.name}")

    print(f"OPENRECOMP_CALL_GRAPH_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
