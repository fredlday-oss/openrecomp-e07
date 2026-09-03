#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openrecomp.module_v1_1 import load_module_v1_1
from tools.native_aot_abi_v1 import NativeABIError, generate


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: native_aot_abi_v1_1.py <module.json> <ir.json> <host-contract.json> <out.c>", file=sys.stderr); return 2
    try:
        module = load_module_v1_1(argv[1], argv[2], argv[3])
        Path(argv[4]).write_text(generate(module), encoding="utf-8", newline="\n")
    except (OSError, KeyError, ValueError, NativeABIError) as exc:
        print(f"OPENRECOMP_NATIVE_AOT_ABI_V1_1_GENERATE=FAIL: {exc}", file=sys.stderr); return 2
    print("OPENRECOMP_NATIVE_AOT_ABI_V1_1_GENERATE=PASS"); return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
