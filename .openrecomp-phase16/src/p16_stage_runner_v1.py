#!/usr/bin/env python3
"""Phase-16 deterministic stage runner."""

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

MARKER_RE = re.compile(r"^OPENRECOMP_[A-Z0-9_]+=.*$", re.MULTILINE)

OFFICIAL_RUNS_SCHEMA = "openrecomp-phase16-official-runs-v1"
DETERMINISM_SCHEMA = "openrecomp-phase16-determinism-v1"


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
             tests_json: pathlib.Path, evidence_dir: pathlib.Path) -> dict[str, Any]:
    completed = subprocess.run(argv, cwd=str(ROOT), capture_output=True)
    stdout = completed.stdout
    stderr = completed.stderr
    lf_stdout = lf_normalize(stdout)
    text = stdout.decode("utf-8", errors="replace")
    markers = [match.strip() for match in MARKER_RE.findall(text)]
    fail_lines = [line for line in text.splitlines() if line.startswith("FAIL:")]
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
        "tests_json_present": tests_json.is_file(),
        "_stdout_lf": lf_stdout,
        "_stderr": stderr,
    }
    if tests_json.is_file():
        entry[f"{tests_json.stem}_sha256"] = sha256_bytes(tests_json.read_bytes())
    entry["artifact_sha256"] = {
        artifact.name: sha256_bytes(artifact.read_bytes())
        for artifact in sorted(evidence_dir.glob("*.json"))
        if artifact.name not in ("official_runs.json", "determinism.json")
    }
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase-16 stage runner")
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
    command = [args.python, str(script.relative_to(ROOT).as_posix()),
               "--evidence-dir", args.evidence_dir]
    display = ["python", str(script.relative_to(ROOT).as_posix()),
               "--evidence-dir", args.evidence_dir]
    stage_number = args.stage.split("-")[1]

    runs: list[dict[str, Any]] = []
    for index in range(1, args.runs + 1):
        entry = run_once(f"run{index}", command, display, tests_json, evidence_dir)
        write_bytes(evidence_dir / f"run{index}.txt", entry.pop("_stdout_lf"))
        write_bytes(evidence_dir / f"run{index}.err.txt", entry.pop("_stderr"))
        runs.append(entry)

    artifact_hashes: dict[str, str] = {}
    for artifact in sorted(evidence_dir.glob("*.json")):
        if artifact.name in ("official_runs.json", "determinism.json"):
            continue
        artifact_hashes[artifact.name] = sha256_bytes(artifact.read_bytes())

    raw_hashes = [entry["stdout_sha256_raw"] for entry in runs]
    lf_hashes = [entry["stdout_sha256_lf"] for entry in runs]
    identical_raw = len(set(raw_hashes)) == 1
    identical_lf = len(set(lf_hashes)) == 1
    returncodes_zero = all(entry["returncode"] == 0 for entry in runs)
    stderr_empty = all(entry["stderr_empty"] for entry in runs)
    tests_json_present = all(entry["tests_json_present"] for entry in runs)
    accepted = (f"OPENRECOMP_P16_{stage_number}=PASS",)
    markers_ok = all(
        any(marker in accepted for marker in entry["markers"])
        and not entry["fail_lines"]
        for entry in runs
    )
    artifacts_identical = (
        len(runs) >= 2
        and bool(runs[0]["artifact_sha256"])
        and all(entry["artifact_sha256"] == runs[0]["artifact_sha256"] for entry in runs)
    )

    write_json(evidence_dir / "official_runs.json", {
        "schema": OFFICIAL_RUNS_SCHEMA,
        "stage": args.stage,
        "runs": runs,
        "identical_raw": identical_raw,
        "identical_lf": identical_lf,
        "returncode_zero_both": returncodes_zero,
        "stderr_empty_both": stderr_empty,
        "tests_json_present_both": tests_json_present,
        "markers_present_both": markers_ok,
        "artifact_sha256": artifact_hashes,
    })
    write_json(evidence_dir / "determinism.json", {
        "schema": DETERMINISM_SCHEMA,
        "stage": args.stage,
        "gate": args.script,
        "gate_sha256": sha256_bytes(script.read_bytes()),
        "artifacts_identical": artifacts_identical,
        "stdout_identical_raw": identical_raw,
        "stdout_identical_lf": identical_lf,
        "returncode_zero_both": returncodes_zero,
        "stderr_empty_both": stderr_empty,
        "tests_json_present_both": tests_json_present,
        "artifact_sha256": artifact_hashes,
        "runs": {
            entry["name"]: {
                f"{tests_json.stem}_sha256": entry.get(f"{tests_json.stem}_sha256", ""),
                "returncode": entry["returncode"],
                "stdout_bytes_raw": entry["stdout_bytes"],
                "stdout_sha256_raw": entry["stdout_sha256_raw"],
                "stdout_sha256_lf": entry["stdout_sha256_lf"],
                "artifact_sha256": entry["artifact_sha256"],
            }
            for entry in runs
        },
    })

    passed = (
        identical_raw and identical_lf and returncodes_zero and stderr_empty
        and tests_json_present
        and markers_ok and artifacts_identical
    )
    print(json.dumps({
        "stage": args.stage,
        "identical_raw": identical_raw,
        "identical_lf": identical_lf,
        "returncode_zero_both": returncodes_zero,
        "stderr_empty_both": stderr_empty,
        "tests_json_present_both": tests_json_present,
        "markers_present_both": markers_ok,
        "artifacts_identical": artifacts_identical,
        "runner_status": "PASS" if passed else "FAIL",
    }, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
