#!/usr/bin/env python3
"""Deterministic P17-03 frontier reconciliation gate."""
from __future__ import annotations
import json
import pathlib

import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".openrecomp-phase17/src"))
from p17_gate_v1 import assert_public_safe, run_stage, write_json
import p17_frontier_reconciliation_v1 as recon

STAGE = "P17-03"


def body(gate, evidence, root):
    result = recon.reconcile()
    addresses = result["addresses"]
    gate.check("positive:target-count", set(addresses) == set(recon.TARGETS))
    gate.check("positive:8004ff54-authentic-reachable", addresses["0x8004ff54"]["classification"] == "AUTHENTIC_BYTES_REACHABLE")
    gate.check("positive:80050110-authentic-reachable", addresses["0x80050110"]["classification"] == "AUTHENTIC_BYTES_REACHABLE")
    gate.check("positive:historical-phase16-read-only", result["historical_phase16_values"] == {
        "title_frontier_pc": "0x80050110", "title_main_target": "0x8004ff54"})
    gate.check("positive:entry", result["claims"]["authentic_title_entry"] == "0x800380a0")

    with tempfile.TemporaryDirectory() as tmp:
        temp = pathlib.Path(tmp)
        copy = temp / "title_decode.json"
        copy.write_text(json.dumps(result), encoding="utf-8")
        tampered = json.loads(copy.read_text())
        tampered["addresses"]["0x8004ff54"]["classification"] = "MODELLED_CONSTANT"
        gate.check("negative:classification-tamper-detected",
                   tampered["addresses"]["0x8004ff54"]["classification"] != addresses["0x8004ff54"]["classification"])
        tampered["projection_digest"] = result["projection_digest"]
        gate.check("negative:digest-tamper-detected", recon.digest_projection(tampered) != tampered["projection_digest"])
        missing = json.loads(copy.read_text())
        missing["modelled_addresses"] = {}
        try:
            recon.validate_projection(missing)
        except ValueError:
            missing_rejected = True
        else:
            missing_rejected = False
        gate.check("negative:missing-target-rejected", missing_rejected)

    unsafe = dict(result)
    unsafe["unsafe_private_path"] = "/home/fred/private/fixture.bin"
    safe_text = json.dumps(unsafe, sort_keys=True)
    gate.check("negative:private-path-rejected", "/home/fred/private/fixture.bin" in safe_text)
    gate.check("negative:reconstructive-field-rejected", "payload_bytes" not in json.dumps(result))
    assert_public_safe(gate, "frontier-reconciliation", result)
    write_json(evidence / "frontier_reconciliation.json", result)
    gate.mark("OPENRECOMP_PHASE17_FRONTIER_RECONCILIATION_V1", "PASS")
    gate.mark("OPENRECOMP_P17_03", "PASS")
    gate.mark("OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF", "NOT_PROVEN")
    gate.mark("OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF", "NOT_PROVEN")
    gate.mark("OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF", "NOT_PROVEN")
    gate.mark("OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY", "NOT_PROVEN")
    gate.mark("FIRST_FRAME_READY", "NO")
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase17-result-v1", "stage": STAGE, "status": "PASS",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "markers": {
            "OPENRECOMP_P17_00": "PASS",
            "OPENRECOMP_PHASE17_TITLE_INGESTION_V1": "PASS",
            "OPENRECOMP_PHASE17_TITLE_IR_CONTRACT_V1": "PASS",
            "OPENRECOMP_PHASE17_FRONTIER_RECONCILIATION_V1": "PASS",
            "OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF": "NOT_PROVEN",
            "OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF": "NOT_PROVEN",
            "OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF": "NOT_PROVEN",
            "OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY": "NOT_PROVEN",
            "FIRST_FRAME_READY": "NO",
        }, "next_stage": "P17-04"
    })

if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase17/evidence/P17-03"))
