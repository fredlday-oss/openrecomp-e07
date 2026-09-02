#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "evidence" / "external-repro-v1" / "RESULT.json"
SHA = ROOT / "evidence" / "external-repro-v1" / "RESULT.sha256"

EXPECTED_FIXTURES = {
    "logic-shift": (435263539, 72, 1),
    "memory-width": (4257846410, 60, 1),
    "branches-calls": (2065440492, 75, 9),
    "mult-hilo": (768371589, 44, 1),
    "big-endian-memory": (938211822, 24, 1),
}


def fail(message: str) -> None:
    raise ValueError(message)


def main() -> int:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    if result.get("schema_version") != "1.0.0":
        fail("unexpected external-repro result schema version")
    if result.get("frontier") != "OPENRECOMP_EXTERNAL_REPRO_V1" or result.get("status") != "PASS":
        fail("frontier identity/status mismatch")
    if result.get("classification") != "PASS - reproducible Linux reviewer path":
        fail("classification mismatch")

    source = result["source"]
    commit = source["commit"]
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        fail("source commit is not a lowercase SHA-1 commit id")
    if source["tracked_tree_mutation"] is not False:
        fail("tracked-tree mutation must remain false")
    expected_manifest = hashlib.sha256((ROOT / "SOURCE_SHA256SUMS.txt").read_bytes()).hexdigest()
    if source["source_sha256s_manifest"] != expected_manifest:
        fail("SOURCE_SHA256SUMS.txt digest mismatch")

    rv = result["rv32i"]
    if rv != {
        "checksum": 122010428,
        "core_gcc_clang_equivalence": "PASS",
        "e07_classification": "PROVEN",
        "operations": 3866,
        "return_a0": 48,
    }:
        fail("RV32I result changed")

    mips = result["mips32_vertical_slice"]
    if mips != {
        "checksum": 1950232098,
        "classification": "PASS - bounded",
        "core_gcc_clang_equivalence": "PASS",
        "operations": 100,
        "return_v0": 31,
    }:
        fail("MIPS32 vertical-slice result changed")

    expansion = result["mips32_expansion_v1"]
    if len(expansion) != len(EXPECTED_FIXTURES):
        fail("unexpected MIPS32 expansion fixture count")
    seen = set()
    for item in expansion:
        name = item["fixture"]
        if name not in EXPECTED_FIXTURES or name in seen:
            fail(f"unexpected or duplicate expansion fixture: {name}")
        seen.add(name)
        checksum, operations, delay_slots = EXPECTED_FIXTURES[name]
        if item["checksum"] != checksum or item["operations"] != operations or item["delay_slots"] != delay_slots:
            fail(f"{name}: established result changed")
        if item["reference_core_aot_equivalence"] != "PASS":
            fail(f"{name}: equivalence is not PASS")
    if seen != set(EXPECTED_FIXTURES):
        fail("MIPS32 expansion fixture set mismatch")

    if result["contracts"] != {
        "native_aot_abi_v1": "FROZEN-FOR-PORTABILITY-TESTING",
        "normalized_ir_v1": "FROZEN-FOR-IMPLEMENTATION",
    }:
        fail("frozen-contract classification changed")
    if result["public_safety"] != "PASS":
        fail("public safety is not PASS")

    raw = RESULT.read_bytes()
    expected_digest = hashlib.sha256(raw).hexdigest()
    digest_line = SHA.read_text(encoding="ascii").strip()
    if digest_line != f"{expected_digest}  RESULT.json":
        fail("RESULT.sha256 does not authenticate RESULT.json")

    print(f"OPENRECOMP_EXTERNAL_REPRO_V1_VERIFIED_SHA256={expected_digest}")
    print("OPENRECOMP_EXTERNAL_REPRO_V1_VERIFY=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"OPENRECOMP_EXTERNAL_REPRO_V1_VERIFY=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
