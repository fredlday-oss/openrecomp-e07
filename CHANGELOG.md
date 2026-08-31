# Changelog

Significant project changes will be recorded here.

## Unreleased

### Added
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
- E07 proof CI now requires deterministic Module Image V1 packaging and exact Core API V1 equivalence in addition to the RV32I-to-IR-V1 bridge proof.
- Architecture documentation now separates normalized IR semantics, executable module packaging, reference execution and future production AOT translation.
- E07 proof CI requires deterministic RV32I-to-IR-V1 normalization and exact bridge equivalence with checksum `122010428`.
- Source-integrity policy keeps proof-critical inputs separate from mutable project documentation.
