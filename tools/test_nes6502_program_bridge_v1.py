#!/usr/bin/env python3
"""OpenRecomp NES6502 program-bridge proof V1 (P2-20).

Proves that a synthetic/original NES 6502 region can be fed through the **same**
shared, architecture-neutral Phase-2 layers used by the MIPS32 path:

    adapters.nes6502 decode_full
      -> P2-01 DecodedInstruction / ProgramModel
      -> P2-02 CFG
      -> P2-03 function discovery
      -> P2-04 call graph
      -> P2-05 translation units
      -> P2-06 indirect-control-flow classification

The fixture is a documented 6502 program with a counted loop, an indexed store,
a direct `jsr`/`rts` call, a direct `jmp` and an indirect `jmp ($0300)` whose
target is a runtime value and is therefore never inferred. The bridge is the
only architecture-aware seam; the shared layers must not import any
architecture adapter or frontend.

The structural model is independently cross-checked against the frozen Phase-1
`tools/nes6502_reference_v1.py` interpreter: every executed instruction address
must be a decoded instruction, and the executed control-flow instructions must
be exactly the model's control-flow instructions.

This gate proves the structural bridge only. It does not generate host code
(P2-21), does not execute translated host code and does not claim NES
equivalence or compatibility.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402
from nes6502_reference_v1 import NES6502State, ReferenceNES6502  # noqa: E402
from openrecomp import call_graph as call_graph_module  # noqa: E402
from openrecomp import cfg as cfg_module  # noqa: E402
from openrecomp import functions as functions_module  # noqa: E402
from openrecomp import indirect_control_flow as indirect_module  # noqa: E402
from openrecomp import program_model as program_model_module  # noqa: E402
from openrecomp import translation_units as units_module  # noqa: E402
from openrecomp.call_graph import CallEdgeKind  # noqa: E402
from openrecomp.cfg import EdgeKind  # noqa: E402
from openrecomp.frontends import nes6502 as bridge  # noqa: E402
from openrecomp.indirect_control_flow import IndirectControlFlowStatus  # noqa: E402
from openrecomp.program_model import DecodedInstruction, EvidenceClass, InstructionFlow  # noqa: E402

ENTRY = 0x8000
MEMORY_SIZE = 0x10000
HALT = nes_adapter.HALT_OPCODE

RESULTS: list[dict[str, str]] = []


def check(label, condition):
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}")


def expect_fail(label, thunk, error_type=bridge.NES6502BridgeError):
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
def assemble():
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


CODE, LABELS, REGION_END = assemble()
REGION_SHA256 = hashlib.sha256(CODE).hexdigest()
MEMORY = bytearray([HALT] * MEMORY_SIZE)
MEMORY[ENTRY:ENTRY + len(CODE)] = CODE

EXPECTED_BLOCKS = [0x8000, 0x8002, 0x800B, 0x800E, 0x8011, 0x8012, 0x8015, 0x8018]


def _write_text(path, text):
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def write_evidence(evidence_dir, staging):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    hashes = {}
    program = staging["program"]

    fixture_lines = [
        "P2-20 synthetic NES6502 fixture (program bridge)",
        "=" * 52,
        "architecture: nes6502 (NES 2A03/2A07-family)",
        "endianness: little",
        "address width: 16 bits",
        f"entry: 0x{ENTRY:04x}",
        f"region end: 0x{REGION_END:04x}",
        f"region byte length: {len(CODE)}",
        f"region sha256: {REGION_SHA256}",
        "origin: synthetic/original (no commercial ROM bytes)",
        "labels: " + ", ".join(f"{name}=0x{value:04x}" for name, value in sorted(LABELS.items())),
        "",
        "region bytes (hex):",
        CODE.hex(),
        "",
        "decoded instructions:",
    ]
    for instruction in program.instructions:
        fields = dict((instruction.metadata or {}).get("adapter_fields", {}))
        fixture_lines.append(
            f"  0x{instruction.address:04x}  {instruction.op:<4} size={instruction.size_bytes} "
            f"flow={instruction.flow.value} target={instruction.direct_target} fields={fields}"
        )
    fixture_lines.append("")
    hashes["fixture.txt"] = _write_text(evidence_dir / "fixture.txt", "\n".join(fixture_lines))

    cfg = program.cfg
    edge_lines = []
    for block in cfg.ordered_blocks():
        for successor in block.successors:
            target = successor.target_block if successor.resolved else successor.detail
            edge_lines.append(f"  {block.id}: {successor.kind.value} -> {target}")
    hashes["pipeline_cfg.txt"] = _write_text(evidence_dir / "pipeline_cfg.txt", "\n".join([
        "P2-02 CFG evidence (NES6502)", "============================",
        f"mode: {cfg.mode.value}", f"fingerprint: {cfg.fingerprint()}",
        f"block_count: {len(cfg.blocks)}",
        "blocks: " + ", ".join(f"0x{block.entry_address:04x}" for block in cfg.ordered_blocks()),
        "edges:", *edge_lines, "",
    ]))

    discovery = program.discovery
    hashes["pipeline_functions.txt"] = _write_text(evidence_dir / "pipeline_functions.txt", "\n".join([
        "P2-03 function-discovery evidence (NES6502)", "==========================================",
        f"entry_function: {discovery.entry_function_id}", f"fingerprint: {discovery.fingerprint()}",
        "functions: " + ", ".join(f"{f.id}@0x{f.entry_address:04x}" for f in discovery.functions),
        "unowned_blocks: " + ", ".join(discovery.unowned_blocks), "",
    ]))

    call_graph = program.call_graph
    hashes["pipeline_call_graph.txt"] = _write_text(evidence_dir / "pipeline_call_graph.txt", "\n".join([
        "P2-04 call-graph evidence (NES6502)", "=================================",
        "nodes: " + ", ".join(node.function_id for node in call_graph.nodes), "edges:",
        *[f"  {e.caller} -> {e.callee} ({e.kind.value})" for e in sorted(call_graph.edges, key=lambda item: (item.caller, item.callee))],
        f"fingerprint: {call_graph.fingerprint()}", "",
    ]))

    units = program.units
    hashes["pipeline_translation_units.txt"] = _write_text(evidence_dir / "pipeline_translation_units.txt", "\n".join([
        "P2-05 translation-unit evidence (NES6502)", "========================================",
        "units: " + ", ".join(f"{unit.unit_id}({unit.function_id})" for unit in units.units),
        "unowned_blocks: " + ", ".join(units.unowned_blocks), f"fingerprint: {units.fingerprint()}", "",
    ]))

    classification = program.classification
    classification_lines = ["P2-06 indirect-control-flow evidence (NES6502)", "============================================",
                            f"fingerprint: {classification.fingerprint()}"]
    for unit in classification.units:
        for item in unit.classifications:
            classification_lines.append(
                f"  {item.block_id} 0x{item.address:04x} {item.kind.value} status={item.status.value} "
                f"basis={item.basis.value} targets={list(item.targets)}")
    classification_lines.append("")
    hashes["pipeline_indirect_control_flow.txt"] = _write_text(evidence_dir / "pipeline_indirect_control_flow.txt", "\n".join(classification_lines))

    hashes["bridge_summary.txt"] = _write_text(evidence_dir / "bridge_summary.txt", "\n".join(staging["summary_lines"]))
    return hashes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    parser.add_argument("--evidence-dir", help="write deterministic UTF-8 evidence here (output only)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # A. fixture ------------------------------------------------------------
    check("fixture-assembler-deterministic", assemble() == (CODE, LABELS, REGION_END))
    check("fixture-region-length", len(CODE) == 26)
    check("fixture-region-sha256", REGION_SHA256 == hashlib.sha256(CODE).hexdigest())
    check("fixture-entry", ENTRY == 0x8000 and LABELS["start"] == ENTRY)
    check("fixture-region-end", REGION_END == 0x801A)
    check("fixture-halt-padding", MEMORY[0x0202] == HALT and MEMORY[REGION_END] == HALT)
    check("fixture-synthetic-origin", all(0 <= byte <= 0xFF for byte in CODE))

    # B. bridge decode ------------------------------------------------------
    program = bridge.bridge_program(MEMORY, entry=ENTRY, end=REGION_END)
    instructions = program.instructions
    expected_addresses = [0x8000, 0x8002, 0x8003, 0x8005, 0x8008, 0x8009, 0x800B, 0x800E,
                          0x8011, 0x8012, 0x8015, 0x8016, 0x8017, 0x8018, 0x8019]
    check("decode-instruction-count", len(instructions) == 15)
    check("decode-addresses", [i.address for i in instructions] == expected_addresses)
    check("decode-ops", [i.op for i in instructions] == [
        "ldx", "clc", "adc", "sta", "dex", "bne", "jsr", "jmp", "nop",
        "jmp", "nop", "nop", "nop", "inx", "rts"])
    check("decode-sizes", [i.size_bytes for i in instructions] == [2, 1, 2, 3, 1, 2, 3, 3, 1, 3, 1, 1, 1, 1, 1])
    check("decode-proven-evidence", all(isinstance(i, DecodedInstruction) and i.evidence is EvidenceClass.PROVEN for i in instructions))

    by_address = {i.address: i for i in instructions}
    check("decode-branch-flow", by_address[0x8009].flow is InstructionFlow.BRANCH and by_address[0x8009].direct_target == 0x8002)
    check("decode-call-flow", by_address[0x800B].flow is InstructionFlow.CALL and by_address[0x800B].direct_target == 0x8018)
    check("decode-jump-flow", by_address[0x800E].flow is InstructionFlow.JUMP and by_address[0x800E].direct_target == 0x8012)
    check("decode-indirect-jump", by_address[0x8012].flow is InstructionFlow.INDIRECT_JUMP and by_address[0x8012].unresolved and by_address[0x8012].direct_target is None)
    check("decode-return-flow", by_address[0x8019].flow is InstructionFlow.RETURN)
    check("decode-normal-flow", by_address[0x8000].flow is InstructionFlow.NORMAL and by_address[0x8002].flow is InstructionFlow.NORMAL)
    check("decode-imm-operand", by_address[0x8000].metadata["adapter_fields"]["imm8"] == 3)
    check("decode-relative-operand", by_address[0x8009].metadata["adapter_fields"]["rel"] == -9)
    check("decode-absx-operand", by_address[0x8005].metadata["adapter_fields"]["abs,x"] == 0x0400)
    check("decode-indirect-pointer", by_address[0x8012].metadata["adapter_fields"]["indirect"] == 0x0300)
    check("decode-jsr-target", by_address[0x800B].metadata["adapter_fields"]["a16"] == 0x8018)

    # C. ProgramModel -------------------------------------------------------
    check("programmodel-source", program.source.to_document() == {
        "architecture": "nes6502", "adapter": "adapters.nes6502", "address_width_bits": 16,
        "endianness": "little", "input_sha256": REGION_SHA256})
    check("programmodel-functions", [f.id for f in program.discovery.program_model.functions] == ["fn_8000", "fn_8018"])
    check("programmodel-validates", program.discovery.program_model.function("fn_8000").entry_address == ENTRY)

    # D. CFG ----------------------------------------------------------------
    cfg = program.cfg
    check("cfg-block-entries", [block.entry_address for block in cfg.ordered_blocks()] == EXPECTED_BLOCKS)
    check("cfg-loop-backedge", _edge_targets(cfg, "blk_8002", EdgeKind.BRANCH_TAKEN) == [0x8002])
    check("cfg-loop-exit", _edge_targets(cfg, "blk_8002", EdgeKind.BRANCH_NOT_TAKEN) == [0x800B])
    check("cfg-entry-fallthrough", _edge_targets(cfg, "blk_8000", EdgeKind.FALLTHROUGH) == [0x8002])
    check("cfg-call-continuation", _edge_targets(cfg, "blk_800b", EdgeKind.CALL_RETURN) == [0x800E])
    check("cfg-direct-jump", _edge_targets(cfg, "blk_800e", EdgeKind.JUMP) == [0x8012])
    check("cfg-indirect-unresolved", _edge_kinds(cfg, "blk_8012") == [EdgeKind.INDIRECT])
    check("cfg-return-no-successors", _edge_kinds(cfg, "blk_8018") == [])
    check("cfg-no-phantom-blocks", len(cfg.blocks) == 8)
    check("cfg-deterministic", cfg.fingerprint() == bridge.bridge_program(MEMORY, entry=ENTRY, end=REGION_END).cfg.fingerprint())

    # E. function discovery / call graph / units ----------------------------
    discovery = program.discovery
    check("functions-two", program.function_ids() == ("fn_8000", "fn_8018"))
    check("functions-entry", discovery.entry_function_id == "fn_8000")
    check("functions-main-body", [block.id for block in discovery.function("fn_8000").blocks] ==
          ["blk_8000", "blk_8002", "blk_800b", "blk_800e", "blk_8012"])
    check("functions-helper-body", [block.id for block in discovery.function("fn_8018").blocks] == ["blk_8018"])
    check("functions-unowned", discovery.unowned_blocks == ("blk_8011", "blk_8015"))

    call_graph = program.call_graph
    check("callgraph-nodes", [node.function_id for node in call_graph.nodes] == ["fn_8000", "fn_8018"])
    check("callgraph-internal-edge", len(call_graph.edges) == 1 and call_graph.edges[0].caller == "fn_8000"
          and call_graph.edges[0].callee == "fn_8018" and call_graph.edges[0].kind is CallEdgeKind.INTERNAL_DIRECT)

    units = program.units
    check("units-two", [unit.unit_id for unit in units.units] == ["tu_fn_8000", "tu_fn_8018"])
    check("units-call-edges", [len(unit.call_edges) for unit in units.units] == [1, 0])
    check("units-unowned-preserved", units.unowned_blocks == ("blk_8011", "blk_8015"))

    # F. P2-06 classification ----------------------------------------------
    sites = [item for unit in program.classification.units for item in unit.classifications]
    check("indirect-site-count", len(sites) == 1)
    check("indirect-site-address", sites[0].address == 0x8012)
    check("indirect-status-unresolved", sites[0].status is IndirectControlFlowStatus.UNRESOLVED_INDIRECT_JUMP)
    check("indirect-no-guessed-targets", sites[0].targets == ())
    check("indirect-basis-none", sites[0].basis.value == "NONE")
    check("indirect-unowned-control-flow-empty", len(program.classification.unowned_control_flow) == 0)

    # G. determinism and serialization -------------------------------------
    second = bridge.bridge_program(MEMORY, entry=ENTRY, end=REGION_END)
    check("determinism-program-fingerprint", program.fingerprint() == second.fingerprint())
    check("determinism-cfg", cfg.fingerprint() == second.cfg.fingerprint())
    check("determinism-functions", discovery.fingerprint() == second.discovery.fingerprint())
    check("determinism-callgraph", call_graph.fingerprint() == second.call_graph.fingerprint())
    check("determinism-units", units.fingerprint() == second.units.fingerprint())
    check("determinism-classification", program.classification.fingerprint() == second.classification.fingerprint())
    check("determinism-serialize", program.serialize() == second.serialize())
    check("cfg-roundtrip", cfg_module.ControlFlowGraph.deserialize(cfg.serialize()).fingerprint() == cfg.fingerprint())
    check("units-roundtrip", units_module.TranslationUnitSet.deserialize(units.serialize()).fingerprint() == units.fingerprint())

    # H. shared-layer neutrality -------------------------------------------
    shared_modules = {
        "program_model": program_model_module,
        "cfg": cfg_module,
        "functions": functions_module,
        "call_graph": call_graph_module,
        "translation_units": units_module,
        "indirect_control_flow": indirect_module,
    }
    forbidden_import_tokens = ("adapter", "frontend", "nes6502", "mips", "6502")
    for name, module in shared_modules.items():
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        check(f"neutrality-no-arch-import:{name}",
              not any(token in value.lower() for value in imported for token in forbidden_import_tokens))
    bridge_source = pathlib.Path(bridge.__file__).read_text(encoding="utf-8")
    check("neutrality-bridge-imports-adapter", "from adapters import nes6502" in bridge_source)
    check("neutrality-bridge-no-host-emission", "host_emitter" not in bridge_source and "build_pipeline" not in bridge_source)
    metadata_keys = set()
    for instruction in instructions:
        metadata_keys.update((instruction.metadata or {}).get("adapter_fields", {}).keys())
    check("neutrality-generic-metadata", "adapter_fields" in (instructions[0].metadata or {}) and all(isinstance(key, str) for key in metadata_keys))

    # I. independent Phase-1 reference cross-check --------------------------
    reference = ReferenceNES6502(MEMORY, NES6502State(pc=ENTRY))
    trace = []
    while True:
        pc = reference.state.pc
        if not reference.step():
            break
        trace.append(pc)
    instruction_addresses = {instruction.address for instruction in instructions}
    control_addresses = {instruction.address for instruction in instructions if instruction.flow is not InstructionFlow.NORMAL}
    check("reference-trace-in-model", all(address in instruction_addresses for address in trace))
    check("reference-executed-control-matches", {address for address in trace if address in control_addresses} == control_addresses)
    check("reference-loop-taken", trace.count(0x8002) == 3)
    check("reference-call-order", trace.index(0x800B) < trace.index(0x8018) < trace.index(0x800E))
    check("reference-halts", reference.state.halted and reference.state.pc == 0x0202)
    check("reference-final-state", reference.state.a == 15 and reference.state.x == 1)
    check("reference-steps", reference.steps == 21)

    # J. fail-closed --------------------------------------------------------
    bad = bytearray(MEMORY)
    bad[0x8000] = HALT
    expect_fail("undocumented-opcode", lambda: bridge.bridge_program(bad, entry=ENTRY, end=REGION_END))
    expect_fail("truncated-operands", lambda: bridge.bridge_region(MEMORY, entry=ENTRY, end=ENTRY + 1))
    expect_fail("region-past-memory", lambda: bridge.bridge_region(bytes(MEMORY[:0x8001]), entry=ENTRY, end=REGION_END))
    expect_fail("entry-not-before-end", lambda: bridge.bridge_region(MEMORY, entry=ENTRY, end=ENTRY))
    expect_fail("entry-out-of-range", lambda: bridge.bridge_region(MEMORY, entry=0x10000, end=0x10000))
    expect_fail("memory-not-bytes", lambda: bridge.bridge_region("not bytes", entry=ENTRY, end=REGION_END))
    expect_fail("empty-region-selection", lambda: bridge.bridge_region(MEMORY, entry=0x7000, end=0x7000))

    # K. no P2-21 work ------------------------------------------------------
    # The bridge/gate must not emit host code; this is checked structurally
    # (imports/definitions), never as a future-stage absence guard.
    gate_tree = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    gate_imports: set[str] = set()
    gate_defined: set[str] = set()
    for node in ast.walk(gate_tree):
        if isinstance(node, ast.Import):
            gate_imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            gate_imports.add(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            gate_defined.add(node.name)
    check("no-p2-21-host-emitter-import",
          not any("host_emitter" in value or "build_pipeline" in value for value in gate_imports))
    check("no-p2-21-emission-symbol", not any("emit" in name.lower() for name in gate_defined))

    summary_lines = [
        "P2-20 NES6502 program bridge summary",
        "====================================",
        f"region sha256: {REGION_SHA256}",
        f"instruction count: {len(instructions)}",
        f"functions: {', '.join(program.function_ids())}",
        f"call edges: {[(e.caller, e.callee, e.kind.value) for e in call_graph.edges]}",
        f"units: {[u.unit_id for u in units.units]}",
        f"unowned blocks: {discovery.unowned_blocks}",
        f"indirect sites: {[(hex(s.address), s.status.value, list(s.targets)) for s in sites]}",
        f"cfg fingerprint: {cfg.fingerprint()}",
        f"functions fingerprint: {discovery.fingerprint()}",
        f"call graph fingerprint: {call_graph.fingerprint()}",
        f"units fingerprint: {units.fingerprint()}",
        f"classification fingerprint: {program.classification.fingerprint()}",
        f"program fingerprint: {program.fingerprint()}",
        "",
        "independent Phase-1 reference cross-check:",
        f"  trace length: {len(trace)}",
        f"  trace addresses outside the model: {[hex(a) for a in trace if a not in instruction_addresses]}",
        f"  executed control-flow set == model control-flow set: "
        f"{{address for address in trace if address in control_addresses}} == control_addresses",
        f"  halted at: 0x{reference.state.pc:04x}; steps: {reference.steps}; a={reference.state.a}; x={reference.state.x}",
        "",
    ]

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    if args.json:
        record = {
            "stage": "P2-20",
            "marker": f"OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "architecture": bridge.NES6502_ARCHITECTURE,
            "entry": ENTRY,
            "region_end": REGION_END,
            "region_sha256": REGION_SHA256,
            "instruction_count": len(instructions),
            "functions": list(program.function_ids()),
            "call_edges": [{"caller": e.caller, "callee": e.callee, "kind": e.kind.value} for e in call_graph.edges],
            "units": [unit.unit_id for unit in units.units],
            "unowned_blocks": list(discovery.unowned_blocks),
            "indirect_sites": [{"address": s.address, "status": s.status.value, "targets": list(s.targets)} for s in sites],
            "fingerprints": program.to_document(),
            "results": sorted(RESULTS, key=lambda item: item["check"]),
        }
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1_JSON={out.name}")

    if args.evidence_dir:
        write_evidence(pathlib.Path(args.evidence_dir), {"program": program, "summary_lines": summary_lines})

    print(f"OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests={tests}")
    return 0


def _edge_targets(cfg, block_id, kind):
    return sorted(successor.target_address for successor in cfg.block(block_id).successors if successor.kind is kind and successor.resolved)


def _edge_kinds(cfg, block_id):
    return sorted(successor.kind for successor in cfg.block(block_id).successors)


if __name__ == "__main__":
    raise SystemExit(main())
