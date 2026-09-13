"""OpenRecomp deterministic host emitter V1 (P2-07).

`OpenRecomp Phase 2` stage P2-07 deliverable. This is the first host-code
emitter for OpenRecomp: it consumes the frozen structural pipeline
(`TranslationUnitSet` from P2-05 plus the `IndirectControlFlowSet` from P2-06)
and produces deterministic, portable C for a deliberately bounded, explicitly
proven subset of guest semantics.

Core safety rule: **emit only what is proven**.

* Guest semantics are never inferred from mnemonic or address appearance. Every
  emitted instruction requires an explicit `HostInstructionSemantics` rule for
  its exact `(architecture, op)` pair, supplied to the emitter through the
  configured `HostSemantics` table. A missing rule fails closed.
* Only a bounded, explicit neutral operation vocabulary is emitted: masked
  integer `const`/`copy`, `binop` and `compare` operations with explicit
  guest-width wraparound, plus the direct control-flow edges already present in
  the CFG.
* Unsupported, ambiguous or unresolved guest behavior fails closed. Unresolved
  indirect sites are never guessed; `BOUNDED_CANDIDATES` are never promoted to
  resolved targets; external/runtime-mediated transfers never receive an
  invented internal target.
* No IR lowering, no guest execution, no generic runtime ABI (P2-08) and no
  platform/framework APIs are introduced here. Loads, stores, host calls and
  runtime services are outside the bounded V1 subset.

Generated identifiers derive deterministically from stable OpenRecomp
identities; ordering (translation units, functions, blocks, instructions,
declarations, helpers) is canonical; identical inputs produce byte-identical C.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Union

from openrecomp.call_graph import CallEdgeKind
from openrecomp.indirect_control_flow import (
    IndirectControlFlowClassification,
    IndirectControlFlowKind,
    IndirectControlFlowSet,
    IndirectControlFlowStatus,
    IndirectControlFlowUnit,
)
from openrecomp.program_model import (
    BasicBlock,
    DecodedInstruction,
    EdgeKind,
    InstructionFlow,
    ProgramModelError,
    ProgramSource,
    canonical_json,
)
from openrecomp.translation_units import TranslationUnit, TranslationUnitSet

HOST_EMITTER_VERSION = "1.0.0"

_BINOP_KINDS = frozenset({"add", "sub", "mul", "and", "or", "xor", "shl", "lshr", "ashr"})
_UNSIGNED_PREDICATES = frozenset({"eq", "ne", "ult", "ule", "ugt", "uge"})
_SIGNED_PREDICATES = frozenset({"slt", "sle", "sgt", "sge"})
_PREDICATES = _UNSIGNED_PREDICATES | _SIGNED_PREDICATES
_WORD_BITS = frozenset({8, 16, 32, 64})


class HostEmitterError(ValueError):
    """Raised when host emission input is unsupported, inconsistent or unsafe."""


class HostUnsupportedPolicy(str, Enum):
    """How a non-resolved indirect site is emitted.

    `BOUNDARY` emits an explicit fail-closed runtime boundary; `REJECT` refuses
    to emit the translation unit at all. Either way the site is never guessed.
    """

    BOUNDARY = "BOUNDARY"
    REJECT = "REJECT"


def _sanitize(value: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not out:
        out = "_"
    if out[0].isdigit():
        out = "_" + out
    return out


def _c_string(value: str) -> str:
    if any(ord(ch) > 0x7F for ch in value):
        raise HostEmitterError("portable C output requires ASCII identifiers")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _u64(value: int) -> str:
    if value < 0:
        raise HostEmitterError(f"negative C literal: {value}")
    return f"UINT64_C({value})"


def _mask(bits: int) -> int:
    return (1 << bits) - 1


# --- semantic operands -----------------------------------------------------
@dataclass(frozen=True)
class HostRegister:
    """References a guest register by an adapter field name (e.g. ``rd``)."""

    field: str

    def __post_init__(self) -> None:
        if not isinstance(self.field, str) or not self.field:
            raise HostEmitterError("HostRegister.field must be a non-empty string")


@dataclass(frozen=True)
class HostImmediate:
    """References an immediate by adapter field name, with optional shift."""

    field: str
    signed: bool = False
    shift: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.field, str) or not self.field:
            raise HostEmitterError("HostImmediate.field must be a non-empty string")
        if not isinstance(self.signed, bool):
            raise HostEmitterError("HostImmediate.signed must be a boolean")
        if isinstance(self.shift, bool) or not isinstance(self.shift, int) or self.shift < 0:
            raise HostEmitterError("HostImmediate.shift must be a non-negative integer")


@dataclass(frozen=True)
class HostConstant:
    """A literal constant."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise HostEmitterError("HostConstant.value must be an integer")


HostOperand = Union[HostRegister, HostImmediate, HostConstant]


# --- semantic operations ---------------------------------------------------
@dataclass(frozen=True)
class HostNop:
    pass


@dataclass(frozen=True)
class HostCopy:
    dest: HostRegister
    source: HostOperand


@dataclass(frozen=True)
class HostConst:
    dest: HostRegister
    value: HostOperand


@dataclass(frozen=True)
class HostBinop:
    dest: HostRegister
    lhs: HostOperand
    rhs: HostOperand
    kind: str

    def __post_init__(self) -> None:
        if self.kind not in _BINOP_KINDS:
            raise HostEmitterError(f"unsupported binop kind {self.kind!r}")


@dataclass(frozen=True)
class HostCompare:
    dest: HostRegister
    lhs: HostOperand
    rhs: HostOperand
    predicate: str

    def __post_init__(self) -> None:
        if self.predicate not in _PREDICATES:
            raise HostEmitterError(f"unsupported compare predicate {self.predicate!r}")


HostOperation = Union[HostNop, HostCopy, HostConst, HostBinop, HostCompare]
_NORMAL_OPERATIONS = (HostNop, HostCopy, HostConst, HostBinop, HostCompare)


@dataclass(frozen=True)
class HostComparison:
    """A branch condition: ``lhs <predicate> rhs`` (no destination)."""

    lhs: HostOperand
    rhs: HostOperand
    predicate: str

    def __post_init__(self) -> None:
        if self.predicate not in _PREDICATES:
            raise HostEmitterError(f"unsupported comparison predicate {self.predicate!r}")


@dataclass(frozen=True)
class HostInstructionSemantics:
    """An explicit, proven semantic rule for one ``(architecture, op)`` pair.

    The rule declares the neutral operations emitted for the instruction and,
    for control-flow instructions, the branch condition or the register holding
    an indirect target. It is supplied by a trusted adapter/fixture; the emitter
    never fabricates one from an opcode mnemonic.
    """

    architecture: str
    op: str
    flow: InstructionFlow
    operations: tuple[HostOperation, ...] = ()
    condition: HostComparison | None = None
    indirect_source: HostOperand | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.architecture, str) or not self.architecture:
            raise HostEmitterError("semantics.architecture must be a non-empty string")
        if not isinstance(self.op, str) or not self.op:
            raise HostEmitterError("semantics.op must be a non-empty string")
        if not isinstance(self.flow, InstructionFlow):
            raise HostEmitterError(f"semantics.flow must be an InstructionFlow, got {self.flow!r}")
        if not isinstance(self.operations, tuple):
            raise HostEmitterError("semantics.operations must be a tuple")
        for operation in self.operations:
            if not isinstance(operation, _NORMAL_OPERATIONS):
                raise HostEmitterError(f"unsupported semantic operation {operation!r}")
        if self.condition is not None and not isinstance(self.condition, HostComparison):
            raise HostEmitterError("semantics.condition must be a HostComparison or null")
        if self.indirect_source is not None and not isinstance(
            self.indirect_source, (HostRegister, HostImmediate, HostConstant)
        ):
            raise HostEmitterError("semantics.indirect_source must be a host operand or null")

        if self.flow is InstructionFlow.BRANCH:
            if self.condition is None:
                raise HostEmitterError(f"{self.architecture}/{self.op}: BRANCH requires a condition")
            if self.operations or self.indirect_source is not None:
                raise HostEmitterError(f"{self.architecture}/{self.op}: BRANCH must not carry operations or indirect source")
        elif self.flow in (InstructionFlow.INDIRECT_CALL, InstructionFlow.INDIRECT_JUMP):
            if self.indirect_source is None:
                raise HostEmitterError(f"{self.architecture}/{self.op}: indirect flow requires an indirect source")
            if self.operations or self.condition is not None:
                raise HostEmitterError(f"{self.architecture}/{self.op}: indirect flow must not carry operations or condition")
        elif self.flow in (InstructionFlow.JUMP, InstructionFlow.CALL, InstructionFlow.RETURN, InstructionFlow.TRAP):
            if self.operations or self.condition is not None or self.indirect_source is not None:
                raise HostEmitterError(f"{self.architecture}/{self.op}: {self.flow.value} must not carry semantics")
        elif self.flow is InstructionFlow.NORMAL:
            if self.condition is not None or self.indirect_source is not None:
                raise HostEmitterError(f"{self.architecture}/{self.op}: NORMAL must not carry a condition or indirect source")
        else:
            raise HostEmitterError(f"{self.architecture}/{self.op}: unsupported flow {self.flow!r}")


class HostSemantics:
    """A deterministic table of explicit semantic rules keyed by ``(architecture, op)``."""

    def __init__(self, rules: Iterable[HostInstructionSemantics]) -> None:
        self._rules: dict[tuple[str, str], HostInstructionSemantics] = {}
        for rule in rules:
            if not isinstance(rule, HostInstructionSemantics):
                raise HostEmitterError("semantics rules must be HostInstructionSemantics instances")
            key = (rule.architecture, rule.op)
            if key in self._rules:
                raise HostEmitterError(f"duplicate semantics rule for {rule.architecture}/{rule.op}")
            self._rules[key] = rule

    def rule(self, architecture: str, op: str) -> HostInstructionSemantics:
        try:
            return self._rules[(architecture, op)]
        except KeyError as exc:
            raise HostEmitterError(f"no proven semantic rule for {architecture}/{op}") from exc

    def has(self, architecture: str, op: str) -> bool:
        return (architecture, op) in self._rules

    def keys(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._rules))


@dataclass(frozen=True)
class HostEmitterConfig:
    """Bounded V1 emitter configuration.

    ``semantics`` is the explicit proven rule table; ``entry_function`` names the
    P2 function to expose as the generated entry point. ``word_bits`` defines the
    explicit guest word width. No runtime/memory/host-call contract is provided:
    those belong to P2-08.
    """

    semantics: HostSemantics
    entry_function: str
    word_bits: int = 32
    register_names: tuple[str, ...] = ()
    unsupported_indirect_policy: HostUnsupportedPolicy = HostUnsupportedPolicy.BOUNDARY

    def __post_init__(self) -> None:
        if not isinstance(self.semantics, HostSemantics):
            raise HostEmitterError("config.semantics must be a HostSemantics table")
        if not isinstance(self.entry_function, str) or not self.entry_function:
            raise HostEmitterError("config.entry_function must be a non-empty string")
        if self.word_bits not in _WORD_BITS:
            raise HostEmitterError(f"config.word_bits must be one of {sorted(_WORD_BITS)}")
        if not isinstance(self.register_names, tuple):
            raise HostEmitterError("config.register_names must be a tuple")
        for name in self.register_names:
            if not isinstance(name, str) or not name:
                raise HostEmitterError("config.register_names must contain non-empty strings")
        if len(set(self.register_names)) != len(self.register_names):
            raise HostEmitterError("config.register_names must be unique")
        if not isinstance(self.unsupported_indirect_policy, HostUnsupportedPolicy):
            raise HostEmitterError("config.unsupported_indirect_policy must be a HostUnsupportedPolicy")


@dataclass(frozen=True)
class HostTranslation:
    """The generated host representation of one translation unit."""

    unit_id: str
    function_id: str
    entry_address: int
    function_name: str
    declaration: str
    definition: str
    block_labels: tuple[str, ...]
    reference_functions: tuple[str, ...]
    operations_emitted: int
    indirect_statuses: tuple[str, ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "function_id": self.function_id,
            "entry_address": self.entry_address,
            "function_name": self.function_name,
            "declaration": self.declaration,
            "block_labels": list(self.block_labels),
            "reference_functions": list(self.reference_functions),
            "operations_emitted": self.operations_emitted,
            "indirect_statuses": list(self.indirect_statuses),
        }


@dataclass(frozen=True)
class HostTranslationSet:
    """A deterministic, validated set of generated host translations."""

    version: str
    architecture: str
    entry_function: str
    entry_function_name: str
    source: ProgramSource
    word_bits: int
    register_names: tuple[str, ...]
    translations: tuple[HostTranslation, ...]
    source_text: str

    def fingerprint(self) -> str:
        return hashlib.sha256(self.source_text.encode("utf-8")).hexdigest()

    def translation_for(self, function_id: str) -> HostTranslation:
        for translation in self.translations:
            if translation.function_id == function_id:
                return translation
        raise HostEmitterError(f"unknown host translation for function {function_id}")

    def to_document(self) -> dict[str, Any]:
        return {
            "host_emitter_version": self.version,
            "architecture": self.architecture,
            "entry_function": self.entry_function,
            "entry_function_name": self.entry_function_name,
            "source": self.source.to_document(),
            "word_bits": self.word_bits,
            "register_names": list(self.register_names),
            "translations": [translation.to_document() for translation in self.translations],
            "source_sha256": self.fingerprint(),
            "source_text": self.source_text,
        }

    def serialize(self) -> bytes:
        return (canonical_json(self.to_document()) + "\n").encode("utf-8")


class _UnitContext:
    __slots__ = ("unit", "labels", "index", "classifications", "references", "statuses", "entry_index")

    def __init__(
        self,
        unit: TranslationUnit,
        labels: Mapping[str, str],
        index: Mapping[str, int],
        classifications: Mapping[tuple[str, int, str], IndirectControlFlowClassification],
        entry_index: Mapping[int, str],
    ) -> None:
        self.unit = unit
        self.labels = labels
        self.index = index
        self.classifications = classifications
        self.entry_index = entry_index
        self.references: list[str] = []
        self.statuses: list[str] = []


class HostEmitter:
    """Deterministic emitter from the P2 structural pipeline to portable C."""

    def __init__(self, config: HostEmitterConfig) -> None:
        if not isinstance(config, HostEmitterConfig):
            raise HostEmitterError("HostEmitter requires a HostEmitterConfig")
        self.config = config
        self._architecture = ""

    # -- public --------------------------------------------------------------
    def emit(
        self,
        translation_units: TranslationUnitSet,
        classification: IndirectControlFlowSet,
    ) -> HostTranslationSet:
        if not isinstance(translation_units, TranslationUnitSet):
            raise HostEmitterError("translation_units must be a TranslationUnitSet")
        if not isinstance(classification, IndirectControlFlowSet):
            raise HostEmitterError("classification must be an IndirectControlFlowSet")
        if classification.source != translation_units.source:
            raise HostEmitterError("classification source disagrees with the translation units")
        self._validate_mapping(translation_units, classification)
        self._architecture = translation_units.source.architecture

        units = translation_units.units
        per_unit_registers = [self._collect_register_names(unit) for unit in units]
        global_names = self._register_file(units, per_unit_registers)
        index = {name: position for position, name in enumerate(global_names)}
        entry_index = {unit.entry_address: unit.function_id for unit in units}

        translations = tuple(
            self._emit_unit(unit, classification.unit_for(unit.function_id), index, entry_index) for unit in units
        )
        source_text = self._source_text(translation_units, classification, translations, global_names)
        return HostTranslationSet(
            version=HOST_EMITTER_VERSION,
            architecture=self._architecture,
            entry_function=self.config.entry_function,
            entry_function_name=f"fn_{_sanitize(self.config.entry_function)}",
            source=translation_units.source,
            word_bits=self.config.word_bits,
            register_names=global_names,
            translations=translations,
            source_text=source_text,
        )

    # -- validation / layout -------------------------------------------------
    def _validate_mapping(self, translation_units: TranslationUnitSet, classification: IndirectControlFlowSet) -> None:
        unit_functions = {unit.function_id for unit in translation_units.units}
        classified_functions = {unit.function_id for unit in classification.units}
        if unit_functions != classified_functions:
            raise HostEmitterError("classification units disagree with translation-unit functions")
        for unit in translation_units.units:
            classified = classification.unit_for(unit.function_id)
            if classified.unit_id != unit.unit_id or classified.entry_address != unit.entry_address:
                raise HostEmitterError(
                    f"classification unit {classified.unit_id} disagrees with translation unit {unit.unit_id}"
                )
        if self.config.entry_function not in unit_functions:
            raise HostEmitterError(f"entry function {self.config.entry_function} is not a translation unit")

    def _collect_register_names(self, unit: TranslationUnit) -> tuple[str, ...]:
        names: set[str] = set()
        for block in unit.blocks:
            for instruction in block.instructions:
                rule = self._rule_for(instruction)
                fields = self._adapter_fields(instruction)
                for operand in self._rule_operands(rule):
                    if isinstance(operand, HostRegister):
                        names.add(self._register_name(fields, operand.field))
        return tuple(sorted(names))

    def _register_file(
        self, units: tuple[TranslationUnit, ...], per_unit: list[tuple[str, ...]]
    ) -> tuple[str, ...]:
        if self.config.register_names:
            declared = set(self.config.register_names)
            for unit, names in zip(units, per_unit):
                missing = sorted(set(names) - declared)
                if missing:
                    raise HostEmitterError(f"unit {unit.unit_id}: registers {missing} are not declared")
            return self.config.register_names
        return tuple(sorted({name for names in per_unit for name in names}))

    def _emit_unit(
        self,
        unit: TranslationUnit,
        classified: IndirectControlFlowUnit,
        index: Mapping[str, int],
        entry_index: Mapping[int, str],
    ) -> HostTranslation:
        labels: dict[str, str] = {}
        for block in unit.blocks:
            label = f"bb_{_sanitize(block.id)}"
            if label in labels.values():
                raise HostEmitterError(f"unit {unit.unit_id}: duplicate host block label {label}")
            labels[block.id] = label
        classifications = {
            (item.block_id, item.address, item.kind.value): item for item in classified.classifications
        }
        if len(classifications) != len(classified.classifications):
            raise HostEmitterError(f"unit {unit.unit_id}: duplicate indirect classification")
        context = _UnitContext(unit, labels, index, classifications, entry_index)

        function_name = f"fn_{_sanitize(unit.function_id)}"
        operations = 0
        body: list[str] = [f"static void {function_name}(void) {{"]
        for block in unit.blocks:
            body.append(f"{labels[block.id]}:;")
            for position, instruction in enumerate(block.instructions):
                rule = self._rule_for(instruction)
                body.extend(self._emit_operations(instruction, rule, context))
                operations += len(rule.operations)
                if position == len(block.instructions) - 1:
                    body.extend(self._emit_transfer(block, rule, context))
        body.append("}")
        return HostTranslation(
            unit_id=unit.unit_id,
            function_id=unit.function_id,
            entry_address=unit.entry_address,
            function_name=function_name,
            declaration=f"static void {function_name}(void);",
            definition="\n".join(body) + "\n",
            block_labels=tuple(labels[block.id] for block in unit.blocks),
            reference_functions=tuple(sorted(set(context.references))),
            operations_emitted=operations,
            indirect_statuses=tuple(sorted(set(context.statuses))),
        )

    # -- semantics lookup ----------------------------------------------------
    def _rule_for(self, instruction: DecodedInstruction) -> HostInstructionSemantics:
        rule = self.config.semantics.rule(self._architecture, instruction.op)
        if rule.flow is not instruction.flow:
            raise HostEmitterError(
                f"{self._architecture}/{instruction.op}: rule flow {rule.flow.value} "
                f"disagrees with instruction flow {instruction.flow.value}"
            )
        return rule

    # -- operands ------------------------------------------------------------
    def _rule_operands(self, rule: HostInstructionSemantics) -> tuple[HostOperand, ...]:
        operands: list[HostOperand] = []
        for operation in rule.operations:
            if isinstance(operation, HostCopy):
                operands.extend((operation.dest, operation.source))
            elif isinstance(operation, HostConst):
                operands.extend((operation.dest, operation.value))
            elif isinstance(operation, (HostBinop, HostCompare)):
                operands.extend((operation.dest, operation.lhs, operation.rhs))
        if rule.condition is not None:
            operands.extend((rule.condition.lhs, rule.condition.rhs))
        if rule.indirect_source is not None:
            operands.append(rule.indirect_source)
        return tuple(operands)

    @staticmethod
    def _adapter_fields(instruction: DecodedInstruction) -> Mapping[str, Any]:
        metadata = instruction.metadata or {}
        fields = metadata.get("adapter_fields")
        if fields is None:
            return {}
        if not isinstance(fields, Mapping):
            raise HostEmitterError(f"0x{instruction.address:x}: metadata adapter_fields must be a mapping")
        return fields

    def _register_name(self, fields: Mapping[str, Any], field: str) -> str:
        if field not in fields:
            raise HostEmitterError(f"adapter field {field!r} is required by a semantic rule but absent")
        value = fields[field]
        if isinstance(value, bool) or not isinstance(value, (int, str)) or (isinstance(value, str) and not value):
            raise HostEmitterError(f"adapter field {field!r} is not a valid register reference")
        return f"r{value}" if isinstance(value, int) else value

    def _operand_expr(self, operand: HostOperand, instruction: DecodedInstruction, context: _UnitContext) -> str:
        fields = self._adapter_fields(instruction)
        if isinstance(operand, HostRegister):
            name = self._register_name(fields, operand.field)
            if name not in context.index:
                raise HostEmitterError(f"register {name!r} has no allocation")
            return f"g_r[{context.index[name]}]"
        if isinstance(operand, HostImmediate):
            if operand.field not in fields:
                raise HostEmitterError(f"0x{instruction.address:x}: adapter field {operand.field!r} is required but absent")
            value = fields[operand.field]
            if isinstance(value, bool) or not isinstance(value, int):
                raise HostEmitterError(f"0x{instruction.address:x}: adapter field {operand.field!r} is not an integer")
            if operand.shift:
                value <<= operand.shift
            return _u64(value & _mask(self.config.word_bits))
        if isinstance(operand, HostConstant):
            return _u64(operand.value & _mask(self.config.word_bits))
        raise HostEmitterError(f"unsupported host operand {operand!r}")

    # -- operation emission --------------------------------------------------
    def _emit_operations(
        self, instruction: DecodedInstruction, rule: HostInstructionSemantics, context: _UnitContext
    ) -> list[str]:
        lines: list[str] = []
        for operation in rule.operations:
            lines.extend(self._emit_operation(operation, instruction, context))
        return lines

    def _emit_operation(
        self, operation: HostOperation, instruction: DecodedInstruction, context: _UnitContext
    ) -> list[str]:
        bits = self.config.word_bits
        if isinstance(operation, HostNop):
            return []
        if isinstance(operation, HostCopy):
            dest = self._operand_expr(operation.dest, instruction, context)
            src = self._operand_expr(operation.source, instruction, context)
            return [f"    {dest} = ({src}) & or_mask({bits}u);"]
        if isinstance(operation, HostConst):
            dest = self._operand_expr(operation.dest, instruction, context)
            value = self._operand_expr(operation.value, instruction, context)
            return [f"    {dest} = ({value}) & or_mask({bits}u);"]
        if isinstance(operation, HostBinop):
            dest = self._operand_expr(operation.dest, instruction, context)
            lhs = self._operand_expr(operation.lhs, instruction, context)
            rhs = self._operand_expr(operation.rhs, instruction, context)
            return self._emit_binop(dest, lhs, rhs, operation.kind, bits)
        if isinstance(operation, HostCompare):
            dest = self._operand_expr(operation.dest, instruction, context)
            lhs = self._operand_expr(operation.lhs, instruction, context)
            rhs = self._operand_expr(operation.rhs, instruction, context)
            condition = self._comparison_expr(lhs, rhs, operation.predicate, bits)
            return [f"    {dest} = ({condition}) ? UINT64_C(1) : UINT64_C(0);"]
        raise HostEmitterError(f"unsupported operation {operation!r}")

    def _emit_binop(self, dest: str, lhs: str, rhs: str, kind: str, bits: int) -> list[str]:
        simple = {"add": "+", "sub": "-", "mul": "*", "and": "&", "or": "|", "xor": "^"}
        if kind in simple:
            return [f"    {dest} = (({lhs}) {simple[kind]} ({rhs})) & or_mask({bits}u);"]
        if kind in {"shl", "lshr", "ashr"}:
            lines = [f'    if (({rhs}) >= {bits}u) {{ or_fail("shift count is not normalized"); return; }}']
            if kind == "shl":
                lines.append(f"    {dest} = (({lhs}) << ({rhs})) & or_mask({bits}u);")
            elif kind == "lshr":
                lines.append(f"    {dest} = (({lhs}) >> ({rhs})) & or_mask({bits}u);")
            else:
                lines.append(f"    {dest} = or_ashr(({lhs}), ({rhs}), {bits}u);")
            return lines
        raise HostEmitterError(f"unsupported binop kind {kind!r}")

    def _comparison_expr(self, lhs: str, rhs: str, predicate: str, bits: int) -> str:
        operators = {
            "eq": "==", "ne": "!=", "ult": "<", "ule": "<=", "ugt": ">", "uge": ">=",
            "slt": "<", "sle": "<=", "sgt": ">", "sge": ">=",
        }
        if predicate in _SIGNED_PREDICATES:
            return f"(or_signed(({lhs}), {bits}u) {operators[predicate]} or_signed(({rhs}), {bits}u))"
        return f"(({lhs}) {operators[predicate]} ({rhs}))"

    # -- control transfer ----------------------------------------------------
    def _emit_transfer(
        self,
        block: BasicBlock,
        rule: HostInstructionSemantics,
        context: _UnitContext,
    ) -> list[str]:
        flow = block.terminal_flow()
        if flow is InstructionFlow.NORMAL:
            successors = self._successors(block, EdgeKind.FALLTHROUGH)
            if not successors:
                return ["    return;"]
            return [f"    goto {self._target_label(context, successors[0])};"]
        if flow is InstructionFlow.BRANCH:
            taken = self._successors(block, EdgeKind.BRANCH_TAKEN)
            not_taken = self._successors(block, EdgeKind.BRANCH_NOT_TAKEN)
            if not taken or not not_taken or rule.condition is None:
                raise HostEmitterError(f"unit {context.unit.unit_id} block {block.id}: malformed branch")
            condition = self._comparison_expr(
                self._operand_expr(rule.condition.lhs, block.terminal, context),
                self._operand_expr(rule.condition.rhs, block.terminal, context),
                rule.condition.predicate,
                self.config.word_bits,
            )
            return [
                f"    if ({condition}) goto {self._target_label(context, taken[0])}; "
                f"else goto {self._target_label(context, not_taken[0])};"
            ]
        if flow is InstructionFlow.JUMP:
            successors = self._successors(block, EdgeKind.JUMP)
            if not successors:
                raise HostEmitterError(f"unit {context.unit.unit_id} block {block.id}: unresolved direct jump")
            return [f"    goto {self._target_label(context, successors[0])};"]
        if flow is InstructionFlow.CALL:
            return self._emit_direct_call(block, context)
        if flow is InstructionFlow.RETURN:
            return ["    return;"]
        if flow is InstructionFlow.TRAP:
            return ['    or_fail("guest trap is unsupported");', "    return;"]
        if flow in (InstructionFlow.INDIRECT_CALL, InstructionFlow.INDIRECT_JUMP):
            return self._emit_indirect(block, rule, context)
        raise HostEmitterError(f"unit {context.unit.unit_id} block {block.id}: unsupported terminal flow {flow.value}")

    def _successors(self, block: BasicBlock, kind: EdgeKind) -> list[str]:
        targets: list[str] = []
        for successor in block.successors:
            if successor.kind is not kind:
                continue
            if not successor.resolved or successor.target_block is None:
                raise HostEmitterError(f"block {block.id}: unresolved {kind.value} edge is unsupported")
            targets.append(successor.target_block)
        return targets

    def _target_label(self, context: _UnitContext, block_id: str) -> str:
        if block_id not in context.labels:
            raise HostEmitterError(
                f"unit {context.unit.unit_id}: control transfer leaves the translation unit to block {block_id}"
            )
        return context.labels[block_id]

    def _continuation(self, block: BasicBlock, context: _UnitContext) -> str:
        successors = self._successors(block, EdgeKind.CALL_RETURN)
        if not successors:
            raise HostEmitterError(f"unit {context.unit.unit_id} block {block.id}: call has no continuation")
        return self._target_label(context, successors[0])

    def _emit_direct_call(self, block: BasicBlock, context: _UnitContext) -> list[str]:
        instruction = block.terminal
        internal = [
            edge
            for edge in context.unit.call_edges
            if edge.kind is CallEdgeKind.INTERNAL_DIRECT
            and edge.call_site_block == block.id
            and edge.call_site_address == instruction.address
        ]
        if not internal:
            external = [
                edge
                for edge in context.unit.call_edges
                if edge.kind is CallEdgeKind.EXTERNAL_DIRECT
                and edge.call_site_block == block.id
                and edge.call_site_address == instruction.address
            ]
            if external:
                raise HostEmitterError(
                    f"unit {context.unit.unit_id}: external direct call at 0x{instruction.address:x} "
                    f"requires the generic runtime ABI (P2-08)"
                )
            raise HostEmitterError(
                f"unit {context.unit.unit_id}: direct call at 0x{instruction.address:x} has no resolved callee"
            )
        callee = internal[0].callee
        if callee is None:
            raise HostEmitterError(f"unit {context.unit.unit_id}: internal call edge at 0x{instruction.address:x} lost its callee")
        callee_name = f"fn_{_sanitize(callee)}"
        if callee_name not in context.references:
            context.references.append(callee_name)
        return [f"    {callee_name}();", f"    goto {self._continuation(block, context)};"]

    def _emit_indirect(self, block: BasicBlock, rule: HostInstructionSemantics, context: _UnitContext) -> list[str]:
        instruction = block.terminal
        kind = (
            IndirectControlFlowKind.INDIRECT_CALL
            if instruction.flow is InstructionFlow.INDIRECT_CALL
            else IndirectControlFlowKind.INDIRECT_JUMP
        )
        classification = context.classifications.get((block.id, instruction.address, kind.value))
        if classification is None:
            raise HostEmitterError(
                f"unit {context.unit.unit_id}: indirect site 0x{instruction.address:x} has no P2-06 classification"
            )
        status = classification.status
        if status.value not in context.statuses:
            context.statuses.append(status.value)

        if kind is IndirectControlFlowKind.INDIRECT_JUMP:
            if status is IndirectControlFlowStatus.RETURN_LIKE:
                return ["    return;"]
            if status is IndirectControlFlowStatus.RESOLVED:
                return self._emit_resolved_jump(block, rule, classification, context)
        else:
            if status is IndirectControlFlowStatus.RESOLVED:
                return self._emit_resolved_call(block, rule, classification, context)

        if status is IndirectControlFlowStatus.UNSUPPORTED_OR_MALFORMED:
            raise HostEmitterError(f"unit {context.unit.unit_id}: indirect site 0x{instruction.address:x} is {status.value}")
        if self.config.unsupported_indirect_policy is HostUnsupportedPolicy.REJECT:
            raise HostEmitterError(
                f"unit {context.unit.unit_id}: indirect site 0x{instruction.address:x} classified {status.value} is not emittable"
            )
        message = {
            IndirectControlFlowStatus.BOUNDED_CANDIDATES: "bounded candidate set is not a resolved target",
            IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED: "external or runtime-mediated indirect transfer is unsupported",
            IndirectControlFlowStatus.UNRESOLVED_INDIRECT_CALL: "unresolved indirect call",
            IndirectControlFlowStatus.UNRESOLVED_INDIRECT_JUMP: "unresolved indirect jump",
        }.get(status, f"unsupported indirect classification {status.value}")
        return [f"    or_fail({_c_string(message)});", "    return;"]

    def _emit_resolved_jump(
        self,
        block: BasicBlock,
        rule: HostInstructionSemantics,
        classification: IndirectControlFlowClassification,
        context: _UnitContext,
    ) -> list[str]:
        targets = classification.targets
        if not targets:
            raise HostEmitterError(f"unit {context.unit.unit_id}: RESOLVED indirect jump has no targets")
        if len(targets) == 1:
            return [f"    goto {self._resolved_label(context, targets[0])};"]
        lines = [f"    switch ((uint64_t)({self._indirect_source(rule, block, context)})) {{"]
        for target in targets:
            lines.append(f"      case {_u64(target)}: goto {self._resolved_label(context, target)};")
        lines.append('      default: or_fail("indirect target outside proven set"); return;')
        lines.append("    }")
        return lines

    def _emit_resolved_call(
        self,
        block: BasicBlock,
        rule: HostInstructionSemantics,
        classification: IndirectControlFlowClassification,
        context: _UnitContext,
    ) -> list[str]:
        targets = classification.targets
        if not targets:
            raise HostEmitterError(f"unit {context.unit.unit_id}: RESOLVED indirect call has no targets")
        continuation = self._continuation(block, context)
        if len(targets) == 1:
            callee = self._resolved_callee(context, targets[0])
            if callee not in context.references:
                context.references.append(callee)
            return [f"    {callee}();", f"    goto {continuation};"]
        lines = [f"    switch ((uint64_t)({self._indirect_source(rule, block, context)})) {{"]
        for target in targets:
            callee = self._resolved_callee(context, target)
            if callee not in context.references:
                context.references.append(callee)
            lines.append(f"      case {_u64(target)}: {callee}(); goto {continuation};")
        lines.append('      default: or_fail("indirect target outside proven set"); return;')
        lines.append("    }")
        return lines

    def _indirect_source(self, rule: HostInstructionSemantics, block: BasicBlock, context: _UnitContext) -> str:
        if rule.indirect_source is None:
            raise HostEmitterError(f"unit {context.unit.unit_id} block {block.id}: indirect transfer has no source register")
        return self._operand_expr(rule.indirect_source, block.terminal, context)

    def _resolved_label(self, context: _UnitContext, target: int) -> str:
        for block in context.unit.blocks:
            if block.entry_address == target:
                return context.labels[block.id]
        raise HostEmitterError(
            f"unit {context.unit.unit_id}: resolved indirect target 0x{target:x} is not a block in the unit"
        )

    def _resolved_callee(self, context: _UnitContext, target: int) -> str:
        function_id = context.entry_index.get(target)
        if function_id is None:
            raise HostEmitterError(
                f"unit {context.unit.unit_id}: resolved indirect target 0x{target:x} is not a known internal function"
            )
        return f"fn_{_sanitize(function_id)}"

    # -- assembly ------------------------------------------------------------
    def _source_text(
        self,
        translation_units: TranslationUnitSet,
        classification: IndirectControlFlowSet,
        translations: tuple[HostTranslation, ...],
        register_names: tuple[str, ...],
    ) -> str:
        digest = hashlib.sha256()
        digest.update(translation_units.serialize())
        digest.update(classification.serialize())
        input_fingerprint = digest.hexdigest()
        count = max(1, len(register_names))

        lines: list[str] = [
            "/* OpenRecomp deterministic host emitter V1 (P2-07). */",
            f"/* architecture: {self._architecture}; word_bits: {self.config.word_bits}; entry: {self.config.entry_function} */",
            f"/* emitter_version: {HOST_EMITTER_VERSION} */",
            f"/* input_sha256: {input_fingerprint} */",
            "#include <stdint.h>",
            "#include <stddef.h>",
            "",
            f"static uint64_t g_r[{count}];",
            "static int g_failed;",
            'static const char *g_error = "";',
            "",
            "static uint64_t or_mask(unsigned bits) {",
            "    return bits >= 64u ? UINT64_MAX : ((UINT64_C(1) << bits) - UINT64_C(1));",
            "}",
            "static int64_t or_signed(uint64_t value, unsigned bits) {",
            "    uint64_t mask = or_mask(bits);",
            "    value &= mask;",
            "    if (bits >= 64u) return (int64_t)value;",
            "    uint64_t sign = UINT64_C(1) << (bits - 1u);",
            "    if (value & sign) value |= ~mask;",
            "    return (int64_t)value;",
            "}",
            "static uint64_t or_ashr(uint64_t value, uint64_t shift, unsigned bits) {",
            "    uint64_t mask = or_mask(bits);",
            "    value &= mask;",
            "    uint64_t shifted = value >> shift;",
            "    uint64_t sign = bits >= 64u ? (value >> 63u) : (value >> (bits - 1u));",
            "    if (sign) shifted |= (mask ^ (mask >> shift));",
            "    return shifted & mask;",
            "}",
            "static void or_fail(const char *message) {",
            "    if (!g_failed) g_error = message;",
            "    g_failed = 1;",
            "}",
            "",
        ]
        for translation in translations:
            lines.append(translation.declaration)
        lines.append("")
        for translation in translations:
            lines.append(translation.definition.rstrip("\n"))
            lines.append("")
        lines.extend(
            [
                "void openrecomp_run(void) {",
                f"    for (size_t i = 0; i < {count}u; ++i) g_r[i] = UINT64_C(0);",
                "    g_failed = 0;",
                '    g_error = "";',
                f"    {f'fn_{_sanitize(self.config.entry_function)}'}();",
                "}",
                "int openrecomp_failed(void) { return g_failed; }",
                "const char *openrecomp_error(void) { return g_error; }",
                f"size_t openrecomp_register_count(void) {{ return {count}u; }}",
                "uint64_t openrecomp_register_value(size_t index) {",
                f"    return index < {count}u ? g_r[index] : UINT64_C(0);",
                "}",
            ]
        )
        return "\n".join(lines) + "\n"


def emit_host_translation(
    translation_units: TranslationUnitSet,
    classification: IndirectControlFlowSet,
    *,
    config: HostEmitterConfig,
) -> HostTranslationSet:
    """Emit deterministic portable C for the supplied structural pipeline."""
    return HostEmitter(config).emit(translation_units, classification)


def emit_host_translation_from(
    units: Iterable[TranslationUnit],
    classification: IndirectControlFlowSet,
    *,
    source: ProgramSource,
    config: HostEmitterConfig,
) -> HostTranslationSet:
    """Lower-level entry point over explicit translation units."""
    if not isinstance(classification, IndirectControlFlowSet):
        raise HostEmitterError("classification must be an IndirectControlFlowSet")
    if not isinstance(source, ProgramSource):
        raise HostEmitterError("source must be a ProgramSource")
    unit_items = tuple(units)
    if not unit_items:
        raise HostEmitterError("at least one translation unit is required")
    entry_unit = next((unit.unit_id for unit in unit_items if unit.function_id == config.entry_function), None)
    try:
        translation_units = TranslationUnitSet(source, unit_items, entry_unit=entry_unit)
    except (ProgramModelError, ValueError) as exc:
        raise HostEmitterError(str(exc)) from exc
    return HostEmitter(config).emit(translation_units, classification)
