# OpenRecomp Unreal Native AOT Host V1

**Frontier:** `OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1`  
**Status:** **PASS — local UE5.8 Windows x64 runtime evidence; host core reproducible in Windows CI**

This frontier connects the frozen Native AOT ABI V1 to the Unreal Engine host path without changing the ABI or replacing the existing Unreal Gate B proof.

## Evidence provenance

The integration has two distinct evidence layers:

1. **Windows host-core CI — reproducible PASS.** GitHub Actions builds the synthetic RV32I AOT DLL and the engine-independent host core under MSVC and clang-cl, then executes all four host/module compiler combinations.
2. **UE5.8 PIE — local runtime PASS.** A Windows machine with Unreal Engine 5.8 installed built the host integration and executed the same synthetic AOT module in PIE. The installed ABI header, host source and DLL were matched to the CI handoff by SHA-256 before the runtime result was recorded.

Hosted GitHub Actions does not contain Unreal Engine, so the UE5.8 PIE result is intentionally not presented as hosted-CI-reproducible evidence.

## Separation from the existing Unreal proof

`OpenRecompProofActor` remains the independent original Unreal synthetic workload:

```text
OPENRECOMP_GATE_B PASS x=15 y=6 rgba=ff3aa7ff frame=8
OPENRECOMP_DEMO PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

The Native AOT host is a separate path using the already-validated E07 RV32I AOT module:

```text
RV32I IR V1
  -> Module Image V1
  -> portable C AOT
  -> Windows x64 DLL
  -> openrecomp_native_aot_query
  -> Native AOT ABI V1
  -> Unreal host callback bridge
  -> deterministic E07 host state
  -> UE-visible validation result
```

A visual Unreal presentation does not substitute for Native AOT execution, and Native AOT execution does not rewrite the historical Gate B workload.

## Reusable host implementation

The integration consists of:

```text
integrations/unreal/OpenRecompNativeAotHostCoreV1.h
integrations/unreal/OpenRecompNativeAotHostCoreV1.cpp
integrations/unreal/OpenRecompNativeAotHostV1.h
integrations/unreal/OpenRecompNativeAotHostV1.cpp
integrations/unreal/OpenRecompNativeAotHostActor.h
integrations/unreal/OpenRecompNativeAotHostActor.cpp
```

`OpenRecompNativeAotHostCoreV1` has no Unreal dependency. The engine supplies DLL loading and symbol lookup, then hands the resolved `openrecomp_native_aot_query` function to the core. The core performs exact V1 negotiation, host binding, execution, result capture and host unbind. It never falls back to legacy AOT symbols.

`FOpenRecompNativeAotHostV1` is the Unreal-specific loading layer. It uses `FPlatformProcess::GetDllHandle` and `FPlatformProcess::GetDllExport`, resolves only `openrecomp_native_aot_query`, and copies module metadata/results before unloading the DLL.

`AOpenRecompNativeAotHostActor` is the proof consumer. It binds the deterministic E07 host services and validates the known E07 result.

## Deterministic host callback bridge

The proof actor implements the same bounded host semantics used by the Core API/AOT reference gate:

- `host_graphics`: 4x4 RGB framebuffer with the established channel transforms;
- `host_audio`: 16 deterministic 16-bit samples with step 257;
- `host_input`: fixed script `{4,7,1,9,2,6,3,8}`;
- `host_system`: deterministic bias `7`, no wall clock and no randomness.

The expected result is:

```text
module=e07.rv32i.fixture-full.ir-v1
architecture=riscv32-rv32i
host_contract=0.1.1
observed_state=48
operations=3866
checksum=122010428
```

The architecture identifier is the exact normalized IR metadata emitted by the frozen RV32I bridge; `rv32i` is only a human shorthand.

## Windows host-core CI proof

The dedicated workflow builds a fresh validated RV32I Module Image, regenerates its portable C and Native AOT ABI adapter on Windows, builds the AOT DLL with MSVC and clang-cl, and builds the engine-independent host core with both compilers.

All four cross-toolchain combinations pass:

```text
MSVC host     -> MSVC module
MSVC host     -> clang-cl module
clang-cl host -> MSVC module
clang-cl host -> clang-cl module
```

Each case rejects a missing required host, validates exact normalized metadata, exercises all deterministic E07 callback classes, and reproduces:

```text
UNREAL_NATIVE_AOT_SOURCE_ARCH=riscv32-rv32i
UNREAL_NATIVE_AOT_OBSERVED_STATE=48
UNREAL_NATIVE_AOT_CHECKSUM=122010428
UNREAL_NATIVE_AOT_OPERATIONS=3866
OPENRECOMP_UNREAL_NATIVE_AOT_HOST_CORE_V1=PASS
```

This layer is the externally reproducible proof for the Native AOT host core.

## UE5.8 local runtime validation

The host source and CI-built synthetic module were installed into a UE5.8 project and built successfully on Windows x64. PIE then loaded the AOT DLL through Unreal's platform abstraction, negotiated Native AOT ABI V1, exercised the deterministic host callback bridge and produced:

```text
OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

Status: **PASS — local runtime evidence**.

The runtime handoff manifest was compared with the CI handoff: all eight installed proof artifacts matched byte-for-byte by SHA-256, including the frozen ABI header, six Native AOT Unreal host source files and the synthetic RV32I DLL. The existing Gate B source and frozen ABI header were reported unchanged.

Public-safe runtime evidence is committed at:

```text
evidence/UNREAL_NATIVE_AOT_HOST_V1_PUBLIC_SAFE.txt
```

No raw Unreal startup/launcher log is committed or required for the public evidence record.

A future project-controlled self-hosted UE runner, or an equivalent independently reproducible UE environment, would strengthen this from local runtime evidence to a reproducible runtime claim.

## Local installation

Install the source into an existing `OpenRecompHost` project module with:

```powershell
powershell -ExecutionPolicy Bypass -File .\integrations\unreal\INSTALL_NATIVE_AOT_HOST_V1.ps1 `
  -UnrealProjectRoot "D:\path\to\OpenRecompHost" `
  -NativeModuleDll "D:\path\to\openrecomp-e07-rv32i.dll"
```

The default runtime module location is:

```text
<ProjectRoot>\Binaries\Win64\openrecomp-e07-rv32i.dll
```

`NativeModulePath` on the proof actor may override that location.

## Public-safe evidence collection

Never publish a raw Unreal startup/launcher log. Extract only allow-listed OpenRecomp proof lines:

```powershell
powershell -ExecutionPolicy Bypass -File .\integrations\unreal\COLLECT_NATIVE_AOT_HOST_V1_EVIDENCE.ps1 `
  -UnrealLog "D:\path\to\OpenRecompHost.log"
```

The collector writes only the Native AOT marker and, when present, the existing Gate B/demo markers. It fails if the Native AOT PASS marker is absent or if an authentication/account marker survives extraction.

## Claim boundary

The current evidence establishes:

- reproducible Windows x64 Native AOT host-core behavior under MSVC/clang-cl;
- a locally executed UE5.8 Windows x64 integration using the frozen Native AOT ABI V1;
- the current synthetic E07 RV32I AOT module;
- deterministic host callback binding;
- dynamic DLL loading through Unreal's platform abstraction;
- observable-result parity with the established Core/AOT proof;
- byte-identical installation provenance for the tested source/header/DLL set.

It does **not** establish hosted-CI UE5.8 reproducibility, arbitrary RV32I binaries, general MIPS32 Unreal hosting, packaged-game deployment, macOS Unreal hosting, Windows ARM64, or a release-quality plugin/API surface.
