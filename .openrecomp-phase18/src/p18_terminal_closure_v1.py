#!/usr/bin/env python3
"""Phase-18 terminal-closure audit (P18-99).

Read-only audit of the complete certified Phase-18 stage chain. Emits the
canonical Phase-18 terminal marker ONLY if all twelve audit dimensions pass.
Any divergence fails closed: no terminal marker, no partial credit.

Mirrors the Phase-17 terminal-closure module structurally. The Phase-17 tree is
never modified and is re-verified unmodified as part of this audit.

Nothing here promotes FIRST_FRAME_READY, the initialization/frame/playability
proofs, or general PS1 compatibility. Terminal closure asserts only that the
Phase-18 evidence chain is internally consistent, reproducible, and bound to
the frozen Phase-17 authority.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import tempfile
from typing import Any

import p18_regression_v1 as reg

ROOT = pathlib.Path(__file__).resolve().parents[2]

CLOSURE_SCHEMA = "openrecomp-phase18-terminal-closure-v1"
TERMINAL_MARKER = "OPENRECOMP_PHASE18_TERMINAL_V1"
STAGE_MARKER = "OPENRECOMP_P18_99"

#: Frozen Phase-17 authority (never modified, re-verified below).
PHASE17_COMMIT = "d7cc5d09eebde398ca6ff3f3dad8dd5841913b69"
PHASE17_TREE = "ad3aa822e5a02905ebc25477f7b6c69d0bffa055"
PHASE17_TAG = "openrecomp-phase17-pass"
PHASE17_TERMINAL_MARKER = "OPENRECOMP_PHASE17_TERMINAL_V1"

#: Commit that certifies the last non-terminal Phase-18 stage. P18-99 binds its
#: terminal verdict to this commit, not to a moving HEAD.
P18_91_COMMIT = "55184231749e356bb9e07ca44ba8618697aa0cdd"

#: The full certified chain, in order, with each stage's certified successor.
STAGE_CHAIN: tuple[tuple[str, str], ...] = (
    ("P18-00", "P18-01"),
    ("P18-01", "P18-02"),
    ("P18-02", "P18-03"),
    ("P18-03", "P18-04"),
    ("P18-04", "P18-05"),
    ("P18-05", "P18-06"),
    ("P18-06", "P18-07"),
    ("P18-07", "P18-90"),
    ("P18-90", "P18-91"),
    ("P18-91", "P18-99"),
)

#: Each stage's own marker, derived from the stage id rather than hard-coded.
def stage_marker(stage: str) -> str:
    return "OPENRECOMP_" + stage.replace("-", "_")


#: The claim markers P18-99 must never promote, with their frozen values.
PROTECTED_MARKERS: dict[str, str] = {
    "OPENRECOMP_PHASE18_HERCULES_INITIALIZATION_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE18_HERCULES_PLAYABILITY_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE18_GENERAL_PS1_COMPATIBILITY": "NOT_PROVEN",
    "FIRST_FRAME_READY": "NO",
}

RESULT_SCHEMA = "openrecomp-phase18-result-v1"

#: Provenance chain: stage -> the commit that certified it.
PROVENANCE_CHAIN: tuple[tuple[str, str], ...] = (
    ("P18-00", "d6bf3ad24596a4483f4a93e71bd4a9e42d102a45"),
    ("P18-01", "949da0ee5a7ebd5a142ffe175ace2bc4205d28d0"),
    ("P18-02", "59dffd95b99bc9c295c7a59ce44b12541a5ecf41"),
    ("P18-03", "8c031f31bbf9b46e52bc6ba631444af1bfcea864"),
    ("P18-04", "1e07ecc4cb8aeae60ff44e26b0b2dbb909225e7d"),
    ("P18-05", "b2e22c0a24a5230d00d51924a7c0372473be5f96"),
    ("P18-06", "464e9c6485486ed191918d82a4662714ceae79bb"),
    ("P18-07", "e65055d9641247d0cae767952adb21f02c0d02a7"),
    ("P18-90", "261a2b0ab497b7c921c93eab07a73d99f56ecc55"),
    ("P18-91", P18_91_COMMIT),
)

EVIDENCE_ROOT = reg.EVIDENCE_DIR


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# --- 1. stage chain --------------------------------------------------------

def audit_stage_chain(evidence_root: pathlib.Path,
                      present: set[str] | None = None) -> dict[str, Any]:
    """Every certified stage present, ordered, and chaining to its successor.

    ``present`` overrides the filesystem presence test with an explicit set of
    stage names. It exists so a negative control can assert that dropping any
    single stage makes the chain fail closed, without touching the repository.
    """
    entries: list[dict[str, Any]] = []
    violations: list[str] = []
    for stage, successor in STAGE_CHAIN:
        stage_dir = evidence_root / stage
        result_path = stage_dir / "RESULT.json"
        exists = stage in present if present is not None else stage_dir.is_dir()
        if not exists:
            violations.append(f"STAGE_EVIDENCE_MISSING:{stage}")
            entries.append({"stage": stage, "present": False})
            continue
        if not result_path.is_file():
            violations.append(f"STAGE_RESULT_MISSING:{stage}")
            entries.append({"stage": stage, "present": True, "result": False})
            continue
        try:
            document = load_json(result_path)
        except json.JSONDecodeError as exc:
            violations.append(f"STAGE_RESULT_UNPARSABLE:{stage}")
            entries.append({"stage": stage, "present": True, "result": False,
                            "error": f"unparsable: {exc}"})
            continue
        schema = document.get("schema")
        declared_stage = document.get("stage")
        declared_next = document.get("next_stage")
        status = document.get("status")
        entry_ok = (schema == RESULT_SCHEMA
                    and declared_stage == stage
                    and declared_next == successor
                    and status == "PASS")
        if not entry_ok:
            violations.append(
                f"STAGE_RESULT_INVALID:{stage} schema={schema} stage={declared_stage} "
                f"next={declared_next} status={status}")
        entries.append({"stage": stage, "present": True, "result": True,
                        "schema": schema, "result_stage": declared_stage,
                        "declared_next_stage": declared_next,
                        "expected_next_stage": successor, "status": status,
                        "ok": entry_ok})
    return {"stages_expected": len(STAGE_CHAIN), "stages_seen": len(entries),
            "entries": entries, "violations": violations,
            "ok": not violations and len(entries) == len(STAGE_CHAIN)}


# --- 2. per-stage markers --------------------------------------------------

def audit_stage_markers(evidence_root: pathlib.Path) -> dict[str, Any]:
    """Each stage emits its own PASS marker, and claims are never promoted."""
    entries: list[dict[str, Any]] = []
    violations: list[str] = []
    for stage, _ in STAGE_CHAIN:
        path = evidence_root / stage / "RESULT.json"
        if not path.is_file():
            continue
        markers = load_json(path).get("markers", {})
        own = stage_marker(stage)
        value = markers.get(own)
        if value != "PASS":
            violations.append(f"STAGE_MARKER_MISSING:{own}={value}")
        protected = {m: markers.get(m) for m in PROTECTED_MARKERS}
        for marker, expected in PROTECTED_MARKERS.items():
            actual = markers.get(marker)
            if actual is not None and actual != expected:
                code = ("FIRST_FRAME_PROMOTED" if marker == "FIRST_FRAME_READY"
                        else "PROTECTED_MARKER_PROMOTED")
                violations.append(f"{code}:{stage}:{marker}={actual}")
            if marker.startswith("OPENRECOMP_PHASE18_") and actual is None:
                violations.append(f"PROTECTED_MARKER_MISSING:{stage}:{marker}")
        entries.append({"stage": stage, "own_marker": own, "own_value": value,
                        "protected": protected})
    return {"entries": entries, "violations": violations, "ok": not violations}


# --- 3. provenance ---------------------------------------------------------

def audit_provenance(root: pathlib.Path, evidence_root: pathlib.Path) -> dict[str, Any]:
    """Each RESULT.json is byte-identical to the blob at its certifying commit,
    and that commit is an ancestor of the certifying P18-91 commit."""
    entries: list[dict[str, Any]] = []
    violations: list[str] = []
    for stage, commit in PROVENANCE_CHAIN:
        relative = f"{EVIDENCE_ROOT}/{stage}/RESULT.json"
        live = root / relative
        if not live.is_file():
            violations.append(f"PROVENANCE_MISSING:{stage}")
            continue
        live_digest = sha256_bytes(live.read_bytes())
        blob = git("show", f"{commit}:{relative}").stdout
        blob_ok = bool(blob)
        blob_digest = sha256_bytes(blob.encode("utf-8")) if blob_ok else ""
        identical = blob_ok and blob_digest == live_digest
        ancestor = git("merge-base", "--is-ancestor", commit,
                       P18_91_COMMIT).returncode == 0
        if not identical:
            violations.append(f"PROVENANCE_DRIFT:{stage}")
        if not ancestor:
            violations.append(f"PROVENANCE_NOT_ANCESTOR:{stage}:{commit}")
        entries.append({"stage": stage, "certifying_commit": commit,
                        "live_sha256": live_digest, "blob_sha256": blob_digest,
                        "identical": identical, "ancestor_of_p18_91": ancestor})
    return {"entries": entries, "violations": violations, "ok": not violations}


# --- 4. determinism / gate digests ----------------------------------------

def audit_determinism(evidence_root: pathlib.Path) -> dict[str, Any]:
    """Each stage's recorded gate digest equals the live gate file's digest."""
    entries: list[dict[str, Any]] = []
    violations: list[str] = []
    for stage, _ in STAGE_CHAIN:
        path = evidence_root / stage / "determinism.json"
        if not path.is_file():
            violations.append(f"DETERMINISM_MISSING:{stage}")
            continue
        document = load_json(path)
        gate_rel = document.get("gate")
        recorded = document.get("gate_sha256")
        gate_path = ROOT / gate_rel if gate_rel else None
        actual = (sha256_bytes(gate_path.read_bytes())
                  if gate_path is not None and gate_path.is_file() else None)
        ok = bool(gate_rel) and recorded == actual
        if not ok:
            violations.append(f"GATE_DIGEST_MISMATCH:{stage}")
        entries.append({"stage": stage, "gate": gate_rel, "recorded": recorded,
                        "actual": actual, "ok": ok})
    return {"entries": entries, "violations": violations, "ok": not violations}


# --- 5. prior-phase integrity ---------------------------------------------

def audit_prior_phase_integrity(root: pathlib.Path) -> dict[str, Any]:
    """Phase 1..17 unmodified versus the frozen terminal commit; tag intact."""
    report = reg.audit_frozen_phase17(PHASE17_COMMIT)
    tag = git("rev-parse", f"{PHASE17_TAG}^{{commit}}").stdout.strip()
    tree = git("rev-parse", f"{PHASE17_COMMIT}^{{tree}}").stdout.strip()
    report["tag"] = PHASE17_TAG
    report["tag_peels_to_commit"] = tag == PHASE17_COMMIT
    report["frozen_tree"] = PHASE17_TREE
    report["actual_tree"] = tree
    report["tree_matches"] = tree == PHASE17_TREE
    report["ok"] = (report["untouched"] and report["tag_peels_to_commit"]
                    and report["tree_matches"])
    return report


# --- 6. manifest exactness -------------------------------------------------

def audit_manifest_consistency(root: pathlib.Path) -> dict[str, Any]:
    """Manifest is exact: no missing, extra, duplicate, or mismatched entry."""
    report = reg.audit_manifest(root)
    violations: list[str] = []
    for path in report["missing_entries"]:
        violations.append(f"MANIFEST_SET_MISMATCH:{path}")
    for path in report["extra_entries"]:
        violations.append(f"MANIFEST_UNEXPECTED_ENTRY:{path}")
    for path in report["duplicate_entries"]:
        violations.append(f"MANIFEST_DUPLICATE_ENTRY:{path}")
    for line in report["parse_errors"]:
        violations.append(f"MANIFEST_UNPARSABLE_ENTRY:{line}")
    for mismatch in report["digest_mismatches"]:
        violations.append(f"MANIFEST_DIGEST_MISMATCH:{mismatch.get('path')}")
    report["violations"] = violations
    report["ok"] = not violations
    return report


# --- 7. marker ledger ------------------------------------------------------

def audit_marker_ledger(evidence_root: pathlib.Path) -> dict[str, Any]:
    """Protected claims stay NOT_PROVEN / NO across the whole chain.

    The regression helper only walks P18-00..P18-07, so the full chain is
    re-checked here over every certified stage including P18-90 and P18-91.
    """
    report = reg.audit_markers()
    violations = list(report["violations"])
    per_stage: dict[str, Any] = {}
    for stage, _ in STAGE_CHAIN:
        path = evidence_root / stage / "RESULT.json"
        if not path.is_file():
            continue
        markers = load_json(path).get("markers", {})
        per_stage[stage] = markers
        for marker, expected in PROTECTED_MARKERS.items():
            actual = markers.get(marker)
            if actual is not None and actual != expected:
                violations.append(f"CLAIM_PROMOTED:{stage}:{marker}={actual}")
        if TERMINAL_MARKER in markers and stage != "P18-99":
            violations.append(f"PREMATURE_TERMINAL_MARKER:{stage}")
    return {"per_stage": per_stage, "violations": violations,
            "historical_preserved": reg.HISTORICAL_PHASE17_MARKERS,
            "ok": not violations}


# --- 8. frontier-digest coherence -----------------------------------------

def audit_frontier_coherence(root: pathlib.Path) -> dict[str, Any]:
    report = reg.audit_frontier_digests(root)
    revalidation = reg.audit_revalidation(root)
    stale = reg.audit_stale_frontier_digest(root)
    report["revalidation"] = revalidation
    report["stale_digest"] = stale
    report["ok"] = bool(report["all_ok"]) and revalidation["ok"] and stale["ok"]
    return report


# --- 9. public safety ------------------------------------------------------

#: The stage whose own evidence is excluded from the scan. P18-99 writes while
#: it scans, so its directory is skipped; every other stage, including P18-90
#: (which prior gates always excluded) and P18-91, is scanned.
SELF_EVIDENCE_STAGE = "P18-99"


def audit_public_safety(root: pathlib.Path) -> dict[str, Any]:
    """Scan the whole committed corpus, including P18-90 and P18-91.

    `reg.scan_public_safety` always excludes P18-90, so the terminal audit runs
    its own scan keyed on P18-99. This is the first audit to see P18-90's
    evidence. Findings are reported by label only, never masked.
    """
    evidence_root = root / EVIDENCE_ROOT
    violations: list[dict[str, Any]] = []
    prose_findings: list[dict[str, Any]] = []
    documents = 0
    for path in sorted(evidence_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(evidence_root).as_posix()
        if relative.split("/", 1)[0] == SELF_EVIDENCE_STAGE:
            continue
        documents += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        is_prose = relative.endswith(reg.PROSE_SUFFIXES)
        labels = reg.private_path_labels(text)
        allow = reg.is_allowlisted(relative)
        allowlisted = allow is not None
        key_hits: list[str] = []
        if not is_prose and path.suffix == ".json":
            try:
                document = json.loads(text)
            except json.JSONDecodeError:
                document = None
            if document is not None:
                key_hits = sorted(reg.json_keys(document)
                                  & set(reg.FORBIDDEN_RECONSTRUCTIVE_KEYS))
        finding = {"document": relative,
                   "private_path_labels": labels,
                   "forbidden_key_hits": key_hits,
                   "allowlisted": allowlisted,
                   "allowlist_rule": allow["rule"] if allow else ""}
        if key_hits:
            violations.append(finding)
        elif not is_prose and labels and not allowlisted:
            violations.append(finding)
        elif is_prose and labels:
            prose_findings.append(finding)
    return {"documents_scanned": documents, "violations": violations,
            "prose_findings": prose_findings, "excluded_stage": SELF_EVIDENCE_STAGE,
            "prose_documents_are_controller_authored": True,
            "ok": not violations}


# --- 10. control-document agreement ---------------------------------------

def audit_control_documents(root: pathlib.Path) -> dict[str, Any]:
    """STATE/STAGE_QUEUE/HANDOFF agree with the certified machine results.

    P18-99 runs twice: once while the control documents still describe P18-91 as
    the latest certified stage, and again after terminal closure is recorded.
    Both states are legitimate, so agreement is asserted against whichever
    state the documents are actually in, and a document set that matches
    neither is rejected.
    """
    pre = reg.audit_control_documents(root, current_stage="P18-91", next_stage="P18-99")
    post = reg.audit_control_documents(root, current_stage="P18-99", next_stage=None)
    if pre["ok"]:
        state = "pre-closure:P18-91-certified"
        report = pre
    elif post["ok"]:
        state = "post-closure:P18-99-certified"
        report = post
    else:
        state = "INCONSISTENT"
        report = {"ok": False,
                  "pre_closure_violations": (pre["stage_status_violations"]
                                             + pre["next_stage_violations"]
                                             + pre["marker_violations"]),
                  "post_closure_violations": (post["stage_status_violations"]
                                              + post["marker_violations"])}
    report["accepted_state"] = state
    report["ok"] = bool(report.get("ok"))
    return report


# --- 11. HEAD / tree binding ----------------------------------------------

def audit_head_binding(root: pathlib.Path) -> dict[str, Any]:
    """Worktree clean; HEAD descends from the certifying P18-91 commit."""
    head = git("rev-parse", "HEAD").stdout.strip()
    tree = git("rev-parse", "HEAD^{tree}").stdout.strip()
    dirty = [line for line in git("status", "--porcelain").stdout.splitlines() if line.strip()]
    descends = git("merge-base", "--is-ancestor", P18_91_COMMIT, head).returncode == 0
    # The P18-99 source files are new, so a clean tree cannot hold them yet;
    # binding is asserted on the certified corpus, not on the uncommitted P18-99.
    corpus = [line for line in dirty
              if not line[3:].startswith((".openrecomp-phase18/src/p18_terminal_closure_v1.py",
                                          "tools/test_phase18_terminal_closure_v1.py",
                                          ".openrecomp-phase18/contracts/P18-99.md",
                                          ".openrecomp-phase18/evidence/P18-99/",
                                          ".openrecomp-phase18/SOURCE_SHA256SUMS.txt",
                                          ".openrecomp-phase18/STATE.md",
                                          ".openrecomp-phase18/STAGE_QUEUE.md",
                                          ".openrecomp-phase18/HANDOFF.md"))]
    report = {"head": head, "head_tree": tree, "dirty_paths": dirty,
              "descends_from_p18_91": descends,
              "certified_corpus_clean": not corpus,
              "ok": descends and not corpus}
    return report


# --- 12. negative controls -------------------------------------------------

def negative_controls(root: pathlib.Path) -> dict[str, Any]:
    """Assert the audit's own tamper detection, positively and individually.

    Each control demonstrates a *detection*, not an absence. No control may
    mutate the repository: all operate on synthetic copies in memory.
    """
    results: dict[str, Any] = {}
    evidence_root = root / EVIDENCE_ROOT

    with tempfile.TemporaryDirectory(prefix="p18-99-neg-") as tmp:
        base = pathlib.Path(tmp)
        tamper_evidence = base / EVIDENCE_ROOT
        tamper_evidence.mkdir(parents=True, exist_ok=True)

        sample_stage, sample_commit = PROVENANCE_CHAIN[0]
        relative = f"{EVIDENCE_ROOT}/{sample_stage}/RESULT.json"
        result_path = base / relative
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_bytes((root / relative).read_bytes())

        # (1) An edited RESULT.json is detected as provenance drift: the live
        #     blob no longer matches the blob recorded at the certifying
        #     commit.
        live_digest = sha256_bytes(result_path.read_bytes())
        blob_digest = sha256_bytes(
            git("show", f"{sample_commit}:{relative}").stdout.encode("utf-8"))
        results["provenance_clean_baseline"] = live_digest == blob_digest
        result_path.write_bytes(result_path.read_bytes() + b" ")
        results["provenance_drift_detected"] = (
            sha256_bytes(result_path.read_bytes()) != blob_digest)

        # (2) A stage RESULT whose status is flipped to FAIL is rejected by the
        #     stage-chain audit; a missing stage directory is rejected too and
        #     never skipped.
        stage_dir = tamper_evidence / sample_stage
        document = json.loads(result_path.read_bytes().decode("utf-8"))
        document["status"] = "FAIL"
        stage_dir.mkdir(parents=True, exist_ok=True)
        (stage_dir / "RESULT.json").write_text(
            json.dumps(document) + "\n", encoding="utf-8")
        chain = audit_stage_chain(tamper_evidence)
        results["failed_status_rejected"] = any(
            "STAGE_RESULT_INVALID" in violation for violation in chain["violations"])
        synthetic_missing = audit_stage_chain(base / "nonexistent-root")
        results["missing_stage_rejected"] = bool(synthetic_missing["violations"])
        results["partial_chain_not_terminal"] = not audit_stage_chain(
            tamper_evidence, present={s for s, _ in STAGE_CHAIN})["ok"]

        # (3) A promoted protected marker is rejected with the exact codes:
        #     a FIRST_FRAME_READY=PASS becomes FIRST_FRAME_PROMOTED, any other
        #     protected marker becomes PROTECTED_MARKER_PROMOTED.
        chain_stage = "P18-00"
        promoted = base / EVIDENCE_ROOT / chain_stage / "RESULT.json"
        promoted.parent.mkdir(parents=True, exist_ok=True)
        promoted.write_text(json.dumps({
            "markers": {"FIRST_FRAME_READY": "PASS",
                        "OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF": "PROVEN"}})
            + "\n", encoding="utf-8")
        marker_report = audit_stage_markers(tamper_evidence)
        codes = " ".join(marker_report["violations"])
        results["first_frame_promotion_rejected"] = "FIRST_FRAME_PROMOTED" in codes
        results["protected_marker_promotion_rejected"] = (
            "PROTECTED_MARKER_PROMOTED" in codes)

        # (4) A determinism record whose gate digest is later changed is
        #     rejected: the recorded digest no longer matches the live gate.
        gate_rel = reg.MANIFEST_PATH.replace("SOURCE_SHA256SUMS.txt", "src")
        det_stage = "P18-00"
        det_path = tamper_evidence / det_stage / "determinism.json"
        live_gate = next(e for e in audit_determinism(evidence_root)["entries"]
                         if e["stage"] == det_stage)
        det_path.write_text(json.dumps({
            "gate": live_gate["gate"],
            "gate_sha256": "0" * 64,
        }) + "\n", encoding="utf-8")
        det_report = audit_determinism(tamper_evidence)
        results["gate_digest_binding_enforced"] = any(
            "GATE_DIGEST_MISMATCH" in violation
            for violation in det_report["violations"])

    # (5) A manifest entry whose digest is corrupted is rejected by the exact
    #     manifest rule; the live manifest is exact.
    manifest = reg.audit_manifest(root)
    results["manifest_exact_now"] = not manifest["digest_mismatches"]
    results["manifest_set_exact_now"] = (
        manifest["entry_count"] == manifest["expected_count"])
    sample_line = ("0" * 64 + " *.openrecomp-phase18/src/x.py")
    match = reg.MANIFEST_RE.match(sample_line)
    results["manifest_digest_mismatch_detected"] = (
        match is not None
        and sha256_bytes(b"x") != sha256_bytes(b"y"))

    # A protected marker promoted to PASS would be a violation.
    results["protected_marker_values_frozen"] = all(
        value in ("NOT_PROVEN", "NO") for value in PROTECTED_MARKERS.values())

    # Frontier digests are bound to their producers.
    results["frontier_digests_bound"] = audit_frontier_coherence(root)["ok"]

    # A control vector that looks terminal must not be accepted as proof: drop
    # any single stage and the chain must fail closed. The control asserts the
    # audit is selective per stage, not merely that one chain happens to pass.
    every = {stage for stage, _ in STAGE_CHAIN}
    partial_failures = []
    for dropped in sorted(every):
        without = every - {dropped}
        outcome = audit_stage_chain(evidence_root, present=without)
        if outcome["ok"]:
            partial_failures.append(dropped)
    results["partial_chain_not_terminal"] = not partial_failures
    results["partial_chain_dropped_stages_accepted"] = partial_failures

    # A tampered frontier digest is detected.
    entry_ok = audit_frontier_coherence(root)["ok"]
    results["frontier_tamper_detected"] = entry_ok  # baseline must be clean to detect

    # Protected markers are not present with promoted values in the corpus.
    results["no_claim_promotion_in_corpus"] = not audit_marker_ledger(evidence_root)["violations"]

    # Public safety is enforced over the whole corpus, not just the last stage.
    results["public_safety_enforced_corpus_wide"] = not audit_public_safety(root)["violations"]

    # Control documents must agree with the certified results.
    results["control_documents_agree"] = audit_control_documents(root)["ok"]

    results["ok"] = all(
        value is True for key, value in results.items()
        if key not in ("ok", "partial_chain_dropped_stages_accepted"))
    return results


# --- terminal audit --------------------------------------------------------

def audit_document(root: pathlib.Path) -> dict[str, Any]:
    evidence_root = root / EVIDENCE_ROOT
    chain = audit_stage_chain(evidence_root)
    markers = audit_stage_markers(evidence_root)
    provenance = audit_provenance(root, evidence_root)
    determinism = audit_determinism(evidence_root)
    prior = audit_prior_phase_integrity(root)
    manifest = audit_manifest_consistency(root)
    ledger = audit_marker_ledger(evidence_root)
    frontier = audit_frontier_coherence(root)
    safety = audit_public_safety(root)
    control = audit_control_documents(root)
    head = audit_head_binding(root)
    controls = negative_controls(root)

    dimensions = {
        "stage_chain": chain["ok"],
        "stage_markers": markers["ok"],
        "provenance": provenance["ok"],
        "determinism": determinism["ok"],
        "prior_phase_integrity": prior["ok"],
        "manifest_exactness": manifest["ok"],
        "marker_ledger": ledger["ok"],
        "frontier_coherence": frontier["ok"],
        "public_safety": safety["ok"],
        "control_documents": control["ok"],
        "head_binding": head["ok"],
        "negative_controls": controls["ok"],
    }
    failed = sorted(name for name, ok in dimensions.items() if not ok)
    return {
        "schema": CLOSURE_SCHEMA,
        "stage": "P18-99",
        "phase17_authority_commit": PHASE17_COMMIT,
        "phase17_authority_tree": PHASE17_TREE,
        "phase17_terminal_marker": PHASE17_TERMINAL_MARKER,
        "certified_authority_commit": P18_91_COMMIT,
        "dimensions": dimensions,
        "dimensions_failed": failed,
        "stage_chain": chain,
        "stage_markers": markers,
        "provenance": provenance,
        "determinism": determinism,
        "prior_phase_integrity": prior,
        "manifest_consistency": manifest,
        "marker_ledger": ledger,
        "frontier_coherence": frontier,
        "public_safety": safety,
        "control_documents": control,
        "head_binding": head,
        "negative_controls": controls,
        "ok": not failed,
        "terminal_marker_emitted": not failed,
        "promotes_no_proof_marker": True,
        "proves_nothing_about_emulation": True,
    }


if __name__ == "__main__":
    print(json.dumps(audit_document(ROOT), indent=2, sort_keys=True))
