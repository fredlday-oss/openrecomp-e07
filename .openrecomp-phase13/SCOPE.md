# OpenRecomp Phase 13 Scope

## Mission

Advance the frozen Phase-12 bounded result (`PASS_BOUNDED_B0_MEDIATION_PRIVATE_FIXTURE`)
into a stronger, private-fixture-bounded Phase-13 result by implementing the
minimum architecture-correct C0 BIOS interrupt-routine queue semantics required
by Hercules, resolving the dynamic callback control-flow frontier, and continuing
the real Hercules initialization path until the inherited initialization proof
contract is legitimately satisfied or a new irreducible blocker is established.

Phase 13 is **not** primarily a first-frame or playability phase. It must never
claim, merely because initialization advances:

- Hercules first-frame proof;
- Hercules playability;
- general PS1 compatibility.

## Architecture

The existing OpenRecomp pipeline is extended additively and evidence-bounded:

```
PS-X EXE ingestion -> PS1 image/memory contract -> MIPS32 decode/semantics
 -> shared ProgramModel / CFG / functions / call graph / TUs
 -> architecture-neutral translation -> host emitter -> generic runtime
 -> typed BIOS/GPU/DMA/timer/controller/SPU/CD-ROM boundaries
 -> native build -> deterministic execution
```

No second PS1/MIPS runtime, MIPS decoder, CFG pipeline, host emitter or
recompilation pipeline is created.

## Layered interrupt model

The reconnaissance recommendation `LAYERED_MODEL` is followed exactly:

- Layer 1: C0 BIOS interrupt-routine queue bookkeeping and controlled synthetic
  callback mediation.
- Layer 2: `ChangeClearRCnt` / bounded deterministic timer support, only when a
  live frontier proves it necessary.
- Layer 3: hardware interrupt-controller / CPU exception delivery, only when a
  later proven frontier explicitly requires it.

A layer is never implemented for completeness. Hardware interrupt delivery is not
implemented unless real execution proves it necessary.

## Initialization proof contract

Phase 13 reuses the exact Phase-12 initialization proof contract documented in
`.openrecomp-phase12/src/p12_contracts_v1.py` and emitted to
`.openrecomp-phase12/evidence/P12-00/proof_contracts.json`. Phase 13 may add
stronger evidence requirements but may not silently move the boundary earlier.

Recorded at `P13-00`:

- `INITIALIZATION_CONTRACT_SOURCE=.openrecomp-phase12/src/p12_contracts_v1.py`
  (plus the P12-00 proof_contracts.json sidecar);
- `INITIALIZATION_CONTRACT_CHANGED=NO`.

## Claim boundaries

Phase 13 may attempt to promote:

- `OPENRECOMP_PHASE13_HERCULES_INITIALIZATION_PROOF`.

Phase 13 MUST NOT automatically promote (they remain `NOT_PROVEN`):

- `OPENRECOMP_PHASE13_HERCULES_FRAME_PROOF`;
- `OPENRECOMP_PHASE13_HERCULES_PLAYABILITY_PROOF`;
- `OPENRECOMP_PHASE13_GENERAL_PS1_COMPATIBILITY`.

Phase 13 may promote the bounded service markers
`OPENRECOMP_PHASE13_SYSENQINTRP_V1`, `OPENRECOMP_PHASE13_SYSDEQINTRP_V1`,
`OPENRECOMP_PHASE13_INTRP_ROUNDTRIP_V1`,
`OPENRECOMP_PHASE13_CALLBACK_MEDIATION_V1`,
`OPENRECOMP_PHASE13_CHANGECLEARRCNT_V1`, `OPENRECOMP_PHASE13_TIMER1_V1`,
`OPENRECOMP_PHASE13_INTERRUPT_MMIO_V1` and
`OPENRECOMP_PHASE13_INITIALIZATION_REPLAY_V1` only on their own evidence.

## Completion definition

- `PHASE_EXECUTION_COMPLETE`: every stage in the queue has a recorded,
  evidence-backed result and the evidence closure passes.
- `PHASE13_TARGET_PROOF_COMPLETE`: the initialization proof is `PASS`.

The primary technical objective is achieved only when the initialization proof is
`PASS`. If a genuine blocker prevents it after all mechanically sound approaches
are exhausted, the phase closes bounded/blocked according to the established
OpenRecomp convention, never falsely successful.

## Out of scope

- arbitrary PS-X EXE support;
- BIOS image loading, execution or emulation;
- memory cards, link cable, multi-tap device behaviour beyond documented
  bookkeeping;
- cycle-accurate timing, SPU audio synthesis completeness;
- any commercial asset, key, firmware, SDK material or console-derived format;
- any general-purpose or multi-game compatibility claim.
