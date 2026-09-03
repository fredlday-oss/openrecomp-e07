#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openrecomp import CallbackHostBinding
from openrecomp.executor_v1_1 import ReferenceExecutorV11
from openrecomp.module_v1_1 import load_module_v1_1
from openrecomp.runtime import CoreRuntimeError
from tools.run_mips32_expansion_core_v1 import _checksum


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print("usage: run_mips32_divrem_core_v1.py <module.json> <ir.json> <host-contract.json> <fixture.json> <out-result.json>", file=sys.stderr); return 2
    try:
        module = load_module_v1_1(argv[1], argv[2], argv[3]); meta = json.loads(Path(argv[4]).read_text(encoding="utf-8"))
        if meta.get("profile") != "divrem-v1": raise CoreRuntimeError("MIPS32 div/rem gate requires divrem-v1 fixture")
        if module.ir["source"]["architecture"] != meta["architecture"]: raise CoreRuntimeError("fixture/normalized architecture mismatch")
        if module.ir["required_host_symbols"]: raise CoreRuntimeError("MIPS32 div/rem fixture unexpectedly requires host calls")
        host = CallbackHostBinding(module.host_contract["contract_version"], {}); executor = ReferenceExecutorV11(module, host); execution = executor.run()
        obs = meta["observable_memory"]; start = obs["address"]; end = start + obs["size_bytes"]; memory_bytes = bytes(executor.memory.data[start:end])
        result = {"architecture": module.ir["source"]["architecture"], "source_input_sha256": module.ir["source"]["input_sha256"], "return_v0": execution.observed_state, "function_return": execution.function_return, "state": execution.state, "memory_address": start, "memory_bytes_hex": memory_bytes.hex(), "memory_word": int.from_bytes(memory_bytes, module.ir["source"]["endianness"]) if memory_bytes else 0, "checksum": _checksum(execution.state, memory_bytes), "operations": execution.operations, "host": execution.host}
        Path(argv[5]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, CoreRuntimeError) as exc:
        print(f"OPENRECOMP_MIPS32_DIVREM_CORE_API=FAIL: {exc}", file=sys.stderr); return 2
    print(f"MIPS32_DIVREM_CORE_V0={result['return_v0']}"); print(f"MIPS32_DIVREM_CORE_CHECKSUM={result['checksum']}"); print(f"MIPS32_DIVREM_CORE_OPERATIONS={result['operations']}"); print("OPENRECOMP_MIPS32_DIVREM_CORE_API=PASS"); return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
