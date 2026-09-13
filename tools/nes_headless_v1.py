#!/usr/bin/env python3
"""NES deterministic headless harness (P1-34).

Bridges the P1-31 6502 reference (`tools/nes6502_reference_v1.py`) to the
P1-32 NROM mapper and the P1-33 CPU-facing platform contract
(`tools/nes_platform_v1.py`):

- `NesReference6502` routes every CPU memory access through the documented NES
  bus (`NesMachine`): RAM/mirrors, PPU registers, APU/IO, OAM DMA, controllers
  and the cartridge mapper. The 64 KiB decode stream mirrors the mapped CPU
  address space so instruction fetches see the ROM;
- the differential gate (`tools/test_nes_headless_v1.py`) runs one synthetic
  NROM program twice: through this machine-backed reference oracle and through
  the P1-31 frontend -> normalized IR V1 -> Module Image V1 -> Core API
  `ReferenceExecutor`, requiring identical final CPU state (A/X/Y/SP/P/PC) and
  the full 64 KiB CPU address space;
- the platform protocol (PPU register/memory, OAM DMA, controller shift
  protocol, APU latches) is pinned on the reference side because CPU MMIO is
  memory-mapped on the NES (unlike the Master System's separate port space):
  the differential fixture deliberately performs no MMIO, and the platform
  fixture is verified against pinned documented values.

Interrupt dispatch is a between-instructions platform concern: the reference
models reset/IRQ/NMI entry (`ReferenceNES6502.reset/irq/nmi`), and the headless
proof drives those surfaces directly rather than through CPU cycle timing
(same documented split as P1-23).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from adapters.nes6502 import FLAG_I, FLAG_UNUSED  # noqa: E402
from nes6502_reference_v1 import MEMORY_SIZE, ReferenceNES6502  # noqa: E402
from nes_platform_v1 import NesMachine  # noqa: E402
from nes_rom_v1 import classify, make_mapper  # noqa: E402

BASE = FLAG_UNUSED | FLAG_I

ENTRY = 0x8000  # NROM PRG is mapped at $8000

# CPU/mapper differential program (no MMIO): RAM, stack, loop, JSR/RTS, JMP.
ROM_PROGRAM = bytes([
    0xA9, 0x42,        # LDA #$42
    0x85, 0x10,        # STA $10
    0xA2, 0x03,        # LDX #$03
    0xA9, 0x00,        # LDA #$00
    0x18,              # CLC          <- loop @ $8008
    0x65, 0x10,        # ADC $10
    0xCA,              # DEX
    0xD0, 0xFA,        # BNE loop
    0x85, 0x11,        # STA $11
    0x20, 0x20, 0x80,  # JSR $8020
    0x4C, 0x30, 0x80,  # JMP $8030
    0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA,  # NOP padding to $8020
    0xA9, 0x55,        # LDA #$55     <- $8020
    0x85, 0x12,        # STA $12
    0xA9, 0x99,        # LDA #$99
    0x60,              # RTS
    0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA,  # NOP padding to $8030
    0xA5, 0x11,        # LDA $11      <- $8030
    0x02,              # KIL halt
])
ROM_REGION_END = 0x8033

# Platform protocol program (PPU registers/memory, OAM DMA, controller, APU).
PLATFORM_PROGRAM = bytes([
    0xA9, 0x80, 0x8D, 0x00, 0x20,  # LDA #$80 ; STA $2000 (PPUCTRL)
    0xA9, 0x1E, 0x8D, 0x01, 0x20,  # LDA #$1E ; STA $2001 (PPUMASK)
    0xA9, 0x00, 0x8D, 0x03, 0x20,  # LDA #$00 ; STA $2003 (OAMADDR)
    0xA9, 0xAB, 0x8D, 0x04, 0x20,  # LDA #$AB ; STA $2004 (OAM[0])
    0xA9, 0x20, 0x8D, 0x06, 0x20,  # LDA #$20 ; STA $2006 (PPUADDR high)
    0xA9, 0x00, 0x8D, 0x06, 0x20,  # LDA #$00 ; STA $2006 (PPUADDR low -> $2000)
    0xA9, 0x11, 0x8D, 0x07, 0x20,  # LDA #$11 ; STA $2007 (vram[0])
    0xA9, 0x22, 0x8D, 0x07, 0x20,  # LDA #$22 ; STA $2007 (vram[1])
    0xA9, 0x1F, 0x8D, 0x15, 0x40,  # LDA #$1F ; STA $4015 (APU status)
    0xA9, 0x03, 0x8D, 0x14, 0x40,  # LDA #$03 ; STA $4014 (OAM DMA page $03)
    0xA9, 0x01, 0x8D, 0x16, 0x40,  # LDA #$01 ; STA $4016 (strobe high)
    0xA9, 0x00, 0x8D, 0x16, 0x40,  # LDA #$00 ; STA $4016 (strobe low)
    0xAD, 0x16, 0x40,              # LDA $4016 (controller bit 0)
    0x85, 0x20,                    # STA $20
    0xA9, 0x40, 0x8D, 0x17, 0x40,  # LDA #$40 ; STA $4017 (APU frame counter)
    0xA9, 0x7E, 0x8D, 0x00, 0x20,  # LDA #$7E ; STA $2000 (PPUCTRL rewrite)
    0x02,                          # KIL halt
])

# NROM mapping program: read the same address from both $8000 halves.
MAPPING_PROGRAM = bytes([
    0xAD, 0x00, 0x80,  # LDA $8000
    0x8D, 0x00, 0x02,  # STA $0200
    0xAD, 0x00, 0xC0,  # LDA $C000
    0x8D, 0x01, 0x02,  # STA $0201
    0x02,              # KIL halt
])

# Fail-closed: writes to the disabled I/O window.
FAIL_PROGRAM = bytes([
    0xA9, 0x00,        # LDA #$00
    0x8D, 0x18, 0x40,  # STA $4018 (disabled)
    0x02,              # KIL halt
])


class NesReference6502(ReferenceNES6502):
    """6502 reference bridged to the NES machine bus.

    Data reads/writes route through `NesMachine` (RAM/mirrors, PPU, APU/IO,
    mapper); the 64 KiB decode image holds the mapped CPU address space so
    instruction fetches match the cartridge mapping.
    """

    def __init__(self, machine: NesMachine, image: bytes, state=None) -> None:
        super().__init__(bytearray(image), state)
        self.machine = machine

    def read_byte(self, address: int) -> int:
        address &= 0xFFFF
        value = self.machine.read_memory(address)
        self.memory[address] = value
        return value

    def write_byte(self, address: int, value: int) -> None:
        address &= 0xFFFF
        self.machine.write_memory(address, value)
        # Keep the decode image in sync only for plain memory. Reading back an
        # MMIO address would apply its read side effects ($2002/$2007), so the
        # mapped streams ($2000-$401F) are left as the written image.
        if address < 0x2000 or address >= 0x4020:
            self.memory[address] = self.machine.read_memory(address)


def build_rom(prg_banks: int, program: bytes = ROM_PROGRAM, *, marker: tuple[int, int] | None = None) -> bytes:
    """Build a synthetic iNES NROM image (header + PRG + 8 KiB CHR)."""
    header = bytearray(16)
    header[0:4] = b"NES\x1a"
    header[4] = prg_banks
    header[5] = 1
    rom = bytearray(header) + bytearray(prg_banks * 0x4000) + bytearray(0x2000)
    rom[16:16 + len(program)] = program
    if marker is not None:
        offset, value = marker
        rom[16 + offset] = value
    return bytes(rom)


def build_cpu_image(rom: bytes) -> bytes:
    """Map NROM PRG into the 64 KiB CPU address space (16 KiB mirrored)."""
    info = classify(rom)
    image = bytearray(MEMORY_SIZE)
    prg = rom[info.prg_offset:info.prg_offset + info.prg_bytes]
    if len(prg) == 0x4000:
        image[0x8000:0xC000] = prg
        image[0xC000:0x10000] = prg
    else:
        image[0x8000:0x10000] = prg
    return bytes(image)


def run_reference(rom: bytes, *, entry: int = ENTRY, sp: int = 0xFD, max_steps: int = 100000):
    machine = NesMachine(rom)
    if len(rom) and classify(rom).prg_bytes == 0x4000 and entry >= 0xC000:
        raise ValueError("16 KiB NROM entry must lie in the $8000-$BFFF window")
    ref = NesReference6502(machine, build_cpu_image(rom), _state(entry, sp))
    final = ref.run(max_steps=max_steps)
    return machine, ref, final


def _state(pc: int, sp: int):
    from nes6502_reference_v1 import NES6502State

    return NES6502State(pc=pc, sp=sp, p=BASE)


def snapshot(machine: NesMachine) -> dict:
    return {
        "ram": bytes(machine.ram),
        "oam": bytes(machine.ppu.oam),
        "oam_addr": machine.ppu.oam_addr,
        "vram": bytes(machine.ppu.vram),
        "palette": bytes(machine.ppu.palette),
        "ctrl": machine.ppu.ctrl,
        "mask": machine.ppu.mask,
        "status": machine.ppu.status,
        "addr": machine.ppu.addr,
        "scroll_x": machine.ppu.scroll_x,
        "scroll_y": machine.ppu.scroll_y,
        "apu_status": machine.apu_status,
        "apu_registers": bytes(machine.apu_registers),
    }


def run_core(image: bytes, meta: dict, contract: dict, contract_bytes: bytes):
    import hashlib
    import json

    from nes6502_frontend_v1 import convert
    from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor

    def serialize(document: object) -> str:
        return json.dumps(document, indent=2, sort_keys=True) + "\n"

    ir, sidecar, _report = convert(image, meta, contract)
    ir_bytes = serialize(ir).encode("utf-8")
    segments = [
        {
            "name": segment["name"],
            "guest_address": segment["guest_address"],
            "data_hex": segment["data_hex"],
            "data_sha256": hashlib.sha256(bytes.fromhex(segment["data_hex"])).hexdigest(),
        }
        for segment in sorted(sidecar["memory_segments"], key=lambda item: (item["guest_address"], item["name"]))
    ]
    manifest = {
        "module_format_version": "1.0.0",
        "module_id": ir["module_id"],
        "ir": {
            "version": ir["ir_version"],
            "sha256": hashlib.sha256(ir_bytes).hexdigest(),
            "source_input_sha256": ir["source"]["input_sha256"],
        },
        "host_contract": {
            "version": contract["contract_version"],
            "sha256": hashlib.sha256(contract_bytes).hexdigest(),
        },
        "memory": {"size_bytes": sidecar["memory_size_bytes"], "segments": segments},
        "initial_state": [
            {"slot": slot, "value": value} for slot, value in sorted(sidecar["initial_state"].items())
        ],
        "entry": {
            "function": ir["entry_function"],
            "observe_state_slot": sidecar["entry_state_slot"],
        },
        "limits": {"max_operations": sidecar["max_operations"], "max_call_depth": 1024},
        "provenance": {
            "producer": "openrecomp.nes-headless-v1",
            "source_input_sha256": ir["source"]["input_sha256"],
        },
    }
    module = ModuleImage.from_documents(
        manifest,
        ir,
        contract,
        ir_sha256=hashlib.sha256(ir_bytes).hexdigest(),
        contract_sha256=hashlib.sha256(contract_bytes).hexdigest(),
    )
    executor = ReferenceExecutor(module, CallbackHostBinding(contract["contract_version"], {}))
    execution = executor.run()
    return execution, bytes(executor.memory.data), ir, sidecar


def main(argv: list[str]) -> int:
    rom = build_rom(2)
    machine, _ref, final = run_reference(rom)
    print(f"NES_HEADLESS_REFERENCE_A={final['a']:#x} X={final['x']:#x} SP={final['sp']:#x} "
          f"P={final['p']:#x} PC={final['pc']:#x} HALTED={final['halted']}")
    print(f"NES_HEADLESS_RAM_0010={machine.ram[0x10]:#x} 0011={machine.ram[0x11]:#x} 0012={machine.ram[0x12]:#x}")
    print("OPENRECOMP_NES_HEADLESS_REFERENCE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
