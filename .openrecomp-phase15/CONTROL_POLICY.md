# OpenRecomp Phase 15 Control Policy

Phase 15 starts from the frozen Phase-14 terminal boundary on branch
`phase14/ps1-hercules-init-closure-v1` at commit
`830be0f7be998061e8d442134cfae511d5dd8c62`, whose terminal verdict is
`PASS_BOUNDED_INITIALIZATION_CLOSURE_FRONTIER_REMAINS`. Phase 15 adds no
Phase-14 claim and never weakens the Phase-1 through Phase-14 evidence chain.

Work branch: `phase15/ps1-hercules-init-mmio-v1`.

1. Work as one agent and on one serial production frontier at a time. Parallel
   work is allowed only while read-only/non-mutating.
2. Freeze the stage rows at the `P15-00` `PASS` boundary. A later queue change
   must fail closed with `QUEUE_RECONCILIATION_REQUIRED`, record the forcing
   technical dependency, and stop the phase instead of silently adapting.
3. Never rewrite, amend, rebase, squash, force-push, delete or otherwise alter
   any frozen Phase-1 through Phase-14 commit, tag, evidence file, verdict,
   control file, source manifest or gate. Commit
   `830be0f7be998061e8d442134cfae511d5dd8c62` is the Phase-15 baseline authority.
   The `.openrecomp-phase14` and earlier `.openrecomp-phaseN` trees are read-only
   for Phase 15.
4. Never fabricate, move or create a historical tag.
5. Phase-15 work is additive under `.openrecomp-phase15/` plus new
   `tools/test_phase15_*` gates. A shared-layer change requires direct Phase-15
   evidence of a real gap, must be additive, architecture-neutral where
   possible, regression-checked against its direct dependency gates, and
   recorded in the stage evidence. Do not build a second PS1 frontend, MIPS
   decoder, CFG pipeline, host emitter or parallel runtime architecture.
6. Preserve `PROVEN` versus `CANDIDATE` and the claim-ledger vocabulary
   `PROVEN`, `BOUNDED`, `NOT_PROVEN`, `NOT_TESTED`.
7. Fail closed and never guess: instruction semantics, delay-slot behaviour,
   exception/BREAK/SYSCALL delivery, ABI behaviour, indirect targets, memory
   aliases, KSEG mapping, BIOS service identity,
   GPU/DMA/SPU/CD-ROM/controller behaviour, interrupt delivery, root counters or
   host-filesystem substitution for PS1 CD behaviour. `NOT_PROVEN` /
   `UNSUPPORTED` / `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` are valid outcomes.
8. Work one evidence-bounded stage at a time. Each official stage gate runs
   twice; `PASS` requires exit 0, empty stderr, byte-identical stdout, no
   `FAIL:` line, and committed deterministic evidence.
9. Do not run the full historical regression after every stage. Run the stage's
   own gate, its direct dependency gates, source/provenance checks and any
   regression made necessary by changed code. The expensive whole-project
   regression is reserved for `P15-90`.
10. Causality before implementation. For every suspected blocker: identify the
    earliest observable divergence, establish temporal ordering, show that
    changing the suspected condition changes progress, construct the smallest
    legal/public reproducer where practical, define the independent expected
    behaviour, implement the smallest reusable fix, rerun Hercules, and record
    the new exact frontier. Correlation is not causation.
11. Never commit, package, copy, redistribute or byte-reference the private
    commercial fixture (executable, CUE, BIN or disc contents), and never copy
    game sectors, files, framebuffers, VRAM content, textures, palettes or other
    reconstructive derived data into evidence. Only non-reconstructive metadata
    may be recorded (hashes, sizes, filenames, addresses, load addresses,
    classifications, counts, BIOS/service identifiers, MMIO classes, bounded
    execution transcripts, failure categories, runtime observables, state
    digests).
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
    Phase-15 source manifest and `.openrecomp-phase15/evidence/<STAGE>/`.
18. Commit only completed `PASS` boundaries with a stage-specific message. Do
    not commit failed or partial stages. Do not push unless the user explicitly
    instructs it.

## Third-party code

No implementation code is copied from PCSX, PCSX-Redux, PSXRecomp, DuckStation,
Mednafen or any other external emulator/recompiler. All Phase-15 behaviour is
implemented from mechanically observed fixture behaviour, public documented BIOS
and hardware behaviour available to the project, the existing OpenRecomp
architecture and independently written tests. Record
`THIRD_PARTY_CODE_IMPORTED=NO`.

## Bounded MMIO model

The Phase-15 interrupt/MMIO layer is a versioned, project-owned bounded register
model layered additively on the frozen runtime:

- every modelled register has an explicit allowed access width; an unsupported
  width fails closed;
- unknown addresses in the I/O window fall through to the frozen fail-closed
  boundary;
- no interrupt delivery, no COP0 exception vectoring, no GPU rasterization, no
  root-counter IRQ and no asynchronous DMA timing is implemented unless a live
  execution frontier proves it is required.

## Stop markers

- `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
- `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
- `REGRESSION_DETECTED`
- `PROVENANCE_VIOLATION`
- `QUEUE_RECONCILIATION_REQUIRED`
- `EVIDENCE_INTEGRITY_FAILURE`
