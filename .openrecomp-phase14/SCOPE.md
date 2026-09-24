# OpenRecomp Phase 14 Scope

## Mission

Close the strongest legitimate Hercules initialization frontier by mediating the
Phase-13 terminal blocker — the indirect B0 BIOS dispatcher call at `0x80026ebc`
— as the documented `B0:0x56 GetC0Table()` service, modelling the minimum
guest-observable C0 surface the real code inspects, preserving the early-card IRQ
patch dataflow, closing the derived continuation target, validating the
immediately following `B0:0x57 GetB0Table()` path and resuming live execution
until the inherited initialization proof contract is satisfied or a genuine
bounded blocker remains.

## Frozen baseline

- Phase-13 branch `phase13/ps1-hercules-c0-init-v1`, commit
  `7bb4502450d47a0d3f3b207a072c5729277af278`
  (`FINAL_VERDICT=PASS_BOUNDED_C0_AND_CALLBACK_MEDIATION`).
- Phase-12 ancestor `7d76f242db2e9233ad9e023d0c63a6984fb118a0`.
- Phase-14 branch `phase14/ps1-hercules-init-closure-v1`.

## In scope

- A typed, documented `ps1.bios.B0.56` `GetC0Table()` service.
- A versioned, project-owned synthetic C0/exception-handler/early-card-handler
  surface inside the existing bounded synthetic window.
- The exact observable early-card IRQ patch dataflow required by `fn_80026ea8`.
- A typed `SYNTHETIC_BIOS_CONTINUATION` identity with provenance to `B0:0x56`.
- Validation of the existing `B0:0x57` `GetB0Table` service on the live path.
- The memory-card initialization chain and the next execution-reached
  initialization blockers.
- Reuse (never weakening) of the inherited initialization proof predicates.

## Out of scope / not claimed

- Asynchronous memory-card IRQ generation, a full interrupt controller, CPU
  COP0 exception delivery or JOY hardware timing unless a real Phase-14
  frontier requires them.
- First-frame graphics/CD/GTE proof (`NOT_PROVEN`; banked reconnaissance only).
- Playability and general PS1 compatibility.
- Any claim that a synthetic address is an authentic PS1 BIOS address.

## Phase-14 target proof

`OPENRECOMP_PHASE14_HERCULES_INITIALIZATION_PROOF` may be promoted to `PASS`
only when the inherited initialization contract predicates
(`INIT-BOUNDARY`, `INIT-NO-FAIL-CLOSED`, determinism, no fabrication) hold on the
real private-fixture production trace. Otherwise the honest result is
`NOT_PROVEN` with the exact remaining frontier recorded.
