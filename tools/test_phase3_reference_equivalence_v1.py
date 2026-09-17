#!/usr/bin/env python3
"""OpenRecomp Phase-3 independent MIPS32 reference + equivalence gate (P3-09).

P3-09 executes the audited CoreMark ELF with an independently written MIPS32
reference (its own ELF loader, decoder and interpreter) and proves deterministic
observable equivalence against the P3-08 native runtime observable.

The deterministic gate:

* verifies source integrity: the frozen root ``SOURCE_SHA256SUMS.txt`` is
  unchanged and every entry still hashes, and the Phase-3
  ``.openrecomp-phase3/SOURCE_SHA256SUMS.txt`` manifest registers and verifies
  the Phase-3 source/gate files (grown additively to this stage's set);
* loads the audited ELF with the independent loader and proves its flat image
  and region table reproduce the P3-02/P3-07 load image exactly;
* decodes the executable region with the independent decoder and cross-checks
  the per-op histogram against the frozen P3-03/P3-07 decode evidence;
* executes the full deterministic run and compares every observable field
  (exit status, step count, PC, HI/LO, UART stream, FNV-1a 64 state digest,
  failure state) with the P3-08 native observable recorded in its evidence;
* checks CoreMark's published validation CRCs in the reference UART stream;
* executes synthetic minimal ELFs to prove the reference's fail-closed paths
  (divide by zero, taken trap, unaligned indirect target, out-of-image memory
  access, malformed ELF, PC outside the image);
* captures the reference observable, the equivalence record and the final
  reference image digest as evidence.

The official two-run determinism of this gate is also the reference's
determinism proof: two independent process invocations must emit byte-identical
stdout for the same full run.

On success it emits::

    OPENRECOMP_P3_09=PASS
    OPENRECOMP_PHASE3_REFERENCE_EQUIVALENCE_V1=PASS tests=<count>

Any failed invariant fails closed and emits ``OPENRECOMP_P3_09=FAIL``.

Usage:

    python tools/test_phase3_reference_equivalence_v1.py
    python tools/test_phase3_reference_equivalence_v1.py --elf .openrecomp-phase3/build/P3-01/candidate-a/coremark_mips32_O1.elf
"""
from __future__ import annotations

import argparse
import hashlib
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

from p3_elf_image_v1 import evidence_json_bytes, sha256_bytes  # noqa: E402
from p3_reference_mips32_v1 import (  # noqa: E402
    FAIL_DIVIDE_BY_ZERO,
    FAIL_MEMORY_OUT_OF_RANGE,
    FAIL_PC_OUTSIDE,
    FAIL_UNALIGNED_JUMP,
    IMAGE_WINDOW,
    OP_NAMES,
    ReferenceError,
    decode_text,
    load_elf_flat,
    run,
)

EVIDENCE_ROOT = ROOT / ".openrecomp-phase3" / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-09"
P3_02_EVIDENCE = EVIDENCE_ROOT / "P3-02"
P3_07_EVIDENCE = EVIDENCE_ROOT / "P3-07"
P3_08_EVIDENCE = EVIDENCE_ROOT / "P3-08"

STAGE = "P3-09"
STAGE_MARKER = "OPENRECOMP_P3_09"
FEATURE_MARKER = "OPENRECOMP_PHASE3_REFERENCE_EQUIVALENCE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF"

P3_SOURCE_MANIFEST = ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt"
P3_SOURCE_FILES = (
    ".openrecomp-phase3/src/p3_code_frontier_v1.py",
    ".openrecomp-phase3/src/p3_decode_mips32_v1.py",
    ".openrecomp-phase3/src/p3_elf_image_v1.py",
    ".openrecomp-phase3/src/p3_host_emit_v1.py",
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
    "tools/test_phase3_reachable_semantics_v1.py",
    "tools/test_phase3_reference_equivalence_v1.py",
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
ENTRY = 0x4650
EXPECTED_IMAGE_SHA256 = (
    "3eecfc957c4ed147544d2aa98c6e4f4d7aac41957e531cdfe01c2555ff0a91ae"
)
EXPECTED_REGIONS = (
    (0x0, 0x134, "r--"),
    (0x1000, 0x467C, "r-x"),
    (0x4680, 0x4DF8, "r--"),
    (0x4E00, 0x9620, "rw-"),
)
EXPECTED_DECODED_WORDS = 3479
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
EXPECTED_COREMARK_LINES = (
    "CoreMark Size    : 666",
    "Iterations       : 1000",
    "seedcrc          : 0xe9f5",
    "[0]crclist       : 0xe714",
    "[0]crcmatrix     : 0x1fd7",
    "[0]crcstate      : 0x8e3a",
    "[0]crcfinal      : 0xd340",
    "Correct operation validated.",
)
COMPARED_FIELDS = (
    "exit_status", "steps", "pc", "hi", "lo", "uart_bytes", "uart_hex",
    "state_fnv1a64", "failed", "failure",
)

SOURCE_INTEGRITY = "source_integrity.txt"
LOADER_JSON = "loader_cross_check.json"
REFERENCE_JSON = "reference_observable.json"
EQUIVALENCE_JSON = "equivalence.json"
NEGATIVES_JSON = "runtime_negatives.json"
DETERMINISM = "determinism.json"
RESULT_JSON = "RESULT.json"

CLAIM_BOUNDARY = (
    "P3-09 proves deterministic observable equivalence between the P3-08 native "
    "host execution and an independently written MIPS32 reference execution of "
    "the audited CoreMark ELF: identical exit status, step count, PC, HI/LO, "
    "UART byte stream and FNV-1a 64 state digest over the final guest image and "
    "register file. It proves this bounded audited program only and claims no "
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
    check("source:root-manifest-entries-verified", not [
        relative for relative, digest in sorted(root_entries.items())
        if not (ROOT / relative).is_file()
        or sha256_bytes((ROOT / relative).read_bytes()) != digest])
    check("source:phase3-manifest-exists", P3_SOURCE_MANIFEST.is_file())
    phase3_digest = sha256_bytes(P3_SOURCE_MANIFEST.read_bytes())
    phase3_entries = parse_manifest(P3_SOURCE_MANIFEST)
    check("source:phase3-manifest-entry-set",
          tuple(sorted(phase3_entries)) == tuple(sorted(P3_SOURCE_FILES)))
    check("source:phase3-manifest-entries-verified", not [
        relative for relative, digest in sorted(phase3_entries.items())
        if not (ROOT / relative).is_file()
        or sha256_bytes((ROOT / relative).read_bytes()) != digest])
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
        "phase3_manifest_sha256": phase3_digest,
        "phase3_manifest_entries": len(phase3_entries),
    }


def audit_loader(data: bytes) -> None:
    check("fixture:sha256", sha256_bytes(data) == ELF_SHA256)
    check("fixture:size", len(data) == ELF_SIZE)
    loaded = load_elf_flat(data)
    check("loader:entry", loaded.entry == ENTRY)
    check("loader:image-sha", loaded.sha256 == EXPECTED_IMAGE_SHA256)
    p3_07 = json.loads((P3_07_EVIDENCE / "emission.json").read_text(encoding="utf-8"))
    check("loader:image-matches-host-image",
          p3_07["image_sha256"] == loaded.sha256)
    check("loader:regions", loaded.regions == EXPECTED_REGIONS)

    code = decode_text(loaded.data)
    check("loader:decoded-words", len(code) == EXPECTED_DECODED_WORDS)
    histogram: dict[str, int] = {}
    for record in code.values():
        name = OP_NAMES[record[0]]
        histogram[name] = histogram.get(name, 0) + 1
    check("loader:op-histogram", histogram == EXPECTED_OP_HISTOGRAM)

    payload = {
        "stage": STAGE,
        "image_sha256": loaded.sha256,
        "host_image_sha256": p3_07["image_sha256"],
        "entry": f"0x{loaded.entry:08x}",
        "regions": [{"start": f"0x{start:08x}", "end": f"0x{end:08x}",
                     "permissions": permissions}
                    for start, end, permissions in loaded.regions],
        "decoded_words": len(code),
        "op_histogram": dict(sorted(histogram.items())),
        "policy": (
            "the reference loader and decoder are independent of the host "
            "emitter and of the P3-03/P3-04 decode layers; equality with the "
            "host image and the frozen op histogram is the cross-check"
        ),
    }
    ARTIFACTS[LOADER_JSON] = evidence_json_bytes(payload)
    FINDINGS["loader"] = {
        "image_sha256": loaded.sha256,
        "decoded_words": len(code),
        "op_histogram_sha256": sha256_bytes(
            json.dumps(dict(sorted(histogram.items())), sort_keys=True).encode("ascii")),
    }


def audit_reference(data: bytes) -> dict[str, str]:
    result = run(data)
    observable = result.observable
    uart = bytes.fromhex(observable["uart_hex"])
    text = uart.decode("ascii", errors="strict")
    for marker in EXPECTED_COREMARK_LINES:
        check(f"reference:coremark-line:{marker.split(':')[0]}", marker in text)
    check("reference:no-failure", observable["failed"] == "0"
          and observable["failure"] == "")
    payload = {
        "stage": STAGE,
        "observable": observable,
        "final_image_sha256": sha256_bytes(result.image),
        "final_register_dump_sha256": sha256_bytes(result.dump),
        "uart_text": text,
        "policy": (
            "the reference is a full deterministic execution of the audited "
            "program; the evidence records only deterministic values so the "
            "artifact set is byte-identical across runs"
        ),
    }
    ARTIFACTS[REFERENCE_JSON] = evidence_json_bytes(payload)
    FINDINGS["reference"] = {
        "observable": observable,
        "final_image_sha256": sha256_bytes(result.image),
        "final_register_dump_sha256": sha256_bytes(result.dump),
    }
    return observable


def audit_equivalence(native: dict[str, str], reference: dict[str, str]) -> None:
    for field in COMPARED_FIELDS:
        check(f"equivalence:{field}", native.get(field) == reference.get(field))
    payload = {
        "stage": STAGE,
        "fields": list(COMPARED_FIELDS),
        "native": {field: native.get(field) for field in COMPARED_FIELDS},
        "reference": {field: reference.get(field) for field in COMPARED_FIELDS},
        "result": "DETERMINISTIC_OBSERVABLE_EQUIVALENCE",
    }
    ARTIFACTS[EQUIVALENCE_JSON] = evidence_json_bytes(payload)
    FINDINGS["equivalence"] = {"result": payload["result"],
                               "native_sha256": sha256_bytes(
                                   json.dumps(native, sort_keys=True).encode("ascii"))}


def synthetic_elf(words: list[int], *, vaddr: int = 0x1000) -> bytes:
    """Build a minimal little-endian ELF32 with one executable PT_LOAD segment."""
    code = b"".join(struct.pack("<I", word & 0xFFFFFFFF) for word in words)
    phoff = 52
    code_offset = 0x1000
    header = bytearray(52)
    header[0:4] = b"\x7fELF"
    header[4] = 1
    header[5] = 1
    header[6] = 1
    ident = struct.pack(
        "<HHIIIIIHHHHHH",
        2, 8, 1, vaddr, phoff, 0, 0, 52, 32, 1, 0, 0, 0)
    header[0x10:0x10 + len(ident)] = ident
    phdr = struct.pack("<IIIIIIII", 1, code_offset, vaddr, vaddr,
                       len(code), len(code), 5, 4)
    data = bytearray(code_offset)
    data[0:52] = header
    data[52:52 + 32] = phdr
    data[code_offset:code_offset + len(code)] = code
    return bytes(data)


def audit_reference_negatives() -> None:
    cases = []

    def expect(name: str, expected: str, words: list[int]) -> None:
        try:
            observable = run(synthetic_elf(words)).observable
            actual = observable["failure"]
            failed = observable["failed"]
        except ReferenceError as exc:
            actual = exc.code
            failed = "1"
        cases.append({
            "fixture": name,
            "expected_failure": expected,
            "observed_failure": actual,
            "observed_failed": failed,
            "status": "PASS" if (failed == "1" and actual == expected) else "FAIL",
        })

    # divu $4, $5 with both registers zero.
    expect("div-by-zero", FAIL_DIVIDE_BY_ZERO, [0x0085001B])
    # teq $4, $5 with both registers zero (code 0).
    expect("teq-trap", "teq trap code=0x0", [(4 << 21) | (5 << 16) | 0x34])
    # addiu $4, $0, 2; jr $4; nop
    expect("unaligned-jr", FAIL_UNALIGNED_JUMP,
           [0x24040002, 0x00800008, 0x00000000])
    # lui $4, 0x2000; sw $5, 0($4)
    expect("memory-out-of-range", FAIL_MEMORY_OUT_OF_RANGE,
           [0x3C042000, 0xAC850000])
    # jr $ra with $ra = 0 -> PC outside the text region.
    expect("pc-outside-image", FAIL_PC_OUTSIDE,
           [0x03E00008, 0x00000000])

    malformed = []
    for name, payload in (
        ("bad-magic", b"\x00" * 64),
        ("short-file", b"\x7fELF"),
    ):
        try:
            load_elf_flat(payload)
            malformed.append({"fixture": name, "status": "FAIL", "error": "accepted"})
        except ReferenceError as exc:
            malformed.append({"fixture": name, "status": "PASS", "error": exc.code})
    check("negatives:malformed-rejected", all(item["status"] == "PASS" for item in malformed))

    failures = [item for item in cases if item["status"] != "PASS"]
    for item in failures:
        print(f"NEGATIVE-FAILURE: {item}", flush=True)
    check("negatives:no-failures", not failures)
    check("negatives:count", len(cases) == 5)
    ARTIFACTS[NEGATIVES_JSON] = evidence_json_bytes({
        "stage": STAGE,
        "cases": cases,
        "malformed": malformed,
        "failed": len(failures),
    })
    FINDINGS["runtime_negatives"] = cases


def audit_determinism(data: bytes) -> None:
    artifact_hashes = {name: sha256_bytes(payload) for name, payload in sorted(ARTIFACTS.items())}
    record = {
        "source_sha256": sha256_bytes(data),
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
    parser = argparse.ArgumentParser(description="P3-09 reference equivalence gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-09")
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

    print("=== P3-09 Independent Reference Equivalence Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    evidence_files: dict[str, str] = {}
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("fixture / loader")
        data = elf_path.read_bytes()
        audit_loader(data)
        banner("native observable pin")
        native = json.loads(
            (P3_08_EVIDENCE / "native_execution.json").read_text(encoding="utf-8"))
        check("native:recorded", native["observable"]["steps"] == "394997250")
        banner("reference execution")
        reference = audit_reference(data)
        banner("equivalence")
        audit_equivalence(native["observable"], reference)
        banner("reference negatives")
        audit_reference_negatives()
        banner("determinism")
        audit_determinism(data)
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
