# P5-99 Final Phase-5 Verdict - Result

Verdict: `PASS` (bounded audited claim)

## Baseline

- Branch `phase5/nes-platform-v1` at commit `b5fdd71` (P5-91 boundary).

## Markers issued

- Stage marker: `OPENRECOMP_P5_99=PASS`
- Gate marker: `OPENRECOMP_PHASE5_FINAL_VERDICT_V1=PASS tests=87`
- Terminal marker: `OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=PASS` (for the exact
  bounded audited claim only; the reserved pre-verdict value recorded
  throughout P5-00 .. P5-91 was `NOT_PROVEN`)
- General compatibility marker:
  `OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`

## Preconditions verified

- Source integrity: root manifest `76f77bbc...`, Phase-3 manifest
  `a7d0953c...`, Phase-4 and Phase-5 manifests verified entry-by-entry,
  P3-99 record/gate and P4-99 record/gate identities.
- Frozen chain: annotated Phase-4 tag object `e7eaab18...` -> commit
  `b3c71fb...` -> tree `f2ca3080...`; Phase-3 object `ac315245...` -> commit
  `e16e4b29...` -> tree `a940f0d8...`; Phase-2/Phase-1 commits; descent.
- Control plane: every queue row `P5-00` .. `P5-91` `COMPLETE`, every ledger
  row `PASS`, terminal marker still reserved before the verdict, general
  marker `NOT_PROVEN`.
- Stage records: all fourteen recorded stage results `PASS` with no failure.
- Identities: public fixture ROM `272c94cd...`; translation program
  `6e4dcb44...` and support `2b411eea...`; native observable
  `state_fnv1a64=0x440A095E452B3BA9`, `steps=90904`; P5-10 equivalence true
  for all four plans; P5-09 interactivity records; package
  `447f72cc...`; P5-91 evidence index and claim ledger (12 PROVEN, 4 BOUNDED,
  4 private observations, 7 UNPROVEN, 4 UNSUPPORTED, 6 NOT TESTED); P5-90
  whole-regression byte-identical records; private TMNT
  `BLOCKED_UNSUPPORTED_MAPPER`.

## The proven bounded claim

The Phase-5 audited tree supports exactly this bounded claim (see `SCOPE.md`
and the P5-91 ledger): an iNES/NES 2.0 ingestion-to-native-execution static
recompilation path for the original Apache-2.0 public NES fixture, through
the shared architecture-neutral ProgramModel/CFG/function/translation-unit
layers and the Phase-4 generic runtime/platform contracts, with exact CPU
semantics, a bounded NROM CPU bus, bounded PPU/graphics and
input/timing/interrupt boundaries, independent-reference equivalence and a
reproducible public package.

## Explicit non-claims

A Phase-5 PASS does NOT imply: all NES games work; all mappers work; cycle
accuracy; full PPU accuracy; full APU accuracy; commercial-game
compatibility; Famicom Disk System compatibility; arbitrary 6502 binary
compatibility; general NES compatibility
(`OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`).

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 2971 bytes raw, raw sha256
    `bc1f1e97f9f34cb06eba388a96e3879e4304e9a38a7224051d1c05aceced1591`,
    LF sha256
    `2378b480a1be7cbb10219e3da0c0171c48de962fb45c31ac8033c28e0f133907`.
  - `p5_99_tests.json` sha256
    `b0e8267c70ab2e990ca74665d8020ba463280447dd9f5fb370f4411cfb6e72c9`.
- Gate sha256 `bc772128a91344e17d1ed00fb5e2b503aae8a0ef5e4ad9de35b7fbdfcba52143`.
- Terminal state recorded in `STATE.md` and `STAGE_QUEUE.md`; the pre-verdict
  reconstruction means a later re-run of this gate on the promoted tree
  reports the intended terminal state (as with P4-99).

## Evidence-template note

The stage runner's `determinism.json` `terminal_marker` field carries the
reserved template string `...=NOT_PROVEN`; the authoritative promoted markers
are this gate's stdout and `p5_99_tests.json` (both `...=PASS`). This is a
documented template limitation, not a claim change.

## Terminal-state snapshot note

The P5-12 package identity `447f72cc...` is the stage-time snapshot taken
with the pre-verdict control plane; the terminal `STATE.md`,
`STAGE_QUEUE.md` and `HANDOFF.md` updates were made after the P5-12 and P5-91
gates ran, so a fresh package rebuild would differ in those control-plane
bytes while the recorded identity (and the P5-91 index/report) remains the
audited snapshot. This is the intended terminal-state transition and not a
regression; the pre-verdict P5-12 reconstruction is preserved in the P5-12
evidence and in the package itself.

## Limitations

- The verdict is exactly the bounded audited claim; the P5-91 claim ledger
  and limitations apply unchanged.
- Private TMNT observations remain non-redistributed and outside the public
  claim.
- `FINAL_VERDICT` (general/arbitrary compatibility) remains `NOT_PROVEN`.

## Evidence files

`RESULT.md`, `p5_99_tests.json`, `official_runs.json`, `determinism.json`,
`run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`.

## Terminal state

Phase 5 is COMPLETE. No further Phase-5 stage remains. Any broader
compatibility claim requires a later phase with its own evidence.
