#!/usr/bin/env python3
"""Deterministic P15-07 bounded GPUSTAT status-model gate."""

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

from tools import test_phase15_timer1_virtual_time_v1 as p15_06  # noqa: E402
from p15_contracts_v1 import GPUSTAT_MARKER  # noqa: E402
from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
import p15_mmio_contract_v1 as contract  # noqa: E402
import p15_surface_v1 as surface  # noqa: E402

STAGE = "P15-07"
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
    int status = p15_mmio_read(P15_GPUSTAT, 32u, &value);
    printf("read32=%d,0x%08x\n", status, (unsigned)value);
    printf("reads=%llu ready_cmd=%u ready_dma=%u\n",
           (unsigned long long)p15_gpustat_reads(),
           (unsigned)((value >> 26u) & 1u),
           (unsigned)((value >> 22u) & 1u));
    printf("read16=%d\n", p15_mmio_read(P15_GPUSTAT, 16u, &value));
    printf("write=%d\n", p15_mmio_write(P15_GPUSTAT, 32u, 0u));
    printf("unknown=%d\n", p15_mmio_read(0x1f801818u, 32u, &value));
    printf("denied=%llu unsupported=%llu\n",
           (unsigned long long)g_p9_denied_accesses,
           (unsigned long long)p15_mmio_unsupported());
    return 0;
}
"""

EXPECTED = """read32=0,0x14802000
reads=1 ready_cmd=1 ready_dma=0
read16=2
write=-1000
unknown=-1000
denied=1 unsupported=1
"""


def run_harness() -> str:
    with tempfile.TemporaryDirectory() as temp:
        workspace = pathlib.Path(temp)
        source = workspace / "gpustat_harness.c"
        source.write_text(HARNESS, encoding="utf-8", newline="\n")
        executable = workspace / "gpustat_harness.exe"
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


def gpustat_events(simple: dict[str, str]) -> list[int]:
    values: list[int] = []
    for index in range(int(simple.get("p15_mmio_events", "0"))):
        encoded = simple.get(f"p15_mmio_{index}", "")
        address, width, is_write, value = encoded.split(",")
        if (int(address, 16) == contract.GPUSTAT and int(width) == 32
                and int(is_write) == 0):
            values.append(int(value, 16))
    return values


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    model = contract.MmioModel()
    gate.check("model:read", model.read(contract.GPUSTAT, 32)
               == (contract.STATUS_OK, contract.GPUSTAT_VALUE),
               f"0x{contract.GPUSTAT_VALUE:08x}")
    gate.check("model:counter", model.gpustat_reads == 1,
               str(model.gpustat_reads))
    gate.check("model:width-refused", model.read(contract.GPUSTAT, 16)[0]
               == contract.STATUS_WIDTH_UNSUPPORTED, "16-bit refused")
    gate.check("model:write-falls-through", model.write(contract.GPUSTAT, 32, 0)
               == contract.STATUS_UNHANDLED, "GP1 write not intercepted")

    harness = run_harness()
    gate.check("c:harness", harness.replace("\r\n", "\n") == EXPECTED,
               harness.replace("\r\n", "|").strip())

    built, executed, image = p15_06.live_build(root, STAGE)
    simple = executed["simple"]
    events = gpustat_events(simple)
    reads = int(simple.get("p15_gpustat_reads", "0"))
    gate.check("live:build", built["build_status"] == ["OK", "OK"],
               str(built["build_status"]))
    gate.check("live:build-reproducible", built["build_reproducible"],
               built["executable_sha256"])
    gate.check("live:stderr-empty", executed["stderr_bytes"] == 0,
               str(executed["stderr_bytes"]))
    gate.check("live:reads", reads > 0, str(reads))
    gate.check("live:event-value", bool(events)
               and all(value == contract.GPUSTAT_VALUE for value in events),
               str([f"0x{value:08x}" for value in events[:8]]))
    gate.check("live:ready-command", bool(contract.GPUSTAT_VALUE & (1 << 26)),
               "bit26=1")
    gate.check("live:dma-request-clear", not (contract.GPUSTAT_VALUE & (1 << 22)),
               "bit22=0")
    gate.check("live:no-unsupported", simple.get("p15_mmio_unsupported") == "0",
               simple.get("p15_mmio_unsupported"))

    observation = {
        "schema": "openrecomp-phase15-gpustat-v1",
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
        "gpustat": {"address": "0x1f801814", "width_bits": 32,
                    "value": "0x14802000", "reads": reads,
                    "recorded_events": len(events),
                    "ready_for_command_bit26": 1,
                    "dma_request_bit22": 0},
        "gpu_command_execution": "NOT_MODELED_NOT_REQUIRED",
        "gpu_rasterization": "NOT_MODELED_NOT_REQUIRED",
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "gpustat.json", observation)
    assert_public_safe(gate, "gpustat", observation, image.payload)
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1", "stage": STAGE,
        "status": "PASS", "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "markers": {GPUSTAT_MARKER: "PASS", "OPENRECOMP_P15_07": "PASS"},
        "next_stage": "P15-08",
    })
    gate.mark(GPUSTAT_MARKER)
    gate.mark("OPENRECOMP_P15_07")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-07"))
