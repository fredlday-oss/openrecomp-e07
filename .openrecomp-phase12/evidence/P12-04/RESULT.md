# P12-04 — Hercules initialization frontier loop

Verdict: **PASS** (20 checks, deterministic twice).

Marker: `OPENRECOMP_P12_04=PASS`.

Initialization frontier status:
`OPENRECOMP_PHASE12_INITIALIZATION_FRONTIER=BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`.

## Implemented this stage

- `ps1.bios.A0.44` `FlushCache`: documented no-argument, void cache flush. The
  bounded runtime models a flat, immediately-coherent memory with no caches, so
  the flush has no observable architectural effect; it is recorded as a typed
  no-op with fail-closed arity handling. Public synthetic emitter and direct
  dispatcher fixtures prove identity, void return, unchanged RAM, continuation
  and arity refusal.

## Frontier movement

- Previous frontier (`0x80015b94`, A0 `0x44`) now resolves; the initialization
  path advances a further 24 block entries.
- New exact frontier:

```
site          0x80015f5c
message       unresolved indirect jump
source_value  0x000000c0        (C0 vector)
function_id   fn_80015f58
block_id      blk_80015f58
block_index   468365
terminal_op   jr_indirect
```

## Recorded blocker

The immediate post-`FlushCache` path reaches the BIOS C0 interrupt-routine
dispatcher (`fn_80015f58`) with three reachable documented entries:

| site | index | documented name |
|---|---|---|
| `0x80015f4c` | `0x02` | `SysEnqIntRP` |
| `0x80015f5c` | `0x03` | `SysDeqIntRP` |
| `0x800161e0` | `0x0a` | `ChangeClearRCnt` |

All three stay `BIOS_VECTOR_NOT_IMPLEMENTED` / `FAIL_CLOSED`. Faithful
implementation would require BIOS interrupt-delivery and callback-invocation
semantics that the bounded architecture does not model; implementing only
registration state would be a permissive partial model without evidence for
delivery. The initialization completion boundary is therefore recorded
`BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`; milestone B remains `NOT_PROVEN`.

## Reserved markers

```
OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
```

## Evidence

`blocker.json`, `p12_04_tests.json`, `RESULT.json`, `official_runs.json`,
`determinism.json`, run stdout/stderr.

## Next stage

`P12-05` — Hercules initialization proof (evaluates the P12-00 contract; the
initialization completion boundary is not reached, so the proof stays
`NOT_PROVEN`).
