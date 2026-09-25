#!/usr/bin/env python3
"""OpenRecomp Phase-15 gate helpers V1 (deterministic, fail-closed)."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from typing import Any


DEFAULT_CLAIM_MARKERS = {
    "OPENRECOMP_PHASE15_HERCULES_INITIALIZATION_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE15_HERCULES_FRAME_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE15_HERCULES_PLAYABILITY_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE15_GENERAL_PS1_COMPATIBILITY": "NOT_PROVEN",
}


class Gate:
    def __init__(self, stage: str) -> None:
        self.stage = stage
        self.results: list[dict[str, str]] = []
        self.markers: list[str] = []

    def check(self, label: str, condition: bool, detail: str = "") -> None:
        self.results.append({
            "check": label,
            "status": "PASS" if condition else "FAIL",
            "detail": detail,
        })
        if not condition:
            raise AssertionError(f"{label}: condition failed ({detail})")

    def mark(self, marker: str, value: str = "PASS") -> None:
        self.markers.append(f"{marker}={value}")

    def tests_document(self, name: str) -> dict[str, Any]:
        return {
            "schema": "openrecomp-phase15-tests-v1",
            "stage": self.stage,
            "checks": self.results,
            "summary": {
                "passed": sum(item["status"] == "PASS" for item in self.results),
                "failed": sum(item["status"] == "FAIL" for item in self.results),
            },
            "name": name,
        }

    def emit(self) -> None:
        for item in self.results:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        for marker in self.markers:
            print(marker)
        print(f"{self.stage}_CHECKS={len(self.results)}")


def write_json(path: pathlib.Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def assert_public_safe(gate: Gate, label: str, document: dict[str, Any],
                       payload: bytes) -> None:
    text = json.dumps(document, sort_keys=True)
    sample = payload[:64]
    gate.check(f"{label}:no-private-path", ":\\" not in text and "fixtures/" not in text,
               "absolute private paths absent")
    if sample:
        gate.check(f"{label}:no-payload-hex", sample.hex() not in text.lower(),
                   "payload sample absent")
    else:
        gate.check(f"{label}:no-payload-hex", True, "no payload supplied")
    gate.check(f"{label}:no-raw-words",
               all(term not in text for term in ("raw_instruction", "instruction_word",
                                                 "payload_bytes", "bios_bytes")),
               "reconstructive fields absent")


def run_stage(stage: str, body, default_evidence: str):
    import argparse
    import pathlib as _pathlib

    root = _pathlib.Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=default_evidence)
    options = parser.parse_args()
    evidence = (root / options.evidence_dir).resolve()
    gate = Gate(stage)
    try:
        integrity = subprocess.run(
            [sys.executable, str(root / ".openrecomp-phase15" / "src"
                                 / "p15_source_manifest_v1.py")],
            cwd=str(root), capture_output=True, text=True,
        )
        gate.check(
            "integrity:phase15-sources",
            integrity.returncode == 0,
            integrity.stdout.strip() or integrity.stderr.strip(),
        )
        body(gate, evidence, root)
    except AssertionError as exc:
        print(f"FAIL: {stage}:{exc}")
        return 1
    except Exception as exc:  # fail closed without a traceback
        print(f"FAIL: {stage}:{type(exc).__name__}:{exc}")
        return 1
    for marker, value in DEFAULT_CLAIM_MARKERS.items():
        if not any(item.startswith(f"{marker}=") for item in gate.markers):
            gate.mark(marker, value)
    result_path = evidence / "RESULT.json"
    if result_path.is_file():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        markers = result.setdefault("markers", {})
        for marker, value in DEFAULT_CLAIM_MARKERS.items():
            markers.setdefault(marker, value)
        write_json(result_path, result)
    tests_name = f"{stage.lower().replace('-', '_')}_tests.json"
    write_json(evidence / tests_name, gate.tests_document(stage))
    gate.emit()
    return 0
