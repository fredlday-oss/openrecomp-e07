# P12-00 — Phase bootstrap / Phase-11 freeze / proof contracts

Verdict: **PASS** (23 checks, deterministic twice).

Marker: `OPENRECOMP_P12_00=PASS`.

## Objective

Establish the Phase-12 control plane from the frozen Phase-11 terminal commit,
verify the frozen Phase-11 boundary is untouched, re-verify the private fixture
identity, and define the two machine-readable proof contracts before any
promotion.

## Frozen baseline

- Phase-11 branch `phase11/ps1-playability-v1` tip
  `665d11dc9f760d0c4ea2486e186c1fe5c762647c`
  (`phase11: complete P11-99 final bounded verdict`).
- Phase-11 terminal verdict `PASS_BOUNDED_MILESTONE_C_PRIVATE_FIXTURE`;
  highest proven milestone C.
- Required ancestors present: `1aef50f6` (P11-91), `615e769c` (P11-90).
- Phase-12 branch `phase12/ps1-hercules-init-frame-v1`.

## What the gate verifies

1. `boundary:base-is-ancestor` and the two required ancestors are ancestors of
   the audited HEAD.
2. The frozen Phase-1..Phase-11 tracked trees and the historical
   `tools/test_phase11_*.py` gates are byte-identical between the base commit
   and HEAD, and the frozen worktree has no tracked modification.
3. The private fixture identity is re-derived read-only: `SLUS_005.29` size
   `129024`, SHA-256
   `c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f`,
   single-track MODE2/2352 CUE, boot extent byte-identical to the executable.
4. The machine-readable proof contracts are written and internally consistent
   (`INIT-PREDECESSOR`, `INIT-B0-PATCH`, `INIT-BOUNDARY`,
   `INIT-NO-FAIL-CLOSED`, `INIT-DETERMINISTIC`, `INIT-NO-FABRICATION`;
   `FRAME-PREDECESSOR`, `FRAME-PRIMITIVE`, `FRAME-OT`, `FRAME-SUBMIT`,
   `FRAME-DETERMINISTIC`, `FRAME-NOT-PLAYABILITY`).
5. The reserved markers remain `NOT_PROVEN`.

## Proof contract summary

- `OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF`: requires the documented
  B0 pad-patch sequence (GetB0Table -> entry `0x5B`; derived pointers at
  `+0x884`/`+0x894`; eleven-word clear `+0x594`..`+0x5bc`), a mechanically
  defined initialization-completion boundary (first steady-state repeating
  cycle after the patch), zero fail-closed events on the prefix, and
  two-run determinism. Bounded `PRIVATE_FIXTURE_BOUNDED`, milestone B.
- `OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF`: requires the initialization
  predecessor, a genuine typed GPU primitive, an active ordering-table
  insertion, a frame-submission/buffer transition, and two-run determinism.
  Bounded `PRIVATE_FIXTURE_BOUNDED`, milestone D. Not playability.

## Reserved markers

```
OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
```

## Evidence

- `proof_contracts.json`, `boundary.json`, `fixture_identity.json`,
  `p12_00_tests.json`, `RESULT.json`, `official_runs.json`,
  `determinism.json`, `run1.txt`/`run2.txt`, `run1.err.txt`/`run2.err.txt`.

## Next stage

`P12-01` — B0:0x5B ChangeClearPAD service V1.
