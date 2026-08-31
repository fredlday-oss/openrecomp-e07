# OpenRecomp proof status

| Component | Status | Evidence / notes |
| --- | --- | --- |
| E07 RV32I synthetic path | **PROVEN** | Hardened E07 V1.1 proof |
| Deterministic translation | **PASS** | Existing E07 evidence |
| Native execution | **PASS** | Existing E07 evidence |
| WebAssembly execution | **PASS** | Existing E07 evidence |
| Golden regression | **PASS** | Existing E07 evidence |
| Normalized IR V1 specification | **FROZEN-FOR-IMPLEMENTATION** | Schema, semantic validator and acceptance/rejection tests |
| RV32I -> normalized IR V1 bridge | **PASS** | Deterministic normalization and execution match E07 native/golden checksum `122010428`, return `a0=48`, and host counters |
| Module Image V1 packaging | **PASS** | Repeated packaging is byte-identical; hashes bind IR, host contract and initialized memory |
| Core API V1 reference module/runtime | **PASS** | Generic `ModuleImage` + `ReferenceExecutor` path matches bridge/native/golden checksum `122010428`, return `a0=48`, 3,866 operations and output hashes |
| MIPS32 synthetic vertical slice | **PASS** | Independent machine-code reference and shared IR V1/Module V1/Core API path match complete register state, memory and checksum `1950232098`; 7 delay slots lowered |
| Cross-architecture IR/Module/Core boundary | **PASS** | Bounded validation crosses both RV32I and MIPS32 synthetic guest workloads through the same normalized contracts |
| Portable C AOT backend V1 | **PASS** | One common IR V1 backend generates deterministic C for both current guest workloads; compiled native results equal Core API results exactly |
| GCC/Clang AOT behavioral parity | **PASS** | The same generated C produces identical proof-result JSON after native compilation with both compilers for RV32I and MIPS32 fixtures |
| AOT warning-clean compiler gate | **PASS** | Established dual-architecture workloads plus dedicated hardening corpus compile with GCC/Clang `-Wall -Wextra -Werror` |
| Core API/AOT runtime-fault equivalence | **PASS** | 9 bounded fault classes agree: memory OOB, misalignment, operation limit, shift count, trap, indirect target, call depth, host failure and host void-return |
| AOT ASan/UBSan smoke | **PASS** | Little- and big-endian positive hardening fixtures execute cleanly under GCC and Clang ASan+UBSan on Linux CI |
| General MIPS32 frontend/ISA coverage | **CANDIDATE** | Current implementation is a bounded little-endian subset, not arbitrary MIPS32 |
| Stable external native-module ABI | **CANDIDATE** | Current exported surface is exercised internally but is not frozen as a third-party compatibility contract |
| Release-quality production AOT compiler pipeline | **CANDIDATE** | Portable C backend is execution-backed and hardened for current fixtures, but broader platform/optimization/release evidence remains outstanding |
| Unreal Engine 5.8 build | **PASS** | Validated locally |
| Unreal Gate B PIE runtime | **PROVEN-RUNTIME** | Public-safe runtime evidence |
| Unreal visual replay | **PASS** | Presentation evidence, separate from authoritative Gate B |

## Claim policy

**PROVEN** means the current evidence directly validates the stated path.

**PASS** means a bounded validation/test completed successfully.

**PROVEN-RUNTIME** means the expected behavior was observed and validated during actual runtime execution.

**CANDIDATE** means an interface or future direction exists but the implementation has not crossed the required proof gate.

**FROZEN-FOR-IMPLEMENTATION** is a specification state, not a proof state. It means the contract is sufficiently defined and mechanically validated to implement against, while broader runtime/generalization claims remain gated on execution evidence.

The RV32I results remain bounded to the E07 synthetic fixture/proven RV32I subset. The MIPS32 result is separately bounded to `OPENRECOMP_MIPS32_VERTICAL_SLICE_V1`: a clean little-endian synthetic machine-word fixture covering arithmetic, signed/unsigned comparison, branches, aligned `lw`/`sw`, direct call/return, direct jump and delay-slot lowering.

The cross-architecture IR/Module/Core PASS means the same normalized IR V1, Module Image V1 and Core API V1 boundaries have been validated with two materially different synthetic guest architectures.

`OPENRECOMP_IR_V1_AOT_TRANSLATOR_V1` adds a separate bounded PASS: the same architecture-neutral portable C backend consumes both normalized workloads, emits byte-identical C on repeated translation, and after GCC/Clang compilation reproduces the existing Core API result exactly.

`OPENRECOMP_AOT_HARDENING_V1` strengthens that backend evidence without expanding the guest-support claim. It requires warning-clean `-Werror` compilation, exact positive-result parity for a broader normalized-operation corpus in little- and big-endian configurations, deterministic Core API/AOT agreement across nine runtime-fault categories, and ASan/UBSan-clean standalone execution under GCC and Clang.

These results do **not** promote arbitrary RV32I/MIPS32 executables, full MIPS32 ISA/ABI coverage, Windows/macOS portability, a stable third-party native-module ABI, arbitrary optimization correctness, WebAssembly AOT compilation or a release-quality production compiler pipeline to PROVEN.
