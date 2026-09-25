#!/usr/bin/env python3
"""Verify Phase-17 gate code works in a fresh temporary repository."""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        subprocess.run(["git", "init", "--quiet"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), check=True)

        # Copy Phase-17 source into temp repo
        dest_src = tmp_path / ".openrecomp-phase17" / "src"
        dest_src.mkdir(parents=True)
        for src_file in (ROOT / ".openrecomp-phase17/src").glob("*.py"):
            shutil.copy2(src_file, dest_src / src_file.name)

        # Copy control files used by bootstrap sanity checks
        dest_ctrl = tmp_path / ".openrecomp-phase17"
        for name in ("CONTROL_POLICY.md", "SCOPE.md", "STAGE_QUEUE.md",
                     "EVIDENCE_SCHEMA.md", "FIXTURE_POLICY.md", "STATE.md", "HANDOFF.md"):
            shutil.copy2(ROOT / ".openrecomp-phase17" / name, dest_ctrl / name)

        # Copy all Phase-17 gate scripts
        dest_tools = tmp_path / "tools"
        dest_tools.mkdir(parents=True)
        for tool_file in (ROOT / "tools").glob("test_phase17_*.py"):
            shutil.copy2(tool_file, dest_tools / tool_file.name)

        # Synthetic fixtures
        fixture_dir = tmp_path / "fixtures" / "psx" / "hercules"
        fixture_dir.mkdir(parents=True)
        real_fixture_dir = ROOT.parents[1] / "fixtures" / "psx" / "hercules"
        if not (real_fixture_dir / "Disney's Hercules Action Game (USA).bin").is_file():
            print("OPENRECOMP_P17_00_TEMP_REPOSITORY_TEST=FAIL real-fixtures-unavailable")
            return 1
        for name in ("Disney's Hercules Action Game (USA).bin",
                     "Disney's Hercules Action Game (USA).cue",
                     "SLUS_005.29"):
            shutil.copy2(real_fixture_dir / name, fixture_dir / name)

        # Commit so HEAD exists
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "temp"], cwd=str(tmp_path), check=True)

        env = os.environ.copy()
        env["OPENRECOMP_HERCULES_FIXTURE_ROOT"] = str(fixture_dir)

        # Generate and verify source manifest in the temp repo
        gen = subprocess.run(
            [sys.executable, ".openrecomp-phase17/src/p17_source_manifest_v1.py", "--write"],
            cwd=str(tmp_path), capture_output=True, text=True, env=env,
        )
        if gen.returncode != 0:
            print("OPENRECOMP_P17_00_TEMP_REPOSITORY_TEST=FAIL manifest-write")
            print(gen.stdout, gen.stderr)
            return 1
        manifest = subprocess.run(
            [sys.executable, ".openrecomp-phase17/src/p17_source_manifest_v1.py"],
            cwd=str(tmp_path), capture_output=True, text=True, env=env,
        )
        if manifest.returncode != 0 or "OPENRECOMP_PHASE17_SOURCE_INTEGRITY=PASS" not in manifest.stdout:
            print("OPENRECOMP_P17_00_TEMP_REPOSITORY_TEST=FAIL source-manifest")
            print(manifest.stdout, manifest.stderr)
            return 1

        # Synthetic fixture verification in the temp repo
        synth = tmp_path / "synthetic_fixture_check.py"
        synth.write_text(
            """#!/usr/bin/env python3
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / ".openrecomp-phase17/src"))
import p17_fixture_verification_v1 as fixture
root = pathlib.Path(__file__).resolve().parent
fx_dir = pathlib.Path(__import__("os").environ["OPENRECOMP_HERCULES_FIXTURE_ROOT"])
ok, report = fixture.verify_fixture(fx_dir)
if ok:
    print("OPENRECOMP_P17_00_TEMP_REPOSITORY_SYNTHETIC_FIXTURE=PASS")
    sys.exit(0)
print(f"OPENRECOMP_P17_00_TEMP_REPOSITORY_SYNTHETIC_FIXTURE=FAIL {report}")
sys.exit(1)
""",
            encoding="utf-8",
        )
        fixture_check = subprocess.run(
            [sys.executable, str(synth)],
            cwd=str(tmp_path), capture_output=True, text=True, env=env,
        )
        if fixture_check.returncode != 0 or "OPENRECOMP_P17_00_TEMP_REPOSITORY_SYNTHETIC_FIXTURE=PASS" not in fixture_check.stdout:
            print("OPENRECOMP_P17_00_TEMP_REPOSITORY_TEST=FAIL synthetic-fixture")
            print(fixture_check.stdout, fixture_check.stderr)
            return 1

        # Nondeterminism rejection must also work in temp repo
        nondet = subprocess.run(
            [sys.executable, "tools/test_phase17_nondeterminism_v1.py"],
            cwd=str(tmp_path), capture_output=True, text=True, env=env,
        )
        if nondet.returncode != 0 or "OPENRECOMP_P17_00_NONDETERMINISM_TEST=PASS" not in nondet.stdout:
            print("OPENRECOMP_P17_00_TEMP_REPOSITORY_TEST=FAIL nondeterminism")
            print(nondet.stdout, nondet.stderr)
            return 1

        print("OPENRECOMP_P17_00_TEMP_REPOSITORY_TEST=PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
