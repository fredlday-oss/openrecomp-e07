# P9-04 result: reachable translation-frontier closure

Status: `PASS` (31 checks)

Markers:

- `OPENRECOMP_P9_04=PASS`
- `OPENRECOMP_PHASE9_TRANSLATION_CLOSURE_V1=PASS tests=31`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_translation_v1.py`.

## Implementation

`.openrecomp-phase9/src/p9_semantics_v1.py` reuses the frozen Phase-8 closed
MIPS32 rule table and emitter configuration unchanged and adds only:

- a coverage check classifying every reachable neutral instruction exactly
  once against the table (with explicit uncovered sites and flow mismatches);
- an evidence-based classification of reachable recognized-unsupported
  MIPS32 forms into explicit categories;
- an explicit COP0/GTE reachability scan.

No new instruction semantics were added: the bounded public fixture requires
none, and any uncovered reachable form fails closed.

## Public fixture closure (exact)

All 41 neutral instructions (48 reachable words with 7 folded delay slots) are
covered exactly once with matching flow:

`addiu` 14, `andi` 1, `beq` 1, `bne` 1, `jal` 2, `jr` 3, `lui` 7, `lw` 3,
`ori` 1, `sb` 3, `sw` 5. No uncovered sites, no flow mismatches.

The public structure emits deterministically through the frozen host emitter:
3 functions, fingerprint
`7f277a526dc3b49c0436442666ea5cd6af1855f98dc201f9dd32346ea50c59be`,
generated C with no original machine code or payload bytes present.

## Fail-closed negative

An injected reachable `lwl` (recognized-unsupported, outside the frozen table)
is decodable (no frontier gap) but produces an open closure with exactly one
uncovered op `lwl`; the host emitter rejects it (`HostEmitterError`). It is
never guessed or silently skipped.

## Private fixture closure classification (metadata only)

The 96 reachable recognized-unsupported words are classified explicitly:

| Category | Ops | Total |
|---|---|---|
| `UNALIGNED_PARTIAL_WORD_LOAD` | `lwl` 17, `lwr` 17 | 34 |
| `UNALIGNED_PARTIAL_WORD_STORE` | `swl` 17, `swr` 17 | 34 |
| `INDIRECT_CONTROL_FLOW` | `jalr` 22 | 22 |
| `TRAP_OR_SYSTEM` | `break` 1, `syscall` 2 | 3 |
| `OVERFLOW_TRAPPING_ARITHMETIC` | `addi` 3 | 3 |

No unknown category and no reachable COP0/GTE instruction. The closure remains
open at the first blocker `0x80013390` (external trap). No payload bytes are
present in the evidence; the fixture is explicitly `is_pass_criterion: false`.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-04
--script tools/test_phase9_translation_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-04 --tests-json p9_04_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1281 bytes (LF), sha256
`04b8704c0a2a2b58575a2b29baac133e6291eaaf44d1034e791a5d9d5398e524`.

Sidecar identities:

- `p9_04_tests.json` `ce10c149ac7e3c3f37eeed292d2e5e69ada885f336e6feaafbbb73123592e16c`;
- `public_closure.json` `50fe5896919cc6b1136a4d8f9e1b5ed22687f73188c960c9be186ef06bad9141`;
- `private_closure.json` `d286ed24d21294bf378162b73c2fa3503a428521eb601a0429006e0e85f19bee`;
- `official_runs.json` `32b8973c8a044bc345e9cc122373c37002b759cd4674f673e044696eee3799ea`;
- `determinism.json` `00fe37eb9e082b95c3c8daef6233059a0e4841f44acdd432ce8e383508b37b3a`;
- `run1.txt` = `run2.txt` `04b8704c0a2a2b58575a2b29baac133e6291eaaf44d1034e791a5d9d5398e524`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Documented fixture correction (P9-10 preparation)

The public fixture was corrected to initialize `$sp` itself at entry (see the
P9-03 correction record). The covered histogram gained `lui` 7 and `ori` 1,
the covered total is 41, and the emission fingerprint is now `7f277a52...`.
The official runs were re-issued; the official stdout identity is unchanged
(`04b8704c...`).

## Claim-ledger delta

`BOUNDED`: the exact bounded public fixture's reachable translation frontier is
closed against the frozen Phase-8 semantics/emitter paths; the private
fixture's unsupported reachable forms are explicitly classified and no
COP0/GTE form is reachable. No platform service, emission set, build or
execution is claimed.

## Next stage

`P9-05` - PS1 BIOS/service boundary: discover reachable BIOS/system-service
calls, build an explicit typed/versioned service boundary, implement only
services required by the bounded fixture, and fail closed on unknown BIOS
calls.
