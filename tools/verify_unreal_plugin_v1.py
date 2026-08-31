#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "integrations/unreal/OpenRecompRuntime"
MODULE = PLUGIN / "Source/OpenRecompRuntime"


def fail(message: str) -> int:
    print(f"OPENRECOMP_UNREAL_PLUGIN_V1_SOURCE=FAIL: {message}", file=sys.stderr)
    return 2


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require_tokens(text: str, tokens: tuple[str, ...], context: str) -> None:
    missing = [token for token in tokens if token not in text]
    if missing:
        raise ValueError(f"{context} missing: {', '.join(missing)}")


def main() -> int:
    try:
        descriptor_path = PLUGIN / "OpenRecompRuntime.uplugin"
        descriptor = json.loads(read(descriptor_path))
        if descriptor.get("FileVersion") != 3:
            return fail("plugin descriptor FileVersion must be 3")
        if descriptor.get("VersionName") != "1.0.0":
            return fail("plugin VersionName must be 1.0.0")
        if descriptor.get("EnabledByDefault") is not True:
            return fail("plugin must be enabled by default for the V1 handoff")
        modules = descriptor.get("Modules")
        if modules != [
            {
                "Name": "OpenRecompRuntime",
                "Type": "Runtime",
                "LoadingPhase": "Default",
            }
        ]:
            return fail("plugin must expose exactly one Runtime module")

        root_abi = ROOT / "include/openrecomp/native_aot_abi_v1.h"
        plugin_abi = MODULE / "Public/openrecomp/native_aot_abi_v1.h"
        if root_abi.read_bytes() != plugin_abi.read_bytes():
            return fail("vendored plugin Native AOT ABI V1 header differs from frozen root header")

        build_cs = read(MODULE / "OpenRecompRuntime.Build.cs")
        require_tokens(
            build_cs,
            (
                '"Core"',
                '"CoreUObject"',
                '"Engine"',
                '"Projects"',
                "RuntimeDependencies.Add",
                "File.Exists(ProofDll)",
                "openrecomp-e07-rv32i.dll",
            ),
            "Build.cs",
        )

        types_h = read(MODULE / "Public/OpenRecompRuntimeTypes.h")
        host_h = read(MODULE / "Public/OpenRecompHostService.h")
        native_h = read(MODULE / "Public/OpenRecompNativeAotModule.h")
        subsystem_h = read(MODULE / "Public/OpenRecompSubsystem.h")
        native_cpp = read(MODULE / "Private/OpenRecompNativeAotModule.cpp")
        subsystem_cpp = read(MODULE / "Private/OpenRecompSubsystem.cpp")
        validation_cpp = read(MODULE / "Private/OpenRecompE07ValidationHostService.cpp")
        module_cpp = read(MODULE / "Private/OpenRecompRuntimeModule.cpp")

        require_tokens(
            types_h,
            (
                "FOpenRecompModuleInfo",
                "FOpenRecompExecutionResult",
                "EOpenRecompEndianness",
                "BlueprintType",
            ),
            "reflected types",
        )
        require_tokens(
            host_h,
            (
                "UOpenRecompHostService",
                "IOpenRecompHostService",
                "BlueprintNativeEvent",
                "HandleOpenRecompHostCall",
            ),
            "host-service interface",
        )
        require_tokens(
            native_h + native_cpp,
            (
                "FOpenRecompNativeAotModule",
                "openrecomp_native_aot_query",
                "OPENRECOMP_NATIVE_AOT_ABI_V1",
                "OPENRECOMP_NATIVE_AOT_API_V1_SIZE",
                "GetDllHandle",
                "GetDllExport",
                "set_host(nullptr)",
                "GetStateValue",
                "ReadMemory",
                "GetMemorySize",
                "OPENRECOMP_NATIVE_AOT_CAP_STATE_INSPECTION",
                "OPENRECOMP_NATIVE_AOT_CAP_MEMORY_READ",
            ),
            "persistent native module",
        )
        require_tokens(
            subsystem_h + subsystem_cpp,
            (
                "UGameInstanceSubsystem",
                "LoadNativeAotModule",
                "ExecuteLoadedModule",
                "GetStateValue",
                "ReadGuestMemory",
                "GetGuestMemorySize",
                "RegisterHostService",
                "ClearHostService",
                "IOpenRecompHostService::Execute_HandleOpenRecompHostCall",
                "OpenRecompPluginProof",
                "OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_PASS",
            ),
            "runtime subsystem",
        )
        require_tokens(
            validation_cpp,
            (
                "host_graphics",
                "host_audio",
                "host_input",
                "host_system",
                "16777619u",
            ),
            "private synthetic validation host",
        )
        require_tokens(
            module_cpp,
            ("IMPLEMENT_MODULE", "OpenRecompRuntime"),
            "runtime module entry point",
        )

        combined = "\n".join(
            (
                types_h,
                host_h,
                native_h,
                subsystem_h,
                native_cpp,
                subsystem_cpp,
                validation_cpp,
                module_cpp,
            )
        )
        for forbidden in (
            "openrecomp_run",
            "openrecomp_set_host_callback",
            "openrecomp_observed_state",
            "openrecomp_operations",
            "OPENRECOMPHOST_API",
        ):
            if forbidden in combined:
                return fail(f"plugin references forbidden legacy/project-module token: {forbidden}")

        proof_actor = read(ROOT / "integrations/unreal/OpenRecompProofActor.cpp")
        require_tokens(
            proof_actor,
            ("OPENRECOMP_GATE_B PASS", "OPENRECOMP_DEMO PASS"),
            "historical Unreal proof actor",
        )

        wrapper = read(ROOT / "integrations/unreal/RUN_UNREAL_PLUGIN_V1_HANDOFF.ps1")
        packaged_runner = read(ROOT / "integrations/unreal/RUN_UNREAL_PLUGIN_V1_PACKAGED_PROOF.ps1")
        collector = read(ROOT / "integrations/unreal/COLLECT_UNREAL_PLUGIN_V1_EVIDENCE.ps1")

        if "$LASTEXITCODE" in wrapper:
            return fail("handoff wrapper must not read LASTEXITCODE after PowerShell-script invocation")
        require_tokens(
            wrapper,
            (
                "INSTALL_UNREAL_PLUGIN_V1.ps1",
                "RUN_UNREAL_PLUGIN_V1_PACKAGED_PROOF.ps1",
                "OPENRECOMP_UNREAL_PLUGIN_V1_HANDOFF_RUN=COMPLETE",
            ),
            "strict-mode-safe handoff wrapper",
        )
        require_tokens(
            packaged_runner,
            (
                "RuntimeExecutables",
                "Binaries[\\/]Win64",
                "PACKAGED_EXE_CANDIDATES",
                "OPENRECOMP_UNREAL_PLUGIN_V1_RUNTIME_DIAGNOSTIC=READY",
            ),
            "packaged runtime runner",
        )
        require_tokens(
            collector,
            (
                "DiagnosticPattern",
                "PACKAGED_FAIL stage=validate",
                "OPENRECOMP_UNREAL_PLUGIN_V1_PUBLIC_SAFE=DIAGNOSTIC",
            ),
            "public-safe evidence collector",
        )

        tracked = subprocess.check_output(
            ["git", "ls-files", "-z", "integrations/unreal/OpenRecompRuntime"],
            cwd=ROOT,
        ).split(bytes([0]))
        tracked_names = [item.decode("utf-8") for item in tracked if item]
        binary_suffixes = (".dll", ".exe", ".pdb", ".lib", ".exp")
        unexpected = [name for name in tracked_names if name.lower().endswith(binary_suffixes)]
        if unexpected:
            return fail("generated/native binaries are tracked in plugin source: " + ", ".join(unexpected))

    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError, subprocess.CalledProcessError) as exc:
        return fail(str(exc))

    print("OPENRECOMP_UNREAL_PLUGIN_V1_ABI_HEADER_FROZEN=PASS")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_QUERY_ONLY=PASS")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_INSPECTION_SURFACE=PASS")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_HANDOFF_SCRIPTS=PASS")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_GATE_B_PRESERVED=PASS")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_NO_TRACKED_BINARIES=PASS")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_SOURCE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
