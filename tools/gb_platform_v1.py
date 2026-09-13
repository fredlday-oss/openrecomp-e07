#!/usr/bin/env python3
"""Game Boy deterministic headless platform contract (P1-15).

This module is the bounded platform layer between the P1-14 cartridge loader
(`tools/gb_rom_loader_v1.py`) and the P1-12/P1-13 CPU chain
(`tools/sm83_reference_v1.py`, `tools/sm83_frontend_v1.py`). It implements only
behaviour that is pinned by public Game Boy hardware documentation
(gbdev.io Pan Docs), with everything else failing closed:

- memory map: ROM 0x0000-0x7FFF (ROM-only cartridges map 32 KiB), VRAM
  0x8000-0x9FFF, cartridge RAM 0xA000-0xBFFF (fail closed without a RAM
  mapper), WRAM 0xC000-0xDFFF with the documented bidirectional echo at
  0xE000-0xFDFF, OAM 0xFE00-0xFE9F, the documented-unusable region
  0xFEA0-0xFEFF (fail closed), I/O 0xFF00-0xFF7F (only JOYP/timer/IF are
  modelled here; all other I/O fails closed because PPU/APU/serial surfaces
  are deferred), HRAM 0xFF80-0xFFFE, IE at 0xFFFF;
- timer: DIV increments at 16384 Hz and writing it resets it; TIMA increments
  at the TAC-selected rate when enabled; on overflow TIMA loads TMA and the
  timer interrupt (IF bit 2) is requested. The documented "obscure behaviour"
  (TAC-write increment, TIMA/DIV interplay) is not modelled;
- joypad: JOYP bit 5 selects the button group, bit 4 the d-pad group
  (active low); the lower nibble is read-only and reports pressed buttons as
  0; with neither group selected it reads 0xF; upper bits read 1;
- interrupts: IE at 0xFFFF / IF at 0xFF0F (bits 0-4; unused bits read 1,
  writes are masked); IME is modified only by ei/di/reti/interrupt servicing;
  ei is delayed by one instruction; a pending interrupt is serviced between
  instructions only when IME and the corresponding IE bit are set, with bit 0
  (VBlank) having the highest priority; servicing clears the IF bit and IME,
  pushes PC (high byte first) and jumps to the documented vector
  (0x0040/0x0048/0x0050/0x0058/0x0060);
- halt: the CPU wakes when (IE & IF) != 0 regardless of IME; with IME set the
  interrupt is serviced first, otherwise execution resumes after the halt.
  The documented "halt bug" (halt executed while IME=0 and an interrupt is
  already pending) is not modelled and fails closed.

The platform also extracts the documented cartridge entry stub (`nop; jp
$0150` at 0x0100) into a frontend meta description whose `data_ranges`
declares the documented header-data span (0x0104..0x014F).

GB vs GBC platform selection (P1-16): `select_platform_mode` applies the
documented cartridge-header rule (bit 7 of 0x0143 enables CGB mode on CGB
hardware; $C0 functions the same as $80; monochrome hardware always runs in
DMG mode). In CGB mode the documented CGB-only surfaces are available — KEY1
(0xFF4D, speed-switch arm + read-only speed bit, switch performed by an armed
`stop`), VBK (0xFF4F, VRAM bank 0/1), SVBK (0xFF70, WRAM banks 1-7 at
D000-DFFF with bank 0 fixed at C000-CFFF), and the documented double-speed
timer/divider rates — while in DMG mode those addresses fail closed. The
documented 2050 M-cycle post-STOP pause and KEY0 itself (not officially
documented) are not modelled.

Determinism: no wall-clock, no randomness, no cycle-perfect claims. Timer
advances are expressed in T-cycles (1 M-cycle = 4 T-cycles, 4194304 Hz
machine clock; the doubled machine clock in double-speed mode is folded into
the documented doubled frequencies). PPU/APU cycle behaviour is out of scope.
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from gb_rom_loader_v1 import GBROMError, Mapper, RomOnlyMapper, make_mapper  # noqa: E402
from sm83_reference_v1 import SM83ReferenceError, SM83State, ReferenceSM83  # noqa: E402

MEMORY_SIZE = 1 << 16
ROM_WINDOW = (0x0000, 0x8000)
VRAM_WINDOW = (0x8000, 0xA000)
CART_RAM_WINDOW = (0xA000, 0xC000)
WRAM_WINDOW = (0xC000, 0xE000)
ECHO_WINDOW = (0xE000, 0xFE00)
ECHO_DELTA = 0x2000
OAM_WINDOW = (0xFE00, 0xFEA0)
UNUSABLE_WINDOW = (0xFEA0, 0xFF00)
IO_WINDOW = (0xFF00, 0xFF80)
HRAM_WINDOW = (0xFF80, 0xFFFF)
IE_ADDRESS = 0xFFFF

ADDR_JOYP = 0xFF00
ADDR_DIV = 0xFF04
ADDR_TIMA = 0xFF05
ADDR_TMA = 0xFF06
ADDR_TAC = 0xFF07
ADDR_IF = 0xFF0F
ADDR_KEY1 = 0xFF4D  # CGB only
ADDR_VBK = 0xFF4F  # CGB only
ADDR_SVBK = 0xFF70  # CGB only

INTERRUPT_VECTORS = {0: 0x0040, 1: 0x0048, 2: 0x0050, 3: 0x0058, 4: 0x0060}
INTERRUPT_PRIORITY = (0, 1, 2, 3, 4)
INTERRUPT_BITS = 0x1F

# Documented TAC clock select -> T-cycles per TIMA increment (1 M-cycle = 4 T-cycles).
TAC_PERIOD_T = {0: 1024, 1: 16, 2: 64, 3: 256}
DIV_PERIOD_T = 256  # 16384 Hz at the 4194304 Hz machine clock
VRAM_BANK_SIZE = 0x2000
WRAM_BANK_SIZE = 0x1000
CGB_WRAM_BANKS = 8

BOOT_ENTRY = 0x0100
BOOT_STUB_BYTES = b"\x00\xC3\x50\x01"  # nop; jp $0150 (documented cartridge entry stub)

PLATFORM_MODES = ("dmg", "cgb")
HARDWARE_MODELS = ("dmg", "cgb")


def select_platform_mode(cgb_flag: int, hardware: str) -> str:
    """Documented GB vs GBC platform-mode selection.

    The CGB and later models interpret header byte 0x0143: setting bit 7
    triggers a write to KEY0 that enables CGB mode, otherwise the console
    operates in monochrome "Non-CGB" compatibility mode. $C0 functions the
    same as $80 (the hardware ignores bit 6). A monochrome console always
    runs in DMG mode regardless of the flag (CGB-only games lock themselves
    up, but the console itself runs the ROM).
    """
    if hardware not in HARDWARE_MODELS:
        raise GBPlatformError(f"unknown hardware model {hardware!r} (documented: dmg, cgb)")
    if isinstance(cgb_flag, bool) or not isinstance(cgb_flag, int) or not (0 <= cgb_flag <= 0xFF):
        raise GBPlatformError(f"cgb_flag 0x{cgb_flag:x} is outside the 8-bit header field")
    if hardware == "dmg":
        return "dmg"
    return "cgb" if cgb_flag & 0x80 else "dmg"


class GBPlatformError(RuntimeError):
    """Deterministic fail-closed platform rejection."""


@dataclass
class JoypadState:
    d_pad: int = 0x0F
    buttons: int = 0x0F


def map_rom_romonly(rom: bytes) -> bytearray:
    """Map a ROM-only cartridge into the 64 KiB guest memory image.

    Documented no-MBC mapping: the 32 KiB image is visible at 0x0000-0x7FFF.
    Larger images require a mapper and fail closed here.
    """
    if len(rom) != 0x8000:
        raise GBPlatformError(f"ROM-only mapping requires a 32 KiB image, got {len(rom)} bytes")
    image = bytearray(MEMORY_SIZE)
    image[0x0000:0x8000] = rom
    return image


def extract_entry_meta(rom: bytes) -> dict:
    """Extract the documented entry stub into frontend meta (fail closed).

    Requires the documented `nop; jp $0150` stub at 0x0100. The region is the
    whole mapped ROM window (0x0100..0x8000) with the documented header-data
    span 0x0104..0x014F declared as a data range so the frontend never decodes
    it as code.
    """
    if len(rom) < 0x8000:
        raise GBPlatformError("ROM is too short to extract the entry stub")
    if bytes(rom[BOOT_ENTRY:BOOT_ENTRY + 4]) != BOOT_STUB_BYTES:
        raise GBPlatformError(
            "entry stub is not the documented `nop; jp $0150` layout; "
            "fail closed instead of guessing a boot path"
        )
    return {
        "architecture": "sm83-gb",
        "entry_address": BOOT_ENTRY,
        "region_start": BOOT_ENTRY,
        "region_end": 0x8000,
        "data_ranges": [[0x0104, 0x0150]],
        "initial_state": {"cpu:a": 0, "cpu:f": 0, "cpu:sp": 0xFFFE},
        "observe_state_slot": "cpu:a",
        "max_operations": 1000000,
    }


class GBPlatform:
    """Bounded deterministic headless platform: memory surface + timer +
    joypad + interrupt contract + documented GB/GBC mode separation.
    Fail closed outside the documented model."""

    def __init__(self, memory: bytes | bytearray, mapper: Mapper | None = None, *, mode: str = "dmg") -> None:
        if len(memory) != MEMORY_SIZE:
            raise GBPlatformError(f"platform requires a {MEMORY_SIZE}-byte memory image")
        if mode not in PLATFORM_MODES:
            raise GBPlatformError(f"unknown platform mode {mode!r} (documented: dmg, cgb)")
        self.memory = bytearray(memory)
        self.mapper = mapper
        self.mode = mode
        # timer
        self.div = 0
        self.tima = 0
        self.tma = 0
        self.tac = 0
        self.div_acc = 0
        self.tima_acc = 0
        # joypad
        self.joyp_select = 0x30
        self.joypad = JoypadState()
        # interrupts
        self.ie = 0
        self.if_flags = 0
        # CGB-only surfaces (documented; only meaningful in cgb mode)
        self.speed = 1  # 1 = normal, 2 = double (KEY1 bit 7)
        self.key1 = 0  # KEY1 bit 0: speed-switch armed
        self.vbk = 0
        self.vram_banks = [bytearray(VRAM_BANK_SIZE), bytearray(VRAM_BANK_SIZE)]
        self.svbk_raw = 1  # documented: writing 0 maps WRAM bank 1
        self.wram_banks = bytearray(CGB_WRAM_BANKS * WRAM_BANK_SIZE)

    # -- memory surface --------------------------------------------------
    def read8(self, address: int) -> int:
        address &= 0xFFFF
        if address < 0x8000:
            if self.mapper is None:
                return self.memory[address]
            return self.mapper.read_rom(address)
        if address < 0xA000:
            if self.mode == "cgb":
                return self.vram_banks[self.vbk][address - 0x8000]  # documented VRAM banking
            return self.memory[address]  # VRAM
        if address < 0xC000:
            if self.mapper is None:
                raise GBPlatformError(f"cartridge RAM read 0x{address:x} without a RAM mapper (fail closed)")
            return self.mapper.read_ram(address)
        if address < 0xE000:
            return self._read_wram(address)
        if address < 0xFE00:
            return self._read_wram(address - ECHO_DELTA)  # documented WRAM echo
        if address < 0xFEA0:
            return self.memory[address]  # OAM
        if address < 0xFF00:
            raise GBPlatformError(f"documented-unusable region read 0x{address:x} (fail closed)")
        if address < 0xFF80:
            return self._read_io(address)
        if address < 0xFFFF:
            return self.memory[address]  # HRAM
        return self.ie | 0xE0  # IE: unused bits read 1, writes are masked

    def write8(self, address: int, value: int) -> None:
        address &= 0xFFFF
        value &= 0xFF
        if address < 0x8000:
            # Documented: on a ROM-only cartridge the ROM window has no bank
            # registers, so writes are ordinary (no-effect) bus writes. The
            # mapper's own `write` surface (MBC registers) stays fail closed
            # for ROM-only cartridges in the P1-14 loader.
            if self.mapper is None or isinstance(self.mapper, RomOnlyMapper):
                return
            self.mapper.write(address, value)
            return
        if address < 0xA000:
            if self.mode == "cgb":
                self.vram_banks[self.vbk][address - 0x8000] = value  # documented VRAM banking
            else:
                self.memory[address] = value  # VRAM
            return
        if address < 0xC000:
            if self.mapper is None:
                raise GBPlatformError(f"cartridge RAM write 0x{address:x} without a RAM mapper (fail closed)")
            self.mapper.write_ram(address, value)
            return
        if address < 0xE000:
            self._write_wram(address, value)
            return
        if address < 0xFE00:
            self._write_wram(address - ECHO_DELTA, value)  # documented bidirectional echo
            return
        if address < 0xFEA0:
            self.memory[address] = value  # OAM
            return
        if address < 0xFF00:
            raise GBPlatformError(f"documented-unusable region write 0x{address:x} (fail closed)")
        if address < 0xFF80:
            self._write_io(address, value)
            return
        if address < 0xFFFF:
            self.memory[address] = value  # HRAM
            return
        self.ie = value & INTERRUPT_BITS  # IE at 0xFFFF

    # -- WRAM surface ----------------------------------------------------
    def _wram_bank(self) -> int:
        return 1 if self.svbk_raw == 0 else self.svbk_raw  # documented: 0 maps bank 1

    def _read_wram(self, address: int) -> int:
        if self.mode == "dmg":
            return self.memory[address]
        if address < 0xD000:
            return self.wram_banks[address - 0xC000]  # bank 0 is fixed at C000-CFFF
        return self.wram_banks[self._wram_bank() * WRAM_BANK_SIZE + (address - 0xD000)]

    def _write_wram(self, address: int, value: int) -> None:
        if self.mode == "dmg":
            self.memory[address] = value
            return
        if address < 0xD000:
            self.wram_banks[address - 0xC000] = value  # bank 0 is fixed at C000-CFFF
        else:
            self.wram_banks[self._wram_bank() * WRAM_BANK_SIZE + (address - 0xD000)] = value

    # -- I/O registers ---------------------------------------------------
    def _read_io(self, address: int) -> int:
        if address == ADDR_JOYP:
            return self.read_joyp()
        if address == ADDR_DIV:
            return self.div
        if address == ADDR_TIMA:
            return self.tima
        if address == ADDR_TMA:
            return self.tma
        if address == ADDR_TAC:
            return 0xF8 | self.tac  # unused bits read 1
        if address == ADDR_IF:
            return 0xE0 | self.if_flags  # unused bits read 1
        if address == ADDR_KEY1 and self.mode == "cgb":
            # documented: bit 7 = current speed (read-only), bit 0 = switch armed
            return (0x80 if self.speed == 2 else 0x00) | (self.key1 & 0x01)
        if address == ADDR_VBK and self.mode == "cgb":
            return 0xFE | (self.vbk & 0x01)  # documented: bit 0 = bank, other bits read 1
        if address == ADDR_SVBK and self.mode == "cgb":
            return self.svbk_raw & 0x07
        raise GBPlatformError(f"unmodelled I/O register read 0x{address:x} (PPU/APU/serial deferred; fail closed)")

    def _write_io(self, address: int, value: int) -> None:
        if address == ADDR_JOYP:
            self.joyp_select = value & 0x30  # documented: only bits 4-5 are writable
            return
        if address == ADDR_DIV:
            self.div = 0  # documented: any write resets the divider
            self.div_acc = 0
            return
        if address == ADDR_TIMA:
            self.tima = value
            return
        if address == ADDR_TMA:
            self.tma = value
            return
        if address == ADDR_TAC:
            self.tac = value & 0x07  # documented: enable + 2-bit clock select
            return
        if address == ADDR_IF:
            self.if_flags = value & INTERRUPT_BITS  # documented: software may request/discard interrupts
            return
        if address == ADDR_KEY1 and self.mode == "cgb":
            self.key1 = value & 0x01  # documented: only bit 0 (switch armed) is writable
            return
        if address == ADDR_VBK and self.mode == "cgb":
            self.vbk = value & 0x01  # documented: only bit 0 matters
            return
        if address == ADDR_SVBK and self.mode == "cgb":
            self.svbk_raw = value & 0x07  # documented: banks 1-7; 0 maps bank 1
            return
        raise GBPlatformError(f"unmodelled I/O register write 0x{address:x} (PPU/APU/serial deferred; fail closed)")

    def complete_speed_switch(self) -> None:
        """Documented KEY1 speed-switch result (after the armed STOP).

        The CGB performs the switch when a `stop` instruction executes with
        KEY1 bit 0 set: the CPU operates at the other speed, bit 0 is cleared
        automatically and the divider is reset (the divider does not tick
        during the documented 2050 M-cycle stop; that pause duration is not
        modelled — no cycle-perfect claims).
        """
        if self.mode != "cgb":
            raise GBPlatformError("speed switch requires cgb mode (fail closed)")
        if not (self.key1 & 0x01):
            raise GBPlatformError("speed switch requested without KEY1 bit 0 armed")
        self.speed = 1 if self.speed == 2 else 2
        self.key1 &= ~0x01
        self.div = 0
        self.div_acc = 0

    # -- joypad ----------------------------------------------------------
    def read_joyp(self) -> int:
        low = 0x0F
        if not (self.joyp_select & 0x10):
            low &= self.joypad.d_pad
        if not (self.joyp_select & 0x20):
            low &= self.joypad.buttons
        return 0xC0 | (self.joyp_select & 0x30) | low

    # -- timer -----------------------------------------------------------
    def step_timer(self, t_cycles: int) -> None:
        if t_cycles < 0:
            raise GBPlatformError("timer step must be non-negative")
        # Documented: in double-speed mode the timer and divider operate
        # twice as fast (DIV 32768 Hz; TIMA 8192/524288/131072/32768 Hz),
        # i.e. the same M-cycle counts at the doubled machine clock.
        self.div_acc += t_cycles
        increments, self.div_acc = divmod(self.div_acc, DIV_PERIOD_T // self.speed)
        self.div = (self.div + increments) & 0xFF
        if not (self.tac & 0x04):
            return  # documented: TIMA counts only when enabled
        period = TAC_PERIOD_T[self.tac & 0x03] // self.speed
        self.tima_acc += t_cycles
        increments, self.tima_acc = divmod(self.tima_acc, period)
        for _ in range(increments):
            if self.tima == 0xFF:
                self.tima = self.tma  # documented: overflow reloads TMA
                self.if_flags |= 0x04  # documented: timer interrupt requested
            else:
                self.tima = (self.tima + 1) & 0xFF

    # -- interrupts ------------------------------------------------------
    def pending(self) -> int:
        """Enabled pending interrupt bits (documented: IE & IF)."""
        return self.ie & self.if_flags & INTERRUPT_BITS

    def highest_pending(self) -> int | None:
        """Highest-priority enabled pending interrupt (bit 0 = VBlank first)."""
        pending = self.pending()
        if not pending:
            return None
        for bit in INTERRUPT_PRIORITY:
            if pending & (1 << bit):
                return bit
        return None

    def dispatch(self, cpu: ReferenceSM83) -> int:
        """Service the highest-priority pending interrupt on the given CPU.

        Documented servicing: IME=0, the IF bit is cleared, PC is pushed
        (high byte first, exactly like a call) and PC jumps to the vector.
        Returns the vector that was serviced.
        """
        bit = self.highest_pending()
        if bit is None:
            raise GBPlatformError("interrupt dispatch called with no pending enabled interrupt")
        if not cpu.state.ime:
            raise GBPlatformError("interrupt dispatch called with IME disabled")
        vector = INTERRUPT_VECTORS[bit]
        cpu.state.ime = False
        self.if_flags &= ~(1 << bit)
        self._push16(cpu, cpu.state.pc)
        cpu.state.pc = vector
        return vector

    @staticmethod
    def _push16(cpu: ReferenceSM83, value: int) -> None:
        value &= 0xFFFF
        cpu.state.sp = (cpu.state.sp - 1) & 0xFFFF
        cpu.write_byte(cpu.state.sp, value >> 8)
        cpu.state.sp = (cpu.state.sp - 1) & 0xFFFF
        cpu.write_byte(cpu.state.sp, value & 0xFF)


class PlatformBoundSM83(ReferenceSM83):
    """Reference CPU whose memory surface is the documented platform surface."""

    def __init__(self, platform: GBPlatform, state: SM83State | None = None) -> None:
        super().__init__(platform.memory, state)
        self.platform = platform

    def read_byte(self, address: int) -> int:
        return self.platform.read8(address & 0xFFFF)

    def write_byte(self, address: int, value: int) -> None:
        self.platform.write8(address & 0xFFFF, value)


def run_headless(cpu: ReferenceSM83, platform: GBPlatform, *, max_steps: int = 1000000,
                 tick=None) -> dict:
    """Platform-driven execution: one instruction, then the documented
    interrupt/HALT contract, repeated until HALT with no pending interrupt or
    the step limit. Fail closed on the documented halt bug.

    `tick` is an optional deterministic event pump (e.g. bounded timer steps)
    that runs once per iteration while the CPU is halted and after each
    instruction; it must return False when exhausted.
    """
    while cpu.steps < max_steps:
        if cpu.state.halted:
            if platform.pending():
                # Documented: HALT wakes on (IE & IF) != 0 even with IME=0.
                cpu.state.halted = False
                if cpu.state.ime:
                    platform.dispatch(cpu)
                # with IME=0 the CPU simply resumes after the halt (pc already advanced)
                continue
            if tick is None or not tick():
                return cpu.state.snapshot()
            continue
        trace = cpu.step()
        if trace["op"] == "stop" and platform.mode == "cgb" and (platform.key1 & 0x01):
            # Documented: an armed KEY1 makes the `stop` instruction perform
            # the speed switch; bit 0 is cleared and execution resumes after
            # the stop (the documented 2050 M-cycle pause is not modelled).
            platform.complete_speed_switch()
            cpu.state.halted = False
            if tick is not None:
                tick()
            continue
        if cpu.state.halted:
            if platform.pending():
                if cpu.state.ime:
                    cpu.state.halted = False
                    platform.dispatch(cpu)
                else:
                    # Documented "halt bug" (halt executed while IME=0 with an
                    # interrupt already pending): not modelled, fail closed.
                    raise GBPlatformError(
                        "halt bug: halt executed with IME=0 while an interrupt is pending (unsupported)"
                    )
            if tick is not None:
                tick()
            continue
        if cpu.state.ime and platform.pending():
            platform.dispatch(cpu)
        if tick is not None:
            tick()
    if not cpu.state.halted:
        raise GBPlatformError("platform-driven run hit the step limit")
    return cpu.state.snapshot()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
