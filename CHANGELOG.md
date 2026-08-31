# Changelog

Significant project changes will be recorded here.

## Unreleased

### Added
- Deterministic normalized IR V1 -> portable C ahead-of-time backend shared by RV32I and MIPS32 workloads.
- Native AOT module interface with external host-call callback binding, state/memory inspection and deterministic execution-limit enforcement.
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
- Common AOT code generation is now execution-backed for both current clean synthetic guest architectures while the broader release-quality production compiler remains `CANDIDATE`.
- The shared IR V1, Module Image V1 and Core API V1 boundary is now boundedly validated with both RV32I and MIPS32 synthetic guest workloads; broader MIPS32 coverage remains `CANDIDATE`.
- E07 proof CI now requires deterministic Module Image V1 packaging and exact Core API V1 equivalence in addition to the RV32I-to-IR-V1 bridge proof.
- Architecture documentation now separates normalized IR semantics, executable module packaging, reference execution and portable C AOT translation.
- E07 proof CI requires deterministic RV32I-to-IR-V1 normalization and exact bridge equivalence with checksum `122010428`.
- Source-integrity policy keeps proof-critical inputs separate from mutable project documentation.
