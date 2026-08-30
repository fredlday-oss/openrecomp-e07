# OpenRecomp E07 Synthetic Fixture

Public, rights-safe synthetic evidence fixture for the OpenRecomp deterministic static-recompilation architecture.

The hardened V1.1 evidence path exercises a synthetic RV32I ELF through fail-closed loading, versioned whole-program IR, an architecture adapter, deterministic C translation, native x86-64 and WebAssembly execution, and golden-output validation.

## Evidence status

**PROVEN:** RV32I synthetic fixture path; malformed-input rejection; IR schema enforcement; host-contract enforcement; guest-memory bounds checks; deterministic translation; native/WebAssembly parity; golden framebuffer/audio/state validation; source/provenance verification.

**CANDIDATE:** MIPS32 second architecture adapter. It is intentionally not represented as executed architecture coverage.

The recorded hardened reference run produced native and WebAssembly checksum `122010428`.

## Rights firewall

This evidence fixture is synthetic and intended for lawful preservation-infrastructure development. It contains no commercial game binaries or assets, console keys, firmware, proprietary SDK material, or console-specific executable formats.

## Reproducibility

The complete hardened E07 V1.1 fixture is being published here as a reproducible evidence demonstrator. The intended local entry point is `./RUN.sh`; a successful run ends with:

`PASS: E07 V1.1 HARDENED END-TO-END`
