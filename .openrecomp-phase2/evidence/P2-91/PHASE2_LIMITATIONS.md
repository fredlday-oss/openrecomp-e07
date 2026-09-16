# PHASE2_LIMITATIONS

Authoritative Phase-2 limitations record (P2-91 closure; P2-99 terminal update).

This document states exactly what OpenRecomp Phase 2 proves and what remains
unproven or out of scope. Every claim identifier below is shared with
`PHASE2_CLAIM_MATRIX.md` and `PHASE2_EVIDENCE_INDEX.md`; classifications come
from the audited P2-90 claim table plus five closure claims added by P2-91.
P2-99 reclassified the `Phase-2 final end-to-end proof marker` claim from
`NOT_PROVEN` to `PROVEN` at its documented boundary when the terminal verdict
was issued; every other classification is unchanged.
All evidence is synthetic/original; no commercial ROM, BIOS, firmware, SDK
material or console-derived asset is used anywhere in Phase 2.

## Proven and bounded-proven claims (PROVEN / BOUNDED_PROVEN)

### PROVEN

- `architecture-neutral shared analysis pipeline` (`PROVEN`): static import and
  symbol isolation over the audited shared modules plus MIPS32 and NES6502 path
  exercises. Neutrality is proven only for the audited modules and the
  synthetic fixtures used by P2-30.
- `deterministic ProgramModel/CFG/function/call-graph/translation pipeline`
  (`PROVEN`): P2-01..P2-06 provide canonical serialization, stable fingerprints,
  byte-identical round trips and byte-identical repeated-run identities; P2-90
  re-audits every recorded identity on the frozen tree.
- `deterministic repeated execution` (`PROVEN`): repeated gate runs and repeated
  native executions are byte-identical for the audited fixtures.
- `generic runtime neutrality` (`PROVEN`): the audited generic runtime modules
  contain no platform leakage and both adapters share the generic contracts
  unchanged (P2-40).
- `provenance and legal-asset policy enforcement` (`PROVEN`): source-integrity,
  release content policy, console-image detection, secret scanning and
  public-safety scanning run as gates and reject violations; every release
  package produced by P2-50 passes the policy clean.
- `Phase-2 final end-to-end proof marker` (`PROVEN`): the P2-99 terminal verdict
  (`tools/test_phase2_final_verdict_v1.py`) issued
  `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` (P2-99) on the audited
  terminal tree after the terminal whole-project P2-90 regression re-run, the P2-91
  evidence-closure re-run, source integrity, the legal/content policy and the
  claim/limitation consistency passed. The claim is bounded to the exact
  synthetic-fixture pipeline statement in
  `.openrecomp-phase2/evidence/P2-99/final_claim_boundary.md`; it does not
  upgrade any of the unproven or out-of-scope claims below.

### BOUNDED_PROVEN

- `NES/6502 frontend integration` (`BOUNDED_PROVEN`): one synthetic 26-byte
  NES6502 region through P2-01..P2-06 (P2-20) and one bounded emitted subset
  (P2-21). This is not full 6502 support.
- `NES runtime bridge` (`BOUNDED_PROVEN`): a bounded synthetic NROM fixture with
  memory, input, frame and audio contracts through the generic ABI (P2-22).
  There is no PPU/APU implementation.
- `NES synthetic end-to-end native recompilation` (`BOUNDED_PROVEN`): one
  synthetic 59-instruction NROM fixture is recompiled and executed natively with
  a reference-equal observable (P2-23).
- `observable equivalence` (`BOUNDED_PROVEN`): declared observable sets for
  synthetic fixtures only; this is not general guest/host equivalence.
- `MIPS32 shared-path operation` (`BOUNDED_PROVEN`): synthetic 13/16/35/5/57
  instruction fixtures through the shared pipeline; no general MIPS32 support.
- `fail-closed unsupported-service behavior` (`BOUNDED_PROVEN`): unknown or
  unsupported runtime services, arity mismatches and unsupported sites fail
  closed in unit checks and in the audited native runs (P2-08, P2-13, P2-22,
  P2-40). The behavior is proven for the declared service surfaces, not for an
  unbounded service space.
- `reproducible native build` (`BOUNDED_PROVEN`): reproducible builds are
  demonstrated for the detected `clang-cl`/`lld-link` 22.1.8 toolchain on this
  host for the audited fixtures; other compilers or hosts may require different
  deterministic flags and are classified honestly.
- `reproducible release package` (`BOUNDED_PROVEN`): deterministic packaging is
  proven for the audited canonical ZIP path and three representative fixtures
  (P2-50).

## Unproven and out-of-scope claims (NOT_PROVEN / OUT_OF_SCOPE)

### NOT_PROVEN

- `arbitrary NES ROM compatibility` (`NOT_PROVEN`): no general NES ROM support
  is implemented or claimed.
- `commercial-game compatibility` (`NOT_PROVEN`): no commercial ROM or game is
  used or supported.
- `complete NES hardware compatibility` (`NOT_PROVEN`): no full PPU, APU or
  mapper implementation exists.
- `arbitrary mapper support` (`NOT_PROVEN`): only the synthetic mapper-0/NROM
  paths used by the fixtures are exercised; other mappers fail closed.
- `arbitrary MIPS32 binary compatibility` (`NOT_PROVEN`): only bounded synthetic
  fixtures are proven.
- `future architecture compatibility` (`NOT_PROVEN`): GB/GBC/SMS/RT64-like
  extension points are documented only; no such adapter is implemented.
- `production-ready universal console runtime` (`NOT_PROVEN`): the generic
  runtime is a bounded contract surface, not a complete emulator or product.

### OUT_OF_SCOPE

- `cycle accuracy` (`OUT_OF_SCOPE`): cycle-exact behavior is not modeled or
  claimed.
- `PS1/PS2/Xbox compatibility` (`OUT_OF_SCOPE`): not implemented and not
  claimed; the MIPS32 path is not a PS1/PS2 runtime.

## Additional explicit boundaries

- The P2-07 emitted subset covers only rule-proven operations; most runtime
  services remain outside the emitted subset, emitted functions are `void` with
  no argument/return ABI, and P2-21's `jsr`/`rts` stack effects are not modeled.
- P2-10..P2-14 call/return handling is structural; delay slots are not modeled
  as first-class semantics and general `$ra` dataflow is not recovered.
- Bounded dispatch target sets and runtime service identities are supplied by
  explicit evidence; the pipeline never recovers or guesses them by analysis.
- Toolchain-gated gates remain unexecutable on this host and are skipped, never
  counted as passes.
- `direct_call_graph` means direct calls only; unresolved `jalr`/tail calls are
  separate evidence.
- Host-path evidence hygiene is bounded by the nine frozen historical
  occurrences documented in `host_path_audit.md`; no new absolute host path is
  permitted in portable Phase-2 evidence or release artifacts.

## Final marker

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` was issued by the P2-99
terminal verdict on the audited terminal tree (evidence:
`.openrecomp-phase2/evidence/P2-99/RESULT.md`, capture and validation records in
`.openrecomp-phase2/evidence/P2-99/`). Before P2-99 the marker was
`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN`, reserved for the P2-99
final verdict per `.openrecomp-phase2/STAGE_QUEUE.md`; those records are
historical stage-time evidence. The P2-99 verdict adds no architecture feature
and broadens no compatibility claim: every boundary above remains in force.
