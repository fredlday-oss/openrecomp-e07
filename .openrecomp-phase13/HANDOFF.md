# OpenRecomp Phase 13 Handoff

## Current boundary

- work branch `phase13/ps1-hercules-c0-init-v1`, based exactly on the frozen
  Phase-12 terminal commit `7d76f242db2e9233ad9e023d0c63a6984fb118a0`;
- `P13-00`..`P13-06`, `P13-10`, `P13-11`, `P13-20`, `P13-30`, `P13-40`, `P13-50`,
  `P13-90`, `P13-91`, `P13-99` all `PASS` with two-run deterministic evidence;
  `P13-07`/`P13-08`/`P13-09` are `PASS_NOT_REQUIRED`;
- reserved claim markers remain `NOT_PROVEN`.

## Exact next action

None. Phase 13 is complete with the bounded terminal verdict
`PASS_BOUNDED_C0_AND_CALLBACK_MEDIATION`: the initialization proof remains
`NOT_PROVEN` at the exact technical frontier `0x80026ebc` (an unresolved B0
indirect call). The next work would implement the documented B0 service at that
frontier, then continue the discovered B0/BIOS service chain toward
`ChangeClearRCnt`/`Timer1`.

## Proven Phase-13 results

- `OPENRECOMP_PHASE13_SYSENQINTRP_V1=PASS`;
- `OPENRECOMP_PHASE13_SYSDEQINTRP_V1=PASS`;
- `OPENRECOMP_PHASE13_INTRP_ROUNDTRIP_V1=PASS`;
- `OPENRECOMP_PHASE13_CALLBACK_MEDIATION_V1=PASS`;
- `OPENRECOMP_PHASE13_INITIALIZATION_REPLAY_V1=PASS`;
- `OPENRECOMP_PHASE13_CHANGECLEARRCNT_V1=NOT_REQUIRED`,
  `OPENRECOMP_PHASE13_TIMER1_V1=NOT_REQUIRED`,
  `OPENRECOMP_PHASE13_INTERRUPT_MMIO_V1=NOT_REQUIRED`.

## Exact unresolved blocker

`BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` at the B0 vector indirect call
`0x80026ebc` (`fn_80026ea8`, block 468385). The live initialization path reaches
this call after the C0 queue, pad and memory-card services; its documented
service semantics have not yet been derived and implemented. The inherited
Phase-12 initialization contract is unmet (`INIT-BOUNDARY` false,
`INIT-NO-FAIL-CLOSED` false with `trace_failure_count=9`).

## Verification commands

```
python .openrecomp-phase13/src/p13_stage_runner_v1.py \
  --stage P13-01 --script tools/test_phase13_queue_v1.py \
  --evidence-dir .openrecomp-phase13/evidence/P13-01 --tests-json p13_01_tests.json
python .openrecomp-phase13/src/p13_stage_runner_v1.py \
  --stage P13-06 --script tools/test_phase13_frontier_v1.py \
  --evidence-dir .openrecomp-phase13/evidence/P13-06 --tests-json p13_06_tests.json
python .openrecomp-phase13/src/p13_stage_runner_v1.py \
  --stage P13-90 --script tools/test_phase13_whole_regression_v1.py \
  --evidence-dir .openrecomp-phase13/evidence/P13-90 --tests-json p13_90_tests.json
python .openrecomp-phase13/src/p13_stage_runner_v1.py \
  --stage P13-99 --script tools/test_phase13_final_verdict_v1.py \
  --evidence-dir .openrecomp-phase13/evidence/P13-99 --tests-json p13_99_tests.json
```

## Notes

- `THIRD_PARTY_CODE_IMPORTED=NO`;
- the frozen Phase-11/Phase-12 trees and both read-only reconnaissance
  directories are untouched;
- no private fixture or BIOS bytes are committed.
