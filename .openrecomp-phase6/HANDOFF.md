# OpenRecomp Phase 6 Handoff

STATUS: Phase 6 `ACTIVE` - stage P6-00 (Phase-6 boundary) passed and the
frozen queue `P6-01` .. `P6-99` is frozen. Phase 5 is COMPLETE and frozen at
annotated tag `openrecomp-phase5-pass` (object
`b5d6832ba2374b810f4c24500ed9093a9481fd8d`) =
`e8d3627a622d0ca3196b117c5112f29fabdb49e7`, tree
`468fb9788350de393d3de2ca9471b7d874ee8dc9`, with `OPENRECOMP_P5_99=PASS`,
`OPENRECOMP_PHASE5_FINAL_VERDICT_V1=PASS tests=87` and
`OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=PASS` (bounded audited claim only);
`OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` remains permanent.

Phase 6 objective (reserved `NOT_PROVEN` until P6-99): expand the proven
Phase-5 NROM static-recompilation path to a bounded, audited MMC1/mapper-1
platform path using an original Apache-2.0 public MMC1 fixture, with exact
independent MMC1 reference equivalence, and record the private TMNT image only
as a non-redistributed compatibility observation.

Reserved markers:

- `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN` (P6-99 may issue PASS for
  the bounded claim only)
- `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` (never promoted)

## Firm constraints carried into Phase 6

- Never mutate the frozen Phase-1/Phase-2/Phase-3/Phase-4/Phase-5 histories,
  tags, evidence, gates or verdicts. Phase-6 work is additive under
  `.openrecomp-phase6/` plus new `tools/test_phase6_*` gates.
- Never commit, copy, embed or package the private TMNT image bytes or any
  ROM-derived binary copy (`FIXTURE_POLICY.md`, `CONTROL_POLICY.md` rule 11).
- The public proof fixture is an original Apache-2.0 MMC1 NES program authored
  for Phase 6 with full recorded provenance.
- Fail closed on unsupported mappers, MMC1 variants/wiring and opcodes; never
  guess hardware behaviour.
- Never execute original guest CPU code directly on the host.
- One implementation frontier at a time; every official stage gate runs twice
  with byte-identical stdout and empty stderr.

## P6-00 outcome (PASS)

Markers: `OPENRECOMP_P6_00=PASS`,
`OPENRECOMP_PHASE6_BOUNDARY_V1=PASS tests=85`; terminal and general markers
reserved as `NOT_PROVEN`.

- Branch `phase6/nes-compat-v1` descends from the frozen Phase-5 boundary
  commit `e8d3627...`; tag object `b5d6832b...`, tree `468fb978...`.
- The Phase-5 final verdict gate independently re-passed twice in a
  reconstructed pre-verdict context with byte-identical stdout to the recorded
  official capture (2971 bytes raw `bc1f1e97...`, LF `2378b480...`,
  `tests=87`) and regenerated the committed `p5_99_tests.json`
  (`b0e8267c...`).
- Phase-6 control plane established and deterministic; queue `P6-01` ..
  `P6-99` frozen; `MMC1_PLATFORM_STATUS=NOT_PROVEN`; no MMC1 capability
  claimed.
- ROM safety verified: private fixture 262160 bytes / SHA-256 `2a9345e6...`
  present outside the worktree; no ROM image or private copy anywhere in the
  repository; `.gitignore` ROM rules effective; public/private separation
  recorded in `FIXTURE_POLICY.md`.
- Two official runs byte-identical raw (`9391a99a...`, 3201 bytes) and LF
  (`ca7ab210...`), empty stderr, exit 0; the regenerated
  `p6_00_tests.json` hash and full check list are recorded in the stage
  evidence.
- Evidence: `.openrecomp-phase6/evidence/P6-00/`.

## P6-01 outcome (PASS)

Markers: `OPENRECOMP_P6_01=PASS`,
`OPENRECOMP_PHASE6_MMC1_INVENTORY_V1=PASS tests=85`; terminal and general
markers reserved as `NOT_PROVEN`.

- Supported MMC1 subset `MMC1_SUBSET_V1` defined in
  `.openrecomp-phase6/MMC1_SUBSET.md` and `p6_mmc1_spec_v1.py`: four serial
  registers, 5-bit LSB-first write protocol, reset bit, control
  mirroring/PRG/CHR modes, 16/32 KiB PRG banking, 8/4 KiB CHR banking, no
  PRG-RAM/battery in the supported fixture, 26 pinned requirement IDs and
  explicitly classified unsupported variants.
- Original Apache-2.0 MMC1 fixture established and built deterministically:
  64 KiB PRG (4 x 16 KiB, bank 3 fixed with code and vectors), 32 KiB CHR
  (4 x 8 KiB), horizontal mirroring, ROM SHA-256 `7d5514c7...` (98320 bytes),
  PRG `2fc4064e...`, CHR `4f9abd22...`, vectors NMI `$C029` / RESET `$C000` /
  IRQ `$C02C`, 57 instructions cross-checked against the frozen decoder.
- MMC1-aware ingestion (`p6_ines_v1.py`) classifies mapper-1 images against
  the subset and extracts power-on fixed-last-bank vectors for supported
  images only; unsupported/malformed declarations fail closed. Phase-5
  ingestion behavior is preserved (mapper 1 still `BLOCKED_UNSUPPORTED_MAPPER`
  with vectors unavailable) and the frozen `make_mapper` still fails closed.
- Private TMNT inventoried by metadata/hash only (262160 bytes, SHA-256
  `2a9345e6...`, mapper 1, submapper 0, 128 KiB PRG/CHR, no battery/trainer,
  horizontal); cartridge contract `SUPPORTED_MMC1`, execution still
  `BLOCKED_MMC1_MAPPER_NOT_YET_IMPLEMENTED`. No ROM bytes in evidence.
- Negative coverage: bad magic, truncation, excess bytes, zero PRG, PRG/CHR
  out-of-range, absent CHR, battery, declared PRG-RAM, non-zero submapper,
  four-screen and unsupported mapper all fail closed or classify with explicit
  reasons.
- Regressions: `tools/test_nes_rom_v1.py` and `tools/test_nes_platform_v1.py`
  pass with empty stderr.
- Two official runs byte-identical raw (`2bfd8a5e...`, 3140 bytes) and LF
  (`d153a32d...`), empty stderr, exit 0; `p6_01_tests.json` sha256
  `69900ee9...`.
- Evidence: `.openrecomp-phase6/evidence/P6-01/`.

## P6-02 outcome (PASS)

Markers: `OPENRECOMP_P6_02=PASS`,
`OPENRECOMP_PHASE6_MMC1_SERIAL_V1=PASS tests=47`; terminal and general markers
reserved as `NOT_PROVEN`.

- New deterministic MMC1 serial register file (`p6_mmc1_serial_v1.py`):
  four 5-bit registers selected by address bits 14:13, five-write LSB-first
  commits, bit-7 shift reset, the audited consecutive-cycle suppression model
  (a write on the immediately following CPU cycle is ignored and leaves all
  state, including the last-write cycle, unchanged), power-on control `0x0C`.
- Independently structured reference model
  (`p6_mmc1_serial_reference_v1.py`, explicit received-bit list) and
  differential vectors: 4940+ comparisons with zero mismatches, including all
  256 first-write classifications, 128 exhaustive five-write commits, 128
  reset-bit sequences, suppression/write-edge sequences and 3000 deterministic
  pseudo-random mixed writes.
- Malformed writes (outside `$8000-$FFFF`, non-8-bit or non-integer values,
  negative cycles) and unknown register names fail closed without traceback
  and leave state untouched.
- `MMC1_SUBSET.md` records the exact audited suppression model; the public
  fixture control write (`0x0F`) replays to the expected commit.
- Regressions: `tools/test_nes_rom_v1.py`, `tools/test_nes_platform_v1.py`,
  the P6-01 gate and the P6-00 boundary gate all pass with empty stderr
  (P6-01/P6-00 re-run into ignored scratch evidence).
- Two official runs byte-identical raw (`caf7bb5c...`, 2305 bytes) and LF
  (`ed006109...`), empty stderr, exit 0; `p6_02_tests.json` sha256
  `86ca0e02...`.
- Evidence: `.openrecomp-phase6/evidence/P6-02/`.

## P6-03 outcome (PASS)

Markers: `OPENRECOMP_P6_03=PASS`,
`OPENRECOMP_PHASE6_MMC1_PRG_V1=PASS tests=50`; terminal and general markers
reserved as `NOT_PROVEN`.

- New `p6_mapper1_prg_v1.py`: control/PRG register state mapped to the
  `$8000-$FFFF` CPU window for 32 KiB modes (low register bit ignored),
  mode 2 (bank 0 fixed first, register bank at `$C000`) and mode 3 (register
  bank at `$8000`, last bank fixed), with masking `register & (count - 1)`.
  Supported bank counts are powers of two 1, 2, 4, 8, 16 (16 KiB .. 256 KiB);
  larger or non-power-of-two PRG sizes now classify
  `prg_bank_count_not_power_of_two` and fail closed.
- Independently structured reference (`p6_mapper1_prg_reference_v1.py`,
  modulo arithmetic and dispatch decoding) and exhaustive bounded vectors:
  5120 register/bank combinations and 40960 address mappings with zero
  mismatches, plus 480 explicit fixed-first/fixed-last/32 KiB checks and
  mode 0/1 equivalence for all bank counts.
- Serial integration: committing control `0x0F` and PRG register `2` through
  the P6-02 serial file yields window banks `(2, 3)` and the expected ROM
  offsets; the public 4-bank and private 8-bank contract layouts are `(0, 3)`
  and `(0, 7)`.
- Malformed bank counts and out-of-window addresses fail closed.
- Regressions: frozen NES tools plus P6-00/P6-01/P6-02 gates pass with empty
  stderr (earlier gates re-run into ignored scratch evidence).
- Two official runs byte-identical raw/LF with empty stderr; hashes are
  recorded in `p6_03_tests.json`, `official_runs.json` and `RESULT.md`.
- Evidence: `.openrecomp-phase6/evidence/P6-03/`.

## P6-04 outcome (PASS)

Markers: `OPENRECOMP_P6_04=PASS`,
`OPENRECOMP_PHASE6_MMC1_CHR_V1=PASS tests=61`; terminal and general markers
reserved as `NOT_PROVEN`.

- New `p6_mapper1_chr_v1.py`: CHR mode 0 (8 KiB bank = `chr_bank_0 >> 1`,
  masked to the 8 KiB bank count), CHR mode 1 (two 4 KiB banks from
  `chr_bank_0`/`chr_bank_1`, masked to twice the bank count) and nametable
  mapping for all four mirroring settings over `$2000-$3EFF` with
  `table * 0x400 + (address & 0x3FF)`; out-of-window addresses fail closed.
- Supported CHR 8 KiB bank counts are powers of two 1, 2, 4, 8, 16; non-powers
  now classify `chr_bank_count_not_power_of_two` and fail closed.
- Independently structured reference (`p6_mapper1_chr_reference_v1.py`,
  division/modulo and branch tables) and differential vectors: 1,013,760 CHR
  mapping comparisons over all 5 bank counts x 32 control x 32 register 0 x 32
  register 1 values, plus 63,488 nametable comparisons over every
  `$2000-$3EFF` address for all four modes; zero mismatches.
- Explicit one-screen lower/upper, vertical and horizontal tables and table
  offsets verified; serial integration commits control `0x1F`, CHR registers
  `5`/`2` and maps `$0543`/`$1543` to the expected 4 KiB banks.
- Malformed bank counts and out-of-window CHR/nametable addresses fail closed.
- Regressions: frozen NES tools plus P6-00/P6-01/P6-02/P6-03 gates pass with
  empty stderr (earlier gates re-run into ignored scratch evidence).
- Official run hashes are recorded in `p6_04_tests.json`, `official_runs.json`
  and `RESULT.md`.
- Evidence: `.openrecomp-phase6/evidence/P6-04/`.

## P6-05 outcome (PASS)

Markers: `OPENRECOMP_P6_05=PASS`,
`OPENRECOMP_PHASE6_MMC1_VARIANT_V1=PASS tests=61`; terminal and general markers
reserved as `NOT_PROVEN`.

- New `p6_mapper1_variant_v1.py`: the supported profile
  `discrete_mmc1_chr_rom_no_wram` implements a disabled `$6000-$7FFF` PRG-RAM
  window (every read/write fails closed) and fails closed at construction when
  an image declares PRG-RAM/NVRAM or a battery; no board wiring is inferred.
- Explicit variant ledger V-001 .. V-012: base discrete MMC1 (supported),
  MMC1A/B/C differences, CHR-RAM boards, PRG-RAM/battery boards, SUROM 512 KiB,
  SOROM/SXROM hybrids, four-screen, VS/PlayChoice, non-power-of-two bank
  counts, non-zero submapper, clone/FPGA implementations (not tested) and
  write-protection/bus conflicts.
- Deterministic classifications verified for the public fixture and the
  private TMNT contract (`SUPPORTED_PROFILE`) plus probes for battery,
  PRG-RAM, CHR-RAM, submapper, four-screen, VS, PlayChoice, three-bank
  PRG/CHR and 512 KiB (variant-blocked) and mapper 2 (unsupported mapper).
- MMC1 subset complete through PRG-RAM/variants: serial protocol (P6-02), PRG
  banking (P6-03), CHR banking/mirroring (P6-04) and the variant boundary
  (P6-05) are implemented and differentially verified; no execution claim yet.
- Regressions: frozen NES tools plus P6-00..P6-04 gates pass with empty stderr
  (earlier gates re-run into ignored scratch evidence).
- Official run hashes are recorded in `p6_05_tests.json`, `official_runs.json`
  and `RESULT.md`.
- Evidence: `.openrecomp-phase6/evidence/P6-05/`.

## P6-06 outcome (PASS)

Markers: `OPENRECOMP_P6_06=PASS`,
`OPENRECOMP_PHASE6_MMC1_FIXTURE_V1=PASS tests=67`; terminal and general markers
reserved as `NOT_PROVEN`.

- New full behavioural proof fixture
  `.openrecomp-phase6/fixture/p6_public_mmc1_proof.asm` (262 instructions,
  original Apache-2.0) and proof builder `p6_fixture_proof_v1.py`; the P6-01
  established fixture identity remains frozen and is re-verified.
- Proof fixture identity: 64 KiB PRG (4 x 16 KiB), 32 KiB CHR (4 x 8 KiB),
  mapper 1, submapper 0, horizontal mirroring, ROM SHA-256 `9e10dce5...`
  (98320 bytes), PRG `197a464f...`, CHR `4f9abd22...`, vectors NMI `$C1F8` /
  RESET `$C000` / IRQ `$C235`, source revision `17f12ba0...`, assembler
  `dd82b6a4...`.
- Static behavioural inventory verified: writes to all four MMC1 register
  windows, reads of the switched `$8000`/`$8100` window, CHR 4 KiB bank
  selection observed through PPUDATA, all four mirroring modes observed
  through aliased nametable reads, controller reads, graphics setup
  (palette/nametable/sprites/NMI/OAM DMA) and the `$02FF` run-exit thunk.
- Mapper contract exercise: PRG banks 0..3, CHR 4 KiB banks 0..7 and all four
  mirroring modes replayed through the P6-02 .. P6-05 models with the expected
  deterministic states.
- Negative coverage: unsupported mnemonic, missing reset label and broken
  vector all fail closed during the build.
- Regressions: frozen NES tools plus P6-00 .. P6-05 gates pass with empty
  stderr (earlier gates re-run into ignored scratch evidence).
- Official run hashes are recorded in `p6_06_tests.json`, `official_runs.json`
  and `RESULT.md`.
- Evidence: `.openrecomp-phase6/evidence/P6-06/`.

## P6-07 outcome (PASS)

Markers: `OPENRECOMP_P6_07=PASS`,
`OPENRECOMP_PHASE6_MMC1_RECOMP_V1=PASS tests=65`; terminal and general markers
reserved as `NOT_PROVEN`.

- New bank-aware frontier (`p6_frontier_v1.py`): fixed last bank at
  `$C000-$FFFF`, mapper-selected low bank at `$8000-$BFFF`; 262 reachable
  instructions / 571 bytes, 0 dead, one unresolved indirect site at `$C089`
  (`jmp ($02FF)`) with empty targets, no interrupt sites, 14 dynamic returns.
- Neutral structure (`p6_structure_v1.py`) through the shared Phase-2 layers:
  262 instructions, 64 blocks, 15 functions, 15 translation units, 17 call
  sites, no boundary violations; pinned CFG/discovery/call-graph/units/
  classification fingerprints.
- MMC1 cartridge service (`p6_cartridge_v1.py`) implementing the Phase-5 bus
  `cpu_read`/`cpu_write` protocol over the audited P6-02 .. P6-05 models with
  an explicit `advance(cost)` cycle hook: PRG banks 0..3, CHR 4 KiB banks
  0..7, all four mirroring modes, consecutive-write suppression and a
  fail-closed `$6000-$7FFF` window.
- Host emission (`p6_emit_v1.py`): deterministic C host program through the
  frozen Phase-5 emitter (sha256 `6c1ccac5...`) with exactly one declared
  run-exit site, plus deterministic MMC1 runtime support source (sha256
  `c15980d4...`) implementing the typed runtime ABI over the MMC1 bus.
- Negative coverage: an undeclared indirect pointer, an unsupported mapper
  cartridge and a declared-PRG-RAM cartridge all fail closed.
- Regressions: frozen NES tools plus P6-00 .. P6-06 gates pass with empty
  stderr (earlier gates re-run into ignored scratch evidence).
- Official run hashes are recorded in `p6_07_tests.json`, `official_runs.json`
  and `RESULT.md`.
- Evidence: `.openrecomp-phase6/evidence/P6-07/`.

## P6-08 outcome (PASS)

Markers: `OPENRECOMP_P6_08=PASS`,
`OPENRECOMP_PHASE6_MMC1_NATIVE_V1=PASS tests=74`; terminal and general markers
reserved as `NOT_PROVEN`.

- Native build through the shared Phase-2 pipeline: `EXECUTABLE_REPRODUCIBLE`,
  two OK runs, clang-cl/lld-link toolchain, executable present.
- Three native runs byte-identical (stdout, empty stderr, exit 0): `failed=0`,
  `exit=1`, `steps=82731`, `pc=0xC089`, `frames=9`, `nmi=6`,
  `clock=241746`, `exit_arg=0x0000C089`.
- Mapper observables: `mmc1_regs=1F070703`, `prg_window_8000=3`,
  `prg_window_c000=3`, `chr_mode=1`, `mirroring=3`, `prg_ram_enabled=0`,
  5905 serial writes; RAM/PPU/state FNV digests and the 9-frame transcript
  pinned; controller transcript `0101010101010000`.
- Meaningful deterministic behaviour across bank switching, CPU, memory, PPU,
  input and timing; the original 6502 guest program is never executed directly
  (host code runs the emitted switch machine through the typed runtime ABI).
- Negative coverage: truncated ROM support generation and a missing run-exit
  thunk fail closed.
- Regressions: frozen NES tools plus the P6-06/P6-07 gates pass with empty
  stderr (earlier gates re-run into ignored scratch evidence).
- Official run hashes are recorded in `p6_08_tests.json`, `official_runs.json`
  and `RESULT.md`.
- Evidence: `.openrecomp-phase6/evidence/P6-08/`.

## P6-09 outcome (PASS)

Markers: `OPENRECOMP_P6_09=PASS`,
`OPENRECOMP_PHASE6_MMC1_REFERENCE_EQUIVALENCE_V1=PASS tests=100`; terminal and
general markers reserved as `NOT_PROVEN`.

- New independent reference driver (`.openrecomp-phase6/src/p6_reference_v1.py`)
  and gate (`tools/test_phase6_mmc1_reference_equiv_v1.py`): the frozen
  independently written `ReferenceNES6502` oracle over a local CPU bus /
  PPU / APU / OAM DMA / controller / frame+vblank+NMI model, composing the
  independently structured P6-02 .. P6-05 reference mapper models, with its own
  base-cost schedule and the declared `$C089 jmp ($02FF)` run-exit service
  interception.
- Three declared input plans (`(00,01,80)`, `(FF,FF,FF)`, `(00,11,22)`) were
  built through the native pipeline and run through the reference path; all
  four comparison categories matched exactly per plan: CPU state, RAM / PPU /
  state digests, mapper registers/shift/count/writes, PRG window banks, CHR
  banks, mirroring, nine-line frame transcript, controller transcript,
  interrupt counts (`frames=9`, `nmi=6`), `p6.exit` transcript
  (`arg=0x0000C089`) and bounded final/exit state (`steps=82731`,
  `clock=241746`).
- Primary plan support source is byte-identical to the P6-08 identity
  `c15980d4...`; host program `6c1ccac5...`; P6-08 pinned observables and
  frame transcript re-verified; the reference reproduces the same pinned
  observables.
- Schedule cross-check: the reference's own cost table covers exactly the 40
  fixture opcode forms / 262 instructions with zero mismatches against the
  frozen audited cost table; timing constants verified.
- Sensitivity: cross-plan comparison rejected; tampered NMI cost and frame
  length change observables. Negative: truncated ROM, unsupported mapper,
  battery, PRG-RAM, empty/out-of-range plan, PRG-RAM window read and CHR-ROM
  write all fail closed without traceback.
- Regressions: frozen NES tools plus P6-01 .. P6-05 gates pass with empty
  stderr (earlier gates re-run into ignored scratch evidence).
- Two official runs byte-identical raw (`0144086e...`, 4147 bytes) and LF
  (`dcfbcb01...`), empty stderr, exit 0; `p6_09_tests.json` sha256
  `cddf93dc...`.
- Evidence: `.openrecomp-phase6/evidence/P6-09/`.

## P6-10 outcome (PASS)

Markers: `OPENRECOMP_P6_10=PASS`,
`OPENRECOMP_PHASE6_PRIVATE_COMPAT_V1=PASS tests=62`; terminal and general
markers reserved as `NOT_PROVEN`.

- New private pipeline runner (`.openrecomp-phase6/src/p6_private_run_v1.py`)
  and gate (`tools/test_phase6_private_tmnt_v1.py`), metadata/derived-only.
- Private identity re-verified in place: 262160 bytes, SHA-256 `2a9345e6...`,
  NES 2.0, mapper 1/submapper 0, horizontal, 8 x 16 KiB PRG / 16 x 8 KiB CHR,
  no PRG-RAM/battery/trainer; vectors NMI `0xC3A3` / RESET `0xFFD8` /
  IRQ `0xC412`.
- Ingestion now classifies `SUPPORTED_MMC1` and the P6-07 cartridge plus the
  P6-09 reference platform construct with the expected power-on state
  (registers `0C 00 00 00`, PRG windows `(0,7)`, CHR mode 0, one-screen
  lower). The P6-01 `BLOCKED_MMC1_MAPPER_NOT_YET_IMPLEMENTED` status is
  superseded.
- Pipeline stop frontier: the frozen documented-control-flow walk fails closed
  at `0xC570` (undocumented opcode `0x7C`); the candidate traversal reaches
  1250 instructions / 2711 bytes (202 fixed, 1048 power-on low window), 42
  opcode forms and three unresolved `$E2` indirect jumps
  (`0x86E8`/`0x8956`/`0x8F3C`). The neutral structure attempt fails closed with
  `proof fixture metadata declares no data spans`; translation and native
  execution are not attempted. MMC1 runtime support generation is
  deterministic and recorded by hash only (`2e3fa4ba...`).
- Exact remaining blockers: private code/data boundary evidence, runtime
  indirect jump-table targets, runtime bank-state evidence, and (untestable
  until translation) extended platform behaviour. TMNT playability is not
  required and was not achieved.
- Frozen Phase-5 mapper and bus still fail closed on mapper 1 (preserved
  boundary). Negative: missing path, empty/out-of-range plan, invalid budget.
- Regressions: frozen NES tools plus the P6-01, P6-05 and P6-09 gates pass
  with empty stderr (re-run into ignored scratch evidence).
- Two official runs byte-identical raw (`45186d8b...`, 2886 bytes) and LF
  (`9b061b7e...`), empty stderr, exit 0; `p6_10_tests.json` sha256
  `bf18298c...`.
- Evidence: `.openrecomp-phase6/evidence/P6-10/`.

## Exact next action

Proceed to P6-11 - Evidence-driven platform expansion.
