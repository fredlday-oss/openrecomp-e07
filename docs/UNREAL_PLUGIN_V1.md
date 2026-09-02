# OpenRecomp Unreal Plugin V1

**Frontier:** `OPENRECOMP_UNREAL_PLUGIN_V1`  
**Implementation status:** **CANDIDATE — source/native CI plus UE5.8 packaged Win64 runtime gate required**

This frontier turns the already-proven Unreal Native AOT host path into a reusable Unreal Engine runtime plugin without changing Native AOT ABI V1, IR V1, Module Image V1 or guest-architecture semantics.

## Boundary

```text
OpenRecomp guest frontend
        ↓
normalized IR V1
        ↓
Module Image V1
        ↓
portable C AOT
        ↓
Native AOT ABI V1 module
        ↓
openrecomp_native_aot_query
        ↓
OpenRecompRuntime plugin
  ├── FOpenRecompNativeAotModule
  ├── UOpenRecompSubsystem
  ├── UOpenRecompHostService
  ├── reflected metadata/results
  └── state + memory inspection
        ↓
Unreal game/project code
```

The existing `OpenRecompProofActor` remains the historical Gate B proof. `OpenRecompNativeAotHostActor` remains the separate V1 Native-AOT proof consumer. Neither actor becomes part of the plugin runtime architecture.

## Plugin layout

```text
integrations/unreal/OpenRecompRuntime/
  OpenRecompRuntime.uplugin
  Source/OpenRecompRuntime/
    OpenRecompRuntime.Build.cs
    Public/
      OpenRecompRuntimeTypes.h
      OpenRecompHostService.h
      OpenRecompNativeAotModule.h
      OpenRecompSubsystem.h
      openrecomp/native_aot_abi_v1.h
    Private/
      OpenRecompRuntimeModule.cpp
      OpenRecompNativeAotModule.cpp
      OpenRecompSubsystem.cpp
      OpenRecompE07ValidationHostService.h/.cpp
```

The vendored ABI header must be byte-identical to `include/openrecomp/native_aot_abi_v1.h`. CI compares the bytes directly.

## C++ module API

`FOpenRecompNativeAotModule` owns a loaded native module for longer than one call. It provides:

- `Load` / `Unload`;
- exact Native AOT ABI V1 discovery and structure/version validation;
- immutable module metadata;
- synchronous execution with an optional V1 host binding;
- state-slot lookup;
- bounded guest-memory reads;
- memory-size inspection.

It resolves only `openrecomp_native_aot_query`. Legacy implementation symbols are not a compatibility path.

## Unreal subsystem API

`UOpenRecompSubsystem` is a `UGameInstanceSubsystem` exposing the reusable runtime to C++ and Blueprint:

```text
LoadNativeAotModule
ExecuteLoadedModule
UnloadNativeAotModule
IsNativeAotModuleLoaded
GetLoadedModuleInfo
GetStateValue
ReadGuestMemory
GetGuestMemorySize
RegisterHostService
ClearHostService
```

V1 execution is synchronous and game-thread-only. Recursive module execution, load/unload while executing, and host replacement while executing are rejected or ignored fail-closed.

## Blueprint/C++ host-service boundary

Objects implement `OpenRecompHostService` and its BlueprintNativeEvent:

```text
HandleOpenRecompHostCall(
    Symbol,
    Arguments,
    OutValue,
    bOutHasValue)
```

The Native AOT ABI carries unsigned 64-bit values. Unreal reflection exposes the same raw bit patterns through `int64`; host implementations interpret them according to their named host contract.

## CI gate

`.github/workflows/unreal-plugin-v1.yml` separates what GitHub Actions can prove from what requires Unreal Engine locally.

CI must:

1. validate the plugin descriptor and source contract;
2. require the vendored ABI header to match the frozen root header byte-for-byte;
3. reject tracked DLL/EXE/PDB/LIB/EXP output in plugin source;
4. rebuild the validated E07 RV32I IR V1 + Module Image V1 input;
5. regenerate portable C and the Native AOT adapter deterministically on Windows;
6. compile real proof DLLs with MSVC and clang-cl using the **plugin's vendored header**;
7. re-execute both DLLs and require checksum `122010428`, return `48` and `3866` operations;
8. exercise the installer against a mock UE project;
9. produce a hash-manifested runtime handoff artifact.

A green CI gate does not by itself prove UHT/UBT compilation or packaged Unreal execution.

## UE5.8 packaged-runtime gate

The local completion gate is stronger than the previous PIE-only integration gate.

The exact CI handoff must be installed into the UE5.8 host project, then:

1. build the Editor target successfully;
2. package a Win64 Development build through `BuildCookRun`;
3. require the validated synthetic DLL to be staged byte-identically;
4. launch the packaged executable with `-OpenRecompPluginProof`;
5. exercise plugin load -> host registration -> Native AOT execution through the normal subsystem API;
6. observe exact normalized module metadata;
7. observe state `48`, function return `48`, operation count `3866`, all expected E07 host-service classes and checksum `122010428`;
8. extract only the allow-listed public-safe result;
9. return a result ZIP that contains no raw Unreal launcher/runtime log.

Expected marker:

```text
OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

Until that marker is captured from the packaged executable, the plugin remains **CANDIDATE**.

## Installation / proof scripts

```text
integrations/unreal/INSTALL_UNREAL_PLUGIN_V1.ps1
integrations/unreal/RUN_UNREAL_PLUGIN_V1_PACKAGED_PROOF.ps1
integrations/unreal/COLLECT_UNREAL_PLUGIN_V1_EVIDENCE.ps1
```

The installer enables the project plugin, copies the supplied synthetic DLL into `Plugins/OpenRecompRuntime/Binaries/Win64`, and writes an SHA-256 install manifest.

The packaged proof runner builds, cooks, packages and runs the application. It verifies that the staged DLL is byte-identical to the installed validated DLL and deletes the raw runtime log after extracting the expected public-safe marker.

## Claim boundary

A completed V1 packaged proof will establish a bounded reusable plugin path for:

- Unreal Engine 5.8;
- Windows x64;
- Native AOT ABI V1;
- the current clean E07 RV32I module;
- C++ persistent module loading;
- Blueprint/C++ subsystem access;
- BlueprintNativeEvent host-service dispatch;
- packaged Win64 DLL staging and execution;
- module metadata plus state/memory inspection APIs.

It will **not** establish arbitrary RV32I binaries, general MIPS32 Unreal hosting, Shipping-configuration certification, macOS/Windows ARM64 Unreal support, asynchronous/threaded execution, hot reload of executing modules, or a final stable third-party plugin API beyond this bounded V1 surface.
