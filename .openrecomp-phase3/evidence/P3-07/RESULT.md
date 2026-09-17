# P3-07 result (PASS)

Stage: `P3-07` host emission for CoreMark semantics (frozen queue row).
Gate: `tools/test_phase3_host_emit_v1.py` (67 checks).
Evidence: `.openrecomp-phase3/evidence/P3-07/`.

Markers issued:

- Stage marker: `OPENRECOMP_P3_07=PASS`
- Gate marker: `OPENRECOMP_PHASE3_HOST_EMISSION_V1=PASS tests=67`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

## Scope

P3-07 emits one deterministic portable-C translation of the entire audited
CoreMark MIPS32 executable image plus the host runtime support that executes it
through the frozen P2-08 generic runtime ABI boundary. New Phase-3 files only;
no shared layer, frozen adapter, Phase-1/Phase-2 file, gate or frozen manifest
was modified:

- `.openrecomp-phase3/src/p3_host_emit_v1.py` — the phase-3 emitter;
- `tools/test_phase3_host_emit_v1.py` — the P3-07 gate;
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — grown additively from fourteen
  to sixteen entries; the P3-02..P3-06 gates' expected entry set grew 14 -> 16
  additively and their stdout is unchanged.

Generated artifacts (committed as evidence):

- `coremark_program.c` (1073923 bytes) — the whole-image translation;
- `coremark_support.c` (7946 bytes) — the host runtime support.

## Translation

The whole executable image is emitted, not only the P3-05 reachable frontier,
because the three statically unresolved `jr $at` jump tables are resolved at
run time. The emitter:

- emits exactly one case per decodable word: **3479 cases** (all words except
  the eight reserved padding encodings);
- keeps the P3-04 `.openrecomp-phase3/evidence/P3-03` classification as the
  source of truth for flow: 620 control transfers each followed by an emitted
  non-control delay slot, 567 direct targets all emitted, 4 indirect sites
  (`0x1958` dead `jalr`, `0x3130`, `0x3830`, `0x39a0` reachable `jr $at`)
  emitted as runtime-mediated validated dispatch with no static target;
- implements true MIPS32 delay-slot behaviour with a one-instruction
  `g_pending`/`g_has_pending` protocol, so calls, branches, jumps and returns
  execute the delay slot before transferring;
- emits exact semantics for the 46 ops present in the image (register-only
  arithmetic/shift/compare, checked byte/half/word loads and stores, the P3-04
  overlay ops `movz`/`movn`/`mul`/`divu`/`teq`/`swl`/`swr`/`jalr`, and
  `multu`/`mfhi`/`mflo`), plus rules for the audited-but-absent `mult`, `div`
  and `lb`;
- routes guest memory through the P2-08 ABI (`or_rt_memory_read`,
  `or_rt_memory_write`) and the two external windows through runtime-mediated
  host calls (`p3_uart_write`, `p3_exit`); the emitted region table equals the
  P3-02 segment permissions, and the emitted `g_image` initializer decodes
  byte-for-byte to the P3-02 guest image window (`0x0..0x10000`);
- fails closed on architecturally UNPREDICTABLE states: divide by zero, taken
  `teq` (code preserved), unaligned indirect target, PC outside the emitted
  image, step-limit exceeded, out-of-image or non-writable memory access and
  UART overflow. `mul` writes only `rd` and leaves HI/LO unchanged, which is
  safe because P3-04 proved no reachable HI/LO read depends on a `mul`.

## Deterministic observable

`coremark_support.c` reports after `openrecomp_run()`: `exit_status`,
`steps`, `pc`, `hi`, `lo`, `uart_bytes`, `uart_hex`, `state_fnv1a64`
(FNV-1a 64 over the flat image bytes, the 32 registers little-endian, HI, LO,
PC, steps, exit status, UART length and the UART bytes, in that order),
`failed` and `failure`. The same contract is re-implemented independently by
the P3-09 reference.

## Verification

- 67 gate checks: source integrity (root manifest 134 entries frozen,
  Phase-3 manifest 16 entries), frontier/model cross-checks, exact case/
  histogram/delay-slot/direct-target counts, emitted image and region table
  parsed back from the generated text, P2-08 ABI boundary presence, observable
  contract presence, 11 fail-closed negatives and emission determinism.
- Emission determinism: two independent ingest/frontier/model/emission runs
  produce byte-identical program and support text.
- Official runs: two consecutive runs byte-identical (raw sha256
  `d7986967dbf9fb2021e86dab7902c18d294a6b52e606a0cabad13907bd317746`, empty
  stderr, exit 0); no native build or execution is performed in P3-07.
- Regressions all exit 0 with empty stderr and byte-identical stdout: P2-99
  `PASS tests=202` (`66913e57...`), P3-00 `PASS tests=61` (`a039bbff...`),
  P3-01 `PASS tests=76` (`81eede03...`), P3-02 `PASS tests=197`
  (`f24f4cef...`), P3-03 `PASS tests=201` (`15e20a2c...`), P3-04
  `PASS tests=126` (`412544a4...`), P3-05 `PASS tests=202` (`12bf87d7...`),
  P3-06 `PASS tests=123` (`23d2f1c2...`), Phase-1 host gates
  `PASS=44 FAIL=0 SKIPPED=2` (`2a9d1bba...`), public safety `PASS`
  (`ad022ff1...`).

## Claim boundary

P3-07 proves only deterministic generation of exact host code for the audited
image. It does not build or execute the native program (P3-08) and does not yet
prove equivalence against an independent reference (P3-09); it claims no
arbitrary MIPS32, PS1 or PS2 compatibility. `COREMARK_STATUS=NOT_PROVEN`.
