#!/usr/bin/env python3
"""OpenRecomp Phase-13 controlled synthetic callback mediation V1.

The Hercules pad-start wrapper ``fn_80015d18`` tail-calls the thunk
``fn_80015f68`` (call site ``0x80015d30``). The thunk loads the callback slot
``0x8002ed84`` and performs ``jr t1`` at ``0x80015f74``. That slot is populated
by ``fn_80015f90`` from the documented B0 table entry ``0x5b`` plus the
documented offset ``0x884``:

    [0x8002ed84] = GetB0Table()[0x5b] + 0x884

Under the versioned Phase-12 synthetic B0 model the entry value is
``P12_SYNTH_BASE + 0x1000`` (``0x1f001000``), so the runtime target is the
project-owned synthetic address ``0x1f001884``. It is an internal BIOS pad hook,
not a guest code address and not a recovered BIOS address.

This module mediates that site as a *typed synthetic controlled target*
(``ps1.bios.internal.pad_start_hook``): a host-call rule is keyed on a unique op
name, the source register value is passed to the runtime service as an argument,
and the service validates it against the mechanically derived address. Unknown,
null, unaligned or out-of-surface targets fail closed; there is no general
permissive indirect execution.

The second thunk (``0x80015f7c``/``0x80015f88`` -> ``0x1f001894``,
``ps1.bios.internal.pad_stop_hook``) is not reached in initialization and is not
present in the bounded fixture analysis; its runtime service identity is defined
and fails closed, but no site is fabricated.
"""

from __future__ import annotations

import dataclasses
import pathlib
import sys
from dataclasses import dataclass
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src"):
    sys.path.insert(0, str(ROOT / extra))

import p10_mips32_semantics_v1 as p10_semantics  # noqa: E402
import p11_bios_v1 as p11_bios  # noqa: E402
import p11_dynamic_v1 as dynamic  # noqa: E402
import p11_semantics_v1 as p11_semantics  # noqa: E402
import p11_structure_v1 as structure_bridge  # noqa: E402
import p12_semantics_v1 as p12_semantics  # noqa: E402
from openrecomp import runtime_abi as rt_abi  # noqa: E402
from openrecomp.host_emitter import (  # noqa: E402
    HostCallOperation,
    HostInstructionSemantics,
    HostRegister,
    HostSemantics,
)
from openrecomp.indirect_control_flow import (  # noqa: E402
    IndirectControlFlowBasis,
    IndirectControlFlowEvidence,
    IndirectControlFlowKind,
    IndirectControlFlowStatus,
    classify_indirect_control_flow,
)
from openrecomp.program_model import EvidenceClass, InstructionFlow  # noqa: E402

import p13_services_v1 as services  # noqa: E402

PAD_HOOK_VERSION = "1.0.0"

ARCHITECTURE = p10_semantics.ARCHITECTURE

#: Operand-field name carrying the jr source register (resolved through the
#: neutral adapter fields exactly like the documented ``bios_argN`` fields).
PAD_HOOK_FIELD = "pad_hook_target"

#: Synthetic B0 window offset for the pad hooks (documented +0x884 / +0x894).
PAD_HOOK_START_OFFSET = 0x884
PAD_HOOK_STOP_OFFSET = 0x894

ERROR_CODES = (
    "PAD_HOOK_SITE_ABSENT",
    "PAD_HOOK_SITE_SHAPE",
    "PAD_HOOK_DUPLICATE_OP",
)


class Phase13PadHookError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown Phase-13 pad-hook error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class PadHook:
    site: int
    op: str
    service_id: str
    slot: int
    offset: int
    present: bool


PAD_HOOKS: tuple[PadHook, ...] = (
    PadHook(
        site=0x80015F74,
        op="jump_p13_pad_start_hook",
        service_id="ps1.bios.internal.pad_start_hook",
        slot=0x8002ED84,
        offset=PAD_HOOK_START_OFFSET,
        present=True,
    ),
    PadHook(
        site=0x80015F88,
        op="jump_p13_pad_stop_hook",
        service_id="ps1.bios.internal.pad_stop_hook",
        slot=0x8002ED88,
        offset=PAD_HOOK_STOP_OFFSET,
        present=False,
    ),
)

PRESENT_HOOKS = tuple(spec for spec in PAD_HOOKS if spec.present)


def synthetic_target(spec: PadHook) -> int:
    """The synthetic callback target derived from the versioned B0 window model.

    ``GetB0Table()[0x5b]`` resolves to ``P12_SYNTH_BASE + SYNTH_TARGET_OFFSET``;
    the documented pad hook offsets are added. This is a project-owned synthetic
    address, never a recovered BIOS address.
    """
    return services.services12.SYNTH_BASE + services.services12.SYNTH_TARGET_OFFSET + spec.offset


def inject_records(analysis: dict[str, Any]) -> dict[str, Any]:
    """Rename the present pad-hook thunk records and annotate the source register."""
    modified = _deep_copy(analysis)
    by_site = {spec.site: spec for spec in PRESENT_HOOKS}
    for record in modified.get("records", []):
        spec = by_site.get(record.get("address"))
        if spec is None:
            continue
        if record.get("terminator") != "indirect-jump" or record.get("op") != "jr":
            raise Phase13PadHookError(
                "PAD_HOOK_SITE_SHAPE", f"0x{spec.site:08x}:{record.get('op')}"
            )
        source = (record.get("operands") or {}).get("rs")
        if not isinstance(source, int):
            raise Phase13PadHookError("PAD_HOOK_SITE_SHAPE", f"0x{spec.site:08x}:rs")
        record["op"] = spec.op
        record.setdefault("operands", {})[PAD_HOOK_FIELD] = source
    return modified


def _deep_copy(analysis: dict[str, Any]) -> dict[str, Any]:
    import copy

    return copy.deepcopy(analysis)


def pad_hook_evidence(result: Any) -> tuple[IndirectControlFlowEvidence, ...]:
    terminals = structure_bridge.terminal_units(result)
    records: list[IndirectControlFlowEvidence] = []
    for spec in PRESENT_HOOKS:
        unit = terminals.get(spec.site)
        if unit is None:
            raise Phase13PadHookError("PAD_HOOK_SITE_ABSENT", f"0x{spec.site:08x}")
        target = synthetic_target(spec)
        records.append(
            IndirectControlFlowEvidence(
                function_id=unit[0],
                block_id=unit[1],
                address=spec.site,
                kind=IndirectControlFlowKind.INDIRECT_JUMP,
                status=IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED,
                basis=IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE,
                external_mechanism=spec.service_id,
                detail=(
                    f"slot=0x{spec.slot:08x}; "
                    f"target=GetB0Table()[0x5b]+0x{spec.offset:x}=0x{target:08x}; "
                    "project-owned synthetic controlled target, validated by the typed host service"
                ),
                source="phase13-pad-hook-evidence",
                evidence=EvidenceClass.PROVEN,
            )
        )
    return tuple(records)


def reclassify(
    result: Any,
    site_document: dict[str, Any],
    merged_analysis: dict[str, Any],
    dynamic_observations: dict[int, tuple[int, ...]] | None,
) -> Any:
    """Rebuild the indirect-control classification with the pad-hook evidence added."""
    terminals = structure_bridge.terminal_units(result)
    evidence = list(p11_bios.evidence_records(site_document, terminals))
    if dynamic_observations:
        dynamic_evidence, _ = dynamic.resolve_sites(
            merged_analysis, observations=dynamic_observations, site_units=terminals
        )
        evidence.extend(dynamic_evidence)
    evidence.extend(pad_hook_evidence(result))
    classification = classify_indirect_control_flow(result.units, evidence=tuple(evidence))
    return dataclasses.replace(result, classification=classification)


def pad_hook_rules() -> tuple[HostInstructionSemantics, ...]:
    seen: set[str] = set()
    rules: list[HostInstructionSemantics] = []
    for spec in PRESENT_HOOKS:
        if spec.op in seen:
            raise Phase13PadHookError("PAD_HOOK_DUPLICATE_OP", spec.op)
        seen.add(spec.op)
        rules.append(
            HostInstructionSemantics(
                ARCHITECTURE,
                spec.op,
                InstructionFlow.INDIRECT_JUMP,
                host_call=HostCallOperation(
                    spec.service_id,
                    (HostRegister(PAD_HOOK_FIELD),),
                    result=None,
                ),
            )
        )
    return tuple(rules)


def build_semantics(sites: list[Any]) -> HostSemantics:
    return HostSemantics(
        p10_semantics.semantics_rules()
        + p11_semantics.added_rules()
        + p12_semantics.bios_rules(sites)
        + pad_hook_rules()
    )


def build_service_table(sites: list[Any]) -> rt_abi.RuntimeServiceTable:
    base = p12_semantics.build_service_table(sites)

    def native_only(args: tuple[int, ...]) -> int:
        raise rt_abi.RuntimeAbiError("the native runtime implementation handles this service")

    entries: list[rt_abi.RuntimeService] = []
    seen: set[str] = set()
    for service in base._services.values():
        entries.append(rt_abi.RuntimeService(service.service_id, service.arg_count))
        seen.add(service.service_id)
    for spec in PAD_HOOKS:
        if spec.service_id in seen:
            continue
        entries.append(rt_abi.RuntimeService(spec.service_id, 1))
        seen.add(spec.service_id)
    handlers = {service.service_id: native_only for service in entries}
    return rt_abi.RuntimeServiceTable(entries, handlers=handlers)


def build_emitter_config(
    entry_function: str,
    sites: list[Any],
    *,
    instrumentation: Any | None = None,
    guarded_resolved_indirect: bool = False,
):
    return p12_semantics.HostEmitterConfig(
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
    """The real sites plus service-id stubs so the runtime macros are emitted."""
    import types

    extended = list(sites)
    existing = {site.service_id for site in sites}
    for spec in PAD_HOOKS:
        if spec.service_id not in existing:
            extended.append(types.SimpleNamespace(service_id=spec.service_id))
    return extended


def semantics_document(sites: list[Any]) -> dict[str, Any]:
    document = p12_semantics.semantics_document(sites)
    service_ids = sorted(set(document["service_ids"])
                         | {spec.service_id for spec in PAD_HOOKS})
    document["service_ids"] = service_ids
    document["service_arities"] = dict(document["service_arities"])
    for spec in PAD_HOOKS:
        document["service_arities"][spec.service_id] = 1
    document["pad_hook_rules"] = [
        {
            "op": rule.op,
            "flow": rule.flow.value,
            "service": rule.host_call.service if rule.host_call else None,
            "args": [operand.field for operand in rule.host_call.args] if rule.host_call else [],
            "result": None,
        }
        for rule in pad_hook_rules()
    ]
    return document


def document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase13-pad-hook-mediation-v1",
        "version": PAD_HOOK_VERSION,
        "field": PAD_HOOK_FIELD,
        "hooks": [
            {
                "site": f"0x{spec.site:08x}",
                "op": spec.op,
                "service_id": spec.service_id,
                "slot": f"0x{spec.slot:08x}",
                "offset": f"0x{spec.offset:x}",
                "synthetic_target": f"0x{synthetic_target(spec):08x}",
                "present": spec.present,
            }
            for spec in PAD_HOOKS
        ],
        "mediation": "SYNTHETIC_CONTROLLED_TARGET",
        "general_permissive_indirect": False,
        "third_party_code_imported": "NO",
    }
