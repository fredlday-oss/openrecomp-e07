# OPENRECOMP Phase 1 — P1-91 Evidence

Stage: `P1-91` — Phase-1 evidence index + limitations report

Revision: working tree at HEAD `bd5f02f` (no commit created).

## Scope delivered

- `.openrecomp-phase1/evidence/INDEX.md`: the Phase-1 evidence index and
  consolidated limitations report, containing:
  - the full stage ledger (P1-00..P1-99) with verdicts and `RESULT.md` paths;
  - the executable gate markers grouped by shared/core, Game Boy/GBC, Master
    System, NES, and the established MIPS32/RV32I/safety/release gates;
  - the reproducible verification commands and the authoritative P1-90 harness
    result (44 PASS / 0 FAIL / 2 SKIPPED, identical output hash across two runs);
  - the consolidated limitations report and the exact final-verdict procedure.

No source or test files were changed by this stage; it is documentation-only.

## Files changed (this stage)

Added:
- `.openrecomp-phase1/evidence/INDEX.md`
- `.openrecomp-phase1/evidence/P1-91/RESULT.md` (this file)

## Verification

```text
python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

(Authoritative P1-90 run; no gate semantics changed in P1-91. The index does not
touch `SOURCE_SHA256SUMS.txt` because it adds no `tools/*.py`, `adapters/*.py`,
`contracts/*.json` or `schemas/*.json` file.)

## Verdict

`PASS`
