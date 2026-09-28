# P18-06 controller review

Branch: `phase18/ps1-first-frame-frontier-v1`
Base authority: `c8c77e0798514336a56b68a7252d0e3c864dad2f` (tree `e7190147`)
Reviewed: recovery of inherited, uncommitted P18-06 worker work.

## Disposition
**ACCEPT AND INTEGRATE.** The work is legitimate and reproducible. The honest
outcome is preserved unchanged: the VRAM / display frontier is **UNREACHED**.

## Inherited-work handling
The four inherited artifacts were preserved, never reset or cleaned. The review
repaired them in place and added the missing fail-closed path the contract
already required.

## Defects found, reproduced, and fixed

| id | severity | defect | how it was proved |
|---|---|---|---|
| D1 | critical | source manifest stale: `tools/test_phase18_vram_display_v1.py` recorded `fec763ba...`, disk was `256fdf19...`, so the gate aborted at `integrity:phase18-sources` with `OPENRECOMP_PHASE18_SOURCE_INTEGRITY=FAIL mismatch`, exit 1 | ran the gate, observed the fail-closed abort; then diffed every manifest entry against disk hashes |
| D2 | critical | `fill.vram_region_digest()` with no args; `VramDisplayState` has no such method | gate run raised `AttributeError: 'VramDisplayState' object has no attribute 'vram_region_digest'` at `positive_model_controls` |
| D3 | critical | negative control encoded GP1 0x05 start `x=0x3FF, y=0x1FF`, which are *inside* the 1024x512 space, so nothing raised and the control was a false pass | direct probe: `apply_gp1` accepted it; then proved the field widths (10-bit X, 9-bit Y) exactly span VRAM, so the command cannot express out-of-range by construction |
| D4 | critical | controlled probe wrote fill words `0x00000010`/`0x00000020`, decoding to a 0x0 region, so the control could never produce a real mutation | direct probe: `apply_gp0` raised `VRAM_REGION_EMPTY 32x0` |
| D5 | high | contract required `VRAM_ADDRESS_OUT_OF_RANGE` and `VRAM_ADDRESS_UNALIGNED`; the module implemented neither and had no alignment check at all — contract drift | grep of contract negative-control list against the module surface |
| D6 | low | `replay_words()` was dead code that unconditionally raised `GP0_PACKETISATION_REQUIRED` and was called from nowhere | `grep -rn replay_words` returned only the definition |
| D7 | critical | controlled probe never printed `P18G_GP0_TOTAL` / `P18G_GP1_TOTAL`, which `_parse_fifo_lines` requires to cross-check the FIFO against the runtime counters | gate run raised `FIFO_TOTAL_MISMATCH: gp0=4/0 gp1=2/0` |

## One hypothesis disproven
The initial review claimed the probe would not compile because it omits
`#include "or_side_effects_v1.h"`. That was **wrong**, and the claim was not
carried into the commit. `cont.emitter._compile_c` passes
`-include or_side_effects_v1.c`, putting the runtime in the same translation
unit, so the probe compiles and runs and emits real FIFO lines. The claim was
retracted rather than shipped, because a review record that overstates a defect
is itself a trust defect.

## Fixes applied
- Regenerated `SOURCE_SHA256SUMS.txt` from actual disk truth, then again after
  each source change, so the integrity gate re-passes.
- `fill_ok` now compares `fill_record["region_digest"]` (the digest the model
  computed for the region it actually wrote) against an independent recompute
  over `(x=0x10, y=0x20, w=0x20, h=0x10)`, and requires it to be non-zero.
- Replaced the impossible GP1 out-of-range control with two honest controls: a
  positive control asserting the maximum encodable start is in range, and a
  `derive_framebuffer` out-of-range control that does fail closed.
- Probe fill words corrected to the packed `0x00200010` / `0x00100020` form.
- Probe now prints the GP0/GP1 totals it depends on.
- Added `vram_address()` implementing the contract's `VRAM_ADDRESS_OUT_OF_RANGE`
  and `VRAM_ADDRESS_UNALIGNED`; `vram_offset` now routes through it, so every
  VRAM byte access is range- and alignment-checked. No input is ever rounded.
- Added the two new negative controls to the gate and to `negative_tests.json`.
- Removed the dead `replay_words()`.

The contract was treated as authoritative and the module was brought into
compliance; the contract was not edited to match the code.

## Proof-boundary discipline
- The authentic continuation executed 8270 instructions, 8192 of them in the
  continuation, and stopped on `CONTINUATION_BUDGET_REACHED`.
- Authentic result: `gp0_write_count=0`, `gp1_write_count=0`,
  `dma_access_count=0`, `vram_display_status=NOT_REACHED`,
  `explicit_not_reached=true`, `first_frame_ready=NO`.
- The controlled probe produced real GPU traffic (4 GP0 words, 2 GP1 words, 1
  mutation, VRAM digest `60245987...`) purely in a throwaway private directory,
  and its contrast with the zero authentic traffic is asserted by the gate
  (`control:contrast-with-unreached-frontier`).
- No VRAM or frame content was fabricated. The controlled digest is labelled as
  coming from a control, is kept out of the frontier document, and is not
  presented as authentic title output.
- `FIRST_FRAME_READY=NO` and the four claim markers stay `NOT_PROVEN`.

## Evidence
- Gate: `tools/test_phase18_vram_display_v1.py`, 71 checks, exit 0.
- Determinism: `determinism.json` — `stdout_identical_raw=true`,
  `stdout_identical_lf=true`, `artifacts_identical=true`,
  `returncode_zero_both=true`, `stderr_empty_both=true`; both runs
  `fa2dde9d7297cb0ea716120eb5cb79399abca9721a63320d91d33af62e79adb3`.
- Fresh root: `FRESH_ROOT_REPRODUCTION.md` — all five artifacts byte-identical.
- Frontier document digest `2848c231c0351638485931e8dfd064abf7ba990d7a9fab178c3730d94e084e5e`.
- Frozen Phase-1..17 namespaces: unchanged since `PHASE17_TERMINAL_COMMIT` and
  clean in the working tree.
