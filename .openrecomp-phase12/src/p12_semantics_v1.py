#!/usr/bin/env python3
"""OpenRecomp Phase-12 semantics and service surface V1.

Reuses the frozen Phase-10 rule table and the Phase-11 additive rules, and adds
one explicit host-call rule per resolved Phase-12 BIOS vector site. Unlike the
Phase-11 rule builder, the Phase-12 builder supports both indirect-jump
(``jr``) and indirect-call (``jalr``) BIOS vector sites, because the
``B0:0x57`` GetB0Table caller is a ``jalr`` site.

Nothing is inferred from an address or opcode: a rule exists only for a site
whose vector base and function index both resolve to constants and whose
(vector, index) pair is in the documented Phase-12 surface.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase10/src", ".openrecomp-phase11/src"):
    sys.path.insert(0, str(ROOT / extra))

import p10_mips32_semantics_v1 as p10_semantics  # noqa: E402
import p11_bios_v1 as bios  # noqa: E402
import p11_semantics_v1 as p11_semantics  # noqa: E402
from openrecomp import runtime_abi as rt_abi  # noqa: E402
from openrecomp.host_emitter import (  # noqa: E402
    HostCallOperation,
    HostEmitterConfig,
    HostInstructionSemantics,
    HostInstrumentation,
    HostRegister,
    HostSemantics,
)
from openrecomp.program_model import InstructionFlow  # noqa: E402

SEMANTICS_VERSION = "2.0.0"

ARCHITECTURE = p10_semantics.ARCHITECTURE

_KIND_TO_FLOW = {
    "INDIRECT_JUMP": InstructionFlow.INDIRECT_JUMP,
    "INDIRECT_CALL": InstructionFlow.INDIRECT_CALL,
}


def bios_rules(sites: list[bios.BiosVectorSite]) -> tuple[HostInstructionSemantics, ...]:
    """One explicit host-call rule per resolved BIOS vector op (both kinds)."""
    frozen_ops = {rule.op for rule in p10_semantics.semantics_rules()}
    seen: dict[str, str] = {}
    rules: list[HostInstructionSemantics] = []
    for site in sorted(sites, key=lambda item: (item.op_name or "", item.site)):
        if site.op_name is None or site.service_id is None:
            continue
        if site.op_name in frozen_ops:
            raise p11_semantics.Phase11SemanticsError("BIOS_RULE_DRIFT", site.op_name)
        if site.op_name in seen:
            if seen[site.op_name] != site.service_id:
                raise p11_semantics.Phase11SemanticsError("BIOS_RULE_DUPLICATE", site.op_name)
            continue
        seen[site.op_name] = site.service_id
        flow = _KIND_TO_FLOW.get(site.kind)
        if flow is None:
            raise p11_semantics.Phase11SemanticsError(
                "BIOS_RULE_DRIFT", f"{site.op_name}:{site.kind}"
            )
        service = bios.VECTOR_TABLES[site.vector][site.function_index]
        args = tuple(
            HostRegister(f"bios_arg{position}")
            for position in range(len(service["signature"]))
        )
        result_register = service.get("result_register", bios.BIOS_RETURN_REGISTER)
        rules.append(
            HostInstructionSemantics(
                ARCHITECTURE,
                site.op_name,
                flow,
                host_call=HostCallOperation(
                    site.service_id,
                    args,
                    result=(HostRegister("bios_ret") if result_register is not None else None),
                ),
            )
        )
    return tuple(rules)


def build_semantics(sites: list[bios.BiosVectorSite]) -> HostSemantics:
    return HostSemantics(
        p10_semantics.semantics_rules()
        + p11_semantics.added_rules()
        + bios_rules(sites)
    )


def build_service_table(sites: list[bios.BiosVectorSite]) -> rt_abi.RuntimeServiceTable:
    return p11_semantics.build_service_table(sites)


def build_emitter_config(
    entry_function: str,
    sites: list[bios.BiosVectorSite],
    *,
    instrumentation: HostInstrumentation | None = None,
    guarded_resolved_indirect: bool = False,
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
        guarded_resolved_indirect=guarded_resolved_indirect,
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
                "flow": rule.flow.value,
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
