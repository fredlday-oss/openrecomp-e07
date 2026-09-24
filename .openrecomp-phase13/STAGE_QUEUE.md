# OpenRecomp Phase 13 Stage Queue (frozen at P13-00 PASS)

Every stage terminates `PASS`, `PASS_NOT_REQUIRED`, or `FAIL`. A stage `PASS`
does not by itself promote a milestone or a target proof.

| Stage | Objective | Marker |
|---|---|---|
| P13-00 | Phase bootstrap / Phase-12 freeze / contract recovery | `OPENRECOMP_P13_00=PASS` |
| P13-01 | C0:0x02 SysEnqIntRP service V1 | `OPENRECOMP_P13_01=PASS` |
| P13-02 | C0:0x03 SysDeqIntRP service V1 | `OPENRECOMP_P13_02=PASS` |
| P13-03 | IntRP enqueue/dequeue round-trip proof | `OPENRECOMP_P13_03=PASS` |
| P13-04 | Hercules callback pointer provenance | `OPENRECOMP_P13_04=PASS` |
| P13-05 | Dynamic callback target mediation | `OPENRECOMP_P13_05=PASS` |
| P13-06 | Hercules initialization frontier loop I | `OPENRECOMP_P13_06=PASS` |
| P13-07 | ChangeClearRCnt service V1 (conditional) | `OPENRECOMP_P13_07=PASS|PASS_NOT_REQUIRED` |
| P13-08 | Timer1 / bounded virtual-time support (conditional) | `OPENRECOMP_P13_08=PASS|PASS_NOT_REQUIRED` |
| P13-09 | I_STAT / I_MASK bounded support (conditional) | `OPENRECOMP_P13_09=PASS|PASS_NOT_REQUIRED` |
| P13-10 | Hercules initialization frontier loop II | `OPENRECOMP_P13_10=PASS` |
| P13-11 | Hercules initialization proof | `OPENRECOMP_P13_11=PASS` |
| P13-20 | C0 / callback / timer fail-closed hardening | `OPENRECOMP_P13_20=PASS` |
| P13-30 | Interrupt layer consistency | `OPENRECOMP_P13_30=PASS` |
| P13-40 | Deterministic initialization replay | `OPENRECOMP_P13_40=PASS` |
| P13-50 | Post-initialization / first-frame readiness assessment | `OPENRECOMP_P13_50=PASS` |
| P13-90 | Whole Phase-13 regression | `OPENRECOMP_P13_90=PASS` |
| P13-91 | Evidence closure | `OPENRECOMP_P13_91=PASS` |
| P13-99 | Final Phase-13 verdict | `OPENRECOMP_P13_99=PASS` |

Claim markers:

- `OPENRECOMP_PHASE13_HERCULES_INITIALIZATION_PROOF` (promote only on the exact
  inherited initialization contract);
- `OPENRECOMP_PHASE13_HERCULES_FRAME_PROOF=NOT_PROVEN` (reserved);
- `OPENRECOMP_PHASE13_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (reserved);
- `OPENRECOMP_PHASE13_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (reserved).

A queue change requires `QUEUE_RECONCILIATION_REQUIRED` and a stop.
