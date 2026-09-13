# P1-16 — Game Boy Color bounded platform-mode proof

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- Modified: `tools/gb_platform_v1.py` (mode separation + CGB surfaces),
  `tools/test_gb_headless_v1.py` (builder gained `cgb_flag` parameter only),
  `tools/phase1_host_gates_v1.py` (one gate), `SOURCE_SHA256SUMS.txt`
  (regenerated).
- Added: `tools/test_gb_mode_v1.py`.
- No commit created. No commercial ROM bytes copied/embedded/committed; the
  GBC ROM is metadata-only evidence (hash, size, header fields, classifier).

## Deliverables

| File | Role |
| --- | --- |
| `tools/gb_platform_v1.py` | `select_platform_mode()` documented mode-selection API; `GBPlatform(mode=...)` with CGB-only surfaces (KEY1/VBK/SVBK, VRAM + WRAM banking, double-speed timer rates, armed-STOP speed switch in the driver) |
| `tools/test_gb_mode_v1.py` | 11-test deterministic gate `OPENRECOMP_GB_MODE_V1=PASS` |

## Documented facts implemented (gbdev.io Pan Docs: CGB Registers, Cartridge Header, Memory Map)

- Mode selection: CGB hardware interprets header byte 0x0143 — bit 7 set
  triggers CGB mode (the value is written to KEY0); otherwise "Non-CGB"
  compatibility mode. `$C0` functions the same as `$80` (bit 6 ignored).
  Monochrome hardware always runs DMG mode. (`select_platform_mode`)
- KEY1 (0xFF4D, CGB only): bit 7 read-only current speed, bit 0 R/W
  switch-armed. The switch is performed by a `stop` executed with bit 0 set;
  afterwards bit 0 is cleared automatically, the CPU operates at the other
  speed and the divider is reset (divider does not tick during the stop).
  The documented 2050 M-cycle pause duration is not modelled.
- VBK (0xFF4F, CGB only): only bit 0 matters on writes; reads return the
  current bank in bit 0 with all other bits set to 1.
- SVBK (0xFF70, CGB only): writing maps a WRAM bank to D000-DFFF, except 0
  which maps bank 1; bank 0 is always at C000-CFFF.
- VRAM: "In CGB mode, switchable bank 0/1" via VBK.
- Echo RAM: "All reads and writes to this range have the same effect as reads
  and writes to C000-DDFF" — implemented so the echo follows the mapped
  D000-DFFF bank in CGB mode.
- Double speed: timer and divider operate twice as fast (DIV 32768 Hz; TIMA
  8192/524288/131072/32768 Hz) — the documented frequency table folded into
  the T-cycle model (periods halved).
- DMG mode: KEY1/VBK/SVBK are CGB-only and fail closed (our documented
  choice for unmodelled I/O, consistent with P1-15).

Not modelled (documented limitations): KEY0 itself (not officially
documented, written by the boot ROM and locked), the post-STOP pause
duration, HDMA/IR/palette registers (PPU/serial deferred).

## Verification

```text
python tools/test_gb_mode_v1.py
OPENRECOMP_GB_MODE_V1=PASS tests=11

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=28 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

Gate determinism: two runs byte-identical
(`sha256 = 9699709491CDFC47567BD51FD235DF3081D45F42988E084F805E83FBC05F182C`).

## Pinned deterministic results

- mode selection: 0x00/0x01/0x40 -> dmg on both hardware models; 0x80/0xC0 ->
  cgb on CGB hardware, dmg on DMG hardware; unknown hardware / out-of-range
  flag fail closed.
- dmg: KEY1/VBK/SVBK read+write fail closed (6 rejections).
- KEY1: 0x00 initial; write 0xFF -> 0x01 (masked); write 0x00 -> 0x00.
- VBK: 0xFE initial; write 0xFF -> bank 1 (read 0xFF); VRAM 0x8000 holds
  0x11 in bank 0 and 0x22 in bank 1; write 0x02 -> back to bank 0 (0x11).
- SVBK: bank 3 write -> 0xD000 holds 0x33; write 0x00 -> bank 1 (0x11);
  0xC000 stays 0xAA across switching; echo 0xE000==0xAA, 0xF000==0x11
  (same effect as C000-DDFF).
- speed switch: armed -> speed 2, KEY1 reads 0x80, divider reset to 0;
  unarmed switch and DMG switch fail closed.
- double speed: DIV +1 per 128 T; TIMA (select 00) +1 per 512 T.
- driver end-to-end: `LDH (0xFF4D),A; STOP` in cgb mode -> speed 2, armed
  cleared, execution resumes after the stop (A=0x2B, halted=1); the same
  program on a dmg platform fails closed (KEY1 write); unarmed STOP stays a
  halt with speed 1.

## Local-only GBC ROM metadata evidence (never bytes)

`D:\OpenRecomp\roms\phase1\gameboy-color\primary\Return of the Ninja (USA).gbc`:
`sha256=ebe140f2c6dcd4e99192d5676b4cfe443a071daa9ff243a23a26ae98a53fead8`
(matches `ROM_INVENTORY.json`), 1048576 bytes, title `NINJA` + manufacturer
code `BNJE`, classifier `mapper=mbc5 cgb_mode=cgb-only rom_banks=64
ram_banks=0`, header checksum valid. MBC5 execution is out of scope (mapper
classified but not implemented; fails closed in the P1-14 loader).

## Semantic assumptions and boundaries

- The platform-mode proof is about *selection and surface separation*, not
  CGB game execution: the CGB-only surfaces follow their documented bit
  contracts; PPU/palette/HDMA/IR surfaces remain deferred and fail closed.
- The speed-switch pause (2050 M-cycles) and KEY0 are documented but not
  modelled; no cycle-perfect claims.
- SVBK reads return the written bank value (bits 0-2); unused-bit read
  behaviour is not pinned by the tests.

## Verdict

`PASS` — GB vs GBC platform selection is pinned by the documented header-bit
rule and hardware model, the documented CGB-only register surfaces are
separated from DMG mode (fail closed), VRAM/WRAM banking and the speed switch
follow their documented contracts, and all results are deterministic with
synthetic inputs only.
