#!/usr/bin/env python3
"""OpenRecomp Phase-3 CoreMark MIPS32 decode-frontier gate (P3-03).

P3-03 proves that OpenRecomp can deterministically decode and classify the
complete executable instruction frontier of the audited CoreMark MIPS32 ELF and
identify the exact remaining semantic/control-flow gaps.  It adds no
execution/translation semantics and does not run CoreMark.

The deterministic gate:

* verifies source integrity: the frozen root ``SOURCE_SHA256SUMS.txt`` is
  unchanged and every entry still hashes, and the Phase-3
  ``.openrecomp-phase3/SOURCE_SHA256SUMS.txt`` manifest registers and verifies
  the Phase-3 source/gate files;
* verifies the P3-01 fixture identity (sha256 ``16a0a0aa...``, 31184 bytes) and
  that the executable words read through the P3-02 ``GuestImage`` equal the raw
  ``.text`` file slice;
* classifies every executable word through the additive Phase-3 decode layer
  (``p3_decode_mips32_v1``): words the frozen bounded adapter decodes are
  ``SUPPORTED``; the P3-01 recognized-but-semantically-unsupported classes are
  decoded with exact operands but stay ``RECOGNIZED_UNSUPPORTED``; reserved and
  unknown encodings are fail-closed ``RESERVED_ENCODING``/``UNKNOWN_ENCODING``;
* cross-checks the resulting inventory against the frozen P3-01 evidence and
  against an independent bounded-adapter sweep of the same words;
* discovers reachable code from the ELF entry point with MIPS32 delay-slot
  semantics (``p3_code_frontier_v1``), never treating every executable word as
  reachable code, never inventing indirect targets, and stopping flow at
  reserved/unknown encodings and unresolvable delay slots;
* classifies the eight ``0x04170001`` words as unreachable non-code padding
  using three independent evidence elements (reachability, reserved encoding,
  function-symbol gap position) rather than inheriting the P3-01 label;
* exercises malformed/reserved/unknown-encoding panels and synthetic reachability
  fixtures (delay-slot fall-through suppression, direct/indirect calls, branches,
  returns, boundary successors, fail-closed cases) and requires deterministic
  classifications;
* re-runs the whole classification on fresh bytes and requires byte-identical
  canonical serializations.

On success it emits::

    OPENRECOMP_P3_03=PASS
    OPENRECOMP_PHASE3_COREMARK_DECODE_FRONTIER_V1=PASS tests=<count>

Any failed invariant fails closed and emits ``OPENRECOMP_P3_03=FAIL``.

Usage:

    python tools/test_phase3_decode_frontier_v1.py
    python tools/test_phase3_decode_frontier_v1.py --elf .openrecomp-phase3/build/P3-01/candidate-a/coremark_mips32_O1.elf
"""
from __future__ import annotations

import argparse
import hashlib
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

from adapters import mips32  # noqa: E402
from p3_code_frontier_v1 import (  # noqa: E402
    PADDING_NON_CODE,
    UNREACHED_CODE,
    FrontierError,
    analyze,
    unreachable_classification,
)
from p3_decode_mips32_v1 import (  # noqa: E402
    CLASS_RECOGNIZED_UNSUPPORTED,
    CLASS_RESERVED,
    CLASS_SUPPORTED,
    CLASS_UNKNOWN,
    DecodeClassificationError,
    classify,
)
from p3_elf_image_v1 import (  # noqa: E402
    canonical_json_bytes,
    evidence_json_bytes,
    ingest,
    sha256_bytes,
)
from p3_target_mips32_v1 import MIPS32_O32  # noqa: E402

EVIDENCE_ROOT = ROOT / ".openrecomp-phase3" / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-03"

STAGE = "P3-03"
STAGE_MARKER = "OPENRECOMP_P3_03"
FEATURE_MARKER = "OPENRECOMP_PHASE3_COREMARK_DECODE_FRONTIER_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF"

P3_SOURCE_MANIFEST = ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt"
# Stage-grown registry (documented additive change at P3-04): the P3-04
# semantics source and gate are registered as well (8 -> 10 entries).  Every
# entry is still verified; the P3-03 stdout capture stays byte-identical.
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

P3_01_INVENTORY = EVIDENCE_ROOT / "P3-01" / "instruction_inventory.json"
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
TEXT_FILE_SIZE = 13948

TERM_RETURN = "return"
TERM_INDIRECT_CALL = "indirect-call"
TERM_CONDITIONAL_BRANCH = "conditional-branch"

CLAIM_BOUNDARY = (
    "P3-03 proves that OpenRecomp can deterministically decode and classify "
    "the executable instruction frontier of the audited CoreMark MIPS32 ELF "
    "and identify the exact remaining semantic/control-flow gaps. It does not "
    "prove that the unsupported instructions execute correctly, that CoreMark "
    "translates successfully, that CoreMark runs, or any arbitrary MIPS32/"
    "console compatibility."
)

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
    "control_flow_site_counts": {
        "conditional-branches": 198,
        "direct-calls": 96,
        "indirect-calls": 0,
        "indirect-jumps": 3,
        "jumps": 70,
        "returns": 24,
        "unsupported-control-transfers": 0,
    },
    "unresolved_site_counts": {
        "indirect-jump": 3,
        "successor-outside-image": 1,
    },
    "exception_site_count": 6,
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
EXPECTED_SUPPORTED_HISTOGRAM = {
    "addiu": 654, "addu": 171, "and": 11, "andi": 161, "beq": 170,
    "bgez": 2, "bgtz": 13, "blez": 17, "bltz": 4, "bne": 135, "j": 125,
    "jal": 101, "jr": 52, "lbu": 74, "lh": 28, "lhu": 43, "lui": 73,
    "lw": 275, "mfhi": 4, "mflo": 4, "multu": 3, "nop": 224, "nor": 2,
    "or": 345, "ori": 17, "sb": 79, "sh": 32, "sll": 106, "slt": 24,
    "slti": 8, "sltiu": 33, "sltu": 19, "sra": 13, "srl": 81, "subu": 35,
    "sw": 205, "xor": 52, "xori": 2,
}

EXPECTED_PADDING = (0x1D8C, 0x25CC, 0x33C8, 0x33CC, 0x36FC, 0x4644, 0x4648, 0x464C)
EXPECTED_PADDING_RUNS = (
    (0x1D8C, 0x1D90, 0x1D84, 0x1D88, "iterate"),
    (0x25CC, 0x25D0, 0x25C4, 0x25C8, "core_bench_matrix"),
    (0x33C8, 0x33D0, 0x33C0, 0x33C4, "get_seed_32"),
    (0x36FC, 0x3700, 0x36F4, 0x36F8, "uart_send_char"),
    (0x4644, 0x4650, 0x463C, 0x4640, "_start"),
)
EXPECTED_DELAY_SLOTS = 391
EXPECTED_REACHABLE_INDIRECT_JR = (0x3130, 0x3830, 0x39A0)
EXPECTED_UNREACHABLE_JALR = 0x1958
EXPECTED_EXCEPTION_SITES = (
    (0x1F60, "divu"), (0x1F64, "teq"),
    (0x2044, "divu"), (0x2048, "teq"),
    (0x2370, "divu"), (0x2374, "teq"),
)
EXPECTED_BOUNDARY_SUCCESSOR = {"site": 0x4674, "kind": "successor-outside-image", "target": 0x467C}
EXPECTED_UNREACHED_FUNCTIONS = (
    "barebones_clock", "cmp_complex", "cmp_idx", "copy_info", "core_list_find",
    "core_list_insert_new", "core_list_mergesort", "core_list_remove",
    "core_list_reverse", "core_list_undo_remove", "crcu8", "matrix_add_const",
    "matrix_mul_const", "matrix_mul_matrix", "matrix_mul_matrix_bitextract",
    "matrix_mul_vect", "matrix_sum", "memcpy", "memmove", "memset", "number",
    "uart_send_char",
)
EXPECTED_FULLY_REACHABLE_FUNCTIONS = (
    "core_bench_list", "core_bench_matrix", "core_bench_state", "core_init_matrix",
    "core_init_state", "core_list_init", "crc16", "crcu16", "crcu32",
    "get_seed_32", "iterate", "main", "_start",
)
EXPECTED_PARTIAL_FUNCTIONS = {"core_state_transition": (49, 142), "ee_printf": (187, 708)}

EXPECTED_DECODE_POSITIVE = (
    ("movz", 0x00A2180A, {"rs": 5, "rt": 2, "rd": 3}),
    ("movn", 0x0069080B, {"rs": 3, "rt": 9, "rd": 1}),
    ("mul", 0x70410802, {"rs": 2, "rt": 1, "rd": 1}),
    ("divu", 0x0081001B, {"rs": 4, "rt": 1}),
    ("teq", 0x002001F4, {"rs": 1, "rt": 0, "code": 7}),
    ("swl", 0xA8E10003, {"rs": 7, "rt": 1, "imm": 3}),
    ("swr", 0xB8E10000, {"rs": 7, "rt": 1, "imm": 0}),
    ("jalr", 0x0320F809, {"rs": 25, "rd": 31}),
)

INSTRUCTION_INVENTORY = "instruction_inventory.json"
REACHABLE_CODE_MAP = "reachable_code_map.json"
UNSUPPORTED_FRONTIER = "unsupported_frontier.json"
CONTROL_FLOW_FRONTIER = "control_flow_frontier.json"
INVALID_PADDING_ANALYSIS = "invalid_padding_analysis.json"
NEGATIVE_RESULTS = "negative_results.json"
SOURCE_INTEGRITY = "source_integrity.txt"
DETERMINISM = "determinism.json"
RESULT_JSON = "RESULT.json"

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


def section(name: str, function, *args) -> None:
    print(f"\n--- {name} ---", flush=True)
    function(*args)


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
# Fixture and ingestion
# ---------------------------------------------------------------------------
def audit_fixture(elf_path: pathlib.Path) -> bytes:
    check("fixture:exists", elf_path.is_file())
    data = elf_path.read_bytes()
    check("fixture:sha256", sha256_bytes(data) == ELF_SHA256)
    check("fixture:size", len(data) == ELF_SIZE)
    check("fixture:p3-01-inventory-exists", P3_01_INVENTORY.is_file())
    FINDINGS["fixture"] = {
        "path": elf_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_bytes(data),
        "size": len(data),
        "p3_01_inventory": P3_01_INVENTORY.relative_to(ROOT).as_posix(),
        "p3_01_inventory_sha256": sha256_bytes(P3_01_INVENTORY.read_bytes()),
    }
    return data


def audit_input_integrity(data: bytes) -> tuple[Any, dict[int, int]]:
    ingested = ingest(data, MIPS32_O32)
    parsed = ingested.parsed
    image = ingested.image
    text = parsed.section(".text")
    check("input:text-section", text is not None)
    check("input:text-vaddr", text.sh_addr == TEXT_VADDR)
    check("input:text-size", text.sh_size == TEXT_SIZE)
    check("input:entry", parsed.header.e_entry == ENTRY)
    check("input:entry-inside-text",
          text.sh_addr <= parsed.header.e_entry < text.sh_addr + text.sh_size)
    raw_slice = data[TEXT_OFFSET:TEXT_OFFSET + TEXT_FILE_SIZE]
    check("input:text-file-slice-size", len(raw_slice) == TEXT_SIZE)
    words: dict[int, int] = {}
    mismatched: list[int] = []
    for index in range(TEXT_WORDS):
        address = TEXT_VADDR + index * 4
        value = image.read_u32(address)
        file_value = int.from_bytes(raw_slice[index * 4:index * 4 + 4], "little")
        if value != file_value:
            mismatched.append(address)
        words[address] = value
    check("input:guest-image-equals-file-slice", not mismatched)
    check("input:word-count", len(words) == TEXT_WORDS)
    FINDINGS["input"] = {
        "text_vaddr": hexv(TEXT_VADDR),
        "text_size": TEXT_SIZE,
        "text_words": len(words),
        "entry": hexv(parsed.header.e_entry),
        "guest_image_file_slice_mismatches": [hexv(item) for item in mismatched],
        "text_slice_sha256": sha256_bytes(raw_slice),
    }
    return ingested, words


# ---------------------------------------------------------------------------
# Decode inventory
# ---------------------------------------------------------------------------
def _adapter_decodes(address: int, word: int) -> bool:
    try:
        mips32.decode(address, word)
        return True
    except mips32.DecodeError:
        return False


def _record_row(record: dict[str, Any], reachability: str) -> str:
    op = record["op"] if record["op"] is not None else "-"
    return (
        f"{hexv(record['address'])} {hexv(record['word'])} "
        f"{record['decode_class']} {op} {reachability}"
    )


def audit_inventory(words: dict[int, int], result: dict[str, Any]) -> dict[str, Any]:
    records = result["records"]
    by_address = {record["address"]: record for record in records}
    check("inventory:record-count", len(records) == TEXT_WORDS)
    check("inventory:record-addresses", sorted(by_address) == sorted(words))

    supported_addresses = {
        address for address, record in by_address.items()
        if record["decode_class"] == CLASS_SUPPORTED}
    adapter_supported = {
        address for address, word in words.items() if _adapter_decodes(address, word)}
    check("inventory:supported-equals-bounded-adapter", supported_addresses == adapter_supported)
    check("inventory:supported-count", len(supported_addresses) == EXPECTED_TOTALS["supported_words"])

    unsupported_addresses = {
        address for address, record in by_address.items()
        if record["decode_class"] == CLASS_RECOGNIZED_UNSUPPORTED}
    reserved_addresses = {
        address for address, record in by_address.items()
        if record["decode_class"] == CLASS_RESERVED}
    unknown_addresses = {
        address for address, record in by_address.items()
        if record["decode_class"] == CLASS_UNKNOWN}
    check("inventory:reserved-addresses", tuple(sorted(reserved_addresses)) == EXPECTED_PADDING)
    check("inventory:unknown-count", not unknown_addresses)
    check("inventory:rejected-by-adapter-partition",
          unsupported_addresses | reserved_addresses | unknown_addresses
          == {address for address in words if address not in adapter_supported})

    summary = result["summary"]
    for key, expected in EXPECTED_TOTALS.items():
        if key in ("control_flow_site_counts", "unresolved_site_counts"):
            continue
        check(f"inventory:total:{key}", summary[key] == expected)
    check("inventory:supported-histogram", summary["supported_histogram"] == EXPECTED_SUPPORTED_HISTOGRAM)
    check("inventory:unsupported-histogram", summary["unsupported_histogram"] == EXPECTED_UNSUPPORTED_TOTAL)
    check("inventory:unsupported-reachable-histogram",
          summary["unsupported_reachable_histogram"] == EXPECTED_UNSUPPORTED_REACHABLE)
    check("inventory:unsupported-unreachable-histogram",
          summary["unsupported_unreachable_histogram"] == EXPECTED_UNSUPPORTED_UNREACHABLE)
    check("inventory:reserved-histogram",
          summary["reserved_encoding_words"] == len(EXPECTED_PADDING))

    p3_01 = json.loads(P3_01_INVENTORY.read_text(encoding="utf-8"))
    check("inventory:p3-01-supported-histogram-cross-check",
          summary["supported_histogram"] == p3_01["supported"])
    p3_01_unsupported = p3_01["unsupported"]
    check("inventory:p3-01-unsupported-cross-check",
          summary["unsupported_histogram"] == {
              "movz": p3_01_unsupported["movz"],
              "movn": p3_01_unsupported["movn"],
              "mul": p3_01_unsupported["mul (SPECIAL2 funct 0x02)"],
              "divu": p3_01_unsupported["divu"],
              "teq": p3_01_unsupported["teq"],
              "swl": p3_01_unsupported["swl"],
              "swr": p3_01_unsupported["swr"],
              "jalr": p3_01_unsupported["jalr"],
          })
    check("inventory:p3-01-padding-cross-check",
          p3_01_unsupported["alignment-padding (0x04170001)"]
          == summary["reserved_encoding_words"])
    padding_sites_ok = True
    for site in p3_01["unsupported_sites"]["alignment-padding (0x04170001)"]:
        record = by_address.get(site["address"])
        if record is None or record["word"] != site["word"] \
                or record["decode_class"] != CLASS_RESERVED:
            padding_sites_ok = False
    check("inventory:p3-01-padding-sites-cross-check", padding_sites_ok)
    site_ok = True
    site_mismatches: list[str] = []
    key_map = {
        "movz": "movz", "movn": "movn", "mul": "mul (SPECIAL2 funct 0x02)",
        "divu": "divu", "teq": "teq", "swl": "swl", "swr": "swr", "jalr": "jalr",
    }
    for op, p3_01_name in key_map.items():
        for site in p3_01["unsupported_sites"].get(p3_01_name, []):
            record = by_address.get(site["address"])
            if record is None or record["word"] != site["word"] \
                    or record["decode_class"] != CLASS_RECOGNIZED_UNSUPPORTED \
                    or record["op"] != op:
                site_ok = False
                site_mismatches.append(f"{op}@0x{site['address']:x}")
    check("inventory:p3-01-recorded-sites-cross-check", site_ok)

    classes: dict[str, list[dict[str, Any]]] = {}
    for op in sorted(EXPECTED_UNSUPPORTED_TOTAL):
        sites = []
        for record in records:
            if record["decode_class"] != CLASS_RECOGNIZED_UNSUPPORTED or record["op"] != op:
                continue
            sites.append({
                "address": hexv(record["address"]),
                "word": hexv(record["word"]),
                "operands": record["operands"],
                "reachability": record["reachability"],
                "semantics": record["semantics"],
                "control_flow": record["control_flow"],
                "terminator": record["terminator"],
            })
        classes[op] = sites

    reserved_sites = [
        {
            "address": hexv(record["address"]),
            "word": hexv(record["word"]),
            "reason": record["reason"],
            "reachability": record["reachability"],
            "operands": record["operands"],
        }
        for record in records if record["decode_class"] == CLASS_RESERVED
    ]

    rows = [_record_row(record, record["reachability"]) for record in records]
    rows_sha256 = sha256_bytes("\n".join(rows).encode("ascii"))
    inventory = {
        "stage": STAGE,
        "source": {
            "elf_sha256": ELF_SHA256,
            "elf_size": ELF_SIZE,
            "text_vaddr": hexv(TEXT_VADDR),
            "text_size": TEXT_SIZE,
            "text_words": TEXT_WORDS,
            "entry": hexv(ENTRY),
        },
        "semantics_model": {
            "SUPPORTED": "decoded by the frozen bounded adapter with semantic support",
            "RECOGNIZED_UNSUPPORTED": "decoded with exact operands; execution/translation semantics explicitly unsupported",
            "RESERVED_ENCODING": "reserved encoding in a known field space; never interpreted",
            "UNKNOWN_ENCODING": "encoding outside the classified table; never interpreted",
        },
        "totals": {
            key: summary[key] for key in (
                "total_words", "decoded_words", "supported_words",
                "recognized_unsupported_words", "reserved_encoding_words",
                "unknown_encoding_words", "invalid_words", "reachable_words",
                "unreachable_words", "reachable_supported_words",
                "reachable_unsupported_words", "reachable_invalid_words")
        },
        "supported_histogram": summary["supported_histogram"],
        "supported_reachable_histogram": summary["supported_reachable_histogram"],
        "unsupported_histogram": summary["unsupported_histogram"],
        "unsupported_reachable_histogram": summary["unsupported_reachable_histogram"],
        "unsupported_unreachable_histogram": summary["unsupported_unreachable_histogram"],
        "unsupported_classes": classes,
        "reserved_encoding_sites": reserved_sites,
        "unknown_encoding_sites": [],
        "rows_sha256": rows_sha256,
        "rows": rows,
    }
    ARTIFACTS[INSTRUCTION_INVENTORY] = evidence_json_bytes(inventory)
    FINDINGS["inventory"] = {
        "totals": inventory["totals"],
        "supported_histogram": summary["supported_histogram"],
        "unsupported_histogram": summary["unsupported_histogram"],
        "unsupported_reachable_histogram": summary["unsupported_reachable_histogram"],
        "unsupported_unreachable_histogram": summary["unsupported_unreachable_histogram"],
        "rows_sha256": rows_sha256,
    }
    return {"by_address": by_address, "classes": classes, "reserved_sites": reserved_sites,
            "rows_sha256": rows_sha256}


# ---------------------------------------------------------------------------
# Reachability, padding classification and control-flow frontier
# ---------------------------------------------------------------------------
def build_unsupported_frontier(by_address: dict[int, dict[str, Any]]) -> dict[str, Any]:
    classes: dict[str, dict[str, Any]] = {}
    for op in sorted(EXPECTED_UNSUPPORTED_TOTAL):
        sites = []
        for address in sorted(by_address):
            record = by_address[address]
            if record["decode_class"] != CLASS_RECOGNIZED_UNSUPPORTED or record["op"] != op:
                continue
            sites.append({
                "address": hexv(address),
                "word": hexv(record["word"]),
                "operands": record["operands"],
                "reachability": record["reachability"],
                "semantics": record["semantics"],
                "control_flow": record["control_flow"],
                "terminator": record["terminator"],
            })
        reachable = sum(1 for site in sites if site["reachability"] == "REACHABLE")
        classes[op] = {
            "count": len(sites),
            "reachable": reachable,
            "unreachable": len(sites) - reachable,
            "semantics_support": "UNSUPPORTED",
            "decode_support": "DECODED",
            "sites": sites,
        }
    jalr = classes["jalr"]
    return {
        "stage": STAGE,
        "semantics_support": "DECODED_BUT_UNSUPPORTED (decode support does not imply semantic support)",
        "histogram": EXPECTED_UNSUPPORTED_TOTAL,
        "reachable_histogram": EXPECTED_UNSUPPORTED_REACHABLE,
        "unreachable_histogram": EXPECTED_UNSUPPORTED_UNREACHABLE,
        "classes": classes,
        "jalr_classification": {
            "count": jalr["count"],
            "reachable": jalr["reachable"],
            "unreachable": jalr["unreachable"],
            "decoded_form": "jalr rd=31 ($ra), rs=25 ($t9) - indirect call",
            "target_resolution": "not statically resolved; no target invented",
            "sites": jalr["sites"],
        },
        "total_recognized_unsupported_words": sum(
            item["count"] for item in classes.values()),
    }


def build_reachable_map(result: dict[str, Any]) -> dict[str, Any]:
    records = result["records"]
    reachable = set(result["reachable_addresses"])
    start = result["region"]["start"]
    end = result["region"]["end"]

    def ranges(addresses: list[int]) -> list[list[str]]:
        output: list[list[str]] = []
        run_start = None
        previous = None
        for address in addresses:
            if run_start is None:
                run_start = address
            elif address != previous + 4:
                output.append([hexv(run_start), hexv(previous + 4)])
                run_start = address
            previous = address
        if run_start is not None:
            output.append([hexv(run_start), hexv(previous + 4)])
        return output

    reachability_rows = [
        f"{hexv(record['address'])} {record['reachability']}" for record in records
    ]
    unreachable = len(records) - len(reachable)
    return {
        "stage": STAGE,
        "entry": hexv(result["entry"]),
        "region": {"start": hexv(start), "end": hexv(end), "words": result["region"]["words"]},
        "reachable_words": len(reachable),
        "unreachable_words": unreachable,
        "padding_word_count": len(EXPECTED_PADDING),
        "unreached_code_word_count": unreachable - len(EXPECTED_PADDING),
        "reachable_ranges": ranges(sorted(reachable)),
        "unreachable_ranges": ranges(result["unreachable_addresses"]),
        "padding_addresses": [hexv(address) for address in EXPECTED_PADDING],
        "reachability_sha256": sha256_bytes("\n".join(reachability_rows).encode("ascii")),
        "discovery_model": (
            "static discovery from the ELF entry point through direct control flow "
            "with MIPS32 delay slots; indirect targets never invented; reserved/unknown "
            "encodings and unresolvable delay slots stop flow"
        ),
    }


def audit_padding(
    ingested,
    result: dict[str, Any],
    classified: list[dict[str, Any]],
) -> dict[str, Any]:
    parsed = ingested.parsed
    functions = [symbol for symbol in parsed.symbols() if symbol.is_function and symbol.size]
    function_ranges = [(symbol.value, symbol.value + symbol.size) for symbol in functions]
    function_by_start = {symbol.value: symbol.name for symbol in functions}

    covered: set[int] = set()
    for start, end in function_ranges:
        covered.update(range(start, end, 4))
    text_start = TEXT_VADDR
    text_end = TEXT_VADDR + TEXT_SIZE
    words = set(range(text_start, text_end, 4))
    check("padding:function-ranges-disjoint",
          sum(len(range(start, end, 4)) for start, end in function_ranges) == len(covered))
    outside = sorted(words - covered)
    check("padding:non-function-words-are-padding", tuple(outside) == EXPECTED_PADDING)

    padding = [item for item in classified if item["code_class"] == PADDING_NON_CODE]
    check("padding:unreachable-classification-count", len(padding) == len(EXPECTED_PADDING))
    check("padding:unreachable-classification-addresses",
          tuple(sorted(item["address"] for item in padding)) == EXPECTED_PADDING)
    check("padding:unreachable-decoded-code-count",
          sum(1 for item in classified if item["code_class"] == UNREACHED_CODE) == 1301)

    by_address = {record["address"]: record for record in result["records"]}
    runs: list[dict[str, Any]] = []
    run_start = None
    run_addresses: list[int] = []
    for address in sorted(EXPECTED_PADDING) + [None]:
        if address is not None and (run_start is None or address == run_addresses[-1] + 4):
            if run_start is None:
                run_start = address
            run_addresses.append(address)
            continue
        runs.append({
            "start": run_start, "end": run_addresses[-1] + 4, "addresses": list(run_addresses)})
        run_start = address
        run_addresses = [address] if address is not None else []

    check("padding:run-count", len(runs) == len(EXPECTED_PADDING_RUNS))
    run_details: list[dict[str, Any]] = []
    for run, expected in zip(runs, EXPECTED_PADDING_RUNS):
        start, end, owner, delay, following = expected
        check(f"padding:run-start:0x{start:x}", run["start"] == start)
        check(f"padding:run-end:0x{end:x}", run["end"] == end)
        owner_record = by_address[owner]
        delay_record = by_address[delay]
        check(f"padding:preceding-return:0x{owner:x}", owner_record["terminator"] == TERM_RETURN)
        check(f"padding:preceding-delay-slot:0x{delay:x}",
              delay + 4 == start and not delay_record["control_flow"])
        check(f"padding:following-function:{following}",
              function_by_start.get(run["end"]) == following)
        for address in run["addresses"]:
            record = by_address[address]
            check(f"padding:reserved:0x{address:x}", record["decode_class"] == CLASS_RESERVED)
            check(f"padding:unreachable:0x{address:x}", record["reachability"] == "UNREACHABLE")
            check(f"padding:word:0x{address:x}", record["word"] == 0x04170001)
        run_details.append({
            "start": hexv(start), "end": hexv(end),
            "addresses": [hexv(item) for item in run["addresses"]],
            "preceding_return_site": hexv(owner),
            "preceding_delay_slot": hexv(delay),
            "following_function_symbol": following,
            "following_function_address": hexv(run["end"]),
        })

    all_reachable_reserved = [
        record["address"] for record in result["records"]
        if record["decode_class"] == CLASS_RESERVED and record["reachability"] == "REACHABLE"
    ]
    check("padding:no-reachable-reserved-encoding", not all_reachable_reserved)
    analysis = {
        "stage": STAGE,
        "classification": PADDING_NON_CODE,
        "word_encoding": "0x04170001",
        "encoding_interpretation": (
            "opcode 0x01 (REGIMM) with rt=0x17; rt=0x17 is unassigned in the MIPS32 "
            "REGIMM encoding space, so the word is a reserved encoding and is never "
            "interpreted as an instruction"
        ),
        "evidence_elements": [
            "not reachable from the ELF entry point through direct control-flow discovery",
            "reserved encoding (REGIMM rt=0x17 unassigned)",
            "outside every function symbol range; each run starts immediately after a function's "
            "return and its delay slot and ends exactly at the next function symbol start",
        ],
        "symbol_assisted": True,
        "symbol_usage": "cross-check only; reachability and decoding do not depend on symbols",
        "runs": run_details,
        "padding_word_count": len(EXPECTED_PADDING),
        "reachable_reserved_count": 0,
        "unreached_code_words": sum(1 for item in classified if item["code_class"] == UNREACHED_CODE),
    }
    ARTIFACTS[INVALID_PADDING_ANALYSIS] = evidence_json_bytes(analysis)
    return analysis


def _hex_control_flow(control: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, sites in control.items():
        converted = []
        for site in sites:
            item = {"site": hexv(site["site"]), "op": site["op"]}
            if "target" in site:
                item["target"] = hexv(site["target"])
            if "link" in site:
                item["link"] = site["link"]
            if "operands" in site:
                item["operands"] = site["operands"]
            converted.append(item)
        output[key] = converted
    return output


def _hex_unresolved(unresolved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for item in unresolved:
        converted = dict(item)
        if "site" in converted:
            converted["site"] = hexv(converted["site"])
        if "target" in converted:
            converted["target"] = hexv(converted["target"])
        output.append(converted)
    return output


def audit_control_flow(result: dict[str, Any], by_address: dict[int, dict[str, Any]]) -> dict[str, Any]:
    control = result["control_flow"]
    counts = result["summary"]["control_flow_site_counts"]
    check("control:counts", counts == EXPECTED_TOTALS["control_flow_site_counts"])
    check("control:unresolved-counts",
          result["summary"]["unresolved_site_counts"] == EXPECTED_TOTALS["unresolved_site_counts"])
    check("control:delay-slots", len(result["delay_slots"]) == EXPECTED_DELAY_SLOTS)
    check("control:no-target-into-delay-slot", not result["diagnostics"]["target-into-delay-slot"])
    check("control:no-delay-slot-fallthrough", not result["diagnostics"]["delay-slot-reached-by-fallthrough"])

    branch_targets = [site["target"] for site in control["conditional-branches"]]
    check("control:branch-targets-inside-region",
          all(TEXT_VADDR <= target < TEXT_VADDR + TEXT_SIZE for target in branch_targets))
    call_targets = [site["target"] for site in control["direct-calls"]]
    check("control:call-targets-inside-region",
          all(TEXT_VADDR <= target < TEXT_VADDR + TEXT_SIZE for target in call_targets))

    indirect_sites_all: list[dict[str, Any]] = []
    for address in sorted(by_address):
        record = by_address[address]
        if record["op"] == "jalr" or (record["op"] == "jr" and record["operands"].get("rs") != 31):
            indirect_sites_all.append({
                "address": hexv(address),
                "word": hexv(record["word"]),
                "op": record["op"],
                "operands": record["operands"],
                "reachability": record["reachability"],
                "terminator": record["terminator"],
                "target_resolution": "not statically resolved",
            })
    reachable_indirect = tuple(
        item["address"] for item in indirect_sites_all if item["reachability"] == "REACHABLE")
    expected_reachable = tuple(hexv(item) for item in EXPECTED_REACHABLE_INDIRECT_JR)
    check("control:indirect-sites-all-count", len(indirect_sites_all) == 4)
    check("control:reachable-indirect-jr", reachable_indirect == expected_reachable)
    jalr_sites = [item for item in indirect_sites_all if item["op"] == "jalr"]
    check("control:jalr-site", len(jalr_sites) == 1
          and jalr_sites[0]["address"] == hexv(EXPECTED_UNREACHABLE_JALR)
          and jalr_sites[0]["reachability"] == "UNREACHABLE"
          and jalr_sites[0]["operands"] == {"rs": 25, "rd": 31}
          and jalr_sites[0]["terminator"] == TERM_INDIRECT_CALL)

    unresolved = result["unresolved"]
    boundary = [item for item in unresolved if item["kind"] == "successor-outside-image"]
    check("control:boundary-successor",
          len(boundary) == 1
          and boundary[0]["site"] == EXPECTED_BOUNDARY_SUCCESSOR["site"]
          and boundary[0]["kind"] == EXPECTED_BOUNDARY_SUCCESSOR["kind"]
          and boundary[0]["target"] == EXPECTED_BOUNDARY_SUCCESSOR["target"])
    check("control:unresolved-sites-are-known",
          all(item["kind"] in ("indirect-jump", "successor-outside-image") for item in unresolved))

    exception_sites = tuple(
        (item["site"], item["op"]) for item in result["exception_sites"])
    check("control:exception-sites", exception_sites == EXPECTED_EXCEPTION_SITES)

    frontier = {
        "stage": STAGE,
        "reachable": _hex_control_flow(control),
        "reachable_counts": counts,
        "delay_slot_count": len(result["delay_slots"]),
        "unresolved": _hex_unresolved(unresolved),
        "unresolved_counts": result["summary"]["unresolved_site_counts"],
        "indirect_sites_all": indirect_sites_all,
        "exception_frontier": _hex_unresolved(result["exception_sites"]),
        "diagnostics": result["diagnostics"],
        "boundary_notes": [
            {
                "site": hexv(EXPECTED_BOUNDARY_SUCCESSOR["site"]),
                "word": "0x1000ffff",
                "interpretation": (
                    "beq $zero,$zero,-1 (branch-to-self infinite loop at the end of "
                    "_start); the always-taken target is the instruction itself and the "
                    "not-taken successor 0x467c leaves the executable region"
                ),
            },
        ],
    }
    ARTIFACTS[CONTROL_FLOW_FRONTIER] = evidence_json_bytes(frontier)
    return frontier


def compute_function_diagnostics(ingested, result: dict[str, Any]) -> dict[str, Any]:
    parsed = ingested.parsed
    reachable = set(result["reachable_addresses"])
    functions = [symbol for symbol in parsed.symbols() if symbol.is_function and symbol.size]
    diagnostics: list[dict[str, Any]] = []
    dead: list[str] = []
    partial: dict[str, tuple[int, int]] = {}
    for symbol in sorted(functions, key=lambda item: item.value):
        total = symbol.size // 4
        reachable_count = sum(
            1 for address in range(symbol.value, symbol.value + symbol.size, 4)
            if address in reachable)
        entry = {
            "name": symbol.name,
            "address": hexv(symbol.value),
            "size": symbol.size,
            "words": total,
            "reachable_words": reachable_count,
        }
        if reachable_count == 0:
            dead.append(symbol.name)
        elif reachable_count != total:
            partial[symbol.name] = (reachable_count, total)
            entry["classification"] = "PARTIAL_INDIRECT_OR_UNRESOLVED"
        else:
            entry["classification"] = "FULLY_REACHABLE"
        diagnostics.append(entry)
    return {"functions": diagnostics, "dead": sorted(dead), "partial": partial}


def audit_reachability(ingested, result: dict[str, Any]) -> dict[str, Any]:
    summary = result["summary"]
    for key, expected in EXPECTED_TOTALS.items():
        if key in ("control_flow_site_counts", "unresolved_site_counts"):
            continue
        check(f"reachability:total:{key}", summary[key] == expected)

    classified = unreachable_classification(result["records"], [
        (symbol.value, symbol.value + symbol.size)
        for symbol in ingested.parsed.symbols() if symbol.is_function and symbol.size
    ])
    check("reachability:unreachable-partition",
          len(classified) == summary["unreachable_words"])

    padding = audit_padding(ingested, result, classified)
    unsupported = build_unsupported_frontier({record["address"]: record for record in result["records"]})
    check("frontier:unsupported-total",
          unsupported["total_recognized_unsupported_words"] == EXPECTED_TOTALS["recognized_unsupported_words"])
    check("frontier:unsupported-histogram", unsupported["histogram"] == EXPECTED_UNSUPPORTED_TOTAL)
    check("frontier:jalr", unsupported["jalr_classification"]["count"] == 1
          and unsupported["jalr_classification"]["unreachable"] == 1)

    reachable_map = build_reachable_map(result)
    ARTIFACTS[REACHABLE_CODE_MAP] = evidence_json_bytes(reachable_map)
    ARTIFACTS[UNSUPPORTED_FRONTIER] = evidence_json_bytes(unsupported)
    control_frontier = audit_control_flow(result, {record["address"]: record for record in result["records"]})
    function_diagnostics = compute_function_diagnostics(ingested, result)

    by_name = {entry["name"]: entry for entry in function_diagnostics["functions"]}
    dead = function_diagnostics["dead"]
    check("functions:expected-dead-set", tuple(sorted(dead)) == tuple(sorted(EXPECTED_UNREACHED_FUNCTIONS)))
    check("functions:dead-uart-send-char", by_name["uart_send_char"]["reachable_words"] == 0)
    check("functions:fully-reachable-set",
          all(by_name[name]["reachable_words"] == by_name[name]["words"]
              for name in EXPECTED_FULLY_REACHABLE_FUNCTIONS))
    check("functions:partial-set", function_diagnostics["partial"] == EXPECTED_PARTIAL_FUNCTIONS)

    FINDINGS["reachability"] = {
        "entry": hexv(ENTRY),
        "reachable_words": summary["reachable_words"],
        "unreachable_words": summary["unreachable_words"],
        "padding_words": padding["padding_word_count"],
        "unreached_code_words": padding["unreached_code_words"],
        "control_flow_counts": summary["control_flow_site_counts"],
        "unresolved_counts": summary["unresolved_site_counts"],
        "exception_site_count": summary["exception_site_count"],
        "padding": padding["runs"],
        "dead_function_count": len(dead),
        "dead_functions": sorted(dead),
        "partial_functions": function_diagnostics["partial"],
        "indirect_sites_all": control_frontier["indirect_sites_all"],
        "function_diagnostics": function_diagnostics["functions"],
    }
    return {"result": result, "classified": classified, "padding": padding,
            "unsupported": unsupported, "reachable_map": reachable_map,
            "control_frontier": control_frontier}


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def audit_determinism(data: bytes) -> None:
    first = ingest(data, MIPS32_O32)
    second = ingest(bytes(data), MIPS32_O32)
    first_result = analyze(first.image.read_u32, TEXT_VADDR, TEXT_VADDR + TEXT_SIZE, ENTRY)
    second_result = analyze(second.image.read_u32, TEXT_VADDR, TEXT_VADDR + TEXT_SIZE, ENTRY)
    check("determinism:summary-stable",
          canonical_json_bytes(first_result["summary"]) == canonical_json_bytes(second_result["summary"]))
    check("determinism:records-stable",
          canonical_json_bytes(first_result["records"]) == canonical_json_bytes(second_result["records"]))
    check("determinism:frontier-stable",
          canonical_json_bytes({
              "control_flow": first_result["control_flow"],
              "unresolved": first_result["unresolved"],
              "exception_sites": first_result["exception_sites"],
              "diagnostics": first_result["diagnostics"],
          }) == canonical_json_bytes({
              "control_flow": second_result["control_flow"],
              "unresolved": second_result["unresolved"],
              "exception_sites": second_result["exception_sites"],
              "diagnostics": second_result["diagnostics"],
          }))
    check("determinism:reachable-set-stable",
          first_result["reachable_addresses"] == second_result["reachable_addresses"])

    artifact_hashes = {
        name: sha256_bytes(payload) for name, payload in sorted(ARTIFACTS.items())
    }
    record = {
        "source_sha256": sha256_bytes(data),
        "repeated_classification_identical": True,
        "artifact_sha256": artifact_hashes,
        "rows_sha256": FINDINGS["inventory"]["rows_sha256"],
    }
    ARTIFACTS[DETERMINISM] = evidence_json_bytes(record)
    FINDINGS["determinism"] = record


# ---------------------------------------------------------------------------
# Negative and synthetic fixtures
# ---------------------------------------------------------------------------
def _enc_special(funct: int, rs: int = 0, rt: int = 0, rd: int = 0, shamt: int = 0) -> int:
    return (rs << 21) | (rt << 16) | (rd << 11) | (shamt << 6) | funct


NEGATIVE_DECODE_CASES: tuple[tuple[str, int, str], ...] = (
    ("reserved-regimm-rt-0x17", (1 << 26) | (0x17 << 16) | 1, CLASS_RESERVED),
    ("reserved-regimm-rt-0x0d", (1 << 26) | (0x0D << 16) | 1, CLASS_RESERVED),
    ("reserved-regimm-rt-0x1e", (1 << 26) | (0x1E << 16) | 1, CLASS_RESERVED),
    ("reserved-special-funct-0x05", _enc_special(0x05), CLASS_RESERVED),
    ("reserved-special-funct-0x0e", _enc_special(0x0E), CLASS_RESERVED),
    ("reserved-special-funct-0x17", _enc_special(0x17), CLASS_RESERVED),
    ("reserved-special2-funct-0x03", (0x1C << 26) | 0x03, CLASS_RESERVED),
    ("reserved-special2-funct-0x3f", (0x1C << 26) | 0x3F, CLASS_RESERVED),
    ("unknown-opcode-0x1e", (0x1E << 26), CLASS_UNKNOWN),
    ("unknown-opcode-0x3f", (0x3F << 26), CLASS_UNKNOWN),
    ("malformed-sll-rs-nonzero", _enc_special(0x00, rs=1, rd=1), CLASS_UNKNOWN),
    ("malformed-jr-rt-nonzero", _enc_special(0x08, rs=31, rt=1), CLASS_UNKNOWN),
    ("malformed-mfhi-rs-nonzero", _enc_special(0x10, rs=1, rd=1), CLASS_UNKNOWN),
    ("malformed-mult-rd-nonzero", _enc_special(0x18, rs=1, rt=2, rd=3), CLASS_UNKNOWN),
    ("malformed-branch-rt-nonzero", (0x06 << 26) | (8 << 21) | (1 << 16), CLASS_UNKNOWN),
    ("malformed-lui-rs-nonzero", (0x0F << 26) | (1 << 21) | (1 << 16), CLASS_UNKNOWN),
    ("malformed-movz-shamt-nonzero", _enc_special(0x0A, rs=2, rt=3, rd=4, shamt=5), CLASS_UNKNOWN),
    ("malformed-movn-shamt-nonzero", _enc_special(0x0B, rs=2, rt=3, rd=4, shamt=5), CLASS_UNKNOWN),
    ("malformed-divu-rd-nonzero", _enc_special(0x1B, rs=4, rt=1, rd=2), CLASS_UNKNOWN),
    ("malformed-jalr-rt-nonzero", _enc_special(0x09, rs=25, rt=1, rd=31), CLASS_UNKNOWN),
    ("malformed-mul-shamt-nonzero",
     (0x1C << 26) | (2 << 21) | (1 << 16) | (1 << 11) | (3 << 6) | 0x02, CLASS_UNKNOWN),
)


def _fixture(start: int, words: list[int]) -> dict[int, int]:
    return {start + index * 4: word for index, word in enumerate(words)}


def run_engine(entries: dict[int, int], start: int, end: int, entry: int) -> dict[str, Any]:
    return analyze(lambda address: entries[address], start, end, entry)


def reachable_of(result: dict[str, Any]) -> set[int]:
    return set(result["reachable_addresses"])


def audit_negative_cases() -> None:
    recorded: list[dict[str, Any]] = []
    for name, word, expected_class in NEGATIVE_DECODE_CASES:
        actual = "NONE"
        try:
            record = classify(0x1000, word)
            actual = record["decode_class"]
        except DecodeClassificationError as exc:
            actual = f"REJECTED_{exc.code}"
        recorded.append({
            "fixture": name,
            "kind": "decode-classification",
            "word": hexv(word),
            "expected_class": expected_class,
            "actual_class": actual,
            "status": "PASS" if actual == expected_class else "FAIL",
        })
    for name, word, expected_operands in EXPECTED_DECODE_POSITIVE:
        record = classify(0x1000, word)
        actual_class = record["decode_class"]
        operands_match = record["operands"] == expected_operands
        recorded.append({
            "fixture": f"positive-{name}",
            "kind": "decode-operands",
            "word": hexv(word),
            "expected_class": CLASS_RECOGNIZED_UNSUPPORTED,
            "actual_class": actual_class,
            "expected_operands": expected_operands,
            "actual_operands": record["operands"],
            "semantics": record["semantics"],
            "status": "PASS" if actual_class == CLASS_RECOGNIZED_UNSUPPORTED
            and record["semantics"] == "UNSUPPORTED" and operands_match else "FAIL",
        })
    input_cases = (
        ("misaligned-address", lambda: classify(0x1002, 0), "INVALID_ADDRESS"),
        ("negative-address", lambda: classify(-4, 0), "INVALID_ADDRESS"),
        ("word-too-large", lambda: classify(0x1000, 0x100000000), "INVALID_WORD"),
        ("word-negative", lambda: classify(0x1000, -1), "INVALID_WORD"),
        ("empty-region", lambda: analyze(lambda address: 0, 0x1000, 0x1000, 0x1000), "EMPTY_REGION"),
        ("misaligned-region", lambda: analyze(lambda address: 0, 0x1002, 0x1020, 0x1002), "INVALID_REGION"),
        ("entry-outside-region", lambda: analyze(lambda address: 0, 0x1000, 0x1020, 0x1020), "INVALID_ENTRY"),
        ("reader-out-of-range", lambda: analyze(lambda address: 0x100000000, 0x1000, 0x1010, 0x1000), "INVALID_WORD"),
    )
    for name, action, expected_code in input_cases:
        actual = "NONE"
        try:
            action()
        except DecodeClassificationError as exc:
            actual = exc.code
        except FrontierError as exc:
            actual = exc.code
        recorded.append({
            "fixture": name,
            "kind": "input-validation",
            "expected_class": expected_code,
            "actual_class": actual,
            "status": "PASS" if actual == expected_code else "FAIL",
        })

    nop = 0x00000000
    jr_ra = 0x03E00008
    jr_t0 = 0x01000008
    jalr_ra_t9 = 0x0320F809
    addiu_t0 = 0x24080001
    beq_t0_t1_1008 = 0x11090001
    beq_t0_t1_100C = 0x11090002
    j_1010 = 0x08000404
    jal_1010 = 0x0C000404
    j_2000 = 0x08000800
    reserved = 0x04170001
    unknown = 0xFC000000
    bltzl_t0 = 0x05020001

    linear = _fixture(0x1000, [addiu_t0, jr_ra, nop, jr_ra])
    linear_result = run_engine(linear, 0x1000, 0x1010, 0x1000)
    check("engine:linear-reachable", reachable_of(linear_result) == {0x1000, 0x1004, 0x1008})
    check("engine:linear-return-count",
          linear_result["summary"]["control_flow_site_counts"]["returns"] == 1)

    call = _fixture(0x1000, [jal_1010, nop, jr_ra, nop, addiu_t0, jr_ra, nop, jr_ra])
    call_result = run_engine(call, 0x1000, 0x1020, 0x1000)
    check("engine:direct-call-discovers-callee",
          reachable_of(call_result) == {0x1000, 0x1004, 0x1008, 0x100C, 0x1010, 0x1014, 0x1018})
    check("engine:direct-call-count",
          call_result["summary"]["control_flow_site_counts"]["direct-calls"] == 1)

    branch = _fixture(0x1000, [beq_t0_t1_100C, addiu_t0, addiu_t0, jr_ra, nop, jr_ra])
    branch_result = run_engine(branch, 0x1000, 0x1018, 0x1000)
    check("engine:branch-targets",
          reachable_of(branch_result) == {0x1000, 0x1004, 0x1008, 0x100C, 0x1010})
    check("engine:branch-count",
          branch_result["summary"]["control_flow_site_counts"]["conditional-branches"] == 1)

    delay_slot = _fixture(0x1000, [j_1010, addiu_t0, jr_ra, nop, jr_ra, nop])
    delay_result = run_engine(delay_slot, 0x1000, 0x1018, 0x1000)
    check("engine:delay-slot-reachable", 0x1004 in reachable_of(delay_result))
    check("engine:delay-slot-no-fallthrough",
          reachable_of(delay_result) == {0x1000, 0x1004, 0x1010, 0x1014})

    return_beq = _fixture(0x1000, [jr_ra, nop, jr_ra, nop])
    return_result = run_engine(return_beq, 0x1000, 0x1010, 0x1000)
    check("engine:return-stops-flow", reachable_of(return_result) == {0x1000, 0x1004})

    indirect_jump = _fixture(0x1000, [jr_t0, nop, jr_ra, nop])
    indirect_result = run_engine(indirect_jump, 0x1000, 0x1010, 0x1000)
    check("engine:indirect-jump-unresolved",
          reachable_of(indirect_result) == {0x1000, 0x1004}
          and any(item["kind"] == "indirect-jump" for item in indirect_result["unresolved"]))
    check("engine:indirect-jump-count",
          indirect_result["summary"]["control_flow_site_counts"]["indirect-jumps"] == 1)

    indirect_call = _fixture(0x1000, [jalr_ra_t9, nop, jr_ra, nop, nop, nop])
    indirect_call_result = run_engine(indirect_call, 0x1000, 0x1018, 0x1000)
    check("engine:indirect-call-continuation",
          reachable_of(indirect_call_result) == {0x1000, 0x1004, 0x1008, 0x100C})
    check("engine:indirect-call-unresolved",
          any(item["kind"] == "indirect-call" for item in indirect_call_result["unresolved"]))
    check("engine:indirect-call-count",
          indirect_call_result["summary"]["control_flow_site_counts"]["indirect-calls"] == 1)

    reserved_reachable = _fixture(0x1000, [reserved, jr_ra, nop, nop])
    reserved_result = run_engine(reserved_reachable, 0x1000, 0x1010, 0x1000)
    check("engine:reachable-reserved-fail-closed",
          reachable_of(reserved_result) == {0x1000}
          and any(item["kind"] == "reserved-encoding" for item in reserved_result["unresolved"])
          and reserved_result["summary"]["reachable_invalid_words"] == 1)

    unknown_reachable = _fixture(0x1000, [unknown, jr_ra, nop, nop])
    unknown_result = run_engine(unknown_reachable, 0x1000, 0x1010, 0x1000)
    check("engine:reachable-unknown-fail-closed",
          reachable_of(unknown_result) == {0x1000}
          and any(item["kind"] == "unknown-encoding" for item in unknown_result["unresolved"]))

    boundary = _fixture(0x1000, [j_2000, nop, jr_ra, nop])
    boundary_result = run_engine(boundary, 0x1000, 0x1010, 0x1000)
    check("engine:successor-outside-image",
          any(item["kind"] == "successor-outside-image" for item in boundary_result["unresolved"]))

    branch_in_delay = _fixture(0x1000, [beq_t0_t1_100C, jr_ra, jr_ra, nop, jr_ra, nop])
    branch_delay_result = run_engine(branch_in_delay, 0x1000, 0x1018, 0x1000)
    check("engine:control-in-delay-slot-fail-closed",
          reachable_of(branch_delay_result) == {0x1000}
          and any(item["kind"] == "control-transfer-in-delay-slot"
                  for item in branch_delay_result["unresolved"]))

    likely = _fixture(0x1000, [bltzl_t0, nop, jr_ra, nop])
    likely_result = run_engine(likely, 0x1000, 0x1010, 0x1000)
    check("engine:unsupported-control-fail-closed",
          reachable_of(likely_result) == {0x1000, 0x1004}
          and any(item["kind"] == "unsupported-control-transfer" for item in likely_result["unresolved"])
          and likely_result["summary"]["control_flow_site_counts"]["unsupported-control-transfers"] == 1)

    syscall = 0x0000000C
    external_trap = _fixture(0x1000, [syscall, nop, jr_ra, nop])
    external_result = run_engine(external_trap, 0x1000, 0x1010, 0x1000)
    check("engine:external-trap-fail-closed",
          reachable_of(external_result) == {0x1000}
          and any(item["kind"] == "external-trap" for item in external_result["unresolved"])
          and not external_result["delay_slots"])

    padding_records = [
        {"address": 0x1000, "word": reserved, "decode_class": CLASS_RESERVED, "op": None,
         "reachability": "UNREACHABLE"},
        {"address": 0x1004, "word": addiu_t0, "decode_class": CLASS_SUPPORTED, "op": "addiu",
         "reachability": "UNREACHABLE"},
    ]
    padding_classified = unreachable_classification(padding_records, [(0x2000, 0x2010)])
    check("engine:unreachable-classification",
          padding_classified[0]["code_class"] == PADDING_NON_CODE
          and padding_classified[1]["code_class"] == UNREACHED_CODE)

    dead_cases = [item for item in recorded if item["status"] != "PASS"]
    for item in recorded:
        check(f"negative:{item['fixture']}", item["status"] == "PASS")
    ARTIFACTS[NEGATIVE_RESULTS] = evidence_json_bytes({
        "decode_classification_cases": len(NEGATIVE_DECODE_CASES),
        "positive_decode_cases": len(EXPECTED_DECODE_POSITIVE),
        "input_validation_cases": len(input_cases),
        "engine_cases": 14,
        "failed": len(dead_cases),
        "cases": recorded,
    })
    FINDINGS["negative_cases"] = {
        "total": len(recorded),
        "failed": len(dead_cases),
        "cases": recorded,
    }


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
    parser = argparse.ArgumentParser(description="P3-03 CoreMark decode-frontier gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-03")
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

    print("=== P3-03 CoreMark Decode Frontier Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    evidence_files: dict[str, str] = {}
    try:
        section("source_integrity", audit_source_integrity)
        print("\n--- fixture ---", flush=True)
        data = audit_fixture(elf_path)
        print("\n--- input integrity ---", flush=True)
        ingested, words = audit_input_integrity(data)
        print("\n--- decode inventory ---", flush=True)
        probe = analyze(ingested.image.read_u32, TEXT_VADDR, TEXT_VADDR + TEXT_SIZE, ENTRY)
        audit_inventory(words, probe)
        section("reachability", audit_reachability, ingested, probe)
        section("negative_cases", audit_negative_cases)
        section("determinism", audit_determinism, data)
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
