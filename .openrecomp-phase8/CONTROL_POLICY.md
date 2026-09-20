# OpenRecomp Phase 8 Control Policy

Phase 8 starts from the immutable annotated tag `openrecomp-phase7-pass`
(tag object `b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800`) at the frozen Phase-7
terminal commit `2917aa6549ab975cffdeb50120514c1723f7e493`, tree
`59529c130d759ceb1ca9e6c65a510fa373656b01`, on branch
`phase8/mips32-end-to-end-native-v1`.

1. Work as one agent and on one serial implementation frontier at a time.
   Parallel work is allowed only while read-only/non-mutating (reference-vector
   generation, test-case design, evidence review, documentation drafting,
   manifest preparation, static analysis of frozen artifacts).
2. Freeze rows `P8-01` through `P8-99` at the P8-00 `PASS` boundary. A later
   queue change must fail closed, record the forcing technical dependency, and
   stop the phase instead of silently adapting.
3. Never rewrite, amend, rebase, squash, force-push, delete, or otherwise alter
   any frozen Phase-1 through Phase-7 commit, tag, evidence file, verdict,
   control file, source manifest, or gate. `openrecomp-phase7-pass` and
   `2917aa6549ab975cffdeb50120514c1723f7e493` are the Phase-7 authority for
   this phase. The separately tagged `openrecomp-phase7-pass-v2` hardening line
   and the `phase7/hardening-v2` branch are outside this phase's baseline and
   are neither used nor modified.
4. The historical Phase-6 tag `openrecomp-phase6-pass` did not exist. The
   frozen Phase-7 record states `BASELINE_TAG_STATUS=ABSENT_RECONCILED`. Do not
   fabricate or retroactively create a Phase-6 tag.
5. Phase-8 work is additive under `.openrecomp-phase8/` plus new
   `tools/test_phase8_*` gates, except where real Phase-8 evidence demonstrates
   a gap in a shared layer. A shared-layer change must be additive,
   architecture-neutral where possible, regression-checked against its direct
   dependency gates, and recorded in the stage evidence.
6. Preserve `PROVEN` versus `CANDIDATE` and the claim-ledger vocabulary
   `PROVEN`, `BOUNDED`, `UNPROVEN`, `UNSUPPORTED`, `NOT TESTED`.
7. Fail closed and never guess instruction semantics, delay-slot behavior, ABI
   behavior, indirect targets, memory aliases, exception behavior, ELF
   container features, or runtime services. `NOT_PROVEN` / `UNSUPPORTED` /
   `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` are valid outcomes.
8. Work one evidence-bounded stage at a time. Each official stage gate runs
   twice; `PASS` requires exit 0, empty stderr, byte-identical stdout, no
   `FAIL:` line, and committed deterministic evidence.
9. Do not run the full historical Phase-1..Phase-7 regression after every
   stage. Run the stage's own gate, its direct dependency gates, fast
   source-integrity/provenance checks, and any regression made necessary by
   changed code. The expensive whole-project regression is reserved for P8-90,
   P8-91, and P8-99 (see `ACCELERATION_POLICY.md`).
10. Compilation is not semantic evidence. Native execution requires an
    incrementally independent reference comparison before equivalence is
    claimed. A reference that merely calls the same translated semantics is not
    independent.
11. Use only pinned, legally redistributable inputs with recorded provenance
    and licence. Never commit toolchain distributions, upstream source trees,
    generated ELF or native build products, proprietary binaries, ROMs,
    firmware, BIOS images, keys, SDK material, console-derived assets, or
    unknown precompiled MIPS binaries.
12. Private or commercial binaries are never a `PASS` criterion and are never
    committed, packaged, or byte-copied into evidence.
13. Never execute original MIPS32 machine code at runtime. Native execution
    comes only from generated host code.
14. Record the exact compiler, linker, flags, source revision, hashes, ELF
    inventory, executable frontier, and observable contract. Host paths,
    timestamps, UUIDs, and process identities are forbidden in committed
    evidence.
15. Preserve every permanent Phase-8 non-claim. No stage may promote arbitrary
    MIPS32, general MIPS32 compatibility, complete ISA or o32 ABI support,
    arbitrary Linux binaries, dynamic linking, exceptions, floating point,
    coprocessors, privileged execution, arbitrary indirect-control-flow
    recovery, PS1, PS2, game, or commercial-binary compatibility.
16. Never weaken, delete, skip, or silently redefine an existing passing test.
    If a contract intentionally changes, record the reason and add replacement
    coverage.
17. A completed stage updates `STATE.md`, `HANDOFF.md`, `STAGE_QUEUE.md`, the
    Phase-8 source manifest, and `.openrecomp-phase8/evidence/<STAGE>/`.
18. Commit only completed `PASS` boundaries with a stage-specific message. Do
    not commit failed or partial stages. Do not push unless the user explicitly
    instructs it.

## Stop markers

- `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
- `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
- `REGRESSION_DETECTED`
- `PROVENANCE_VIOLATION`
- `QUEUE_RECONCILIATION_REQUIRED`
