#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor
from openrecomp.runtime import CoreRuntimeError

MASK32 = 0xFFFFFFFF


def _checksum(state: dict[str, int], memory_bytes: bytes) -> int:
    value = 2166136261
    for reg in range(1, 32):
        register = state[f"gpr:r{reg}"] & MASK32
        for byte in register.to_bytes(4, "little"):
            value = ((value ^ byte) * 16777619) & MASK32
    for byte in memory_bytes:
        value = ((value ^ byte) * 16777619) & MASK32
    return value


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print(
            "usage: run_mips32_core_v1.py <module.json> <ir.json> <host-contract.json> <fixture.json> <out-result.json>",
            file=sys.stderr,
        )
        return 2
    try:
        module = ModuleImage.from_files(argv[1], argv[2], argv[3])
        meta = json.loads(Path(argv[4]).read_text(encoding="utf-8"))
        if module.ir["source"]["architecture"] != "mips32-le":
            raise CoreRuntimeError("Core MIPS32 gate requires mips32-le normalized source")
        if module.ir["required_host_symbols"]:
            raise CoreRuntimeError("MIPS32 vertical slice unexpectedly requires host calls")

        host = CallbackHostBinding(module.host_contract["contract_version"], {})
        executor = ReferenceExecutor(module, host)
        execution = executor.run()

        obs = meta["observable_memory"]
        start = obs["address"]
        end = start + obs["size_bytes"]
        memory_bytes = bytes(executor.memory.data[start:end])
        result = {
            "architecture": module.ir["source"]["architecture"],
            "source_input_sha256": module.ir["source"]["input_sha256"],
            "return_v0": execution.observed_state,
            "function_return": execution.function_return,
            "state": execution.state,
            "memory_address": start,
            "memory_bytes_hex": memory_bytes.hex(),
            "memory_word": int.from_bytes(memory_bytes, "little"),
            "checksum": _checksum(execution.state, memory_bytes),
            "operations": execution.operations,
            "host": execution.host,
        }
        Path(argv[5]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, CoreRuntimeError) as exc:
        print(f"OPENRECOMP_MIPS32_CORE_API_V1=FAIL: {exc}", file=sys.stderr)
        return 2

    print(f"MIPS32_CORE_API_V0={result['return_v0']}")
    print(f"MIPS32_CORE_API_CHECKSUM={result['checksum']}")
    print(f"MIPS32_CORE_API_OPERATIONS={result['operations']}")
    print("OPENRECOMP_MIPS32_CORE_API_V1=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
