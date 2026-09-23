# OpenRecomp Phase 12 Handoff

## Current boundary

- work branch `phase12/ps1-hercules-init-frame-v1`, based exactly on the frozen
  Phase-11 terminal commit `665d11dc9f760d0c4ea2486e186c1fe5c762647c`;
- `P12-00` `PASS` (23 checks): ancestry/freeze verification, frozen Phase-1..11
  trees untouched, private fixture identity re-derived, machine-readable proof
  contracts written, reserved markers `NOT_PROVEN`;
- `P12-01` `PASS` (35 checks): documented `ps1.bios.B0.5b` `ChangeClearPAD`
  service installed through the existing mediation architecture plus a
  synthetic project-owned B0 window; positive/fail-closed emitter and direct
  dispatcher coverage; `OPENRECOMP_PHASE12_B0_5B_CHANGECLEARPAD_V1=PASS`;
- `P12-02` `PASS` (22 checks): independently re-derived two reachable `B0:0x57`
  sites, the direct `B0:0x5B` stub and seven callers; all reachable B0 paths
  resolve consistently and unknown entries fail closed;
- `P12-03` `PASS` (22 checks): the real initialization path runs past the
  Phase-11 frontier; GetB0Table mediation, entry `0x5B`, derived pointers and
  the eleven-word clear are all observed; unknown entries stay zero; the new
  exact frontier is A0 `0x44` `FlushCache` at `0x80015b94`; markers
  `OPENRECOMP_PHASE12_B0_TABLE_INDIRECT_V1=PASS`;
- `P12-04` `PASS` (20 checks): documented `A0:0x44` `FlushCache` implemented
  with positive/negative fixtures; the initialization path advances to the C0
  interrupt-routine dispatcher at `0x80015f5c`; C0 `0x02`/`0x03`/`0x0a` stay
  fail-closed and the initialization frontier is recorded
  `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` (interrupt delivery not modelled);
- next stage `P12-05` (Hercules initialization proof evaluation).

## Exact next action

Run the P12-00 initialization contract: execute the final-tree private
initialization path twice, evaluate every predicate, and honestly report
`NOT_PROVEN` because the `INIT-BOUNDARY` predicate is not reached (C0 interrupt
services stay fail-closed). Then run the `P12-05` gate twice.

## Verification commands

```
python .openrecomp-phase12/src/p12_stage_runner_v1.py \
  --stage P12-00 --script tools/test_phase12_boundary_v1.py \
  --evidence-dir .openrecomp-phase12/evidence/P12-00 \
  --tests-json p12_00_tests.json
```

## Proof marker states

```
OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
```

## Unresolved evidence

- The `B0:0x5B` target is BIOS-resident and absent from the fixture; Phase 12
  models it through synthetic, project-owned mediation. No fabricated BIOS
  address is used.

## Third-party code

`THIRD_PARTY_CODE_IMPORTED=NO`.
