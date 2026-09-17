# Phase 4 Evidence Schema

Each stage writes `.openrecomp-phase4/evidence/<STAGE>/RESULT.md` plus
machine-readable sidecars.

## Required `RESULT.md` fields

- Verdict: `PASS` / `FAIL` / `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` /
  `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
- Baseline: git HEAD commit and tree, branch, baseline tag and commit
- Objective: the frozen queue required outcome for the stage
- Changes: exact files, additive vs modified, and why
- Commands and exit codes: official gate (twice), relevant regressions,
  source integrity
- Deterministic markers/hashes/traces: raw and LF-normalized sha256 for every
  stdout capture
- Independent/reference comparison where technically appropriate
- Negative / fail-closed coverage
- Relevant Phase-1 / Phase-2 / Phase-3 / Phase-4 regressions with results
- Claim ledger deltas
- Limitations and unproven areas
- Repository side effects: tracked vs untracked, working-tree delta
- Evidence index: the files in the stage evidence directory
- Next stage

## Machine-readable sidecars

- `RESULT.json` with fields
  `{stage, stage_name, status, tests, passed, failed, markers, checks, findings, failure}`
  matching the gate's own record; `checks` sorted by check label.
- `official_runs.json` recording both official gate runs
  (`returncode`, `stdout_bytes`, `stdout_sha256_raw`, `stdout_sha256_lf`,
  `stderr_empty`, markers).
- Per-topic JSON records (for example regression summaries or determinism
  records) written next to `RESULT.md`.

## Rules

1. Evidence is UTF-8 with LF endings. Captures piped from a Windows console
   are stored LF-normalized, with both raw and LF sha256 recorded; raw
   captures that must stay untracked are hash-pinned by their stage record.
2. Evidence must be deterministic: no host paths, timestamps, process
   identity, UUIDs or absolute toolchain paths.
3. Fail closed on malformed input without a Python traceback; stable
   deterministic failure classifications only.
4. Compilation success alone is not semantic equivalence. Linear disassembly
   alone is not function recovery. Indirect targets must not be guessed.
5. Every stage gate emits on stdout:
   `OPENRECOMP_P4_XX=<status>`,
   `OPENRECOMP_PHASE4_<NAME>_V1=<status> tests=N`,
   and the terminal markers in their current reserved state.
6. The official gate is run twice; byte-identical stdout with empty stderr is
   required for PASS.
7. Frozen Phase-3 gate re-runs may refresh their own deterministic evidence
   sidecars in the working tree; this is recorded as a re-run artifact and
   never as a history change.

## Claim ledger vocabulary

- `PROVEN`: supported by deterministic audited evidence on the frozen tree.
- `BOUNDED`: proven only for the exact recorded fixture, configuration and
  claim.
- `UNPROVEN`: not established by evidence.
- `UNSUPPORTED`: known to be outside the implementation or target support.
- `NOT TESTED`: no claim was attempted.

Numeric or performance results are never claims of correctness.
