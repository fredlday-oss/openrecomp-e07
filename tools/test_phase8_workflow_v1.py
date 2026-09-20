#!/usr/bin/env python3
"""OpenRecomp Phase-8 reusable ELF-to-native workflow gate (P8-10).

P8-10 exercises the deterministic reusable workflow
(`.openrecomp-phase8/src/p8_workflow_v1.py`) end to end on the frozen
fixture and proves fail-closed behaviour for malformed and unsupported
inputs, each rejected with an explicit stable category (no guessed recovery,
no silent compatibility widening).

On success it emits::

    OPENRECOMP_P8_10=PASS
    OPENRECOMP_PHASE8_WORKFLOW_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_workflow_v1.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))

import p8_workflow_v1 as workflow  # noqa: E402

EVIDENCE_DIR = ROOT / ".openrecomp-phase8" / "evidence" / "P8-10"
WORKSPACE = ROOT / ".openrecomp-phase8" / "build" / "P8-10"
NEGATIVE_DIR = WORKSPACE / "negatives"

STAGE = "P8-10"
STAGE_MARKER = "OPENRECOMP_P8_10"
FEATURE_MARKER = "OPENRECOMP_PHASE8_WORKFLOW_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

FIXTURE_ELF = ROOT / ".openrecomp-phase8" / "build" / "P8-01" / "candidate-a" / "p8_aes128_mips32_O1.elf"
FIXTURE_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"
P8_09_EVIDENCE = ROOT / ".openrecomp-phase8" / "evidence" / "P8-09" / "reference_equivalence.json"

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL", "detail": detail})
        raise AssertionError(f"{label}: condition failed ({detail})")
    RESULTS.append({"check": label, "status": "PASS", "detail": detail})
    print(f"PASS: {label}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evidence_json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_evidence(name: str, payload: object) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_bytes(evidence_json(payload))


def patch_word(data: bytes, address: int, word: int) -> bytes:
    # The frozen fixture's `.text` segment maps file offset 0x1000 == vaddr.
    mutated = bytearray(data)
    mutated[address : address + 4] = word.to_bytes(4, "little")
    return bytes(mutated)


def main() -> int:
    try:
        data = FIXTURE_ELF.read_bytes()
        check("fixture:sha256", sha256_bytes(data) == FIXTURE_SHA256, sha256_bytes(data))

        if WORKSPACE.exists():
            shutil.rmtree(WORKSPACE)
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        NEGATIVE_DIR.mkdir(parents=True, exist_ok=True)

        result = workflow.run_workflow(FIXTURE_ELF, workspace=WORKSPACE / "fixture")
        check("fixture:outcome", result["outcome"] == "COMPLETED", json.dumps(result, sort_keys=True)[:300])
        check("fixture:stages", {"elf_identity", "frontier", "structure", "contract_digest", "emission", "build", "native", "reference", "equivalence"} <= set(result), json.dumps(sorted(result)))
        check("fixture:equivalence-none-excluded", result["equivalence"] == {"excluded_observables": [], "mismatches": {}}, json.dumps(result["equivalence"], sort_keys=True))
        check("fixture:emission-fingerprint", result["emission"]["program_fingerprint"] == "3df423e0efdd1b6d0c91ce9f95bd33d0b58f08833226314bd43aff407751c704", result["emission"]["program_fingerprint"])
        check("fixture:native-exit", result["native"]["exit_status"] == "0x00000000", result["native"]["exit_status"])

        recorded = json.loads(P8_09_EVIDENCE.read_text(encoding="utf-8"))
        reference_recorded = recorded["reference"]["observables"]
        check(
            "fixture:workflow-matches-p8-09",
            result["reference"]["registers_digest"] == reference_recorded["registers_digest"]
            and result["reference"]["memory_digest"] == reference_recorded["memory_digest"]
            and result["reference"]["transcript_digest"] == reference_recorded["transcript_digest"]
            and result["native"]["exit_status"] == reference_recorded["exit_status"],
            json.dumps(
                {
                    "workflow": {
                        "registers": result["reference"]["registers_digest"],
                        "memory": result["reference"]["memory_digest"],
                        "transcript": result["reference"]["transcript_digest"],
                    },
                    "p8_09": {
                        "registers": reference_recorded["registers_digest"],
                        "memory": reference_recorded["memory_digest"],
                        "transcript": reference_recorded["transcript_digest"],
                    },
                },
                sort_keys=True,
            ),
        )

        # second identical run: deterministic result record
        repeat = workflow.run_workflow(FIXTURE_ELF, workspace=WORKSPACE / "fixture-repeat")
        check("fixture:deterministic-result", repeat == result, "identical workflow record")

        negatives: list[dict[str, str]] = []

        def expect_category(name: str, payload: bytes, category: str, *, expected_observable=None, compiler=None) -> None:
            path = NEGATIVE_DIR / f"{name}.elf"
            path.write_bytes(payload)
            outcome = workflow.run_workflow(
                path,
                workspace=NEGATIVE_DIR / name,
                expected_observable=expected_observable,
                compiler=compiler,
            )
            negatives.append({"case": name, "outcome": outcome["outcome"], "category": outcome["category"], "stage": outcome["stage"]})
            check(f"reject:{name}", outcome["outcome"] == "FAIL_CLOSED" and outcome["category"] == category, json.dumps(outcome, sort_keys=True)[:300])

        expect_category("not-an-elf", b"this is not an elf image at all", "UNSUPPORTED_ELF_CONTAINER")
        expect_category("truncated", data[:64], "UNSUPPORTED_ELF_CONTAINER")
        wrong_type = bytearray(data)
        wrong_type[16:18] = (3).to_bytes(2, "little")  # ET_DYN
        expect_category("et-dyn", bytes(wrong_type), "UNSUPPORTED_ELF_CONTAINER")
        expect_category("unsupported-op", patch_word(data, 0x2440, 0x0085001B), "UNSUPPORTED_ISA_SEMANTIC")  # div
        expect_category("indirect-return", patch_word(data, 0x247C, (25 << 21) | 0x08), "UNRESOLVED_INDIRECT_CONTROL_FLOW")  # jr $t9
        expect_category("toolchain-missing", data, "TOOLCHAIN_UNAVAILABLE", compiler="definitely-not-a-compiler.exe")
        expect_category(
            "reference-mismatch",
            data,
            "REFERENCE_MISMATCH",
            expected_observable={"exit_status": "0xdeadbeef"},
        )

        write_evidence(
            "workflow.json",
            {
                "stage": STAGE,
                "workflow_version": workflow.WORKFLOW_VERSION,
                "fixture": {"sha256": FIXTURE_SHA256},
                "result": result,
                "negative_cases": negatives,
                "markers": {
                    "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
                    "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
                },
            },
        )
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    status = "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    record = {
        "stage": STAGE,
        "stage_name": "Reusable real-MIPS32 ELF-to-native workflow",
        "status": status,
        "tests": len(RESULTS),
        "passed": sum(1 for item in RESULTS if item["status"] == "PASS"),
        "failed": sum(1 for item in RESULTS if item["status"] != "PASS"),
        "checks": RESULTS,
        "failure": None if status == "PASS" else [item for item in RESULTS if item["status"] != "PASS"],
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={len(RESULTS)}",
            "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
            "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
        },
    }
    write_evidence("p8_10_tests.json", record)

    for item in RESULTS:
        if item["status"] != "PASS":
            print(f"FAIL: {item['check']} :: {item.get('detail', '')}")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(RESULTS)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
