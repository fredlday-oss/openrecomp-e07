# OpenRecomp Phase 12 Handoff

## Current boundary

- work branch `phase12/ps1-hercules-init-frame-v1`, based exactly on the frozen
  Phase-11 terminal commit `665d11dc9f760d0c4ea2486e186c1fe5c762647c`;
- `P12-00`..`P12-40`, `P12-90`, `P12-91` all `PASS` with two-run deterministic
  evidence; next stage `P12-99` (final bounded verdict);
- reserved claim markers remain `NOT_PROVEN`:
  `OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF`,
  `OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF`,
  `OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF`,
  `OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY`.

## Exact next action

Run `tools/test_phase12_final_verdict_v1.py` twice through the Phase-12 stage
runner, record the bounded terminal verdict, update STATE/HANDOFF, regenerate
`SOURCE_SHA256SUMS.txt`, and commit `P12-99`.

## Proven Phase-12 results

- `OPENRECOMP_PHASE12_B0_5B_CHANGECLEARPAD_V1=PASS`;
- `OPENRECOMP_PHASE12_B0_TABLE_INDIRECT_V1=PASS`;
- `OPENRECOMP_PHASE12_END_TO_END_REPLAY_V1=PASS`;
- GPU/OT/DMA, texture/VRAM, GTE/geometry, initialization and frame markers are
  `NOT_PROVEN`.

## Exact unresolved blocker

`BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` at the BIOS C0 interrupt-routine
dispatcher `0x80015f5c` (`fn_80015f58`, block 468365). The initialization path
requires C0 `0x02` `SysEnqIntRP`, C0 `0x03` `SysDeqIntRP` and C0 `0x0a`
`ChangeClearRCnt`, whose faithful semantics require interrupt delivery and
callback invocation ordering that the bounded architecture does not model and
must not guess. They therefore stay fail-closed.

## Verification commands

```
python .openrecomp-phase12/src/p12_stage_runner_v1.py \
  --stage P12-90 --script tools/test_phase12_whole_regression_v1.py \
  --evidence-dir .openrecomp-phase12/evidence/P12-90 \
  --tests-json p12_90_tests.json
python .openrecomp-phase12/src/p12_stage_runner_v1.py \
  --stage P12-91 --script tools/test_phase12_evidence_closure_v1.py \
  --evidence-dir .openrecomp-phase12/evidence/P12-91 \
  --tests-json p12_91_tests.json
python .openrecomp-phase12/src/p12_stage_runner_v1.py \
  --stage P12-99 --script tools/test_phase12_final_verdict_v1.py \
  --evidence-dir .openrecomp-phase12/evidence/P12-99 \
  --tests-json p12_99_tests.json
```

## Notes

- `THIRD_PARTY_CODE_IMPORTED=NO`;
- the frozen Phase-11/Phase-10 trees and the read-only reconnaissance are
  untouched;
- no private fixture or BIOS bytes are committed.
