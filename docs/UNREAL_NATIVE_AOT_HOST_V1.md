# OpenRecomp Unreal Native AOT Host V1

**Frontier:** `OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1`  
**Implementation status:** **CANDIDATE — Windows host-core CI and UE5.8 runtime gate required**

This frontier connects the frozen Native AOT ABI V1 to the Unreal Engine host path without changing the ABI or replacing the existing Unreal Gate B proof.

## Separation from the existing Unreal proof

`OpenRecompProofActor` remains the authoritative proof for the original Unreal synthetic workload:

```text
OPENRECOMP_GATE_B PASS x=15 y=6 rgba=ff3aa7ff frame=8
OPENRECOMP_DEMO PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

The Native AOT host is a separate proof path using the already-validated E07 RV32I AOT module:

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

The two proof paths must not be conflated. A visual Unreal presentation does not substitute for Native AOT execution, and Native AOT execution does not rewrite the historical Gate B workload.

## Source layout

The reusable host implementation consists of:

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

## Deterministic E07 host callback bridge

The proof actor implements the same bounded host semantics used by the Core API/AOT reference gate:

- `host_graphics`: 4x4 RGB framebuffer with the established channel transforms;
- `host_audio`: 16 deterministic 16-bit samples with step 257;
- `host_input`: fixed script `{4,7,1,9,2,6,3,8}`;
- `host_system`: deterministic bias `7`, no wall clock and no randomness.

The authoritative Native AOT result is:

```text
module=e07.rv32i.fixture-full.ir-v1
architecture=rv32i
host_contract=0.1.1
observed_state=48
operations=3866
checksum=122010428
```

Expected Unreal runtime marker:

```text
OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=rv32i observed_state=48 checksum=122010428 operations=3866
```

## Host-core CI gate

`.github/workflows/unreal-native-aot-host-v1.yml` builds a fresh validated RV32I Module Image on Linux, regenerates its portable C and Native AOT ABI adapter on Windows, and builds AOT DLLs with both MSVC and clang-cl.

The same workflow builds the engine-independent host core/harness with both MSVC and clang-cl and executes the four host/module compiler combinations:

```text
MSVC host     -> MSVC module
MSVC host     -> clang-cl module
clang-cl host -> MSVC module
clang-cl host -> clang-cl module
```

Every case must reject a missing required host, exercise the E07 callback bridge, validate module metadata, and reproduce:

```text
UNREAL_NATIVE_AOT_OBSERVED_STATE=48
UNREAL_NATIVE_AOT_CHECKSUM=122010428
UNREAL_NATIVE_AOT_OPERATIONS=3866
OPENRECOMP_UNREAL_NATIVE_AOT_HOST_CORE_V1=PASS
```

Passing this CI gate proves the exact host core against real Windows Native AOT DLLs. It does **not** by itself prove Unreal Engine compilation or PIE execution.

## Local UE5.8 installation

From a clone of this repository, install the source into an existing `OpenRecompHost` Unreal project module with:

```powershell
powershell -ExecutionPolicy Bypass -File .\integrations\unreal\INSTALL_NATIVE_AOT_HOST_V1.ps1 `
  -UnrealProjectRoot "D:\path\to\OpenRecompHost" `
  -NativeModuleDll "D:\path\to\openrecomp-e07-rv32i.dll"
```

The installer copies the frozen ABI header plus the host-core, Unreal wrapper and proof actor source. It does not modify `OpenRecompProofActor`.

The default runtime module location is:

```text
<ProjectRoot>\Binaries\Win64\openrecomp-e07-rv32i.dll
```

`NativeModulePath` on the proof actor may override that location.

## UE5.8 runtime gate

The runtime proof requires all of the following:

1. `OpenRecompHostEditor Win64 Development` builds successfully with Unreal Engine 5.8;
2. `AOpenRecompNativeAotHostActor` is present in the test level;
3. PIE loads the synthetic Windows x64 AOT DLL through `FPlatformProcess`;
4. only Native AOT ABI V1 query/table dispatch is used;
5. all deterministic E07 host callbacks execute successfully;
6. Unreal observes state `48`, operation count `3866` and checksum `122010428`;
7. the expected `OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 PASS ...` marker appears;
8. the existing Gate B source and proof remain separate and unchanged.

Until that runtime gate is captured, the Unreal integration remains **CANDIDATE**, even if the Windows host-core CI is green.

## Public-safe evidence

Never publish a raw Unreal startup/launcher log. Extract only allow-listed OpenRecomp proof lines:

```powershell
powershell -ExecutionPolicy Bypass -File .\integrations\unreal\COLLECT_NATIVE_AOT_HOST_V1_EVIDENCE.ps1 `
  -UnrealLog "D:\path\to\OpenRecompHost.log"
```

The collector writes only the new Native AOT marker and, when present, the existing Gate B/demo markers. It fails if the Native AOT PASS marker is absent or if an authentication/account marker survives extraction.

## Claim boundary

A completed V1 runtime proof will establish a bounded host integration for:

- Unreal Engine 5.8 on Windows x64;
- the frozen Native AOT ABI V1;
- the current synthetic E07 RV32I AOT module;
- deterministic host callback binding;
- dynamic DLL loading through Unreal's platform abstraction;
- authoritative observable-result parity with the established Core/AOT proof.

It will not establish arbitrary RV32I binaries, general MIPS32 Unreal hosting, packaged-game deployment, macOS Unreal hosting, Windows ARM64, or a release-quality plugin/API surface.
