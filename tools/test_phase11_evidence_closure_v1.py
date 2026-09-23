#!/usr/bin/env python3
"""P11-91 Phase-11 evidence closure and bounded proof matrix.

Verifies every completed Phase-11 stage (P11-00 through P11-07, P11-RC and
P11-90) as already-committed deterministic evidence, cross-checks the exact
pinned facts recorded by those stages, and assembles a closure evidence
index, proof matrix and claim ledger. P11-08 through P11-12 are recorded as
not executed and receive no verdict. The four reserved Phase-11 claim
markers stay `NOT_PROVEN`; the already-promoted milestone-C GPU command
marker is verified unchanged.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re
import subprocess
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
P11 = ROOT / ".openrecomp-phase11"
EVIDENCE = P11 / "evidence"
STAGE = "P11-91"
FEATURE_MARKER = "OPENRECOMP_PHASE11_EVIDENCE_CLOSURE_V1"

INITIALIZATION_MARKER = "OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN"
FRAME_MARKER = "OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN"
GENERAL_MARKER = "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN"
GPU_MARKER = "OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF=PROVEN"
RESERVED_MARKERS = (
    INITIALIZATION_MARKER, FRAME_MARKER, PLAYABILITY_MARKER, GENERAL_MARKER,
)

STAGE_GATES = {
    "P11-00": ("tools/test_phase11_boundary_v1.py", "p11_00_tests.json"),
    "P11-01": ("tools/test_phase11_causality_v1.py", "p11_01_tests.json"),
    "P11-02": ("tools/test_phase11_indirect_v1.py", "p11_02_tests.json"),
    "P11-03": ("tools/test_phase11_event_contract_v1.py", "p11_03_tests.json"),
    "P11-04": ("tools/test_phase11_initialization_v1.py", "p11_04_tests.json"),
    "P11-05": ("tools/test_phase11_gpu_v1.py", "p11_05_tests.json"),
    "P11-06": ("tools/test_phase11_gpu_closure_v1.py", "p11_06_tests.json"),
    "P11-07": ("tools/test_phase11_b0_table_v1.py", "p11_07_tests.json"),
    "P11-RC": ("tools/test_phase11_queue_reconciliation_v1.py", "p11_rc_tests.json"),
    "P11-90": ("tools/test_phase11_whole_regression_v1.py", "p11_90_tests.json"),
}
COMPLETED_STAGES = tuple(STAGE_GATES)
STAGES_WITHOUT_RESULT = ("P11-90",)
UNEXECUTED_STAGES = ("P11-08", "P11-09", "P11-10", "P11-11", "P11-12")

RESULTS: list[dict[str, str]] = []


def check(name: str, condition: bool, detail: object = "") -> None:
    RESULTS.append({
        "check": name,
        "status": "PASS" if condition else "FAIL",
        "detail": str(detail),
    })
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: pathlib.Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


def load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(ROOT), check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    if completed.returncode != 0 or completed.stderr:
        raise RuntimeError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def tests_status(doc: dict[str, Any]) -> tuple[str, int, int]:
    """Return (status, passed, failed) for either tests-json schema shape."""
    if "summary" in doc:
        failed = int(doc["summary"]["failed"])
        passed = int(doc["summary"]["passed"])
        status = "PASS" if failed == 0 else "FAIL"
        return status, passed, failed
    failed = int(doc["failed"])
    passed = int(doc["passed"])
    return doc["status"], passed, failed


def verify_stage_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for stage in COMPLETED_STAGES:
        stage_dir = EVIDENCE / stage
        check(f"stage:{stage}:dir", stage_dir.is_dir(), stage_dir)
        script, tests_name = STAGE_GATES[stage]
        if stage not in STAGES_WITHOUT_RESULT:
            check(f"stage:{stage}:result-md", (stage_dir / "RESULT.md").is_file(),
                  "RESULT.md")

        official = load(stage_dir / "official_runs.json")
        check(f"stage:{stage}:official-identical-raw", official["identical_raw"] is True,
              official["identical_raw"])
        check(f"stage:{stage}:official-identical-lf", official["identical_lf"] is True,
              official["identical_lf"])
        check(f"stage:{stage}:official-returncode-zero",
              official["returncode_zero_both"] is True, official["returncode_zero_both"])
        check(f"stage:{stage}:official-stderr-empty",
              official["stderr_empty_both"] is True, official["stderr_empty_both"])
        check(f"stage:{stage}:official-markers-present",
              official["markers_present_both"] is True, official["markers_present_both"])
        check(f"stage:{stage}:official-no-fail-lines",
              all(not run["fail_lines"] for run in official["runs"]), "no FAIL lines")
        gate_marker = f"OPENRECOMP_{stage.replace('-', '_')}=PASS"
        check(f"stage:{stage}:gate-marker",
              all(any(marker == gate_marker or marker.startswith(gate_marker + " ")
                      for marker in run["markers"]) for run in official["runs"]),
              gate_marker)

        determinism = load(stage_dir / "determinism.json")
        check(f"stage:{stage}:determinism-artifacts-identical",
              determinism["artifacts_identical"] is True, "sidecars")
        recorded_gate_sha256 = determinism["gate_sha256"]
        current_gate_sha256 = sha256_file(ROOT / script)
        # P11-02/P11-03 were later, authorizedly enriched with the P11-07
        # public B0:0x57 name (see P11-90 whole_regression.json delta); their
        # gate hash legitimately differs from their own original stage
        # record. Every completed-stage gate must be committed and clean.
        gate_diff = git("diff", "--name-only", "HEAD", "--", script)
        check(f"stage:{stage}:gate-no-uncommitted-diff", gate_diff == "", gate_diff)
        if stage not in ("P11-02", "P11-03"):
            check(f"stage:{stage}:gate-unchanged",
                  current_gate_sha256 == recorded_gate_sha256, current_gate_sha256)

        tests_doc = load(stage_dir / tests_name)
        status, passed, failed = tests_status(tests_doc)
        check(f"stage:{stage}:tests-status", status == "PASS", status)
        check(f"stage:{stage}:tests-failed-zero", failed == 0, failed)

        records.append({
            "stage": stage,
            "gate": script,
            "tests_json": tests_name,
            "checks_passed": passed,
            "stdout_sha256_raw": official["runs"][0]["stdout_sha256_raw"],
            "gate_sha256": recorded_gate_sha256,
        })
    return records


def verify_exact_records() -> None:
    fixture = load(EVIDENCE / "P11-00" / "fixture_identity.json")["identity"]
    check("exact:p11-00:executable-sha256",
          fixture["executable"]["sha256"]
          == "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f",
          fixture["executable"]["sha256"])
    check("exact:p11-00:cue-sha256",
          fixture["disc"]["cue"]["cue_sha256"]
          == "beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2",
          fixture["disc"]["cue"]["cue_sha256"])
    check("exact:p11-00:bin-sha256",
          fixture["disc"]["bins"][0]["sha256"]
          == "2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365",
          fixture["disc"]["bins"][0]["sha256"])

    frontier00 = load(EVIDENCE / "P11-00" / "frontier.json")
    check("exact:p11-00:highest-milestone",
          frontier00["inherited_boundary"]["highest_milestone"] == "A",
          frontier00["inherited_boundary"]["highest_milestone"])
    check("exact:p11-00:program-fingerprint",
          frontier00["emission"]["program_fingerprint"]
          == "a047a52fb460d3786e5bff03b5c26ac2978ae768b581f5e6c4a9cbc284db4a9a",
          frontier00["emission"]["program_fingerprint"])

    causality = load(EVIDENCE / "P11-01" / "causality.json")["first_fail_closed_event"]
    check("exact:p11-01:site", causality["site"] == "0x80026ccc", causality["site"])
    check("exact:p11-01:service-id", causality["service_id"] == "ps1.bios.A0.2b",
          causality["service_id"])
    check("exact:p11-01:block-index", causality["block_index"] == 9424,
          causality["block_index"])

    causal_ab = load(EVIDENCE / "P11-05" / "causal_ab.json")
    required_write = causal_ab["prefix"]["required_gpu_write"][0]
    check("exact:p11-05:required-gpu-write-value",
          required_write["value"] == "0x0002a244", required_write["value"])
    check("exact:p11-05:required-gpu-write-command",
          required_write["command"] == "0x00" and required_write["classification"]["class"] == "NOP",
          required_write["classification"])
    check("exact:p11-05:frontier-b-site",
          causal_ab["b"]["failure"]["site"] == "0x8001882c",
          causal_ab["b"]["failure"]["site"])
    check("exact:p11-05:frontier-b-source-value",
          causal_ab["b"]["failure"]["source_value"] == "0x8001a7dc",
          causal_ab["b"]["failure"]["source_value"])

    target = load(EVIDENCE / "P11-06" / "target_provenance.json")
    check("exact:p11-06:observed-target", target["observed_target"] == "0x8001a7dc",
          target["observed_target"])
    check("exact:p11-06:classification", target["classification"] == "EXACT_CONSTANT_TARGET",
          target["classification"])

    contract = load(EVIDENCE / "P11-07" / "public_contract.json")["established_contract"]
    check("exact:p11-07:contract-name", contract["name"] == "GetB0Table", contract["name"])
    check("exact:p11-07:contract-vector-index",
          contract["vector"] == "B0" and contract["function_index"] == "0x57",
          (contract["vector"], contract["function_index"]))

    caller = load(EVIDENCE / "P11-07" / "caller_use.json")
    check("exact:p11-07:caller-site", caller["call"]["site"] == "0x80015fa4",
          caller["call"]["site"])
    check("exact:p11-07:caller-block-index", caller["call"]["block_index"] == 468341,
          caller["call"]["block_index"])
    check("exact:p11-07:first-required-entry",
          caller["classification"]["first_required_entry"] == "B0:0x5b ChangeClearPAD",
          caller["classification"]["first_required_entry"])
    check("exact:p11-07:next-frontier-status",
          caller["next_frontier"]["status"] == "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
          caller["next_frontier"]["status"])

    blocker = load(EVIDENCE / "P11-07" / "blocker.json")
    check("exact:p11-07:blocker-classification",
          blocker["classification"] == "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
          blocker["classification"])
    check("exact:p11-07:blocker-frontier",
          blocker["current_frontier"]["site"] == "0x80015fa4"
          and blocker["current_frontier"]["block_index"] == 468341,
          blocker["current_frontier"])
    check("exact:p11-07:blocker-milestone-c",
          blocker["milestones"]["C"] == "PROVEN_IN_P11_05", blocker["milestones"]["C"])
    check("exact:p11-07:blocker-no-implementation-delta",
          not any(blocker["implementation_delta"].values()),
          blocker["implementation_delta"])

    reconciliation = load(EVIDENCE / "P11-RC" / "reconciliation.json")
    check("exact:p11-rc:control-decision",
          reconciliation["control_decision"] == "QUEUE_RECONCILIATION_REQUIRED",
          reconciliation["control_decision"])
    check("exact:p11-rc:authorized-route",
          reconciliation["authorized_terminal_route"]
          == ["P11-RC", "P11-90", "P11-91", "P11-99"],
          reconciliation["authorized_terminal_route"])
    check("exact:p11-rc:milestone-c",
          reconciliation["milestones"]["C"] == "PROVEN_PRIVATE_FIXTURE_BOUNDED",
          reconciliation["milestones"]["C"])
    check("exact:p11-rc:forcing-dependency",
          reconciliation["forcing_dependency"]["site"] == "0x80015fa4"
          and reconciliation["forcing_dependency"]["block_index"] == 468341
          and reconciliation["forcing_dependency"]["cause"]
          == "architectural/evidentiary, not implementation defect",
          reconciliation["forcing_dependency"])

    regression = load(EVIDENCE / "P11-90" / "whole_regression.json")
    check("exact:p11-90:claims-c",
          regression["claims"]["C"] == "PROVEN_PRIVATE_FIXTURE_BOUNDED",
          regression["claims"]["C"])
    check("exact:p11-90:claims-general",
          regression["claims"]["general_ps1_compatibility"] == "NOT_PROVEN_PERMANENT",
          regression["claims"]["general_ps1_compatibility"])
    check("exact:p11-90:unexecuted",
          regression["reconciled_queue"]["unexecuted_stages"] == list(UNEXECUTED_STAGES),
          regression["reconciled_queue"]["unexecuted_stages"])
    check("exact:p11-90:stage-verdict-not-assigned",
          regression["reconciled_queue"]["stage_verdict_assigned"] is False,
          regression["reconciled_queue"]["stage_verdict_assigned"])


def verify_claim_markers() -> None:
    state = (P11 / "STATE.md").read_text(encoding="utf-8")
    for marker in RESERVED_MARKERS:
        check(f"claims:state:{marker}", marker in state, marker)
    check("claims:state:gpu-marker", GPU_MARKER in state, GPU_MARKER)
    for stage in COMPLETED_STAGES:
        check(f"claims:state:stage-row-pass:{stage}",
              re.search(rf"\|\s*{re.escape(stage)}\s*\|\s*PASS", state) is not None,
              stage)
    for stage in UNEXECUTED_STAGES:
        check(f"claims:state:stage-row-not-executed:{stage}",
              f"| {stage} | NOT EXECUTED — no stage verdict assigned |" in state,
              stage)
    queue = (P11 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
    check("claims:queue:authorized-route",
          "`P11-RC -> P11-90 -> P11-91 -> P11-99`" in queue, "route")
    check("claims:queue:general-non-claim",
          "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)" in queue,
          "general non-claim")


def verify_manifest() -> None:
    source = subprocess.run(
        ["python", str(P11 / "src" / "p11_source_manifest_v1.py")],
        cwd=str(ROOT), check=False, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8",
    )
    check("source:p11-manifest",
          source.returncode == 0 and source.stderr == ""
          and source.stdout.startswith("OPENRECOMP_PHASE11_SOURCE_INTEGRITY=PASS entries="),
          source.stdout.strip() or source.stderr.strip())


def build_index(records: list[dict[str, Any]]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for stage in COMPLETED_STAGES:
        stage_dir = EVIDENCE / stage
        for path in sorted(stage_dir.rglob("*")):
            if path.is_dir():
                continue
            relative = path.relative_to(P11).as_posix()
            files.append({
                "path": relative,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            })
    return {
        "schema": "openrecomp-phase11-evidence-index-v1",
        "stage": STAGE,
        "completed_stages": list(COMPLETED_STAGES),
        "unexecuted_stages": list(UNEXECUTED_STAGES),
        "stage_records": records,
        "file_count": len(files),
        "files": files,
    }


def build_proof_matrix() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase11-proof-matrix-v1",
        "stage": STAGE,
        "fixture": {
            "label": "hercules-private-fixture",
            "executable": "SLUS_005.29",
            "executable_sha256":
                "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f",
        },
        "milestones": {
            "A": "INHERITED_PROVEN",
            "B": "NOT_PROVEN",
            "C": "PROVEN_PRIVATE_FIXTURE_BOUNDED",
            "D": "NOT_PROVEN",
            "E": "NOT_PROVEN",
            "F": "NOT_PROVEN",
            "G": "NOT_PROVEN",
        },
        "highest_proven_milestone": "C",
        "gpu_command_proof_marker": GPU_MARKER,
        "frontier": {
            "site": "0x80015fa4",
            "vector": "B0",
            "function_index": "0x57",
            "public_name": "GetB0Table",
            "block_index": 468341,
            "required_entry": "B0:0x5b ChangeClearPAD",
            "status": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
            "cause": "architectural/evidentiary, not implementation defect",
        },
        "unresolved_blockers": [
            {
                "site": "0x80015fa4",
                "vector": "B0",
                "function_index": "0x57",
                "public_name": "GetB0Table",
                "block_index": 468341,
                "classification": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
                "reason": "no public source establishes a portable guest B0:0x5B "
                          "callable target and writable target-relative object "
                          "compatible with the no-BIOS-runtime scope",
            },
        ],
        "deliberate_exclusions": [
            "P11-08 CD-ROM / overlay / resource-loading frontier",
            "P11-09 Controller / event / SPU frontier",
            "P11-10 Title/menu progression (milestones E and F)",
            "P11-11 Milestone G: controllable gameplay",
            "P11-12 Playability hardening + reproducibility",
        ],
        "permanent_non_claims": [
            GENERAL_MARKER,
        ],
        "terminal_claims_reserved_at_p11_91": list(RESERVED_MARKERS),
        "completed_stages": list(COMPLETED_STAGES),
        "unexecuted_stages": list(UNEXECUTED_STAGES),
        "authorized_terminal_route": ["P11-RC", "P11-90", "P11-91", "P11-99"],
    }


def build_ledger(records: list[dict[str, Any]]) -> dict[str, Any]:
    claim_evidence = {
        "milestone_a_inherited": ["P11-00"],
        "milestone_b_not_proven": ["P11-04"],
        "milestone_c_proven_private_fixture_bounded": ["P11-05", "P11-06"],
        "milestone_d_not_proven": ["P11-07"],
        "milestone_e_not_proven": ["P11-RC"],
        "milestone_f_not_proven": ["P11-RC"],
        "milestone_g_not_proven": ["P11-RC"],
        "gpu_command_proof_proven": ["P11-05"],
        "initialization_proof_not_proven": ["P11-04", "P11-90"],
        "frame_proof_not_proven": ["P11-07", "P11-90"],
        "playability_proof_not_proven": ["P11-RC", "P11-90"],
        "general_ps1_compatibility_not_proven_permanent": ["P11-00", "P11-90"],
        "b0_57_public_contract": ["P11-07"],
        "b0_5b_target_missing": ["P11-07"],
        "queue_reconciliation_authorized": ["P11-RC"],
        "whole_regression_reconciled": ["P11-90"],
        "p11_08_through_p11_12_not_executed": ["P11-RC", "P11-90"],
    }
    return {
        "schema": "openrecomp-phase11-claim-ledger-v1",
        "stage": STAGE,
        "claims": [
            {"key": key, "evidence_stages": stages}
            for key, stages in sorted(claim_evidence.items())
        ],
        "reserved_non_claims_at_p11_91": list(RESERVED_MARKERS),
        "permanent_non_claim": GENERAL_MARKER,
        "gpu_command_proof_marker": GPU_MARKER,
        "stage_records": [
            {"stage": item["stage"], "checks_passed": item["checks_passed"]}
            for item in records
        ],
    }


def scan_tracked_evidence(payload: bytes) -> dict[str, Any]:
    sample_hex = payload[:64].hex()
    sample_b64 = base64.b64encode(payload[:64]).decode("ascii")
    ascii_runs: list[str] = []
    for start in range(0, min(len(payload), 4096) - 8):
        run = payload[start:start + 8]
        if all(32 <= byte < 127 for byte in run):
            ascii_runs.append(run.decode("ascii"))
    host_patterns = (
        re.compile(r"[A-Za-z]:[\\](?![\\])"),
        re.compile(r"/Users/"),
        re.compile(r"/home/[a-z]"),
    )
    files = git("ls-files", ".openrecomp-phase11/evidence").splitlines()
    payload_violations: list[str] = []
    path_violations: list[str] = []
    for relative in files:
        blob = subprocess.run(
            ["git", "show", f"HEAD:{relative}"], cwd=str(ROOT), check=False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        check(f"safety:tracked:{relative}", blob.returncode == 0, relative)
        text = blob.stdout.decode("utf-8", "replace")
        lowered = text.lower()
        if sample_hex in lowered or sample_b64 in text:
            payload_violations.append(relative)
        elif any(candidate in text for candidate in ascii_runs):
            payload_violations.append(relative + ":ascii")
        if any(pattern.search(text) for pattern in host_patterns):
            path_violations.append(relative)
    return {
        "files_scanned": len(files),
        "private_payload_violations": sorted(set(payload_violations)),
        "host_path_violations": sorted(set(path_violations)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-91")
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        records = verify_stage_records()
        verify_exact_records()
        verify_claim_markers()
        verify_manifest()

        index = build_index(records)
        write_json(evidence / "evidence_index.json", index)
        check("index:file-count-positive", index["file_count"] > 0, index["file_count"])

        matrix = build_proof_matrix()
        write_json(evidence / "proof_matrix.json", matrix)
        check("matrix:highest-milestone", matrix["highest_proven_milestone"] == "C",
              matrix["highest_proven_milestone"])
        check("matrix:reserved-count", len(matrix["terminal_claims_reserved_at_p11_91"]) == 4,
              matrix["terminal_claims_reserved_at_p11_91"])

        ledger = build_ledger(records)
        write_json(evidence / "claim_ledger.json", ledger)
        check("ledger:reserved-count", len(ledger["reserved_non_claims_at_p11_91"]) == 4,
              ledger["reserved_non_claims_at_p11_91"])

        payload_path = ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
        payload = payload_path.read_bytes()[0x800:0x1800]
        safety = scan_tracked_evidence(payload)
        check("safety:files-scanned", safety["files_scanned"] >= 120,
              safety["files_scanned"])
        check("safety:no-private-payload", not safety["private_payload_violations"],
              safety["private_payload_violations"])
        check("safety:no-host-paths", not safety["host_path_violations"],
              safety["host_path_violations"])
        write_json(evidence / "safety_scan.json", {
            "schema": "openrecomp-phase11-safety-scan-v1",
            "stage": STAGE,
            **safety,
        })
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:
        RESULTS.append({
            "check": "gate:exception", "status": "FAIL",
            "detail": f"{type(exc).__name__}: {exc}",
        })

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    ordered = sorted(RESULTS, key=lambda item: item["check"])
    tests = {
        "schema": "openrecomp-phase11-tests-v1",
        "stage": STAGE,
        "status": status,
        "checks": ordered,
        "summary": {
            "passed": sum(item["status"] == "PASS" for item in ordered),
            "failed": len(failed),
        },
    }
    write_json(evidence / "p11_91_tests.json", tests)
    for item in ordered:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P11_91={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(ordered)}")
    print(INITIALIZATION_MARKER)
    print(FRAME_MARKER)
    print(PLAYABILITY_MARKER)
    print(GENERAL_MARKER)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
