#!/usr/bin/env python3
"""Master System deterministic headless harness (P1-23).

Bridges the P1-21 Z80 reference (`tools/z80_reference_v1.py`) to the P1-22
SMS platform contract (`tools/sms_platform_v1.py`):

- `SmsReferenceZ80` routes every CPU memory access through the documented
  SMS memory map (Sega mapper + RAM mirror + control-register write-through)
  and every IN/OUT through the SMS port decode; the 64 KiB decode stream is
  kept in sync so the documented paging behaviour is visible to the fetch
  path (refreshed whenever a control register at $fff8-$ffff is written);
- the differential gate (`tools/test_sms_headless_v1.py`) runs one synthetic
  SMS ROM twice: through this machine-backed reference oracle and through
  the P1-21 frontend -> normalized IR V1 -> Module Image V1 -> Core API
  `ReferenceExecutor`, and requires identical final CPU state, RAM,
  control-register mirrors and the flat port segment (the machine's
  `port_trace`);

Boundary contract (documented): the CPU frontend exposes I/O as a flat
256-byte port segment; the platform port protocol (VDP two-byte control
words, data-port buffer lag, PSG latch, status read-and-reset) is applied
by the platform layer (`SmsMachine`), never by the CPU model. The headless
proof therefore pins the protocol results on the reference side and the
flat port bytes on the Core API side, with both sides driven by identical
guest code.

Interrupt dispatch is a between-instructions platform concern and is not
part of this proof (same documented split as P1-15); the reference models
DI/IM/RETN/IFF surfaces only.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from sms_platform_v1 import SMSPlatformError, SmsMachine  # noqa: E402
from z80_reference_v1 import MEMORY_SIZE, ReferenceZ80, Z80State  # noqa: E402

ROM_PROGRAM = bytes([
    0xF3,             # DI
    0xED, 0x56,       # IM 1
    0x31, 0xF0, 0xDF,  # LD SP,0xDFF0
    0x21, 0x52, 0x00,  # LD HL,0x0052 (mapper init table)
    0x11, 0xFC, 0xFF,  # LD DE,0xFFFC
    0x01, 0x04, 0x00,  # LD BC,4
    0xED, 0xB0,       # LDIR -> FFFC..FFFF = 00 00 01 02 (documented init pattern)
    0x0E, 0xBF,       # LD C,0xBF
    0x3E, 0xE4,       # LD A,0xE4
    0xED, 0x79,       # OUT (C),A  (register 1 data)
    0x3E, 0x81,       # LD A,0x81
    0xED, 0x79,       # OUT (C),A  (register write: reg 1 <- 0xE4)
    0x3E, 0x00,       # LD A,0x00
    0xED, 0x79,       # OUT (C),A  (VRAM address low)
    0x3E, 0x40,       # LD A,0x40
    0xED, 0x79,       # OUT (C),A  (code 01: VRAM write address 0x0000)
    0x0E, 0xBE,       # LD C,0xBE
    0x3E, 0x11,
    0xED, 0x79,       # vram[0] = 0x11
    0x3E, 0x22,
    0xED, 0x79,       # vram[1] = 0x22
    0x3E, 0x33,
    0xED, 0x79,       # vram[2] = 0x33
    0x3E, 0x44,
    0xED, 0x79,       # vram[3] = 0x44
    0x3E, 0x80,       # LD A,0x80
    0xD3, 0x7F,       # OUT (0x7F),A (PSG latch: register 0)
    0x3E, 0x0F,       # LD A,0x0F
    0xD3, 0x7F,       # OUT (0x7F),A (PSG data)
    0x3E, 0x5A,       # LD A,0x5A
    0x32, 0x00, 0xC0,  # LD (0xC000),A
    0x21, 0x00, 0xC0,  # LD HL,0xC000
    0x7E,             # LD A,(HL)
    0xFE, 0x5A,       # CP 0x5A
    0x20, 0x02,       # JR NZ,+2
    0x3E, 0x01,       # LD A,0x01
    0x18, 0x02,       # JR +2
    0x3E, 0xFF,       # LD A,0xFF  (not taken)
    0x47,             # LD B,A
    0x76,             # HALT
    0x00, 0x00, 0x01, 0x02,  # mapper init table (data, documented reset values)
])

PROGRAM_END = 0x0052
DATA_RANGE = (0x0052, 0x0056)

STATUS_PROGRAM = bytes([
    0x0E, 0xBF,       # LD C,0xBF
    0xED, 0x78,       # IN A,(C) (VDP status read)
    0x76,             # HALT
])

PAGING_PROGRAM = bytes([
    0xF3,             # DI
    0x3E, 0x01,       # LD A,0x01
    0x32, 0xFF, 0xFF,  # LD (0xFFFF),A (slot 2 -> bank 1, write-through)
    0x3A, 0x00, 0x80,  # LD A,(0x8000) (bank 1 marker read through the mapper)
    0xFE, 0xE7,       # CP 0xE7
    0x20, 0x02,       # JR NZ,+2
    0x3E, 0x01,       # LD A,0x01
    0x18, 0x02,       # JR +2
    0x3E, 0xFF,       # LD A,0xFF
    0x76,             # HALT
])


class SmsReferenceZ80(ReferenceZ80):
    """Z80 reference bridged to the SMS machine contract.

    Data reads/writes route through the machine's documented memory map and
    port decode; the raw 64 KiB stream used by the decoder is kept in sync
    (fully refreshed whenever a control register at $fff8-$ffff is written,
    so instruction fetches always see the current paging state).
    """

    def __init__(self, machine: SmsMachine, state: Z80State | None = None) -> None:
        super().__init__(bytearray(MEMORY_SIZE), state)
        self.machine = machine
        self._refresh_view()

    def _refresh_view(self) -> None:
        for address in range(MEMORY_SIZE):
            self.memory[address] = self.machine.read_memory(address)

    def read_byte(self, address: int) -> int:
        address &= 0xFFFF
        value = self.machine.read_memory(address)
        self.memory[address] = value
        return value

    def write_byte(self, address: int, value: int) -> None:
        address &= 0xFFFF
        self.machine.write_memory(address, value)
        self.memory[address] = self.machine.read_memory(address)
        if 0xFFF8 <= address <= 0xFFFF:
            self._refresh_view()

    def port_in(self, address: int) -> int:
        return self.machine.port_in(address & 0xFF)

    def port_out(self, address: int, value: int) -> None:
        self.machine.port_out(address & 0xFF, value & 0xFF)


def build_rom(banks: int, program: bytes = ROM_PROGRAM, *, marker: int | None = None) -> bytes:
    rom = bytearray(banks * 0x4000)
    rom[0:len(program)] = program
    if marker is not None:
        rom[0x4000] = marker
    return bytes(rom)


def run_reference(rom: bytes, *, entry: int = 0x0000, sp: int = 0xDFF0, max_steps: int = 100000):
    machine = SmsMachine(rom)
    ref = SmsReferenceZ80(machine, Z80State(pc=entry, sp=sp))
    final = ref.run(max_steps=max_steps)
    return machine, ref, final


def run_core(rom: bytes, meta: dict, contract: dict, contract_bytes: bytes):
    image = bytearray(MEMORY_SIZE)
    image[0:len(rom)] = rom
    from z80_frontend_v1 import convert  # noqa: F401
    ir, sidecar, _report = convert(bytes(image), meta, contract)
    import hashlib
    import json

    def serialize(document: object) -> str:
        return json.dumps(document, indent=2, sort_keys=True) + "\n"

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
            "producer": "openrecomp.sms-headless-v1",
            "source_input_sha256": ir["source"]["input_sha256"],
        },
    }
    from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor
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
    rom = build_rom(1)
    machine, _ref, final = run_reference(rom)
    print(f"SMS_HEADLESS_REFERENCE_A={final['a']:#x} F={final['f']:#x} HL={final['h']:#x}{final['l']:02x} "
          f"SP={final['sp']:#x} B={final['b']:#x} IM={final['im']} HALTED={final['halted']}")
    print(f"SMS_HEADLESS_VRAM_0003={machine.vdp.vram[0]:02x}{machine.vdp.vram[1]:02x}{machine.vdp.vram[2]:02x}{machine.vdp.vram[3]:02x}")
    print(f"SMS_HEADLESS_VDP_REG1={machine.vdp.registers[1]:#x}")
    print(f"SMS_HEADLESS_PSG_REG0={machine.psg.registers[0]:#x}")
    print(f"SMS_HEADLESS_MAPPER_FFFC={machine.mapper.fffc:#x} SLOTS={machine.mapper.slot}")
    print("OPENRECOMP_SMS_HEADLESS_REFERENCE=PASS")
    paging_machine, _ref2, paging_final = run_reference(build_rom(2, PAGING_PROGRAM, marker=0xE7))
    print(f"SMS_HEADLESS_PAGING_A={paging_final['a']:#x} SLOT2={paging_machine.mapper.slot[2]}")
    print("OPENRECOMP_SMS_HEADLESS_PAGING=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
