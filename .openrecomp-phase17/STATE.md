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
- CURRENT_STAGE: P17-05R
- LAST_COMPLETED_STAGE: P17-04R (Revision 4 accepted and integrated)
- NEXT_STAGE: P17-05R
- next_stage: P17-05R
- FINAL_VERDICT: PHASE17_IN_PROGRESS
- REVIEW_GATE: P17-04R Revision 4 was independently re-verified by the controller (canonical dual reruns, 0 non-PASS, regenerated evidence byte-identical to the committed evidence) and integrated by fast-forward to `0ab4e7eb2ed4393cec7f61a79705d2c44bbc4441`. The remaining fail-closed review stop covers P17-05R through P17-07R; see `.openrecomp-phase17/REVIEW_REQUIRED.md` and `.openrecomp-phase17/evidence/P17-04R/CONTROLLER_REVIEW.md`.

## Revision 4 (P17-04R) authoritative metadata
- STATUS: PASS (integrated into the controller branch)
- base_commit: 937e5fa0a8e353808620b82b0203ab608e2d8cf4
- worker_branch: agent/kimi-phase17-p17-04r-rev4
- resulting_candidate_commit: 0ab4e7eb2ed4393cec7f61a79705d2c44bbc4441
- resulting_candidate_commit_resolver: git rev-parse agent/kimi-phase17-p17-04r-rev4
- authentic_frontier: last_successfully_executed_pc=0x80038130, attempted_frontier_pc=0x80011af0, frontier_pc=0x80011af0, stop_reason=PC_NOT_IN_AUTHENTICATED_TABLE
- authentic_jal: owner_pc=0x8003812c, delay_slot_pc=0x80038130, pending_transfer_type=DIRECT_CALL, pending_transfer_target=0x80011af0
- semantic_vocabulary_counts: implemented=45, exercised=derived-from-execution-trace (see `.openrecomp-phase17/evidence/P17-04R/semantic_vocabulary.json`)
- persisted_private_artifacts: generated source, generated header, generated harness, private authenticated mapping, build metadata, compiled shared object, compiled executable under `$OPENRECOMP_P17_PRIVATE_BUILD_ROOT/official-run-{1,2}` (configured default private build root; never committed)
- linkage_exclusion: handwritten title-transition substitute excluded at the linkage level (`TITLE_TRANSITION_CODE`, `p16_emission_v1`, `p16_record_title_transition` absent); forbidden-symbol negative control detected
- next_stage: P17-05R

## Stage Status
| Stage | Status | Marker |
|---|---|---|
| P17-00 | PASS | `OPENRECOMP_P17_00=PASS` |
| P17-01 | PASS | `OPENRECOMP_PHASE17_TITLE_INGESTION_V1=PASS` |
| P17-02 | PASS | `OPENRECOMP_PHASE17_TITLE_IR_CONTRACT_V1=PASS` |
| P17-03 | PASS | `OPENRECOMP_PHASE17_FRONTIER_RECONCILIATION_V1=PASS` |
| P17-04 | FAIL_REVIEW_REQUIRED | Historical gate PASS checks a block inventory, not emitted guest code; marker not established |
| P17-04R | PASS (integrated) | `OPENRECOMP_P17_04R=PASS` + `OPENRECOMP_P17_04R_REV4=PASS` |
| P17-05 | FAIL_REVIEW_REQUIRED | Historical gate PASS checks metadata, not a live Exec dispatch/ablation; marker not established |
| P17-06 | FAIL_REVIEW_REQUIRED | Historical gate PASS advances PCs without executing guest instruction effects; frontier marker not established |
| P17-07 | FAIL_REVIEW_REQUIRED | Historical gate PASS infers absent device events from a digest without a checked transcript; marker not established |
| P17-90 | PLANNED | `OPENRECOMP_P17_90=PASS` |
| P17-91 | PLANNED | `OPENRECOMP_P17_91=PASS` |
| P17-99 | PLANNED | `OPENRECOMP_P17_99=PASS` |

## Review stop
The original P17-04 through P17-07 `RESULT.json` files and commits remain unchanged as historical gate outputs; their PASS markers do not establish the mission's execution/emission/dispatch claims. P17-04R Revision 4 re-establishes authenticated executable emission with fresh-decode binding, corrected MIPS delay-slot timing (including authentic JAL pending-transfer/delay-slot frontier semantics), a reusable persistent guest-state interface, persistent private build artifacts, separated implemented/exercised semantic vocabulary, linkage-level exclusion of the historical handwritten substitute, and deterministic official reruns. See `REVIEW_REQUIRED.md` for remaining stages. Do not promote the bounded terminal marker beyond P17-04R.
