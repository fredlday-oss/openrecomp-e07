# P8-91 result: evidence index and proof matrix

Status: `PASS` (27 checks)

Markers:

- `OPENRECOMP_P8_91=PASS`
- `OPENRECOMP_PHASE8_EVIDENCE_INDEX_V1=PASS tests=27`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_evidence_index_v1.py`.

## Evidence index

`evidence_index.json` indexes every committed Phase-8 evidence file for
stages `P8-00`..`P8-12` and `P8-90` (stage, path, size, SHA-256, tracked
status); the index excludes its own stage's generated sidecars. Every stage
carries its `RESULT.md` and machine-readable records.

## Claim ledger

`claim_ledger.json` separates:

**PROVEN** -- the exact bounded public real-ELF end-to-end native path: for
the frozen tiny-AES-c AES-128-ECB fixture (`0a90f477...`) the existing
ingestion/decode/semantics, shared neutral structure with delay-slot folding,
architecture-neutral host emission, generic runtime ABI boundary, reproducible
native build, deterministic execution and full observable equivalence against
an independently structured MIPS32 reference, with no excluded observables.

**BOUNDED/PASS** -- the specific behaviours actually exercised: the 22-op
reachable ISA set; 23 folded delay slots (16 non-nop) with link-register
materialization; the flat image/permission/stack/bounded-access/single-output-
service/return-boundary runtime contract; the bounded observable record; the
reusable fail-closed workflow and its negative coverage.

**NOT_PROVEN** -- general MIPS32 compatibility (the permanent marker),
arbitrary MIPS32 ELF compatibility, complete ISA support (division/HI-LO,
halfword and partial-word memory, branch-likely, coprocessors, floating
point, traps, privileged execution), complete o32 ABI support, arbitrary
Linux binaries/dynamic linking/kernel emulation, exceptions, arbitrary
indirect-control-flow recovery, PS1/PS2/game/commercial compatibility, cycle
accuracy and cross-platform claims.

**UNSUPPORTED / NOT TESTED** -- unsupported ELF containers, unsupported
encodings with no rule, non-return indirect control flow without evidence,
non-stack/non-image/GP-relative memory access and stale cache states, all of
which fail closed.

## Public-safety verification

No Phase-8 committed material (control plane, evidence, sources, runtime and
fixture files) contains the private Phase-7 fixture identity, a private path
marker or a ROM/native-binary suffix; the upstream source tree remains
untracked and ignored. The only embedded bytes are the public fixture's
initialized image required by its redistribution licence.

## Official runs

Command `python tools/test_phase8_evidence_index_v1.py`, exit 0, empty
stderr, both runs byte-identical: stdout 916 bytes, raw sha256
`4e7b72ed840c8622923518cf28cf5389fd25ba87c0bb6ea1a213b94a2f8c2bf2`, LF
sha256 `542fa9cc187e6bf2e4163053384d395a3f29bb9c5a229b050b5ae874a164ec7f`.

Sidecar identities: `evidence_index.json`
`a084579e2c947f0d46ba3caf67dcee1483173f76d2af2c0b7abcc01bd63ac35b`,
`claim_ledger.json`
`a8eee1edcde541659a24269dfae4f29bfecce63966cd030ce6f024a4173ff2e3`,
`p8_91_tests.json`
`00aa4052bc9e23e55c3c10f09900c572b07696ae9e08cc3f2dd6464ac0e4ec45`.

## Claim-ledger delta

- New evidence: the complete Phase-8 evidence index and the explicit
  PROVEN / BOUNDED / NOT_PROVEN / UNSUPPORTED ledger, with public-safety
  verification.
- The terminal marker remains reserved `NOT_PROVEN` for the P8-99 audit.

## Next stage

P8-99: audit every Phase-8 stage and issue the final bounded verdict.
