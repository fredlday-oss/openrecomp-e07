# P10-90 result: whole-project regression

Status: `PASS` (155 checks)

Markers:

- `OPENRECOMP_P10_90=PASS`
- `OPENRECOMP_PHASE10_WHOLE_REGRESSION_V1=PASS tests=155`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_whole_regression_v1.py`.

## Audited on one tree

- frozen Phase-9 terminal boundary commit
  `08c639d9032a364163f2985432744be420d402eb`, tree
  `900dccf06ce3d5df7b499a9f05a6ceea060114d7`, frozen branch
  `phase8/mips32-end-to-end-native-v1` with its tip identity verified;
- the frozen Phase-9 terminal/control-plane hashes (10) and the frozen Phase-8
  terminal records (6);
- the documented prior tracked diff (the two Phase-3 evidence files) and the
  frozen Phase-8/Phase-9 source manifests plus the Phase-10 source manifest
  (33 entries);
- the frozen Phase-8 terminal audits verified through the frozen `P9-90`
  in-place record (byte-identical stdout on the audited commit/tree at the
  audited path) and the frozen evidence hashes.

## Live re-runs (byte-identical stdout, empty stderr, exit 0)

| Run | Identity |
|---|---|
| Phase-1 host gates | 44 pass / 0 fail / 2 toolchain skips, stdout `2a9d1bba...` |
| Phase-9 gates P9-01..P9-12 (scratch evidence) | 1101 tests, byte-identical to their committed captures |
| P9-00 boundary | reconciled frozen branch-name assertion; frozen capture identity verified |
| Phase-10 gates P10-00..P10-12 (scratch evidence) | 1633 tests, byte-identical to their committed captures |

The committed Phase-10 evidence root is verified untouched by the re-runs.

## Counts

- historical gates: 16; historical re-verified tests: 1435
  (Phase-8 terminal audits 334 + Phase-9 gates 1101);
- Phase-10 gates: 13; Phase-10 tests: 1633;
- total re-verified tests: 3068.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-90
--script tools/test_phase10_whole_regression_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-90 --tests-json p10_90_tests.json`, exit 0,
empty stderr, both runs byte-identical: raw stdout 5279 bytes sha256
`90630afd040fe19f21c6ae25f07e6eefba07aa95c061f15c8488e32a2fd1aad`, LF capture
sha256 `0370518d1c9f91f432fdf1d419d3226c8e86b6dc0ee5721b6fbcdc938089b671`; both
generated sidecars byte-identical across the runs.

Sidecar identities:

- `whole_regression.json` `d4ae5b7b574aec643c5f8b840a64655ba072add969396046f6ad72d8724f5e80`;
- `p10_90_tests.json` `c5386f35aaabd0546f3bbd865ce6f98beb7309b11407fdd2bce6634e838171dd`;
- `official_runs.json` `505704df1403fe80cdc40164960b38245f2843b21d1a46716022ca4b0b76edd8`;
- `determinism.json` `9f47dc20195b0985fe316be24daaf1eeefbf7f18e16049b01844294d062d8c8d`;
- `run1.txt` = `run2.txt` `0370518d1c9f91f432fdf1d419d3226c8e86b6dc0ee5721b6fbcdc938089b671`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Reconstruction mechanism (documented, not silent)

A temporary worktree checked out on the frozen branch plus byte-exact
audited-byte materialisation reproduces the audited tracked bytes and the
audited index stat cache, and the isolated `P8-00 --verify-only` run reproduces
the frozen stdout
`8bc1af6294db8b70b92792362226cb56666f6affaffa3ffd657ce7caba503562` twice (the
`frozen:no-new-prior-residue` check passes; the exact mechanism is recorded in
`STATE.md`). The live re-run of the three frozen Phase-8 terminal gates
nevertheless cannot be byte-identical: the frozen Phase-8 evidence embeds the
absolute worktree path (the `P8-01` sidecar records the toolchain path;
measured: 1 of the 27 frozen sidecars diverges), so `P8-12` evidence closure
cannot pass in a reconstruction. The three gates therefore remain verified by
the frozen `P9-90` in-place record, which re-ran them on the same audited
commit/tree at the audited path with byte-identical stdout. This is a recorded
limitation of the frozen Phase-8 gates, not a reconstruction failure.

The completed Phase-10 stages record the runtime composition at their own
boundary (the documented `P10-07`/`P10-08` composition advance) and downstream
gates bind earlier records by hard-coded digest, so in-place regeneration of
the committed sidecars is not byte-identical by design; the Phase-10 gate
re-runs are redirected to scratch evidence and the committed evidence root is
verified untouched.

## Claim-ledger delta

None. `P10-90` re-verifies the frozen Phase-1..Phase-9 chain and the completed
Phase-10 stages; it adds no capability and promotes no marker. The highest
demonstrated milestone remains `A` (`P10-11`).

## Public safety

The committed record contains hashes, counts and mechanism descriptions only.
No payload bytes, no toolchain binaries, no build products and no disc
material.

## Next stage

`P10-91` - final evidence index and proof matrix.
