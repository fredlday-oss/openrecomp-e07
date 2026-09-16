"""NES platform runtime adapter for the OpenRecomp generic runtime ABI V1 (P2-22).

`OpenRecomp Phase 2` stage P2-22 deliverable. This module connects the
architecture-neutral runtime contracts from `openrecomp.runtime_abi` to the
documented NES CPU bus:

* **memory**: NES CPU-visible reads and writes are routed through the generic
  `RuntimeMemory` contract with explicit bounds checking. RAM mirrors, the
  controller register protocol and the cartridge window are handled by this
  adapter, not by the shared runtime.
* **input**: a generic `RuntimeInputSnapshot` is mapped to the documented NES
  standard-controller bit order; the guest reads controller state through the
  $4016/$4017 serial protocol.
* **frame**: a host-call service (`nes.frame.submit`) reads a pixel payload from
  guest memory and submits a `RuntimeFrame` through the generic frame contract.
* **audio**: a host-call service (`nes.audio.submit`) reads a PCM payload from
  guest memory and submits a `RuntimeAudio` through the generic audio contract.

The adapter is deliberately bounded: it does not implement a full PPU, APU,
mapper library or commercial-game runtime. Unsupported mappers, disabled I/O
regions, expansion areas and unimplemented PPU/APU register accesses fail
closed. NES-specific behaviour lives entirely in this module; the shared
`runtime_abi`, `host_emitter` and build-pipeline layers contain no NES
knowledge.
"""
from __future__ import annotations

from typing import Any, Mapping

from openrecomp import runtime_abi as rt

CPU_ADDRESS_SPACE = 0x10000
RAM_SIZE = 0x0800
PRG_BANK_SIZE = 16 * 1024
PRG_RAM_BASE = 0x6000
PRG_ROM_BASE = 0x8000
PPU_REGISTER_BASE = 0x2000
APU_IO_BASE = 0x4000
CONTROLLER_STROBE = 0x4016
CONTROLLER_PORT1 = 0x4016
CONTROLLER_PORT2 = 0x4017
DISABLED_IO_BASE = 0x4018
EXPANSION_BASE = 0x4020

# Canonical NES controller bit order (public NESdev "standard controller").
CONTROLLER_BUTTONS = ("a", "b", "select", "start", "up", "down", "left", "right")

# Generic frame/audio format identifiers used by the NES runtime services.
# The numeric ids are an adapter-local convention; the generic contract only
# sees the resulting `RuntimePixelFormat` / `RuntimeSampleFormat`.
FRAME_FORMATS: Mapping[int, rt.RuntimePixelFormat] = {
    0: rt.RuntimePixelFormat.RGBA8,
    1: rt.RuntimePixelFormat.RGB565,
    2: rt.RuntimePixelFormat.GRAY8,
}
FRAME_BYTES: Mapping[rt.RuntimePixelFormat, int] = {
    rt.RuntimePixelFormat.RGBA8: 4,
    rt.RuntimePixelFormat.RGB565: 2,
    rt.RuntimePixelFormat.GRAY8: 1,
}
AUDIO_FORMATS: Mapping[int, rt.RuntimeSampleFormat] = {
    0: rt.RuntimeSampleFormat.U8,
    1: rt.RuntimeSampleFormat.S16LE,
}
AUDIO_BYTES: Mapping[rt.RuntimeSampleFormat, int] = {
    rt.RuntimeSampleFormat.U8: 1,
    rt.RuntimeSampleFormat.S16LE: 2,
}


class NESRuntimeError(ValueError):
    """Fail-closed error for unsupported or malformed NES runtime use."""


def _check_address(address: int, operation: str) -> None:
    if isinstance(address, bool) or not isinstance(address, int) or not (0 <= address <= 0xFFFF):
        raise NESRuntimeError(f"{operation} address 0x{address:x} is outside the 16-bit NES CPU space")


class NESRuntimeAdapter:
    """A bounded NES platform adapter over the generic runtime ABI.

    The adapter owns one deterministic `RuntimeState`. Guest memory accesses are
    routed through the state's `RuntimeMemory`; controller input is mapped from
    the generic input snapshot; frame/audio submissions are emitted through the
    generic host-call boundary.
    """

    def __init__(
        self,
        *,
        config: rt.RuntimeConfig | None = None,
        prg_rom: bytes | bytearray | None = None,
        prg_ram: bytes | bytearray | None = None,
        mapper: int = 0,
    ) -> None:
        if config is None:
            config = rt.RuntimeConfig(memory_size_bytes=CPU_ADDRESS_SPACE, endianness="little")
        if not isinstance(config, rt.RuntimeConfig):
            raise NESRuntimeError("config must be a RuntimeConfig")
        if mapper != 0:
            raise NESRuntimeError(f"NES mapper {mapper} is not supported by the P2-22 runtime bridge; only NROM (mapper 0)")

        segments: list[rt.RuntimeMemorySegment] = [
            rt.RuntimeMemorySegment(0, "ram", bytearray(RAM_SIZE)),
        ]

        self._prg_ram_size = 0
        if prg_ram is not None:
            prg_ram_bytes = bytes(prg_ram)
            if len(prg_ram_bytes) > 0x2000:
                raise NESRuntimeError(f"PRG-RAM size {len(prg_ram_bytes)} exceeds the 8 KiB NROM window")
            if prg_ram_bytes:
                segments.append(rt.RuntimeMemorySegment(PRG_RAM_BASE, "prg_ram", prg_ram_bytes))
                self._prg_ram_size = len(prg_ram_bytes)

        self._prg_rom_size = 0
        if prg_rom is not None:
            prg_rom_bytes = bytes(prg_rom)
            if len(prg_rom_bytes) > 2 * PRG_BANK_SIZE:
                raise NESRuntimeError(f"PRG-ROM size {len(prg_rom_bytes)} exceeds the 32 KiB NROM window")
            if prg_rom_bytes:
                segments.append(rt.RuntimeMemorySegment(PRG_ROM_BASE, "prg_rom", prg_rom_bytes))
                self._prg_rom_size = len(prg_rom_bytes)

        memory = rt.RuntimeMemory(CPU_ADDRESS_SPACE, endianness=config.endianness, segments=segments)

        # Host-call services declared by the NES platform adapter. Handlers are
        # closures over this adapter so they can read guest memory and submit
        # generic frame/audio objects.
        self._services = rt.RuntimeServiceTable(
            [
                rt.RuntimeService("nes.frame.submit", 4),
                rt.RuntimeService("nes.audio.submit", 5),
            ],
            {
                "nes.frame.submit": self._service_frame_submit,
                "nes.audio.submit": self._service_audio_submit,
            },
        )

        self.state = rt.RuntimeState(config, memory=memory, services=self._services)
        self._controllers = [0, 0]
        self._strobe = 0
        self._shift_position = [0, 0]
        self._input_snapshot = rt.RuntimeInputSnapshot()

    # -- memory -------------------------------------------------------------
    def cpu_read(self, address: int) -> int:
        """Read one byte from the NES CPU address space through `RuntimeMemory`."""
        _check_address(address, "CPU read")
        if address < PPU_REGISTER_BASE:
            return self.state.memory.read(address & 0x07FF, 8)
        if address < APU_IO_BASE:
            raise NESRuntimeError(f"PPU register read at 0x{address:04x} is not implemented by the P2-22 bridge")
        if address == 0x4014:
            return 0  # OAMDMA is write-only
        if address == 0x4015:
            return 0  # APU status read is not implemented; return deterministic open-bus 0
        if address == CONTROLLER_PORT1:
            return self._read_controller(0)
        if address == CONTROLLER_PORT2:
            return self._read_controller(1)
        if address < DISABLED_IO_BASE:
            return 0  # APU channel registers are write-only
        if address < EXPANSION_BASE:
            raise NESRuntimeError(f"disabled I/O register 0x{address:04x} is not accessible")
        if address < PRG_RAM_BASE:
            raise NESRuntimeError(f"expansion area 0x{address:04x} is not implemented by the P2-22 bridge")
        if address < PRG_ROM_BASE:
            if self._prg_ram_size == 0:
                raise NESRuntimeError(f"PRG-RAM read at 0x{address:04x} but no PRG-RAM is present")
            return self.state.memory.read(address, 8)
        # PRG-ROM (NROM; writes are ignored, reads are mirrored for 16 KiB images).
        offset = address - PRG_ROM_BASE
        if self._prg_rom_size == PRG_BANK_SIZE:
            offset &= 0x3FFF
        return self.state.memory.read(PRG_ROM_BASE + offset, 8)

    def cpu_write(self, address: int, value: int) -> None:
        """Write one byte to the NES CPU address space through `RuntimeMemory`."""
        _check_address(address, "CPU write")
        if isinstance(value, bool) or not isinstance(value, int):
            raise NESRuntimeError(f"CPU write value {value!r} is not an integer")
        value &= 0xFF
        if address < PPU_REGISTER_BASE:
            self.state.memory.write(address & 0x07FF, value, 8)
            return
        if address < APU_IO_BASE:
            raise NESRuntimeError(f"PPU register write at 0x{address:04x} is not implemented by the P2-22 bridge")
        if address <= 0x4013:
            return  # APU channel register latch; not implemented, silently ignored
        if address == 0x4014:
            return  # OAMDMA; not implemented, silently ignored
        if address == 0x4015:
            return  # APU status; not implemented, silently ignored
        if address == CONTROLLER_STROBE:
            self._write_strobe(value)
            return
        if address == 0x4017:
            return  # frame counter / controller port 2 write strobe; ignored
        if address < DISABLED_IO_BASE:
            return  # APU channel registers
        if address < EXPANSION_BASE:
            raise NESRuntimeError(f"disabled I/O register 0x{address:04x} is not accessible")
        if address < PRG_RAM_BASE:
            raise NESRuntimeError(f"expansion area 0x{address:04x} is not implemented by the P2-22 bridge")
        if address < PRG_ROM_BASE:
            if self._prg_ram_size == 0:
                raise NESRuntimeError(f"PRG-RAM write at 0x{address:04x} but no PRG-RAM is present")
            self.state.memory.write(address, value, 8)
            return
        # NROM has no mapper registers; writes to PRG-ROM are ignored.

    # -- input --------------------------------------------------------------
    def set_input(self, snapshot: rt.RuntimeInputSnapshot) -> None:
        """Apply a generic input snapshot to the NES controller ports."""
        if not isinstance(snapshot, rt.RuntimeInputSnapshot):
            raise NESRuntimeError("set_input requires a RuntimeInputSnapshot")
        self.state.set_input(snapshot)
        self._input_snapshot = snapshot
        self._controllers[0] = self._snapshot_to_controller(snapshot, 0)
        self._controllers[1] = self._snapshot_to_controller(snapshot, 1)

    @staticmethod
    def _snapshot_to_controller(snapshot: rt.RuntimeInputSnapshot, port: int) -> int:
        base = port * len(CONTROLLER_BUTTONS)
        value = 0
        for index, _name in enumerate(CONTROLLER_BUTTONS):
            channel = base + index
            if channel < len(snapshot.digital) and snapshot.digital[channel]:
                value |= 1 << index
        return value

    def _read_controller(self, port: int) -> int:
        if self._strobe:
            bit = self._controllers[port] & 0x01
            return 0x40 | bit
        position = self._shift_position[port]
        if position < 8:
            bit = (self._controllers[port] >> position) & 0x01
        else:
            bit = 1
        self._shift_position[port] = position + 1
        return 0x40 | bit

    def _write_strobe(self, value: int) -> None:
        previous = self._strobe
        self._strobe = value & 0x01
        if self._strobe:
            self._shift_position = [0, 0]
        elif previous:
            # Transition 1 -> 0 starts the serial shift sequence.
            self._shift_position = [0, 0]

    # -- frame / audio services --------------------------------------------
    def submit_frame(
        self,
        pointer: int,
        width: int,
        height: int,
        format_id: int,
    ) -> rt.RuntimeResult:
        """Adapter entry point: submit a frame whose pixels live in guest memory."""
        self._submit_frame(pointer, width, height, format_id)
        return rt.RuntimeResult.success()

    def _submit_frame(self, pointer: int, width: int, height: int, format_id: int) -> None:
        pixel_format = FRAME_FORMATS.get(format_id)
        if pixel_format is None:
            raise NESRuntimeError(f"unsupported frame format_id {format_id}")
        bytes_per_pixel = FRAME_BYTES[pixel_format]
        length = width * height * bytes_per_pixel
        if length < 0:
            raise NESRuntimeError("frame dimensions must be non-negative")
        payload = self.state.memory.read_bytes(pointer, length)
        frame = rt.RuntimeFrame(
            width,
            height,
            pixel_format,
            payload,
            sequence=len(self.state.frames),
        )
        self.state.submit_frame(frame)

    def _service_frame_submit(self, args: tuple[int, ...]) -> int:
        pointer, width, height, format_id = args
        self._submit_frame(pointer, width, height, format_id)
        return 0

    def submit_audio(
        self,
        pointer: int,
        sample_rate: int,
        channels: int,
        frames: int,
        format_id: int,
    ) -> rt.RuntimeResult:
        """Adapter entry point: submit audio whose samples live in guest memory."""
        self._submit_audio(pointer, sample_rate, channels, frames, format_id)
        return rt.RuntimeResult.success()

    def _submit_audio(self, pointer: int, sample_rate: int, channels: int, frames: int, format_id: int) -> None:
        sample_format = AUDIO_FORMATS.get(format_id)
        if sample_format is None:
            raise NESRuntimeError(f"unsupported audio format_id {format_id}")
        bytes_per_sample = AUDIO_BYTES[sample_format]
        length = frames * channels * bytes_per_sample
        if length < 0:
            raise NESRuntimeError("audio dimensions must be non-negative")
        payload = self.state.memory.read_bytes(pointer, length)
        audio = rt.RuntimeAudio(
            sample_format,
            sample_rate,
            channels,
            frames,
            payload,
            sequence=len(self.state.audio),
        )
        self.state.submit_audio(audio)

    def _service_audio_submit(self, args: tuple[int, ...]) -> int:
        pointer, sample_rate, channels, frames, format_id = args
        self._submit_audio(pointer, sample_rate, channels, frames, format_id)
        return 0

    # -- introspection ------------------------------------------------------
    @property
    def services(self) -> rt.RuntimeServiceTable:
        return self._services

    def to_document(self) -> dict[str, Any]:
        return {
            "adapter": "openrecomp.frontends.nes_runtime.NESRuntimeAdapter",
            "cpu_address_space": CPU_ADDRESS_SPACE,
            "ram_size": RAM_SIZE,
            "prg_rom_size": self._prg_rom_size,
            "prg_ram_size": self._prg_ram_size,
            "mapper": 0,
            "services": self._services.to_document(),
            "state_fingerprint": self.state.fingerprint(),
        }


__all__ = [
    "AUDIO_FORMATS",
    "AUDIO_BYTES",
    "CONTROLLER_BUTTONS",
    "CPU_ADDRESS_SPACE",
    "FRAME_FORMATS",
    "FRAME_BYTES",
    "NESRuntimeAdapter",
    "NESRuntimeError",
    "PRG_BANK_SIZE",
    "PRG_RAM_BASE",
    "PRG_ROM_BASE",
    "RAM_SIZE",
]
