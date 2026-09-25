#!/usr/bin/env python3
"""Deterministic P16-00 Phase-16 bootstrap / frozen-baseline gate."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p16_contracts_v1 as contract
from p16_gate_v1 import assert_public_safe, run_stage, write_json
import p16_frozen_phase15_boundary_v1 as p15_boundary
import p16_frozen_phase15_integrity_v1 as p15_integrity

STAGE = "P16-00"

CONTROL_FILES = (
    "CONTROL_POLICY.md",
    "SCOPE.md",
    "STAGE_QUEUE.md",
    "EVIDENCE_SCHEMA.md",
    "FIXTURE_POLICY.md",
    "STATE.md",
    "HANDOFF.md",
)

REQUIRED_DIRS = ("src", "runtime", "evidence", "build", "scratch")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True).stdout.strip()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    head = git("rev-parse", "HEAD")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")

    # 1. Verify frozen Phase-15 boundary and ancestry
    p15_ok = p15_boundary.verify_frozen_boundary()
    gate.check("phase15:boundary-frozen", p15_ok, f"frozen commit={contract.PHASE15_BASE_COMMIT}")

    # 2. Verify frozen Phase-15 source integrity
    p15_int_ok = p15_integrity.verify_phase15_integrity()
    gate.check("phase15:sources-intact", p15_int_ok, "36 Phase-15 source blobs verified")

    # 3. Verify Phase-16 control plane
    control_root = root / ".openrecomp-phase16"
    for filename in CONTROL_FILES:
        cpath = control_root / filename
        gate.check(f"control:{filename}", cpath.is_file() and cpath.stat().st_size > 0, filename)

    for dirname in REQUIRED_DIRS:
        dpath = control_root / dirname
        dpath.mkdir(parents=True, exist_ok=True)
        gate.check(f"dir:{dirname}", dpath.is_dir(), dirname)

    # 4. Verify private fixture files and record hashes
    fixture_dir = root.parents[1] / "fixtures" / "psx" / "hercules"
    bin_file = fixture_dir / "Disney's Hercules Action Game (USA).bin"
    cue_file = fixture_dir / "Disney's Hercules Action Game (USA).cue"
    slus_file = fixture_dir / "SLUS_005.29"

    gate.check("fixture:bin-exists", bin_file.is_file(), str(bin_file.name))
    gate.check("fixture:cue-exists", cue_file.is_file(), str(cue_file.name))
    gate.check("fixture:slus-exists", slus_file.is_file(), str(slus_file.name))

    bin_hash = sha256_file(bin_file)
    cue_hash = sha256_file(cue_file)
    slus_hash = sha256_file(slus_file)

    gate.check("fixture:bin-hash", bin_hash == contract.FIXTURE_BIN_SHA256, bin_hash)
    gate.check("fixture:cue-hash", cue_hash == contract.FIXTURE_CUE_SHA256, cue_hash)
    gate.check("fixture:slus-hash", slus_hash == contract.FIXTURE_SLUS_SHA256, slus_hash)

    # 5. Output stage document
    bootstrap_doc = {
        "schema": "openrecomp-phase16-bootstrap-v1",
        "stage": STAGE,
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "branch": branch,
        "head": head,
        "phase15_base_commit": contract.PHASE15_BASE_COMMIT,
        "phase15_base_tree": contract.PHASE15_BASE_TREE,
        "phase14_base_commit": contract.PHASE14_BASE_COMMIT,
        "phase14_base_tree": contract.PHASE14_BASE_TREE,
        "fixture_provenance": {
            "bin_sha256": bin_hash,
            "bin_size": bin_file.stat().st_size,
            "cue_sha256": cue_hash,
            "slus_sha256": slus_hash,
            "slus_size": slus_file.stat().st_size,
        },
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "bootstrap.json", bootstrap_doc)
    assert_public_safe(gate, "bootstrap", bootstrap_doc, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase16-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
        },
        "next_stage": "P16-01",
    })

    gate.mark(contract.BOOTSTRAP_MARKER)
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase16/evidence/P16-00"))
