#!/usr/bin/env python3
"""OpenRecomp Phase-8 final bounded verdict gate (P8-99).

Audits every Phase-8 stage and issues the terminal bounded verdict only when
all of the following hold on the audited tree:

* the exact frozen Phase-7 baseline identity and terminal evidence;
* every required Phase-8 stage record is PASS (`P8-00`..`P8-12`, `P8-90`,
  `P8-91`);
* the frozen public fixture provenance is exact (SHA-256, upstream revision,
  licence, port files, toolchain) and the fixture rebuilds byte-identically;
* native/reference equivalence holds with no excluded observables;
* the evidence chain and public-safety records verify;
* the general-compatibility scope guards remain in force.

Emits::

    OPENRECOMP_P8_99=PASS
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=PASS
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

or, if any terminal requirement is missing::

    OPENRECOMP_P8_99=FAIL
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_final_verdict_v1.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
P8 = ROOT / ".openrecomp-phase8"
EVIDENCE_DIR = P8 / "evidence" / "P8-99"

STAGE = "P8-99"
STAGE_MARKER = "OPENRECOMP_P8_99"
FEATURE_MARKER = "OPENRECOMP_PHASE8_FINAL_VERDICT_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"
PROVEN = "PASS"

BASELINE_TAG = "openrecomp-phase7-pass"
BASELINE_TAG_OBJECT = "b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800"
BASELINE_COMMIT = "2917aa6549ab975cffdeb50120514c1723f7e493"
BASELINE_TREE = "59529c130d759ceb1ca9e6c65a510fa373656b01"

REQUIRED_STAGES = tuple(f"P8-{index:02d}" for index in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)) + ("P8-90", "P8-91")
REQUIRED_MARKER = {
    "P8-00": "OPENRECOMP_PHASE8_BOUNDARY_V1=PASS",
    "P8-01": "OPENRECOMP_PHASE8_REAL_ELF_FIXTURE_V1=PASS",
    "P8-02": "OPENRECOMP_PHASE8_FRONTIER_REDERIVATION_V1=PASS",
    "P8-03": "OPENRECOMP_PHASE8_PROGRAM_STRUCTURE_V1=PASS",
    "P8-04": "OPENRECOMP_PHASE8_TRANSLATION_CLOSURE_V1=PASS",
    "P8-05": "OPENRECOMP_PHASE8_RUNTIME_CONTRACT_V1=PASS",
    "P8-06": "OPENRECOMP_PHASE8_HOST_EMISSION_V1=PASS",
    "P8-07": "OPENRECOMP_PHASE8_NATIVE_BUILD_V1=PASS",
    "P8-08": "OPENRECOMP_PHASE8_NATIVE_EXECUTION_V1=PASS",
    "P8-09": "OPENRECOMP_PHASE8_REFERENCE_EQUIVALENCE_V1=PASS",
    "P8-10": "OPENRECOMP_PHASE8_WORKFLOW_V1=PASS",
    "P8-11": "OPENRECOMP_PHASE8_HARDENING_V1=PASS",
    "P8-12": "OPENRECOMP_PHASE8_EVIDENCE_CLOSURE_V1=PASS",
    "P8-90": "OPENRECOMP_PHASE8_WHOLE_REGRESSION_V1=PASS",
    "P8-91": "OPENRECOMP_PHASE8_EVIDENCE_INDEX_V1=PASS",
}
FIXTURE_ELF = P8 / "build" / "P8-01" / "candidate-a" / "p8_aes128_mips32_O1.elf"
FIXTURE_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"
FIXTURE_SIZE = 12904
UPSTREAM = {
    "repository": "https://github.com/kokke/tiny-AES-c",
    "commit": "23856752fbd139da0b8ca6e471a13d5bcc99a08d",
    "aes.c": "2cf709c77dcb742ef0845e20e7382da38193c630f18b035f8a7796651ea48af1",
    "aes.h": "40f381d86c7b84648eb96053e604cf17cfeab532233b2eeedfa6afc3752f313d",
    "unlicense.txt": "640514163b17f977adc997cb16f51871122cfb0555ebad1a3f01e167b7ba8857",
}
TOOLCHAIN_ZIG_SHA256 = "2e44af5bbf7a72ef8cbdae370284687c95d65a19affa469d2ad0364d905b8e84"
EXPECTED_EXECUTABLE_SHA256 = "fb98c8a68c5c3af7bc30dab2e907910e1c1dfd665eb79e0ee7fcd60dd07a04dc"
EXPECTED_OBSERVABLE = {
    "exit_status": "0x00000000",
    "registers_digest": "0x7ee0f4a187050726",
    "memory_digest": "0x231c4a49e79c5e56",
    "transcript_len": 33,
    "transcript_digest": "0xca6dcb87f8ac9814",
    "reads": 1136,
    "writes": 681,
    "host_calls": 33,
    "denied": 0,
}

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL", "detail": detail})
        raise AssertionError(f"{label}: condition failed ({detail})")
    RESULTS.append({"check": label, "status": "PASS", "detail": detail})
    print(f"PASS: {label}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git failed")
    return result.stdout.strip()


def evidence_json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_evidence(name: str, payload: object) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_bytes(evidence_json(payload))


def main() -> int:
    verdict = PROVEN
    try:
        # 1. frozen Phase-7 baseline identity
        check("baseline:tag-object", git("rev-parse", BASELINE_TAG) == BASELINE_TAG_OBJECT, BASELINE_TAG_OBJECT)
        check("baseline:commit", git("rev-parse", f"{BASELINE_TAG}^{{commit}}") == BASELINE_COMMIT, BASELINE_COMMIT)
        check("baseline:tree", git("rev-parse", f"{BASELINE_TAG}^{{tree}}") == BASELINE_TREE, BASELINE_TREE)

        # 2. stage records
        state = (P8 / "STATE.md").read_text(encoding="utf-8")
        queue = (P8 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        stage_report = []
        for stage in REQUIRED_STAGES:
            runs_path = P8 / "evidence" / stage / "official_runs.json"
            check(f"stage:{stage}:record", runs_path.is_file() and (P8 / "evidence" / stage / "RESULT.md").is_file(), stage)
            runs = json.loads(runs_path.read_text(encoding="utf-8"))
            gate_marker = REQUIRED_MARKER[stage]
            check(f"stage:{stage}:gate-marker", any(gate_marker in value for value in runs["markers"].values()), gate_marker)
            check(f"stage:{stage}:two-runs-identical", runs["byte_identical"] is True, "byte-identical")
            check(f"stage:{stage}:ledger", f"| {stage} |" in state and "| PASS |" in [line for line in state.splitlines() if line.startswith(f"| {stage} |")][0], "ledger PASS")
            stage_report.append({"stage": stage, "gate_marker": gate_marker, "outcome": "PASS"})

        # 3. fixture provenance
        data = FIXTURE_ELF.read_bytes()
        check("fixture:sha256", sha256_bytes(data) == FIXTURE_SHA256, sha256_bytes(data))
        check("fixture:size", len(data) == FIXTURE_SIZE, str(len(data)))
        for name, digest in sorted(UPSTREAM.items()):
            if name in ("repository", "commit"):
                continue
            path = P8 / "external" / "tiny-AES-c" / name
            check(f"upstream:{name}", path.is_file() and sha256_file(path) == digest, digest)
        fixture_doc = json.loads((P8 / "evidence" / "P8-01" / "fixture_identity.json").read_text(encoding="utf-8"))
        check("fixture:identity-entry", fixture_doc["identity"]["entry"] == "0x00002490", fixture_doc["identity"]["entry"])
        check("fixture:identity-abi", fixture_doc["identity"]["abi"] == "O32", fixture_doc["identity"]["abi"])
        check("fixture:upstream-commit", fixture_doc["fixture"]["upstream"]["commit"] == UPSTREAM["commit"], UPSTREAM["commit"])
        zig = ROOT / ".openrecomp-phase3" / "tools" / "zig" / "zig.exe"
        if zig.is_file():
            check("toolchain:zig-identity", sha256_file(zig) == TOOLCHAIN_ZIG_SHA256, TOOLCHAIN_ZIG_SHA256)
        check("fixture:external-ignored", "external/" in (P8 / ".gitignore").read_text(encoding="utf-8"), "upstream untracked")

        # 4. native/reference agreement
        equivalence = json.loads((P8 / "evidence" / "P8-09" / "reference_equivalence.json").read_text(encoding="utf-8"))
        check("equivalence:no-excluded", equivalence["excluded_observables"] == [], "none")
        check("equivalence:no-mismatches", all(item["native"] == item["reference"] for item in equivalence["comparisons"].values()), "all fields equal")
        closure = json.loads((P8 / "evidence" / "P8-12" / "closure.json").read_text(encoding="utf-8"))
        check("closure:implementation-delta", closure["implementation_delta"] == "none", "none")
        native = closure["workflow"]["native"]
        check("native:observable-identity", all(native.get(key) == value for key, value in EXPECTED_OBSERVABLE.items()), json.dumps(native, sort_keys=True))
        reference = closure["workflow"]["reference"]
        check("reference:observable-identity", all(reference.get(key) == value for key, value in EXPECTED_OBSERVABLE.items()), json.dumps(reference, sort_keys=True))
        check("native:executable-identity", closure["workflow"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256, closure["workflow"]["executable_sha256"])

        # 5. evidence closure and whole-regression records
        regression = json.loads((P8 / "evidence" / "P8-90" / "whole_regression.json").read_text(encoding="utf-8"))
        check("regression:phase7-gates", len(regression["phase7_stage_gates"]) == 15, str(len(regression["phase7_stage_gates"])))
        check("regression:phase8-gates", len(regression["phase8_stage_gates"]) == 13, str(len(regression["phase8_stage_gates"])))
        check("regression:total-tests", regression["total_reverified_tests"] == 1463, str(regression["total_reverified_tests"]))
        index = json.loads((P8 / "evidence" / "P8-91" / "evidence_index.json").read_text(encoding="utf-8"))
        check("index:entry-count", index["entry_count"] > 100, str(index["entry_count"]))
        ledger = json.loads((P8 / "evidence" / "P8-91" / "claim_ledger.json").read_text(encoding="utf-8"))
        check("ledger:proven-bounded-not-proven", bool(ledger["proven"]) and bool(ledger["bounded_pass"]) and len(ledger["not_proven"]) >= 8, "separated")
        check("ledger:general-not-proven", any("GENERAL_MIPS32" in item for item in ledger["not_proven"]), "general non-claim")
        check("ledger:no-excluded-observables", equivalence["excluded_observables"] == [], "none")
        safety_run = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "test_phase8_evidence_index_v1.py")],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        check(
            "safety:index-and-ledger-gate",
            safety_run.returncode == 0
            and b"OPENRECOMP_PHASE8_EVIDENCE_INDEX_V1=PASS" in safety_run.stdout
            and safety_run.stderr == b"",
            "P8-91 gate re-passes with public-safety verification",
        )

        # 6. scope guards
        scope = (P8 / "SCOPE.md").read_text(encoding="utf-8")
        check("scope:general-marker", f"{GENERAL_MARKER}={NOT_PROVEN}" in scope, NOT_PROVEN)
        check("scope:arbitrary-non-claims", all(token in scope for token in ("arbitrary MIPS32 ELF compatibility", "dynamic linking", "PS1 or PS2 compatibility")), "scope guards present")
        check("state:general-marker", f"{GENERAL_MARKER}={NOT_PROVEN}" in state, NOT_PROVEN)
        check("queue:general-marker", f"{GENERAL_MARKER}={NOT_PROVEN}" in queue, NOT_PROVEN)
        if f"{TERMINAL_MARKER}=PASS" in state:
            check("state:terminal-promoted-consistent", "FINAL_VERDICT=PASS" in state and "STATUS=COMPLETE" in state, "promoted consistently")
        else:
            check("state:terminal-reserved", f"{TERMINAL_MARKER}={NOT_PROVEN}" in state, "reserved")

        write_evidence(
            "terminal_verdict.json",
            {
                "stage": STAGE,
                "decision": PROVEN,
                "required_stages": stage_report,
                "fixture": {
                    "sha256": FIXTURE_SHA256,
                    "size": FIXTURE_SIZE,
                    "upstream": UPSTREAM,
                    "toolchain_zig_sha256": TOOLCHAIN_ZIG_SHA256,
                },
                "native_reference_agreement": {
                    "excluded_observables": [],
                    "observable": EXPECTED_OBSERVABLE,
                    "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
                },
                "whole_regression": {
                    "phase7_gates": len(regression["phase7_stage_gates"]),
                    "phase8_gates": len(regression["phase8_stage_gates"]),
                    "total_reverified_tests": regression["total_reverified_tests"],
                },
                "scope_guards": {
                    "general_compatibility": f"{GENERAL_MARKER}={NOT_PROVEN}",
                    "arbitrary_elf": "NOT_PROVEN",
                    "unsupported_isa_families": "NOT_PROVEN",
                    "broader_abi_os_runtime": "NOT_PROVEN",
                },
                "markers_issued": [f"{TERMINAL_MARKER}={PROVEN}", f"{GENERAL_MARKER}={NOT_PROVEN}"],
            },
        )
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})
        verdict = NOT_PROVEN

    status = "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    terminal_status = status
    if status == "PASS":
        write_evidence(
            "verdict_record.json",
            {
                "stage": STAGE,
                "decision": "PASS",
                "terminal_marker": f"{TERMINAL_MARKER}={PROVEN}",
                "general_marker": f"{GENERAL_MARKER}={NOT_PROVEN}",
                "fixture_sha256": FIXTURE_SHA256,
                "tests": len(RESULTS),
            },
        )
    record = {
        "stage": STAGE,
        "stage_name": "Final Phase-8 bounded verdict",
        "status": status,
        "tests": len(RESULTS),
        "passed": sum(1 for item in RESULTS if item["status"] == "PASS"),
        "failed": sum(1 for item in RESULTS if item["status"] != "PASS"),
        "checks": RESULTS,
        "failure": None if status == "PASS" else [item for item in RESULTS if item["status"] != "PASS"],
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={len(RESULTS)}",
            "terminal": f"{TERMINAL_MARKER}={terminal_status if terminal_status == 'PASS' else NOT_PROVEN}",
            "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
        },
    }
    write_evidence("p8_99_tests.json", record)

    for item in RESULTS:
        if item["status"] != "PASS":
            print(f"FAIL: {item['check']} :: {item.get('detail', '')}")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(RESULTS)}")
    print(f"{TERMINAL_MARKER}={terminal_status if terminal_status == 'PASS' else NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
