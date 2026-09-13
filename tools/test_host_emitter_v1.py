#!/usr/bin/env python3
"""Fail-closed tests for the OpenRecomp deterministic host emitter V1 (P2-07).

Proves `openrecomp/host_emitter.py` over the frozen P2-05 translation units and
P2-06 indirect-control-flow classifications: deterministic portable-C generation,
canonical ordering, stable identifiers/declarations, bounded explicit guest
semantics (masked integer operations with guest-width wraparound), direct control
flow emission, fail-closed handling of unsupported semantics and unresolved or
bounded indirect sites, and the absence of any runtime ABI (P2-08), IR lowering,
host execution or machine-specific metadata.

The generated source is inspected directly and, when a native compiler is
available, a tiny generated fixture is compiled and executed against its expected
register value. Compiler availability is detected, never assumed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import openrecomp.host_emitter as host_emitter  # noqa: E402
from openrecomp.cfg import EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.host_emitter import (  # noqa: E402
    HostBinop,
    HostCompare,
    HostComparison,
    HostConst,
    HostCopy,
    HostEmitterConfig,
    HostEmitterError,
    HostImmediate,
    HostInstructionSemantics,
    HostNop,
    HostRegister,
    HostSemantics,
    HostUnsupportedPolicy,
    emit_host_translation,
    emit_host_translation_from,
)
from openrecomp.indirect_control_flow import (  # noqa: E402
    IndirectControlFlowBasis,
    IndirectControlFlowEvidence,
    IndirectControlFlowKind,
    IndirectControlFlowStatus,
    classify_indirect_control_flow,
)
from openrecomp.program_model import (  # noqa: E402
    DecodedInstruction,
    EvidenceClass,
    InstructionFlow,
    ProgramSource,
)
from openrecomp.translation_units import TranslationUnitSet, build_translation_units  # noqa: E402

ARCH = "bounded-synthetic-v1"
PROV = EvidenceClass.PROVEN
NORMAL = InstructionFlow.NORMAL
BRANCH = InstructionFlow.BRANCH
JUMP = InstructionFlow.JUMP
CALL = InstructionFlow.CALL
RETURN = InstructionFlow.RETURN
INDIRECT_CALL = InstructionFlow.INDIRECT_CALL
INDIRECT_JUMP = InstructionFlow.INDIRECT_JUMP

CALL_KIND = IndirectControlFlowKind.INDIRECT_CALL
JUMP_KIND = IndirectControlFlowKind.INDIRECT_JUMP
RESOLVED = IndirectControlFlowStatus.RESOLVED
BOUNDED = IndirectControlFlowStatus.BOUNDED_CANDIDATES
EXTERNAL = IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED
RETURN_LIKE = IndirectControlFlowStatus.RETURN_LIKE

EXACT_ONE = IndirectControlFlowBasis.EXACT_CONSTANT_TARGET
EXACT_SET = IndirectControlFlowBasis.EXACT_TARGET_SET
BOUNDED_EV = IndirectControlFlowBasis.BOUNDED_CANDIDATE_EVIDENCE
EXTERNAL_EV = IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE
RETURN_EV = IndirectControlFlowBasis.STRUCTURAL_RETURN_EVIDENCE

RESULTS: list[dict[str, str]] = []


def I(address, op, size=1, flow=NORMAL, target=None, unresolved=False, fields=None, evidence=PROV):
    return DecodedInstruction(
        address=address,
        op=op,
        size_bytes=size,
        flow=flow,
        direct_target=target,
        unresolved=unresolved,
        evidence=evidence,
        metadata={"adapter_fields": dict(fields or {})},
    )


def check(label, condition):
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}")


def expect_fail(label, thunk, error_type=HostEmitterError):
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


def rule(op, flow, *, operations=(), condition=None, indirect_source=None):
    return HostInstructionSemantics(
        ARCH, op, flow, operations=operations, condition=condition, indirect_source=indirect_source
    )


def semantics():
    return HostSemantics(
        [
            rule("nop", NORMAL),
            rule("li", NORMAL, operations=(HostConst(HostRegister("rd"), HostImmediate("imm")),)),
            rule("li_s", NORMAL, operations=(HostConst(HostRegister("rd"), HostImmediate("imm", signed=True)),)),
            rule("mov", NORMAL, operations=(HostCopy(HostRegister("rd"), HostRegister("rs")),)),
            rule("add", NORMAL, operations=(HostBinop(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "add"),)),
            rule("sub", NORMAL, operations=(HostBinop(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "sub"),)),
            rule("and", NORMAL, operations=(HostBinop(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "and"),)),
            rule("or", NORMAL, operations=(HostBinop(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "or"),)),
            rule("xor", NORMAL, operations=(HostBinop(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "xor"),)),
            rule("addi", NORMAL, operations=(HostBinop(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True), "add"),)),
            rule("slt", NORMAL, operations=(HostCompare(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "slt"),)),
            rule("sltu", NORMAL, operations=(HostCompare(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "ult"),)),
            rule("shl", NORMAL, operations=(HostBinop(HostRegister("rd"), HostRegister("rs"), HostImmediate("imm"), "shl"),)),
            rule("sra", NORMAL, operations=(HostBinop(HostRegister("rd"), HostRegister("rs"), HostImmediate("imm"), "ashr"),)),
            rule("beq", BRANCH, condition=HostComparison(HostRegister("rs"), HostRegister("rt"), "eq")),
            rule("bne", BRANCH, condition=HostComparison(HostRegister("rs"), HostRegister("rt"), "ne")),
            rule("j", JUMP),
            rule("call", CALL),
            rule("ret", RETURN),
            rule("callix", INDIRECT_CALL, indirect_source=HostRegister("rs")),
            rule("jmpix", INDIRECT_JUMP, indirect_source=HostRegister("rs")),
        ]
    )


def config(entry="fn_1000", **kwargs):
    return HostEmitterConfig(semantics=semantics(), entry_function=entry, **kwargs)


def source(width=32):
    return ProgramSource(ARCH, adapter="openrecomp.synthetic", address_width_bits=width)


def program(insns, entries, *, region_boundaries=(), width=32):
    cfg = build_cfg(
        insns,
        source=source(width),
        entries=[EntryPoint(address, PROV) for address in entries],
        region_boundaries=region_boundaries,
    )
    return build_translation_units(discover_functions(cfg, program_entries=entries))


def evidence(function_id, block_id, address, kind, status, basis, *, targets=(), mechanism=None, source_label="fixture"):
    return IndirectControlFlowEvidence(
        function_id=function_id,
        block_id=block_id,
        address=address,
        kind=kind,
        status=status,
        basis=basis,
        targets=targets,
        external_mechanism=mechanism,
        source=source_label,
        evidence=PROV,
    )


def emit(units, records=(), *, cfg=None):
    classification = classify_indirect_control_flow(units, evidence=records)
    return emit_host_translation(units, classification, config=cfg or config())


# --- fixtures --------------------------------------------------------------
def f_arith():
    return program(
        [
            I(0x1000, "li", fields={"rd": 1, "imm": 5}),
            I(0x1001, "li", fields={"rd": 2, "imm": 7}),
            I(0x1002, "add", fields={"rd": 3, "rs": 1, "rt": 2}),
            I(0x1003, "ret", flow=RETURN),
        ],
        [0x1000],
    )


def f_fallthrough():
    return program(
        [
            I(0x1000, "li", fields={"rd": 1, "imm": 1}),
            I(0x1001, "ret", flow=RETURN),
        ],
        [0x1000],
        region_boundaries=[0x1001],
    )


def f_branch():
    return program(
        [
            I(0x1000, "beq", flow=BRANCH, target=0x1010, fields={"rs": 1, "rt": 2}),
            I(0x1001, "li", fields={"rd": 3, "imm": 1}),
            I(0x1002, "ret", flow=RETURN),
            I(0x1010, "li", fields={"rd": 3, "imm": 2}),
            I(0x1011, "ret", flow=RETURN),
        ],
        [0x1000],
    )


def f_jump():
    return program(
        [
            I(0x1000, "j", flow=JUMP, target=0x1010),
            I(0x1010, "ret", flow=RETURN),
        ],
        [0x1000],
    )


def f_call():
    return program(
        [
            I(0x1000, "call", flow=CALL, target=0x2000),
            I(0x1001, "ret", flow=RETURN),
            I(0x2000, "ret", flow=RETURN),
        ],
        [0x1000],
    )


def f_return_like():
    return program([I(0x1000, "jmpix", flow=INDIRECT_JUMP, unresolved=True, fields={"rs": 1})], [0x1000])


def f_unresolved_jump():
    return program([I(0x1000, "jmpix", flow=INDIRECT_JUMP, unresolved=True, fields={"rs": 1})], [0x1000])


def f_unresolved_call():
    return program(
        [
            I(0x1000, "callix", flow=INDIRECT_CALL, unresolved=True, fields={"rs": 1}),
            I(0x1001, "ret", flow=RETURN),
        ],
        [0x1000],
    )


def f_bounded():
    return program([I(0x1000, "jmpix", flow=INDIRECT_JUMP, unresolved=True, fields={"rs": 1})], [0x1000])


def f_external():
    return program([I(0x1000, "jmpix", flow=INDIRECT_JUMP, unresolved=True, fields={"rs": 1})], [0x1000])


def f_resolved_jump_single():
    return program(
        [
            I(0x1000, "beq", flow=BRANCH, target=0x1010, fields={"rs": 1, "rt": 2}),
            I(0x1001, "jmpix", flow=INDIRECT_JUMP, unresolved=True, fields={"rs": 2}),
            I(0x1010, "ret", flow=RETURN),
        ],
        [0x1000],
    )


def f_resolved_jump_set():
    return program(
        [
            I(0x1000, "beq", flow=BRANCH, target=0x1010, fields={"rs": 1, "rt": 2}),
            I(0x1001, "jmpix", flow=INDIRECT_JUMP, unresolved=True, fields={"rs": 2}),
            I(0x1010, "j", flow=JUMP, target=0x1020),
            I(0x1020, "ret", flow=RETURN),
        ],
        [0x1000],
    )


def f_resolved_call():
    return program(
        [
            I(0x1000, "callix", flow=INDIRECT_CALL, unresolved=True, fields={"rs": 1}),
            I(0x1001, "ret", flow=RETURN),
            I(0x2000, "ret", flow=RETURN),
        ],
        [0x1000, 0x2000],
    )


def f_resolved_call_set():
    return program(
        [
            I(0x1000, "callix", flow=INDIRECT_CALL, unresolved=True, fields={"rs": 1}),
            I(0x1001, "ret", flow=RETURN),
            I(0x2000, "ret", flow=RETURN),
            I(0x3000, "ret", flow=RETURN),
        ],
        [0x1000, 0x2000, 0x3000],
    )


def f_external_direct_call():
    return program(
        [
            I(0x1000, "call", flow=CALL, target=0x9000),
            I(0x1001, "ret", flow=RETURN),
        ],
        [0x1000],
    )


def f_unsupported_op():
    return program(
        [
            I(0x1000, "mystery"),
            I(0x1001, "ret", flow=RETURN),
        ],
        [0x1000],
    )


def f_empty():
    return program([I(0x1000, "ret", flow=RETURN)], [0x1000])


def f_multi():
    return program(
        [
            I(0x1000, "li", fields={"rd": 1, "imm": 1}),
            I(0x1001, "callix", flow=INDIRECT_CALL, unresolved=True, fields={"rs": 1}),
            I(0x1002, "ret", flow=RETURN),
            I(0x2000, "jmpix", flow=INDIRECT_JUMP, unresolved=True, fields={"rs": 2}),
        ],
        [0x1000, 0x2000],
    )


# --- optional compiler ------------------------------------------------------
def find_compiler():
    for name in ("clang", "gcc", "cc"):
        path = shutil.which(name)
        if path:
            return path
    return None


def compile_and_run(source_text, expected):
    compiler = find_compiler()
    if compiler is None:
        return None
    with tempfile.TemporaryDirectory(prefix="openrecomp-p207-") as work:
        c_path = Path(work) / "generated.c"
        exe = Path(work) / ("generated.exe" if os.name == "nt" else "generated")
        c_path.write_text(
            source_text
            + '\n#include <stdio.h>\nint main(void){ openrecomp_run(); printf("%llu %d\\n",'
            + " (unsigned long long)openrecomp_register_value(2), openrecomp_failed()); return 0; }\n",
            encoding="utf-8",
        )
        built = subprocess.run([compiler, str(c_path), "-o", str(exe)], capture_output=True, text=True)
        if built.returncode != 0:
            return {"status": "compile-failed", "detail": (built.stderr or "").strip()[-400:]}
        ran = subprocess.run([str(exe)], capture_output=True, text=True)
        if ran.returncode != 0:
            return {"status": "run-failed", "detail": (ran.stderr or "").strip()[-400:]}
        observed = (ran.stdout or "").strip()
        return {"status": "ok", "observed": observed, "expected": expected, "match": observed == expected}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # A. deterministic generation & stable identifiers ----------------------
    units = f_arith()
    first = emit(units)
    second = emit(f_arith())
    check("deterministic-source", first.source_text == second.source_text)
    check("deterministic-fingerprint", first.fingerprint() == second.fingerprint())
    check("fingerprint-matches-text", hashlib.sha256(first.source_text.encode("utf-8")).hexdigest() == first.fingerprint())
    check("canonical-function-name", first.translations[0].function_name == "fn_fn_1000")
    check("canonical-block-label", first.translations[0].block_labels == ("bb_blk_1000",))
    check("entry-function-name", first.entry_function_name == "fn_fn_1000")
    check("stable-declaration", "static void fn_fn_1000(void);" in first.source_text)
    check("single-translation", len(first.translations) == 1)
    check("register-names", first.register_names == ("r1", "r2", "r3"))
    check("unit-id-preserved", first.translations[0].unit_id == units.unit_for("fn_1000").unit_id)

    # B. instruction semantics -----------------------------------------------
    check("const-emission", "g_r[0] = (UINT64_C(5)) & or_mask(32u);" in first.source_text)
    check("binop-emission", "g_r[2] = ((g_r[0]) + (g_r[1])) & or_mask(32u);" in first.source_text)
    check("explicit-width", "or_mask(32u)" in first.source_text)
    check("operations-counted", first.translations[0].operations_emitted == 3)

    copy_src = emit(program([I(0x1000, "mov", fields={"rd": 1, "rs": 2}), I(0x1001, "ret", flow=RETURN)], [0x1000])).source_text
    check("copy-emission", "g_r[0] = (g_r[1]) & or_mask(32u);" in copy_src)

    signed_src = emit(program([I(0x1000, "li_s", fields={"rd": 1, "imm": -1}), I(0x1001, "ret", flow=RETURN)], [0x1000])).source_text
    check("signed-immediate-masked", "UINT64_C(4294967295)" in signed_src)

    compare_src = emit(
        program([I(0x1000, "slt", fields={"rd": 1, "rs": 2, "rt": 3}), I(0x1001, "ret", flow=RETURN)], [0x1000])
    ).source_text
    check("signed-compare-uses-helper", "or_signed((g_r[1]), 32u) < or_signed((g_r[2]), 32u)" in compare_src)
    unsigned_compare = emit(
        program([I(0x1000, "sltu", fields={"rd": 1, "rs": 2, "rt": 3}), I(0x1001, "ret", flow=RETURN)], [0x1000])
    ).source_text
    check("unsigned-compare-direct", "g_r[0] = (((g_r[1]) < (g_r[2]))) ? UINT64_C(1) : UINT64_C(0);" in unsigned_compare)

    shift_src = emit(
        program([I(0x1000, "shl", fields={"rd": 1, "rs": 2, "imm": 1}), I(0x1001, "ret", flow=RETURN)], [0x1000])
    ).source_text
    check("shift-guard", 'or_fail("shift count is not normalized")' in shift_src)
    sra_src = emit(
        program([I(0x1000, "sra", fields={"rd": 1, "rs": 2, "imm": 1}), I(0x1001, "ret", flow=RETURN)], [0x1000])
    ).source_text
    check("arithmetic-shift-helper", "or_ashr((g_r" in sra_src)

    # C. control flow --------------------------------------------------------
    fall = emit(f_fallthrough())
    check("fallthrough-emission", "goto bb_blk_1001;" in fall.source_text)
    branch = emit(f_branch())
    check("branch-emission", "if (((g_r" in branch.source_text and ") == (g_r" in branch.source_text and "goto bb_blk_1010; else goto bb_blk_1001;" in branch.source_text)
    jump = emit(f_jump())
    check("jump-emission", "goto bb_blk_1010;" in jump.source_text)
    call = emit(f_call())
    check("call-emission", "fn_fn_2000();" in call.source_text and "goto bb_blk_1001;" in call.source_text)
    check("call-declaration", "static void fn_fn_2000(void);" in call.source_text)
    check("call-reference", call.translation_for("fn_1000").reference_functions == ("fn_fn_2000",))
    check("return-emission", "return;" in first.source_text)
    instruction_positions = [
        first.source_text.index("UINT64_C(5)"),
        first.source_text.index("UINT64_C(7)"),
        first.source_text.index(") + (g_r[1])"),
    ]
    check("canonical-instruction-order", instruction_positions == sorted(instruction_positions))
    block_positions = [
        branch.source_text.index("bb_blk_1000:"),
        branch.source_text.index("bb_blk_1001:"),
        branch.source_text.index("bb_blk_1010:"),
    ]
    check("canonical-block-order", block_positions == sorted(block_positions))

    # D. return-like and indirect handling -----------------------------------
    return_like = emit(
        f_return_like(),
        [
            evidence(
                "fn_1000", "blk_1000", 0x1000, JUMP_KIND, RETURN_LIKE, RETURN_EV
            )
        ],
    )
    check("return-like-return", "return;" in return_like.source_text)
    check("return-like-status", return_like.translation_for("fn_1000").indirect_statuses == ("RETURN_LIKE",))
    check("return-like-no-goto", "goto" not in return_like.source_text.split("static void fn_fn_1000", 1)[1].split("}", 1)[0])

    unresolved_jump = emit(f_unresolved_jump())
    check("unresolved-jump-boundary", 'or_fail("unresolved indirect jump");' in unresolved_jump.source_text)
    check("unresolved-jump-status", "UNRESOLVED_INDIRECT_JUMP" in unresolved_jump.translation_for("fn_1000").indirect_statuses)
    unresolved_call = emit(f_unresolved_call())
    check("unresolved-call-boundary", 'or_fail("unresolved indirect call");' in unresolved_call.source_text)

    bounded = emit(
        f_bounded(),
        [
            evidence(
                "fn_1000", "blk_1000", 0x1000, JUMP_KIND, BOUNDED, BOUNDED_EV, targets=(0x1010, 0x1020)
            )
        ],
    )
    check("bounded-boundary", 'or_fail("bounded candidate set is not a resolved target");' in bounded.source_text)
    check("bounded-not-promoted-no-case", "case UINT64_C(4112)" not in bounded.source_text)
    check("bounded-not-promoted-no-goto", "goto bb_blk_1010" not in bounded.source_text)
    check("bounded-status", "BOUNDED_CANDIDATES" in bounded.translation_for("fn_1000").indirect_statuses)

    external = emit(
        f_external(),
        [
            evidence(
                "fn_1000", "blk_1000", 0x1000, JUMP_KIND, EXTERNAL, EXTERNAL_EV, mechanism="syscall"
            )
        ],
    )
    check("external-boundary", 'or_fail("external or runtime-mediated indirect transfer is unsupported");' in external.source_text)
    check("external-no-target", "goto bb_" not in external.source_text.split("static void fn_fn_1000", 1)[1].split("}", 1)[0])
    check("external-status", "EXTERNAL_OR_RUNTIME_MEDIATED" in external.translation_for("fn_1000").indirect_statuses)

    # E. resolved indirect sites --------------------------------------------
    single = emit(
        f_resolved_jump_single(),
        [evidence("fn_1000", "blk_1001", 0x1001, JUMP_KIND, RESOLVED, EXACT_ONE, targets=(0x1010,))],
    )
    check("resolved-jump-single", "goto bb_blk_1010;" in single.source_text)
    check("resolved-jump-single-no-switch", "switch" not in single.source_text)
    check("resolved-jump-status", "RESOLVED" in single.translation_for("fn_1000").indirect_statuses)

    jump_set = emit(
        f_resolved_jump_set(),
        [evidence("fn_1000", "blk_1001", 0x1001, JUMP_KIND, RESOLVED, EXACT_SET, targets=(0x1010, 0x1020))],
    )
    check("resolved-jump-set-case-a", "case UINT64_C(4112): goto bb_blk_1010;" in jump_set.source_text)
    check("resolved-jump-set-case-b", "case UINT64_C(4128): goto bb_blk_1020;" in jump_set.source_text)
    check("resolved-jump-set-default", 'default: or_fail("indirect target outside proven set");' in jump_set.source_text)
    check("resolved-jump-set-switch", f"switch ((uint64_t)(g_r[" in jump_set.source_text)

    resolved_call = emit(
        f_resolved_call(),
        [evidence("fn_1000", "blk_1000", 0x1000, CALL_KIND, RESOLVED, EXACT_ONE, targets=(0x2000,))],
    )
    check("resolved-call-single", "fn_fn_2000();" in resolved_call.source_text and "goto bb_blk_1001;" in resolved_call.source_text)

    resolved_call_set = emit(
        f_resolved_call_set(),
        [evidence("fn_1000", "blk_1000", 0x1000, CALL_KIND, RESOLVED, EXACT_SET, targets=(0x2000, 0x3000))],
    )
    check("resolved-call-set", "fn_fn_2000(); goto bb_blk_1001;" in resolved_call_set.source_text)
    check("resolved-call-set-other", "fn_fn_3000(); goto bb_blk_1001;" in resolved_call_set.source_text)

    # F. failure modes -------------------------------------------------------
    expect_fail("unsupported-op", lambda: emit(f_unsupported_op()))
    expect_fail("non-unit-set", lambda: emit_host_translation(None, classify_indirect_control_flow(f_arith()), config=config()))
    expect_fail("non-classification", lambda: emit_host_translation(f_arith(), None, config=config()))
    expect_fail(
        "mismatched-classification",
        lambda: emit_host_translation(f_arith(), classify_indirect_control_flow(f_call()), config=config()),
    )
    expect_fail("unknown-entry", lambda: emit(f_arith(), cfg=config("fn_9999")))
    expect_fail(
        "external-direct-call",
        lambda: emit(f_external_direct_call()),
    )
    expect_fail(
        "resolved-jump-target-not-block",
        lambda: emit(
            f_resolved_jump_single(),
            [evidence("fn_1000", "blk_1001", 0x1001, JUMP_KIND, RESOLVED, EXACT_ONE, targets=(0x9999,))],
        ),
    )
    expect_fail(
        "resolved-call-target-not-function",
        lambda: emit(
            f_resolved_call(),
            [evidence("fn_1000", "blk_1000", 0x1000, CALL_KIND, RESOLVED, EXACT_ONE, targets=(0x9999,))],
        ),
    )
    def reject_unresolved():
        units_ = f_unresolved_jump()
        classification = classify_indirect_control_flow(units_)
        return emit_host_translation(
            units_, classification, config=config(unsupported_indirect_policy=HostUnsupportedPolicy.REJECT)
        )

    expect_fail("reject-policy", reject_unresolved)
    expect_fail(
        "reject-policy-bounded",
        lambda: emit_host_translation(
            f_bounded(),
            classify_indirect_control_flow(
                f_bounded(),
                evidence=[evidence("fn_1000", "blk_1000", 0x1000, JUMP_KIND, BOUNDED, BOUNDED_EV, targets=(0x1010,))],
            ),
            config=config(unsupported_indirect_policy=HostUnsupportedPolicy.REJECT),
        ),
    )

    # G. no machine-specific metadata ---------------------------------------
    forbidden = ("D:\\", "C:\\", "/home/", "\\Users\\", "Temp", "tmp")
    check("no-source-path", not any(token in first.source_text for token in forbidden))
    check("no-timestamp", not any(part in first.source_text for part in ("2026-", "2025-", "2024-")))
    check("no-python-object-id", "object at 0x" not in first.source_text and "<class" not in first.source_text)
    check("no-filename", ".py" not in first.source_text)
    check("input-fingerprint-stable", f"/* input_sha256: {hashlib.sha256((units.serialize() + classify_indirect_control_flow(units).serialize())).hexdigest()} */" in first.source_text)

    # H. ordering variations -------------------------------------------------
    reversed_units = TranslationUnitSet(
        units.source,
        list(reversed(units.units)),
        entry_unit=units.entry_unit,
        shared_blocks=units.shared_blocks,
        suppressed_entries=units.suppressed_entries,
        unowned_blocks=units.unowned_blocks,
        external_direct_call_targets=units.external_direct_call_targets,
        unowned_control_flow=units.unowned_control_flow,
    )
    reversed_set = emit_host_translation(reversed_units, classify_indirect_control_flow(units), config=config())
    check("ordering-input-independent", reversed_set.source_text == first.source_text)
    expect_fail(
        "low-level-entry",
        lambda: emit_host_translation_from((), classify_indirect_control_flow(units), source=units.source, config=config()),
    )
    low_level = emit_host_translation_from(
        units.units, classify_indirect_control_flow(units), source=units.source, config=config()
    )
    check("low-level-entry-point", low_level.source_text == first.source_text)
    multi = emit(f_multi())
    check("multi-translation-order", [t.function_id for t in multi.translations] == ["fn_1000", "fn_2000"])
    check("multi-declarations-order", multi.source_text.index("fn_fn_1000(void);") < multi.source_text.index("fn_fn_2000(void);"))

    # I. empty / bounded / width --------------------------------------------
    empty = emit(f_empty())
    check("empty-function-valid", "static void fn_fn_1000(void) {" in empty.source_text and "return;" in empty.source_text)
    check("empty-no-registers", empty.register_names == ())

    for width, expected_mask in ((8, "or_mask(8u)"), (16, "or_mask(16u)"), (64, "or_mask(64u)")):
        out = emit(
            program([I(0x1000, "li", fields={"rd": 1, "imm": 200}), I(0x1001, "ret", flow=RETURN)], [0x1000]),
            cfg=config(word_bits=width),
        )
        check(f"word-bits-{width}", expected_mask in out.source_text)
    width8 = emit(
        program([I(0x1000, "li", fields={"rd": 1, "imm": 0x1FF}), I(0x1001, "ret", flow=RETURN)], [0x1000]),
        cfg=config(word_bits=8),
    )
    check("immediate-masked-to-width", "UINT64_C(255)" in width8.source_text)

    # J. no P2-08 runtime / no IR lowering ----------------------------------
    check("no-host-call", "host_call" not in first.source_text and "host_callback" not in first.source_text)
    check("no-memory", "g_memory" not in first.source_text and "memcpy" not in first.source_text and "malloc" not in first.source_text)
    check("no-file-io", "#include <stdio.h>" not in first.source_text and "fopen" not in first.source_text)
    check("only-portable-includes", set(re.findall(r"#include <([^>]+)>", first.source_text)) == {"stdint.h", "stddef.h"})
    module_source = Path(host_emitter.__file__).read_text(encoding="utf-8")
    for token in ("openrecomp.executor", "openrecomp.runtime", "openrecomp.module", "validate_ir", "make_ir"):
        check(f"no-ir-import:{token}", token not in module_source)
    public = [name for name in dir(host_emitter) if not name.startswith("_")]
    check("no-ir-lowering-api", not any(tok in name for name in public for tok in ("lower", "Lower")))

    # K. structural preservation --------------------------------------------
    before = units.fingerprint()
    emit(units)
    check("p2-05-unmutated", units.fingerprint() == before)

    # L. model validation ----------------------------------------------------
    expect_fail("duplicate-semantics", lambda: HostSemantics([rule("li", NORMAL), rule("li", NORMAL)]))
    expect_fail("branch-without-condition", lambda: rule("beq", BRANCH))
    expect_fail("normal-with-condition", lambda: rule("li", NORMAL, condition=HostComparison(HostRegister("rs"), HostRegister("rt"), "eq")))
    expect_fail("indirect-without-source", lambda: rule("jmpix", INDIRECT_JUMP))
    expect_fail("jump-with-operations", lambda: rule("j", JUMP, operations=(HostNop(),)))
    expect_fail("bad-binop-kind", lambda: HostBinop(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "power"))
    expect_fail("bad-predicate", lambda: HostCompare(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "equiv"))
    expect_fail("bad-word-bits", lambda: config(word_bits=24))
    expect_fail("duplicate-register-names", lambda: config(register_names=("r1", "r1")))
    expect_fail("missing-adapter-field", lambda: emit(program([I(0x1000, "li", fields={"rd": 1}), I(0x1001, "ret", flow=RETURN)], [0x1000])))
    expect_fail("declared-register-missing", lambda: emit(f_arith(), cfg=config(register_names=("r1",))))

    # M. declarations/helpers stability -------------------------------------
    check("helper-mask", "static uint64_t or_mask(unsigned bits)" in first.source_text)
    check("helper-fail", "static void or_fail(const char *message)" in first.source_text)
    check("run-entry", "void openrecomp_run(void)" in first.source_text)
    check("register-accessors", "openrecomp_register_value" in first.source_text)
    check("serialize-stable", first.serialize() == emit(f_arith()).serialize())

    # N. optional native compile + execute ----------------------------------
    compiler = find_compiler()
    compile_result = None
    if compiler is None:
        print("SKIP: native-host-compile (no clang/gcc/cc on PATH)")
    else:
        sample = emit(
            program(
                [
                    I(0x1000, "li", fields={"rd": 1, "imm": 200}),
                    I(0x1001, "li", fields={"rd": 2, "imm": 100}),
                    I(0x1002, "add", fields={"rd": 3, "rs": 1, "rt": 2}),
                    I(0x1003, "ret", flow=RETURN),
                ],
                [0x1000],
            ),
            cfg=config(word_bits=8),
        )
        compile_result = compile_and_run(sample.source_text, "44 0")
        if compile_result is None:
            print("SKIP: native-host-compile (detected compiler not runnable)")
        elif compile_result["status"] == "ok" and compile_result.get("match"):
            check("compiled-fixture-runs", True)
        elif compile_result["status"] == "ok":
            check("compiled-fixture-runs", False)
        else:
            raise AssertionError(f"native compile/run failed: {compile_result}")

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    if args.json:
        record = {
            "stage": "P2-07",
            "marker": f"OPENRECOMP_HOST_EMITTER_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "results": sorted(RESULTS, key=lambda item: item["check"]),
            "native_compiler": compiler,
            "native_compile_result": compile_result,
            "sample_fingerprints": {
                "arith": first.fingerprint(),
                "branch": emit(f_branch()).fingerprint(),
                "call": emit(f_call()).fingerprint(),
                "return_like": return_like.fingerprint(),
                "bounded": bounded.fingerprint(),
                "external": external.fingerprint(),
                "resolved_jump_set": jump_set.fingerprint(),
                "resolved_call_set": resolved_call_set.fingerprint(),
                "multi": multi.fingerprint(),
            },
        }
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_HOST_EMITTER_V1_JSON={out.name}")

    print(f"OPENRECOMP_HOST_EMITTER_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
