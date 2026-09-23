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

- CURRENT_STAGE: P12-04
- LAST_COMPLETED_STAGE: P12-03
- NEXT_STAGE: P12-04

## Proof markers

- `OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (reserved)

## Stage status

| Stage | Status |
|---|---|
| P12-00 | PASS (23 checks) |
| P12-01 | PASS (35 checks) |
| P12-02 | PASS (22 checks) |
| P12-03 | PASS (22 checks) |
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

### P12-01 — B0:0x5B ChangeClearPAD service V1

PASS (35 checks). Gate `tools/test_phase12_changeclear_pad_v1.py` ran twice
through the Phase-12 stage runner with byte-identical stdout, empty stderr,
exit 0 and byte-identical JSON sidecars.

- installed the documented Phase-12 B0 surface (`0x57` GetB0Table, `0x5b`
  ChangeClearPAD) and a synthetic project-owned window (`0x1f000000`) that is
  not a recovered BIOS address;
- minimum semantics: `ChangeClearPAD(mode)` records the documented pad/card
  clear auto-acknowledge mode for `mode in {0,1}`; other values/arity fail
  closed; no SIO/interrupt/DMA/device behaviour;
- public synthetic emitter fixtures (mode 0/1) and a direct production
  dispatcher fixture verify identity, dispatch, deterministic state, void
  return, continuation, exact observables and fail-closed refusal;
- unrelated B0 entry `0x58` stays fail-closed;
- markers `OPENRECOMP_P12_01=PASS` and
  `OPENRECOMP_PHASE12_B0_5B_CHANGECLEARPAD_V1=PASS`;
- evidence: `.openrecomp-phase12/evidence/P12-01/`.

### P12-02 — complete B0:0x5B caller coverage

PASS (22 checks). Gate `tools/test_phase12_caller_coverage_v1.py` ran twice with
byte-identical stdout, empty stderr, exit 0 and byte-identical sidecars.

- independently re-derived two reachable `B0:0x57` sites (`0x80015fa4`,
  `0x80026f74`), the direct `B0:0x5B` stub (`0x80015f3c`) and seven callers;
- both `B0:0x57` sites and the direct stub resolve to `ps1.bios.B0.57` /
  `ps1.bios.B0.5b`; eight other reachable B0 indices stay fail-closed;
- direct and indirect paths converge on the Phase-12 dispatcher; no unknown-B0
  rule is emitted; committed evidence is public-safe;
- evidence: `.openrecomp-phase12/evidence/P12-02/`.

### P12-03 — GetB0Table indirect service mediation

PASS (22 checks). Gate `tools/test_phase12_b0_mediation_v1.py` ran twice with
byte-identical stdout, empty stderr, exit 0 and byte-identical sidecars.

- the real initialization path runs past the frozen P11-07 frontier; the
  synthetic table base, entry `0x5B`, derived pointers (`0x1f001884`,
  `0x1f001894`) and the eleven-word clear are all observed;
- `ChangeClearPAD` invoked 4 times; zero service failures; both reachable
  `B0:0x57` sites resolve;
- unknown table entries stay zero; no guest-code interpreter;
- new exact frontier: unresolved indirect jump at `0x80015b94`
  (`fn_80015b90`, block 468355) resolving to A0 `0x44` `FlushCache`;
- evidence: `.openrecomp-phase12/evidence/P12-03/`.

## Third-party code

`THIRD_PARTY_CODE_IMPORTED=NO`.

## Working-tree residue (preserve untouched)

The inherited untracked Phase-2/Phase-3 residue and the root untracked
`tools/test_build_package_reproducibility_v1.py` predate Phase 12 and must never
be committed, deleted or altered by Phase-12 work.
