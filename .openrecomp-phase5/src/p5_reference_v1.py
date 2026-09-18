#!/usr/bin/env python3
"""Phase-5 independent NES reference driver (P5-10).

Drives the frozen, independently written reference interpreter
(`tools/nes6502_reference_v1.py`) through the frozen independent platform
(`tools/nes_platform_v1.py::NesMachine` + `tools/nes_headless_v1.py::
NesReference6502`) with the exact P5-07 scheduling policy, and produces the
same canonical observable layout as the native support (same FNV-1a 64 field
order and frame transcript).

The declared run-exit service site (`$C0FD jmp ($02FF)`) is intercepted by the
driver exactly like the native service binding: the original jump is never
executed, and the driver records the same final state (PC at the site, exit
requested, step and clock advanced by the jump's documented cost).
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any, Sequence

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p5_bus_v1 as bus_module  # noqa: E402
import p5_platform_v1 as platform  # noqa: E402
import p5_support_v1 as support_module  # noqa: E402
from nes6502_reference_v1 import FLAG_UNUSED, NES6502State  # noqa: E402
from nes_headless_v1 import NesReference6502, build_cpu_image  # noqa: E402
from nes_platform_v1 import NesMachine  # noqa: E402

EXIT_SITE = 0xC0FD
ENTRY = 0xC000
MAX_STEPS = 4000000
FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211


class ReferenceError(ValueError):
    """Fail-closed reference driver error."""


def fnv1a64(state: int, data: bytes) -> int:
    for value in data:
        state ^= value
        state = (state * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return state


def fnv1a64_byte(state: int, value: int) -> int:
    state ^= value & 0xFF
    return (state * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF


def run_reference(rom: bytes, plan: Sequence[int], *,
                  frame_units: int = platform.FRAME_CLOCK_UNITS,
                  vblank_units: int = platform.VBLANK_CLOCK_UNITS,
                  nmi_entry_cost: int = support_module.NMI_ENTRY_COST,
                  exit_site: int = EXIT_SITE,
                  max_steps: int = MAX_STEPS) -> dict[str, Any]:
    machine = NesMachine(rom)
    image = build_cpu_image(rom)
    reference = NesReference6502(
        machine, image, NES6502State(pc=ENTRY, sp=0xFD, p=0))
    plan = tuple(plan)

    clock = 0
    next_frame_start = 0
    next_vblank_end = vblank_units
    pending_nmi = 0
    nmi_delivered = 0
    frame_index = 0
    frames: list[dict[str, Any]] = []
    steps = 0
    exit_requested = False
    exit_argument = 0

    def frame_start(at: int) -> None:
        nonlocal pending_nmi, frame_index, next_frame_start, next_vblank_end
        input_value = plan[min(frame_index, len(plan) - 1)]
        machine.set_controller(0, input_value)
        machine.ppu.set_vblank(True)
        if machine.ppu.ctrl & 0x80:
            pending_nmi += 1
        vram = bytes(machine.ppu.vram)
        tile = fnv1a64(FNV_OFFSET, vram[0:960])
        ppu_digest = fnv1a64(FNV_OFFSET, vram)
        ppu_digest = fnv1a64(ppu_digest, bytes(machine.ppu.palette))
        ppu_digest = fnv1a64(ppu_digest, bytes(machine.ppu.oam))
        frames.append({
            "index": frame_index,
            "input": input_value,
            "tile": tile,
            "ppu": ppu_digest,
            "clock": at,
        })
        frame_index += 1
        next_frame_start += frame_units
        next_vblank_end = at + vblank_units

    def advance(cost: int) -> None:
        nonlocal clock, next_vblank_end
        target = clock + cost
        while next_frame_start <= target:
            frame_start(next_frame_start)
        while next_vblank_end <= target:
            machine.ppu.set_vblank(False)
            next_vblank_end += frame_units
        clock = target

    while steps < max_steps:
        if pending_nmi > 0:
            pending_nmi -= 1
            nmi_delivered += 1
            reference.nmi()
            clock += nmi_entry_cost
        pc = reference.state.pc & 0xFFFF
        opcode = image[pc]
        cost = platform.cost_of(opcode)
        if pc == exit_site:
            exit_requested = True
            exit_argument = pc
            advance(cost)
            steps += 1
            break
        reference.step()
        advance(cost)
        steps += 1
        if reference.state.halted:
            break

    ppu = machine.ppu
    state = reference.state
    cpu_image_state = bytes(reference.memory)
    ram = bytes(machine.ram)
    vram = bytes(ppu.vram)
    palette = bytes(ppu.palette)
    oam = bytes(ppu.oam)
    apu = bytes(machine.apu_registers)
    controller_state = machine.controllers[0]
    p = (state.p | FLAG_UNUSED) & 0xFF

    digest = FNV_OFFSET
    digest = fnv1a64(digest, ram)
    digest = fnv1a64(digest, vram)
    digest = fnv1a64(digest, palette)
    digest = fnv1a64(digest, oam)
    digest = fnv1a64(digest, apu)
    digest = fnv1a64_byte(digest, machine.apu_status)
    digest = fnv1a64_byte(digest, controller_state)
    digest = fnv1a64_byte(digest, ppu.ctrl)
    digest = fnv1a64_byte(digest, ppu.mask)
    digest = fnv1a64_byte(digest, ppu.status)
    digest = fnv1a64_byte(digest, ppu.oam_addr)
    digest = fnv1a64_byte(digest, ppu.addr & 0xFF)
    digest = fnv1a64_byte(digest, (ppu.addr >> 8) & 0xFF)
    digest = fnv1a64_byte(digest, ppu.scroll_x)
    digest = fnv1a64_byte(digest, ppu.scroll_y)
    digest = fnv1a64_byte(digest, ppu.buffer)
    digest = fnv1a64_byte(digest, state.a)
    digest = fnv1a64_byte(digest, state.x)
    digest = fnv1a64_byte(digest, state.y)
    digest = fnv1a64_byte(digest, state.sp)
    digest = fnv1a64_byte(digest, state.pc & 0xFF)
    digest = fnv1a64_byte(digest, (state.pc >> 8) & 0xFF)
    digest = fnv1a64_byte(digest, p)
    digest = fnv1a64_byte(digest, steps & 0xFF)
    digest = fnv1a64_byte(digest, (steps >> 8) & 0xFF)
    digest = fnv1a64_byte(digest, (steps >> 16) & 0xFF)
    digest = fnv1a64_byte(digest, (steps >> 24) & 0xFF)

    fields = {
        "failed": "0",
        "error": "",
        "exit": "1" if exit_requested else "0",
        "steps": str(steps),
        "pc": f"0x{state.pc & 0xFFFF:04X}",
        "a": f"0x{state.a & 0xFF:02X}",
        "x": f"0x{state.x & 0xFF:02X}",
        "y": f"0x{state.y & 0xFF:02X}",
        "sp": f"0x{state.sp & 0xFF:02X}",
        "p": f"0x{p:02X}",
        "frames": str(frame_index),
        "nmi": str(nmi_delivered),
        "clock": str(clock),
        "exit_arg": f"0x{exit_argument:08X}",
        "ram_fnv1a64": f"0x{fnv1a64(FNV_OFFSET, ram):016X}",
        "ppu_fnv1a64": f"0x{fnv1a64(fnv1a64(fnv1a64(FNV_OFFSET, vram), palette), oam):016X}",
        "state_fnv1a64": f"0x{digest:016X}",
    }
    frame_lines = [
        f"frame[{item['index']}]={item['input']:02X},{item['tile']:016X},{item['ppu']:016X}"
        for item in frames
    ]
    exit_word = bytes(machine.ram[0x0400:0x0408])
    return {
        "fields": fields,
        "frames": frame_lines,
        "exit_word": exit_word.hex().upper(),
        "cpu_image_state": cpu_image_state,
        "raw": {
            "ram": ram,
            "vram": vram,
            "palette": palette,
            "oam": oam,
            "apu": apu,
            "apu_status": machine.apu_status,
            "controller_state": controller_state,
            "cpu": {
                "a": state.a, "x": state.x, "y": state.y, "sp": state.sp,
                "pc": state.pc, "p": p, "steps": steps,
            },
        },
    }


__all__ = [
    "ENTRY",
    "EXIT_SITE",
    "FNV_OFFSET",
    "MAX_STEPS",
    "ReferenceError",
    "fnv1a64",
    "fnv1a64_byte",
    "run_reference",
]
