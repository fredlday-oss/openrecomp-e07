#!/usr/bin/env python3
"""OpenRecomp Phase-13 proof contracts V1.

Phase 13 reuses the exact Phase-12 initialization/frame proof contracts. These
are definitions only: a contract is satisfied at its own stage gate, never by
this module.
"""

from __future__ import annotations

from typing import Any

CONTRACTS_VERSION = "1.0.0"

INITIALIZATION_MARKER = "OPENRECOMP_PHASE13_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE13_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE13_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE13_GENERAL_PS1_COMPATIBILITY"

SYSENQINTRP_MARKER = "OPENRECOMP_PHASE13_SYSENQINTRP_V1"
SYSDEQINTRP_MARKER = "OPENRECOMP_PHASE13_SYSDEQINTRP_V1"
INTRP_ROUNDTRIP_MARKER = "OPENRECOMP_PHASE13_INTRP_ROUNDTRIP_V1"
CALLBACK_MEDIATION_MARKER = "OPENRECOMP_PHASE13_CALLBACK_MEDIATION_V1"
CHANGECLEARRCNT_MARKER = "OPENRECOMP_PHASE13_CHANGECLEARRCNT_V1"
TIMER1_MARKER = "OPENRECOMP_PHASE13_TIMER1_V1"
INTERRUPT_MMIO_MARKER = "OPENRECOMP_PHASE13_INTERRUPT_MMIO_V1"
INITIALIZATION_REPLAY_MARKER = "OPENRECOMP_PHASE13_INITIALIZATION_REPLAY_V1"

#: The inherited initialization contract source (unchanged by Phase 13).
INITIALIZATION_CONTRACT_SOURCE = ".openrecomp-phase12/src/p12_contracts_v1.py"
INITIALIZATION_CONTRACT_CHANGED = "NO"

PHASE12_BASE_COMMIT = "7d76f242db2e9233ad9e023d0c63a6984fb118a0"
PHASE11_BASE_COMMIT = "665d11dc9f760d0c4ea2486e186c1fe5c762647c"

RESERVED_MARKERS = {
    FRAME_MARKER: "NOT_PROVEN",
    PLAYABILITY_MARKER: "NOT_PROVEN",
    GENERAL_MARKER: "NOT_PROVEN",
}


def contracts_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase13-proof-contracts-v1",
        "contracts_version": CONTRACTS_VERSION,
        "initialization_contract_source": INITIALIZATION_CONTRACT_SOURCE,
        "initialization_contract_changed": INITIALIZATION_CONTRACT_CHANGED,
        "inherited_phase12_contracts": [
            "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF",
            "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF",
        ],
        "initialization_marker": INITIALIZATION_MARKER,
        "frame_marker": FRAME_MARKER,
        "playability_marker": PLAYABILITY_MARKER,
        "general_marker": GENERAL_MARKER,
        "reserved_markers": dict(sorted(RESERVED_MARKERS.items())),
        "bounded_service_markers": {
            SYSENQINTRP_MARKER: "PASS|NOT_PROVEN",
            SYSDEQINTRP_MARKER: "PASS|NOT_PROVEN",
            INTRP_ROUNDTRIP_MARKER: "PASS|NOT_PROVEN",
            CALLBACK_MEDIATION_MARKER: "PASS|NOT_PROVEN",
            CHANGECLEARRCNT_MARKER: "PASS|NOT_REQUIRED|NOT_PROVEN",
            TIMER1_MARKER: "PASS|NOT_REQUIRED|NOT_PROVEN",
            INTERRUPT_MMIO_MARKER: "PASS|NOT_REQUIRED|NOT_PROVEN",
            INITIALIZATION_REPLAY_MARKER: "PASS|NOT_PROVEN",
        },
        "phase12_terminal_boundary": {
            "branch": "phase12/ps1-hercules-init-frame-v1",
            "commit": PHASE12_BASE_COMMIT,
            "verdict": "PASS_BOUNDED_B0_MEDIATION_PRIVATE_FIXTURE",
        },
        "phase11_terminal_boundary": {
            "branch": "phase11/ps1-playability-v1",
            "commit": PHASE11_BASE_COMMIT,
            "verdict": "PASS_BOUNDED_MILESTONE_C_PRIVATE_FIXTURE",
        },
        "third_party_code_imported": "NO",
    }
