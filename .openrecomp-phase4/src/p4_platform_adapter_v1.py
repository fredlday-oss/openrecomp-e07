#!/usr/bin/env python3
"""OpenRecomp Phase-4 platform adapter interface V1 (P4-05).

An architecture-neutral contract through which future platform-specific
implementations provide platform behaviour without contaminating the
recompiler core or the generic runtime layers:

* ``AdapterIdentity`` - a stable adapter id, a contract-compatible version and
  a description; the adapter id is the only place a platform name may appear;
* ``MemoryMap`` - declared guest memory regions (reusing the P4-02 region
  model and its validation);
* ``TimingProfile`` - the virtual tick source and initial tick count; host
  clock sources are rejected in V1;
* ``ServiceProfile`` - the subset of the *generic* interface catalog the
  adapter supports, its declarative aliases and its handler bindings;
  platform-specific behaviour must be expressed through the generic
  interfaces (via aliases/handlers), never by adding platform names to the
  core catalog;
* ``PlatformHooks`` - optional graphics/audio hooks receiving the P2-08
  frame/audio contracts; hooks are optional and the core never requires them;
* ``bind_platform`` - validates an adapter and composes it with the generic
  runtime layers (P4-02 guest memory, P4-03 mediation, P4-04 deterministic
  I/O), producing a ``BoundPlatform`` with an explicit capabilities document
  and explicit negative compatibility claims.

Do NOT claim support for any console merely because the adapter interface
exists: bound platforms always record ``console_compatibility: false`` and
``arbitrary_binary_compatibility: false``, and the core contract contains no
console or architecture names.  Nothing here is used by, or changes, the
frozen Phase-1/Phase-2/Phase-3 emitters or evidence.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from openrecomp import runtime_abi as rt
from openrecomp.program_model import canonical_json

import p4_deterministic_io_v1 as dio
import p4_guest_memory_v1 as gm
import p4_runtime_services_v1 as svc

PLATFORM_ADAPTER_CONTRACT_NAME = "openrecomp-platform-adapter"
PLATFORM_ADAPTER_VERSION = rt.RUNTIME_ABI_VERSION
ADAPTER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
TIMING_SOURCES = ("virtual",)


class PlatformAdapterError(ValueError):
    """Raised when the platform adapter contract is violated (fail closed)."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PlatformAdapterError(message)


def _require_uint(value: Any, where: str, *, maximum: int = dio.TICKS_MAX) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PlatformAdapterError(f"{where} must be a non-negative integer, got {value!r}")
    if value > maximum:
        raise PlatformAdapterError(f"{where} exceeds {maximum}, got {value!r}")
    return value


@dataclass(frozen=True)
class AdapterIdentity:
    adapter_id: str
    version: str
    description: str

    def __post_init__(self) -> None:
        _require(ADAPTER_ID_PATTERN.match(self.adapter_id) is not None,
                 f"adapter id {self.adapter_id!r} is not a stable lower-case identifier")
        parsed = rt.RuntimeAbiVersion.parse(self.version)
        _require(parsed.compatible_with(rt.RUNTIME_ABI),
                 f"adapter version {self.version!r} is incompatible with the contract")
        _require(bool(self.description), "adapter identity needs a description")

    def to_document(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "version": self.version,
            "description": self.description,
            "contract": {
                "name": PLATFORM_ADAPTER_CONTRACT_NAME,
                "version": PLATFORM_ADAPTER_VERSION,
            },
        }


@dataclass(frozen=True)
class MemoryMap:
    regions: tuple[gm.GuestRegion, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.regions, tuple):
            raise PlatformAdapterError("memory map regions must be a tuple")
        if not self.regions:
            raise PlatformAdapterError("the memory map must declare at least one region")
        for item in self.regions:
            if not isinstance(item, gm.GuestRegion):
                raise PlatformAdapterError(
                    "memory map regions must be GuestRegion instances")
        try:
            gm.GuestMemoryModel(self.regions)
        except gm.GuestMemoryError as exc:
            raise PlatformAdapterError(f"invalid memory map: {exc}") from exc

    def model(self, *, endianness: str = "little",
              alignment: str = "allow") -> gm.GuestMemoryModel:
        return gm.GuestMemoryModel(self.regions, endianness=endianness,
                                   alignment=alignment)

    def to_document(self) -> dict[str, Any]:
        return {"regions": [item.to_document() for item in self.regions]}


@dataclass(frozen=True)
class TimingProfile:
    initial_ticks: int = 0
    tick_source: str = "virtual"

    def __post_init__(self) -> None:
        _require_uint(self.initial_ticks, "timing.initial_ticks")
        _require(self.tick_source in TIMING_SOURCES,
                 f"tick source {self.tick_source!r} is not supported (virtual only)")

    def to_document(self) -> dict[str, Any]:
        return {"initial_ticks": self.initial_ticks, "tick_source": self.tick_source}


@dataclass(frozen=True)
class ServiceProfile:
    interfaces: tuple[svc.RuntimeServiceInterface, ...] = ()
    aliases: tuple[svc.ServiceAlias, ...] = ()
    handlers: Mapping[str, Callable[[tuple[int, ...]], int | None]] = field(
        default_factory=dict)

    def __post_init__(self) -> None:
        catalog = {interface.service_id for interface in generic_interfaces()}
        declared = {interface.service_id for interface in self.interfaces}
        _require(len(declared) == len(self.interfaces),
                 "service profile interfaces must be unique")
        for interface in self.interfaces:
            _require(isinstance(interface, svc.RuntimeServiceInterface),
                     "service profile interfaces must be RuntimeServiceInterface instances")
            _require(interface.service_id in catalog,
                     f"adapter interface {interface.service_id!r} is not in the generic catalog")
        for key in self.handlers:
            _require(key in declared,
                     f"adapter handler {key!r} has no declared interface")
        for interface in self.interfaces:
            if interface.terminates_run:
                _require(interface.service_id not in self.handlers,
                         f"adapter must not bind a handler for terminating interface "
                         f"{interface.service_id!r}")
        for alias in self.aliases:
            _require(isinstance(alias, svc.ServiceAlias),
                     "service profile aliases must be ServiceAlias instances")
            _require(alias.target_service_id in declared
                     or alias.target_service_id in {item.service_id
                                                    for item in svc.standard_interfaces()},
                     f"alias target {alias.target_service_id!r} is not declared by the adapter")

    def to_document(self) -> dict[str, Any]:
        return {
            "interfaces": [interface.to_document() for interface in self.interfaces],
            "aliases": [alias.to_document() for alias in self.aliases],
            "handlers": sorted(self.handlers),
        }


class GraphicsHook:
    """Optional graphics boundary; receives P2-08 RuntimeFrame values."""

    hook_id = "graphics"

    def submit_frame(self, frame: rt.RuntimeFrame) -> None:
        raise NotImplementedError

    def to_document(self) -> dict[str, Any]:
        raise NotImplementedError


class AudioHook:
    """Optional audio boundary; receives P2-08 RuntimeAudio values."""

    hook_id = "audio"

    def submit_audio(self, audio: rt.RuntimeAudio) -> None:
        raise NotImplementedError

    def to_document(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class PlatformHooks:
    graphics: GraphicsHook | None = None
    audio: AudioHook | None = None

    def __post_init__(self) -> None:
        _require(self.graphics is None or isinstance(self.graphics, GraphicsHook),
                 "graphics hook must be a GraphicsHook or None")
        _require(self.audio is None or isinstance(self.audio, AudioHook),
                 "audio hook must be an AudioHook or None")

    def to_document(self) -> dict[str, Any]:
        return {
            "graphics": None if self.graphics is None else self.graphics.to_document(),
            "audio": None if self.audio is None else self.audio.to_document(),
        }


def generic_interfaces() -> tuple[svc.RuntimeServiceInterface, ...]:
    """The approved generic interface catalog (base plus deterministic I/O)."""
    return svc.standard_interfaces() + dio.io_interfaces()


class PlatformAdapter:
    """Base class for future platform-specific adapter implementations."""

    def identity(self) -> AdapterIdentity:
        raise NotImplementedError

    def memory_map(self) -> MemoryMap:
        raise NotImplementedError

    def timing_profile(self) -> TimingProfile:
        return TimingProfile()

    def recorded_input(self) -> dio.RecordedInput:
        return dio.RecordedInput()

    def service_profile(self) -> ServiceProfile:
        return ServiceProfile()

    def hooks(self) -> PlatformHooks:
        return PlatformHooks()


def validate_adapter(adapter: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(adapter, PlatformAdapter):
        return ["adapter must be a PlatformAdapter instance"]
    try:
        identity = adapter.identity()
        if not isinstance(identity, AdapterIdentity):
            problems.append("identity() must return an AdapterIdentity")
    except NotImplementedError:
        problems.append("adapter does not implement identity()")
    except PlatformAdapterError as exc:
        problems.append(f"identity() raised: {exc}")
    try:
        memory = adapter.memory_map()
        if not isinstance(memory, MemoryMap):
            problems.append("memory_map() must return a MemoryMap")
    except NotImplementedError:
        problems.append("adapter does not implement memory_map()")
    except PlatformAdapterError as exc:
        problems.append(f"memory_map() raised: {exc}")
    for name, method, expected in (
        ("timing_profile", adapter.timing_profile, TimingProfile),
        ("recorded_input", adapter.recorded_input, dio.RecordedInput),
        ("service_profile", adapter.service_profile, ServiceProfile),
        ("hooks", adapter.hooks, PlatformHooks),
    ):
        try:
            value = method()
            if not isinstance(value, expected):
                problems.append(f"{name}() must return a {expected.__name__}")
        except PlatformAdapterError as exc:
            problems.append(f"{name}() raised: {exc}")
    try:
        profile = adapter.service_profile()
    except PlatformAdapterError as exc:
        problems.append(f"service_profile() raised: {exc}")
        return problems
    if isinstance(profile, ServiceProfile):
        try:
            svc.RuntimeServiceMediator(
                svc.ServiceRegistry(svc.standard_interfaces() + profile.interfaces),
                aliases=profile.aliases, handlers=dict(profile.handlers))
        except svc.ServiceMediationError as exc:
            problems.append(f"service profile is not bindable: {exc}")
    return problems


@dataclass(frozen=True)
class BoundPlatform:
    identity: AdapterIdentity
    memory: gm.GuestMemoryModel
    io: dio.IoRuntime
    mediator: svc.RuntimeServiceMediator
    hooks: PlatformHooks
    interface_ids: tuple[str, ...]
    capabilities: Mapping[str, bool]
    claims: Mapping[str, bool]

    def to_document(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_document(),
            "interface_ids": list(self.interface_ids),
            "capabilities": dict(self.capabilities),
            "claims": dict(self.claims),
            "memory": self.memory.to_document(),
            "io": self.io.to_document(),
            "hooks": self.hooks.to_document(),
            "service_registry": self.mediator.registry.to_document(),
            "mediator_calls": self.mediator.call_log_document(),
        }

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.to_document()).encode("utf-8")).hexdigest()


def bind_platform(adapter: PlatformAdapter, *, input_policy: dio.InputExhaustionPolicy =
                  dio.InputExhaustionPolicy.EOF) -> BoundPlatform:
    problems = validate_adapter(adapter)
    if problems:
        raise PlatformAdapterError("adapter is not bindable: " + "; ".join(problems))
    identity = adapter.identity()
    memory = adapter.memory_map().model()
    timing = adapter.timing_profile()
    record = adapter.recorded_input()
    if record.initial_ticks != timing.initial_ticks:
        record = dio.RecordedInput(
            console_input=record.console_input, files=record.files,
            events=record.events, initial_ticks=timing.initial_ticks)
    io_runtime = dio.IoRuntime(record, input_policy=input_policy)
    profile = adapter.service_profile()
    interfaces = svc.standard_interfaces() + profile.interfaces
    registry = svc.ServiceRegistry(interfaces)
    handlers: dict[str, Any] = {
        key: value for key, value in dio.io_handlers(io_runtime).items()
        if key in registry.service_ids
    }
    handlers.update(dict(profile.handlers))
    mediator = svc.RuntimeServiceMediator(registry, aliases=profile.aliases,
                                          handlers=handlers)
    interface_ids = tuple(interface.service_id for interface in interfaces)
    capabilities = {
        "memory": True,
        "timing_virtual": timing.tick_source == "virtual",
        "input_streams": "or.runtime.stream_read" in interface_ids,
        "event_delivery": "or.runtime.input_poll" in interface_ids,
        "console_output": "or.runtime.stream_write" in interface_ids,
        "graphics_hook": adapter.hooks().graphics is not None,
        "audio_hook": adapter.hooks().audio is not None,
        "platform_services": bool(profile.handlers),
    }
    claims = {
        "console_compatibility": False,
        "arbitrary_binary_compatibility": False,
        "cycle_accuracy": False,
    }
    return BoundPlatform(
        identity=identity,
        memory=memory,
        io=io_runtime,
        mediator=mediator,
        hooks=adapter.hooks(),
        interface_ids=interface_ids,
        capabilities=capabilities,
        claims=claims,
    )


def core_contract_document() -> dict[str, Any]:
    return {
        "name": PLATFORM_ADAPTER_CONTRACT_NAME,
        "version": PLATFORM_ADAPTER_VERSION,
        "adapter_id_pattern": ADAPTER_ID_PATTERN.pattern,
        "timing_sources": list(TIMING_SOURCES),
        "generic_interfaces": [interface.to_document() for interface in generic_interfaces()],
        "optional_hooks": ["graphics", "audio"],
        "claims": {
            "console_compatibility": False,
            "arbitrary_binary_compatibility": False,
        },
    }


def core_contract_fingerprint() -> str:
    return hashlib.sha256(canonical_json(core_contract_document()).encode("utf-8")).hexdigest()
