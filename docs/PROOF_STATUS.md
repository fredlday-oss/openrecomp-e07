# OpenRecomp proof status

OpenRecomp uses evidence labels narrowly. The table below distinguishes reproducible project CI from runtime observations that currently require a machine-local environment.

| Component | Status | Evidence / notes |
| --- | --- | --- |
| E07 RV32I synthetic path | **PROVEN** | Hardened E07 V1.1 proof runs from a fresh clone |
| Deterministic translation | **PASS** | Existing E07 evidence |
| Native execution | **PASS** | Existing E07 evidence |
| WebAssembly execution | **PASS** | Existing E07 evidence |
| Golden regression | **PASS** | Existing E07 evidence |
| Normalized IR V1 specification | **FROZEN-FOR-IMPLEMENTATION** | Schema, semantic validator and acceptance/rejection tests |
| RV32I -> normalized IR V1 bridge | **PASS** | Deterministic normalization matches checksum `122010428`, return `a0=48` and host counters |
| Module Image V1 packaging | **PASS** | Repeated packaging is byte-identical; hashes bind IR, host contract and initialized memory |
| Core API V1 reference module/runtime | **PASS** | Generic reference path matches checksum `122010428`, `a0=48`, 3,866 operations and output hashes |
| MIPS32 synthetic vertical slice | **PASS** | Independent machine-code reference and shared IR/Core path match state, memory and checksum `1950232098`; 7 delay slots lowered |
| Cross-architecture IR/Module/Core boundary | **PASS** | Bounded RV32I + MIPS32 synthetic validation through the same normalized contracts |
| Portable C AOT backend V1 | **PASS** | Common backend generates deterministic C for both current guest workloads and reproduces Core API results |
| GCC/Clang AOT behavioral parity | **PASS** | Identical proof-result JSON for current RV32I/MIPS32 fixtures |
| AOT warning-clean compiler gate | **PASS** | Current fixtures/hardening corpus compile with `-Wall -Wextra -Werror` |
| Core API/AOT runtime-fault equivalence | **PASS** | 9 bounded fault classes agree |
| AOT ASan/UBSan smoke | **PASS** | Little/big-endian positive hardening fixtures under GCC and Clang on Linux CI |
| Native AOT ABI V1 contract | **FROZEN-FOR-PORTABILITY-TESTING** | Public fixed-width C header and exact version/size negotiation |
| Native AOT ABI V1 Linux validation | **PASS** | RV32I + bounded MIPS32 under GCC and Clang |
| Native AOT ABI V1 Windows x64 validation | **PASS** | Frozen layout under MSVC + clang-cl `/W4 /WX` |
| Native AOT ABI V1 public symbol surface | **PASS** | `openrecomp_native_aot_query` is the stable OpenRecomp entry point |
| Linux/Windows native AOT observable parity | **PASS** | Windows results equal Linux/Core reference results |
| Cross-platform proof-text byte stability | **PASS** | `.gitattributes` keeps hashed proof/source text LF-stable across Linux/Windows |
| Unreal Native AOT host core | **PASS** | Reproducible Windows CI four-way MSVC/clang-cl host/module matrix; exact V1 negotiation/callback/result checks |
| Unreal Native AOT host V1 UE5.8 runtime | **PASS — local runtime evidence** | UE5.8 Windows x64 PIE loaded the synthetic RV32I AOT DLL and observed state `48`, checksum `122010428`, operations `3866`; installation inputs matched CI handoff by SHA-256, but UE itself is not available in hosted CI |
| Unreal Engine 5.8 build | **PASS — local environment** | Windows UE5.8 Editor build completed outside hosted CI |
| Original Unreal Gate B PIE runtime | **PASS — local runtime evidence** | Public-safe local UE5.8 runtime evidence; independent from visual replay |
| Unreal visual replay | **PASS — local presentation evidence** | Presentation-only evidence, separate from authoritative runtime paths |
| General MIPS32 frontend/ISA coverage | **CANDIDATE** | Current implementation is a bounded little-endian subset |
| macOS / Windows ARM64 / Windows x86 Native AOT ABI parity | **CANDIDATE** | Not covered by current x64 Linux/Windows evidence |
| Release-quality production AOT compiler/plugin pipeline | **CANDIDATE** | Broader platform/optimization/deployment evidence remains outstanding |

## Claim policy

**PROVEN** means the current evidence directly validates the stated path and is reproducible at the stated project scope.

**PASS** means a bounded validation/test completed successfully.

**PROVEN-RUNTIME** is reserved for runtime behavior whose evidence path is reproducible at the stated scope. A machine-local runtime observation that cannot currently be reproduced in project-controlled CI is instead reported as **PASS — local runtime evidence** with its environment/provenance stated explicitly.

**CANDIDATE** means an interface or future direction exists but the implementation has not crossed the required proof gate.

**FROZEN-FOR-IMPLEMENTATION** is a specification state, not a proof state. It means the contract is sufficiently defined and mechanically validated to implement against while broader runtime/generalization claims remain evidence-gated.

**FROZEN-FOR-PORTABILITY-TESTING** means the V1 binary layout and semantics are fixed for cross-platform validation. Incompatible changes must use a new ABI version rather than silently mutating V1.

Automated or AI-generated summaries, code suggestions and review output are not evidence by themselves and cannot upgrade a status. See [`../DEVELOPMENT_PROCESS.md`](../DEVELOPMENT_PROCESS.md).

## Current bounded claim boundaries

The RV32I result remains bounded to the clean E07 synthetic fixture/proven subset. The MIPS32 result remains bounded to the clean little-endian vertical slice covering arithmetic, signed/unsigned comparison, branches, aligned `lw`/`sw`, direct call/return, direct jump and delay-slot lowering.

The cross-architecture PASS means the same normalized IR V1, Module Image V1 and Core API V1 boundaries have been executed with two materially different synthetic guest architectures. It does not establish arbitrary-binary support.

The portable C AOT PASS means the same architecture-neutral backend consumes both normalized workloads and reproduces the existing Core API result after native compilation. AOT hardening adds warning-clean compilation, deterministic fault-category equivalence and sanitizer smoke coverage without expanding the guest-support claim.

Native AOT ABI V1 freezes a public native-module boundary. Linux GCC/Clang and Windows x64 MSVC/clang-cl validate that unchanged contract for the current bounded workloads, including exact query/size rejection and host callback behavior.

The Unreal Native AOT host has two evidence layers: the engine-independent host core is reproducibly exercised in Windows CI, while the UE5.8 PIE execution is currently machine-local evidence. The local run used the same synthetic RV32I module and frozen ABI interface, with installation inputs matched to the CI handoff by SHA-256. External summaries should describe this as local UE5.8 runtime validation rather than imply hosted-CI reproducibility.

These results do **not** promote arbitrary RV32I/MIPS32 executables, full MIPS32 ISA/ABI coverage, macOS/Windows ARM64/Windows x86 ABI parity, arbitrary optimization correctness, WebAssembly AOT compilation, general MIPS32 Unreal hosting, packaged-game deployment or a release-quality production compiler/plugin pipeline to PROVEN.
