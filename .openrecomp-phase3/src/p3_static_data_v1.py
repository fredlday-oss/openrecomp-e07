#!/usr/bin/env python3
"""OpenRecomp Phase-3 static data / global reconstruction V1 (P3-06).

Builds the explicit, verifiable static-data model of the audited CoreMark
MIPS32 image on top of the P3-02 guest image and the P3-05 neutral structure:

* the allocated data sections (``.rodata``, ``.data``, ``.bss`` and the two
  read-only metadata sections) are modelled with exact bytes, zero-fill,
  hashes, permissions and symbol-annotated layout;
* every reachable instruction that forms a constant value is recorded with its
  exact provenance chain (``lui``/``addiu``/``ori``/shift/ALU folds, or a load
  from a read-only file-backed section) -- no value is guessed;
* every reachable memory access is classified by the address it provably
  reaches: resolved inside a static section, resolved in a mapped region but
  outside a classified section, resolved outside the loaded image
  (external/MMIO), or ``RUNTIME_BASE`` when the base register is not a static
  constant on the audited path. ``RUNTIME_BASE`` accesses are reported, never
  assumed to hit or miss any object;
* loads from read-only file-backed sections propagate their exact image value
  (sound: the mapping is read-only and the bytes are load-time constants);
  loads from writable sections do not;
* a store whose resolved address lands in a read-only static section fails
  closed;
* the O32 ``$gp`` model is explicit: reachable ``$gp`` base uses and ``$gp``
  writes are counted, and the model states whether the audited path requires
  GP-relative addressing at all.

The analysis is block-local exact-value propagation; it never claims a runtime
value for a register the block does not establish. It is OpenRecomp-original,
standard-library only, and contains no console assets, proprietary data or
copied tables.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from openrecomp.program_model import InstructionFlow

STATIC_DATA_VERSION = "1.0.0"
MASK32 = 0xFFFFFFFF

ROLE_CODE = "CODE"
ROLE_RODATA = "RODATA"
ROLE_DATA = "DATA"
ROLE_BSS = "BSS"
ROLE_METADATA = "METADATA"
STATIC_ROLES = (ROLE_RODATA, ROLE_DATA, ROLE_BSS, ROLE_METADATA)

SECTION_ROLES = {
    ".text": ROLE_CODE,
    ".rodata": ROLE_RODATA,
    ".data": ROLE_DATA,
    ".bss": ROLE_BSS,
    ".MIPS.abiflags": ROLE_METADATA,
    ".reginfo": ROLE_METADATA,
}

ACCESS_LOAD = "LOAD"
ACCESS_STORE = "STORE"

STATUS_RESOLVED_STATIC = "RESOLVED_STATIC"
STATUS_RESOLVED_REGION_UNCLASSIFIED = "RESOLVED_REGION_UNCLASSIFIED"
STATUS_RESOLVED_OUTSIDE_IMAGE = "RESOLVED_OUTSIDE_IMAGE"
STATUS_CROSS_SECTION = "CROSS_SECTION_ACCESS"
STATUS_RUNTIME_BASE = "RUNTIME_BASE"
STATUS_ORDER = (
    STATUS_RESOLVED_STATIC,
    STATUS_CROSS_SECTION,
    STATUS_RESOLVED_REGION_UNCLASSIFIED,
    STATUS_RESOLVED_OUTSIDE_IMAGE,
    STATUS_RUNTIME_BASE,
)

ORIGIN_IMMEDIATE = "IMMEDIATE_CHAIN"
ORIGIN_LOAD = "READ_ONLY_LOAD"

GP_NOT_REQUIRED = "NOT_REQUIRED_BY_REACHABLE_CODE"
GP_REQUIRED = "REQUIRED_AND_RESOLVED"
GP_UNRESOLVED = "REQUIRED_BUT_UNRESOLVED"

ARGUMENT_REGISTERS = (4, 5, 6, 7)
GP_REGISTER = 28

RD_WRITE_OPS = frozenset({
    "addu", "subu", "and", "or", "xor", "nor", "slt", "sltu", "sll", "srl",
    "sra", "sllv", "srlv", "srav", "mfhi", "mflo", "mul", "movz", "movn",
})
RT_WRITE_OPS = frozenset({
    "addiu", "addi", "andi", "ori", "xori", "slti", "sltiu", "lui", "lb",
    "lbu", "lh", "lhu", "lw", "lwl", "lwr",
})
NO_WRITE_OPS = frozenset({
    "nop", "sw", "swl", "swr", "sb", "sh", "beq", "bne", "blez", "bgtz",
    "bltz", "bgez", "j", "jal", "jr", "teq", "tge", "tgeu", "tlt", "tltu",
    "tne", "syscall", "break", "mult", "multu", "div", "divu", "jalr",
})
MEMORY_OPS = frozenset({
    "lb", "lbu", "lh", "lhu", "lw", "lwl", "lwr", "sb", "sh", "sw", "swl", "swr",
})
LOAD_OPS = frozenset({"lb", "lbu", "lh", "lhu", "lw", "lwl", "lwr"})
STORE_OPS = frozenset({"sb", "sh", "sw", "swl", "swr"})
PROPAGATING_LOADS = frozenset({"lb", "lbu", "lh", "lhu", "lw"})
ACCESS_WIDTH = {
    "lb": 1, "lbu": 1, "sb": 1,
    "lh": 2, "lhu": 2, "sh": 2,
    "lw": 4, "sw": 4, "lwl": 4, "lwr": 4, "swl": 4, "swr": 4,
}

BINARY_FOLD = {
    "addu": lambda a, b: (a + b) & MASK32,
    "subu": lambda a, b: (a - b) & MASK32,
    "and": lambda a, b: a & b,
    "or": lambda a, b: a | b,
    "xor": lambda a, b: a ^ b,
    "nor": lambda a, b: (~(a | b)) & MASK32,
    "slt": lambda a, b: 1 if _signed(a) < _signed(b) else 0,
    "sltu": lambda a, b: 1 if a < b else 0,
}
SHIFT_FOLD = {
    "sll": lambda a, s: (a << s) & MASK32,
    "srl": lambda a, s: (a >> s) & MASK32,
    "sra": lambda a, s: (_signed(a) >> s) & MASK32,
}
IMMEDIATE_FOLD_OPS = frozenset({"addiu", "addi", "ori", "andi", "xori"})
SHIFT_OPS = frozenset({"sll", "srl", "sra"})


class StaticDataError(ValueError):
    """Fail-closed static-data rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _signed(value: int) -> int:
    value &= MASK32
    return value - 0x100000000 if value & 0x80000000 else value


def _sign16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


@dataclass(frozen=True)
class MappedRegion:
    vaddr: int
    size: int
    permissions: str

    @property
    def memory_end(self) -> int:
        return self.vaddr + self.size


@dataclass(frozen=True)
class StaticSection:
    name: str
    role: str
    kind: str
    vaddr: int
    size: int
    permissions: str
    section_type: int
    sha256: str
    content: bytes

    @property
    def memory_end(self) -> int:
        return self.vaddr + self.size

    @property
    def read_only(self) -> bool:
        return self.role in (ROLE_RODATA, ROLE_METADATA)

    @property
    def writable(self) -> bool:
        return "w" in self.permissions

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "kind": self.kind,
            "vaddr": f"0x{self.vaddr:08x}",
            "size": self.size,
            "memory_end": f"0x{self.memory_end:08x}",
            "permissions": self.permissions,
            "section_type": self.section_type,
            "sha256": self.sha256,
            "read_only": self.read_only,
            "writable": self.writable,
        }


@dataclass(frozen=True)
class DataSymbol:
    name: str
    address: int
    size: int
    bind: int
    sym_type: int
    section: str | None
    offset: int | None

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": f"0x{self.address:08x}",
            "size": self.size,
            "bind": self.bind,
            "type": self.sym_type,
            "section": self.section,
            "offset": self.offset,
        }


@dataclass(frozen=True)
class StaticDataModel:
    sections: tuple[StaticSection, ...]
    symbols: tuple[DataSymbol, ...]
    regions: tuple[MappedRegion, ...] = ()

    def section_at(self, address: int, size: int = 1) -> StaticSection | None:
        if size < 0:
            raise StaticDataError("INVALID_SIZE", f"size={size}")
        for section in self.sections:
            if section.vaddr <= address < section.memory_end:
                return section
        return None

    def contained(self, address: int, size: int) -> bool:
        section = self.section_at(address, size)
        return section is not None and address + size <= section.memory_end

    def read(self, address: int, size: int) -> bytes:
        section = self.section_at(address, size)
        if section is None or address + size > section.memory_end:
            raise StaticDataError("UNMAPPED_STATIC_ADDRESS", f"0x{address:08x}+{size}")
        offset = address - section.vaddr
        return section.content[offset:offset + size]

    def read_u32(self, address: int) -> int:
        return int.from_bytes(self.read(address, 4), "little")

    def is_mapped(self, address: int, size: int) -> bool:
        if size < 0 or address < 0 or address + size > 0x100000000:
            return False
        position, remaining = address, size
        while remaining:
            region = next(
                (item for item in self.regions
                 if item.vaddr <= position < item.memory_end), None)
            if region is None:
                return False
            step = min(remaining, region.memory_end - position)
            position += step
            remaining -= step
        return True

    def symbol_at(self, address: int) -> DataSymbol | None:
        for symbol in self.symbols:
            if symbol.size and symbol.address <= address < symbol.address + symbol.size:
                return symbol
        for symbol in self.symbols:
            if not symbol.size and symbol.address == address:
                return symbol
        return None

    def data_sections(self) -> tuple[StaticSection, ...]:
        return tuple(section for section in self.sections if section.role in STATIC_ROLES)


def build_static_data_model(ingested) -> StaticDataModel:
    """Derive the static-data model from an ingested ELF (fail closed)."""
    sections: list[StaticSection] = []
    seen: set[str] = set()
    for placement in ingested.parsed.section_placements:
        if placement.name in seen:
            raise StaticDataError("DUPLICATE_SECTION", placement.name)
        seen.add(placement.name)
        role = SECTION_ROLES.get(placement.name)
        if role is None:
            raise StaticDataError("UNKNOWN_SECTION_ROLE", placement.name)
        if placement.size == 0:
            continue
        if placement.vaddr + placement.size > 0x100000000:
            raise StaticDataError("SECTION_OVERFLOW", placement.name)
        content = ingested.image.section_bytes(placement.name)
        if len(content) != placement.size:
            raise StaticDataError(
                "SECTION_CONTENT_SIZE",
                f"{placement.name} expected={placement.size} actual={len(content)}")
        sections.append(StaticSection(
            name=placement.name,
            role=role,
            kind=placement.kind,
            vaddr=placement.vaddr,
            size=placement.size,
            permissions=placement.permissions,
            section_type=placement.section_type,
            sha256=hashlib.sha256(content).hexdigest(),
            content=bytes(content),
        ))
    ordered = tuple(sorted(sections, key=lambda item: item.vaddr))
    for first, second in zip(ordered, ordered[1:]):
        if first.memory_end > second.vaddr:
            raise StaticDataError("OVERLAPPING_SECTIONS", f"{first.name}/{second.name}")

    provisional = StaticDataModel(ordered, ())
    symbols: list[DataSymbol] = []
    for symbol in ingested.parsed.symbols():
        if not symbol.name or not symbol.defined:
            continue
        section = provisional.section_at(symbol.value) if symbol.value else None
        if section is not None and section.role == ROLE_CODE:
            section = None
        if section is not None and symbol.size and symbol.value + symbol.size > section.memory_end:
            section = None
        symbols.append(DataSymbol(
            name=symbol.name,
            address=symbol.value,
            size=symbol.size,
            bind=symbol.bind,
            sym_type=symbol.sym_type,
            section=section.name if section is not None else None,
            offset=(symbol.value - section.vaddr) if section is not None else None,
        ))
    regions = tuple(
        MappedRegion(region.vaddr, region.memsz, region.permissions)
        for region in sorted(ingested.image.regions, key=lambda item: item.vaddr))
    return StaticDataModel(
        ordered,
        tuple(sorted(symbols, key=lambda item: (item.address, item.name))),
        regions,
    )


# ---------------------------------------------------------------------------
# Global analysis
# ---------------------------------------------------------------------------
@dataclass
class _Register:
    value: int | None = None
    provenance: tuple[str, ...] = ()


@dataclass
class _Formation:
    site: int
    register: int
    value: int
    origin: str
    provenance: tuple[str, ...]
    uses: list[dict[str, Any]] = field(default_factory=list)

    def freeze(self) -> "Materialization":
        return Materialization(
            site=self.site, register=self.register, value=self.value,
            origin=self.origin, provenance=self.provenance,
            uses=tuple(self.uses))


@dataclass(frozen=True)
class Materialization:
    site: int
    register: int
    value: int
    origin: str
    provenance: tuple[str, ...]
    uses: tuple[dict[str, Any], ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "site": f"0x{self.site:08x}",
            "register": self.register,
            "value": f"0x{self.value:08x}",
            "origin": self.origin,
            "provenance": list(self.provenance),
            "uses": list(self.uses),
        }


@dataclass(frozen=True)
class AccessSite:
    site: int
    op: str
    kind: str
    width: int
    base_register: int
    base_value: int | None
    offset: int
    address: int | None
    status: str
    section: str | None
    symbol: str | None
    base_provenance: tuple[str, ...]
    containing_function: str
    value_loaded: int | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "site": f"0x{self.site:08x}",
            "op": self.op,
            "kind": self.kind,
            "width": self.width,
            "base_register": self.base_register,
            "base_value": f"0x{self.base_value:08x}" if self.base_value is not None else None,
            "offset": self.offset,
            "address": f"0x{self.address:08x}" if self.address is not None else None,
            "status": self.status,
            "section": self.section,
            "symbol": self.symbol,
            "base_provenance": list(self.base_provenance),
            "containing_function": self.containing_function,
            "value_loaded": f"0x{self.value_loaded:08x}" if self.value_loaded is not None else None,
        }


@dataclass(frozen=True)
class GlobalAnalysis:
    materializations: tuple[Materialization, ...]
    accesses: tuple[AccessSite, ...]
    gp_base_accesses: tuple[AccessSite, ...]
    gp_writes: tuple[int, ...]
    gp_status: str
    pointer_arguments: tuple[dict[str, Any], ...]
    unclassified_ops: tuple[str, ...] = ()

    def access_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for access in self.accesses:
            counts[access.status] = counts.get(access.status, 0) + 1
        return dict(sorted(counts.items()))

    def access_kind_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for access in self.accesses:
            key = f"{access.status}:{access.kind}"
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    def resolved_static_sites(self) -> tuple[AccessSite, ...]:
        return tuple(access for access in self.accesses
                     if access.status == STATUS_RESOLVED_STATIC)


def written_registers(op: str, operands: dict[str, Any]) -> tuple[int, ...]:
    """Registers written by one audited instruction (fail closed on unknown ops)."""
    if op in RD_WRITE_OPS:
        return (operands["rd"],)
    if op in RT_WRITE_OPS:
        return (operands["rt"],)
    if op == "jalr":
        return (operands["rd"],)
    if op in NO_WRITE_OPS:
        return ()
    raise StaticDataError("UNCLASSIFIED_OP", op)


_written_registers = written_registers


def _block_owners(structure) -> dict[int, str]:
    owners: dict[int, str] = {}
    for unit in structure.units.units:
        for block in unit.blocks:
            for instruction in block.instructions:
                owners[instruction.address] = unit.function_id
    return owners


def _immediate_value(op: str, immediate: int, base: int) -> int:
    if op in ("addiu", "addi"):
        return (base + _sign16(immediate)) & MASK32
    if op == "ori":
        return base | (immediate & 0xFFFF)
    if op == "andi":
        return base & (immediate & 0xFFFF)
    if op == "xori":
        return base ^ (immediate & 0xFFFF)
    raise StaticDataError("UNCLASSIFIED_OP", op)


def analyze_globals(structure, model: StaticDataModel) -> GlobalAnalysis:
    """Block-local exact-constant analysis of every reachable memory access."""
    owners = _block_owners(structure)
    formations: dict[int, _Formation] = {}
    accesses: list[AccessSite] = []
    gp_base_accesses: list[AccessSite] = []
    gp_writes: list[int] = []
    pointer_arguments: list[dict[str, Any]] = []
    unclassified: set[str] = set()

    for block in structure.cfg.ordered_blocks():
        registers: dict[int, _Register] = {0: _Register(0, ("zero",))}
        live: dict[int, int] = {}
        function_id = owners.get(block.entry_address, "?")

        def attribute(register: int, site: int, kind: str) -> None:
            formation_site = live.get(register)
            if formation_site is None:
                return
            formations[formation_site].uses.append(
                {"site": f"0x{site:08x}", "kind": kind})

        def drop(register: int) -> None:
            registers.pop(register, None)
            live.pop(register, None)

        def form(site: int, register: int, value: int, origin: str,
                 provenance: tuple[str, ...]) -> None:
            registers[register] = _Register(value, provenance)
            live[register] = site
            formations.setdefault(site, _Formation(
                site=site, register=register, value=value, origin=origin,
                provenance=provenance))

        for instruction in block.instructions:
            op = instruction.op
            operands = dict(instruction.metadata["operands"])
            address = instruction.address
            try:
                written_registers = _written_registers(op, operands)
            except StaticDataError:
                unclassified.add(op)
                written_registers = tuple(
                    index for index in (operands.get("rd"), operands.get("rt"))
                    if index is not None)
            if GP_REGISTER in written_registers:
                gp_writes.append(address)

            if op == "lui":
                form(address, operands["rt"], (operands["imm"] << 16) & MASK32,
                     ORIGIN_IMMEDIATE, (f"lui@0x{address:08x}",))
                continue

            if op in IMMEDIATE_FOLD_OPS:
                source = registers.get(operands["rs"])
                if source is not None and source.value is not None:
                    provenance = source.provenance + (f"{op}@0x{address:08x}",)
                    form(address, operands["rt"],
                         _immediate_value(op, operands["imm"], source.value),
                         ORIGIN_IMMEDIATE, provenance)
                else:
                    drop(operands["rt"])
                continue

            if op in SHIFT_OPS:
                source = registers.get(operands["rt"])
                if source is not None and source.value is not None:
                    form(address, operands["rd"],
                         SHIFT_FOLD[op](source.value, operands["shamt"]),
                         ORIGIN_IMMEDIATE, source.provenance)
                else:
                    drop(operands["rd"])
                continue

            if op in BINARY_FOLD:
                left = registers.get(operands["rs"])
                right = registers.get(operands["rt"])
                if (left is not None and left.value is not None
                        and right is not None and right.value is not None):
                    form(address, operands["rd"],
                         BINARY_FOLD[op](left.value, right.value),
                         ORIGIN_IMMEDIATE, left.provenance)
                else:
                    drop(operands["rd"])
                continue

            if op in MEMORY_OPS:
                base = registers.get(operands["rs"])
                offset = _sign16(operands["imm"])
                kind = ACCESS_LOAD if op in LOAD_OPS else ACCESS_STORE
                width = ACCESS_WIDTH[op]
                attribute(operands["rs"], address, "base")
                if base is not None and base.value is not None:
                    target = (base.value + offset) & MASK32
                    section = model.section_at(target, width)
                    if section is not None and target + width <= section.memory_end:
                        status, section_name = STATUS_RESOLVED_STATIC, section.name
                        if kind == ACCESS_STORE and section.read_only:
                            raise StaticDataError(
                                "STORE_TO_READ_ONLY_STATIC",
                                f"0x{address:08x} -> 0x{target:08x} {section.name}")
                    elif section is not None:
                        status, section_name = STATUS_CROSS_SECTION, section.name
                    elif model.is_mapped(target, width):
                        status, section_name = STATUS_RESOLVED_REGION_UNCLASSIFIED, None
                    else:
                        status, section_name = STATUS_RESOLVED_OUTSIDE_IMAGE, None
                    symbol = model.symbol_at(target) if status == STATUS_RESOLVED_STATIC else None
                    value_loaded = None
                    if (kind == ACCESS_LOAD and op in PROPAGATING_LOADS
                            and status == STATUS_RESOLVED_STATIC
                            and model.section_at(target, width).read_only):
                        raw = model.read(target, width)
                        value = int.from_bytes(raw, "little")
                        if op in ("lb", "lh") and value & (1 << (width * 8 - 1)):
                            value -= 1 << (width * 8)
                        value_loaded = value & MASK32
                        form(address, operands["rt"], value_loaded, ORIGIN_LOAD,
                             (f"load@0x{address:08x}<-0x{target:08x}",))
                    else:
                        drop(operands["rt"])
                    access = AccessSite(
                        site=address, op=op, kind=kind, width=width,
                        base_register=operands["rs"], base_value=base.value,
                        offset=offset, address=target, status=status,
                        section=section_name,
                        symbol=symbol.name if symbol is not None else None,
                        base_provenance=base.provenance,
                        containing_function=function_id,
                        value_loaded=value_loaded,
                    )
                    accesses.append(access)
                    if operands["rs"] == GP_REGISTER:
                        gp_base_accesses.append(access)
                else:
                    drop(operands["rt"])
                    access = AccessSite(
                        site=address, op=op, kind=kind, width=width,
                        base_register=operands["rs"], base_value=None,
                        offset=offset, address=None, status=STATUS_RUNTIME_BASE,
                        section=None, symbol=None,
                        base_provenance=base.provenance if base is not None else (),
                        containing_function=function_id,
                    )
                    accesses.append(access)
                    if operands["rs"] == GP_REGISTER:
                        gp_base_accesses.append(access)
                continue

            if instruction.flow is InstructionFlow.CALL:
                for register in ARGUMENT_REGISTERS:
                    formation_site = live.get(register)
                    if formation_site is None:
                        continue
                    formation = formations[formation_site]
                    pointer_arguments.append({
                        "call_site": f"0x{address:08x}",
                        "callee": f"0x{instruction.direct_target:08x}"
                        if instruction.direct_target is not None else None,
                        "register": register,
                        "value": f"0x{formation.value:08x}",
                        "origin": formation.origin,
                        "provenance": list(formation.provenance),
                        "containing_function": function_id,
                    })
                    attribute(register, address, "argument")
                for register in (operands.get("rd"), operands.get("rt")):
                    if register is not None:
                        drop(register)
                continue

            for register in written_registers:
                drop(register)

    materializations = tuple(
        formations[site].freeze() for site in sorted(formations))

    if not gp_base_accesses:
        gp_status = GP_NOT_REQUIRED
    elif any(access.status == STATUS_RUNTIME_BASE for access in gp_base_accesses):
        gp_status = GP_UNRESOLVED
    else:
        gp_status = GP_REQUIRED
    return GlobalAnalysis(
        materializations=materializations,
        accesses=tuple(sorted(accesses, key=lambda item: item.site)),
        gp_base_accesses=tuple(gp_base_accesses),
        gp_writes=tuple(gp_writes),
        gp_status=gp_status,
        pointer_arguments=tuple(pointer_arguments),
        unclassified_ops=tuple(sorted(unclassified)),
    )


__all__ = [
    "ACCESS_LOAD",
    "ACCESS_STORE",
    "ARGUMENT_REGISTERS",
    "GP_NOT_REQUIRED",
    "GP_REGISTER",
    "GP_REQUIRED",
    "GP_UNRESOLVED",
    "GlobalAnalysis",
    "ORIGIN_IMMEDIATE",
    "ORIGIN_LOAD",
    "SECTION_ROLES",
    "STATIC_DATA_VERSION",
    "STATIC_ROLES",
    "STATUS_CROSS_SECTION",
    "STATUS_RESOLVED_OUTSIDE_IMAGE",
    "STATUS_RESOLVED_REGION_UNCLASSIFIED",
    "STATUS_RESOLVED_STATIC",
    "STATUS_RUNTIME_BASE",
    "StaticDataError",
    "StaticDataModel",
    "StaticSection",
    "analyze_globals",
    "build_static_data_model",
    "written_registers",
]
