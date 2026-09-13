#!/usr/bin/env python3
"""Fail-closed tests for OpenRecomp deterministic function discovery (P2-03).

Proves `openrecomp/functions.py` over the P2-02 CFG and P2-01 ProgramModel with
architecture-neutral, deterministic coverage: entry sources, caller/callee
isolation, recursion, loops, ownership priority/suppression, shared tails,
external direct-call inventory, unresolved indirect non-discovery, arbitrary
address widths, NES6502-derived CFG, and the required fail-closed rejections.

No guest semantics and no ISA-specific function heuristics are introduced.
"""
from __future__ import annotations

import argparse
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
from openrecomp.cfg import CFGMode, EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import (  # noqa: E402
    FunctionDiscoveryError,
    FunctionEntry,
    FunctionEntrySource,
    discover_functions,
)
from openrecomp.program_model import (  # noqa: E402
    BasicBlock,
    DecodedInstruction,
    EvidenceClass,
    FunctionUnit,
    InstructionFlow,
    ProgramModel,
    ProgramModelError,
    ProgramSource,
    instruction_from_adapter,
)
from validate_program_model_v1 import load_and_validate  # noqa: E402

SCHEMA = json.loads((ROOT / "schema" / "openrecomp-program-v1.schema.json").read_text(encoding="utf-8"))
PROV = EvidenceClass.PROVEN
CAND = EvidenceClass.CANDIDATE

RESULTS: list[dict[str, str]] = []


def I(address, op, size=1, flow=InstructionFlow.NORMAL, evidence=PROV, target=None, unresolved=False):
    return DecodedInstruction(
        address=address, op=op, size_bytes=size, flow=flow, direct_target=target, unresolved=unresolved, evidence=evidence
    )


def mkcfg(insns, entries, *, mode=CFGMode.CLOSED, width=None, boundaries=()):
    return build_cfg(
        insns,
        source=ProgramSource("synthetic", adapter="openrecomp.synthetic", address_width_bits=width),
        entries=entries,
        mode=mode,
        region_boundaries=boundaries,
    )


def ent(address, evidence=PROV):
    return EntryPoint(address, evidence)


def fentry(address, source, evidence):
    return FunctionEntry(address, source, evidence)


def check(label, condition):
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}")


def expect_fail(label, thunk, error_type=FunctionDiscoveryError):
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


# --- CFG fixtures ----------------------------------------------------------
def cfg_single():
    return mkcfg([I(0x1000, "nop"), I(0x1001, "ret", 1, InstructionFlow.RETURN)], [ent(0x1000)])


def cfg_two_regions():
    return mkcfg(
        [I(0x100, "nop"), I(0x101, "ret", 1, InstructionFlow.RETURN), I(0x200, "nop"), I(0x201, "ret", 1, InstructionFlow.RETURN)],
        [ent(0x100)],
    )


def cfg_call():
    return mkcfg(
        [I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x8000), I(0x7003, "ret", 1, InstructionFlow.RETURN), I(0x8000, "ret", 1, InstructionFlow.RETURN)],
        [ent(0x7000)],
    )


def cfg_call_multi():
    return mkcfg(
        [
            I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x8000),
            I(0x7003, "jsr", 3, InstructionFlow.CALL, target=0x8000),
            I(0x7006, "ret", 1, InstructionFlow.RETURN),
            I(0x8000, "ret", 1, InstructionFlow.RETURN),
        ],
        [ent(0x7000)],
    )


def cfg_recursive():
    return mkcfg(
        [I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x7000), I(0x7003, "ret", 1, InstructionFlow.RETURN)],
        [ent(0x7000)],
    )


def cfg_mutual():
    return mkcfg(
        [
            I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x8000),
            I(0x7003, "ret", 1, InstructionFlow.RETURN),
            I(0x8000, "jsr", 3, InstructionFlow.CALL, target=0x7000),
            I(0x8003, "ret", 1, InstructionFlow.RETURN),
        ],
        [ent(0x7000)],
    )


def cfg_loop():
    return mkcfg(
        [I(0x3000, "add", 2), I(0x3002, "bne", 2, InstructionFlow.BRANCH, target=0x3000), I(0x3004, "ret", 1, InstructionFlow.RETURN)],
        [ent(0x3000)],
    )


def cfg_internal_branch():
    return mkcfg(
        [I(0x2000, "cmp", 2), I(0x2002, "beq", 2, InstructionFlow.BRANCH, target=0x2008), I(0x2004, "ret", 1, InstructionFlow.RETURN), I(0x2008, "ret", 1, InstructionFlow.RETURN)],
        [ent(0x2000)],
    )


def cfg_entry_above_lowest():
    return mkcfg(
        [I(0x3000, "nop"), I(0x3001, "ret", 1, InstructionFlow.RETURN), I(0x3010, "jmp", 2, InstructionFlow.JUMP, target=0x3000)],
        [ent(0x3010)],
    )


def cfg_call_external():
    return mkcfg(
        [I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x9000), I(0x7003, "ret", 1, InstructionFlow.RETURN)],
        [ent(0x7000)],
    )


def cfg_indirect_call():
    return mkcfg(
        [I(0x1000, "call_ix", 2, InstructionFlow.INDIRECT_CALL, unresolved=True), I(0x1002, "ret", 1, InstructionFlow.RETURN)],
        [ent(0x1000)],
    )


def cfg_indirect_jump():
    return mkcfg([I(0x2000, "jmp_ix", 2, InstructionFlow.INDIRECT_JUMP, unresolved=True)], [ent(0x2000)])


def cfg_trap():
    return mkcfg([I(0x4000, "trap", 1, InstructionFlow.TRAP)], [ent(0x4000)])


def cfg_shared_tail():
    return mkcfg(
        [
            I(0x1000, "jmp", 2, InstructionFlow.JUMP, target=0x1010),
            I(0x1010, "ret", 1, InstructionFlow.RETURN),
            I(0x1020, "jmp", 2, InstructionFlow.JUMP, target=0x1010),
        ],
        [ent(0x1000)],
    )


def cfg_candidate_inside_proven():
    return mkcfg(
        [I(0x1000, "nop"), I(0x1001, "nop"), I(0x1002, "ret", 1, InstructionFlow.RETURN)],
        [ent(0x1000)],
        boundaries=[0x1001],
    )


def cfg_wide():
    base = 0x1_0000_0000
    return mkcfg(
        [
            I(base, "mov", 4),
            I(base + 4, "jmp", 4, InstructionFlow.JUMP, target=base + 0x10),
            I(base + 0x10, "ret", 4, InstructionFlow.RETURN),
        ],
        [ent(base)],
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


def cfg_nes6502():
    code = bytearray(0x10000)
    code[0x8000:0x8007] = bytes([0xA9, 0x05, 0xF0, 0x02, 0xEA, 0x60, 0x60])
    instructions = []
    for address in (0x8000, 0x8002, 0x8004, 0x8005, 0x8006):
        decoded = nes6502.decode_full(code, address)
        instructions.append(instruction_from_adapter(decoded, flow=nes_flow(decoded), evidence=PROV))
    return build_cfg(
        instructions,
        source=ProgramSource("nes6502", adapter="openrecomp.nes6502", address_width_bits=16),
        entries=[ent(0x8000)],
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    tests = 0

    # 1/3/17. program / explicit entries ---------------------------------
    r = discover_functions(cfg_single(), program_entries=[0x1000])
    check("program-entry-one-function", len(r.functions) == 1 and r.functions[0].entry_address == 0x1000)
    check("program-entry-proven", r.functions[0].evidence == PROV)
    check("program-entry-source", r.functions[0].entry_sources == ("PROGRAM_ENTRY",))
    tests += 3

    r = discover_functions(cfg_single(), function_entries=[fentry(0x1000, FunctionEntrySource.EXPLICIT_PROVEN, PROV)])
    check("explicit-proven-entry", r.functions[0].entry_sources == ("EXPLICIT_PROVEN",) and r.functions[0].evidence == PROV)

    r = discover_functions(cfg_single(), function_entries=[fentry(0x1000, FunctionEntrySource.EXPLICIT_CANDIDATE, CAND)])
    check("explicit-candidate-entry", r.functions[0].entry_sources == ("EXPLICIT_CANDIDATE",) and r.functions[0].evidence == CAND)
    tests += 2

    # 2. two explicit entries -> two functions ---------------------------
    r = discover_functions(cfg_two_regions(), program_entries=[0x100], function_entries=[fentry(0x200, FunctionEntrySource.EXPLICIT_PROVEN, PROV)])
    check("two-entries-two-functions", {f.entry_address for f in r.functions} == {0x100, 0x200})
    check("two-entries-entry-function-lowest", r.entry_function_id == "fn_100")
    tests += 2

    # 4/5/6. direct call discovery and isolation -------------------------
    r = discover_functions(cfg_call(), program_entries=[0x7000])
    by_entry = {f.entry_address: f for f in r.functions}
    check("direct-call-creates-callee", set(by_entry) == {0x7000, 0x8000})
    check("caller-no-callee-block", {b.id for b in by_entry[0x7000].blocks} == {"blk_7000", "blk_7003"})
    check("callee-no-caller-continuation", {b.id for b in by_entry[0x8000].blocks} == {"blk_8000"})
    check("caller-direct-callee", by_entry[0x7000].direct_callees == ("fn_8000",))
    check("callee-entry-source", by_entry[0x8000].entry_sources == ("DIRECT_CALL",))
    check("callee-proven", by_entry[0x8000].evidence == PROV)
    tests += 6

    # 19. candidate direct-call target -----------------------------------
    cand_call = mkcfg(
        [I(0x7000, "jsr", 3, InstructionFlow.CALL, evidence=CAND, target=0x8000), I(0x7003, "ret", 1, InstructionFlow.RETURN), I(0x8000, "ret", 1, InstructionFlow.RETURN, evidence=CAND)],
        [ent(0x7000)],
    )
    r = discover_functions(cand_call, program_entries=[0x7000])
    callee = {f.entry_address: f for f in r.functions}[0x8000]
    check("candidate-callee-not-promoted", callee.evidence == CAND)
    tests += 1

    # 7. multiple calls to same callee -> one function -------------------
    r = discover_functions(cfg_call_multi(), program_entries=[0x7000])
    check("multiple-calls-one-callee", len([f for f in r.functions if f.entry_address == 0x8000]) == 1)
    tests += 1

    # 8. recursion --------------------------------------------------------
    r = discover_functions(cfg_recursive(), program_entries=[0x7000])
    check("recursive-one-function", len(r.functions) == 1 and r.functions[0].entry_address == 0x7000)
    check("recursive-self-callee", r.functions[0].direct_callees == ("fn_7000",))
    tests += 2

    # 9. mutual recursion -------------------------------------------------
    r = discover_functions(cfg_mutual(), program_entries=[0x7000])
    by_entry = {f.entry_address: f for f in r.functions}
    check("mutual-two-functions", set(by_entry) == {0x7000, 0x8000})
    check("mutual-callees", by_entry[0x7000].direct_callees == ("fn_8000",) and by_entry[0x8000].direct_callees == ("fn_7000",))
    tests += 2

    # 12/13/14. internal branch, loop, multi-block -----------------------
    r = discover_functions(cfg_internal_branch(), program_entries=[0x2000])
    check("internal-branch-one-function", len(r.functions) == 1 and len(r.functions[0].blocks) == 3)
    r = discover_functions(cfg_loop(), program_entries=[0x3000])
    check("internal-loop-one-function", len(r.functions) == 1 and {b.id for b in r.functions[0].blocks} == {"blk_3000", "blk_3004"})
    tests += 2

    # 10/11. return / trap terminated ------------------------------------
    r = discover_functions(cfg_single(), program_entries=[0x1000])
    check("return-terminated", r.functions[0].blocks[-1].terminal_flow() == InstructionFlow.RETURN)
    r = discover_functions(cfg_trap(), program_entries=[0x4000])
    check("trap-terminated", len(r.functions) == 1 and r.functions[0].blocks[0].terminal_flow() == InstructionFlow.TRAP)
    tests += 2

    # 15. disconnected region stays unowned ------------------------------
    r = discover_functions(cfg_two_regions(), program_entries=[0x100])
    check("disconnected-unowned", "blk_200" in r.unowned_blocks and all(b.id != "blk_200" for f in r.functions for b in f.blocks))
    tests += 1

    # 22. address above 0xFFFFFFFF ---------------------------------------
    base = 0x1_0000_0000
    r = discover_functions(cfg_wide(), program_entries=[base])
    check("wide-function-entry", r.functions[0].entry_address == base)
    check("wide-block-membership", {b.id for b in r.functions[0].blocks} == {f"blk_{base:x}", f"blk_{base + 0x10:x}"})
    tests += 2

    # 20/21/35. unresolved indirect non-discovery ------------------------
    r = discover_functions(cfg_indirect_call(), program_entries=[0x1000])
    check("indirect-call-no-function", len(r.functions) == 1 and r.functions[0].unresolved_call_sites[0].address == 0x1000)
    r = discover_functions(cfg_indirect_jump(), program_entries=[0x2000])
    check("indirect-jump-no-function", len(r.functions) == 1)
    check("indirect-jump-no-target", all(f.entry_address == 0x2000 for f in r.functions))
    tests += 3

    # 23. NES6502-derived CFG --------------------------------------------
    r = discover_functions(cfg_nes6502(), program_entries=[0x8000])
    check("nes-one-function", len(r.functions) == 1 and r.functions[0].entry_address == 0x8000)
    check("nes-block-membership", {b.id for b in r.functions[0].blocks} == {"blk_8000", "blk_8004", "blk_8006"})
    check("nes-evidence", r.functions[0].evidence == PROV)
    tests += 3

    # 16/17b. evidence propagation ---------------------------------------
    cand_block_cfg = mkcfg(
        [I(0x1000, "nop", evidence=CAND), I(0x1001, "ret", 1, InstructionFlow.RETURN, evidence=CAND)],
        [ent(0x1000)],
    )
    r = discover_functions(cand_block_cfg, program_entries=[0x1000])
    check("candidate-blocks-not-promoted", r.functions[0].evidence == CAND)
    tests += 1

    # 30. shared tail policy ---------------------------------------------
    r = discover_functions(cfg_shared_tail(), program_entries=[0x1000], function_entries=[fentry(0x1020, FunctionEntrySource.EXPLICIT_PROVEN, PROV)])
    by_entry = {f.entry_address: f for f in r.functions}
    check("shared-tail-two-functions", set(by_entry) == {0x1000, 0x1020})
    check("shared-tail-single-owner", r.shared_blocks and r.shared_blocks[0].block_id == "blk_1010")
    check("shared-tail-owner-deterministic", r.shared_blocks[0].owner == "fn_1000" and r.shared_blocks[0].also_reachable_from == ("fn_1020",))
    check("shared-tail-loser-keeps-entry", "blk_1020" in {b.id for b in by_entry[0x1020].blocks})
    tests += 4

    # 31. candidate inside proven -> suppressed --------------------------
    r = discover_functions(
        cfg_candidate_inside_proven(),
        program_entries=[0x1000],
        function_entries=[fentry(0x1001, FunctionEntrySource.EXPLICIT_CANDIDATE, CAND)],
    )
    check("candidate-inside-proven-suppressed", len(r.functions) == 1 and r.functions[0].entry_address == 0x1000)
    check("candidate-inside-proven-reason", len(r.suppressed_entries) == 1 and r.suppressed_entries[0].address == 0x1001)
    tests += 2

    # proven nested in proven: deterministic cross-function boundary -----
    r = discover_functions(
        cfg_candidate_inside_proven(),
        program_entries=[0x1000],
        function_entries=[fentry(0x1001, FunctionEntrySource.EXPLICIT_PROVEN, PROV)],
    )
    by_entry = {f.entry_address: f for f in r.functions}
    check("proven-nested-both-functions", set(by_entry) == {0x1000, 0x1001})
    check("proven-nested-no-cross-ownership", "blk_1001" not in {b.id for b in by_entry[0x1000].blocks})
    check("proven-nested-cross-edge", any(s.target_block == "blk_1001" for s in by_entry[0x1000].blocks[0].successors))
    tests += 3

    # 33. caller/callee boundary via a direct jump (tail transfer) -------
    tail_cfg = mkcfg(
        [I(0x1000, "jmp", 2, InstructionFlow.JUMP, target=0x1010), I(0x1010, "ret", 1, InstructionFlow.RETURN)],
        [ent(0x1000)],
    )
    r = discover_functions(tail_cfg, program_entries=[0x1000], function_entries=[fentry(0x1010, FunctionEntrySource.EXPLICIT_PROVEN, PROV)])
    by_entry = {f.entry_address: f for f in r.functions}
    check("tail-transfer-separate-functions", set(by_entry) == {0x1000, 0x1010})
    check("tail-transfer-not-absorbed", "blk_1010" not in {b.id for b in by_entry[0x1000].blocks})
    tests += 2

    # 36. entry block not lowest address ---------------------------------
    r = discover_functions(cfg_entry_above_lowest(), program_entries=[0x3010])
    function = r.functions[0]
    check("entry-not-lowest-first", function.blocks[0].entry_address == 0x3010)
    check("entry-not-lowest-membership", {b.id for b in function.blocks} == {"blk_3010", "blk_3000"})
    serialized = function.to_document()
    check("entry-not-lowest-canonical", serialized["blocks"][0]["entry_address"] == 0x3010)
    restored = ProgramModel.deserialize(r.to_program_model().serialize())
    check("entry-not-lowest-roundtrip", restored.serialize() == r.to_program_model().serialize())
    tests += 4

    # 35b. external direct-call inventory --------------------------------
    r = discover_functions(cfg_call_external(), program_entries=[0x7000])
    check("external-target-recorded", [(t.address, t.evidence) for t in r.external_direct_call_targets] == [(0x9000, PROV)])
    check("external-target-no-function", {f.entry_address for f in r.functions} == {0x7000})
    check("external-target-not-callee", r.functions[0].direct_callees == ())
    tests += 3

    # 24/25/26. determinism ----------------------------------------------
    a = discover_functions(cfg_internal_branch(), program_entries=[0x2000])
    b = discover_functions(cfg_internal_branch(), program_entries=[0x2000])
    check("deterministic-serialization", a.serialize() == b.serialize())
    check("deterministic-fingerprint", a.fingerprint() == b.fingerprint())
    check("deterministic-order", [f.id for f in a.functions] == [f.id for f in b.functions])
    check("deterministic-membership", [ [blk.id for blk in f.blocks] for f in a.functions] == [[blk.id for blk in f.blocks] for f in b.functions])
    tests += 4

    # entry_sources serialization + schema ------------------------------
    doc = a.to_program_model().to_document()
    jsonschema.validate(doc, SCHEMA)
    check("schema-entry-sources", doc["functions"][0].get("entry_sources") == ["PROGRAM_ENTRY"])
    restored = ProgramModel.deserialize(a.to_program_model().serialize())
    check("entry-sources-survive", restored.function("fn_2000").entry_sources == ("PROGRAM_ENTRY",))
    plain = FunctionUnit("fn_plain", 0, (BasicBlock("blk_p", 0, (I(0, "nop"),)),)).to_document()
    check("entry-sources-omitted-when-empty", "entry_sources" not in plain)
    tests += 4

    # CLI validator accepts the discovered program model -----------------
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "functions.program.json"
        path.write_bytes(a.to_program_model().serialize())
        check("functions-program-valid", load_and_validate(path) is not None)
        tests += 1

    # fail-closed rejections --------------------------------------------
    expect_fail("missing-entry", lambda: discover_functions(cfg_single(), program_entries=[0x9999]))
    expect_fail("entry-not-block-boundary", lambda: discover_functions(cfg_single(), program_entries=[0x1001]))
    interior_cfg = mkcfg([I(0x1000, "nop", 2), I(0x1002, "ret", 1, InstructionFlow.RETURN)], [ent(0x1000)])
    expect_fail("entry-instruction-interior", lambda: discover_functions(interior_cfg, program_entries=[0x1001]))
    expect_fail("no-entries", lambda: discover_functions(cfg_single(), include_direct_call_targets=False))
    expect_fail("invalid-proven-evidence", lambda: fentry(0x1000, FunctionEntrySource.EXPLICIT_PROVEN, CAND))
    expect_fail("invalid-candidate-evidence", lambda: fentry(0x1000, FunctionEntrySource.EXPLICIT_CANDIDATE, PROV))
    tests += 6

    # malformed FunctionUnit / ProgramModel membership rejection ---------
    block = BasicBlock("blk_x", 0, (I(0, "nop"),))
    function_a = FunctionUnit("fn_a", 0, (block,))
    function_b = FunctionUnit("fn_b", 0, (block,))
    expect_fail(
        "duplicate-block-membership-rejected",
        lambda: ProgramModel(ProgramSource("synthetic"), [function_a, function_b], "fn_a"),
        ProgramModelError,
    )
    tests += 1

    if args.json:
        record = {
            "stage": "P2-03",
            "marker": f"OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "results": sorted(RESULTS, key=lambda item: item["check"]),
            "sample_fingerprints": {
                "call": discover_functions(cfg_call(), program_entries=[0x7000]).fingerprint(),
                "nes6502": discover_functions(cfg_nes6502(), program_entries=[0x8000]).fingerprint(),
                "wide": discover_functions(cfg_wide(), program_entries=[base]).fingerprint(),
                "shared_tail": discover_functions(cfg_shared_tail(), program_entries=[0x1000], function_entries=[fentry(0x1020, FunctionEntrySource.EXPLICIT_PROVEN, PROV)]).fingerprint(),
            },
        }
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_FUNCTION_DISCOVERY_V1_JSON={out.name}")

    print(f"OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
