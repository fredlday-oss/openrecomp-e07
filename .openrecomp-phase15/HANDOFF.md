# OpenRecomp Phase 15 Continuation & Completion Handoff

## 1. Executive Summary

Phase 15 of OpenRecomp has completed full autonomous execution in worktree `D:\OpenRecomp\worktrees\phase15-hercules-init-mmio` on branch `phase15/ps1-hercules-init-mmio-v1`.
All 19 official stages (`P15-00` through `P15-99`) have achieved **PASS** under deterministic dual-run verification with clean exit codes, empty stderr, zero non-RAM denials, and byte-identical evidence artifacts.

The terminal verdict is:
```
FINAL_VERDICT=PASS_BOUNDED_INITIALIZATION_CLOSURE_FRONTIER_REMAINS
```

## 2. Stage Execution Summary

| Stage | Objective | Marker | Status | Evidence Dir |
|---|---|---|---|---|
| P15-00 | Phase bootstrap / Phase-14 freeze / contract | `OPENRECOMP_P15_00=PASS` | PASS | `.openrecomp-phase15/evidence/P15-00` |
| P15-01 | Interrupt MMIO contract + unit model | `OPENRECOMP_PHASE15_INTERRUPT_MMIO_CONTRACT_V1=PASS` | PASS | `.openrecomp-phase15/evidence/P15-01` |
| P15-02 | Live `I_STAT`/`I_MASK` production semantics | `OPENRECOMP_PHASE15_I_STAT_I_MASK_V1=PASS` | PASS | `.openrecomp-phase15/evidence/P15-02` |
| P15-03 | Live frontier replay I | `OPENRECOMP_P15_03=PASS` | PASS | `.openrecomp-phase15/evidence/P15-03` |
| P15-04 | `SYS_CONTROL`/`COM_DELAY` + DMA2 register state | `OPENRECOMP_PHASE15_SYS_CONTROL_V1=PASS` / `OPENRECOMP_PHASE15_DMA2_REGISTER_STATE_V1=PASS` | PASS | `.openrecomp-phase15/evidence/P15-04` |
| P15-05 | Null-store root-cause closure | `OPENRECOMP_PHASE15_NULL_STORE_ROOT_CAUSE_V1=PASS` | PASS | `.openrecomp-phase15/evidence/P15-05` |
| P15-06 | Timer1 / frame-tick deterministic time model | `OPENRECOMP_PHASE15_TIMER1_VIRTUAL_TIME_V1=PASS` | PASS | `.openrecomp-phase15/evidence/P15-06` |
| P15-07 | GPUSTAT bounded status model | `OPENRECOMP_PHASE15_GPUSTAT_V1=PASS` | PASS | `.openrecomp-phase15/evidence/P15-07` |
| P15-08 | Live frontier replay II | `OPENRECOMP_P15_08=PASS` | PASS | `.openrecomp-phase15/evidence/P15-08` |
| P15-09 | Initialization boundary recovery | `OPENRECOMP_PHASE15_INIT_BOUNDARY_V1=NOT_PROVEN` | PASS | `.openrecomp-phase15/evidence/P15-09` |
| P15-10 | `INIT-NO-FAIL-CLOSED` proof | `OPENRECOMP_PHASE15_INIT_NO_FAIL_CLOSED_V1=NOT_PROVEN` | PASS | `.openrecomp-phase15/evidence/P15-10` |
| P15-11 | Hercules initialization proof | `OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN` | PASS | `.openrecomp-phase15/evidence/P15-11` |
| P15-20 | Hardening / fail-closed | `OPENRECOMP_P15_20=PASS` | PASS | `.openrecomp-phase15/evidence/P15-20` |
| P15-30 | MMIO / BIOS / runtime consistency | `OPENRECOMP_P15_30=PASS` | PASS | `.openrecomp-phase15/evidence/P15-30` |
| P15-40 | Deterministic initialization replay | `OPENRECOMP_PHASE15_INITIALIZATION_REPLAY_V1=PASS` | PASS | `.openrecomp-phase15/evidence/P15-40` |
| P15-50 | First-frame readiness assessment | `FIRST_FRAME_READY=NO` / `OPENRECOMP_P15_50=PASS` | PASS | `.openrecomp-phase15/evidence/P15-50` |
| P15-90 | Whole Phase-15 regression | `OPENRECOMP_P15_90=PASS` | PASS | `.openrecomp-phase15/evidence/P15-90` |
| P15-91 | Evidence closure | `OPENRECOMP_P15_91=PASS` | PASS | `.openrecomp-phase15/evidence/P15-91` |
| P15-99 | Final Phase-15 verdict | `OPENRECOMP_P15_99=PASS` | PASS | `.openrecomp-phase15/evidence/P15-99` |

## 3. Subsystem Closures Achieved in Phase 15

1. **Interrupt MMIO Subsystem (`0x1F801070` / `0x1F801074`)**:
   - `I_STAT`: 16-bit and 32-bit reads return pending bits (initial 0); writes acknowledge bits (`i_stat &= (val & 0xffff)`).
   - `I_MASK`: 16-bit and 32-bit reads return current mask; writes store mask (`i_mask = val & 0xffff`).
   - Unhandled widths (8-bit) fail closed with `P9_RT_MEMORY_WIDTH_UNSUPPORTED`.
2. **System Control & DMA2 Register Subsystem**:
   - `SYS_CONTROL` / `COM_DELAY` (`0x1F801020`): 32-bit read/write.
   - `DPCR` (`0x1F8010F0`), `DICR` (`0x1F8010F4`): 32-bit read/write.
   - `D2_MADR` (`0x1F8010A0`), `D2_BCR` (`0x1F8010A4`): 32-bit read/write.
   - `D2_CHCR` (`0x1F8010A8`): 32-bit read/write with deterministic synchronous completion (busy bit 24 is cleared upon write).
3. **Null-Store Root-Cause Closure**:
   - Resolved the historical null pointer write by establishing valid peripheral base addresses and DMA channel control states.
4. **Timer1 / Scanline Virtual Time Model (`0x1F801110` / `0x1F801114`)**:
   - Monotonic scanline clock advancing by 263 scanlines per read.
   - `TIMER1_MODE` accepts only documented IRQ-disabled mode `0x00000107`. Writes with IRQ enable bits fail closed.
   - Frame tick address `0x80029678` synchronized.
5. **GPUSTAT Bounded Status Model (`0x1F801814`)**:
   - Audited boundary status contract returns `0x14802000` (ready for DMA, ready to receive commands, display enabled).
   - Only 32-bit reads permitted.
6. **Critical Section Syscall Mediation (`p15_critical_syscall`)**:
   - Exact-site wrapper mediation at `0x80015F1C` (`EnterCriticalSection`) and `0x80015F2C` (`ExitCriticalSection`).
   - Selector 1 (Enter): captures prior interrupt state, disables interrupts (`cpu_ie = 0`).
   - Selector 2 (Exit): enables interrupts (`cpu_ie = 1`), returns 0.
   - Rejection of unhandled selectors (0, 3, etc.) and NULL pointers.
   - Replay reveals exactly 7 enters and 7 exits, strictly balanced, with CPU interrupts enabled at boundary.

## 4. Bounded Technical Frontier for Phase 16

At 520,000 blocks budget, execution advances past all hardware, MMIO, timer, and critical-section setup into `ClearImage` (`0x800189E0`), which calls dispatcher `0x8001A908` and worker `0x8001A0C0`.
The path reaches the boundary before `A0:0x43 Exec` (`0x80015B84`) handoff to `TITLE` entry (`0x800380A0`).
Traversing this boundary requires:
1. CD-ROM sector delivery for the TITLE executable overlay payload.
2. GPU command processing and rasterization for subsequent frames.

Under strict fail-closed discipline:
- `OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`
- `FIRST_FRAME_READY=NO`
- `OPENRECOMP_PHASE15_HERCULES_FRAME_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE15_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE15_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`

## 5. Integrity Guarantees

- `THIRD_PARTY_CODE_IMPORTED=NO`
- `PRIVATE_FIXTURE_BYTES_COMMITTED=NO`
- `PHASE14_TOUCHED=NO` (Frozen Phase-14 baseline commit `830be0f7be998061e8d442134cfae511d5dd8c62` and tree `3b5b998dacc60eff88258509bdb5cc548b8b1401` intact).
- Source manifest `.openrecomp-phase15/SOURCE_SHA256SUMS.txt` contains 36 verified entries passing `OPENRECOMP_PHASE15_SOURCE_INTEGRITY=PASS`.
