# Changelog

Significant project changes will be recorded here.

## Unreleased

### Added
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
- E07 proof CI now also requires deterministic RV32I-to-IR-V1 normalization and exact bridge equivalence with checksum `122010428`.
- Architecture documentation distinguishes the proven E07 `0.1.1` proof IR, the normalized V1 contract, and later common-translator/generalization gates.
- Source-integrity policy clarified so proof-critical inputs are separated from mutable project documentation.
