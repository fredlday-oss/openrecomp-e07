#!/usr/bin/env python3
"""OpenRecomp Phase-4 generated-code <-> runtime ABI V1 (P4-01).

This module is the executable, architecture-neutral contract for the boundary
between generated host code and the OpenRecomp generic runtime.  It
formalizes the implicit C surface used by the verified Phase-3 path
(``openrecomp_*`` execution-state accessors provided by generated code and
``or_rt_*`` entries provided by the runtime) as an explicit, versioned,
machine-checkable contract covering:

* execution state: typed generated-code accessors for the register file, the
  program counter, the step counter, the failure latch, the loaded image and
  the memory region table;
* calls: one checked, synchronous host-call entry point with typed and
  versioned service descriptors; unknown services, arity/type violations and
  version mismatches fail closed;
* returns/exits: an explicit termination contract (a service declared
  ``terminates_run`` ends the run deterministically; a run that returns from
  its entry function without a declared termination is a deterministic
  fault);
* faults: the P2-08 architecture-neutral failure codes, a first-failure latch
  and fail-closed behaviour on every boundary;
* memory service boundaries: width/endianness/bounds-checked read and write
  services that never expose a host pointer;
* deterministic observable state: a canonical state document and a defined
  FNV-1a 64 digest over a byte-exact layout.

The contract core contains no fixture- or platform-specific names.  A concrete
program is described by a declared :class:`InstanceProfile` (for example the
frozen Phase-3 CoreMark instance); the verifier checks generated sources
against the contract plus their profile.  Nothing in this module is used by,
or changes, the frozen Phase-1/Phase-2/Phase-3 emitters or evidence.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from openrecomp import runtime_abi as rt
from openrecomp.program_model import canonical_json

CONTRACT_NAME = "openrecomp-generated-runtime-abi"
CONTRACT_VERSION = rt.RUNTIME_ABI_VERSION

CONTRACT_DOCUMENT_PATH = ".openrecomp-phase4/contracts/generated_runtime_abi_v1.json"
CONTRACT_HEADER_PATH = ".openrecomp-phase4/ports/generated_runtime_abi_v1.h"
PROFILE_DOCUMENT_PATH = (
    ".openrecomp-phase4/ports/generated_runtime_abi_v1_profile_mips32_o32.json")

RUNTIME_PROVIDES = "runtime-provides"
GENERATED_PROVIDES = "generated-provides"
DIRECTIONS = (RUNTIME_PROVIDES, GENERATED_PROVIDES)

C_TYPES = frozenset({
    "void", "int", "int32_t", "uint32_t", "uint64_t", "size_t",
    "const char *", "const uint8_t *", "const uint64_t *", "uint64_t *",
    "uint32_t *",
})
ARG_TYPES = ("u32", "u64")
RESULT_TYPES = ("u32", "u64")
SERVICE_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")
AUX_ACCESSOR_PATTERN = re.compile(r"^openrecomp_[a-z][a-z0-9_]*$")
CORE_SERVICE_NAMESPACE = "or.runtime."

ENTRY_RETURN_POLICY = "fault"
OBSERVABLE_FIELDS = (
    "image_sha256",
    "registers",
    "aux_registers",
    "pc",
    "steps",
    "exit_status",
    "external_output",
    "failure",
)
OBSERVABLE_DIGEST = "fnv1a-64"
OBSERVABLE_LAYOUT = (
    "fnv1a64 over: ascii 'OROBS1' | u32le image_length | image bytes | "
    "u32le register_count | each register u32le | u32le aux_count | each aux "
    "value u32le in profile order | u32le pc | u64le steps | u32le "
    "exit_status (0xffffffff when absent) | u32le external_output_length | "
    "external_output bytes")
EXIT_STATUS_ABSENT = 0xffffffff
FNV1A64_OFFSET = 0xCBF29CE484222325
FNV1A64_PRIME = 0x100000001B3

GENERATED_INCLUDE_SET = frozenset({"stdint.h", "stddef.h"})
RUNTIME_INCLUDE_SET = frozenset({"stdint.h", "stddef.h", "stdio.h", "string.h"})
PLATFORM_TOKENS = (
    "windows.h", "winsock", "xaudio", "wasapi", "direct3d", "d3d11", "d3d12",
    "vulkan", "opengl", "SDL_", "Rt64", "RT64", "mmap(", "VirtualAlloc",
    "fopen", "pthread", "unistd.h", "sys/types.h", "dlopen",
)


class P4AbiError(ValueError):
    """Raised when the ABI contract itself is violated (fail closed)."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise P4AbiError(message)


def _normalize_type(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*\*+\s*", " *", collapsed)


def _split_param(text: str) -> tuple[str, str]:
    stripped = text.strip()
    match = re.match(r"^(.*?)\s*([A-Za-z_][A-Za-z0-9_]*)$", stripped)
    _require(match is not None, f"parameter {text!r} has no name")
    return _normalize_type(match.group(1)), match.group(2)


# ---------------------------------------------------------------------------
# Contract model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AbiParam:
    name: str
    c_type: str
    doc: str = ""

    def __post_init__(self) -> None:
        _require(re.match(r"^[a-z][a-z0-9_]*$", self.name) is not None,
                 f"parameter name {self.name!r} is not a stable lower-case identifier")
        _require(self.c_type in C_TYPES, f"parameter type {self.c_type!r} is not bounded")

    def c_text(self) -> str:
        if self.c_type.endswith("*"):
            return f"{self.c_type}{self.name}"
        return f"{self.c_type} {self.name}"

    def to_document(self) -> dict[str, Any]:
        return {"name": self.name, "c_type": self.c_type, "doc": self.doc}


@dataclass(frozen=True)
class AbiSymbol:
    name: str
    returns: str
    params: tuple[AbiParam, ...]
    direction: str
    semantics: str

    def __post_init__(self) -> None:
        _require(re.match(r"^[a-z][a-z0-9_]*$", self.name) is not None,
                 f"symbol name {self.name!r} is not a stable lower-case identifier")
        _require(self.returns in C_TYPES, f"symbol {self.name} return type {self.returns!r} is not bounded")
        _require(self.direction in DIRECTIONS, f"symbol {self.name} has invalid direction {self.direction!r}")
        if self.direction == RUNTIME_PROVIDES:
            _require(self.name.startswith("or_rt_"),
                     f"runtime-provides symbol {self.name!r} must be in the or_rt_* namespace")
        else:
            _require(self.name.startswith("openrecomp_"),
                     f"generated-provides symbol {self.name!r} must be in the openrecomp_* namespace")
        _require(bool(self.semantics), f"symbol {self.name} needs documented semantics")
        _require(len({param.name for param in self.params}) == len(self.params),
                 f"symbol {self.name} has duplicate parameter names")

    def signature(self) -> str:
        params = ", ".join(param.c_text() for param in self.params) or "void"
        prefix = self.returns if self.returns.endswith("*") else self.returns + " "
        return f"{prefix}{self.name}({params})"

    def to_document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "returns": self.returns,
            "params": [param.to_document() for param in self.params],
            "direction": self.direction,
            "semantics": self.semantics,
            "signature": self.signature(),
        }


@dataclass(frozen=True)
class CoreService:
    service_id: str
    version: str
    arg_types: tuple[str, ...]
    result_type: str | None
    terminates_run: bool
    description: str

    def __post_init__(self) -> None:
        _require(SERVICE_ID_PATTERN.match(self.service_id) is not None,
                 f"core service id {self.service_id!r} is not a stable identifier")
        _require(self.service_id.startswith(CORE_SERVICE_NAMESPACE),
                 f"core service {self.service_id!r} must be in the {CORE_SERVICE_NAMESPACE}* namespace")
        _require(rt.RuntimeAbiVersion.parse(self.version).compatible_with(rt.RUNTIME_ABI),
                 f"core service {self.service_id!r} version {self.version!r} is incompatible")
        _require(all(item in ARG_TYPES for item in self.arg_types),
                 f"core service {self.service_id!r} has an unbounded argument type")
        _require(self.result_type is None or self.result_type in RESULT_TYPES,
                 f"core service {self.service_id!r} has an unbounded result type")
        _require(bool(self.description), f"core service {self.service_id!r} needs a description")

    def to_document(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "version": self.version,
            "arg_types": list(self.arg_types),
            "result_type": self.result_type,
            "terminates_run": self.terminates_run,
            "description": self.description,
        }


@dataclass(frozen=True)
class ServiceDescriptor:
    """A typed, versioned instance service declaration."""

    service_id: str
    numeric_id: int
    version: str
    arg_types: tuple[str, ...]
    result_type: str | None
    terminates_run: bool
    description: str

    def __post_init__(self) -> None:
        _require(SERVICE_ID_PATTERN.match(self.service_id) is not None,
                 f"service id {self.service_id!r} is not a stable identifier")
        _require(not isinstance(self.numeric_id, bool) and self.numeric_id > 0,
                 f"service {self.service_id!r} needs a positive numeric id")
        _require(rt.RuntimeAbiVersion.parse(self.version).compatible_with(rt.RUNTIME_ABI),
                 f"service {self.service_id!r} version {self.version!r} is incompatible")
        _require(all(item in ARG_TYPES for item in self.arg_types),
                 f"service {self.service_id!r} has an unbounded argument type")
        _require(self.result_type is None or self.result_type in RESULT_TYPES,
                 f"service {self.service_id!r} has an unbounded result type")
        _require(bool(self.description), f"service {self.service_id!r} needs a description")

    @property
    def macro(self) -> str:
        return "OR_RT_SERVICE_" + re.sub(r"[^A-Za-z0-9]", "_", self.service_id).upper()

    def to_document(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "numeric_id": self.numeric_id,
            "version": self.version,
            "arg_types": list(self.arg_types),
            "result_type": self.result_type,
            "terminates_run": self.terminates_run,
            "description": self.description,
            "macro": self.macro,
        }


@dataclass(frozen=True)
class InstanceProfile:
    """A declared program instance of the ABI (capability subset + services)."""

    name: str
    abi_version: str
    endianness: str
    widths: tuple[int, ...]
    register_count: int
    aux_registers: tuple[tuple[str, str, str], ...]
    services: tuple[ServiceDescriptor, ...]
    entry_return_policy: str
    artifacts: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        _require(bool(self.name), "profile needs a name")
        _require(rt.RuntimeAbiVersion.parse(self.abi_version).compatible_with(rt.RUNTIME_ABI),
                 f"profile ABI version {self.abi_version!r} is incompatible")
        _require(self.endianness in rt.RUNTIME_ENDIANNESS,
                 f"profile endianness {self.endianness!r} is unsupported")
        _require(self.widths and set(self.widths) <= rt.RUNTIME_WIDTHS,
                 "profile widths must be a non-empty subset of the ABI widths")
        _require(not isinstance(self.register_count, bool) and 0 < self.register_count <= 256,
                 "profile register_count must be in 1..256")
        aux_names = [item[0] for item in self.aux_registers]
        _require(len(set(aux_names)) == len(aux_names), "profile aux register names must be unique")
        for name, accessor, c_type in self.aux_registers:
            _require(re.match(r"^[a-z][a-z0-9_]*$", name) is not None,
                     f"aux register name {name!r} is not a stable identifier")
            _require(AUX_ACCESSOR_PATTERN.match(accessor) is not None,
                     f"aux accessor {accessor!r} is not in the openrecomp_* generated namespace")
            _require(c_type == "uint32_t", f"aux accessor {accessor!r} must be uint32_t")
        ids = [service.service_id for service in self.services]
        _require(len(set(ids)) == len(ids), "profile service ids must be unique")
        numbers = [service.numeric_id for service in self.services]
        _require(len(set(numbers)) == len(numbers), "profile service numeric ids must be unique")
        if self.services:
            _require(sorted(numbers) == list(range(1, len(numbers) + 1)),
                     "profile service numeric ids must be exactly 1..N")
            canonical = {service_id: index for index, service_id in
                         enumerate(sorted(ids), start=1)}
            _require(all(service.numeric_id == canonical[service.service_id]
                         for service in self.services),
                     "profile service numeric ids must follow the canonical sorted-id order")
        macro_names = [service.macro for service in self.services]
        _require(len(set(macro_names)) == len(macro_names), "profile service macros must be unique")
        _require(self.entry_return_policy == ENTRY_RETURN_POLICY,
                 f"entry_return_policy must be {ENTRY_RETURN_POLICY!r}")
        for path, digest in self.artifacts:
            _require(bool(path) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
                     f"profile artifact {path!r} needs a sha256")

    def service(self, service_id: str) -> ServiceDescriptor:
        for service in self.services:
            if service.service_id == service_id:
                return service
        raise P4AbiError(f"unknown instance service {service_id!r}")

    def to_document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "abi_version": self.abi_version,
            "endianness": self.endianness,
            "widths": list(self.widths),
            "register_count": self.register_count,
            "aux_registers": [
                {"name": name, "accessor": accessor, "c_type": c_type}
                for name, accessor, c_type in self.aux_registers
            ],
            "services": [service.to_document() for service in self.services],
            "entry_return_policy": self.entry_return_policy,
            "artifacts": [
                {"path": path, "sha256": digest} for path, digest in self.artifacts
            ],
        }


@dataclass(frozen=True)
class RuntimeAbiContract:
    name: str
    version: str
    symbols: tuple[AbiSymbol, ...]
    core_services: tuple[CoreService, ...]
    failure_codes: tuple[str, ...]
    widths: tuple[int, ...]
    endianness: tuple[str, ...]
    entry_return_policy: str
    observable_fields: tuple[str, ...]
    observable_digest: str
    observable_layout: str

    def __post_init__(self) -> None:
        _require(self.name == CONTRACT_NAME, "contract name mismatch")
        _require(self.version == CONTRACT_VERSION, "contract version mismatch")
        names = [symbol.name for symbol in self.symbols]
        _require(len(set(names)) == len(names), "contract symbol names must be unique")
        for symbol in self.symbols:
            if symbol.direction == RUNTIME_PROVIDES:
                _require(symbol.name.startswith("or_rt_"),
                         f"runtime-provides symbol {symbol.name!r} must be in the or_rt_* namespace")
            else:
                _require(symbol.name.startswith("openrecomp_"),
                         f"generated-provides symbol {symbol.name!r} must be in the openrecomp_* namespace")
        service_ids = [service.service_id for service in self.core_services]
        _require(len(set(service_ids)) == len(service_ids), "core service ids must be unique")
        _require(self.entry_return_policy == ENTRY_RETURN_POLICY,
                 f"entry_return_policy must be {ENTRY_RETURN_POLICY!r}")
        _require(self.observable_digest == OBSERVABLE_DIGEST, "observable digest must be fnv1a-64")
        _require(bool(self.observable_fields) and bool(self.observable_layout),
                 "observable contract needs fields and a layout")
        for code in self.failure_codes:
            _require(code in rt.RUNTIME_FAILURE_CODES, f"failure code {code!r} is not an ABI failure code")

    def runtime_symbols(self) -> dict[str, AbiSymbol]:
        return {symbol.name: symbol for symbol in self.symbols
                if symbol.direction == RUNTIME_PROVIDES}

    def generated_symbols(self) -> dict[str, AbiSymbol]:
        return {symbol.name: symbol for symbol in self.symbols
                if symbol.direction == GENERATED_PROVIDES}

    def core_service(self, service_id: str) -> CoreService:
        for service in self.core_services:
            if service.service_id == service_id:
                return service
        raise P4AbiError(f"unknown core service {service_id!r}")

    def verify_profile(self, profile: InstanceProfile) -> list[str]:
        problems: list[str] = []
        if profile.abi_version != self.version:
            problems.append(
                f"profile {profile.name!r} version {profile.abi_version!r} != contract {self.version!r}")
        if not set(profile.widths) <= set(self.widths):
            problems.append(f"profile {profile.name!r} declares unsupported widths {profile.widths}")
        if profile.endianness not in self.endianness:
            problems.append(f"profile {profile.name!r} declares unsupported endianness")
        if profile.entry_return_policy != self.entry_return_policy:
            problems.append(f"profile {profile.name!r} entry-return policy mismatch")
        reserved = {symbol.name for symbol in self.symbols}
        for _, accessor, _ in profile.aux_registers:
            if accessor in reserved:
                problems.append(f"aux accessor {accessor!r} collides with a contract symbol")
        for service in profile.services:
            if service.service_id.startswith(CORE_SERVICE_NAMESPACE):
                problems.append(
                    f"instance service {service.service_id!r} is in the reserved core namespace")
            if service.version != self.version:
                problems.append(
                    f"instance service {service.service_id!r} version {service.version!r} != {self.version!r}")
        return problems

    def to_document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "runtime_abi": {"name": rt.RUNTIME_ABI_NAME, "version": rt.RUNTIME_ABI_VERSION},
            "failure_codes": [
                {"code": code, "value": index + 1}
                for index, code in enumerate(self.failure_codes)
            ],
            "memory": {
                "widths": sorted(self.widths),
                "endianness": sorted(self.endianness),
                "max_address": rt.RUNTIME_MAX_ADDRESS,
                "host_pointers_exposed": False,
            },
            "symbols": [symbol.to_document() for symbol in self.symbols],
            "core_services": [service.to_document() for service in self.core_services],
            "entry_return_policy": self.entry_return_policy,
            "observable": {
                "fields": list(self.observable_fields),
                "digest": self.observable_digest,
                "digest_layout": self.observable_layout,
            },
        }

    def to_c_header(self) -> str:
        lines = [
            "/* OpenRecomp generated-code <-> runtime ABI V1 (P4-01). "
            "Architecture-neutral. */",
            f"/* abi_name: {self.name} */",
            f"/* abi_version: {self.version} */",
            "/* This header is emitted deterministically from "
            ".openrecomp-phase4/src/p4_runtime_abi_v1.py. */",
            "#ifndef OPENRECOMP_GENERATED_RUNTIME_ABI_V1_H",
            "#define OPENRECOMP_GENERATED_RUNTIME_ABI_V1_H",
            "#include <stdint.h>",
            "#include <stddef.h>",
            "",
            "/* Architecture-neutral failure codes (P2-08 order). */",
            "enum {",
            "    OR_RT_OK = 0,",
        ]
        for index, code in enumerate(self.failure_codes):
            comma = "," if index + 1 < len(self.failure_codes) else ","
            lines.append(f"    OR_RT_{code} = {index + 1}{comma}")
        lines.append("};")
        lines.append("")
        lines.append("/* Entries the runtime must provide to generated code. */")
        for symbol in self.symbols:
            if symbol.direction == RUNTIME_PROVIDES:
                lines.append(f"/* {symbol.semantics} */")
                lines.append(f"extern {symbol.signature()};")
        lines.append("")
        lines.append("/* Accessors generated code must provide to the runtime. */")
        for symbol in self.symbols:
            if symbol.direction == GENERATED_PROVIDES:
                lines.append(f"/* {symbol.semantics} */")
                lines.append(f"{symbol.signature()};")
        lines.append("")
        lines.append("/* Reserved core service namespace (typed, versioned): */")
        for service in self.core_services:
            args = ", ".join(service.arg_types) or "none"
            result = service.result_type or "none"
            terminate = "terminates-run" if service.terminates_run else "non-terminating"
            lines.append(
                f"/* {service.service_id} v{service.version}: args=({args}) "
                f"result={result} {terminate} - {service.description} */")
        lines.append("")
        lines.append("/* Entry-return policy: returning from the generated entry "
                      "function without a declared termination is a "
                      f"{self.entry_return_policy.upper()} fault. */")
        lines.append("")
        lines.append("/* Observable digest contract: " + self.observable_digest + " over " +
                     self.observable_layout + " */")
        lines.append("")
        lines.append("#endif")
        return "\n".join(lines) + "\n"


def build_contract() -> RuntimeAbiContract:
    runtime_symbols = (
        AbiSymbol(
            "or_rt_memory_read", "int",
            (AbiParam("address", "uint64_t"), AbiParam("width_bits", "uint32_t"),
             AbiParam("out_value", "uint64_t *")),
            RUNTIME_PROVIDES,
            "Read width_bits (8/16/32/64) at a guest address into *out_value; "
            "returns OR_RT_OK or a memory failure code; out_value must not be null."),
        AbiSymbol(
            "or_rt_memory_write", "int",
            (AbiParam("address", "uint64_t"), AbiParam("width_bits", "uint32_t"),
             AbiParam("value", "uint64_t")),
            RUNTIME_PROVIDES,
            "Write the low width_bits of value at a guest address; returns "
            "OR_RT_OK or a memory failure code."),
        AbiSymbol(
            "or_rt_host_call", "int",
            (AbiParam("service_id", "uint64_t"), AbiParam("argc", "uint32_t"),
             AbiParam("args", "const uint64_t *"), AbiParam("out_value", "uint64_t *")),
            RUNTIME_PROVIDES,
            "Synchronous typed service call; unknown services, wrong argument "
            "counts, version mismatches and handler failures return a stable "
            "failure code and never call undeclared host functionality."),
        AbiSymbol(
            "or_rt_failure_reason", "const char *",
            (AbiParam("code", "int"),),
            RUNTIME_PROVIDES,
            "Stable, host-path-free failure name for a failure code; empty "
            "string for OR_RT_OK; bounded for unknown codes."),
    )
    generated_symbols = (
        AbiSymbol("openrecomp_run", "void", (), GENERATED_PROVIDES,
                  "Execute the generated program from its entry state."),
        AbiSymbol("openrecomp_failed", "int", (), GENERATED_PROVIDES,
                  "1 once the run latched a failure, else 0."),
        AbiSymbol("openrecomp_error", "const char *", (), GENERATED_PROVIDES,
                  "Empty string while no failure is latched; otherwise the stable failure name."),
        AbiSymbol("openrecomp_steps", "uint64_t", (), GENERATED_PROVIDES,
                  "Number of executed guest steps."),
        AbiSymbol("openrecomp_pc", "uint32_t", (), GENERATED_PROVIDES,
                  "Current program counter (target-profile width)."),
        AbiSymbol("openrecomp_register_count", "size_t", (), GENERATED_PROVIDES,
                  "Size of the guest register file (architecture-neutral vector)."),
        AbiSymbol("openrecomp_register_value", "uint32_t",
                  (AbiParam("index", "size_t"),), GENERATED_PROVIDES,
                  "Value of guest register index; out-of-range index fails closed."),
        AbiSymbol("openrecomp_image", "const uint8_t *", (), GENERATED_PROVIDES,
                  "Start of the immutable loaded guest image."),
        AbiSymbol("openrecomp_image_size", "uint32_t", (), GENERATED_PROVIDES,
                  "Byte length of the loaded guest image."),
        AbiSymbol("openrecomp_region_count", "uint32_t", (), GENERATED_PROVIDES,
                  "Number of declared guest memory regions."),
        AbiSymbol("openrecomp_region", "void",
                  (AbiParam("index", "uint32_t"), AbiParam("start", "uint32_t *"),
                   AbiParam("end", "uint32_t *"), AbiParam("flags", "uint32_t *")),
                  GENERATED_PROVIDES,
                  "Region index bounds (end exclusive) and permission flags; "
                  "out-of-range index fails closed."),
    )
    core_services = (
        CoreService(
            "or.runtime.exit", rt.RUNTIME_ABI_VERSION, ("u32",), None, True,
            "Terminate the run with a 32-bit exit status; a second termination "
            "request fails closed."),
    )
    return RuntimeAbiContract(
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        symbols=runtime_symbols + generated_symbols,
        core_services=core_services,
        failure_codes=tuple(rt.RUNTIME_FAILURE_CODES),
        widths=tuple(sorted(rt.RUNTIME_WIDTHS)),
        endianness=tuple(sorted(rt.RUNTIME_ENDIANNESS)),
        entry_return_policy=ENTRY_RETURN_POLICY,
        observable_fields=OBSERVABLE_FIELDS,
        observable_digest=OBSERVABLE_DIGEST,
        observable_layout=OBSERVABLE_LAYOUT,
    )


def frozen_phase3_profile() -> InstanceProfile:
    program = ".openrecomp-phase3/evidence/P3-07/coremark_program.c"
    support = ".openrecomp-phase3/evidence/P3-07/coremark_support.c"
    return InstanceProfile(
        name="phase3-coremark-mips32-o32",
        abi_version=CONTRACT_VERSION,
        endianness="little",
        widths=(8, 16, 32),
        register_count=32,
        aux_registers=(("hi", "openrecomp_hi", "uint32_t"),
                       ("lo", "openrecomp_lo", "uint32_t")),
        services=(
            ServiceDescriptor(
                "p3.exit", 1, CONTRACT_VERSION, ("u32",), None, True,
                "Terminate the audited MIPS32 program with a 32-bit status."),
            ServiceDescriptor(
                "p3.uart_write", 2, CONTRACT_VERSION, ("u32",), None, False,
                "Append one byte to the bounded deterministic output stream."),
        ),
        entry_return_policy=ENTRY_RETURN_POLICY,
        artifacts=(
            (program, "5199e2f0a11974847966bd7ea6b855e0147c6e762d002ede3f14bc3ee8d9649a"),
            (support, "c5c69054cbbcd4e6ea9259f2e3d80e4bfada6fc12fec1cfe3fe9224b9f861580"),
        ),
    )


def contract_document_bytes() -> bytes:
    document = build_contract().to_document()
    return (canonical_json(document) + "\n").encode("utf-8")


def contract_header_bytes() -> bytes:
    return build_contract().to_c_header().encode("utf-8")


def profile_document_bytes() -> bytes:
    return (canonical_json(frozen_phase3_profile().to_document()) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Generated-source verification
# ---------------------------------------------------------------------------
_TYPE_CHARS = r"[A-Za-z_][A-Za-z0-9_ *]*?"
_EXTERN_RE = re.compile(
    rf"^extern\s+({_TYPE_CHARS})\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*;",
    re.MULTILINE)
_DEFINITION_RE = re.compile(
    rf"^((?:static\s+)?{_TYPE_CHARS})\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*\{{",
    re.MULTILINE)
_INCLUDE_RE = re.compile(r"^#include\s+<([^>]+)>", re.MULTILINE)
_SERVICE_MACRO_RE = re.compile(r"^#define\s+(OR_RT_SERVICE_[A-Z0-9_]+)\s+UINT64_C\((\d+)\)", re.MULTILINE)
_SERVICE_USE_RE = re.compile(r"or_host_service\(\s*(OR_RT_SERVICE_[A-Z0-9_]+)\s*,\s*(\d+)u")
_CORE_FAILURE_ENUM_RE = re.compile(r"OR_RT_([A-Z0-9_]+)\s*=\s*(\d+)")
_MACRO_REFERENCE_RE = re.compile(r"\b(OR_RT_SERVICE_[A-Z0-9_]+)\b")


@dataclass(frozen=True)
class ParsedFunction:
    returns: str
    name: str
    params: tuple[tuple[str, str], ...]
    static: bool


@dataclass(frozen=True)
class SourceFacts:
    includes: frozenset[str]
    externs: tuple[ParsedFunction, ...]
    definitions: tuple[ParsedFunction, ...]
    service_macros: tuple[tuple[str, int], ...]
    service_uses: tuple[tuple[str, int], ...]
    service_macro_refs: frozenset[str]
    failure_enum: tuple[tuple[str, int], ...]


def parse_source(text: str) -> SourceFacts:
    externs: list[ParsedFunction] = []
    for match in _EXTERN_RE.finditer(text):
        externs.append(_parsed_function(match))
    definitions: list[ParsedFunction] = []
    for match in _DEFINITION_RE.finditer(text):
        definitions.append(_parsed_function(match))
    includes = frozenset(match.group(1).strip() for match in _INCLUDE_RE.finditer(text))
    macros = tuple((match.group(1), int(match.group(2))) for match in _SERVICE_MACRO_RE.finditer(text))
    uses = tuple((match.group(1), int(match.group(2))) for match in _SERVICE_USE_RE.finditer(text))
    refs = frozenset(match.group(1) for match in _MACRO_REFERENCE_RE.finditer(text))
    failure_enum = tuple((match.group(1), int(match.group(2)))
                         for match in _CORE_FAILURE_ENUM_RE.finditer(text))
    return SourceFacts(
        includes=includes,
        externs=tuple(externs),
        definitions=tuple(definitions),
        service_macros=macros,
        service_uses=uses,
        service_macro_refs=refs,
        failure_enum=failure_enum,
    )


def _parsed_function(match: re.Match[str]) -> ParsedFunction:
    raw_return = match.group(1)
    static = raw_return.startswith("static ")
    returns = _normalize_type(raw_return[len("static "):] if static else raw_return)
    name = match.group(2)
    raw_params = match.group(3).strip()
    params: list[tuple[str, str]] = []
    if raw_params and raw_params != "void":
        for item in raw_params.split(","):
            params.append(_split_param(item))
    return ParsedFunction(returns=returns, name=name, params=tuple(params), static=static)


def _signature_matches(function: ParsedFunction, symbol: AbiSymbol) -> bool:
    return (function.returns == symbol.returns
            and function.params == tuple((param.c_type, param.name) for param in symbol.params))


class GeneratedSourceVerifier:
    """Checks generated sources against the contract and their instance profile."""

    def __init__(self, contract: RuntimeAbiContract, profile: InstanceProfile) -> None:
        problems = contract.verify_profile(profile)
        _require(not problems, f"profile invalid: {problems}")
        self.contract = contract
        self.profile = profile
        self.runtime_symbols = contract.runtime_symbols()
        self.generated_symbols = contract.generated_symbols()
        self.aux_symbols = {accessor: c_type for _, accessor, c_type in profile.aux_registers}
        self.services_by_macro = {service.macro: service for service in profile.services}

    def verify_program(self, text: str) -> list[str]:
        facts = parse_source(text)
        problems: list[str] = []
        extra_includes = facts.includes - GENERATED_INCLUDE_SET
        if extra_includes:
            problems.append(f"generated program includes non-ABI headers: {sorted(extra_includes)}")
        for function in facts.externs:
            symbol = self.runtime_symbols.get(function.name)
            if symbol is None:
                problems.append(f"generated program declares undeclared extern {function.name!r}")
            elif not _signature_matches(function, symbol):
                problems.append(
                    f"extern {function.name!r} signature mismatch: "
                    f"{function.returns} {function.params} != {symbol.signature()}")
        for function in facts.definitions:
            if function.static or not function.name.startswith("openrecomp_"):
                continue
            symbol = self.generated_symbols.get(function.name)
            if symbol is not None:
                if not _signature_matches(function, symbol):
                    problems.append(
                        f"accessor {function.name!r} signature mismatch: "
                        f"{function.returns} {function.params} != {symbol.signature()}")
                continue
            if function.name in self.aux_symbols:
                expected = self.aux_symbols[function.name]
                if function.returns != expected or function.params:
                    problems.append(f"aux accessor {function.name!r} must be {expected} {function.name}(void)")
                continue
            problems.append(f"generated program defines undeclared accessor {function.name!r}")
        defined = {function.name for function in facts.definitions if not function.static}
        for name in self.generated_symbols:
            if name not in defined:
                problems.append(f"generated program does not define required accessor {name!r}")
        for accessor in self.aux_symbols:
            if accessor not in defined:
                problems.append(f"generated program does not define declared aux accessor {accessor!r}")
        declared_macros = dict(facts.service_macros)
        expected_macros = {service.macro: service.numeric_id for service in self.profile.services}
        if declared_macros != expected_macros:
            problems.append(
                f"generated program service macros {sorted(declared_macros)} != profile {sorted(expected_macros)}")
        for macro, argc in facts.service_uses:
            service = self.services_by_macro.get(macro)
            if service is None:
                problems.append(f"generated program calls undeclared service macro {macro!r}")
            elif argc != len(service.arg_types):
                problems.append(f"generated program calls {macro} with {argc} args, profile declares {len(service.arg_types)}")
        unknown_refs = {ref for ref in facts.service_macro_refs if ref not in expected_macros}
        if unknown_refs:
            problems.append(f"generated program references undeclared service macros {sorted(unknown_refs)}")
        enum_map = dict(facts.failure_enum)
        enum_map.pop("OK", None)
        expected_enum = {code: index + 1 for index, code in enumerate(self.contract.failure_codes)}
        if enum_map != expected_enum:
            problems.append("generated program failure enum does not match the contract codes")
        problems.extend(self._platform_problems(text))
        return problems

    def verify_runtime_support(self, text: str) -> list[str]:
        facts = parse_source(text)
        problems: list[str] = []
        extra_includes = facts.includes - RUNTIME_INCLUDE_SET
        if extra_includes:
            problems.append(f"runtime support includes non-bounded headers: {sorted(extra_includes)}")
        defined = {function.name: function for function in facts.definitions if not function.static}
        for name, symbol in self.runtime_symbols.items():
            function = defined.get(name)
            if function is None:
                problems.append(f"runtime support does not define {name!r}")
            elif not _signature_matches(function, symbol):
                problems.append(f"runtime support {name!r} signature mismatch")
        for name in self.generated_symbols:
            if name in defined:
                problems.append(f"runtime support must not define generated accessor {name!r}")
        for name, function in defined.items():
            if name.startswith("or_rt_") and name not in self.runtime_symbols:
                problems.append(f"runtime support defines undeclared runtime entry {name!r}")
        if "main" not in defined:
            problems.append("runtime support must define the bounded harness entry main")
        declared_macros = dict(facts.service_macros)
        expected_macros = {service.macro: service.numeric_id for service in self.profile.services}
        if declared_macros != expected_macros:
            problems.append(
                f"runtime support service macros {sorted(declared_macros)} != profile {sorted(expected_macros)}")
        if "OR_RT_UNKNOWN_HOST_SERVICE" not in text:
            problems.append("runtime support must fail closed with OR_RT_UNKNOWN_HOST_SERVICE")
        problems.extend(self._platform_problems(text))
        return problems

    def _platform_problems(self, text: str) -> list[str]:
        lowered = text.lower()
        problems = []
        for token in PLATFORM_TOKENS:
            if token.lower() in lowered:
                problems.append(f"platform/foreign token {token!r} is not allowed at the ABI boundary")
        return problems

    def check_profile_artifacts(self, root: Any) -> list[str]:
        problems: list[str] = []
        for path, digest in self.profile.artifacts:
            candidate = root / path
            if not candidate.is_file():
                problems.append(f"profile artifact missing: {path}")
                continue
            actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if actual != digest:
                problems.append(f"profile artifact {path} sha256 {actual} != {digest}")
        return problems


# ---------------------------------------------------------------------------
# Contract runtime model (fail-closed reference implementation)
# ---------------------------------------------------------------------------
class ContractRuntimeModel:
    """A bounded Python implementation of the ABI used for contract tests.

    Failures latch: the first failure is preserved and every later operation
    fails closed with TRAP.  Termination is explicit.  There is no host
    pointer, no wall clock, no randomness and no environment access.
    """

    def __init__(
        self,
        contract: RuntimeAbiContract,
        profile: InstanceProfile,
        *,
        memory_size_bytes: int,
        segments: Iterable[rt.RuntimeMemorySegment] = (),
        handlers: Mapping[str, Callable[[tuple[int, ...]], int | None]] | None = None,
        output_capacity: int = 1 << 20,
    ) -> None:
        problems = contract.verify_profile(profile)
        _require(not problems, f"profile invalid: {problems}")
        _require(not isinstance(memory_size_bytes, bool) and memory_size_bytes > 0,
                 "memory_size_bytes must be positive")
        _require(not isinstance(output_capacity, bool) and output_capacity > 0,
                 "output_capacity must be positive")
        self.contract = contract
        self.profile = profile
        self._memory = rt.RuntimeMemory(memory_size_bytes, endianness=profile.endianness,
                                        segments=segments)
        supplied = dict(handlers or {})
        for service in profile.services:
            if service.terminates_run and service.service_id in supplied:
                raise P4AbiError(
                    f"terminating service {service.service_id!r} must not have a handler")
            if not service.terminates_run and service.service_id not in supplied:
                raise P4AbiError(f"service {service.service_id!r} has no handler")
        self._handlers = supplied
        self._output_capacity = output_capacity
        self.output = bytearray()
        self.exit_status: int | None = None
        self.terminated = False
        self.steps = 0
        self.pc = 0
        self.registers = [0] * profile.register_count
        self.aux = {name: 0 for name, _, _ in profile.aux_registers}
        self.failure: rt.RuntimeFailure | None = None
        self.calls: list[rt.RuntimeHostCallRecord] = []
        self._table = rt.RuntimeServiceTable(
            [rt.RuntimeService(service.service_id, len(service.arg_types))
             for service in profile.services],
            {service.service_id: self._wrapped(service) for service in profile.services},
        )

    @property
    def failed(self) -> bool:
        return self.failure is not None

    def _latch(self, failure: rt.RuntimeFailure) -> None:
        if self.failure is None:
            self.failure = failure

    def _active(self) -> bool:
        if self.terminated:
            self._latch(rt.RuntimeFailure(rt.RuntimeFailureCode.TRAP,
                                          "operation after run termination"))
            return False
        return self.failure is None

    def _wrapped(self, service: ServiceDescriptor) -> Callable[[tuple[int, ...]], int | None]:
        def handler(args: tuple[int, ...]) -> int | None:
            if service.terminates_run:
                self.exit_status = int(args[0]) & 0xFFFFFFFF
                self.terminated = True
                return None
            return self._handlers[service.service_id](args)
        return handler

    def read(self, address: int, width_bits: int) -> rt.RuntimeResult:
        if not self._active():
            return rt.RuntimeResult.failed(self.failure)
        if width_bits not in self.profile.widths:
            self._latch(rt.RuntimeFailure(
                rt.RuntimeFailureCode.MEMORY_WIDTH_UNSUPPORTED,
                f"width {width_bits} is not declared by the profile"))
            return rt.RuntimeResult.failed(self.failure)
        result = self._memory.try_read(address, width_bits)
        if not result.ok:
            self._latch(result.failure)
        return result

    def write(self, address: int, value: int, width_bits: int) -> rt.RuntimeResult:
        if not self._active():
            return rt.RuntimeResult.failed(self.failure)
        if width_bits not in self.profile.widths:
            self._latch(rt.RuntimeFailure(
                rt.RuntimeFailureCode.MEMORY_WIDTH_UNSUPPORTED,
                f"width {width_bits} is not declared by the profile"))
            return rt.RuntimeResult.failed(self.failure)
        result = self._memory.try_write(address, value, width_bits)
        if not result.ok:
            self._latch(result.failure)
        return result

    def call(self, service_id: str, args: Iterable[int] = (), *,
             version: str | None = None) -> rt.RuntimeResult:
        if not self._active():
            return rt.RuntimeResult.failed(self.failure)
        try:
            service = self.profile.service(service_id)
        except P4AbiError:
            self._latch(rt.RuntimeFailure(
                rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE,
                f"unknown runtime host service {service_id!r}"))
            return rt.RuntimeResult.failed(self.failure)
        requested = self.contract.version if version is None else version
        if requested != service.version:
            self._latch(rt.RuntimeFailure(
                rt.RuntimeFailureCode.ABI_VERSION_MISMATCH,
                f"service {service_id!r} version {requested!r} != {service.version!r}"))
            return rt.RuntimeResult.failed(self.failure)
        arguments = tuple(args)
        for index, (argument, arg_type) in enumerate(zip(arguments, service.arg_types)):
            limit = 0xFFFFFFFF if arg_type == "u32" else rt.RUNTIME_MAX_ADDRESS
            if isinstance(argument, bool) or not isinstance(argument, int) or not 0 <= argument <= limit:
                self._latch(rt.RuntimeFailure(
                    rt.RuntimeFailureCode.HOST_CALL_ARITY,
                    f"service {service_id!r} argument {index} violates the declared {arg_type} type"))
                return rt.RuntimeResult.failed(self.failure)
        request = rt.RuntimeHostCallRequest(service_id, arguments)
        result = self._table.dispatch(request)
        self.calls.append(rt.RuntimeHostCallRecord(
            sequence=len(self.calls), service=service_id, args=arguments, result=result))
        if not result.ok:
            self._latch(result.failure)
            return result
        if service.terminates_run and len(arguments) == 0:
            self._latch(rt.RuntimeFailure(
                rt.RuntimeFailureCode.HOST_CALL_ARITY,
                f"terminating service {service_id!r} requires a status argument"))
            return rt.RuntimeResult.failed(self.failure)
        if service.result_type == "u32" and result.value is not None and result.value > 0xFFFFFFFF:
            self._latch(rt.RuntimeFailure(
                rt.RuntimeFailureCode.HOST_SERVICE_FAILED,
                f"service {service_id!r} result exceeds the declared u32 result type"))
            return rt.RuntimeResult.failed(self.failure)
        return result

    def emit_output(self, data: bytes) -> rt.RuntimeResult:
        if not self._active():
            return rt.RuntimeResult.failed(self.failure)
        if len(self.output) + len(data) > self._output_capacity:
            self._latch(rt.RuntimeFailure(
                rt.RuntimeFailureCode.UNSUPPORTED_OPERATION,
                "runtime output capacity exceeded"))
            return rt.RuntimeResult.failed(self.failure)
        self.output.extend(data)
        return rt.RuntimeResult.success()

    def entry_returned(self) -> rt.RuntimeFailure:
        self._latch(rt.RuntimeFailure(
            rt.RuntimeFailureCode.TRAP,
            "generated entry returned without a declared termination"))
        return self.failure

    def run(self, body: Callable[["ContractRuntimeModel"], None]) -> None:
        if not self._active():
            raise P4AbiError("run() requires an active model")
        body(self)

    # -- deterministic observable state ------------------------------------
    def observable_document(self) -> dict[str, Any]:
        return {
            "abi": f"{self.contract.name} {self.contract.version}",
            "profile": self.profile.name,
            "image_sha256": self._memory.fingerprint(),
            "registers": list(self.registers),
            "aux_registers": {name: self.aux[name] for name, _, _ in self.profile.aux_registers},
            "pc": self.pc,
            "steps": self.steps,
            "exit_status": self.exit_status,
            "external_output_sha256": hashlib.sha256(bytes(self.output)).hexdigest(),
            "external_output_length": len(self.output),
            "failure": None if self.failure is None else self.failure.to_document(),
        }

    def observable_digest(self) -> str:
        hash_value = FNV1A64_OFFSET
        hash_value = _fnv1a64(hash_value, b"OROBS1")
        image = self._memory.snapshot()
        hash_value = _fnv1a64(hash_value, len(image).to_bytes(4, "little"))
        hash_value = _fnv1a64(hash_value, image)
        hash_value = _fnv1a64(hash_value, len(self.registers).to_bytes(4, "little"))
        for register in self.registers:
            hash_value = _fnv1a64(hash_value, (register & 0xFFFFFFFF).to_bytes(4, "little"))
        hash_value = _fnv1a64(hash_value, len(self.aux).to_bytes(4, "little"))
        for name, _, _ in self.profile.aux_registers:
            hash_value = _fnv1a64(hash_value, (self.aux[name] & 0xFFFFFFFF).to_bytes(4, "little"))
        hash_value = _fnv1a64(hash_value, (self.pc & 0xFFFFFFFF).to_bytes(4, "little"))
        hash_value = _fnv1a64(hash_value, (self.steps & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "little"))
        status = EXIT_STATUS_ABSENT if self.exit_status is None else self.exit_status
        hash_value = _fnv1a64(hash_value, status.to_bytes(4, "little"))
        hash_value = _fnv1a64(hash_value, len(self.output).to_bytes(4, "little"))
        hash_value = _fnv1a64(hash_value, bytes(self.output))
        return f"0x{hash_value:016x}"


def _fnv1a64(hash_value: int, data: bytes) -> int:
    for byte in data:
        hash_value ^= byte
        hash_value = (hash_value * FNV1A64_PRIME) & 0xFFFFFFFFFFFFFFFF
    return hash_value
