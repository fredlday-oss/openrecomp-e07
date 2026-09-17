# OpenRecomp Phase 4 Control Policy

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
   The frozen Phase-1, Phase-2 and Phase-3 histories and tags are immutable.
3. Commit only the completed stage boundary after a deterministic PASS, as
   instructed by the Phase-4 program. Do not push unless explicitly requested.
4. Preserve the frozen Phase-3 boundary: annotated tag `openrecomp-phase3-pass`
   (object `ac31524504b1b5cc63aabcfd5132a3eb4275e8e9`) resolves to commit
   `e16e4b29b90f379615f1af97e47747cd1d531796`, tree
   `a940f0d84a32adaf191f7ff2bebfb24cc855cde0`. Tags
   `openrecomp-phase2-pass` = `01b1d7cba8c931fca95d041389cfb1902b7c89fe` and
   `openrecomp-phase1-pass` = `46c2f971e1a42cf49bd936bad94697b81bf31002`
   remain earlier reference boundaries. Never rewrite, amend, squash, rebase,
   modify or otherwise mutate the frozen Phase-3 history or tag.
5. Do not modify frozen Phase-3 evidence, gates, control plane or the P3-99
   verdict, and do not modify frozen Phase-1/Phase-2 evidence, gates or
   verdicts. Re-running a frozen gate may refresh its own deterministic
   evidence sidecars in the working tree; that is a re-run artifact, not a
   history change, and must be recorded. If Phase 4 exposes a defect in an
   earlier implementation layer, document it explicitly, fix the underlying
   source on the Phase-4 branch, rerun every affected proof/regression gate,
   and do not rewrite the historical tags.
6. Work one evidence-bounded Phase-4 stage at a time. Advance only after
   deterministic evidence satisfies that stage's acceptance criteria and the
   frozen required outcome.
7. Do not weaken, delete, skip or silently rewrite an existing passing test to
   make a stage pass. If a contract intentionally changes, document the reason
   and add replacement coverage.
8. Fail closed on malformed ELF/IR/input and on uncertain semantics, ABI,
   memory behavior, control flow, runtime services, timing, exception or
   platform behavior. Invalid or unmapped guest accesses fail closed.
9. Preserve `PROVEN` vs `CANDIDATE` classification. The Phase-4 claim ledger
   uses `PROVEN`, `BOUNDED`, `UNPROVEN`, `UNSUPPORTED` and `NOT TESTED`.
   Never promote bounded evidence to a universal claim.
10. Never commit proprietary ROMs, ISOs, BIOS, firmware, keys, SDK content,
    console assets, or copied copyrighted code/data. Fixtures must be
    synthetic/original or openly licensed, with recorded provenance, license,
    exact source/toolchain/build flags and hashes.
11. Never execute original untrusted guest machine code directly on the host
    merely to bypass missing translation semantics.
12. Do not invent indirect branch targets, hardware behavior, imports, runtime
    services, memory mappings, timing behavior, exception behavior or
    compatibility claims. Unknown behavior remains explicit and fail-closed.
13. Generated code must not silently call arbitrary host functionality.
    External behavior is mediated through explicit typed and versioned runtime
    service interfaces; unknown or unsupported services fail closed.
14. Keep architecture-neutral layers independent of platform-specific
    behavior. Graphics/audio backends (RT64, SDL, Vulkan, Direct3D or any other
    particular renderer/audio system) must not become mandatory to the
    OpenRecomp core; backend-specific integrations are future adapters unless
    explicitly required and proven by this phase.
15. Queue freeze: at the P4-00 PASS boundary, rows `P4-01` .. `P4-99` are
    frozen exactly as recorded in `STAGE_QUEUE.md`. No silent renumbering,
    insertion, merging, splitting, scope change or relaxation of required
    outcomes. If a genuine technical dependency makes a frozen stage
    impossible as written, fail closed with
    `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` or
    `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`, capture the evidence, and require
    an explicit documented reconciliation before changing the frozen contract.
16. Every stage writes deterministic evidence under
    `.openrecomp-phase4/evidence/<STAGE>/` and updates `STATE.md`,
    `HANDOFF.md` and the stage-queue status. The official stage gate is run
    twice with byte-identical stdout on PASS.
17. Record every material limitation. A Phase-4 PASS must not silently imply
    arbitrary binary compatibility, arbitrary MIPS32 compatibility,
    PS1/PS2/N64/PSP or any console compatibility, game or commercial-title
    compatibility, cycle accuracy, hardware emulation or universal runtime
    completeness.

## Advancement rule

A stage advances only when its frozen required outcome, acceptance criteria,
negative/fail-closed coverage, relevant Phase-1/Phase-2/Phase-3 regressions,
source integrity, evidence, `STATE.md` and `HANDOFF.md` are complete and the
official gate has passed twice with deterministic output and empty stderr.

## Stop markers

- `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
- `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
- `REGRESSION_DETECTED`
- `PROVENANCE_VIOLATION`
