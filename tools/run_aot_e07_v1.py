#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.aot_native_module_v1 import NativeAOTError, NativeAOTModule
from tools.run_core_api_v1 import E07ReferenceHost
from openrecomp.runtime import CoreRuntimeError


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: run_aot_e07_v1.py <native-module.so> <host-contract.json> <out-result.json>", file=sys.stderr)
        return 2
    try:
        contract = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        host = E07ReferenceHost(contract)
        native = NativeAOTModule(argv[1])
        native.set_host_callback(lambda symbol, args: (True, host.call(symbol, args)))
        native.run()
        result = host.proof_result(native.observed_state, native.operations)
        Path(argv[3]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, KeyError, ValueError, CoreRuntimeError, NativeAOTError) as exc:
        print(f"OPENRECOMP_AOT_E07_V1=FAIL: {exc}", file=sys.stderr)
        return 2

    print(f"AOT_E07_CHECKSUM={result['checksum']}")
    print(f"AOT_E07_RETURN_A0={result['return_a0']}")
    print(f"AOT_E07_OPERATIONS={result['operations']}")
    print("OPENRECOMP_AOT_E07_V1=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
