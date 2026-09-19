# P7-02 Undocumented Opcode 0x7C Classification - Result

Verdict: `PASS`

Classification: `0x7C` at `0xC570` is **`DATA_NOT_CODE`** - the low byte of
the first 16-bit code pointer in an inline dispatch table following
`jsr $C71F` at `0xC56D`. It is not an executable instruction, and no
undocumented-opcode semantics were added.

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-01 boundary commit,
  descending from the frozen Phase-6 terminal commit
  `1643817d43196c43155805249137e4b4e4a21eb1`.

## Objective (frozen queue)

Determine exactly what the `0x7C` byte represents in this binary/context from
evidence, without guessing semantics from the opcode value alone, and
classify it as `SUPPORTED_PROVEN`, `RECOGNIZED_UNSUPPORTED`, `DATA_NOT_CODE`,
`UNREACHABLE`, `AMBIGUOUS` or another explicitly justified fail-closed
category. No universal undocumented-opcode claim.

## Evidence chain

1. Control-flow context: the bounded documented-control-flow walk (same model
   as Phase 6) stops at `0xC570`; the only static predecessor edge is the
   fallthrough of `jsr $C71F` at `0xC56D`. No direct branch or jump targets
   `0xC570`.
2. Callee semantics (documented instructions only): the callee entry at
   `0xC71F` is `asl a; sty $03; tay; iny; pla; sta $00; pla; sta $01;
   lda ($00),y; sta $02; iny; lda ($00),y; ldy $03; sta $03; jmp ($0002)`.
   It pulls the two bytes of the pushed return address (`$C56F`) into
   `$00/$01` before any transfer, reads a little-endian pointer pair from the
   inline data after the call site and dispatches through `jmp ($0002)`. It
   never returns to `0xC570`.
3. Inline table: decoding little-endian 16-bit entries from `0xC570` yields
   exactly six targets in the fixed code window, each decoding to a documented
   instruction first op:
   `$C57C`, `$C644`, `$C679`, `$C686`, `$CB24`, `$C6B6`. Documented code
   resumes at `0xC57C` (`lda $1C; jsr $C71F; ...`).
4. Nested structure: the resumed code's `jsr $C71F` at `0xC57E` has its own
   inline table at `0xC581` with four in-window targets (`$C589`, `$C5B4`,
   `$C5FE`, `$C62C`), confirming the recursive dispatch-table idiom.
5. Corroboration: the byte stream after `0xC570` is not a coherent documented
   instruction stream; forcing any skip width reaches an undocumented byte
   (`0xCB`) within nine bytes - typical of table data, not of code.
6. Reference basis: the classification is structural and uses only documented
   6502 semantics (`plA`, `sta zp`, `lda (zp),y`, `jmp (indirect)`, 16-bit
   little-endian pointer arithmetic) on the NES 2A03 NMOS core. It does not
   depend on any undocumented-opcode table entry, and no undocumented opcode
   semantics are implemented. The frozen decoder still rejects `0x7C`
   (151 documented opcodes, `0x7C` absent).

## Classifier mechanism proof (original synthetic public images)

The gate proves the same classifier on original synthetic images:

| Case | Expected | Result |
| --- | --- | --- |
| full inline-dispatch idiom with two `$C1xx`/`$C2xx` targets | `DATA_NOT_CODE` | PASS |
| callee with plain `rts` (does not consume the return address) | `AMBIGUOUS` | PASS |
| return-consuming callee but no in-window table | `AMBIGUOUS` | PASS |
| literal `jmp` predecessor instead of `jsr` fallthrough | `AMBIGUOUS` | PASS |
| documented reachable instruction address | `REACHABLE_CODE` | PASS |
| address with no static predecessor | `UNREACHABLE` | PASS |

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-02
  --script tools/test_phase7_opcode_classification_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-02 --tests-json p7_02_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 1802 bytes raw, raw sha256
    `1a10323c5785bd3cb8fcb526a4b1eed47b68f4c540e4f6ea935d219bf007bad1`,
    LF sha256
    `6ffe5e57f2b36ca0ceac68257f01b3eb81d47026f910ad9392b9ff6f64908332`.
  - `p7_02_tests.json` sha256
    `f94b83640a4679529c681ca6a170e340052d4b898d314cd80d99c40733be0efa`,
    `tests=37`; both runs produced the same tests-json hash.
- Markers: `OPENRECOMP_P7_02=PASS`,
  `OPENRECOMP_PHASE7_OPCODE_CLASSIFICATION_V1=PASS tests=37`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Negative / fail-closed coverage

- Missing private path and a synthetic malformed container fail closed as
  `P7OpcodeError` without traceback.
- The classifier never guesses: non-`jsr` predecessors, non-consuming
  callees and missing tables classify `AMBIGUOUS`; the frozen decoder is
  unchanged and still fails closed on `0x7C`.
- Evidence hygiene: no private ROM bytes in the classification record; no
  ROM-extension file in the stage scratch tree.

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_frontier_rederive_v1.py` re-run into ignored scratch
  evidence: exit 0, empty stderr, `OPENRECOMP_P7_01=PASS`.

## Changes

- Added `.openrecomp-phase7/src/p7_opcode_7c_v1.py`.
- Added `tools/test_phase7_opcode_classification_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`,
  `.openrecomp-phase7/STATE.md`, `.openrecomp-phase7/STAGE_QUEUE.md` and
  `.openrecomp-phase7/HANDOFF.md`.
- No frozen Phase-1..Phase-6 file was modified; the frozen 6502 decoder and
  its 151-opcode documented table are unchanged.

## Limitations

- The classification is bounded to this byte, this binary and this context; it
  makes no universal claim about `0x7C` or undocumented opcodes and adds no
  semantics.
- The classification proves the byte is data; it does not by itself resolve
  the whole inline-dispatch tree, the `$E2` indirect sites or bank state.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `opcode_classification.json`,
  `p7_02_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-03 Public undocumented-opcode proof fixture (classification-mechanism
fixture, since P7-02 proved the byte is data).
