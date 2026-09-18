# OpenRecomp Phase 6 Scope

Final bounded objective (not yet proven):

`OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF`

Permanent general marker:

`OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`

## Phase-6 purpose

Expand the proven Phase-5 NES static-recompilation path from NROM/mapper 0 to a
bounded, audited MMC1/mapper 1 platform path. Phase 6 reuses the frozen
Phase-4/Phase-5 architecture-neutral ProgramModel / CFG / function-discovery /
translation-unit / host-emission / runtime / platform-adapter layers and adds
only the MMC1 mapper behaviour, fixture and platform behaviour proven necessary
by deterministic evidence.

The primary public proof must use a legally redistributable original
Apache-2.0 MMC1 NES fixture. The private TMNT image remains
`PRIVATE_LOCAL_COMPATIBILITY_FIXTURE` only and never enters public artifacts.

## Intended progression

original Apache-2.0 public MMC1 fixture
-> MMC1 requirements and fixture inventory
-> MMC1 serial register protocol (five-write shift register, reset bit)
-> MMC1 PRG banking (32 KiB / 16 KiB modes, fixed-first/fixed-last, bank mask)
-> MMC1 CHR banking (8 KiB / 4 KiB) and mirroring (one-screen/vertical/horizontal)
-> MMC1 PRG-RAM and explicit variant boundary
-> deterministic fixture build with recorded provenance
-> static recompilation integration (ProgramModel/CFG/functions/units)
-> native execution through the generic runtime/platform adapter
-> independent structured reference equivalence
-> evidence-driven platform expansion (only what evidence requires)
-> reusable deterministic ROM-to-native workflow
-> private TMNT compatibility observations (separate, non-redistributed)

## Phase-6 goal (bounded)

The exact bounded Phase-6 claim is proven only if the audited tree supports:

- a deterministic MMC1 serial/shift-register protocol with register selection,
  reset-bit behaviour and fail-closed malformed/unsupported states;
- the MMC1 PRG bank modes and masking required by the proven fixture
  configuration, verified against independent bounded reference vectors;
- the MMC1 CHR bank modes and mirroring modes required by the proven fixture
  configuration, differentially verified at the PPU address-mapping boundary;
- the PRG-RAM behaviour required by the supported fixture, with unsupported
  MMC1 board variants/features explicitly classified and not inferred;
- a deterministic, legally redistributable original Apache-2.0 MMC1 public
  fixture with recorded provenance, toolchain, hashes, vectors and metadata;
- static recompilation of that fixture with reachable-code recovery,
  neutral structure construction and mapper service integration, without
  fabricated indirect targets or hardware behaviour;
- native host execution through the frozen generic runtime/platform adapter
  contracts, demonstrating deterministic behaviour involving bank switching,
  CPU, memory, PPU, input and timing, never executing guest 6502 code directly;
- exact equivalence for the bounded proof against an independently structured
  MMC1 reference path over deterministic input plans;
- a reusable deterministic ROM-to-native workflow that fails closed with
  explicit reasons for unsupported mapper/hardware paths;
- private TMNT compatibility observations recorded only as hashes, metadata,
  counts, addresses, classifications and stop reasons.

## Claim boundary

A Phase-6 PASS must not claim and P6-99 must not silently imply:

- general NES compatibility;
- all MMC1 boards, revisions, PRG/CHR configurations or wiring variants;
- all NES games;
- commercial-game compatibility;
- cycle accuracy;
- full PPU accuracy;
- full APU accuracy;
- Famicom Disk System compatibility;
- arbitrary 6502 compatibility.

## Terminal markers

- `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF` - reserved until P6-99; every earlier
  stage records the value `NOT_PROVEN`. P6-99 may issue `PASS` only for the
  exact bounded audited public MMC1 claim above.
- `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` - general NES /
  commercial compatibility is out of scope and is never promoted by Phase 6.

## Out of scope

Console hardware emulation; cycle accuracy; copyrighted or console-derived
assets; ROM redistribution of any kind; proprietary SDK material; mandatory
third-party renderer/audio backends; performance claims; arbitrary
self-modifying code; FDS images; MMC1 board variants not demonstrated by the
audited fixtures.
