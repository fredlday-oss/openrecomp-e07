# OpenRecomp Phase 18 Handoff

## Summary
Phase 18 begins from the frozen Phase-17 terminal authority (tag
`openrecomp-phase17-pass`, commit
`d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`, tree
`ad3aa822e5a02905ebc25477f7b6c69d0bffa055`). P18-00 established the Phase-18
control plane and re-derived the GPUSTAT polling frontier. P18-01 investigated
that frontier mechanically and established the minimum state-driven GPUSTAT
model for the exact bit the authentic guest tests.

## Invariants
1. Commit `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69` is the immutable ancestor.
2. Phase-1 through Phase-17 files and evidence are frozen.
3. No guest binary bytes committed to Git.
4. Historical Phase-17 markers are preserved verbatim; Phase 18 uses its own
   `OPENRECOMP_PHASE18_*` namespace.

## P18-01 result
- Authentic poll condition re-derived from fixture bytes: PC `0x8001a9fc`,
  loop `lw; nop; and; beq`, mask `0x04000000` (bit 26), exit requires bit 26
  set. Provenance digest recomputed and matched to the committed transcript.
- The guest-tested bit agrees with DuckStation and PCSX-Redux references.
- Minimum model `STATE_DRIVEN_BIT26`; unmodelled bits fail closed.
- Simulation shows the exit is reachable exactly under faithful idle state and
  unreachable under `ZERO_FILL_RECORDED` / busy state.
- Promotes no proof marker. `FIRST_FRAME_READY=NO`; Phase-18 claim markers all
  `NOT_PROVEN`.

## P18-02 result
- Uses the P18-01 state-driven bit-26 GPUSTAT model to continue authentic
  execution past the wait-poll at `0x8001a9fc`: derived branch geometry
  (`lw; nop; and; beq`, mask bit 26), branch taken to the fall-through exit
  within the budget, and the GPUSTAT value consumed at the owner carries
  bit 26 (`0x04000000`). The emitted runtime's read is state-driven
  (`pending == 0`); the literal Phase-17 zero read model is absent.
- Every executed continuation PC is authenticated with a provenance digest;
  five newly reached regions are authenticated from source bytes; stop reason
  `CONTINUATION_BUDGET_REACHED`. Causal transcript digest
  `c4fa0d67039102ef8e61e70e9610b51e64982202373dbeeb982d60c68f071331`.
- Gate: 66/66 checks PASS; dual official runs byte-identical; independent
  fresh-private-root reproduction byte-identical.
- Promotes no proof marker. `FIRST_FRAME_READY=NO`; Phase-18 claims NOT_PROVEN.


## P18-03 result
- Layers a second fail-closed overlay on the P18-02 overlay so the frozen
  P17-06R runtime emits a causal device-state snapshot per MMIO event; 20
  events with 18 causal snapshots; every event carries sequence, owner
  provenance digest, fresh-decode-verified decoded instruction, class,
  address, value, width and causal device state.
- Reached: BIOS_DISPATCH, GPUSTAT_READ, INTERRUPT_ACCESS, TIMER_ACCESS.
  Unreached (explicit): GP0/GP1, DMA, OT, CD-ROM, SPU, PAD, SIO, MMIO,
  VRAM_MUTATION.
- Causal transcript digest `1eabe6c7b5c5263a61da8f91534f89b7a92c38916cdc482f3792b807dd10d6d6`.
- Gate 56/56 PASS; dual official runs byte-identical; independent
  fresh-private-root reproduction byte-identical.
- Promotes no proof marker. `FIRST_FRAME_READY=NO`; Phase-18 claims NOT_PROVEN.

## P18-04 result

- Establishes mechanically whether authentic GP0/GP1 GPU command traffic is
  reached by the P18-03 continuation.  Result: the GPU command frontier is
  **UNREACHED** - the continuation reaches device traffic (BIOS dispatch,
  GPUSTAT reads, interrupt, timer) but zero GP0 and zero GP1 writes to
  `0x1f801810`/`0x1f801814`.
- Provenance for the verdict: the generated runtime contains a genuine,
  state-driven GP0/GP1 write path gated on exactly those two physical registers
  (single gate, both literals present, write function free of any guest-PC
  constant); the P18-04 FIFO tap records zero GP0/GP1 writes; and no reached
  instruction materialises the `0x1f80` window high half.
- A controlled probe compiled against the official generated runtime source
  drives the generated GPU write entry points and produces real GP0/GP1 frontier
  events (GP0=1, GP1=1; classes POLYGON + GP1_CONTROL).  This proves the write
  path, tap and classifier are genuine, so "unreached" is a real frontier state
  and not a missing implementation.
- Unknown command words classify `UNKNOWN` and are never treated as a no-op.
- Frontier digest `297a549350e89c4fdf765353c7cf6ff9a1f9a0e563c8c62b02a33677943be58b`.
- Worker dev gate: 64/64 checks PASS (single run).  Controller dual-gate
  integration and fresh-root reproduction remain the controller's step.
- Promotes no proof marker. `FIRST_FRAME_READY=NO`; Phase-18 claims NOT_PROVEN.

## P18-04 result (integrated)

- GPU command frontier established as UNREACHED: the authentic continuation
  reaches device traffic but zero GP0/GP1 writes. Controller dual gate PASS
  (64/64) and fresh-root reproduction byte-identical; frontier digest
  `297a549350e89c4fdf765353c7cf6ff9a1f9a0e563c8c62b02a33677943be58b`.

## P18-05 result

- Establishes the DMA / ordering-table frontier as **UNREACHED**: the
  continuation executes 8270 instructions (8192 continuation budget, stop
  `CONTINUATION_BUDGET_REACHED`) with zero accesses to any DMA channel register;
  the DMA tap is empty and every channel is listed explicitly `NOT_REACHED`.
- Provenance: the generated runtime contains a genuine DMA-window tap gated on
  exactly `0x1f801080`..`0x1f8010ff` (single gate, both literals, record
  function free of any guest-PC constant), reduced through the shared
  `or_p18_phys` reducer, with read/write hooks rewired; no reached instruction
  materialises the window (759 reached PCs / 103424 records / 0 sites).
- A controlled probe compiled against the official generated source drives the
  generated DMA entry points and yields real channel-2 DMA-frontier events,
  proving the tap/decoder genuine and the frontier a real unreached state.
- Bounded ordering-table traversal model (alignment/cycle/depth/command-count
  bounds, end-of-list bit, per-node GP0 classification) proven by a positive
  chain and negative controls.
- Frontier digest `f0251b43b8d60ac8c101df71d59cd28441615e1ab58c7036dce98933450fa5c1`.
- Gate 74/74 PASS; dual official runs byte-identical; independent
  fresh-private-root reproduction byte-identical to official evidence.
- Promotes no proof marker. `FIRST_FRAME_READY=NO`; Phase-18 claims NOT_PROVEN.

## P18-06 result (VRAM mutation / display state)

- Establishes the VRAM / display frontier as **UNREACHED**: the authentic
  continuation executes 8270 instructions (8192 continuation budget, stop
  `CONTINUATION_BUDGET_REACHED`) with zero GP0 writes, zero GP1 writes and zero
  DMA accesses, so no VRAM byte is mutated and no display state is set.
- Provenance: the generated runtime is shown to contain the genuine,
  window-gated GPU write path and the P18-05 DMA-window tap. A controlled probe
  compiled against the official generated runtime source drives the generated GPU
  write entry points and yields real traffic (4 GP0 words, 2 GP1 words,
  1 mutation) in a throwaway private directory only; the gate asserts the
  contrast against the zero authentic traffic. So "unreached" is a real frontier
  state, not a missing implementation.
- No VRAM or frame content was fabricated. The control VRAM digest is labelled
  control-derived, is excluded from the frontier document, and is never presented
  as authentic title output. An image alone is not proof; nothing is promoted.
- Every VRAM byte access is range- and alignment-checked fail-closed
  (`VRAM_ADDRESS_OUT_OF_RANGE`, `VRAM_ADDRESS_UNALIGNED`); no input is rounded.
- Controller review recovered, reviewed and repaired seven reproduced defects in
  the inherited worker work, and retracted one review hypothesis that was
  disproven rather than shipped. See `evidence/P18-06/CONTROLLER_REVIEW.md` and
  `evidence/P18-06/RECOVERY_FINDINGS.md`.
- Frontier digest `2848c231c0351638485931e8dfd064abf7ba990d7a9fab178c3730d94e084e5e`.
- Gate 71/71 PASS; dual official runs byte-identical; independent
  fresh-private-root reproduction byte-identical to official evidence.
- Promotes no proof marker. `FIRST_FRAME_READY=NO`; Phase-18 claims NOT_PROVEN.

## Next Action
Controller: author and execute `P18-07` (first-frame evidence assessment).
Do NOT begin Phase 19.
