# P8-99 result: final bounded verdict

Status: `PASS` (92 checks)

Markers issued:

- `OPENRECOMP_P8_99=PASS`
- `OPENRECOMP_PHASE8_FINAL_VERDICT_V1=PASS tests=92`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=PASS` (exact bounded
  audited public fixture and behaviour only)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_final_verdict_v1.py`.

## Audit performed

- frozen Phase-7 baseline annotated tag object `b07e0f69...` -> commit
  `2917aa65...` -> tree `59529c13...` re-verified;
- every required stage record present with its gate marker and byte-identical
  two-run evidence: `P8-00` (68), `P8-01` (89), `P8-02` (43), `P8-03` (52),
  `P8-04` (30), `P8-05` (36), `P8-06` (25), `P8-07` (24), `P8-08` (26),
  `P8-09` (24), `P8-10` (15), `P8-11` (47), `P8-12` (130), `P8-90` (215),
  `P8-91` (27);
- exact frozen public fixture provenance: SHA-256 `0a90f477...`, 12904 bytes,
  upstream tiny-AES-c commit `23856752...` with recorded file hashes and
  Unlicense, recorded Zig 0.13.0 executable identity, ELF identity
  (ELF32 LE `EM_MIPS` `ET_EXEC`, O32/MIPS32/non-PIC, entry `0x2490`),
  upstream tree untracked/ignored;
- native/reference agreement: `excluded_observables` empty, every compared
  field equal, the audited observable record (`exit_status=0x00000000`,
  register digest `0x7ee0f4a187050726`, memory digest `0x231c4a49e79c5e56`,
  transcript 33 bytes / digest `0xca6dcb87f8ac9814`, reads 1136, writes 681,
  host calls 33, denied 0) identical between the native and reference paths
  and to the committed P8-08/P8-12 records; executable `fb98c8a6...`;
- evidence closure and whole-regression records: P8-12 implementation delta
  `none`, P8-90 15 Phase-7 + 13 Phase-8 gates and 1463 re-verified
  stage-gate tests, P8-91 index and claim ledger;
- public-safety: the P8-91 gate (which verifies no private identity, path or
  ROM/native binary material in committed Phase-8 material) re-passes live;
- scope guards: `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`
  present in the scope, state and queue, with the arbitrary-MIPS32,
  dynamic-linking and PS1/PS2 non-claims.

## Official runs

Command `python tools/test_phase8_final_verdict_v1.py`, exit 0, empty stderr,
both runs byte-identical: stdout 2969 bytes, raw sha256
`00d50af7e6d33448e956a72ac31361e4fd326c999877fecaa6ea1d716fd186ba`, LF
sha256 `6a07754ce902e731becb5f4f07cf9c215294e561feaecf5a8047dfc0d0f6f414`.

Sidecar identities: `terminal_verdict.json`
`ffe1b89d1284435cbb9dd53318025ee052ad0fa58b1f8a304736a381712dc693`,
`verdict_record.json`
`fa9d62c79ab6399981e1acedbedbd07a149daec2c6ea4bde1dc7aee3a7d52738`,
`p8_99_tests.json`
`9450c473d3578f327301b0f4a758fbeb3dfc0a8d8151a01241fda92809f101e3`.

## Verdict boundary

The terminal marker is `PASS` for the exact bounded audited public fixture
and behaviour only. It does not authorize general MIPS32 compatibility,
arbitrary MIPS32 ELF support, complete ISA or o32 ABI support, arbitrary
Linux binaries, dynamic linking, exceptions, floating point, coprocessors,
privileged execution, arbitrary indirect-control-flow recovery, PS1/PS2,
game or commercial compatibility, or any claim beyond the audited evidence.
`OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` is permanent.
