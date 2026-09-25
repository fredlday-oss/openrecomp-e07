#!/usr/bin/env python3
"""Deterministic P15-06 Timer1 and RAM frame-tick virtual-time gate."""

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

import p11_native_v1 as native  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402

from p15_contracts_v1 import TIMER1_VIRTUAL_TIME_MARKER  # noqa: E402
from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
import p15_analysis_v1 as analysis_mod  # noqa: E402
import p15_emission_v1 as emission  # noqa: E402
import p15_mmio_contract_v1 as contract  # noqa: E402
import p15_surface_v1 as surface  # noqa: E402
import p15_trace_v1 as trace  # noqa: E402

STAGE = "P15-06"
FRAGMENT = ROOT / ".openrecomp-phase15/runtime/p15_mmio_extension_v1.c"

HARNESS = r"""
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
enum {
    P9_RT_OK = 0,
    P9_RT_MEMORY_OUT_OF_RANGE = 1,
    P9_RT_MEMORY_WIDTH_UNSUPPORTED = 2,
    P9_RT_UNSUPPORTED_OPERATION = 13
};
static uint64_t g_p9_denied_accesses;
static uint64_t g_p9_memory_reads;
static unsigned char g_p9_ram[0x40000];
static int p9_translate_ram(uint64_t address, uint64_t width, uint32_t *out_offset)
{
    if (address >= UINT64_C(0x80000000)
        && address + width <= UINT64_C(0x80040000)) {
        *out_offset = (uint32_t)(address - UINT64_C(0x80000000));
        return 1;
    }
    return 0;
}
#include "p15_mmio_extension_v1.c"

int main(void)
{
    uint64_t value = 0;
    int status;
    status = p15_mmio_read(P15_TIMER1_COUNT, 32u, &value);
    printf("timer_read0=%d,0x%08x\n", status, (unsigned)value);
    status = p15_mmio_read(P15_TIMER1_COUNT, 32u, &value);
    printf("timer_read1=%d,0x%08x\n", status, (unsigned)value);
    printf("timer_count=0x%08x reads=%llu\n", p15_timer1_count(),
           (unsigned long long)p15_timer1_reads());
    printf("timer_read16=%d\n", p15_mmio_read(P15_TIMER1_COUNT, 16u, &value));
    printf("timer_write_count=%d\n", p15_mmio_write(P15_TIMER1_COUNT, 32u, 0u));
    printf("mode_read=%d\n", p15_mmio_read(P15_TIMER1_MODE, 32u, &value));
    printf("mode_bad=%d\n", p15_mmio_write(P15_TIMER1_MODE, 32u, 0u));
    printf("mode_good=%d\n", p15_mmio_write(P15_TIMER1_MODE, 32u, 0x107u));
    printf("mode=0x%08x writes=%llu\n", p15_timer1_mode(),
           (unsigned long long)p15_timer1_mode_writes());
    status = p15_virtual_time_read(P15_FRAME_TICK, 32u, &value);
    printf("frame0=%d,0x%08x\n", status, (unsigned)value);
    status = p15_virtual_time_read(P15_FRAME_TICK, 32u, &value);
    printf("frame1=%d,0x%08x\n", status, (unsigned)value);
    printf("frame_value=0x%08x reads=%llu memory_reads=%llu\n",
           p15_frame_tick_value(), (unsigned long long)p15_frame_tick_reads(),
           (unsigned long long)g_p9_memory_reads);
    printf("frame_width16=%d\n", p15_virtual_time_read(P15_FRAME_TICK, 16u, &value));
    printf("frame_unknown=%d\n", p15_virtual_time_read(0x8002967cu, 32u, &value));
    printf("denied=%llu unsupported=%llu\n",
           (unsigned long long)g_p9_denied_accesses,
           (unsigned long long)p15_mmio_unsupported());
    return 0;
}
"""

EXPECTED = """timer_read0=0,0x00000000
timer_read1=0,0x00000107
timer_count=0x0000020e reads=2
timer_read16=2
timer_write_count=13
mode_read=13
mode_bad=13
mode_good=0
mode=0x00000107 writes=1
frame0=0,0x00000001
frame1=0,0x00000002
frame_value=0x00000002 reads=2 memory_reads=2
frame_width16=2
frame_unknown=-1000
denied=5 unsupported=5
"""


def run_harness() -> str:
    with tempfile.TemporaryDirectory() as temp:
        workspace = pathlib.Path(temp)
        source = workspace / "timer_harness.c"
        source.write_text(HARNESS, encoding="utf-8", newline="\n")
        executable = workspace / "timer_harness.exe"
        compiled = subprocess.run(
            ["clang", "-std=c11", "-Wall", "-Wextra", "-O0",
             f"-I{FRAGMENT.parent}", str(source), "-o", str(executable)],
            capture_output=True, text=True,
        )
        if compiled.returncode != 0:
            raise AssertionError(f"compile failed: {compiled.stderr.strip()}")
        executed = subprocess.run([str(executable)], capture_output=True, text=True)
        if executed.returncode != 0:
            raise AssertionError(f"harness failed: {executed.stderr.strip()}")
        return executed.stdout


def live_build(root: pathlib.Path, stage: str = STAGE) -> tuple[dict, dict, object]:
    p15_a0 = (0x13, 0x72)
    p15_b0 = surface.P15_B0
    private = analysis_mod.build_phase15_private(
        p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT,
        extra_a0=surface.EXTRA_A0, extra_c0=surface.EXTRA_C0,
        extra_b0=surface.EXTRA_B0, p14_b0=surface.P14_B0,
        p14_a0=surface.P14_A0, p15_a0=p15_a0, p15_b0=p15_b0,
        internal_targets=surface.INTERNAL_TARGETS,
    )
    image = private["image"]
    build_set = emission.build_build_set(
        private["result_b"], private["base"], private["contract"], private["flat"],
        image.file_sha256, sites=private["sites_b"], trace=True,
        guarded_resolved_indirect=True, extra_a0=surface.EXTRA_A0,
        extra_c0=surface.EXTRA_C0, extra_b0=surface.EXTRA_B0,
        p14_b0=surface.P14_B0, p14_a0=surface.P14_A0,
        p15_a0=p15_a0, p15_b0=p15_b0,
    )
    built = native.build_native(
        build_set, root / f".openrecomp-phase15/build/{stage}/{stage.lower()}",
        fixture_id=stage.lower(), run_count=2,
    )
    executed = trace.run_program(
        built["executables"][0], budget=8_000_000,
        block_budget=surface.FRONTIER_BLOCK_BUDGET, timeout=600,
    )
    return built, executed, image


def timer_values(simple: dict[str, str]) -> list[int]:
    values = []
    for index in range(int(simple.get("p15_mmio_events", "0"))):
        encoded = simple.get(f"p15_mmio_{index}", "")
        address, width, is_write, value = encoded.split(",")
        if int(address, 16) == contract.TIMER1_COUNT and int(width) == 32 \
                and int(is_write) == 0:
            values.append(int(value, 16))
    return values


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    model = contract.MmioModel()
    gate.check("model:timer-read0", model.read(contract.TIMER1_COUNT, 32) == (0, 0),
               str(model.timer1_count))
    gate.check("model:timer-read1", model.read(contract.TIMER1_COUNT, 32) == (0, 263),
               str(model.timer1_count))
    gate.check("model:timer-step", model.timer1_count == 526, str(model.timer1_count))
    gate.check("model:mode-good", model.write(contract.TIMER1_MODE, 32, 0x107) == 0,
               str(model.timer1_mode))
    gate.check("model:mode-bad",
               model.write(contract.TIMER1_MODE, 32, 0) == contract.STATUS_OPERATION_UNSUPPORTED,
               "wrong mode refused")
    gate.check("model:timer-write-refused",
               model.write(contract.TIMER1_COUNT, 32, 0) == contract.STATUS_OPERATION_UNSUPPORTED,
               "counter write refused")

    harness = run_harness()
    gate.check("c:harness", harness.replace("\r\n", "\n") == EXPECTED,
               harness.replace("\r\n", "|").strip())

    built, executed, image = live_build(root)
    simple = executed["simple"]
    values = timer_values(simple)
    gate.check("live:build", built["build_status"] == ["OK", "OK"],
               str(built["build_status"]))
    gate.check("live:build-reproducible", built["build_reproducible"],
               built["executable_sha256"])
    gate.check("live:stderr-empty", executed["stderr_bytes"] == 0,
               str(executed["stderr_bytes"]))
    gate.check("live:timer-reads", int(simple.get("p15_timer1_reads", "0")) >= 2,
               simple.get("p15_timer1_reads"))
    gate.check("live:timer-sequence", len(values) >= 2
               and all(((b - a) & 0xFFFFFFFF) == 263 for a, b in zip(values, values[1:])),
               str(values[:8]))
    gate.check("live:mode-107", simple.get("p15_timer1_mode") == "0x00000107",
               simple.get("p15_timer1_mode"))
    gate.check("live:mode-writes", int(simple.get("p15_timer1_mode_writes", "0")) > 0,
               simple.get("p15_timer1_mode_writes"))
    gate.check("live:frame-tick-progress",
               int(simple.get("p15_frame_tick_reads", "0")) > 0
               and int(simple.get("p15_frame_tick_value", "0"), 16) > 0,
               f"{simple.get('p15_frame_tick_reads')}:{simple.get('p15_frame_tick_value')}")
    gate.check("live:no-unsupported", simple.get("p15_mmio_unsupported") == "0",
               simple.get("p15_mmio_unsupported"))

    observation = {
        "schema": "openrecomp-phase15-timer1-virtual-time-v1",
        "stage": STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "fixture": {"sha256": image.file_sha256, "size": image.file_size},
        "build": {"status": built["build_status"],
                  "executable_sha256": built["executable_sha256"],
                  "toolchain": built["toolchain"]},
        "run": {"stdout_sha256": executed["stdout_sha256"],
                "block_budget": surface.FRONTIER_BLOCK_BUDGET,
                "access_budget": 8_000_000,
                "failed": simple.get("failed"), "error": simple.get("error"),
                "trace_failure_count": simple.get("trace_failure_count")},
        "timer1": {
            "counter_address": "0x1f801110", "mode_address": "0x1f801114",
            "counter_step": 263, "mode": simple.get("p15_timer1_mode"),
            "reads": simple.get("p15_timer1_reads"),
            "mode_writes": simple.get("p15_timer1_mode_writes"),
            "sampled_values": values[:16],
        },
        "frame_tick": {
            "address": "0x80029678",
            "reads": simple.get("p15_frame_tick_reads"),
            "final_value": simple.get("p15_frame_tick_value"),
            "progression": "one per bounds-checked poll",
        },
        "timer1_irq_delivery": "NOT_MODELED_NOT_REQUIRED",
        "cpu_interrupt_delivery": "NOT_MODELED_NOT_REQUIRED",
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "timer1_virtual_time.json", observation)
    assert_public_safe(gate, "timer1", observation, image.payload)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1", "stage": STAGE,
        "status": "PASS", "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "markers": {TIMER1_VIRTUAL_TIME_MARKER: "PASS",
                    "OPENRECOMP_P15_06": "PASS"},
        "next_stage": "P15-07",
    })
    gate.mark(TIMER1_VIRTUAL_TIME_MARKER)
    gate.mark("OPENRECOMP_P15_06")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-06"))
