#!/usr/bin/env python3
"""Deterministic P15-04 SYS_CONTROL and DMA2 register-state gate."""

from __future__ import annotations

import collections
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src", ".openrecomp-phase15/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p11_native_v1 as native  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402

from p15_contracts_v1 import DMA2_REGISTER_STATE_MARKER, SYS_CONTROL_MARKER  # noqa: E402
from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
import p15_analysis_v1 as analysis_mod  # noqa: E402
import p15_emission_v1 as emission  # noqa: E402
import p15_mmio_contract_v1 as contract  # noqa: E402
import p15_surface_v1 as surface  # noqa: E402
import p15_trace_v1 as trace  # noqa: E402

STAGE = "P15-04"


def build_and_run_once(root: pathlib.Path) -> dict:
    private = analysis_mod.build_phase15_private(
        p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT,
        extra_a0=surface.EXTRA_A0, extra_c0=surface.EXTRA_C0,
        extra_b0=surface.EXTRA_B0, p14_b0=surface.P14_B0,
        p14_a0=surface.P14_A0, internal_targets=surface.INTERNAL_TARGETS,
    )
    image = private["image"]
    build_set = emission.build_build_set(
        private["result_b"], private["base"], private["contract"], private["flat"],
        image.file_sha256, sites=private["sites_b"], trace=True,
        guarded_resolved_indirect=True, extra_a0=surface.EXTRA_A0,
        extra_c0=surface.EXTRA_C0, extra_b0=surface.EXTRA_B0,
        p14_b0=surface.P14_B0, p14_a0=surface.P14_A0,
    )
    built = native.build_native(
        build_set, root / ".openrecomp-phase15/build/P15-04/p15-04",
        fixture_id="p15-04", run_count=2,
    )
    executed = trace.run_program(
        built["executables"][0], budget=p11_05.ACCESS_BUDGET,
        block_budget=surface.FRONTIER_BLOCK_BUDGET, timeout=600,
    )
    return {"private": private, "image": image, "build_set": build_set,
            "built": built, "executed": executed}


def parse_events(simple: dict[str, str]) -> list[dict[str, int]]:
    count = int(simple.get("p15_mmio_events", "0"))
    events = []
    for index in range(count):
        address, width, is_write, value = simple[f"p15_mmio_{index}"].split(",")
        events.append({"address": int(address, 16), "width_bits": int(width),
                       "is_write": int(is_write), "value": int(value, 16)})
    return events


def has(events: list[dict[str, int]], address: int, is_write: int,
        value: int | None = None) -> bool:
    return any(
        item["address"] == address and item["width_bits"] == 32
        and item["is_write"] == is_write
        and (value is None or item["value"] == value)
        for item in events
    )


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    model = contract.MmioModel()
    gate.check("sys:write", model.write(contract.SYS_CONTROL, 32, 0x1325) == 0
               and model.sys_control == 0x1325, f"{model.sys_control:#x}")
    gate.check("sys:read", model.read(contract.SYS_CONTROL, 32) == (0, 0x1325),
               str(model.read(contract.SYS_CONTROL, 32)))
    gate.check("sys:width16-refused",
               model.write(contract.SYS_CONTROL, 16, 0) == contract.STATUS_WIDTH_UNSUPPORTED,
               "16-bit refused")
    gate.check("dma:dpcr", model.write(contract.DPCR, 32, 0x33333333) == 0
               and model.read(contract.DPCR, 32) == (0, 0x33333333),
               f"{model.dpcr:#x}")
    gate.check("dma:dicr", model.write(contract.DICR, 32, 0) == 0
               and model.read(contract.DICR, 32) == (0, 0), f"{model.dicr:#x}")
    gate.check("dma:madr", model.write(contract.D2_MADR, 32, 0x80029834) == 0
               and model.read(contract.D2_MADR, 32) == (0, 0x80029834),
               f"{model.d2_madr:#x}")
    gate.check("dma:bcr", model.write(contract.D2_BCR, 32, 0x01000010) == 0
               and model.read(contract.D2_BCR, 32) == (0, 0x01000010),
               f"{model.d2_bcr:#x}")
    gate.check("dma:chcr-synchronous-completion",
               model.write(contract.D2_CHCR, 32, 0x01000401) == 0
               and model.read(contract.D2_CHCR, 32) == (0, 0x00000401),
               f"{model.d2_chcr:#x}")
    for address in (contract.DPCR, contract.DICR, contract.D2_MADR,
                    contract.D2_BCR, contract.D2_CHCR):
        gate.check(f"dma:width16-refused:{address:08x}",
                   model.read(address, 16)[0] == contract.STATUS_WIDTH_UNSUPPORTED,
                   "16-bit refused")

    live = build_and_run_once(root)
    built, executed, simple = live["built"], live["executed"], live["executed"]["simple"]
    events = parse_events(simple)
    gate.check("live:build", built["build_status"] == ["OK", "OK"],
               str(built["build_status"]))
    gate.check("live:build-reproducible", built["build_reproducible"],
               built["executable_sha256"])
    gate.check("live:stderr-empty", executed["stderr_bytes"] == 0,
               str(executed["stderr_bytes"]))
    gate.check("live:sys-write-1325", has(events, contract.SYS_CONTROL, 1, 0x1325),
               "0x1325 observed")
    gate.check("live:dpcr-write", has(events, contract.DPCR, 1, 0x33333333),
               "0x33333333 observed")
    gate.check("live:dicr-write", has(events, contract.DICR, 1, 0),
               "zero observed")
    gate.check("live:d2-madr-write", has(events, contract.D2_MADR, 1),
               "MADR observed")
    gate.check("live:d2-bcr-write", has(events, contract.D2_BCR, 1),
               "BCR observed")
    gate.check("live:d2-chcr-start",
               any(item["address"] == contract.D2_CHCR and item["is_write"] == 1
                   and item["value"] & contract.D2_CHCR_BUSY for item in events),
               "busy/start write observed")
    gate.check("live:d2-chcr-read-idle",
               any(item["address"] == contract.D2_CHCR and item["is_write"] == 0
                   and not (item["value"] & contract.D2_CHCR_BUSY) for item in events),
               "read observes busy clear")
    gate.check("live:no-width-failure", simple.get("p15_mmio_unsupported") == "0",
               simple.get("p15_mmio_unsupported"))

    relevant = [item for item in events if item["address"] in {
        contract.SYS_CONTROL, contract.DPCR, contract.DICR, contract.D2_MADR,
        contract.D2_BCR, contract.D2_CHCR,
    }]
    counts = collections.Counter(
        (item["address"], item["width_bits"], item["is_write"]) for item in relevant
    )
    observation = {
        "schema": "openrecomp-phase15-sys-control-dma2-v1",
        "stage": STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "fixture": {"sha256": live["image"].file_sha256,
                    "size": live["image"].file_size},
        "build": {"status": built["build_status"],
                  "executable_sha256": built["executable_sha256"],
                  "toolchain": built["toolchain"],
                  "source_hashes": live["build_set"]["hashes"]},
        "run": {"stdout_sha256": executed["stdout_sha256"],
                "stderr_empty": executed["stderr_bytes"] == 0,
                "block_budget": surface.FRONTIER_BLOCK_BUDGET},
        "event_counts": {
            f"0x{address:08x}:{width}:{'write' if is_write else 'read'}": count
            for (address, width, is_write), count in sorted(counts.items())
        },
        "events": relevant,
        "final_state": {
            "sys_control": simple.get("p15_sys_control"),
            "d2_madr": simple.get("p15_d2_madr"),
            "d2_bcr": simple.get("p15_d2_bcr"),
            "d2_chcr": simple.get("p15_d2_chcr"),
            "dpcr": simple.get("p15_dpcr"),
            "dicr": simple.get("p15_dicr"),
        },
        "asynchronous_dma_timing": "NOT_MODELED",
        "gpu_command_execution": "NOT_MODELED",
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "sys_control_dma2.json", observation)
    assert_public_safe(gate, "sys-control-dma2", observation, live["image"].payload)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1", "stage": STAGE,
        "status": "PASS", "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "markers": {SYS_CONTROL_MARKER: "PASS",
                    DMA2_REGISTER_STATE_MARKER: "PASS",
                    "OPENRECOMP_P15_04": "PASS"},
        "next_stage": "P15-05",
    })
    gate.mark(SYS_CONTROL_MARKER)
    gate.mark(DMA2_REGISTER_STATE_MARKER)
    gate.mark("OPENRECOMP_P15_04")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-04"))
