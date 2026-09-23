# Platforms and Architecture Boundaries

OpenRecomp separates the **guest architecture being analysed/recompiled** from the **host platform executing the resulting module**. This distinction is important: evidence for one guest or host does not automatically establish another.

## Guest-side work

### RV32I

The repository contains the strongest published bounded proof path for RV32I fixtures, including hardened validation, normalized IR, reference execution, native AOT generation and reproducibility gates.

This is not a claim of arbitrary RISC-V executable compatibility.

### MIPS32

OpenRecomp contains bounded MIPS32 validation and continuing expansion work. MIPS32 is particularly relevant to current legacy-platform research, but general MIPS32 executable compatibility remains unproven.

### PlayStation-era / PS1

Current research applies the MIPS-family and runtime work to bounded PlayStation-era compatibility/static-recompilation investigation using legally obtained software.

**General PS1 compatibility: NOT PROVEN.**

**General commercial-title playability: NOT PROVEN.**

No Sony or PlayStation affiliation or endorsement is implied.

## Host-side work

### Linux x86-64

The repository provides a clean external-reviewer reproducibility path for the documented open-core fixtures, including native AOT validation using the supported toolchains described by the relevant evidence documents.

### Windows x64

Native AOT ABI and host integration have bounded Windows x64 evidence, including MSVC/clang-cl paths described in the public documentation.

### WebAssembly

WebAssembly is used in bounded equivalence/validation work. It should not be interpreted as evidence that every guest path is deployable as a production WebAssembly application.

### Unreal Engine

Unreal integration is an optional consumer of OpenRecomp's native-module interface. It demonstrates that the host boundary can be integrated into a larger engine; Unreal is not required by the architecture-neutral core.

### Other hosts

macOS, Windows ARM64, Windows x86 and other host/platform combinations should be treated as **CANDIDATE** or **NOT PROVEN** unless a specific current gate establishes the relevant ABI/runtime claim.

## Portability rule

A useful way to read OpenRecomp results is:

> guest semantics proof + module/ABI proof + host-runtime proof = evidence for that exact bounded path

Removing or changing any component requires new evidence rather than assuming portability.

See [TECHNICAL_STATUS.md](TECHNICAL_STATUS.md), [NATIVE_AOT_ABI_V1.md](NATIVE_AOT_ABI_V1.md) and [AOT_WINDOWS_PORTABILITY_V1.md](AOT_WINDOWS_PORTABILITY_V1.md).