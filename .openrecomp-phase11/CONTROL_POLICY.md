# OpenRecomp Phase 11 Control Policy

Phase 11 starts from the frozen Phase-10 terminal boundary on branch
`phase10/ps1-commercial-game-native-v1` at commit
`8961682` (tree derived from Git, recorded in `evidence/P11-00/baseline.json`),
whose `P10-99` terminal verdict is
`OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=PASS` for the exact audited
private Hercules fixture and the demonstrated milestone A only. Phase 11 adds
no Phase-10 claim and never weakens the Phase-1 through Phase-10 evidence
chain.

Work branch: `phase11/ps1-playability-v1`.

1. Work as one agent and on one serial implementation frontier at a time.
   Parallel work is allowed only while read-only/non-mutating (private fixture
   reconnaissance, static analysis, reference-vector generation, trace
   review, test design, evidence review, documentation drafting, manifest
   preparation).
2. Freeze rows `P11-01` through `P11-99` at the `P11-00` `PASS` boundary. A
   later queue change must fail closed with
   `QUEUE_RECONCILIATION_REQUIRED`, record the forcing technical dependency,
   and stop the phase instead of silently adapting.
3. Never rewrite, amend, rebase, squash, force-push, delete or otherwise alter
   any frozen Phase-1 through Phase-10 commit, tag, evidence file, verdict,
   control file, source manifest or gate. The Phase-10 terminal commit above is
   the Phase-11 baseline authority.
4. Never fabricate, move or create a historical tag. The inherited
   reconciliations (absent Phase-6 tag, frozen Phase-7 annotated tag, absent
   Phase-8/Phase-9/Phase-10 terminal tags) remain as recorded by Phase 10.
5. Phase-11 work is additive under `.openrecomp-phase11/` plus new
   `tools/test_phase11_*` gates. A shared-layer change requires direct
   Phase-11 evidence of a real gap, must be additive, architecture-neutral
   where possible, regression-checked against its direct dependency gates, and
   recorded in the stage evidence. Do not build a second PS1 frontend, MIPS
   decoder, CFG pipeline, host emitter or parallel runtime architecture.
6. Preserve `PROVEN` versus `CANDIDATE` and the claim-ledger vocabulary
   `PROVEN`, `BOUNDED`, `NOT_PROVEN`, `NOT_TESTED`.
7. Fail closed and never guess: instruction semantics, delay-slot behaviour,
   exception/BREAK delivery, ABI behaviour, indirect targets, memory aliases,
   KSEG mapping, BIOS service identity, GPU/DMA/SPU/CD-ROM/controller
   behaviour, interrupt delivery, or host-filesystem substitution for PS1 CD
   behaviour. `NOT_PROVEN` / `UNSUPPORTED` /
   `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` are valid outcomes.
8. Work one evidence-bounded stage at a time. Each official stage gate runs
   twice; `PASS` requires exit 0, empty stderr, byte-identical stdout, no
   `FAIL:` line, and committed deterministic evidence.
9. Do not run the full historical regression after every stage. Run the
   stage's own gate, its direct dependency gates, source/provenance checks and
   any regression made necessary by changed code. The expensive whole-project
   regression is reserved for `P11-90`.
10. Causality before implementation. For every suspected blocker: identify the
    earliest observable divergence, establish temporal ordering, show that
    changing the suspected condition changes progress, construct the smallest
    legal/public reproducer where practical, define the independent expected
    behaviour, demonstrate the old path blocks for the expected reason,
    implement the smallest reusable fix, rerun Hercules, and record the new
    exact frontier. Correlation is not causation.
11. Never commit, package, copy, redistribute or byte-reference the private
    commercial fixture (executable, CUE, BIN or disc contents), and never copy
    game sectors, files, framebuffers, VRAM content, textures, palettes or
    other reconstructive derived data into evidence. Only non-reconstructive
    metadata may be recorded (hashes, sizes, filenames, track/filesystem
    metadata, addresses, load addresses, classifications, counts,
    BIOS/service identifiers, MMIO classes, sector/file access classes,
    bounded execution transcripts, failure categories, runtime observables,
    state digests).
12. Private-fixture results are `PRIVATE_FIXTURE_BOUNDED` and never promote a
    general or playability claim.
13. Never execute original MIPS machine code at runtime. Native execution
    comes only from generated host code; guest images are inert data.
14. Milestones A-G are distinct and must be recorded separately:
    A translated native execution begins, B initialization completes,
    C GPU command stream reached, D first valid frame, E title/logo screen,
    F menu, G controllable gameplay. Promotion rules:
    * B requires deterministic evidence that initialization actually
      completes;
    * C requires actual GPU command writes/stream, not status polling;
    * D requires a valid rendered frame proven semantically or by hash;
    * E requires title/logo state;
    * F requires menu state;
    * G requires deterministic scripted controller input causing reproducible
      game-state progression; a screenshot alone never proves G.
15. Record the exact compiler, linker, flags, revisions, hashes, fixture
    identity and observable contract. Host paths, timestamps, UUIDs and
    process identities are forbidden in committed evidence.
16. Never weaken, delete, skip or silently redefine an existing passing test.
    If a contract intentionally changes, record the reason and add replacement
    coverage.
17. A completed stage updates `STATE.md`, `HANDOFF.md`, `STAGE_QUEUE.md`, the
    Phase-11 source manifest and `.openrecomp-phase11/evidence/<STAGE>/`.
18. Commit only completed `PASS` boundaries with a stage-specific message. Do
    not commit failed or partial stages. Do not push unless the user explicitly
    instructs it.

## Authorized queue reconciliation

The serial runtime frontier became unreachable at the completed `P11-07`
boundary because the caller requires a guest-addressable `B0:0x5B` code/data
representation that is not established by acceptable public evidence. The
required queue decision is `QUEUE_RECONCILIATION_REQUIRED`.

The user explicitly authorized one control-only reconciliation stage,
`P11-RC`, whose baseline is commit
`515e3fb0e660d3c7975e3828eb3e26ac025c7cf2`. This authorization:

- preserves every completed `P11-00` through `P11-07` commit and evidence
  record byte-for-byte;
- preserves the original `P11-08` through `P11-12` queue rows verbatim as the
  historical frozen plan;
- records that `P11-08` through `P11-12` were not executed and receive no
  stage verdict because their serial runtime frontier is unreachable;
- authorizes only the terminal route `P11-RC -> P11-90 -> P11-91 -> P11-99`;
- does not authorize a BIOS replacement, B0 table, HLE opcode, guest target,
  runtime bypass, or any other semantic implementation;
- leaves all milestone and compatibility promotion rules unchanged.

`P11-RC` is a completed boundary only when its gate and the required
P11-00/P11-07/P11-06/P11-05 regressions each pass twice with deterministic
evidence. The reconciled route does not reinterpret an unexecuted stage as
`PASS`, `FAIL`, skipped, inherited-blocked or not-applicable. `P11-90`,
`P11-91` and `P11-99` remain independent evidence stages and may begin only
after their predecessor commits successfully.

## Analysis cache

Cache keys must include, as applicable: the executable SHA-256, the CUE
SHA-256, the BIN SHA-256, the analysis version, the semantics version, the
runtime version, the device-contract version, the trace configuration and the
scripted-input identity. A stale or mismatched entry is rejected, never
silently reused.

## Stop markers

- `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
- `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
- `REGRESSION_DETECTED`
- `PROVENANCE_VIOLATION`
- `QUEUE_RECONCILIATION_REQUIRED`
- `EVIDENCE_INTEGRITY_FAILURE`
