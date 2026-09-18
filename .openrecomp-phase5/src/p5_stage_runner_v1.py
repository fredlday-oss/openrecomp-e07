#!/usr/bin/env python3
"""Phase-5 deterministic stage runner.

Runs a Phase-5 stage gate twice, captures stdout/stderr bytes, requires
byte-identical stdout (raw and LF-normalized) with empty stderr and exit 0,
and writes the frozen evidence sidecars `official_runs.json` and
`determinism.json` next to the stage evidence.

Usage:

    python .openrecomp-phase5/src/p5_stage_runner_v1.py \
        --stage P5-00 \
        --script tools/test_phase5_boundary_v1.py \
        --evidence-dir .openrecomp-phase5/evidence/P5-00 \
        --tests-json p5_00_tests.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]

MARKER_RE = re.compile(r"^OPENRECOMP_[A-Z0-9_]+=", re.MULTILINE)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def write_bytes(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: pathlib.Path, document: dict[str, Any]) -> None:
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    write_bytes(path, text.encode("utf-8"))


def run_once(name: str, argv: list[str], display: list[str],
             tests_json: pathlib.Path) -> dict[str, Any]:
    completed = subprocess.run(argv, cwd=str(ROOT), capture_output=True)
    stdout = completed.stdout
    stderr = completed.stderr
    lf_stdout = lf_normalize(stdout)
    markers = MARKER_RE.findall(stdout.decode("utf-8", errors="replace"))
    fail_lines = [line for line in stdout.decode("utf-8", errors="replace").splitlines()
                  if line.startswith("FAIL:")]
    entry: dict[str, Any] = {
        "name": name,
        "command": display,
        "returncode": completed.returncode,
        "stdout_bytes": len(stdout),
        "stdout_bytes_lf": len(lf_stdout),
        "stdout_sha256_raw": sha256_bytes(stdout),
        "stdout_sha256_lf": sha256_bytes(lf_stdout),
        "stderr_bytes": len(stderr),
        "stderr_empty": len(stderr) == 0,
        "markers": markers,
        "fail_lines": fail_lines,
        "_stdout_lf": lf_stdout,
        "_stderr": stderr,
    }
    if tests_json.is_file():
        entry[f"{tests_json.stem}_sha256"] = sha256_bytes(tests_json.read_bytes())
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase-5 stage runner")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--tests-json", required=True)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)

    evidence_dir = (ROOT / args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    script = (ROOT / args.script).resolve()
    tests_json = evidence_dir / args.tests_json
    python_name = pathlib.Path(args.python).name
    if not python_name.lower().startswith("python"):
        python_name = "python"
    command = [args.python, str(script.relative_to(ROOT).as_posix()),
               "--evidence-dir", args.evidence_dir]
    display = ["python", str(script.relative_to(ROOT).as_posix()),
               "--evidence-dir", args.evidence_dir]

    runs: list[dict[str, Any]] = []
    for index in range(1, args.runs + 1):
        entry = run_once(f"run{index}", command, display, tests_json)
        write_bytes(evidence_dir / f"run{index}.txt", entry.pop("_stdout_lf"))
        write_bytes(evidence_dir / f"run{index}.err.txt", entry.pop("_stderr"))
        runs.append(entry)

    raw_hashes = [entry["stdout_sha256_raw"] for entry in runs]
    lf_hashes = [entry["stdout_sha256_lf"] for entry in runs]
    identical_raw = len(set(raw_hashes)) == 1
    identical_lf = len(set(lf_hashes)) == 1
    returncodes_zero = all(entry["returncode"] == 0 for entry in runs)
    stderr_empty = all(entry["stderr_empty"] for entry in runs)
    markers_ok = all(any(marker.startswith("OPENRECOMP_P5_") for marker in entry["markers"])
                     for entry in runs)

    official_runs = {
        "stage": args.stage,
        "runs": runs,
        "identical_raw": identical_raw,
        "identical_lf": identical_lf,
        "returncode_zero_both": returncodes_zero,
        "stderr_empty_both": stderr_empty,
        "markers_present_both": markers_ok,
    }
    write_json(evidence_dir / "official_runs.json", official_runs)

    determinism = {
        "stage": args.stage,
        "gate": args.script,
        "gate_sha256": sha256_bytes(script.read_bytes()),
        "artifacts_identical": tests_json.is_file(),
        "stdout_identical_raw": identical_raw,
        "stdout_identical_lf": identical_lf,
        "returncode_zero_both": returncodes_zero,
        "stderr_empty_both": stderr_empty,
        "runs": {
            entry["name"]: {
                f"{tests_json.stem}_sha256": entry.get(f"{tests_json.stem}_sha256", ""),
                "returncode": entry["returncode"],
                "stdout_bytes_raw": entry["stdout_bytes"],
                "stdout_sha256_raw": entry["stdout_sha256_raw"],
                "stdout_sha256_lf": entry["stdout_sha256_lf"],
            }
            for entry in runs
        },
        "compatibility_marker": "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN",
        "terminal_marker": "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN",
    }
    write_json(evidence_dir / "determinism.json", determinism)

    passed = identical_raw and identical_lf and returncodes_zero and stderr_empty and markers_ok
    print(json.dumps({
        "stage": args.stage,
        "identical_raw": identical_raw,
        "identical_lf": identical_lf,
        "returncode_zero_both": returncodes_zero,
        "stderr_empty_both": stderr_empty,
        "markers_present_both": markers_ok,
        "runner_status": "PASS" if passed else "FAIL",
    }, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
