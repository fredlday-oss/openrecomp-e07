# OpenRecomp

OpenRecomp is an open-source, architecture-neutral static recompilation framework with deterministic validation and modern host integration, including native, WebAssembly and Unreal Engine.

The project separates binary analysis, a versioned intermediate representation (IR), executable module packaging, translation, explicit host runtime services and host integration so the same core infrastructure can be reused across architectures and projects rather than tied to a single game or executable.

## Current status

| Area | Status |
| --- | --- |
| E07 RV32I synthetic fixture | **PROVEN** |
| Deterministic reference/translated equivalence | **PASS** |
| Native host execution | **PASS** |
| WebAssembly host execution | **PASS** |
| Normalized OpenRecomp IR V1 specification | **FROZEN-FOR-IMPLEMENTATION** |
| RV32I -> normalized IR V1 bridge | **PASS** — E07 equivalence |
| Core API V1 reference module/runtime | **PASS** — E07 equivalence |
| MIPS32 synthetic vertical slice | **PASS** — IR V1/Core API equivalence |
| Cross-architecture IR/Module/Core boundary | **PASS** — bounded RV32I + MIPS32 synthetic validation |
| Portable C AOT backend V1 | **PASS** — bounded hardened RV32I + MIPS32 equivalence |
| GCC/Clang AOT `-Werror` gate | **PASS** — current dual-architecture fixtures + hardening corpus |
| Core API/AOT deterministic fault equivalence | **PASS** — 9 bounded fault classes |
| GCC/Clang ASan + UBSan AOT smoke | **PASS** — Linux little/big-endian hardening fixtures |
| Native AOT ABI V1 contract | **FROZEN-FOR-PORTABILITY-TESTING** |
| Native AOT ABI V1 Linux GCC/Clang | **PASS** — RV32I + bounded MIPS32 |
| Native AOT ABI V1 Windows x64 MSVC/clang-cl | **PASS** — exact Core/Linux parity |
| Native AOT ABI V1 public symbol surface | **PASS** — single versioned query entry point |
| Unreal Native AOT host core | **PASS** — four-way MSVC/clang-cl host/module matrix |
| Unreal Native AOT host V1 UE5.8 runtime | **PROVEN-RUNTIME** — RV32I AOT module through frozen ABI V1 |
| General MIPS32 coverage | **CANDIDATE** — bounded subset only |
| macOS / Windows ARM64 / Windows x86 ABI parity | **CANDIDATE** |
| Release-quality production AOT compiler/plugin pipeline | **CANDIDATE** |
| Unreal Engine 5.8 Gate B runtime | **PROVEN-RUNTIME** |
| Unreal visual replay | **PASS** |

The hardened E07 V1.1 fixture remains the first proven architecture path and validation harness. It is a proof component of the broader OpenRecomp project, not the total intended scope.

The normalized IR V1, Module Image V1 and Core API V1 boundaries have now been exercised by two materially different clean synthetic guest workloads. A single portable C AOT backend consumes both normalized workloads and reproduces their Core API results after native compilation. The backend is warning-clean under the project compiler gates, its deterministic failure behavior is cross-checked against the reference executor, and Native AOT ABI V1 crosses both Linux GCC/Clang and Windows x64 MSVC/clang-cl for the same bounded workloads. UE5.8 now also consumes that frozen Windows x64 ABI in a separate execution-backed Native AOT runtime proof for the E07 RV32I module. Broader MIPS32 coverage, additional platforms/deployment modes and a release-quality compiler/plugin pipeline remain separately gated.

## Architecture

```text
Guest binary / clean machine-code fixture
    ↓
Binary analysis / architecture frontend
    ↓
Normalized versioned OpenRecomp IR
    ↓
Module Image V1
    ↓
    ├── Core API V1 reference executor
    └── Portable C AOT backend V1
             ↓
       native AOT module
             ↓
       Native AOT ABI V1
             ↓
Explicit host runtime services
    ↓
Linux / Windows x64 / WebAssembly / Unreal Engine host paths
```

OpenRecomp's long-term objective is reusable infrastructure for preservation, interoperability, research, tooling and legally clean static recompilation projects.

## Normalized IR V1

The frozen normalized contract is documented in [`docs/IR_SPEC_V1.md`](docs/IR_SPEC_V1.md). Its machine schema is [`schema/openrecomp-ir-v1.schema.json`](schema/openrecomp-ir-v1.schema.json).

Validate the supplied example with:

```bash
python3 tools/validate_ir_v1.py examples/ir-v1/minimal.json
python3 tools/test_ir_v1.py
```

The RV32I bridge normalizes the current proven E07 workload into V1 and independently reproduces:

```text
IR_V1_BRIDGE_CHECKSUM=122010428
IR_V1_BRIDGE_RETURN_A0=48
OPENRECOMP_RV32I_IR_V1_EQUIVALENCE=PASS checksum=122010428
```

See [`docs/RV32I_IR_V1_BRIDGE.md`](docs/RV32I_IR_V1_BRIDGE.md).

## Core API V1

[`docs/CORE_API_V1.md`](docs/CORE_API_V1.md) defines the first reusable reference module/runtime API around normalized IR V1.

The public Python reference surface includes `ModuleImage`, `GuestState`, `GuestMemory`, `HostBinding`, `CallbackHostBinding`, `ReferenceExecutor` and `ExecutionResult`. Executable packaging is defined separately from the IR by [`schema/openrecomp-module-v1.schema.json`](schema/openrecomp-module-v1.schema.json).

For the E07 fixture, Module Image V1 packaging is deterministic and the generic Core API reference executor independently reaches:

```text
CORE_API_V1_CHECKSUM=122010428
CORE_API_V1_RETURN_A0=48
CORE_API_V1_OPERATIONS=3866
OPENRECOMP_CORE_API_V1_EQUIVALENCE=PASS checksum=122010428
```

## MIPS32 vertical slice

The first implemented second-guest path is documented in [`docs/MIPS32_VERTICAL_SLICE_V1.md`](docs/MIPS32_VERTICAL_SLICE_V1.md).

A clean synthetic little-endian MIPS32 machine-word fixture exercises arithmetic, signed/unsigned comparison, branches, aligned loads/stores, direct call/return, direct jumps and seven architectural delay slots. A bounded MIPS32 frontend lowers those guest semantics into the existing IR V1 contract; the result is packaged with the existing Module Image V1 and executed by the same architecture-neutral Core API V1 reference executor.

An independent machine-code reference path and the Core API path agree on the complete normalized register state, observable memory and deterministic checksum:

```text
MIPS32_REFERENCE_V0=31
MIPS32_REFERENCE_CHECKSUM=1950232098
MIPS32_REFERENCE_DELAY_SLOTS=7

MIPS32_CORE_API_V0=31
MIPS32_CORE_API_CHECKSUM=1950232098
MIPS32_CORE_API_OPERATIONS=100

OPENRECOMP_MIPS32_VERTICAL_SLICE_V1=PASS checksum=1950232098
```

This is a **bounded vertical-slice PASS**, not a claim that arbitrary MIPS32 executables or the full ISA/ABI are supported.

## Portable C AOT backend V1

[`docs/AOT_TRANSLATOR_V1.md`](docs/AOT_TRANSLATOR_V1.md) documents the first common ahead-of-time backend for normalized IR V1. [`docs/AOT_HARDENING_V1.md`](docs/AOT_HARDENING_V1.md) documents its first dedicated compiler-quality hardening gate.

The backend consumes validated IR V1 + Module Image V1 and deterministically emits portable C. The same normalized workloads are compiled into independent native execution forms and required to equal the Core API reference result exactly.

```text
AOT_E07_CHECKSUM=122010428
AOT_E07_RETURN_A0=48
AOT_E07_OPERATIONS=3866

AOT_MIPS32_V0=31
AOT_MIPS32_CHECKSUM=1950232098
AOT_MIPS32_OPERATIONS=100

OPENRECOMP_IR_V1_AOT_RV32I=PASS
OPENRECOMP_IR_V1_AOT_MIPS32=PASS
OPENRECOMP_IR_V1_AOT_DUAL_ARCH=PASS
```

The hardening gate additionally requires warning-clean compilation, deterministic Core API/AOT failure-category agreement for nine runtime fault cases, and ASan/UBSan-clean execution of little- and big-endian positive hardening fixtures under GCC and Clang:

```text
AOT_HARDENING_POSITIVE=2147483672
AOT_HARDENING_FAULT_CASES=9
OPENRECOMP_AOT_HARDENING_WARNING_CLEAN=PASS
OPENRECOMP_AOT_HARDENING_FAULT_EQUIVALENCE=PASS
OPENRECOMP_AOT_HARDENING_GCC_SANITIZERS=PASS
OPENRECOMP_AOT_HARDENING_CLANG_SANITIZERS=PASS
OPENRECOMP_AOT_HARDENING_V1=PASS
```

This establishes a **bounded hardened dual-architecture AOT PASS** for the current synthetic workloads and hardening corpus. It does not claim arbitrary guest binaries, full platform/compiler portability or a release-quality optimizing compiler pipeline.

## Native AOT ABI V1

[`docs/NATIVE_AOT_ABI_V1.md`](docs/NATIVE_AOT_ABI_V1.md) defines the first versioned host-facing binary interface for compiled OpenRecomp modules. The public C contract is [`include/openrecomp/native_aot_abi_v1.h`](include/openrecomp/native_aot_abi_v1.h).

A finished V1 proof module exposes one stable OpenRecomp symbol:

```text
openrecomp_native_aot_query
```

The query returns a fixed-width function table containing version/size information, capability flags, module/provenance metadata, host binding, execution, state/memory inspection and deterministic error access. Unsupported versions and incorrect structure sizes fail closed.

Linux GCC/Clang and Windows x64 MSVC/clang-cl validate the same frozen public V1 surface for the current RV32I and bounded MIPS32 workloads. The V1 header layout was not changed for Windows.

```text
OPENRECOMP_NATIVE_AOT_ABI_V1_QUERY=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_VERSION_REJECTION=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_SIZE_REJECTION=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_METADATA=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_HOST_NEGOTIATION=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_PRIVATE_SURFACE=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_LOADER=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_DUAL_ARCH=PASS
```

The V1 layout remains **frozen for portability testing**. Incompatible layout/signature changes require a new ABI version rather than silently mutating V1.

## Windows x64 AOT portability

[`docs/AOT_WINDOWS_PORTABILITY_V1.md`](docs/AOT_WINDOWS_PORTABILITY_V1.md) records the first cross-OS native AOT proof.

Windows x64 regenerates the portable C and ABI adapters, compiles both guest workloads under MSVC and clang-cl with warnings as errors, verifies the fixed x64 ABI layout (`host=24` bytes, `api=168` bytes), requires the DLL OpenRecomp export set to contain only `openrecomp_native_aot_query`, and compares both Windows results exactly with the Linux-produced Core API references.

```text
OPENRECOMP_AOT_WINDOWS_CODEGEN_DETERMINISTIC=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_WINDOWS_EXPORT_SURFACE=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_WINDOWS_NEGOTIATION=PASS
OPENRECOMP_AOT_WINDOWS_RV32I=PASS
OPENRECOMP_AOT_WINDOWS_MIPS32=PASS
OPENRECOMP_AOT_WINDOWS_MSVC_CLANGCL_PARITY=PASS
OPENRECOMP_AOT_WINDOWS_LINUX_REFERENCE_PARITY=PASS
OPENRECOMP_AOT_WINDOWS_PORTABILITY_V1=PASS
```

The first Windows run also exposed a real byte-integrity problem caused by CRLF checkout conversion of the hashed host contract. `.gitattributes` pins proof/source text to LF; the hash check itself remains unchanged and fail-closed.

## Unreal Engine interoperability

OpenRecomp has two distinct UE5.8 runtime proof paths.

The original authoritative Gate B proof reaches:

```text
OPENRECOMP_GATE_B PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

A separate visual replay reaches:

```text
OPENRECOMP_DEMO PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

The presentation replay does not replace the authoritative runtime validation.

The newer [`docs/UNREAL_NATIVE_AOT_HOST_V1.md`](docs/UNREAL_NATIVE_AOT_HOST_V1.md) path connects the actual normalized/AOT architecture to UE5.8. The engine loads the CI-built synthetic RV32I DLL through `FPlatformProcess`, resolves only `openrecomp_native_aot_query`, negotiates the frozen Native AOT ABI V1, binds deterministic host callbacks and reproduces the established AOT result:

```text
OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

Status: **PROVEN-RUNTIME — bounded UE5.8 Windows x64 Native AOT host validation**.

The installed ABI header, six Native AOT host source files and synthetic RV32I DLL were verified byte-for-byte against the CI handoff by SHA-256 before promotion. The original Gate B source and frozen ABI header remain unchanged.

See [`integrations/unreal/README.md`](integrations/unreal/README.md), [`evidence/UNREAL_GATE_B_PUBLIC_SAFE.txt`](evidence/UNREAL_GATE_B_PUBLIC_SAFE.txt) and [`evidence/UNREAL_NATIVE_AOT_HOST_V1_PUBLIC_SAFE.txt`](evidence/UNREAL_NATIVE_AOT_HOST_V1_PUBLIC_SAFE.txt).

## Hardened E07 proof

The E07 V1.1 proof includes machine-enforced IR/schema checks, translator-consumed host contracts, checked guest memory, deterministic translation, native/WebAssembly parity, golden validation and adversarial rejection coverage.

Run:

```bash
./RUN.sh
```

A successful E07 V1.1 run ends with:

```text
PASS: E07 V1.1 HARDENED END-TO-END
```

See the existing [`evidence/`](evidence/) directory for detailed proof artifacts.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/IR_SPEC_V1.md`](docs/IR_SPEC_V1.md)
- [`docs/RV32I_IR_V1_BRIDGE.md`](docs/RV32I_IR_V1_BRIDGE.md)
- [`docs/CORE_API_V1.md`](docs/CORE_API_V1.md)
- [`docs/MIPS32_VERTICAL_SLICE_V1.md`](docs/MIPS32_VERTICAL_SLICE_V1.md)
- [`docs/AOT_TRANSLATOR_V1.md`](docs/AOT_TRANSLATOR_V1.md)
- [`docs/AOT_HARDENING_V1.md`](docs/AOT_HARDENING_V1.md)
- [`docs/NATIVE_AOT_ABI_V1.md`](docs/NATIVE_AOT_ABI_V1.md)
- [`docs/AOT_WINDOWS_PORTABILITY_V1.md`](docs/AOT_WINDOWS_PORTABILITY_V1.md)
- [`docs/UNREAL_NATIVE_AOT_HOST_V1.md`](docs/UNREAL_NATIVE_AOT_HOST_V1.md)
- [`docs/PROOF_STATUS.md`](docs/PROOF_STATUS.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/BUILDING.md`](docs/BUILDING.md)
- [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md)
- [`integrations/unreal/README.md`](integrations/unreal/README.md)
- [`DEPENDENCIES.md`](DEPENDENCIES.md)

## Contributing and security

See [`CONTRIBUTING.md`](CONTRIBUTING.md) before proposing code or architecture changes. Security-sensitive reports should follow [`SECURITY.md`](SECURITY.md). Significant project changes are tracked in [`CHANGELOG.md`](CHANGELOG.md).

## Rights firewall

The public repository uses original synthetic source and standard toolchain outputs only. It does **not** contain commercial game binaries/assets, console BIOS/firmware or keys, proprietary SDK material or proprietary console executable content.

## License

OpenRecomp E07 is distributed under the Apache License, Version 2.0. See [`LICENSE`](LICENSE). Third-party build/runtime dependency boundaries are documented in [`DEPENDENCIES.md`](DEPENDENCIES.md).
