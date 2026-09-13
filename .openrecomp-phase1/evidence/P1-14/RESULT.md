# P1-14 — Game Boy ROM ingestion + memory/platform contract

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- Modified: `tools/phase1_host_gates_v1.py` (one gate), `SOURCE_SHA256SUMS.txt` (regenerated).
- Added: `tools/gb_rom_loader_v1.py`, `tools/test_gb_rom_v1.py`.
- No commit created. No commercial ROM bytes were copied, embedded or committed;
  all fixtures are synthetic (built programmatically with the documented header
  layout and a placeholder logo — the Nintendo logo itself is never embedded).

## Deliverables

| File | Role |
| --- | --- |
| `tools/gb_rom_loader_v1.py` | documented GB cartridge header parse/classify/validate + memory-map facts + fail-closed mapper interface (RomOnly, MBC1) |
| `tools/test_gb_rom_v1.py` | 8-test deterministic gate (all synthetic inputs) |

## Documented facts implemented (public Game Boy hardware documentation)

- Header at 0x0100..0x014F: entry instruction bytes, title (0x134-0x143),
  CGB flag 0x143 (0x80 CGB-capable, 0xC0 CGB-only), SGB flag, cartridge type,
  ROM/RAM size codes, destination, licensee, version, header checksum, global
  checksum. Header checksum accumulation (x = x - byte - 1 over 0x134..0x14C)
  is enforced fail-closed.
- Cartridge-type table: ROM ONLY, MBC1/2/3/5 variants, MMM01, MBC6/7, camera,
  TAMA5, HuC1/3, each with RAM/battery/extra flags.
- ROM size codes 0x00..0x08 + 0x52/0x53/0x54; RAM size codes 0x00..0x05.
- Memory map constants: ROM 0x0000-0x7FFF (banked above 0x4000), cartridge RAM
  0xA000-0xBFFF, plus the documented WRAM echo (recorded in the loader doc;
  echo modelling is platform-stage work).
- MBC1 documented rules: RAM enable low nibble 0x0A; ROM bank register
  0x2000-0x3FFF with the documented 0->1 mapping; RAM bank 0x4000-0x5FFF;
  banking mode 0x6000-0x7FFF; advanced-mode masking.
- Classified-but-unimplemented mappers (MBC5 etc.) **fail closed** rather than
  guessing banking behaviour.
- The Nintendo logo is never embedded or verified (proprietary material);
  presence is recorded only.

## Verification

```text
python tools/test_gb_rom_v1.py
OPENRECOMP_GB_ROM_V1=PASS tests=8
```

- header-parse: entry 0xC300 (LE bytes of `nop; jp 0x0150`), title, flags,
  synthetic placeholder logo recorded as absent.
- classification: ROM ONLY/dmg; 7 documented cartridge types (0x00, 0x01,
  0x03, 0x0F, 0x13, 0x19, 0x1B); CGB mode separation dmg/cgb-compatible/
  cgb-only (0x00/0x80/0xC0).
- fail-closed rejections: short image, tampered header checksum,
  undocumented cartridge type, undocumented ROM size code, ROM-only write,
  MBC1 RAM read while disabled, MBC1 write outside the 0x0000-0x7FFF window,
  MBC5 `make_mapper` (classified but not implemented).
- MBC1 documented rules: enable pattern, bank-0-selects-1, ROM/RAM bank
  switching, advanced mode, per-bank RAM isolation.

Full host-gate regression:

```text
python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=26 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

`SOURCE_SHA256SUMS.txt` regenerated (`update_sums.py`); integrity gate passes.

## Semantic assumptions

- Header checksum mismatch is treated as a malformed-ROM rejection (fail
  closed), matching the repository's deterministic-ingestion policy for ELF.
- Battery persistence, RTC and MBC2/3/5 banking are recorded in the
  classification and fail closed; no banking behaviour is guessed.
- No commercial ROM was needed for any part of this stage (ROM_PATHS.md
  rule 7); local ROMs remain external inputs for P1-15 metadata only.

## Remaining limitations

- WRAM echo, OAM/I/O/HRAM behaviour and PPU/APU/timer surfaces belong to the
  platform stage (P1-15).
- MBC1 is implemented; MBC2/3/5 etc. remain classified-only (SCOPE allows
  bounded MBC1 "if evidence/tests are available" — the synthetic tests above
  are that evidence).

## Verdict

`PASS` — documented GB cartridge ingestion, classification and the no-MBC +
bounded MBC1 mapper contract are pinned by a deterministic synthetic-only
gate with fail-closed behaviour throughout.
