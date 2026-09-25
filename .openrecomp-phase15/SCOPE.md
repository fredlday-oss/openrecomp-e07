# OpenRecomp Phase 15 Scope

## Mission

Advance the frozen Phase-14 bounded initialization-closure result into a genuine
deterministic Hercules initialization proof by closing only the live
hardware/MMIO state required before the initialization boundary, and by iterating
the real bounded Hercules probe one execution-reached blocker at a time until the
semantic initialization boundary (`A0:0x43 Exec` → TITLE entry `0x800380A0`) is
reached cleanly or a genuine new architectural blocker remains.

## Frozen baseline

- Phase-14 terminal branch `phase14/ps1-hercules-init-closure-v1`, commit
  `830be0f7be998061e8d442134cfae511d5dd8c62`.

## In scope

- A bounded, project-owned interrupt-controller MMIO model (`I_STAT`
  `0x1F801070`, `I_MASK` `0x1F801074`) with explicit allowed widths and PS1
  acknowledgement semantics.
- The minimum live `SYS_CONTROL`/`COM_DELAY` (`0x1F801020`) and DMA2 register
  state (`D2_MADR`/`D2_BCR`/`D2_CHCR`/`DPCR`) reached before the boundary.
- Root-counter (`0x1F801110`) and GPUSTAT (`0x1F801814`) bounded deterministic
  behaviour where the live path requires it.
- Root-cause closure of the Phase-14 address-zero store denial without making
  address zero writable.
- Recovery and verification of the semantic initialization boundary and of the
  fail-closed-clean execution prefix before it.
- Reuse (never weakening) of the inherited initialization proof predicates.

## Out of scope / not claimed

- CPU COP0 interrupt delivery, general exception vector dispatch or arbitrary
  interrupt scheduling.
- Timer1 IRQ generation, GPU command execution, GPU rasterization, VRAM state or
  a renderer.
- First-frame graphics/CD/GTE proof; playability; general PS1 compatibility.
- Any claim that a synthetic address is an authentic PS1 BIOS address.

## Phase-15 target proof

`OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF` may be promoted to `PASS`
only when every inherited initialization contract predicate holds on the real
private-fixture production trace and the prefix from boot to the `A0:0x43 Exec`
boundary is fail-closed clean and deterministic. Otherwise the honest result is
`NOT_PROVEN` with the exact remaining frontier recorded.
