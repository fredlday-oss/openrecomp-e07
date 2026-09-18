# P6-10 Private TMNT Compatibility Run - Result

Verdict: `PASS`

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-09 boundary commit
  `3f3c45a7f4fe3cecf7b92c6b275cae6866050ebb`, tree
  `aafe632a09b8067e111a5bb1d498cf824208db4a` (Phase-5 frozen boundary
  `e8d3627a622d0ca3196b117c5112f29fabdb49e7`; tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Use only the existing private local TMNT path. Re-run the
ingestion/frontier/translation/runtime pipeline now that MMC1 exists. Record
only hashes, metadata, counts, addresses, classifications and stop reasons.
Determine exactly what next blocks execution. TMNT playability is not required
for Phase-6 PASS.

## Changes (additive)

- `.openrecomp-phase6/src/p6_private_run_v1.py`: new private compatibility
  pipeline runner (metadata/derived-only; ROM bytes never returned, stored or
  echoed).
- `tools/test_phase6_private_tmnt_v1.py`: new P6-10 gate.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`, `HANDOFF.md`: stage bookkeeping.
- No frozen file was modified. The private image was read in place; no copy
  exists anywhere in the repository or evidence.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-10
  --script tools/test_phase6_private_tmnt_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-10 --tests-json p6_10_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 2886 bytes raw, raw sha256
    `45186d8b764977a44988a4bc8c1dcf2c6ee1e823b2bf0055e265b858c44ac23c`,
    LF sha256
    `9b061b7ea851550a028b3ad0542202d50b715be49fac12a454076a38e5ac2406`.
  - `p6_10_tests.json` sha256
    `bf18298cb2a90e70802ff79bd84185ac984534578dd0e06016cb2dcbf8468507`,
    `tests=62`.
- Markers: `OPENRECOMP_P6_10=PASS`,
  `OPENRECOMP_PHASE6_PRIVATE_COMPAT_V1=PASS tests=62`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Private fixture identity (re-verified, not copied)

`PRIVATE_LOCAL_COMPATIBILITY_FIXTURE`, path
`D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes`, 262160 bytes, SHA-256
`2a9345e6...`, NES 2.0 container, mapper 1 / submapper 0, horizontal
mirroring, 8 x 16 KiB PRG (`2fbc367a...`), 16 x 8 KiB CHR (`f9e354d5...`), no
PRG-RAM/battery/trainer/four-screen. Power-on fixed-last-bank vectors NMI
`0xC3A3` / RESET `0xFFD8` / IRQ `0xC412`.

## Pipeline re-run result

- Ingestion: `SUPPORTED_MMC1` (MMC1_SUBSET_V1, no reasons), power-on control
  `0x0C`, PRG mode 3, CHR mode 0, one-screen lower mirroring; variant profile
  `discrete_mmc1_chr_rom_no_wram`. The P6-01 recorded status
  `BLOCKED_MMC1_MAPPER_NOT_YET_IMPLEMENTED` is superseded: the mapper now
  exists and is differentially verified through P6-09.
- Cartridge service (P6-07): constructs, power-on registers
  `{control: 0C, chr0: 0, chr1: 0, prg: 0}`, PRG windows `(0, 7)`, CHR mode 0,
  one-screen lower, PRG-RAM disabled.
- Independent reference platform (P6-09): same power-on state and the reset
  vector reads back as `0xFFD8`.
- Frontier: the frozen documented-control-flow walk fails closed at `0xC570`
  (`undocumented 6502 opcode 0x7C`). The bounded candidate traversal reaches
  1250 instructions / 2711 bytes (202 fixed-window, 1048 power-on low-window),
  42 opcode forms, stops with 11 pending and 42 dynamic returns; it records
  three unresolved indirect jumps (`0x86E8`, `0x8956`, `0x8F3C`, all through
  zero-page pointer `0x00E2`) and no interrupt sites.
- Structure: fails closed with `proof fixture metadata declares no data spans`
  (no private code/data boundary evidence exists).
- Translation: `NOT_ATTEMPTED` (no complete reachable instruction set; no
  fabricated targets). Native build/execution: not reached.
- Runtime: MMC1 runtime support generation for the private image is
  deterministic, sha256 `2e3fa4ba...` (generated in memory only; no source
  stored or echoed).
- Preserved Phase-5 boundary: the frozen NROM mapper and the frozen Phase-5
  cartridge both still fail closed on mapper 1.

## Exact remaining blockers

1. `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` (frontier): reachable decode fails
   closed at `0xC570` after a `jsr` from `0xC56D`; private code/data boundary
   evidence is required to complete code discovery.
2. `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` (indirect control flow): three
   runtime jump-table sites through `$E2` cannot be resolved statically and are
   never guessed.
3. `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` (bank state): 1048 candidate
   instructions touch the mapper-switched `$8000-$BFFF` window under the
   power-on bank only; the actual bank sequence needs runtime bank-state
   evidence.
4. `NOT_TESTED` (runtime platform): PPU/APU/input/timing requirements beyond
   the bounded platform model cannot be assessed until translation completes.
5. `SUPERSEDED` (mapper): the P6-01 mapper blocker no longer applies.

## Negative / fail-closed coverage

Missing private path, empty input plan, out-of-range plan value and invalid
frontier budget all fail closed without traceback. Evidence hygiene: no ROM
bytes, no first/last 16 KiB bank bytes in any evidence file.

## Regressions

`tools/test_nes_rom_v1.py`, `tools/test_nes_platform_v1.py` and the Phase-6
P6-01 inventory, P6-05 variant and P6-09 independent reference equivalence
gates all exit 0 with empty stderr (earlier gates re-run into ignored scratch
evidence; committed evidence untouched).

## Limitations

- The private image is not playable and no compatibility claim is derived from
  this analysis; TMNT playability is not required for Phase-6 PASS.
- The candidate traversal is a CANDIDATE / NOT PROVEN analysis artifact; the
  authoritative frontier result is the fail-closed frozen walk.
- No general NES compatibility, no MMC1 board-variant coverage, no cycle or
  full PPU/APU accuracy is claimed. The terminal marker remains `NOT_PROVEN`.

## Repository side effects

- Tracked additive changes: new pipeline runner, new gate, updated manifest and
  control plane, P6-10 evidence. Untracked scratch/build artifacts remain
  ignored; no ROM copy exists in the repository or evidence.

## Evidence index

`RESULT.md`, `p6_10_tests.json`, `official_runs.json`, `determinism.json`,
`tmnt_pipeline.json`, `blockers.json`, `regressions.json`, `run1.txt`,
`run2.txt`, `run1.err.txt`, `run2.err.txt`, `changed_files.txt`.

## Next stage

P6-11 - Evidence-driven platform expansion.
