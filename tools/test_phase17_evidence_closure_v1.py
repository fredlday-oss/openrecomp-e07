#!/usr/bin/env python3
"""P17-91 evidence-closure and source-manifest audit gate.

Terminal consistency gate over the committed Phase-17 evidence corpus. It
mechanically audits, failing closed:

  a. source-manifest exactness (every tracked p17_*.py src and
     tools/test_phase17_*_test appears exactly once with a correct digest);
  b. evidence closure (every stage directory carries the schema-required
     documents and a schema-conformant RESULT.json);
  c. dual-run determinism (run1==run2, empty stderr, re-derived digests);
  d. public-safety (private host paths and reconstructive metadata keys);
  e. frozen prior-phase integrity (Phase 1..16 trees unmodified);
  f. marker ledger (protected claim markers un-promoted);
  g. negative controls (tamper cases fail closed).

P17-91 promotes NO proof marker. FIRST_FRAME_READY=NO and the four
NOT_PROVEN markers remain exactly as committed. The audit is additive and
does not modify any existing stage evidence.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".openrecomp-phase17" / "src"))

import p17_evidence_closure_v1 as audit
from p17_contracts_v1 import (FIRST_FRAME_READY_MARKER, FRAME_MARKER,
                              GENERAL_MARKER, INITIALIZATION_MARKER,
                              PLAYABILITY_MARKER)
from p17_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P17-91"
NEXT_STAGE = "P17-99"
BASE_COMMIT = "724d3d4c8ff9a58702d05a5f5fb7aaf503bf5649"
WORKER_BRANCH = "agent/deepseek-phase17-p17-91-r1"
EVIDENCE_CLASS = "PRIVATE_FIXTURE_BOUNDED"

EVIDENCE_ROOT = ROOT / ".openrecomp-phase17" / "evidence"

def _load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    gate.check("next-stage:declared-constant", NEXT_STAGE == "P17-99")

    # 1. Source-manifest exactness.
    manifest_text = (root / audit.MANIFEST_PATH).read_text(encoding="utf-8")
    manifest = audit.audit_manifest(root, manifest_text)
    write_json(evidence / "manifest_audit.json", manifest)
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
    gate.check("manifest:digest-basis-agrees", not manifest["basis_divergences"],
               json.dumps(manifest["basis_divergences"], sort_keys=True))
    gate.check("manifest:counts-consistent",
               manifest["expected_count"] == manifest["entry_count"]
               and manifest["entry_count"] > 0,
               json.dumps({"expected": manifest["expected_count"],
                           "entries": manifest["entry_count"]}, sort_keys=True))
    gate.check("manifest:new-module-registered",
               ".openrecomp-phase17/src/p17_evidence_closure_v1.py"
               in manifest["expected_paths"]
               and "tools/test_phase17_evidence_closure_v1.py"
               in manifest["expected_paths"],
               "new src module and gate present in manifest")

    # 2. Evidence closure.
    closure = audit.audit_evidence_closure(EVIDENCE_ROOT)
    write_json(evidence / "closure.json", closure)
    gate.check("closure:all-stage-dirs-present",
               closure["stages_checked"] == closure["stages_expected"],
               json.dumps({"checked": closure["stages_checked"]}, sort_keys=True))
    for stage in closure["stages"]:
        gate.check(f"closure:{stage['stage']}:documents-present",
                   not stage["missing_documents"],
                   json.dumps(stage["missing_documents"], sort_keys=True))
        gate.check(f"closure:{stage['stage']}:result-schema-conformant",
                   stage["schema_conformant"],
                   json.dumps({"schema": stage["schema"],
                               "class": stage["evidence_class"],
                               "status": stage["status"]}, sort_keys=True))

    # 3. Dual-run determinism.
    determinism = audit.audit_dual_run_determinism(EVIDENCE_ROOT)
    for entry in determinism["stages"]:
        gate.check(f"determinism:{entry['stage']}:run1-equals-run2",
                   entry["run_byte_identical"],
                   json.dumps({"run1": entry["run1_sha256"][:16],
                               "run2": entry["run2_sha256"][:16]}, sort_keys=True))
        gate.check(f"determinism:{entry['stage']}:stderr-empty",
                   entry["stderr_both_empty"],
                   "both stderr files empty")
        gate.check(f"determinism:{entry['stage']}:recorded-digests-match",
                   entry["recorded_digests_match"],
                   json.dumps(entry["recorded_mismatch"], sort_keys=True))
    gate.check("determinism:all-stages", determinism["ok"],
               json.dumps({"stages": determinism["stages_checked"]}, sort_keys=True))

    # 3b. Transcript binding for the one transcript-based stage.
    transcript = audit.audit_transcript_binding(EVIDENCE_ROOT)
    write_json(evidence / "transcript_binding.json", transcript)
    gate.check("transcript:p17-06r-sidecar-matches",
               transcript["P17-06R_sidecar_matches"],
               json.dumps({"sidecar": transcript["P17-06R_sidecar_sha256"],
                           "actual": transcript["P17-06R_transcript_sha256"]},
                          sort_keys=True))
    gate.check("transcript:p17-07r-binding-matches",
               transcript["P17-07R_binding_matches_transcript"],
               json.dumps({"bound": transcript["P17-07R_bound_sha256"]},
                          sort_keys=True))

    # 4. Public-safety scan (control policy rules 11 and 15).
    public_safety = audit.public_safety_scan(EVIDENCE_ROOT)
    write_json(evidence / "public_safety.json", public_safety)
    gate.check("public-safety:no-unallowlisted-hits", public_safety["ok"],
               json.dumps(public_safety["documents_failed"], sort_keys=True))
    gate.check("public-safety:no-forbidden-keys",
               all(not report["forbidden_key_hits"]
                   for report in public_safety["reports"]),
               "no reconstructive metadata keys in any evidence document")
    gate.check("public-safety:scan-covered-evidence",
               public_safety["documents_scanned"] > 0,
               json.dumps({"scanned": public_safety["documents_scanned"]},
                          sort_keys=True))
    gate.check("public-safety:allowlist-is-named-and-bounded",
               len(audit.PUBLIC_SAFETY_ALLOWLIST) <= 8
               and all(entry["rule"] and entry["reason"]
                       for entry in audit.PUBLIC_SAFETY_ALLOWLIST),
               json.dumps([entry["glob"] for entry in audit.PUBLIC_SAFETY_ALLOWLIST],
                          sort_keys=True))

    # 5. Frozen prior-phase integrity (rule 3).
    prior = audit.audit_prior_phase_integrity(root)
    write_json(evidence / "prior_phase_integrity.json", prior)
    gate.check("prior-phase:no-commits-touched-phase1-16",
               not prior["commits_touching_prior_phases"],
               json.dumps(prior["commits_touching_prior_phases"], sort_keys=True))
    gate.check("prior-phase:all-trees-identical-to-baseline",
               all(entry["identical"] for entry in prior["tree_comparisons"]),
               json.dumps([entry["directory"]
                           for entry in prior["tree_comparisons"]
                           if not entry["identical"]], sort_keys=True))
    gate.check("prior-phase:no-dirty-worktree-paths",
               not prior["worktree_dirty_prior_phases"],
               json.dumps(prior["worktree_dirty_prior_phases"], sort_keys=True))
    gate.check("prior-phase:all-sixteen-trees-checked",
               len(prior["tree_comparisons"]) == 16,
               json.dumps({"checked": len(prior["tree_comparisons"])},
                          sort_keys=True))

    # 6. Marker ledger.
    state_text = (root / ".openrecomp-phase17" / "STATE.md").read_text(
        encoding="utf-8")
    queue_text = (root / ".openrecomp-phase17" / "STAGE_QUEUE.md").read_text(
        encoding="utf-8")
    ledger = audit.audit_marker_ledger(EVIDENCE_ROOT, state_text, queue_text)
    write_json(evidence / "marker_ledger.json", ledger)
    gate.check("ledger:no-promoted-markers", not ledger["promoted_markers"],
               json.dumps(ledger["promoted_markers"], sort_keys=True))
    gate.check("ledger:every-stage-checked",
               all(entry["result_present"] for entry in ledger["stages"]),
               json.dumps([entry["stage"] for entry in ledger["stages"]
                           if not entry["result_present"]], sort_keys=True))
    gate.check("ledger:state-declares-protected-markers",
               all(ledger["state_declares"].values()),
               json.dumps(ledger["state_declares"], sort_keys=True))
    gate.check("ledger:queue-declares-protected-markers",
               all(ledger["queue_declares"].values()),
               json.dumps(ledger["queue_declares"], sort_keys=True))

    # 7. Negative controls: the audit detects each tamper class.
    negatives = audit.negative_controls(root, EVIDENCE_ROOT)
    write_json(evidence / "negative_controls.json", negatives)
    for case in negatives["cases"]:
        gate.check(f"negative:{case['case'].replace('_', '-')}",
                   case["detected"], json.dumps(case, sort_keys=True))
    gate.check("negative:all-cases-detected", negatives["ok"],
               json.dumps({"cases": negatives["tamper_case_count"],
                           "detected": negatives["tamper_detected_count"]},
                          sort_keys=True))
    gate.check("negative:minimum-case-coverage",
               negatives["tamper_case_count"] >= 6,
               json.dumps({"cases": negatives["tamper_case_count"]},
                          sort_keys=True))

    # 8. Evidence documents.
    audit_doc = audit.audit_document()
    stage_metadata = {
        "schema": "openrecomp-phase17-stage-metadata-v1",
        "stage": STAGE,
        "status": "PASS",
        "next_stage": NEXT_STAGE,
        "base_commit": BASE_COMMIT,
        "worker_branch": WORKER_BRANCH,
        "resulting_candidate_commit": "PENDING_FINAL_COMMIT",
        "resulting_candidate_commit_resolver": f"git rev-parse {WORKER_BRANCH}",
    }
    next_stage_doc = {
        "schema": "openrecomp-phase17-next-stage-v1",
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "authoritative_sources": [
            "RESULT.json", "closure.json", "manifest_audit.json",
            "public_safety.json", "prior_phase_integrity.json",
            "marker_ledger.json", "negative_controls.json",
            "transcript_binding.json", "stage_metadata.json",
            "next_stage.json", "STATE.md", "STAGE_QUEUE.md",
        ],
    }
    result_doc = {
        "schema": "openrecomp-phase17-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "next_stage": NEXT_STAGE,
        "evidence_class": EVIDENCE_CLASS,
        "base_commit": BASE_COMMIT,
        "worker_branch": WORKER_BRANCH,
        "resulting_candidate_commit": "PENDING_FINAL_COMMIT",
        "resulting_candidate_commit_resolver": f"git rev-parse {WORKER_BRANCH}",
        "proves_nothing_about_emulation": True,
        "manifest_entry_count": manifest["entry_count"],
        "stages_audited": len(audit.STAGE_DIRS),
        "dual_run_stages_audited": len(audit.DUAL_RUN_STAGES),
        "public_safety_documents_scanned": public_safety["documents_scanned"],
        "public_safety_allowlisted_documents": public_safety[
            "allowlisted_documents"],
        "prior_phase_trees_verified": len(prior["tree_comparisons"]),
        "negative_tamper_cases": negatives["tamper_case_count"],
        "negative_tamper_detected": negatives["tamper_detected_count"],
        "public_safety_review_document_findings": [
            finding["document"]
            for finding in public_safety["review_document_findings"]],
        "markers": {
            f"OPENRECOMP_{STAGE.replace('-', '_')}": "PASS",
            audit.MARKER: "PASS",
            INITIALIZATION_MARKER: "NOT_PROVEN",
            FRAME_MARKER: "NOT_PROVEN",
            PLAYABILITY_MARKER: "NOT_PROVEN",
            GENERAL_MARKER: "NOT_PROVEN",
            FIRST_FRAME_READY_MARKER: "NO",
        },
        "proof_boundaries": {
            INITIALIZATION_MARKER: "NOT_PROVEN",
            FRAME_MARKER: "NOT_PROVEN",
            PLAYABILITY_MARKER: "NOT_PROVEN",
            GENERAL_MARKER: "NOT_PROVEN",
            FIRST_FRAME_READY_MARKER: "NO",
        },
        "findings": (
            public_safety["review_document_findings"]
        ),
    }
    write_json(evidence / "audit.json", audit_doc)
    write_json(evidence / "RESULT.json", result_doc)
    write_json(evidence / "next_stage.json", next_stage_doc)
    write_json(evidence / "stage_metadata.json", stage_metadata)

    for name, document in (("RESULT", result_doc),
                           ("next_stage", next_stage_doc),
                           ("stage_metadata", stage_metadata),
                           ("audit", audit_doc),
                           ("manifest_audit", manifest),
                           ("closure", closure),
                           ("public_safety", public_safety),
                           ("prior_phase_integrity", prior),
                           ("marker_ledger", ledger),
                           ("negative_controls", negatives),
                           ("transcript_binding", transcript)):
        assert_public_safe(gate, name, document)

    # 9. Marker claims: this stage promotes no proof marker.
    gate.mark(f"OPENRECOMP_{STAGE.replace('-', '_')}")
    gate.mark(audit.MARKER)
    for marker in (INITIALIZATION_MARKER, FRAME_MARKER, PLAYABILITY_MARKER,
                   GENERAL_MARKER):
        gate.mark(marker, "NOT_PROVEN")
    gate.mark(FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(
        STAGE, body, ".openrecomp-phase17/evidence/P17-91"))

