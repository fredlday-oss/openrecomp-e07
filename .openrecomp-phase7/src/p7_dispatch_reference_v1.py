#!/usr/bin/env python3
"""Phase-7 independent inline-dispatch reference (P7-03).

Two independent structures:

* `run` executes the original public fixture through the frozen independent
  6502 reference core (`nes_headless_v1.NesReference6502`) over the frozen
  independent MMC1 platform/bus (`p6_reference_v1.P6Mmc1ReferencePlatform`),
  with a Phase-7 base-cost schedule for exactly the opcodes the fixture
  executes. The schedule is cross-checked against the frozen Phase-6
  `REFERENCE_COSTS` table for every shared opcode by the P7-03 gate, so the
  extension is auditable.
* `predict_target` computes the dispatched target from the fixture bytes with
  its own little-endian pointer arithmetic, independent of the classifier's
  table extraction. Out-of-window targets fail closed.

The `0x7C` table byte is data; it is never executed by either path.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_reference_v1 as frozen_reference  # noqa: E402
from nes6502_reference_v1 import NES6502State  # noqa: E402
from nes_headless_v1 import NesReference6502  # noqa: E402

FIXED_WINDOW_BASE = 0xC000
FIXED_WINDOW_END = 0xFFFF
PRG_BANK_BYTES = 0x4000
JSR_LENGTH = 3

# Phase-7 base-cost schedule for the opcodes executed by the original public
# fixture. Values are the documented NMOS 6502 base cycle counts; the P7-03
# gate cross-checks every opcode also present in the frozen Phase-6 table.
P7_COSTS: dict[int, int] = {
    0x0A: 2,   # asl a
    0x18: 2,   # clc
    0x20: 6,   # jsr
    0x29: 2,   # and #
    0x40: 6,   # rti
    0x4C: 3,   # jmp abs
    0x60: 6,   # rts
    0x68: 3,   # pla
    0x6C: 5,   # jmp (ind)
    0x78: 2,   # sei
    0x85: 3,   # sta zp
    0x8D: 4,   # sta abs
    0x9A: 2,   # txs
    0xA2: 2,   # ldx #
    0xA5: 3,   # lda zp
    0xA8: 2,   # tay
    0xA9: 2,   # lda #
    0xB1: 5,   # lda (zp),y
    0xB9: 4,   # lda abs,y
    0xC8: 2,   # iny
    0xC9: 2,   # cmp #
    0xD8: 2,   # cld
    0xE8: 2,   # inx
    0xF0: 2,   # beq
}


class P7DispatchError(ValueError):
    """Fail-closed P7-03 dispatch reference error."""


def predict_target(image: bytes, call_site: int, selector: int) -> int:
    """Independent little-endian pointer read from the inline table.

    The JSR pushes the address of its last byte; the table starts immediately
    after the instruction, and the dispatcher indexes entry `selector`.
    """
    if isinstance(selector, bool) or not isinstance(selector, int) \
            or selector < 0:
        raise P7DispatchError("selector must be a non-negative integer")
    table_base = (call_site + JSR_LENGTH) & 0xFFFF
    offset = table_base + 2 * selector
    if offset + 1 >= len(image):
        raise P7DispatchError("inline table entry is outside the image")
    target = image[offset] | (image[offset + 1] << 8)
    if not FIXED_WINDOW_BASE <= target <= FIXED_WINDOW_END:
        raise P7DispatchError(
            f"selector {selector} points outside the fixed code window "
            f"(0x{target:04x}); fail closed instead of guessing")
    return target


def run(rom: bytes, inventory: dict[str, Any], *, exit_site: int,
        max_steps: int = 20000,
        indirect_sites: tuple[int, ...] = (),
        plan: tuple[int, ...] = (0, 0, 0)) -> dict[str, Any]:
    if max_steps <= 0:
        raise P7DispatchError("max_steps must be positive")
    plan = tuple(plan)
    for value in plan:
        if isinstance(value, bool) or not isinstance(value, int) \
                or not 0 <= value <= 0xFF:
            raise P7DispatchError("plan values must be 8-bit integers")
    platform = frozen_reference.P6Mmc1ReferencePlatform(rom, inventory)
    image = frozen_reference.build_cpu_image(platform)
    reset = int(inventory["vectors"]["reset"])
    if not FIXED_WINDOW_BASE <= reset <= FIXED_WINDOW_END:
        raise P7DispatchError(
            f"reset vector 0x{reset:04x} is outside the fixed window")
    cpu = NesReference6502(platform, image, NES6502State(pc=reset, sp=0xFD, p=0))
    state = cpu.state
    clock = 0
    steps = 0
    executed: list[int] = []
    frames: list[dict[str, Any]] = []
    frame_index = 0
    next_frame_start = 0
    next_vblank_end = frozen_reference.VBLANK_UNITS
    pending_nmi = 0
    nmi_delivered = 0
    services: list[dict[str, Any]] = []
    transcript: list[dict[str, Any]] = []

    def sync_windows() -> None:
        """Keep the decode image mapped to the current MMC1 bank state."""
        low, high = platform.prg_window_banks()
        cpu.memory[0x8000:0xC000] = platform.prg[
            low * PRG_BANK_BYTES:(low + 1) * PRG_BANK_BYTES]
        cpu.memory[0xC000:0x10000] = platform.prg[
            high * PRG_BANK_BYTES:(high + 1) * PRG_BANK_BYTES]

    def frame_start(at: int) -> None:
        nonlocal pending_nmi, frame_index, next_frame_start, next_vblank_end
        input_value = plan[min(frame_index, len(plan) - 1)]
        platform.set_controller(0, input_value)
        platform.status |= 0x80
        if platform.ctrl & 0x80:
            pending_nmi += 1
        vram = bytes(platform.vram)
        tile = frozen_reference.fnv1a64(frozen_reference.FNV_OFFSET,
                                        vram[0:960])
        ppu_digest = frozen_reference.fnv1a64(frozen_reference.FNV_OFFSET,
                                              vram)
        ppu_digest = frozen_reference.fnv1a64(ppu_digest,
                                              bytes(platform.palette))
        ppu_digest = frozen_reference.fnv1a64(ppu_digest,
                                              bytes(platform.oam))
        frames.append({"index": frame_index, "input": input_value,
                       "tile": tile, "ppu": ppu_digest, "clock": at})
        frame_index += 1
        next_frame_start += frozen_reference.FRAME_UNITS
        next_vblank_end = at + frozen_reference.VBLANK_UNITS

    def advance(cost: int) -> None:
        nonlocal clock, next_vblank_end
        target = clock + cost
        while next_frame_start <= target:
            frame_start(next_frame_start)
        while next_vblank_end <= target:
            platform.status &= ~0x80
            next_vblank_end += frozen_reference.FRAME_UNITS
        clock = target

    while steps < max_steps:
        if pending_nmi > 0:
            pending_nmi -= 1
            nmi_delivered += 1
            platform.clock = clock
            cpu.nmi()
            clock += frozen_reference.NMI_ENTRY_COST
        sync_windows()
        pc = state.pc & 0xFFFF
        executed.append(pc)
        if pc in indirect_sites:
            pointer = platform.ram[0xE2] | (platform.ram[0xE3] << 8)
            transcript.append({"site": pc, "pointer": pointer,
                               "target": pointer})
        cost = P7_COSTS.get(cpu.memory[pc])
        if cost is None:
            raise P7DispatchError(
                f"opcode 0x{cpu.memory[pc]:02x} at 0x{pc:04x} has no "
                "Phase-7 reference cost")
        if pc == exit_site:
            services.append({"service": "p7.exit", "argc": 1, "args": [pc]})
            advance(cost)
            steps += 1
            break
        platform.clock = clock
        cpu.step()
        advance(cost)
        steps += 1
        if state.halted:
            raise P7DispatchError("reference CPU halted unexpectedly")
    else:
        raise P7DispatchError("reference step limit reached without exit")

    outside = sorted(address for address in set(executed)
                     if not 0x8000 <= address <= 0xFFFF)
    if outside:
        raise P7DispatchError(
            f"executed code outside the PRG windows: {outside[:4]}")
    ram = bytes(platform.ram)
    p = (state.p | 0x20) & 0xFF
    digest = frozen_reference.FNV_OFFSET
    digest = frozen_reference.fnv1a64(digest, ram)
    digest = frozen_reference.fnv1a64(digest, bytes(platform.vram))
    digest = frozen_reference.fnv1a64(digest, bytes(platform.palette))
    digest = frozen_reference.fnv1a64(digest, bytes(platform.oam))
    digest = frozen_reference.fnv1a64(digest, bytes(platform.apu))
    digest = frozen_reference.fnv1a64_byte(digest, platform.apu_status)
    digest = frozen_reference.fnv1a64_byte(digest, platform.controllers[0])
    digest = frozen_reference.fnv1a64_byte(digest, platform.ctrl)
    digest = frozen_reference.fnv1a64_byte(digest, platform.mask)
    digest = frozen_reference.fnv1a64_byte(digest, platform.status)
    digest = frozen_reference.fnv1a64_byte(digest, platform.oam_addr)
    digest = frozen_reference.fnv1a64_byte(digest, platform.addr & 0xFF)
    digest = frozen_reference.fnv1a64_byte(digest, (platform.addr >> 8) & 0xFF)
    digest = frozen_reference.fnv1a64_byte(digest, platform.scroll_x)
    digest = frozen_reference.fnv1a64_byte(digest, platform.scroll_y)
    digest = frozen_reference.fnv1a64_byte(digest, platform.buffer)
    digest = frozen_reference.fnv1a64(digest, bytes(platform.serial.reg))
    digest = frozen_reference.fnv1a64_byte(
        digest, platform.serial.snapshot()["shift"])
    digest = frozen_reference.fnv1a64_byte(
        digest, platform.serial.snapshot()["count"])
    digest = frozen_reference.fnv1a64_byte(digest, state.a)
    digest = frozen_reference.fnv1a64_byte(digest, state.x)
    digest = frozen_reference.fnv1a64_byte(digest, state.y)
    digest = frozen_reference.fnv1a64_byte(digest, state.sp)
    digest = frozen_reference.fnv1a64_byte(digest, state.pc & 0xFF)
    digest = frozen_reference.fnv1a64_byte(digest, (state.pc >> 8) & 0xFF)
    digest = frozen_reference.fnv1a64_byte(digest, p)
    digest = frozen_reference.fnv1a64_byte(digest, steps & 0xFF)
    digest = frozen_reference.fnv1a64_byte(digest, (steps >> 8) & 0xFF)
    digest = frozen_reference.fnv1a64_byte(digest, (steps >> 16) & 0xFF)
    digest = frozen_reference.fnv1a64_byte(digest, (steps >> 24) & 0xFF)
    mapper = platform.mapper_state()
    registers = platform.serial.reg
    fields = {
        "failed": "0",
        "error": "",
        "exit": "1" if pc == exit_site else "0",
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
        "exit_arg": f"0x{pc & 0xFFFFFFFF:08X}",
        "ram_fnv1a64": f"0x{frozen_reference.fnv1a64(frozen_reference.FNV_OFFSET, ram):016X}",
        "ppu_fnv1a64": "0x" + format(
            frozen_reference.fnv1a64(
                frozen_reference.fnv1a64(
                    frozen_reference.fnv1a64(
                        frozen_reference.FNV_OFFSET, bytes(platform.vram)),
                    bytes(platform.palette)),
                bytes(platform.oam)), "016X"),
        "state_fnv1a64": f"0x{digest:016X}",
        "mmc1_regs": "".join(f"{value:02X}" for value in registers),
        "mmc1_shift": str(mapper["shift"]),
        "mmc1_count": str(mapper["count"]),
        "mmc1_writes": str(mapper["serial_writes"]),
        "prg_window_8000": str(mapper["prg_window_8000_bank"]),
        "prg_window_c000": str(mapper["prg_window_c000_bank"]),
        "chr_mode": str(mapper["chr_mode"]),
        "mirroring": str(mapper["mirroring"]),
        "prg_ram_enabled": "0",
    }
    frame_lines = [
        f"frame[{item['index']}]={item['input']:02X},{item['tile']:016X},"
        f"{item['ppu']:016X}"
        for item in frames
    ]
    return {
        "steps": steps,
        "clock": clock,
        "pc": state.pc & 0xFFFF,
        "a": state.a & 0xFF,
        "x": state.x & 0xFF,
        "y": state.y & 0xFF,
        "sp": state.sp & 0xFF,
        "p": p,
        "exit_reached": pc == exit_site,
        "markers": {
            "marker": ram[0x0300],
            "selector": ram[0x0301],
            "resume_out": ram[0x0302],
            "plain_out": ram[0x0303],
        },
        "executed_addresses": sorted(set(executed)),
        "executed_count": len(set(executed)),
        "image_sha256": __import__("hashlib").sha256(image).hexdigest(),
        "fields": fields,
        "frames": frame_lines,
        "frame_records": frames,
        "exit_word": ram[0x0400:0x0408].hex().upper(),
        "indirect_transcript": transcript,
        "service_transcript": services,
    }


__all__ = [
    "FIXED_WINDOW_BASE",
    "FIXED_WINDOW_END",
    "P7DispatchError",
    "P7_COSTS",
    "predict_target",
    "run",
]
