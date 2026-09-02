# OpenRecomp Runtime — Unreal Plugin V1

`OpenRecompRuntime` is a code-only Unreal Engine runtime plugin that consumes translated modules through the frozen **Native AOT ABI V1** boundary.

The plugin does not implement guest instruction semantics. It dynamically loads a native module, resolves only `openrecomp_native_aot_query`, negotiates exact ABI V1, exposes a `UGameInstanceSubsystem`, dispatches optional host calls supplied by the consumer, and provides bounded state/memory inspection through the ABI table.

## Public runtime surface

`UOpenRecompSubsystem` provides Blueprint-callable module lifecycle and observation helpers:

- `LoadNativeModule`
- `UnloadNativeModule`
- `RunNativeModule`
- `IsNativeModuleLoaded`
- `GetLastError`
- `GetModuleId`
- `GetSourceArchitecture`
- `GetObservedState`
- `GetOperationCount`
- `ReadMemory`

The exact-width C++ surface is exposed through `FOpenRecompNativeModuleV1`, `FOpenRecompModuleMetadataV1`, and `FOpenRecompExecutionResultV1`. C++ consumers can install a `FOpenRecompHostCallHandlerV1` before execution. The Blueprint integer convenience accessors use Unreal's signed `int64`; use the C++ result structs when preserving the full unsigned 64-bit ABI domain matters.

## Example consumer

`AOpenRecompPluginExampleActor` is a clean synthetic example. It obtains `UOpenRecompSubsystem` from the game instance, installs the deterministic E07 host callbacks, loads the synthetic RV32I Native AOT module, executes through the subsystem, and independently validates the established result:

```text
observed_state=48
checksum=122010428
operations=3866
```

A successful real UE runtime execution emits only the bounded marker:

```text
OPENRECOMP_UNREAL_PLUGIN_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

## Module placement

The example actor first uses its editable `NativeModulePath`. When empty, it looks for the synthetic proof DLL at:

```text
<OpenRecompRuntime plugin>/Binaries/Win64/openrecomp-e07-rv32i.dll
```

The repository does not check generated DLLs into source control. CI/local handoff packaging may place the validated synthetic DLL there.

## Contract boundaries

- Native AOT ABI V1 is copied byte-for-byte from `include/openrecomp/native_aot_abi_v1.h` and is checked by CI.
- `openrecomp_native_aot_query` is the only implementation entry point resolved by the plugin.
- Legacy private AOT symbols are rejected by the plugin source-contract test.
- The plugin is a host/integration layer; it does not promote arbitrary RV32I, MIPS32, Unreal, or production-compiler compatibility.
- Hosted CI can validate source/package contracts and the engine-independent Native AOT execution path. A real Unreal Engine compile and runtime/PIE result remains a separate evidence gate.

See `docs/UNREAL_PLUGIN_V1.md` in the repository for validation and handoff details.
