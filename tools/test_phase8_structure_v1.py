#!/usr/bin/env python3
"""OpenRecomp Phase-8 real-ELF neutral structure gate (P8-03).

P8-03 drives the frozen P8-01 real MIPS32 ELF through the existing neutral
ProgramModel, CFG, function discovery, call graph and translation-unit
structure using the additive P8 bridge `.openrecomp-phase8/src/p8_structure_v1.py`.

The gate proves, on frozen evidence:

* the structure is complete and deterministic (two independent derivations
  with identical fingerprints);
* delay slots are folded exactly (23 sites, 16 non-nop), every control
  instruction owns exactly one adjacent delay slot, and no delay slot is a
  control transfer or a transfer target;
* indirect control flow is never guessed: `jr $ra` is a structural return
  backed by the frozen terminator, every other indirect transfer stays an
  explicit unresolved site with no target;
* the call graph, functions and translation units are internally consistent
  with the CFG and with the frozen frontier;
* fail-closed mutations are rejected with stable codes.

On success it emits::

    OPENRECOMP_P8_03=PASS
    OPENRECOMP_PHASE8_PROGRAM_STRUCTURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_structure_v1.py
"""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))

import adapters.mips32 as mips32_adapter  # noqa: E402
import p3_code_frontier_v1 as frontier  # noqa: E402
import p3_elf_image_v1 as elf  # noqa: E402
import p3_target_mips32_v1 as target  # noqa: E402
import p8_structure_v1 as structure  # noqa: E402
from openrecomp.program_model import InstructionFlow, ProgramSource  # noqa: E402

EVIDENCE_DIR = ROOT / ".openrecomp-phase8" / "evidence" / "P8-03"

STAGE = "P8-03"
STAGE_MARKER = "OPENRECOMP_P8_03"
FEATURE_MARKER = "OPENRECOMP_PHASE8_PROGRAM_STRUCTURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

FIXTURE_ELF = ROOT / ".openrecomp-phase8" / "build" / "P8-01" / "candidate-a" / "p8_aes128_mips32_O1.elf"
FIXTURE_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"

EXPECTED_SUMMARY = {
    "neutral_instructions": 486,
    "folded_delay_slots": 23,
    "non_nop_delay_slots": 16,
    "blocks": 27,
    "edges": 25,
    "edge_histogram": {
        "BRANCH_NOT_TAKEN": 5,
        "BRANCH_TAKEN": 5,
        "CALL_RETURN": 8,
        "FALLTHROUGH": 4,
        "JUMP": 3,
    },
    "flow_histogram": {
        "BRANCH": 5,
        "CALL": 8,
        "JUMP": 3,
        "NORMAL": 463,
        "RETURN": 7,
    },
    "functions": 7,
    "shared_blocks": 0,
    "unowned_blocks": 0,
    "call_edges_internal": 8,
    "call_edges_external": 0,
    "call_edges_unresolved": 0,
    "translation_units": 7,
    "entry_unit": "tu_fn_2490",
    "entry_function": "fn_2490",
    "classification_units": 7,
    "unresolved_sites": [],
    "program_model_fingerprint": "718f538ed53acacafb81ebe00d4effa29ab827ae2a5654de6662a62c46c8b60c",
    "cfg_fingerprint": "8c51308cd9ad9bd7987f57637e23ab94bbfbf0a9eeac10fa73d259ac0a689e71",
    "call_graph_fingerprint": "8508c599d2869d1d32a24949c4b113112bf21a57c7c3c04a7a255c581220cd5b",
    "units_fingerprint": "50034a80e085b9a80c9742dffd50521d24d1b76dfbc29e5dd6066c3f519ac33b",
    "discovery_fingerprint": "2a9835556a8a3db0433060a2fe81d3647cc2cf1babdb234367f8b1a816fa528d",
}
EXPECTED_DELAY_OPS = {"addiu", "nop", "or", "sb"}
EXPECTED_NON_NOP_DELAY_OPS = {"addiu", "or", "sb"}

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL", "detail": detail})
        raise AssertionError(f"{label}: condition failed ({detail})")
    RESULTS.append({"check": label, "status": "PASS", "detail": detail})
    print(f"PASS: {label}")


def expect_fail(label: str, thunk, code: str) -> None:
    try:
        thunk()
    except structure.P8StructureError as exc:
        if exc.code == code:
            RESULTS.append({"check": f"reject:{label}", "status": "PASS", "detail": exc.code})
            print(f"PASS reject: {label}")
            return
        RESULTS.append({"check": f"reject:{label}", "status": "FAIL", "detail": f"{exc.code} != {code}"})
        raise AssertionError(f"{label}: raised {exc.code} instead of {code}") from exc
    except Exception as exc:  # noqa: BLE001
        RESULTS.append({"check": f"reject:{label}", "status": "FAIL", "detail": type(exc).__name__})
        raise AssertionError(f"{label}: raised {type(exc).__name__} instead of {code}: {exc}") from exc
    RESULTS.append({"check": f"reject:{label}", "status": "FAIL", "detail": "accepted"})
    raise AssertionError(f"{label}: accepted")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evidence_json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_evidence(name: str, payload: object) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_bytes(evidence_json(payload))


def build_source(data: bytes) -> ProgramSource:
    return ProgramSource(
        mips32_adapter.info.architecture_id,
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=sha256_bytes(data),
    )


def derive(analysis, source, entry):
    return structure.analyze_structure(analysis, source=source, entry=entry)


def main() -> int:
    try:
        data = FIXTURE_ELF.read_bytes()
        check("fixture:sha256", sha256_bytes(data) == FIXTURE_SHA256, sha256_bytes(data))

        ingested = elf.ingest(data, target.MIPS32_O32)
        region = ingested.parsed.executable_regions()[0]
        entry = ingested.parsed.header.e_entry
        analysis = frontier.analyze(ingested.image.read_u32, region.p_vaddr, region.p_vaddr + region.p_memsz, entry)
        check("frontier:reachable", analysis["summary"]["reachable_words"] == 509, str(analysis["summary"]["reachable_words"]))
        source = build_source(data)

        first = derive(analysis, source, entry)
        second = derive(analysis, source, entry)
        summary = structure.structure_summary(first)
        summary_second = structure.structure_summary(second)
        check("determinism:summary", summary == summary_second, "identical summary")
        for key, expected in sorted(EXPECTED_SUMMARY.items()):
            check(f"structure:{key}", summary[key] == expected, json.dumps(summary[key], sort_keys=True))

        # delay-slot folding facts
        folded = first.folded_delay_slots
        check("delay:folded-count", len(folded) == 23, str(len(folded)))
        check(
            "delay:folded-non-nop",
            sum(1 for item in folded.values() if item["non_nop"]) == 16,
            str(sum(1 for item in folded.values() if item["non_nop"])),
        )
        check("delay:folded-ops", set(item["op"] for item in folded.values()) == EXPECTED_DELAY_OPS, json.dumps(sorted({item["op"] for item in folded.values()})))
        check(
            "delay:non-nop-ops",
            set(item["op"] for item in folded.values() if item["non_nop"]) == EXPECTED_NON_NOP_DELAY_OPS,
            json.dumps(sorted({item["op"] for item in folded.values() if item["non_nop"]})),
        )
        check(
            "delay:owner-plus-four",
            all(item["address"] == owner + 4 for owner, item in folded.items()),
            "owner+4",
        )
        check(
            "delay:adapter-fields",
            all(
                item["adapter_fields"].get("address") == item["address"]
                and item["adapter_fields"].get("op") == item["op"]
                for item in folded.values()
            ),
            "fields-consistent",
        )
        check(
            "delay:dropped-not-neutral",
            not (set(first.dropped_delay_addresses) & set(first.neutral_addresses)),
            "disjoint",
        )
        check(
            "delay:count-reconciles",
            len(first.neutral_addresses) + len(first.dropped_delay_addresses) == 509,
            f"{len(first.neutral_addresses)}+{len(first.dropped_delay_addresses)}",
        )

        # neutral instruction metadata and extents
        neutral = tuple(first.cfg.instructions)
        check(
            "neutral:control-has-delay",
            all(
                (instruction.metadata.get("delay_slot") is not None)
                == (instruction.flow in (InstructionFlow.BRANCH, InstructionFlow.JUMP, InstructionFlow.CALL, InstructionFlow.RETURN))
                for instruction in neutral
            ),
            "control-only",
        )
        check(
            "neutral:control-extent-eight",
            all(
                (instruction.size_bytes == 8)
                == (instruction.flow in (InstructionFlow.BRANCH, InstructionFlow.JUMP, InstructionFlow.CALL, InstructionFlow.RETURN))
                for instruction in neutral
            ),
            "control=8 normal=4",
        )
        check(
            "neutral:no-indirect-flow",
            all(
                instruction.flow not in (InstructionFlow.INDIRECT_JUMP, InstructionFlow.INDIRECT_CALL)
                for instruction in neutral
            ),
            "no indirect flow",
        )
        check("neutral:no-traps", all(instruction.flow is not InstructionFlow.TRAP for instruction in neutral), "no traps")

        neutral_set = set(first.neutral_addresses)
        check(
            "cfg:targets-inside",
            all(
                successor.target_address is None or successor.target_address in neutral_set
                for block in first.cfg.blocks
                for successor in block.successors
            ),
            "all targets neutral",
        )
        check(
            "cfg:no-target-into-delay",
            not (
                {
                    successor.target_address
                    for block in first.cfg.blocks
                    for successor in block.successors
                    if successor.target_address is not None
                }
                & set(first.dropped_delay_addresses)
            ),
            "no delay targets",
        )

        # call graph consistency with the frozen frontier
        frontier_calls = {
            item["site"]: item["target"] for item in analysis["control_flow"]["direct-calls"]
        }
        check("calls:frontier-count", len(frontier_calls) == 8, str(len(frontier_calls)))
        internal = first.call_graph.internal_edges()
        entry_by_function = {function.id: function.entry_address for function in first.discovery.functions}
        observed_calls = sorted((edge.call_site_address, entry_by_function[edge.callee]) for edge in internal)
        check(
            "calls:edges-match-frontier",
            set(observed_calls) == set(frontier_calls.items()),
            json.dumps(observed_calls),
        )
        check("calls:entry-source", first.discovery.entry_function_id == "fn_2490", first.discovery.entry_function_id)
        check(
            "calls:callee-entries",
            sorted(function.entry_address for function in first.discovery.functions)
            == sorted({entry} | set(frontier_calls.values())),
            json.dumps(sorted({entry} | set(frontier_calls.values()))),
        )
        check("units:one-per-function", len(first.units.units) == len(first.discovery.functions), str(len(first.units.units)))
        check("classification:no-unresolved", structure.structure_summary(first)["unresolved_sites"] == [], "none")

        # fail-closed mutations
        def mutated():
            return copy.deepcopy(analysis)

        broken = mutated()
        delay_address = min(first.dropped_delay_addresses)
        broken["reachable_addresses"] = [a for a in broken["reachable_addresses"] if a != delay_address]
        expect_fail(
            "delay-slot-unreachable",
            lambda: derive(broken, source, entry),
            "DELAY_SLOT_UNREACHABLE",
        )

        broken = mutated()
        for record in broken["records"]:
            if record["address"] == delay_address:
                record["control_flow"] = {"op": "b", "operands": {}}
                record["terminator"] = "conditional-branch"
                record["target"] = 0x1000
        expect_fail("delay-slot-is-control", lambda: derive(broken, source, entry), "DELAY_SLOT_IS_CONTROL")

        broken = mutated()
        branch_site = next(item["site"] for item in broken["control_flow"]["conditional-branches"])
        for record in broken["records"]:
            if record["address"] == branch_site:
                record["target"] = delay_address
        expect_fail("target-into-delay-slot", lambda: derive(broken, source, entry), "TARGET_INTO_DELAY_SLOT")

        broken = mutated()
        return_site = next(item["site"] for item in broken["control_flow"]["returns"])
        for record in broken["records"]:
            if record["address"] == return_site:
                record["terminator"] = "indirect-jump"
                record["target"] = None
                record["control_flow"] = {"op": "jr", "operands": {"rs": 31}}
                record["decode_class"] = "SUPPORTED"
        unresolved_result = derive(broken, source, entry)
        unresolved_sites = structure.structure_summary(unresolved_result)["unresolved_sites"]
        check(
            "indirect:not-guessed",
            len(unresolved_sites) == 1 and unresolved_sites[0]["target"] is None,
            json.dumps(unresolved_sites),
        )
        broken = mutated()
        for record in broken["records"]:
            if record["address"] == return_site:
                record["operands"] = {"rs": 5}
        expect_fail("return-not-ra", lambda: derive(broken, source, entry), "RETURN_NOT_RA")

        expect_fail(
            "malformed-analysis",
            lambda: derive({"records": [], "reachable_addresses": []}, source, entry),
            "INVALID_ANALYSIS",
        )

        write_evidence(
            "structure_summary.json",
            {
                "stage": STAGE,
                "fixture": {"sha256": FIXTURE_SHA256},
                "summary": summary,
                "folded_delay_slots": {
                    f"0x{owner:08x}": {
                        "delay": f"0x{item['address']:08x}",
                        "delay_op": item["op"],
                        "non_nop": item["non_nop"],
                    }
                    for owner, item in sorted(folded.items())
                },
                "function_entries": sorted(function.entry_address for function in first.discovery.functions),
                "call_edges": observed_calls,
                "markers": {
                    "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
                    "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
                },
            },
        )
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    status = "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    record = {
        "stage": STAGE,
        "stage_name": "Real-ELF ProgramModel / CFG integration",
        "status": status,
        "tests": len(RESULTS),
        "passed": sum(1 for item in RESULTS if item["status"] == "PASS"),
        "failed": sum(1 for item in RESULTS if item["status"] != "PASS"),
        "checks": RESULTS,
        "failure": None if status == "PASS" else [item for item in RESULTS if item["status"] != "PASS"],
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={len(RESULTS)}",
            "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
            "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
        },
    }
    write_evidence("p8_03_tests.json", record)

    for item in RESULTS:
        if item["status"] != "PASS":
            print(f"FAIL: {item['check']} :: {item.get('detail', '')}")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(RESULTS)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
