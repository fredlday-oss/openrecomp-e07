#!/usr/bin/env python3
"""Fail-closed tests for the OpenRecomp Generic Runtime ABI V1 (P2-08).

Proves `openrecomp/runtime_abi.py` is an architecture-neutral runtime contract:
a bounded, checked guest address space; a stable host-call boundary where
unknown services fail closed; generic input/frame/audio submission contracts;
an explicit deterministic failure model; and a versioned, deterministic runtime
state. It also proves the bounded P2-07 emitter integration: a host call is
emitted only when an explicit semantic rule names a service that the configured
runtime ABI declares, and every unsupported case still fails closed.

No P2-09 deterministic build pipeline is implemented or exercised. Optional
native compile/run is a bounded synthetic check against a hand-written runtime
stub, never an equivalence proof. Compiler availability is detected, never
assumed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import openrecomp.host_emitter as host_emitter  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402
from openrecomp.cfg import EntryPoint, build_cfg  # noqa: E402
from openrecomp.functions import discover_functions  # noqa: E402
from openrecomp.host_emitter import (  # noqa: E402
    HostCallOperation,
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
from openrecomp.program_model import DecodedInstruction, EvidenceClass, InstructionFlow, ProgramSource  # noqa: E402
from openrecomp.translation_units import build_translation_units  # noqa: E402

ARCH = "bounded-synthetic-v1"
PROV = EvidenceClass.PROVEN
NORMAL = InstructionFlow.NORMAL
RETURN = InstructionFlow.RETURN
INDIRECT_CALL = InstructionFlow.INDIRECT_CALL

CALL_KIND = IndirectControlFlowKind.INDIRECT_CALL
EXTERNAL = IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED
BOUNDED = IndirectControlFlowStatus.BOUNDED_CANDIDATES
EXTERNAL_EV = IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE
BOUNDED_EV = IndirectControlFlowBasis.BOUNDED_CANDIDATE_EVIDENCE

RESULTS: list[dict[str, str]] = []


def check(label, condition):
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}")


def expect_fail(label, thunk, error_type=rt.RuntimeAbiError):
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


def expect_runtime_fail(label, thunk, code):
    try:
        thunk()
    except rt.RuntimeAbiError as exc:
        if exc.failure is None or exc.failure.code is not code:
            RESULTS.append({"check": f"fault:{label}", "status": "FAIL"})
            raise AssertionError(f"{label}: failure code {exc.failure!r} != {code.value}")
        RESULTS.append({"check": f"fault:{label}", "status": "PASS"})
        print(f"PASS fault: {label} ({code.value})")
        return
    RESULTS.append({"check": f"fault:{label}", "status": "FAIL"})
    raise AssertionError(f"{label}: no runtime failure raised")


# --- P2-07 fixture helpers --------------------------------------------------
def I(address, op, size=1, flow=NORMAL, target=None, unresolved=False, fields=None, evidence=PROV):
    return DecodedInstruction(
        address=address,
        op=op,
        size_bytes=size,
        flow=flow,
        direct_target=target,
        unresolved=unresolved,
        evidence=evidence,
        metadata={"adapter_fields": dict(fields or {})},
    )


def source(width=32):
    return ProgramSource(ARCH, adapter="openrecomp.synthetic", address_width_bits=width)


def program(insns, entries, *, region_boundaries=(), width=32):
    cfg = build_cfg(
        insns,
        source=source(width),
        entries=[EntryPoint(address, PROV) for address in entries],
        region_boundaries=region_boundaries,
    )
    return build_translation_units(discover_functions(cfg, program_entries=entries))


def evidence(function_id, block_id, address, kind, status, basis, *, targets=(), mechanism=None, source_label="fixture"):
    return IndirectControlFlowEvidence(
        function_id=function_id,
        block_id=block_id,
        address=address,
        kind=kind,
        status=status,
        basis=basis,
        targets=targets,
        external_mechanism=mechanism,
        source=source_label,
        evidence=PROV,
    )


def host_call_rules():
    def rule(op, flow, **kw):
        return HostInstructionSemantics(ARCH, op, flow, **kw)

    return HostSemantics(
        [
            rule("li", NORMAL, operations=(HostConst(HostRegister("rd"), HostImmediate("imm")),)),
            rule("ret", RETURN, operations=()),
            rule(
                "call_rt",
                INDIRECT_CALL,
                host_call=HostCallOperation(
                    "demo.mul", args=(HostRegister("rs"), HostRegister("rt")), result=HostRegister("rd")
                ),
            ),
        ]
    )


def host_call_program():
    return program(
        [
            I(0x1000, "li", fields={"rd": 1, "imm": 6}),
            I(0x1001, "li", fields={"rd": 2, "imm": 7}),
            I(0x1002, "call_rt", flow=INDIRECT_CALL, unresolved=True, fields={"rs": 1, "rt": 2, "rd": 3}),
            I(0x1003, "ret", flow=RETURN),
        ],
        [0x1000],
    )


def indirect_call_site(units):
    for unit in units.units:
        for block in unit.blocks:
            terminal = block.terminal
            if terminal.flow is INDIRECT_CALL:
                return unit.function_id, block.id, terminal.address
    raise AssertionError("fixture has no indirect call site")


def host_call_classification(units, status=EXTERNAL, basis=EXTERNAL_EV, targets=(), mechanism="runtime-service"):
    function_id, block_id, address = indirect_call_site(units)
    return classify_indirect_control_flow(
        units,
        evidence=[
            evidence(function_id, block_id, address, CALL_KIND, status, basis, targets=targets, mechanism=mechanism)
        ],
    )


def service_table():
    return rt.RuntimeServiceTable(
        [rt.RuntimeService("demo.mul", 2), rt.RuntimeService("demo.noop", 0)],
        {"demo.mul": lambda args: args[0] * args[1], "demo.noop": lambda args: None},
    )


def emit_fixture(config):
    units = host_call_program()
    classification = host_call_classification(units)
    return emit_host_translation(units, classification, config=config)


def runtime_config(**kwargs):
    return rt.RuntimeConfig(memory_size_bytes=64, **kwargs)


# --- optional native compile ------------------------------------------------
def find_compiler():
    for name in ("clang", "gcc", "cc"):
        path = shutil.which(name)
        if path:
            return path
    return None


def compile_and_run(source_text, expected):
    compiler = find_compiler()
    if compiler is None:
        return None
    driver = (
        "\n"
        "int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value) {\n"
        "    if (service_id != OR_RT_SERVICE_DEMO_MUL) return OR_RT_UNKNOWN_HOST_SERVICE;\n"
        "    if (argc != 2u || args == 0 || out_value == 0) return OR_RT_HOST_CALL_ARITY;\n"
        "    *out_value = args[0] * args[1];\n"
        "    return OR_RT_OK;\n"
        "}\n"
        "int or_rt_memory_read(uint64_t a, uint32_t w, uint64_t *o){(void)a;(void)w;(void)o;return OR_RT_UNSUPPORTED_OPERATION;}\n"
        "int or_rt_memory_write(uint64_t a, uint32_t w, uint64_t v){(void)a;(void)w;(void)v;return OR_RT_UNSUPPORTED_OPERATION;}\n"
        "const char *or_rt_failure_reason(int c){(void)c;return \"\";}\n"
        "#include <stdio.h>\n"
        "int main(void){ openrecomp_run(); printf(\"%llu %d\\n\","
        " (unsigned long long)openrecomp_register_value(2), openrecomp_failed()); return 0; }\n"
    )
    with tempfile.TemporaryDirectory(prefix="openrecomp-p208-") as work:
        c_path = Path(work) / "generated.c"
        exe = Path(work) / ("generated.exe" if os.name == "nt" else "generated")
        c_path.write_text(source_text + driver, encoding="utf-8")
        built = subprocess.run([compiler, str(c_path), "-o", str(exe)], capture_output=True, text=True)
        if built.returncode != 0:
            return {"status": "compile-failed", "detail": (built.stderr or "").strip()[-400:]}
        ran = subprocess.run([str(exe)], capture_output=True, text=True)
        if ran.returncode != 0:
            return {"status": "run-failed", "detail": (ran.stderr or "").strip()[-400:]}
        observed = (ran.stdout or "").strip()
        return {"status": "ok", "observed": observed, "expected": expected, "match": observed == expected}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # A. ABI versioning ------------------------------------------------------
    check("abi-version-string", rt.RUNTIME_ABI_VERSION == "1.0.0")
    check("abi-version-current", rt.RuntimeAbiVersion.current() == rt.RuntimeAbiVersion(major=1, minor=0, patch=0))
    check("abi-version-parse-roundtrip", rt.RuntimeAbiVersion.parse(rt.RUNTIME_ABI_VERSION).version_string == rt.RUNTIME_ABI_VERSION)
    check("abi-version-str", str(rt.RUNTIME_ABI) == "openrecomp-generic-runtime-abi 1.0.0")
    check("abi-version-compatible", rt.RUNTIME_ABI.compatible_with(rt.RuntimeAbiVersion.current()))
    check("abi-version-incompatible-major", not rt.RuntimeAbiVersion(major=2).compatible_with(rt.RUNTIME_ABI))
    check("abi-version-document", rt.RUNTIME_ABI.to_document() == {"name": rt.RUNTIME_ABI_NAME, "major": 1, "minor": 0, "patch": 0})
    check("abi-config-default-compatible", rt.RuntimeAbiConfig().version.compatible_with(rt.RUNTIME_ABI))
    expect_fail("abi-version-bad-text", lambda: rt.RuntimeAbiVersion.parse("1.0"))
    expect_fail(
        "abi-config-incompatible",
        lambda: rt.RuntimeAbiConfig(version=rt.RuntimeAbiVersion(major=9)),
    )
    expect_fail(
        "config-incompatible-version",
        lambda: runtime_config(abi_version=rt.RuntimeAbiVersion(major=9)),
    )

    # B. deterministic construction / repeated-run identity ------------------
    state_a = rt.RuntimeState(runtime_config())
    state_b = rt.RuntimeState(runtime_config())
    check("state-construction-deterministic", state_a.fingerprint() == state_b.fingerprint())
    check("state-serialize-deterministic", state_a.serialize() == state_b.serialize())
    check("state-snapshot-version", state_a.snapshot()["runtime_abi"] == rt.RUNTIME_ABI_VERSION)
    check("state-initially-not-failed", not state_a.failed)
    check("state-starts-at-zero-steps", state_a.steps == 0)

    def scenario():
        state = rt.RuntimeState(runtime_config(seed=7), services=service_table())
        state.write(0, 0x1234, 16)
        state.write(4, 0xA5, 8, endianness="big")
        state.read(0, 16)
        state.set_input(rt.RuntimeInputSnapshot((True, False, True), (10, 20), 16))
        state.host_call("demo.mul", (3, 4))
        state.submit_frame(rt.RuntimeFrame(2, 1, rt.RuntimePixelFormat.RGBA8, bytes(range(8)), sequence=1))
        state.submit_audio(rt.RuntimeAudio(rt.RuntimeSampleFormat.U8, 8000, 1, 4, b"\x01\x02\x03\x04"))
        state.next_random()
        return state

    run_one = scenario()
    run_two = scenario()
    check("repeated-run-identity", run_one.fingerprint() == run_two.fingerprint())
    check("repeated-run-serialize-identity", run_one.serialize() == run_two.serialize())
    check("deterministic-rng-repeatable", run_one.next_random() == run_two.next_random())
    check("deterministic-rng-seed-sensitive", rt.RuntimeState(runtime_config(seed=1)).next_random() != rt.RuntimeState(runtime_config(seed=2)).next_random())
    check("snapshot-ser-roundtrip-json", json.loads(run_one.serialize().decode("utf-8"))["runtime_abi"] == rt.RUNTIME_ABI_VERSION)
    check("snapshot-no-absolute-path", not any(token in run_one.serialize().decode("utf-8") for token in ("D:\\", "C:\\", "/home/", "\\\\Users\\\\")))

    # C. memory read/write/width/endianness/boundaries -----------------------
    memory = rt.RuntimeMemory(16, endianness="little")
    memory.write(0, 0xAB, 8)
    check("memory-write-read-8", memory.read(0, 8) == 0xAB)
    memory.write(2, 0x1234, 16)
    check("memory-read-little-endian", memory.read(2, 16) == 0x1234)
    check("memory-read-big-endian-override", memory.read(2, 16, endianness="big") == 0x3412)
    memory.write(4, 0xDEADBEEF, 32)
    check("memory-read-32", memory.read(4, 32) == 0xDEADBEEF)
    memory.write(8, 0x0123456789ABCDEF, 64)
    check("memory-read-64", memory.read(8, 64) == 0x0123456789ABCDEF)
    check("memory-width-8", memory.try_read(0, 8).ok)
    check("memory-width-16", memory.try_read(2, 16).ok)
    check("memory-width-32", memory.try_read(4, 32).ok)
    check("memory-width-64", memory.try_read(8, 64).ok)
    memory.write(15, 0x7F, 8)
    check("memory-boundary-last-byte", memory.read(15, 8) == 0x7F)
    memory.write(0, 0xFFFF, 16)
    check("memory-boundary-zero", memory.read(0, 16) == 0xFFFF)
    check("memory-read-bytes-is-bytes", type(memory.read_bytes(0, 4)) is bytes)
    check("memory-snapshot-is-bytes", type(memory.snapshot()) is bytes)
    check("memory-fingerprint-stable", memory.fingerprint() == hashlib.sha256(memory.snapshot()).hexdigest())

    check("memory-oob-read-result", memory.try_read(16, 8).failure.code is rt.RuntimeFailureCode.MEMORY_OUT_OF_RANGE)
    check("memory-oob-write-result", memory.try_write(16, 1, 8).failure.code is rt.RuntimeFailureCode.MEMORY_OUT_OF_RANGE)
    check("memory-width-result", memory.try_read(0, 24).failure.code is rt.RuntimeFailureCode.MEMORY_WIDTH_UNSUPPORTED)
    expect_runtime_fail("memory-oob-read", lambda: rt.RuntimeMemory(8).read(8, 8), rt.RuntimeFailureCode.MEMORY_OUT_OF_RANGE)
    expect_runtime_fail("memory-oob-read-wide", lambda: rt.RuntimeMemory(8).read(4, 64), rt.RuntimeFailureCode.MEMORY_OUT_OF_RANGE)
    expect_runtime_fail("memory-oob-write", lambda: rt.RuntimeMemory(8).write(8, 1, 8), rt.RuntimeFailureCode.MEMORY_OUT_OF_RANGE)
    expect_runtime_fail("memory-address-overflow", lambda: rt.RuntimeMemory(8).read(rt.RUNTIME_MAX_ADDRESS, 32), rt.RuntimeFailureCode.MEMORY_ADDRESS_OVERFLOW)
    expect_runtime_fail("memory-address-beyond-64", lambda: rt.RuntimeMemory(8).read(1 << 64, 8), rt.RuntimeFailureCode.MEMORY_ADDRESS_OVERFLOW)
    expect_runtime_fail("memory-invalid-width", lambda: rt.RuntimeMemory(8).read(0, 24), rt.RuntimeFailureCode.MEMORY_WIDTH_UNSUPPORTED)
    expect_runtime_fail("memory-invalid-endianness", lambda: rt.RuntimeMemory(8).read(0, 8, endianness="middle"), rt.RuntimeFailureCode.MEMORY_ENDIANNESS_UNSUPPORTED)
    expect_fail("memory-zero-size", lambda: rt.RuntimeMemory(0))
    expect_fail(
        "memory-segment-overlap",
        lambda: rt.RuntimeMemory(16, segments=[
            rt.RuntimeMemorySegment(0, "a", b"abcdefgh"),
            rt.RuntimeMemorySegment(4, "b", b"wxyz"),
        ]),
    )
    expect_runtime_fail(
        "memory-segment-out-of-range",
        lambda: rt.RuntimeMemory(4, segments=[rt.RuntimeMemorySegment(2, "a", b"abcdef")]),
        rt.RuntimeFailureCode.MEMORY_OUT_OF_RANGE,
    )
    check("memory-segment-deterministic", rt.RuntimeMemory(8, segments=[rt.RuntimeMemorySegment(0, "boot", b"\x01\x02")]).read(0, 16) == 0x0201)
    check("memory-no-public-buffer", not hasattr(memory, "data") and not hasattr(memory, "buffer"))
    check("memory-snapshot-is-copy", memory.snapshot() is not memory.snapshot())

    # D. host calls ----------------------------------------------------------
    table = service_table()
    check("service-ids-canonical", table.service_ids == ("demo.mul", "demo.noop"))
    check("service-known-dispatch", table.dispatch(rt.RuntimeHostCallRequest("demo.mul", (6, 7))).value == 42)
    check("service-void-dispatch", table.dispatch(rt.RuntimeHostCallRequest("demo.noop", ())).ok)
    unknown = table.dispatch(rt.RuntimeHostCallRequest("missing.service", ()))
    check("service-unknown-fails-closed", not unknown.ok and unknown.failure.code is rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE)
    arity = table.dispatch(rt.RuntimeHostCallRequest("demo.mul", (1,)))
    check("service-arity-fails-closed", not arity.ok and arity.failure.code is rt.RuntimeFailureCode.HOST_CALL_ARITY)

    def raising_handler(_args):
        raise RuntimeError("boom")

    raising = rt.RuntimeServiceTable([rt.RuntimeService("demo.raise", 0)], {"demo.raise": raising_handler})
    raised = raising.dispatch(rt.RuntimeHostCallRequest("demo.raise", ()))
    check("service-handler-exception-fails-closed", not raised.ok and raised.failure.code is rt.RuntimeFailureCode.HOST_SERVICE_FAILED)
    bad_return = rt.RuntimeServiceTable([rt.RuntimeService("demo.bad", 0)], {"demo.bad": lambda _a: -1})
    check("service-negative-result-fails-closed", bad_return.dispatch(rt.RuntimeHostCallRequest("demo.bad", ())).failure.code is rt.RuntimeFailureCode.HOST_SERVICE_FAILED)
    check("service-macro-name", table.macro("demo.mul") == "OR_RT_SERVICE_DEMO_MUL")
    check("service-numeric-id", table.numeric_id("demo.mul") == 1 and table.numeric_id("demo.noop") == 2)
    check("service-document", table.to_document()["services"] == [{"service_id": "demo.mul", "arg_count": 2}, {"service_id": "demo.noop", "arg_count": 0}])
    expect_fail("service-duplicate", lambda: rt.RuntimeServiceTable([rt.RuntimeService("a", 0), rt.RuntimeService("a", 0)], {"a": lambda _a: None}))
    expect_fail("service-missing-handler", lambda: rt.RuntimeServiceTable([rt.RuntimeService("a", 0)], {}))
    expect_fail("service-handler-without-declaration", lambda: rt.RuntimeServiceTable([], {"a": lambda _a: None}))
    expect_fail("service-bad-id", lambda: rt.RuntimeService("1bad id", 0))
    expect_fail("service-negative-arity", lambda: rt.RuntimeService("x", -1))

    state = rt.RuntimeState(runtime_config(), services=table)
    call_result = state.host_call("demo.mul", (6, 7))
    check("state-host-call-result", call_result.ok and call_result.value == 42)
    check("state-host-call-record-count", len(state.host_calls) == 1)
    record = state.host_calls[0]
    check("host-call-argument-preservation", record.args == (6, 7))
    check("host-call-result-preservation", record.result.value == 42)
    check("host-call-sequence", record.sequence == 0)
    check("host-call-record-document", record.to_document()["service"] == "demo.mul")
    failed_call = state.host_call("missing.service", ())
    check("state-unknown-service-fails-closed", not failed_call.ok)
    check("state-unknown-service-recorded", state.host_calls[1].result.failure.code is rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE)

    # E. input ---------------------------------------------------------------
    canonical = rt.RuntimeInputSnapshot((True, False, False), (5, 0), 16)
    check("input-canonical-trims-digital", canonical.digital == (True,))
    check("input-canonical-trims-analog", canonical.analog == (5,))
    check("input-canonical-equivalence", canonical.fingerprint() == rt.RuntimeInputSnapshot((True,), (5,), 16).fingerprint())
    check("input-digital-document", canonical.to_document()["digital"] == [1])
    check("input-roundtrip-identity", rt.RuntimeInputSnapshot.deserialize(canonical.serialize()).fingerprint() == canonical.fingerprint())
    check("input-analog-bits-explicit", canonical.to_document()["analog_bits"] == 16)
    expect_fail("input-non-bool-digital", lambda: rt.RuntimeInputSnapshot((1,), (), 16))
    expect_fail("input-analog-over-width", lambda: rt.RuntimeInputSnapshot((), (1 << 16,), 16))
    expect_fail("input-negative-analog", lambda: rt.RuntimeInputSnapshot((), (-1,), 16))
    expect_fail("input-too-many-digital", lambda: rt.RuntimeInputSnapshot(tuple(True for _ in range(257)), (), 16))
    expect_fail("input-bad-analog-bits", lambda: rt.RuntimeInputSnapshot((), (), 24))
    expect_fail("input-malformed-document", lambda: rt.RuntimeInputSnapshot.from_document({"digital": [1]}))

    # F. frame ---------------------------------------------------------------
    frame = rt.RuntimeFrame(2, 1, rt.RuntimePixelFormat.RGBA8, bytes(range(8)), sequence=3)
    check("frame-descriptor-deterministic", frame.to_document() == rt.RuntimeFrame(2, 1, rt.RuntimePixelFormat.RGBA8, bytes(range(8)), sequence=3).to_document())
    check("frame-checksum-deterministic", frame.checksum() == hashlib.sha256(bytes(range(8))).hexdigest())
    check("frame-checksum-payload-sensitive", frame.checksum() != rt.RuntimeFrame(2, 1, rt.RuntimePixelFormat.RGBA8, bytes(range(1, 9))).checksum())
    check("frame-fingerprint-stable", frame.fingerprint() == rt.RuntimeFrame(2, 1, rt.RuntimePixelFormat.RGBA8, bytes(range(8)), sequence=3).fingerprint())
    check("frame-roundtrip-identity", rt.RuntimeFrame.deserialize(frame.serialize()).fingerprint() == frame.fingerprint())
    check("frame-descriptor-excludes-payload", "payload_hex" not in frame.to_document())
    check("frame-index8-size", rt.RuntimeFrame(2, 1, rt.RuntimePixelFormat.INDEX8, b"\x00\x01").checksum())
    expect_fail("frame-length-mismatch", lambda: rt.RuntimeFrame(2, 1, rt.RuntimePixelFormat.RGBA8, b"\x00" * 7))
    expect_fail("frame-zero-dimension", lambda: rt.RuntimeFrame(0, 1, rt.RuntimePixelFormat.GRAY8, b""))
    expect_fail("frame-bad-format", lambda: rt.RuntimeFrame(1, 1, "RGBA8", b"\x00" * 4))
    expect_fail("frame-malformed-document", lambda: rt.RuntimeFrame.from_document({"width": 1}))

    # G. audio ---------------------------------------------------------------
    audio = rt.RuntimeAudio(rt.RuntimeSampleFormat.S16LE, 44100, 2, 4, bytes(range(16)), sequence=2)
    check("audio-descriptor-deterministic", audio.to_document() == rt.RuntimeAudio(rt.RuntimeSampleFormat.S16LE, 44100, 2, 4, bytes(range(16)), sequence=2).to_document())
    check("audio-checksum-deterministic", audio.checksum() == hashlib.sha256(bytes(range(16))).hexdigest())
    check("audio-fingerprint-stable", audio.fingerprint() == rt.RuntimeAudio(rt.RuntimeSampleFormat.S16LE, 44100, 2, 4, bytes(range(16)), sequence=2).fingerprint())
    check("audio-roundtrip-identity", rt.RuntimeAudio.deserialize(audio.serialize()).fingerprint() == audio.fingerprint())
    check("audio-checksum-payload-sensitive", audio.checksum() != rt.RuntimeAudio(rt.RuntimeSampleFormat.S16LE, 44100, 2, 4, bytes(range(1, 17))).checksum())
    expect_fail("audio-length-mismatch", lambda: rt.RuntimeAudio(rt.RuntimeSampleFormat.S16LE, 44100, 2, 4, b"\x00" * 15))
    expect_fail("audio-zero-rate", lambda: rt.RuntimeAudio(rt.RuntimeSampleFormat.U8, 0, 1, 1, b"\x00"))
    expect_fail("audio-bad-format", lambda: rt.RuntimeAudio("S16LE", 44100, 1, 1, b"\x00\x00"))
    expect_fail("audio-malformed-document", lambda: rt.RuntimeAudio.from_document({"sample_format": "U8"}))

    # H. failure / trap ------------------------------------------------------
    trapped = rt.RuntimeState(runtime_config())
    trap_result = trapped.trap("synthetic unsupported operation")
    check("trap-fails-closed", not trap_result.ok and trap_result.failure.code is rt.RuntimeFailureCode.TRAP)
    check("trap-latched", trapped.failed and trapped.failure.code is rt.RuntimeFailureCode.TRAP)
    trapped.record_failure(rt.RuntimeFailure(rt.RuntimeFailureCode.UNSUPPORTED_OPERATION))
    check("trap-first-failure-preserved", trapped.failure.code is rt.RuntimeFailureCode.TRAP)
    check("failure-document-stable", rt.RuntimeFailure(rt.RuntimeFailureCode.TRAP, "x").to_document() == {"code": "TRAP", "detail": "x", "address": None, "width_bits": None})
    expected_codes = {
        "MEMORY_OUT_OF_RANGE", "MEMORY_WIDTH_UNSUPPORTED", "MEMORY_ADDRESS_OVERFLOW",
        "MEMORY_ENDIANNESS_UNSUPPORTED", "MEMORY_SEGMENT_OVERLAP", "UNKNOWN_HOST_SERVICE",
        "HOST_SERVICE_FAILED", "HOST_CALL_ARITY", "INPUT_INVALID", "FRAME_INVALID",
        "AUDIO_INVALID", "ABI_VERSION_MISMATCH", "UNSUPPORTED_OPERATION", "TRAP",
    }
    check("failure-codes-stable", set(rt.RUNTIME_FAILURE_CODES) == expected_codes)
    check("result-success-document", rt.RuntimeResult.success(5).to_document() == {"ok": True, "value": 5, "failure": None})
    expect_fail("result-inconsistent-success", lambda: rt.RuntimeResult(True, failure=rt.RuntimeFailure(rt.RuntimeFailureCode.TRAP)))
    expect_fail("result-inconsistent-failure", lambda: rt.RuntimeResult(False))
    expect_fail("result-negative-value", lambda: rt.RuntimeResult.success(-1))
    limited = rt.RuntimeState(rt.RuntimeConfig(memory_size_bytes=8, max_steps=1))
    limited.read(0, 8)
    expect_runtime_fail("state-step-limit", lambda: limited.read(0, 8), rt.RuntimeFailureCode.TRAP)

    # I. deterministic state, config, serialization --------------------------
    config = runtime_config(seed=11, endianness="big")
    check("config-roundtrip", rt.RuntimeConfig.from_document(json.loads(config.serialize().decode("utf-8"))) == config)
    check("config-serialize-stable", config.serialize() == runtime_config(seed=11, endianness="big").serialize())
    check("config-abi-version-recorded", json.loads(config.serialize().decode("utf-8"))["abi_version"]["major"] == 1)
    check("abi-config-serialize-stable", rt.RuntimeAbiConfig(services=table).fingerprint() == rt.RuntimeAbiConfig(services=service_table()).fingerprint())
    check("abi-config-document", rt.RuntimeAbiConfig().to_document()["services"] == {"services": []})
    expect_fail("config-zero-memory", lambda: rt.RuntimeConfig(0))
    expect_fail("config-bad-endianness", lambda: rt.RuntimeConfig(8, endianness="mixed"))
    expect_fail("abi-config-bad-services", lambda: rt.RuntimeAbiConfig(services="nope"))

    check("state-memory-deterministic", run_one.snapshot()["memory"] == run_two.snapshot()["memory"])
    check("state-host-call-log-deterministic", run_one.snapshot()["host_calls"] == run_two.snapshot()["host_calls"])
    check("state-frame-log-deterministic", run_one.snapshot()["frames"] == run_two.snapshot()["frames"])
    check("state-audio-log-deterministic", run_one.snapshot()["audio"] == run_two.snapshot()["audio"])

    module_source = Path(rt.__file__).read_text(encoding="utf-8")
    for token in ("import time", "import random", "import secrets", "import os", "import subprocess", "os.getpid", "os.environ", "uuid.uuid4", "datetime.now"):
        check(f"no-nondeterministic-dependency:{token}", token not in module_source)
    for token in ("memoryview", "ctypes", "from_buffer", "PyMemoryView"):
        check(f"no-host-pointer-mechanism:{token}", token not in module_source)
    for token in ("subprocess", "BuildPipeline", "def build_", "link_executable", "object_file"):
        check(f"no-p2-09-build-pipeline:{token}", token not in module_source)

    # J. P2-07 emitter integration ------------------------------------------
    abi_config = rt.RuntimeAbiConfig(services=service_table())
    integrated = emit_fixture(HostEmitterConfig(semantics=host_call_rules(), entry_function="fn_1000", runtime_abi=abi_config))
    check("emitter-emits-abi-version", "runtime_abi_version: openrecomp-generic-runtime-abi 1.0.0" in integrated.source_text)
    check("emitter-emits-support-codes", "OR_RT_UNKNOWN_HOST_SERVICE" in integrated.source_text and "OR_RT_OK = 0" in integrated.source_text)
    check("emitter-emits-service-macro", "#define OR_RT_SERVICE_DEMO_MUL UINT64_C(1)" in integrated.source_text)
    check("emitter-emits-host-call", "or_rt_host_call(OR_RT_SERVICE_DEMO_MUL, 2u, or_call_args, &or_call_result) != OR_RT_OK" in integrated.source_text)
    check("emitter-declares-boundary-extern", "extern int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);" in integrated.source_text)
    check("emitter-result-register", "g_r[2] = or_call_result & or_mask(32u);" in integrated.source_text)
    check("emitter-host-call-fail-closed-branch", 'or_fail("runtime host service demo.mul failed");' in integrated.source_text)
    check("emitter-host-call-continuation", "goto bb_" in integrated.source_text)
    check("emitter-no-platform-api", not any(token in integrated.source_text for token in ("D3D", "Vulkan", "OpenGL", "XAudio2", "WASAPI", "fopen", "SDL_")))
    check("emitter-portable-includes", set(re.findall(r"#include <([^>]+)>", integrated.source_text)) == {"stdint.h", "stddef.h"})
    check("emitter-deterministic", integrated.source_text == emit_fixture(HostEmitterConfig(semantics=host_call_rules(), entry_function="fn_1000", runtime_abi=rt.RuntimeAbiConfig(services=service_table()))).source_text)

    # Undeclared service fails closed.
    undeclared = rt.RuntimeAbiConfig(services=rt.RuntimeServiceTable([rt.RuntimeService("other.service", 2)], {"other.service": lambda a: 0}))
    expect_fail(
        "emitter-undeclared-service",
        lambda: emit_fixture(HostEmitterConfig(semantics=host_call_rules(), entry_function="fn_1000", runtime_abi=undeclared)),
        HostEmitterError,
    )
    # No runtime ABI configured: the P2-07 boundary must be preserved.
    expect_fail(
        "emitter-host-call-without-runtime-abi",
        lambda: emit_fixture(HostEmitterConfig(semantics=host_call_rules(), entry_function="fn_1000")),
        HostEmitterError,
    )
    default_units = program([I(0x1000, "li", fields={"rd": 1, "imm": 5}), I(0x1001, "ret", flow=RETURN)], [0x1000])
    default_rules = HostSemantics([HostInstructionSemantics(ARCH, "li", NORMAL, operations=()), HostInstructionSemantics(ARCH, "ret", RETURN, operations=())])
    default_emission = emit_host_translation(
        default_units,
        classify_indirect_control_flow(default_units),
        config=HostEmitterConfig(semantics=default_rules, entry_function="fn_1000"),
    )
    check("emitter-default-no-runtime-surface", "or_rt_" not in default_emission.source_text)
    check("emitter-default-includes-unchanged", set(re.findall(r"#include <([^>]+)>", default_emission.source_text)) == {"stdint.h", "stddef.h"})
    check("emitter-abi-opt-in-only", "or_rt_host_call" in integrated.source_text and "or_rt_host_call" not in default_emission.source_text)

    # Host call on an indirect site that is not explicitly external fails closed.
    bounded_units = host_call_program()
    expect_fail(
        "emitter-host-call-non-external",
        lambda: emit_host_translation(
            bounded_units,
            host_call_classification(bounded_units, status=BOUNDED, basis=BOUNDED_EV, targets=(0x1003,), mechanism=None),
            config=HostEmitterConfig(semantics=host_call_rules(), entry_function="fn_1000", runtime_abi=abi_config),
        ),
        HostEmitterError,
    )
    expect_fail("emitter-host-call-model-requires-source-or-call", lambda: HostInstructionSemantics(ARCH, "x", INDIRECT_CALL), HostEmitterError)
    expect_fail("emitter-host-call-bad-service", lambda: HostCallOperation(""), HostEmitterError)
    expect_fail("emitter-host-call-config-type", lambda: HostEmitterConfig(semantics=host_call_rules(), entry_function="fn_1000", runtime_abi="nope"), HostEmitterError)

    # Integration is bounded: runtime_abi alone does not broaden guest semantics.
    unknown_op_units = program([I(0x1000, "mystery"), I(0x1001, "ret", flow=RETURN)], [0x1000])
    expect_fail(
        "emitter-runtime-abi-does-not-broaden-semantics",
        lambda: emit_host_translation(
            unknown_op_units,
            classify_indirect_control_flow(unknown_op_units),
            config=HostEmitterConfig(semantics=host_call_rules(), entry_function="fn_1000", runtime_abi=abi_config),
        ),
        HostEmitterError,
    )

    # K. optional native compile + execute ----------------------------------
    compiler = find_compiler()
    compile_result = None
    if compiler is None:
        print("SKIP: native-runtime-abi-compile (no clang/gcc/cc on PATH)")
    else:
        compile_result = compile_and_run(integrated.source_text, "42 0")
        if compile_result is None:
            print("SKIP: native-runtime-abi-compile (detected compiler not runnable)")
        elif compile_result["status"] == "ok" and compile_result.get("match"):
            check("compiled-runtime-abi-fixture", True)
        elif compile_result["status"] == "ok":
            check("compiled-runtime-abi-fixture", False)
        else:
            raise AssertionError(f"native compile/run failed: {compile_result}")

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    if args.json:
        record = {
            "stage": "P2-08",
            "marker": f"OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "runtime_abi_version": rt.RUNTIME_ABI_VERSION,
            "runtime_abi_name": rt.RUNTIME_ABI_NAME,
            "failure_codes": list(rt.RUNTIME_FAILURE_CODES),
            "results": sorted(RESULTS, key=lambda item: item["check"]),
            "native_compiler": compiler,
            "native_compile_result": compile_result,
            "sample_fingerprints": {
                "state_scenario": run_one.fingerprint(),
                "input": canonical.fingerprint(),
                "frame": frame.fingerprint(),
                "audio": audio.fingerprint(),
                "abi_config": abi_config.fingerprint(),
                "integrated_source": integrated.fingerprint(),
                "default_source": default_emission.fingerprint(),
            },
        }
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_GENERIC_RUNTIME_ABI_V1_JSON={out.name}")

    print(f"OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
