"""OpenRecomp Generic Runtime ABI V1 (architecture-neutral, P2-08).

`OpenRecomp Phase 2` stage P2-08 deliverable. This module defines the first
*architecture-neutral* runtime contract that sits between generated host code
(P2-07) and platform-specific runtime implementations:

    generated host code  ->  generic runtime ABI  ->  platform adapters
                                     ^
                              this module only

Core rules:

* **architecture-neutral**: the shared contract names generic operations and
  capabilities. It contains no MIPS32/NES6502 register naming, no console API
  (PS2/Xbox/NES/PSP/PS1), no Windows/POSIX API, no emulator API and no
  graphics/audio backend assumption. Platform behaviour lives behind adapters.
* **bounded guest address space**: `RuntimeMemory` never reinterprets a guest
  address as a host pointer. Every access is range-, width- and overflow-checked
  and endianness is explicit. Out-of-range, unsupported width, endianness and
  address-wrap conditions fail deterministically.
* **fail closed**: an unknown host service, an unsupported operation, malformed
  input or a trap terminates through an explicit `RuntimeFailure` with a stable
  code. Nothing is silently continued or guessed.
* **deterministic**: runtime construction and all observable state derive only
  from explicit configuration and the supplied inputs. There is no wall-clock,
  random-host-state, process-id, memory-address, filesystem-order, locale or
  environment dependency. The only pseudo-random surface is an explicit,
  configuration-seeded deterministic hook.
* **versioned**: the ABI carries a stable identifier (`RUNTIME_ABI_VERSION`) and
  a structured `RuntimeAbiVersion` with a compatibility rule so future
  incompatible changes are detectable.

This module deliberately does **not** implement any console runtime, BIOS/HLE,
GPU/APU/DSP, filesystem, window or device backend. It also does not implement
the P2-09 deterministic build pipeline.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Mapping

from openrecomp.program_model import canonical_json

RUNTIME_ABI_NAME = "openrecomp-generic-runtime-abi"
RUNTIME_ABI_VERSION = "1.0.0"

RUNTIME_WIDTHS = frozenset({8, 16, 32, 64})
RUNTIME_ENDIANNESS = frozenset({"little", "big"})
RUNTIME_MAX_ADDRESS = (1 << 64) - 1

_MAX_DIGITAL_INPUTS = 256
_MAX_ANALOG_INPUTS = 64
_MAX_FRAME_DIMENSION = 16384
_MAX_AUDIO_CHANNELS = 64

_SERVICE_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")


class RuntimeAbiError(ValueError):
    """Raised when a generic runtime contract is violated.

    Every raised error carries an explicit, stable `RuntimeFailure` so callers
    and evidence can act on a deterministic failure code rather than a message.
    """

    def __init__(self, message: str, *, failure: "RuntimeFailure | None" = None) -> None:
        super().__init__(message)
        self.failure = failure


class RuntimeFailureCode(str, Enum):
    """Stable, architecture-neutral failure codes.

    The values are part of the ABI and are used verbatim in evidence and in the
    generated C enum (`OR_RT_<CODE>`).
    """

    MEMORY_OUT_OF_RANGE = "MEMORY_OUT_OF_RANGE"
    MEMORY_WIDTH_UNSUPPORTED = "MEMORY_WIDTH_UNSUPPORTED"
    MEMORY_ADDRESS_OVERFLOW = "MEMORY_ADDRESS_OVERFLOW"
    MEMORY_ENDIANNESS_UNSUPPORTED = "MEMORY_ENDIANNESS_UNSUPPORTED"
    MEMORY_SEGMENT_OVERLAP = "MEMORY_SEGMENT_OVERLAP"
    UNKNOWN_HOST_SERVICE = "UNKNOWN_HOST_SERVICE"
    HOST_SERVICE_FAILED = "HOST_SERVICE_FAILED"
    HOST_CALL_ARITY = "HOST_CALL_ARITY"
    INPUT_INVALID = "INPUT_INVALID"
    FRAME_INVALID = "FRAME_INVALID"
    AUDIO_INVALID = "AUDIO_INVALID"
    ABI_VERSION_MISMATCH = "ABI_VERSION_MISMATCH"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    TRAP = "TRAP"


RUNTIME_FAILURE_CODES: tuple[str, ...] = tuple(code.value for code in RuntimeFailureCode)


def _failure(code: RuntimeFailureCode, detail: str, **extra: Any) -> RuntimeFailure:
    return RuntimeFailure(code=code, detail=detail, **extra)


def _fail(code: RuntimeFailureCode, detail: str, **extra: Any) -> "RuntimeAbiError":
    return RuntimeAbiError(detail, failure=_failure(code, detail, **extra))


def _require_uint(value: Any, where: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeAbiError(f"{where} must be a non-negative integer, got {value!r}")
    if maximum is not None and value > maximum:
        raise RuntimeAbiError(f"{where} exceeds the maximum {maximum}, got {value!r}")
    return value


@dataclass(frozen=True)
class RuntimeFailure:
    """A deterministic, serializable runtime failure."""

    code: RuntimeFailureCode
    detail: str = ""
    address: int | None = None
    width_bits: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, RuntimeFailureCode):
            raise RuntimeAbiError(f"failure.code must be a RuntimeFailureCode, got {self.code!r}")
        if not isinstance(self.detail, str):
            raise RuntimeAbiError("failure.detail must be a string")
        if self.address is not None:
            _require_uint(self.address, "failure.address")
        if self.width_bits is not None and self.width_bits not in RUNTIME_WIDTHS:
            raise RuntimeAbiError(f"failure.width_bits must be one of {sorted(RUNTIME_WIDTHS)}")

    def to_document(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "detail": self.detail,
            "address": self.address,
            "width_bits": self.width_bits,
        }


@dataclass(frozen=True)
class RuntimeResult:
    """A deterministic operation result: either a value or an explicit failure."""

    ok: bool
    value: int | None = None
    failure: RuntimeFailure | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ok, bool):
            raise RuntimeAbiError("result.ok must be a boolean")
        if self.ok and self.failure is not None:
            raise RuntimeAbiError("a successful result must not carry a failure")
        if not self.ok and not isinstance(self.failure, RuntimeFailure):
            raise RuntimeAbiError("a failed result must carry a RuntimeFailure")
        if self.value is not None:
            _require_uint(self.value, "result.value", maximum=RUNTIME_MAX_ADDRESS)

    @classmethod
    def success(cls, value: int | None = None) -> "RuntimeResult":
        return cls(True, value=value)

    @classmethod
    def failed(cls, failure: RuntimeFailure) -> "RuntimeResult":
        return cls(False, failure=failure)

    def require(self) -> int | None:
        if not self.ok:
            assert self.failure is not None
            raise RuntimeAbiError(f"runtime failure {self.failure.code.value}: {self.failure.detail}", failure=self.failure)
        return self.value

    def to_document(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "value": self.value,
            "failure": None if self.failure is None else self.failure.to_document(),
        }


@dataclass(frozen=True)
class RuntimeAbiVersion:
    """Structured runtime ABI version with an explicit compatibility rule."""

    name: str = RUNTIME_ABI_NAME
    major: int = 1
    minor: int = 0
    patch: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise RuntimeAbiError("abi version name must be a non-empty string")
        for part, label in ((self.major, "major"), (self.minor, "minor"), (self.patch, "patch")):
            _require_uint(part, f"abi version {label}", maximum=(1 << 31) - 1)

    @property
    def version_string(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __str__(self) -> str:
        return f"{self.name} {self.version_string}"

    def compatible_with(self, other: "RuntimeAbiVersion") -> bool:
        """Two versions are compatible when the name and major component match."""
        if not isinstance(other, RuntimeAbiVersion):
            raise RuntimeAbiError("compatible_with requires a RuntimeAbiVersion")
        return self.name == other.name and self.major == other.major

    @classmethod
    def parse(cls, text: str, *, name: str = RUNTIME_ABI_NAME) -> "RuntimeAbiVersion":
        if not isinstance(text, str):
            raise RuntimeAbiError("abi version text must be a string")
        parts = text.split(".")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise RuntimeAbiError(f"abi version {text!r} must have the form MAJOR.MINOR.PATCH")
        return cls(name=name, major=int(parts[0]), minor=int(parts[1]), patch=int(parts[2]))

    @classmethod
    def current(cls) -> "RuntimeAbiVersion":
        return cls.parse(RUNTIME_ABI_VERSION)

    def to_document(self) -> dict[str, Any]:
        return {"name": self.name, "major": self.major, "minor": self.minor, "patch": self.patch}


RUNTIME_ABI = RuntimeAbiVersion()


# --- 1. memory -------------------------------------------------------------
@dataclass(frozen=True)
class RuntimeMemorySegment:
    """A bounded, named region loaded into a runtime memory image.

    The segment name is an opaque adapter label; it carries no platform
    semantics. Overlap is detected by `RuntimeMemory`, not here.
    """

    guest_address: int
    name: str
    data: bytes

    def __post_init__(self) -> None:
        _require_uint(self.guest_address, "memory segment.guest_address", maximum=RUNTIME_MAX_ADDRESS)
        if not isinstance(self.name, str) or not self.name:
            raise RuntimeAbiError("memory segment.name must be a non-empty string")
        if not isinstance(self.data, (bytes, bytearray)):
            raise RuntimeAbiError("memory segment.data must be bytes")
        object.__setattr__(self, "data", bytes(self.data))

    def to_document(self) -> dict[str, Any]:
        return {
            "guest_address": self.guest_address,
            "name": self.name,
            "byte_length": len(self.data),
            "sha256": hashlib.sha256(self.data).hexdigest(),
        }


class RuntimeMemory:
    """A bounded guest address space with checked, deterministic access.

    Guest addresses are indices into an internal byte buffer; a guest address is
    never converted to a host pointer. Reads return integer values and copies of
    bytes, never a view onto internal storage.
    """

    def __init__(
        self,
        size_bytes: int,
        *,
        endianness: str = "little",
        segments: Iterable[RuntimeMemorySegment] = (),
    ) -> None:
        _require_uint(size_bytes, "memory.size_bytes", maximum=RUNTIME_MAX_ADDRESS + 1)
        if size_bytes == 0:
            raise RuntimeAbiError("memory.size_bytes must be positive")
        if endianness not in RUNTIME_ENDIANNESS:
            raise _fail(
                RuntimeFailureCode.MEMORY_ENDIANNESS_UNSUPPORTED,
                f"unsupported byte order {endianness!r}",
            )
        self._size = size_bytes
        self._endianness = endianness
        self._data = bytearray(size_bytes)
        occupied: list[tuple[int, int, str]] = []
        for segment in sorted(segments, key=lambda item: (item.guest_address, item.name)):
            if not isinstance(segment, RuntimeMemorySegment):
                raise RuntimeAbiError("memory segments must be RuntimeMemorySegment instances")
            start = segment.guest_address
            length = len(segment.data)
            self._range(start, length, endianness)
            end = start + length
            for other_start, other_end, other_name in occupied:
                if max(start, other_start) < min(end, other_end):
                    raise _fail(
                        RuntimeFailureCode.MEMORY_SEGMENT_OVERLAP,
                        f"memory segments overlap: {other_name!r} and {segment.name!r}",
                        address=start,
                    )
            occupied.append((start, end, segment.name))
            self._data[start:end] = segment.data

    @property
    def size_bytes(self) -> int:
        return self._size

    @property
    def endianness(self) -> str:
        return self._endianness

    def _range(self, address: int, length: int, endianness: str) -> tuple[int, str]:
        if endianness not in RUNTIME_ENDIANNESS:
            raise _fail(
                RuntimeFailureCode.MEMORY_ENDIANNESS_UNSUPPORTED,
                f"unsupported byte order {endianness!r}",
                address=address if isinstance(address, int) and not isinstance(address, bool) else None,
            )
        if isinstance(address, bool) or not isinstance(address, int) or address < 0:
            raise _fail(
                RuntimeFailureCode.MEMORY_OUT_OF_RANGE,
                f"guest address {address!r} is not a non-negative integer",
            )
        if address > RUNTIME_MAX_ADDRESS:
            raise _fail(
                RuntimeFailureCode.MEMORY_ADDRESS_OVERFLOW,
                f"guest address 0x{address:x} exceeds the 64-bit address space",
                address=address,
            )
        if length != 0 and address > RUNTIME_MAX_ADDRESS - length:
            raise _fail(
                RuntimeFailureCode.MEMORY_ADDRESS_OVERFLOW,
                f"guest address 0x{address:x} + {length} wraps the 64-bit address space",
                address=address,
            )
        if length > self._size or address > self._size - length:
            raise _fail(
                RuntimeFailureCode.MEMORY_OUT_OF_RANGE,
                f"guest address 0x{address:x} length {length} is outside the {self._size}-byte memory",
                address=address,
            )
        return length, endianness

    def _checked(self, address: int, width_bits: int, endianness: str | None) -> tuple[int, str]:
        if isinstance(width_bits, bool) or not isinstance(width_bits, int) or width_bits not in RUNTIME_WIDTHS:
            raise _fail(
                RuntimeFailureCode.MEMORY_WIDTH_UNSUPPORTED,
                f"unsupported access width {width_bits!r}",
                address=address if isinstance(address, int) and not isinstance(address, bool) and address >= 0 else None,
            )
        order = self._endianness if endianness is None else endianness
        return self._range(address, width_bits // 8, order)

    def read(self, address: int, width_bits: int, *, endianness: str | None = None) -> int:
        size, order = self._checked(address, width_bits, endianness)
        return int.from_bytes(self._data[address : address + size], order)

    def write(self, address: int, value: int, width_bits: int, *, endianness: str | None = None) -> None:
        size, order = self._checked(address, width_bits, endianness)
        if isinstance(value, bool) or not isinstance(value, int):
            raise _fail(RuntimeFailureCode.MEMORY_OUT_OF_RANGE, f"write value {value!r} is not an integer", address=address)
        masked = value & ((1 << width_bits) - 1)
        self._data[address : address + size] = masked.to_bytes(size, order)

    def read_bytes(self, address: int, length: int) -> bytes:
        _require_uint(length, "memory.read_bytes.length")
        self._range(address, length, self._endianness)
        return bytes(self._data[address : address + length])

    def write_bytes(self, address: int, data: bytes) -> None:
        if not isinstance(data, (bytes, bytearray)):
            raise _fail(RuntimeFailureCode.MEMORY_OUT_OF_RANGE, "memory.write_bytes requires bytes", address=address)
        self._range(address, len(data), self._endianness)
        self._data[address : address + len(data)] = bytes(data)

    def try_read(self, address: int, width_bits: int, *, endianness: str | None = None) -> RuntimeResult:
        try:
            return RuntimeResult.success(self.read(address, width_bits, endianness=endianness))
        except RuntimeAbiError as exc:
            return RuntimeResult.failed(exc.failure or _failure(RuntimeFailureCode.MEMORY_OUT_OF_RANGE, str(exc)))

    def try_write(self, address: int, value: int, width_bits: int, *, endianness: str | None = None) -> RuntimeResult:
        try:
            self.write(address, value, width_bits, endianness=endianness)
            return RuntimeResult.success()
        except RuntimeAbiError as exc:
            return RuntimeResult.failed(exc.failure or _failure(RuntimeFailureCode.MEMORY_OUT_OF_RANGE, str(exc)))

    def snapshot(self) -> bytes:
        return bytes(self._data)

    def fingerprint(self) -> str:
        return hashlib.sha256(self._data).hexdigest()

    def to_document(self) -> dict[str, Any]:
        return {
            "size_bytes": self._size,
            "endianness": self._endianness,
            "sha256": self.fingerprint(),
        }


# --- 2. host calls ---------------------------------------------------------
@dataclass(frozen=True)
class RuntimeService:
    """A stable host-service declaration: identity plus a fixed argument count."""

    service_id: str
    arg_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.service_id, str) or not _SERVICE_ID_PATTERN.match(self.service_id):
            raise RuntimeAbiError(f"service_id {self.service_id!r} is not a stable service identifier")
        _require_uint(self.arg_count, "service.arg_count", maximum=64)

    def to_document(self) -> dict[str, Any]:
        return {"service_id": self.service_id, "arg_count": self.arg_count}


@dataclass(frozen=True)
class RuntimeHostCallRequest:
    """An architecture-neutral host-call request with deterministic arguments."""

    service: str
    args: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.service, str) or not self.service:
            raise RuntimeAbiError("host call service must be a non-empty string")
        if not isinstance(self.args, tuple):
            raise RuntimeAbiError("host call args must be a tuple")
        for index, arg in enumerate(self.args):
            _require_uint(arg, f"host call arg[{index}]", maximum=RUNTIME_MAX_ADDRESS)

    def to_document(self) -> dict[str, Any]:
        return {"service": self.service, "args": list(self.args)}


@dataclass(frozen=True)
class RuntimeHostCallRecord:
    """A deterministic record of one dispatched host call."""

    sequence: int
    service: str
    args: tuple[int, ...]
    result: RuntimeResult

    def __post_init__(self) -> None:
        _require_uint(self.sequence, "host call record.sequence")
        if not isinstance(self.service, str) or not self.service:
            raise RuntimeAbiError("host call record.service must be a non-empty string")
        for index, arg in enumerate(self.args):
            _require_uint(arg, f"host call record.args[{index}]", maximum=RUNTIME_MAX_ADDRESS)
        if not isinstance(self.result, RuntimeResult):
            raise RuntimeAbiError("host call record.result must be a RuntimeResult")

    def to_document(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "service": self.service,
            "args": list(self.args),
            "result": self.result.to_document(),
        }


class RuntimeServiceTable:
    """A deterministic, validated set of host services and their handlers.

    A service that is not declared is never dispatched: unknown services fail
    closed. Handler exceptions are converted to a deterministic failure code
    (the exception type name is not an observable output).
    """

    def __init__(
        self,
        services: Iterable[RuntimeService] = (),
        handlers: Mapping[str, Callable[[tuple[int, ...]], int | None]] | None = None,
    ) -> None:
        self._services: dict[str, RuntimeService] = {}
        for service in services:
            if not isinstance(service, RuntimeService):
                raise RuntimeAbiError("services must be RuntimeService instances")
            if service.service_id in self._services:
                raise RuntimeAbiError(f"duplicate service id {service.service_id!r}")
            self._services[service.service_id] = service
        resolved = dict(handlers or {})
        for key in resolved:
            if key not in self._services:
                raise RuntimeAbiError(f"handler registered for undeclared service {key!r}")
        for key in self._services:
            if key not in resolved:
                raise RuntimeAbiError(f"service {key!r} has no handler")
        self._handlers = resolved

    @property
    def service_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._services))

    def has(self, service_id: str) -> bool:
        return service_id in self._services

    def service(self, service_id: str) -> RuntimeService:
        try:
            return self._services[service_id]
        except KeyError as exc:
            raise _fail(RuntimeFailureCode.UNKNOWN_HOST_SERVICE, f"unknown runtime host service {service_id!r}") from exc

    def numeric_id(self, service_id: str) -> int:
        for index, known in enumerate(self.service_ids, start=1):
            if known == service_id:
                return index
        raise _fail(RuntimeFailureCode.UNKNOWN_HOST_SERVICE, f"unknown runtime host service {service_id!r}")

    def macro(self, service_id: str) -> str:
        self.service(service_id)
        return "OR_RT_SERVICE_" + re.sub(r"[^A-Za-z0-9]", "_", service_id).upper()

    def dispatch(self, request: RuntimeHostCallRequest) -> RuntimeResult:
        if not isinstance(request, RuntimeHostCallRequest):
            raise RuntimeAbiError("dispatch requires a RuntimeHostCallRequest")
        if request.service not in self._services:
            return RuntimeResult.failed(
                _failure(RuntimeFailureCode.UNKNOWN_HOST_SERVICE, f"unknown runtime host service {request.service!r}")
            )
        declared = self._services[request.service]
        if len(request.args) != declared.arg_count:
            return RuntimeResult.failed(
                _failure(
                    RuntimeFailureCode.HOST_CALL_ARITY,
                    f"service {request.service!r} expects {declared.arg_count} argument(s), got {len(request.args)}",
                )
            )
        try:
            returned = self._handlers[request.service](tuple(request.args))
        except Exception as exc:  # noqa: BLE001 - converted to a deterministic code
            return RuntimeResult.failed(
                _failure(RuntimeFailureCode.HOST_SERVICE_FAILED, f"service {request.service!r} raised {type(exc).__name__}")
            )
        if returned is None:
            return RuntimeResult.success()
        if isinstance(returned, bool) or not isinstance(returned, int) or returned < 0:
            return RuntimeResult.failed(
                _failure(RuntimeFailureCode.HOST_SERVICE_FAILED, f"service {request.service!r} returned a non-unsigned-integer")
            )
        return RuntimeResult.success(returned & RUNTIME_MAX_ADDRESS)

    def to_document(self) -> dict[str, Any]:
        return {"services": [self._services[key].to_document() for key in self.service_ids]}

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.to_document()).encode("utf-8")).hexdigest()


# --- 3. input --------------------------------------------------------------
@dataclass(frozen=True)
class RuntimeInputSnapshot:
    """A generic, bounded digital/analog input snapshot.

    The contract is intentionally layout-free: `digital` is an ordered tuple of
    boolean channels and `analog` an ordered tuple of unsigned channels at an
    explicit `analog_bits` width. No Xbox/PlayStation/Nintendo controller layout
    is assumed; platform mappings belong outside the shared ABI.

    Construction canonicalizes the snapshot: trailing default channels
    (`False` / `0`) are trimmed so logically identical states compare and hash
    identically.
    """

    digital: tuple[bool, ...] = ()
    analog: tuple[int, ...] = ()
    analog_bits: int = 16

    def __post_init__(self) -> None:
        if isinstance(self.analog_bits, bool) or not isinstance(self.analog_bits, int) or self.analog_bits not in RUNTIME_WIDTHS:
            raise _fail(RuntimeFailureCode.INPUT_INVALID, f"input.analog_bits must be one of {sorted(RUNTIME_WIDTHS)}")
        if not isinstance(self.digital, tuple):
            raise _fail(RuntimeFailureCode.INPUT_INVALID, "input.digital must be a tuple")
        if not isinstance(self.analog, tuple):
            raise _fail(RuntimeFailureCode.INPUT_INVALID, "input.analog must be a tuple")
        if len(self.digital) > _MAX_DIGITAL_INPUTS:
            raise _fail(RuntimeFailureCode.INPUT_INVALID, f"input.digital exceeds {_MAX_DIGITAL_INPUTS} channels")
        if len(self.analog) > _MAX_ANALOG_INPUTS:
            raise _fail(RuntimeFailureCode.INPUT_INVALID, f"input.analog exceeds {_MAX_ANALOG_INPUTS} channels")
        for index, value in enumerate(self.digital):
            if not isinstance(value, bool):
                raise _fail(RuntimeFailureCode.INPUT_INVALID, f"input.digital[{index}] must be a boolean")
        mask = (1 << self.analog_bits) - 1
        for index, value in enumerate(self.analog):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise _fail(RuntimeFailureCode.INPUT_INVALID, f"input.analog[{index}] must be a non-negative integer")
            if value > mask:
                raise _fail(RuntimeFailureCode.INPUT_INVALID, f"input.analog[{index}] does not fit {self.analog_bits} bits")
        digital = tuple(self.digital)
        while digital and not digital[-1]:
            digital = digital[:-1]
        analog = tuple(self.analog)
        while analog and analog[-1] == 0:
            analog = analog[:-1]
        object.__setattr__(self, "digital", digital)
        object.__setattr__(self, "analog", analog)

    def canonicalized(self) -> "RuntimeInputSnapshot":
        return self

    def to_document(self) -> dict[str, Any]:
        return {
            "digital": [1 if value else 0 for value in self.digital],
            "analog": list(self.analog),
            "analog_bits": self.analog_bits,
        }

    def serialize(self) -> bytes:
        return (canonical_json(self.to_document()) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return hashlib.sha256(self.serialize()).hexdigest()

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "RuntimeInputSnapshot":
        if not isinstance(document, Mapping):
            raise _fail(RuntimeFailureCode.INPUT_INVALID, "input document must be an object")
        required = {"digital", "analog", "analog_bits"}
        missing = sorted(required - set(document))
        if missing:
            raise _fail(RuntimeFailureCode.INPUT_INVALID, f"input document is missing {', '.join(missing)}")
        if not isinstance(document["digital"], list) or not isinstance(document["analog"], list):
            raise _fail(RuntimeFailureCode.INPUT_INVALID, "input document digital/analog must be lists")
        return cls(
            digital=tuple(bool(value) for value in document["digital"]),
            analog=tuple(document["analog"]),
            analog_bits=document["analog_bits"],
        )

    @classmethod
    def deserialize(cls, data: bytes | str) -> "RuntimeInputSnapshot":
        try:
            document = json.loads(data)
        except (ValueError, UnicodeDecodeError) as exc:
            raise _fail(RuntimeFailureCode.INPUT_INVALID, "invalid input snapshot JSON") from exc
        return cls.from_document(document)


# --- 4. frame --------------------------------------------------------------
class RuntimePixelFormat(str, Enum):
    """Neutral pixel formats; no graphics backend is implied."""

    RGBA8 = "RGBA8"
    BGRA8 = "BGRA8"
    RGB565 = "RGB565"
    INDEX8 = "INDEX8"
    GRAY8 = "GRAY8"


_PIXEL_BYTES = {
    RuntimePixelFormat.RGBA8: 4,
    RuntimePixelFormat.BGRA8: 4,
    RuntimePixelFormat.RGB565: 2,
    RuntimePixelFormat.INDEX8: 1,
    RuntimePixelFormat.GRAY8: 1,
}


@dataclass(frozen=True)
class RuntimeFrame:
    """A deterministic frame descriptor plus its opaque pixel payload.

    The ABI defines only the boundary: geometry, pixel format, a monotonic
    sequence and the payload. It performs no rendering and assumes no D3D/
    Vulkan/OpenGL/SDL/RT64/console GPU.
    """

    width: int
    height: int
    pixel_format: RuntimePixelFormat
    payload: bytes
    sequence: int = 0

    def __post_init__(self) -> None:
        _require_uint(self.width, "frame.width", maximum=_MAX_FRAME_DIMENSION)
        _require_uint(self.height, "frame.height", maximum=_MAX_FRAME_DIMENSION)
        if self.width == 0 or self.height == 0:
            raise _fail(RuntimeFailureCode.FRAME_INVALID, "frame dimensions must be positive")
        if not isinstance(self.pixel_format, RuntimePixelFormat):
            raise _fail(RuntimeFailureCode.FRAME_INVALID, f"frame.pixel_format must be a RuntimePixelFormat, got {self.pixel_format!r}")
        if not isinstance(self.payload, (bytes, bytearray)):
            raise _fail(RuntimeFailureCode.FRAME_INVALID, "frame.payload must be bytes")
        object.__setattr__(self, "payload", bytes(self.payload))
        _require_uint(self.sequence, "frame.sequence", maximum=RUNTIME_MAX_ADDRESS)
        expected = self.width * self.height * _PIXEL_BYTES[self.pixel_format]
        if len(self.payload) != expected:
            raise _fail(
                RuntimeFailureCode.FRAME_INVALID,
                f"frame payload length {len(self.payload)} does not match {self.width}x{self.height} {self.pixel_format.value} ({expected} bytes)",
            )

    def checksum(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_document(self, *, with_payload: bool = False) -> dict[str, Any]:
        document: dict[str, Any] = {
            "width": self.width,
            "height": self.height,
            "pixel_format": self.pixel_format.value,
            "sequence": self.sequence,
            "byte_length": len(self.payload),
            "checksum": self.checksum(),
        }
        if with_payload:
            document["payload_hex"] = self.payload.hex()
        return document

    def serialize(self) -> bytes:
        return (canonical_json(self.to_document(with_payload=True)) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.to_document()).encode("utf-8")).hexdigest()

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "RuntimeFrame":
        if not isinstance(document, Mapping):
            raise _fail(RuntimeFailureCode.FRAME_INVALID, "frame document must be an object")
        required = {"width", "height", "pixel_format", "payload_hex"}
        missing = sorted(required - set(document))
        if missing:
            raise _fail(RuntimeFailureCode.FRAME_INVALID, f"frame document is missing {', '.join(missing)}")
        try:
            payload = bytes.fromhex(document["payload_hex"])
        except (ValueError, TypeError) as exc:
            raise _fail(RuntimeFailureCode.FRAME_INVALID, "frame payload_hex is not valid hex") from exc
        return cls(
            width=document["width"],
            height=document["height"],
            pixel_format=RuntimePixelFormat(document["pixel_format"]),
            payload=payload,
            sequence=document.get("sequence", 0),
        )

    @classmethod
    def deserialize(cls, data: bytes | str) -> "RuntimeFrame":
        try:
            document = json.loads(data)
        except (ValueError, UnicodeDecodeError) as exc:
            raise _fail(RuntimeFailureCode.FRAME_INVALID, "invalid frame JSON") from exc
        return cls.from_document(document)


# --- 5. audio --------------------------------------------------------------
class RuntimeSampleFormat(str, Enum):
    """Neutral PCM sample formats; no audio backend is implied."""

    U8 = "U8"
    S16LE = "S16LE"
    S16BE = "S16BE"
    S32LE = "S32LE"
    F32LE = "F32LE"
    F32BE = "F32BE"


_SAMPLE_BYTES = {
    RuntimeSampleFormat.U8: 1,
    RuntimeSampleFormat.S16LE: 2,
    RuntimeSampleFormat.S16BE: 2,
    RuntimeSampleFormat.S32LE: 4,
    RuntimeSampleFormat.F32LE: 4,
    RuntimeSampleFormat.F32BE: 4,
}


@dataclass(frozen=True)
class RuntimeAudio:
    """A deterministic audio submission boundary.

    Explicit sample format, sample rate, channel count and frame count plus an
    opaque PCM payload. No XAudio2/SDL/WASAPI/console DSP is implemented.
    """

    sample_format: RuntimeSampleFormat
    sample_rate: int
    channels: int
    frames: int
    payload: bytes
    sequence: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.sample_format, RuntimeSampleFormat):
            raise _fail(RuntimeFailureCode.AUDIO_INVALID, f"audio.sample_format must be a RuntimeSampleFormat, got {self.sample_format!r}")
        _require_uint(self.sample_rate, "audio.sample_rate", maximum=(1 << 32) - 1)
        _require_uint(self.channels, "audio.channels", maximum=_MAX_AUDIO_CHANNELS)
        _require_uint(self.frames, "audio.frames", maximum=(1 << 32) - 1)
        if self.sample_rate == 0 or self.channels == 0 or self.frames == 0:
            raise _fail(RuntimeFailureCode.AUDIO_INVALID, "audio sample_rate, channels and frames must be positive")
        if not isinstance(self.payload, (bytes, bytearray)):
            raise _fail(RuntimeFailureCode.AUDIO_INVALID, "audio.payload must be bytes")
        object.__setattr__(self, "payload", bytes(self.payload))
        _require_uint(self.sequence, "audio.sequence", maximum=RUNTIME_MAX_ADDRESS)
        expected = _SAMPLE_BYTES[self.sample_format] * self.channels * self.frames
        if len(self.payload) != expected:
            raise _fail(
                RuntimeFailureCode.AUDIO_INVALID,
                f"audio payload length {len(self.payload)} does not match {self.frames} frames x {self.channels} channels x {_SAMPLE_BYTES[self.sample_format]} bytes ({expected} bytes)",
            )

    def checksum(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_document(self, *, with_payload: bool = False) -> dict[str, Any]:
        document: dict[str, Any] = {
            "sample_format": self.sample_format.value,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "frames": self.frames,
            "sequence": self.sequence,
            "byte_length": len(self.payload),
            "checksum": self.checksum(),
        }
        if with_payload:
            document["payload_hex"] = self.payload.hex()
        return document

    def serialize(self) -> bytes:
        return (canonical_json(self.to_document(with_payload=True)) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.to_document()).encode("utf-8")).hexdigest()

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "RuntimeAudio":
        if not isinstance(document, Mapping):
            raise _fail(RuntimeFailureCode.AUDIO_INVALID, "audio document must be an object")
        required = {"sample_format", "sample_rate", "channels", "frames", "payload_hex"}
        missing = sorted(required - set(document))
        if missing:
            raise _fail(RuntimeFailureCode.AUDIO_INVALID, f"audio document is missing {', '.join(missing)}")
        try:
            payload = bytes.fromhex(document["payload_hex"])
        except (ValueError, TypeError) as exc:
            raise _fail(RuntimeFailureCode.AUDIO_INVALID, "audio payload_hex is not valid hex") from exc
        return cls(
            sample_format=RuntimeSampleFormat(document["sample_format"]),
            sample_rate=document["sample_rate"],
            channels=document["channels"],
            frames=document["frames"],
            payload=payload,
            sequence=document.get("sequence", 0),
        )

    @classmethod
    def deserialize(cls, data: bytes | str) -> "RuntimeAudio":
        try:
            document = json.loads(data)
        except (ValueError, UnicodeDecodeError) as exc:
            raise _fail(RuntimeFailureCode.AUDIO_INVALID, "invalid audio JSON") from exc
        return cls.from_document(document)


# --- 6. configuration / state ---------------------------------------------
@dataclass(frozen=True)
class RuntimeConfig:
    """Deterministic runtime configuration.

    Every input is explicit. There is no environment, clock or host-state input.
    """

    memory_size_bytes: int
    endianness: str = "little"
    max_steps: int = 1_000_000
    seed: int = 0
    abi_version: RuntimeAbiVersion = RUNTIME_ABI

    def __post_init__(self) -> None:
        _require_uint(self.memory_size_bytes, "config.memory_size_bytes", maximum=RUNTIME_MAX_ADDRESS + 1)
        if self.memory_size_bytes == 0:
            raise RuntimeAbiError("config.memory_size_bytes must be positive")
        if self.endianness not in RUNTIME_ENDIANNESS:
            raise _fail(RuntimeFailureCode.MEMORY_ENDIANNESS_UNSUPPORTED, f"unsupported byte order {self.endianness!r}")
        _require_uint(self.max_steps, "config.max_steps")
        _require_uint(self.seed, "config.seed", maximum=RUNTIME_MAX_ADDRESS)
        if not isinstance(self.abi_version, RuntimeAbiVersion):
            raise RuntimeAbiError("config.abi_version must be a RuntimeAbiVersion")
        if not self.abi_version.compatible_with(RUNTIME_ABI):
            raise _fail(
                RuntimeFailureCode.ABI_VERSION_MISMATCH,
                f"runtime ABI {self.abi_version} is not compatible with {RUNTIME_ABI}",
            )

    def to_document(self) -> dict[str, Any]:
        return {
            "abi_version": self.abi_version.to_document(),
            "memory_size_bytes": self.memory_size_bytes,
            "endianness": self.endianness,
            "max_steps": self.max_steps,
            "seed": self.seed,
        }

    def serialize(self) -> bytes:
        return (canonical_json(self.to_document()) + "\n").encode("utf-8")

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "RuntimeConfig":
        if not isinstance(document, Mapping):
            raise RuntimeAbiError("config document must be an object")
        version = document.get("abi_version")
        if not isinstance(version, Mapping):
            raise _fail(RuntimeFailureCode.ABI_VERSION_MISMATCH, "config document is missing abi_version")
        return cls(
            memory_size_bytes=document["memory_size_bytes"],
            endianness=document.get("endianness", "little"),
            max_steps=document.get("max_steps", 1_000_000),
            seed=document.get("seed", 0),
            abi_version=RuntimeAbiVersion(
                name=version.get("name", RUNTIME_ABI_NAME),
                major=version["major"],
                minor=version["minor"],
                patch=version["patch"],
            ),
        )


@dataclass(frozen=True)
class RuntimeAbiConfig:
    """The runtime ABI surface offered to the P2-07 host emitter.

    Holds only the ABI version and the declared host services. It is not a
    platform runtime: platform behaviour remains behind adapters.
    """

    services: RuntimeServiceTable = field(default_factory=RuntimeServiceTable)
    version: RuntimeAbiVersion = RUNTIME_ABI

    def __post_init__(self) -> None:
        if not isinstance(self.services, RuntimeServiceTable):
            raise RuntimeAbiError("abi config.services must be a RuntimeServiceTable")
        if not isinstance(self.version, RuntimeAbiVersion):
            raise RuntimeAbiError("abi config.version must be a RuntimeAbiVersion")
        if not self.version.compatible_with(RUNTIME_ABI):
            raise _fail(
                RuntimeFailureCode.ABI_VERSION_MISMATCH,
                f"runtime ABI {self.version} is not compatible with {RUNTIME_ABI}",
            )

    def to_document(self) -> dict[str, Any]:
        return {"version": self.version.to_document(), "services": self.services.to_document()}

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.to_document()).encode("utf-8")).hexdigest()


class RuntimeState:
    """Deterministic generic runtime state used by synthetic fixtures.

    Combines a bounded memory image, an explicit host-service table, an input
    snapshot, frame/audio submissions and an explicit failure/trap latch. All
    observable state derives solely from the configuration and the operations
    applied to it.
    """

    def __init__(
        self,
        config: RuntimeConfig,
        *,
        memory: RuntimeMemory | None = None,
        services: RuntimeServiceTable | None = None,
    ) -> None:
        if not isinstance(config, RuntimeConfig):
            raise RuntimeAbiError("RuntimeState requires a RuntimeConfig")
        if memory is None:
            memory = RuntimeMemory(config.memory_size_bytes, endianness=config.endianness)
        if not isinstance(memory, RuntimeMemory):
            raise RuntimeAbiError("RuntimeState.memory must be a RuntimeMemory")
        if services is None:
            services = RuntimeServiceTable()
        if not isinstance(services, RuntimeServiceTable):
            raise RuntimeAbiError("RuntimeState.services must be a RuntimeServiceTable")
        self.config = config
        self.memory = memory
        self.services = services
        self.input = RuntimeInputSnapshot()
        self._host_calls: list[RuntimeHostCallRecord] = []
        self._frames: list[RuntimeFrame] = []
        self._audio: list[RuntimeAudio] = []
        self._failure: RuntimeFailure | None = None
        self._steps = 0
        self._random_state = (config.seed & RUNTIME_MAX_ADDRESS) or 0x9E3779B97F4A7C15

    # -- helpers -------------------------------------------------------------
    def _step(self) -> None:
        self._steps += 1
        if self._steps > self.config.max_steps:
            self.record_failure(_failure(RuntimeFailureCode.TRAP, "runtime step limit exceeded"))
            raise _fail(RuntimeFailureCode.TRAP, "runtime step limit exceeded")

    @property
    def steps(self) -> int:
        return self._steps

    @property
    def failed(self) -> bool:
        return self._failure is not None

    @property
    def failure(self) -> RuntimeFailure | None:
        return self._failure

    def record_failure(self, failure: RuntimeFailure) -> RuntimeResult:
        if not isinstance(failure, RuntimeFailure):
            raise RuntimeAbiError("record_failure requires a RuntimeFailure")
        if self._failure is None:
            self._failure = failure
        return RuntimeResult.failed(failure)

    def trap(self, detail: str = "unsupported runtime operation") -> RuntimeResult:
        return self.record_failure(_failure(RuntimeFailureCode.TRAP, detail))

    # -- memory --------------------------------------------------------------
    def read(self, address: int, width_bits: int, *, endianness: str | None = None) -> int:
        self._step()
        return self.memory.read(address, width_bits, endianness=endianness)

    def write(self, address: int, value: int, width_bits: int, *, endianness: str | None = None) -> None:
        self._step()
        self.memory.write(address, value, width_bits, endianness=endianness)

    # -- input ---------------------------------------------------------------
    def set_input(self, snapshot: RuntimeInputSnapshot) -> None:
        if not isinstance(snapshot, RuntimeInputSnapshot):
            raise _fail(RuntimeFailureCode.INPUT_INVALID, "set_input requires a RuntimeInputSnapshot")
        self._step()
        self.input = snapshot

    # -- host calls ----------------------------------------------------------
    def host_call(self, service: str, args: tuple[int, ...] = ()) -> RuntimeResult:
        self._step()
        request = RuntimeHostCallRequest(service=service, args=tuple(args))
        result = self.services.dispatch(request)
        record = RuntimeHostCallRecord(
            sequence=len(self._host_calls),
            service=service,
            args=tuple(request.args),
            result=result,
        )
        self._host_calls.append(record)
        return result

    @property
    def host_calls(self) -> tuple[RuntimeHostCallRecord, ...]:
        return tuple(self._host_calls)

    # -- frame / audio -------------------------------------------------------
    def submit_frame(self, frame: RuntimeFrame) -> None:
        if not isinstance(frame, RuntimeFrame):
            raise _fail(RuntimeFailureCode.FRAME_INVALID, "submit_frame requires a RuntimeFrame")
        self._step()
        self._frames.append(frame)

    def submit_audio(self, audio: RuntimeAudio) -> None:
        if not isinstance(audio, RuntimeAudio):
            raise _fail(RuntimeFailureCode.AUDIO_INVALID, "submit_audio requires a RuntimeAudio")
        self._step()
        self._audio.append(audio)

    @property
    def frames(self) -> tuple[RuntimeFrame, ...]:
        return tuple(self._frames)

    @property
    def audio(self) -> tuple[RuntimeAudio, ...]:
        return tuple(self._audio)

    # -- deterministic pseudo-random hook -----------------------------------
    def next_random(self) -> int:
        """A deterministic, configuration-seeded value; never host randomness."""
        self._step()
        value = self._random_state
        value ^= (value >> 12) & RUNTIME_MAX_ADDRESS
        value ^= (value << 25) & RUNTIME_MAX_ADDRESS
        value ^= (value >> 27) & RUNTIME_MAX_ADDRESS
        self._random_state = value & RUNTIME_MAX_ADDRESS
        return (self._random_state * 0x2545F4914F6CDD1D) & RUNTIME_MAX_ADDRESS

    # -- reporting -----------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        return {
            "runtime_abi": RUNTIME_ABI_VERSION,
            "steps": self._steps,
            "memory": self.memory.to_document(),
            "input": self.input.to_document(),
            "host_calls": [record.to_document() for record in self._host_calls],
            "frames": [frame.to_document() for frame in self._frames],
            "audio": [audio.to_document() for audio in self._audio],
            "failure": None if self._failure is None else self._failure.to_document(),
        }

    def serialize(self) -> bytes:
        return (canonical_json(self.snapshot()) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return hashlib.sha256(self.serialize()).hexdigest()


# --- generated-C boundary ---------------------------------------------------
def abi_c_declarations(services: RuntimeServiceTable | None = None) -> str:
    """Deterministic C declarations for the generic runtime ABI boundary.

    Declarations only: no platform implementation is generated. Service identity
    is exposed as a stable numeric macro (`OR_RT_SERVICE_<ID>`) assigned in
    canonical sorted order.
    """
    if services is None:
        services = RuntimeServiceTable()
    if not isinstance(services, RuntimeServiceTable):
        raise RuntimeAbiError("abi_c_declarations services must be a RuntimeServiceTable")
    lines: list[str] = [
        "/* OpenRecomp generic runtime ABI V1 (P2-08). Architecture-neutral. */",
        f"/* runtime_abi_version: {RUNTIME_ABI_NAME} {RUNTIME_ABI_VERSION} */",
        "",
        "enum {",
        "    OR_RT_OK = 0,",
    ]
    for index, code in enumerate(RUNTIME_FAILURE_CODES, start=1):
        lines.append(f"    OR_RT_{code} = {index},")
    lines.append("};")
    lines.append("")
    if services.service_ids:
        for service_id in services.service_ids:
            lines.append(f"#define {services.macro(service_id)} UINT64_C({services.numeric_id(service_id)})")
        lines.append("")
    lines.append("extern int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value);")
    lines.append("extern int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value);")
    lines.append("extern int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);")
    lines.append("extern const char *or_rt_failure_reason(int code);")
    return "\n".join(lines) + "\n"


def abi_c_source(services: RuntimeServiceTable | None = None) -> str:
    """A self-contained generated-C boundary snippet (include + declarations)."""
    return "#include <stdint.h>\n" + abi_c_declarations(services)


__all__ = [
    "RUNTIME_ABI",
    "RUNTIME_ABI_NAME",
    "RUNTIME_ABI_VERSION",
    "RUNTIME_ENDIANNESS",
    "RUNTIME_FAILURE_CODES",
    "RUNTIME_MAX_ADDRESS",
    "RUNTIME_WIDTHS",
    "RuntimeAbiConfig",
    "RuntimeAbiError",
    "RuntimeAbiVersion",
    "RuntimeAudio",
    "RuntimeConfig",
    "RuntimeFailure",
    "RuntimeFailureCode",
    "RuntimeFrame",
    "RuntimeHostCallRecord",
    "RuntimeHostCallRequest",
    "RuntimeInputSnapshot",
    "RuntimeMemory",
    "RuntimeMemorySegment",
    "RuntimePixelFormat",
    "RuntimeResult",
    "RuntimeSampleFormat",
    "RuntimeService",
    "RuntimeServiceTable",
    "RuntimeState",
    "abi_c_declarations",
    "abi_c_source",
]
