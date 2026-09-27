# P18-00 Controller Review — Phase-18 bootstrap / authority / provenance

## Decision

ACCEPT and INTEGRATE on branch `phase18/ps1-first-frame-frontier-v1`.

## Scope

P18-00 is a bootstrap/authority stage. It establishes the Phase-18 control
plane, re-verifies the frozen Phase-17 terminal authority from live Git,
inventories imported reconnaissance as reference-only material, and re-derives
the GPUSTAT polling frontier from the committed P17-06R transcript. It promotes
**no proof marker**.

## Independent controller verification

- Official gate: `python3 tools/test_phase18_bootstrap_v1.py
  --evidence-dir .openrecomp-phase18/evidence/P18-00` -> `P18-00_CHECKS=64`,
  zero FAIL.
- Official stage runner (dual runs): `runner_status=PASS`,
  `identical_raw=true`, `identical_lf=true`, `returncode_zero_both=true`,
  `stderr_empty_both=true`, `artifacts_identical=true`.
- Fresh-root reproduction: an independent `/tmp/p18-00-fresh-*` evidence root
  run produced byte-identical stdout and byte-identical artifacts (every JSON
  document except the two runner-generated ones `diff -q` empty), confirming
  the evidence is not a function of the evidence directory.
- Authority re-derived from live Git (not from chat): tag
  `openrecomp-phase17-pass` resolves to
  `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`; that commit's tree is
  `ad3aa822e5a02905ebc25477f7b6c69d0bffa055`; HEAD descends from it.
- Phase-1..17 namespaces: no commit since the authority touches them; no
  staged/unstaged/untracked changes reported.

## Defect found and repaired fail-closed

The gate's own negative control `negative:transcript-digest-mismatch` initially
**failed**, exposing a real fail-open: `analyse()` accepted an arbitrary digest
argument and analysed the transcript regardless. This was repaired in
`p18_gpustat_frontier_analysis_v1.py` by making `analyse()` raise
`FrontierAnalysisError("TRANSCRIPT_DIGEST_MISMATCH")` unless the supplied digest
equals the recorded P17-06R transcript digest. The defect was fixed in the
module rather than relaxed in the test.

## Negative controls (all fail closed)

- wrong certified authority commit -> rejected;
- transcript digest mismatch -> rejected (after repair);
- frontier promotion attempt -> cannot set `FIRST_FRAME_READY`;
- altered GPUSTAT owner census -> detected (dominant owner changes);
- missing fixture -> rejected;
- four private-path cases -> all rejected; ordinary relative path accepted.

## Honesty boundaries

- P18-00 proves nothing about the GPU, emulation correctness, or a frame.
- The leading hypothesis (zero-returning GPUSTAT under `ZERO_FILL_RECORDED`
  blocks poll exit) is recorded as `HYPOTHESIS_NOT_YET_PROVEN`.
- `FIRST_FRAME_READY=NO`; Phase-18 claim markers all `NOT_PROVEN`.

## Frontier

Re-derived: 1587 GPUSTAT reads, every value `0x00000000`, dominant owner
`0x8001a9fc`; zero GP0 writes; zero DMA-2 window events; stop reason
`CONTINUATION_BUDGET_REACHED`.

## Next

P18-01 (GPUSTAT polling model investigation) — author its contract before
claiming completion.
