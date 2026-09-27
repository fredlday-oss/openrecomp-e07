# OpenRecomp Phase 17 Stage Queue

Every stage terminates `PASS`, `PASS_NOT_REQUIRED`, or `FAIL`. A stage `PASS` does not by itself promote a target proof marker.

P17-00 froze placeholder/reserved rows before the complete Phase-17 execution contract was supplied; the authoritative mission now assigns evidence-bounded meanings. The reconciled queue is exactly:

`P17-00, P17-01, P17-02, P17-03, P17-04, P17-05, P17-06, P17-07, P17-90, P17-91, P17-99`.

| Stage | Objective | Marker | Status |
|---|---|---|---|
| P17-00 | Phase bootstrap / Phase-16 freeze / clean control plane | `OPENRECOMP_P17_00=PASS` | PASS |
| P17-01 | Authentic TITLE identity and bounded PS-X EXE ingestion | `OPENRECOMP_PHASE17_TITLE_INGESTION_V1=PASS` | PASS |
| P17-02 | Authentic TITLE payload decode and bounded direct-control-flow structure | `OPENRECOMP_PHASE17_TITLE_IR_CONTRACT_V1=PASS` | PASS |
| P17-03 | Frontier reconciliation of Phase-16 modelled post-dispatch addresses | `OPENRECOMP_PHASE17_FRONTIER_RECONCILIATION_V1=PASS` | PASS |
| P17-04 | Authentic TITLE emission with provenance and exclusion of hand-authored guest flow | gate PASS does not establish emission | FAIL_REVIEW_REQUIRED |
| P17-05 | Verified A0:0x43 Exec dispatch to authentic emitted TITLE entry and causality | gate PASS does not establish live dispatch | FAIL_REVIEW_REQUIRED |
| P17-06 | Bounded authentic TITLE execution to the exact first semantic/budget frontier | gate PASS does not establish execution | FAIL_REVIEW_REQUIRED |
| P17-07 | Authentic frontier assessment for GPU, DMA, OT, framebuffer, and initialization predicates | gate PASS does not establish observations | FAIL_REVIEW_REQUIRED |
| P17-05R | Authentic execution continuation across the TITLE -> main-EXE transition | `OPENRECOMP_P17_05R=PASS` | PASS (integrated) |
| P17-06R | Live BIOS/Exec and device side-effect frontier past the P17-05R stop | `OPENRECOMP_P17_06R=PASS` | PASS (worker; controller review pending) |
| P17-90 | Whole Phase-17 regression suite | `OPENRECOMP_P17_90=PASS` | PLANNED |
| P17-91 | Evidence closure & source manifest audit | `OPENRECOMP_P17_91=PASS` | PLANNED |
| P17-99 | Final Phase-17 verdict | `OPENRECOMP_P17_99=PASS` | PLANNED |

Claim markers:
- `OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`;
- `OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF=NOT_PROVEN`;
- `OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`;
- `OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`;
- `FIRST_FRAME_READY=NO`.

## Worker closure — P17-06R
- P17-06R: PASS (worker; controller review pending) — `OPENRECOMP_P17_06R=PASS`; authentic continuation frontier advanced from the P17-05R stop `0x80026cc8` through 4 newly authenticated main-EXE regions (8340 authenticated records) to the bounded stop `CONTINUATION_BUDGET_REACHED` (`last_successfully_executed_pc=0x8001aa08`, `attempted_frontier_pc=0x8001aa0c`, 8192 additional instructions).
- P17-06R device/BIOS transcript: 1 BIOS A0 dispatch (table index 0x2b) and 1590 device events (GPUSTAT_READ 1587, INTERRUPT_ACCESS 2, TIMER_ACCESS 1), sha256 `d7e222c87726748ced23dd60c2b1ba138625227c984dac587be6a5761695fd3a`; BIOS internals NOT_MODELED.
- P17-07R: OUTSTANDING (replacement contract; historical P17-05..P17-07 remain FAIL_REVIEW_REQUIRED).

## Worker closure — P17-05R
- P17-05R: PASS (integrated) — `OPENRECOMP_P17_05R=PASS`; authentic continuation frontier advanced from the P17-04R entry `0x80011af0` to `0x80026cc8` (`PC_NOT_IN_AUTHENTICATED_TABLE`).

## Controller closure — P17-04R (Revision 4)
- P17-04R: PASS (integrated) — `OPENRECOMP_P17_04R=PASS` + `OPENRECOMP_P17_04R_REV4=PASS`, integrated at `0ab4e7eb2ed4393cec7f61a79705d2c44bbc4441`.
- P17-05R / P17-06R / P17-07R: OUTSTANDING (replacement contracts required; historical P17-05..P17-07 remain FAIL_REVIEW_REQUIRED).
- P17-90 / P17-91 / P17-99: not executed.
