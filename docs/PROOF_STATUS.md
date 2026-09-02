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
| MIPS32 synthetic vertical slice | **PASS** | Historical bounded little-endian fixture: independent machine-code reference and shared IR/Core path match state, memory and checksum `1950232098`; 7 delay slots lowered |
| MIPS32 expansion V1 synthetic suite | **PASS** | Five bounded little/big-endian fixtures agree across independent reference, IR/Core and native AOT paths; checksums `435263539`, `4257846410`, `2065440492`, `768371589`, `938211822` |
| MIPS32 expansion Linux compiler parity | **PASS** | All five expanded fixtures reproduce Core/reference results under GCC and Clang with `-Werror` |
| MIPS32 expansion Windows x64 parity | **PASS** | All five expanded fixtures reproduce Linux/Core evidence under MSVC and clang-cl through unchanged Native AOT ABI V1 |
| Cross-architecture IR/Module/Core boundary | **PASS** | Bounded RV32I + multi-fixture MIPS32 synthetic validation through the same normalized contracts |
| Portable C AOT backend V1 | **PASS** | Common backend generates deterministic C for current RV32I and bounded MIPS32 workloads and reproduces Core API results |
| GCC/Clang AOT behavioral parity | **PASS** | Exact observable parity for current RV32I/MIPS32 proof fixtures |
| AOT warning-clean compiler gate | **PASS** | Current fixtures/hardening corpus compile with `-Wall -Wextra -Werror` |
| Core API/AOT runtime-fault equivalence | **PASS** | 9 bounded architecture-independent fault classes agree |
| AOT ASan/UBSan smoke | **PASS** | Little/big-endian positive hardening fixtures under GCC and Clang on Linux CI |
| Native AOT ABI V1 contract | **FROZEN-FOR-PORTABILITY-TESTING** | Public fixed-width C header and exact version/size negotiation |
| Native AOT ABI V1 Linux validation | **PASS** | RV32I + bounded MIPS32 under GCC and Clang |
| Native AOT ABI V1 Windows x64 validation | **PASS** | Frozen layout under MSVC + clang-cl `/W4 /WX` |
| Native AOT ABI V1 public symbol surface | **PASS** | `openrecomp_native_aot_query` is the stable OpenRecomp entry point |
| Linux/Windows native AOT observable parity | **PASS** | Windows results equal Linux/Core reference results for the bounded evidence matrix |
| Cross-platform proof-text byte stability | **PASS** | `.gitattributes` keeps hashed proof/source text LF-stable across Linux/Windows |
| External Reproducibility V1 | **PASS — reproducible Linux reviewer path** | One clean-checkout command executes hardened E07, RV32I/Core/AOT, bounded MIPS32 vertical + five-fixture expansion, Native AOT ABI loading and public safety; hosted CI runs it twice and requires byte-identical semantic `RESULT.json` evidence |
| Unreal Native AOT host core | **PASS** | Reproducible Windows CI four-way MSVC/clang-cl host/module matrix; exact V1 negotiation/callback/result checks |
| Unreal Native AOT host V1 UE5.8 runtime | **PASS — local runtime evidence** | UE5.8 Windows x64 PIE loaded the synthetic RV32I AOT DLL and observed state `48`, checksum `122010428`, operations `3866`; installation inputs matched CI handoff by SHA-256, but UE itself is not available in hosted CI |
| OpenRecompRuntime plugin V1 hosted gate | **PASS** | Hosted CI verifies plugin structure/header identity, deterministic packaging, builds the validated Windows synthetic DLL and executes it through the established host core |
| OpenRecompRuntime plugin V1 UE5.8 runtime | **PASS — local runtime evidence** | UE5.8 Windows x64 build completed and PIE through `UOpenRecompSubsystem`/the plugin example consumer produced state `48`, checksum `122010428`, operations `3866`; returned plugin manifest exactly matched the CI handoff |
| Unreal packaged build V1 hosted gate | **PASS** | Hosted Windows CI verifies packaged-build source/staging contracts, Windows PowerShell 5.1 collector execution, validated Native AOT DLL/host-core behavior and deterministic handoff generation |
| Unreal packaged build V1 UE5.8 Development package | **PASS — local packaged runtime evidence** | UE5.8 Windows x64 Development BuildCookRun staged the exact CI DLL and the packaged executable launched outside Editor/PIE with state `48`, checksum `122010428`, operations `3866` |
| Unreal Engine 5.8 build | **PASS — local environment** | Windows UE5.8 Editor build completed outside hosted CI |
| Original Unreal Gate B PIE runtime | **PASS — local runtime evidence** | Public-safe local UE5.8 runtime evidence; independent from visual replay |
| Unreal visual replay | **PASS — local presentation evidence** | Presentation-only evidence, separate from authoritative runtime paths |
| General MIPS32 frontend/ISA coverage | **CANDIDATE** | Expansion V1 remains a fixture-backed subset; it is not full ISA or o32 ABI support |
| macOS / Windows ARM64 / Windows x86 Native AOT ABI parity | **CANDIDATE** | Not covered by current x64 Linux/Windows evidence |
| Release-quality production AOT compiler/plugin pipeline | **CANDIDATE** | Broader platform/optimization/Shipping/general-deployment evidence remains outstanding |

## Claim policy

**PROVEN** means the current evidence directly validates the stated path and is reproducible at the stated project scope.

**PASS** means a bounded validation/test completed successfully.

**PROVEN-RUNTIME** is reserved for runtime behavior whose evidence path is reproducible at the stated scope. A machine-local runtime observation that cannot currently be reproduced in project-controlled CI is instead reported as **PASS — local runtime evidence** with its environment/provenance stated explicitly.

**CANDIDATE** means an interface or future direction exists but the implementation has not crossed the required proof gate.

**FROZEN-FOR-IMPLEMENTATION** is a specification state, not a proof state. It means the contract is sufficiently defined and mechanically validated to implement against while broader runtime/generalization claims remain evidence-gated.

**FROZEN-FOR-PORTABILITY-TESTING** means the V1 binary layout and semantics are fixed for cross-platform validation. Incompatible changes must use a new ABI version rather than silently mutating V1.

Automated or AI-generated summaries, code suggestions and review output are not evidence by themselves and cannot upgrade a status. See [`../DEVELOPMENT_PROCESS.md`](../DEVELOPMENT_PROCESS.md).

## Current bounded claim boundaries

The RV32I result remains bounded to the clean E07 synthetic fixture/proven subset.

The historical MIPS32 vertical-slice result remains independently reproducible and bounded to its original clean little-endian fixture. Expansion V1 adds five separate fixture-backed proofs covering logical/fixed-and-variable shift operations, signed/unsigned comparisons and immediates, byte/halfword/word memory semantics, signed branch forms and delay slots, bounded nested direct-call/stack behavior, signed/unsigned multiply with HI/LO state, and one bounded big-endian memory workload. These fixtures cross the same IR V1, Module Image V1, Core API V1, portable-C AOT and Native AOT ABI V1 boundaries.

The `branches-calls` fixture demonstrates a bounded o32-style register/stack interaction using `$a0/$a1`, `$v0`, `$sp` and `$ra`; it is not a complete o32 ABI implementation or validation suite.

`div` and `divu` remain explicitly rejected in Expansion V1 because normalized IR V1 currently has no division/remainder semantic operation. The frontier did not silently mutate frozen IR V1 to increase guest-opcode coverage. A future architecture-neutral IR revision or extension would need to define those semantics before they can be normalized.

The cross-architecture PASS means the same normalized IR V1, Module Image V1 and Core API V1 boundaries have been executed with two materially different synthetic guest architectures, with the MIPS32 side now represented by multiple independent semantic fixtures. It does not establish arbitrary-binary support.

The portable C AOT PASS means the same architecture-neutral backend consumes the normalized workloads and reproduces Core API results after native compilation. AOT hardening adds warning-clean compilation, deterministic fault-category equivalence and sanitizer smoke coverage without expanding the guest-support claim.

Native AOT ABI V1 freezes a public native-module boundary. Linux GCC/Clang and Windows x64 MSVC/clang-cl validate that unchanged contract for the current bounded workloads, including exact query/size rejection and host callback behavior. Expansion V1 reuses that contract unchanged for all five added MIPS32 fixtures.

External Reproducibility V1 packages the established Linux-side open-core evidence into one reviewer command, `bash EXTERNAL_REPRO_V1.sh`. The gate starts from a clean tracked tree, runs the hardened E07 proof, independently regenerates and executes the normalized RV32I and bounded MIPS32 Core/AOT evidence, validates Native AOT ABI V1 modules under GCC and Clang, restores the reviewed tracked evidence before running the unchanged fail-closed public-safety scanner, and finishes with no tracked-tree mutation. Hosted CI executes the full reviewer gate twice at the exact source commit and requires byte-identical `RESULT.json` and `RESULT.sha256`. This is a bounded Linux reviewer reproducibility claim, not evidence for Windows, Unreal execution, other host architectures, arbitrary guest binaries or production compiler status.

The Unreal Native AOT host has two evidence layers: the engine-independent host core is reproducibly exercised in Windows CI, while the UE5.8 PIE execution is currently machine-local evidence. The local run used the same synthetic RV32I module and frozen ABI interface, with installation inputs matched to the CI handoff by SHA-256. External summaries should describe this as local UE5.8 runtime validation rather than imply hosted-CI reproducibility.

OpenRecompRuntime Plugin V1 adds a reusable code-only UE host layer over that same frozen ABI. Hosted CI verifies source/ABI boundaries, deterministic packaging and the validated Windows module/host-core path. A separate UE5.8 Windows x64 run built the plugin without source edits and produced the exact plugin runtime marker through PIE. Its returned plugin manifest exactly matched the CI handoff, but the UE execution remains **local runtime evidence** because Unreal Engine is not present in hosted project CI.

Unreal Packaged Build V1 extends that same plugin/ABI path into a real Windows x64 Development package. Hosted CI verifies the source/staging contract, validates the synthetic DLL through the host core, smoke-tests the PowerShell 5.1 public-safe collector path and generates the deterministic handoff. The local UE5.8 gate then used PR #19 source head `334a4ba603618b243c896c8122fd4cd730730e56`, staged the validated DLL with SHA-256 `f6a8679cbd763529b6dd5f33c2ffeac8e269d8f4e2d859e8b1c48dec8cc6b2b6`, packaged a Development Win64 build and launched the packaged executable outside Editor/PIE. It reproduced state `48`, checksum `122010428` and operations `3866`. This is **PASS — local packaged runtime evidence**; it does not establish Shipping parity or arbitrary Unreal-project/version/platform compatibility.

These results do **not** promote arbitrary RV32I/MIPS32 executables, full MIPS32 ISA/ABI coverage, `div/divu`, unaligned MIPS load/store families, exceptions/coprocessors/floating point, macOS/Windows ARM64/Windows x86 ABI parity, arbitrary optimization correctness, WebAssembly AOT compilation, general MIPS32 Unreal hosting, Shipping packaged-build parity, arbitrary Unreal-project/version/platform compatibility or a release-quality production compiler/plugin pipeline to PROVEN.
