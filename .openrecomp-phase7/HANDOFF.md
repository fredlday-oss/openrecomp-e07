# OpenRecomp Phase 7 Handoff

STATUS: Phase 7 `ACTIVE` - stage P7-00 (Phase-7 boundary) in progress. The
frozen queue `P7-01` .. `P7-99` is recorded in `STAGE_QUEUE.md` and becomes
frozen at the P7-00 `PASS` boundary. Phase 6 is COMPLETE and frozen at the
P6-99 verdict commit `1643817d43196c43155805249137e4b4e4a21eb1`, tree
`cda3f535be43dc6f3d4b457d11d356ae39ea34af`, with
`OPENRECOMP_P6_99=PASS`,
`OPENRECOMP_PHASE6_FINAL_VERDICT_V1=PASS tests=108`,
`OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS` (bounded audited public MMC1
claim only); `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` remains
permanent.

Baseline reconciliation: the mission baseline names an annotated tag
`openrecomp-phase6-pass`; the frozen Phase-6 P6-99 record states that no
terminal tag was created or required. The authoritative baseline is the
P6-99 verdict commit/tree above. Phase 7 records this as
`BASELINE_TAG_STATUS=ABSENT_RECONCILED` and does not fabricate a frozen
artifact.

Phase 7 objective (reserved `NOT_PROVEN` until P7-99): resolve the exact
translation/control-flow compatibility frontier exposed by the private TMNT
run - undocumented opcode `0x7C` at `0xC570`, the three `$E2` indirect jump
sites `0x86E8`/`0x8956`/`0x8F3C` and the 1048-instruction bank-switched
`$8000-$BFFF` candidate window - through evidence-based classification,
bank-aware reachability, indirect-target analysis and a bounded public
proof, without guessing hardware behaviour, indirect targets,
undocumented-instruction semantics, bank state or platform behaviour.

Reserved markers:

- `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN` (P7-99 may issue
  PASS for the bounded public translation/control-flow claim only)
- `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` (never promoted)
- `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN` (never promoted without
  actual generated-native meaningful interactive execution)

## Firm constraints carried into Phase 7

- Never mutate the frozen Phase-1/Phase-2/Phase-3/Phase-4/Phase-5/Phase-6
  histories, tags, evidence, gates or verdicts. Phase-7 work is additive under
  `.openrecomp-phase7/` plus new `tools/test_phase7_*` gates.
- Never commit, copy, embed or package the private TMNT image bytes or any
  ROM-derived binary copy (`FIXTURE_POLICY.md`, `CONTROL_POLICY.md` rule 11).
- Every public Phase-7 proof fixture is an original Apache-2.0 NES program
  authored for Phase 7 with full recorded provenance.
- Fail closed on unsupported mappers, MMC1 variants/wiring, unproven opaque
  opcodes, unresolved indirect targets, ambiguous bank provenance and
  unknown platform behaviour; never guess.
- Never execute original guest CPU code directly on the host. Native execution
  must come from generated host code.
- One implementation frontier at a time; every official stage gate runs twice
  with byte-identical stdout, empty stderr and exit 0.

## P7-00 outcome (PASS)

Markers: `OPENRECOMP_P7_00=PASS`,
`OPENRECOMP_PHASE7_BOUNDARY_V1=PASS tests=96`; the terminal, general and
playability markers are reserved as `NOT_PROVEN`.

- Branch `phase7/nes-translation-frontier-v1` at the frozen Phase-6 terminal
  commit `1643817...`, tree `cda3f535...`; the missing Phase-6 baseline tag is
  recorded as `ABSENT_RECONCILED` (the frozen P6-99 record states no tag was
  created or required); no frozen artifact was modified or fabricated.
- The Phase-6 final verdict gate independently re-passed twice in a
  reconstructed pre-verdict context with byte-identical stdout to the recorded
  official capture (3750 bytes raw `d7e96e11...`, LF `4fafd384...`,
  `tests=108`) and regenerated the committed `p6_99_tests.json`
  (`e7e462f1...`). The reconstruction used a temporary detached worktree that
  was removed afterwards.
- Phase-7 control plane established and deterministic; queue `P7-01` ..
  `P7-99` frozen; `TRANSLATION_FRONTIER_STATUS=NOT_PROVEN`; no
  translation/control-flow capability claimed.
- ROM safety verified: private fixture 262160 bytes / SHA-256 `2a9345e6...`
  present outside the worktree; no ROM image or private copy anywhere in the
  repository; `.gitignore` ROM rules and probes verified; public/private
  separation recorded in `FIXTURE_POLICY.md`.
- Two official runs byte-identical raw (`8d5b206b...`, 3690 bytes) and LF
  (`66052b58...`), empty stderr, exit 0; `p7_00_tests.json` sha256
  `d0ef5d68...` in both runs; control-plane manifest sha256
  `86f2bcd0...`.
- Evidence: `.openrecomp-phase7/evidence/P7-00/`.

## P7-01 outcome (PASS)

Markers: `OPENRECOMP_P7_01=PASS`,
`OPENRECOMP_PHASE7_FRONTIER_REDERIVATION_V1=PASS tests=49`; terminal,
general and playability markers reserved as `NOT_PROVEN`.

- The private TMNT frontier was re-derived from scratch through the frozen
  Phase-6 pipeline and workflow; all eight comparison classes are true:
  pipeline projection, workflow projection, P6-13 frontier record, P6-10
  blockers, P6-12 private blockers, runtime support identity `2e3fa4ba...`,
  image identity `2a9345e6...` (262160 bytes) and mapper-blocker supersession.
- Confirmed exactly: undocumented opcode `0x7C` at `0xC570` (predecessor
  `jsr` at `0xC56D`; walk stops after 1250 candidate instructions / 2711
  bytes; 202 fixed, 1048 low window; 42 opcode forms; `pending_at_stop=11`);
  unresolved `jmp ($00E2)` at `0x86E8`/`0x8956`/`0x8F3C` with empty targets;
  blockers `unsupported_opcode`/`unresolved_indirect_control_flow`/
  `bank_state_unresolved`/`platform_runtime_not_tested`.
- No mapper blocker has returned: ingestion `SUPPORTED_MMC1`, variant
  `SUPPORTED_PROFILE`, P6-01 mapper blocker still `SUPERSEDED`.
- Translation/generated sources/native build/native execution remain
  `NOT_ATTEMPTED`/`NOT_GENERATED`; runtime platform `NOT_TESTED`.
- Two official runs byte-identical raw (`fc9f6a0e...`, 2589 bytes) and LF
  (`bd28ad98...`), empty stderr, exit 0; `p7_01_tests.json` sha256
  `8c518674...` in both runs.
- The P7-00 boundary gate was re-run as a regression from this later stage
  (`OPENRECOMP_P7_00=PASS`); its `control-plane:current-stage` check was
  relaxed from an exact `P7-00` pin to the `P7-\d\d` stage shape so frozen
  boundaries remain re-runnable. No P7-00 evidence changed.
- Evidence: `.openrecomp-phase7/evidence/P7-01/`.

## P7-02 outcome (PASS)

Marker: `OPENRECOMP_PHASE7_OPCODE_CLASSIFICATION_V1=PASS tests=37`;
terminal, general and playability markers reserved as `NOT_PROVEN`.

- Classification: the `0x7C` byte at `0xC570` is `DATA_NOT_CODE` - the low
  byte of the first 16-bit code pointer in an inline dispatch table following
  `jsr $C71F` at `0xC56D`.
- Evidence chain: only static predecessor is the `jsr` fallthrough; the
  callee at `0xC71F` pulls the pushed return address (`pla`/`sta $00`,
  `pla`/`sta $01`), reads pointer pairs through `lda ($00),y` and dispatches
  through `jmp ($0002)`; the inline table at `0xC570` has exactly six
  in-window targets (`$C57C`, `$C644`, `$C679`, `$C686`, `$CB24`, `$C6B6`)
  and documented code resumes at `0xC57C`; a nested table at `0xC581` has
  four targets (`$C589`, `$C5B4`, `$C5FE`, `$C62C`); the byte stream after
  `0xC570` is not a coherent documented stream (undocumented byte within
  nine bytes).
- No undocumented-opcode semantics were added; the frozen decoder is
  unchanged (151 documented opcodes, `0x7C` still rejected) and no universal
  claim is made.
- The classifier is proven on original synthetic public images: full idiom ->
  `DATA_NOT_CODE`; non-consuming callee, missing table and literal
  predecessor -> `AMBIGUOUS`; reachable documented address -> `REACHABLE_CODE`;
  no predecessor -> `UNREACHABLE`.
- Two official runs byte-identical raw (`1a10323c...`, 1802 bytes) and LF
  (`6ffe5e57...`), empty stderr, exit 0; `p7_02_tests.json` sha256
  `f94b8364...` in both runs.
- Evidence: `.openrecomp-phase7/evidence/P7-02/`.

## P7-03 outcome (PASS)

Marker: `OPENRECOMP_PHASE7_OPCODE_FIXTURE_V1=PASS tests=49`; terminal, general
and playability markers reserved as `NOT_PROVEN`.

- Original Apache-2.0 public fixture
  `.openrecomp-phase7/fixture/p7_inline_dispatch_fixture.asm` built
  deterministically with the frozen Phase-5 assembler and cross-checked
  against the frozen decoder: ROM sha256 `66c4d8c7...` (40976 bytes), 2 x
  16 KiB PRG / 1 x 8 KiB CHR, mapper 1, horizontal, vectors NMI `$C140` /
  RESET `$C000` / IRQ `$C141`.
- The fixture reproduces the inline-dispatch idiom: `jsr $C100` at `$C018`
  followed by a three-entry inline pointer table at `$C01B` whose first byte
  is `0x7C`, return-address-consuming dispatcher, documented resume at
  `$C021`, targets `$C07C`/`$C090`/`$C0A0`, exit thunk `jmp ($02FF)` at
  `$C130`.
- The frozen P7-02 classifier returns `DATA_NOT_CODE` at the table base with
  the expected structural evidence; no undocumented-opcode semantics were
  added and the decoder is unchanged (151 documented opcodes, `0x7C` absent).
- Differential verification: the independent static pointer model predicts
  `$C07C`/`$C090`/`$C0A0` for selectors 0/1/2 and the frozen independent 6502
  reference core over the frozen MMC1 platform executes the fixture with exit
  reached and markers `$10`/`$11`/`$12`; out-of-range selector 3 and bad
  selector types fail closed; a tampered dispatcher classifies `AMBIGUOUS`.
- Two official runs byte-identical raw (`6edadcda...`, 2329 bytes) and LF
  (`59ffed5c...`), empty stderr, exit 0; `p7_03_tests.json` sha256
  `29405ee8...` in both runs.
- Evidence: `.openrecomp-phase7/evidence/P7-03/`.

## Evidence-completion fix (P7-01/P7-02)

The P7-01 and P7-02 stage gates did not write their extra evidence sidecars;
fixed in commit `phase7: write stage evidence sidecars in P7-01/P7-02 gates`
(`frontier_rederivation.json` and `opcode_classification.json` are now
present). Both stages were re-run officially with byte-identical stdout and
identical `p7_01_tests.json`/`p7_02_tests.json` hashes.

## P7-04 outcome (PASS)

Marker: `OPENRECOMP_PHASE7_BANK_REACHABILITY_V1=PASS tests=289`; terminal,
general and playability markers reserved as `NOT_PROVEN`.

- New bank-aware model `.openrecomp-phase7/src/p7_bank_reachability_v1.py`
  with code identity `(physical bank, cpu address)`, explicit fixed/
  switchable windows via the frozen PRG reference model (240 layout
  combinations matched), separate control/PRG provenance, statically proven
  constant bank commits, fail-closed `UNRESOLVED` expansion, bounded
  unresolved candidates and explicit `multi_bank_cpu_addresses` non-merging.
- Original Apache-2.0 synthetic fixtures
  `.openrecomp-phase7/src/p7_bank_fixtures_v1.py` prove: proven bank commit
  and switchable call (bank 2 `PROVEN`), bit-7 reset handling, unknown-value
  expansion (all banks candidates, `$8000` under 4 banks, never merged),
  consecutive-write suppression ambiguity, window-spanning fail close and the
  frozen public Phase-6 MMC1 proof fixture (28 proven fixed-bank
  instructions, unresolved-limited loops).
- `tools/test_phase7_bank_reachability_v1.py`: 289 checks; two official runs
  byte-identical raw (`4ff35a0c...`, 10014 bytes) and LF (`897f6904...`),
  empty stderr, exit 0; `p7_04_tests.json` sha256 `12ddbd03...`.
- Evidence: `.openrecomp-phase7/evidence/P7-04/`.

## P7-05 outcome (PASS)

Marker: `OPENRECOMP_PHASE7_BANK_STRUCTURE_V1=PASS tests=38`; terminal,
general and playability markers reserved as `NOT_PROVEN`.

- Original Apache-2.0 public bank-switching fixture
  `.openrecomp-phase7/fixture/p7_bank_switching_fixture.asm` (ROM sha256
  `902a9c42...`, 4 x 16 KiB PRG / 1 x 8 KiB CHR) commits bank 1 from the
  fixed bank and calls `$8000`; the bank-1 routine calls the fixed helper
  `$C100`.
- Bank-aware neutral structure `.openrecomp-phase7/src/p7_bank_structure_v1.py`
  builds one CFG/function/unit structure per proven physical bank (bank 1: 4
  instructions, 1 function; bank 3: 22 instructions, >= 4 functions) with
  cross-bank call entries `$8000` (bank 1) and `$C100` (bank 3), two proven
  cross-bank edges, one unresolved indirect site at `$C024` with no
  fabricated targets and no merged CPU addresses.
- The bank model gained additive bank-qualified `instructions`/`edges`
  outputs; the P7 reference driver now syncs its decode image to the live
  MMC1 window state (switchable-window execution); P7-03 reference behavior
  re-verified unchanged.
- Fail-closed: mutated edge, missing edge, non-OK reachability and truncated
  PRG all rejected.
- Two official runs byte-identical raw (`70bd60ca...`, 1917 bytes) and LF
  (`74c0bb54...`), empty stderr, exit 0; `p7_05_tests.json` sha256
  `670fd4bc...`.
- Evidence: `.openrecomp-phase7/evidence/P7-05/`.

## P7-06 outcome (PASS)

Marker: `OPENRECOMP_PHASE7_INDIRECT_MODEL_V1=PASS tests=51`; terminal,
general and playability markers reserved as `NOT_PROVEN`.

- New indirect-jump evidence model
  `.openrecomp-phase7/src/p7_indirect_evidence_v1.py`: unique-chain reaching
  definitions, constant/ROM/paired-table value sources, bounded 8-bit index
  domain simulation, per-bank candidate enumeration and target validation,
  explicit `RESOLVED_EXACT`/`RESOLVED_FINITE_SET`/`UNRESOLVED`/`IMPOSSIBLE`
  states; targets are never guessed.
- Private `$E2` sites all classify `RESOLVED_FINITE_SET`:
  - `0x86E8`: bank 0 `PROVEN`, table `$8FB8`/`$8FB9`, domain `{0,2,4,6}`,
    4 feasible targets, 0 infeasible;
  - `0x8956`: bank 0 candidate (`UNRESOLVED` provenance), table
    `$8FCC`/`$8FCD`, domain `{0,2,4,6}`, 4 feasible targets;
  - `0x8F3C`: `MODEL_UNREACHED`, all 8 banks evaluated, table
    `$8FC0`/`$8FC1`, 128 index values, 300 feasible pairs, 442 infeasible.
- Public unit states proven on original synthetic images: exact single
  target, masked finite set, unresolved RAM-sourced pointer, impossible
  out-of-window pointer.
- Two official runs byte-identical raw (`2e407ded...`, 2170 bytes) and LF
  (`d8fc208e...`), empty stderr, exit 0; `p7_06_tests.json` sha256
  `700c9d33...`.
- Evidence: `.openrecomp-phase7/evidence/P7-06/`.

## P7-07 outcome (PASS)

Marker: `OPENRECOMP_PHASE7_INDIRECT_FIXTURE_V1=PASS tests=42`; terminal,
general and playability markers reserved as `NOT_PROVEN`.

- Original Apache-2.0 public fixture (`p7_indirect_flow_fixture.asm` +
  `p7_indirect_flow_bank.asm`, ROM sha256 `1c9ad658...`) with three `$E2`
  dispatch sites in bank 1: exact (`$8013` -> `$8033`), masked four-entry
  finite set (`$8025` -> `$8100/$8110/$8120/$8130`) and unresolved
  RAM-sourced pointer (`$8030`), all with `PROVEN` bank-1 provenance.
- Reference execution through the frozen independent 6502 core/MMC1 platform
  for selectors 0/1/2: markers `$E0/$01/$F0`, `$F2/$02/$F0`, `$00/$00/$F0`;
  both exact and finite model-predicted targets were executed; the
  unresolved runtime path correctly resolves only at runtime.
- Negative: invalid selector types rejected, zeroed table -> `IMPOSSIBLE`,
  short image fails closed.
- Two official runs byte-identical raw (`30175c6a...`, 2006 bytes) and LF
  (`1890e432...`), empty stderr, exit 0; `p7_07_tests.json` sha256
  `4b3491a7...`.
- Evidence: `.openrecomp-phase7/evidence/P7-07/`.

## P7-08 outcome (PASS)

Marker: `OPENRECOMP_PHASE7_TRANSLATION_INTEGRATION_V1=PASS tests=28`;
terminal, general and playability markers reserved as `NOT_PROVEN`.

- New integration `.openrecomp-phase7/src/p7_frontier_integration_v1.py`:
  bank-aware frontier walk with resolved indirect dispatch specialization and
  fail-closed exclusion of unresolved sites; host emission only for proven
  paths through the frozen Phase-5/6 emitters.
- Public indirect-flow fixture: 61 proven identities across banks 1 and 3
  (12 dynamic target nodes), 2 resolved dispatch sites, 1 fail-closed site
  (`$8030` excluded); host program `231a3a09...` (61 instructions), support
  `5ea325b2...`; native build `EXECUTABLE_REPRODUCIBLE` with executable
  sha256 `23679fb8...`.
- Data exclusion: the P7-03 classification fixture's inline table stays
  `DATA_NOT_CODE` and the bank-aware frontier fails closed exactly there.
- Negative: out-of-set assignment target and tampered table both fail closed.
- Two official runs byte-identical raw (`b32eb763...`, 1610 bytes) and LF
  (`d12eaf4c...`), empty stderr, exit 0; `p7_08_tests.json` sha256
  `30bde79a...`.
- Evidence: `.openrecomp-phase7/evidence/P7-08/`.

## P7-09 outcome (PASS)

Marker: `OPENRECOMP_PHASE7_NATIVE_EXECUTION_V1=PASS tests=34`; terminal,
general and playability markers reserved as `NOT_PROVEN`.

- Three native variants of the public indirect-flow fixture built
  reproducibly and run 3x byte-identically each:
  - exact (selector 0): `failed=0`, `exit=1`, `pc=$C205`, `steps=38`,
    `clock=108`, RAM digest `0xAA5AB26E...`; executable `23679fb8...`
    (byte-identical to the P7-08 build);
  - finite (selector 1, index 2 -> `$8110`): `steps=43`, `clock=123`, RAM
    digest `0x7F6B5F25...` (distinct path proof); executable `7da08a48...`;
  - unresolved (selector 2): `failed=1`, `error=pc outside the emitted
    image`, `pc=$8030` (fail closed, no host case emitted); executable
    `ea6bef23...`.
- All variants show the MMC1 runtime bank commit
  (`mmc1_regs=0C000001`, PRG windows `(1,3)`); execution is generated host
  code only.
- Two official runs byte-identical raw (`ac9c15e2...`, 1712 bytes) and LF
  (`e393a62c...`), empty stderr, exit 0; `p7_09_tests.json` sha256
  `d84bc50e...`.
- Evidence: `.openrecomp-phase7/evidence/P7-09/`.

## Exact next action

Start P7-10 (independent reference equivalence): compare the generated native
execution against the independently structured reference for the public
fixture variants over CPU state, RAM, mapper/bank state, PPU state where
relevant, controller transcript, interrupt counts, indirect-control-flow
transcript, translation/service transcript and bounded final state, requiring
exact bounded equivalence. Do not push.
