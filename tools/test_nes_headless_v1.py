#!/usr/bin/env python3
"""P1-34 gate: NES deterministic headless proof.

Runs synthetic NROM programs twice:

- through the machine-backed 6502 reference oracle
  (`tools/nes_headless_v1.NesReference6502`, which routes every CPU access
  through the P1-33 `NesMachine` bus and the P1-32 NROM mapper);
- through the P1-31 frontend -> normalized IR V1 -> Module Image V1 -> the
  architecture-neutral Core API `ReferenceExecutor`.

The final CPU state (A/X/Y/SP/P/PC) and the full 64 KiB CPU address space must
match exactly for the MMIO-free differential fixture. The platform protocol
fixture (PPU registers/memory, OAM DMA, controller shift protocol, APU latches)
is pinned on the reference side because NES CPU MMIO is memory-mapped. Also
proves: NROM 16 KiB mirroring vs 32 KiB identity, reset/IRQ/NMI entry through
the cartridge vectors, deterministic repeatability, and fail-closed access to
disabled I/O.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from adapters.nes6502 import FLAG_B, FLAG_I, FLAG_UNUSED  # noqa: E402
from nes6502_reference_v1 import MEMORY_SIZE, NES6502State  # noqa: E402
from nes_headless_v1 import (  # noqa: E402
    ENTRY,
    FAIL_PROGRAM,
    MAPPING_PROGRAM,
    PLATFORM_PROGRAM,
    ROM_PROGRAM,
    ROM_REGION_END,
    NesReference6502,
    build_cpu_image,
    build_rom,
    run_core,
    run_reference,
    snapshot,
)
from nes_platform_v1 import NESPlatformError, NesMachine  # noqa: E402
from nes_rom_v1 import classify  # noqa: E402

CONTRACT_PATH = ROOT / "contracts" / "host_contract.json"
BASE = FLAG_UNUSED | FLAG_I


def base_meta(region_end: int) -> dict:
    return {
        "architecture": "nes6502",
        "entry_address": ENTRY,
        "region_start": ENTRY,
        "region_end": region_end,
        "initial_state": {
            "cpu:a": 0x00, "cpu:x": 0x00, "cpu:y": 0x00, "cpu:sp": 0xFD,
            "cpu:pc": ENTRY, "cpu:p": BASE, "platform:halted": 0,
        },
        "observe_state_slot": "cpu:a",
        "max_operations": 1000000,
    }


def run_platform_fixture(rom: bytes, controllers=None, ram_page=None):
    machine = NesMachine(rom)
    if controllers:
        for port, buttons in controllers.items():
            machine.set_controller(port, buttons)
    if ram_page:
        base, data = ram_page
        for offset, value in enumerate(data):
            machine.ram[(base + offset) & 0x07FF] = value
    ref = NesReference6502(machine, build_cpu_image(rom), NES6502State(pc=ENTRY, sp=0xFD, p=BASE))
    final = ref.run(max_steps=100000)
    return machine, ref, final


def main() -> int:
    tests = 0
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_bytes = CONTRACT_PATH.read_bytes()

    # 1. Differential: CPU + mapper (no MMIO) reference == Core API ----------
    rom = build_rom(2, ROM_PROGRAM)
    machine, ref, final = run_reference(rom)
    image = build_cpu_image(rom)
    execution, core_memory, _ir, _sidecar = run_core(image, base_meta(ROM_REGION_END), contract, contract_bytes)
    for key in ("a", "x", "y", "sp", "p", "pc"):
        expected = final[key]
        actual = execution.state[f"cpu:{key}"]
        if int(actual) != int(expected):
            raise AssertionError(f"cpu:{key} = {actual:#x} != reference {expected:#x}")
    if int(execution.state["platform:halted"]) != int(final["halted"]):
        raise AssertionError("halted state differs from the reference")
    if bytes(ref.memory) != core_memory[:MEMORY_SIZE]:
        for index, (left, right) in enumerate(zip(ref.memory, core_memory[:MEMORY_SIZE])):
            if left != right:
                raise AssertionError(f"CPU address space differs at 0x{index:04x}: {left:#x} != {right:#x}")
        raise AssertionError("CPU address space length differs")
    assert final["a"] == 0xC6 and final["x"] == 0x00 and final["pc"] == 0x8032, final
    assert machine.ram[0x11] == 0xC6 and machine.ram[0x12] == 0x55
    print(
        "PASS differential-proof reference == Core API "
        f"(a={final['a']:#x} x={final['x']:#x} sp={final['sp']:#x} p={final['p']:#x} pc={final['pc']:#x})"
    )
    tests += 1

    # 2. Platform protocol pinned on the reference side ----------------------
    platform_rom = build_rom(2, PLATFORM_PROGRAM)
    page = bytes((index ^ 0x77) & 0xFF for index in range(256))
    platform_machine, platform_ref, platform_final = run_platform_fixture(
        platform_rom, controllers={0: {"a", "right"}}, ram_page=(0x0300, page)
    )
    ppu = platform_machine.ppu
    assert ppu.ctrl == 0x7E, hex(ppu.ctrl)
    assert ppu.mask == 0x1E, hex(ppu.mask)
    assert ppu.oam_addr == 0x01, hex(ppu.oam_addr)
    assert ppu.vram[0] == 0x11 and ppu.vram[1] == 0x22
    assert ppu.addr == 0x2002, hex(ppu.addr)
    assert bytes(ppu.oam) == page, "OAM DMA did not copy CPU page $03"
    assert platform_machine.ram[0x20] == 0x41, hex(platform_machine.ram[0x20])
    assert platform_machine.apu_status == 0x1F
    assert platform_machine.apu_registers[0x17] == 0x40
    assert platform_final["halted"] == 1
    print(
        "PASS platform-proof ppuctrl=0x7e ppumask=0x1e vram=1122 oam_dma=1 controller=0x41 apu=0x1f"
    )
    tests += 1

    # 3. NROM 16 KiB mirroring vs 32 KiB identity ----------------------------
    machine16, _ref16, final16 = run_reference(build_rom(1, MAPPING_PROGRAM))
    assert machine16.ram[0x0200] == machine16.ram[0x0201] == 0xAD, machine16.ram[0x0200:0x0202]
    machine32, _ref32, final32 = run_reference(build_rom(2, MAPPING_PROGRAM, marker=(0x4000, 0xA5)))
    assert machine32.ram[0x0200] == 0xAD and machine32.ram[0x0201] == 0xA5, machine32.ram[0x0200:0x0202]
    print("PASS nrom-16k-mirroring vs 32k-identity")
    tests += 1

    # 4. Deterministic repeatability -----------------------------------------
    first = snapshot(platform_machine)
    second_machine, _ref, _final = run_platform_fixture(
        platform_rom, controllers={0: {"a", "right"}}, ram_page=(0x0300, page)
    )
    if first != snapshot(second_machine):
        raise AssertionError("platform state is not deterministic across runs")
    print("PASS deterministic-repeatability")
    tests += 1

    # 5. Reset / IRQ / NMI entry through the cartridge vectors ----------------
    vector_rom = bytearray(build_rom(2, ROM_PROGRAM))
    vector_rom[16 + 0x7FFA] = 0x00  # NMI vector -> $9000
    vector_rom[16 + 0x7FFB] = 0x90
    vector_rom[16 + 0x7FFC] = 0x00  # RESET vector -> $8000
    vector_rom[16 + 0x7FFD] = 0x80
    vector_rom[16 + 0x7FFE] = 0x00  # IRQ vector -> $9000
    vector_rom[16 + 0x7FFF] = 0x90
    vector_rom[16 + 0x1000] = 0x02  # handler at $9000 (KIL halt)
    vector_rom = bytes(vector_rom)
    machine = NesMachine(vector_rom)
    ref = NesReference6502(machine, build_cpu_image(vector_rom), NES6502State(pc=ENTRY, sp=0xFD, p=BASE & ~FLAG_I))
    if ref.irq() is not True or ref.state.pc != 0x9000:
        raise AssertionError("IRQ was not dispatched through $FFFE")
    if not (ref.state.p & FLAG_I):
        raise AssertionError("IRQ did not set the interrupt-disable flag")
    machine2 = NesMachine(vector_rom)
    ref2 = NesReference6502(machine2, build_cpu_image(vector_rom), NES6502State(pc=ENTRY, sp=0xFD, p=BASE))
    if ref2.irq() is not False:
        raise AssertionError("masked IRQ was dispatched")
    if ref2.nmi() is not True or ref2.state.pc != 0x9000:
        raise AssertionError("NMI was not dispatched through $FFFA")
    machine3 = NesMachine(vector_rom)
    ref3 = NesReference6502(machine3, build_cpu_image(vector_rom), NES6502State(pc=0, sp=0, p=0))
    ref3.reset()
    assert (ref3.state.pc, ref3.state.sp, ref3.state.p) == (0x8000, 0xFD, BASE), (
        hex(ref3.state.pc), hex(ref3.state.sp), hex(ref3.state.p)
    )
    print("PASS reset-irq-nmi-through-cartridge-vectors")
    tests += 1

    # 6. Fail-closed disabled I/O --------------------------------------------
    fail_rom = build_rom(2, FAIL_PROGRAM)
    fail_machine = NesMachine(fail_rom)
    fail_ref = NesReference6502(fail_machine, build_cpu_image(fail_rom), NES6502State(pc=ENTRY, sp=0xFD, p=BASE))
    try:
        fail_ref.run(max_steps=100)
    except NESPlatformError:
        print("PASS reject: write-to-disabled-io")
        tests += 1
    else:
        raise AssertionError("write to disabled I/O did not fail closed")

    # 7. Local-ROM metadata-only evidence ------------------------------------
    inventory_path = ROOT / ".openrecomp-phase1" / "ROM_INVENTORY.json"
    if inventory_path.exists():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
        entry = inventory["platforms"]["nes"][0]
        rom_path = Path(entry["full_path"])
        if rom_path.exists():
            rom_bytes = rom_path.read_bytes()
            assert hashlib.sha256(rom_bytes).hexdigest() == entry["sha256"], "local ROM hash drifted"
            local = classify(rom_bytes)
            print(
                f"LOCAL_NES_ROM metadata-only sha256={hashlib.sha256(rom_bytes).hexdigest()} "
                f"mapper={local.mapper} prg_bytes={local.prg_bytes} chr_bytes={local.chr_bytes} "
                f"mirroring={local.mirroring} nes2={int(local.is_nes2)}"
            )
        else:
            print(f"LOCAL_NES_ROM SKIPPED (file absent: {entry['full_path']})")
    else:
        print("LOCAL_NES_ROM SKIPPED (no ROM_INVENTORY.json)")
    tests += 1

    print(f"OPENRECOMP_NES_HEADLESS_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
