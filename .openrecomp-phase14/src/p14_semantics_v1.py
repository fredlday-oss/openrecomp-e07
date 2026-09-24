#!/usr/bin/env python3
"""OpenRecomp Phase-14 semantics and service surface V1.

Reuses the frozen Phase-13 semantic-rule builder (which already supports both
``jr`` and ``jalr`` BIOS vector sites and the synthetic pad-hook rules). Phase 14
adds:

* the typed internal service ``ps1.bios.internal.card_continuation`` (the
  project-owned synthetic early-card IRQ continuation identity), so the native
  runtime can validate it through the same host-call ABI as every other service;
* an additive MIPS helper rule for ``mflo`` (the HI/LO low-word read), which the
  Phase-14 frontier reaches inside a newly reachable internal function. The
  frozen Phase-10 table already implements ``mult``/``mfhi`` through host
  services and keeps the shared HI/LO state; ``mflo`` is the missing low-word
  read. Its service id is deliberately placed in a project-owned ``ps1.mips``
  namespace so the frozen Phase-10/11 canonical service numbering is preserved
  exactly (it sorts after every existing service id).

Nothing is inferred from an address or opcode.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src"):
    sys.path.insert(0, str(ROOT / extra))

import p10_mips32_semantics_v1 as p10_semantics  # noqa: E402
import p11_semantics_v1 as p11_semantics  # noqa: E402
import p12_semantics_v1 as p12_semantics  # noqa: E402
import p13_pad_hook_v1 as pad_hook  # noqa: E402
import p13_semantics_v1 as semantics13  # noqa: E402
from openrecomp import runtime_abi as rt_abi  # noqa: E402
from openrecomp.host_emitter import (  # noqa: E402
    HostCallOperation,
    HostEmitterConfig,
    HostInstructionSemantics,
    HostRegister,
    HostSemantics,
)
from openrecomp.program_model import InstructionFlow  # noqa: E402

import p14_services_v1 as services  # noqa: E402

SEMANTICS_VERSION = "4.0.0"

ARCHITECTURE = semantics13.ARCHITECTURE

#: The typed synthetic continuation service identity.
CARD_CONTINUATION_SERVICE = "ps1.bios.internal.card_continuation"
CARD_CONTINUATION_ARITY = 1

#: The additive MIPS helper service (low word of the multiplicand result).
#: The id is project-owned and sorts after every existing service id, so the
#: frozen Phase-10/11 canonical numeric assignment is unchanged.
MIPS_MFLO_SERVICE = "ps1.mips.mflo"
MIPS_MFLO_ARITY = 0
MIPS_ADDED_OPS = ("mflo",)


def added_service_ids() -> tuple[str, ...]:
    return (CARD_CONTINUATION_SERVICE, MIPS_MFLO_SERVICE)


def mips_rules() -> tuple[HostInstructionSemantics, ...]:
    frozen_ops = {rule.op for rule in p10_semantics.semantics_rules()}
    if "mflo" in frozen_ops:
        raise AssertionError("mflo must not already be a frozen rule")
    return (
        HostInstructionSemantics(
            ARCHITECTURE,
            "mflo",
            InstructionFlow.NORMAL,
            host_call=HostCallOperation(MIPS_MFLO_SERVICE, (), result=HostRegister("rd")),
        ),
    )


def build_semantics(sites: list[Any]) -> HostSemantics:
    return HostSemantics(
        p10_semantics.semantics_rules()
        + p11_semantics.added_rules()
        + p12_semantics.bios_rules(sites)
        + pad_hook.pad_hook_rules()
        + mips_rules()
    )


def build_service_table(sites: list[Any]):
    base = semantics13.build_service_table(sites)
    entries: list[rt_abi.RuntimeService] = []
    seen: set[str] = set()
    for service in base._services.values():
        entries.append(rt_abi.RuntimeService(service.service_id, service.arg_count))
        seen.add(service.service_id)
    additions = (
        (CARD_CONTINUATION_SERVICE, CARD_CONTINUATION_ARITY),
        (MIPS_MFLO_SERVICE, MIPS_MFLO_ARITY),
    )
    for service_id, arity in additions:
        if service_id not in seen:
            entries.append(rt_abi.RuntimeService(service_id, arity))
            seen.add(service_id)

    def native_only(args: tuple[int, ...]) -> int:
        raise rt_abi.RuntimeAbiError("the native runtime implementation handles this service")

    handlers = {service.service_id: native_only for service in entries}
    return rt_abi.RuntimeServiceTable(entries, handlers=handlers)


def build_emitter_config(
    entry_function: str,
    sites: list[Any],
    *,
    instrumentation: Any | None = None,
    guarded_resolved_indirect: bool = False,
):
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


def runtime_sites(sites: list[Any]) -> list[Any]:
    """The real sites plus typed internal-service stubs so their macros emit."""
    import types

    extended = list(pad_hook.runtime_sites(list(sites)))
    existing = {getattr(site, "service_id", None) for site in extended}
    for service_id in added_service_ids():
        if service_id not in existing:
            extended.append(types.SimpleNamespace(service_id=service_id))
    return extended


def semantics_document(sites: list[Any]) -> dict[str, Any]:
    document = semantics13.semantics_document(sites)
    document["semantics_version"] = SEMANTICS_VERSION
    service_ids = sorted(set(document["service_ids"]) | set(added_service_ids()))
    document["service_ids"] = service_ids
    document["service_arities"] = dict(document["service_arities"])
    document["service_arities"][CARD_CONTINUATION_SERVICE] = CARD_CONTINUATION_ARITY
    document["service_arities"][MIPS_MFLO_SERVICE] = MIPS_MFLO_ARITY
    document["p14_added_service_ids"] = list(added_service_ids())
    document["p14_added_mips_ops"] = list(MIPS_ADDED_OPS)
    return document
