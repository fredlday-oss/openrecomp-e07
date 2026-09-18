# P4-09 result (PASS)

Stage: `P4-09` End-to-end generic-runtime native proof (frozen queue row).
Gate: `tools/test_phase4_generic_runtime_proof_v1.py` (55 checks, sha256
`6827d66856764d87631bbb0e6f673c9ff85d56c2f8b810d2f3e418782a35e3a1`).
Evidence: `.openrecomp-phase4/evidence/P4-09/`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_09=PASS`
- Gate marker: `OPENRECOMP_PHASE4_END_TO_END_NATIVE_PROOF_V1=PASS tests=55`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Objective (frozen queue)

Demonstrate the bounded pipeline: fixture/input -> ingestion -> program
recovery -> translation -> host emission -> native build -> generic runtime ->
platform adapter -> deterministic execution. Verify the observable against an
independent reference/model where technically appropriate. No target or
behaviour may be guessed merely to achieve execution.

## Implementation (additive Phase-4 files only)

- `.openrecomp-phase4/src/p4_reference_fixture_v1.py`: an independently
  written ELF32 loader (program headers parsed directly), raw-word decoder and
  executor for the fixture instruction set with the delay-slot protocol, the
  four MMIO windows, the declared deterministic input plan and the
  one-tick-per-retired-instruction policy; it produces the P4-01 canonical
  observable (transcript, exit status, steps, PC, output and the FNV-1a 64
  state digest over the contract layout).
- `tools/test_phase4_generic_runtime_proof_v1.py`: the pipeline gate.
- `.openrecomp-phase4/SOURCE_SHA256SUMS.txt`: grown additively to 27 entries.

## Pipeline demonstration (each stage executed and recorded)

1. fixture/input: pinned fixture ELF `acb4f4e5...` and input plan
   `0512ab34ff`.
2. ingestion: frozen Phase-3 ingestion identity (ELF32 `EM_MIPS` `ET_EXEC`,
   O32, static, entry `0x1c00`, `.text` `0x1000`+3104); the independent
   loader agrees on entry and all four segment ranges.
3. program recovery: the frozen neutral structure layer recovers 774
   instructions, 142 blocks, 9 functions, 14 internal call edges with one
   recursive function (`fn_1010`), entry unit `tu_fn_1c00`, zero indirect
   sites and zero unresolved edges; fingerprints recorded.
4. translation / host emission: generated program `abd138ea...` and support
   `755a004630...` (P4-01-ABI compliant, verified in P4-08).
5. native build: `EXECUTABLE_REPRODUCIBLE`, executable `c966e185...`,
   deterministic manifest.
6. generic runtime / platform adapter: `BoundPlatform` fixture adapter with
   the declared memory map, generic service aliases and explicit negative
   compatibility claims; services driven fail-closed.
7. deterministic execution: three identical native replays with the exact
   transcript, `steps=6784`, `pc=0x1bf4`, `state_fnv1a64=0x5185479717fe4020`
   and no failure.

## Independent reference equivalence

The independent reference ran the same input plan twice with identical
documents and matched the native observable on every compared field:
transcript (all 11 lines including `ticks_start=19`/`ticks_end=6691`), exit
status 0, steps 6784, PC `0x1bf4`, no failure, output byte-identical and the
state digest `0x5185479717fe4020` (whose layout covers the image, all
registers, HI/LO, PC, steps, exit status and output). The reference also
fails closed on unsupported instructions, step-limit exhaustion, out-of-region
stores and unaligned indirect jumps.

## Determinism

- Two consecutive official gate runs: exit 0, empty stderr, stdout
  byte-identical raw (1815 bytes, `8ab7d3fa...`) and LF, and
  `p4_09_tests.json` byte-identical across both runs.
- Evidence: `official_runs.json`, `determinism.json`, `pipeline.json`,
  `equivalence.json`.

## Regressions

- P2-08 `PASS tests=169`; P4-01..P4-08 all PASS.
- `tools/phase1_host_gates_v1.py` `PASS=44 FAIL=0 SKIPPED=2`.
- `tools/public_safety_scan.py` `OPENRECOMP_PUBLIC_SAFETY=PASS`.
- P4-00 `PASS tests=74` (`953312d0...`) with the documented dynamic
  boundary-context hygiene.

## Limitations

- The proof is bounded to the audited fixture, profile and declared tick
  policy; it is not arbitrary MIPS32, console, game or commercial
  compatibility.
- The native runtime support is the concrete adapter implementation for this
  fixture; no universal runtime completeness is claimed.
- The reference covers exactly the fixture instruction set and fails closed
  otherwise; no target or behaviour was guessed to achieve execution.
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal verdict remains reserved
  for P4-99.

## Next stage

P4-10 - Reproducible Phase-4 package.
