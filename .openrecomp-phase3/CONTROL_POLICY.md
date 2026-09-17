# OpenRecomp Phase 3 Control Policy

1. Work as one agent only. No subagents, background agents, parallel implementations,
   competing branches, or parallel worktrees.
2. Do not use destructive Git commands such as `reset --hard`, `clean -fd`, force
   checkout, force push, or history rewrite.
3. Do not commit or push unless the user explicitly requests it.
4. Preserve the frozen Phase-2 boundary. Tag `openrecomp-phase2-pass` is the reference
   boundary for the Phase-3 baseline; the Phase-1 tag `openrecomp-phase1-pass` remains
   the earlier reference.
5. Do not modify frozen Phase-2 evidence, the P2-90/P2-91 gates, the P2-99 verdict or
   the recorded Phase-2 claim boundaries. Do not weaken any Phase-2 gate.
6. Work on exactly one Phase-3 stage at a time. Advance only after deterministic
   evidence satisfies that stage's acceptance criteria.
7. Do not weaken, delete, skip, or silently rewrite an existing passing test to make a
   stage pass. If a contract intentionally changes, document the reason and add
   replacement coverage.
8. Fail closed on malformed ELF/IR/input and on uncertain semantics, ABI, memory
   behavior, control flow, provenance, or runtime behavior.
9. Preserve PROVEN vs CANDIDATE classification. Never promote bounded evidence to a
   universal claim.
10. Never commit proprietary ROMs, ISOs, BIOS, firmware, keys, SDK content, console
    assets, or copied copyrighted code/data. Third-party open-source material (for
    example CoreMark) may only be used with recorded provenance, license and hashes.
11. Prefer synthetic/original or openly licensed fixtures. Model confidence, decompiler
    output and compilation success alone are not semantic proof.
12. Keep architecture-neutral layers independent of platform-specific behavior; record
    inventory-driven gaps rather than guessing semantics.
13. Runtime work must keep CPU semantics separate from platform render/audio/input
    implementations.
14. Record limitations explicitly in `.openrecomp-phase3/STATE.md`,
    `.openrecomp-phase3/HANDOFF.md` and stage evidence.

## Advancement rule

A stage advances only when implementation acceptance criteria, stage tests, relevant
Phase-1/Phase-2 regressions, evidence, STATE.md and HANDOFF.md are complete.

## Stop markers

- `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
- `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
- `REGRESSION_DETECTED`
- `PROVENANCE_VIOLATION`
