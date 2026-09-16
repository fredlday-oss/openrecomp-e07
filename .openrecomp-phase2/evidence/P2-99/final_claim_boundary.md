# P2-99 final claim boundary

This file records the exact bounded claim issued by the P2-99 terminal verdict
and the explicit non-claims that remain in force. It is validated by
`tools/test_phase2_final_verdict_v1.py` (checks `claims:bounded-final-claim-text`,
`claims:exclusions-listed`, `claims:final-claim-boundary-p2-99`).

## Issued bounded claim

OpenRecomp has demonstrated an architecture-neutral static-recompilation pipeline capable of taking supported synthetic guest programs through decoding, program modelling, control-flow recovery, translation, native host compilation, generic runtime execution, deterministic observable equivalence, and reproducible packaging across the audited NES6502 and MIPS32 paths.

Scope of the claim:

- "supported synthetic guest programs" means the audited synthetic/original
  fixtures of P2-10..P2-14 (MIPS32) and P2-20..P2-23 (NES6502) plus the bounded
  P2-30/P2-40/P2-50 representative fixtures; it is not a statement about
  arbitrary guest programs.
- "architecture-neutral" is proven only for the audited shared Phase-2 modules
  (P2-30 static isolation and path exercises; P2-40 generic-runtime neutrality).
- "deterministic observable equivalence" means the declared observable sets of
  the audited fixtures compared against independent references; it is not
  general guest/host equivalence.
- "reproducible packaging" is proven only for the detected `clang-cl`/`lld-link`
  22.1.8 toolchain on this host and the audited canonical ZIP packaging path.
- Every claim is bounded by
  `.openrecomp-phase2/evidence/P2-91/PHASE2_LIMITATIONS.md` and
  `.openrecomp-phase2/evidence/P2-91/PHASE2_CLAIM_MATRIX.md`.

## Explicit non-claims (remain NOT_PROVEN / OUT_OF_SCOPE)

- `arbitrary NES ROM compatibility` (`NOT_PROVEN`): no general NES ROM support.
- `arbitrary MIPS32 binary compatibility` (`NOT_PROVEN`): bounded synthetic
  fixtures only.
- `commercial-game compatibility` (`NOT_PROVEN`): no commercial ROM or game is
  used or supported.
- `complete NES hardware compatibility` (`NOT_PROVEN`): no full PPU, APU or
  mapper implementation.
- `cycle accuracy` (`OUT_OF_SCOPE`): cycle-exact behavior is not modeled.
- `PS1/PS2/Xbox compatibility` (`OUT_OF_SCOPE`): the MIPS32 path is not a
  PS1/PS2 runtime.
- `production-ready universal console runtime` (`NOT_PROVEN`): the generic
  runtime is a bounded contract surface, not a product or complete emulator.
- `future architecture compatibility` (`NOT_PROVEN`): GB/GBC/SMS/RT64-like
  extension points are documented only; no adapter is implemented.

The verdict further does not imply universal-console support or any hardware
emulation beyond the documented synthetic fixtures.

## Verdict authority

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` is issued by the P2-99 terminal
gate only while the P2-99 verdict evidence exists, declares PASS, pins the live
P2-99 gate by SHA-256 and the control plane states the terminal markers; any
other artifact claiming that marker fails the P2-90 and P2-91 gates.
