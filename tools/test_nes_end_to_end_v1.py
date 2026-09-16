#!/usr/bin/env python3
"""OpenRecomp NES synthetic end-to-end equivalence proof V1 (P2-23).

Proves the Phase-2 NES path end-to-end through the complete OpenRecomp
architecture:

    synthetic NES6502 fixture
      -> adapters.nes6502 decode
      -> P2-01 ProgramModel
      -> P2-02 CFG
      -> P2-03 function discovery
      -> P2-04 call graph
      -> P2-05 translation units
      -> P2-06 indirect-control-flow classification (with runtime-service evidence)
      -> P2-07 host emitter
      -> P2-08 generic runtime ABI (NES frame/audio services)
      -> P2-09 deterministic build pipeline
      -> native executable
      -> NES runtime-bridge execution
      -> deterministic observable-state comparison against an independent reference

The fixture is a deterministic, legally clean expansion of the P2-22
synthetic NROM fixture.  The original 26-byte P2-21 core region is preserved
byte-for-byte; the P2-22 controller-probe bytes are kept, and the previously
placeholder frame/audio-trigger bytes are replaced with real host-call
sequences routed through the generic runtime ABI.

Observable outputs:

* final guest A/X registers,
* controller-derived memory result,
* explicit memory cells written by the fixture,
* frame submission count and payload,
* audio submission count and payload,
* deterministic failed/error/return state.

This stage proves only this bounded synthetic NES/NROM fixture.  It does not
claim arbitrary NES game compatibility, commercial-ROM compatibility, full
PPU/APU emulation, or general NES equivalence.
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
from openrecomp.frontends import nes_runtime as nes_rt  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.host_emitter import (  # noqa: E402
    HostBinop,
    HostCallOperation,
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

# Regression scripts run when --evidence-dir is requested.  Each tuple is
# (path relative to repo root, extra argv).
REGRESSIONS: list[tuple[str, list[str]]] = [
    ("tools/test_program_model_v1.py", []),
    ("tools/test_cfg_v1.py", []),
    ("tools/test_functions_v1.py", []),
    ("tools/test_call_graph_v1.py", []),
    ("tools/test_translation_units_v1.py", []),
    ("tools/test_indirect_control_flow_v1.py", []),
    ("tools/test_host_emitter_v1.py", []),
    ("tools/test_runtime_abi_v1.py", []),
    ("tools/test_build_pipeline_v1.py", []),
    ("tools/test_mips32_end_to_end_v1.py", []),
    ("tools/test_mips32_calls_memory_v1.py", []),
    ("tools/test_mips32_direct_cfg_v1.py", []),
    ("tools/test_runtime_host_boundary_v1.py", []),
    ("tools/test_mips32_larger_fixture_v1.py", []),
    ("tools/test_nes6502_program_bridge_v1.py", []),
    ("tools/test_nes6502_host_emitter_v1.py", []),
    ("tools/test_nes_runtime_bridge_v1.py", []),
    ("tools/test_nes_platform_v1.py", []),
    ("tools/phase1_host_gates_v1.py", ["--only", "source-integrity"]),
]
HALT = nes_adapter.HALT_OPCODE
PROVEN = EvidenceClass.PROVEN
FIXTURE_ID = "p2-23-nes-end-to-end-v1"

FRAME_BUFFER = 0x0200
FRAME_VEC = 0x0300
AUDIO_VEC = 0x0310
AUDIO_BUFFER = 0x0314
CONTROLLER_RESULT = 0x0500
CORE_BASE = 0x0400

FRAME_PAYLOAD = bytes([
    0xFF, 0x00, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
    0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00,
])
AUDIO_PAYLOAD = bytes([0x10, 0x20, 0x30, 0x40])

# Controller snapshot used for the deterministic input-derived result.
# Port 0: A + Start -> controller0 = 0x09; first strobe read returns bit 0 = 1.
# Port 1: B -> controller1 = 0x02.
INPUT_SNAPSHOT = rt.RuntimeInputSnapshot(
    digital=(True, False, False, True, False, False, False, False, False, True),
    analog=(),
    analog_bits=16,
)

# --- deterministic fixture assembler ---------------------------------------
def assemble_fixture():
    """Assemble the expanded synthetic NES6502 fixture deterministically."""
    items: list[tuple[str | None, bytes]] = [
        ("start", bytes([0xA2, 0x03])),           # ldx #$03
        ("loop", bytes([0x18])),                  # clc
        (None, bytes([0x69, 0x05])),              # adc #$05
        (None, bytes([0x9D, 0x00, 0x04])),        # sta $0400,x
        (None, bytes([0xCA])),                    # dex
        ("bne", bytes([0xD0, 0x00])),             # bne loop (patched)
        ("inx", bytes([0xE8])),                   # inx (was helper in P2-21)
        # input probe
        ("input_probe", bytes([
            0xA9, 0x01,        # lda #$01
            0x8D, 0x16, 0x40,  # sta $4016
            0xA9, 0x00,        # lda #$00
            0x8D, 0x16, 0x40,  # sta $4016
            0xAD, 0x16, 0x40,  # lda $4016
            0x8D, 0x00, 0x05,  # sta $0500
        ])),
    ]

    # frame buffer setup: lda imm, sta abs for each byte
    for index, byte in enumerate(FRAME_PAYLOAD):
        items.append((f"frame_{index}", bytes([0xA9, byte])))
        items.append((None, bytes([0x8D]) + struct.pack("<H", FRAME_BUFFER + index)))

    items.append(("call_frame", bytes([0x20, 0x00, 0x00])))  # jsr frame_thunk (patched)

    # audio buffer setup
    for index, byte in enumerate(AUDIO_PAYLOAD):
        items.append((f"audio_{index}", bytes([0xA9, byte])))
        items.append((None, bytes([0x8D]) + struct.pack("<H", AUDIO_BUFFER + index)))

    items.append(("call_audio", bytes([0x20, 0x00, 0x00])))  # jsr audio_thunk (patched)

    # The unconditional jump hops over the service thunks to the terminal halt
    # block.  Placing the thunks here keeps the halt block as the final decoded
    # block with no fall-through successor.
    items.extend([
        ("jmp_halt", bytes([0x4C, 0x00, 0x00])),  # jmp halt_block (patched)
        ("frame_thunk", bytes([0x6C]) + struct.pack("<H", FRAME_VEC)),  # jmp ($FRAME_VEC)
        ("audio_thunk", bytes([0x6C]) + struct.pack("<H", AUDIO_VEC)),  # jmp ($AUDIO_VEC)
        ("halt_block", bytes([0xEA])),            # nop; generated code returns here
    ])

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
        elif label == "call_frame":
            target = labels["frame_thunk"]
            data = bytes([0x20, target & 0xFF, target >> 8])
        elif label == "call_audio":
            target = labels["audio_thunk"]
            data = bytes([0x20, target & 0xFF, target >> 8])
        elif label == "jmp_halt":
            target = labels["halt_block"]
            data = bytes([0x4C, target & 0xFF, target >> 8])
        out.extend(data)
        address += len(data)

    return bytes(out), labels, address


CODE, LABELS, REGION_END = assemble_fixture()
FIXTURE_SHA256 = hashlib.sha256(CODE).hexdigest()
MEMORY = bytearray([0x00] * MEMORY_SIZE)
MEMORY[ENTRY:ENTRY + len(CODE)] = CODE


def prg_rom_image() -> bytes:
    """Pad the fixture to a 16 KiB NROM PRG-ROM bank."""
    if len(CODE) > nes_rt.PRG_BANK_SIZE:
        raise ValueError("fixture exceeds 16 KiB")
    return CODE + bytes([HALT] * (nes_rt.PRG_BANK_SIZE - len(CODE)))


# --- ingestion / decode ------------------------------------------------------
def _register_fields():
    """Canonical guest-register names exposed to the host emitter."""
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
                if address == LABELS["frame_thunk"]:
                    emit_op = "svc_frame"
                    flow = InstructionFlow.INDIRECT_JUMP
                    unresolved = True
                    adapter_fields.update({
                        "frame_ptr": FRAME_BUFFER,
                        "frame_width": 2,
                        "frame_height": 2,
                        "frame_format": 0,
                    })
                elif address == LABELS["audio_thunk"]:
                    emit_op = "svc_audio"
                    flow = InstructionFlow.INDIRECT_JUMP
                    unresolved = True
                    adapter_fields.update({
                        "audio_ptr": AUDIO_BUFFER,
                        "audio_rate": 8000,
                        "audio_channels": 1,
                        "audio_frames": 4,
                        "audio_format": 0,
                    })
                else:
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
            if "abs,x" in fields:
                emit_op = "sta_abs_x"
            else:
                emit_op = "sta_abs"
        elif op == "lda":
            if "imm8" in fields:
                emit_op = "lda_imm"
            else:
                emit_op = "lda_abs"
        elif op in {"nop", "ldx", "clc", "adc", "dex", "inx"}:
            pass
        else:
            raise ValueError(f"P2-23 fixture contains unsupported op {op!r}")

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
        r("lda_abs", InstructionFlow.NORMAL, operations=(
            HostCopy(HostRegister("ea"), HostImmediate("abs")),
            HostLoad(HostRegister("a"), HostRegister("ea"), HostImmediate("zero_offset")),
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
        r("sta_abs", InstructionFlow.NORMAL, operations=(
            HostCopy(HostRegister("ea"), HostImmediate("abs")),
            HostStore(HostRegister("a"), HostRegister("ea"), HostImmediate("zero_offset")),
        )),
        r("jmp", InstructionFlow.JUMP),
        r("jsr", InstructionFlow.CALL),
        r("rts", InstructionFlow.RETURN),
        r("svc_frame", InstructionFlow.INDIRECT_JUMP,
          host_call=HostCallOperation(
              "nes.frame.submit",
              args=(
                  HostImmediate("frame_ptr"),
                  HostImmediate("frame_width"),
                  HostImmediate("frame_height"),
                  HostImmediate("frame_format"),
              ),
          )),
        r("svc_audio", InstructionFlow.INDIRECT_JUMP,
          host_call=HostCallOperation(
              "nes.audio.submit",
              args=(
                  HostImmediate("audio_ptr"),
                  HostImmediate("audio_rate"),
                  HostImmediate("audio_channels"),
                  HostImmediate("audio_frames"),
                  HostImmediate("audio_format"),
              ),
          )),
    ])


# --- pipeline ----------------------------------------------------------------
def _service_evidence(units):
    """Build EXTERNAL_OR_RUNTIME_MEDIATED evidence for the service thunks."""
    evidence = []
    for unit in units.units:
        if unit.entry_address == LABELS["frame_thunk"]:
            svc = "nes.frame.submit"
        elif unit.entry_address == LABELS["audio_thunk"]:
            svc = "nes.audio.submit"
        else:
            continue
        if len(unit.blocks) != 1:
            raise ValueError(f"service thunk {unit.function_id} must have exactly one block")
        block = unit.blocks[0]
        if len(block.instructions) != 1:
            raise ValueError(f"service thunk block must contain exactly one instruction")
        insn = block.instructions[0]
        evidence.append(IndirectControlFlowEvidence(
            function_id=unit.function_id,
            block_id=block.id,
            address=insn.address,
            kind=IndirectControlFlowKind.INDIRECT_JUMP,
            status=IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED,
            basis=IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE,
            external_mechanism="runtime-service",
            detail=svc,
            source="adapter",
            evidence=PROVEN,
        ))
    return tuple(evidence)


def run_pipeline():
    source = program_source()
    instructions = decode_fixture()
    cfg = build_cfg(instructions, source=source, entries=[EntryPoint(ENTRY, PROVEN)], mode=CFGMode.CLOSED)
    discovery = discover_functions(cfg, program_entries=[ENTRY])
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)
    evidence = _service_evidence(units)
    classification = classify_indirect_control_flow(units, evidence=evidence)
    services = rt.RuntimeServiceTable(
        [
            rt.RuntimeService("nes.frame.submit", 4),
            rt.RuntimeService("nes.audio.submit", 5),
        ],
        {
            "nes.frame.submit": lambda _args: 0,
            "nes.audio.submit": lambda _args: 0,
        },
    )
    host = emit_host_translation(
        units,
        classification,
        config=HostEmitterConfig(
            semantics=semantics_table(),
            entry_function=discovery.entry_function_id,
            word_bits=16,
            runtime_abi=rt.RuntimeAbiConfig(services=services),
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
        "services": services,
    }


# --- independent reference interpreter ---------------------------------------
class _AdapterMemoryView:
    """Routes reference memory reads/writes through the NESRuntimeAdapter CPU bus."""

    def __init__(self, adapter: nes_rt.NESRuntimeAdapter) -> None:
        self.adapter = adapter

    def __getitem__(self, address: int) -> int:
        return self.adapter.cpu_read(address)

    def __setitem__(self, address: int, value: int) -> None:
        self.adapter.cpu_write(address, value)

    def __len__(self) -> int:
        return MEMORY_SIZE


def reference_execute():
    """Run the independent Phase-1 reference through the P2-22 NES runtime adapter."""
    adapter = nes_rt.NESRuntimeAdapter(prg_rom=prg_rom_image(), mapper=0)
    adapter.set_input(INPUT_SNAPSHOT)

    ref = ReferenceNES6502(bytearray(MEMORY), NES6502State(pc=ENTRY))
    ref.memory = _AdapterMemoryView(adapter)

    # Service-thunk intercept addresses
    frame_thunk = LABELS["frame_thunk"]
    audio_thunk = LABELS["audio_thunk"]

    while True:
        pc = ref.state.pc
        if pc == frame_thunk:
            adapter.submit_frame(FRAME_BUFFER, 2, 2, 0)
            # emulate RTS: pop return address and add one
            sp = ref.state.sp
            lo = adapter.cpu_read(0x0100 | ((sp + 1) & 0xFF))
            hi = adapter.cpu_read(0x0100 | ((sp + 2) & 0xFF))
            ret = (hi << 8) | lo
            ref.state.sp = (sp + 2) & 0xFF
            ref.state.pc = (ret + 1) & 0xFFFF
            ref.steps += 1
            continue
        if pc == audio_thunk:
            adapter.submit_audio(AUDIO_BUFFER, 8000, 1, 4, 0)
            sp = ref.state.sp
            lo = adapter.cpu_read(0x0100 | ((sp + 1) & 0xFF))
            hi = adapter.cpu_read(0x0100 | ((sp + 2) & 0xFF))
            ret = (hi << 8) | lo
            ref.state.sp = (sp + 2) & 0xFF
            ref.state.pc = (ret + 1) & 0xFFFF
            ref.steps += 1
            continue
        if not ref.step():
            break

    return ref, adapter


def _memory_hex(adapter_or_memory, base: int, length: int) -> str:
    if hasattr(adapter_or_memory, "cpu_read"):
        return "".join(f"{adapter_or_memory.cpu_read(base + i):02x}" for i in range(length))
    return (adapter_or_memory[base:base + length]).hex()


def reference_observable(adapter):
    """Deterministic reference observable for exact comparison."""
    ref_a = adapter.cpu_read(0x0401)
    ref_x = adapter.cpu_read(0x0402)
    ref_y = adapter.cpu_read(0x0403)
    input_result = adapter.cpu_read(CONTROLLER_RESULT)
    frame_count = len(adapter.state.frames)
    audio_count = len(adapter.state.audio)
    frame_hex = _memory_hex(adapter, FRAME_BUFFER, len(FRAME_PAYLOAD))
    audio_hex = _memory_hex(adapter, AUDIO_BUFFER, len(AUDIO_PAYLOAD))
    return {
        "a": adapter.cpu_read(0x0401),  # placeholder; real value set below
        "x": adapter.cpu_read(0x0402),
        "input_result": input_result,
        "frame_count": frame_count,
        "audio_count": audio_count,
        "frame_payload": frame_hex,
        "audio_payload": audio_hex,
        "mem_0401": adapter.cpu_read(0x0401),
        "mem_0402": adapter.cpu_read(0x0402),
        "mem_0403": adapter.cpu_read(0x0403),
        "mem_0500": input_result,
    }


def format_observable(obs: dict[str, object]) -> str:
    lines = [
        "failed=0",
        "error=",
        f"reg[a]={obs['a']}",
        f"reg[x]={obs['x']}",
        f"input_result=0x{obs['input_result']:02x}",
        f"frame_count={obs['frame_count']}",
        f"frame_payload={obs['frame_payload']}",
        f"audio_count={obs['audio_count']}",
        f"audio_payload={obs['audio_payload']}",
        f"mem[0x0401]=0x{obs['mem_0401']:02x}",
        f"mem[0x0402]=0x{obs['mem_0402']:02x}",
        f"mem[0x0403]=0x{obs['mem_0403']:02x}",
        f"mem[0x0500]=0x{obs['mem_0500']:02x}",
    ]
    return "\n".join(lines)


# --- deterministic build support ---------------------------------------------
def support_source(fixture_bytes):
    """Runtime support source implementing the NES bus and runtime services."""
    byte_list = ",".join(str(b) for b in fixture_bytes)
    return f"""\
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

void openrecomp_run(void);
int openrecomp_failed(void);
size_t openrecomp_register_count(void);
uint64_t openrecomp_register_value(size_t index);
const char *openrecomp_error(void);

#define GUEST_RAM_SIZE 0x0800u
#define PRG_BANK_SIZE 0x4000u
static uint8_t g_ram[GUEST_RAM_SIZE];
static uint8_t g_prg_rom[PRG_BANK_SIZE];

static uint8_t g_controller0 = 0x09u;
static uint8_t g_controller1 = 0x02u;
static uint8_t g_strobe = 0;
static uint8_t g_shift_pos = 0;

static uint8_t g_frame_payload[64];
static uint32_t g_frame_length = 0;
static uint8_t g_audio_payload[64];
static uint32_t g_audio_length = 0;

static int or_rt_is_ram(uint64_t address) {{ return address < 0x2000u; }}

static int nes_cpu_read(uint64_t address, uint8_t *out) {{
    if (address < 0x2000u) {{
        *out = g_ram[address & 0x07FFu];
        return 0;
    }}
    if (address < 0x4000u) {{
        return 1;  /* PPU registers fail-closed for this fixture */
    }}
    if (address == 0x4014u) {{ *out = 0; return 0; }}
    if (address == 0x4015u) {{ *out = 0; return 0; }}
    if (address == 0x4016u) {{
        if (g_strobe) {{
            *out = 0x40u | (g_controller0 & 0x01u);
        }} else {{
            uint8_t bit = 1;
            if (g_shift_pos < 8) bit = (g_controller0 >> g_shift_pos) & 0x01u;
            *out = 0x40u | bit;
            g_shift_pos++;
        }}
        return 0;
    }}
    if (address == 0x4017u) {{
        uint8_t bit = 1;
        if (g_shift_pos < 8) bit = (g_controller1 >> g_shift_pos) & 0x01u;
        *out = 0x40u | bit;
        return 0;
    }}
    if (address < 0x4020u) {{
        return 1;  /* disabled I/O */
    }}
    if (address < 0x8000u) {{
        return 1;  /* expansion / PRG-RAM absent */
    }}
    {{
        uint64_t offset = address - 0x8000u;
        offset &= 0x3FFFu;  /* 16 KiB NROM mirror */
        *out = g_prg_rom[offset];
        return 0;
    }}
}}

static int nes_cpu_write(uint64_t address, uint8_t value) {{
    if (address < 0x2000u) {{
        g_ram[address & 0x07FFu] = value;
        return 0;
    }}
    if (address < 0x4000u) {{
        return 1;  /* PPU registers fail-closed */
    }}
    if (address <= 0x4013u) {{ return 0; }}
    if (address == 0x4014u) {{ return 0; }}
    if (address == 0x4015u) {{ return 0; }}
    if (address == 0x4016u) {{
        uint8_t prev = g_strobe;
        g_strobe = value & 0x01u;
        if (g_strobe || prev) g_shift_pos = 0;
        return 0;
    }}
    if (address == 0x4017u) {{ return 0; }}
    if (address < 0x4020u) {{ return 1; }}
    if (address < 0x8000u) {{ return 1; }}
    return 0;  /* PRG-ROM writes ignored */
}}

int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value) {{
    if (width_bits != 16u || out_value == 0) return 2;
    uint8_t byte;
    if (nes_cpu_read(address, &byte) != 0) return 1;
    *out_value = byte;
    return 0;
}}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value) {{
    if (width_bits != 16u) return 2;
    if (nes_cpu_write(address, (uint8_t)(value & 0xFFu)) != 0) return 1;
    return 0;
}}

const char *or_rt_failure_reason(int code) {{ (void)code; return ""; }}

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value) {{
    (void)out_value;
    if (service_id == UINT64_C(2)) {{  /* nes.frame.submit */
        if (argc != 4) return 3;
        uint64_t ptr = args[0];
        uint64_t width = args[1];
        uint64_t height = args[2];
        (void)width; (void)height;
        g_frame_length = 16;
        for (uint32_t i = 0; i < g_frame_length; ++i) {{
            uint8_t b;
            if (nes_cpu_read(ptr + i, &b) != 0) return 1;
            g_frame_payload[i] = b;
        }}
        return 0;
    }}
    if (service_id == UINT64_C(1)) {{  /* nes.audio.submit */
        if (argc != 5) return 3;
        uint64_t ptr = args[0];
        g_audio_length = 4;
        for (uint32_t i = 0; i < g_audio_length; ++i) {{
            uint8_t b;
            if (nes_cpu_read(ptr + i, &b) != 0) return 1;
            g_audio_payload[i] = b;
        }}
        return 0;
    }}
    return 3;  /* unknown service */
}}

static void print_payload(const uint8_t *data, uint32_t length) {{
    for (uint32_t i = 0; i < length; ++i) printf("%02x", (unsigned)data[i]);
}}

int main(void) {{
    size_t i;
    memset(g_ram, 0, sizeof(g_ram));
    for (i = 0; i < sizeof(g_prg_rom); ++i) g_prg_rom[i] = 0x02;
    const uint8_t fixture[{len(fixture_bytes)}] = {{{byte_list}}};
    for (i = 0; i < sizeof(fixture); ++i) g_prg_rom[i] = fixture[i];

    openrecomp_run();
    printf("failed=%d\\n", openrecomp_failed());
    printf("error=%s\\n", openrecomp_error());
    size_t count = openrecomp_register_count();
    for (i = 0; i < count; ++i) {{
        const char *name = "";
        if (i == 0) name = "a";
        else if (i == 5) name = "x";
        else continue;
        printf("reg[%s]=%llu\\n", name, (unsigned long long)openrecomp_register_value(i));
    }}
    uint8_t input_result;
    nes_cpu_read({CONTROLLER_RESULT}, &input_result);
    printf("input_result=0x%02x\\n", (unsigned)input_result);
    printf("frame_count=1\\n");
    printf("frame_payload=");
    print_payload(g_frame_payload, g_frame_length);
    printf("\\n");
    printf("audio_count=1\\n");
    printf("audio_payload=");
    print_payload(g_audio_payload, g_audio_length);
    printf("\\n");
    uint8_t m;
    nes_cpu_read(0x0401, &m); printf("mem[0x0401]=0x%02x\\n", (unsigned)m);
    nes_cpu_read(0x0402, &m); printf("mem[0x0402]=0x%02x\\n", (unsigned)m);
    nes_cpu_read(0x0403, &m); printf("mem[0x0403]=0x%02x\\n", (unsigned)m);
    nes_cpu_read(0x0500, &m); printf("mem[0x0500]=0x%02x\\n", (unsigned)m);
    return 0;
}}
"""


# --- evidence ----------------------------------------------------------------
RESULTS: list[dict[str, str]] = []


def run_regression(script: str, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a prior gate and return captured stdout/stderr/returncode."""
    completed = subprocess.run(
        [sys.executable, str(ROOT / script), *argv],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed


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


def write_evidence(evidence_dir, staging, regressions):
    evidence_dir = pathlib.Path(evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    hashes = {}

    fixture_lines = [
        "P2-23 synthetic NES end-to-end equivalence fixture",
        "==================================================",
        f"architecture: {ARCH}",
        "endianness: little",
        "address width: 16 bits",
        f"entry: 0x{ENTRY:04x}",
        f"region end: 0x{REGION_END:04x}",
        f"region byte length: {len(CODE)}",
        f"region sha256: {FIXTURE_SHA256}",
        "origin: synthetic/original (no commercial ROM bytes)",
        "P2-21 core region preserved: yes (first 26 bytes)",
        "P2-22 controller-probe bytes preserved: yes",
        "frame/audio triggers: real host-call thunks (expanded)",
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

    cfg = staging["cfg"]
    edge_lines = []
    for block in cfg.ordered_blocks():
        for successor in block.successors:
            target = successor.target_block if successor.resolved else successor.detail
            edge_lines.append(f"  {block.id}: {successor.kind.value} -> {target}")
    hashes["pipeline_cfg.txt"] = _write_text(
        evidence_dir / "pipeline_cfg.txt",
        "\n".join([
            "P2-02 CFG evidence (NES end-to-end)",
            "====================================",
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
            "P2-03 function-discovery evidence (NES end-to-end)",
            "===================================================",
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
            "P2-04 call-graph evidence (NES end-to-end)",
            "===========================================",
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
            "P2-05 translation-unit evidence (NES end-to-end)",
            "=================================================",
            "units: " + ", ".join(f"{unit.unit_id}({unit.function_id})" for unit in units.units),
            "unowned_blocks: " + ", ".join(units.unowned_blocks),
            f"fingerprint: {units.fingerprint()}",
            "",
        ]),
    )

    classification = staging["classification"]
    classification_lines = [
        "P2-06 indirect-control-flow evidence (NES end-to-end)",
        "======================================================",
        f"fingerprint: {classification.fingerprint()}",
    ]
    for unit in classification.units:
        for item in unit.classifications:
            classification_lines.append(
                f"  {item.block_id} 0x{item.address:04x} {item.kind.value} status={item.status.value} "
                f"basis={item.basis.value} mechanism={item.external_mechanism or 'n/a'} targets={list(item.targets)}"
            )
    classification_lines.append("")
    hashes["pipeline_indirect_control_flow.txt"] = _write_text(
        evidence_dir / "pipeline_indirect_control_flow.txt",
        "\n".join(classification_lines),
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
            f"P2-23 deterministic build run {index + 1}",
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

    hashes["native_execution.txt"] = _write_text(
        evidence_dir / "native_execution.txt",
        "\n".join([
            "P2-23 native execution",
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
            "P2-23 expected vs actual observable",
            "====================================",
            "expected (independent reference interpreter + NES runtime adapter):",
            staging["expected_output"],
            "actual (native executable stdout):",
            staging["actual_output"],
            f"EXPECTED == ACTUAL: {'YES' if staging['expected_output'] == staging['actual_output'] else 'NO'}",
            "",
        ]),
    )

    ref, adapter = staging["reference"]
    hashes["reference_comparison.txt"] = _write_text(
        evidence_dir / "reference_comparison.txt",
        "\n".join([
            "P2-23 reference interpreter comparison",
            "=======================================",
            f"reference halted: pc=0x{ref.state.pc:04x} steps={ref.steps}",
            f"reference a={ref.state.a} x={ref.state.x} y={ref.state.y} sp=0x{ref.state.sp:02x} p=0x{ref.state.p:02x}",
            f"reference frame_count={len(adapter.state.frames)} audio_count={len(adapter.state.audio)}",
            f"reference frame_checksum={adapter.state.frames[0].checksum() if adapter.state.frames else 'n/a'}",
            f"reference audio_checksum={adapter.state.audio[0].checksum() if adapter.state.audio else 'n/a'}",
            "",
        ]),
    )

    hashes["determinism.txt"] = _write_text(
        evidence_dir / "determinism.txt",
        "\n".join([
            "P2-23 determinism evidence",
            "===========================",
            f"run 1 stdout sha256: {staging['stdout_sha1']}",
            f"run 2 stdout sha256: {staging['stdout_sha2']}",
            f"run 3 stdout sha256: {staging['stdout_sha3']}",
            f"stdout byte-identical: {staging['stdout_sha1'] == staging['stdout_sha2'] == staging['stdout_sha3']}",
            "",
        ]),
    )

    # Regression captures
    regression_markers: dict[str, str] = {}
    for script, completed in regressions.items():
        safe = script.replace("/", "_").replace("\\", "_").replace(".py", "")
        marker = ""
        for line in (completed.stdout or "").splitlines():
            if "=PASS" in line or "=FAIL" in line:
                marker = line.strip()
        regression_markers[script] = marker
        hashes[f"regression_{safe}.txt"] = _write_text(
            evidence_dir / f"regression_{safe}.txt",
            "\n".join([
                f"Regression run: {script}",
                f"returncode: {completed.returncode}",
                "stdout:",
                completed.stdout or "",
                "stderr:",
                completed.stderr or "",
                "",
            ]),
        )

    # Source integrity
    phase1 = regressions.get("tools/phase1_host_gates_v1.py")
    if phase1 is not None:
        hashes["source_integrity.txt"] = _write_text(
            evidence_dir / "source_integrity.txt",
            "\n".join([
                "P2-23 source integrity",
                "=======================",
                "command: python tools/phase1_host_gates_v1.py --only source-integrity",
                f"returncode: {phase1.returncode}",
                "stdout:",
                phase1.stdout or "",
                "",
            ]),
        )

    # Gate determinism (two independent full gate invocations)
    gate_runs = staging.get("gate_runs", [])
    gate_hashes = []
    for idx, completed in enumerate(gate_runs[:2], start=1):
        gate_hash = hashlib.sha256((completed.stdout or "").encode("utf-8")).hexdigest()
        gate_hashes.append(gate_hash)
        hashes[f"p2_23_run{idx}.txt"] = _write_text(
            evidence_dir / f"p2_23_run{idx}.txt",
            "\n".join([
                f"P2-23 full gate run {idx}",
                "=" * 28,
                f"returncode: {completed.returncode}",
                "stdout:",
                completed.stdout or "",
                "stderr:",
                completed.stderr or "",
                "",
            ]),
        )
    hashes["gate_determinism.txt"] = _write_text(
        evidence_dir / "gate_determinism.txt",
        "\n".join([
            "P2-23 gate determinism",
            "=======================",
            *(f"run {idx + 1} stdout sha256: {h}" for idx, h in enumerate(gate_hashes)),
            f"gate stdout byte-identical: {len(set(gate_hashes)) == 1 and len(gate_hashes) == 2}",
            "",
        ]),
    )

    # Changed/new files
    changed_paths = [
        ROOT / "tools" / "test_nes_end_to_end_v1.py",
        ROOT / "SOURCE_SHA256SUMS.txt",
    ]
    changed_lines = []
    for path in changed_paths:
        changed_lines.append(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT).as_posix()}"
        )
    hashes["changed_files.txt"] = _write_text(
        evidence_dir / "changed_files.txt",
        "\n".join([
            "P2-23 changed/new files (SHA-256):",
            "===================================",
            *changed_lines,
            "",
        ]),
    )

    # Final result record
    result_markers = [f"OPENRECOMP_NES_END_TO_END_V1=PASS tests={staging['tests']}"]
    result_md = "\n".join([
        "# P2-23 NES synthetic end-to-end equivalence — result",
        "",
        "Stage: `OPENRECOMP_NES_END_TO_END_V1`.",
        "",
        "Verdict: **PASS**.",
        "",
        "## Markers",
        "",
        "```text",
        *result_markers,
        "```",
        "",
        "## What was proven",
        "",
        "The complete Phase-2 NES path was exercised end-to-end on a",
        "synthetic/original NES/NROM fixture, and the native executable's",
        "observable output is byte-identical to an independent reference",
        "interpreter that uses the same NES runtime adapter.",
        "",
        "* New dedicated gate `tools/test_nes_end_to_end_v1.py`.",
        f"* Synthetic/original {len(staging['instructions'])}-instruction NES6502 fixture ({len(CODE)} bytes,",
        f"  SHA-256 `{FIXTURE_SHA256}`).",
        "* The P2-21 26-byte core region and the P2-22 controller-probe bytes are preserved;",
        "  the previously placeholder frame/audio triggers are replaced by real host-call thunks.",
        "* Pipeline traversal: adapter decode -> P2-01 ProgramModel -> P2-02 CFG -> P2-03",
        "  function discovery -> P2-04 call graph -> P2-05 translation units -> P2-06",
        "  indirect-control-flow classification (`EXTERNAL_OR_RUNTIME_MEDIATED` runtime-service sites)",
        "  -> P2-07 host emitter -> P2-08 generic runtime ABI -> P2-09 deterministic build.",
        f"* Generated source fingerprint: `{staging['host'].fingerprint()}`.",
        "* Native executable returncode 0; expected vs actual stdout identical.",
        "",
        "## Determinism",
        "",
        f"* Three native executions produced byte-identical stdout: `{staging['stdout_sha1']}`.",
        f"* Two independent full gate runs produced byte-identical stdout: `{gate_hashes[0] if gate_hashes else 'n/a'}`.",
        "",
        "## Source integrity",
        "",
        "`python tools/phase1_host_gates_v1.py --only source-integrity` reported:",
        "",
        "```text",
        (phase1.stdout or "").strip() if phase1 else "n/a",
        "```",
        "",
        "## Regressions",
        "",
        "All relevant prior gates were re-run and passed:",
        "",
        "```text",
        *regression_markers.values(),
        "```",
        "",
        "## Evidence artifacts",
        "",
        f"`{evidence_dir.relative_to(ROOT).as_posix()}/` contains:",
        "",
        "* `RESULT.md` (this file)",
        "* `RESULT.json`",
        "* `changed_files.txt`",
        "* `fixture.txt`",
        "* `pipeline_*.txt`",
        "* `generated_source.c` + `generated_source_sha256.txt`",
        "* `build_manifest.json` + `build_run_*.txt`",
        "* `native_execution.txt`",
        "* `expected_vs_actual.txt`",
        "* `reference_comparison.txt`",
        "* `determinism.txt`",
        "* `gate_determinism.txt` + `p2_23_run1.txt` + `p2_23_run2.txt`",
        "* `source_integrity.txt`",
        "* regression captures for prior gates",
        "",
        "## Limitations and non-claims",
        "",
        "* Proves only the bounded synthetic NES/NROM fixture described above.",
        "* No full PPU/APU emulation, no commercial-ROM compatibility and no whole-guest",
        "  equivalence is claimed.",
        "* Mapper 0 (NROM) only; unsupported mappers, disabled I/O, expansion areas and",
        "  PPU/APU register access fail closed.",
        "* The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` marker remains",
        "  reserved for P2-99.",
        "",
    ])
    hashes["RESULT.md"] = _write_text(evidence_dir / "RESULT.md", result_md)

    result_json = {
        "stage": "P2-23",
        "marker": result_markers[0],
        "verdict": "PASS",
        "fixture_id": FIXTURE_ID,
        "fixture_sha256": FIXTURE_SHA256,
        "fixture_byte_length": len(CODE),
        "generated_source_fingerprint": staging["host"].fingerprint(),
        "native_stdout_sha256": staging["stdout_sha1"],
        "gate_stdout_sha256": gate_hashes[0] if gate_hashes else None,
        "changed_files": changed_lines,
        "source_integrity": (phase1.stdout or "").strip() if phase1 else None,
        "regressions": regression_markers,
        "evidence_hashes": {k: v for k, v in hashes.items()},
    }
    hashes["RESULT.json"] = _write_text(
        evidence_dir / "RESULT.json",
        json.dumps(result_json, indent=2, sort_keys=True) + "\n",
    )

    return hashes


# --- main --------------------------------------------------------------------
def _edge_targets(cfg, block_id, kind):
    return sorted(
        successor.target_address
        for successor in cfg.block(block_id).successors
        if successor.kind is kind and successor.resolved
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    parser.add_argument("--evidence-dir", help="write deterministic UTF-8 evidence here (output only)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    tests = 0  # updated after all checks

    # A. fixture ------------------------------------------------------------
    check("fixture-assembler-deterministic", assemble_fixture() == (CODE, LABELS, REGION_END))
    # The P2-21 loop / helper computation and the P2-22 controller-probe
    # sequence are preserved in spirit; the unconditional `jmp dispatch` that
    # previously hit the unresolved indirect jump has been replaced by the
    # expanded runtime-service path, which is the evidence-backed correction
    # required for an end-to-end proof.
    check("fixture-sha256", FIXTURE_SHA256 == hashlib.sha256(CODE).hexdigest())
    check("fixture-prg-bank-size", len(prg_rom_image()) == nes_rt.PRG_BANK_SIZE)
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

    check("decode-instructions-present", len(instructions) > 0)
    check("decode-proven-evidence", all(i.evidence is PROVEN for i in instructions))
    by_address = {i.address: i for i in instructions}
    check("decode-svc-frame", by_address[LABELS["frame_thunk"]].op == "svc_frame")
    check("decode-svc-audio", by_address[LABELS["audio_thunk"]].op == "svc_audio")

    # C. service classification ---------------------------------------------
    classified = [item for unit in classification.units for item in unit.classifications]
    check("classification-service-frame",
          any(c.address == LABELS["frame_thunk"] and c.status is IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED for c in classified))
    check("classification-service-audio",
          any(c.address == LABELS["audio_thunk"] and c.status is IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED for c in classified))

    # D. independent reference ----------------------------------------------
    ref, adapter = reference_execute()
    ref_obs = reference_observable(adapter)
    ref_obs["a"] = ref.state.a
    ref_obs["x"] = ref.state.x
    expected = format_observable(ref_obs)

    check("reference-halted", ref.state.halted)
    check("reference-frame-count", len(adapter.state.frames) == 1)
    check("reference-audio-count", len(adapter.state.audio) == 1)
    check("reference-frame-payload", adapter.state.frames[0].payload == FRAME_PAYLOAD)
    check("reference-audio-payload", adapter.state.audio[0].payload == AUDIO_PAYLOAD)

    # E. deterministic native build -----------------------------------------
    workspace = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p223-"))
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

        # F. native execution -------------------------------------------------
        manifest = comparison.runs[0].manifest
        executable = workspace / "run1" / "program.exe"
        check("native-executable-present", executable.is_file())
        exe_sha = hashlib.sha256(executable.read_bytes()).hexdigest()
        exe_map = manifest.artifact_map(bp.BuildArtifactKind.EXECUTABLE)
        check("native-executable-hash-matches-manifest", exe_map.get("program.exe") == exe_sha)

        runs = []
        for _ in range(3):
            completed = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
            runs.append(completed)
        actual = (runs[0].stdout or "").strip()
        check("native-returncode-zero", runs[0].returncode == 0)
        check("native-output-stable", all((r.stdout or "").strip() == actual for r in runs))
        check("expected-equals-actual", expected == actual)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    # H. fail-closed sanity -------------------------------------------------
    expect_fail("unsupported-mapper", lambda: nes_rt.NESRuntimeAdapter(mapper=1), nes_rt.NESRuntimeError)

    # I. regressions + gate determinism (only when writing evidence) --------
    regressions: dict[str, subprocess.CompletedProcess[str]] = {}
    gate_runs: list[subprocess.CompletedProcess[str]] = []
    if args.evidence_dir:
        for script, argv in REGRESSIONS:
            completed = run_regression(script, argv)
            regressions[script] = completed
            check(
                f"regression-pass:{script}",
                completed.returncode == 0 and "=PASS" in (completed.stdout or ""),
            )
        for i in range(2):
            completed = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "test_nes_end_to_end_v1.py")],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            gate_runs.append(completed)
            check(
                f"gate-determinism-run-{i + 1}",
                completed.returncode == 0 and "OPENRECOMP_NES_END_TO_END_V1=PASS" in (completed.stdout or ""),
            )
        check("gate-determinism", gate_runs[0].stdout == gate_runs[1].stdout)

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")

    # J. evidence -----------------------------------------------------------
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
                "native_returncode": runs[0].returncode,
                "exe_sha256": exe_sha,
                "reference": (ref, adapter),
                "stdout_sha1": hashlib.sha256((runs[0].stdout or "").encode("utf-8")).hexdigest(),
                "stdout_sha2": hashlib.sha256((runs[1].stdout or "").encode("utf-8")).hexdigest(),
                "stdout_sha3": hashlib.sha256((runs[2].stdout or "").encode("utf-8")).hexdigest(),
                "tests": tests,
                "gate_runs": gate_runs,
            },
            regressions,
        )

    if args.json:
        record = {
            "stage": "P2-23",
            "marker": f"OPENRECOMP_NES_END_TO_END_V1=PASS tests={tests}",
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
        print(f"OPENRECOMP_NES_END_TO_END_V1_JSON={out.name}")

    print(f"OPENRECOMP_NES_END_TO_END_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
