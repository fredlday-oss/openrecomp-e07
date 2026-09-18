#!/usr/bin/env python3
"""Phase-5 CPU semantics proof (P5-03).

Builds a complete differential vector suite for the documented NMOS 6502
official opcode set and runs every vector through two independently written
implementations:

* subject: the frozen Phase-1/Phase-2 translation path
  (`tools/nes6502_frontend_v1.py` -> normalized IR V1 -> the shared
  `openrecomp` core `ReferenceExecutor`);
* oracle: the frozen independent reference interpreter
  (`tools/nes6502_reference_v1.py`).

Each vector is a small deterministic 64 KiB image; the final CPU state
(A/X/Y/SP/P/PC/halted) and the complete 64 KiB guest memory must agree
exactly. The suite additionally covers the documented edge cases: flag
boundaries for ADC/SBC/CMP, stack operations, all eight conditional branches
(taken and not taken), absolute indexed page crossing, indirect-indexed page
crossing, JMP-indirect page-wrap, BRK/RTI vector behaviour and the NES 2A03
binary-only decimal-mode behaviour.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402
import nes6502_frontend_v1 as frozen_frontend  # noqa: E402
from nes6502_reference_v1 import (  # noqa: E402
    FLAG_C,
    FLAG_I,
    FLAG_UNUSED,
    NES6502State,
    ReferenceNES6502,
)
from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor  # noqa: E402
from p5_fixture_asm_v1 import AssemblyError, assemble  # noqa: E402

ENTRY = 0x0100
HALT = nes_adapter.HALT_OPCODE
MEMORY_SIZE = 0x10000
BASE_FLAGS = FLAG_UNUSED | FLAG_I
CONTRACT_PATH = ROOT / "contracts" / "host_contract.json"


class SemanticsError(ValueError):
    """Fail-closed semantics-vector error."""


@dataclass(frozen=True)
class Vector:
    name: str
    source: str
    covers: tuple[tuple[str, str], ...]
    preloads: dict[int, int] = field(default_factory=dict)
    extra_leaders: tuple[int, ...] = ()
    data_ranges: tuple[tuple[int, int], ...] = ()
    initial: tuple[int, ...] | None = None

    def document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "covers": [list(item) for item in self.covers],
            "extra_leaders": list(self.extra_leaders),
            "data_ranges": [list(item) for item in self.data_ranges],
        }


def _prologue(*, a: int = 0x5A, x: int = 0x03, y: int = 0x07, sp: int = 0xFD,
              carry: int = 0, decimal: int = 0) -> list[str]:
    lines = [
        f"lda #${a:02X}",
        f"ldx #${sp:02X}",
        "txs",
        f"ldx #${x:02X}",
        f"ldy #${y:02X}",
        f"lda #${a:02X}",
        "sei",
        "cld" if not decimal else "sed",
        "sec" if carry else "clc",
        "clv",
    ]
    return lines


def _store(addr: int, value: int) -> list[str]:
    return [f"lda #${value:02X}", f"sta ${addr:04X}"]


def _generic_source(mnemonic: str, mode: str, kind: str) -> str:
    lines = [".org $0100", *_prologue()]
    target = {
        "imm": f"{mnemonic} #$A5",
        "zp": f"{mnemonic} $20",
        "zpx": f"{mnemonic} $20,x",
        "zpy": f"{mnemonic} $20,y",
        "abs": f"{mnemonic} $0400",
        "absx": f"{mnemonic} $02FD,x",
        "absy": f"{mnemonic} $02F9,y",
        "indx": f"{mnemonic} ($20,x)",
        "indy": f"{mnemonic} ($20),y",
        "acc": f"{mnemonic} a",
        "impl": mnemonic,
    }[mode]
    if mode in ("zp", "zpx", "zpy"):
        address = {"zp": 0x20, "zpx": 0x23, "zpy": 0x27}[mode]
        lines += _store(address, 0xA5 if kind != "rmw" else 0x81)
    elif mode in ("abs", "absx", "absy"):
        address = {"abs": 0x0400, "absx": 0x0300, "absy": 0x0300}[mode]
        lines += _store(address, 0xA5 if kind != "rmw" else 0x81)
    elif mode == "indx":
        lines += _store(0x23, 0x00)
        lines += _store(0x24, 0x04)
        lines += _store(0x0400, 0xA5 if kind != "rmw" else 0x81)
    elif mode == "indy":
        lines += _store(0x20, 0xF9)
        lines += _store(0x21, 0x02)
        lines += _store(0x0300, 0xA5 if kind != "rmw" else 0x81)
    if mnemonic in ("rol", "ror") and kind == "acc":
        lines.append("sec")
    lines.append(target)
    lines.append(".byte $02")
    return "\n".join(lines) + "\n"


def _branch_source(mnemonic: str, taken: bool) -> str:
    flag_setup = {
        "bpl": ["lda #$00"] if taken else ["lda #$80"],
        "bmi": ["lda #$80"] if taken else ["lda #$00"],
        "bvc": ["clv"] if taken else ["bit $0400"],
        "bvs": ["bit $0400"] if taken else ["clv"],
        "bcc": ["clc"] if taken else ["sec"],
        "bcs": ["sec"] if taken else ["clc"],
        "bne": ["lda #$01"] if taken else ["lda #$00"],
        "beq": ["lda #$00"] if taken else ["lda #$01"],
    }[mnemonic]
    memory = ["lda #$40", "sta $0400"] if mnemonic in ("bvc", "bvs") else []
    lines = [
        ".org $0100",
        *_prologue(),
        *memory,
        *flag_setup,
        f"{mnemonic} taken",
        "lda #$11",
        ".byte $02",
        "taken:",
        "lda #$22",
        ".byte $02",
    ]
    return "\n".join(lines) + "\n"


def _jsr_source() -> str:
    return "\n".join([
        ".org $0100",
        *_prologue(),
        "jsr sub",
        "lda #$11",
        ".byte $02",
        "sub:",
        "lda #$44",
        "rts",
    ]) + "\n"


def _jmp_abs_source() -> str:
    return "\n".join([
        ".org $0100",
        *_prologue(),
        "jmp target",
        ".byte $02",
        "target:",
        "lda #$77",
        ".byte $02",
    ]) + "\n"


def _brk_source() -> str:
    return "\n".join([
        ".org $0100",
        *_prologue(),
        "lda #$11",
        "brk",
        "nop",
        ".byte $02",
        ".res 236, $02",
        ".org $0200",
        "lda #$44",
        "rti",
    ]) + "\n"


def _jmp_indirect_wrap_source() -> str:
    return "\n".join([
        ".org $0100",
        *_prologue(),
        "lda #$33",
        "jmp ($02FF)",
        ".byte $02",
        ".res 491, $02",
        ".org $0300",
        "lda #$77",
        ".byte $02",
    ]) + "\n"


def _pha_source() -> str:
    return "\n".join([".org $0100", *_prologue(), "pha", ".byte $02"]) + "\n"


def _php_source() -> str:
    return "\n".join([".org $0100", *_prologue(), "php", ".byte $02"]) + "\n"


def _pla_source() -> str:
    return "\n".join([".org $0100", *_prologue(), "pha", "lda #$00", "pla",
                      ".byte $02"]) + "\n"


def _plp_source() -> str:
    return "\n".join([".org $0100", *_prologue(), "php", "clc", "plp",
                      ".byte $02"]) + "\n"


def _shift_edge(name: str, mnemonic: str, mode: str, a: int, value: int,
                carry: int) -> Vector:
    if mode == "imm":
        source = "\n".join([
            ".org $0100", *_prologue(a=a, carry=carry),
            f"{mnemonic} #${value:02X}", ".byte $02",
        ]) + "\n"
    else:
        source = "\n".join([
            ".org $0100", *_prologue(a=a, carry=carry),
            *_store(0x0400, value),
            f"{mnemonic} $0400", ".byte $02",
        ]) + "\n"
    return Vector(name=name, source=source, covers=((mnemonic, mode),))


def build_vectors() -> list[Vector]:
    vectors: list[Vector] = []
    special: set[int] = set()
    for opcode, (mnemonic, mode, kind) in sorted(nes_adapter.OPCODES.items()):
        if opcode in nes_adapter.BRANCHES:
            continue
        if mnemonic == "brk":
            special.add(opcode)
            continue
        if mnemonic == "rti":
            special.add(opcode)
            continue
        if mnemonic in ("jsr", "rts", "jmp"):
            special.add(opcode)
            continue
        if mnemonic in ("pha", "php", "pla", "plp"):
            special.add(opcode)
            continue
        vectors.append(Vector(
            name=f"op_{opcode:02x}_{mnemonic}_{mode.replace(',', '_')}",
            source=_generic_source(mnemonic, mode, kind),
            covers=((mnemonic, mode),),
        ))
    for opcode, (mnemonic, _flag, _taken) in sorted(nes_adapter.BRANCHES.items()):
        special.add(opcode)
        vectors.append(Vector(
            name=f"op_{opcode:02x}_{mnemonic}_taken",
            source=_branch_source(mnemonic, True),
            covers=((mnemonic, "rel"),),
        ))
        vectors.append(Vector(
            name=f"op_{opcode:02x}_{mnemonic}_not_taken",
            source=_branch_source(mnemonic, False),
            covers=((mnemonic, "rel"),),
        ))
    for opcode, (mnemonic, mode, _kind) in sorted(nes_adapter.OPCODES.items()):
        if opcode not in special:
            continue
        source = {
            ("jmp", "abs"): _jmp_abs_source,
            ("jmp", "ind"): _jmp_indirect_wrap_source,
            ("jsr", "abs"): _jsr_source,
            ("rts", "impl"): None,
            ("brk", "impl"): _brk_source,
            ("rti", "impl"): _brk_source,
            ("pha", "impl"): _pha_source,
            ("php", "impl"): _php_source,
            ("pla", "impl"): _pla_source,
            ("plp", "impl"): _plp_source,
        }.get((mnemonic, mode))
        if source is None:
            continue
        covers: tuple[tuple[str, str], ...] = ((mnemonic, mode),)
        if mnemonic == "jsr":
            covers = (("jsr", "abs"), ("rts", "impl"))
        extra_leaders: tuple[int, ...] = ()
        data_ranges: tuple[tuple[int, int], ...] = ()
        preloads: dict[int, int] = {}
        if mnemonic == "jmp" and mode == "ind":
            extra_leaders = (0x0300,)
            data_ranges = ((0x0200, 0x0300),)
            preloads = {0x02FF: 0x00, 0x0200: 0x03}
        if mnemonic in ("brk", "rti"):
            extra_leaders = (0x0200,)
            preloads = {0xFFFE: 0x00, 0xFFFF: 0x02}
        vectors.append(Vector(
            name=f"op_{opcode:02x}_{mnemonic}_{mode}",
            source=source(),
            covers=covers,
            preloads=preloads,
            extra_leaders=extra_leaders,
            data_ranges=data_ranges,
        ))
    vectors.extend([
        Vector(name="edge_adc_imm_7f_01",
               source=_shift_edge("a", "adc", "imm", 0x7F, 0x01, 0).source,
               covers=(("adc", "imm"),)),
        Vector(name="edge_adc_imm_ff_01",
               source=_shift_edge("a", "adc", "imm", 0xFF, 0x01, 0).source,
               covers=(("adc", "imm"),)),
        Vector(name="edge_adc_imm_80_80",
               source=_shift_edge("a", "adc", "imm", 0x80, 0x80, 0).source,
               covers=(("adc", "imm"),)),
        Vector(name="edge_adc_imm_00_ff_c",
               source=_shift_edge("a", "adc", "imm", 0x00, 0xFF, 1).source,
               covers=(("adc", "imm"),)),
        Vector(name="edge_adc_abs_50_50_c",
               source=_shift_edge("a", "adc", "abs", 0x50, 0x50, 1).source,
               covers=(("adc", "abs"),)),
        Vector(name="edge_sbc_imm_00_01_c",
               source=_shift_edge("a", "sbc", "imm", 0x00, 0x01, 1).source,
               covers=(("sbc", "imm"),)),
        Vector(name="edge_sbc_imm_80_01_c",
               source=_shift_edge("a", "sbc", "imm", 0x80, 0x01, 1).source,
               covers=(("sbc", "imm"),)),
        Vector(name="edge_sbc_imm_50_f0_c",
               source=_shift_edge("a", "sbc", "imm", 0x50, 0xF0, 1).source,
               covers=(("sbc", "imm"),)),
        Vector(name="edge_sbc_imm_00_00",
               source=_shift_edge("a", "sbc", "imm", 0x00, 0x00, 0).source,
               covers=(("sbc", "imm"),)),
        Vector(name="edge_bit_abs_40",
               source="\n".join([".org $0100", *_prologue(), *_store(0x0400, 0x40),
                                 "bit $0400", ".byte $02"]) + "\n",
               covers=(("bit", "abs"),)),
        Vector(name="edge_inc_abs_7f",
               source="\n".join([".org $0100", *_prologue(), *_store(0x0400, 0x7F),
                                 "inc $0400", ".byte $02"]) + "\n",
               covers=(("inc", "abs"),)),
        Vector(name="edge_dec_abs_00",
               source="\n".join([".org $0100", *_prologue(), *_store(0x0400, 0x00),
                                 "dec $0400", ".byte $02"]) + "\n",
               covers=(("dec", "abs"),)),
        Vector(name="edge_lda_zpx_wrap",
               source="\n".join([".org $0100", *_prologue(x=0x02),
                                 *_store(0x0001, 0x6C),
                                 "lda $FF,x", ".byte $02"]) + "\n",
               covers=(("lda", "zpx"),)),
        Vector(name="edge_lda_absx_page_cross",
               source="\n".join([".org $0100", *_prologue(x=0x04),
                                 *_store(0x0302, 0x6D),
                                 "lda $02FE,x", ".byte $02"]) + "\n",
               covers=(("lda", "absx"),)),
        Vector(name="edge_lda_absy_page_cross",
               source="\n".join([".org $0100", *_prologue(y=0x04),
                                 *_store(0x0302, 0x6E),
                                 "lda $02FE,y", ".byte $02"]) + "\n",
               covers=(("lda", "absy"),)),
        Vector(name="edge_lda_indy_page_cross",
               source="\n".join([".org $0100", *_prologue(y=0x07),
                                 *_store(0x20, 0xF9), *_store(0x21, 0x02),
                                 *_store(0x0300, 0x6F),
                                 "lda ($20),y", ".byte $02"]) + "\n",
               covers=(("lda", "indy"),)),
        Vector(name="edge_rmw_inc_absx_page_cross",
               source="\n".join([".org $0100", *_prologue(x=0x04),
                                 *_store(0x0302, 0x7E),
                                 "inc $02FE,x", ".byte $02"]) + "\n",
               covers=(("inc", "absx"),)),
        Vector(name="edge_cmp_imm_equal",
               source="\n".join([".org $0100", *_prologue(), "cmp #$5A",
                                 ".byte $02"]) + "\n",
               covers=(("cmp", "imm"),)),
        Vector(name="edge_cmp_imm_less",
               source="\n".join([".org $0100", *_prologue(), "cmp #$5B",
                                 ".byte $02"]) + "\n",
               covers=(("cmp", "imm"),)),
        Vector(name="edge_cpx_imm_greater",
               source="\n".join([".org $0100", *_prologue(), "cpx #$02",
                                 ".byte $02"]) + "\n",
               covers=(("cpx", "imm"),)),
        Vector(name="edge_cpy_imm_equal",
               source="\n".join([".org $0100", *_prologue(), "cpy #$07",
                                 ".byte $02"]) + "\n",
               covers=(("cpy", "imm"),)),
        Vector(name="edge_2a03_sed_adc_binary",
               source="\n".join([".org $0100", *_prologue(decimal=1),
                                 "clc", "lda #$0A", "adc #$01",
                                 ".byte $02"]) + "\n",
               covers=(("adc", "imm"),)),
        Vector(name="edge_2a03_sed_sbc_binary",
               source="\n".join([".org $0100", *_prologue(decimal=1),
                                 "sec", "lda #$0A", "sbc #$01",
                                 ".byte $02"]) + "\n",
               covers=(("sbc", "imm"),)),
    ])
    return vectors


def _serialize(document: object) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assemble_vector(vector: Vector) -> tuple[bytes, int]:
    try:
        result = assemble(vector.source)
    except AssemblyError as exc:
        raise SemanticsError(f"{vector.name}: assembly failed: {exc}") from exc
    if result.origin != ENTRY:
        raise SemanticsError(f"{vector.name}: origin 0x{result.origin:04x} != 0x{ENTRY:04x}")
    image = bytearray([HALT] * MEMORY_SIZE)
    image[result.origin:result.end] = result.image
    for address, value in vector.preloads.items():
        image[address] = value & 0xFF
    return bytes(image), result.end


def _initial_state() -> NES6502State:
    return NES6502State(pc=ENTRY, sp=0xFD, p=BASE_FLAGS)


def run_vector(vector: Vector) -> dict[str, Any]:
    image, region_end = assemble_vector(vector)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_bytes = CONTRACT_PATH.read_bytes()
    meta = {
        "architecture": "nes6502",
        "entry_address": ENTRY,
        "region_start": ENTRY,
        "region_end": region_end,
        "initial_state": {
            "cpu:a": 0x00, "cpu:x": 0x00, "cpu:y": 0x00, "cpu:sp": 0xFD,
            "cpu:pc": ENTRY, "cpu:p": BASE_FLAGS, "platform:halted": 0,
        },
        "observe_state_slot": "cpu:a",
        "max_operations": 1000000,
    }
    if vector.extra_leaders:
        meta["extra_leaders"] = list(vector.extra_leaders)
    if vector.data_ranges:
        meta["data_ranges"] = [list(item) for item in vector.data_ranges]

    try:
        ir, sidecar, report = frozen_frontend.convert(image, meta, contract)
    except Exception as exc:  # noqa: BLE001 - fail closed per vector
        raise SemanticsError(f"{vector.name}: frontend conversion failed: {exc}") from exc

    ir_bytes = _serialize(ir).encode("utf-8")
    segments = []
    for segment in sorted(sidecar["memory_segments"],
                          key=lambda item: (item["guest_address"], item["name"])):
        data = bytes.fromhex(segment["data_hex"])
        segments.append({
            "name": segment["name"],
            "guest_address": segment["guest_address"],
            "data_hex": data.hex(),
            "data_sha256": _digest(data),
        })
    manifest = {
        "module_format_version": "1.0.0",
        "module_id": ir["module_id"],
        "ir": {
            "version": ir["ir_version"],
            "sha256": _digest(ir_bytes),
            "source_input_sha256": ir["source"]["input_sha256"],
        },
        "host_contract": {
            "version": contract["contract_version"],
            "sha256": _digest(contract_bytes),
        },
        "memory": {"size_bytes": sidecar["memory_size_bytes"], "segments": segments},
        "initial_state": [
            {"slot": slot, "value": value}
            for slot, value in sorted(sidecar["initial_state"].items())
        ],
        "entry": {
            "function": ir["entry_function"],
            "observe_state_slot": sidecar["entry_state_slot"],
        },
        "limits": {"max_operations": sidecar["max_operations"], "max_call_depth": 1024},
        "provenance": {
            "producer": "openrecomp.nes6502-frontend-v1",
            "source_input_sha256": ir["source"]["input_sha256"],
        },
    }
    module = ModuleImage.from_documents(
        manifest, ir, contract,
        ir_sha256=_digest(ir_bytes), contract_sha256=_digest(contract_bytes))
    executor = ReferenceExecutor(
        module, CallbackHostBinding(contract["contract_version"], {}))
    execution = executor.run()
    core_memory = bytes(executor.memory.data)

    reference = ReferenceNES6502(bytearray(image), _initial_state())
    ref_state = reference.run(max_steps=100000)
    reference_memory = bytes(reference.memory)

    mismatches: list[str] = []
    for key in ("a", "x", "y", "sp", "p", "pc", "halted"):
        slot = "platform:halted" if key == "halted" else f"cpu:{key}"
        actual = int(execution.state[slot])
        expected = int(ref_state[key])
        if actual != expected:
            mismatches.append(f"{slot}={actual:#x} != reference {expected:#x}")
    if core_memory != reference_memory:
        for index in range(MEMORY_SIZE):
            if core_memory[index] != reference_memory[index]:
                mismatches.append(
                    f"memory[0x{index:04x}]={core_memory[index]:#x} != "
                    f"reference {reference_memory[index]:#x}")
                break

    return {
        "name": vector.name,
        "covers": [list(item) for item in vector.covers],
        "region": [ENTRY, region_end],
        "blocks": report["blocks"],
        "instructions": report["instructions"],
        "image_sha256": _digest(image),
        "core_state": {
            key: int(execution.state["platform:halted" if key == "halted"
                                      else f"cpu:{key}"])
            for key in ("a", "x", "y", "sp", "p", "pc", "halted")
        },
        "reference_state": {key: int(ref_state[key])
                            for key in ("a", "x", "y", "sp", "p", "pc", "halted")},
        "memory_sha256": _digest(core_memory),
        "equivalent": not mismatches,
        "mismatches": mismatches,
    }


def run_suite() -> dict[str, Any]:
    vectors = build_vectors()
    results = []
    for vector in vectors:
        result = run_vector(vector)
        result["vector"] = vector.document()
        results.append(result)
    covered = sorted({tuple(item) for result in results for item in result["covers"]})
    failed = [result["name"] for result in results if not result["equivalent"]]
    return {
        "vectors": len(results),
        "covered_pairs": [list(item) for item in covered],
        "failed": failed,
        "results": results,
    }


def reachable_pairs(rom: bytes, metadata: dict, inventory: dict) -> list[tuple[str, str]]:
    import p5_frontier_v1 as frontier

    image = frontier.build_cpu_image(rom, 16, metadata["prg_size"])
    vectors = inventory["vectors"]
    walk = frontier.reachable_frontier(
        image, [vectors["reset"], vectors["nmi"], vectors["irq"]])
    pairs = set()
    for item in walk["instructions"]:
        mnemonic, mode, _kind = nes_adapter.OPCODES[item["word"]]
        pairs.add((mnemonic, mode))
    return sorted(pairs)


def interrupt_document() -> dict[str, Any]:
    image = bytearray([HALT] * MEMORY_SIZE)
    image[0xFFFC] = 0x00
    image[0xFFFD] = 0x80
    image[0xFFFA] = 0x00
    image[0xFFFB] = 0x81
    image[0xFFFE] = 0x00
    image[0xFFFF] = 0x82
    state = NES6502State(pc=0x0100, sp=0xFD, p=BASE_FLAGS)
    reference = ReferenceNES6502(image, state)
    reference.reset()
    reset_document = {
        "pc": reference.state.pc,
        "sp": reference.state.sp,
        "p": reference.state.p,
        "vector_source": "0xFFFC/0xFFFD",
    }
    state = NES6502State(pc=0x0100, sp=0xFD, p=BASE_FLAGS & ~FLAG_I)
    reference = ReferenceNES6502(bytearray(image), state)
    taken = reference.irq()
    irq_document = {
        "taken": taken,
        "pc": reference.state.pc,
        "sp": reference.state.sp,
        "p": reference.state.p,
        "stack_pch": reference.memory[0x01FD],
        "stack_pcl": reference.memory[0x01FC],
        "stack_p": reference.memory[0x01FB],
    }
    state = NES6502State(pc=0x0100, sp=0xFD, p=BASE_FLAGS)
    reference = ReferenceNES6502(bytearray(image), state)
    taken = reference.nmi()
    nmi_document = {
        "taken": taken,
        "pc": reference.state.pc,
        "sp": reference.state.sp,
        "p": reference.state.p,
        "stack_pch": reference.memory[0x01FD],
        "stack_pcl": reference.memory[0x01FC],
        "stack_p": reference.memory[0x01FB],
    }
    return {
        "reset": reset_document,
        "reset_expected": {"pc": 0x8000, "sp": 0xFD, "p": BASE_FLAGS,
                           "vector_source": "0xFFFC/0xFFFD"},
        "irq": irq_document,
        "irq_expected": {
            "taken": True, "pc": 0x8200, "sp": 0xFA, "p": BASE_FLAGS,
            "stack_pch": 0x01, "stack_pcl": 0x00,
            "stack_p": (BASE_FLAGS & ~FLAG_I) & ~0x10,
        },
        "nmi": nmi_document,
        "nmi_expected": {
            "taken": True, "pc": 0x8100, "sp": 0xFA, "p": BASE_FLAGS,
            "stack_pch": 0x01, "stack_pcl": 0x00,
            "stack_p": BASE_FLAGS & ~0x10,
        },
    }


__all__ = [
    "HALT",
    "SemanticsError",
    "Vector",
    "BASE_FLAGS",
    "build_vectors",
    "interrupt_document",
    "reachable_pairs",
    "run_suite",
    "run_vector",
]
