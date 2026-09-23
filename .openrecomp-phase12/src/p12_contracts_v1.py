#!/usr/bin/env python3
"""OpenRecomp Phase-12 proof contracts V1.

Machine-readable definitions of the two Phase-12 target proof contracts and the
reserved markers. These are definitions only: a contract is satisfied at its
own stage gate, never by this module.
"""

from __future__ import annotations

from typing import Any

CONTRACTS_VERSION = "1.0.0"

INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"

B0_5B_MARKER = "OPENRECOMP_PHASE12_B0_5B_CHANGECLEARPAD_V1"
B0_TABLE_MARKER = "OPENRECOMP_PHASE12_B0_TABLE_INDIRECT_V1"
GPU_OT_DMA_MARKER = "OPENRECOMP_PHASE12_GPU_OT_DMA_V1"
TEXTURE_VRAM_MARKER = "OPENRECOMP_PHASE12_TEXTURE_VRAM_V1"
GTE_GEOMETRY_MARKER = "OPENRECOMP_PHASE12_GTE_GEOMETRY_V1"
REPLAY_MARKER = "OPENRECOMP_PHASE12_END_TO_END_REPLAY_V1"

INITIALIZATION_PREDICATES = (
    "INIT-PREDECESSOR",
    "INIT-B0-PATCH",
    "INIT-BOUNDARY",
    "INIT-NO-FAIL-CLOSED",
    "INIT-DETERMINISTIC",
    "INIT-NO-FABRICATION",
)

FRAME_PREDICATES = (
    "FRAME-PREDECESSOR",
    "FRAME-PRIMITIVE",
    "FRAME-OT",
    "FRAME-SUBMIT",
    "FRAME-DETERMINISTIC",
    "FRAME-NOT-PLAYABILITY",
)

RESERVED_MARKERS = {
    PLAYABILITY_MARKER: "NOT_PROVEN",
    GENERAL_MARKER: "NOT_PROVEN",
}


def initialization_contract() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase12-proof-contract-v1",
        "marker": INITIALIZATION_MARKER,
        "target": "deterministic Hercules initialization completion",
        "bounded": "PRIVATE_FIXTURE_BOUNDED",
        "milestone": "B",
        "predicates": [
            {
                "id": "INIT-PREDECESSOR",
                "requirement": "frozen Phase-11 boundary and Phase-12 predecessors PASS",
                "mechanical": "ancestry from 665d11dc; P12-00..P12-04 markers PASS",
            },
            {
                "id": "INIT-B0-PATCH",
                "requirement": "documented B0 pad-patch sequence observed",
                "mechanical": "GetB0Table returns a table pointer; entry 0x5B read; "
                              "derived pointers at +0x884/+0x894; eleven words cleared at "
                              "+0x594..+0x5bc; each recorded as a deterministic observable",
            },
            {
                "id": "INIT-BOUNDARY",
                "requirement": "reach a mechanically defined initialization-completion boundary",
                "mechanical": "first steady-state repeating block cycle after INIT-B0-PATCH",
            },
            {
                "id": "INIT-NO-FAIL-CLOSED",
                "requirement": "no fail-closed event on the proven prefix",
                "mechanical": "trace failure count is zero from entry to INIT-BOUNDARY",
            },
            {
                "id": "INIT-DETERMINISTIC",
                "requirement": "two fresh runs byte-identical on deterministic fields",
                "mechanical": "block digest, register file, RAM digest, device transcripts",
            },
            {
                "id": "INIT-NO-FABRICATION",
                "requirement": "no fabrication and no guest machine-code execution",
                "mechanical": "no BIOS image, no fabricated guest code, no fail-open fallback",
            },
        ],
        "not_required": ["playability", "general PS1 compatibility"],
    }


def frame_contract() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase12-proof-contract-v1",
        "marker": FRAME_MARKER,
        "target": "deterministic Hercules first-frame submission",
        "bounded": "PRIVATE_FIXTURE_BOUNDED",
        "milestone": "D",
        "predicate_dependency": INITIALIZATION_MARKER,
        "predicates": [
            {
                "id": "FRAME-PREDECESSOR",
                "requirement": "initialization proof PASS",
                "mechanical": f"{INITIALIZATION_MARKER}=PASS",
            },
            {
                "id": "FRAME-PRIMITIVE",
                "requirement": "genuine typed GPU primitive/command submission",
                "mechanical": ">=1 ordered typed GP0/GP1 write with classification",
            },
            {
                "id": "FRAME-OT",
                "requirement": "active ordering-table insertion observed",
                "mechanical": "guest OT node write subsequently traversed",
            },
            {
                "id": "FRAME-SUBMIT",
                "requirement": "frame-submission boundary and buffer transition",
                "mechanical": "active OT submitted via documented GPU/DMA path; "
                              "active-buffer/OT transition observed",
            },
            {
                "id": "FRAME-DETERMINISTIC",
                "requirement": "two fresh runs byte-identical on deterministic fields",
                "mechanical": "block digest, register file, RAM digest, device transcripts",
            },
            {
                "id": "FRAME-NOT-PLAYABILITY",
                "requirement": "no playability or general-compatibility claim",
                "mechanical": "playability and general markers remain NOT_PROVEN",
            },
        ],
        "explicitly_not_required": [
            "literal framebuffer or screenshot (unless the contract is amended by evidence)",
            "playability",
            "general PS1 compatibility",
        ],
    }


def contracts_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase12-proof-contracts-v1",
        "contracts_version": CONTRACTS_VERSION,
        "initialization": initialization_contract(),
        "frame": frame_contract(),
        "reserved_markers": dict(sorted(RESERVED_MARKERS.items())),
        "bounded_service_markers": {
            B0_5B_MARKER: "PASS|NOT_PROVEN",
            B0_TABLE_MARKER: "PASS|NOT_PROVEN",
            GPU_OT_DMA_MARKER: "PASS|NOT_PROVEN",
            TEXTURE_VRAM_MARKER: "PASS|NOT_PROVEN",
            GTE_GEOMETRY_MARKER: "PASS|NOT_PROVEN",
            REPLAY_MARKER: "PASS|NOT_PROVEN",
        },
        "phase11_terminal_boundary": {
            "branch": "phase11/ps1-playability-v1",
            "commit": "665d11dc9f760d0c4ea2486e186c1fe5c762647c",
            "verdict": "PASS_BOUNDED_MILESTONE_C_PRIVATE_FIXTURE",
        },
        "third_party_code_imported": "NO",
    }
