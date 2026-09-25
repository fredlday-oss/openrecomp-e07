#!/usr/bin/env python3
"""OpenRecomp Phase-15 proof contracts V1.

Phase 15 reuses the exact inherited Phase-14/Phase-13 initialization proof
contract. These are definitions only: a contract is satisfied at its own stage
gate, never by this module.
"""

from __future__ import annotations

from typing import Any

CONTRACTS_VERSION = "1.0.0"

INITIALIZATION_MARKER = "OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE15_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE15_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE15_GENERAL_PS1_COMPATIBILITY"

INTERRUPT_MMIO_CONTRACT_MARKER = "OPENRECOMP_PHASE15_INTERRUPT_MMIO_CONTRACT_V1"
I_STAT_I_MASK_MARKER = "OPENRECOMP_PHASE15_I_STAT_I_MASK_V1"
SYS_CONTROL_MARKER = "OPENRECOMP_PHASE15_SYS_CONTROL_V1"
DMA2_REGISTER_STATE_MARKER = "OPENRECOMP_PHASE15_DMA2_REGISTER_STATE_V1"
NULL_STORE_ROOT_CAUSE_MARKER = "OPENRECOMP_PHASE15_NULL_STORE_ROOT_CAUSE_V1"
TIMER1_VIRTUAL_TIME_MARKER = "OPENRECOMP_PHASE15_TIMER1_VIRTUAL_TIME_V1"
GPUSTAT_MARKER = "OPENRECOMP_PHASE15_GPUSTAT_V1"
INIT_BOUNDARY_MARKER = "OPENRECOMP_PHASE15_INIT_BOUNDARY_V1"
INIT_NO_FAIL_CLOSED_MARKER = "OPENRECOMP_PHASE15_INIT_NO_FAIL_CLOSED_V1"
INITIALIZATION_REPLAY_MARKER = "OPENRECOMP_PHASE15_INITIALIZATION_REPLAY_V1"

INITIALIZATION_PREDICATES = (
    "INIT-PREDECESSOR",
    "INIT-B0-PATCH",
    "INIT-BOUNDARY",
    "INIT-NO-FAIL-CLOSED",
    "INIT-DETERMINISTIC",
    "INIT-NO-FABRICATION",
)

#: The inherited initialization contract source (unchanged by Phase 15).
INITIALIZATION_CONTRACT_SOURCE = ".openrecomp-phase12/src/p12_contracts_v1.py"
INITIALIZATION_CONTRACT_CHANGED = "NO"

PHASE14_BASE_COMMIT = "830be0f7be998061e8d442134cfae511d5dd8c62"

#: The semantic initialization boundary (Exec handoff to the TITLE overlay).
INIT_BOUNDARY_EXEC_SITE = 0x80015B84
INIT_BOUNDARY_TITLE_ENTRY = 0x800380A0

RESERVED_MARKERS = {
    FRAME_MARKER: "NOT_PROVEN",
    PLAYABILITY_MARKER: "NOT_PROVEN",
    GENERAL_MARKER: "NOT_PROVEN",
}


def contracts_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase15-proof-contracts-v1",
        "contracts_version": CONTRACTS_VERSION,
        "initialization_contract_source": INITIALIZATION_CONTRACT_SOURCE,
        "initialization_contract_changed": INITIALIZATION_CONTRACT_CHANGED,
        "inherited_initialization_predicates": list(INITIALIZATION_PREDICATES),
        "initialization_marker": INITIALIZATION_MARKER,
        "frame_marker": FRAME_MARKER,
        "playability_marker": PLAYABILITY_MARKER,
        "general_marker": GENERAL_MARKER,
        "reserved_markers": dict(sorted(RESERVED_MARKERS.items())),
        "init_boundary": {
            "kind": "A0:0x43 Exec handoff",
            "exec_site": f"0x{INIT_BOUNDARY_EXEC_SITE:08x}",
            "title_entry": f"0x{INIT_BOUNDARY_TITLE_ENTRY:08x}",
        },
        "bounded_service_markers": {
            INTERRUPT_MMIO_CONTRACT_MARKER: "PASS|NOT_PROVEN",
            I_STAT_I_MASK_MARKER: "PASS|NOT_PROVEN",
            SYS_CONTROL_MARKER: "PASS|NOT_PROVEN",
            DMA2_REGISTER_STATE_MARKER: "PASS|NOT_PROVEN",
            NULL_STORE_ROOT_CAUSE_MARKER: "PASS|NOT_PROVEN",
            TIMER1_VIRTUAL_TIME_MARKER: "PASS|NOT_PROVEN",
            GPUSTAT_MARKER: "PASS|NOT_PROVEN",
            INIT_BOUNDARY_MARKER: "PASS|NOT_PROVEN",
            INIT_NO_FAIL_CLOSED_MARKER: "PASS|NOT_PROVEN",
            INITIALIZATION_REPLAY_MARKER: "PASS|NOT_PROVEN",
        },
        "phase14_terminal_boundary": {
            "branch": "phase14/ps1-hercules-init-closure-v1",
            "commit": PHASE14_BASE_COMMIT,
            "verdict": "PASS_BOUNDED_INITIALIZATION_CLOSURE_FRONTIER_REMAINS",
        },
        "third_party_code_imported": "NO",
    }
