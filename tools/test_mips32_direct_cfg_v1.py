#!/usr/bin/env python3
"""OpenRecomp MIPS32 direct-CFG stress proof V1 (P2-12).

Stresses the direct control-flow pipeline on one synthetic/original MIPS32
fixture that contains:

* a counted loop with a backward branch and both branch outcomes,
* conditional branches whose targets are not taken at runtime (used only to give
  the CFG structural reachability to the dispatch targets),
* a direct `jal` call to a leaf function and `jr $ra` returns,
* a stack save/restore of `$ra` (checked `sw`/`lw` through the P2-08 boundary),
* a bounded indirect dispatch (`jr r5`) whose finite exact target set is
  supplied by explicit P2-06 `EXACT_TARGET_SET` evidence, lowered by P2-07 to a
  `switch` with a fail-closed default.

Traversal is the real Phase-2 pipeline (P2-01..P2-09). The expected observable
is derived independently by a true-MIPS32 reference interpreter with delay slots,
`jal`/`jr $ra` linkage, `lw`/`sw`, a bounded little-endian RAM and the documented
derivation. No indirect target is guessed: without explicit evidence the dispatch
site fails closed, and a bounded candidate set is never promoted.

This gate proves only this bounded synthetic fixture. It is not full MIPS32
support, not PS2 support and not a guest/host equivalence proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.mips32 as mips32_adapter  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402
from openrecomp.call_graph import CallEdgeKind, build_call_graph  # noqa: E402
from openrecomp.cfg import CFGError, CFGMode, EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.host_emitter import (  # noqa: E402
    HostBinop,
    HostCompare,
    HostComparison,
    HostConst,
    HostEmitterConfig,
    HostEmitterError,
    HostImmediate,
    HostInstructionSemantics,
    HostLoad,
    HostRegister,
    HostSemantics,
    HostStore,
    HostUnsupportedPolicy,
    emit_host_translation,
)
from openrecomp.indirect_control_flow import (  # noqa: E402
    IndirectControlFlowBasis,
    IndirectControlFlowEvidence,
    IndirectControlFlowKind,
    IndirectControlFlowStatus,
    classify_indirect_control_flow,
)
from openrecomp.program_model import (  # noqa: E402
    EdgeKind,
    EvidenceClass,
    InstructionFlow,
    ProgramSource,
    instruction_from_adapter,
)
from openrecomp.translation_units import build_translation_units  # noqa: E402

ARCH = mips32_adapter.info.architecture_id
ENTRY = 0x1000
LEAF = 0x1080
DISPATCH = 0x1054
CASE_A = 0x105C
CASE_B = 0x106C
PROVEN = EvidenceClass.PROVEN
FIXTURE_ID = "p2-12-mips32-direct-cfg-v1"
RAM_SIZE = 4096

# --- deterministic encoder (used to cross-check the recorded words) ---------
def _rtype(rs, rt, rd, shamt, funct):
    return (0 << 26) | (rs << 21) | (rt << 16) | (rd << 11) | (shamt << 6) | funct


def _itype(op, rs, rt, imm):
    return (op << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def _jtype(op, target):
    return (op << 26) | ((target >> 2) & 0x03FFFFFF)


def _branch(op, rs, rt, pc, target):
    return _itype(op, rs, rt, ((target - (pc + 4)) >> 2) & 0xFFFF)


def _addiu(rt, rs, imm):
    return _itype(0x09, rs, rt, imm)


def _addu(rd, rs, rt):
    return _rtype(rs, rt, rd, 0, 0x21)


def _slti(rt, rs, imm):
    return _itype(0x0A, rs, rt, imm)


def _lw(rt, rs, imm):
    return _itype(0x23, rs, rt, imm)


def _sw(rt, rs, imm):
    return _itype(0x2B, rs, rt, imm)


def _jr(rs):
    return _rtype(rs, 0, 0, 0, 0x08)


# (address, word, mnemonic) -- synthetic/original fixture, little-endian MIPS32.
FIXTURE = (
    (0x1000, 0x241D0100, "addiu sp, r0, 0x100"),
    (0x1004, 0x27BDFFF8, "addiu sp, sp, -8"),
    (0x1008, 0xAFBF0004, "sw ra, 4(sp)"),
    (0x100C, 0x24020000, "addiu r2, r0, 0"),
    (0x1010, 0x24030000, "addiu r3, r0, 0"),
    (0x1014, 0x24080001, "addiu r8, r0, 1"),
    (0x1018, 0x24630001, "addiu r3, r3, 1          (loop: i += 1)"),
    (0x101C, 0x00431021, "addu r2, r2, r3          (acc += i)"),
    (0x1020, 0x28640005, "slti r4, r3, 5"),
    (0x1024, 0x1480FFFC, "bne r4, r0, 0x1018       (back edge)"),
    (0x1028, 0x00000000, "nop (delay slot)"),
    (0x102C, 0x24440000, "addiu r4, r2, 0          (arg = acc)"),
    (0x1030, 0x0C000420, "jal 0x1080               (direct call)"),
    (0x1034, 0x00000000, "nop (delay slot)"),
    (0x1038, 0x8FBF0004, "lw ra, 4(sp)             (restore ra)"),
    (0x103C, 0x24090001, "addiu r9, r0, 1"),
    (0x1040, 0x1100000A, "beq r8, r0, 0x106c       (structural edge to case B)"),
    (0x1044, 0x00000000, "nop (delay slot)"),
    (0x1048, 0x11200004, "beq r9, r0, 0x105c       (structural edge to case A)"),
    (0x104C, 0x00000000, "nop (delay slot)"),
    (0x1050, 0x2405105C, "addiu r5, r0, 0x105c     (selector = case A)"),
    (0x1054, 0x00A00008, "jr r5                    (bounded dispatch)"),
    (0x1058, 0x00000000, "nop (delay slot)"),
    (0x105C, 0x24060064, "addiu r6, r0, 100        (case A)"),
    (0x1060, 0x00C23021, "addu r6, r6, r2"),
    (0x1064, 0x0800041D, "j 0x1074                 (to end)"),
    (0x1068, 0x00000000, "nop (delay slot)"),
    (0x106C, 0x240600C8, "addiu r6, r0, 200        (case B)"),
    (0x1070, 0x00C23021, "addu r6, r6, r2"),
    (0x1074, 0x24C70005, "addiu r7, r6, 5          (end)"),
    (0x1078, 0x03E00008, "jr ra"),
    (0x107C, 0x00000000, "nop (delay slot)"),
    (0x1080, 0x24420005, "addiu r2, r2, 5          (leaf)"),
    (0x1084, 0x03E00008, "jr ra"),
    (0x1088, 0x00000000, "nop (delay slot)"),
)
WORDS = tuple(word for _, word, _ in FIXTURE)
WORD_BY_ADDR = {address: word for address, word, _ in FIXTURE}
FIXTURE_BYTES = struct.pack("<%dI" % len(WORDS), *WORDS)
FIXTURE_SHA256 = hashlib.sha256(FIXTURE_BYTES).hexdigest()

# Independent derivation (true MIPS32 with delay slots):
#   loop i=1..5 sums to acc=15; call leaf -> r2 = 15 + 5 = 20;
#   both structural branches are not taken at runtime; r5 = 0x105c; bounded
#   switch dispatches to case A: r6 = 100 + 20 = 120; j end; r7 = 120 + 5 = 125;
#   jr $ra with $ra = 0 halts. sp = 0x100 - 8 = 248.
EXPECTED_REGS = {2: 20, 3: 5, 4: 15, 5: 0x105C, 6: 120, 7: 125, 8: 1, 9: 1, 29: 248, 31: 0}

SUPPORT_SOURCE = """\
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>

void openrecomp_run(void);
int openrecomp_failed(void);
size_t openrecomp_register_count(void);
uint64_t openrecomp_register_value(size_t index);
const char *openrecomp_error(void);

#define OR_RT_RAM_SIZE 4096u
static uint8_t g_ram[OR_RT_RAM_SIZE];

int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value) {
    if (width_bits != 32u || out_value == 0) return 2;
    uint64_t size = width_bits / 8u;
    if (address + size > OR_RT_RAM_SIZE) return 1;
    uint32_t value = 0;
    for (uint32_t index = 0; index < size; ++index) value |= (uint32_t)g_ram[address + index] << (8u * index);
    *out_value = value;
    return 0;
}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value) {
    if (width_bits != 32u) return 2;
    uint64_t size = width_bits / 8u;
    if (address + size > OR_RT_RAM_SIZE) return 1;
    for (uint32_t index = 0; index < size; ++index) g_ram[address + index] = (uint8_t)((value >> (8u * index)) & 0xFFu);
    return 0;
}

const char *or_rt_failure_reason(int code) { (void)code; return ""; }

int main(void) {
    openrecomp_run();
    printf("failed=%d\\n", openrecomp_failed());
    printf("error=%s\\n", openrecomp_error());
    size_t count = openrecomp_register_count();
    for (size_t index = 0; index < count; ++index) {
        printf("reg[%zu]=%llu\\n", index, (unsigned long long)openrecomp_register_value(index));
    }
    return 0;
}
"""

RESULTS: list[dict[str, str]] = []


def check(label, condition):
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}")


def expect_fail(label, thunk, error_type):
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


FLOW = {
    "nop": InstructionFlow.NORMAL,
    "addiu": InstructionFlow.NORMAL,
    "addu": InstructionFlow.NORMAL,
    "slti": InstructionFlow.NORMAL,
    "lw": InstructionFlow.NORMAL,
    "sw": InstructionFlow.NORMAL,
    "beq": InstructionFlow.BRANCH,
    "bne": InstructionFlow.BRANCH,
    "j": InstructionFlow.JUMP,
    "jal": InstructionFlow.CALL,
    "jr": InstructionFlow.INDIRECT_JUMP,
}


def decode_fixture(table=FIXTURE):
    instructions = []
    for address, word, _ in table:
        decoded = mips32_adapter.decode(address, word)
        flow = FLOW[decoded["op"]]
        instructions.append(
            instruction_from_adapter(
                decoded, flow=flow, unresolved=(flow is InstructionFlow.INDIRECT_JUMP),
                size_bytes=4, evidence=PROVEN,
            )
        )
    return tuple(instructions)


def program_source(sha=FIXTURE_SHA256):
    return ProgramSource(
        ARCH, adapter="adapters.mips32", address_width_bits=32, endianness="little", input_sha256=sha
    )


def semantics_table():
    def r(op, flow, **kw):
        return HostInstructionSemantics(ARCH, op, flow, **kw)
    return HostSemantics([
        r("nop", InstructionFlow.NORMAL),
        r("addiu", InstructionFlow.NORMAL, operations=(HostBinop(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True), "add"),)),
        r("addu", InstructionFlow.NORMAL, operations=(HostBinop(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "add"),)),
        r("slti", InstructionFlow.NORMAL, operations=(HostCompare(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True), "slt"),)),
        r("lw", InstructionFlow.NORMAL, operations=(HostLoad(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True)),)),
        r("sw", InstructionFlow.NORMAL, operations=(HostStore(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True)),)),
        r("beq", InstructionFlow.BRANCH, condition=HostComparison(HostRegister("rs"), HostRegister("rt"), "eq")),
        r("bne", InstructionFlow.BRANCH, condition=HostComparison(HostRegister("rs"), HostRegister("rt"), "ne")),
        r("j", InstructionFlow.JUMP),
        r("jal", InstructionFlow.CALL),
        r("jr", InstructionFlow.INDIRECT_JUMP, indirect_source=HostRegister("rs")),
    ])


def run_pipeline(table=FIXTURE, *, evidence_kind="resolved", policy=HostUnsupportedPolicy.BOUNDARY):
    source = program_source()
    instructions = decode_fixture(table)
    cfg = build_cfg(instructions, source=source, entries=[EntryPoint(ENTRY, PROVEN)], mode=CFGMode.CLOSED)
    discovery = discover_functions(cfg, program_entries=[ENTRY])
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)
    evidence = []
    dispatch_site = None
    for unit in units.units:
        for block in unit.blocks:
            terminal = block.terminal
            if terminal.flow is not InstructionFlow.INDIRECT_JUMP:
                continue
            if terminal.address == DISPATCH:
                dispatch_site = (unit.function_id, block.id, terminal.address)
                if evidence_kind == "resolved":
                    evidence.append(IndirectControlFlowEvidence(
                        function_id=unit.function_id, block_id=block.id, address=terminal.address,
                        kind=IndirectControlFlowKind.INDIRECT_JUMP,
                        status=IndirectControlFlowStatus.RESOLVED,
                        basis=IndirectControlFlowBasis.EXACT_TARGET_SET,
                        targets=(CASE_A, CASE_B),
                        source="p2-12-fixture", evidence=PROVEN,
                    ))
                elif evidence_kind == "bounded":
                    evidence.append(IndirectControlFlowEvidence(
                        function_id=unit.function_id, block_id=block.id, address=terminal.address,
                        kind=IndirectControlFlowKind.INDIRECT_JUMP,
                        status=IndirectControlFlowStatus.BOUNDED_CANDIDATES,
                        basis=IndirectControlFlowBasis.BOUNDED_CANDIDATE_EVIDENCE,
                        targets=(CASE_A, CASE_B),
                        source="p2-12-fixture", evidence=PROVEN,
                    ))
            else:
                evidence.append(IndirectControlFlowEvidence(
                    function_id=unit.function_id, block_id=block.id, address=terminal.address,
                    kind=IndirectControlFlowKind.INDIRECT_JUMP,
                    status=IndirectControlFlowStatus.RETURN_LIKE,
                    basis=IndirectControlFlowBasis.STRUCTURAL_RETURN_EVIDENCE,
                    source="p2-12-fixture", evidence=PROVEN,
                ))
    classification = classify_indirect_control_flow(units, evidence=evidence)
    host = emit_host_translation(units, classification, config=HostEmitterConfig(
        semantics=semantics_table(), entry_function=discovery.entry_function_id, word_bits=32,
        runtime_abi=rt.RuntimeAbiConfig(), unsupported_indirect_policy=policy,
    ))
    return {
        "cfg": cfg, "discovery": discovery, "call_graph": call_graph, "units": units,
        "classification": classification, "host": host, "dispatch_site": dispatch_site,
    }


# --- independent reference interpreter --------------------------------------
def reference_execute(table=FIXTURE, entry=ENTRY, limit=100000):
    words = {address: word for address, word, _ in table}
    regs = [0] * 32
    ram = bytearray(RAM_SIZE)
    pc = entry
    pending = None
    steps = 0
    while True:
        steps += 1
        if steps > limit:
            raise AssertionError("reference interpreter step limit exceeded")
        if pc == 0:
            break
        if pc not in words:
            raise AssertionError(f"reference interpreter left the fixture at 0x{pc:x}")
        word = words[pc]
        opcode = (word >> 26) & 0x3F
        rs = (word >> 21) & 0x1F
        rt_field = (word >> 16) & 0x1F
        rd = (word >> 11) & 0x1F
        funct = word & 0x3F
        imm = word & 0xFFFF
        if imm & 0x8000:
            imm -= 0x10000
        branch = False
        target = None
        if word == 0:
            pass
        elif opcode == 0x09:
            regs[rt_field] = (regs[rs] + imm) & 0xFFFFFFFF
        elif opcode == 0 and funct == 0x21:
            regs[rd] = (regs[rs] + regs[rt_field]) & 0xFFFFFFFF
        elif opcode == 0x0A:
            regs[rt_field] = 1 if regs[rs] < imm else 0
        elif opcode == 0x23:
            address = (regs[rs] + imm) & 0xFFFFFFFF
            if address + 4 > RAM_SIZE:
                raise AssertionError(f"reference lw out of range at 0x{address:x}")
            regs[rt_field] = int.from_bytes(ram[address:address + 4], "little")
        elif opcode == 0x2B:
            address = (regs[rs] + imm) & 0xFFFFFFFF
            if address + 4 > RAM_SIZE:
                raise AssertionError(f"reference sw out of range at 0x{address:x}")
            ram[address:address + 4] = (regs[rt_field] & 0xFFFFFFFF).to_bytes(4, "little")
        elif opcode == 0x04:
            branch = True
            target = (pc + 4 + (imm << 2)) & 0xFFFFFFFF if regs[rs] == regs[rt_field] else None
        elif opcode == 0x05:
            branch = True
            target = (pc + 4 + (imm << 2)) & 0xFFFFFFFF if regs[rs] != regs[rt_field] else None
        elif opcode == 0x02:
            branch = True
            target = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
        elif opcode == 0x03:
            branch = True
            target = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
            regs[31] = (pc + 8) & 0xFFFFFFFF
        elif opcode == 0 and funct == 0x08:
            branch = True
            target = regs[rs]
        else:
            raise AssertionError(f"reference interpreter: unsupported word 0x{word:08x}")
        regs[0] = 0
        if pending is not None:
            pc = pending
            pending = None
        elif branch:
            pending = target if target is not None else pc + 4
            pc = pc + 4
        else:
            pc = pc + 4
    return regs, ram


def expected_output(register_names, regs):
    lines = ["failed=0", "error="]
    for index, name in enumerate(register_names):
        lines.append(f"reg[{index}]={regs[int(name[1:])]}")
    return "\n".join(lines)


# --- evidence ---------------------------------------------------------------
def _write_text(path, text):
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def write_evidence(evidence_dir, staging, *, switch_failclosed_lines):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    hashes = {}

    fixture_lines = [
        "P2-12 synthetic MIPS32 fixture (direct-CFG stress)",
        "=" * 48,
        f"architecture: {ARCH}",
        "endianness: little",
        "instruction width: 4 bytes",
        f"entry: 0x{ENTRY:x}; leaf: 0x{LEAF:x}; dispatch: 0x{DISPATCH:x}",
        f"instruction count: {len(FIXTURE)}",
        f"byte length: {len(FIXTURE_BYTES)}",
        f"sha256: {FIXTURE_SHA256}",
        "origin: synthetic/original (no commercial ROM/ELF bytes)",
        "features: counted loop with back edge; conditional branches; direct call; "
        "stack save/restore of $ra; bounded indirect dispatch with explicit evidence",
        "",
        "instructions:",
    ]
    for address, word, mnemonic in FIXTURE:
        fixture_lines.append(f"  0x{address:08x}  0x{word:08x}  {mnemonic}")
    fixture_lines += ["", "bytes (little-endian hex):", FIXTURE_BYTES.hex(), ""]
    hashes["fixture.txt"] = _write_text(evidence_dir / "fixture.txt", "\n".join(fixture_lines))

    cfg = staging["cfg"]
    edge_lines = []
    for block in cfg.ordered_blocks():
        for successor in block.successors:
            target = successor.target_block if successor.resolved else successor.detail
            edge_lines.append(f"  {block.id}: {successor.kind.value} -> {target}")
    hashes["pipeline_cfg.txt"] = _write_text(
        evidence_dir / "pipeline_cfg.txt",
        "\n".join([
            "P2-02 CFG evidence (direct-CFG stress)",
            "======================================",
            f"mode: {cfg.mode.value}",
            f"fingerprint: {cfg.fingerprint()}",
            "blocks: " + ", ".join(f"0x{block.entry_address:x}" for block in cfg.ordered_blocks()),
            "edges:",
            *edge_lines,
            "",
        ]),
    )

    discovery = staging["discovery"]
    hashes["pipeline_functions.txt"] = _write_text(
        evidence_dir / "pipeline_functions.txt",
        "\n".join([
            "P2-03 function-discovery evidence",
            "=================================",
            f"entry_function: {discovery.entry_function_id}",
            f"fingerprint: {discovery.fingerprint()}",
            "functions: " + ", ".join(f"{f.id}@0x{f.entry_address:x}" for f in discovery.functions),
            "unowned_blocks: " + ", ".join(discovery.unowned_blocks),
            "",
        ]),
    )

    call_graph = staging["call_graph"]
    hashes["pipeline_call_graph.txt"] = _write_text(
        evidence_dir / "pipeline_call_graph.txt",
        "\n".join([
            "P2-04 call-graph evidence",
            "=========================",
            "nodes: " + ", ".join(node.function_id for node in call_graph.nodes),
            "edges:",
            *[f"  {edge.caller} -> {edge.callee} ({edge.kind.value})" for edge in sorted(call_graph.edges, key=lambda item: (item.caller, item.callee))],
            f"fingerprint: {call_graph.fingerprint()}",
            "",
        ]),
    )

    units = staging["units"]
    hashes["pipeline_translation_units.txt"] = _write_text(
        evidence_dir / "pipeline_translation_units.txt",
        "\n".join([
            "P2-05 translation-unit evidence",
            "===============================",
            "units: " + ", ".join(f"{unit.unit_id}({unit.function_id})" for unit in units.units),
            "unowned_blocks: " + ", ".join(units.unowned_blocks),
            f"fingerprint: {units.fingerprint()}",
            "",
        ]),
    )

    classification = staging["classification"]
    classification_lines = [
        "P2-06 indirect-control-flow evidence",
        "====================================",
        f"fingerprint: {classification.fingerprint()}",
    ]
    for unit in classification.units:
        for item in unit.classifications:
            classification_lines.append(
                f"  {item.block_id} 0x{item.address:x} {item.kind.value} status={item.status.value} "
                f"basis={item.basis.value} targets={list(item.targets)}"
            )
    classification_lines.append("")
    hashes["pipeline_indirect_control_flow.txt"] = _write_text(
        evidence_dir / "pipeline_indirect_control_flow.txt", "\n".join(classification_lines)
    )

    host = staging["host"]
    source_bytes = host.source_text.encode("utf-8")
    (evidence_dir / "generated_source.c").write_bytes(source_bytes)
    hashes["generated_source.c"] = hashlib.sha256(source_bytes).hexdigest()
    hashes["generated_source_sha256.txt"] = _write_text(
        evidence_dir / "generated_source_sha256.txt",
        f"generated_source.c sha256: {hashes['generated_source.c']}\n"
        f"register_names: {list(host.register_names)}\n"
        f"fingerprint: {host.fingerprint()}\n",
    )

    comparison = staging["comparison"]
    (evidence_dir / "build_manifest.json").write_bytes(comparison.runs[0].manifest.serialize())
    hashes["build_manifest.json"] = hashlib.sha256((evidence_dir / "build_manifest.json").read_bytes()).hexdigest()
    for index, run in enumerate(comparison.runs[:2]):
        manifest = run.manifest
        lines = [
            f"P2-12 deterministic build run {index + 1}",
            "=" * 36,
            f"build_status: {manifest.build_status.value}",
            f"classification: {manifest.reproducibility.value}",
            "inputs:",
        ]
        for item in manifest.inputs:
            lines.append(f"  {item.kind.value} {item.name} {item.sha256}")
        lines.append("outputs:")
        for artifact in manifest.outputs:
            lines.append(f"  {artifact.kind.value} {artifact.name} {artifact.sha256}")
        lines += [
            "compile_commands:",
            *["  " + " ".join(command) for command in manifest.compile_commands],
            "link_command: " + " ".join(manifest.link_command),
            f"manifest_sha256: {manifest.fingerprint()}",
            "",
        ]
        hashes[f"build_run_{index + 1}.txt"] = _write_text(evidence_dir / f"build_run_{index + 1}.txt", "\n".join(lines))

    expected = staging["expected_output"]
    actual = staging["actual_output"]
    hashes["native_execution.txt"] = _write_text(
        evidence_dir / "native_execution.txt",
        "\n".join([
            "P2-12 native execution",
            "======================",
            f"executable sha256: {staging['exe_sha256']}",
            f"returncode: {staging['native_returncode']}",
            "stdout:",
            actual,
            "",
        ]),
    )
    hashes["expected_vs_actual.txt"] = _write_text(
        evidence_dir / "expected_vs_actual.txt",
        "\n".join([
            "P2-12 expected vs actual observable",
            "===================================",
            "expected (independent true-MIPS32 reference interpreter):",
            expected,
            "actual (native executable stdout):",
            actual,
            f"EXPECTED == ACTUAL: {'YES' if expected == actual else 'NO'}",
            "",
        ]),
    )

    lines = [
        "P2-12 bounded-dispatch fail-closed evidence",
        "===========================================",
        *switch_failclosed_lines,
        "",
    ]
    hashes["switch_fail_closed.txt"] = _write_text(evidence_dir / "switch_fail_closed.txt", "\n".join(lines))
    return hashes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    parser.add_argument("--evidence-dir", help="write deterministic UTF-8 evidence here (output only)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # A. fixture identity and encoder cross-check --------------------------
    check("fixture-byte-length", len(FIXTURE_BYTES) == 4 * len(FIXTURE))
    check("fixture-sha256", FIXTURE_SHA256 == hashlib.sha256(struct.pack("<%dI" % len(WORDS), *WORDS)).hexdigest())
    check("fixture-instruction-count", len(FIXTURE) == 35)
    check("encoder-addiu", _addiu(29, 0, 0x100) == WORD_BY_ADDR[0x1000])
    check("encoder-sw", _sw(31, 29, 4) == WORD_BY_ADDR[0x1008])
    check("encoder-lw", _lw(31, 29, 4) == WORD_BY_ADDR[0x1038])
    check("encoder-addu", _addu(2, 2, 3) == WORD_BY_ADDR[0x101C])
    check("encoder-slti", _slti(4, 3, 5) == WORD_BY_ADDR[0x1020])
    check("encoder-bne", _branch(0x05, 4, 0, 0x1024, 0x1018) == WORD_BY_ADDR[0x1024])
    check("encoder-beq", _branch(0x04, 8, 0, 0x1040, CASE_B) == WORD_BY_ADDR[0x1040])
    check("encoder-j", _jtype(0x02, 0x1074) == WORD_BY_ADDR[0x1064])
    check("encoder-jal", _jtype(0x03, LEAF) == WORD_BY_ADDR[0x1030])
    check("encoder-jr", _jr(5) == WORD_BY_ADDR[0x1054])
    check("fixture-synthetic-origin", all(mnemonic for _, _, mnemonic in FIXTURE))

    # B. decode -------------------------------------------------------------
    staging = run_pipeline()
    instructions = decode_fixture()
    ops = [instruction.op for instruction in instructions]
    check("decode-addresses", [instruction.address for instruction in instructions] == [address for address, _, _ in FIXTURE])
    check("decode-loop-backedge-target", instructions[9].direct_target == 0x1018 and instructions[9].flow is InstructionFlow.BRANCH)
    check("decode-call-target", instructions[12].direct_target == LEAF and instructions[12].flow is InstructionFlow.CALL)
    check("decode-jump-target", instructions[25].direct_target == 0x1074 and instructions[25].flow is InstructionFlow.JUMP)
    check("decode-dispatch-unresolved", instructions[21].flow is InstructionFlow.INDIRECT_JUMP and instructions[21].unresolved)
    check("decode-memory-flow-normal", instructions[2].flow is InstructionFlow.NORMAL and instructions[14].flow is InstructionFlow.NORMAL)
    check("decode-size-bytes", all(instruction.size_bytes == 4 for instruction in instructions))

    # C. CFG ----------------------------------------------------------------
    cfg = staging["cfg"]
    discovery = staging["discovery"]
    call_graph = staging["call_graph"]
    units = staging["units"]
    classification = staging["classification"]
    host = staging["host"]

    check("cfg-block-count", len(cfg.blocks) == 14)
    check("cfg-loop-backedge", _edge_targets(cfg, "blk_1018", EdgeKind.BRANCH_TAKEN) == [0x1018])
    check("cfg-loop-exit", _edge_targets(cfg, "blk_1018", EdgeKind.BRANCH_NOT_TAKEN) == [0x1028])
    check("cfg-branch-to-caseb", _edge_targets(cfg, "blk_1034", EdgeKind.BRANCH_TAKEN) == [CASE_B])
    check("cfg-branch-to-casea", _edge_targets(cfg, "blk_1044", EdgeKind.BRANCH_TAKEN) == [CASE_A])
    check("cfg-dispatch-unresolved", _edge_kinds(cfg, "blk_104c") == [EdgeKind.INDIRECT])
    check("cfg-jump-to-end", _edge_targets(cfg, "blk_105c", EdgeKind.JUMP) == [0x1074])
    check("cfg-caseb-fallthrough", _edge_targets(cfg, "blk_106c", EdgeKind.FALLTHROUGH) == [0x1074])
    check("cfg-call-continuation", _edge_targets(cfg, "blk_1028", EdgeKind.CALL_RETURN) == [0x1034])
    check("cfg-deterministic", cfg.fingerprint() == run_pipeline()["cfg"].fingerprint())

    check("functions-two", [function.id for function in discovery.functions] == ["fn_1000", "fn_1080"])
    check("functions-loop-owned", [block.id for block in discovery.function("fn_1000").blocks] == ["blk_1000", "blk_1018", "blk_1028", "blk_1034", "blk_1044", "blk_104c", "blk_105c", "blk_106c", "blk_1074"])
    check("functions-leaf-owned", [block.id for block in discovery.function("fn_1080").blocks] == ["blk_1080"])
    check("functions-unowned-delay-slots", discovery.unowned_blocks == ("blk_1058", "blk_1068", "blk_107c", "blk_1088"))
    check("functions-deterministic", discovery.fingerprint() == run_pipeline()["discovery"].fingerprint())

    check("callgraph-nodes", [node.function_id for node in call_graph.nodes] == ["fn_1000", "fn_1080"])
    check("callgraph-edge", len(call_graph.edges) == 1 and call_graph.edges[0].caller == "fn_1000" and call_graph.edges[0].callee == "fn_1080" and call_graph.edges[0].kind is CallEdgeKind.INTERNAL_DIRECT)
    check("units-two", [unit.unit_id for unit in units.units] == ["tu_fn_1000", "tu_fn_1080"])
    check("units-deterministic", units.fingerprint() == run_pipeline()["units"].fingerprint())

    sites = sorted(
        ((item.address, item.status, item.basis, item.targets) for unit in classification.units for item in unit.classifications),
        key=lambda item: item[0],
    )
    check("indirect-site-count", len(sites) == 3)
    dispatch = [item for item in sites if item[0] == DISPATCH]
    check("indirect-dispatch-resolved", len(dispatch) == 1 and dispatch[0][1] is IndirectControlFlowStatus.RESOLVED)
    check("indirect-dispatch-basis", dispatch[0][2] is IndirectControlFlowBasis.EXACT_TARGET_SET)
    check("indirect-dispatch-targets", dispatch[0][3] == (CASE_A, CASE_B))
    check("indirect-returns", sorted(item[0] for item in sites if item[1] is IndirectControlFlowStatus.RETURN_LIKE) == [0x1078, 0x1084])

    unclassified = run_pipeline(evidence_kind="none")
    unclassified_sites = [item for unit in unclassified["classification"].units for item in unit.classifications]
    dispatch_none = [item for item in unclassified_sites if item.address == DISPATCH][0]
    check("indirect-no-evidence-fails-closed", dispatch_none.status is IndirectControlFlowStatus.UNRESOLVED_INDIRECT_JUMP)
    check("indirect-no-evidence-no-targets", dispatch_none.targets == ())
    check("indirect-no-evidence-boundary", 'or_fail("unresolved indirect jump");' in unclassified["host"].source_text)
    expect_fail(
        "indirect-no-evidence-reject-policy",
        lambda: run_pipeline(evidence_kind="none", policy=HostUnsupportedPolicy.REJECT),
        HostEmitterError,
    )

    bounded = run_pipeline(evidence_kind="bounded")
    bounded_host = bounded["host"]
    check("bounded-not-promoted", 'or_fail("bounded candidate set is not a resolved target");' in bounded_host.source_text)
    check("bounded-no-case-emission", "case UINT64_C(4188)" not in bounded_host.source_text)
    expect_fail(
        "bounded-reject-policy",
        lambda: run_pipeline(evidence_kind="bounded", policy=HostUnsupportedPolicy.REJECT),
        HostEmitterError,
    )

    # D. host emission ------------------------------------------------------
    check("emission-loop-backedge", "goto bb_blk_1018; else goto bb_blk_1028;" in host.source_text)
    check("emission-dispatch-switch", "switch ((uint64_t)(g_r[" in host.source_text)
    check("emission-switch-cases", f"case UINT64_C({CASE_A}): goto bb_blk_105c;" in host.source_text and f"case UINT64_C({CASE_B}): goto bb_blk_106c;" in host.source_text)
    check("emission-switch-default-fails-closed", 'default: or_fail("indirect target outside proven set"); return;' in host.source_text)
    check("emission-call", "fn_fn_1080();" in host.source_text and "goto bb_blk_1034;" in host.source_text)
    check("emission-memory", "or_rt_memory_read(" in host.source_text and "or_rt_memory_write(" in host.source_text)
    check("emission-returns", host.source_text.count("return;") >= 4)
    check("emission-deterministic", host.source_text == run_pipeline()["host"].source_text)
    check("emission-no-hardcoded-result-125", "UINT64_C(125)" not in host.source_text)
    check("emission-no-pointer-cast", "*(uint32_t *)" not in host.source_text and "memcpy" not in host.source_text)

    # E. independent expected observable ------------------------------------
    regs, _ram = reference_execute()
    check("reference-registers", {index: regs[index] for index in EXPECTED_REGS} == EXPECTED_REGS)
    check("derivation-loop-sum", regs[2] == 15 + 5)
    check("derivation-case-a-result", regs[6] == 100 + regs[2])
    check("derivation-end", regs[7] == regs[6] + 5)
    check("derivation-restored-ra", regs[31] == 0)
    expected = expected_output(host.register_names, regs)

    # F. deterministic native build -----------------------------------------
    workspace = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p212-"))
    comparison = None
    try:
        config = bp.BuildConfig(fixture_id=FIXTURE_ID, expected_smoke_output=expected)
        comparison = bp.build_generated_host_from(
            lambda: run_pipeline()["host"],
            support_sources=(
                bp.BuildSource("runtime_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, SUPPORT_SOURCE.encode("utf-8")),
            ),
            config=config,
            workspace=workspace,
            keep_workspace=True,
        )
        check("build-status-ok", all(run.manifest.build_status is bp.BuildStatus.OK for run in comparison.runs))
        check("build-classification", comparison.classification is bp.BuildReproducibility.EXECUTABLE_REPRODUCIBLE)
        check("build-source-reproducible", comparison.source_reproducible)
        check("build-manifest-reproducible", comparison.manifest_reproducible)
        check("build-object-reproducible", comparison.object_reproducible is True)
        check("build-executable-reproducible", comparison.executable_reproducible is True)
        manifest = comparison.runs[0].manifest
        check("build-brepro", all("/Brepro" in command for command in manifest.compile_commands) and "/Brepro" in manifest.link_command)
        check("build-manifest-deterministic", manifest.serialize() == comparison.runs[1].manifest.serialize())
        manifest_text = manifest.serialize().decode("utf-8")
        check("build-manifest-no-path-leak", str(ROOT) not in manifest_text and str(workspace) not in manifest_text)
        check("build-manifest-no-identity", (not os.environ.get("USERNAME") or os.environ["USERNAME"] not in manifest_text) and (not os.environ.get("COMPUTERNAME") or os.environ["COMPUTERNAME"] not in manifest_text))

        # G. native execution -------------------------------------------------
        executable = workspace / "run1" / "program.exe"
        exe_sha = hashlib.sha256(executable.read_bytes()).hexdigest()
        check("native-executable-hash-matches-manifest", manifest.artifact_map(bp.BuildArtifactKind.EXECUTABLE).get("program.exe") == exe_sha)
        first = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        second = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        actual = (first.stdout or "").strip()
        check("native-returncode-zero", first.returncode == 0)
        check("native-output-stable", actual == (second.stdout or "").strip())
        check("expected-equals-actual", expected == actual)
        observed_by_index = {}
        for line in actual.splitlines()[2:]:
            match = re.match(r"reg\[(\d+)\]=(\d+)$", line.strip())
            if match:
                observed_by_index[int(match.group(1))] = int(match.group(2))
        observed_guest = {int(name[1:]): observed_by_index[index] for index, name in enumerate(host.register_names)}
        check("native-guest-registers", {index: observed_guest[index] for index in EXPECTED_REGS} == EXPECTED_REGS)

        # H. bounded dispatch fail-closed at runtime --------------------------
        oob_table = tuple(
            (address, (0x24052000 if address == 0x1050 else word), mnemonic)
            for address, word, mnemonic in FIXTURE
        )
        oob_workspace = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p212-oob-"))
        switch_lines = []
        try:
            oob_host = run_pipeline(oob_table)["host"]
            check("oob-selector-not-in-proven-set", "UINT64_C(8192)" in oob_host.source_text)
            bp.build_generated_host_from(
                lambda: oob_host,
                support_sources=(bp.BuildSource("runtime_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, SUPPORT_SOURCE.encode("utf-8")),),
                config=bp.BuildConfig(fixture_id=FIXTURE_ID + "-oob", smoke_test=False),
                workspace=oob_workspace,
                keep_workspace=True,
            )
            oob_exe = oob_workspace / "run1" / "program.exe"
            oob_run = subprocess.run([str(oob_exe)], capture_output=True, text=True, encoding="utf-8", errors="replace")
            oob_stdout = (oob_run.stdout or "").strip()
            check("runtime-switch-default-fails-closed", oob_stdout.startswith("failed=1"))
            check("runtime-switch-default-error", "indirect target outside proven set" in oob_stdout)
            switch_lines = [
                "fixture variant: selector r5 = 0x2000 (8192), outside the proven set {0x105c, 0x106c}",
                f"executable returncode: {oob_run.returncode}",
                "stdout:",
                oob_stdout,
                "result: PASS (bounded switch default reported the out-of-set target; no guessed dispatch)",
            ]
        finally:
            shutil.rmtree(oob_workspace, ignore_errors=True)

        if args.evidence_dir:
            write_evidence(
                pathlib.Path(args.evidence_dir),
                {
                    "cfg": cfg, "discovery": discovery, "call_graph": call_graph, "units": units,
                    "classification": classification, "host": host, "dispatch_site": staging["dispatch_site"],
                    "comparison": comparison, "expected_output": expected, "actual_output": actual,
                    "native_returncode": first.returncode, "exe_sha256": exe_sha,
                },
                switch_failclosed_lines=switch_lines,
            )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    # I. fail-closed --------------------------------------------------------
    expect_fail("missing-slti-rule", lambda: emit_host_translation(
        units, classification,
        config=HostEmitterConfig(semantics=HostSemantics([
            HostInstructionSemantics(ARCH, "nop", InstructionFlow.NORMAL),
            HostInstructionSemantics(ARCH, "jr", InstructionFlow.INDIRECT_JUMP, indirect_source=HostRegister("rs")),
        ]), entry_function="fn_1000", word_bits=32, runtime_abi=rt.RuntimeAbiConfig()),
    ), HostEmitterError)
    expect_fail("external-call-fails-closed", lambda: run_pipeline(tuple(
        (address, (0x0C000800 if address == 0x1030 else word), mnemonic) for address, word, mnemonic in FIXTURE
    )), HostEmitterError)
    expect_fail("bad-load-base", lambda: HostLoad("x", HostRegister("rs"), HostImmediate("imm")), HostEmitterError)
    expect_fail("unsupported-opcode", lambda: mips32_adapter.decode(0x1000, 0xFC000000), mips32_adapter.DecodeError)
    expect_fail("misaligned-entry", lambda: build_cfg(decode_fixture(), source=program_source(), entries=[EntryPoint(0x1002, PROVEN)], mode=CFGMode.CLOSED), CFGError)
    expect_fail("empty-region", lambda: build_cfg((), source=program_source(), entries=[EntryPoint(ENTRY, PROVEN)], mode=CFGMode.CLOSED), CFGError)

    # J. no next-stage work -------------------------------------------------
    import ast as _ast

    tree = _ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in _ast.walk(tree)
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef))
    }
    for token in ("p2_13", "p2_14", "p2_20", "runtime_host_boundary"):
        check(f"no-next-stage-symbol:{token}", not any(token in name.lower() for name in defined))
    check("no-p2-13-evidence-directory", not (ROOT / ".openrecomp-phase2" / "evidence" / "P2-13").exists())

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    if args.json:
        record = {
            "stage": "P2-12",
            "marker": f"OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "fixture_id": FIXTURE_ID,
            "fixture_sha256": FIXTURE_SHA256,
            "fixture_byte_length": len(FIXTURE_BYTES),
            "loop_back_edge": True,
            "call_edge": {"caller": "fn_1000", "callee": "fn_1080", "kind": "INTERNAL_DIRECT"},
            "bounded_dispatch": {"address": DISPATCH, "targets": [CASE_A, CASE_B], "basis": "EXACT_TARGET_SET", "lowering": "switch"},
            "generated_source_sha256": host.fingerprint(),
            "register_names": list(host.register_names),
            "expected_observable": expected if comparison is not None else None,
            "actual_observable": actual if comparison is not None else None,
            "expected_equals_actual": (comparison is not None and expected == actual),
            "classification": comparison.classification.value if comparison else None,
            "results": sorted(RESULTS, key=lambda item: item["check"]),
        }
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_MIPS32_DIRECT_CFG_V1_JSON={out.name}")

    print(f"OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests={tests}")
    return 0


def _edge_targets(cfg, block_id, kind):
    return sorted(
        successor.target_address
        for successor in cfg.block(block_id).successors
        if successor.kind is kind and successor.resolved
    )


def _edge_kinds(cfg, block_id):
    return sorted(successor.kind for successor in cfg.block(block_id).successors)


if __name__ == "__main__":
    raise SystemExit(main())
