# P7-03 Public Classification Fixture - Result

Verdict: `PASS`

Because P7-02 proved the `0x7C` byte is data rather than an executable
instruction, P7-03 proves the classification mechanism end-to-end on an
original Apache-2.0 public NES fixture and adds no undocumented-opcode
semantics.

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-02 boundary commit,
  descending from the frozen Phase-6 terminal commit
  `1643817d43196c43155805249137e4b4e4a21eb1`.

## Objective (frozen queue)

Create an equivalent public proof fixture demonstrating the classification
mechanism rather than adding false semantics (the P7-02 branch of the frozen
P7-03 contract).

## Public fixture identity

| Field | Value |
| --- | --- |
| Fixture | `openrecomp-phase7-inline-dispatch-classification-fixture` |
| License / origin | Apache-2.0 / original |
| Source | `.openrecomp-phase7/fixture/p7_inline_dispatch_fixture.asm` |
| Source sha256 | `f7059d20e638b32767a19d3e87b45f2ed056dd574cb744e26d479510ddffff8d` |
| ROM sha256 | `66c4d8c759e622e214f25eb1cb1a6f67b928d3031e1d21a4db0367f06ccd6d8c` |
| ROM size | 40976 bytes |
| PRG / CHR | 2 x 16 KiB / 1 x 8 KiB |
| PRG sha256 | `ddf925c0b4e900a6f6242a093c3da347c8200c9b39fcd00d9bcb3ff2642fde10` |
| CHR sha256 | `5fe9a00381da1fb105be549320eae615b35f8afc820bdd34803198403d1161ec` |
| Mapper / mirroring | 1 (MMC1) / horizontal |
| Vectors | NMI `$C140`, RESET `$C000`, IRQ `$C141` |
| Assembler | frozen `.openrecomp-phase5/src/p5_fixture_asm_v1.py` |
| Cross-check | every assembled instruction re-decoded by `adapters/nes6502.py` |

Fixture structure (original code):

- `reset` at `$C000` initialises, stores selector 1, calls `plain_sub` and
  then `jsr $C100` at `call_site` `$C018`;
- the inline table at `inline_table` `$C01B` holds three little-endian code
  pointers (`$C07C`, `$C090`, `$C0A0`); its first byte is `0x7C`, so the
  documented decoder stops exactly at the table base;
- `dispatch` at `$C100` pulls the pushed return address (`pla; sta $00; pla;
  sta $01`), reads the selected pointer through `lda ($00),y` and tail-jumps
  through `jmp ($0002)`;
- documented code resumes at `resume_code` `$C021` and is not executed by the
  fixture's dynamic path;
- each target writes its marker to `$0300` and exits through
  `jmp ($02FF)` at `$C130`.

## Classification mechanism verified on the public fixture

The frozen P7-02 classifier applied to the fixture's MMC1 CPU image returns
`DATA_NOT_CODE` at `$C01B` with exactly the expected structural evidence:
single predecessor (`jsr` fallthrough at `$C018`), return-consuming callee
(`$C100`, pulls 2, indirect reads, indirect jump), three in-window table
targets (`$C07C`, `$C090`, `$C0A0`) and documented code resume at `$C021`.

## Independent differential verification

- Static model: `p7_dispatch_reference_v1.predict_target` (independent
  little-endian pointer arithmetic) predicts `$C07C`, `$C090`, `$C0A0` for
  selectors 0, 1, 2, matching the classifier's table targets.
- Dynamic model: the frozen independent 6502 reference core
  (`nes_headless_v1.NesReference6502`) over the frozen independent MMC1
  platform executes the fixture for all three selectors: exit reached at
  `$C130`, markers `$10`/`$11`/`$12`, `plain_out=$22`, 32 steps, clock 102,
  predicted target present in the executed set.
- The Phase-7 cost schedule is cross-checked against the frozen Phase-6
  `REFERENCE_COSTS` table for every shared opcode (all equal).

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-03
  --script tools/test_phase7_classification_fixture_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-03 --tests-json p7_03_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 2329 bytes raw, raw sha256
    `6edadcda6370684194deade84a4fdcea3c56cd66890eb085a575a7054959254e`,
    LF sha256
    `59ffed5c74144d53e3a3abfeac571ec20a24eaa1a6dedd5a45cddb1f31152e2c`.
  - `p7_03_tests.json` sha256
    `29405ee81d96278ddd6535388f8cc70cc2ba4dbb1ccb5db694e04c0850640f2c`,
    `tests=49`; both runs produced the same tests-json hash.
- Markers: `OPENRECOMP_P7_03=PASS`,
  `OPENRECOMP_PHASE7_OPCODE_FIXTURE_V1=PASS tests=49`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Edge and negative coverage

- Selector 3 points outside the fixed code window: the static model fails
  closed (`P7DispatchError`) instead of guessing.
- Negative selectors (`-1`, `True`, `"1"`) fail closed.
- A tampered dispatcher (first `pla` replaced by `nop`) classifies
  `AMBIGUOUS` ("does not consume") - fail closed, no false `DATA_NOT_CODE`.
- The frozen decoder is unchanged: 151 documented opcodes, `0x7C` still
  rejected; no undocumented-opcode semantics were added.
- Evidence hygiene: no private ROM bytes in evidence; no ROM-extension file
  written to the repository or scratch; the public fixture is never written as
  a `.nes` file.

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_opcode_classification_v1.py` re-run into ignored scratch
  evidence: exit 0, empty stderr, `OPENRECOMP_P7_02=PASS`.

## Changes

- Added `.openrecomp-phase7/fixture/p7_inline_dispatch_fixture.asm`.
- Added `.openrecomp-phase7/src/p7_classification_fixture_v1.py` and
  `.openrecomp-phase7/src/p7_dispatch_reference_v1.py`.
- Added `tools/test_phase7_classification_fixture_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`,
  `.openrecomp-phase7/STATE.md`, `.openrecomp-phase7/STAGE_QUEUE.md` and
  `.openrecomp-phase7/HANDOFF.md`.
- No frozen Phase-1..Phase-6 file was modified.

## Limitations

- The fixture proves the bounded inline-dispatch classification mechanism and
  its documented execution; it makes no universal claim about undocumented
  opcodes, real ROMs or general NES compatibility.
- Translation/native execution of the fixture is not attempted in this stage
  (P7-08/P7-09).

## Evidence index

- `RESULT.md`, `changed_files.txt`, `classification_fixture.json`,
  `p7_03_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-04 Bank-aware cartridge reachability model.
