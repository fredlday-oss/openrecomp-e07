# OpenRecompRuntime Unreal plugin

`OpenRecompRuntime` is the reusable Unreal Engine host layer for OpenRecomp Native AOT ABI V1 modules.

The plugin is deliberately separate from the historical `OpenRecompProofActor` and `OpenRecompNativeAotHostActor` evidence actors. Those remain bounded demonstrations; the plugin provides the reusable runtime surface.

## Public API

The Runtime module exposes:

- `FOpenRecompNativeAotModule` for persistent C++ loading, exact ABI V1 negotiation, execution, metadata, state inspection and guest-memory inspection;
- `UOpenRecompSubsystem`, a `UGameInstanceSubsystem` with C++/Blueprint load/execute/inspect operations;
- `UOpenRecompHostService` / `IOpenRecompHostService`, a BlueprintNativeEvent host-call boundary;
- `FOpenRecompModuleInfo` and `FOpenRecompExecutionResult` reflected result types.

The plugin resolves only the stable `openrecomp_native_aot_query` entry point. It has no fallback to the older private generated execution symbols.

## Host services

A host-service object implements `OpenRecompHostService` and handles normalized named calls:

```text
symbol + raw 64-bit arguments
        ↓
HandleOpenRecompHostCall
        ↓
handled / optional 64-bit return value
```

Register the object with `UOpenRecompSubsystem::RegisterHostService` before executing a module that declares `OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS`.

Execution is synchronous and game-thread-only in V1. Reentrant execution and host replacement during execution fail closed.

## Installation

The repository installer copies the self-contained plugin into an existing UE project and stages a supplied Native AOT DLL for the bounded proof:

```powershell
powershell -ExecutionPolicy Bypass -File .\integrations\unreal\INSTALL_UNREAL_PLUGIN_V1.ps1 `
  -UnrealProjectRoot "D:\path\to\OpenRecompHost" `
  -NativeModuleDll "D:\path\to\openrecomp-e07-rv32i.dll"
```

The synthetic proof DLL is intentionally not committed to the repository.

## Packaged validation

`-OpenRecompPluginProof` enables an internal, opt-in validation helper. It is not part of the public runtime API. The helper exercises the public subsystem load/register/execute path against the synthetic E07 RV32I module and exits after emitting either a PASS or FAIL marker.

The expected public-safe packaged result is:

```text
OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

Use `RUN_UNREAL_PLUGIN_V1_PACKAGED_PROOF.ps1` for the UE5.8 Editor-build, BuildCookRun, staged-DLL integrity and packaged-runtime gate.

## Frozen ABI copy

`Source/OpenRecompRuntime/Public/openrecomp/native_aot_abi_v1.h` is a byte-identical vendored copy of the repository's frozen public V1 header. CI rejects any divergence. Incompatible ABI changes require a new ABI version; the plugin does not redefine V1.
