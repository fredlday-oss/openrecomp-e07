# AGENTS.md — E07 V1.1
- Synthetic/original inputs only.
- Fail closed without traceback for malformed ELF/IR.
- IR schema and host contract are executable gates.
- Every guest memory access is bounds checked.
- Preserve PROVEN vs CANDIDATE.
- `direct_call_graph` means direct calls only; unresolved `jalr`/tail calls are separate.
- Verify `SOURCE_SHA256SUMS.txt` before execution; generated files use the per-run manifest.
- Never add proprietary/console assets, keys, firmware, SDK material or console-derived formats.

<!-- OPENRECOMP_PHASE1_OPENCODE_BEGIN -->
## OpenRecomp Phase 1 multi-architecture control

When working on Phase 1, read these files before modifying code:

- `.openrecomp-phase1/CONTROL_POLICY.md`
- `.openrecomp-phase1/SCOPE.md`
- `.openrecomp-phase1/STAGE_QUEUE.md`
- `.openrecomp-phase1/STATE.md`
- `.openrecomp-phase1/HANDOFF.md` if it contains a current checkpoint.

### Non-negotiable rules

1. Work as **one agent only**. Do not create subagents, background agents, parallel implementation branches, or competing solutions.
2. Preserve existing OpenRecomp functionality, especially the established PS2/R5900 path. Multi-architecture support must be additive or cleanly abstract existing code without semantic regression.
3. Work one evidence-bounded stage at a time. A stage passes only after deterministic verification.
4. Do not treat model confidence as evidence. Tests, compiler output, deterministic traces, fixture comparison, or source-backed architectural facts decide correctness.
5. Never use destructive Git commands such as `reset --hard`, `clean -fd`, force checkout, force push, history rewriting, or deletion of unrelated user work.
6. Never weaken/delete an existing test just to obtain PASS. If a prior test must change because a contract intentionally changed, explain the reason and add replacement coverage.
7. Do not silently guess CPU semantics, flags, cycle behavior, memory mapping, interrupt behavior, cartridge banking, or undocumented opcodes. Mark unresolved semantics as `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`.
8. Do not embed or commit copyrighted commercial ROM images, BIOS files, keys, or other proprietary assets. Use synthetic fixtures, openly licensed tests, or user-supplied local assets that remain outside version control.
9. Keep generated evidence under `.openrecomp-phase1/evidence/<stage-id>/` when practical.
10. Update `.openrecomp-phase1/STATE.md` after every completed, failed, or blocked stage.
11. Before a context/session handoff, update `.openrecomp-phase1/HANDOFF.md` with exact next action, changed files, verification commands/results, unresolved evidence, and Git status.
12. Continue automatically between evidence-supported stages. Stop only for a real blocker, failed baseline that cannot safely be repaired, missing external evidence/asset, or a potentially destructive/irreversible action.
13. Do not claim broad emulator/game compatibility from the Phase-1 proof. Use the exact completion definitions in `SCOPE.md`.
<!-- OPENRECOMP_PHASE1_OPENCODE_END -->

<!-- OPENRECOMP_PHASE2_OPENCODE_BEGIN -->
## OpenRecomp Phase 2 end-to-end recompilation control

Phase 2 starts from the frozen Phase-1 proof at tag openrecomp-phase1-pass.

Before modifying Phase-2 code, read:

- .openrecomp-phase2/CONTROL_POLICY.md
- .openrecomp-phase2/SCOPE.md
- .openrecomp-phase2/STAGE_QUEUE.md
- .openrecomp-phase2/STATE.md
- .openrecomp-phase2/HANDOFF.md

Work sequentially, one evidence-bounded stage at a time. Preserve all Phase-1 functionality and fail closed on unsupported semantics. Do not commit proprietary ROM/game/BIOS/firmware/SDK material.
<!-- OPENRECOMP_PHASE2_OPENCODE_END -->