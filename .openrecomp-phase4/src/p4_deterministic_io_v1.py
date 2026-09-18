#!/usr/bin/env python3
"""OpenRecomp Phase-4 deterministic I/O, timing and input V1 (P4-04).

Reusable, bounded interfaces for deterministic console/file-style I/O,
virtual time/timers and input/event delivery:

* a deterministic console with bounded output and an explicit input
  exhaustion policy (end-of-input sentinel or fail closed);
* deterministic file-style byte buffers (bounded, with explicit read/write
  positions and digests) that never touch the host filesystem;
* a virtual clock that advances only on explicit ticks and a deterministic
  event queue with virtual-tick delivery ordering;
* an explicit ``RecordedInput`` snapshot (console bytes, file images, event
  plan, initial tick) with a digest, so every run consumes exactly the
  declared inputs;
* a structural rejection of ambient host input: the module has no clock,
  random, filesystem or process capability and ``ambient_input`` always fails
  closed;
* additional typed/versioned runtime service interfaces
  (``or.runtime.stream_read``, ``or.runtime.clock_ticks``,
  ``or.runtime.input_poll``) composed onto the P4-03 base catalog with
  handlers bound to an ``IoRuntime``.

The P4-03 base catalog is not modified; this layer composes it with the I/O
interfaces.  Nothing here is used by, or changes, the frozen
Phase-1/Phase-2/Phase-3 emitters or evidence.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from openrecomp.program_model import canonical_json

import p4_runtime_services_v1 as svc

ABI_VERSION = svc.ABI_VERSION
TICKS_MAX = (1 << 64) - 1
BYTE_MAX = 0xFF
STREAM_ID_MAX = 0xFFFFFFFF
EOF_SENTINEL = 0xFFFFFFFF
NO_EVENT_SENTINEL = 0xFFFFFFFF
STREAM_CONSOLE_OUT = 0
STREAM_CONSOLE_IN = 1
FILE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


class IoModelError(ValueError):
    """Raised when the deterministic I/O model is violated (fail closed)."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IoModelError(message)


def _require_uint(value: Any, where: str, *, maximum: int = TICKS_MAX) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IoModelError(f"{where} must be a non-negative integer, got {value!r}")
    if value > maximum:
        raise IoModelError(f"{where} exceeds {maximum}, got {value!r}")
    return value


class InputExhaustionPolicy(str, Enum):
    EOF = "eof"
    FAULT = "fault"


class EventKind(str, Enum):
    BYTE = "byte"
    KEY = "key"
    TIMER = "timer"
    POINTER = "pointer"


@dataclass(frozen=True)
class InputEvent:
    tick: int
    kind: EventKind
    code: int
    value: int = 0

    def __post_init__(self) -> None:
        _require_uint(self.tick, "event.tick")
        _require(isinstance(self.kind, EventKind), "event.kind must be an EventKind")
        _require_uint(self.code, "event.code", maximum=STREAM_ID_MAX)
        _require_uint(self.value, "event.value")

    def to_document(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "kind": self.kind.value,
            "code": self.code,
            "value": self.value,
        }


@dataclass(frozen=True)
class RecordedInput:
    """The complete declared input set of a deterministic run."""

    console_input: bytes = b""
    files: tuple[tuple[str, bytes], ...] = ()
    events: tuple[InputEvent, ...] = ()
    initial_ticks: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.console_input, (bytes, bytearray)):
            raise IoModelError("console_input must be bytes")
        object.__setattr__(self, "console_input", bytes(self.console_input))
        _require_uint(self.initial_ticks, "record.initial_ticks")
        seen: set[str] = set()
        for name, data in self.files:
            _require(FILE_NAME_PATTERN.match(name) is not None,
                     f"file name {name!r} is not a stable lower-case identifier")
            _require(name not in seen, f"duplicate recorded file {name!r}")
            seen.add(name)
            if not isinstance(data, (bytes, bytearray)):
                raise IoModelError(f"recorded file {name!r} must be bytes")
        for event in self.events:
            if not isinstance(event, InputEvent):
                raise IoModelError("recorded events must be InputEvent instances")

    def to_document(self) -> dict[str, Any]:
        return {
            "console_input_bytes": len(self.console_input),
            "console_input_sha256": hashlib.sha256(self.console_input).hexdigest(),
            "files": [
                {"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in self.files
            ],
            "events": [event.to_document() for event in self.events],
            "initial_ticks": self.initial_ticks,
            "fingerprint": self.fingerprint(),
        }

    def fingerprint(self) -> str:
        payload = {
            "console_input": hashlib.sha256(self.console_input).hexdigest(),
            "files": sorted((name, hashlib.sha256(data).hexdigest())
                            for name, data in self.files),
            "events": [event.to_document() for event in self.events],
            "initial_ticks": self.initial_ticks,
        }
        return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class DeterministicConsole:
    """A bounded console with deterministic input and recorded output."""

    def __init__(self, input_bytes: bytes = b"", *, output_capacity: int = 1 << 20) -> None:
        if not isinstance(input_bytes, (bytes, bytearray)):
            raise IoModelError("console input must be bytes")
        _require_uint(output_capacity, "console output_capacity")
        _require(output_capacity > 0, "console output_capacity must be positive")
        self._input = bytes(input_bytes)
        self._read_position = 0
        self._output = bytearray()
        self._output_capacity = output_capacity

    @property
    def output(self) -> bytes:
        return bytes(self._output)

    @property
    def input_length(self) -> int:
        return len(self._input)

    @property
    def pending_input(self) -> int:
        return len(self._input) - self._read_position

    def write_byte(self, byte: int) -> None:
        value = _require_uint(byte, "console byte", maximum=BYTE_MAX)
        if len(self._output) >= self._output_capacity:
            raise IoModelError("console output capacity exceeded")
        self._output.append(value)

    def read_byte(self, *, policy: InputExhaustionPolicy = InputExhaustionPolicy.EOF) -> int:
        if not isinstance(policy, InputExhaustionPolicy):
            raise IoModelError("policy must be an InputExhaustionPolicy")
        if self._read_position >= len(self._input):
            if policy is InputExhaustionPolicy.FAULT:
                raise IoModelError("console input exhausted")
            return EOF_SENTINEL
        value = self._input[self._read_position]
        self._read_position += 1
        return value

    def to_document(self) -> dict[str, Any]:
        return {
            "input_bytes": len(self._input),
            "input_sha256": hashlib.sha256(self._input).hexdigest(),
            "input_read": self._read_position,
            "output_bytes": len(self._output),
            "output_capacity": self._output_capacity,
            "output_sha256": hashlib.sha256(bytes(self._output)).hexdigest(),
        }

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.to_document()).encode("utf-8")).hexdigest()


class DeterministicFileBuffer:
    """A bounded in-memory file-style buffer; never touches the host filesystem."""

    def __init__(self, name: str, *, capacity: int, initial: bytes = b"",
                 writable: bool = True) -> None:
        _require(FILE_NAME_PATTERN.match(name) is not None,
                 f"file name {name!r} is not a stable lower-case identifier")
        _require_uint(capacity, "file capacity")
        _require(capacity > 0, "file capacity must be positive")
        if not isinstance(initial, (bytes, bytearray)):
            raise IoModelError("file initial content must be bytes")
        if len(initial) > capacity:
            raise IoModelError("file initial content exceeds the capacity")
        if not isinstance(writable, bool):
            raise IoModelError("file writable must be a bool")
        self.name = name
        self.capacity = capacity
        self.writable = writable
        self._data = bytearray(initial)
        self._read_position = 0

    def read(self, length: int) -> bytes:
        _require_uint(length, "file read length")
        end = min(self._read_position + length, len(self._data))
        payload = bytes(self._data[self._read_position:end])
        self._read_position = end
        return payload

    def read_byte(self) -> int:
        chunk = self.read(1)
        return EOF_SENTINEL if not chunk else chunk[0]

    def write(self, payload: bytes) -> None:
        if not self.writable:
            raise IoModelError(f"file {self.name!r} is not writable")
        if not isinstance(payload, (bytes, bytearray)):
            raise IoModelError("file write requires bytes")
        if len(self._data) + len(payload) > self.capacity:
            raise IoModelError(f"file {self.name!r} capacity exceeded")
        self._data.extend(payload)

    def seek(self, position: int) -> None:
        _require_uint(position, "file seek position", maximum=self.capacity)
        self._read_position = min(position, len(self._data))

    @property
    def size(self) -> int:
        return len(self._data)

    @property
    def read_position(self) -> int:
        return self._read_position

    def snapshot(self) -> bytes:
        return bytes(self._data)

    def to_document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capacity": self.capacity,
            "writable": self.writable,
            "size": len(self._data),
            "read_position": self._read_position,
            "sha256": hashlib.sha256(bytes(self._data)).hexdigest(),
        }


class VirtualClock:
    """A deterministic clock advanced only by explicit ticks."""

    def __init__(self, initial_ticks: int = 0) -> None:
        _require_uint(initial_ticks, "initial_ticks")
        self._ticks = initial_ticks

    @property
    def ticks(self) -> int:
        return self._ticks

    def advance(self, delta: int) -> int:
        _require_uint(delta, "clock delta")
        _require(self._ticks + delta <= TICKS_MAX, "clock overflow")
        self._ticks += delta
        return self._ticks

    def to_document(self) -> dict[str, Any]:
        return {"ticks": self._ticks, "source": "virtual"}


class EventQueue:
    """A bounded deterministic event queue with virtual-tick delivery."""

    def __init__(self, events: Iterable[InputEvent] = (), *, max_events: int = 1024) -> None:
        _require_uint(max_events, "max_events")
        _require(max_events > 0, "max_events must be positive")
        ordered = sorted(enumerate(events), key=lambda item: (item[1].tick, item[0]))
        if len(ordered) > max_events:
            raise IoModelError("event plan exceeds max_events")
        for _, event in ordered:
            if not isinstance(event, InputEvent):
                raise IoModelError("events must be InputEvent instances")
        self._events: list[InputEvent] = [event for _, event in ordered]
        self._position = 0
        self._max_events = max_events
        self._delivered: list[InputEvent] = []

    @property
    def pending(self) -> int:
        return len(self._events) - self._position

    @property
    def delivered(self) -> tuple[InputEvent, ...]:
        return tuple(self._delivered)

    def next_tick(self) -> int | None:
        if self._position >= len(self._events):
            return None
        return self._events[self._position].tick

    def pop_due(self, current_tick: int) -> InputEvent | None:
        _require_uint(current_tick, "current_tick")
        if self._position >= len(self._events):
            return None
        event = self._events[self._position]
        if event.tick > current_tick:
            return None
        self._position += 1
        self._delivered.append(event)
        return event

    def to_document(self) -> dict[str, Any]:
        return {
            "planned": len(self._events),
            "delivered": len(self._delivered),
            "pending": self.pending,
            "events": [event.to_document() for event in self._events],
        }


class IoRuntime:
    """The deterministic I/O, timing and input runtime over a recorded input."""

    def __init__(
        self,
        record: RecordedInput,
        *,
        output_capacity: int = 1 << 20,
        input_policy: InputExhaustionPolicy = InputExhaustionPolicy.EOF,
        max_events: int = 1024,
    ) -> None:
        if not isinstance(record, RecordedInput):
            raise IoModelError("IoRuntime requires a RecordedInput")
        if not isinstance(input_policy, InputExhaustionPolicy):
            raise IoModelError("input_policy must be an InputExhaustionPolicy")
        self.record = record
        self.console = DeterministicConsole(record.console_input,
                                            output_capacity=output_capacity)
        self.clock = VirtualClock(record.initial_ticks)
        self.events = EventQueue(record.events, max_events=max_events)
        self.input_policy = input_policy
        self.files: dict[str, DeterministicFileBuffer] = {}
        for name, data in record.files:
            self.files[name] = DeterministicFileBuffer(
                name, capacity=max(len(data), 1), initial=data, writable=False)
        self._event_log: list[int] = []

    # -- console streams ----------------------------------------------------
    def write_stream(self, stream_id: int, byte: int) -> None:
        value = _require_uint(stream_id, "stream_id", maximum=STREAM_ID_MAX)
        if value != STREAM_CONSOLE_OUT:
            raise IoModelError(f"stream {value} is not the declared output stream")
        self.console.write_byte(byte)

    def read_stream(self, stream_id: int) -> int:
        value = _require_uint(stream_id, "stream_id", maximum=STREAM_ID_MAX)
        if value != STREAM_CONSOLE_IN:
            raise IoModelError(f"stream {value} is not the declared input stream")
        return self.console.read_byte(policy=self.input_policy)

    # -- time and events ----------------------------------------------------
    def clock_ticks(self) -> int:
        return self.clock.ticks

    def advance_ticks(self, delta: int) -> int:
        return self.clock.advance(delta)

    def poll_event(self) -> InputEvent | None:
        event = self.events.pop_due(self.clock.ticks)
        if event is not None:
            self._event_log.append(event.code)
        return event

    def poll_event_code(self) -> int:
        event = self.poll_event()
        return NO_EVENT_SENTINEL if event is None else event.code

    def open_file(self, name: str) -> DeterministicFileBuffer:
        if name not in self.files:
            raise IoModelError(f"file {name!r} is not part of the recorded input")
        return self.files[name]

    def to_document(self) -> dict[str, Any]:
        return {
            "record_fingerprint": self.record.fingerprint(),
            "console": self.console.to_document(),
            "clock": self.clock.to_document(),
            "events": self.events.to_document(),
            "event_codes": list(self._event_log),
            "files": [self.files[key].to_document() for key in sorted(self.files)],
            "input_policy": self.input_policy.value,
            "ambient_host_input": False,
        }

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.to_document()).encode("utf-8")).hexdigest()


def ambient_input(*_args: Any, **_kwargs: Any) -> None:
    """Always fails closed: deterministic runs never acquire ambient input."""
    raise IoModelError(
        "the deterministic runtime never acquires ambient host input; "
        "provide an explicit RecordedInput")


# ---------------------------------------------------------------------------
# Runtime service integration (composable with the P4-03 base catalog)
# ---------------------------------------------------------------------------
def io_interfaces() -> tuple[svc.RuntimeServiceInterface, ...]:
    return (
        svc.RuntimeServiceInterface(
            "or.runtime.stream_read", ABI_VERSION, ("u32",), "u32", False,
            "Read one byte from a declared input stream; 0xffffffff means "
            "end-of-input."),
        svc.RuntimeServiceInterface(
            "or.runtime.clock_ticks", ABI_VERSION, (), "u64", False,
            "Read the deterministic virtual tick count (never the host clock)."),
        svc.RuntimeServiceInterface(
            "or.runtime.input_poll", ABI_VERSION, (), "u32", False,
            "Return the next due input event code or 0xffffffff when none is due."),
    )


def io_registry() -> svc.ServiceRegistry:
    return svc.ServiceRegistry(svc.standard_interfaces() + io_interfaces())


def io_handlers(runtime: IoRuntime) -> dict[str, Any]:
    if not isinstance(runtime, IoRuntime):
        raise IoModelError("io_handlers requires an IoRuntime")
    return {
        svc.STREAM_WRITE_INTERFACE: lambda args: runtime.write_stream(args[0], args[1]),
        "or.runtime.stream_read": lambda args: runtime.read_stream(args[0]),
        "or.runtime.clock_ticks": lambda _args: runtime.clock_ticks(),
        "or.runtime.input_poll": lambda _args: runtime.poll_event_code(),
    }


def mediator_with_io(runtime: IoRuntime, *, aliases=None) -> svc.RuntimeServiceMediator:
    if not isinstance(runtime, IoRuntime):
        raise IoModelError("mediator_with_io requires an IoRuntime")
    if aliases is None:
        import p4_runtime_abi_v1 as abi

        aliases = svc.aliases_for_profile(abi.frozen_phase3_profile())
    return svc.RuntimeServiceMediator(io_registry(), aliases=aliases,
                                      handlers=io_handlers(runtime))
