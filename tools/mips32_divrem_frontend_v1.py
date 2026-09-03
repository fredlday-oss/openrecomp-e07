#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mips32 import DecodeError
from adapters.mips32_divrem import decode as decode_divrem
import tools.mips32_expansion_frontend_v1 as base

PROFILE = "divrem-v1"
FRONTEND_VERSION = "1.0.0"
_BASE_LOWER_SIMPLE = base._lower_simple


def _divop(out: list[dict], address: int, tag: str, kind: str, lhs: dict, rhs: dict) -> dict:
    result = base._tmp(address, tag)
    out.append({"op": "binop", "result": result, "result_type": "i32", "kind": kind, "lhs": lhs, "rhs": rhs, "source_address": address})
    return {"value": result}


def _lower_simple_divrem(out: list[dict], insn: dict) -> None:
    if insn["op"] not in {"div", "divu"}:
        return _BASE_LOWER_SIMPLE(out, insn)
    address = insn["address"]
    lhs = base._read_reg(out, address, insn["rs"], "div_lhs")
    rhs = base._read_reg(out, address, insn["rt"], "div_rhs")
    signed = insn["op"] == "div"
    quotient = _divop(out, address, "div_q", "sdiv" if signed else "udiv", lhs, rhs)
    remainder = _divop(out, address, "div_r", "srem" if signed else "urem", lhs, rhs)
    base._write_state(out, address, "special:lo", quotient)
    base._write_state(out, address, "special:hi", remainder)


def convert(meta: dict, words: dict[int, int], source_sha256: str, contract: dict) -> tuple[dict, dict, dict]:
    if meta.get("fixture_version") != FRONTEND_VERSION or meta.get("profile") != PROFILE:
        raise base.FrontendError("unsupported MIPS32 div/rem fixture/profile version")
    if meta.get("divrem_domain") != "defined-mips32-operands-only":
        raise base.FrontendError("div/rem fixture must declare the bounded defined-MIPS32 operand domain")
    legacy_meta = copy.deepcopy(meta); legacy_meta["profile"] = base.PROFILE
    old_decode = base.decode; old_lower = base._lower_simple
    base.decode = decode_divrem; base._lower_simple = _lower_simple_divrem
    try:
        ir, sidecar, report = base.convert(legacy_meta, words, source_sha256, contract)
    finally:
        base.decode = old_decode; base._lower_simple = old_lower
    fixture_id = meta["fixture_id"]
    ir["ir_version"] = "1.1.0"
    ir["module_id"] = f"openrecomp.mips32.synthetic.divrem-v1.{fixture_id}"
    ir["source"]["adapter"] = "openrecomp.mips32-divrem-v1"
    ir["required_features"] = ["core-v1", "integer-divrem-v1"]
    report["profile"] = PROFILE; report["divrem_domain"] = meta["divrem_domain"]
    return ir, sidecar, report


def main(argv: list[str]) -> int:
    if len(argv) != 7:
        print("usage: mips32_divrem_frontend_v1.py <fixture.hex> <fixture.json> <host-contract.json> <out-ir.json> <out-sidecar.json> <out-report.json>", file=sys.stderr); return 2
    try:
        words, source_hash = base.load_hex(argv[1]); meta = json.loads(Path(argv[2]).read_text(encoding="utf-8")); contract = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        ir, sidecar, report = convert(meta, words, source_hash, contract)
        base._write_json(argv[4], ir); base._write_json(argv[5], sidecar); base._write_json(argv[6], report)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, DecodeError, base.FrontendError) as exc:
        print(f"OPENRECOMP_MIPS32_DIVREM_FRONTEND=FAIL: {exc}", file=sys.stderr); return 2
    print(f"MIPS32_DIVREM_FIXTURE={report['fixture_id']}"); print("OPENRECOMP_MIPS32_DIVREM_FRONTEND=PASS"); return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
