#!/usr/bin/env python3
"""OpenRecomp Phase-14 proof contracts V1.

Phase 14 reuses the exact inherited Phase-12/Phase-13 initialization proof
contract. These are definitions only: a contract is satisfied at its own stage
gate, never by this module.
"""

from __future__ import annotations

from typing import Any

CONTRACTS_VERSION = "1.0.0"

INITIALIZATION_MARKER = "OPENRECOMP_PHASE14_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE14_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE14_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE14_GENERAL_PS1_COMPATIBILITY"

B0_56_MARKER = "OPENRECOMP_PHASE14_B0_56_GETC0TABLE_V1"
C0_TABLE_MARKER = "OPENRECOMP_PHASE14_C0_TABLE_SURFACE_V1"
EARLY_CARD_PATCH_MARKER = "OPENRECOMP_PHASE14_EARLY_CARD_PATCH_V1"
CARD_CONTINUATION_MARKER = "OPENRECOMP_PHASE14_CARD_CONTINUATION_V1"
B0_57_MARKER = "OPENRECOMP_PHASE14_B0_57_LIVE_VALIDATION_V1"
CARD_INIT_CHAIN_MARKER = "OPENRECOMP_PHASE14_CARD_INIT_CHAIN_V1"
CARD_IRQ_MARKER = "OPENRECOMP_PHASE14_CARD_IRQ_V1"
INITIALIZATION_REPLAY_MARKER = "OPENRECOMP_PHASE14_INITIALIZATION_REPLAY_V1"

INITIALIZATION_PREDICATES = (
    "INIT-PREDECESSOR",
    "INIT-B0-PATCH",
    "INIT-BOUNDARY",
    "INIT-NO-FAIL-CLOSED",
    "INIT-DETERMINISTIC",
    "INIT-NO-FABRICATION",
)

#: The inherited initialization contract source (unchanged by Phase 14).
INITIALIZATION_CONTRACT_SOURCE = ".openrecomp-phase12/src/p12_contracts_v1.py"
INITIALIZATION_CONTRACT_CHANGED = "NO"

PHASE13_BASE_COMMIT = "7bb4502450d47a0d3f3b207a072c5729277af278"
PHASE12_BASE_COMMIT = "7d76f242db2e9233ad9e023d0c63a6984fb118a0"

RESERVED_MARKERS = {
    FRAME_MARKER: "NOT_PROVEN",
    PLAYABILITY_MARKER: "NOT_PROVEN",
    GENERAL_MARKER: "NOT_PROVEN",
}


def contracts_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase14-proof-contracts-v1",
        "contracts_version": CONTRACTS_VERSION,
        "initialization_contract_source": INITIALIZATION_CONTRACT_SOURCE,
        "initialization_contract_changed": INITIALIZATION_CONTRACT_CHANGED,
        "inherited_initialization_predicates": list(INITIALIZATION_PREDICATES),
        "initialization_marker": INITIALIZATION_MARKER,
        "frame_marker": FRAME_MARKER,
        "playability_marker": PLAYABILITY_MARKER,
        "general_marker": GENERAL_MARKER,
        "reserved_markers": dict(sorted(RESERVED_MARKERS.items())),
        "bounded_service_markers": {
            B0_56_MARKER: "PASS|NOT_PROVEN",
            C0_TABLE_MARKER: "PASS|NOT_PROVEN",
            EARLY_CARD_PATCH_MARKER: "PASS|NOT_PROVEN",
            CARD_CONTINUATION_MARKER: "PASS|NOT_PROVEN",
            B0_57_MARKER: "PASS|NOT_PROVEN",
            CARD_INIT_CHAIN_MARKER: "PASS|NOT_PROVEN",
            CARD_IRQ_MARKER: "PASS|NOT_REQUIRED|NOT_PROVEN",
            INITIALIZATION_REPLAY_MARKER: "PASS|NOT_PROVEN",
        },
        "phase13_terminal_boundary": {
            "branch": "phase13/ps1-hercules-c0-init-v1",
            "commit": PHASE13_BASE_COMMIT,
            "verdict": "PASS_BOUNDED_C0_AND_CALLBACK_MEDIATION",
        },
        "phase12_ancestor": {
            "branch": "phase12/ps1-hercules-init-frame-v1",
            "commit": PHASE12_BASE_COMMIT,
        },
        "third_party_code_imported": "NO",
    }
