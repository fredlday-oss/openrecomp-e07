# OpenRecomp Phase 17 Stage Queue

Every stage terminates `PASS`, `PASS_NOT_REQUIRED`, or `FAIL`. A stage `PASS` does not by itself promote a target proof marker.

P17-00 froze placeholder/reserved rows before the complete Phase-17 execution contract was supplied; the authoritative mission now assigns evidence-bounded meanings. The reconciled queue is exactly:

`P17-00, P17-01, P17-02, P17-03, P17-04, P17-05, P17-06, P17-07, P17-90, P17-91, P17-99`.

| Stage | Objective | Marker | Status |
|---|---|---|---|
| P17-00 | Phase bootstrap / Phase-16 freeze / clean control plane | `OPENRECOMP_P17_00=PASS` | PASS |
| P17-01 | Authentic TITLE identity and bounded PS-X EXE ingestion | `OPENRECOMP_PHASE17_TITLE_INGESTION_V1=PASS` | PASS |
| P17-02 | Authentic TITLE payload decode and bounded direct-control-flow structure | `OPENRECOMP_PHASE17_TITLE_IR_CONTRACT_V1=PASS` | PLANNED |
| P17-03 | TITLE overlay host translation surface | `OPENRECOMP_PHASE17_TITLE_HOST_SURFACE_V1=PLANNED` | PLANNED |
| P17-04 | TITLE overlay deterministic replay boundary | `OPENRECOMP_PHASE17_TITLE_REPLAY_BOUNDARY_V1=PLANNED` | PLANNED |
| P17-05 | Verified A0:0x43 Exec dispatch to authentic emitted TITLE entry and causality | `OPENRECOMP_PHASE17_EXEC_DISPATCH_CAUSALITY_V1=PLANNED` | PLANNED |
| P17-06 | Bounded authentic TITLE execution to the exact first semantic/budget frontier | `OPENRECOMP_PHASE17_AUTHENTIC_EXECUTION_FRONTIER_V1=PLANNED` | PLANNED |
| P17-07 | Authentic frontier assessment for GPU, DMA, OT, framebuffer, and initialization predicates | `OPENRECOMP_PHASE17_FRONTIER_ASSESSMENT_V1=PLANNED` | PLANNED |
| P17-90 | Whole Phase-17 regression suite | `OPENRECOMP_P17_90=PASS` | PLANNED |
| P17-91 | Evidence closure & source manifest audit | `OPENRECOMP_P17_91=PASS` | PLANNED |
| P17-99 | Final Phase-17 verdict | `OPENRECOMP_P17_99=PASS` | PLANNED |

Claim markers:
- `OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`;
- `OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF=NOT_PROVEN`;
- `OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`;
- `OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`;
- `FIRST_FRAME_READY=NO`.
