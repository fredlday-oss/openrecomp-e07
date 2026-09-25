#!/usr/bin/env python3
"""Real nondeterminism rejection test for Phase-17 stage runner."""

from __future__ import annotations

import json
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

        # Copy Phase-17 stage runner and gate helpers into temp repo
        dest_src = tmp_path / ".openrecomp-phase17" / "src"
        dest_src.mkdir(parents=True)
        for src_file in (ROOT / ".openrecomp-phase17/src").glob("*.py"):
            shutil.copy2(src_file, dest_src / src_file.name)

        # Nondeterministic gate script
        script = tmp_path / "nondeterministic_gate.py"
        script.write_text(
            """#!/usr/bin/env python3
import json, pathlib, sys, time
root = pathlib.Path(__file__).resolve().parent
evidence = root / "evidence"
evidence.mkdir(parents=True, exist_ok=True)
value = time.time_ns()
(root / "evidence" / "artifact.json").write_text(
    json.dumps({"value": value}, sort_keys=True) + "\n", encoding="utf-8")
print("OPENRECOMP_P17_00=PASS")
""",
            encoding="utf-8",
        )

        runner = tmp_path / ".openrecomp-phase17/src/p17_stage_runner_v1.py"
        completed = subprocess.run(
            [sys.executable, str(runner),
             "--stage", "P17-00",
             "--script", str(script),
             "--evidence-dir", str(tmp_path / "evidence"),
             "--tests-json", "artifact.json"],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        try:
            result = json.loads(completed.stdout)
        except Exception:
            print("OPENRECOMP_P17_00_NONDETERMINISM_TEST=FAIL runner-output-unparseable")
            print(completed.stderr)
            return 1

        if (
            completed.returncode != 0
            and result.get("runner_status") == "FAIL"
            and result.get("artifacts_identical") is False
        ):
            print("OPENRECOMP_P17_00_NONDETERMINISM_TEST=PASS")
            return 0
        print(f"OPENRECOMP_P17_00_NONDETERMINISM_TEST=FAIL {json.dumps(result, sort_keys=True)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
