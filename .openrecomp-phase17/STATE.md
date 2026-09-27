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
- CURRENT_STAGE: P17-99
- LAST_COMPLETED_STAGE: P17-99 (terminal Phase-17 closure; worker candidate under review, then integrated by the controller)
- NEXT_STAGE: NONE (Phase 17 terminally closed; Phase 18 not started)
- next_stage: NONE
- FINAL_VERDICT: PASS_BOUNDED_CHECKED_DEVICE_FRONTIER
- REVIEW_GATE: terminally closed at P17-99. P17-04R Revision 4, P17-05R, P17-06R, P17-07R, P17-90 and P17-91 were each independently re-verified and integrated; see REVIEW_REQUIRED_TERMINAL_STATE=RETIRED in `.openrecomp-phase17/REVIEW_REQUIRED.md` and the per-stage `CONTROLLER_REVIEW.md` documents. No stale review stop remains.

## P17-07R authoritative metadata (checked device-frontier assessment)
- STATUS: PASS (controller reviewed and INTEGRATED; see `evidence/P17-07R/CONTROLLER_REVIEW.md`)
- base_commit: 2701415223dd182a40cf257c849952a6ce63ee08
- worker_branch: agent/deepseek-phase17-p17-07r-r1
- resulting_candidate_commit: b553f70163fbd660252a3fcdaa77eee672af0f48
- resulting_candidate_commit_resolver: git rev-parse agent/deepseek-phase17-p17-07r-r1
- controller_verification: independent dual runs (default + fresh private build root) exit 0, empty stderr, `P17-07R_CHECKS=93`, zero FAIL/ERROR, stdout byte-identical run-to-run and identical to committed `run1.txt`, full 12-file evidence directory byte-identical to committed; independent re-derivation of base 7001 + added 3/86/623/627 = 8340 records with 8340 provenance digests; 16 controller-authored tamper cases all fail closed; marker syntax clean
- supersedes_historical_stage: P17-07 (whose every observation hard-coded `encountered: false` from a digest, with no checked transcript)
- source_stage: P17-06R; the committed P17-06R transcript is re-verified by digest and left byte-untouched
- transcript_binding: sha256 d7e222c87726748ced23dd60c2b1ba138625227c984dac587be6a5761695fd3a, 1591 events (device 1590, BIOS dispatch 1)
- independent_rederivation: authenticated record set re-derived from the frozen decoder without compilation — base 7001 + added 3/86/623/627 = 8340 records, matching the committed P17-06R region log and counts (title 6995, mainexe 1345); 8340 provenance digests re-derived; poll owner 0x8001a9fc digest matched
- observation_classes (7, all resolved from the checked transcript): `gpu_wait_poll` ENCOUNTERED (1587 GPUSTAT reads, all zero under `ZERO_FILL_RECORDED`, dominant owner 0x8001a9fc is a `lw`); `gpu_writes`, `dma2`, `framebuffer_activity` NOT_ENCOUNTERED (no matching event in the instrumented surface); `ordering_table_writes`, `ot_traversal`, `initialization_predicates` NOT_ESTABLISHED (guest RAM stores and BIOS internals are not instrumented, so no conclusion is drawn either way)
- key_finding: 1586 of 1590 device events are repeated GPUSTAT wait-poll reads returning zero; under the declared device model the guest cannot evaluate its wait exit condition, so this is the binding constraint on the frontier
- negative_controls: transcript digest mismatch, unprovenanced owner, altered provenance digest, inflated device count, continuation digest mismatch, emptied frontier, each of six removed frontier fields, continuation entry-PC mismatch, promotion attempt, empty transcript, missing transcript — all fail closed
- marker: `OPENRECOMP_PHASE17_CHECKED_DEVICE_FRONTIER_ASSESSMENT_V1=PASS` and `OPENRECOMP_P17_07R=PASS`
- proof boundaries unchanged: initialization/frame/playability/general compatibility remain NOT_PROVEN; `FIRST_FRAME_READY=NO`
- next_stage: P17-91

## P17-91 authoritative metadata (evidence closure & source manifest audit)
- STATUS: PASS (controller reviewed and INTEGRATED)
- base_commit: 724d3d4c8ff9a58702d05a5f5fb7aaf503bf5649
- worker_branch: agent/deepseek-phase17-p17-91-r1
- resulting_candidate_commit: 84e3e8ae19bcab79ef819e937d1b1361f5628b0c (tree 992862fb456ddfe579b24c40352b737d108a5dc4)
- resulting_candidate_commit_resolver: git rev-parse agent/deepseek-phase17-p17-91-r1
- gate: `python3 .openrecomp-phase17/src/p17_stage_runner_v1.py --stage P17-91 --script tools/test_phase17_evidence_closure_v1.py --evidence-dir .openrecomp-phase17/evidence/P17-91 --tests-json p17_91_tests.json`
- checks: 153 PASS, 0 FAIL (`P17-91_CHECKS=153`); dual runs exit 0, empty stderr, stdout byte-identical; `sha256(run1.txt)=6ad7f44153a35483827c0c8e206eadbc1e140c1354f386bc6dca8ccd9e190f83`; `gate_sha256=6d3f040b69a44b3004412209a537ada51ac9b446f32c3af39a7041af24904a83`
- controller_verification: independent fresh-root dual runs (byte-identical stdout, empty stderr, rc 0) and a clean-root in-place regeneration that leaves `git status --porcelain` empty (13 of 14 JSON documents byte-identical to the committed evidence; sole divergence `official_runs.json` is the echoed `--evidence-dir` invocation string only); independent re-derivation of the public-safety scan, the 41-entry source manifest (`sha256sum -c` all OK; `OPENRECOMP_PHASE17_SOURCE_INTEGRITY=PASS entries=41`), evidence closure, dual-run determinism, marker ledger and prior-phase integrity (16 trees); controller-authored manifest-digest and removed-entry tamper cases both detected.
- reported_finding_resolved: the worker surfaced (not waived) two literal `/home/<user>/…` paths in the controller-authored `P17-90/CONTROLLER_REVIEW.md`; the controller fixed them at `69c4611` and regenerated the P17-91 evidence. Post-fix `public_safety.json.review_document_findings` and `RESULT.json.findings` are empty.
- scope: terminal consistency gate only; promotes no proof marker and proves nothing about emulation
- marker: `OPENRECOMP_P17_91=PASS` and `OPENRECOMP_PHASE17_EVIDENCE_CLOSURE_V1=PASS`
- proof boundaries unchanged: initialization/frame/playability/general compatibility remain NOT_PROVEN; `FIRST_FRAME_READY=NO`
- next_stage: P17-99

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

## P17-06R authoritative metadata (live BIOS/Exec and device side-effect frontier)
- STATUS: PASS (worker; controller review pending)
- base_commit: 8735bf34ba3884d19a66818d92ddd8004dc87b17
- worker_branch: agent/deepseek-phase17-p17-06r-r1
- resulting_candidate_commit: PENDING_FINAL_COMMIT
- resulting_candidate_commit_resolver: git rev-parse agent/deepseek-phase17-p17-06r-r1
- continuation_entry_pc: 0x80026cc8 (derived from the recorded P17-05R frontier attempted_frontier_pc; never hard-coded)
- p17_05r_frontier_steps_reproduced: 78 (the live replay reproduces the recorded P17-05R executed-instruction count before reaching the continuation entry)
- authentic_frontier: stop_reason=CONTINUATION_BUDGET_REACHED, last_successfully_executed_pc=0x8001aa08, attempted_frontier_pc=0x8001aa0c, frontier_pc=0x8001aa08, continuation_executed_count=8192, executed_instruction_count=8270, distinct_executed_pc_count=346
- newly_authenticated_records: title=6995, mainexe=1345, total=8340 (provenance chain: SLUS_005.29 / TITLE payload SHA-256 -> PS-X EXE header -> file offset -> guest address -> word -> fresh decode -> record)
- newly_authenticated_regions: 0x80026cc8 (+3), 0x80011b08 (+86), 0x80012e8c (+623), 0x8001a908 (+627)
- bios_dispatch_events: 1 (vector A0, table index 0x2b, owning authenticated instruction 0x80026ccc, delay slot 0x80026cd0, return PC 0x8004ffc4)
- device_events: 1590 (GPUSTAT_READ 1587, INTERRUPT_ACCESS 2, TIMER_ACCESS 1)
- transcript: sha256 d7e222c87726748ced23dd60c2b1ba138625227c984dac587be6a5761695fd3a, 1591 events
- semantic_vocabulary_counts: implemented=55 (45 P17-05R + lwl/lwr/swl/swr/div/divu/mthi/mtlo/add/sub), exercised=derived-from-execution
- device_layer_model: BIOS dispatch envelope + return-to-RA only; BIOS internals NOT_MODELED; MMIO reads zero-filled and recorded; MMIO writes recorded and not applied
- persisted_private_artifacts: generated source/header/harness, private authenticated mapping, build metadata, compiled shared object/executable and the transcript under the configured private build root (never committed)
- next_stage: P17-07R

## P17-05R authoritative metadata (bounded continuation)
- STATUS: PASS (worker; controller review pending)
- base_commit: 36be03b5756726a20ecd69735b41cb5eba795155
- worker_branch: agent/deepseek-phase17-p17-05r-r1
- resulting_candidate_commit: PENDING_FINAL_COMMIT
- resulting_candidate_commit_resolver: git rev-parse agent/deepseek-phase17-p17-05r-r1
- authentic_frontier: last_successfully_executed_pc=0x8004ffc0, attempted_frontier_pc=0x80026cc8, frontier_pc=0x80026cc8, stop_reason=PC_NOT_IN_AUTHENTICATED_TABLE
- p17_04r_frontier_reproduced: title_prefix_executed_count=37, title_prefix_last_executed_pc=0x80038130, continuation_entry=0x80011af0
- newly_authenticated_mainexe_records: 6 (provenance chain: SLUS_005.29 SHA-256 -> PS-X EXE header -> file offset -> guest address -> word -> fresh decode -> record)
- continuation_budget_used: 6 newly authenticated main-EXE instructions (bound 4096)
- persisted_private_artifacts: generated source/header/harness, private authenticated mapping, build metadata, compiled shared object/executable under the configured private build root (never committed)
- next_stage: P17-06R

## Stage Status
| Stage | Status | Marker |
|---|---|---|
| P17-00 | PASS | `OPENRECOMP_P17_00=PASS` |
| P17-01 | PASS | `OPENRECOMP_PHASE17_TITLE_INGESTION_V1=PASS` |
| P17-02 | PASS | `OPENRECOMP_PHASE17_TITLE_IR_CONTRACT_V1=PASS` |
| P17-03 | PASS | `OPENRECOMP_PHASE17_FRONTIER_RECONCILIATION_V1=PASS` |
| P17-04 | FAIL_REVIEW_REQUIRED | Historical gate PASS checks a block inventory, not emitted guest code; marker not established |
| P17-04R | PASS (integrated) | `OPENRECOMP_P17_04R=PASS` + `OPENRECOMP_P17_04R_REV4=PASS` |
| P17-05R | PASS (integrated) | `OPENRECOMP_P17_05R=PASS` |
| P17-06R | PASS (integrated) | `OPENRECOMP_P17_06R=PASS` |
| P17-05 | FAIL_REVIEW_REQUIRED | Historical gate PASS checks metadata, not a live Exec dispatch/ablation; marker not established |
| P17-06 | FAIL_REVIEW_REQUIRED | Historical gate PASS advances PCs without executing guest instruction effects; frontier marker not established |
| P17-07 | FAIL_REVIEW_REQUIRED | Historical gate PASS infers absent device events from a digest without a checked transcript; marker not established |
| P17-07R | PASS (integrated) | `OPENRECOMP_P17_07R=PASS` |
| P17-90 | PASS (integrated) | `OPENRECOMP_P17_90=PASS` |
| P17-91 | PASS (integrated) | `OPENRECOMP_P17_91=PASS` + `OPENRECOMP_PHASE17_EVIDENCE_CLOSURE_V1=PASS` |
| P17-99 | PASS | `OPENRECOMP_P17_99=PASS` + `OPENRECOMP_PHASE17_TERMINAL_V1=PASS` |

## Review stop
The original P17-04 through P17-07 `RESULT.json` files and commits remain unchanged as historical gate outputs; their PASS markers do not establish the mission's execution/emission/dispatch claims. P17-04R Revision 4 re-establishes authenticated executable emission with fresh-decode binding, corrected MIPS delay-slot timing (including authentic JAL pending-transfer/delay-slot frontier semantics), a reusable persistent guest-state interface, persistent private build artifacts, separated implemented/exercised semantic vocabulary, linkage-level exclusion of the historical handwritten substitute, and deterministic official reruns. See `REVIEW_REQUIRED.md` for remaining stages. Do not promote the bounded terminal marker beyond P17-04R.
