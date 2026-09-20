# P9-90 result: Phase-9 whole-project regression

Status: `PASS` (221 checks)

Markers:

- `OPENRECOMP_P9_90=PASS`
- `OPENRECOMP_PHASE9_WHOLE_REGRESSION_V1=PASS tests=221`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_whole_regression_v1.py`.

## Audited on one tree

- frozen Phase-8 terminal boundary commit
  `61136fc37cf0810e64241addd8f57a91872bc0af`, tree
  `f9262497b82fe0027c3b23432ba7bd8cbccdf433`, branch
  `phase8/mips32-end-to-end-native-v1`;
- all fifteen frozen Phase-8 terminal evidence/control-plane hashes, the
  frozen P8-90/P8-91/P8-99 record hashes, the frozen Phase-3 module hashes,
  the Phase-8 source manifest and the Phase-9 source manifest;
- no tracked file under `.openrecomp-phase1` .. `.openrecomp-phase8` changed
  against the baseline outside the documented pre-existing Phase-3 residue.

## Live Phase-9 gate re-runs (byte-identical stdout)

All thirteen completed Phase-9 official gates re-ran live with byte-identical
stdout, empty stderr and exit 0, redirected to scratch evidence:

| Stage | Tests | Gate |
|---|---|---|
| P9-00 | 95 | boundary + control plane (`--verify-only`) |
| P9-01 | 163 | PS-X EXE ingestion |
| P9-02 | 128 | memory-map contract |
| P9-03 | 66 | MIPS32 pipeline integration |
| P9-04 | 31 | translation-frontier closure |
| P9-05 | 88 | BIOS/service boundary |
| P9-06 | 102 | GPU/runtime boundary |
| P9-07 | 64 | input/timer/event boundary |
| P9-08 | 60 | SPU/audio boundary |
| P9-09 | 73 | CD-ROM/file-service boundary |
| P9-10 | 49 | native build + execution |
| P9-11 | 155 | private Hercules validation |
| P9-12 | 27 | hardening + reproducibility |

## Live frozen Phase-8 terminal audits (byte-identical stdout)

| Stage | Tests | Stdout raw SHA-256 |
|---|---|---|
| P8-90 | 215 | `29652124...` (re-runs Phase-1 host gates, the reconstructed Phase-7 chain and all thirteen Phase-8 gates; 1463 re-verified tests) |
| P8-91 | 27 | `4e7b72ed...` |
| P8-99 | 92 | `00d50af7...` |

The live P8-91 re-run regenerates its committed index from the current
evidence; the committed index predates the P8-99 post-verdict stabilization
and records stale P8-99 hashes. Frozen evidence was snapshotted and restored,
so the re-run could not modify any frozen Phase-8 file
(`frozen_evidence_restored: [".openrecomp-phase8/evidence/P8-91/evidence_index.json"]`);
all frozen hashes re-verify after the runs and `git status` for
`.openrecomp-phase8` is clean.

## Committed Phase-9 evidence unchanged

An evidence snapshot taken before the live re-runs is byte-identical after
them; no committed Phase-9 evidence file was modified.

## Totals

- Phase-9 gate tests re-verified live: 1101;
- Phase-8 terminal audit tests: 334 (P8-90 215, P8-91 27, P8-99 92);
- P8-90 re-verified historical tests: 1463 (Phase-7 852 + Phase-8 611);
- **total re-verified tests: 3113**.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-90
--script tools/test_phase9_whole_regression_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-90 --tests-json p9_90_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 236 bytes (LF), sha256
`19a0d0a5a2c9b4b937bc195dc4597c01155da6dcad64c5bce0422a83dd857c8a`.

Sidecar identities:

- `p9_90_tests.json` `3cec07cd23add4a665749534b060f0c868a2b89b02c9579ab5ebeb7f328cc1ea`;
- `whole_regression.json` `1a7ea773c2cab5656724acbb273bdf6273e4b08bc1cc6372a6e48689c820c59d`;
- `official_runs.json` `4d1240b5b6cf7fbbb27de8ffd0c80e01db5b3ca30b50e873dbd9ab85e7324a7a`;
- `determinism.json` `417b572b29d55ff2edf2fc25f57c21b97e10824de7a296833909a5bd16fd987e`;
- `run1.txt` = `run2.txt` `19a0d0a5a2c9b4b937bc195dc4597c01155da6dcad64c5bce0422a83dd857c8a`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Claim-ledger delta

None. P9-90 re-verifies the frozen Phase-1..Phase-8 chain and the completed
Phase-9 stages; it adds no capability and promotes no marker.

## Next stage

`P9-91` - evidence closure and claim ledger: verify all sidecar hashes,
manifests, stage records and evidence indexes, and classify every Phase-9
claim as PROVEN / BOUNDED / NOT_PROVEN / NOT_TESTED.
