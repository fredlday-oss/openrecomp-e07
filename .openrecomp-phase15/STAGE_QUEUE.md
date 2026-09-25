# OpenRecomp Phase 15 Stage Queue (frozen at P15-00 PASS)

Every stage terminates `PASS`, `PASS_NOT_REQUIRED`, or `FAIL`. A stage `PASS`
does not by itself promote a milestone or a target proof.

| Stage | Objective | Marker |
|---|---|---|
| P15-00 | Phase bootstrap / Phase-14 freeze / contract | `OPENRECOMP_P15_00=PASS` |
| P15-01 | Interrupt MMIO contract + unit model | `OPENRECOMP_PHASE15_INTERRUPT_MMIO_CONTRACT_V1=PASS` |
| P15-02 | Live `I_STAT`/`I_MASK` production semantics | `OPENRECOMP_PHASE15_I_STAT_I_MASK_V1=PASS` |
| P15-03 | Live frontier replay I | `OPENRECOMP_P15_03=PASS` |
| P15-04 | `SYS_CONTROL`/`COM_DELAY` + DMA2 register state | `OPENRECOMP_PHASE15_SYS_CONTROL_V1=PASS` / `OPENRECOMP_PHASE15_DMA2_REGISTER_STATE_V1=PASS` |
| P15-05 | Null-store root-cause closure | `OPENRECOMP_PHASE15_NULL_STORE_ROOT_CAUSE_V1=PASS` |
| P15-06 | Timer1 / frame-tick deterministic time model | `OPENRECOMP_PHASE15_TIMER1_VIRTUAL_TIME_V1=PASS` |
| P15-07 | GPUSTAT bounded status model | `OPENRECOMP_PHASE15_GPUSTAT_V1=PASS` |
| P15-08 | Live frontier replay II | `OPENRECOMP_P15_08=PASS` |
| P15-09 | Initialization boundary recovery | `OPENRECOMP_PHASE15_INIT_BOUNDARY_V1=PASS\|NOT_PROVEN` |
| P15-10 | `INIT-NO-FAIL-CLOSED` proof | `OPENRECOMP_PHASE15_INIT_NO_FAIL_CLOSED_V1=PASS\|NOT_PROVEN` |
| P15-11 | Hercules initialization proof | `OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF=PASS\|NOT_PROVEN` |
| P15-20 | Hardening / fail-closed | `OPENRECOMP_P15_20=PASS` |
| P15-30 | MMIO / BIOS / runtime consistency | `OPENRECOMP_P15_30=PASS` |
| P15-40 | Deterministic initialization replay | `OPENRECOMP_PHASE15_INITIALIZATION_REPLAY_V1=PASS\|NOT_PROVEN` |
| P15-50 | First-frame readiness assessment | `OPENRECOMP_P15_50=PASS` |
| P15-90 | Whole Phase-15 regression | `OPENRECOMP_P15_90=PASS` |
| P15-91 | Evidence closure | `OPENRECOMP_P15_91=PASS` |
| P15-99 | Final Phase-15 verdict | `OPENRECOMP_P15_99=PASS` |

Claim markers:

- `OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF` (promote only on the exact
  inherited initialization contract);
- `OPENRECOMP_PHASE15_HERCULES_FRAME_PROOF=NOT_PROVEN` (reserved);
- `OPENRECOMP_PHASE15_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (reserved);
- `OPENRECOMP_PHASE15_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (reserved);
- `FIRST_FRAME_READY=YES|NO`.

A queue change requires `QUEUE_RECONCILIATION_REQUIRED` and a stop.

## Recorded progress (objective rows frozen)

- `P15-00`: `PASS`
- `P15-01`: `PASS`
- `P15-02`: `IN_PROGRESS`
