# Phase 7 Evidence Schema

Each stage writes `.openrecomp-phase7/evidence/<STAGE>/RESULT.md` plus
machine-readable sidecars.

## Required `RESULT.md` fields

- Verdict: `PASS` / `FAIL` / `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` /
  `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
- Baseline: git HEAD commit and tree, branch, baseline identity
- Objective: the frozen queue required outcome for the stage
- Changes: exact files, additive vs modified, and why
- Commands and exit codes: official gate (twice), relevant regressions,
  source integrity
- Deterministic markers/hashes/traces: raw and LF-normalized sha256 for every
  stdout capture
- Independent/reference comparison where technically appropriate
- Negative / fail-closed coverage
- Relevant Phase-1 / Phase-2 / Phase-3 / Phase-4 / Phase-5 / Phase-6
  regressions with results
- Claim ledger deltas
- Limitations and unproven areas
- Repository side effects: tracked vs untracked, working-tree delta
- Evidence index: the files in the stage evidence directory
- Next stage

## Machine-readable sidecars

- The stage gate's own record `<stage>_tests.json` (for example
  `p7_00_tests.json`) with fields
  `{stage, stage_name, status, tests, passed, failed, markers, checks, findings, failure}`;
  `checks` sorted by check label.
- `official_runs.json` recording both official gate runs
  (`returncode`, `stdout_bytes`, `stdout_sha256_raw`, `stdout_sha256_lf`,
  `stderr_empty`, markers).
- Per-topic JSON records (for example frontier re-derivation records, opcode
  classification records, bank-reachability records, indirect-target records,
  equivalence records) written next to `RESULT.md`.

## Rules

1. Evidence is UTF-8 with LF endings. Captures piped from a Windows console
   are stored LF-normalized, with both raw and LF sha256 recorded; raw
   captures that must stay untracked are hash-pinned by their stage record.
2. Evidence must be deterministic: no host paths, timestamps, process
   identity, UUIDs or absolute toolchain paths.
3. Fail closed on malformed input without a Python traceback; stable
   deterministic failure classifications only.
4. Compilation success alone is not semantic equivalence. Linear disassembly
   alone is not function recovery. Indirect targets, bank state and board
   wiring must not be guessed.
5. Every stage gate emits on stdout:
   `OPENRECOMP_P7_XX=<status>`,
   `OPENRECOMP_PHASE7_<NAME>_V1=<status> tests=N`,
   and the terminal/general markers in their current reserved state.
6. The official gate is run twice; byte-identical stdout with empty stderr is
   required for PASS.
7. Evidence never contains ROM bytes (private or public) or derived binary
   copies; only hashes, metadata, counts, addresses and derived analysis.
8. The private TMNT image is analyzed only by metadata/hash plus derived
   classification evidence (counts, opcode histograms, addresses,
   control-flow classifications, stop reasons), never program bytes.

## Frozen-gate re-run hygiene

Frozen gates verify a committed boundary, so they must be re-run with the
tracked context at that boundary. The Phase-6 final verdict gate (P6-99)
verifies the pre-verdict control-plane state, so Phase 7 re-runs it in a
reconstructed verification context: a temporary detached worktree at the
exact frozen Phase-6 terminal commit with only the post-verdict control-plane
edits reverted (`LAST_PASSED_STAGE=P6-99` -> `P6-91`,
`MMC1_PLATFORM_STATUS=PROVEN` -> `NOT_PROVEN`, `FINAL_VERDICT=PASS` ->
`NOT_PROVEN`, the state terminal marker back to `NOT_PROVEN`, the queue
terminal marker back to `NOT_PROVEN` and the `P6-99` queue row back to
`QUEUED`), run twice, compared byte-for-byte against the recorded official
stdout. The reconstruction is deterministic, touches no tracked file in the
Phase-7 worktree and is removed afterwards. The exact procedure and hashes
are recorded in the stage evidence.

No frozen file may be modified in place and no history may be rewritten.

## Claim ledger vocabulary

- `PROVEN`: supported by deterministic audited evidence on the frozen tree.
- `BOUNDED`: proven only for the exact recorded fixture, configuration and
  claim.
- `UNPROVEN`: not established by evidence.
- `UNSUPPORTED`: known to be outside the implementation or target support.
- `NOT TESTED`: no claim was attempted.

Indirect-control-flow states use the explicit vocabulary `RESOLVED_EXACT`,
`RESOLVED_FINITE_SET`, `UNRESOLVED`, `IMPOSSIBLE`.

Numeric or performance results are never claims of correctness.
