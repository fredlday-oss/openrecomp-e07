# P2-90 whole Phase-2 regression and evidence audit - result

Stage: `OPENRECOMP_PHASE2_WHOLE_REGRESSION_AUDIT_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-90/`.

Verdict: **PASS**.

## Markers

```text
OPENRECOMP_P2_90=PASS
OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990
OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN
```

## Baseline

- Branch `phase2/opencode-v1`, `HEAD` `2fc27bfd80ef36b62ab3dc854562bbb4d0ce82db`
  (P2-14 boundary).
- Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
  `46c2f971e1a42cf49bd936bad94697b81bf31002`.
- Phase-1 host gates: `PASS=44 FAIL=0 SKIPPED=2` (toolchain-gated gates skipped, never
  counted as passes). Source integrity: 132 manifest entries
  (`SOURCE_SHA256SUMS.txt` sha256
  `1bf21db59bf11f4ff19d60bbe4e37afd8e4b8ca5f1391296d882c1149cc08fca`).

## Objective

Re-run every applicable completed Phase-2 gate and audit the complete evidence chain
from guest input through decode/frontend, ProgramModel, CFG, function discovery, call
graph, translation units, indirect-control-flow handling, host emission, deterministic
build, native executable, generic runtime, platform adapters, observable execution,
reference equivalence and reproducible release packaging.

## Audit gate

`tools/test_phase2_whole_regression_v1.py`
(sha256 `5832a0aaf0dd470f7bfdff093d09be371ab03fcfb66d45d2a9844a7cceb090ef`) performs:

1. control-plane audit (`STATE.md`, `HANDOFF.md`, `STAGE_QUEUE.md`: ledger, queue,
   markers, final-marker non-claim);
2. evidence audit (RESULT.md/RESULT.json presence, verdicts, feature markers, 34
   recorded identity checks, evidence-reference existence);
3. claim classification audit (18 classified claims);
4. regression matrix execution (22 gates, 1990 gate checks);
5. Phase-1 host gates and source-integrity verification;
6. asset/legal/content policy audit;
7. deterministic audit output (two consecutive runs).

No `openrecomp/*.py` implementation source, gate or existing test was modified.

## Regression matrix (22 gates, 1990 gate checks)

| gate | mode | marker | checks |
|---|---|---|---|
| P2-01 | noargs | `OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49` | 49 |
| P2-02 | noargs | `OPENRECOMP_CFG_V1=PASS tests=82` | 82 |
| P2-03 | noargs | `OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67` | 67 |
| P2-04 | noargs | `OPENRECOMP_CALL_GRAPH_V1=PASS tests=61` | 61 |
| P2-05 | noargs | `OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104` | 104 |
| P2-06 | noargs | `OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134` | 134 |
| P2-07 | noargs | `OPENRECOMP_HOST_EMITTER_V1=PASS tests=106` | 106 |
| P2-08 | noargs | `OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169` | 169 |
| P2-09 | noargs | `OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120` | 120 |
| P2-10 | noargs | `OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108` | 108 |
| P2-11 | noargs | `OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests=77` | 77 |
| P2-12 | noargs | `OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests=96` | 96 |
| P2-13 | noargs | `OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests=80` | 80 |
| P2-14 | noargs | `OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests=82` | 82 |
| P2-20 | evidence | `OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests=86` | 86 |
| P2-21 | evidence | `OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests=74` | 74 |
| P2-22 | evidence | `OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests=66` | 66 |
| P2-23 | evidence | `OPENRECOMP_NES_END_TO_END_V1=PASS tests=50` | 50 |
| P2-30 | evidence | `OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1=PASS tests=14` | 14 |
| P2-40 | evidence | `OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1=PASS tests=181` | 181 |
| P2-50 | evidence | `OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1=PASS tests=174` | 174 |
| NES platform | noargs | `OPENRECOMP_NES_PLATFORM_V1=PASS tests=10` | 10 |

Full per-gate stdout hashes and capture conventions: `regression_matrix.json`,
`regression_matrix.txt`, `regression_matrix_full.txt`.

- Recorded stdout-hash claims reproduce under the capture convention used to record
  them (utf-8 LF, utf-8 CRLF, or utf-16le-BOM CRLF); the P2-40 hash additionally
  requires reconstructing the frozen evidence-dir prefix that its stdout prints for the
  nested Phase-1 host-gates invocation.
- Seven frozen stdout captures (P2-10..P2-14, P2-20 evidence run, P2-22) reproduce
  byte-for-byte after newline normalisation, except for the documented one-line
  cross-stage guard deltas (five MIPS32 stages).
- All 34 recorded identity checks pass: fixture SHA-256, generated source SHA-256/source
  fingerprints, executable SHA-256, package archive SHA-256 and source-state
  fingerprint all match the frozen evidence and the fresh runs.
- The re-run P2-50 gate reproduces every recorded package, payload, object and
  executable byte-identically; three manifest-count-dependent files
  (`changed_files.txt`, `input_hashes.txt`, `source_integrity.txt`) differ exactly by the
  P2-90 gate registration (131 -> 132 manifest entries).

## Determinism

```text
run 1 stdout sha256: 74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7
run 2 stdout sha256: 74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7
stdout byte-identical: yes (18136 bytes)
run 1/2 stderr sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 (empty)
```

Two consecutive full audit runs, each re-executing every gate, produced byte-identical
stdout and empty stderr; captures are `p2_90_run1.txt`, `p2_90_run2.txt`,
`p2_90_run1.err`, `p2_90_run2.err`, summarised in `deterministic_runs.txt`.

## Cross-stage consistency and corrections

Full detail: `corrections_report.md`.

- **C1** stale P2-50 archive/source-state claims in `STATE.md`/`HANDOFF.md` were
  replaced with the evidence-derived values (`fa72b5d169ad...`, `1c1dac0ea994...`,
  `71847f9d7ffd...`,
  `5d93971b102b24e56b2c98bf4c6b6486f58e6c174700af1c77cf969f85024c54`). The audit now
  enforces these values and rejects the superseded tokens.
- **C2** the P2-20-session P2-14 guard replacement (`no-p2-20-evidence-directory` ->
  `no-nes6502-dependency-in-p2-14`, count unchanged at 82) is now documented in
  `STATE.md`/`HANDOFF.md`; the current P2-14 stdout hash is
  `197a6c5e5c5578ee6fced2eb45b937359bbd612dab8ec11bb4d5c2e6b717da51` and the frozen
  pre-adjustment capture `P2-14/p2_14_gate.txt` (`115c2c8a...`) is marked historical.
- **C3** the control-plane gate block source-integrity count was corrected to 132
  manifest entries.
- **C4** nine frozen evidence files in P2-00/P2-07/P2-08/P2-40/P2-50 contain absolute
  host-environment identifiers; they are enumerated in `asset_legal_audit.txt`, no new
  occurrence is permitted, and sanitization is deferred to P2-91 because they are pinned
  by hash-recorded PASS evidence.

## Source integrity and asset/legal/content policy

- `SOURCE_SHA256SUMS.txt` verified: 132 entries, audit gate registered via
  `update_sums.py`, no existing entry changed relative to the pre-P2-90 state.
- Tracked tree: no console asset suffixes, no console header magics at offset 0, no
  public-safety markers (credentials, tokens, private keys).
- Release packages: release content policy findings: none.
- Shared implementation source (`openrecomp/*.py`, `adapters/*.py`): no absolute host
  paths.
- P2-90-owned artifacts: no console magics, secrets or absolute host paths.
- Frozen evidence findings: the nine documented host-path occurrences (C4).

## Claim classification summary

Full table: `claim_classification.md` / `claim_classification.json`.

| classification | claims |
|---|---|
| `PROVEN` | architecture-neutral shared analysis pipeline; deterministic repeated execution; generic runtime neutrality |
| `BOUNDED_PROVEN` | NES/6502 frontend integration; NES runtime bridge; NES synthetic end-to-end native recompilation; observable equivalence; MIPS32 shared-path operation; reproducible native build; reproducible release package |
| `NOT_PROVEN` | arbitrary NES ROM compatibility; commercial-game compatibility; complete NES hardware compatibility; arbitrary MIPS32 binary compatibility; future architecture compatibility; Phase-2 final end-to-end proof marker |
| `OUT_OF_SCOPE` | PS1/PS2/Xbox compatibility; cycle accuracy |

No bounded proof is promoted to a general compatibility claim.

## Repository side effects

- New audit gate `tools/test_phase2_whole_regression_v1.py`; `SOURCE_SHA256SUMS.txt`
  updated (131 -> 132 entries).
- Control-plane corrections in `STATE.md`, `HANDOFF.md`, `STAGE_QUEUE.md`.
- New evidence under `.openrecomp-phase2/evidence/P2-90/` (this file, `RESULT.json`,
  `p2_90_tests.json`, `regression_matrix.{json,txt,full.txt}`, run captures,
  `stage_evidence_consistency.{json,txt}`, `claim_classification.{json,md}`,
  `asset_legal_audit.txt`, `source_integrity.txt`, `deterministic_runs.txt`,
  `changed_files.txt`, `corrections_report.md`).
- Raw per-gate captures remain in the untracked scratch area
  `.openrecomp-phase2/scratch/P2-90/regressions/` so the audited evidence tree stays
  free of host-specific capture bytes.
- No `openrecomp/*.py` implementation source, adapter, gate or prior test modified; no
  prior evidence artifact modified; no commit created.

## Limitations and non-claims

- P2-90 proves only that the completed stages still pass together and that their
  cross-stage evidence is internally consistent on the audited tree. It does not upgrade
  any bounded stage claim and does not prove arbitrary NES ROM, commercial-game,
  complete NES hardware, arbitrary MIPS32, PS1/PS2/Xbox or future-architecture
  compatibility, nor cycle accuracy.
- The audit's coverage is limited to the audited gate set, the detected host toolchain
  (`clang-cl`/`lld-link` 22.1.8) and synthetic/original fixtures.
- The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF` marker remains `NOT_PROVEN`;
  P2-90 does not claim it (reserved for P2-99).

## Next stage

`P2-91` - evidence index + limitations.
