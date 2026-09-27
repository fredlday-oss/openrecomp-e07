#!/usr/bin/env python3
"""P17-99 terminal Phase-17 closure gate.

The terminal Phase-17 verdict. It re-establishes, failing closed, that the
complete Phase-17 chain is internally consistent and terminally closed:

  1. stage-chain closure (every chained stage PASS with its required marker,
     and the next_stage links form one unbroken chain);
  2. prior-phase integrity (Phase 1..16 trees byte-identical to the frozen
     Phase-16 baseline; no Phase-17 commit touched them);
  3. certified provenance chain (each certifying commit resolves and is an
     ancestor of the certified controller authority);
  4. source-manifest exactness (re-derived from git ls-files);
  5. marker ledger (protected claim markers un-promoted everywhere);
  6. REVIEW_REQUIRED terminal consistency (the historical stop is superseded
     and no stale required-next-action remains);
  7. terminal HEAD/tree binding (exact and internally consistent);
  8. marker syntax cleanliness;
  9. public safety (private host paths, reconstructive keys) over the corpus;
 10. cited terminal evidence re-verified by digest;
 11. negative controls (tamper cases fail closed).

P17-99 promotes NO proof marker. FIRST_FRAME_READY stays NO and the four
claim markers stay NOT_PROVEN. A terminal PASS here does not promote any
broader claim.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".openrecomp-phase17" / "src"))

import p17_evidence_closure_v1 as closure_audit  # noqa: E402
import p17_terminal_closure_v1 as term  # noqa: E402
from p17_contracts_v1 import (FIRST_FRAME_READY_MARKER, FRAME_MARKER,  # noqa: E402
                              GENERAL_MARKER, INITIALIZATION_MARKER,
                              PLAYABILITY_MARKER)
from p17_gate_v1 import Gate, assert_public_safe, run_stage, write_json  # noqa: E402

STAGE = "P17-99"
NEXT_STAGE = "NONE"
EVIDENCE_CLASS = "PRIVATE_FIXTURE_BOUNDED"

EVIDENCE_ROOT = ROOT / ".openrecomp-phase17" / "evidence"
CONTROL_ROOT = ROOT / ".openrecomp-phase17"

#: The gate runs while its own evidence directory is being (re)written, so it
#: excludes that directory from the corpus scan -- exactly the reason P17-91
#: excluded its own. P17-99 audits the committed prior-stage corpus.
SCAN_EXCLUDE_DIRS = ("P17-99",)

#: Terminal evidence documents re-verified by digest at gate time.
P17_07R_TRANSCRIPT_BINDING = EVIDENCE_ROOT / "P17-07R" / "transcript_binding.json"
P17_06R_TRANSCRIPT = EVIDENCE_ROOT / "P17-06R" / "transcript.json"


def _load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*args: str) -> str:
    import subprocess
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True).stdout.strip()


# --- negative controls -----------------------------------------------------

def negative_controls(root: pathlib.Path) -> dict[str, Any]:
    """Tamper cases proving every terminal check fails closed."""
    results: list[dict[str, Any]] = []

    def add(name: str, detected: bool, detail: str) -> None:
        results.append({"case": name, "detected": bool(detected),
                        "detail": detail})

    # 1. Stage-chain: a chained stage missing its RESULT must be detected.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = pathlib.Path(tmp)
        for stage in term.STAGE_CHAIN:
            d = tmp_root / stage
            d.mkdir()
            (d / "RESULT.json").write_text(json.dumps({
                "status": "PASS", "stage": stage,
                "markers": {m: "PASS" for o, m in term.STAGE_MARKERS if o == stage},
                "next_stage": "NEXT",
            }), encoding="utf-8")
        (tmp_root / "P17-90" / "RESULT.json").unlink()
        report = term.audit_stage_chain(tmp_root)
        add("stage_chain_missing_stage", report["ok"] is False,
            "one chained stage RESULT removed")

    # 2. Stage-chain: a stage whose status is not PASS must be detected.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = pathlib.Path(tmp)
        for stage in term.STAGE_CHAIN:
            d = tmp_root / stage
            d.mkdir()
            (d / "RESULT.json").write_text(json.dumps({
                "status": "PASS", "stage": stage,
                "markers": {m: "PASS" for o, m in term.STAGE_MARKERS if o == stage},
                "next_stage": "NEXT",
            }), encoding="utf-8")
        doc = _load(tmp_root / "P17-05R" / "RESULT.json")
        doc["status"] = "FAIL"
        (tmp_root / "P17-05R" / "RESULT.json").write_text(
            json.dumps(doc), encoding="utf-8")
        report = term.audit_stage_chain(tmp_root)
        add("stage_chain_non_pass_status", report["ok"] is False,
            "one chained stage status set to FAIL")

    # 3. Marker ledger: a protected marker promoted in a synthetic corpus.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = pathlib.Path(tmp)
        for stage in term.EVIDENCE_STAGE_DIRS:
            d = tmp_root / stage
            d.mkdir()
            (d / "RESULT.json").write_text(json.dumps({
                "markers": dict(term.PROTECTED_MARKERS)}), encoding="utf-8")
        promoted = _load(tmp_root / "P17-00" / "RESULT.json")
        promoted["markers"]["OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF"] = "PASS"
        (tmp_root / "P17-00" / "RESULT.json").write_text(
            json.dumps(promoted), encoding="utf-8")
        report = term.audit_marker_ledger(tmp_root, "", "", "")
        add("promoted_protected_marker", report["ok"] is False,
            f"promoted_count={len(report['promoted_markers'])}")

    # 4. REVIEW_REQUIRED: a stale required-next-action must be detected.
    stale = ("P17-90 was independently reviewed and integrated. "
             "P17-91 was independently reviewed and integrated. "
             "The required next action is human review and redesign.")
    report = term.audit_review_required(stale)
    add("stale_review_required_action", report["ok"] is False,
        "historical required-next-action still present")

    # 5. Source manifest: a corrupted digest must be detected.
    manifest_text = (root / term.MANIFEST_PATH).read_text(encoding="utf-8")
    lines = manifest_text.splitlines()
    for index, line in enumerate(lines):
        if " *" in line:
            digest, rest = line.split(" *", 1)
            bad = ("0" if digest[0] != "0" else "1") + digest[1:]
            lines[index] = bad + " *" + rest
            break
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = pathlib.Path(tmp)
        fake = tmp_root / term.MANIFEST_PATH
        fake.parent.mkdir(parents=True, exist_ok=True)
        fake.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # Re-run the real audit against a root whose manifest is corrupted but
        # whose tracked sources are the same as the live tree, by pointing the
        # audit at a root that carries the corrupted manifest copy.
        report = term.audit_manifest_consistency(root, manifest_override="\n".join(lines) + "\n")
    add("corrupted_manifest_digest", report["ok"] is False,
        f"digest_mismatches={len(report['digest_mismatches'])}")

    # 6. Provenance chain: a commit that is not an ancestor of the base.
    report = term.audit_provenance_chain(root,
                                         base_commit=term.PHASE16_BASELINE_COMMIT)
    add("provenance_not_ancestor", report["ok"] is False,
        "certified commits are not ancestors of the Phase-16 baseline")

    # 7. Terminal binding: an unresolvable HEAD/tree must be detected.
    report = term.audit_terminal_binding(root, "0" * 40, "0" * 40)
    add("unresolvable_terminal_binding", report["ok"] is False,
        "synthetic zero HEAD/tree rejected")

    # 8. Marker syntax: a multi-equals marker must be detected.
    report = term.audit_marker_syntax(
        {"synthetic": "OPENRECOMP_PHASE17_TERMINAL_V1=NOT_PROVEN=PASS\n"})
    add("promoted_marker_syntax", report["ok"] is False,
        f"problems={len(report['problems'])}")

    # 9. Public safety: an injected private host path must be detected.
    injected = closure_audit.scan_document(
        {"schema": "x", "note": "see /home/intruder/secret/path for detail"},
        "P17-99/injected.json")
    add("fabricated_private_host_path", injected["ok"] is False,
        f"unallowlisted_path_hit_count="
        f"{injected['unallowlisted_path_hit_count']}")

    # 10. Prior-phase integrity: a baseline tree comparison that cannot be
    #     resolved must fail closed.
    report = term.audit_prior_phase_integrity(
        root, baseline="0000000000000000000000000000000000000000")
    add("unresolvable_prior_phase_baseline", report["ok"] is False,
        "all sixteen tree comparisons unresolved")

    tamper = [entry for entry in results]
    return {
        "schema": "openrecomp-phase17-terminal-negative-controls-v1",
        "cases": results,
        "tamper_case_count": len(tamper),
        "tamper_detected_count": sum(1 for entry in tamper if entry["detected"]),
        "ok": all(entry["detected"] for entry in tamper),
    }


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    closure_audit.SELF_EVIDENCE_DIR = "P17-99"

    head = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")

    # 1. Stage-chain closure.
    chain = term.audit_stage_chain(EVIDENCE_ROOT)
    write_json(evidence / "stage_chain.json", chain)
    gate.check("chain:all-stages-pass", chain["ok"],
               json.dumps([entry["stage"] for entry in chain["stages"]
                           if not entry["ok"]], sort_keys=True))
    gate.check("chain:ten-stages", chain["chain_length"] == 10,
               json.dumps({"length": chain["chain_length"]}, sort_keys=True))
    for entry in chain["stages"]:
        gate.check(f"chain:{entry['stage']}:result-pass", entry["ok"],
                   json.dumps(entry["required_markers"], sort_keys=True))

    # 2. Prior-phase integrity.
    prior = term.audit_prior_phase_integrity(root)
    write_json(evidence / "prior_phase_integrity.json", prior)
    gate.check("prior-phase:no-commits-touched-phase1-16",
               not prior["commits_touching_prior_phases"],
               json.dumps(prior["commits_touching_prior_phases"], sort_keys=True))
    gate.check("prior-phase:all-sixteen-trees-identical",
               all(entry["identical"] for entry in prior["tree_comparisons"]),
               json.dumps([entry["directory"] for entry in prior["tree_comparisons"]
                           if not entry["identical"]], sort_keys=True))
    gate.check("prior-phase:no-dirty-prior-phase-paths",
               not prior["worktree_dirty_prior_phases"],
               json.dumps(prior["worktree_dirty_prior_phases"], sort_keys=True))

    # 3. Certified provenance chain.
    provenance = term.audit_provenance_chain(root)
    write_json(evidence / "provenance_chain.json", provenance)
    gate.check("provenance:all-certified-commits-ancestors", provenance["ok"],
               json.dumps([entry["stage"] for entry in provenance["certified_stages"]
                           if not entry["ok"]], sort_keys=True))

    # 4. Source manifest consistency.
    manifest = term.audit_manifest_consistency(root)
    write_json(evidence / "manifest_consistency.json", manifest)
    gate.check("manifest:exact", manifest["ok"],
               json.dumps({"expected": manifest["expected_count"],
                           "entries": manifest["entry_count"]}, sort_keys=True))
    gate.check("manifest:terminal-module-registered",
               ".openrecomp-phase17/src/p17_terminal_closure_v1.py"
               in set(_manifest_paths(root))
               and "tools/test_phase17_terminal_closure_v1.py"
               in set(_manifest_paths(root)),
               "terminal module and gate tracked")

    # 5. Marker ledger.
    state_text = (CONTROL_ROOT / "STATE.md").read_text(encoding="utf-8")
    queue_text = (CONTROL_ROOT / "STAGE_QUEUE.md").read_text(encoding="utf-8")
    review_text = (CONTROL_ROOT / "REVIEW_REQUIRED.md").read_text(encoding="utf-8")
    ledger = term.audit_marker_ledger(EVIDENCE_ROOT, state_text, queue_text,
                                      review_text)
    write_json(evidence / "marker_ledger.json", ledger)
    gate.check("ledger:no-promoted-markers", not ledger["promoted_markers"],
               json.dumps(ledger["promoted_markers"], sort_keys=True))
    gate.check("ledger:state-declares-protected-markers",
               all(ledger["state_declares"].values()),
               json.dumps(ledger["state_declares"], sort_keys=True))
    gate.check("ledger:queue-declares-protected-markers",
               all(ledger["queue_declares"].values()),
               json.dumps(ledger["queue_declares"], sort_keys=True))

    # 6. REVIEW_REQUIRED terminal consistency.
    review = term.audit_review_required(review_text)
    write_json(evidence / "review_required.json", review)
    gate.check("review-required:historical-stop-superseded", review["ok"],
               json.dumps(review, sort_keys=True))

    # 7. Terminal binding.
    binding = term.audit_terminal_binding(root, head, tree)
    write_json(evidence / "terminal_binding.json", binding)
    gate.check("binding:certified-authority-exact", binding["ok"],
               json.dumps({"base": binding["base_commit"],
                           "base_tree": binding["base_tree"]},
                          sort_keys=True))

    # 8. Marker syntax cleanliness over STATE/STAGE_QUEUE and stage transcripts.
    syntax_docs: dict[str, str] = {
        "STATE.md": state_text, "STAGE_QUEUE.md": queue_text,
        "REVIEW_REQUIRED.md": review_text,
    }
    for stage in term.EVIDENCE_STAGE_DIRS:
        run1 = EVIDENCE_ROOT / stage / "run1.txt"
        if run1.is_file():
            syntax_docs[f"{stage}/run1.txt"] = run1.read_text(encoding="utf-8")
    syntax = term.audit_marker_syntax(syntax_docs)
    write_json(evidence / "marker_syntax.json", syntax)
    gate.check("marker-syntax:clean", syntax["ok"],
               json.dumps(syntax["problems"][:3], sort_keys=True))

    # 9. Public safety over the committed corpus.
    # public_safety_scan excludes the module-level SELF_EVIDENCE_DIR, which is
    # set to "P17-99" at the top of body(); the gate audits the committed
    # prior-stage corpus, not its own in-flight output.
    safety = closure_audit.public_safety_scan(EVIDENCE_ROOT)
    write_json(evidence / "public_safety.json", safety)
    gate.check("public-safety:no-unallowlisted-hits", safety["ok"],
               json.dumps(safety["documents_failed"], sort_keys=True))
    gate.check("public-safety:no-forbidden-keys",
               all(not report["forbidden_key_hits"] for report in safety["reports"]),
               "no reconstructive metadata keys")
    gate.check("public-safety:review-documents-clean",
               not safety["review_document_findings"],
               json.dumps([finding["document"]
                           for finding in safety["review_document_findings"]],
                          sort_keys=True))
    gate.check("public-safety:scan-covered-corpus",
               safety["documents_scanned"] > 100,
               json.dumps({"scanned": safety["documents_scanned"]},
                          sort_keys=True))

    # 10. Cited terminal evidence re-verified by digest.
    binding_doc = _load(P17_07R_TRANSCRIPT_BINDING)
    transcript_bytes = P17_06R_TRANSCRIPT.read_bytes()
    transcript_sha = sha256_bytes(transcript_bytes)
    gate.check("terminal-evidence:p17-06r-transcript-digest",
               transcript_sha == binding_doc.get("transcript_sha256")
               and transcript_sha == "d7e222c87726748ced23dd60c2b1ba138625227c984dac587be6a5761695fd3a",
               "P17-06R transcript digest re-derived and matched")
    gate.check("terminal-evidence:p17-07r-transcript-binding",
               binding_doc.get("transcript_sha256") == transcript_sha
               and int(binding_doc.get("rederived_provenance_digest_count", 0)) == 8340,
               "P17-07R binding matches the transcript and 8340 digests")
    gate.check("terminal-evidence:p17-91-closure-marker",
               _load(EVIDENCE_ROOT / "P17-91" / "RESULT.json")["markers"]
               .get("OPENRECOMP_PHASE17_EVIDENCE_CLOSURE_V1") == "PASS",
               "P17-91 closure marker PASS")
    gate.check("terminal-evidence:p17-90-regression-marker",
               _load(EVIDENCE_ROOT / "P17-90" / "RESULT.json")["markers"]
               .get("OPENRECOMP_PHASE17_WHOLE_REGRESSION_CONSISTENCY_V1") == "PASS",
               "P17-90 whole-regression marker PASS")

    # 11. Negative controls.
    negatives = negative_controls(root)
    write_json(evidence / "negative_controls.json", negatives)
    gate.check("negative:all-cases-detected", negatives["ok"],
               json.dumps({"cases": negatives["tamper_case_count"],
                           "detected": negatives["tamper_detected_count"]},
                          sort_keys=True))
    gate.check("negative:minimum-case-coverage",
               negatives["tamper_case_count"] >= 10,
               json.dumps({"cases": negatives["tamper_case_count"]},
                          sort_keys=True))

    # 12. Terminal verdict document.
    verdict = {
        "schema": "openrecomp-phase17-terminal-verdict-v1",
        "stage": STAGE,
        "phase16_base_commit": term.PHASE16_BASELINE_COMMIT,
        "certified_authority_commit": term.BASE_COMMIT,
        "certified_authority_tree": term.BASE_TREE,
        "stage_chain": list(term.STAGE_CHAIN),
        "stage_results": {stage.replace("-", "_") + "_RESULT": "PASS"
                          for stage in term.STAGE_CHAIN},
        "stage_markers": {marker: "PASS" for _, marker in term.STAGE_MARKERS},
        "claim_markers": dict(term.PROTECTED_MARKERS),
        "proof_boundaries": dict(term.PROTECTED_MARKERS),
        "terminal_marker": term.MARKER,
        "terminal_stage_marker": term.STAGE_MARKER,
        "final_verdict": "PASS_PHASE17_TERMINAL_CLOSURE_BOUNDED_DEVICE_FRONTIER",
        "runtime_conclusion": (
            "Bounded checked device frontier dominated by a zero-returning "
            "GPUSTAT wait-poll; 1586 of 1590 recorded device events are repeated "
            "GPUSTAT reads returning zero under ZERO_FILL_RECORDED. No frame, "
            "initialization, playability or general compatibility claim is "
            "promoted."
        ),
        "proves_nothing_about_emulation": True,
        "promotes_no_proof_marker": True,
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
        "fail_closed_discipline": "STRICT_NO_SUPPRESSION",
        "phase18_started": "NO",
        "next_stage": "NONE",
    }
    write_json(evidence / "verdict.json", verdict)

    result = {
        "schema": "openrecomp-phase17-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": EVIDENCE_CLASS,
        "next_stage": NEXT_STAGE,
        "base_commit": term.BASE_COMMIT,
        "certified_authority_commit": term.BASE_COMMIT,
        "certified_authority_tree": term.BASE_TREE,
        "stages_verified": len(term.STAGE_CHAIN),
        "prior_phase_trees_verified": len(prior["tree_comparisons"]),
        "manifest_entry_count": manifest["entry_count"],
        "public_safety_documents_scanned": safety["documents_scanned"],
        "negative_tamper_cases": negatives["tamper_case_count"],
        "negative_tamper_detected": negatives["tamper_detected_count"],
        "proves_nothing_about_emulation": True,
        "promotes_no_proof_marker": True,
        "markers": {
            term.STAGE_MARKER: "PASS",
            term.MARKER: "PASS",
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
        "final_verdict": verdict["final_verdict"],
        "phase18_started": "NO",
    }
    write_json(evidence / "RESULT.json", result)

    next_stage_doc = {
        "schema": "openrecomp-phase17-next-stage-v1",
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "phase18_started": "NO",
        "authoritative_sources": [
            "RESULT.json", "verdict.json", "stage_chain.json",
            "prior_phase_integrity.json", "provenance_chain.json",
            "manifest_consistency.json", "marker_ledger.json",
            "review_required.json", "terminal_binding.json",
            "marker_syntax.json", "public_safety.json",
            "negative_controls.json", "stage_metadata.json",
            "next_stage.json", "STATE.md", "HANDOFF.md", "STAGE_QUEUE.md",
        ],
    }
    stage_metadata = {
        "schema": "openrecomp-phase17-stage-metadata-v1",
        "stage": STAGE,
        "status": "PASS",
        "next_stage": NEXT_STAGE,
        "base_commit": term.BASE_COMMIT,
        "worker_branch": "agent/deepseek-phase17-p17-99-r1",
        "resulting_candidate_commit": "PENDING_FINAL_COMMIT",
        "resulting_candidate_commit_resolver":
            "git rev-parse agent/deepseek-phase17-p17-99-r1",
    }
    write_json(evidence / "next_stage.json", next_stage_doc)
    write_json(evidence / "stage_metadata.json", stage_metadata)
    write_json(evidence / "terminal_audit.json", term.audit_document())

    for name, document in (("RESULT", result), ("verdict", verdict),
                           ("stage_chain", chain), ("prior_phase_integrity", prior),
                           ("provenance_chain", provenance),
                           ("manifest_consistency", manifest),
                           ("marker_ledger", ledger), ("review_required", review),
                           ("terminal_binding", binding), ("marker_syntax", syntax),
                           ("public_safety", safety),
                           ("negative_controls", negatives),
                           ("next_stage", next_stage_doc),
                           ("stage_metadata", stage_metadata)):
        assert_public_safe(gate, name, document)

    # Terminal marker and preserved proof boundaries.
    gate.mark(term.STAGE_MARKER)
    gate.mark(term.MARKER)
    for marker in (INITIALIZATION_MARKER, FRAME_MARKER, PLAYABILITY_MARKER,
                   GENERAL_MARKER):
        gate.mark(marker, "NOT_PROVEN")
    gate.mark(FIRST_FRAME_READY_MARKER, "NO")


def _manifest_paths(root: pathlib.Path) -> list[str]:
    import subprocess
    listing = subprocess.run(["git", "ls-files", ".openrecomp-phase17/src", "tools"],
                             cwd=str(root), capture_output=True, text=True)
    return [line for line in listing.stdout.splitlines() if line]


if __name__ == "__main__":
    raise SystemExit(run_stage(
        STAGE, body, ".openrecomp-phase17/evidence/P17-99"))
