# OpenRecomp Phase 12 Control Policy

Phase 12 starts from the frozen Phase-11 terminal boundary on branch
`phase11/ps1-playability-v1` at commit
`665d11dc9f760d0c4ea2486e186c1fe5c762647c`
(`phase11: complete P11-99 final bounded verdict`), whose terminal verdict is
`FINAL_VERDICT=PASS_BOUNDED_MILESTONE_C_PRIVATE_FIXTURE`. Phase 12 adds no
Phase-11 claim and never weakens the Phase-1 through Phase-11 evidence chain.

Work branch: `phase12/ps1-hercules-init-frame-v1`.

1. Work as one agent and on one serial implementation frontier at a time.
   Parallel work is allowed only while read-only/non-mutating (private fixture
   reconnaissance review, static analysis, reference-vector generation, trace
   review, test design, evidence review, documentation drafting, manifest
   preparation).
2. Freeze the stage rows `P12-01` through `P12-99` at the `P12-00` `PASS`
   boundary. A later queue change must fail closed with
   `QUEUE_RECONCILIATION_REQUIRED`, record the forcing technical dependency, and
   stop the phase instead of silently adapting.
3. Never rewrite, amend, rebase, squash, force-push, delete or otherwise alter
   any frozen Phase-1 through Phase-11 commit, tag, evidence file, verdict,
   control file, source manifest or gate. Commit `665d11dc` is the Phase-12
   baseline authority. The `.openrecomp-phase11`, `.openrecomp-phase10` and
   earlier `.openrecomp-phaseN` trees are read-only for Phase 12.
4. Never fabricate, move or create a historical tag.
5. Phase-12 work is additive under `.openrecomp-phase12/` plus new
   `tools/test_phase12_*` gates. A shared-layer change requires direct Phase-12
   evidence of a real gap, must be additive, architecture-neutral where
   possible, regression-checked against its direct dependency gates, and
   recorded in the stage evidence. Do not build a second PS1 frontend, MIPS
   decoder, CFG pipeline, host emitter or parallel runtime architecture.
6. Preserve `PROVEN` versus `CANDIDATE` and the claim-ledger vocabulary
   `PROVEN`, `BOUNDED`, `NOT_PROVEN`, `NOT_TESTED`.
7. Fail closed and never guess: instruction semantics, delay-slot behaviour,
   exception/BREAK delivery, ABI behaviour, indirect targets, memory aliases,
   KSEG mapping, BIOS service identity, GPU/DMA/SPU/CD-ROM/controller
   behaviour, interrupt delivery, or host-filesystem substitution for PS1 CD
   behaviour. `NOT_PROVEN` / `UNSUPPORTED` / `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
   are valid outcomes.
8. Work one evidence-bounded stage at a time. Each official stage gate runs
   twice; `PASS` requires exit 0, empty stderr, byte-identical stdout, no
   `FAIL:` line, and committed deterministic evidence.
9. Do not run the full historical regression after every stage. Run the stage's
   own gate, its direct dependency gates, source/provenance checks and any
   regression made necessary by changed code. The expensive whole-project
   regression is reserved for `P12-90`.
10. Causality before implementation. For every suspected blocker: identify the
    earliest observable divergence, establish temporal ordering, show that
    changing the suspected condition changes progress, construct the smallest
    legal/public reproducer where practical, define the independent expected
    behaviour, demonstrate the old path blocks for the expected reason,
    implement the smallest reusable fix, rerun Hercules, and record the new
    exact frontier. Correlation is not causation.
11. Never commit, package, copy, redistribute or byte-reference the private
    commercial fixture (executable, CUE, BIN or disc contents), and never copy
    game sectors, files, framebuffers, VRAM content, textures, palettes or other
    reconstructive derived data into evidence. Only non-reconstructive metadata
    may be recorded (hashes, sizes, filenames, track/filesystem metadata,
    addresses, load addresses, classifications, counts, BIOS/service
    identifiers, MMIO classes, sector/file access classes, bounded execution
    transcripts, failure categories, runtime observables, state digests).
12. Private-fixture results are `PRIVATE_FIXTURE_BOUNDED` and never promote a
    general or playability claim.
13. Never execute original MIPS machine code at runtime. Native execution comes
    only from generated host code; guest images are inert data.
14. Milestones A-G keep the exact Phase-11 meanings. A `PASS` does not itself
    imply a milestone promotion.
15. Record the exact compiler, linker, flags, revisions, hashes, fixture
    identity and observable contract. Host paths, timestamps, UUIDs and process
    identities are forbidden in committed evidence.
16. Never weaken, delete, skip or silently redefine an existing passing test. If
    a contract intentionally changes, record the reason and add replacement
    coverage.
17. A completed stage updates `STATE.md`, `HANDOFF.md`, `STAGE_QUEUE.md`, the
    Phase-12 source manifest and `.openrecomp-phase12/evidence/<STAGE>/`.
18. Commit only completed `PASS` boundaries with a stage-specific message. Do
    not commit failed or partial stages. Do not push unless the user explicitly
    instructs it.

## Third-party code

No implementation code is copied from PCSX, PCSX-Redux, PSXRecomp, DuckStation,
Mednafen or any other external emulator/recompiler. All Phase-12 behaviour is
implemented from mechanically observed fixture behaviour, clean semantic
descriptions available to the project, the existing OpenRecomp architecture and
independently written tests. Record `THIRD_PARTY_CODE_IMPORTED=NO`.

## Synthetic BIOS object window

The B0 jump table is BIOS-resident and absent from the fixture. Phase 12 models
the required B0 semantics through the existing typed service/runtime mediation
architecture and a clearly synthetic, project-owned guest data window
(`P12_SYNTH_BASE`). The synthetic window is explicitly implementation-defined:
it is never presented as a recovered BIOS address and it is never derived from
the fixture. Unknown B0 table entries remain unmapped and fail closed.

## Stop markers

- `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
- `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
- `REGRESSION_DETECTED`
- `PROVENANCE_VIOLATION`
- `QUEUE_RECONCILIATION_REQUIRED`
- `EVIDENCE_INTEGRITY_FAILURE`
