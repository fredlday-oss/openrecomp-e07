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

## Next Action
Author and execute `P18-02` (authentic execution escape from the polling
frontier): wire the state-driven GPUSTAT model into the runtime and prove the
authentic guest leaves the poll. Author the stage contract before claiming the
stage complete. Do NOT begin Phase 19.
