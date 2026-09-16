# P2-50 build and package reproducibility - result

Stage: `OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1`.

Verdict: **PASS**.

## Markers

```text
OPENRECOMP_P2_50=PASS
OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1=PASS tests=174
```

## What was proven

For three representative Phase-2 targets - the synthetic NES/NROM end-to-end
fixture (P2-23), the synthetic 4-function MIPS32/non-NES fixture (P2-14) and the
shared runtime/build pipeline through the P2-08 generic runtime ABI (P2-40) -
two independent clean build roots (two isolated P2-09 runs each) produced
byte-identical generated source, normalized compiler/linker command lines, build
manifests, objects and executables, and independently assembled release packages
produced byte-identical archives. Repeated native executions of the independently
built executables produced byte-identical output equal to the independent
reference observables.

| representative | generated source | executable | release archive |
|---|---|---|---|
| `generic-runtime-pipeline` | `c0a76e0f1921...` | `96676becf33f...` | `fa72b5d169ad...` |
| `mips32-larger` | `25d8d85ff88d...` | `1e81bf8cd32b...` | `1c1dac0ea994...` |
| `nes-nrom-end-to-end` | `9819b40e9909...` | `5afd387d0482...` | `71847f9d7ffd...` |

## Reproducibility classification

```text
generic-runtime-pipeline: EXECUTABLE_REPRODUCIBLE (source=yes, manifest=yes, object=yes, executable=yes, package=yes)
mips32-larger: EXECUTABLE_REPRODUCIBLE (source=yes, manifest=yes, object=yes, executable=yes, package=yes)
nes-nrom-end-to-end: EXECUTABLE_REPRODUCIBLE (source=yes, manifest=yes, object=yes, executable=yes, package=yes)
```

No binary post-processing or normalization was applied. `/Brepro` is passed
directly to the detected `clang-cl`/`lld-link` toolchain; the release archive
writer fixes all container metadata (stored compression, sorted names, fixed
1980-01-01 timestamps, no extra fields, no directory entries).

## Nondeterminism audit

All audited nondeterminism surfaces were checked per representative and found
stable across independent roots: COFF object `TimeDateStamp` values (fixed 0),
PE executable `TimeDateStamp` values (content-derived by `/Brepro`), the PE
debug directory (a single deterministic `Repro (0x10)` `/Brepro` marker; objects
carry none), and binary scans for host paths and secrets. Normalization applied:
none. Classification:

```text
generic-runtime-pipeline: BYTE_DETERMINISTIC_NO_NORMALIZATION
mips32-larger: BYTE_DETERMINISTIC_NO_NORMALIZATION
nes-nrom-end-to-end: BYTE_DETERMINISTIC_NO_NORMALIZATION
```

## Package legality

Packages contain exactly the declared generated source, runtime support source,
build manifest, executable, release manifest and checksums file. The content
policy rejected no findings and found no console image magics, ROM/BIOS/firmware
names, absolute host paths, temporary paths, private keys or credential patterns.

## Source/evidence provenance

Canonical source-state fingerprint: `5d93971b102b24e56b2c98bf4c6b6486f58e6c174700af1c77cf969f85024c54`.
Each release manifest records the pipeline source files and SHA-256 values that
produced its artifacts; the gate re-verified them against the working tree, and
the Phase-1 source-integrity gate verified the tracked manifest in this run.

## Runtime equivalence

```text
generic-runtime-pipeline: observations byte-identical=yes, equal to declared expected=yes
mips32-larger: observations byte-identical=yes, equal to declared expected=yes
nes-nrom-end-to-end: observations byte-identical=yes, equal to declared expected=yes
```

## Regressions

`21` prior gates were re-run; all passed:

```text
tools/test_program_model_v1.py: rc=0
tools/test_cfg_v1.py: rc=0
tools/test_functions_v1.py: rc=0
tools/test_call_graph_v1.py: rc=0
tools/test_translation_units_v1.py: rc=0
tools/test_indirect_control_flow_v1.py: rc=0
tools/test_host_emitter_v1.py: rc=0
tools/test_runtime_abi_v1.py: rc=0
tools/test_build_pipeline_v1.py: rc=0
tools/test_mips32_end_to_end_v1.py: rc=0
tools/test_mips32_calls_memory_v1.py: rc=0
tools/test_mips32_direct_cfg_v1.py: rc=0
tools/test_runtime_host_boundary_v1.py: rc=0
tools/test_mips32_larger_fixture_v1.py: rc=0
tools/test_nes6502_program_bridge_v1.py: rc=0
tools/test_nes6502_host_emitter_v1.py: rc=0
tools/test_nes_runtime_bridge_v1.py: rc=0
tools/test_nes_end_to_end_v1.py: rc=0
tools/test_cross_architecture_neutrality_v1.py: rc=0
tools/test_generic_runtime_integration_v1.py: rc=0
tools/test_nes_platform_v1.py: rc=0
```

Phase-1 host gates and source integrity:

```text
PASS                             source-integrity                 verified 131 manifest entries
PASS                             wasm-runner-intact               sha256=b973c3c52712937d59a15f2e50c405830be9882b5c457c05b1248b12405613ca
PASS                             ir-v1-spec                       marker 'OPENRECOMP_IR_V1_SPEC=PASS' present
PASS                             ir-v1-minimal-example            marker 'OPENRECOMP_IR_V1_VALID=PASS' present
PASS                             core-api-v1                      marker 'OPENRECOMP_CORE_API_V1_TESTS=PASS' present
PASS                             adapter-seam                     marker 'PASS: shared adapter interface is real' present
PASS                             frontend-contract-v1             marker 'OPENRECOMP_FRONTEND_CONTRACT_V1=PASS' present
PASS                             frontend-scaffold-v1             marker 'OPENRECOMP_FRONTEND_SCAFFOLD_V1=PASS' present
PASS                             arch-harness-mips32-v1           marker 'OPENRECOMP_ARCH_HARNESS_V1=PASS' present
PASS                             arch-harness-riscv32-v1          marker 'OPENRECOMP_ARCH_HARNESS_V1=PASS' present
PASS                             sm83-state-v1                    marker 'OPENRECOMP_SM83_STATE_V1=PASS' present
PASS                             sm83-decode-v1                   marker 'OPENRECOMP_SM83_DECODE_V1=PASS' present
PASS                             sm83-semantics-v1                marker 'OPENRECOMP_SM83_SEMANTICS_V1=PASS' present
PASS                             sm83-lowering-v1                 marker 'OPENRECOMP_SM83_LOWERING_V1=PASS' present
PASS                             gb-rom-v1                        marker 'OPENRECOMP_GB_ROM_V1=PASS' present
PASS                             gb-headless-v1                   marker 'OPENRECOMP_GB_HEADLESS_V1=PASS' present
PASS                             gb-mode-v1                       marker 'OPENRECOMP_GB_MODE_V1=PASS' present
PASS                             sm83-gb-gbc-regression-v1        marker 'OPENRECOMP_SM83_GB_GBC_REGRESSION_V1=PASS' present
PASS                             z80-state-v1                     marker 'OPENRECOMP_Z80_STATE_V1=PASS' present
PASS                             z80-decode-v1                    marker 'OPENRECOMP_Z80_DECODE_V1=PASS' present
PASS                             z80-semantics-v1                 marker 'OPENRECOMP_Z80_SEMANTICS_V1=PASS' present
PASS                             z80-lowering-v1                  marker 'OPENRECOMP_Z80_LOWERING_V1=PASS' present
PASS                             sms-platform-v1                  marker 'OPENRECOMP_SMS_PLATFORM_V1=PASS' present
PASS                             sms-headless-v1                  marker 'OPENRECOMP_SMS_HEADLESS_V1=PASS' present
PASS                             z80-sms-regression-v1            marker 'OPENRECOMP_Z80_SMS_REGRESSION_V1=PASS' present
PASS                             nes6502-state-v1                 marker 'OPENRECOMP_NES6502_STATE_V1=PASS' present
PASS                             nes6502-decode-v1                marker 'OPENRECOMP_NES6502_DECODE_V1=PASS' present
PASS                             nes6502-semantics-v1             marker 'OPENRECOMP_NES6502_SEMANTICS_V1=PASS' present
PASS                             nes6502-lowering-v1              marker 'OPENRECOMP_NES6502_LOWERING_V1=PASS' present
PASS                             nes-rom-v1                       marker 'OPENRECOMP_NES_ROM_V1=PASS' present
PASS                             nes-platform-v1                  marker 'OPENRECOMP_NES_PLATFORM_V1=PASS' present
PASS                             nes-headless-v1                  marker 'OPENRECOMP_NES_HEADLESS_V1=PASS' present
PASS                             nes-regression-v1                marker 'OPENRECOMP_NES_REGRESSION_V1=PASS' present
PASS                             arch-harness-sm83-v1             marker 'OPENRECOMP_ARCH_HARNESS_V1=PASS' present
PASS                             mips32-frontend-v1               marker 'OPENRECOMP_MIPS32_FRONTEND_V1_TESTS=PASS' present
PASS                             mips32-expansion-v1-negative     marker 'OPENRECOMP_MIPS32_EXPANSION_NEGATIVE_TESTS=PASS' present
PASS                             mips32-microtests-v1             marker '0 failed' present
PASS                             mips32-causality-v1              marker 'CAUSALITY_PASS' present
PASS                             mips32-equivalence-v1            marker 'EQUIVALENCE_PASS' present
PASS                             public-safety-scan               marker 'OPENRECOMP_PUBLIC_SAFETY=PASS' present
PASS                             public-safety-missing-file-test  marker 'OPENRECOMP_PUBLIC_SAFETY_MISSING_FILE_TEST=PASS' present
PASS                             doc-links                        marker 'OPENRECOMP_DOC_LINKS=PASS' present
PASS                             release-metadata-tests           marker 'OPENRECOMP_RELEASE_AUTOMATION_V1_TESTS=PASS' present
PASS                             release-v0_2_0-metadata          marker 'OPENRECOMP_V0_2_RELEASE_METADATA=PASS' present
SKIPPED_TOOLCHAIN_UNAVAILABLE    e07-hardened-end-to-end          missing required tool(s): gcc
SKIPPED_TOOLCHAIN_UNAVAILABLE    external-repro-v1                missing required tool(s): gcc, posix
OPENRECOMP_PHASE1_HOST_GATES_JSON=host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS                             source-integrity                 verified 131 manifest entries
PASS                             wasm-runner-intact               sha256=b973c3c52712937d59a15f2e50c405830be9882b5c457c05b1248b12405613ca
OPENRECOMP_PHASE1_HOST_GATES_PASS=2 FAIL=0 SKIPPED=0
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

## Gate determinism

All comparisons in this gate are byte-level and were made across two independent
build roots, two isolated runs per root, and two independently assembled release
packages. Two consecutive full gate runs produced byte-identical stdout; the
hash is recorded in the stage control plane together with this evidence.

## Limitations and non-claims

* Proves reproducibility only for the audited synthetic fixtures, the detected
  `clang-cl`/`lld-link` toolchain on this host and the audited packaging path.
* Does not prove reproducibility across other compiler versions, operating
  systems, architectures or future toolchains.
* Does not prove arbitrary game compatibility; the fixtures are synthetic/original
  and bounded as documented by P2-10..P2-23 and P2-40.
* The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF` marker remains reserved
  for P2-99.
