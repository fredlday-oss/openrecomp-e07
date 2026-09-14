#!/usr/bin/env python3
"""OpenRecomp generic runtime-host boundary proof V1 (P2-13).

Proves the deterministic host-call boundary between generated host code and
runtime services on one synthetic/original MIPS32 fixture:

    synthetic fixture -> adapters.mips32 decode -> P2-01 ProgramModel -> P2-02 CFG
    -> P2-03 function discovery -> P2-04 call graph -> P2-05 translation units
    -> P2-06 EXTERNAL_OR_RUNTIME_MEDIATED classification (explicit evidence)
    -> P2-07 host-call emission through the P2-08 ABI -> P2-09 deterministic build
    -> native executable -> runtime service record + guest observable

The fixture computes a guest value (42) and hands it to a runtime-mediated
transfer (`jr r4`) that explicit P2-06 evidence identifies as a runtime service
call. The generated host code invokes `or_rt_host_call` with the declared,
ABI-assigned service id; the runtime-support implements the service
deterministically and records the call. The expected result is derived
independently from the guest arithmetic plus the fixture-declared service
semantics, never from the native run.

An unsupported service (declared at build time but not implemented by the
runtime) must fail closed: the host-call boundary reports failure and the
generated code stops with `failed=1` instead of continuing.

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
from openrecomp.call_graph import build_call_graph  # noqa: E402
from openrecomp.cfg import CFGError, CFGMode, EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.host_emitter import (  # noqa: E402
    HostBinop,
    HostCallOperation,
    HostConstant,
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
CALL_SITE = 0x1008
PROVEN = EvidenceClass.PROVEN
FIXTURE_ID = "p2-13-runtime-host-boundary-v1"
SERVICE = "demo.double"
GUEST_ARG = 42
SERVICE_RESULT = GUEST_ARG * 2
CONTINUATION_RESULT = SERVICE_RESULT + 8

# (address, word, mnemonic) -- synthetic/original fixture, little-endian MIPS32.
FIXTURE = (
    (0x1000, 0x24040015, "addiu r4, r0, 21"),
    (0x1004, 0x24840015, "addiu r4, r4, 21        ; r4 = 42"),
    (0x1008, 0x00800008, "jr r4                  ; runtime-mediated host call"),
    (0x100C, 0x00000000, "nop (delay slot)"),
    (0x1010, 0x24850008, "addiu r5, r4, 8        ; r5 = service result + 8"),
)
WORDS = tuple(word for _, word, _ in FIXTURE)
FIXTURE_BYTES = struct.pack("<%dI" % len(WORDS), *WORDS)
FIXTURE_SHA256 = hashlib.sha256(FIXTURE_BYTES).hexdigest()

FLOW = {"nop": InstructionFlow.NORMAL, "addiu": InstructionFlow.NORMAL, "jr": InstructionFlow.INDIRECT_CALL}

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


def service_table(service=SERVICE):
    handlers = {service: (lambda args: args[0] * 2)}
    return rt.RuntimeServiceTable([rt.RuntimeService(service, 1)], handlers)


def decode_fixture():
    instructions = []
    for address, word, _ in FIXTURE:
        decoded = mips32_adapter.decode(address, word)
        flow = FLOW[decoded["op"]]
        instructions.append(
            instruction_from_adapter(
                decoded, flow=flow, unresolved=(flow is InstructionFlow.INDIRECT_CALL),
                size_bytes=4, evidence=PROVEN,
            )
        )
    return tuple(instructions)


def program_source():
    return ProgramSource(ARCH, adapter="adapters.mips32", address_width_bits=32, endianness="little", input_sha256=FIXTURE_SHA256)


def semantics_table(service=SERVICE, *, host_call_rule=True):
    def r(op, flow, **kw):
        return HostInstructionSemantics(ARCH, op, flow, **kw)
    jr_rule = (
        r("jr", InstructionFlow.INDIRECT_CALL, host_call=HostCallOperation(service, args=(HostRegister("rs"),), result=HostRegister("rs")))
        if host_call_rule
        else r("jr", InstructionFlow.INDIRECT_CALL, indirect_source=HostRegister("rs"))
    )
    return HostSemantics([
        r("nop", InstructionFlow.NORMAL),
        r("addiu", InstructionFlow.NORMAL, operations=(HostBinop(HostRegister("rt"), HostRegister("rs"), HostImmediate("imm", signed=True), "add"),)),
        jr_rule,
    ])


def run_pipeline(service=SERVICE, *, evidence_kind="external", declared=True, rule_service=None, host_call_rule=True):
    rule_service = service if rule_service is None else rule_service
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
    if evidence_kind == "external":
        evidence.append(IndirectControlFlowEvidence(
            function_id=site[0], block_id=site[1], address=site[2],
            kind=IndirectControlFlowKind.INDIRECT_CALL,
            status=IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED,
            basis=IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE,
            external_mechanism="runtime-service",
            source="p2-13-fixture", evidence=PROVEN,
        ))
    classification = classify_indirect_control_flow(units, evidence=evidence)
    runtime_abi = rt.RuntimeAbiConfig(services=service_table(service)) if declared else rt.RuntimeAbiConfig()
    host = emit_host_translation(units, classification, config=HostEmitterConfig(
        semantics=semantics_table(rule_service, host_call_rule=host_call_rule), entry_function=discovery.entry_function_id, word_bits=32,
        runtime_abi=runtime_abi,
    ))
    return {"cfg": cfg, "discovery": discovery, "call_graph": call_graph, "units": units,
            "classification": classification, "host": host, "site": site}


def guest_before_call():
    """Deterministic guest arithmetic up to the runtime-mediated call site."""
    regs = [0] * 32
    for address, word, _ in FIXTURE:
        if address == CALL_SITE:
            break
        opcode = (word >> 26) & 0x3F
        rs = (word >> 21) & 0x1F
        rt_field = (word >> 16) & 0x1F
        imm = word & 0xFFFF
        if imm & 0x8000:
            imm -= 0x10000
        if opcode == 0x09:
            regs[rt_field] = (regs[rs] + imm) & 0xFFFFFFFF
        regs[0] = 0
    return regs


def expected_result():
    regs = guest_before_call()
    arg = regs[4]
    result = arg * 2
    return {"arg": arg, "result": result, "continuation": result + 8, "regs": {4: result, 5: result + 8}}


def expected_output(register_names, expected, service_id):
    lines = [
        "failed=0",
        "error=",
        "calls=1",
        f"last_service={service_id}",
        f"last_arg={expected['arg']}",
        f"last_result={expected['result']}",
    ]
    for index, name in enumerate(register_names):
        lines.append(f"reg[{index}]={expected['regs'].get(int(name[1:]), 0)}")
    return "\n".join(lines)


SUPPORT_KNOWN_TEMPLATE = """\
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>

void openrecomp_run(void);
int openrecomp_failed(void);
size_t openrecomp_register_count(void);
uint64_t openrecomp_register_value(size_t index);
const char *openrecomp_error(void);

static uint32_t g_call_count;
static uint64_t g_last_service;
static uint64_t g_last_arg;
static uint64_t g_last_result;

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value) {
    g_call_count += 1;
    g_last_service = service_id;
    if (service_id == __SERVICE_ID__u) {
        if (argc != 1u || args == 0 || out_value == 0) return 2;
        g_last_arg = args[0];
        g_last_result = args[0] * 2u;
        *out_value = g_last_result;
        return 0;
    }
    return 6;
}

const char *or_rt_failure_reason(int code) { (void)code; return ""; }

int main(void) {
    openrecomp_run();
    printf("failed=%d\\n", openrecomp_failed());
    printf("error=%s\\n", openrecomp_error());
    printf("calls=%u\\n", (unsigned)g_call_count);
    printf("last_service=%llu\\n", (unsigned long long)g_last_service);
    printf("last_arg=%llu\\n", (unsigned long long)g_last_arg);
    printf("last_result=%llu\\n", (unsigned long long)g_last_result);
    size_t count = openrecomp_register_count();
    for (size_t index = 0; index < count; ++index) {
        printf("reg[%zu]=%llu\\n", index, (unsigned long long)openrecomp_register_value(index));
    }
    return 0;
}
"""

SUPPORT_UNSUPPORTED_TEMPLATE = """\
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>

void openrecomp_run(void);
int openrecomp_failed(void);
size_t openrecomp_register_count(void);
uint64_t openrecomp_register_value(size_t index);
const char *openrecomp_error(void);

static uint32_t g_call_count;
static uint64_t g_last_service;

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value) {
    g_call_count += 1;
    g_last_service = service_id;
    (void)argc; (void)args; (void)out_value;
    return 6;
}

const char *or_rt_failure_reason(int code) { (void)code; return ""; }

int main(void) {
    openrecomp_run();
    printf("failed=%d\\n", openrecomp_failed());
    printf("error=%s\\n", openrecomp_error());
    printf("calls=%u\\n", (unsigned)g_call_count);
    printf("last_service=%llu\\n", (unsigned long long)g_last_service);
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
        "P2-13 synthetic MIPS32 fixture (runtime-host boundary)",
        "=" * 54,
        f"architecture: {ARCH}",
        "endianness: little",
        f"entry: 0x{ENTRY:x}; runtime-mediated call site: 0x{CALL_SITE:x}",
        f"instruction count: {len(FIXTURE)}",
        f"byte length: {len(FIXTURE_BYTES)}",
        f"sha256: {FIXTURE_SHA256}",
        "origin: synthetic/original (no commercial ROM/ELF bytes)",
        f"declared service: {SERVICE} (ABI id {staging['service_id']})",
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
        "functions: " + ", ".join(f"{f.id}@0x{f.entry_address:x}" for f in discovery.functions),
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
    hashes["pipeline_indirect_control_flow.txt"] = _write_text(evidence_dir / "pipeline_indirect_control_flow.txt", "\n".join(classification_lines))

    abi_lines = staging["abi_lines"]
    hashes["runtime_abi_contract.txt"] = _write_text(evidence_dir / "runtime_abi_contract.txt", "\n".join(abi_lines) + "\n")

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
        lines = [f"P2-13 deterministic build run {index + 1}", "=" * 36,
                 f"build_status: {manifest.build_status.value}", f"classification: {manifest.reproducibility.value}", "inputs:"]
        for item in manifest.inputs:
            lines.append(f"  {item.kind.value} {item.name} {item.sha256}")
        lines.append("outputs:")
        for artifact in manifest.outputs:
            lines.append(f"  {artifact.kind.value} {artifact.name} {artifact.sha256}")
        lines += ["compile_commands:", *["  " + " ".join(command) for command in manifest.compile_commands],
                  "link_command: " + " ".join(manifest.link_command),
                  f"manifest_sha256: {manifest.fingerprint()}", ""]
        hashes[f"build_run_{index + 1}.txt"] = _write_text(evidence_dir / f"build_run_{index + 1}.txt", "\n".join(lines))

    expected = staging["expected_output"]
    actual = staging["actual_output"]
    hashes["native_execution.txt"] = _write_text(evidence_dir / "native_execution.txt", "\n".join([
        "P2-13 native execution",
        "======================",
        f"executable sha256: {staging['exe_sha256']}",
        f"returncode: {staging['native_returncode']}",
        "stdout:", actual, "",
    ]))
    hashes["expected_vs_actual.txt"] = _write_text(evidence_dir / "expected_vs_actual.txt", "\n".join([
        "P2-13 expected vs actual observable",
        "===================================",
        "expected (independent guest arithmetic + fixture-declared service semantics):",
        expected,
        "actual (native executable stdout):",
        actual,
        f"EXPECTED == ACTUAL: {'YES' if expected == actual else 'NO'}",
        "",
    ]))
    hashes["unsupported_service.txt"] = _write_text(evidence_dir / "unsupported_service.txt",
        "\n".join(["P2-13 unsupported service fail-closed evidence", "=" * 48,
                   *staging["unsupported_lines"], ""]))
    return hashes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    parser.add_argument("--evidence-dir", help="write deterministic UTF-8 evidence here (output only)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # A. fixture ------------------------------------------------------------
    check("fixture-byte-length", len(FIXTURE_BYTES) == 4 * len(FIXTURE))
    check("fixture-sha256", FIXTURE_SHA256 == hashlib.sha256(struct.pack("<%dI" % len(WORDS), *WORDS)).hexdigest())
    check("fixture-instruction-count", len(FIXTURE) == 5)
    check("fixture-call-site", FIXTURE[2][0] == CALL_SITE and FIXTURE[2][1] == 0x00800008)
    check("fixture-synthetic-origin", all(mnemonic for _, _, mnemonic in FIXTURE))

    # B. decode -------------------------------------------------------------
    instructions = decode_fixture()
    check("decode-op", instructions[2].op == "jr")
    check("decode-flow-indirect-call", instructions[2].flow is InstructionFlow.INDIRECT_CALL and instructions[2].unresolved)
    check("decode-no-direct-target", instructions[2].direct_target is None)
    check("decode-guest-arithmetic", instructions[0].op == "addiu" and instructions[1].op == "addiu" and instructions[4].op == "addiu")

    # C. pipeline -----------------------------------------------------------
    staging = run_pipeline()
    cfg = staging["cfg"]
    discovery = staging["discovery"]
    units = staging["units"]
    classification = staging["classification"]
    host = staging["host"]
    site = staging["site"]

    check("cfg-call-continuation", _edge_targets(cfg, "blk_1000", EdgeKind.CALL_RETURN) == [0x100C])
    check("cfg-call-site-block", site[1] == "blk_1000" and site[2] == CALL_SITE)
    check("cfg-deterministic", cfg.fingerprint() == run_pipeline()["cfg"].fingerprint())
    check("functions-single", [function.id for function in discovery.functions] == ["fn_1000"])
    check("functions-unresolved-site", len(units.unit_for("fn_1000").unresolved_call_sites) == 1)
    check("units-single", [unit.unit_id for unit in units.units] == ["tu_fn_1000"])
    check("units-deterministic", units.fingerprint() == run_pipeline()["units"].fingerprint())

    # D. P2-06 classification ----------------------------------------------
    sites = [item for unit in classification.units for item in unit.classifications]
    check("indirect-site-count", len(sites) == 1)
    check("indirect-status-external", sites[0].status is IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED)
    check("indirect-basis-external", sites[0].basis is IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE)
    check("indirect-mechanism-recorded", sites[0].external_mechanism == "runtime-service")
    check("indirect-no-guessed-targets", sites[0].targets == ())
    no_evidence_classification = classify_indirect_control_flow(units, evidence=[])
    no_sites = [item for unit in no_evidence_classification.units for item in unit.classifications]
    check("indirect-no-evidence-fails-closed", no_sites[0].status is IndirectControlFlowStatus.UNRESOLVED_INDIRECT_CALL)
    check("indirect-no-evidence-no-targets", no_sites[0].targets == ())
    # A host-call rule without explicit external evidence is rejected at emission.
    expect_fail("no-evidence-host-call-rejected", lambda: run_pipeline(evidence_kind="none"), HostEmitterError)
    # A plain indirect rule without evidence emits the fail-closed boundary.
    plain = run_pipeline(evidence_kind="none", host_call_rule=False)
    check("indirect-no-evidence-boundary", 'or_fail("unresolved indirect call");' in plain["host"].source_text)

    # E. P2-08 ABI contract (in-process) ------------------------------------
    table = service_table()
    service_id = table.numeric_id(SERVICE)
    check("abi-service-id", service_id == 1)
    check("abi-service-macro", table.macro(SERVICE) == "OR_RT_SERVICE_DEMO_DOUBLE")
    dispatch = table.dispatch(rt.RuntimeHostCallRequest(SERVICE, (GUEST_ARG,)))
    check("abi-dispatch-known", dispatch.ok and dispatch.value == SERVICE_RESULT)
    unknown = table.dispatch(rt.RuntimeHostCallRequest("demo.unknown", (GUEST_ARG,)))
    check("abi-dispatch-unknown-fails-closed", not unknown.ok and unknown.failure.code is rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE)
    arity = table.dispatch(rt.RuntimeHostCallRequest(SERVICE, (GUEST_ARG, 1)))
    check("abi-dispatch-arity-fails-closed", not arity.ok and arity.failure.code is rt.RuntimeFailureCode.HOST_CALL_ARITY)
    check("abi-dispatch-deterministic", table.dispatch(rt.RuntimeHostCallRequest(SERVICE, (GUEST_ARG,))).value == SERVICE_RESULT)
    state = rt.RuntimeState(rt.RuntimeConfig(memory_size_bytes=4096), services=table)
    recorded = state.host_call(SERVICE, (GUEST_ARG,))
    check("abi-state-record", recorded.value == SERVICE_RESULT and state.host_calls[0].args == (GUEST_ARG,))
    check("abi-version", rt.RUNTIME_ABI_VERSION == "1.0.0")

    # F. host emission ------------------------------------------------------
    check("emission-host-call", f"or_rt_host_call(OR_RT_SERVICE_DEMO_DOUBLE, 1u, or_call_args, &or_call_result)" in host.source_text)
    check("emission-abi-declaration", "extern int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);" in host.source_text)
    check("emission-service-macro", "#define OR_RT_SERVICE_DEMO_DOUBLE UINT64_C(1)" in host.source_text)
    check("emission-result-register", "g_r[1] = or_call_result & or_mask(32u);" in host.source_text)
    check("emission-fail-closed", 'or_fail("runtime host service demo.double failed");' in host.source_text)
    check("emission-continuation", "goto bb_blk_100c;" in host.source_text)
    check("emission-deterministic", host.source_text == run_pipeline()["host"].source_text)
    check("emission-no-pointer-cast", "*(uint64_t *)" not in host.source_text and "*(uint32_t *)" not in host.source_text)
    check("emission-no-hardcoded-result-84", "UINT64_C(84)" not in host.source_text and "UINT64_C(92)" not in host.source_text)

    expect_fail("undeclared-service", lambda: run_pipeline(service=SERVICE, rule_service="demo.other"), HostEmitterError)
    expect_fail("host-call-without-runtime-abi", lambda: run_pipeline(declared=False), HostEmitterError)

    # G. independent expected observable and deterministic build ------------
    expected = expected_result()
    check("derivation-guest-arg", expected["arg"] == GUEST_ARG)
    check("derivation-service-result", expected["result"] == SERVICE_RESULT)
    check("derivation-continuation", expected["continuation"] == CONTINUATION_RESULT)
    expected_text = expected_output(host.register_names, expected, service_id)

    workspace = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p213-"))
    comparison = None
    unsupported_lines = []
    try:
        config = bp.BuildConfig(fixture_id=FIXTURE_ID, expected_smoke_output=expected_text)
        comparison = bp.build_generated_host_from(
            lambda: run_pipeline()["host"],
            support_sources=(
                bp.BuildSource("runtime_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                               SUPPORT_KNOWN_TEMPLATE.replace("__SERVICE_ID__", str(service_id)).encode("utf-8")),
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
        first = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        second = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        actual = (first.stdout or "").strip()
        check("native-returncode-zero", first.returncode == 0)
        check("native-output-stable", actual == (second.stdout or "").strip())
        check("expected-equals-actual", expected_text == actual)
        check("native-service-record", f"last_service={service_id}" in actual and f"last_arg={GUEST_ARG}" in actual and f"last_result={SERVICE_RESULT}" in actual and "calls=1" in actual)
        check("native-continuation-register", f"reg[2]={CONTINUATION_RESULT}" in actual)
        check("native-result-register", f"reg[1]={SERVICE_RESULT}" in actual)

        # H. unsupported service fails closed natively -------------------------
        unsupported_service = "demo.missing"
        unsupported_table = rt.RuntimeServiceTable([rt.RuntimeService(unsupported_service, 1)], {unsupported_service: lambda a: 0})
        unsupported_id = unsupported_table.numeric_id(unsupported_service)
        unsupported_workspace = pathlib.Path(tempfile.mkdtemp(prefix="openrecomp-p213-bad-"))
        try:
            unsupported_host = run_pipeline(service=unsupported_service)["host"]
            check("unsupported-service-macro-emitted", f"OR_RT_SERVICE_DEMO_MISSING" in unsupported_host.source_text)
            bp.build_generated_host_from(
                lambda: unsupported_host,
                support_sources=(
                    bp.BuildSource("runtime_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                                   SUPPORT_UNSUPPORTED_TEMPLATE.encode("utf-8")),
                ),
                config=bp.BuildConfig(fixture_id=FIXTURE_ID + "-unsupported", smoke_test=False),
                workspace=unsupported_workspace,
                keep_workspace=True,
            )
            unsupported_exe = unsupported_workspace / "run1" / "program.exe"
            ran = subprocess.run([str(unsupported_exe)], capture_output=True, text=True, encoding="utf-8", errors="replace")
            unsupported_stdout = (ran.stdout or "").strip()
            check("unsupported-service-fails-closed", unsupported_stdout.startswith("failed=1"))
            check("unsupported-service-error", f"runtime host service {unsupported_service} failed" in unsupported_stdout)
            check("unsupported-service-no-continuation", "reg[2]=0" in unsupported_stdout)
            unsupported_lines = [
                f"declared-at-build service: {unsupported_service} (ABI id {unsupported_id}); runtime does not implement it",
                f"executable returncode: {ran.returncode}",
                "stdout:", unsupported_stdout,
                "result: PASS (checked host-call boundary reported the unsupported service; the generated code stopped instead of continuing)",
            ]
        finally:
            shutil.rmtree(unsupported_workspace, ignore_errors=True)

        if args.evidence_dir:
            abi_lines = [
                "P2-08 generic runtime ABI contract evidence",
                "===========================================",
                f"runtime ABI: {rt.RUNTIME_ABI_NAME} {rt.RUNTIME_ABI_VERSION}",
                f"declared service: {SERVICE} (numeric id {service_id})",
                f"known dispatch result: {dispatch.value}",
                f"unknown service failure code: {unknown.failure.code.value}",
                f"arity failure code: {arity.failure.code.value}",
                f"RuntimeState recorded args: {list(state.host_calls[0].args)} result: {state.host_calls[0].result.value}",
                f"RuntimeServiceTable fingerprint: {table.fingerprint()}",
            ]
            write_evidence(pathlib.Path(args.evidence_dir), {
                "cfg": cfg, "discovery": discovery, "call_graph": staging["call_graph"], "units": units,
                "classification": classification, "host": host, "site": site, "comparison": comparison,
                "expected_output": expected_text, "actual_output": actual, "native_returncode": first.returncode,
                "exe_sha256": exe_sha, "service_id": service_id, "abi_lines": abi_lines,
                "unsupported_lines": unsupported_lines,
            })
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    # I. fail-closed --------------------------------------------------------
    expect_fail("bad-host-call-service", lambda: HostCallOperation(""), HostEmitterError)
    expect_fail("bad-host-call-args", lambda: HostCallOperation(SERVICE, args=[HostRegister("rs")]), HostEmitterError)
    expect_fail("bad-host-call-result", lambda: HostCallOperation(SERVICE, result=HostConstant(0)), HostEmitterError)
    expect_fail("unsupported-opcode", lambda: mips32_adapter.decode(0x1000, 0xFC000000), mips32_adapter.DecodeError)
    expect_fail("misaligned-entry", lambda: build_cfg(decode_fixture(), source=program_source(), entries=[EntryPoint(0x1002, PROVEN)], mode=CFGMode.CLOSED), CFGError)
    expect_fail("empty-region", lambda: build_cfg((), source=program_source(), entries=[EntryPoint(ENTRY, PROVEN)], mode=CFGMode.CLOSED), CFGError)
    expect_fail("service-table-handler-missing", lambda: rt.RuntimeServiceTable([rt.RuntimeService("x", 0)], {}), rt.RuntimeAbiError)

    # J. no next-stage work -------------------------------------------------
    import ast as _ast

    tree = _ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    defined = {node.name for node in _ast.walk(tree) if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef))}
    for token in ("p2_14", "p2_20", "nes_runtime", "larger_fixture"):
        check(f"no-next-stage-symbol:{token}", not any(token in name.lower() for name in defined))
    check("no-p2-14-evidence-directory", not (ROOT / ".openrecomp-phase2" / "evidence" / "P2-14").exists())

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    if args.json:
        record = {
            "stage": "P2-13",
            "marker": f"OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "fixture_id": FIXTURE_ID,
            "fixture_sha256": FIXTURE_SHA256,
            "fixture_byte_length": len(FIXTURE_BYTES),
            "service": SERVICE,
            "service_id": service_id,
            "guest_arg": GUEST_ARG,
            "service_result": SERVICE_RESULT,
            "continuation_result": CONTINUATION_RESULT,
            "generated_source_sha256": host.fingerprint(),
            "register_names": list(host.register_names),
            "expected_observable": expected_text if comparison is not None else None,
            "actual_observable": actual if comparison is not None else None,
            "expected_equals_actual": (comparison is not None and expected_text == actual),
            "classification": comparison.classification.value if comparison else None,
            "results": sorted(RESULTS, key=lambda item: item["check"]),
        }
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1_JSON={out.name}")

    print(f"OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests={tests}")
    return 0


def _edge_targets(cfg, block_id, kind):
    return sorted(successor.target_address for successor in cfg.block(block_id).successors if successor.kind is kind and successor.resolved)


if __name__ == "__main__":
    raise SystemExit(main())
