# OpenRecomp Phase 1 â€” Local ROM Paths

ROM_ROOT: $RomRoot

These files are **external local verification inputs only**.

## Platform paths

GAME_BOY_PRIMARY: $RomRoot\gameboy\primary
GAME_BOY_ADDITIONAL: $RomRoot\gameboy\additional

GAME_BOY_COLOR_PRIMARY: $RomRoot\gameboy-color\primary
GAME_BOY_COLOR_ADDITIONAL: $RomRoot\gameboy-color\additional

MASTER_SYSTEM_PRIMARY: $RomRoot\master-system\primary
MASTER_SYSTEM_ADDITIONAL: $RomRoot\master-system\additional

NES_PRIMARY: $RomRoot\nes\primary
NES_ADDITIONAL: $RomRoot\nes\additional

## Allowed extensions

Game Boy: .gb
Game Boy Color: .gbc
Master System: .sms, .bin when positively identified as SMS
NES: .nes

## Mandatory handling rules

1. Do not copy ROMs into D:\OpenRecomp\openrecomp-e07.
2. Do not commit ROMs.
3. Do not modify original ROM files.
4. Prefer one ROM in each primary folder as the first compatibility target.
5. Use dditional ROMs only after the primary target has a stable evidence-backed path.
6. Record only metadata/evidence such as filename, byte size, SHA-256, detected format/header details, and test result.
7. Never require a commercial ROM to prove CPU semantics when a synthetic/open test can provide the same proof.
8. If a ROM requires unsupported cartridge hardware, classify the exact requirement rather than silently implementing guessed behavior.
9. Never treat successful loading alone as proof of correct recompilation.
10. Run .openrecomp-phase1\UPDATE_ROM_INVENTORY.ps1 whenever ROM contents change.

## Discovery

Before a platform proof begins, OpenCode should:
- inspect the platform's primary folder;
- select the single primary ROM if exactly one exists;
- if multiple primary ROMs exist, choose the lexically first for deterministic behavior and note that in evidence;
- use dditional only for regression/compatibility expansion;
- run/update the inventory before recording ROM evidence.
