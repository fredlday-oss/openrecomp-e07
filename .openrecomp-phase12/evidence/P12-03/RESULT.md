# P12-03 — GetB0Table indirect service mediation

Verdict: **PASS** (22 checks, deterministic twice).

Markers: `OPENRECOMP_P12_03=PASS`,
`OPENRECOMP_PHASE12_B0_TABLE_INDIRECT_V1=PASS`.

## Objective

Close the `B0:0x57` -> synthetic table -> entry `0x5B` indirect-control problem
without inventing a BIOS-resident guest address, and run the real Hercules
initialization path past the frozen Phase-11 frontier.

## Mechanism

- `B0:0x57 GetB0Table` returns a pointer to the synthetic project-owned window
  `0x1f000000` (entry stride `0x16c == 0x5b*4`).
- The synthetic entry `0x5B` resolves to the synthetic ChangeClearPAD target
  object at `0x1f001000`; the target-relative writes the caller performs are
  backed by the same window.
- Unknown table entries stay `0` and carry no pointer into BIOS or code.

## Fixture-run mediation observables (private, bounded)

- `p12_b0_table_base = 0x1f000000`, `p12_b0_entry_5b = 0x1f001000`.
- entry read at `0x1f00016c` observed.
- derived pointers stored: `0x1f001884` (`0x8002ed84`),
  `0x1f001894` (`0x8002ed88`).
- eleven-word clear at offsets `0x594`..`0x5bc` (synth `0x1f001594`..
  `0x1f0015bc`) observed; all zero.
- `ChangeClearPAD` invoked 4 times during initialization; zero service failures.
- Both reachable `B0:0x57` sites (`0x80015fa4`, `0x80026f74`) resolve to
  `ps1.bios.B0.57`.

## New exact frontier

```
site             0x80015b94
message          unresolved indirect jump
source_value     0x000000a0        (A0 vector)
function_id      fn_80015b90
block_id         blk_80015b90
block_index      468355
terminal_op      jr_indirect
```

The immediate post-patch direct call `jal 0x80015b90` reaches a two-instruction
A0 jump dispatcher (`addiu t2,zero,0xa0`; `jr t2`) whose delay-slot index
resolves to A0 `0x44` `FlushCache`, which is documented but not yet implemented,
so it stays fail-closed. Recorded for `P12-04`.

## Unknown-index / no-arbitrary-execution coverage

- A public dispatcher fixture proves unknown entries (`0x10`, `0x19`, `0x44`,
  `0x57`, table word `0x0000`) are zero while entry `0x5B` is the synthetic
  target.
- The runtime contains no guest-code interpreter and the synthetic object stays
  inside the project-owned window.

## Reserved markers

```
OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
```

## Evidence

`mediation.json`, `frontier.json`, `p12_03_tests.json`, `RESULT.json`,
`official_runs.json`, `determinism.json`, run stdout/stderr.

## Next stage

`P12-04` — Hercules initialization frontier loop.
