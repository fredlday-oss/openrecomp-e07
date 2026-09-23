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
- next stage `P12-02` (complete B0:0x5B caller coverage).

## Exact next action

Independently re-derive the B0:0x5B caller inventory on the private fixture
(reconnaissance lists two `B0:0x57` sites and seven direct callers via stub
`0x80015f38`), classify direct/GetB0Table/trampoline/reachability, and test that
all reachable required paths resolve consistently. Then run the `P12-02` gate
twice.

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
