# PHASE2_CLAIM_MATRIX

Authoritative Phase-2 claim-to-evidence matrix (P2-91 closure; P2-99 terminal update).

Every major public-facing Phase-2 claim is mapped to the audited evidence that
supports it and to an explicit claim boundary. The eighteen claims below are the
audited P2-90 claim table unchanged; five closure claims were added by P2-91
(marked "P2-91 addition") so that
`deterministic ProgramModel/CFG/function/call-graph/translation pipeline`,
`fail-closed unsupported-service behavior`,
`provenance and legal-asset policy enforcement`, `arbitrary mapper support` and
`production-ready universal console runtime` are also explicitly bounded.
P2-99 reclassified `Phase-2 final end-to-end proof marker` to `PROVEN` when the
terminal verdict was issued; no other classification changed.
Classification vocabulary: `PROVEN`, `BOUNDED_PROVEN`, `NOT_PROVEN`,
`OUT_OF_SCOPE`.

| Claim | Classification | Supporting evidence | Claim boundary |
| --- | --- | --- | --- |
| `architecture-neutral shared analysis pipeline` | `PROVEN` | P2-30 static import/symbol isolation; MIPS32 path through P2-01..P2-07; NES6502 path through the same shared layers (P2-20) | Audited shared modules and synthetic fixtures only; not universal future-architecture integrability |
| `deterministic ProgramModel/CFG/function/call-graph/translation pipeline` | `PROVEN` | P2-01..P2-06 canonical serialization, fingerprints, round-trip and repeated-run identities; P2-90 re-audits all recorded identities | Determinism is proven for the audited modules and fixtures, not for arbitrary guest programs |
| `NES/6502 frontend integration` | `BOUNDED_PROVEN` | P2-20 structural bridge for one synthetic 26-byte region; P2-21 bounded emitted subset | One synthetic region and one bounded semantic subset; not full 6502 support |
| `NES runtime bridge` | `BOUNDED_PROVEN` | P2-22 memory/input/frame/audio contracts over the generic ABI; P2-23 end-to-end service routing | Bounded synthetic NROM fixture; no PPU/APU implementation |
| `NES synthetic end-to-end native recompilation` | `BOUNDED_PROVEN` | P2-23 recompiled 59-instruction NROM fixture with native execution | One synthetic fixture; not arbitrary NES content |
| `observable equivalence` | `BOUNDED_PROVEN` | Declared observable comparison for P2-10..P2-14, P2-21, P2-23, P2-40 fixtures | Declared observable sets for synthetic fixtures only; not general guest/host equivalence |
| `deterministic repeated execution` | `PROVEN` | Byte-identical repeated gate runs and repeated native executions across the audited stages | Audited fixtures and gates; not a claim about arbitrary workloads |
| `MIPS32 shared-path operation` | `BOUNDED_PROVEN` | P2-10..P2-14 synthetic fixtures through the shared pipeline | Synthetic 13/16/35/5/57-instruction fixtures; no general MIPS32 support |
| `generic runtime neutrality` | `PROVEN` | P2-40 isolation audit; both adapters share `RuntimeServiceTable.dispatch` unchanged | Audited generic modules and contract surfaces only |
| `fail-closed unsupported-service behavior` | `BOUNDED_PROVEN` | P2-08 unit checks; P2-13 and P2-40 native unsupported-service runs; P2-22 arity fail-closed | Proven for the declared service surfaces and audited native runs; not an unbounded service space |
| `reproducible native build` | `BOUNDED_PROVEN` | P2-09 and P2-50 independent `/Brepro` builds on the detected toolchain | Detected `clang-cl`/`lld-link` 22.1.8 on this host for the audited fixtures |
| `reproducible release package` | `BOUNDED_PROVEN` | P2-50 byte-identical release archives for three representative fixtures and policy-clean contents | Audited canonical ZIP path and representative fixtures only |
| `provenance and legal-asset policy enforcement` | `PROVEN` | Source-integrity manifest gate; P2-50 release content policy; P2-90 legal audit; console-image/secret/public-safety scans | Enforcement covers the tracked tree, Phase-2 evidence and release packages; not a general DRM or asset-provenance claim |
| `arbitrary NES ROM compatibility` | `NOT_PROVEN` | No general NES ROM parser/mapper/PPU/APU execution path exists | Not implemented, not claimed |
| `commercial-game compatibility` | `NOT_PROVEN` | No commercial ROM/game is used or supported | Not implemented, not claimed |
| `complete NES hardware compatibility` | `NOT_PROVEN` | Synthetic mapper-0 subset only (P2-22, P2-23) | No full PPU/APU/mapper implementation |
| `arbitrary mapper support` | `NOT_PROVEN` | Only synthetic NROM paths are exercised; unsupported mappers fail closed | Not implemented, not claimed |
| `cycle accuracy` | `OUT_OF_SCOPE` | No cycle modeling or cycle-exact evidence exists | Cycle-exact behavior is not modeled or claimed |
| `arbitrary MIPS32 binary compatibility` | `NOT_PROVEN` | Bounded synthetic MIPS32 fixtures only (P2-10..P2-14) | Not implemented, not claimed |
| `PS1/PS2/Xbox compatibility` | `OUT_OF_SCOPE` | The MIPS32 path is not a PS1/PS2 runtime; no R5900/PS2 code is present | Not implemented, not claimed |
| `future architecture compatibility` | `NOT_PROVEN` | GB/GBC/SMS/RT64-like extension points are documented only (P2-40) | No adapter implemented for those targets |
| `production-ready universal console runtime` | `NOT_PROVEN` | The generic runtime is a bounded contract surface with synthetic fixtures | Not a product, not a complete emulator, not universally applicable |
| `Phase-2 final end-to-end proof marker` | `PROVEN` | P2-99 terminal verdict (`tools/test_phase2_final_verdict_v1.py`): terminal whole-project P2-90 regression re-run (22 gates, 361 audit checks, 1990 gate checks), P2-91 closure re-run (882 checks), source integrity, legal/content policy and claim/limitation consistency all PASS | Issued only for the bounded synthetic-fixture pipeline claim recorded in `.openrecomp-phase2/evidence/P2-99/final_claim_boundary.md`; it does not imply arbitrary NES ROM, MIPS32, commercial-game, complete-console, cycle-accurate, PS1/PS2/Xbox, universal-console or future-architecture compatibility |

## Consistency rule

The eight `PROVEN`/`BOUNDED_PROVEN` foundation claims and the nine
`NOT_PROVEN`/`OUT_OF_SCOPE` boundaries above are restated with identical
identifiers in `PHASE2_LIMITATIONS.md`, and every stage named here is indexed in
`PHASE2_EVIDENCE_INDEX.md`. `tools/test_phase2_evidence_closure_v1.py` enforces
that the eighteen P2-90 claims keep their audited classification and that the
five P2-91 additions are present with the classifications above. The single
authorized terminal reclassification is `Phase-2 final end-to-end proof marker`
(`NOT_PROVEN` -> `PROVEN`), performed by P2-99 when the terminal verdict was
issued; the closure gate expects that value only when the validated P2-99
verdict evidence is present and fails closed on a `PROVEN` classification
without it.

## Final marker

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` was issued by P2-99 on the
audited terminal tree (evidence `.openrecomp-phase2/evidence/P2-99/RESULT.md`).
The pre-terminal record
`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN` remains in the frozen
P2-90/P2-91 stage evidence as a historical stage-time statement; P2-99 adds no
architecture feature and broadens no compatibility claim.

Verification note (historical, pre-terminal): before P2-99 the only literal
final-marker-with-`PASS` occurrences outside negation contexts in the tracked
control plane were the objective/success-marker definitions in
`.openrecomp-phase2/SCOPE.md` and `.openrecomp-phase2/STAGE_QUEUE.md`; they
define the reserved outcome and did not claim achievement. After P2-99 the
authorized claim lives in `.openrecomp-phase2/evidence/P2-99/`, the terminal
control-plane markers and the terminal addenda of this document, the
limitations record and the evidence index; the P2-91 closure gate rejects any
other un-negated final-marker pass occurrence.
