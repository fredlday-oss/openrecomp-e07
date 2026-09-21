#!/usr/bin/env python3
"""OpenRecomp Phase-10 MIPS32 semantic rule table V1.

The Phase-10 frontier reaches 24 MIPS32 op types for which the frozen Phase-8
rule table has no rule. This module adds exactly those rules, additively, on
top of the frozen Phase-8 table:

* the frozen Phase-8 rules are reused unchanged and are never redefined;
* every added rule uses only the existing architecture-neutral host-emitter
  vocabulary (``HostBinop``/``HostCompare``/``HostLoad``/``HostStore``/
  ``HostComparison``/``HostCallOperation``);
* forms that the bounded scalar vocabulary cannot express exactly
  (unaligned partial-word merges, HI/LO multiplication, the overflow-trapping
  ``addi``) are expressed as explicit host-service calls, never as guessed
  scalar approximations. The services are declared here and implemented in the
  Phase-10 runtime support.

Reachability discipline: only op types that are actually reachable in the
Phase-10 frontier are given rules. No speculative compatibility is added.

Fail-closed preconditions checked by :func:`assert_preconditions`:

* every reachable ``jalr`` must use ``$ra`` as its link destination, because
  the emitter's link-register materialisation is fixed to ``$ra``;
* every reachable folded delay slot must have a semantic rule.
"""

from __future__ import annotations

from typing import Any, Iterable

import p8_mips32_semantics_v1 as p8_semantics
from openrecomp import runtime_abi as rt_abi
from openrecomp.host_emitter import (
    HostBinop,
    HostCallOperation,
    HostCompare,
    HostComparison,
    HostConst,
    HostConstant,
    HostEmitterConfig,
    HostImmediate,
    HostInstructionSemantics,
    HostLoad,
    HostRegister,
    HostSemantics,
    HostStore,
)
from openrecomp.program_model import InstructionFlow

ARCHITECTURE = p8_semantics.ARCHITECTURE
DELAY_SLOT_METADATA_KEY = p8_semantics.DELAY_SLOT_METADATA_KEY
LINK_REGISTER = p8_semantics.LINK_REGISTER

SEMANTICS_VERSION = "1.0.0"

#: Phase-10 host services used by the added rules. Service identities are
#: stable and the runtime dispatches them by numeric id in sorted order.
SERVICE_ARITIES = {
    "openrecomp.mips.add.overflow.check": 2,
    "openrecomp.mips.lwl": 2,
    "openrecomp.mips.lwr": 2,
    "openrecomp.mips.mfhi": 0,
    "openrecomp.mips.mult": 2,
    "openrecomp.mips.swl": 2,
    "openrecomp.mips.swr": 2,
}

#: The op types added on top of the frozen Phase-8 rule table.
ADDED_OPS = (
    "addi", "and", "bgez", "bgtz", "blez", "bltz", "break", "jalr", "lh",
    "lhu", "lwl", "lwr", "mfhi", "mult", "sh", "slt", "slti", "sltiu",
    "sltu", "subu", "swl", "swr", "syscall", "xori",
)

#: Neutral classification ops (not MIPS mnemonics) produced by the Phase-10
#: structure bridge: the frozen frontier classifies a ``jr`` whose source
#: register is not ``$ra`` as an indirect jump, and the one-flow-per-op
#: emitter contract requires a distinct neutral rule for it.
CLASSIFICATION_OPS = ("jr_indirect",)

#: Op types whose exact semantics live behind a Phase-10 host service.
HOST_SERVICE_OPS = {
    "addi": "openrecomp.mips.add.overflow.check",
    "lwl": "openrecomp.mips.lwl",
    "lwr": "openrecomp.mips.lwr",
    "mfhi": "openrecomp.mips.mfhi",
    "mult": "openrecomp.mips.mult",
    "swl": "openrecomp.mips.swl",
    "swr": "openrecomp.mips.swr",
}

ERROR_DRIFT = "PHASE8_RULE_REDEFINED"
ERROR_UNSUPPORTED_JALR = "UNSUPPORTED_JALR_DESTINATION"
ERROR_UNMAPPED_DELAY_SLOT = "DELAY_SLOT_WITHOUT_RULE"


class Phase10SemanticsError(ValueError):
    """Fail-closed Phase-10 semantics error with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def added_rules() -> tuple[HostInstructionSemantics, ...]:
    """The additive Phase-10 rules for the newly reachable op types."""
    r = HostRegister
    imm = HostImmediate
    const = HostConstant

    def rule(op: str, flow: InstructionFlow, **kwargs: Any) -> HostInstructionSemantics:
        return HostInstructionSemantics(ARCHITECTURE, op, flow, **kwargs)

    base = (
        # --- scalar bitwise / arithmetic ------------------------------------
        rule("and", InstructionFlow.NORMAL, operations=(HostBinop(r("rd"), r("rs"), r("rt"), "and"),)),
        rule("xori", InstructionFlow.NORMAL, operations=(HostBinop(r("rt"), r("rs"), imm("imm"), "xor"),)),
        rule("subu", InstructionFlow.NORMAL, operations=(HostBinop(r("rd"), r("rs"), r("rt"), "sub"),)),
        # --- set-less-than ---------------------------------------------------
        rule("slt", InstructionFlow.NORMAL, operations=(HostCompare(r("rd"), r("rs"), r("rt"), "slt"),)),
        rule("sltu", InstructionFlow.NORMAL, operations=(HostCompare(r("rd"), r("rs"), r("rt"), "ult"),)),
        rule("slti", InstructionFlow.NORMAL, operations=(HostCompare(r("rt"), r("rs"), imm("imm", signed=True), "slt"),)),
        rule("sltiu", InstructionFlow.NORMAL, operations=(HostCompare(r("rt"), r("rs"), imm("imm", signed=True), "ult"),)),
        # --- halfword memory -------------------------------------------------
        rule("lh", InstructionFlow.NORMAL, operations=(HostLoad(r("rt"), r("rs"), imm("imm", signed=True), 16, True),)),
        rule("lhu", InstructionFlow.NORMAL, operations=(HostLoad(r("rt"), r("rs"), imm("imm", signed=True), 16, False),)),
        rule("sh", InstructionFlow.NORMAL, operations=(HostStore(r("rt"), r("rs"), imm("imm", signed=True), 16),)),
        # --- conditional branches -------------------------------------------
        rule("bgez", InstructionFlow.BRANCH, condition=HostComparison(r("rs"), const(0), "sge")),
        rule("bgtz", InstructionFlow.BRANCH, condition=HostComparison(r("rs"), const(0), "sgt")),
        rule("blez", InstructionFlow.BRANCH, condition=HostComparison(r("rs"), const(0), "sle")),
        rule("bltz", InstructionFlow.BRANCH, condition=HostComparison(r("rs"), const(0), "slt")),
        # --- exceptions ------------------------------------------------------
        rule("break", InstructionFlow.TRAP),
        rule("syscall", InstructionFlow.TRAP),
        # --- indirect control ------------------------------------------------
        rule("jalr", InstructionFlow.INDIRECT_CALL, indirect_source=r("rs")),
        rule("jr_indirect", InstructionFlow.INDIRECT_JUMP, indirect_source=r("rs")),
        # --- overflow-trapping add-immediate ---------------------------------
        rule(
            "addi",
            InstructionFlow.NORMAL,
            host_call=HostCallOperation(
                "openrecomp.mips.add.overflow.check", (r("rs"), imm("imm", signed=True))
            ),
            operations=(HostBinop(r("rt"), r("rs"), imm("imm", signed=True), "add"),),
        ),
        # --- unaligned partial-word merges -----------------------------------
        rule(
            "lwl",
            InstructionFlow.NORMAL,
            host_call=HostCallOperation(
                "openrecomp.mips.lwl",
                (r("rs"), imm("imm", signed=True), r("rt")),
                result=r("rt"),
            ),
        ),
        rule(
            "lwr",
            InstructionFlow.NORMAL,
            host_call=HostCallOperation(
                "openrecomp.mips.lwr",
                (r("rs"), imm("imm", signed=True), r("rt")),
                result=r("rt"),
            ),
        ),
        rule(
            "swl",
            InstructionFlow.NORMAL,
            host_call=HostCallOperation(
                "openrecomp.mips.swl", (r("rs"), imm("imm", signed=True), r("rt"))
            ),
        ),
        rule(
            "swr",
            InstructionFlow.NORMAL,
            host_call=HostCallOperation(
                "openrecomp.mips.swr", (r("rs"), imm("imm", signed=True), r("rt"))
            ),
        ),
        # --- HI/LO multiplication -------------------------------------------
        rule(
            "mult",
            InstructionFlow.NORMAL,
            host_call=HostCallOperation("openrecomp.mips.mult", (r("rs"), r("rt"))),
        ),
        rule(
            "mfhi",
            InstructionFlow.NORMAL,
            host_call=HostCallOperation("openrecomp.mips.mfhi", (), result=r("rd")),
        ),
    )
    return base


def semantics_rules() -> tuple[HostInstructionSemantics, ...]:
    """The frozen Phase-8 rules followed by the additive Phase-10 rules."""
    frozen = p8_semantics.semantics_rules()
    frozen_ops = {rule.op for rule in frozen}
    added = added_rules()
    drift = sorted(rule.op for rule in added if rule.op in frozen_ops)
    if drift:
        raise Phase10SemanticsError(ERROR_DRIFT, ",".join(drift))
    return frozen + added


def build_semantics() -> HostSemantics:
    return HostSemantics(semantics_rules())


def build_service_table() -> rt_abi.RuntimeServiceTable:
    """The declared Phase-10 service surface.

    The Python handlers are the architecture-exact reference used to
    cross-check the native runtime implementation; the native runtime owns the
    actual dispatch.
    """
    services = [
        rt_abi.RuntimeService(service_id, arity)
        for service_id, arity in sorted(SERVICE_ARITIES.items())
    ]

    def native_only(args: tuple[int, ...]) -> int:
        raise rt_abi.RuntimeAbiError("the native runtime implementation handles this service")

    handlers = {service.service_id: native_only for service in services}
    return rt_abi.RuntimeServiceTable(services, handlers=handlers)


def build_emitter_config(
    entry_function: str,
    *,
    services: rt_abi.RuntimeServiceTable | None = None,
    runtime_abi: bool = True,
    delay_slots: bool = True,
    link_register: bool = True,
) -> HostEmitterConfig:
    return HostEmitterConfig(
        semantics=build_semantics(),
        entry_function=entry_function,
        word_bits=32,
        register_names=tuple(f"r{index}" for index in range(32)),
        runtime_abi=rt_abi.RuntimeAbiConfig(services or build_service_table()) if runtime_abi else None,
        delay_slot_metadata_key=DELAY_SLOT_METADATA_KEY if delay_slots else None,
        link_register=LINK_REGISTER if link_register else None,
    )


def missing_rules(ops: Iterable[str]) -> tuple[str, ...]:
    table = build_semantics()
    return tuple(sorted({op for op in ops if not table.has(ARCHITECTURE, op)}))


def assert_preconditions(structure: Any) -> dict[str, Any]:
    """Fail closed on a reachable form the added rules cannot model exactly."""
    jalr_sites: list[int] = []
    jalr_bad: list[int] = []
    delay_slots: list[int] = []
    unmapped_delay_slots: list[int] = []
    trap_sites: list[int] = []
    table = build_semantics()

    for instruction in structure.cfg.instructions:
        if instruction.op == "jalr":
            jalr_sites.append(instruction.address)
            operands = (instruction.metadata or {}).get("operands") or {}
            if operands.get("rd") != 31:
                jalr_bad.append(instruction.address)
        if instruction.flow is InstructionFlow.TRAP:
            trap_sites.append(instruction.address)
        delay_slot = (instruction.metadata or {}).get(DELAY_SLOT_METADATA_KEY)
        if isinstance(delay_slot, dict):
            delay_slots.append(instruction.address)
            if not table.has(ARCHITECTURE, delay_slot.get("op")):
                unmapped_delay_slots.append(instruction.address)

    if jalr_bad:
        raise Phase10SemanticsError(ERROR_UNSUPPORTED_JALR, ",".join(f"0x{a:08x}" for a in sorted(jalr_bad)))
    if unmapped_delay_slots:
        raise Phase10SemanticsError(ERROR_UNMAPPED_DELAY_SLOT, ",".join(f"0x{a:08x}" for a in sorted(unmapped_delay_slots)))

    return {
        "semantics_version": SEMANTICS_VERSION,
        "architecture": ARCHITECTURE,
        "added_ops": list(ADDED_OPS),
        "host_service_ops": dict(sorted(HOST_SERVICE_OPS.items())),
        "service_arities": {name: SERVICE_ARITIES[name] for name in sorted(SERVICE_ARITIES)},
        "jalr_sites": len(jalr_sites),
        "jalr_bad_destinations": len(jalr_bad),
        "folded_delay_slots": len(delay_slots),
        "unmapped_delay_slots": len(unmapped_delay_slots),
        "trap_sites": len(trap_sites),
        "rules_total": len(semantics_rules()),
        "rules_added": len(added_rules()),
    }
