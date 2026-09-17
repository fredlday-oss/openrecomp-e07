#!/usr/bin/env python3
"""OpenRecomp Phase-3 real-ELF program structure gate (P3-05).

P3-05 exercises the frozen Phase-2 architecture-neutral structural layers
(``openrecomp.program_model``, ``openrecomp.cfg``, ``openrecomp.functions``,
``openrecomp.call_graph``, ``openrecomp.translation_units``) against the audited
CoreMark MIPS32 ELF frontier established by P3-03/P3-04.

The deterministic gate:

* verifies source integrity: the frozen root ``SOURCE_SHA256SUMS.txt`` is
  unchanged and every entry still hashes, and the Phase-3
  ``.openrecomp-phase3/SOURCE_SHA256SUMS.txt`` manifest registers and verifies
  the Phase-3 source/gate files (grown additively to this stage's set);
* re-derives the P3-03 frontier on fresh bytes and cross-checks totals,
  histograms, reachability hash, control-flow sites, unresolved sites, the
  delay-slot count, the exception frontier and the indirect sites against the
  recorded P3-03 evidence;
* converts only the ``REACHABLE`` frontier records into neutral
  ``DecodedInstruction`` objects through ``p3_structure_v1`` and asserts the
  exact flow histogram, the exact reachable set, the 391 delay slots, the
  absence of the eight padding words and the absence of every invalid
  encoding from the structural model;
* builds the CFG, function discovery, direct call graph and translation units
  through the frozen shared layers and pins the exact block/edge/function/
  call-graph/unit structure plus their fingerprints;
* proves that every resolved direct edge matches its decoded target, that the
  three reachable ``jr $at`` sites stay unresolved with no target invented,
  and that the dead ``jalr`` at ``0x1958`` stays outside the structure;
* proves serialization round-trips byte-identically for all four shared
  containers and that ``PROVEN`` is preserved across round-trips;
* fails closed on synthetic malformed frontier records (invalid encoding,
  unsupported control transfer, missing/forbidden targets, missing delay slot,
  inconsistent region, duplicate records, unknown terminator);
* never resolves indirect targets, never attributes unreachable words to a
  function and never treats the structural model as an execution claim.

On success it emits::

    OPENRECOMP_P3_05=PASS
    OPENRECOMP_PHASE3_PROGRAM_STRUCTURE_V1=PASS tests=<count>

Any failed invariant fails closed and emits ``OPENRECOMP_P3_05=FAIL``.

Usage:

    python tools/test_phase3_structure_v1.py
    python tools/test_phase3_structure_v1.py --elf .openrecomp-phase3/build/P3-01/candidate-a/coremark_mips32_O1.elf
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / ".openrecomp-phase3" / "src"
for candidate in (str(ROOT), str(SRC_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from p3_code_frontier_v1 import analyze  # noqa: E402
from p3_decode_mips32_v1 import (  # noqa: E402
    CLASS_RECOGNIZED_UNSUPPORTED,
    CLASS_RESERVED,
    classify,
)
from p3_elf_image_v1 import (  # noqa: E402
    canonical_json_bytes,
    evidence_json_bytes,
    ingest,
    sha256_bytes,
)
from p3_structure_v1 import (  # noqa: E402
    StructureError,
    analyze_structure,
    flow_for_record,
    neutral_instruction,
    structure_summary,
)
from p3_target_mips32_v1 import MIPS32_O32  # noqa: E402
from openrecomp.call_graph import CallEdgeKind  # noqa: E402
from openrecomp.program_model import (  # noqa: E402
    DecodedInstruction,
    EvidenceClass,
    InstructionFlow,
    ProgramModel,
    ProgramSource,
)
from openrecomp.cfg import ControlFlowGraph  # noqa: E402
from openrecomp.call_graph import CallGraph  # noqa: E402
from openrecomp.translation_units import TranslationUnitSet  # noqa: E402

EVIDENCE_ROOT = ROOT / ".openrecomp-phase3" / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-05"
P3_03_EVIDENCE = EVIDENCE_ROOT / "P3-03"
P3_04_EVIDENCE = EVIDENCE_ROOT / "P3-04"

STAGE = "P3-05"
STAGE_MARKER = "OPENRECOMP_P3_05"
FEATURE_MARKER = "OPENRECOMP_PHASE3_PROGRAM_STRUCTURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF"

P3_SOURCE_MANIFEST = ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt"
P3_SOURCE_FILES = (
    ".openrecomp-phase3/src/p3_code_frontier_v1.py",
    ".openrecomp-phase3/src/p3_decode_mips32_v1.py",
    ".openrecomp-phase3/src/p3_elf_image_v1.py",
    ".openrecomp-phase3/src/p3_host_emit_v1.py",
    ".openrecomp-phase3/src/p3_semantics_mips32_v1.py",
    ".openrecomp-phase3/src/p3_static_data_v1.py",
    ".openrecomp-phase3/src/p3_structure_v1.py",
    ".openrecomp-phase3/src/p3_target_mips32_v1.py",
    "tools/test_phase3_boundary_v1.py",
    "tools/test_phase3_coremark_fixture_v1.py",
    "tools/test_phase3_decode_frontier_v1.py",
    "tools/test_phase3_elf_ingestion_v1.py",
    "tools/test_phase3_host_emit_v1.py",
    "tools/test_phase3_native_runtime_v1.py",
    "tools/test_phase3_reachable_semantics_v1.py",
    "tools/test_phase3_static_data_v1.py",
    "tools/test_phase3_structure_v1.py",
)
ROOT_MANIFEST = ROOT / "SOURCE_SHA256SUMS.txt"
ROOT_MANIFEST_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
ROOT_MANIFEST_ENTRIES = 134

DEFAULT_ELF = (
    ROOT / ".openrecomp-phase3" / "build" / "P3-01" / "candidate-a"
    / "coremark_mips32_O1.elf"
)
ELF_SHA256 = "16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669"
ELF_SIZE = 31184
TEXT_VADDR = 0x1000
TEXT_SIZE = 13948
TEXT_END = TEXT_VADDR + TEXT_SIZE
TEXT_WORDS = 3487
ENTRY = 0x4650

ARCHITECTURE = "MIPS32"
ADAPTER_NAME = "mips32-bounded-v1 + p3_decode_mips32_v1"
ADDRESS_WIDTH_BITS = 32

EXPECTED_TOTALS = {
    "total_words": 3487,
    "decoded_words": 3479,
    "supported_words": 3397,
    "recognized_unsupported_words": 82,
    "reserved_encoding_words": 8,
    "unknown_encoding_words": 0,
    "invalid_words": 8,
    "reachable_words": 2178,
    "unreachable_words": 1309,
    "reachable_supported_words": 2123,
    "reachable_unsupported_words": 55,
    "reachable_invalid_words": 0,
}
EXPECTED_CONTROL_FLOW_COUNTS = {
    "conditional-branches": 198,
    "direct-calls": 96,
    "indirect-calls": 0,
    "indirect-jumps": 3,
    "jumps": 70,
    "returns": 24,
    "unsupported-control-transfers": 0,
}
EXPECTED_UNRESOLVED_COUNTS = {"indirect-jump": 3, "successor-outside-image": 1}
EXPECTED_DELAY_SLOTS = 391
EXPECTED_REACHABILITY_SHA256 = (
    "c62d54838cbc5fcc7b0ff83cdc9b2f0f47b8851c5e4023ae2ca6d629c8f76edf"
)
EXPECTED_REACHABLE_INDIRECT_JR = (0x3130, 0x3830, 0x39A0)
EXPECTED_DEAD_JALR = 0x1958
EXPECTED_PADDING = (0x1D8C, 0x25CC, 0x33C8, 0x33CC, 0x36FC, 0x4644, 0x4648, 0x464C)
EXPECTED_EXCEPTION_SITES = (
    (0x1F60, "divu"), (0x1F64, "teq"),
    (0x2044, "divu"), (0x2048, "teq"),
    (0x2370, "divu"), (0x2374, "teq"),
)
EXPECTED_BOUNDARY_SITE = 0x4674
EXPECTED_BOUNDARY_SUCCESSOR = 0x467C
EXPECTED_BOUNDARY_WORD = 0x1000FFFF

EXPECTED_FLOW_HISTOGRAM = {
    "BRANCH": 198,
    "CALL": 96,
    "INDIRECT_JUMP": 3,
    "JUMP": 70,
    "NORMAL": 1787,
    "RETURN": 24,
}
EXPECTED_INSTRUCTION_COUNT = 2178
EXPECTED_BLOCK_COUNT = 615
EXPECTED_EDGE_HISTOGRAM = {
    "BRANCH_NOT_TAKEN": 198,
    "BRANCH_TAKEN": 198,
    "CALL_RETURN": 96,
    "FALLTHROUGH": 205,
    "INDIRECT": 3,
    "JUMP": 70,
}
EXPECTED_RESOLVED_EDGES = 767
EXPECTED_UNRESOLVED_EDGES = 3
EXPECTED_ORPHAN_DELAY_SLOTS = 97
EXPECTED_FUNCTION_COUNT = 26
EXPECTED_CALL_GRAPH_EDGES = 96
EXPECTED_UNIT_COUNT = 26
EXPECTED_ENTRY_UNIT = "tu_fn_4650"

EXPECTED_FUNCTION_ENTRIES = (
    0x1000, 0x1190, 0x1A40, 0x1D90, 0x1E5C, 0x25D0, 0x2618, 0x2D0C, 0x2E40,
    0x30B0, 0x32E8, 0x33D0, 0x34E0, 0x36A4, 0x36D8, 0x36F4, 0x371C, 0x44D4,
    0x44F0, 0x450C, 0x4524, 0x453C, 0x4558, 0x456C, 0x4578, 0x4650,
)
EXPECTED_JUMP_SITES_BY_FUNCTION = {
    "fn_30b0": (0x3130,),
    "fn_371c": (0x3830, 0x39A0),
}

EXPECTED_PROGRAM_MODEL_FINGERPRINT = (
    "8ed487c0332977f2b5da2767ebc6a858020c5f8df9f049a30fbc026a099e5d94"
)
EXPECTED_CFG_FINGERPRINT = (
    "c9029a0d2382a9845f0da811dbbc343fe4d4573cc2cea6ac484f0d3fdc8ab814"
)
EXPECTED_CALL_GRAPH_FINGERPRINT = (
    "9462f40ccd7cd23bcedc37c03222335913d2da785696baf8cabb86fc5b4e93c9"
)
EXPECTED_UNIT_SET_FINGERPRINT = (
    "44c8b895d7672d692b487c961ec448f655b1e0854639af706335f8760a9f3e25"
)
EXPECTED_DISCOVERY_FINGERPRINT = (
    "cf307c18bc925001e54edb678d83c5591d6e1e6af07435a91d7e17326c238e2f"
)

SOURCE_INTEGRITY = "source_integrity.txt"
FIXTURE_JSON = "fixture.json"
CROSS_CHECK_JSON = "frontier_cross_check.json"
INSTRUCTIONS_JSON = "neutral_instructions.json"
CFG_JSON = "cfg_structure.json"
FUNCTIONS_JSON = "functions.json"
CALL_GRAPH_JSON = "call_graph.json"
UNITS_JSON = "translation_units.json"
ROUNDTRIP_JSON = "roundtrip.json"
NEGATIVES_JSON = "negatives.json"
DETERMINISM = "determinism.json"
RESULT_JSON = "RESULT.json"

CLAIM_BOUNDARY = (
    "P3-05 proves only that the frozen Phase-2 architecture-neutral structural "
    "layers run deterministically on the audited CoreMark MIPS32 reachable "
    "frontier: 2178 reachable instructions become 615 blocks, 26 proven "
    "functions, a 96-edge direct call graph and 26 translation units with the "
    "three reachable jr $at sites and the dead jalr left unresolved. It does "
    "not translate or execute CoreMark, does not resolve indirect targets, "
    "does not model MIPS32 delay slots in the shared layers beyond the "
    "explicitly recorded delay-slot frontier, and claims no arbitrary MIPS32, "
    "PS1 or PS2 compatibility."
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
ARTIFACTS: dict[str, bytes] = {}
EVIDENCE_DIR = DEFAULT_EVIDENCE_DIR


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def hexv(value: int) -> str:
    return f"0x{value:08x}"


def parse_manifest(path: pathlib.Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if " *" not in line:
            raise ValueError(f"unparsable manifest line: {line[:80]}")
        digest, relative = line.split(" *", 1)
        if relative in entries:
            raise ValueError(f"duplicate manifest entry: {relative}")
        entries[relative] = digest
    return entries


_HEX_VALUE = re.compile(r"^0x[0-9a-fA-F]+$")


def denormalize_hex(value: Any) -> Any:
    """Map recorded hex-string addresses back to integers for canonical comparison."""
    if isinstance(value, str) and _HEX_VALUE.match(value):
        return int(value, 16)
    if isinstance(value, dict):
        return {key: denormalize_hex(item) for key, item in value.items()}
    if isinstance(value, list):
        return [denormalize_hex(item) for item in value]
    return value


def make_source() -> ProgramSource:
    return ProgramSource(
        architecture=ARCHITECTURE,
        adapter=ADAPTER_NAME,
        address_width_bits=ADDRESS_WIDTH_BITS,
        endianness="little",
        input_sha256=ELF_SHA256,
    )


# ---------------------------------------------------------------------------
# Source integrity
# ---------------------------------------------------------------------------
def audit_source_integrity() -> None:
    check("source:root-manifest-exists", ROOT_MANIFEST.is_file())
    root_digest = sha256_bytes(ROOT_MANIFEST.read_bytes())
    check("source:root-manifest-frozen-sha256", root_digest == ROOT_MANIFEST_SHA256)
    root_entries = parse_manifest(ROOT_MANIFEST)
    check("source:root-manifest-entry-count", len(root_entries) == ROOT_MANIFEST_ENTRIES)
    root_mismatched = [
        relative for relative, digest in sorted(root_entries.items())
        if not (ROOT / relative).is_file()
        or sha256_bytes((ROOT / relative).read_bytes()) != digest
    ]
    check("source:root-manifest-entries-verified", not root_mismatched)

    check("source:phase3-manifest-exists", P3_SOURCE_MANIFEST.is_file())
    phase3_digest = sha256_bytes(P3_SOURCE_MANIFEST.read_bytes())
    phase3_entries = parse_manifest(P3_SOURCE_MANIFEST)
    check("source:phase3-manifest-entry-set",
          tuple(sorted(phase3_entries)) == tuple(sorted(P3_SOURCE_FILES)))
    phase3_mismatched = [
        relative for relative, digest in sorted(phase3_entries.items())
        if not (ROOT / relative).is_file()
        or sha256_bytes((ROOT / relative).read_bytes()) != digest
    ]
    check("source:phase3-manifest-entries-verified", not phase3_mismatched)

    lines = [
        f"PHASE3_SOURCE_MANIFEST={P3_SOURCE_MANIFEST.relative_to(ROOT).as_posix()}",
        f"PHASE3_SOURCE_MANIFEST_SHA256={phase3_digest}",
        f"PHASE3_SOURCE_ENTRIES={len(phase3_entries)}",
    ]
    lines += [f"{digest} *{relative}" for relative, digest in sorted(phase3_entries.items())]
    lines += [
        "PHASE3_SOURCE_INTEGRITY=PASS",
        f"ROOT_SOURCE_MANIFEST={ROOT_MANIFEST.name}",
        f"ROOT_SOURCE_MANIFEST_SHA256={root_digest}",
        f"ROOT_SOURCE_MANIFEST_ENTRIES={len(root_entries)}",
        "ROOT_SOURCE_INTEGRITY=PASS",
    ]
    ARTIFACTS[SOURCE_INTEGRITY] = ("\n".join(lines) + "\n").encode("utf-8")
    FINDINGS["source_integrity"] = {
        "root_manifest_sha256": root_digest,
        "root_manifest_entries": len(root_entries),
        "root_manifest_mismatched": root_mismatched,
        "phase3_manifest_sha256": phase3_digest,
        "phase3_manifest_entries": len(phase3_entries),
        "phase3_manifest_mismatched": phase3_mismatched,
        "phase3_files": sorted(phase3_entries),
    }


# ---------------------------------------------------------------------------
# Fixture, ingestion, frontier
# ---------------------------------------------------------------------------
def audit_fixture(elf_path: pathlib.Path) -> tuple[bytes, Any, dict[str, Any]]:
    check("fixture:exists", elf_path.is_file())
    data = elf_path.read_bytes()
    check("fixture:sha256", sha256_bytes(data) == ELF_SHA256)
    check("fixture:size", len(data) == ELF_SIZE)
    ingested = ingest(data, MIPS32_O32)
    text = ingested.parsed.section(".text")
    check("fixture:text-section", text is not None)
    check("fixture:text-identity", text.sh_addr == TEXT_VADDR and text.sh_size == TEXT_SIZE)
    check("fixture:entry", ingested.parsed.header.e_entry == ENTRY)
    raw_slice = data[TEXT_VADDR:TEXT_VADDR + TEXT_SIZE]
    check("fixture:image-equals-file-slice",
          all(ingested.image.read_u32(TEXT_VADDR + index * 4)
              == int.from_bytes(raw_slice[index * 4:index * 4 + 4], "little")
              for index in range(TEXT_WORDS)))
    record = {
        "path": elf_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_bytes(data),
        "size": len(data),
        "text_vaddr": hexv(TEXT_VADDR),
        "text_size": TEXT_SIZE,
        "text_words": TEXT_WORDS,
        "entry": hexv(ENTRY),
        "text_slice_sha256": sha256_bytes(raw_slice),
    }
    ARTIFACTS[FIXTURE_JSON] = evidence_json_bytes({"stage": STAGE, **record})
    FINDINGS["fixture"] = record
    return data, ingested, record


def run_frontier(ingested) -> dict[str, Any]:
    return analyze(ingested.image.read_u32, TEXT_VADDR, TEXT_END, ENTRY)


def function_layout(ingested) -> list[tuple[int, int, str]]:
    return [(symbol.value, symbol.value + symbol.size, symbol.name)
            for symbol in ingested.parsed.symbols()
            if symbol.is_function and symbol.size]


# ---------------------------------------------------------------------------
# P3-03 recorded-evidence cross-check
# ---------------------------------------------------------------------------
def audit_p3_03_cross_check(result: dict[str, Any], ingested) -> dict[str, Any]:
    paths = {
        "inventory": P3_03_EVIDENCE / "instruction_inventory.json",
        "reachable": P3_03_EVIDENCE / "reachable_code_map.json",
        "control": P3_03_EVIDENCE / "control_flow_frontier.json",
        "padding": P3_03_EVIDENCE / "padding_invalid_classification.md",
    }
    for key, path in paths.items():
        check(f"p3-03:{key}-exists", path.is_file())
    inventory = json.loads(paths["inventory"].read_text(encoding="utf-8"))
    reachable = json.loads(paths["reachable"].read_text(encoding="utf-8"))
    control = json.loads(paths["control"].read_text(encoding="utf-8"))
    summary = result["summary"]

    for key, expected in EXPECTED_TOTALS.items():
        check(f"p3-03:total:{key}", summary[key] == expected)
        check(f"p3-03:inventory:{key}", inventory["totals"][key] == expected)
    check("p3-03:supported-histogram",
          summary["supported_histogram"] == inventory["supported_histogram"])

    rows = [f"{hexv(record['address'])} {record['reachability']}"
            for record in result["records"]]
    reachability_digest = sha256_bytes("\n".join(rows).encode("ascii"))
    check("p3-03:reachability-sha256-frozen",
          reachability_digest == EXPECTED_REACHABILITY_SHA256)
    check("p3-03:reachable-map-sha256",
          reachable["reachability_sha256"] == EXPECTED_REACHABILITY_SHA256)
    check("p3-03:reachable-words", summary["reachable_words"] == reachable["reachable_words"])
    check("p3-03:unreachable-words",
          summary["unreachable_words"] == reachable["unreachable_words"])
    check("p3-03:padding-addresses",
          tuple(int(item, 16) for item in reachable["padding_addresses"]) == EXPECTED_PADDING)

    check("p3-03:control-flow-counts",
          summary["control_flow_site_counts"] == EXPECTED_CONTROL_FLOW_COUNTS)
    check("p3-03:control-recorded-counts",
          control["reachable_counts"] == EXPECTED_CONTROL_FLOW_COUNTS)
    check("p3-03:unresolved-counts",
          summary["unresolved_site_counts"] == EXPECTED_UNRESOLVED_COUNTS)
    check("p3-03:unresolved-recorded", control["unresolved_counts"] == EXPECTED_UNRESOLVED_COUNTS)
    check("p3-03:unresolved-records",
          canonical_json_bytes(denormalize_hex(control["unresolved"]))
          == canonical_json_bytes(result["unresolved"]))
    check("p3-03:delay-slot-count", control["delay_slot_count"] == EXPECTED_DELAY_SLOTS
          and len(result["delay_slots"]) == EXPECTED_DELAY_SLOTS)
    check("p3-03:diagnostics-empty",
          all(not value for value in result["diagnostics"].values()))

    indirect_reachable = tuple(
        int(item["address"], 16)
        for item in control["indirect_sites_all"]
        if item["reachability"] == "REACHABLE"
    )
    check("p3-03:indirect-sites", indirect_reachable == EXPECTED_REACHABLE_INDIRECT_JR)
    dead_jalr = [item for item in control["indirect_sites_all"]
                 if item["address"] == hexv(EXPECTED_DEAD_JALR)]
    check("p3-03:dead-jalr", len(dead_jalr) == 1
          and dead_jalr[0]["reachability"] == "UNREACHABLE"
          and dead_jalr[0]["op"] == "jalr")

    check("p3-03:exception-frontier",
          tuple((int(item["site"], 16), item["op"]) for item in control["exception_frontier"])
          == EXPECTED_EXCEPTION_SITES)
    check("p3-03:recomputed-exception-frontier",
          tuple((item["site"], item["op"]) for item in result["exception_sites"])
          == EXPECTED_EXCEPTION_SITES)
    boundary = [item for item in result["unresolved"]
                if item["kind"] == "successor-outside-image"]
    check("p3-03:boundary-successor",
          len(boundary) == 1
          and boundary[0]["site"] == EXPECTED_BOUNDARY_SITE
          and boundary[0]["target"] == EXPECTED_BOUNDARY_SUCCESSOR
          and boundary[0]["successor_kind"] == "conditional-branch-not-taken")
    boundary_note = [item for item in control["boundary_notes"]
                     if item["site"] == hexv(EXPECTED_BOUNDARY_SITE)]
    check("p3-03:boundary-recorded",
          len(boundary_note) == 1
          and int(boundary_note[0]["word"], 16) == EXPECTED_BOUNDARY_WORD)
    check("p3-03:boundary-recorded-word",
          ingested.image.read_u32(EXPECTED_BOUNDARY_SITE) == EXPECTED_BOUNDARY_WORD)

    check("p3-03:reachable-control-sites",
          canonical_json_bytes(result["control_flow"])
          == canonical_json_bytes(denormalize_hex(control["reachable"])))
    check("p3-03:exception-frontier-records",
          canonical_json_bytes(denormalize_hex(control["exception_frontier"]))
          == canonical_json_bytes(result["exception_sites"]))

    cross = {
        "stage": STAGE,
        "recorded": {
            "inventory_sha256": sha256_bytes(paths["inventory"].read_bytes()),
            "reachable_map_sha256": sha256_bytes(paths["reachable"].read_bytes()),
            "control_frontier_sha256": sha256_bytes(paths["control"].read_bytes()),
            "padding_note_sha256": sha256_bytes(paths["padding"].read_bytes()),
        },
        "recomputed": {
            "reachability_sha256": reachability_digest,
            "control_flow_site_counts": summary["control_flow_site_counts"],
            "unresolved_site_counts": summary["unresolved_site_counts"],
            "delay_slot_count": len(result["delay_slots"]),
            "exception_site_count": len(result["exception_sites"]),
            "indirect_sites": [hexv(site) for site in EXPECTED_REACHABLE_INDIRECT_JR],
            "dead_jalr": hexv(EXPECTED_DEAD_JALR),
            "boundary": {
                "site": hexv(EXPECTED_BOUNDARY_SITE),
                "successor": hexv(EXPECTED_BOUNDARY_SUCCESSOR),
                "word": hexv(EXPECTED_BOUNDARY_WORD),
            },
        },
        "result": "RECORDED_EVIDENCE_REPRODUCED_EXACTLY",
    }
    ARTIFACTS[CROSS_CHECK_JSON] = evidence_json_bytes(cross)
    FINDINGS["p3_03_cross_check"] = {
        "reachability_sha256": reachability_digest,
        "control_flow_site_counts": summary["control_flow_site_counts"],
        "unresolved_site_counts": summary["unresolved_site_counts"],
    }
    return cross


def audit_p3_04_cross_check(result: dict[str, Any]) -> None:
    path = P3_04_EVIDENCE / "reachable_unsupported_after.json"
    check("p3-04:after-table-exists", path.is_file())
    after = json.loads(path.read_text(encoding="utf-8"))
    reachable_sites = sorted(
        int(row["address"], 16) for row in after["site_table"]
        if row["reachability"] == "REACHABLE"
    )
    check("p3-04:reachable-site-count", len(reachable_sites) == 55)
    by_address = {record["address"]: record for record in result["records"]}
    recomputed = sorted(
        record["address"] for record in result["records"]
        if record["decode_class"] == CLASS_RECOGNIZED_UNSUPPORTED
        and record["reachability"] == "REACHABLE"
    )
    check("p3-04:reachable-sites-match", reachable_sites == recomputed)
    check("p3-04:all-sites-implemented",
          all(row["semantic_implementation_status"] == "IMPLEMENTED"
              for row in after["site_table"]))
    check("p3-04:reachable-semantic-gap-zero",
          after["counts"]["reachable_semantically_unsupported_after"] == 0)
    FINDINGS["p3_04_cross_check"] = {
        "reachable_unsupported_sites": len(reachable_sites),
        "after_table_sha256": sha256_bytes(path.read_bytes()),
    }


# ---------------------------------------------------------------------------
# Neutral instructions and structure
# ---------------------------------------------------------------------------
def build_structure(analysis: dict[str, Any]):
    return analyze_structure(analysis, source=make_source(), entry=ENTRY)


def audit_instructions(structure, analysis: dict[str, Any], ingested) -> dict[str, Any]:
    instructions = structure.instructions
    by_address = {record["address"]: record for record in analysis["records"]}
    reachable = sorted(analysis["reachable_addresses"])

    check("neutral:instruction-count", len(instructions) == EXPECTED_INSTRUCTION_COUNT)
    check("neutral:instruction-addresses-exact",
          tuple(instruction.address for instruction in instructions) == tuple(reachable))
    check("neutral:all-decoded-instruction", all(
        isinstance(instruction, DecodedInstruction) for instruction in instructions))
    check("neutral:all-size-four",
          all(instruction.size_bytes == 4 for instruction in instructions))
    check("neutral:all-evidence-proven",
          all(instruction.evidence is EvidenceClass.PROVEN for instruction in instructions))

    histogram = structure_summary(structure)["flow_histogram"]
    check("neutral:flow-histogram", histogram == EXPECTED_FLOW_HISTOGRAM)
    check("neutral:no-invalid-encoding-included", all(
        not (by_address[instruction.address]["decode_class"] in ("RESERVED_ENCODING", "UNKNOWN_ENCODING"))
        for instruction in instructions))
    check("neutral:word-identity", all(
        instruction.metadata["word"] == ingested.image.read_u32(instruction.address)
        and instruction.metadata["word"] == by_address[instruction.address]["word"]
        for instruction in instructions))
    check("neutral:metadata-canonical", all(
        instruction.metadata["decode_class"] == by_address[instruction.address]["decode_class"]
        and instruction.metadata["semantics"] == by_address[instruction.address]["semantics"]
        and dict(instruction.metadata["operands"]) == by_address[instruction.address]["operands"]
        for instruction in instructions))

    delay_addresses = sorted(item["delay"] for item in analysis["delay_slots"])
    instruction_index = {instruction.address: instruction for instruction in instructions}
    check("neutral:all-delay-slots-present",
          all(address in instruction_index for address in delay_addresses))
    check("neutral:delay-slots-normal", all(
        instruction_index[address].flow is InstructionFlow.NORMAL for address in delay_addresses))
    check("neutral:delay-slot-count", len(delay_addresses) == EXPECTED_DELAY_SLOTS)

    padding_in_instructions = [address for address in EXPECTED_PADDING if address in instruction_index]
    check("neutral:padding-excluded", not padding_in_instructions)
    check("neutral:padding-unreachable", all(
        by_address[address]["reachability"] == "UNREACHABLE" for address in EXPECTED_PADDING))

    indirect_jumps = [instruction for instruction in instructions
                      if instruction.flow is InstructionFlow.INDIRECT_JUMP]
    check("neutral:indirect-jump-sites",
          tuple(instruction.address for instruction in indirect_jumps)
          == EXPECTED_REACHABLE_INDIRECT_JR)
    check("neutral:indirect-targets-never-guessed", all(
        instruction.direct_target is None and instruction.unresolved
        for instruction in indirect_jumps))
    indirect_calls = [instruction for instruction in instructions
                      if instruction.flow is InstructionFlow.INDIRECT_CALL]
    check("neutral:no-reachable-indirect-call", not indirect_calls)
    check("neutral:dead-jalr-excluded", all(
        instruction.address != EXPECTED_DEAD_JALR for instruction in instructions))
    dead_jalr_record = by_address[EXPECTED_DEAD_JALR]
    check("neutral:dead-jalr-classified",
          dead_jalr_record["op"] == "jalr"
          and dead_jalr_record["reachability"] == "UNREACHABLE")

    returns = [instruction for instruction in instructions
               if instruction.flow is InstructionFlow.RETURN]
    check("neutral:return-count", len(returns) == EXPECTED_FLOW_HISTOGRAM["RETURN"])
    check("neutral:returns-without-target",
          all(instruction.direct_target is None and not instruction.unresolved
              for instruction in returns))
    calls = [instruction for instruction in instructions
             if instruction.flow is InstructionFlow.CALL]
    branches = [instruction for instruction in instructions
                if instruction.flow is InstructionFlow.BRANCH]
    jumps = [instruction for instruction in instructions
             if instruction.flow is InstructionFlow.JUMP]
    check("neutral:direct-call-targets-present",
          all(instruction.direct_target is not None for instruction in calls))
    check("neutral:branch-targets-present",
          all(instruction.direct_target is not None for instruction in branches))
    check("neutral:jump-targets-present",
          all(instruction.direct_target is not None for instruction in jumps))
    check("neutral:direct-target-matches-record", all(
        instruction.direct_target == by_address[instruction.address]["target"]
        for instruction in calls + branches + jumps))

    trap_continuation = [instruction for instruction in instructions
                         if instruction.metadata["exception_transfer"]]
    check("neutral:exception-continuations-normal",
          tuple((instruction.address, instruction.op) for instruction in trap_continuation)
          == EXPECTED_EXCEPTION_SITES)
    check("neutral:unsupported-control-transfer-absent",
          all(instruction.metadata["operands"] is not None for instruction in instructions))

    rows = [{
        "address": hexv(instruction.address),
        "word": hexv(instruction.metadata["word"]),
        "op": instruction.op,
        "decode_class": instruction.metadata["decode_class"],
        "semantics": instruction.metadata["semantics"],
        "flow": instruction.flow.value,
        "direct_target": hexv(instruction.direct_target)
        if instruction.direct_target is not None else None,
        "unresolved": instruction.unresolved,
        "size_bytes": instruction.size_bytes,
        "evidence": instruction.evidence.value,
        "delay_slot": instruction.metadata["delay_slot"],
        "operands": dict(instruction.metadata["operands"]),
    } for instruction in instructions]
    payload = {
        "stage": STAGE,
        "source": {
            "elf_sha256": ELF_SHA256,
            "text_vaddr": hexv(TEXT_VADDR),
            "text_end": hexv(TEXT_END),
            "entry": hexv(ENTRY),
        },
        "policy": (
            "only REACHABLE frontier records become neutral instructions; flow is a "
            "pure function of the frozen record; delay slots are ordinary NORMAL "
            "instructions with their frontier relationship recorded separately; "
            "PROVEN is structural (exact decode + reachable from the proven entry "
            "through resolved direct edges), not a runtime claim"
        ),
        "instruction_rows": rows,
        "instruction_rows_sha256": sha256_bytes(canonical_json_bytes(rows)),
        "flow_histogram": histogram,
        "count": len(rows),
        "unreachable_word_count": len(structure.unreachable_frontier),
    }
    ARTIFACTS[INSTRUCTIONS_JSON] = evidence_json_bytes(payload)
    FINDINGS["instructions"] = {
        "count": len(rows),
        "flow_histogram": histogram,
        "rows_sha256": payload["instruction_rows_sha256"],
        "unreachable_word_count": len(structure.unreachable_frontier),
    }
    return payload


def audit_unreachable_frontier(structure, analysis: dict[str, Any]) -> None:
    frontier = structure.unreachable_frontier
    check("unreachable:count", len(frontier) == 1309)
    by_address = {item["address"]: item for item in frontier}
    check("unreachable:padding-classes",
          all(by_address[address]["decode_class"] == CLASS_RESERVED
              and by_address[address]["op"] is None for address in EXPECTED_PADDING))
    check("unreachable:recognized-unsupported-count",
          sum(1 for item in frontier
              if item["decode_class"] == CLASS_RECOGNIZED_UNSUPPORTED) == 27)
    check("unreachable:decoded-word-count",
          sum(1 for item in frontier
              if item["decode_class"] in (CLASS_RECOGNIZED_UNSUPPORTED, "SUPPORTED")) == 1301)
    check("unreachable:dead-jalr-record",
          by_address[EXPECTED_DEAD_JALR]["op"] == "jalr"
          and by_address[EXPECTED_DEAD_JALR]["control_flow"] is True)
    check("unreachable:no-duplicate-addresses",
          len(by_address) == len(frontier))
    check("unreachable:disjoint-from-instructions",
          not (set(by_address) & {instruction.address for instruction in structure.instructions}))


# ---------------------------------------------------------------------------
# CFG structure
# ---------------------------------------------------------------------------
def audit_cfg(structure, ingested) -> dict[str, Any]:
    cfg = structure.cfg
    summary = structure_summary(structure)
    check("cfg:block-count", len(cfg.blocks) == EXPECTED_BLOCK_COUNT)
    check("cfg:edge-histogram", summary["edge_histogram"] == EXPECTED_EDGE_HISTOGRAM)
    check("cfg:resolved-edge-count", summary["resolved_edges"] == EXPECTED_RESOLVED_EDGES)
    check("cfg:unresolved-edge-count",
          summary["unresolved_edges"] == EXPECTED_UNRESOLVED_EDGES)

    blocks = cfg.ordered_blocks()
    block_by_id = {block.id: block for block in blocks}
    check("cfg:entry-block", block_by_id.get("blk_4650") is not None
          and block_by_id["blk_4650"].entry_address == ENTRY
          and block_by_id["blk_4650"].evidence is EvidenceClass.PROVEN)
    check("cfg:all-blocks-proven",
          all(block.evidence is EvidenceClass.PROVEN for block in blocks))
    check("cfg:all-instructions-assigned",
          sum(len(block.instructions) for block in blocks) == EXPECTED_INSTRUCTION_COUNT)
    check("cfg:instruction-partition",
          len({instruction.address for block in blocks for instruction in block.instructions})
          == EXPECTED_INSTRUCTION_COUNT)

    resolved = [(block, successor) for block in blocks for successor in block.successors
                if successor.resolved]
    unresolved = [(block, successor) for block in blocks for successor in block.successors
                  if not successor.resolved]
    check("cfg:resolved-edges-have-blocks", all(
        successor.target_block in block_by_id for _, successor in resolved))
    check("cfg:resolved-edge-target-match", all(
        successor.target_address == block_by_id[successor.target_block].entry_address
        for _, successor in resolved))

    terminal_by_block = {
        block.id: block.terminal for block in blocks
    }
    direct_edges = []
    for block, successor in resolved:
        terminal = terminal_by_block[block.id]
        if successor.kind.value in ("JUMP", "BRANCH_TAKEN"):
            direct_edges.append((terminal.address, terminal.direct_target,
                                 successor.target_address))
        elif successor.kind.value == "CALL_RETURN":
            direct_edges.append((terminal.address, terminal.address + 4,
                                 successor.target_address))
    check("cfg:direct-edges-match-decode",
          all(decoded == actual for _, decoded, actual in direct_edges))
    check("cfg:direct-edge-count",
          len(direct_edges) == 70 + 198 + 96)

    branch_blocks = [block for block in blocks
                     if block.terminal_flow() is InstructionFlow.BRANCH]
    check("cfg:branch-block-count", len(branch_blocks) == 198)
    check("cfg:branch-successor-pairs", all(
        sorted(successor.kind.value for successor in block.successors)
        == ["BRANCH_NOT_TAKEN", "BRANCH_TAKEN"] for block in branch_blocks))
    check("cfg:branch-not-taken-is-delay-slot", all(
        next(successor for successor in block.successors
             if successor.kind.value == "BRANCH_NOT_TAKEN").target_address
        == block.terminal.address + 4 for block in branch_blocks))

    return_blocks = [block for block in blocks
                     if block.terminal_flow() is InstructionFlow.RETURN]
    check("cfg:return-block-count", len(return_blocks) == 24)
    check("cfg:return-blocks-no-successors", all(not block.successors for block in return_blocks))

    indirect_blocks = [block for block in blocks
                       if block.terminal_flow() is InstructionFlow.INDIRECT_JUMP]
    check("cfg:indirect-block-count", len(indirect_blocks) == 3)
    check("cfg:indirect-single-unresolved", all(
        len(block.successors) == 1
        and block.successors[0].kind.value == "INDIRECT"
        and not block.successors[0].resolved
        and block.successors[0].target_block is None
        and block.successors[0].target_address is None
        for block in indirect_blocks))
    check("cfg:indirect-blocks-are-jr-at", tuple(sorted(
        block.terminal.address for block in indirect_blocks)) == EXPECTED_REACHABLE_INDIRECT_JR)
    check("cfg:unresolved-edges-are-indirect", all(
        successor.kind.value == "INDIRECT" for _, successor in unresolved))

    orphan_entries = sorted(block.entry_address for block in blocks
                            if block.id in set(structure.discovery.unowned_blocks))
    expected_orphans = sorted(
        item["delay"] for item in structure.delay_slot_frontier
        if item["owner_terminator"] in ("jump", "return", "indirect-jump", "indirect-call"))
    check("cfg:orphan-count", len(orphan_entries) == EXPECTED_ORPHAN_DELAY_SLOTS)
    check("cfg:orphans-are-delay-slots", orphan_entries == expected_orphans)
    check("cfg:unowned-set-match",
          tuple(sorted(structure.discovery.unowned_blocks))
          == tuple(block.id for block in blocks if block.entry_address in set(orphan_entries)))
    check("cfg:unowned-only-jump-return-indirect", all(
        item["owner_terminator"] in ("jump", "return", "indirect-jump")
        for item in structure.delay_slot_frontier
        if item["delay"] in set(orphan_entries)))

    predecessors = cfg.predecessors()
    check("cfg:predecessors-cover", all(
        any(entry["from"] == block.id
            for entry in predecessors.get(successor.target_block, ()))
        for block in blocks for successor in block.successors if successor.resolved))
    reverse_count = sum(len(predecessors.get(block.id, ())) for block in blocks)
    check("cfg:predecessor-count", reverse_count == EXPECTED_RESOLVED_EDGES)

    boundary_block = block_by_id.get("blk_4674")
    check("cfg:boundary-branch-block", boundary_block is not None
          and boundary_block.terminal.address == EXPECTED_BOUNDARY_SITE
          and boundary_block.terminal_flow() is InstructionFlow.BRANCH)
    check("cfg:boundary-target-is-self",
          boundary_block.terminal.direct_target == EXPECTED_BOUNDARY_SITE)
    boundary_not_taken = next(
        successor for successor in boundary_block.successors
        if successor.kind.value == "BRANCH_NOT_TAKEN")
    check("cfg:boundary-not-taken-is-delay-slot",
          boundary_not_taken.target_address == EXPECTED_BOUNDARY_SITE + 4)
    delay_block = block_by_id.get(f"blk_{EXPECTED_BOUNDARY_SITE + 4:x}")
    check("cfg:boundary-delay-block-terminal",
          delay_block is not None and delay_block.entry_address == EXPECTED_BOUNDARY_SITE + 4)
    check("cfg:boundary-delay-block-no-out-of-region-edge",
          all(successor.target_address != EXPECTED_BOUNDARY_SUCCESSOR
              for successor in delay_block.successors))

    delay_set = {item["delay"] for item in structure.delay_slot_frontier}
    check("cfg:no-direct-target-into-delay-slot", all(
        successor.target_address not in delay_set
        for block in blocks for successor in block.successors
        if successor.resolved and successor.kind.value in ("BRANCH_TAKEN", "JUMP")))
    check("cfg:call-return-is-own-delay-slot", all(
        successor.target_address == block.terminal.address + 4
        for block in blocks for successor in block.successors
        if successor.resolved and successor.kind.value == "CALL_RETURN"))

    payload = {
        "stage": STAGE,
        "entry_block": "blk_4650",
        "blocks": [{
            "id": block.id,
            "entry_address": hexv(block.entry_address),
            "evidence": block.evidence.value,
            "instruction_count": len(block.instructions),
            "terminal": {
                "address": hexv(block.terminal.address),
                "op": block.terminal.op,
                "flow": block.terminal.flow.value,
                "direct_target": hexv(block.terminal.direct_target)
                if block.terminal.direct_target is not None else None,
            },
            "successors": [{
                "kind": successor.kind.value,
                "target_block": successor.target_block,
                "target_address": hexv(successor.target_address)
                if successor.target_address is not None else None,
                "resolved": successor.resolved,
                "evidence": successor.evidence.value,
            } for successor in block.successors],
        } for block in blocks],
        "edge_histogram": summary["edge_histogram"],
        "resolved_edges": summary["resolved_edges"],
        "unresolved_edges": summary["unresolved_edges"],
        "orphan_delay_blocks": [hexv(address) for address in orphan_entries],
        "delay_slot_frontier": [{
            "owner": hexv(item["owner"]),
            "owner_op": item["owner_op"],
            "owner_terminator": item["owner_terminator"],
            "delay": hexv(item["delay"]),
            "delay_op": item["delay_op"],
        } for item in structure.delay_slot_frontier],
        "delay_slot_policy": (
            "the shared neutral layers have no MIPS32 delay-slot concept: call "
            "delay slots are the CALL_RETURN continuation, branch delay slots are "
            "the BRANCH_NOT_TAKEN successor, and jump/return/indirect-jump delay "
            "slots are explicit orphan blocks neither owned by a function nor "
            "silently dropped; true delay-slot execution semantics stay in the "
            "P3-03/P3-04 frontier and the later runtime stages"
        ),
    }
    payload["blocks_sha256"] = sha256_bytes(canonical_json_bytes(payload["blocks"]))
    ARTIFACTS[CFG_JSON] = evidence_json_bytes(payload)
    FINDINGS["cfg"] = {
        "block_count": len(blocks),
        "edge_histogram": summary["edge_histogram"],
        "resolved_edges": summary["resolved_edges"],
        "unresolved_edges": summary["unresolved_edges"],
        "orphan_delay_blocks": len(orphan_entries),
        "blocks_sha256": payload["blocks_sha256"],
    }
    return payload


# ---------------------------------------------------------------------------
# Functions, call graph, translation units
# ---------------------------------------------------------------------------
def audit_functions(structure) -> dict[str, Any]:
    discovery = structure.discovery
    functions = discovery.functions
    check("functions:count", len(functions) == EXPECTED_FUNCTION_COUNT)
    check("functions:entries-exact",
          tuple(function.entry_address for function in functions) == EXPECTED_FUNCTION_ENTRIES)
    check("functions:all-proven",
          all(function.evidence is EvidenceClass.PROVEN for function in functions))
    check("functions:entry-function",
          discovery.entry_function_id == "fn_4650"
          and functions[-1].entry_sources == ("PROGRAM_ENTRY",))
    check("functions:direct-call-provenance", all(
        "DIRECT_CALL" in function.entry_sources
        for function in functions if function.id != "fn_4650"))
    check("functions:no-suppressed-entries", not discovery.suppressed_entries)
    check("functions:no-shared-blocks", not discovery.shared_blocks)
    check("functions:no-external-targets", not discovery.external_direct_call_targets)
    check("functions:unresolved-call-sites",
          all(not function.unresolved_call_sites for function in functions))
    check("functions:bodies-non-empty", all(function.blocks for function in functions))
    check("functions:partition",
          len({block.id for function in functions for block in function.blocks})
          == EXPECTED_BLOCK_COUNT - EXPECTED_ORPHAN_DELAY_SLOTS)
    check("functions:owned-plus-orphans-is-all",
          len({block.id for function in functions for block in function.blocks})
          + len(discovery.unowned_blocks) == EXPECTED_BLOCK_COUNT)
    check("functions:callees-declared", all(
        callee in {function.id for function in functions}
        for function in functions for callee in function.direct_callees))

    unresolved_by_function: dict[str, tuple[int, ...]] = {}
    for unit in structure.units.units:
        if unit.unresolved_jump_sites:
            unresolved_by_function[unit.function_id] = tuple(
                site.address for site in unit.unresolved_jump_sites)
    check("functions:unresolved-jump-sites",
          unresolved_by_function == EXPECTED_JUMP_SITES_BY_FUNCTION)
    check("functions:unresolved-jump-reasons", all(
        site.reason == "unresolved indirect jump target" and site.op == "jr"
        for unit in structure.units.units for site in unit.unresolved_jump_sites))
    check("functions:provenance-retained", all(
        discovery.basis(function.id) for function in functions))

    rows = [{
        "function": function.id,
        "entry_address": hexv(function.entry_address),
        "evidence": function.evidence.value,
        "entry_sources": list(function.entry_sources),
        "provenance": [basis.to_document() for basis in discovery.basis(function.id)],
        "blocks": [block.id for block in function.blocks],
        "instruction_count": sum(len(block.instructions) for block in function.blocks),
        "direct_callees": sorted(function.direct_callees),
        "unresolved_call_sites": [site.to_document() for site in function.unresolved_call_sites],
        "unresolved_jump_sites": [site.to_document() for site in structure.units.unit_for(function.id).unresolved_jump_sites],
    } for function in functions]
    payload = {
        "stage": STAGE,
        "entry_function": discovery.entry_function_id,
        "functions": rows,
        "functions_sha256": sha256_bytes(canonical_json_bytes(rows)),
        "suppressed_entries": [item.to_document() for item in discovery.suppressed_entries],
        "shared_blocks": [item.to_document() for item in discovery.shared_blocks],
        "external_direct_call_targets": [
            item.to_document() for item in discovery.external_direct_call_targets],
        "unowned_blocks": list(discovery.unowned_blocks),
        "unowned_policy": (
            "orphan delay-slot blocks of jump/return/indirect-jump transfers are "
            "structurally unreachable in the neutral CFG; they are reported, never "
            "attributed to a function and never given an invented predecessor"
        ),
        "fingerprints": {
            "discovery": discovery.fingerprint(),
            "program_model": discovery.to_program_model().fingerprint(),
        },
    }
    ARTIFACTS[FUNCTIONS_JSON] = evidence_json_bytes(payload)
    FINDINGS["functions"] = {
        "count": len(rows),
        "entry_function": discovery.entry_function_id,
        "unresolved_jump_sites": unresolved_by_function,
        "functions_sha256": payload["functions_sha256"],
        "discovery_fingerprint": payload["fingerprints"]["discovery"],
        "program_model_fingerprint": payload["fingerprints"]["program_model"],
    }
    return payload


def audit_call_graph(structure) -> dict[str, Any]:
    graph = structure.call_graph
    check("callgraph:node-count", len(graph.nodes) == EXPECTED_FUNCTION_COUNT)
    check("callgraph:edge-count", len(graph.edges) == EXPECTED_CALL_GRAPH_EDGES)
    check("callgraph:all-internal",
          len(graph.internal_edges()) == EXPECTED_CALL_GRAPH_EDGES
          and not graph.external_edges() and not graph.unresolved_edges())
    check("callgraph:node-function-match",
          {node.function_id for node in graph.nodes}
          == {function.id for function in structure.discovery.functions})
    check("callgraph:entry-function", graph.entry_function == "fn_4650")
    check("callgraph:no-recursion", not graph.recursive_functions()
          and not graph.mutual_recursion_components())

    site_by_address = {site.address: site for site in structure.cfg.direct_call_sites}
    check("callgraph:edges-match-call-sites",
          len(site_by_address) == EXPECTED_CALL_GRAPH_EDGES)
    check("callgraph:edge-evidence-proven",
          all(edge.evidence is EvidenceClass.PROVEN for edge in graph.edges))
    check("callgraph:edge-sites-resolve", all(
        edge.call_site_address in site_by_address
        and site_by_address[edge.call_site_address].target_address
        == structure.discovery.function(edge.callee).entry_address
        for edge in graph.internal_edges()))
    check("callgraph:function-callee-consistency", all(
        set(function.direct_callees) == set(graph.callees(function.id))
        for function in structure.discovery.functions))

    rows = [edge.to_document() for edge in graph.edges]
    payload = {
        "stage": STAGE,
        "call_graph_version": "1.0.0",
        "entry_function": graph.entry_function,
        "nodes": [node.to_document() for node in graph.nodes],
        "edges": rows,
        "edges_sha256": sha256_bytes(canonical_json_bytes(rows)),
        "counts": {
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "internal_direct": len(graph.internal_edges()),
            "external_direct": len(graph.external_edges()),
            "unresolved_indirect": len(graph.unresolved_edges()),
        },
        "recursive_functions": list(graph.recursive_functions()),
        "mutual_recursion_components": [list(component)
                                        for component in graph.mutual_recursion_components()],
        "fingerprint": graph.fingerprint(),
        "policy": (
            "direct calls only; the three reachable jr $at jump tables are not call "
            "sites and are not upgraded into call-graph edges; no indirect target is "
            "guessed and no external call target exists in the audited frontier"
        ),
    }
    ARTIFACTS[CALL_GRAPH_JSON] = evidence_json_bytes(payload)
    FINDINGS["call_graph"] = {
        "counts": payload["counts"],
        "edges_sha256": payload["edges_sha256"],
        "fingerprint": payload["fingerprint"],
    }
    return payload


def audit_translation_units(structure) -> dict[str, Any]:
    units = structure.units
    check("units:count", len(units.units) == EXPECTED_UNIT_COUNT)
    check("units:one-to-one-functions",
          units.function_ids() == tuple(
              function.id for function in structure.discovery.functions))
    check("units:entry-unit", units.entry_unit == EXPECTED_ENTRY_UNIT)
    check("units:call-edges-match", all(
        tuple(edge.identity() for edge in unit.call_edges)
        == tuple(edge.identity() for edge in structure.call_graph.edges_from(unit.function_id))
        for unit in units.units))
    check("units:direct-callees-match", all(
        set(unit.direct_callees)
        == set(structure.call_graph.callees(unit.function_id))
        for unit in units.units))
    check("units:no-unresolved-call-sites",
          all(not unit.unresolved_call_sites for unit in units.units))
    check("units:no-unowned-control-flow", not units.unowned_control_flow)
    check("units:unowned-blocks-match",
          units.unowned_blocks == structure.discovery.unowned_blocks)
    check("units:no-shared/suppressed/external",
          not units.shared_blocks and not units.suppressed_entries
          and not units.external_direct_call_targets)
    check("units:provenance-retained", all(
        len(unit.provenance) == len(structure.discovery.basis(unit.function_id))
        for unit in units.units))
    check("units:block-ownership-partition",
          len({block.id for unit in units.units for block in unit.blocks})
          == EXPECTED_BLOCK_COUNT - EXPECTED_ORPHAN_DELAY_SLOTS)
    check("units:canonical-block-order", all(
        unit.blocks[0].entry_address == unit.entry_address for unit in units.units))

    rows = [{
        "unit_id": unit.unit_id,
        "function_id": unit.function_id,
        "entry_address": hexv(unit.entry_address),
        "evidence": unit.evidence.value,
        "entry_sources": list(unit.entry_sources),
        "block_count": len(unit.blocks),
        "instruction_count": sum(len(block.instructions) for block in unit.blocks),
        "direct_callees": sorted(unit.direct_callees),
        "call_edge_count": len(unit.call_edges),
        "unresolved_call_sites": [site.to_document() for site in unit.unresolved_call_sites],
        "unresolved_jump_sites": [
            {**site.to_document(), "target_resolution": "not statically resolved; no target invented"}
            for site in unit.unresolved_jump_sites
        ],
    } for unit in units.units]
    payload = {
        "stage": STAGE,
        "translation_unit_set_version": "1.0.0",
        "entry_unit": units.entry_unit,
        "units": rows,
        "units_sha256": sha256_bytes(canonical_json_bytes(rows)),
        "residual_evidence": {
            "shared_blocks": [item.to_document() for item in units.shared_blocks],
            "suppressed_entries": [item.to_document() for item in units.suppressed_entries],
            "unowned_blocks": list(units.unowned_blocks),
            "external_direct_call_targets": [
                item.to_document() for item in units.external_direct_call_targets],
            "unowned_control_flow": [item.to_document() for item in units.unowned_control_flow],
        },
        "fingerprint": units.fingerprint(),
        "policy": (
            "translation units are a structural packaging boundary only: no "
            "instruction is lowered, no indirect target is resolved, and the "
            "unresolved jr $at sites stay attached to their owning units"
        ),
    }
    ARTIFACTS[UNITS_JSON] = evidence_json_bytes(payload)
    FINDINGS["translation_units"] = {
        "count": len(rows),
        "entry_unit": units.entry_unit,
        "units_sha256": payload["units_sha256"],
        "fingerprint": payload["fingerprint"],
        "unresolved_jump_sites": {
            unit.function_id: [site.address for site in unit.unresolved_jump_sites]
            for unit in units.units if unit.unresolved_jump_sites
        },
    }
    return payload


# ---------------------------------------------------------------------------
# Serialization round-trips
# ---------------------------------------------------------------------------
def audit_roundtrip(structure) -> dict[str, Any]:
    program_model = structure.discovery.to_program_model()
    cfg = structure.cfg
    call_graph = structure.call_graph
    units = structure.units

    program_bytes = program_model.serialize()
    program_again = ProgramModel.deserialize(program_bytes)
    check("roundtrip:program-model-bytes",
          program_again.serialize() == program_bytes)
    check("roundtrip:program-model-fingerprint",
          program_again.fingerprint() == program_model.fingerprint())

    cfg_bytes = cfg.serialize()
    cfg_again = ControlFlowGraph.deserialize(cfg_bytes)
    check("roundtrip:cfg-bytes", cfg_again.serialize() == cfg_bytes)
    check("roundtrip:cfg-fingerprint", cfg_again.fingerprint() == cfg.fingerprint())

    graph_bytes = call_graph.serialize()
    graph_again = CallGraph.deserialize(graph_bytes)
    check("roundtrip:call-graph-bytes", graph_again.serialize() == graph_bytes)
    check("roundtrip:call-graph-fingerprint",
          graph_again.fingerprint() == call_graph.fingerprint())

    units_bytes = units.serialize()
    units_again = TranslationUnitSet.deserialize(units_bytes)
    check("roundtrip:units-bytes", units_again.serialize() == units_bytes)
    check("roundtrip:units-fingerprint", units_again.fingerprint() == units.fingerprint())

    owned = {
        instruction.address: instruction
        for function in structure.discovery.functions
        for block in function.blocks
        for instruction in block.instructions
    }
    roundtripped = {
        instruction.address: instruction
        for function in program_again.functions
        for block in function.blocks
        for instruction in block.instructions
    }
    check("roundtrip:owned-instruction-partition",
          len(owned) == EXPECTED_INSTRUCTION_COUNT - EXPECTED_ORPHAN_DELAY_SLOTS
          and len(roundtripped) == len(owned))
    check("roundtrip:instruction-identity-preserved", all(
        roundtripped[address].stable_key() == instruction.stable_key()
        for address, instruction in owned.items()))
    check("roundtrip:orphan-blocks-excluded", all(
        address not in roundtripped for address in (
            block.entry_address for block in structure.cfg.blocks
            if block.id in set(structure.discovery.unowned_blocks)))
          and all(len(block.instructions) == 1 for block in structure.cfg.blocks
                  if block.id in set(structure.discovery.unowned_blocks)))
    cfg_roundtrip = {
        instruction.address
        for block in cfg_again.blocks for instruction in block.instructions
    }
    check("roundtrip:cfg-covers-all-instructions",
          cfg_roundtrip == {instruction.address for instruction in structure.instructions})
    check("roundtrip:evidence-preserved", all(
        instruction.evidence is EvidenceClass.PROVEN
        for function in program_again.functions
        for block in function.blocks
        for instruction in block.instructions))
    check("roundtrip:unresolved-preserved", tuple(sorted(
        instruction.address for function in program_again.functions
        for block in function.blocks
        for instruction in block.instructions
        if instruction.unresolved)) == EXPECTED_REACHABLE_INDIRECT_JR)
    check("roundtrip:unresolved-inventory", tuple(sorted(
        item["address"] for item in program_again.unresolved_inventory()
    )) == EXPECTED_REACHABLE_INDIRECT_JR)
    check("roundtrip:direct-call-graph-stable",
          program_again.direct_call_graph() == program_model.direct_call_graph())

    payload = {
        "stage": STAGE,
        "program_model": {
            "bytes": len(program_bytes),
            "fingerprint": program_model.fingerprint(),
            "roundtrip_identical": True,
        },
        "cfg": {
            "bytes": len(cfg_bytes),
            "fingerprint": cfg.fingerprint(),
            "roundtrip_identical": True,
        },
        "call_graph": {
            "bytes": len(graph_bytes),
            "fingerprint": call_graph.fingerprint(),
            "roundtrip_identical": True,
        },
        "translation_units": {
            "bytes": len(units_bytes),
            "fingerprint": units.fingerprint(),
            "roundtrip_identical": True,
        },
        "policy": (
            "canonical serialization reconstructs an equal model; PROVEN/CANDIDATE "
            "classification, unresolved flags and indirect sites survive unchanged"
        ),
    }
    ARTIFACTS[ROUNDTRIP_JSON] = evidence_json_bytes(payload)
    FINDINGS["roundtrip"] = payload
    return payload


# ---------------------------------------------------------------------------
# Fail-closed negatives on synthetic frontier records
# ---------------------------------------------------------------------------
def error_code(action) -> str:
    try:
        action()
    except StructureError as exc:
        return exc.code
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        return f"UNEXPECTED_{type(exc).__name__}"
    return "NONE"


def _record(word: int, address: int = 0x8000) -> dict[str, Any]:
    return classify(address, word)


def _mutated(word: int, **overrides: Any) -> dict[str, Any]:
    record = dict(_record(word))
    record.update(overrides)
    return record


def _tiny_analysis(records: list[dict[str, Any]], reachable: list[int],
                   start: int, end: int, entry: int) -> dict[str, Any]:
    return {
        "region": {"start": start, "end": end, "words": (end - start) // 4},
        "entry": entry,
        "records": records,
        "reachable_addresses": reachable,
        "unreachable_addresses": sorted(
            address for address in range(start, end, 4) if address not in reachable),
        "delay_slots": [],
        "control_flow": {},
        "unresolved": [],
        "exception_sites": [],
        "diagnostics": {},
    }


NOP = 0x00000000
ADDIU = 0x24220001
JR_RA = 0x03E00008
BEQ = 0x10800001
J = 0x08002000
JAL = 0x0C002000
BTLZL = 0x04020000
SYSCALL = 0x0000000C
PADDING_WORD = 0x04170001


def audit_negatives() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []

    def expect(name: str, expected: str, action) -> None:
        actual = error_code(action)
        cases.append({"fixture": name, "expected_code": expected, "actual_code": actual,
                      "status": "PASS" if actual == expected else "FAIL"})

    expect("misaligned-record-address", "INVALID_RECORD_ADDRESS",
           lambda: flow_for_record(_mutated(NOP, address=0x8002)))
    expect("reachable-reserved-encoding", "REACHABLE_INVALID_ENCODING",
           lambda: flow_for_record(_record(PADDING_WORD)))
    expect("non-control-with-terminator", "INCONSISTENT_TERMINATOR",
           lambda: flow_for_record(_mutated(NOP, terminator="jump")))
    expect("non-control-with-target", "INCONSISTENT_TARGET",
           lambda: flow_for_record(_mutated(NOP, target=0x8000)))
    expect("non-control-with-delay-slot", "INCONSISTENT_DELAY_SLOT",
           lambda: flow_for_record(_mutated(NOP, delay_slot=True)))
    expect("unknown-exception-transfer", "UNKNOWN_EXCEPTION_TRANSFER",
           lambda: flow_for_record(_mutated(NOP, exception_transfer=True)))
    expect("branch-without-target", "MISSING_BRANCH_TARGET",
           lambda: flow_for_record(_mutated(BEQ, target=None)))
    expect("jump-without-target", "MISSING_JUMP_TARGET",
           lambda: flow_for_record(_mutated(J, target=None)))
    expect("call-without-target", "MISSING_CALL_TARGET",
           lambda: flow_for_record(_mutated(JAL, target=None)))
    expect("jump-without-delay-slot", "MISSING_DELAY_SLOT",
           lambda: flow_for_record(_mutated(J, delay_slot=False)))
    expect("return-with-target", "RETURN_WITH_TARGET",
           lambda: flow_for_record(_mutated(JR_RA, target=0x8000)))
    expect("indirect-jump-with-target", "INDIRECT_JUMP_WITH_TARGET",
           lambda: flow_for_record(_mutated(0x00200008, target=0x8000)))
    expect("indirect-call-with-target", "INDIRECT_CALL_WITH_TARGET",
           lambda: flow_for_record(_mutated(0x0320F809, target=0x8000)))
    expect("unsupported-control-transfer", "UNSUPPORTED_CONTROL_TRANSFER",
           lambda: flow_for_record(_record(BTLZL)))
    expect("external-trap-with-target", "INCONSISTENT_TRAP",
           lambda: flow_for_record(_mutated(SYSCALL, target=0x8000)))
    expect("unknown-terminator", "UNKNOWN_TERMINATOR",
           lambda: flow_for_record(_mutated(BEQ, terminator="mystery")))
    expect("missing-operands", "MISSING_OPERANDS",
           lambda: neutral_instruction({**_record(NOP), "operands": None}))

    tiny_records = [_record(word, 0x1000 + index * 4)
                    for index, word in enumerate((NOP, ADDIU, JR_RA, NOP))]
    tiny_reachable = [0x1000, 0x1004, 0x1008, 0x100C]
    expect("duplicate-record", "DUPLICATE_RECORD",
           lambda: analyze_structure(
               _tiny_analysis(tiny_records + [tiny_records[0]], tiny_reachable,
                              0x1000, 0x1010, 0x1000),
               source=make_source(), entry=0x1000))
    expect("inconsistent-region-missing-word", "INCONSISTENT_REGION",
           lambda: analyze_structure(
               _tiny_analysis(tiny_records[:-1], tiny_reachable,
                              0x1000, 0x1010, 0x1000),
               source=make_source(), entry=0x1000))
    expect("inconsistent-region-unaligned", "INVALID_REGION",
           lambda: analyze_structure(
               _tiny_analysis(tiny_records, tiny_reachable, 0x1002, 0x1012, 0x1002),
               source=make_source(), entry=0x1000))
    expect("entry-outside-region", "ENTRY_OUTSIDE_REGION",
           lambda: analyze_structure(
               _tiny_analysis(tiny_records, tiny_reachable, 0x1000, 0x1010, 0x1020),
               source=make_source(), entry=0x1020))
    expect("entry-above-declared-region", "ENTRY_OUTSIDE_REGION",
           lambda: analyze_structure(
               _tiny_analysis(tiny_records, tiny_reachable, 0x1000, 0x1010, 0x1000),
               source=make_source(), entry=0x2000))
    expect("invalid-reachable-address", "INVALID_REACHABLE_ADDRESS",
           lambda: analyze_structure(
               _tiny_analysis(tiny_records, [0x1000, 0x9999], 0x1000, 0x1010, 0x1000),
               source=make_source(), entry=0x1000))
    expect("invalid-source", "INVALID_SOURCE",
           lambda: analyze_structure(
               _tiny_analysis(tiny_records, tiny_reachable, 0x1000, 0x1010, 0x1000),
               source="not-a-source", entry=0x1000))
    expect("invalid-entry", "INVALID_ENTRY",
           lambda: analyze_structure(
               _tiny_analysis(tiny_records, tiny_reachable, 0x1000, 0x1010, 0x1000),
               source=make_source(), entry=0x1002))
    expect("invalid-analysis", "INVALID_ANALYSIS",
           lambda: analyze_structure("not-an-analysis", source=make_source(), entry=0x1000))

    synthetic = analyze_structure(
        _tiny_analysis(tiny_records, tiny_reachable, 0x1000, 0x1010, 0x1000),
        source=make_source(), entry=0x1000)
    synthetic_ok = (
        len(synthetic.instructions) == 4
        and len(synthetic.cfg.blocks) == 2
        and len(synthetic.discovery.functions) == 1
        and synthetic.discovery.functions[0].entry_sources == ("PROGRAM_ENTRY",)
        and tuple(sorted(synthetic.discovery.unowned_blocks)) == ("blk_100c",)
        and synthetic.instructions[2].flow is InstructionFlow.RETURN
    )
    cases.append({
        "fixture": "synthetic-positive-mini-program",
        "expected_code": None,
        "actual_code": None,
        "status": "PASS" if synthetic_ok else "FAIL",
    })

    cross_branch = analyze_structure(
        _tiny_analysis(
            [_record(BEQ, 0x1000), _record(NOP, 0x1004), _record(NOP, 0x1008),
             _record(JR_RA, 0x100C), _record(NOP, 0x1010)],
            [0x1000, 0x1004, 0x1008, 0x100C, 0x1010], 0x1000, 0x1014, 0x1000),
        source=make_source(), entry=0x1000)
    cross_branch_ok = (
        cross_branch.instructions[0].flow is InstructionFlow.BRANCH
        and cross_branch.instructions[0].direct_target == 0x1008
        and any(successor.kind.value == "BRANCH_NOT_TAKEN"
                for successor in cross_branch.cfg.block("blk_1000").successors))
    cases.append({
        "fixture": "synthetic-branch-target-continuation",
        "expected_code": None,
        "actual_code": None,
        "status": "PASS" if cross_branch_ok else "FAIL",
    })

    failures = [item for item in cases if item["status"] != "PASS"]
    for item in failures:
        print(f"NEGATIVE-FAILURE: {item}", flush=True)
    check("negatives:no-failures", not failures)
    check("negatives:count", len(cases) >= 25)
    payload = {"stage": STAGE, "cases": cases, "failed": len(failures)}
    ARTIFACTS[NEGATIVES_JSON] = evidence_json_bytes(payload)
    FINDINGS["negatives"] = {"count": len(cases), "failed": len(failures)}
    return payload


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def audit_determinism(data: bytes, structure, analysis: dict[str, Any]) -> None:
    second_ingest = ingest(bytes(data), MIPS32_O32)
    second_analysis = run_frontier(second_ingest)
    check("determinism:frontier-stable",
          canonical_json_bytes(analysis["summary"])
          == canonical_json_bytes(second_analysis["summary"]))
    check("determinism:records-stable",
          canonical_json_bytes(analysis["records"]) == canonical_json_bytes(second_analysis["records"]))
    rebuilt = build_structure(second_analysis)
    rebuilt_summary = structure_summary(rebuilt)
    first_summary = structure_summary(structure)
    check("determinism:structure-summary-stable",
          canonical_json_bytes(first_summary) == canonical_json_bytes(rebuilt_summary))
    check("determinism:program-model-fingerprint",
          rebuilt_summary["program_model_fingerprint"] == EXPECTED_PROGRAM_MODEL_FINGERPRINT
          and structure.discovery.to_program_model().fingerprint()
          == EXPECTED_PROGRAM_MODEL_FINGERPRINT)
    check("determinism:cfg-fingerprint",
          rebuilt_summary["cfg_fingerprint"] == EXPECTED_CFG_FINGERPRINT)
    check("determinism:call-graph-fingerprint",
          rebuilt_summary["call_graph_fingerprint"] == EXPECTED_CALL_GRAPH_FINGERPRINT)
    check("determinism:unit-set-fingerprint",
          rebuilt_summary["translation_unit_set_fingerprint"] == EXPECTED_UNIT_SET_FINGERPRINT)
    check("determinism:discovery-fingerprint",
          rebuilt_summary["discovery_fingerprint"] == EXPECTED_DISCOVERY_FINGERPRINT)

    artifact_hashes = {name: sha256_bytes(payload) for name, payload in sorted(ARTIFACTS.items())}
    record = {
        "source_sha256": sha256_bytes(data),
        "instruction_count": len(structure.instructions),
        "artifact_sha256": artifact_hashes,
        "fingerprints": {
            "program_model": structure.discovery.to_program_model().fingerprint(),
            "cfg": structure.cfg.fingerprint(),
            "call_graph": structure.call_graph.fingerprint(),
            "translation_units": structure.units.fingerprint(),
            "discovery": structure.discovery.fingerprint(),
        },
    }
    ARTIFACTS[DETERMINISM] = evidence_json_bytes(record)
    FINDINGS["determinism"] = record
    check("determinism:artifact-hashes-recorded", bool(artifact_hashes))


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
def write_evidence() -> dict[str, str]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for name, payload in sorted(ARTIFACTS.items()):
        (EVIDENCE_DIR / name).write_bytes(payload)
        hashes[name] = sha256_bytes(payload)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser(description="P3-05 real-ELF program structure gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-05")
    parser.add_argument("--elf", type=str,
                        default=os.environ.get("OPENRECOMP_P3_ELF", str(DEFAULT_ELF)))
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, ARTIFACTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    ARTIFACTS = {}
    elf_path = pathlib.Path(args.elf)
    if not elf_path.is_absolute():
        elf_path = (ROOT / elf_path).resolve()

    print("=== P3-05 Real-ELF Program Structure Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    evidence_files: dict[str, str] = {}
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("fixture")
        data, ingested, _ = audit_fixture(elf_path)
        banner("frontier")
        analysis = run_frontier(ingested)
        banner("p3_03 cross-check")
        audit_p3_03_cross_check(analysis, ingested)
        banner("p3_04 cross-check")
        audit_p3_04_cross_check(analysis)
        banner("structure")
        structure = build_structure(analysis)
        banner("neutral instructions")
        audit_instructions(structure, analysis, ingested)
        banner("unreachable frontier")
        audit_unreachable_frontier(structure, analysis)
        banner("cfg")
        audit_cfg(structure, ingested)
        banner("functions")
        audit_functions(structure)
        banner("call graph")
        audit_call_graph(structure)
        banner("translation units")
        audit_translation_units(structure)
        banner("roundtrip")
        audit_roundtrip(structure)
        banner("negatives")
        audit_negatives()
        banner("determinism")
        audit_determinism(data, structure, analysis)
        evidence_files = write_evidence()
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"
        status = "FAIL"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    result = {
        "stage": STAGE,
        "stage_name": FEATURE_MARKER,
        "status": status,
        "tests": passed,
        "passed": passed,
        "failed": failed,
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={passed}",
            "terminal": f"{TERMINAL_MARKER}=NOT_PROVEN",
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "evidence_files": evidence_files,
        "failure": failure,
    }
    payload = evidence_json_bytes(result)
    (EVIDENCE_DIR / RESULT_JSON).write_bytes(payload)

    print("\n=== RESULT ===")
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{TERMINAL_MARKER}=NOT_PROVEN")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FEATURE_MARKER}=FAIL")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
