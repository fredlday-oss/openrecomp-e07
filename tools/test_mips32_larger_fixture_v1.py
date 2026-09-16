#!/usr/bin/env python3
"""OpenRecomp larger MIPS32 open-fixture proof V1 (P2-14).

Exercises the full Phase-2 pipeline on a larger synthetic/original MIPS32
program with deterministic recompilation and replay:

    synthetic 4-function fixture (57 instructions)
    -> adapters.mips32 decode -> P2-01 ProgramModel -> P2-02 CFG
    -> P2-03 function discovery -> P2-04 call graph (3 internal calls)
    -> P2-05 translation units (4 units) -> P2-06 RETURN_LIKE classification
    -> P2-07 host emitter (loop, calls, nested frames, lw/sw)
    -> P2-09 deterministic build -> native executable -> replay

The program iterates `i = 1..20`, accumulates `outer(i) = 4i + 1` in a
memory-resident accumulator and tracks the maximum, then returns
`total + best = 941`. The expected observable is derived independently by a
true-MIPS32 reference interpreter (delay slots, `jal`/`jr $ra`, `lw`/`sw`,
bounded RAM) plus the explicit mathematical derivation; the native result is
never used to derive the expectation.

Deterministic recompilation is checked by running the whole structural pipeline
twice and comparing every fingerprint and the emitted source byte-for-byte.
Replay is checked by executing the built native program repeatedly and requiring
byte-identical stdout.

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
    HostEmitterConfig,
    HostEmitterError,
    HostImmediate,
    HostInstructionSemantics,
    HostLoad,
    HostRegister,
    HostSemantics,
    HostStore,
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
PROVEN = EvidenceClass.PROVEN
FIXTURE_ID = "p2-14-mips32-larger-open-fixture-v1"
RAM_SIZE = 4096
LOOP_ITERATIONS = 20
TOTAL = 860
BEST = 81
OBSERVABLE = 941

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


# --- deterministic fixture assembler ---------------------------------------
def _rtype(rs, rt, rd, shamt, funct):
    return (0 << 26) | (rs << 21) | (rt << 16) | (rd << 11) | (shamt << 6) | funct


def _itype(op, rs, rt, imm):
    return (op << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def _jtype(op, target):
    return (op << 26) | ((target >> 2) & 0x03FFFFFF)


def addiu(rt, rs, imm):
    return _itype(0x09, rs, rt, imm)


def addu(rd, rs, rt):
    return _rtype(rs, rt, rd, 0, 0x21)


def slt(rd, rs, rt):
    return _rtype(rs, rt, rd, 0, 0x2A)


def lw(rt, rs, imm):
    return _itype(0x23, rs, rt, imm)


def sw(rt, rs, imm):
    return _itype(0x2B, rs, rt, imm)


def beq(rs, rt, label):
    return ("BEQ", rs, rt, label)


def bne(rs, rt, label):
    return ("BNE", rs, rt, label)


def j(label):
    return ("J", label)


def jal(label):
    return ("JAL", label)


def jr(rs):
    return _rtype(rs, 0, 0, 0, 0x08)


NOP = 0x00000000

# (label, instruction) -- synthetic/original MIPS32 program (4 functions).
PROGRAM = (
    ("main", addiu(29, 0, 0x400)),
    ("main", addiu(29, 29, -24)),
    ("main", sw(31, 29, 20)),
    ("main", addiu(4, 0, 0)),
    ("main", sw(4, 29, 0)),
    ("main", sw(4, 29, 4)),
    ("main", addiu(9, 0, 0)),
    ("main", addiu(6, 0, LOOP_ITERATIONS)),
    ("loop", slt(7, 9, 6)),
    ("loop", beq(7, 0, "after")),
    ("loop", NOP),
    ("loop", addiu(9, 9, 1)),
    ("loop", addu(4, 9, 0)),
    ("loop", jal("outer")),
    ("loop", NOP),
    ("loop", lw(3, 29, 0)),
    ("loop", addu(3, 3, 2)),
    ("loop", sw(3, 29, 0)),
    ("loop", lw(4, 29, 4)),
    ("loop", addu(5, 2, 0)),
    ("loop", jal("bigger")),
    ("loop", NOP),
    ("loop", sw(2, 29, 4)),
    ("loop", j("loop")),
    ("loop", NOP),
    ("after", lw(4, 29, 0)),
    ("after", lw(5, 29, 4)),
    ("after", addu(6, 4, 5)),
    ("after", addiu(10, 6, 0)),
    ("after", lw(31, 29, 20)),
    ("after", addiu(29, 29, 24)),
    ("after", jr(31)),
    ("after", NOP),
    ("outer", addiu(29, 29, -8)),
    ("outer", sw(31, 29, 4)),
    ("outer", addu(4, 4, 0)),
    ("outer", jal("inner")),
    ("outer", NOP),
    ("outer", addu(2, 2, 4)),
    ("outer", lw(31, 29, 4)),
    ("outer", addiu(29, 29, 8)),
    ("outer", jr(31)),
    ("outer", NOP),
    ("inner", addu(2, 4, 4)),
    ("inner", addu(2, 2, 4)),
    ("inner", addiu(2, 2, 1)),
    ("inner", jr(31)),
    ("inner", NOP),
    ("bigger", slt(2, 4, 5)),
    ("bigger", bne(2, 0, "takeb")),
    ("bigger", NOP),
    ("bigger", addu(2, 4, 0)),
    ("bigger", jr(31)),
    ("bigger", NOP),
    ("takeb", addu(2, 5, 0)),
    ("takeb", jr(31)),
    ("takeb", NOP),
)


def assemble(program=PROGRAM, entry=ENTRY):
    labels = {}
    address = entry
    for label, insn in program:
        if label not in labels:
            labels[label] = address
        address += 4
    instructions = []
    address = entry
    for label, insn in program:
        if isinstance(insn, tuple):
            kind = insn[0]
            if kind in ("BEQ", "BNE"):
                _, rs, rt, target = insn
                op = 0x04 if kind == "BEQ" else 0x05
                imm = ((labels[target] - (address + 4)) >> 2) & 0xFFFF
                word = _itype(op, rs, rt, imm)
            elif kind in ("J", "JAL"):
                _, target = insn
                op = 0x02 if kind == "J" else 0x03
                word = _jtype(op, labels[target])
            else:
                raise AssertionError(kind)
        else:
            word = insn
        instructions.append((address, word, f"{label}: 0x{word:08x}"))
        address += 4
    return tuple(instructions), labels


FIXTURE, LABELS = assemble()
WORDS = tuple(word for _, word, _ in FIXTURE)
WORD_BY_ADDR = {address: word for address, word, _ in FIXTURE}
FIXTURE_BYTES = struct.pack("<%dI" % len(WORDS), *WORDS)
FIXTURE_SHA256 = hashlib.sha256(FIXTURE_BYTES).hexdigest()

FLOW = {
    "nop": InstructionFlow.NORMAL,
    "addiu": InstructionFlow.NORMAL,
    "addu": InstructionFlow.NORMAL,
    "slt": InstructionFlow.NORMAL,
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


def program_source():
    return ProgramSource(ARCH, adapter="adapters.mips32", address_width_bits=32, endianness="little", input_sha256=FIXTURE_SHA256)


def semantics_table():
    def r(op, flow, **kw):
        return HostInstructionSemantics(ARCH, op, flow, **kw)
    return HostSemantics([
        r("nop", InstructionFlow.NORMAL),
        r("addiu", InstructionFlow.NORMAL, operations=(HostBinop(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True), "add"),)),
        r("addu", InstructionFlow.NORMAL, operations=(HostBinop(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "add"),)),
        r("slt", InstructionFlow.NORMAL, operations=(HostCompare(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "slt"),)),
        r("lw", InstructionFlow.NORMAL, operations=(HostLoad(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True)),)),
        r("sw", InstructionFlow.NORMAL, operations=(HostStore(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True)),)),
        r("beq", InstructionFlow.BRANCH, condition=HostComparison(HostRegister("rs"), HostRegister("rt"), "eq")),
        r("bne", InstructionFlow.BRANCH, condition=HostComparison(HostRegister("rs"), HostRegister("rt"), "ne")),
        r("j", InstructionFlow.JUMP),
        r("jal", InstructionFlow.CALL),
        r("jr", InstructionFlow.INDIRECT_JUMP, indirect_source=HostRegister("rs")),
    ])


def run_pipeline(*, with_evidence=True, table=FIXTURE):
    source = program_source()
    cfg = build_cfg(decode_fixture(table), source=source, entries=[EntryPoint(ENTRY, PROVEN)], mode=CFGMode.CLOSED)
    discovery = discover_functions(cfg, program_entries=[ENTRY])
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)
    evidence = []
    if with_evidence:
        for unit in units.units:
            for block in unit.blocks:
                terminal = block.terminal
                if terminal.flow is InstructionFlow.INDIRECT_JUMP:
                    evidence.append(IndirectControlFlowEvidence(
                        function_id=unit.function_id, block_id=block.id, address=terminal.address,
                        kind=IndirectControlFlowKind.INDIRECT_JUMP,
                        status=IndirectControlFlowStatus.RETURN_LIKE,
                        basis=IndirectControlFlowBasis.STRUCTURAL_RETURN_EVIDENCE,
                        source="p2-14-fixture", evidence=PROVEN,
                    ))
    classification = classify_indirect_control_flow(units, evidence=evidence)
    host = emit_host_translation(units, classification, config=HostEmitterConfig(
        semantics=semantics_table(), entry_function=discovery.entry_function_id, word_bits=32,
        runtime_abi=rt.RuntimeAbiConfig(),
    ))
    return {"cfg": cfg, "discovery": discovery, "call_graph": call_graph, "units": units,
            "classification": classification, "host": host}


# --- independent reference interpreter --------------------------------------
def reference_execute(limit=200000):
    """A tiny independent true-MIPS32 interpreter with delay slots."""
    regs = [0] * 32
    ram = bytearray(RAM_SIZE)
    pc = ENTRY
    pending = None
    steps = 0
    while True:
        steps += 1
        if steps > limit:
            raise AssertionError("reference interpreter step limit exceeded")
        if pc == 0:
            break
        if pc not in WORD_BY_ADDR:
            raise AssertionError(f"reference interpreter left the fixture at 0x{pc:x}")
        word = WORD_BY_ADDR[pc]
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
        elif opcode == 0 and funct == 0x2A:
            regs[rd] = 1 if regs[rs] < regs[rt_field] else 0
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
        elif opcode in (0x02, 0x03):
            branch = True
            target = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
            if opcode == 0x03:
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
    return regs, steps


def expected_output(register_names, regs):
    lines = ["failed=0", "error="]
    for index, name in enumerate(register_names):
        lines.append(f"reg[{index}]={regs[int(name[1:])]}")
    return "\n".join(lines)


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


def _write_text(path, text):
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def write_evidence(evidence_dir, staging):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    hashes = {}
    fixture_lines = [
        "P2-14 synthetic MIPS32 larger open fixture",
        "=" * 42,
        f"architecture: {ARCH}",
        "endianness: little",
        f"entry: 0x{ENTRY:x}",
        f"instruction count: {len(FIXTURE)}",
        f"byte length: {len(FIXTURE_BYTES)}",
        f"sha256: {FIXTURE_SHA256}",
        "origin: synthetic/original (no commercial ROM/ELF bytes)",
        "functions: main@0x1000, outer@0x1084, inner@0x10ac, bigger@0x10c0",
        "labels: " + ", ".join(f"{name}=0x{value:x}" for name, value in sorted(LABELS.items())),
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
    hashes["pipeline_cfg.txt"] = _write_text(evidence_dir / "pipeline_cfg.txt", "\n".join([
        "P2-02 CFG evidence", "==================",
        f"mode: {cfg.mode.value}", f"fingerprint: {cfg.fingerprint()}",
        f"block_count: {len(cfg.blocks)}",
        "blocks: " + ", ".join(f"0x{block.entry_address:x}" for block in cfg.ordered_blocks()),
        "edges:", *edge_lines, "",
    ]))

    discovery = staging["discovery"]
    hashes["pipeline_functions.txt"] = _write_text(evidence_dir / "pipeline_functions.txt", "\n".join([
        "P2-03 function-discovery evidence", "=================================",
        f"entry_function: {discovery.entry_function_id}", f"fingerprint: {discovery.fingerprint()}",
        "functions: " + ", ".join(f"{f.id}@0x{f.entry_address:x}" for f in discovery.functions),
        "unowned_blocks: " + ", ".join(discovery.unowned_blocks), "",
    ]))

    call_graph = staging["call_graph"]
    hashes["pipeline_call_graph.txt"] = _write_text(evidence_dir / "pipeline_call_graph.txt", "\n".join([
        "P2-04 call-graph evidence", "=========================",
        "nodes: " + ", ".join(node.function_id for node in call_graph.nodes), "edges:",
        *[f"  {e.caller} -> {e.callee} ({e.kind.value})" for e in sorted(call_graph.edges, key=lambda item: (item.caller, item.callee))],
        f"fingerprint: {call_graph.fingerprint()}", "",
    ]))

    units = staging["units"]
    hashes["pipeline_translation_units.txt"] = _write_text(evidence_dir / "pipeline_translation_units.txt", "\n".join([
        "P2-05 translation-unit evidence", "===============================",
        "units: " + ", ".join(f"{unit.unit_id}({unit.function_id})" for unit in units.units),
        "unowned_blocks: " + ", ".join(units.unowned_blocks), f"fingerprint: {units.fingerprint()}", "",
    ]))

    classification = staging["classification"]
    classification_lines = ["P2-06 indirect-control-flow evidence", "====================================",
                            f"fingerprint: {classification.fingerprint()}"]
    for unit in classification.units:
        for item in unit.classifications:
            classification_lines.append(
                f"  {item.block_id} 0x{item.address:x} {item.kind.value} status={item.status.value} "
                f"basis={item.basis.value} targets={list(item.targets)}")
    classification_lines.append("")
    hashes["pipeline_indirect_control_flow.txt"] = _write_text(evidence_dir / "pipeline_indirect_control_flow.txt", "\n".join(classification_lines))

    host = staging["host"]
    source_bytes = host.source_text.encode("utf-8")
    (evidence_dir / "generated_source.c").write_bytes(source_bytes)
    hashes["generated_source.c"] = hashlib.sha256(source_bytes).hexdigest()
    hashes["generated_source_sha256.txt"] = _write_text(evidence_dir / "generated_source_sha256.txt",
        f"generated_source.c sha256: {hashes['generated_source.c']}\nregister_names: {list(host.register_names)}\nfingerprint: {host.fingerprint()}\n")

    comparison = staging["comparison"]
    (evidence_dir / "build_manifest.json").write_bytes(comparison.runs[0].manifest.serialize())
    hashes["build_manifest.json"] = hashlib.sha256((evidence_dir / "build_manifest.json").read_bytes()).hexdigest()
    for index, run in enumerate(comparison.runs[:2]):
        manifest = run.manifest
        lines = [f"P2-14 deterministic build run {index + 1}", "=" * 36,
                 f"build_status: {manifest.build_status.value}", f"classification: {manifest.reproducibility.value}", "inputs:"]
        for item in manifest.inputs:
            lines.append(f"  {item.kind.value} {item.name} {item.sha256}")
        lines.append("outputs:")
        for artifact in manifest.outputs:
            lines.append(f"  {artifact.kind.value} {artifact.name} {artifact.sha256}")
        lines += ["compile_commands:", *["  " + " ".join(command) for command in manifest.compile_commands],
                  "link_command: " + " ".join(manifest.link_command), f"manifest_sha256: {manifest.fingerprint()}", ""]
        hashes[f"build_run_{index + 1}.txt"] = _write_text(evidence_dir / f"build_run_{index + 1}.txt", "\n".join(lines))

    expected = staging["expected_output"]
    actual = staging["actual_output"]
    hashes["native_execution.txt"] = _write_text(evidence_dir / "native_execution.txt", "\n".join([
        "P2-14 native execution", "======================",
        f"executable sha256: {staging['exe_sha256']}", f"returncode: {staging['native_returncode']}",
        "stdout:", actual, ""]))
    hashes["expected_vs_actual.txt"] = _write_text(evidence_dir / "expected_vs_actual.txt", "\n".join([
        "P2-14 expected vs actual observable", "===================================",
        "expected (independent true-MIPS32 reference interpreter + derivation):", expected,
        "actual (native executable stdout):", actual,
        f"EXPECTED == ACTUAL: {'YES' if expected == actual else 'NO'}", ""]))

    hashes["recompilation.txt"] = _write_text(evidence_dir / "recompilation.txt", "\n".join(staging["recompilation_lines"]))
    hashes["replay.txt"] = _write_text(evidence_dir / "replay.txt", "\n".join(staging["replay_lines"]))
    return hashes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    parser.add_argument("--evidence-dir", help="write deterministic UTF-8 evidence here (output only)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # A. fixture ------------------------------------------------------------
    check("fixture-assembler-deterministic", assemble() == (FIXTURE, LABELS))
    check("fixture-byte-length", len(FIXTURE_BYTES) == 4 * len(FIXTURE))
    check("fixture-sha256", FIXTURE_SHA256 == hashlib.sha256(struct.pack("<%dI" % len(WORDS), *WORDS)).hexdigest())
    check("fixture-instruction-count", len(FIXTURE) == 57)
    check("fixture-four-functions", set(LABELS) >= {"main", "outer", "inner", "bigger"})
    check("fixture-synthetic-origin", all(mnemonic for _, _, mnemonic in FIXTURE))

    # B. decode -------------------------------------------------------------
    instructions = decode_fixture()
    ops = [instruction.op for instruction in instructions]
    check("decode-addresses", [instruction.address for instruction in instructions] == [address for address, _, _ in FIXTURE])
    check("decode-call-count", ops.count("jal") == 3)
    check("decode-memory-count", ops.count("lw") == 6 and ops.count("sw") == 6)
    check("decode-jr-count", ops.count("jr") == 5)
    check("decode-loop-branch", instructions[9].flow is InstructionFlow.BRANCH and instructions[9].direct_target == LABELS["after"])
    check("decode-back-jump", instructions[23].flow is InstructionFlow.JUMP and instructions[23].direct_target == LABELS["loop"])
    check("decode-call-targets", [i.direct_target for i in instructions if i.op == "jal"] == [LABELS["outer"], LABELS["bigger"], LABELS["inner"]])
    check("decode-size-bytes", all(instruction.size_bytes == 4 for instruction in instructions))

    # C. structural pipeline ------------------------------------------------
    staging = run_pipeline()
    cfg = staging["cfg"]
    discovery = staging["discovery"]
    call_graph = staging["call_graph"]
    units = staging["units"]
    classification = staging["classification"]
    host = staging["host"]

    check("cfg-block-count", len(cfg.blocks) == 18)
    check("cfg-loop-conditional-taken", _edge_targets(cfg, "blk_1020", EdgeKind.BRANCH_TAKEN) == [LABELS["after"]])
    check("cfg-loop-conditional-not-taken", _edge_targets(cfg, "blk_1020", EdgeKind.BRANCH_NOT_TAKEN) == [0x1028])
    check("cfg-back-jump", _edge_targets(cfg, "blk_1054", EdgeKind.JUMP) == [LABELS["loop"]])
    check("cfg-call-continuations", _call_continuations(cfg) == {"blk_1028": 0x1038, "blk_1038": 0x1054, "blk_1084": 0x1094})
    check("cfg-deterministic", cfg.fingerprint() == run_pipeline()["cfg"].fingerprint())

    check("functions-four", [function.id for function in discovery.functions] == ["fn_1000", "fn_1084", "fn_10ac", "fn_10c0"])
    check("functions-count", len(discovery.functions) == 4)
    check("functions-unowned-delay-slots", len(discovery.unowned_blocks) == 6)
    check("functions-deterministic", discovery.fingerprint() == run_pipeline()["discovery"].fingerprint())

    check("callgraph-nodes", [node.function_id for node in call_graph.nodes] == ["fn_1000", "fn_1084", "fn_10ac", "fn_10c0"])
    check("callgraph-edges", sorted((e.caller, e.callee) for e in call_graph.edges) == [
        ("fn_1000", "fn_1084"), ("fn_1000", "fn_10c0"), ("fn_1084", "fn_10ac")])
    check("callgraph-all-internal", all(e.kind is CallEdgeKind.INTERNAL_DIRECT for e in call_graph.edges))
    check("callgraph-deterministic", call_graph.fingerprint() == run_pipeline()["call_graph"].fingerprint())

    check("units-four", [unit.unit_id for unit in units.units] == ["tu_fn_1000", "tu_fn_1084", "tu_fn_10ac", "tu_fn_10c0"])
    check("units-call-edges", [len(unit.call_edges) for unit in units.units] == [2, 1, 0, 0])
    check("units-deterministic", units.fingerprint() == run_pipeline()["units"].fingerprint())

    sites = [item for unit in classification.units for item in unit.classifications]
    check("indirect-site-count", len(sites) == 5)
    check("indirect-all-return-like", all(item.status is IndirectControlFlowStatus.RETURN_LIKE for item in sites))
    check("indirect-no-guessed-targets", all(item.targets == () for item in sites))
    no_evidence_classification = classify_indirect_control_flow(units, evidence=[])
    check("indirect-no-evidence-unresolved", all(
        item.status is IndirectControlFlowStatus.UNRESOLVED_INDIRECT_JUMP
        for unit in no_evidence_classification.units for item in unit.classifications))

    # D. host emission ------------------------------------------------------
    check("emission-prototypes", all(f"static void fn_{name}(void);" in host.source_text for name in ("fn_1000", "fn_1084", "fn_10ac", "fn_10c0")))
    check("emission-calls", all(f"fn_{name}();" in host.source_text for name in ("fn_1084", "fn_10ac", "fn_10c0")))
    check("emission-loop-backedge", f"goto bb_blk_{LABELS['loop']:x};" in host.source_text)
    check("emission-memory", "or_rt_memory_read(" in host.source_text and "or_rt_memory_write(" in host.source_text)
    check("emission-memory-fail-closed", 'or_fail("runtime memory read failed");' in host.source_text and 'or_fail("runtime memory write failed");' in host.source_text)
    check("emission-deterministic", host.source_text == run_pipeline()["host"].source_text)
    check("emission-no-hardcoded-observable", "UINT64_C(941)" not in host.source_text and "UINT64_C(860)" not in host.source_text)
    check("emission-no-pointer-cast", "*(uint32_t *)" not in host.source_text and "memcpy" not in host.source_text)

    # E. independent expected observable ------------------------------------
    regs, steps = reference_execute()
    check("derivation-total", regs[3] == TOTAL and regs[4] == TOTAL)
    check("derivation-best", regs[5] == BEST)
    check("derivation-observable", regs[6] == OBSERVABLE and regs[10] == OBSERVABLE)
    check("derivation-iteration", regs[9] == LOOP_ITERATIONS)
    check("derivation-restored-sp", regs[29] == 0x400)
    check("derivation-restored-ra", regs[31] == 0)
    check("derivation-formula", 4 * (LOOP_ITERATIONS * (LOOP_ITERATIONS + 1) // 2) + LOOP_ITERATIONS == TOTAL and 4 * LOOP_ITERATIONS + 1 == BEST)
    check("reference-step-count", steps > 500)
    expected = expected_output(host.register_names, regs)

    # F. deterministic recompilation and replay -----------------------------
    second = run_pipeline()
    recompilation_lines = [
        "P2-14 deterministic recompilation",
        "=================================",
        "two independent structural pipeline runs (decode -> CFG -> discovery -> call graph -> units -> classification -> emission)",
        f"cfg fingerprint identical: {cfg.fingerprint() == second['cfg'].fingerprint()} ({cfg.fingerprint()})",
        f"functions fingerprint identical: {discovery.fingerprint() == second['discovery'].fingerprint()} ({discovery.fingerprint()})",
        f"call graph fingerprint identical: {call_graph.fingerprint() == second['call_graph'].fingerprint()} ({call_graph.fingerprint()})",
        f"units fingerprint identical: {units.fingerprint() == second['units'].fingerprint()} ({units.fingerprint()})",
        f"classification fingerprint identical: {classification.fingerprint() == second['classification'].fingerprint()} ({classification.fingerprint()})",
        f"generated source byte-identical: {host.source_text == second['host'].source_text}",
        f"generated source sha256: {host.fingerprint()}",
        "",
    ]
    check("recompilation-cfg-identical", cfg.fingerprint() == second["cfg"].fingerprint())
    check("recompilation-functions-identical", discovery.fingerprint() == second["discovery"].fingerprint())
    check("recompilation-callgraph-identical", call_graph.fingerprint() == second["call_graph"].fingerprint())
    check("recompilation-units-identical", units.fingerprint() == second["units"].fingerprint())
    check("recompilation-classification-identical", classification.fingerprint() == second["classification"].fingerprint())
    check("recompilation-source-identical", host.source_text == second["host"].source_text)

    workspace = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p214-"))
    comparison = None
    replay_lines = []
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

        executable = workspace / "run1" / "program.exe"
        exe_sha = hashlib.sha256(executable.read_bytes()).hexdigest()
        check("native-executable-hash-matches-manifest", manifest.artifact_map(bp.BuildArtifactKind.EXECUTABLE).get("program.exe") == exe_sha)
        run_outputs = []
        for _ in range(3):
            ran = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
            check_ok = ran.returncode == 0
            run_outputs.append(((ran.stdout or "").strip(), ran.returncode))
        actual = run_outputs[0][0]
        check("replay-returncode-zero", all(returncode == 0 for _, returncode in run_outputs))
        check("replay-byte-identical", len({output for output, _ in run_outputs}) == 1)
        check("expected-equals-actual", expected == actual)
        replay_lines = [
            "P2-14 deterministic replay",
            "==========================",
            f"executable sha256: {exe_sha}",
            f"replays: {len(run_outputs)}",
            "stdout sha256 per replay:",
            *[f"  run {index + 1}: {hashlib.sha256(output.encode('utf-8')).hexdigest()}" for index, (output, _) in enumerate(run_outputs)],
            f"byte-identical: {len({output for output, _ in run_outputs}) == 1}",
            f"returncode: {run_outputs[0][1]}",
            f"observable r10: {OBSERVABLE}",
            "",
        ]
        check("replay-stdout-hash-stable", len({hashlib.sha256(output.encode('utf-8')).hexdigest() for output, _ in run_outputs}) == 1)

        if args.evidence_dir:
            write_evidence(pathlib.Path(args.evidence_dir), {
                "cfg": cfg, "discovery": discovery, "call_graph": call_graph, "units": units,
                "classification": classification, "host": host, "comparison": comparison,
                "expected_output": expected, "actual_output": actual, "native_returncode": run_outputs[0][1],
                "exe_sha256": exe_sha, "recompilation_lines": recompilation_lines, "replay_lines": replay_lines,
            })
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    # G. fail-closed --------------------------------------------------------
    expect_fail("missing-semantics-rule", lambda: emit_host_translation(
        units, classification,
        config=HostEmitterConfig(semantics=HostSemantics([
            HostInstructionSemantics(ARCH, "nop", InstructionFlow.NORMAL),
            HostInstructionSemantics(ARCH, "jr", InstructionFlow.INDIRECT_JUMP, indirect_source=HostRegister("rs")),
        ]), entry_function="fn_1000", word_bits=32, runtime_abi=rt.RuntimeAbiConfig()),
    ), HostEmitterError)
    expect_fail("memory-without-runtime-abi", lambda: emit_host_translation(
        units, classification,
        config=HostEmitterConfig(semantics=semantics_table(), entry_function="fn_1000", word_bits=32),
    ), HostEmitterError)
    inner_call = next(i.address for i in decode_fixture() if i.op == "jal" and i.direct_target == LABELS["inner"])
    external_table = tuple(
        (address, (0x0C000800 if address == inner_call else word), mnemonic)
        for address, word, mnemonic in FIXTURE
    )
    expect_fail("external-call-fails-closed", lambda: run_pipeline(table=external_table), HostEmitterError)
    expect_fail("unsupported-opcode", lambda: mips32_adapter.decode(0x1000, 0xFC000000), mips32_adapter.DecodeError)
    expect_fail("misaligned-entry", lambda: build_cfg(decode_fixture(), source=program_source(), entries=[EntryPoint(0x1002, PROVEN)], mode=CFGMode.CLOSED), CFGError)
    expect_fail("empty-region", lambda: build_cfg((), source=program_source(), entries=[EntryPoint(ENTRY, PROVEN)], mode=CFGMode.CLOSED), CFGError)

    # H. no next-stage work -------------------------------------------------
    import ast as _ast

    tree = _ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    defined = {node.name for node in _ast.walk(tree) if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef))}
    for token in ("p2_20", "nes6502", "program_bridge"):
        check(f"no-next-stage-symbol:{token}", not any(token in name.lower() for name in defined))
    # P2-14 is a MIPS32-only stage; it must not depend on the later NES6502 bridge.
    # (The former "P2-20 evidence must not exist" cross-stage guard was replaced
    # here once P2-20 was authorized; it asserted build state, not a P2-14
    # property, and could not hold while P2-20 was in progress.)
    gate_imports: set[str] = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            gate_imports.update(alias.name for alias in node.names)
        elif isinstance(node, _ast.ImportFrom):
            gate_imports.add(node.module or "")
    check("no-nes6502-dependency-in-p2-14", not any("nes6502" in value.lower() for value in gate_imports))

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    if args.json:
        record = {
            "stage": "P2-14",
            "marker": f"OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "fixture_id": FIXTURE_ID,
            "fixture_sha256": FIXTURE_SHA256,
            "fixture_byte_length": len(FIXTURE_BYTES),
            "instruction_count": len(FIXTURE),
            "function_count": len(discovery.functions),
            "call_edge_count": len(call_graph.edges),
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
        print(f"OPENRECOMP_MIPS32_LARGER_FIXTURE_V1_JSON={out.name}")

    print(f"OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests={tests}")
    return 0


def _edge_targets(cfg, block_id, kind):
    return sorted(successor.target_address for successor in cfg.block(block_id).successors if successor.kind is kind and successor.resolved)


def _edge_kinds(cfg, block_id):
    return sorted(successor.kind for successor in cfg.block(block_id).successors)


def _call_continuations(cfg):
    return {
        block.id: successor.target_address
        for block in cfg.ordered_blocks()
        for successor in block.successors
        if successor.kind is EdgeKind.CALL_RETURN and successor.resolved
    }


if __name__ == "__main__":
    raise SystemExit(main())
