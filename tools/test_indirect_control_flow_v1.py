#!/usr/bin/env python3
"""Fail-closed tests for OpenRecomp indirect-control-flow classification (P2-06).

Proves `openrecomp/indirect_control_flow.py` over the completed P2-05
translation-unit set: deterministic classification of indirect call/jump sites,
exact resolved targets and finite proven target sets, bounded candidates that are
never promoted, external/runtime-mediated and return-like classification from
explicit proof, preservation of unresolved evidence and provenance, canonical
serialization/round-trip, arbitrary-width addresses, and all fail-closed
rejections. It also proves that no target is invented from address-shaped
metadata or nearby code, that no IR is lowered and no host code is emitted.

The test fixtures are synthetic/open and contain no guest semantics.
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
import openrecomp.indirect_control_flow as indirect_control_flow  # noqa: E402
from openrecomp.cfg import EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.indirect_control_flow import (  # noqa: E402
    IndirectControlFlowBasis,
    IndirectControlFlowClassification,
    IndirectControlFlowError,
    IndirectControlFlowEvidence,
    IndirectControlFlowKind,
    IndirectControlFlowSet,
    IndirectControlFlowStatus,
    IndirectControlFlowUnit,
    classify_indirect_control_flow,
    classify_indirect_control_flow_from,
)
from openrecomp.program_model import (  # noqa: E402
    DecodedInstruction,
    EvidenceClass,
    InstructionFlow,
    ProgramSource,
    UnresolvedSite,
    instruction_from_adapter,
)
from openrecomp.translation_units import build_translation_units  # noqa: E402

PROV = EvidenceClass.PROVEN
CAND = EvidenceClass.CANDIDATE

CALL = IndirectControlFlowKind.INDIRECT_CALL
JUMP = IndirectControlFlowKind.INDIRECT_JUMP
RESOLVED = IndirectControlFlowStatus.RESOLVED
BOUNDED = IndirectControlFlowStatus.BOUNDED_CANDIDATES
EXTERNAL = IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED
RETURN_LIKE = IndirectControlFlowStatus.RETURN_LIKE
UNRESOLVED_CALL = IndirectControlFlowStatus.UNRESOLVED_INDIRECT_CALL
UNRESOLVED_JUMP = IndirectControlFlowStatus.UNRESOLVED_INDIRECT_JUMP

EXACT_ONE = IndirectControlFlowBasis.EXACT_CONSTANT_TARGET
EXACT_SET = IndirectControlFlowBasis.EXACT_TARGET_SET
ADAPTER = IndirectControlFlowBasis.ADAPTER_EVIDENCE
BOUNDED_EV = IndirectControlFlowBasis.BOUNDED_CANDIDATE_EVIDENCE
EXTERNAL_EV = IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE
RETURN_EV = IndirectControlFlowBasis.STRUCTURAL_RETURN_EVIDENCE
NO_BASIS = IndirectControlFlowBasis.NONE

RESULTS: list[dict[str, str]] = []


def I(address, op, size=1, flow=InstructionFlow.NORMAL, evidence=PROV, target=None, unresolved=False, metadata=None):
    return DecodedInstruction(
        address=address,
        op=op,
        size_bytes=size,
        flow=flow,
        direct_target=target,
        unresolved=unresolved,
        evidence=evidence,
        metadata=metadata or {},
    )


def check(label, condition):
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}")


def expect_fail(label, thunk, error_type=IndirectControlFlowError):
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


def source(width=None):
    return ProgramSource("synthetic", adapter="openrecomp.synthetic", address_width_bits=width)


def translation_units(insns, program_entries, *, width=None):
    cfg = build_cfg(
        insns,
        source=source(width),
        entries=[EntryPoint(address, PROV) for address in program_entries],
    )
    return build_translation_units(discover_functions(cfg, program_entries=program_entries))


def ev(function_id, block_id, address, kind, status, basis, *, targets=(), mechanism=None, detail=None, source_label="fixture", evidence=PROV):
    return IndirectControlFlowEvidence(
        function_id=function_id,
        block_id=block_id,
        address=address,
        kind=kind,
        status=status,
        basis=basis,
        targets=targets,
        external_mechanism=mechanism,
        detail=detail,
        source=source_label,
        evidence=evidence,
    )


# --- fixtures --------------------------------------------------------------
def f_none():
    return translation_units([I(0x1000, "nop"), I(0x1001, "ret", 1, InstructionFlow.RETURN)], [0x1000])


def f_call():
    return translation_units(
        [
            I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x8000),
            I(0x7003, "call_ix", 2, InstructionFlow.INDIRECT_CALL, unresolved=True),
            I(0x7005, "ret", 1, InstructionFlow.RETURN),
            I(0x8000, "ret", 1, InstructionFlow.RETURN),
        ],
        [0x7000],
    )


def f_jump():
    return translation_units([I(0x2000, "jmp_ix", 2, InstructionFlow.INDIRECT_JUMP, unresolved=True)], [0x2000])


def f_both():
    return translation_units(
        [
            I(0x1000, "call_ix", 2, InstructionFlow.INDIRECT_CALL, unresolved=True),
            I(0x1002, "jmp_ix", 2, InstructionFlow.INDIRECT_JUMP, unresolved=True),
        ],
        [0x1000],
    )


def f_multi():
    return translation_units(
        [
            I(0x1000, "call_ix", 2, InstructionFlow.INDIRECT_CALL, unresolved=True),
            I(0x1002, "ret", 1, InstructionFlow.RETURN),
            I(0x2000, "jmp_ix", 2, InstructionFlow.INDIRECT_JUMP, unresolved=True),
        ],
        [0x1000, 0x2000],
    )


def f_set():
    return translation_units(
        [
            I(0x7000, "jsr", 3, InstructionFlow.CALL, target=0x8000),
            I(0x7003, "jsr", 3, InstructionFlow.CALL, target=0x9000),
            I(0x7006, "call_ix", 2, InstructionFlow.INDIRECT_CALL, unresolved=True),
            I(0x7008, "ret", 1, InstructionFlow.RETURN),
            I(0x8000, "ret", 1, InstructionFlow.RETURN),
            I(0x9000, "ret", 1, InstructionFlow.RETURN),
        ],
        [0x7000],
    )


def f_wide():
    base = 0x1_0000_0000
    return translation_units(
        [
            I(base, "jsr", 4, InstructionFlow.CALL, target=base + 0x10),
            I(base + 4, "call_ix", 4, InstructionFlow.INDIRECT_CALL, unresolved=True),
            I(base + 8, "ret", 4, InstructionFlow.RETURN),
            I(base + 0x10, "ret", 4, InstructionFlow.RETURN),
        ],
        [base],
        width=64,
    )


def f_very_wide():
    base = 0x1_0000_0000_0000_0000
    return translation_units(
        [I(base, "jmp_ix", 1, InstructionFlow.INDIRECT_JUMP, unresolved=True)],
        [base],
    )


def f_zero():
    return translation_units(
        [I(0x0, "jmp_ix", 1, InstructionFlow.INDIRECT_JUMP, unresolved=True)],
        [0x0],
    )


def f_metadata_addr():
    return translation_units(
        [I(0x3000, "jmp_ix", 2, InstructionFlow.INDIRECT_JUMP, unresolved=True, metadata={"target_hint": 0x4000, "indirect": 0x4000})],
        [0x3000],
    )


def f_nearby():
    return translation_units(
        [
            I(0x2000, "branch", 1, InstructionFlow.BRANCH, target=0x3000),
            I(0x2001, "jmp_ix", 1, InstructionFlow.INDIRECT_JUMP, unresolved=True),
            I(0x3000, "ret", 1, InstructionFlow.RETURN),
        ],
        [0x2000],
    )


def f_unowned():
    return translation_units(
        [
            I(0x1000, "ret", 1, InstructionFlow.RETURN),
            I(0x5000, "jmp_ix", 2, InstructionFlow.INDIRECT_JUMP, unresolved=True),
        ],
        [0x1000],
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


def f_nes():
    code = bytearray(0x10000)
    code[0x8000:0x8003] = bytes([0x6C, 0x00, 0x90])
    decoded = nes6502.decode_full(code, 0x8000)
    flow = nes_flow(decoded)
    instruction = instruction_from_adapter(
        decoded,
        flow=flow,
        unresolved=flow is InstructionFlow.INDIRECT_JUMP,
        evidence=PROV,
    )
    instructions = [instruction]
    cfg = build_cfg(
        instructions,
        source=ProgramSource("nes6502", adapter="openrecomp.nes6502", address_width_bits=16),
        entries=[EntryPoint(0x8000, PROV)],
    )
    return build_translation_units(discover_functions(cfg, program_entries=[0x8000]))


def build(units, records=()):
    return classify_indirect_control_flow(units, evidence=records)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # A. deterministic classification / structural enumeration ---------------
    none_units = f_none()
    none_set = classify_indirect_control_flow(none_units)
    check("empty-unit-preserved", len(none_set.units) == 1 and none_set.unit_for("fn_1000").site_count() == 0)
    check("empty-no-classifications", none_set.classifications() == ())
    check("empty-status-counts-zero", sum(none_set.status_counts().values()) == 0)

    call_units = f_call()
    call_set = classify_indirect_control_flow(call_units)
    check("call-one-site", len(call_set.classifications()) == 1)
    call_cls = call_set.classification_for("fn_7000", "blk_7003", 0x7003, CALL)
    check("call-unresolved-status", call_cls.status is UNRESOLVED_CALL)
    check("call-basis-none", call_cls.basis is NO_BASIS)
    check("call-no-targets", call_cls.targets == () and call_cls.target_functions == ())
    check("call-kind", call_cls.kind is CALL)
    check("call-op", call_cls.op == "call_ix")
    check("call-provenance-structural", "P2-05:TranslationUnit.unresolved_call_sites" in call_cls.provenance)
    check("call-provenance-p2-04", "P2-04:CallGraphEdge.UNRESOLVED_INDIRECT" in call_cls.provenance)
    check("call-provenance-p2-02", "P2-02:InstructionFlow.INDIRECT_CALL" in call_cls.provenance)

    jump_units = f_jump()
    jump_set = classify_indirect_control_flow(jump_units)
    jump_cls = jump_set.classification_for("fn_2000", "blk_2000", 0x2000, JUMP)
    check("jump-unresolved-status", jump_cls.status is UNRESOLVED_JUMP)
    check("jump-provenance-structural", "P2-05:TranslationUnit.unresolved_jump_sites" in jump_cls.provenance)
    check("jump-provenance-p2-02", "P2-02:InstructionFlow.INDIRECT_JUMP" in jump_cls.provenance)

    both_set = classify_indirect_control_flow(f_both())
    check("both-two-sites", len(both_set.classifications()) == 2)
    check(
        "both-kinds",
        {item.kind for item in both_set.classifications()} == {CALL, JUMP},
    )
    check("both-statuses", {item.status for item in both_set.classifications()} == {UNRESOLVED_CALL, UNRESOLVED_JUMP})

    # B. provenance preservation -------------------------------------------
    unit = call_units.unit_for("fn_7000")
    original_site = unit.unresolved_call_sites[0]
    check("original-unresolved-site-preserved", call_cls.unresolved_site is original_site or call_cls.unresolved_site == original_site)
    check("source-function-provenance", call_cls.function_id == "fn_7000" and call_cls.unit_id == unit.unit_id)
    check("source-block-provenance", call_cls.block_id == "blk_7003")
    check("source-instruction-provenance", call_cls.address == 0x7003 and call_cls.op == "call_ix")
    check("entry-address-provenance", call_cls.entry_address == 0x7000)

    before = call_units.fingerprint()
    classify_indirect_control_flow(call_units)
    check("p2-05-unmutated", call_units.fingerprint() == before)

    # C. low-level entry point equivalence ----------------------------------
    low = classify_indirect_control_flow_from(
        call_units.units,
        source=call_units.source,
        unowned_control_flow=call_units.unowned_control_flow,
    )
    check("low-level-equivalent", low.serialize() == call_set.serialize())

    # D. exact resolved single target ---------------------------------------
    resolved = build(call_units, [ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_ONE, targets=(0x8000,), detail="proven")])
    resolved_cls = resolved.classification_for("fn_7000", "blk_7003", 0x7003, CALL)
    check("resolved-status", resolved_cls.status is RESOLVED and resolved_cls.resolved)
    check("resolved-targets", resolved_cls.targets == (0x8000,))
    check("resolved-target-function", resolved_cls.target_functions == ("fn_8000",))
    check("resolved-basis", resolved_cls.basis is EXACT_ONE)
    check("resolved-evidence-proven", resolved_cls.evidence is PROV)
    check("resolved-detail", resolved_cls.detail == "proven")
    check("resolved-provenance-evidence", "evidence:fixture" in resolved_cls.provenance)
    check("resolved-preserves-unresolved-site", resolved_cls.unresolved_site is not None)

    # E. exact finite proven target set -------------------------------------
    set_units = f_set()
    exact_set = build(
        set_units,
        [ev("fn_7000", "blk_7006", 0x7006, CALL, RESOLVED, EXACT_SET, targets=(0x9000, 0x8000))],
    )
    exact_cls = exact_set.classification_for("fn_7000", "blk_7006", 0x7006, CALL)
    check("exact-set-resolved", exact_cls.status is RESOLVED)
    check("exact-set-canonical-order", exact_cls.targets == (0x8000, 0x9000))
    check("exact-set-functions", exact_cls.target_functions == ("fn_8000", "fn_9000"))
    check("exact-set-evidence-count", len(exact_set.classifications()) == 1)

    nonfunction = build(call_units, [ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_ONE, targets=(0x1234,))])
    nonfunction_cls = nonfunction.classification_for("fn_7000", "blk_7003", 0x7003, CALL)
    check("exact-nonfunction-target-recorded", nonfunction_cls.targets == (0x1234,))
    check("exact-nonfunction-no-fabricated-function", nonfunction_cls.target_functions == ())

    # F. bounded candidates never become resolved ---------------------------
    bounded = build(
        call_units,
        [
            ev(
                "fn_7000",
                "blk_7003",
                0x7003,
                CALL,
                BOUNDED,
                BOUNDED_EV,
                targets=(0x9000, 0x8000, 0xA000),
            )
        ],
    )
    bounded_cls = bounded.classification_for("fn_7000", "blk_7003", 0x7003, CALL)
    check("bounded-status", bounded_cls.status is BOUNDED)
    check("bounded-not-resolved", not bounded_cls.resolved and bounded_cls.status is not RESOLVED)
    check("bounded-canonical-order", bounded_cls.targets == (0x8000, 0x9000, 0xA000))
    check("bounded-functions-subset", bounded_cls.target_functions == ("fn_8000",))
    check("bounded-basis", bounded_cls.basis is BOUNDED_EV)

    bounded_candidate = build(
        call_units,
        [ev("fn_7000", "blk_7003", 0x7003, CALL, BOUNDED, BOUNDED_EV, targets=(0x8000,), evidence=CAND)],
    )
    bc_cls = bounded_candidate.classification_for("fn_7000", "blk_7003", 0x7003, CALL)
    check("bounded-candidate-evidence-allowed", bc_cls.status is BOUNDED)
    check("bounded-candidate-not-promoted", not bc_cls.resolved and bc_cls.evidence is CAND)

    # G. external / runtime mediated ----------------------------------------
    external = build(
        jump_units,
        [ev("fn_2000", "blk_2000", 0x2000, JUMP, EXTERNAL, EXTERNAL_EV, mechanism="syscall_dispatch")],
    )
    ext_cls = external.classification_for("fn_2000", "blk_2000", 0x2000, JUMP)
    check("external-status", ext_cls.status is EXTERNAL)
    check("external-no-targets", ext_cls.targets == ())
    check("external-mechanism", ext_cls.external_mechanism == "syscall_dispatch")
    check("external-not-resolved", not ext_cls.resolved)

    # H. return-like classification -----------------------------------------
    ret = build(jump_units, [ev("fn_2000", "blk_2000", 0x2000, JUMP, RETURN_LIKE, RETURN_EV)])
    ret_cls = ret.classification_for("fn_2000", "blk_2000", 0x2000, JUMP)
    check("return-like-status", ret_cls.status is RETURN_LIKE)
    check("return-like-no-targets", ret_cls.targets == ())
    check("return-like-basis", ret_cls.basis is RETURN_EV)
    check("return-like-not-classified-without-proof", jump_cls.status is UNRESOLVED_JUMP and jump_cls.status is not RETURN_LIKE)

    # I. no invented target --------------------------------------------------
    metadata_set = classify_indirect_control_flow(f_metadata_addr())
    metadata_cls = metadata_set.classification_for("fn_3000", "blk_3000", 0x3000, JUMP)
    check("metadata-address-not-used", metadata_cls.status is UNRESOLVED_JUMP and metadata_cls.targets == ())
    check("metadata-no-fabricated-function", metadata_cls.target_functions == ())

    nearby_set = classify_indirect_control_flow(f_nearby())
    nearby_cls = nearby_set.classification_for("fn_2000", "blk_2001", 0x2001, JUMP)
    check("nearby-code-not-used", nearby_cls.status is UNRESOLVED_JUMP and nearby_cls.targets == ())

    # J. fail-closed claim validation ---------------------------------------
    expect_fail("evidence-resolved-candidate-evidence", lambda: ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_ONE, targets=(0x8000,), evidence=CAND))
    expect_fail("evidence-resolved-without-target", lambda: ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_ONE))
    expect_fail("evidence-constant-two-targets", lambda: ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_ONE, targets=(0x8000, 0x9000)))
    expect_fail("evidence-set-one-target", lambda: ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_SET, targets=(0x8000,)))
    expect_fail("evidence-resolved-none-basis", lambda: ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, NO_BASIS, targets=(0x8000,)))
    expect_fail("evidence-external-with-targets", lambda: ev("fn_2000", "blk_2000", 0x2000, JUMP, EXTERNAL, EXTERNAL_EV, targets=(0x8000,), mechanism="m"))
    expect_fail("evidence-external-without-mechanism", lambda: ev("fn_2000", "blk_2000", 0x2000, JUMP, EXTERNAL, EXTERNAL_EV))
    expect_fail("evidence-bounded-without-target", lambda: ev("fn_7000", "blk_7003", 0x7003, CALL, BOUNDED, BOUNDED_EV))
    expect_fail("evidence-return-like-with-targets", lambda: ev("fn_2000", "blk_2000", 0x2000, JUMP, RETURN_LIKE, RETURN_EV, targets=(0x8000,)))
    expect_fail("evidence-return-like-on-call", lambda: ev("fn_7000", "blk_7003", 0x7003, CALL, RETURN_LIKE, RETURN_EV))
    expect_fail("evidence-positive-none-basis", lambda: ev("fn_7000", "blk_7003", 0x7003, CALL, BOUNDED, NO_BASIS, targets=(0x8000,)))
    expect_fail(
        "evidence-unresolved-status-rejected",
        lambda: ev("fn_7000", "blk_7003", 0x7003, CALL, UNRESOLVED_CALL, NO_BASIS),
    )
    expect_fail(
        "evidence-duplicate-targets",
        lambda: ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_SET, targets=(0x8000, 0x8000)),
    )
    expect_fail(
        "evidence-negative-target",
        lambda: ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_ONE, targets=(-1,)),
    )
    expect_fail(
        "evidence-bad-address",
        lambda: ev("fn_7000", "blk_7003", True, CALL, RESOLVED, EXACT_ONE, targets=(0x8000,)),
    )

    # K. classification rejection -------------------------------------------
    good = resolved.classification_for("fn_7000", "blk_7003", 0x7003, CALL)
    doc = good.to_document()
    check("classification-roundtrip", IndirectControlFlowClassification.from_document(doc).to_document() == doc)
    expect_fail("classification-missing-provenance", lambda: IndirectControlFlowClassification(
        unit_id="tu_fn_7000", function_id="fn_7000", entry_address=0x7000, block_id="blk_7003", address=0x7003,
        op="call_ix", kind=CALL, status=UNRESOLVED_CALL, basis=NO_BASIS, provenance=(), unresolved_site=good.unresolved_site,
    ))
    expect_fail("classification-missing-unresolved-site", lambda: IndirectControlFlowClassification(
        unit_id="tu_fn_7000", function_id="fn_7000", entry_address=0x7000, block_id="blk_7003", address=0x7003,
        op="call_ix", kind=CALL, status=UNRESOLVED_CALL, basis=NO_BASIS, provenance=("x",), unresolved_site=None,
    ))
    wrong_site = UnresolvedSite("blk_other", 0x9999, "call_ix", "reason")
    expect_fail("classification-unresolved-site-mismatch", lambda: IndirectControlFlowClassification(
        unit_id="tu_fn_7000", function_id="fn_7000", entry_address=0x7000, block_id="blk_7003", address=0x7003,
        op="call_ix", kind=CALL, status=UNRESOLVED_CALL, basis=NO_BASIS, provenance=("x",), unresolved_site=wrong_site,
    ))
    expect_fail("classification-contradictory-targets", lambda: IndirectControlFlowClassification(
        unit_id="tu_fn_7000", function_id="fn_7000", entry_address=0x7000, block_id="blk_7003", address=0x7003,
        op="call_ix", kind=CALL, status=RESOLVED, basis=EXACT_ONE, targets=(), evidence=PROV,
        provenance=("x",), unresolved_site=good.unresolved_site,
    ))
    bad_status = dict(doc)
    bad_status["status"] = "BOGUS"
    expect_fail("classification-unknown-status", lambda: IndirectControlFlowClassification.from_document(bad_status))
    bad_basis = dict(doc)
    bad_basis["basis"] = "BOGUS"
    expect_fail("classification-unknown-basis", lambda: IndirectControlFlowClassification.from_document(bad_basis))
    bad_kind = dict(doc)
    bad_kind["kind"] = "BOGUS"
    expect_fail("classification-unknown-kind", lambda: IndirectControlFlowClassification.from_document(bad_kind))
    no_prov = dict(doc)
    no_prov["provenance"] = []
    expect_fail("classification-document-no-provenance", lambda: IndirectControlFlowClassification.from_document(no_prov))
    no_site = dict(doc)
    no_site["unresolved_site"] = None
    expect_fail("classification-document-no-site", lambda: IndirectControlFlowClassification.from_document(no_site))
    bad_evidence = dict(doc)
    bad_evidence["evidence"] = "BOGUS"
    expect_fail("classification-unknown-evidence", lambda: IndirectControlFlowClassification.from_document(bad_evidence))

    # L. site matching / evidence rejection ---------------------------------
    expect_fail(
        "evidence-unknown-site",
        lambda: build(call_units, [ev("fn_7000", "blk_7003", 0x9999, CALL, RESOLVED, EXACT_ONE, targets=(0x8000,))]),
    )
    expect_fail(
        "evidence-kind-mismatch",
        lambda: build(call_units, [ev("fn_7000", "blk_7003", 0x7003, JUMP, RESOLVED, EXACT_ONE, targets=(0x8000,))]),
    )
    expect_fail(
        "evidence-duplicate",
        lambda: build(
            call_units,
            [
                ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_ONE, targets=(0x8000,)),
                ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_ONE, targets=(0x8000,)),
            ],
        ),
    )
    expect_fail(
        "evidence-conflict",
        lambda: build(
            call_units,
            [
                ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_ONE, targets=(0x8000,)),
                ev("fn_7000", "blk_7003", 0x7003, CALL, BOUNDED, BOUNDED_EV, targets=(0x8000, 0x9000)),
            ],
        ),
    )
    expect_fail("non-unit-set-input", lambda: classify_indirect_control_flow(None))
    expect_fail("empty-units", lambda: classify_indirect_control_flow_from((), source=source(), unowned_control_flow=()))
    expect_fail(
        "non-translation-unit",
        lambda: classify_indirect_control_flow_from((None,), source=source(), unowned_control_flow=()),
    )
    expect_fail(
        "non-evidence",
        lambda: classify_indirect_control_flow(call_units, evidence=("not-evidence",)),
    )

    # M. unit / set structural rejection ------------------------------------
    check("unit-rejects-wrong-function", expect_unit_error(call_units, resolved))
    expect_fail(
        "set-duplicate-unit-id",
        lambda: IndirectControlFlowSet(
            source(),
            [
                IndirectControlFlowUnit("tu_a", "fn_a", 0),
                IndirectControlFlowUnit("tu_a", "fn_b", 8),
            ],
        ),
    )
    expect_fail(
        "set-duplicate-function-id",
        lambda: IndirectControlFlowSet(
            source(),
            [
                IndirectControlFlowUnit("tu_a", "fn_a", 0),
                IndirectControlFlowUnit("tu_b", "fn_a", 8),
            ],
        ),
    )
    expect_fail(
        "set-unowned-owned-block",
        lambda: IndirectControlFlowSet(
            source(),
            [IndirectControlFlowUnit("tu_a", "fn_a", 0, (good,))],
            unowned_control_flow=(good.unresolved_site,),
        ),
    )
    expect_fail("set-empty", lambda: IndirectControlFlowSet(source(), []))
    expect_fail("set-bad-unowned-type", lambda: IndirectControlFlowSet(source(), [IndirectControlFlowUnit("tu_a", "fn_a", 0)], unowned_control_flow=(object(),)))

    # N. determinism / serialization ----------------------------------------
    a = build(call_units, [ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_ONE, targets=(0x8000,))])
    b = build(f_call(), [ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_ONE, targets=(0x8000,))])
    check("deterministic-serialization", a.serialize() == b.serialize())
    check("deterministic-fingerprint", a.fingerprint() == b.fingerprint())
    check("roundtrip-bytes", IndirectControlFlowSet.deserialize(a.serialize()).serialize() == a.serialize())
    check("roundtrip-fingerprint", IndirectControlFlowSet.deserialize(a.serialize()).fingerprint() == a.fingerprint())
    roundtrip = IndirectControlFlowSet.deserialize(a.serialize())
    check("roundtrip-resolved", roundtrip.classification_for("fn_7000", "blk_7003", 0x7003, CALL).status is RESOLVED)
    check("roundtrip-targets", roundtrip.classification_for("fn_7000", "blk_7003", 0x7003, CALL).targets == (0x8000,))

    multi = classify_indirect_control_flow(f_multi())
    check("multi-unit-order", [u.function_id for u in multi.units] == ["fn_1000", "fn_2000"])
    multi_reversed = IndirectControlFlowSet(multi.source, list(reversed(multi.units)), unowned_control_flow=multi.unowned_control_flow)
    check("multi-order-input-independent", multi_reversed.serialize() == multi.serialize())
    check(
        "classification-canonical-order",
        [c.address for c in classify_indirect_control_flow(f_both()).classifications()] == [0x1000, 0x1002],
    )
    check("status-counts", build(call_units, [ev("fn_7000", "blk_7003", 0x7003, CALL, RESOLVED, EXACT_ONE, targets=(0x8000,))]).status_counts()["RESOLVED"] == 1)

    # O. arbitrary-width addresses ------------------------------------------
    base = 0x1_0000_0000
    wide = build(f_wide(), [ev("fn_%x" % base, "blk_%x" % (base + 4), base + 4, CALL, RESOLVED, EXACT_ONE, targets=(base + 0x10,))])
    wide_cls = wide.classification_for("fn_%x" % base, "blk_%x" % (base + 4), base + 4, CALL)
    check("wide-resolved-target", wide_cls.targets == (base + 0x10,) and wide_cls.target_functions == ("fn_%x" % (base + 0x10),))
    check("wide-roundtrip", IndirectControlFlowSet.deserialize(wide.serialize()).serialize() == wide.serialize())
    wide_doc = wide.to_document()
    check("wide-value-serialized", str(base + 0x10) in json.dumps(wide_doc))

    very_base = 0x1_0000_0000_0000_0000
    very_unresolved = classify_indirect_control_flow(f_very_wide())
    very_cls = very_unresolved.classification_for("fn_%x" % very_base, "blk_%x" % very_base, very_base, JUMP)
    check("very-wide-unresolved", very_cls.status is UNRESOLVED_JUMP)
    check("very-wide-roundtrip", IndirectControlFlowSet.deserialize(very_unresolved.serialize()).serialize() == very_unresolved.serialize())
    very_resolved = build(f_very_wide(), [ev("fn_%x" % very_base, "blk_%x" % very_base, very_base, JUMP, RESOLVED, EXACT_ONE, targets=(very_base + 0x10,))])
    check("very-wide-resolved-target", very_resolved.classification_for("fn_%x" % very_base, "blk_%x" % very_base, very_base, JUMP).targets == (very_base + 0x10,))

    zero_units = f_zero()
    zero_unresolved = classify_indirect_control_flow(zero_units)
    zero_cls = zero_unresolved.classification_for("fn_0", "blk_0", 0, JUMP)
    check("zero-address-unresolved", zero_cls.address == 0 and zero_cls.status is UNRESOLVED_JUMP)
    zero_resolved = build(zero_units, [ev("fn_0", "blk_0", 0, JUMP, RESOLVED, EXACT_ONE, targets=(0x10,))])
    check("zero-address-resolved", zero_resolved.classification_for("fn_0", "blk_0", 0, JUMP).targets == (0x10,))
    check("zero-address-roundtrip", IndirectControlFlowSet.deserialize(zero_resolved.serialize()).serialize() == zero_resolved.serialize())

    # P. unowned residual preservation --------------------------------------
    unowned = classify_indirect_control_flow(f_unowned())
    check("unowned-preserved", len(unowned.unowned_control_flow) == 1)
    check("unowned-classified-units", unowned.unit_for("fn_1000").site_count() == 0)
    check("unowned-roundtrip", IndirectControlFlowSet.deserialize(unowned.serialize()).serialize() == unowned.serialize())

    # Q. NES6502-derived classification -------------------------------------
    nes = f_nes()
    nes_unresolved = classify_indirect_control_flow(nes)
    nes_cls = nes_unresolved.classification_for("fn_8000", "blk_8000", 0x8000, JUMP)
    check("nes-indirect-jump-unresolved", nes_cls.status is UNRESOLVED_JUMP)
    check("nes-adapter-indirect-not-a-target", nes_cls.targets == ())
    nes_resolved = build(nes, [ev("fn_8000", "blk_8000", 0x8000, JUMP, RESOLVED, EXACT_ONE, targets=(0x9000,))])
    check("nes-resolved-target", nes_resolved.classification_for("fn_8000", "blk_8000", 0x8000, JUMP).targets == (0x9000,))

    # R. no IR lowering / no host emission ----------------------------------
    module_source = Path(indirect_control_flow.__file__).read_text(encoding="utf-8")
    for forbidden in ("openrecomp.executor", "openrecomp.runtime", "openrecomp.module", "validate_ir", "make_ir", "openrecomp.ir", "codegen", "emit_host"):
        check(f"no-host-or-ir-import:{forbidden}", forbidden not in module_source)
    public = [name for name in dir(indirect_control_flow) if not name.startswith("_")]
    suspicious = [name for name in public if any(token in name for token in ("lower", "Lower", "emit", "Emit"))]
    check("no-lowering-api", not suspicious)
    document_text = a.serialize().decode("utf-8")
    check("no-ir-or-host-keys", "ir_version" not in document_text and "emit" not in document_text and "lower" not in document_text)
    check("classification-keeps-structural-provenance", isinstance(call_cls.unresolved_site, UnresolvedSite))
    check("classification-kind-from-instruction-flow", call_cls.kind is CALL and jump_cls.kind is JUMP)

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    if args.json:
        record = {
            "stage": "P2-06",
            "marker": f"OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "results": sorted(RESULTS, key=lambda item: item["check"]),
            "sample_fingerprints": {
                "call_unresolved": call_set.fingerprint(),
                "call_resolved": resolved.fingerprint(),
                "bounded": bounded.fingerprint(),
                "external": external.fingerprint(),
                "return_like": ret.fingerprint(),
                "multi": multi.fingerprint(),
                "nes6502": nes_unresolved.fingerprint(),
                "unowned": unowned.fingerprint(),
            },
        }
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_INDIRECT_CONTROL_FLOW_V1_JSON={out.name}")

    print(f"OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests={tests}")
    return 0


def expect_unit_error(units, classification_set):
    try:
        IndirectControlFlowUnit("tu_fn_7000", "fn_other", 0x7000, classification_set.classifications())
    except IndirectControlFlowError:
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
