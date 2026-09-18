# OpenRecomp Phase 6 Control Policy

1. One implementation frontier at a time. Do not create subagents, background
   agents, parallel implementation branches or competing solutions. Only one
   implementation stage may be `ACTIVE` at a time. Read-only analysis,
   independent verification, test/vector generation, evidence indexing,
   manifest verification and regression preparation may proceed in parallel
   only when they cannot mutate the active frontier.
2. Freeze the complete Phase-6 queue at P6-00: rows `P6-01` .. `P6-99` are
   frozen exactly as recorded in `STAGE_QUEUE.md`, effective before any P6-01
   implementation work. No silent renumbering, insertion, merging, splitting,
   scope change or relaxation of required outcomes.
3. Do not use destructive Git commands such as `reset --hard`, `clean -fd`,
   force checkout, force push, rebase, amend, squash or any history rewrite.
   The frozen Phase-1, Phase-2, Phase-3, Phase-4 and Phase-5 histories, tags,
   evidence, verdicts and control planes are immutable.
4. Preserve the frozen Phase-5 boundary: annotated tag
   `openrecomp-phase5-pass` (object
   `b5d6832ba2374b810f4c24500ed9093a9481fd8d`) resolves to commit
   `e8d3627a622d0ca3196b117c5112f29fabdb49e7`, tree
   `468fb9788350de393d3de2ca9471b7d874ee8dc9`. The Phase-4 boundary
   (object `e7eaab18fee267b3d7962db13835c9e14dd77fc2`, commit
   `b3c71fb690f00b4811e8ec30c28f7725141295d0`, tree
   `f2ca3080915aa68f403526b89dfc17454687aed6`), the Phase-3 boundary
   (object `ac31524504b1b5cc63aabcfd5132a3eb4275e8e9`, commit
   `e16e4b29b90f379615f1af97e47747cd1d531796`, tree
   `a940f0d84a32adaf191f7ff2bebfb24cc855cde0`), the Phase-2 boundary
   `01b1d7cba8c931fca95d041389cfb1902b7c89fe` and the Phase-1 boundary
   `46c2f971e1a42cf49bd936bad94697b81bf31002` remain earlier reference
   boundaries. Never rewrite, amend, squash, rebase, modify or otherwise
   mutate any frozen history, tag, evidence, verdict or control plane.
5. Do not modify frozen Phase-1/Phase-2/Phase-3/Phase-4/Phase-5 evidence,
   gates, control planes or verdicts and do not modify any file listed in the
   frozen root/Phase-3/Phase-4/Phase-5 manifests. Phase-6 work is additive
   under `.openrecomp-phase6/` plus new `tools/test_phase6_*` gates. Re-running
   a frozen gate may refresh its own deterministic evidence sidecar in the
   working tree; that is a re-run artifact, not a history change, and must be
   recorded.
6. Work one evidence-bounded Phase-6 stage at a time. Advance only after
   deterministic evidence satisfies that stage's acceptance criteria and the
   frozen required outcome, and every official stage gate has been run twice.
7. PASS requires byte-identical stdout across the two official runs and empty
   stderr on both. Commit only after a deterministic stage PASS, and only the
   completed stage boundary. Do not push unless explicitly instructed.
8. Never weaken, delete, skip or silently rewrite an existing passing test or
   gate to obtain PASS. If a contract intentionally changes, document the
   reason and add replacement coverage.
9. Fail closed on malformed iNES/NES 2.0 images, unsupported mappers,
   unsupported MMC1 variants/board wiring, unsupported/undocumented opcodes,
   uncertain semantics, unmapped memory, unsupported PPU/APU/reset/NMI/IRQ
   behaviour and any unsupported hardware requirement. Unknown mapper or
   hardware behaviour fails closed. Never guess hardware behaviour or board
   wiring not proven by cartridge evidence.
10. Do not execute original guest 6502 code directly on the host. Native
    execution must come from OpenRecomp-generated host code.
11. Preserve public/private fixture separation. The private image
    `D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes` is classified
    `PRIVATE_LOCAL_COMPATIBILITY_FIXTURE`. Never commit, copy, embed, package,
    upload or redistribute its bytes or any ROM-derived binary copy. Never add
    `*.nes`, `*.fds`, `*.unf`, `*.unif` or ROM-derived binary dumps to the
    repository, evidence, package, ZIP, fixture directory, Git object database
    or any public artifact. Record only source path, file size, cryptographic
    hashes, iNES metadata, mapper/mirroring/PRG/CHR inventory and derived
    control-flow/instruction/compatibility evidence that does not reproduce
    copyrighted program data unnecessarily. The private image can never be the
    public Phase-6 proof fixture.
12. The public Phase-6 proof fixture must be legally redistributable with
    recorded provenance, license, exact source revision, toolchain, build
    flags, ROM SHA-256, PRG/CHR sizes, mapper, mirroring and vectors. It is an
    original MMC1 fixture authored for Phase 6 under Apache-2.0.
13. Preserve `PROVEN` vs `CANDIDATE` classification. The Phase-6 claim ledger
    uses `PROVEN`, `BOUNDED`, `UNPROVEN`, `UNSUPPORTED` and `NOT TESTED`.
    Never promote bounded evidence to a universal claim.
14. Do not invent indirect branch targets, MMC1 board wiring, register
    behaviour, hardware behaviour, imports, runtime services, memory mappings,
    timing behaviour, interrupt behaviour or compatibility claims. Unknown
    behaviour remains explicit and fail-closed.
15. Generated code must not silently call arbitrary host functionality.
    External behaviour is mediated through the frozen Phase-4 typed and
    versioned runtime service interfaces; unknown or unsupported services fail
    closed.
16. Keep architecture-neutral layers independent of platform-specific
    behaviour. MMC1-specific behaviour lives behind explicit Phase-6 mapper
    adapter boundaries. Graphics/audio backends must not become mandatory to
    the OpenRecomp core.
17. Every stage writes deterministic evidence under
    `.openrecomp-phase6/evidence/<STAGE>/` and automatically updates
    `STATE.md`, `HANDOFF.md`, `STAGE_QUEUE.md`, `SOURCE_SHA256SUMS.txt` and
    the stage `RESULT.md` on PASS.
18. The Phase-6 whole-regression gate (P6-90) must re-verify the frozen
    Phase-1/Phase-2/Phase-3/Phase-4/Phase-5 chain and all Phase-6 stage gates
    from the audited tree, preserving frozen historical evidence and requiring
    deterministic outputs.
19. Record every material limitation. A Phase-6 PASS must not silently imply
    general NES compatibility, all MMC1 boards or revisions, all NES games,
    commercial-game compatibility, cycle accuracy, full PPU accuracy, full APU
    accuracy, FDS compatibility or arbitrary 6502 compatibility. Retain
    `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` always.
20. Automatic commit applies to each completed PASS boundary only. Never
    commit a failed, blocked or partial stage.

## Advancement rule

A stage advances only when its frozen required outcome, acceptance criteria,
negative/fail-closed coverage, relevant earlier-phase regressions, source
integrity, evidence, `STATE.md`, `HANDOFF.md`, `STAGE_QUEUE.md` and
`SOURCE_SHA256SUMS.txt` are complete and the official gate has passed twice
with byte-identical stdout and empty stderr.

## Stop markers

- `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
- `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
- `REGRESSION_DETECTED`
- `PROVENANCE_VIOLATION`
