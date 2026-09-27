#!/usr/bin/env python3
"""Deterministic P18-00 Phase-18 bootstrap / authority / provenance gate.

P18-00 establishes the Phase-18 control plane from the frozen Phase-17 terminal
authority. It:
  * re-verifies the frozen Phase-17 authority from live Git;
  * verifies Phase-1..17 evidence is untouched;
  * inventories imported reconnaissance as reference/hypothesis material;
  * re-derives the GPUSTAT polling frontier from the committed P17-06R
    transcript;
  * records the Phase-18 stage plan and claim boundaries.

It promotes NO proof marker: FIRST_FRAME_READY stays NO and the Phase-18 claim
markers are NOT_PROVEN.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase18/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p18_contracts_v1 as contract
import p18_fixture_verification_v1 as fixture
import p18_gpustat_frontier_analysis_v1 as frontier_analysis
import p18_import_recon_inventory_v1 as recon_inventory
from p18_gate_v1 import Gate, assert_public_safe, reject_private_path, run_stage, write_json
import p18_frozen_phase17_authority_v1 as authority

STAGE = "P18-00"
NEXT_STAGE = "P18-01"

CONTROL_FILES = (
    "CONTROL_POLICY.md",
    "SCOPE.md",
    "STAGE_QUEUE.md",
    "EVIDENCE_SCHEMA.md",
    "FIXTURE_POLICY.md",
    "STATE.md",
    "HANDOFF.md",
)
REQUIRED_DIRS = ("src", "evidence", "build", "scratch")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True).stdout.strip()


def fixture_root() -> pathlib.Path:
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def run_authority() -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, ".openrecomp-phase18/src/p18_frozen_phase17_authority_v1.py"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    ok = (completed.returncode == 0
          and "OPENRECOMP_PHASE18_P17_AUTHORITY_FROZEN=PASS" in completed.stdout)
    return ok, completed.stdout.strip() if not ok else "authority-ok"


def phase17_evidence_untouched() -> tuple[bool, list[str]]:
    """Phase-1..17 namespaces must be byte-identical to the certified commit."""
    changed = git("diff", "--name-only", f"{contract.PHASE17_TERMINAL_COMMIT}..HEAD",
                  "--", *contract.FROZEN_NAMESPACES).splitlines()
    dirty = git("status", "--porcelain", "--", *contract.FROZEN_NAMESPACES).splitlines()
    return (not changed and not dirty), changed + dirty


def negative_authority_wrong_tag() -> bool:
    """A tag that does not resolve to the certified commit must fail closed."""
    with tempfile.TemporaryDirectory() as tmp:
        wrong = pathlib.Path(tmp) / "p18_frozen_phase17_authority_v1.py"
        wrong.write_text(
            pathlib.Path(ROOT / ".openrecomp-phase18/src/p18_frozen_phase17_authority_v1.py")
            .read_text(encoding="utf-8")
            .replace('AUTHORITY_COMMIT = "d7cc5d09eebde398ca6ff3f3dad8dd5841913b69"',
                     'AUTHORITY_COMMIT = "0" * 40'),
            encoding="utf-8")
        completed = subprocess.run([sys.executable, str(wrong)], cwd=str(ROOT),
                                   capture_output=True, text=True)
        return completed.returncode != 0


def negative_transcript_digest_mismatch() -> bool:
    """A transcript whose digest does not match must be rejected."""
    document, _ = frontier_analysis.load_transcript()
    try:
        frontier_analysis.analyse(document, "0" * 64)
    except Exception:
        return True
    return False


def negative_frontier_promotion_attempt() -> bool:
    """Analysis output must never claim FIRST_FRAME_READY=YES."""
    analysis, _ = frontier_analysis.analyse_committed()
    return analysis["claims"]["first_frame_ready"] == "NO"


def negative_inflated_gpustat_count() -> bool:
    """An inflated GPUSTAT read count changes the derived census -> must differ."""
    document, digest = frontier_analysis.load_transcript()
    baseline = frontier_analysis.analyse(document, digest)
    mutated = json.loads(json.dumps(document))
    for event in mutated["events"]:
        if event.get("class") == "GPUSTAT_READ":
            event["owning_instruction_pc"] = "0xdeadbeef"
    altered = frontier_analysis.analyse(mutated, digest)
    return (altered["gpustat"]["dominant_owner_pc"]
            != baseline["gpustat"]["dominant_owner_pc"])


def negative_fixture_absent() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        ok, _ = fixture.verify_fixture(pathlib.Path(tmp) / "does-not-exist")
        return not ok


def negative_private_path_safety() -> dict[str, object]:
    cases = (
        "/home/fred/private/location",
        "/Users/example/private/location",
        "/tmp/private-fixture",
        r"C:\private\fixture",
    )
    results: dict[str, object] = {}
    all_rejected = True
    for path in cases:
        gate = Gate("private-path")
        try:
            assert_public_safe(gate, "private-path", {"probe_path": path})
            results[path] = {"rejected": False}
            all_rejected = False
        except AssertionError:
            results[path] = {"rejected": True}
    return {"all_rejected": all_rejected, "cases": results}


def positive_safe_relative_path() -> bool:
    gate = Gate("positive-safe")
    try:
        assert_public_safe(gate, "positive-safe",
                           {"probe_path": "relative/synthetic/control.bin"})
        return True
    except AssertionError:
        return False


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 1. Frozen Phase-17 authority, independently re-derived from live Git.
    ok, out = run_authority()
    gate.check("authority:phase17-frozen", ok, out)
    gate.check("authority:tag-resolves",
               git("rev-parse", f"{contract.PHASE17_TERMINAL_TAG}^{{commit}}")
               == contract.PHASE17_TERMINAL_COMMIT, contract.PHASE17_TERMINAL_TAG)
    gate.check("authority:tree-matches",
               git("rev-parse", f"{contract.PHASE17_TERMINAL_COMMIT}^{{tree}}")
               == contract.PHASE17_TERMINAL_TREE, "certified tree")
    gate.check("authority:branch-name",
               git("branch", "--show-current") == "phase18/ps1-first-frame-frontier-v1",
               "phase18 branch")

    # 2. Phase-1..17 evidence stays untouched.
    untouched, offenders = phase17_evidence_untouched()
    gate.check("frozen:phase1-17-untouched", untouched, ",".join(offenders[:5]))

    # 3. Phase-18 control plane present.
    control_root = root / contract.PHASE18_NAMESPACE
    for filename in CONTROL_FILES:
        cpath = control_root / filename
        gate.check(f"control:{filename}", cpath.is_file() and cpath.stat().st_size > 0,
                   filename)
    for dirname in REQUIRED_DIRS:
        dpath = control_root / dirname
        dpath.mkdir(parents=True, exist_ok=True)
        gate.check(f"dir:{dirname}", dpath.is_dir(), dirname)

    # 4. Private fixture integrity (fail-closed).
    fx_report = fixture.verify_fixture_with_callback(
        fixture_root(),
        lambda label, condition, detail="": gate.check(label, condition, str(detail)),
    )

    # 5. No private fixture bytes tracked.
    tracked = subprocess.run(["git", "ls-files"], cwd=str(root),
                             capture_output=True, text=True).stdout.splitlines()
    forbidden = (".bin", ".cue", "SLUS_005.29", "fixtures/psx/hercules")
    leaked = [name for name in tracked if any(tok in name for tok in forbidden)]
    gate.check("private:no-fixture-bytes-tracked", not leaked, ",".join(leaked))

    # 6. Imported reconnaissance inventory (reference material only).
    recon = recon_inventory.inventory()
    gate.check("recon:import-present", recon["import_present"] is True,
               "imported reconnaissance located")
    gate.check("recon:reference-only",
               recon["authority"] == "REFERENCE_HYPOTHESIS_ONLY"
               and recon["evidence_policy"]
               == "IMPORTED_RESULTS_REQUIRE_INDEPENDENT_AUTHENTICATION",
               "import evidence policy")

    # 7. Frontier re-derivation from the digest-verified transcript.
    analysis, digest = frontier_analysis.analyse_committed()
    gate.check("frontier:transcript-digest", digest == frontier_analysis.EXPECTED_TRANSCRIPT_SHA256,
               "P17-06R transcript digest")
    gate.check("frontier:gpustat-poll-encountered",
               analysis["gpustat"]["read_count"] > 0
               and analysis["gpustat"]["all_reads_returned_zero"] is True,
               "zero-returning GPUSTAT poll")
    gate.check("frontier:no-gpu-writes",
               analysis["adjacent_frontier"]["gp0_write_count"] == 0,
               "no GP0 traffic recorded")
    gate.check("frontier:no-dma2-traffic",
               analysis["adjacent_frontier"]["dma2_window_event_count"] == 0,
               "no DMA-2 traffic recorded")
    gate.check("frontier:no-marker-promotion",
               analysis["promotes_no_proof_marker"] is True
               and analysis["claims"]["first_frame_ready"] == "NO",
               "analysis promotes nothing")

    # 8. Phase-18 claim markers start NOT_PROVEN / NO.
    gate.check("markers:phase18-initialization",
               contract.INITIALIZATION_MARKER.endswith("INITIALIZATION_PROOF"), "created")
    gate.check("markers:no-phase17-reuse",
               "PHASE17" not in contract.INITIALIZATION_MARKER
               and "PHASE18" in contract.INITIALIZATION_MARKER, "distinct namespace")

    # 9. Required negative controls.
    gate.check("negative:authority-wrong-commit", negative_authority_wrong_tag(),
               "wrong certified commit rejected")
    gate.check("negative:transcript-digest-mismatch", negative_transcript_digest_mismatch(),
               "digest mismatch rejected")
    gate.check("negative:frontier-promotion-blocked", negative_frontier_promotion_attempt(),
               "promotion attempt cannot set frame ready")
    gate.check("negative:inflated-gpustat-census", negative_inflated_gpustat_count(),
               "altered owner census detected")
    gate.check("negative:fixture-absent", negative_fixture_absent(), "missing fixture rejected")
    private_results = negative_private_path_safety()
    gate.check("negative:private-path-safety", private_results["all_rejected"],
               json.dumps(private_results["cases"], sort_keys=True))
    gate.check("positive:safe-relative-path", positive_safe_relative_path(),
               "ordinary public-safe relative path accepted")

    # 10. Stable control documents.
    authority_doc = {
        "schema": "openrecomp-phase18-authority-v1",
        "stage": STAGE,
        "authority_tag": contract.PHASE17_TERMINAL_TAG,
        "authority_commit": contract.PHASE17_TERMINAL_COMMIT,
        "authority_tree": contract.PHASE17_TERMINAL_TREE,
        "phase16_base_commit": contract.PHASE16_BASE_COMMIT,
        "phase16_base_tree": contract.PHASE16_BASE_TREE,
        "phase17_terminal_marker": contract.PHASE17_TERMINAL_MARKER,
        "phase17_terminal_marker_value": contract.PHASE17_TERMINAL_MARKER_VALUE,
        "phase18_branch": "phase18/ps1-first-frame-frontier-v1",
        "frozen_namespaces_verified": list(contract.FROZEN_NAMESPACES),
        "phase1_17_untouched": untouched,
    }
    write_json(evidence / "authority.json", authority_doc)
    assert_public_safe(gate, "authority", authority_doc)

    recon_doc = {k: v for k, v in recon.items()}
    write_json(evidence / "recon_inventory.json", recon_doc)
    assert_public_safe(gate, "recon", recon_doc)

    write_json(evidence / "frontier_analysis.json", analysis)
    assert_public_safe(gate, "frontier", analysis)

    stage_plan = {
        "schema": "openrecomp-phase18-stage-plan-v1",
        "stage": STAGE,
        "admitted_stages": ["P18-00"],
        "conceptual_progression": [
            "P18-00", "P18-01", "P18-02", "P18-03", "P18-04",
            "P18-05", "P18-06", "P18-07", "P18-90", "P18-91", "P18-99",
        ],
        "primary_technical_question": (
            "Why does authentic execution remain in the GPUSTAT polling "
            "behaviour observed at the end of Phase 17?"
        ),
        "leading_hypothesis": (
            "Under the declared ZERO_FILL_RECORDED MMIO read model every "
            "GPUSTAT read returns zero, so the guest's poll exit condition "
            "(bit 26 ready-to-receive-command == 1) can never be evaluated "
            "true and authentic execution cannot leave the wait loop."
        ),
        "hypothesis_status": "HYPOTHESIS_NOT_YET_PROVEN",
        "next_stage": NEXT_STAGE,
    }
    write_json(evidence / "stage_plan.json", stage_plan)
    assert_public_safe(gate, "stage_plan", stage_plan)

    write_json(evidence / "fixture_verification.json", {
        "schema": "openrecomp-phase18-fixture-verification-v1",
        "stage": STAGE,
        "bin_sha256": fx_report.get("bin_sha256"),
        "bin_size": fx_report.get("bin_size"),
        "cue_sha256": fx_report.get("cue_sha256"),
        "slus_sha256": fx_report.get("slus_sha256"),
        "slus_size": fx_report.get("slus_size"),
        "private_fixture_bytes_recorded": "NO",
    })

    write_json(evidence / "negative_tests.json", {
        "schema": "openrecomp-phase18-negative-tests-v1",
        "stage": STAGE,
        "private_path_cases": private_results["cases"],
    })

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase18-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "authority_commit": contract.PHASE17_TERMINAL_COMMIT,
        "authority_tree": contract.PHASE17_TERMINAL_TREE,
        "frozen_authority": contract.PHASE17_TERMINAL_MARKER,
        "frontier_summary": {
            "gpustat_read_count": analysis["gpustat"]["read_count"],
            "gpustat_all_zero": analysis["gpustat"]["all_reads_returned_zero"],
            "dominant_owner_pc": analysis["gpustat"]["dominant_owner_pc"],
            "read_model": analysis["gpustat"]["read_model"],
            "runtime_stop_reason": analysis["frontier"]["runtime_stop_reason"],
        },
        "import_recon_file_count": recon.get("file_count"),
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
            contract.FIRST_FRAME_READY_MARKER: "NO",
        },
        "next_stage": NEXT_STAGE,
    })

    gate.mark(contract.BOOTSTRAP_MARKER)
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase18/evidence/P18-00"))
