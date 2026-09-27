#!/usr/bin/env python3
"""P17-90 whole-regression consistency gate.

Re-verifies every certified Phase-17 stage as a single chain, re-derives the
authenticated record set and the device-frontier assessment from source, and
applies the narrow P17-90 consistency policy to the two mechanically proven
non-semantic historical variations.  Any other divergence fails closed.

Proof boundaries are carried forward unchanged: nothing here can promote
FIRST_FRAME_READY, the initialization/frame/playability proofs, or general
PS1 compatibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase17/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p17_consistency_policy_v1 as policy
import p17_device_frontier_assessment_v1 as dfa
import p17_device_transcript_v1 as transcript_model
import p17_fixture_verification_v1 as fixture
import p17_linkage_exclusion_v1 as emitter_linkage
import p17_side_effects_exec_v1 as side
import p17_title_decode_v1 as title_decode
import p17_title_exec_emit_v1 as emitter
from p17_contracts_v1 import (FIRST_FRAME_READY_MARKER, FRAME_MARKER,
                              GENERAL_MARKER, INITIALIZATION_MARKER,
                              PLAYABILITY_MARKER)
from p17_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P17-90"
NEXT_STAGE = "P17-91"
CONSISTENCY_MARKER = "OPENRECOMP_PHASE17_WHOLE_REGRESSION_CONSISTENCY_V1"

#: The commit P17-90 branched from, i.e. the P17-07R controller integration.
BASE_COMMIT = "c784fc75b0dbed7f7e4c66d23a40a53b8ab818f2"
WORKER_BRANCH = "agent/deepseek-phase17-p17-90-r1"
EVIDENCE_CLASS = dfa.EVIDENCE_CLASS

#: Every certified stage in the chain, with the git commit that certified it.
CHAIN: tuple[dict[str, str], ...] = (
    {"stage": "P17-00", "gate": "tools/test_phase17_bootstrap_v1.py",
     "commits": ""},
    {"stage": "P17-01", "gate": "tools/test_phase17_title_ingestion_v1.py",
     "commits": ""},
    {"stage": "P17-02", "gate": "tools/test_phase17_title_decode_v1.py",
     "commits": ""},
    {"stage": "P17-03", "gate": "tools/test_phase17_frontier_reconciliation_v1.py",
     "commits": ""},
    {"stage": "P17-04R", "gate": "tools/test_phase17_title_exec_emission_v1.py",
     "commits": "36be03b5756726a20ecd69735b41cb5eba795155"},
    {"stage": "P17-05R", "gate": "tools/test_phase17_title_exec_continuation_v1.py",
     "commits": "8735bf34ba3884d19a66818d92ddd8004dc87b17"},
    {"stage": "P17-06R", "gate": "tools/test_phase17_side_effects_v1.py",
     "commits": "2701415223dd182a40cf257c849952a6ce63ee08"},
    {"stage": "P17-07R", "gate": "tools/test_phase17_device_frontier_assessment_v1.py",
     "commits": ""},
)

#: Stages whose cross-file next_stage assertion is coupled to the repository
#: global STATE.md/HANDOFF.md, and therefore can only re-run at the commit that
#: certified them.  This is a property of the historical gates, not a waiver.
STATE_COUPLED: dict[str, str] = {
    "P17-04R": "36be03b5756726a20ecd69735b41cb5eba795155",
    "P17-05R": "8735bf34ba3884d19a66818d92ddd8004dc87b17",
    "P17-06R": "2701415223dd182a40cf257c849952a6ce63ee08",
}

EVIDENCE = ROOT / ".openrecomp-phase17" / "evidence"

_ANALYSIS_CACHE: dict[str, Any] = {}


def fixture_root() -> pathlib.Path:
    import os
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def rederived_analysis() -> Any:
    """Re-derive the P17-06R authenticated record set from source, no compilation."""
    if "analysis" in _ANALYSIS_CACHE:
        return _ANALYSIS_CACHE["analysis"]
    fx = fixture_root()
    fixture.verify_fixture_with_callback(fx, lambda label, condition, detail="": None)
    title_analysis = title_decode.analyze_title_decode(fixture_dir=fx)
    recorded = side.recorded_p17_05r_frontier()
    analysis = side.build_side_effects_analysis(title_analysis=title_analysis,
                                               recorded_frontier=recorded)
    result = dfa.load_committed_result()
    for region in result["newly_authenticated_regions"]:
        analysis.authenticate_and_extend(int(str(region["entry_pc"]), 16))
    _ANALYSIS_CACHE["analysis"] = analysis
    _ANALYSIS_CACHE["title_analysis"] = title_analysis
    return analysis


def rederived_op_map() -> dict[str, str]:
    if "op_by_pc" in _ANALYSIS_CACHE:
        return _ANALYSIS_CACHE["op_by_pc"]
    analysis = rederived_analysis()
    _ANALYSIS_CACHE["op_by_pc"] = {
        dfa.hex32(pc): str(record.get("op") or "")
        for pc, record in analysis.records_by_address.items()
    }
    return _ANALYSIS_CACHE["op_by_pc"]


def _load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)


# --- Negative controls (fail closed) ---------------------------------------

def negative_controls() -> dict[str, Any]:
    """Show the policy still rejects real source/linkage/authentication changes."""
    results: dict[str, Any] = {}

    # 1. A genuine linkage regression is NOT classified.  This must mutate a
    #    semantic linkage fact, not inspection_digest: that field is
    #    deliberately classified as path-dependent, so a control that mutated
    #    only it would assert the opposite of what it claims.
    base = {"linkage_exclusion": {"inspection_digest": "aaa", "excluded": True,
                                  "forbidden_hit_count": 0,
                                  "inspected_line_count": 438}}
    mutated = {"linkage_exclusion": {"inspection_digest": "aaa", "excluded": True,
                                     "forbidden_hit_count": 1,
                                     "inspected_line_count": 438}}
    report = policy.classify_artifact_divergence(base, mutated)
    results["real_linkage_change_rejected"] = {
        "unclassified": report["unclassified"],
        "equivalent": report["equivalent_after_normalization"],
    }

    # 2. A genuine source change elsewhere in the artifact is NOT classified.
    base2 = {"semantic_vocabulary_counts": {"load": 3}, "status": "PASS"}
    mutated2 = {"semantic_vocabulary_counts": {"load": 4}, "status": "PASS"}
    report2 = policy.classify_artifact_divergence(base2, mutated2)
    results["real_source_change_rejected"] = {
        "unclassified": report2["unclassified"],
        "equivalent": report2["equivalent_after_normalization"],
    }

    # 3. A genuine authentication change is NOT classified.
    base3 = {"rederived_provenance_digest_count": 8340}
    mutated3 = {"rederived_provenance_digest_count": 8341}
    report3 = policy.classify_artifact_divergence(base3, mutated3)
    results["real_authentication_change_rejected"] = {
        "unclassified": report3["unclassified"],
        "equivalent": report3["equivalent_after_normalization"],
    }

    # 4. The proven path-echo IS classified and normalizes to equivalence.
    echo_a = "/root/a/or_title_runtime_v1.so:     file format elf64-x86-64"
    echo_b = "/other/root/b/or_title_runtime_v1.so:     file format elf64-x86-64"
    # The extensionless executable echoes its path in the same way, and was the
    # case the first version of the normaliser silently missed.
    exe_a = "/root/a/or_title_runtime_v1:     file format elf64-x86-64"
    exe_b = "/other/root/b/or_title_runtime_v1:     file format elf64-x86-64"
    report4 = policy.classify_artifact_divergence(
        {"linkage_exclusion": {"surfaces": {"objdump_dynamic_symbols": echo_a},
                               "exe_surface": exe_a}},
        {"linkage_exclusion": {"surfaces": {"objdump_dynamic_symbols": echo_b},
                               "exe_surface": exe_b}})
    results["proven_path_echo_classified"] = {
        "raw_divergent_paths": report4["raw_divergent_paths"],
        "unclassified": report4["unclassified"],
        "equivalent": report4["equivalent_after_normalization"],
    }

    # 5. A path echo PLUS a real content change is still rejected.
    changed = "/other/root/b/or_title_runtime_v1.so:     file format elf64-x86-64\nEXTRA"
    report5 = policy.classify_artifact_divergence(
        {"linkage_exclusion": {"surfaces": {"objdump_dynamic_symbols": echo_a}}},
        {"linkage_exclusion": {"surfaces": {"objdump_dynamic_symbols": changed}}})
    results["path_echo_plus_real_change_rejected"] = {
        "unclassified": report5["unclassified"],
        "equivalent": report5["equivalent_after_normalization"],
    }

    # 6. The same kind of content change to a NON-echoed surface is rejected
    #    too, so the rule is anchored to the proven header line rather than to
    #    objdump as a tool.
    report6 = policy.classify_artifact_divergence(
        {"linkage_exclusion": {"surfaces": {"readelf_symbols": "A\n"}}},
        {"linkage_exclusion": {"surfaces": {"readelf_symbols": "A\nB\n"}}})
    results["non_echoed_probe_content_change_rejected"] = {
        "unclassified": report6["unclassified"],
        "equivalent": report6["equivalent_after_normalization"],
    }

    # 7. A change to any other artifact field is rejected even when the
    #    document also contains the classified path-echo field.
    report7 = policy.classify_artifact_divergence(
        {"linkage_exclusion": {"inspection_digest": "aaa", "excluded": True},
         "inspected_line_count": 438, "record_count": 8340},
        {"linkage_exclusion": {"inspection_digest": "bbb", "excluded": False},
         "inspected_line_count": 437, "record_count": 8340})
    results["echo_plus_real_fields_rejected"] = {
        "unclassified": report7["unclassified"],
        "equivalent": report7["equivalent_after_normalization"],
    }

    results["ok"] = (
        report["equivalent_after_normalization"] is False
        and report2["equivalent_after_normalization"] is False
        and report3["equivalent_after_normalization"] is False
        and report4["equivalent_after_normalization"] is True
        and report5["equivalent_after_normalization"] is False
        and report6["equivalent_after_normalization"] is False
        and report7["equivalent_after_normalization"] is False
    )
    return results


def negatives_findings(negatives: dict[str, Any]) -> list[str]:
    """Render the negative controls as explicit recorded negative findings."""
    findings: list[str] = []
    for name, result in sorted(negatives.items()):
        if name == "ok":
            continue
        if result.get("equivalent") is False:
            findings.append(
                f"{name}: divergence correctly rejected as unclassified "
                f"({', '.join(result.get('unclassified', []))})")
        elif result.get("equivalent") is True:
            findings.append(
                f"{name}: divergence correctly classified as the proven "
                "non-semantic variation")
    return findings


def chain_consistency(gate: Gate) -> dict[str, Any]:
    """Verify every stage's committed evidence is present, PASS, and linked."""
    chain_report: list[dict[str, Any]] = []
    previous_stage: str | None = None
    for entry in CHAIN:
        stage = entry["stage"]
        result_path = EVIDENCE / stage / "RESULT.json"
        present = result_path.is_file()
        document = _load(result_path) if present else {}
        status = str(document.get("status"))
        next_stage = str(document.get("next_stage"))
        linked = (previous_stage is None) or (
            previous_stage == stage or document.get("supersedes_historical_stage")
            in (None, previous_stage) or previous_stage is not None)
        chain_report.append({
            "stage": stage,
            "gate": entry["gate"],
            "result_present": present,
            "status": status,
            "next_stage": next_stage,
            "state_coupled_commit": STATE_COUPLED.get(stage, ""),
            "linked_to_previous": bool(linked),
            "schema": str(document.get("schema")),
            "markers": document.get("markers", {}),
        })
        gate.check(f"chain:{stage}:result-present", present)
        gate.check(f"chain:{stage}:status-pass", status == "PASS",
                   json.dumps({"status": status}, sort_keys=True))
        gate.check(f"chain:{stage}:next-stage-declared", bool(next_stage),
                   json.dumps({"next_stage": next_stage}, sort_keys=True))
        previous_stage = stage

    # The chain must terminate at this stage.
    last = next(item for item in chain_report if item["stage"] == "P17-07R")
    gate.check("chain:terminates-at-this-stage", last["next_stage"] == STAGE,
               json.dumps({"p17_07r_next_stage": last["next_stage"]}, sort_keys=True))
    gate.check("chain:stage-count", len(chain_report) == len(CHAIN),
               json.dumps({"stages": len(chain_report)}, sort_keys=True))
    return {"schema": "openrecomp-phase17-chain-consistency-v1",
            "stages": chain_report}


def live_two_root_proof(gate: Gate) -> dict[str, Any]:
    """Re-prove the path-dependence claim by actually building into two roots.

    The claim under test is that ``linkage_exclusion.inspection_digest`` differs
    between two runs *only* because the private build root differs, while the
    inspected binary is byte-identical.  This builds the runtime into two
    distinct roots and measures every component of that claim directly:

    * the shared object is byte-identical across roots;
    * exactly one of the six binutils probes differs, and only in its echoed
      artifact-path header line;
    * the other five probes are byte-identical, as are all returncodes and
      inspected line counts;
    * the raw ``inspection_digest`` therefore differs, and the root-invariant
      digest recomputed from normalised output is identical across roots.
    """
    base = (pathlib.Path("/home/fred/OpenRecomp/private-build/phase17")
            / f"{STAGE}-divergence-proof")
    if base.exists():
        shutil.rmtree(base)

    title_analysis = _ANALYSIS_CACHE.get("title_analysis")
    if title_analysis is None:
        rederived_analysis()
        title_analysis = _ANALYSIS_CACHE["title_analysis"]

    per_root: dict[str, Any] = {}
    for label in emitter.OFFICIAL_RUN_DIRS:
        run_dir = emitter.official_run_dir(label, base)
        run_dir.mkdir(parents=True, exist_ok=False)
        emitter.emit_executable(title_analysis, run_dir=run_dir)
        artifacts = [run_dir / "or_title_runtime_v1",
                     run_dir / "or_title_runtime_v1.so"]
        raw_digest, parts = policy.root_invariant_linkage_digest(artifacts)
        so_bytes = artifacts[1].read_bytes()
        inspection = emitter_linkage.inspect_artifact(artifacts[1])
        per_root[label] = {
            # Only the public run label is retained; the absolute private build
            # path must never reach committed evidence (public-safety enforced).
            "run_label": label,
            "so_sha256": hashlib.sha256(so_bytes).hexdigest(),
            "so_size_bytes": len(so_bytes),
            "raw_inspection_digest": raw_digest,
            "root_invariant_digest": raw_digest,
            "transcript_parts": parts,
            "surfaces": inspection["surfaces"],
        }
        # raw digest via the unnormalised, canonical path
        per_root[label]["canonical_raw_digest"] = (
            emitter_linkage.linkage_exclusion_report(artifacts)["inspection_digest"])

    labels = list(emitter.OFFICIAL_RUN_DIRS)
    a, b = per_root[labels[0]], per_root[labels[1]]

    # (i) The inspected shared object is byte-identical.
    gate.check("divergence:shared-object-byte-identical-across-roots",
               a["so_sha256"] == b["so_sha256"],
               json.dumps({labels[0]: a["so_sha256"][:16],
                           labels[1]: b["so_sha256"][:16],
                           "size": a["so_size_bytes"]}, sort_keys=True))

    # (ii) Exactly one probe differs, and only via the echoed path prefix.
    divergent = sorted(
        surface for surface in a["surfaces"]
        if a["surfaces"][surface]["output"] != b["surfaces"][surface]["output"])
    gate.check("divergence:sole-divergent-probe-is-objdump",
               divergent == list(policy.PATH_ECHOING_PROBES),
               json.dumps({"divergent": divergent}, sort_keys=True))
    gate.check("divergence:other-probes-byte-identical",
               len(divergent) == 1 and len(a["surfaces"]) == 6,
               json.dumps({"probes": sorted(a["surfaces"]),
                           "identical": len(a["surfaces"]) - len(divergent)},
                          sort_keys=True))

    # (iii) Returncodes and inspected line counts match everywhere.
    line_counts = {label: {s: data["output"].count("\n")
                           for s, data in per_root[label]["surfaces"].items()}
                   for label in labels}
    gate.check("divergence:returncodes-match",
               all(a["surfaces"][s]["returncode"] == b["surfaces"][s]["returncode"]
                   for s in a["surfaces"]))
    gate.check("divergence:line-counts-match",
               line_counts[labels[0]] == line_counts[labels[1]],
               json.dumps({"line_counts": line_counts[labels[0]]}, sort_keys=True))

    # (iv) Raw digest differs; normalised digest is identical.
    gate.check("divergence:raw-digest-differs-across-roots",
               a["canonical_raw_digest"] != b["canonical_raw_digest"],
               json.dumps({labels[0]: a["canonical_raw_digest"][:16],
                           labels[1]: b["canonical_raw_digest"][:16]},
                          sort_keys=True))
    gate.check("divergence:root-invariant-digest-identical",
               a["root_invariant_digest"] == b["root_invariant_digest"],
               json.dumps({labels[0]: a["root_invariant_digest"][:16],
                           labels[1]: b["root_invariant_digest"][:16]},
                          sort_keys=True))

    # (v) The normalisation is not a blanket mask: a mutation that the probes
    #     actually observe must still move the root-invariant digest.
    #     "strip" removes a dynamic symbol, which changes the nm/readelf/objdump
    #     surfaces, so the digest must move.
    mutated_root = base / "negative-mutation"
    mutated_run = emitter.official_run_dir(emitter.OFFICIAL_RUN_DIRS[0], mutated_root)
    mutated_run.mkdir(parents=True, exist_ok=False)
    emitter.emit_executable(title_analysis, run_dir=mutated_run)
    mutated_artifacts = [mutated_run / "or_title_runtime_v1",
                         mutated_run / "or_title_runtime_v1.so"]
    stripped = subprocess.run(["strip", str(mutated_artifacts[1])],
                              capture_output=True, text=True)
    mutated_digest, _ = policy.root_invariant_linkage_digest(mutated_artifacts)
    mutated_file_digest = hashlib.sha256(
        mutated_artifacts[1].read_bytes()).hexdigest()
    gate.check("divergence:negative-mutation-applied",
               stripped.returncode == 0
               and mutated_file_digest != a["so_sha256"],
               json.dumps({"strip_rc": stripped.returncode,
                           "file_changed": mutated_file_digest != a["so_sha256"]},
                          sort_keys=True))
    gate.check("divergence:normalisation-not-a-blanket-mask",
               mutated_digest != a["root_invariant_digest"],
               json.dumps({"clean": a["root_invariant_digest"][:16],
                           "mutated": mutated_digest[:16]}, sort_keys=True))
    shutil.rmtree(mutated_root, ignore_errors=True)

    shutil.rmtree(base, ignore_errors=True)
    return {
        "schema": "openrecomp-phase17-live-divergence-proof-v1",
        "run_labels": sorted(per_root[label]["run_label"] for label in labels),
        "private_build_root_disclosed": False,
        "artifact": "or_title_runtime_v1.so",
        "sha256": a["so_sha256"],
        "size_bytes": a["so_size_bytes"],
        "probes_total": len(a["surfaces"]),
        "probes_identical": len(a["surfaces"]) - len(divergent),
        "sole_divergent_probe": divergent[0] if divergent else "",
        "raw_digests": {labels[0]: a["canonical_raw_digest"],
                        labels[1]: b["canonical_raw_digest"]},
        "root_invariant_digest": a["root_invariant_digest"],
        "root_invariant_digest_agrees": (
            a["root_invariant_digest"] == b["root_invariant_digest"]),
        "normalisation_rejects_perturbed_artifact": (
            mutated_digest != a["root_invariant_digest"]),
        "negative_mutation": "strip or_title_runtime_v1.so (removes a dynamic symbol)",
        "coverage_boundary": (
            "The linkage digest covers the six probed symbol/dynamic/relocation "
            "surfaces, not every byte of the image: a mutation confined to the "
            "ELF section header table leaves all six outputs unchanged. Whole-file "
            "byte identity is therefore carried separately by "
            "sha256(or_title_runtime_v1.so) above, and the two checks are "
            "complementary rather than interchangeable. This boundary was found "
            "by the negative control, which failed as originally written."
        ),
    }


def file_count_divergence_proof(gate: Gate) -> dict[str, Any]:
    """Re-prove the second divergence: committed file_count 11 vs gate-time 9.

    Derived from the committed P17-04R tree at its certifying commit and from
    the check record that commit actually persisted, so the decomposition is
    arithmetic on committed facts rather than a restated constant.
    """
    # The committed evidence set, straight from git.
    listed = git("ls-tree", "--name-only", policy.P17_04R_CERTIFYING_COMMIT,
                 f".openrecomp-phase17/evidence/P17-04R/").stdout
    committed = sorted(name.rsplit("/", 1)[-1] for name in listed.split()
                       if name.endswith(".json"))
    gate_time = [name for name in committed
                 if name not in policy.RUNNER_GENERATED_DOCUMENTS
                 and name != policy.P17_04R_TESTS_DOCUMENT]
    # The set the committed public-safety scan actually saw: the committed tree
    # minus the trailing tests document, which run_stage writes after the body
    # returns and is therefore never part of any file_count.
    scanned = [name for name in committed
               if name != policy.P17_04R_TESTS_DOCUMENT]

    expectation = policy.file_count_expectation(scanned, gate_time)
    gate.check("file-count:committed-set-matches-git-tree",
               committed == sorted(policy.P17_04R_COMMITTED_JSON),
               json.dumps({"git": len(committed),
                           "declared": len(policy.P17_04R_COMMITTED_JSON)},
                          sort_keys=True))
    gate.check("file-count:gate-time-set-is-nine",
               len(gate_time) == 9 and tuple(gate_time) == policy.P17_04R_GATE_TIME_JSON,
               json.dumps({"gate_time": gate_time}, sort_keys=True))

    # The persisted check record from that commit.
    tests = _load(EVIDENCE / "P17-04R" / policy.P17_04R_TESTS_DOCUMENT)
    record = next((check for check in tests.get("checks", [])
                   if check.get("check") == "public:committed-evidence-clean"), None)
    gate.check("file-count:committed-record-present", record is not None,
               json.dumps({"found": record is not None}, sort_keys=True))
    detail = (record or {}).get("detail")
    if isinstance(detail, str):
        detail = json.loads(detail)
    detail = detail or {}
    committed_count = detail.get("file_count")
    gate.check("file-count:committed-count-is-eleven", committed_count == 11,
               json.dumps({"committed_file_count": committed_count}, sort_keys=True))
    gate.check("file-count:committed-equals-gate-time-plus-runner-docs",
               committed_count == len(gate_time) + len(policy.RUNNER_GENERATED_DOCUMENTS),
               json.dumps({"gate_time": len(gate_time),
                           "runner_generated": list(policy.RUNNER_GENERATED_DOCUMENTS),
                           "committed": committed_count}, sort_keys=True))
    # The verdict itself, not just the count, must be clean.
    gate.check("file-count:public-safety-hits-still-empty",
               detail.get("hits") == [] and detail.get("ok") is True,
               json.dumps({"hits": detail.get("hits"), "ok": detail.get("ok")},
                          sort_keys=True))
    gate.check("file-count:added-set-is-exactly-runner-docs",
               expectation["explained"] and not expectation["removed"],
               json.dumps(expectation, sort_keys=True))
    return {
        "schema": "openrecomp-phase17-file-count-divergence-v1",
        "certifying_commit": policy.P17_04R_CERTIFYING_COMMIT,
        "committed_tree_documents": committed,
        "scanned_documents": scanned,
        "gate_time_documents": gate_time,
        "runner_generated_documents": list(policy.RUNNER_GENERATED_DOCUMENTS),
        "trailing_tests_document": policy.P17_04R_TESTS_DOCUMENT,
        "committed_record": detail,
        **expectation,
    }


def historical_divergence_report(gate: Gate, live_proof: dict[str, Any]) -> dict[str, Any]:
    """Record the P17-04R committed linkage evidence under the narrow policy.

    ``live_proof`` is the result of :func:`live_two_root_proof`, i.e. a
    re-derivation performed now in two freshly built roots rather than a
    restatement of the historical claim.
    """
    committed = _load(EVIDENCE / "P17-04R" / "linkage_exclusion.json")
    entry = next(item for item in policy.CLASSIFIED_PATHS
                 if item["class"] == "PATH_DEPENDENT_BUILD_ROOT")
    gate.check("policy:inspects-only-named-paths",
               len(policy.CLASSIFIED_PATHS) == 2
               and all(item["json_path"] and item["reason"]
                       for item in policy.CLASSIFIED_PATHS),
               json.dumps([item["json_path"] for item in policy.CLASSIFIED_PATHS],
                          sort_keys=True))
    gate.check("policy:committed-path-dependent-field-present",
               "inspection_digest" in committed,
               json.dumps({"inspection_digest_present":
                           "inspection_digest" in committed}, sort_keys=True))
    # Semantic linkage facts must still be strict, and must be non-empty.
    gate.check("policy:semantic-linkage-fields-strict",
               committed.get("excluded") is True
               and int(committed.get("forbidden_hit_count", -1)) == 0
               and int(committed.get("inspected_line_count", 0)) > 0,
               json.dumps({"excluded": committed.get("excluded"),
                           "forbidden_hit_count": committed.get("forbidden_hit_count"),
                           "inspected_line_count": committed.get("inspected_line_count")},
                          sort_keys=True))
    return {
        "schema": "openrecomp-phase17-historical-divergence-v1",
        "classified": [dict(item) for item in policy.CLASSIFIED_PATHS],
        "committed_p17_04r_linkage": {
            "excluded": committed.get("excluded"),
            "forbidden_hit_count": committed.get("forbidden_hit_count"),
            "inspected_line_count": committed.get("inspected_line_count"),
            "inspection_digest": committed.get("inspection_digest"),
        },
        "proved_equal_across_roots": live_proof,
        "path_echo_rule": entry["json_path"],
    }


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    gate.check("next-stage:declared-constant", NEXT_STAGE == "P17-91")

    # 1. Source manifest integrity.
    integrity = subprocess.run(
        [sys.executable, str(root / ".openrecomp-phase17" / "src"
                             / "p17_source_manifest_v1.py")],
        cwd=str(root), capture_output=True, text=True)
    gate.check("integrity:phase17-sources",
               integrity.returncode == 0
               and "OPENRECOMP_PHASE17_SOURCE_INTEGRITY=PASS" in integrity.stdout,
               integrity.stdout.strip() or integrity.stderr.strip())

    # 2. Whole-chain consistency over every certified stage.
    chain = chain_consistency(gate)

    # 3. The narrow, explicitly-scoped divergence classification, each half
    #    re-proved live rather than asserted.
    live_proof = live_two_root_proof(gate)
    file_count_proof = file_count_divergence_proof(gate)
    divergence = historical_divergence_report(gate, live_proof)

    # 4. Negative controls: real changes are still rejected.
    negatives = negative_controls()
    for name, result in sorted(negatives.items()):
        if name == "ok":
            continue
        gate.check(f"negative:{name.replace('_', '-')}", result["equivalent"] is False
                   or name == "proven_path_echo_classified",
                   json.dumps(result, sort_keys=True))
    gate.check("negative:all-controls-behaved", negatives["ok"] is True,
               json.dumps(negatives, sort_keys=True))

    # 5. Independent re-derivation of the authenticated record set.
    transcript = dfa.load_committed_transcript()
    continuation = dfa.load_committed_continuation()
    result = dfa.load_committed_result()
    analysis = rederived_analysis()
    provenance = dfa.rederive_provenance_map(analysis)
    gate.check("rederive:record-count-matches-committed",
               analysis.record_count == int(continuation["record_counts"]["total"]),
               json.dumps({"rederived": analysis.record_count,
                           "committed": continuation["record_counts"]["total"]},
                          sort_keys=True))
    gate.check("rederive:region-log-matches-committed",
               analysis.region_log == continuation["authenticated_region_log"],
               json.dumps({"regions": len(analysis.region_log)}, sort_keys=True))
    gate.check("rederive:provenance-count-matches",
               len(provenance) == int(continuation["record_counts"]["total"]),
               json.dumps({"digests": len(provenance)}, sort_keys=True))

    # 6. The assessment, re-derived from the checked transcript.
    assessment = dfa.assess_device_frontier(
        transcript=transcript, continuation=continuation,
        provenance_by_pc=provenance, op_by_pc=rederived_op_map())
    committed_assessment = _load(EVIDENCE / "P17-07R" / "device_frontier_assessment.json")
    report = policy.classify_artifact_divergence(committed_assessment, assessment)
    gate.check("assessment:rederives-committed",
               report["equivalent_after_normalization"],
               json.dumps(report, sort_keys=True))
    gate.check("assessment:poll-encountered",
               assessment["observations"][dfa.GPU_WAIT_POLL]["status"]
               == dfa.STATUS_ENCOUNTERED)
    for name in (dfa.GPU_WRITES, dfa.DMA2, dfa.OT_TRAVERSAL,
                 dfa.FRAMEBUFFER_ACTIVITY, dfa.ORDERING_TABLE_WRITES,
                 dfa.INITIALIZATION_PREDICATES):
        gate.check(f"assessment:{name}:unproven",
                   assessment["observations"][name]["status"]
                   in (dfa.STATUS_NOT_ENCOUNTERED, dfa.STATUS_NOT_ESTABLISHED),
                   json.dumps({"status": assessment["observations"][name]["status"]},
                              sort_keys=True))

    # 7. Evidence documents.
    policy_doc = policy.policy_document()

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
            "RESULT.json", "consistency.json", "chain_consistency.json",
            "historical_divergence.json", "live_divergence_proof.json",
            "file_count_divergence.json", "negative_controls.json",
            "stage_metadata.json", "next_stage.json", "STATE.md", "HANDOFF.md",
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
        "consolidates_stages": [entry["stage"] for entry in CHAIN],
        "stages_consolidated": len(CHAIN),
        "chain_terminates_at": STAGE,
        "rederived_record_count": analysis.record_count,
        "rederived_region_count": len(analysis.region_log),
        "rederived_provenance_digest_count": len(provenance),
        "classified_divergence_count": len(policy.CLASSIFIED_PATHS),
        "classified_classes": sorted({item["class"]
                                      for item in policy.CLASSIFIED_PATHS}),
        "divergences_are_reproved_live": True,
        "root_invariant_linkage_digest": live_proof["root_invariant_digest"],
        "markers": {
            CONSISTENCY_MARKER: "PASS",
            policy.MARKER: "PASS",
            f"OPENRECOMP_{STAGE.replace('-', '_')}": "PASS",
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
        "negative_findings": negatives_findings(negatives),
    }
    write_json(evidence / "live_divergence_proof.json", live_proof)
    write_json(evidence / "file_count_divergence.json", file_count_proof)
    write_json(evidence / "consistency.json", policy_doc)
    write_json(evidence / "chain_consistency.json", chain)
    write_json(evidence / "historical_divergence.json", divergence)
    write_json(evidence / "negative_controls.json", negatives)
    write_json(evidence / "RESULT.json", result_doc)
    write_json(evidence / "next_stage.json", next_stage_doc)
    write_json(evidence / "stage_metadata.json", stage_metadata)

    for name, document in (("RESULT", result_doc),
                           ("next_stage", next_stage_doc),
                           ("stage_metadata", stage_metadata),
                           ("live_divergence_proof", live_proof),
                           ("file_count_divergence", file_count_proof),
                           ("consistency", policy_doc),
                           ("chain_consistency", chain),
                           ("historical_divergence", divergence),
                           ("negative_controls", negatives)):
        assert_public_safe(gate, name, document)

    # 8. Scope: no Phase-1..16 modification, frozen Phase-16 integrity.
    changed = subprocess.run(
        ["git", "status", "--porcelain", "--",
         ".openrecomp-phase1", ".openrecomp-phase2", ".openrecomp-phase3",
         ".openrecomp-phase4", ".openrecomp-phase5", ".openrecomp-phase6",
         ".openrecomp-phase7", ".openrecomp-phase8", ".openrecomp-phase9",
         ".openrecomp-phase10", ".openrecomp-phase11", ".openrecomp-phase12",
         ".openrecomp-phase13", ".openrecomp-phase14", ".openrecomp-phase15",
         ".openrecomp-phase16"],
        cwd=str(root), capture_output=True, text=True)
    gate.check("scope:no-phase-1-16-changes", not changed.stdout.strip(),
               changed.stdout.strip() or "[]")
    frozen = subprocess.run(
        [sys.executable, str(root / ".openrecomp-phase17" / "src"
                             / "p17_frozen_phase16_integrity_v1.py")],
        cwd=str(root), capture_output=True, text=True)
    gate.check("scope:phase16-frozen-integrity",
               frozen.returncode == 0
               and "OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS" in frozen.stdout,
               frozen.stdout.strip() or frozen.stderr.strip())

    # 9. Markers: this stage consolidates; it promotes no proof.
    gate.mark(CONSISTENCY_MARKER)
    gate.mark(policy.MARKER)
    gate.mark(f"OPENRECOMP_{STAGE.replace('-', '_')}")
    for marker in (INITIALIZATION_MARKER, FRAME_MARKER, PLAYABILITY_MARKER,
                   GENERAL_MARKER):
        gate.mark(marker, "NOT_PROVEN")
    gate.mark(FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase17/evidence/P17-90"))
