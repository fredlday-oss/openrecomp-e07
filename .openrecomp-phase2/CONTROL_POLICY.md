# OpenRecomp Phase 2 Control Policy

1. Work as one agent only. No subagents, background agents, parallel implementations, competing branches, or parallel worktrees.
2. Do not use destructive Git commands such as `reset --hard`, `clean -fd`, force checkout, or history rewrite.
3. Do not commit or push unless the user explicitly requests it.
4. Preserve the frozen Phase-1 behavior. Tag `openrecomp-phase1-pass` is the reference boundary.
5. Work on exactly one Phase-2 stage at a time.
6. Advance only after deterministic evidence satisfies that stage's acceptance criteria.
7. Do not weaken, delete, skip, or silently rewrite an existing passing test to make a stage pass.
8. Fail closed when semantics, ABI, memory behavior, control flow, provenance, or runtime behavior are uncertain.
9. Keep architecture-neutral layers independent of platform-specific behavior.
10. Do not commit proprietary ROMs, ISOs, BIOS, firmware, keys, SDK content, or copied copyrighted game data.
11. Local commercial software may be used only for user-authorized metadata/compatibility checks and must remain outside Git.
12. Prefer synthetic/open fixtures for semantics and equivalence proof.
13. Record limitations explicitly. Never promote bounded evidence to universal compatibility.
14. Model confidence, decompiler output, and compilation success alone are not semantic proof.
15. Before changing a shared contract, enumerate affected architectures and run relevant regression gates afterward.
16. Runtime work must keep CPU semantics separate from platform render/audio/input implementations.
17. RT64/GPU-specific integration is optional later work, not a prerequisite for early Phase-2 PASS.

## Advancement rule

A stage advances only when implementation acceptance criteria, stage tests, relevant Phase-1 regressions, evidence, STATE.md, and HANDOFF.md are complete.

## Stop markers

- `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
- `REGRESSION_DETECTED`
- `PROVENANCE_VIOLATION`
