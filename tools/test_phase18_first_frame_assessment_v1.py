#!/usr/bin/env python3
"""Deterministic P18-07 first-frame assessment gate.

P18-07 does not execute the guest, inject traffic or render anything. It reads
the committed P18-02..P18-06 evidence read-only and hash-verifies the frozen
frontier documents, evaluates the ordered causal-link chain L1..L7, and applies
the exact promotion rule (FIRST_FRAME_READY=YES iff all links are ESTABLISHED).

Because the GP0/GP1, DMA/OT and VRAM/display frontiers are all UNREACHED, the
honest outcome is FIRST_FRAME_READY=NO with FRAME_PROOF=NOT_PROVEN.  The gate
proves this is a real determination, not a vacuous one, by requiring the
promotion logic to yield YES for a fully satisfied control vector (in the
control namespace only, isolated from the authentic verdict), and to yield NO
for every single-milestone anti-inflation control.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase18/src", ".openrecomp-phase17/src",
              ".openrecomp-phase3/src", ".openrecomp-phase9/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p18_contracts_v1 as contract
import p18_first_frame_assessment_v1 as assess
from p18_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P18-07"
NEXT_STAGE = "P18-90"

STAGE_MARKER = "OPENRECOMP_P18_07"
FRONTIER_MARKER = "OPENRECOMP_PHASE18_FIRST_FRAME_ASSESSMENT"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True).stdout.strip()


def run_authority() -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, ".openrecomp-phase18/src/p18_frozen_phase17_authority_v1.py"],
        cwd=str(ROOT), capture_output=True, text=True)
    ok = (completed.returncode == 0
          and "OPENRECOMP_PHASE18_P17_AUTHORITY_FROZEN=PASS" in completed.stdout)
    return ok, completed.stdout.strip() if not ok else "authority-ok"


def phase17_evidence_untouched() -> tuple[bool, list[str]]:
    changed = git("diff", "--name-only", f"{contract.PHASE17_TERMINAL_COMMIT}..HEAD",
                  "--", *contract.FROZEN_NAMESPACES).splitlines()
    dirty = git("status", "--porcelain", "--", *contract.FROZEN_NAMESPACES).splitlines()
    return (not changed and not dirty), changed + dirty


def _raises(fn, code: str | None = None) -> bool:
    try:
        fn()
        return False
    except assess.FirstFrameAssessmentError as exc:
        return True if code is None else exc.code == code


# --- Negative controls -----------------------------------------------------

def negative_digest_mismatch(evidence: dict[str, Any]) -> bool:
    """A frontier document whose digest does not match is rejected.

    The expected-digest map is temporarily poisoned with a wrong digest for the
    P18-04 frontier; the loader must then fail closed.  The override is restored
    in a finally block so the authentic assessment is never affected.
    """
    original = assess.EXPECTED_FRONTIER_DIGESTS
    try:
        assess.EXPECTED_FRONTIER_DIGESTS = {
            **original,
            "P18-04/gpu_command_frontier.json": "0" * 64,
        }
        return _raises(lambda: assess.load_evidence(),
                       "FRONTIER_DIGEST_MISMATCH")
    finally:
        assess.EXPECTED_FRONTIER_DIGESTS = original


def negative_missing_document(tmp_root: pathlib.Path) -> bool:
    return _raises(lambda: assess.read_document(tmp_root / "does-not-exist.json"),
                   "FRONTIER_EVIDENCE_MISSING")


def negative_unparsable_document(tmp_root: pathlib.Path) -> bool:
    broken = tmp_root / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    return _raises(lambda: assess.read_document(broken),
                   "FRONTIER_EVIDENCE_UNPARSABLE")


def negative_chain_incomplete() -> bool:
    return _raises(lambda: assess.promotion_from_verdicts({"L1": assess.ESTABLISHED}),
                   "PROMOTION_CHAIN_INCOMPLETE")


def negative_link_provenance_missing() -> bool:
    document = {
        "schema": assess.SCHEMA,
        "ledger": {"order": list(assess.LINK_IDS), "authentic_first_frame_ready": "NO",
                   "links": [{"id": link, "verdict": assess.UNREACHED, "evidence": []}
                             for link in assess.LINK_IDS]},
        "first_frame_ready": "NO",
        "promotion_controls": {"control_namespace_isolated": True,
                               "anti_vacuity": {"first_frame_ready": "YES"},
                               "anti_inflation": []},
    }
    return _raises(lambda: assess.validate_assessment(document),
                   "LINK_PROVENANCE_MISSING")


def negative_control_derived_established() -> bool:
    links = []
    for link in assess.LINK_IDS:
        citations = [{"source": "control", "field": "x", "value": 1,
                      "evidence_class": "CONTROL"}]
        verdict = assess.ESTABLISHED if link == "L1" else assess.UNREACHED
        if link == "L1":
            links.append({"id": link, "verdict": verdict, "evidence": citations})
        else:
            links.append({"id": link, "verdict": assess.UNREACHED,
                          "evidence": [{"source": "e", "field": "f", "value": 0,
                                        "evidence_class": "AUTHENTIC"}]})
    document = {
        "schema": assess.SCHEMA,
        "ledger": {"order": list(assess.LINK_IDS), "authentic_first_frame_ready": "NO",
                   "links": links},
        "first_frame_ready": "NO",
        "promotion_controls": {"control_namespace_isolated": True,
                               "anti_vacuity": {"first_frame_ready": "YES"},
                               "anti_inflation": []},
    }
    return _raises(lambda: assess.validate_assessment(document),
                   "LINK_CONTROL_DERIVED_EVIDENCE_REJECTED")


def negative_control_contamination() -> bool:
    """A control-derived YES leaking into the authentic verdict is rejected."""
    document = {
        "schema": assess.SCHEMA,
        "ledger": {"order": list(assess.LINK_IDS),
                   "authentic_first_frame_ready": "YES",
                   "links": [{"id": link, "verdict": assess.ESTABLISHED,
                              "evidence": [{"source": "s", "field": "f", "value": 0,
                                            "evidence_class": "AUTHENTIC"}]}
                             for link in assess.LINK_IDS]},
        "first_frame_ready": "YES",
        "promotion_controls": {"control_namespace_isolated": True,
                               "anti_vacuity": {"first_frame_ready": "YES"},
                               "anti_inflation": []},
    }
    # L1..L7 all ESTABLISHED -> the rule does yield YES, so to test contamination
    # corrupt only the ledger's authentic field.
    document["ledger"]["authentic_first_frame_ready"] = "NO"
    return _raises(lambda: assess.validate_assessment(document),
                   "CONTROL_VERDICT_CONTAMINATION")


def negative_anti_vacuity_cannot_promote() -> bool:
    document = {
        "schema": assess.SCHEMA,
        "ledger": {"order": list(assess.LINK_IDS), "authentic_first_frame_ready": "NO",
                   "links": [{"id": link, "verdict": assess.UNREACHED,
                              "evidence": [{"source": "s", "field": "f", "value": 0,
                                            "evidence_class": "AUTHENTIC"}]}
                             for link in assess.LINK_IDS]},
        "first_frame_ready": "NO",
        "promotion_controls": {"control_namespace_isolated": True,
                               "anti_vacuity": {"first_frame_ready": "NO"},
                               "anti_inflation": []},
    }
    return _raises(lambda: assess.validate_assessment(document), "ANTI_VACUITY_FAILED")


def negative_single_milestone_promotes() -> bool:
    """The real anti-inflation logic must never yield YES for one milestone."""
    for vector in ("first-gp0-write", "first-gpu-dma", "first-vram-mutation"):
        verdicts = {link: assess.NOT_PROVEN for link in assess.LINK_IDS}
        verdicts["L1"] = assess.ESTABLISHED
        verdicts["L5" if "vram" in vector else "L2"] = assess.ESTABLISHED
        if assess.promotion_from_verdicts(verdicts) != "NO":
            return False
    return True


# --- Gate body -------------------------------------------------------------

def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    stale = evidence / "p18_07_tests.json"
    if stale.is_file():
        stale.unlink()
    # Remove any stray artifact a previous control run may have left behind.
    leftover = evidence / "broken.json"
    if leftover.is_file():
        leftover.unlink()

    ok, out = run_authority()
    gate.check("authority:phase17-frozen", ok, out)
    untouched, offenders = phase17_evidence_untouched()
    gate.check("frozen:phase1-17-untouched", untouched, ",".join(offenders[:5]))

    loaded = assess.load_evidence(root)
    gate.check("evidence:all-present",
               all(key in loaded for key, _ in assess.EVIDENCE_FILES),
               json.dumps([rel for _, rel in assess.EVIDENCE_FILES], sort_keys=True))

    for relative, expected in assess.EXPECTED_FRONTIER_DIGESTS.items():
        key = assess._key_for(relative)
        gate.check(f"frontier-digest:{relative}",
                   loaded[key + "_sha256"] == expected, loaded[key + "_sha256"])

    gate.check("p18-04:frontier-unreached",
               loaded["gpu_frontier"]["frontier_reached"] is False
               and loaded["gpu_frontier"]["gp0_write_count"] == 0
               and loaded["gpu_frontier"]["gp1_write_count"] == 0)
    gate.check("p18-05:frontier-unreached",
               loaded["dma_frontier"]["dma_reached"] is False
               and loaded["dma_frontier"]["dma_access_count"] == 0)
    gate.check("p18-06:frontier-unreached",
               loaded["vram"]["vram_frontier_reached"] is False
               and loaded["vram"]["first_frame_ready"] == "NO")

    document, doc_sha = assess.build_assessment(loaded)
    assess.validate_assessment(document)
    gate.check("assessment:schema", document["schema"] == assess.SCHEMA)
    gate.check("assessment:validated", True, doc_sha)

    links = document["ledger"]["links"]
    gate.check("ledger:ordered", [l["id"] for l in links] == list(assess.LINK_IDS),
               json.dumps([l["id"] for l in links]))
    gate.check("ledger:l1-established",
               document["ledger"]["links"][0]["verdict"] == assess.ESTABLISHED,
               json.dumps({l["id"]: l["verdict"] for l in links}, sort_keys=True))
    gate.check("ledger:l2-unreached", links[1]["verdict"] == assess.UNREACHED)
    gate.check("ledger:l3-unreached", links[2]["verdict"] == assess.UNREACHED)
    gate.check("ledger:l4-not-proven", links[3]["verdict"] == assess.NOT_PROVEN)
    gate.check("ledger:l5-unreached", links[4]["verdict"] == assess.UNREACHED)
    gate.check("ledger:l6-unreached", links[5]["verdict"] == assess.UNREACHED)
    gate.check("ledger:l7-not-proven", links[6]["verdict"] == assess.NOT_PROVEN)
    gate.check("ledger:every-link-cites-evidence",
               all(link["evidence"] for link in links))

    gate.check("promotion:first-frame-not-ready",
               document["first_frame_ready"] == "NO", document["first_frame_ready"])
    gate.check("promotion:rule-exact",
               document["first_frame_rule"] == "YES iff all of L1..L7 are ESTABLISHED")

    controls = document["promotion_controls"]
    gate.check("control:anti-vacuity-promotes",
               controls["anti_vacuity"]["first_frame_ready"] == "YES",
               json.dumps(controls["anti_vacuity"], sort_keys=True))
    gate.check("control:anti-inflation-all-no",
               all(v["first_frame_ready"] == "NO" for v in controls["anti_inflation"]),
               json.dumps([v["vector"] for v in controls["anti_inflation"]]))
    gate.check("control:namespace-isolated", controls["control_namespace_isolated"])

    scratch = pathlib.Path(tempfile.mkdtemp(prefix="p18-07-negative-"))
    try:
        missing_ok = negative_missing_document(scratch)
        unparsable_ok = negative_unparsable_document(scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    gate.check("negative:digest-mismatch", negative_digest_mismatch(loaded))
    gate.check("negative:missing-document", missing_ok)
    gate.check("negative:unparsable-document", unparsable_ok)
    gate.check("negative:chain-incomplete", negative_chain_incomplete())
    gate.check("negative:link-provenance-missing", negative_link_provenance_missing())
    gate.check("negative:control-derived-established",
               negative_control_derived_established())
    gate.check("negative:control-contamination", negative_control_contamination())
    gate.check("negative:anti-vacuity-cannot-promote",
               negative_anti_vacuity_cannot_promote())
    gate.check("negative:single-milestone-not-promoted",
               negative_single_milestone_promotes())

    (evidence / "first_frame_assessment.json").write_bytes(
        assess.assessment_bytes(document))
    (evidence / "first_frame_assessment.sha256").write_text(
        f"{doc_sha}  first_frame_assessment.json\n", encoding="utf-8", newline="\n")
    assert_public_safe(gate, "first_frame_assessment", document)

    ledger_doc = {
        "schema": assess.LEDGER_SCHEMA,
        "stage": STAGE,
        "order": document["ledger"]["order"],
        "links": document["ledger"]["links"],
        "authentic_first_frame_ready": document["ledger"]["authentic_first_frame_ready"],
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "causal_link_ledger.json", ledger_doc)
    assert_public_safe(gate, "causal_link_ledger", ledger_doc)

    write_json(evidence / "promotion_controls.json", controls)
    assert_public_safe(gate, "promotion_controls", controls)

    negative_doc = {
        "schema": "openrecomp-phase18-negative-tests-v1",
        "stage": STAGE,
        "frontier_digest_mismatch_rejected": negative_digest_mismatch(loaded),
        "missing_document_rejected": missing_ok,
        "unparsable_document_rejected": unparsable_ok,
        "promotion_chain_incomplete_rejected": negative_chain_incomplete(),
        "link_provenance_missing_rejected": negative_link_provenance_missing(),
        "link_control_derived_evidence_rejected": negative_control_derived_established(),
        "control_verdict_contamination_rejected": negative_control_contamination(),
        "anti_vacuity_cannot_promote_rejected": negative_anti_vacuity_cannot_promote(),
        "single_milestone_never_promotes": negative_single_milestone_promotes(),
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "negative_tests.json", negative_doc)
    assert_public_safe(gate, "negative_tests", negative_doc)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase18-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "authority_commit": contract.PHASE17_TERMINAL_COMMIT,
        "authority_tree": contract.PHASE17_TERMINAL_TREE,
        "first_frame_ready": document["first_frame_ready"],
        "link_verdicts": {link["id"]: link["verdict"] for link in links},
        "frontier_digests": document["frontier_digests"],
        "assessment_sha256": doc_sha,
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            "OPENRECOMP_P18_01": "PASS",
            "OPENRECOMP_P18_02": "PASS",
            "OPENRECOMP_P18_03": "PASS",
            "OPENRECOMP_P18_04": "PASS",
            "OPENRECOMP_P18_05": "PASS",
            "OPENRECOMP_P18_06": "PASS",
            STAGE_MARKER: "PASS",
            FRONTIER_MARKER: "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
            contract.FIRST_FRAME_READY_MARKER: "NO",
        },
        "next_stage": NEXT_STAGE,
    })

    for marker in (contract.BOOTSTRAP_MARKER, "OPENRECOMP_P18_01", "OPENRECOMP_P18_02",
                   "OPENRECOMP_P18_03", "OPENRECOMP_P18_04", "OPENRECOMP_P18_05",
                   "OPENRECOMP_P18_06", STAGE_MARKER, FRONTIER_MARKER):
        gate.mark(marker)
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase18/evidence/P18-07"))
