#!/usr/bin/env python3
"""Deterministic P15-02 live I_STAT/I_MASK production-integration gate.

Builds the real private-fixture generated host program through the canonical
Phase-15 composition, runs two bounded native copies, and proves that every
execution-reached I_STAT/I_MASK access is handled by the additive model before
the frozen fail-closed platform boundary. Only non-reconstructive metadata is
committed.
"""

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

from p15_contracts_v1 import I_STAT_I_MASK_MARKER  # noqa: E402
from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402

import p15_emission_v1 as emission  # noqa: E402
import p15_probe_v1 as probe  # noqa: E402
import p15_surface_v1 as surface  # noqa: E402

STAGE = "P15-02"


def parse_mmio_events(simple: dict[str, str]) -> list[dict[str, int]]:
    count = int(simple.get("p15_mmio_events", "0"))
    events: list[dict[str, int]] = []
    for index in range(count):
        encoded = simple.get(f"p15_mmio_{index}")
        if encoded is None:
            raise AssertionError(f"missing p15_mmio_{index}")
        address, width, is_write, value = encoded.split(",")
        events.append({
            "address": int(address, 16),
            "width_bits": int(width),
            "is_write": int(is_write),
            "value": int(value, 16),
        })
    return events


def denial_inventory(nonram: dict[str, int]) -> list[dict[str, int]]:
    inventory: list[dict[str, int]] = []
    for signature, count in sorted(nonram.items()):
        address, width, is_write, denied = signature.split(":")
        if int(address, 16) not in (0x1F801070, 0x1F801074):
            continue
        inventory.append({
            "address": int(address, 16),
            "width_bits": int(width),
            "is_write": int(is_write),
            "denied": int(denied),
            "count": int(count),
        })
    return inventory


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    result = probe.build_and_run(
        root / ".openrecomp-phase15/build/P15-02", "p15-02",
        block_budget=surface.FRONTIER_BLOCK_BUDGET,
    )
    first, second = result["first"], result["second"]
    simple = result["simple"]
    gate.check("production:build",
               all(item == "OK" for item in result["built"]["build_status"]),
               str(result["built"]["build_status"]))
    gate.check("production:build-reproducible",
               bool(result["built"]["build_reproducible"]),
               result["built"]["executable_sha256"])
    gate.check("production:stdout-identical", probe.deterministic_match(result),
               first["stdout_sha256"])
    gate.check("production:stderr-empty",
               first["stderr_bytes"] == 0 and second["stderr_bytes"] == 0,
               f"{first['stderr_bytes']}:{second['stderr_bytes']}")

    support = result["build_set"]["files"][emission.SUPPORT_NAME]
    read_hook = "int p15_status = p15_mmio_read(address, width_bits, out_value);"
    write_hook = "int p15_status = p15_mmio_write(address, width_bits, value);"
    frozen_read_blocker = (
        "if (address == (uint64_t)P9_I_STAT || address == (uint64_t)P9_I_MASK)"
    )
    gate.check("composition:read-predispatch", support.count(read_hook) == 1,
               str(support.count(read_hook)))
    gate.check("composition:write-predispatch", support.count(write_hook) == 1,
               str(support.count(write_hook)))
    gate.check("composition:before-frozen-blocker",
               support.index(read_hook) < support.index(frozen_read_blocker)
               and support.index(write_hook) < support.rindex(frozen_read_blocker),
               "Phase-15 hooks precede frozen blockers")

    events = parse_mmio_events(simple)
    signatures = collections.Counter(
        (event["address"], event["width_bits"], event["is_write"])
        for event in events
    )
    gate.check("live:i-mask-read16", signatures[(0x1F801074, 16, 0)] > 0,
               str(signatures[(0x1F801074, 16, 0)]))
    gate.check("live:i-mask-write16", signatures[(0x1F801074, 16, 1)] > 0,
               str(signatures[(0x1F801074, 16, 1)]))
    gate.check("live:i-stat-read16", signatures[(0x1F801070, 16, 0)] > 0,
               str(signatures[(0x1F801070, 16, 0)]))
    gate.check("live:i-stat-write16", signatures[(0x1F801070, 16, 1)] > 0,
               str(signatures[(0x1F801070, 16, 1)]))
    gate.check("live:i-mask-init-zero",
               any(event == {"address": 0x1F801074, "width_bits": 16,
                             "is_write": 1, "value": 0} for event in events),
               "observed write 0")
    gate.check("live:i-stat-ack-zero",
               any(event == {"address": 0x1F801070, "width_bits": 16,
                             "is_write": 1, "value": 0} for event in events),
               "observed write 0")
    gate.check("live:no-mmio-width-failure",
               simple.get("p15_mmio_unsupported") == "0",
               simple.get("p15_mmio_unsupported"))

    interrupt_inventory = denial_inventory(first["parsed"].get("nonram", {}))
    gate.check("live:interrupt-accesses-in-inventory", bool(interrupt_inventory),
               str(len(interrupt_inventory)))
    gate.check("live:historical-interrupt-denials-eliminated",
               all(item["denied"] == 0 for item in interrupt_inventory),
               str(interrupt_inventory))

    observation = {
        "schema": "openrecomp-phase15-live-i-stat-i-mask-v1",
        "stage": STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "fixture": {
            "sha256": result["image"].file_sha256,
            "size": result["image"].file_size,
        },
        "build": {
            "status": result["built"]["build_status"],
            "reproducible": result["built"]["build_reproducible"],
            "executable_sha256": result["built"]["executable_sha256"],
            "toolchain": result["built"]["toolchain"],
            "source_hashes": result["build_set"]["hashes"],
            "runtime_composed_sha256": result["build_set"]["runtime_composition"]["composed_sha256"],
        },
        "runs": {
            "run1_sha256": first["stdout_sha256"],
            "run2_sha256": second["stdout_sha256"],
            "byte_identical": probe.deterministic_match(result),
            "stderr_empty": first["stderr_bytes"] == 0 and second["stderr_bytes"] == 0,
            "block_budget": surface.FRONTIER_BLOCK_BUDGET,
        },
        "interrupt_access_inventory": interrupt_inventory,
        "model_event_counts": {
            f"0x{address:08x}:{width}:{'write' if is_write else 'read'}": count
            for (address, width, is_write), count in sorted(signatures.items())
            if address in (0x1F801070, 0x1F801074)
        },
        "model": {
            "i_stat": simple.get("p15_i_stat"),
            "i_mask": simple.get("p15_i_mask"),
            "reads": simple.get("p15_mmio_reads"),
            "writes": simple.get("p15_mmio_writes"),
            "unsupported": simple.get("p15_mmio_unsupported"),
            "transcript_digest": simple.get("p15_mmio_digest"),
        },
        "first_remaining_runtime_failure": result["failure"],
        "historical_i_mask_denials_eliminated": True,
        "cpu_interrupt_delivery": "NOT_REQUIRED_NOW",
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "live_i_stat_i_mask.json", observation)
    assert_public_safe(gate, "live-i-stat-i-mask", observation,
                       result["image"].payload)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1", "stage": STAGE,
        "status": "PASS", "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "markers": {I_STAT_I_MASK_MARKER: "PASS", "OPENRECOMP_P15_02": "PASS"},
        "next_stage": "P15-03",
    })
    gate.mark(I_STAT_I_MASK_MARKER)
    gate.mark("OPENRECOMP_P15_02")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-02"))
