#!/usr/bin/env python3
"""OpenRecomp Phase-3 CoreMark host-emission gate (P3-07).

P3-07 emits the deterministic host C translation of the entire audited CoreMark
MIPS32 executable image plus the host runtime support that executes it through
the frozen P2-08 generic runtime ABI boundary.

The deterministic gate:

* verifies source integrity: the frozen root ``SOURCE_SHA256SUMS.txt`` is
  unchanged and every entry still hashes, and the Phase-3
  ``.openrecomp-phase3/SOURCE_SHA256SUMS.txt`` manifest registers and verifies
  the Phase-3 source/gate files (grown additively to this stage's set);
* re-derives the P3-03 frontier and the P3-06 static-data model from fresh
  bytes and cross-checks the emission inputs;
* emits the whole executable image twice and requires byte-identical output;
* proves the emission covers every decodable word (3479 cases), that no
  invalid/padding word is emitted, that every control transfer has an emitted
  non-control delay slot (620), that every direct target is an emitted word
  (567) and that the four indirect sites are runtime-mediated with no static
  target;
* parses the emitted ``g_image`` initializer and proves it equals the P3-02
  guest image window byte-for-byte, and the emitted region table matches the
  P3-02 segment permissions;
* proves the emitted program uses the frozen P2-08 ABI boundary
  (``or_rt_memory_read``/``or_rt_memory_write``/``or_rt_host_call`` and the two
  service macros) and that the deterministic observable contract is present;
* fails closed on synthetic malformed inputs (unknown op, control in delay
  slot, unemitted delay slot, unemitted direct target, indirect with target,
  unsupported control, external trap, missing operand, invalid shamt, region
  without access);
* proves the emitted text contains no host path, timestamp or UUID.

On success it emits::

    OPENRECOMP_P3_07=PASS
    OPENRECOMP_PHASE3_HOST_EMISSION_V1=PASS tests=<count>

Any failed invariant fails closed and emits ``OPENRECOMP_P3_07=FAIL``.

Usage:

    python tools/test_phase3_host_emit_v1.py
    python tools/test_phase3_host_emit_v1.py --elf .openrecomp-phase3/build/P3-01/candidate-a/coremark_mips32_O1.elf
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
from p3_decode_mips32_v1 import classify, is_invalid  # noqa: E402
from p3_elf_image_v1 import (  # noqa: E402
    canonical_json_bytes,
    evidence_json_bytes,
    ingest,
    sha256_bytes,
)
from p3_host_emit_v1 import (  # noqa: E402
    EXIT_ADDR,
    EXIT_SERVICE,
    IMAGE_WINDOW,
    MAX_STEPS,
    OP_SET,
    UART_ADDR,
    UART_CAPACITY,
    UART_SERVICE,
    HostEmitError,
    emit_instruction,
    emit_program,
    runtime_services,
)
from p3_static_data_v1 import (  # noqa: E402
    MappedRegion,
    StaticDataError,
    StaticDataModel,
    StaticSection,
    build_static_data_model,
)
from p3_target_mips32_v1 import MIPS32_O32  # noqa: E402
from openrecomp import runtime_abi as rt_abi  # noqa: E402

EVIDENCE_ROOT = ROOT / ".openrecomp-phase3" / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-07"
P3_02_EVIDENCE = EVIDENCE_ROOT / "P3-02"
P3_03_EVIDENCE = EVIDENCE_ROOT / "P3-03"

STAGE = "P3-07"
STAGE_MARKER = "OPENRECOMP_P3_07"
FEATURE_MARKER = "OPENRECOMP_PHASE3_HOST_EMISSION_V1"
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
ENTRY = 0x4650

EXPECTED_TOTALS = {
    "total_words": 3487,
    "reachable_words": 2178,
    "unreachable_words": 1309,
}
EXPECTED_CASE_COUNT = 3479
EXPECTED_DELAY_SLOTS = 620
EXPECTED_DIRECT_TARGETS = 567
EXPECTED_INDIRECT_SITES = (0x1958, 0x3130, 0x3830, 0x39A0)
EXPECTED_OP_HISTOGRAM = {
    "addiu": 654, "or": 345, "lw": 275, "nop": 224, "sw": 205, "addu": 171,
    "beq": 170, "andi": 161, "bne": 135, "j": 125, "sll": 106, "jal": 101,
    "srl": 81, "sb": 79, "lbu": 74, "lui": 73, "jr": 52, "xor": 52,
    "lhu": 43, "movz": 35, "subu": 35, "sltiu": 33, "sh": 32, "lh": 28,
    "slt": 24, "mul": 22, "sltu": 19, "ori": 17, "blez": 17, "sra": 13,
    "bgtz": 13, "movn": 12, "and": 11, "slti": 8, "bltz": 4, "mfhi": 4,
    "divu": 4, "teq": 4, "mflo": 4, "multu": 3, "nor": 2, "swl": 2,
    "swr": 2, "xori": 2, "bgez": 2, "jalr": 1,
}
EXPECTED_LINK_HISTOGRAM = {
    "conditional-branch": 341,
    "direct-call": 101,
    "indirect-call": 1,
    "indirect-jump": 3,
    "jump": 125,
    "return": 49,
}
EXPECTED_PADDING = (0x1D8C, 0x25CC, 0x33C8, 0x33CC, 0x36FC, 0x4644, 0x4648, 0x464C)
EXPECTED_REGION_ROWS = (
    (0x0, 0x134, "OR_REGION_READABLE"),
    (0x1000, 0x467C, "OR_REGION_READABLE"),
    (0x4680, 0x4DF8, "OR_REGION_READABLE"),
    (0x4E00, 0x9620, "OR_REGION_READABLE | OR_REGION_WRITABLE"),
)

SOURCE_INTEGRITY = "source_integrity.txt"
FIXTURE_JSON = "fixture.json"
EMISSION_JSON = "emission.json"
COVERAGE_JSON = "coverage.json"
PROGRAM_C = "coremark_program.c"
SUPPORT_C = "coremark_support.c"
NEGATIVES_JSON = "negatives.json"
DETERMINISM = "determinism.json"
RESULT_JSON = "RESULT.json"

CLAIM_BOUNDARY = (
    "P3-07 proves only that the audited CoreMark MIPS32 executable image is "
    "translated deterministically to portable host C with exact audited "
    "semantics, true delay-slot behaviour, runtime-mediated indirect dispatch, "
    "runtime-mediated MMIO and P2-08 ABI memory access. It does not build or "
    "execute the native program (P3-08) and does not yet prove equivalence "
    "against an independent reference (P3-09); it claims no arbitrary MIPS32, "
    "PS1 or PS2 compatibility."
)

HOST_PATH_PATTERN = re.compile(
    rb"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"
    rb"|(?<![\\])\\\\[A-Za-z0-9_.$-]"
    rb"|file://|/tmp/|/var/tmp/|/home/|/Users/|\\Temp\\|\\AppData\\|\\Users\\"
)
TIMESTAMP_PATTERN = re.compile(
    rb"\b(?:19|20)\d\d[-/]\d\d[-/]\d\d\b|\bT\d\d:\d\d:\d\d(?:\.\d+)?Z?\b"
    rb"|\b\d\d:\d\d:\d\d\b"
)
IDENTITY_PATTERN = re.compile(
    rb"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
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
        "phase3_manifest_sha256": phase3_digest,
        "phase3_manifest_entries": len(phase3_entries),
        "phase3_manifest_mismatched": phase3_mismatched,
    }


def audit_inputs(elf_path: pathlib.Path):
    check("fixture:exists", elf_path.is_file())
    data = elf_path.read_bytes()
    check("fixture:sha256", sha256_bytes(data) == ELF_SHA256)
    check("fixture:size", len(data) == ELF_SIZE)
    ingested = ingest(data, MIPS32_O32)
    analysis = analyze(ingested.image.read_u32, TEXT_VADDR, TEXT_VADDR + TEXT_SIZE, ENTRY)
    check("fixture:entry", analysis["entry"] == ENTRY)
    for key, expected in EXPECTED_TOTALS.items():
        check(f"frontier:{key}", analysis["summary"][key] == expected)
    model = build_static_data_model(ingested)
    check("model:regions", tuple(
        (region.vaddr, region.vaddr + region.size) for region in
        sorted(model.regions, key=lambda item: item.vaddr))
        == tuple((start, end) for start, end, _ in EXPECTED_REGION_ROWS))
    payload = {
        "stage": STAGE,
        "elf_sha256": ELF_SHA256,
        "elf_size": ELF_SIZE,
        "entry": f"0x{ENTRY:08x}",
        "decodable_words": EXPECTED_CASE_COUNT,
        "reachable_words": EXPECTED_TOTALS["reachable_words"],
        "unreachable_words": EXPECTED_TOTALS["unreachable_words"],
        "regions": [
            {"start": f"0x{start:08x}", "end": f"0x{end:08x}", "flags": flags}
            for start, end, flags in EXPECTED_REGION_ROWS
        ],
    }
    ARTIFACTS[FIXTURE_JSON] = evidence_json_bytes(payload)
    FINDINGS["inputs"] = payload
    return data, ingested, analysis, model


def emit(analysis, model):
    return emit_program(analysis, model, source_sha256=ELF_SHA256)


def audit_emission(program, analysis, model) -> None:
    check("emission:case-count", program.case_count == EXPECTED_CASE_COUNT)
    check("emission:op-histogram", program.op_histogram == EXPECTED_OP_HISTOGRAM)
    check("emission:op-set-covers-image",
          set(program.op_histogram) <= OP_SET)
    check("emission:delay-slots", program.delay_slots == EXPECTED_DELAY_SLOTS)
    check("emission:direct-targets", program.direct_targets == EXPECTED_DIRECT_TARGETS)
    check("emission:link-histogram", program.link_histogram == EXPECTED_LINK_HISTOGRAM)
    check("emission:indirect-sites",
          tuple(int(site["address"], 16) for site in program.indirect_sites)
          == EXPECTED_INDIRECT_SITES)
    check("emission:indirect-never-static", all(
        "runtime-mediated" in site["resolution"] for site in program.indirect_sites))

    by_address = {record["address"]: record for record in analysis["records"]}
    invalid = tuple(record["address"] for record in analysis["records"] if is_invalid(record))
    check("emission:padding-invalid-set", invalid == EXPECTED_PADDING)
    check("emission:padding-not-emitted",
          all(address not in program.emitted_addresses for address in invalid))
    check("emission:all-decodable-emitted",
          len(program.emitted_addresses) == EXPECTED_CASE_COUNT
          and all(not is_invalid(by_address[address]) for address in program.emitted_addresses))

    text = program.program_text
    check("emission:no-host-path", not HOST_PATH_PATTERN.search(text.encode("utf-8")))
    check("emission:no-timestamp", not TIMESTAMP_PATTERN.search(text.encode("utf-8")))
    check("emission:no-uuid", not IDENTITY_PATTERN.search(text.encode("utf-8")))
    check("emission:ascii-lf",
          text.isascii() and "\r" not in text and "\t" not in text)
    check("emission:case-labels", text.count("\n    case 0x") == EXPECTED_CASE_COUNT)
    check("emission:break-per-case", text.count("\n        break;") == EXPECTED_CASE_COUNT + 1)
    check("emission:default-fails-closed",
          'or_fail("pc outside the emitted image");' in text)
    check("emission:delay-slot-protocol",
          "g_has_pending" in text and "g_pending" in text)
    check("emission:step-limit", f"#define OR_MAX_STEPS {MAX_STEPS}u" in text)
    check("emission:uart-capacity", f"#define OR_UART_CAPACITY {UART_CAPACITY}u" in text)
    check("emission:mmio-addresses",
          f"#define OR_UART_ADDR 0x{UART_ADDR:08x}u" in text
          and f"#define OR_EXIT_ADDR 0x{EXIT_ADDR:08x}u" in text)
    check("emission:abi-memory-boundary",
          "or_rt_memory_read(" in text and "or_rt_memory_write(" in text)
    check("emission:abi-host-call", "or_rt_host_call(" in text)
    check("emission:service-macros",
          f"OR_RT_SERVICE_{UART_SERVICE.upper()}" in text
          and f"OR_RT_SERVICE_{EXIT_SERVICE.upper()}" in text)
    check("emission:fail-closed-unpredictable",
          'or_fail("divide by zero");' in text
          and 'or_fail("unaligned indirect jump target");' in text
          and 'or_fail("unaligned indirect call target");' in text
          and "teq trap code=" in text)
    check("emission:no-forbidden-casts",
          "*(uint32_t *)" not in text and "memcpy" not in text)

    expected_image = bytearray(IMAGE_WINDOW)
    for section in model.sections:
        expected_image[section.vaddr:section.vaddr + section.size] = section.content
    expected_sha = sha256_bytes(bytes(expected_image))
    check("emission:image-sha", program.image_sha256 == expected_sha)

    match = re.search(r"static const uint8_t g_image\[OR_IMAGE_WINDOW\] = \{\n(.*?)\n\};",
                      text, re.S)
    check("emission:image-initializer-present", match is not None)
    parsed = bytes(
        int(token, 16)
        for line in match.group(1).splitlines()
        for token in line.replace(",", " ").split()
        if token.startswith("0x")
    )
    check("emission:image-initializer-length", len(parsed) == IMAGE_WINDOW)
    check("emission:image-initializer-equals-guest-image", parsed == bytes(expected_image))

    region_rows = re.findall(
        r"\{ (0x[0-9a-f]{8}u), (0x[0-9a-f]{8}u), ([^}]+) \},", text)
    check("emission:region-table",
          tuple((int(start.rstrip("u"), 16), int(end.rstrip("u"), 16), flags.strip())
                for start, end, flags in region_rows)
          == EXPECTED_REGION_ROWS)

    support = program.support_text
    check("support:no-host-path", not HOST_PATH_PATTERN.search(support.encode("utf-8")))
    check("support:no-timestamp", not TIMESTAMP_PATTERN.search(support.encode("utf-8")))
    check("support:no-uuid", not IDENTITY_PATTERN.search(support.encode("utf-8")))
    check("support:observable-contract",
          all(token in support for token in (
              "exit_status=", "steps=", "pc=0x", "hi=0x", "lo=0x",
              "uart_bytes=", "uart_hex=", "state_fnv1a64=0x", "failed=", "failure=")))
    check("support:hash-order",
          "or_fnv1a64(hash, g_mem, sizeof(g_mem))" in support
          and "openrecomp_register_value(index)" in support
          and "or_hash_u32(hash, openrecomp_hi())" in support
          and "or_hash_u32(hash, g_uart_len)" in support
          and "or_fnv1a64(hash, g_uart, (size_t)g_uart_len)" in support)
    check("support:region-checked", "or_region_flags(" in support)
    check("support:service-dispatch",
          "OR_RT_SERVICE_P3_UART_WRITE" in support and "OR_RT_SERVICE_P3_EXIT" in support)
    check("support:failure-reasons",
          all(f'"{code}"' in support for code in rt_abi.RUNTIME_FAILURE_CODES))

    payload = {
        "stage": STAGE,
        "program_fingerprint": program.fingerprint,
        "support_fingerprint": program.support_fingerprint,
        "program_bytes": len(program.program_text),
        "support_bytes": len(program.support_text),
        "case_count": program.case_count,
        "delay_slots": program.delay_slots,
        "direct_targets": program.direct_targets,
        "op_histogram": dict(sorted(program.op_histogram.items())),
        "indirect_sites": list(program.indirect_sites),
        "image_sha256": program.image_sha256,
        "model": program.to_document(),
    }
    ARTIFACTS[EMISSION_JSON] = evidence_json_bytes(payload)
    ARTIFACTS[PROGRAM_C] = program.program_text.encode("utf-8")
    ARTIFACTS[SUPPORT_C] = program.support_text.encode("utf-8")
    FINDINGS["emission"] = {
        "program_fingerprint": program.fingerprint,
        "support_fingerprint": program.support_fingerprint,
        "case_count": program.case_count,
        "delay_slots": program.delay_slots,
        "direct_targets": program.direct_targets,
        "indirect_sites": [site["address"] for site in program.indirect_sites],
    }


def audit_coverage(analysis, program) -> None:
    by_op: dict[str, list[dict[str, Any]]] = {}
    for record in analysis["records"]:
        if is_invalid(record):
            continue
        by_op.setdefault(record["op"], []).append(record)
    emitted_ops = sorted(by_op)
    check("coverage:emitted-op-count", len(emitted_ops) == len(EXPECTED_OP_HISTOGRAM))
    check("coverage:emitted-ops", emitted_ops == sorted(EXPECTED_OP_HISTOGRAM))
    rows = []
    for op in emitted_ops:
        record = by_op[op][0]
        try:
            emit_instruction(record)
            rows.append({"op": op, "sites": len(by_op[op]), "status": "EMITTED"})
        except HostEmitError as exc:
            rows.append({"op": op, "sites": len(by_op[op]), "status": exc.code})
    check("coverage:all-ops-emitted",
          all(row["status"] == "EMITTED" for row in rows))
    check("coverage:unused-op-set", sorted(set(OP_SET) - set(emitted_ops)) == [
        "div", "lb", "mult"])
    payload = {
        "stage": STAGE,
        "ops": rows,
        "op_set": sorted(OP_SET),
        "unused_op_set": sorted(set(OP_SET) - set(emitted_ops)),
        "policy": (
            "every op present in the audited image has an explicit emission rule; "
            "OP_SET also carries rules for the audited instruction classes that "
            "are absent from this image (mult, div, lb) so a future image cannot "
            "silently fall through"
        ),
    }
    ARTIFACTS[COVERAGE_JSON] = evidence_json_bytes(payload)
    FINDINGS["coverage"] = {"ops": len(rows), "unused_op_set": payload["unused_op_set"]}


def error_code(action) -> str:
    try:
        action()
    except (HostEmitError, StaticDataError) as exc:
        return exc.code
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        return f"UNEXPECTED_{type(exc).__name__}"
    return "NONE"


def tiny_model() -> StaticDataModel:
    content = bytes(range(16))
    section = StaticSection(
        name=".data", role="DATA", kind="FILE_BACKED", vaddr=0x0, size=16,
        permissions="rw-", section_type=1, sha256=sha256_bytes(content), content=content)
    return StaticDataModel((section,), (), regions=(MappedRegion(0, 16, "rw-"),))


def tiny_analysis(records: list[dict[str, Any]], reachable: list[int],
                  start: int = 0x1000, end: int = 0x1018) -> dict[str, Any]:
    return {
        "region": {"start": start, "end": end, "words": (end - start) // 4},
        "entry": start,
        "records": records,
        "reachable_addresses": reachable,
        "unreachable_addresses": [],
        "delay_slots": [],
        "control_flow": {},
        "unresolved": [],
        "exception_sites": [],
        "diagnostics": {},
    }


def audit_negatives() -> None:
    cases: list[dict[str, Any]] = []

    def expect(name: str, expected: str, action) -> None:
        actual = error_code(action)
        cases.append({"fixture": name, "expected_code": expected, "actual_code": actual,
                      "status": "PASS" if actual == expected else "FAIL"})

    model = tiny_model()
    nop = classify(0x1000, 0x00000000)
    unknown = classify(0x1000, 0x00000000)
    unknown = dict(unknown, op="mystery")

    expect("unknown-op", "UNSUPPORTED_OP",
           lambda: emit_program(
               tiny_analysis([unknown], [0x1000]), model, source_sha256="0" * 64))

    beq = classify(0x1000, 0x10800001)          # beq $4, $0, +4 -> 0x1008
    bad_delay = dict(classify(0x1004, 0x03E00008))  # jr $ra in the delay slot
    expect("control-in-delay-slot", "CONTROL_IN_DELAY_SLOT",
           lambda: emit_program(
               tiny_analysis([beq, bad_delay, classify(0x1008, 0x00000000),
                              classify(0x100C, 0x03E00008),
                              classify(0x1010, 0x00000000)],
                             [0x1000, 0x1004, 0x1008, 0x100C, 0x1010]),
               model, source_sha256="0" * 64))

    j = classify(0x1000, 0x08000420)            # j 0x1080
    expect("direct-target-not-emitted", "DIRECT_TARGET_NOT_EMITTED",
           lambda: emit_program(
               tiny_analysis([j, classify(0x1004, 0x00000000)],
                             [0x1000, 0x1004], end=0x1008),
               model, source_sha256="0" * 64))

    jr_at = classify(0x1000, 0x00200008)        # jr $1
    with_target = dict(jr_at, target=0x1004)
    expect("indirect-with-target", "INDIRECT_WITH_TARGET",
           lambda: emit_program(
               tiny_analysis([with_target, classify(0x1004, 0x00000000)],
                             [0x1000, 0x1004], end=0x1008),
               model, source_sha256="0" * 64))

    bltzl = classify(0x1000, 0x04020000)        # unsupported control transfer
    expect("unsupported-control", "UNSUPPORTED_CONTROL",
           lambda: emit_program(
               tiny_analysis([bltzl, classify(0x1004, 0x00000000)],
                             [0x1000, 0x1004], end=0x1008),
               model, source_sha256="0" * 64))

    syscall = classify(0x1000, 0x0000000C)
    expect("external-trap", "EXTERNAL_TRAP_OP",
           lambda: emit_program(
               tiny_analysis([syscall, classify(0x1004, 0x00000000)],
                             [0x1000, 0x1004], end=0x1008),
               model, source_sha256="0" * 64))

    j_missing_delay = classify(0x1000, 0x08000420)   # j 0x1080, delay 0x1004 absent
    expect("delay-slot-not-emitted", "DELAY_SLOT_NOT_EMITTED",
           lambda: emit_program(
               tiny_analysis([j_missing_delay, classify(0x1008, 0x00000000),
                              classify(0x100C, 0x00000000)],
                             [0x1000, 0x1008, 0x100C], end=0x1010),
               model, source_sha256="0" * 64))
    expect("empty-image", "EMPTY_IMAGE",
           lambda: emit_program(
               tiny_analysis([], [], end=0x1004), model, source_sha256="0" * 64))
    expect("missing-target-operand", "MISSING_OPERAND",
           lambda: emit_instruction(dict(beq, operands={"rs": 4, "rt": 0})))
    shift = classify(0x1000, 0x00000000)
    shift = dict(shift, op="sll", operands={"rt": 2, "rd": 3, "shamt": 32})
    expect("invalid-shamt", "INVALID_SHAMT", lambda: emit_instruction(shift))

    empty_region = StaticDataModel((StaticSection(
        name=".data", role="DATA", kind="FILE_BACKED", vaddr=0x0, size=16,
        permissions="---", section_type=1, sha256=sha256_bytes(bytes(16)),
        content=bytes(16)),), (), regions=(MappedRegion(0, 16, "---"),))
    expect("region-without-access", "REGION_WITHOUT_ACCESS",
           lambda: emit_program(
               tiny_analysis([nop], [0x1000], end=0x1004),
               empty_region, source_sha256="0" * 64))

    failures = [item for item in cases if item["status"] != "PASS"]
    for item in failures:
        print(f"NEGATIVE-FAILURE: {item}", flush=True)
    check("negatives:no-failures", not failures)
    check("negatives:count", len(cases) >= 10)
    payload = {"stage": STAGE, "cases": cases, "failed": len(failures)}
    ARTIFACTS[NEGATIVES_JSON] = evidence_json_bytes(payload)
    FINDINGS["negatives"] = {"count": len(cases), "failed": len(failures)}


def audit_determinism(data: bytes, ingested, analysis, model, program) -> None:
    second_ingest = ingest(bytes(data), MIPS32_O32)
    second_analysis = analyze(
        second_ingest.image.read_u32, TEXT_VADDR, TEXT_VADDR + TEXT_SIZE, ENTRY)
    second_model = build_static_data_model(second_ingest)
    second = emit_program(second_analysis, second_model, source_sha256=ELF_SHA256)
    check("determinism:program-source", second.program_text == program.program_text)
    check("determinism:support-source", second.support_text == program.support_text)
    check("determinism:program-fingerprint", second.fingerprint == program.fingerprint)
    check("determinism:support-fingerprint",
          second.support_fingerprint == program.support_fingerprint)
    check("determinism:counts",
          second.case_count == program.case_count
          and second.delay_slots == program.delay_slots
          and second.direct_targets == program.direct_targets)
    artifact_hashes = {name: sha256_bytes(payload) for name, payload in sorted(ARTIFACTS.items())}
    record = {
        "source_sha256": sha256_bytes(data),
        "program_fingerprint": program.fingerprint,
        "support_fingerprint": program.support_fingerprint,
        "artifact_sha256": artifact_hashes,
    }
    ARTIFACTS[DETERMINISM] = evidence_json_bytes(record)
    FINDINGS["determinism"] = record
    check("determinism:artifact-hashes-recorded", bool(artifact_hashes))


def write_evidence() -> dict[str, str]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for name, payload in sorted(ARTIFACTS.items()):
        (EVIDENCE_DIR / name).write_bytes(payload)
        hashes[name] = sha256_bytes(payload)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser(description="P3-07 host-emission gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-07")
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

    print("=== P3-07 Host Emission Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    evidence_files: dict[str, str] = {}
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("inputs")
        data, ingested, analysis, model = audit_inputs(elf_path)
        banner("emission")
        program = emit(analysis, model)
        audit_emission(program, analysis, model)
        banner("coverage")
        audit_coverage(analysis, program)
        banner("negatives")
        audit_negatives()
        banner("determinism")
        audit_determinism(data, ingested, analysis, model, program)
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
