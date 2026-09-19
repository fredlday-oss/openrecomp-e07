# OpenRecomp Phase 7 Control Policy

Phase 7 starts from the frozen Phase-6 terminal boundary
(`OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS`, bounded audited public MMC1
claim only) at commit
`1643817d43196c43155805249137e4b4e4a21eb1`, tree
`cda3f535be43dc6f3d4b457d11d356ae39ea34af`, on branch
`phase7/nes-translation-frontier-v1`.

1. One implementation frontier at a time. Do not create subagents, background
   agents, parallel implementation branches or competing solutions. Only one
   implementation stage may be `ACTIVE` at a time. Read-only analysis,
   independent verification, test/vector generation, evidence indexing,
   manifest verification and regression preparation may proceed in parallel
   only when they cannot mutate the active frontier.
2. Freeze the complete Phase-7 queue at P7-00: rows `P7-01` .. `P7-99` are
   frozen exactly as recorded in `STAGE_QUEUE.md`, effective before any P7-01
   implementation work. No silent renumbering, insertion, merging, splitting,
   scope change or relaxation of required outcomes.
3. Do not use destructive Git commands such as `reset --hard`, `clean -fd`,
   force checkout, force push, rebase, amend, squash or any history rewrite.
   The frozen Phase-1, Phase-2, Phase-3, Phase-4, Phase-5 and Phase-6
   histories, tags, evidence, verdicts and control planes are immutable. In
   particular, no Phase-1..Phase-6 tag, commit, evidence file or verdict may be
   modified, rewritten, amended, squashed, rebased or deleted.
4. Preserve the exact Phase-6 terminal boundary. The mission baseline names an
   annotated tag `openrecomp-phase6-pass`; the frozen Phase-6 P6-99 record
   states that the Phase-6 control policy required and created no terminal tag,
   so that tag is absent. Phase 7 records this reconciliation as
   `ABSENT_RECONCILED` without fabricating a frozen artifact: the
   authoritative Phase-6 baseline is commit
   `1643817d43196c43155805249137e4b4e4a21eb1`, tree
   `cda3f535be43dc6f3d4b457d11d356ae39ea34af`, with terminal marker
   `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS` for the bounded audited public
   MMC1 claim only and
   `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` permanent. No tag
   is created for Phase 6 retroactively unless a later frozen-contract
   reconciliation explicitly authorizes it.
5. Do not modify frozen Phase-1/Phase-2/Phase-3/Phase-4/Phase-5/Phase-6
   evidence, gates, control planes or verdicts and do not modify any file
   listed in the frozen root/Phase-3/Phase-4/Phase-5/Phase-6 manifests.
   Phase-7 work is additive under `.openrecomp-phase7/` plus new
   `tools/test_phase7_*` gates. Re-running a frozen gate may refresh its own
   deterministic evidence sidecar in the working tree; that is a re-run
   artifact, not a history change, and must be recorded.
6. Work one evidence-bounded Phase-7 stage at a time. Advance only after
   deterministic evidence satisfies that stage's acceptance criteria and the
   frozen required outcome, and every official stage gate has been run twice.
7. PASS requires byte-identical stdout across the two official runs and empty
   stderr on both, with exit 0 and no `FAIL:` lines. Commit only after a
   deterministic stage PASS, and only the completed stage boundary. Do not
   push unless explicitly instructed.
8. Never weaken, delete, skip or silently rewrite an existing passing test or
   gate to obtain PASS. If a contract intentionally changes, document the
   reason and add replacement coverage.
9. Fail closed on malformed input, malformed iNES/NES 2.0 images, unsupported
   mappers, unsupported MMC1 variants/board wiring, unsupported/undocumented
   opcodes without proven semantics, uncertain semantics, unmapped memory,
   unsupported platform behaviour and any unsupported hardware requirement.
   Unknown control flow, indirect targets, bank provenance or hardware
   behaviour fails closed; it is never guessed.
10. Do not execute original guest 6502 code directly on the host. Native
    execution must come only from OpenRecomp-generated host code.
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
    public Phase-7 proof fixture.
12. Every public Phase-7 proof fixture must be legally redistributable with
    recorded provenance, license, exact source revision, toolchain, build
    flags, ROM SHA-256, PRG/CHR sizes, mapper, mirroring, bank configuration
    and vectors. Phase-7 fixtures are original programs authored for Phase 7
    under Apache-2.0.
13. Preserve `PROVEN` vs `CANDIDATE` classification. The Phase-7 claim ledger
    uses `PROVEN`, `BOUNDED`, `UNPROVEN`, `UNSUPPORTED` and `NOT TESTED`.
    Never promote bounded evidence to a universal claim. Indirect jump targets
    carry explicit `RESOLVED_EXACT`, `RESOLVED_FINITE_SET`, `UNRESOLVED` or
    `IMPOSSIBLE` states and are never fabricated.
14. Do not invent indirect branch targets, MMC1 bank sequences, code/data
    boundaries, register behaviour, hardware behaviour, imports, runtime
    services, memory mappings, timing behaviour, interrupt behaviour or
    compatibility claims. Unknown behaviour remains explicit and fail-closed.
15. Generated code must not silently call arbitrary host functionality.
    External behaviour is mediated through the frozen Phase-4 typed and
    versioned runtime service interfaces; unknown or unsupported services fail
    closed.
16. Keep architecture-neutral layers independent of platform-specific
    behaviour. Banked-code identity and MMC1-specific behaviour live behind
    explicit Phase-7 adapter boundaries. Graphics/audio backends must not
    become mandatory to the OpenRecomp core.
17. Every stage writes deterministic evidence under
    `.openrecomp-phase7/evidence/<STAGE>/` and automatically updates
    `STATE.md`, `HANDOFF.md`, `STAGE_QUEUE.md`, `SOURCE_SHA256SUMS.txt` and
    the stage `RESULT.md` on PASS.
18. The Phase-7 whole-regression gate (P7-90) must re-verify the frozen
    Phase-1/Phase-2/Phase-3/Phase-4/Phase-5/Phase-6 chain and all Phase-7 stage
    gates from the audited tree, preserving frozen historical evidence and
    requiring deterministic outputs.
19. Record every material limitation. A Phase-7 PASS must not silently imply:
    general NES compatibility; commercial-game compatibility; TMNT
    playability; all undocumented 6502 opcodes; all indirect-control-flow
    recovery; arbitrary bank-switched binaries; cycle accuracy; full PPU/APU
    accuracy; or arbitrary 6502 compatibility. Retain
    `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` and
    `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN` always (the latter denotes
    the private TMNT playability status; the spelling is exact as issued by the
    Phase-7 mission).
20. Automatic commit applies to each completed PASS boundary only. Never
    commit a failed, blocked or partial stage. Never push.

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
