# P10-02 result: CONTROL_WITHOUT_DELAY_SLOT reconciliation

Status: `PASS` (65 checks)

Markers:

- `OPENRECOMP_P10_02=PASS`
- `OPENRECOMP_PHASE10_STRUCTURE_V1=PASS tests=65`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_structure_v1.py`.

## Exact cause

`BREAK`/`SYSCALL` control semantics. The frozen Phase-3 decoder marks `break`
and `syscall` with `control_flow` true and `terminator` `external-trap`
because they raise a synchronous exception; they carry **no** delay slot by
architecture. The frozen Phase-8 bridge requires a delay slot for every record
with `control_flow` true, so it fails closed with
`CONTROL_WITHOUT_DELAY_SLOT` at the first such record. The cause is not
structure recovery, code ownership, translation-unit construction,
unreachable/non-code bytes, control folding or a missing reachable
instruction. No delay slot is manufactured.

## Resolution

Additive `.openrecomp-phase10/src/p10_structure_v1.py`:

- maps an `external-trap` record to the shared neutral
  `InstructionFlow.TRAP` with no successor, no delay slot, no fabricated
  fall-through and no fabricated target, after validating it against the
  Phase-10 exception classification;
- reuses the frozen Phase-8 delay-slot validation, delay-slot folding and the
  shared `ProgramModel` -> `CFG` -> `discover_functions` -> `build_call_graph`
  -> `build_translation_units` -> `classify_indirect_control_flow` layers in
  the same closed mode;
- the frozen Phase-8 module is unchanged
  (`.openrecomp-phase8` and `.openrecomp-phase9` have no diff against the
  Phase-9 terminal commit) and the frozen `P9-11` gate still passes and still
  fails closed with `CONTROL_WITHOUT_DELAY_SLOT` on the same site.

## Additivity proof

For a trap-free synthetic fixture the Phase-10 bridge produces identical
`neutral_instructions`, `folded_delay_slots`, `blocks`, `edges`, `functions`,
`translation_units`, `call_edges_internal`, `call_edges_unresolved` and
identical CFG / discovery / call-graph / units / program-model fingerprints to
the frozen Phase-8 bridge, and an identical neutral-address tuple.

## Public synthetic evidence

- trap fixture: structure completes with 5 neutral instructions, exactly two
  `TRAP`-flow instructions at the trap sites, their blocks have no successors,
  no direct target and no delay slot, and the trap metadata carries the
  `explicit-trap-terminator` classification; there are no unresolved sites;
- negatives (fail-closed, stable codes): `CONTROL_WITHOUT_DELAY_SLOT` for a
  non-trap control record without a delay slot, `TRAP_WITH_DELAY_SLOT`,
  `TARGET_INTO_DELAY_SLOT`, `TRAP_CODE_OUT_OF_RANGE` for a malformed trap
  record, and `DELAY_SLOT_IS_CONTROL` for a trap placed in a delay slot.

## New exact Hercules frontier

Structure now completes:

| Observable | Value |
|---|---|
| reachable words | 4068 |
| neutral instructions | 3433 |
| folded delay slots | 635 (328 non-NOP) |
| basic blocks | 739 |
| CFG edges | 889 |
| functions / translation units | 110 / 110 |
| internal / unresolved call edges | 209 / 22 |
| unresolved indirect control sites | 40 (18 indirect jumps, 22 indirect calls) |
| exception sites | 3 (`0x80013390` break, `0x80015f1c` and `0x80015f2c` syscall) |
| flow histogram | NORMAL 2795, BRANCH 243, CALL 209, JUMP 53, RETURN 90, INDIRECT_CALL 22, INDIRECT_JUMP 18, TRAP 3 |
| first unresolved indirect site | `0x80013e7c` `jr_indirect` (`UNRESOLVED_INDIRECT_JUMP`) |
| first site without a semantic rule | `0x80011a60` `sh` |

Remaining semantic gap: 25 op types / 304 reachable instructions without a
host-emitter rule - `addi` (2), `and` (17), `bgez` (4), `bgtz` (5), `blez`
(11), `bltz` (6), `break` (1), `jalr` (22), `lh` (12), `lhu` (6), `lwl` (17),
`lwr` (17), `mfhi` (5), `mult` (5), `sh` (31), `slt` (19), `slti` (12),
`sltiu` (8), `sltu` (23), `subu` (23), `swl` (17), `swr` (17), `syscall` (2),
`xori` (4). This is the `P10-03` frontier; it is recorded with exact sites in
`structure_reconciliation.json`.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-02
--script tools/test_phase10_structure_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-02 --tests-json p10_02_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 29048 bytes (LF), sha256
`293a47f6344861664436986f9d17671f291d7969273e0f46bb9736f6f171a84a`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `structure_reconciliation.json` `2ca89528e85f7fc635a4e506e2d4e54c863977438b252cb0f88d03e9cfd22f34`;
- `p10_02_tests.json` `d715f8d7a87894b7c35eab5dbcaeb5528ab4ecba49d6b826e6bcb49cfd86d37d`;
- `official_runs.json` `a30044af974c28fceaa8be0bd5f77dfec208ca270983a3c842e915f7bd07512e`;
- `determinism.json` `f57ca0a5461166aa68de51dcfea5c5015390924b04bec63d1edf1e78e1fba608`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed reconciliation record was leak-checked against the private
payload (no payload hex, no base64, no ASCII payload run, no string over 128
characters). Only counts, fingerprints, addresses and classification names are
recorded.

## Claim-ledger delta

`PROVEN`: the reconciliation cause and the additive exception-aware structure
mapping, including preserved fail-closed behaviour. `BOUNDED` (private only):
the new frontier record. Native execution, playability and general PS1
compatibility remain `NOT_PROVEN`.

## Next stage

`P10-03` - CPU/control frontier iteration from the new frontier.

## Re-issue note (documented, not silent)

This stage's evidence was re-issued during the `P10-05` boundary because a real
structural gap found while emitting the native Hercules program required an
explicit neutral classification: the neutral host-emitter contract allows one
flow per `(architecture, op)` pair, while the frozen frontier already
distinguishes a structural return (`jr $ra`) from an indirect jump
(`jr` through another register). The Phase-10 structure bridge now records the
latter with the distinct neutral op name `jr_indirect`, so the frozen Phase-8
rules stay untouched and the one-flow contract holds.

Consequences for this stage's evidence: the new-frontier unruled gap is 25 op
types / 304 instructions (`jr_indirect` has no frozen Phase-8 rule), the first
unresolved indirect site's op is reported as `jr_indirect`, and the structure
fingerprints in `structure_reconciliation.json` changed. The reconciliation
result itself (`CONTROL_WITHOUT_DELAY_SLOT` resolved, additivity proof,
fail-closed negatives, frozen-module behaviour preserved) is unchanged and the
gate was re-run twice with byte-identical stdout.
