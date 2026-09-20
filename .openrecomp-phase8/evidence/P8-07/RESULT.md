# P8-07 result: incremental native build

Status: `PASS` (24 checks)

Markers:

- `OPENRECOMP_P8_07=PASS`
- `OPENRECOMP_PHASE8_NATIVE_BUILD_V1=PASS tests=24`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_native_build_v1.py`.

## Revision note

This record was regenerated after the P8-04 movz ISA correction changed the
emitted program (program.c fingerprint 3df423e0...); only the executable
and sidecar hashes changed, and the build behaviour is identical.

## Toolchain provenance

`clang-cl.exe` 22.1.8 (`ca7933e47d3a3451d81e72ac174dcb5aa28b59d1`) with
`lld-link.exe` 22.1.8 discovered through `openrecomp.build_pipeline`;
deterministic flags `/c /Brepro /Od /std:c11 /nologo` and
`/Brepro /nologo`.

## Incremental build (development path)

New module `.openrecomp-phase8/src/p8_incremental_build_v1.py` implements the
acceleration policy's content-hash object cache. Keys bind the source SHA-256,
compiler identity/version, compile arguments and object name:

- cold build: 4 compiled, 0 reused;
- warm build: 0 compiled, 4 reused (byte-identical objects);
- corrupted cache entry: exactly 1 recompiled, 3 reused, executable unchanged;
- the incremental executable is byte-stable across all three builds
  (`53abcedf70d7218c39688265865d555b913b68ba05fd980f5af9bd023cc995b8`).

## Clean audited build path (terminal verification)

The existing `openrecomp.build_pipeline` builds the emission set twice in
isolated run directories:

- classification `EXECUTABLE_REPRODUCIBLE`;
- `program.exe` 226304 bytes, SHA-256
  `fb98c8a68c5c3af7bc30dab2e907910e1c1dfd665eb79e0ee7fcd60dd07a04dc`;
- every object file is byte-identical to the incremental build's objects;
- manifest inputs exactly `generated.c`, `p8_driver.c`, `p8_image_v1.c`,
  `p8_runtime_support.c` (the four content-hashed emission files), so no
  source-ROM or other binary material is embedded beyond the permitted
  initialized guest image data;
- the only compiler diagnostics are the documented
  `-Wparentheses-equality` notes from the frozen emitter's defensive
  parentheses; the project policy does not treat them as errors, and they are
  recorded as warning kinds only.

The clean executable differs from the incremental executable only in the
linker-produced debug-directory/workspace metadata (identical objects and
size); the two clean runs are byte-identical, which is the audited
reproducibility claim.

## Official runs

Command `python tools/test_phase8_native_build_v1.py`, exit 0, empty stderr,
both runs byte-identical: stdout 1020 bytes, raw sha256
`40d6e1daa9bdd00dec485fb5f9c18b32a39d0fd34ad5e0b21f2fe0b93a4aa913`, LF
sha256 `add64a0ce1f8bfed6973560c8796bdc0855bb49268836a48d2de023e3105f5db`.

Sidecar identities: `native_build.json`
`48e66ae86b5f37d9bc3c1eff3d78d048b8e6367be4814f7cba326a10002a60cb`,
`p8_07_tests.json`
`e3cd818ddf1c6dceadc8b0af02abaebb791e7cbc8474078b9b7c402cec47196b`.

## Claim-ledger delta

- New evidence: the emission set compiles reproducibly through the existing
  native toolchain boundary, with an audited clean path and a cached
  development path that reuses objects only when content-addressed keys match.
- The executable has not been executed under the official gate; the terminal
  marker remains reserved `NOT_PROVEN`.

## Limitations

- The incremental cache is untracked development state; the audited claim
  rests on the clean isolated two-run build.
- The warning set is documented for this generated program; a new warning
  kind would fail the gate.

## Next stage

P8-08: execute the generated native program, define and run the bounded
observable record twice, and require deterministic result evidence.
