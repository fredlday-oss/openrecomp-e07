# P8-09 result: independent reference equivalence

Status: `PASS` (24 checks)

Markers:

- `OPENRECOMP_P8_09=PASS`
- `OPENRECOMP_PHASE8_REFERENCE_EQUIVALENCE_V1=PASS tests=24`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_reference_equivalence_v1.py`.

## Independently structured reference

New module `.openrecomp-phase8/src/p8_reference_mips32_v1.py` (SHA-256
`86314e6bf5d05cdf07b249a6c634e83a5c6b47b960ca0cae1c993622ae344ead`):

- its own minimal ELF32 little-endian loader (`PT_LOAD` only, own bounds,
  overlap and permission checks);
- its own decoder and interpreter for the reachable architectural semantics,
  including true delay-slot execution, the `jal` link register
  (`$ra = pc + 8`), sign-extending `lb` and `movz` per the MIPS32 definition;
- its own implementation of the bounded P8-05 memory/runtime contract
  (region permissions, write-only output window, counter semantics).

The gate verifies the module has no recompilation imports (`openrecomp.*`,
`p3_elf_image_v1`, `p3_code_frontier_v1`, `p8_structure_v1`,
`p8_mips32_semantics_v1`, `p8_emission_v1`, `host_emitter`), so this is not a
self-comparison.

## Equivalence result (no excluded observables)

The reference executed the frozen ELF from `0x2490` for 4572 retired
instructions and reached the host return boundary. Every required field is
exactly equal between the native record and the reference:

| Observable | Native | Reference |
|---|---|---|
| exit status | `0x00000000` | `0x00000000` |
| 32 boundary registers | exact per-register equality | exact per-register equality |
| register digest | `0x7ee0f4a187050726` | `0x7ee0f4a187050726` |
| memory digest | `0x231c4a49e79c5e56` | `0x231c4a49e79c5e56` |
| transcript length | 33 | 33 |
| transcript digest | `0xca6dcb87f8ac9814` | `0xca6dcb87f8ac9814` |
| memory reads | 1136 | 1136 |
| memory writes | 681 | 681 |
| host calls | 33 | 33 |
| denied accesses | 0 | 0 |

The reference transcript text is `69c4e0d86a7b0430d8cdb78070b4c55a\n`, the
FIPS-197 AES-128 known-answer line. `excluded_observables` is empty: there is
no intentional difference and no unexplained semantic delta. All values also
match the committed P8-08 evidence record, so neither side drifted.

## Official runs

Command `python tools/test_phase8_reference_equivalence_v1.py`, exit 0, empty
stderr, both runs byte-identical: stdout 955 bytes, raw sha256
`0526f26cf99555e8c208eda38606c2d0090c6708915a6b94415265b57cac6d56`, LF
sha256 `a4d5b190544c6e5ffb77de3f87403e634b5e1068c59a7884789f55015fff6c6c`.

Sidecar identities: `reference_equivalence.json`
`d611c344968c129ac052bb9b67a8d8430221d1d52bb9c0c5644c56421f0c95a1`,
`p8_09_tests.json`
`c29c2e854faf77465c3cc07263a701a0004ee8aa2eb5fc6a78e3c681dfef0fc0`.

## Claim-ledger delta

- New evidence: for the exact audited bounded fixture and observable record,
  the generated native host program and an independently structured MIPS32
  reference agree completely, with no excluded observable.
- The terminal Phase-8 marker remains reserved `NOT_PROVEN` until the
  remaining frozen stages (P8-10..P8-12, P8-90, P8-91, P8-99) pass.

## Limitations

- Equivalence is proven for this exact fixture, contract and observable
  record; it is not a general MIPS32 equivalence claim.
- The reference is bounded to the reachable op set of the fixture; other
  MIPS32 instructions fail closed.

## Next stage

P8-10: create the deterministic reusable real-MIPS32 ELF-to-native workflow
with explicit fail-closed categories.
