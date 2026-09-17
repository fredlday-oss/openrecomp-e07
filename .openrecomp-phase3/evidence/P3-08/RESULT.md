# P3-08 result (PASS)

Stage: `P3-08` native build + generic runtime execution (frozen queue row).
Gate: `tools/test_phase3_native_runtime_v1.py` (55 checks).
Evidence: `.openrecomp-phase3/evidence/P3-08/`.

Markers issued:

- Stage marker: `OPENRECOMP_P3_08=PASS`
- Gate marker: `OPENRECOMP_PHASE3_NATIVE_RUNTIME_V1=PASS tests=55`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

## Scope

P3-08 builds the P3-07 generated host translation with the frozen Phase-2
deterministic build pipeline and executes the native program through the P2-08
generic runtime ABI boundary. New Phase-3 file only
(`tools/test_phase3_native_runtime_v1.py`); no shared layer, frozen adapter,
Phase-1/Phase-2 file, gate or frozen manifest was modified. The Phase-3
manifest grew additively from sixteen to seventeen entries; the earlier gates
now expect seventeen entries and still emit byte-identical stdout.

## Build

- The gate re-emits the host program/support from the frozen inputs and pins
  the exact P3-07 fingerprints (`5199e2f0...` / `c5c69054...`) and the P3-07
  evidence bytes, so P3-08 executes the audited translation.
- `openrecomp.build_pipeline` builds it in two isolated run directories with
  the detected `clang-cl.exe` (LLVM 22.1.8) + `lld-link.exe` toolchain and
  `/Brepro`; the result is `EXECUTABLE_REPRODUCIBLE`: identical sources,
  objects (`generated.obj` `c9a3debf...`, `coremark_support.obj` `feaf60b1...`),
  executable (`c80ecc4b...`) and manifest (`e3eb9651...`) across both runs.
  The manifest leaks no host path or process identity.

## Native execution

- Executable `program.exe` sha256
  `c80ecc4b88c09aa05e913c935d18834373a0920910ee781fa51d3764ef3dd1b6` runs
  three times with byte-identical stdout (sha256
  `7347b5fd5d500ff7713f8bd26f319c4f81205d2075ab0230ab59842fdba56f1b`,
  captured in `native_execution.txt`), exit 0.
- Deterministic observable: `exit_status=0`, `steps=394997250`,
  `pc=0x00004564`, `hi=0x0000000d`, `lo=0x00000000`, `uart_bytes=499`,
  `state_fnv1a64=0x78651c29dd149ab1`, `failed=0`, empty failure.
- CoreMark's own validation contract holds: the UART stream contains
  `CoreMark Size    : 666`, `Total ticks      : 10000`,
  `Iterations       : 1000`, the published validation CRCs
  (`seedcrc 0xe9f5`, `crclist 0xe714`, `crcmatrix 0x1fd7`, `crcstate 0x8e3a`,
  `crcfinal 0xd340`) and `Correct operation validated.`

## Runtime fail-closed boundaries

Four tiny synthetic programs built and executed through the same pipeline
prove the runtime failure paths: divide by zero, taken `teq` trap (code
preserved), unaligned indirect jump target and an out-of-region guest memory
write (`MEMORY_OUT_OF_RANGE`). Each produced the exact expected deterministic
failure message with `failed=1`.

## Verification

- 54 gate checks: source integrity, P3-07 pin, build reproducibility and
  manifest hygiene, replay determinism, observable fields, UART length and
  CoreMark validation lines, four runtime negatives and artifact hashing.
- Official runs: two consecutive runs byte-identical (raw sha256
  `cdc7abbfc3d12d02f197fb0b99e1c7f4ef55f1dc62debb288387ff121225bb9d`, empty
  stderr, exit 0).
- Regressions all exit 0 with empty stderr and byte-identical stdout: P2-99
  `PASS tests=202` (`66913e57...`), P3-00 `PASS tests=61` (`a039bbff...`),
  P3-01 `PASS tests=76` (`81eede03...`), P3-02 `PASS tests=197`
  (`f24f4cef...`), P3-03 `PASS tests=201` (`15e20a2c...`), P3-04
  `PASS tests=126` (`412544a4...`), P3-05 `PASS tests=202` (`12bf87d7...`),
  P3-06 `PASS tests=123` (`23d2f1c2...`), P3-07 `PASS tests=68`
  (`26b871bf...`), Phase-1 host gates `PASS=44 FAIL=0 SKIPPED=2`
  (`2a9d1bba...`), public safety `PASS` (`ad022ff1...`).

## Claim boundary

P3-08 proves only that the audited translation builds reproducibly and executes
deterministically through the generic runtime ABI, with CoreMark's own
validation CRCs and the fail-closed runtime boundaries demonstrated. It does
not yet prove equivalence against an independent MIPS32 reference (P3-09) and
claims no arbitrary MIPS32, PS1 or PS2 compatibility.
`COREMARK_STATUS=NOT_PROVEN`.

## Image-fidelity correction (P3-09 boundary)

The P3-09 independent loader compared the host runtime's flat image with the
true ELF load image and found that the P3-07 emitter had built it from the
allocated sections instead of the PT_LOAD region bytes, so the 308-byte
read-only ELF header region (`0x0..0x134`, never read by the audited guest,
but part of the load image) was zero in the host program. The emitter was
repaired at the source within P3-09 to embed the exact P3-02 load image
(region bytes plus zero-fill); the P3-07 and P3-08 gates were re-run and
re-passed with the corrected evidence, including the new state digest
`0x78651c29dd149ab1` that now matches the independent reference exactly.
No execution result changed: steps, PC, HI/LO, UART stream and exit status
are identical; only the image digest and build/emission hashes changed.
