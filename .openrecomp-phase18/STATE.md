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

## Current Stage
- CURRENT_STAGE: P18-05
- LAST_COMPLETED_STAGE: P18-05 DMA / ordering-table frontier (controller reviewed and integrated)
- NEXT_STAGE: P18-06
- FINAL_VERDICT: (not terminal)
- REVIEW_GATE: open; no REVIEW_REQUIRED stop raised by P18-01.

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
- frontier digest `297a549350e89c4fdf765353c7cf6ff9a1f9a0e563c8c62b02a33677943be58b`.
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

## Stage Status
| Stage | Status | Marker |
|---|---|---|
| P18-00 | PASS | `OPENRECOMP_P18_00=PASS` |
| P18-01 | PASS | `OPENRECOMP_P18_01=PASS` |
| P18-02 | PASS | `OPENRECOMP_P18_02=PASS` |
| P18-03 | PASS | `OPENRECOMP_P18_03=PASS` |
| P18-04 | PASS | `OPENRECOMP_P18_04=PASS` |
| P18-05 | PASS | `OPENRECOMP_P18_05=PASS` |
