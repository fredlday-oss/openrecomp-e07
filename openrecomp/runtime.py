from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from typing import Any

from .module import MemorySegment

TYPE_BITS = {"i1": 1, "i8": 8, "i16": 16, "i32": 32, "i64": 64}


class CoreRuntimeError(RuntimeError):
    """Deterministic runtime failure raised by the Core API reference path."""


def mask_for(type_name: str) -> int:
    try:
        return (1 << TYPE_BITS[type_name]) - 1
    except KeyError as exc:
        raise CoreRuntimeError(f"unsupported integer type {type_name}") from exc


def signed_value(value: int, bits: int) -> int:
    value &= (1 << bits) - 1
    sign = 1 << (bits - 1)
    return value - (1 << bits) if value & sign else value


class GuestState:
    def __init__(self, state_slots: list[dict[str, Any]], initial: Mapping[str, int]):
        self.types = {slot["id"]: slot["type"] for slot in state_slots}
        self.values = {slot: 0 for slot in self.types}
        for slot, value in initial.items():
            self.write(slot, value)

    def read(self, slot: str) -> int:
        if slot not in self.values:
            raise CoreRuntimeError(f"read from undeclared state slot {slot}")
        return self.values[slot]

    def write(self, slot: str, value: int) -> None:
        if slot not in self.types:
            raise CoreRuntimeError(f"write to undeclared state slot {slot}")
        self.values[slot] = value & mask_for(self.types[slot])

    def snapshot(self) -> dict[str, int]:
        return dict(sorted(self.values.items()))


class GuestMemory:
    def __init__(self, size_bytes: int, segments: tuple[MemorySegment, ...], endianness: str):
        if endianness not in {"little", "big"}:
            raise CoreRuntimeError(f"unsupported byte order {endianness}")
        self.endianness = endianness
        self.data = bytearray(size_bytes)
        occupied: list[tuple[int, int, str]] = []
        for segment in sorted(segments, key=lambda s: (s.guest_address, s.name)):
            start = segment.guest_address
            end = start + len(segment.data)
            self._bounds(start, len(segment.data))
            for old_start, old_end, old_name in occupied:
                if max(start, old_start) < min(end, old_end):
                    raise CoreRuntimeError(f"memory segments overlap: {old_name} and {segment.name}")
            occupied.append((start, end, segment.name))
            self.data[start:end] = segment.data

    def _bounds(self, address: int, size: int) -> None:
        if address < 0 or size < 0 or address > len(self.data) or size > len(self.data) - address:
            raise CoreRuntimeError(f"deterministic memory fault at 0x{address:x} size={size}")

    @staticmethod
    def _alignment(address: int, alignment: int, policy: str) -> None:
        if policy == "fault" and address % alignment:
            raise CoreRuntimeError(f"deterministic misalignment fault at 0x{address:x}")
        if policy not in {"fault", "allow"}:
            raise CoreRuntimeError(f"unknown misalignment policy {policy}")

    def load(
        self,
        address: int,
        *,
        width_bits: int,
        result_type: str,
        signed: bool,
        alignment: int,
        misaligned_policy: str,
    ) -> int:
        size = width_bits // 8
        self._alignment(address, alignment, misaligned_policy)
        self._bounds(address, size)
        raw = int.from_bytes(self.data[address:address + size], self.endianness)
        result_bits = TYPE_BITS[result_type]
        if signed and width_bits < result_bits:
            raw = signed_value(raw, width_bits)
        return raw & ((1 << result_bits) - 1)

    def store(
        self,
        address: int,
        value: int,
        *,
        width_bits: int,
        alignment: int,
        misaligned_policy: str,
    ) -> None:
        size = width_bits // 8
        self._alignment(address, alignment, misaligned_policy)
        self._bounds(address, size)
        value &= (1 << width_bits) - 1
        self.data[address:address + size] = value.to_bytes(size, self.endianness)


class HostBinding(ABC):
    """Architecture-neutral boundary between normalized IR and host services."""

    @property
    @abstractmethod
    def contract_version(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def symbols(self) -> frozenset[str]:
        raise NotImplementedError

    @abstractmethod
    def call(self, symbol: str, args: list[int]) -> int | None:
        raise NotImplementedError

    def snapshot(self) -> dict[str, Any]:
        return {}


class CallbackHostBinding(HostBinding):
    """Small reusable binding for tests and simple host integrations."""

    def __init__(
        self,
        contract_version: str,
        callbacks: Mapping[str, Callable[[list[int]], int | None]],
        snapshot: Callable[[], dict[str, Any]] | None = None,
    ):
        self._contract_version = contract_version
        self._callbacks = dict(callbacks)
        self._snapshot = snapshot

    @property
    def contract_version(self) -> str:
        return self._contract_version

    @property
    def symbols(self) -> frozenset[str]:
        return frozenset(self._callbacks)

    def call(self, symbol: str, args: list[int]) -> int | None:
        try:
            callback = self._callbacks[symbol]
        except KeyError as exc:
            raise CoreRuntimeError(f"unbound host symbol {symbol}") from exc
        return callback(args)

    def snapshot(self) -> dict[str, Any]:
        return {} if self._snapshot is None else dict(self._snapshot())
