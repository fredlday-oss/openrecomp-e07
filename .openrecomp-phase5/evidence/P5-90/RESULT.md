# P5-90 Phase-5 Whole Regression - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `ee6a98a` (P5-12 boundary).

## Objective (frozen queue)

Run Phase-1 + Phase-2 + Phase-3 + Phase-4 + Phase-5 required gates. Require
deterministic/byte-identical outputs where applicable.

## Frozen chain re-verification

- `openrecomp-phase4-pass` annotated tag object
  `e7eaab18...` -> commit `b3c71fb...` -> tree `f2ca3080...`;
  `openrecomp-phase3-pass` object `ac315245...` -> commit `e16e4b29...` ->
  tree `a940f0d8...`; Phase-2 `01b1d7cb...` and Phase-1 `46c2f971...`;
  descent from the Phase-4 boundary commit verified.
- Root manifest `76f77bbc...` (134 entries), Phase-3 manifest `a7d0953c...`
  (24 entries), Phase-4 manifest verified entry-by-entry, Phase-5 manifest
  (28 entries, terminal gates hash-pinned in their own evidence) verified.
- P3-99 record `c893250b...` and gate `ba581490...`; P4-99 record
  `f13cf891...`, gate `6c357c18...`, terminal marker `PASS`.

## Stage gates (byte-identical to official captures)

Every Phase-5 gate P5-00 .. P5-12 re-ran from the audited tree with scratch
evidence; each exited 0 with empty stderr and stdout byte-identical to its
recorded official run1 capture:

- P5-00 boundary (80 checks), P5-01 ingestion (53), P5-02 frontier (33),
  P5-03 semantics (46), P5-04 structure (34), P5-05 bus (21),
  P5-06 PPU (32), P5-07 timing/input (34), P5-08 host emission (48),
  P5-09 native execution (40), P5-10 reference equivalence (37),
  P5-11 private TMNT (31), P5-12 package (190).

The P5-00 re-run internally re-executed the Phase-4 final verdict gate twice
in the reconstructed pre-verdict context (the full Phase-1..Phase-4 chain).

## Hygiene

- No tracked committed Phase-5 evidence was modified (scratch evidence used).
- The one frozen Phase-4 sidecar refreshed by the P5-06 regression
  (`.openrecomp-phase4/evidence/P4-06/p4_06_tests.json`) was restored to the
  committed bytes immediately; the final frozen-clean check passes.

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 2039 bytes raw, raw sha256
    `e487dbc0221d813d1d1138065be422bf8440d96f64d0dee5cd94d80f123ff5c5`,
    LF sha256
    `5cbea86f0baaeb395679f453711e1ffe2f1a895d83db66337a581ac60e1ce565`.
  - `p5_90_tests.json` sha256
    `431d4e5a9766b2c3aff214146541f1346ef3d65ae8721b1cead93db298172262`.
- Markers: `OPENRECOMP_P5_90=PASS`,
  `OPENRECOMP_PHASE5_WHOLE_REGRESSION_V1=PASS tests=59`; terminal/general
  reserved as `NOT_PROVEN`.
- Gate sha256 `ccecffe187e077566f4bbf2047ee79d60e3e98c1d29e215e9adc7dd8b76da392`.

## Limitations

- The audit re-runs gates and frozen-boundary checks; it adds no capability
  and promotes no marker.
- Byte-identical stdout proves the audited tree reproduces every recorded gate
  result under the same toolchains; it does not extend the bounded claim.

## Evidence files

`RESULT.md`, `p5_90_tests.json`, `official_runs.json`, `determinism.json`,
`whole_regression.json`, `run1.txt`, `run2.txt`, `run1.err.txt`,
`run2.err.txt`.

## Next stage

P5-91 - Evidence index + compatibility limitations.
