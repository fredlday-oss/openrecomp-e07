#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: str) -> dict: return json.loads(Path(path).read_text(encoding="utf-8"))
def fail(message: str) -> None: raise AssertionError(message)


def main(argv: list[str]) -> int:
    if len(argv) < 8:
        print("usage: check_mips32_divrem_v1.py <fixture.json> <frontend.json> <ir.json> <module.json> <reference.json> <core.json> <aot.json> [aot.json ...]", file=sys.stderr); return 2
    meta, report, ir, module, reference, core = map(load, argv[1:7]); aots = [load(path) for path in argv[7:]]; expected = meta["expected"]
    if meta.get("profile") != "divrem-v1" or meta.get("divrem_domain") != "defined-mips32-operands-only": fail("fixture bounded div/rem profile mismatch")
    if ir["ir_version"] != "1.1.0": fail("frontend did not emit IR V1.1")
    if ir["required_features"] != ["core-v1", "integer-divrem-v1"]: fail("integer-divrem-v1 feature declaration mismatch")
    if ir["source"]["adapter"] != "openrecomp.mips32-divrem-v1": fail("MIPS32 div/rem adapter identity mismatch")
    if module["ir"]["version"] != "1.1.0": fail("Module Image did not preserve IR V1.1")
    if report.get("divrem_domain") != "defined-mips32-operands-only": fail("frontend report lost bounded MIPS32 domain")
    kinds = [insn["kind"] for function in ir["functions"] for block in function["blocks"] for insn in block["instructions"] if insn.get("op") == "binop" and insn.get("kind") in {"udiv", "urem", "sdiv", "srem"}]
    if sorted(kinds) != ["sdiv", "srem", "udiv", "urem"]: fail(f"expected all four portable div/rem kinds once, got {kinds!r}")
    results = [reference, core, *aots]
    hashes = {ir["source"]["input_sha256"], module["ir"]["source_input_sha256"], module["provenance"]["source_input_sha256"], report["source_input_sha256"], *(result["source_input_sha256"] for result in results)}
    if len(hashes) != 1: fail("source provenance diverged")
    named = [("reference", reference), ("core", core)] + [(f"aot[{i}]", x) for i, x in enumerate(aots, 1)]
    for name, result in named:
        for key in ("return_v0", "memory_word", "memory_bytes_hex", "checksum"):
            if result[key] != expected[key]: fail(f"{name}: {key} mismatch: expected {expected[key]!r}, got {result[key]!r}")
        for slot, value in expected["state"].items():
            if result["state"].get(slot) != value: fail(f"{name}: expected {slot}={value}, got {result['state'].get(slot)}")
    if reference["state"] != core["state"]: fail("Core complete state differs from independent reference")
    for index, result in enumerate(aots, 1):
        if result["state"] != reference["state"]: fail(f"AOT[{index}] complete state differs from independent reference")
        if result["operations"] != core["operations"]: fail(f"AOT[{index}] operation count differs from Core")
    if reference["delay_slots_executed"] != expected["delay_slots_executed"]: fail("independent reference delay-slot count mismatch")
    if report["delay_slots_lowered"] != expected["delay_slots_executed"]: fail("frontend delay-slot count mismatch")
    print(f"MIPS32_DIVREM_CHECKSUM={reference['checksum']}"); print("OPENRECOMP_MIPS32_DIVREM_V1=PASS"); return 0


if __name__ == "__main__":
    try: raise SystemExit(main(sys.argv))
    except (OSError, json.JSONDecodeError, KeyError, AssertionError) as exc:
        print(f"OPENRECOMP_MIPS32_DIVREM_V1=FAIL: {exc}", file=sys.stderr); raise SystemExit(2)
