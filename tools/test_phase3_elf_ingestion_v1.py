#!/usr/bin/env python3
"""OpenRecomp Phase-3 MIPS32 ELF ingestion gate (P3-02).

P3-02 proves fail-closed ingestion of the audited CoreMark MIPS32 ELF and the
deterministic guest section/data image built from it.  It adds no instruction
semantics and does not translate the program.

The deterministic gate:

* verifies source integrity: the frozen root ``SOURCE_SHA256SUMS.txt`` is
  unchanged and every entry still hashes, and the Phase-3
  ``.openrecomp-phase3/SOURCE_SHA256SUMS.txt`` manifest registers and verifies
  the Phase-3 source/gate files;
* verifies the P3-01 fixture identity (sha256 ``16a0a0aa...``, 31184 bytes)
  and that the structurally ingested identity exactly matches the recorded
  P3-01 characterisation (class/endian/machine/type/flags/entry/sections/
  program headers/symbols/relocations);
* ingests the ELF through the architecture-neutral loader
  (``p3_elf_image_v1``) plus the MIPS32 O32 target policy
  (``p3_target_mips32_v1``) and cross-checks the parsed tables against an
  independent raw byte view of the same file;
* builds the deterministic sparse guest image and verifies that reconstructed
  ``.text``/``.rodata``/``.data`` bytes equal the file slices, that ``.bss``
  is exactly zero-filled to the declared size without reading nonexistent file
  bytes, that file-backed / zero-fill / executable / read-only / writable
  distinctions are preserved, and that every access is bounds checked;
* ingests twice and requires byte-identical canonical metadata/image
  serializations (repeated ingestion is deterministic);
* exercises synthetic malformed ELF fixtures (truncated header, wrong
  class/endian/machine, out-of-bounds and overflowing tables/ranges,
  malformed section-name tables, overlapping load ranges, NOBITS misuse,
  dynamic/relocation forms) and requires each one to fail closed with the
  expected deterministic classification.

On success it emits::

    OPENRECOMP_P3_02=PASS
    OPENRECOMP_PHASE3_MIPS32_ELF_INGESTION_V1=PASS tests=<count>

Any failed invariant fails closed and emits ``OPENRECOMP_P3_02=FAIL``.

Usage:

    python tools/test_phase3_elf_ingestion_v1.py
    python tools/test_phase3_elf_ingestion_v1.py --elf .openrecomp-phase3/build/P3-01/candidate-a/coremark_mips32_O1.elf
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import struct
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / ".openrecomp-phase3" / "src"
for candidate in (str(ROOT), str(SRC_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from p3_elf_image_v1 import (  # noqa: E402
    ElfIngestError,
    GuestImageError,
    canonical_json_bytes,
    evidence_json_bytes,
    ingest,
    sha256_bytes,
)
from p3_target_mips32_v1 import MIPS32_O32  # noqa: E402

EVIDENCE_ROOT = ROOT / ".openrecomp-phase3" / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-02"

STAGE = "P3-02"
STAGE_MARKER = "OPENRECOMP_P3_02"
FEATURE_MARKER = "OPENRECOMP_PHASE3_MIPS32_ELF_INGESTION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF"

P3_SOURCE_MANIFEST = ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt"
# The Phase-3 source manifest is the stage-grown registry: later Phase-3 stages
# register their additive source/gate files here (documented in the stage
# evidence and control plane).  P3-02 verifies the complete registry, so this
# list intentionally includes the P3-03 decode/frontier sources and gate as
# well as the P3-04 semantics source and gate (8 -> 10, additive).
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
    "tools/test_phase3_evidence_index_v1.py",
    "tools/test_phase3_final_verdict_v1.py",
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

P3_01_EVIDENCE = EVIDENCE_ROOT / "P3-01" / "elf_characterisation.json"
DEFAULT_ELF = (
    ROOT / ".openrecomp-phase3" / "build" / "P3-01" / "candidate-a"
    / "coremark_mips32_O1.elf"
)
ELF_SHA256 = "16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669"
ELF_SIZE = 31184
EXPECTED_ENTRY = 0x4650
EXPECTED_FLAGS = 0x50001001
EXPECTED_TEXT_ADDRESS = 0x1000
EXPECTED_SECTIONS = {
    ".text": 13948,
    ".rodata": 1864,
    ".data": 40,
    ".bss": 18416,
    ".MIPS.abiflags": 24,
    ".reginfo": 24,
}
EXPECTED_BSS_VADDR = 0x4E30
EXPECTED_BSS_SIZE = 18416
EXPECTED_SEGMENT_TAIL_START = 0x4E28
EXPECTED_SEGMENT_TAIL_SIZE = 18424
EXPECTED_LOAD_REGIONS = (
    {"vaddr": 0x0, "filesz": 308, "memsz": 308, "permissions": "r--", "zero_fill_size": 0},
    {"vaddr": 0x1000, "filesz": 13948, "memsz": 13948, "permissions": "r-x", "zero_fill_size": 0},
    {"vaddr": 0x4680, "filesz": 1912, "memsz": 1912, "permissions": "r--", "zero_fill_size": 0},
    {"vaddr": 0x4E00, "filesz": 40, "memsz": 18464, "permissions": "rw-", "zero_fill_size": 18424},
)
UNMAPPED_PROBES = (0x134, 0x200, 0x467C, 0x4680 - 1, 0x4DF8, 0x4E00 - 1, 0x9620, 0x20000)
CLAIM_BOUNDARY = (
    "P3-02 proves that OpenRecomp can safely and deterministically ingest the "
    "audited CoreMark MIPS32 ELF and construct its guest section/data image. "
    "It does not prove that all CoreMark instructions are supported, that "
    "CoreMark can yet be translated or run, or any arbitrary ELF/MIPS32/"
    "console compatibility."
)

ELF_PARSED_METADATA = "elf_parsed_metadata.json"
SECTION_TABLE = "section_table.json"
LOAD_IMAGE_MAP = "load_image_map.json"
REGION_HASHES = "region_hashes.json"
BSS_PROOF = "bss_proof.json"
MALFORMED_RESULTS = "malformed_fixture_results.json"
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


def independent_facts(data: bytes) -> dict[str, Any]:
    """Raw stdlib-only view of the ELF tables, independent of the loader."""
    (
        e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags,
        e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx,
    ) = struct.unpack_from("<HHIIIIIHHHHHH", data, 0x10)
    shstr_header = e_shoff + e_shstrndx * e_shentsize
    shstr_offset, shstr_size = struct.unpack_from("<II", data, shstr_header + 16)
    names = data[shstr_offset:shstr_offset + shstr_size]

    def name_at(offset: int) -> str:
        end = names.index(b"\x00", offset)
        return names[offset:end].decode("ascii")

    sections: list[dict[str, Any]] = []
    for index in range(e_shnum):
        values = struct.unpack_from("<IIIIIIIIII", data, e_shoff + index * e_shentsize)
        sections.append({
            "index": index,
            "name": name_at(values[0]) if values[0] < len(names) else "",
            "type": values[1],
            "flags": values[2],
            "addr": values[3],
            "offset": values[4],
            "size": values[5],
            "link": values[6],
            "info": values[7],
            "addralign": values[8],
            "entsize": values[9],
        })
    program_headers: list[dict[str, Any]] = []
    for index in range(e_phnum):
        values = struct.unpack_from("<IIIIIIII", data, e_phoff + index * e_phentsize)
        program_headers.append({
            "index": index,
            "type": values[0],
            "offset": values[1],
            "vaddr": values[2],
            "paddr": values[3],
            "filesz": values[4],
            "memsz": values[5],
            "flags": values[6],
            "align": values[7],
        })
    return {
        "ident_class": data[4],
        "ident_encoding": data[5],
        "type": e_type,
        "machine": e_machine,
        "version": e_version,
        "entry": e_entry,
        "phoff": e_phoff,
        "shoff": e_shoff,
        "flags": e_flags,
        "ehsize": e_ehsize,
        "phentsize": e_phentsize,
        "phnum": e_phnum,
        "shentsize": e_shentsize,
        "shnum": e_shnum,
        "shstrndx": e_shstrndx,
        "sections": sections,
        "program_headers": program_headers,
    }


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
# Fixture and P3-01 identity
# ---------------------------------------------------------------------------
def audit_fixture(elf_path: pathlib.Path) -> bytes:
    check("fixture:exists", elf_path.is_file())
    data = elf_path.read_bytes()
    check("fixture:sha256", sha256_bytes(data) == ELF_SHA256)
    check("fixture:size", len(data) == ELF_SIZE)
    check("fixture:p3-01-evidence-exists", P3_01_EVIDENCE.is_file())
    FINDINGS["fixture"] = {
        "path": elf_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_bytes(data),
        "size": len(data),
        "p3_01_evidence": P3_01_EVIDENCE.relative_to(ROOT).as_posix(),
        "p3_01_evidence_sha256": sha256_bytes(P3_01_EVIDENCE.read_bytes()),
    }
    return data


# ---------------------------------------------------------------------------
# Ingestion proof
# ---------------------------------------------------------------------------
def build_metadata(ingested, facts: dict[str, Any]) -> dict[str, Any]:
    parsed = ingested.parsed
    symbols = parsed.symbols()
    undefined = [item for item in symbols if not item.defined and item.name]
    return {
        "identification": parsed.identification.describe(),
        "header": {
            "type": parsed.header.e_type,
            "type_name": parsed.header.type_name,
            "machine": parsed.header.e_machine,
            "version": parsed.header.e_version,
            "entry": hexv(parsed.header.e_entry),
            "phoff": parsed.header.e_phoff,
            "shoff": parsed.header.e_shoff,
            "flags": hexv(parsed.header.e_flags),
            "ehsize": parsed.header.e_ehsize,
            "phentsize": parsed.header.e_phentsize,
            "phnum": parsed.header.e_phnum,
            "shentsize": parsed.header.e_shentsize,
            "shnum": parsed.header.e_shnum,
            "shstrndx": parsed.header.e_shstrndx,
        },
        "table_bounds": {
            "file_size": parsed.size,
            "header_size": parsed.header.e_ehsize,
            "program_table_offset": parsed.header.e_phoff,
            "program_table_size": parsed.header.program_table_size,
            "program_table_end": parsed.header.e_phoff + parsed.header.program_table_size,
            "program_table_within_file": (
                parsed.header.e_phoff + parsed.header.program_table_size <= parsed.size),
            "section_table_offset": parsed.header.e_shoff,
            "section_table_size": parsed.header.section_table_size,
            "section_table_end": parsed.header.e_shoff + parsed.header.section_table_size,
            "section_table_within_file": (
                parsed.header.e_shoff + parsed.header.section_table_size <= parsed.size),
        },
        "target_identity": ingested.identity,
        "program_headers": [item.describe() for item in parsed.program_headers],
        "sections": [item.describe() for item in parsed.sections],
        "load_map": [
            {
                "segment_index": item.index,
                "vaddr": hexv(item.p_vaddr),
                "memsz": item.p_memsz,
                "filesz": item.p_filesz,
                "file_offset": item.p_offset,
                "permissions": item.permissions,
                "align": item.p_align,
                "zero_fill_size": item.zero_fill_size,
            }
            for item in parsed.load_segments
        ],
        "counts": {
            "program_headers": len(parsed.program_headers),
            "load_segments": len(parsed.load_segments),
            "sections": len(parsed.sections),
            "allocated_sections": len(parsed.section_placements),
            "file_backed_allocated_sections": sum(
                1 for item in parsed.section_placements if item.kind == "FILE_BACKED"),
            "zero_fill_allocated_sections": sum(
                1 for item in parsed.section_placements if item.kind == "ZERO_FILL"),
            "relocation_sections": parsed.relocation_section_count(),
            "dynamic_sections": parsed.dynamic_section_count(),
            "symbols": len(symbols),
            "undefined_symbols": len(undefined),
        },
        "symbols": [item.describe() for item in symbols],
        "independent_raw_facts": {
            "entry": hexv(facts["entry"]),
            "flags": hexv(facts["flags"]),
            "phoff": facts["phoff"],
            "shoff": facts["shoff"],
            "phnum": facts["phnum"],
            "shnum": facts["shnum"],
        },
    }


def audit_ingestion(data: bytes) -> None:
    ingested = ingest(data, MIPS32_O32)
    parsed = ingested.parsed
    image = ingested.image
    identity = ingested.identity
    facts = independent_facts(data)

    check("identity:class-32", parsed.identification.elf_class == 1)
    check("identity:little-endian", parsed.identification.data_encoding == 1)
    check("identity:ident-version", parsed.identification.ident_version == 1)
    check("identity:machine-em-mips", parsed.header.e_machine == 8)
    check("identity:type-exec", parsed.header.e_type == 2)
    check("identity:flags", parsed.header.e_flags == EXPECTED_FLAGS)
    check("identity:entry", parsed.header.e_entry == EXPECTED_ENTRY)
    check("identity:entry-word-aligned", parsed.header.e_entry % 4 == 0)
    check("identity:target-policy", identity["target"] == MIPS32_O32.name)
    check("identity:target-abi-o32", identity["abi"] == "O32")
    check("identity:target-arch-32", identity["isa"] == "MIPS32 (EF_MIPS_ARCH_32)")
    check("identity:target-non-pic", identity["pic"] is False)
    check("identity:entry-section", identity["entry_section"] == ".text")

    check("tables:program-header-entry-size", parsed.header.e_phentsize == 32)
    check("tables:section-header-entry-size", parsed.header.e_shentsize == 40)
    check("tables:program-table-within-file",
          parsed.header.e_phoff + parsed.header.program_table_size <= parsed.size)
    check("tables:section-table-within-file",
          parsed.header.e_shoff + parsed.header.section_table_size <= parsed.size)
    check("tables:no-relocation-sections", parsed.relocation_section_count() == 0)
    check("tables:no-dynamic-sections", parsed.dynamic_section_count() == 0)
    check("tables:no-dynamic-program-header",
          all(item.p_type != 2 for item in parsed.program_headers))
    check("tables:no-interp-program-header",
          all(item.p_type != 3 for item in parsed.program_headers))
    check("tables:counts",
          len(parsed.program_headers) == 8 and len(parsed.sections) == 12
          and len(parsed.load_segments) == 4)
    check("tables:independent-raw-view",
          facts["entry"] == parsed.header.e_entry
          and facts["flags"] == parsed.header.e_flags
          and facts["phnum"] == parsed.header.e_phnum
          and facts["shnum"] == parsed.header.e_shnum
          and facts["phoff"] == parsed.header.e_phoff
          and facts["shoff"] == parsed.header.e_shoff)
    for wanted, actual in (
        ("e_phentsize", parsed.header.e_phentsize),
        ("e_shentsize", parsed.header.e_shentsize),
        ("e_shstrndx", parsed.header.e_shstrndx),
    ):
        key = wanted[2:]
        check(f"tables:independent-{key}", facts[key] == actual)

    symbols = parsed.symbols()
    undefined = [item for item in symbols if not item.defined and item.name]
    check("symbols:count", len(symbols) == 563)
    check("symbols:undefined-zero", not undefined)
    functions = [item for item in symbols if item.is_function and item.size > 0]
    check("symbols:function-count", len(functions) == 48)
    entry_symbols = [item for item in symbols if item.value == EXPECTED_ENTRY]
    check("symbols:entry-symbol-recorded", bool(entry_symbols))

    raw_sections = {item["name"]: item for item in facts["sections"]}
    for name, size in EXPECTED_SECTIONS.items():
        described = parsed.section(name)
        raw = raw_sections.get(name)
        check(f"section:present:{name}", described is not None and raw is not None)
        check(f"section:size:{name}", described.sh_size == size and raw["size"] == size)
        check(f"section:attributes:{name}",
              described.sh_type == raw["type"]
              and described.sh_flags == raw["flags"]
              and described.sh_addr == raw["addr"]
              and described.sh_offset == raw["offset"]
              and described.sh_addralign == raw["addralign"]
              and described.sh_entsize == raw["entsize"])
    check("section:text-flags",
          parsed.section(".text").sh_flags == 0x6)
    check("section:rodata-flags",
          parsed.section(".rodata").sh_flags == 0x32)
    check("section:data-flags",
          parsed.section(".data").sh_flags == 0x10000003)
    check("section:bss-nobits", parsed.section(".bss").sh_type == 8)
    check("section:bss-flags", parsed.section(".bss").sh_flags == 0x3)
    check("section:bss-address-size",
          parsed.section(".bss").sh_addr == EXPECTED_BSS_VADDR
          and parsed.section(".bss").sh_size == EXPECTED_BSS_SIZE)
    check("section:text-address", parsed.section(".text").sh_addr == EXPECTED_TEXT_ADDRESS)
    names = [item.name for item in parsed.sections]
    check("section:names",
          names == ["", ".text", ".MIPS.abiflags", ".reginfo", ".rodata", ".data",
                    ".bss", ".mdebug.abi32", ".comment", ".symtab", ".shstrtab",
                    ".strtab"])
    check("section:placement-count",
          len(parsed.section_placements) == 6)
    bss_placement = parsed.placement(".bss")
    check("section:bss-zero-fill-placement",
          bss_placement is not None
          and bss_placement.kind == "ZERO_FILL"
          and bss_placement.file_size == 0
          and bss_placement.file_offset == 0)
    data_placement = parsed.placement(".data")
    check("section:data-file-backed-placement",
          data_placement is not None
          and data_placement.kind == "FILE_BACKED"
          and data_placement.file_size == 40
          and data_placement.file_offset == 0x4E00)
    rodata_placement = parsed.placement(".rodata")
    check("section:rodata-readonly-placement",
          rodata_placement is not None
          and rodata_placement.kind == "FILE_BACKED"
          and rodata_placement.read and not rodata_placement.write
          and not rodata_placement.execute)

    for index, expected in enumerate(EXPECTED_LOAD_REGIONS):
        region = image.regions[index]
        check(f"region:identity:{index}",
              region.vaddr == expected["vaddr"]
              and region.filesz == expected["filesz"]
              and region.memsz == expected["memsz"]
              and region.permissions == expected["permissions"]
              and region.zero_fill_size == expected["zero_fill_size"])
        check(f"region:file-slice:{index}",
              region.file_bytes == data[region.file_offset:region.file_offset + region.filesz])
        check(f"region:content:{index}",
              region.initial_bytes
              == region.file_bytes + b"\x00" * region.zero_fill_size)
    check("region:executable-count", len(parsed.executable_regions()) == 1)
    check("region:text-executable",
          image.regions[1].execute and not image.regions[1].write)
    check("region:rodata-readonly",
          image.regions[2].read and not image.regions[2].write
          and not image.regions[2].execute)
    check("region:data-writable", image.regions[3].write)
    check("region:independent-load-map",
          [(item.p_vaddr, item.p_filesz, item.p_memsz)
           for item in parsed.load_segments]
          == [(item["vaddr"], item["filesz"], item["memsz"]) for item in facts["program_headers"]
              if item["type"] == 1])

    text_file = data[0x1000:0x1000 + EXPECTED_SECTIONS[".text"]]
    rodata_file = data[0x46B0:0x46B0 + EXPECTED_SECTIONS[".rodata"]]
    data_file = data[0x4E00:0x4E00 + EXPECTED_SECTIONS[".data"]]
    check("reconstruct:text-bytes",
          image.section_bytes(".text") == text_file
          and sha256_bytes(text_file) == sha256_bytes(image.section_bytes(".text")))
    check("reconstruct:rodata-bytes",
          image.section_bytes(".rodata") == rodata_file)
    check("reconstruct:data-bytes",
          image.section_bytes(".data") == data_file)
    check("reconstruct:text-file-offset",
          parsed.section(".text").sh_offset == 0x1000)
    check("reconstruct:rodata-file-offset",
          parsed.section(".rodata").sh_offset == 0x46B0)
    check("reconstruct:data-file-offset",
          parsed.section(".data").sh_offset == 0x4E00)

    check("image:read-header-region", image.read(0x0, 308) == data[0:308])
    check("image:read-first-word",
          image.read_u32(0x1000) == struct.unpack_from("<I", data, 0x1000)[0])
    check("image:read-boundary-span",
          image.read(0x4E20, 0x20) == data[0x4E20:0x4E28] + b"\x00" * 24)
    check("image:bss-all-zero",
          image.read(EXPECTED_BSS_VADDR, EXPECTED_BSS_SIZE) == b"\x00" * EXPECTED_BSS_SIZE)
    check("image:zero-fill-ranges",
          image.zero_fill_ranges() == ((EXPECTED_SEGMENT_TAIL_START, EXPECTED_SEGMENT_TAIL_SIZE),))
    for probe in UNMAPPED_PROBES:
        check(f"image:unmapped:{hexv(probe)}", not image.is_mapped(probe, 4))
    unmapped_rejected = False
    try:
        image.read(0x20000, 4)
    except GuestImageError as exc:
        unmapped_rejected = exc.code == "UNMAPPED_ADDRESS"
    check("image:unmapped-read-rejected", unmapped_rejected)
    overflow_rejected = False
    try:
        image.read(0xFFFFFFF0, 0x20)
    except GuestImageError as exc:
        overflow_rejected = exc.code == "RANGE_OVERFLOW"
    check("image:overflow-read-rejected", overflow_rejected)
    readonly_rejected = False
    try:
        image.write(0x1000, b"\x00\x00\x00\x00")
    except GuestImageError as exc:
        readonly_rejected = exc.code == "READONLY_VIOLATION"
    check("image:readonly-write-rejected", readonly_rejected)
    rodata_write_rejected = False
    try:
        image.write(0x46B0, b"\x00")
    except GuestImageError as exc:
        rodata_write_rejected = exc.code == "READONLY_VIOLATION"
    check("image:rodata-write-rejected", rodata_write_rejected)

    mutable = ingest(data, MIPS32_O32).image
    mutable.write(0x4E00, b"\x9a")
    check("image:writable-write-applied", mutable.read(0x4E00, 1) == b"\x9a")
    mutable.write(EXPECTED_BSS_VADDR, b"\xff" * 16)
    check("image:zero-fill-write-applied",
          mutable.read(EXPECTED_BSS_VADDR, 16) == b"\xff" * 16)
    check("image:pristine-identity-unchanged",
          mutable.regions[3].initial_bytes == data[0x4E00:0x4E00 + 40] + b"\x00" * 18424
          and mutable.regions[3].content_sha256
          == sha256_bytes(mutable.regions[3].initial_bytes))

    p3_01 = json.loads(P3_01_EVIDENCE.read_text(encoding="utf-8"))
    check("p3-01:class", p3_01["class"] == parsed.identification.class_name)
    check("p3-01:endianness", p3_01["endianness"] == parsed.identification.endianness)
    check("p3-01:machine", p3_01["machine"] == "EM_MIPS (0x8)")
    check("p3-01:type", p3_01["type"] == parsed.header.type_name)
    check("p3-01:flags", p3_01["flags"] == hexv(parsed.header.e_flags))
    check("p3-01:entry", p3_01["entry"] == hexv(parsed.header.e_entry))
    check("p3-01:sizes", p3_01["sizes"] == EXPECTED_SECTIONS)
    check("p3-01:sections",
          [(item["name"], int(item["addr"], 16), item["size"], item["type"])
           for item in p3_01["sections"]]
          == [(item.name, item.sh_addr, item.sh_size, item.sh_type)
              for item in parsed.sections])
    check("p3-01:program-headers",
          [(int(item["vaddr"], 16), item["filesz"], item["memsz"], item["flags"])
           for item in p3_01["program_headers"]]
          == [(item.p_vaddr, item.p_filesz, item.p_memsz, item.p_flags)
              for item in parsed.program_headers])
    check("p3-01:symbol-count", p3_01["symbol_count"] == len(symbols))
    check("p3-01:function-symbol-count", p3_01["function_symbol_count"] == len(functions))
    check("p3-01:relocations", p3_01["relocation_count"] == 0)
    check("p3-01:undefined", p3_01["undefined_symbol_count"] == 0)
    check("p3-01:instruction-words",
          p3_01["executable_instruction_count_estimate"]
          == EXPECTED_SECTIONS[".text"] // 4)
    check("p3-01:no-dynamic-section", ".dynamic" not in [item.name for item in parsed.sections])
    check("p3-01:imported-none",
          p3_01["imported_external_requirements"].startswith("none"))

    metadata = build_metadata(ingested, facts)
    image_description = image.describe(sha256_bytes(data), len(data), parsed.header.e_entry)

    section_hashes: dict[str, Any] = {}
    for name in (".text", ".rodata", ".data", ".MIPS.abiflags", ".reginfo"):
        described = parsed.section(name)
        slice_bytes = data[described.sh_offset:described.sh_offset + described.sh_size]
        section_hashes[name] = {
            "size": described.sh_size,
            "file_offset": described.sh_offset,
            "file_slice_sha256": sha256_bytes(slice_bytes),
            "image_sha256": sha256_bytes(image.section_bytes(name)),
            "bytes_equal": image.section_bytes(name) == slice_bytes,
        }
    bss = parsed.section(".bss")
    bss_image = image.section_bytes(".bss")
    section_hashes[".bss"] = {
        "size": bss.sh_size,
        "declared_file_offset": bss.sh_offset,
        "file_backed": False,
        "image_sha256": sha256_bytes(bss_image),
        "zero_verified": bss_image == b"\x00" * bss.sh_size,
        "zeros_sha256": sha256_bytes(b"\x00" * bss.sh_size),
    }

    section_table_evidence = {
        "sections": [item.describe() for item in parsed.sections],
        "placements": [item.describe() for item in parsed.section_placements],
        "independent_raw_sections": facts["sections"],
    }
    load_image_evidence = {
        "load_map": metadata["load_map"],
        "image": image_description,
    }
    region_hash_evidence = {
        "source_sha256": sha256_bytes(data),
        "image_hashes": image_description["hashes"],
        "section_hashes": section_hashes,
        "segments": [region.describe() for region in image.regions],
    }

    declared_bytes = data[bss.sh_offset:bss.sh_offset + 16]
    bss_proof = {
        "section": ".bss",
        "vaddr": hexv(bss.sh_addr),
        "declared_size": bss.sh_size,
        "section_type": bss.sh_type,
        "section_flags": bss.sh_flags,
        "placement_kind": bss_placement.kind,
        "placement_file_size": bss_placement.file_size,
        "image_region_index": image.region_at(bss.sh_addr).index,
        "image_region_vaddr": hexv(image.region_at(bss.sh_addr).vaddr),
        "image_region_filesz": image.region_at(bss.sh_addr).filesz,
        "image_region_memsz": image.region_at(bss.sh_addr).memsz,
        "segment_zero_fill_start": hexv(EXPECTED_SEGMENT_TAIL_START),
        "segment_zero_fill_size": EXPECTED_SEGMENT_TAIL_SIZE,
        "declared_file_range_end": bss.sh_offset + bss.sh_size,
        "file_size": len(data),
        "declared_file_range_exceeds_file": bss.sh_offset + bss.sh_size > len(data),
        "bytes_read_from_file": 0,
        "zero_bytes_verified": bss.sh_size,
        "image_sha256": sha256_bytes(bss_image),
        "zeros_sha256": sha256_bytes(b"\x00" * bss.sh_size),
        "file_bytes_at_declared_offset_sha256": sha256_bytes(declared_bytes),
        "file_bytes_at_declared_offset_all_zero": declared_bytes == b"\x00" * 16,
        "file_bytes_at_declared_offset_sample": declared_bytes.hex(),
    }
    check("bss:declared-in-file-range", bss.sh_offset < len(data))
    check("bss:declared-range-crosses-eof", bss.sh_offset + bss.sh_size > len(data))
    check("bss:declared-bytes-nonzero", declared_bytes != b"\x00" * 16)
    check("bss:image-all-zero", bss_image == b"\x00" * bss.sh_size)
    check("bss:zeros-hash", sha256_bytes(bss_image) == sha256_bytes(b"\x00" * bss.sh_size))
    check("bss:file-size-zero", bss_placement.file_size == 0)
    check("bss:tail-containment",
          bss.sh_addr >= EXPECTED_SEGMENT_TAIL_START
          and bss.sh_addr + bss.sh_size
          == EXPECTED_SEGMENT_TAIL_START + EXPECTED_SEGMENT_TAIL_SIZE)

    ARTIFACTS[ELF_PARSED_METADATA] = evidence_json_bytes(metadata)
    ARTIFACTS[SECTION_TABLE] = evidence_json_bytes(section_table_evidence)
    ARTIFACTS[LOAD_IMAGE_MAP] = evidence_json_bytes(load_image_evidence)
    ARTIFACTS[REGION_HASHES] = evidence_json_bytes(region_hash_evidence)
    ARTIFACTS[BSS_PROOF] = evidence_json_bytes(bss_proof)
    FINDINGS["ingestion"] = {
        "identity": identity,
        "metadata": metadata,
        "image_hashes": image_description["hashes"],
        "image_sha256": image_description["image_sha256"],
        "section_hashes": section_hashes,
        "bss_proof": bss_proof,
        "symbols": {
            "count": len(symbols),
            "functions": len(functions),
            "undefined": len(undefined),
        },
    }


# ---------------------------------------------------------------------------
# Determinism (repeated ingestion)
# ---------------------------------------------------------------------------
def audit_determinism(data: bytes) -> None:
    first = ingest(data, MIPS32_O32)
    second = ingest(bytes(data), MIPS32_O32)
    first_metadata = {
        "header": first.parsed.header,
        "sections": first.parsed.sections,
        "placements": first.parsed.section_placements,
        "load": first.parsed.load_segments,
    }
    second_metadata = {
        "header": second.parsed.header,
        "sections": second.parsed.sections,
        "placements": second.parsed.section_placements,
        "load": second.parsed.load_segments,
    }
    check("determinism:metadata-structures", first_metadata == second_metadata)
    first_image = first.image.describe(
        sha256_bytes(data), len(data), first.parsed.header.e_entry)
    second_image = second.image.describe(
        sha256_bytes(data), len(data), second.parsed.header.e_entry)
    check("determinism:image-serialization",
          canonical_json_bytes(first_image) == canonical_json_bytes(second_image))
    check("determinism:image-identity",
          first_image["image_sha256"] == second_image["image_sha256"])
    check("determinism:metadata-artifact-stable",
          evidence_json_bytes(build_metadata(first, independent_facts(data)))
          == ARTIFACTS[ELF_PARSED_METADATA])

    hashed = {
        name: sha256_bytes(payload)
        for name, payload in sorted(ARTIFACTS.items())
    }
    record = {
        "source_sha256": sha256_bytes(data),
        "artifact_sha256": hashed,
        "image_sha256": first_image["image_sha256"],
        "repeated_ingestion_identical": True,
    }
    ARTIFACTS[DETERMINISM] = evidence_json_bytes(record)
    FINDINGS["determinism"] = record


# ---------------------------------------------------------------------------
# Synthetic fixture: structural baseline and mutations
# ---------------------------------------------------------------------------
FIXTURE_SHOFF = 0xB4
FIXTURE_SHNUM = 5
FIXTURE_TEXT_OFF = 0x80
FIXTURE_DATA_OFF = 0x90
FIXTURE_SHSTR_OFF = 0x98
FIXTURE_SHSTR_SIZE = 28
FIXTURE_ENTRY = 0x1000
FIXTURE_IDENT = b"\x7fELF\x01\x01\x01\x00" + b"\x00" * 8


def build_synthetic_elf() -> bytes:
    text = struct.pack("<4I", 0x03E00008, 0x00000000, 0x24020001, 0x00000000)
    data = b"\x11\x22\x33\x44\x55\x66\x77\x88"
    names = b"\x00.text\x00.data\x00.bss\x00.shstrtab\x00"
    blob = bytearray()
    blob += FIXTURE_IDENT
    blob += struct.pack(
        "<HHIIIIIHHHHHH", 2, 8, 1, FIXTURE_ENTRY, 0x34, FIXTURE_SHOFF, 0x50001001,
        52, 32, 2, 40, FIXTURE_SHNUM, 4)
    blob += struct.pack("<IIIIIIII", 1, FIXTURE_TEXT_OFF, 0x1000, 0x1000, 16, 16, 5, 4)
    blob += struct.pack("<IIIIIIII", 1, FIXTURE_DATA_OFF, 0x2000, 0x2000, 8, 24, 6, 4)
    blob += b"\x00" * (FIXTURE_TEXT_OFF - len(blob))
    blob += text
    blob += data
    blob += names
    if len(blob) != FIXTURE_SHOFF:
        raise AssertionError(f"synthetic fixture layout drift: {len(blob)}")
    headers = (
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        (1, 1, 0x6, 0x1000, FIXTURE_TEXT_OFF, 16, 0, 0, 4, 0),
        (7, 1, 0x3, 0x2000, FIXTURE_DATA_OFF, 8, 0, 0, 4, 0),
        (13, 8, 0x3, 0x2008, FIXTURE_SHSTR_OFF, 16, 0, 0, 4, 0),
        (18, 3, 0x0, 0x0, FIXTURE_SHSTR_OFF, FIXTURE_SHSTR_SIZE, 0, 0, 1, 0),
    )
    for entry in headers:
        blob += struct.pack("<IIIIIIIIII", *entry)
    return bytes(blob)


def sh_field(index: int, field: int) -> int:
    return FIXTURE_SHOFF + index * 40 + field


def ph_field(index: int, field: int) -> int:
    return 0x34 + index * 32 + field


def patch_u8(data: bytes, offset: int, value: int) -> bytes:
    blob = bytearray(data)
    blob[offset] = value
    return bytes(blob)


def patch_u16(data: bytes, offset: int, value: int) -> bytes:
    blob = bytearray(data)
    struct.pack_into("<H", blob, offset, value)
    return bytes(blob)


def patch_u32(data: bytes, offset: int, value: int) -> bytes:
    blob = bytearray(data)
    struct.pack_into("<I", blob, offset, value)
    return bytes(blob)


def _expected_negative_cases(base: bytes) -> list[tuple[str, str, bytes]]:
    return [
        ("truncated-magic", "INVALID_MAGIC", base[:4]),
        ("truncated-elf-header", "TRUNCATED_ELF_HEADER", base[:40]),
        ("wrong-class", "UNSUPPORTED_CLASS", patch_u8(base, 4, 2)),
        ("wrong-endianness", "UNSUPPORTED_ENDIANNESS", patch_u8(base, 5, 2)),
        ("wrong-ident-version", "UNSUPPORTED_IDENT_VERSION", patch_u8(base, 6, 0)),
        ("wrong-machine", "UNSUPPORTED_MACHINE", patch_u16(base, 0x12, 243)),
        ("unsupported-type", "UNSUPPORTED_TYPE", patch_u16(base, 0x10, 3)),
        ("unsupported-header-size", "UNSUPPORTED_HEADER_SIZE", patch_u16(base, 0x28, 64)),
        ("unsupported-version", "UNSUPPORTED_VERSION", patch_u32(base, 0x14, 0)),
        ("unsupported-abi", "UNSUPPORTED_ABI", patch_u32(base, 0x24, 0x50000001)),
        ("unsupported-pic", "UNSUPPORTED_PIC", patch_u32(base, 0x24, 0x50001003)),
        ("invalid-phentsize", "INVALID_PROGRAM_TABLE_SIZE", patch_u16(base, 0x2A, 16)),
        ("invalid-shentsize", "INVALID_SECTION_TABLE_SIZE", patch_u16(base, 0x2E, 20)),
        ("program-table-out-of-bounds", "PROGRAM_TABLE_OUT_OF_BOUNDS",
         patch_u32(base, 0x1C, len(base) - 8)),
        ("program-table-overflow", "PROGRAM_TABLE_OVERFLOW",
         patch_u32(base, 0x1C, 0xFFFFFFF0)),
        ("section-table-out-of-bounds", "SECTION_TABLE_OUT_OF_BOUNDS",
         patch_u32(base, 0x20, len(base) - 8)),
        ("section-table-overflow", "SECTION_TABLE_OVERFLOW",
         patch_u32(base, 0x20, 0xFFFFFFF0)),
        ("missing-section-table", "MISSING_SECTION_TABLE", patch_u16(base, 0x30, 0)),
        ("malformed-section-zero", "MALFORMED_SECTION_ZERO",
         patch_u32(base, sh_field(0, 4), 1)),
        ("malformed-shstrndx", "MALFORMED_SECTION_NAME_TABLE",
         patch_u16(base, 0x32, 99)),
        ("malformed-shstrndx-zero", "MALFORMED_SECTION_NAME_TABLE",
         patch_u16(base, 0x32, 0)),
        ("malformed-section-name-offset", "MALFORMED_SECTION_NAME_TABLE",
         patch_u32(base, sh_field(1, 0), 0xFFFF)),
        ("malformed-section-name-unterminated", "MALFORMED_SECTION_NAME_TABLE",
         patch_u8(base, FIXTURE_SHSTR_OFF + FIXTURE_SHSTR_SIZE - 1, ord("X"))),
        ("section-content-out-of-bounds", "SECTION_OUT_OF_BOUNDS",
         patch_u32(base, sh_field(1, 16), len(base) + 0x100)),
        ("section-range-overflow", "SECTION_RANGE_OVERFLOW",
         patch_u32(patch_u32(base, sh_field(1, 16), 0xFFFFFFF0),
                   sh_field(1, 20), 0x20)),
        ("segment-file-range-out-of-bounds", "SEGMENT_FILE_RANGE_OUT_OF_BOUNDS",
         patch_u32(base, ph_field(0, 4), len(base) + 0x100)),
        ("segment-memory-overflow", "SEGMENT_MEMORY_OVERFLOW",
         patch_u32(base, ph_field(1, 8), 0xFFFFFFF0)),
        ("filesz-greater-than-memsz", "INVALID_SEGMENT_SIZE",
         patch_u32(base, ph_field(1, 16), 0x20)),
        ("nobits-exec-trap", "NOBITS_EXEC_TRAP",
         patch_u32(base, ph_field(0, 20), 0x20)),
        ("impossible-segment-alignment", "IMPOSSIBLE_SEGMENT_ALIGNMENT",
         patch_u32(base, ph_field(0, 28), 3)),
        ("incongruent-segment-alignment", "IMPOSSIBLE_SEGMENT_ALIGNMENT",
         patch_u32(base, ph_field(1, 28), 0x1000)),
        ("impossible-section-alignment", "IMPOSSIBLE_SECTION_ALIGNMENT",
         patch_u32(base, sh_field(1, 32), 3)),
        ("no-loadable-segments", "NO_LOADABLE_SEGMENTS", patch_u16(base, 0x2C, 0)),
        ("overlapping-load-ranges", "OVERLAPPING_LOAD_RANGES",
         patch_u32(base, ph_field(1, 8), 0x1008)),
        ("overlapping-load-file-ranges", "OVERLAPPING_LOAD_FILE_RANGES",
         patch_u32(base, ph_field(1, 4), 0x88)),
        ("overlapping-alloc-sections", "OVERLAPPING_ALLOC_SECTIONS",
         patch_u32(patch_u32(base, sh_field(2, 12), 0x1008), sh_field(2, 16), 0x88)),
        ("section-outside-load", "SECTION_LOAD_MISMATCH",
         patch_u32(base, sh_field(1, 12), 0x3000)),
        ("section-file-mismatch", "SECTION_LOAD_MISMATCH",
         patch_u32(base, sh_field(1, 16), 0x84)),
        ("nobits-outside-zero-fill", "NOBITS_OUTSIDE_ZERO_FILL",
         patch_u32(base, sh_field(3, 12), 0x2004)),
        ("unsupported-dynamic-section", "UNSUPPORTED_DYNAMIC",
         patch_u32(base, sh_field(1, 4), 6)),
        ("unsupported-dynamic-program-header", "UNSUPPORTED_DYNAMIC",
         patch_u32(base, ph_field(0, 0), 2)),
        ("unsupported-relocation-rel", "UNSUPPORTED_RELOCATION",
         patch_u32(base, sh_field(1, 4), 9)),
        ("unsupported-relocation-rela", "UNSUPPORTED_RELOCATION",
         patch_u32(base, sh_field(1, 4), 4)),
        ("unsupported-interp", "UNSUPPORTED_INTERP",
         patch_u32(base, ph_field(0, 0), 3)),
        ("missing-executable-section", "MISSING_EXECUTABLE_SECTION",
         patch_u32(base, sh_field(1, 8), 0x2)),
        ("entry-outside-executable", "ENTRY_OUTSIDE_EXECUTABLE",
         patch_u32(base, 0x18, 0x2000)),
        ("entry-misaligned", "ENTRY_MISALIGNED", patch_u32(base, 0x18, 0x1002)),
    ]


def audit_synthetic_fixtures() -> None:
    base = build_synthetic_elf()
    baseline = ingest(base, MIPS32_O32)
    check("synthetic:baseline-ingested", baseline.parsed.header.e_entry == FIXTURE_ENTRY)
    check("synthetic:baseline-regions", len(baseline.image.regions) == 2)
    check("synthetic:baseline-text",
          baseline.image.section_bytes(".text") == base[FIXTURE_TEXT_OFF:FIXTURE_TEXT_OFF + 16])
    check("synthetic:baseline-data",
          baseline.image.section_bytes(".data")
          == base[FIXTURE_DATA_OFF:FIXTURE_DATA_OFF + 8])
    check("synthetic:baseline-bss-zero",
          baseline.image.section_bytes(".bss") == b"\x00" * 16)
    check("synthetic:baseline-bss-kind",
          baseline.parsed.placement(".bss").kind == "ZERO_FILL")
    check("synthetic:baseline-first-word",
          baseline.image.read_u32(0x1000) == 0x03E00008)

    nobits_in_text = patch_u32(base, sh_field(3, 16), FIXTURE_TEXT_OFF)
    nobits = ingest(nobits_in_text, MIPS32_O32)
    check("synthetic:nobits-declared-inside-text-is-zero",
          nobits.image.section_bytes(".bss") == b"\x00" * 16
          and nobits.parsed.placement(".bss").file_size == 0)

    nobits_beyond_eof = patch_u32(base, sh_field(3, 16), 0xFFFFFF00)
    beyond = ingest(nobits_beyond_eof, MIPS32_O32)
    check("synthetic:nobits-declared-beyond-eof-is-zero",
          beyond.image.section_bytes(".bss") == b"\x00" * 16)

    cases = _expected_negative_cases(base)
    recorded: list[dict[str, Any]] = []
    mismatched: list[str] = []
    for name, expected, mutated in cases:
        actual = "NONE"
        detail = ""
        try:
            ingest(mutated, MIPS32_O32)
        except ElfIngestError as exc:
            actual = exc.code
            detail = exc.detail
        except Exception as exc:  # noqa: BLE001 - classification must be typed
            actual = f"UNEXPECTED_{type(exc).__name__}"
            detail = str(exc)
        recorded.append({
            "fixture": name,
            "expected_code": expected,
            "actual_code": actual,
            "detail": detail,
            "status": "PASS" if actual == expected else "FAIL",
        })
        if actual != expected:
            mismatched.append(f"{name}: expected={expected} actual={actual} detail={detail}")
    for item in recorded:
        check(f"synthetic:negative:{item['fixture']}", item["status"] == "PASS")
    if mismatched:
        raise AssertionError("; ".join(mismatched))

    positive = [
        {
            "fixture": "baseline",
            "status": "INGESTED",
            "image_sha256": baseline.image.describe(
                sha256_bytes(base), len(base),
                baseline.parsed.header.e_entry)["image_sha256"],
        },
        {"fixture": "nobits-declared-inside-text", "status": "INGESTED"},
        {"fixture": "nobits-declared-beyond-eof", "status": "INGESTED"},
    ]
    ARTIFACTS[MALFORMED_RESULTS] = evidence_json_bytes({
        "baseline_sha256": sha256_bytes(base),
        "baseline_size": len(base),
        "negative_cases": recorded,
        "negative_cases_passed": sum(1 for item in recorded if item["status"] == "PASS"),
        "positive_cases": positive,
    })
    FINDINGS["synthetic_fixtures"] = {
        "baseline_sha256": sha256_bytes(base),
        "negative_cases": len(recorded),
        "positive_cases": len(positive),
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
    parser = argparse.ArgumentParser(description="P3-02 CoreMark ELF ingestion gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-02")
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

    print("=== P3-02 CoreMark ELF Ingestion Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    evidence_files: dict[str, str] = {}
    try:
        section("source_integrity", audit_source_integrity)
        print("\n--- fixture ---", flush=True)
        data = audit_fixture(elf_path)
        section("ingestion", audit_ingestion, data)
        section("determinism", audit_determinism, data)
        section("synthetic_fixtures", audit_synthetic_fixtures)
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
