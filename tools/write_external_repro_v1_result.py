#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "external-repro-v1"
EVIDENCE = ROOT / "evidence" / "external-repro-v1"
FIXTURES = [
    "logic-shift",
    "memory-width",
    "branches-calls",
    "mult-hilo",
    "big-endian-memory",
]
EXPECTED_MIPS = {
    "logic-shift": {"checksum": 435263539, "operations": 72, "delay_slots": 1},
    "memory-width": {"checksum": 4257846410, "operations": 60, "delay_slots": 1},
    "branches-calls": {"checksum": 2065440492, "operations": 75, "delay_slots": 9},
    "mult-hilo": {"checksum": 768371589, "operations": 44, "delay_slots": 1},
    "big-endian-memory": {"checksum": 938211822, "operations": 24, "delay_slots": 1},
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    source_head = os.environ.get("OPENRECOMP_SOURCE_HEAD", "").strip()
    require(len(source_head) == 40 and all(c in "0123456789abcdef" for c in source_head), "OPENRECOMP_SOURCE_HEAD must be a lowercase 40-character commit SHA")

    e07 = load(BUILD / "e07.result.json")
    rv_core = load(BUILD / "rv32i.core.json")
    rv_gcc = load(BUILD / "rv32i.aot.gcc.json")
    rv_clang = load(BUILD / "rv32i.aot.clang.json")
    mips_core = load(BUILD / "mips32.core.json")
    mips_gcc = load(BUILD / "mips32.aot.gcc.json")
    mips_clang = load(BUILD / "mips32.aot.clang.json")

    require(e07["status"] == "PASS", "E07 result is not PASS")
    require(e07["classification"]["riscv32_fixture_path"] == "PROVEN", "E07 RV32I classification changed")
    require(rv_core == rv_gcc == rv_clang, "RV32I Core/GCC/Clang results differ")
    require(mips_core == mips_gcc == mips_clang, "MIPS32 vertical-slice Core/GCC/Clang results differ")
    require(rv_core["checksum"] == 122010428 and rv_core["return_a0"] == 48 and rv_core["operations"] == 3866, "RV32I established result changed")
    require(mips_core["checksum"] == 1950232098 and mips_core["return_v0"] == 31 and mips_core["operations"] == 100, "MIPS32 vertical-slice established result changed")

    expansion = []
    for name in FIXTURES:
        reference = load(BUILD / f"{name}.reference.json")
        core = load(BUILD / f"{name}.core.json")
        gcc = load(BUILD / f"{name}.aot.gcc.json")
        clang = load(BUILD / f"{name}.aot.clang.json")
        frontend = load(BUILD / f"{name}.frontend.json")
        expected = EXPECTED_MIPS[name]
        require(reference["checksum"] == expected["checksum"], f"{name}: checksum changed")
        require(core["checksum"] == reference["checksum"] == gcc["checksum"] == clang["checksum"], f"{name}: reference/Core/AOT checksum mismatch")
        require(core["operations"] == expected["operations"], f"{name}: operation count changed")
        require(gcc["operations"] == core["operations"] == clang["operations"], f"{name}: Core/AOT operation mismatch")
        require(reference["delay_slots_executed"] == expected["delay_slots"], f"{name}: reference delay-slot count changed")
        require(frontend["delay_slots_lowered"] == expected["delay_slots"], f"{name}: frontend delay-slot count changed")
        expansion.append(
            {
                "fixture": name,
                "architecture": reference["architecture"],
                "checksum": reference["checksum"],
                "operations": core["operations"],
                "delay_slots": reference["delay_slots_executed"],
                "reference_core_aot_equivalence": "PASS",
            }
        )

    source_manifest_sha = hashlib.sha256((ROOT / "SOURCE_SHA256SUMS.txt").read_bytes()).hexdigest()
    result = {
        "schema_version": "1.0.0",
        "frontier": "OPENRECOMP_EXTERNAL_REPRO_V1",
        "status": "PASS",
        "classification": "PASS - reproducible Linux reviewer path",
        "source": {
            "commit": source_head,
            "source_sha256s_manifest": source_manifest_sha,
            "tracked_tree_mutation": False,
        },
        "scope": {
            "includes": [
                "E07 hardened synthetic RV32I proof",
                "RV32I normalized IR V1 and Core API V1 equivalence",
                "RV32I portable-C AOT under GCC and Clang",
                "MIPS32 vertical-slice Core/AOT equivalence",
                "MIPS32 Expansion V1 five-fixture reference/Core/AOT matrix",
                "Native AOT ABI V1 module loading on Linux x64",
                "tracked-file public-safety scan",
            ],
            "excludes": [
                "Unreal Engine execution",
                "Windows compiler/runtime parity",
                "macOS or non-x64 host parity",
                "Shipping Unreal packaging",
                "arbitrary guest-binary compatibility",
                "production optimizing-compiler claims",
            ],
        },
        "contracts": {
            "normalized_ir_v1": "FROZEN-FOR-IMPLEMENTATION",
            "native_aot_abi_v1": "FROZEN-FOR-PORTABILITY-TESTING",
        },
        "rv32i": {
            "e07_classification": "PROVEN",
            "checksum": rv_core["checksum"],
            "return_a0": rv_core["return_a0"],
            "operations": rv_core["operations"],
            "core_gcc_clang_equivalence": "PASS",
        },
        "mips32_vertical_slice": {
            "classification": "PASS - bounded",
            "checksum": mips_core["checksum"],
            "return_v0": mips_core["return_v0"],
            "operations": mips_core["operations"],
            "core_gcc_clang_equivalence": "PASS",
        },
        "mips32_expansion_v1": expansion,
        "public_safety": "PASS",
    }

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    result_path = EVIDENCE / "RESULT.json"
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    result_path.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    (EVIDENCE / "RESULT.sha256").write_text(f"{digest}  RESULT.json\n", encoding="ascii")
    (EVIDENCE / "RESULT.md").write_text(
        "# OpenRecomp External Repro V1\n\n"
        "**PASS** - reproducible Linux reviewer path for the bounded open-core evidence set.\n\n"
        f"- Source commit: `{source_head}`\n"
        "- RV32I E07: **PROVEN**; checksum `122010428`, `a0=48`, `3866` operations.\n"
        "- MIPS32 vertical slice: **PASS - bounded**; checksum `1950232098`, `v0=31`, `100` operations.\n"
        "- MIPS32 Expansion V1: **PASS - bounded** across five synthetic fixtures.\n"
        "- Linux GCC/Clang Native AOT parity: **PASS** for the included fixtures.\n"
        "- Public-safety scan: **PASS**.\n\n"
        "Unreal execution, Windows parity, other host platforms, arbitrary guest binaries and production compiler claims are outside this gate.\n",
        encoding="utf-8",
    )
    print(f"OPENRECOMP_EXTERNAL_REPRO_V1_RESULT_SHA256={digest}")
    print("OPENRECOMP_EXTERNAL_REPRO_V1_RESULT=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"OPENRECOMP_EXTERNAL_REPRO_V1_RESULT=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
