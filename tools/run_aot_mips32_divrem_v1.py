#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.aot_native_module_v1 import NativeAOTError, NativeAOTModule
from tools.run_mips32_expansion_core_v1 import _checksum


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: run_aot_mips32_divrem_v1.py <native-module> <ir.json> <fixture.json> <out-result.json>", file=sys.stderr); return 2
    try:
        ir = json.loads(Path(argv[2]).read_text(encoding="utf-8")); meta = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        if ir["ir_version"] != "1.1.0" or "integer-divrem-v1" not in ir["required_features"]: raise ValueError("AOT div/rem proof requires IR V1.1 integer-divrem-v1")
        if meta.get("profile") != "divrem-v1": raise ValueError("AOT div/rem proof requires divrem-v1 fixture")
        native = NativeAOTModule(argv[1]); native.run(); state = native.state_snapshot(); obs = meta["observable_memory"]; memory_bytes = native.memory(obs["address"], obs["size_bytes"])
        result = {"architecture": ir["source"]["architecture"], "source_input_sha256": ir["source"]["input_sha256"], "return_v0": native.observed_state, "function_return": native.function_return, "state": state, "memory_address": obs["address"], "memory_bytes_hex": memory_bytes.hex(), "memory_word": int.from_bytes(memory_bytes, ir["source"]["endianness"]) if memory_bytes else 0, "checksum": _checksum(state, memory_bytes), "operations": native.operations, "host": {}}
        Path(argv[4]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, KeyError, ValueError, NativeAOTError) as exc:
        print(f"OPENRECOMP_MIPS32_DIVREM_AOT=FAIL: {exc}", file=sys.stderr); return 2
    print(f"MIPS32_DIVREM_AOT_V0={result['return_v0']}"); print(f"MIPS32_DIVREM_AOT_CHECKSUM={result['checksum']}"); print(f"MIPS32_DIVREM_AOT_OPERATIONS={result['operations']}"); print("OPENRECOMP_MIPS32_DIVREM_AOT=PASS"); return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
