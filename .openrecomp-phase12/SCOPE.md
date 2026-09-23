# OpenRecomp Phase 12 Scope

## Mission

Advance the frozen Phase-11 bounded commercial-fixture result into two
substantially stronger, private-fixture-bounded claims:

1. a deterministic Hercules **initialization** proof; and
2. a deterministic Hercules **first-frame** proof.

The immediate starting frontier is the BIOS `B0:0x5B` `ChangeClearPAD` path
identified by post-Phase-11 reconnaissance: the `B0:0x57` `GetB0Table` caller
at `0x80015fa4` (block 468341) that requires the `B0:0x5B` entry and a writable
target-relative object.

Phase 12 must NOT claim playability or general PS1 compatibility.

The architecture is the existing OpenRecomp pipeline, extended additively and
evidence-bounded:

```
PS-X EXE ingestion -> PS1 image/memory contract -> MIPS32 decode/semantics
 -> shared ProgramModel / CFG / functions / call graph / TUs
 -> architecture-neutral translation -> host emitter -> generic runtime
 -> typified BIOS/GPU/DMA/timer/controller/SPU/CD-ROM boundaries
 -> native build -> deterministic execution
```

No second PS1/MIPS runtime, MIPS decoder, CFG pipeline, host emitter or
recompilation pipeline is created.

## Milestones (Phase-11 meanings preserved exactly)

| Id | Milestone | Promotion requirement |
|---|---|---|
| A | translated native execution begins | inherited |
| B | initialization completes | deterministic evidence that initialization actually completes |
| C | GPU command stream reached | actual GP0 and/or GP1 command/control writes with deterministic ordering and classifications |
| D | first valid frame | mechanically observable frame completion/submission (not a screenshot of commercial artwork) |
| E | title/logo screen | reproducible title/logo state |
| F | menu | reproducible menu state |
| G | controllable gameplay | deterministic scripted controller input causing reproducible guest-state progression |

A stage `PASS` does not itself imply a milestone promotion.

## Proof contracts

The machine-readable definitions live in
`.openrecomp-phase12/src/p12_contracts_v1.py` and are emitted to
`evidence/P12-00/proof_contracts.json`.

### `OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF`

The initialization contract is satisfied when all of the following hold on the
bounded private-fixture execution:

- `INIT-PREDECESSOR`: the frozen Phase-11 boundary and all predecessor stages
  that Phase 12 depends on are `PASS`.
- `INIT-B0-PATCH`: execution passes the Phase-11 `B0:0x57` frontier
  (`0x80015fa4`); the documented `GetB0Table` -> entry `0x5B` lookup, the two
  target-relative pointer derivations at offsets `0x884`/`0x894` and the
  eleven-word clear at offsets `0x594`..`0x5bc` all occur, each recorded as a
  deterministic observable.
- `INIT-BOUNDARY`: execution reaches a mechanically defined
  initialization-completion boundary: the first execution point after
  `INIT-B0-PATCH` at which the guest enters its steady-state loop (a repeating
  block cycle with a deterministic period) with no fail-closed
  instruction/service/device access between the entry and the boundary. The
  concrete boundary site, function and block index are pinned by the execution
  evidence of `P12-04` and frozen by the `P12-05` gate.
- `INIT-NO-FAIL-CLOSED`: zero fail-closed events occur on the proven prefix from
  the fixture entry to `INIT-BOUNDARY`.
- `INIT-DETERMINISTIC`: two fresh executions produce byte-identical evidence for
  the fields declared deterministic (block-event count/digest, register file,
  RAM digest, device transcripts, ordered BIOS service calls).
- `INIT-NO-FABRICATION`: no fabricated BIOS guest code object, no execution of
  original guest machine code, no fail-open fallback, no private payload in
  evidence.

Any missing predicate keeps the claim `NOT_PROVEN`.

### `OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF`

The frame contract is satisfied when all of the following hold, given a
satisfied initialization contract:

- `FRAME-PREDECESSOR`: `OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=PASS`.
- `FRAME-PRIMITIVE`: at least one genuine typed GPU primitive/command
  submission (GP0/GP1) occurs on the frame path, with deterministic ordering
  and classification.
- `FRAME-OT`: the guest inserts at least one primitive into an active ordering
  table (a linked-list node write to a guest OT that is subsequently
  traversed), observed deterministically.
- `FRAME-SUBMIT`: a frame-submission boundary is reached: the guest submits the
  active ordering table through the documented GPU/DMA path and performs the
  active-buffer (OT/drawing-area) transition, observed deterministically.
- `FRAME-DETERMINISTIC`: two fresh executions produce byte-identical evidence
  for the deterministic fields.
- `FRAME-NOT-PLAYABILITY`: no playability or general-compatibility claim is
  derived; the frame proof is `PRIVATE_FIXTURE_BOUNDED`.

A literal framebuffer/screenshot is required only if the contract is amended by
new evidence; the default contract does not require pixel output. A mere
initialization callback is never a frame.

## Claim boundaries

Phase 12 may attempt to promote:

- `OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF`
- `OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF`

Phase 12 MUST NOT automatically promote (they remain `NOT_PROVEN`):

- `OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF`
- `OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY`

Phase 12 may promote the bounded service markers
`OPENRECOMP_PHASE12_B0_5B_CHANGECLEARPAD_V1`,
`OPENRECOMP_PHASE12_B0_TABLE_INDIRECT_V1`,
`OPENRECOMP_PHASE12_GPU_OT_DMA_V1`, `OPENRECOMP_PHASE12_TEXTURE_VRAM_V1`,
`OPENRECOMP_PHASE12_GTE_GEOMETRY_V1` and
`OPENRECOMP_PHASE12_END_TO_END_REPLAY_V1` only on their own evidence.

## Completion definition

Phase 12 distinguishes:

- `PHASE_EXECUTION_COMPLETE`: every stage in the queue has a recorded,
  evidence-backed result and the evidence closure passes.
- `PHASE12_TARGET_PROOF_COMPLETE`: both target proofs are `PASS`.

The primary technical objective is achieved only when both target proofs are
`PASS`. If a genuine blocker prevents one target after all mechanically sound
approaches are exhausted, the phase closes bounded/blocked according to the
established OpenRecomp convention, never falsely successful.

## Out of scope

- arbitrary PS-X EXE support;
- BIOS image loading, execution or emulation;
- memory cards, link cable, multi-tap;
- cycle-accurate timing, SPU audio synthesis completeness;
- any commercial asset, key, firmware, SDK material or console-derived format;
- any general-purpose or multi-game compatibility claim.
