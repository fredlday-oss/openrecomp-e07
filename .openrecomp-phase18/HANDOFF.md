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

## Next Action
Author and execute `P18-03` (causal device transcript): capture deterministic
events actually caused by authentic guest execution, each bound to sequence,
guest PC, authenticated owner, decoded instruction, event type, address/register,
value, width and causal device state. Do NOT begin Phase 19.
