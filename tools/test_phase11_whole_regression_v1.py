#!/usr/bin/env python3
"""P11-90 reconciled Phase-1 through Phase-11 whole-project regression.

The frozen Phase-10 whole-regression gate is executed live, then every
executed Phase-11 stage P11-00 through P11-07 is executed live into scratch
evidence and compared with its committed official stdout. P11-RC is verified
as a committed deterministic control boundary. P11-08 through P11-12 are
neither executed nor assigned a verdict.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
P11 = ROOT / ".openrecomp-phase11"
STAGE = "P11-90"
FEATURE_MARKER = "OPENRECOMP_PHASE11_WHOLE_REGRESSION_V1"
P11_RC_COMMIT = "1292b923af0af75424cec95e1c14f95c8b3d1fd0"
P11_RC_TREE = "f20c22b3ac9727ea67e448413cea79e302f5a1cb"
BRANCH = "phase11/ps1-playability-v1"
PHASE10_BRANCH = "phase10/ps1-commercial-game-native-v1"
PHASE10_COMMIT = "8961682aa36e14db979e8e8dbe88e04fa2b4c87a"
PHASE10_TREE = "4a58d9238d76a490560c588bb470fd9e6a58cafe"

INITIALIZATION_MARKER = (
    "OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN"
)
FRAME_MARKER = "OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN"
GENERAL_MARKER = "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN"
GPU_MARKER = "OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF=PROVEN"

P10_90 = (
    "tools/test_phase10_whole_regression_v1.py",
    "OPENRECOMP_P10_90=PASS",
    "90630afd040fe19f21c6ae25f07e6e6efba07aa95c061f15c8488e32a2fd1aad",
)

# P11-07 added the public identifier for B0:0x57 to the shared classifier.
# P11-02's frozen evidence remains historical, while its current-system gate
# now emits the enriched metadata and five additional public-safety checks.
P11_02_CURRENT_STDOUT_SHA256 = (
    "0a9f7efca00000497efa11978c3ec56cf9a8094cd48c0a88cf936bb4a347fcb1"
)
P11_02_CURRENT_TESTS = 1471
P11_03_CURRENT_STDOUT_SHA256 = (
    "e442fcde36a8e5d1613476b4ea88e38d3b990b72e083e6206aac3e20dea0c325"
)
P11_03_CURRENT_TESTS = 1331

P11_GATES = (
    ("P11-00", "tools/test_phase11_boundary_v1.py", "p11_00_tests.json"),
    ("P11-01", "tools/test_phase11_causality_v1.py", "p11_01_tests.json"),
    ("P11-02", "tools/test_phase11_indirect_v1.py", "p11_02_tests.json"),
    ("P11-03", "tools/test_phase11_event_contract_v1.py", "p11_03_tests.json"),
    ("P11-04", "tools/test_phase11_initialization_v1.py", "p11_04_tests.json"),
    ("P11-05", "tools/test_phase11_gpu_v1.py", "p11_05_tests.json"),
    ("P11-06", "tools/test_phase11_gpu_closure_v1.py", "p11_06_tests.json"),
    ("P11-07", "tools/test_phase11_b0_table_v1.py", "p11_07_tests.json"),
)

RESULTS: list[dict[str, str]] = []


def check(name: str, condition: bool, detail: object = "") -> None:
    RESULTS.append({
        "check": name,
        "status": "PASS" if condition else "FAIL",
        "detail": str(detail),
    })
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def write_json(path: pathlib.Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(ROOT), check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    if completed.returncode != 0 or completed.stderr:
        raise RuntimeError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def run_gate(script: str, evidence_dir: pathlib.Path) -> tuple[int, bytes, bytes]:
    completed = subprocess.run(
        [sys.executable, script, "--evidence-dir",
         evidence_dir.relative_to(ROOT).as_posix()],
        cwd=str(ROOT), check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return completed.returncode, completed.stdout, completed.stderr


def run_phase10_gate(worktree: pathlib.Path) -> tuple[int, bytes, bytes, pathlib.Path]:
    evidence_dir = worktree / ".openrecomp-phase10/cache/p11-90-output"
    completed = subprocess.run(
        [sys.executable, P10_90[0], "--evidence-dir",
         ".openrecomp-phase10/cache/p11-90-output"],
        cwd=str(worktree), check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return completed.returncode, completed.stdout, completed.stderr, evidence_dir


def committed_stdout(stage: str) -> str:
    official = json.loads(
        (P11 / "evidence" / stage / "official_runs.json").read_text(encoding="utf-8")
    )
    return official["runs"][0]["stdout_sha256_raw"]


def p11_02_expectation_delta() -> list[tuple[int, str, str]]:
    """Return the exact current-vs-P11-RC P11-02 source-line changes."""
    path = "tools/test_phase11_indirect_v1.py"
    historical = git("show", f"HEAD:{path}").splitlines()
    current = (ROOT / path).read_text(encoding="utf-8").splitlines()
    if len(historical) != len(current):
        return [(-1, str(len(historical)), str(len(current)))]
    return [
        (number, before, after)
        for number, (before, after) in enumerate(zip(historical, current), 1)
        if before != after
    ]


def scan_tracked_evidence(payload: bytes) -> dict[str, Any]:
    sample_hex = payload[:64].hex()
    sample_b64 = base64.b64encode(payload[:64]).decode("ascii")
    ascii_runs: list[str] = []
    for start in range(0, min(len(payload), 4096) - 8):
        run = payload[start:start + 8]
        if all(32 <= byte < 127 for byte in run):
            ascii_runs.append(run.decode("ascii"))
    host_patterns = (
        re.compile(r"[A-Za-z]:[\\](?![\\])"),
        re.compile(r"/Users/"),
        re.compile(r"/home/[a-z]"),
    )
    files = git("ls-files", ".openrecomp-phase11/evidence").splitlines()
    payload_violations: list[str] = []
    path_violations: list[str] = []
    for relative in files:
        blob = subprocess.run(
            ["git", "show", f"HEAD:{relative}"], cwd=str(ROOT), check=False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        check(f"safety:tracked:{relative}", blob.returncode == 0, relative)
        text = blob.stdout.decode("utf-8", "replace")
        lowered = text.lower()
        if sample_hex in lowered or sample_b64 in text:
            payload_violations.append(relative)
        elif any(candidate in text for candidate in ascii_runs):
            payload_violations.append(relative + ":ascii")
        if any(pattern.search(text) for pattern in host_patterns):
            path_violations.append(relative)
    return {
        "files_scanned": len(files),
        "private_payload_violations": sorted(set(payload_violations)),
        "host_path_violations": sorted(set(path_violations)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-90")
    parser.add_argument(
        "--phase10-worktree",
        default=str(ROOT.parent / "p11-90-phase10-regression"),
    )
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    phase10_worktree = pathlib.Path(options.phase10_worktree).resolve()
    scratch = P11 / "cache" / "p11-90"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    try:
        check("authority:branch", git("branch", "--show-current") == BRANCH, BRANCH)
        check("authority:head", git("rev-parse", "HEAD") == P11_RC_COMMIT, P11_RC_COMMIT)
        check("authority:tree", git("rev-parse", "HEAD^{tree}") == P11_RC_TREE, P11_RC_TREE)
        check("authority:commit-subject",
              git("show", "-s", "--format=%s", "HEAD")
              == "phase11: reconcile bounded terminal route at P11-07 blocker",
              "P11-RC subject")
        check("phase10-worktree:parent",
              phase10_worktree.parent == ROOT.parent.resolve()
              and phase10_worktree.name == "p11-90-phase10-regression",
              "fixed sibling worktree")
        check("phase10-worktree:exists", phase10_worktree.is_dir(), "present")

        def phase10_git(*args: str) -> str:
            completed = subprocess.run(
                ["git", *args], cwd=str(phase10_worktree), check=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8",
            )
            if completed.returncode != 0 or completed.stderr:
                raise RuntimeError(completed.stderr.strip() or "phase10 git failed")
            return completed.stdout.strip()

        check("phase10-worktree:branch",
              phase10_git("branch", "--show-current") == PHASE10_BRANCH,
              PHASE10_BRANCH)
        check("phase10-worktree:commit",
              phase10_git("rev-parse", "HEAD") == PHASE10_COMMIT,
              PHASE10_COMMIT)
        check("phase10-worktree:tree",
              phase10_git("rev-parse", "HEAD^{tree}") == PHASE10_TREE,
              PHASE10_TREE)

        context_marker = b"OPENRECOMP_PHASE11_VERIFICATION_CONTEXT=PASS files=28"
        for mode in ("prepare", "verify"):
            context = subprocess.run(
                [sys.executable, "tools/test_phase11_verification_context_v1.py",
                 "--mode", mode, "--evidence-dir", options.evidence_dir],
                cwd=str(ROOT), check=False, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            check(f"phase10-worktree:verification-context:{mode}",
                  context.returncode == 0 and context.stderr == b""
                  and context_marker in context.stdout,
                  context.stdout.decode("utf-8", "replace").strip())
        context_record = json.loads(
            (evidence / "verification_context.json").read_text(encoding="utf-8")
        )
        check("phase10-worktree:verification-context-digest",
              context_record["aggregate_residue_sha256"]
              == "40e4f23a35f40c5d25da630467d46f5e8ad8409a40efff8412892217447a8349"
              and context_record["file_count"] == 28,
              context_record["aggregate_residue_sha256"])
        check("phase10-worktree:tracked-clean",
              phase10_git("status", "--porcelain", "--untracked-files=no") == "",
              "no tracked modification")

        source = subprocess.run(
            [sys.executable, str(P11 / "src" / "p11_source_manifest_v1.py")],
            cwd=str(ROOT), check=False, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
        )
        check("source:p11-manifest",
              source.returncode == 0 and source.stderr == ""
              and source.stdout.startswith(
                  "OPENRECOMP_PHASE11_SOURCE_INTEGRITY=PASS entries="
              ), source.stdout.strip() or source.stderr.strip())

        implementation = git(
            "diff", "--name-only", "HEAD", "--",
            ".openrecomp-phase11/runtime", ".openrecomp-phase11/src",
            "tools/test_phase11_boundary_v1.py",
            "tools/test_phase11_causality_v1.py",
            "tools/test_phase11_event_contract_v1.py",
            "tools/test_phase11_initialization_v1.py",
            "tools/test_phase11_gpu_v1.py",
            "tools/test_phase11_gpu_closure_v1.py",
            "tools/test_phase11_b0_table_v1.py",
            "tools/test_phase11_queue_reconciliation_v1.py",
        )
        check("delta:no-runtime-or-completed-gate-change", implementation == "",
              implementation or "none")
        expected_p11_02_delta = [
            (
                119,
                '    "0x80015fa4": ("B0", 0x57, None),',
                '    "0x80015fa4": ("B0", 0x57, "GetB0Table"),',
            ),
            (
                129,
                '    "0x80026f74": ("B0", 0x57, None),',
                '    "0x80026f74": ("B0", 0x57, "GetB0Table"),',
            ),
        ]
        observed_p11_02_delta = p11_02_expectation_delta()
        check("delta:p11-02-proven-metadata-expectation-only",
              observed_p11_02_delta == expected_p11_02_delta,
              observed_p11_02_delta)

        rc_official = json.loads(
            (P11 / "evidence/P11-RC/official_runs.json").read_text(encoding="utf-8")
        )
        rc_determinism = json.loads(
            (P11 / "evidence/P11-RC/determinism.json").read_text(encoding="utf-8")
        )
        check("p11-rc:official-pass",
              all(rc_official[key] for key in (
                  "identical_raw", "identical_lf", "returncode_zero_both",
                  "stderr_empty_both", "markers_present_both",
              )), "official")
        check("p11-rc:deterministic-sidecars",
              rc_determinism["artifacts_identical"] is True, "sidecars")
        check("p11-rc:no-fail-lines",
              all(not run["fail_lines"] for run in rc_official["runs"]), "no FAIL")
        rc_tree = git("rev-parse", "HEAD:.openrecomp-phase11/evidence/P11-RC")

        rc, stdout, stderr, p10_target = run_phase10_gate(phase10_worktree)
        check("phase1-10:p10-90:exit", rc == 0, rc)
        check("phase1-10:p10-90:stderr", stderr == b"", stderr[:160].decode("utf-8", "replace"))
        check("phase1-10:p10-90:marker", P10_90[1].encode("utf-8") in stdout, P10_90[1])
        p10_hash = sha256_bytes(stdout)
        check("phase1-10:p10-90:stdout-identity", p10_hash == P10_90[2], p10_hash)
        p10_tests = json.loads((p10_target / "p10_90_tests.json").read_text(encoding="utf-8"))
        check("phase1-10:p10-90:checks", p10_tests["failed"] == 0, p10_tests["tests"])

        phase11_records: list[dict[str, Any]] = []
        for stage, script, tests_name in P11_GATES:
            target = scratch / stage
            rc, stdout, stderr = run_gate(script, target)
            check(f"phase11:{stage}:exit", rc == 0, rc)
            check(f"phase11:{stage}:stderr", stderr == b"",
                  stderr[:160].decode("utf-8", "replace"))
            marker = f"OPENRECOMP_{stage.replace('-', '_')}=PASS".encode("utf-8")
            check(f"phase11:{stage}:marker", marker in stdout, marker.decode("utf-8"))
            observed = sha256_bytes(stdout)
            historical_stdout = committed_stdout(stage)
            current_expectations = {
                "P11-02": P11_02_CURRENT_STDOUT_SHA256,
                "P11-03": P11_03_CURRENT_STDOUT_SHA256,
            }
            expected = current_expectations.get(stage, historical_stdout)
            identity_kind = (
                "current-stdout-identity"
                if stage in current_expectations else "stdout-identity"
            )
            check(f"phase11:{stage}:{identity_kind}", observed == expected, observed)
            tests = json.loads((target / tests_name).read_text(encoding="utf-8"))
            failed = sum(item["status"] == "FAIL" for item in tests["checks"])
            check(f"phase11:{stage}:checks", failed == 0, len(tests["checks"]))
            if stage == "P11-02":
                check("phase11:P11-02:current-check-count",
                      len(tests["checks"]) == P11_02_CURRENT_TESTS,
                      len(tests["checks"]))
                site_table_item = next(
                    item for item in tests["checks"]
                    if item["check"] == "bios:site-table"
                )
                site_table = json.loads(site_table_item["detail"])
                check("phase11:P11-02:current-public-name",
                      site_table["0x80015fa4"] == ["B0", 0x57, "GetB0Table"]
                      and site_table["0x80026f74"] == ["B0", 0x57, "GetB0Table"],
                      "B0:0x57=GetB0Table at both sites")
                frontier = json.loads((target / "frontier.json").read_text(encoding="utf-8"))
                frontier_sites = {
                    item["site_hex"]: item
                    for item in frontier["bios_vector_classification"]["sites"]
                }
                metadata_only = all(
                    frontier_sites[address]["op_name"] is None
                    and frontier_sites[address]["service_id"] is None
                    and frontier_sites[address]["classification"]
                    == "BIOS_VECTOR_NOT_IMPLEMENTED"
                    and frontier_sites[address]["disposition"] == "FAIL_CLOSED"
                    for address in ("0x80015fa4", "0x80026f74")
                )
                check("phase11:P11-02:name-does-not-implement-service",
                      metadata_only, "metadata-only and fail-closed")
            if stage == "P11-03":
                check("phase11:P11-03:current-check-count",
                      len(tests["checks"]) == P11_03_CURRENT_TESTS,
                      len(tests["checks"]))
                frontier = json.loads((target / "frontier.json").read_text(encoding="utf-8"))
                check("phase11:P11-03:later-proven-versions",
                      frontier["bios_vector_classification"]["bios_version"] == "1.2.0"
                      and frontier["emission"]["semantics"]["semantics_version"] == "1.2.0"
                      and frontier["emission"]["semantics"]["rules_total"] == 51
                      and frontier["runtime_composition"]["runtime_version"] == "1.2.0",
                      "bios/semantics/runtime=1.2.0 rules=51")
                frontier_sites = {
                    item["site_hex"]: item
                    for item in frontier["bios_vector_classification"]["sites"]
                }
                metadata_only = all(
                    frontier_sites[address]["documented_name"] == "GetB0Table"
                    and frontier_sites[address]["op_name"] is None
                    and frontier_sites[address]["service_id"] is None
                    and frontier_sites[address]["classification"]
                    == "BIOS_VECTOR_NOT_IMPLEMENTED"
                    and frontier_sites[address]["disposition"] == "FAIL_CLOSED"
                    for address in ("0x80015fa4", "0x80026f74")
                )
                check("phase11:P11-03:name-does-not-implement-service",
                      metadata_only, "metadata-only and fail-closed")
            phase11_records.append({
                "stage": stage,
                "checks": len(tests["checks"]),
                "stdout_sha256_raw": observed,
                "historical_stdout_sha256_raw": historical_stdout,
                "committed_stdout_match": stage not in current_expectations,
                "identity_basis": (
                    "current shared contracts after later proven Phase-11 refinements"
                    if stage in current_expectations else "committed stage stdout"
                ),
            })

        evidence_delta = git(
            "status", "--porcelain", "--untracked-files=no", "--",
            ".openrecomp-phase11/evidence/P11-00",
            ".openrecomp-phase11/evidence/P11-01",
            ".openrecomp-phase11/evidence/P11-02",
            ".openrecomp-phase11/evidence/P11-03",
            ".openrecomp-phase11/evidence/P11-04",
            ".openrecomp-phase11/evidence/P11-05",
            ".openrecomp-phase11/evidence/P11-06",
            ".openrecomp-phase11/evidence/P11-07",
            ".openrecomp-phase11/evidence/P11-RC",
        )
        check("evidence:executed-history-untouched", evidence_delta == "",
              evidence_delta or "clean")

        state = (P11 / "STATE.md").read_text(encoding="utf-8")
        queue = (P11 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        for marker in (GPU_MARKER, INITIALIZATION_MARKER, FRAME_MARKER,
                       PLAYABILITY_MARKER, GENERAL_MARKER):
            check(f"claims:{marker}", marker in state, marker)
        check("claims:highest-C", "milestone C remains the highest proven" in state,
              "milestone C")
        for stage in ("P11-08", "P11-09", "P11-10", "P11-11", "P11-12"):
            check(f"queue:{stage}:not-executed",
                  f"| {stage} | NOT EXECUTED — no stage verdict assigned |" in state,
                  stage)
        check("queue:authorized-route",
              "`P11-RC -> P11-90 -> P11-91 -> P11-99`" in queue, "route")

        payload_path = ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
        payload = payload_path.read_bytes()[0x800:0x1800]
        safety = scan_tracked_evidence(payload)
        check("safety:files-scanned", safety["files_scanned"] >= 120,
              safety["files_scanned"])
        check("safety:no-private-payload",
              not safety["private_payload_violations"],
              safety["private_payload_violations"])
        check("safety:no-host-paths",
              not safety["host_path_violations"], safety["host_path_violations"])

        record = {
            "schema": "openrecomp-phase11-whole-regression-v1",
            "stage": STAGE,
            "baseline": {
                "branch": BRANCH,
                "commit": P11_RC_COMMIT,
                "tree": P11_RC_TREE,
            },
            "phase1_through_phase10": {
                "gate": P10_90[0],
                "reconstruction": "verified untracked Phase-2 Git blobs in an isolated worktree on the frozen Phase-10 branch and commit",
                "verification_context": "verification_context.json",
                "historical_source_commit": context_record["historical_source"]["commit"],
                "historical_source_tree": context_record["historical_source"]["tree"],
                "frozen_untracked_files": context_record["file_count"],
                "aggregate_residue_sha256": context_record["aggregate_residue_sha256"],
                "branch": PHASE10_BRANCH,
                "commit": PHASE10_COMMIT,
                "tree": PHASE10_TREE,
                "checks": p10_tests["tests"],
                "stdout_sha256_raw": p10_hash,
                "committed_stdout_match": True,
            },
            "executed_phase11_stages": phase11_records,
            "p11_rc": {
                "evidence_tree": rc_tree,
                "official_runs": "PASS",
                "deterministic": True,
            },
            "reconciled_queue": {
                "unexecuted_stages": [
                    "P11-08", "P11-09", "P11-10", "P11-11", "P11-12",
                ],
                "stage_verdict_assigned": False,
                "terminal_route": ["P11-RC", "P11-90", "P11-91", "P11-99"],
            },
            "counts": {
                "phase10_whole_regression_checks": p10_tests["tests"],
                "executed_phase11_gates": len(phase11_records),
                "executed_phase11_checks": sum(item["checks"] for item in phase11_records),
                "p11_rc_checks": len(json.loads(
                    (P11 / "evidence/P11-RC/p11_rc_tests.json").read_text(encoding="utf-8")
                )["checks"]),
            },
            "safety": safety,
            "claims": {
                "A": "INHERITED_PROVEN",
                "B": "NOT_PROVEN",
                "C": "PROVEN_PRIVATE_FIXTURE_BOUNDED",
                "D": "NOT_PROVEN",
                "E": "NOT_PROVEN",
                "F": "NOT_PROVEN",
                "G": "NOT_PROVEN",
                "general_ps1_compatibility": "NOT_PROVEN_PERMANENT",
            },
        }
        write_json(evidence / "whole_regression.json", record)
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:
        RESULTS.append({
            "check": "gate:exception", "status": "FAIL",
            "detail": f"{type(exc).__name__}: {exc}",
        })

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    ordered = sorted(RESULTS, key=lambda item: item["check"])
    tests = {
        "schema": "openrecomp-phase11-tests-v1",
        "stage": STAGE,
        "status": status,
        "checks": ordered,
        "summary": {
            "passed": sum(item["status"] == "PASS" for item in ordered),
            "failed": len(failed),
        },
    }
    write_json(evidence / "p11_90_tests.json", tests)
    for item in ordered:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P11_90={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(ordered)}")
    print("OPENRECOMP_PHASE11_HIGHEST_MILESTONE=C_PRIVATE_FIXTURE_BOUNDED")
    print(INITIALIZATION_MARKER)
    print(FRAME_MARKER)
    print(PLAYABILITY_MARKER)
    print(GENERAL_MARKER)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
