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

## Exact next action

Start P7-03 (public undocumented-opcode proof fixture): because P7-02 proved
the byte is data rather than an executable instruction, author an original
Apache-2.0 NES fixture that reproduces the inline-dispatch classification
mechanism (call site with inline pointer table, return-address-consuming
dispatcher, documented code resume) and prove the classification mechanism
end-to-end rather than adding false opcode semantics. Do not push.
