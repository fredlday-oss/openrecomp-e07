#!/usr/bin/env python3
"""OpenRecomp generic runtime integration audit V1 (P2-40).

This gate proves that the Phase-2 generic runtime layer is architecture-neutral,
reusable across platform adapters and safely bounded at the translated-host
boundary. It audits the runtime-facing contracts defined by P2-08
(`openrecomp/runtime_abi.py`) together with the runtime seam in the P2-07 host
emitter and the P2-09 build/launch integration:

    generated host code -> generic runtime ABI -> platform adapters
                                 ^
                       audited generic layer only

Audited generic runtime modules:

    openrecomp/runtime_abi.py    (P2-08 generic runtime ABI: memory, input,
                                  frame, audio, host calls, lifecycle/state)
    openrecomp/runtime.py        (Phase-1 generic normalized-IR core runtime)
    openrecomp/module.py         (Phase-1 generic memory-segment image model)
    openrecomp/host_emitter.py   (P2-07 translated-host runtime boundary)
    openrecomp/build_pipeline.py (P2-09 build/launch integration)

Architecture-specific adapters (`openrecomp/frontends/nes_runtime.py`, NES6502
bridge) are expected to exist and must depend on the generic contracts rather
than forcing platform behavior into the shared runtime.

Deterministic checks:

1. Static import/symbol/address isolation of the generic runtime modules.
2. Generic memory contract: non-NES address spaces (16-bit, 20-bit, 24-bit),
   explicit widths/endianness, overflow, copy semantics, and fail-closed
   rejection of NES-style address mirroring.
3. Generic input/frame/audio contracts with no controller/PPU/APU/DSP layout.
4. Host-call registration/dispatch extensibility without ABI changes and
   fail-closed behavior for unknown services, arity mismatch and handler faults.
5. Runtime lifecycle/state determinism and the explicit failure/trap model.
6. Translated-host boundary: the emitter emits only generic `or_rt_*` calls and
   refuses host calls without an explicit ABI declaration, external evidence or
   the runtime ABI configuration.
7. A synthetic non-NES MIPS32 fixture exercised end-to-end: generated host code
   runs natively against a synthetic platform adapter built on the generic
   contracts and matches an independent Python reference observable exactly.
8. The existing NES runtime adapter exercised through the same generic
   contracts (input mapping, memory, frame/audio submission, fail-closed use).
9. A native unsupported-service run proves the boundary fails closed.
10. The required regression suite, Phase-1 host gates and source integrity.

This gate proves only the audited runtime contracts and the bounded synthetic
fixtures described above. It does not prove complete generic console emulation,
arbitrary future-architecture compatibility, full PPU/APU behavior, commercial
game compatibility, cycle accuracy or full hardware emulation.
"""
from __future__ import annotations

import argparse
import ast
import dataclasses
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
from openrecomp.call_graph import build_call_graph  # noqa: E402
from openrecomp.cfg import CFGError, CFGMode, EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.host_emitter import (  # noqa: E402
    HostBinop,
    HostCallOperation,
    HostConst,
    HostConstant,
    HostEmitterConfig,
    HostEmitterError,
    HostImmediate,
    HostInstructionSemantics,
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
    EvidenceClass,
    InstructionFlow,
    ProgramSource,
    instruction_from_adapter,
)
from openrecomp.translation_units import build_translation_units  # noqa: E402
from openrecomp.frontends import nes_runtime as nes_rt  # noqa: E402

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def expect_fail(label: str, thunk, error_type) -> None:
    try:
        thunk()
    except error_type:
        RESULTS.append({"check": f"reject:{label}", "status": "PASS"})
        print(f"PASS reject: {label}", flush=True)
        return
    except Exception as exc:  # noqa: BLE001
        RESULTS.append({"check": f"reject:{label}", "status": "FAIL"})
        raise AssertionError(f"{label}: raised {type(exc).__name__} instead of {error_type.__name__}: {exc}") from exc
    RESULTS.append({"check": f"reject:{label}", "status": "FAIL"})
    raise AssertionError(f"{label}: accepted")


def expect_code(label: str, thunk, code: rt.RuntimeFailureCode) -> None:
    """Run `thunk` and require a deterministic RuntimeAbiError failure code."""
    try:
        thunk()
    except rt.RuntimeAbiError as exc:
        failure = exc.failure
        check(label, failure is not None and failure.code is code)
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"{label}: raised {type(exc).__name__} instead of RuntimeAbiError: {exc}") from exc
    raise AssertionError(f"{label}: accepted")


def fnv1a64(data: bytes) -> int:
    value = 0xCBF29CE484222325
    for byte in data:
        value ^= byte
        value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value


# ---------------------------------------------------------------------------
# 1. Generic runtime module inventory + static isolation
# ---------------------------------------------------------------------------
AUDITED_RUNTIME_MODULES = (
    "openrecomp.runtime_abi",
    "openrecomp.runtime",
    "openrecomp.module",
    "openrecomp.host_emitter",
    "openrecomp.build_pipeline",
)

# `openrecomp.module` imports the frozen Phase-1 IR validator, which is a
# generic schema/validation dependency, not a platform adapter.
IMPORT_ISOLATION_ALLOWED = {
    ("openrecomp.module", "tools.validate_ir_v1"),
    ("openrecomp.module", "tools.validate_ir_v1.validate_document"),
}

PLATFORM_TOKEN_DENYLIST = (
    "nes", "nes6502", "6502", "ppu", "apu", "nrom", "cartridge", "mapper",
    "controller", "joypad", "gamepad", "ps2", "psx", "psp", "xbox", "rt64",
    "vulkan", "d3d", "d3d12", "opengl", "metal", "sdl", "wasapi", "xaudio",
    "alsa", "pulseaudio", "coreaudio", "sm83", "z80", "m68k", "sh2",
    "eekernel", "iop", "bios", "hle",
)

PLATFORM_BUS_ADDRESSES = {
    0x2000: "NES PPU register base",
    0x2007: "NES PPU register limit",
    0x3F00: "NES palette base",
    0x4014: "NES OAMDMA",
    0x4015: "NES APU status",
    0x4016: "NES controller port 1",
    0x4017: "NES controller port 2",
    0x6000: "NES PRG-RAM base",
    0x8000: "NES PRG-ROM base",
    0xFF00: "GB/SMS I/O base",
    0xFFFF: "16-bit address limit",
    0x10000: "fixed 16-bit address space",
}

PLATFORM_SERVICE_PATTERN = re.compile(r"^(nes|gb|gbc|sms|gg|psx|ps2|nds|n64|snes|atari)\.", re.IGNORECASE)

# Scanner self-test fixtures: the leak scanner must flag these tokens and must
# not flag generic runtime vocabulary.
PLANTED_LEAK_SOURCE = '''
NES_PPU_BASE = 0x2000
CONTROLLER_STROBE = 0x4016
SERVICE = "nes.frame.submit"


def read_controller():
    return CONTROLLER_STROBE
'''

CLEAN_SOURCE = '''
GENERIC_WIDTHS = (8, 16, 32, 64)


def read_memory(address, width_bits):
    return address + width_bits
'''

HOST_STATE_MODULES = ("openrecomp.runtime_abi", "openrecomp.runtime")
HOST_STATE_IMPORTS = frozenset({
    "os", "sys", "time", "random", "uuid", "socket", "platform", "locale",
    "subprocess", "tempfile", "shutil", "pathlib", "getpass", "secrets",
})


def _runtime_module_path(module_name: str) -> pathlib.Path:
    parts = module_name.split(".")
    return ROOT / "openrecomp" / f"{parts[1]}.py"


def _ast_imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                imports.add(module)
            for alias in node.names:
                imports.add(f"{module}.{alias.name}" if module else alias.name)
    return imports


def _docstring_nodes(tree: ast.AST) -> set[int]:
    docs: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docs.add(id(body[0].value))
    return docs


def _identifiers(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
    return names


def _string_constants(tree: ast.AST) -> list[str]:
    docs = _docstring_nodes(tree)
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            values.append(node.value)
    return values


def _integer_constants(tree: ast.AST) -> set[int]:
    values: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            values.add(node.value)
    return values


def audit_runtime_imports() -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for module in AUDITED_RUNTIME_MODULES:
        imports = _ast_imports(_runtime_module_path(module))
        leaked: list[str] = []
        for imp in sorted(imports):
            if (module, imp) in IMPORT_ISOLATION_ALLOWED:
                continue
            if imp.startswith(("adapters.", "openrecomp.frontends.", "tools.")) or imp == "adapters":
                leaked.append(imp)
        if leaked:
            findings.append({"module": module, "kind": "platform_import", "details": leaked})
    return findings


def symbol_findings(module: str, tree: ast.AST) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    identifiers = _identifiers(tree)
    strings = _string_constants(tree)
    for token in PLATFORM_TOKEN_DENYLIST:
        for name in sorted(identifiers):
            segments = {segment.lower() for segment in name.split("_")}
            if name.lower() == token or token in segments:
                findings.append({"module": module, "kind": "platform_identifier", "token": token, "detail": name})
        word = re.compile(r"\b" + re.escape(token) + r"\b", re.IGNORECASE)
        for value in strings:
            if word.search(value):
                findings.append({"module": module, "kind": "platform_string", "token": token, "detail": value})
    for value in strings:
        if PLATFORM_SERVICE_PATTERN.match(value):
            findings.append({"module": module, "kind": "platform_service_name", "detail": value})
    return findings


def address_findings(module: str, tree: ast.AST) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for value in sorted(_integer_constants(tree) & set(PLATFORM_BUS_ADDRESSES)):
        findings.append(
            {
                "module": module,
                "kind": "platform_bus_address",
                "literal": value,
                "hex": hex(value),
                "meaning": PLATFORM_BUS_ADDRESSES[value],
            }
        )
    return findings


def audit_runtime_symbols() -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for module in AUDITED_RUNTIME_MODULES:
        findings.extend(symbol_findings(module, ast.parse(_runtime_module_path(module).read_text(encoding="utf-8"))))
    return findings


def audit_runtime_addresses() -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for module in AUDITED_RUNTIME_MODULES:
        findings.extend(address_findings(module, ast.parse(_runtime_module_path(module).read_text(encoding="utf-8"))))
    return findings


def audit_host_state_imports() -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for module in HOST_STATE_MODULES:
        imports = {name.split(".")[0] for name in _ast_imports(_runtime_module_path(module))}
        leaked = sorted(imports & HOST_STATE_IMPORTS)
        if leaked:
            findings.append({"module": module, "kind": "host_state_import", "details": leaked})
    return findings


# ---------------------------------------------------------------------------
# 2. Contract classification (evidence data, validated here)
# ---------------------------------------------------------------------------
ALLOWED_LAYERS = frozenset({
    "architecture-neutral runtime contract",
    "platform adapter responsibility",
    "architecture/frontend responsibility",
    "host implementation responsibility",
})

CONCEPT_CLASSIFICATION = (
    ("guest memory image and checked byte/word access", "architecture-neutral runtime contract", "openrecomp.runtime_abi.RuntimeMemory"),
    ("guest address space size, endianness and segment layout", "platform adapter responsibility", "adapter-supplied RuntimeMemory configuration"),
    ("guest address width declaration", "architecture/frontend responsibility", "ProgramSource.address_width_bits and emitter word_bits"),
    ("guest register file ownership", "architecture/frontend responsibility", "emitter register_names derived from adapter fields"),
    ("digital/analog input snapshot transport", "architecture-neutral runtime contract", "openrecomp.runtime_abi.RuntimeInputSnapshot"),
    ("device button/axis layout and serial protocol", "platform adapter responsibility", "NES controller mapping in openrecomp/frontends/nes_runtime.py"),
    ("physical input device acquisition", "host implementation responsibility", "host process feeding RuntimeInputSnapshot"),
    ("frame geometry/format/payload transport", "architecture-neutral runtime contract", "openrecomp.runtime_abi.RuntimeFrame"),
    ("platform pixel format ids and rendering", "platform adapter responsibility", "adapter-local format id maps; rendering stays outside the ABI"),
    ("frame presentation backend selection", "host implementation responsibility", "host backend fed by RuntimeFrame"),
    ("audio sample format/rate/channel/payload transport", "architecture-neutral runtime contract", "openrecomp.runtime_abi.RuntimeAudio"),
    ("platform audio format ids and synthesis", "platform adapter responsibility", "adapter-local format id maps; DSP stays outside the ABI"),
    ("audio device backend selection", "host implementation responsibility", "host backend fed by RuntimeAudio"),
    ("host service identity, arity and dispatch", "architecture-neutral runtime contract", "openrecomp.runtime_abi.RuntimeService and RuntimeServiceTable"),
    ("platform service names and implementations", "platform adapter responsibility", "adapter-declared services (for example nes.frame.submit)"),
    ("which guest site invokes which service", "architecture/frontend responsibility", "P2-06 external/runtime evidence plus explicit emitter rule"),
    ("runtime lifecycle, step budget and failure latch", "architecture-neutral runtime contract", "openrecomp.runtime_abi.RuntimeConfig and RuntimeState"),
    ("deterministic RNG hook", "architecture-neutral runtime contract", "openrecomp.runtime_abi.RuntimeState.next_random"),
    ("ABI identity and versioning", "architecture-neutral runtime contract", "openrecomp.runtime_abi.RuntimeAbiVersion"),
    ("generated host -> runtime boundary", "host implementation responsibility", "or_rt_* declarations plus host-provided implementation"),
    ("build, launch and artifact reproducibility", "host implementation responsibility", "openrecomp.build_pipeline plus host toolchain"),
)

BACKEND_EXTENSION_POINTS = (
    {
        "platform": "gb",
        "guest_address_width_bits": 16,
        "generic_contracts_used": ["RuntimeMemory", "RuntimeInputSnapshot", "RuntimeFrame", "RuntimeAudio", "RuntimeServiceTable", "RuntimeState"],
        "adapter_responsibilities": ["ROM banking / MBC mapping", "JOYP input protocol", "2bpp tile-to-pixel conversion", "4-channel APU mixing/resampling"],
        "abi_changes_required": "none",
        "notes": "16-bit guest space is an adapter configuration, not a shared-ABI assumption.",
    },
    {
        "platform": "gbc",
        "guest_address_width_bits": 16,
        "generic_contracts_used": ["RuntimeMemory", "RuntimeInputSnapshot", "RuntimeFrame", "RuntimeAudio", "RuntimeServiceTable", "RuntimeState"],
        "adapter_responsibilities": ["VRAM/WRAM banking", "double-speed timing policy", "CGB palette expansion to a RuntimePixelFormat"],
        "abi_changes_required": "none",
        "notes": "CGB extras stay in the platform adapter; the generic contracts are unchanged.",
    },
    {
        "platform": "sms",
        "guest_address_width_bits": 16,
        "generic_contracts_used": ["RuntimeMemory", "RuntimeInputSnapshot", "RuntimeFrame", "RuntimeAudio", "RuntimeServiceTable", "RuntimeState"],
        "adapter_responsibilities": ["Sega mapper banking", "controller port decoding", "VDP palette expansion", "PSG synthesis"],
        "abi_changes_required": "none",
        "notes": "Z80 I/O ports map to adapter-defined services and memory-side registers.",
    },
    {
        "platform": "rt64-like presentation backend",
        "guest_address_width_bits": None,
        "generic_contracts_used": ["RuntimeFrame", "RuntimeAudio", "RuntimeServiceTable"],
        "adapter_responsibilities": ["GPU-side scene/present integration", "frame pacing and resampling"],
        "abi_changes_required": "none",
        "notes": "Rendering backends consume RuntimeFrame submissions from the host side; no GPU API enters the shared ABI.",
    },
)

# ---------------------------------------------------------------------------
# 3. Synthetic non-NES runtime fixture (MIPS32 guest)
# ---------------------------------------------------------------------------
ARCH = mips32_adapter.info.architecture_id
ENTRY = 0x1000
FRAME_SUBMIT_SITE = 0x1018
PROVEN = EvidenceClass.PROVEN
FIXTURE_ID = "p2-40-generic-runtime-integration-v1"

MEMORY_SIZE = 0x20000
FRAME_PTR = 0x10200
AUDIO_PTR = 0x10210
FRAME_BYTES = bytes(
    (0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80,
     0x90, 0xA0, 0xB0, 0xC0, 0xD0, 0xE0, 0xF0, 0x01)
)
AUDIO_BYTES = bytes((0x7F, 0x80, 0x81, 0x82))
INPUT_DIGITAL = (True, False, True, True, False, False, False, True)
INPUT_POLL_VALUE = 0x8D
FRAME_FORMAT_ID = 1   # synthetic adapter: 1 = RGBA8 (platform-defined)
AUDIO_FORMAT_ID = 0   # synthetic adapter: 0 = U8 (platform-defined)

# (address, word, mnemonic) -- synthetic/original fixture, little-endian MIPS32.
FIXTURE = (
    (0x1000, 0x3C040001, "lui r4, 0x0001                 ; r4 = 0x10000"),
    (0x1004, 0x24840200, "addiu r4, r4, 0x200           ; r4 = 0x10200 frame payload"),
    (0x1008, 0x3C050001, "lui r5, 0x0001                 ; r5 = 0x10000"),
    (0x100C, 0x24A50210, "addiu r5, r5, 0x210           ; r5 = 0x10210 audio payload"),
    (0x1010, 0xAC040000, "sw r4, 0(r0)                  ; generic 32-bit memory write"),
    (0x1014, 0xAC050004, "sw r5, 4(r0)                  ; generic 32-bit memory write"),
    (0x1018, 0x00800008, "jr r4                         ; synthetic.frame.submit(r4,2,2,1)"),
    (0x101C, 0x00000000, "nop (delay slot)"),
    (0x1020, 0x34A50000, "ori r5, r5, 0                 ; synthetic.audio.submit(r5,8000,1,4,0)"),
    (0x1024, 0x38C60000, "xori r6, r6, 0                ; r6 = synthetic.input.poll()"),
    (0x1028, 0x24C70007, "addiu r7, r6, 7               ; r7 = poll + 7"),
)
WORDS = tuple(word for _, word, _ in FIXTURE)
FIXTURE_BYTES = struct.pack("<%dI" % len(WORDS), *WORDS)
FIXTURE_SHA256 = hashlib.sha256(FIXTURE_BYTES).hexdigest()

FLOW = {
    "nop": InstructionFlow.NORMAL,
    "lui": InstructionFlow.NORMAL,
    "addiu": InstructionFlow.NORMAL,
    "sw": InstructionFlow.NORMAL,
    "ori": InstructionFlow.NORMAL,
    "xori": InstructionFlow.NORMAL,
    "jr": InstructionFlow.INDIRECT_CALL,
}

SERVICE_FRAME = "synthetic.frame.submit"
SERVICE_AUDIO = "synthetic.audio.submit"
SERVICE_INPUT = "synthetic.input.poll"
SERVICES = (
    rt.RuntimeService(SERVICE_AUDIO, 5),
    rt.RuntimeService(SERVICE_FRAME, 4),
    rt.RuntimeService(SERVICE_INPUT, 0),
)

FRAME_FORMATS = {
    0: rt.RuntimePixelFormat.RGB565,
    1: rt.RuntimePixelFormat.RGBA8,
    2: rt.RuntimePixelFormat.INDEX8,
}
FRAME_PIXEL_BYTES = {
    rt.RuntimePixelFormat.RGB565: 2,
    rt.RuntimePixelFormat.RGBA8: 4,
    rt.RuntimePixelFormat.INDEX8: 1,
}
AUDIO_FORMATS = {
    0: rt.RuntimeSampleFormat.U8,
    1: rt.RuntimeSampleFormat.S16LE,
    2: rt.RuntimeSampleFormat.S32LE,
}
AUDIO_SAMPLE_BYTES = {
    rt.RuntimeSampleFormat.U8: 1,
    rt.RuntimeSampleFormat.S16LE: 2,
    rt.RuntimeSampleFormat.S32LE: 4,
}


def decode_fixture():
    instructions = []
    for address, word, _ in FIXTURE:
        decoded = mips32_adapter.decode(address, word)
        flow = FLOW[decoded["op"]]
        instructions.append(
            instruction_from_adapter(
                decoded,
                flow=flow,
                unresolved=(flow is InstructionFlow.INDIRECT_CALL),
                size_bytes=4,
                evidence=PROVEN,
            )
        )
    return tuple(instructions)


def program_source() -> ProgramSource:
    return ProgramSource(
        ARCH,
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=FIXTURE_SHA256,
    )


def semantics_table(*, frame_service: str = SERVICE_FRAME):
    def r(op, flow, **kw):
        return HostInstructionSemantics(ARCH, op, flow, **kw)

    return HostSemantics([
        r("nop", InstructionFlow.NORMAL),
        r("lui", InstructionFlow.NORMAL, operations=(
            HostConst(HostRegister("rt"), HostImmediate("imm", shift=16)),
        )),
        r("addiu", InstructionFlow.NORMAL, operations=(
            HostBinop(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True), "add"),
        )),
        r("sw", InstructionFlow.NORMAL, operations=(
            HostStore(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True)),
        )),
        r("ori", InstructionFlow.NORMAL, host_call=HostCallOperation(
            SERVICE_AUDIO,
            args=(HostRegister("rs"), HostConstant(8000), HostConstant(1), HostConstant(4), HostConstant(AUDIO_FORMAT_ID)),
        )),
        r("xori", InstructionFlow.NORMAL, host_call=HostCallOperation(
            SERVICE_INPUT,
            args=(),
            result=HostRegister("rt"),
        )),
        r("jr", InstructionFlow.INDIRECT_CALL, host_call=HostCallOperation(
            frame_service,
            args=(HostRegister("rs"), HostConstant(2), HostConstant(2), HostConstant(FRAME_FORMAT_ID)),
        )),
    ])


def run_pipeline(*, declared: bool = True, evidence_kind: str = "external", frame_service: str = SERVICE_FRAME):
    source = program_source()
    cfg = build_cfg(decode_fixture(), source=source, entries=[EntryPoint(ENTRY, PROVEN)], mode=CFGMode.CLOSED)
    discovery = discover_functions(cfg, program_entries=[ENTRY])
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)

    site = None
    for unit in units.units:
        for block in unit.blocks:
            terminal = block.terminal
            if terminal.flow is InstructionFlow.INDIRECT_CALL:
                site = (unit.function_id, block.id, terminal.address)

    evidence = []
    if evidence_kind == "external" and site is not None:
        evidence.append(IndirectControlFlowEvidence(
            function_id=site[0],
            block_id=site[1],
            address=site[2],
            kind=IndirectControlFlowKind.INDIRECT_CALL,
            status=IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED,
            basis=IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE,
            external_mechanism="runtime-service",
            source="p2-40-fixture",
            evidence=PROVEN,
        ))
    classification = classify_indirect_control_flow(units, evidence=evidence)

    table = rt.RuntimeServiceTable(SERVICES, {service.service_id: (lambda args: 0) for service in SERVICES})
    runtime_abi = rt.RuntimeAbiConfig(services=table) if declared else None
    host = emit_host_translation(units, classification, config=HostEmitterConfig(
        semantics=semantics_table(frame_service=frame_service),
        entry_function=discovery.entry_function_id,
        word_bits=32,
        runtime_abi=runtime_abi,
    ))
    return {
        "cfg": cfg,
        "discovery": discovery,
        "call_graph": call_graph,
        "units": units,
        "classification": classification,
        "table": table,
        "host": host,
        "site": site,
    }


class SyntheticPlatformAdapter:
    """A non-NES platform adapter built only on the generic runtime contracts.

    The adapter owns one deterministic `RuntimeState`, pre-seeds its frame and
    audio payload regions, declares its own service names and format ids, and
    maps a generic `RuntimeInputSnapshot` to a platform-defined poll word. No
    shared runtime module knows anything about this platform.
    """

    def __init__(self, *, input_snapshot=None):
        snapshot = rt.RuntimeInputSnapshot(digital=INPUT_DIGITAL) if input_snapshot is None else input_snapshot
        config = rt.RuntimeConfig(memory_size_bytes=MEMORY_SIZE, endianness="little")
        memory = rt.RuntimeMemory(
            MEMORY_SIZE,
            endianness="little",
            segments=(
                rt.RuntimeMemorySegment(FRAME_PTR, "frame_payload", FRAME_BYTES),
                rt.RuntimeMemorySegment(AUDIO_PTR, "audio_payload", AUDIO_BYTES),
            ),
        )
        services = rt.RuntimeServiceTable(
            SERVICES,
            {
                SERVICE_FRAME: self._frame_submit,
                SERVICE_AUDIO: self._audio_submit,
                SERVICE_INPUT: self._input_poll,
            },
        )
        self.state = rt.RuntimeState(config, memory=memory, services=services)
        self.state.set_input(snapshot)

    def _frame_submit(self, args):
        pointer, width, height, format_id = args
        pixel_format = FRAME_FORMATS.get(format_id)
        if pixel_format is None:
            raise ValueError(f"unsupported frame format id {format_id}")
        length = width * height * FRAME_PIXEL_BYTES[pixel_format]
        payload = self.state.memory.read_bytes(pointer, length)
        self.state.submit_frame(
            rt.RuntimeFrame(width, height, pixel_format, payload, sequence=len(self.state.frames))
        )
        return 0

    def _audio_submit(self, args):
        pointer, sample_rate, channels, frames, format_id = args
        sample_format = AUDIO_FORMATS.get(format_id)
        if sample_format is None:
            raise ValueError(f"unsupported audio format id {format_id}")
        length = frames * channels * AUDIO_SAMPLE_BYTES[sample_format]
        payload = self.state.memory.read_bytes(pointer, length)
        self.state.submit_audio(
            rt.RuntimeAudio(sample_format, sample_rate, channels, frames, payload, sequence=len(self.state.audio))
        )
        return 0

    def _input_poll(self, _args):
        value = 0
        for index, pressed in enumerate(self.state.input.digital):
            if pressed:
                value |= 1 << index
        return value


def expected_memory_image() -> bytearray:
    """Build the expected post-run memory image independently of the adapter."""
    image = bytearray(MEMORY_SIZE)
    image[0:4] = FRAME_PTR.to_bytes(4, "little")
    image[4:8] = AUDIO_PTR.to_bytes(4, "little")
    image[FRAME_PTR:FRAME_PTR + len(FRAME_BYTES)] = FRAME_BYTES
    image[AUDIO_PTR:AUDIO_PTR + len(AUDIO_BYTES)] = AUDIO_BYTES
    return image


def expected_observable() -> str:
    image = expected_memory_image()
    lines = [
        "failed=0",
        "error=",
        "register_count=5",
        "reg[0]=0",
        f"reg[1]={FRAME_PTR}",
        f"reg[2]={AUDIO_PTR}",
        f"reg[3]={INPUT_POLL_VALUE}",
        f"reg[4]={INPUT_POLL_VALUE + 7}",
        f"mem_words={FRAME_PTR},{AUDIO_PTR}",
        "frame_count=1",
        f"frame[0]=2x2 format=RGBA8 checksum={fnv1a64(FRAME_BYTES)}",
        "audio_count=1",
        f"audio[0]=8000Hz channels=1 frames=4 format=U8 checksum={fnv1a64(AUDIO_BYTES)}",
        f"input_poll={INPUT_POLL_VALUE}",
        f"memory_checksum={fnv1a64(bytes(image))}",
    ]
    return "\n".join(lines)


SUPPORT_TEMPLATE = """\
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

void openrecomp_run(void);
int openrecomp_failed(void);
size_t openrecomp_register_count(void);
uint64_t openrecomp_register_value(size_t index);
const char *openrecomp_error(void);

#define MEMORY_SIZE __MEMORY_SIZE__u
#define FRAME_PTR __FRAME_PTR__u
#define AUDIO_PTR __AUDIO_PTR__u
#define SERVICE_AUDIO __SERVICE_AUDIO__u
#define SERVICE_FRAME __SERVICE_FRAME__u
#define SERVICE_INPUT __SERVICE_INPUT__u

static uint8_t g_mem[MEMORY_SIZE];
static const uint8_t g_frame_payload[__FRAME_LENGTH__] = { __FRAME_BYTES__ };
static const uint8_t g_audio_payload[__AUDIO_LENGTH__] = { __AUDIO_BYTES__ };

static uint64_t g_frame_count;
static uint64_t g_frame_w;
static uint64_t g_frame_h;
static uint64_t g_frame_checksum;
static uint64_t g_audio_count;
static uint64_t g_audio_rate;
static uint64_t g_audio_channels;
static uint64_t g_audio_frames;
static uint64_t g_audio_checksum;
static uint64_t g_input_poll;

static uint64_t fnv1a64(const uint8_t *data, size_t length) {
    uint64_t hash = UINT64_C(14695981039346656037);
    for (size_t index = 0; index < length; ++index) {
        hash ^= (uint64_t)data[index];
        hash *= UINT64_C(1099511628211);
    }
    return hash;
}

static int memory_span(uint64_t address, uint64_t length, const uint8_t **out) {
    if (address > MEMORY_SIZE || length > MEMORY_SIZE - address) return 0;
    *out = &g_mem[address];
    return 1;
}

int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value) {
    if (width_bits != 32u || out_value == 0) return 1;
    const uint8_t *span = 0;
    if (!memory_span(address, 4u, &span)) return 2;
    uint64_t value = 0;
    for (unsigned index = 0; index < 4u; ++index) value |= (uint64_t)span[index] << (8u * index);
    *out_value = value;
    return 0;
}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value) {
    if (width_bits != 32u) return 1;
    if (address > MEMORY_SIZE || 4u > MEMORY_SIZE - address) return 2;
    for (unsigned index = 0; index < 4u; ++index) g_mem[address + index] = (uint8_t)(value >> (8u * index));
    return 0;
}

/* Synthetic non-NES platform adapter. Format ids are platform-defined; the
   generic runtime ABI only sees the resulting frame/audio semantics. */
int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value) {
    if (out_value == 0) return 2;
    *out_value = 0;
    if (service_id == SERVICE_FRAME) {
        if (argc != 4u || args == 0) return 2;
        uint64_t pointer = args[0], width = args[1], height = args[2], format_id = args[3];
        if (format_id != 1u) return 4;
        const uint8_t *payload = 0;
        if (!memory_span(pointer, width * height * 4u, &payload)) return 3;
        g_frame_count += 1u;
        g_frame_w = width;
        g_frame_h = height;
        g_frame_checksum = fnv1a64(payload, (size_t)(width * height * 4u));
        return 0;
    }
    if (service_id == SERVICE_AUDIO) {
        if (argc != 5u || args == 0) return 2;
        if (!__AUDIO_SUPPORTED__) return 6;
        uint64_t pointer = args[0], rate = args[1], channels = args[2], frames = args[3], format_id = args[4];
        if (format_id != 0u) return 4;
        const uint8_t *payload = 0;
        if (!memory_span(pointer, frames * channels, &payload)) return 3;
        g_audio_count += 1u;
        g_audio_rate = rate;
        g_audio_channels = channels;
        g_audio_frames = frames;
        g_audio_checksum = fnv1a64(payload, (size_t)(frames * channels));
        return 0;
    }
    if (service_id == SERVICE_INPUT) {
        if (argc != 0u) return 2;
        g_input_poll = UINT64_C(__INPUT_POLL__);
        *out_value = g_input_poll;
        return 0;
    }
    return 6;
}

const char *or_rt_failure_reason(int code) { (void)code; return ""; }

int main(void) {
    memcpy(g_mem + FRAME_PTR, g_frame_payload, sizeof(g_frame_payload));
    memcpy(g_mem + AUDIO_PTR, g_audio_payload, sizeof(g_audio_payload));
    openrecomp_run();
    printf("failed=%d\\n", openrecomp_failed());
    printf("error=%s\\n", openrecomp_error());
    printf("register_count=%zu\\n", openrecomp_register_count());
    for (size_t index = 0; index < openrecomp_register_count(); ++index) {
        printf("reg[%zu]=%llu\\n", index, (unsigned long long)openrecomp_register_value(index));
    }
    printf("mem_words=%llu,%llu\\n",
           (unsigned long long)g_mem[0] | ((unsigned long long)g_mem[1] << 8) |
               ((unsigned long long)g_mem[2] << 16) | ((unsigned long long)g_mem[3] << 24),
           (unsigned long long)g_mem[4] | ((unsigned long long)g_mem[5] << 8) |
               ((unsigned long long)g_mem[6] << 16) | ((unsigned long long)g_mem[7] << 24));
    printf("frame_count=%llu\\n", (unsigned long long)g_frame_count);
    if (g_frame_count != 0u) {
        printf("frame[0]=%llux%llu format=%s checksum=%llu\\n",
               (unsigned long long)g_frame_w, (unsigned long long)g_frame_h, "RGBA8",
               (unsigned long long)g_frame_checksum);
    }
    printf("audio_count=%llu\\n", (unsigned long long)g_audio_count);
    if (g_audio_count != 0u) {
        printf("audio[0]=%lluHz channels=%llu frames=%llu format=%s checksum=%llu\\n",
               (unsigned long long)g_audio_rate, (unsigned long long)g_audio_channels,
               (unsigned long long)g_audio_frames, "U8", (unsigned long long)g_audio_checksum);
    }
    printf("input_poll=%llu\\n", (unsigned long long)g_input_poll);
    printf("memory_checksum=%llu\\n", (unsigned long long)fnv1a64(g_mem, MEMORY_SIZE));
    return 0;
}
"""


def support_source(table: rt.RuntimeServiceTable, *, audio_supported: bool = True) -> str:
    payload = ", ".join(f"0x{byte:02x}" for byte in FRAME_BYTES)
    audio_payload = ", ".join(f"0x{byte:02x}" for byte in AUDIO_BYTES)
    substitutions = {
        "__MEMORY_SIZE__": str(MEMORY_SIZE),
        "__FRAME_PTR__": str(FRAME_PTR),
        "__AUDIO_PTR__": str(AUDIO_PTR),
        "__SERVICE_AUDIO__": str(table.numeric_id(SERVICE_AUDIO)),
        "__SERVICE_FRAME__": str(table.numeric_id(SERVICE_FRAME)),
        "__SERVICE_INPUT__": str(table.numeric_id(SERVICE_INPUT)),
        "__FRAME_LENGTH__": str(len(FRAME_BYTES)),
        "__FRAME_BYTES__": payload,
        "__AUDIO_LENGTH__": str(len(AUDIO_BYTES)),
        "__AUDIO_BYTES__": audio_payload,
        "__AUDIO_SUPPORTED__": "1u" if audio_supported else "0u",
        "__INPUT_POLL__": str(INPUT_POLL_VALUE),
    }
    text = SUPPORT_TEMPLATE
    for key, value in substitutions.items():
        text = text.replace(key, value)
    return text


# ---------------------------------------------------------------------------
# 4. NES runtime adapter exercise (existing platform path)
# ---------------------------------------------------------------------------
NES_PRG_ROM = bytes((index * 7 + 3) & 0xFF for index in range(16 * 1024))
NES_INPUT = rt.RuntimeInputSnapshot(digital=INPUT_DIGITAL)
NES_FRAME_BYTES = bytes((0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88,
                         0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x00))
NES_AUDIO_BYTES = bytes((0x01, 0x02, 0x03, 0x04))


# ---------------------------------------------------------------------------
# 5. Regression suite
# ---------------------------------------------------------------------------
REGRESSION_TESTS = (
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
    ("P2-30 cross-architecture neutrality", "tools/test_cross_architecture_neutrality_v1.py"),
    ("NES platform contract", "tools/test_nes_platform_v1.py"),
)


def run_command(command: list[str], python: str) -> subprocess.CompletedProcess:
    print(f"RUN: {' '.join(command)}", flush=True)
    return subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# ---------------------------------------------------------------------------
# 6. Evidence helpers
# ---------------------------------------------------------------------------
def _write_text(path: pathlib.Path, text: str) -> str:
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def write_evidence(evidence_dir: pathlib.Path, staging: dict) -> dict[str, str]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}

    fixture_lines = [
        "P2-40 synthetic non-NES MIPS32 fixture (generic runtime integration)",
        "=" * 76,
        f"architecture: {ARCH}",
        "endianness: little",
        f"entry: 0x{ENTRY:x}; runtime-mediated call site: 0x{FRAME_SUBMIT_SITE:x}",
        f"instruction count: {len(FIXTURE)}",
        f"byte length: {len(FIXTURE_BYTES)}",
        f"sha256: {FIXTURE_SHA256}",
        "origin: synthetic/original (no commercial ROM/ELF bytes)",
        f"fixture-declared services: {SERVICE_FRAME} (4 args), {SERVICE_AUDIO} (5 args), {SERVICE_INPUT} (0 args)",
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
        "P2-02 CFG evidence",
        "==================",
        f"mode: {cfg.mode.value}",
        f"fingerprint: {cfg.fingerprint()}",
        "blocks: " + ", ".join(f"0x{block.entry_address:x}" for block in cfg.ordered_blocks()),
        "edges:", *edge_lines, "",
    ]))

    discovery = staging["discovery"]
    hashes["pipeline_functions.txt"] = _write_text(evidence_dir / "pipeline_functions.txt", "\n".join([
        "P2-03 function-discovery evidence",
        "=================================",
        f"entry_function: {discovery.entry_function_id}",
        f"fingerprint: {discovery.fingerprint()}",
        "functions: " + ", ".join(f"{function.id}@0x{function.entry_address:x}" for function in discovery.functions),
        "unowned_blocks: " + ", ".join(discovery.unowned_blocks),
        "",
    ]))

    units = staging["units"]
    hashes["pipeline_translation_units.txt"] = _write_text(evidence_dir / "pipeline_translation_units.txt", "\n".join([
        "P2-05 translation-unit evidence",
        "===============================",
        "units: " + ", ".join(f"{unit.unit_id}({unit.function_id})" for unit in units.units),
        "unowned_blocks: " + ", ".join(units.unowned_blocks),
        f"fingerprint: {units.fingerprint()}",
        "",
    ]))

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
                f"basis={item.basis.value} mechanism={item.external_mechanism} targets={list(item.targets)}"
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
        f"register_names: {list(host.register_names)}\nfingerprint: {host.fingerprint()}\n",
    )

    table = staging["table"]
    abi_lines = [
        "P2-08 generic runtime ABI contract evidence (P2-40 audit)",
        "=========================================================",
        f"runtime ABI: {rt.RUNTIME_ABI_NAME} {rt.RUNTIME_ABI_VERSION}",
        f"declared services: {list(table.service_ids)}",
        f"numeric ids: {[table.numeric_id(service) for service in table.service_ids]}",
        f"macros: {[table.macro(service) for service in table.service_ids]}",
        f"service table fingerprint: {table.fingerprint()}",
    ]
    hashes["runtime_abi_contract.txt"] = _write_text(evidence_dir / "runtime_abi_contract.txt", "\n".join(abi_lines) + "\n")

    comparison = staging["comparison"]
    (evidence_dir / "build_manifest.json").write_bytes(comparison.runs[0].manifest.serialize())
    hashes["build_manifest.json"] = hashlib.sha256((evidence_dir / "build_manifest.json").read_bytes()).hexdigest()
    for index, run in enumerate(comparison.runs[:2]):
        manifest = run.manifest
        lines = [
            f"P2-40 deterministic build run {index + 1}",
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
            "compile_commands:", *["  " + " ".join(command) for command in manifest.compile_commands],
            "link_command: " + " ".join(manifest.link_command),
            f"manifest_sha256: {manifest.fingerprint()}",
            "",
        ]
        hashes[f"build_run_{index + 1}.txt"] = _write_text(evidence_dir / f"build_run_{index + 1}.txt", "\n".join(lines))

    expected = staging["expected_output"]
    actual = staging["actual_output"]
    hashes["native_execution.txt"] = _write_text(evidence_dir / "native_execution.txt", "\n".join([
        "P2-40 native execution (synthetic non-NES platform adapter)",
        "===========================================================",
        f"executable sha256: {staging['exe_sha256']}",
        f"returncode: {staging['native_returncode']}",
        "stdout:", actual, "",
    ]))
    hashes["expected_vs_actual.txt"] = _write_text(evidence_dir / "expected_vs_actual.txt", "\n".join([
        "P2-40 expected vs actual observable",
        "===================================",
        "expected (independent Python reference through the generic runtime contracts):",
        expected,
        "actual (native executable stdout):",
        actual,
        f"EXPECTED == ACTUAL: {'YES' if expected == actual else 'NO'}",
        "",
    ]))
    hashes["unsupported_service.txt"] = _write_text(
        evidence_dir / "unsupported_service.txt",
        "\n".join(["P2-40 native unsupported-service fail-closed evidence", "=" * 54,
                   *staging["unsupported_lines"], ""]),
    )
    hashes["nes_path_exercise.txt"] = _write_text(
        evidence_dir / "nes_path_exercise.txt",
        "\n".join(["P2-40 NES runtime-adapter exercise (generic contract reuse)", "=" * 60,
                   *staging["nes_lines"], ""]),
    )
    hashes["static_isolation.json"] = _write_text(
        evidence_dir / "static_isolation.json",
        json.dumps(staging["static_findings"], indent=2, sort_keys=True) + "\n",
    )
    return hashes


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="P2-40 generic runtime integration audit")
    parser.add_argument("--evidence-dir", type=str, default=".openrecomp-phase2/evidence/P2-40")
    parser.add_argument("--json", type=str, default=None)
    parser.add_argument("--python", type=str, default=sys.executable)
    parser.add_argument(
        "--skip-regressions",
        action="store_true",
        help="development only: skip the regression suite (never used for committed evidence)",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    evidence_dir = pathlib.Path(args.evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    global RESULTS
    RESULTS = []

    print("=== P2-40 Generic Runtime Integration Audit ===")

    # A. inventory + static isolation ---------------------------------------
    check("audited-runtime-module-count", len(AUDITED_RUNTIME_MODULES) == 5)
    check(
        "audited-runtime-modules-exist",
        all(_runtime_module_path(module).exists() for module in AUDITED_RUNTIME_MODULES),
    )
    runtime_abi_path = _runtime_module_path("openrecomp.runtime_abi")
    runtime_abi_source = runtime_abi_path.read_text(encoding="utf-8")

    import_findings = audit_runtime_imports()
    module_symbol_findings = audit_runtime_symbols()
    module_address_findings = audit_runtime_addresses()
    host_state_findings = audit_host_state_imports()
    check("runtime-no-platform-imports", not import_findings)
    check("runtime-no-platform-symbols", not module_symbol_findings)
    check("runtime-no-platform-service-names",
          not [f for f in module_symbol_findings if f["kind"] == "platform_service_name"])
    check("runtime-no-platform-bus-addresses", not module_address_findings)
    check("runtime-no-host-state-imports", not host_state_findings)
    if import_findings or module_symbol_findings or module_address_findings or host_state_findings:
        print("STATIC FINDINGS:", json.dumps(
            {"imports": import_findings, "symbols": module_symbol_findings,
             "addresses": module_address_findings, "host_state": host_state_findings}, indent=2))

    # Scanner self-test: a planted leak must be detected, a clean source must not.
    planted_symbols = symbol_findings("<planted>", ast.parse(PLANTED_LEAK_SOURCE))
    planted_addresses = address_findings("<planted>", ast.parse(PLANTED_LEAK_SOURCE))
    clean_symbols = symbol_findings("<clean>", ast.parse(CLEAN_SOURCE))
    clean_addresses = address_findings("<clean>", ast.parse(CLEAN_SOURCE))
    check("static-scanner-detects-planted-leak",
          {"platform_identifier", "platform_service_name"}.issubset({finding["kind"] for finding in planted_symbols})
          and len(planted_addresses) >= 2)
    check("static-scanner-clean-source-passes", not clean_symbols and not clean_addresses)

    # B. ABI identity -------------------------------------------------------
    check("runtime-abi-name", rt.RUNTIME_ABI_NAME == "openrecomp-generic-runtime-abi")
    check("runtime-abi-version", rt.RUNTIME_ABI_VERSION == "1.0.0" and rt.RUNTIME_ABI == rt.RuntimeAbiVersion.current())
    check("runtime-widths-set", rt.RUNTIME_WIDTHS == frozenset({8, 16, 32, 64}))
    check("runtime-endianness-set", rt.RUNTIME_ENDIANNESS == frozenset({"little", "big"}))

    # C. memory contract ----------------------------------------------------
    small = rt.RuntimeMemory(0x10000, endianness="little")
    small.write(0x1234, 0xA5, 8)
    small.write(0x00FF, 0x1234, 16)
    check("memory-16bit-space-round-trip",
          small.read(0x1234, 8) == 0xA5 and small.read(0x00FF, 16) == 0x1234)
    expect_code("memory-16bit-space-does-not-wrap",
                lambda: small.read(0x10000, 8), rt.RuntimeFailureCode.MEMORY_OUT_OF_RANGE)
    check("memory-16bit-space-no-alias", small.read(0x0000, 8) == 0 and small.read(0xFFFC, 8) == 0)

    mirrored = rt.RuntimeMemory(0x800, endianness="little")
    mirrored.write(0x07FF, 0x5A, 8)
    expect_code("memory-no-nes-ram-mirror-read",
                lambda: mirrored.read(0x0800, 8), rt.RuntimeFailureCode.MEMORY_OUT_OF_RANGE)
    expect_code("memory-no-nes-ram-mirror-write",
                lambda: mirrored.write(0x0800, 1, 8), rt.RuntimeFailureCode.MEMORY_OUT_OF_RANGE)
    check("memory-no-nes-ram-mirror-alias", mirrored.read(0x0000, 8) == 0)

    large = rt.RuntimeMemory(0x00100000, endianness="little",
                             segments=(rt.RuntimeMemorySegment(0x000FF000, "high", b"\x11\x22\x33\x44"),))
    check("memory-20bit-segment-no-truncation",
          large.read(0x000FF000, 8) == 0x11 and large.read(0x000FF003, 8) == 0x44)
    check("memory-20bit-segment-no-mirror", large.read(0x0000F000, 8) == 0)

    wide = rt.RuntimeMemory(0x01000000, endianness="little",
                            segments=(rt.RuntimeMemorySegment(0x00FFF000, "wide", b"\xAB"),))
    check("memory-24bit-segment-no-truncation", wide.read(0x00FFF000, 8) == 0xAB)
    check("memory-24bit-segment-no-mirror", wide.read(0x0000F000, 8) == 0)
    wide.write(0x00FFFFFF, 0x7F, 8)
    check("memory-24bit-write-round-trip", wide.read(0x00FFFFFF, 8) == 0x7F)

    expect_code("memory-64bit-address-overflow",
                lambda: rt.RuntimeMemory(0x100, endianness="little").read(rt.RUNTIME_MAX_ADDRESS, 64),
                rt.RuntimeFailureCode.MEMORY_ADDRESS_OVERFLOW)
    expect_code("memory-unsupported-width",
                lambda: small.read(0, 24), rt.RuntimeFailureCode.MEMORY_WIDTH_UNSUPPORTED)
    expect_code("memory-width-bool-rejected",
                lambda: small.read(0, True), rt.RuntimeFailureCode.MEMORY_WIDTH_UNSUPPORTED)
    expect_code("memory-out-of-range", lambda: small.read(0xFFFF, 16), rt.RuntimeFailureCode.MEMORY_OUT_OF_RANGE)
    expect_code("memory-unsupported-endianness",
                lambda: rt.RuntimeMemory(0x10, endianness="middle"), rt.RuntimeFailureCode.MEMORY_ENDIANNESS_UNSUPPORTED)
    expect_fail("memory-zero-size", lambda: rt.RuntimeMemory(0), rt.RuntimeAbiError)
    expect_code("memory-segment-overlap", lambda: rt.RuntimeMemory(
        0x100,
        segments=(
            rt.RuntimeMemorySegment(0x00, "a", b"\x01\x02\x03\x04"),
            rt.RuntimeMemorySegment(0x02, "b", b"\x05"),
        ),
    ), rt.RuntimeFailureCode.MEMORY_SEGMENT_OVERLAP)
    expect_fail("memory-segment-out-of-range", lambda: rt.RuntimeMemory(
        0x10, segments=(rt.RuntimeMemorySegment(0x0F, "a", b"\x01\x02"),)), rt.RuntimeAbiError)

    big = rt.RuntimeMemory(4, endianness="big", segments=(rt.RuntimeMemorySegment(0, "s", b"\x01\x02\x03\x04"),))
    check("memory-big-endian-read", big.read(0, 32) == 0x01020304 and big.read(0, 16) == 0x0102)
    byte_swap = rt.RuntimeMemory(4, endianness="little", segments=(rt.RuntimeMemorySegment(0, "s", b"\x01\x02\x03\x04"),))
    check("memory-per-access-endianness", byte_swap.read(0, 32, endianness="big") == 0x01020304)

    copies = rt.RuntimeMemory(0x20, endianness="little")
    copies.write_bytes(0x00, b"\x01\x02\x03\x04")
    got = copies.read_bytes(0x00, 4)
    got += b"\xFF"
    check("memory-read-bytes-copy", copies.read_bytes(0x00, 4) == b"\x01\x02\x03\x04" and got == b"\x01\x02\x03\x04\xFF")
    copies.write(0x10, 0x1FF, 8)
    check("memory-write-value-masked", copies.read(0x10, 8) == 0xFF)
    result_ok = copies.try_read(0x00, 8)
    result_bad = copies.try_read(0x100, 8)
    check("memory-try-result-contract",
          result_ok.ok and result_ok.value == 0x01 and not result_bad.ok
          and result_bad.failure is not None
          and result_bad.failure.code is rt.RuntimeFailureCode.MEMORY_OUT_OF_RANGE)
    expect_code("memory-read-bytes-negative", lambda: copies.read_bytes(-1, 1), rt.RuntimeFailureCode.MEMORY_OUT_OF_RANGE)

    # D. input contract ------------------------------------------------------
    digital = tuple(index % 3 == 0 for index in range(25))
    analog = tuple((index * 7) % 65536 for index in range(8))
    snapshot = rt.RuntimeInputSnapshot(digital=digital, analog=analog, analog_bits=16)
    check("input-generic-digital-analog",
          snapshot.digital == digital and snapshot.analog == analog and snapshot.analog_bits == 16)
    input_fields = {field.name for field in dataclasses.fields(rt.RuntimeInputSnapshot)}
    check("input-contract-field-surface", input_fields == {"digital", "analog", "analog_bits"})
    trimmed = rt.RuntimeInputSnapshot(digital=(True, False, False), analog=(5, 0, 0))
    check("input-canonicalization",
          trimmed.digital == (True,) and trimmed.analog == (5,)
          and trimmed.fingerprint() == rt.RuntimeInputSnapshot(digital=(True,), analog=(5,)).fingerprint())
    restored = rt.RuntimeInputSnapshot.deserialize(snapshot.serialize())
    check("input-round-trip", restored.digital == snapshot.digital and restored.analog == snapshot.analog
          and restored.fingerprint() == snapshot.fingerprint())
    expect_code("input-digital-limit", lambda: rt.RuntimeInputSnapshot(digital=(True,) * 257),
                rt.RuntimeFailureCode.INPUT_INVALID)
    expect_code("input-analog-limit", lambda: rt.RuntimeInputSnapshot(analog=(1,) * 65),
                rt.RuntimeFailureCode.INPUT_INVALID)
    expect_code("input-analog-bits-invalid", lambda: rt.RuntimeInputSnapshot(analog_bits=7),
                rt.RuntimeFailureCode.INPUT_INVALID)
    expect_code("input-analog-overflow", lambda: rt.RuntimeInputSnapshot(analog=(0x10000,), analog_bits=16),
                rt.RuntimeFailureCode.INPUT_INVALID)
    expect_code("input-digital-non-bool", lambda: rt.RuntimeInputSnapshot(digital=(1,)),
                rt.RuntimeFailureCode.INPUT_INVALID)
    expect_code("input-deserialize-missing-key",
                lambda: rt.RuntimeInputSnapshot.from_document({"digital": [], "analog": []}),
                rt.RuntimeFailureCode.INPUT_INVALID)
    expect_code("input-deserialize-malformed",
                lambda: rt.RuntimeInputSnapshot.deserialize(b"{not json"),
                rt.RuntimeFailureCode.INPUT_INVALID)

    # E. frame contract ------------------------------------------------------
    frame_cases = (
        (256, 224, rt.RuntimePixelFormat.RGBA8, 4),
        (320, 240, rt.RuntimePixelFormat.RGB565, 2),
        (160, 144, rt.RuntimePixelFormat.INDEX8, 1),
        (640, 480, rt.RuntimePixelFormat.GRAY8, 1),
        (384, 216, rt.RuntimePixelFormat.BGRA8, 4),
    )
    frame_ok = True
    frame_fingerprints = set()
    for width, height, pixel_format, bytes_per_pixel in frame_cases:
        payload = bytes((index * 13 + 1) & 0xFF for index in range(width * height * bytes_per_pixel))
        frame = rt.RuntimeFrame(width, height, pixel_format, payload)
        frame_ok = frame_ok and frame.width == width and frame.height == height and len(frame.payload) == len(payload)
        restored_frame = rt.RuntimeFrame.deserialize(frame.serialize())
        frame_ok = frame_ok and restored_frame.fingerprint() == frame.fingerprint()
        frame_fingerprints.add(frame.fingerprint())
    check("frame-non-nes-geometries-and-formats", frame_ok and len(frame_fingerprints) == len(frame_cases))
    expect_code("frame-payload-length", lambda: rt.RuntimeFrame(2, 2, rt.RuntimePixelFormat.RGBA8, b"\x00"),
                rt.RuntimeFailureCode.FRAME_INVALID)
    expect_code("frame-zero-dimension", lambda: rt.RuntimeFrame(0, 2, rt.RuntimePixelFormat.RGBA8, b""),
                rt.RuntimeFailureCode.FRAME_INVALID)
    expect_fail("frame-dimension-bound",
                lambda: rt.RuntimeFrame(16385, 2, rt.RuntimePixelFormat.RGBA8, b""), rt.RuntimeAbiError)
    expect_code("frame-bad-pixel-format",
                lambda: rt.RuntimeFrame(2, 2, "RGBA8", b"\x00" * 16), rt.RuntimeFailureCode.FRAME_INVALID)
    frame_descriptor_fields = {field.name for field in dataclasses.fields(rt.RuntimeFrame)}
    check("frame-contract-field-surface",
          frame_descriptor_fields == {"width", "height", "pixel_format", "payload", "sequence"})
    frame_document = rt.RuntimeFrame(2, 2, rt.RuntimePixelFormat.RGBA8, b"\x00" * 16, sequence=3).to_document()
    check("frame-document-generic", set(frame_document) == {
        "width", "height", "pixel_format", "sequence", "byte_length", "checksum"})
    check("frame-checksum-stable",
          rt.RuntimeFrame(2, 2, rt.RuntimePixelFormat.RGBA8, b"\x00" * 16).checksum()
          == hashlib.sha256(b"\x00" * 16).hexdigest())

    # F. audio contract ------------------------------------------------------
    audio_cases = (
        (rt.RuntimeSampleFormat.U8, 8000, 1, 512, 1),
        (rt.RuntimeSampleFormat.S16LE, 22050, 2, 256, 2),
        (rt.RuntimeSampleFormat.S16BE, 44100, 1, 128, 2),
        (rt.RuntimeSampleFormat.S32LE, 48000, 2, 64, 4),
        (rt.RuntimeSampleFormat.F32LE, 96000, 6, 32, 4),
        (rt.RuntimeSampleFormat.F32BE, 32000, 4, 16, 4),
    )
    audio_ok = True
    for sample_format, sample_rate, channels, frames, bytes_per_sample in audio_cases:
        payload = bytes((index * 3 + 7) & 0xFF for index in range(frames * channels * bytes_per_sample))
        audio = rt.RuntimeAudio(sample_format, sample_rate, channels, frames, payload)
        restored_audio = rt.RuntimeAudio.deserialize(audio.serialize())
        audio_ok = audio_ok and len(audio.payload) == len(payload) and restored_audio.fingerprint() == audio.fingerprint()
    check("audio-all-sample-formats", audio_ok)
    expect_code("audio-payload-length",
                lambda: rt.RuntimeAudio(rt.RuntimeSampleFormat.U8, 8000, 1, 4, b"\x00"),
                rt.RuntimeFailureCode.AUDIO_INVALID)
    expect_code("audio-zero-rate",
                lambda: rt.RuntimeAudio(rt.RuntimeSampleFormat.U8, 0, 1, 4, b"\x00" * 4),
                rt.RuntimeFailureCode.AUDIO_INVALID)
    expect_code("audio-zero-channels",
                lambda: rt.RuntimeAudio(rt.RuntimeSampleFormat.U8, 8000, 0, 4, b"\x00" * 4),
                rt.RuntimeFailureCode.AUDIO_INVALID)
    expect_code("audio-zero-frames",
                lambda: rt.RuntimeAudio(rt.RuntimeSampleFormat.U8, 8000, 1, 0, b""),
                rt.RuntimeFailureCode.AUDIO_INVALID)
    expect_fail("audio-channel-bound",
                lambda: rt.RuntimeAudio(rt.RuntimeSampleFormat.U8, 8000, 65, 1, b"\x00" * 65),
                rt.RuntimeAbiError)
    audio_descriptor_fields = {field.name for field in dataclasses.fields(rt.RuntimeAudio)}
    check("audio-contract-field-surface",
          audio_descriptor_fields == {"sample_format", "sample_rate", "channels", "frames", "payload", "sequence"})

    # G. host services: registration, dispatch, extensibility ---------------
    table_a = rt.RuntimeServiceTable(
        (
            rt.RuntimeService("device.chan-0:x", 2),
            rt.RuntimeService("device.frame.submit", 1),
        ),
        {
            "device.chan-0:x": lambda args: args[0] + args[1],
            "device.frame.submit": lambda args: None,
        },
    )
    synthetic_table = rt.RuntimeServiceTable(
        SERVICES, {service.service_id: (lambda args: len(args)) for service in SERVICES}
    )
    check("services-extension-two-independent-tables",
          table_a.service_ids == ("device.chan-0:x", "device.frame.submit")
          and synthetic_table.service_ids == ("synthetic.audio.submit", "synthetic.frame.submit", "synthetic.input.poll"))
    check("services-numeric-id-canonical",
          table_a.numeric_id("device.chan-0:x") == 1 and table_a.numeric_id("device.frame.submit") == 2
          and synthetic_table.numeric_id("synthetic.audio.submit") == 1
          and synthetic_table.numeric_id("synthetic.input.poll") == 3)
    check("services-macro-sanitization", table_a.macro("device.chan-0:x") == "OR_RT_SERVICE_DEVICE_CHAN_0_X")
    dispatch_a = table_a.dispatch(rt.RuntimeHostCallRequest("device.chan-0:x", (20, 22)))
    dispatch_b = synthetic_table.dispatch(rt.RuntimeHostCallRequest("synthetic.input.poll", ()))
    check("services-dispatch-both-tables", dispatch_a.ok and dispatch_a.value == 42 and dispatch_b.ok and dispatch_b.value == 0)
    unknown = synthetic_table.dispatch(rt.RuntimeHostCallRequest("synthetic.missing", ()))
    check("services-unknown-fails-closed",
          not unknown.ok and unknown.failure is not None
          and unknown.failure.code is rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE)
    arity = synthetic_table.dispatch(rt.RuntimeHostCallRequest("synthetic.frame.submit", (1, 2, 3)))
    check("services-arity-fails-closed",
          not arity.ok and arity.failure is not None
          and arity.failure.code is rt.RuntimeFailureCode.HOST_CALL_ARITY)
    expect_fail("services-unknown-raises", lambda: synthetic_table.service("synthetic.missing"), rt.RuntimeAbiError)
    expect_fail("services-duplicate-id", lambda: rt.RuntimeServiceTable(
        (rt.RuntimeService("a.b", 0), rt.RuntimeService("a.b", 0)), {"a.b": lambda args: None},
    ), rt.RuntimeAbiError)
    expect_fail("services-handler-without-declaration",
                lambda: rt.RuntimeServiceTable((rt.RuntimeService("a.b", 0),), {"a.c": lambda args: None}),
                rt.RuntimeAbiError)
    expect_fail("services-declaration-without-handler",
                lambda: rt.RuntimeServiceTable((rt.RuntimeService("a.b", 0),), {}), rt.RuntimeAbiError)
    expect_fail("services-invalid-identifier",
                lambda: rt.RuntimeService("1bad id", 0), rt.RuntimeAbiError)
    expect_fail("host-call-request-empty-service", lambda: rt.RuntimeHostCallRequest(""), rt.RuntimeAbiError)
    expect_fail("host-call-request-list-args", lambda: rt.RuntimeHostCallRequest("a.b", [1]), rt.RuntimeAbiError)
    expect_fail("host-call-request-negative-arg", lambda: rt.RuntimeHostCallRequest("a.b", (-1,)), rt.RuntimeAbiError)

    failing_table = rt.RuntimeServiceTable(
        (rt.RuntimeService("device.boom", 0), rt.RuntimeService("device.bad-return", 0)),
        {
            "device.boom": lambda args: (_ for _ in ()).throw(ValueError("boom")),
            "device.bad-return": lambda args: True,
        },
    )
    boom = failing_table.dispatch(rt.RuntimeHostCallRequest("device.boom", ()))
    bad_return = failing_table.dispatch(rt.RuntimeHostCallRequest("device.bad-return", ()))
    check("services-handler-exception-fails-closed",
          not boom.ok and boom.failure is not None
          and boom.failure.code is rt.RuntimeFailureCode.HOST_SERVICE_FAILED
          and "ValueError" in boom.failure.detail)
    check("services-handler-bad-return-fails-closed",
          not bad_return.ok and bad_return.failure is not None
          and bad_return.failure.code is rt.RuntimeFailureCode.HOST_SERVICE_FAILED)
    masked = rt.RuntimeServiceTable(
        (rt.RuntimeService("device.mask", 0),),
        {"device.mask": lambda args: (1 << 64) + 5},
    ).dispatch(rt.RuntimeHostCallRequest("device.mask", ()))
    check("services-result-masked", masked.ok and masked.value == 5)
    check("services-table-fingerprint-deterministic",
          table_a.fingerprint() == rt.RuntimeServiceTable(
              (rt.RuntimeService("device.frame.submit", 1), rt.RuntimeService("device.chan-0:x", 2)),
              {
                  "device.chan-0:x": lambda args: args[0] + args[1],
                  "device.frame.submit": lambda args: None,
              },
          ).fingerprint())

    # H. configuration, lifecycle and state ---------------------------------
    config = rt.RuntimeConfig(memory_size_bytes=0x100)
    check("config-defaults",
          config.endianness == "little" and config.max_steps == 1_000_000 and config.seed == 0
          and config.abi_version == rt.RUNTIME_ABI)
    config_fields = {field.name for field in dataclasses.fields(rt.RuntimeConfig)}
    check("config-no-fixed-guest-width-fields",
          config_fields == {"memory_size_bytes", "endianness", "max_steps", "seed", "abi_version"})
    expect_fail("config-zero-memory", lambda: rt.RuntimeConfig(memory_size_bytes=0), rt.RuntimeAbiError)
    expect_code("config-endianness-invalid",
                lambda: rt.RuntimeConfig(memory_size_bytes=16, endianness="middle"),
                rt.RuntimeFailureCode.MEMORY_ENDIANNESS_UNSUPPORTED)
    version_two = rt.RuntimeAbiVersion(major=2)
    expect_code("config-abi-mismatch",
                lambda: rt.RuntimeConfig(memory_size_bytes=16, abi_version=version_two),
                rt.RuntimeFailureCode.ABI_VERSION_MISMATCH)
    expect_code("abi-config-mismatch",
                lambda: rt.RuntimeAbiConfig(version=version_two), rt.RuntimeFailureCode.ABI_VERSION_MISMATCH)
    check("abi-version-parse", rt.RuntimeAbiVersion.parse("1.2.3") == rt.RuntimeAbiVersion(major=1, minor=2, patch=3))
    check("abi-version-compatibility",
          rt.RuntimeAbiVersion(major=1, minor=9).compatible_with(rt.RUNTIME_ABI)
          and not version_two.compatible_with(rt.RUNTIME_ABI))
    expect_fail("abi-version-parse-malformed", lambda: rt.RuntimeAbiVersion.parse("1.2"), rt.RuntimeAbiError)

    state = rt.RuntimeState(rt.RuntimeConfig(memory_size_bytes=0x100))
    state.read(0, 8)
    state.write(0, 1, 8)
    state.set_input(rt.RuntimeInputSnapshot(digital=(True,)))
    state.host_call("none", ())
    state.submit_frame(rt.RuntimeFrame(1, 1, rt.RuntimePixelFormat.GRAY8, b"\x00"))
    state.submit_audio(rt.RuntimeAudio(rt.RuntimeSampleFormat.U8, 8000, 1, 1, b"\x00"))
    check("state-steps-monotonic", state.steps == 6)
    check("state-host-call-record", len(state.host_calls) == 1
          and state.host_calls[0].sequence == 0
          and state.host_calls[0].service == "none"
          and not state.host_calls[0].result.ok)
    check("state-unknown-host-call-latched-host-service",
          state.host_calls[0].result.failure is not None
          and state.host_calls[0].result.failure.code is rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE)
    check("state-frame-audio-recorded", len(state.frames) == 1 and len(state.audio) == 1)

    trapped = rt.RuntimeState(rt.RuntimeConfig(memory_size_bytes=0x100, max_steps=2))
    trapped.read(0, 8)
    trapped.read(0, 8)
    expect_code("state-step-limit-trap", lambda: trapped.read(0, 8), rt.RuntimeFailureCode.TRAP)
    check("state-trap-latches-failure",
          trapped.failed and trapped.failure is not None
          and trapped.failure.code is rt.RuntimeFailureCode.TRAP)

    latched = rt.RuntimeState(rt.RuntimeConfig(memory_size_bytes=0x100))
    first_failure = rt.RuntimeFailure(code=rt.RuntimeFailureCode.TRAP, detail="first")
    latched.record_failure(first_failure)
    latched.record_failure(rt.RuntimeFailure(code=rt.RuntimeFailureCode.UNSUPPORTED_OPERATION, detail="second"))
    check("state-failure-first-wins", latched.failure == first_failure)

    random_a = rt.RuntimeState(rt.RuntimeConfig(memory_size_bytes=16, seed=1234))
    random_b = rt.RuntimeState(rt.RuntimeConfig(memory_size_bytes=16, seed=1234))
    random_c = rt.RuntimeState(rt.RuntimeConfig(memory_size_bytes=16, seed=4321))
    sequence_a = [random_a.next_random() for _ in range(5)]
    sequence_b = [random_b.next_random() for _ in range(5)]
    sequence_c = [random_c.next_random() for _ in range(5)]
    check("state-random-seeded-deterministic", sequence_a == sequence_b and sequence_a != sequence_c)

    deterministic_a = SyntheticPlatformAdapter()
    deterministic_b = SyntheticPlatformAdapter()
    check("state-snapshot-deterministic", deterministic_a.state.fingerprint() == deterministic_b.state.fingerprint())
    deterministic_b.state.write(0, 1, 32)
    check("state-fingerprint-changes-with-state",
          deterministic_a.state.fingerprint() != deterministic_b.state.fingerprint())
    state_text = deterministic_a.state.serialize()
    check("state-serialize-versioned", b"runtime_abi" in state_text and b"1.0.0" in state_text)

    declarations = rt.abi_c_declarations(table_a)
    check("abi-c-declarations-generic", all(
        line in declarations for line in (
            "extern int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value);",
            "extern int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value);",
            "extern int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);",
        )
    ))
    check("abi-c-declarations-service-macros",
          "#define OR_RT_SERVICE_DEVICE_CHAN_0_X UINT64_C(1)" in declarations
          and rt.abi_c_source(table_a).startswith("#include <stdint.h>\n"))
    check("abi-c-declarations-deterministic", declarations == rt.abi_c_declarations(table_a))

    # I. concept classification data ----------------------------------------
    check("classification-all-layers-declared",
          all(layer in ALLOWED_LAYERS for _, layer, _ in CONCEPT_CLASSIFICATION))
    check("classification-concept-count", len(CONCEPT_CLASSIFICATION) == 21)
    check("classification-platform-tokens-absent-from-generic-source",
          all(not PLATFORM_SERVICE_PATTERN.search(value)
              for value in _string_constants(ast.parse(runtime_abi_source))))
    check("extension-points-no-abi-changes",
          all(entry["abi_changes_required"] == "none" for entry in BACKEND_EXTENSION_POINTS)
          and len(BACKEND_EXTENSION_POINTS) == 4)

    # J. translated-host boundary (emitter) ----------------------------------
    staging = run_pipeline()
    host = staging["host"]
    source_text = host.source_text
    check("emitter-host-call-frame",
          "or_rt_host_call(OR_RT_SERVICE_SYNTHETIC_FRAME_SUBMIT, 4u, or_call_args, &or_call_result)" in source_text)
    check("emitter-host-call-audio",
          "or_rt_host_call(OR_RT_SERVICE_SYNTHETIC_AUDIO_SUBMIT, 5u, or_call_args, &or_call_result)" in source_text)
    check("emitter-host-call-input",
          "or_rt_host_call(OR_RT_SERVICE_SYNTHETIC_INPUT_POLL, 0u, 0, &or_call_result)" in source_text)
    check("emitter-memory-boundary",
          "or_rt_memory_write(or_addr, 32u, g_r[1])" in source_text
          and "or_rt_memory_write(or_addr, 32u, g_r[2])" in source_text)
    check("emitter-fail-closed-message",
          'or_fail("runtime host service synthetic.audio.submit failed");' in source_text)
    check("emitter-boundary-declarations-only",
          source_text.count("extern ") == 4 and "or_rt_failure_reason" in source_text)
    check("emitter-no-pointer-cast",
          all(token not in source_text for token in ("*(uint64_t *)", "*(uint32_t *)", "*(uint8_t *)")))
    check("emitter-no-platform-tokens",
          all(not re.search(r"\b" + re.escape(token) + r"\b", source_text, re.IGNORECASE)
              for token in ("nes", "ppu", "apu", "nrom", "cartridge", "controller", "rt64", "vulkan")))
    check("emitter-only-portable-standard-headers",
          all(line in ("#include <stdint.h>", "#include <stddef.h>")
              for line in source_text.splitlines() if line.startswith("#include ")))
    check("emitter-word-bits-explicit", "or_mask(32u)" in source_text and "static uint64_t g_r[5];" in source_text)
    check("emitter-deterministic", host.source_text == run_pipeline()["host"].source_text)

    expect_fail("emitter-default-config-fails-closed", lambda: run_pipeline(declared=False), HostEmitterError)
    expect_fail("emitter-undeclared-service-fails-closed",
                lambda: run_pipeline(frame_service="synthetic.other"), HostEmitterError)
    expect_fail("emitter-host-call-without-evidence-fails-closed",
                lambda: run_pipeline(evidence_kind="none"), HostEmitterError)
    expect_fail("emitter-invalid-word-bits", lambda: HostEmitterConfig(
        semantics=semantics_table(), entry_function="fn_1000", word_bits=24,
    ), HostEmitterError)
    expect_fail("emitter-host-call-empty-service", lambda: HostCallOperation(""), HostEmitterError)

    # K. synthetic non-NES runtime exercise (reference) ----------------------
    check("fixture-sha256", FIXTURE_SHA256 == hashlib.sha256(struct.pack("<%dI" % len(WORDS), *WORDS)).hexdigest())
    check("fixture-instruction-count", len(FIXTURE) == 11)
    check("fixture-synthetic-origin", all(mnemonic for _, _, mnemonic in FIXTURE))

    cfg = staging["cfg"]
    discovery = staging["discovery"]
    units = staging["units"]
    classification = staging["classification"]
    check("pipeline-cfg-two-blocks", [block.id for block in cfg.ordered_blocks()] == ["blk_1000", "blk_101c"])
    check("pipeline-single-function", [function.id for function in discovery.functions] == ["fn_1000"])
    check("pipeline-single-unit", [unit.unit_id for unit in units.units] == ["tu_fn_1000"])
    sites = [item for unit in classification.units for item in unit.classifications]
    check("pipeline-classification-external",
          len(sites) == 1 and sites[0].status is IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED
          and sites[0].basis is IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE
          and sites[0].external_mechanism == "runtime-service")
    check("pipeline-classification-no-targets", sites[0].targets == () and staging["site"][2] == FRAME_SUBMIT_SITE)
    check("pipeline-deterministic",
          cfg.fingerprint() == run_pipeline()["cfg"].fingerprint()
          and units.fingerprint() == run_pipeline()["units"].fingerprint())
    no_evidence = classify_indirect_control_flow(units, evidence=[])
    no_evidence_sites = [item for unit in no_evidence.units for item in unit.classifications]
    check("pipeline-no-evidence-fails-closed",
          no_evidence_sites[0].status is IndirectControlFlowStatus.UNRESOLVED_INDIRECT_CALL
          and no_evidence_sites[0].targets == ())

    adapter = SyntheticPlatformAdapter()
    adapter.state.write(0, FRAME_PTR, 32)
    adapter.state.write(4, AUDIO_PTR, 32)
    frame_call = adapter.state.host_call(SERVICE_FRAME, (FRAME_PTR, 2, 2, FRAME_FORMAT_ID))
    audio_call = adapter.state.host_call(SERVICE_AUDIO, (AUDIO_PTR, 8000, 1, 4, AUDIO_FORMAT_ID))
    input_call = adapter.state.host_call(SERVICE_INPUT, ())
    check("reference-memory-writes",
          adapter.state.memory.read(0, 32) == FRAME_PTR and adapter.state.memory.read(4, 32) == AUDIO_PTR)
    check("reference-frame-submitted",
          frame_call.ok and len(adapter.state.frames) == 1
          and adapter.state.frames[0].payload == FRAME_BYTES
          and adapter.state.frames[0].pixel_format is rt.RuntimePixelFormat.RGBA8
          and adapter.state.frames[0].width == 2 and adapter.state.frames[0].height == 2)
    check("reference-audio-submitted",
          audio_call.ok and len(adapter.state.audio) == 1
          and adapter.state.audio[0].payload == AUDIO_BYTES
          and adapter.state.audio[0].sample_format is rt.RuntimeSampleFormat.U8
          and adapter.state.audio[0].sample_rate == 8000)
    check("reference-input-poll", input_call.ok and input_call.value == INPUT_POLL_VALUE)
    check("reference-memory-image-matches",
          hashlib.sha256(adapter.state.memory.snapshot()).hexdigest()
          == hashlib.sha256(bytes(expected_memory_image())).hexdigest())
    frame_snapshot = {
        "width": adapter.state.frames[0].width,
        "height": adapter.state.frames[0].height,
        "format": adapter.state.frames[0].pixel_format.value,
        "checksum": fnv1a64(adapter.state.frames[0].payload),
    }
    audio_snapshot = {
        "rate": adapter.state.audio[0].sample_rate,
        "channels": adapter.state.audio[0].channels,
        "frames": adapter.state.audio[0].frames,
        "format": adapter.state.audio[0].sample_format.value,
        "checksum": fnv1a64(adapter.state.audio[0].payload),
    }
    check("reference-frame-descriptor", frame_snapshot == {"width": 2, "height": 2, "format": "RGBA8",
                                                            "checksum": fnv1a64(FRAME_BYTES)})
    check("reference-audio-descriptor", audio_snapshot == {"rate": 8000, "channels": 1, "frames": 4,
                                                            "format": "U8", "checksum": fnv1a64(AUDIO_BYTES)})

    # L. native non-NES runtime integration ----------------------------------
    expected_text = expected_observable()
    workspace = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p240-"))
    comparison = None
    actual = ""
    exe_sha = ""
    native_returncode = None
    unsupported_lines: list[str] = []
    try:
        comparison = bp.build_generated_host_from(
            lambda: run_pipeline()["host"],
            support_sources=(
                bp.BuildSource("runtime_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                               support_source(staging["table"], audio_supported=True).encode("utf-8")),
            ),
            config=bp.BuildConfig(fixture_id=FIXTURE_ID, expected_smoke_output=expected_text),
            workspace=workspace,
            keep_workspace=True,
        )
        check("build-status-ok", all(run.manifest.build_status is bp.BuildStatus.OK for run in comparison.runs))
        check("build-classification-executable-reproducible",
              comparison.classification is bp.BuildReproducibility.EXECUTABLE_REPRODUCIBLE)
        check("build-source-reproducible", comparison.source_reproducible)
        check("build-manifest-reproducible", comparison.manifest_reproducible)
        check("build-object-reproducible", comparison.object_reproducible is True)
        check("build-executable-reproducible", comparison.executable_reproducible is True)
        manifest = comparison.runs[0].manifest
        check("build-brepro",
              all("/Brepro" in command for command in manifest.compile_commands) and "/Brepro" in manifest.link_command)
        check("build-manifest-deterministic", manifest.serialize() == comparison.runs[1].manifest.serialize())
        manifest_text = manifest.serialize().decode("utf-8")
        check("build-manifest-no-path-leak",
              str(ROOT) not in manifest_text and str(workspace) not in manifest_text)
        check("build-manifest-no-identity",
              (not os.environ.get("USERNAME") or os.environ["USERNAME"] not in manifest_text)
              and (not os.environ.get("COMPUTERNAME") or os.environ["COMPUTERNAME"] not in manifest_text))

        executable = workspace / "run1" / "program.exe"
        exe_sha = hashlib.sha256(executable.read_bytes()).hexdigest()
        check("native-executable-hash-matches-manifest",
              manifest.artifact_map(bp.BuildArtifactKind.EXECUTABLE).get("program.exe") == exe_sha)
        first = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        second = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        actual = (first.stdout or "").strip()
        native_returncode = first.returncode
        check("native-returncode-zero", first.returncode == 0)
        check("native-output-stable", actual == (second.stdout or "").strip())
        check("expected-equals-actual", expected_text == actual)
        check("native-frame-record", f"frame_count=1" in actual and f"frame[0]=2x2 format=RGBA8" in actual
              and f"checksum={fnv1a64(FRAME_BYTES)}" in actual)
        check("native-audio-record", "audio_count=1" in actual and "audio[0]=8000Hz channels=1 frames=4 format=U8" in actual
              and f"checksum={fnv1a64(AUDIO_BYTES)}" in actual)
        check("native-input-poll-line", f"input_poll={INPUT_POLL_VALUE}" in actual)
        check("native-register-values",
              f"reg[1]={FRAME_PTR}" in actual and f"reg[2]={AUDIO_PTR}" in actual
              and f"reg[3]={INPUT_POLL_VALUE}" in actual and f"reg[4]={INPUT_POLL_VALUE + 7}" in actual)
        check("native-memory-checksum", f"memory_checksum={fnv1a64(bytes(expected_memory_image()))}" in actual)

        unsupported_workspace = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p240-unsupported-"))
        try:
            bp.build_generated_host_from(
                lambda: run_pipeline()["host"],
                support_sources=(
                    bp.BuildSource("runtime_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                                   support_source(staging["table"], audio_supported=False).encode("utf-8")),
                ),
                config=bp.BuildConfig(fixture_id=FIXTURE_ID + "-unsupported", smoke_test=False),
                workspace=unsupported_workspace,
                keep_workspace=True,
            )
            unsupported_exe = unsupported_workspace / "run1" / "program.exe"
            ran = subprocess.run([str(unsupported_exe)], capture_output=True, text=True, encoding="utf-8", errors="replace")
            unsupported_stdout = (ran.stdout or "").strip()
            check("unsupported-service-fails-closed", unsupported_stdout.startswith("failed=1"))
            check("unsupported-service-error",
                  f"error=runtime host service {SERVICE_AUDIO} failed" in unsupported_stdout)
            check("unsupported-service-no-audio", "audio_count=0" in unsupported_stdout)
            check("unsupported-service-no-continuation",
                  "input_poll=0" in unsupported_stdout and "reg[3]=0" in unsupported_stdout and "reg[4]=0" in unsupported_stdout)
            check("unsupported-service-frame-still-submitted", "frame_count=1" in unsupported_stdout)
            unsupported_lines = [
                f"declared service: {SERVICE_AUDIO} (ABI id {staging['table'].numeric_id(SERVICE_AUDIO)})",
                "support-source variant: returns nonzero for the declared audio service (unsupported at runtime)",
                f"executable returncode: {ran.returncode}",
                "stdout:", unsupported_stdout,
                "result: PASS (the generated code stopped at the failed host call; the continuation did not run)",
            ]
        finally:
            shutil.rmtree(unsupported_workspace, ignore_errors=True)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    # M. NES runtime adapter (existing platform path) ------------------------
    nes_adapter = nes_rt.NESRuntimeAdapter(prg_rom=NES_PRG_ROM, mapper=0)
    check("nes-adapter-services-declared",
          nes_adapter.services.service_ids == ("nes.audio.submit", "nes.frame.submit"))
    nes_adapter.set_input(NES_INPUT)
    nes_adapter.cpu_write(0x4016, 1)
    nes_adapter.cpu_write(0x4016, 0)
    controller_bits = tuple(nes_adapter.cpu_read(0x4016) & 1 for _ in range(8))
    check("nes-adapter-input-mapping", controller_bits == tuple(1 if value else 0 for value in INPUT_DIGITAL))
    for offset, value in enumerate(NES_FRAME_BYTES):
        nes_adapter.cpu_write(0x0100 + offset, value)
    for offset, value in enumerate(NES_AUDIO_BYTES):
        nes_adapter.cpu_write(0x0200 + offset, value)
    nes_frame_call = nes_adapter.state.host_call("nes.frame.submit", (0x0100, 2, 2, 0))
    nes_audio_call = nes_adapter.state.host_call("nes.audio.submit", (0x0200, 8000, 1, 4, 0))
    check("nes-adapter-frame-submission",
          nes_frame_call.ok and len(nes_adapter.state.frames) == 1
          and nes_adapter.state.frames[0].payload == NES_FRAME_BYTES
          and nes_adapter.state.frames[0].pixel_format is rt.RuntimePixelFormat.RGBA8)
    check("nes-adapter-audio-submission",
          nes_audio_call.ok and len(nes_adapter.state.audio) == 1
          and nes_adapter.state.audio[0].payload == NES_AUDIO_BYTES
          and nes_adapter.state.audio[0].sample_format is rt.RuntimeSampleFormat.U8)
    check("nes-adapter-generic-state-records",
          len(nes_adapter.state.host_calls) == 2
          and nes_adapter.state.host_calls[0].service == "nes.frame.submit")
    nes_arity = nes_adapter.state.host_call("nes.frame.submit", (0x0100, 2, 2))
    check("nes-adapter-arity-fails-closed",
          not nes_arity.ok and nes_arity.failure is not None
          and nes_arity.failure.code is rt.RuntimeFailureCode.HOST_CALL_ARITY)
    nes_bad_format = nes_adapter.state.host_call("nes.frame.submit", (0x0100, 2, 2, 9))
    check("nes-adapter-unsupported-format-fails-closed",
          not nes_bad_format.ok and nes_bad_format.failure is not None
          and nes_bad_format.failure.code is rt.RuntimeFailureCode.HOST_SERVICE_FAILED)
    expect_fail("nes-adapter-unsupported-mapper",
                lambda: nes_rt.NESRuntimeAdapter(mapper=1), nes_rt.NESRuntimeError)
    expect_fail("nes-adapter-ppu-register-read", lambda: nes_adapter.cpu_read(0x2000), nes_rt.NESRuntimeError)
    expect_fail("nes-adapter-expansion-read", lambda: nes_adapter.cpu_read(0x4020), nes_rt.NESRuntimeError)
    check("nes-synthetic-share-generic-dispatch",
          type(nes_adapter.services) is rt.RuntimeServiceTable
          and type(adapter.state.services) is rt.RuntimeServiceTable
          and nes_adapter.services.dispatch.__func__ is rt.RuntimeServiceTable.dispatch
          and adapter.state.services.dispatch.__func__ is rt.RuntimeServiceTable.dispatch)
    check("nes-service-names-adapter-local",
          "nes.frame.submit" not in runtime_abi_source and "nes.audio.submit" not in runtime_abi_source)

    # N. regressions, host gates and source integrity ------------------------
    regression_results: list[dict[str, object]] = []
    regression_failures: list[dict[str, object]] = []
    if args.skip_regressions:
        print("SKIP: regression suite (development flag)")
    else:
        for name, script in REGRESSION_TESTS:
            completed = run_command([args.python, script], args.python)
            record = {
                "name": name,
                "script": script,
                "returncode": completed.returncode,
                "stdout_sha256": hashlib.sha256((completed.stdout or "").encode("utf-8")).hexdigest(),
            }
            regression_results.append(record)
            if completed.returncode != 0:
                regression_failures.append({"name": name, "stderr": (completed.stderr or "")[-2000:]})
                print(f"FAIL regression {name}")
            else:
                print(f"PASS regression {name}")
        check("regression-suite", not regression_failures)

    source_integrity = run_command([args.python, "tools/phase1_host_gates_v1.py", "--only", "source-integrity"], args.python)
    check("source-integrity",
          source_integrity.returncode == 0 and "source-integrity" in (source_integrity.stdout or "")
          and "verified" in (source_integrity.stdout or ""))

    if args.skip_regressions:
        print("SKIP: phase1-host-gates (development flag)")
    else:
        host_gates_json = evidence_dir / "host_gates.json"
        host_gates = run_command(
            [args.python, "tools/phase1_host_gates_v1.py", "--json", str(host_gates_json)], args.python
        )
        check("phase1-host-gates",
              host_gates.returncode == 0 and "OPENRECOMP_PHASE1_HOST_GATES_V1=PASS" in (host_gates.stdout or ""))

    # O. evidence + result record --------------------------------------------
    static_findings = {
        "audited_modules": list(AUDITED_RUNTIME_MODULES),
        "import_isolation": import_findings,
        "symbol_isolation": module_symbol_findings,
        "address_isolation": module_address_findings,
        "host_state_imports": host_state_findings,
        "scanner_self_test": {
            "planted_symbol_findings": planted_symbols,
            "planted_address_findings": planted_addresses,
            "clean_symbol_findings": clean_symbols,
            "clean_address_findings": clean_addresses,
        },
        "concept_classification": [
            {"concept": concept, "layer": layer, "reference": reference}
            for concept, layer, reference in CONCEPT_CLASSIFICATION
        ],
        "backend_extension_points": list(BACKEND_EXTENSION_POINTS),
    }

    result = {
        "stage": "P2-40",
        "marker": "OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1",
        "status": "PASS",
        "tests": len(RESULTS),
        "passed": sum(1 for item in RESULTS if item["status"] == "PASS"),
        "failed": sum(1 for item in RESULTS if item["status"] == "FAIL"),
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": static_findings,
        "fixture_id": FIXTURE_ID,
        "fixture_sha256": FIXTURE_SHA256,
        "fixture_byte_length": len(FIXTURE_BYTES),
        "services": list(staging["table"].service_ids),
        "generated_source_sha256": host.fingerprint(),
        "expected_observable": expected_text,
        "actual_observable": actual,
        "expected_equals_actual": expected_text == actual,
        "executable_sha256": exe_sha,
        "native_returncode": native_returncode,
        "build_classification": comparison.classification.value if comparison else None,
        "regressions": regression_results,
        "regression_failures": regression_failures,
    }

    if args.evidence_dir:
        evidence_path = pathlib.Path(args.evidence_dir)
        evidence_path.mkdir(parents=True, exist_ok=True)
        evidence_hashes = write_evidence(evidence_path, {
            "cfg": cfg,
            "discovery": discovery,
            "units": units,
            "classification": classification,
            "host": host,
            "table": staging["table"],
            "comparison": comparison,
            "expected_output": expected_text,
            "actual_output": actual,
            "exe_sha256": exe_sha,
            "native_returncode": native_returncode,
            "unsupported_lines": unsupported_lines,
            "nes_lines": [
                f"adapter: openrecomp.frontends.nes_runtime.NESRuntimeAdapter",
                f"declared services: {list(nes_adapter.services.service_ids)}",
                f"controller bits read through $4016: {''.join(str(bit) for bit in controller_bits)}",
                f"frame submissions: {len(nes_adapter.state.frames)} (payload checksum {hashlib.sha256(NES_FRAME_BYTES).hexdigest()})",
                f"audio submissions: {len(nes_adapter.state.audio)} (payload checksum {hashlib.sha256(NES_AUDIO_BYTES).hexdigest()})",
                f"host-call records: {[record.service for record in nes_adapter.state.host_calls]}",
                "unsupported mapper, PPU register access, expansion access, arity mismatch and unsupported",
                "format ids fail closed through the same generic dispatch used by the synthetic adapter.",
            ],
            "static_findings": static_findings,
            "cfg_evidence": evidence_path / "pipeline_cfg.txt",
        })
        (evidence_path / "regression_results.json").write_text(
            json.dumps(regression_results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (evidence_path / "source_integrity.txt").write_text(source_integrity.stdout or "", encoding="utf-8")
        (evidence_path / "p2_40_tests.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("EVIDENCE_FILES:", ", ".join(sorted(evidence_hashes)))

    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    print("\n=== RESULT ===")
    print("OPENRECOMP_P2_40=PASS")
    print(f"OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
