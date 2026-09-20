#!/usr/bin/env python3
"""OpenRecomp Phase-8 MIPS32 semantic rule table for the real-ELF fixture.

This module declares the explicit, proven ``(architecture, op)`` host-emitter
semantic rules for exactly the reachable op set of the frozen P8-01 fixture
(plus the folded delay-slot ops).  It uses only the existing neutral host
emitter vocabulary, extended additively at P8-04 with:

* width/sign-explicit checked guest memory loads and width-explicit stores;
* a conditional-select operation for ``movz``;
* an opt-in folded delay-slot protocol driven by instruction metadata;
* an opt-in link-register (``$ra``) materialization at call sites.

The table is deliberately closed: unsupported MIPS32 forms (`div`, `mult`,
`movn`, `jalr`, partial-word stores, halfword accesses, ...) have no rule and
therefore fail closed at emission time.
"""

from __future__ import annotations

from typing import Iterable

from openrecomp import runtime_abi as rt_abi
from openrecomp.host_emitter import (
    HostBinop,
    HostComparison,
    HostConst,
    HostConstant,
    HostEmitterConfig,
    HostImmediate,
    HostInstructionSemantics,
    HostLoad,
    HostRegister,
    HostSelect,
    HostSemantics,
    HostStore,
)
from openrecomp.program_model import InstructionFlow

ARCHITECTURE = "mips32-bounded-v1"

DELAY_SLOT_METADATA_KEY = "delay_slot"
LINK_REGISTER = "r31"
OUTPUT_SERVICE = "p8_uart_write"

#: The closed reachable op set of the P8-01 fixture (controls included).
SUPPORTED_OPS = (
    "addiu", "addu", "andi", "beq", "bne", "j", "jal", "jr", "lb", "lbu",
    "lui", "lw", "movz", "nop", "or", "ori", "sb", "sll", "sra", "srl",
    "sw", "xor",
)
#: Folded delay-slot ops (subset of the reachable set, all NORMAL).
DELAY_SLOT_OPS = ("addiu", "nop", "or", "sb")


def _r(op: str, flow: InstructionFlow, **kwargs) -> HostInstructionSemantics:
    return HostInstructionSemantics(ARCHITECTURE, op, flow, **kwargs)


def semantics_rules() -> tuple[HostInstructionSemantics, ...]:
    """The explicit semantic rules for the frozen fixture's reachable ops."""
    register = HostRegister
    immediate = HostImmediate
    constant = HostConstant
    return (
        _r("nop", InstructionFlow.NORMAL),
        _r(
            "addiu",
            InstructionFlow.NORMAL,
            operations=(HostBinop(register("rt"), register("rs"), immediate("imm", signed=True), "add"),),
        ),
        _r(
            "addu",
            InstructionFlow.NORMAL,
            operations=(HostBinop(register("rd"), register("rs"), register("rt"), "add"),),
        ),
        _r(
            "andi",
            InstructionFlow.NORMAL,
            operations=(HostBinop(register("rt"), register("rs"), immediate("imm"), "and"),),
        ),
        _r(
            "lui",
            InstructionFlow.NORMAL,
            operations=(HostConst(register("rt"), immediate("imm", shift=16)),),
        ),
        _r(
            "or",
            InstructionFlow.NORMAL,
            operations=(HostBinop(register("rd"), register("rs"), register("rt"), "or"),),
        ),
        _r(
            "ori",
            InstructionFlow.NORMAL,
            operations=(HostBinop(register("rt"), register("rs"), immediate("imm"), "or"),),
        ),
        _r(
            "sll",
            InstructionFlow.NORMAL,
            operations=(HostBinop(register("rd"), register("rt"), immediate("shamt"), "shl"),),
        ),
        _r(
            "sra",
            InstructionFlow.NORMAL,
            operations=(HostBinop(register("rd"), register("rt"), immediate("shamt"), "ashr"),),
        ),
        _r(
            "srl",
            InstructionFlow.NORMAL,
            operations=(HostBinop(register("rd"), register("rt"), immediate("shamt"), "lshr"),),
        ),
        _r(
            "xor",
            InstructionFlow.NORMAL,
            operations=(HostBinop(register("rd"), register("rs"), register("rt"), "xor"),),
        ),
        _r(
            "lb",
            InstructionFlow.NORMAL,
            operations=(HostLoad(register("rt"), register("rs"), immediate("imm", signed=True), width_bits=8, signed=True),),
        ),
        _r(
            "lbu",
            InstructionFlow.NORMAL,
            operations=(HostLoad(register("rt"), register("rs"), immediate("imm", signed=True), width_bits=8, signed=False),),
        ),
        _r(
            "lw",
            InstructionFlow.NORMAL,
            operations=(HostLoad(register("rt"), register("rs"), immediate("imm", signed=True), width_bits=32, signed=False),),
        ),
        _r(
            "sb",
            InstructionFlow.NORMAL,
            operations=(HostStore(register("rt"), register("rs"), immediate("imm", signed=True), width_bits=8),),
        ),
        _r(
            "sw",
            InstructionFlow.NORMAL,
            operations=(HostStore(register("rt"), register("rs"), immediate("imm", signed=True), width_bits=32),),
        ),
        _r(
            "movz",
            InstructionFlow.NORMAL,
            operations=(
                HostSelect(
                    register("rd"),
                    true_value=register("rt"),
                    false_value=register("rd"),
                    lhs=register("rs"),
                    rhs=constant(0),
                    predicate="eq",
                ),
            ),
        ),
        _r("beq", InstructionFlow.BRANCH, condition=HostComparison(register("rs"), register("rt"), "eq")),
        _r("bne", InstructionFlow.BRANCH, condition=HostComparison(register("rs"), register("rt"), "ne")),
        _r("j", InstructionFlow.JUMP),
        _r("jal", InstructionFlow.CALL),
        _r("jr", InstructionFlow.RETURN),
    )


def build_semantics() -> HostSemantics:
    return HostSemantics(semantics_rules())


def runtime_services() -> rt_abi.RuntimeServiceTable:
    """The fixture's explicit host-service surface (output byte sink)."""

    def _native_only(args: tuple[int, ...]) -> int:
        raise rt_abi.RuntimeAbiError("the native runtime implementation handles this service")

    service = rt_abi.RuntimeService(OUTPUT_SERVICE, 1)
    return rt_abi.RuntimeServiceTable([service], handlers={OUTPUT_SERVICE: _native_only})


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
        runtime_abi=rt_abi.RuntimeAbiConfig(services or runtime_services()) if runtime_abi else None,
        delay_slot_metadata_key=DELAY_SLOT_METADATA_KEY if delay_slots else None,
        link_register=LINK_REGISTER if link_register else None,
    )


def missing_rules(ops: Iterable[str]) -> tuple[str, ...]:
    """Return the ops of ``ops`` that have no semantic rule (fail closed)."""
    table = build_semantics()
    return tuple(sorted({op for op in ops if not table.has(ARCHITECTURE, op)}))
