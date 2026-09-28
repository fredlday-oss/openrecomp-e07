# P18-06 Recovery — controller findings on inherited worker work

## Live Git authority at recovery start
- branch: phase18/ps1-first-frame-frontier-v1
- HEAD: c8c77e0798514336a56b68a7252d0e3c864dad2f (tree e7190147)
- P18-05 certified: PASS (substantive b2e22c0, state c8c77e0)
- working tree: modified .openrecomp-phase18/SOURCE_SHA256SUMS.txt
  untracked: contracts/P18-06.md, src/p18_vram_display_v1.py, tools/test_phase18_vram_display_v1.py
- NO reset/clean/overwrite performed. All inherited work preserved.

## What was already complete
1. .openrecomp-phase18/contracts/P18-06.md — complete, contract-defined.
2. .openrecomp-phase18/src/p18_vram_display_v1.py — VRAM 1024x512x16 model,
   GP0 fill/cpu2vram/vram2vram/vram2cpu, GP1 display enable/start/h-range/
   v-range/mode, derive_framebuffer, fail-closed error codes, provenance-bound
   frontier document builder + validator. Import surface verified complete
   against p18_gpu_command_frontier_v1 / p18_dma_frontier_v1 / p17 helpers.
3. tools/test_phase18_vram_display_v1.py — gate body, dual official run,
   controlled probe, positive + negative controls, evidence writers, markers.

## Defects found by independent controller review (all pre-repair)
- D1 CRITICAL: source manifest stale. tools/test_phase18_vram_display_v1.py
  recorded fec763ba..., disk 256fdf19... -> fail-closed
  OPENRECOMP_PHASE18_SOURCE_INTEGRITY=FAIL. Gate cannot start.
- D2 **DISPROVEN AND RETRACTED**: the initial review claimed the controlled
  probe would not compile because it omits
  `#include "or_side_effects_v1.h"`. This was wrong. `cont.emitter._compile_c`
  passes `-include or_side_effects_v1.c`, placing the runtime in the same
  translation unit, so the probe compiles and runs. Verified by compiling a
  standalone probe with the same flags: it built and emitted real FIFO lines.
  The claim is retracted here rather than shipped, because an evidence record
  that overstates a defect is itself a trust defect.
- D3 CRITICAL: positive_model_controls calls fill.vram_region_digest() with no
  arguments; VramDisplayState has no such method (module-level function
  requires x,y,w,h) -> AttributeError.
- D4 CRITICAL: negative_display_start_out_of_range encodes x=0x3FF,y=0x1FF,
  which are INSIDE the 1024x512 VRAM coordinate space -> no exception raised,
  the fail-closed control fails.
- D5: contract names controls VRAM_ADDRESS_OUT_OF_RANGE and
  VRAM_ADDRESS_UNALIGNED; module implements VRAM_COORD_OUT_OF_RANGE and has no
  alignment check at all. Contract drift.
- D6: replay_words() is dead code: it raises GP0_PACKETISATION_REQUIRED for
  every GP0 entry and never applies anything. Unreachable from the gate.

## Defects found only by running the repaired gate (post-manifest-fix)
- D7 CRITICAL: the controlled probe never printed the `P18G_GP0_TOTAL` /
  `P18G_GP1_TOTAL` lines that `_parse_fifo_lines` requires to cross-check the
  FIFO against the runtime counters. The gate failed closed with
  `FIFO_TOTAL_MISMATCH: gp0=4/0 gp1=2/0`. `or_p18g_gp0_total` and
  `or_p18g_gp1_total` do exist in the generated runtime; the probe just did not
  call them.

## Disposition
Repaired under REPRODUCE->DIAGNOSE->IMPLEMENT->TEST->REVIEW->RECORD->COMMIT.
