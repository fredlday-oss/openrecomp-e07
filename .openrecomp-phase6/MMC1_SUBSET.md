# OpenRecomp Phase 6 MMC1 Supported Subset

Claim label: `MMC1_SUBSET_V1`. Machine-readable source of truth:
`.openrecomp-phase6/src/p6_mmc1_spec_v1.py`; requirement inventory IDs are
pinned by the P6-01 gate.

## Scope

This document defines the exact MMC1/mapper-1 behaviour Phase 6 commits to
implement and prove, and the behaviour it explicitly does not support. It
contains no execution model; P6-02 .. P6-05 implement this contract and prove
it against independent reference vectors and, finally, exact runtime
equivalence for the public fixture.

## Registers

Four 5-bit internal registers are selected by CPU address bits 14:13 across
the write window `$8000-$FFFF`:

| Register | Write window | Purpose |
| --- | --- | --- |
| control | `$8000-$9FFF` | mirroring (bits 1:0), PRG mode (bits 3:2), CHR mode (bit 4) |
| chr_bank_0 | `$A000-$BFFF` | CHR bank for `$0000` (4 KiB mode) / 8 KiB bank register |
| chr_bank_1 | `$C000-$DFFF` | CHR bank for `$1000` (4 KiB mode); unused in 8 KiB mode |
| prg_bank | `$E000-$FFFF` | 16 KiB PRG bank for the switchable window |

## Serial protocol (P6-02)

1. Write bit 0 is the data bit; the register commits on the fifth write,
   least-significant bit first.
2. A write with bit 7 set resets the shift register.
3. Writes on consecutive CPU cycles are suppressed: a write that lands on the
   CPU cycle immediately after another MMC1 write is ignored and leaves all
   state, including the last-write cycle, unchanged. The exact suppression
   model is proven by P6-02 differential vectors.
4. Power-on state: shift register cleared, control register `0x0C` (PRG mode
   3, CHR mode 0, one-screen lower mirroring), all other registers `0`.

## Control register

- Mirroring: `0` one-screen lower, `1` one-screen upper, `2` vertical,
  `3` horizontal.
- PRG mode: `0`/`1` 32 KiB switch at `$8000` (bank low bit ignored);
  `2` fix first bank at `$8000`, switch 16 KiB at `$C000`; `3` fix last bank
  at `$C000`, switch 16 KiB at `$8000`.
- CHR mode: `0` one 8 KiB bank from the CHR bank 0 register shifted right by
  one; `1` two independent 4 KiB banks from the CHR bank 0/1 registers.

## PRG banking (P6-03)

- 16 KiB bank selection by the PRG register low bits; masking to the declared
  PRG ROM size is proven by bounded reference vectors.
- Supported PRG ROM sizes: 16 KiB .. 256 KiB in exact 16 KiB banks with a
  power-of-two bank count (1, 2, 4, 8, 16). Larger or non-power-of-two ROMs
  are classified unsupported and fail closed.
- Bank masking rule: the selected bank is `register & (bank_count - 1)`.
  32 KiB modes ignore the register low bit; mode 2 fixes bank 0 at
  `$8000-$BFFF`; mode 3 fixes the last bank at `$C000-$FFFF`.

## CHR banking and mirroring (P6-04)

- Supported CHR ROM sizes: 8 KiB .. 128 KiB in exact 8 KiB banks with a
  power-of-two bank count (1, 2, 4, 8, 16); CHR-RAM boards, absent CHR ROM
  and non-power-of-two bank counts are classified unsupported.
- CHR mode 0: 8 KiB bank = `chr_bank_0 >> 1`, masked to the 8 KiB bank count.
- CHR mode 1: two 4 KiB banks from `chr_bank_0` and `chr_bank_1`, masked to
  twice the 8 KiB bank count.
- All four mirroring settings are in the supported subset. Nametable mapping
  covers `$2000-$3EFF`: one-screen lower/upper fix all four logical nametables
  to physical table 0/1; vertical selects on address bit 10; horizontal
  selects on address bit 11. Nametable address offsets are
  `table * 0x400 + (address & 0x3FF)`; the palette window `$3F00-$3FFF` is a
  separate pass-through and other addresses fail closed.

## PRG-RAM and variants (P6-05)

- The supported fixture declares no PRG-RAM/NVRAM and no battery. Declared
  PRG-RAM, battery-backed NVRAM and board wiring are never inferred.
- Explicitly unsupported: MMC1A/MMC1B/MMC1C differences, SUROM/SXROM/SOROM
  and 512 KiB wiring variants, CHR-RAM boards, four-screen/VS/PlayChoice
  layouts, write-protection and board-specific bus conflicts.

## Claim boundary

A P6-99 PASS may only claim the bounded audited public MMC1
static-recompilation proof. It never implies general NES compatibility, all
MMC1 boards or revisions, all NES games, commercial-game compatibility, cycle
accuracy, full PPU/APU accuracy, FDS compatibility or arbitrary 6502
compatibility. `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`
remains permanent.
