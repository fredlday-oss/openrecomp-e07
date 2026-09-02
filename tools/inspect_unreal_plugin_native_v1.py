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
    if len(argv) != 3:
        print(
            "usage: inspect_unreal_plugin_native_v1.py <native-module.dll> <host-contract.json>",
            file=sys.stderr,
        )
        return 2

    try:
        contract = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        host = E07ReferenceHost(contract)
        native = NativeAOTModule(argv[1], require_abi_v1=True)
        native.set_host_callback(lambda symbol, args: (True, host.call(symbol, args)))
        native.run()
        result = host.proof_result(native.observed_state, native.operations)
        function_return = native.function_return
        snapshot = host.snapshot()
    except (OSError, json.JSONDecodeError, KeyError, ValueError, CoreRuntimeError, NativeAOTError) as exc:
        print(f"OPENRECOMP_UNREAL_PLUGIN_V1_NATIVE_DIAGNOSTIC=FAIL: {exc}", file=sys.stderr)
        return 2

    print(f"NATIVE_OBSERVED_STATE={native.observed_state}")
    print(f"NATIVE_FUNCTION_HAS_RETURN={1 if function_return is not None else 0}")
    print(f"NATIVE_FUNCTION_RETURN={0 if function_return is None else function_return}")
    print(f"NATIVE_OPERATIONS={native.operations}")
    print(f"NATIVE_CHECKSUM={result['checksum']}")
    print(f"NATIVE_TICK_COUNT={snapshot['tick_count']}")
    print(f"NATIVE_GRAPHICS_CALLS={snapshot['graphics_calls']}")
    print(f"NATIVE_AUDIO_CALLS={snapshot['audio_calls']}")
    print(f"NATIVE_INPUT_CALLS={snapshot['input_calls']}")
    print(f"NATIVE_SYSTEM_CALLS={snapshot['system_calls']}")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_NATIVE_DIAGNOSTIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
