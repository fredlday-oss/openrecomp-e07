# P3-91 result (PASS)

Stage: `P3-91` evidence index + limitations (frozen queue row).
Gate: `tools/test_phase3_evidence_index_v1.py` (50 checks).
Evidence: `.openrecomp-phase3/evidence/P3-91/`.

Markers issued:

- Stage marker: `OPENRECOMP_P3_91=PASS`
- Gate marker: `OPENRECOMP_PHASE3_EVIDENCE_INDEX_V1=PASS tests=50`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

## Evidence index

`evidence_index.json` indexes the complete on-disk Phase-3 evidence tree at
this boundary: **346 files**, 10495633 bytes, 314 tracked and 32 untracked
(the platform-line-ending captures plus the current stage's working files),
each with stage, path, size, sha256 and tracked status. It also records the
six control-plane files with hashes, the frozen boundary identities
(`openrecomp-phase2-pass` = `01b1d7cb...` / tree `6513eefa...`,
`openrecomp-phase1-pass` = `46c2f971...`, P2-99 result `880d2596...` and
capture `66913e57...`) and the P3-10 package identity (`cf9ab795...`,
fingerprint `9050a117...`).

Every stage directory `P3-00 .. P3-90` carries its result record; every JSON
evidence file is tracked; the stage set and control-plane set verify.

## Claim record

`claim_record.json` records:

- the reserved terminal marker `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`
  and `COREMARK_STATUS=NOT_PROVEN`;
- nine bounded proven statements (reproducible fixture, ingestion, frontier,
  reachable semantics, structure, static data, host emission, native build and
  execution with CoreMark's own validation, independent-reference equivalence,
  reproducible package and whole regression);
- eight explicit unproven areas: arbitrary MIPS32 ELF support, PS1, PS2, game
  or commercial binary compatibility, cycle accuracy and console emulation,
  self-modifying code, the `-O2` profile and runtime equivalence beyond the
  audited deterministic observable;
- eight limitations, each with its evidence and impact:

| id | limitation |
| --- | --- |
| L1 | the shared Phase-2 structural layers have no delay-slot concept |
| L2 | three `jr $at` tables and the dead `jalr` are unresolved at the shared-layer boundary (runtime-mediated, never guessed) |
| L3 | 493 of 505 reachable accesses have runtime base registers; no alias analysis |
| L4 | UNPREDICTABLE states fail closed (divide by zero, taken trap, unaligned indirect target, mul-defined HI/LO reads) |
| L5 | native reproducibility is bound to the recorded clang-cl/lld-link toolchain and host platform |
| L6 | one audited `-O1` non-PIC soft-float fixture only |
| L7 | CoreMark is not a supported target |
| L8 | the committed P3-10 package is the boundary snapshot of the tracked path |

## Verification

- 50 gate checks: source integrity (root manifest 134 entries, Phase-3
  manifest 23 entries), evidence index completeness/trackedness/stage results,
  control-plane hashes, the claim record and deterministic artifact hashing.
- Official runs: two consecutive gate invocations byte-identical (raw sha256
  `98a4b3dffd5959eadf8fb25241c84f0777ca646ebcfe8471ba7ad71b3e13d8c2`, 2046
  bytes, empty stderr, exit 0); boundary regressions (P2-99, P3-00, Phase-1
  host gates, public safety) re-passed unchanged.
- The terminal marker remains reserved and `NOT_PROVEN`; only P3-99 issues the
  verdict.

## Claim boundary

P3-91 indexes the evidence and records the bounded proven statements and the
explicit limitations. It adds no capability claim and does not issue the
terminal verdict. `COREMARK_STATUS=NOT_PROVEN`.
