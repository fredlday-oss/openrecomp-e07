#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "integrations" / "unreal" / "Plugins" / "OpenRecompRuntime"
SOURCE = PLUGIN / "Source" / "OpenRecompRuntime"
PUBLIC = SOURCE / "Public"
PRIVATE = SOURCE / "Private"


def fail(message: str) -> None:
    raise SystemExit(f"OPENRECOMP_UNREAL_PLUGIN_V1_SOURCE_CONTRACT=FAIL: {message}")


def require(path: Path) -> str:
    if not path.is_file():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require_tokens(text: str, path: Path, tokens: list[str]) -> None:
    for token in tokens:
        if token not in text:
            fail(f"{path.relative_to(ROOT)} missing token: {token}")


def main() -> int:
    descriptor_path = PLUGIN / "OpenRecompRuntime.uplugin"
    descriptor = json.loads(require(descriptor_path))
    if descriptor.get("VersionName") != "1.0.0":
        fail("plugin VersionName must be 1.0.0")
    if descriptor.get("CanContainContent") is not False:
        fail("plugin must remain code-only")
    modules = descriptor.get("Modules")
    if not isinstance(modules, list) or len(modules) != 1:
        fail("plugin must expose exactly one runtime module")
    module = modules[0]
    if module.get("Name") != "OpenRecompRuntime" or module.get("Type") != "Runtime":
        fail("OpenRecompRuntime runtime module descriptor mismatch")

    build_path = SOURCE / "OpenRecompRuntime.Build.cs"
    build = require(build_path)
    require_tokens(
        build,
        build_path,
        [
            "class OpenRecompRuntime : ModuleRules",
            '"Core"',
            '"CoreUObject"',
            '"Engine"',
            '"Projects"',
            "RuntimeDependencies.Add",
        ],
    )

    canonical_abi = ROOT / "include" / "openrecomp" / "native_aot_abi_v1.h"
    plugin_abi = PUBLIC / "openrecomp" / "native_aot_abi_v1.h"
    canonical_bytes = canonical_abi.read_bytes()
    plugin_bytes = plugin_abi.read_bytes() if plugin_abi.is_file() else b""
    if canonical_bytes != plugin_bytes:
        fail("plugin Native AOT ABI V1 header is not byte-identical to canonical header")
    abi_sha = hashlib.sha256(plugin_bytes).hexdigest()

    native_header_path = PUBLIC / "OpenRecompNativeModuleV1.h"
    native_cpp_path = PRIVATE / "OpenRecompNativeModuleV1.cpp"
    native_header = require(native_header_path)
    native_cpp = require(native_cpp_path)
    require_tokens(
        native_header,
        native_header_path,
        [
            "FOpenRecompNativeModuleV1",
            "FOpenRecompHostCallHandlerV1",
            "bool Load(const FString& ModulePath)",
            "bool Run()",
            "bool ReadMemory",
            "bool GetStateValue",
        ],
    )
    require_tokens(
        native_cpp,
        native_cpp_path,
        [
            "FPlatformProcess::GetDllHandle",
            "FPlatformProcess::GetDllExport",
            'TEXT("openrecomp_native_aot_query")',
            "OPENRECOMP_NATIVE_AOT_ABI_V1",
            "OPENRECOMP_NATIVE_AOT_API_V1_SIZE",
            "OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS",
            "OPENRECOMP_NATIVE_AOT_CAP_MEMORY_READ",
            "OPENRECOMP_NATIVE_AOT_CAP_STATE_INSPECTION",
            "Api->set_host(nullptr)",
        ],
    )

    subsystem_header_path = PUBLIC / "OpenRecompSubsystem.h"
    subsystem_cpp_path = PRIVATE / "OpenRecompSubsystem.cpp"
    subsystem_header = require(subsystem_header_path)
    subsystem_cpp = require(subsystem_cpp_path)
    require_tokens(
        subsystem_header,
        subsystem_header_path,
        [
            "public UGameInstanceSubsystem",
            "LoadNativeModule",
            "UnloadNativeModule",
            "RunNativeModule",
            "ReadMemory",
            "SetHostCallHandler",
            "GetMetadataV1",
            "GetLastExecutionV1",
        ],
    )
    require_tokens(subsystem_cpp, subsystem_cpp_path, ["NativeModule.Load", "NativeModule.Run"])

    example_header_path = PUBLIC / "OpenRecompPluginExampleActor.h"
    example_cpp_path = PRIVATE / "OpenRecompPluginExampleActor.cpp"
    example_header = require(example_header_path)
    example_cpp = require(example_cpp_path)
    require_tokens(example_header, example_header_path, ["AOpenRecompPluginExampleActor", "RunPluginProof"])
    require_tokens(
        example_cpp,
        example_cpp_path,
        [
            "GetSubsystem<UOpenRecompSubsystem>()",
            "SetHostCallHandler",
            "LoadNativeModule",
            "RunNativeModule",
            "OPENRECOMP_UNREAL_PLUGIN_V1 PASS",
            "122010428u",
            "ExpectedObservedState = 48u",
            "ExpectedOperations = 3866u",
        ],
    )
    if "FPlatformProcess::" in example_cpp or "openrecomp_native_aot_query" in example_cpp:
        fail("example actor bypasses the reusable subsystem/native-module layer")

    legacy_symbols = [
        "openrecomp_run",
        "openrecomp_observed_state",
        "openrecomp_function_return",
        "openrecomp_operations",
        "openrecomp_memory_read",
    ]
    for path in SOURCE.rglob("*"):
        if not path.is_file() or path.suffix not in {".h", ".cpp", ".cs"}:
            continue
        text = path.read_text(encoding="utf-8")
        for symbol in legacy_symbols:
            if symbol in text:
                fail(f"legacy implementation symbol referenced by plugin: {path.relative_to(ROOT)}: {symbol}")

    query_mentions = 0
    for path in SOURCE.rglob("*"):
        if path.is_file() and path.suffix in {".h", ".cpp"}:
            query_mentions += path.read_text(encoding="utf-8").count("openrecomp_native_aot_query")
    if query_mentions != 2:
        fail(f"unexpected query-symbol surface in plugin sources: mentions={query_mentions}, expected=2")

    print(f"OPENRECOMP_UNREAL_PLUGIN_V1_ABI_SHA256={abi_sha}")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_DESCRIPTOR=PASS")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_ABI_COPY=PASS")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_SUBSYSTEM=PASS")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_EXAMPLE_CONSUMER=PASS")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_LEGACY_SYMBOL_REJECTION=PASS")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_SOURCE_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
