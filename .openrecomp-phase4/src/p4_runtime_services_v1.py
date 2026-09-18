#!/usr/bin/env python3
"""OpenRecomp Phase-4 runtime service mediation V1 (P4-03).

Replaces fixture-specific external handling with explicit typed and versioned
runtime service interfaces:

* a bounded registry of architecture-neutral runtime service interfaces
  (``or.runtime.*``) with declared argument types, result type, version,
  termination behaviour and description;
* declarative aliases that map an instance's raw service ids onto registry
  interfaces with bound arguments, so fixture-specific handling becomes
  declared data rather than hard-coded dispatch;
* a fail-closed mediator: unknown services, version mismatches, arity/type
  violations, missing handlers and handler failures all return stable P2-08
  failure codes, and generated code can only reach interfaces that the
  instance declares (no ambient host capability);
* a bounded ``or_rt_host_call`` bridge that maps the ABI numeric service ids
  of a declared instance profile onto the mediator.

The standard interface catalog contains no fixture- or platform-specific
names.  The frozen Phase-3 instance is described by a declared alias table
(``p3.exit`` -> ``or.runtime.exit``; ``p3.uart_write`` ->
``or.runtime.stream_write`` on stream 0) and can be replayed through the
generic mediator.  Nothing here is used by, or changes, the frozen
Phase-1/Phase-2/Phase-3 emitters or evidence.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from openrecomp import runtime_abi as rt
from openrecomp.program_model import canonical_json

ABI_VERSION = rt.RUNTIME_ABI_VERSION
SERVICE_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")
SUPPORTED_ARG_TYPES = ("u32", "u64")
SUPPORTED_RESULT_TYPES = ("u32", "u64")
CORE_NAMESPACE = "or.runtime."

EXIT_INTERFACE = "or.runtime.exit"
STREAM_WRITE_INTERFACE = "or.runtime.stream_write"

STREAM_ID_MAX = 0xFFFFFFFF
BYTE_MAX = 0xFF


class ServiceMediationError(ValueError):
    """Raised when the mediation contract is violated (fail closed)."""

    def __init__(self, message: str, *, failure: "rt.RuntimeFailure | None" = None) -> None:
        super().__init__(message)
        self.failure = failure


def _fail(code: rt.RuntimeFailureCode, detail: str) -> ServiceMediationError:
    return ServiceMediationError(detail, failure=rt.RuntimeFailure(code=code, detail=detail))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ServiceMediationError(message)


def _require_uint(value: Any, where: str, *, maximum: int = rt.RUNTIME_MAX_ADDRESS) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ServiceMediationError(f"{where} must be a non-negative integer, got {value!r}")
    if value > maximum:
        raise ServiceMediationError(f"{where} exceeds {maximum}, got {value!r}")
    return value


@dataclass(frozen=True)
class RuntimeServiceInterface:
    service_id: str
    version: str
    arg_types: tuple[str, ...]
    result_type: str | None
    terminates_run: bool
    description: str

    def __post_init__(self) -> None:
        _require(SERVICE_ID_PATTERN.match(self.service_id) is not None,
                 f"service id {self.service_id!r} is not a stable identifier")
        _require(self.service_id.startswith(CORE_NAMESPACE),
                 f"runtime interface {self.service_id!r} must be in the {CORE_NAMESPACE}* namespace")
        parsed = rt.RuntimeAbiVersion.parse(self.version)
        _require(parsed.compatible_with(rt.RUNTIME_ABI),
                 f"interface {self.service_id!r} version {self.version!r} is incompatible")
        _require(all(item in SUPPORTED_ARG_TYPES for item in self.arg_types),
                 f"interface {self.service_id!r} has an unbounded argument type")
        _require(self.result_type is None or self.result_type in SUPPORTED_RESULT_TYPES,
                 f"interface {self.service_id!r} has an unbounded result type")
        _require(bool(self.description), f"interface {self.service_id!r} needs a description")

    @property
    def arg_count(self) -> int:
        return len(self.arg_types)

    def to_document(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "version": self.version,
            "arg_types": list(self.arg_types),
            "result_type": self.result_type,
            "terminates_run": self.terminates_run,
            "description": self.description,
        }


def standard_interfaces() -> tuple[RuntimeServiceInterface, ...]:
    return (
        RuntimeServiceInterface(
            EXIT_INTERFACE, ABI_VERSION, ("u32",), None, True,
            "Terminate the run with a 32-bit exit status; a second "
            "termination request fails closed."),
        RuntimeServiceInterface(
            STREAM_WRITE_INTERFACE, ABI_VERSION, ("u32", "u32"), None, False,
            "Append one byte to a declared bounded output stream "
            "(stream_id, byte)."),
    )


@dataclass(frozen=True)
class ServiceAlias:
    source_service_id: str
    source_version: str
    target_service_id: str
    target_version: str
    bound_args: tuple[int, ...]
    description: str

    def __post_init__(self) -> None:
        _require(SERVICE_ID_PATTERN.match(self.source_service_id) is not None,
                 f"alias source {self.source_service_id!r} is not a stable identifier")
        _require(SERVICE_ID_PATTERN.match(self.target_service_id) is not None,
                 f"alias target {self.target_service_id!r} is not a stable identifier")
        rt.RuntimeAbiVersion.parse(self.source_version)
        rt.RuntimeAbiVersion.parse(self.target_version)
        for index, value in enumerate(self.bound_args):
            _require_uint(value, f"alias {self.source_service_id}.bound_args[{index}]")
        _require(bool(self.description), f"alias {self.source_service_id!r} needs a description")

    def adapt(self, args: Iterable[int]) -> tuple[int, ...]:
        return tuple(self.bound_args) + tuple(args)

    def to_document(self) -> dict[str, Any]:
        return {
            "source_service_id": self.source_service_id,
            "source_version": self.source_version,
            "target_service_id": self.target_service_id,
            "target_version": self.target_version,
            "bound_args": list(self.bound_args),
            "description": self.description,
        }


@dataclass(frozen=True)
class MediatedCall:
    sequence: int
    raw_service_id: str
    interface_id: str
    version: str
    raw_args: tuple[int, ...]
    adapted_args: tuple[int, ...]
    ok: bool
    failure_code: str | None

    def to_document(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "raw_service_id": self.raw_service_id,
            "interface_id": self.interface_id,
            "version": self.version,
            "raw_args": list(self.raw_args),
            "adapted_args": list(self.adapted_args),
            "ok": self.ok,
            "failure_code": self.failure_code,
        }


class ServiceRegistry:
    """A bounded, versioned set of runtime service interfaces."""

    def __init__(self, interfaces: Iterable[RuntimeServiceInterface]) -> None:
        self._interfaces: dict[str, RuntimeServiceInterface] = {}
        for interface in interfaces:
            if not isinstance(interface, RuntimeServiceInterface):
                raise ServiceMediationError("registry entries must be RuntimeServiceInterface")
            if interface.service_id in self._interfaces:
                raise ServiceMediationError(f"duplicate interface id {interface.service_id!r}")
            self._interfaces[interface.service_id] = interface
        if not self._interfaces:
            raise ServiceMediationError("the service registry must not be empty")

    @property
    def service_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._interfaces))

    def has(self, service_id: str) -> bool:
        return service_id in self._interfaces

    def interface(self, service_id: str, version: str | None = None) -> RuntimeServiceInterface:
        if service_id not in self._interfaces:
            raise _fail(rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE,
                        f"unknown runtime service {service_id!r}")
        interface = self._interfaces[service_id]
        if version is not None and version != interface.version:
            raise _fail(rt.RuntimeFailureCode.ABI_VERSION_MISMATCH,
                        f"service {service_id!r} version {version!r} != {interface.version!r}")
        return interface

    def to_document(self) -> dict[str, Any]:
        return {"interfaces": [self._interfaces[key].to_document() for key in self.service_ids]}

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.to_document()).encode("utf-8")).hexdigest()


class BoundedOutputStream:
    """A generic bounded byte sink usable as a stream_write handler."""

    def __init__(self, stream_id: int, capacity: int) -> None:
        _require_uint(stream_id, "stream_id", maximum=STREAM_ID_MAX)
        _require_uint(capacity, "capacity")
        _require(capacity > 0, "capacity must be positive")
        self.stream_id = stream_id
        self.capacity = capacity
        self.data = bytearray()

    def __call__(self, args: tuple[int, ...]) -> None:
        if len(args) != 2:
            raise ServiceMediationError("stream_write requires (stream_id, byte)")
        if args[0] != self.stream_id:
            raise ServiceMediationError(
                f"stream {args[0]} is not the declared stream {self.stream_id}")
        byte = _require_uint(args[1], "stream byte", maximum=BYTE_MAX)
        if len(self.data) >= self.capacity:
            raise ServiceMediationError("output stream capacity exceeded")
        self.data.append(byte)

    def to_document(self) -> dict[str, Any]:
        return {
            "stream_id": self.stream_id,
            "capacity": self.capacity,
            "length": len(self.data),
            "sha256": hashlib.sha256(bytes(self.data)).hexdigest(),
        }


class RuntimeServiceMediator:
    """Mediates declared raw service calls onto typed/versioned interfaces."""

    def __init__(
        self,
        registry: ServiceRegistry,
        *,
        aliases: Iterable[ServiceAlias] = (),
        handlers: Mapping[str, Callable[[tuple[int, ...]], int | None]] | None = None,
    ) -> None:
        if not isinstance(registry, ServiceRegistry):
            raise ServiceMediationError("mediator requires a ServiceRegistry")
        self._registry = registry
        self._aliases: dict[str, ServiceAlias] = {}
        for alias in aliases:
            if not isinstance(alias, ServiceAlias):
                raise ServiceMediationError("aliases must be ServiceAlias instances")
            if alias.source_service_id in self._aliases:
                raise ServiceMediationError(f"duplicate alias source {alias.source_service_id!r}")
            self._registry.interface(alias.target_service_id, alias.target_version)
            self._aliases[alias.source_service_id] = alias
        self._handlers = dict(handlers or {})
        for key in self._handlers:
            interface = self._registry.interface(key)
            if interface.terminates_run:
                raise ServiceMediationError(
                    f"terminating interface {key!r} must not have a handler")
        self.terminated = False
        self.exit_status: int | None = None
        self.failure: rt.RuntimeFailure | None = None
        self._calls: list[MediatedCall] = []

    @property
    def registry(self) -> ServiceRegistry:
        return self._registry

    @property
    def aliases(self) -> tuple[ServiceAlias, ...]:
        return tuple(self._aliases[key] for key in sorted(self._aliases))

    @property
    def calls(self) -> tuple[MediatedCall, ...]:
        return tuple(self._calls)

    @property
    def failed(self) -> bool:
        return self.failure is not None

    def _latch(self, failure: rt.RuntimeFailure) -> rt.RuntimeResult:
        if self.failure is None:
            self.failure = failure
        return rt.RuntimeResult.failed(self.failure)

    def _failure_result(self, code: rt.RuntimeFailureCode, detail: str,
                        raw_service_id: str, interface_id: str, version: str,
                        raw_args: tuple[int, ...],
                        adapted_args: tuple[int, ...]) -> rt.RuntimeResult:
        self._calls.append(MediatedCall(
            sequence=len(self._calls), raw_service_id=raw_service_id,
            interface_id=interface_id, version=version, raw_args=raw_args,
            adapted_args=adapted_args, ok=False, failure_code=code.value))
        return self._latch(rt.RuntimeFailure(code=code, detail=detail))

    def dispatch(self, raw_service_id: str, args: Iterable[int] = (), *,
                 version: str | None = None) -> rt.RuntimeResult:
        if self.terminated:
            return self._failure_result(
                rt.RuntimeFailureCode.TRAP, "operation after run termination",
                raw_service_id, raw_service_id, version or ABI_VERSION, tuple(args), tuple(args))
        if self.failure is not None:
            # Fail closed: the first failure is preserved and every later call
            # returns it without reaching a handler.
            return rt.RuntimeResult.failed(self.failure)
        raw_args = tuple(args)
        alias = self._aliases.get(raw_service_id)
        if alias is not None:
            requested = alias.source_version if version is None else version
            if requested != alias.source_version:
                return self._failure_result(
                    rt.RuntimeFailureCode.ABI_VERSION_MISMATCH,
                    f"service {raw_service_id!r} version {requested!r} != {alias.source_version!r}",
                    raw_service_id, alias.target_service_id, requested, raw_args, ())
            interface_id = alias.target_service_id
            interface_version = alias.target_version
            adapted = alias.adapt(raw_args)
        else:
            interface_id = raw_service_id
            try:
                interface = self._registry.interface(interface_id, version)
            except ServiceMediationError as exc:
                code = exc.failure.code if exc.failure else rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE
                return self._failure_result(
                    code, str(exc), raw_service_id, interface_id,
                    version or ABI_VERSION, raw_args, raw_args)
            interface_version = interface.version
            adapted = raw_args
        try:
            interface = self._registry.interface(interface_id, interface_version)
        except ServiceMediationError as exc:
            code = exc.failure.code if exc.failure else rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE
            return self._failure_result(code, str(exc), raw_service_id,
                                        interface_id, interface_version, raw_args, adapted)
        if len(adapted) != interface.arg_count:
            return self._failure_result(
                rt.RuntimeFailureCode.HOST_CALL_ARITY,
                f"service {interface_id!r} expects {interface.arg_count} argument(s), "
                f"got {len(adapted)}", raw_service_id, interface_id, interface_version,
                raw_args, adapted)
        for index, (argument, arg_type) in enumerate(zip(adapted, interface.arg_types)):
            limit = 0xFFFFFFFF if arg_type == "u32" else rt.RUNTIME_MAX_ADDRESS
            if isinstance(argument, bool) or not isinstance(argument, int) or not 0 <= argument <= limit:
                return self._failure_result(
                    rt.RuntimeFailureCode.HOST_CALL_ARITY,
                    f"service {interface_id!r} argument {index} violates the declared "
                    f"{arg_type} type", raw_service_id, interface_id, interface_version,
                    raw_args, adapted)
        if interface.terminates_run:
            self.exit_status = int(adapted[0]) & 0xFFFFFFFF
            self.terminated = True
            result = rt.RuntimeResult.success()
        else:
            handler = self._handlers.get(interface_id)
            if handler is None:
                return self._failure_result(
                    rt.RuntimeFailureCode.UNSUPPORTED_OPERATION,
                    f"service {interface_id!r} has no handler in this mediator",
                    raw_service_id, interface_id, interface_version, raw_args, adapted)
            try:
                returned = handler(adapted)
            except Exception as exc:  # noqa: BLE001 - converted to a stable code
                return self._failure_result(
                    rt.RuntimeFailureCode.HOST_SERVICE_FAILED,
                    f"service {interface_id!r} raised {type(exc).__name__}",
                    raw_service_id, interface_id, interface_version, raw_args, adapted)
            if interface.result_type is None:
                if returned is not None:
                    return self._failure_result(
                        rt.RuntimeFailureCode.HOST_SERVICE_FAILED,
                        f"service {interface_id!r} returned a value but declares no result",
                        raw_service_id, interface_id, interface_version, raw_args, adapted)
                result = rt.RuntimeResult.success()
            else:
                limit = 0xFFFFFFFF if interface.result_type == "u32" else rt.RUNTIME_MAX_ADDRESS
                if returned is None or isinstance(returned, bool) or not isinstance(returned, int) \
                        or not 0 <= returned <= limit:
                    return self._failure_result(
                        rt.RuntimeFailureCode.HOST_SERVICE_FAILED,
                        f"service {interface_id!r} result violates the declared "
                        f"{interface.result_type} type", raw_service_id, interface_id,
                        interface_version, raw_args, adapted)
                result = rt.RuntimeResult.success(returned)
        self._calls.append(MediatedCall(
            sequence=len(self._calls), raw_service_id=raw_service_id,
            interface_id=interface_id, version=interface_version, raw_args=raw_args,
            adapted_args=adapted, ok=True, failure_code=None))
        return result

    def call_log_document(self) -> dict[str, Any]:
        return {
            "calls": [call.to_document() for call in self._calls],
            "terminated": self.terminated,
            "exit_status": self.exit_status,
            "failure": None if self.failure is None else self.failure.to_document(),
        }

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.call_log_document()).encode("utf-8")).hexdigest()


class AbiHostCallBridge:
    """Maps ABI numeric service ids of a declared profile onto the mediator."""

    def __init__(
        self,
        mediator: RuntimeServiceMediator,
        profile: Any,
        *,
        failure_codes: tuple[str, ...] = rt.RUNTIME_FAILURE_CODES,
    ) -> None:
        if not isinstance(mediator, RuntimeServiceMediator):
            raise ServiceMediationError("bridge requires a RuntimeServiceMediator")
        services = getattr(profile, "services", None)
        if not services:
            raise ServiceMediationError("bridge requires a declared instance profile")
        self._mediator = mediator
        self._profile = profile
        self._by_numeric: dict[int, Any] = {}
        for service in services:
            if service.numeric_id in self._by_numeric:
                raise ServiceMediationError(f"duplicate numeric service id {service.numeric_id}")
            self._by_numeric[service.numeric_id] = service
            known = (service.service_id in {alias.source_service_id
                                            for alias in mediator.aliases}
                     or mediator.registry.has(service.service_id))
            if not known:
                raise ServiceMediationError(
                    f"profile service {service.service_id!r} has no alias or interface")
        self._codes = {code: index + 1 for index, code in enumerate(failure_codes)}
        for code in ("UNKNOWN_HOST_SERVICE", "HOST_CALL_ARITY", "ABI_VERSION_MISMATCH"):
            if code not in self._codes:
                raise ServiceMediationError(f"failure code {code!r} is not available")

    def host_call(self, numeric_id: int, argc: int,
                  args: tuple[int, ...]) -> tuple[int, int | None]:
        service = self._by_numeric.get(numeric_id)
        if service is None:
            return self._codes["UNKNOWN_HOST_SERVICE"], None
        if argc != len(service.arg_types):
            return self._codes["HOST_CALL_ARITY"], None
        result = self._mediator.dispatch(service.service_id, tuple(args),
                                         version=service.version)
        if not result.ok:
            return self._codes[result.failure.code.value], None
        return 0, result.value


# --- declared instance data (the only fixture-specific section) -------------
FROZEN_SERVICE_MAP: dict[str, tuple[str, tuple[int, ...]]] = {
    "p3.exit": (EXIT_INTERFACE, ()),
    "p3.uart_write": (STREAM_WRITE_INTERFACE, (0,)),
}
FROZEN_SERVICE_DESCRIPTIONS = {
    "p3.exit": "Frozen Phase-3 termination request mapped onto or.runtime.exit.",
    "p3.uart_write": "Frozen Phase-3 byte output mapped onto or.runtime.stream_write stream 0.",
}


def aliases_for_profile(profile: Any,
                        mapping: Mapping[str, tuple[str, tuple[int, ...]]] | None = None,
                        ) -> tuple[ServiceAlias, ...]:
    declared = FROZEN_SERVICE_MAP if mapping is None else mapping
    services = getattr(profile, "services", None)
    if not services:
        raise ServiceMediationError("aliases_for_profile requires a profile with services")
    aliases: list[ServiceAlias] = []
    for service in services:
        if service.service_id not in declared:
            raise ServiceMediationError(
                f"profile service {service.service_id!r} has no declared alias mapping")
        target_id, bound = declared[service.service_id]
        aliases.append(ServiceAlias(
            source_service_id=service.service_id,
            source_version=service.version,
            target_service_id=target_id,
            target_version=ABI_VERSION,
            bound_args=tuple(bound),
            description=FROZEN_SERVICE_DESCRIPTIONS.get(
                service.service_id, f"Alias {service.service_id} -> {target_id}."),
        ))
    return tuple(aliases)


def standard_registry() -> ServiceRegistry:
    return ServiceRegistry(standard_interfaces())


def frozen_mediator(*, output_capacity: int = 1 << 20,
                    aliases: Iterable[ServiceAlias] | None = None,
                    ) -> tuple[RuntimeServiceMediator, BoundedOutputStream]:
    """Build a generic mediator configured for the declared frozen instance."""
    import p4_runtime_abi_v1 as abi

    profile = abi.frozen_phase3_profile()
    resolved = aliases_for_profile(profile) if aliases is None else tuple(aliases)
    sink = BoundedOutputStream(0, output_capacity)
    mediator = RuntimeServiceMediator(
        standard_registry(), aliases=resolved,
        handlers={STREAM_WRITE_INTERFACE: sink})
    return mediator, sink
