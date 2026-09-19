# OpenRecomp Phase 7 Scope

Final bounded objective (not yet proven):

`OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF`

Permanent general markers (never promoted by Phase 7):

`OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`
`OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`

(`TMMT` is the exact spelling issued by the Phase-7 mission and denotes the
private TMNT playability status.)

## Phase-7 purpose

Phase 7 starts from the frozen Phase-6 MMC1 platform proof and resolves the
exact translation/control-flow compatibility frontier exposed by the private
TMNT compatibility runs, without guessing hardware behaviour, indirect
targets, undocumented-instruction semantics, bank state or platform behaviour.

Phase 7 is NOT a general NES compatibility phase. Its public proof must use
legally redistributable original fixtures. The private TMNT image remains
`PRIVATE_LOCAL_COMPATIBILITY_FIXTURE` only.

The exact Phase-6 frontier to resolve:

1. undocumented opcode `0x7C` at CPU address `0xC570` (classification
   evidence required; the byte must not be assumed to mean anything from its
   opcode value alone);
2. unresolved indirect jumps through zero-page pointer `$E2` at `0x86E8`,
   `0x8956`, `0x8F3C` (targets must never be guessed);
3. 1048 candidate instructions in the bank-switched `$8000-$BFFF` window
   (reachability across MMC1 PRG bank states must be modelled, not assumed);
4. translation/native execution not reached beyond this frontier;
5. additional platform behaviour `NOT_TESTED` until translation advances.

## Intended progression

Phase-6 frozen boundary
-> private TMNT frontier re-derivation (P7-01)
-> undocumented opcode 0x7C classification from evidence (P7-02)
-> public undocumented-opcode proof fixture and additive semantics (P7-03)
-> bank-aware cartridge reachability model (P7-04)
-> bank-aware ProgramModel / CFG integration plus public bank-switching
   fixture (P7-05)
-> indirect jump evidence model for the `$E2` sites (P7-06)
-> public indirect-control-flow proof fixture (P7-07)
-> translation frontier integration (P7-08)
-> native execution of the public Phase-7 fixture (P7-09)
-> independent reference equivalence (P7-10)
-> private TMNT frontier run with Phase-7 support (P7-11)
-> evidence-driven translation closure, zero-delta allowed (P7-12)
-> second private TMNT run (P7-13)
-> reusable bank-aware ROM-to-native workflow (P7-14)
-> whole regression (P7-90)
-> evidence index and compatibility matrix (P7-91)
-> final Phase-7 verdict (P7-99)

## Phase-7 goal (bounded)

The exact bounded Phase-7 claim is proven only if the audited tree supports:

- an evidence-backed classification of the `0x7C` byte at `0xC570` in the
  private image context (SUPPORTED_PROVEN, RECOGNIZED_UNSUPPORTED,
  DATA_NOT_CODE, UNREACHABLE, AMBIGUOUS or another explicitly justified
  fail-closed category), without a universal undocumented-opcode claim;
- an original Apache-2.0 public fixture exercising exactly the proven
  instruction/classification form, with differential verification against an
  independently structured oracle including flags, addressing, memory effects
  and negative cases (P7-03), or the equivalent public proof of the
  classification mechanism when the byte is data/unreachable/not an
  executable instruction;
- a bank-aware cartridge reachability model that tracks fixed and switchable
  windows explicitly, associates code addresses with cartridge bank state
  where required, never merges different physical bank contents sharing a CPU
  address range and fails closed on ambiguous bank provenance (P7-04);
- bank-aware neutral structure recovery that distinguishes banked code
  identities without fabricating cross-bank edges, with a public
  redistributable bank-switching fixture (P7-05);
- a deterministic indirect-jump evidence model for the three `$E2` sites
  tracking pointer writes/reads, bank state, memory provenance and feasible
  target sets with explicit `RESOLVED_EXACT` / `RESOLVED_FINITE_SET` /
  `UNRESOLVED` / `IMPOSSIBLE` states (P7-06);
- an original Apache-2.0 public indirect-control-flow fixture covering exact
  single-target resolution, finite target sets where supported, the
  unresolved/fail-closed case and the relevant bank switching (P7-07);
- integration into the static-recompilation pipeline that emits host code
  only for proven executable paths and keeps unknown control flow fail closed
  (P7-08);
- native host execution of the public Phase-7 fixture from generated host
  code only, never original guest 6502 execution (P7-09);
- exact bounded equivalence of the generated native execution against an
  independently structured reference over CPU state, RAM, mapper/bank state,
  PPU state where relevant, controller transcript, interrupt counts,
  indirect-control-flow transcript, translation/service transcript and
  bounded final state (P7-10);
- private TMNT frontier runs recording only hashes, metadata and derived
  evidence, determining exactly which frontier elements change (P7-11,
  P7-13);
- only translation/control-flow behaviour demonstrated necessary, each with
  deterministic independent verification; a documented zero-delta PASS is
  permitted when no further behaviour is justified (P7-12);
- a reusable bank-aware ROM-to-native workflow that accepts a local ROM path
  and outputs inventory, compatibility classification, bank-aware frontier,
  indirect-control-flow classification, generated native source/build when
  supported, or an explicit fail-closed blocker, never copying or packaging
  the source ROM (P7-14);
- a complete PROVEN / BOUNDED / UNPROVEN / UNSUPPORTED / NOT TESTED ledger
  keeping the Phase-5 NROM proof, the Phase-6 MMC1 proof, the Phase-7
  translation/control-flow proof, the private TMNT observations and general
  NES compatibility as separate sections (P7-91).

## Claim boundary

A Phase-7 PASS must not claim and P7-99 must not silently imply:

- general NES compatibility;
- commercial-game compatibility;
- TMNT playability unless actually demonstrated by generated native,
  meaningful interactive execution;
- all undocumented 6502 opcodes;
- all indirect-control-flow recovery;
- arbitrary bank-switched binaries;
- cycle accuracy;
- full PPU/APU accuracy;
- arbitrary 6502 compatibility.

TMNT playability is NOT required for Phase-7 PASS.

## Terminal markers

- `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF` - reserved until P7-99;
  every earlier stage records the value `NOT_PROVEN`. P7-99 may issue `PASS`
  only for the exact bounded public translation/control-flow claim above.
- `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` - general NES /
  commercial compatibility is out of scope and is never promoted by Phase 7.
- `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN` - the private TMNT
  playability status; never promoted without actual generated-native,
  meaningful interactive execution.

## Out of scope

Console hardware emulation; cycle accuracy; copyrighted or console-derived
assets; ROM redistribution of any kind; proprietary SDK material; mandatory
third-party renderer/audio backends; performance claims; arbitrary
self-modifying code; FDS images; NES mappers or board variants not
demonstrated by the audited fixtures; universal undocumented-opcode support.
