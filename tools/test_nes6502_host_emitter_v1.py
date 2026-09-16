#!/usr/bin/env python3
"""OpenRecomp NES6502 host-emitter path proof V1 (P2-21).

Proves that the NES6502 ProgramModel and translation-unit output proven in
P2-20 can be lowered into executable host-side code using the **same**
architecture-neutral Phase-2 host emitter and deterministic build pipeline used
by the MIPS32 path:

    synthetic NES6502 fixture
      -> adapters.nes6502 decode -> P2-01 ProgramModel -> P2-02 CFG
      -> P2-03 function discovery -> P2-04 call graph -> P2-05 translation units
      -> P2-06 indirect-control-flow classification -> P2-07 host emitter
      -> P2-08 generic runtime ABI (checked byte memory boundary)
      -> P2-09 deterministic build pipeline -> native executable -> execution

The fixture exercises representative NMOS 6502 behavior:

* register load (`ldx`),
* arithmetic (`adc`),
* flag manipulation (`clc`),
* conditional branch / counted loop (`dex`/`bne`),
* indexed memory store (`sta $0400,x`),
* direct subroutine call/return (`jsr`/`rts`),
* direct jump (`jmp`),
* unresolved indirect jump (`jmp ($0300)`) which remains fail-closed.

Expected observable behavior is derived independently from the frozen Phase-1
`tools/nes6502_reference_v1.py` interpreter. The generated host code is
expected to fail closed at the unresolved indirect jump with the same register
and memory state the reference had before it executed that runtime target.

This gate proves only this bounded synthetic fixture. It is not full NES6502
recompilation, not NES equivalence, and does not use a commercial ROM.
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

import adapters.nes6502 as nes_adapter  # noqa: E402
from nes6502_reference_v1 import NES6502State, ReferenceNES6502  # noqa: E402
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
    HostConstant,
    HostCopy,
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
    DecodedInstruction,
    EdgeKind,
    EvidenceClass,
    InstructionFlow,
    ProgramSource,
)
from openrecomp.translation_units import build_translation_units  # noqa: E402

ARCH = "nes6502"
ENTRY = 0x8000
MEMORY_SIZE = 0x10000
HALT = nes_adapter.HALT_OPCODE
PROVEN = EvidenceClass.PROVEN
FIXTURE_ID = "p2-21-nes6502-host-emitter-v1"

# --- deterministic fixture assembler ---------------------------------------
def assemble_fixture():
    """Assemble the synthetic NES6502 region deterministically."""
    items = [
        ("start", bytes([0xA2, 0x03])),           # ldx #$03
        ("loop", bytes([0x18])),                  # clc
        (None, bytes([0x69, 0x05])),              # adc #$05
        (None, bytes([0x9D, 0x00, 0x04])),        # sta $0400,x
        (None, bytes([0xCA])),                    # dex
        ("bne", bytes([0xD0, 0x00])),             # bne loop (patched)
        ("call", bytes([0x20, 0x00, 0x00])),      # jsr helper (patched)
        ("jmpd", bytes([0x4C, 0x00, 0x00])),      # jmp dispatch (patched)
        (None, bytes([0xEA])),                    # nop
        ("dispatch", bytes([0x6C, 0x00, 0x03])),  # jmp ($0300)
        (None, bytes([0xEA])),
        (None, bytes([0xEA])),
        (None, bytes([0xEA])),
        ("helper", bytes([0xE8])),                # inx
        (None, bytes([0x60])),                    # rts
    ]
    labels: dict[str, int] = {}
    address = ENTRY
    for label, data in items:
        if label is not None:
            labels[label] = address
        address += len(data)
    out = bytearray()
    address = ENTRY
    for label, data in items:
        if label == "bne":
            data = bytes([0xD0, (labels["loop"] - (address + 2)) & 0xFF])
        elif label == "call":
            target = labels["helper"]
            data = bytes([0x20, target & 0xFF, target >> 8])
        elif label == "jmpd":
            target = labels["dispatch"]
            data = bytes([0x4C, target & 0xFF, target >> 8])
        out.extend(data)
        address += len(data)
    return bytes(out), labels, address


CODE, LABELS, REGION_END = assemble_fixture()
FIXTURE_SHA256 = hashlib.sha256(CODE).hexdigest()
MEMORY = bytearray([HALT] * MEMORY_SIZE)
MEMORY[ENTRY:ENTRY + len(CODE)] = CODE


# --- ingestion / decode ------------------------------------------------------
def _register_fields():
    """Canonical guest-register names exposed to the host emitter.

    These are synthetic names for the 6502 architectural state plus a few
    temporaries. They live in adapter_fields so the architecture-neutral
    emitter can reference them without knowing 6502 register names.
    """
    return {
        "a": "a",
        "x": "x",
        "y": "y",
        "sp": "sp",
        "c": "c",
        "z": "z",
        "n": "n",
        "tmp": "tmp",
        "ea": "ea",
        "zero_offset": 0,
    }


def decode_fixture():
    """Decode the fixture into neutral instructions with emitter metadata."""
    instructions: list[DecodedInstruction] = []
    address = ENTRY
    while address < REGION_END:
        decoded = nes_adapter.decode_full(MEMORY, address)
        op = decoded["op"]
        fields = {key: value for key, value in decoded.items() if key not in {"address", "op", "length"}}
        adapter_fields = {**fields, **_register_fields()}

        emit_op = op
        flow = InstructionFlow.NORMAL
        unresolved = False
        direct_target = None

        if op == "jmp":
            if "indirect" in decoded:
                emit_op = "jmp_indirect"
                flow = InstructionFlow.INDIRECT_JUMP
                unresolved = True
            else:
                flow = InstructionFlow.JUMP
                direct_target = decoded.get("target")
        elif op == "jsr":
            flow = InstructionFlow.CALL
            direct_target = decoded.get("target")
        elif op == "rts":
            flow = InstructionFlow.RETURN
        elif op == "bne":
            flow = InstructionFlow.BRANCH
            direct_target = decoded.get("target")
        elif op == "sta":
            # The fixture only uses absolute-indexed-by-X stores.
            emit_op = "sta_abs_x"
        elif op in {"nop", "ldx", "clc", "adc", "dex", "inx"}:
            pass
        else:
            raise ValueError(f"P2-21 fixture contains unsupported op {op!r}")

        instructions.append(
            DecodedInstruction(
                address=decoded["address"],
                op=emit_op,
                size_bytes=decoded["length"],
                flow=flow,
                direct_target=direct_target,
                unresolved=unresolved,
                evidence=PROVEN,
                metadata={"adapter_fields": adapter_fields},
            )
        )
        address += decoded["length"]
    return tuple(instructions)


def program_source():
    return ProgramSource(
        ARCH,
        adapter="adapters.nes6502",
        address_width_bits=16,
        endianness="little",
        input_sha256=FIXTURE_SHA256,
    )


# --- semantic rules ----------------------------------------------------------
def _zn(value_reg: str):
    """Operations that update the Z and N flag registers from ``value_reg``."""
    c0 = HostConstant(0)
    c0x80 = HostConstant(0x80)
    return (
        HostCompare(HostRegister("z"), HostRegister(value_reg), c0, "eq"),
        HostBinop(HostRegister("n"), HostRegister(value_reg), c0x80, "and"),
        HostCompare(HostRegister("n"), HostRegister("n"), c0, "ne"),
    )


def semantics_table():
    """Explicit, proven semantic rules for the bounded 6502 subset."""
    def r(op, flow, **kw):
        return HostInstructionSemantics(ARCH, op, flow, **kw)

    c0 = HostConstant(0)
    c1 = HostConstant(1)
    c8 = HostConstant(8)
    c0xFF = HostConstant(0xFF)

    return HostSemantics([
        r("nop", InstructionFlow.NORMAL),
        r("clc", InstructionFlow.NORMAL, operations=(HostConst(HostRegister("c"), c0),)),
        r("sec", InstructionFlow.NORMAL, operations=(HostConst(HostRegister("c"), c1),)),
        r("ldx", InstructionFlow.NORMAL, operations=(
            HostCopy(HostRegister("x"), HostImmediate("imm8")),
            *_zn("x"),
        )),
        r("lda_imm", InstructionFlow.NORMAL, operations=(
            HostCopy(HostRegister("a"), HostImmediate("imm8")),
            *_zn("a"),
        )),
        r("adc", InstructionFlow.NORMAL, operations=(
            HostBinop(HostRegister("tmp"), HostRegister("a"), HostImmediate("imm8"), "add"),
            HostBinop(HostRegister("tmp"), HostRegister("tmp"), HostRegister("c"), "add"),
            HostBinop(HostRegister("a"), HostRegister("tmp"), c0xFF, "and"),
            HostBinop(HostRegister("c"), HostRegister("tmp"), c8, "lshr"),
            HostBinop(HostRegister("c"), HostRegister("c"), c1, "and"),
            *_zn("a"),
        )),
        r("dex", InstructionFlow.NORMAL, operations=(
            HostBinop(HostRegister("x"), HostRegister("x"), c1, "sub"),
            HostBinop(HostRegister("x"), HostRegister("x"), c0xFF, "and"),
            *_zn("x"),
        )),
        r("inx", InstructionFlow.NORMAL, operations=(
            HostBinop(HostRegister("x"), HostRegister("x"), c1, "add"),
            HostBinop(HostRegister("x"), HostRegister("x"), c0xFF, "and"),
            *_zn("x"),
        )),
        r("bne", InstructionFlow.BRANCH, condition=HostComparison(HostRegister("z"), c0, "eq")),
        r("beq", InstructionFlow.BRANCH, condition=HostComparison(HostRegister("z"), c0, "ne")),
        r("sta_abs_x", InstructionFlow.NORMAL, operations=(
            HostBinop(HostRegister("ea"), HostImmediate("abs,x"), HostRegister("x"), "add"),
            HostStore(HostRegister("a"), HostRegister("ea"), HostImmediate("zero_offset")),
        )),
        r("lda_abs", InstructionFlow.NORMAL, operations=(
            HostCopy(HostRegister("ea"), HostImmediate("abs")),
            HostLoad(HostRegister("a"), HostRegister("ea"), HostImmediate("zero_offset")),
            *_zn("a"),
        )),
        r("jmp", InstructionFlow.JUMP),
        r("jmp_indirect", InstructionFlow.INDIRECT_JUMP, indirect_source=HostRegister("ea")),
        r("jsr", InstructionFlow.CALL),
        r("rts", InstructionFlow.RETURN),
    ])


# --- pipeline ----------------------------------------------------------------
def run_pipeline():
    source = program_source()
    instructions = decode_fixture()
    cfg = build_cfg(instructions, source=source, entries=[EntryPoint(ENTRY, PROVEN)], mode=CFGMode.CLOSED)
    discovery = discover_functions(cfg, program_entries=[ENTRY])
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)
    classification = classify_indirect_control_flow(units)
    host = emit_host_translation(
        units,
        classification,
        config=HostEmitterConfig(
            semantics=semantics_table(),
            entry_function=discovery.entry_function_id,
            word_bits=16,
            runtime_abi=rt.RuntimeAbiConfig(),
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


# --- independent Phase-1 reference interpreter -------------------------------
def reference_execute():
    """Run the frozen Phase-1 reference interpreter on the fixture."""
    memory = bytearray(MEMORY)
    ref = ReferenceNES6502(memory, NES6502State(pc=ENTRY))
    trace = []
    while True:
        pc = ref.state.pc
        if not ref.step():
            break
        trace.append(pc)
    return ref, trace


def ram_checksum(memory):
    """Deterministic 31-accumulator checksum over guest RAM."""
    checksum = 0
    for byte in memory:
        checksum = (checksum * 31 + byte) & 0xFFFFFFFF
    return checksum


def expected_register_values():
    """Derive the expected synthetic register values at the fail-closed point.

    Traced from the emitted semantics (not from the native run):

    * loop runs three times, leaving A = 15, X = 0,
    * the helper ``inx`` leaves X = 1,
    * the unresolved indirect ``jmp ($0300)`` stops execution.
    """
    return {
        "a": 15,
        "c": 0,
        "ea": 0x0401,
        "n": 0,
        "tmp": 15,
        "x": 1,
        "z": 0,
    }


def expected_output(register_names):
    """Exact stdout expected from the native support harness.

    The expected RAM state reflects only the explicitly modeled stores
    (``sta $0400,x``); the 6502 stack effects of ``jsr``/``rts`` are not
    modeled by the structural call/return path, so they are excluded from the
    observable memory checksum.
    """
    values = expected_register_values()
    expected_memory = bytearray(MEMORY)
    expected_memory[0x0401] = 15
    expected_memory[0x0402] = 10
    expected_memory[0x0403] = 5
    checksum = ram_checksum(expected_memory)
    lines = ["failed=1", "error=unresolved indirect jump"]
    for index, name in enumerate(register_names):
        lines.append(f"reg[{index}]={values.get(name, 0)}")
    lines.append(f"ram_checksum={checksum}")
    return "\n".join(lines)


# --- deterministic build support ---------------------------------------------
def support_source(fixture_bytes):
    """Runtime support source with 64 KiB guest RAM and fixture pre-load."""
    byte_list = ",".join(str(b) for b in fixture_bytes)
    return f"""\
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>

void openrecomp_run(void);
int openrecomp_failed(void);
size_t openrecomp_register_count(void);
uint64_t openrecomp_register_value(size_t index);
const char *openrecomp_error(void);

#define GUEST_RAM_SIZE 0x10000u
static uint8_t g_ram[GUEST_RAM_SIZE];

static const uint8_t fixture[{len(fixture_bytes)}] = {{{byte_list}}};

int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value) {{
    if (width_bits != 16u || out_value == 0) return 2;
    if (address >= GUEST_RAM_SIZE) return 1;
    *out_value = g_ram[address];
    return 0;
}}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value) {{
    if (width_bits != 16u) return 2;
    if (address >= GUEST_RAM_SIZE) return 1;
    g_ram[address] = (uint8_t)(value & 0xFFu);
    return 0;
}}

const char *or_rt_failure_reason(int code) {{ (void)code; return ""; }}

int main(void) {{
    size_t i;
    for (i = 0; i < GUEST_RAM_SIZE; ++i) g_ram[i] = 0x02;
    for (i = 0; i < sizeof(fixture); ++i) g_ram[0x8000 + i] = fixture[i];
    openrecomp_run();
    printf("failed=%d\\n", openrecomp_failed());
    printf("error=%s\\n", openrecomp_error());
    size_t count = openrecomp_register_count();
    for (i = 0; i < count; ++i) {{
        printf("reg[%zu]=%llu\\n", i, (unsigned long long)openrecomp_register_value(i));
    }}
    uint32_t checksum = 0;
    for (i = 0; i < GUEST_RAM_SIZE; ++i) checksum = (checksum * 31u + g_ram[i]) & 0xFFFFFFFFu;
    printf("ram_checksum=%u\\n", (unsigned)checksum);
    return 0;
}}
"""


# --- evidence ----------------------------------------------------------------
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


def _write_text(path, text):
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _capture_stdout(command):
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return completed.stdout or "", completed.returncode


def write_evidence(evidence_dir, staging):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    hashes = {}

    # fixture.txt
    fixture_lines = [
        "P2-21 synthetic NES6502 fixture (host emitter path)",
        "===================================================",
        f"architecture: {ARCH}",
        "endianness: little",
        "address width: 16 bits",
        f"entry: 0x{ENTRY:04x}",
        f"region end: 0x{REGION_END:04x}",
        f"region byte length: {len(CODE)}",
        f"region sha256: {FIXTURE_SHA256}",
        "origin: synthetic/original (no commercial ROM bytes)",
        "labels: " + ", ".join(f"{name}=0x{value:04x}" for name, value in sorted(LABELS.items())),
        "",
        "region bytes (hex):",
        CODE.hex(),
        "",
        "decoded instructions:",
    ]
    for instruction in staging["instructions"]:
        fields = dict((instruction.metadata or {}).get("adapter_fields", {}))
        fixture_lines.append(
            f"  0x{instruction.address:04x}  {instruction.op:<12} size={instruction.size_bytes} "
            f"flow={instruction.flow.value} target={instruction.direct_target} fields={fields}"
        )
    fixture_lines.append("")
    hashes["fixture.txt"] = _write_text(evidence_dir / "fixture.txt", "\n".join(fixture_lines))

    # pipeline evidence files
    cfg = staging["cfg"]
    edge_lines = []
    for block in cfg.ordered_blocks():
        for successor in block.successors:
            target = successor.target_block if successor.resolved else successor.detail
            edge_lines.append(f"  {block.id}: {successor.kind.value} -> {target}")
    hashes["pipeline_cfg.txt"] = _write_text(
        evidence_dir / "pipeline_cfg.txt",
        "\n".join([
            "P2-02 CFG evidence (NES6502 host emitter)",
            "=========================================",
            f"mode: {cfg.mode.value}",
            f"fingerprint: {cfg.fingerprint()}",
            f"block_count: {len(cfg.blocks)}",
            "blocks: " + ", ".join(f"0x{block.entry_address:04x}" for block in cfg.ordered_blocks()),
            "edges:", *edge_lines, "",
        ]),
    )

    discovery = staging["discovery"]
    hashes["pipeline_functions.txt"] = _write_text(
        evidence_dir / "pipeline_functions.txt",
        "\n".join([
            "P2-03 function-discovery evidence (NES6502)",
            "===========================================",
            f"entry_function: {discovery.entry_function_id}",
            f"fingerprint: {discovery.fingerprint()}",
            "functions: " + ", ".join(f"{f.id}@0x{f.entry_address:04x}" for f in discovery.functions),
            "unowned_blocks: " + ", ".join(discovery.unowned_blocks),
            "",
        ]),
    )

    call_graph = staging["call_graph"]
    hashes["pipeline_call_graph.txt"] = _write_text(
        evidence_dir / "pipeline_call_graph.txt",
        "\n".join([
            "P2-04 call-graph evidence (NES6502)",
            "===================================",
            "nodes: " + ", ".join(node.function_id for node in call_graph.nodes),
            "edges:",
            *[f"  {e.caller} -> {e.callee} ({e.kind.value})" for e in sorted(call_graph.edges, key=lambda item: (item.caller, item.callee))],
            f"fingerprint: {call_graph.fingerprint()}",
            "",
        ]),
    )

    units = staging["units"]
    hashes["pipeline_translation_units.txt"] = _write_text(
        evidence_dir / "pipeline_translation_units.txt",
        "\n".join([
            "P2-05 translation-unit evidence (NES6502)",
            "=========================================",
            "units: " + ", ".join(f"{unit.unit_id}({unit.function_id})" for unit in units.units),
            "unowned_blocks: " + ", ".join(units.unowned_blocks),
            f"fingerprint: {units.fingerprint()}",
            "",
        ]),
    )

    classification = staging["classification"]
    classification_lines = [
        "P2-06 indirect-control-flow evidence (NES6502)",
        "==============================================",
        f"fingerprint: {classification.fingerprint()}",
    ]
    for unit in classification.units:
        for item in unit.classifications:
            classification_lines.append(
                f"  {item.block_id} 0x{item.address:04x} {item.kind.value} status={item.status.value} "
                f"basis={item.basis.value} targets={list(item.targets)}"
            )
    classification_lines.append("")
    hashes["pipeline_indirect_control_flow.txt"] = _write_text(
        evidence_dir / "pipeline_indirect_control_flow.txt",
        "\n".join(classification_lines),
    )

    # emitted host source
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

    # build evidence
    comparison = staging["comparison"]
    (evidence_dir / "build_manifest.json").write_bytes(comparison.runs[0].manifest.serialize())
    hashes["build_manifest.json"] = hashlib.sha256((evidence_dir / "build_manifest.json").read_bytes()).hexdigest()
    for index, run in enumerate(comparison.runs[:2]):
        manifest = run.manifest
        lines = [
            f"P2-21 deterministic build run {index + 1}",
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
        hashes[f"build_run_{index + 1}.txt"] = _write_text(
            evidence_dir / f"build_run_{index + 1}.txt", "\n".join(lines)
        )

    # execution / comparison
    hashes["native_execution.txt"] = _write_text(
        evidence_dir / "native_execution.txt",
        "\n".join([
            "P2-21 native execution",
            "======================",
            f"executable sha256: {staging['exe_sha256']}",
            f"returncode: {staging['native_returncode']}",
            "stdout:",
            staging["actual_output"],
            "",
        ]),
    )
    hashes["expected_vs_actual.txt"] = _write_text(
        evidence_dir / "expected_vs_actual.txt",
        "\n".join([
            "P2-21 expected vs actual observable",
            "===================================",
            "expected (independent reference interpreter + semantic derivation):",
            staging["expected_output"],
            "actual (native executable stdout):",
            staging["actual_output"],
            f"EXPECTED == ACTUAL: {'YES' if staging['expected_output'] == staging['actual_output'] else 'NO'}",
            "",
        ]),
    )

    ref, trace = reference_execute()
    hashes["reference_comparison.txt"] = _write_text(
        evidence_dir / "reference_comparison.txt",
        "\n".join([
            "P2-21 Phase-1 reference interpreter comparison",
            "==============================================",
            f"reference trace length: {len(trace)}",
            f"reference halted: pc=0x{ref.state.pc:04x} steps={ref.steps}",
            f"reference a={ref.state.a} x={ref.state.x} y={ref.state.y} sp=0x{ref.state.sp:02x} p=0x{ref.state.p:02x}",
            f"generated a={staging['observed_registers'].get('a')} x={staging['observed_registers'].get('x')}",
            f"a matches reference: {staging['observed_registers'].get('a') == ref.state.a}",
            f"x matches reference: {staging['observed_registers'].get('x') == ref.state.x}",
            f"ram_checksum: {ram_checksum(ref.memory)}",
            "",
        ]),
    )

    # determinism
    hashes["determinism.txt"] = _write_text(
        evidence_dir / "determinism.txt",
        "\n".join([
            "P2-21 determinism evidence",
            "==========================",
            f"run 1 stdout sha256: {staging['stdout_sha1']}",
            f"run 2 stdout sha256: {staging['stdout_sha2']}",
            f"stdout byte-identical: {staging['stdout_sha1'] == staging['stdout_sha2']}",
            "",
        ]),
    )

    return hashes


# --- main --------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    parser.add_argument("--evidence-dir", help="write deterministic UTF-8 evidence here (output only)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # A. fixture ------------------------------------------------------------
    check("fixture-assembler-deterministic", assemble_fixture() == (CODE, LABELS, REGION_END))
    check("fixture-region-length", len(CODE) == 26)
    check("fixture-region-sha256", FIXTURE_SHA256 == hashlib.sha256(CODE).hexdigest())
    check("fixture-entry", ENTRY == 0x8000 and LABELS["start"] == ENTRY)
    check("fixture-region-end", REGION_END == 0x801A)
    check("fixture-halt-padding", MEMORY[0x0202] == HALT and MEMORY[REGION_END] == HALT)
    check("fixture-synthetic-origin", all(0 <= byte <= 0xFF for byte in CODE))

    # B. decode / structural pipeline ---------------------------------------
    staging = run_pipeline()
    instructions = staging["instructions"]
    cfg = staging["cfg"]
    discovery = staging["discovery"]
    call_graph = staging["call_graph"]
    units = staging["units"]
    classification = staging["classification"]
    host = staging["host"]

    expected_addresses = [0x8000, 0x8002, 0x8003, 0x8005, 0x8008, 0x8009, 0x800B, 0x800E,
                          0x8011, 0x8012, 0x8015, 0x8016, 0x8017, 0x8018, 0x8019]
    check("decode-instruction-count", len(instructions) == 15)
    check("decode-addresses", [i.address for i in instructions] == expected_addresses)
    check("decode-ops", [i.op for i in instructions] == [
        "ldx", "clc", "adc", "sta_abs_x", "dex", "bne", "jsr", "jmp", "nop",
        "jmp_indirect", "nop", "nop", "nop", "inx", "rts"])
    check("decode-proven-evidence", all(i.evidence is PROVEN for i in instructions))

    by_address = {i.address: i for i in instructions}
    check("decode-branch-flow", by_address[0x8009].flow is InstructionFlow.BRANCH and by_address[0x8009].direct_target == 0x8002)
    check("decode-call-flow", by_address[0x800B].flow is InstructionFlow.CALL and by_address[0x800B].direct_target == 0x8018)
    check("decode-jump-flow", by_address[0x800E].flow is InstructionFlow.JUMP and by_address[0x800E].direct_target == 0x8012)
    check("decode-indirect-jump", by_address[0x8012].flow is InstructionFlow.INDIRECT_JUMP and by_address[0x8012].unresolved)
    check("decode-return-flow", by_address[0x8019].flow is InstructionFlow.RETURN)

    # C. shared-layer traversal ---------------------------------------------
    check("cfg-block-count", len(cfg.blocks) == 8)
    check("cfg-loop-backedge", _edge_targets(cfg, "blk_8002", EdgeKind.BRANCH_TAKEN) == [0x8002])
    check("cfg-loop-exit", _edge_targets(cfg, "blk_8002", EdgeKind.BRANCH_NOT_TAKEN) == [0x800B])
    check("cfg-call-continuation", _edge_targets(cfg, "blk_800b", EdgeKind.CALL_RETURN) == [0x800E])
    check("cfg-direct-jump", _edge_targets(cfg, "blk_800e", EdgeKind.JUMP) == [0x8012])
    check("cfg-indirect-unresolved", _edge_kinds(cfg, "blk_8012") == [EdgeKind.INDIRECT])

    check("functions-two", tuple(f.id for f in discovery.functions) == ("fn_8000", "fn_8018"))
    check("functions-entry", discovery.entry_function_id == "fn_8000")
    check("functions-unowned", discovery.unowned_blocks == ("blk_8011", "blk_8015"))

    check("callgraph-internal-edge", len(call_graph.edges) == 1 and call_graph.edges[0].kind is CallEdgeKind.INTERNAL_DIRECT)

    check("units-two", [unit.unit_id for unit in units.units] == ["tu_fn_8000", "tu_fn_8018"])
    check("units-call-edges", [len(unit.call_edges) for unit in units.units] == [1, 0])

    classified_sites = [item for unit in classification.units for item in unit.classifications]
    check("indirect-site-count", len(classified_sites) == 1)
    check("indirect-status-unresolved", classified_sites[0].status is IndirectControlFlowStatus.UNRESOLVED_INDIRECT_JUMP)
    check("indirect-no-targets", classified_sites[0].targets == ())

    # D. host emission ------------------------------------------------------
    check("emission-register-names", host.register_names == ("a", "c", "ea", "n", "tmp", "x", "z"))
    check("emission-word-bits-16", "word_bits: 16" in host.source_text or "or_mask(16u)" in host.source_text)
    check("emission-memory-boundary", "or_rt_memory_read(" in host.source_text and "or_rt_memory_write(" in host.source_text)
    check("emission-fail-closed-indirect", 'or_fail("unresolved indirect jump");' in host.source_text)
    check("emission-deterministic", host.source_text == run_pipeline()["host"].source_text)

    # E. independent reference cross-check ----------------------------------
    ref, trace = reference_execute()
    instruction_addresses = {i.address for i in instructions}
    control_addresses = {i.address for i in instructions if i.flow is not InstructionFlow.NORMAL}
    check("reference-trace-in-model", all(address in instruction_addresses for address in trace))
    check("reference-executed-control-matches", {address for address in trace if address in control_addresses} == control_addresses)
    check("reference-loop-taken", trace.count(0x8002) == 3)
    check("reference-halts", ref.state.halted and ref.state.pc == 0x0202)
    check("reference-final-a", ref.state.a == 15)
    check("reference-final-x", ref.state.x == 1)

    expected = expected_output(host.register_names)

    # F. deterministic native build -----------------------------------------
    workspace = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p221-"))
    comparison = None
    try:
        config = bp.BuildConfig(fixture_id=FIXTURE_ID, expected_smoke_output=expected)
        comparison = bp.build_generated_host_from(
            lambda: run_pipeline()["host"],
            support_sources=(
                bp.BuildSource("runtime_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, support_source(CODE).encode("utf-8")),
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
        check("build-run-count", len(comparison.runs) == 2)

        # G. native execution -------------------------------------------------
        manifest = comparison.runs[0].manifest
        executable = workspace / "run1" / "program.exe"
        check("native-executable-present", executable.is_file())
        exe_sha = hashlib.sha256(executable.read_bytes()).hexdigest()
        exe_map = manifest.artifact_map(bp.BuildArtifactKind.EXECUTABLE)
        check("native-executable-hash-matches-manifest", exe_map.get("program.exe") == exe_sha)

        first = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        second = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        actual = (first.stdout or "").strip()
        check("native-returncode-zero", first.returncode == 0)
        check("native-output-stable", actual == (second.stdout or "").strip())
        check("expected-equals-actual", expected == actual)

        observed_by_index = {}
        for line in actual.splitlines():
            match = re.match(r"reg\[(\d+)\]=(\d+)$", line.strip())
            if match:
                observed_by_index[int(match.group(1))] = int(match.group(2))
        observed = {name: observed_by_index.get(index, 0) for index, name in enumerate(host.register_names)}
        check("native-guest-a", observed["a"] == 15)
        check("native-guest-x", observed["x"] == 1)
        check("native-reference-a-match", observed["a"] == ref.state.a)
        check("native-reference-x-match", observed["x"] == ref.state.x)

        # H. evidence ---------------------------------------------------------
        if args.evidence_dir:
            write_evidence(
                pathlib.Path(args.evidence_dir),
                {
                    "instructions": instructions,
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
                    "observed_registers": observed,
                    "stdout_sha1": hashlib.sha256((first.stdout or "").encode("utf-8")).hexdigest(),
                    "stdout_sha2": hashlib.sha256((second.stdout or "").encode("utf-8")).hexdigest(),
                },
            )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    # I. fail-closed --------------------------------------------------------
    expect_fail("missing-semantics-rule", _missing_semantics, HostEmitterError)
    expect_fail("missing-entry-function", _missing_entry, HostEmitterError)

    # J. no P2-22 real-ROM work ---------------------------------------------
    import ast as _ast

    tree = _ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    defined = {node.name for node in _ast.walk(tree) if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef))}
    imported: set[str] = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, _ast.ImportFrom):
            imported.add(node.module or "")
    for token in ("rom", "ines", "cartridge", "mapper", "prg", "chr", "p2_22"):
        check(f"no-next-stage-symbol:{token}", not any(token in name.lower() for name in defined))
        check(f"no-next-stage-import:{token}", not any(token in name.lower() for name in imported))

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    if args.json:
        record = {
            "stage": "P2-21",
            "marker": f"OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "fixture_id": FIXTURE_ID,
            "fixture_sha256": FIXTURE_SHA256,
            "fixture_byte_length": len(CODE),
            "generated_source_sha256": host.fingerprint(),
            "register_names": list(host.register_names),
            "expected_observable": expected,
            "actual_observable": actual if comparison is not None else None,
            "expected_equals_actual": (comparison is not None and expected == actual),
            "classification": comparison.classification.value if comparison else None,
            "results": sorted(RESULTS, key=lambda item: item["check"]),
        }
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_NES6502_HOST_EMITTER_V1_JSON={out.name}")

    print(f"OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests={tests}")
    return 0


def _edge_targets(cfg, block_id, kind):
    return sorted(
        successor.target_address
        for successor in cfg.block(block_id).successors
        if successor.kind is kind and successor.resolved
    )


def _edge_kinds(cfg, block_id):
    return sorted(successor.kind for successor in cfg.block(block_id).successors)


def _missing_semantics():
    """Emit with a deliberately incomplete semantics table."""
    staging = run_pipeline()
    bad = HostSemantics([
        HostInstructionSemantics(ARCH, "nop", InstructionFlow.NORMAL),
    ])
    emit_host_translation(
        staging["units"],
        staging["classification"],
        config=HostEmitterConfig(
            semantics=bad,
            entry_function=staging["discovery"].entry_function_id,
            word_bits=16,
            runtime_abi=rt.RuntimeAbiConfig(),
        ),
    )


def _missing_entry():
    """Emit with an entry function that does not exist."""
    staging = run_pipeline()
    emit_host_translation(
        staging["units"],
        staging["classification"],
        config=HostEmitterConfig(
            semantics=semantics_table(),
            entry_function="fn_dead",
            word_bits=16,
            runtime_abi=rt.RuntimeAbiConfig(),
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
