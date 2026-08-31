#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.aot_native_module_v1 import NativeAOTError, NativeAOTModule
from tools.run_mips32_core_v1 import _checksum


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: run_aot_mips32_v1.py <native-module.so> <ir.json> <fixture.json> <out-result.json>", file=sys.stderr)
        return 2
    try:
        ir = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        meta = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        if ir["source"]["architecture"] != "mips32-le":
            raise ValueError("MIPS32 AOT proof requires mips32-le normalized source")
        if ir["required_host_symbols"]:
            raise ValueError("MIPS32 AOT proof unexpectedly requires host calls")

        native = NativeAOTModule(argv[1])
        native.run()
        state = native.state_snapshot()
        obs = meta["observable_memory"]
        memory_bytes = native.memory(obs["address"], obs["size_bytes"])
        result = {
            "architecture": ir["source"]["architecture"],
            "source_input_sha256": ir["source"]["input_sha256"],
            "return_v0": native.observed_state,
            "function_return": native.function_return,
            "state": state,
            "memory_address": obs["address"],
            "memory_bytes_hex": memory_bytes.hex(),
            "memory_word": int.from_bytes(memory_bytes, "little"),
            "checksum": _checksum(state, memory_bytes),
            "operations": native.operations,
            "host": {},
        }
        Path(argv[4]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, KeyError, ValueError, NativeAOTError) as exc:
        print(f"OPENRECOMP_AOT_MIPS32_V1=FAIL: {exc}", file=sys.stderr)
        return 2

    print(f"AOT_MIPS32_V0={result['return_v0']}")
    print(f"AOT_MIPS32_CHECKSUM={result['checksum']}")
    print(f"AOT_MIPS32_OPERATIONS={result['operations']}")
    print("OPENRECOMP_AOT_MIPS32_V1=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
