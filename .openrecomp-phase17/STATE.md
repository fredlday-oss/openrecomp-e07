# OpenRecomp Phase 17 State

## Baseline
- Phase-16 terminal commit: `a0c26e882ca65cfc84cbec78f7e787509a4992a3`
- Phase-16 terminal tree: `7f70357c14636d56c4c8bd000f5092f7052a1425`
- Phase-15 terminal commit: `5cec005d45e8361e5ea132731661b13a72a5ed13`
- Phase-15 terminal tree: `f7d5aebe1d0db96a0850dc03123d9ad04040460d`
- Phase-14 inherited baseline commit: `830be0f7be998061e8d442134cfae511d5dd8c62`
- Phase-14 inherited baseline tree: `3b5b998dacc60eff88258509bdb5cc548b8b1401`
- Branch: `phase17/ps1-title-overlay-recompile-v1`
- Baseline Verdict: `PASS_AUTHENTIC_CDROM_TITLE_TRANSITION_POST_TITLE_FRONTIER_REMAINS`

## Proof Markers
- `OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`
- `FIRST_FRAME_READY=NO`

## Current Stage
- CURRENT_STAGE: P17-04R_REVIEW
- LAST_COMPLETED_STAGE: P17-04R
- NEXT_STAGE: HUMAN_REVIEW_REQUIRED
- FINAL_VERDICT: HUMAN_REVIEW_REQUIRED

## Stage Status
| Stage | Status | Marker |
|---|---|---|
| P17-00 | PASS | `OPENRECOMP_P17_00=PASS` |
| P17-01 | PASS | `OPENRECOMP_PHASE17_TITLE_INGESTION_V1=PASS` |
| P17-02 | PASS | `OPENRECOMP_PHASE17_TITLE_IR_CONTRACT_V1=PASS` |
| P17-03 | PASS | `OPENRECOMP_PHASE17_FRONTIER_RECONCILIATION_V1=PASS` |
| P17-04 | FAIL_REVIEW_REQUIRED | Historical gate PASS checks a block inventory, not emitted guest code; marker not established |
| P17-04R | PASS | `OPENRECOMP_P17_04R=PASS` |
| P17-05 | FAIL_REVIEW_REQUIRED | Historical gate PASS checks metadata, not a live Exec dispatch/ablation; marker not established |
| P17-06 | FAIL_REVIEW_REQUIRED | Historical gate PASS advances PCs without executing guest instruction effects; frontier marker not established |
| P17-07 | FAIL_REVIEW_REQUIRED | Historical gate PASS infers absent device events from a digest without a checked transcript; marker not established |
| P17-90 | PLANNED | `OPENRECOMP_P17_90=PASS` |
| P17-91 | PLANNED | `OPENRECOMP_P17_91=PASS` |
| P17-99 | PLANNED | `OPENRECOMP_P17_99=PASS` |

## Review stop
The original P17-04 through P17-07 `RESULT.json` files and commits remain unchanged as historical gate outputs; their PASS markers do not establish the mission's execution/emission/dispatch claims. P17-04R Revision 3 re-establishes authenticated executable emission with fresh-decode binding, corrected MIPS delay-slot timing, a reusable persistent guest-state interface, active-path exclusion, and deterministic official reruns. See `REVIEW_REQUIRED.md` for remaining stages. Do not promote the bounded terminal marker beyond P17-04R.
