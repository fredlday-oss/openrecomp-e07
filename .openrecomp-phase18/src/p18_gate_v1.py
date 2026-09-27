#!/usr/bin/env python3
"""OpenRecomp Phase-18 gate helpers V1 (deterministic, fail-closed).

Semantics are inherited from the Phase-17 gate helper so Phase-18 evidence is
held to the same public-safety standard. Phase 18 owns its own copy; the
Phase-17 tree is never modified.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]

from p18_contracts_v1 import (  # noqa: E402
    BOOTSTRAP_MARKER,
    FIRST_FRAME_READY_MARKER,
    FRAME_MARKER,
    GENERAL_MARKER,
    INITIALIZATION_MARKER,
    PLAYABILITY_MARKER,
)


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
            "schema": "openrecomp-phase18-tests-v1",
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


FORBIDDEN_PRIVATE_PATHS = (
    "/home/fred/private/location",
    "/Users/example/private/location",
    "/tmp/private-fixture",
    r"C:\private\fixture",
)

#: Substrings that must never appear in committed Phase-18 evidence documents.
FORBIDDEN_EVIDENCE_SUBSTRINGS = (
    r"C:\Users\fredd",
    r"C:\private",
    "imported-recon/pc-phase1-17/reconnaissance",
    "imported-recon/pc-phase1-17/psx_recon",
)


def reject_private_path(path: str) -> tuple[bool, str | None]:
    """Fail-closed public-safety check for a single string value."""
    normal = path.replace("/", "\\")
    for forbidden in FORBIDDEN_PRIVATE_PATHS:
        if path == forbidden:
            return True, forbidden
        if normal == forbidden.replace("/", "\\"):
            return True, forbidden
    lowered = path.lower()
    if ":\\" in path or path.startswith("\\\\"):
        return True, "windows-or-unc-absolute"
    if path.startswith("/home/") or path.startswith("/Users/") or path.startswith("/tmp/"):
        return True, "unix-absolute-home-or-tmp"
    if path.startswith("/private/") or "fixtures/private" in lowered:
        return True, "absolute-or-private-pattern"
    return False, None


def _walk_strings(obj: Any) -> list[str]:
    found: list[str] = []
    if isinstance(obj, str):
        found.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            found.extend(_walk_strings(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk_strings(item))
    return found


def assert_public_safe(gate: Gate, label: str, document: dict[str, Any],
                       payload: bytes | None = None) -> None:
    text = json.dumps(document, sort_keys=True)
    forbidden = [path for path in FORBIDDEN_PRIVATE_PATHS if path in text]
    gate.check(f"{label}:no-private-path",
               not forbidden and ":\\" not in text and "fixtures/" not in text,
               "absolute private paths absent")

    hits: list[str] = []
    for value in _walk_strings(document):
        rejected, _ = reject_private_path(value)
        if rejected:
            hits.append(value)
    gate.check(f"{label}:reject-private-paths", not hits,
               json.dumps(hits, sort_keys=True) if hits else "no private paths in values")

    imported_hits = [term for term in FORBIDDEN_EVIDENCE_SUBSTRINGS if term in text]
    gate.check(f"{label}:no-import-private-paths", not imported_hits,
               json.dumps(imported_hits, sort_keys=True) if imported_hits else "no import paths")

    positive_ok, _ = reject_private_path("relative/synthetic/control.bin")
    gate.check(f"{label}:positive-safe-relative-path", not positive_ok,
               "ordinary public-safe relative path accepted")

    if payload:
        sample = payload[:64]
        gate.check(f"{label}:no-payload-hex", sample.hex() not in text.lower(),
                   "payload sample absent")
    else:
        gate.check(f"{label}:no-payload-hex", True, "no payload supplied")
    gate.check(f"{label}:no-raw-words",
               all(term not in text for term in ("raw_instruction", "instruction_word",
                                                 "payload_bytes", "bios_bytes")),
               "reconstructive fields absent")


def run_stage(stage: str, body, default_evidence: str):
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=default_evidence)
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    gate = Gate(stage)
    try:
        integrity = subprocess.run(
            [sys.executable, str(ROOT / ".openrecomp-phase18" / "src"
                                 / "p18_source_manifest_v1.py")],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        gate.check(
            "integrity:phase18-sources",
            integrity.returncode == 0
            and "OPENRECOMP_PHASE18_SOURCE_INTEGRITY=PASS" in integrity.stdout,
            integrity.stdout.strip() or integrity.stderr.strip(),
        )
        body(gate, evidence, ROOT)
    except AssertionError as err:
        gate.emit()
        sys.stderr.write(f"{stage} failed: {err}\n")
        return 1
    except Exception as err:
        gate.check(f"{stage}:unhandled-exception", False, f"{type(err).__name__}: {err}")
        gate.emit()
        sys.stderr.write(f"{stage} exception: {err}\n")
        return 2

    write_json(evidence / f"{stage.lower().replace('-', '_')}_tests.json",
               gate.tests_document(f"{stage} Test Results"))
    gate.emit()
    return 0
