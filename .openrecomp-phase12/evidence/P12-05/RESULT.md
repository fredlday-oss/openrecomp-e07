# P12-05 — Hercules initialization proof

Verdict: **PASS** (12 checks, deterministic twice).

Stage marker: `OPENRECOMP_P12_05=PASS`.

Target marker: `OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`.

## Contract evaluation (P12-00)

Two fresh deterministic executions of the final-tree private initialization
path were run. Predicates:

| Predicate | Result |
|---|---|
| `INIT-PREDECESSOR` | PASS (P12-00..P12-04 present) |
| `INIT-B0-PATCH` | PASS (GetB0Table -> entry `0x5B`, derived pointers `0x1f001884`/`0x1f001894`, eleven-word clear) |
| `INIT-BOUNDARY` | **FAIL** (not reached) |
| `INIT-NO-FAIL-CLOSED` | **FAIL** (fail-closed events remain) |
| `INIT-DETERMINISTIC` | PASS (byte-identical two-run stdout) |
| `INIT-NO-FABRICATION` | PASS (no BIOS image, no fabricated code, no fail-open fallback) |

Because `INIT-BOUNDARY` is not reached, the initialization contract is not
satisfied and the proof marker remains `NOT_PROVEN`.

## Exact current frontier

```
site          0x80015f5c
message       unresolved indirect jump
source_value  0x000000c0        (C0 vector)
function_id   fn_80015f58
block_id      blk_80015f58
block_index   468365
```

Blocker: `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` — BIOS interrupt-routine
management (C0:0x02/0x03, C0:0x0a) requires interrupt-delivery semantics that
the bounded architecture does not model and must not guess.

## Reserved markers

```
OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
```

## Evidence

`initialization_proof.json`, `p12_05_tests.json`, `RESULT.json`,
`official_runs.json`, `determinism.json`, run stdout/stderr.

## Next stage

`P12-06` — GPU DMA / DrawOTag / OT promotion assessment.
