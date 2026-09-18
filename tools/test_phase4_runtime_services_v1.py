#!/usr/bin/env python3
"""OpenRecomp Phase-4 runtime service mediation gate (P4-03).

Proves that fixture-specific external handling is replaced by explicit typed
and versioned runtime service interfaces in
``.openrecomp-phase4/src/p4_runtime_services_v1.py``:

* a bounded architecture-neutral interface catalog (``or.runtime.exit``,
  ``or.runtime.stream_write``) with declared argument/result types, versions,
  termination behaviour and descriptions;
* declarative aliases that map an instance's raw service ids onto interfaces
  with bound arguments (fixture handling is data, not code);
* a fail-closed mediator: unknown services, version mismatches, arity/type
  violations, missing handlers and handler failures return stable P2-08
  failure codes; the first failure is latched and later calls fail closed;
* an ``or_rt_host_call`` bridge that exposes only the numeric services of a
  declared profile and nothing else (no ambient host capability);
* frozen-instance replay equivalence: the exact Phase-3 external interaction
  (499 output bytes plus the terminating exit status 0, taken from the frozen
  P3-08 native execution evidence) is reproduced byte-for-byte through the
  generic mediator, and without the declared aliases the same calls fail
  closed.

It emits::

    OPENRECOMP_P4_03=PASS
    OPENRECOMP_PHASE4_RUNTIME_SERVICES_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_runtime_services_v1.py
    python tools/test_phase4_runtime_services_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-03
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

import p4_guest_memory_v1 as gm  # noqa: E402
import p4_runtime_abi_v1 as abi  # noqa: E402
import p4_runtime_services_v1 as svc  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402
from openrecomp.program_model import canonical_json  # noqa: E402

STAGE = "P4-03"
STAGE_MARKER = "OPENRECOMP_P4_03"
FEATURE_MARKER = "OPENRECOMP_PHASE4_RUNTIME_SERVICES_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

SOURCE_SUMS = "SOURCE_SHA256SUMS.txt"
SOURCE_SUMS_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
SOURCE_SUMS_ENTRIES = 134
P3_SUMS = ".openrecomp-phase3/SOURCE_SHA256SUMS.txt"
P3_SUMS_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_SUMS_ENTRIES = 24
P4_SUMS = ".openrecomp-phase4/SOURCE_SHA256SUMS.txt"

P3_08_EXECUTION = ".openrecomp-phase3/evidence/P3-08/native_execution.json"

FROZEN_OUTPUT_BYTES = 499
FROZEN_EXIT_STATUS = 0
STATUS = {code: index + 1 for index, code in enumerate(rt.RUNTIME_FAILURE_CODES)}
STATUS[None] = 0

FORBIDDEN_CORE_TOKENS = (
    "coremark", "mips", "ps1", "ps2", "psp", "n64", "p3", "uart", "r5900",
)
AMBIENT_CAPABILITY_TOKENS = (
    "import os", "import subprocess", "import socket", "import urllib",
    "import time", "import random", "import uuid", "open(", "os.environ",
    "os.getpid", "socket.", "requests.", "urllib.",
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


def expect_fail(label: str, thunk, error_type=svc.ServiceMediationError) -> None:
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


def fresh_mediator(**kwargs):
    return svc.frozen_mediator(**kwargs)


# ---------------------------------------------------------------------------
# Source integrity
# ---------------------------------------------------------------------------
def audit_source_integrity() -> None:
    check("source:root-manifest", sha256_file(ROOT / SOURCE_SUMS) == SOURCE_SUMS_SHA256)
    root_entries = parse_manifest(ROOT / SOURCE_SUMS)
    check("source:root-manifest-entries", len(root_entries) == SOURCE_SUMS_ENTRIES)
    check("source:root-manifest-verified",
          all((ROOT / rel).is_file() and sha256_file(ROOT / rel) == digest
              for digest, rel in root_entries))
    check("source:phase3-manifest", sha256_file(ROOT / P3_SUMS) == P3_SUMS_SHA256)
    phase3_entries = parse_manifest(ROOT / P3_SUMS)
    check("source:phase3-manifest-entries", len(phase3_entries) == P3_SUMS_ENTRIES)
    phase4_entries = parse_manifest(ROOT / P4_SUMS)
    bad = [rel for digest, rel in phase4_entries
           if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
    check("source:phase4-manifest-verified", phase4_entries and not bad)
    FINDINGS["source_integrity"] = {
        "root_entries": len(root_entries),
        "phase3_entries": len(phase3_entries),
        "phase4_entries": len(phase4_entries),
    }


# ---------------------------------------------------------------------------
# Interface catalog and registry
# ---------------------------------------------------------------------------
def audit_interfaces() -> None:
    interfaces = svc.standard_interfaces()
    check("interfaces:catalog",
          [(item.service_id, item.version, item.arg_types, item.result_type,
            item.terminates_run)
           for item in interfaces]
          == [("or.runtime.exit", rt.RUNTIME_ABI_VERSION, ("u32",), None, True),
              ("or.runtime.stream_write", rt.RUNTIME_ABI_VERSION,
               ("u32", "u32"), None, False)])
    check("interfaces:core-namespace",
          all(item.service_id.startswith(svc.CORE_NAMESPACE) for item in interfaces))
    check("interfaces:typed",
          all(set(item.arg_types) <= set(svc.SUPPORTED_ARG_TYPES) for item in interfaces))
    check("interfaces:terminating-exactly-one",
          [item.service_id for item in interfaces if item.terminates_run]
          == [svc.EXIT_INTERFACE])
    check("interfaces:version-abi", all(item.version == rt.RUNTIME_ABI_VERSION
                                        for item in interfaces))
    check("interfaces:arg-count", all(item.arg_count == len(item.arg_types)
                                      for item in interfaces))
    expect_fail("interface-outside-namespace", lambda: svc.RuntimeServiceInterface(
        "p3.exit", rt.RUNTIME_ABI_VERSION, ("u32",), None, True, "x"))
    expect_fail("interface-unbounded-type", lambda: svc.RuntimeServiceInterface(
        "or.runtime.bad", rt.RUNTIME_ABI_VERSION, ("bytes",), None, False, "x"))
    expect_fail("interface-incompatible-version", lambda: svc.RuntimeServiceInterface(
        "or.runtime.bad", "9.0.0", (), None, False, "x"))
    expect_fail("interface-empty-description", lambda: svc.RuntimeServiceInterface(
        "or.runtime.bad", rt.RUNTIME_ABI_VERSION, (), None, False, ""))

    registry = svc.standard_registry()
    check("registry:ids", registry.service_ids
          == ("or.runtime.exit", "or.runtime.stream_write"))
    check("registry:resolve", registry.interface("or.runtime.exit")
          .service_id == "or.runtime.exit")
    check("registry:resolve-version-ok",
          registry.interface("or.runtime.exit", rt.RUNTIME_ABI_VERSION).terminates_run)
    expect_fail("registry-unknown", lambda: registry.interface("or.runtime.none"))
    version_code = None
    try:
        registry.interface("or.runtime.exit", "9.0.0")
    except svc.ServiceMediationError as exc:
        version_code = exc.failure.code.value
    check("registry-version-mismatch", version_code == "ABI_VERSION_MISMATCH")
    expect_fail("registry-duplicate", lambda: svc.ServiceRegistry((
        svc.RuntimeServiceInterface("or.runtime.a", rt.RUNTIME_ABI_VERSION, (), None, False, "x"),
        svc.RuntimeServiceInterface("or.runtime.a", rt.RUNTIME_ABI_VERSION, (), None, False, "y"))))
    expect_fail("registry-empty", lambda: svc.ServiceRegistry(()))
    expect_fail("registry-bad-entry", lambda: svc.ServiceRegistry(("nope",)))
    check("registry:document-roundtrip",
          json.loads(canonical_json(registry.to_document())) == registry.to_document())
    check("registry:fingerprint-stable",
          registry.fingerprint() == svc.standard_registry().fingerprint())
    neutral = canonical_json(registry.to_document()).lower()
    check("registry:no-fixture-tokens",
          not any(token in neutral for token in FORBIDDEN_CORE_TOKENS))
    FINDINGS["interfaces"] = {
        "catalog": [item.service_id for item in interfaces],
        "registry_fingerprint": registry.fingerprint(),
    }


# ---------------------------------------------------------------------------
# Mediator semantics
# ---------------------------------------------------------------------------
def audit_mediator() -> None:
    profile = abi.frozen_phase3_profile()
    check("aliases:declared",
          [(alias.source_service_id, alias.target_service_id, alias.bound_args)
           for alias in svc.aliases_for_profile(profile)]
          == [("p3.exit", "or.runtime.exit", ()),
              ("p3.uart_write", "or.runtime.stream_write", (0,))])
    check("aliases:version",
          all(alias.source_version == rt.RUNTIME_ABI_VERSION
              and alias.target_version == rt.RUNTIME_ABI_VERSION
              for alias in svc.aliases_for_profile(profile)))
    expect_fail("alias-bad-source-id", lambda: svc.ServiceAlias(
        "1bad", rt.RUNTIME_ABI_VERSION, "or.runtime.exit", rt.RUNTIME_ABI_VERSION, (), "x"))
    expect_fail("alias-negative-bound-arg", lambda: svc.ServiceAlias(
        "x.y", rt.RUNTIME_ABI_VERSION, "or.runtime.stream_write",
        rt.RUNTIME_ABI_VERSION, (-1,), "x"))
    expect_fail("mediator-alias-to-unknown",
                lambda: svc.RuntimeServiceMediator(
                    svc.standard_registry(),
                    aliases=(svc.ServiceAlias("x.y", rt.RUNTIME_ABI_VERSION,
                                              "or.runtime.none", rt.RUNTIME_ABI_VERSION,
                                              (), "x"),)))
    expect_fail("mediator-duplicate-alias", lambda: svc.RuntimeServiceMediator(
        svc.standard_registry(),
        aliases=(svc.ServiceAlias("x.y", rt.RUNTIME_ABI_VERSION, "or.runtime.exit",
                                  rt.RUNTIME_ABI_VERSION, (), "x"),
                 svc.ServiceAlias("x.y", rt.RUNTIME_ABI_VERSION, "or.runtime.exit",
                                  rt.RUNTIME_ABI_VERSION, (), "x"))))
    expect_fail("mediator-terminating-handler", lambda: svc.RuntimeServiceMediator(
        svc.standard_registry(), handlers={svc.EXIT_INTERFACE: lambda _a: None}))

    mediator, sink = fresh_mediator()
    result = mediator.dispatch("p3.uart_write", (0x41,))
    check("mediate:stream-ok", result.ok and bytes(sink.data) == b"A")
    check("mediate:call-log",
          mediator.calls[0].to_document() == {
              "sequence": 0, "raw_service_id": "p3.uart_write",
              "interface_id": "or.runtime.stream_write",
              "version": rt.RUNTIME_ABI_VERSION,
              "raw_args": [0x41], "adapted_args": [0, 0x41], "ok": True,
              "failure_code": None})
    check("mediate:identity-service",
          svc.standard_registry().interface("or.runtime.stream_write").arg_count == 2)

    exit_result = mediator.dispatch("p3.exit", (7,))
    check("mediate:exit-ok", exit_result.ok)
    check("mediate:exit-status", mediator.exit_status == 7 and mediator.terminated)
    check("mediate:post-termination",
          mediator.dispatch("p3.exit", (8,)).failure.code is rt.RuntimeFailureCode.TRAP)
    check("mediate:post-termination-log", mediator.calls[-1].ok is False)

    for label, call, code in (
        ("unknown", lambda m: m.dispatch("p3.none", ()), "UNKNOWN_HOST_SERVICE"),
        ("version", lambda m: m.dispatch("p3.uart_write", (1,), version="9.0.0"),
         "ABI_VERSION_MISMATCH"),
        ("arity", lambda m: m.dispatch("p3.uart_write", ()), "HOST_CALL_ARITY"),
        ("typed-overflow", lambda m: m.dispatch("p3.uart_write", (1 << 32,)),
         "HOST_CALL_ARITY"),
        ("typed-negative", lambda m: m.dispatch("p3.uart_write", (-1,)),
         "HOST_CALL_ARITY"),
    ):
        fail = call(fresh_mediator()[0])
        check(f"mediate:{label}", fail.failure is not None
              and fail.failure.code.value == code)

    no_handler = svc.RuntimeServiceMediator(
        svc.standard_registry(), aliases=svc.aliases_for_profile(profile))
    fail = no_handler.dispatch("p3.uart_write", (0x41,))
    check("mediate:no-handler",
          fail.failure.code is rt.RuntimeFailureCode.UNSUPPORTED_OPERATION)
    raising = svc.RuntimeServiceMediator(
        svc.standard_registry(), aliases=svc.aliases_for_profile(profile),
        handlers={svc.STREAM_WRITE_INTERFACE:
                  lambda _args: (_ for _ in ()).throw(RuntimeError("boom"))})
    fail = raising.dispatch("p3.uart_write", (0x41,))
    check("mediate:handler-failure",
          fail.failure.code is rt.RuntimeFailureCode.HOST_SERVICE_FAILED)

    latched = fresh_mediator()[0]
    check("mediate:first-call-ok", latched.dispatch("p3.uart_write", (1,)).ok)
    check("mediate:first-failure", latched.dispatch("p3.none", ()).failure.code
          is rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE)
    later = latched.dispatch("p3.uart_write", (2,))
    check("mediate:latch-preserved",
          later.failure.code is rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE)
    check("mediate:latch-blocks-handler", len(latched.calls) == 2)

    no_alias = fresh_mediator(aliases=())[0]
    fail = no_alias.dispatch("p3.uart_write", (0x41,))
    check("mediate:no-alias-fails-closed",
          fail.failure.code is rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE)
    expect_fail("sink-wrong-stream", lambda: svc.BoundedOutputStream(0, 4)((1, 0x41)))
    expect_fail("sink-byte-overflow", lambda: svc.BoundedOutputStream(0, 4)((0, 0x100)))
    capacity_sink = svc.BoundedOutputStream(0, 1)
    capacity_sink((0, 1))
    expect_fail("sink-capacity", lambda: capacity_sink((0, 2)))
    FINDINGS["mediator"] = {
        "aliases": [alias.source_service_id for alias in mediator.aliases],
        "call_log_fingerprint": mediator.fingerprint(),
    }


# ---------------------------------------------------------------------------
# ABI host-call bridge
# ---------------------------------------------------------------------------
def audit_bridge() -> None:
    profile = abi.frozen_phase3_profile()
    def fresh_bridge() -> svc.AbiHostCallBridge:
        return svc.AbiHostCallBridge(fresh_mediator()[0], profile)

    check("bridge:ok-stream", fresh_bridge().host_call(2, 1, (0x42,)) == (0, None))
    check("bridge:ok-exit", fresh_bridge().host_call(1, 1, (0,)) == (0, None))
    check("bridge:unknown-numeric",
          fresh_bridge().host_call(99, 0, ()) == (STATUS["UNKNOWN_HOST_SERVICE"], None))
    check("bridge:arity",
          fresh_bridge().host_call(2, 2, (1, 2)) == (STATUS["HOST_CALL_ARITY"], None))
    check("bridge:typed", fresh_bridge().host_call(2, 1, (1 << 32,))
          == (STATUS["HOST_CALL_ARITY"], None))
    check("bridge:status-values",
          STATUS["UNKNOWN_HOST_SERVICE"] == 6 and STATUS["HOST_CALL_ARITY"] == 8
          and STATUS["ABI_VERSION_MISMATCH"] == 12 and STATUS["HOST_SERVICE_FAILED"] == 7
          and STATUS["UNSUPPORTED_OPERATION"] == 13 and STATUS["TRAP"] == 14)
    expect_fail("bridge-no-mediator", lambda: svc.AbiHostCallBridge("nope", profile))
    expect_fail("bridge-no-profile-services",
                lambda: svc.AbiHostCallBridge(fresh_mediator()[0], object()))
    unmapped = svc.RuntimeServiceMediator(svc.standard_registry(), aliases=())
    expect_fail("bridge-unmapped-profile-service",
                lambda: svc.AbiHostCallBridge(unmapped, profile))
    expect_fail("bridge-missing-codes", lambda: svc.AbiHostCallBridge(
        fresh_mediator()[0], profile, failure_codes=("TRAP",)))
    FINDINGS["bridge"] = {"status_codes": {code: value for code, value in STATUS.items() if code}}


# ---------------------------------------------------------------------------
# Frozen fixture replacement and replay equivalence
# ---------------------------------------------------------------------------
def audit_fixture_replacement() -> None:
    execution = json.loads(read_text(ROOT / P3_08_EXECUTION))
    uart = bytes.fromhex(execution["observable"]["uart_hex"])
    check("replay:frozen-stream-length", len(uart) == FROZEN_OUTPUT_BYTES)
    check("replay:frozen-exit-status",
          int(execution["observable"]["exit_status"]) == FROZEN_EXIT_STATUS)

    mediator, sink = fresh_mediator()
    results = [mediator.dispatch("p3.uart_write", (byte,)) for byte in uart]
    check("replay:all-bytes-accepted", all(result.ok for result in results))
    check("replay:output-byte-identical", bytes(sink.data) == uart)
    check("replay:call-count", len(mediator.calls) == len(uart))
    check("replay:not-terminated-before-exit", not mediator.terminated)
    exit_result = mediator.dispatch("p3.exit", (FROZEN_EXIT_STATUS,))
    check("replay:exit-accepted", exit_result.ok)
    check("replay:exit-status", mediator.exit_status == FROZEN_EXIT_STATUS
          and mediator.terminated)
    check("replay:no-failure", not mediator.failed)
    check("replay:output-sha256",
          hashlib.sha256(bytes(sink.data)).hexdigest()
          == hashlib.sha256(uart).hexdigest())

    second, second_sink = fresh_mediator()
    for byte in uart:
        second.dispatch("p3.uart_write", (byte,))
    second.dispatch("p3.exit", (FROZEN_EXIT_STATUS,))
    check("replay:deterministic-document",
          canonical_json(mediator.call_log_document())
          == canonical_json(second.call_log_document()))
    check("replay:deterministic-fingerprint",
          mediator.fingerprint() == second.fingerprint())
    check("replay:deterministic-output", bytes(second_sink.data) == uart)

    without_aliases = fresh_mediator(aliases=())[0]
    first_failure = without_aliases.dispatch("p3.uart_write", (uart[0],))
    check("replay:no-aliases-fails-closed",
          first_failure.failure.code is rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE)

    bridge = svc.AbiHostCallBridge(fresh_mediator()[0], abi.frozen_phase3_profile())
    replay_ok = all(bridge.host_call(2, 1, (byte,))[0] == 0 for byte in uart)
    check("replay:bridge-all-ok", replay_ok)
    check("replay:bridge-exit", bridge.host_call(1, 1, (0,))[0] == 0)
    check("replay:bridge-unknown-after-exit", bridge.host_call(2, 1, (0,))[0]
          == STATUS["TRAP"])

    manager_source = read_text(ROOT / ".openrecomp-phase4/src/p4_runtime_services_v1.py")
    ambient = [token for token in AMBIENT_CAPABILITY_TOKENS if token in manager_source]
    check("capability:no-ambient-host-access", not ambient)
    verifier = abi.GeneratedSourceVerifier(abi.build_contract(), abi.frozen_phase3_profile())
    generated_problems = verifier.verify_program(read_text(ROOT / gm.FROZEN_PROGRAM_PATH))
    check("capability:generated-source-compliant", generated_problems == [])
    check("capability:generated-service-macros-declared",
          {service.macro for service in abi.frozen_phase3_profile().services}
          == {"OR_RT_SERVICE_P3_EXIT", "OR_RT_SERVICE_P3_UART_WRITE"})
    FINDINGS["fixture_replacement"] = {
        "output_bytes": len(uart),
        "output_sha256": hashlib.sha256(uart).hexdigest(),
        "calls": len(mediator.calls),
        "call_log_fingerprint": mediator.fingerprint(),
        "ambient_tokens": ambient,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P4-03 runtime service mediation gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-03")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}

    print("=== P4-03 Runtime Service Mediation Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("interfaces")
        audit_interfaces()
        banner("mediator")
        audit_mediator()
        banner("bridge")
        audit_bridge()
        banner("fixture_replacement")
        audit_fixture_replacement()
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
    (EVIDENCE_DIR / "p4_03_tests.json").write_bytes(
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
