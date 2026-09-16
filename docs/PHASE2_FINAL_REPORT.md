# Phase 2 final report — bounded local verdict

**Recorded 16 September 2026.** The Phase 2 end-to-end recompilation proof reached `PASS` in the audited local OpenRecomp worktree. This report records that result and its limits. The Phase 2 implementation and full evidence have **not yet been published to this GitHub repository**, so the result is not currently reproducible from a public clean clone.

## Exact boundary

- Final implementation/evidence closure commit: `b935699991bdcbea518e5f6fbbd69ecb45bc12cf`.
- Local frozen tag `openrecomp-phase2-pass` resolves to `01b1d7cba8c931fca95d041389cfb1902b7c89fe`. The tag and commits are local and are not public GitHub refs as of this report.
- The local Phase 1 baseline tag `openrecomp-phase1-pass` resolves to `46c2f971e1a42cf49bd936bad94697b81bf31002`.
- P2-99 terminal marker: `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`.

The P2-99 verdict is recorded in the local `.openrecomp-phase2/evidence/P2-99/RESULT.md` and `RESULT.json`. Its exact claim is in `.openrecomp-phase2/evidence/P2-99/final_claim_boundary.md`. These paths identify local evidence; they are not links to files on public `main`.

## What passed

P2-99 closed an evidence chain spanning program modelling, control-flow graphs, function and direct-call discovery, translation units, bounded indirect-control-flow classification, host emission, a generic runtime ABI, deterministic builds, synthetic MIPS32 and NES6502 execution paths, cross-architecture and runtime audits, and reproducible packaging.

The final claim is limited to **supported synthetic guest programs** on the audited NES6502 and MIPS32 paths: decoding, program modelling, control-flow recovery, translation, native host compilation, generic runtime execution, deterministic comparison of declared observables, and packaging. It does not claim the same result for arbitrary binaries.

| Local terminal check | Recorded result |
| --- | --- |
| P2-99 final verdict | `OPENRECOMP_P2_99=PASS`; 202 verdict checks |
| P2-90 whole-project regression | `PASS`; 361 audit checks, 22 gates, 1,990 gate checks, zero failures |
| P2-91 evidence closure | `PASS`; 882 checks |
| Source integrity | `PASS`; 134 manifest entries |
| P2-99 repeated stdout | Byte-identical across the recorded full-regression and verify-only runs |

The build reproducibility evidence is bounded to the audited representative fixtures and the detected local `clang-cl`/`lld-link` 22.1.8 toolchain. It does not establish reproducible builds on other hosts or compilers.

## Limits

The verdict does not establish arbitrary NES ROM or MIPS32 executable compatibility, commercial-game compatibility, full NES hardware or mapper support, cycle accuracy, PS1/PS2/Xbox compatibility, a production-ready universal runtime, or future-architecture compatibility. The local `PHASE2_LIMITATIONS.md` and `PHASE2_CLAIM_MATRIX.md` retain these as `NOT_PROVEN` or `OUT_OF_SCOPE`. Phase 3's real-ELF/CoreMark path is active and has **no final PASS**.

Phase 2 used synthetic/original fixtures for its semantics and equivalence proof. The local checkout also contains historical host-path evidence and a separate Phase 1 inventory of external local assets. Those records need a rights and privacy review before any source/evidence branch is made public.

## Public release status and reproduction

The latest tagged public release remains **v0.2.0**. This documentation update does not ship the Phase 2 implementation, publish the local tag, issue v0.3.0, or establish public clean-clone reproducibility. The local freeze intentionally keeps 28 verification-context files outside Git tracking, including one test module; publishing the tag alone would therefore not reproduce the recorded local verification environment.

A public Phase 2 release needs a reviewed rights-safe source/evidence export, the required verification context represented safely, a fresh-clone rerun of the bounded gates, and a tag on the exact reviewed public commit. Until then, cite this as **“Phase 2 PASS in an audited local worktree; public reproduction pending.”**
