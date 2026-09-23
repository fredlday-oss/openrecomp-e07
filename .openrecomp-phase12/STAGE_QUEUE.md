# OpenRecomp Phase 12 Stage Queue (frozen at P12-00 PASS)

Every stage terminates `PASS` or `FAIL`. A stage `PASS` does not by itself
promote a milestone or a target proof.

| Stage | Objective | Marker |
|---|---|---|
| P12-00 | Phase bootstrap / Phase-11 freeze / proof contracts | `OPENRECOMP_P12_00=PASS` |
| P12-01 | B0:0x5B ChangeClearPAD service V1 | `OPENRECOMP_P12_01=PASS` |
| P12-02 | Complete B0:0x5B caller coverage | `OPENRECOMP_P12_02=PASS` |
| P12-03 | GetB0Table indirect service mediation | `OPENRECOMP_P12_03=PASS` |
| P12-04 | Hercules initialization frontier loop | `OPENRECOMP_P12_04=PASS` |
| P12-05 | Hercules initialization proof | `OPENRECOMP_P12_05=PASS` |
| P12-06 | GPU DMA / DrawOTag / OT promotion | `OPENRECOMP_P12_06=PASS` |
| P12-07 | Texture / VRAM provenance promotion | `OPENRECOMP_P12_07=PASS` |
| P12-08 | GTE / geometry / OT promotion | `OPENRECOMP_P12_08=PASS` |
| P12-09 | First-frame execution frontier loop | `OPENRECOMP_P12_09=PASS` |
| P12-10 | Hercules first-frame proof | `OPENRECOMP_P12_10=PASS` |
| P12-20 | Runtime / fail-closed hardening | `OPENRECOMP_P12_20=PASS` |
| P12-30 | Direct / indirect BIOS path consistency | `OPENRECOMP_P12_30=PASS` |
| P12-40 | Deterministic end-to-end replay | `OPENRECOMP_P12_40=PASS` |
| P12-90 | Whole Phase-12 regression | `OPENRECOMP_P12_90=PASS` |
| P12-91 | Evidence closure | `OPENRECOMP_P12_91=PASS` |
| P12-99 | Final Phase-12 verdict | `OPENRECOMP_P12_99=PASS` |

Claim markers:

- `OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF` (promote only on the
  initialization contract);
- `OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF` (promote only on the frame
  contract);
- `OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (reserved);
- `OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (reserved).

A queue change requires `QUEUE_RECONCILIATION_REQUIRED` and a stop.
