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

## Exact next action

Proceed to P6-03 - MMC1 PRG banking.
