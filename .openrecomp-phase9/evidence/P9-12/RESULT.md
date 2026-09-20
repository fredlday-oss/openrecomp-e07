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
- the public-safety scan covered 132 committed Phase-9 evidence text files
  (its own stage directory excluded) with zero private payload leaks
  (hex/base64/ASCII) and zero absolute host path leaks.

## Evidence-hygiene adjustments

The P9-10 `build:executable` check detail recorded an absolute build path; it
now records the repository-relative path and the P9-10 official runs were
re-issued with unchanged stdout (`caa9746a...`). The safety scan now excludes
this stage's own generated sidecars so the scanned-file count (and therefore
the tests sidecar) is stable across the two official runs; the official
stdout is unchanged (`1e4981ce...`). No semantic evidence changed.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-12
--script tools/test_phase9_hardening_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-12 --tests-json p9_12_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1144 bytes (LF), sha256
`1e4981cee471ee7240d78d8bf6a039202f5285874d70607d56c7fe115726703b`.

Sidecar identities:

- `p9_12_tests.json` `5664341d963f3a3430c1e4b0fdc1e49cc8e9366b1798ac890cc8f07eb5dd76db`;
- `rebuild.json` `e569f927c0994f9d3ec48378bd8fde3de0fc4fae5628e76e2ef6a1e5b6a0a407`;
- `negatives.json` `bce7b51bff1003438c0d23de2dffc3d31b2f77744c1ffcd2040cfe006660b3d1`;
- `cache_test.json` `78c14b43eee7accfb60c03fe16fb784e47946263f96057c7d818cbc6118ace19`;
- `safety_scan.json` `9ebf7ee359743dcb5037f67cf3722301e57eb709a890740b91ac1f1444007440`;
- `official_runs.json` `659a370617a45fe5c0f2373c927074d01cc206712298020e57727a4090f7104e`;
- `determinism.json` `efb6d2edd873bf6875624cd9a969914f9548f9938d46b43cb24bea6f9f587a98`;
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
