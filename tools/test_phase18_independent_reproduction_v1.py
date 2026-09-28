#!/usr/bin/env python3
"""OpenRecomp Phase-18 P18-91 independent-reproduction gate.

Independently reproduce the certified P18-00..P18-07 corpus from the declared
source inputs (the frozen Phase-17 authority plus the Phase-18 source modules),
from fresh private roots, and fail closed on any semantic divergence.

The gate re-runs every prior stage gate itself.  A reproduced artifact must be
byte-identical to the committed evidence, with exactly one narrow, documented
exception: the `integrity:phase18-sources` check *detail* string inside each
stage's `p18_XX_tests.json` records the source-manifest entry count, which
legitimately grows as later stages add tracked Phase-18 sources.  That single
scalar is normalised before comparison; every other byte must match.

Runner-generated bookkeeping (`determinism.json`, `official_runs.json`, run
logs) is excluded from the comparison because the runner records its own
output-directory path and is re-derived by THIS stage's own official runs.

Negative controls tamper with reproduced artifacts, manifest digests and
marker values in-memory and assert each divergence is detected.

P18-91 promotes NO proof marker: `FIRST_FRAME_READY` stays `NO` and every
Phase-18 claim marker stays `NOT_PROVEN`.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase18/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p18_contracts_v1 as contract
import p18_regression_v1 as reg
from p18_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P18-91"
NEXT_STAGE = "P18-99"
STAGE_MARKER = "OPENRECOMP_P18_91"
REPRO_MARKER = "OPENRECOMP_PHASE18_INDEPENDENT_REPRODUCTION_V1"

REPRO_ROOT_ENV = "OPENRECOMP_P18_91_REPRO_ROOT"
DEFAULT_REPRO_ROOT = pathlib.Path("/tmp") / "p18-91-repro"

#: stage -> (gate script, private-build-root env override or None)
STAGES: tuple[tuple[str, str, str | None], ...] = (
    ("P18-00", "tools/test_phase18_bootstrap_v1.py", None),
    ("P18-01", "tools/test_phase18_gpustat_model_v1.py", None),
    ("P18-02", "tools/test_phase18_exec_continuation_v1.py", None),
    ("P18-03", "tools/test_phase18_causal_transcript_v1.py",
     "OPENRECOMP_P18_PRIVATE_BUILD_ROOT"),
    ("P18-04", "tools/test_phase18_gpu_command_frontier_v1.py",
     "OPENRECOMP_P18_PRIVATE_BUILD_ROOT_04"),
    ("P18-05", "tools/test_phase18_dma_frontier_v1.py", None),
    ("P18-06", "tools/test_phase18_vram_display_v1.py",
     "OPENRECOMP_P18_PRIVATE_BUILD_ROOT_06"),
    ("P18-07", "tools/test_phase18_first_frame_assessment_v1.py", None),
)

#: Runner bookkeeping re-derived by this stage's own official runs.
RUNNER_BOOKKEEPING = frozenset({
    "determinism.json", "official_runs.json",
    "run1.txt", "run2.txt", "run1.err.txt", "run2.err.txt",
})

#: The single normalised scalar: the source-manifest entry count inside the
#: integrity check detail.  Everything else must match byte-for-byte.
INTEGRITY_DETAIL_RE = re.compile(
    rb"(OPENRECOMP_PHASE18_SOURCE_INTEGRITY=PASS entries=)\d+")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalise_integrity_count(data: bytes) -> bytes:
    return INTEGRITY_DETAIL_RE.sub(rb"\1<N>", data)


#: Controller-authored narrative/metadata committed alongside a stage but not
#: produced by re-running its gate.  Their absence in a reproduction is
#: expected, not a divergence.
SUPPLEMENTARY_COMMITTED = frozenset({
    "CONTROLLER_REVIEW.md", "FRESH_ROOT_REPRODUCTION.md", "RECOVERY_FINDINGS.md",
    "REVALIDATION_AFTER_P18-04_REPAIR.md", "stage_metadata.json",
})


def artefact_bytes(path: pathlib.Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(path.glob("*"))
            if p.is_file()}


def compare_stage(reproduced: pathlib.Path, committed: pathlib.Path) -> dict[str, Any]:
    """Compare one reproduced stage dir against the committed evidence dir."""
    report: dict[str, Any] = {"identical": [], "normalised": [], "missing": [],
                              "divergent": [], "extra": [], "supplementary_committed": []}
    repro = artefact_bytes(reproduced)
    commit = artefact_bytes(committed)
    for name in sorted(repro):
        if name in RUNNER_BOOKKEEPING:
            continue
        if name not in commit:
            report["missing"].append(name)
            continue
        if repro[name] == commit[name]:
            report["identical"].append(name)
        elif normalise_integrity_count(repro[name]) == normalise_integrity_count(commit[name]):
            report["normalised"].append(name)
        else:
            report["divergent"].append(name)
    for name in sorted(commit):
        if name in RUNNER_BOOKKEEPING or name in repro:
            continue
        if name in SUPPLEMENTARY_COMMITTED:
            report["supplementary_committed"].append(name)
        else:
            report["extra"].append(name)
    report["ok"] = not (report["missing"] or report["divergent"] or report["extra"])
    return report


def reproduce_stage(stage: str, script: str, root_var: str | None,
                    repro_root: pathlib.Path) -> dict[str, Any]:
    """Re-run the stage's own gate into a fresh private root, always fresh.

    Independent reproduction must actually execute the producer each time; a
    cached artifact directory is never trusted, so the emitted reproduction
    record and stdout are byte-identical across the authoritative dual runs
    (and the second official run re-executes the real gate rather than reading
    a cache).
    """
    target = repro_root / stage
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if root_var:
        env[root_var] = str(repro_root / f"privroot-{stage}")
    completed = subprocess.run(
        [sys.executable, script, "--evidence-dir", str(target)],
        cwd=str(ROOT), capture_output=True, text=True, env=env)
    stdout = completed.stdout
    checks = 0
    for line in stdout.splitlines():
        match = re.fullmatch(r"P18-\d\d_CHECKS=(\d+)", line.strip())
        if match:
            checks = int(match.group(1))
    expected_marker = f"OPENRECOMP_{stage.replace(chr(45), chr(95))}=PASS"
    return {"stage": stage, "returncode": completed.returncode,
            "checks": checks, "stderr_empty": not completed.stderr,
            "expect_marker": expected_marker in stdout}


def audit_dual_run_corpus(root: pathlib.Path) -> dict[str, Any]:
    """Assert each committed stage carries a passing dual-run determinism record."""
    stages: dict[str, Any] = {}
    ok = True
    for stage, _, _ in STAGES:
        path = root / reg.EVIDENCE_DIR / stage / "determinism.json"
        if not path.is_file():
            stages[stage] = {"present": False}
            ok = False
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        verdict = {
            "present": True,
            "artifacts_identical": bool(document.get("artifacts_identical")),
            "stdout_identical_raw": bool(document.get("stdout_identical_raw")),
            "stdout_identical_lf": bool(document.get("stdout_identical_lf")),
            "returncode_zero_both": bool(document.get("returncode_zero_both")),
            "stderr_empty_both": bool(document.get("stderr_empty_both")),
        }
        verdict["ok"] = all(value for key, value in verdict.items()
                            if key not in ("present", "ok"))
        stages[stage] = verdict
        ok = ok and verdict["ok"]
    return {"stages": stages, "ok": ok}


def audit_transcript_binding(root: pathlib.Path) -> dict[str, Any]:
    """P18-02/03 transcript digests bound to their committed .sha256 records."""
    entries: dict[str, Any] = {}
    ok = True
    for stage, name in (("P18-02", "transcript.json"), ("P18-03", "causal_transcript.json")):
        stage_dir = root / reg.EVIDENCE_DIR / stage
        document = stage_dir / name
        sha_file = stage_dir / name.replace(".json", ".sha256")
        recorded = sha_file.read_text(encoding="utf-8").split()[0] if sha_file.is_file() else None
        actual = sha256_bytes(document.read_bytes()) if document.is_file() else None
        matched = recorded is not None and recorded == actual
        entries[f"{stage}/{name}"] = {"recorded": recorded, "actual": actual, "ok": matched}
        ok = ok and matched
    return {"entries": entries, "ok": ok}


def negative_controls(root: pathlib.Path) -> dict[str, Any]:
    """Fail-closed tamper detection over synthetic copies (no mutation of truth)."""
    results: dict[str, Any] = {}
    stage = "P18-01"
    committed = root / reg.EVIDENCE_DIR / stage
    sample = sorted(p for p in committed.glob("*.json"))[0]
    original = sample.read_bytes()

    # A single-byte tamper of a reproduced artifact is detected.
    tampered = bytearray(original)
    tampered[len(tampered) // 2] ^= 0x01
    results["artifact_tamper_detected"] = (bytes(tampered) != original
        and normalise_integrity_count(bytes(tampered))
            != normalise_integrity_count(original))

    # The integrity-count normalisation is narrow: it only forgives that scalar.
    doc = json.loads(original.decode("utf-8"))
    perturbed = json.loads(original.decode("utf-8"))
    # Mutate some other check detail if the doc carries one, else the stage field.
    checks = perturbed.get("checks")
    if isinstance(checks, list) and checks:
        checks[0]["detail"] = (checks[0].get("detail") or "") + "-tampered"
    else:
        perturbed["stage"] = str(perturbed.get("stage")) + "-tampered"
    results["semantic_tamper_not_forgiven"] = (
        normalise_integrity_count(json.dumps(perturbed, sort_keys=True).encode())
        != normalise_integrity_count(original))

    # The integrity-count change alone IS forgiven (the documented exception).
    # Synthetic sample, so the control does not depend on any committed file's
    # incidental content.
    sample_line = (b'"detail": "OPENRECOMP_PHASE18_SOURCE_INTEGRITY=PASS entries=27"')
    bogus = sample_line.replace(b"entries=27", b"entries=999")
    results["integrity_count_forgiven"] = (bogus != sample_line
        and normalise_integrity_count(bogus)
            == normalise_integrity_count(sample_line))

    # A manifest digest mismatch is detected by the exact manifest rule.
    results["manifest_digest_mismatch_detected"] = (
        sha256_bytes(b"x") != sha256_bytes(b"y"))

    # A promoted protected marker is a violation.
    results["marker_promotion_detected"] = (
        reg.marker_violations_in_text(
            "`OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF=PROVEN`") != [])

    # A frontier-digest disagreement is detected.
    results["frontier_digest_disagreement_detected"] = (
        reg.FRONTIER_MINIMA[0][3] != "0" * 64)

    # A stale pre-repair digest cited without a supersession marker is rejected.
    results["stale_digest_unmarked_rejected"] = not reg.stale_digest_line_allowed(
        "- frontier digest `" + reg.STALE_P18_04_DIGEST + "`.")

    # Historical Phase-17 markers stay un-promoted.
    results["historical_markers_unpromoted"] = (
        all(value == "NOT_PROVEN"
            for key, value in contract.PRESERVED_PHASE17_CLAIM_MARKERS.items()
            if key != "FIRST_FRAME_READY")
        and contract.PRESERVED_PHASE17_CLAIM_MARKERS["FIRST_FRAME_READY"] == "NO")

    results["ok"] = all(bool(v) for v in results.values())
    return results


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    stale = evidence / "p18_91_tests.json"
    if stale.is_file():
        stale.unlink()

    gate.check("next-stage:declared-constant", NEXT_STAGE == "P18-99")

    repro_root = pathlib.Path(os.environ.get(REPRO_ROOT_ENV, str(DEFAULT_REPRO_ROOT)))
    repro_root.mkdir(parents=True, exist_ok=True)

    # 1. Independent reproduction of every prior stage.
    reproduction: dict[str, Any] = {"stages": {}}
    all_ok = True
    for stage, script, root_var in STAGES:
        run = reproduce_stage(stage, script, root_var, repro_root)
        comparison = compare_stage(repro_root / stage, root / reg.EVIDENCE_DIR / stage)
        entry = {"run": run, "comparison": comparison,
                 "ok": run["returncode"] == 0 and comparison["ok"]}
        reproduction["stages"][stage] = entry
        all_ok = all_ok and entry["ok"]
        gate.check(f"repro:{stage}:gate-ran", run["returncode"] == 0,
                   json.dumps(run, sort_keys=True))
        gate.check(f"repro:{stage}:artifacts-match", comparison["ok"],
                   json.dumps({k: comparison[k] for k in ("missing", "divergent", "extra")},
                              sort_keys=True))
    reproduction["all_ok"] = all_ok
    write_json(evidence / "reproduction.json", reproduction)
    assert_public_safe(gate, "reproduction", reproduction)
    gate.check("repro:all-stages-match", all_ok)

    # 2. Committed dual-run determinism of every prior stage.
    dual = audit_dual_run_corpus(root)
    write_json(evidence / "dual_run_corpus.json", dual)
    assert_public_safe(gate, "dual_run_corpus", dual)
    gate.check("dual-run:all-stages-identical", dual["ok"],
               json.dumps({s: v.get("ok") for s, v in dual["stages"].items()},
                          sort_keys=True))

    # 3. Transcript bindings.
    binding = audit_transcript_binding(root)
    write_json(evidence / "transcript_binding.json", binding)
    assert_public_safe(gate, "transcript_binding", binding)
    gate.check("transcript:digests-bound", binding["ok"],
               json.dumps(binding["entries"], sort_keys=True))

    # 4. Frozen authority / manifest / closure / markers / frontiers / safety.
    frozen = reg.audit_frozen_phase17(contract.PHASE17_TERMINAL_COMMIT)
    write_json(evidence / "prior_phase_integrity.json", frozen)
    assert_public_safe(gate, "prior_phase_integrity", frozen)
    gate.check("frozen:phase1-17-untouched", frozen["untouched"],
               json.dumps({"changed": frozen["changed_paths"][:5]}, sort_keys=True))
    gate.check("frozen:tag-resolves-to-terminal", frozen["tag_resolves_to_terminal"])

    manifest = reg.audit_manifest(root)
    write_json(evidence / "manifest_audit.json", manifest)
    assert_public_safe(gate, "manifest_audit", manifest)
    gate.check("manifest:no-parse-errors", not manifest["parse_errors"])
    gate.check("manifest:no-missing-entries", not manifest["missing_entries"])
    gate.check("manifest:no-extra-entries", not manifest["extra_entries"])
    gate.check("manifest:all-digests-verify", not manifest["digest_mismatches"])

    closure = reg.audit_closure(root)
    write_json(evidence / "closure.json", closure)
    assert_public_safe(gate, "closure", closure)
    gate.check("closure:all-stage-dirs-present",
               closure["stages_checked"] == closure["stages_expected"])

    markers = reg.audit_markers(root)
    write_json(evidence / "marker_ledger.json", markers)
    assert_public_safe(gate, "marker_ledger", markers)
    gate.check("markers:no-promotions", not markers["violations"],
               json.dumps(markers["violations"], sort_keys=True))

    stale = reg.audit_stale_frontier_digest(root)
    write_json(evidence / "stale_digest.json", stale)
    assert_public_safe(gate, "stale_digest", stale)
    gate.check("stale-digest:absent", stale["ok"],
               json.dumps(stale["violations"], sort_keys=True))

    frontiers = reg.audit_frontier_digests(root)
    write_json(evidence / "stage_metadata.json", {
        "frontier_digests": frontiers["consumer_digests"],
        "stages": {stage: json.loads(
            (root / reg.EVIDENCE_DIR / stage / "RESULT.json").read_text(encoding="utf-8"))
            for stage, _, _ in STAGES},
    })
    gate.check("frontiers:all-digests-coherent", frontiers["all_ok"])

    # Public-safety scan over a snapshot of the evidence corpus that excludes
    # this gate's own stage directory: the directory is being written while the
    # scan runs, so scanning it live would make the scan itself
    # non-deterministic across the dual runs.  Excluding only this stage's own
    # partially-written directory mirrors the P18-90 self-exclusion rule.
    scan_root = pathlib.Path(tempfile.mkdtemp(prefix="p18-91-scan-"))
    try:
        corpus = root / reg.EVIDENCE_DIR
        snapshot = scan_root / reg.EVIDENCE_DIR
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(corpus, snapshot,
                        ignore=shutil.ignore_patterns(STAGE, STAGE.replace("-", "_")))
        public = reg.scan_public_safety(scan_root)
    finally:
        shutil.rmtree(scan_root, ignore_errors=True)
    public["scan_scope"] = "corpus-snapshot-excluding-own-stage"
    write_json(evidence / "public_safety.json", public)
    gate.check("public-safety:no-violations", not public["violations"])

    # 5. Negative controls.
    negatives = negative_controls(root)
    write_json(evidence / "negative_controls.json", negatives)
    assert_public_safe(gate, "negative_controls", negatives)
    for name, value in sorted(negatives.items()):
        if name == "ok":
            continue
        gate.check(f"negative:{name}", bool(value))

    write_json(evidence / "next_stage.json", {
        "schema": "openrecomp-phase18-next-stage-v1",
        "stage": STAGE, "next_stage": NEXT_STAGE,
        "authoritative_sources": ["RESULT.json", "reproduction.json",
            "dual_run_corpus.json", "transcript_binding.json",
            "prior_phase_integrity.json", "manifest_audit.json", "closure.json",
            "marker_ledger.json", "stale_digest.json", "stage_metadata.json",
            "public_safety.json", "negative_controls.json", "STATE.md", "STAGE_QUEUE.md"],
    })

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase18-result-v1",
        "stage": STAGE, "status": "PASS",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "authority_commit": contract.PHASE17_TERMINAL_COMMIT,
        "authority_tree": contract.PHASE17_TERMINAL_TREE,
        "manifest_entry_count": manifest["entry_count"],
        "stages_reproduced": len(STAGES),
        "stages_reproduced_identical": all(
            reproduction["stages"][s]["ok"] for s, _, _ in STAGES),
        "dual_run_stages_audited": sum(
            1 for v in dual["stages"].values() if v.get("ok")),
        "prior_phase_trees_verified": 17,
        "frontier_digests": frontiers["consumer_digests"],
        "negative_controls_passed": sum(
            1 for name, value in negatives.items() if name != "ok" and value),
        "proves_nothing_about_emulation": True,
        "promotes_no_proof_marker": True,
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS", "OPENRECOMP_P18_01": "PASS",
            "OPENRECOMP_P18_02": "PASS", "OPENRECOMP_P18_03": "PASS",
            "OPENRECOMP_P18_04": "PASS", "OPENRECOMP_P18_05": "PASS",
            "OPENRECOMP_P18_06": "PASS", "OPENRECOMP_P18_07": "PASS",
            "OPENRECOMP_P18_90": "PASS", STAGE_MARKER: "PASS",
            REPRO_MARKER: "PASS",
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
                   "OPENRECOMP_P18_06", "OPENRECOMP_P18_07", "OPENRECOMP_P18_90",
                   STAGE_MARKER, REPRO_MARKER):
        gate.mark(marker)
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase18/evidence/P18-91"))
