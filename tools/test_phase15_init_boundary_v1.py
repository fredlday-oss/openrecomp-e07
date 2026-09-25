#!/usr/bin/env python3
"""Deterministic P15-09 initialization boundary recovery gate.

Validates exact-site mediation of EnterCriticalSection / ExitCriticalSection
syscalls, verifies bounded hardware/BIOS execution through 520,000 blocks with
zero denials, zero trace failures, and zero unsupported MMIO/BIOS operations,
and records the boundary status:
A0:0x43 Exec handoff is reached only upon CD sector delivery, which is absent
from the bounded model; therefore OPENRECOMP_PHASE15_INIT_BOUNDARY_V1 is
honestly preserved as NOT_PROVEN while stage P15-09 PASSES.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src", ".openrecomp-phase15/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
import p15_probe_v1 as probe  # noqa: E402
import p15_surface_v1 as surface  # noqa: E402

STAGE = "P15-09"
ENTER_BLOCK = "0x80015f18"
EXIT_BLOCK = "0x80015f28"
EXEC_HANDOFF_BLOCK = "0x80015b84"
TITLE_ENTRY_BLOCK = "0x800380a0"

FRAGMENT = ROOT / ".openrecomp-phase15" / "runtime" / "p15_bios_extension_v1.c"

HARNESS = r"""
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

enum {
    P9_RT_OK = 0,
    P9_RT_MEMORY_OUT_OF_RANGE = 1,
    P9_RT_MEMORY_WIDTH_UNSUPPORTED = 2,
    P9_RT_UNSUPPORTED_OPERATION = 13,
    P9_RT_UNKNOWN_HOST_SERVICE = 100
};

static int p9_translate_ram(uint64_t address, uint64_t width, uint32_t *out_offset)
{
    (void)address; (void)width; (void)out_offset;
    return 1;
}

static int p14_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)
{
    (void)service_id; (void)argc; (void)args; (void)out_value;
    return P9_RT_UNKNOWN_HOST_SERVICE;
}

#include "p15_bios_extension_v1.c"

int main(void)
{
    uint64_t val = 0;
    int s;

    printf("init_ie=%u enter_calls=%llu exit_calls=%llu failures=%llu\n",
           p15_cpu_interrupt_enabled(),
           (unsigned long long)p15_enter_critical_calls(),
           (unsigned long long)p15_exit_critical_calls(),
           (unsigned long long)p15_critical_syscall_failures());

    /* enter 1: prior was 1, sets ie to 0, returns 1 */
    s = p15_critical_syscall(1, &val);
    printf("enter1 s=%d val=%llu ie=%u\n", s, (unsigned long long)val, p15_cpu_interrupt_enabled());

    /* enter 2: prior was 0, keeps ie 0, returns 0 */
    val = 99;
    s = p15_critical_syscall(1, &val);
    printf("enter2 s=%d val=%llu ie=%u\n", s, (unsigned long long)val, p15_cpu_interrupt_enabled());

    /* exit 1: sets ie to 1, returns 0 */
    val = 99;
    s = p15_critical_syscall(2, &val);
    printf("exit1 s=%d val=%llu ie=%u\n", s, (unsigned long long)val, p15_cpu_interrupt_enabled());

    /* exit 2 (already enabled): keeps ie 1, returns 0 */
    val = 99;
    s = p15_critical_syscall(2, &val);
    printf("exit2 s=%d val=%llu ie=%u\n", s, (unsigned long long)val, p15_cpu_interrupt_enabled());

    /* unhandled selectors fail closed */
    s = p15_critical_syscall(0, &val);
    printf("sel0 s=%d\n", s);
    s = p15_critical_syscall(3, &val);
    printf("sel3 s=%d\n", s);

    /* NULL out_value fails closed */
    s = p15_critical_syscall(1, NULL);
    printf("null s=%d\n", s);

    printf("final enter_calls=%llu exit_calls=%llu failures=%llu\n",
           (unsigned long long)p15_enter_critical_calls(),
           (unsigned long long)p15_exit_critical_calls(),
           (unsigned long long)p15_critical_syscall_failures());
    return 0;
}
"""


def _run_harness(workspace: pathlib.Path) -> str:
    source = workspace / "p15_critical_harness.c"
    source.write_text(HARNESS, encoding="utf-8", newline="\n")
    executable = workspace / "p15_critical_harness.exe"
    compile_cmd = [
        "clang", "-std=c11", "-Wall", "-Wextra", "-O0",
        f"-I{FRAGMENT.parent}", str(source), "-o", str(executable),
    ]
    completed = subprocess.run(compile_cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise AssertionError(f"compile failed: {completed.stderr.strip()}")
    run = subprocess.run([str(executable)], capture_output=True, text=True)
    if run.returncode != 0:
        raise AssertionError(f"harness failed: {run.stderr.strip()}")
    return run.stdout


def nonram_denials(parsed: dict) -> int:
    return sum(
        int(count)
        for signature, count in parsed.get("nonram", {}).items()
        if int(signature.rsplit(":", 1)[-1]) != 0
    )


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 1. Standalone unit verification of critical-section syscall semantics
    with tempfile.TemporaryDirectory() as tmp:
        harness_output = _run_harness(pathlib.Path(tmp))

    lines = dict(line.split(" ", 1) if " " in line else (line, "") for line in harness_output.strip().splitlines())
    gate.check("unit:initial-ie", "init_ie=1" in harness_output, harness_output.splitlines()[0])
    gate.check("unit:enter1", "enter1 s=0 val=1 ie=0" in harness_output, "enter returns prior state 1, sets ie=0")
    gate.check("unit:enter2", "enter2 s=0 val=0 ie=0" in harness_output, "enter returns prior state 0, keeps ie=0")
    gate.check("unit:exit1", "exit1 s=0 val=0 ie=1" in harness_output, "exit returns 0, sets ie=1")
    gate.check("unit:exit2-idempotent", "exit2 s=0 val=0 ie=1" in harness_output, "exit while enabled sets ie=1")
    gate.check("unit:sel0-fail-closed", "sel0 s=13" in harness_output, "selector 0 rejected")
    gate.check("unit:sel3-fail-closed", "sel3 s=13" in harness_output, "selector 3 rejected")
    gate.check("unit:null-out-value", "null s=13" in harness_output, "null pointer rejected")
    gate.check("unit:final-counts", "final enter_calls=2 exit_calls=2 failures=3" in harness_output,
               "exact call counters match")

    # 2. Live private initialization replay with critical-section mediation
    result = probe.build_and_run(
        root / ".openrecomp-phase15/build/P15-09", "p15-09",
        block_budget=surface.FRONTIER_BLOCK_BUDGET,
        p15_a0=(0x13, 0x72), p15_b0=surface.P15_B0,
    )
    first, second, simple = result["first"], result["second"], result["simple"]
    parsed = first["parsed"]
    counts = parsed.get("trace_block_counts", {})
    enter_count = int(simple.get("p15_enter_critical_calls", 0))
    exit_count = int(simple.get("p15_exit_critical_calls", 0))
    critical_failures = int(simple.get("p15_critical_syscall_failures", 0))
    cpu_ie = int(simple.get("p15_cpu_interrupt_enabled", 0))
    denials = nonram_denials(parsed)
    exec_count = int(counts.get(EXEC_HANDOFF_BLOCK, 0))
    title_count = int(counts.get(TITLE_ENTRY_BLOCK, 0))

    gate.check("replay:build", result["built"]["build_status"] == ["OK", "OK"],
               str(result["built"]["build_status"]))
    gate.check("replay:deterministic", probe.deterministic_match(result),
               first["stdout_sha256"])
    gate.check("replay:stderr-empty",
               first["stderr_bytes"] == 0 and second["stderr_bytes"] == 0,
               f"{first['stderr_bytes']}:{second['stderr_bytes']}")
    gate.check("replay:trace-indirect-clean",
               simple.get("trace_failure_count") == "0",
               simple.get("trace_failure_count"))
    gate.check("replay:nonram-denials-zero", denials == 0, str(denials))
    gate.check("replay:mmio-unsupported-zero",
               simple.get("p15_mmio_unsupported") == "0",
               simple.get("p15_mmio_unsupported"))
    gate.check("replay:bios-failures-zero",
               simple.get("p15_bios_service_failures") == "0",
               simple.get("p15_bios_service_failures"))
    gate.check("replay:critical-failures-zero", critical_failures == 0,
               str(critical_failures))
    gate.check("replay:host-bound-reached",
               simple.get("bound_reached") == "1"
               and simple.get("bound_denials") == "1",
               f"{simple.get('bound_reached')}:{simple.get('bound_denials')}")
    gate.check("critical:enter-count", enter_count == 7, str(enter_count))
    gate.check("critical:exit-count", exit_count == 7, str(exit_count))
    gate.check("critical:balanced", enter_count == exit_count,
               f"{enter_count}:{exit_count}")
    gate.check("critical:cpu-interrupt-enabled", cpu_ie == 1, str(cpu_ie))
    gate.check("boundary:exec-handoff-not-reached", exec_count == 0, str(exec_count))
    gate.check("boundary:title-entry-not-reached", title_count == 0, str(title_count))

    init_boundary = {
        "schema": "openrecomp-phase15-init-boundary-v1",
        "stage": STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "fixture": {"sha256": result["image"].file_sha256,
                    "size": result["image"].file_size},
        "build_status": result["built"]["build_status"],
        "run1_sha256": first["stdout_sha256"],
        "run2_sha256": second["stdout_sha256"],
        "byte_identical": probe.deterministic_match(result),
        "block_budget": surface.FRONTIER_BLOCK_BUDGET,
        "block_events": int(simple.get("trace_block_events", "0")),
        "bound_reached": simple.get("bound_reached"),
        "bound_denials": simple.get("bound_denials"),
        "trace_failure_count": int(simple.get("trace_failure_count", "0")),
        "memory_denial_count": denials,
        "unexpected_mmio_count": int(simple.get("p15_mmio_unsupported", "0")),
        "unknown_service_count": int(simple.get("p15_bios_service_failures", "0")),
        "critical_syscall_failures": critical_failures,
        "enter_critical_calls": enter_count,
        "exit_critical_calls": exit_count,
        "cpu_interrupt_enabled": cpu_ie,
        "boundary_exec_handoff": {
            "site": EXEC_HANDOFF_BLOCK,
            "target": TITLE_ENTRY_BLOCK,
            "reached": False,
            "count": exec_count,
            "basis": "TITLE overlay CD sector delivery absent from bounded model",
        },
        "boundary_marker": "NOT_PROVEN",
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "init_boundary.json", init_boundary)
    assert_public_safe(gate, "init-boundary", init_boundary, result["image"].payload)
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1", "stage": STAGE,
        "status": "PASS", "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "markers": {
            "OPENRECOMP_P15_09": "PASS",
            "OPENRECOMP_PHASE15_INIT_BOUNDARY_V1": "NOT_PROVEN",
        },
        "next_stage": "P15-10",
        "next_action": "verify fail-closed discipline against INIT_NO_FAIL_CLOSED contract",
    })
    gate.mark("OPENRECOMP_P15_09")
    gate.mark("OPENRECOMP_PHASE15_INIT_BOUNDARY_V1", "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-09"))
