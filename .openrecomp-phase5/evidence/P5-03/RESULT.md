# P5-03 CPU Semantics Proof - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `c472bf2` (P5-02 boundary).

## Objective (frozen queue)

Verify exact semantics for every instruction required by the reachable public
fixture path, including flags, stack, branches, page crossing, BRK/IRQ/NMI/
RESET behaviour, JMP-indirect page-wrap, zero-page addressing and
read/modify/write semantics, using an independently written reference model
for differential vectors.

## Delivered

- New `.openrecomp-phase5/src/p5_semantics_v1.py`: deterministic vector
  generator and differential runner. Subject is the frozen translation path
  (`tools/nes6502_frontend_v1.convert` -> normalized IR V1 -> shared
  `openrecomp` core `ReferenceExecutor`); oracle is the frozen independently
  written `tools/nes6502_reference_v1.py`. Every vector requires exact
  agreement of A/X/Y/SP/P/PC/halted and the complete 64 KiB guest memory.
- New `tools/test_phase5_semantics_v1.py` gate.

## Coverage (181 vectors, all equivalent)

- 151 distinct (mnemonic, mode) pairs = every documented official NMOS 6502
  opcode form, including all 8 conditional branches taken and not taken,
  BRK/RTI, JSR/RTS, JMP absolute, JMP-indirect page-wrap and the legal
  addressing modes.
- Every (mnemonic, mode) pair required by the reachable public fixture path
  (63 triples) is included in the covered set.
- Edge vectors: ADC/SBC carry/overflow/zero/negative boundaries, CMP/CPX/CPY
  boundaries, BIT V/N, INC `$7F` -> `$80`, DEC `$00` -> `$FF`, zero-page
  indexed wrap (`$FF,X`), absolute-X/Y page crossing, indirect-indexed page
  crossing, RMW absolute-X page crossing, PHP/PLP/PHA/PLA stack round trips,
  BRK/RTI vector round trip, and the NES 2A03 binary-only SED+ADC/SBC
  behaviour.
- Interrupt entry: documented RESET (`$FFFC`), IRQ (`$FFFE`, I-cleared) and
  NMI (`$FFFA`) vector, stack push order (PCH, PCL, P with B clear) and flag
  effects verified against the independent reference with explicit expected
  values.

## Negative coverage

Undocumented opcode (0x03), missing terminator and malformed assembly each
fail closed with a deterministic `SemanticsError`; no traceback.

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 2513 bytes raw, raw sha256
    `11055196b02a7e3ef6aedfd67c99034c385083bf132e45460bce23d934e3a5e3`,
    LF sha256
    `42c5cb65270aef7c6864766914044b6ed540fbd1f0896f9b0b97c677cfd05937`.
  - `p5_03_tests.json` sha256
    `aa46976f48d5a7d2461c9d93b98ee7b622241cf3880d37e11c0d43cf1aed1e49`.
- Markers: `OPENRECOMP_P5_03=PASS`,
  `OPENRECOMP_PHASE5_CPU_SEMANTICS_V1=PASS tests=46`; terminal/general
  reserved as `NOT_PROVEN`.
- Gate sha256 `aed9ee537721b73a48961b06ce92aa842c4dcee80dcefe4e8d0ea25aedcd8f09`;
  Phase-5 manifest verifies all eleven entries.

## Regressions

`tools/test_nes6502_semantics_v1.py` and `tools/test_nes6502_state_v1.py`
re-pass with empty stderr (recorded in `regressions.json`).

## Limitations

- The suite proves instruction semantics for the official opcode map; the
  Phase-5 claim remains bounded to the public fixture path and does not extend
  to arbitrary 6502 binaries or to cycle timing.
- Interrupt semantics are verified at the independent-reference level with
  explicit documented expectations; native platform-level interrupt delivery
  equivalence is P5-07/P5-10 scope.
- No performance or timing claim is made.

## Evidence files

`RESULT.md`, `p5_03_tests.json`, `official_runs.json`, `determinism.json`,
`semantics.json`, `coverage.json`, `interrupt.json`, `regressions.json`,
`run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`.

## Next stage

P5-04 - ProgramModel / CFG / functions / translation units.
