# Phase 6 Evidence Schema

Each stage writes `.openrecomp-phase6/evidence/<STAGE>/RESULT.md` plus
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
- Relevant Phase-1 / Phase-2 / Phase-3 / Phase-4 / Phase-5 regressions with
  results
- Claim ledger deltas
- Limitations and unproven areas
- Repository side effects: tracked vs untracked, working-tree delta
- Evidence index: the files in the stage evidence directory
- Next stage

## Machine-readable sidecars

- The stage gate's own record `<stage>_tests.json` (for example
  `p6_00_tests.json`) with fields
  `{stage, stage_name, status, tests, passed, failed, markers, checks, findings, failure}`;
  `checks` sorted by check label.
- `official_runs.json` recording both official gate runs
  (`returncode`, `stdout_bytes`, `stdout_sha256_raw`, `stdout_sha256_lf`,
  `stderr_empty`, markers).
- Per-topic JSON records (for example mapper protocol vectors, bank-state
  records, equivalence records) written next to `RESULT.md`.

## Rules

1. Evidence is UTF-8 with LF endings. Captures piped from a Windows console
   are stored LF-normalized, with both raw and LF sha256 recorded; raw
   captures that must stay untracked are hash-pinned by their stage record.
2. Evidence must be deterministic: no host paths, timestamps, process
   identity, UUIDs or absolute toolchain paths.
3. Fail closed on malformed input without a Python traceback; stable
   deterministic failure classifications only.
4. Compilation success alone is not semantic equivalence. Linear disassembly
   alone is not function recovery. Indirect targets and board wiring must not
   be guessed.
5. Every stage gate emits on stdout:
   `OPENRECOMP_P6_XX=<status>`,
   `OPENRECOMP_PHASE6_<NAME>_V1=<status> tests=N`,
   and the terminal markers in their current reserved state.
6. The official gate is run twice; byte-identical stdout with empty stderr is
   required for PASS.
7. Evidence never contains ROM bytes (private or public) or derived binary
   copies; only hashes, metadata, counts, addresses and derived analysis.

## Frozen-gate re-run hygiene

Frozen gates verify a committed boundary, so they must be re-run with the
tracked context at that boundary. The Phase-5 final verdict gate (P5-99)
verifies the pre-verdict control-plane state, so Phase 6 re-runs it in a
reconstructed verification context: a temporary detached worktree at the exact
frozen Phase-5 tag with only the two post-verdict control-plane edits reverted
(`LAST_PASSED_STAGE=P5-99` -> `P5-91` and the promoted terminal marker in the
queue back to its reserved `NOT_PROVEN` form), run twice, compared
byte-for-byte against the recorded official stdout. The reconstruction is
deterministic, touches no tracked file in the Phase-6 worktree and is removed
afterwards. The exact procedure and hashes are recorded in the stage evidence.

No frozen file may be modified in place and no history may be rewritten.

## Claim ledger vocabulary

- `PROVEN`: supported by deterministic audited evidence on the frozen tree.
- `BOUNDED`: proven only for the exact recorded fixture, configuration and
  claim.
- `UNPROVEN`: not established by evidence.
- `UNSUPPORTED`: known to be outside the implementation or target support.
- `NOT TESTED`: no claim was attempted.

Numeric or performance results are never claims of correctness.
