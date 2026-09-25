# OpenRecomp Phase 15 State

## Mission

Advance the frozen Phase-14 bounded initialization-closure result into a genuine
deterministic Hercules initialization proof by closing only the live
hardware/MMIO state required before the semantic initialization boundary
(`A0:0x43 Exec` → TITLE entry `0x800380A0`).

## Baseline

- Phase-14 terminal branch `phase14/ps1-hercules-init-closure-v1`, commit
  `830be0f7be998061e8d442134cfae511d5dd8c62`
  (`FINAL_VERDICT=PASS_BOUNDED_INITIALIZATION_CLOSURE_FRONTIER_REMAINS`).
- Phase-15 branch `phase15/ps1-hercules-init-mmio-v1`.
- Starting frontier: `0x1F801074` (I_STAT/I_MASK) interrupt-mask MMIO, 14
  Phase-14 memory-denial events.

## Progress

- CURRENT_STAGE: P15-99
- LAST_COMPLETED_STAGE: P15-99
- NEXT_STAGE: NONE (Phase 15 Terminal Verdict Reached)

## Proof markers

- `OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE15_HERCULES_FRAME_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE15_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE15_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`
- `FIRST_FRAME_READY=NO`
- `FINAL_VERDICT=PASS_BOUNDED_INITIALIZATION_CLOSURE_FRONTIER_REMAINS`

## Stage status

| Stage | Status |
|---|---|
| P15-00 | PASS |
| P15-01 | PASS |
| P15-02 | PASS |
| P15-03 | PASS |
| P15-04 | PASS |
| P15-05 | PASS |
| P15-06 | PASS |
| P15-07 | PASS |
| P15-08 | PASS |
| P15-09 | PASS |
| P15-10 | PASS |
| P15-11 | PASS |
| P15-20 | PASS |
| P15-30 | PASS |
| P15-40 | PASS |
| P15-50 | PASS |
| P15-90 | PASS |
| P15-91 | PASS |
| P15-99 | PASS |

## Verified recovery

- The frozen Phase-14 commit/tree and its authoritative 26-entry source
  manifest pass canonical Git-blob verification.
- The repository-root `SOURCE_SHA256SUMS.txt` is unchanged from the frozen
  base. Its one missing historical entry
  (`tools/test_build_package_reproducibility_v1.py`) was already absent at that
  base; all 133 present entries match. This inherited gap was not modified.
- All 16 recovered Phase-15 Python modules/gates compile and all 14 source
  modules import with the canonical inherited module paths.
- `P15-00` and `P15-01` each pass two official runs with byte-identical stdout,
  empty stderr and deterministic evidence artifacts.

## Third-party code

`THIRD_PARTY_CODE_IMPORTED=NO`.
