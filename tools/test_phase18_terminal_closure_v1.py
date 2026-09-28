#!/usr/bin/env python3
"""P18-99 terminal Phase-18 closure gate.

Runs the read-only terminal-closure audit over the complete certified Phase-18
stage chain and emits the canonical Phase-18 terminal marker ONLY if every one
of the twelve audit dimensions passes. Fails closed otherwise: no marker, no
partial credit.

A terminal PASS asserts only that the Phase-18 evidence chain is internally
consistent, reproducible and bound to the frozen Phase-17 authority. It does
NOT promote FIRST_FRAME_READY, the initialization/frame/playability proofs, or
general PS1 compatibility.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase18/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p18_contracts_v1 as contract  # noqa: E402
import p18_terminal_closure_v1 as term  # noqa: E402
from p18_gate_v1 import Gate, assert_public_safe, run_stage, write_json  # noqa: E402

STAGE = "P18-99"
NEXT_STAGE = "NONE"
EVIDENCE_CLASS = "PRIVATE_FIXTURE_BOUNDED"
STAGE_MARKER = "OPENRECOMP_P18_99"

#: The certified chain markers restated by terminal closure (echoed by the
#: gate, exactly as P18-91 echoes its predecessors).
CHAIN_MARKERS = tuple(f"OPENRECOMP_{stage.replace(chr(45), chr(95))}"
                      for stage, _ in term.STAGE_CHAIN) + (STAGE_MARKER,)

PROTECTED = (
    contract.INITIALIZATION_MARKER,
    contract.FRAME_MARKER,
    contract.PLAYABILITY_MARKER,
    contract.GENERAL_MARKER,
)

#: (dimension key, audit-document key, committed document name). The audit
#: document names differ from the dimension labels for two dimensions.
DIMENSION_DOCUMENTS = (
    ("stage_chain", "stage_chain", "stage_chain.json"),
    ("stage_markers", "stage_markers", "stage_markers.json"),
    ("provenance", "provenance", "provenance.json"),
    ("determinism", "determinism", "gate_digests.json"),
    ("prior_phase_integrity", "prior_phase_integrity", "prior_phase_integrity.json"),
    ("manifest_exactness", "manifest_consistency", "manifest_consistency.json"),
    ("marker_ledger", "marker_ledger", "marker_ledger.json"),
    ("frontier_coherence", "frontier_coherence", "frontier_coherence.json"),
    ("public_safety", "public_safety", "public_safety.json"),
    ("control_documents", "control_documents", "control_documents.json"),
    ("head_binding", "head_binding", "head_binding.json"),
    ("negative_controls", "negative_controls", "negative_controls.json"),
)


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    for name in ("RESULT.json", "verdict.json"):
        stale = evidence / name
        if stale.is_file():
            stale.unlink()

    audit = term.audit_document(root)
    write_json(evidence / "terminal_audit.json", audit)

    for dimension, audit_key, document in DIMENSION_DOCUMENTS:
        write_json(evidence / document, audit[audit_key])
        gate.check(f"dimension:{dimension}", bool(audit["dimensions"][dimension]),
                   json.dumps(audit["dimensions"][dimension], sort_keys=True))

    gate.check("dimensions:all-pass", not audit["dimensions_failed"],
               json.dumps(audit["dimensions_failed"], sort_keys=True))
    gate.check("terminal-marker:condition", bool(audit["terminal_marker_emitted"]),
               "all twelve dimensions pass")

    verdict = {
        "schema": "openrecomp-phase18-terminal-verdict-v1",
        "stage": STAGE,
        "phase17_authority_commit": term.PHASE17_COMMIT,
        "phase17_authority_tree": term.PHASE17_TREE,
        "certified_authority_commit": term.P18_91_COMMIT,
        "stage_chain": [stage for stage, _ in term.STAGE_CHAIN],
        "dimensions": audit["dimensions"],
        "dimensions_failed": audit["dimensions_failed"],
        "terminal_marker": term.TERMINAL_MARKER,
        "final_verdict": "PASS_PHASE18_TERMINAL_CLOSURE_EVIDENCE_CHAIN",
        "first_frame_ready": "NO",
        "claim_markers": dict(term.PROTECTED_MARKERS),
        "proof_boundaries": dict(term.PROTECTED_MARKERS),
        "promotes_no_proof_marker": True,
        "proves_nothing_about_emulation": True,
        "phase19_started": "NO",
        "next_stage": NEXT_STAGE,
    }
    write_json(evidence / "verdict.json", verdict)

    result = {
        "schema": "openrecomp-phase18-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": EVIDENCE_CLASS,
        "authority_commit": term.PHASE17_COMMIT,
        "authority_tree": term.PHASE17_TREE,
        "certified_authority_commit": term.P18_91_COMMIT,
        "terminal_marker": term.TERMINAL_MARKER,
        "dimensions_passed": sum(1 for ok in audit["dimensions"].values() if ok),
        "dimensions_total": len(audit["dimensions"]),
        "negative_controls_passed": sum(
            1 for name, value in audit["negative_controls"].items()
            if name != "ok" and value is True),
        "promotes_no_proof_marker": True,
        "proves_nothing_about_emulation": True,
        "markers": {
            STAGE_MARKER: "PASS",
            term.TERMINAL_MARKER: "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
            contract.FIRST_FRAME_READY_MARKER: "NO",
        },
        "next_stage": NEXT_STAGE,
    }
    write_json(evidence / "RESULT.json", result)

    write_json(evidence / "next_stage.json", {
        "schema": "openrecomp-phase18-next-stage-v1",
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "phase19_started": "NO",
        "authoritative_sources": [
            "RESULT.json", "verdict.json", "terminal_audit.json",
            "stage_chain.json", "stage_markers.json", "provenance.json",
            "gate_digests.json", "prior_phase_integrity.json",
            "manifest_consistency.json", "marker_ledger.json",
            "frontier_coherence.json", "public_safety.json",
            "control_documents.json", "head_binding.json",
            "negative_controls.json", "STATE.md", "STAGE_QUEUE.md", "HANDOFF.md",
        ],
    })
    write_json(evidence / "stage_metadata.json", {
        "schema": "openrecomp-phase18-stage-metadata-v1",
        "stage": STAGE,
        "status": "PASS",
        "next_stage": NEXT_STAGE,
        "authority_commit": term.PHASE17_COMMIT,
        "certified_authority_commit": term.P18_91_COMMIT,
        "resulting_candidate_commit": "PENDING_FINAL_COMMIT",
    })

    for name, document in (
        ("RESULT", result), ("verdict", verdict),
        ("stage_chain", audit["stage_chain"]),
        ("stage_markers", audit["stage_markers"]),
        ("provenance", audit["provenance"]),
        ("gate_digests", audit["determinism"]),
        ("prior_phase_integrity", audit["prior_phase_integrity"]),
        ("manifest_consistency", audit["manifest_consistency"]),
        ("marker_ledger", audit["marker_ledger"]),
        ("frontier_coherence", audit["frontier_coherence"]),
        ("public_safety", audit["public_safety"]),
        ("control_documents", audit["control_documents"]),
        ("head_binding", audit["head_binding"]),
        ("negative_controls", audit["negative_controls"]),
    ):
        assert_public_safe(gate, name, document)
    assert_public_safe(gate, "terminal_audit", audit)

    for marker in CHAIN_MARKERS:
        gate.mark(marker)
    gate.mark(term.TERMINAL_MARKER)
    for marker in PROTECTED:
        gate.mark(marker, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase18/evidence/P18-99"))
