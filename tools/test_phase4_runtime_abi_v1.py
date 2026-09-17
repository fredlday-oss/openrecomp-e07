#!/usr/bin/env python3
"""OpenRecomp Phase-4 generic runtime ABI gate (P4-01).

Proves the generated-code <-> runtime ABI V1 contract defined in
``.openrecomp-phase4/src/p4_runtime_abi_v1.py``:

* the contract is architecture-neutral, versioned and derived from the frozen
  P2-08 generic runtime ABI (name, version, failure codes, widths, and the
  canonical sorted service numeric ids);
* the contract covers execution state, calls, returns/exits, faults, memory
  service boundaries, host/runtime services and deterministic observable
  state, with bounded C types and no fixture-specific shortcuts;
* the emitted contract document, C header and instance profile are
  byte-deterministic and equal to the on-disk artifacts;
* the frozen Phase-3 generated instance (``coremark_program.c`` +
  ``coremark_support.c``, sha256-pinned) is a compliant instance of the
  contract and its declared profile: every extern, accessor, service macro and
  failure code matches, includes are bounded and no foreign host symbol is
  referenced;
* the fail-closed reference model implements the contract semantics with
  deterministic observable state, first-failure latching and explicit
  termination;
* negative sources (undeclared extern, undeclared service macro, foreign
  include, changed signature, fixture names in the core surface) are rejected.

It emits::

    OPENRECOMP_P4_01=PASS
    OPENRECOMP_PHASE4_RUNTIME_ABI_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_runtime_abi_v1.py
    python tools/test_phase4_runtime_abi_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-01
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(ROOT / ".openrecomp-phase4" / "src")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import p4_runtime_abi_v1 as abi  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402
from openrecomp.program_model import canonical_json  # noqa: E402

STAGE = "P4-01"
STAGE_MARKER = "OPENRECOMP_P4_01"
FEATURE_MARKER = "OPENRECOMP_PHASE4_RUNTIME_ABI_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

SOURCE_SUMS = "SOURCE_SHA256SUMS.txt"
SOURCE_SUMS_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
SOURCE_SUMS_ENTRIES = 134
P3_SUMS = ".openrecomp-phase3/SOURCE_SHA256SUMS.txt"
P3_SUMS_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_SUMS_ENTRIES = 24
P4_SUMS = ".openrecomp-phase4/SOURCE_SHA256SUMS.txt"

PROGRAM_PATH = ".openrecomp-phase3/evidence/P3-07/coremark_program.c"
PROGRAM_SHA256 = "5199e2f0a11974847966bd7ea6b855e0147c6e762d002ede3f14bc3ee8d9649a"
SUPPORT_PATH = ".openrecomp-phase3/evidence/P3-07/coremark_support.c"
SUPPORT_SHA256 = "c5c69054cbbcd4e6ea9259f2e3d80e4bfada6fc12fec1cfe3fe9224b9f861580"

EXPECTED_RUNTIME_SIGNATURES = {
    "or_rt_memory_read":
        "int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value)",
    "or_rt_memory_write":
        "int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value)",
    "or_rt_host_call":
        "int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)",
    "or_rt_failure_reason":
        "const char *or_rt_failure_reason(int code)",
}
EXPECTED_GENERATED_SIGNATURES = {
    "openrecomp_run": "void openrecomp_run(void)",
    "openrecomp_failed": "int openrecomp_failed(void)",
    "openrecomp_error": "const char *openrecomp_error(void)",
    "openrecomp_steps": "uint64_t openrecomp_steps(void)",
    "openrecomp_pc": "uint32_t openrecomp_pc(void)",
    "openrecomp_register_count": "size_t openrecomp_register_count(void)",
    "openrecomp_register_value": "uint32_t openrecomp_register_value(size_t index)",
    "openrecomp_image": "const uint8_t *openrecomp_image(void)",
    "openrecomp_image_size": "uint32_t openrecomp_image_size(void)",
    "openrecomp_region_count": "uint32_t openrecomp_region_count(void)",
    "openrecomp_region":
        "void openrecomp_region(uint32_t index, uint32_t *start, uint32_t *end, uint32_t *flags)",
}
FORBIDDEN_CORE_TOKENS = (
    "coremark", "mips", "ps1", "ps2", "psp", "n64", "p3_", "p3.", "r5900",
    "uart", "ee_", "emotion",
)
NONDETERMINISM_TOKENS = (
    "import time", "import random", "import secrets", "import os",
    "import uuid", "import datetime", "import subprocess", "time.time(",
    "random.", "os.environ", "uuid.uuid4", "datetime.now",
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def expect_fail(label: str, thunk, error_type=abi.P4AbiError) -> None:
    try:
        thunk()
    except error_type:
        check(f"reject:{label}", True)
        return
    except Exception as exc:  # noqa: BLE001 - fail closed
        raise AssertionError(
            f"{label}: raised {type(exc).__name__} instead of {error_type.__name__}") from exc
    raise AssertionError(f"{label}: accepted")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def render_signature(function: abi.ParsedFunction) -> str:
    params = ", ".join(
        (c_type + name) if c_type.endswith("*") else f"{c_type} {name}"
        for c_type, name in function.params) or "void"
    prefix = function.returns if function.returns.endswith("*") else function.returns + " "
    return f"{prefix}{function.name}({params})"


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def parse_manifest(path: pathlib.Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in read_text(path).strip().splitlines():
        if not line.strip():
            continue
        match = re.match(r"^([0-9a-f]{64}) \*(.+)$", line)
        if match is None:
            raise AssertionError(f"malformed manifest line: {line[:80]}")
        entries.append((match.group(1), match.group(2)))
    return entries


# ---------------------------------------------------------------------------
# Source integrity
# ---------------------------------------------------------------------------
def audit_source_integrity() -> None:
    check("source:root-manifest", sha256_file(ROOT / SOURCE_SUMS) == SOURCE_SUMS_SHA256)
    root_entries = parse_manifest(ROOT / SOURCE_SUMS)
    check("source:root-manifest-entries", len(root_entries) == SOURCE_SUMS_ENTRIES)
    bad = [rel for digest, rel in root_entries
           if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
    check("source:root-manifest-verified", not bad)
    check("source:phase3-manifest", sha256_file(ROOT / P3_SUMS) == P3_SUMS_SHA256)
    phase3_entries = parse_manifest(ROOT / P3_SUMS)
    check("source:phase3-manifest-entries", len(phase3_entries) == P3_SUMS_ENTRIES)
    check("source:phase4-manifest-exists", (ROOT / P4_SUMS).is_file())
    phase4_entries = parse_manifest(ROOT / P4_SUMS)
    bad4 = [rel for digest, rel in phase4_entries
            if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
    check("source:phase4-manifest-verified", phase4_entries and not bad4)
    FINDINGS["source_integrity"] = {
        "root_entries": len(root_entries),
        "phase3_entries": len(phase3_entries),
        "phase4_entries": len(phase4_entries),
    }


# ---------------------------------------------------------------------------
# Contract structure
# ---------------------------------------------------------------------------
def audit_contract() -> None:
    contract = abi.build_contract()
    profile = abi.frozen_phase3_profile()
    check("contract:name", contract.name == "openrecomp-generated-runtime-abi")
    check("contract:version-matches-p2-08", contract.version == rt.RUNTIME_ABI_VERSION)
    check("contract:runtime-abi-name",
          contract.to_document()["runtime_abi"]["name"] == rt.RUNTIME_ABI_NAME)
    check("contract:failure-codes-equal-p2-08",
          contract.failure_codes == rt.RUNTIME_FAILURE_CODES)
    check("contract:failure-code-values",
          [entry["value"] for entry in contract.to_document()["failure_codes"]]
          == list(range(1, len(rt.RUNTIME_FAILURE_CODES) + 1)))
    check("contract:widths-equal-p2-08",
          frozenset(contract.widths) == rt.RUNTIME_WIDTHS)
    check("contract:endianness-equal-p2-08",
          frozenset(contract.endianness) == rt.RUNTIME_ENDIANNESS)
    check("contract:max-address",
          contract.to_document()["memory"]["max_address"] == rt.RUNTIME_MAX_ADDRESS)
    check("contract:no-host-pointers",
          contract.to_document()["memory"]["host_pointers_exposed"] is False)

    runtime_symbols = contract.runtime_symbols()
    generated_symbols = contract.generated_symbols()
    check("contract:runtime-symbol-set",
          set(runtime_symbols) == set(EXPECTED_RUNTIME_SIGNATURES))
    check("contract:generated-symbol-set",
          set(generated_symbols) == set(EXPECTED_GENERATED_SIGNATURES))
    for name, signature in sorted(EXPECTED_RUNTIME_SIGNATURES.items()):
        check(f"contract:signature:{name}", runtime_symbols[name].signature() == signature)
    for name, signature in sorted(EXPECTED_GENERATED_SIGNATURES.items()):
        check(f"contract:signature:{name}", generated_symbols[name].signature() == signature)
    check("contract:types-bounded",
          all(parameter.c_type in abi.C_TYPES
              for symbol in contract.symbols for parameter in symbol.params))
    check("contract:return-types-bounded",
          all(symbol.returns in abi.C_TYPES for symbol in contract.symbols))
    check("contract:core-service-set",
          [service.service_id for service in contract.core_services] == ["or.runtime.exit"])
    exit_service = contract.core_service("or.runtime.exit")
    check("contract:core-exit-terminates", exit_service.terminates_run)
    check("contract:core-exit-typed", exit_service.arg_types == ("u32",)
          and exit_service.result_type is None)
    check("contract:core-exit-version", exit_service.version == rt.RUNTIME_ABI_VERSION)
    check("contract:entry-return-policy", contract.entry_return_policy == "fault")
    check("contract:observable-fields",
          tuple(contract.observable_fields) == abi.OBSERVABLE_FIELDS)
    check("contract:observable-digest", contract.observable_digest == "fnv1a-64")

    check("profile:valid", contract.verify_profile(profile) == [])
    check("profile:name", profile.name == "phase3-coremark-mips32-o32")
    check("profile:widths-subset", set(profile.widths) < set(contract.widths))
    check("profile:widths-exact", tuple(profile.widths) == (8, 16, 32))
    check("profile:endianness", profile.endianness == "little")
    check("profile:register-count", profile.register_count == 32)
    check("profile:aux-registers",
          tuple(profile.aux_registers)
          == (("hi", "openrecomp_hi", "uint32_t"), ("lo", "openrecomp_lo", "uint32_t")))
    check("profile:service-macros",
          [(service.service_id, service.macro, service.numeric_id)
           for service in profile.services]
          == [("p3.exit", "OR_RT_SERVICE_P3_EXIT", 1),
              ("p3.uart_write", "OR_RT_SERVICE_P3_UART_WRITE", 2)])
    table = rt.RuntimeServiceTable(
        [rt.RuntimeService(service.service_id, len(service.arg_types))
         for service in profile.services],
        {service.service_id: (lambda _args: None) for service in profile.services})
    check("profile:macro-matches-p2-08-canonical",
          all(service.macro == table.macro(service.service_id) for service in profile.services))
    check("profile:numeric-matches-p2-08-canonical",
          all(service.numeric_id == table.numeric_id(service.service_id)
              for service in profile.services))
    check("profile:terminating-service",
          [service.service_id for service in profile.services if service.terminates_run]
          == ["p3.exit"])
    check("profile:artifacts",
          dict(profile.artifacts) == {PROGRAM_PATH: PROGRAM_SHA256,
                                      SUPPORT_PATH: SUPPORT_SHA256})

    expect_fail("core-service-fixture-namespace", lambda: abi.CoreService(
        "p3.exit", rt.RUNTIME_ABI_VERSION, ("u32",), None, True, "x"))
    expect_fail("core-service-unbounded-type", lambda: abi.CoreService(
        "or.runtime.bad", rt.RUNTIME_ABI_VERSION, ("w32",), None, False, "x"))
    expect_fail("core-service-incompatible-version", lambda: abi.CoreService(
        "or.runtime.bad", "9.0.0", (), None, False, "x"))
    expect_fail("symbol-unbounded-type", lambda: abi.AbiSymbol(
        "or_rt_bad", "int", (abi.AbiParam("x", "double"),), abi.RUNTIME_PROVIDES, "x"))
    expect_fail("symbol-wrong-namespace", lambda: abi.AbiSymbol(
        "host_bad", "int", (), abi.RUNTIME_PROVIDES, "x"))
    expect_fail("profile-unknown-width", lambda: abi.InstanceProfile(
        "x", rt.RUNTIME_ABI_VERSION, "little", (12,), 1, (), (), "fault", ()))
    expect_fail("profile-v1-service-version", lambda: abi.InstanceProfile(
        "x", rt.RUNTIME_ABI_VERSION, "little", (8,), 1, (),
        (abi.ServiceDescriptor("a.b", 1, "9.0.0", (), None, False, "x"),), "fault", ()))
    FINDINGS["contract"] = {
        "name": contract.name,
        "version": contract.version,
        "runtime_symbols": sorted(runtime_symbols),
        "generated_symbols": sorted(generated_symbols),
        "core_services": [service.service_id for service in contract.core_services],
        "profile": profile.name,
    }


# ---------------------------------------------------------------------------
# Artifact determinism
# ---------------------------------------------------------------------------
def audit_artifacts() -> None:
    document = abi.contract_document_bytes()
    header = abi.contract_header_bytes()
    profile = abi.profile_document_bytes()
    check("artifact:contract-json-identical",
          (ROOT / abi.CONTRACT_DOCUMENT_PATH).read_bytes() == document)
    check("artifact:header-identical",
          (ROOT / abi.CONTRACT_HEADER_PATH).read_bytes() == header)
    check("artifact:profile-identical",
          (ROOT / abi.PROFILE_DOCUMENT_PATH).read_bytes() == profile)
    check("artifact:contract-json-roundtrip",
          json.loads(document.decode("utf-8")) == abi.build_contract().to_document())
    check("artifact:two-emissions-identical",
          abi.contract_document_bytes() == document
          and abi.contract_header_bytes() == header
          and abi.profile_document_bytes() == profile)
    check("artifact:header-has-version", b"abi_version: " + abi.CONTRACT_VERSION.encode() in header)
    check("artifact:header-has-guard", b"#ifndef OPENRECOMP_GENERATED_RUNTIME_ABI_V1_H" in header)
    FINDINGS["artifacts"] = {
        "contract_json_sha256": sha256_bytes(document),
        "header_sha256": sha256_bytes(header),
        "profile_sha256": sha256_bytes(profile),
    }


# ---------------------------------------------------------------------------
# Frozen Phase-3 instance compliance
# ---------------------------------------------------------------------------
def audit_frozen_instance() -> None:
    check("instance:program-sha256", sha256_file(ROOT / PROGRAM_PATH) == PROGRAM_SHA256)
    check("instance:support-sha256", sha256_file(ROOT / SUPPORT_PATH) == SUPPORT_SHA256)
    contract = abi.build_contract()
    profile = abi.frozen_phase3_profile()
    verifier = abi.GeneratedSourceVerifier(contract, profile)
    check("instance:profile-artifacts", verifier.check_profile_artifacts(ROOT) == [])

    program_text = read_text(ROOT / PROGRAM_PATH)
    support_text = read_text(ROOT / SUPPORT_PATH)
    program_problems = verifier.verify_program(program_text)
    support_problems = verifier.verify_runtime_support(support_text)
    check("instance:program-compliant", program_problems == [])
    check("instance:support-compliant", support_problems == [])

    program = abi.parse_source(program_text)
    check("instance:program-includes",
          program.includes == frozenset({"stdint.h", "stddef.h"}))
    externs = {function.name: function for function in program.externs}
    check("instance:extern-set", set(externs) == set(EXPECTED_RUNTIME_SIGNATURES))
    check("instance:extern-signatures",
          all(render_signature(function) == EXPECTED_RUNTIME_SIGNATURES[function.name]
              for function in program.externs))
    check("instance:service-macros",
          dict(program.service_macros)
          == {"OR_RT_SERVICE_P3_EXIT": 1, "OR_RT_SERVICE_P3_UART_WRITE": 2})
    check("instance:service-uses",
          dict(program.service_uses)
          == {"OR_RT_SERVICE_P3_UART_WRITE": 1, "OR_RT_SERVICE_P3_EXIT": 1})
    failure_enum = dict(program.failure_enum)
    check("instance:failure-enum-ok", failure_enum.pop("OK", None) == 0)
    check("instance:failure-enum-codes",
          failure_enum == {code: index + 1 for index, code in enumerate(rt.RUNTIME_FAILURE_CODES)})
    defined = {function.name: function for function in program.definitions if not function.static}
    check("instance:accessors-defined",
          all(name in defined for name in EXPECTED_GENERATED_SIGNATURES))
    check("instance:aux-accessors-defined",
          "openrecomp_hi" in defined and "openrecomp_lo" in defined
          and defined["openrecomp_hi"].returns == "uint32_t"
          and defined["openrecomp_lo"].returns == "uint32_t")

    support = abi.parse_source(support_text)
    support_defined = {function.name: function for function in support.definitions
                       if not function.static}
    check("instance:support-defines-runtime-entries",
          all(name in support_defined for name in EXPECTED_RUNTIME_SIGNATURES))
    check("instance:support-defines-no-accessors",
          not any(name in support_defined for name in EXPECTED_GENERATED_SIGNATURES))
    check("instance:support-defines-main", "main" in support_defined)
    check("instance:support-unknown-service-fallback",
          "OR_RT_UNKNOWN_HOST_SERVICE" in support_text)

    # Negative sources: the verifier must reject them (fail closed).
    check("negative:extra-extern",
          verifier.verify_program(program_text.replace(
              "extern int or_rt_memory_read",
              "extern int system(const char *command);\nextern int or_rt_memory_read", 1)) != [])
    check("negative:undeclared-macro",
          verifier.verify_program(program_text.replace(
              "or_host_service(OR_RT_SERVICE_P3_UART_WRITE, 1u",
              "or_host_service(OR_RT_SERVICE_HOST_FS, 1u", 1)) != [])
    check("negative:foreign-include",
          verifier.verify_program(program_text.replace(
              "#include <stdint.h>", "#include <windows.h>", 1)) != [])
    check("negative:changed-accessor-signature",
          verifier.verify_program(program_text.replace(
              "uint32_t openrecomp_pc(void)", "uint64_t openrecomp_pc(void)", 1)) != [])
    check("negative:missing-accessor",
          verifier.verify_program(program_text.replace(
              "int openrecomp_failed(void) { return (int)g_failed; }", "", 1)) != [])
    check("negative:support-foreign-include",
          verifier.verify_runtime_support(support_text.replace(
              "#include <stdio.h>", "#include <windows.h>", 1)) != [])
    check("negative:support-changed-signature",
          verifier.verify_runtime_support(support_text.replace(
              "int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value) {",
              "int or_rt_memory_read(uint32_t address, uint32_t width_bits, uint64_t *out_value) {",
              1)) != [])
    check("negative:support-missing-fallback",
          verifier.verify_runtime_support(support_text.replace(
              "OR_RT_UNKNOWN_HOST_SERVICE", "OR_RT_TRAP")) != [])
    FINDINGS["frozen_instance"] = {
        "program_sha256": PROGRAM_SHA256,
        "support_sha256": SUPPORT_SHA256,
        "program_problems": program_problems,
        "support_problems": support_problems,
    }


# ---------------------------------------------------------------------------
# Fail-closed model conformance
# ---------------------------------------------------------------------------
def fresh_model(**kwargs) -> abi.ContractRuntimeModel:
    contract = abi.build_contract()
    profile = abi.frozen_phase3_profile()
    handlers = {"p3.uart_write": kwargs.pop("uart_handler", lambda _args: None)}
    return abi.ContractRuntimeModel(
        contract, profile, memory_size_bytes=kwargs.pop("memory_size_bytes", 64),
        handlers=handlers, **kwargs)


def expect_model_failure(label: str, result, code: str) -> None:
    check(f"model:{label}",
          result.failure is not None and result.failure.code.value == code)


def audit_model() -> None:
    model = fresh_model()
    check("model:write-read-8", model.write(0, 0xAB, 8).ok and model.read(0, 8).value == 0xAB)
    check("model:write-read-16", model.write(2, 0x1234, 16).ok and model.read(2, 16).value == 0x1234)
    check("model:write-read-32", model.write(4, 0xDEADBEEF, 32).ok
          and model.read(4, 32).value == 0xDEADBEEF)
    check("model:little-endian-bytes", bytes([model.read(index, 8).value for index in range(4, 8)])
          == b"\xef\xbe\xad\xde")
    check("model:width-64-unsupported-by-profile",
          not model.read(0, 64).ok and model.failed)

    expect_model_failure("oob-read", fresh_model().read(64, 8), "MEMORY_OUT_OF_RANGE")
    expect_model_failure("oob-write", fresh_model().write(64, 1, 8), "MEMORY_OUT_OF_RANGE")
    expect_model_failure("address-overflow",
                         fresh_model().read(rt.RUNTIME_MAX_ADDRESS, 16), "MEMORY_ADDRESS_OVERFLOW")
    expect_model_failure("unknown-service",
                         fresh_model().call("p3.nope", ()), "UNKNOWN_HOST_SERVICE")
    expect_model_failure("arity",
                         fresh_model().call("p3.uart_write", ()), "HOST_CALL_ARITY")
    expect_model_failure("typed-argument-overflow",
                         fresh_model().call("p3.uart_write", (1 << 32,)), "HOST_CALL_ARITY")
    expect_model_failure("version-mismatch",
                         fresh_model().call("p3.uart_write", (1,), version="9.0.0"),
                         "ABI_VERSION_MISMATCH")
    expect_model_failure("handler-exception",
                         fresh_model(uart_handler=lambda _args: (_ for _ in ()).throw(RuntimeError("x")))
                         .call("p3.uart_write", (1,)),
                         "HOST_SERVICE_FAILED")

    terminated = fresh_model()
    check("model:exit-result", terminated.call("p3.exit", (7,)).ok)
    check("model:exit-status", terminated.exit_status == 7)
    check("model:terminated", terminated.terminated)
    expect_model_failure("operation-after-termination", terminated.read(0, 8), "TRAP")
    check("model:first-failure-preserved",
          terminated.failure.code is rt.RuntimeFailureCode.TRAP)

    latched = fresh_model()
    latched.read(64, 8)
    first = latched.failure.code
    latched.write(64, 1, 8)
    check("model:latch-stable", latched.failure.code is first)

    returned = fresh_model()
    failure = returned.entry_returned()
    check("model:entry-return-fault", failure.code is rt.RuntimeFailureCode.TRAP
          and returned.failed)

    output = fresh_model(output_capacity=2)
    check("model:output-accepted", output.emit_output(b"ab").ok)
    expect_model_failure("output-capacity", output.emit_output(b"c"), "UNSUPPORTED_OPERATION")

    def scenario(model: abi.ContractRuntimeModel) -> abi.ContractRuntimeModel:
        model.write(0, 0x1234, 32)
        model.registers[1] = 7
        model.aux["hi"] = 3
        model.pc = 0x1000
        model.steps = 12
        model.call("p3.uart_write", (0x41,))
        model.emit_output(b"Z")
        return model

    scenario_a = scenario(fresh_model())
    scenario_b = scenario(fresh_model())
    check("model:observable-digest-format",
          re.fullmatch(r"0x[0-9a-f]{16}", scenario_a.observable_digest()) is not None)
    check("model:observable-digest-deterministic",
          scenario_a.observable_digest() == scenario_b.observable_digest())
    check("model:observable-document-deterministic",
          canonical_json(scenario_a.observable_document())
          == canonical_json(scenario_b.observable_document()))
    baseline = scenario_a.observable_digest()
    check("model:baseline-active", not scenario_a.failed and not scenario_a.terminated)
    scenario_b.registers[1] = 8
    check("model:observable-sensitive-register", scenario_b.observable_digest() != baseline)
    scenario_b.registers[1] = 7
    scenario_b.pc = 0x1004
    check("model:observable-sensitive-pc", scenario_b.observable_digest() != baseline)
    scenario_b.pc = 0x1000
    scenario_b.steps = 13
    check("model:observable-sensitive-steps", scenario_b.observable_digest() != baseline)
    scenario_b.steps = 12
    check("model:observable-restored-identity", scenario_b.observable_digest() == baseline)
    scenario_c = scenario(fresh_model())
    scenario_c.write(0, 0x1235, 32)
    check("model:observable-sensitive-memory", scenario_c.observable_digest() != baseline)
    output_a = scenario(fresh_model())
    output_b = scenario(fresh_model())
    output_b.emit_output(b"Y")
    check("model:observable-sensitive-output", output_b.observable_digest() != output_a.observable_digest())
    exit_zero = fresh_model()
    exit_zero.call("p3.exit", (0,))
    exit_one = fresh_model()
    exit_one.call("p3.exit", (1,))
    check("model:observable-sensitive-exit",
          exit_zero.observable_digest() != exit_one.observable_digest())
    check("model:observable-document-failure",
          "failure" in output_a.observable_document()
          and output_a.observable_document()["failure"] is None)
    FINDINGS["model"] = {
        "digest": baseline,
        "document_fields": sorted(scenario_a.observable_document()),
    }


# ---------------------------------------------------------------------------
# Architecture neutrality
# ---------------------------------------------------------------------------
def audit_neutrality() -> None:
    module_path = ROOT / ".openrecomp-phase4" / "src" / "p4_runtime_abi_v1.py"
    module_source = read_text(module_path)
    for token in NONDETERMINISM_TOKENS:
        check(f"neutrality:no-nondeterminism:{token}", token not in module_source)

    contract = abi.build_contract()
    surface = canonical_json(contract.to_document()) + contract.to_c_header()
    lowered = surface.lower()
    for token in FORBIDDEN_CORE_TOKENS:
        check(f"neutrality:core-surface-clean:{token}", token not in lowered)
    profile_document = canonical_json(abi.frozen_phase3_profile().to_document())
    check("neutrality:fixture-declared-in-profile",
          "p3.uart_write" in profile_document)
    check("neutrality:core-namespace-reserved",
          abi.CORE_SERVICE_NAMESPACE == "or.runtime.")
    check("neutrality:platform-tokens-declared",
          "fopen" in abi.PLATFORM_TOKENS and "vulkan" in abi.PLATFORM_TOKENS)
    check("neutrality:generated-include-set",
          abi.GENERATED_INCLUDE_SET == frozenset({"stdint.h", "stddef.h"}))
    FINDINGS["neutrality"] = {"forbidden_tokens": list(FORBIDDEN_CORE_TOKENS)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P4-01 generic runtime ABI gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-01")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}

    print("=== P4-01 Generic Runtime ABI Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("contract")
        audit_contract()
        banner("artifacts")
        audit_artifacts()
        banner("frozen_instance")
        audit_frozen_instance()
        banner("model")
        audit_model()
        banner("neutrality")
        audit_neutrality()
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    status = "FAIL" if failure else "PASS"

    result = {
        "stage": STAGE,
        "stage_name": FEATURE_MARKER,
        "status": status,
        "tests": passed,
        "passed": passed,
        "failed": failed,
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={passed}",
            "terminal": f"{TERMINAL_MARKER}=NOT_PROVEN",
            "compatibility": f"{COMPAT_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    (EVIDENCE_DIR / "p4_01_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    print("\n=== RESULT ===")
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{TERMINAL_MARKER}=NOT_PROVEN")
        print(f"{COMPAT_MARKER}=NOT_PROVEN")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FEATURE_MARKER}=FAIL")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
