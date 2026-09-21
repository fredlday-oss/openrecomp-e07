# OpenRecomp Phase 10 Control Policy

Phase 10 starts from the frozen Phase-9 terminal boundary on branch
`phase8/mips32-end-to-end-native-v1` at commit
`08c639d9032a364163f2985432744be420d402eb`, tree
`900dccf06ce3d5df7b499a9f05a6ceea060114d7`, whose P9-99 terminal verdict is
`OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=PASS` for the exact bounded
audited public fixture and behaviour only. Phase 10 adds no Phase-9 claim and
never weakens the Phase-1 through Phase-9 evidence chain.

1. Work as one agent and on one serial implementation frontier at a time.
   Parallel work is allowed only while read-only/non-mutating (private fixture
   reconnaissance, static analysis, reference-vector generation, test design,
   evidence review, documentation drafting, manifest preparation).
2. Freeze rows `P10-01` through `P10-99` at the P10-00 `PASS` boundary. A later
   queue change must fail closed with `QUEUE_RECONCILIATION_REQUIRED`, record
   the forcing technical dependency, and stop the phase instead of silently
   adapting.
3. Never rewrite, amend, rebase, squash, force-push, delete or otherwise alter
   any frozen Phase-1 through Phase-9 commit, tag, evidence file, verdict,
   control file, source manifest or gate. The Phase-9 terminal commit above is
   the Phase-10 baseline authority.
4. Never fabricate, move or create a historical tag. The inherited
   reconciliations (absent Phase-6 tag, frozen Phase-7 annotated tag, absent
   Phase-8 terminal tag) remain as recorded by Phase 9.
5. Phase-10 work is additive under `.openrecomp-phase10/` plus new
   `tools/test_phase10_*` gates. A shared-layer change requires direct Phase-10
   evidence of a real gap, must be additive, architecture-neutral where
   possible, regression-checked against its direct dependency gates, and
   recorded in the stage evidence. Do not build a second PS1 frontend, MIPS
   decoder, CFG pipeline, host emitter or parallel runtime architecture.
6. Preserve `PROVEN` versus `CANDIDATE` and the claim-ledger vocabulary
   `PROVEN`, `BOUNDED`, `NOT_PROVEN`, `NOT_TESTED`.
7. Fail closed and never guess: instruction semantics, delay-slot behaviour,
   exception/BREAK delivery, ABI behaviour, indirect targets, memory aliases,
   KSEG mapping, BIOS service identity, GPU/DMA/SPU/CD-ROM behaviour, or
   host-filesystem substitution for PS1 CD behaviour.
   `NOT_PROVEN` / `UNSUPPORTED` / `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` are
   valid outcomes.
8. Work one evidence-bounded stage at a time. Each official stage gate runs
   twice; `PASS` requires exit 0, empty stderr, byte-identical stdout, no
   `FAIL:` line, and committed deterministic evidence.
9. Do not run the full historical regression after every stage. Run the
   stage's own gate, its direct dependency gates, source/provenance checks and
   any regression made necessary by changed code. The expensive whole-project
   regression is reserved for P10-90.
10. Compilation or self-comparison is not semantic evidence. Native execution
    requires an incrementally independent reference comparison before
    equivalence is claimed.
11. Never commit, package, copy, redistribute or byte-reference the private
    commercial fixture (executable, CUE, BIN or disc contents), and never copy
    game sectors, files or reconstructive derived data into evidence. Only
    non-reconstructive metadata may be recorded (hashes, sizes, filenames,
    track/filesystem metadata, addresses, load addresses, classifications,
    counts, BIOS/service identifiers, MMIO classes, sector/file access classes,
    bounded execution transcripts, failure categories, runtime observables).
12. Private-fixture results are `PRIVATE_FIXTURE_BOUNDED` and never promote a
    general or playability claim.
13. Never execute original MIPS machine code at runtime. Native execution
    comes only from generated host code; guest images are inert data.
14. Milestones A-G are distinct and must be recorded separately. Only
    milestone G (controllable gameplay) with deterministic scripted-input
    evidence may support `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=PASS`.
15. Record the exact compiler, linker, flags, revisions, hashes, fixture
    identity and observable contract. Host paths, timestamps, UUIDs and
    process identities are forbidden in committed evidence.
16. Never weaken, delete, skip or silently redefine an existing passing test.
    If a contract intentionally changes, record the reason and add replacement
    coverage.
17. A completed stage updates `STATE.md`, `HANDOFF.md`, `STAGE_QUEUE.md`, the
    Phase-10 source manifest and `.openrecomp-phase10/evidence/<STAGE>/`.
18. Commit only completed `PASS` boundaries with a stage-specific message. Do
    not commit failed or partial stages. Do not push unless the user explicitly
    instructs it.

## Stop markers

- `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
- `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
- `REGRESSION_DETECTED`
- `PROVENANCE_VIOLATION`
- `QUEUE_RECONCILIATION_REQUIRED`
- `EVIDENCE_INTEGRITY_FAILURE`
