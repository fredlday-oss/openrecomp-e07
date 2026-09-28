#!/usr/bin/env python3
"""Deterministic P18-90 integrated-regression gate.

Runs the read-only Phase-18 corpus audit as a single chain: source-manifest
exactness, evidence closure, stage/next_stage agreement, frozen Phase 1..17
integrity, marker ledger, frontier-digest coherence, and public safety.  Any
divergence fails closed.

P18-90 promotes NO proof marker: FIRST_FRAME_READY stays NO and every Phase-18
claim marker stays NOT_PROVEN.  Historical Phase-17 markers are preserved
verbatim.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase18/src", ".openrecomp-phase17/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p18_contracts_v1 as contract
import p18_regression_v1 as reg
from p18_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P18-90"
NEXT_STAGE = "P18-91"

STAGE_MARKER = "OPENRECOMP_P18_90"
CONSISTENCY_MARKER = "OPENRECOMP_PHASE18_WHOLE_REGRESSION_CONSISTENCY_V1"


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    stale = evidence / "p18_90_tests.json"
    if stale.is_file():
        stale.unlink()

    gate.check("next-stage:declared-constant", NEXT_STAGE == "P18-91")

    # 1. Source manifest exactness.
    manifest = reg.audit_manifest(root)
    write_json(evidence / "manifest_audit.json", manifest)
    assert_public_safe(gate, "manifest_audit", manifest)
    gate.check("manifest:no-parse-errors", not manifest["parse_errors"],
               json.dumps(manifest["parse_errors"], sort_keys=True))
    gate.check("manifest:no-missing-entries", not manifest["missing_entries"],
               json.dumps(manifest["missing_entries"], sort_keys=True))
    gate.check("manifest:no-extra-entries", not manifest["extra_entries"],
               json.dumps(manifest["extra_entries"], sort_keys=True))
    gate.check("manifest:no-duplicates", not manifest["duplicate_entries"],
               json.dumps(manifest["duplicate_entries"], sort_keys=True))
    gate.check("manifest:all-digests-verify", not manifest["digest_mismatches"],
               json.dumps(manifest["digest_mismatches"], sort_keys=True))
    gate.check("manifest:counts-consistent",
               manifest["entry_count"] == manifest["expected_count"]
               and manifest["entry_count"] > 0,
               json.dumps({"expected": manifest["expected_count"],
                           "entries": manifest["entry_count"]}, sort_keys=True))

    # 2. Evidence closure.
    closure = reg.audit_closure(root)
    write_json(evidence / "closure.json", closure)
    assert_public_safe(gate, "closure", closure)
    gate.check("closure:all-stage-dirs-present",
               closure["stages_checked"] == closure["stages_expected"],
               json.dumps({"checked": closure["stages_checked"]}, sort_keys=True))
    for stage in closure["stages"]:
        gate.check(f"closure:{stage['stage']}:documents-present",
                   not stage["missing_documents"],
                   json.dumps(stage["missing_documents"], sort_keys=True))
        gate.check(f"closure:{stage['stage']}:result-schema",
                   stage.get("result_schema") == reg.RESULT_SCHEMA,
                   str(stage.get("result_schema")))
        gate.check(f"closure:{stage['stage']}:result-status-pass",
                   stage.get("result_status") == "PASS",
                   str(stage.get("result_status")))
        gate.check(f"closure:{stage['stage']}:result-stage-agrees",
                   stage.get("result_stage") == stage["stage"],
                   str(stage.get("result_stage")))
        gate.check(f"closure:{stage['stage']}:next-stage-agrees",
                   stage.get("result_next_stage") == stage["declared_next_stage"],
                   json.dumps({"declared": stage["declared_next_stage"],
                               "result": stage.get("result_next_stage")},
                              sort_keys=True))
        gate.check(f"closure:{stage['stage']}:authority-commit",
                   stage.get("authority_commit") == contract.PHASE17_TERMINAL_COMMIT,
                   str(stage.get("authority_commit")))

    # 3. Frozen Phase 1..17 integrity.
    frozen = reg.audit_frozen_phase17(contract.PHASE17_TERMINAL_COMMIT)
    write_json(evidence / "frozen_phase17.json", frozen)
    assert_public_safe(gate, "frozen_phase17", frozen)
    gate.check("frozen:phase1-17-untouched", frozen["untouched"],
               json.dumps({"changed": frozen["changed_paths"][:5],
                           "dirty": frozen["dirty_paths"][:5]}, sort_keys=True))
    gate.check("frozen:tag-resolves-to-terminal", frozen["tag_resolves_to_terminal"])

    # 4. Marker ledger.
    markers = reg.audit_markers(root)
    write_json(evidence / "marker_ledger.json", markers)
    assert_public_safe(gate, "marker_ledger", markers)
    gate.check("markers:no-promotions", not markers["violations"],
               json.dumps(markers["violations"], sort_keys=True))

    # 5. Frontier-digest coherence.
    frontiers = reg.audit_frontier_digests(root)
    write_json(evidence / "frontier_digests.json", frontiers)
    assert_public_safe(gate, "frontier_digests", frontiers)
    gate.check("frontiers:all-digests-coherent", frontiers["all_ok"],
               json.dumps(frontiers["entries"], sort_keys=True))
    for relative, expected in (
            ("P18-04/gpu_command_frontier.json",
             "a009003b644122a011a4a53a9ceeae1d2e4a560a462fc28ef2c3ac9dd4b2bfe9"),
            ("P18-05/dma_frontier.json",
             "f0251b43b8d60ac8c101df71d59cd28441615e1ab58c7036dce98933450fa5c1"),
            ("P18-06/vram_display.json",
             "2848c231c0351638485931e8dfd064abf7ba990d7a9fab178c3730d94e084e5e")):
        gate.check(f"frontiers:consumer-agrees:{relative}",
                   frontiers["consumer_digests"].get(relative) == expected,
                   str(frontiers["consumer_digests"].get(relative)))

    # 5b. Authoritative control-document agreement.
    control = reg.audit_control_documents(root, current_stage=STAGE,
                                         next_stage=NEXT_STAGE)
    write_json(evidence / "control_documents.json", control)
    assert_public_safe(gate, "control_documents", control)
    gate.check("control-docs:present", not control["missing_documents"],
               json.dumps(control["missing_documents"], sort_keys=True))
    gate.check("control-docs:stage-status-agree",
               not control["stage_status_violations"],
               json.dumps(control["stage_status_violations"], sort_keys=True))
    gate.check("control-docs:markers-unpromoted",
               not control["marker_violations"],
               json.dumps(control["marker_violations"], sort_keys=True))
    gate.check("control-docs:next-stage-agree",
               not control["next_stage_violations"],
               json.dumps(control["next_stage_violations"], sort_keys=True))

    # 5c. No stale pre-repair frontier digest survives as authority.
    stale = reg.audit_stale_frontier_digest(root)
    write_json(evidence / "stale_digest.json", stale)
    assert_public_safe(gate, "stale_digest", stale)
    gate.check("stale-digest:absent-from-json-evidence",
               not stale["json_evidence_hits"],
               json.dumps(stale["json_evidence_hits"], sort_keys=True))
    gate.check("stale-digest:unmarked-only-history",
               not stale["control_doc_hits"],
               json.dumps(stale["control_doc_hits"], sort_keys=True))

    # 5d. Downstream revalidation remains valid against repaired P18-04.
    revalidation = reg.audit_revalidation(root)
    write_json(evidence / "revalidation.json", revalidation)
    assert_public_safe(gate, "revalidation", revalidation)
    gate.check("revalidation:p18-07-consumer-matches",
               revalidation["p18_07_consumer_matches"])
    gate.check("revalidation:frontier-sha-files-agree",
               all(revalidation["revalidation_docs"].values()),
               json.dumps(revalidation["revalidation_docs"], sort_keys=True))

    # 6. Public safety.
    public = reg.scan_public_safety(root)
    write_json(evidence / "public_safety.json", public)
    gate.check("public-safety:no-violations", not public["violations"],
               json.dumps(public["violations"][:5], sort_keys=True))
    gate.check("public-safety:prose-reported-separately",
               public["prose_documents_are_controller_authored"],
               json.dumps(public["prose_findings"][:5], sort_keys=True))

    # 7. Negative controls.
    negatives = reg.negative_controls()
    write_json(evidence / "negative_tests.json", negatives)
    assert_public_safe(gate, "negative_tests", negatives)
    for name, value in sorted(negatives.items()):
        if name == "ok":
            continue
        gate.check(f"negative:{name}", bool(value))

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase18-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "authority_commit": contract.PHASE17_TERMINAL_COMMIT,
        "authority_tree": contract.PHASE17_TERMINAL_TREE,
        "manifest_entry_count": manifest["entry_count"],
        "stages_verified": closure["stages_checked"],
        "prior_phase_trees_verified": 17,
        "frontier_digests": frontiers["consumer_digests"],
        "negative_controls_passed": sum(
            1 for name, value in negatives.items() if name != "ok" and value),
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            "OPENRECOMP_P18_01": "PASS",
            "OPENRECOMP_P18_02": "PASS",
            "OPENRECOMP_P18_03": "PASS",
            "OPENRECOMP_P18_04": "PASS",
            "OPENRECOMP_P18_05": "PASS",
            "OPENRECOMP_P18_06": "PASS",
            "OPENRECOMP_P18_07": "PASS",
            STAGE_MARKER: "PASS",
            CONSISTENCY_MARKER: "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
            contract.FIRST_FRAME_READY_MARKER: "NO",
        },
        "promotes_no_proof_marker": True,
        "next_stage": NEXT_STAGE,
    })

    for marker in (contract.BOOTSTRAP_MARKER, "OPENRECOMP_P18_01", "OPENRECOMP_P18_02",
                   "OPENRECOMP_P18_03", "OPENRECOMP_P18_04", "OPENRECOMP_P18_05",
                   "OPENRECOMP_P18_06", "OPENRECOMP_P18_07", STAGE_MARKER,
                   CONSISTENCY_MARKER):
        gate.mark(marker)
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase18/evidence/P18-90"))
