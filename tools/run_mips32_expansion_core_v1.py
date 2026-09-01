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
            "usage: run_mips32_expansion_core_v1.py <module.json> <ir.json> <host-contract.json> <fixture.json> <out-result.json>",
            file=sys.stderr,
        )
        return 2
    try:
        module = ModuleImage.from_files(argv[1], argv[2], argv[3])
        meta = json.loads(Path(argv[4]).read_text(encoding="utf-8"))
        architecture = module.ir["source"]["architecture"]
        if architecture not in {"mips32-le", "mips32-be"}:
            raise CoreRuntimeError("expanded MIPS32 gate requires mips32-le or mips32-be normalized source")
        if architecture != meta["architecture"]:
            raise CoreRuntimeError("fixture/normalized architecture mismatch")
        if module.ir["required_host_symbols"]:
            raise CoreRuntimeError("expanded MIPS32 fixture unexpectedly requires host calls")

        host = CallbackHostBinding(module.host_contract["contract_version"], {})
        executor = ReferenceExecutor(module, host)
        execution = executor.run()

        obs = meta["observable_memory"]
        start = obs["address"]
        end = start + obs["size_bytes"]
        memory_bytes = bytes(executor.memory.data[start:end])
        byteorder = module.ir["source"]["endianness"]
        result = {
            "architecture": architecture,
            "source_input_sha256": module.ir["source"]["input_sha256"],
            "return_v0": execution.observed_state,
            "function_return": execution.function_return,
            "state": execution.state,
            "memory_address": start,
            "memory_bytes_hex": memory_bytes.hex(),
            "memory_word": int.from_bytes(memory_bytes, byteorder) if memory_bytes else 0,
            "checksum": _checksum(execution.state, memory_bytes),
            "operations": execution.operations,
            "host": execution.host,
        }
        Path(argv[5]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, CoreRuntimeError) as exc:
        print(f"OPENRECOMP_MIPS32_EXPANSION_CORE_API=FAIL: {exc}", file=sys.stderr)
        return 2

    print(f"MIPS32_EXPANSION_CORE_V0={result['return_v0']}")
    print(f"MIPS32_EXPANSION_CORE_CHECKSUM={result['checksum']}")
    print(f"MIPS32_EXPANSION_CORE_OPERATIONS={result['operations']}")
    print("OPENRECOMP_MIPS32_EXPANSION_CORE_API=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
