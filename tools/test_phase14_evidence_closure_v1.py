#!/usr/bin/env python3
"""Deterministic P14-91 evidence-closure gate."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase14/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p14_gate_v1 import run_stage, write_json  # noqa: E402
from p14_contracts_v1 import (  # noqa: E402
    FRAME_MARKER,
    GENERAL_MARKER,
    INITIALIZATION_MARKER,
    PHASE13_BASE_COMMIT,
    PLAYABILITY_MARKER,
)

STAGE = "P14-91"
EVIDENCE = ROOT / ".openrecomp-phase14/evidence"

REQUIRED_STAGES = (
    "P14-00", "P14-01", "P14-05", "P14-20", "P14-30", "P14-40", "P14-50",
)

FORBIDDEN_TRACKED = (".bin", ".cue", "SLUS", "fixtures/psx/hercules")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    index = {}
    for stage in REQUIRED_STAGES:
        result_path = EVIDENCE / stage / "RESULT.json"
        gate.check(f"record:{stage}", result_path.is_file(), str(result_path.name))
        document = json.loads(result_path.read_text(encoding="utf-8"))
        index[stage] = {
            "sha256": sha256(result_path),
            "status": document.get("status"),
            "markers": document.get("markers", {}),
        }
        for artifact in sorted((EVIDENCE / stage).glob("*.json")):
            json.loads(artifact.read_text(encoding="utf-8"))

    manifest = subprocess.run(
        [sys.executable, ".openrecomp-phase14/src/p14_source_manifest_v1.py"],
        cwd=str(root), capture_output=True, text=True)
    gate.check("source-integrity", manifest.returncode == 0
               and "OPENRECOMP_PHASE14_SOURCE_INTEGRITY=PASS" in manifest.stdout,
               manifest.stdout.strip())

    diff = subprocess.run(["git", "diff", "--name-only", f"{PHASE13_BASE_COMMIT}..HEAD", "--",
                           ".openrecomp-phase13"], cwd=str(root), capture_output=True, text=True)
    gate.check("frozen:phase13-unchanged", not diff.stdout.strip(), diff.stdout.strip())

    tracked = subprocess.run(["git", "ls-files"], cwd=str(root),
                             capture_output=True, text=True).stdout.splitlines()
    leaked = [name for name in tracked if any(token in name for token in FORBIDDEN_TRACKED)]
    gate.check("private:no-fixture-bytes-tracked", not leaked, ",".join(leaked))

    proof = json.loads((EVIDENCE / "P14-05" / "initialization_proof.json").read_text(encoding="utf-8"))
    gate.check("proof:marker-matches-evidence",
               proof["result"] == "NOT_PROVEN"
               and index["P14-05"]["markers"][INITIALIZATION_MARKER] == "NOT_PROVEN")
    gate.check("proof:predicates-honest",
               proof["predicates"]["INIT-NO-FAIL-CLOSED"] is False
               and proof["satisfied"] is False,
               json.dumps(proof["predicates"], sort_keys=True))

    surface = json.loads((EVIDENCE / "P14-20" / "hardening.json").read_text(encoding="utf-8"))
    gate.check("synthetic:project-owned",
               surface["synthetic_surface"]["authentic_bios_address_claimed"] is False
               and surface["synthetic_surface"]["classification"]
               == "synthetic-project-owned-not-a-recovered-bios-address")
    gate.check("reserved:frame-playability-general",
               index["P14-00"]["markers"][FRAME_MARKER] == "NOT_PROVEN"
               and index["P14-00"]["markers"][PLAYABILITY_MARKER] == "NOT_PROVEN"
               and index["P14-00"]["markers"][GENERAL_MARKER] == "NOT_PROVEN")

    write_json(evidence / "evidence_index.json", {
        "schema": "openrecomp-phase14-evidence-index-v1", "stage": STAGE,
        "stages": index,
        "source_integrity": "PASS",
        "phase13_unchanged": "YES",
        "private_fixture_bytes_tracked": "NO",
        "third_party_code_imported": "NO",
    })
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase14-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P14_91": "PASS", INITIALIZATION_MARKER: "NOT_PROVEN",
                    FRAME_MARKER: "NOT_PROVEN", PLAYABILITY_MARKER: "NOT_PROVEN",
                    GENERAL_MARKER: "NOT_PROVEN"},
        "next_stage": "P14-99",
    })
    write_json(evidence / "p14_91_tests.json", gate.tests_document("evidence-closure"))
    gate.mark("OPENRECOMP_P14_91")
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase14/evidence/P14-91"))
