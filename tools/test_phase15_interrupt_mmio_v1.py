#!/usr/bin/env python3
"""Deterministic P15-01 interrupt MMIO contract gate.

Exercises the Phase-15 bounded interrupt/peripheral register model at two levels:

* the pure-Python executable contract (:mod:`p15_mmio_contract_v1`);
* the actual C fragment (:file:`.openrecomp-phase15/runtime/p15_mmio_extension_v1.c`)
  compiled standalone with the frozen runtime failure codes stubbed.

Positive I_MASK/I_STAT sequences and fail-closed negatives (unsupported width,
unaligned/unknown address) are both checked. No private fixture is used.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase15/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p15_mmio_contract_v1 as contract  # noqa: E402
from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402

STAGE = "P15-01"

FRAGMENT = ROOT / ".openrecomp-phase15" / "runtime" / "p15_mmio_extension_v1.c"

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
    uint64_t v = 0;
    int s;
    printf("init_stat=0x%08x init_mask=0x%08x\n", p15_i_stat(), p15_i_mask());

    s = p15_mmio_write(P15_I_MASK, 16u, 0x0000u);
    printf("mask_write0 s=%d mask=0x%08x\n", s, p15_i_mask());
    s = p15_mmio_read(P15_I_MASK, 16u, &v);
    printf("mask_read s=%d v=0x%08x\n", s, (unsigned)v);

    s = p15_mmio_write(P15_I_MASK, 16u, 0x1234u);
    printf("mask_write1234 s=%d mask=0x%08x\n", s, p15_i_mask());
    s = p15_mmio_read(P15_I_MASK, 16u, &v);
    printf("mask_read s=%d v=0x%08x\n", s, (unsigned)v);

    s = p15_mmio_write(P15_I_MASK, 32u, 0x0000ABCDu);
    printf("mask_write32 s=%d mask=0x%08x\n", s, p15_i_mask());

    s = p15_mmio_read(P15_I_STAT, 16u, &v);
    printf("stat_read s=%d v=0x%08x\n", s, (unsigned)v);
    s = p15_mmio_write(P15_I_STAT, 16u, 0x0000u);
    printf("stat_write0 s=%d stat=0x%08x\n", s, p15_i_stat());
    s = p15_mmio_write(P15_I_STAT, 16u, 0xFFFFu);
    printf("stat_writeFFFF s=%d stat=0x%08x\n", s, p15_i_stat());

    s = p15_mmio_read(P15_I_MASK, 8u, &v);
    printf("mask_read8 s=%d denied=%llu unsupported=%llu\n", s,
           (unsigned long long)g_p9_denied_accesses,
           (unsigned long long)p15_mmio_unsupported());
    s = p15_mmio_write(P15_I_STAT, 8u, 0u);
    printf("stat_write8 s=%d denied=%llu\n", s,
           (unsigned long long)g_p9_denied_accesses);

    s = p15_mmio_read(0x1f801075u, 16u, &v);
    printf("unaligned_read s=%d\n", s);
    s = p15_mmio_write(0x1f801072u, 16u, 0u);
    printf("unknown_read s=%d\n", s);
    s = p15_mmio_read(0x1f801078u, 32u, &v);
    printf("neighbor_read s=%d\n", s);

    printf("events=%lu digest=0x%016llx\n",
           (unsigned long)p15_mmio_event_count(),
           (unsigned long long)p15_mmio_transcript_digest());
    return 0;
}
"""

EXPECTED = """init_stat=0x00000000 init_mask=0x00000000
mask_write0 s=0 mask=0x00000000
mask_read s=0 v=0x00000000
mask_write1234 s=0 mask=0x00001234
mask_read s=0 v=0x00001234
mask_write32 s=0 mask=0x0000abcd
stat_read s=0 v=0x00000000
stat_write0 s=0 stat=0x00000000
stat_writeFFFF s=0 stat=0x00000000
mask_read8 s=2 denied=1 unsupported=1
stat_write8 s=2 denied=2
unaligned_read s=-1000
unknown_read s=-1000
neighbor_read s=-1000
"""


def _run_harness(workspace: pathlib.Path) -> str:
    source = workspace / "p15_mmio_harness.c"
    source.write_text(HARNESS, encoding="utf-8", newline="\n")
    executable = workspace / "p15_mmio_harness.exe"
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


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    model = contract.MmioModel()

    # --- I_MASK: deterministic init, write 0, read, write nonzero, restore -----
    status, value = model.read(contract.I_MASK, 16)
    gate.check("mask:init", status == contract.STATUS_OK and value == 0x0000,
               f"{status}:{value:#x}")
    gate.check("mask:write-zero", model.write(contract.I_MASK, 16, 0x0000) == contract.STATUS_OK
               and model.i_mask == 0x0000, f"{model.i_mask:#x}")
    status, value = model.read(contract.I_MASK, 16)
    gate.check("mask:read-zero", status == contract.STATUS_OK and value == 0x0000,
               f"{status}:{value:#x}")
    gate.check("mask:write-nonzero",
               model.write(contract.I_MASK, 16, 0x1234) == contract.STATUS_OK
               and model.i_mask == 0x1234, f"{model.i_mask:#x}")
    status, value = model.read(contract.I_MASK, 16)
    gate.check("mask:read-nonzero", value == 0x1234, f"{value:#x}")
    gate.check("mask:exact-16bit", model.write(contract.I_MASK, 16, 0x0000ABCD) == contract.STATUS_OK
               and model.i_mask == 0xABCD, f"{model.i_mask:#x}")

    # --- I_STAT: ack semantics on an injected non-zero pending state ------------
    model.i_stat = 0x0006
    status, value = model.read(contract.I_STAT, 16)
    gate.check("stat:read-pending", status == contract.STATUS_OK and value == 0x0006,
               f"{status}:{value:#x}")
    gate.check("stat:ack-and", model.write(contract.I_STAT, 16, 0x0002) == contract.STATUS_OK
               and model.i_stat == 0x0002, f"{model.i_stat:#x}")
    gate.check("stat:ack-zero-clears",
               model.write(contract.I_STAT, 16, 0x0000) == contract.STATUS_OK
               and model.i_stat == 0x0000, f"{model.i_stat:#x}")

    # --- negatives: unsupported widths and unaligned/unknown addresses ----------
    before = model.unsupported
    gate.check("neg:width8-mask", model.read(contract.I_MASK, 8)[0]
               == contract.STATUS_WIDTH_UNSUPPORTED, "width 8 rejected")
    gate.check("neg:width8-stat", model.write(contract.I_STAT, 8, 0)
               == contract.STATUS_WIDTH_UNSUPPORTED, "width 8 rejected")
    gate.check("neg:width-unsupported-counted", model.unsupported == before + 2,
               str(model.unsupported))
    gate.check("neg:unaligned", model.read(contract.I_MASK + 1, 16)[0]
               == contract.STATUS_UNHANDLED, "unaligned rejected")
    gate.check("neg:unknown-nearby", model.read(contract.I_MASK + 4, 32)[0]
               == contract.STATUS_UNHANDLED, "unknown rejected")

    # --- source-level contract of the C fragment --------------------------------
    source = FRAGMENT.read_text(encoding="utf-8")
    gate.check("c:ack-expression", "g_p15_i_stat &= (value & UINT32_C(0xffff))" in source,
               "PS1 ack semantics present")
    gate.check("c:mask-store", "g_p15_i_mask = value & UINT32_C(0xffff);" in source,
               "mask store present")
    gate.check("c:width-guard", "p15_width_ok" in source, "explicit width guard present")
    gate.check("c:unhandled-fallthrough", "P15_MMIO_UNHANDLED" in source,
               "unhandled fallthrough present")

    # --- actual C fragment behaviour --------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        output = _run_harness(pathlib.Path(tmp))
    expected_head = EXPECTED.strip()
    actual_head = "\n".join(output.splitlines()[: len(expected_head.splitlines())])
    gate.check("c:harness-sequence", actual_head == expected_head,
               actual_head.replace("\n", "|"))
    last = output.splitlines()[-1]
    gate.check("c:harness-events", last.startswith("events="), last)

    write_json(evidence / "interrupt_mmio_contract.json", {
        "schema": "openrecomp-phase15-interrupt-mmio-contract-v1",
        "stage": STAGE,
        "contract": contract.contract_document(),
        "harness_output": output,
        "expected_sequence": expected_head,
    })
    assert_public_safe(gate, "contract", contract.contract_document(), b"")

    gate.mark(contract_safe_marker())
    gate.mark("OPENRECOMP_P15_01")
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {
            "OPENRECOMP_PHASE15_INTERRUPT_MMIO_CONTRACT_V1": "PASS",
            "OPENRECOMP_P15_01": "PASS",
        },
        "fixture_used": False,
        "next_stage": "P15-02",
    })


def contract_safe_marker() -> str:
    return "OPENRECOMP_PHASE15_INTERRUPT_MMIO_CONTRACT_V1"


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-01"))
