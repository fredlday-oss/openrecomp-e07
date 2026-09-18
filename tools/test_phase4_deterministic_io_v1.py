#!/usr/bin/env python3
"""OpenRecomp Phase-4 deterministic I/O, timing and input gate (P4-04).

Proves the bounded deterministic interfaces in
``.openrecomp-phase4/src/p4_deterministic_io_v1.py``:

* a deterministic console with bounded output and an explicit input
  exhaustion policy (end-of-input sentinel or fail closed);
* deterministic file-style buffers with bounded capacity and no host
  filesystem access;
* a virtual clock advanced only by explicit ticks and a bounded event queue
  with deterministic virtual-tick delivery ordering;
* an explicit ``RecordedInput`` snapshot with a digest, so every run consumes
  exactly the declared inputs (console bytes, file images, event plan,
  initial tick) and never ambient host input;
* typed/versioned ``or.runtime.stream_read``, ``or.runtime.clock_ticks`` and
  ``or.runtime.input_poll`` interfaces composed onto the P4-03 base catalog
  with handlers bound to an ``IoRuntime``;
* the exact frozen Phase-3 output interaction (499 bytes from the P3-08
  evidence) replays byte-identically through the I/O-bound mediator.

It emits::

    OPENRECOMP_P4_04=PASS
    OPENRECOMP_PHASE4_DETERMINISTIC_IO_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_deterministic_io_v1.py
    python tools/test_phase4_deterministic_io_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-04
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

import p4_deterministic_io_v1 as dio  # noqa: E402
import p4_runtime_services_v1 as svc  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402
from openrecomp.program_model import canonical_json  # noqa: E402

STAGE = "P4-04"
STAGE_MARKER = "OPENRECOMP_P4_04"
FEATURE_MARKER = "OPENRECOMP_PHASE4_DETERMINISTIC_IO_V1"
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
MODULE_PATH = ".openrecomp-phase4/src/p4_deterministic_io_v1.py"

FROZEN_OUTPUT_BYTES = 499
STREAM_READ = "or.runtime.stream_read"
CLOCK_TICKS = "or.runtime.clock_ticks"
INPUT_POLL = "or.runtime.input_poll"

AMBIENT_TOKENS = (
    "import time", "import os", "import random", "import secrets",
    "import subprocess", "import socket", "import uuid", "import datetime",
    "time.time", "time.monotonic", "os.environ", "open(", "getpid",
)
FORBIDDEN_CORE_TOKENS = ("coremark", "mips", "ps2", "n64", "p3.", "uart", "r5900")

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def expect_fail(label: str, thunk, error_type=dio.IoModelError) -> None:
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


def sample_record() -> dio.RecordedInput:
    return dio.RecordedInput(
        console_input=b"AB",
        files=(("stdin.txt", b"hello"),),
        events=(dio.InputEvent(5, dio.EventKind.KEY, 0x41),
                dio.InputEvent(10, dio.EventKind.BYTE, 0x42, 1),
                dio.InputEvent(10, dio.EventKind.TIMER, 7)),
        initial_ticks=3,
    )


def scripted(runtime: dio.IoRuntime) -> dio.IoRuntime:
    runtime.read_stream(dio.STREAM_CONSOLE_IN)
    runtime.read_stream(dio.STREAM_CONSOLE_IN)
    runtime.read_stream(dio.STREAM_CONSOLE_IN)
    runtime.write_stream(dio.STREAM_CONSOLE_OUT, 0x41)
    runtime.write_stream(dio.STREAM_CONSOLE_OUT, 0x42)
    runtime.advance_ticks(5)
    runtime.poll_event_code()
    runtime.advance_ticks(5)
    runtime.poll_event_code()
    runtime.poll_event_code()
    runtime.poll_event_code()
    runtime.open_file("stdin.txt").read(3)
    return runtime


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
# Recorded input and console
# ---------------------------------------------------------------------------
def audit_recorded_input() -> None:
    record = sample_record()
    check("record:digest-format", re.fullmatch(r"[0-9a-f]{64}", record.fingerprint()))
    check("record:digest-stable", record.fingerprint() == sample_record().fingerprint())
    check("record:document",
          record.to_document()["console_input_bytes"] == 2
          and record.to_document()["initial_ticks"] == 3)
    changed = dio.RecordedInput(console_input=b"AB", files=(("stdin.txt", b"hellp"),),
                                events=record.events, initial_ticks=3)
    check("record:digest-sensitive", changed.fingerprint() != record.fingerprint())
    expect_fail("record-duplicate-file", lambda: dio.RecordedInput(
        files=(("a.txt", b"1"), ("a.txt", b"2"))))
    expect_fail("record-bad-file-name", lambda: dio.RecordedInput(files=(("Bad Name", b"1"),)))
    expect_fail("record-non-bytes-file", lambda: dio.RecordedInput(files=(("a.txt", "text"),)))
    expect_fail("record-non-bytes-console", lambda: dio.RecordedInput(console_input="text"))
    expect_fail("record-negative-ticks", lambda: dio.RecordedInput(initial_ticks=-1))
    expect_fail("record-bad-event", lambda: dio.RecordedInput(events=("x",)))

    console = dio.DeterministicConsole(b"AB", output_capacity=2)
    check("console:read-a", console.read_byte() == 0x41)
    check("console:read-b", console.read_byte() == 0x42)
    check("console:eof-sentinel", console.read_byte() == dio.EOF_SENTINEL)
    check("console:pending-input", console.pending_input == 0)
    check("console:input-length", console.input_length == 2)
    console.write_byte(1)
    console.write_byte(2)
    check("console:output", console.output == b"\x01\x02")
    expect_fail("console-output-capacity", lambda: console.write_byte(3))
    expect_fail("console-byte-overflow", lambda: dio.DeterministicConsole().write_byte(0x100))
    expect_fail("console-negative-byte", lambda: dio.DeterministicConsole().write_byte(-1))
    expect_fail("console-zero-capacity",
                lambda: dio.DeterministicConsole(output_capacity=0))
    strict = dio.DeterministicConsole(b"")
    expect_fail("console-fault-policy",
                lambda: strict.read_byte(policy=dio.InputExhaustionPolicy.FAULT))
    expect_fail("console-bad-policy",
                lambda: strict.read_byte(policy="eof"))
    check("console:document",
          console.to_document()["output_bytes"] == 2
          and console.to_document()["input_read"] == 2)
    FINDINGS["recorded_input"] = {
        "record_fingerprint": record.fingerprint(),
        "console_document": console.to_document(),
    }


# ---------------------------------------------------------------------------
# File buffers, clock and events
# ---------------------------------------------------------------------------
def audit_files_time_events() -> None:
    file_buffer = dio.DeterministicFileBuffer("log.txt", capacity=8, initial=b"ab")
    check("file:read", file_buffer.read(2) == b"ab")
    check("file:eof", file_buffer.read_byte() == dio.EOF_SENTINEL)
    file_buffer.seek(1)
    check("file:seek-read", file_buffer.read(1) == b"b")
    file_buffer.write(b"cd")
    check("file:write-append", file_buffer.snapshot() == b"abcd")
    file_buffer.seek(0)
    check("file:size", file_buffer.size == 4)
    expect_fail("file:capacity",
                lambda: dio.DeterministicFileBuffer("x.txt", capacity=2, initial=b"ab").write(b"c"))
    expect_fail("file:initial-too-large",
                lambda: dio.DeterministicFileBuffer("x.txt", capacity=2, initial=b"abc"))
    read_only = dio.DeterministicFileBuffer("ro.txt", capacity=4, initial=b"x", writable=False)
    expect_fail("file:read-only-write", lambda: read_only.write(b"y"))
    expect_fail("file:seek-beyond-capacity", lambda: read_only.seek(5))
    expect_fail("file:bad-name", lambda: dio.DeterministicFileBuffer("Bad", capacity=1))
    expect_fail("file:zero-capacity", lambda: dio.DeterministicFileBuffer("a", capacity=0))

    clock = dio.VirtualClock(initial_ticks=4)
    check("clock:initial", clock.ticks == 4)
    check("clock:advance", clock.advance(3) == 7)
    check("clock:read-does-not-advance", clock.ticks == 7)
    expect_fail("clock:negative-delta", lambda: clock.advance(-1))
    expect_fail("clock:overflow", lambda: dio.VirtualClock(dio.TICKS_MAX).advance(1))
    check("clock:document", clock.to_document() == {"ticks": 7, "source": "virtual"})

    queue = dio.EventQueue((
        dio.InputEvent(10, dio.EventKind.BYTE, 0x42),
        dio.InputEvent(5, dio.EventKind.KEY, 0x41),
    ), max_events=4)
    check("events:next-tick", queue.next_tick() == 5)
    check("events:not-early", queue.pop_due(4) is None)
    first = queue.pop_due(5)
    check("events:deliver-ordered", first.code == 0x41)
    second = queue.pop_due(10)
    check("events:deliver-second", second.code == 0x42)
    check("events:empty", queue.pop_due(10) is None and queue.pending == 0)
    check("events:delivered-log", len(queue.delivered) == 2)
    same_tick = dio.EventQueue((
        dio.InputEvent(3, dio.EventKind.KEY, 1),
        dio.InputEvent(3, dio.EventKind.KEY, 2),
    ))
    check("events:insertion-order", same_tick.pop_due(3).code == 1
          and same_tick.pop_due(3).code == 2)
    expect_fail("events:overflow", lambda: dio.EventQueue(
        (dio.InputEvent(0, dio.EventKind.KEY, 1),), max_events=0))
    expect_fail("events:too-many", lambda: dio.EventQueue(
        tuple(dio.InputEvent(0, dio.EventKind.KEY, index) for index in range(3)),
        max_events=2))
    expect_fail("events:negative-tick", lambda: dio.InputEvent(-1, dio.EventKind.KEY, 1))
    expect_fail("events:bad-kind", lambda: dio.InputEvent(0, "key", 1))
    check("events:timer-kind", dio.InputEvent(0, dio.EventKind.TIMER, 1).kind
          is dio.EventKind.TIMER)
    check("events:kinds", tuple(kind.value for kind in dio.EventKind)
          == ("byte", "key", "timer", "pointer"))
    FINDINGS["files_time_events"] = {
        "file_document": file_buffer.to_document(),
        "clock_document": clock.to_document(),
        "event_document": queue.to_document(),
    }


# ---------------------------------------------------------------------------
# IoRuntime and service integration
# ---------------------------------------------------------------------------
def audit_runtime_services() -> None:
    runtime = dio.IoRuntime(sample_record())
    check("runtime:read-a", runtime.read_stream(dio.STREAM_CONSOLE_IN) == 0x41)
    check("runtime:read-b", runtime.read_stream(dio.STREAM_CONSOLE_IN) == 0x42)
    check("runtime:eof", runtime.read_stream(dio.STREAM_CONSOLE_IN) == dio.EOF_SENTINEL)
    runtime.write_stream(dio.STREAM_CONSOLE_OUT, 0x5A)
    check("runtime:write", runtime.console.output == b"Z")
    check("runtime:ticks", runtime.clock_ticks() == 3)
    check("runtime:poll-early", runtime.poll_event_code() == dio.NO_EVENT_SENTINEL)
    check("runtime:advance", runtime.advance_ticks(2) == 5)
    check("runtime:poll-due", runtime.poll_event_code() == 0x41)
    expect_fail("runtime:unknown-file-open", lambda: runtime.open_file("nope.txt"))
    expect_fail("runtime:bad-output-stream", lambda: runtime.write_stream(7, 1))
    expect_fail("runtime:bad-input-stream", lambda: runtime.read_stream(7))
    expect_fail("runtime:bad-record", lambda: dio.IoRuntime(object()))
    expect_fail("runtime:bad-policy", lambda: dio.IoRuntime(sample_record(), input_policy="eof"))
    strict = dio.IoRuntime(dio.RecordedInput(), input_policy=dio.InputExhaustionPolicy.FAULT)
    expect_fail("runtime:input-fault", lambda: strict.read_stream(dio.STREAM_CONSOLE_IN))
    expect_fail("runtime:ambient-rejected", lambda: dio.ambient_input())
    check("runtime:ambient-flag", runtime.to_document()["ambient_host_input"] is False)

    registry = dio.io_registry()
    check("services:registry-composition",
          registry.service_ids == tuple(sorted((
              "or.runtime.exit", "or.runtime.stream_write", STREAM_READ,
              CLOCK_TICKS, INPUT_POLL))))
    check("services:base-catalog-unmodified",
          svc.standard_registry().service_ids == ("or.runtime.exit",
                                                 "or.runtime.stream_write"))
    check("services:interface-typed",
          [interface.to_document() for interface in dio.io_interfaces()]
          == [{"service_id": STREAM_READ, "version": rt.RUNTIME_ABI_VERSION,
               "arg_types": ["u32"], "result_type": "u32",
               "terminates_run": False,
               "description": "Read one byte from a declared input stream; "
                              "0xffffffff means end-of-input."},
              {"service_id": CLOCK_TICKS, "version": rt.RUNTIME_ABI_VERSION,
               "arg_types": [], "result_type": "u64", "terminates_run": False,
               "description": "Read the deterministic virtual tick count (never "
                              "the host clock)."},
              {"service_id": INPUT_POLL, "version": rt.RUNTIME_ABI_VERSION,
               "arg_types": [], "result_type": "u32", "terminates_run": False,
               "description": "Return the next due input event code or 0xffffffff "
                              "when none is due."}])
    expect_fail("services:handlers-need-runtime", lambda: dio.io_handlers(object()))

    mediator = dio.mediator_with_io(runtime)
    check("services:stream-write", mediator.dispatch("p3.uart_write", (0x41,)).ok)
    check("services:stream-write-output", runtime.console.output == b"ZA")
    check("services:clock", mediator.dispatch(CLOCK_TICKS, ()).value == 5)
    check("services:poll-early", mediator.dispatch(INPUT_POLL, ()).value
          == dio.NO_EVENT_SENTINEL)
    runtime.advance_ticks(5)
    check("services:poll", mediator.dispatch(INPUT_POLL, ()).value == 0x42)
    check("services:stream-read", mediator.dispatch(STREAM_READ, (1,)).value
          == dio.EOF_SENTINEL)
    check("services:exit", mediator.dispatch("p3.exit", (0,)).ok)
    check("services:bridge-unknown-stream",
          dio.mediator_with_io(dio.IoRuntime(sample_record()))
          .dispatch(STREAM_READ, (9,)).failure.code.value == "HOST_SERVICE_FAILED")
    FINDINGS["runtime_services"] = {
        "document": runtime.to_document(),
        "fingerprint": runtime.fingerprint(),
        "registry": list(registry.service_ids),
    }


# ---------------------------------------------------------------------------
# Determinism and frozen replay
# ---------------------------------------------------------------------------
def audit_determinism_and_replay() -> None:
    first = scripted(dio.IoRuntime(sample_record()))
    second = scripted(dio.IoRuntime(sample_record()))
    check("determinism:document",
          canonical_json(first.to_document()) == canonical_json(second.to_document()))
    check("determinism:fingerprint", first.fingerprint() == second.fingerprint())
    check("determinism:output", first.console.output == second.console.output)
    check("determinism:event-log",
          first.to_document()["event_codes"] == second.to_document()["event_codes"])
    check("determinism:policies",
          dio.IoRuntime(sample_record()).input_policy is dio.InputExhaustionPolicy.EOF)
    check("determinism:no-host-time",
          first.to_document()["clock"]["source"] == "virtual")
    module_source = read_text(ROOT / MODULE_PATH)
    ambient = [token for token in AMBIENT_TOKENS if token in module_source]
    check("determinism:no-ambient-tokens", not ambient)
    core = canonical_json(dio.RecordedInput().to_document()).lower()
    check("determinism:no-fixture-tokens",
          not any(token in core for token in FORBIDDEN_CORE_TOKENS))

    execution = json.loads(read_text(ROOT / P3_08_EXECUTION))
    uart = bytes.fromhex(execution["observable"]["uart_hex"])
    check("replay:frozen-stream-length", len(uart) == FROZEN_OUTPUT_BYTES)
    runtime = dio.IoRuntime(dio.RecordedInput())
    mediator = dio.mediator_with_io(runtime)
    accepted = all(mediator.dispatch("p3.uart_write", (byte,)).ok for byte in uart)
    check("replay:all-bytes-accepted", accepted)
    check("replay:output-byte-identical", runtime.console.output == uart)
    check("replay:exit", mediator.dispatch("p3.exit", (0,)).ok)
    check("replay:no-failure", not mediator.failed)
    check("replay:output-sha256",
          hashlib.sha256(runtime.console.output).hexdigest()
          == hashlib.sha256(uart).hexdigest())
    FINDINGS["determinism_replay"] = {
        "fingerprint": first.fingerprint(),
        "frozen_output_sha256": hashlib.sha256(uart).hexdigest(),
        "frozen_output_bytes": len(uart),
        "ambient_tokens": ambient,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P4-04 deterministic I/O gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-04")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}

    print("=== P4-04 Deterministic I/O Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("recorded_input")
        audit_recorded_input()
        banner("files_time_events")
        audit_files_time_events()
        banner("runtime_services")
        audit_runtime_services()
        banner("determinism_replay")
        audit_determinism_and_replay()
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
    (EVIDENCE_DIR / "p4_04_tests.json").write_bytes(
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
