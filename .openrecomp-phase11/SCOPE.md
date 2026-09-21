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
   rigorously bounded `PASS` that records the exact next blocker;
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
