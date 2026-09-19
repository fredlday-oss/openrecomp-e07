# P6-91 Evidence Index and Compatibility Matrix - Result

Verdict: `PASS` (complete deterministic evidence index and separated claim
ledger; terminal marker still reserved)

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-90 boundary commit
  `1f1f015aef61fc560f7ad3cd10739e94dd74b27a`, tree
  `99c8644f61eff91c1cc545c1e8a641a49a167337`, descending from the Phase-5
  frozen boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7` (tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Produce a complete PROVEN / BOUNDED / UNPROVEN / UNSUPPORTED / NOT TESTED
ledger. Separate the public NROM proof, the public MMC1 proof, the private
TMNT observations and general NES compatibility. Record every remaining
limitation.

## Changes (additive)

- `.openrecomp-phase6/src/p6_evidence_index_v1.py`: new evidence index and
  claim-ledger module (metadata/hashes/counts/addresses/classifications only).
- `tools/test_phase6_evidence_index_v1.py`: new P6-91 gate verifying the index
  against an independent filesystem walk, the claim ledger vocabulary and
  separation, frozen cross-stage anchors, every Phase-6 stage record PASS, and
  the private compatibility observation hygiene.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`: adds the two new identities.
- `.openrecomp-phase6/STATE.md`, `STAGE_QUEUE.md`, `HANDOFF.md`: stage
  bookkeeping.
- No frozen Phase-1..5 or earlier Phase-6 file was modified.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-91
  --script tools/test_phase6_evidence_index_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-91 --tests-json p6_91_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 4042 bytes raw, raw sha256
    `dd143bff72028e9ead5d78be2cae7e92f491e58148e3b7bb27956323e95bc063`,
    LF sha256
    `1963f454cb293bb80263899318a96ff4e55d56240e79536239cba9bedd50c9e1`.
  - `p6_91_tests.json` sha256
    `e72f78f811fb27b73b871044aa023aab8ad783f7dc95b55139b9abd87e8d10e0`,
    `tests=93`; both runs produced the same tests-json hash.
- Markers: `OPENRECOMP_P6_91=PASS`,
  `OPENRECOMP_PHASE6_EVIDENCE_INDEX_V1=PASS tests=93`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Evidence index

- 181 evidence files indexed across `P6-00` .. `P6-13` and `P6-90`, each with
  path, size, sha256 and tracked status; the index matches an independent
  filesystem walk exactly and every hash re-verified.
- Control-plane hashes (7 control files + the Phase-6 source manifest) and the
  Phase-6 manifest entries verified.
- Frozen boundaries recorded: Phase-5 tag object/commit/tree, Phase-4/3/2/1
  boundaries, the public NROM fixture sha256 `272c94cd...`, the public MMC1
  proof fixture sha256 `9e10dce5...`, host program `6c1ccac5...`, support
  `c15980d4...`, executable `0ba034bd...`, private image sha256 `2a9345e6...`
  / 262160 bytes.
- Every Phase-6 stage record `p6_XX_tests.json` verified PASS with no failure.
- Index file sha256 `42ba4d2d...`; claim record sha256 `000a4db9...`;
  regressions sha256 `67718e8b...`.

## Claim ledger (separated areas)

1. Phase-5 public NROM result: `PROVEN` - 7 proven + 4 bounded claims,
   anchored to the frozen P5-91 claim record sha256 `ef926dac...` and the
   P5-99 terminal record `b0e8267c...` with stdout capture `bc1f1e97...`.
2. Phase-6 public MMC1 result: `PROVEN` - 11 proven + 5 bounded claims
   covering the subset, fixtures, serial protocol, PRG/CHR banking, mirroring,
   variant boundary, static recompilation, native execution, independent
   reference equivalence, zero-delta platform decision, the reusable workflow
   and the whole regression.
3. Private TMNT compatibility observation: `UNPROVEN` - 4 observations
   (ingestion SUPPORTED_MMC1, candidate frontier 1250/2711 with stop at
   `0xC570`, three `jmp ($E2)` sites, translation/execution not reached) and
   the exact remaining blockers:
   - `unsupported_opcode`: documented walk fails closed at `0xC570`
     (undocumented `0x7C`, after `jsr` at `0xC56D`);
   - `unresolved_indirect_control_flow`: `jmp ($E2)` at `0x86E8`, `0x8956`,
     `0x8F3C` - targets never guessed;
   - `bank_state_unresolved`: 1048 candidate instructions in the
     mapper-switched `$8000-$BFFF` window under the power-on bank only;
   - `platform_runtime_not_tested`: cannot be assessed until translation
     completes.
   `public_claim = none`; TMNT playability remains not reached.
4. General NES compatibility: `UNPROVEN` (`OPENRECOMP_PHASE6_GENERAL_NES_
   COMPATIBILITY=NOT_PROVEN`, never promoted) - 8 unproven areas, 9
   unsupported areas (non-supported mappers, MMC1 revisions, CHR-RAM,
   PRG-RAM/battery, SUROM/SOROM/SXROM, four-screen/VS/PlayChoice,
   non-power-of-two banks, NES 2.0 extended sizes, FDS/UNIF/UNF) and 8 not
   tested areas (PAL/Dendy, hardware IRQ, CHR-RAM writes, sprite-0/overflow,
   second controller, OAM decay/DMC conflicts, MMC1 clones, extended platform
   requirements).

## Limitations recorded

- Phase-6 is bounded to the original Apache-2.0 MMC1 fixture and
  `MMC1_SUBSET_V1`; not a general MMC1 or NES result.
- Private TMNT is not playable; the four blockers above remain exact.
- No MMC1 board variant beyond V-001 is supported or inferred.
- The workflow translates only a contiguous documented fixed-bank region with
  the declared `$02FF` exit thunk.
- Timing is a documented base-cost model, not cycle accuracy; graphics/audio
  observables are bounded state views, not rendered media.
- The Phase-1 host gate set retains two `SKIPPED_TOOLCHAIN_UNAVAILABLE` checks
  (external POSIX/gcc toolchains).

## Cross-stage anchors

Frozen anchors verified unchanged: P5-91 claim record, P5-99 record, P6-10
private pipeline, P6-12 workflow evidence, P6-13 private workflow and frontier
records, P6-90 whole-regression record. The P6-13 regression re-ran as part of
the gate: `OPENRECOMP_P6_13=PASS` with empty stderr.

## Negative / fail-closed coverage

Index completeness (indexed set equals the filesystem walk), hash tie-out,
control-plane and manifest verification, stage-record PASS, ledger vocabulary,
section separation, private blocker exactness and evidence hygiene (no private
ROM bytes or banks in any P6-91 evidence file). A mismatch in any of these
fails closed.

## Claim ledger deltas

- No capability change: this stage indexes and classifies previously audited
  evidence. Terminal marker remains
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`; general compatibility
  remains `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Repository side effects

- Tracked additive changes: new index module, new gate, manifest entries,
  updated control plane, P6-91 evidence. Scratch artifacts remain ignored; no
  ROM copy exists.

## Evidence index

`RESULT.md`, `p6_91_tests.json`, `official_runs.json`, `determinism.json`,
`evidence_index.json`, `claim_record.json`, `regressions.json`, `run1.txt`,
`run2.txt`, `run1.err.txt`, `run2.err.txt`, `changed_files.txt`.

## Next stage

P6-99 - Final Phase-6 verdict.
