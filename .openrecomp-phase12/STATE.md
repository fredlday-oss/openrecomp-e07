# OpenRecomp Phase 12 State

## Mission

Advance the frozen Phase-11 bounded commercial-fixture result into two
substantially stronger, private-fixture-bounded claims: deterministic Hercules
initialization proof and deterministic Hercules first-frame proof. Phase 12
must NOT claim playability or general PS1 compatibility.

## Baseline

- Phase-11 terminal: branch `phase11/ps1-playability-v1`, commit
  `665d11dc9f760d0c4ea2486e186c1fe5c762647c`,
  `FINAL_VERDICT=PASS_BOUNDED_MILESTONE_C_PRIVATE_FIXTURE`, highest milestone C.
- Phase-12 branch: `phase12/ps1-hercules-init-frame-v1`.
- Starting frontier: BIOS `B0:0x5B` `ChangeClearPAD` dependency through the
  `B0:0x57` `GetB0Table` caller at `0x80015fa4` (block 468341).

## Progress

- CURRENT_STAGE: P12-01
- LAST_COMPLETED_STAGE: P12-00
- NEXT_STAGE: P12-01

## Proof markers

- `OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (reserved)

## Stage status

| Stage | Status |
|---|---|
| P12-00 | PASS (23 checks) |
| P12-01 | not started |
| P12-02 | not started |
| P12-03 | not started |
| P12-04 | not started |
| P12-05 | not started |
| P12-06 | not started |
| P12-07 | not started |
| P12-08 | not started |
| P12-09 | not started |
| P12-10 | not started |
| P12-20 | not started |
| P12-30 | not started |
| P12-40 | not started |
| P12-90 | not started |
| P12-91 | not started |
| P12-99 | not started |

## Stage records

### P12-00 — boundary / freeze / proof contracts

PASS (23 checks). Gate `tools/test_phase12_boundary_v1.py` ran twice through
the Phase-12 stage runner with byte-identical stdout, empty stderr, exit 0 and
byte-identical JSON sidecars.

- base commit `665d11dc` and ancestors `1aef50f6`/`615e769c` verified;
- frozen Phase-1..Phase-11 tracked trees and `tools/test_phase11_*.py` gates
  byte-identical between base and HEAD; frozen worktree clean;
- private fixture identity re-derived (`SLUS_005.29`, size 129024, SHA-256
  `c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f`,
  boot extent identical, single MODE2/2352 track);
- proof contracts written (`proof_contracts.json`); reserved markers
  `NOT_PROVEN`;
- evidence: `.openrecomp-phase12/evidence/P12-00/`.

## Third-party code

`THIRD_PARTY_CODE_IMPORTED=NO`.

## Working-tree residue (preserve untouched)

The inherited untracked Phase-2/Phase-3 residue and the root untracked
`tools/test_build_package_reproducibility_v1.py` predate Phase 12 and must never
be committed, deleted or altered by Phase-12 work.
