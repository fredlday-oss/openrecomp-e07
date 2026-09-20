# P8-12 result: Phase-8 evidence closure

Status: `PASS` (130 checks)

Markers:

- `OPENRECOMP_P8_12=PASS`
- `OPENRECOMP_PHASE8_EVIDENCE_CLOSURE_V1=PASS tests=130`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_evidence_closure_v1.py`.

## Implementation delta

`none`: P8-12 adds no capability. It re-runs the frozen bounded path from
clean inputs and audits the complete evidence chain.

## Verified

- phase-8 source manifest (all entries, recomputed);
- control plane: `QUEUE_FREEZE=FROZEN`, the terminal marker still reserved
  `NOT_PROVEN`, the permanent general marker present, and every stage row
  `P8-00`..`P8-11` in the ledger;
- every stage's `RESULT.md`, `official_runs.json`, both run captures (raw
  stdout hash and byte count, empty-stderr hash) and every declared sidecar
  hash, for all twelve completed stages;
- analysis-cache correctness with a real `frontier-summary` product under the
  `openrecomp-phase8-analysis-cache-v1` key contract: hit for the same key,
  misses for a different fixture identity and a different configuration;
- clean re-run of the workflow: emission identity for all four files
  (`program.c` `3df423e0...`, `p8_image_v1.c` `d5d95845...`,
  `p8_runtime_support.c` `9b5e70f5...`, `p8_driver.c` `e918de64...`),
  native executable identity `fb98c8a6...` with
  `EXECUTABLE_REPRODUCIBLE`, observable identity (exit status, register
  digest, memory digest, transcript length/digest, reads/writes/host
  calls/denied), reference equivalence with no excluded observables, and a
  second clean run producing an identical workflow record.

## Official runs

Command `python tools/test_phase8_evidence_closure_v1.py`, exit 0, empty
stderr, both runs byte-identical: stdout 4764 bytes, raw sha256
`6e95c115159e5e1668d8afa942e99f316ee6745b6239c82c935e89595e1a4bd6`, LF
sha256 `76b4004951fe941ece1d4538ef7a81deaa156dd74888600f4219deab9564291e`.

Sidecar identities: `closure.json`
`a5c812c40c88e2bce2661be3c2b29b5cbe46b46cb4ea4eaeb16477021c68df99`,
`p8_12_tests.json`
`612be3e5c1114522c66c311d0c88f8dcc9e31d229247b0b0cdede96d7cc9e1c9`.

## Claim-ledger delta

- New evidence: the Phase-8 bounded public path and its evidence chain are
  internally consistent and reproducible from clean inputs with zero
  implementation delta.
- The terminal marker remains reserved `NOT_PROVEN` until P8-90, P8-91 and
  P8-99 pass.

## Next stage

P8-90: the expensive whole-project regression -- frozen Phase-1..Phase-7
behaviour plus all Phase-8 official gates.
