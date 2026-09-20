# OpenRecomp Phase 9 Control Policy

Phase 9 starts from the frozen Phase-8 terminal boundary on branch
`phase8/mips32-end-to-end-native-v1` at commit
`61136fc37cf0810e64241addd8f57a91872bc0af`, tree
`f9262497b82fe0027c3b23432ba7bd8cbccdf433`, whose P8-99 terminal verdict is
`OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=PASS` for the exact bounded
audited Phase-8 fixture and behaviour only. Phase 9 adds no Phase-8 claim and
never weakens the Phase-8 evidence chain.

1. Work as one agent and on one serial implementation frontier at a time.
   Parallel work is allowed only while read-only/non-mutating (reference-vector
   generation, test-case design, evidence review, documentation drafting,
   manifest preparation, static analysis of frozen artifacts).
2. Freeze rows `P9-01` through `P9-99` at the P9-00 `PASS` boundary. A later
   queue change must fail closed, record the forcing technical dependency, and
   stop the phase instead of silently adapting.
3. Never rewrite, amend, rebase, squash, force-push, delete, or otherwise alter
   any frozen Phase-1 through Phase-8 commit, tag, evidence file, verdict,
   control file, source manifest, or gate. The Phase-8 terminal commit above is
   the Phase-9 baseline authority. No Phase-8 terminal tag exists; none is
   fabricated or retroactively created.
4. The historical Phase-6 tag `openrecomp-phase6-pass` did not exist
   (`ABSENT_RECONCILED`); the Phase-7 annotated tag `openrecomp-phase7-pass`
   and its commit/tree identity are frozen. Do not fabricate, move or create
   any historical tag.
5. Phase-9 work is additive under `.openrecomp-phase9/` plus new
   `tools/test_phase9_*` gates, except where real Phase-9 evidence demonstrates
   a gap in a shared layer. A shared-layer change must be additive,
   architecture-neutral where possible, regression-checked against its direct
   dependency gates, and recorded in the stage evidence.
6. Preserve `PROVEN` versus `CANDIDATE` and the claim-ledger vocabulary
   `PROVEN`, `BOUNDED`, `UNPROVEN`, `UNSUPPORTED`, `NOT TESTED`.
7. Fail closed and never guess instruction semantics, delay-slot behavior, ABI
   behavior, indirect targets, memory aliases, KSEG mapping, exception
   behavior, BIOS service identity, GPU command behavior or runtime services.
   `NOT_PROVEN` / `UNSUPPORTED` / `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` are
   valid outcomes.
8. Work one evidence-bounded stage at a time. Each official stage gate runs
   twice; `PASS` requires exit 0, empty stderr, byte-identical stdout, no
   `FAIL:` line, and committed deterministic evidence.
9. Do not run the full historical Phase-1..Phase-8 regression after every
   stage. Run the stage's own gate, its direct dependency gates, fast
   source-integrity/provenance checks, and any regression made necessary by
   changed code. The expensive whole-project regression is reserved for P9-90,
   P9-91 and P9-99 (see `ACCELERATION_POLICY.md`).
10. Compilation is not semantic evidence. Native execution requires an
    incrementally independent reference comparison before equivalence is
    claimed. A reference that merely calls the same translated semantics is not
    independent.
11. Use only pinned, legally redistributable inputs with recorded provenance
    and licence. Never commit toolchain distributions, upstream source trees,
    generated executables or native build products, proprietary binaries,
    ROMs, firmware, BIOS images, disc images, keys, SDK material,
    console-derived assets, or unknown precompiled MIPS binaries.
12. Private or commercial binaries are never a public `PASS` criterion and are
    never committed, packaged, copied or byte-referenced into evidence. For the
    private Hercules fixture only derived, non-reconstructive metadata
    (hashes, sizes, offsets, entry/load fields, classifications, counts,
    diagnostics) may be recorded. No payload bytes, code excerpts, strings or
    reconstructive derived data.
13. Never execute original MIPS32 machine code at runtime. Native execution
    comes only from generated host code; guest images are inert data.
14. Record the exact compiler, linker, flags, source revision, hashes, image
    inventory, executable frontier and observable contract. Host paths,
    timestamps, UUIDs and process identities are forbidden in committed
    evidence.
15. Preserve every permanent Phase-9 non-claim. No stage may promote general
    PS1 compatibility, Hercules playability, BIOS emulation, GPU/SPU/CD-ROM
    hardware emulation, PS2, commercial-game compatibility, cycle accuracy or
    any claim beyond the audited evidence. The permanent markers
    `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` and
    `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` are never promoted at
    any stage, including P9-99.
16. Never weaken, delete, skip, or silently redefine an existing passing test.
    If a contract intentionally changes, record the reason and add replacement
    coverage.
17. A completed stage updates `STATE.md`, `HANDOFF.md`, `STAGE_QUEUE.md`, the
    Phase-9 source manifest, and `.openrecomp-phase9/evidence/<STAGE>/`.
18. Commit only completed `PASS` boundaries with a stage-specific message. Do
    not commit failed or partial stages. Do not push unless the user explicitly
    instructs it.

## Stop markers

- `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
- `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
- `REGRESSION_DETECTED`
- `PROVENANCE_VIOLATION`
- `QUEUE_RECONCILIATION_REQUIRED`
