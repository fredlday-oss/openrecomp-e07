# OPENRECOMP Phase 1 — P1-32 Evidence

Stage: `P1-32` — NES ROM ingestion + NROM/mapper abstraction

Revision: working tree at HEAD `bd5f02f` (no commit created; additive untracked files).

## Scope delivered

- `tools/nes_rom_v1.py`: documented iNES / NES 2.0 ingestion and NROM
  (mapper 0) contract, sourced from NESdev "iNES":
  - 16-byte header `$4E $45 $53 $1A`, PRG banks (16 KiB) and CHR banks (8 KiB,
    0 = CHR RAM);
  - flags 6 (nametable arrangement, battery, trainer, four-screen, mapper low
    nybble), flags 7 (VS/PlayChoice, NES 2.0 signature, mapper high nybble),
    flags 8/9/10 (PRG RAM, TV system);
  - NES 2.0 detection `(flags7 & $0C) == $08`, mapper highest nybble from
    flags 8 bits 3-0, logarithmic PRG RAM in flags 10;
  - fail closed on bad magic, short images, zero PRG banks, truncated/
    missing-trainer images and unsupported mappers at `make_mapper` (classified
    but not guessed);
  - `NromMapper`: 32 KiB PRG identity at $8000-$FFFF, 16 KiB mirroring at
    $8000/$C000, 8 KiB CHR ROM/RAM at PPU $0000-$1FFF, ignored PRG writes
    (documented: NROM has no bank registers), PRG RAM at $6000-$7FFF only when
    declared, and fail-closed windows outside the cartridge space.
- `tools/test_nes_rom_v1.py` (`OPENRECOMP_NES_ROM_V1=PASS`): synthetic ROMs
  only; header/classification/mirroring/trainer/battery/NES 2.0/NROM mapping
  pins plus fail-closed rejections.

## Files changed (this stage)

Added:
- `tools/nes_rom_v1.py`
- `tools/test_nes_rom_v1.py`

Modified:
- `tools/phase1_host_gates_v1.py` (registered `nes-rom-v1`, area `nes`)
- `SOURCE_SHA256SUMS.txt` (regenerated with `python update_sums.py`)

## Verification commands and results

```text
python tools/test_nes_rom_v1.py
OPENRECOMP_NES_ROM_V1=PASS tests=12
LOCAL_NES_ROM metadata-only sha256=2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1
  bytes=262160 mapper=1 mapper_name=unsupported prg_bytes=131072 chr_bytes=131072
  mirroring=horizontal trainer=0 battery=0 nes2=1 tv=ntsc

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=41 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

No pre-existing gate was weakened or removed.

## Semantic assumptions / documented sources

- Header layout, flags, NES 2.0 detection and cartridge layout: NESdev "iNES"
  (fetched; quoted in the loader docstring).
- Mirroring naming follows the header's documented nametable arrangement
  (bit 0 = 0 -> vertical arrangement = conventional horizontal mirroring).
- Local NES ROM is a commercial image (mapper 1, NES 2.0 header): only header
  fields and hashes are recorded; no bytes are copied into the repository.
  `make_mapper` fails closed on it as expected (mapper 1 unsupported).

## Limitations / deferred

- Only NROM (mapper 0) banking is implemented; all other mappers classify but
  fail closed (fail-closed mapper interface per SCOPE).
- Battery persistence is recorded, not persisted to disk.
- CPU RAM/PPU/APU/controller register contracts are P1-33; the headless proof
  is P1-34.

## Verdict

`PASS`
