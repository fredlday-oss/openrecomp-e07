#!/usr/bin/env python3
"""OpenRecomp Phase-4 graphics/audio abstraction boundary V1 (P4-06).

Reusable graphics and audio adapter boundaries for later backend
implementations, built on the P2-08 neutral frame/audio contracts:

* ``GraphicsCapabilities`` / ``AudioCapabilities`` declare the pixel/sample
  formats, dimensions, rates and bounds a backend accepts;
* ``GraphicsBoundary`` / ``AudioBoundary`` are the adapter interfaces a
  backend implements; submissions are validated against the declared
  capabilities and fail closed on unsupported formats, out-of-bounds
  dimensions/rates or capacity exhaustion;
* ``HeadlessGraphics`` / ``HeadlessAudio`` are deterministic reference
  boundaries that record bounded presentation ledgers (sequence, format,
  checksum) without producing any output, so the core is usable with no
  renderer or audio system at all;
* ``NullGraphics`` / ``NullAudio`` accept nothing and fail closed on every
  submission;
* ``GraphicsBoundaryHook`` / ``AudioBoundaryHook`` route the optional P4-05
  platform hooks into boundaries.

No third-party renderer or audio SDK is imported, referenced or required; the
contract document records ``renderer_backend_mandatory: false`` and
``audio_backend_mandatory: false``.  Backend-specific integrations are future
adapters only.  Nothing here is used by, or changes, the frozen
Phase-1/Phase-2/Phase-3 emitters or evidence.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable

from openrecomp import runtime_abi as rt
from openrecomp.program_model import canonical_json

import p4_platform_adapter_v1 as pa

GRAPHICS_AUDIO_CONTRACT_NAME = "openrecomp-graphics-audio-boundary"
GRAPHICS_AUDIO_CONTRACT_VERSION = rt.RUNTIME_ABI_VERSION
GRAPHICS_PIXEL_FORMATS = tuple(format_.value for format_ in rt.RuntimePixelFormat)
AUDIO_SAMPLE_FORMATS = tuple(format_.value for format_ in rt.RuntimeSampleFormat)
MAX_DIMENSION = 16384
MAX_CHANNELS = 64
MAX_SAMPLE_RATE = 384000
MAX_SAMPLES_PER_BUFFER = 1 << 20


class GraphicsAudioError(ValueError):
    """Raised when a graphics/audio boundary contract is violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GraphicsAudioError(message)


def _require_uint(value: Any, where: str, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GraphicsAudioError(f"{where} must be a non-negative integer, got {value!r}")
    if value > maximum:
        raise GraphicsAudioError(f"{where} exceeds {maximum}, got {value!r}")
    return value


@dataclass(frozen=True)
class GraphicsCapabilities:
    pixel_formats: tuple[str, ...]
    max_width: int
    max_height: int
    capacity: int = 4096

    def __post_init__(self) -> None:
        if not isinstance(self.pixel_formats, tuple):
            raise GraphicsAudioError("pixel_formats must be a tuple")
        unknown = [item for item in self.pixel_formats if item not in GRAPHICS_PIXEL_FORMATS]
        _require(not unknown, f"unknown pixel formats {unknown}")
        _require_uint(self.max_width, "max_width", maximum=MAX_DIMENSION)
        _require_uint(self.max_height, "max_height", maximum=MAX_DIMENSION)
        _require(1 <= self.max_width <= MAX_DIMENSION, "max_width must be in 1..16384")
        _require(1 <= self.max_height <= MAX_DIMENSION, "max_height must be in 1..16384")
        _require_uint(self.capacity, "capacity", maximum=1 << 20)
        _require(self.capacity > 0, "capacity must be positive")

    def supports(self, width: int, height: int, pixel_format: str) -> bool:
        if not isinstance(pixel_format, str):
            return False
        return (pixel_format in self.pixel_formats
                and 1 <= width <= self.max_width
                and 1 <= height <= self.max_height)

    def to_document(self) -> dict[str, Any]:
        return {
            "pixel_formats": list(self.pixel_formats),
            "max_width": self.max_width,
            "max_height": self.max_height,
            "capacity": self.capacity,
        }


@dataclass(frozen=True)
class AudioCapabilities:
    sample_formats: tuple[str, ...]
    sample_rates: tuple[int, ...]
    max_channels: int
    max_samples_per_buffer: int
    capacity: int = 4096

    def __post_init__(self) -> None:
        if not isinstance(self.sample_formats, tuple) or not isinstance(self.sample_rates, tuple):
            raise GraphicsAudioError("sample_formats and sample_rates must be tuples")
        unknown = [item for item in self.sample_formats if item not in AUDIO_SAMPLE_FORMATS]
        _require(not unknown, f"unknown sample formats {unknown}")
        for rate in self.sample_rates:
            _require_uint(rate, "sample_rate", maximum=MAX_SAMPLE_RATE)
            _require(rate > 0, "sample rates must be positive")
        _require(len(set(self.sample_rates)) == len(self.sample_rates),
                 "sample rates must be unique")
        _require(1 <= self.max_channels <= MAX_CHANNELS,
                 f"max_channels must be in 1..{MAX_CHANNELS}")
        _require(1 <= self.max_samples_per_buffer <= MAX_SAMPLES_PER_BUFFER,
                 "max_samples_per_buffer is out of range")
        _require_uint(self.capacity, "capacity", maximum=1 << 20)
        _require(self.capacity > 0, "capacity must be positive")

    def supports(self, sample_format: str, sample_rate: int, channels: int,
                 samples: int) -> bool:
        return (isinstance(sample_format, str)
                and sample_format in self.sample_formats
                and sample_rate in self.sample_rates
                and 1 <= channels <= self.max_channels
                and 1 <= samples <= self.max_samples_per_buffer)

    def to_document(self) -> dict[str, Any]:
        return {
            "sample_formats": list(self.sample_formats),
            "sample_rates": list(self.sample_rates),
            "max_channels": self.max_channels,
            "max_samples_per_buffer": self.max_samples_per_buffer,
            "capacity": self.capacity,
        }


@dataclass(frozen=True)
class PresentationRecord:
    sequence: int
    width: int
    height: int
    pixel_format: str
    checksum: str

    def to_document(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "width": self.width,
            "height": self.height,
            "pixel_format": self.pixel_format,
            "checksum": self.checksum,
        }


@dataclass(frozen=True)
class AudioRecord:
    sequence: int
    sample_format: str
    sample_rate: int
    channels: int
    sample_count: int
    checksum: str

    def to_document(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "sample_format": self.sample_format,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "sample_count": self.sample_count,
            "checksum": self.checksum,
        }


class GraphicsBoundary:
    """The graphics adapter interface a backend implements."""

    def capabilities(self) -> GraphicsCapabilities:
        raise NotImplementedError

    def present(self, frame: rt.RuntimeFrame) -> None:
        raise NotImplementedError

    def to_document(self) -> dict[str, Any]:
        raise NotImplementedError


class AudioBoundary:
    """The audio adapter interface a backend implements."""

    def capabilities(self) -> AudioCapabilities:
        raise NotImplementedError

    def submit(self, buffer: rt.RuntimeAudio) -> None:
        raise NotImplementedError

    def to_document(self) -> dict[str, Any]:
        raise NotImplementedError


class HeadlessGraphics(GraphicsBoundary):
    """A deterministic graphics boundary that records a bounded ledger."""

    def __init__(self, capabilities: GraphicsCapabilities) -> None:
        if not isinstance(capabilities, GraphicsCapabilities):
            raise GraphicsAudioError("HeadlessGraphics requires GraphicsCapabilities")
        self._capabilities = capabilities
        self._records: list[PresentationRecord] = []

    def capabilities(self) -> GraphicsCapabilities:
        return self._capabilities

    @property
    def presentations(self) -> tuple[PresentationRecord, ...]:
        return tuple(self._records)

    def present(self, frame: rt.RuntimeFrame) -> None:
        if not isinstance(frame, rt.RuntimeFrame):
            raise GraphicsAudioError("present requires a RuntimeFrame")
        if not self._capabilities.supports(frame.width, frame.height, frame.pixel_format.value):
            raise GraphicsAudioError(
                f"frame {frame.width}x{frame.height} {frame.pixel_format.value} is not "
                f"supported by the declared capabilities")
        if len(self._records) >= self._capabilities.capacity:
            raise GraphicsAudioError("presentation capacity exceeded")
        self._records.append(PresentationRecord(
            sequence=frame.sequence, width=frame.width, height=frame.height,
            pixel_format=frame.pixel_format.value, checksum=frame.checksum()))

    def to_document(self) -> dict[str, Any]:
        return {
            "hook_id": "graphics",
            "boundary": "headless",
            "capabilities": self._capabilities.to_document(),
            "presentations": [record.to_document() for record in self._records],
            "presentation_count": len(self._records),
            "ledger_sha256": hashlib.sha256(
                canonical_json([record.to_document() for record in self._records])
                .encode("utf-8")).hexdigest(),
            "output": None,
        }

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.to_document()).encode("utf-8")).hexdigest()


class NullGraphics(GraphicsBoundary):
    """A graphics boundary that accepts nothing and fails closed."""

    _CAPABILITIES = GraphicsCapabilities(tuple(), 1, 1, capacity=1)

    def capabilities(self) -> GraphicsCapabilities:
        return self._CAPABILITIES

    def present(self, frame: rt.RuntimeFrame) -> None:
        raise GraphicsAudioError(
            "unavailable graphics boundary rejects every frame (fail closed)")

    def to_document(self) -> dict[str, Any]:
        return {"hook_id": "graphics", "boundary": "null",
                "capabilities": self._CAPABILITIES.to_document(),
                "presentation_count": 0, "output": None}


class HeadlessAudio(AudioBoundary):
    """A deterministic audio boundary that records a bounded ledger."""

    def __init__(self, capabilities: AudioCapabilities) -> None:
        if not isinstance(capabilities, AudioCapabilities):
            raise GraphicsAudioError("HeadlessAudio requires AudioCapabilities")
        self._capabilities = capabilities
        self._records: list[AudioRecord] = []

    def capabilities(self) -> AudioCapabilities:
        return self._capabilities

    @property
    def buffers(self) -> tuple[AudioRecord, ...]:
        return tuple(self._records)

    def submit(self, buffer: rt.RuntimeAudio) -> None:
        if not isinstance(buffer, rt.RuntimeAudio):
            raise GraphicsAudioError("submit requires a RuntimeAudio")
        samples = buffer.frames
        if not self._capabilities.supports(buffer.sample_format.value,
                                           buffer.sample_rate, buffer.channels, samples):
            raise GraphicsAudioError(
                f"audio buffer {buffer.sample_format.value} {buffer.sample_rate}Hz "
                f"{buffer.channels}ch {samples} samples is not supported by the "
                f"declared capabilities")
        if len(self._records) >= self._capabilities.capacity:
            raise GraphicsAudioError("audio capacity exceeded")
        self._records.append(AudioRecord(
            sequence=buffer.sequence, sample_format=buffer.sample_format.value,
            sample_rate=buffer.sample_rate, channels=buffer.channels,
            sample_count=samples, checksum=buffer.checksum()))

    def to_document(self) -> dict[str, Any]:
        return {
            "hook_id": "audio",
            "boundary": "headless",
            "capabilities": self._capabilities.to_document(),
            "buffers": [record.to_document() for record in self._records],
            "buffer_count": len(self._records),
            "ledger_sha256": hashlib.sha256(
                canonical_json([record.to_document() for record in self._records])
                .encode("utf-8")).hexdigest(),
            "output": None,
        }

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.to_document()).encode("utf-8")).hexdigest()


class NullAudio(AudioBoundary):
    """An audio boundary that accepts nothing and fails closed."""

    _CAPABILITIES = AudioCapabilities(tuple(), tuple(), 1, 1, capacity=1)

    def capabilities(self) -> AudioCapabilities:
        return self._CAPABILITIES

    def submit(self, buffer: rt.RuntimeAudio) -> None:
        raise GraphicsAudioError(
            "unavailable audio boundary rejects every buffer (fail closed)")

    def to_document(self) -> dict[str, Any]:
        return {"hook_id": "audio", "boundary": "null",
                "capabilities": self._CAPABILITIES.to_document(),
                "buffer_count": 0, "output": None}


class GraphicsBoundaryHook(pa.GraphicsHook):
    """Routes the optional P4-05 graphics hook into a graphics boundary."""

    def __init__(self, boundary: GraphicsBoundary) -> None:
        if not isinstance(boundary, GraphicsBoundary):
            raise GraphicsAudioError("GraphicsBoundaryHook requires a GraphicsBoundary")
        self.boundary = boundary

    def submit_frame(self, frame: rt.RuntimeFrame) -> None:
        self.boundary.present(frame)

    def to_document(self) -> dict[str, Any]:
        return {"hook_id": "graphics", "boundary": self.boundary.to_document()}


class AudioBoundaryHook(pa.AudioHook):
    """Routes the optional P4-05 audio hook into an audio boundary."""

    def __init__(self, boundary: AudioBoundary) -> None:
        if not isinstance(boundary, AudioBoundary):
            raise GraphicsAudioError("AudioBoundaryHook requires an AudioBoundary")
        self.boundary = boundary

    def submit_audio(self, buffer: rt.RuntimeAudio) -> None:
        self.boundary.submit(buffer)

    def to_document(self) -> dict[str, Any]:
        return {"hook_id": "audio", "boundary": self.boundary.to_document()}


def contract_document() -> dict[str, Any]:
    return {
        "name": GRAPHICS_AUDIO_CONTRACT_NAME,
        "version": GRAPHICS_AUDIO_CONTRACT_VERSION,
        "pixel_formats": list(GRAPHICS_PIXEL_FORMATS),
        "sample_formats": list(AUDIO_SAMPLE_FORMATS),
        "limits": {
            "max_dimension": MAX_DIMENSION,
            "max_channels": MAX_CHANNELS,
            "max_sample_rate": MAX_SAMPLE_RATE,
            "max_samples_per_buffer": MAX_SAMPLES_PER_BUFFER,
        },
        "claims": {
            "renderer_backend_mandatory": False,
            "audio_backend_mandatory": False,
            "backend_integrations_are_future_adapters": True,
        },
    }


def contract_fingerprint() -> str:
    return hashlib.sha256(canonical_json(contract_document()).encode("utf-8")).hexdigest()


ALL_GRAPHICS_PIXEL_FORMATS = GRAPHICS_PIXEL_FORMATS
ALL_AUDIO_SAMPLE_FORMATS = AUDIO_SAMPLE_FORMATS
