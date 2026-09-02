#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "integrations" / "unreal" / "Plugins" / "OpenRecompRuntime"
SOURCE = PLUGIN / "Source" / "OpenRecompRuntime"
PRIVATE = SOURCE / "Private"
PUBLIC = SOURCE / "Public"
SUPPORT = ROOT / "integrations" / "unreal" / "packaged-build-v1"


def fail(message: str) -> None:
    raise SystemExit(f"OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_SOURCE_CONTRACT=FAIL: {message}")


def require(path: Path) -> str:
    if not path.is_file():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require_tokens(text: str, path: Path, tokens: list[str]) -> None:
    for token in tokens:
        if token not in text:
            fail(f"{path.relative_to(ROOT)} missing token: {token}")


def main() -> int:
    build_path = SOURCE / "OpenRecompRuntime.Build.cs"
    build = require(build_path)
    require_tokens(
        build,
        build_path,
        [
            "RuntimeDependencies.Add(SyntheticModule, StagedFileType.NonUFS)",
            '"Binaries"',
            '"Win64"',
            '"openrecomp-e07-rv32i.dll"',
        ],
    )

    subsystem_header_path = PUBLIC / "OpenRecompSubsystem.h"
    subsystem_cpp_path = PRIVATE / "OpenRecompSubsystem.cpp"
    subsystem_header = require(subsystem_header_path)
    subsystem_cpp = require(subsystem_cpp_path)
    require_tokens(
        subsystem_header,
        subsystem_header_path,
        ["Initialize(FSubsystemCollectionBase& Collection)", "Deinitialize()"],
    )
    require_tokens(
        subsystem_cpp,
        subsystem_cpp_path,
        [
            'FParse::Param(FCommandLine::Get(), TEXT("OpenRecompPackagedProof"))',
            "RunOpenRecompPackagedProofV1(*this)",
        ],
    )

    proof_header_path = PRIVATE / "OpenRecompPackagedProofV1.h"
    proof_cpp_path = PRIVATE / "OpenRecompPackagedProofV1.cpp"
    proof_header = require(proof_header_path)
    proof_cpp = require(proof_cpp_path)
    require_tokens(proof_header, proof_header_path, ["RunOpenRecompPackagedProofV1"])
    require_tokens(
        proof_cpp,
        proof_cpp_path,
        [
            "SetHostCallHandler",
            "LoadNativeModule",
            "RunNativeModule",
            "UnloadNativeModule",
            "ExpectedChecksum = 122010428u",
            "ExpectedObservedState = 48u",
            "ExpectedOperations = 3866u",
            "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1 PASS",
            'TEXT("Binaries/Win64/openrecomp-e07-rv32i.dll")',
        ],
    )
    if "FPlatformProcess::GetDllExport" in proof_cpp or "openrecomp_native_aot_query" in proof_cpp:
        fail("packaged proof bypasses the reusable subsystem/native-module layer")

    required_support = [
        "INSTALL_FROM_HANDOFF.ps1",
        "RUN_PACKAGE.ps1",
        "RUN_PACKAGED_PROOF.ps1",
        "COLLECT_PACKAGED_BUILD_V1_EVIDENCE.ps1",
        "README_RUNTIME_GATE.md",
        "ANTIGRAVITY_PROMPT.md",
    ]
    for name in required_support:
        require(SUPPORT / name)

    package_script = require(SUPPORT / "RUN_PACKAGE.ps1")
    require_tokens(
        package_script,
        SUPPORT / "RUN_PACKAGE.ps1",
        [
            "BuildCookRun",
            "-platform=Win64",
            "-clientconfig=Development",
            "-cook",
            "-stage",
            "-pak",
            "-package",
            "openrecomp-e07-rv32i.dll",
            "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_PACKAGE=PASS",
        ],
    )

    runner = require(SUPPORT / "RUN_PACKAGED_PROOF.ps1")
    require_tokens(
        runner,
        SUPPORT / "RUN_PACKAGED_PROOF.ps1",
        [
            "-OpenRecompPackagedProof",
            "-stdout",
            "-FullStdOutLogOutput",
            "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1 PASS",
            "COLLECT_PACKAGED_BUILD_V1_EVIDENCE.ps1",
        ],
    )

    collector = require(SUPPORT / "COLLECT_PACKAGED_BUILD_V1_EVIDENCE.ps1")
    require_tokens(
        collector,
        SUPPORT / "COLLECT_PACKAGED_BUILD_V1_EVIDENCE.ps1",
        [
            "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1 PASS",
            "AUTH_PASSWORD",
            "AUTH_LOGIN",
            "exchangecode",
            "epicusername",
            "epicuserid",
            "loginid",
        ],
    )

    print("OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_NONUFS_STAGING=PASS")
    print("OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_COMMANDLINE_ENTRY=PASS")
    print("OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_SUBSYSTEM_LAYERING=PASS")
    print("OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_HANDOFF_SCRIPTS=PASS")
    print("OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_SOURCE_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
