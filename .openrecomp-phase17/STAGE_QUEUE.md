# OpenRecomp Phase 17 Stage Queue (frozen at P17-00 PASS)

Every stage terminates `PASS`, `PASS_NOT_REQUIRED`, or `FAIL`. A stage `PASS` does not by itself promote a target proof marker.

| Stage | Objective | Marker | Status |
|---|---|---|---|
| P17-00 | Phase bootstrap / Phase-16 freeze / clean control plane | `OPENRECOMP_P17_00=PASS` | PASS |
| P17-01 | Reserved: TITLE overlay payload decoding policy | `OPENRECOMP_PHASE17_TITLE_PAYLOAD_DECODING_POLICY_V1=PLANNED` | PLANNED |
| P17-02 | Reserved: TITLE overlay IR ingestion contract | `OPENRECOMP_PHASE17_TITLE_IR_CONTRACT_V1=PLANNED` | PLANNED |
| P17-03 | Reserved: TITLE overlay host translation surface | `OPENRECOMP_PHASE17_TITLE_HOST_SURFACE_V1=PLANNED` | PLANNED |
| P17-04 | Reserved: TITLE overlay deterministic replay boundary | `OPENRECOMP_PHASE17_TITLE_REPLAY_BOUNDARY_V1=PLANNED` | PLANNED |
| P17-90 | Reserved: whole Phase-17 regression suite | `OPENRECOMP_P17_90=PASS` | PLANNED |
| P17-91 | Reserved: evidence closure & source manifest audit | `OPENRECOMP_P17_91=PASS` | PLANNED |
| P17-99 | Reserved: final Phase-17 verdict | `OPENRECOMP_P17_99=PASS` | PLANNED |

Claim markers:
- `OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN` (reserved);
- `OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF=NOT_PROVEN` (reserved);
- `OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (reserved);
- `OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (reserved);
- `FIRST_FRAME_READY=NO` (reserved).
