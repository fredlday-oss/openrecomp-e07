# P8-11 result: fail-closed hardening

Status: `PASS` (47 checks)

Markers:

- `OPENRECOMP_P8_11=PASS`
- `OPENRECOMP_PHASE8_HARDENING_V1=PASS tests=47`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_hardening_v1.py`.

## Deterministic rejection with no guessed recovery

Eight focused malformed/unsupported inputs are rejected twice with identical
result records; each rejection stops before emission, build or execution and
leaves no generated executable:

| Case | Category |
|---|---|
| `EI_DATA=2` (big-endian) | `UNSUPPORTED_ELF_CONTAINER` |
| `EI_CLASS=2` (ELF64) | `UNSUPPORTED_ELF_CONTAINER` |
| `ET_REL` object file | `UNSUPPORTED_ELF_CONTAINER` |
| entry address `0` (not executable) | `UNSUPPORTED_ELF_CONTAINER` |
| reachable `divu` substituted for `movz` | `UNSUPPORTED_ISA_SEMANTIC` |
| reachable `lh` substituted for `movz` | `UNSUPPORTED_ISA_SEMANTIC` |
| reachable `jalr` (no delay-slot ownership evidence) | `UNSUPPORTED_ISA_SEMANTIC` |
| reachable `jr $t9` (no target evidence) | `UNRESOLVED_INDIRECT_CONTROL_FLOW` |

## No silent compatibility widening

The closed rule table still contains exactly the 22 reachable fixture ops;
`div`, `divu`, `mult`, `multu`, `mul`, `movn`, `jalr`, `swl`, `swr`, `lwl`,
`lwr`, `lh`, `lhu`, `sh`, `beql` and `bnel` have no rule and cannot be emitted.

## No stale-cache acceptance

New module `.openrecomp-phase8/src/p8_analysis_cache_v1.py` implements the
frozen `openrecomp-phase8-analysis-cache-v1` key contract with mandatory key
recomputation. Verified: a valid entry hits; an entry whose recorded key
inputs are tampered with is rejected as stale (and counted); a different
fixture identity misses; entries are product-scoped.

The content-hash incremental object cache (P8-07) was re-verified: a changed
source produces a different key and a recompile; a corrupted cached object is
detected by its recorded hash and recompiles; a warm build with unchanged
content reuses every object.

## Positive control

The frozen fixture still completes the entire workflow with reference
equivalence (no mismatches) under the hardened path.

## Official runs

Command `python tools/test_phase8_hardening_v1.py`, exit 0, empty stderr, both
runs byte-identical: stdout 1943 bytes, raw sha256
`64ffa42360c6be319ab4d3bfc76b3ce755d67cc897671800071dd128023c6375`, LF
sha256 `546256d4126e1b4300da12fdfae1a5f7b7ad5bec192682ceb2e0f618966d518c`.

Sidecar identities: `hardening.json`
`7b8aaf66cf516054d508e09e701c2c4a13ec6f03ad4614f80fe108f4f4d87af0`,
`p8_11_tests.json`
`6c74abf09875467a4bcc7479c590ea4ddacda9f0483f3a8ccd473a5bd59417ef`.

## Claim-ledger delta

- New evidence: the Phase-8 mechanisms reject malformed and unsupported
  inputs deterministically, without guessed recovery, silent widening, stale
  cache acceptance, or execution after a classification failure.
- The terminal marker remains reserved `NOT_PROVEN`.

## Limitations

- Negative coverage is focused on the Phase-8 mechanisms; it is not a general
  fuzzing or adversarial-security claim.
- The defined `BUILD_FAILURE`, `EXECUTION_FAILURE`, `REFERENCE_UNAVAILABLE`,
  `UNSUPPORTED_ABI_REQUIREMENT` and `UNSUPPORTED_MEMORY_RUNTIME` categories
  are not all force-triggered by these vectors (they remain implemented and
  fail-closed by construction).

## Next stage

P8-12: re-run the bounded public MIPS32 path from clean inputs and verify
fixture identity, cache correctness, generated-source identity, native result
identity, reference equivalence and manifest/evidence consistency.
