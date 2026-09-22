# OpenRecomp Phase 11 Scope

## Mission

Advance the exact audited private Hercules fixture (`SLUS_005.29`, legally
obtained, outside version control) beyond the Phase-10 milestone A and
establish the strongest reproducibly proven playability milestone possible,
through the existing OpenRecomp architecture:

```
PS-X EXE ingestion
 -> PS1 image/memory contract
 -> MIPS32 decode/semantics
 -> shared ProgramModel / CFG / functions / call graph / TUs
 -> architecture-neutral translation
 -> host emitter
 -> generic runtime
 -> PS1 BIOS/GPU/DMA/timer/controller/SPU/CD boundaries
 -> native build
 -> deterministic execution
```

No second PS1/MIPS runtime, MIPS decoder, CFG pipeline, host emitter or
recompilation pipeline is created. Only evidence-demonstrated gaps are
extended.

## Milestones

| Id | Milestone | Promotion requirement |
|---|---|---|
| A | translated native execution begins | inherited from `P10-05`/`P10-11` |
| B | initialization completes | deterministic evidence that initialization actually completes |
| C | GPU command stream reached | actual GP0 and/or GP1 command/control writes with deterministic ordering and classifications |
| D | first valid frame | valid rendered frame proven semantically or by hash (no commercial framebuffer in public evidence) |
| E | title/logo screen | reproducible title/logo state |
| F | menu | reproducible menu state |
| G | controllable gameplay | deterministic scripted controller input causing reproducible guest-state progression |

A stage `PASS` does not itself imply a milestone promotion. A screenshot alone
never proves G.

## Phase-11 completion definition

Phase 11 is complete when:

1. every frozen stage `P11-00` .. `P11-12` has an official `PASS` or a
   rigorously bounded `PASS` that records the exact next blocker, unless the
   single authorized reconciliation route below applies;
2. `P11-90` re-runs the frozen Phase-1 .. Phase-11 regression and passes;
3. `P11-91` closes the evidence chain with a milestone matrix and claim
   ledger;
4. `P11-99` audits every stage, the frozen history, the fixture identity, the
   evidence chain, determinism and the scope guards, and issues the bounded
   terminal verdict;
5. the highest achieved milestone is reported honestly, and every unpromoted
   claim remains `NOT_PROVEN`.

`P11-99` may `PASS` for a rigorously bounded phase even if milestone G is not
reached, provided the phase mission and evidence closure contract is satisfied
and the highest achieved milestone is reported honestly.

### Authorized P11-RC completion route

The user authorized one queue reconciliation after the completed `P11-07`
boundary at commit `515e3fb0e660d3c7975e3828eb3e26ac025c7cf2`.
`P11-07` proves that its serial runtime frontier is unreachable without a
guest-addressable `B0:0x5B` code/data representation that acceptable public
evidence does not establish within this phase's architecture.

Under this single exception:

1. `P11-00` through `P11-07` and their evidence remain byte-for-byte frozen;
2. the historical `P11-08` through `P11-12` queue rows remain present, but
   those stages are not executed and receive no stage verdict;
3. `P11-RC` must pass its control, history-preservation, source-integrity and
   direct-dependency regressions;
4. the only terminal route is `P11-RC -> P11-90 -> P11-91 -> P11-99`;
5. `P11-90`, `P11-91` and `P11-99` retain their original regression,
   evidence-closure and bounded-verdict responsibilities;
6. this route cannot promote milestones or compatibility claims that the
   executed evidence did not prove.

This exception is a recorded queue amendment, not a `PASS`, `FAIL`, skip,
inherited blocker or not-applicable result for any unexecuted stage.

## Permanent non-claims

- `OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent; never
  promoted by Phase 11).
- Phase-10 inherited non-claims stay recorded and unpromoted:
  `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`.

## Out of scope

- arbitrary PS-X EXE support;
- BIOS image loading, execution or emulation;
- memory cards, link cable, multi-tap;
- cycle-accurate timing, SPU audio synthesis completeness;
- any commercial asset, key, firmware, SDK material or console-derived
  format;
- any general-purpose or multi-game compatibility claim.
