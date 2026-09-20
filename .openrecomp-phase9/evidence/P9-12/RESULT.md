# P9-12 result: hardening and reproducibility

Status: `PASS` (27 checks)

Markers:

- `OPENRECOMP_P9_12=PASS`
- `OPENRECOMP_PHASE9_HARDENING_V1=PASS tests=27`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_hardening_v1.py`.

## Bounded workflow and reproducibility

A bounded workflow with explicit fail-closed categories
(`UNSUPPORTED_PSX_CONTAINER`, `UNSUPPORTED_MEMORY_RUNTIME`,
`UNRESOLVED_INDIRECT_CONTROL_FLOW`, `UNSUPPORTED_ISA_SEMANTIC`,
`BUILD_FAILURE`, `EXECUTION_FAILURE`) completes the public fixture end to end.
Two clean builds in fresh workspaces reproduce the P9-10 executable identity
`5c016be2f043760ef6ac1a7c37c60bbe335c271f307b8e05275f75e0ee2ceb9d` and the
exact P9-10 observable record (exit `0x00000002`, registers digest
`0x17f2292e1363f17f`, memory digest `0x28d892afac2d8496`, GPU 2 /
`0x6a326cbc723c24b1`, input 2 / `0xe35ba7548adde99a`, SPU 1 /
`0x55788edbf95cf3ea`, CD-ROM 1 / `0x0dc54fdf2d1b3c3c`, reads 1, writes 4,
denied 0, host calls 0), with byte-identical stdout and full reference
agreement.

## Negative and fail-closed coverage

| Case | Category |
|---|---|
| bad container magic | `UNSUPPORTED_PSX_CONTAINER` |
| truncated container | `UNSUPPORTED_PSX_CONTAINER` |
| unresolved indirect control flow | `UNRESOLVED_INDIRECT_CONTROL_FLOW` |
| uncovered semantics (`lwl`) | `UNSUPPORTED_ISA_SEMANTIC` |
| stack/image overlap | `UNSUPPORTED_MEMORY_RUNTIME` |
| unknown GPU command | explicit blocker (`UNKNOWN_COMMAND`, not emulated) |
| unknown SPU register | explicit blocker |
| unknown CD-ROM command | explicit blocker |
| BIOS A0 invocation | `UNIMPLEMENTED_SERVICE` |

No malformed input reaches emission, build or execution.

## Immutable-hash analysis cache

`.openrecomp-phase9/src/p9_analysis_cache_v1.py` implements the frozen
`openrecomp-phase9-analysis-cache-v1` key contract: put/get round trip, stale
key rejection (`CACHE_MISS`), corrupted-product rejection (`CACHE_CORRUPT`)
and deterministic repair. Cache key
`5391b931d9a98997912951aa9c8cbb4451b4d18c59b9ea06df5b79e44dd7daaa`; payloads
stay untracked under `.openrecomp-phase9/cache/`.

## Manifests and public safety

- the Phase-9 source manifest, the frozen Phase-8 manifest and the frozen
  Phase-3 module hashes re-verify;
- the public-safety scan covered 129 committed Phase-9 evidence text files
  with zero private payload leaks (hex/base64/ASCII) and zero absolute host
  path leaks.

## Evidence-hygiene adjustment

The P9-10 `build:executable` check detail recorded an absolute build path; it
now records the repository-relative path and the P9-10 official runs were
re-issued with unchanged stdout (`caa9746a...`). No semantic evidence changed.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-12
--script tools/test_phase9_hardening_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-12 --tests-json p9_12_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1144 bytes (LF), sha256
`1e4981cee471ee7240d78d8bf6a039202f5285874d70607d56c7fe115726703b`.

Sidecar identities:

- `p9_12_tests.json` `be894a5fdc28e41731872b09dbbde20cccf1ca900f1e81339c218030a9751a38`;
- `rebuild.json` `e569f927c0994f9d3ec48378bd8fde3de0fc4fae5628e76e2ef6a1e5b6a0a407`;
- `negatives.json` `bce7b51bff1003438c0d23de2dffc3d31b2f77744c1ffcd2040cfe006660b3d1`;
- `cache_test.json` `6c8de664977a870f6b9c18eec69d5b52d9213717f14555c0de3050a2b5b08cc9`;
- `safety_scan.json` `1b4003ea47a7102d61946d401312c7f36cd767aed2ae2c779b496d96206fc50c`;
- `official_runs.json` `aa3e822fa21021b938a9e77f167d62a7b80ec38c09ed5595209f7f0297a689bc`;
- `determinism.json` `a5d25ad06cde9e33cccd9a75d8ded7ff70719856ad79c84c93f814cb7216e090`;
- `run1.txt` = `run2.txt` `1e4981cee471ee7240d78d8bf6a039202f5285874d70607d56c7fe115726703b`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Claim-ledger delta

`BOUNDED`: the bounded path is fail-closed on malformed/unsupported inputs,
cache-correct, reproducible and public-safety clean. No new capability claim
is added; the terminal marker remains reserved.

## Next stage

`P9-90` - whole-project regression: re-run the applicable frozen Phase-1
through Phase-8 gates plus all completed Phase-9 official gates with exact
counts and deterministic evidence.
