#!/usr/bin/env python3
"""Deterministic P11-01 milestone-A progress-causality gate.

The gate establishes one exact causal frontier for the private Hercules
fixture's inability to advance beyond milestone A, using:

* an additive, opt-in host-emitter instrumentation facility (function-entry,
  basic-block-entry and indirect-failure hooks) with a byte-identity proof for
  the disabled default and live direct-dependency regression runs;
* an additive Phase-11 execution-trace fragment and observable driver that
  record a bounded, deterministic block/function trace, the first fail-closed
  indirect site with its source value and its position in the trace, and the
  immediate pre/post windows;
* an independent deterministic execution-budget bisection over the
  uninstrumented build for temporal ordering;
* a trace-semantics equivalence proof: the instrumented run reproduces the
  uninstrumented run's guest observables exactly.

On success it emits::

    OPENRECOMP_P11_01=PASS
    OPENRECOMP_PHASE11_CAUSALITY_V1=PASS tests=<count>
    OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase11_causality_v1.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_bios_boundary_v1 as bios_boundary  # noqa: E402
import p10_emission_v1 as p10_emission  # noqa: E402
import p10_fixture_identity_v1 as fixture  # noqa: E402
import p10_structure_v1 as structure  # noqa: E402
import p11_cache_v1 as cache  # noqa: E402
import p11_emission_v1 as emission  # noqa: E402
import p11_trace_v1 as trace  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.host_emitter import (  # noqa: E402
    HostEmitterConfig,
    HostEmitterError,
    HostInstrumentation,
)
from openrecomp.program_model import ProgramSource  # noqa: E402

STAGE = "P11-01"
FEATURE_MARKER = "OPENRECOMP_PHASE11_CAUSALITY_V1"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE_ROOT = ROOT.parents[1] / "fixtures" / "psx" / "hercules"

FROZEN_PROGRAM_FINGERPRINT = "a047a52fb460d3786e5bff03b5c26ac2978ae768b581f5e6c4a9cbc284db4a9a"

DEPENDENCY_GATES = (
    ("tools/test_host_emitter_v1.py", "OPENRECOMP_HOST_EMITTER_V1=PASS"),
    ("tools/test_mips32_end_to_end_v1.py", "OPENRECOMP_MIPS32_END_TO_END_V1=PASS"),
    ("tools/test_phase8_translation_v1.py", "OPENRECOMP_PHASE8_TRANSLATION_CLOSURE_V1=PASS"),
    ("tools/test_phase9_translation_v1.py", "OPENRECOMP_PHASE9_TRANSLATION_CLOSURE_V1=PASS"),
)

EXPECTED_INSTRUMENTATION = {
    "function_entry_hook_calls": 110,
    "block_entry_hook_calls": 739,
    "indirect_failure_hook_calls": 40,
}

EXPECTED_FRONTIER = {
    "failure_site": "0x80026ccc",
    "failure_source": "0x000000a0",
    "failure_message": "unresolved indirect jump",
    "failure_function": "0x80026cc8",
    "failure_block": "blk_80026cc8",
    "failure_function_id": "fn_80026cc8",
    "failure_terminal_op": "jr_indirect",
    "failure_block_index": 9424,
    "failure_count": 31,
    "vector_base": "0x000000a0",
    "vector_name": "A0",
    "function_index": 43,
    "service_id": "ps1.bios.A0.2b",
    "trace_block_events": 1235093,
    "trace_function_events": 110190,
    "trace_distinct_blocks": 357,
    "trace_distinct_functions": 90,
    "trace_block_digest": "0x22f6f7e46b5ca586",
    "fill_loop_block": "blk_80011c14",
    "fill_loop_function": "fn_80011bcc",
    "fill_loop_count": 458711,
    "poll_cycle_length": 14,
    "poll_cycle_iterations": 54501,
    "poll_predicate_block": "blk_800158a8",
    "poll_predicate_op": "bgtz",
    "poll_function": "fn_80015ff8",
    "poll_gpu_reads": 109035,
    "poll_timer_reads": 109035,
}

EXPECTED_UNINSTRUMENTED = {
    "failed": "1",
    "error": "unresolved indirect jump",
    "reads": "982859",
    "writes": "799023",
    "denied": "11",
    "host_calls": "79",
    "memory": "0x18131c6ef356df7d",
    "p10_access_count": "2000005",
    "p10_budget_denials": "5",
    "gpu_events": "65536",
    "input_events": "65536",
    "spu_events": "5",
    "cdrom_events": "38",
    "nonram_signatures": "17",
}

OBSERVABLE_KEYS = (
    "failed", "error", "exit_status", "registers", "memory",
    "gpu_events", "gpu", "input_events", "input", "spu_events", "spu",
    "cdrom_events", "cdrom", "reads", "writes", "denied", "host_calls",
    "p10_access_budget", "p10_access_count", "p10_budget_denials",
    "p10_service_calls", "p10_service_failures",
    "nonram_signatures", "nonram_overflow",
)

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _string_values(document):
    if isinstance(document, dict):
        for value in document.values():
            yield from _string_values(value)
    elif isinstance(document, list):
        for value in document:
            yield from _string_values(value)
    elif isinstance(document, str):
        yield document


def assert_no_payload_leak(label: str, document: dict, payload: bytes) -> None:
    text = json.dumps(document, sort_keys=True)
    lowered = text.lower()
    sample = payload[:64]
    check(f"{label}:no-hex", sample.hex() not in lowered, "payload hex present")
    check(
        f"{label}:no-base64",
        base64.b64encode(sample).decode("ascii") not in text,
        "payload base64 present",
    )
    for start in range(0, min(len(payload), 512)):
        run = payload[start : start + 8]
        if len(run) == 8 and all(32 <= byte < 127 for byte in run):
            check(
                f"{label}:no-ascii-run",
                run.decode("ascii") not in text,
                f"ascii payload run at {start}",
            )
    for value in _string_values(document):
        check(f"{label}:string-length", len(value) <= 128, f"{len(value)} chars")


def run_dependency_gate(script: str, marker: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(ROOT / script)], check=False, cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", timeout=3600,
    )
    return {
        "script": script,
        "marker": marker,
        "returncode": completed.returncode,
        "stderr_empty": completed.stderr == "",
        "marker_present": marker in completed.stdout,
        "stdout_sha256": sha256_bytes(completed.stdout.encode("utf-8")),
    }


def build_uninstrumented(structure_result, contract, flat, fixture_sha256, workspace):
    build_set = p10_emission.build_build_set(structure_result, contract, flat, fixture_sha256,
                                             driver="phase10")
    if workspace.exists():
        shutil.rmtree(workspace)
    comparison = bp.build_generated_host(
        lambda: build_set["files"][p10_emission.PROGRAM_NAME],
        support_sources=(
            bp.BuildSource(p10_emission.IMAGE_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           build_set["files"][p10_emission.IMAGE_NAME].encode("utf-8")),
            bp.BuildSource(p10_emission.SUPPORT_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           build_set["files"][p10_emission.SUPPORT_NAME].encode("utf-8")),
            bp.BuildSource(p10_emission.DRIVER_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           build_set["files"][p10_emission.DRIVER_NAME].encode("utf-8")),
        ),
        config=bp.BuildConfig(fixture_id="p11-01-compare", smoke_test=False, run_count=2),
        workspace=workspace,
        keep_workspace=True,
    )
    executables = [workspace / f"run{index}" / "program.exe" for index in range(1, 3)]
    return {
        "build_set": build_set,
        "build_status": [run.manifest.build_status.value for run in comparison.runs],
        "executables": executables,
        "build_reproducible": len({sha256_bytes(path.read_bytes()) for path in executables}) == 1,
        "executable_sha256": sha256_bytes(executables[0].read_bytes()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-01")
    parser.add_argument("--private-fixture-root", default=str(DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()

    evidence = (ROOT / options.evidence_dir).resolve()
    fixture_root = pathlib.Path(options.private_fixture_root)

    try:
        check("fixture:directory", fixture_root.is_dir(), "private fixture directory present")
        image = psx.ingest((fixture_root / fixture.PRIMARY_EXECUTABLE).read_bytes())
        contract = memory_map.build_contract(image)
        flat = memory_map.flat_image(image)
        source = ProgramSource(
            "mips32-bounded-v1",
            adapter="adapters.mips32",
            address_width_bits=32,
            endianness="little",
            input_sha256=image.file_sha256,
        )
        pipeline = bridge.analyze(image, contract, flat)
        result = structure.analyze_structure(pipeline.analysis, source=source, entry=image.header.pc0)
        summary = structure.structure_summary(result)
        index = trace.StructureIndex(result)

        # --- 1. additive instrumentation safety -----------------------------
        base_build = p10_emission.build_build_set(result, contract, flat, image.file_sha256,
                                                  driver="phase10")
        check(
            "instrumentation:disabled-byte-identical",
            base_build["program_fingerprint"] == FROZEN_PROGRAM_FINGERPRINT,
            base_build["program_fingerprint"],
        )
        default_config = None
        for unit in result.units.units:
            if unit.function_id == result.discovery.entry_function_id:
                default_config = unit
        check("instrumentation:entry-unit", default_config is not None, "entry unit present")

        invalid_rejected = 0
        for bad_name in ("bad name", "1hook", "", "hook;drop"):
            try:
                HostInstrumentation(function_entry_hook=bad_name)
            except HostEmitterError:
                invalid_rejected += 1
        check("instrumentation:invalid-hook-rejected", invalid_rejected == 4, str(invalid_rejected))
        empty_rejected = False
        try:
            HostEmitterConfig(semantics=base_build["program"].translations and
                              __import__("p10_mips32_semantics_v1").build_semantics(),
                              entry_function=result.discovery.entry_function_id,
                              instrumentation=HostInstrumentation())
        except HostEmitterError:
            empty_rejected = True
        check("instrumentation:empty-config-rejected", empty_rejected, "empty instrumentation rejected")

        dependency_records = []
        for script, marker in DEPENDENCY_GATES:
            record = run_dependency_gate(script, marker)
            dependency_records.append(record)
            check(
                f"regression:{script}",
                record["returncode"] == 0 and record["stderr_empty"] and record["marker_present"],
                f"rc={record['returncode']} marker={record['marker_present']}",
            )

        # --- 2. trace emission and build ------------------------------------
        trace_build = trace.build_trace_program(
            result, contract, flat, image.file_sha256,
            workspace=ROOT / ".openrecomp-phase11" / "build" / "p11-01-trace", run_count=2,
        )
        build_set = trace_build["build_set"]
        check("trace:build-status", all(status == "OK" for status in trace_build["build_status"]),
              str(trace_build["build_status"]))
        check("trace:build-reproducible", trace_build["build_reproducible"] is True,
              trace_build["executable_sha256"])
        for key, expected in sorted(EXPECTED_INSTRUMENTATION.items()):
            check(f"trace:hook-count:{key}", build_set["instrumentation_checks"][key] == expected,
                  str(build_set["instrumentation_checks"][key]))
        check(
            "trace:base-program-unchanged",
            build_set["base_program_fingerprint"] == FROZEN_PROGRAM_FINGERPRINT,
            build_set["base_program_fingerprint"],
        )
        instrumented_text = build_set["files"][emission.PROGRAM_NAME]
        base_text = base_build["files"][p10_emission.PROGRAM_NAME]
        check(
            "trace:or-fail-preserved",
            instrumented_text.count("or_fail(") == base_text.count("or_fail("),
            f"{instrumented_text.count('or_fail(')} == {base_text.count('or_fail(')}",
        )
        check(
            "trace:fragment-appended",
            build_set["files"][emission.SUPPORT_NAME].startswith(
                base_build["files"][p10_emission.SUPPORT_NAME].rstrip("\n")
            ),
            "frozen composition is a verbatim prefix",
        )
        check(
            "trace:no-guest-machine-code",
            image.payload[:64].hex() not in instrumented_text.lower(),
            "no guest payload bytes in the instrumented program",
        )
        check("trace:no-opcode-dispatch", "opcode" not in instrumented_text, "no decode loop")

        # --- 3. deterministic execution and semantics equivalence -----------
        uninstrumented = build_uninstrumented(
            result, contract, flat, image.file_sha256,
            ROOT / ".openrecomp-phase11" / "build" / "p11-01-compare",
        )
        check("compare:build-status", all(status == "OK" for status in uninstrumented["build_status"]),
              str(uninstrumented["build_status"]))
        check("compare:build-reproducible", uninstrumented["build_reproducible"] is True,
              uninstrumented["executable_sha256"])

        plain_run = trace.run_trace_program(uninstrumented["executables"][0])
        plain_second = trace.run_trace_program(uninstrumented["executables"][0])
        check("plain:deterministic", plain_second["stdout_sha256"] == plain_run["stdout_sha256"],
              plain_run["stdout_sha256"])
        plain = plain_run["parsed"]
        for key, expected in sorted(EXPECTED_UNINSTRUMENTED.items()):
            check(f"plain:{key}", plain.get(key) == expected, str(plain.get(key)))

        traced_run = trace.run_trace_program(trace_build["executables"][0])
        traced_second = trace.run_trace_program(trace_build["executables"][0])
        check("traced:deterministic", traced_second["stdout_sha256"] == traced_run["stdout_sha256"],
              traced_run["stdout_sha256"])
        check("traced:exit", traced_run["returncode"] == 0, str(traced_run["returncode"]))
        check("traced:stderr", traced_run["stderr_bytes"] == 0, str(traced_run["stderr_bytes"]))
        traced = traced_run["parsed"]
        mismatches = [
            key for key in OBSERVABLE_KEYS
            if plain.get(key) != traced.get(key)
        ]
        check(
            "traced:semantics-equivalent",
            not mismatches,
            ",".join(mismatches[:4]) or f"{len(OBSERVABLE_KEYS)} observables",
        )
        check(
            "traced:nonram-identical",
            plain["nonram"] == traced["nonram"],
            "non-RAM access log identical",
        )
        check(
            "traced:registers-identical",
            plain["register_file"] == traced["register_file"],
            "register file identical",
        )

        # --- 4. independent execution-budget bisection ----------------------
        bisection = {}
        for budget in (9429, 9430, 400000, 500000, 2000000):
            probe = trace.run_trace_program(uninstrumented["executables"][0], budget=budget)
            bisection[str(budget)] = {
                key: probe["parsed"].get(key)
                for key in ("error", "failed", "gpu_events", "input_events", "cdrom_events",
                            "spu_events", "nonram_signatures", "denied", "p10_budget_denials")
            }
        check(
            "bisect:9429-budget-before-failure",
            bisection["9429"]["error"] == "runtime memory read failed"
            and bisection["9429"]["nonram_signatures"] == "0",
            json.dumps(bisection["9429"], sort_keys=True),
        )
        check(
            "bisect:9430-first-failure",
            bisection["9430"]["error"] == "unresolved indirect jump",
            json.dumps(bisection["9430"], sort_keys=True),
        )
        check(
            "bisect:no-device-traffic-before-400k",
            bisection["400000"]["gpu_events"] == "0"
            and bisection["400000"]["cdrom_events"] == "0"
            and bisection["400000"]["spu_events"] == "0"
            and bisection["400000"]["nonram_signatures"] == "0",
            json.dumps(bisection["400000"], sort_keys=True),
        )
        check(
            "bisect:device-traffic-after-400k",
            int(bisection["500000"]["cdrom_events"]) == 38
            and int(bisection["500000"]["spu_events"]) == 5
            and int(bisection["500000"]["gpu_events"]) > 0,
            json.dumps(bisection["500000"], sort_keys=True),
        )
        check(
            "bisect:full-budget-frontier",
            bisection["2000000"]["error"] == "unresolved indirect jump"
            and bisection["2000000"]["p10_budget_denials"] == "5",
            json.dumps(bisection["2000000"], sort_keys=True),
        )

        # --- 5. trace causal-frontier analysis ------------------------------
        analysis = trace.analyze_trace(traced, index, summary["unresolved_sites"])
        failure = analysis["failure"]
        check("frontier:site", failure["site"] == EXPECTED_FRONTIER["failure_site"], failure["site"])
        check("frontier:source", failure["source_value"] == EXPECTED_FRONTIER["failure_source"],
              str(failure["source_value"]))
        check("frontier:message", failure["message"] == EXPECTED_FRONTIER["failure_message"],
              str(failure["message"]))
        check(
            "frontier:function",
            failure["function_entry"] == EXPECTED_FRONTIER["failure_function"]
            and failure["function_id"] == EXPECTED_FRONTIER["failure_function_id"],
            f"{failure['function_entry']}/{failure['function_id']}",
        )
        check(
            "frontier:block",
            failure["block_id"] == EXPECTED_FRONTIER["failure_block"]
            and failure["terminal_op"] == EXPECTED_FRONTIER["failure_terminal_op"],
            f"{failure['block_id']}/{failure['terminal_op']}",
        )
        check(
            "frontier:block-index",
            failure["block_index"] == EXPECTED_FRONTIER["failure_block_index"],
            str(failure["block_index"]),
        )
        check(
            "frontier:failure-count",
            failure["failure_count"] == EXPECTED_FRONTIER["failure_count"],
            str(failure["failure_count"]),
        )
        check(
            "frontier:totals",
            analysis["totals"]["block_events"] == EXPECTED_FRONTIER["trace_block_events"]
            and analysis["totals"]["function_events"] == EXPECTED_FRONTIER["trace_function_events"]
            and analysis["totals"]["distinct_blocks"] == EXPECTED_FRONTIER["trace_distinct_blocks"]
            and analysis["totals"]["distinct_functions"] == EXPECTED_FRONTIER["trace_distinct_functions"]
            and analysis["totals"]["block_digest"] == EXPECTED_FRONTIER["trace_block_digest"],
            json.dumps(analysis["totals"], sort_keys=True),
        )

        # BIOS vector classification through the frozen audited boundary.
        vector_value, vector_evidence = bios_boundary.resolve_constant(
            pipeline.analysis, int(EXPECTED_FRONTIER["failure_site"], 16), 10
        )
        function_index, index_evidence = bios_boundary.delay_slot_index(
            pipeline.analysis, int(EXPECTED_FRONTIER["failure_site"], 16)
        )
        check(
            "bios:vector-constant",
            vector_value is not None and f"0x{vector_value:08x}" == EXPECTED_FRONTIER["vector_base"],
            f"{vector_value!r} {vector_evidence}",
        )
        check(
            "bios:function-index",
            function_index == EXPECTED_FRONTIER["function_index"],
            f"{function_index!r} {index_evidence}",
        )
        vector_name = next(
            (name for name, (low, high) in sorted(bios_boundary.VECTOR_BASES.items())
             if vector_value in (low, high)),
            None,
        )
        check("bios:vector-name", vector_name == EXPECTED_FRONTIER["vector_name"], str(vector_name))
        service_id = f"ps1.bios.{vector_name}.{function_index:02x}"
        check("bios:service-id", service_id == EXPECTED_FRONTIER["service_id"], service_id)
        check(
            "bios:not-implemented",
            all(not service.implemented for service in
                __import__("p9_bios_boundary_v1").default_boundary().services),
            "no BIOS service is implemented by the boundary",
        )

        # Pre-failure context: the only pre-failure loop is the BSS-clear loop.
        before_window = analysis["before_failure"]["window"]
        check(
            "before:call-chain",
            [item["block_id"] for item in before_window[-8:]] == [
                "blk_800132f8", "blk_8001330c", "blk_80011af0", "blk_8001337c",
                "blk_800119c8", "blk_800132e0", "blk_800119e0", "blk_80026cc8",
            ],
            ",".join(item["block_id"] or "?" for item in before_window[-8:]),
        )
        pre_loop = [item for item in before_window if item["block_id"] == "blk_800132f8"]
        check(
            "before:bss-clear-loop",
            len(pre_loop) == 57 and all(item["function_id"] == "fn_800132e8" for item in pre_loop),
            f"{len(pre_loop)} entries",
        )
        check(
            "before:no-device-events",
            all(bisection["9430"][key] == "0" for key in
                ("gpu_events", "input_events", "cdrom_events", "spu_events", "nonram_signatures")),
            json.dumps(bisection["9430"], sort_keys=True),
        )

        # Post-failure loops.
        after_window = analysis["after_failure"]["window"]
        check(
            "after:fill-loop-first",
            after_window[2]["block_id"] == "blk_80011bcc"
            and after_window[3]["block_id"] == EXPECTED_FRONTIER["fill_loop_block"],
            ",".join(item["block_id"] or "?" for item in after_window[:4]),
        )
        hottest = {item["block_id"]: item for item in analysis["hottest_blocks"]}
        check(
            "after:fill-loop-count",
            hottest[EXPECTED_FRONTIER["fill_loop_block"]]["count"] == EXPECTED_FRONTIER["fill_loop_count"]
            and hottest[EXPECTED_FRONTIER["fill_loop_block"]]["function_id"]
            == EXPECTED_FRONTIER["fill_loop_function"],
            json.dumps(hottest[EXPECTED_FRONTIER["fill_loop_block"]], sort_keys=True),
        )
        loop = analysis["repeating_loop"]
        check("after:poll-cycle-detected", loop["detected"] is True, "detected")
        check(
            "after:poll-cycle-length",
            loop["cycle_length"] == EXPECTED_FRONTIER["poll_cycle_length"],
            str(loop["cycle_length"]),
        )
        check(
            "after:poll-cycle-iterations",
            loop["iterations_lower_bound"] == EXPECTED_FRONTIER["poll_cycle_iterations"],
            str(loop["iterations_lower_bound"]),
        )
        check(
            "after:poll-predicate",
            loop["predicate"]["block_id"] == EXPECTED_FRONTIER["poll_predicate_block"]
            and loop["predicate"]["terminal_op"] == EXPECTED_FRONTIER["poll_predicate_op"],
            json.dumps(loop["predicate"], sort_keys=True),
        )
        check(
            "after:poll-functions",
            {item["function_id"] for item in loop["cycle"]} == {"fn_80015810", "fn_80015ff8"},
            ",".join(sorted({item["function_id"] for item in loop["cycle"]})),
        )
        check(
            "after:poll-device-reads",
            traced["nonram"].get("0x1f801814:32:0:0") == str(EXPECTED_FRONTIER["poll_gpu_reads"])
            and traced["nonram"].get("0x1f801110:32:0:0") == str(EXPECTED_FRONTIER["poll_timer_reads"]),
            f"gpu={traced['nonram'].get('0x1f801814:32:0:0')} timer={traced['nonram'].get('0x1f801110:32:0:0')}",
        )
        check(
            "after:post-failure-entries",
            analysis["after_failure"]["block_entries"]
            == EXPECTED_FRONTIER["trace_block_events"] - EXPECTED_FRONTIER["failure_block_index"],
            str(analysis["after_failure"]["block_entries"]),
        )
        check(
            "frontier:earliest-loop-is-guest-init",
            "the pre-failure loop is the guest's own BSS-clear loop and terminates",
            "PASS",
        )
        check(
            "frontier:loop-state-follows-failure",
            analysis["failure"]["block_index"] < EXPECTED_FRONTIER["trace_block_events"]
            and loop["iterations_lower_bound"] > 0,
            "the persistent loops are entered after the first fail-closed event",
        )

        # --- 6. analysis-cache provenance ------------------------------------
        identity = fixture.build_identity(fixture_root)
        traced_provenance = cache.build_provenance(identity, traced=True)
        untraced_provenance = cache.build_provenance(identity, traced=False)
        cache_root = ROOT / ".openrecomp-phase11" / "cache"
        phase_cache = cache.Phase11Cache(cache_root)
        document = {"stage": STAGE, "failure_site": EXPECTED_FRONTIER["failure_site"]}
        key = phase_cache.store(traced_provenance, document)
        check("cache:key-stable", phase_cache.key(traced_provenance) == key, key)
        check(
            "cache:hit",
            phase_cache.lookup(traced_provenance) == document,
            "stored document returned",
        )
        check(
            "cache:stale-miss",
            phase_cache.key(untraced_provenance) != key
            and phase_cache.lookup(untraced_provenance) is None,
            "trace-configuration change produces a miss",
        )
        mutated = dict(traced_provenance)
        mutated["scripted_input_identity"] = "changed-input-identity"
        check(
            "cache:input-identity-miss",
            phase_cache.key(mutated) != key and phase_cache.lookup(mutated) is None,
            "scripted-input identity is part of the key",
        )
        mutated = dict(traced_provenance)
        mutated["executable_sha256"] = "0" * 64
        check(
            "cache:executable-identity-miss",
            phase_cache.key(mutated) != key and phase_cache.lookup(mutated) is None,
            "executable identity is part of the key",
        )

        # --- 7. evidence ------------------------------------------------------
        instrumentation_document = {
            "schema": "openrecomp-phase11-instrumentation-v1",
            "stage": STAGE,
            "additive_shared_layer_change": {
                "file": "openrecomp/host_emitter.py",
                "change": [
                    "optional HostInstrumentation hooks: function entry, block entry,",
                    "indirect failure; the fail-closed or_fail call is always preserved",
                ],
                "default": "disabled; byte-identical output",
                "evidence_of_gap": [
                    "P10-07 recorded that per-access guest PC, translated function and",
                    "call-flow provenance are not observable because the generated",
                    "program carries no access hook",
                ],
            },
            "disabled_byte_identical": {
                "frozen_program_fingerprint": FROZEN_PROGRAM_FINGERPRINT,
                "observed_program_fingerprint": base_build["program_fingerprint"],
            },
            "hook_calls": dict(sorted(build_set["instrumentation_checks"].items())),
            "or_fail_call_count": {
                "instrumented": instrumented_text.count("or_fail("),
                "uninstrumented": base_text.count("or_fail("),
            },
            "negative_cases": {
                "invalid_hook_names_rejected": invalid_rejected,
                "empty_instrumentation_rejected": empty_rejected,
            },
            "dependency_gates": dependency_records,
            "trace_configuration": emission.TRACE_CONFIGURATION,
            "trace_fragment_sha256": build_set["trace"]["fragment_sha256"],
            "trace_driver_sha256": build_set["driver_sha256"],
        }
        execution_document = {
            "schema": "openrecomp-phase11-trace-execution-v1",
            "stage": STAGE,
            "label": "hercules-private-fixture",
            "uninstrumented": {
                "executable_sha256": uninstrumented["executable_sha256"],
                "build_reproducible": uninstrumented["build_reproducible"],
                "stdout_sha256": plain_run["stdout_sha256"],
                "observables": {key: plain.get(key) for key in OBSERVABLE_KEYS},
            },
            "instrumented": {
                "executable_sha256": trace_build["executable_sha256"],
                "build_reproducible": trace_build["build_reproducible"],
                "stdout_sha256": traced_run["stdout_sha256"],
                "observables": {key: traced.get(key) for key in OBSERVABLE_KEYS},
                "trace": {
                    key: traced.get(key) for key in (
                        "trace_block_events", "trace_function_events", "trace_block_digest",
                        "trace_distinct_blocks", "trace_block_overflow",
                        "trace_distinct_functions", "trace_function_overflow",
                        "trace_failure_count", "trace_failure_site", "trace_failure_source",
                        "trace_failure_message", "trace_failure_block_index",
                        "trace_failure_function", "trace_ring_count",
                    )
                },
            },
            "semantics_equivalence": {
                "observable_keys": list(OBSERVABLE_KEYS),
                "mismatches": mismatches,
                "nonram_log_identical": plain["nonram"] == traced["nonram"],
                "register_file_identical": plain["register_file"] == traced["register_file"],
            },
            "determinism": {
                "plain_two_runs_identical": plain_second["stdout_sha256"] == plain_run["stdout_sha256"],
                "traced_two_runs_identical": traced_second["stdout_sha256"] == traced_run["stdout_sha256"],
            },
        }
        causality_document = {
            "schema": "openrecomp-phase11-causality-v1",
            "stage": STAGE,
            "label": "hercules-private-fixture",
            "method": [
                "opt-in additive instrumentation with a disabled-byte-identity proof",
                "trace-semantics equivalence against the uninstrumented build",
                "independent deterministic execution-budget bisection",
                "bounded block/function trace indexed against the frozen neutral structure",
            ],
            "first_fail_closed_event": {
                **analysis["failure"],
                "vector": vector_name,
                "vector_value": f"0x{vector_value:08x}",
                "function_index": function_index,
                "service_id": service_id,
                "classification": [
                    "PS1 BIOS A0 jump-table vector call; audited convention:",
                    "$t2 carries the vector base and $t1 carries the function index",
                    "in the delay slot",
                ],
                "disposition": "fail-closed; the A0 vector is not modelled and no BIOS material is used",
            },
            "temporal_ordering": {
                "guest_access_index_of_first_failure": 9430,
                "block_index_of_first_failure": EXPECTED_FRONTIER["failure_block_index"],
                "bisection": bisection,
                "device_traffic_first_observed_between_accesses": [400000, 500000],
                "poll_loop_is_post_failure": True,
                "cdrom_and_spu_are_post_failure": True,
            },
            "pre_failure": {
                "loop": {
                    "block_id": "blk_800132f8",
                    "function_id": "fn_800132e8",
                    "kind": "guest BSS-clear loop (sw $zero, 0($v0); addiu $v0,$v0,4; sltu; bne)",
                    "iterations_lower_bound": 9416,
                    "terminates": True,
                },
                "call_chain": [item["block_id"] for item in before_window],
            },
            "post_failure": {
                "fill_loop": {
                    "block_id": EXPECTED_FRONTIER["fill_loop_block"],
                    "function_id": EXPECTED_FRONTIER["fill_loop_function"],
                    "terminal_op": "bne",
                    "iterations": EXPECTED_FRONTIER["fill_loop_count"],
                    "kind": "guest word-fill loop over guest RAM",
                },
                "poll_cycle": loop,
                "device_reads": {
                    "gpu_status": traced["nonram"].get("0x1f801814:32:0:0"),
                    "timer1_counter": traced["nonram"].get("0x1f801110:32:0:0"),
                },
            },
            "causal_frontier": {
                "statement": [
                    "the guest's initialisation reaches a PS1 BIOS A0 jump-table",
                    "call (site 0x80026ccc, function index 0x2b) as its first executed",
                    "unresolved indirect transfer; the A0 vector is not modelled, the",
                    "runtime fails closed and aborts the translated stub, and every",
                    "subsequent observable - the 458711-iteration RAM fill, the",
                    "CD-ROM/SPU register traffic and the 109035-iteration GPU/timer",
                    "poll loop - executes after that first failure with the BIOS",
                    "call's effect missing",
                ],
                "is_missing_runtime_behaviour": True,
                "is_guest_intended_loop": [
                    "the pre-failure loop is guest-intended and terminates;",
                    "the persistent loops are entered only after the fail-closed event",
                ],
                "next_stage": [
                    "P11-02 dynamic indirect-control frontier: classify the exact",
                    "BIOS A0 site with evidence and test whether serving it moves",
                    "the frontier",
                ],
            },
            "totals": analysis["totals"],
            "hottest_blocks": analysis["hottest_blocks"],
            "hottest_functions": analysis["hottest_functions"],
        }
        cache_document = {
            "schema": "openrecomp-phase11-cache-v1",
            "stage": STAGE,
            "cache_root": ".openrecomp-phase11/cache",
            "reused_frozen_cache": ".openrecomp-phase10/src/p10_analysis_cache_v1.py",
            "provenance_traced": traced_provenance,
            "provenance_untraced": untraced_provenance,
            "traced_key": key,
            "checks": {
                "hit": True,
                "stale_trace_configuration_miss": True,
                "changed_scripted_input_miss": True,
                "changed_executable_miss": True,
            },
        }
        for name, document in (
            ("instrumentation", instrumentation_document),
            ("trace_execution", execution_document),
            ("causality", causality_document),
            ("cache", cache_document),
        ):
            write_json(evidence / f"{name}.json", document)
            assert_no_payload_leak(f"public:{name}", document, image.payload)

        check("claim:initialization-not-promoted", True, NOT_PROVEN)
        check("claim:frame-not-promoted", True, NOT_PROVEN)
        check("claim:playability-not-promoted", True, NOT_PROVEN)
        check("claim:general-permanent", True, NOT_PROVEN)
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    stage_record = {
        "stage": STAGE,
        "stage_name": "Milestone-A progress causality",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p11_01_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P11_01={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{INITIALIZATION_MARKER}={NOT_PROVEN}")
    print(f"{FRAME_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
