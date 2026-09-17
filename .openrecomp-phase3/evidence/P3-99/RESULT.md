# P3-99 result (FINAL VERDICT: PASS for the bounded audited claim)

Stage: `P3-99` final verdict (frozen queue row, terminal stage).
Gate: `tools/test_phase3_final_verdict_v1.py` (46 checks).
Evidence: `.openrecomp-phase3/evidence/P3-99/`.

Markers issued:

- Stage marker: `OPENRECOMP_P3_99=PASS`
- Gate marker: `OPENRECOMP_PHASE3_FINAL_VERDICT_V1=PASS tests=46`
- Terminal marker: `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=PASS`
  (issued for the bounded audited claim only)

## Verdict

The bounded Phase-3 claim is proven on the audited tree: a legally clean,
compiler-produced CoreMark MIPS32 `-O1` ELF is statically recompiled to a
native host executable whose deterministic observable is identical to an
independently written MIPS32 reference execution over the full run, with a
byte-reproducible package and whole-regression coherence.

Explicitly **not** proven and not claimed: arbitrary MIPS32 ELF support, PS1
compatibility, PS2 compatibility, game or commercial binary compatibility,
cycle accuracy or console hardware emulation, self-modifying code, the `-O2`
stress profile and runtime equivalence beyond the audited deterministic
observable. `COREMARK_STATUS=NOT_PROVEN`: CoreMark is not a supported target.

## Preconditions verified by this gate

- source integrity: root manifest `76f77bbc...` (134 entries) and the Phase-3
  manifest (24 entries) fully verified;
- frozen chain: `openrecomp-phase2-pass` annotated tag = `01b1d7cb...`, tree
  `6513eefa...`; `openrecomp-phase1-pass` = `46c2f971...`; the branch descends
  from the Phase-2 boundary; P2-99 result `880d2596...` and P2-90 capture
  `74e9eada...` re-hash exactly; fixture `16a0a0aa...` (31184 bytes);
- control plane: `CURRENT_STAGE=P3-99`, `LAST_PASSED_STAGE=P3-91`, all stage
  ledger rows `P3-00 .. P3-91` `PASS`, terminal marker reserved before this
  stage;
- completed audits: P3-10 package `cf9ab795...` / fingerprint `9050a117...` /
  287 entries; P3-90 whole-regression `13/13` passed; P3-91 index (346 files)
  and claim record (8 limitations, 9 proven statements, 8 unproven areas);
- equivalence: P3-08 native and P3-09 reference observables identical in all
  ten fields (`exit_status=0`, `steps=394997250`, `pc=0x00004564`,
  `hi=0x0000000d`, `lo=0`, `uart_bytes=499`,
  `state_fnv1a64=0x78651c29dd149ab1`, no failure), with CoreMark's published
  validation CRCs in the UART stream;
- fresh whole regression: all thirteen gates (P2-99, P3-00 .. P3-09, Phase-1
  host gates, public safety) exit 0 with empty stderr and stdout
  byte-identical (LF-normalized) to their recorded captures.

## Verification

- 46 gate checks; official runs: two consecutive invocations byte-identical
  (raw sha256
  `953ec70c312c7203022ba98f763aabf270409e2f39a9a7fa2ac90d887ae087bc`, 2498
  bytes, empty stderr, exit 0); boundary regressions (P2-99, P3-00, Phase-1
  host gates, public safety) re-passed unchanged.
- On any failure this gate emits `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`
  and fails closed; the PASS above was issued only after every precondition
  passed.

## Claim boundary

The terminal marker is issued `PASS` for the bounded audited claim on this
tree, with the limitations recorded in P3-91. It is not a general emulator,
recompiler, platform or game compatibility claim, and the earlier stage gates
keep emitting the reserved `NOT_PROVEN` terminal string as frozen evidence of
their boundary states.
