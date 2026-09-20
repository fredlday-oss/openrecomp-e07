#!/usr/bin/env python3
"""OpenRecomp Phase-8 whole-project regression gate (P8-90).

This is the expensive terminal gate.  It verifies, on one audited tree:

* the exact frozen Phase-7 baseline identity (tag object, commit, tree) and
  the pinned Phase-7 terminal evidence;
* the frozen Phase-1..Phase-6 boundary identities recorded by Phase 7;
* the frozen P7-90 whole-regression record (hash chain) and the frozen
  P6-90 record identity it carries (the documented coverage boundary);
* a live Phase-1 host-gate re-run with byte-identical stdout;
* a live re-run of all fifteen Phase-7 stage gates into scratch evidence,
  each with byte-identical stdout to the frozen official capture;
* a live re-run of all twelve completed Phase-8 official gates, each with
  byte-identical stdout to its committed official capture, plus this
  regression's own determinism across two runs.

No historical evidence is modified: Phase-7 gates are redirected to scratch
evidence directories and the Phase-8 boundary gate runs in verify-only mode.

On success it emits::

    OPENRECOMP_P8_90=PASS
    OPENRECOMP_PHASE8_WHOLE_REGRESSION_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_whole_regression_v1.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]

EVIDENCE_DIR = ROOT / ".openrecomp-phase8" / "evidence" / "P8-90"
SCRATCH = ROOT / ".openrecomp-phase8" / "build" / "P8-90" / "scratch"

STAGE = "P8-90"
STAGE_MARKER = "OPENRECOMP_P8_90"
FEATURE_MARKER = "OPENRECOMP_PHASE8_WHOLE_REGRESSION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

BASELINE_TAG = "openrecomp-phase7-pass"
BASELINE_TAG_OBJECT = "b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800"
BASELINE_COMMIT = "2917aa6549ab975cffdeb50120514c1723f7e493"
BASELINE_TREE = "59529c130d759ceb1ca9e6c65a510fa373656b01"
BRANCH = "phase8/mips32-end-to-end-native-v1"

FROZEN_P7_EVIDENCE = {
    ".openrecomp-phase7/evidence/P7-99/RESULT.md": "88648d7fdecf06e5dd9c089a1a2f032ddcbb4df4c1ff13df30144d87ea398a73",
    ".openrecomp-phase7/evidence/P7-99/terminal_verdict.json": "1f26733ed712299e3ad9d278432856e76facd473df92590c22f57e6dacf01955",
    ".openrecomp-phase7/evidence/P7-99/verdict_record.json": "51ff2374c067ddb7c1063880d33118b807104bae8861c8d87b1e66e1abbb1d00",
    ".openrecomp-phase7/evidence/P7-99/p7_99_tests.json": "b9d77b29fc35d3c32a87f6c4956c0ed7246595b549de271427b238d718aa36d9",
    ".openrecomp-phase7/STATE.md": "23c423e9163e3f7fc873b06e293ee96bd85a18b22ca655a24d62d35453f6eb33",
    ".openrecomp-phase7/STAGE_QUEUE.md": "6162bda0a5ec2c92b817d31bb2968a2f32f10df3ce80139cd8d68c1946ced377",
    ".openrecomp-phase7/HANDOFF.md": "65a56a974f0e651b74b7c0c3399b55c8a45ca1513ddebcb2cde0de3f0447c89a",
    ".openrecomp-phase7/SOURCE_SHA256SUMS.txt": "d5da028111b4e8d9cf24e961270393d34aba2a8f6e7d63279739a0afa69fef7a",
}
FROZEN_P7_90_RECORD = {
    ".openrecomp-phase7/evidence/P7-90/RESULT.md": "ce104465ae6b171d864d900994fc844e68fccd0240b9e81d759b4f00b5cae9d5",
    ".openrecomp-phase7/evidence/P7-90/p7_90_tests.json": "c0b4433bdba9cc2bd80186652fcef4dddb824500839497821e05c99b6fda88d5",
    ".openrecomp-phase7/evidence/P7-90/whole_regression.json": "53cc8ceea69e20244769265aff0c316b419bea8ab897a7a89f355fdbb85b4c38",
    ".openrecomp-phase7/evidence/P7-90/determinism.json": "6042ef4de307cbc9b0d4d120315d600adb3288bdf04ec5cacee74b4da9a95903",
    ".openrecomp-phase7/evidence/P7-90/official_runs.json": "b31a5d6be762c443c399fc6eab820d03a407e78b80118852973ea124bfefe88c",
}
FROZEN_BOUNDARIES = {
    "phase1_commit": "46c2f971e1a42cf49bd936bad94697b81bf31002",
    "phase2_commit": "01b1d7cba8c931fca95d041389cfb1902b7c89fe",
    "phase3_tag_object": "ac31524504b1b5cc63aabcfd5132a3eb4275e8e9",
    "phase3_commit": "e16e4b29b90f379615f1af97e47747cd1d531796",
    "phase3_tree": "a940f0d84a32adaf191f7ff2bebfb24cc855cde0",
    "phase4_tag_object": "e7eaab18fee267b3d7962db13835c9e14dd77fc2",
    "phase4_commit": "b3c71fb690f00b4811e8ec30c28f7725141295d0",
    "phase4_tree": "f2ca3080915aa68f403526b89dfc17454687aed6",
    "phase5_tag_object": "b5d6832ba2374b810f4c24500ed9093a9481fd8d",
    "phase5_commit": "e8d3627a622d0ca3196b117c5112f29fabdb49e7",
    "phase5_tree": "468fb9788350de393d3de2ca9471b7d874ee8dc9",
    "phase6_commit": "1643817d43196c43155805249137e4b4e4a21eb1",
    "phase6_tree": "cda3f535be43dc6f3d4b457d11d356ae39ea34af",
}
P7_90_COMMIT = "519c0e7313eb99d6dbd83a4853c070bd5fdf5d17"
PHASE6_90_RECORD_SHA256 = "930f6ec57ea62b8e2e5aceb0fff2fc1369eafc876f51f6bf7f933b64bd8cb37f"
PHASE6_90_STDOUT_SHA256 = "120d002830037ac26d5780e0cdb820f8dbd4bd55415e6f2b9aabb08cda8c97fa"
PHASE1_HOST_GATES_STDOUT_SHA256 = "2a9d1bba538b91605d61c3c47d8208cc7012cdfe49042f088c409dc54729cc35"

PHASE8_GATES = (
    ("P8-00", "tools/test_phase8_boundary_v1.py", ["--verify-only"], "OPENRECOMP_P8_00=PASS"),
    ("P8-01", "tools/test_phase8_fixture_v1.py", [], "OPENRECOMP_P8_01=PASS"),
    ("P8-02", "tools/test_phase8_frontier_v1.py", [], "OPENRECOMP_P8_02=PASS"),
    ("P8-03", "tools/test_phase8_structure_v1.py", [], "OPENRECOMP_P8_03=PASS"),
    ("P8-04", "tools/test_phase8_translation_v1.py", [], "OPENRECOMP_P8_04=PASS"),
    ("P8-05", "tools/test_phase8_runtime_v1.py", [], "OPENRECOMP_P8_05=PASS"),
    ("P8-06", "tools/test_phase8_emission_v1.py", [], "OPENRECOMP_P8_06=PASS"),
    ("P8-07", "tools/test_phase8_native_build_v1.py", [], "OPENRECOMP_P8_07=PASS"),
    ("P8-08", "tools/test_phase8_native_execution_v1.py", [], "OPENRECOMP_P8_08=PASS"),
    ("P8-09", "tools/test_phase8_reference_equivalence_v1.py", [], "OPENRECOMP_P8_09=PASS"),
    ("P8-10", "tools/test_phase8_workflow_v1.py", [], "OPENRECOMP_P8_10=PASS"),
    ("P8-11", "tools/test_phase8_hardening_v1.py", [], "OPENRECOMP_P8_11=PASS"),
    ("P8-12", "tools/test_phase8_evidence_closure_v1.py", [], "OPENRECOMP_P8_12=PASS"),
)
DOCUMENTED_PRIOR_TRACKED_DIFF = {
    ".openrecomp-phase3/evidence/P3-00/p3_00_tests.json",
    ".openrecomp-phase3/evidence/P3-00/residue_manifest.txt",
}

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL", "detail": detail})
        raise AssertionError(f"{label}: condition failed ({detail})")
    RESULTS.append({"check": label, "status": "PASS", "detail": detail})
    print(f"PASS: {label}")


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git failed")
    return result.stdout.strip()


def run_gate(script: str, extra: list[str]) -> tuple[int, bytes, bytes]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / script), *extra],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.returncode, completed.stdout, completed.stderr


def main() -> int:
    try:
        # frozen Phase-7 baseline and terminal evidence
        check("baseline:tag-object", git("rev-parse", BASELINE_TAG) == BASELINE_TAG_OBJECT, BASELINE_TAG_OBJECT)
        check("baseline:commit", git("rev-parse", f"{BASELINE_TAG}^{{commit}}") == BASELINE_COMMIT, BASELINE_COMMIT)
        check("baseline:tree", git("rev-parse", f"{BASELINE_TAG}^{{tree}}") == BASELINE_TREE, BASELINE_TREE)
        check("branch:name", git("branch", "--show-current") == BRANCH, BRANCH)
        for rel, digest in sorted(FROZEN_P7_EVIDENCE.items()):
            check(f"frozen:p7-terminal:{rel}", sha256_file(ROOT / rel) == digest, digest)
        for rel, digest in sorted(FROZEN_P7_90_RECORD.items()):
            check(f"frozen:p7-90-record:{rel}", sha256_file(ROOT / rel) == digest, digest)
        phase6_tag = git("tag", "-l", "openrecomp-phase6-pass")
        check("phase6:tag-absent", phase6_tag == "", phase6_tag or "absent")
        boundary_tags = {
            "phase3": "openrecomp-phase3-pass",
            "phase4": "openrecomp-phase4-pass",
            "phase5": "openrecomp-phase5-pass",
        }
        for phase, tag in boundary_tags.items():
            check(f"boundary:{phase}:tag-object", git("rev-parse", tag) == FROZEN_BOUNDARIES[f"{phase}_tag_object"], FROZEN_BOUNDARIES[f"{phase}_tag_object"])
            check(f"boundary:{phase}:commit", git("rev-parse", f"{tag}^{{commit}}") == FROZEN_BOUNDARIES[f"{phase}_commit"], FROZEN_BOUNDARIES[f"{phase}_commit"])
            check(f"boundary:{phase}:tree", git("rev-parse", f"{tag}^{{tree}}") == FROZEN_BOUNDARIES[f"{phase}_tree"], FROZEN_BOUNDARIES[f"{phase}_tree"])
        for phase in ("phase1", "phase2", "phase6"):
            ancestor = subprocess.run(
                ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", FROZEN_BOUNDARIES[f"{phase}_commit"], BASELINE_COMMIT],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).returncode == 0
            check(f"boundary:{phase}:ancestor", ancestor, FROZEN_BOUNDARIES[f"{phase}_commit"])
        check("boundary:phase6:tree", git("rev-parse", f"{FROZEN_BOUNDARIES['phase6_commit']}^{{tree}}") == FROZEN_BOUNDARIES["phase6_tree"], FROZEN_BOUNDARIES["phase6_tree"])
        record = json.loads((ROOT / ".openrecomp-phase7" / "evidence" / "P7-90" / "whole_regression.json").read_text(encoding="utf-8"))
        check("p7-90:phase6-record", record["phase6_whole_regression"]["record_sha256"] == PHASE6_90_RECORD_SHA256, PHASE6_90_RECORD_SHA256)
        check("p7-90:phase6-stdout", record["phase6_whole_regression"]["official_stdout_sha256_raw"] == PHASE6_90_STDOUT_SHA256, PHASE6_90_STDOUT_SHA256)
        check("p7-90:stage-gates-count", len(record["phase7_stage_gates"]) == 15, str(len(record["phase7_stage_gates"])))

        # prior-tree cleanliness
        changed = git("diff", "--name-only", BASELINE_COMMIT, "--", *[f".openrecomp-phase{i}" for i in range(1, 8)])
        changed_set = set(filter(None, changed.splitlines()))
        check("frozen:no-undocumented-prior-diff", changed_set <= DOCUMENTED_PRIOR_TRACKED_DIFF, ",".join(sorted(changed_set)) or "none")

        # Phase-1 host gates live
        rc, stdout, stderr = run_gate("tools/phase1_host_gates_v1.py", [])
        check("phase1-host-gates:exit", rc == 0, str(rc))
        check("phase1-host-gates:stderr", stderr == b"", stderr[:120].decode("ascii", "replace"))
        check("phase1-host-gates:stdout-identity", hashlib.sha256(stdout).hexdigest() == PHASE1_HOST_GATES_STDOUT_SHA256, hashlib.sha256(stdout).hexdigest())
        check("phase1-host-gates:markers", b"OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2" in stdout, "markers")

        # Phase-7 stage gates live in a reconstructed pre-verdict context.
        # The frozen Phase-7 stage gates assert the pre-verdict control-plane
        # markers (the terminal marker reserved NOT_PROVEN), so they are
        # re-run in a temporary worktree at the frozen P7-90 commit -- the
        # same reconstruction technique the frozen P7-00 gate uses -- and
        # redirected to scratch evidence so no frozen evidence is modified.
        if SCRATCH.exists():
            shutil.rmtree(SCRATCH)
        SCRATCH.mkdir(parents=True, exist_ok=True)
        phase7_counts = []
        recon = pathlib.Path(tempfile.mkdtemp(prefix="p8_p7_recon_"))
        created = False
        try:
            added = subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(recon), P7_90_COMMIT],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            created = added.returncode == 0
            check("p7-recon:worktree", created, added.stderr.strip()[:200] or P7_90_COMMIT)
            recon_head = subprocess.run(
                ["git", "-C", str(recon), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout.strip()
            check("p7-recon:commit", recon_head == P7_90_COMMIT, recon_head)
            recon_state = (recon / ".openrecomp-phase7" / "STATE.md").read_text(encoding="utf-8")
            check(
                "p7-recon:pre-verdict-context",
                "TRANSLATION_FRONTIER_STATUS=NOT_PROVEN" in recon_state,
                "terminal marker reserved",
            )
            for gate in record["phase7_stage_gates"]:
                stage = gate["stage"]
                target = SCRATCH / stage
                target.mkdir(parents=True, exist_ok=True)
                completed = subprocess.run(
                    [sys.executable, str(recon / gate["script"]), "--evidence-dir", str(target)],
                    cwd=str(recon),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                stdout = completed.stdout
                stderr = completed.stderr
                check(f"p7:{stage}:exit", completed.returncode == 0, str(completed.returncode))
                check(f"p7:{stage}:stderr", stderr == b"", stderr[:120].decode("ascii", "replace"))
                check(f"p7:{stage}:stdout-identity", hashlib.sha256(stdout).hexdigest() == gate["stdout_sha256_raw"], hashlib.sha256(stdout).hexdigest())
                for marker in gate["markers"]:
                    check(f"p7:{stage}:marker:{marker.split('=')[0]}", marker.encode("utf-8") in stdout, marker)
                tests = 0
                for line in stdout.decode("utf-8", "replace").splitlines():
                    if "=PASS tests=" in line:
                        tests = int(line.rsplit("tests=", 1)[1])
                        break
                phase7_counts.append({"stage": stage, "tests": tests, "stdout_sha256_raw": gate["stdout_sha256_raw"]})
        finally:
            if created:
                subprocess.run(
                    ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(recon)],
                    capture_output=True,
                )
                subprocess.run(["git", "-C", str(ROOT), "worktree", "prune"], capture_output=True)
            else:
                shutil.rmtree(recon, ignore_errors=True)
        check("p7-recon:removed", not recon.exists(), "temporary worktree removed")

        # Phase-8 official gates live with committed capture identity
        phase8_counts = []
        for stage, script, extra, marker in PHASE8_GATES:
            runs_path = ROOT / ".openrecomp-phase8" / "evidence" / stage / "official_runs.json"
            runs = json.loads(runs_path.read_text(encoding="utf-8"))
            expected_stdout = runs["runs"][0]["stdout_sha256_raw"]
            rc, stdout, stderr = run_gate(script, extra)
            check(f"p8:{stage}:exit", rc == 0, str(rc))
            check(f"p8:{stage}:stderr", stderr == b"", stderr[:120].decode("ascii", "replace"))
            check(f"p8:{stage}:marker", marker.encode("utf-8") in stdout, marker)
            check(f"p8:{stage}:stdout-identity", hashlib.sha256(stdout).hexdigest() == expected_stdout, hashlib.sha256(stdout).hexdigest())
            tests = 0
            for line in stdout.decode("utf-8", "replace").splitlines():
                if "=PASS tests=" in line:
                    tests = int(line.rsplit("tests=", 1)[1])
                    break
            phase8_counts.append({"stage": stage, "tests": tests, "stdout_sha256_raw": expected_stdout})

        total = sum(item["tests"] for item in phase7_counts + phase8_counts)

        write_payload = {
            "stage": STAGE,
            "decision": "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL",
            "phase1_host_gates": {"stdout_sha256_raw": PHASE1_HOST_GATES_STDOUT_SHA256, "markers": ["OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2"]},
            "phase6_90_record": {"record_sha256": PHASE6_90_RECORD_SHA256, "stdout_sha256_raw": PHASE6_90_STDOUT_SHA256, "coverage": record["phase6_whole_regression"]["context"]},
            "phase7_stage_gates": phase7_counts,
            "phase8_stage_gates": phase8_counts,
            "total_reverified_tests": total,
            "markers": {
                "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
                "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
            },
        }
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        (EVIDENCE_DIR / "whole_regression.json").write_bytes(
            (json.dumps(write_payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    status = "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    record = {
        "stage": STAGE,
        "stage_name": "Phase-8 whole-project regression",
        "status": status,
        "tests": len(RESULTS),
        "passed": sum(1 for item in RESULTS if item["status"] == "PASS"),
        "failed": sum(1 for item in RESULTS if item["status"] != "PASS"),
        "checks": RESULTS,
        "failure": None if status == "PASS" else [item for item in RESULTS if item["status"] != "PASS"],
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={len(RESULTS)}",
            "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
            "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
        },
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "p8_90_tests.json").write_bytes(
        (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )

    for item in RESULTS:
        if item["status"] != "PASS":
            print(f"FAIL: {item['check']} :: {item.get('detail', '')}")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(RESULTS)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
