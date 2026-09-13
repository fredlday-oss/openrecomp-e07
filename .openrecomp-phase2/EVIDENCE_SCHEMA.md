# Phase 2 Evidence Schema

Each stage writes `.openrecomp-phase2/evidence/<STAGE>/RESULT.md`.

Recommended fields:

- Verdict: PASS / FAIL / BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE
- Baseline: git HEAD, Phase-1 tag, source hashes
- Objective
- Changes
- Commands and exit codes
- Deterministic markers/hashes/traces
- Independent/reference comparison where applicable
- Relevant Phase-1 and Phase-2 regressions
- Limitations
- Repository side effects
- Next stage

Machine-readable evidence may be written beside RESULT.md as JSON.

Compilation success alone is not semantic equivalence. Linear disassembly alone is not function recovery. Indirect targets must not be guessed.
