#!/usr/bin/env python3
"""Deterministic P14-00 Phase bootstrap / Phase-13 freeze / contract recovery gate."""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase14/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p14_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
from p14_contracts_v1 import (  # noqa: E402
    GENERAL_MARKER,
    INITIALIZATION_CONTRACT_CHANGED,
    INITIALIZATION_CONTRACT_SOURCE,
    INITIALIZATION_MARKER,
    PLAYABILITY_MARKER,
    PHASE13_BASE_COMMIT,
    PHASE12_BASE_COMMIT,
    FRAME_MARKER,
    contracts_document,
)

STAGE = "P14-00"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(gate, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)
    gate.check(f"git:{args[0]}", completed.returncode == 0, completed.stderr.strip())
    return completed.stdout


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    head = git(gate, "rev-parse", "HEAD").strip()
    for name, base in (("phase13-base", PHASE13_BASE_COMMIT),
                       ("phase12-base", PHASE12_BASE_COMMIT)):
        ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", base, head],
                                  cwd=str(root), capture_output=True)
        gate.check(f"ancestry:{name}", ancestor.returncode == 0, head)
    branch = git(gate, "rev-parse", "--abbrev-ref", "HEAD").strip()
    gate.check("branch:phase14", branch == "phase14/ps1-hercules-init-closure-v1", branch)

    diff = git(gate, "diff", "--name-only", f"{PHASE13_BASE_COMMIT}..{head}", "--",
               ".openrecomp-phase13", "tools/test_phase13_boundary_v1.py").strip().splitlines()
    gate.check("freeze:phase13-untouched", not diff, ",".join(diff))
    tree = git(gate, "rev-parse", f"{PHASE13_BASE_COMMIT}^{{tree}}").strip()
    gate.check("freeze:phase13-tree", len(tree) == 40, tree)

    contract_path = root / INITIALIZATION_CONTRACT_SOURCE
    gate.check("contract:source-present", contract_path.is_file(), INITIALIZATION_CONTRACT_SOURCE)
    gate.check("contract:unchanged-flag", INITIALIZATION_CONTRACT_CHANGED == "NO")
    contract_hash = sha256(contract_path)
    p12_contracts_json = root / ".openrecomp-phase12/evidence/P12-00/proof_contracts.json"
    gate.check("contract:p12-sidecar-present", p12_contracts_json.is_file(),
               str(p12_contracts_json.relative_to(root)))

    document = {
        "schema": "openrecomp-phase14-boundary-v1",
        "stage": STAGE,
        "phase13_base_commit": PHASE13_BASE_COMMIT,
        "phase13_base_tree": tree,
        "phase12_ancestor": PHASE12_BASE_COMMIT,
        "head": head,
        "branch": branch,
        "initialization_contract_source": INITIALIZATION_CONTRACT_SOURCE,
        "initialization_contract_sha256": contract_hash,
        "initialization_contract_changed": INITIALIZATION_CONTRACT_CHANGED,
        "phase13_evidence_untouched": not diff,
        "reconnaissance_consumed": [
            "reconnaissance/post-b0-init-frontier-v1",
            "reconnaissance/phase13-trace-failure-closure-v1",
            "reconnaissance/card-irq-reachability-v1",
            "reconnaissance/bu-init-b0-3f-closure-v1",
            "reconnaissance/internal-indirect-target-closure-v1",
        ],
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "boundary.json", document)
    write_json(evidence / "proof_contracts.json", contracts_document())
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase14-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P14_00": "PASS", INITIALIZATION_MARKER: "NOT_PROVEN",
                    FRAME_MARKER: "NOT_PROVEN", PLAYABILITY_MARKER: "NOT_PROVEN",
                    GENERAL_MARKER: "NOT_PROVEN"},
        "next_stage": "P14-01",
    })
    assert_public_safe(gate, "boundary", document, b"")
    write_json(evidence / "p14_00_tests.json", gate.tests_document("boundary"))
    gate.mark("OPENRECOMP_P14_00")
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase14/evidence/P14-00"))
