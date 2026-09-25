#!/usr/bin/env python3
"""Deterministic P17-00 Phase-17 bootstrap / frozen-baseline gate."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase17/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p17_contracts_v1 as contract
import p17_fixture_verification_v1 as fixture
from p17_gate_v1 import assert_public_safe, Gate, reject_private_path, run_stage, write_json
import p17_frozen_phase16_boundary_v1 as p16_boundary
import p17_frozen_phase16_integrity_v1 as p16_integrity

STAGE = "P17-00"

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
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True).stdout.strip()


def fixture_root() -> pathlib.Path:
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def run_p16_boundary() -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / ".openrecomp-phase17/src/p17_frozen_phase16_boundary_v1.py")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    ok = completed.returncode == 0 and "OPENRECOMP_PHASE17_P16_BOUNDARY_FROZEN=PASS" in completed.stdout
    return ok, completed.stdout.strip() if not ok else "frozen-boundary-ok"


def run_p16_integrity() -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / ".openrecomp-phase17/src/p17_frozen_phase16_integrity_v1.py")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    ok = completed.returncode == 0 and "OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS" in completed.stdout
    return ok, completed.stdout.strip() if not ok else "source-integrity-ok"


def run_p15_boundary() -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, ".openrecomp-phase16/src/p16_frozen_phase15_boundary_v1.py"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    ok = completed.returncode == 0 and "OPENRECOMP_PHASE16_P15_BOUNDARY_FROZEN=PASS" in completed.stdout
    return ok, completed.stdout.strip() if not ok else "frozen-boundary-ok"


def run_p15_integrity() -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, ".openrecomp-phase16/src/p16_frozen_phase15_integrity_v1.py"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    ok = completed.returncode == 0 and "OPENRECOMP_PHASE16_P15_SOURCE_INTEGRITY=PASS" in completed.stdout
    # Do not echo the legacy helper output into tracked evidence; it contains a
    # self-referential "frozen-commit==HEAD" classification that is not stable
    # for the Phase-17 candidate boundary.
    return ok, completed.stdout.strip() if not ok else "source-integrity-ok"


def negative_fixture_absent() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        bogus = pathlib.Path(tmp) / "does-not-exist"
        ok, _ = fixture.verify_fixture(bogus)
        return not ok


def negative_fixture_digest_mismatch() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        fixture_dir = pathlib.Path(tmp)
        (fixture_dir / "Disney's Hercules Action Game (USA).bin").write_bytes(b"wrong bin")
        (fixture_dir / "Disney's Hercules Action Game (USA).cue").write_bytes(b"wrong cue")
        (fixture_dir / "SLUS_005.29").write_bytes(b"wrong slus")
        ok, _ = fixture.verify_fixture(fixture_dir)
        return not ok


def negative_fixture_malformed_metadata() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        fixture_dir = pathlib.Path(tmp)
        (fixture_dir / "Disney's Hercules Action Game (USA).bin").write_bytes(b"x" * 409_452_624)
        (fixture_dir / "Disney's Hercules Action Game (USA).cue").write_bytes(b"NOT A CUE\n")
        (fixture_dir / "SLUS_005.29").write_bytes(b"x" * 129_024)
        ok, report = fixture.verify_fixture(fixture_dir)
        return not ok and not report.get("bin_hash_ok", False)


FORBIDDEN_PRIVATE_PATHS = (
    "/home/fred/private/location",
    "/Users/example/private/location",
    "/tmp/private-fixture",
    r"C:\private\fixture",
    r"D:\OpenRecomp\fixtures\private",
    r"\\server\share\private",
)


def negative_private_path_safety() -> dict[str, object]:
    """Assert rejection for each exact private-path case through assert_public_safe."""
    results: dict[str, object] = {}
    all_rejected = True
    for path in FORBIDDEN_PRIVATE_PATHS:
        gate = Gate("private-path")
        try:
            assert_public_safe(gate, "private-path", {"probe_path": path})
            results[path] = {"rejected": False}
            all_rejected = False
        except AssertionError:
            results[path] = {"rejected": True}
    return {"all_rejected": all_rejected, "cases": results}


def positive_safe_relative_path() -> bool:
    """Ordinary public-safe relative path must pass through assert_public_safe."""
    gate = Gate("positive-safe")
    try:
        assert_public_safe(gate, "positive-safe", {"probe_path": "relative/synthetic/control.bin"})
        return True
    except AssertionError:
        return False


def negative_manifest_completeness() -> dict[str, object]:
    """Directly assert fail-closed rejection for incomplete/malformed manifests."""
    expected = p16_integrity.expected_inventory_from_frozen_commit()
    real_manifest = ROOT / ".openrecomp-phase16" / "SOURCE_SHA256SUMS.txt"
    real_text = real_manifest.read_text(encoding="utf-8")
    real_lines = [line for line in real_text.splitlines() if line.strip()]
    first_entry = real_lines[0]
    middle_entry = real_lines[len(real_lines) // 2]

    def make_case(name: str, content: str | None) -> dict[str, object]:
        rejected, report = p16_integrity.negative_manifest_case(name, content, expected)
        return {"name": name, "rejected": rejected, "report": report}

    cases = [
        make_case("empty-manifest", ""),
        make_case("malformed-manifest", "this-is-not-a-manifest\nno-digest-here *foo\n"),
        make_case("one-valid-entry", first_entry + "\n"),
        make_case("missing-middle-entry", "\n".join([l for l in real_lines if l != middle_entry]) + "\n"),
        make_case("unexpected-extra-entry", real_text + "0" * 64 + " *extra/phase16/file.py\n"),
    ]
    all_rejected = all(case["rejected"] for case in cases)
    return {"all_rejected": all_rejected, "cases": cases}


def nondeterminism_rejection_test() -> bool:
    """Run a deliberately nondeterministic gate and confirm the runner rejects it."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        script = tmp_path / "nondeterministic_gate.py"
        script.write_text(
            """#!/usr/bin/env python3
import json, pathlib, sys, time
root = pathlib.Path(__file__).resolve().parent
evidence = root / "evidence"
evidence.mkdir(parents=True, exist_ok=True)
# Genuinely different output on each run
value = time.time_ns()
(root / "evidence" / "artifact.json").write_text(
    json.dumps({"value": value}, sort_keys=True) + "\n", encoding="utf-8")
print("OPENRECOMP_P17_00=PASS")
""",
            encoding="utf-8",
        )
        runner = ROOT / ".openrecomp-phase17/src/p17_stage_runner_v1.py"
        completed = subprocess.run(
            [sys.executable, str(runner),
             "--stage", "P17-00",
             "--script", str(script),
             "--evidence-dir", str(tmp_path / "evidence"),
             "--tests-json", "artifact.json"],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        try:
            result = json.loads(completed.stdout)
        except Exception:
            return False
        return (
            completed.returncode != 0
            and result.get("runner_status") == "FAIL"
            and result.get("artifacts_identical") is False
        )


def temp_repository_test() -> bool:
    """Copy Phase-17 gate code into a fresh git repo and verify it still passes."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        subprocess.run(["git", "init", "--quiet"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), check=True)

        # Copy Phase-17 source and gate
        dest_src = tmp_path / ".openrecomp-phase17" / "src"
        dest_src.mkdir(parents=True)
        for src_file in (ROOT / ".openrecomp-phase17/src").glob("*.py"):
            shutil.copy2(src_file, dest_src / src_file.name)
        dest_tools = tmp_path / "tools"
        dest_tools.mkdir(parents=True)
        shutil.copy2(ROOT / "tools/test_phase17_bootstrap_v1.py", dest_tools / "test_phase17_bootstrap_v1.py")

        # Create synthetic fixtures with the correct hashes/sizes in the temp repo
        fixture_dir = tmp_path / "fixtures" / "psx" / "hercules"
        fixture_dir.mkdir(parents=True)
        real_fixture_dir = fixture_root()
        if not (real_fixture_dir / "Disney's Hercules Action Game (USA).bin").is_file():
            return False
        for name in ("Disney's Hercules Action Game (USA).bin",
                     "Disney's Hercules Action Game (USA).cue",
                     "SLUS_005.29"):
            shutil.copy2(real_fixture_dir / name, fixture_dir / name)

        # Add and commit so HEAD exists
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "temp"], cwd=str(tmp_path), check=True)

        env = os.environ.copy()
        env["OPENRECOMP_HERCULES_FIXTURE_ROOT"] = str(fixture_dir)

        # Source manifest must pass in the temp repo
        manifest = subprocess.run(
            [sys.executable, ".openrecomp-phase17/src/p17_source_manifest_v1.py"],
            cwd=str(tmp_path), capture_output=True, text=True, env=env,
        )
        if manifest.returncode != 0 or "OPENRECOMP_PHASE17_SOURCE_INTEGRITY=PASS" not in manifest.stdout:
            return False

        # Bootstrap gate must pass in the temp repo
        bootstrap = subprocess.run(
            [sys.executable, "tools/test_phase17_bootstrap_v1.py",
             "--evidence-dir", ".openrecomp-phase17/evidence/P17-00"],
            cwd=str(tmp_path), capture_output=True, text=True, env=env,
        )
        return bootstrap.returncode == 0 and "OPENRECOMP_P17_00=PASS" in bootstrap.stdout


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 1. Verify frozen Phase-16 boundary and ancestry
    p16_ok, p16_out = run_p16_boundary()
    gate.check("phase16:boundary-frozen", p16_ok, p16_out)

    # 2. Verify frozen Phase-16 source integrity
    p16_int_ok, p16_int_out = run_p16_integrity()
    gate.check("phase16:sources-intact", p16_int_ok, p16_int_out)

    # 3. Verify frozen Phase-15 boundary and source integrity
    p15_ok, p15_out = run_p15_boundary()
    gate.check("phase15:boundary-frozen", p15_ok, p15_out)
    p15_int_ok, p15_int_out = run_p15_integrity()
    gate.check("phase15:sources-intact", p15_int_ok, p15_int_out)

    # 4. Verify Phase-17 control plane
    control_root = root / ".openrecomp-phase17"
    for filename in CONTROL_FILES:
        cpath = control_root / filename
        gate.check(f"control:{filename}", cpath.is_file() and cpath.stat().st_size > 0, filename)

    for dirname in REQUIRED_DIRS:
        dpath = control_root / dirname
        dpath.mkdir(parents=True, exist_ok=True)
        gate.check(f"dir:{dirname}", dpath.is_dir(), dirname)

    # 5. Verify private fixture files and record hashes (fail-closed)
    fx_root = fixture_root()
    fx_report = fixture.verify_fixture_with_callback(
        fx_root,
        lambda label, condition, detail="": gate.check(label, condition, str(detail)),
    )

    # 6. Verify no private fixture bytes tracked in git
    tracked = subprocess.run(["git", "ls-files"], cwd=str(root),
                             capture_output=True, text=True).stdout.splitlines()
    forbidden = (".bin", ".cue", "SLUS_005.29", "fixtures/psx/hercules")
    leaked = [name for name in tracked if any(token in name for token in forbidden)]
    gate.check("private:no-fixture-bytes-tracked", not leaked, ",".join(leaked))

    # 7. TITLE payload decoding state
    gate.check("title-payload:not-decoded", contract.TITLE_PAYLOAD_DECODING_STATE == "NOT_DECODED", "NOT_DECODED")

    # 8. Required negative tests
    gate.check("negative:fixture-absent", negative_fixture_absent(), "missing fixture rejected")
    gate.check("negative:fixture-digest-mismatch", negative_fixture_digest_mismatch(), "wrong digest rejected")
    gate.check("negative:fixture-malformed-metadata", negative_fixture_malformed_metadata(), "malformed metadata rejected")

    private_results = negative_private_path_safety()
    gate.check("negative:private-path-safety", private_results["all_rejected"],
               json.dumps(private_results["cases"], sort_keys=True))

    gate.check("positive:safe-relative-path", positive_safe_relative_path(),
               "ordinary public-safe relative path accepted")

    manifest_results = negative_manifest_completeness()
    gate.check("negative:manifest-completeness", manifest_results["all_rejected"],
               json.dumps([{"name": c["name"], "rejected": c["rejected"]} for c in manifest_results["cases"]],
                          sort_keys=True))

    nondet = subprocess.run(
        [sys.executable, str(ROOT / "tools/test_phase17_nondeterminism_v1.py")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    gate.check("negative:nondeterminism-rejected",
               nondet.returncode == 0 and "OPENRECOMP_P17_00_NONDETERMINISM_TEST=PASS" in nondet.stdout,
               nondet.stdout.strip())

    temp_repo = subprocess.run(
        [sys.executable, str(ROOT / "tools/test_phase17_temp_repository_v1.py")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    gate.check("negative:temp-repository",
               temp_repo.returncode == 0 and "OPENRECOMP_P17_00_TEMP_REPOSITORY_TEST=PASS" in temp_repo.stdout,
               temp_repo.stdout.strip())

    # 9. Output stable stage document (no branch, no current HEAD, no timestamps)
    bootstrap_doc = {
        "schema": "openrecomp-phase17-bootstrap-v1",
        "stage": STAGE,
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "predecessor_commit": contract.PHASE16_BASE_COMMIT,
        "predecessor_tree": contract.PHASE16_BASE_TREE,
        "phase15_base_commit": contract.PHASE15_BASE_COMMIT,
        "phase15_base_tree": contract.PHASE15_BASE_TREE,
        "phase14_base_commit": contract.PHASE14_BASE_COMMIT,
        "phase14_base_tree": contract.PHASE14_BASE_TREE,
        "fixture_provenance": {
            "bin_sha256": fx_report["bin_sha256"],
            "bin_size": fx_report["bin_size"],
            "cue_sha256": fx_report["cue_sha256"],
            "slus_sha256": fx_report["slus_sha256"],
            "slus_size": fx_report["slus_size"],
        },
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
        "title_payload_decoding_state": contract.TITLE_PAYLOAD_DECODING_STATE,
    }
    write_json(evidence / "bootstrap.json", bootstrap_doc)
    assert_public_safe(gate, "bootstrap", bootstrap_doc)

    # Negative-test audit trail is intentionally recorded separately so that
    # forbidden fixture-path strings (used only as test inputs) do not pollute
    # the stable bootstrap document.
    write_json(evidence / "negative_tests.json", {
        "schema": "openrecomp-phase17-negative-tests-v1",
        "stage": STAGE,
        "private_path_cases": private_results["cases"],
        "manifest_completeness_cases": [
            {"name": c["name"], "rejected": c["rejected"]} for c in manifest_results["cases"]
        ],
    })

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase17-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
            contract.FIRST_FRAME_READY_MARKER: "NO",
        },
        "next_stage": "P17-01",
    })

    gate.mark(contract.BOOTSTRAP_MARKER)
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase17/evidence/P17-00"))
