# P6-06 Public MMC1 Proof Fixture - Result

Verdict: `PASS`

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-05 boundary commit (Phase-5 frozen
  boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7`; tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Build the original Apache-2.0 MMC1 NES proof fixture deterministically; record
exact source revision, assembler/toolchain, ROM hash, PRG/CHR configuration,
vectors and mapper metadata; include bank switching, CHR switching, mirroring,
input and graphics behaviour sufficient to exercise the supported MMC1
contract.

## Changes (additive)

- `.openrecomp-phase6/fixture/p6_public_mmc1_proof.asm`: new full behavioural
  proof fixture (262 instructions, original Apache-2.0).
- `.openrecomp-phase6/src/p6_fixture_proof_v1.py`: proof builder with decoder
  cross-check, provenance metadata and static behaviour inventory.
- `tools/test_phase6_mmc1_fixture_v1.py`: new P6-06 gate.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`, `STATE.md`, `STAGE_QUEUE.md`,
  `HANDOFF.md`: stage bookkeeping.
- The P6-01 established fixture (`p6_public_fixture.asm` and its builder) is
  unchanged; its frozen identity is re-verified by this gate.
- No frozen file was modified.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-06
  --script tools/test_phase6_mmc1_fixture_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-06 --tests-json p6_06_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 3073 bytes raw, raw sha256
    `2d32801cfec18390f4cb16f361c3fa6a1fd7a1c7d7a10232632d0b59a573beb9`,
    LF sha256
    `3fd40332c6b5055da61ed913c846752947d1a4119411f150d55968284e3fd2bb`.
  - `p6_06_tests.json` sha256
    `a8b37306876210051d662c07a85f413667cbb000e5ce16e6d178a126de3e4b4d`.
- Markers: `OPENRECOMP_P6_06=PASS`,
  `OPENRECOMP_PHASE6_MMC1_FIXTURE_V1=PASS tests=67`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Proof fixture identity

- Source revision `.openrecomp-phase6/fixture/p6_public_mmc1_proof.asm`
  sha256 `17f12ba0cb7b5d5a220ed205b28e66ff62e33959b8e62f47dae9c598fa533528`;
  assembler `.openrecomp-phase5/src/p5_fixture_asm_v1.py` sha256
  `dd82b6a46b3c0411b9977677254b2796b5a6161da8fe544588df13b7d444ce80`.
- ROM SHA-256 `9e10dce532266592f9ccda781bc6d3a7354ab4951bd3db87e4f43d1c45056b70`
  (98320 bytes); header `4e45531a040410000000000000000000`.
- PRG `197a464f...` (64 KiB, 4 banks); CHR `4f9abd22...` (32 KiB, 4 banks);
  mapper 1, submapper 0, horizontal mirroring, power-on control `0x0C`.
- Vectors: NMI `$C1F8`, RESET `$C000`, IRQ `$C235`. 262 instructions, all
  cross-checked against the frozen `adapters.nes6502` decoder; two builds
  byte-identical.

## Behaviours exercised (static inventory)

- Serial writes to all four MMC1 windows `$8000`, `$A000`, `$C000`, `$E000`.
- PRG bank selection 0..3 followed by reads of the switched `$8000`/`$8100`
  window; CHR 4 KiB bank selection (mode 1) observed through PPUDATA reads at
  PPU `$0000` and `$1000`.
- Mirroring modes 0..3 written and observed through aliased nametable reads at
  `$2400`/`$2C00` (one-screen lower/upper, vertical, horizontal).
- Controller serial reads through `$4016` into a per-frame transcript;
  palette/nametable/sprite setup; NMI per frame with OAM DMA and scroll
  updates; `$02FF` page-wrap run-exit thunk.
- Replaying the fixture's register sequences through the P6-02 .. P6-05 models
  yields PRG windows `(0..3, 3)`, CHR 4 KiB banks 0..7 and the exact expected
  mirroring tables; the proof image classifies `SUPPORTED_MMC1` with a
  disabled PRG-RAM window.

## Negative / fail-closed coverage

An unsupported mnemonic, a missing reset label and a broken vector word all
fail closed during the proof build without traceback.

## Regressions

`tools/test_nes_rom_v1.py`, `tools/test_nes_platform_v1.py` and the P6-00 ..
P6-05 gates all exit 0 with empty stderr (earlier P6 gates re-run into ignored
scratch evidence; committed evidence untouched). The P6-01 established fixture
identity `7d5514c7...` is preserved.

## Limitations

- The proof fixture is established and statically verified here; its
  static-recompilation integration (P6-07), native execution (P6-08) and
  independent equivalence (P6-09) are later stages. No execution claim is made
  and the terminal marker remains `NOT_PROVEN`.
- The P6-01 established fixture remains a separate frozen identity; it is not
  the proof fixture.

## Evidence files

`RESULT.md`, `p6_06_tests.json`, `official_runs.json`, `determinism.json`,
`proof_fixture.json`, `behaviours.json`, `regressions.json`, `run1.txt`,
`run2.txt`, `run1.err.txt`, `run2.err.txt`, `changed_files.txt`.

## Next stage

P6-07 - MMC1 static-recompilation integration.
