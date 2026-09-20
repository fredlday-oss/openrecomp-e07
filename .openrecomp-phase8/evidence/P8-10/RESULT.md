# P8-10 result: reusable real-MIPS32 ELF-to-native workflow

Status: `PASS` (15 checks)

Markers:

- `OPENRECOMP_P8_10=PASS`
- `OPENRECOMP_PHASE8_WORKFLOW_V1=PASS tests=15`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_workflow_v1.py`.

## Workflow

New module `.openrecomp-phase8/src/p8_workflow_v1.py` runs the deterministic
bounded path

```
ELF -> classification -> analysis -> structure -> memory contract
    -> host emission -> native build -> execution -> reference equivalence
```

and returns a structured, deterministic result record (outcome, category,
stage, fixture identity, frontier, structure, contract digest, emission
document, build identity, native record, reference record, equivalence).
Unsupported cases fail closed with exactly one explicit category from:
`UNSUPPORTED_ELF_CONTAINER`, `UNSUPPORTED_ISA_SEMANTIC`,
`UNSUPPORTED_ABI_REQUIREMENT`, `UNRESOLVED_INDIRECT_CONTROL_FLOW`,
`UNSUPPORTED_MEMORY_RUNTIME`, `TOOLCHAIN_UNAVAILABLE`, `BUILD_FAILURE`,
`EXECUTION_FAILURE`, `REFERENCE_UNAVAILABLE`, `REFERENCE_MISMATCH`,
`INPUT_UNREADABLE`. No target is guessed, no data is treated as code, and no
compatibility is widened silently.

## Frozen fixture run

The frozen ELF completes the whole workflow: emission fingerprint
`3df423e0...`, clean build `EXECUTABLE_REPRODUCIBLE`, native
`exit_status=0x00000000`, reference equivalence with no excluded observables
and no mismatches. The workflow's reference observables equal the committed
P8-09 record, and a second identical run produces an identical result record.

## Fail-closed coverage

| Case | Category |
|---|---|
| not an ELF | `UNSUPPORTED_ELF_CONTAINER` |
| truncated image | `UNSUPPORTED_ELF_CONTAINER` |
| `ET_DYN` (dynamic executable type) | `UNSUPPORTED_ELF_CONTAINER` |
| reachable `divu` substituted for `movz` | `UNSUPPORTED_ISA_SEMANTIC` |
| reachable `jr $ra` rewritten to `jr $t9` | `UNRESOLVED_INDIRECT_CONTROL_FLOW` |
| missing native toolchain | `TOOLCHAIN_UNAVAILABLE` |
| declared expected observable mismatch | `REFERENCE_MISMATCH` |

## Official runs

Command `python tools/test_phase8_workflow_v1.py`, exit 0, empty stderr, both
runs byte-identical: stdout 627 bytes, raw sha256
`7449ea88014e34901818f6f34648e033213e9aeed9d6e554f93ff78a30c247ad`, LF
sha256 `3e07fcbc9af5dccf4dbf9084d560426006f5517c9f08662c8584bccdc3e6a6e7`.

Sidecar identities: `workflow.json`
`128ce6c8a2aca70dca6292efcfd568b0a340c718b515c58a7690370621783333`,
`p8_10_tests.json`
`6db389ee858a9c8b538be74d23c43f02f94b905ba430cc02f000f71707378220`.

## Claim-ledger delta

- New evidence: the proven bounded path is a reusable deterministic workflow
  with explicit fail-closed categories, exercised on the frozen fixture and
  on seven malformed/unsupported inputs.
- The terminal marker remains reserved `NOT_PROVEN`.

## Limitations

- The workflow's supported input class remains the bounded freestanding
  MIPS32/O32 profile the fixture demonstrates; other classes fail closed.
- `BUILD_FAILURE`, `EXECUTION_FAILURE`, `UNSUPPORTED_ABI_REQUIREMENT`,
  `UNSUPPORTED_MEMORY_RUNTIME` and `REFERENCE_UNAVAILABLE` are defined but not
  forced by this stage's vectors (P8-11 hardening covers more negatives).

## Next stage

P8-11: focused fail-closed hardening -- deterministic rejection, no guessed
recovery, no silent widening, no stale-cache acceptance and no execution
after a classification failure.
