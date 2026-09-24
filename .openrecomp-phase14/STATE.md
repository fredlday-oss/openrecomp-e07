# OpenRecomp Phase 14 State

## Mission

Advance the frozen Phase-13 bounded result by mediating the terminal indirect B0
dispatcher call at `0x80026ebc` as the documented `B0:0x56` `GetC0Table`
service, modelling the minimum guest-observable C0 surface, preserving the exact
early-card IRQ patch dataflow, closing the derived continuation identity,
validating `B0:0x57`, and continuing the real Hercules initialization path until
the inherited initialization proof contract is satisfied or a new bounded
blocker is established.

## Baseline

- Phase-13 terminal: branch `phase13/ps1-hercules-c0-init-v1`, commit
  `7bb4502450d47a0d3f3b207a072c5729277af278`,
  `FINAL_VERDICT=PASS_BOUNDED_C0_AND_CALLBACK_MEDIATION`.
- Phase-12 ancestor: `7d76f242db2e9233ad9e023d0c63a6984fb118a0`.
- Phase-14 branch: `phase14/ps1-hercules-init-closure-v1`.
- Starting frontier: `0x80026ebc` (`fn_80026ea8`), B0:0x56 indirect call.

## Progress

- CURRENT_STAGE: COMPLETE
- LAST_COMPLETED_STAGE: P14-99
- NEXT_STAGE: NONE

## Terminal closure

- PHASE14_HEAD: `0aab59bf9688c5ee6abe982c2bfa57e7a52d10ee` (branch
  `phase14/ps1-hercules-init-closure-v1`).
- Commits: `0e6cac2f` (implementation, control plane, gates), `0aab59bf`
  (deterministic evidence, whole regression, bounded verdict).
- FINAL_VERDICT: `PASS_BOUNDED_INITIALIZATION_CLOSURE_FRONTIER_REMAINS`.
- CURRENT_TECHNICAL_FRONTIER: `0x1F801074` (I_STAT/I_MASK interrupt-mask MMIO
  memory-denial channel).
- INITIALIZATION_PROOF_COMPLETE: NO (inherited contract unmet:
  `INIT-BOUNDARY` true, `INIT-NO-FAIL-CLOSED` false).

## Proof markers

- `OPENRECOMP_PHASE14_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE14_HERCULES_FRAME_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE14_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE14_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`

## Service markers

- `OPENRECOMP_PHASE14_B0_56_GETC0TABLE_V1=PASS`
- `OPENRECOMP_PHASE14_C0_TABLE_SURFACE_V1=PASS`
- `OPENRECOMP_PHASE14_EARLY_CARD_PATCH_V1=PASS`
- `OPENRECOMP_PHASE14_CARD_CONTINUATION_V1=PASS`
- `OPENRECOMP_PHASE14_B0_57_LIVE_VALIDATION_V1=PASS`
- `OPENRECOMP_PHASE14_CARD_INIT_CHAIN_V1=PASS`
- `OPENRECOMP_PHASE14_CARD_IRQ_V1=NOT_REQUIRED`
- `OPENRECOMP_PHASE14_INITIALIZATION_REPLAY_V1=PASS`

## Stage status

| Stage | Status |
|---|---|
| P14-00 | PASS (bootstrap / freeze / contract) |
| P14-01 | PASS (B0:0x56 GetC0Table contract) |
| P14-02 | PASS (C0 table observable surface) |
| P14-03 | PASS (early-card IRQ patch dataflow) |
| P14-04 | PASS (continuation target closure) |
| P14-05 | PASS (B0:0x57 live validation) |
| P14-06 | PASS (memory-card init chain) |
| P14-07 | PASS (frontier loop I) |
| P14-08 | PASS_NOT_REQUIRED (card IRQ not delivered) |
| P14-09 | PASS (frontier loop II) |
| P14-10 | PASS (boundary recovery; boundary not ready) |
| P14-11 | PASS (proof evaluation; proof NOT_PROVEN) |
| P14-20 | PASS (fail-closed hardening) |
| P14-30 | PASS (service consistency) |
| P14-40 | PASS (deterministic replay) |
| P14-50 | PASS (first-frame readiness assessment) |
| P14-90 | PASS (whole regression, 11 suites, 0 failures) |
| P14-91 | PASS (evidence closure) |
| P14-99 | PASS (final bounded verdict) |

## Production results

- Implemented a typed documented `ps1.bios.B0.56` `GetC0Table()` in
  `.openrecomp-phase14/runtime/p14_bios_extension_v1.c`; returns the
  project-owned synthetic C0 table pointer `0x1F000800`.
- Modelled a bounded synthetic C0 surface inside the existing Phase-12 window:
  C0[6] (`+0x18`) = exception-handler object `0x1F001800`; handler `+0x70`/
  `+0x74` = `0x1F00`/`0x1900`; derived early-card handler `0x1F001900`; patch at
  `+0x28`; continuation `0x1F00193C`. None is an authentic BIOS address.
- Preserved the guest patch dataflow: the exact five-word game-side trampoline is
  copied to `handler+0x28` (10 non-zero bytes; FNV-1a verified against the
  fixture source range) and the continuation `0x1F00193C` is stored to
  `0x8002ED90`.
- Added typed continuation service `ps1.bios.internal.card_continuation`
  (fail-closed on any other target) and additive follow-on services
  `A0:0x70` `_bu_init`, `A0:0x30` `abs`, `B0:0x3F` `puts`, and `ps1.mips.mflo`
  (the HI/LO low-word read), plus five bounded site-specific internal indirect
  admissions.
- Validated the existing `B0:0x57` `GetB0Table` live path (synthetic B0 table
  `0x1F000000`, entry `0x5B` = `0x1F001000`, derived pad pointers
  `0x1F001884`/`0x1F001894`).
- Closed all nine Phase-13 trace failures: `trace_failure_count=0` on the live
  path.

## Current technical frontier

`0x1F801074` interrupt-mask MMIO (I_STAT/I_MASK). The live bounded run reaches
14 memory-denial fail-closed events (`failed=1`, `error="runtime memory write
failed"`) at approximately 467000 block events, together with root-counter
(`0x1F801110`) and GPU-status (`0x1F801814`) polling. The initialization proof is
`NOT_PROVEN`: `INIT-BOUNDARY` is mechanically reached (steady repeating cycle,
zero trace failures) but `INIT-NO-FAIL-CLOSED` is false because the run is not
fail-closed clean.

## Third-party code

`THIRD_PARTY_CODE_IMPORTED=NO`.
