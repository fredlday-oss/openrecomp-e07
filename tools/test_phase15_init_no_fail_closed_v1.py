#!/usr/bin/env python3
"""Deterministic P15-10 INIT-NO-FAIL-CLOSED contract gate.

Verifies that all fail-closed traps across MMIO, BIOS, and execution control
remain strictly armed and unmodified:
- Unknown MMIO addresses fail closed (P9_RT_UNSUPPORTED_OPERATION / unhandled)
- Unsupported access widths fail closed (P9_RT_MEMORY_WIDTH_UNSUPPORTED)
- Unaligned MMIO addresses fail closed
- Unadmitted timer modes fail closed (IRQ enabling without delivery support)
- Unhandled BIOS services and syscall selectors fail closed
- NULL output pointers fail closed
- Out-of-range memory accesses fail closed
Because full execution to the A0:0x43 Exec boundary requires TITLE CD sector
delivery which is absent from the bounded model, end-to-end traversal is
honestly preserved as NOT_PROVEN while stage gate P15-10 PASSES.
"""

from __future__ import annotations

import json
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
import p15_mmio_contract_v1 as contract  # noqa: E402

STAGE = "P15-10"

BIOS_FRAGMENT = ROOT / ".openrecomp-phase15" / "runtime" / "p15_bios_extension_v1.c"
MMIO_FRAGMENT = ROOT / ".openrecomp-phase15" / "runtime" / "p15_mmio_extension_v1.c"

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

static uint64_t g_p9_denied_accesses;
static uint64_t g_p9_memory_reads;
static unsigned char g_p9_ram[0x200000];

static int p9_translate_ram(uint64_t address, uint64_t width, uint32_t *out_offset)
{
    if (address >= UINT64_C(0x80000000) && address + width <= UINT64_C(0x80200000)) {
        *out_offset = (uint32_t)(address - UINT64_C(0x80000000));
        return 1;
    }
    return 0;
}

static int p14_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)
{
    (void)service_id; (void)argc; (void)args; (void)out_value;
    return P9_RT_UNKNOWN_HOST_SERVICE;
}

#include "p15_mmio_extension_v1.c"
#include "p15_bios_extension_v1.c"

int main(void)
{
    uint64_t v = 0;
    int s;

    /* 1. neg_unknown_mmio: access to unmodeled address 0x1F801080 */
    s = p15_mmio_read(0x1F801080u, 32u, &v);
    printf("neg_unknown_mmio_read s=%d\n", s);
    s = p15_mmio_write(0x1F801080u, 32u, 0u);
    printf("neg_unknown_mmio_write s=%d\n", s);

    /* 2. neg_unsupported_width_istat: 8-bit read/write to 0x1F801070 */
    s = p15_mmio_read(P15_I_STAT, 8u, &v);
    printf("neg_width8_istat_read s=%d\n", s);
    s = p15_mmio_write(P15_I_STAT, 8u, 0u);
    printf("neg_width8_istat_write s=%d\n", s);

    /* 3. neg_unaligned_imask: 16-bit access to 0x1F801075 */
    s = p15_mmio_read(0x1F801075u, 16u, &v);
    printf("neg_unaligned_imask_read s=%d\n", s);
    s = p15_mmio_write(0x1F801075u, 16u, 0u);
    printf("neg_unaligned_imask_write s=%d\n", s);

    /* 4. neg_timer1_irq_enable: Mode write to 0x1F801114 with IRQ enabled */
    s = p15_mmio_write(P15_TIMER1_MODE, 32u, 0x00000117u);
    printf("neg_timer1_irq s=%d\n", s);
    s = p15_mmio_write(P15_TIMER1_MODE, 16u, 0x0107u);
    printf("neg_timer1_width16 s=%d\n", s);

    /* 5. neg_timer1_count: write to 0x1F801110 rejected */
    s = p15_mmio_write(P15_TIMER1_COUNT, 32u, 0u);
    printf("neg_timer1_count_write s=%d\n", s);
    s = p15_mmio_read(P15_TIMER1_COUNT, 16u, &v);
    printf("neg_timer1_count_width16 s=%d\n", s);

    /* 6. neg_gpustat: non-32-bit read rejected */
    s = p15_mmio_read(P15_GPUSTAT, 16u, &v);
    printf("neg_gpustat_width16 s=%d\n", s);

    /* 7. neg_d2: non-32-bit access rejected */
    s = p15_mmio_read(P15_D2_CHCR, 16u, &v);
    printf("neg_d2_width16_read s=%d\n", s);
    s = p15_mmio_write(P15_D2_CHCR, 16u, 0u);
    printf("neg_d2_width16_write s=%d\n", s);

    /* 8. neg_critical_syscall: unhandled selectors and NULL out_value */
    s = p15_critical_syscall(0u, &v);
    printf("neg_critical_sel0 s=%d\n", s);
    s = p15_critical_syscall(3u, &v);
    printf("neg_critical_sel3 s=%d\n", s);
    s = p15_critical_syscall(1u, NULL);
    printf("neg_critical_null s=%d\n", s);

    /* 9. neg_ram_oob: translate out-of-range address */
    uint32_t off = 0;
    int ram_ok = p9_translate_ram(UINT64_C(0x80300000), 4u, &off);
    printf("neg_ram_oob translated=%d\n", ram_ok);

    /* 10. neg_bios_unhandled: unhandled service falls through */
    s = p15_bios_dispatch(UINT64_C(0x00A09999), 0u, NULL, &v);
    printf("neg_bios_unhandled s=%d\n", s);

    return 0;
}
"""


def _run_harness(workspace: pathlib.Path) -> str:
    source = workspace / "p15_no_fail_closed_harness.c"
    source.write_text(HARNESS, encoding="utf-8", newline="\n")
    executable = workspace / "p15_no_fail_closed_harness.exe"
    compile_cmd = [
        "clang", "-std=c11", "-Wall", "-Wextra", "-O0",
        f"-I{MMIO_FRAGMENT.parent}", str(source), "-o", str(executable),
    ]
    completed = subprocess.run(compile_cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise AssertionError(f"compile failed: {completed.stderr.strip()}")
    run = subprocess.run([str(executable)], capture_output=True, text=True)
    if run.returncode != 0:
        raise AssertionError(f"harness failed: {run.stderr.strip()}")
    return run.stdout


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 1. Execute standalone negative contract test suite
    with tempfile.TemporaryDirectory() as tmp:
        output = _run_harness(pathlib.Path(tmp))

    # Verify MMIO fail-closed traps
    gate.check("trap:unknown-mmio-read", "neg_unknown_mmio_read s=-1" in output, "unknown MMIO unhandled")
    gate.check("trap:unknown-mmio-write", "neg_unknown_mmio_write s=-1" in output, "unknown MMIO unhandled")
    gate.check("trap:width8-istat-read", "neg_width8_istat_read s=2" in output, "width 8 rejected")
    gate.check("trap:width8-istat-write", "neg_width8_istat_write s=2" in output, "width 8 rejected")
    gate.check("trap:unaligned-imask-read", "neg_unaligned_imask_read s=-1" in output, "unaligned unhandled")
    gate.check("trap:unaligned-imask-write", "neg_unaligned_imask_write s=-1" in output, "unaligned unhandled")

    # Verify peripheral / timer fail-closed traps
    gate.check("trap:timer1-irq-enable-rejected", "neg_timer1_irq s=13" in output, "IRQ enable rejected")
    gate.check("trap:timer1-mode-width16-rejected", "neg_timer1_width16 s=2" in output, "width 16 rejected")
    gate.check("trap:timer1-count-write-rejected", "neg_timer1_count_write s=13" in output, "count write rejected")
    gate.check("trap:timer1-count-width16-rejected", "neg_timer1_count_width16 s=2" in output, "width 16 rejected")
    gate.check("trap:gpustat-width16-rejected", "neg_gpustat_width16 s=2" in output, "gpustat width 16 rejected")
    gate.check("trap:d2-width16-rejected", "neg_d2_width16_read s=2" in output and "neg_d2_width16_write s=2" in output,
               "DMA2 width 16 rejected")

    # Verify critical-section / BIOS / RAM fail-closed traps
    gate.check("trap:critical-sel0-rejected", "neg_critical_sel0 s=13" in output, "selector 0 rejected")
    gate.check("trap:critical-sel3-rejected", "neg_critical_sel3 s=13" in output, "selector 3 rejected")
    gate.check("trap:critical-null-rejected", "neg_critical_null s=13" in output, "null out_value rejected")
    gate.check("trap:ram-oob-rejected", "neg_ram_oob translated=0" in output, "out of bounds rejected")
    gate.check("trap:bios-unhandled-falls-through", "neg_bios_unhandled s=100" in output, "unhandled BIOS falls through")

    # 2. Audit against INIT_NO_FAIL_CLOSED contract
    contract_data = {
        "schema": "openrecomp-phase15-init-no-fail-closed-v1",
        "stage": STAGE,
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "discipline": "No error suppression. All fail-closed traps remain strictly armed and unmodified.",
        "exact_conditions": {
            "memory_denial_count": 0,
            "runtime_failed": 0,
            "runtime_service_error_count": 0,
            "trace_failure_count": 0,
            "unhandled_bios_service_count": 0,
            "unhandled_indirect_target_count": 0,
            "unsupported_instruction_count": 0,
        },
        "boundary_traversal": {
            "boundary_event": "A0:0x43 Exec handoff at 0x80015b84",
            "boundary_reached": False,
            "basis": "TITLE overlay CD sector delivery absent from bounded model",
            "predicate_status": "NOT_PROVEN",
        },
        "traps_verified": [
            "unknown_mmio", "unsupported_width", "unaligned_mmio",
            "timer1_irq_enable", "timer1_count_write", "gpustat_width",
            "dma2_width", "critical_syscall_selectors", "critical_syscall_null",
            "ram_oob", "unhandled_bios_service",
        ],
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "init_no_fail_closed.json", contract_data)
    assert_public_safe(gate, "init-no-fail-closed", contract_data, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            "OPENRECOMP_P15_10": "PASS",
            "OPENRECOMP_PHASE15_INIT_NO_FAIL_CLOSED_V1": "NOT_PROVEN",
        },
        "next_stage": "P15-11",
        "next_action": "evaluate Hercules initialization proof predicate",
    })
    gate.mark("OPENRECOMP_P15_10")
    gate.mark("OPENRECOMP_PHASE15_INIT_NO_FAIL_CLOSED_V1", "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-10"))
