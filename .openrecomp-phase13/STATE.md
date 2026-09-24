# OpenRecomp Phase 13 State

## Mission

Advance the frozen Phase-12 bounded result into a stronger, private-fixture-
bounded claim by implementing the minimum architecture-correct C0 BIOS
interrupt-routine queue semantics required by Hercules, resolving the dynamic
callback control-flow frontier, and continuing the real initialization path until
the inherited initialization proof contract is satisfied or a new irreducible
blocker is established.

## Baseline

- Phase-12 terminal: branch `phase12/ps1-hercules-init-frame-v1`, commit
  `7d76f242db2e9233ad9e023d0c63a6984fb118a0`,
  `FINAL_VERDICT=PASS_BOUNDED_B0_MEDIATION_PRIVATE_FIXTURE`.
- Phase-11 base: `665d11dc9f760d0c4ea2486e186c1fe5c762647c`.
- Phase-13 branch: `phase13/ps1-hercules-c0-init-v1`.
- Starting frontier: BIOS `C0:0x03` `SysDeqIntRP` dispatcher at `0x80015f5c`
  (`fn_80015f58`, block 468365).

## Progress

- CURRENT_STAGE: COMPLETE
- LAST_COMPLETED_STAGE: P13-99
- NEXT_STAGE: NONE

## Proof markers

- `OPENRECOMP_PHASE13_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE13_HERCULES_FRAME_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE13_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE13_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (reserved)

## Service markers

- `OPENRECOMP_PHASE13_SYSENQINTRP_V1=PASS`
- `OPENRECOMP_PHASE13_SYSDEQINTRP_V1=PASS`
- `OPENRECOMP_PHASE13_INTRP_ROUNDTRIP_V1=PASS`
- `OPENRECOMP_PHASE13_CALLBACK_MEDIATION_V1=PASS`
- `OPENRECOMP_PHASE13_CHANGECLEARRCNT_V1=NOT_REQUIRED`
- `OPENRECOMP_PHASE13_TIMER1_V1=NOT_REQUIRED`
- `OPENRECOMP_PHASE13_INTERRUPT_MMIO_V1=NOT_REQUIRED`
- `OPENRECOMP_PHASE13_INITIALIZATION_REPLAY_V1=PASS`

## Stage status

| Stage | Status |
|---|---|
| P13-00 | PASS (boundary / freeze / contract recovery) |
| P13-01 | PASS (SysEnqIntRP) |
| P13-02 | PASS (SysDeqIntRP) |
| P13-03 | PASS (IntRP round-trip) |
| P13-04 | PASS (callback provenance) |
| P13-05 | PASS (callback mediation) |
| P13-06 | PASS (frontier loop I) |
| P13-07 | PASS_NOT_REQUIRED |
| P13-08 | PASS_NOT_REQUIRED |
| P13-09 | PASS_NOT_REQUIRED |
| P13-10 | PASS (frontier loop II) |
| P13-11 | PASS (initialization proof assessment; proof NOT_PROVEN) |
| P13-20 | PASS (fail-closed hardening) |
| P13-30 | PASS (interrupt layer consistency) |
| P13-40 | PASS (deterministic replay) |
| P13-50 | PASS (first-frame readiness assessment) |
| P13-90 | PASS (whole regression, 34 checks) |
| P13-91 | PASS (evidence closure) |
| P13-99 | PASS (final bounded verdict) |

## Production results

- Implemented the documented four-chain C0 IntRP queue in
  `.openrecomp-phase13/runtime/p13_bios_extension_v1.c`: `ps1.bios.C0.02`
  `SysEnqIntRP(priority, struc)` inserts at the head and writes the previous head
  into the element's `next` field; `ps1.bios.C0.03` `SysDeqIntRP(priority, struc)`
  removes the head element and returns it (0 when empty / not head), matching the
  documented first-element-only behaviour. Both fail closed on unknown priority,
  invalid/null element pointer, duplicate registration, or wrong arity.
- Added documented B0 bookkeeping services required by the live frontier:
  `B0:0x12 InitPAD2`, `B0:0x13 StartPAD2`, `B0:0x14 StopPAD2`,
  `B0:0x4A InitCARD2`, `B0:0x4B StartCARD2`, `B0:0x4C StopCARD2`.
- Resolved the callback frontier: the pad-start thunk `fn_80015f68` `jr t1` at
  `0x80015f74` is mediated as the typed synthetic controlled target
  `ps1.bios.internal.pad_start_hook`; the runtime validates the target against the
  mechanically derived synthetic address `0x1f001884`. The stop hook
  (`ps1.bios.internal.pad_stop_hook`, `0x1f001894`) is defined and fails closed;
  its thunk is not reached in initialization.
- IntRP callback provenance independently derived: the registered element at
  `0x8002ffb4` carries `func2=0x80015e30` and `func1=0x80015e98`.

## Current technical frontier

`0x80026ebc` (`fn_80026ea8`, block 468385): an unresolved indirect **call** with
source value `0x000000b0` (B0 vector). The initialization proof is `NOT_PROVEN`;
`INIT-BOUNDARY` and `INIT-NO-FAIL-CLOSED` are false on this bounded run. The
frontier advanced from the Phase-12 `0x80015f5c` through the C0 dispatcher, the
pad services, the callback mediation, and the memory-card services.

## Third-party code

`THIRD_PARTY_CODE_IMPORTED=NO`.
