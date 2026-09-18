# P5-02 2A03/6502 Decode + Reachable Frontier - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `bf09843` (P5-01 boundary).

## Objective (frozen queue)

Exercise the existing NES6502 frontend against the real fixture; produce an
exact reachable/dead/unsupported opcode inventory; account explicitly for NES
2A03 behaviour including the absent decimal-mode arithmetic semantics.
Unsupported or illegal opcodes remain fail closed.

## Delivered

- New `.openrecomp-phase5/src/p5_frontier_v1.py`: exact reachability walk over
  the 64 KiB NROM CPU image from the reset/NMI/IRQ roots using the frozen
  `adapters.nes6502` decoder. Only documented static edges are followed
  (direct jmp/jsr/branch targets and fallthrough); `jmp (indirect)` is an
  unresolved indirect site; `rts`/`rti` are recorded as dynamic-return sites;
  `brk` continues at the documented pushed return address (pc+2); undocumented
  opcodes fail closed. Data regions/padding are classified as non-code.
- New `tools/test_phase5_frontier_v1.py` gate.

## Frontier (exact, public fixture)

- Roots: RESET `$C000`, NMI `$C196`, IRQ `$C1F7`.
- Reachable: 230 instructions / 508 bytes. Code span `[$C000,$C1FD)` linearly
  decodes 231 instructions; exactly 1 dead instruction: the padding NOP at
  `$C0A7` after the software BRK (correct: BRK resumes at `$C0A8`).
- Reachable undocumented opcodes: 0 (frozen decoder fails closed; none occur).
- 39 distinct mnemonics; mode coverage includes zero page, indexed zero page,
  absolute indexed (with page crossing), `(zp,X)`, `(zp),Y`, accumulator and
  relative modes.
- Indirect sites: exactly one - `$C0FD jmp ($02FF)`, the declared
  run-exit service thunk (page-wrap vector layout), unresolved by design.
- Interrupt site: `$C0A6 brk` with documented continuation `$C0A8`.
- Dynamic return sites: 9 (`rts` x7, `rti` x2); never guessed.
- 2A03 decimal-mode accounting: `sed`/`cld` present, arithmetic is
  `binary_only_2a03`; exact semantics are proven in P5-03.

## Frozen frontend exercise

`tools/nes6502_frontend_v1.convert` was exercised on the real fixture code
region `[$C000,$C1FD)`: 231 instructions / 45 blocks, one function, source
input digest `eda59866...`; two conversions are byte-identical. A crafted
undocumented opcode (0x03 SLO) is rejected with `NES6502FrontendError`
fail-closed. (0x02 is the frozen frontend's synthetic halt sentinel and is not
a published opcode; it does not occur in the fixture.)

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 1531 bytes raw, raw sha256
    `76767a3b046d7b18b3754982885bb8ab931d59ee69c9b4ec16877e0eb5aa0c03`,
    LF sha256
    `27de3c2798e2a6d28af6744fefc2e935f967179dd4844e4c8c3af6d7fb6cb7ea`.
  - `p5_02_tests.json` sha256
    `2eb8ef8c40706f2bdf45c3f76171410e06aa20d4d7c88e49fdd1807aaada0dc4`.
- Markers: `OPENRECOMP_P5_02=PASS`,
  `OPENRECOMP_PHASE5_DECODE_FRONTIER_V1=PASS tests=33`; terminal/general
  reserved as `NOT_PROVEN`.
- Gate sha256 `c330a9ea9d71bdc5e367c2c6d0ddf715304d3a91d0650b301c647672292b5b4c`;
  Phase-5 manifest verifies all nine entries.

## Negative coverage

Reachable undocumented opcode, unsupported NROM PRG size and missing data-span
metadata all fail closed without traceback.

## Regressions

`tools/test_nes6502_decode_v1.py` and `tools/test_nes6502_lowering_v1.py`
re-pass with empty stderr (recorded in `regressions.json`).

## Limitations

- The frontier is exact for the audited public fixture only; it is not a
  general 6502/NES disassembler and makes no claim about other images.
- Dynamic return targets remain dynamic; the static model records them
  explicitly instead of guessing them.
- No execution semantics are proven here; P5-03 owns instruction semantics.

## Evidence files

`RESULT.md`, `p5_02_tests.json`, `official_runs.json`, `determinism.json`,
`frontier.json`, `frontend.json`, `regressions.json`, `run1.txt`, `run2.txt`,
`run1.err.txt`, `run2.err.txt`.

## Next stage

P5-03 - CPU semantics proof.
