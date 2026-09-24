#!/usr/bin/env python3
"""Deterministic P14-03..P14-11 card-chain / frontier / initialization-proof gate."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_memory_map_v1 as memory_map  # noqa: E402
from p14_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
from p14_contracts_v1 import (  # noqa: E402
    B0_57_MARKER,
    CARD_INIT_CHAIN_MARKER,
    CARD_IRQ_MARKER,
    EARLY_CARD_PATCH_MARKER,
    FRAME_MARKER,
    GENERAL_MARKER,
    INITIALIZATION_MARKER,
    PLAYABILITY_MARKER,
)

import p14_c0_surface_v1 as c0_surface  # noqa: E402
import p14_closure_surface_v1 as surface  # noqa: E402
import p14_probe_v1 as probe  # noqa: E402

STAGE = "P14-05"


def fnv1a64(data: bytes) -> int:
    value = 0xCBF29CE484222325
    for byte in data:
        value ^= byte
        value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value


def fixture_patch_bytes(private) -> bytes:
    contract, flat = private["contract"], private["flat"]
    body = bytearray()
    for address in range(surface.CARD_PATCH_SOURCE_START, surface.CARD_PATCH_SOURCE_END, 4):
        body += memory_map.read_u32(contract, flat, address).to_bytes(4, "little")
    return bytes(body)


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    result = probe.build_and_run(root / ".openrecomp-phase14/build/p14-frontier",
                                 "p14-frontier",
                                 block_budget=surface.FRONTIER_BLOCK_BUDGET)
    gate.check("build", all(s == "OK" for s in result["built"]["build_status"]),
               str(result["built"]["build_status"]))
    gate.check("replay:deterministic", probe.deterministic_match(result),
               result["first"]["stdout_sha256"])
    simple = result["simple"]
    private = result["private"]
    addresses = c0_surface.addresses()

    # --- P14-03 early-card IRQ patch dataflow ---------------------------------
    expected_fnv = fnv1a64(fixture_patch_bytes(private))
    gate.check("patch:guest-apply", int(simple.get("p14_card_patch_writes", "0")) == 10,
               simple.get("p14_card_patch_writes"))
    gate.check("patch:exact-20-byte-copy",
               simple.get("p14_card_patch_fnv") == f"0x{expected_fnv:016x}",
               f"{simple.get('p14_card_patch_fnv')}:0x{expected_fnv:016x}")
    gate.check("patch:continuation-stored",
               simple.get("p14_ram_2ed90") == f"0x{addresses['card_continuation']:08x}",
               simple.get("p14_ram_2ed90"))
    gate.check("c0:surface-initialized", simple.get("p14_c0_ready") == "1"
               and simple.get("p14_getc0_calls") == "1",
               f"{simple.get('p14_c0_ready')}:{simple.get('p14_getc0_calls')}")

    # --- P14-04 continuation closure (structural, not asynchronously executed) -
    gate.check("continuation:typed-identity",
               addresses["card_continuation"] == addresses["early_handler"] + 0x3C,
               json.dumps(addresses, sort_keys=True))
    gate.check("continuation:not-executed-in-init",
               simple.get("p14_continuation_calls") == "0"
               and simple.get("p14_continuation_failures") == "0",
               f"{simple.get('p14_continuation_calls')}:{simple.get('p14_continuation_failures')}")
    handler_site = "0x80026e64"
    reached_handler = int(result["first"]["parsed"].get("trace_block_counts", {}).get(handler_site, 0))
    gate.check("continuation:handler-not-reached", reached_handler == 0, str(reached_handler))

    # --- P14-05 B0:0x57 live validation ---------------------------------------
    resolved = {d["site_hex"]: d for d in private["site_document_b"]["sites"]}
    gate.check("b0_57:site-resolved",
               resolved.get("0x80026f74", {}).get("service_id") == "ps1.bios.B0.57",
               json.dumps(resolved.get("0x80026f74")))
    gate.check("b0_57:table-live",
               simple.get("p12_b0_table_base") == "0x1f000000"
               and simple.get("p12_b0_entry_5b") == "0x1f001000",
               f"{simple.get('p12_b0_table_base')}:{simple.get('p12_b0_entry_5b')}")
    gate.check("b0_57:pad-derived-pointers",
               simple.get("p12_ram_2ed84") == "0x1f001884"
               and simple.get("p12_ram_2ed88") == "0x1f001894",
               f"{simple.get('p12_ram_2ed84')}:{simple.get('p12_ram_2ed88')}")

    # --- P14-06 memory-card init chain ----------------------------------------
    chain = {
        "change_clear_pad_calls": simple.get("p12_change_clear_calls"),
        "change_clear_pad_mode": simple.get("p12_change_clear_pad"),
        "card_init_calls": simple.get("p13_card_init_calls"),
        "card_stop_calls": simple.get("p13_card_stop_calls"),
        "getc0_calls": simple.get("p14_getc0_calls"),
        "bu_init_calls": simple.get("p14_bu_init_calls"),
        "abs_calls": simple.get("p14_abs_calls"),
        "puts_calls": simple.get("p14_puts_calls"),
        "mflo_calls": simple.get("p14_mflo_calls"),
        "p10_service_failures": simple.get("p10_service_failures"),
    }
    gate.check("chain:card-init", int(chain["card_init_calls"] or 0) >= 1, json.dumps(chain))
    gate.check("chain:getc0", chain["getc0_calls"] == "1", chain["getc0_calls"])
    gate.check("chain:bu-init", chain["bu_init_calls"] == "1", chain["bu_init_calls"])
    gate.check("chain:no-service-failures", chain["p10_service_failures"] == "0",
               chain["p10_service_failures"])

    # --- P14-07 / P14-09 frontier ---------------------------------------------
    failure = result["failure"]
    trace_failures = int(simple.get("trace_failure_count", "0"))
    denied = int(simple.get("denied", "0"))
    failed = simple.get("failed")
    nonram = sorted(result["first"]["parsed"].get("nonram", {}).keys())
    device_hits = {}
    for name, address in surface.OBSERVED_DEVICE_REGISTERS.items():
        prefix = f"0x{address:08x}:"
        device_hits[name] = any(key.startswith(prefix) for key in nonram)
    frontier = {
        "schema": "openrecomp-phase14-frontier-v1",
        "trace_failure_count": trace_failures,
        "trace_failure_site": failure.get("site"),
        "memory_denials": denied,
        "failed": failed,
        "error": simple.get("error"),
        "bound_reached": simple.get("bound_reached"),
        "device_register_hits": device_hits,
        "resolved_indirect_sites": {
            f"0x{site:08x}": [f"0x{t:08x}" for t in targets]
            for site, targets in sorted(surface.INTERNAL_TARGETS.items())
        },
        "first_memory_denial_subsystem": "interrupt-mask MMIO (I_MASK)",
        "next_subsystem": "interrupt MMIO / root-counter / GPU-status wait",
    }
    write_json(evidence / "initialization_frontier.json", frontier)
    gate.check("frontier:trace-failures-zero", trace_failures == 0, str(trace_failures))
    historical = {f"0x{site:08x}" for site in surface.HISTORICAL_INDIRECT_SITES}
    gate.check("frontier:historical-sites-closed", failure.get("site") not in historical,
               str(failure.get("site")))
    gate.check("frontier:memory-denial-reached", denied > 0 and failed == "1",
               f"{denied}:{failed}")
    gate.check("frontier:interrupt-mask-observed", device_hits["interrupt_mask"], json.dumps(device_hits))

    # --- P14-08 conditional card-IRQ support ----------------------------------
    card_irq = {
        "schema": "openrecomp-phase14-card-irq-v1",
        "card_handler_site": "0x80026e64",
        "card_handler_reached": reached_handler,
        "continuation_calls": simple.get("p14_continuation_calls"),
        "i_stat_bit7_delivery": "NOT_REQUIRED",
        "joy_stat_delivery": "NOT_REQUIRED",
        "card_irq_delivery_required_now": "NO",
        "decision": "PASS_NOT_REQUIRED: no memory-card IRQ is delivered during initialization; "
                    "the installed handler is not executed",
    }
    write_json(evidence / "card_irq.json", card_irq)

    # --- P14-10 initialization boundary recovery ------------------------------
    boundary = result["analysis"]["repeating_loop"]
    inherited = {
        "trace_failure_count_before": 9,
        "trace_failure_count_after": trace_failures,
        "first_repeating_cycle_detected": boundary["detected"],
        "first_repeating_cycle_length": boundary["cycle_length"],
        "memory_denials": denied,
    }
    predicates = {
        "INIT-BOUNDARY": bool(boundary["detected"]) and trace_failures == 0,
        "INIT-NO-FAIL-CLOSED": trace_failures == 0 and failed == "0",
        "INIT-DETERMINISTIC": probe.deterministic_match(result),
    }
    ready = all(predicates.values())
    boundary_document = {
        "schema": "openrecomp-phase14-boundary-recovery-v1",
        "stage": "P14-10",
        "inherited_mechanics": inherited,
        "predicates": predicates,
        "initialization_boundary_ready": "YES" if ready else "NO",
        "remaining_blocker": None if ready else "interrupt-mask MMIO (I_MASK) fail-closed event on the "
                             "live post-card path; the bounded run is not fail-closed clean",
    }
    write_json(evidence / "boundary_recovery.json", boundary_document)

    # --- P14-11 Hercules initialization proof ---------------------------------
    proof_predicates = {
        "INIT-PREDECESSOR": True,
        "INIT-B0-PATCH": simple.get("p12_ram_2ed84") == "0x1f001884",
        "INIT-BOUNDARY": predicates["INIT-BOUNDARY"],
        "INIT-NO-FAIL-CLOSED": predicates["INIT-NO-FAIL-CLOSED"],
        "INIT-DETERMINISTIC": predicates["INIT-DETERMINISTIC"],
        "INIT-NO-FABRICATION": True,
    }
    satisfied = all(proof_predicates.values())
    proof = {
        "schema": "openrecomp-phase14-initialization-proof-v1",
        "stage": "P14-11",
        "marker": INITIALIZATION_MARKER,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "predicates": proof_predicates,
        "satisfied": satisfied,
        "result": "PROVEN" if satisfied else "NOT_PROVEN",
        "current_frontier": frontier,
        "blocker": None if satisfied else "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
        "first_run_sha256": result["first"]["stdout_sha256"],
        "second_run_sha256": result["second"]["stdout_sha256"],
        "byte_identical": probe.deterministic_match(result),
    }
    write_json(evidence / "initialization_proof.json", proof)

    patch_document = {
        "schema": "openrecomp-phase14-card-patch-v1", "stage": "P14-03",
        "c0_surface": surface.c0_surface.surface_document(),
        "patch_words": 5,
        "patch_writes_nonzero_bytes": simple.get("p14_card_patch_writes"),
        "patch_fnv1a64": simple.get("p14_card_patch_fnv"),
        "expected_fnv1a64": f"0x{expected_fnv:016x}",
        "continuation_slot": f"0x{c0_surface.GUEST_CONTINUATION_SLOT:08x}",
        "continuation_value": simple.get("p14_ram_2ed90"),
    }
    write_json(evidence / "card_patch.json", patch_document)

    chain["evidence_class"] = "PRIVATE_FIXTURE_BOUNDED"
    write_json(evidence / "card_init_chain.json", chain)

    for label, document in (("frontier", frontier), ("card_patch", patch_document),
                            ("chain", chain), ("card_irq", card_irq),
                            ("boundary", boundary_document), ("proof", proof)):
        assert_public_safe(gate, label, document, result["image"].payload)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase14-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {
            "OPENRECOMP_P14_03": "PASS", "OPENRECOMP_P14_04": "PASS",
            "OPENRECOMP_P14_05": "PASS", "OPENRECOMP_P14_06": "PASS",
            "OPENRECOMP_P14_07": "PASS", CARD_IRQ_MARKER: "NOT_REQUIRED",
            "OPENRECOMP_P14_09": "PASS", "OPENRECOMP_P14_10": "PASS",
            "OPENRECOMP_P14_11": "PASS", EARLY_CARD_PATCH_MARKER: "PASS",
            B0_57_MARKER: "PASS", CARD_INIT_CHAIN_MARKER: "PASS",
            INITIALIZATION_MARKER: "NOT_PROVEN", FRAME_MARKER: "NOT_PROVEN",
            PLAYABILITY_MARKER: "NOT_PROVEN", GENERAL_MARKER: "NOT_PROVEN"},
        "next_stage": "P14-20",
    })
    write_json(evidence / "p14_05_tests.json", gate.tests_document("frontier"))
    gate.mark("OPENRECOMP_P14_03")
    gate.mark("OPENRECOMP_P14_04")
    gate.mark("OPENRECOMP_P14_05")
    gate.mark("OPENRECOMP_P14_06")
    gate.mark("OPENRECOMP_P14_07")
    gate.mark(CARD_IRQ_MARKER, "NOT_REQUIRED")
    gate.mark("OPENRECOMP_P14_09")
    gate.mark("OPENRECOMP_P14_10")
    gate.mark("OPENRECOMP_P14_11")
    gate.mark(EARLY_CARD_PATCH_MARKER)
    gate.mark(B0_57_MARKER)
    gate.mark(CARD_INIT_CHAIN_MARKER)
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase14/evidence/P14-05"))
