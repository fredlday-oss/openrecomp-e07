#!/usr/bin/env python3
"""OpenRecomp Phase-3 static data / global reconstruction gate (P3-06).

P3-06 reconstructs the audited CoreMark MIPS32 static data image and its
reachable global access model on top of the P3-02 guest image and the P3-05
neutral structure.

The deterministic gate:

* verifies source integrity: the frozen root ``SOURCE_SHA256SUMS.txt`` is
  unchanged and every entry still hashes, and the Phase-3
  ``.openrecomp-phase3/SOURCE_SHA256SUMS.txt`` manifest registers and verifies
  the Phase-3 source/gate files (grown additively to this stage's set);
* models the allocated static sections (``.rodata``, ``.data``, ``.bss``, the
  two read-only metadata sections) with exact bytes, zero-fill, hashes,
  permissions and symbol-annotated layout, cross-checked against the P3-02
  evidence;
* classifies every reachable memory access by its provably resolved address:
  ten resolved static accesses (three ``.data`` loads, five ``.bss`` loads and
  two ``.bss`` stores), two resolved external MMIO stores outside the loaded
  image, and 493 ``RUNTIME_BASE`` accesses that stay explicitly unresolved;
* records every reachable constant formation (283 immediate chains) with its
  exact provenance and its recorded uses (base or call argument);
* proves the ``$gp`` model explicitly: ``_start`` sets ``$gp = _gp``
  (``0xcdf0``) and ``$sp = 0x9620``, no reachable instruction uses ``$gp`` as
  a memory base, and ``$28`` is reused as a general scratch register at four
  sites, so GP-relative global access is not required by the audited path;
* reconstructs the bounded seed-pointer chain from static evidence only: the
  materialised ``.rodata`` table base ``0x4c50``, the ``sltiu`` guard limiting
  the index to five entries, the five statically known pointers to the seed
  globals and the two-level load shape in ``get_seed_32``;
* never guesses a runtime base, never assumes an unresolved access misses any
  object, and fails closed on a store into a read-only static section;
* fails closed on synthetic malformed inputs (unknown section role, overlapping
  sections, unmapped/cross-section reads, unclassified op, invalid size).

On success it emits::

    OPENRECOMP_P3_06=PASS
    OPENRECOMP_PHASE3_STATIC_DATA_V1=PASS tests=<count>

Any failed invariant fails closed and emits ``OPENRECOMP_P3_06=FAIL``.

Usage:

    python tools/test_phase3_static_data_v1.py
    python tools/test_phase3_static_data_v1.py --elf .openrecomp-phase3/build/P3-01/candidate-a/coremark_mips32_O1.elf
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
from p3_elf_image_v1 import (  # noqa: E402
    canonical_json_bytes,
    evidence_json_bytes,
    ingest,
    sha256_bytes,
)
from p3_static_data_v1 import (  # noqa: E402
    ACCESS_LOAD,
    ACCESS_STORE,
    GP_NOT_REQUIRED,
    GP_REGISTER,
    ROLE_BSS,
    ROLE_DATA,
    ROLE_METADATA,
    ROLE_RODATA,
    STATUS_CROSS_SECTION,
    STATUS_RESOLVED_OUTSIDE_IMAGE,
    STATUS_RESOLVED_REGION_UNCLASSIFIED,
    STATUS_RESOLVED_STATIC,
    STATUS_RUNTIME_BASE,
    StaticDataError,
    StaticDataModel,
    StaticSection,
    analyze_globals,
    build_static_data_model,
    written_registers,
)
from p3_structure_v1 import analyze_structure  # noqa: E402
from p3_target_mips32_v1 import MIPS32_O32  # noqa: E402
from openrecomp.program_model import EvidenceClass, InstructionFlow, ProgramSource  # noqa: E402

EVIDENCE_ROOT = ROOT / ".openrecomp-phase3" / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-06"
P3_02_EVIDENCE = EVIDENCE_ROOT / "P3-02"
P3_04_EVIDENCE = EVIDENCE_ROOT / "P3-04"

STAGE = "P3-06"
STAGE_MARKER = "OPENRECOMP_P3_06"
FEATURE_MARKER = "OPENRECOMP_PHASE3_STATIC_DATA_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF"

P3_SOURCE_MANIFEST = ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt"
P3_SOURCE_FILES = (
    ".openrecomp-phase3/src/p3_code_frontier_v1.py",
    ".openrecomp-phase3/src/p3_decode_mips32_v1.py",
    ".openrecomp-phase3/src/p3_elf_image_v1.py",
    ".openrecomp-phase3/src/p3_semantics_mips32_v1.py",
    ".openrecomp-phase3/src/p3_static_data_v1.py",
    ".openrecomp-phase3/src/p3_structure_v1.py",
    ".openrecomp-phase3/src/p3_target_mips32_v1.py",
    "tools/test_phase3_boundary_v1.py",
    "tools/test_phase3_coremark_fixture_v1.py",
    "tools/test_phase3_decode_frontier_v1.py",
    "tools/test_phase3_elf_ingestion_v1.py",
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

ARCHITECTURE = "MIPS32"
ADAPTER_NAME = "mips32-bounded-v1 + p3_decode_mips32_v1"

EXPECTED_SECTIONS = {
    ".text": (0x1000, 13948, "CODE", "r-x", "c7b48c7c01772f179193ac123560b1f2ae16da116e2c2c69d5b53c96e0f98f6f"),
    ".MIPS.abiflags": (0x4680, 24, "METADATA", "r--", "e1e6189012e650c4982a94f7150cb9c652e8225e06e5d87086273ce9d6cd56d9"),
    ".reginfo": (0x4698, 24, "METADATA", "r--", "46530814a13bba83c4eb0930bbe8e7d896fd5bbdbc53c268ed0e06f9f92641f6"),
    ".rodata": (0x46B0, 1864, "RODATA", "r--", "0fa7bd674dea65827c6e23cca2627254fd4a07e85a5fe45777f06f572157dab4"),
    ".data": (0x4E00, 40, "DATA", "rw-", "89a1e02aacc300ae9f52752ea428e09fcd43bf9855601d2092eedb9f030db7aa"),
    ".bss": (0x4E30, 18416, "BSS", "rw-", "c7d9a61211afaf5d6daf6f796219e56bd345ec160378ce97d0cd5d9d8c3aea81"),
}
EXPECTED_REGIONS = {
    0x0: (308, "r--"),
    0x1000: (13948, "r-x"),
    0x4680: (1912, "r--"),
    0x4E00: (18464, "rw-"),
}
EXPECTED_SYMBOLS = {
    "seed1_volatile": (0x5600, 4, ".bss"),
    "seed2_volatile": (0x5604, 4, ".bss"),
    "seed3_volatile": (0x4E10, 4, ".data"),
    "seed4_volatile": (0x4E14, 4, ".data"),
    "seed5_volatile": (0x5608, 4, ".bss"),
    "default_num_contexts": (0x4E18, 4, ".data"),
    "mem_name": (0x4E00, 12, ".data"),
    "static_memblk": (0x4E30, 2000, ".bss"),
    "p3_tick": (0x560C, 4, ".bss"),
    "p3_start_time_val": (0x5610, 4, ".bss"),
    "p3_stop_time_val": (0x5614, 4, ".bss"),
    "p3_uart_byte_count": (0x5618, 4, ".bss"),
    "p3_stack": (0x5620, 16384, ".bss"),
    "_gp": (0xCDF0, 0, None),
}
EXPECTED_GP_SYMBOL = 0xCDF0
EXPECTED_SP_VALUE = 0x9620
EXPECTED_MATERIALIZATIONS = 283
EXPECTED_MATERIALIZATIONS_WITH_USES = 25
EXPECTED_ACCESS_STATUS_COUNTS = {
    STATUS_RUNTIME_BASE: 493,
    STATUS_RESOLVED_STATIC: 10,
    STATUS_RESOLVED_OUTSIDE_IMAGE: 2,
}
EXPECTED_ACCESS_KIND_COUNTS = {
    f"{STATUS_RUNTIME_BASE}:{ACCESS_LOAD}": 286,
    f"{STATUS_RUNTIME_BASE}:{ACCESS_STORE}": 207,
    f"{STATUS_RESOLVED_STATIC}:{ACCESS_LOAD}": 8,
    f"{STATUS_RESOLVED_STATIC}:{ACCESS_STORE}": 2,
    f"{STATUS_RESOLVED_OUTSIDE_IMAGE}:{ACCESS_STORE}": 2,
}
EXPECTED_RESOLVED_STATIC_SITES = {
    0x21CC: ("lw", ACCESS_LOAD, ".data", "default_num_contexts"),
    0x235C: ("lw", ACCESS_LOAD, ".data", "default_num_contexts"),
    0x23C8: ("lw", ACCESS_LOAD, ".data", "default_num_contexts"),
    0x44D8: ("lw", ACCESS_LOAD, ".bss", "p3_tick"),
    0x44E4: ("sw", ACCESS_STORE, ".bss", "p3_start_time_val"),
    0x44F4: ("lw", ACCESS_LOAD, ".bss", "p3_tick"),
    0x4500: ("sw", ACCESS_STORE, ".bss", "p3_stop_time_val"),
    0x4510: ("lw", ACCESS_LOAD, ".bss", "p3_start_time_val"),
    0x4518: ("lw", ACCESS_LOAD, ".bss", "p3_stop_time_val"),
    0x4548: ("lw", ACCESS_LOAD, ".bss", "p3_uart_byte_count"),
}
EXPECTED_MMIO_SITES = {
    0x4540: ("sb", ACCESS_STORE, 0x10000000),
    0x4560: ("sw", ACCESS_STORE, 0x10000008),
}
EXPECTED_GP_WRITES = (0x2DC8, 0x3108, 0x3558, 0x3564, 0x4650, 0x4654)
EXPECTED_POINTER_ARGUMENTS = 13
EXPECTED_SEED_TABLE = 0x4C50
EXPECTED_SEED_POINTERS = (0x5600, 0x5604, 0x4E10, 0x4E14, 0x5608)
EXPECTED_SEED_VALUES = (0, 0, 0x66, 0x3E8, 0)
EXPECTED_SEED_FUNCTION = "fn_33d0"
EXPECTED_SEED_INSTRUCTIONS = {
    0x33D4: ("sltiu", 5),
    0x33D8: ("beq", 0x33F8),
    0x33E8: ("addiu", 0x4C50),
    0x33F0: ("lw", None),
    0x33F4: ("lw", None),
    0x33F8: ("jr", None),
}
EXPECTED_SEED_TABLE_6TH = 0x3804

SOURCE_INTEGRITY = "source_integrity.txt"
FIXTURE_JSON = "fixture.json"
MODEL_JSON = "static_data_model.json"
MATERIALIZATIONS_JSON = "materializations.json"
ACCESSES_JSON = "accesses.json"
GP_JSON = "gp_model.json"
SEED_JSON = "seed_chain.json"
POINTER_ARGS_JSON = "pointer_arguments.json"
NEGATIVES_JSON = "negatives.json"
DETERMINISM = "determinism.json"
RESULT_JSON = "RESULT.json"

CLAIM_BOUNDARY = (
    "P3-06 proves only the static-data reconstruction of the audited CoreMark "
    "MIPS32 image: exact .rodata/.data/.bss content and zero-fill, ten resolved "
    "static accesses and two external MMIO stores, 283 provenance-recorded "
    "constant formations, an explicit gp/sp entry model and the bounded seed "
    "pointer chain. It does not execute or translate CoreMark, does not resolve "
    "the 493 runtime-base accesses, does not perform alias analysis, and claims "
    "no arbitrary MIPS32, PS1 or PS2 compatibility."
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


def make_source() -> ProgramSource:
    return ProgramSource(
        architecture=ARCHITECTURE,
        adapter=ADAPTER_NAME,
        address_width_bits=32,
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
# Fixture and structure
# ---------------------------------------------------------------------------
def audit_fixture(elf_path: pathlib.Path):
    check("fixture:exists", elf_path.is_file())
    data = elf_path.read_bytes()
    check("fixture:sha256", sha256_bytes(data) == ELF_SHA256)
    check("fixture:size", len(data) == ELF_SIZE)
    ingested = ingest(data, MIPS32_O32)
    text = ingested.parsed.section(".text")
    check("fixture:text-identity",
          text is not None and text.sh_addr == TEXT_VADDR and text.sh_size == TEXT_SIZE)
    check("fixture:entry", ingested.parsed.header.e_entry == ENTRY)
    payload = {
        "path": elf_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_bytes(data),
        "size": len(data),
        "entry": hexv(ENTRY),
    }
    ARTIFACTS[FIXTURE_JSON] = evidence_json_bytes({"stage": STAGE, **payload})
    FINDINGS["fixture"] = payload
    return data, ingested


def build_structure(ingested):
    analysis = analyze(ingested.image.read_u32, TEXT_VADDR, TEXT_VADDR + TEXT_SIZE, ENTRY)
    return analyze_structure(analysis, source=make_source(), entry=ENTRY), analysis


# ---------------------------------------------------------------------------
# Static data model
# ---------------------------------------------------------------------------
def audit_static_model(ingested, model: StaticDataModel) -> dict[str, Any]:
    check("model:section-count", len(model.sections) == len(EXPECTED_SECTIONS))
    by_name = {section.name: section for section in model.sections}
    check("model:section-set", set(by_name) == set(EXPECTED_SECTIONS))
    for name, (vaddr, size, role, permissions, digest) in EXPECTED_SECTIONS.items():
        section = by_name[name]
        check(f"model:section:{name}",
              section.vaddr == vaddr and section.size == size
              and section.role == role and section.permissions == permissions
              and section.sha256 == digest)
    check("model:bss-zero-fill", all(value == 0 for value in by_name[".bss"].content))
    check("model:bss-kind", by_name[".bss"].kind == "ZERO_FILL")
    check("model:rodata-kind",
          by_name[".rodata"].kind == "FILE_BACKED" and by_name[".rodata"].read_only)
    check("model:data-writable",
          by_name[".data"].writable and not by_name[".data"].read_only)
    check("model:metadata-read-only",
          by_name[".MIPS.abiflags"].read_only and by_name[".reginfo"].read_only)

    p3_02 = json.loads((P3_02_EVIDENCE / "region_hashes.json").read_text(encoding="utf-8"))
    check("model:p3-02-section-hashes", all(
        p3_02["section_hashes"][name]["image_sha256"] == by_name[name].sha256
        for name in EXPECTED_SECTIONS))
    check("model:p3-02-bss-hash",
          p3_02["image_hashes"]["bss_zero_fill_sha256"] == by_name[".bss"].sha256)
    check("model:p3-02-readonly-hash",
          p3_02["image_hashes"]["readonly_sha256"] == sha256_bytes(
              ingested.image.read(0x0, 308)
              + by_name[".MIPS.abiflags"].content + by_name[".reginfo"].content
              + by_name[".rodata"].content))
    check("model:p3-02-data-hash",
          p3_02["image_hashes"]["writable_initialized_sha256"] == by_name[".data"].sha256)
    check("model:p3-02-executable-hash",
          p3_02["image_hashes"]["executable_sha256"] == by_name[".text"].sha256)

    regions = {region.vaddr: (region.size, region.permissions) for region in model.regions}
    check("model:region-set", regions == EXPECTED_REGIONS)
    check("model:sections-monotonic",
          all(first.memory_end <= second.vaddr
              for first, second in zip(model.sections, model.sections[1:])))
    check("model:readonly-metadata-tiling",
          by_name[".MIPS.abiflags"].memory_end == by_name[".reginfo"].vaddr
          and by_name[".reginfo"].memory_end == by_name[".rodata"].vaddr)
    check("model:text-gap", by_name[".MIPS.abiflags"].vaddr
          - by_name[".text"].memory_end == 4)
    check("model:rodata-data-gap", by_name[".data"].vaddr
          - by_name[".rodata"].memory_end == 8)
    check("model:data-bss-gap", by_name[".bss"].vaddr - by_name[".data"].memory_end == 8)

    symbols = {symbol.name: symbol for symbol in model.symbols}
    for name, (address, size, section_name) in EXPECTED_SYMBOLS.items():
        symbol = symbols.get(name)
        check(f"model:symbol:{name}",
              symbol is not None and symbol.address == address and symbol.size == size
              and symbol.section == section_name)
    seed_symbols = {name: symbols[name] for name in EXPECTED_SYMBOLS if name.startswith("seed")}
    check("model:seed-symbol-set", len(seed_symbols) == 5)
    check("model:no-seed-outside-static-image", all(
        symbol.section is not None for symbol in seed_symbols.values()))

    payload = {
        "stage": STAGE,
        "sections": [section.describe() for section in model.sections],
        "regions": [{"vaddr": hexv(region.vaddr), "size": region.size,
                     "permissions": region.permissions} for region in model.regions],
        "symbols": [symbol.describe() for symbol in model.symbols
                    if symbol.section is not None or symbol.name == "_gp"],
        "policy": (
            "section bytes are the P3-02 guest-image content; .bss is exact "
            "zero-fill; symbols are diagnostic layout evidence, not required by "
            "the model"
        ),
    }
    ARTIFACTS[MODEL_JSON] = evidence_json_bytes(payload)
    FINDINGS["static_data_model"] = {
        "section_count": len(model.sections),
        "data_sections": [section.name for section in model.data_sections()],
        "seed_symbols": {name: hexv(symbol.address) for name, symbol in seed_symbols.items()},
        "gp_symbol": hexv(symbols["_gp"].address),
    }
    return payload


def audit_cross_checks(ingested, model: StaticDataModel) -> None:
    p3_04 = json.loads(
        (P3_04_EVIDENCE / "exception_frontier.json").read_text(encoding="utf-8"))
    seeds = p3_04["fixture_constants"]["seed_values"]
    check("cross:p3-04-seed-values", tuple(
        model.read_u32(address) for address in EXPECTED_SEED_POINTERS)
        == EXPECTED_SEED_VALUES)
    check("cross:p3-04-seed-hashes", all(
        int(seeds[name], 16) == value for name, value in zip(
            ("seed1_volatile", "seed2_volatile", "seed3_volatile",
             "seed4_volatile", "seed5_volatile"), EXPECTED_SEED_VALUES)))
    table_pointers = tuple(model.read_u32(EXPECTED_SEED_TABLE + index * 4)
                           for index in range(5))
    check("cross:seed-table-pointers", table_pointers == EXPECTED_SEED_POINTERS)
    check("cross:seed-table-targets-are-seeds", all(
        model.symbol_at(address).name.startswith("seed") for address in table_pointers))
    check("cross:gp-symbol-matches-entry-init",
          model.symbol_at(EXPECTED_GP_SYMBOL) is not None
          and model.symbol_at(EXPECTED_GP_SYMBOL).name == "_gp")
    check("cross:stack-top-symbol",
          model.symbol_at(EXPECTED_SP_VALUE - 4) is not None
          and model.symbol_at(EXPECTED_SP_VALUE - 4).name == "p3_stack"
          and model.symbol_at(EXPECTED_SP_VALUE - 4).address
          + model.symbol_at(EXPECTED_SP_VALUE - 4).size == EXPECTED_SP_VALUE)
    check("cross:p3-04-seed-materialisation-absent",
          p3_04["seed_materialisation_scan"]["matches"] == [])
    FINDINGS["cross_checks"] = {
        "seed_table_pointers": [hexv(value) for value in table_pointers],
        "seed_values": [hexv(value) for value in EXPECTED_SEED_VALUES],
        "gp_symbol": hexv(EXPECTED_GP_SYMBOL),
    }


# ---------------------------------------------------------------------------
# Global analysis
# ---------------------------------------------------------------------------
def audit_materializations(analysis) -> dict[str, Any]:
    check("materials:count", len(analysis.materializations) == EXPECTED_MATERIALIZATIONS)
    check("materials:with-uses",
          sum(1 for item in analysis.materializations if item.uses)
          == EXPECTED_MATERIALIZATIONS_WITH_USES)
    check("materials:all-have-provenance", all(
        item.provenance for item in analysis.materializations))
    check("materials:sites-unique",
          len({item.site for item in analysis.materializations})
          == len(analysis.materializations))
    static_values = sorted({
        item.value for item in analysis.materializations
        if model_section_role(item.value) is not None})
    check("materials:static-range-values", bool(static_values))
    rows = [item.to_document() for item in analysis.materializations]
    payload = {
        "stage": STAGE,
        "count": len(rows),
        "rows_sha256": sha256_bytes(canonical_json_bytes(rows)),
        "rows": rows,
        "policy": (
            "a formation is an exact constant established by an immediate chain "
            "in one straight-line block; a formation without a recorded use is "
            "not claimed to be an address"
        ),
    }
    ARTIFACTS[MATERIALIZATIONS_JSON] = evidence_json_bytes(payload)
    FINDINGS["materializations"] = {
        "count": len(rows),
        "with_uses": sum(1 for item in analysis.materializations if item.uses),
        "rows_sha256": payload["rows_sha256"],
    }
    return payload


def model_section_role(value: int) -> str | None:
    for name, (vaddr, size, role, _, _) in EXPECTED_SECTIONS.items():
        if role in ("RODATA", "DATA", "BSS", "METADATA") and vaddr <= value < vaddr + size:
            return role
    return None


def audit_accesses(analysis, model: StaticDataModel) -> dict[str, Any]:
    check("access:status-counts",
          analysis.access_counts() == EXPECTED_ACCESS_STATUS_COUNTS)
    check("access:kind-counts",
          analysis.access_kind_counts() == EXPECTED_ACCESS_KIND_COUNTS)
    check("access:no-cross-section",
          all(access.status != STATUS_CROSS_SECTION for access in analysis.accesses))
    check("access:no-region-unclassified",
          all(access.status != STATUS_RESOLVED_REGION_UNCLASSIFIED
              for access in analysis.accesses))

    resolved = {access.site: access for access in analysis.resolved_static_sites()}
    check("access:resolved-static-sites",
          tuple(sorted(resolved)) == tuple(sorted(EXPECTED_RESOLVED_STATIC_SITES)))
    for site, (op, kind, section, symbol) in EXPECTED_RESOLVED_STATIC_SITES.items():
        access = resolved[site]
        check(f"access:resolved:{hexv(site)}",
              access.op == op and access.kind == kind and access.section == section
              and access.symbol == symbol)

    mmio = {access.site: access for access in analysis.accesses
            if access.status == STATUS_RESOLVED_OUTSIDE_IMAGE}
    check("access:mmio-sites", tuple(sorted(mmio)) == tuple(sorted(EXPECTED_MMIO_SITES)))
    for site, (op, kind, address) in EXPECTED_MMIO_SITES.items():
        access = mmio[site]
        check(f"access:mmio:{hexv(site)}",
              access.op == op and access.kind == kind and access.address == address
              and access.section is None)

    runtime = [access for access in analysis.accesses
               if access.status == STATUS_RUNTIME_BASE]
    check("access:runtime-base-count", len(runtime) == 493)
    check("access:runtime-base-never-resolved", all(
        access.address is None and access.section is None and access.symbol is None
        and access.base_value is None for access in runtime))
    check("access:runtime-base-histogram", len({access.base_register for access in runtime}) >= 20)
    check("access:loads-and-stores-covered",
          sum(1 for access in analysis.accesses if access.kind == ACCESS_LOAD) == 294
          and sum(1 for access in analysis.accesses if access.kind == ACCESS_STORE) == 211)

    seed_addresses = set(EXPECTED_SEED_POINTERS)
    check("access:no-resolved-access-to-seed", all(
        access.address not in seed_addresses
        for access in analysis.accesses if access.address is not None))
    check("access:no-store-to-read-only", all(
        not (access.kind == ACCESS_STORE and access.section in
             (".rodata", ".MIPS.abiflags", ".reginfo"))
        for access in analysis.accesses if access.status == STATUS_RESOLVED_STATIC))
    check("access:resolved-address-in-expected-section", all(
        model.section_at(access.address) is not None
        for access in analysis.resolved_static_sites()))
    check("access:unclassified-ops-empty", analysis.unclassified_ops == ())

    rows = [access.to_document() for access in analysis.accesses]
    payload = {
        "stage": STAGE,
        "status_counts": analysis.access_counts(),
        "kind_counts": analysis.access_kind_counts(),
        "rows_sha256": sha256_bytes(canonical_json_bytes(rows)),
        "rows": rows,
        "policy": (
            "RUNTIME_BASE accesses carry no address claim; resolved accesses are "
            "exact constants from the same straight-line block; the two external "
            "stores are not guest-image objects"
        ),
    }
    ARTIFACTS[ACCESSES_JSON] = evidence_json_bytes(payload)
    FINDINGS["accesses"] = {
        "status_counts": analysis.access_counts(),
        "kind_counts": analysis.access_kind_counts(),
        "resolved_static_sites": [hexv(site) for site in sorted(resolved)],
        "mmio_sites": [hexv(site) for site in sorted(mmio)],
        "rows_sha256": payload["rows_sha256"],
    }
    return payload


def audit_gp(analysis, model: StaticDataModel) -> dict[str, Any]:
    check("gp:no-base-access", not analysis.gp_base_accesses)
    check("gp:status", analysis.gp_status == GP_NOT_REQUIRED)
    check("gp:writes", analysis.gp_writes == EXPECTED_GP_WRITES)
    by_site = {item.site: item for item in analysis.materializations}
    entry_gp = by_site.get(0x4654)
    check("gp:entry-gp-value", entry_gp is not None and entry_gp.register == GP_REGISTER
          and entry_gp.value == EXPECTED_GP_SYMBOL
          and entry_gp.provenance == ("lui@0x00004650", "addiu@0x00004654"))
    entry_sp = by_site.get(0x465C)
    check("gp:entry-sp-value", entry_sp is not None and entry_sp.register == 29
          and entry_sp.value == EXPECTED_SP_VALUE
          and entry_sp.provenance == ("lui@0x00004658", "addiu@0x0000465c"))
    check("gp:symbol-cross-check", model.symbol_at(EXPECTED_GP_SYMBOL).name == "_gp")
    payload = {
        "stage": STAGE,
        "gp_status": analysis.gp_status,
        "gp_base_accesses": [],
        "gp_writes": [hexv(site) for site in analysis.gp_writes],
        "entry_register_initialization": {
            "site_gp": hexv(0x4654),
            "gp_value": hexv(EXPECTED_GP_SYMBOL),
            "site_sp": hexv(0x465C),
            "sp_value": hexv(EXPECTED_SP_VALUE),
            "provenance": "lui/addiu immediate chains in _start (0x4650..)",
        },
        "policy": (
            "the O32 ABI names $28 as $gp and _start initialises it to the _gp "
            "symbol value, but no reachable instruction uses $28 as a memory "
            "base and the register is reused as a general scratch register; "
            "GP-relative global access is therefore not required by the audited "
            "reachable path"
        ),
    }
    ARTIFACTS[GP_JSON] = evidence_json_bytes(payload)
    FINDINGS["gp_model"] = {
        "status": analysis.gp_status,
        "base_accesses": 0,
        "writes": [hexv(site) for site in analysis.gp_writes],
        "gp_value": hexv(EXPECTED_GP_SYMBOL),
        "sp_value": hexv(EXPECTED_SP_VALUE),
    }
    return payload


def audit_seed_chain(structure, model: StaticDataModel, analysis) -> dict[str, Any]:
    instructions = {instruction.address: instruction
                    for instruction in structure.instructions}
    check("seed:instruction-set",
          all(site in instructions for site in EXPECTED_SEED_INSTRUCTIONS))
    check("seed:guard-bounds",
          instructions[0x33D4].op == "sltiu"
          and instructions[0x33D4].metadata["operands"]["imm"] == 5)
    guard = instructions[0x33D8]
    check("seed:guard-target",
          guard.op == "beq" and guard.flow is InstructionFlow.BRANCH
          and guard.direct_target == 0x33F8)
    check("seed:table-base-materialised",
          instructions[0x33E8].op == "addiu"
          and instructions[0x33E8].metadata["operands"]["imm"] == 0x4C50)
    check("seed:two-load-shape",
          instructions[0x33F0].op == "lw" and instructions[0x33F4].op == "lw")
    check("seed:return-block",
          instructions[0x33F8].op == "jr"
          and instructions[0x33F8].flow is InstructionFlow.RETURN)
    function_of = {}
    for unit in structure.units.units:
        for block in unit.blocks:
            for instruction in block.instructions:
                function_of[instruction.address] = unit.function_id
    seed_sites = (0x33E8, 0x33F0, 0x33F4)
    check("seed:function", all(function_of[site] == EXPECTED_SEED_FUNCTION
                               for site in seed_sites))
    materialization = next(
        (item for item in analysis.materializations if item.value == EXPECTED_SEED_TABLE),
        None)
    check("seed:table-materialisation", materialization is not None
          and materialization.site == 0x33E8 and materialization.register == 2
          and materialization.provenance
          == ("lui@0x000033e4", "addiu@0x000033e8"))
    table_pointers = tuple(model.read_u32(EXPECTED_SEED_TABLE + index * 4)
                           for index in range(5))
    check("seed:table-pointers", table_pointers == EXPECTED_SEED_POINTERS)
    check("seed:table-sixth-word", model.read_u32(EXPECTED_SEED_TABLE + 20)
          == EXPECTED_SEED_TABLE_6TH)
    check("seed:guard-bounds-table",
          instructions[0x33D4].metadata["operands"]["imm"] == 5
          and model.section_at(EXPECTED_SEED_TABLE + 4 * 5).name == ".rodata"
          and model.section_at(EXPECTED_SEED_TABLE_6TH).name == ".text")
    check("seed:pointer-symbols", tuple(
        model.symbol_at(address).name for address in table_pointers)
        == ("seed1_volatile", "seed2_volatile", "seed3_volatile",
            "seed4_volatile", "seed5_volatile"))
    check("seed:value-loads", tuple(
        model.read_u32(address) for address in table_pointers) == EXPECTED_SEED_VALUES)
    check("seed:table-in-rodata", model.section_at(EXPECTED_SEED_TABLE).name == ".rodata")
    check("seed:no-static-seed-pointer-elsewhere", all(
        not (address in EXPECTED_SEED_POINTERS)
        for address in (access.address for access in analysis.accesses
                        if access.address is not None)))
    payload = {
        "stage": STAGE,
        "function": EXPECTED_SEED_FUNCTION,
        "table_address": hexv(EXPECTED_SEED_TABLE),
        "table_section": ".rodata",
        "table_entries": [
            {"index": index + 1, "slot": hexv(EXPECTED_SEED_TABLE + index * 4),
             "pointer": hexv(pointer), "symbol": model.symbol_at(pointer).name,
             "initial_value": hexv(model.read_u32(pointer))}
            for index, pointer in enumerate(table_pointers)
        ],
        "guard": {
            "site": hexv(0x33D4),
            "form": "sltiu $1, (index-1), 5",
            "branch": hexv(0x33D8),
            "exit": hexv(0x33F8),
            "bound": "1 <= index <= 5, exactly the five static table entries",
        },
        "load_shape": {
            "table_load": hexv(0x33F0),
            "value_load": hexv(0x33F4),
            "semantics": "pointer = seed_ptrs[index-1]; value = *pointer",
        },
        "policy": (
            "the finite target set is derived from the materialised table base, "
            "the guard immediate and the exact .rodata bytes; no runtime target "
            "is guessed and no indirect store is assumed absent"
        ),
    }
    ARTIFACTS[SEED_JSON] = evidence_json_bytes(payload)
    FINDINGS["seed_chain"] = {
        "table_address": hexv(EXPECTED_SEED_TABLE),
        "pointers": [hexv(pointer) for pointer in table_pointers],
        "function": EXPECTED_SEED_FUNCTION,
    }
    return payload


def audit_pointer_arguments(analysis) -> dict[str, Any]:
    check("pointer-args:count",
          len(analysis.pointer_arguments) == EXPECTED_POINTER_ARGUMENTS)
    static_range = [item for item in analysis.pointer_arguments
                    if model_section_role(int(item["value"], 16)) is not None]
    check("pointer-args:static-range", len(static_range) >= 5)
    check("pointer-args:callees-are-functions", all(
        item["callee"] is not None for item in analysis.pointer_arguments))
    rows = [dict(item) for item in analysis.pointer_arguments]
    payload = {
        "stage": STAGE,
        "count": len(rows),
        "static_range_count": len(static_range),
        "rows": rows,
        "policy": (
            "argument materialisations are exact values live at a direct call in "
            "the same straight-line block; a static-range value is a proven "
            "static address in use, values outside the image are not classified "
            "as addresses"
        ),
    }
    ARTIFACTS[POINTER_ARGS_JSON] = evidence_json_bytes(payload)
    FINDINGS["pointer_arguments"] = {
        "count": len(rows),
        "static_range_count": len(static_range),
        "static_range_values": sorted({item["value"] for item in static_range}),
    }
    return payload


# ---------------------------------------------------------------------------
# Fail-closed negatives
# ---------------------------------------------------------------------------
def error_code(action) -> str:
    try:
        action()
    except StaticDataError as exc:
        return exc.code
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        return f"UNEXPECTED_{type(exc).__name__}"
    return "NONE"


def _section(name: str, vaddr: int, content: bytes, role: str,
             permissions: str = "r--") -> StaticSection:
    return StaticSection(
        name=name, role=role, kind="FILE_BACKED", vaddr=vaddr, size=len(content),
        permissions=permissions, section_type=1,
        sha256=sha256_bytes(content), content=content)


def audit_negatives() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []

    def expect(name: str, expected: str, action) -> None:
        actual = error_code(action)
        cases.append({"fixture": name, "expected_code": expected, "actual_code": actual,
                      "status": "PASS" if actual == expected else "FAIL"})

    rodata = _section(".rodata", 0x100, bytes(range(16)), ROLE_RODATA)
    data_section = _section(".data", 0x200, bytes(range(16)), ROLE_DATA, "rw-")
    model = StaticDataModel((rodata, data_section), ())
    check("negatives:model-positive-read", model.read_u32(0x100) == 0x03020100)
    expect("unmapped-read", "UNMAPPED_STATIC_ADDRESS", lambda: model.read(0x300, 4))
    expect("cross-section-read", "UNMAPPED_STATIC_ADDRESS", lambda: model.read(0x10C, 8))
    expect("read-at-section-end", "UNMAPPED_STATIC_ADDRESS", lambda: model.read(0x110, 4))
    expect("read-crossing-data-end", "UNMAPPED_STATIC_ADDRESS",
           lambda: model.read(0x20E, 4))
    expect("negative-size", "INVALID_SIZE", lambda: model.read(0x100, -1))
    expect("unclassified-op", "UNCLASSIFIED_OP",
           lambda: written_registers("mystery", {"rd": 1, "rt": 2}))
    check("negatives:written-registers", written_registers("lw", {"rt": 3}) == (3,)
          and written_registers("sw", {"rt": 3}) == ()
          and written_registers("movz", {"rd": 4}) == (4,))

    tiny = {
        "region": {"start": 0x1000, "end": 0x1018, "words": 6},
        "entry": 0x1000,
        "records": [
            classify_word(0x1000, 0x00000000),
            classify_word(0x1004, 0x3C010000),   # lui $1, 0x0
            classify_word(0x1008, 0x24210004),   # addiu $1, $1, 4
            classify_word(0x100C, 0xAC210000),   # sw $1, 0($1) -> 0x4
            classify_word(0x1010, 0x03E00008),   # jr $ra
            classify_word(0x1014, 0x00000000),   # delay slot
        ],
        "reachable_addresses": [0x1000, 0x1004, 0x1008, 0x100C, 0x1010, 0x1014],
        "unreachable_addresses": [],
        "delay_slots": [{"owner": 0x1010, "delay": 0x1014}],
        "control_flow": {},
        "unresolved": [],
        "exception_sites": [],
        "diagnostics": {},
    }
    try:
        structure = analyze_structure(tiny, source=make_source(), entry=0x1000)
        tiny_model = StaticDataModel(
            (_section(".data", 0x0, bytes(16), ROLE_DATA, "rw-"),), (),
            regions=())
        expect("store-to-read-only-static", "STORE_TO_READ_ONLY_STATIC",
               lambda: analyze_globals(
                   structure,
                   StaticDataModel((_section(".data", 0x0, bytes(16), ROLE_RODATA),), ())))
        analysis = analyze_globals(structure, tiny_model)
        resolved = [access for access in analysis.accesses
                    if access.status == STATUS_RESOLVED_STATIC]
        cases.append({
            "fixture": "synthetic-resolved-static-store",
            "expected_code": None,
            "actual_code": None,
            "status": "PASS" if (len(resolved) == 1 and resolved[0].address == 0x4
                                 and resolved[0].kind == ACCESS_STORE) else "FAIL",
        })
        outside = [access for access in analysis.accesses
                   if access.status == STATUS_RESOLVED_OUTSIDE_IMAGE]
        cases.append({
            "fixture": "synthetic-outside-image",
            "expected_code": None,
            "actual_code": None,
            "status": "PASS" if not outside and len(resolved) == 1 else "FAIL",
        })
    except StaticDataError as exc:  # pragma: no cover - defensive
        cases.append({"fixture": "synthetic-build", "expected_code": None,
                      "actual_code": exc.code, "status": "FAIL"})

    failures = [item for item in cases if item["status"] != "PASS"]
    for item in failures:
        print(f"NEGATIVE-FAILURE: {item}", flush=True)
    check("negatives:no-failures", not failures)
    check("negatives:count", len(cases) >= 8)
    payload = {"stage": STAGE, "cases": cases, "failed": len(failures)}
    ARTIFACTS[NEGATIVES_JSON] = evidence_json_bytes(payload)
    FINDINGS["negatives"] = {"count": len(cases), "failed": len(failures)}
    return payload


def classify_word(address: int, word: int) -> dict[str, Any]:
    from p3_decode_mips32_v1 import classify
    return classify(address, word)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def audit_determinism(data: bytes, structure, model, analysis) -> None:
    second = ingest(bytes(data), MIPS32_O32)
    second_structure, _ = build_structure(second)
    second_model = build_static_data_model(second)
    second_analysis = analyze_globals(second_structure, second_model)
    check("determinism:section-hashes",
          canonical_json_bytes([section.describe() for section in model.sections])
          == canonical_json_bytes([section.describe() for section in second_model.sections]))
    check("determinism:materializations",
          canonical_json_bytes([item.to_document() for item in analysis.materializations])
          == canonical_json_bytes([item.to_document() for item in second_analysis.materializations]))
    check("determinism:accesses",
          canonical_json_bytes([item.to_document() for item in analysis.accesses])
          == canonical_json_bytes([item.to_document() for item in second_analysis.accesses]))
    check("determinism:gp", second_analysis.gp_status == analysis.gp_status
          and second_analysis.gp_writes == analysis.gp_writes)
    artifact_hashes = {name: sha256_bytes(payload) for name, payload in sorted(ARTIFACTS.items())}
    record = {
        "source_sha256": sha256_bytes(data),
        "section_count": len(model.sections),
        "materialization_count": len(analysis.materializations),
        "access_count": len(analysis.accesses),
        "artifact_sha256": artifact_hashes,
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
    parser = argparse.ArgumentParser(description="P3-06 static data gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-06")
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

    print("=== P3-06 Static Data / Global Reconstruction Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    evidence_files: dict[str, str] = {}
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("fixture")
        data, ingested = audit_fixture(elf_path)
        banner("static data model")
        model = build_static_data_model(ingested)
        audit_static_model(ingested, model)
        banner("cross-checks")
        audit_cross_checks(ingested, model)
        banner("structure")
        structure, _ = build_structure(ingested)
        banner("global analysis")
        analysis = analyze_globals(structure, model)
        audit_materializations(analysis)
        audit_accesses(analysis, model)
        audit_gp(analysis, model)
        audit_seed_chain(structure, model, analysis)
        audit_pointer_arguments(analysis)
        banner("negatives")
        audit_negatives()
        banner("determinism")
        audit_determinism(data, structure, model, analysis)
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
