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
| General MIPS32 coverage | **CANDIDATE** — bounded subset only |
| Stable external native-module ABI | **CANDIDATE** |
| Release-quality production AOT compiler pipeline | **CANDIDATE** |
| Unreal Engine 5.8 Gate B runtime | **PROVEN-RUNTIME** |
| Unreal visual replay | **PASS** |

The hardened E07 V1.1 fixture remains the first proven architecture path and validation harness. It is a proof component of the broader OpenRecomp project, not the total intended scope.

The normalized IR V1, Module Image V1 and Core API V1 boundaries have now been exercised by two materially different clean synthetic guest workloads. A single portable C AOT backend also consumes both normalized workloads and reproduces their Core API results after native compilation with GCC and Clang. The backend is now warning-clean under the project `-Werror` gates for those workloads plus a dedicated hardening corpus, and its deterministic failure behavior is cross-checked against the reference executor. RV32I remains the deeper proven architecture path; broader MIPS32 coverage, external ABI stability and a release-quality production compiler pipeline remain separately gated.

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
    └── Portable C AOT backend V1 → native compiled module
    ↓
Explicit host runtime services
    ↓
Native / WebAssembly / Unreal Engine host
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

The backend consumes validated IR V1 + Module Image V1 and deterministically emits portable C. The same generated source is compiled independently by GCC and Clang and loaded as native code. For both current guest workloads, the native AOT result must equal the Core API reference result exactly.

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

The hardening gate additionally requires warning-clean `-Werror` compilation, deterministic Core API/AOT failure-category agreement for nine runtime fault cases, and ASan/UBSan-clean execution of little- and big-endian positive hardening fixtures under both GCC and Clang:

```text
AOT_HARDENING_POSITIVE=2147483672
AOT_HARDENING_FAULT_CASES=9
OPENRECOMP_AOT_HARDENING_WARNING_CLEAN=PASS
OPENRECOMP_AOT_HARDENING_FAULT_EQUIVALENCE=PASS
OPENRECOMP_AOT_HARDENING_GCC_SANITIZERS=PASS
OPENRECOMP_AOT_HARDENING_CLANG_SANITIZERS=PASS
OPENRECOMP_AOT_HARDENING_V1=PASS
```

This establishes a **bounded hardened dual-architecture AOT PASS** for the current synthetic workloads and hardening corpus. It does not claim arbitrary guest binaries, full platform/compiler portability, a frozen third-party ABI or a release-quality optimizing compiler pipeline.

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

## Unreal Engine interoperability

OpenRecomp also has a validated Unreal Engine 5.8 interoperability proof using a legally redistributable synthetic workload.

The authoritative runtime proof reaches:

```text
OPENRECOMP_GATE_B PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

A separate visual replay reaches:

```text
OPENRECOMP_DEMO PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

The presentation replay does not replace the authoritative runtime validation.

See [`integrations/unreal/README.md`](integrations/unreal/README.md) and [`evidence/UNREAL_GATE_B_PUBLIC_SAFE.txt`](evidence/UNREAL_GATE_B_PUBLIC_SAFE.txt).

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/IR_SPEC_V1.md`](docs/IR_SPEC_V1.md)
- [`docs/RV32I_IR_V1_BRIDGE.md`](docs/RV32I_IR_V1_BRIDGE.md)
- [`docs/CORE_API_V1.md`](docs/CORE_API_V1.md)
- [`docs/MIPS32_VERTICAL_SLICE_V1.md`](docs/MIPS32_VERTICAL_SLICE_V1.md)
- [`docs/AOT_TRANSLATOR_V1.md`](docs/AOT_TRANSLATOR_V1.md)
- [`docs/AOT_HARDENING_V1.md`](docs/AOT_HARDENING_V1.md)
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
