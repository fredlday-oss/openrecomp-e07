#!/usr/bin/env python3
"""OpenRecomp Phase-11 semantics and service surface V1.

The frozen Phase-10 semantic rule table and service table are reused
unchanged. This module adds exactly one additive layer:

* one explicit semantic rule per resolved BIOS vector op (for example
  ``jump_bios_a0_2b``) with a declared host call into the typed BIOS service
  surface; the rule carries the audited argument registers and the documented
  return register, and is never inferred from an address or opcode;
* the declared service surface is the Phase-10 surface plus the resolved BIOS
  service ids with their documented arities.

Everything not resolved here keeps the frozen fail-closed behaviour.
"""

from __future__ import annotations

from typing import Any

import p10_mips32_semantics_v1 as p10_semantics
import p11_bios_v1 as bios
from openrecomp import runtime_abi as rt_abi
from openrecomp.host_emitter import (
    HostCallOperation,
    HostEmitterConfig,
    HostInstrumentation,
    HostInstructionSemantics,
    HostRegister,
    HostSemantics,
)
from openrecomp.program_model import InstructionFlow

SEMANTICS_VERSION = "1.1.0"

ARCHITECTURE = p10_semantics.ARCHITECTURE

ERROR_CODES = (
    "BIOS_RULE_DUPLICATE",
    "BIOS_RULE_DRIFT",
)


class Phase11SemanticsError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown Phase-11 semantics error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def bios_rules(sites: list[bios.BiosVectorSite]) -> tuple[HostInstructionSemantics, ...]:
    """One explicit host-call rule per resolved BIOS vector op."""
    frozen_ops = {rule.op for rule in p10_semantics.semantics_rules()}
    seen: dict[str, str] = {}
    rules: list[HostInstructionSemantics] = []
    for site in sorted(sites, key=lambda item: (item.op_name or "", item.site)):
        if site.op_name is None or site.service_id is None:
            continue
        if site.op_name in frozen_ops:
            raise Phase11SemanticsError("BIOS_RULE_DRIFT", site.op_name)
        if site.op_name in seen:
            if seen[site.op_name] != site.service_id:
                raise Phase11SemanticsError("BIOS_RULE_DUPLICATE", site.op_name)
            continue
        seen[site.op_name] = site.service_id
        if site.kind != "INDIRECT_JUMP":
            raise Phase11SemanticsError("BIOS_RULE_DRIFT", f"{site.op_name}:{site.kind}")
        rules.append(
            HostInstructionSemantics(
                ARCHITECTURE,
                site.op_name,
                InstructionFlow.INDIRECT_JUMP,
                host_call=HostCallOperation(
                    site.service_id,
                    (
                        HostRegister("bios_arg0"),
                        HostRegister("bios_arg1"),
                        HostRegister("bios_arg2"),
                    ),
                    result=HostRegister("bios_ret"),
                ),
            )
        )
    return tuple(rules)


def build_semantics(sites: list[bios.BiosVectorSite]) -> HostSemantics:
    return HostSemantics(p10_semantics.semantics_rules() + bios_rules(sites))


def build_service_table(sites: list[bios.BiosVectorSite]) -> rt_abi.RuntimeServiceTable:
    arities = p10_semantics.SERVICE_ARITIES.copy()
    arities.update(bios.service_arities(sites))
    services = [
        rt_abi.RuntimeService(service_id, arity)
        for service_id, arity in sorted(arities.items())
    ]

    def native_only(args: tuple[int, ...]) -> int:
        raise rt_abi.RuntimeAbiError("the native runtime implementation handles this service")

    handlers = {service.service_id: native_only for service in services}
    return rt_abi.RuntimeServiceTable(services, handlers=handlers)


def build_emitter_config(
    entry_function: str,
    sites: list[bios.BiosVectorSite],
    *,
    instrumentation: HostInstrumentation | None = None,
) -> HostEmitterConfig:
    return HostEmitterConfig(
        semantics=build_semantics(sites),
        entry_function=entry_function,
        word_bits=32,
        register_names=tuple(f"r{index}" for index in range(32)),
        runtime_abi=rt_abi.RuntimeAbiConfig(build_service_table(sites)),
        delay_slot_metadata_key=p10_semantics.DELAY_SLOT_METADATA_KEY,
        link_register=p10_semantics.LINK_REGISTER,
        instrumentation=instrumentation,
    )


def semantics_document(sites: list[bios.BiosVectorSite]) -> dict[str, Any]:
    table = build_semantics(sites)
    service_table = build_service_table(sites)
    return {
        "semantics_version": SEMANTICS_VERSION,
        "rules_total": len(table.keys()),
        "bios_rules": [
            {
                "op": rule.op,
                "service": rule.host_call.service if rule.host_call else None,
                "args": [operand.field for operand in rule.host_call.args] if rule.host_call else [],
                "result": rule.host_call.result.field if rule.host_call and rule.host_call.result else None,
            }
            for rule in bios_rules(sites)
        ],
        "service_ids": list(service_table.service_ids),
        "service_arities": {
            service.service_id: service.arg_count for service in service_table._services.values()
        },
        "native_only_handlers": True,
        "bios_image": "none",
    }
