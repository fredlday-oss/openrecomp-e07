# P17-06R — Controller independent review

Decision: **ACCEPT and INTEGRATE**.

## Authority
- controller branch `phase17/ps1-title-overlay-recompile-v1`; pre-integration HEAD `8735bf34ba3884d19a66818d92ddd8004dc87b17`
- worker branch `agent/deepseek-phase17-p17-06r-r1`; integrated by fast-forward only
- the worker left the stage **uncommitted** (`PENDING_FINAL_COMMIT`, empty evidence directory) after two
  latent defects stopped the official gate; the controller finished and validated the stage

## Worker defects found and repaired by the controller
The official gate failed twice on two independent, pre-existing defects in the worker's code. Both were
genuine contract bugs, not environment problems, and both were fixed fail-closed:

1. **`KeyError: 'distinct_executed_pc_count'`** (`p17_side_effects_exec_v1.py::_parse_runtime_stdout`).
   `frontier_block()` and the gate both read `distinct_executed_pc_count`, but the runtime-result parser
   never produced that key. Repair: the parser now sets it explicitly, after the existing
   `DISTINCT_PC_COUNT` == `len(distinct_executed_pcs)` cross-check, so the derived value is bound to the
   count the runtime itself reported.
2. **`vocabulary:executed-op-counts-sum` FAIL (`executed=8270`, `sum=346`)** — silent evidence
   under-reporting. The harness already collected a per-step op trace (`g_ops`, cap 262144) and printed
   `TRACE_LEN`, but never printed the ops, so `executed_vocabulary()` was forced to count **distinct PCs**
   (346) while the gate correctly bound op counts to **executed instructions** (8270). This was the
   serious one: a PASS here would have published an execution-mix statistic off by a factor of 24.
   Repair, in the authenticated direction only:
   - the harness prints one `STEP <pc> <op>` line per executed instruction and records the step PC;
   - the parser consumes `STEP` lines and fail-closes on malformed lines, on
     `trace_length != parsed steps`, and on `parsed steps != executed_instruction_count`;
   - `executed_vocabulary()` now derives op and region counts from the per-step trace, with a
     `EXECUTED_PC_NOT_AUTHENTICATED` guard on every step;
   - the runtime itself now fail-closes on `EXECUTED_OP_COUNT_SUM_MISMATCH`;
   - the per-step trace is excluded from the public manifest (it is large and redundant with the
     published op counts); the derived counts are published instead.

## Independent controller verification (in the P17-06R worktree)
- official P17-06R gate rerun twice from **fresh private build roots** (run 1 default root; run 2 under
  `OPENRECOMP_P17_PRIVATE_BUILD_ROOT=.../P17-06R-controller-fresh-<ts>`): both exit 0, empty stderr,
  `P17-06R_CHECKS=119`, zero non-PASS, `OPENRECOMP_P17_06R=PASS`
- stdout **byte-identical** across the two runs; all 7 regenerated evidence files
  (`RESULT.json`, `continuation.json`, `next_stage.json`, `p17_06r_tests.json`, `stage_metadata.json`,
  `transcript.json`, `transcript.sha256`) **byte-identical** between runs and to the committed evidence
- `python3 .openrecomp-phase17/src/p17_source_manifest_v1.py` → `OPENRECOMP_PHASE17_SOURCE_INTEGRITY=PASS`
  (35 entries, regenerated after the repairs)
- `python3 .openrecomp-phase17/src/p17_frozen_phase16_integrity_v1.py` →
  `OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS` (canonical git-blob comparison)
- `git diff --check` clean; zero Phase-1..16 paths modified; historical P17-04..P17-07 `RESULT` records
  untouched
- hardcoding audit: the frontier/region addresses (`0x80026cc8`, `0x80011b08`, `0x80012e8c`,
  `0x8001a908`, `0x8001aa08`) appear only in a module docstring; the continuation entry is derived from
  the recorded P17-05R `attempted_frontier_pc`
- linkage exclusion: the Phase-16 hand-authored substitute (`TITLE_TRANSITION_CODE`, `p16_emission_v1`,
  `p16_record_title_transition`) is absent from the generated native runtime (grep count 0)

## Stage result (bounded)
- continuation entry `0x80026cc8`, derived from the recorded P17-05R frontier; the live replay
  reproduces the recorded P17-05R step count exactly (78)
- 4 newly authenticated main-EXE regions: `0x80026cc8` (+3), `0x80011b08` (+86), `0x80012e8c` (+623),
  `0x8001a908` (+627); 8340 authenticated records total (title 6995, main-EXE 1345)
- authentic frontier: `stop_reason=CONTINUATION_BUDGET_REACHED`,
  `last_successfully_executed_pc=0x8001aa08`, `attempted_frontier_pc=0x8001aa0c`, 8192 additional
  instructions past the P17-05R frontier, 8270 executed in total, 346 distinct executed PCs
- device/BIOS transcript: 1 BIOS `A0` dispatch (table index `0x2b`, owning authenticated instruction
  `0x80026ccc`, return PC `0x8004ffc4`) and 1590 device events (GPUSTAT_READ 1587, INTERRUPT_ACCESS 2,
  TIMER_ACCESS 1); sha256 `d7e222c87726748ced23dd60c2b1ba138625227c984dac587be6a5761695fd3a`
- device layer: BIOS dispatch envelope + return-to-RA only, BIOS internals `NOT_MODELED`, MMIO reads
  zero-filled and recorded, MMIO writes recorded and not applied
- semantic vocabulary: implemented 55 (45 from P17-05R plus lwl/lwr/swl/swr/div/divu/mthi/mtlo/add/sub),
  exercised 31 derived from the execution trace

## Fail-closed negatives covered by the gate
unauthenticated destination, unaligned entry, altered source word, altered header geometry and wrong
mapping base, tampered member/payload digest, missing provenance, device event without provenance,
forged device class, fake BIOS vector, tampered recorded frontier, already-authenticated entry, and a live
replay that does not reproduce the recorded frontier step count.

## Scope discipline
- no Phase-1..16 change; all `NOT_PROVEN` markers preserved
  (`HERCULES_INITIALIZATION_PROOF`, `HERCULES_FRAME_PROOF`, `HERCULES_PLAYABILITY_PROOF`,
  `GENERAL_PS1_COMPATIBILITY`), `FIRST_FRAME_READY=NO`
- private fixture bytes never committed; generated sources, private mapping, build metadata, compiled
  artifacts and the transcript stay under the configured private build root
- pre-existing and out of scope: root `SOURCE_SHA256SUMS.txt` lists
  `tools/test_build_package_reproducibility_v1.py`, which is absent at the pre-existing base commit; left
  untouched

## Remaining
- P17-07R (checked GPU/OT/framebuffer device frontier), P17-90 (regression suite), P17-91 (evidence and
  source-manifest closure), P17-99 (final Phase-17 verdict)
