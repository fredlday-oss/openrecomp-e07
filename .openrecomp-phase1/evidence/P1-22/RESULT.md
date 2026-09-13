# P1-22 — Master System ROM/banking/I-O platform contract

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- No commit created. No ROM bytes copied, committed, or modified.

## Files changed

| File | Change |
| --- | --- |
| `tools/sms_platform_v1.py` | Added: SMS ROM ingestion/classification, documented Sega mapper, memory map, VDP control/data port protocol, PSG surface, controller ports, port decode with documented mirrors. |
| `tools/test_sms_platform_v1.py` | Added: 30-test deterministic gate `OPENRECOMP_SMS_PLATFORM_V1=PASS`. |
| `tools/phase1_host_gates_v1.py` | Registered gate `sms-platform-v1` (area "master-system"). |
| `SOURCE_SHA256SUMS.txt` | Regenerated via `python update_sums.py`. |

## Documented facts implemented (public references, fetched this session)

- SMS Power! Development pages: MemoryMap, Mappers (Sega mapper), ROMHeader,
  ControlPort, PeripheralPorts, RAM; plus the official SMS developer
  documents excerpted on SMSOfficialDocs. All quoted facts recorded below.
- Memory map: `$0000-$03ff` ROM unpaged (fixed first 1 KiB); `$0400-$3fff`
  mapper slot 0; `$4000-$7fff` slot 1; `$8000-$bfff` slot 2; `$c000-$dfff`
  system RAM; `$e000-$ffff` RAM mirror; `$fff8` 3D-glasses control
  (`$fff9-$fffb` mirrors); `$fffc` RAM/misc control; `$fffd`/`$fffe`/`$ffff`
  slot 0/1/2 controls. Control registers overlap the RAM mirror: writes
  affect the device AND RAM, reads return RAM.
- Sega mapper: four 16 KiB slots, any ROM bank into any of the first three;
  first 1 KiB of slot 0 always fixed; `$fffc` bit 7 = "ROM write" enable,
  bit 4 = RAM enable over `$c000-$ffff`, bit 3 = RAM enable over slot 2,
  bit 2 = RAM bank select, bits 1-0 = bank shift (added to values written
  to `$fffd-$ffff`); ROM mirroring nullifies out-of-range bank bits;
  315-5235 reset state `fffc=00, fffd=00, fffe=01, ffff=02`.
- ROM header: optional; `TMR SEGA` at `$7ff0` (also `$3ff0`/`$1ff0`),
  little-endian checksum word at `+$0a`, product code/version/region+size
  nibbles at `+$0c..$0f`; region codes 3=SMS Japan, 4=SMS Export, 5=GG
  Japan, 6=GG Export, 7=GG International; size codes A-2 = 8 KiB..1 MiB.
  Checksum mismatch is recorded, not rejected (documented: many headers
  contain mistakes; only the export BIOS enforces it, and no BIOS is
  modelled).
- I/O ports (only A7-A0 decoded; A0 selects within each pair group):
  `$3e` memory enables (bit 4 = RAM, bit 1 = cartridge, bit 0 = BIOS —
  BIOS/card/external slots recorded, not modelled), `$3f` joystick-port
  control (defaults input-only = `$0f`), `$7e`/`$7f` light-phaser reads and
  PSG write (`$7f`), `$be`/`$bf` VDP data/control, `$dc`/`$dd` controller
  ports. Documented mirrors: odd `$01-$3f`, odd `$41-$7f`, odd `$81-$bf`,
  even `$c0-$fe`, odd `$c1-$ff`.
- VDP control port: two-byte control word, low byte first; second byte
  `%CCAAAAAA` (code 00=VRAM read address with documented prefetch +
  increment, 01=VRAM write address, 10=register write — first byte = data,
  address bits 11-8 = register number, 11=CRAM write address); data port
  read returns the buffer then prefetches (documented one-byte lag); writes
  go to VRAM (or CRAM when code=11, masked to 64 bytes); address
  auto-increments wrapping at `$3fff`; status reads return bit 7 VBlank /
  bit 6 sprite overflow / bit 5 collision / bits 4-0 fifth sprite and
  reset the flags; data/control-port reads and data writes clear the
  second-byte flag; software may write only the first byte to update the
  low address bits.
- PSG: documented latch protocol (bit 7 = latch with bits 6-4 selecting
  the register, data writes follow); 8-register deterministic surface;
  audio synthesis deferred.
- Controller ports: `1 = not pressed` for all documented button/TH/CONT/
  reset bits; default `$ff`.

## Fail-closed behaviour (documented limitations)

- ROM size must be a positive multiple of 16 KiB, at most 1 MiB;
  undocumented size codes with a known region are rejected.
- Cartridge RAM (mapper `$fffc` bits 3/4) is classified but absent: any
  access that would map it raises `SMSPlatformError`.
- ROM writes raise while `$fffc` bit 7 is clear (documented write protect;
  the documented "ROM write" enable is implemented).
- System RAM disabled via port `$3e` bit 4, or the cartridge disabled via
  bit 1, raises on access (documented feature, unused by software).
- BIOS ROM, 3D-glasses hardware, light phaser, FM unit, TH-pin hardware
  interaction, cycle-perfect VDP/audio: deferred, recorded in RESULT.

## Verification

```text
python tools/test_sms_platform_v1.py
OPENRECOMP_SMS_PLATFORM_V1=PASS tests=30
(run twice: output sha256 B1FC438E6F51999AC01F95A6AC583298A5E61B95C8F7E472BE019B3A8809AB02)

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=34 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

## Local ROM evidence (metadata only, external input never copied)

Primary: `D:\OpenRecomp\roms\phase1\master-system\primary\Ninja, The (USA, Europe, Brazil) (En).sms`

```text
sha256 = 56015cea41324003e2ed1b9f0fb35d6feb47d2461962df4cc89c5c5645eada85
bytes  = 131072 (8 x 16 KiB banks)
python tools/sms_platform_v1.py <rom>
SMS_ROM_HEADER_PRESENT=1
SMS_ROM_REGION=sms-export
SMS_ROM_BANKS=8
SMS_ROM_CHECKSUM_VALID=0   (documented: many headers contain mistakes)
OPENRECOMP_SMS_PLATFORM_V1=PASS
```

## Next

P1-23 (SMS deterministic headless proof: wire the Z80 reference/frontend to
this platform contract), then P1-24 (Z80/SMS regression + differential
audit).
