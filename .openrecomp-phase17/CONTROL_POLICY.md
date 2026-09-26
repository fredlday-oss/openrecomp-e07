# OpenRecomp Phase 17 Control Policy

Phase 17 starts from the frozen Phase-16 terminal boundary on branch
`phase16/ps1-title-exec-cdrom-v1` at commit
`a0c26e882ca65cfc84cbec78f7e787509a4992a3`, whose terminal verdict is
`PASS_AUTHENTIC_CDROM_TITLE_TRANSITION_POST_TITLE_FRONTIER_REMAINS`. Phase 17 adds no
retroactive Phase-16 claim and preserves the frozen Phase-1 through Phase-16
evidence chains intact.

Authoritative work branch: `phase17/ps1-title-overlay-recompile-v1`.

1. Work as one agent on one serial production frontier at a time.
2. Freeze the stage rows at the `P17-00` `PASS` boundary and reconcile the
   authoritative Phase-17 stage queue to exactly:
   `P17-00, P17-01, P17-02, P17-03, P17-04, P17-05, P17-06, P17-07, P17-90, P17-91, P17-99`.
   `P17-00` froze placeholder/reserved rows before the complete Phase-17
   execution contract was supplied; the authoritative mission now assigns
   evidence-bounded meanings.
3. Never rewrite, amend, rebase, squash, force-push, delete or alter any
   frozen Phase-1 through Phase-16 commit, tag, evidence file, verdict,
   control file, source manifest or gate. Commit `a0c26e882ca65cfc84cbec78f7e787509a4992a3` is the Phase-17
   baseline authority. All previous `.openrecomp-phaseN` trees remain read-only.
4. Never fabricate, move or create a historical tag.
5. Phase-17 work is strictly additive under `.openrecomp-phase17/` plus new
   `tools/test_phase17_*` gates. A shared-layer change requires direct Phase-17
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
9. Whole-suite regression is executed at `P17-90`. Stage gates run their own
   unit and direct dependency checks.
10. Causality before implementation: every new capability must be proven
    causally before it is promoted.
11. Authentic-data discipline: never commit, copy, package or redistribute
    private commercial fixture bytes (executable, CUE, BIN, or raw sectors).
    Only non-reconstructive metadata may be recorded in evidence.
12. Private-fixture results are `PRIVATE_FIXTURE_BOUNDED` and never promote
    unwarranted general compatibility or playability claims.
13. No generic IRQ delivery or speculative hardware simulation beyond what
    the reached fixture mechanically requires.
14. Authenticated P17-02 decoding is permitted under this policy. The historical
    `TITLE_PAYLOAD_DECODING_STATE = "NOT_DECODED"` marker is retained as the P17-01
    policy value only; P17-02 may produce an authenticated, non-reconstructive
    decode projection without claiming later-stage execution objectives.
15. Public-safety rules remain in force: no raw payload bytes, instruction words,
    operands, private host paths, or reconstructive sequences enter evidence.
