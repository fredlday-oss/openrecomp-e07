# Unreal Plugin V1

`OPENRECOMP_UNREAL_PLUGIN_V1` turns the existing Unreal Native AOT host proof into a reusable code-only Unreal Engine plugin while preserving the frozen Native AOT ABI V1 boundary.

## Architecture

```text
translated Native AOT module
        |
        | openrecomp_native_aot_query
        v
FOpenRecompNativeModuleV1
        |
        v
UOpenRecompSubsystem (UGameInstanceSubsystem)
        |
        +-- module lifecycle
        +-- host-call dispatch
        +-- exact C++ metadata/result access
        +-- Blueprint convenience accessors
        +-- bounded memory/state inspection
        |
        v
AOpenRecompPluginExampleActor
```

The plugin does not decode guest instructions, execute IR, or implement architecture-specific semantics. Those remain in the OpenRecomp frontend/Core/AOT pipeline. Unreal is an optional Native AOT ABI consumer.

## Source layout

The reusable plugin lives at:

```text
integrations/unreal/Plugins/OpenRecompRuntime/
```

Important files:

- `OpenRecompRuntime.uplugin` — code-only runtime plugin descriptor;
- `OpenRecompRuntime.Build.cs` — UE module dependencies and bounded synthetic DLL staging hook;
- `OpenRecompNativeModuleV1.*` — persistent Native AOT ABI V1 loader/session wrapper;
- `OpenRecompSubsystem.*` — reusable game-instance subsystem;
- `OpenRecompPluginExampleActor.*` — synthetic example consumer;
- `Public/openrecomp/native_aot_abi_v1.h` — byte-identical copy of the frozen canonical ABI header.

## V1 API behavior

The native-module wrapper:

1. loads an explicitly supplied DLL path with Unreal's platform process API;
2. resolves only `openrecomp_native_aot_query`;
3. requests exact `OPENRECOMP_NATIVE_AOT_ABI_V1` and exact V1 API structure size;
4. rejects malformed/incomplete metadata or function tables;
5. binds a C++ host-call handler only when supplied;
6. fails closed when a module declares host calls but no handler is installed;
7. executes through the returned ABI function table;
8. unbinds host callbacks after each run;
9. exposes metadata, observed state, function return, operation count, state inspection and memory reads without adding guest-specific host semantics.

`UOpenRecompSubsystem` owns the module wrapper for the game-instance lifetime. The current V1 API is intended for game-thread integration; concurrency/re-entrancy is not a V1 claim.

## Synthetic proof consumer

The included example actor uses the same deterministic E07 host behavior as the prior Unreal Native AOT proof. Its expected observable result is:

```text
module=e07.rv32i.fixture-full.ir-v1
arch=riscv32-rv32i
observed_state=48
checksum=122010428
operations=3866
```

Successful runtime evidence contains the exact marker:

```text
OPENRECOMP_UNREAL_PLUGIN_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

Use `integrations/unreal/COLLECT_PLUGIN_V1_EVIDENCE.ps1` to extract that marker from a local Unreal log. The collector emits only the allow-listed line and rejects selected authentication/account markers. Raw Unreal startup/authentication logs are not public evidence.

## Hosted CI gate

`.github/workflows/unreal-plugin-v1.yml` validates the parts that do not require a licensed Unreal installation:

- plugin descriptor and required source layout;
- exact byte identity of the plugin ABI header with the canonical frozen header;
- subsystem/native-module layering and rejection of legacy private AOT symbols;
- deterministic source package generation;
- generation of the established synthetic RV32I Module Image/portable-C/ABI adapter;
- MSVC build of the synthetic Native AOT DLL;
- engine-independent Windows host-core execution of that DLL;
- deterministic plugin handoff ZIP generation containing the validated synthetic DLL.

This hosted gate does **not** prove Unreal Header Tool/Unreal Build Tool compilation or UE runtime execution.

## Local UE5.8 gate — PASS

A real UE5.8 Windows x64 environment consumed the CI-produced handoff without modifying the plugin source. The returned runtime-result package verified:

```text
OPENRECOMP_UNREAL_PLUGIN_V1_UE58_BUILD=PASS
OPENRECOMP_UNREAL_PLUGIN_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

The returned plugin SHA-256 manifest exactly matched the CI handoff manifest, and the CI plugin files independently verified against that manifest. The result is therefore classified as **PASS — local runtime evidence**: the plugin built under UE5.8 and executed the validated synthetic RV32I Native AOT module in PIE through the frozen ABI V1 boundary.

The public-safe evidence record is [`../integrations/unreal/evidence/OPENRECOMP_UNREAL_PLUGIN_V1_RUNTIME_PUBLIC_SAFE.txt`](../integrations/unreal/evidence/OPENRECOMP_UNREAL_PLUGIN_V1_RUNTIME_PUBLIC_SAFE.txt). It records only the build/result/provenance markers; raw Unreal startup/authentication logs are not tracked.

Because Unreal Engine itself is not available in hosted project CI, this does not promote the plugin to an unqualified hosted-CI runtime proof. A project-controlled self-hosted UE runner remains a future reproducibility improvement.

## Explicit non-claims

This frontier does not establish:

- arbitrary Unreal project compatibility;
- packaged-build/deployment compatibility;
- macOS/Linux Unreal plugin compatibility;
- arbitrary guest-binary support;
- full MIPS32/RV32I support;
- rendering/audio/input APIs beyond the clean synthetic example callbacks;
- a stable Blueprint ABI independent of the underlying Native AOT ABI;
- production/release-quality compiler status.

Packaged-build validation is intentionally a later evidence gate.
