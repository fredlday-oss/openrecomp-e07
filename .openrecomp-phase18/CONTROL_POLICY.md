# OpenRecomp Phase 18 Control Policy

Phase 18 starts from the frozen Phase-17 terminal boundary on branch
`phase18/ps1-first-frame-frontier-v1`, forked from
`d7cc5d09eebde398ca6ff3f3dad8dd5841913b69` (tree
`ad3aa822e5a02905ebc25477f7b6c69d0bffa055`).

1. Work one bounded stage at a time. Each stage terminates `PASS`,
   `PASS_NOT_REQUIRED` or `FAIL`.
2. Never rewrite, amend, rebase, squash, force-push, delete or alter any frozen
   Phase-1 through Phase-17 commit, tag, evidence file, verdict, control file,
   source manifest or gate. Commit
   `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69` is the Phase-18 baseline
   authority. All previous `.openrecomp-phaseN` trees remain read-only.
3. Never fabricate, move or create a historical tag.
4. Phase-18 work is strictly additive under `.openrecomp-phase18/` plus new
   `tools/test_phase18_*` gates. A shared-layer change requires direct Phase-18
   evidence of a real gap, must be additive and fail-closed.
5. Preserve the claim-ledger vocabulary `PROVEN`, `BOUNDED`, `NOT_PROVEN`,
   `NOT_TESTED`.
6. Fail closed and never guess: instruction semantics, delay-slot behaviour,
   exception/syscall delivery, ABI behaviour, indirect targets, memory aliases,
   BIOS service identity, GPU/DMA/VRAM/SPU/CD-ROM behaviour, or virtual time.
   `NOT_PROVEN` is a completely valid and honorable outcome.
7. Each official stage gate runs twice under deterministic budgets; `PASS`
   requires exit 0, empty stderr, byte-identical stdout across dual runs, no
   `FAIL:` lines, and deterministic evidence generation.
8. Causality before implementation: every new capability must be proven
   causally before it is promoted.
9. Authentic-data discipline: never commit, copy, package or redistribute
   private commercial fixture bytes. Only non-reconstructive metadata may be
   recorded in evidence.
10. Private-fixture results are `PRIVATE_FIXTURE_BOUNDED` and never promote
    unwarranted general compatibility or playability claims.
11. Any improved device semantics must derive from PS1 behaviour and actual
    current execution state, with tests and evidence; a title-specific constant
    used solely to escape polling is unacceptable.
12. Public-safety rules remain in force: no raw payload bytes, instruction
    words, operands, private host paths, or reconstructive sequences enter
    evidence.
