#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "core_h": ROOT / "integrations/unreal/OpenRecompNativeAotHostCoreV1.h",
    "core_cpp": ROOT / "integrations/unreal/OpenRecompNativeAotHostCoreV1.cpp",
    "ue_h": ROOT / "integrations/unreal/OpenRecompNativeAotHostV1.h",
    "ue_cpp": ROOT / "integrations/unreal/OpenRecompNativeAotHostV1.cpp",
    "actor_h": ROOT / "integrations/unreal/OpenRecompNativeAotHostActor.h",
    "actor_cpp": ROOT / "integrations/unreal/OpenRecompNativeAotHostActor.cpp",
    "proof_cpp": ROOT / "integrations/unreal/OpenRecompProofActor.cpp",
}


def fail(message: str) -> int:
    print(f"OPENRECOMP_UNREAL_NATIVE_AOT_SOURCE_V1=FAIL: {message}", file=sys.stderr)
    return 2


def main() -> int:
    try:
        text = {name: path.read_text(encoding="utf-8") for name, path in FILES.items()}
    except OSError as exc:
        return fail(str(exc))

    required_core = (
        "OPENRECOMP_NATIVE_AOT_ABI_V1",
        "OPENRECOMP_NATIVE_AOT_API_V1_SIZE",
        "OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS",
        "openrecomp_unreal_native_aot_execute_v1",
    )
    for token in required_core:
        if token not in text["core_cpp"] and token not in text["core_h"]:
            return fail(f"host core missing required token {token}")

    required_ue = (
        "FPlatformProcess::GetDllHandle",
        "FPlatformProcess::GetDllExport",
        "openrecomp_native_aot_query",
        "openrecomp_unreal_native_aot_execute_v1",
    )
    for token in required_ue:
        if token not in text["ue_cpp"]:
            return fail(f"Unreal loader missing required token {token}")

    forbidden_legacy = (
        "openrecomp_run",
        "openrecomp_set_host_callback",
        "openrecomp_observed_state",
        "openrecomp_operations",
    )
    combined_new = "\n".join(
        text[name]
        for name in ("core_h", "core_cpp", "ue_h", "ue_cpp", "actor_h", "actor_cpp")
    )
    for token in forbidden_legacy:
        if token in combined_new:
            return fail(f"new Unreal host references forbidden legacy symbol {token}")

    actor_required = (
        "OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 PASS",
        "e07.rv32i.fixture-full.ir-v1",
        "122010428",
        "3866",
        "host_graphics",
        "host_audio",
        "host_input",
        "host_system",
    )
    for token in actor_required:
        if token not in text["actor_cpp"]:
            return fail(f"Native AOT proof actor missing {token}")

    for marker in (
        "OPENRECOMP_GATE_B PASS",
        "OPENRECOMP_DEMO PASS",
    ):
        if marker not in text["proof_cpp"]:
            return fail(f"existing Unreal proof marker missing: {marker}")

    print("OPENRECOMP_UNREAL_NATIVE_AOT_SOURCE_V1_QUERY_ONLY=PASS")
    print("OPENRECOMP_UNREAL_NATIVE_AOT_SOURCE_V1_GATE_B_PRESERVED=PASS")
    print("OPENRECOMP_UNREAL_NATIVE_AOT_SOURCE_V1=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
