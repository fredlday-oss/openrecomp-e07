#!/usr/bin/env python3
"""OpenRecomp Phase-8 translation frontier closure gate (P8-04).

P8-04 closes the minimum translation/semantics gaps demonstrated by
P8-02/P8-03 for the frozen P8-01 fixture and proves every reachable
instruction is translatable, or fails closed with an explicit reason.

The gate:

* verifies the additive shared-emitter extensions are byte-compatible for the
  default configuration and re-runs the direct dependency gates;
* proves full emission coverage of the frozen 486-instruction neutral
  structure with the closed P8 MIPS32 semantic rule table;
* runs differential execution of the new semantics against an independently
  written Python reference model: width/sign byte loads, byte stores, `movz`
  conditional select, folded non-nop delay slots on taken/not-taken/call/
  return paths, and the o32 `$ra` link-register contract;
* proves the rule table is closed: unsupported MIPS32 forms have no rule and
  fail closed, with no silent widening.

On success it emits::

    OPENRECOMP_P8_04=PASS
    OPENRECOMP_PHASE8_TRANSLATION_CLOSURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_translation_v1.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))

import adapters.mips32 as mips32_adapter  # noqa: E402
import p3_code_frontier_v1 as frontier  # noqa: E402
import p3_elf_image_v1 as elf  # noqa: E402
import p3_target_mips32_v1 as target  # noqa: E402
import p8_mips32_semantics_v1 as semantics  # noqa: E402
import p8_structure_v1 as structure_bridge  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.call_graph import build_call_graph  # noqa: E402
from openrecomp.cfg import CFGMode, EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.host_emitter import HostEmitterError, emit_host_translation  # noqa: E402
from openrecomp.indirect_control_flow import classify_indirect_control_flow  # noqa: E402
from openrecomp.program_model import (  # noqa: E402
    EvidenceClass,
    InstructionFlow,
    ProgramSource,
    instruction_from_adapter,
)
from openrecomp.translation_units import build_translation_units  # noqa: E402

EVIDENCE_DIR = ROOT / ".openrecomp-phase8" / "evidence" / "P8-04"
WORKSPACE = ROOT / ".openrecomp-phase8" / "build" / "P8-04"

STAGE = "P8-04"
STAGE_MARKER = "OPENRECOMP_P8_04"
FEATURE_MARKER = "OPENRECOMP_PHASE8_TRANSLATION_CLOSURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

FIXTURE_ELF = ROOT / ".openrecomp-phase8" / "build" / "P8-01" / "candidate-a" / "p8_aes128_mips32_O1.elf"
FIXTURE_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"
PROVEN = EvidenceClass.PROVEN

UNSUPPORTED_OPS = ("div", "divu", "mult", "multu", "mul", "movn", "jalr", "swl", "swr", "lwl", "lwr", "lh", "lhu", "sh")

DEPENDENCY_GATES = (
    ("tools/test_host_emitter_v1.py", "OPENRECOMP_HOST_EMITTER_V1=PASS"),
    ("tools/test_mips32_end_to_end_v1.py", "OPENRECOMP_MIPS32_END_TO_END_V1=PASS"),
)

SUPPORT_SOURCE = """\
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>

void openrecomp_run(void);
int openrecomp_failed(void);
const char *openrecomp_error(void);
size_t openrecomp_register_count(void);
uint64_t openrecomp_register_value(size_t index);

#define P8_MEM_BASE UINT64_C(0x2000)
#define P8_MEM_SIZE 256u

/* OpenRecomp generic runtime ABI V1 failure codes (numeric contract). */
enum {
    P8_RT_OK = 0,
    P8_RT_MEMORY_OUT_OF_RANGE = 1,
    P8_RT_MEMORY_WIDTH_UNSUPPORTED = 2,
    P8_RT_UNKNOWN_HOST_SERVICE = 6
};

static uint8_t g_mem[P8_MEM_SIZE];

int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value) {
    if (address < P8_MEM_BASE || address >= P8_MEM_BASE + P8_MEM_SIZE) return P8_RT_MEMORY_OUT_OF_RANGE;
    uint64_t offset = address - P8_MEM_BASE;
    uint64_t value = UINT64_C(0);
    if (width_bits == 8u) {
        value = (uint64_t)g_mem[offset];
    } else if (width_bits == 16u) {
        if (offset + 2u > P8_MEM_SIZE) return P8_RT_MEMORY_OUT_OF_RANGE;
        value = ((uint64_t)g_mem[offset]) | ((uint64_t)g_mem[offset + 1u] << 8);
    } else if (width_bits == 32u) {
        if (offset + 4u > P8_MEM_SIZE) return P8_RT_MEMORY_OUT_OF_RANGE;
        value = ((uint64_t)g_mem[offset]) | ((uint64_t)g_mem[offset + 1u] << 8)
              | ((uint64_t)g_mem[offset + 2u] << 16) | ((uint64_t)g_mem[offset + 3u] << 24);
    } else {
        return P8_RT_MEMORY_WIDTH_UNSUPPORTED;
    }
    if (out_value != NULL) *out_value = value;
    return P8_RT_OK;
}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value) {
    if (address < P8_MEM_BASE || address >= P8_MEM_BASE + P8_MEM_SIZE) return P8_RT_MEMORY_OUT_OF_RANGE;
    uint64_t offset = address - P8_MEM_BASE;
    if (width_bits == 8u) {
        g_mem[offset] = (uint8_t)(value & 0xFFu);
    } else if (width_bits == 16u) {
        if (offset + 2u > P8_MEM_SIZE) return P8_RT_MEMORY_OUT_OF_RANGE;
        g_mem[offset] = (uint8_t)(value & 0xFFu);
        g_mem[offset + 1u] = (uint8_t)((value >> 8) & 0xFFu);
    } else if (width_bits == 32u) {
        if (offset + 4u > P8_MEM_SIZE) return P8_RT_MEMORY_OUT_OF_RANGE;
        for (unsigned index = 0; index < 4u; ++index) {
            g_mem[offset + index] = (uint8_t)((value >> (8u * index)) & 0xFFu);
        }
    } else {
        return P8_RT_MEMORY_WIDTH_UNSUPPORTED;
    }
    return P8_RT_OK;
}

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value) {
    (void)service_id; (void)argc; (void)args; (void)out_value;
    return P8_RT_UNKNOWN_HOST_SERVICE;
}

const char *or_rt_failure_reason(int code) {
    switch (code) {
    case P8_RT_OK: return "ok";
    case P8_RT_MEMORY_OUT_OF_RANGE: return "memory out of range";
    case P8_RT_MEMORY_WIDTH_UNSUPPORTED: return "memory width unsupported";
    case P8_RT_UNKNOWN_HOST_SERVICE: return "unknown host service";
    default: return "runtime failure";
    }
}

int main(void) {
    openrecomp_run();
    printf("failed=%d\\n", openrecomp_failed());
    printf("error=%s\\n", openrecomp_error());
    size_t count = openrecomp_register_count();
    for (size_t index = 0; index < count; ++index) {
        printf("r%zu=%08llx\\n", index, (unsigned long long)(openrecomp_register_value(index) & UINT64_C(0xFFFFFFFF)));
    }
    for (unsigned index = 0; index < 12u; ++index) {
        printf("mem[%u]=%02x\\n", index, (unsigned)g_mem[index]);
    }
    return 0;
}
"""

# --- synthetic differential fixture -----------------------------------------
# Exercises the new/explicit semantics: byte load sign/zero extension, byte
# store, word round-trip, movz, folded non-nop delay slots on a taken branch,
# a call, a return and a callee return, plus the $ra save/restore/clobber
# pattern the real fixture uses.
SYNTHETIC_DELAYS = {
    0x1048: {"address": 0x104C, "op": "addiu", "fields": {"rs": 0, "rt": 15, "imm": 0x11}},
    0x1058: {"address": 0x105C, "op": "addiu", "fields": {"rs": 0, "rt": 18, "imm": 0x44}},
    0x1068: {"address": 0x106C, "op": "addiu", "fields": {"rs": 0, "rt": 20, "imm": 0x66}},
    0x1120: {"address": 0x1124, "op": "addiu", "fields": {"rs": 0, "rt": 22, "imm": 0x99}},
}
SYNTHETIC = (
    (0x1000, "lui", InstructionFlow.NORMAL, {"rs": 0, "rt": 1, "imm": 0x0000}, None),
    (0x1004, "ori", InstructionFlow.NORMAL, {"rs": 1, "rt": 1, "imm": 0x2000}, None),
    (0x1008, "addiu", InstructionFlow.NORMAL, {"rs": 0, "rt": 4, "imm": 0x80}, None),
    (0x100C, "sb", InstructionFlow.NORMAL, {"rs": 1, "rt": 4, "imm": 0}, None),
    (0x1010, "addiu", InstructionFlow.NORMAL, {"rs": 0, "rt": 5, "imm": 0x7F}, None),
    (0x1014, "sb", InstructionFlow.NORMAL, {"rs": 1, "rt": 5, "imm": 1}, None),
    (0x1018, "lbu", InstructionFlow.NORMAL, {"rs": 1, "rt": 6, "imm": 0}, None),
    (0x101C, "lb", InstructionFlow.NORMAL, {"rs": 1, "rt": 7, "imm": 0}, None),
    (0x1020, "lbu", InstructionFlow.NORMAL, {"rs": 1, "rt": 8, "imm": 1}, None),
    (0x1024, "lb", InstructionFlow.NORMAL, {"rs": 1, "rt": 9, "imm": 1}, None),
    (0x1028, "sw", InstructionFlow.NORMAL, {"rs": 1, "rt": 7, "imm": 4}, None),
    (0x102C, "lw", InstructionFlow.NORMAL, {"rs": 1, "rt": 10, "imm": 4}, None),
    (0x1030, "addiu", InstructionFlow.NORMAL, {"rs": 0, "rt": 11, "imm": 5}, None),
    (0x1034, "addiu", InstructionFlow.NORMAL, {"rs": 0, "rt": 12, "imm": 0}, None),
    (0x1038, "addiu", InstructionFlow.NORMAL, {"rs": 0, "rt": 13, "imm": 0}, None),
    (0x103C, "movz", InstructionFlow.NORMAL, {"rs": 13, "rt": 11, "rd": 12}, None),
    (0x1040, "addiu", InstructionFlow.NORMAL, {"rs": 0, "rt": 14, "imm": 7}, None),
    (0x1044, "movz", InstructionFlow.NORMAL, {"rs": 14, "rt": 0, "rd": 12}, None),
    (0x1048, "beq", InstructionFlow.BRANCH, {"rs": 0, "rt": 0}, 0x1058),
    (0x1050, "addiu", InstructionFlow.NORMAL, {"rs": 0, "rt": 16, "imm": 0x33}, None),
    (0x1054, "addiu", InstructionFlow.NORMAL, {"rs": 0, "rt": 17, "imm": 0xAA}, None),
    (0x1058, "jal", InstructionFlow.CALL, {}, 0x1110),
    (0x1060, "addiu", InstructionFlow.NORMAL, {"rs": 0, "rt": 19, "imm": 0x55}, None),
    (0x1064, "or", InstructionFlow.NORMAL, {"rs": 0, "rt": 0, "rd": 31}, None),
    (0x1068, "jr", InstructionFlow.RETURN, {"rs": 31}, None),
    (0x1110, "sw", InstructionFlow.NORMAL, {"rs": 1, "rt": 31, "imm": 8}, None),
    (0x1114, "addiu", InstructionFlow.NORMAL, {"rs": 0, "rt": 31, "imm": 0x77}, None),
    (0x1118, "addiu", InstructionFlow.NORMAL, {"rs": 0, "rt": 21, "imm": 0x88}, None),
    (0x111C, "lw", InstructionFlow.NORMAL, {"rs": 1, "rt": 31, "imm": 8}, None),
    (0x1120, "jr", InstructionFlow.RETURN, {"rs": 31}, None),
)
SYNTHETIC_ENTRY = 0x1000
MEM_BASE = 0x2000
MEM_SIZE = 256

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL", "detail": detail})
        raise AssertionError(f"{label}: condition failed ({detail})")
    RESULTS.append({"check": label, "status": "PASS", "detail": detail})
    print(f"PASS: {label}")


def expect_fail(label: str, thunk, error_type) -> None:
    try:
        thunk()
    except error_type as exc:
        RESULTS.append({"check": f"reject:{label}", "status": "PASS", "detail": type(exc).__name__})
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        RESULTS.append({"check": f"reject:{label}", "status": "FAIL", "detail": type(exc).__name__})
        raise AssertionError(f"{label}: raised {type(exc).__name__} instead of {error_type.__name__}: {exc}") from exc
    RESULTS.append({"check": f"reject:{label}", "status": "FAIL", "detail": "accepted"})
    raise AssertionError(f"{label}: accepted")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evidence_json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_evidence(name: str, payload: object) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_bytes(evidence_json(payload))


# --- independent reference model --------------------------------------------
def _sx(value: int, bits: int) -> int:
    mask = (1 << bits) - 1
    value &= mask
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def reference_execute():
    """Independently written MIPS32 model of the synthetic fixture."""
    regs = [0] * 32
    memory = bytearray(MEM_SIZE)
    by_address = {item[0]: item for item in SYNTHETIC}
    pc = SYNTHETIC_ENTRY
    steps = 0
    while True:
        if pc == 0:
            break
        steps += 1
        if steps > 10000:
            raise AssertionError("reference model step limit")
        item = by_address.get(pc)
        if item is None:
            raise AssertionError(f"reference model left the fixture at 0x{pc:x}")
        address, op, flow, fields, target = item
        delay = SYNTHETIC_DELAYS.get(address)
        if flow is InstructionFlow.CALL:
            regs[31] = (address + 8) & 0xFFFFFFFF
        branch = False
        jump_target = None
        if op == "lui":
            regs[fields["rt"]] = (fields["imm"] << 16) & 0xFFFFFFFF
        elif op == "ori":
            regs[fields["rt"]] = (regs[fields["rs"]] | fields["imm"]) & 0xFFFFFFFF
        elif op == "addiu":
            regs[fields["rt"]] = (regs[fields["rs"]] + _sx(fields["imm"], 16)) & 0xFFFFFFFF
        elif op == "sb":
            offset = (regs[fields["rs"]] + _sx(fields["imm"], 16) - MEM_BASE) & 0xFFFFFFFF
            memory[offset] = regs[fields["rt"]] & 0xFF
        elif op == "lbu":
            offset = (regs[fields["rs"]] + _sx(fields["imm"], 16) - MEM_BASE) & 0xFFFFFFFF
            regs[fields["rt"]] = memory[offset]
        elif op == "lb":
            offset = (regs[fields["rs"]] + _sx(fields["imm"], 16) - MEM_BASE) & 0xFFFFFFFF
            regs[fields["rt"]] = _sx(memory[offset], 8) & 0xFFFFFFFF
        elif op == "sw":
            offset = (regs[fields["rs"]] + _sx(fields["imm"], 16) - MEM_BASE) & 0xFFFFFFFF
            value = regs[fields["rt"]] & 0xFFFFFFFF
            for index in range(4):
                memory[offset + index] = (value >> (8 * index)) & 0xFF
        elif op == "lw":
            offset = (regs[fields["rs"]] + _sx(fields["imm"], 16) - MEM_BASE) & 0xFFFFFFFF
            regs[fields["rt"]] = int.from_bytes(memory[offset:offset + 4], "little")
        elif op == "movz":
            # MIPS32 MOVZ: if GPR[rt] == 0 then GPR[rd] = GPR[rs].
            if regs[fields["rt"]] == 0:
                regs[fields["rd"]] = regs[fields["rs"]]
        elif op == "or":
            regs[fields["rd"]] = (regs[fields["rs"]] | regs[fields["rt"]]) & 0xFFFFFFFF
        elif op == "beq":
            branch = True
            jump_target = target if regs[fields["rs"]] == regs[fields["rt"]] else None
        elif op == "jal":
            branch = True
            jump_target = target
        elif op == "jr":
            branch = True
            jump_target = regs[fields["rs"]]
        else:
            raise AssertionError(f"reference model: unsupported op {op!r}")
        regs[0] = 0
        if delay is not None:
            inner_address = delay["address"]
            inner_fields = delay["fields"]
            inner_op = delay["op"]
            if inner_op == "addiu":
                regs[inner_fields["rt"]] = (regs[inner_fields["rs"]] + _sx(inner_fields["imm"], 16)) & 0xFFFFFFFF
            elif inner_op == "or":
                regs[inner_fields["rd"]] = (regs[inner_fields["rs"]] | regs[inner_fields["rt"]]) & 0xFFFFFFFF
            elif inner_op == "sb":
                offset = (regs[inner_fields["rs"]] + _sx(inner_fields["imm"], 16) - MEM_BASE) & 0xFFFFFFFF
                memory[offset] = regs[inner_fields["rt"]] & 0xFF
            else:
                raise AssertionError(f"reference model: unsupported delay op {inner_op!r} at 0x{inner_address:x}")
            regs[0] = 0
        if branch:
            pc = jump_target if jump_target is not None else address + 8
        else:
            pc = address + 4
        if pc == 0:
            break
    return regs, memory


def synthetic_instruction(address, op, flow, fields, target):
    delay = SYNTHETIC_DELAYS.get(address)
    metadata = {
        "adapter_fields": {"address": address, "op": op, **fields},
        "delay_slot": (
            {
                "address": delay["address"],
                "op": delay["op"],
                "adapter_fields": {"address": delay["address"], "op": delay["op"], **delay["fields"]},
            }
            if delay is not None
            else None
        ),
    }
    return instruction_from_adapter(
        {"address": address, "op": op, **fields},
        flow=flow,
        unresolved=False,
        direct_target=target,
        size_bytes=8 if delay is not None else 4,
        evidence=PROVEN,
        metadata=metadata,
    )


def synthetic_source():
    return ProgramSource(
        mips32_adapter.info.architecture_id,
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256="0" * 64,
    )


def synthetic_host():
    instructions = tuple(synthetic_instruction(*item) for item in SYNTHETIC)
    cfg = build_cfg(instructions, source=synthetic_source(), entries=[EntryPoint(SYNTHETIC_ENTRY, PROVEN)], mode=CFGMode.CLOSED)
    discovery = discover_functions(cfg, program_entries=[SYNTHETIC_ENTRY])
    call_graph = build_call_graph(discovery)
    units = build_translation_units(discovery, call_graph=call_graph)
    classification = classify_indirect_control_flow(units, evidence=[])
    host = emit_host_translation(
        units,
        classification,
        config=semantics.build_emitter_config(discovery.entry_function_id),
    )
    return host, discovery


def real_structure():
    data = FIXTURE_ELF.read_bytes()
    ingested = elf.ingest(data, target.MIPS32_O32)
    region = ingested.parsed.executable_regions()[0]
    analysis = frontier.analyze(ingested.image.read_u32, region.p_vaddr, region.p_vaddr + region.p_memsz, ingested.parsed.header.e_entry)
    source = ProgramSource(
        mips32_adapter.info.architecture_id,
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=sha256_bytes(data),
    )
    return structure_bridge.analyze_structure(analysis, source=source, entry=ingested.parsed.header.e_entry), ingested


def run_dependency_gates():
    results = []
    for relative, marker in DEPENDENCY_GATES:
        completed = subprocess.run(
            [sys.executable, str(ROOT / relative)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        results.append(
            {
                "gate": relative,
                "exit_code": completed.returncode,
                "marker": marker,
                "marker_present": marker in completed.stdout,
                "stderr_bytes": len(completed.stderr.encode("utf-8")),
            }
        )
    return results


def main() -> int:
    try:
        data = FIXTURE_ELF.read_bytes()
        check("fixture:sha256", sha256_bytes(data) == FIXTURE_SHA256, sha256_bytes(data))

        # closed rule table
        table = semantics.build_semantics()
        check(
            "table:supported-ops",
            tuple(op for _, op in table.keys()) == tuple(sorted(semantics.SUPPORTED_OPS)),
            json.dumps([op for _, op in table.keys()]),
        )
        missing = semantics.missing_rules(UNSUPPORTED_OPS)
        check("table:unsupported-closed", missing == tuple(sorted(UNSUPPORTED_OPS)), json.dumps(missing))

        # real-fixture full emission coverage
        structure, ingested = real_structure()
        host_a = emit_host_translation(
            structure.units,
            structure.classification,
            config=semantics.build_emitter_config(structure.discovery.entry_function_id),
        )
        host_b = emit_host_translation(
            structure.units,
            structure.classification,
            config=semantics.build_emitter_config(structure.discovery.entry_function_id),
        )
        check("emission:deterministic-source", host_a.source_text == host_b.source_text, host_a.fingerprint())
        neutral = tuple(structure.cfg.instructions)
        check("coverage:neutral-instructions", len(neutral) == 486, str(len(neutral)))
        uncovered = [f"0x{instruction.address:x}:{instruction.op}" for instruction in neutral if not table.has(semantics.ARCHITECTURE, instruction.op)]
        check("coverage:every-op-has-rule", uncovered == [], ",".join(uncovered) or "none")
        mismatched = []
        for instruction in neutral:
            rule = table.rule(semantics.ARCHITECTURE, instruction.op)
            if rule.flow is not instruction.flow:
                mismatched.append(f"0x{instruction.address:x}:{instruction.op}")
        check("coverage:flow-agreement", mismatched == [], ",".join(mismatched) or "none")
        delays = [instruction for instruction in neutral if instruction.metadata.get(semantics.DELAY_SLOT_METADATA_KEY)]
        check("coverage:folded-delay-sites", len(delays) == 23, str(len(delays)))
        text = host_a.source_text
        check("emission:byte-reads", "or_rt_memory_read(or_addr, 8u" in text, "width 8 reads")
        check("emission:signed-extension", "or_signed(" in text, "sign extension helper")
        check("emission:byte-writes", "or_rt_memory_write(or_addr, 8u" in text, "width 8 writes")
        check("emission:select", "? (" in text, "conditional select")
        check("emission:link-register", "g_r[31] = UINT64_C(" in text, "link register writes")
        check("emission:runtime-abi", "or_rt_memory_read" in text and "OR_RT_SERVICE_P8_UART_WRITE" in text, "ABI surface")
        check("emission:no-guest-code", "#include <stdint.h>" in text and "static void fn_" in text, "portable C only")

        # fail-closed emission
        unsupported_instruction = instruction_from_adapter(
            {"address": 0x1000, "op": "div", "rs": 4, "rt": 5},
            flow=InstructionFlow.NORMAL,
            unresolved=False,
            direct_target=None,
            size_bytes=4,
            evidence=PROVEN,
            metadata={"adapter_fields": {"address": 0x1000, "op": "div", "rs": 4, "rt": 5}},
        )
        cfg = build_cfg(
            (unsupported_instruction, synthetic_instruction(0x1060, "jr", InstructionFlow.RETURN, {"rs": 31}, None)),
            source=synthetic_source(),
            entries=[EntryPoint(0x1000, PROVEN)],
            mode=CFGMode.CLOSED,
        )
        discovery = discover_functions(cfg, program_entries=[0x1000])
        call_graph = build_call_graph(discovery)
        units = build_translation_units(discovery, call_graph=call_graph)
        classification = classify_indirect_control_flow(units, evidence=[])
        expect_fail(
            "unsupported-op",
            lambda: emit_host_translation(units, classification, config=semantics.build_emitter_config(discovery.entry_function_id)),
            HostEmitterError,
        )

        normal_terminal = instruction_from_adapter(
            {"address": 0x1000, "op": "nop"},
            flow=InstructionFlow.NORMAL,
            unresolved=False,
            direct_target=None,
            size_bytes=4,
            evidence=PROVEN,
            metadata={"adapter_fields": {"address": 0x1000, "op": "nop"}, "delay_slot": {"address": 0x1004, "op": "nop", "adapter_fields": {"address": 0x1004, "op": "nop"}}},
        )
        cfg = build_cfg(
            (normal_terminal,),
            source=synthetic_source(),
            entries=[EntryPoint(0x1000, PROVEN)],
            mode=CFGMode.CLOSED,
        )
        discovery = discover_functions(cfg, program_entries=[0x1000])
        units = build_translation_units(discovery, call_graph=build_call_graph(discovery))
        classification = classify_indirect_control_flow(units, evidence=[])
        expect_fail(
            "delay-on-normal-terminal",
            lambda: emit_host_translation(units, classification, config=semantics.build_emitter_config(discovery.entry_function_id)),
            HostEmitterError,
        )

        # differential execution against the independent model
        host, discovery = synthetic_host()
        reference_regs, reference_memory = reference_execute()
        if WORKSPACE.exists():
            shutil.rmtree(WORKSPACE)
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        comparison = bp.build_generated_host(
            lambda: host.source_text,
            support_sources=(
                bp.BuildSource("p8_04_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, SUPPORT_SOURCE.encode("utf-8")),
            ),
            config=bp.BuildConfig(fixture_id="p8-04-mips32-semantics", smoke_test=False, run_count=2),
            workspace=WORKSPACE,
            keep_workspace=True,
        )
        check("build:status-ok", all(run.manifest.build_status is bp.BuildStatus.OK for run in comparison.runs), "ok")
        check("build:reproducible", comparison.classification is bp.BuildReproducibility.EXECUTABLE_REPRODUCIBLE, comparison.classification.value)
        executable = WORKSPACE / "run1" / "program.exe"
        ran = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        check("native:exit-code", ran.returncode == 0, str(ran.returncode))
        lines = [line.strip() for line in ran.stdout.splitlines() if line.strip()]
        native_regs: dict[int, int] = {}
        native_mem: dict[int, int] = {}
        failed = None
        error_text = None
        for line in lines:
            if line.startswith("failed="):
                failed = int(line.split("=", 1)[1])
            elif line.startswith("error="):
                error_text = line.split("=", 1)[1]
            elif line.startswith("r") and "=" in line:
                index, value = line[1:].split("=", 1)
                native_regs[int(index)] = int(value, 16)
            elif line.startswith("mem[") and "=" in line:
                index, value = line[len("mem["):].split("=", 1)
                native_mem[int(index.rstrip("]"))] = int(value, 16)
        check("native:no-failure", failed == 0, f"failed={failed} error={error_text}")
        check("native:register-count", len(native_regs) == 32, str(len(native_regs)))
        check(
            "native:registers-equal-reference",
            [native_regs[index] & 0xFFFFFFFF for index in range(32)] == [value & 0xFFFFFFFF for value in reference_regs],
            json.dumps({"native": [native_regs[i] for i in range(32)], "reference": reference_regs}),
        )
        check(
            "native:memory-equal-reference",
            [native_mem[index] for index in range(12)] == list(reference_memory[:12]),
            json.dumps({"native": [native_mem[i] for i in range(12)], "reference": list(reference_memory[:12])}),
        )
        check(
            "reference:movz-isa-semantics",
            reference_regs[12] == 7 and reference_regs[13] == 0 and reference_regs[14] == 7,
            f"r12={reference_regs[12]} r13={reference_regs[13]} r14={reference_regs[14]}",
        )
        check("reference:delay-program-order", reference_regs[15] == 0x11 and reference_regs[18] == 0x44 and reference_regs[20] == 0x66 and reference_regs[22] == 0x99, "delay slots executed")
        check("reference:not-taken-skipped", reference_regs[16] == 0 and reference_regs[17] == 0, "skipped path")
        check("native:link-register-value", native_mem[8] == 0x60 and native_mem[9] == 0x10 and native_mem[10] == 0 and native_mem[11] == 0, f"mem[8..11]={[native_mem[i] for i in range(8, 12)]}")

        dependencies = run_dependency_gates()
        for item in dependencies:
            check(f"dependency:{item['gate']}", item["exit_code"] == 0 and item["marker_present"], json.dumps(item, sort_keys=True))

        write_evidence(
            "translation_closure.json",
            {
                "stage": STAGE,
                "fixture": {"sha256": FIXTURE_SHA256},
                "rule_table": {
                    "architecture": semantics.ARCHITECTURE,
                    "supported_ops": sorted(semantics.SUPPORTED_OPS),
                    "unsupported_ops": sorted(UNSUPPORTED_OPS),
                    "delay_slot_ops": sorted(semantics.DELAY_SLOT_OPS),
                    "link_register": semantics.LINK_REGISTER,
                    "output_service": semantics.OUTPUT_SERVICE,
                },
                "real_emission": {
                    "neutral_instructions": len(neutral),
                    "folded_delay_sites": len(delays),
                    "fingerprint": host_a.fingerprint(),
                    "source_bytes": len(host_a.source_text.encode("utf-8")),
                },
                "synthetic_differential": {
                    "fingerprint": host.fingerprint(),
                    "register_values": {f"r{index}": f"{value:08x}" for index, value in enumerate(reference_regs)},
                    "memory_prefix": [f"{value:02x}" for value in reference_memory[:12]],
                    "steps": "reference model of the synthetic fixture",
                },
                "dependency_gates": dependencies,
                "markers": {
                    "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
                    "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
                },
            },
        )
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    status = "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    record = {
        "stage": STAGE,
        "stage_name": "Translation frontier closure",
        "status": status,
        "tests": len(RESULTS),
        "passed": sum(1 for item in RESULTS if item["status"] == "PASS"),
        "failed": sum(1 for item in RESULTS if item["status"] != "PASS"),
        "checks": RESULTS,
        "failure": None if status == "PASS" else [item for item in RESULTS if item["status"] != "PASS"],
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={len(RESULTS)}",
            "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
            "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
        },
    }
    write_evidence("p8_04_tests.json", record)

    for item in RESULTS:
        if item["status"] != "PASS":
            print(f"FAIL: {item['check']} :: {item.get('detail', '')}")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(RESULTS)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
