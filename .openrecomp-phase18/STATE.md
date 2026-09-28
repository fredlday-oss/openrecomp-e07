# OpenRecomp Phase 18 State

## Baseline
- Phase-17 terminal commit: `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`
- Phase-17 terminal tree: `ad3aa822e5a02905ebc25477f7b6c69d0bffa055`
- Phase-17 terminal tag: `openrecomp-phase17-pass`
- Phase-17 terminal marker: `OPENRECOMP_PHASE17_TERMINAL_V1=PASS`
- Phase-16 frozen baseline commit: `a0c26e882ca65cfc84cbec78f7e787509a4992a3`
- Branch: `phase18/ps1-first-frame-frontier-v1`

## Proof Markers (Phase 18, created fresh)
- `OPENRECOMP_PHASE18_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE18_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE18_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`
- `FIRST_FRAME_READY=NO`

## Historical Phase-17 markers (preserved verbatim, never promoted)
- `OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`
- `FIRST_FRAME_READY=NO`

## Recovery authority (Phase-18 autonomous continuation)
- Recovery commit chain: `1e07ecc` (P18-04 producer repair), `a4010f5`
  (P18-05/P18-06 revalidation + P18-07 contract), `0244839` (P18-06 fresh-root
  evidence), `e65055d` (P18-07).
- P18-04 inherited defect (repaired): the frontier producer appended a literal
  backslash-n token instead of a newline, so `gpu_command_frontier.json` was not
  valid JSON. Regenerated with the corrected producer; digest
  `297a5493...be58b` -> `a009003b...bfe9`; GP0/GP1 frontier still UNREACHED.
- P18-05 and P18-06 were re-run from the current authority: both PASS. P18-05's
  semantic artifacts are byte-identical (only integrity-count bookkeeping
  changed); P18-06 produced zero diff.

## Current Stage
- CURRENT_STAGE: P18-90
- LAST_COMPLETED_STAGE: P18-90 Integrated regression (controller reviewed,
  dual-gated, fresh-root reproduced)
- NEXT_STAGE: P18-91
- FINAL_VERDICT: (not terminal)
- REVIEW_GATE: open.

## P18-00 authoritative metadata (bootstrap / authority / provenance)
- STATUS: PASS (controller reviewed and INTEGRATED; see `evidence/P18-00/CONTROLLER_REVIEW.md`)
- authority_commit: `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`
- authority_tree: `ad3aa822e5a02905ebc25477f7b6c69d0bffa055`
- establishes: Phase-17 tag/commit/tree re-verified from live Git; HEAD descends
  from the authority; Phase-1..17 namespaces untouched; Phase-18 control plane
  present; private fixture integrity fail-closed; imported reconnaissance
  inventoried as reference-only; GPUSTAT polling frontier re-derived from the
  digest-verified P17-06R transcript; Phase-18 claim markers start NOT_PROVEN.
- frontier (re-derived, not hard-coded): 1587 GPUSTAT reads, all zero under
  `ZERO_FILL_RECORDED`; dominant owner `0x8001a9fc`; no GP0 writes; no DMA-2
  traffic; stop reason `CONTINUATION_BUDGET_REACHED`.
- proof boundaries: initialization / frame / playability / general compatibility
  remain NOT_PROVEN; `FIRST_FRAME_READY=NO`.
- next_stage: P18-01

## P18-01 authoritative metadata (GPUSTAT polling model)
- STATUS: PASS (controller reviewed and INTEGRATED)
- authority_commit: `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`
- authority_tree: `ad3aa822e5a02905ebc25477f7b6c69d0bffa055`
- derives from authenticated fixture bytes the exact guest poll condition:
  poll PC `0x8001a9fc`, loop `lw; nop; and; beq`, single-bit mask
  `0x04000000` (bit 26), branch back to the load, exit requires bit 26 set.
- the guest-tested bit agrees with two independent emulator references
  (DuckStation `GPUSTATReg::gpu_idle`, PCSX-Redux `GPUSTATUS_IDLE 0x04000000`).
- minimum state model: `STATE_DRIVEN_BIT26` (idle => 1, busy => 0); unmodelled
  bits fail closed (`UNMODELLED_GPUSTAT_BIT`).
- simulation: exit reachable in 1 iteration under faithful idle state; not
  reachable under busy state; not reachable under `ZERO_FILL_RECORDED`.
- does NOT run the guest past the poll and produces no frame evidence.
- proof boundaries: initialization / frame / playability / general compatibility
  remain NOT_PROVEN; `FIRST_FRAME_READY=NO`.
- next_stage: P18-02

## P18-02 authoritative metadata (authentic poll exit / execution continuation)
- STATUS: PASS (controller reviewed and INTEGRATED; see `evidence/P18-02/CONTROLLER_REVIEW.md`)
- authority_commit: `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`
- authority_tree: `ad3aa822e5a02905ebc25477f7b6c69d0bffa055`
- uses the P18-01 state-driven bit-26 model to continue authentic execution
  past the GPUSTAT wait-poll: derived poll owner `0x8001a9fc`, branch
  `lw; nop; and; beq`, mask bit 26, taken-to-exit within the budget; the value
  consumed at the owner had bit 26 set (`0x04000000`).
- every executed continuation PC is authenticated with provenance; five new
  regions authenticated from source bytes; stop reason
  `CONTINUATION_BUDGET_REACHED`; causal transcript digest
  `c4fa0d67039102ef8e61e70e9610b51e64982202373dbeeb982d60c68f071331`.
- gate: 66/66 checks PASS; dual official runs byte-identical; independent
  fresh-private-root reproduction byte-identical to official evidence.
- promotes no proof marker (FIRST_FRAME_READY=NO; Phase-18 claims NOT_PROVEN).
- next_stage: P18-03

## P18-04 authoritative metadata (GPU command frontier)
- STATUS: PASS (worker dev gate 64/64; awaiting controller dual-gate integration)
- authority_commit: `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`
- authority_tree: `ad3aa822e5a02905ebc25477f7b6c69d0bffa055`
- mechanically establishes that the authentic continuation reaches device
  traffic (BIOS dispatch, GPUSTAT reads, interrupt, timer) but **no GP0/GP1
  write**: the GPU command frontier is UNREACHED.
- evidence for the unreached verdict: the generated runtime contains a genuine
  state-driven GP0/GP1 write path gated on exactly `0x1f801810`/`0x1f801814`
  (gate count 1, both literals present, function PC-free); the FIFO tap records
  zero GP0 and zero GP1 writes; no reached instruction materialises the
  `0x1f80` window high half (materialisation sites 0).
- controlled probe against the official generated source drives the generated
  GPU write entry points and produces real GP0/GP1 frontier events (GP0=1,
  GP1=1; classes POLYGON + GP1_CONTROL), proving the path/tap/classifier are
  genuine and the frontier is a genuine unreached state, not a missing path.
- GP0/GP1 explicitly listed `NOT_REACHED`; unknown command words classify
  `UNKNOWN` (never a no-op); all fail-closed controls pass.
- frontier digest `a009003b644122a011a4a53a9ceeae1d2e4a560a462fc28ef2c3ac9dd4b2bfe9`
  (repaired by the P18-04 recovery commit; the pre-repair value `297a5493...be58b` was
  not valid JSON and was superseded).
- promotes no proof marker (FIRST_FRAME_READY=NO; Phase-18 claims NOT_PROVEN).
- next_stage: P18-05

## P18-05 authoritative metadata (DMA / ordering-table frontier)
- STATUS: PASS (controller authored, dual-gated and independently reproduced; see
  `evidence/P18-05/CONTROLLER_REVIEW.md`)
- authority_commit: `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`
- authority_tree: `ad3aa822e5a02905ebc25477f7b6c69d0bffa055`
- mechanically establishes that the authentic continuation reaches device
  traffic but **no DMA-channel access**: the DMA / ordering-table frontier is
  UNREACHED (zero accesses, empty DMA tap).
- provenance for the verdict: the generated runtime contains a genuine DMA-window
  tap gated on exactly `0x1f801080`..`0x1f8010ff` (single window gate, both
  literals present, record function free of any guest-PC constant), reduced
  through the shared `or_p18_phys` hardware-window reducer, with the read and
  write access hooks rewired; no reached instruction materialises the window
  (759 reached PCs, 103424 records, 0 sites).
- controlled probe against the official generated source drives the generated DMA
  entry points and produces real channel-2 DMA-frontier events (4 accesses),
  proving the tap/decoder/classifier genuine and the frontier a genuine unreached
  state.
- bounded ordering-table traversal model (alignment, cycle, depth and command-count
  bounds, end-of-list bit, per-node GP0 classification) proven by positive chain
  and negative controls; all channels listed explicitly `NOT_REACHED`.
- gate: 74/74 checks PASS; dual official runs byte-identical; independent
  fresh-private-root reproduction byte-identical to official evidence.
- frontier digest `f0251b43b8d60ac8c101df71d59cd28441615e1ab58c7036dce98933450fa5c1`.
- promotes no proof marker (FIRST_FRAME_READY=NO; Phase-18 claims NOT_PROVEN).
- next_stage: P18-06

## P18-06 authoritative metadata (VRAM mutation / display state)
- STATUS: PASS (controller recovered, reviewed, repaired and integrated inherited
  worker work; see `evidence/P18-06/CONTROLLER_REVIEW.md` and
  `evidence/P18-06/RECOVERY_FINDINGS.md`)
- authority_commit: `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`
- authority_tree: `ad3aa822e5a02905ebc25477f7b6c69d0bffa055`
- integration_commit: `464e9c6485486ed191918d82a4662714ceae79bb`
- mechanically establishes that the authentic continuation executes 8270
  instructions (8192 continuation budget, stop `CONTINUATION_BUDGET_REACHED`)
  with **no GP0/GP1 write and no DMA access**, therefore **no VRAM mutation and
  no display-state change**: the VRAM / display frontier is UNREACHED
  (`gp0_write_count=0`, `gp1_write_count=0`, `dma_access_count=0`,
  `vram_display_status=NOT_REACHED`, `explicit_not_reached=true`).
- provenance for the verdict: the generated runtime is shown to contain the
  genuine, window-gated GPU write path and the P18-05 DMA-window tap; a controlled
  probe compiled against the official generated runtime source drives the
  generated GPU write entry points and produces real traffic (4 GP0 words,
  2 GP1 words, 1 mutation) in a throwaway private directory only. The gate
  asserts the contrast between that non-zero control and the zero authentic
  traffic, so "unreached" is a real frontier state and not a missing
  implementation.
- no VRAM or frame content was fabricated: the controlled VRAM digest is labelled
  as control-derived, is excluded from the frontier document, and is never
  presented as authentic title output.
- every VRAM byte access is range- and alignment-checked fail-closed
  (`VRAM_ADDRESS_OUT_OF_RANGE`, `VRAM_ADDRESS_UNALIGNED`); no input is rounded.
- controller review repaired seven reproduced defects in the inherited work
  (stale source manifest; non-existent `vram_region_digest()` call; a false-pass
  negative control encoding an in-range GP1 start; probe fill words decoding to a
  0x0 region; missing contract-mandated out-of-range/alignment checks; dead
  `replay_words()`; missing `P18G_GP0_TOTAL`/`P18G_GP1_TOTAL` probe output). One
  review hypothesis (probe would not compile without the runtime header) was
  tested, disproven and retracted rather than shipped.
- gate: 71/71 checks PASS; dual official runs byte-identical (stdout raw and
  LF-normalized, all artifacts, rc=0 both, empty stderr both); independent
  fresh-private-root reproduction byte-identical on all five artifacts.
- frontier digest `2848c231c0351638485931e8dfd064abf7ba990d7a9fab178c3730d94e084e5e`.
- promotes no proof marker (FIRST_FRAME_READY=NO; Phase-18 claims NOT_PROVEN).
- next_stage: P18-07

## P18-07 authoritative metadata (first-frame assessment)
- STATUS: PASS (controller authored, dual-gated, independently reproduced)
- authority_commit: `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`
- authority_tree: `ad3aa822e5a02905ebc25477f7b6c69d0bffa055`
- integration_commit: `e65055d`
- consumes P18-02..P18-06 evidence read-only and hash-verifies the frozen
  frontier documents (P18-04 `a009003b...`, P18-05 `f0251b43...`, P18-06
  `2848c231...`); any mismatch/absence/unparsable document fails closed.
- causal-link ledger: L1 authenticated execution **ESTABLISHED**; L2 GP0/GP1,
  L3 DMA/OT, L5 VRAM, L6 display **UNREACHED**; L4 decoded semantics, L7
  framebuffer **NOT_PROVEN**.
- promotion rule `FIRST_FRAME_READY=YES iff all of L1..L7 ESTABLISHED` yields
  **NO**. Anti-vacuity control promotes to YES in an isolated control namespace;
  six single-milestone anti-inflation vectors each yield NO.
- gate: 59 checks PASS; dual official runs byte-identical; fresh-root
  reproduction byte-identical on all seven artifacts.
- assessment digest `85ceec185a8f5a1fafb859f7fa32d81b57e21d4da9397f99dde11dec0818ba6f`.
- promotes no proof marker (FIRST_FRAME_READY=NO; Phase-18 claims NOT_PROVEN).
- next_stage: P18-90

## P18-90 authoritative metadata (integrated regression)
- STATUS: PASS (controller recovered, reviewed and completed the in-flight work;
  see `evidence/P18-90/CONTROLLER_REVIEW.md` and
  `evidence/P18-90/FRESH_ROOT_REPRODUCTION.md`)
- authority_commit: `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`
- authority_tree: `ad3aa822e5a02905ebc25477f7b6c69d0bffa055`
- read-only integrated audit over the certified P18-00..P18-07 corpus: source
  manifest exactness (27 entries, all digests verify); evidence closure and
  stage/next_stage agreement; repaired P18-04 authority in use (frontier JSON
  digests match the recorded `.sha256` and the P18-07 consumer); no stale
  pre-repair digest `297a5493...be58b` surviving as authority; frozen Phase 1..17
  namespaces untouched; marker ledger with no promotion; 14 fail-closed negative
  controls.
- repairs made during recovery: corrected `STATE.md`/`HANDOFF.md` lines that
  still presented the pre-repair P18-04 digest as current authority; added the
  control-document, stale-digest and revalidation audits (with negative controls)
  to the regression gate.
- gate: `P18-90_CHECKS=142` PASS; authoritative dual-run runner PASS (identical
  raw/LF stdout, empty stderr both, byte-identical artifacts); fresh-private-root
  reproduction byte-identical on every semantic artifact (only the runner's own
  self-recorded output path differs, non-semantic).
- promotes no proof marker (FIRST_FRAME_READY=NO; Phase-18 claims NOT_PROVEN).
- next_stage: P18-91

## Stage Status
| Stage | Status | Marker |
|---|---|---|
| P18-00 | PASS | `OPENRECOMP_P18_00=PASS` |
| P18-01 | PASS | `OPENRECOMP_P18_01=PASS` |
| P18-02 | PASS | `OPENRECOMP_P18_02=PASS` |
| P18-03 | PASS | `OPENRECOMP_P18_03=PASS` |
| P18-04 | PASS (repaired) | `OPENRECOMP_P18_04=PASS` |
| P18-05 | PASS (revalidated) | `OPENRECOMP_P18_05=PASS` |
| P18-06 | PASS (revalidated) | `OPENRECOMP_P18_06=PASS` |
| P18-07 | PASS | `OPENRECOMP_P18_07=PASS` |
| P18-90 | PASS | `OPENRECOMP_P18_90=PASS` |
