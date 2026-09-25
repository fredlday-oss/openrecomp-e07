# OpenRecomp Phase 16 Control Policy

Phase 16 starts from the frozen Phase-15 terminal boundary on branch
`phase15/ps1-hercules-init-mmio-v1` at commit
`5cec005d45e8361e5ea132731661b13a72a5ed13`, whose terminal verdict is
`PASS_BOUNDED_INITIALIZATION_CLOSURE_FRONTIER_REMAINS`. Phase 16 adds no
retroactive Phase-15 claim and preserves the frozen Phase-14 and Phase-15
evidence chains intact.

Work branch: `phase16/ps1-title-exec-cdrom-v1`.

1. Work as one agent on one serial production frontier at a time.
2. Freeze the stage rows at the `P16-00` `PASS` boundary. Any stage queue
   change requires explicit technical justification and fails closed.
3. Never rewrite, amend, rebase, squash, force-push, delete or alter any
   frozen Phase-1 through Phase-15 commit, tag, evidence file, verdict,
   control file, source manifest or gate. Commit `5cec005d` is the Phase-16
   baseline authority. All previous `.openrecomp-phaseN` trees remain read-only.
4. Never fabricate, move or create a historical tag.
5. Phase-16 work is strictly additive under `.openrecomp-phase16/` plus new
   `tools/test_phase16_*` gates. A shared-layer change requires direct Phase-16
   evidence of a real gap, must be additive and fail-closed.
6. Preserve `PROVEN` versus `CANDIDATE` and the claim-ledger vocabulary
   `PROVEN`, `BOUNDED`, `NOT_PROVEN`, `NOT_TESTED`.
7. Fail closed and never guess: instruction semantics, delay-slot behaviour,
   exception/syscall delivery, ABI behaviour, indirect targets, memory aliases,
   BIOS service identity, GPU/DMA/SPU/CD-ROM behaviour, or virtual time.
   `NOT_PROVEN` is a completely valid and honorable outcome.
8. Each official stage gate runs twice under deterministic budgets; `PASS`
   requires exit 0, empty stderr, byte-identical stdout across dual runs,
   no `FAIL:` lines, and deterministic evidence generation.
9. Whole-suite regression is executed at `P16-90`. Stage gates run their own
   unit and direct dependency checks.
10. Causality before implementation: every new capability must be proven
    causally (e.g., via ablation testing showing that removing the CD sector
    delivery blocks TITLE load deterministically).
11. Authentic-data discipline: never commit, copy, package or redistribute
    private commercial fixture bytes (executable, CUE, BIN, or raw sectors).
    Only non-reconstructive metadata may be recorded in evidence.
12. Private-fixture results are `PRIVATE_FIXTURE_BOUNDED` and never promote
    unwarranted general compatibility or playability claims.
13. No generic IRQ delivery or speculative hardware simulation beyond what
    the reached fixture mechanically requires.
