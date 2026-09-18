# OpenRecomp Phase 5 Control Policy

1. Work as one agent only. Do not create subagents, background agents, parallel
   implementation branches, or competing solutions. Keep the primary
   implementation/recompilation/runtime frontier serial: only one
   implementation stage may be `ACTIVE` at a time. Parallel work is allowed
   only when it cannot mutate or conflict with the active implementation
   frontier (read-only analysis, independent verification, test/vector
   generation, evidence indexing, documentation preparation, manifest
   verification, regression preparation).
2. Do not use destructive Git commands such as `reset --hard`, `clean -fd`,
   force checkout, force push, rebase, amend, squash or any history rewrite.
   The frozen Phase-1, Phase-2, Phase-3 and Phase-4 histories and tags are
   immutable.
3. Commit only the completed stage boundary after a deterministic PASS, as
   instructed by the Phase-5 program. Do not push unless explicitly requested.
4. Preserve the frozen Phase-4 boundary: annotated tag
   `openrecomp-phase4-pass` (object
   `e7eaab18fee267b3d7962db13835c9e14dd77fc2`) resolves to commit
   `b3c71fb690f00b4811e8ec30c28f7725141295d0`, tree
   `f2ca3080915aa68f403526b89dfc17454687aed6`. Tags
   `openrecomp-phase3-pass` (object
   `ac31524504b1b5cc63aabcfd5132a3eb4275e8e9`, commit
   `e16e4b29b90f379615f1af97e47747cd1d531796`, tree
   `a940f0d84a32adaf191f7ff2bebfb24cc855cde0`),
   `openrecomp-phase2-pass` = `01b1d7cba8c931fca95d041389cfb1902b7c89fe`
   and `openrecomp-phase1-pass` = `46c2f971e1a42cf49bd936bad94697b81bf31002`
   remain earlier reference boundaries. Never rewrite, amend, squash, rebase,
   modify or otherwise mutate any frozen history or tag.
5. Do not modify frozen Phase-1/Phase-2/Phase-3/Phase-4 evidence, gates,
   control planes or verdicts, and do not modify any file listed in the frozen
   root manifest, the frozen Phase-3 manifest or the frozen Phase-4 manifest.
   Phase-5 work is additive under `.openrecomp-phase5/` plus new
   `tools/test_phase5_*` gates. Re-running a frozen gate may refresh its own
   deterministic evidence sidecar in the working tree; that is a re-run
   artifact, not a history change, and must be recorded. If Phase 5 exposes a
   defect in an earlier implementation layer, document it explicitly, keep the
   historical tags untouched, and prefer an additive Phase-5 layer; fixing a
   frozen file requires an explicit, documented reconciliation record.
6. Work one evidence-bounded Phase-5 stage at a time. Advance only after
   deterministic evidence satisfies that stage's acceptance criteria and the
   frozen required outcome.
7. Do not weaken, delete, skip or silently rewrite an existing passing test or
   gate to make a stage pass. If a contract intentionally changes, document
   the reason and add replacement coverage.
8. Fail closed on malformed iNES/NES 2.0 images, unsupported mappers,
   unsupported/undocumented opcodes, uncertain semantics, unmapped memory,
   unsupported PPU/APU/reset/NMI/IRQ behaviour and any unsupported hardware
   requirement. Never guess hardware behaviour.
9. Preserve `PROVEN` vs `CANDIDATE` classification. The Phase-5 claim ledger
   uses `PROVEN`, `BOUNDED`, `UNPROVEN`, `UNSUPPORTED` and `NOT TESTED`.
   Never promote bounded evidence to a universal claim.
10. ROM safety (strict): the private image
    `D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes` is classified
    `PRIVATE_LOCAL_COMPATIBILITY_FIXTURE`. Never commit, copy, embed, package
    or redistribute its bytes or any ROM-derived binary copy. Never add
    `*.nes`, `*.fds`, `*.unf`, `*.unif` or ROM-derived binary dumps to the
    repository, evidence, package, ZIP, fixture directory, Git object database
    or any public artifact. Record only source path, file size, cryptographic
    hashes, iNES metadata, mapper/mirroring/PRG/CHR inventory and derived
    control-flow/instruction/compatibility evidence that does not reproduce
    copyrighted program data unnecessarily. The private image can never be the
    public Phase-5 proof fixture.
11. The public Phase-5 proof fixture must be legally redistributable with
    recorded provenance, license, exact source revision, toolchain, build
    flags, ROM SHA-256, PRG/CHR sizes, mapper, mirroring and vectors. Prefer an
    original fixture authored for Phase 5 under Apache-2.0.
12. Never execute original untrusted guest machine code directly on the host
    merely to bypass missing translation semantics. Native execution must come
    from OpenRecomp-emitted host code.
13. Do not invent indirect branch targets, hardware behaviour, imports,
    runtime services, memory mappings, timing behaviour, interrupt behaviour or
    compatibility claims. Unknown behaviour remains explicit and fail-closed.
14. Generated code must not silently call arbitrary host functionality.
    External behaviour is mediated through the Phase-4 typed and versioned
    runtime service interfaces; unknown or unsupported services fail closed.
15. Keep architecture-neutral layers independent of platform-specific
    behaviour. Graphics/audio backends (RT64, SDL, Vulkan, Direct3D or any
    other particular renderer/audio system) must not become mandatory to the
    OpenRecomp core; backend-specific integrations are future adapters unless
    explicitly required and proven by this phase.
16. Queue freeze: at the P5-00 PASS boundary, rows `P5-01` .. `P5-99` are
    frozen exactly as recorded in `STAGE_QUEUE.md`. No silent renumbering,
    insertion, merging, splitting, scope change or relaxation of required
    outcomes. If a genuine technical dependency makes a frozen stage
    impossible as written, fail closed with
    `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` or
    `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`, capture the evidence, and require
    an explicit documented reconciliation before changing the frozen contract.
17. Every stage writes deterministic evidence under
    `.openrecomp-phase5/evidence/<STAGE>/` and updates `STATE.md`,
    `HANDOFF.md` and the stage-queue status. The official stage gate is run
    twice with byte-identical stdout on PASS.
18. The Phase-5 whole-regression gate (P5-90) must re-verify the frozen
    Phase-1/Phase-2/Phase-3/Phase-4 chain and all Phase-5 stage gates from the
    audited tree.
19. Record every material limitation. A Phase-5 PASS must not silently imply
    arbitrary 6502/NES/mapper/PPU/APU compatibility, cycle accuracy, hardware
    emulation, commercial-game compatibility, FDS compatibility or universal
    runtime completeness.

## Advancement rule

A stage advances only when its frozen required outcome, acceptance criteria,
negative/fail-closed coverage, relevant earlier-phase regressions, source
integrity, evidence, `STATE.md` and `HANDOFF.md` are complete and the official
gate has passed twice with deterministic output and empty stderr.

## Stop markers

- `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
- `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
- `REGRESSION_DETECTED`
- `PROVENANCE_VIOLATION`
