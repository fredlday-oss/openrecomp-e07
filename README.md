# OPENRECOMP_E07_SYNTHETIC_FIXTURE_V1_1

Hardened E07 synthetic proof. V1.1 closes the independent-review findings: `.text` NOBITS rejection, clean decode rejection, machine-enforced IR schema, translator-consumed host contract, bounds-checked guest memory, verified immutable-source checksums, fresh per-run manifest, and precise direct-vs-unresolved call-graph evidence.

Run `./RUN.sh`. Success ends with `PASS: E07 V1.1 HARDENED END-TO-END`.

Rights firewall: original synthetic source and standard ELF/toolchain outputs only; no commercial game binaries/assets, console keys, firmware, proprietary SDK material or console-specific executable formats.

## Licence

OpenRecomp E07 is distributed under the Apache License, Version 2.0. See `LICENSE`.

## Dependencies

The E07 fixture vendors no third-party source. Build/runtime dependencies and their licensing boundary are documented in `DEPENDENCIES.md`.
