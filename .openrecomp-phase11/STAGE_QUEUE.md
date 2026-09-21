# OpenRecomp Phase 11 Stage Queue (frozen at P11-00 PASS)

Every stage terminates `PASS` or `FAIL`. A stage `PASS` does not by itself
promote a milestone; milestone promotion follows the scope rules.

| Stage | Objective | Marker |
|---|---|---|
| P11-00 | Phase-11 boundary + control plane | `OPENRECOMP_P11_00=PASS` |
| P11-01 | Milestone-A progress causality (deterministic execution-budget bisection and trace analysis) | `OPENRECOMP_P11_01=PASS` |
| P11-02 | Dynamic indirect-control frontier (resolve exactly the causal frontier using dynamic target evidence; never guess) | `OPENRECOMP_P11_02=PASS` |
| P11-03 | Event / interrupt / DMA progress contract (causal A/B; implement only proven-necessary behaviour) | `OPENRECOMP_P11_03=PASS` |
| P11-04 | Milestone B: initialization completion (bounded semantic boundary + state digest) | `OPENRECOMP_P11_04=PASS` |
| P11-05 | GPU command-stream frontier (GP0/GP1 writes, ordering, classifications) | `OPENRECOMP_P11_05=PASS` |
| P11-06 | GPU/DMA/VRAM semantic closure (minimum evidence-required path) | `OPENRECOMP_P11_06=PASS` |
| P11-07 | Milestone D: first valid frame (commercial-artwork-independent criterion) | `OPENRECOMP_P11_07=PASS` |
| P11-08 | CD-ROM / overlay / resource-loading frontier | `OPENRECOMP_P11_08=PASS` |
| P11-09 | Controller / event / SPU frontier (deterministic replay format) | `OPENRECOMP_P11_09=PASS` |
| P11-10 | Title/menu progression (milestones E and F) | `OPENRECOMP_P11_10=PASS` |
| P11-11 | Milestone G: controllable gameplay (scripted input -> reproducible guest state change) | `OPENRECOMP_P11_11=PASS` |
| P11-12 | Playability hardening + reproducibility | `OPENRECOMP_P11_12=PASS` |
| P11-90 | Whole-project regression (Phase-1 .. Phase-11) | `OPENRECOMP_P11_90=PASS` |
| P11-91 | Evidence closure + milestone matrix | `OPENRECOMP_P11_91=PASS` |
| P11-99 | Final bounded verdict | `OPENRECOMP_P11_99=PASS` |

Claim markers:

- `OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF` (promote only if
  milestone B is actually proven);
- `OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF` (promote only if milestone D is
  actually proven);
- `OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF` (promote only if milestone G
  is actually proven);
- `OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent).

A queue change requires `QUEUE_RECONCILIATION_REQUIRED` and a stop.
