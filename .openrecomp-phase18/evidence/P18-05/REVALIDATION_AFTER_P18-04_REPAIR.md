# P18-05 Revalidation After P18-04 Repair (controller)

## Why this revalidation was required

The committed P18-04 `gpu_command_frontier.json` was not valid JSON: the
producer appended a literal backslash-n token instead of a newline (see
`evidence/P18-04/RECOVERY_FINDINGS.md`). That artifact was repaired and its
digest changed from `297a5493...be58b` to
`a009003b...bfe9` in commit `1e07ecc`. A downstream stage may not be assumed
valid merely because it passed before, so P18-05 was re-run from the current
authority.

## Independent revalidation

Command (authoritative stage runner, dual official runs):

```
python3 .openrecomp-phase18/src/p18_stage_runner_v1.py --stage P18-05 \
  --script tools/test_phase18_dma_frontier_v1.py \
  --evidence-dir .openrecomp-phase18/evidence/P18-05 \
  --tests-json p18_05_tests.json
```

Result: `runner_status=PASS`, exit 0, empty stderr both runs, raw and
LF-normalized stdout byte-identical, all evidence artifacts byte-identical
across both runs.

## Outcome: P18-05 certification remains valid

- Every **semantic** P18-05 artifact is byte-identical to the committed
  certification: `dma_frontier.json` (digest
  `f0251b43b8d60ac8c101df71d59cd28441615e1ab58c7036dce98933450fa5c1`),
  `dma_frontier.sha256`, `dma_verdict.json`, `ordering_table_model.json`,
  `negative_tests.json`, `RESULT.json`. The DMA / ordering-table frontier
  remains `UNREACHED`; `FIRST_FRAME_READY=NO`; all
  `OPENRECOMP_PHASE18_*` claim markers `NOT_PROVEN`.
- The only changed files are the source-integrity/runner bookkeeping:
  `run1.txt`, `run2.txt`, `p18_05_tests.json`, `official_runs.json`,
  `determinism.json`. The change is exactly the integrity entry count
  (21 -> 23) because P18-06 added two `checked-in` Phase-18 source files; the
  manifest and every gate check still `PASS`.

## Why P18-04's repair cannot change P18-05 semantics

P18-05 imports the P18-04 **module** and re-derives the GP0/GP1 verdict inside
its own gate; it does not read or parse the committed P18-04 JSON artifact.
The repair changed only the artifact's byte serialization (invalid JSON -> valid
JSON) and the module's trailing-newline expression. The GP0/GP1 frontier verdict
was `UNREACHED` before and is `UNREACHED` after. Hence no P18-04 semantic
input to P18-05 changed.

## Downstream confirmation (P18-06)

P18-06 was re-run through the same authoritative runner for the same reason.
Result: `runner_status=PASS` and **every** P18-06 evidence artifact
byte-identical to its committed certification (no diff at all).
`vram_display.json` digest
`2848c231c0351638485931e8dfd064abf7ba990d7a9fab178c3730d94e084e5e`
unchanged; VRAM / display frontier `UNREACHED`; `FIRST_FRAME_READY=NO`.

## Verdict

P18-05 and P18-06 certifications remain valid against the repaired P18-04
authority. No check was weakened, no frozen history touched, and no reset was
performed.
