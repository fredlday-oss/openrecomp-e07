#!/usr/bin/env python3
"""OpenRecomp Phase-4 guest memory/runtime model gate (P4-02).

Proves the explicit guest memory model in
``.openrecomp-phase4/src/p4_guest_memory_v1.py``:

* regions with declared kinds (code/rodata/data/bss/stack/heap) and explicit
  read/write/execute permissions, validated non-overlap, bounds, W^X and
  zero-fill semantics;
* byte-addressed access with widths 8/16/32/64, explicit little/big
  endianness and a declared alignment policy (byte-addressed by default,
  deterministic alignment faults under require-natural);
* deterministic fail-closed faults (unmapped, permission, alignment, width,
  endianness, overflow) with a total mapping to the P2-08/P4-01 ABI failure
  codes;
* the frozen Phase-3 image adapter: the P3-07 emitted ``g_image`` window
  (sha256-pinned) and the emitted region table parse exactly, and the model's
  permissioned regions agree with the emitted table;
* deterministic state documents and fingerprints.

It emits::

    OPENRECOMP_P4_02=PASS
    OPENRECOMP_PHASE4_GUEST_MEMORY_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_guest_memory_v1.py
    python tools/test_phase4_guest_memory_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-02
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(ROOT / ".openrecomp-phase4" / "src")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import p4_guest_memory_v1 as gm  # noqa: E402
import p4_runtime_abi_v1 as abi  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402
from openrecomp.program_model import canonical_json  # noqa: E402

STAGE = "P4-02"
STAGE_MARKER = "OPENRECOMP_P4_02"
FEATURE_MARKER = "OPENRECOMP_PHASE4_GUEST_MEMORY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

SOURCE_SUMS = "SOURCE_SHA256SUMS.txt"
SOURCE_SUMS_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
SOURCE_SUMS_ENTRIES = 134
P3_SUMS = ".openrecomp-phase3/SOURCE_SHA256SUMS.txt"
P3_SUMS_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_SUMS_ENTRIES = 24
P4_SUMS = ".openrecomp-phase4/SOURCE_SHA256SUMS.txt"

PROGRAM_PATH = ".openrecomp-phase3/evidence/P3-07/coremark_program.c"
PROGRAM_SHA256 = "5199e2f0a11974847966bd7ea6b855e0147c6e762d002ede3f14bc3ee8d9649a"
IMAGE_SHA256 = "3eecfc957c4ed147544d2aa98c6e4f4d7aac41957e531cdfe01c2555ff0a91ae"
EXPECTED_EMITTED_REGIONS = (
    (0x0, 0x134, gm.FROZEN_REGION_READABLE),
    (0x1000, 0x467C, gm.FROZEN_REGION_READABLE),
    (0x4680, 0x4DF8, gm.FROZEN_REGION_READABLE),
    (0x4E00, 0x9620, gm.FROZEN_REGION_READABLE | gm.FROZEN_REGION_WRITABLE),
)
EXPECTED_MODEL_REGIONS = (
    ("elf_image_headers", 0x0, 0x134, "rodata"),
    ("text", 0x1000, 0x467C, "code"),
    ("rodata", 0x4680, 0x4DF8, "rodata"),
    ("data", 0x4E00, 0x4E28, "data"),
    ("bss_zero_fill", 0x4E28, 0x9620, "bss"),
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def expect_fail(label: str, thunk, error_type=gm.GuestMemoryError) -> None:
    try:
        thunk()
    except error_type:
        check(f"reject:{label}", True)
        return
    except Exception as exc:  # noqa: BLE001 - fail closed
        raise AssertionError(
            f"{label}: raised {type(exc).__name__} instead of {error_type.__name__}") from exc
    raise AssertionError(f"{label}: accepted")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def parse_manifest(path: pathlib.Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in read_text(path).strip().splitlines():
        if not line.strip():
            continue
        match = re.match(r"^([0-9a-f]{64}) \*(.+)$", line)
        if match is None:
            raise AssertionError(f"malformed manifest line: {line[:80]}")
        entries.append((match.group(1), match.group(2)))
    return entries


def synthetic_model(**kwargs) -> gm.GuestMemoryModel:
    regions = (
        gm.region("code", 0x1000, 0x100, gm.RegionKind.CODE, file_data=bytes(range(0x100))),
        gm.region("rodata", 0x2000, 0x100, gm.RegionKind.RODATA, file_data=b"\xaa" * 0x100),
        gm.region("data", 0x3000, 0x100, gm.RegionKind.DATA, file_data=b"\x11\x22\x33\x44"),
        gm.region("bss", 0x4000, 0x100, gm.RegionKind.BSS),
        gm.region("stack", 0x5000, 0x100, gm.RegionKind.STACK),
        gm.region("heap", 0x6000, 0x100, gm.RegionKind.HEAP),
        gm.GuestRegion("blind", 0x7000, 0x10, gm.RegionKind.RODATA,
                       readable=False, writable=False, executable=False, file_data=b""),
    )
    return gm.GuestMemoryModel(regions, **kwargs)


def fault_kind(result: gm.GuestAccess) -> str | None:
    return None if result.fault is None else result.fault.kind.value


# ---------------------------------------------------------------------------
# Source integrity
# ---------------------------------------------------------------------------
def audit_source_integrity() -> None:
    check("source:root-manifest", sha256_file(ROOT / SOURCE_SUMS) == SOURCE_SUMS_SHA256)
    root_entries = parse_manifest(ROOT / SOURCE_SUMS)
    check("source:root-manifest-entries", len(root_entries) == SOURCE_SUMS_ENTRIES)
    check("source:root-manifest-verified",
          all((ROOT / rel).is_file() and sha256_file(ROOT / rel) == digest
              for digest, rel in root_entries))
    check("source:phase3-manifest", sha256_file(ROOT / P3_SUMS) == P3_SUMS_SHA256)
    phase3_entries = parse_manifest(ROOT / P3_SUMS)
    check("source:phase3-manifest-entries", len(phase3_entries) == P3_SUMS_ENTRIES)
    phase4_entries = parse_manifest(ROOT / P4_SUMS)
    bad = [rel for digest, rel in phase4_entries
           if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
    check("source:phase4-manifest-verified", phase4_entries and not bad)
    FINDINGS["source_integrity"] = {
        "root_entries": len(root_entries),
        "phase3_entries": len(phase3_entries),
        "phase4_entries": len(phase4_entries),
    }


# ---------------------------------------------------------------------------
# Region structure
# ---------------------------------------------------------------------------
def audit_region_structure() -> None:
    code = gm.region("code", 0, 16, gm.RegionKind.CODE)
    check("region:code-permissions",
          code.readable and not code.writable and code.executable)
    rodata = gm.region("ro", 0, 16, gm.RegionKind.RODATA)
    check("region:rodata-permissions",
          rodata.readable and not rodata.writable and not rodata.executable)
    data = gm.region("d", 0, 16, gm.RegionKind.DATA)
    check("region:data-permissions", data.readable and data.writable and not data.executable)
    bss = gm.region("b", 0, 16, gm.RegionKind.BSS)
    check("region:bss-permissions", bss.readable and bss.writable and not bss.executable)
    stack = gm.region("s", 0, 16, gm.RegionKind.STACK)
    heap = gm.region("h", 0, 16, gm.RegionKind.HEAP)
    check("region:stack-heap-permissions",
          stack.readable and stack.writable and heap.readable and heap.writable)
    check("region:kind-value",
          gm.RegionKind("code") is gm.RegionKind.CODE and len(gm.RegionKind) == 6)

    expect_fail("region-zero-size", lambda: gm.region("z", 0, 0, gm.RegionKind.DATA))
    expect_fail("region-address-wrap",
                lambda: gm.region("w", gm.MAX_ADDRESS, 2, gm.RegionKind.DATA))
    expect_fail("region-file-data-too-large",
                lambda: gm.region("f", 0, 4, gm.RegionKind.DATA, file_data=b"12345"))
    expect_fail("region-bss-file-data",
                lambda: gm.region("b", 0, 4, gm.RegionKind.BSS, file_data=b"1"))
    expect_fail("region-stack-file-data",
                lambda: gm.region("s", 0, 4, gm.RegionKind.STACK, file_data=b"1"))
    expect_fail("region-w-x", lambda: gm.GuestRegion(
        "wx", 0, 16, gm.RegionKind.DATA, readable=True, writable=True,
        executable=True, file_data=b""))
    expect_fail("region-code-not-executable", lambda: gm.GuestRegion(
        "c", 0, 16, gm.RegionKind.CODE, readable=True, writable=False,
        executable=False, file_data=b""))
    expect_fail("model-empty", lambda: gm.GuestMemoryModel(()))
    expect_fail("model-duplicate-name",
                lambda: gm.GuestMemoryModel((
                    gm.region("a", 0, 16, gm.RegionKind.DATA),
                    gm.region("a", 16, 16, gm.RegionKind.DATA))))
    expect_fail("model-overlap",
                lambda: gm.GuestMemoryModel((
                    gm.region("a", 0, 16, gm.RegionKind.DATA),
                    gm.region("b", 8, 16, gm.RegionKind.DATA))))
    expect_fail("model-bad-endianness",
                lambda: gm.GuestMemoryModel((gm.region("a", 0, 16, gm.RegionKind.DATA),),
                                            endianness="middle"))
    expect_fail("model-bad-alignment",
                lambda: gm.GuestMemoryModel((gm.region("a", 0, 16, gm.RegionKind.DATA),),
                                            alignment="strict"))
    check("model-adjacent-regions-allowed",
          gm.GuestMemoryModel((
              gm.region("a", 0, 16, gm.RegionKind.DATA),
              gm.region("b", 16, 16, gm.RegionKind.DATA))).region_at(16).name == "b")
    FINDINGS["region_structure"] = {
        "kinds": [kind.value for kind in gm.RegionKind],
        "alignment_policies": list(gm.ALIGNMENT_POLICIES),
    }


# ---------------------------------------------------------------------------
# Access semantics
# ---------------------------------------------------------------------------
def audit_access_semantics() -> None:
    model = synthetic_model()
    check("access:read-8", model.read(0x2000, 8) == 0xAA)
    check("access:read-16", model.read(0x2000, 16) == 0xAAAA)
    check("access:read-32", model.read(0x2000, 32) == 0xAAAAAAAA)
    check("access:read-64", model.read(0x2000, 64) == 0xAAAAAAAAAAAAAAAA)
    check("access:big-endian-override", model.read(0x2000, 16, endianness="big") == 0xAAAA)
    check("access:data-little-endian", model.read(0x3000, 32) == 0x44332211)
    check("access:data-big-endian", model.read(0x3000, 32, endianness="big") == 0x11223344)
    check("access:unaligned-allowed", model.read(0x3001, 16) == 0x3322)
    check("access:fetch-code", model.fetch(0x1000, 32)
          == int.from_bytes(bytes(range(4)), "little"))
    check("access:fetch-default-width", model.fetch(0x1004) > 0)

    check("access:write-mask", model.try_write(0x3000, 0x1FF, 8).ok
          and model.read(0x3000, 8) == 0xFF)
    check("access:write-bss", model.try_write(0x4000, 0x1234, 16).ok
          and model.read(0x4000, 16) == 0x1234)
    check("access:write-stack", model.try_write(0x5000, 0x55, 8).ok)
    check("access:write-heap", model.try_write(0x6000, 0x66, 8).ok)
    check("access:read-after-write", model.read(0x5000, 8) == 0x55)
    model.write_bytes(0x3004, b"\x01\x02\x03")
    check("access:bytes-roundtrip", model.read_bytes(0x3004, 3) == b"\x01\x02\x03")
    check("access:bytes-zero-length", model.read_bytes(0x3000, 0) == b"")
    check("access:bss-starts-zero",
          all(synthetic_model().read(0x4000 + offset, 8) == 0 for offset in range(0, 16)))

    check("fault:unmapped", fault_kind(model.try_read(0x8000, 8)) == "UNMAPPED")
    check("fault:gap-between-regions", fault_kind(model.try_read(0x1F00, 8)) == "UNMAPPED")
    check("fault:unmapped-write", fault_kind(model.try_write(0x8000, 1, 8)) == "UNMAPPED")
    check("fault:write-code", fault_kind(model.try_write(0x1000, 1, 8)) == "PERMISSION")
    check("fault:write-rodata", fault_kind(model.try_write(0x2000, 1, 8)) == "PERMISSION")
    check("fault:read-blind", fault_kind(model.try_read(0x7000, 8)) == "PERMISSION")
    check("fault:write-blind", fault_kind(model.try_write(0x7000, 1, 8)) == "PERMISSION")
    try:
        model.fetch(0x2000, 32)
        fetch_kind = None
    except gm.GuestMemoryError as exc:
        fetch_kind = exc.fault.kind.value
    check("fault:fetch-rodata", fetch_kind == "PERMISSION")
    check("fault:bad-width", fault_kind(model.try_read(0x2000, 24)) == "WIDTH")
    check("fault:bad-width-zero", fault_kind(model.try_read(0x2000, 0)) == "WIDTH")
    check("fault:bad-endianness", fault_kind(model.try_read(0x2000, 8, endianness="middle"))
          == "ENDIANNESS")
    check("fault:negative-address", fault_kind(model.try_read(-1, 8)) == "UNMAPPED")
    check("fault:bool-address", fault_kind(model.try_read(True, 8)) == "UNMAPPED")
    check("fault:address-overflow", fault_kind(model.try_read(gm.MAX_ADDRESS, 16)) == "OVERFLOW")
    check("fault:address-beyond-space", fault_kind(model.try_read(1 << 64, 8)) == "OVERFLOW")
    check("fault:cross-region-end",
          fault_kind(model.try_read(0x1FFF, 16)) in ("UNMAPPED", "PERMISSION"))

    strict = synthetic_model(alignment="require-natural")
    check("align:natural-ok", strict.try_read(0x3000, 32).ok)
    check("align:fault", fault_kind(strict.try_read(0x3001, 16)) == "ALIGNMENT")
    check("align:fault-32", fault_kind(strict.try_read(0x3002, 32)) == "ALIGNMENT")
    check("align:byte-never-faults", strict.try_read(0x3001, 8).ok)
    check("align:write-fault", fault_kind(strict.try_write(0x4001, 1, 16)) == "ALIGNMENT")

    check("state:region-at", model.region_at(0x1000).name == "code"
          and model.region_at(0x1F00) is None)
    check("state:snapshot-deterministic", model.snapshot() == model.snapshot())
    check("state:snapshot-copy", model.snapshot()["data"] is not model.snapshot()["data"])
    first = model.fingerprint()
    check("state:fingerprint-stable", model.fingerprint() == first)
    model.write(0x3000, 0x99, 8)
    check("state:fingerprint-sensitive", model.fingerprint() != first)
    document = model.to_document()
    check("state:document-regions", [entry["name"] for entry in document["regions"]]
          == ["code", "rodata", "data", "bss", "stack", "heap", "blind"])
    check("state:document-roundtrip",
          json.loads(canonical_json(document)) == document)
    check("state:document-no-host-path",
          not any(token in canonical_json(document) for token in ("C:\\", "D:\\", "/home/")))
    FINDINGS["access_semantics"] = {
        "regions": len(model.regions),
        "fingerprint": first,
    }


# ---------------------------------------------------------------------------
# ABI integration
# ---------------------------------------------------------------------------
def audit_abi_integration() -> None:
    contract = abi.build_contract()
    check("abi:fault-map-total", set(gm.ABI_FAILURE_BY_FAULT) == set(gm.FaultKind))
    check("abi:fault-map-codes-valid",
          all(code in contract.failure_codes for code in gm.ABI_FAILURE_BY_FAULT.values()))
    check("abi:fault-map-codes-p2-08",
          all(code in rt.RUNTIME_FAILURE_CODES for code in gm.ABI_FAILURE_BY_FAULT.values()))

    model = synthetic_model()
    service = gm.AbiMemoryService(model, widths=(8, 16, 32))
    status, value = service.read(0x3000, 32)
    check("abi:read-ok", status == 0 and value == 0x44332211)
    check("abi:read-width-64-rejected", service.read(0x3000, 64)[0] == 2)
    check("abi:read-permission", service.read(0x7000, 8)[0] == 1)
    check("abi:read-unmapped", service.read(0x8000, 8)[0] == 1)
    check("abi:write-ok", service.write(0x3000, 0x1234, 16) == 0)
    check("abi:write-code", service.write(0x1000, 0, 8) == 1)
    check("abi:fetch-code", service.fetch(0x1000, 32) == (0, int.from_bytes(bytes(range(4)), "little")))
    check("abi:fetch-non-code", service.fetch(0x3000, 32)[0] == 1)
    expect_fail("abi-unknown-failure-code", lambda: gm.AbiMemoryService(
        model, failure_codes=("TRAP",)))
    expect_fail("abi-bad-width-subset", lambda: gm.AbiMemoryService(model, widths=(12,)))

    flat = rt.RuntimeMemory(0x100, endianness="little",
                            segments=(rt.RuntimeMemorySegment(0, "init", bytes(range(0x100))),))
    differential = True
    for address in range(0, 0x100 - 8, 7):
        for width_bits in (8, 16, 32, 64):
            if gm.GuestMemoryModel((gm.region("flat", 0, 0x100, gm.RegionKind.DATA,
                                              file_data=bytes(range(0x100))),),).read(
                                                  address, width_bits) != flat.read(
                                                      address, width_bits):
                differential = False
    check("abi:differential-flat-memory", differential)
    FINDINGS["abi_integration"] = {
        "mapping": {kind.value: code for kind, code in gm.ABI_FAILURE_BY_FAULT.items()},
    }


# ---------------------------------------------------------------------------
# Frozen Phase-3 instance
# ---------------------------------------------------------------------------
def audit_frozen_instance() -> None:
    program = ROOT / PROGRAM_PATH
    check("instance:program-sha256", sha256_file(program) == PROGRAM_SHA256)
    text = read_text(program)
    image = gm.parse_g_image(text)
    check("instance:image-sha256", sha256_bytes(image) == IMAGE_SHA256)
    check("instance:image-window", len(image) == gm.FROZEN_IMAGE_WINDOW)
    check("instance:image-elf-magic", image[:4] == b"\x7fELF")
    emitted = gm.parse_emitted_regions(text)
    check("instance:emitted-regions", emitted == EXPECTED_EMITTED_REGIONS)

    model, built_image = gm.frozen_phase3_memory()
    check("instance:model-image-identical", built_image == image)
    check("instance:model-regions",
          tuple((item.name, item.start, item.end, item.kind.value)
                for item in model.regions)
          == EXPECTED_MODEL_REGIONS)
    coverage: list[tuple[int, int, int]] = []
    for item in model.regions:
        flags = 0
        if item.readable:
            flags |= gm.FROZEN_REGION_READABLE
        if item.writable:
            flags |= gm.FROZEN_REGION_WRITABLE
        coverage.append((item.start, item.end, flags))
    merged: list[tuple[int, int, int]] = []
    for start, end, flags in coverage:
        if merged and merged[-1][1] == start and merged[-1][2] == flags:
            merged[-1] = (merged[-1][0], end, flags)
        else:
            merged.append((start, end, flags))
    check("instance:model-coverage-equals-emitted", tuple(merged) == emitted)
    check("instance:entry-word",
          model.fetch(gm.FROZEN_ENTRY, 32)
          == int.from_bytes(image[gm.FROZEN_ENTRY:gm.FROZEN_ENTRY + 4], "little"))
    check("instance:text-readable", model.read(0x1000, 32) == int.from_bytes(image[0x1000:0x1004], "little"))
    check("instance:rodata-readable", model.read(0x4680, 32) == int.from_bytes(image[0x4680:0x4684], "little"))
    check("instance:data-readable", model.read(0x4E00, 32) == int.from_bytes(image[0x4E00:0x4E04], "little"))
    check("instance:bss-zero",
          all(model.read(0x4E28 + offset, 8) == 0 for offset in range(0, 32)))
    check("instance:bss-zero-at-end", model.read(0x961F, 8) == 0)
    check("instance:guest-stack-in-bss",
          model.region_at(0x5620).kind is gm.RegionKind.BSS
          and model.try_write(0x5620, 0x1234, 32).ok
          and model.read(0x5620, 32) == 0x1234)
    check("instance:write-text-fails-closed",
          fault_kind(model.try_write(0x1000, 0, 8)) == "PERMISSION")
    check("instance:write-rodata-fails-closed",
          fault_kind(model.try_write(0x4680, 0, 8)) == "PERMISSION")
    check("instance:write-headers-fails-closed",
          fault_kind(model.try_write(0x0, 0, 8)) == "PERMISSION")
    check("instance:write-data-allowed", model.try_write(0x4E00, 0xAA, 8).ok)
    check("instance:gap-before-rodata-unmapped",
          fault_kind(model.try_read(0x467C, 8)) == "UNMAPPED")
    check("instance:outside-image-unmapped",
          fault_kind(model.try_read(0x10000, 8)) == "UNMAPPED")
    check("instance:model-endianness", model.endianness == "little"
          and model.alignment == "allow")

    service = gm.AbiMemoryService(model, widths=(8, 16, 32))
    check("instance:abi-entry-fetch",
          service.fetch(gm.FROZEN_ENTRY, 32)[0] == 0)
    check("instance:abi-width-64-rejected", service.read(0x1000, 64)[0] == 2)
    check("instance:abi-write-text-rejected", service.write(0x1000, 0, 32) == 1)

    first, _ = gm.frozen_phase3_memory()
    second, _ = gm.frozen_phase3_memory()
    check("instance:deterministic-fingerprint",
          first.fingerprint() == second.fingerprint())
    check("instance:deterministic-document",
          canonical_json(first.to_document()) == canonical_json(second.to_document()))
    FINDINGS["frozen_instance"] = {
        "image_sha256": IMAGE_SHA256,
        "emitted_regions": [list(row) for row in emitted],
        "model_regions": [list(row) for row in EXPECTED_MODEL_REGIONS],
        "fingerprint": model.fingerprint(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P4-02 guest memory model gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-02")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}

    print("=== P4-02 Guest Memory Model Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("region_structure")
        audit_region_structure()
        banner("access_semantics")
        audit_access_semantics()
        banner("abi_integration")
        audit_abi_integration()
        banner("frozen_instance")
        audit_frozen_instance()
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    status = "FAIL" if failure else "PASS"

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
            "compatibility": f"{COMPAT_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    (EVIDENCE_DIR / "p4_02_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    print("\n=== RESULT ===")
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{TERMINAL_MARKER}=NOT_PROVEN")
        print(f"{COMPAT_MARKER}=NOT_PROVEN")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FEATURE_MARKER}=FAIL")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
