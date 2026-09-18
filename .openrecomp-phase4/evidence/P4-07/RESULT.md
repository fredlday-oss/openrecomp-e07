# P4-07 result (PASS)

Stage: `P4-07` Interactive legally-clean fixture (frozen queue row).
Gate: `tools/test_phase4_fixture_v1.py` (49 checks, sha256
`620c2ff75d93a0467ec58413ff8fea9bfd22ec17e3482ffda8cc5b71d0913320`).
Evidence: `.openrecomp-phase4/evidence/P4-07/`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_07=PASS`
- Gate marker: `OPENRECOMP_PHASE4_FIXTURE_V1=PASS tests=49`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Objective (frozen queue)

Introduce or build a legally clean/open fixture materially more demanding
than CoreMark and exercising a meaningful subset of code, static/global data,
stack, heap if required, runtime services, deterministic input/events, timing
and observable output. Record license, provenance, exact source/toolchain/
build flags and hashes. Do not use proprietary ROMs, commercial game
binaries, copyrighted game assets or unverified fixtures.

## Fixture (original, Apache-2.0)

`.openrecomp-phase4/fixture/` contains an original interactive freestanding
MIPS32 program authored for OpenRecomp (repository Apache License 2.0):

- `p4_fixture.h`, `p4_fixture_util.c`, `p4_fixture_main.c`, `p4_start.S`,
  `p4_fixture.ld`, `README.md`, `input_plan.json`;
- exercises: recursion (`p4_fib`), loops/branches, direct calls, const tables
  (`.rodata`), initialised globals (`.data`), zero-fill storage (`.bss`),
  a 256-byte scratch round-trip and an 8 KiB stack window, a bounded 1 KiB
  static bump arena, and a 64-byte heap-like allocation round;
- runtime services: byte output (`0x20000000`), byte input (`0x20000004`),
  32-bit exit (`0x20000008`) and virtual ticks (`0x2000000c`);
- deterministic input plan `0512ab34ff` (terminating `0xff`);
- observable: fixed-format transcript plus a 32-bit FNV-1a-style checksum.

## Verification highlights

- `provenance:*`: original-work headers, Apache-2.0 statement, repository
  license, no forbidden third-party/console/commercial tokens, no binary
  container magics, and an LF-normalized pin for the start stub (its extension
  is not covered by the frozen `.gitattributes` line-ending rules).
- `toolchain:*` / `build:*`: `zig cc` 0.13.0 with the recorded bounded flags
  and `zig ld.lld -m elf32ltsmip`; two isolated build roots produce a
  byte-identical 9884-byte ELF, sha256
  `acb4f4e57a7f996e87989e99d702d802259b752aabb2476f574665ef061969bc`
  (pinned by the gate).
- `ingest:*`: the frozen Phase-3 ingestion layer parses the fixture
  (ELF32 LE `EM_MIPS` `ET_EXEC`, O32, soft-float, static, non-PIC, no dynamic
  section); required sections present; entry inside `.text`; `.bss`
  `SHT_NOBITS`; `.data` initialised.
- `frontier:*`: 776 words; 774 reachable; 2 unreachable reserved alignment
  words; 0 unknown encodings and 0 reachable invalid words; reachable
  recognized-unsupported words are exactly `movn` (1) and `mul` (4), both in
  the bounded P3-04 semantic class; 14 direct calls, 48 conditional
  branches, 11 jumps, 10 returns; zero indirect jumps, indirect calls and
  unsupported control transfers; no unresolved successors.
- `features:*` / `plan:*`: bounded code scale, region model present, declared
  input plan with terminator and the virtual tick policy.
- `model:*`: the clearly labelled preliminary Python mirror computes
  `fib10=55`, `primes_sum=381`, `bss_sum=4028012831`, `heap_sum=3784880468`
  and `checksum=0xd43e5ba6`; tick fields stay policy-dependent and are to be
  confirmed by the independent reference in P4-09.

## Determinism

- Two consecutive official gate runs (each rebuilding the fixture twice):
  exit 0, empty stderr, stdout byte-identical raw (1868 bytes, `76dd4cf2...`)
  and LF (`d1f1d554...`), and `p4_07_tests.json` byte-identical across both
  runs (`2c41e62e...`).
- Evidence: `official_runs.json`, `determinism.json`, `build.json`,
  `elf_characterisation.json`, `expected_transcript.json`.

## Regressions

- P2-08 `PASS tests=169`; P4-01 `PASS tests=156`; P4-02 `PASS tests=113`;
  P4-03 `PASS tests=86`; P4-04 `PASS tests=101`; P4-05 `PASS tests=76`;
  P4-06 `PASS tests=72`.
- `tools/phase1_host_gates_v1.py` `PASS=44 FAIL=0 SKIPPED=2`.
- `tools/public_safety_scan.py` `OPENRECOMP_PUBLIC_SAFETY=PASS`.
- P4-00 `PASS tests=74` (`953312d0...`) with the documented dynamic
  boundary-context hygiene (`regression_hygiene.json`).

## Limitations

- The fixture is not yet translated or executed; P4-08/P4-09 own the
  platform-adapter execution proof and the independent reference. No opcode
  support, execution or equivalence claim is made here.
- The preliminary transcript mirror is model-derived, not independent
  evidence; the tick fields are runtime-policy dependent by design.
- The fixture deliberately avoids indirect control flow, unaligned word
  accesses and out-of-class operations so it stays inside the proven bounded
  translation frontier; this is a bounding choice, not a general MIPS32
  support claim.
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal and general compatibility
  markers stay reserved.

## Next stage

P4-08 - First platform-adapter execution proof.
