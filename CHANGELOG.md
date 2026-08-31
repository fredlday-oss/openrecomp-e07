# Changelog

Significant project changes will be recorded here.

## Unreleased

### Added
- `OPENRECOMP_AOT_WINDOWS_PORTABILITY_V1` cross-OS gate for the frozen Native AOT ABI V1 on Windows x64 under MSVC and clang-cl.
- Windows x64 ABI layout probe pinning the V1 host structure at 24 bytes, API table at 168 bytes and every public field offset.
- Windows DLL export, ABI-negotiation and Linux/Core reference-parity checks for the current RV32I and bounded MIPS32 workloads.
- `OPENRECOMP_NATIVE_AOT_ABI_V1` public fixed-width C contract with a single versioned `openrecomp_native_aot_query` discovery entry point.
- Deterministic Module Image-backed Native AOT ABI adapter generation with module/IR/host-contract/source-provenance metadata and explicit capability flags.
- Native AOT ABI V1 fail-closed version/structure-size negotiation and versioned host callback structure with opaque user data.
- Dual-architecture Native AOT ABI validation for current RV32I and bounded MIPS32 modules under both GCC and Clang, including hidden legacy execution symbols and V1-aware loader checks.
- `OPENRECOMP_AOT_HARDENING_V1` compiler-quality gate with a broader architecture-independent normalized IR operation corpus in little- and big-endian configurations.
- Nine deterministic Core API/AOT runtime-fault equivalence cases covering memory OOB, misalignment, operation limit, shift count, trap, indirect target, call depth, host failure and void host return.
- GCC and Clang AddressSanitizer + UndefinedBehaviorSanitizer standalone smoke execution for the AOT hardening positive fixtures.
- Deterministic normalized IR V1 -> portable C ahead-of-time backend shared by RV32I and MIPS32 workloads.
- Native AOT module execution surface with external host-call callback binding, state/memory inspection and deterministic execution-limit enforcement.
- Dual-architecture AOT equivalence gate requiring exact Core API result parity for RV32I checksum `122010428` and MIPS32 checksum `1950232098`.
- GCC/Clang behavioral parity checks for the current generated native AOT modules.
- Clean synthetic little-endian MIPS32 machine-word fixture for second-guest validation.
- Bounded MIPS32 decoder/frontend with deterministic lowering of arithmetic, signed/unsigned comparison, branches, aligned memory access, direct call/return, direct jump and architectural delay slots into normalized IR V1.
- Independent MIPS32 machine-code reference executor and exact register/memory/checksum equivalence gate against the shared Core API V1 path.
- Deterministic MIPS32 IR V1 and Module Image V1 packaging plus dedicated rejection tests and GitHub Actions CI.
- OpenRecomp Core API V1 reference package with `ModuleImage`, `GuestState`, `GuestMemory`, `HostBinding` and `ReferenceExecutor`.
- Module Image V1 schema binding normalized IR, host contract, memory image, initial state, provenance and deterministic execution limits.
- Deterministic Module Image V1 packaging, explicit validation and E07 Core API equivalence CI.
- Core API fail-closed tests for host binding, guest memory, state declaration and integrity mismatches.
- Deterministic RV32I E07 `0.1.1` -> normalized IR V1 `1.0.0` bridge.
- IR V1 bridge interpreter and equivalence gate against E07 native/golden state.
- Normalized OpenRecomp IR V1 (`1.0.0`) specification and JSON Schema.
- Semantic IR V1 validator with fail-closed compatibility checks.
- IR V1 acceptance/rejection regression tests and a minimal redistributable example.
- GitHub Actions validation for the normalized IR V1 contract.
- Repository production-hardening work.
- Continuous integration for the hardened E07 proof.
- Public-safety scanning.
- Documentation-link validation.
- Contributor, security, build and reproducibility guidance.

### Changed
- Native AOT ABI V1 Windows x64 portability is now **PASS** for the bounded RV32I and MIPS32 workloads under both MSVC and clang-cl; macOS, Windows ARM64 and Windows x86 remain separate candidate gates.
- Added `.gitattributes` LF rules for proof/source text after Windows CRLF checkout conversion correctly caused Module Image host-contract SHA-256 validation to fail; the byte-integrity check itself remains unchanged and fail-closed.
- Native AOT ABI V1 remains **FROZEN-FOR-PORTABILITY-TESTING**; incompatible layout/signature changes must use a new ABI version rather than silently changing V1.
- Finished ABI proof modules keep private execution functions outside the stable module surface; Linux uses hidden default visibility and Windows DLL export validation requires `openrecomp_native_aot_query` as the only OpenRecomp-named export.
- The Python native AOT loader negotiates Native AOT ABI V1 when present while retaining temporary legacy fallback for internal hardening fixtures that are intentionally linked without the public ABI adapter.
- Portable C AOT output is warning-clean for the established dual-architecture workloads and hardening corpus; GCC and Clang compile gates use `-Wall -Wextra -Werror`.
- Generator warning fixes are structural rather than suppressions: unused call results/arguments are emitted deliberately, unsigned comparison lowering is warning-stable, and helpers are only emitted when needed while valid minimal/trap modules retain required shared helpers.
- Common AOT code generation is execution-backed and compiler-hardened for current clean synthetic workloads while the broader release-quality production compiler remains `CANDIDATE`.
- The shared IR V1, Module Image V1 and Core API V1 boundary is now boundedly validated with both RV32I and MIPS32 synthetic guest workloads; broader MIPS32 coverage remains `CANDIDATE`.
- E07 proof CI now requires deterministic Module Image V1 packaging and exact Core API V1 equivalence in addition to the RV32I-to-IR-V1 bridge proof.
- Architecture documentation now separates normalized IR semantics, executable module packaging, reference execution, hardened portable C AOT translation and the versioned native-module ABI.
- E07 proof CI requires deterministic RV32I-to-IR-V1 normalization and exact bridge equivalence with checksum `122010428`.
- Source-integrity policy keeps proof-critical inputs separate from mutable project documentation.
