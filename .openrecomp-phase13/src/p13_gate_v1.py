#!/usr/bin/env python3
"""OpenRecomp Phase-13 gate helpers V1 (deterministic, fail-closed)."""

from __future__ import annotations

import json
import pathlib
from typing import Any


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
            "schema": "openrecomp-phase13-tests-v1",
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
        body(gate, evidence, root)
    except AssertionError as exc:
        print(f"FAIL: {stage}:{exc}")
        return 1
    except Exception as exc:  # fail closed without a traceback
        print(f"FAIL: {stage}:{type(exc).__name__}:{exc}")
        return 1
    gate.emit()
    return 0
