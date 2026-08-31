#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: check_aot_ir_v1.py <rv-core.json> <rv-aot.json> <mips-core.json> <mips-aot.json>", file=sys.stderr)
        return 2
    try:
        rv_core, rv_aot, mips_core, mips_aot = map(load, argv[1:])
        if rv_core != rv_aot:
            raise ValueError("RV32I AOT result differs from Core API reference result")
        if mips_core != mips_aot:
            raise ValueError("MIPS32 AOT result differs from Core API reference result")
        if rv_aot["checksum"] != 122010428 or rv_aot["return_a0"] != 48:
            raise ValueError("RV32I established proof result changed")
        if mips_aot["checksum"] != 1950232098 or mips_aot["return_v0"] != 31:
            raise ValueError("MIPS32 established proof result changed")
        if rv_aot["operations"] != 3866:
            raise ValueError("RV32I AOT operation count differs from established Core API count")
        if mips_aot["operations"] != 100:
            raise ValueError("MIPS32 AOT operation count differs from established Core API count")
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"OPENRECOMP_IR_V1_AOT_DUAL_ARCH=FAIL: {exc}", file=sys.stderr)
        return 2

    print("AOT_RV32I_CHECKSUM=122010428")
    print("AOT_MIPS32_CHECKSUM=1950232098")
    print("AOT_RV32I_OPERATIONS=3866")
    print("AOT_MIPS32_OPERATIONS=100")
    print("OPENRECOMP_IR_V1_AOT_RV32I=PASS")
    print("OPENRECOMP_IR_V1_AOT_MIPS32=PASS")
    print("OPENRECOMP_IR_V1_AOT_DUAL_ARCH=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
