#!/usr/bin/env python3
"""OpenRecomp MIPS32 calls/stack/memory proof V1 (P2-11).

Extends the bounded P2-10 end-to-end proof to multiple functions, a stack
frame and checked guest loads/stores through the generic runtime ABI (P2-08):

    synthetic fixture -> adapters.mips32 decode -> P2-01 ProgramModel -> P2-02 CFG
    -> P2-03 function discovery (two functions, one direct call)
    -> P2-04 call graph (internal direct edge) -> P2-05 translation units
    -> P2-06 indirect-control-flow classification (two RETURN_LIKE sites)
    -> P2-07 host emitter (additive HostLoad/HostStore through or_rt_memory_*)
    -> P2-09 deterministic build -> native executable -> expected vs actual

The expected observable is derived independently of the generated host code by a
tiny reference interpreter with true MIPS32 delay slots, `jal`/`jr $ra`
linkage, `lw`/`sw` and a bounded little-endian RAM, plus an explicit
mathematical derivation and a RAM checksum.

The fixture uses the standard o32 stack-frame pattern (save/restore `$ra`) so
the structural call/return model and the true MIPS model agree on the observable.
This gate proves only this bounded synthetic fixture; it is not full MIPS32
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
    HostComparison,
    HostConst,
    HostConstant,
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
LEAF = 0x1088
PROVEN = EvidenceClass.PROVEN
FIXTURE_ID = "p2-11-mips32-calls-memory-v1"
RAM_SIZE = 4096

# (address, word, mnemonic) -- synthetic/original fixture, little-endian MIPS32.
FIXTURE = (
    (0x1000, 0x241D0100, "addiu sp, r0, 0x100"),
    (0x1004, 0x27BDFFF8, "addiu sp, sp, -8"),
    (0x1008, 0xAFBF0004, "sw ra, 4(sp)"),
    (0x100C, 0x24040015, "addiu r4, r0, 21"),
    (0x1010, 0xAFA40000, "sw r4, 0(sp)"),
    (0x1014, 0x0C000422, "jal 0x1088"),
    (0x1018, 0x00000000, "nop (delay slot)"),
    (0x101C, 0x8FA50000, "lw r5, 0(sp)"),
    (0x1020, 0x8FBF0004, "lw ra, 4(sp)"),
    (0x1024, 0x00A22821, "addu r5, r5, r2"),
    (0x1028, 0x27BD0008, "addiu sp, sp, 8"),
    (0x102C, 0x03E00008, "jr ra"),
    (0x1030, 0x00000000, "nop (delay slot)"),
    (0x1088, 0x24020015, "addiu r2, r0, 21"),
    (0x108C, 0x03E00008, "jr ra"),
    (0x1090, 0x00000000, "nop (delay slot)"),
)
WORDS = tuple(word for _, word, _ in FIXTURE)
WORD_BY_ADDR = {address: word for address, word, _ in FIXTURE}
FIXTURE_BYTES = struct.pack("<%dI" % len(WORDS), *WORDS)
FIXTURE_SHA256 = hashlib.sha256(FIXTURE_BYTES).hexdigest()

FLOW = {
    "nop": InstructionFlow.NORMAL,
    "addiu": InstructionFlow.NORMAL,
    "addu": InstructionFlow.NORMAL,
    "lw": InstructionFlow.NORMAL,
    "sw": InstructionFlow.NORMAL,
    "beq": InstructionFlow.BRANCH,
    "bne": InstructionFlow.BRANCH,
    "jal": InstructionFlow.CALL,
    "j": InstructionFlow.JUMP,
    "jr": InstructionFlow.INDIRECT_JUMP,
}

# Independent derivation (true MIPS32 with delay slots):
#   sp = 0x100; sp -= 8 -> 0xF8; store ra=0 at 0xF8+4 and r4=21 at 0xF8;
#   jal 0x1088 sets ra=0x101C; leaf sets r2=21 and returns;
#   lw r5 <- mem[0xF8] = 21; lw ra <- mem[0xFC] = 0; r5 += r2 = 42;
#   sp += 8 -> 0x100; jr ra with ra=0 halts.
EXPECTED_REGS = {2: 21, 4: 21, 5: 42, 29: 256, 31: 0}
EXPECTED_RAM_CHECKSUM = 409079371

SUPPORT_SOURCE = """\
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>

void openrecomp_run(void);
int openrecomp_failed(void);
size_t openrecomp_register_count(void);
uint64_t openrecomp_register_value(size_t index);

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
    size_t count = openrecomp_register_count();
    for (size_t index = 0; index < count; ++index) {
        printf("reg[%zu]=%llu\\n", index, (unsigned long long)openrecomp_register_value(index));
    }
    uint32_t checksum = 0;
    for (size_t index = 0; index < OR_RT_RAM_SIZE; ++index) checksum = (checksum * 31u + g_ram[index]) & 0xFFFFFFFFu;
    printf("ram_checksum=%u\\n", (unsigned)checksum);
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


# --- ingestion --------------------------------------------------------------
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


def semantics_table(include_memory=True):
    def r(op, flow, **kw):
        return HostInstructionSemantics(ARCH, op, flow, **kw)

    rules = [
        r("nop", InstructionFlow.NORMAL),
        r("addiu", InstructionFlow.NORMAL, operations=(HostBinop(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True), "add"),)),
        r("addu", InstructionFlow.NORMAL, operations=(HostBinop(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "add"),)),
        r("jal", InstructionFlow.CALL),
        r("jr", InstructionFlow.INDIRECT_JUMP, indirect_source=HostRegister("rs")),
    ]
    if include_memory:
        rules.append(r("lw", InstructionFlow.NORMAL, operations=(HostLoad(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True)),)))
        rules.append(r("sw", InstructionFlow.NORMAL, operations=(HostStore(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True)),)))
    return HostSemantics(rules)


def emit_program(table=FIXTURE, *, include_memory=True, runtime_abi=True, entry=ENTRY):
    source = program_source()
    instructions = decode_fixture(table)
    cfg = build_cfg(instructions, source=source, entries=[EntryPoint(entry, PROVEN)], mode=CFGMode.CLOSED)
    discovery = discover_functions(cfg, program_entries=[entry])
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)
    evidence = []
    for unit in units.units:
        for block in unit.blocks:
            terminal = block.terminal
            if terminal.flow is InstructionFlow.INDIRECT_JUMP:
                evidence.append(
                    IndirectControlFlowEvidence(
                        function_id=unit.function_id,
                        block_id=block.id,
                        address=terminal.address,
                        kind=IndirectControlFlowKind.INDIRECT_JUMP,
                        status=IndirectControlFlowStatus.RETURN_LIKE,
                        basis=IndirectControlFlowBasis.STRUCTURAL_RETURN_EVIDENCE,
                        source="p2-11-fixture",
                        evidence=PROVEN,
                    )
                )
    classification = classify_indirect_control_flow(units, evidence=evidence)
    host = emit_host_translation(
        units,
        classification,
        config=HostEmitterConfig(
            semantics=semantics_table(include_memory=include_memory),
            entry_function=discovery.entry_function_id,
            word_bits=32,
            runtime_abi=rt.RuntimeAbiConfig() if runtime_abi else None,
        ),
    )
    return {
        "instructions": instructions,
        "cfg": cfg,
        "discovery": discovery,
        "call_graph": call_graph,
        "units": units,
        "classification": classification,
        "host": host,
    }


# --- independent reference interpreter --------------------------------------
def reference_execute(table=FIXTURE, entry=ENTRY, limit=4096):
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
        elif opcode == 0x23:  # lw
            address = (regs[rs] + imm) & 0xFFFFFFFF
            if address + 4 > RAM_SIZE:
                raise AssertionError(f"reference lw out of range at 0x{address:x}")
            regs[rt_field] = int.from_bytes(ram[address:address + 4], "little")
        elif opcode == 0x2B:  # sw
            address = (regs[rs] + imm) & 0xFFFFFFFF
            if address + 4 > RAM_SIZE:
                raise AssertionError(f"reference sw out of range at 0x{address:x}")
            ram[address:address + 4] = (regs[rt_field] & 0xFFFFFFFF).to_bytes(4, "little")
        elif opcode == 3:  # jal
            branch = True
            target = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
            regs[31] = (pc + 8) & 0xFFFFFFFF
        elif opcode == 0 and funct == 0x08:  # jr
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


def ram_checksum(ram):
    checksum = 0
    for byte in ram:
        checksum = (checksum * 31 + byte) & 0xFFFFFFFF
    return checksum


def expected_output(register_names, regs, checksum):
    lines = ["failed=0"]
    for index, name in enumerate(register_names):
        lines.append(f"reg[{index}]={regs[int(name[1:])]}")
    lines.append(f"ram_checksum={checksum}")
    return "\n".join(lines)


# --- evidence ---------------------------------------------------------------
def _write_text(path, text):
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def write_evidence(evidence_dir, staging):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    hashes = {}

    fixture_lines = [
        "P2-11 synthetic MIPS32 fixture (calls / stack / memory)",
        "=" * 56,
        f"architecture: {ARCH}",
        "endianness: little",
        "instruction width: 4 bytes",
        f"entry address: 0x{ENTRY:x}",
        f"leaf address: 0x{LEAF:x}",
        f"instruction count: {len(FIXTURE)}",
        f"byte length: {len(FIXTURE_BYTES)}",
        f"sha256: {FIXTURE_SHA256}",
        "origin: synthetic/original (no commercial ROM/ELF bytes)",
        "stack model: o32-style save/restore of $ra, local slot for r4",
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
        "\n".join(
            [
                "P2-02 CFG evidence",
                "==================",
                f"mode: {cfg.mode.value}",
                f"fingerprint: {cfg.fingerprint()}",
                "blocks: " + ", ".join(f"0x{block.entry_address:x}" for block in cfg.ordered_blocks()),
                "edges:",
                *edge_lines,
                "",
            ]
        ),
    )

    discovery = staging["discovery"]
    hashes["pipeline_functions.txt"] = _write_text(
        evidence_dir / "pipeline_functions.txt",
        "\n".join(
            [
                "P2-03 function-discovery evidence",
                "=================================",
                f"entry_function: {discovery.entry_function_id}",
                f"fingerprint: {discovery.fingerprint()}",
                "functions: " + ", ".join(f"{f.id}@0x{f.entry_address:x}" for f in discovery.functions),
                "unowned_blocks: " + ", ".join(discovery.unowned_blocks),
                "",
            ]
        ),
    )

    call_graph = staging["call_graph"]
    hashes["pipeline_call_graph.txt"] = _write_text(
        evidence_dir / "pipeline_call_graph.txt",
        "\n".join(
            [
                "P2-04 call-graph evidence",
                "=========================",
                "nodes: " + ", ".join(node.function_id for node in call_graph.nodes),
                "edges:",
                *[
                    f"  {edge.caller} -> {edge.callee} ({edge.kind.value})"
                    for edge in sorted(call_graph.edges, key=lambda item: (item.caller, item.callee))
                ],
                f"fingerprint: {call_graph.fingerprint()}",
                "",
            ]
        ),
    )

    units = staging["units"]
    hashes["pipeline_translation_units.txt"] = _write_text(
        evidence_dir / "pipeline_translation_units.txt",
        "\n".join(
            [
                "P2-05 translation-unit evidence",
                "===============================",
                "units: " + ", ".join(f"{unit.unit_id}({unit.function_id})" for unit in units.units),
                "unowned_blocks: " + ", ".join(units.unowned_blocks),
                f"fingerprint: {units.fingerprint()}",
                "",
            ]
        ),
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
            f"P2-11 deterministic build run {index + 1}",
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
        "\n".join(
            [
                "P2-11 native execution",
                "======================",
                f"executable sha256: {staging['exe_sha256']}",
                f"returncode: {staging['native_returncode']}",
                "stdout:",
                actual,
                "",
            ]
        ),
    )
    hashes["expected_vs_actual.txt"] = _write_text(
        evidence_dir / "expected_vs_actual.txt",
        "\n".join(
            [
                "P2-11 expected vs actual observable",
                "===================================",
                "expected (independent reference interpreter, true MIPS32 with delay slots):",
                expected,
                "actual (native executable stdout):",
                actual,
                f"EXPECTED == ACTUAL: {'YES' if expected == actual else 'NO'}",
                "",
            ]
        ),
    )

    runtime_lines = ["P2-11 runtime memory failure (fail-closed) evidence", "=" * 52]
    runtime_lines += staging["runtime_failure_lines"]
    runtime_lines.append("")
    hashes["runtime_memory_failure.txt"] = _write_text(
        evidence_dir / "runtime_memory_failure.txt", "\n".join(runtime_lines)
    )

    return hashes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    parser.add_argument("--evidence-dir", help="write deterministic UTF-8 evidence here (output only)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # A. fixture ------------------------------------------------------------
    check("fixture-byte-length", len(FIXTURE_BYTES) == 4 * len(FIXTURE))
    check("fixture-sha256", FIXTURE_SHA256 == hashlib.sha256(struct.pack("<%dI" % len(WORDS), *WORDS)).hexdigest())
    check("fixture-instruction-count", len(FIXTURE) == 16)
    check("fixture-two-functions", {0x1000, 0x1088} <= {address for address, _, _ in FIXTURE})
    check("fixture-noncontiguous", any(
        FIXTURE[index + 1][0] != FIXTURE[index][0] + 4 for index in range(len(FIXTURE) - 1)
    ))

    # B. decode -------------------------------------------------------------
    staging = emit_program()
    instructions = staging["instructions"]
    ops = [instruction.op for instruction in instructions]
    check("decode-addresses", [instruction.address for instruction in instructions] == [address for address, _, _ in FIXTURE])
    check(
        "decode-ops",
        ops == ["addiu", "addiu", "sw", "addiu", "sw", "jal", "nop", "lw", "lw", "addu", "addiu", "jr", "nop", "addiu", "jr", "nop"],
    )
    check("decode-jal-target", instructions[5].direct_target == LEAF and instructions[5].flow is InstructionFlow.CALL)
    check("decode-memory-flow-normal", instructions[2].flow is InstructionFlow.NORMAL and instructions[7].flow is InstructionFlow.NORMAL)
    check("decode-size-bytes", all(instruction.size_bytes == 4 for instruction in instructions))

    # C. pipeline -----------------------------------------------------------
    cfg = staging["cfg"]
    discovery = staging["discovery"]
    call_graph = staging["call_graph"]
    units = staging["units"]
    classification = staging["classification"]

    check("cfg-block-entries", [block.entry_address for block in cfg.ordered_blocks()] == [0x1000, 0x1018, 0x1030, 0x1088, 0x1090])
    check("cfg-call-continuation", _edge_targets(cfg, "blk_1000", EdgeKind.CALL_RETURN) == [0x1018])
    check("cfg-return-unresolved", _edge_kinds(cfg, "blk_1018") == [EdgeKind.INDIRECT] and _edge_kinds(cfg, "blk_1088") == [EdgeKind.INDIRECT])
    check("cfg-deterministic", cfg.fingerprint() == emit_program()["cfg"].fingerprint())

    check("functions-two", [function.id for function in discovery.functions] == ["fn_1000", "fn_1088"])
    check("functions-entry", discovery.entry_function_id == "fn_1000")
    check("functions-leaf-body", [block.id for block in discovery.function("fn_1088").blocks] == ["blk_1088"])
    check("functions-unowned-delay-slots", discovery.unowned_blocks == ("blk_1030", "blk_1090"))
    check("functions-deterministic", discovery.fingerprint() == emit_program()["discovery"].fingerprint())

    check("callgraph-nodes", [node.function_id for node in call_graph.nodes] == ["fn_1000", "fn_1088"])
    check("callgraph-internal-edge", len(call_graph.edges) == 1)
    edge = call_graph.edges[0]
    check("callgraph-edge-direction", edge.caller == "fn_1000" and edge.callee == "fn_1088")
    check("callgraph-edge-kind", edge.kind is CallEdgeKind.INTERNAL_DIRECT)
    check("callgraph-deterministic", call_graph.fingerprint() == emit_program()["call_graph"].fingerprint())

    check("units-two", [unit.unit_id for unit in units.units] == ["tu_fn_1000", "tu_fn_1088"])
    check("units-call-edge", [e.kind for u in units.units for e in u.call_edges if u.function_id == "fn_1000"] == [CallEdgeKind.INTERNAL_DIRECT])
    check("units-deterministic", units.fingerprint() == emit_program()["units"].fingerprint())

    classified_sites = [item for unit in classification.units for item in unit.classifications]
    check("indirect-site-count", len(classified_sites) == 2)
    check("indirect-sites-return-like", all(item.status is IndirectControlFlowStatus.RETURN_LIKE for item in classified_sites))
    check("indirect-sites-no-targets", all(item.targets == () for item in classified_sites))

    # D. host emission ------------------------------------------------------
    host = staging["host"]
    check("emission-two-declarations", "static void fn_fn_1000(void);" in host.source_text and "static void fn_fn_1088(void);" in host.source_text)
    check("emission-internal-call", "fn_fn_1088();" in host.source_text and "goto bb_blk_1018;" in host.source_text)
    check("emission-memory-read", "or_rt_memory_read(" in host.source_text)
    check("emission-memory-write", "or_rt_memory_write(" in host.source_text)
    check("emission-memory-abi-declarations", "extern int or_rt_memory_read(" in host.source_text and "extern int or_rt_memory_write(" in host.source_text)
    check("emission-memory-width-32", "or_rt_memory_read(or_addr, 32u, &or_value)" in host.source_text and "or_rt_memory_write(or_addr, 32u," in host.source_text)
    check("emission-memory-fail-closed", 'or_fail("runtime memory read failed");' in host.source_text and 'or_fail("runtime memory write failed");' in host.source_text)
    check("emission-return-like", host.source_text.count("return;") >= 3)
    check("emission-deterministic", host.source_text == emit_program()["host"].source_text)
    check("emission-no-hardcoded-result-42", "UINT64_C(42)" not in host.source_text)
    check("emission-no-guest-pointer-cast", "*(uint32_t *)" not in host.source_text and "memcpy" not in host.source_text)

    # E. independent expected observable ------------------------------------
    regs, ram = reference_execute()
    check("reference-registers", {index: regs[index] for index in EXPECTED_REGS} == EXPECTED_REGS)
    check("derivation-call-result", regs[5] == 21 + 21)
    check("derivation-restored-sp", regs[29] == 256)
    check("derivation-restored-ra", regs[31] == 0)
    check("derivation-ram-store", int.from_bytes(ram[248:252], "little") == 21)
    checksum = ram_checksum(ram)
    check("reference-ram-checksum", checksum == EXPECTED_RAM_CHECKSUM)
    expected = expected_output(host.register_names, regs, checksum)

    # F. deterministic native build -----------------------------------------
    workspace = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p211-"))
    comparison = None
    try:
        config = bp.BuildConfig(fixture_id=FIXTURE_ID, expected_smoke_output=expected)
        comparison = bp.build_generated_host_from(
            lambda: emit_program()["host"],
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
        check("build-manifest-no-repo-path", str(ROOT) not in manifest_text and str(workspace) not in manifest_text)
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
        check("native-ram-checksum", f"ram_checksum={EXPECTED_RAM_CHECKSUM}" in actual)
        observed_by_index = {}
        for line in actual.splitlines()[1:]:
            match = re.match(r"reg\[(\d+)\]=(\d+)$", line.strip())
            if match:
                observed_by_index[int(match.group(1))] = int(match.group(2))
        observed_guest = {int(name[1:]): observed_by_index[index] for index, name in enumerate(host.register_names)}
        check("native-guest-registers", {index: observed_guest[index] for index in EXPECTED_REGS} == EXPECTED_REGS)

        # H. runtime memory failure (fail closed) -----------------------------
        oob_table = (
            (0x1000, 0x241D1000, "addiu sp, r0, 0x1000"),
            (0x1004, 0x24040007, "addiu r4, r0, 7"),
            (0x1008, 0xAFA40000, "sw r4, 0(sp)"),
            (0x100C, 0x03E00008, "jr ra"),
            (0x1010, 0x00000000, "nop"),
        )
        oob_host = emit_program(oob_table)["host"]
        oob_workspace = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p211-oob-"))
        runtime_failure_lines = []
        try:
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
            check("runtime-oob-fails-closed", oob_stdout.startswith("failed=1"))
            runtime_failure_lines = [
                "fixture: addiu sp,r0,0x1000 ; sw r4,0(sp) (address 0x1000 is outside the 4096-byte runtime RAM)",
                f"executable returncode: {oob_run.returncode}",
                "stdout:",
                oob_stdout,
                f"observed failed flag: {oob_stdout.splitlines()[0] if oob_stdout else 'n/a'}",
                "result: PASS (runtime memory boundary reported the out-of-range access; no host out-of-bounds write)",
            ]
        finally:
            shutil.rmtree(oob_workspace, ignore_errors=True)

        if args.evidence_dir:
            write_evidence(
                pathlib.Path(args.evidence_dir),
                {
                    "cfg": cfg,
                    "discovery": discovery,
                    "call_graph": call_graph,
                    "units": units,
                    "classification": classification,
                    "host": host,
                    "comparison": comparison,
                    "expected_output": expected,
                    "actual_output": actual,
                    "native_returncode": first.returncode,
                    "exe_sha256": exe_sha,
                    "runtime_failure_lines": runtime_failure_lines,
                },
            )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    # I. fail-closed --------------------------------------------------------
    expect_fail(
        "memory-without-runtime-abi",
        lambda: emit_program(runtime_abi=False),
        HostEmitterError,
    )
    expect_fail(
        "missing-memory-semantics-rule",
        lambda: emit_program(include_memory=False),
        HostEmitterError,
    )
    expect_fail(
        "external-call-fails-closed",
        lambda: emit_program((
            (0x1000, 0x0C000800, "jal 0x2000 (external)"),
            (0x1004, 0x00000000, "nop"),
            (0x1008, 0x03E00008, "jr ra"),
            (0x100C, 0x00000000, "nop"),
        )),
        HostEmitterError,
    )
    expect_fail("bad-load-base", lambda: HostLoad("x", HostRegister("rs"), HostImmediate("imm")), HostEmitterError)
    expect_fail("bad-store-offset", lambda: HostStore(HostRegister("rt"), HostRegister("rs"), HostConstant(0)), HostEmitterError)
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
    for token in ("p2_12", "p2_13", "p2_20", "direct_table"):
        check(f"no-next-stage-symbol:{token}", not any(token in name.lower() for name in defined))
    # P2-11's bounded fixture must not use the later P2-12 bounded-switch lowering.
    # (The former "P2-12 evidence must not exist" cross-stage guard was replaced
    # here once P2-12 was authorized; it asserted build state, not a P2-11
    # property, and could not hold while P2-12 was in progress.)
    check("no-p2-12-switch-emission-in-p2-11", "switch (" not in host.source_text)

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    if args.json:
        record = {
            "stage": "P2-11",
            "marker": f"OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "fixture_id": FIXTURE_ID,
            "fixture_sha256": FIXTURE_SHA256,
            "fixture_byte_length": len(FIXTURE_BYTES),
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
        print(f"OPENRECOMP_MIPS32_CALLS_MEMORY_V1_JSON={out.name}")

    print(f"OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests={tests}")
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
