# OPENRECOMP Phase 1 — P1-33 Evidence

Stage: `P1-33` — NES CPU-facing PPU/APU/controller contracts

Revision: working tree at HEAD `bd5f02f` (no commit created; additive untracked files).

## Scope delivered

- `tools/nes_platform_v1.py`: documented NES CPU bus and CPU-facing register
  surfaces, sourced from NESdev "CPU memory map", "PPU registers" and
  "Standard controller":
  - CPU map: 2 KiB RAM ($0000-$07FF) mirrored through $1FFF; PPU registers
    $2000-$2007 mirrored through $3FFF; APU/IO $4000-$4017; $4018-$401F
    disabled; $4020-$5FFF expansion; $6000-$FFFF via the `nes_rom_v1` mapper.
    Disabled/expansion access fails closed.
  - PPU registers: PPUCTRL, PPUMASK, PPUSTATUS (vblank read-and-clear + write
    latch clear), OAMADDR, OAMDATA (write increments, read does not),
    PPUSCROLL (two writes), PPUADDR (two writes high/low), PPUDATA (one-byte
    read buffer, palette immediate reads, 1/32 increment).
  - PPU memory: CHR via the mapper; 2 KiB nametable VRAM with the documented
    horizontal/vertical arrangement mapping; 32-byte palette with
    $3F10/$3F14/$3F18/$3F1C universal-background mirrors; $3000-$3EFF mirrors;
    greyscale read masking.
  - OAMDMA ($4014) page copy; deterministic APU register/status/frame-counter
    latch surface ($4000-$4013, $4015, $4017).
  - Standard controller: $4016 strobe (1/0 latch), read order A, B, Select,
    Start, Up, Down, Left, Right; $40 open-bus bits; documented all-1 tail;
    controller 2 via $4017.
- `tools/test_nes_platform_v1.py` (`OPENRECOMP_NES_PLATFORM_V1=PASS`) with
  synthetic NROM images only.

## Files changed (this stage)

Added:
- `tools/nes_platform_v1.py`
- `tools/test_nes_platform_v1.py`

Modified:
- `tools/phase1_host_gates_v1.py` (registered `nes-platform-v1`, area `nes`)
- `SOURCE_SHA256SUMS.txt` (regenerated with `python update_sums.py`)

## Verification commands and results

```text
python tools/test_nes_platform_v1.py
OPENRECOMP_NES_PLATFORM_V1=PASS tests=10
LOCAL_NES_ROM metadata-only sha256=2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1
  mapper=1 prg_bytes=131072 chr_bytes=131072 mirroring=horizontal nes2=1 tv=ntsc

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=42 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

No pre-existing gate was weakened or removed.

## Semantic assumptions / documented sources

- PPU register semantics, PPUDATA read buffer, palette mirroring, OAMDMA:
  NESdev "PPU registers" (fetched; quoted in the module docstring).
- Controller report order/strobe/open-bus/all-1 tail: NESdev "Standard
  controller" (fetched; quoted).
- Nametable arrangement mapping follows the iNES header bit 0 convention
  documented by NESdev (bit 0 = 0 -> vertical arrangement = conventional
  horizontal mirroring).
- Local NES ROM (mapper 1) is metadata-only; `make_mapper` fails closed on it.

## Limitations / deferred

- No cycle-perfect PPU/APU; sprite-0 hit/overflow timing, OAM decay and
  DPCM read conflicts are not modelled.
- Four-screen VRAM is not modelled (fails closed; only 2 KiB VRAM present).
- Non-NROM mappers classify but fail closed (deferred by SCOPE).

## Verdict

`PASS`
