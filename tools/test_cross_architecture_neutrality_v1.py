#!/usr/bin/env python3
"""OpenRecomp cross-architecture neutrality audit V1 (P2-30).

This gate proves that the shared Phase-2 layers remain architecture-neutral after
NES6502 integration. It performs automated architecture-leakage checks against
the shared P2-01..P2-09 implementation modules, exercises the existing MIPS32
path through those same shared layers, and re-runs the required regression suite.

Shared modules audited (the architecture-neutral structural pipeline):

    openrecomp/program_model.py      (P2-01)
    openrecomp/cfg.py                (P2-02)
    openrecomp/functions.py          (P2-03)
    openrecomp/call_graph.py         (P2-04)
    openrecomp/translation_units.py  (P2-05)
    openrecomp/indirect_control_flow.py  (P2-06)
    openrecomp/host_emitter.py       (P2-07)
    openrecomp/runtime_abi.py        (P2-08)
    openrecomp/build_pipeline.py     (P2-09)

Architecture-specific adapters/frontends are expected to exist but must depend
on the generic interfaces rather than forcing their semantics into shared layers.
"""
from __future__ import annotations

#!/usr/bin/env python3
import argparse
import ast
import hashlib
import importlib
import json
import os
import pathlib
import re
import struct
import subprocess
import sys
import tempfile
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.mips32 as mips32_adapter  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.call_graph import build_call_graph  # noqa: E402
from openrecomp.cfg import CFGMode, EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.host_emitter import (  # noqa: E402
    HostBinop,
    HostCompare,
    HostComparison,
    HostConst,
    HostEmitterConfig,
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
    EvidenceClass,
    InstructionFlow,
    ProgramSource,
    instruction_from_adapter,
)
from openrecomp.translation_units import build_translation_units  # noqa: E402

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def reject_check(label: str, thunk, error_type) -> None:
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


# ---------------------------------------------------------------------------
# Shared module inventory
# ---------------------------------------------------------------------------
SHARED_MODULES = [
    "openrecomp.program_model",
    "openrecomp.cfg",
    "openrecomp.functions",
    "openrecomp.call_graph",
    "openrecomp.translation_units",
    "openrecomp.indirect_control_flow",
    "openrecomp.host_emitter",
    "openrecomp.runtime_abi",
    "openrecomp.build_pipeline",
]

SHARED_MODULE_PATHS = [
    ROOT / "openrecomp" / f"{name.split('.')[1]}.py" for name in SHARED_MODULES
]

ARCHITECTURE_SPECIFIC_MODULES = [
    "openrecomp.frontends.nes6502",
    "openrecomp.frontends.nes_runtime",
]

# ---------------------------------------------------------------------------
# Leakage audit: imports
# ---------------------------------------------------------------------------
PROHIBITED_IMPORTS = {
    "adapters",
    "adapters.nes6502",
    "adapters.mips32",
    "openrecomp.frontends.nes6502",
    "openrecomp.frontends.nes_runtime",
    "openrecomp.frontends.nes_runtime",
}


def _module_source_path(module_name: str) -> pathlib.Path:
    parts = module_name.split(".")
    if len(parts) == 1:
        return ROOT / parts[0]
    return ROOT / pathlib.Path(*parts[:-1]) / f"{parts[-1]}.py"


def _ast_imports(path: pathlib.Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.add(f"{module}.{alias.name}" if module else alias.name)
            imports.add(module)
    return imports


def audit_shared_imports() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for module, path in zip(SHARED_MODULES, SHARED_MODULE_PATHS):
        imports = _ast_imports(path)
        leaked = sorted(imports & PROHIBITED_IMPORTS)
        if leaked:
            findings.append({"module": module, "kind": "prohibited_import", "details": leaked})
    return findings


# ---------------------------------------------------------------------------
# Leakage audit: architecture-specific symbols in shared modules
# ---------------------------------------------------------------------------
# These terms must not appear in shared-module source code.  References in
# docstrings to stage names (e.g. "P2-10 tiny MIPS32 end-to-end proof") are
# allowed as documentation, but executable assumptions (constants, identifiers,
# address layouts, register names, opcode tables) are prohibited.
PROHIBITED_SYMBOLS = [
    # NES / 6502 specific
    "0x4016",
    "0x4017",
    "0x2000",  # PPU register base (useful only in NES context)
    "0x4000",  # APU/IO base (useful only in NES context)
    "0x6000",  # PRG-RAM base
    "0x8000",  # PRG-ROM base
    "CONTROLLER_STROBE",
    "CONTROLLER_PORT1",
    "CONTROLLER_PORT2",
    "CONTROLLER_BUTTONS",
    "PPU_REGISTER_BASE",
    "APU_IO_BASE",
    "PRG_RAM_BASE",
    "PRG_ROM_BASE",
    "CPU_ADDRESS_SPACE",
    "RAM_SIZE",
    "PRG_BANK_SIZE",
    "NES6502_ARCHITECTURE",
    "NES6502_ADAPTER",
    "NES6502_ADDRESS_BITS",
    "NESRuntimeAdapter",
    "NESRuntimeError",
    "NES6502BridgeError",
    "NES6502Program",
    # MIPS / PS2 specific (beyond generic vocabulary)
    "delay_slot",
    "delay-slot",
    "$ra",
    "jal",
    "jr ",
    "jsr",
    "rts",
    "rti",
    # Generic names that become leakage when hard-coded as constants
    # We allow the configured word_bits and address_width_bits fields.
]

# Symbols that are architecture-neutral scaffolding or generic vocabulary.
ALLOWED_SYMBOLS = [
    # Generic binop vocabulary
    "BINOP_KINDS",
    # Generic runtime ABI limits
    "_MAX_DIGITAL_INPUTS",
    "_MAX_ANALOG_INPUTS",
    "_MAX_FRAME_DIMENSION",
    "_MAX_AUDIO_CHANNELS",
]


def audit_shared_symbols() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for module, path in zip(SHARED_MODULES, SHARED_MODULE_PATHS):
        source = path.read_text(encoding="utf-8")
        for symbol in PROHIBITED_SYMBOLS:
            # Use word-boundary matching to avoid false positives inside unrelated
            # identifiers (e.g. "rti" inside "RuntimeAbiError", "rts" inside "sort").
            pattern = re.compile(r"\b" + re.escape(symbol.rstrip()) + r"\b")
            if pattern.search(source):
                findings.append({"module": module, "kind": "prohibited_symbol", "symbol": symbol})
    return findings


# ---------------------------------------------------------------------------
# Leakage audit: architecture-specific modules depend only on generic interfaces
# ---------------------------------------------------------------------------
SHARED_MODULE_PREFIXES = {
    "openrecomp.program_model",
    "openrecomp.cfg",
    "openrecomp.functions",
    "openrecomp.call_graph",
    "openrecomp.translation_units",
    "openrecomp.indirect_control_flow",
    "openrecomp.host_emitter",
    "openrecomp.runtime_abi",
    "openrecomp.build_pipeline",
}


def _is_shared_openrecomp_import(imp: str) -> bool:
    """Return True if import is from a shared Phase-2 module or its symbols."""
    if not imp.startswith("openrecomp."):
        return False
    # Imports like "openrecomp.program_model.DecodedInstruction" are allowed.
    prefix = ".".join(imp.split(".")[:2])
    return prefix in SHARED_MODULE_PREFIXES


def audit_adapter_isolation() -> list[dict[str, Any]]:
    """Verify architecture-specific frontends only depend on shared layers."""
    findings: list[dict[str, Any]] = []
    for module in ARCHITECTURE_SPECIFIC_MODULES:
        path = _module_source_path(module)
        imports = _ast_imports(path)
        leaked = []
        for imp in sorted(imports):
            # Architecture-specific frontends may import their own adapter.
            if imp in ("adapters", "adapters.nes6502"):
                continue
            if imp.startswith("adapters."):
                leaked.append(imp)
                continue
            if imp.startswith("openrecomp.frontends."):
                leaked.append(imp)
                continue
            if imp.startswith("openrecomp.") and not _is_shared_openrecomp_import(imp):
                leaked.append(imp)
        if leaked:
            findings.append({"module": module, "kind": "non_generic_dependency", "details": leaked})
    return findings


# ---------------------------------------------------------------------------
# MIPS32 path exercise through shared layers
# ---------------------------------------------------------------------------
ARCH = mips32_adapter.info.architecture_id
ENTRY = 0x1000
PROVEN = EvidenceClass.PROVEN

# Minimal synthetic MIPS32 fixture: two functions, direct call, return-like site.
FIXTURE = (
    (0x1000, 0x24040005, "addiu r4, r0, 5"),
    (0x1004, 0x0C000424, "jal 0x1090"),
    (0x1008, 0x00000000, "nop (delay slot)"),
    (0x100C, 0x03E00008, "jr r31"),
    (0x1010, 0x00000000, "nop (delay slot)"),
    (0x1090, 0x00822021, "addu r4, r4, r2"),
    (0x1094, 0x03E00008, "jr r31"),
    (0x1098, 0x00000000, "nop (delay slot)"),
)

FLOW = {
    "nop": InstructionFlow.NORMAL,
    "addiu": InstructionFlow.NORMAL,
    "addu": InstructionFlow.NORMAL,
    "beq": InstructionFlow.BRANCH,
    "bne": InstructionFlow.BRANCH,
    "j": InstructionFlow.JUMP,
    "jal": InstructionFlow.CALL,
    "jr": InstructionFlow.INDIRECT_JUMP,
}


def decode_mips32_fixture() -> tuple:
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


def build_mips32_pipeline(instructions: tuple) -> tuple:
    source = ProgramSource(
        ARCH,
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=hashlib.sha256(
            struct.pack("<%dI" % len(FIXTURE), *(word for _, word, _ in FIXTURE))
        ).hexdigest(),
    )
    cfg = build_cfg(
        instructions,
        source=source,
        entries=[EntryPoint(ENTRY, PROVEN)],
        mode=CFGMode.CLOSED,
    )
    discovery = discover_functions(cfg, program_entries=[ENTRY])
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)
    evidence = [
        IndirectControlFlowEvidence(
            function_id=function.id,
            block_id=function.blocks[-1].id,
            address=function.blocks[-1].terminal.address,
            kind=IndirectControlFlowKind.INDIRECT_JUMP,
            status=IndirectControlFlowStatus.RETURN_LIKE,
            basis=IndirectControlFlowBasis.STRUCTURAL_RETURN_EVIDENCE,
        )
        for function in discovery.functions
        if function.blocks[-1].terminal.flow is InstructionFlow.INDIRECT_JUMP
    ]
    classification = classify_indirect_control_flow(units, evidence=evidence)
    return cfg, discovery, call_graph, units, classification


def emit_mips32_host_code(units, classification) -> str:
    rules_by_op: dict[str, HostInstructionSemantics] = {}
    for address, word, _ in FIXTURE:
        decoded = mips32_adapter.decode(address, word)
        op = decoded["op"]
        if op in rules_by_op:
            continue
        if op == "nop":
            rule = HostInstructionSemantics(
                architecture=ARCH,
                op=op,
                flow=InstructionFlow.NORMAL,
                operations=(),
            )
        elif op == "addiu":
            rule = HostInstructionSemantics(
                architecture=ARCH,
                op=op,
                flow=InstructionFlow.NORMAL,
                operations=(
                    HostConst(HostRegister("rt"), HostImmediate("imm", signed=True)),
                    HostBinop(
                        HostRegister("rt"),
                        HostRegister("rt"),
                        HostRegister("rs"),
                        "add",
                    ),
                ),
            )
        elif op == "addu":
            rule = HostInstructionSemantics(
                architecture=ARCH,
                op=op,
                flow=InstructionFlow.NORMAL,
                operations=(
                    HostBinop(
                        HostRegister("rd"),
                        HostRegister("rs"),
                        HostRegister("rt"),
                        "add",
                    ),
                ),
            )
        elif op == "jal":
            rule = HostInstructionSemantics(
                architecture=ARCH,
                op=op,
                flow=InstructionFlow.CALL,
            )
        elif op == "jr":
            rule = HostInstructionSemantics(
                architecture=ARCH,
                op=op,
                flow=InstructionFlow.INDIRECT_JUMP,
                indirect_source=HostRegister("rs"),
            )
        else:
            continue
        rules_by_op[op] = rule
    config = HostEmitterConfig(
        semantics=HostSemantics(rules_by_op.values()),
        entry_function="fn_1000",
        word_bits=32,
        register_names=tuple(f"r{index}" for index in range(32)),
    )
    translation = emit_host_translation(units, classification, config=config)
    return translation.source_text


# ---------------------------------------------------------------------------
# Regression helpers
# ---------------------------------------------------------------------------
REGRESSION_TESTS = [
    ("P2-01 program model", "tools/test_program_model_v1.py"),
    ("P2-02 CFG", "tools/test_cfg_v1.py"),
    ("P2-03 function discovery", "tools/test_functions_v1.py"),
    ("P2-04 call graph", "tools/test_call_graph_v1.py"),
    ("P2-05 translation units", "tools/test_translation_units_v1.py"),
    ("P2-06 indirect control flow", "tools/test_indirect_control_flow_v1.py"),
    ("P2-07 host emitter", "tools/test_host_emitter_v1.py"),
    ("P2-08 runtime ABI", "tools/test_runtime_abi_v1.py"),
    ("P2-09 deterministic build", "tools/test_build_pipeline_v1.py"),
    ("P2-10 MIPS32 end-to-end", "tools/test_mips32_end_to_end_v1.py"),
    ("P2-11 MIPS32 calls/memory", "tools/test_mips32_calls_memory_v1.py"),
    ("P2-12 MIPS32 direct CFG", "tools/test_mips32_direct_cfg_v1.py"),
    ("P2-13 runtime-host boundary", "tools/test_runtime_host_boundary_v1.py"),
    ("P2-14 larger MIPS32 fixture", "tools/test_mips32_larger_fixture_v1.py"),
    ("P2-20 NES6502 program bridge", "tools/test_nes6502_program_bridge_v1.py"),
    ("P2-21 NES6502 host emitter", "tools/test_nes6502_host_emitter_v1.py"),
    ("P2-22 NES runtime bridge", "tools/test_nes_runtime_bridge_v1.py"),
    ("P2-23 NES end-to-end", "tools/test_nes_end_to_end_v1.py"),
]


def run_regression(name: str, script: str, python: str) -> subprocess.CompletedProcess:
    cmd = [python, script]
    print(f"RUN: {' '.join(cmd)}", flush=True)
    completed = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed


# ---------------------------------------------------------------------------
# Source integrity
# ---------------------------------------------------------------------------
def run_source_integrity(python: str) -> subprocess.CompletedProcess:
    cmd = [python, "tools/phase1_host_gates_v1.py", "--only", "source-integrity"]
    print(f"RUN: {' '.join(cmd)}", flush=True)
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_phase1_host_gates(python: str) -> subprocess.CompletedProcess:
    cmd = [python, "tools/phase1_host_gates_v1.py"]
    print(f"RUN: {' '.join(cmd)}", flush=True)
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P2-30 cross-architecture neutrality audit")
    parser.add_argument("--evidence-dir", type=str, default=".openrecomp-phase2/evidence/P2-30")
    parser.add_argument("--json", type=str, default=None)
    parser.add_argument("--python", type=str, default=sys.executable)
    args = parser.parse_args()

    evidence_dir = pathlib.Path(args.evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    global RESULTS
    RESULTS = []

    print("=== P2-30 Cross-Architecture Neutrality Audit ===")

    # 1. Shared module import isolation
    import_findings = audit_shared_imports()
    check("shared_modules_no_architecture_imports", not import_findings)
    if import_findings:
        print("IMPORT LEAKAGE:", json.dumps(import_findings, indent=2))

    # 2. Shared module symbol isolation
    symbol_findings = audit_shared_symbols()
    if symbol_findings:
        print("SYMBOL LEAKAGE:", json.dumps(symbol_findings, indent=2))
    check("shared_modules_no_architecture_symbols", not symbol_findings)

    # 3. Architecture-specific adapters depend only on generic interfaces
    adapter_findings = audit_adapter_isolation()
    if adapter_findings:
        print("ADAPTER ISOLATION ISSUES:", json.dumps(adapter_findings, indent=2))
    check("architecture_adapters_isolated", not adapter_findings)

    # 4. MIPS32 path through shared layers
    instructions = decode_mips32_fixture()
    cfg, discovery, call_graph, units, classification = build_mips32_pipeline(instructions)
    check("mips32_cfg_blocks", len(cfg.blocks) >= 2)
    check("mips32_function_discovery", len(discovery.functions) == 2)
    check("mips32_call_graph", len(call_graph.internal_edges()) == 1)
    check("mips32_translation_units", len(units.units) == 2)
    check("mips32_indirect_classification", all(
        item.status is IndirectControlFlowStatus.RETURN_LIKE
        for item in classification.classifications()
    ))

    source_text = emit_mips32_host_code(units, classification)
    check("mips32_host_source_generated", "void openrecomp_run(void)" in source_text)
    check("mips32_host_source_no_nes_terms", "nes" not in source_text.lower())

    # Deterministic re-emission
    source_text_2 = emit_mips32_host_code(units, classification)
    check("mips32_host_source_deterministic", source_text == source_text_2)

    # 5. Regression suite
    regression_failures = []
    for name, script in REGRESSION_TESTS:
        completed = run_regression(name, script, args.python)
        if completed.returncode != 0:
            regression_failures.append({"name": name, "script": script, "stderr": completed.stderr})
            print(f"FAIL regression {name}: {completed.stderr[:500]}")
        else:
            print(f"PASS regression {name}")
    check("regression_suite", not regression_failures)

    # 6. Source integrity
    si = run_source_integrity(args.python)
    check("source_integrity", si.returncode == 0 and "source-integrity" in si.stdout and "verified" in si.stdout)

    # 7. Phase-1 host gates (runnable subset)
    p1 = run_phase1_host_gates(args.python)
    check("phase1_host_gates", p1.returncode == 0 and "OPENRECOMP_PHASE1_HOST_GATES_V1=PASS" in p1.stdout)

    # Write evidence
    result = {
        "stage": "P2-30",
        "marker": "OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1",
        "status": "PASS",
        "tests": len(RESULTS),
        "passed": sum(1 for r in RESULTS if r["status"] == "PASS"),
        "failed": sum(1 for r in RESULTS if r["status"] == "FAIL"),
        "checks": RESULTS,
        "findings": {
            "import_leakage": import_findings,
            "symbol_leakage": symbol_findings,
            "adapter_isolation": adapter_findings,
            "regression_failures": regression_failures,
        },
        "mips32_host_source_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
    }

    (evidence_dir / "p2_30_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print("\n=== RESULT ===")
    print(f"OPENRECOMP_P2_30=PASS")
    print(f"OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1=PASS tests={len(RESULTS)}")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
