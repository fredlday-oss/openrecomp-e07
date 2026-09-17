# P4-01 result (PASS)

Stage: `P4-01` Generic Runtime ABI V1 (frozen queue row).
Gate: `tools/test_phase4_runtime_abi_v1.py` (156 checks, sha256
`a9f2c9968508120de8e2b35f41891cca8965dbeb724d645d8d89d893e9680563`).
Evidence: `.openrecomp-phase4/evidence/P4-01/`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_01=PASS`
- Gate marker: `OPENRECOMP_PHASE4_RUNTIME_ABI_V1=PASS tests=156`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Objective (frozen queue)

Define and verify an architecture-neutral generated-code <-> runtime ABI
covering execution state, calls, returns/exits, faults, memory service
boundaries, host/runtime services and deterministic observable state, with no
CoreMark-specific shortcuts in the ABI.

## Implementation (additive Phase-4 files only)

- `.openrecomp-phase4/src/p4_runtime_abi_v1.py` — the executable contract:
  typed C symbols, typed/versioned service descriptors, instance profiles, a
  generated-source verifier and a fail-closed reference runtime model.
  It reuses the frozen P2-08 `openrecomp.runtime_abi` as the single source of
  truth for the ABI name, version, failure codes, widths, endianness and the
  canonical sorted service numeric ids; nothing in it is used by, or changes,
  the frozen emitters or evidence.
- `.openrecomp-phase4/contracts/generated_runtime_abi_v1.json` — the
  deterministic machine-readable contract document.
- `.openrecomp-phase4/ports/generated_runtime_abi_v1.h` — the deterministic C
  header for the boundary.
- `.openrecomp-phase4/ports/generated_runtime_abi_v1_profile_mips32_o32.json`
  — the declared instance profile of the frozen Phase-3 path (widths
  `{8,16,32}`, 32 registers, `hi`/`lo` aux accessors, services `p3.exit` = 1
  and `p3.uart_write` = 2, sha256-pinned generated artifacts).
- `tools/test_phase4_runtime_abi_v1.py` — the P4-01 gate.
- `.openrecomp-phase4/SOURCE_SHA256SUMS.txt` — grown additively to six
  entries.

No frozen Phase-1/Phase-2/Phase-3 file, gate, evidence byte or tag was
modified.

## ABI surface (verified)

Runtime provides: `or_rt_memory_read`, `or_rt_memory_write`,
`or_rt_host_call`, `or_rt_failure_reason` with exact signatures.
Generated code provides: `openrecomp_run`, `openrecomp_failed`,
`openrecomp_error`, `openrecomp_steps`, `openrecomp_pc`,
`openrecomp_register_count`, `openrecomp_register_value`, `openrecomp_image`,
`openrecomp_image_size`, `openrecomp_region_count`, `openrecomp_region`.
Reserved core namespace: `or.runtime.*` (`or.runtime.exit` declared typed and
terminating). Fault model: the 14 P2-08 failure codes with first-failure
latching. Memory boundary: widths/endianness/bounds-checked, no host pointer.
Observable: canonical state document plus an FNV-1a 64 digest over a
byte-exact layout. Entry-return policy: returning from the generated entry
without a declared termination is a deterministic fault.

## Verification highlights

- `contract:*` and `profile:*`: version/name/failure-codes/widths equal the
  P2-08 ABI; macro names and numeric ids equal the P2-08 canonical
  (`RuntimeServiceTable.macro`/`numeric_id`) assignments; instance profile
  valid; invalid contract constructions rejected (fixture namespace, unbounded
  types, incompatible versions, bad widths, duplicate ids).
- `artifact:*`: contract JSON/header/profile on disk are byte-identical to
  fresh emissions; two emissions identical; JSON round-trips.
- `instance:*`: the frozen `coremark_program.c` (`5199e2f0...`) and
  `coremark_support.c` (`c5c69054...`) are verified compliant: exact externs,
  accessor definitions, service macros/uses, failure enum and bounded
  includes; the support defines only the four runtime entries plus the bounded
  harness `main` and fails closed with `OR_RT_UNKNOWN_HOST_SERVICE`.
- `negative:*`: undeclared extern, undeclared service macro, foreign include,
  changed accessor signature, missing accessor, changed runtime signature and
  missing unknown-service fallback are all rejected by the verifier.
- `model:*`: memory, service, version, arity, typed-argument, termination,
  latch, output-capacity and entry-return semantics fail closed with the exact
  codes; the observable digest is deterministic and sensitive to image,
  register, aux, pc, steps, exit status, output and failure state.
- `neutrality:*`: no non-deterministic imports; the contract core surface,
  header and JSON contain no fixture/platform tokens (CoreMark/MIPS/PS1/PS2/
  PSP/N64/`p3.*`/UART/...). Fixture-specific material exists only in the
  declared instance profile.

## Determinism

- Two consecutive official gate runs: exit 0, empty stderr, stdout
  byte-identical raw (6199 bytes, `81c96314...`) and LF (`ad9a0a58...`), and
  `p4_01_tests.json` byte-identical across both runs (`64da953d...`).
- Evidence: `official_runs.json`, `determinism.json`.

## Regressions

- `tools/test_runtime_abi_v1.py` (P2-08) `PASS tests=169`.
- `tools/phase1_host_gates_v1.py` `PASS=44 FAIL=0 SKIPPED=2`.
- `tools/public_safety_scan.py` `OPENRECOMP_PUBLIC_SAFETY=PASS`.
- `tools/test_phase4_boundary_v1.py` (P4-00) `PASS tests=74`, stdout
  byte-identical to the P4-00 official capture (`953312d0...`), re-run with
  the documented frozen-gate boundary-context hygiene (restore the committed
  Phase-4 manifest and P4-00 evidence sidecars for the rerun, then re-apply
  and restore; see `regression_hygiene.json`). No frozen file was modified and
  no history was rewritten.

## Limitations

- The ABI is defined and verified, not yet implemented end-to-end: the
  reference model is a bounded Python model, and the frozen Phase-3 artifacts
  are verified as a compliant instance, but no new runtime execution path is
  claimed by this stage.
- The instance service set used by the frozen Phase-3 path (`p3.exit`,
  `p3.uart_write`) is declared as fixture-specific profile data; replacing it
  with generic typed/versioned runtime services is P4-03's frozen scope.
- The reference observable digest is a contract definition; the frozen
  Phase-3 instance keeps its own instance-specific observable (documented in
  the profile), so no observable equivalence claim is made here.
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal and general compatibility
  markers stay reserved.

## Next stage

P4-02 — Guest memory/runtime model.
