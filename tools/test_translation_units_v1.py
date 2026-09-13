#!/usr/bin/env python3
"""Fail-closed tests for OpenRecomp deterministic translation units (P2-05).

Proves `openrecomp/translation_units.py` over the P2-03 discovered functions,
the P2-02 CFG structure and the P2-04 call graph: one-to-one mapping, canonical
block order, verbatim instruction/CFG preservation, resolved and unresolved call
evidence, provenance, arbitrary-width addresses, deterministic serialization,
byte-identical repeated construction, fail-closed rejection and the absence of
any IR lowering.

No guest semantics, decoding, CFG reconstruction or lowering are introduced.
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
import openrecomp.translation_units as translation_units  # noqa: E402
from openrecomp.call_graph import (  # noqa: E402
    CallEdgeKind,
    CallGraphEdge,
    build_call_graph,
)
from openrecomp.cfg import EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import (  # noqa: E402
    ExternalDirectCallTarget,
    FunctionEntry,
    FunctionEntrySource,
    SharedBlock,
    SuppressedEntry,
    discover_functions,
)
from openrecomp.program_model import (  # noqa: E402
    BasicBlock,
    DecodedInstruction,
    EvidenceClass,
    InstructionFlow,
    ProgramSource,
    UnresolvedSite,
    instruction_from_adapter,
)
from openrecomp.translation_units import (  # noqa: E402
    TranslationUnit,
    TranslationUnitError,
    TranslationUnitSet,
    build_translation_units,
    build_translation_units_from,
)

PROV = EvidenceClass.PROVEN
CAND = EvidenceClass.CANDIDATE

RESULTS: list[dict[str, str]] = []


def I(address, op, size=1, flow=InstructionFlow.NORMAL, evidence=PROV, target=None, unresolved=False):
    return DecodedInstruction(
        address=address, op=op, size_bytes=size, flow=flow, direct_target=target, unresolved=unresolved, evidence=evidence
    )


def check(label, condition):
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}")


def expect_fail(label, thunk, error_type=TranslationUnitError):
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


def synthetic_source(width=None):
    return ProgramSource("synthetic", adapter="openrecomp.synthetic", address_width_bits=width)


def discover(insns, program_entries, *, width=None):
    cfg = build_cfg(
        insns,
        source=synthetic_source(width),
        entries=[EntryPoint(address, PROV) for address in program_entries],
    )
    return discover_functions(cfg, program_entries=program_entries)


def discover_candidate(insns, entry):
    cfg = build_cfg(insns, source=synthetic_source(), entries=[EntryPoint(entry, CAND)])
    return discover_functions(
        cfg,
        function_entries=[FunctionEntry(entry, FunctionEntrySource.EXPLICIT_CANDIDATE, CAND)],
    )


# --- fixtures --------------------------------------------------------------
def d_single():
    return discover([I(0x1000, "nop"), I(0x1001, "ret", 1, InstructionFlow.RETURN)], [0x1000])


def d_calls():
    return discover(
        [
            I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x8000),
            I(0x7003, "jsr", 3, InstructionFlow.CALL, target=0x9000),
            I(0x7006, "call_ix", 2, InstructionFlow.INDIRECT_CALL, unresolved=True),
            I(0x7008, "ret", 1, InstructionFlow.RETURN),
            I(0x8000, "ret", 1, InstructionFlow.RETURN),
        ],
        [0x7000],
    )


def d_indirect_jump():
    return discover([I(0x2000, "jmp_ix", 2, InstructionFlow.INDIRECT_JUMP, unresolved=True)], [0x2000])


def d_unowned():
    return discover(
        [
            I(0x1000, "ret", 1, InstructionFlow.RETURN),
            I(0x5000, "jmp_ix", 2, InstructionFlow.INDIRECT_JUMP, unresolved=True),
        ],
        [0x1000],
    )


def d_shared():
    return discover(
        [
            I(0x1000, "jmp", 1, InstructionFlow.JUMP, target=0x3000),
            I(0x2000, "jmp", 1, InstructionFlow.JUMP, target=0x3000),
            I(0x3000, "ret", 1, InstructionFlow.RETURN),
        ],
        [0x1000, 0x2000],
    )


def d_candidate():
    return discover_candidate(
        [I(0x1000, "nop", 1, InstructionFlow.NORMAL, CAND), I(0x1001, "ret", 1, InstructionFlow.RETURN, CAND)],
        0x1000,
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


def d_very_wide():
    base = 0x1_0000_0000_0000_0000
    return discover(
        [I(base, "nop", 1), I(base + 1, "ret", 1, InstructionFlow.RETURN)],
        [base],
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

    # A. one-to-one FunctionUnit -> TranslationUnit mapping -----------------
    d = d_calls()
    s = build_translation_units(d)
    check("one-unit-per-function", len(s.units) == len(d.functions) == 2)
    check("unit-function-ids", set(s.function_ids()) == {function.id for function in d.functions})
    check(
        "unit-one-to-one",
        all(s.unit_for(function.id).function_id == function.id for function in d.functions),
    )
    check("unit-ids-stable", {unit.unit_id for unit in s.units} == {"tu_fn_7000", "tu_fn_8000"})
    check("unit-lookup-by-id", s.unit_by_id("tu_fn_7000") is s.unit_for("fn_7000"))

    # B. deterministic construction / stable ordering -----------------------
    check("stable-order", [unit.entry_address for unit in s.units] == [0x7000, 0x8000])
    reversed_set = TranslationUnitSet(
        s.source,
        list(reversed(s.units)),
        entry_unit=s.entry_unit,
        shared_blocks=s.shared_blocks,
        suppressed_entries=s.suppressed_entries,
        unowned_blocks=s.unowned_blocks,
        external_direct_call_targets=s.external_direct_call_targets,
        unowned_control_flow=s.unowned_control_flow,
    )
    check("stable-order-input-independent", reversed_set.serialize() == s.serialize())
    check("deterministic-construction", build_translation_units(d_calls()).serialize() == s.serialize())

    # C. preservation of instructions ---------------------------------------
    for function in d.functions:
        unit = s.unit_for(function.id)
        function_instructions = tuple(
            instruction for block in function.blocks for instruction in block.instructions
        )
        check(f"instructions-preserved:{function.id}", unit.instructions() == function_instructions)
        check(
            f"instruction-objects-preserved:{function.id}",
            all(isinstance(instruction, DecodedInstruction) for instruction in unit.instructions()),
        )
    caller_unit = s.unit_for("fn_7000")
    caller_function = next(function for function in d.functions if function.id == "fn_7000")
    check("instruction-ops-unlowered", [i.op for i in caller_unit.instructions()] == ["jsr", "jsr", "call_ix", "ret"])

    # D. preservation of CFG / block membership -----------------------------
    for function in d.functions:
        unit = s.unit_for(function.id)
        check(f"block-membership:{function.id}", [block.id for block in unit.blocks] == [block.id for block in function.blocks])
        check(
            f"block-addresses:{function.id}",
            [block.entry_address for block in unit.blocks] == [block.entry_address for block in function.blocks],
        )
        check(
            f"block-successors:{function.id}",
            [block.successors for block in unit.blocks] == [block.successors for block in function.blocks],
        )
    check("canonical-block-order", caller_unit.blocks[0].entry_address == caller_unit.entry_address)

    # E. preservation of resolved direct calls ------------------------------
    caller_edges = caller_unit.call_edges
    internal = [edge for edge in caller_edges if edge.kind is CallEdgeKind.INTERNAL_DIRECT]
    check("resolved-call-one", len(internal) == 1 and internal[0].callee == "fn_8000")
    check("resolved-call-site", internal[0].call_site_address == 0x7000 and internal[0].call_site_op == "jsr")
    check("resolved-callees", caller_unit.direct_callees == ("fn_8000",))
    check(
        "resolved-matches-call-graph",
        internal[0].identity() == build_call_graph(d).edges_from("fn_7000")[0].identity(),
    )
    check("callee-unit-single-block", s.unit_for("fn_8000").entry_address == 0x8000)

    # F. preservation of unresolved / indirect evidence ---------------------
    unresolved = [edge for edge in caller_edges if edge.kind is CallEdgeKind.UNRESOLVED_INDIRECT]
    check("unresolved-edge-preserved", len(unresolved) == 1)
    check("unresolved-no-invented-target", unresolved[0].callee is None and unresolved[0].target_address is None)
    check("unresolved-site-preserved", len(caller_unit.unresolved_call_sites) == 1)
    check(
        "unresolved-site-matches-function",
        caller_unit.unresolved_call_sites == tuple(caller_function.unresolved_call_sites),
    )
    external = [edge for edge in caller_edges if edge.kind is CallEdgeKind.EXTERNAL_DIRECT]
    check("external-edge-preserved", len(external) == 1 and external[0].target_address == 0x9000)
    check("external-no-invented-callee", external[0].callee is None)

    ju = build_translation_units(d_indirect_jump()).unit_for("fn_2000")
    check("indirect-jump-preserved", len(ju.unresolved_jump_sites) == 1)
    check("indirect-jump-block-owned", ju.unresolved_jump_sites[0].block_id == "blk_2000")
    check("indirect-jump-no-target", ju.blocks[0].successors[0].resolved is False)

    # G. provenance / evidence / residual preservation ----------------------
    check("provenance-preserved", caller_unit.provenance == tuple(d.provenance["fn_7000"]))
    check("entry-sources-preserved", caller_unit.entry_sources == tuple(caller_function.entry_sources))
    check("source-preserved", s.source == d.cfg.source)
    check("external-inventory-preserved", [target.address for target in s.external_direct_call_targets] == [0x9000])
    check("entry-unit", s.entry_unit == "tu_fn_7000")

    candidate = build_translation_units(d_candidate())
    check("candidate-not-promoted", candidate.unit_for("fn_1000").evidence is CAND)

    shared = build_translation_units(d_shared())
    check("shared-blocks-preserved", len(shared.shared_blocks) == 1)
    check("shared-block-owner", shared.shared_blocks[0].block_id == "blk_3000")
    check("shared-block-also", shared.shared_blocks[0].also_reachable_from == ("fn_2000",))

    unowned = build_translation_units(d_unowned())
    check("unowned-blocks-preserved", unowned.unowned_blocks == ("blk_5000",))
    check("unowned-control-flow-preserved", len(unowned.unowned_control_flow) == 1)
    check("unowned-control-flow-not-invented", unowned.unowned_control_flow[0].block_id == "blk_5000")
    check(
        "unowned-control-flow-not-owned",
        all(block.id != "blk_5000" for unit in unowned.units for block in unit.blocks),
    )
    single = d_single()
    with_suppressed = build_translation_units_from(
        single.cfg,
        single.functions,
        provenance=single.provenance,
        entry_function_id=single.entry_function_id,
        suppressed_entries=(SuppressedEntry(0x4000, CAND, "test-only", owner=None),),
    )
    check("suppressed-entries-preserved", len(with_suppressed.suppressed_entries) == 1)

    # H. arbitrary-width addresses ------------------------------------------
    wide = build_translation_units(d_wide())
    check("wide-entry", wide.unit_for(f"fn_{0x1_0000_0000:x}").entry_address == 0x1_0000_0000)
    wide_internal = [edge for edge in wide.unit_for(f"fn_{0x1_0000_0000:x}").call_edges if edge.kind is CallEdgeKind.INTERNAL_DIRECT]
    check("wide-callee", wide_internal[0].callee == f"fn_{0x1_0000_0000 + 0x10:x}")
    check("wide-roundtrip", TranslationUnitSet.deserialize(wide.serialize()).serialize() == wide.serialize())

    very_wide = build_translation_units(d_very_wide())
    check("very-wide-entry", very_wide.units[0].entry_address == 0x1_0000_0000_0000_0000)
    check(
        "very-wide-serialized",
        b"18446744073709551616" in very_wide.serialize(),
    )

    # I. deterministic serialization / byte identity ------------------------
    a = build_translation_units(d_calls())
    b = build_translation_units(d_calls())
    check("deterministic-serialization", a.serialize() == b.serialize())
    check("deterministic-fingerprint", a.fingerprint() == b.fingerprint())
    check("deterministic-unit-order", [u.unit_id for u in a.units] == [u.unit_id for u in b.units])
    check("roundtrip-bytes", TranslationUnitSet.deserialize(a.serialize()).serialize() == a.serialize())
    check("roundtrip-fingerprint", TranslationUnitSet.deserialize(a.serialize()).fingerprint() == a.fingerprint())
    roundtrip = TranslationUnitSet.deserialize(a.serialize())
    check("roundtrip-unresolved", len(roundtrip.unit_for("fn_7000").unresolved_call_sites) == 1)
    check("roundtrip-direct-callees", roundtrip.unit_for("fn_7000").direct_callees == ("fn_8000",))
    check("roundtrip-shared", build_translation_units(d_shared()).serialize() == TranslationUnitSet.deserialize(
        build_translation_units(d_shared()).serialize()
    ).serialize())
    check("roundtrip-unowned", TranslationUnitSet.deserialize(build_translation_units(d_unowned()).serialize()).unowned_blocks == ("blk_5000",))

    # J. no accidental IR lowering ------------------------------------------
    module_source = Path(translation_units.__file__).read_text(encoding="utf-8")
    for forbidden in ("openrecomp.executor", "openrecomp.runtime", "openrecomp.module", "validate_ir", "make_ir"):
        check(f"no-ir-import:{forbidden}", forbidden not in module_source)
    public = [name for name in dir(translation_units) if not name.startswith("_")]
    check("no-lowering-api", not any("lower" in name.lower() or "emit" in name.lower() for name in public))
    document_text = json.dumps(s.to_document())
    check("no-ir-keys", "ir_version" not in document_text and "lowered" not in document_text)
    check("blocks-remain-neutral", all(isinstance(block, BasicBlock) for unit in s.units for block in unit.blocks))

    # K. cross-check against P2-01 ProgramModel and P2-04 CallGraph --------
    pm_edges = {(edge["from"], edge["to"]) for edge in d.program_model.direct_call_graph()}
    tu_edges = {
        (unit.function_id, edge.callee)
        for unit in s.units
        for edge in unit.call_edges
        if edge.kind is CallEdgeKind.INTERNAL_DIRECT
    }
    check("program-model-cross-check", pm_edges == tu_edges)
    cg = build_call_graph(d)
    check(
        "call-graph-cross-check",
        [edge.identity() for unit in s.units for edge in unit.call_edges]
        == [edge.identity() for edge in cg.edges],
    )

    # L. NES6502-derived translation units ----------------------------------
    nes = build_translation_units(d_nes6502())
    check("nes-one-unit-per-function", len(nes.units) == 2)
    check("nes-internal-edge", len(nes.unit_for("fn_8000").direct_callees) == 1 and nes.unit_for("fn_8000").direct_callees == ("fn_9000",))
    check("nes-block-order", nes.unit_for("fn_8000").blocks[0].entry_address == 0x8000)

    # M. malformed input fails closed ---------------------------------------
    expect_fail("non-discovery-input", lambda: build_translation_units(None))
    expect_fail("non-call-graph", lambda: build_translation_units(d_calls(), call_graph="not-a-graph"))
    expect_fail(
        "call-graph-node-mismatch",
        lambda: build_translation_units_from(
            d_calls().cfg,
            [function for function in d_calls().functions if function.id == "fn_8000"],
            entry_function_id="fn_8000",
            external_direct_call_targets=d_calls().external_direct_call_targets,
            call_graph=build_call_graph(d_calls()),
        ),
    )
    calls = d_calls()
    caller_function = next(function for function in calls.functions if function.id == "fn_7000")
    expect_fail(
        "duplicate-function-input",
        lambda: build_translation_units_from(
            calls.cfg,
            [caller_function, caller_function],
            entry_function_id="fn_7000",
            external_direct_call_targets=calls.external_direct_call_targets,
        ),
    )
    expect_fail("empty-functions", lambda: build_translation_units_from(d_single().cfg, [], entry_function_id="fn_1000"))

    block_a = BasicBlock("blk_a", 0, (I(0, "nop"),))
    block_b = BasicBlock("blk_b", 8, (I(8, "nop"),))
    expect_fail("unit-empty-blocks", lambda: TranslationUnit("tu_a", "fn_a", 0, ()))
    expect_fail("unit-entry-not-a-block", lambda: TranslationUnit("tu_a", "fn_a", 0x40, (block_a,)))
    expect_fail(
        "unit-call-edge-caller-mismatch",
        lambda: TranslationUnit(
            "tu_a",
            "fn_a",
            0,
            (block_a,),
            call_edges=(CallGraphEdge(CallEdgeKind.EXTERNAL_DIRECT, "fn_b", "blk_a", 0, "jsr", PROV, target_address=0x9999),),
        ),
    )
    expect_fail(
        "unit-direct-callees-mismatch",
        lambda: TranslationUnit("tu_a", "fn_a", 0, (block_a,), direct_callees=("fn_b",)),
    )
    expect_fail(
        "unit-unresolved-site-not-owned",
        lambda: TranslationUnit(
            "tu_a",
            "fn_a",
            0,
            (block_a,),
            unresolved_call_sites=(UnresolvedSite("blk_other", 0, "call_ix", "reason"),),
        ),
    )
    expect_fail(
        "unit-unresolved-jump-not-owned",
        lambda: TranslationUnit(
            "tu_a",
            "fn_a",
            0,
            (block_a,),
            unresolved_jump_sites=(UnresolvedSite("blk_other", 0, "jmp_ix", "reason"),),
        ),
    )

    unit_a = TranslationUnit("tu_a", "fn_a", 0, (block_a,))
    unit_b = TranslationUnit("tu_b", "fn_b", 8, (block_b,))
    expect_fail("set-empty", lambda: TranslationUnitSet(synthetic_source(), []))
    expect_fail("set-duplicate-unit-id", lambda: TranslationUnitSet(synthetic_source(), [unit_a, TranslationUnit("tu_a", "fn_b", 8, (block_b,))]))
    expect_fail("set-duplicate-function-id", lambda: TranslationUnitSet(synthetic_source(), [unit_a, TranslationUnit("tu_b", "fn_a", 8, (block_b,))]))
    block_a2 = BasicBlock("blk_a2", 0, (I(0, "nop"),))
    expect_fail("set-duplicate-entry", lambda: TranslationUnitSet(synthetic_source(), [unit_a, TranslationUnit("tu_b", "fn_b", 0, (block_a2,))]))
    expect_fail("set-unknown-entry-unit", lambda: TranslationUnitSet(synthetic_source(), [unit_a], entry_unit="tu_ghost"))
    expect_fail(
        "set-unowned-block-owned",
        lambda: TranslationUnitSet(synthetic_source(), [unit_a], unowned_blocks=["blk_a"]),
    )
    expect_fail(
        "set-external-matches-entry",
        lambda: TranslationUnitSet(
            synthetic_source(),
            [unit_a],
            external_direct_call_targets=(ExternalDirectCallTarget(0, PROV),),
        ),
    )
    expect_fail(
        "set-width-overflow",
        lambda: TranslationUnitSet(ProgramSource("synthetic", address_width_bits=8), [TranslationUnit("tu_a", "fn_a", 0x100, (BasicBlock("blk_a", 0x100, (I(0x100, "nop"),)),))]),
    )
    expect_fail(
        "set-shared-block-not-owned",
        lambda: TranslationUnitSet(synthetic_source(), [unit_a], shared_blocks=(SharedBlock("blk_ghost", "fn_a", ()),)),
    )
    expect_fail(
        "set-shared-owner-unknown",
        lambda: TranslationUnitSet(synthetic_source(), [unit_a], shared_blocks=(SharedBlock("blk_a", "fn_ghost", ()),)),
    )
    expect_fail(
        "set-unowned-control-flow-owned",
        lambda: TranslationUnitSet(
            synthetic_source(),
            [unit_a],
            unowned_control_flow=(UnresolvedSite("blk_a", 0, "jmp_ix", "reason"),),
        ),
    )
    expect_fail("deserialize-invalid-json", lambda: TranslationUnitSet.deserialize(b"{not json"))
    expect_fail("from-document-not-object", lambda: TranslationUnitSet.deserialize("[1, 2, 3]"))
    bad_version = s.to_document()
    bad_version["translation_unit_set_version"] = "9.9.9"
    expect_fail("unsupported-version", lambda: TranslationUnitSet.from_document(bad_version))
    bad_blocks = s.to_document()
    bad_blocks["units"][0]["blocks"] = []
    expect_fail("empty-unit-blocks-document", lambda: TranslationUnitSet.from_document(bad_blocks))

    # valid direct construction still succeeds ------------------------------
    valid = TranslationUnitSet(synthetic_source(), [unit_a, unit_b], entry_unit="tu_a")
    check("valid-direct-construction", valid.unit_for("fn_a") is unit_a and valid.unit_for("fn_b") is unit_b)
    expect_fail("unknown-unit-lookup", lambda: valid.unit_by_id("tu_ghost"))
    expect_fail("unknown-function-lookup", lambda: valid.unit_for("fn_ghost"))

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    if args.json:
        record = {
            "stage": "P2-05",
            "marker": f"OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "results": sorted(RESULTS, key=lambda item: item["check"]),
            "sample_fingerprints": {
                "single": build_translation_units(d_single()).fingerprint(),
                "calls": build_translation_units(d_calls()).fingerprint(),
                "shared": build_translation_units(d_shared()).fingerprint(),
                "unowned": build_translation_units(d_unowned()).fingerprint(),
                "wide": build_translation_units(d_wide()).fingerprint(),
                "nes6502": build_translation_units(d_nes6502()).fingerprint(),
            },
        }
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_TRANSLATION_UNITS_V1_JSON={out.name}")

    print(f"OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
