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

- CURRENT_STAGE: COMPLETE
- LAST_COMPLETED_STAGE: P12-99
- NEXT_STAGE: NONE

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
| P12-04 | PASS (20 checks) |
| P12-05 | PASS (12 checks) |
| P12-06 | PASS (6 checks), GPU/OT/DMA NOT_PROVEN |
| P12-07 | PASS (4 checks), texture/VRAM NOT_PROVEN |
| P12-08 | PASS (3 checks), GTE/geometry NOT_PROVEN |
| P12-09 | PASS (7 checks), frame frontier blocked |
| P12-10 | PASS (8 checks), frame proof NOT_PROVEN |
| P12-20 | PASS (7 checks), fail-closed hardening |
| P12-30 | PASS (10 checks), direct/indirect consistency |
| P12-40 | PASS (4 checks), deterministic replay PASS |
| P12-90 | PASS (66 checks; 14 stages, 183 stage checks) |
| P12-91 | PASS (114 checks; 249 stage checks) |
| P12-99 | PASS (10 checks) |

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

### P12-04 — Hercules initialization frontier loop

PASS (20 checks). Gate `tools/test_phase12_init_frontier_v1.py` ran twice with
byte-identical stdout, empty stderr, exit 0 and byte-identical sidecars.

- implemented documented `ps1.bios.A0.44` `FlushCache` (void, no observable
  effect in the non-cached flat-memory model) with public positive/negative
  fixtures;
- the initialization path advances past the A0 site to the C0 interrupt-routine
  dispatcher at `0x80015f5c` (`fn_80015f58`, block 468365);
- C0 `0x02`/`0x03`/`0x0a` stay fail-closed; faithful semantics require
  interrupt delivery not modelled by the bounded architecture;
- initialization frontier recorded
  `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`; milestone B `NOT_PROVEN`;
- evidence: `.openrecomp-phase12/evidence/P12-04/`.

### P12-05 — Hercules initialization proof

PASS (12 checks). Gate `tools/test_phase12_init_proof_v1.py` ran twice with
byte-identical stdout, empty stderr, exit 0 and byte-identical sidecars.

- two fresh deterministic runs of the final-tree initialization path;
- `INIT-PREDECESSOR`/`INIT-B0-PATCH`/`INIT-DETERMINISTIC`/`INIT-NO-FABRICATION`
  pass; `INIT-BOUNDARY` and `INIT-NO-FAIL-CLOSED` fail;
- `OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`, frontier
  `0x80015f5c`, blocker `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`;
- evidence: `.openrecomp-phase12/evidence/P12-05/`.

### P12-06/07/08 — graphics promotion assessments

PASS (6/4/3 checks). The frame path is unreachable because initialization is
blocked at C0, and DMA2/OT, VRAM/texture and GTE geometry are not modelled by
the bounded runtime. The existing production typed GP0/GP1 classifier is
re-verified; the markers `OPENRECOMP_PHASE12_GPU_OT_DMA_V1`,
`OPENRECOMP_PHASE12_TEXTURE_VRAM_V1` and `OPENRECOMP_PHASE12_GTE_GEOMETRY_V1`
remain `NOT_PROVEN`.

### P12-09/10 — first-frame frontier and proof

PASS (7/8 checks). No frame-submission boundary is reachable; the frontier is
the C0 dispatcher; GPU traffic is initialization-only; the frame contract fails
on its predecessor and boundary predicates. `OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF`
remains `NOT_PROVEN`; playability/general remain reserved `NOT_PROVEN`.

### P12-20 — runtime / fail-closed hardening

PASS (7 checks). Malformed/unsupported dispatcher inputs reject (unknown
service `6`; wrong arity/mode `13`; null target read `1`), unknown B0 entries
stay zero, the production runtime has no private-fixture path and no permissive
fallback.

### P12-30/40 — path consistency and deterministic replay

PASS (10/4 checks). Direct and indirect B0:0x5B paths converge on one bounded
implementation with all seven callers accounted for; the bounded
initialization run replays byte-identically (`OPENRECOMP_PHASE12_END_TO_END_REPLAY_V1=PASS`).

### P12-90 — whole Phase-12 regression

PASS (66 checks). Frozen Phase-11 boundary and source integrity verified; all
14 required stages carry two-run deterministic `PASS` evidence and no proof
marker is `PROVEN`.

### P12-91 — evidence closure

PASS (114 checks). 15 stages audited; manifest, frozen boundary, public safety,
reconnaissance hashes and the proof matrix verified; 81 evidence files indexed,
249 committed stage checks.

### P12-99 — final bounded verdict

PASS (10 checks). `FINAL_VERDICT=PASS_BOUNDED_B0_MEDIATION_PRIVATE_FIXTURE`.
The Phase-12 infrastructure and regression integrity are `PASS`; the B0:0x5B
service, GetB0Table mediation and deterministic replay are `PASS`; the Hercules
initialization and first-frame proofs are `NOT_PROVEN`; playability and general
compatibility remain reserved `NOT_PROVEN`.

## Terminal status

```
STATUS=COMPLETE
FINAL_VERDICT=PASS_BOUNDED_B0_MEDIATION_PRIVATE_FIXTURE
OPENRECOMP_PHASE12=PASS_BOUNDED_B0_MEDIATION_PRIVATE_FIXTURE
OPENRECOMP_PHASE12_INITIALIZATION_AND_FRAME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
OPENRECOMP_PHASE12_B0_5B_CHANGECLEARPAD_V1=PASS
OPENRECOMP_PHASE12_B0_TABLE_INDIRECT_V1=PASS
OPENRECOMP_PHASE12_END_TO_END_REPLAY_V1=PASS
```

## Third-party code

`THIRD_PARTY_CODE_IMPORTED=NO`.

## Working-tree residue (preserve untouched)

The inherited untracked Phase-2/Phase-3 residue and the root untracked
`tools/test_build_package_reproducibility_v1.py` predate Phase 12 and must never
be committed, deleted or altered by Phase-12 work.
