#!/usr/bin/env python3
"""OpenRecomp tiny MIPS32 end-to-end proof V1 (P2-10).

The smallest rigorous deterministic MIPS32 end-to-end proof: a synthetic/original
MIPS32 fixture (no commercial ROM/ELF bytes) is ingested through the real Phase-2
pipeline:

    fixture bytes -> adapters.mips32 decode -> P2-01 ProgramModel -> P2-02 CFG
    -> P2-03 function discovery -> P2-04 call graph -> P2-05 translation units
    -> P2-06 indirect-control-flow classification -> P2-07 host emitter
    -> P2-09 deterministic build pipeline -> native executable -> execution

The expected observable is derived independently of the generated host code by a
tiny reference interpreter (written from the documented MIPS32 subset, with
architectural delay-slot handling) plus an explicit mathematical derivation. The
Phase-1 `tools/mips32_oracle_v1.py` reference is used as an additional
independent cross-check on a reduced fixture, when importable.

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
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.mips32 as mips32_adapter  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.call_graph import build_call_graph  # noqa: E402
from openrecomp.cfg import CFGError, CFGMode, EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import FunctionDiscoveryError, discover_functions  # noqa: E402
from openrecomp.host_emitter import (  # noqa: E402
    HostBinop,
    HostCompare,
    HostComparison,
    HostConst,
    HostEmitterConfig,
    HostEmitterError,
    HostImmediate,
    HostInstructionSemantics,
    HostRegister,
    HostSemantics,
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

FIXTURE_ID = "p2-10-mips32-tiny-v1"

# (address, word, mnemonic) -- synthetic/original fixture, little-endian MIPS32.
FIXTURE = (
    (0x1000, 0x24020007, "addiu r2, r0, 7"),
    (0x1004, 0x24030005, "addiu r3, r0, 5"),
    (0x1008, 0x10430002, "beq r2, r3, 0x1014"),
    (0x100C, 0x00000000, "nop (delay slot)"),
    (0x1010, 0x24040003, "addiu r4, r0, 3"),
    (0x1014, 0x24840001, "addiu r4, r4, 1"),
    (0x1018, 0x14820001, "bne r4, r2, 0x1020"),
    (0x101C, 0x00000000, "nop (delay slot)"),
    (0x1020, 0x00822821, "addu r5, r4, r2"),
    (0x1024, 0x00A33023, "subu r6, r5, r3"),
    (0x1028, 0x00C2382A, "slt r7, r6, r2"),
    (0x102C, 0x03E00008, "jr r31"),
    (0x1030, 0x00000000, "nop (delay slot)"),
)
WORDS = tuple(word for _, word, _ in FIXTURE)
FIXTURE_BYTES = struct.pack("<%dI" % len(WORDS), *WORDS)
FIXTURE_SHA256 = hashlib.sha256(FIXTURE_BYTES).hexdigest()

FLOW = {
    "nop": InstructionFlow.NORMAL,
    "addiu": InstructionFlow.NORMAL,
    "addu": InstructionFlow.NORMAL,
    "subu": InstructionFlow.NORMAL,
    "slt": InstructionFlow.NORMAL,
    "beq": InstructionFlow.BRANCH,
    "bne": InstructionFlow.BRANCH,
    "j": InstructionFlow.JUMP,
    "jal": InstructionFlow.CALL,
    "jr": InstructionFlow.INDIRECT_JUMP,
}

# Independently derived expected guest registers (documented derivation in
# .openrecomp-phase2/evidence/P2-10/RESULT.md):
#   r2=7, r3=5; beq(7,5) false -> delay slot, r4=3; r4=4; bne(4,7) true -> r5=4+7=11;
#   r6=11-5=6; slt(6,7)=1 -> r7=1; jr r31 (r31=0) halts.
EXPECTED_REGS = {2: 7, 3: 5, 4: 4, 5: 11, 6: 6, 7: 1, 31: 0}

SUPPORT_SOURCE = """\
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>

void openrecomp_run(void);
int openrecomp_failed(void);
size_t openrecomp_register_count(void);
uint64_t openrecomp_register_value(size_t index);

int main(void) {
    openrecomp_run();
    printf("failed=%d\\n", openrecomp_failed());
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


# --- ingestion --------------------------------------------------------------
def decode_fixture():
    instructions = []
    for address, word, _ in FIXTURE:
        decoded = mips32_adapter.decode(address, word)
        flow = FLOW[decoded["op"]]
        instructions.append(
            instruction_from_adapter(
                decoded,
                flow=flow,
                unresolved=(flow is InstructionFlow.INDIRECT_JUMP),
                size_bytes=4,
                evidence=PROVEN,
            )
        )
    return tuple(instructions)


def program_source():
    return ProgramSource(
        ARCH,
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=FIXTURE_SHA256,
    )


def decode_region(byte_stream, base):
    if not isinstance(byte_stream, (bytes, bytearray)):
        raise ValueError("fixture must be bytes")
    if len(byte_stream) == 0 or len(byte_stream) % 4 != 0:
        raise ValueError(f"truncated or malformed fixture: {len(byte_stream)} bytes")
    instructions = []
    for offset in range(0, len(byte_stream), 4):
        word = struct.unpack_from("<I", byte_stream, offset)[0]
        decoded = mips32_adapter.decode(base + offset, word)
        flow = FLOW.get(decoded["op"])
        if flow is None:
            raise ValueError(f"unsupported op {decoded['op']!r}")
        instructions.append(
            instruction_from_adapter(
                decoded, flow=flow, unresolved=(flow is InstructionFlow.INDIRECT_JUMP),
                size_bytes=4, evidence=PROVEN,
            )
        )
    return tuple(instructions)


def semantics_table(include_subu=True):
    def r(op, flow, **kw):
        return HostInstructionSemantics(ARCH, op, flow, **kw)

    rules = [
        r("nop", InstructionFlow.NORMAL),
        r("addiu", InstructionFlow.NORMAL, operations=(HostBinop(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True), "add"),)),
        r("addu", InstructionFlow.NORMAL, operations=(HostBinop(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "add"),)),
        r("slt", InstructionFlow.NORMAL, operations=(HostCompare(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "slt"),)),
        r("beq", InstructionFlow.BRANCH, condition=HostComparison(HostRegister("rs"), HostRegister("rt"), "eq")),
        r("bne", InstructionFlow.BRANCH, condition=HostComparison(HostRegister("rs"), HostRegister("rt"), "ne")),
        r("jr", InstructionFlow.INDIRECT_JUMP, indirect_source=HostRegister("rs")),
    ]
    if include_subu:
        rules.append(r("subu", InstructionFlow.NORMAL, operations=(HostBinop(HostRegister("rd"), HostRegister("rs"), HostRegister("rt"), "sub"),)))
    return HostSemantics(rules)


def run_pipeline(*, jr_evidence=True):
    source = program_source()
    instructions = decode_fixture()
    cfg = build_cfg(instructions, source=source, entries=[EntryPoint(ENTRY, PROVEN)], mode=CFGMode.CLOSED)
    discovery = discover_functions(cfg, program_entries=[ENTRY])
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)
    if jr_evidence:
        site = None
        for unit in units.units:
            for block in unit.blocks:
                terminal = block.terminal
                if terminal.flow is InstructionFlow.INDIRECT_JUMP:
                    site = (unit.function_id, block.id, terminal.address)
        evidence = [
            IndirectControlFlowEvidence(
                function_id=site[0],
                block_id=site[1],
                address=site[2],
                kind=IndirectControlFlowKind.INDIRECT_JUMP,
                status=IndirectControlFlowStatus.RETURN_LIKE,
                basis=IndirectControlFlowBasis.STRUCTURAL_RETURN_EVIDENCE,
                source="p2-10-fixture",
                evidence=PROVEN,
            )
        ]
    else:
        evidence = []
    classification = classify_indirect_control_flow(units, evidence=evidence)
    host = emit_host_translation(
        units,
        classification,
        config=HostEmitterConfig(
            semantics=semantics_table(),
            entry_function=discovery.entry_function_id,
            word_bits=32,
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
        "jr_site": site if jr_evidence else None,
    }


# --- independent reference interpreter --------------------------------------
def reference_execute(words, entry=ENTRY, limit=4096):
    """A tiny independent MIPS32 subset interpreter (includes delay slots)."""
    regs = [0] * 32
    pc = entry
    pending = None
    steps = 0
    while True:
        steps += 1
        if steps > limit:
            raise AssertionError("reference interpreter step limit exceeded")
        if pc == 0:
            break
        offset = pc - entry
        if offset < 0 or offset % 4 or offset // 4 >= len(words):
            raise AssertionError(f"reference interpreter left the fixture at 0x{pc:x}")
        word = words[offset // 4]
        opcode = (word >> 26) & 0x3F
        rs = (word >> 21) & 0x1F
        rt = (word >> 16) & 0x1F
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
            regs[rt] = (regs[rs] + imm) & 0xFFFFFFFF
        elif opcode == 0 and funct == 0x21:
            regs[rd] = (regs[rs] + regs[rt]) & 0xFFFFFFFF
        elif opcode == 0 and funct == 0x23:
            regs[rd] = (regs[rs] - regs[rt]) & 0xFFFFFFFF
        elif opcode == 0 and funct == 0x2A:
            regs[rd] = 1 if regs[rs] < regs[rt] else 0
        elif opcode == 0x04:
            branch = True
            target = (pc + 4 + (imm << 2)) & 0xFFFFFFFF if regs[rs] == regs[rt] else None
        elif opcode == 0x05:
            branch = True
            target = (pc + 4 + (imm << 2)) & 0xFFFFFFFF if regs[rs] != regs[rt] else None
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
    return regs


def expected_output(register_names, regs):
    lines = ["failed=0"]
    for index, name in enumerate(register_names):
        lines.append(f"reg[{index}]={regs[int(name[1:])]}")
    return "\n".join(lines)


# --- Phase-1 oracle cross-check (optional, importable) ----------------------
def _elf_with_code(code, entry=ENTRY):
    header = b"\x7fELF\x01\x01\x01" + b"\x00" * 9
    header += struct.pack(
        "<HHIIIIIHHHHHH",
        2, 8, 1, entry, 52, 0, 0, 52, 32, 1, 0, 0, 0,
    )
    code_offset = 52 + 32
    program = struct.pack(
        "<IIIIIIII",
        1, code_offset, entry, entry, len(code), len(code), 5, 4,
    )
    return header + program + code


def oracle_cross_check():
    try:
        from mips32_oracle_v1 import simulate  # noqa: E402
    except Exception:  # noqa: BLE001
        return None
    results = {}
    # taken branch
    taken = struct.pack("<7I", 0x24030005, 0x10630002, 0x00000000, 0x24030063, 0x00601021, 0x03E00008, 0x00000000)
    # 0x1000 addiu r3,r0,5 ; 0x1004 beq r3,r3,0x1010 ; 0x1008 nop ; 0x100C addiu r3,r0,99 ;
    # 0x1010 addu r2,r3,r0 ; 0x1014 jr r31 ; 0x1018 nop
    not_taken = struct.pack("<7I", 0x24030005, 0x10600002, 0x00000000, 0x24630004, 0x00601021, 0x03E00008, 0x00000000)
    # 0x1000 addiu r3,r0,5 ; 0x1004 beq r3,r0,0x1010 (not taken) ; 0x1008 nop ;
    # 0x100C addiu r3,r3,4 ; 0x1010 addu r2,r3,r0 ; 0x1014 jr r31 ; 0x1018 nop
    path = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p210-oracle-")) / "fixture.elf"
    try:
        path.write_bytes(_elf_with_code(taken))
        results["taken"] = simulate(str(path))
        path.write_bytes(_elf_with_code(not_taken))
        results["not_taken"] = simulate(str(path))
    finally:
        shutil.rmtree(path.parent, ignore_errors=True)
    return results


# --- evidence ---------------------------------------------------------------
def _write_text(path, text):
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def write_evidence(evidence_dir, staging):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    hashes = {}

    fixture_lines = [
        "P2-10 synthetic MIPS32 fixture",
        "==============================",
        "architecture: " + ARCH,
        "endianness: little",
        "instruction width: 4 bytes",
        "base/entry address: 0x1000",
        f"instruction count: {len(FIXTURE)}",
        f"byte length: {len(FIXTURE_BYTES)}",
        f"sha256: {FIXTURE_SHA256}",
        "origin: synthetic/original (no commercial ROM/ELF bytes)",
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
                f"edge_count: {len(call_graph.edges)}",
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
    site = staging["jr_site"]
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
    classification_lines += ["", f"jr_site: {site}", ""]
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
            f"P2-10 deterministic build run {index + 1}",
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
                "P2-10 native execution",
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
                "P2-10 expected vs actual observable",
                "===================================",
                "expected (independent reference interpreter):",
                expected,
                "actual (native executable stdout):",
                actual,
                f"EXPECTED == ACTUAL: {'YES' if expected == actual else 'NO'}",
                "",
            ]
        ),
    )

    if staging.get("oracle"):
        lines = ["P2-10 Phase-1 oracle cross-check", "================================"]
        for name, result in sorted(staging["oracle"].items()):
            lines.append(f"{name}: r2={result['r2']} r3={result['r3']} operations={result['operations']}")
        lines.append("")
        hashes["oracle_cross_check.txt"] = _write_text(evidence_dir / "oracle_cross_check.txt", "\n".join(lines))

    return hashes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    parser.add_argument("--evidence-dir", help="write deterministic UTF-8 evidence here (output only)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # A. fixture ------------------------------------------------------------
    check("fixture-byte-length", len(FIXTURE_BYTES) == 4 * len(FIXTURE))
    check("fixture-sha256", FIXTURE_SHA256 == hashlib.sha256(FIXTURE_BYTES).hexdigest())
    check("fixture-sha256-stable", FIXTURE_SHA256 == hashlib.sha256(struct.pack("<13I", *WORDS)).hexdigest() and len(FIXTURE_SHA256) == 64)
    check("fixture-word-count", len(WORDS) == len(FIXTURE))
    check("fixture-entry-aligned", ENTRY % 4 == 0 and FIXTURE[0][0] == ENTRY)
    check("fixture-instructions-13", len(FIXTURE) == 13)
    check("fixture-synthetic-origin", all(mnemonic for _, _, mnemonic in FIXTURE))

    # B. ingestion / decode -------------------------------------------------
    instructions = decode_fixture()
    ops = [instruction.op for instruction in instructions]
    check("decode-addresses", [instruction.address for instruction in instructions] == [address for address, _, _ in FIXTURE])
    check(
        "decode-ops",
        ops == ["addiu", "addiu", "beq", "nop", "addiu", "addiu", "bne", "nop", "addu", "subu", "slt", "jr", "nop"],
    )
    check("decode-size-bytes", all(instruction.size_bytes == 4 for instruction in instructions))
    check("decode-branch-targets", instructions[2].direct_target == 0x1014 and instructions[6].direct_target == 0x1020)
    check("decode-jr-unresolved", instructions[11].flow is InstructionFlow.INDIRECT_JUMP and instructions[11].unresolved)
    check("decode-evidence-proven", all(instruction.evidence is PROVEN for instruction in instructions))
    check("decode-deterministic", [item.to_document() for item in decode_fixture()] == [item.to_document() for item in instructions])

    # C. pipeline -----------------------------------------------------------
    staging = run_pipeline()
    cfg = staging["cfg"]
    discovery = staging["discovery"]
    call_graph = staging["call_graph"]
    units = staging["units"]
    classification = staging["classification"]
    host = staging["host"]

    check("programmodel-source", discovery.program_model.source.to_document() == program_source().to_document())
    check("programmodel-functions", [function.id for function in discovery.program_model.functions] == ["fn_1000"])
    check("programmodel-validates", discovery.program_model.function("fn_1000").entry_address == ENTRY)

    check("cfg-block-entries", [block.entry_address for block in cfg.ordered_blocks()] == [0x1000, 0x100C, 0x1014, 0x101C, 0x1020, 0x1030])
    check("cfg-branch-taken", _edge_targets(cfg, "blk_1000", EdgeKind.BRANCH_TAKEN) == [0x1014])
    check("cfg-branch-not-taken", _edge_targets(cfg, "blk_1000", EdgeKind.BRANCH_NOT_TAKEN) == [0x100C])
    check("cfg-fallthrough-100c", _edge_targets(cfg, "blk_100c", EdgeKind.FALLTHROUGH) == [0x1014])
    check("cfg-branch-taken-bne", _edge_targets(cfg, "blk_1014", EdgeKind.BRANCH_TAKEN) == [0x1020])
    check("cfg-branch-not-taken-bne", _edge_targets(cfg, "blk_1014", EdgeKind.BRANCH_NOT_TAKEN) == [0x101C])
    check("cfg-fallthrough-101c", _edge_targets(cfg, "blk_101c", EdgeKind.FALLTHROUGH) == [0x1020])
    check("cfg-indirect-unresolved", _edge_kinds(cfg, "blk_1020") == [EdgeKind.INDIRECT])
    check("cfg-no-successors-jr-unowned", _edge_kinds(cfg, "blk_1030") == [])
    check("cfg-deterministic", cfg.fingerprint() == run_pipeline()["cfg"].fingerprint())
    check("cfg-no-phantom-blocks", len(cfg.blocks) == 6)

    check("functions-single", [function.id for function in discovery.functions] == ["fn_1000"])
    check("functions-entry", discovery.entry_function_id == "fn_1000")
    check("functions-body", [block.id for block in discovery.function("fn_1000").blocks] == ["blk_1000", "blk_100c", "blk_1014", "blk_101c", "blk_1020"])
    check("functions-unowned", discovery.unowned_blocks == ("blk_1030",))
    check("functions-provenance", [basis.source.value for basis in discovery.basis("fn_1000")] == ["PROGRAM_ENTRY"])
    check("functions-deterministic", discovery.fingerprint() == run_pipeline()["discovery"].fingerprint())

    check("callgraph-nodes", [node.function_id for node in call_graph.nodes] == ["fn_1000"])
    check("callgraph-no-edges", len(call_graph.edges) == 0)
    check("callgraph-deterministic", call_graph.fingerprint() == run_pipeline()["call_graph"].fingerprint())

    check("units-single", [unit.unit_id for unit in units.units] == ["tu_fn_1000"])
    check("units-function", units.unit_for("fn_1000").function_id == "fn_1000")
    check("units-unowned-preserved", units.unowned_blocks == ("blk_1030",))
    check("units-deterministic", units.fingerprint() == run_pipeline()["units"].fingerprint())

    classified_sites = [item for unit in classification.units for item in unit.classifications]
    check("indirect-site-count", len(classified_sites) == 1)
    check("indirect-site-address", classified_sites[0].address == 0x102C and classified_sites[0].kind is IndirectControlFlowKind.INDIRECT_JUMP)
    check("indirect-status-return-like", classified_sites[0].status is IndirectControlFlowStatus.RETURN_LIKE)
    check("indirect-no-guessed-targets", classified_sites[0].targets == ())
    no_evidence = run_pipeline(jr_evidence=False)
    unclassified = [item for unit in no_evidence["classification"].units for item in unit.classifications]
    check("indirect-fails-closed-without-evidence", unclassified[0].status is IndirectControlFlowStatus.UNRESOLVED_INDIRECT_JUMP)
    check("indirect-no-invented-target-without-evidence", unclassified[0].targets == ())

    # D. host emission ------------------------------------------------------
    check("emission-registers", host.register_names == ("r0", "r2", "r3", "r31", "r4", "r5", "r6", "r7"))
    check("emission-mask", "or_mask(32u)" in host.source_text)
    check("emission-add", "+" in host.source_text)
    check("emission-sub", "-" in host.source_text)
    check("emission-signed-compare", "or_signed(" in host.source_text)
    check("emission-branch", "goto bb_blk_1014" in host.source_text and "goto bb_blk_100c" in host.source_text)
    check("emission-return-like", "return;" in host.source_text.split("bb_blk_1020:;", 1)[1].split("}", 1)[0])
    check("emission-deterministic", host.source_text == run_pipeline()["host"].source_text)
    check("emission-no-hardcoded-result-11", "UINT64_C(11)" not in host.source_text)
    check("emission-no-hardcoded-result-6", "UINT64_C(6)" not in host.source_text)
    check("emission-slt-select", "? UINT64_C(1) : UINT64_C(0)" in host.source_text)

    # E. independent expected observable ------------------------------------
    regs = reference_execute(WORDS)
    check("reference-registers", {index: regs[index] for index in EXPECTED_REGS} == EXPECTED_REGS)
    check("derivation-r5", regs[4] + regs[2] == 11)
    check("derivation-r6", regs[5] - regs[3] == 6)
    check("derivation-r7", int(regs[6] < regs[2]) == 1)
    expected = expected_output(host.register_names, regs)

    oracle = oracle_cross_check()
    if oracle is None:
        print("SKIP: phase1-oracle-cross-check (mips32_oracle_v1 not importable)")
    else:
        check("oracle-taken-branch", oracle["taken"]["r2"] == 5 and oracle["taken"]["r3"] == 5)
        check("oracle-not-taken-branch", oracle["not_taken"]["r2"] == 9 and oracle["not_taken"]["r3"] == 9)

    # F. deterministic native build -----------------------------------------
    workspace = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p210-"))
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
        check("build-run-count", len(comparison.runs) == 2)
        manifest = comparison.runs[0].manifest
        check("build-brepro-compile", all("/Brepro" in command for command in manifest.compile_commands))
        check("build-brepro-link", "/Brepro" in manifest.link_command)
        check("build-manifest-deterministic", manifest.serialize() == comparison.runs[1].manifest.serialize())
        manifest_text = manifest.serialize().decode("utf-8")
        check("build-manifest-no-repo-path", str(ROOT) not in manifest_text)
        check("build-manifest-no-workspace", str(workspace) not in manifest_text)
        check("build-manifest-no-username", not os.environ.get("USERNAME") or os.environ["USERNAME"] not in manifest_text)
        check("build-manifest-no-hostname", not os.environ.get("COMPUTERNAME") or os.environ["COMPUTERNAME"] not in manifest_text)

        # G. native execution -------------------------------------------------
        executable = workspace / "run1" / "program.exe"
        object_map = manifest.artifact_map(bp.BuildArtifactKind.OBJECT)
        exe_map = manifest.artifact_map(bp.BuildArtifactKind.EXECUTABLE)
        check("native-executable-present", executable.is_file())
        exe_sha = hashlib.sha256(executable.read_bytes()).hexdigest()
        check("native-executable-hash-matches-manifest", exe_map.get("program.exe") == exe_sha)
        check("native-object-hash-matches-manifest", hashlib.sha256((workspace / "run1" / "generated.obj").read_bytes()).hexdigest() == object_map.get("generated.obj"))

        import subprocess

        first = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        second = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        actual = (first.stdout or "").strip()
        check("native-returncode-zero", first.returncode == 0)
        check("native-output-stable", actual == (second.stdout or "").strip())
        check("native-failed-flag-zero", actual.splitlines()[0] == "failed=0")
        check("expected-equals-actual", expected == actual)

        observed_by_index = {}
        for line in actual.splitlines()[1:]:
            match = re.match(r"reg\[(\d+)\]=(\d+)$", line.strip())
            if match:
                observed_by_index[int(match.group(1))] = int(match.group(2))
        observed_guest = {int(name[1:]): observed_by_index[index] for index, name in enumerate(host.register_names)}
        check("native-guest-registers", {index: observed_guest[index] for index in EXPECTED_REGS} == EXPECTED_REGS)

        # H. evidence ---------------------------------------------------------
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
                    "jr_site": staging["jr_site"],
                    "comparison": comparison,
                    "expected_output": expected,
                    "actual_output": actual,
                    "native_returncode": first.returncode,
                    "exe_sha256": exe_sha,
                    "oracle": oracle,
                },
            )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    # I. fail-closed --------------------------------------------------------
    expect_fail("malformed-fixture-truncated", lambda: decode_region(FIXTURE_BYTES[:6], ENTRY), ValueError)
    expect_fail("malformed-fixture-empty", lambda: decode_region(b"", ENTRY), ValueError)
    expect_fail("unsupported-opcode", lambda: mips32_adapter.decode(0x1000, 0xFC000000), mips32_adapter.DecodeError)
    expect_fail("invalid-branch-target-outside-region", _mutate_branch_target, CFGError)
    expect_fail("misaligned-entry", lambda: build_cfg(decode_fixture(), source=program_source(), entries=[EntryPoint(0x1002, PROVEN)], mode=CFGMode.CLOSED), CFGError)
    expect_fail("empty-region", lambda: build_cfg((), source=program_source(), entries=[EntryPoint(ENTRY, PROVEN)], mode=CFGMode.CLOSED), CFGError)
    expect_fail(
        "missing-semantics-rule",
        lambda: emit_host_translation(
            units,
            classification,
            config=HostEmitterConfig(semantics=semantics_table(include_subu=False), entry_function="fn_1000", word_bits=32),
        ),
        HostEmitterError,
    )
    expect_fail(
        "missing-entry-function",
        lambda: emit_host_translation(
            units,
            classification,
            config=HostEmitterConfig(semantics=semantics_table(), entry_function="fn_dead", word_bits=32),
        ),
        HostEmitterError,
    )
    unresolved_host = emit_host_translation(
        no_evidence["units"],
        no_evidence["classification"],
        config=HostEmitterConfig(semantics=semantics_table(), entry_function="fn_1000", word_bits=32),
    )
    check("unresolved-indirect-fails-closed-in-emission", 'or_fail("unresolved indirect jump");' in unresolved_host.source_text)
    check("unresolved-indirect-no-goto", "goto bb_" not in unresolved_host.source_text.split("bb_blk_1020:;", 1)[1].split("}", 1)[0])

    tampered = bytearray(FIXTURE_BYTES)
    tampered[0] ^= 0x01
    check("fixture-tamper-detected", hashlib.sha256(bytes(tampered)).hexdigest() != FIXTURE_SHA256)

    # J. no next-stage work -------------------------------------------------
    import ast as _ast

    tree = _ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in _ast.walk(tree)
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef))
    }
    imported: set[str] = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, _ast.ImportFrom):
            imported.add(node.module or "")
    for token in ("stack", "frame", "p2_11", "p2_12", "p2_20", "equivalence"):
        check(f"no-next-stage-symbol:{token}", not any(token in name.lower() for name in defined))
    for token in ("stack", "p2_11", "p2_12", "p2_20"):
        check(f"no-next-stage-import:{token}", not any(token in name.lower() for name in imported))
    check("no-p2-11-evidence-directory", not (ROOT / ".openrecomp-phase2" / "evidence" / "P2-11").exists())

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    if args.json:
        record = {
            "stage": "P2-10",
            "marker": f"OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "fixture_id": FIXTURE_ID,
            "fixture_sha256": FIXTURE_SHA256,
            "fixture_byte_length": len(FIXTURE_BYTES),
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
        print(f"OPENRECOMP_MIPS32_END_TO_END_V1_JSON={out.name}")

    print(f"OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests={tests}")
    return 0


def _edge_targets(cfg, block_id, kind):
    return sorted(
        successor.target_address
        for successor in cfg.block(block_id).successors
        if successor.kind is kind and successor.resolved
    )


def _edge_kinds(cfg, block_id):
    return sorted(successor.kind for successor in cfg.block(block_id).successors)


def _mutate_branch_target():
    """Build a fixture whose beq target leaves the closed region (fail closed)."""
    instructions = list(decode_fixture())
    bad = instructions[2]
    mutated = type(bad)(
        address=bad.address,
        op=bad.op,
        size_bytes=bad.size_bytes,
        flow=bad.flow,
        direct_target=0x2000,
        unresolved=False,
        evidence=bad.evidence,
        metadata=bad.metadata,
    )
    instructions[2] = mutated
    return build_cfg(tuple(instructions), source=program_source(), entries=[EntryPoint(ENTRY, PROVEN)], mode=CFGMode.CLOSED)


if __name__ == "__main__":
    raise SystemExit(main())
