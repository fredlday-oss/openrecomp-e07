# P12-09 — Hercules first-frame execution frontier loop

Verdict: **PASS** (7 checks, deterministic twice).

Stage marker: `OPENRECOMP_P12_09=PASS`.

Target marker: `OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN`.

Resuming the final-tree initialization execution, no frame-submission boundary
is reachable. The exact frontier remains the C0 interrupt-routine dispatcher
(`0x80015f5c`, `fn_80015f58`, block 468365). GPU traffic on the path is
initialization-only (one GP0 `NOP`, one GP1 `DISPLAY_ENABLE`) with no
frame/primitive GP0 opcode; the detected repeating 14-block cycle is
post-failure polling, not a frame cycle. No ordering-table or DMA activity is
observed.

Evidence: `frame_frontier.json`, `p12_09_tests.json`, `RESULT.json`,
`official_runs.json`, `determinism.json`, run stdout/stderr.
