# OpenRecomp Phase 15 Handoff

## Current boundary

- work branch `phase15/ps1-hercules-init-mmio-v1`, based exactly on the frozen
  Phase-14 terminal commit `830be0f7be998061e8d442134cfae511d5dd8c62`;
- recovered Phase-15 Python sources pass syntax/import validation and the C
  interrupt-MMIO fragment compiles in its focused harness;
- `P15-00` and `P15-01` pass their official deterministic two-run gates;
- current stage is `P15-02` (live `I_STAT`/`I_MASK` production semantics).

## Exact next action

Complete the `P15-02` production-integration gate, then immediately run the
real Hercules frontier probe and record the first execution-reached blocker for
`P15-03`.

## Verification commands

```
python .openrecomp-phase15/src/p15_stage_runner_v1.py \
  --stage P15-01 --script tools/test_phase15_interrupt_mmio_v1.py \
  --evidence-dir .openrecomp-phase15/evidence/P15-01 --tests-json p15_01_tests.json
```

## Notes

- `THIRD_PARTY_CODE_IMPORTED=NO`;
- the frozen Phase-14 tree and all read-only reconnaissance directories are
  untouched;
- the frozen repository-root source manifest has one inherited missing entry,
  disclosed in `P15-00/baseline.json`; the authoritative Phase-14 manifest
  passes;
- no private fixture or BIOS bytes are committed.
