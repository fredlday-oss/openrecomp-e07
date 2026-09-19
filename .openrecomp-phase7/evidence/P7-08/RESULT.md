# P7-08 Translation Frontier Integration - Result

Verdict: `PASS`

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-07 boundary commit,
  descending from the frozen Phase-6 terminal commit
  `1643817d43196c43155805249137e4b4e4a21eb1`.

## Objective (frozen queue)

Integrate proven P7-02..P7-07 results into the static recompilation pipeline,
recompute the reachable/dead/unsupported frontier, emit host code only for
proven executable paths, and keep unknown control flow fail closed.

## Integration result (public indirect-flow fixture)

`.openrecomp-phase7/src/p7_frontier_integration_v1.py`:

- bank-aware reachability (P7-04) fixes 50 proven physical-bank identities;
- indirect evidence (P7-06) resolves the exact site (`$8013` -> `$8033`) and
  the finite site (`$8025`, assignment `$8110`) and keeps `$8030`
  `UNRESOLVED`;
- path specialization follows the proven dispatch targets, decodes the
  dynamically reached target code as proven identities and stops at the
  unresolved site (excluded from the emitted set);
- recomputed frontier: 61 proven identities across banks 1 and 3 (12 dynamic
  target nodes), 2 resolved dispatch sites, 1 fail-closed site, and the
  excluded bank identities recorded (`1:0x8030`);
- host emission through the frozen Phase-5 CPU emitter + Phase-6 MMC1
  support: 61 instructions, host program sha256
  `231a3a09924e94c7977ffaae71712ad9d48e443495c633ae2b6b96a8539b0b38`,
  support sha256
  `5ea325b2dea6eb348638e129c51e242aaaa047be83860ba38302e3963ef8b6a7`;
  the emitted program contains cases for the proven targets and no case for
  the unresolved site (runtime fail-closed).
- Native build through the shared Phase-2 pipeline:
  `EXECUTABLE_REPRODUCIBLE`, manifest reproducible, clang-cl/lld-link,
  executable sha256
  `23679fb850d427951dc4f685b5322ccc9de3c4f50df5cd18fa97f2a2b83426ab`.

## Data-region exclusion (public classification fixture)

The P7-02/P7-03 classifier returns `DATA_NOT_CODE` for the inline table base
and the bank-aware frontier over the same fixture fails closed at exactly that
address (`BLOCKED_UNDECODABLE`), so data regions are never emitted as code.

## Negative / fail-closed coverage

- An assignment target outside the proven feasible set fails closed with an
  explicit frontier entry.
- A tampered pointer table yields `IMPOSSIBLE`/`UNRESOLVED`, never fabricated
  targets.
- Runtime execution attempting the excluded unresolved site has no emitted
  case and fails closed (`pc outside the emitted image`).

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-08
  --script tools/test_phase7_frontier_integration_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-08 --tests-json p7_08_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 1610 bytes raw, raw sha256
    `b32eb763404e2097e2fa940519ce69cb5c8350830f177c98f8df6b2fb4ed8664`,
    LF sha256
    `d12eaf4cbe931a2d1288f6f2529b3da4c64b91015092d3e6b135d43ac776cb3b`.
  - `p7_08_tests.json` sha256
    `30bde79aa0653229647557da1a0ee474a4b9459b39650314ea001aa4eaaac0d0`,
    `tests=28`.
- Markers: `OPENRECOMP_P7_08=PASS`,
  `OPENRECOMP_PHASE7_TRANSLATION_INTEGRATION_V1=PASS tests=28`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_indirect_fixture_v1.py` re-run into ignored scratch
  evidence: exit 0, empty stderr, `OPENRECOMP_P7_07=PASS`.

## Changes

- Added `.openrecomp-phase7/src/p7_frontier_integration_v1.py`.
- Added `tools/test_phase7_frontier_integration_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`, `HANDOFF.md`.
- No frozen Phase-1..Phase-6 file was modified.

## Limitations

- Path specialization uses the proven bank context of the site; bank states
  that the model cannot prove remain fail closed.
- One native artifact per dispatch assignment; the unresolved path has no
  artifact by design.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `translation_frontier.json`,
  `p7_08_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-09 Native execution of the public Phase-7 fixture.
