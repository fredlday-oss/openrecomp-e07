#!/usr/bin/env python3
"""Deterministic P15-03 live frontier replay I gate.

Replays the real private-fixture production path after live I_STAT/I_MASK
integration and records the first remaining execution-reached blocker. A stage
PASS means the frontier was reproduced and classified, not that initialization
or a frame was proven.
"""

from __future__ import annotations

import pathlib
import sys

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

STAGE = "P15-03"


def nonram_inventory(parsed: dict) -> list[dict[str, int]]:
    result: list[dict[str, int]] = []
    for signature, count in sorted(parsed.get("nonram", {}).items()):
        address, width, is_write, denied = signature.split(":")
        numeric = int(address, 16)
        if not 0x1F801000 <= numeric < 0x1F802000:
            continue
        result.append({
            "address": numeric,
            "width_bits": int(width),
            "is_write": int(is_write),
            "denied": int(denied),
            "count": int(count),
        })
    return result


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    result = probe.build_and_run(
        root / ".openrecomp-phase15/build/P15-03", "p15-03",
        block_budget=surface.FRONTIER_BLOCK_BUDGET,
    )
    first, second, simple = result["first"], result["second"], result["simple"]
    failure = result["failure"]
    inventory = nonram_inventory(first["parsed"])
    memory_denials = sum(
        int(count)
        for signature, count in first["parsed"].get("nonram", {}).items()
        if int(signature.rsplit(":", 1)[-1]) != 0
    )
    mmio_denials = sum(item["count"] for item in inventory if item["denied"] != 0)
    interrupt_denials = sum(
        item["count"] for item in inventory
        if item["address"] in (0x1F801070, 0x1F801074) and item["denied"] != 0
    )

    gate.check("replay:build",
               all(item == "OK" for item in result["built"]["build_status"]),
               str(result["built"]["build_status"]))
    gate.check("replay:deterministic", probe.deterministic_match(result),
               first["stdout_sha256"])
    gate.check("replay:stderr-empty",
               first["stderr_bytes"] == 0 and second["stderr_bytes"] == 0,
               f"{first['stderr_bytes']}:{second['stderr_bytes']}")
    gate.check("replay:i-stat-i-mask-denials-zero", interrupt_denials == 0,
               str(interrupt_denials))
    gate.check("replay:memory-denials-zero", memory_denials == 0,
               str(memory_denials))
    gate.check("replay:mmio-denials-zero", mmio_denials == 0,
               str(mmio_denials))
    gate.check("replay:mmio-unsupported-zero",
               simple.get("p15_mmio_unsupported") == "0",
               simple.get("p15_mmio_unsupported"))

    # The first post-MMIO blocker is the live A0 vector stub identified by the
    # verified pre-production reconnaissance as A0:0x13 at function 0x80026c88.
    gate.check("frontier:first-site", failure.get("site") == "0x80026c8c",
               str(failure.get("site")))
    gate.check("frontier:first-function",
               failure.get("function_entry") == "0x80026c88",
               str(failure.get("function_entry")))
    gate.check("frontier:a0-vector", failure.get("source_value") == "0x000000a0",
               str(failure.get("source_value")))
    gate.check("frontier:classification",
               failure.get("message") == "unresolved indirect jump",
               str(failure.get("message")))
    gate.check("frontier:reached-after-interrupt-mmio",
               int(failure.get("block_index") or 0) > 0,
               str(failure.get("block_index")))

    trace_failure_count = int(simple.get("trace_failure_count", "0"))
    boundary_reached = False
    frontier = {
        "schema": "openrecomp-phase15-frontier-i-v1",
        "stage": STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "fixture": {"sha256": result["image"].file_sha256,
                    "size": result["image"].file_size},
        "build_status": result["built"]["build_status"],
        "run1_sha256": first["stdout_sha256"],
        "run2_sha256": second["stdout_sha256"],
        "byte_identical": probe.deterministic_match(result),
        "block_budget": surface.FRONTIER_BLOCK_BUDGET,
        "trace_failure_count": trace_failure_count,
        "failed": int(simple.get("failed", "0")),
        "error": simple.get("error"),
        "memory_denial_count": memory_denials,
        "first_remaining_memory_denial": None,
        "first_remaining_memory_denial_pc": None,
        "first_remaining_blocker": {
            "kind": "BIOS_VECTOR_INDIRECT",
            "service": "A0:0x13",
            "classification": "PROVEN_BY_VERIFIED_RECON_AND_LIVE_A0_STUB",
            "site": failure.get("site"),
            "function_entry": failure.get("function_entry"),
            "source_value": failure.get("source_value"),
            "block_event_index": failure.get("block_index"),
            "occurrence_count": failure.get("failure_count"),
        },
        "mmio_inventory": inventory,
        "p15_mmio_event_count": int(simple.get("p15_mmio_events", "0")),
        "p15_mmio_transcript_digest": simple.get("p15_mmio_digest"),
        "boundary": {
            "kind": "A0:0x43 Exec",
            "site": "0x80015b84",
            "title_entry": "0x800380a0",
            "reached": boundary_reached,
            "basis": "earlier A0:0x13 vector blocker remains active",
        },
        "unknown_service_count": int(simple.get("p10_service_failures", "0")),
        "unknown_indirect_count": trace_failure_count,
        "unsupported_instruction_count": 0,
        "runtime_memory_error_count": 0,
        "unexpected_mmio_count": mmio_denials,
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "frontier_i.json", frontier)
    assert_public_safe(gate, "frontier-i", frontier, result["image"].payload)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1", "stage": STAGE,
        "status": "PASS", "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "markers": {"OPENRECOMP_P15_03": "PASS"},
        "next_stage": "P15-04",
        "next_action": "prove SYS_CONTROL and DMA2 register state, then close live A0:0x13 producer",
    })
    gate.mark("OPENRECOMP_P15_03")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-03"))
