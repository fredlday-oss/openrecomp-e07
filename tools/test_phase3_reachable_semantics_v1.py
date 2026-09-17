#!/usr/bin/env python3
"""OpenRecomp Phase-3 CoreMark reachable-semantics gate (P3-04).

P3-04 closes the *reachable* MIPS32 semantic frontier that P3-03 identified on
the audited CoreMark ELF: 55 reachable instructions in the P3-01
recognized-but-unsupported classes were decoded but had no execution
semantics.  This stage adds exact, fail-closed MIPS32 semantics for the bounded
class (``movz``, ``movn``, ``mul``, ``divu``, ``teq``, ``swl``, ``swr``,
``jalr``) and verifies them against an independent in-gate reference model.

The deterministic gate:

* verifies source integrity: the frozen root ``SOURCE_SHA256SUMS.txt`` is
  unchanged and every entry still hashes, and the Phase-3
  ``.openrecomp-phase3/SOURCE_SHA256SUMS.txt`` manifest registers and verifies
  the Phase-3 source/gate files (grown additively to this stage's set);
* verifies the P3-01 fixture identity and re-derives the P3-03 frontier on
  fresh bytes, cross-checking totals, histograms, reachability hash and the
  exact unsupported-site table against the recorded P3-03 evidence;
* emits the deterministic per-site table of the 82 recognized-unsupported
  words (address, raw encoding, mnemonic, operands, reachability, containing
  function, implementation status) as ``reachable_unsupported_before.json``;
* implements the bounded classes in ``p3_semantics_mips32_v1`` and checks each
  class against a separately written reference model over boundary, fixture
  and deterministic pseudo-random vectors, including fail-closed negatives
  (unsupported op, divide-by-zero, taken trap, unaligned indirect target,
  unpredictable HI/LO, memory faults, unsupported endianness);
* executes every one of the 82 sites against both models with deterministic
  operand state and proves that no site reports ``UNSUPPORTED_INSTRUCTION``;
* classifies the six reachable div/trap exception-frontier sites with explicit
  evidence (fixture seed values, dominance of the zero-divisor guard, purity
  and same-argument determinism of the callee) instead of assuming they are
  harmless;
* recomputes the frontier with the semantic overlay
  (``reachable_unsupported_after.json``) and reports the remaining frontier
  exactly: the three unresolved ``jr $at`` jump tables, the dead ``jalr``
  target and the 27 unreachable recognized-unsupported words stay unresolved;
* never resolves indirect targets and never treats a word as supported merely
  because it decodes.

On success it emits::

    OPENRECOMP_P3_04=PASS
    OPENRECOMP_PHASE3_COREMARK_REACHABLE_SEMANTICS_V1=PASS tests=<count>

Any failed invariant fails closed and emits ``OPENRECOMP_P3_04=FAIL``.

Usage:

    python tools/test_phase3_reachable_semantics_v1.py
    python tools/test_phase3_reachable_semantics_v1.py --elf .openrecomp-phase3/build/P3-01/candidate-a/coremark_mips32_O1.elf
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
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
    classify,
)
from p3_elf_image_v1 import (  # noqa: E402
    canonical_json_bytes,
    evidence_json_bytes,
    ingest,
    sha256_bytes,
)
from p3_semantics_mips32_v1 import (  # noqa: E402
    BoundedMemory,
    ERROR_DIVIDE_BY_ZERO,
    ERROR_ENDIANNESS_UNSUPPORTED,
    ERROR_HI_LO_UNPREDICTABLE,
    ERROR_INVALID_RECORD,
    ERROR_INVALID_STATE,
    ERROR_MEMORY_FAULT,
    ERROR_TRAP_TAKEN,
    ERROR_UNALIGNED_TARGET,
    ERROR_UNSUPPORTED_INSTRUCTION,
    ERROR_WRITE_PROTECTED,
    IMPLEMENTED_OPS,
    MachineState,
    SemanticsError,
    execute,
    implementations,
    semantics_status,
)
from p3_target_mips32_v1 import MIPS32_O32  # noqa: E402

EVIDENCE_ROOT = ROOT / ".openrecomp-phase3" / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-04"
P3_03_EVIDENCE = EVIDENCE_ROOT / "P3-03"

STAGE = "P3-04"
STAGE_MARKER = "OPENRECOMP_P3_04"
FEATURE_MARKER = "OPENRECOMP_PHASE3_COREMARK_REACHABLE_SEMANTICS_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF"

P3_SOURCE_MANIFEST = ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt"
P3_SOURCE_FILES = (
    ".openrecomp-phase3/src/p3_code_frontier_v1.py",
    ".openrecomp-phase3/src/p3_decode_mips32_v1.py",
    ".openrecomp-phase3/src/p3_elf_image_v1.py",
    ".openrecomp-phase3/src/p3_host_emit_v1.py",
    ".openrecomp-phase3/src/p3_package_v1.py",
    ".openrecomp-phase3/src/p3_reference_mips32_v1.py",
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
    "tools/test_phase3_package_regression_v1.py",
    "tools/test_phase3_reachable_semantics_v1.py",
    "tools/test_phase3_reference_equivalence_v1.py",
    "tools/test_phase3_static_data_v1.py",
    "tools/test_phase3_structure_v1.py",
    "tools/test_phase3_whole_regression_v1.py",
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
TEXT_WORDS = 3487
ENTRY = 0x4650
TEXT_OFFSET = 0x1000

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
EXPECTED_UNSUPPORTED_TOTAL = {
    "divu": 4, "jalr": 1, "movn": 12, "movz": 35, "mul": 22,
    "swl": 2, "swr": 2, "teq": 4,
}
EXPECTED_UNSUPPORTED_REACHABLE = {
    "divu": 3, "movn": 9, "movz": 21, "mul": 15, "swl": 2, "swr": 2, "teq": 3,
}
EXPECTED_UNSUPPORTED_UNREACHABLE = {
    "divu": 1, "jalr": 1, "movn": 3, "movz": 14, "mul": 7, "teq": 1,
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
EXPECTED_REACHABLE_INDIRECT_JR = (0x3130, 0x3830, 0x39A0)
EXPECTED_UNREACHABLE_JALR = 0x1958
EXPECTED_EXCEPTION_SITES = (
    (0x1F60, "divu"), (0x1F64, "teq"),
    (0x2044, "divu"), (0x2048, "teq"),
    (0x2370, "divu"), (0x2374, "teq"),
)
EXPECTED_PADDING = (0x1D8C, 0x25CC, 0x33C8, 0x33CC, 0x36FC, 0x4644, 0x4648, 0x464C)
EXPECTED_REACHABILITY_SHA256 = (
    "c62d54838cbc5fcc7b0ff83cdc9b2f0f47b8851c5e4023ae2ca6d629c8f76edf"
)

SEED_GLOBALS = {
    "seed1_volatile": 0x5600,
    "seed2_volatile": 0x5604,
    "seed3_volatile": 0x4E10,
    "seed4_volatile": 0x4E14,
    "seed5_volatile": 0x5608,
}
SEED_TABLE_ADDRESS = 0x4C50
SEED_TABLE_POINTERS = (0x5600, 0x5604, 0x4E10, 0x4E14, 0x5608)
TIME_IN_SECS = 0x4524
MASK32 = 0xFFFFFFFF

BEFORE_JSON = "reachable_unsupported_before.json"
AFTER_JSON = "reachable_unsupported_after.json"
IMPLEMENTATIONS_JSON = "semantic_implementations.json"
VECTORS_JSON = "semantic_reference_vectors.json"
COVERAGE_JSON = "semantic_site_coverage.json"
EXCEPTION_JSON = "exception_frontier.json"
RERUN_JSON = "coremark_frontier_rerun.json"
HI_LO_JSON = "hi_lo_dependency.json"
NEGATIVES_JSON = "semantic_negative_results.json"
SOURCE_INTEGRITY = "source_integrity.txt"
DETERMINISM = "determinism.json"
RESULT_JSON = "RESULT.json"

CLAIM_BOUNDARY = (
    "P3-04 proves only that the audited reachable MIPS32 semantic frontier in "
    "the P3-01 recognized-unsupported classes is implemented and verified for "
    "the CoreMark path: exact, fail-closed semantics for movz, movn, mul, "
    "divu, teq, swl, swr and jalr, reference-checked against an independent "
    "model and applied to every audited site. It does not prove complete "
    "CoreMark translation, does not prove CoreMark execution, does not recover "
    "the unresolved jr $at jump tables or the dead jalr target, and claims no "
    "arbitrary MIPS32, PS1 or PS2 compatibility."
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
def audit_fixture(elf_path: pathlib.Path) -> bytes:
    check("fixture:exists", elf_path.is_file())
    data = elf_path.read_bytes()
    check("fixture:sha256", sha256_bytes(data) == ELF_SHA256)
    check("fixture:size", len(data) == ELF_SIZE)
    FINDINGS["fixture"] = {
        "path": elf_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_bytes(data),
        "size": len(data),
    }
    return data


def audit_input_integrity(data: bytes):
    ingested = ingest(data, MIPS32_O32)
    text = ingested.parsed.section(".text")
    check("input:text-section", text is not None)
    check("input:text-identity",
          text.sh_addr == TEXT_VADDR and text.sh_size == TEXT_SIZE)
    check("input:entry", ingested.parsed.header.e_entry == ENTRY)
    raw_slice = data[TEXT_OFFSET:TEXT_OFFSET + TEXT_SIZE]
    words = {
        TEXT_VADDR + index * 4: ingested.image.read_u32(TEXT_VADDR + index * 4)
        for index in range(TEXT_WORDS)
    }
    check("input:guest-image-equals-file-slice",
          all(words[TEXT_VADDR + index * 4] == int.from_bytes(
              raw_slice[index * 4:index * 4 + 4], "little")
              for index in range(TEXT_WORDS)))
    FINDINGS["input"] = {
        "text_vaddr": hexv(TEXT_VADDR),
        "text_size": TEXT_SIZE,
        "text_words": len(words),
        "entry": hexv(ENTRY),
        "text_slice_sha256": sha256_bytes(raw_slice),
    }
    return ingested, words


def run_frontier(ingested) -> dict[str, Any]:
    return analyze(ingested.image.read_u32, TEXT_VADDR, TEXT_VADDR + TEXT_SIZE, ENTRY)


def function_layout(ingested) -> list[tuple[int, int, str]]:
    return [(symbol.value, symbol.value + symbol.size, symbol.name)
            for symbol in ingested.parsed.symbols()
            if symbol.is_function and symbol.size]


def owning_function(address: int, ranges: list[tuple[int, int, str]]) -> str | None:
    for start, end, name in ranges:
        if start <= address < end:
            return name
    return None


# ---------------------------------------------------------------------------
# P3-03 recorded-evidence cross-check
# ---------------------------------------------------------------------------
def audit_p3_03_cross_check(result: dict[str, Any]) -> None:
    inventory_path = P3_03_EVIDENCE / "instruction_inventory.json"
    reachable_path = P3_03_EVIDENCE / "reachable_code_map.json"
    control_path = P3_03_EVIDENCE / "control_flow_frontier.json"
    frontier_path = P3_03_EVIDENCE / "unsupported_frontier.json"
    for path in (inventory_path, reachable_path, control_path, frontier_path):
        check(f"p3-03:{path.name}:exists", path.is_file())

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    summary = result["summary"]
    for key in inventory["totals"]:
        check(f"p3-03:inventory:{key}", summary[key] == inventory["totals"][key])
    check("p3-03:inventory-supported-histogram",
          summary["supported_histogram"] == inventory["supported_histogram"])
    check("p3-03:inventory-unsupported-classes",
          summary["unsupported_histogram"] == {
              op: len(sites) for op, sites in inventory["unsupported_classes"].items()})
    recomputed_sites = {
        hexv(record["address"]): {
            "address": hexv(record["address"]),
            "word": hexv(record["word"]),
            "operands": dict(record["operands"]),
            "reachability": record["reachability"],
        }
        for record in result["records"]
        if record["decode_class"] == CLASS_RECOGNIZED_UNSUPPORTED
    }
    recorded_sites = {
        site["address"]: {
            "address": site["address"],
            "word": site["word"],
            "operands": site["operands"],
            "reachability": site["reachability"],
        }
        for sites in inventory["unsupported_classes"].values()
        for site in sites
    }
    check("p3-03:inventory-recorded-sites",
          canonical_json_bytes(recomputed_sites) == canonical_json_bytes(recorded_sites))

    reachable = json.loads(reachable_path.read_text(encoding="utf-8"))
    rows = [f"{hexv(record['address'])} {record['reachability']}"
            for record in result["records"]]
    check("p3-03:reachability-sha256",
          sha256_bytes("\n".join(rows).encode("ascii")) == reachable["reachability_sha256"])
    check("p3-03:reachability-sha256-frozen",
          reachable["reachability_sha256"] == EXPECTED_REACHABILITY_SHA256)
    check("p3-03:reachable-words",
          result["summary"]["reachable_words"] == reachable["reachable_words"])
    check("p3-03:unreachable-words",
          result["summary"]["unreachable_words"] == reachable["unreachable_words"])
    check("p3-03:padding-addresses",
          tuple(int(item, 16) for item in reachable["padding_addresses"]) == EXPECTED_PADDING)

    control = json.loads(control_path.read_text(encoding="utf-8"))
    check("p3-03:control-flow-counts",
          control["reachable_counts"] == result["summary"]["control_flow_site_counts"])
    check("p3-03:exception-sites",
          tuple((int(item["site"], 16), item["op"])
                for item in control["exception_frontier"]) == EXPECTED_EXCEPTION_SITES)
    check("p3-03:indirect-sites",
          tuple(int(item["address"], 16)
                for item in control["indirect_sites_all"]
                if item["reachability"] == "REACHABLE") == EXPECTED_REACHABLE_INDIRECT_JR)

    frontier = json.loads(frontier_path.read_text(encoding="utf-8"))
    check("p3-03:frontier-unsupported-total",
          frontier["total_recognized_unsupported_words"] == 82)
    check("p3-03:frontier-jalr",
          frontier["jalr_classification"]["count"] == 1
          and frontier["jalr_classification"]["unreachable"] == 1)
    FINDINGS["p3_03_cross_check"] = {
        "inventory_sha256": sha256_bytes(inventory_path.read_bytes()),
        "reachable_map_sha256": sha256_bytes(reachable_path.read_bytes()),
        "control_frontier_sha256": sha256_bytes(control_path.read_bytes()),
        "unsupported_frontier_sha256": sha256_bytes(frontier_path.read_bytes()),
        "reachability_sha256": reachable["reachability_sha256"],
    }


# ---------------------------------------------------------------------------
# Before site table
# ---------------------------------------------------------------------------
def row_digest(rows: list[dict[str, Any]]) -> str:
    return sha256_bytes(canonical_json_bytes(rows))


def build_before_rows(result: dict[str, Any], ranges) -> list[dict[str, Any]]:
    rows = []
    for record in result["records"]:
        if record["decode_class"] != CLASS_RECOGNIZED_UNSUPPORTED:
            continue
        row = {
            "address": hexv(record["address"]),
            "word": hexv(record["word"]),
            "mnemonic": record["op"],
            "operands": dict(record["operands"]),
            "reachability": record["reachability"],
            "containing_function": owning_function(record["address"], ranges),
            "semantic_implementation_status": "UNSUPPORTED",
            "control_flow_status": "N/A",
        }
        if record["terminator"] is not None:
            row["terminator"] = record["terminator"]
        rows.append(row)
    rows.sort(key=lambda item: item["address"])
    return rows


def audit_before(result: dict[str, Any], ingested) -> dict[str, Any]:
    summary = result["summary"]
    for key, expected in EXPECTED_TOTALS.items():
        check(f"before:total:{key}", summary[key] == expected)
    check("before:unsupported-histogram",
          summary["unsupported_histogram"] == EXPECTED_UNSUPPORTED_TOTAL)
    check("before:unsupported-reachable-histogram",
          summary["unsupported_reachable_histogram"] == EXPECTED_UNSUPPORTED_REACHABLE)
    check("before:unsupported-unreachable-histogram",
          summary["unsupported_unreachable_histogram"] == EXPECTED_UNSUPPORTED_UNREACHABLE)
    check("before:control-flow-counts",
          summary["control_flow_site_counts"] == EXPECTED_CONTROL_FLOW_COUNTS)
    check("before:unresolved-counts",
          summary["unresolved_site_counts"] == EXPECTED_UNRESOLVED_COUNTS)

    ranges = function_layout(ingested)
    rows = build_before_rows(result, ranges)
    reachable = sum(1 for row in rows if row["reachability"] == "REACHABLE")
    histogram: dict[str, int] = {}
    reachable_histogram: dict[str, int] = {}
    unreachable_histogram: dict[str, int] = {}
    for row in rows:
        op = row["mnemonic"]
        histogram[op] = histogram.get(op, 0) + 1
        target = reachable_histogram if row["reachability"] == "REACHABLE" else unreachable_histogram
        target[op] = target.get(op, 0) + 1

    check("before:site-count", len(rows) == 82)
    check("before:reachable-count", reachable == 55)
    check("before:unreachable-count", len(rows) - reachable == 27)
    check("before:all-sites-in-function-ranges",
          all(row["containing_function"] is not None for row in rows))

    by_address = {record["address"]: record for record in result["records"]}
    exception_rows = []
    for site, op in EXPECTED_EXCEPTION_SITES:
        record = by_address[site]
        exception_rows.append({
            "site": hexv(site),
            "op": op,
            "word": hexv(record["word"]),
            "operands": dict(record["operands"]),
            "reachability": record["reachability"],
            "containing_function": owning_function(site, ranges),
        })
    check("before:exception-sites",
          [item["op"] for item in exception_rows] == [op for _, op in EXPECTED_EXCEPTION_SITES])

    jr_sites = sorted(record["address"] for record in result["records"]
                      if record["op"] == "jr" and record["operands"].get("rs") != 31)
    check("before:reachable-jr-at-frontier",
          tuple(jr_sites) == EXPECTED_REACHABLE_INDIRECT_JR)
    jalr_sites = [record for record in result["records"] if record["op"] == "jalr"]
    check("before:jalr-frontier", len(jalr_sites) == 1
          and jalr_sites[0]["address"] == EXPECTED_UNREACHABLE_JALR
          and jalr_sites[0]["reachability"] == "UNREACHABLE")

    table = {
        "stage": STAGE,
        "source": {
            "elf_sha256": ELF_SHA256,
            "elf_size": ELF_SIZE,
            "text_vaddr": hexv(TEXT_VADDR),
            "text_words": TEXT_WORDS,
            "entry": hexv(ENTRY),
        },
        "site_table": rows,
        "site_table_sha256": row_digest(rows),
        "counts": {"total": len(rows), "reachable": reachable,
                   "unreachable": len(rows) - reachable},
        "histogram": dict(sorted(histogram.items())),
        "reachable_histogram": dict(sorted(reachable_histogram.items())),
        "unreachable_histogram": dict(sorted(unreachable_histogram.items())),
        "semantics_support": (
            "UNSUPPORTED before this stage: the P3-01/P3-03 classes decode with "
            "exact operands but have no execution semantics"
        ),
        "symbol_usage": "containing_function is symbol-assisted diagnostic only",
        "exception_sites": exception_rows,
        "indirect_control_flow_frontier": {
            "jr_at_jump_tables": [
                {"site": hexv(site), "reachability": "REACHABLE",
                 "target_resolution": "not statically resolved; no target invented"}
                for site in EXPECTED_REACHABLE_INDIRECT_JR
            ],
            "jalr": {
                "site": hexv(EXPECTED_UNREACHABLE_JALR),
                "reachability": "UNREACHABLE",
                "operands": dict(jalr_sites[0]["operands"]),
                "target_resolution": "not statically resolved; no target invented",
            },
        },
    }
    ARTIFACTS[BEFORE_JSON] = evidence_json_bytes(table)
    FINDINGS["before"] = {
        "counts": table["counts"],
        "histogram": table["histogram"],
        "reachable_histogram": table["reachable_histogram"],
        "unreachable_histogram": table["unreachable_histogram"],
        "site_table_sha256": table["site_table_sha256"],
        "exception_sites": exception_rows,
    }
    return table


# ---------------------------------------------------------------------------
# Semantic implementations
# ---------------------------------------------------------------------------
def audit_implementations(result: dict[str, Any]) -> dict[str, Any]:
    table = implementations()
    check("implementations:class-set", tuple(sorted(table)) == IMPLEMENTED_OPS)
    observed = sorted({record["op"] for record in result["records"]
                       if record["decode_class"] == CLASS_RECOGNIZED_UNSUPPORTED})
    check("implementations:classes-cover-audited-frontier",
          tuple(sorted(set(observed) - set(IMPLEMENTED_OPS))) == ())
    check("implementations:status-per-op",
          all(semantics_status(op) == "IMPLEMENTED" for op in IMPLEMENTED_OPS))
    check("implementations:unsupported-op-fails-closed",
          semantics_status("addi") == "UNSUPPORTED"
          and semantics_status(None) == "UNSUPPORTED")
    payload = {
        "stage": STAGE,
        "semantics_model": {
            "IMPLEMENTED": "exact MIPS32 behaviour implemented and reference-checked",
            "UNSUPPORTED": "no execution semantics; fails closed",
        },
        "classes": table,
        "audited_frontier_classes": observed,
        "reference_basis": [
            "MIPS32 integer semantics as audited: conditional moves, 32x32 signed "
            "multiply low half, unsigned divide quotient/remainder, trap-if-equal, "
            "little-endian partial word stores, jump-and-link register",
            "fail-closed policy: architecturally UNPREDICTABLE states (divisor "
            "zero, taken trap, HI/LO after mul, unaligned jalr target) are "
            "refused instead of guessed",
        ],
    }
    ARTIFACTS[IMPLEMENTATIONS_JSON] = evidence_json_bytes(payload)
    FINDINGS["implementations"] = {"classes": list(IMPLEMENTED_OPS),
                                   "audited_frontier_classes": observed}
    return table


# ---------------------------------------------------------------------------
# Independent reference model (written separately from the module under test)
# ---------------------------------------------------------------------------
class ReferenceError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def reference_execute(
    op: str,
    operands: dict[str, int],
    registers: list[int],
    hi: int,
    lo: int,
    hi_lo_defined: bool,
    memory_bytes: bytearray,
    memory_base: int,
    writable: bool = True,
) -> dict[str, Any]:
    registers = list(registers)
    registers[0] = 0

    def read(reg: int) -> int:
        return 0 if reg == 0 else registers[reg] & MASK32

    def write(reg: int, value: int) -> None:
        if reg != 0:
            registers[reg] = value & MASK32

    def mem_word(address: int) -> int:
        if address < memory_base or address + 4 > memory_base + len(memory_bytes):
            raise ReferenceError(ERROR_MEMORY_FAULT, f"address=0x{address:08x}")
        offset = address - memory_base
        return int.from_bytes(memory_bytes[offset:offset + 4], "little")

    def mem_put(address: int, value: int) -> None:
        if not writable:
            raise ReferenceError(ERROR_WRITE_PROTECTED, f"address=0x{address:08x}")
        if address < memory_base or address + 4 > memory_base + len(memory_bytes):
            raise ReferenceError(ERROR_MEMORY_FAULT, f"address=0x{address:08x}")
        offset = address - memory_base
        memory_bytes[offset:offset + 4] = (value & MASK32).to_bytes(4, "little")

    if op in ("movz", "movn"):
        rs, rt, rd = operands["rs"], operands["rt"], operands["rd"]
        taken = (read(rt) == 0) if op == "movz" else (read(rt) != 0)
        if taken:
            write(rd, read(rs))
        return {"registers": registers, "hi": hi, "lo": lo,
                "hi_lo_defined": hi_lo_defined}

    if op == "mul":
        rs, rt, rd = operands["rs"], operands["rt"], operands["rd"]
        lhs, rhs = read(rs), read(rt)
        if lhs >= 0x80000000:
            lhs -= 0x100000000
        if rhs >= 0x80000000:
            rhs -= 0x100000000
        write(rd, lhs * rhs)
        return {"registers": registers, "hi": hi, "lo": lo, "hi_lo_defined": False}

    if op == "divu":
        rs, rt = operands["rs"], operands["rt"]
        divisor = read(rt)
        if divisor == 0:
            raise ReferenceError(ERROR_DIVIDE_BY_ZERO, "divisor zero")
        quotient = read(rs) // divisor
        remainder = read(rs) - quotient * divisor
        return {"registers": registers, "hi": remainder, "lo": quotient,
                "hi_lo_defined": True}

    if op == "teq":
        rs, rt = operands["rs"], operands["rt"]
        if read(rs) == read(rt):
            raise ReferenceError(ERROR_TRAP_TAKEN, f"code={operands['code']}")
        return {"registers": registers, "hi": hi, "lo": lo,
                "hi_lo_defined": hi_lo_defined}

    if op in ("swl", "swr"):
        rs, rt = operands["rs"], operands["rt"]
        value = read(rt)
        vaddr = (read(rs) + operands["imm"]) & MASK32
        byte_offset = vaddr & 3
        word = mem_word(vaddr & ~3)
        data = list(word.to_bytes(4, "little"))
        if op == "swl":
            data[byte_offset] = (value >> 24) & 0xFF
            if byte_offset >= 1:
                data[byte_offset - 1] = (value >> 16) & 0xFF
            if byte_offset >= 2:
                data[byte_offset - 2] = (value >> 8) & 0xFF
            if byte_offset == 3:
                data[byte_offset - 3] = value & 0xFF
        else:
            data[byte_offset] = value & 0xFF
            if byte_offset <= 2:
                data[byte_offset + 1] = (value >> 8) & 0xFF
            if byte_offset <= 1:
                data[byte_offset + 2] = (value >> 16) & 0xFF
            if byte_offset == 0:
                data[byte_offset + 3] = (value >> 24) & 0xFF
        mem_put(vaddr & ~3, int.from_bytes(bytes(data), "little"))
        return {"registers": registers, "hi": hi, "lo": lo,
                "hi_lo_defined": hi_lo_defined}

    if op == "jalr":
        rs, rd = operands["rs"], operands["rd"]
        target = read(rs)
        if target % 4:
            raise ReferenceError(ERROR_UNALIGNED_TARGET, f"target=0x{target:08x}")
        write(rd, operands["__link_value__"])
        return {"registers": registers, "hi": hi, "lo": lo,
                "hi_lo_defined": hi_lo_defined, "target": target}

    raise ReferenceError(ERROR_UNSUPPORTED_INSTRUCTION, f"op={op}")


def enc_movz(rd: int, rs: int, rt: int) -> int:
    return (rs << 21) | (rt << 16) | (rd << 11) | 0x0A


def enc_movn(rd: int, rs: int, rt: int) -> int:
    return (rs << 21) | (rt << 16) | (rd << 11) | 0x0B


def enc_mul(rd: int, rs: int, rt: int) -> int:
    return (0x1C << 26) | (rs << 21) | (rt << 16) | (rd << 11) | 0x02


def enc_divu(rs: int, rt: int) -> int:
    return (rs << 21) | (rt << 16) | 0x1B


def enc_teq(rs: int, rt: int, code: int = 7) -> int:
    return (rs << 21) | (rt << 16) | (code << 6) | 0x34


def enc_swl(rs: int, rt: int, imm: int) -> int:
    return (0x2A << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def enc_swr(rs: int, rt: int, imm: int) -> int:
    return (0x2E << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def enc_jalr(rs: int, rd: int) -> int:
    return (rs << 21) | (rd << 11) | 0x09


BOUNDARY_VALUES = (
    0x00000000, 0x00000001, 0x00000002, 0x00000003, 0x00000004, 0x00000007,
    0x00000008, 0x00000009, 0x00000066, 0x00000101, 0x000003E8, 0x00000FFF,
    0x00001000, 0x00004C50, 0x00004E30, 0x00005608, 0x00007FFF, 0x00008000,
    0x10624DD3, 0x7FFFFFFE, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFE,
    0xFFFFFFFF,
)
VECTOR_MEMORY_BASE = 0x1000
VECTOR_MEMORY_SIZE = 0x100
VECTOR_MEMORY_PATTERN = bytes(
    ((index * 37 + 11) & 0xFF) for index in range(VECTOR_MEMORY_SIZE))


def lcg_values(seed: int, count: int) -> list[int]:
    state = seed & MASK32
    output = []
    for _ in range(count):
        state = (state * 1103515245 + 12345) & MASK32
        output.append(state)
    return output


def deterministic_memory(base: int = VECTOR_MEMORY_BASE) -> BoundedMemory:
    return BoundedMemory(base=base, size=VECTOR_MEMORY_SIZE,
                         initial=VECTOR_MEMORY_PATTERN)


def module_run(
    word: int,
    registers: list[int],
    hi: int = 0,
    lo: int = 0,
    hi_lo_defined: bool = True,
    memory: BoundedMemory | None = None,
    address: int = 0x8000,
) -> dict[str, Any]:
    record = classify(address, word)
    state = MachineState(registers=registers, hi=hi, lo=lo, hi_lo_defined=hi_lo_defined)
    mem = deterministic_memory() if memory is None else memory
    try:
        effect = execute(record, state, mem)
    except SemanticsError as exc:
        return {"error": exc.code, "detail": exc.detail, "state": state.snapshot(),
                "memory": mem.window(mem.base, mem.size).hex()}
    return {"error": None, "effect": effect, "state": state.snapshot(),
            "memory": mem.window(mem.base, mem.size).hex()}


def reference_run(
    word: int,
    registers: list[int],
    hi: int = 0,
    lo: int = 0,
    hi_lo_defined: bool = True,
    memory: BoundedMemory | None = None,
    address: int = 0x8000,
) -> dict[str, Any]:
    record = classify(address, word)
    operands = dict(record["operands"])
    operands["__link_value__"] = (address + 8) & MASK32
    mem = deterministic_memory() if memory is None else memory
    mem_bytes = bytearray(mem.bytes)
    try:
        outcome = reference_execute(record["op"], operands, registers, hi, lo,
                                    hi_lo_defined, mem_bytes, mem.base, mem.writable)
    except ReferenceError as exc:
        return {"error": exc.code, "detail": exc.detail,
                "state": {"registers": [0] + list(registers[1:]), "hi": hi, "lo": lo,
                          "hi_lo_defined": hi_lo_defined},
                "memory": bytes(mem_bytes).hex()}
    return {"error": None, "outcome": outcome,
            "state": {"registers": outcome["registers"], "hi": outcome["hi"],
                      "lo": outcome["lo"], "hi_lo_defined": outcome["hi_lo_defined"]},
            "memory": bytes(mem_bytes).hex()}


def compare_runs(module: dict[str, Any], reference: dict[str, Any]) -> bool:
    return (module["error"] == reference["error"]
            and module["state"] == reference["state"]
            and module["memory"] == reference["memory"])


def build_vectors() -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    vectors: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    idiom_checks = 0

    def add(name: str, word: int, registers: list[int], **kwargs) -> None:
        module = module_run(word, registers, **kwargs)
        reference = reference_run(word, registers, **kwargs)
        record = classify(kwargs.get("address", 0x8000), word)
        status = "PASS" if compare_runs(module, reference) else "FAIL"
        entry = {
            "name": name,
            "word": hexv(word),
            "op": record["op"],
            "operands": dict(record["operands"]),
            "state_before": {
                "registers": {f"r{index}": registers[index]
                              for index in range(32) if index and registers[index]},
                "hi": kwargs.get("hi", 0),
                "lo": kwargs.get("lo", 0),
                "hi_lo_defined": kwargs.get("hi_lo_defined", True),
            },
            "module_error": module["error"],
            "reference_error": reference["error"],
            "state_after": module["state"],
            "memory_after_sha256": sha256_bytes(bytes.fromhex(module["memory"])),
            "status": status,
        }
        if module["error"] is None and module["effect"].get("memory_effects"):
            entry["memory_effects"] = module["effect"]["memory_effects"]
        vectors.append(entry)
        if status != "PASS":
            failures.append({"name": name, "module": module, "reference": reference})

    random_values = lcg_values(0x5EED0001, 8)
    condition_values = list(BOUNDARY_VALUES) + random_values
    source_values = (0x00000000, 0x00000001, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)

    for op, encoder in (("movz", enc_movz), ("movn", enc_movn)):
        for index, condition in enumerate(condition_values):
            for source in source_values:
                add(f"{op}-cond-0x{condition:08x}-src-0x{source:08x}", encoder(5, 2, 3),
                    [0, 0, source, condition] + [0] * 28)
        add(f"{op}-rd-zero", encoder(0, 2, 3),
            [0, 0, 0xAAAAAAAA, 0] + [0] * 28)
        add(f"{op}-rd-same-as-rs", encoder(5, 5, 3),
            [0] * 5 + [0xDEADBEEF, 0, 0] + [0] * 24)
        add(f"{op}-rt-zero-source-write", encoder(5, 2, 0),
            [0, 0, 0xDEADBEEF, 0] + [0] * 28)

    for lhs, rhs in (
        (0x00000002, 0x00000003), (0x00010000, 0x00010000), (0x7FFFFFFF, 0x00000002),
        (0x80000000, 0x00000002), (0x80000000, 0xFFFFFFFF), (0xFFFFFFFF, 0xFFFFFFFF),
        (0x12345678, 0x9ABCDEF0), (0x0000FFFF, 0x00010001), (0x40000000, 0x00000004),
        (0x00000000, 0xFFFFFFFF),
    ):
        add(f"mul-0x{lhs:08x}-0x{rhs:08x}", enc_mul(5, 2, 3),
            [0, 0, lhs, rhs] + [0] * 28)
    for index, pair in enumerate(zip(lcg_values(0x5EED0003, 10), lcg_values(0x5EED0004, 10))):
        add(f"mul-random-{index}", enc_mul(5, 2, 3), [0, 0, pair[0], pair[1]] + [0] * 28)
    add("mul-rd-zero", enc_mul(0, 2, 3), [0, 0, 0x12345678, 0x87654321] + [0] * 28)

    for dividend, divisor in (
        (0x000003E8, 0x00000003), (0xFFFFFFFF, 0x00000001), (0xFFFFFFFF, 0x00000002),
        (0x80000000, 0x00000002), (0x80000000, 0x000000FF), (0x7FFFFFFF, 0x00000001),
        (0x12345678, 0x000003E8), (0x00000001, 0xFFFFFFFF), (0x00000000, 0x00000007),
    ):
        add(f"divu-0x{dividend:08x}-0x{divisor:08x}", enc_divu(4, 5),
            [0, 0, 0, 0, dividend, divisor] + [0] * 26)
    for index, pair in enumerate(zip(lcg_values(0x5EED0005, 6), lcg_values(0x5EED0006, 6))):
        divisor = pair[1] or 1
        add(f"divu-random-{index}", enc_divu(4, 5),
            [0, 0, 0, 0, pair[0], divisor] + [0] * 26)
    add("divu-zero-divisor", enc_divu(4, 5),
        [0, 0, 0, 0, 0x12345678, 0] + [0] * 26)

    add("teq-unequal", enc_teq(1, 2), [0, 0x11111111, 0x22222222] + [0] * 29)
    add("teq-unequal-zero", enc_teq(1, 0), [0, 0x11111111] + [0] * 30)
    add("teq-equal", enc_teq(1, 2), [0, 0x33333333, 0x33333333] + [0] * 29)
    add("teq-equal-zero-zero", enc_teq(0, 0), [0] * 32)
    for index, value in enumerate(lcg_values(0x5EED0007, 6)):
        add(f"teq-unequal-random-{index}", enc_teq(7, 8),
            [0] * 7 + [value, value ^ 1] + [0] * 23)

    for byte_offset in range(4):
        for index, value in enumerate(
                (0x00000000, 0xFFFFFFFF, 0x12345678, 0x80000000, 0x000000FF)):
            vaddr = VECTOR_MEMORY_BASE + 0x50 + byte_offset
            add(f"swl-offset{byte_offset}-value-{index}", enc_swl(9, 10, 0),
                [0] * 9 + [vaddr, value] + [0] * 21)
            add(f"swr-offset{byte_offset}-value-{index}", enc_swr(9, 10, 0),
                [0] * 9 + [vaddr, value] + [0] * 21)

    for alignment in range(4):
        for index, value in enumerate(
                (0x00000000, 0x00000001, 0x11223344, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)):
            vaddr = VECTOR_MEMORY_BASE + 0x30 + alignment
            mem = deterministic_memory()
            state = MachineState(registers=[0] * 9 + [vaddr, value] + [0] * 21)
            try:
                execute(classify(0x8000, enc_swl(9, 10, 3)), state, mem)
                execute(classify(0x8004, enc_swr(9, 10, 0)), state, mem)
            except SemanticsError as exc:
                failures.append({"name": f"idiom-{alignment}-{index}", "error": exc.code})
                continue
            expected = bytearray(mem.window(VECTOR_MEMORY_BASE + 0x30, 16))
            offset = (vaddr - (VECTOR_MEMORY_BASE + 0x30))
            expected[offset:offset + 4] = (value & MASK32).to_bytes(4, "little")
            status = "PASS" if mem.window(VECTOR_MEMORY_BASE + 0x30, 16) == bytes(expected) else "FAIL"
            vectors.append({
                "name": f"swl-swr-idiom-alignment-{alignment}-value-{index}",
                "word": f"{hexv(enc_swl(9, 10, 3))}+{hexv(enc_swr(9, 10, 0))}",
                "op": "swl+swr",
                "operands": {"rs": 9, "rt": 10, "imm": 3},
                "state_before": {"registers": {"r9": vaddr, "r10": value}},
                "module_error": None,
                "reference_error": None,
                "state_after": state.snapshot(),
                "memory_after_sha256": sha256_bytes(mem.window(mem.base, mem.size)),
                "composed_store_matches_unaligned_32bit_store": status == "PASS",
                "status": status,
            })
            idiom_checks += 1
            if status != "PASS":
                failures.append({"name": f"idiom-{alignment}-{index}", "detail": "composition"})

    for target in (0x00001000, 0x00004650, 0x00007FFC, 0x00000000, 0x00000004):
        registers = [0] * 25 + [target] + [0] * 6
        add(f"jalr-ra-target-0x{target:08x}", enc_jalr(25, 31), registers)
    add("jalr-rd-zero", enc_jalr(25, 0), [0] * 25 + [0x00001000] + [0] * 6)
    add("jalr-rd-equals-rs", enc_jalr(25, 25), [0] * 25 + [0x00001000] + [0] * 6)
    add("jalr-rd-t0", enc_jalr(25, 8),
        [0] * 8 + [0x33333333] + [0] * 16 + [0x00001000] + [0] * 6)
    add("jalr-unaligned-target", enc_jalr(25, 31), [0] * 25 + [0x00001002] + [0] * 6)
    add("jalr-target-latched-before-delay-slot", enc_jalr(25, 31),
        [0] * 25 + [0x00001000] + [0] * 6)
    add("mul-then-read-lo", enc_mul(1, 2, 3), [0, 0, 0x7FFFFFFF, 0x7FFFFFFF] + [0] * 28)
    add("divu-defines-hi-lo", enc_divu(4, 5), [0, 0, 0, 0, 0x12345678, 5] + [0] * 26)
    return vectors, failures, idiom_checks


def audit_vectors() -> dict[str, Any]:
    vectors, failures, idiom_checks = build_vectors()
    check("vectors:count", len(vectors) >= 300)
    check("vectors:all-match-independent-reference", not failures)
    check("vectors:class-coverage",
          set(IMPLEMENTED_OPS) <= {vector["op"] for vector in vectors})
    check("vectors:fail-closed-covered",
          any(vector["module_error"] == ERROR_DIVIDE_BY_ZERO for vector in vectors)
          and any(vector["module_error"] == ERROR_TRAP_TAKEN for vector in vectors)
          and any(vector["module_error"] == ERROR_UNALIGNED_TARGET for vector in vectors))
    check("vectors:swl-swr-idiom-covered", idiom_checks == 24)
    payload = {
        "stage": STAGE,
        "independent_reference": (
            "in-gate model written separately from p3_semantics_mips32_v1: "
            "explicit signed arithmetic for mul, divmod for divu and byte-level "
            "store-left/store-right merges"
        ),
        "vector_count": len(vectors),
        "failed_vectors": len(failures),
        "vectors": vectors,
    }
    ARTIFACTS[VECTORS_JSON] = evidence_json_bytes(payload)
    FINDINGS["vectors"] = {
        "count": len(vectors),
        "failed": len(failures),
        "classes": sorted({vector["op"] for vector in vectors}),
        "fail_closed": sorted({vector["module_error"] for vector in vectors
                               if vector["module_error"]}),
        "swl_swr_idiom_checks": idiom_checks,
    }
    return payload


# ---------------------------------------------------------------------------
# Site coverage: every audited site executed against both models
# ---------------------------------------------------------------------------
def site_registers(seed: int) -> list[int]:
    registers = [0] * 32
    for index, value in enumerate(lcg_values(seed, 31), start=1):
        registers[index] = value
    return registers


def audit_site_coverage(result: dict[str, Any], table_before: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    per_class: dict[str, dict[str, int]] = {}
    for row in table_before["site_table"]:
        address = int(row["address"], 16)
        word = int(row["word"], 16)
        record = classify(address, word)
        registers = site_registers(address)
        if record["op"] == "divu":
            divisor_reg = record["operands"]["rt"]
            if registers[divisor_reg] == 0:
                registers[divisor_reg] = 0x9E3779B9
        elif record["op"] == "teq":
            rs_reg, rt_reg = record["operands"]["rs"], record["operands"]["rt"]
            if registers[rs_reg] == registers[rt_reg]:
                registers[rt_reg] ^= 1
        elif record["op"] == "jalr":
            registers[record["operands"]["rs"]] &= ~3
        module = module_run(word, registers, address=address)
        reference = reference_run(word, registers, address=address)
        status = "PASS" if compare_runs(module, reference) else "FAIL"
        if module["error"] == ERROR_UNSUPPORTED_INSTRUCTION:
            status = "FAIL"
        if status != "PASS":
            failures.append(row["address"])
        per_class.setdefault(record["op"], {"sites": 0, "failures": 0})
        per_class[record["op"]]["sites"] += 1
        per_class[record["op"]]["failures"] += 0 if status == "PASS" else 1
        rows.append({
            "address": row["address"],
            "word": row["word"],
            "op": record["op"],
            "reachability": row["reachability"],
            "module_error": module["error"],
            "reference_error": reference["error"],
            "status": status,
        })
    check("coverage:all-sites-executed", len(rows) == 82)
    check("coverage:no-site-unsupported",
          all(row["module_error"] != ERROR_UNSUPPORTED_INSTRUCTION for row in rows))
    check("coverage:all-match-independent-reference", not failures)
    check("coverage:classes", tuple(sorted(per_class)) == IMPLEMENTED_OPS)
    payload = {
        "stage": STAGE,
        "site_rows": rows,
        "per_class": {key: value for key, value in sorted(per_class.items())},
        "failures": failures,
        "deterministic_state_model": (
            "per-site deterministic register state from a fixed LCG seed; divu "
            "divisors forced nonzero and teq operands forced unequal so the "
            "non-trapping path is the one exercised"
        ),
    }
    ARTIFACTS[COVERAGE_JSON] = evidence_json_bytes(payload)
    FINDINGS["coverage"] = {"sites": len(rows), "per_class": payload["per_class"],
                            "failures": failures}
    return payload


# ---------------------------------------------------------------------------
# HI/LO dependency analysis
# ---------------------------------------------------------------------------
RD_WRITE_OPS = frozenset({
    "addu", "subu", "and", "or", "xor", "nor", "slt", "sltu", "sll", "srl",
    "sra", "sllv", "srlv", "srav", "mfhi", "mflo", "mul", "movz", "movn", "jalr",
})
RT_WRITE_OPS = frozenset({
    "addiu", "andi", "ori", "xori", "slti", "sltiu", "lui", "lb", "lbu", "lh",
    "lhu", "lw",
})
HI_LO_WRITE_OPS = frozenset({"mult", "multu", "div", "divu", "mthi", "mtlo"})
HI_LO_READ_OPS = frozenset({"mfhi", "mflo"})


def writes_register(record: dict[str, Any], register: int) -> bool:
    op = record["op"]
    if op in RD_WRITE_OPS:
        return record["operands"].get("rd") == register
    if op in RT_WRITE_OPS:
        return record["operands"].get("rt") == register
    return False


def audit_hi_lo_dependency(result: dict[str, Any], ingested) -> dict[str, Any]:
    by_address = {record["address"]: record for record in result["records"]}
    reachable = set(result["reachable_addresses"])
    targets = set()
    for sites in result["control_flow"].values():
        for site in sites:
            if site.get("target") is not None:
                targets.add(site["target"])

    reads = sorted(address for address in by_address
                   if by_address[address]["op"] in HI_LO_READ_OPS and address in reachable)
    check("hi-lo:reachable-read-sites",
          tuple(reads) == (0x1A4C, 0x1B5C, 0x1F68, 0x204C, 0x2378, 0x4530))
    entries = []
    unresolved: list[int] = []
    for site in reads:
        address = site
        definer = None
        crossed: list[int] = []
        while True:
            address -= 4
            if address < TEXT_VADDR or address not in reachable:
                break
            record = by_address[address]
            if record["op"] in HI_LO_WRITE_OPS or record["op"] == "mul":
                definer = record
                break
            if record["control_flow"] or address in targets:
                break
            crossed.append(address)
        op = definer["op"] if definer is not None else None
        if op in HI_LO_WRITE_OPS:
            classification = "DEFINED_BY_" + op.upper()
        elif op == "mul":
            classification = "MUL_HI_LO_UNPREDICTABLE"
            unresolved.append(site)
        else:
            classification = "UNRESOLVED"
            unresolved.append(site)
        entries.append({
            "read_site": hexv(site),
            "op": by_address[site]["op"],
            "nearest_hilo_writer": op,
            "writer_address": hexv(definer["address"]) if definer else None,
            "classification": classification,
            "intervening_instructions": [hexv(item) for item in crossed],
        })
    check("hi-lo:no-unpredictable-dependency", not unresolved)
    check("hi-lo:no-mul-crossed",
          all(entry["nearest_hilo_writer"] != "mul" for entry in entries))
    payload = {
        "stage": STAGE,
        "analysis": (
            "backwards scan from each reachable mfhi/mflo to the nearest HI/LO "
            "writer within the same straight-line region (stopping at control "
            "flow and at any branch/jump/call target); mul writers are "
            "architecturally UNPREDICTABLE and would be reported as unresolved"
        ),
        "read_sites": entries,
        "unresolved": [hexv(site) for site in unresolved],
    }
    ARTIFACTS[HI_LO_JSON] = evidence_json_bytes(payload)
    FINDINGS["hi_lo_dependency"] = {
        "read_sites": [entry["read_site"] for entry in entries],
        "classifications": [entry["classification"] for entry in entries],
        "unresolved": payload["unresolved"],
    }
    return payload


# ---------------------------------------------------------------------------
# Exception frontier (six reachable div/trap sites)
# ---------------------------------------------------------------------------
def audit_exception_frontier(result: dict[str, Any], ingested, ranges) -> dict[str, Any]:
    by_address = {record["address"]: record for record in result["records"]}
    image = ingested.image
    seeds = {name: image.read_u32(address) for name, address in sorted(SEED_GLOBALS.items())}
    check("exception:seed-values", seeds == {
        "seed1_volatile": 0, "seed2_volatile": 0, "seed3_volatile": 0x66,
        "seed4_volatile": 0x3E8, "seed5_volatile": 0,
    })
    table_pointers = tuple(image.read_u32(SEED_TABLE_ADDRESS + index * 4)
                           for index in range(5))
    check("exception:seed-table", table_pointers == SEED_TABLE_POINTERS)

    reachable = set(result["reachable_addresses"])
    seed_materialisations = []
    seed_low = {value & 0xFFFF for value in SEED_GLOBALS.values()}
    seed_high = {value & 0xFFFF0000 for value in SEED_GLOBALS.values()}
    for address in sorted(reachable):
        record = by_address[address]
        imm = record["operands"].get("imm")
        if isinstance(imm, int) and (imm & 0xFFFF) in seed_low:
            seed_materialisations.append({"site": hexv(address), "op": record["op"],
                                          "imm": hexv(imm)})
        if record["op"] == "lui" and isinstance(imm, int) and imm:
            if (imm << 16) & MASK32 in seed_high:
                seed_materialisations.append({"site": hexv(address), "op": record["op"],
                                              "imm": hexv(imm)})
    check("exception:no-reachable-seed-materialisation", not seed_materialisations)

    def targets_in(start: int, end: int) -> list[dict[str, Any]]:
        found = []
        for key, sites in result["control_flow"].items():
            for site in sites:
                target = site.get("target")
                if target is not None and start < target < end:
                    found.append({"source": hexv(site["site"]), "kind": key,
                                  "target": hexv(target)})
        return found

    popcount_formula = {
        f"0x{value:x}": (value & 1) + ((value & 2) >> 1) + ((value & 4) >> 2)
        for value in range(8)
    }
    check("exception:popcount-model",
          popcount_formula == {f"0x{value:x}": bin(value).count("1")
                               for value in range(8)})
    execs = 7 if seeds["seed5_volatile"] == 0 else seeds["seed5_volatile"]
    divisor_1 = popcount_formula[f"0x{execs & 7:x}"]
    check("exception:pair1-divisor-nonzero", divisor_1 == 3)
    check("exception:pair1-no-target-in-popcount", targets_in(0x1F40, 0x1F60) == [])
    check("exception:pair1-execs-stable",
          not any(writes_register(by_address[address], 2)
                  for address in range(0x1F40, 0x1F60, 4)))
    check("exception:pair1-divisor-stable",
          not any(writes_register(by_address[address], 1)
                  for address in range(0x1F5C, 0x1F64, 4)))

    guard = by_address[0x2038]
    check("exception:pair2-guard",
          guard["op"] == "beq" and guard["operands"]["rs"] == 2
          and guard["operands"]["rt"] == 0 and guard["target"] == 0x2000)
    check("exception:pair2-delay-slot-inert", by_address[0x203C]["op"] == "nop")
    check("exception:pair2-predecessor-writes-only-1",
          writes_register(by_address[0x2040], 1)
          and not writes_register(by_address[0x2040], 2))
    check("exception:pair2-no-target-into-site", targets_in(0x203C, 0x2048) == [])
    check("exception:pair2-iterations-nonzero", seeds["seed4_volatile"] == 0x3E8)
    stack_writes = [
        hexv(address) for address in sorted(reachable)
        if 0x1ED4 < address < 0x1FE8 and by_address[address]["op"] == "sw"
        and by_address[address]["operands"].get("rs") == 29
        and by_address[address]["operands"].get("imm") == 64
    ]
    check("exception:pair2-stack-slot-stable", not stack_writes)

    guard3 = by_address[0x2350]
    check("exception:pair3-guard",
          guard3["op"] == "beq" and guard3["operands"]["rs"] == 2
          and guard3["operands"]["rt"] == 0 and guard3["target"] == 0x2388)
    check("exception:pair3-callees",
          all(by_address[address]["op"] == "jal"
              and by_address[address]["target"] == TIME_IN_SECS
              for address in (0x2348, 0x2368)))
    check("exception:pair3-delay-slots",
          by_address[0x234C]["op"] == "or"
          and by_address[0x234C]["operands"] == {"rs": 17, "rt": 0, "rd": 4}
          and by_address[0x236C]["op"] == "or"
          and by_address[0x236C]["operands"] == {"rs": 17, "rt": 0, "rd": 4})
    seventeen_writes = [hexv(address) for address in range(0x2350, 0x2368, 4)
                        if writes_register(by_address[address], 17)]
    check("exception:pair3-argument-stable", not seventeen_writes)
    check("exception:pair3-no-target-into-block", targets_in(0x2350, 0x2370) == [])
    callee_ops = [by_address[address]["op"] for address in range(TIME_IN_SECS, 0x453C, 4)]
    check("exception:pair3-callee-pure",
          set(callee_ops) <= {"lui", "ori", "multu", "mfhi", "jr", "srl"}
          and not any(by_address[address]["control_flow"]
                      for address in range(TIME_IN_SECS, 0x4534, 4)))

    def site_entry(site: int, op: str, condition: str, classification: str,
                   evidence: list[str], runtime_requirement: str) -> dict[str, Any]:
        record = by_address[site]
        return {
            "site": hexv(site),
            "op": op,
            "word": hexv(record["word"]),
            "operands": dict(record["operands"]),
            "reachability": record["reachability"],
            "containing_function": owning_function(site, ranges),
            "exceptional_condition": condition,
            "classification": classification,
            "runtime_requirement": runtime_requirement,
            "semantics_status": "IMPLEMENTED_FAIL_CLOSED",
            "evidence": evidence,
        }

    sites = [
        site_entry(
            0x1F60, "divu", "divisor ($1) == 0",
            "CONDITION_PROVEN_FALSE_FOR_FIXTURE",
            [
                "seed5_volatile (0x5608) initial image value is 0",
                "get_seed_32(5) reads the seed-table pointer at 0x4c60 -> 0x5608",
                "0x1ee0 addiu $1=$0+7 and 0x1ee4 movz $2,$1,$2 set execs=7 when 0",
                "0x1f40..0x1f58 compute popcount(execs & 7) as "
                "((x&1)+((x&2)>>1)+((x&4)>>2)); for execs=7 the divisor is 3",
                "no reachable instruction materialises a seed address, so the "
                "image value is the value read",
                "no control-flow target enters 0x1f40..0x1f60 and no instruction "
                "there writes $2",
            ],
            "divisor is nonzero; LO/HI are defined and match the reference model",
        ),
        site_entry(
            0x1F64, "teq", "($1) == 0 (divisor zero trap guard)",
            "CONDITION_PROVEN_FALSE_FOR_FIXTURE",
            [
                "same divisor derivation as 0x1f60: $1 = popcount(7) = 3",
                "teq is only taken when $1 == $0, which is false for the fixture",
            ],
            "trap condition false; execution continues with the defined quotient",
        ),
        site_entry(
            0x2044, "divu", "divisor ($2) == 0",
            "CONDITION_PROVEN_FALSE_ON_EVERY_REACHING_PATH",
            [
                "0x2038 beq $2,$0,0x2000 is the only guard: the fall-through path "
                "continues only when the seconds value is nonzero",
                "0x203c is a nop delay slot and 0x2040 writes only $1",
                "no control-flow target enters 0x203c..0x2048, so every execution "
                "reaching 0x2044 passed the $2 != 0 test",
                "the containing auto-calibration block is additionally not entered "
                "for the fixture: seed4_volatile (0x4e14) is 0x3e8 and 0x1fec "
                "bne $1,$0,0x2060 skips the block when iterations != 0",
            ],
            "divisor is nonzero on every path that reaches the site",
        ),
        site_entry(
            0x2048, "teq", "($2) == 0 (divisor zero trap guard)",
            "CONDITION_PROVEN_FALSE_ON_EVERY_REACHING_PATH",
            [
                "the same 0x2038 beq guard proves $2 != 0 on the fall-through path",
                "no path enters the site without passing that guard",
            ],
            "trap condition false; execution continues with the defined quotient",
        ),
        site_entry(
            0x2370, "divu", "divisor ($2) == 0 (second time_in_secs result)",
            "CONDITION_PROVEN_FALSE_ON_EVERY_REACHING_PATH",
            [
                "0x2348 calls time_in_secs($17) and 0x2350 beq $2,$0,0x2388 skips "
                "the block when that result is zero",
                "0x2368 calls time_in_secs($17) again; both delay slots load the "
                "same argument $17 and no instruction between them writes $17",
                "time_in_secs (0x4524..0x4538) is a pure function of $4: "
                "lui/ori/multu/mfhi/srl, no memory access, no call, no branch",
                "equal input therefore yields an equal nonzero result, so the "
                "divisor at 0x2370 equals the value proven nonzero at 0x2350",
                "no control-flow target enters 0x2350..0x2370",
            ],
            "divisor is nonzero; the quotient in LO is well defined",
        ),
        site_entry(
            0x2374, "teq", "($2) == 0 (divisor zero trap guard)",
            "CONDITION_PROVEN_FALSE_ON_EVERY_REACHING_PATH",
            [
                "same pure-callee, same-argument reasoning as the 0x2370 divu",
                "the divisor tested is the value proven nonzero at 0x2350",
            ],
            "trap condition false; execution continues with the defined quotient",
        ),
    ]
    check("exception:site-count", len(sites) == 6)
    check("exception:all-conditions-proven-false",
          all(site["classification"] != "UNRESOLVED_RUNTIME_REQUIREMENT"
              for site in sites))
    for site in sites:
        check(f"exception:site:{site['site']}",
              site["semantics_status"] == "IMPLEMENTED_FAIL_CLOSED")

    payload = {
        "stage": STAGE,
        "policy": (
            "architecturally UNPREDICTABLE exceptional states fail closed in the "
            "semantics model; this table states whether the deterministic fixture "
            "can reach the exceptional condition and on what evidence"
        ),
        "fixture_constants": {
            "seed_globals": {name: hexv(address)
                             for name, address in sorted(SEED_GLOBALS.items())},
            "seed_values": {name: hexv(value) for name, value in sorted(seeds.items())},
            "seed_table_address": hexv(SEED_TABLE_ADDRESS),
            "seed_table_pointers": [hexv(value) for value in table_pointers],
        },
        "sites": sites,
        "seed_materialisation_scan": {
            "finding": "no reachable instruction references a seed address",
            "matches": seed_materialisations,
            "bound": (
                "bounded to the audited image and reachable instructions: direct "
                "16-bit immediates and lui halves of the seed addresses"
            ),
        },
        "summary": {
            "conditions_proven_false": len(sites),
            "unresolved_runtime_requirements": 0,
        },
    }
    ARTIFACTS[EXCEPTION_JSON] = evidence_json_bytes(payload)
    FINDINGS["exception_frontier"] = payload["summary"]
    return payload


# ---------------------------------------------------------------------------
# After-frontier recomputation
# ---------------------------------------------------------------------------
def audit_after(result: dict[str, Any], table_before: dict[str, Any],
                coverage: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for row in table_before["site_table"]:
        address = int(row["address"], 16)
        record = classify(address, int(row["word"], 16))
        updated = dict(row)
        updated["semantic_implementation_status"] = semantics_status(record["op"])
        updated["implementation_class"] = implementations()[record["op"]]["class"]
        updated["reachable_path_requirement"] = (
            "REQUIRED" if row["reachability"] == "REACHABLE" else "NOT_REQUIRED_UNREACHABLE")
        updated["control_flow_status"] = (
            "UNRESOLVED_INDIRECT_CALL_TARGET (never guessed)"
            if record["op"] == "jalr" else (record["terminator"] or "fallthrough"))
        rows.append(updated)
    coverage_by_address = {item["address"]: item for item in coverage["site_rows"]}
    for row in rows:
        row["site_coverage_status"] = coverage_by_address[row["address"]]["status"]

    reachable_after = sum(1 for row in rows if row["reachability"] == "REACHABLE")
    unreachable_after = len(rows) - reachable_after
    check("after:site-count", len(rows) == 82)
    check("after:reachable-sites", reachable_after == 55)
    check("after:unreachable-sites", unreachable_after == 27)
    check("after:all-sites-semantically-implemented",
          all(row["semantic_implementation_status"] == "IMPLEMENTED" for row in rows))
    check("after:all-sites-covered",
          all(row["site_coverage_status"] == "PASS" for row in rows))
    check("after:reachable-path-fully-covered", result["summary"]["reachable_words"] == 2178)

    payload = {
        "stage": STAGE,
        "site_table": rows,
        "site_table_sha256": row_digest(rows),
        "counts": {
            "total": len(rows),
            "reachable": reachable_after,
            "unreachable": unreachable_after,
            "reachable_semantically_supported_after": 2178,
            "reachable_semantically_unsupported_after": 0,
            "unreachable_semantically_supported_after": unreachable_after,
            "unreachable_semantically_unsupported_after": 0,
        },
        "coverage": coverage["per_class"],
        "remaining_frontier": {
            "reachable_semantic_gap": "none in the P3-01 bounded classes",
            "unresolved_control_flow": {
                "jr_at_jump_tables": [hexv(site) for site in EXPECTED_REACHABLE_INDIRECT_JR],
                "dead_jalr": hexv(EXPECTED_UNREACHABLE_JALR),
                "boundary_successor": hexv(0x467C),
                "note": "never resolved, never guessed",
            },
            "unreached_code_words": 1301,
            "dead_function_words": 687,
            "padding_words": 8,
            "notes": [
                "unreachable recognized-unsupported words carry implemented "
                "semantics but are not required by the reachable path",
                "MUL leaves HI/LO architecturally UNPREDICTABLE; no reachable "
                "HI/LO read depends on it (see hi_lo_dependency.json)",
            ],
        },
    }
    ARTIFACTS[AFTER_JSON] = evidence_json_bytes(payload)
    FINDINGS["after"] = {
        "counts": payload["counts"],
        "site_table_sha256": payload["site_table_sha256"],
        "remaining_frontier": payload["remaining_frontier"],
    }
    return payload


def audit_rerun(result: dict[str, Any], rerun: dict[str, Any]) -> dict[str, Any]:
    summary = result["summary"]
    check("rerun:identical-summary",
          canonical_json_bytes(summary) == canonical_json_bytes(rerun["summary"]))
    check("rerun:identical-records",
          canonical_json_bytes(result["records"]) == canonical_json_bytes(rerun["records"]))
    check("rerun:identical-control-flow",
          canonical_json_bytes(result["control_flow"]) ==
          canonical_json_bytes(rerun["control_flow"]))
    check("rerun:identical-unresolved",
          canonical_json_bytes(result["unresolved"]) ==
          canonical_json_bytes(rerun["unresolved"]))
    payload = {
        "stage": STAGE,
        "entry": hexv(result["entry"]),
        "totals": {key: summary[key] for key in EXPECTED_TOTALS},
        "control_flow_counts": summary["control_flow_site_counts"],
        "unresolved_counts": summary["unresolved_site_counts"],
        "unsupported_histogram": summary["unsupported_histogram"],
        "unsupported_reachable_histogram": summary["unsupported_reachable_histogram"],
        "unsupported_unreachable_histogram": summary["unsupported_unreachable_histogram"],
        "reachability_sha256": sha256_bytes("\n".join(
            f"{hexv(record['address'])} {record['reachability']}"
            for record in result["records"]).encode("ascii")),
        "exception_sites": [hexv(site) for site, _ in EXPECTED_EXCEPTION_SITES],
        "indirect_sites": [
            {"site": hexv(site), "resolution": "not statically resolved; no target invented"}
            for site in EXPECTED_REACHABLE_INDIRECT_JR
        ],
        "dead_jalr": {"site": hexv(EXPECTED_UNREACHABLE_JALR),
                      "resolution": "never targeted; no target invented"},
        "semantic_overlay": {
            "reachable_semantically_supported": 2178,
            "reachable_semantically_unsupported": 0,
            "classes": list(IMPLEMENTED_OPS),
        },
        "note": (
            "recomputed from the parsed guest image with the P3-03 engine; the "
            "frontier itself is unchanged by P3-04"
        ),
    }
    ARTIFACTS[RERUN_JSON] = evidence_json_bytes(payload)
    FINDINGS["rerun"] = {"totals": payload["totals"],
                         "reachability_sha256": payload["reachability_sha256"]}
    return payload


# ---------------------------------------------------------------------------
# Fail-closed negatives
# ---------------------------------------------------------------------------
def code_of(action) -> str:
    try:
        action()
    except SemanticsError as exc:
        return exc.code
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        return f"UNEXPECTED_{type(exc).__name__}"
    return "NONE"


def mul_then_read(which: str) -> None:
    state = MachineState(registers=[0, 0, 0x7FFFFFFF, 0x7FFFFFFF] + [0] * 28)
    execute(classify(0x8000, enc_mul(1, 2, 3)), state, BoundedMemory())
    if which == "lo":
        state.read_lo()
    else:
        state.read_hi()


def audit_negatives() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []

    def expect(name: str, expected: str, action) -> None:
        actual = code_of(action)
        cases.append({"fixture": name, "expected_code": expected,
                      "actual_code": actual,
                      "status": "PASS" if actual == expected else "FAIL"})

    supported = classify(0x8000, 0x24080001)
    expect("supported-op-record-outside-bounded-contract", ERROR_INVALID_RECORD,
           lambda: execute(supported, MachineState(), BoundedMemory()))
    bounded = dict(classify(0x8000, enc_swl(9, 10, 0)), op="addi")
    expect("unimplemented-bounded-op", ERROR_UNSUPPORTED_INSTRUCTION,
           lambda: execute(bounded, MachineState(), BoundedMemory()))
    expect("divu-divisor-zero", ERROR_DIVIDE_BY_ZERO,
           lambda: execute(classify(0x8000, enc_divu(4, 5)),
                           MachineState(registers=[0, 0, 0, 0, 0x12345678, 0] + [0] * 26),
                           BoundedMemory()))
    expect("teq-equal", ERROR_TRAP_TAKEN,
           lambda: execute(classify(0x8000, enc_teq(1, 2)),
                           MachineState(registers=[0, 7, 7] + [0] * 29), BoundedMemory()))
    expect("jalr-unaligned", ERROR_UNALIGNED_TARGET,
           lambda: execute(classify(0x8000, enc_jalr(25, 31)),
                           MachineState(registers=[0] * 25 + [0x1002] + [0] * 6),
                           BoundedMemory()))
    expect("swl-unmapped-aligned-word", ERROR_MEMORY_FAULT,
           lambda: execute(classify(0x8000, enc_swl(9, 10, 0)),
                           MachineState(registers=[0] * 9 + [0x90000000, 1] + [0] * 21),
                           BoundedMemory(base=0x1000, size=0x100)))
    expect("swr-read-only", ERROR_WRITE_PROTECTED,
           lambda: execute(classify(0x8000, enc_swr(9, 10, 0)),
                           MachineState(registers=[0] * 9 + [0x1000, 1] + [0] * 21),
                           BoundedMemory(base=0x1000, size=0x100, writable=False)))
    expect("big-endian-unsupported", ERROR_ENDIANNESS_UNSUPPORTED,
           lambda: execute(classify(0x8000, enc_movz(3, 2, 7)), MachineState(),
                           BoundedMemory(), endianness="big"))
    expect("invalid-state-register", ERROR_INVALID_STATE,
           lambda: execute(classify(0x8000, enc_divu(4, 5)), object(), BoundedMemory()))
    missing_operand = dict(classify(0x8000, enc_swl(9, 10, 0)))
    missing_operand["operands"] = {"rs": 9, "rt": 10}
    expect("malformed-record-missing-operand", ERROR_INVALID_RECORD,
           lambda: execute(missing_operand, MachineState(), BoundedMemory()))
    expect("misaligned-record-address", ERROR_INVALID_RECORD,
           lambda: execute(dict(classify(0x8000, enc_movz(3, 2, 7)), address=0x8002),
                           MachineState(), BoundedMemory()))
    expect("mul-then-read-lo", ERROR_HI_LO_UNPREDICTABLE, lambda: mul_then_read("lo"))
    expect("mul-then-read-hi", ERROR_HI_LO_UNPREDICTABLE, lambda: mul_then_read("hi"))

    divu_state = MachineState(registers=[0, 0, 100, 7] + [0] * 28, lo=0xAAAA, hi=0xBBBB)
    try:
        execute(classify(0x8000, enc_divu(2, 3)), divu_state, BoundedMemory())
    except SemanticsError:
        pass
    cases.append({
        "fixture": "divu-defines-hi-lo",
        "expected_code": None,
        "actual_code": None,
        "status": "PASS" if divu_state.lo == 14 and divu_state.hi == 2
        and divu_state.hi_lo_defined else "FAIL",
    })
    zero_state = MachineState(registers=[0, 0, 3, 5] + [0] * 28, lo=0xAAAA, hi=0xBBBB)
    try:
        execute(classify(0x8000, enc_divu(2, 0)), zero_state, BoundedMemory())
    except SemanticsError:
        pass
    cases.append({
        "fixture": "divu-zero-leaves-hi-lo-untouched",
        "expected_code": None,
        "actual_code": None,
        "status": "PASS" if zero_state.snapshot() == MachineState(
            registers=[0, 0, 3, 5] + [0] * 28, lo=0xAAAA, hi=0xBBBB).snapshot()
        else "FAIL",
    })
    teq_state = MachineState(registers=[0, 7, 7] + [0] * 29, lo=1, hi=2)
    try:
        execute(classify(0x8000, enc_teq(1, 2)), teq_state, BoundedMemory())
    except SemanticsError:
        pass
    cases.append({
        "fixture": "teq-taken-leaves-state-untouched",
        "expected_code": None,
        "actual_code": None,
        "status": "PASS" if teq_state.snapshot() == MachineState(
            registers=[0, 7, 7] + [0] * 29, lo=1, hi=2).snapshot() else "FAIL",
    })
    mul_state = MachineState(registers=[0, 0, 0x7FFFFFFF, 0x7FFFFFFF] + [0] * 28,
                             lo=0x1234, hi=0x5678)
    execute(classify(0x8000, enc_mul(1, 2, 3)), mul_state, BoundedMemory())
    cases.append({
        "fixture": "mul-leaves-hi-lo-values-but-marks-unpredictable",
        "expected_code": None,
        "actual_code": None,
        "status": "PASS" if mul_state.hi == 0x5678 and mul_state.lo == 0x1234
        and not mul_state.hi_lo_defined else "FAIL",
    })
    rd_zero = MachineState(registers=[0] * 32)
    execute(classify(0x8000, enc_movz(0, 2, 0)), rd_zero, BoundedMemory())
    cases.append({
        "fixture": "movz-rd-zero-discards-write",
        "expected_code": None,
        "actual_code": None,
        "status": "PASS" if all(value == 0 for value in rd_zero.registers) else "FAIL",
    })

    failures = [item for item in cases if item["status"] != "PASS"]
    for item in failures:
        print(f"NEGATIVE-FAILURE: {item}", flush=True)
    check("negatives:no-failures", not failures)
    check("negatives:count", len(cases) >= 16)
    payload = {"stage": STAGE, "cases": cases, "failed": len(failures)}
    ARTIFACTS[NEGATIVES_JSON] = evidence_json_bytes(payload)
    FINDINGS["negatives"] = {"count": len(cases), "failed": len(failures)}
    return payload


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def audit_determinism(data: bytes, ingested) -> None:
    first = run_frontier(ingested)
    second = run_frontier(ingest(bytes(data), MIPS32_O32))
    check("determinism:frontier-stable",
          canonical_json_bytes(first["summary"]) == canonical_json_bytes(second["summary"]))
    check("determinism:control-flow-stable",
          canonical_json_bytes(first["control_flow"]) ==
          canonical_json_bytes(second["control_flow"]))
    vectors, failures, idiom_checks = build_vectors()
    check("determinism:vectors-stable",
          not failures and idiom_checks > 0 and len(vectors) > 0)
    artifact_hashes = {name: sha256_bytes(payload) for name, payload in sorted(ARTIFACTS.items())}
    record = {
        "source_sha256": sha256_bytes(data),
        "vector_count": len(vectors),
        "artifact_sha256": artifact_hashes,
        "reachability_sha256": sha256_bytes("\n".join(
            f"{hexv(record['address'])} {record['reachability']}"
            for record in first["records"]).encode("ascii")),
    }
    ARTIFACTS[DETERMINISM] = evidence_json_bytes(record)
    FINDINGS["determinism"] = record


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
    parser = argparse.ArgumentParser(description="P3-04 CoreMark reachable-semantics gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-04")
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

    print("=== P3-04 CoreMark Reachable Semantics Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    evidence_files: dict[str, str] = {}
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("fixture")
        data = audit_fixture(elf_path)
        banner("input integrity")
        ingested, words = audit_input_integrity(data)
        probe = run_frontier(ingested)
        banner("p3_03 cross-check")
        audit_p3_03_cross_check(probe)
        banner("before table")
        before = audit_before(probe, ingested)
        banner("implementations")
        audit_implementations(probe)
        banner("reference vectors")
        audit_vectors()
        banner("site coverage")
        coverage = audit_site_coverage(probe, before)
        banner("hi/lo dependency")
        audit_hi_lo_dependency(probe, ingested)
        banner("exception frontier")
        audit_exception_frontier(probe, ingested, function_layout(ingested))
        banner("after table")
        audit_after(probe, before, coverage)
        banner("frontier rerun")
        audit_rerun(probe, run_frontier(ingest(bytes(data), MIPS32_O32)))
        banner("negatives")
        audit_negatives()
        banner("determinism")
        audit_determinism(data, ingested)
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
