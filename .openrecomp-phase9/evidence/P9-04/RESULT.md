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

All 39 neutral instructions (46 reachable words with 7 folded delay slots) are
covered exactly once with matching flow:

`addiu` 14, `andi` 1, `beq` 1, `bne` 1, `jal` 2, `jr` 3, `lui` 6, `lw` 3,
`sb` 3, `sw` 5. No uncovered sites, no flow mismatches.

The public structure emits deterministically through the frozen host emitter:
3 functions, fingerprint
`78d099ed698e99bb3d1af29e0ed5ed6b2807280a79064996e9fd5921b14c84f1`,
7515 bytes of generated C, no original machine code or payload bytes present.

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

- `p9_04_tests.json` `18528baec1acc507d34b4209e380b3132c8bd604ccef8a67865ecd55b2e36d21`;
- `public_closure.json` `1189349e922072edba31b717a885acd6f099cc20892776072be1bf42a23b7a42`;
- `private_closure.json` `d286ed24d21294bf378162b73c2fa3503a428521eb601a0429006e0e85f19bee`;
- `official_runs.json` `1c893220ee4b2d3e8a7b87723b8596f7c4eae01a4fafab55b2e5ce2d7833a1c3`;
- `determinism.json` `0a7eb45177a61d3647ecffea7bf7b3a02527e4188267d0d4bbc811fb33bac9ab`;
- `run1.txt` = `run2.txt` `04b8704c0a2a2b58575a2b29baac133e6291eaaf44d1034e791a5d9d5398e524`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

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
