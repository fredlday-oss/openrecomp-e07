#!/usr/bin/env python3
"""P1-16 gate: Game Boy Color bounded platform-mode proof.

Pins the documented GB vs GBC platform selection and the documented CGB-only
surfaces with synthetic, original inputs only:

- mode selection: header byte 0x0143 bit 7 enables CGB mode on CGB hardware
  ($C0 functions the same as $80 — the hardware ignores bit 6); monochrome
  hardware always runs in DMG mode;
- DMG/CGB surface separation: KEY1 (0xFF4D), VBK (0xFF4F) and SVBK (0xFF70)
  fail closed in DMG mode and follow their documented bit contracts in CGB
  mode;
- documented VRAM banking (VBK bit 0 selects VRAM bank 0/1) and WRAM banking
  (SVBK maps banks 1-7 at D000-DFFF, bank 0 fixed at C000-CFFF; echo mirrors
  C000-DDFF with the same effect);
- documented KEY1 speed switch: armed bit 0 + `stop` performs the switch,
  clears bit 0, toggles the read-only speed bit and resets the divider;
  timer/divider then run at the documented doubled frequencies;
- fail-closed handling: unknown hardware models, out-of-range flags,
  CGB-only register access on DMG, speed switch without the arm bit or in
  DMG mode;
- secondary local GBC-ROM metadata evidence (never bytes).

Documented facts follow the gbdev.io Pan Docs pages for CGB Registers, the
Cartridge Header and the Memory Map.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from gb_rom_loader_v1 import classify, parse_header  # noqa: E402
from gb_platform_v1 import (  # noqa: E402
    ADDR_DIV,
    ADDR_KEY1,
    ADDR_SVBK,
    ADDR_TAC,
    ADDR_VBK,
    GBPlatform,
    GBPlatformError,
    PlatformBoundSM83,
    map_rom_romonly,
    run_headless,
    select_platform_mode,
)
from sm83_reference_v1 import SM83State  # noqa: E402
from test_gb_headless_v1 import build_boot_rom  # noqa: E402


def expect_fail(label: str, action) -> None:
    try:
        action()
    except GBPlatformError:
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"{label}: accepted")


def main() -> int:
    tests = 0

    # 1. Documented mode-selection rule -----------------------------------
    assert select_platform_mode(0x00, "dmg") == "dmg"
    assert select_platform_mode(0x80, "dmg") == "dmg"
    assert select_platform_mode(0xC0, "dmg") == "dmg"
    assert select_platform_mode(0x00, "cgb") == "dmg"
    assert select_platform_mode(0x01, "cgb") == "dmg"
    assert select_platform_mode(0x40, "cgb") == "dmg"
    assert select_platform_mode(0x80, "cgb") == "cgb"
    assert select_platform_mode(0xC0, "cgb") == "cgb"  # documented: bit 6 ignored
    expect_fail("unknown-hardware-model", lambda: select_platform_mode(0x80, "snes"))
    expect_fail("cgb-flag-out-of-range", lambda: select_platform_mode(0x100, "cgb"))
    print("PASS mode selection: header bit 7 + hardware (documented KEY0 rule)")
    tests += 1

    # 2. Header/classification integration ---------------------------------
    for flag, expected in ((0x00, "dmg"), (0x80, "cgb-compatible"), (0xC0, "cgb-only")):
        rom = build_boot_rom(cgb_flag=flag)
        info = classify(rom)
        assert info.cgb_mode == expected, (flag, info.cgb_mode)
        mode = select_platform_mode(parse_header(rom).cgb_flag, "cgb")
        assert mode == ("cgb" if flag & 0x80 else "dmg"), (flag, mode)
    print("PASS header flag -> classifier -> platform mode separation")
    tests += 1

    # 3. CGB-only register surfaces fail closed on DMG ----------------------
    dmg = GBPlatform(map_rom_romonly(build_boot_rom()), mode="dmg")
    expect_fail("dmg-key1-read", lambda: dmg.read8(ADDR_KEY1))
    expect_fail("dmg-key1-write", lambda: dmg.write8(ADDR_KEY1, 0x01))
    expect_fail("dmg-vbk-read", lambda: dmg.read8(ADDR_VBK))
    expect_fail("dmg-vbk-write", lambda: dmg.write8(ADDR_VBK, 0x01))
    expect_fail("dmg-svbk-read", lambda: dmg.read8(ADDR_SVBK))
    expect_fail("dmg-svbk-write", lambda: dmg.write8(ADDR_SVBK, 0x03))
    print("PASS dmg mode: CGB-only registers fail closed")
    tests += 1

    # 4. Documented KEY1 surface (CGB) --------------------------------------
    cgb = GBPlatform(map_rom_romonly(build_boot_rom(cgb_flag=0x80)), mode="cgb")
    assert cgb.read8(ADDR_KEY1) == 0x00  # normal speed, not armed
    cgb.write8(ADDR_KEY1, 0xFF)  # only bit 0 is writable
    assert cgb.read8(ADDR_KEY1) == 0x01
    cgb.write8(ADDR_KEY1, 0x00)
    assert cgb.read8(ADDR_KEY1) == 0x00
    print("PASS cgb KEY1: armed bit 0 writable, bit 7 read-only speed")
    tests += 1

    # 5. Documented VBK surface + VRAM banking (CGB) ------------------------
    assert cgb.read8(ADDR_VBK) == 0xFE  # bank 0, other bits read 1
    cgb.write8(0x8000, 0x11)  # VRAM bank 0
    cgb.write8(ADDR_VBK, 0xFF)  # only bit 0 matters -> bank 1
    assert cgb.vbk == 1 and cgb.read8(ADDR_VBK) == 0xFF
    cgb.write8(0x8000, 0x22)  # VRAM bank 1
    assert cgb.read8(0x8000) == 0x22
    cgb.write8(ADDR_VBK, 0x02)  # -> bank 0
    assert cgb.read8(0x8000) == 0x11
    print("PASS cgb VBK: VRAM bank 0/1 separation")
    tests += 1

    # 6. Documented SVBK surface + WRAM banking + echo (CGB) ------------------
    cgb.write8(0xC000, 0xAA)  # WRAM bank 0 (fixed at C000-CFFF)
    cgb.write8(0xD000, 0x11)  # mapped bank 1 (default)
    cgb.write8(ADDR_SVBK, 0x03)
    assert cgb.read8(ADDR_SVBK) == 0x03
    cgb.write8(0xD000, 0x33)  # bank 3
    assert cgb.read8(0xD000) == 0x33
    cgb.write8(ADDR_SVBK, 0x00)  # documented: 0 maps bank 1
    assert cgb.read8(0xD000) == 0x11
    assert cgb.read8(0xC000) == 0xAA  # bank 0 untouched by switching
    assert cgb.read8(0xE000) == 0xAA  # documented echo: same effect as C000
    assert cgb.read8(0xF000) == 0x11  # echo mirrors the currently mapped D000 window
    print("PASS cgb SVBK: WRAM banks 1-7 + fixed bank 0 + echo equivalence")
    tests += 1

    # 7. Documented speed switch (KEY1 + STOP) -------------------------------
    cgb.write8(ADDR_KEY1, 0x01)  # arm
    cgb.write8(ADDR_DIV, 0xFF)
    cgb.div = 0x7F  # dirty the divider to observe the documented reset
    cgb.complete_speed_switch()
    assert cgb.speed == 2
    assert cgb.read8(ADDR_KEY1) == 0x80  # armed cleared, speed bit reads double
    assert cgb.div == 0  # documented: divider reset by the switch
    expect_fail("speed-switch-unarmed", lambda: cgb.complete_speed_switch())
    dmg_switch = GBPlatform(map_rom_romonly(build_boot_rom()), mode="dmg")
    expect_fail("speed-switch-on-dmg", lambda: dmg_switch.complete_speed_switch())
    print("PASS cgb speed switch: armed + stop -> toggled speed, cleared arm, divider reset")
    tests += 1

    # 8. Documented double-speed timer rates ----------------------------------
    fast = GBPlatform(map_rom_romonly(build_boot_rom(cgb_flag=0x80)), mode="cgb")
    fast.write8(ADDR_KEY1, 0x01)
    fast.complete_speed_switch()
    assert fast.speed == 2
    fast.step_timer(128)
    assert fast.div == 1  # documented: DIV at 32768 Hz in double speed
    fast.write8(ADDR_TAC, 0x04)  # enable, select 00
    fast.step_timer(512)
    assert fast.tima == 1  # documented: 8192 Hz in double speed
    print("PASS double-speed timer/divider frequencies (documented)")
    tests += 1

    # 9. End-to-end driver: armed STOP performs the switch --------------------
    switch_program = bytes([
        0x3E, 0x01,
        0xE0, 0x4D,                 # LDH (0xFF4D), A  -> KEY1 = 0x01 (arm)
        0x10, 0x00,                 # STOP -> documented speed switch
        0x3E, 0x2B,                 # LD A, 0x2B (after the switch)
        0x76,                       # HALT
    ])
    switch_rom = build_boot_rom(program=switch_program, cgb_flag=0x80)
    switch_platform = GBPlatform(map_rom_romonly(switch_rom), mode="cgb")
    switch_cpu = PlatformBoundSM83(switch_platform, SM83State(pc=0x0150))
    final = run_headless(switch_cpu, switch_platform)
    assert switch_platform.speed == 2
    assert switch_platform.read8(ADDR_KEY1) == 0x80  # armed cleared by the switch
    assert final["a"] == 0x2B and final["halted"] == 1
    assert switch_platform.div == 0  # documented divider reset

    dmg_rom = build_boot_rom(program=switch_program, cgb_flag=0x00)
    dmg_platform = GBPlatform(map_rom_romonly(dmg_rom), mode="dmg")
    dmg_cpu = PlatformBoundSM83(dmg_platform, SM83State(pc=0x0150))
    expect_fail("dmg-stop-does-not-switch", lambda: run_headless(dmg_cpu, dmg_platform))
    print("PASS driver: armed STOP switches speed in cgb mode, fails closed on dmg")
    tests += 1

    # 10. Unarmed STOP stays a halt -------------------------------------------
    unarmed_program = bytes([0x10, 0x00, 0x3E, 0x55, 0x76])  # STOP; LD A,0x55; HALT
    unarmed_platform = GBPlatform(map_rom_romonly(build_boot_rom(program=unarmed_program, cgb_flag=0x80)), mode="cgb")
    unarmed_cpu = PlatformBoundSM83(unarmed_platform, SM83State(pc=0x0150))
    unarmed_final = run_headless(unarmed_cpu, unarmed_platform)
    assert unarmed_platform.speed == 1  # no switch without the arm bit
    assert unarmed_final["halted"] == 1 and unarmed_final["a"] == 0x00
    print("PASS unarmed STOP: no switch, documented halt-like bounded behaviour")
    tests += 1

    # 11. Secondary local GBC-ROM metadata evidence (never bytes) -------------
    inventory_path = ROOT / ".openrecomp-phase1" / "ROM_INVENTORY.json"
    if inventory_path.exists():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
        entry = inventory["platforms"]["gameboy-color"][0]
        rom_path = Path(entry["full_path"])
        if rom_path.exists():
            import hashlib

            rom_bytes = rom_path.read_bytes()
            digest = hashlib.sha256(rom_bytes).hexdigest()
            assert digest == entry["sha256"], "local GBC ROM hash drifted from ROM_INVENTORY.json"
            assert len(rom_bytes) == entry["bytes"]
            local = classify(rom_bytes)
            title = bytes(rom_bytes[0x0134:0x0143]).rstrip(b"\x00").decode("ascii", "replace")
            print(
                f"LOCAL_GBC_ROM metadata-only sha256={digest} bytes={len(rom_bytes)} "
                f"title={title} mapper={local.mapper} cgb_mode={local.cgb_mode} "
                f"rom_banks={local.rom_banks} ram_banks={local.ram_banks} header_checksum_valid=1"
            )
        else:
            print(f"LOCAL_GBC_ROM SKIPPED (file absent: {entry['full_path']})")
    else:
        print("LOCAL_GBC_ROM SKIPPED (no ROM_INVENTORY.json)")
    tests += 1

    print(f"OPENRECOMP_GB_MODE_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
